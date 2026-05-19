import os
import pickle
from pathlib import Path
from utils.optimizer import Optimizer

def main():
    profile_name = "P7_Extreme_Friction"
    config_path = "configs/profile_p7.yaml"
    
    print(f"==================================================")
    print(f"Executing Optimization Pipeline for Scenario: {profile_name}")
    print(f"==================================================")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing required configuration profile: {config_path}")
        
    # Initialize the orchestrator for a fresh run
    opt = Optimizer.create(config_path=config_path)
    
    # Run the memetic generational loop
    opt.start()
    
    # Extract the absolute global optimum chromosome from the final population (minimizing cost)
    best_chromosome = min(opt.state.population, key=lambda c: c.cost)
    
    # Inject primitive serialization keys to prevent cross-environment object loss
    for route in best_chromosome.routes:
        route.path_keys = [((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)) for e in route.path]
        
    print(f"\n[CONVERGED] Scenario {profile_name} converged. Best Surrogate Cost: {best_chromosome.cost:.4f}")
    
    # Save the best chromosome to outputs/opt_p7
    out_dir = Path("outputs/opt_p7")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    save_path = out_dir / f"{profile_name}_best_chromosome.pkl"
    with open(save_path, "wb") as f:
        pickle.dump(best_chromosome, f)
        
    print(f"Saved best chromosome to {save_path}")

if __name__ == "__main__":
    main()
