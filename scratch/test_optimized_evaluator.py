import os
import sys
import time
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
        
    print("\n--- RUNNING FULL EVALUATION ---")
    evaluator = SimulationEvaluator(
        config=config,
        city_graph=cg,
        travel_graph=None,
        demand_sampler=ddm
    )
    
    t0 = time.time()
    result = evaluator.evaluate(routes)
    duration = time.time() - t0
    
    print(f"Evaluation finished in {duration:.2f}s")
    print(f"Fitness score: {result.fitness_score:.4f}")
    print(f"Details: {result}")

if __name__ == "__main__":
    main()
