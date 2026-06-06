"""Compute the REAL signed demand-service disparity D(R)=sum|P-S| (with actual fleet supply) for the
optimized network vs a random baseline, by re-simulating both the same way. Stand-alone diagnostic.

    python scratch/_compute_dr.py [run_dir]
"""
import copy
import os
import pickle
import random
import statistics
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root on path
from utils.toy_city import toy_setup_from_yaml
from utils_simplified import generate_route_system, build_pheromone_matrix
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger_generator import PassengerGenerator
from utils.simulation import Simulation
from utils.optimizer_telemetry import _DummySystem

RD = sys.argv[1] if len(sys.argv) > 1 else "outputs/opt_20260606_174038"
cg, sampler, cfg = toy_setup_from_yaml(os.path.join(RD, "configs.yaml"), verbose=False)
SIM = cfg["simulation"]
CTX = cg.get_bounds()
SPT = int(SIM["seconds_per_tick"]); TICKS = int(SIM["num_ticks"]); RATE = float(SIM["spawn_rate_per_hour"])
TOTAL = int(SIM["total_allocatable_jeeps"]); WT = float(SIM.get("weight_tolerance", 14.44))
NROUTES = int(SIM.get("num_routes", 10))


def run(routes):
    tg = TravelGraph(cg, config=cfg.get("travel_graph", {}), routes=routes)
    jpr = max(1, TOTAL // len(routes))
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                  speed=float(SIM.get("jeep_speed_kmh", 40.0)), max_capacity=int(SIM.get("jeep_capacity", 16)),
                  seconds_per_tick=SPT) for r in routes for _ in range(jpr)]
    js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=WT, equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=sampler, rate_per_hour=RATE, stdev=float(SIM.get("spawn_stdev", 10.0)),
                            speed=float(SIM.get("passenger_speed_kmh", 5.0)), seconds_per_tick=SPT)
    c = copy.deepcopy(cfg); c["disable_tqdm"] = True
    sim = Simulation(city_query="toy", bounds=CTX, jeep_system=js, passenger_generator=pg, max_ticks=TICKS,
                     beta_penalty=float(cfg.get("BETA_PENALTY", 2.0)),
                     alpha_std_penalty=float(cfg.get("ALPHA_STD_PENALTY", 0.5)), config=c)
    return sim.run()


def disparity(routes, seed):
    """Re-simulate and return real D(R)=sum|P-S| from the sim's actual fleet supply, + F_sim + completed."""
    random.seed(seed); np.random.seed(seed)
    res = run(routes)
    ph = build_pheromone_matrix(cg, res)   # ph.gaps computed against res.jeep_system (real supply)
    D = float(sum(abs(g) for g in ph.gaps.values()))
    return D, float(res.fitness_score if res.fitness_score is not None else res.score), res.metrics.get("completed_count")


# ---- final-best routes from the last checkpoint ----
elook = {((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)): e for e in cg.graph}
ckpt = sorted([f for f in os.listdir(os.path.join(RD, "checkpoints")) if f.endswith(".pkl")])[-1]
with open(os.path.join(RD, "checkpoints", ckpt), "rb") as f:
    st = pickle.load(f)
for ch in st.population:
    for r in ch.routes:
        r.cg = cg; r.path = [elook[k] for k in r.path_keys if k in elook]
best = min(st.population, key=lambda c: c.cost)
print(f"[info] run={RD}  checkpoint={ckpt}  final-best cost={best.cost:.0f}  routes={len(best.routes)}")
print("[info] (checkpoint pheromone + even-split supply gave D(R)=0.807 in the earlier diagnostic)\n")

# apples-to-apples: re-simulate final-best and random baselines identically
fin = [disparity(best.routes, 7000 + s) for s in range(3)]
print("FINAL (re-sim):   " + "  ".join(f"D={d:.4f}|F={f:.0f}|c={c}" for d, f, c in fin))
base = [disparity(generate_route_system(NROUTES, cg, sampler), 100 + s) for s in range(5)]
print("BASELINE (re-sim):" + "  ".join(f"D={d:.4f}|F={f:.0f}|c={c}" for d, f, c in base))

dfin = statistics.mean(d for d, _, _ in fin)
dbase = statistics.mean(d for d, _, _ in base)
ffin = statistics.mean(f for _, f, _ in fin)
fbase = statistics.mean(f for _, f, _ in base)
print("\n================  REAL DEMAND-SERVICE DISPARITY  ================")
print(f"baseline   D(R) = {dbase:.4f} (sd {statistics.pstdev([d for d,_,_ in base]):.4f}, n=5 random {NROUTES}-route nets)")
print(f"optimized  D(R) = {dfin:.4f} (sd {statistics.pstdev([d for d,_,_ in fin]):.4f}, n=3 sims of final-best)")
print(f"reduction       = {(dbase - dfin) / dbase * 100:.1f}%")
print(f"F_sim baseline={fbase:.0f}  optimized={ffin:.0f}  reduction={(fbase-ffin)/fbase*100:.1f}%")
