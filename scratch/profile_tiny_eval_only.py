import os
import sys
import cProfile
import pstats
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph
from utils.simulation import SimulationEvaluator

def main():
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    print("Generating 1 route...")
    generator = RouteGenerator(city_graph=cg, sampler=ddm, verbose=False)
    routes = [generator.generate(n_points=4)]
    
    print("Pre-building a dummy travel graph to populate base cache...")
    tg_dummy = TravelGraph(cg, config={"walk_wt": 0.05, "ride_wt": 0.005}, routes=routes)
    
    print("Setting up SimulationEvaluator...")
    config = {
        "travel_graph": {"walk_wt": 0.05, "ride_wt": 0.005},
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
        travel_graph=None, # will construct in evaluate
        demand_sampler=ddm
    )
    
    print("\n--- RUNNING EVALUATE UNDER CPROFILE ---")
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = evaluator.evaluate(routes)
    
    profiler.disable()
    
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(50)

if __name__ == "__main__":
    main()
