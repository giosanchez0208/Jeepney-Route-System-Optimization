"""Generate the three Chapter-3 methodology illustration flowcharts (rendered PNGs):
    chap3/figures/fig_system_pipeline.png        -- high-level methodology pipeline
    chap3/figures/fig_simulation_loop.png        -- per-tick event loop + passenger state machine
    chap3/figures/fig_optimization_pipeline.png  -- memetic GA-ACO generational loop (with elitism)

These are illustrative schematics (no real data). Pure matplotlib, so they render anywhere.

    python scratch/_gen_methodology_diagrams.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({"font.family": "serif", "savefig.dpi": 200})

OUT = "chap3/figures"

C_INPUT = "#E9E9E9"
C_ENV = "#CFE3F3"
C_SIM = "#CDE9D3"
C_OPT = "#FBE2C4"
C_OUT = "#E3D4F0"
C_CTRL = "#F7D6D6"
C_DEC = "#FFF3BF"
EDGE = "#3a3a3a"


def box(ax, cx, cy, w, h, title, sub=None, fc="#fff", ec=EDGE, tfs=11, sfs=9):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.10", linewidth=1.3,
                 edgecolor=ec, facecolor=fc, zorder=2))
    if sub:
        ax.text(cx, cy + h * 0.16, title, ha="center", va="center", fontsize=tfs,
                fontweight="bold", color="#111", zorder=3)
        ax.text(cx, cy - h * 0.22, sub, ha="center", va="center", fontsize=sfs,
                color="#333", zorder=3, linespacing=1.2)
    else:
        ax.text(cx, cy, title, ha="center", va="center", fontsize=tfs, fontweight="bold",
                color="#111", zorder=3, linespacing=1.2)
    return dict(cx=cx, cy=cy, w=w, h=h)


def diamond(ax, cx, cy, w, h, text, fc=C_DEC):
    ax.add_patch(plt.Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
                 closed=True, linewidth=1.3, edgecolor=EDGE, facecolor=fc, zorder=2))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=9, fontweight="bold",
            color="#111", zorder=3, linespacing=1.15)
    return dict(cx=cx, cy=cy, w=w, h=h)


def pt(b, side):
    cx, cy, w, h = b["cx"], b["cy"], b["w"], b["h"]
    return {"top": (cx, cy + h / 2), "bottom": (cx, cy - h / 2),
            "left": (cx - w / 2, cy), "right": (cx + w / 2, cy)}[side]


def arrow(ax, p1, p2, label=None, rad=0.0, color=EDGE, ls="-", fs=8.5, lx=0.0, ly=0.0, lw=1.5):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=15, lw=lw,
                 color=color, linestyle=ls, connectionstyle=f"arc3,rad={rad}", zorder=1))
    if label:
        mx, my = (p1[0] + p2[0]) / 2 + lx, (p1[1] + p2[1]) / 2 + ly
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs, color="#333",
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="none", alpha=0.9), zorder=4)


def _canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.set_aspect("equal"); ax.axis("off")
    return fig, ax


# ---------------------------------------------------------------------------
def fig_system_pipeline():
    fig, ax = _canvas(17, 6.2)
    y = 4.2
    xs = [2.0, 5.0, 8.0, 11.0, 14.0]
    bw, bh = 2.5, 1.5
    cg = box(ax, xs[0], y, bw, bh, "CityGraph", "OSM arterial\nroad network", fc=C_ENV)
    dm = box(ax, xs[1], y, bw, bh, "Direct Demand\nModel", "OD centrality\nsurface", fc=C_ENV)
    tg = box(ax, xs[2], y, bw, bh, "TravelGraph", "multi-layer\nEIVM cost", fc=C_ENV)
    sim = box(ax, xs[3], y, bw, bh, "Agent-Based\nSimulation", r"total user cost $F_{sim}$", fc=C_SIM)
    opt = box(ax, xs[4], y, bw, bh, "Memetic\nGA-ACO Optimizer", "evolves route\nsystems", fc=C_OPT)
    out = box(ax, 14.0, 1.4, bw, 1.2, "Optimized Route Network", fc=C_OUT, tfs=11)

    arrow(ax, pt(cg, "right"), pt(dm, "left"))
    arrow(ax, pt(dm, "right"), pt(tg, "left"))
    arrow(ax, pt(tg, "right"), pt(sim, "left"))
    # optimizer <-> simulation evaluation loop
    arrow(ax, pt(sim, "right"), pt(opt, "left"), label=r"$F_{sim}$", ly=0.28)
    arrow(ax, (opt["cx"], opt["cy"] - bh / 2), (sim["cx"], sim["cy"] - bh / 2),
          label="candidate route systems", rad=-0.45, ly=-0.15)
    # survey feeds the EIVM cost weights into the TravelGraph
    sv = box(ax, 8.0, 1.4, 3.0, 1.2, "Commuter Survey", "calibrated EIVM weights", fc=C_INPUT, tfs=11, sfs=9)
    arrow(ax, pt(sv, "top"), pt(tg, "bottom"), label="walk / wait /\ntransfer weights", lx=1.35, fs=8)
    arrow(ax, pt(opt, "bottom"), pt(out, "top"), rad=0.0)

    ax.text(8.5, 5.7, "Methodology pipeline: from empirical data to an optimized jeepney network",
            ha="center", va="center", fontsize=13, fontweight="bold")
    fig.savefig(os.path.join(OUT, "fig_system_pipeline.png"), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
def fig_simulation_loop():
    fig, ax = _canvas(15, 9.5)

    # ---- left: per-tick event loop ----
    cx = 4.0
    ax.text(cx, 9.0, "Per-tick simulation loop", ha="center", fontsize=12, fontweight="bold")
    bw, bh = 3.6, 0.9
    ys = [8.0, 6.9, 5.8, 4.7, 3.6]
    b0 = box(ax, cx, ys[0], bw, bh, "Generate passengers", "DDM rate schedule", fc=C_SIM, tfs=10, sfs=8)
    b1 = box(ax, cx, ys[1], bw, bh, "Update jeep agents", "advance along route loops", fc=C_SIM, tfs=10, sfs=8)
    b2 = box(ax, cx, ys[2], bw, bh, "Update passenger agents", "walk / wait / ride", fc=C_SIM, tfs=10, sfs=8)
    b3 = box(ax, cx, ys[3], bw, bh, "Process boarding / alighting", "capacity-checked events", fc=C_SIM, tfs=10, sfs=8)
    b4 = box(ax, cx, ys[4], bw, bh, "Record tick metrics", fc=C_SIM, tfs=10)
    dec = diamond(ax, cx, 2.25, 2.6, 1.3, "tick <\nnum_ticks ?")
    fsim = box(ax, cx, 0.7, bw, 0.9, r"Compute $F_{sim}$", "user cost + penalties + equity", fc=C_OUT, tfs=10, sfs=8)
    for a, b in [(b0, b1), (b1, b2), (b2, b3), (b3, b4)]:
        arrow(ax, pt(a, "bottom"), pt(b, "top"))
    arrow(ax, pt(b4, "bottom"), pt(dec, "top"))
    # loop-back: decision -> left -> up -> into "Generate passengers"
    lxx = cx - bw / 2 - 0.75
    ax.add_patch(FancyArrowPatch(pt(dec, "left"), (lxx, dec["cy"]), arrowstyle="-", lw=1.5, color=EDGE, zorder=1))
    ax.add_patch(FancyArrowPatch((lxx, dec["cy"]), (lxx, ys[0]), arrowstyle="-", lw=1.5, color=EDGE, zorder=1))
    arrow(ax, (lxx, ys[0]), pt(b0, "left"))
    ax.text(lxx - 0.14, (dec["cy"] + ys[0]) / 2, "yes  (next tick)", rotation=90, ha="center",
            va="center", fontsize=8.5, color="#333")
    arrow(ax, pt(dec, "bottom"), pt(fsim, "top"), label="no  (horizon reached)", lx=2.4, fs=8)

    # ---- right: passenger state machine ----
    sx = 11.2
    ax.text(sx, 9.0, "Passenger state machine", ha="center", fontsize=12, fontweight="bold")
    walk = box(ax, sx, 7.4, 2.5, 1.0, "WALKING", fc=C_ENV, tfs=11)
    wait = box(ax, sx, 5.4, 2.5, 1.0, "WAITING", fc=C_ENV, tfs=11)
    ride = box(ax, sx, 3.4, 2.5, 1.0, "RIDING", fc=C_ENV, tfs=11)
    done = box(ax, sx, 1.3, 2.5, 1.0, "DONE", fc=C_OUT, tfs=11)
    arrow(ax, pt(walk, "bottom"), pt(wait, "top"), label="reach stop", lx=1.2, fs=8)
    arrow(ax, pt(wait, "bottom"), pt(ride, "top"), label="board\n(capacity OK)", lx=-1.55, fs=8)
    arrow(ax, pt(ride, "left"), pt(walk, "left"), label="alight", rad=-0.62, lx=-0.5, fs=8)
    arrow(ax, pt(walk, "right"), pt(done, "right"), label="journey\ncomplete", rad=-0.78, lx=1.2, ly=-0.5, fs=8)

    fig.savefig(os.path.join(OUT, "fig_simulation_loop.png"), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
def fig_optimization_pipeline():
    fig, ax = _canvas(13.5, 11.5)
    cx = 5.2
    bw = 5.6
    ax.text(cx, 11.0, "Memetic GA-ACO generational loop", ha="center", fontsize=13, fontweight="bold")

    init = box(ax, cx, 10.1, bw, 0.85, "Initialize population", "random valid route systems", fc=C_INPUT, tfs=11, sfs=9)
    par = box(ax, cx, 8.85, bw, 1.0, "Parent evaluation", r"agent sim $\rightarrow$ $F_{sim}$ + pheromone map", fc=C_SIM, tfs=11, sfs=9)
    sel = box(ax, cx, 7.45, bw, 1.15, "Selection",
              "Elitism: copy top-$n$ unchanged\nTournament: pick parent pairs", fc=C_OPT, tfs=11, sfs=9)
    xo = box(ax, cx, 6.05, bw, 1.0, "Topological Hub Crossover", "trunk + complementary feeders", fc=C_OPT, tfs=11, sfs=9)
    inh = box(ax, cx, 4.75, bw, 1.05, "Epigenetic Pheromone Inheritance",
              r"fitness-weighted blend $w_A\tau^A + w_B\tau^B$", fc=C_OPT, tfs=11, sfs=9)
    ls = box(ax, cx, 3.4, bw, 1.1, "Lamarckian Local Search",
             "attraction / repulsion / pruning\ngap-gated acceptance", fc=C_OPT, tfs=11, sfs=9)
    fin = box(ax, cx, 2.1, bw, 1.0, "Final evaluation", r"single agent sim $\rightarrow$ $F_{sim}$ + new pheromone", fc=C_SIM, tfs=11, sfs=9)
    dec = diamond(ax, cx, 0.75, 4.0, 1.25, "Converged?  (elite Jaccard >= θ\nand fitness variance < ε)")
    out = box(ax, 11.4, 0.75, 3.2, 1.0, "Optimized\nRoute Network", fc=C_OUT, tfs=11)

    for a, b in [(init, par), (par, sel), (sel, xo), (xo, inh), (inh, ls), (ls, fin), (fin, dec)]:
        arrow(ax, pt(a, "bottom"), pt(b, "top"))
    arrow(ax, pt(dec, "right"), pt(out, "left"), label="yes", ly=0.25)
    # loop back (no) to selection, routed along the left
    lx = cx - bw / 2 - 0.7
    for p1, p2 in [(pt(dec, "left"), (lx, 0.75)), ((lx, 0.75), (lx, sel["cy"]))]:
        ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-", lw=1.6, color=EDGE, zorder=1))
    arrow(ax, (lx, sel["cy"]), pt(sel, "left"))
    ax.text(lx - 0.15, 4.8, "no  (next generation)", rotation=90, ha="center", va="center",
            fontsize=9, color="#333")

    # adaptive controller drives mutation rate / LS intensity
    ctrl = box(ax, 11.6, 3.4, 3.4, 1.5, "Adaptive Controller",
               "stagnation counter scales\nmutation rate & LS intensity;\nresets on improvement", fc=C_CTRL, tfs=11, sfs=8.5)
    arrow(ax, pt(ctrl, "left"), pt(ls, "right"), label="rate / intensity", ly=0.25, fs=8)
    arrow(ax, (par["cx"] + bw / 2, par["cy"]), (ctrl["cx"], ctrl["cy"] + 1.5 / 2),
          label="best-fitness\nfeedback", rad=-0.3, fs=8, ls="--", color="#888")

    fig.savefig(os.path.join(OUT, "fig_optimization_pipeline.png"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_system_pipeline()
    fig_simulation_loop()
    fig_optimization_pipeline()
    print("wrote 3 diagrams to", OUT)
