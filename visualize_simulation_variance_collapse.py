import os
import sys
import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.route import RouteGenerator
from utils.simulation import SimulationEvaluator
from utils.travel_graph import TravelGraph

# ==============================================================================
# TOP-LEVEL WORKER FUNCTION
# Must be at the top level so Python can pickle it and send it to other CPU cores.
# ==============================================================================
def _run_abm_trial(evaluator: SimulationEvaluator, routes: list, rate: int, trial_idx: int):
    # ADD THIS LINE: Ensure true isolated trials
    TravelGraph.findShortestJourney.cache_clear()
    
    evaluator.spawn_rate = rate
    result = evaluator.evaluate(routes, verbose=False)
    
    completed_count = result.metrics.get('completed_count', 0)
    norm_fitness = result.fitness_score / max(1, completed_count)
    
    return rate, trial_idx, norm_fitness, completed_count

def empirical_abm_calibration() -> pd.DataFrame:
    """
    Empirically calibrates the ABM fidelity by measuring the variance 
    collapse as passenger volume increases (Accelerated via Multiprocessing).
    """
    print("Instantiating Infrastructure for ABM Calibration...")
    bbox = (8.1500, 8.3300, 124.1500, 124.4000)
    city = CityGraph(name="Iligan City", bbox=bbox, pbf_path="utils/data/iligan-city.pbf", cache_prefix="iligan_arterial")
    
    config = DDMConfig()
    sampler = DirectDemandSampler(city, config=config)
    rg = RouteGenerator(city, sampler)

    print("Generating 3 baseline transit routes to keep computation light...")
    routes = [rg.generate(n_points=5) for _ in range(3)]
    
    print("Loading simulation config (profile_p1.yaml)...")
    with open("configs/profile_p1.yaml", "r") as f:
        sim_config = yaml.safe_load(f)
        
    print("Instantiating Simulation Evaluator...")
    evaluator = SimulationEvaluator(sim_config, city, None, sampler)
    
    spawn_rates = [25, 50, 100, 200, 300, 400]
    results_map = {r: [] for r in spawn_rates}
    
    cpu_cores = os.cpu_count() or 4
    print(f"\nExecuting Variance vs. Volume Trials concurrently across {cpu_cores} CPU cores...")
    
    # ==========================================================================
    # PARALLEL EXECUTION BLOCK
    # ==========================================================================
    with ProcessPoolExecutor(max_workers=cpu_cores) as executor:
        futures = []
        
        # Submit all 18 trials (6 rates * 3 trials) to the processing pool immediately
        for rate in spawn_rates:
            for k in range(3):
                futures.append(executor.submit(_run_abm_trial, evaluator, routes, rate, k))
        
        # Capture results as they finish (order is not guaranteed, so we map them back)
        for future in as_completed(futures):
            try:
                rate, trial_idx, norm_fitness, completed_count = future.result()
                results_map[rate].append(norm_fitness)
                print(f"  -> [Rate {rate:3d}] Trial {trial_idx+1}/3: Normalized Fitness = {norm_fitness:8.4f} (Completed: {completed_count})")
            except Exception as e:
                print(f"  -> [!] A worker process failed: {e}")

    # ==========================================================================
    # AGGREGATION
    # ==========================================================================
    mean_fitness = []
    std_fitness = []
    
    for rate in spawn_rates:
        scores = results_map[rate]
        # Safety fallback in case a process crashed
        mean_fitness.append(np.mean(scores) if len(scores) > 0 else 0.0)
        std_fitness.append(np.std(scores) if len(scores) > 0 else 0.0)
        
    return pd.DataFrame({
        'spawn_rate': spawn_rates,
        'mean_fitness': mean_fitness,
        'std_fitness': std_fitness
    })

def plot_variance_collapse(df: pd.DataFrame):
    """
    Generates a high-resolution Line Chart with Error Bands to prove 
    the stochastic variance collapse of the ABM fidelity.
    """
    # Setup pristine academic theme
    sns.set_theme(style="white", rc={
        "font.family": "serif", 
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#333333",
        "text.color": "#333333"
    })
    
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Bold dark cyan
    color_main = '#2A9D8F' 
    
    x = df['spawn_rate']
    y = df['mean_fitness']
    err = df['std_fitness']
    
    # Plot Mean Line
    ax.plot(x, y, color=color_main, linewidth=3, marker='o', markersize=8, 
            markeredgecolor='white', markeredgewidth=1.5, label=r'Mean $F_{sim} / N$')
            
    # Overlay Variance Error Bands (± 1 Sigma)
    ax.fill_between(x, y - err, y + err, color=color_main, alpha=0.2, label=r'$\pm 1 \sigma$ Error Band')
    
    # Axes Formatting
    ax.set_xlabel('Passenger Spawn Rate (Passengers/Hour)', fontsize=14, fontweight='bold', labelpad=12)
    ax.set_ylabel(r'Mean Normalized Simulation Fitness ($F_{sim} / N$)', fontsize=14, fontweight='bold', labelpad=12)
    ax.tick_params(labelsize=12)
    
    # Algorithmically find where the standard deviation drops below a stable threshold (< 15% of the mean)
    stable_points = df[df['std_fitness'] < 0.15 * df['mean_fitness']]
    if not stable_points.empty:
        collapse_rate = stable_points.iloc[0]['spawn_rate']
        collapse_mean = stable_points.iloc[0]['mean_fitness']
        
        # Plot vertical dashed line
        ax.axvline(x=collapse_rate, color='black', linestyle='--', linewidth=2, alpha=0.8)
        
        # Annotate prominently
        ax.annotate('Variance Collapse Threshold\n(Fidelity Achieved)',
                    xy=(collapse_rate, collapse_mean),
                    xytext=(collapse_rate + 20, collapse_mean + np.max(err)*0.6),
                    arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8),
                    fontsize=12, fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black", lw=1.2, alpha=0.9))
                    
    # Grid, Legend & Title
    ax.grid(True, which='both', linestyle=':', linewidth=1, alpha=0.6)
    ax.legend(loc='upper right', fontsize=12, frameon=True, shadow=True, borderpad=1, edgecolor='#333333')
    plt.title('Simulation Fidelity Calibration: Variance Collapse vs Volume', fontsize=16, fontweight='bold', pad=20)
    
    # Save Output
    output_dir = Path('documentation/phase_3')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'fig_7_simulation_variance_collapse.png'
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    print(f"\nVisualization successfully generated and saved to: {output_path.absolute()}")
    plt.close()

if __name__ == "__main__":
    print("===============================================================")
    print("CRITICAL: This script runs the heavy Agent-Based Simulation evaluator.")
    print("It will execute K=3 independent trials across 6 spawn rate steps.")
    print("This may take a significant amount of time depending on the machine.")
    print("===============================================================\n")
    
    # CRITICAL SAFETY CONSTRAINT: Manual confirmation prompt
    response = input("Press Enter to execute the heavy ABM simulation (or type 'q' to quit)... ")
    
    if response.lower() == 'q':
        print("Execution cancelled by user.")
    else:
        # Proceed with execution
        calibration_data = empirical_abm_calibration()
        plot_variance_collapse(calibration_data)
        print("Process complete.")