import os
import sys
# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import random
import yaml
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from tqdm import tqdm

# Set seeds for academic reproducibility
random.seed(42)
np.random.seed(42)

from utils_simplified import (
    reuse_citygraph, reuse_ddm, generate_route_system, SimEnvironment, generate_dummy_yaml, run_simulations_parallel,
    build_pheromone_matrix, blend_pheromone_matrix, mutate_attraction, mutate_repulsion, mutate_pruning, crossover_routes,
    build_optimizer, process_telemetry, load_generation_snapshot
)
from utils.route import Route
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.genetic import Chromosome
from utils.evaluation_metrics import jaccard_similarity, graph_edit_distance, wasserstein_2d

# --- Setup ---
cg = reuse_citygraph("results_and_discussion/pkl/profile_p1.pkl")
ddm = reuse_ddm("results_and_discussion/pkl/ddm_8am.pkl")

os.makedirs("configs", exist_ok=True)
opt_yaml = "configs/opt_nb4.yaml"
generate_dummy_yaml(
    opt_yaml,
    **{
        "simulation.num_ticks": 30,             # 30 ticks — enough for passengers to spawn and complete trips
        "simulation.total_allocatable_jeeps": 8,
        "simulation.spawn_rate_per_hour": 60.0,  # Higher spawn rate so passengers actually exist in 30 ticks
        "simulation.mohring_sample_size": 2,     # Minimize mohring sample size
        "optimization.n_population": 4,          # Population size of 4
        "optimization.n_elite": 1,
        "optimization.g_max": 2,                 # 2 generations for speed
        "optimization.telemetry_interval": 1,
        "optimization.checkpoint_interval": 1,
        "optimization.output_root": "outputs/opt_nb4",
        "cg_pkl": "results_and_discussion/pkl/profile_p1.pkl",
        "ddm_pkl": "results_and_discussion/pkl/ddm_8am.pkl"
    }
)

optimizer = build_optimizer(opt_yaml)
optimizer.runner = None
optimizer.engine.runner = None
print(f"Optimizer run directory successfully established: {optimizer.run_dir}")

# --- Part 1: Memetic Pipeline Execution ---
all_populations = {}
mutation_history = []

print("[OPTIMIZER] Initializing population (Generation 0)...")
optimizer.state = optimizer.engine.initialize_state()
optimizer.telemetry.log_lineage(optimizer.state.population)

# Deep copy population but PRESERVE original UIDs for lineage tracking
all_populations[0] = [Chromosome(
    routes=[Route(path=r.path[:], city_graph=cg, id=r.id) for r in c.routes],
    allocation=c.allocation.copy(),
    pheromones=c.pheromones,
    generation=c.generation
) for c in optimizer.state.population]
for idx, c in enumerate(all_populations[0]):
    c.cost = optimizer.state.population[idx].cost
    c.uid = optimizer.state.population[idx].uid      # Preserve original UID
    c.parents = optimizer.state.population[idx].parents

mutation_history.append(optimizer.config.p_mutation)

g_max = optimizer.config.g_max
for gen in range(1, g_max + 1):
    p_local = optimizer.adaptive.get_local_search_prob(gen, g_max)
    intensity = optimizer.adaptive.get_local_search_intensity(gen, g_max)
    
    # Scale up mutation probability if stagnation counter > 0
    current_mut = optimizer.config.p_mutation
    if optimizer.state.stagnation_counter > 0:
        stagnation_boost = optimizer.adaptive.update(optimizer.state.stagnation_counter) - optimizer.config.p_mutation
        p_local = min(p_local + max(0.0, stagnation_boost), 0.95)
        current_mut = min(optimizer.adaptive.update(optimizer.state.stagnation_counter), 0.95)
        
    print(f"\n--- Running generation {gen} / {g_max} (Stagnation: {optimizer.state.stagnation_counter}) ---")
    optimizer.state = optimizer.engine.step_generation(optimizer.state, p_local, intensity=intensity)
    optimizer.state.generation = gen + 1
    
    mean_cost = sum(c.cost for c in optimizer.state.population) / len(optimizer.state.population)
    
    # Log telemetries
    optimizer.telemetry.log_lineage(optimizer.state.population)
    optimizer.telemetry.log_generation(gen + 1, optimizer.state.best_fitness, mean_cost, p_local, optimizer.state.stagnation_counter)
    optimizer.telemetry.export_json_snapshot(gen + 1, optimizer.state.best_fitness, mean_cost, optimizer.state.population)
    
    # Deep copy the population chromosomes — PRESERVE UIDs to prevent lineage breakage
    gen_pop = [Chromosome(
        routes=[Route(path=r.path[:], city_graph=cg, id=r.id) for r in c.routes],
        allocation=c.allocation.copy(),
        pheromones=c.pheromones,
        generation=c.generation
    ) for c in optimizer.state.population]
    for idx, c in enumerate(gen_pop):
        c.cost = optimizer.state.population[idx].cost
        c.uid = optimizer.state.population[idx].uid      # Preserve original UID
        c.parents = optimizer.state.population[idx].parents
        
    all_populations[gen] = gen_pop
    mutation_history.append(current_mut)

print("\n[OPTIMIZER] Run complete! Telemetry successfully serialized.")

# --- Part 2: Convergence ---
telemetry_data = process_telemetry(optimizer.run_dir)
df_lineage = telemetry_data["lineage"]

generations = sorted(df_lineage["Generation"].unique())
best_costs = []
mean_costs = []
worst_costs = []

for g in generations:
    costs = df_lineage[df_lineage["Generation"] == g]["Cost"]
    best_costs.append(costs.min())
    mean_costs.append(costs.mean())
    worst_costs.append(costs.max())

mut_rates = [mutation_history[g] if g < len(mutation_history) else mutation_history[-1] for g in generations]
print(f"Generations parsed: {generations}")
print(f"Best costs: {best_costs}")

# --- Part 3: Trunk Preservation ---
best_chrom_final = sorted(all_populations[g_max], key=lambda c: c.cost)[0]
best_matrix = best_chrom_final.pheromones

# Safely extract sorted edges from the pheromone matrix
sorted_edges = sorted(best_matrix.tau.items(), key=lambda x: x[1], reverse=True)
top_k = max(2, int(len(sorted_edges) * 0.15))
top_edges = {e.id for e, tau in sorted_edges[:top_k]}

all_chroms_by_uid = {}
for gen, pop in all_populations.items():
    for c in pop:
        all_chroms_by_uid[c.uid] = (c, gen)

lineage_path = []
curr_uid = best_chrom_final.uid
while curr_uid:
    if curr_uid in all_chroms_by_uid:
        c, gen = all_chroms_by_uid[curr_uid]
        lineage_path.append((c, gen))
        curr_uid = c.parents[0] if c.parents else None
    else:
        break
lineage_path = lineage_path[::-1]

generations_lineage = []
trunk_preservations = []
for c, gen in lineage_path:
    c_edges = {e.id for r in c.routes for e in r.path}
    shared = c_edges.intersection(top_edges)
    pct = (len(shared) / len(top_edges)) * 100 if top_edges else 0.0
    generations_lineage.append(gen)
    trunk_preservations.append(pct)
print(f"Lineage path length: {len(lineage_path)}")
print(f"Trunk preservations: {trunk_preservations}")

# --- Part 4: Heuristic Efficacy ---
crossover_pairs = []
pop_last_gen = sorted(all_populations[g_max], key=lambda c: c.cost)
for idx in range(min(4, len(pop_last_gen) // 2)):
    crossover_pairs.append((pop_last_gen[idx * 2], pop_last_gen[idx * 2 + 1]))

improvements_A = []
improvements_B = []
runtimes_A = []
runtimes_B = []

print("[EXPERIMENT] Initiating A/B cloning tests across offspring geometries...")
for idx, (p1, p2) in enumerate(crossover_pairs):
    child_routes = crossover_routes(p1.routes, p1.pheromones, p2.routes, cg)
    
    print(f"Evaluating baseline child {idx+1}...")
    baseline_res = optimizer.fitness.evaluate(child_routes)
    baseline_fit = baseline_res.fitness_score
    
    # Twin A
    routes_A = [Route(path=r.path[:], city_graph=cg, id=r.id) for r in child_routes]
    start_A = time.time()
    blended_matrix = blend_pheromone_matrix(p1, p2, cg)
    blended_matrix.gaps = blended_matrix.calculate_demand_service_gaps(routes_A)
    optimizer.engine.algo.local_search.optimize_system(routes_A, blended_matrix, intensity=1.0)
    time_A = time.time() - start_A
    fit_A = optimizer.fitness.evaluate(routes_A).fitness_score
    
    # Twin B
    routes_B = [Route(path=r.path[:], city_graph=cg, id=r.id) for r in child_routes]
    start_B = time.time()
    # Reuse baseline_res to save simulation time
    pre_sim_res = baseline_res
    native_matrix = build_pheromone_matrix(cg, pre_sim_res)
    native_matrix.gaps = native_matrix.calculate_demand_service_gaps(routes_B)
    optimizer.engine.algo.local_search.optimize_system(routes_B, native_matrix, intensity=1.0)
    time_B = time.time() - start_B
    fit_B = optimizer.fitness.evaluate(routes_B).fitness_score
    
    improvements_A.append(max(0.0, baseline_fit - fit_A))
    improvements_B.append(max(0.0, baseline_fit - fit_B))
    runtimes_A.append(time_A)
    runtimes_B.append(time_B)
    print(f"  Pair {idx+1}: Twin A = {improvements_A[-1]:.2f} in {time_A:.3f}s | Twin B = {improvements_B[-1]:.2f} in {time_B:.3f}s")

# --- Part 5: Phenotypic Convergence ---
mean_jaccards = []
mean_geds = []
mean_wassersteins = []
fitness_variances = []

print("[METRICS] Evaluating multi-dimensional population convergence trends...")
for gen in range(g_max + 1):
    pop = all_populations[gen]
    pop_sorted = sorted(pop, key=lambda c: c.cost)
    elite = pop_sorted[0]
    
    elite_edges = set(e for r in elite.routes for e in r.path)
    
    # BUGFIX: Deduplicate edge coordinates AND sample to max 200 points to prevent
    # wasserstein_2d LP solver OOM. The LP has n*m decision variables; with 5000 unique
    # coords, the constraint matrix alone requires ~800 GiB. Sampling preserves the
    # spatial distribution while keeping the LP tractable (200*200 = 40K variables).
    MAX_WASSERSTEIN_POINTS = 200
    
    def _sample_coord_weights(routes, pheromones, max_pts):
        """Deduplicate edges by coordinate, then sample to max_pts for Wasserstein."""
        coord_weights = {}
        for r in routes:
            for e in r.path:
                key = (e.start.lat, e.start.lon)
                coord_weights[key] = coord_weights.get(key, 0.0) + pheromones.tau.get(e, 1.0)
        coords = list(coord_weights.keys())
        weights = list(coord_weights.values())
        if len(coords) > max_pts:
            # Weighted sampling without replacement to preserve high-demand points
            w_arr = np.array(weights)
            w_arr = w_arr / w_arr.sum()  # probability weights
            indices = np.random.choice(len(coords), size=max_pts, replace=False, p=w_arr)
            coords = [coords[i] for i in indices]
            weights = [weights[i] for i in indices]
        return coords, weights
    
    elite_coords, elite_weights = _sample_coord_weights(elite.routes, elite.pheromones, MAX_WASSERSTEIN_POINTS)
    
    jaccards = []
    geds = []
    wassersteins = []
    
    for chrom in pop_sorted[1:]:
        chrom_edges = set(e for r in chrom.routes for e in r.path)
        jaccards.append(jaccard_similarity(elite_edges, chrom_edges))
        geds.append(graph_edit_distance(elite_edges, chrom_edges, max_nodes=8))
        
        chrom_coords, chrom_weights = _sample_coord_weights(chrom.routes, chrom.pheromones, MAX_WASSERSTEIN_POINTS)
        
        try:
            w_dist = wasserstein_2d(elite_coords, elite_weights, chrom_coords, chrom_weights)
        except Exception as e:
            print(f"Wasserstein exception: {e}")
            w_dist = 0.0
        wassersteins.append(w_dist)
        
    mean_jaccards.append(np.mean(jaccards) if jaccards else 0.0)
    mean_geds.append(np.mean(geds) if geds else 0.0)
    mean_wassersteins.append(np.mean(wassersteins) if wassersteins else 0.0)
    costs = [c.cost for c in pop]
    fitness_variances.append(np.var(costs))

print(f"Jaccards: {mean_jaccards}")
print(f"GEDs: {mean_geds}")
print(f"Wassersteins: {mean_wassersteins}")

try:
    if os.path.exists(opt_yaml):
        os.remove(opt_yaml)
except Exception:
    pass
