"""
Phase D: True Lamarckian Memetic Diagnostic
Executes crossover events using correct epigenetic inheritance and symmetrical evaluation.
Exports raw data, text diagnostics, continuous heatmaps, and a KDE Partition Map.
"""

import yaml
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from scipy.stats import binned_statistic_2d
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

def construct_parent_chromosome(cg, routes, target_fleet):
    phero = PheromoneMatrix(all_edges=cg.graph)
    alloc = FleetAllocator.allocate_by_mohring(
        total_fleet=target_fleet, 
        routes=routes, 
        pheromones=phero, 
        cg=cg, 
        route_baseline_tau=100.0
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

def calculate_rpi(best, worst, child):
    delta = worst - best
    return (child - best) / delta if delta != 0 else 0.0

def create_genetic_colormap():
    syn = mcolors.LinearSegmentedColormap.from_list('syn', ['#00FF00', '#FBFF02'])(np.linspace(0, 1, 256))
    interp = mcolors.LinearSegmentedColormap.from_list('interp', ['#1100FF', '#00FFF2'])(np.linspace(0, 1, 256))
    dest = mcolors.LinearSegmentedColormap.from_list('dest', ['#FFAE00', '#FF0000'])(np.linspace(0, 1, 256))
    combined = np.vstack((syn, interp, dest))
    return mcolors.LinearSegmentedColormap.from_list('GeneticLandscape', combined)

def generate_diagnostic_report(df: pd.DataFrame, out_path: Path):
    total = len(df)
    synergy = df[df['Child_RPI'] < 0]
    interpolation = df[(df['Child_RPI'] >= 0) & (df['Child_RPI'] <= 1)]
    destructive = df[df['Child_RPI'] > 1]
    
    corr_bp = df['Best_Parent_Cost'].corr(df['Child_RPI'])
    corr_pg = df['Parental_Gap'].corr(df['Child_RPI'])
    mean_rpi = df['Child_RPI'].mean()

    report = [
        "PHASE D: TOPOLOGICAL HUB EXCHANGE DIAGNOSTIC REPORT",
        "===================================================\n",
        "1. MACRO STATISTICAL SUMMARY",
        f"Total Iterations:               {total}",
        f"Synergy Rate (< 0.0):           {(len(synergy)/total)*100:.2f}%",
        f"Interpolation Rate (0.0 - 1.0): {(len(interpolation)/total)*100:.2f}%",
        f"Destructive Rate (> 1.0):       {(len(destructive)/total)*100:.2f}%",
        f"System Mean RPI:                {mean_rpi:.6f}\n",
        "2. GENETIC GRADIENT CORRELATIONS",
        f"Best Parent Cost vs Child RPI:  {corr_bp:.6f}",
        f"Parental Gap vs Child RPI:      {corr_pg:.6f}\n",
        "3. DISTRIBUTION ANALYSIS",
        f"Synergy Events:                 {len(synergy)}",
        f"Interpolation Events:           {len(interpolation)}",
        f"Destructive Events:             {len(destructive)}\n"
    ]
    out_path.write_text("\n".join(report))

def plot_smooth_partition_map(df: pd.DataFrame, out_dir: Path, grid_res=250):
    from scipy.stats import gaussian_kde
    
    syn = df[df['Child_RPI'] < 0]
    interp = df[(df['Child_RPI'] >= 0) & (df['Child_RPI'] <= 1)]
    dest = df[df['Child_RPI'] > 1]
    
    x_min, x_max = df['Best_Parent_Cost'].min(), df['Best_Parent_Cost'].max()
    y_min, y_max = df['Parental_Gap'].min(), df['Parental_Gap'].max()
    
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, grid_res), np.linspace(y_min, y_max, grid_res))
    positions = np.vstack([xx.ravel(), yy.ravel()])
    
    kde_syn = gaussian_kde(np.vstack([syn['Best_Parent_Cost'], syn['Parental_Gap']]))
    kde_int = gaussian_kde(np.vstack([interp['Best_Parent_Cost'], interp['Parental_Gap']]))
    kde_dest = gaussian_kde(np.vstack([dest['Best_Parent_Cost'], dest['Parental_Gap']]))
    
    n_total = len(df)
    z_syn = kde_syn(positions) * (len(syn) / n_total)
    z_int = kde_int(positions) * (len(interp) / n_total)
    z_dest = kde_dest(positions) * (len(dest) / n_total)
    
    Z_stack = np.vstack([z_syn, z_int, z_dest])
    Z = np.argmax(Z_stack, axis=0).reshape(xx.shape)
    
    threshold = 1e-8 
    mask = np.max(Z_stack, axis=0).reshape(xx.shape) < threshold
    Z = np.ma.masked_where(mask, Z)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ['#00FF00', '#1100FF', '#FF0000']
    ax.contourf(xx, yy, Z, levels=[-0.5, 0.5, 1.5, 2.5], colors=colors, alpha=0.4)
    
    ax.set_xlabel("Best Parent Cost (Base Topology)")
    ax.set_ylabel("Parental Gap (Genetic Variance)")
    ax.set_title("Smoothed Bayesian Partition Map (KDE Decision Boundaries)")
    
    ax.legend(handles=[
        mpatches.Patch(color='#00FF00', alpha=0.4, label='Synergy Zone'),
        mpatches.Patch(color='#1100FF', alpha=0.4, label='Interpolation Zone'),
        mpatches.Patch(color='#FF0000', alpha=0.4, label='Destructive Zone')
    ], loc='upper right')
    
    plt.savefig(out_dir / "smooth_partition_map.png", dpi=300)
    plt.close()

def run_analysis(iterations=1000):
    out_dir = Path("test/parent-child_relationship")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    config = load_config()
    setup = SimulationSetup(city_query="Iligan City, Philippines", config=config)
    sim = setup.build(visualizer=False)
    cg = sim.jeep_system.routes[0].cg
    memetic = MemeticAlgorithm(cg, ACOLocalSearch(cg), 5)
    
    records = []
    for _ in tqdm(range(iterations), desc="Simulating Generations", unit="gen"):
        p_a = construct_parent_chromosome(cg, generate_independent_routes(cg, 5), 100)
        p_b = construct_parent_chromosome(cg, generate_independent_routes(cg, 5), 100)
        
        best_p, worst_p = (p_a, p_b) if p_a.cost < p_b.cost else (p_b, p_a)
        
        c_routes = memetic.crossover_topological_hub(p_a, p_b)
        c_phero = memetic.inherit_pheromones(p_a, p_b)
        
        # Child allocation requires 0.0 baseline to prevent inflating inherited demand
        c_alloc = FleetAllocator.allocate_by_mohring(
            total_fleet=100, 
            routes=c_routes, 
            pheromones=c_phero, 
            cg=cg, 
            route_baseline_tau=0.0
        )
        
        child = Chromosome(routes=c_routes, allocation=c_alloc, pheromones=c_phero)
        report = FleetAllocator.evaluate_allocation(c_alloc, child.pheromones)
        child.cost = (sum(m["headway"] for m in report.values()) + sum(m["load_factor"] for m in report.values())) / (2.0 * len(report))
        
        rpi = calculate_rpi(best_p.cost, worst_p.cost, child.cost)
        records.append({
            "Best_Parent_Cost": best_p.cost,
            "Parental_Gap": worst_p.cost - best_p.cost,
            "Child_RPI": rpi
        })

    df = pd.DataFrame(records)
    df.to_csv(out_dir / "genetic_raw_data.csv", index=False)
    generate_diagnostic_report(df, out_dir / "diagnostic_report.txt")
    plot_smooth_partition_map(df, out_dir, grid_res=250)

    custom_map = create_genetic_colormap()
    for res in [40, 80]:
        statistic, x_edges, y_edges, _ = binned_statistic_2d(
            df["Best_Parent_Cost"], df["Parental_Gap"], df["Child_RPI"].clip(-1, 2), 
            statistic='mean', bins=res
        )

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(
            statistic.T, origin='lower', extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]],
            aspect='auto', cmap=custom_map, vmin=-1, vmax=2
        )
        ax.set_xlabel("Best Parent Cost")
        ax.set_ylabel("Parental Gap")
        ax.set_title(f"Continuous Performance Heatmap ({res}x{res})")
        
        cbar = plt.colorbar(im)
        cbar.set_ticks([-0.5, 0.5, 1.5])
        cbar.set_ticklabels(['Synergy', 'Interpolation', 'Destructive'])
        
        plt.savefig(out_dir / f"continuous_heatmap_{res}x{res}.png", dpi=300)
        plt.close()

if __name__ == "__main__":
    run_analysis(iterations=1000)