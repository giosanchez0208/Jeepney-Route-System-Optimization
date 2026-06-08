import os
import sys
import time
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.travel_graph import TravelGraph

def log(msg):
    print(msg, flush=True)

def main():
    log("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    log("Generating route system of size 38...")
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg_config = config.get("travel_graph", {})
    
    log("Timing TravelGraph construction (5 iterations)...")
    times = []
    for i in range(5):
        t0 = time.time()
        tg = TravelGraph(cg, config=tg_config, routes=routes)
        t1 = time.time()
        times.append(t1 - t0)
        log(f"  Iteration {i+1}: {t1 - t0:.2f}s")
    
    log(f"Average TravelGraph construction time: {sum(times)/len(times):.2f}s")

    # Time a few shortest journeys
    log("Timing shortest journey queries (100 iterations)...")
    tg = TravelGraph(cg, config=tg_config, routes=routes)
    
    origins = [ddm.get_point() for _ in range(100)]
    dests = [ddm.get_point() for _ in range(100)]
    
    t0 = time.time()
    for o, d in zip(origins, dests):
        # Bypass cache to measure raw search time
        tg._findShortestJourney_impl(o, d)
    t1 = time.time()
    log(f"Time for 100 queries: {t1 - t0:.2f}s ({ (t1 - t0)/100:.4f}s per query)")

if __name__ == "__main__":
    main()
