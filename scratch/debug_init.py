import os
import sys
import time
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system

def log(msg):
    print(msg, flush=True)

def main():
    log("Starting debug_init...")
    
    t0 = time.time()
    cg_pkl = "rnd/pkl/profile_p1.pkl"
    log(f"Loading CityGraph from {cg_pkl}...")
    cg = reuse_citygraph(cg_pkl)
    log(f"CityGraph loaded in {time.time() - t0:.2f}s")
    
    t0 = time.time()
    ddm_pkl = "rnd/pkl/ddm_8am.pkl"
    log(f"Loading DDM from {ddm_pkl}...")
    ddm = reuse_ddm(ddm_pkl)
    log(f"DDM loaded in {time.time() - t0:.2f}s")
    
    t0 = time.time()
    log("Generating 38 routes...")
    routes = generate_route_system(38, cg, ddm)
    log(f"Generated {len(routes)} routes in {time.time() - t0:.2f}s")

if __name__ == "__main__":
    main()
