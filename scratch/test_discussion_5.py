"""
Results & Discussion 5: Temporal Resolution Sensitivity Analysis
  Exp 1: seconds_per_tick sweep (constant simulated duration)
  Exp 2: num_ticks sweep (constant seconds_per_tick=10)
Lightweight run for bug-catching only.
"""
import os, sys, random, time, yaml, gc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

from utils_simplified import (
    reuse_citygraph, reuse_ddm, generate_route_system,
    generate_dummy_yaml, build_travelgraph, run_simulation
)
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem

# ---- Setup ----
cg = reuse_citygraph("results_and_discussion/pkl/profile_p1.pkl")
ddm = reuse_ddm("results_and_discussion/pkl/ddm_8am.pkl")
os.makedirs("configs", exist_ok=True)

# Params tuned so passengers actually complete trips
NUM_JEEPS = 25
SPAWN_RATE = 120.0
N_REPS = 2
ROUTE_COUNTS = [3, 5]

# Exp 1: sweep spt at constant simulated duration (30 min = 1800s)
TOTAL_SIM_SECONDS = 1800
SPT_VALUES = [5, 10, 20, 30]

# Exp 2: sweep num_ticks at fixed spt=10
SPT_FIXED = 10
TICK_VALUES = [60, 120, 180, 270]

# ---- Pre-generate route systems ----
print("[SETUP] Generating route systems...")
route_systems = {}
for n_routes in ROUTE_COUNTS:
    random.seed(42 + n_routes)
    np.random.seed(42 + n_routes)
    route_systems[n_routes] = generate_route_system(n_routes, cg, ddm)
    total_edges = sum(len(r.path) for r in route_systems[n_routes])
    print(f"  {n_routes} routes, {total_edges} total edges")


def make_jeep_system(routes, spt):
    """Build a JeepSystem for the given routes and seconds_per_tick."""
    jeeps = []
    per_route = max(1, NUM_JEEPS // len(routes))
    for r in routes:
        for _ in range(per_route):
            start = (r.path[0].start.lon, r.path[0].start.lat)
            jeeps.append(Jeep(r, curr_pos=start, speed=20.0, max_capacity=16, seconds_per_tick=spt))
    return JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=50.0, equidistant_spawn=True)


def run_one(routes, spt, num_ticks, rep_seed):
    """Run a single simulation. Returns (fitness, metrics_dict)."""
    yaml_path = f"configs/_nb5_tmp_{spt}_{num_ticks}_{rep_seed}.yaml"
    generate_dummy_yaml(
        yaml_path,
        **{
            "simulation.num_ticks": num_ticks,
            "simulation.seconds_per_tick": spt,
            "simulation.total_allocatable_jeeps": NUM_JEEPS,
            "simulation.spawn_rate_per_hour": SPAWN_RATE,
            "simulation.mohring_sample_size": 2,
        }
    )
    random.seed(rep_seed)
    np.random.seed(rep_seed)

    js = make_jeep_system(routes, spt)
    tg = build_travelgraph(cg, yaml_path, routes)
    sim = run_simulation(tg, yaml_path, js, ddm, delete_yaml_when_done=True)
    result = sim.evaluate_fitness()
    return result.fitness_score, result.metrics


# ===========================================================
# Experiment 1: seconds_per_tick sensitivity
# ===========================================================
print("\n" + "="*60)
print("[EXP 1] SECONDS-PER-TICK SENSITIVITY")
print("  Constant simulated duration = %d seconds (%d min)" % (TOTAL_SIM_SECONDS, TOTAL_SIM_SECONDS//60))
print("="*60)

spt_rows = []
for n_routes in ROUTE_COUNTS:
    routes = route_systems[n_routes]
    for spt in SPT_VALUES:
        num_ticks = max(10, TOTAL_SIM_SECONDS // spt)
        for rep in range(N_REPS):
            rep_seed = 1000 + n_routes * 100 + spt * 10 + rep
            t0 = time.time()
            fitness, metrics = run_one(routes, spt, num_ticks, rep_seed)
            wall = time.time() - t0
            done = metrics.get("completed_count", 0)
            inc = metrics.get("incomplete_count", 0)
            row = {
                "n_routes": n_routes, "spt": spt, "num_ticks": num_ticks,
                "rep": rep, "fitness": fitness,
                "completed": done, "incomplete": inc,
                "mean_commute": metrics.get("mean_commute_time", 0),
                "wall_s": round(wall, 1)
            }
            spt_rows.append(row)
            print(f"  R={n_routes} spt={spt:2d} ticks={num_ticks:4d} rep={rep} | "
                  f"fit={fitness:10.2f} done={done:3d} inc={inc:3d} wall={wall:.1f}s")
            gc.collect()

df_spt = pd.DataFrame(spt_rows)
print("\n[EXP 1] Aggregated:")
agg1 = df_spt.groupby(["n_routes", "spt"]).agg(
    mean_fit=("fitness", "mean"), std_fit=("fitness", "std"),
    cv_fit=("fitness", lambda x: x.std() / x.mean() if x.mean() > 0 else 0),
    mean_done=("completed", "mean"), mean_inc=("incomplete", "mean"),
    mean_wall=("wall_s", "mean")
).reset_index()
print(agg1.to_string(index=False))

# ===========================================================
# Experiment 2: num_ticks sensitivity
# ===========================================================
print("\n" + "="*60)
print("[EXP 2] NUM-TICKS SENSITIVITY (spt=%d fixed)" % SPT_FIXED)
print("="*60)

tick_rows = []
for n_routes in ROUTE_COUNTS:
    routes = route_systems[n_routes]
    for n_ticks in TICK_VALUES:
        sim_min = (n_ticks * SPT_FIXED) / 60.0
        for rep in range(N_REPS):
            rep_seed = 2000 + n_routes * 100 + n_ticks + rep
            t0 = time.time()
            fitness, metrics = run_one(routes, SPT_FIXED, n_ticks, rep_seed)
            wall = time.time() - t0
            done = metrics.get("completed_count", 0)
            inc = metrics.get("incomplete_count", 0)
            row = {
                "n_routes": n_routes, "num_ticks": n_ticks,
                "sim_min": round(sim_min, 1),
                "rep": rep, "fitness": fitness,
                "completed": done, "incomplete": inc,
                "mean_commute": metrics.get("mean_commute_time", 0),
                "wall_s": round(wall, 1)
            }
            tick_rows.append(row)
            print(f"  R={n_routes} ticks={n_ticks:4d} ({sim_min:.0f}min) rep={rep} | "
                  f"fit={fitness:10.2f} done={done:3d} inc={inc:3d} wall={wall:.1f}s")
            gc.collect()

df_ticks = pd.DataFrame(tick_rows)
print("\n[EXP 2] Aggregated:")
agg2 = df_ticks.groupby(["n_routes", "num_ticks"]).agg(
    mean_fit=("fitness", "mean"), std_fit=("fitness", "std"),
    cv_fit=("fitness", lambda x: x.std() / x.mean() if x.mean() > 0 else 0),
    mean_done=("completed", "mean"), mean_inc=("incomplete", "mean"),
    mean_wall=("wall_s", "mean")
).reset_index()
print(agg2.to_string(index=False))

print("\n[DONE] All experiments complete.")
