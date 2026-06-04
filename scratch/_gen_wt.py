"""Generator for rnd_weight_tolerance.ipynb (calibrated, fast). Throwaway tooling."""
import json

cells = []
def md(s):   cells.append({"cell_type": "markdown", "id": f"md{len(cells)}", "metadata": {}, "source": s.strip("\n")})
def code(s): cells.append({"cell_type": "code", "id": f"c{len(cells)}", "execution_count": None, "metadata": {}, "outputs": [], "source": s.strip("\n")})

md('''
# RND - Weight Tolerance: Opportunistic Riding Benefit

Tests whether passengers who board an earlier ALTERNATIVE jeep (Group B) experience a smaller
travel-time delay than those who wait for their planned jeep (Group A), via a one-sided
Mann-Whitney U test on the delay  delta = actual - expected.

**Calibrated for speed.** Each run uses seconds_per_tick=10 and num_ticks=720 (2 h simulated),
a fixed route count, and SWEEPS weight_tolerance (the actual variable). It builds sims directly on
the pre-loaded CityGraph/DDM (no PBF rebuild) and reuses the TravelGraph across tolerance levels.
It is safe to **Run All**: the gate cell auto-calibrates the route count (escalating until enough
opportunistic riders appear at the top tolerance), so a single pass produces a valid result.

Outputs: `outputs/rnd_weight_tolerance/weight_tolerance_passengers.csv` and a delay box plot.
''')

code('''
import copy, time
from pathlib import Path
import yaml, numpy as np, pandas as pd
from scipy.stats import mannwhitneyu

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger_generator import PassengerGenerator
from utils.simulation import Simulation
from utils.passenger import Passenger, EDGE_SW, EDGE_EW, EDGE_RI

# ---------------- calibrated knobs (tune these) ----------------
NUM_ROUTES         = 10                  # enough route overlap for alternatives to exist; capped for speed
TOLERANCE_LEVELS   = [0.0, 14.4, 30.0]   # EIVM; 0 = baseline (no alternatives), 14.4 = production
REPS               = 3                   # replications per tolerance level
SECONDS_PER_TICK   = 10
NUM_TICKS          = 720                 # 2 h simulated -> enough completions for the delay test (NOT 7200)
GATING_MIN_GROUP_B = 30                  # minimum opportunistic riders for a meaningful U test

CG_PKL  = "rnd/pkl/profile_p1.pkl"
DDM_PKL = "rnd/pkl/ddm_8am.pkl"

with open("configs/profile_p1.yaml", encoding="utf-8") as f:
    base_config = yaml.safe_load(f)
base_config["simulation"]["seconds_per_tick"] = SECONDS_PER_TICK
base_config["simulation"]["num_ticks"]        = NUM_TICKS

walk_speed_kmh = float(base_config["simulation"]["passenger_speed_kmh"])
ride_speed_kmh = float(base_config["simulation"]["jeep_speed_kmh"])
spawn_rate     = base_config["simulation"].get("spawn_rate_per_hour")
print(f"routes={NUM_ROUTES} | tolerances={TOLERANCE_LEVELS} | reps={REPS}")
print(f"spt={SECONDS_PER_TICK}s | num_ticks={NUM_TICKS} ({NUM_TICKS*SECONDS_PER_TICK/3600:.1f} h sim) | spawn_rate={spawn_rate}/h")
''')

code('''
print("Loading cached CityGraph and DDM...")
t0 = time.time()
city_graph = reuse_citygraph(CG_PKL)
ddm = reuse_ddm(DDM_PKL)
print(f"Loaded in {time.time()-t0:.1f}s | {len(city_graph.nodes)} nodes, {len(city_graph.graph)} edges")

def expected_travel_minutes(journey):
    walk_m = sum(e.getLength() for e in journey if e._edge_type in (EDGE_SW, EDGE_EW))
    ride_m = sum(e.getLength() for e in journey if e._edge_type == EDGE_RI)
    return walk_m/1000.0/walk_speed_kmh*60.0 + ride_m/1000.0/ride_speed_kmh*60.0

def build_sim(tg, routes, weight_tolerance):
    # Build a Simulation directly on the pre-loaded city_graph/ddm and a prebuilt TravelGraph.
    sc = base_config["simulation"]
    jpr = max(1, int(sc.get("total_allocatable_jeeps", 470)) // len(routes))
    jeeps = []
    for route in routes:
        for _ in range(jpr):
            start = (route.path[0].start.lon, route.path[0].start.lat)
            jeeps.append(Jeep(route, curr_pos=start, speed=float(sc.get("jeep_speed_kmh", 20.0)),
                              max_capacity=int(sc.get("jeep_capacity", 16)), seconds_per_tick=SECONDS_PER_TICK))
    jeep_system = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=float(weight_tolerance), equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=ddm, rate_per_hour=float(sc.get("spawn_rate_per_hour", 600.0)),
                            stdev=float(sc.get("spawn_stdev", 10.0)), speed=walk_speed_kmh, seconds_per_tick=SECONDS_PER_TICK)
    cfg = copy.deepcopy(base_config); cfg["disable_tqdm"] = True
    return Simulation(city_query=base_config["city_graph"]["name"], bounds=city_graph.get_bounds(),
                      jeep_system=jeep_system, passenger_generator=pg, max_ticks=NUM_TICKS,
                      beta_penalty=float(base_config.get("BETA_PENALTY", 2.0)),
                      alpha_std_penalty=float(base_config.get("ALPHA_STD_PENALTY", 0.5)), config=cfg)

def collect_rows(sim, tol):
    completed = list(sim.passenger_generator.archived_passengers)
    completed += [p for p in sim.passenger_generator.passengers if p.state == Passenger.DONE]
    rows = []
    for p in completed:
        despawn = p.despawn_tick if p.despawn_tick is not None else sim.passenger_generator.simulated_time
        exp = expected_travel_minutes(p.journey)
        act = (despawn - p.spawn_tick) / 60.0   # spawn/despawn are simulated SECONDS
        rows.append({"weight_tolerance": float(tol),
                     "took_alternative": bool(getattr(p, "took_alternative", False)),
                     "boarded_expected": bool(getattr(p, "boarded_expected", False)),
                     "expected_min": exp, "actual_min": act, "delta_min": act - exp})
    return rows
''')

code('''
# ---- GATE + AUTO-CALIBRATE: find a route count that yields a viable Group B, then proceed ----
# Safe for "Run All": escalates the route count until enough opportunistic riders appear (at the
# top tolerance), so the sweep below always has data. The warm (routes, tg) is reused for rep 0.
ROUTE_ESCALATION = [NUM_ROUTES, NUM_ROUTES + 6, NUM_ROUTES + 12]
chosen_routes, warm = None, None
for nr in ROUTE_ESCALATION:
    routes = generate_route_system(nr, city_graph, ddm)
    tg = TravelGraph(city_graph, config=base_config.get("travel_graph", {}), routes=routes)
    t0 = time.time()
    sim = build_sim(tg, routes, max(TOLERANCE_LEVELS)); sim.run()
    g = pd.DataFrame(collect_rows(sim, max(TOLERANCE_LEVELS)))
    n_b = int(g["took_alternative"].sum()) if len(g) else 0
    print(f"[GATE] NUM_ROUTES={nr} | completed={len(g)} | Group B={n_b} | {time.time()-t0:.0f}s")
    warm = (routes, tg)
    if n_b >= GATING_MIN_GROUP_B:
        chosen_routes = nr
        break
if chosen_routes is None:
    chosen_routes = ROUTE_ESCALATION[-1]
    print(f"[GATE][!] Group B stayed under {GATING_MIN_GROUP_B}; proceeding at NUM_ROUTES={chosen_routes} "
          f"(U test may be underpowered -- raise TOLERANCE_LEVELS top value if so).")
else:
    print(f"[GATE][OK] Using NUM_ROUTES={chosen_routes}.")
''')

code('''
# ---- MAIN SWEEP: reuse the gate's warm (routes, tg) for rep 0; build fresh for later reps ----
all_rows = []
for rep in range(REPS):
    if rep == 0 and warm is not None:
        routes, tg = warm                       # reuse the calibrated gate network (no rebuild)
    else:
        routes = generate_route_system(chosen_routes, city_graph, ddm)
        tg = TravelGraph(city_graph, config=base_config.get("travel_graph", {}), routes=routes)
    for tol in TOLERANCE_LEVELS:
        t0 = time.time()
        sim = build_sim(tg, routes, tol)
        sim.run()
        rows = collect_rows(sim, tol)
        for r in rows:
            r["rep"] = rep
        all_rows.extend(rows)
        nb = sum(1 for r in rows if r["took_alternative"])
        print(f"rep={rep} tol={tol:5.1f} | completed={len(rows):4d} | Group B={nb:4d} | {time.time()-t0:.0f}s")

df = pd.DataFrame(all_rows)
out_dir = Path("outputs/rnd_weight_tolerance"); out_dir.mkdir(parents=True, exist_ok=True)
df.to_csv(out_dir / "weight_tolerance_passengers.csv", index=False)
print("")
print(f"Saved {len(df)} completed-passenger rows -> {out_dir / 'weight_tolerance_passengers.csv'}")
''')

code('''
# ---- Mann-Whitney U: is Group B delay LESS than Group A delay, per tolerance level? ----
print(f"{'tol':>6} {'nA':>5} {'nB':>5} {'medA':>9} {'medB':>9} {'U':>12} {'p':>11}  verdict")
print("-" * 80)
for tol in TOLERANCE_LEVELS:
    sub = df[df["weight_tolerance"] == tol]
    a = sub.loc[sub["boarded_expected"], "delta_min"].dropna().values
    b = sub.loc[sub["took_alternative"], "delta_min"].dropna().values
    if len(a) < 1 or len(b) < 1:
        print(f"{tol:6.1f} {len(a):5d} {len(b):5d}   (insufficient samples in one group)")
        continue
    U, p = mannwhitneyu(b, a, alternative="less")   # H1: Group B delay < Group A delay
    verdict = "opportunistic riding helps (p<0.05)" if p < 0.05 else "no significant benefit"
    print(f"{tol:6.1f} {len(a):5d} {len(b):5d} {np.median(a):9.2f} {np.median(b):9.2f} {U:12.1f} {p:11.4g}  {verdict}")
''')

code('''
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "serif", "font.size": 11, "savefig.dpi": 300, "axes.grid": True, "grid.alpha": 0.3})

fig, ax = plt.subplots(figsize=(8, 5))
positions, data, labels, colors = [], [], [], []
pos = 0
for tol in TOLERANCE_LEVELS:
    sub = df[df["weight_tolerance"] == tol]
    for grp, key, c in [("A waited", "boarded_expected", "#377eb8"), ("B alt.", "took_alternative", "#e41a1c")]:
        vals = sub.loc[sub[key], "delta_min"].dropna().values
        if len(vals):
            positions.append(pos); data.append(vals); labels.append(f"t={tol} {grp}"); colors.append(c)
        pos += 1
    pos += 1

bp = ax.boxplot(data, positions=positions, patch_artist=True, showfliers=False, widths=0.7)
for patch, c in zip(bp["boxes"], colors):
    patch.set_facecolor(c); patch.set_alpha(0.6)
ax.set_xticks(positions); ax.set_xticklabels(labels, fontsize=8)
ax.set_ylabel("Travel-time delay: actual - expected (min)")
ax.set_title("Opportunistic riding: travel-time delay by group and weight tolerance", fontweight="bold")
plt.tight_layout()
plt.savefig(out_dir / "weight_tolerance_delta_box.png", bbox_inches="tight")
plt.show()
''')

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}
with open("rnd_weight_tolerance.ipynb", "w", encoding="utf-8") as f:
    f.write(json.dumps(nb, indent=1))
print("wrote rnd_weight_tolerance.ipynb with", len(cells), "cells")
json.load(open("rnd_weight_tolerance.ipynb", encoding="utf-8"))
print("JSON valid")
