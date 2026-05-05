"""test.py

Multi-Export Asynchronous Test.
Runs multiple headless simulation generations and exports segregated 
visual layers (Passengers vs. Network) at the end of each run.
"""

import yaml
import time
import threading
from pathlib import Path
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def main():
    CITY = "Iligan City, Philippines"
    GENERATIONS = 3
    TICKS_PER_GEN = 1500
    
    print("[*] Loading Configurations...")
    config = load_config()

    print("[*] Booting Simulation Setup...")
    setup = SimulationSetup(city_query=CITY, config=config)
    
    # Setup export directories
    export_dir = Path("results/sim_export_test")
    pass_dir = export_dir / "passengers"
    net_dir = export_dir / "network_buildup"
    pass_dir.mkdir(parents=True, exist_ok=True)
    net_dir.mkdir(parents=True, exist_ok=True)

    # Initialize Pheromone Matrix after the first build to ensure routes exist
    pheromones = None

    print(f"\n[*] Starting {GENERATIONS} Headless Generations...")

    for gen in range(1, GENERATIONS + 1):
        print(f"\n--- GENERATION {gen} ---")
        
        # Build simulation state. This populates setup.routes internally.
        sim = setup.build(visualizer=False)
        sim.max_ticks = TICKS_PER_GEN
        
        # Initialize pheromones using the graph from the generated routes
        if pheromones is None:
            pheromones = PheromoneMatrix(
                all_edges=sim.jeep_system.routes[0].cg.graph, 
                initial_tau=config.get("INITIAL_PHEROMONE", 1.0),
                rho=config.get("RHO_EVAPORATION", 0.1),
                q=config.get("Q_PHEROMONE_INTENSITY", 1000.0)
            )
        
        start_time = time.time()
        result = sim.run()
        print(f"[*] Simulation completed in {time.time() - start_time:.2f}s | Fitness: {result.fitness_score:.2f}")

        # Phase B: Update global pheromones based on this generation's results
        pheromones.update_pheromones(result.recorded_paths)

        # ==========================================
        # ASYNC EXPORT 1: Passenger Chokepoints Only
        # ==========================================
        pass_file = pass_dir / f"gen_{gen:02d}_passengers.png"
        sim.export_snapshot(
            filename=str(pass_file),
            draw_routes=False,
            draw_jeeps=False,
            draw_passengers=True
        )

        # ==========================================
        # ASYNC EXPORT 2: Transit Network Isolation
        # ==========================================
        net_file = net_dir / f"gen_{gen:02d}_network.png"
        sim.export_snapshot(
            filename=str(net_file),
            draw_routes=True,
            draw_jeeps=False,
            draw_passengers=False
        )
        
    print("\n[*] Main thread finished. Waiting briefly for background renders to complete...")
    time.sleep(5) 
    print("[*] Pipeline Terminated.")

if __name__ == "__main__":
    main()