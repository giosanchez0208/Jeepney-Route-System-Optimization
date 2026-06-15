"""showcase_optimization.py -- defense-preview visuals of ONE memetic optimization loop.

Stitches the pieces we already have (toy simulation + its draw(), utils_simplified operators,
fig_memetic renderers) into a cohesive 7-beat story for the panel:

  1  simulate_with_frames   jeeps + passengers moving across the city (GIF, every Nth tick)
  2  population route systems + simulated fitness  (no per-system video needed)
  3  realized pheromone (demand-memory) map per system
  4  demand-service gap per system
  5  topological hub crossover: parents -> child   (memetic recombination)
  6  Lamarckian local search with bumped intensity: before -> after   (the "mutation")
  7  re-simulate -> fitness bar (best parent -> crossover child -> + local search)

Default config is SMOKE (tiny, fast) so the whole loop runs in seconds for a sanity check; a groupmate
flips to FULL (`make_config(smoke=False)` or `--full`) on a stronger machine for slide-quality output.

Heavy deps (the simulator, pyrosm-backed utils) are imported lazily inside the functions, so this
module imports anywhere and its tiny test can poke the cheap pieces. Renderers are reused from
fig_memetic so the showcase matches the thesis figures exactly.

    python showcase_optimization.py            # smoke render of all 7 beats -> outputs/defense_showcase/
    python showcase_optimization.py --full      # slide-quality (slow; for the groupmate's machine)
"""
from __future__ import annotations

import os

import numpy as np

# fig_memetic sets matplotlib Agg on import and exposes the exact renderers/primitives the thesis uses.
from fig_memetic import (
    _draw_routes, _edge_field, _tau_pairs, _gap_pairs, _pheromone_norm, _gap_norm, total_disparity,
    fig_hub_crossover, fig_pheromone_blend,
    ROUTE_PALETTE, PHEROMONE_CMAP, GAP_CMAP, GAP_THRESHOLD,
    STABLE_SECONDS_PER_TICK, PROD_WEIGHT_TOLERANCE,
)
from fig_environment import set_pub_style, _extent, BASE_SIZE
import matplotlib.pyplot as plt

TRUNK_RED = "#CC3311"
FEEDER_GREEN = "#117733"


# ======================================================================================
# Config
# ======================================================================================
def make_config(smoke: bool = True, city: str = "toy", **overrides) -> dict:
    """Knobs for the whole showcase. SMOKE = tiny + fast; flip to full for slide quality.

    city="toy"    -> Manhattan grid (clear mechanics; a fresh short optimization drives beat 7).
    city="iligan" -> real Iligan road network from cached pickles (realism; beat 7 renders the existing
                     production-run telemetry, since a fresh Iligan optimization is the multi-hour run).
    """
    # dpi/sizes tuned for slides: crisp when projected, one clean visual per beat
    common = dict(smoke=smoke, city=city, gif_ms=90, mut_intensity=5.0, dpi=160, seed0=1)
    if city == "toy":
        cfg = dict(
            config_path="configs/toy_city_memetic.yaml",
            out_dir="outputs/defense_showcase",
            num_routes=4 if smoke else 6,
            population=3 if smoke else 5,
            fleet=24 if smoke else 60,
            sim_ticks=90 if smoke else 540,            # 540 = production horizon (90 min @ 10s)
            spawn_rate=150.0 if smoke else 600.0,      # 600 = production demand
            frame_stride=6 if smoke else 3,            # capture every Nth tick (the "speed-up")
            frame_size=460 if smoke else 900,
            base_only_drivable=False,                  # the toy grid is the whole network
            convergence_mode="fresh",                  # run a short real optimization for the curve
            preview_generations=6 if smoke else 20,
            preview_population=4 if smoke else 16,
        )
    elif city == "iligan":
        cfg = dict(
            config_path="configs/profile_p1.yaml",
            cg_pkl="rnd/pkl/profile_p1.pkl",           # cached CityGraph (no OSM re-extraction)
            ddm_pkl="rnd/pkl/ddm_8am.pkl",             # cached 08:00 demand sampler
            out_dir="outputs/defense_showcase_iligan",
            num_routes=6 if smoke else 12,
            population=3 if smoke else 4,
            fleet=120 if smoke else 400,
            sim_ticks=90 if smoke else 540,
            spawn_rate=300.0 if smoke else 600.0,
            frame_stride=6 if smoke else 3,
            frame_size=640 if smoke else 1200,         # larger so the real-city sim stays crisp on a slide
            base_only_drivable=True,                   # arterial skeleton: far less clutter than every road
            convergence_mode="existing",               # render the real production run's convergence
            convergence_root="final_runs_2",           # the corrected 30-generation production telemetry
        )
    else:
        raise ValueError(f"unknown city {city!r} (expected 'toy' or 'iligan')")
    cfg.update(common)
    cfg.update(overrides)
    return cfg


def _p(config: dict, name: str) -> str:
    return os.path.join(config["out_dir"], name)


# ======================================================================================
# Environment + simulation (lazy heavy imports)
# ======================================================================================
def setup_env(config: dict) -> dict:
    """City + sampler + faint base map; called once and threaded through every beat. Toy builds from
    YAML; Iligan reuses the cached CityGraph / DDM pickles so there is no OSM re-extraction."""
    set_pub_style()
    if config["city"] == "iligan":
        import yaml
        from utils_simplified import reuse_citygraph, reuse_ddm
        city = reuse_citygraph(config["cg_pkl"])
        sampler = reuse_ddm(config["ddm_pkl"])
        with open(config["config_path"], encoding="utf-8") as f:
            full_cfg = yaml.safe_load(f)
    else:
        from utils.toy_city import toy_setup_from_yaml
        city, sampler, full_cfg = toy_setup_from_yaml(config["config_path"], verbose=False)
    return {
        "city": city, "sampler": sampler, "toy_config": full_cfg,
        "ctx": city.get_bounds(), "extent": _extent(city),
        "base": city.draw(size=BASE_SIZE, only_drivable=config.get("base_only_drivable", False)),
        "sim": full_cfg.get("simulation", {}),
    }


def _build_sim(env: dict, routes: list, config: dict):
    """Construct a Simulation on `routes` at the configured (smoke/full) operating point."""
    import copy
    from utils.travel_graph import TravelGraph
    from utils.jeep import Jeep
    from utils.jeep_system import JeepSystem
    from utils.passenger_generator import PassengerGenerator
    from utils.simulation import Simulation

    city, sampler, toy_config, ctx = env["city"], env["sampler"], env["toy_config"], env["ctx"]
    SIM = env["sim"]
    spt = STABLE_SECONDS_PER_TICK
    tg = TravelGraph(city, config=toy_config.get("travel_graph", {}), routes=routes)
    jpr = max(1, int(config["fleet"]) // len(routes))
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                  speed=float(SIM.get("jeep_speed_kmh", 40.0)),
                  max_capacity=int(SIM.get("jeep_capacity", 16)), seconds_per_tick=spt)
             for r in routes for _ in range(jpr)]
    js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=PROD_WEIGHT_TOLERANCE,
                    equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=sampler, rate_per_hour=float(config["spawn_rate"]),
                            stdev=float(SIM.get("spawn_stdev", 10.0)),
                            speed=float(SIM.get("passenger_speed_kmh", 5.0)), seconds_per_tick=spt)
    cfg = copy.deepcopy(toy_config); cfg["disable_tqdm"] = True
    return Simulation(city_query="toy", bounds=ctx, jeep_system=js, passenger_generator=pg,
                      max_ticks=int(config["sim_ticks"]),
                      beta_penalty=float(toy_config.get("BETA_PENALTY", 2.0)),
                      alpha_std_penalty=float(toy_config.get("ALPHA_STD_PENALTY", 0.5)), config=cfg)


def run_sim(env: dict, routes: list, config: dict):
    """Run a sim to completion; return its SimulationResult."""
    return _build_sim(env, routes, config).run()


def simulate_with_frames(env: dict, routes: list, config: dict):
    """Run a sim, capturing a frame every `frame_stride` ticks: jeeps + passengers over the routes,
    with the live tick/headcount dashboard. Returns (result, [PIL frames])."""
    sim = _build_sim(env, routes, config)
    ctx = env["ctx"]
    stride = max(1, int(config["frame_stride"]))
    rbase = env["city"].draw(size=int(config["frame_size"]),
                             only_drivable=config.get("base_only_drivable", False)).convert("RGBA")
    for i, r in enumerate(routes):  # faint routes so the jeeps are seen travelling along them
        rbase = r.draw(ctx, rbase, color=ROUTE_PALETTE[i % len(ROUTE_PALETTE)], width=3)
    frames = []
    while not sim.is_complete:
        sim.update()
        if sim.current_tick % stride == 0 or sim.is_complete:
            f = sim.draw(ctx, rbase.copy(), draw_jeeps=True, draw_passengers=True)
            frames.append(sim.draw_dashboard(f))
    return sim.evaluate_fitness(), frames


def save_gif(frames: list, out: str, ms: int = 80) -> str:
    if not frames:
        raise ValueError("no frames to write")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rgb = [f.convert("RGB") for f in frames]
    rgb[0].save(out, save_all=True, append_images=rgb[1:], duration=int(ms), loop=0)
    return out


def _make_chrom(env: dict, routes: list, res):
    """Wrap a simulated route system as a Chromosome carrying pheromone memory + demand-service gaps."""
    from utils.genetic import Chromosome
    from utils_simplified import build_pheromone_matrix
    ph = build_pheromone_matrix(env["city"], res)
    alloc = {r: 0 for r in routes}
    js = getattr(res, "jeep_system", None)
    if js is not None:
        for j in js.jeeps:
            if j.route in alloc:
                alloc[j.route] += 1
        ph.gaps = ph.calculate_demand_service_gaps(js)
    c = Chromosome(routes=routes, allocation=alloc, pheromones=ph)
    c.cost = float(res.fitness_score)
    return c


# ======================================================================================
# Beat 2-4: population + its demand-memory / gap signals
# ======================================================================================
def build_population(env: dict, config: dict) -> list:
    """Generate `population` route systems on different seeds, simulate each, return members sorted
    by fitness. Each member carries its routes, Chromosome (pheromone + gaps), and headline numbers."""
    import random
    from utils_simplified import generate_route_system
    members = []
    for k in range(int(config["population"])):
        seed = int(config["seed0"]) + k
        random.seed(seed); np.random.seed(seed)
        routes = generate_route_system(int(config["num_routes"]), env["city"], env["sampler"])
        res = run_sim(env, routes, config)
        chrom = _make_chrom(env, routes, res)
        members.append({
            "seed": seed, "routes": routes, "chrom": chrom, "res": res, "fsim": chrom.cost,
            "completed": res.metrics.get("completed_count", 0),
            "disparity": total_disparity(chrom.pheromones),
        })
    members.sort(key=lambda m: m["fsim"])
    return members


def render_population_grid(env: dict, members: list, kind: str, out: str, dpi: int = 130) -> str:
    """One grid over the population. kind in {'routes','pheromone','gap'}."""
    extent, base = env["extent"], env["base"]
    n = len(members)
    cols = min(n, 4) or 1
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.3 * cols, 4.5 * rows),
                             constrained_layout=True, squeeze=False)
    axes = axes.ravel()
    norm = None
    if kind == "pheromone":
        norm = _pheromone_norm(*[m["chrom"].pheromones for m in members])
    elif kind == "gap":
        norm = _gap_norm(*[m["chrom"].pheromones for m in members])

    mappable = None
    for i, m in enumerate(members):
        ax, ph = axes[i], m["chrom"].pheromones
        if kind == "routes":
            _draw_routes(ax, base, extent, m["routes"],
                         [ROUTE_PALETTE[j % len(ROUTE_PALETTE)] for j in range(len(m["routes"]))])
            tag = "  (best)" if i == 0 else ""
            ax.set_title(f"system {i + 1}{tag}\n$F_{{sim}}={m['fsim']:.0f}$,  completed {m['completed']}",
                         fontsize=11)
        elif kind == "pheromone":
            mappable = _edge_field(ax, base, extent, _tau_pairs(ph), PHEROMONE_CMAP, norm)
            ax.set_title(f"system {i + 1}: demand memory $\\tau$", fontsize=11)
        else:
            mappable = _edge_field(ax, base, extent, _gap_pairs(ph), GAP_CMAP, norm,
                                   diverging=True, threshold=GAP_THRESHOLD)
            ax.set_title(f"system {i + 1}: $D(R)={m['disparity']:.3f}$", fontsize=11)
    for j in range(n, len(axes)):
        axes[j].axis("off")

    if mappable is not None:
        cb = fig.colorbar(mappable, ax=list(axes), shrink=0.7, aspect=30, pad=0.01)
        cb.set_label(r"pheromone memory $\tau$" if kind == "pheromone"
                     else r"demand$-$service gap $\Delta$ (red underserved, blue oversupplied)")
    titles = {
        "routes": "Generated candidate route systems and their simulated fitness",
        "pheromone": "Realized demand memory (pheromone $\\tau$) left by each candidate",
        "gap": "Demand-service gap of each candidate (red underserved, blue oversupplied)",
    }
    fig.suptitle(titles[kind], fontsize=14, fontweight="bold")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out


# ======================================================================================
# Beat 5: topological hub crossover  (reuses fig_memetic's scene + renderers)
# ======================================================================================
def build_crossover_scene(env: dict, members: list, config: dict) -> dict:
    """Best two population members become parents; assemble the fig_memetic-compatible crossover
    scene (hub, trunk, feeders, child, fitness-weighted pheromone blend) + simulate the child.

    Both parent orderings are tried (each parent's hub can seed the trunk) and the lower-cost child is
    kept -- exactly the selection the GA would apply, and it spares the slide a needlessly worse child.
    """
    from utils.genetic import MemeticAlgorithm
    from utils.local_search import ACOLocalSearch
    city = env["city"]
    ma = MemeticAlgorithm(city, ACOLocalSearch(city), target_route_count=int(config["num_routes"]))

    def assemble(A, B):
        hub_ids = ma._get_hub_edges(A.routes, A.pheromones)
        trunk = [r for r in A.routes if any(_eid(e) in hub_ids for e in r.path)]
        child_routes = ma.crossover_topological_hub(A, B)
        blend_ph = ma.inherit_pheromones(A, B)
        trunk_sigs = [_route_sig(r) for r in trunk]
        prov = ["trunk" if _route_sig(cr) in trunk_sigs else "feeder" for cr in child_routes]
        child_sigs = [_route_sig(cr) for cr, p in zip(child_routes, prov) if p == "feeder"]
        feeders = [r for r in B.routes if _route_sig(r) in child_sigs]
        child = _make_chrom(env, child_routes, run_sim(env, child_routes, config))
        hub_tau = sum(A.pheromones.tau.get(e, 0.0) for r in A.routes for e in r.path if _eid(e) in hub_ids)
        tau_total = sum(A.pheromones.tau.get(e, 0.0) for r in A.routes for e in r.path) or 1.0
        total_cost = (A.cost + B.cost) or 1.0
        stats = {
            "A_fsim": A.cost, "B_fsim": B.cost, "child_fsim": child.cost,
            "A_disp": total_disparity(A.pheromones), "B_disp": total_disparity(B.pheromones),
            "child_disp": total_disparity(child.pheromones),
            "A_completed": "?", "hub_edges": len(hub_ids), "hub_share": hub_tau / tau_total,
            "wA": B.cost / total_cost, "wB": A.cost / total_cost,
        }
        return {
            "cg": city, "ctx": env["ctx"], "extent": env["extent"], "base": env["base"], "sampler": env["sampler"],
            "A": A, "B": B, "child": child, "child_blend_ph": blend_ph,
            "hub_edge_ids": hub_ids, "trunk_routes": trunk, "feeder_routes": feeders,
            "child_provenance": prov, "stats": stats,
        }

    A0, B0 = members[0]["chrom"], members[1]["chrom"]
    s1 = assemble(A0, B0)
    s2 = assemble(B0, A0)
    return s1 if s1["child"].cost <= s2["child"].cost else s2


# ======================================================================================
# Beat 6: Lamarckian local search ("mutation") with bumped intensity
# ======================================================================================
def _eid(e):
    return getattr(e, "id", id(e))


def _route_sig(r):
    return frozenset(_eid(e) for e in r.path)


def _edge_id_set(routes):
    return {_eid(e) for r in routes for e in r.path}


def _n_edges_changed(before, after):
    a, b = _edge_id_set(before), _edge_id_set(after)
    return len(a ^ b)


def _changed_route_idx(a, b):
    bsigs = [_route_sig(r) for r in b]
    return [i for i, r in enumerate(a) if _route_sig(r) not in bsigs]


def apply_obvious_mutation(env: dict, routes: list, pheromones, config: dict, base_cost=None) -> dict:
    """Run each of the three local-search operators at bumped `mut_intensity`, re-simulate the ones
    that actually changed the topology, and keep the lowest-cost result. Bumping intensity is the
    user-requested fix so the structural change is unmistakable on a slide (vanilla intensity barely
    perturbs the toy systems)."""
    from utils_simplified import mutate_attraction, mutate_repulsion, mutate_pruning
    city, intensity = env["city"], float(config["mut_intensity"])
    if not getattr(pheromones, "gaps", None):
        try:
            pheromones.gaps = pheromones.calculate_demand_service_gaps(routes)
        except Exception:
            pheromones.gaps = {}

    ops = [("Spatial Attraction", mutate_attraction),
           ("Redundancy Repulsion", mutate_repulsion),
           ("Tortuosity Pruning", mutate_pruning)]
    trials = []
    for name, fn in ops:
        after = fn(pheromones, routes, city, intensity=intensity)
        nch = _n_edges_changed(routes, after)
        if nch == 0:
            continue
        cost = float(run_sim(env, after, config).fitness_score)
        trials.append({"op": name, "after": after, "n_changed": nch, "after_cost": cost})

    if not trials:
        return {"changed": False, "before": routes, "after": routes, "op": None,
                "n_changed": 0, "after_cost": base_cost}
    trials.sort(key=lambda t: t["after_cost"])  # prefer the strongest fitness improvement
    best = trials[0]
    best.update({"changed": True, "before": routes, "trials": trials})
    return best


def render_mutation(env: dict, mut: dict, out: str, dpi: int = 130) -> str:
    """Before vs after the local-search move, the touched routes highlighted (red removed-from, green
    new geometry) so the panel sees exactly what the operator did."""
    extent, base = env["extent"], env["base"]
    before, after = mut["before"], mut["after"]
    ch_before = _changed_route_idx(before, after)
    ch_after = _changed_route_idx(after, before)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.8), constrained_layout=True)
    _draw_routes(axes[0], base, extent, before, ["#C8C8C8"] * len(before), lw=1.7)
    if ch_before:
        _draw_routes(axes[0], None, extent, [before[i] for i in ch_before],
                     [TRUNK_RED] * len(ch_before), lw=3.0, base_alpha=0.0)
    axes[0].set_title("before", fontsize=12)

    _draw_routes(axes[1], base, extent, after, ["#C8C8C8"] * len(after), lw=1.7)
    if ch_after:
        _draw_routes(axes[1], None, extent, [after[i] for i in ch_after],
                     [FEEDER_GREEN] * len(ch_after), lw=3.0, base_alpha=0.0)
    cost_tag = ""
    if mut.get("after_cost") is not None and mut.get("base_cost") is not None:
        cost_tag = f"   ($F_{{sim}}$ {mut['base_cost']:.0f} $\\to$ {mut['after_cost']:.0f})"
    axes[1].set_title("after", fontsize=12)

    fig.suptitle(f"Lamarckian local search — {mut['op']} at bumped intensity "
                 f"({mut['n_changed']} edges changed){cost_tag}", fontsize=13, fontweight="bold")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fig.savefig(out, dpi=dpi)
    plt.close(fig)
    return out


# ======================================================================================
# Beat 7: a SHORT real optimization -> honest convergence curve (fitness genuinely descending)
# ======================================================================================
def run_short_optimization(config: dict) -> str:
    """Run a SHORT real toy optimization and return its telemetry run_dir.

    Launched via subprocess because run_toy_optimization.py is a multiprocessing-safe __main__ script;
    spinning up the optimizer's ProcessPool *inside* a notebook is fragile on Windows. A single
    stochastic crossover child is not representative (it can be worse than its parents) -- the
    optimizer's elitism + selection over a few generations is what actually drives fitness down, and
    that is the honest thing to put in front of the panel.
    """
    import subprocess
    import sys
    from fig_optimization import find_latest_run
    repo = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, os.path.join(repo, "run_toy_optimization.py"),
           "--routes", str(int(config["num_routes"])),
           "--generations", str(int(config["preview_generations"])),
           "--population", str(int(config["preview_population"])),
           "--fleet", str(int(config["fleet"])),
           "--num-ticks", str(int(config["sim_ticks"])),
           "--spawn", str(float(config["spawn_rate"]))]
    subprocess.run(cmd, check=True, cwd=repo)
    run_dir = find_latest_run(os.path.join(repo, "outputs"))
    if run_dir is None:
        raise RuntimeError("optimization produced no run directory under outputs/")
    return run_dir


def _richest_history_run(root: str):
    """Run directory under `root` whose history.csv has the most data rows (handles spaces in the path
    and telemetry that omits snapshots/, unlike fig_optimization.find_latest_run)."""
    import glob
    best = None
    for hp in glob.glob(os.path.join(root, "**", "history.csv"), recursive=True):
        try:
            with open(hp, encoding="utf-8") as f:
                rows = sum(1 for _ in f) - 1
        except OSError:
            continue
        if rows > 0 and (best is None or rows > best[0]):
            best = (rows, os.path.dirname(hp))
    return best[1] if best else None


def render_convergence(run_dir: str, config: dict) -> dict:
    """Convergence curve (+ evolution storyboard) from a telemetry run_dir, via the existing
    fig_optimization renderers the thesis already uses."""
    from fig_optimization import load_run, fig_opt_convergence, fig_opt_evolution
    run = load_run(run_dir)
    out = {"07_convergence": fig_opt_convergence(run, _p(config, "07_convergence.png"))}
    try:
        out["07b_evolution"] = fig_opt_evolution(run, _p(config, "07b_evolution.png"))
    except Exception as exc:  # storyboard needs per-gen snapshots; tolerate their absence on a tiny run
        print(f"[showcase] evolution storyboard skipped: {exc}")
    return out


# ======================================================================================
# Orchestrator (CLI + tiny test entry)
# ======================================================================================
def run_all(config: dict) -> dict:
    """Render all seven beats to config['out_dir']; return {beat: path}."""
    os.makedirs(config["out_dir"], exist_ok=True)
    dpi = int(config["dpi"])
    env = setup_env(config)
    out = {}

    members = build_population(env, config)
    out["02_route_systems"] = render_population_grid(env, members, "routes", _p(config, "02_route_systems.png"), dpi)
    out["03_pheromones"] = render_population_grid(env, members, "pheromone", _p(config, "03_pheromones.png"), dpi)
    out["04_demand_service_gaps"] = render_population_grid(env, members, "gap", _p(config, "04_demand_service_gaps.png"), dpi)

    _, frames = simulate_with_frames(env, members[0]["routes"], config)
    out["01_simulation"] = save_gif(frames, _p(config, "01_simulation.gif"), config["gif_ms"])

    scene = build_crossover_scene(env, members, config)
    out["05_hub_crossover"] = fig_hub_crossover(scene, _p(config, "05_hub_crossover.png"))
    out["05b_pheromone_blend"] = fig_pheromone_blend(scene, _p(config, "05b_pheromone_blend.png"))

    child = scene["child"]
    mut = apply_obvious_mutation(env, child.routes, child.pheromones, config, base_cost=child.cost)
    mut["base_cost"] = child.cost
    out["06_local_search"] = render_mutation(env, mut, _p(config, "06_local_search.png"), dpi)

    out.update(run_beat7(config))   # fresh short optimization (toy) or real production telemetry (iligan)
    return out


def run_beat7(config: dict) -> dict:
    """Beat 7 dispatch. toy -> a fresh short optimization; iligan -> render the existing production-run
    telemetry (a fresh Iligan optimization is the multi-hour run, not a preview)."""
    if config.get("convergence_mode") == "existing":
        run_dir = _richest_history_run(config.get("convergence_root", "outputs"))
        if not run_dir:
            print(f"[showcase] no telemetry with a populated history.csv under "
                  f"{config.get('convergence_root')!r}; skipping beat 7")
            return {}
        return render_convergence(run_dir, config)
    return render_convergence(run_short_optimization(config), config)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Defense-preview optimization showcase.")
    ap.add_argument("--city", choices=["toy", "iligan"], default="toy", help="which map (default toy)")
    ap.add_argument("--full", action="store_true", help="slide-quality full render (slow)")
    ap.add_argument("--out", default=None, help="output directory override")
    args = ap.parse_args()
    cfg = make_config(smoke=not args.full, city=args.city)
    if args.out:
        cfg["out_dir"] = args.out
    print(f"[showcase] {args.city.upper()} {'FULL' if args.full else 'SMOKE'}  ticks={cfg['sim_ticks']} "
          f"pop={cfg['population']} routes={cfg['num_routes']} -> {cfg['out_dir']}")
    for beat, path in run_all(cfg).items():
        print(f"  {beat:24s} {path}")


if __name__ == "__main__":
    main()
