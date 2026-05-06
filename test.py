"""
Phase D & E: High-Intensity Lamarckian Diagnostic
Executes crossover events, applies high-intensity mutations (1.5), 
enforces a survival-of-the-fittest gate, and exports complete visual analytics.
"""

import yaml
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from scipy.stats import binned_statistic_2d, gaussian_kde
from pathlib import Path
from tqdm import tqdm
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.jeep_system import FleetAllocator
from utils.local_search import ACOLocalSearch
from utils.genetic import Chromosome, MemeticAlgorithm
from utils.route import Route

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def construct_chromosome(cg, routes, target_fleet, is_parent=True):
    phero = PheromoneMatrix(all_edges=cg.graph)
    baseline_tau = 100.0 if is_parent else 0.0
    alloc = FleetAllocator.allocate_by_mohring(
        total_fleet=target_fleet, 
        routes=routes, 
        pheromones=phero, 
        cg=cg, 
        route_baseline_tau=baseline_tau
    )
    chrom = Chromosome(routes=routes, allocation=alloc, pheromones=phero)
    report = FleetAllocator.evaluate_allocation(alloc, chrom.pheromones)
    chrom.cost = (sum(m["headway"] for m in report.values()) + sum(m["load_factor"] for m in report.values())) / (2.0 * len(report))
    return chrom

def generate_independent_routes(cg, count, min_edges=30):
    routes = []
    while len(routes) < count:
        start, end = random.sample(cg.nodes, 2)
        path = cg.findShortestPath(start, end)
        if path and len(path) >= min_edges:
            routes.append(Route(path=path, city_graph=cg))
    return routes

def apply_targeted_mutations(cg, base_routes, local_search, target_fleet, mutations=3):
    current_routes = [Route(path=r.path[:], city_graph=cg) for r in base_routes]
    
    for _ in range(mutations):
        phero = PheromoneMatrix(all_edges=cg.graph)
        alloc = FleetAllocator.allocate_by_mohring(target_fleet, current_routes, phero, cg, route_baseline_tau=0.0)
        report = FleetAllocator.evaluate_allocation(alloc, phero)
        
        gaps = {}
        for r in current_routes:
            if r in report:
                parity = report[r]["parity"]
                gap_value = 1.0 - parity if parity != float('inf') else -1.0 
                for edge in r.path:
                    gaps[edge] = gaps.get(edge, 0) + gap_value
                    
        for edge in cg.graph:
            if edge not in gaps:
                gaps[edge] = 1.0

        local_search.optimize_system(current_routes, phero, gaps, intensity=1.5)
        
    return current_routes

def calculate_rpi(best, worst, current):
    delta = worst - best
    return (current - best) / delta if delta != 0 else 0.0

def generate_diagnostic_report(df: pd.DataFrame, out_path: Path):
    total = len(df)
    
    accepted = df[df['Mutation_Accepted'] == True]
    rejected = df[df['Mutation_Accepted'] == False]
    
    m_syn = df[df['Final_RPI'] < 0]
    m_int = df[(df['Final_RPI'] >= 0) & (df['Final_RPI'] <= 1)]
    m_des = df[df['Final_RPI'] > 1]

    report = [
        "PHASE D & E: HIGH-INTENSITY LAMARCKIAN ACCEPTANCE DIAGNOSTIC",
        "============================================================\n",
        "1. LOCAL SEARCH SURVIVAL METRICS",
        f"Total Proposals:                {total}",
        f"Accepted Mutations:             {len(accepted)} ({len(accepted)/total:.2%})",
        f"Rejected Mutations:             {len(rejected)} ({len(rejected)/total:.2%})\n",
        "2. SYSTEMIC PERFORMANCE (AFTER GATE)",
        f"Final Synergy Rate (< 0.0):     {(len(m_syn)/total)*100:.2f}%",
        f"Final Interpolation Rate:       {(len(m_int)/total)*100:.2f}%",
        f"Final Destructive Rate:         {(len(m_des)/total)*100:.2f}%",
        f"Final Mean RPI:                 {df['Final_RPI'].mean():.6f}\n",
        "3. GENETIC STABILITY",
        f"Mean Raw Cost:                  {df['Raw_Cost'].mean():.6f}",
        f"Mean Final Cost:                 {df['Final_Cost'].mean():.6f}",
        f"Net Efficiency Gain:            {df['Raw_Cost'].mean() - df['Final_Cost'].mean():.6f}"
    ]
    out_path.write_text("\n".join(report))

def plot_smooth_partition_map(df: pd.DataFrame, out_dir: Path, target_col: str, prefix: str, grid_res=250):
    syn = df[df[target_col] < 0]
    interp = df[(df[target_col] >= 0) & (df[target_col] <= 1)]
    dest = df[df[target_col] > 1]
    
    x_min, x_max = df['Best_Parent_Cost'].min(), df['Best_Parent_Cost'].max()
    y_min, y_max = df['Parental_Gap'].min(), df['Parental_Gap'].max()
    
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, grid_res), np.linspace(y_min, y_max, grid_res))
    positions = np.vstack([xx.ravel(), yy.ravel()])
    
    n_total = len(df)
    Z_stack = []
    
    for subset in [syn, interp, dest]:
        if len(subset) > 5:
            kde = gaussian_kde(np.vstack([subset['Best_Parent_Cost'], subset['Parental_Gap']]))
            Z_stack.append(kde(positions) * (len(subset) / n_total))
        else:
            Z_stack.append(np.zeros_like(xx.ravel()))
            
    Z_stack = np.vstack(Z_stack)
    Z = np.argmax(Z_stack, axis=0).reshape(xx.shape)
    
    threshold = 1e-8 
    mask = np.max(Z_stack, axis=0).reshape(xx.shape) < threshold
    Z = np.ma.masked_where(mask, Z)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ['#00FF00', '#1100FF', '#FF0000']
    ax.contourf(xx, yy, Z, levels=[-0.5, 0.5, 1.5, 2.5], colors=colors, alpha=0.4)
    
    ax.set_xlabel("Best Parent Cost (Base Topology)")
    ax.set_ylabel("Parental Gap (Genetic Variance)")
    ax.set_title(f"Smoothed Bayesian Partition Map: {prefix}")
    
    ax.legend(handles=[
        mpatches.Patch(color='#00FF00', alpha=0.4, label='Synergy Zone'),
        mpatches.Patch(color='#1100FF', alpha=0.4, label='Interpolation Zone'),
        mpatches.Patch(color='#FF0000', alpha=0.4, label='Destructive Zone')
    ], loc='upper right')
    
    plt.savefig(out_dir / f"{prefix.lower().replace(' ', '_')}_partition_map.png", dpi=300)
    plt.close()

def plot_cost_parity(df: pd.DataFrame, out_dir: Path):
    fig, ax = plt.subplots(figsize=(8, 8))
    
    colors = np.where(df['Mutation_Accepted'], 'green', 'red')
    ax.scatter(df['Raw_Cost'], df['Final_Cost'], c=colors, alpha=0.5, s=15, edgecolor='none')
    
    limits = [
        np.min([ax.get_xlim(), ax.get_ylim()]),  
        np.max([ax.get_xlim(), ax.get_ylim()]),  
    ]
    ax.plot(limits, limits, 'k--', alpha=0.75, zorder=0, label='Neutral Threshold (y=x)')
    
    ax.set_aspect('equal')
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    ax.set_title("Lamarckian Gate: Raw Child vs Final Child Cost")
    ax.set_xlabel("Raw Child Cost (Before Mutation)")
    ax.set_ylabel("Final Child Cost (After Gating)")
    ax.legend()
    
    plt.savefig(out_dir / "mutation_cost_parity.png", dpi=300)
    plt.close()

def run_analysis(iterations=1000):
    out_dir = Path("test/parent-child_relationship")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    config = load_config()
    setup = SimulationSetup(city_query="Iligan City, Philippines", config=config)
    sim = setup.build(visualizer=False)
    cg = sim.jeep_system.routes[0].cg
    local_search = ACOLocalSearch(cg)
    memetic = MemeticAlgorithm(cg, local_search, 5)
    
    records = []
    for _ in tqdm(range(iterations), desc="Simulating Generations", unit="gen"):
        p_a = construct_chromosome(cg, generate_independent_routes(cg, 5), 100, is_parent=True)
        p_b = construct_chromosome(cg, generate_independent_routes(cg, 5), 100, is_parent=True)
        best_p, worst_p = (p_a, p_b) if p_a.cost < p_b.cost else (p_b, p_a)
        
        c_routes = memetic.crossover_topological_hub(p_a, p_b)
        c_phero = memetic.inherit_pheromones(p_a, p_b)
        c_alloc = FleetAllocator.allocate_by_mohring(100, c_routes, c_phero, cg, route_baseline_tau=0.0)
        raw_child = Chromosome(routes=c_routes, allocation=c_alloc, pheromones=c_phero)
        c_report = FleetAllocator.evaluate_allocation(c_alloc, raw_child.pheromones)
        raw_child.cost = (sum(m["headway"] for m in c_report.values()) + sum(m["load_factor"] for m in c_report.values())) / (2.0 * len(c_report))
        
        mutated_routes = apply_targeted_mutations(cg, c_routes, local_search, 100, mutations=3)
        m_alloc = FleetAllocator.allocate_by_mohring(100, mutated_routes, c_phero, cg, route_baseline_tau=0.0)
        mutated_child = Chromosome(routes=mutated_routes, allocation=m_alloc, pheromones=c_phero)
        m_report = FleetAllocator.evaluate_allocation(m_alloc, mutated_child.pheromones)
        mutated_child.cost = (sum(m["headway"] for m in m_report.values()) + sum(m["load_factor"] for m in m_report.values())) / (2.0 * len(m_report))
        
        accepted = mutated_child.cost < raw_child.cost
        final_child = mutated_child if accepted else raw_child
        
        records.append({
            "Best_Parent_Cost": best_p.cost,
            "Parental_Gap": worst_p.cost - best_p.cost,
            "Raw_Cost": raw_child.cost,
            "Final_Cost": final_child.cost,
            "Mutation_Accepted": accepted,
            "Child_RPI": calculate_rpi(best_p.cost, worst_p.cost, raw_child.cost),
            "Final_RPI": calculate_rpi(best_p.cost, worst_p.cost, final_child.cost)
        })

    df = pd.DataFrame(records)
    df.to_csv(out_dir / "lamarckian_gated_data.csv", index=False)
    
    generate_diagnostic_report(df, out_dir / "gate_diagnostic_report.txt")
    plot_smooth_partition_map(df, out_dir, "Child_RPI", "Raw Child")
    plot_smooth_partition_map(df, out_dir, "Final_RPI", "Final Child")
    plot_cost_parity(df, out_dir)

if __name__ == "__main__":
    run_analysis(iterations=1000)