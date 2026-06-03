import os
import sys
# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from tqdm import tqdm
import pandas as pd

from utils_simplified import (
    reuse_citygraph,
    reuse_ddm,
    generate_route_system,
    SimEnvironment,
    generate_dummy_yaml,
    run_simulations_parallel
)
from utils.simulation import StaticSurrogateEvaluator
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem

# 1. Load the pre-compiled static environment data
cg = reuse_citygraph("results_and_discussion/pkl/profile_p1.pkl")
ddm = reuse_ddm("results_and_discussion/pkl/ddm_8am.pkl")

# 2. Configure 5 distinct configuration profiles (we will make this lightweight for testing)
profiles = [
    {"BETA_PENALTY": 2.0, "simulation.spawn_rate_per_hour": 40.0, "travel_graph.transfer_wt": 5.0},
    {"BETA_PENALTY": 1.5, "simulation.spawn_rate_per_hour": 20.0, "travel_graph.transfer_wt": 3.0},
]

# Evaluation Constants
n_setups_per_profile = 2 # lightweight for testing
num_routes = 4
num_jeeps = 25
num_ticks = 20 # fast but robust

# 3. Data Generation Loop
all_fitness_scores = []
all_surrogate_costs = []
profile_labels = []

os.makedirs("configs", exist_ok=True)

for p_idx, profile_overrides in enumerate(tqdm(profiles, desc="Processing Profiles")):
    yaml_path = f"configs/dummy_profile_{p_idx}.yaml"
    
    overrides = profile_overrides.copy()
    overrides["simulation.num_ticks"] = num_ticks
    overrides["simulation.total_allocatable_jeeps"] = num_jeeps
    overrides["cg_pkl"] = "results_and_discussion/pkl/profile_p1.pkl"
    overrides["ddm_pkl"] = "results_and_discussion/pkl/ddm_8am.pkl"
    
    generate_dummy_yaml(yaml_path, **overrides)
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)
        
    surrogate_evaluator = StaticSurrogateEvaluator(config_dict, cg, ddm, num_samples=10)
    
    envs = []
    print(f"\n[Profile {p_idx+1}] Generating {n_setups_per_profile} random setups...")
    
    from utils_simplified import build_travelgraph
    # Read seconds_per_tick from config_dict
    sec_per_tick = config_dict.get("simulation", {}).get("seconds_per_tick", 1)
    
    for _ in tqdm(range(n_setups_per_profile), desc="Generating Routes", leave=False):
        routes = generate_route_system(num_routes, cg, ddm)
        
        # Fast Equidistant Allocation
        jeeps = []
        jeeps_per_route = max(1, num_jeeps // len(routes))
        for r in routes:
            for _ in range(jeeps_per_route):
                start_coord = (r.path[0].start.lon, r.path[0].start.lat)
                jeeps.append(Jeep(r, curr_pos=start_coord, speed=40.0, max_capacity=16, seconds_per_tick=sec_per_tick))
                
        jeep_sys = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=50.0, equidistant_spawn=True)
        tg_obj = build_travelgraph(cg, yaml_path, routes)
        envs.append(SimEnvironment(tg=tg_obj, yaml_file=yaml_path, jeep_system=jeep_sys, sampler=ddm, delete_yaml_when_done=False))

    # Run Microscopic Evaluation (Sequential fallback for stable execution)
    from utils_simplified import run_simulation_env
    micro_results = []
    for env in tqdm(envs, desc="Running Simulations", leave=False):
        sim = run_simulation_env(env)
        micro_results.append(sim.evaluate_fitness())
    
    # Run Surrogate Evaluation (Sequential, fast routing)
    for i, env in enumerate(tqdm(envs, desc="Evaluating Surrogates", leave=False)):
        surr_res = surrogate_evaluator.evaluate(env.jeep_system.routes)
        
        all_fitness_scores.append(micro_results[i].fitness_score)
        all_surrogate_costs.append(surr_res.surrogate_cost)
        profile_labels.append(f"Profile {p_idx+1}")
        
    os.remove(yaml_path)

# 4. Statistical Correlation
df = pd.DataFrame({
    'Fitness Score': all_fitness_scores,
    'Surrogate Cost': all_surrogate_costs,
    'Profile': profile_labels
})

print("--- Raw DataFrame ---")
print(df)

# Filter out degenerate/unreachable simulations
num_samples_test = 10
df_filtered = df[df['Surrogate Cost'] < 100000 * num_samples_test]
print("--- Filtered DataFrame ---")
print(df_filtered)

if len(df_filtered) < 2:
    print("Warning: Less than 2 samples survived the filter!")
    # Use the full df for correlation to avoid crash
    df_for_corr = df
else:
    df_for_corr = df_filtered

pearson_corr, p_value_p = pearsonr(df_for_corr['Surrogate Cost'], df_for_corr['Fitness Score'])
spearman_corr, p_value_s = spearmanr(df_for_corr['Surrogate Cost'], df_for_corr['Fitness Score'])

print("=== Correlation Analysis ===")
print(f"Pearson: {pearson_corr:.4f} (p-value: {p_value_p:.2e})")
print(f"Spearman: {spearman_corr:.4f} (p-value: {p_value_s:.2e})")
