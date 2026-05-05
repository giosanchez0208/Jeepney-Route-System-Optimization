"""test.py

Headless Performance Benchmark.
Executes a 10,000-tick Phase A simulation without visualization to 
measure raw CPU throughput and process Phase B pheromone deposition.
"""

import time
import yaml
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def main():
    CITY = "Iligan City, Philippines"
    OUT_DIR = "results/test"
    TICKS = 10000
    
    print("[*] Loading Configurations...")
    config = load_config()

    print("[*] Booting Simulation Setup...")
    setup = SimulationSetup(city_query=CITY, config=config)
    
    # Enforce strictly headless execution
    sim = setup.build(visualizer=False)
    sim.max_ticks = TICKS

    print(f"\n[*] Executing HEADLESS Phase A Simulation ({TICKS} Ticks)...")
    
    # Start high-precision timer
    start_time = time.time()
    result = sim.run()
    execution_time = time.time() - start_time

    print("\n" + "="*50)
    print(" BENCHMARK RESULTS")
    print("="*50)
    print(f"[*] Execution Time       : {execution_time:.4f} seconds")
    print(f"[*] Ticks Per Second     : {TICKS / execution_time:.2f} TPS")
    print(f"[*] Total Fitness Score  : {result.fitness_score:.2f}")

    print("\n[*] Processing Pheromones (Phase B)...")
    pheromones = PheromoneMatrix(
        all_edges=setup.routes[0].cg.graph, 
        initial_tau=config.get("INITIAL_PHEROMONE", 1.0),
        rho=config.get("RHO_EVAPORATION", 0.1),
        q=config.get("Q_PHEROMONE_INTENSITY", 1000.0)
    )
    pheromones.update_pheromones(result.recorded_paths)
    result.pheromones = pheromones 

    print(f"[*] Exporting Artifacts to {OUT_DIR}...")
    result.export_report(OUT_DIR)
    
    print("[*] Pipeline Test Terminated Successfully.")

if __name__ == "__main__":
    main()