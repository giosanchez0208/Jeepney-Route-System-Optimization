import os
import yaml
from utils.optimizer import Optimizer
from utils_simplified import generate_dummy_yaml

def main():
    print("Generating fast test config...")
    yaml_path = generate_dummy_yaml(
        export_loc="configs/test_optimizer_fast.yaml",
        **{
            "simulation.num_ticks": 50,
            "simulation.total_allocatable_jeeps": 5,
            "simulation.mohring_sample_size": 10,
            "optimization.n_population": 4, # 4 chromosomes so they can evaluate in parallel
            "optimization.n_elite": 1,
            "optimization.p_mutation": 1.0, # Force mutation to test local search
            "optimization.g_max": 2, # Just 2 generations
            "cg_pkl": "results_and_discussion/pkl/profile_p1.pkl",
            "ddm_pkl": "results_and_discussion/pkl/ddm_8am.pkl"
        }
    )
    
    # We must ensure the optimizer creates its run directory properly
    run_dir = "results_and_discussion/test_optimizer_fast"
    
    # Normally we do Optimizer.create() for a new run
    print(f"Creating optimizer at {run_dir} using {yaml_path}")
    optimizer = Optimizer.create(yaml_path)
    
    # Override run_dir since we just want to run it without the automatic timestamp folder
    optimizer.run_dir = run_dir
    os.makedirs(run_dir, exist_ok=True)
    
    print("Starting optimization loop...")
    optimizer.start()
    
    print("Optimization completed successfully.")

if __name__ == '__main__':
    main()
