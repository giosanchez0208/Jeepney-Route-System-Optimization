import os
import sys
import time
import random
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from utils.city_graph import CityGraph
from utils.travel_graph import TravelGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.route import RouteGenerator

# ==============================================================================
# TOP-LEVEL WORKER FUNCTION
# Must be at the top level so Python can pickle it and send it to other CPU cores.
# ==============================================================================
def _run_mohring_trial(tg, sampler, routes, l1_keys, l3_keys, N, trial_idx):
    """
    Isolated worker task. Clears the local A* cache, runs the demand sampling, 
    and returns the Mohring allocation back to the main process.
    """
    # CRITICAL: Clear cache so the runtime metric is accurate, not artificially fast
    tg.findShortestJourney.cache_clear() 
    
    start_time = time.time()
    route_demand = {r: 0.0 for r in routes}

    # Sample and Route N Passengers
    for _ in range(N):
        origin = sampler.get_point()
        dest = sampler.get_point()
        
        start = tg.l1_nodes.get((origin.lon, origin.lat)) or tg.l1_nodes[random.choice(l1_keys)]
        end = tg.l3_nodes.get((dest.lon, dest.lat)) or tg.l3_nodes[random.choice(l3_keys)]

        journey = tg.findShortestJourney(start, end)
        if journey:
            for edge in journey:
                if edge.id.startswith("RI"):
                    try:
                        r_idx = int(edge.id.split("_")[1][1:])
                        route_demand[routes[r_idx]] += 1.0
                    except:
                        pass
    
    # Mohring Allocation (Supply = 50)
    route_tau = {r: math.sqrt(max(1.0, demand)) for r, demand in route_demand.items()}
    total_sqrt_tau = sum(route_tau.values()) or 1.0
    allocation = {r: max(1, int(50 * (route_tau[r] / total_sqrt_tau))) for r in routes}
    
    runtime = time.time() - start_time
    return N, trial_idx, allocation, runtime

# ==============================================================================
# DATA GENERATOR & ORCHESTRATOR
# ==============================================================================
def get_real_calibration_data() -> pd.DataFrame:
    print("Instantiating Infrastructure for Calibration...")
    bbox = (8.1500, 8.3300, 124.1500, 124.4000)
    city = CityGraph(name="Iligan City", bbox=bbox, pbf_path="utils/data/iligan-city.pbf", cache_prefix="iligan_arterial")
    
    config = DDMConfig()
    sampler = DirectDemandSampler(city, config=config)
    rg = RouteGenerator(city, sampler)

    print("Generating 5 transit loops...")
    routes = [rg.generate(n_points=5) for _ in range(5)]

    updated_weights = {'walk_wt': 0.5630, 'ride_wt': 0.00632, 'wait_wt': 14.44, 'transfer_wt': 15.78, 'direct_wt': 0.0, 'alight_wt': 0.0}
    tg = TravelGraph(cg=city, config=updated_weights, routes=routes)

    l1_keys = list(tg.l1_nodes.keys())
    l3_keys = list(tg.l3_nodes.keys())

    sample_sizes = list(range(50, 550, 50))
    
    # INCREASED TRIALS: 10 trials per N mathematically guarantees a smooth variance curve
    NUM_TRIALS = 10 
    
    cpu_cores = os.cpu_count() or 4
    print(f"\nExecuting Variance vs. Runtime Trials concurrently across {cpu_cores} CPU cores...")
    
    results_map = {N: {'allocations': [], 'runtimes': []} for N in sample_sizes}

    # Parallel Execution Block
    with ProcessPoolExecutor(max_workers=cpu_cores) as executor:
        futures = []
        
        # Submit all tasks (100 total tasks = 10 sample sizes * 10 trials)
        for N in sample_sizes:
            for k in range(NUM_TRIALS):
                futures.append(executor.submit(_run_mohring_trial, tg, sampler, routes, l1_keys, l3_keys, N, k))
        
        # Gather results as they finish
        for future in as_completed(futures):
            try:
                N, trial_idx, allocation, runtime = future.result()
                results_map[N]['allocations'].append(allocation)
                results_map[N]['runtimes'].append(runtime)
                print(f"  -> [N={N:3d}] Trial {trial_idx+1}/{NUM_TRIALS} Completed in {runtime:.2f}s")
            except Exception as e:
                print(f"  -> [!] A worker process failed: {e}")

    # Aggregate Stats
    mean_std_devs = []
    mean_runtimes = []
    
    for N in sample_sizes:
        trial_allocs = results_map[N]['allocations']
        trial_runtimes = results_map[N]['runtimes']
        
        if trial_allocs:
            # Map back to routes to calculate standard deviation per route
            route_allocs = {r: [] for r in routes}
            for alloc in trial_allocs:
                for r, count in alloc.items():
                    route_allocs[r].append(count)
            
            route_stdevs = [np.std(counts) for counts in route_allocs.values()]
            mean_std_devs.append(np.mean(route_stdevs))
        else:
            mean_std_devs.append(0.0)
            
        mean_runtimes.append(np.mean(trial_runtimes) if trial_runtimes else 0.0)

    return pd.DataFrame({
        'N': sample_sizes,
        'mean_std_dev': mean_std_devs,
        'mean_runtime': mean_runtimes
    })


def plot_mohring_calibration(df: pd.DataFrame):
    """
    Generates a high-resolution, dual-axis elbow plot for variance vs runtime.
    """
    sns.set_theme(style="white", rc={
        "font.family": "serif", 
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#333333",
        "text.color": "#333333"
    })
    
    fig, ax1 = plt.subplots(figsize=(12, 8), dpi=300)
    fig.patch.set_facecolor('white')
    ax1.set_facecolor('white')
    
    # LEFT Y-AXIS (Variance)
    color_var = '#1E88E5' 
    ax1.set_xlabel('OD Sample Size ($N$)', fontsize=14, fontweight='bold', labelpad=12)
    ax1.set_ylabel(r'Mean Standard Deviation of Fleet Allocation ($\sigma$)', color=color_var, fontsize=14, fontweight='bold', labelpad=12)
    
    line_var, = ax1.plot(df['N'], df['mean_std_dev'], color=color_var, linewidth=3, 
                         marker='o', markersize=8, markeredgecolor='white', markeredgewidth=1.5,
                         label=r'Mean Std. Deviation ($\sigma$)')
    ax1.tick_params(axis='y', labelcolor=color_var, labelsize=12)
    ax1.tick_params(axis='x', labelsize=12)
    
    ax1.axhline(y=0.5, color='gray', linestyle='--', linewidth=1.5, alpha=0.8)
    ax1.text(df['N'].max(), 0.52, r'Stability Threshold ($\sigma = 0.5$)', color='gray', 
             fontsize=11, ha='right', va='bottom', style='italic')

    # RIGHT Y-AXIS (Runtime)
    ax2 = ax1.twinx()
    color_time = '#D90429' 
    ax2.set_ylabel('Mean Computation Time (Seconds)', color=color_time, fontsize=14, fontweight='bold', labelpad=12)
    
    line_time, = ax2.plot(df['N'], df['mean_runtime'], color=color_time, linewidth=3, 
                          marker='s', markersize=7, markeredgecolor='white', markeredgewidth=1.5,
                          label='Mean Runtime (s)')
    ax2.tick_params(axis='y', labelcolor=color_time, labelsize=12)
    
    # ALGORITHMIC SELECTION: Look for SUSTAINED stability (current and next point are below 0.5)
    optimal_n = None
    optimal_sigma = None
    
    for i in range(len(df) - 1):
        if df['mean_std_dev'].iloc[i] <= 0.5 and df['mean_std_dev'].iloc[i+1] <= 0.5:
            optimal_n = df['N'].iloc[i]
            optimal_sigma = df['mean_std_dev'].iloc[i]
            break
            
    # Fallback if sustained stability isn't reached, just pick the first point < 0.5
    if optimal_n is None:
        sweet_spot_df = df[df['mean_std_dev'] <= 0.5]
        if not sweet_spot_df.empty:
            optimal_n = sweet_spot_df.iloc[0]['N']
            optimal_sigma = sweet_spot_df.iloc[0]['mean_std_dev']

    if optimal_n is not None:
        ax1.axvline(x=optimal_n, color='black', linestyle='--', linewidth=2, alpha=0.85)
        ax1.annotate(f'Optimal Sample Size ($N={optimal_n}$)\n| Pareto Frontier',
                     xy=(optimal_n, optimal_sigma),
                     xytext=(optimal_n + 50, optimal_sigma + 0.3),
                     arrowprops=dict(facecolor='black', shrink=0.05, width=2, headwidth=8),
                     fontsize=12, fontweight='bold',
                     bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black", lw=1.2, alpha=0.9))

    # Grid, Legend & Title
    ax1.grid(True, which='both', axis='x', linestyle=':', linewidth=1, alpha=0.6)
    ax1.grid(True, which='both', axis='y', linestyle=':', linewidth=1, alpha=0.6)
    
    lines = [line_var, line_time]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper center', bbox_to_anchor=(0.5, 0.95), 
               fontsize=12, frameon=True, shadow=True, borderpad=1, edgecolor='#333333')
    
    plt.title('Mohring Allocation Stability vs. Computational Runtime', fontsize=18, fontweight='bold', pad=25)
    
    output_dir = Path('documentation/phase_3')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'fig_6_mohring_variance_calibration.png'
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    print(f"\nVisualization successfully generated and saved to: {output_path.absolute()}")
    plt.close()

if __name__ == "__main__":
    print("Executing empirical A* trials for Mohring sample size calibration (Multiprocessing Enabled)...")
    calibration_data = get_real_calibration_data() 
    
    print("Engineering dual-axis visualization...")
    plot_mohring_calibration(calibration_data)
    print("Process complete.")