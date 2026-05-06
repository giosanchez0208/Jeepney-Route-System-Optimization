"""
Phase D & E: High-Intensity Lamarckian Diagnostic (Complete Visual Suite)
Executes crossover events, applies high-intensity mutations (1.5), 
enforces a survival-of-the-fittest gate, and exports two CSVs alongside
all continuous heatmaps and KDE partition maps.
"""

"""

note: we ran this simulation earler
and have CSVs, so
we're just gonna use those from now on

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

def create_genetic_colormap():
    syn = mcolors.LinearSegmentedColormap.from_list('syn', ['#00FF00', '#FBFF02'])(np.linspace(0, 1, 256))
    interp = mcolors.LinearSegmentedColormap.from_list('interp', ['#1100FF', '#00FFF2'])(np.linspace(0, 1, 256))
    dest = mcolors.LinearSegmentedColormap.from_list('dest', ['#FFAE00', '#FF0000'])(np.linspace(0, 1, 256))
    combined = np.vstack((syn, interp, dest))
    return mcolors.LinearSegmentedColormap.from_list('GeneticLandscape', combined)

def generate_diagnostic_report(df: pd.DataFrame, out_path: Path):
    total = len(df)
    accepted = df[df['Mutation_Accepted'] == True]
    rejected = df[df['Mutation_Accepted'] == False]
    
    m_syn = df[df['Final_RPI'] < 0]
    m_int = df[(df['Final_RPI'] >= 0) & (df['Final_RPI'] <= 1)]
    m_des = df[df['Final_RPI'] > 1]

    report = [
        "PHASE D & E: HIGH-INTENSITY LAMARCKIAN DIAGNOSTIC",
        "=================================================\n",
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

def plot_continuous_heatmaps(df: pd.DataFrame, out_dir: Path, target_col: str, prefix: str):
    custom_map = create_genetic_colormap()
    for res in [40, 80]:
        statistic, x_edges, y_edges, _ = binned_statistic_2d(
            df["Best_Parent_Cost"], df["Parental_Gap"], df[target_col].clip(-1, 2), 
            statistic='mean', bins=res
        )

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(
            statistic.T, origin='lower', extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]],
            aspect='auto', cmap=custom_map, vmin=-1, vmax=2
        )
        ax.set_xlabel("Best Parent Cost")
        ax.set_ylabel("Parental Gap")
        ax.set_title(f"Continuous Performance Heatmap: {prefix} ({res}x{res})")
        
        cbar = plt.colorbar(im)
        cbar.set_ticks([-0.5, 0.5, 1.5])
        cbar.set_ticklabels(['Synergy', 'Interpolation', 'Destructive'])
        
        filename = f"{prefix.lower().replace(' ', '_')}_heatmap_{res}x{res}.png"
        plt.savefig(out_dir / filename, dpi=300)
        plt.close()

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
    
    filename = f"{prefix.lower().replace(' ', '_')}_partition_map.png"
    plt.savefig(out_dir / filename, dpi=300)
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
    
    # Export 1: All proposals
    df.to_csv(out_dir / "lamarckian_all_proposals.csv", index=False)
    
    # Export 2: Strictly accepted mutations
    df[df['Mutation_Accepted']].to_csv(out_dir / "lamarckian_accepted_mutations.csv", index=False)
    
    generate_diagnostic_report(df, out_dir / "gate_diagnostic_report.txt")
    
    plot_continuous_heatmaps(df, out_dir, "Child_RPI", "Raw Child")
    plot_continuous_heatmaps(df, out_dir, "Final_RPI", "Final Child")
    
    plot_smooth_partition_map(df, out_dir, "Child_RPI", "Raw Child")
    plot_smooth_partition_map(df, out_dir, "Final_RPI", "Final Child")
    
    plot_cost_parity(df, out_dir)

if __name__ == "__main__":
    run_analysis(iterations=50000)
"""

"""
offline_visualizer.py

Full three-tier diagnostic suite.
Tier 1: Pre-Mutation (Unfiltered)
Tier 2: Post-Mutation (Accepted)
Tier 3: Topological Intersection (Transitions)

Color Harmonies:
- Synergy: Yellow (#FBBC05) to Green (#34A853)
- Interpolation: Cyan ("#4FE5F9") to Blue (#4285F4)
- Destructive: Red (#EA4335) to Orange (#FF6D00)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from scipy.stats import binned_statistic_2d, gaussian_kde
from pathlib import Path

# --- GOOGLE BRANDING & HARMONIES ---
G_GREEN  = '#00906c'
G_BLUE   = "#5151fc"
G_RED    = "#ff4632"
G_YELLOW = "#Ffea00"
G_CYAN   = "#00e1f3"
G_ORANGE = "#ff9800"

# --- COLOR TOOLS ---

def create_gradient_genetic_cmap():
    """
    Creates three distinct gradients with hard boundaries.
    Synergy: Yellow -> Green
    Interpolation: Cyan -> Blue
    Destructive: Red -> Orange
    """
    syn_grads = mcolors.LinearSegmentedColormap.from_list('syn', [G_YELLOW, G_GREEN])(np.linspace(0, 1, 256))
    int_grads = mcolors.LinearSegmentedColormap.from_list('int', [G_CYAN, G_BLUE])(np.linspace(0, 1, 256))
    des_grads = mcolors.LinearSegmentedColormap.from_list('des', [G_RED, G_ORANGE])(np.linspace(0, 1, 256))
    
    cmap = mcolors.ListedColormap(np.vstack((syn_grads, int_grads, des_grads)))
    norm = mcolors.BoundaryNorm([-1.0, 0.0, 1.0, 2.0], cmap.N)
    return cmap, norm

def create_impact_colormap():
    return mcolors.LinearSegmentedColormap.from_list('impact', ['#FFFFFF', G_YELLOW, G_RED])

# --- GRID CALCULATION ---

def get_kde_grid(df, rpi_col, xx, yy, positions):
    """Generates state grid. Uses subsampling to resolve latency issues."""
    # Subsample for KDE speed-up if dataset is large
    sample_size = min(len(df), 5000)
    df_sub = df.sample(n=sample_size, random_state=42)
    
    syn = df_sub[df_sub[rpi_col] < 0]
    interp = df_sub[(df_sub[rpi_col] >= 0) & (df_sub[rpi_col] <= 1)]
    dest = df_sub[df_sub[rpi_col] > 1]
    
    stack = []
    for subset in [syn, interp, dest]:
        if len(subset) > 10:
            kde = gaussian_kde(np.vstack([subset['Best_Parent_Cost'], subset['Parental_Gap']]))
            stack.append(kde(positions) * (len(subset) / len(df_sub)))
        else:
            stack.append(np.zeros_like(xx.ravel()))
    
    Z = np.argmax(np.vstack(stack), axis=0).reshape(xx.shape)
    total_density = np.sum(np.vstack(stack), axis=0).reshape(xx.shape)
    return np.ma.masked_where(total_density < 1e-10, Z)

# --- PLOTTING SUITE ---

def plot_performance_suite(df, out_dir, prefix, rpi_col, bounds):
    cmap, norm = create_gradient_genetic_cmap()
    range_bins = [[bounds['x_min'], bounds['x_max']], [bounds['y_min'], bounds['y_max']]]
    
    for res in [20, 40, 60, 80, 100]:
        stat, x_edges, y_edges, _ = binned_statistic_2d(
            df["Best_Parent_Cost"], df["Parental_Gap"], df[rpi_col].clip(-1, 2), 
            statistic='mean', bins=res, range=range_bins
        )
        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(stat.T, origin='lower', extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]],
                       aspect='auto', cmap=cmap, norm=norm)
        
        ax.set_title(f"{prefix} Performance Heatmap ({res}x{res})")
        cbar = plt.colorbar(im, ax=ax, spacing='proportional')
        cbar.set_ticks([-0.5, 0.5, 1.5])
        cbar.set_ticklabels(['Synergy', 'Interpolation', 'Destructive'])
        plt.savefig(out_dir / f"{prefix.lower()}_heatmap_{res}x{res}.png", dpi=300)
        plt.close()

    xx, yy = np.meshgrid(np.linspace(bounds['x_min'], bounds['x_max'], 300),
                         np.linspace(bounds['y_min'], bounds['y_max'], 300))
    grid = get_kde_grid(df, rpi_col, xx, yy, np.vstack([xx.ravel(), yy.ravel()]))
    
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.contourf(xx, yy, grid, levels=[-0.5, 0.5, 1.5, 2.5], colors=[G_GREEN, G_BLUE, G_RED], alpha=0.5)
    ax.set_title(f"{prefix} Partition Map")
    handles = [mpatches.Patch(color=c, alpha=0.5, label=l) for c, l in zip([G_GREEN, G_BLUE, G_RED], ['Synergy', 'Interpolation', 'Destructive'])]
    ax.legend(handles=handles, loc='upper right')
    plt.savefig(out_dir / f"{prefix.lower()}_partition_map.png", dpi=300)
    plt.close()

def plot_transition_suite(df_all, out_dir, bounds):
    df_all['Impact_Delta'] = df_all['Raw_Cost'] - df_all['Final_Cost']
    xx, yy = np.meshgrid(np.linspace(bounds['x_min'], bounds['x_max'], 300),
                         np.linspace(bounds['y_min'], bounds['y_max'], 300))
    pos = np.vstack([xx.ravel(), yy.ravel()])
    grid_pre = get_kde_grid(df_all, 'Child_RPI', xx, yy, pos)
    grid_post = get_kde_grid(df_all[df_all['Mutation_Accepted']], 'Final_RPI', xx, yy, pos)

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.contourf(xx, yy, (grid_pre == 0) & (grid_post == 0), levels=[0.5, 1.5], colors=['#1e6130'], alpha=0.7) 
    ax.contourf(xx, yy, (grid_pre == 1) & (grid_post == 0), levels=[0.5, 1.5], colors=[G_GREEN], alpha=0.8) 
    ax.contourf(xx, yy, (grid_pre == 1) & (grid_post == 1), levels=[0.5, 1.5], colors=[G_BLUE], alpha=0.4) 
    ax.contourf(xx, yy, (grid_pre == 2) & (grid_post <= 1), levels=[0.5, 1.5], colors=[G_YELLOW], alpha=0.7) 
    ax.contourf(xx, yy, (grid_pre == 2) & (grid_post == 2), levels=[0.5, 1.5], colors=[G_RED], alpha=0.5) 
    ax.contourf(xx, yy, (grid_pre <= 1) & (grid_post == 2), levels=[0.5, 1.5], colors=['#000000'], alpha=0.8) 

    handles = [
        mpatches.Patch(color='#085e55', alpha=0.7, label='Synergy -> Synergy (Stable)'),
        mpatches.Patch(color=G_GREEN, alpha=0.8, label='Interp -> Synergy (Improved)'),
        mpatches.Patch(color=G_BLUE, alpha=0.4, label='Interp -> Interp (Stable)'),
        mpatches.Patch(color=G_YELLOW, alpha=0.7, label='Destruct -> Rescued'),
        mpatches.Patch(color=G_RED, alpha=0.5, label='Destruct (Stable Failure)'),
        mpatches.Patch(color='#090909', alpha=0.8, label='Catastrophic Degradation')
    ]
    ax.legend(handles=handles, loc='center left', bbox_to_anchor=(1, 0.5))
    ax.set_title("Topological Mutation Transitions")
    plt.tight_layout()
    plt.savefig(out_dir / "mutation_state_transitions_intersection.png", dpi=300)
    plt.close()

def write_reports(df_all, df_acc, out_dir):
    s1 = {'syn': (df_all['Child_RPI'] < 0).mean()*100, 'cost': df_all['Raw_Cost'].mean()}
    s2 = {'syn': (df_acc['Final_RPI'] < 0).mean()*100, 'cost': df_acc['Final_Cost'].mean()}
    report = [
        "TIER 1: PRE-MUTATION", f"Synergy Rate: {s1['syn']:.2f}% | Mean Cost: {s1['cost']:.4f}\n",
        "TIER 2: POST-MUTATION", f"Synergy Rate: {s2['syn']:.2f}% | Mean Cost: {s2['cost']:.4f}\n",
        "TIER 3: TRANSITIONS", f"Acceptance: {(len(df_acc)/len(df_all))*100:.2f}% | Gain: {s1['cost'] - s2['cost']:.6f}"
    ]
    (out_dir / "diagnostic_report.txt").write_text("\n".join(report))

if __name__ == "__main__":
    out_dir = Path("test/parent-child_relationship")
    df_all = pd.read_csv(out_dir / "lamarckian_all_proposals.csv")
    df_acc = pd.read_csv(out_dir / "lamarckian_accepted_mutations.csv")
    bounds = {'x_min': df_all['Best_Parent_Cost'].min(), 'x_max': df_all['Best_Parent_Cost'].max(),
              'y_min': df_all['Parental_Gap'].min(), 'y_max': df_all['Parental_Gap'].max()}
    plot_performance_suite(df_all, out_dir, "Pre_Mutation", "Child_RPI", bounds)
    plot_performance_suite(df_acc, out_dir, "Post_Mutation", "Final_RPI", bounds)
    plot_transition_suite(df_all, out_dir, bounds)
    write_reports(df_all, df_acc, out_dir)