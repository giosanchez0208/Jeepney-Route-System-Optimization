import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph

def main():
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    generator = RouteGenerator(city_graph=cg, sampler=ddm, verbose=False)
    routes = [generator.generate(n_points=4)]
    tg = TravelGraph(cg, config={"walk_wt": 0.05, "ride_wt": 0.005}, routes=routes)
    
    print("\nRunning 50 queries and measuring expansions:")
    success_count = 0
    total_pops = 0
    
    for i in range(50):
        o = ddm.get_point()
        d = ddm.get_point()
        
        # We'll patch A* to count popped nodes
        # Let's just run it and see if a path is returned
        t0 = time.time()
        journey = tg.findShortestJourney(o, d)
        duration = time.time() - t0
        
        has_path = len(journey) > 0
        if has_path:
            success_count += 1
            
        print(f"Query {i:2d}: Path? {str(has_path):5s} | Time: {duration:.4f}s")
        
    print(f"\nSummary: {success_count}/50 queries returned a valid path.")

if __name__ == "__main__":
    main()
