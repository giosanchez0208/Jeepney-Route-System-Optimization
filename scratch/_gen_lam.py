"""Generator for nb_4_3_6_lamarckian.ipynb (toy + Iligan, isolated changed route + segment)."""
import json

cells = []
def md(s):   cells.append({"cell_type": "markdown", "id": f"md{len(cells)}", "metadata": {}, "source": s.strip("\n")})
def code(s): cells.append({"cell_type": "code", "id": f"c{len(cells)}", "execution_count": None, "metadata": {}, "outputs": [], "source": s.strip("\n")})

md('''
# Chapter 4.3.6 - Lamarckian Operator Mechanics (toy + Iligan)

Shows the three gap-driven local-search operators (Attraction, Repulsion, Tortuosity pruning)
making the mutation **apparent**: each panel isolates the *single changed route* on a faint city
base and highlights the changed segment -- **red = edges removed, green = edges added**.

- **Visual 1a (toy):** the operators on the synthetic Manhattan grid (clear, fast).
- **Visual 1b (Iligan):** the same operators on the real arterial map.
- **Visual 2 (toy):** scatter -- lower demand-service disparity -> better fitness (why disparity
  is the Lamarckian gate).

How firing works: repulsion/pruning fire on almost any system; **attraction only fires when a
system has an underserved corridor (~1 in 6)**, so the loop searches seeds and captures, per
operator, a system where it actually changed the network.

Runtime: toy ~3-4 min, Iligan ~4-8 min (real sims). Figures use the project's native PIL draws.
Outputs: `results_and_discussion/images/lamarckian_operators_toy.png`,
`..._iligan.png`, `gap_vs_fitness.png`.
''')

code('''
import copy, random, time
import numpy as np
import matplotlib.pyplot as plt
import yaml

from utils.toy_city import toy_setup_from_yaml
from utils_simplified import (reuse_citygraph, reuse_ddm, generate_route_system, build_pheromone_matrix,
                              mutate_attraction, mutate_repulsion, mutate_pruning)
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger_generator import PassengerGenerator
from utils.simulation import Simulation

plt.rcParams.update({"font.family": "serif", "font.size": 11, "savefig.dpi": 200})

NUM_ROUTES = 5
OPERATORS = [("Attraction", mutate_attraction), ("Repulsion", mutate_repulsion), ("Tortuosity pruning", mutate_pruning)]

# ---- Toy environment (fast) ----
toy_city, toy_sampler, toy_config = toy_setup_from_yaml("configs/toy_city_configs.yaml", verbose=False)
toy_ctx = toy_city.get_bounds()
print(f"Toy:    {len(toy_city.nodes)} nodes, {len(toy_city.graph)} edges")

# ---- Iligan environment (real map, from pickles) ----
ilg_city = reuse_citygraph("rnd/pkl/profile_p1.pkl")
ilg_ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
ilg_config = yaml.safe_load(open("configs/profile_p1.yaml", encoding="utf-8"))
ilg_ctx = ilg_city.get_bounds()
print(f"Iligan: {len(ilg_city.nodes)} nodes, {len(ilg_city.graph)} edges")
''')

code('''
def build_and_run(city, sampler, config, ctx, routes, rate, ticks, fleet=None):
    """Build + run one in-process simulation for any environment; returns SimulationResult (with jeep_system).
    `fleet` overrides the total jeep count -- keep it small for the Iligan DEMO (the production 470 jeeps
    makes the sim very slow, and the operators only need *some* supply to compute the demand-service gap)."""
    SIM = config["simulation"]
    spt = int(SIM.get("seconds_per_tick", 1))
    tg = TravelGraph(city, config=config.get("travel_graph", {}), routes=routes)
    total = int(fleet if fleet is not None else SIM.get("total_allocatable_jeeps", 25))
    jpr = max(1, total // len(routes))
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                  speed=float(SIM.get("jeep_speed_kmh", 40.0)), max_capacity=int(SIM.get("jeep_capacity", 16)),
                  seconds_per_tick=spt)
             for r in routes for _ in range(jpr)]
    js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=float(SIM.get("weight_tolerance", 50.0)), equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=sampler, rate_per_hour=float(rate), stdev=float(SIM.get("spawn_stdev", 10.0)),
                            speed=float(SIM.get("passenger_speed_kmh", 5.0)), seconds_per_tick=spt)
    cfg = copy.deepcopy(config); cfg["disable_tqdm"] = True
    sim = Simulation(city_query="env", bounds=ctx, jeep_system=js, passenger_generator=pg, max_ticks=int(ticks),
                     beta_penalty=float(config.get("BETA_PENALTY", 2.0)),
                     alpha_std_penalty=float(config.get("ALPHA_STD_PENALTY", 0.5)), config=cfg)
    return sim.run()

def total_disparity(gaps):
    return float(sum(abs(g) for g in gaps.values())) if gaps else float("nan")

def _ek(e):
    return (round(e.start.lon, 6), round(e.start.lat, 6), round(e.end.lon, 6), round(e.end.lat, 6))

def ekeys_of(route):
    return [_ek(e) for e in route.path]

def most_changed_route(before, after):
    """Index of the route with the largest before/after edge difference (the route the operator hit)."""
    best_i, best_d = 0, -1
    for i in range(min(len(before), len(after))):
        d = len(set(ekeys_of(before[i])) ^ set(ekeys_of(after[i])))
        if d > best_d:
            best_d, best_i = d, i
    return best_i, best_d

def draw_route_highlight(city, ctx, route, highlight_keys, base_color, hi_color, size=900, only_drivable=True):
    """Isolated changed route on a faint city base, with the changed segment thickened in hi_color."""
    img = city.draw(size=size, only_drivable=only_drivable).copy()
    img = route.draw(ctx, img, color=base_color, width=4)
    for e in route.path:
        if _ek(e) in highlight_keys:
            img = e.draw(ctx, img, color=hi_color, width=8)
    return img

def capture_operators(city, sampler, config, ctx, rate, ticks, max_seeds, label, do_scatter=False, scatter_n=20):
    """One sim loop: capture a firing system per operator (isolated changed route + removed/added keys),
    and optionally collect (disparity, fitness) scatter points."""
    captured, xs, ys, seed = {}, [], [], 0
    t0 = time.time()
    while (len(captured) < len(OPERATORS) or (do_scatter and len(xs) < scatter_n)) and seed < max_seeds:
        random.seed(seed); np.random.seed(seed)
        rts = generate_route_system(NUM_ROUTES, city, sampler)
        res = build_and_run(city, sampler, config, ctx, rts, rate, ticks)
        ph = build_pheromone_matrix(city, res)
        if do_scatter and len(xs) < scatter_n:
            xs.append(total_disparity(ph.gaps)); ys.append(res.score)
        for name, fn in OPERATORS:
            if name not in captured:
                mut = fn(ph, rts, city, intensity=1.0)
                i, d = most_changed_route(rts, mut)
                if d > 0:
                    rem = set(ekeys_of(rts[i])) - set(ekeys_of(mut[i]))
                    add = set(ekeys_of(mut[i])) - set(ekeys_of(rts[i]))
                    captured[name] = (rts[i], mut[i], rem, add, d)
                    print(f"  [{label} seed {seed:2d}] {name:18s} route {i}: {d} edges changed "
                          f"(removed {len(rem)}, added {len(add)}); completed={res.metrics.get('completed_count')}")
        seed += 1
    print(f"  [{label}] captured {list(captured)} over {seed} seeds in {time.time()-t0:.0f}s")
    missing = [n for n, _ in OPERATORS if n not in captured]
    if missing:
        print(f"  [{label}] did NOT fire within {max_seeds} seeds: {missing} (raise max_seeds / rate)")
    return captured, xs, ys

def capture_operators_retry(city, sampler, config, ctx, rate, ticks, max_sims, retries, label, fleet=None):
    """For EXPENSIVE environments (Iligan): run few sims, but retry each operator's RNG on the SAME
    system+pheromone until it fires (operators sample randomly from the gaps, so re-seeding finds a
    firing move without paying for another costly simulation)."""
    captured = {}
    t0 = time.time()
    for s in range(max_sims):
        if len(captured) == len(OPERATORS):
            break
        random.seed(1000 + s); np.random.seed(1000 + s)
        rts = generate_route_system(NUM_ROUTES, city, sampler)
        res = build_and_run(city, sampler, config, ctx, rts, rate, ticks, fleet)
        ph = build_pheromone_matrix(city, res)
        print(f"  [{label} sim {s}] completed={res.metrics.get('completed_count')}, "
              f"disparity={total_disparity(ph.gaps):.3f} ({time.time()-t0:.0f}s elapsed)")
        for name, fn in OPERATORS:
            if name in captured:
                continue
            for tr in range(retries):
                random.seed(7000 + s * 100 + tr)
                mut = fn(ph, rts, city, intensity=1.0)
                i, d = most_changed_route(rts, mut)
                if d > 0:
                    rem = set(ekeys_of(rts[i])) - set(ekeys_of(mut[i]))
                    add = set(ekeys_of(mut[i])) - set(ekeys_of(rts[i]))
                    captured[name] = (rts[i], mut[i], rem, add, d)
                    print(f"    {name:18s} fired (sim {s}, try {tr}): route {i}, {d} edges "
                          f"(removed {len(rem)}, added {len(add)})")
                    break
    print(f"  [{label}] captured {list(captured)} in {time.time()-t0:.0f}s")
    missing = [n for n, _ in OPERATORS if n not in captured]
    if missing:
        print(f"  [{label}] did NOT fire: {missing} (raise max_sims / retries / rate)")
    return captured

def draw_panels(city, ctx, captured, label, only_drivable=True, size=900):
    fired = [(n, *captured[n]) for n, _ in OPERATORS if n in captured]
    if not fired:
        print(f"[{label}] nothing to draw."); return
    fig, axes = plt.subplots(len(fired), 2, figsize=(11, 5 * len(fired)))
    if len(fired) == 1:
        axes = np.array([axes])
    for row, (name, before, after, rem, add, d) in enumerate(fired):
        axes[row, 0].imshow(draw_route_highlight(city, ctx, before, rem, "#377eb8", "#e41a1c", size, only_drivable))
        axes[row, 0].set_title(f"{name} - before   (red = {len(rem)} edges removed)", fontsize=10); axes[row, 0].axis("off")
        axes[row, 1].imshow(draw_route_highlight(city, ctx, after, add, "#377eb8", "#2ca02c", size, only_drivable))
        axes[row, 1].set_title(f"{name} - after   (green = {len(add)} edges added)", fontsize=10); axes[row, 1].axis("off")
    fig.suptitle(f"Lamarckian operators on the {label} map - isolated changed route + segment",
                 fontweight="bold", fontsize=13)
    plt.tight_layout()
    out = f"results_and_discussion/images/lamarckian_operators_{label.lower()}.png"
    plt.savefig(out, bbox_inches="tight"); plt.show()
    print(f"saved {out}")
''')

code('''
# ============ Visual 1a + Visual 2 : TOY (fast; also collects the disparity-vs-fitness scatter) ============
toy_captured, xs, ys = capture_operators(toy_city, toy_sampler, toy_config, toy_ctx,
                                         rate=600.0, ticks=1500, max_seeds=45,
                                         label="Toy", do_scatter=True, scatter_n=20)
draw_panels(toy_city, toy_ctx, toy_captured, label="Toy", only_drivable=True, size=900)
''')

code('''
# ---- Visual 2: demand-service disparity vs simulation fitness (toy) ----
xs = np.array(xs); ys = np.array(ys); mask = np.isfinite(xs) & np.isfinite(ys)
r = float(np.corrcoef(xs[mask], ys[mask])[0, 1]) if mask.sum() > 1 else float("nan")
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(xs[mask], ys[mask], alpha=0.75, color="#377eb8", edgecolor="white")
ax.set_xlabel("Total demand-service disparity  D(R) = sum |P - S|")
ax.set_ylabel("Simulation fitness  F_sim  (lower is better)")
ax.set_title(f"Lower disparity -> better fitness   (Pearson r = {r:.2f})", fontweight="bold")
ax.grid(alpha=0.3); plt.tight_layout()
plt.savefig("results_and_discussion/images/gap_vs_fitness.png", bbox_inches="tight"); plt.show()
print(""); print(f"Pearson r (disparity vs fitness) over {int(mask.sum())} toy systems = {r:.3f}")
''')

code('''
# ============ Visual 1b : ILIGAN (real map; each sim is ~80-120s, so few sims + operator retries) ============
# We only need demand pheromones for the operators (not high completion), then retry each operator's
# RNG on the same system until it fires -- far cheaper than a fresh sim per attempt.
ilg_captured = capture_operators_retry(ilg_city, ilg_ddm, ilg_config, ilg_ctx,
                                       rate=600.0, ticks=200, max_sims=2, retries=15, label="Iligan", fleet=50)
draw_panels(ilg_city, ilg_ctx, ilg_captured, label="Iligan", only_drivable=True, size=1100)
# Note: repulsion (redundancy removal) may not fire on the LIGHT demo fleet -- a sparse fleet
# under-serves the whole network, so no corridor is oversupplied. Attraction and pruning fire.
# To exercise repulsion on Iligan too, raise fleet (e.g. 200+), at the cost of slower sims.
''')

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}
with open("nb_4_3_6_lamarckian.ipynb", "w", encoding="utf-8") as f:
    f.write(json.dumps(nb, indent=1))
print("wrote nb_4_3_6_lamarckian.ipynb with", len(cells), "cells")
json.load(open("nb_4_3_6_lamarckian.ipynb", encoding="utf-8"))
print("JSON valid")
