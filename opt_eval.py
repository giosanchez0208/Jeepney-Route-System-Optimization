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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from utils.evaluation_metrics import jaccard_similarity, wasserstein_2d, shannon_entropy, graph_edit_distance

FINAL_ROOT = next((Path(p) for p in ("final_runs", "outputs/final_runs")
                   if Path(p).exists() and any(Path(p).glob("p*"))), Path("final_runs"))
IMG_DIR = Path("results_and_discussion/images")
IMG_DIR.mkdir(parents=True, exist_ok=True)

# Publication style matching fig_environment.py / fig_memetic.py
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titlepad": 12,
    "figure.titlesize": 16,
    "figure.titleweight": "bold",
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

# Route palette matching fig_memetic.py
ROUTE_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE",
                 "#AA3377", "#BBBBBB", "#EE9944", "#000000", "#9970AB",
                 "#332288", "#88CCEE", "#44AA99", "#999933", "#882255",
                 "#661100", "#6699CC", "#CC6677", "#117733", "#DDCC77"]
BASE_ALPHA = 0.35
BASE_SIZE = 800

# Maximum unique nodes for 2D Wasserstein — the exact LP solver is O(n²m²),
# so 200 nodes keeps each pairwise comparison at ~0.3s while preserving coverage shape.
WASS_MAX_NODES = 200

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


def final_routes_from_checkpoint(run_dir: Path, city, edge_lookup):
    """The final-best chromosome's EXACT Route objects from the last checkpoint (path_keys ->
    edges via coord lookup, O(1) per edge; no shortest-path approximation). Mirrors the optimizer's
    own resume reconstruction."""
    import pickle
    ckpts = sorted((run_dir / "checkpoints").glob("state_gen_*.pkl"),
                   key=lambda p: int(p.stem.split("_")[-1]))
    if not ckpts:
        return None
    with open(ckpts[-1], "rb") as f:
        st = pickle.load(f)
    best = min(st.population, key=lambda c: c.cost)
    routes = []
    for r in best.routes:
        r.cg = city
        r.path = [edge_lookup[k] for k in r.path_keys if k in edge_lookup]
        if r.path:
            routes.append(r)
    return routes


def _ek(a, b):
    a = (round(a["lon"], 6), round(a["lat"], 6))
    b = (round(b["lon"], 6), round(b["lat"], 6))
    return tuple(sorted([a, b]))   # undirected "shared street"


def network_edges(routes):
    return {_ek(r[i], r[i + 1]) for r in routes for i in range(len(r) - 1)}


def network_nodes(routes):
    return [(p["lon"], p["lat"]) for r in routes for p in r]


def _subsample_nodes(pts: list[tuple[float, float]], max_n: int = WASS_MAX_NODES
                     ) -> list[tuple[float, float]]:
    """Deduplicate then deterministically subsample to at most `max_n` unique nodes.

    Keeps the spatial coverage distribution representative while capping the O(n*m)
    Wasserstein cost matrix at a tractable size.
    """
    unique = list(dict.fromkeys(pts))  # preserves first-seen order, dedup
    if len(unique) <= max_n:
        return unique
    step = len(unique) / max_n
    return [unique[int(i * step)] for i in range(max_n)]


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
    """networks: tag -> {'edges': set, 'nodes': list}. Plots Jaccard + Wasserstein heatmaps.

    The 2D Wasserstein computation subsamples node coordinates to WASS_MAX_NODES unique points
    to keep the O(n*m) cost matrix tractable (full 38-route networks have ~100K nodes each).
    """
    tags = list(networks)
    n = len(tags)
    if n < 2:
        print(f"[{label}] need >=2 networks, have {n}; skipping.")
        return None
    J = np.zeros((n, n)); W = np.zeros((n, n))
    for i, ti in enumerate(tags):
        for j, tj in enumerate(tags):
            J[i, j] = jaccard_similarity(networks[ti]["edges"], networks[tj]["edges"])
            ni = _subsample_nodes(networks[ti]["nodes"])
            nj = _subsample_nodes(networks[tj]["nodes"])
            try:
                W[i, j] = wasserstein_2d(ni, [1.0] * len(ni), nj, [1.0] * len(nj))
            except Exception as exc:
                print(f"  [warn] Wasserstein({ti},{tj}) failed: {exc}")
                W[i, j] = np.nan

    off_j = J[~np.eye(n, dtype=bool)]
    mean_j = float(off_j.mean())
    off_w = W[~np.eye(n, dtype=bool)]
    mean_w = float(np.nanmean(off_w)) if np.any(np.isfinite(off_w)) else float("nan")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), constrained_layout=True)
    for ax, M, title, cmap in [
        (axes[0], J, "Jaccard (shared streets)", "viridis"),
        (axes[1], W, "2D Wasserstein (coverage)", "magma_r"),
    ]:
        im = ax.imshow(M, cmap=cmap)
        ax.set_xticks(range(n)); ax.set_xticklabels(tags, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(n)); ax.set_yticklabels(tags, fontsize=8)
        ax.set_title(title, fontsize=11)
        fig.colorbar(im, ax=ax, fraction=0.046)
        # Annotate cells with values
        for ii in range(n):
            for jj in range(n):
                v = M[ii, jj]
                if np.isfinite(v):
                    # Pick text color for contrast
                    txt_color = "w" if (cmap == "viridis" and v < 0.8) or \
                                        (cmap == "magma_r" and v > np.nanmedian(M)) else "k"
                    fmt = f"{v:.3f}" if cmap == "viridis" else f"{v:.4f}"
                    ax.text(jj, ii, fmt, ha="center", va="center",
                            fontsize=7, color=txt_color)
    fig.suptitle(f"{label}\n(mean Jaccard = {mean_j:.3f},  mean Wasserstein = {mean_w:.4f})",
                 fontweight="bold")
    fig.savefig(IMG_DIR / fname)
    plt.close(fig)
    print(f"[{label}] {fname} | mean Jaccard = {mean_j:.3f} | mean Wasserstein = {mean_w:.4f}")
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
    """PART 2 (parallel re-simulation). For the 8am reproducibility set vs random baselines: the
    fitness gain (4.5.1), the passenger COMMUTE-TIME Mann-Whitney comparison (the core
    commute-reduction claim), the equity travel-time distribution (4.5.4), and path entropy (4.5.5)."""
    opt_tags = [t for t in REPRO_TAGS if t in runs]
    if not opt_tags:
        print("[PART 2] no reproducibility runs found; skipping re-simulation.")
        return

    import random
    from scipy.stats import mannwhitneyu
    from utils_simplified import generate_route_system
    from utils.route import route_from_coords
    from utils.simulation_parallel import ParallelSimulationRunner

    city, ddm, config = _load_env()
    nrt = int(config["simulation"]["num_routes"])
    total = config["simulation"].get("total_allocatable_jeeps")
    elook = {((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)): e for e in city.graph}

    # Build every route system to simulate: the exact optimized 8am networks (final-best from each
    # run's last checkpoint) + random baselines.
    labels, systems = [], []
    for tag in opt_tags:
        routes = final_routes_from_checkpoint(runs[tag], city, elook)
        if not routes:
            continue
        labels.append(("opt", tag)); systems.append(routes)
    for k in range(baseline_k):
        random.seed(9000 + k); np.random.seed(9000 + k)
        labels.append(("base", f"baseline_{k}")); systems.append(generate_route_system(nrt, city, ddm))

    n_opt = sum(1 for kind, _ in labels if kind == "opt")
    print(f"[PART 2] re-simulating {len(systems)} networks in parallel "
          f"({n_opt} optimized + {baseline_k} baselines, each a full {nrt}-route / {total}-jeep sim)...")
    runner = ParallelSimulationRunner(config=config,
                                      max_workers=config.get("optimization", {}).get("n_workers"))
    runner.open_pool()
    try:
        results = runner.run_parallel(systems)
    finally:
        runner.close_pool()

    opt_fit, base_fit = [], []
    opt_times_all, base_times_all = [], []
    opt_net_mean, base_net_mean = [], []
    opt_entropy = []
    for (kind, tag), res in zip(labels, results):
        if res is None:
            continue
        times = list(res.metrics.get("commute_times_min", []) or [])
        score = float(res.score)
        if kind == "opt":
            opt_fit.append(score); opt_times_all.extend(times)
            if times:
                opt_net_mean.append(float(np.mean(times)))
            freq = {}
            for journey, _c in (getattr(res, "recorded_paths", []) or []):
                for e in journey:
                    key = getattr(e, "id", id(e)); freq[key] = freq.get(key, 0) + 1
            opt_entropy.append(shannon_entropy(list(freq.values())) if freq else np.nan)
        else:
            base_fit.append(score); base_times_all.extend(times)
            if times:
                base_net_mean.append(float(np.mean(times)))
        mc = np.mean(times) if times else float("nan")
        print(f"  [{tag:11s}] F_sim={score:10.0f}  completed={len(times):4d}  mean_commute={mc:6.2f} min")

    # ===== STATISTICS (printed first so they survive any later plotting error) =====
    imp = float("nan")
    if base_fit and opt_fit:
        imp = 100.0 * (np.mean(base_fit) - np.mean(opt_fit)) / np.mean(base_fit)
        print(f"[4.5.1] fitness: baseline mean F={np.mean(base_fit):.0f} | optimized mean F={np.mean(opt_fit):.0f} | {imp:.1f}% lower")

    mw = None
    if opt_times_all and base_times_all:
        U, p = mannwhitneyu(base_times_all, opt_times_all, alternative="greater")  # H1: baseline > optimized
        mb, mo = float(np.median(base_times_all)), float(np.median(opt_times_all))
        red = 100.0 * (mb - mo) / mb if mb else float("nan")
        if base_net_mean and opt_net_mean:
            Un, pn = mannwhitneyu(base_net_mean, opt_net_mean, alternative="greater")
        else:
            Un, pn = float("nan"), float("nan")
        mw = dict(U=U, p=p, mb=mb, mo=mo, red=red, Un=Un, pn=pn, nb=len(base_times_all), no=len(opt_times_all))
        print("=" * 72)
        print("[COMMUTE-TIME REDUCTION]  (the core thesis claim)")
        print(f"  per-passenger : baseline median {mb:.2f} min -> optimized {mo:.2f} min  ({red:.1f}% lower)")
        print(f"                  Mann-Whitney U={U:.0f}, p={p:.3g}  (N_base={mw['nb']}, N_opt={mw['no']}, one-sided)")
        print(f"  per-network   : baseline mean {np.mean(base_net_mean):.2f} min -> optimized {np.mean(opt_net_mean):.2f} min")
        print(f"                  Mann-Whitney U={Un:.0f}, p={pn:.3g}  (n={len(base_net_mean)} vs {len(opt_net_mean)})")
        print("=" * 72)

    if opt_times_all and base_times_all:
        print(f"[4.5.4] travel-time sd: baseline {np.std(base_times_all):.2f} -> optimized {np.std(opt_times_all):.2f} min")
    if any(np.isfinite(opt_entropy)):
        print(f"[4.5.5] path-diversity Shannon entropy (optimized): mean {np.nanmean(opt_entropy):.2f} bits")

    # ===== FIGURES (each guarded so one failure cannot lose the others) =====
    try:
        if base_fit and opt_fit:
            fig, ax = plt.subplots(figsize=(7, 5))
            ax.boxplot([base_fit, opt_fit], labels=["Stochastic baseline", "Optimized"])
            ax.set_ylabel("Simulation fitness $F_{sim}$")
            ax.set_title(f"Optimization gain: {imp:.1f}% lower total user cost", fontweight="bold")
            ax.grid(axis="y", alpha=0.3); plt.tight_layout()
            plt.savefig(IMG_DIR / "baseline_vs_optimized.png", bbox_inches="tight"); plt.close(fig)
    except Exception as e:
        print("  [warn] baseline_vs_optimized plot failed:", e)

    try:
        if mw is not None:
            fig, ax = plt.subplots(figsize=(7.5, 5.5))
            bp = ax.boxplot([base_times_all, opt_times_all], labels=["Unoptimized\n(baseline)", "Optimized"],
                            showfliers=False, widths=0.6, patch_artist=True)
            for patch, c in zip(bp["boxes"], ["#bbbbbb", "#377eb8"]):
                patch.set_facecolor(c)
            ax.set_ylabel("Passenger commute time (min)")
            ax.set_title(f"Commute time falls {mw['red']:.1f}% (median {mw['mb']:.1f}$\\to${mw['mo']:.1f} min)\n"
                         f"Mann-Whitney $U={mw['U']:.0f}$, $p={mw['p']:.2g}$", fontweight="bold", fontsize=12)
            ax.grid(axis="y", alpha=0.3); plt.tight_layout()
            plt.savefig(IMG_DIR / "commute_time_comparison.png", bbox_inches="tight"); plt.close(fig)
            print("[commute] commute_time_comparison.png")
    except Exception as e:
        print("  [warn] commute_time_comparison plot failed:", e)

    try:
        if opt_times_all and base_times_all:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.hist(base_times_all, bins=40, alpha=0.5, label=f"Baseline (sd={np.std(base_times_all):.1f})", color="#999999")
            ax.hist(opt_times_all, bins=40, alpha=0.6, label=f"Optimized (sd={np.std(opt_times_all):.1f})", color="#377eb8")
            ax.set_xlabel("Passenger travel time (min)"); ax.set_ylabel("count")
            ax.set_title("Equity: travel-time distribution (shorter, tighter tail)", fontweight="bold")
            ax.legend(); ax.grid(alpha=0.3); plt.tight_layout()
            plt.savefig(IMG_DIR / "equity_traveltime_hist.png", bbox_inches="tight"); plt.close(fig)
    except Exception as e:
        print("  [warn] equity_traveltime_hist plot failed:", e)


# ----------------------------------------------------------------------------- PART 1: route system visualization
def _load_snapshot_routes(run_dir: Path, gen: int):
    """Load routes from a specific generation snapshot. Returns list-of-list-of-{lat,lon} or None."""
    snap = run_dir / "snapshots" / f"network_state_gen_{gen}.json"
    if not snap.exists():
        return None
    with open(snap) as f:
        return json.load(f)["layers"]["routes"]


def _snapshot_gens(run_dir: Path) -> list[int]:
    """Return sorted list of available generation numbers in a run's snapshots."""
    snaps = (run_dir / "snapshots").glob("network_state_gen_*.json")
    return sorted(int(p.stem.split("_")[-1]) for p in snaps)


def _get_fitness_at_gen(run_dir: Path, gen: int) -> float | None:
    """Look up the global-best fitness at a specific generation from history.csv."""
    h = run_dir / "history.csv"
    if not h.exists():
        return None
    df = pd.read_csv(h)
    row = df.loc[df["Generation"] == gen]
    if row.empty:
        return None
    return float(row["Global_Best_Cost"].iloc[0])


def _draw_route_system_on_ax(ax, base_img, extent, routes_json, title, *,
                              fitness=None, lw=1.6):
    """Draw a JSON route system (list of list of {lat,lon} dicts) on a matplotlib Axes.

    Follows the fig_memetic.py rendering convention: faint PIL base + coloured LineCollections.
    """
    ax.imshow(base_img, extent=extent, alpha=BASE_ALPHA, zorder=0)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.axis("off")

    for idx, route in enumerate(routes_json):
        color = ROUTE_PALETTE[idx % len(ROUTE_PALETTE)]
        segs = []
        for i in range(len(route) - 1):
            segs.append([(route[i]["lon"], route[i]["lat"]),
                         (route[i + 1]["lon"], route[i + 1]["lat"])])
        if segs:
            ax.add_collection(LineCollection(segs, colors=color, linewidths=lw,
                                             zorder=2, capstyle="round"))

    lbl = title
    if fitness is not None:
        lbl += f"\n$F_{{sim}} = {fitness:,.0f}$"
    ax.set_title(lbl, fontsize=12)


def _get_base_map():
    """Load (or lazily build) the CityGraph PIL base image and extent."""
    from utils_simplified import reuse_citygraph
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    base_img = cg.draw(size=BASE_SIZE, only_drivable=False)
    (tl_lon, tl_lat), (br_lon, br_lat) = cg.get_bounds()
    extent = [tl_lon, br_lon, br_lat, tl_lat]
    return base_img, extent


def plot_initial_vs_final(runs: dict[str, Path], showcase_tags: list[str] | None = None):
    """Render initial (gen 2) vs final route systems for selected runs.

    Creates a figure with two rows per showcased run: the earliest snapshot (random init)
    and the latest snapshot (optimized), with fitness scores annotated.
    """
    if showcase_tags is None:
        # Show p1 (first seed), p4 (mid seed), p7 (last seed) for diversity
        showcase_tags = [t for t in ["p1", "p4", "p7"] if t in runs]
    showcase_tags = [t for t in showcase_tags if t in runs]
    if not showcase_tags:
        print("[route-viz] no showcase runs available; skipping.")
        return

    print("[route-viz] loading CityGraph base map ...")
    base_img, extent = _get_base_map()

    n = len(showcase_tags)
    fig, axes = plt.subplots(n, 2, figsize=(14, 6.8 * n), constrained_layout=True,
                              squeeze=False)

    for row, tag in enumerate(showcase_tags):
        run_dir = runs[tag]
        gens = _snapshot_gens(run_dir)
        gen_init, gen_final = gens[0], gens[-1]

        routes_init = _load_snapshot_routes(run_dir, gen_init)
        routes_final = _load_snapshot_routes(run_dir, gen_final)
        fit_init = _get_fitness_at_gen(run_dir, gen_init)
        fit_final = _get_fitness_at_gen(run_dir, gen_final)

        if routes_init:
            _draw_route_system_on_ax(
                axes[row, 0], base_img, extent, routes_init,
                f"{tag} — Generation {gen_init} (initial)",
                fitness=fit_init, lw=1.4)
        else:
            axes[row, 0].set_title(f"{tag} — gen {gen_init}: no snapshot")
            axes[row, 0].axis("off")

        if routes_final:
            _draw_route_system_on_ax(
                axes[row, 1], base_img, extent, routes_final,
                f"{tag} — Generation {gen_final} (optimized)",
                fitness=fit_final, lw=1.4)
        else:
            axes[row, 1].set_title(f"{tag} — gen {gen_final}: no snapshot")
            axes[row, 1].axis("off")

    fig.suptitle("Route System Evolution: Initial vs Optimized", fontsize=16, fontweight="bold")
    out = IMG_DIR / "route_system_initial_vs_final.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"[route-viz] {out.name}  ({n} runs × 2 panels)")


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

    # Route system visualization (initial vs final)
    plot_initial_vs_final(runs)

    # PART 2 (heavy). Comment out if you only want the no-sim robustness/convergence.
    resim_evaluation(runs)

    print("\nDone. Figures in", IMG_DIR)


if __name__ == "__main__":
    main()
