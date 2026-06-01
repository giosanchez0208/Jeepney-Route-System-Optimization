import copy
import yaml
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import traceback

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.route import RouteGenerator
from utils.simulation import SimulationEvaluator
from utils.travel_graph import TravelGraph

CITY_GRAPH_BBOX = (8.1500, 8.3300, 124.1500, 124.4000)
CITY_GRAPH_NAME = "Iligan City"
CITY_GRAPH_PBF_PATH = "utils/data/iligan-city.pbf"
CITY_GRAPH_CACHE_PREFIX = "iligan_arterial"
ROUTES_PER_TRIAL = 3
MAX_ROUTE_BUILD_ATTEMPTS = ROUTES_PER_TRIAL * 20
TRIALS_PER_RATE = 10
STABILITY_RATIO = 0.10
STABILITY_WINDOW = 2

# ==============================================================================
# ZERO-PICKLE WORKER FUNCTION
# ==============================================================================
def _build_city_graph(verbose: bool = False) -> CityGraph:
    return CityGraph(
        name=CITY_GRAPH_NAME,
        bbox=CITY_GRAPH_BBOX,
        pbf_path=CITY_GRAPH_PBF_PATH,
        cache_prefix=CITY_GRAPH_CACHE_PREFIX,
        verbose=verbose,
    )


def _prewarm_city_graph_cache() -> None:
    _build_city_graph(verbose=False)


def _run_abm_variance_trial(rate: float, trial_idx: int, config_dict: dict):
    """
    Executes a heavy ABM trial entirely in local memory to prevent serialization corruption.
    Isolates passenger stochasticity by using a fixed route topology.
    """
    try:
        # 1. Clear the A* cache to prevent cross-contamination
        try:
            TravelGraph.findShortestJourney.cache_clear()
        except AttributeError:
            pass

        # 2. Rebuild the Infrastructure Locally (Zero-Pickle)
        city = _build_city_graph(verbose=False)
        sampler = DirectDemandSampler(city, config=DDMConfig(), verbose=False)
        rg = RouteGenerator(city, sampler, verbose=False)

        # 3. Natively Generate 3 Valid Routes (FIXED TOPOLOGY)
        # We use a hardcoded seed so every trial tests the EXACT same 3 routes.
        # This guarantees that the variance we measure comes strictly from passenger 
        # spawn stochasticity, not from different route layouts.
        random.seed(42)
        np.random.seed(42)

        routes = []
        route_attempts = 0
        route_error = None
        try:
            while len(routes) < ROUTES_PER_TRIAL and route_attempts < MAX_ROUTE_BUILD_ATTEMPTS:
                route_attempts += 1
                try:
                    r = rg.generate(n_points=5)
                except ValueError as exc:
                    route_error = exc
                    continue

                if hasattr(r, "path") and r.path and len(r.path) > 0:
                    routes.append(r)

            if len(routes) < ROUTES_PER_TRIAL:
                raise RuntimeError(
                    f"[ABM VARIANCE] Failed to generate {ROUTES_PER_TRIAL} valid routes "
                    f"after {route_attempts} attempts. Last error: {route_error}"
                )
        finally:
            random.seed()
            np.random.seed()

        # 4. Reset to stochastic defaults before the passenger simulation.
        # Override the spawn rate for this specific trial
        trial_config = copy.deepcopy(config_dict)
        trial_config.setdefault("simulation", {})
        trial_config["simulation"]["spawn_rate_per_hour"] = float(rate)
        
        # 5. Evaluate the full ABM Simulation
        sim_eval = SimulationEvaluator(trial_config, city, None, sampler)
        sim_res = sim_eval.evaluate(routes, verbose=False)
        
        completed = int(sim_res.metrics.get("completed_count", 0) or 0)
        if completed <= 0:
            raise ValueError("[ABM VARIANCE] Simulation completed zero passengers; normalized fitness is undefined.")
        norm_fitness = sim_res.fitness_score / completed

        return rate, trial_idx, norm_fitness, None

    except Exception:
        return rate, trial_idx, None, traceback.format_exc()

# ==============================================================================
# ORCHESTRATOR
# ==============================================================================
def empirical_abm_calibration() -> pd.DataFrame:
    print("Loading simulation config (profile_p1.yaml)...")
    with open("configs/profile_p1.yaml", "r") as f:
        config_dict = yaml.safe_load(f)

    print("Prewarming shared CityGraph cache...")
    _prewarm_city_graph_cache()

    # Test rates from 50 to 400 passengers per hour
    spawn_rates = [50, 100, 150, 200, 250, 300, 400]

    cores = max(1, multiprocessing.cpu_count() - 2)
    total_tasks = len(spawn_rates) * TRIALS_PER_RATE
    
    print(f"Blasting {total_tasks} heavy ABM simulation trials across {cores} CPU cores...")
    print("Note: Workers are rebuilding local graphs. The first batch may take a moment.")
    
    results_map = {r: [] for r in spawn_rates}
    
    with ProcessPoolExecutor(max_workers=cores) as executor:
        futures = []
        for rate in spawn_rates:
            for k in range(TRIALS_PER_RATE):
                futures.append(executor.submit(_run_abm_variance_trial, rate, k, config_dict))
                
        for future in as_completed(futures):
            rate, trial_idx, norm_fitness, err_trace = future.result()
            
            if err_trace:
                print(f"\n  -> [!] Rate {rate} Trial {trial_idx+1} FAILED:")
                print(err_trace)
            else:
                results_map[rate].append(norm_fitness)
                print(f"  -> Completed [Rate: {rate:3.0f}] Trial {trial_idx+1}: Normalized ABM Fitness = {norm_fitness:.2f}")

    # Aggregate Data
    mean_fitness = []
    std_fitness = []
    trial_counts = []
    
    for rate in spawn_rates:
        scores = results_map[rate]
        trial_counts.append(len(scores))
        if len(scores) == TRIALS_PER_RATE:
            mean_fitness.append(float(np.mean(scores)))
            std_fitness.append(float(np.std(scores)))
        else:
            mean_fitness.append(np.nan)
            std_fitness.append(np.nan)

    if any(count != TRIALS_PER_RATE for count in trial_counts):
        incomplete_rates = [rate for rate, count in zip(spawn_rates, trial_counts) if count != TRIALS_PER_RATE]
        print(f"\n[!] Incomplete trial counts detected for rates: {incomplete_rates}. Collapse detection will ignore them.")
        
    return pd.DataFrame({
        'spawn_rate': spawn_rates,
        'mean_fitness': mean_fitness,
        'std_fitness': std_fitness,
        'trial_count': trial_counts
    })

def _find_sustained_collapse(df: pd.DataFrame) -> tuple[float | None, float | None]:
    if df.empty:
        return None, None

    stable_mask = (
        df['trial_count'].eq(TRIALS_PER_RATE)
        & df['mean_fitness'].notna()
        & df['std_fitness'].notna()
        & (df['std_fitness'] <= STABILITY_RATIO * df['mean_fitness'])
    )

    run_length = 0
    for idx, is_stable in enumerate(stable_mask.tolist()):
        if is_stable:
            run_length += 1
            if run_length >= STABILITY_WINDOW:
                start_idx = idx - STABILITY_WINDOW + 1
                row = df.iloc[start_idx]
                return float(row['spawn_rate']), float(row['mean_fitness'])
        else:
            run_length = 0

    return None, None

def plot_variance_collapse(df: pd.DataFrame):
    if df.empty: return

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
    
    color_main = '#2A9D8F' 

    complete_df = df[df['trial_count'].eq(TRIALS_PER_RATE)].copy()
    if complete_df.empty:
        raise RuntimeError("[ABM VARIANCE] No spawn-rate bucket completed the full trial count; refusing to plot a false collapse threshold.")

    x = complete_df['spawn_rate'].values
    y = complete_df['mean_fitness'].values
    err = complete_df['std_fitness'].values
    
    # Plot Mean Line
    ax.plot(x, y, color=color_main, linewidth=3, marker='o', markersize=8, 
            markeredgecolor='white', markeredgewidth=1.5, label=r'Mean $F_{sim} / N$')
            
    # Overlay Variance Error Bands (± 1 Sigma)
    ax.fill_between(x, y - err, y + err, color=color_main, alpha=0.2, label=r'$\pm 1 \sigma$ Error Band')
    
    # Algorithmic Selection: require sustained stability across consecutive complete rates.
    collapse_rate, collapse_mean = _find_sustained_collapse(complete_df)
    if collapse_rate is not None:
        max_err = float(np.nanmax(err)) if np.any(np.isfinite(err)) else 0.0
        
        ax.axvline(x=collapse_rate, color='black', linestyle='--', linewidth=2, alpha=0.8)
        ax.annotate('Variance Collapse Threshold\n(Fidelity Achieved)',
                    xy=(collapse_rate, collapse_mean),
                    xytext=(collapse_rate + 20, collapse_mean + max_err * 0.8),
                    arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8),
                    fontsize=12, fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="black", lw=1.2, alpha=0.9))
    else:
        ax.text(
            0.02,
            0.98,
            "No sustained collapse threshold met",
            transform=ax.transAxes,
            ha='left',
            va='top',
            fontsize=11,
            fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#333333", lw=1.0, alpha=0.9),
        )
                    
    ax.set_xlabel('Passenger Spawn Rate (Passengers/Hour)', fontsize=14, fontweight='bold', labelpad=12)
    ax.set_ylabel(r'Mean Normalized ABM Fitness ($F_{sim} / N$)', fontsize=14, fontweight='bold', labelpad=12)
    ax.tick_params(labelsize=12)
    
    ax.grid(True, which='both', linestyle=':', linewidth=1, alpha=0.6)
    ax.legend(loc='upper right', fontsize=12, frameon=True, shadow=True, borderpad=1, edgecolor='#333333')
    plt.title('ABM Simulation Fidelity: Stochastic Variance Collapse', fontsize=16, fontweight='bold', pad=20)
    
    output_dir = Path('documentation/phase_3')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'fig_7_simulation_variance_collapse.png'
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    print(f"\nVisualization successfully generated and saved to: {output_path.absolute()}")
    plt.close()

if __name__ == "__main__":
    print("===============================================================")
    print("CRITICAL: Executing multi-core ABM Simulation Variance Test.")
    print("===============================================================\n")
    
    response = input("Press Enter to execute the heavy ABM simulation (or type 'q' to quit)... ")
    if response.lower() != 'q':
        data = empirical_abm_calibration()
        plot_variance_collapse(data)
        print("Process complete.")
