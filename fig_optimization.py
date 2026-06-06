"""
fig_optimization.py -- visualize the optimization MECHANICS (Chapter 4.4.1) by replaying a finished
toy optimization run's telemetry. Pure JSON/CSV in, figures out: NO simulation, NO pyrosm, so it runs
anywhere and is fully testable.

It reads a run directory written by utils/optimizer_telemetry.py:
    <run_dir>/history.csv                       (Generation, Global_Best_Cost, Population_Mean_Cost,
                                                 Active_Mutation_Rate, Stagnation_Counter)
    <run_dir>/snapshots/network_state_gen_*.json  (layers.routes / layers.pheromones /
                                                   layers.chokepoints, metadata.topological_hub)

and produces:
  * fig_opt_convergence : best & mean cost vs generation with the adaptive mutation rate, the best
    improving exactly at the marked generations -- the AdaptiveController story, annotated with the
    gen-0 -> final cost reduction.
  * fig_opt_evolution   : a storyboard whose columns are the generations where the BEST changed, with
    three rows -- the best route system, its pheromone memory tau, and its underserved chokepoints --
    so the reader watches topology, demand memory, and service gaps co-evolve from gen 1 to gen N.

This is a TWO-STEP module (it renders a *finished* run, it does not run the optimizer itself):
    python run_toy_optimization.py          # step 1: runs the optimizer (~minutes), writes telemetry
    python fig_optimization.py              # step 2: renders the NEWEST run under outputs/ (fast)
    python fig_optimization.py --run-dir outputs/<...> --only fig_opt_convergence   # explicit / subset
The split means you can re-render / restyle the figures any number of times without re-optimizing.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import PowerNorm

from fig_environment import set_pub_style, IMG_DIR

PHEROMONE_CMAP = "viridis"
GAP_CMAP = "Reds"          # underserved demand-service gap (matches the red side of the Sec 4.3.6 field)
CHOKE_COLOR = "#d62728"
HUB_COLOR = "#000000"
BEST_COLOR = "#CC3311"
MEAN_COLOR = "#4477AA"
MUT_COLOR = "#888888"
ROUTE_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE",
                 "#AA3377", "#999933", "#EE9944", "#882255", "#117733",
                 "#332288", "#DDCC77"]
MAX_STORY_COLS = 5


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------
def load_run(run_dir):
    """Read history.csv + every snapshot JSON. Returns {'history': [...], 'snaps': {gen: payload}}."""
    hist_path = os.path.join(run_dir, "history.csv")
    if not os.path.exists(hist_path):
        raise FileNotFoundError(f"No history.csv in {run_dir}")
    history = []
    with open(hist_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                history.append({
                    "gen": int(float(row["Generation"])),
                    "best": float(row["Global_Best_Cost"]),
                    "mean": float(row["Population_Mean_Cost"]),
                    "mut": float(row.get("Active_Mutation_Rate", "nan") or "nan"),
                    "stag": float(row.get("Stagnation_Counter", "nan") or "nan"),
                })
            except (ValueError, KeyError):
                continue
    history.sort(key=lambda r: r["gen"])

    snaps = {}
    for path in glob.glob(os.path.join(run_dir, "snapshots", "network_state_gen_*.json")):
        try:
            with open(path) as f:
                payload = json.load(f)
            snaps[int(payload["generation"])] = payload
        except (ValueError, KeyError, OSError):
            continue
    return {"history": history, "snaps": snaps, "run_dir": run_dir}


def find_latest_run(root="outputs"):
    """The most recently written run directory (has history.csv + snapshots/) under `root`.
    Lets you skip --run-dir: the toy run you just finished is the newest one."""
    best = None
    for dirpath, _dirs, files in os.walk(root):
        if "history.csv" in files and os.path.isdir(os.path.join(dirpath, "snapshots")):
            mtime = os.path.getmtime(os.path.join(dirpath, "history.csv"))
            if best is None or mtime > best[0]:
                best = (mtime, dirpath)
    return best[1] if best else None


def improvement_generations(history, eps=1e-9):
    """Generations where the global best strictly improved (the 'best changed' events)."""
    gens, best = [], float("inf")
    for r in history:
        if r["best"] < best - eps:
            gens.append(r["gen"])
            best = r["best"]
    return gens


def _nearest_snapshot(snaps, gen):
    """The snapshot at gen, or the closest available one (telemetry_interval may exceed 1)."""
    if gen in snaps:
        return snaps[gen]
    if not snaps:
        return None
    return snaps[min(snaps, key=lambda g: abs(g - gen))]


def _sample_columns(gens, k=MAX_STORY_COLS):
    if len(gens) <= k:
        return gens
    idx = np.unique(np.linspace(0, len(gens) - 1, k).round().astype(int))
    return [gens[i] for i in idx]


# --------------------------------------------------------------------------------------
# Geometry helpers (snapshots store lat/lon dicts)
# --------------------------------------------------------------------------------------
def _route_lonlat(route):
    return [p["lon"] for p in route], [p["lat"] for p in route]


def _global_extent(snaps, gens, margin=0.06):
    lons, lats = [], []
    for g in gens:
        snap = _nearest_snapshot(snaps, g)
        if not snap:
            continue
        for route in snap["layers"]["routes"]:
            for p in route:
                lons.append(p["lon"]); lats.append(p["lat"])
    if not lons:
        return [0, 1, 0, 1]
    dlon = (max(lons) - min(lons)) or 1.0
    dlat = (max(lats) - min(lats)) or 1.0
    return [min(lons) - margin * dlon, max(lons) + margin * dlon,
            min(lats) - margin * dlat, max(lats) + margin * dlat]


def _frame(ax, ext):
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_aspect("equal"); ax.axis("off")


def _pheromone_segments(snap):
    segs, vals = [], []
    for ph in snap["layers"]["pheromones"]:
        e = ph["edge"]
        segs.append([(e[0]["lon"], e[0]["lat"]), (e[1]["lon"], e[1]["lat"])])
        vals.append(ph["intensity"])
    return segs, np.array(vals, dtype=float)


# --------------------------------------------------------------------------------------
# Figure: convergence + adaptive control
# --------------------------------------------------------------------------------------
def fig_opt_convergence(run, out):
    history = run["history"]
    if not history:
        raise ValueError("empty history")
    gens = [r["gen"] for r in history]
    best = [r["best"] for r in history]
    mean = [r["mean"] for r in history]
    mut = [r["mut"] for r in history]
    imp = improvement_generations(history)

    set_pub_style()
    fig, ax = plt.subplots(figsize=(11, 6.2), constrained_layout=True)
    ax.plot(gens, mean, color=MEAN_COLOR, lw=1.8, label="population mean $F_{sim}$", alpha=0.9)
    ax.plot(gens, best, color=BEST_COLOR, lw=2.4, label="global best $F_{sim}$")
    best_by_gen = dict(zip(gens, best))
    ax.scatter(imp, [best_by_gen[g] for g in imp], color=BEST_COLOR, edgecolor="white",
               zorder=5, s=55, label="best improved")
    ax.set_xlabel("generation"); ax.set_ylabel(r"$F_{sim}$  (total user cost, lower is better)")
    ax.grid(alpha=0.3)

    if np.isfinite(np.nanmax(mut)):
        ax2 = ax.twinx()
        ax2.plot(gens, mut, color=MUT_COLOR, lw=1.4, ls="--", label="mutation rate")
        ax2.set_ylabel("active mutation rate", color=MUT_COLOR)
        ax2.tick_params(axis="y", labelcolor=MUT_COLOR)
        lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
        labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
        ax.legend(lines, labels, loc="upper right", framealpha=0.9)
    else:
        ax.legend(loc="upper right", framealpha=0.9)

    f0, fN = best[0], best[-1]
    red = (f0 - fN) / f0 * 100 if f0 else 0.0
    ax.set_title(f"Convergence over {len(gens)} generations — best $F_{{sim}}$ "
                 f"{f0:.0f} → {fN:.0f} ({red:.1f}% reduction, {len(imp)} improvements)",
                 fontsize=13, fontweight="bold")
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Figure: best-network evolution storyboard
# --------------------------------------------------------------------------------------
def fig_opt_evolution(run, out):
    history, snaps = run["history"], run["snaps"]
    if not snaps:
        raise ValueError("no snapshots to render")
    imp = improvement_generations(history) or sorted(snaps)
    cols = _sample_columns(imp)
    ext = _global_extent(snaps, cols)
    best_by_gen = {r["gen"]: r["best"] for r in history}

    # shared pheromone scale across shown gens
    pmax = 1.1
    for g in cols:
        snap = _nearest_snapshot(snaps, g)
        if snap:
            _, v = _pheromone_segments(snap)
            if v.size:
                pmax = max(pmax, float(v.max()))
    pnorm = PowerNorm(0.5, vmin=1.1, vmax=pmax)

    # shared demand-service gap scale across shown gens, so the gap visibly shrinks generation to generation
    gmax = 0.0
    for g in cols:
        snap = _nearest_snapshot(snaps, g)
        if snap:
            for c in snap["layers"].get("chokepoints", []):
                gmax = max(gmax, float(c.get("gap_value", 0.0)))
    gnorm = PowerNorm(0.6, vmin=0.0, vmax=(gmax or 1.0))

    set_pub_style()
    nrows, ncols = 3, len(cols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.5 * ncols, 10.5), constrained_layout=True)
    axes = np.atleast_2d(axes)
    if ncols == 1:
        axes = axes.reshape(nrows, 1)

    lc_last = gc_last = None
    for j, g in enumerate(cols):
        snap = _nearest_snapshot(snaps, g)
        routes = snap["layers"]["routes"]

        # row 0: best route system
        ax = axes[0, j]; _frame(ax, ext)
        for i, route in enumerate(routes):
            xs, ys = _route_lonlat(route)
            ax.plot(xs, ys, color=ROUTE_PALETTE[i % len(ROUTE_PALETTE)], lw=2.0, zorder=2)
        cost = best_by_gen.get(g)
        ax.set_title(f"Gen {g}" + (f"\n$F_{{sim}}={cost:.0f}$" if cost is not None else ""), fontsize=11)

        # row 1: pheromone memory tau
        ax = axes[1, j]; _frame(ax, ext)
        segs, vals = _pheromone_segments(snap)
        if segs:
            order = np.argsort(vals)
            lc = LineCollection([segs[i] for i in order], cmap=PHEROMONE_CMAP, norm=pnorm,
                                linewidths=0.8 + 4.0 * np.clip((vals[order] - 1.1) / (pmax - 1.1 or 1), 0, 1),
                                capstyle="round")
            lc.set_array(vals[order])
            ax.add_collection(lc); lc_last = lc

        # row 2: demand-service gap (underserved corridors) on a shared scale across generations
        ax = axes[2, j]; _frame(ax, ext)
        for route in routes:
            xs, ys = _route_lonlat(route)
            ax.plot(xs, ys, color="#CCCCCC", lw=1.0, zorder=1)
        chokes = snap["layers"].get("chokepoints", [])
        if chokes:
            cx = [c["lon"] for c in chokes]; cy = [c["lat"] for c in chokes]
            cs = np.array([float(c["gap_value"]) for c in chokes], dtype=float)
            gc_last = ax.scatter(cx, cy, c=cs, cmap=GAP_CMAP, norm=gnorm,
                                 s=22 + 80 * np.clip(cs / (gmax or 1), 0, 1),
                                 alpha=0.9, edgecolor="white", linewidth=0.4, zorder=3)
        hub = snap.get("metadata", {}).get("topological_hub")
        if hub:
            ax.scatter([hub["lon"]], [hub["lat"]], marker="*", s=170, facecolor="none",
                       edgecolor=HUB_COLOR, linewidth=1.4, zorder=4)

    axes[0, 0].set_ylabel("best route system", fontsize=12)
    axes[1, 0].set_ylabel(r"pheromone memory $\tau$", fontsize=12)
    axes[2, 0].set_ylabel("demand-service gap", fontsize=12)
    for r in range(3):  # set_ylabel needs the axis visible
        axes[r, 0].axis("on"); axes[r, 0].set_xticks([]); axes[r, 0].set_yticks([])
        for sp in axes[r, 0].spines.values():
            sp.set_visible(False)

    if lc_last is not None:
        cb = fig.colorbar(lc_last, ax=axes[1, :].tolist(), shrink=0.7, aspect=30, pad=0.01)
        cb.set_label(r"pheromone $\tau$ (shared)")
    if gc_last is not None:
        cbg = fig.colorbar(gc_last, ax=axes[2, :].tolist(), shrink=0.7, aspect=30, pad=0.01)
        cbg.set_label(r"demand$-$service gap $\Delta$ (underserved, shared)")

    fig.suptitle("Best-network evolution at each improvement — topology, demand memory, and "
                 "service gaps co-evolving", fontsize=14, fontweight="bold")
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
FIGS = {
    "fig_opt_convergence": fig_opt_convergence,
    "fig_opt_evolution": fig_opt_evolution,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default=None,
                    help="optimizer run directory (history.csv + snapshots/). "
                         "If omitted, the most recent run under outputs/ is used.")
    ap.add_argument("--only", nargs="*", metavar="NAME", help="subset of figure names")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for n in FIGS:
            print(n)
        return

    names = args.only or list(FIGS)
    unknown = [n for n in names if n not in FIGS]
    if unknown:
        raise SystemExit(f"Unknown figure(s): {unknown}\nKnown: {list(FIGS)}")

    run_dir = args.run_dir or find_latest_run()
    if not run_dir:
        raise SystemExit("No --run-dir given and no run found under outputs/.\n"
                         "Run 'python run_toy_optimization.py' first to produce one.")
    if not args.run_dir:
        print(f"[auto] newest run under outputs/: {run_dir}")

    set_pub_style()
    os.makedirs(IMG_DIR, exist_ok=True)
    run = load_run(run_dir)
    print(f"[load] {len(run['history'])} generations, {len(run['snaps'])} snapshots from {run_dir}")
    print(f"[load] best improved at generations: {improvement_generations(run['history'])}")
    for n in names:
        out = os.path.join(IMG_DIR, f"{n}.png")
        print(f"[fig] {n} -> {FIGS[n](run, out)}")


if __name__ == "__main__":
    main()
