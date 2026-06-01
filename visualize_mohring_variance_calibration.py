"""
Mohring Allocation Sample-Size Calibration

Purpose
-------
Runs repeated OD-sampling trials to estimate how OD sample size N affects:
1. Stability of Mohring fleet allocation, measured by mean route-level standard deviation.
2. Runtime cost, measured by mean computation time per trial.

Important corrections from the earlier version
----------------------------------------------
1. Allocations are returned with route indices, not Route objects.
   This avoids multiprocessing pickle/key-identity problems.
2. The allocation always sums exactly to TOTAL_FLEET.
3. Worker processes receive heavy graph objects once through an initializer,
   rather than sending them again with every submitted task.
4. Each trial receives a deterministic random seed for reproducibility.
5. Broad bare except blocks are replaced with specific exception handling.
"""

from __future__ import annotations

import math
import os
import random
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Ensure the project root is importable when this script is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DDMConfig, DirectDemandSampler
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph

# =============================================================================
# CONFIGURATION
# =============================================================================

CITY_NAME = "Iligan City"
BBOX = (8.1500, 8.3300, 124.1500, 124.4000)  # (min_lat, max_lat, min_lon, max_lon)
PBF_PATH = "utils/data/iligan-city.pbf"
CACHE_PREFIX = "iligan_arterial"

N_ROUTES = 5
ROUTE_N_POINTS = 5
TOTAL_FLEET = 50

SAMPLE_SIZES = list(range(50, 550, 50))
NUM_TRIALS = 10
BASE_SEED = 42
STABILITY_THRESHOLD = 0.5

UPDATED_WEIGHTS = {
    "walk_wt": 0.5630,
    "ride_wt": 0.00632,
    "wait_wt": 14.44,
    "transfer_wt": 15.78,
    "direct_wt": 0.0,
    "alight_wt": 0.0,
}

OUTPUT_DIR = Path("documentation/phase_3")
OUTPUT_CSV = OUTPUT_DIR / "mohring_calibration_data.csv"
OUTPUT_FIG = OUTPUT_DIR / "fig_6_mohring_variance_calibration.png"

# =============================================================================
# WORKER GLOBALS
# =============================================================================

_WORKER_TG: Optional[TravelGraph] = None
_WORKER_SAMPLER: Optional[DirectDemandSampler] = None
_WORKER_ROUTE_COUNT: int = 0
_WORKER_L1_KEYS: list[tuple[float, float]] = []
_WORKER_L3_KEYS: list[tuple[float, float]] = []

_RIDE_ROUTE_PATTERN = re.compile(r"^RI_R(\d+)_")


def _init_mohring_worker(
    tg: TravelGraph,
    sampler: DirectDemandSampler,
    route_count: int,
    l1_keys: list[tuple[float, float]],
    l3_keys: list[tuple[float, float]],
) -> None:
    """
    Initializes per-process global references.

    This avoids repeatedly pickling and sending the heavy TravelGraph and sampler
    objects for every single trial task.
    """
    global _WORKER_TG, _WORKER_SAMPLER, _WORKER_ROUTE_COUNT, _WORKER_L1_KEYS, _WORKER_L3_KEYS

    _WORKER_TG = tg
    _WORKER_SAMPLER = sampler
    _WORKER_ROUTE_COUNT = int(route_count)
    _WORKER_L1_KEYS = list(l1_keys)
    _WORKER_L3_KEYS = list(l3_keys)


def _extract_route_index(edge_id: str) -> Optional[int]:
    """
    Extracts the route index from a TravelGraph ride-edge ID.

    Expected format from TravelGraph:
        RI_R0_00001
        RI_R1_00002
        ...
    """
    match = _RIDE_ROUTE_PATTERN.match(edge_id)
    if not match:
        return None
    return int(match.group(1))


def _allocate_mohring_exact(route_demand: dict[int, float], total_fleet: int) -> dict[int, int]:
    """
    Applies Mohring square-root allocation and guarantees that the final integer
    allocation sums exactly to total_fleet.

    Formula:
        F_i = F_total * sqrt(tau_i) / sum_j sqrt(tau_j)

    The integer correction follows the same logic as the project's FleetAllocator:
    floor exact shares, protect each route with at least one jeep, then distribute
    remaining units by largest positive remainder.
    """
    if total_fleet <= 0:
        raise ValueError("total_fleet must be positive.")
    if not route_demand:
        raise ValueError("route_demand cannot be empty.")
    if total_fleet < len(route_demand):
        raise ValueError("total_fleet must be at least the number of routes when min allocation is 1.")

    route_tau = {route_idx: math.sqrt(max(1.0, demand)) for route_idx, demand in route_demand.items()}
    total_tau = sum(route_tau.values()) or 1.0
    exact_shares = {route_idx: total_fleet * (tau / total_tau) for route_idx, tau in route_tau.items()}

    allocation = {
        route_idx: max(1, int(math.floor(exact_share)))
        for route_idx, exact_share in exact_shares.items()
    }

    allocated = sum(allocation.values())

    while allocated > total_fleet:
        reducible = [route_idx for route_idx, count in allocation.items() if count > 1]
        if not reducible:
            break
        route_to_reduce = max(reducible, key=lambda route_idx: allocation[route_idx] - exact_shares[route_idx])
        allocation[route_to_reduce] -= 1
        allocated -= 1

    while allocated < total_fleet:
        route_to_increase = max(allocation, key=lambda route_idx: exact_shares[route_idx] - allocation[route_idx])
        allocation[route_to_increase] += 1
        allocated += 1

    return allocation


def _snap_to_layer_nodes(origin, destination):
    """
    Converts sampled CityGraph nodes into valid TravelGraph layer nodes.

    TravelGraph.findShortestJourney can also snap internally, but doing exact
    dictionary lookup first avoids unnecessary KDTree queries when the sampled
    nodes already exist in the layer dictionaries.
    """
    if _WORKER_TG is None:
        raise RuntimeError("Worker TravelGraph was not initialized.")

    origin_coord = (origin.lon, origin.lat)
    dest_coord = (destination.lon, destination.lat)

    start = _WORKER_TG.l1_nodes.get(origin_coord)
    end = _WORKER_TG.l3_nodes.get(dest_coord)

    # Rare fallback for any sampled point that is not exactly in the layer maps.
    if start is None:
        start = _WORKER_TG.l1_nodes[random.choice(_WORKER_L1_KEYS)]
    if end is None:
        end = _WORKER_TG.l3_nodes[random.choice(_WORKER_L3_KEYS)]

    return start, end


def _run_mohring_trial(task: tuple[int, int, int, int]) -> tuple[int, int, dict[int, int], float]:
    """
    Runs one isolated Mohring calibration trial.

    Returns:
        (N, trial_idx, allocation_by_route_index, runtime_seconds)
    """
    N, trial_idx, total_fleet, seed = task

    if _WORKER_TG is None or _WORKER_SAMPLER is None:
        raise RuntimeError("Worker was not initialized. Check ProcessPoolExecutor initializer.")

    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))

    # Clear local A* cache so each trial measures cold-cache routing cost.
    _WORKER_TG.findShortestJourney.cache_clear()

    start_time = time.perf_counter()
    route_demand = {route_idx: 0.0 for route_idx in range(_WORKER_ROUTE_COUNT)}

    for _ in range(N):
        origin = _WORKER_SAMPLER.get_point()
        destination = _WORKER_SAMPLER.get_point()
        start, end = _snap_to_layer_nodes(origin, destination)

        journey = _WORKER_TG.findShortestJourney(start, end)
        if not journey:
            continue

        # Demand is counted per traversed ride edge, matching the original logic
        # and the current FleetAllocator convention.
        for edge in journey:
            route_idx = _extract_route_index(edge.id)
            if route_idx is None:
                continue
            if 0 <= route_idx < _WORKER_ROUTE_COUNT:
                route_demand[route_idx] += 1.0

    allocation = _allocate_mohring_exact(route_demand, total_fleet=total_fleet)
    runtime = time.perf_counter() - start_time

    return N, trial_idx, allocation, runtime


# =============================================================================
# DATA GENERATION
# =============================================================================

def build_calibration_infrastructure(seed: int = BASE_SEED) -> tuple[TravelGraph, DirectDemandSampler, int]:
    """
    Builds the CityGraph, DirectDemandSampler, generated routes, and TravelGraph
    used by all Mohring calibration trials.
    """
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))

    print("Instantiating infrastructure for Mohring calibration...")
    city = CityGraph(
        name=CITY_NAME,
        bbox=BBOX,
        pbf_path=PBF_PATH,
        cache_prefix=CACHE_PREFIX,
    )

    sampler = DirectDemandSampler(city, config=DDMConfig())
    route_generator = RouteGenerator(city, sampler)

    print(f"Generating {N_ROUTES} transit loops...")
    routes = [route_generator.generate(n_points=ROUTE_N_POINTS) for _ in range(N_ROUTES)]

    print("Constructing TravelGraph with calibrated generalized-cost weights...")
    travel_graph = TravelGraph(cg=city, config=UPDATED_WEIGHTS, routes=routes)

    return travel_graph, sampler, len(routes)


def get_real_calibration_data(
    sample_sizes: list[int] = SAMPLE_SIZES,
    num_trials: int = NUM_TRIALS,
    total_fleet: int = TOTAL_FLEET,
    base_seed: int = BASE_SEED,
    use_parallel: bool = True,
) -> pd.DataFrame:
    """
    Executes repeated OD-sampling trials and returns a calibration DataFrame.
    """
    tg, sampler, route_count = build_calibration_infrastructure(seed=base_seed)

    if total_fleet < route_count:
        raise ValueError("TOTAL_FLEET must be at least the number of routes.")

    l1_keys = list(tg.l1_nodes.keys())
    l3_keys = list(tg.l3_nodes.keys())

    if not l1_keys or not l3_keys:
        raise ValueError("TravelGraph layer nodes were not constructed correctly.")

    results_map: dict[int, dict[str, list]] = {
        N: {"allocations": [], "runtimes": []}
        for N in sample_sizes
    }

    tasks: list[tuple[int, int, int, int]] = []
    for N in sample_sizes:
        for trial_idx in range(num_trials):
            seed = base_seed + (N * 10_000) + trial_idx
            tasks.append((N, trial_idx, total_fleet, seed))

    if use_parallel:
        cpu_count = os.cpu_count() or 1
        max_workers = max(1, min(cpu_count - 1 if cpu_count > 1 else 1, len(tasks)))
        print(f"\nExecuting {len(tasks)} trials across {max_workers} worker process(es)...")

        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_mohring_worker,
            initargs=(tg, sampler, route_count, l1_keys, l3_keys),
        ) as executor:
            futures = [executor.submit(_run_mohring_trial, task) for task in tasks]

            for future in as_completed(futures):
                N, trial_idx, allocation, runtime = future.result()
                results_map[N]["allocations"].append(allocation)
                results_map[N]["runtimes"].append(runtime)
                print(f"  -> [N={N:3d}] Trial {trial_idx + 1:02d}/{num_trials} completed in {runtime:.2f}s")
    else:
        print(f"\nExecuting {len(tasks)} trials sequentially...")
        _init_mohring_worker(tg, sampler, route_count, l1_keys, l3_keys)
        for task in tasks:
            N, trial_idx, allocation, runtime = _run_mohring_trial(task)
            results_map[N]["allocations"].append(allocation)
            results_map[N]["runtimes"].append(runtime)
            print(f"  -> [N={N:3d}] Trial {trial_idx + 1:02d}/{num_trials} completed in {runtime:.2f}s")

    rows = []
    for N in sample_sizes:
        trial_allocations: list[dict[int, int]] = results_map[N]["allocations"]
        trial_runtimes: list[float] = results_map[N]["runtimes"]

        if not trial_allocations:
            rows.append({
                "N": N,
                "completed_trials": 0,
                "mean_std_dev": 0.0,
                "mean_runtime": 0.0,
                "min_runtime": 0.0,
                "max_runtime": 0.0,
            })
            continue

        route_allocations = {route_idx: [] for route_idx in range(route_count)}
        for allocation in trial_allocations:
            if sum(allocation.values()) != total_fleet:
                raise RuntimeError(f"Allocation does not sum to {total_fleet}: {allocation}")
            for route_idx in range(route_count):
                route_allocations[route_idx].append(allocation.get(route_idx, 0))

        route_std_devs = [float(np.std(counts, ddof=0)) for counts in route_allocations.values()]

        rows.append({
            "N": N,
            "completed_trials": len(trial_allocations),
            "mean_std_dev": float(np.mean(route_std_devs)),
            "mean_runtime": float(np.mean(trial_runtimes)),
            "min_runtime": float(np.min(trial_runtimes)),
            "max_runtime": float(np.max(trial_runtimes)),
        })

    df = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nCalibration data saved to: {OUTPUT_CSV.resolve()}")

    return df


# =============================================================================
# PLOTTING
# =============================================================================

def select_stable_sample_size(
    df: pd.DataFrame,
    threshold: float = STABILITY_THRESHOLD,
) -> tuple[Optional[int], Optional[float]]:
    """
    Selects the first sample size where stability is sustained for two adjacent
    sample sizes. If sustained stability is not reached, selects the first point
    below the threshold.
    """
    if df.empty:
        return None, None

    ordered = df.sort_values("N").reset_index(drop=True)

    for i in range(len(ordered) - 1):
        current_sigma = float(ordered.loc[i, "mean_std_dev"])
        next_sigma = float(ordered.loc[i + 1, "mean_std_dev"])
        if current_sigma <= threshold and next_sigma <= threshold:
            return int(ordered.loc[i, "N"]), current_sigma

    below_threshold = ordered[ordered["mean_std_dev"] <= threshold]
    if not below_threshold.empty:
        row = below_threshold.iloc[0]
        return int(row["N"]), float(row["mean_std_dev"])

    return None, None


def plot_mohring_calibration(
    df: pd.DataFrame,
    output_path: Path = OUTPUT_FIG,
    stability_threshold: float = STABILITY_THRESHOLD,
) -> None:
    """
    Generates a high-resolution dual-axis plot for allocation stability and
    computation time.
    """
    if df.empty:
        raise ValueError("Cannot plot an empty calibration DataFrame.")

    sns.set_theme(
        style="white",
        rc={
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#333333",
            "text.color": "#333333",
        },
    )

    fig, ax1 = plt.subplots(figsize=(12, 8), dpi=300)
    fig.patch.set_facecolor("white")
    ax1.set_facecolor("white")

    color_variance = "#1E88E5"
    color_runtime = "#D90429"

    line_variance, = ax1.plot(
        df["N"],
        df["mean_std_dev"],
        color=color_variance,
        linewidth=3,
        marker="o",
        markersize=8,
        markeredgecolor="white",
        markeredgewidth=1.5,
        label=r"Mean Std. Deviation ($\sigma$)",
    )

    ax1.set_xlabel("OD Sample Size ($N$)", fontsize=14, fontweight="bold", labelpad=12)
    ax1.set_ylabel(
        r"Mean Standard Deviation of Fleet Allocation ($\sigma$)",
        color=color_variance,
        fontsize=14,
        fontweight="bold",
        labelpad=12,
    )
    ax1.tick_params(axis="y", labelcolor=color_variance, labelsize=12)
    ax1.tick_params(axis="x", labelsize=12)

    ax1.axhline(y=stability_threshold, color="gray", linestyle="--", linewidth=1.5, alpha=0.8)
    ax1.text(
        df["N"].max(),
        stability_threshold + 0.02,
        rf"Stability Threshold ($\sigma = {stability_threshold}$)",
        color="gray",
        fontsize=11,
        ha="right",
        va="bottom",
        style="italic",
    )

    ax2 = ax1.twinx()
    line_runtime, = ax2.plot(
        df["N"],
        df["mean_runtime"],
        color=color_runtime,
        linewidth=3,
        marker="s",
        markersize=7,
        markeredgecolor="white",
        markeredgewidth=1.5,
        label="Mean Runtime (s)",
    )
    ax2.set_ylabel(
        "Mean Computation Time (Seconds)",
        color=color_runtime,
        fontsize=14,
        fontweight="bold",
        labelpad=12,
    )
    ax2.tick_params(axis="y", labelcolor=color_runtime, labelsize=12)

    selected_n, selected_sigma = select_stable_sample_size(df, threshold=stability_threshold)
    if selected_n is not None and selected_sigma is not None:
        ax1.axvline(x=selected_n, color="black", linestyle="--", linewidth=2, alpha=0.85)
        ax1.annotate(
            f"Selected Sample Size ($N={selected_n}$)\nSustained stability criterion",
            xy=(selected_n, selected_sigma),
            xytext=(selected_n + 50, selected_sigma + 0.3),
            arrowprops={"facecolor": "black", "shrink": 0.05, "width": 2, "headwidth": 8},
            fontsize=12,
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.5", "fc": "white", "ec": "black", "lw": 1.2, "alpha": 0.9},
        )

    ax1.grid(True, which="both", axis="x", linestyle=":", linewidth=1, alpha=0.6)
    ax1.grid(True, which="both", axis="y", linestyle=":", linewidth=1, alpha=0.6)

    lines = [line_variance, line_runtime]
    labels = [line.get_label() for line in lines]
    ax1.legend(
        lines,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.95),
        fontsize=12,
        frameon=True,
        shadow=True,
        borderpad=1,
        edgecolor="#333333",
    )

    plt.title(
        "Mohring Allocation Stability vs. Computational Runtime",
        fontsize=18,
        fontweight="bold",
        pad=25,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"Visualization saved to: {output_path.resolve()}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    print("Executing empirical A* trials for Mohring sample-size calibration...")
    calibration_data = get_real_calibration_data(
        sample_sizes=SAMPLE_SIZES,
        num_trials=NUM_TRIALS,
        total_fleet=TOTAL_FLEET,
        base_seed=BASE_SEED,
        use_parallel=True,
    )

    print("\nCalibration summary:")
    print(calibration_data.to_string(index=False))

    selected_n, selected_sigma = select_stable_sample_size(calibration_data)
    if selected_n is not None:
        print(f"\nSelected sample size: N={selected_n} with mean_std_dev={selected_sigma:.4f}")
    else:
        print("\nNo sample size reached the configured stability threshold.")

    print("\nGenerating dual-axis visualization...")
    plot_mohring_calibration(calibration_data)
    print("Process complete.")


if __name__ == "__main__":
    main()