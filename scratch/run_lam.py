import copy, random, time, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from pathlib import Path

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

def build_and_run(city, sampler, config, ctx, routes, rate, ticks, fleet=None):
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
    best_i, best_d = 0, -1
    for i in range(min(len(before), len(after))):
        d = len(set(ekeys_of(before[i])) ^ set(ekeys_of(after[i])))
        if d > best_d:
            best_d, best_i = d, i
    return best_i, best_d

def draw_route_highlight(city, ctx, route, highlight_keys, base_color, hi_color, size=900, only_drivable=True):
    img = city.draw(size=size, only_drivable=only_drivable).copy()
    img = route.draw(ctx, img, color=base_color, width=4)
    for e in route.path:
        if _ek(e) in highlight_keys:
            img = e.draw(ctx, img, color=hi_color, width=8)
    return img

def capture_operators(city, sampler, config, ctx, rate, ticks, max_seeds, label, do_scatter=False, scatter_n=20):
    captured, xs, ys, seed = {}, [], [], 0
    exemplar_ph, best_disp = None, -1.0
    t0 = time.time()
    while (len(captured) < len(OPERATORS) or (do_scatter and len(xs) < scatter_n)) and seed < max_seeds:
        random.seed(seed); np.random.seed(seed)
        rts = generate_route_system(NUM_ROUTES, city, sampler)
        res = build_and_run(city, sampler, config, ctx, rts, rate, ticks)
        ph = build_pheromone_matrix(city, res)
        disp = total_disparity(ph.gaps)
        if do_scatter and len(xs) < scatter_n:
            xs.append(disp); ys.append(res.score)
        if np.isfinite(disp) and disp > best_disp:
            best_disp, exemplar_ph = disp, ph
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
    return captured, xs, ys, exemplar_ph

def capture_operators_retry(city, sampler, config, ctx, rate, ticks, max_sims, retries, label, fleet=None):
    captured = {}
    exemplar_ph, best_disp = None, -1.0
    t0 = time.time()
    for s in range(max_sims):
        if len(captured) == len(OPERATORS):
            break
        random.seed(1000 + s); np.random.seed(1000 + s)
        rts = generate_route_system(NUM_ROUTES, city, sampler)
        res = build_and_run(city, sampler, config, ctx, rts, rate, ticks, fleet)
        ph = build_pheromone_matrix(city, res)
        disp = total_disparity(ph.gaps)
        if np.isfinite(disp) and disp > best_disp:
            best_disp, exemplar_ph = disp, ph
        print(f"  [{label} sim {s}] completed={res.metrics.get('completed_count')}, "
              f"disparity={disp:.3f} ({time.time()-t0:.0f}s elapsed)")
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
    return captured, exemplar_ph

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
    plt.savefig(out, bbox_inches="tight"); plt.close(fig)
    print(f"saved {out}")

print("[Step 1] Running Toy simulations...")
toy_captured, xs, ys, toy_ph = capture_operators(toy_city, toy_sampler, toy_config, toy_ctx,
                                                 rate=600.0, ticks=1500, max_seeds=45,
                                                 label="Toy", do_scatter=True, scatter_n=20)
draw_panels(toy_city, toy_ctx, toy_captured, label="Toy", only_drivable=True, size=900)

print("[Step 2] Plotting Scatter...")
xs = np.array(xs); ys = np.array(ys); mask = np.isfinite(xs) & np.isfinite(ys)
r = float(np.corrcoef(xs[mask], ys[mask])[0, 1]) if mask.sum() > 1 else float("nan")
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(xs[mask], ys[mask], alpha=0.75, color="#377eb8", edgecolor="white")
ax.set_xlabel("Total demand-service disparity  D(R) = sum |P - S|")
ax.set_ylabel("Simulation fitness  F_sim  (lower is better)")
ax.set_title(f"Lower disparity -> better fitness   (Pearson r = {r:.2f})", fontweight="bold")
ax.grid(alpha=0.3); plt.tight_layout()
plt.savefig("results_and_discussion/images/gap_vs_fitness.png", bbox_inches="tight"); plt.close(fig)
print(f"saved gap_vs_fitness.png (r={r:.3f})")

print("[Step 3] Running Iligan simulations...")
ilg_captured, ilg_ph = capture_operators_retry(ilg_city, ilg_ddm, ilg_config, ilg_ctx,
                                               rate=600.0, ticks=200, max_sims=2, retries=15, label="Iligan", fleet=50)
draw_panels(ilg_city, ilg_ctx, ilg_captured, label="Iligan", only_drivable=True, size=1100)

print("[Step 4] Plotting Gap Field...")
from matplotlib.patches import Patch
GAP_THRESHOLD = 0.1

def draw_gap_panel(ax, city, ctx, ph, label, size, only_drivable=True, threshold=GAP_THRESHOLD):
    if ph is None or not getattr(ph, "gaps", None):
        ax.set_title(f"{label}: no gap data available"); ax.axis("off"); return
    base = city.draw(size=size, only_drivable=only_drivable).copy()
    ax.imshow(ph.draw_gaps(ctx, base, threshold=threshold))
    ax.set_title(f"Demand-service gap field - {label}   (D = {total_disparity(ph.gaps):.3f})", fontsize=11)
    ax.axis("off")

panels = [("Toy", toy_city, toy_ctx, toy_ph, 900)]
if ilg_ph is not None:
    panels.append(("Iligan", ilg_city, ilg_ctx, ilg_ph, 1100))

fig, axes = plt.subplots(1, len(panels), figsize=(6 * len(panels), 6.5))
if len(panels) == 1:
    axes = [axes]
for ax, (label, c, ctx, ph, sz) in zip(axes, panels):
    draw_gap_panel(ax, c, ctx, ph, label, sz)
fig.legend(handles=[Patch(facecolor="#ff0000", label="underserved  (demand share > supply)  -> attraction"),
                    Patch(facecolor="#0000ff", label="oversupplied  (supply share > demand)  -> repulsion")],
           loc="lower center", ncol=2, frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("Signed demand-service gap - the pheromone signal that gates / steers the Lamarckian operators",
             fontweight="bold", fontsize=13)
plt.tight_layout(rect=(0, 0.03, 1, 1))
out = "results_and_discussion/images/demand_service_gap_field.png"
plt.savefig(out, bbox_inches="tight"); plt.close(fig)
print(f"saved {out}")
print("All done!")
