"""analyze_crossover.py

Executes a 50,000-iteration batch simulation of Topological Hub Exchange.
Outputs a Sorted Performance Corridor visualizing Parent A, Parent B, and Child.
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
    chrom.cost = (chrom.headway_cost + chrom.load_cost) / 2.0
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

def run_batch_analysis(iterations=50000):
    CITY = "Iligan City, Philippines"
    TOTAL_FLEET = 100
    ROUTE_SUBSET_SIZE = 5

    out_dir = Path("results/phase_d_analysis")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f" BOOTING PHASE D: BATCH ANALYSIS ({iterations} ITERATIONS)")
    print("=" * 60)

    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    cg = sim.jeep_system.routes[0].cg

    local_search = ACOLocalSearch(cg, p_local=1.0, base_window_size=15)
    memetic_algo = MemeticAlgorithm(cg, local_search, target_route_count=ROUTE_SUBSET_SIZE)

    records = []

    for i in range(iterations):
        if i % 500 == 0:
            print(f"[*] Processing Iteration {i}/{iterations}...", end="\r")

        parent_a_routes = [Route(path=r.path[:], city_graph=cg) for r in sim.jeep_system.routes[:ROUTE_SUBSET_SIZE]]
        if i % 2 == 0:
            parent_a_routes = generate_independent_routes(cg, ROUTE_SUBSET_SIZE)

        parent_a = construct_matured_chromosome(cg, parent_a_routes, TOTAL_FLEET)
        parent_b_routes = generate_independent_routes(cg, ROUTE_SUBSET_SIZE)
        parent_b = construct_matured_chromosome(cg, parent_b_routes, TOTAL_FLEET)

        child_routes = memetic_algo.crossover_topological_hub(parent_a, parent_b)
        child_phero = memetic_algo.inherit_pheromones(parent_a, parent_b)
        child_alloc = FleetAllocator.allocate_by_mohring(TOTAL_FLEET, child_routes, child_phero, cg)
        child = construct_matured_chromosome(cg, child_routes, TOTAL_FLEET)

        best_parent_cost = min(parent_a.cost, parent_b.cost)
        worst_parent_cost = max(parent_a.cost, parent_b.cost)

        if child.cost < best_parent_cost:
            status = "Synergy"
        elif child.cost > worst_parent_cost:
            status = "Destructive"
        else:
            status = "Interpolation"

        records.append({
            "Best_Parent": best_parent_cost,
            "Worst_Parent": worst_parent_cost,
            "Child_Cost": child.cost,
            "Status": status
        })

    print(f"\n[*] Batch processing complete.")

    df = pd.DataFrame(records)

    # --- Print breakdown ---
    total = len(df)
    counts = df["Status"].value_counts()
    print("\n" + "=" * 40)
    print(" CROSSOVER OUTCOME BREAKDOWN")
    print("=" * 40)
    for label in ["Synergy", "Interpolation", "Destructive"]:
        n = counts.get(label, 0)
        pct = (n / total) * 100
        print(f"  {label:<16}: {n:>6} / {total}  ({pct:.2f}%)")
    print("=" * 40 + "\n")

    # --- Sort by Best Parent for a smooth baseline ---
    df = df.sort_values(by="Best_Parent").reset_index(drop=True)

    # Smooth the Worst Parent ceiling with a rolling average to kill the spikes
    SMOOTH_WINDOW = max(1, iterations // 200)
    df["Worst_Parent_Smooth"] = df["Worst_Parent"].rolling(window=SMOOTH_WINDOW, center=True, min_periods=1).mean()

    # --- Visualization ---
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(13, 6))

    # Corridor fill between smoothed ceiling and baseline
    ax.fill_between(
        df.index,
        df["Best_Parent"],
        df["Worst_Parent_Smooth"],
        color="#cccccc",
        alpha=0.35,
        label="Inheritance Corridor",
        zorder=1,
    )

    # Smoothed worst parent ceiling
    ax.plot(
        df.index,
        df["Worst_Parent_Smooth"],
        color="#e05050",
        linewidth=1.5,
        alpha=0.85,
        label="Worst Parent — smoothed ceiling",
        zorder=2,
    )

    # Best parent baseline
    ax.plot(
        df.index,
        df["Best_Parent"],
        color="#2a9d4e",
        linewidth=2,
        label="Best Parent — baseline",
        zorder=3,
    )

    # Child scatter — small, semi-transparent dots
    palette = {
        "Synergy":       "#3a7abf",
        "Interpolation": "#888888",
        "Destructive":   "#222222",
    }
    # Plot each category separately for clean legend control
    for status, color in palette.items():
        subset = df[df["Status"] == status]
        n = len(subset)
        pct = (n / total) * 100
        ax.scatter(
            subset.index,
            subset["Child_Cost"],
            color=color,
            s=6,
            alpha=0.45,
            linewidths=0,
            label=f"{status} ({pct:.1f}%)",
            zorder=4,
        )

    ax.set_title("Genetic Inheritance Corridor — Sorted by Best Parent Score", fontsize=13, pad=12)
    ax.set_xlabel("Crossover Event (sorted by Best Parent cost)", fontsize=10)
    ax.set_ylabel("Combined System Cost Proxy  (lower is better)", fontsize=10)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.85)
    ax.tick_params(labelsize=9)
    sns.despine(left=False, bottom=False)

    plt.tight_layout()

    plot_path = out_dir / "inheritance_corridor.png"
    plt.savefig(plot_path, dpi=300)
    df.to_csv(out_dir / "crossover_metrics.csv", index=False)
    print(f"[*] Exported visualization to: {plot_path}")

if __name__ == "__main__":
    run_batch_analysis(iterations=50000)