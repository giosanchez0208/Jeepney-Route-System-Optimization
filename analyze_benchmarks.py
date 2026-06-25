"""analyze_benchmarks.py -- Ask #3: standardized benchmark metrics, baseline vs optimized.

For the 8am reproducibility set (p1-p7) under final_runs_2, this computes, for both the optimized
network (best_sim_result.pkl) and its stochastic baseline (initial_best_sim_result.pkl), the
standardized metrics the panel asked us to report against the baseline:

  - average commute time of completed passengers          (from the saved metrics)
  - transfer rate: mean transfers per trip and the share of trips with >= 1 transfer
                                                          (count of 'transfer' edges in each journey)
  - stop accessibility: share of demand (DDM-weighted) within an 864 m access radius of a stop
  - route coverage: share of drivable road-network nodes traversed by the route system

Journeys are stored in SimulationResult.recorded_paths as (edge_list, cost) tuples, where each
DirEdge is typed (start_walk / wait / ride / alight / transfer / end_walk). The union of a result's
ride edges reconstructs the served network; wait/alight/transfer endpoints are the stops.

    python analyze_benchmarks.py

Writes outputs/benchmarks/benchmark_table.csv and outputs/benchmarks/benchmark_comparison.png.
"""
import math
import os
import pickle
from pathlib import Path

import numpy as np

FINAL_ROOT = Path("final_runs_2/final results_")
EIGHT_AM = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"]
ACCESS_RADIUS_M = 864.0  # paper's 85th-percentile behavioral walk-access radius (Sec 3.1)
STOP_TYPES = {"wait", "alight", "transfer"}
OUT = Path("outputs/benchmarks")


def run_dir_for(tag: str) -> Path | None:
    base = FINAL_ROOT / tag
    if not base.exists():
        return None
    subs = sorted(base.glob("opt_*"))
    return subs[-1] if subs else None


def _ll(node):
    """(lon, lat) from a node object or coord tuple."""
    if node is None:
        return None
    if hasattr(node, "lon") and hasattr(node, "lat"):
        return (float(node.lon), float(node.lat))
    if isinstance(node, (tuple, list)) and len(node) >= 2:
        return (float(node[0]), float(node[1]))
    return None


def journeys(result):
    for elem in result.recorded_paths:
        edges = elem[0] if isinstance(elem, tuple) else elem
        if edges:
            yield edges


def transfer_stats(result):
    per_trip = []
    for edges in journeys(result):
        per_trip.append(sum(1 for e in edges if getattr(e, "type", "") == "transfer"))
    per_trip = np.array(per_trip, dtype=float) if per_trip else np.array([0.0])
    return float(per_trip.mean()), 100.0 * float((per_trip >= 1).mean())


def served_sets(result):
    """Return (set of served network nodes from ride edges, set of stop nodes)."""
    served, stops = set(), set()
    for edges in journeys(result):
        for e in edges:
            t = getattr(e, "type", "")
            s, d = _ll(getattr(e, "start", None)), _ll(getattr(e, "end", None))
            if t == "ride":
                if s:
                    served.add(s)
                if d:
                    served.add(d)
            if t in STOP_TYPES:
                if s:
                    stops.add(s)
                if d:
                    stops.add(d)
    return served, stops


def _to_m(lon, lat, lat0):
    return (lon * 111320.0 * math.cos(math.radians(lat0)), lat * 110540.0)


def accessibility(stops, demand_xyw, lat0):
    """Demand-weighted share within ACCESS_RADIUS_M of any stop."""
    if not stops or not demand_xyw:
        return float("nan")
    try:
        from scipy.spatial import cKDTree
    except Exception:
        return float("nan")
    sp = np.array([_to_m(lon, lat, lat0) for (lon, lat) in stops])
    tree = cKDTree(sp)
    dx = np.array([_to_m(lon, lat, lat0) for (lon, lat, _) in demand_xyw])
    w = np.array([wt for (_, _, wt) in demand_xyw], dtype=float)
    d, _ = tree.query(dx, k=1)
    covered = w[d <= ACCESS_RADIUS_M].sum()
    return 100.0 * covered / w.sum() if w.sum() else float("nan")


def load_demand(ddm):
    """List of (lon, lat, weight) demand points from the DDM sampler."""
    probs = getattr(ddm, "node_probabilities", None) or getattr(ddm, "probabilities", None)
    out = []
    if isinstance(probs, dict):
        for k, v in probs.items():
            ll = _ll(k)
            if ll:
                out.append((ll[0], ll[1], float(v)))
    return out


def city_node_count(city):
    nodes = set()
    graph = getattr(city, "graph", None) or []
    for e in graph:
        s, d = _ll(getattr(e, "start", None)), _ll(getattr(e, "end", None))
        if getattr(e, "is_drivable", True):
            if s:
                nodes.add(s)
            if d:
                nodes.add(d)
    return nodes


def main():
    print("[bench] loading city graph + 8am DDM ...")
    from utils_simplified import reuse_citygraph, reuse_ddm
    city = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    demand = load_demand(ddm)
    city_nodes = city_node_count(city)
    lat0 = np.mean([lat for (_, lat, _) in demand]) if demand else 8.24
    print(f"[bench] demand points={len(demand)}  drivable nodes={len(city_nodes)}")

    rows = []  # (tag, kind, commute, tr_mean, tr_pct, access, coverage)
    for tag in EIGHT_AM:
        rd = run_dir_for(tag)
        if not rd:
            print(f"[bench] {tag}: no run dir, skipping")
            continue
        for kind, fname in (("baseline", "initial_best_sim_result.pkl"),
                            ("optimized", "best_sim_result.pkl")):
            fp = rd / fname
            if not fp.exists():
                print(f"[bench] {tag}/{kind}: missing {fname}")
                continue
            try:
                res = pickle.load(open(fp, "rb"))
            except Exception as e:
                print(f"[bench] {tag}/{kind}: unreadable pkl ({type(e).__name__}), skipping")
                continue
            m = res.metrics
            commute = m.get("mean_commute_time", float("nan")) / 60.0
            done = int(m.get("completed_count", 0))
            undone = int(m.get("incomplete_count", 0))
            completion = 100.0 * done / (done + undone) if (done + undone) else float("nan")
            tr_mean, tr_pct = transfer_stats(res)
            served, stops = served_sets(res)
            access = accessibility(stops, demand, lat0)
            coverage = 100.0 * len(served & city_nodes) / len(city_nodes) if city_nodes else float("nan")
            rows.append((tag, kind, commute, tr_mean, tr_pct, access, coverage, completion))
            print(f"  {tag} {kind:9s}: completion={completion:5.1f}%  commute={commute:6.1f}min  "
                  f"tr/trip={tr_mean:.2f}  tr%={tr_pct:4.1f}  access={access:5.1f}%  coverage={coverage:5.1f}%")

    write_outputs(rows)


def write_outputs(rows):
    import csv
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "benchmark_table.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["profile", "kind", "avg_commute_min", "transfers_per_trip",
                    "pct_trips_with_transfer", "stop_accessibility_pct", "route_coverage_pct",
                    "completion_pct"])
        w.writerows(rows)

    metrics = ["avg_commute_min", "transfers_per_trip", "pct_trips_with_transfer",
               "stop_accessibility_pct", "route_coverage_pct", "completion_pct"]
    agg = {}
    for kind in ("baseline", "optimized"):
        vals = [r for r in rows if r[1] == kind]
        if not vals:
            continue
        arr = np.array([[v[2], v[3], v[4], v[5], v[6], v[7]] for v in vals], dtype=float)
        agg[kind] = (np.nanmean(arr, axis=0), np.nanstd(arr, axis=0))

    print("\n[bench] === baseline vs optimized (mean +/- sd over p1-p7) ===")
    for i, m in enumerate(metrics):
        line = f"  {m:26s}"
        for kind in ("baseline", "optimized"):
            if kind in agg:
                line += f"  {kind}={agg[kind][0][i]:7.2f}+/-{agg[kind][1][i]:.2f}"
        if "baseline" in agg and "optimized" in agg and agg["baseline"][0][i]:
            delta = 100.0 * (agg["optimized"][0][i] - agg["baseline"][0][i]) / agg["baseline"][0][i]
            line += f"   ({delta:+.1f}%)"
        print(line)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        labels = ["Avg commute\n(min)", "Transfers\nper trip", "% trips w/\ntransfer",
                  "Stop access\n(%)", "Route cov\n(%)", "Completion\n(%)"]
        x = np.arange(len(labels))
        fig, ax = plt.subplots(figsize=(9, 4.8))
        for off, kind, col in ((-0.2, "baseline", "#C9821B"), (0.2, "optimized", "#2F8F57")):
            if kind in agg:
                ax.bar(x + off, agg[kind][0], width=0.38, label=kind.capitalize(), color=col,
                       yerr=agg[kind][1], capsize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9)
        ax.set_title("Standardized benchmark metrics: stochastic baseline vs optimized (8am set, p1-p7)")
        ax.legend(frameon=False)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT / "benchmark_comparison.png", dpi=160, bbox_inches="tight")
        plt.close(fig)
        print(f"[bench] wrote {OUT/'benchmark_comparison.png'} and {OUT/'benchmark_table.csv'}")
    except Exception as e:
        print("[bench] plot failed:", e)


if __name__ == "__main__":
    main()
