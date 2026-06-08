import os
import sys
import time
import cProfile
import pstats
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph
from utils.simulation import SimulationSetup

def main():
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    print("Generating 1 route...")
    generator = RouteGenerator(city_graph=cg, sampler=ddm, verbose=False)
    routes = [generator.generate(n_points=4)]
    
    print("Setting up simulation...")
    config = {
        "city_graph": {
            "name": "Iligan City",
            "bbox": [8.1500, 8.3300, 124.1500, 124.4000]
        },
        "ddm": {"alpha": 0.6, "beta": 0.4},
        "travel_graph": {"walk_wt": 0.05, "ride_wt": 0.005},
        "simulation": {
            "num_ticks": 1000,
            "mohring_sample_size": 10,
            "spawn_rate_per_hour": 0.0,
            "total_allocatable_jeeps": 10,
            "jeep_speed_kmh": 20.0,
            "jeep_capacity": 16,
            "weight_tolerance": 14.4,
            "seconds_per_tick": 10
        }
    }
    
    setup = SimulationSetup(city_query="Iligan City", config=config, routes=routes)
    sim = setup.build()
    
    print("\n--- RUNNING 1000 TICKS UNDER CPROFILE ---")
    profiler = cProfile.Profile()
    profiler.enable()
    
    t0 = time.time()
    sim.run()
    duration = time.time() - t0
    
    profiler.disable()
    
    print(f"\n1000 ticks finished in {duration:.2f}s")
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(30)

if __name__ == "__main__":
    main()
