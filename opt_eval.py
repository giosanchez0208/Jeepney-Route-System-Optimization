"""
opt_eval.py — evaluate the findings of all final optimizations (Chapter 4.4-4.5).

Run AFTER the opt_pN.py runs have produced outputs under outputs/final_runs/<tag>/opt_<ts>/.

    python opt_eval.py

It is robust to partial completion: it uses whatever runs exist and skips the rest.

Two parts:
  PART 1 (no simulation): convergence curves (4.4.1) and cross-run / temporal robustness
          similarity matrices (4.5.2 / 4.5.3) from the saved snapshots + history.csv.
  PART 2 (re-simulates each final network, heavier): stochastic baseline (4.5.1), the equity
          travel-time distribution (4.5.4), and path-diversity Shannon entropy (4.5.5).

Figures -> results_and_discussion/images/ ; a stats summary is printed.
"""
from __future__ import annotations

import os
import sys
import json
import copy
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
import yaml
import matplotlib.pyplot as plt

from utils.evaluation_metrics import jaccard_similarity, wasserstein_2d, shannon_entropy, graph_edit_distance

FINAL_ROOT = Path("outputs/final_runs")
IMG_DIR = Path("results_and_discussion/images")
IMG_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 11, "savefig.dpi": 200})

REPRO_TAGS = [f"p{n}" for n in range(1, 8)]          # reproducibility set (8am, seeds 1-7)
TEMPORAL = {"p1": "8am", "p8_1pm": "1pm", "p9_5pm": "5pm"}


# ----------------------------------------------------------------------------- discovery / loading
def discover_runs() -> dict[str, Path]:
    """tag -> latest opt_<ts> dir for that tag."""
    runs = {}
    if not FINAL_ROOT.exists():
        return runs
    for tag_dir in sorted(FINAL_ROOT.glob("*")):
        if not tag_dir.is_dir():
            continue
        opt_dirs = sorted(tag_dir.glob("opt_*"))
        if opt_dirs:
            runs[tag_dir.name] = opt_dirs[-1]
    return runs


def load_final_routes(run_dir: Path):
    """Best chromosome's routes (list of routes, each a list of {lat,lon}) from the last snapshot."""
    snaps = sorted((run_dir / "snapshots").glob("network_state_gen_*.json"),
                   key=lambda p: int(p.stem.split("_")[-1]))
    if not snaps:
        return None
    with open(snaps[-1]) as f:
        return json.load(f)["layers"]["routes"]


def _ek(a, b):
    a = (round(a["lon"], 6), round(a["lat"], 6))
    b = (round(b["lon"], 6), round(b["lat"], 6))
    return tuple(sorted([a, b]))   # undirected "shared street"


def network_edges(routes):
    return {_ek(r[i], r[i + 1]) for r in routes for i in range(len(r) - 1)}


def network_nodes(routes):
    return [(p["lon"], p["lat"]) for r in routes for p in r]


# ----------------------------------------------------------------------------- PART 1: convergence
def plot_convergence(runs: dict[str, Path]):
    fig, ax = plt.subplots(figsize=(8, 5))
    plotted = 0
    for tag, run_dir in runs.items():
        h = run_dir / "history.csv"
        if not h.exists():
            continue
        df = pd.read_csv(h)
        if "Generation" not in df or "Global_Best_Cost" not in df:
            continue
        ax.plot(df["Generation"], df["Global_Best_Cost"], alpha=0.7, label=tag)
        plotted += 1
    if not plotted:
        print("[4.4.1] no history.csv found yet; skipping convergence plot.")
        plt.close(fig)
        return
    ax.set_xlabel("Generation"); ax.set_ylabel("Global best fitness $F_{sim}$ (lower better)")
    ax.set_title("Convergence across final runs", fontweight="bold")
    ax.legend(fontsize=8, ncol=2); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(IMG_DIR / "convergence_curves.png", bbox_inches="tight"); plt.close(fig)
    print(f"[4.4.1] convergence_curves.png  ({plotted} runs)")


# ----------------------------------------------------------------------------- PART 1: robustness
def similarity_matrix(networks: dict[str, dict], label: str, fname: str):
    """networks: tag -> {'edges': set, 'nodes': list}. Plots Jaccard heatmap, returns mean off-diagonal."""
    tags = list(networks)
    n = len(tags)
    if n < 2:
        print(f"[{label}] need >=2 networks, have {n}; skipping.")
        return None
    J = np.zeros((n, n)); W = np.zeros((n, n))
    for i, ti in enumerate(tags):
        for j, tj in enumerate(tags):
            J[i, j] = jaccard_similarity(networks[ti]["edges"], networks[tj]["edges"])
            ni, nj = networks[ti]["nodes"], networks[tj]["nodes"]
            try:
                W[i, j] = wasserstein_2d(ni, [1.0] * len(ni), nj, [1.0] * len(nj))
            except Exception:
                W[i, j] = np.nan

    off = J[~np.eye(n, dtype=bool)]
    mean_j = float(off.mean())

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    for ax, M, title in [(axes[0], J, "Jaccard (shared streets)"), (axes[1], W, "2D Wasserstein (coverage)")]:
        im = ax.imshow(M, cmap="viridis" if M is J else "magma_r")
        ax.set_xticks(range(n)); ax.set_xticklabels(tags, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(n)); ax.set_yticklabels(tags, fontsize=8)
        ax.set_title(title, fontsize=11)
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle(f"{label} (mean pairwise Jaccard = {mean_j:.3f})", fontweight="bold")
    plt.tight_layout(); plt.savefig(IMG_DIR / fname, bbox_inches="tight"); plt.close(fig)
    print(f"[{label}] {fname} | mean pairwise Jaccard = {mean_j:.3f}")
    return mean_j


# ----------------------------------------------------------------------------- PART 2: re-simulation
def _load_env():
    from utils_simplified import reuse_citygraph, reuse_ddm
    city = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    config = yaml.safe_load(open("configs/profile_p1.yaml", encoding="utf-8"))
    return city, ddm, config


def _resim(city, ddm, config, routes, fleet=None):
    """Rebuild Route objects from snapshot coords and run one sim; returns the SimulationResult."""
    from utils.route import route_from_coords
    from utils.travel_graph import TravelGraph
    from utils.jeep import Jeep
    from utils.jeep_system import JeepSystem
    from utils.passenger_generator import PassengerGenerator
    from utils.simulation import Simulation

    route_objs = [route_from_coords(city, json.dumps([[p["lon"], p["lat"]] for p in r]))
                  for r in routes if len(r) >= 2]
    SIM = config["simulation"]
    spt = int(SIM.get("seconds_per_tick", 10))
    total = int(fleet if fleet is not None else SIM.get("total_allocatable_jeeps", 2000))
    jpr = max(1, total // len(route_objs))
    tg = TravelGraph(city, config=config.get("travel_graph", {}), routes=route_objs)
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                  speed=float(SIM.get("jeep_speed_kmh", 20.0)), max_capacity=int(SIM.get("jeep_capacity", 16)),
                  seconds_per_tick=spt)
             for r in route_objs for _ in range(jpr)]
    js = JeepSystem(jeeps=jeeps, routes=route_objs, weight_tolerance=float(SIM.get("weight_tolerance", 14.4)), equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=ddm, rate_per_hour=float(SIM.get("spawn_rate_per_hour", 600.0)),
                            stdev=float(SIM.get("spawn_stdev", 10.0)), speed=float(SIM.get("passenger_speed_kmh", 4.5)),
                            seconds_per_tick=spt)
    cfg = copy.deepcopy(config); cfg["disable_tqdm"] = True
    sim = Simulation(city_query="Iligan", bounds=city.get_bounds(), jeep_system=js, passenger_generator=pg,
                     max_ticks=int(SIM.get("num_ticks", 540)), beta_penalty=2.0, alpha_std_penalty=0.5, config=cfg)
    result = sim.run()
    times = [(p.despawn_tick - p.spawn_tick) / 60.0
             for p in sim.passenger_generator.archived_passengers if p.despawn_tick is not None]
    return result, times


def resim_evaluation(runs: dict[str, Path], baseline_k: int = 7):
    """Stochastic baseline (4.5.1), equity travel-time distribution (4.5.4), path entropy (4.5.5)."""
    opt_tags = [t for t in REPRO_TAGS if t in runs]
    if not opt_tags:
        print("[PART 2] no reproducibility runs found; skipping re-simulation.")
        return
    print(f"[PART 2] re-simulating {len(opt_tags)} optimized networks + {baseline_k} random baselines "
          f"(heavy: each is a full 2000-jeep / 38-route sim)...")
    import random
    from utils_simplified import generate_route_system
    city, ddm, config = _load_env()

    opt_fitness, opt_times_all, opt_entropy = [], [], []
    for tag in opt_tags:
        routes = load_final_routes(runs[tag])
        if not routes:
            continue
        res, times = _resim(city, ddm, config, routes)
        opt_fitness.append(res.score)
        opt_times_all.extend(times)
        # path-diversity entropy: frequency of each traversed edge across recorded journeys
        freq = {}
        for journey, _cost in getattr(res, "recorded_paths", []):
            for e in journey:
                key = getattr(e, "id", id(e))
                freq[key] = freq.get(key, 0) + 1
        opt_entropy.append(shannon_entropy(list(freq.values())) if freq else np.nan)
        print(f"  [{tag}] fitness={res.score:.0f} completed={len(times)} entropy={opt_entropy[-1]:.2f}")

    base_fitness, base_times_all = [], []
    for k in range(baseline_k):
        random.seed(9000 + k); np.random.seed(9000 + k)
        rk = generate_route_system(int(config["simulation"]["num_routes"]), city, ddm)
        coords = [[{"lon": e.start.lon, "lat": e.start.lat} for e in r.path] +
                  [{"lon": r.path[-1].end.lon, "lat": r.path[-1].end.lat}] for r in rk]
        res, times = _resim(city, ddm, config, coords)
        base_fitness.append(res.score); base_times_all.extend(times)
        print(f"  [baseline {k}] fitness={res.score:.0f} completed={len(times)}")

    # ---- 4.5.1: baseline vs optimized fitness ----
    if base_fitness and opt_fitness:
        imp = 100.0 * (np.mean(base_fitness) - np.mean(opt_fitness)) / np.mean(base_fitness)
        print(f"[4.5.1] baseline mean F={np.mean(base_fitness):.0f} | optimized mean F={np.mean(opt_fitness):.0f} "
              f"| improvement {imp:.1f}%")
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.boxplot([base_fitness, opt_fitness], labels=["Stochastic baseline", "Optimized"])
        ax.set_ylabel("Simulation fitness $F_{sim}$")
        ax.set_title(f"Optimization gain: {imp:.1f}% lower cost", fontweight="bold")
        ax.grid(axis="y", alpha=0.3); plt.tight_layout()
        plt.savefig(IMG_DIR / "baseline_vs_optimized.png", bbox_inches="tight"); plt.close(fig)

    # ---- 4.5.4: equity travel-time distribution (baseline vs optimized) ----
    if opt_times_all and base_times_all:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(base_times_all, bins=40, alpha=0.5, label=f"Baseline (sd={np.std(base_times_all):.1f})", color="#999999")
        ax.hist(opt_times_all, bins=40, alpha=0.6, label=f"Optimized (sd={np.std(opt_times_all):.1f})", color="#377eb8")
        ax.set_xlabel("Passenger travel time (min)"); ax.set_ylabel("count")
        ax.set_title("Equity: travel-time distribution (the equity regularizer shortens the long tail)", fontweight="bold")
        ax.legend(); ax.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(IMG_DIR / "equity_traveltime_hist.png", bbox_inches="tight"); plt.close(fig)
        print(f"[4.5.4] travel-time sd: baseline {np.std(base_times_all):.2f} -> optimized {np.std(opt_times_all):.2f} min")

    # ---- 4.5.5: path-diversity entropy ----
    if any(np.isfinite(opt_entropy)):
        print(f"[4.5.5] path-diversity Shannon entropy (optimized): mean {np.nanmean(opt_entropy):.2f} bits")


# ----------------------------------------------------------------------------- main
def main():
    runs = discover_runs()
    print(f"Discovered {len(runs)} run(s): {list(runs)}")
    if not runs:
        print("No runs under outputs/final_runs/ yet. Launch opt_pN.py first.")
        return

    plot_convergence(runs)

    # Load final networks once.
    nets = {}
    for tag, run_dir in runs.items():
        routes = load_final_routes(run_dir)
        if routes:
            nets[tag] = {"edges": network_edges(routes), "nodes": network_nodes(routes)}

    repro = {t: nets[t] for t in REPRO_TAGS if t in nets}
    similarity_matrix(repro, "4.5.2 Cross-run robustness (reproducibility)", "robustness_reproducibility.png")

    temporal = {t: nets[t] for t in TEMPORAL if t in nets}
    similarity_matrix(temporal, "4.5.3 Demand-regime robustness (temporal DDM)", "robustness_temporal.png")

    # PART 2 (heavy). Comment out if you only want the no-sim robustness/convergence.
    resim_evaluation(runs)

    print("\nDone. Figures in", IMG_DIR)


if __name__ == "__main__":
    main()
