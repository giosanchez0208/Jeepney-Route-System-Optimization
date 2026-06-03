import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system, build_travelgraph
from utils.simulation import StaticSurrogateEvaluator

print("Loading cg and ddm...")
cg = reuse_citygraph("results_and_discussion/pkl/profile_p1.pkl")
ddm = reuse_ddm("results_and_discussion/pkl/ddm_8am.pkl")

print("Generating 4 routes...")
routes = generate_route_system(4, cg, ddm)

print("Building TravelGraph...")
yaml_file = "configs/profile_p1.yaml"
tg = build_travelgraph(cg, yaml_file, routes)

print("Getting start/end points...")
points = [ddm.get_point(only_drivable=False) for _ in range(20)]

print("Starting pathfinding tests...")
t0 = time.time()
for i in range(10):
    start = points[i]
    end = points[i+10]
    t_start = time.time()
    path = tg.findShortestJourney(start, end)
    duration = time.time() - t_start
    print(f"Path {i}: length={len(path)}, took {duration:.4f} seconds")
print(f"Total time for 10 paths: {time.time() - t0:.4f} seconds")
