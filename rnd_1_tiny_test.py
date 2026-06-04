"""
rnd_1_tiny_test.py — TINY smoke test + timing probe for rnd_1_ticks_and_rate.ipynb

WHY THIS EXISTS
  Run this on a small/slow box (4-core, no-GPU) BEFORE handing the full notebook to
  thesismates. It (1) confirms the machinery runs end-to-end with no anomaly, and
  (2) prints the wall-clock runtime of each part ON THIS MACHINE.

MODEL: CONTINUOUS ARRIVALS + FIXED HORIZON (abrupt stop at num_ticks)
  This matches production: the simulation is cut off after a fixed number of ticks,
  and passengers still in-flight at the cutoff are scored by the underservice penalty.
  Completion fraction is therefore a DIAGNOSTIC, not a target — at short horizons it
  is expected to be low. The health checks below are: workers don't crash, the
  TravelGraph cache engages (first eval slower than later ones), and CV is finite.

  Driven via per-call overrides through ONE persistent pool, so there is no ~90s
  worker reload and no TravelGraph rebuild per evaluation.

RUN
  python rnd_1_tiny_test.py     (use the venv interpreter: .venv\\Scripts\\python.exe)
"""
import os
import sys
import time
import random
import csv
import numpy as np

sys.path.insert(0, os.getcwd())

# ── TINY CONFIG (intentionally small) ────────────────────────────────────────
ROUTES            = 5
HORIZON_TICKS     = [60, 120, 180]   # 10 / 20 / 30 simulated minutes at SPT=10
HORIZON_DENSITY   = 50               # pax/route/hr held fixed during the horizon sweep
PAX_PER_ROUTE_HR  = [50, 150]        # densities for the volume sweep
VOLUME_TICKS      = 120              # horizon held fixed during the volume sweep
REPLICATIONS      = 3                # CV needs >= 2
JEEPS_PER_ROUTE   = 10
SPT               = 10

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

    timings, eval_log = [], []
    n_cores = os.cpu_count() or 1
    workers = min(REPLICATIONS, max(1, n_cores - 1))

    print("=" * 66)
    print("TINY TEST — rnd_1_ticks_and_rate  (continuous arrivals + fixed horizon)")
    print(f"This machine: {n_cores} cores -> {workers} workers | {REPLICATIONS} reps/eval")
    print("=" * 66)

    t0 = time.time()
    G_city = reuse_citygraph(CG_PKL)
    ddm = reuse_ddm(DDM_PKL)
    timings.append(("load CityGraph+DDM", time.time() - t0))
    print(f"[load]  {len(G_city.nodes)} nodes, {len(G_city.graph)} edges | {timings[-1][1]:.1f}s")

    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        base_cfg = yaml.safe_load(f)
    base_cfg["cg_pkl"] = CG_PKL
    base_cfg["ddm_pkl"] = DDM_PKL

    runner = ParallelSimulationRunner(config=base_cfg, max_workers=workers)
    t0 = time.time()
    runner.open_pool()
    timings.append(("open worker pool", time.time() - t0))
    print(f"[pool]  opened {workers} workers | {timings[-1][1]:.1f}s")

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
        random.seed(42 + ROUTES)
        np.random.seed(42 + ROUTES)
        t0 = time.time()
        routes = generate_route_system(ROUTES, G_city, ddm)
        timings.append((f"route gen (R={ROUTES})", time.time() - t0))
        n_jeeps = ROUTES * JEEPS_PER_ROUTE
        print(f"[routes] R={ROUTES} | {timings[-1][1]:.1f}s")

        # horizon sweep (first eval also builds + caches the TravelGraph per worker)
        for i, T in enumerate(HORIZON_TICKS):
            eval_point(routes, T, HORIZON_DENSITY * ROUTES, n_jeeps,
                       "horizon(1st)" if i == 0 else "horizon")
        # volume sweep
        for d in PAX_PER_ROUTE_HR:
            eval_point(routes, VOLUME_TICKS, d * ROUTES, n_jeeps, "volume")
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
    # NOTE: completion magnitude is NOT gated — under continuous+fixed it is expected
    # to be low at short horizons. The cache check below is the real machinery gate.

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
