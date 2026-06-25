"""analyze_benchmarks_vs_random.py -- Ask #3, the paper-consistent benchmark.

The headline 8% TUC claim is optimized vs the STOCHASTIC BASELINE MEAN (randomly generated
route systems), not vs the best random seed. This script reproduces that baseline: it generates
K random route systems, simulates them under the same 8am Iligan conditions the final runs used
(38 routes, 2000 jeeps, 540 ticks, jeep_speed 20 km/h), and computes the standardized metrics on
them, then compares against the optimized networks (best_sim_result.pkl, p1-p7).

Metrics (baseline-random vs optimized), all from the simulated SimulationResults:
  - F_sim (Total User Cost)            - average commute time of completed passengers
  - completion rate                    - transfers per trip / % trips with a transfer
  - stop accessibility (864 m)         - route coverage (% drivable nodes served)

    python analyze_benchmarks_vs_random.py --k 7

Writes outputs/benchmarks/benchmark_vs_random_table.csv and benchmark_vs_random.png.
This re-simulates K full Iligan networks in parallel; expect several minutes.
"""
import argparse
import csv
import pickle
from pathlib import Path

import numpy as np
import yaml

from analyze_benchmarks import (transfer_stats, served_sets, accessibility, load_demand,
                                city_node_count, run_dir_for, EIGHT_AM, OUT)

MATCH_JEEP_SPEED = 20.0  # final_runs_2 were executed at 20 km/h (see profile_p1 note)


def metrics_for(res, demand, lat0, city_nodes):
    m = res.metrics
    commute = m.get("mean_commute_time", float("nan")) / 60.0
    done, undone = int(m.get("completed_count", 0)), int(m.get("incomplete_count", 0))
    completion = 100.0 * done / (done + undone) if (done + undone) else float("nan")
    tr_mean, tr_pct = transfer_stats(res)
    served, stops = served_sets(res)
    access = accessibility(stops, demand, lat0)
    coverage = 100.0 * len(served & city_nodes) / len(city_nodes) if city_nodes else float("nan")
    return [float(getattr(res, "fitness_score", float("nan"))), completion, commute,
            tr_mean, tr_pct, access, coverage]


COLS = ["F_sim", "completion_pct", "avg_commute_min", "transfers_per_trip",
        "pct_trips_with_transfer", "stop_accessibility_pct", "route_coverage_pct"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=7, help="number of random stochastic baselines")
    args = ap.parse_args()

    print("[bench-vs-random] loading city + 8am DDM + config ...")
    from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
    city = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    config = yaml.safe_load(open("configs/profile_p1.yaml", encoding="utf-8"))
    config.setdefault("simulation", {})["jeep_speed_kmh"] = MATCH_JEEP_SPEED  # match the runs
    demand = load_demand(ddm)
    city_nodes = city_node_count(city)
    lat0 = float(np.mean([lat for (_, lat, _) in demand])) if demand else 8.24
    nrt = int(config["simulation"].get("num_routes", 38))

    # --- stochastic baselines: generate K random systems and simulate them in parallel ---
    print(f"[bench-vs-random] generating + simulating {args.k} random baselines ({nrt} routes each) ...")
    systems = []
    for k in range(args.k):
        np.random.seed(9000 + k)
        import random
        random.seed(9000 + k)
        systems.append(generate_route_system(nrt, city, ddm))

    from utils.simulation_parallel import ParallelSimulationRunner
    runner = ParallelSimulationRunner(config=config,
                                      max_workers=config.get("optimization", {}).get("n_workers"))
    runner.open_pool()
    try:
        base_results = runner.run_parallel(systems)
    finally:
        runner.close_pool()

    base_rows = [metrics_for(r, demand, lat0, city_nodes) for r in base_results]

    # --- optimized networks: reuse the saved best results (already simulated) ---
    opt_rows = []
    for tag in EIGHT_AM:
        rd = run_dir_for(tag)
        fp = rd / "best_sim_result.pkl" if rd else None
        if not fp or not fp.exists():
            continue
        try:
            res = pickle.load(open(fp, "rb"))
        except Exception:
            continue
        opt_rows.append(metrics_for(res, demand, lat0, city_nodes))

    report(np.array(base_rows, dtype=float), np.array(opt_rows, dtype=float))


def report(base, opt):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "benchmark_vs_random_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind"] + COLS)
        for kind, arr in (("baseline_random", base), ("optimized", opt)):
            for row in arr:
                w.writerow([kind] + [f"{v:.4f}" for v in row])

    print("\n[bench-vs-random] === stochastic baseline (random mean) vs optimized ===")
    for i, c in enumerate(COLS):
        bm, bs = np.nanmean(base[:, i]), np.nanstd(base[:, i])
        om, os_ = np.nanmean(opt[:, i]), np.nanstd(opt[:, i])
        delta = 100.0 * (om - bm) / bm if bm else float("nan")
        print(f"  {c:26s} baseline={bm:11.2f}+/-{bs:8.2f}   optimized={om:11.2f}+/-{os_:8.2f}   ({delta:+.1f}%)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        labels = ["Completion\n(%)", "Avg commute\n(min)", "Transfers\nper trip",
                  "% trips w/\ntransfer", "Stop access\n(%)", "Route cov\n(%)"]
        idx = [1, 2, 3, 4, 5, 6]  # skip F_sim (different scale; reported in text)
        x = np.arange(len(idx))
        fig, ax = plt.subplots(figsize=(10, 4.8))
        for off, arr, kind, col in ((-0.2, base, "Stochastic baseline", "#C9821B"),
                                    (0.2, opt, "Optimized", "#2F8F57")):
            ax.bar(x + off, [np.nanmean(arr[:, j]) for j in idx], width=0.38, label=kind, color=col,
                   yerr=[np.nanstd(arr[:, j]) for j in idx], capsize=3)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
        fb, fo = np.nanmean(base[:, 0]), np.nanmean(opt[:, 0])
        ax.set_title(f"Optimized vs stochastic baseline (8am).  F_sim: {fb:.0f} -> {fo:.0f} "
                     f"({100*(fo-fb)/fb:+.1f}%)")
        ax.legend(frameon=False); ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT / "benchmark_vs_random.png", dpi=160, bbox_inches="tight")
        plt.close(fig)
        print(f"[bench-vs-random] wrote {OUT/'benchmark_vs_random.png'} and benchmark_vs_random_table.csv")
    except Exception as e:
        print("[bench-vs-random] plot failed:", e)


if __name__ == "__main__":
    main()
