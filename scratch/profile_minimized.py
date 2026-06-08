import os
import sys
import time
import cProfile
import pstats
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.simulation import SimulationEvaluator

def main():
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Minimize simulation settings for profiling
    config["simulation"]["num_ticks"] = 100
    config["simulation"]["mohring_sample_size"] = 100
    config["simulation"]["spawn_rate_per_hour"] = 200.0
    config["disable_tqdm"] = True
    
    print("\n--- RUNNING MINIMIZED EVALUATION UNDER CPROFILE ---")
    evaluator = SimulationEvaluator(
        config=config,
        city_graph=cg,
        travel_graph=None,
        demand_sampler=ddm
    )
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    t0 = time.time()
    result = evaluator.evaluate(routes)
    duration = time.time() - t0
    
    profiler.disable()
    
    print(f"Evaluation finished in {duration:.2f}s")
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(30)

if __name__ == "__main__":
    main()
