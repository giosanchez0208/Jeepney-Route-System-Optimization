"""
fig_environment.py -- regenerate the Chapter 4.1-4.2 "environment" figures with ONE consistent,
publication-quality style (serif, sequential colormaps, real colorbars, faint city base map).

Why this exists
---------------
The biggest culprit was the Direct Demand Model (DDM). The old `ddm_time_comparison` and
`ddm_whole_vs_arterials` figures were rendered with `DirectDemandSampler.draw_density()` -- a
5000-point *random* PIL scatter (blue->yellow->red, NO colorbar). Low-demand points dominated as
visual noise, the colours had no legend, and the three time panels weren't even on a shared scale,
so 8 AM / 1 PM / 5 PM could not be compared.

Here the demand field (`ddm.node_probabilities` -- the quantity the sampler actually draws from) is
rendered the same proven way the liked `ddm_3maps_comparison` figure already works: a faint city
base + a node scatter coloured by demand, with a colorbar and a SHARED colour scale across panels.
Demand uses a warm light-yellow -> deep-red ramp (YlOrRd) with a power-norm so skewed demand
corridors actually show.

Everything reads from the pickles in rnd/pkl/ -- no CityGraph/TravelGraph rebuild, no simulation --
so it is fast and safe to re-run.

    python fig_environment.py                         # regenerate all
    python fig_environment.py --only ddm_time_comparison ddm_whole_vs_arterials
    python fig_environment.py --list                  # show figure names

Outputs land in results_and_discussion/images/ under the names collect_figures.py expects.
"""
from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")  # headless: save only, never open a window
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize, PowerNorm

# NOTE: reuse_citygraph/reuse_ddm are imported lazily inside load_assets() because
# utils_simplified -> utils.city_graph pulls in pyrosm (a heavy OSM dependency present only on the
# run machines). Keeping it lazy lets the pure-matplotlib renderers (and their tiny test) import and
# run anywhere; only actual figure generation from the pickles needs pyrosm.

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------
PKL_DIR = "rnd/pkl"
IMG_DIR = "results_and_discussion/images"
CG_PKL = os.path.join(PKL_DIR, "profile_p1.pkl")
DDM_PKLS = {"8:00 AM": "ddm_8am.pkl", "1:00 PM": "ddm_1pm.pkl", "5:00 PM": "ddm_5pm.pkl"}

# --------------------------------------------------------------------------------------
# One consistent look
# --------------------------------------------------------------------------------------
DEMAND_CMAP = "YlOrRd"     # demand: pale yellow (low, recedes on white) -> deep red (high, pops)
DEMAND_GAMMA = 0.5         # PowerNorm gamma < 1 spreads the heavy right-skew so corridors show
FRICTION_CMAP = "plasma"   # TomTom friction weight (a different quantity than demand)
CENTRALITY_CMAP = "Reds"   # betweenness centrality
IDW_CMAP = "Blues"         # IDW traffic weights
DEMAND_HIST_COLOR = "#e34a33"  # warm tone tying the OD histogram to the demand cmap

BASE_SIZE = 800            # px of the PIL city render used as the faint base
BASE_ALPHA = 0.35          # faintness of that base map


def set_pub_style() -> None:
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


# --------------------------------------------------------------------------------------
# Core renderer: a node-value heatmap on a faint city base, colorbar-ready
# --------------------------------------------------------------------------------------
def _extent(cg) -> list[float]:
    """[left_lon, right_lon, bottom_lat, top_lat] matching the square PIL render's framing."""
    (tl_lon, tl_lat), (br_lon, br_lat) = cg.get_bounds()
    return [tl_lon, br_lon, br_lat, tl_lat]


def _scatter_field(ax, base_img, extent, node_values, norm, cmap, *,
                   drivable=None, s_lo=6.0, s_hi=34.0, alpha=0.9):
    """Faint city base + nodes scattered in lon/lat, coloured (and sized) by value.

    Low values are drawn first so high-demand nodes sit on top; point size scales with the
    normalized value so dominant corridors read at a glance. Returns the mappable for a colorbar.
    """
    # The PIL base is a square render of square (equal-degree-span) bounds, so imshow's default
    # equal aspect keeps the map undistorted and lets the axes size itself to the map (no forced
    # box aspect fighting constrained_layout / leaving a sea of whitespace).
    ax.imshow(base_img, extent=extent, alpha=BASE_ALPHA, zorder=0)

    drivable = set(drivable) if drivable is not None else None
    items = [(n, v) for n, v in node_values.items() if drivable is None or n in drivable]
    if items:
        xs = np.fromiter((n.lon for n, _ in items), float, len(items))
        ys = np.fromiter((n.lat for n, _ in items), float, len(items))
        vs = np.fromiter((float(v) for _, v in items), float, len(items))
        order = np.argsort(vs)  # low -> high so the strongest land on top
        xs, ys, vs = xs[order], ys[order], vs[order]
        t = np.clip(np.nan_to_num(np.asarray(norm(vs), dtype=float)), 0.0, 1.0)
        sizes = s_lo + (s_hi - s_lo) * t
        sc = ax.scatter(xs, ys, c=vs, cmap=cmap, norm=norm, s=sizes,
                        alpha=alpha, edgecolors="none", zorder=2)
    else:
        from matplotlib.cm import ScalarMappable
        sc = ScalarMappable(norm=norm, cmap=cmap)
        sc.set_array([])

    ax.axis("off")
    return sc


def _demand_norm(*ddms) -> PowerNorm:
    """Shared power-norm over one or more DDMs so panels are directly comparable."""
    vmax = max((max(d.node_probabilities.values(), default=0.0) for d in ddms), default=0.0)
    return PowerNorm(DEMAND_GAMMA, vmin=0.0, vmax=(vmax or 1.0))


# --------------------------------------------------------------------------------------
# Figures -- 4.1 Direct Demand Model
# --------------------------------------------------------------------------------------
def fig_ddm_time_comparison(A, out):
    """8 AM / 1 PM / 5 PM demand fields on a SHARED scale with one colorbar (now comparable)."""
    cg = A["cg"]
    panels = [(lbl, A["ddm"][lbl]) for lbl in DDM_PKLS]
    base = cg.draw(size=BASE_SIZE, only_drivable=False)
    extent = _extent(cg)
    norm = _demand_norm(*(d for _, d in panels))

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 6.4), constrained_layout=True)
    sc = None
    for ax, letter, (lbl, d) in zip(axes, "abc", panels):
        sc = _scatter_field(ax, base, extent, d.node_probabilities, norm, DEMAND_CMAP)
        ax.set_title(f"({letter}) {lbl} Direct Demand Model", fontsize=13)
    cbar = fig.colorbar(sc, ax=axes.ravel().tolist(), shrink=0.82, aspect=32, pad=0.012)
    cbar.set_label("OD demand probability  (shared scale)")
    fig.suptitle("Direct Demand Model across the service day")
    fig.savefig(out)
    plt.close(fig)
    return out


def fig_ddm_whole_vs_arterials(A, out):
    """Complete vs arterials-only demand sampling, shared scale + colorbar."""
    cg, d = A["cg"], A["ddm"]["1:00 PM"]
    base_whole = cg.draw(size=BASE_SIZE, only_drivable=False)
    base_art = cg.draw(size=BASE_SIZE, only_drivable=True)
    extent = _extent(cg)
    norm = _demand_norm(d)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6.8), constrained_layout=True)
    _scatter_field(axes[0], base_whole, extent, d.node_probabilities, norm, DEMAND_CMAP)
    axes[0].set_title("(a) Complete DDM Sampling")
    sc = _scatter_field(axes[1], base_art, extent, d.node_probabilities, norm, DEMAND_CMAP,
                        drivable=getattr(d, "drivable_nodes", None))
    axes[1].set_title("(b) Arterials-Only DDM Sampling")
    cbar = fig.colorbar(sc, ax=axes.ravel().tolist(), shrink=0.82, aspect=30, pad=0.012)
    cbar.set_label("OD demand probability  (shared scale)")
    fig.suptitle("Direct Demand sampling: whole network vs drivable arterials")
    fig.savefig(out)
    plt.close(fig)
    return out


def fig_ddm_pre_imputed(A, out):
    """Raw TomTom empirical friction points (distinct quantity -> plasma, kept from the good version)."""
    cg, d = A["cg"], A["ddm"]["1:00 PM"]
    base = cg.draw(size=BASE_SIZE, only_drivable=False)
    extent = _extent(cg)
    vals = d.empirical_traffic
    vmin = min(vals.values(), default=1.0)
    vmax = max(vals.values(), default=1.0)
    norm = Normalize(vmin=vmin, vmax=(vmax if vmax > vmin else vmin + 1e-6))

    fig, ax = plt.subplots(figsize=(8.5, 8.5), constrained_layout=True)
    sc = _scatter_field(ax, base, extent, vals, norm, FRICTION_CMAP, s_lo=20, s_hi=46, alpha=0.85)
    ax.set_title("Pre-Imputed Points (TomTom Empirical Data)")
    cbar = fig.colorbar(sc, ax=ax, shrink=0.82, aspect=30, pad=0.02)
    cbar.set_label("Friction Weight (Travel Time / Free Flow)")
    fig.savefig(out)
    plt.close(fig)
    return out


def fig_ddm_3maps_comparison(A, out):
    """(a) betweenness centrality, (b) IDW traffic weights, (c) combined OD demand.

    Keeps the liked layout; only the demand panel (c) moves to the consistent YlOrRd demand ramp.
    """
    import matplotlib.gridspec as gridspec
    cg, d = A["cg"], A["ddm"]["1:00 PM"]
    base = cg.draw(size=BASE_SIZE, only_drivable=False)
    extent = _extent(cg)

    fig = plt.figure(figsize=(15, 13.5), constrained_layout=True)
    gs = gridspec.GridSpec(2, 2, figure=fig)

    ax1 = fig.add_subplot(gs[0, 0])
    cs = d.centrality_scores
    sc1 = _scatter_field(ax1, base, extent, cs, Normalize(0.0, max(cs.values(), default=1.0)),
                         CENTRALITY_CMAP, s_lo=5, s_hi=20)
    fig.colorbar(sc1, ax=ax1, shrink=0.8, aspect=28, pad=0.02).set_label("Betweenness Centrality")
    ax1.set_title("(a) Betweenness Centrality Map")

    ax2 = fig.add_subplot(gs[0, 1])
    ws = d.traffic_weights
    sc2 = _scatter_field(ax2, base, extent, ws,
                         Normalize(min(ws.values(), default=1.0), max(ws.values(), default=1.0)),
                         IDW_CMAP, s_lo=5, s_hi=20)
    fig.colorbar(sc2, ax=ax2, shrink=0.8, aspect=28, pad=0.02).set_label("IDW Traffic Weights")
    ax2.set_title("(b) IDW Traffic Weights Map")

    ax3 = fig.add_subplot(gs[1, :])
    sc3 = _scatter_field(ax3, base, extent, d.node_probabilities, _demand_norm(d),
                         DEMAND_CMAP, s_lo=6, s_hi=30)
    fig.colorbar(sc3, ax=ax3, shrink=0.8, aspect=34, pad=0.015).set_label("OD demand probability")
    ax3.set_title("(c) Combined OD Demand Map")

    fig.suptitle("Direct Demand Model components")
    fig.savefig(out)
    plt.close(fig)
    return out


def fig_ddm_distributions(A, out):
    """3x3 histograms of centrality / IDW weights / OD demand at 8 AM, 1 PM, 5 PM."""
    panels = [(lbl, A["ddm"][lbl]) for lbl in DDM_PKLS]
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), constrained_layout=True)
    for i, (lbl, d) in enumerate(panels):
        axes[i, 0].hist(list(d.centrality_scores.values()), bins=50, color="indianred", alpha=0.85)
        axes[i, 0].set_title(f"{lbl} - Betweenness Centrality", fontsize=12)
        axes[i, 0].set_yscale("log"); axes[i, 0].set_ylabel("Frequency (log)")

        axes[i, 1].hist(list(d.traffic_weights.values()), bins=50, color="steelblue", alpha=0.85)
        axes[i, 1].set_title(f"{lbl} - IDW Traffic Weights", fontsize=12)
        axes[i, 1].set_ylabel("Frequency")

        axes[i, 2].hist(list(d.node_probabilities.values()), bins=50, color=DEMAND_HIST_COLOR, alpha=0.85)
        axes[i, 2].set_title(f"{lbl} - Combined OD Demand", fontsize=12)
        axes[i, 2].set_yscale("log"); axes[i, 2].set_ylabel("Frequency (log)")

        if i == 2:
            axes[i, 0].set_xlabel("Centrality score")
            axes[i, 1].set_xlabel("Friction weight (TT / FFTT)")
            axes[i, 2].set_xlabel("OD demand probability")
    fig.suptitle("Direct Demand Model distributions across the service day")
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Figures -- 4.1 City graph
# --------------------------------------------------------------------------------------
def fig_citygraph_comparison(A, out):
    """Whole vs arterial-only city graph, with landmarks stamped (best-effort)."""
    cg = A["cg"]
    try:
        cg.landmarks.clear()
        cg._build_landmarks({"MSU-IIT": (8.2415, 124.2435), "Robinsons Iligan": (8.2045, 124.2370)})
    except Exception as e:  # landmark API drift shouldn't sink the figure
        print(f"  [citygraph] landmarks skipped: {e}")

    def _stamp(img):
        try:
            return cg.draw_landmarks(img)
        except Exception:
            return img

    img_whole = _stamp(cg.draw(size=BASE_SIZE, only_drivable=False))
    img_art = _stamp(cg.draw(size=BASE_SIZE, only_drivable=True))

    fig, axes = plt.subplots(1, 2, figsize=(15, 7.6), constrained_layout=True)
    axes[0].imshow(img_whole); axes[0].set_title("(a) Whole City Graph"); axes[0].axis("off")
    axes[1].imshow(img_art); axes[1].set_title("(b) Arterial City Graph (Drivable Only)"); axes[1].axis("off")
    fig.suptitle("Iligan City road network")
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Registry + driver
# --------------------------------------------------------------------------------------
FIGS = {
    "citygraph_comparison": fig_citygraph_comparison,
    "ddm_pre_imputed": fig_ddm_pre_imputed,
    "ddm_3maps_comparison": fig_ddm_3maps_comparison,
    "ddm_time_comparison": fig_ddm_time_comparison,
    "ddm_whole_vs_arterials": fig_ddm_whole_vs_arterials,
    "ddm_distributions": fig_ddm_distributions,
}


def load_assets():
    from utils_simplified import reuse_citygraph, reuse_ddm  # lazy: pulls in pyrosm
    cg = reuse_citygraph(CG_PKL)
    ddm = {lbl: reuse_ddm(os.path.join(PKL_DIR, fn)) for lbl, fn in DDM_PKLS.items()}
    return {"cg": cg, "ddm": ddm}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", metavar="NAME", help="subset of figure names to regenerate")
    ap.add_argument("--list", action="store_true", help="list figure names and exit")
    args = ap.parse_args()

    if args.list:
        print("Available figures:")
        for n in FIGS:
            print(f"  {n}")
        return

    names = args.only or list(FIGS)
    unknown = [n for n in names if n not in FIGS]
    if unknown:
        raise SystemExit(f"Unknown figure(s): {unknown}\nKnown: {list(FIGS)}")

    set_pub_style()
    os.makedirs(IMG_DIR, exist_ok=True)
    A = load_assets()
    for n in names:
        out = os.path.join(IMG_DIR, f"{n}.png")
        print(f"[fig] {n} ...")
        print(f"      saved {FIGS[n](A, out)}")


if __name__ == "__main__":
    main()
