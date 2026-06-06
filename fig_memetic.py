"""
fig_memetic.py -- showcase figures for the Lamarckian / memetic *mechanics* (Chapter 4.3.6 + 4.4.2 +
4.4.3), rendered on the Manhattan toy grid for visual clarity and annotated with real numbers.

It makes the hidden machinery legible:

  1. memetic_demand_memory_gap : one route system shown as DDM demand PRIOR -> route system ->
     post-simulation pheromone MEMORY (tau) -> signed demand-service GAP. Ties the stigmergic
     pheromone (Sec 3.5.1) back to the demand model it is related to.
  2. memetic_hub_crossover     : the Topological Hub (top-10% tau edges) on parent A, the feeder
     donors on parent B, and the resulting child = trunk(A) + feeders(B). (Sec 3.5.2.5 / 4.4.2)
  3. memetic_pheromone_blend   : the fitness-weighted epigenetic blend tau_child = wA*tauA + wB*tauB
     of the two parents' demand maps. (Sec 3.5.2.6 / 4.4.3)
  4. memetic_gap_change        : the demand-service disparity D(R)=sum|P-S| of parent A, parent B,
     and their child -- does hub crossover yield a less mismatched network? (Sec 3.5.4)

Efficiency: THREE toy simulations (parent A, parent B, child) feed all four figures; parent A is
also the single-system showcase. Sims use the calibrated production values (num_ticks=540,
seconds_per_tick=10).

Heavy deps (utils_simplified -> pyrosm, the simulator) are imported lazily inside build_scene(), so
the pure-matplotlib renderers and their tiny test import and run anywhere.

    python fig_memetic.py                 # build the scene (3 sims) and render all 4 figures
    python fig_memetic.py --only memetic_hub_crossover
    python fig_memetic.py --list
"""
from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import PowerNorm, TwoSlopeNorm

# Reuse the §4.1 environment look so demand renders identically across chapters.
from fig_environment import (
    set_pub_style, _extent, _scatter_field, _demand_norm,
    DEMAND_CMAP, BASE_ALPHA, BASE_SIZE, IMG_DIR,
)

# --------------------------------------------------------------------------------------
# Consistent look for the memetic quantities
# --------------------------------------------------------------------------------------
# Production-calibrated stable simulation values (Sec 4.3.1/4.3.3) -- forced, NOT read from the toy
# config, so every showcase sim runs at the same evaluated operating point the thesis calibrated.
STABLE_NUM_TICKS = 540
STABLE_SECONDS_PER_TICK = 10
STABLE_SPAWN_RATE = 600.0
PROD_WEIGHT_TOLERANCE = 14.44

# Toy config with the additive-Gaussian 'real city' demand (CBD + Port), not the flat IDW default.
TOY_CONFIG = "configs/toy_city_memetic.yaml"

PHEROMONE_CMAP = "viridis"   # realized-demand memory tau (distinct from the YlOrRd demand prior)
PHEROMONE_GAMMA = 0.5        # power-norm: tau deposits are heavily skewed
GAP_CMAP = "RdBu_r"          # diverging: red = underserved (gap>0), blue = oversupplied (gap<0)
GAP_THRESHOLD = 0.08         # hide near-balanced edges (fraction of max |gap|) to declutter
TAU_FLOOR = 1.1              # only draw edges that actually accrued deposits (initial_tau=1.0)

# qualitative palette for route systems (serif-friendly, colour-blind aware)
ROUTE_PALETTE = ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE",
                 "#AA3377", "#BBBBBB", "#EE9944", "#000000", "#9970AB"]
TRUNK_COLOR = "#CC3311"      # child routes inherited from parent A's hub (trunk)
FEEDER_COLOR = "#117733"     # child routes merged in from parent B (feeders)


# --------------------------------------------------------------------------------------
# Renderers (pure matplotlib; operate on plain objects so they are stub-testable)
# --------------------------------------------------------------------------------------
def _segments(routes_or_edges, edges=False):
    """Build LineCollection segments [(lon,lat),(lon,lat)] from routes or an edge iterable."""
    segs = []
    it = routes_or_edges if edges else (e for r in routes_or_edges for e in r.path)
    for e in it:
        segs.append([(e.start.lon, e.start.lat), (e.end.lon, e.end.lat)])
    return segs


def _frame(ax, base_img, extent, base_alpha=BASE_ALPHA):
    if base_img is not None:
        ax.imshow(base_img, extent=extent, alpha=base_alpha, zorder=0)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.axis("off")


def _draw_routes(ax, base_img, extent, routes, colors, *, lw=2.4, base_alpha=BASE_ALPHA):
    """Draw each route as a coloured polyline on the faint base."""
    _frame(ax, base_img, extent, base_alpha)
    for route, color in zip(routes, colors):
        segs = _segments([route])
        if segs:
            ax.add_collection(LineCollection(segs, colors=color, linewidths=lw,
                                             zorder=2, capstyle="round"))


def _draw_edges(ax, extent, edges, color, *, lw=3.2, zorder=3):
    segs = _segments(edges, edges=True)
    if segs:
        ax.add_collection(LineCollection(segs, colors=color, linewidths=lw,
                                         zorder=zorder, capstyle="round"))


def _edge_field(ax, base_img, extent, edge_value_pairs, cmap, norm, *,
                lw_lo=0.8, lw_hi=4.8, diverging=False, threshold=0.0, base_alpha=BASE_ALPHA):
    """Colour edges by a scalar value (tau or gap) via a LineCollection; returns the mappable.

    Width and draw-order scale with magnitude so the strongest corridors dominate and faint ones
    recede. `diverging` ranks by |value| (for signed gaps); `threshold` (fraction of max magnitude)
    drops near-zero edges.
    """
    _frame(ax, base_img, extent, base_alpha)
    pairs = list(edge_value_pairs)
    if not pairs:
        from matplotlib.cm import ScalarMappable
        sm = ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        return sm

    vals = np.array([v for _, v in pairs], dtype=float)
    mag = np.abs(vals) if diverging else vals
    mmax = mag.max() or 1.0
    keep = mag >= threshold * mmax
    pairs = [p for p, k in zip(pairs, keep) if k]
    vals = vals[keep]
    mag = mag[keep]
    if not pairs:
        from matplotlib.cm import ScalarMappable
        sm = ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array([])
        return sm

    order = np.argsort(mag)  # weak first so strong corridors render on top
    pairs = [pairs[i] for i in order]
    vals = vals[order]
    t = np.clip(mag[order] / mmax, 0.0, 1.0)
    lws = lw_lo + (lw_hi - lw_lo) * t

    segs = _segments((e for e, _ in pairs), edges=True)
    lc = LineCollection(segs, cmap=cmap, norm=norm, linewidths=lws, zorder=2, capstyle="round")
    lc.set_array(vals)
    ax.add_collection(lc)
    return lc


# ---- norms / accessors over a PheromoneMatrix-like (.tau.items(), .gaps) -------------
def _tau_pairs(ph, floor=TAU_FLOOR):
    return [(e, t) for e, t in ph.tau.items() if t > floor]


def _pheromone_norm(*phs, floor=TAU_FLOOR):
    vmax = 0.0
    for ph in phs:
        for _, t in ph.tau.items():
            if t > floor:
                vmax = max(vmax, t)
    return PowerNorm(PHEROMONE_GAMMA, vmin=floor, vmax=(vmax if vmax > floor else floor + 1.0))


def _gap_pairs(ph):
    return list(ph.gaps.items())


def _gap_norm(*phs):
    m = 0.0
    for ph in phs:
        for _, g in ph.gaps.items():
            m = max(m, abs(g))
    m = m or 1.0
    return TwoSlopeNorm(vcenter=0.0, vmin=-m, vmax=m)


def total_disparity(ph):
    return float(sum(abs(g) for g in ph.gaps.values())) if ph.gaps else float("nan")


def _cbar(fig, mappable, ax, label):
    cb = fig.colorbar(mappable, ax=ax, shrink=0.8, aspect=26, pad=0.02)
    cb.set_label(label, fontsize=10)
    return cb


# --------------------------------------------------------------------------------------
# Figure 1 -- single system: demand prior -> route system -> pheromone memory -> gap
# --------------------------------------------------------------------------------------
def fig_demand_memory_gap(scene, out):
    cg, extent, base = scene["cg"], scene["extent"], scene["base"]
    A, sampler = scene["A"], scene["sampler"]
    stats = scene["stats"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 12.5), constrained_layout=True)
    ax = axes.ravel()

    dnorm = _demand_norm(sampler)
    sc = _scatter_field(ax[0], base, extent, sampler.node_probabilities, dnorm, DEMAND_CMAP)
    ax[0].set_xlim(extent[0], extent[1]); ax[0].set_ylim(extent[2], extent[3]); ax[0].set_aspect("equal")
    _cbar(fig, sc, ax[0], "OD demand prior")
    ax[0].set_title("(a) Demand model (prior)", fontsize=12)

    _draw_routes(ax[1], base, extent, A.routes, [ROUTE_PALETTE[i % len(ROUTE_PALETTE)] for i in range(len(A.routes))])
    ax[1].set_title(f"(b) Route system ({len(A.routes)} routes)", fontsize=12)

    pnorm = _pheromone_norm(A.pheromones)
    lc = _edge_field(ax[2], base, extent, _tau_pairs(A.pheromones), PHEROMONE_CMAP, pnorm)
    _cbar(fig, lc, ax[2], r"pheromone memory $\tau$")
    ax[2].set_title("(c) Realized demand memory ($\\tau$)", fontsize=12)

    gnorm = _gap_norm(A.pheromones)
    lg = _edge_field(ax[3], base, extent, _gap_pairs(A.pheromones), GAP_CMAP, gnorm,
                     diverging=True, threshold=GAP_THRESHOLD)
    _cbar(fig, lg, ax[3], r"demand$-$service gap $\Delta$")
    ax[3].set_title("(d) Demand-service gap ($\\Delta=P-S$)", fontsize=12)

    fig.suptitle(
        f"From demand prior to service gap on one route system   "
        f"($F_{{sim}}={stats['A_fsim']:.0f}$,  $D(R)={stats['A_disp']:.3f}$,  "
        f"completed {stats['A_completed']})", fontsize=14)
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Figure 2 -- topological hub crossover: parent A hub + parent B feeders -> child
# --------------------------------------------------------------------------------------
def fig_hub_crossover(scene, out):
    extent, base = scene["extent"], scene["base"]
    A, B, child = scene["A"], scene["B"], scene["child"]
    hub_ids = scene["hub_edge_ids"]
    trunk, feeders = scene["trunk_routes"], scene["feeder_routes"]
    prov = scene["child_provenance"]
    stats = scene["stats"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 6.0), constrained_layout=True)

    # (a) Parent A: faint routes + the hub edges highlighted, trunk routes solid
    _draw_routes(axes[0], base, extent, A.routes, ["#BBBBBB"] * len(A.routes), lw=1.6)
    _draw_routes(axes[0], None, extent, trunk, [TRUNK_COLOR] * len(trunk), lw=2.6, base_alpha=0.0)
    hub_edges = [e for r in A.routes for e in r.path if getattr(e, "id", id(e)) in hub_ids]
    _draw_edges(axes[0], extent, hub_edges, "#000000", lw=4.2, zorder=4)
    axes[0].set_title(f"(a) Parent A + topological hub\n(top-10% τ = {stats['hub_edges']} edges, "
                      f"{stats['hub_share']:.0%} of demand)", fontsize=11)

    # (b) Parent B: faint routes + feeder donors highlighted
    _draw_routes(axes[1], base, extent, B.routes, ["#BBBBBB"] * len(B.routes), lw=1.6)
    _draw_routes(axes[1], None, extent, feeders, [FEEDER_COLOR] * len(feeders), lw=2.6, base_alpha=0.0)
    axes[1].set_title(f"(b) Parent B + feeder donors\n({len(feeders)} feeders selected)", fontsize=11)

    # (c) Child: trunk (from A) vs feeders (from B) by provenance
    colors = [TRUNK_COLOR if p == "trunk" else FEEDER_COLOR for p in prov]
    _draw_routes(axes[2], base, extent, child.routes, colors, lw=2.6)
    axes[2].set_title(f"(c) Child = trunk(A) + feeders(B)\n($F_{{sim}}={stats['child_fsim']:.0f}$ vs "
                      f"A={stats['A_fsim']:.0f}, B={stats['B_fsim']:.0f})", fontsize=11)

    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([0], [0], color=TRUNK_COLOR, lw=3, label="trunk (parent A hub)"),
                        Line2D([0], [0], color=FEEDER_COLOR, lw=3, label="feeder (parent B)"),
                        Line2D([0], [0], color="#000000", lw=3, label="hub corridor (top-10% τ)")],
               loc="lower center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Topological Hub Crossover — trunk and feeder preservation", fontsize=14)
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Figure 3 -- epigenetic pheromone inheritance (fitness-weighted blend)
# --------------------------------------------------------------------------------------
def fig_pheromone_blend(scene, out):
    extent, base = scene["extent"], scene["base"]
    A, B = scene["A"], scene["B"]
    blend = scene["child_blend_ph"]
    stats = scene["stats"]

    norm = _pheromone_norm(A.pheromones, B.pheromones, blend)
    panels = [("(a) Parent A  $\\tau^A$", A.pheromones, stats["A_fsim"]),
              ("(b) Parent B  $\\tau^B$", B.pheromones, stats["B_fsim"]),
              (f"(c) Child blend  $\\tau^{{child}}=w_A\\tau^A+w_B\\tau^B$", blend, None)]

    fig, axes = plt.subplots(1, 3, figsize=(17, 6.0), constrained_layout=True)
    lc = None
    for ax, (title, ph, cost) in zip(axes, panels):
        lc = _edge_field(ax, base, extent, _tau_pairs(ph), PHEROMONE_CMAP, norm)
        sub = f"\n(cost {cost:.0f})" if cost is not None else f"\n($w_A={stats['wA']:.2f},\\ w_B={stats['wB']:.2f}$)"
        ax.set_title(title + sub, fontsize=11)
    cb = fig.colorbar(lc, ax=axes.ravel().tolist(), shrink=0.8, aspect=32, pad=0.012)
    cb.set_label(r"pheromone intensity $\tau$ (shared scale)")
    fig.suptitle("Epigenetic Inheritance — the fitter parent's demand map dominates the blend",
                 fontsize=14)
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Figure 4 -- demand-service gap change from parents to child
# --------------------------------------------------------------------------------------
def fig_gap_change(scene, out):
    extent, base = scene["extent"], scene["base"]
    A, B, child = scene["A"], scene["B"], scene["child"]
    stats = scene["stats"]

    norm = _gap_norm(A.pheromones, B.pheromones, child.pheromones)
    panels = [("(a) Parent A", A.pheromones, stats["A_disp"]),
              ("(b) Parent B", B.pheromones, stats["B_disp"]),
              ("(c) Child", child.pheromones, stats["child_disp"])]

    fig, axes = plt.subplots(1, 3, figsize=(17, 6.0), constrained_layout=True)
    lg = None
    for ax, (title, ph, disp) in zip(axes, panels):
        lg = _edge_field(ax, base, extent, _gap_pairs(ph), GAP_CMAP, norm,
                         diverging=True, threshold=GAP_THRESHOLD)
        ax.set_title(f"{title}   $D(R)={disp:.3f}$", fontsize=12)
    cb = fig.colorbar(lg, ax=axes.ravel().tolist(), shrink=0.8, aspect=32, pad=0.012)
    cb.set_label(r"demand$-$service gap $\Delta$ (red underserved, blue oversupplied)")
    delta = stats["child_disp"] - 0.5 * (stats["A_disp"] + stats["B_disp"])
    fig.suptitle(f"Demand-service disparity across crossover   "
                 f"(child $D$ {('below' if delta < 0 else 'above')} parent mean by "
                 f"{abs(delta):.3f})", fontsize=14)
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------------------
# Scene construction (lazy heavy imports; 3 toy sims)
# --------------------------------------------------------------------------------------
def build_scene(num_routes=6, seed_a=1, seed_b=2, fleet=None, config_path=TOY_CONFIG):
    """Run parent A, parent B, and the hub-crossover child on the Manhattan toy; assemble a scene."""
    import copy
    import random
    import yaml

    from utils.toy_city import toy_setup_from_yaml
    from utils_simplified import generate_route_system, build_pheromone_matrix
    from utils.travel_graph import TravelGraph
    from utils.jeep import Jeep
    from utils.jeep_system import JeepSystem
    from utils.passenger_generator import PassengerGenerator
    from utils.simulation import Simulation
    from utils.genetic import Chromosome, MemeticAlgorithm
    from utils.local_search import ACOLocalSearch

    toy_city, toy_sampler, toy_config = toy_setup_from_yaml(config_path, verbose=False)
    ctx = toy_city.get_bounds()
    SIM = toy_config["simulation"]
    spt = STABLE_SECONDS_PER_TICK   # forced stable values, not the toy config's sweep values
    ticks = STABLE_NUM_TICKS
    rate = STABLE_SPAWN_RATE
    total_fleet = int(fleet if fleet is not None else SIM.get("total_allocatable_jeeps", 60))

    def run(routes):
        tg = TravelGraph(toy_city, config=toy_config.get("travel_graph", {}), routes=routes)
        jpr = max(1, total_fleet // len(routes))
        jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                      speed=float(SIM.get("jeep_speed_kmh", 40.0)), max_capacity=int(SIM.get("jeep_capacity", 16)),
                      seconds_per_tick=spt)
                 for r in routes for _ in range(jpr)]
        js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=PROD_WEIGHT_TOLERANCE,
                        equidistant_spawn=True)
        pg = PassengerGenerator(tg=tg, sampler=toy_sampler, rate_per_hour=rate,
                                stdev=float(SIM.get("spawn_stdev", 10.0)),
                                speed=float(SIM.get("passenger_speed_kmh", 5.0)), seconds_per_tick=spt)
        cfg = copy.deepcopy(toy_config); cfg["disable_tqdm"] = True
        sim = Simulation(city_query="toy", bounds=ctx, jeep_system=js, passenger_generator=pg, max_ticks=ticks,
                         beta_penalty=float(toy_config.get("BETA_PENALTY", 2.0)),
                         alpha_std_penalty=float(toy_config.get("ALPHA_STD_PENALTY", 0.5)), config=cfg)
        return sim.run()

    def make_chrom(routes, res):
        ph = build_pheromone_matrix(toy_city, res)
        js = res.jeep_system
        alloc = {r: 0 for r in routes}
        if js is not None:
            for j in js.jeeps:
                if j.route in alloc:
                    alloc[j.route] += 1
            ph.gaps = ph.calculate_demand_service_gaps(js)
        c = Chromosome(routes=routes, allocation=alloc, pheromones=ph)
        c.cost = float(res.fitness_score if res.fitness_score is not None else res.score)
        return c, res

    random.seed(seed_a); np.random.seed(seed_a)
    routes_a = generate_route_system(num_routes, toy_city, toy_sampler)
    A, res_a = make_chrom(routes_a, run(routes_a))

    random.seed(seed_b); np.random.seed(seed_b)
    routes_b = generate_route_system(num_routes, toy_city, toy_sampler)
    B, res_b = make_chrom(routes_b, run(routes_b))

    # Topological hub crossover + epigenetic blend (no extra sim for these)
    ma = MemeticAlgorithm(toy_city, ACOLocalSearch(toy_city), target_route_count=num_routes)
    hub_ids = ma._get_hub_edges(A.routes, A.pheromones)
    trunk = [r for r in A.routes if any(getattr(e, "id", id(e)) in hub_ids for e in r.path)]
    child_routes = ma.crossover_topological_hub(A, B)
    blend_ph = ma.inherit_pheromones(A, B)

    # child provenance: trunk if its edge-id set matches a parent-A trunk route, else feeder
    trunk_sigs = [{getattr(e, "id", id(e)) for e in r.path} for r in trunk]
    prov, feeders = [], []
    for cr in child_routes:
        sig = {getattr(e, "id", id(e)) for e in cr.path}
        prov.append("trunk" if any(sig == ts for ts in trunk_sigs) else "feeder")
    feeders = [r for r in B.routes if any(
        {getattr(e, "id", id(e)) for e in r.path} == {getattr(e, "id", id(e)) for e in cr.path}
        for cr, p in zip(child_routes, prov) if p == "feeder")]

    child, res_c = make_chrom(child_routes, run(child_routes))

    base = toy_city.draw(size=BASE_SIZE, only_drivable=False)
    # Hub share = fraction of parent A's route-system pheromone concentrated in the top-10% hub
    # edges. Computed over ROUTE edges via coord-keyed tau.get (route edge objects differ in identity
    # from the matrix's representative edges, but share the same coordinate key).
    route_taus = [A.pheromones.tau.get(e, 0.0) for r in A.routes for e in r.path]
    hub_tau = sum(A.pheromones.tau.get(e, 0.0) for r in A.routes for e in r.path
                  if getattr(e, "id", id(e)) in hub_ids)
    tau_total = sum(route_taus) or 1.0
    total_cost = A.cost + B.cost or 1.0

    stats = {
        "A_fsim": A.cost, "B_fsim": B.cost, "child_fsim": child.cost,
        "A_disp": total_disparity(A.pheromones), "B_disp": total_disparity(B.pheromones),
        "child_disp": total_disparity(child.pheromones),
        "A_completed": res_a.metrics.get("completed_count", "?"),
        "hub_edges": len(hub_ids), "hub_share": hub_tau / tau_total,
        "wA": B.cost / total_cost, "wB": A.cost / total_cost,
    }
    return {
        "cg": toy_city, "ctx": ctx, "extent": _extent(toy_city), "base": base, "sampler": toy_sampler,
        "A": A, "B": B, "child": child, "child_blend_ph": blend_ph,
        "hub_edge_ids": hub_ids, "trunk_routes": trunk, "feeder_routes": feeders,
        "child_provenance": prov, "stats": stats,
    }


# --------------------------------------------------------------------------------------
# Registry + driver
# --------------------------------------------------------------------------------------
FIGS = {
    "memetic_demand_memory_gap": fig_demand_memory_gap,
    "memetic_hub_crossover": fig_hub_crossover,
    "memetic_pheromone_blend": fig_pheromone_blend,
    "memetic_gap_change": fig_gap_change,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", metavar="NAME", help="subset of figure names")
    ap.add_argument("--list", action="store_true", help="list figure names and exit")
    ap.add_argument("--routes", type=int, default=6, help="routes per parent system (toy)")
    args = ap.parse_args()

    if args.list:
        for n in FIGS:
            print(n)
        return

    names = args.only or list(FIGS)
    unknown = [n for n in names if n not in FIGS]
    if unknown:
        raise SystemExit(f"Unknown figure(s): {unknown}\nKnown: {list(FIGS)}")

    set_pub_style()
    os.makedirs(IMG_DIR, exist_ok=True)
    print("[scene] running parent A, parent B, child toy simulations ...")
    scene = build_scene(num_routes=args.routes)
    s = scene["stats"]
    print(f"[scene] F_sim  A={s['A_fsim']:.0f}  B={s['B_fsim']:.0f}  child={s['child_fsim']:.0f}")
    print(f"[scene] D(R)   A={s['A_disp']:.3f}  B={s['B_disp']:.3f}  child={s['child_disp']:.3f}")
    print(f"[scene] hub    {s['hub_edges']} edges = {s['hub_share']:.0%} of tau   weights wA={s['wA']:.2f} wB={s['wB']:.2f}")
    for n in names:
        out = os.path.join(IMG_DIR, f"{n}.png")
        print(f"[fig] {n} -> {FIGS[n](scene, out)}")


if __name__ == "__main__":
    main()
