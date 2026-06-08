import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm
from utils.route import RouteGenerator

def main():
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    generator = RouteGenerator(city_graph=cg, sampler=ddm, verbose=False)
    
    print("Generating 10 routes and checking edge lengths...")
    for i in range(10):
        r = generator.generate(n_points=4)
        zero_edges = [e for e in r.path if e._length == 0.0]
        if zero_edges:
            print(f"Route {i} has {len(zero_edges)} zero-length edges!")
            for ze in zero_edges:
                print(f"  Edge {ze.id}: {ze.start.id} -> {ze.end.id}, layers: {ze.start.layer} -> {ze.end.layer}")
        else:
            print(f"Route {i} is clean.")

if __name__ == "__main__":
    main()
