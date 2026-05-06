"""
import yaml
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
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

def construct_matured_chromosome(cg, routes, target_fleet):
    phero = PheromoneMatrix(all_edges=cg.graph)
    alloc = FleetAllocator.allocate_by_mohring(target_fleet, routes, phero, cg)
    chrom = Chromosome(routes=routes, allocation=alloc, pheromones=phero)
    for r in routes:
        for edge in r.path:
            chrom.pheromones.tau[edge] = chrom.pheromones.tau.get(edge, 0) + 100.0
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
    syn = mcolors.LinearSegmentedColormap.from_list('syn', ['#00FF00', '#004400'])(np.linspace(0, 1, 256))
    interp = mcolors.LinearSegmentedColormap.from_list('interp', ['#808080', '#000000'])(np.linspace(0, 1, 256))
    dest = mcolors.LinearSegmentedColormap.from_list('dest', ['#FF0000', '#440000'])(np.linspace(0, 1, 256))
    
    combined = np.vstack((syn, interp, dest))
    return mcolors.LinearSegmentedColormap.from_list('GeneticLandscape', combined)

def run_heatmap_analysis(iterations=50_000):
    out_dir = Path("results/thesis_exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    config = load_config()
    setup = SimulationSetup(city_query="Iligan City, Philippines", config=config)
    sim = setup.build(visualizer=False)
    cg = sim.jeep_system.routes[0].cg
    memetic = MemeticAlgorithm(cg, ACOLocalSearch(cg), 5)
    
    records = []
    for _ in tqdm(range(iterations), desc="Simulating Generations", unit="gen"):
        p_a = construct_matured_chromosome(cg, generate_independent_routes(cg, 5), 100)
        p_b = construct_matured_chromosome(cg, generate_independent_routes(cg, 5), 100)
        
        best_p, worst_p = (p_a, p_b) if p_a.cost < p_b.cost else (p_b, p_a)
        child = construct_matured_chromosome(cg, memetic.crossover_topological_hub(p_a, p_b), 100)
        
        rpi = calculate_rpi(best_p.cost, worst_p.cost, child.cost)
        records.append({
            "Best_Parent_Cost": best_p.cost,
            "Parental_Gap": worst_p.cost - best_p.cost,
            "Child_RPI": rpi
        })

    df = pd.DataFrame(records)
    df.to_csv(out_dir / "genetic_raw_data.csv", index=False)
    
    syn_mask = df["Child_RPI"] < 0
    int_mask = (df["Child_RPI"] >= 0) & (df["Child_RPI"] <= 1)
    des_mask = df["Child_RPI"] > 1
    
    summary = (
        f"TOTAL ITERATIONS: {len(df)}\n"
        f"SYNERGY: {syn_mask.sum()} ({syn_mask.mean():.2%})\n"
        f"INTERPOLATION: {int_mask.sum()} ({int_mask.mean():.2%})\n"
        f"DESTRUCTIVE: {des_mask.sum()} ({des_mask.mean():.2%})\n"
        f"MEAN RPI: {df['Child_RPI'].mean():.4f}"
    )
    (out_dir / "analysis_summary.txt").write_text(summary)

    custom_map = create_genetic_colormap()
    resolutions = [20, 40, 60, 80, 100]

    for res in resolutions:
        statistic, x_edges, y_edges, _ = binned_statistic_2d(
            df["Best_Parent_Cost"], 
            df["Parental_Gap"], 
            df["Child_RPI"].clip(-1, 2), 
            statistic='mean', 
            bins=res
        )

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(
            statistic.T, 
            origin='lower', 
            extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]],
            aspect='auto', 
            cmap=custom_map, 
            vmin=-1, 
            vmax=2
        )
        
        ax.set_xlabel("Best Parent Cost")
        ax.set_ylabel("Parental Gap")
        ax.set_title(f"Performance Heatmap ({res}x{res})")
        
        cbar = plt.colorbar(im)
        cbar.set_ticks([-0.5, 0.5, 1.5])
        cbar.set_ticklabels(['Synergy', 'Interpolation', 'Destructive'])
        
        plt.savefig(out_dir / f"heatmap_{res}x{res}.png", dpi=300)
        plt.close()

    print(f"\nFiles exported to: {out_dir.resolve()}")

if __name__ == "__main__":
    run_heatmap_analysis(iterations=100000)
    
only doing this coz i don'tt like the colors
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.stats import binned_statistic_2d
from pathlib import Path

def create_genetic_colormap():
    syn = mcolors.LinearSegmentedColormap.from_list('syn', ['#00FF00', "#FBFF00"])(np.linspace(0, 1, 256))
    interp = mcolors.LinearSegmentedColormap.from_list('interp', ["#4043FF", "#00D0FF"])(np.linspace(0, 1, 256))
    dest = mcolors.LinearSegmentedColormap.from_list('dest', ["#FF8800", "#FF0000"])(np.linspace(0, 1, 256))
    
    combined = np.vstack((syn, interp, dest))
    return mcolors.LinearSegmentedColormap.from_list('GeneticLandscape', combined)

def regenerate_heatmaps_from_csv(csv_path="results/thesis_exports/genetic_raw_data.csv"):
    out_dir = Path("results/thesis_exports/updated_colors")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: Could not find {csv_path}. Ensure the path is correct.")
        return

    custom_map = create_genetic_colormap()
    resolutions = [20, 40, 60, 80, 100]

    print("Generating heatmaps...")
    for res in resolutions:
        statistic, x_edges, y_edges, _ = binned_statistic_2d(
            df["Best_Parent_Cost"], 
            df["Parental_Gap"], 
            df["Child_RPI"].clip(-1, 2), 
            statistic='mean', 
            bins=res
        )

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(
            statistic.T, 
            origin='lower', 
            extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]],
            aspect='auto', 
            cmap=custom_map, 
            vmin=-1, 
            vmax=2
        )
        
        ax.set_xlabel("Best Parent Cost")
        ax.set_ylabel("Parental Gap")
        ax.set_title(f"Performance Heatmap ({res}x{res})")
        
        cbar = plt.colorbar(im)
        cbar.set_ticks([-0.5, 0.5, 1.5])
        cbar.set_ticklabels(['Synergy', 'Interpolation', 'Destructive'])
        
        output_file = out_dir / f"heatmap_{res}x{res}_new_colors.png"
        plt.savefig(output_file, dpi=300)
        plt.close()
        print(f"Saved: {output_file.name}")

    print(f"\nAll files exported to: {out_dir.resolve()}")

if __name__ == "__main__":
    # Update this path if your CSV is located elsewhere
    regenerate_heatmaps_from_csv("results/thesis_exports/genetic_raw_data.csv")