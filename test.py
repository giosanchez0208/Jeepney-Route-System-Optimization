"""analyze_crossover.py

Executes a 1,000-iteration batch simulation of Topological Hub Exchange.
Quantifies Bivariate RPI, Spatial Coverage Shift, and Demand Capture.
"""

import yaml
import random
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.jeep_system import FleetAllocator
from utils.local_search import ACOLocalSearch
from utils.genetic import Chromosome, MemeticAlgorithm
from utils.route import Route

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def construct_matured_chromosome(cg, routes, target_fleet):
    phero = PheromoneMatrix(all_edges=cg.graph)
    alloc = FleetAllocator.allocate_by_mohring(target_fleet, routes, phero, cg)
    chrom = Chromosome(routes=routes, allocation=alloc, pheromones=phero)
    
    for r in routes:
        for edge in r.path:
            chrom.pheromones.tau[edge] = chrom.pheromones.tau.get(edge, 0) + 100.0
            
    report = FleetAllocator.evaluate_allocation(alloc, chrom.pheromones)
    
    chrom.headway_cost = sum(m["headway"] for m in report.values() if m["headway"] != float('inf')) / len(report)
    chrom.load_cost = sum(m["load_factor"] for m in report.values() if m["load_factor"] != float('inf')) / len(report)
    chrom.total_length = sum(m["length"] for m in report.values())
    chrom.total_demand = sum(m["demand"] for m in report.values())
    
    return chrom

def generate_independent_routes(cg, count, min_edges=30):
    routes = []
    valid_nodes = cg.nodes
    while len(routes) < count:
        start = random.choice(valid_nodes)
        end = random.choice(valid_nodes)
        path = cg.findShortestPath(start, end)
        if path and len(path) >= min_edges:
            routes.append(Route(path=path, city_graph=cg))
    return routes

def calculate_rpi(val_a, val_b, val_child):
    best = min(val_a, val_b)
    worst = max(val_a, val_b)
    val_range = worst - best
    if val_range == 0:
        return 0.0 if val_child <= best else 1.0
    return (val_child - best) / val_range

def run_batch_analysis(iterations=1000):
    CITY = "Iligan City, Philippines"
    TOTAL_FLEET = 100
    ROUTE_SUBSET_SIZE = 5

    out_dir = Path("results/phase_d_analysis")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print(f" BOOTING PHASE D: ADVANCED BATCH ANALYSIS ({iterations} ITERATIONS)")
    print("="*60)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    cg = sim.jeep_system.routes[0].cg
    
    local_search = ACOLocalSearch(cg, p_local=1.0, base_window_size=15)
    memetic_algo = MemeticAlgorithm(cg, local_search, target_route_count=ROUTE_SUBSET_SIZE)
    
    records = []
    
    for i in range(iterations):
        if i % 10 == 0:
            print(f"[*] Processing Iteration {i}/{iterations}...", end="\r")
            
        parent_a_routes = [Route(path=r.path[:], city_graph=cg) for r in sim.jeep_system.routes[:ROUTE_SUBSET_SIZE]]
        if i % 2 == 0:
            parent_a_routes = generate_independent_routes(cg, ROUTE_SUBSET_SIZE)
            
        parent_a = construct_matured_chromosome(cg, parent_a_routes, TOTAL_FLEET)
        
        parent_b_routes = generate_independent_routes(cg, ROUTE_SUBSET_SIZE)
        parent_b = construct_matured_chromosome(cg, parent_b_routes, TOTAL_FLEET)
        
        divergence = memetic_algo.calculate_system_divergence(parent_a, parent_b)
        
        child_routes = memetic_algo.crossover_topological_hub(parent_a, parent_b)
        child_phero = memetic_algo.inherit_pheromones(parent_a, parent_b)
        child_alloc = FleetAllocator.allocate_by_mohring(TOTAL_FLEET, child_routes, child_phero, cg)
        child = construct_matured_chromosome(cg, child_routes, TOTAL_FLEET)
        
        rpi_headway = calculate_rpi(parent_a.headway_cost, parent_b.headway_cost, child.headway_cost)
        rpi_load = calculate_rpi(parent_a.load_cost, parent_b.load_cost, child.load_cost)
        
        avg_parent_length = (parent_a.total_length + parent_b.total_length) / 2.0
        coverage_shift = child.total_length / avg_parent_length if avg_parent_length > 0 else 1.0

        avg_parent_demand = (parent_a.total_demand + parent_b.total_demand) / 2.0
        demand_capture = child.total_demand / avg_parent_demand if avg_parent_demand > 0 else 1.0
        
        records.append({
            "Iteration": i,
            "RPI_WaitTime": rpi_headway,
            "RPI_Operator": rpi_load,
            "Coverage_Shift": coverage_shift,
            "Demand_Capture": demand_capture,
            "Frechet_Div": divergence["frechet_divergence"],
            "MSE_Div": divergence["pheromone_mse"],
            "Synergy": rpi_headway < 0.0 and rpi_load < 0.0
        })
        
    print(f"\n[*] Batch processing complete. Generating 2x2 analysis matrix...")
    df = pd.DataFrame(records)
    df.to_csv(out_dir / "advanced_crossover_metrics.csv", index=False)
    
    sns.set_theme(style="darkgrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Top Left: Utility vs Efficiency Pareto
    sns.scatterplot(data=df, x="RPI_WaitTime", y="RPI_Operator", hue="Synergy", palette={True: "green", False: "gray"}, alpha=0.6, ax=axes[0, 0])
    axes[0, 0].axhline(0, color="black", linestyle="--")
    axes[0, 0].axvline(0, color="black", linestyle="--")
    axes[0, 0].set_title("Pareto Front: Passenger vs. Operator RPI")
    
    # Top Right: Spatial Coverage Distribution
    sns.histplot(df["Coverage_Shift"], bins=30, kde=True, color="blue", ax=axes[0, 1])
    axes[0, 1].axvline(1.0, color="red", linestyle="--")
    axes[0, 1].set_title("Spatial Coverage Shift (Child Length / Avg Parent Length)")
    
    # Bottom Left: Geometric Divergence vs Passenger Utility
    sns.scatterplot(data=df, x="Frechet_Div", y="RPI_WaitTime", hue="Synergy", palette={True: "green", False: "gray"}, alpha=0.6, ax=axes[1, 0])
    axes[1, 0].axhline(0, color="black", linestyle="--")
    axes[1, 0].set_title("Geometric Frechet Divergence vs Wait Time RPI")
    
    # Bottom Right: Demand Capture ratio
    sns.histplot(df["Demand_Capture"], bins=30, kde=True, color="purple", ax=axes[1, 1])
    axes[1, 1].axvline(1.0, color="red", linestyle="--")
    axes[1, 1].set_title("Demand Capture Efficiency (Child Phero / Avg Parent Phero)")
    
    plt.tight_layout()
    plot_path = out_dir / "advanced_crossover_analysis.png"
    plt.savefig(plot_path, dpi=300)
    print(f"[*] Exported advanced statistical matrix to: {plot_path}")

if __name__ == "__main__":
    run_batch_analysis(iterations=1000)