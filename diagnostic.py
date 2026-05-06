"""
diagnostic.py

Verifies the optimization architecture and exports JSON topology snapshots.
"""

import traceback
from pathlib import Path
from utils.optimizer import Optimizer

def run_diagnostic():
    config_path = Path("configs/initial_test_configs.yaml")
    
    if not config_path.exists():
        print(f"Error: Config file missing at {config_path}")
        return

    print("Initializing Optimizer Builder...")
    try:
        opt = Optimizer.create(config_path)

        # Inject bounding box for telemetry spatial mapping
        opt.telemetry.bounds = opt.config.city_bounds
        
        run_folder = opt.run_dir.resolve()
        print(f"\n[DIAGNOSTIC TARGET]: {run_folder}")
        print("-" * 60)
        print(f"{'GEN':<5} | {'BEST COST':<12} | {'MEAN COST':<12} | {'STAG':<5}")
        print("-" * 60)
        
        if opt.state is None:
            opt.state = opt.engine.initialize_state()
            opt.telemetry.log_lineage(opt.state.population)

        while opt.state.generation <= opt.config.g_max:
            mut_rate = opt.adaptive.update(opt.state.stagnation_counter)
            opt.state = opt.engine.step_generation(opt.state, mut_rate)

            best_cost = opt.state.best_fitness
            mean_cost = sum(c.cost for c in opt.state.population) / len(opt.state.population)
            stag = opt.state.stagnation_counter
            
            print(f"{opt.state.generation:<5} | {best_cost:<12.4f} | {mean_cost:<12.4f} | {stag:<5}")

            opt.telemetry.log_generation(opt.state.generation, best_cost, mean_cost, mut_rate, stag)
            opt.telemetry.log_lineage(opt.state.population)
            
            # Export decoupled JSON topology
            opt.telemetry.export_json_snapshot(opt.state.generation, best_cost, mean_cost, opt.state.population)

        opt.preservation.save_state(opt.state)
        print("-" * 60)
        print("Diagnostic Complete.")
        print(f"Metrics & Lineage -> {run_folder}")
        print(f"JSON Snapshots    -> {run_folder}\\snapshots\\")
        
    except Exception as e:
        print("\nDiagnostic failed with trace:")
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnostic()