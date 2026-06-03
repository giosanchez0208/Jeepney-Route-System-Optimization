import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system

cg = reuse_citygraph("results_and_discussion/pkl/profile_p1.pkl")
ddm = reuse_ddm("results_and_discussion/pkl/ddm_8am.pkl")

r_sys = generate_route_system(4, cg, ddm)
for i, r in enumerate(r_sys):
    print(f"Route {i} length: {len(r.path)}")
