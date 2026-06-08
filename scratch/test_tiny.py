import os
import sys
import time
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph
from utils.simulation import SimulationEvaluator

def main():
    t_start = time.time()
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    print("Generating 1 route...")
    t0 = time.time()
    generator = RouteGenerator(city_graph=cg, sampler=ddm, verbose=False)
    routes = [generator.generate(n_points=4)]
    print(f"Generated route in {time.time() - t0:.2f}s")
    
    print("Building TravelGraph...")
    t0 = time.time()
    tg = TravelGraph(cg, config={"walk_wt": 0.05, "ride_wt": 0.005}, routes=routes)
    print(f"TravelGraph built in {time.time() - t0:.2f}s")
    
    print("Running 10 queries...")
    t0 = time.time()
    for _ in range(10):
        o = ddm.get_point()
        d = ddm.get_point()
        journey = tg.findShortestJourney(o, d)
    print(f"10 queries finished in {time.time() - t0:.2f}s")
    
    print("Setting up SimulationEvaluator...")
    config = {
        "simulation": {
            "num_ticks": 10,
            "mohring_sample_size": 10,
            "spawn_rate_per_hour": 10.0,
            "total_allocatable_jeeps": 5
        }
    }
    evaluator = SimulationEvaluator(
        config=config,
        city_graph=cg,
        travel_graph=tg,
        demand_sampler=ddm
    )
    
    print("Running evaluation...")
    t0 = time.time()
    result = evaluator.evaluate(routes)
    print(f"Evaluation finished in {time.time() - t0:.2f}s")
    print(f"Total script time: {time.time() - t_start:.2f}s")

if __name__ == "__main__":
    main()
