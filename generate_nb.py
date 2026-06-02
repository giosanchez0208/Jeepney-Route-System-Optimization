import nbformat as nbf

nb = nbf.v4.new_notebook()

nb.cells.append(nbf.v4.new_markdown_cell("""# Academic Validation: Surrogate vs. Microscopic Evaluation
This notebook validates the correlation between the static mathematical `surrogate_cost` and the robust `fitness_score` derived from full microscopic simulation. A high correlation confirms that the Genetic Algorithm's Lamarckian mutation search can reliably use the surrogate cost as a lightweight heuristic guide."""))

nb.cells.append(nbf.v4.new_code_cell("""import os
import yaml
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from tqdm.notebook import tqdm
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
from utils.jeep_system import JeepSystem"""))

nb.cells.append(nbf.v4.new_code_cell("""# 1. Load the pre-compiled static environment data
cg = reuse_citygraph("results_and_discussion/pkl/profile_p1.pkl")
ddm = reuse_ddm("results_and_discussion/pkl/ddm_8am.pkl")"""))

nb.cells.append(nbf.v4.new_code_cell("""# 2. Configure 5 distinct configuration profiles
profiles = [
    {"BETA_PENALTY": 2.0, "simulation.spawn_rate_per_hour": 40.0, "travel_graph.transfer_wt": 5.0},
    {"BETA_PENALTY": 1.5, "simulation.spawn_rate_per_hour": 20.0, "travel_graph.transfer_wt": 3.0},
    {"BETA_PENALTY": 3.0, "simulation.spawn_rate_per_hour": 60.0, "travel_graph.transfer_wt": 10.0},
    {"BETA_PENALTY": 2.5, "simulation.spawn_rate_per_hour": 50.0, "travel_graph.transfer_wt": 7.0},
    {"BETA_PENALTY": 1.0, "simulation.spawn_rate_per_hour": 30.0, "travel_graph.transfer_wt": 2.0},
]

# Evaluation Constants
n_setups_per_profile = 20 # 5 * 20 = 100 simulations
num_routes = 4
num_jeeps = 25
num_ticks = 1800 # 30 mins to keep it fast but robust"""))

nb.cells.append(nbf.v4.new_code_cell("""# 3. Data Generation Loop
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
        
    surrogate_evaluator = StaticSurrogateEvaluator(config_dict, cg, ddm, num_samples=300)
    
    envs = []
    print(f"\\n[Profile {p_idx+1}] Generating {n_setups_per_profile} random setups...")
    
    for _ in tqdm(range(n_setups_per_profile), desc="Generating Routes", leave=False):
        routes = generate_route_system(num_routes, cg, ddm)
        
        # Fast Equidistant Allocation
        jeeps = []
        jeeps_per_route = max(1, num_jeeps // len(routes))
        for r in routes:
            for _ in range(jeeps_per_route):
                start_coord = (r.path[0].start.lon, r.path[0].start.lat)
                jeeps.append(Jeep(r, curr_pos=start_coord, speed=40.0, max_capacity=16))
                
        jeep_sys = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=50.0, equidistant_spawn=True)
        envs.append(SimEnvironment(tg=None, yaml_file=yaml_path, jeep_system=jeep_sys, sampler=ddm, delete_yaml_when_done=False))

    # Run Microscopic Evaluation (Parallel across CPU cores)
    micro_results = run_simulations_parallel(envs)
    
    # Run Surrogate Evaluation (Sequential, fast routing)
    for i, env in enumerate(tqdm(envs, desc="Evaluating Surrogates", leave=False)):
        surr_res = surrogate_evaluator.evaluate(env.jeep_system.routes)
        
        all_fitness_scores.append(micro_results[i].fitness_score)
        all_surrogate_costs.append(surr_res.surrogate_cost)
        profile_labels.append(f"Profile {p_idx+1}")
        
    os.remove(yaml_path)"""))

nb.cells.append(nbf.v4.new_code_cell("""# 4. Statistical Correlation
df = pd.DataFrame({
    'Fitness Score': all_fitness_scores,
    'Surrogate Cost': all_surrogate_costs,
    'Profile': profile_labels
})

# Filter out degenerate/unreachable simulations
df = df[df['Surrogate Cost'] < 100000]

pearson_corr, p_value_p = pearsonr(df['Surrogate Cost'], df['Fitness Score'])
spearman_corr, p_value_s = spearmanr(df['Surrogate Cost'], df['Fitness Score'])

print("=== Correlation Analysis ===")
print(f"Pearson r : {pearson_corr:.4f} (p-value: {p_value_p:.2e})")
print(f"Spearman ρ: {spearman_corr:.4f} (p-value: {p_value_s:.2e})")"""))

nb.cells.append(nbf.v4.new_code_cell("""# 5. Visualization
plt.figure(figsize=(10, 8))
sns.set_theme(style="whitegrid", palette="muted")

ax = sns.scatterplot(
    data=df, 
    x='Surrogate Cost', 
    y='Fitness Score', 
    hue='Profile', 
    palette='viridis', 
    s=100, 
    alpha=0.8,
    edgecolor='w'
)

sns.regplot(
    data=df, 
    x='Surrogate Cost', 
    y='Fitness Score', 
    scatter=False, 
    color='black', 
    line_kws={"linestyle": "--"}
)

plt.title("Academic Validation: Surrogate Cost vs Microscopic Fitness Score\\n"
          f"(Pearson r={pearson_corr:.2f}, Spearman ρ={spearman_corr:.2f})", fontsize=14, fontweight='bold')
plt.xlabel("Surrogate Cost (Static Calculation)", fontsize=12)
plt.ylabel("Microscopic Fitness Score (Parallel Simulation)", fontsize=12)
plt.legend(title="Config Profiles")
plt.tight_layout()
plt.show()"""))

with open("c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/results_and_discussion_2.ipynb", "w", encoding='utf-8') as f:
    nbf.write(nb, f)
