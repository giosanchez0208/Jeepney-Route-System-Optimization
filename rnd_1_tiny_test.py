"""
rnd_1_tiny_test.py — TINY smoke test + timing probe for rnd_1_ticks_and_rate.ipynb

WHY THIS EXISTS
  Run this on a small/slow box (e.g. a 4-core, no-GPU laptop) BEFORE handing the
  full notebook to thesismates. It does two things:
    1. Confirms the whole calibration machinery runs end-to-end with no anomaly
       (workers spawn, TravelGraph caches, sims return valid scores/completions).
    2. Prints the wall-clock runtime of each part ON THIS MACHINE, so per-eval
       costs are known before committing to the full sweep.

  It uses the SAME code paths as the full notebook (persistent pool + per-call
  overrides via run_reps_overrides), just with a tiny grid: one route count,
  few replications, short horizons, low density.

RUN
  python rnd_1_tiny_test.py

NOTE
  Standalone multiprocessing scripts MUST guard execution under
  `if __name__ == "__main__":` on Windows (spawn re-imports this module).
"""
import os
import sys
import time
import random
import csv
import numpy as np

sys.path.insert(0, os.getcwd())

# ── TINY CONFIG (intentionally small) ────────────────────────────────────────
ROUTE_COUNTS     = [5]            # one production-sized route set is enough to smoke-test
HORIZON_TICKS    = [60, 120, 180] # 10 / 20 / 30 simulated minutes at SPT=10
PAX_PER_ROUTE_HR = [50, 150]      # two densities for the volume sweep
REPLICATIONS     = 3              # CV needs >= 2; 3 keeps it to ~one wave on a 4-core box
JEEPS_PER_ROUTE  = 10
SPT              = 10             # Δt fixed at 10s (matches the full notebook)
HORIZON_DENSITY  = 50             # low density held fixed during the horizon sweep
VOLUME_TICKS     = 120            # short horizon held fixed during the volume sweep
CV_THRESHOLD     = 0.05

CG_PKL  = "rnd/pkl/profile_p1.pkl"
DDM_PKL = "rnd/pkl/ddm_8am.pkl"


def compute_cv(scores):
    if len(scores) < 2:
        return float("nan")
    arr = np.array(scores, dtype=float)
    m = arr.mean()
    return float(arr.std(ddof=1) / m) if abs(m) > 1e-9 else float("nan")


def main():
    random.seed(42)
    np.random.seed(42)

    from utils_simplified import (
        reuse_citygraph, reuse_ddm, generate_route_system, run_reps_overrides,
    )
    from utils.simulation_parallel import ParallelSimulationRunner
    import yaml

    timings = []   # [(phase_name, seconds)]
    eval_log = []  # [{tag, ticks, rate, n_ok, cv, completion, wall}]

    n_cores = os.cpu_count() or 1
    workers = min(REPLICATIONS, max(1, n_cores - 1))
    waves_per_eval = -(-REPLICATIONS // workers)  # ceil division

    print("=" * 66)
    print("TINY TEST — rnd_1_ticks_and_rate")
    print(f"This machine: {n_cores} cores -> {workers} workers | "
          f"{REPLICATIONS} reps = {waves_per_eval} wave(s) per eval")
    print("=" * 66)

    # ── load heavy objects ──
    t0 = time.time()
    G_city = reuse_citygraph(CG_PKL)
    ddm = reuse_ddm(DDM_PKL)
    dt = time.time() - t0
    timings.append(("load CityGraph+DDM", dt))
    print(f"[load]  {len(G_city.nodes)} nodes, {len(G_city.graph)} edges | {dt:.1f}s")

    # ── open ONE persistent pool ──
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)
    base_cfg["cg_pkl"] = CG_PKL
    base_cfg["ddm_pkl"] = DDM_PKL

    runner = ParallelSimulationRunner(config=base_cfg, max_workers=workers)
    t0 = time.time()
    runner.open_pool()
    dt = time.time() - t0
    timings.append(("open worker pool", dt))
    print(f"[pool]  opened {workers} workers | {dt:.1f}s")

    def eval_point(routes, num_ticks, rate, n_jeeps, tag):
        overrides = {
            "seconds_per_tick":        SPT,
            "num_ticks":               int(num_ticks),
            "spawn_rate_per_hour":     float(rate),
            "total_allocatable_jeeps": int(n_jeeps),
        }
        t = time.time()
        results = run_reps_overrides(runner, routes, REPLICATIONS, overrides)
        wall = time.time() - t

        scores, comps = [], []
        for r in results:
            if r is None:
                continue
            scores.append(r.score)
            c = r.metrics.get("completed_count", 0)
            inc = r.metrics.get("incomplete_count", 0)
            tot = c + inc
            comps.append(c / tot if tot > 0 else np.nan)

        rec = {
            "tag": tag, "ticks": int(num_ticks), "rate": float(rate),
            "n_ok": len(scores), "cv": compute_cv(scores),
            "completion": float(np.nanmean(comps)) if comps else float("nan"),
            "wall": wall,
        }
        eval_log.append(rec)
        print(f"  {tag:13s} ticks={num_ticks:4d} rate={rate:6.0f}/hr | "
              f"n_ok={len(scores)}/{REPLICATIONS} "
              f"completion={rec['completion'] * 100:5.1f}% CV={rec['cv']:.4f} | {wall:.1f}s")
        return rec

    try:
        for n_routes in ROUTE_COUNTS:
            random.seed(42 + n_routes)
            np.random.seed(42 + n_routes)

            t0 = time.time()
            routes = generate_route_system(n_routes, G_city, ddm)
            dt = time.time() - t0
            timings.append((f"route gen (R={n_routes})", dt))
            n_jeeps = n_routes * JEEPS_PER_ROUTE
            print(f"[routes] R={n_routes} | {dt:.1f}s")

            # horizon sweep (first eval also builds + caches the TravelGraph per worker)
            for i, T in enumerate(HORIZON_TICKS):
                eval_point(routes, T, HORIZON_DENSITY * n_routes, n_jeeps,
                           "horizon(1st)" if i == 0 else "horizon")
            # volume sweep
            for d in PAX_PER_ROUTE_HR:
                eval_point(routes, VOLUME_TICKS, d * n_routes, n_jeeps, "volume")
    finally:
        t0 = time.time()
        runner.close_pool()
        timings.append(("close pool", time.time() - t0))

    # ── functional checks (anomaly detection) ──
    print("\n" + "-" * 66)
    print("FUNCTIONAL CHECKS")
    print("-" * 66)
    problems = []
    for rec in eval_log:
        if rec["n_ok"] != REPLICATIONS:
            problems.append(f"{rec['tag']} ticks={rec['ticks']}: only {rec['n_ok']}/{REPLICATIONS} reps returned (worker crash?)")
        comp = rec["completion"]
        if not (comp == comp and 0.0 <= comp <= 1.0):  # comp==comp rejects NaN
            problems.append(f"{rec['tag']} ticks={rec['ticks']}: completion out of [0,1] ({comp})")
        if not (rec["cv"] == rec["cv"] and rec["cv"] >= 0):
            problems.append(f"{rec['tag']} ticks={rec['ticks']}: CV not finite/non-negative ({rec['cv']})")

    # caching check: the first eval (TravelGraph build) should be slower than later cached evals
    first = next((r for r in eval_log if r["tag"] == "horizon(1st)"), None)
    later = [r for r in eval_log if r["tag"] in ("horizon", "volume")]
    if first and later:
        avg_later = float(np.mean([r["wall"] for r in later]))
        if first["wall"] <= avg_later:
            problems.append(
                f"CACHING: first eval ({first['wall']:.1f}s) is NOT slower than later avg "
                f"({avg_later:.1f}s) — TravelGraph cache may not be engaging (expect rebuild every eval)")
        else:
            print(f"[OK] TravelGraph cache engaging: first eval {first['wall']:.1f}s "
                  f"vs later avg {avg_later:.1f}s")

    for p in problems:
        print(f"[!!] {p}")
    print(f"\n{'ALL CHECKS PASSED' if not problems else f'{len(problems)} ISSUE(S) — investigate before handing off'}")

    # ── runtime report (THIS machine only) ──
    print("\n" + "=" * 66)
    print(f"RUNTIME ON THIS MACHINE ({n_cores} cores, {workers} workers)")
    print("=" * 66)
    for phase, sec in timings:
        print(f"  {phase:28s} {sec:7.1f}s")
    eval_total = sum(r["wall"] for r in eval_log)
    print(f"  {'eval waves (' + str(len(eval_log)) + ' evals)':28s} {eval_total:7.1f}s")
    print(f"  {'-' * 28} {'-' * 7}")
    grand = sum(s for _, s in timings) + eval_total
    print(f"  {'TOTAL':28s} {grand:7.1f}s  ({grand / 60:.1f} min)")

    print("\nPer-eval wall times on this machine:")
    for r in eval_log:
        print(f"    {r['tag']:13s} ticks={r['ticks']:4d} rate={r['rate']:6.0f}/hr -> {r['wall']:5.1f}s")

    os.makedirs("rnd/csv", exist_ok=True)
    if eval_log:
        with open("rnd/csv/rnd1_tiny_timings.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(eval_log[0].keys()))
            w.writeheader()
            for r in eval_log:
                w.writerow(r)
        print("\nSaved per-eval timings -> rnd/csv/rnd1_tiny_timings.csv")


if __name__ == "__main__":
    main()
