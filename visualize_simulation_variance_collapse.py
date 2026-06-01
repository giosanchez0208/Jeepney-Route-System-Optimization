from __future__ import annotations

"""
ABM Simulation Variance-Collapse Calibration
Redone version with the SAME public output as the original script:

    DataFrame columns:
        spawn_rate
        mean_fitness
        std_fitness

    Figure filename:
        documentation/phase_3/fig_7_simulation_variance_collapse.png

What was fixed internally:
1. Does not pass Route objects directly into worker processes.
   In this project, Route.__setstate__ restores route.path as an empty list,
   which can break multiprocessing. This script serializes route geometry and
   reconstructs valid Route objects inside each worker.
2. Uses deterministic seeds for reproducibility.
3. Uses more trials by default, while still allowing the old 3-trial setting.
4. Does not silently convert failed trials to fake zeros.
5. Keeps the same output column names and figure filename requested by the user.

Default normalization:
    NORMALIZATION_MODE = "observed"

This means fitness is divided by completed + incomplete observed passengers.
That is methodologically stronger because the project's simulation fitness
includes penalties for incomplete passengers too. To reproduce the original
normalization more closely, run with:

    --normalization completed --trials 3

Run from the project root:
    python visualize_simulation_variance_collapse_redone_same_output.py --yes

Quick smoke test:
    python visualize_simulation_variance_collapse_redone_same_output.py --spawn-rates 25,50 --trials 2 --sequential --yes
"""

import argparse
import copy
import math
import os
import random
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import yaml

# Make the project root importable when this script is launched directly.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DDMConfig, DirectDemandSampler
from utils.directed_edge import DirEdge
from utils.route import Route, RouteGenerator
from utils.simulation import SimulationEvaluator
from utils.travel_graph import TravelGraph

try:
    from utils.toy_city import toy_setup_from_yaml
except Exception:  # pragma: no cover - optional project utility
    toy_setup_from_yaml = None


# =============================================================================
# USER-FACING DEFAULTS
# =============================================================================

DEFAULT_CONFIG_PATH = "configs/profile_p1.yaml"
DEFAULT_OUTPUT_DIR = "documentation/phase_3"
DEFAULT_FIGURE_FILENAME = "fig_7_simulation_variance_collapse.png"
DEFAULT_SPAWN_RATES = [25, 50, 100, 200, 300, 400]

# Original script used 3. Thesis-ready default is 10.
DEFAULT_NUM_TRIALS = 10

DEFAULT_NUM_ROUTES = 3
DEFAULT_ROUTE_POINTS = 5
DEFAULT_BASE_SEED = 42

# Same rule as the original script: stable if std < 15% of mean.
DEFAULT_RELATIVE_STD_THRESHOLD = 0.15

# "observed" is stronger. "completed" reproduces the old denominator more closely.
DEFAULT_NORMALIZATION_MODE = "observed"  # choices: observed, completed

# Original fallback values if the YAML does not define city_graph.
DEFAULT_CITY_NAME = "Iligan City"
DEFAULT_BBOX = (8.1500, 8.3300, 124.1500, 124.4000)
DEFAULT_PBF_PATH = "utils/data/iligan-city.pbf"
DEFAULT_CACHE_PREFIX = "iligan_arterial"


# =============================================================================
# WORKER GLOBALS
# =============================================================================

_WORKER_EVALUATOR: Optional[SimulationEvaluator] = None
_WORKER_ROUTES: Optional[list[Route]] = None
_WORKER_NORMALIZATION_MODE: str = DEFAULT_NORMALIZATION_MODE


# =============================================================================
# SMALL UTILITIES
# =============================================================================

def set_reproducible_seed(seed: int) -> None:
    """Sets the random seeds used by the project's stochastic components."""
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Simulation config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Config file did not load into a dictionary: {config_path}")

    return config


def parse_spawn_rates(value: str) -> list[int]:
    try:
        rates = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Spawn rates must be comma-separated integers.") from exc

    if not rates or any(rate <= 0 for rate in rates):
        raise argparse.ArgumentTypeError("Spawn rates must contain positive integers.")

    return rates


def coord_key(lon: float, lat: float) -> tuple[float, float]:
    return (round(float(lon), 10), round(float(lat), 10))


# =============================================================================
# CITY / SAMPLER / ROUTE HANDLING
# =============================================================================

def build_city_and_sampler(
    config_path: str | Path,
    config: dict[str, Any],
    seed: int,
    verbose: bool = False,
) -> tuple[CityGraph, Any, dict[str, Any]]:
    """Builds the static city graph and demand sampler."""
    set_reproducible_seed(seed)

    # Optional support for the project's toy_city YAML format.
    if "toy_city" in config:
        if toy_setup_from_yaml is None:
            raise ImportError("utils.toy_city.toy_setup_from_yaml is unavailable.")
        city, sampler, raw_config = toy_setup_from_yaml(str(config_path), verbose=verbose)
        return city, sampler, raw_config

    cg_cfg = config.get("city_graph", {}) or {}
    bbox = tuple(cg_cfg.get("bbox", DEFAULT_BBOX))
    if len(bbox) != 4:
        raise ValueError("city_graph.bbox must contain four values: (min_lat, max_lat, min_lon, max_lon).")

    city = CityGraph(
        name=cg_cfg.get("name", DEFAULT_CITY_NAME),
        bbox=bbox,
        landmarks=cg_cfg.get("landmarks"),
        pbf_path=cg_cfg.get("pbf_path", DEFAULT_PBF_PATH),
        use_api=bool(cg_cfg.get("use_api", False)),
        verbose=bool(cg_cfg.get("verbose", verbose)),
        cache_prefix=cg_cfg.get("cache_prefix", DEFAULT_CACHE_PREFIX),
    )

    ddm_cfg = config.get("ddm", {}) or {}
    sampler = DirectDemandSampler(city, config=DDMConfig(**ddm_cfg), verbose=verbose)
    return city, sampler, config


def serialize_routes(routes: list[Route]) -> list[dict[str, Any]]:
    """
    Converts generated Route objects to lightweight coordinate specs.

    This avoids passing Route objects directly through multiprocessing.
    """
    route_specs: list[dict[str, Any]] = []

    for route_idx, route in enumerate(routes):
        if not route.path:
            raise ValueError(f"Generated route {route_idx + 1} has an empty path.")

        edge_specs: list[dict[str, Any]] = []
        for edge in route.path:
            weight = getattr(edge, "weight", None)
            if weight is None:
                # Defensive fallback. The simulator and Jeep cache expect numeric weights.
                weight = edge.getLength()

            edge_specs.append(
                {
                    "start": [float(edge.start.lon), float(edge.start.lat)],
                    "end": [float(edge.end.lon), float(edge.end.lat)],
                    "weight": float(weight),
                    "id": getattr(edge, "id", None),
                }
            )

        route_specs.append(
            {
                "id": getattr(route, "id", f"baseline_route_{route_idx}"),
                "designated_color": getattr(route, "designated_color", None),
                "edges": edge_specs,
            }
        )

    return route_specs


def reconstruct_routes(city: CityGraph, route_specs: list[dict[str, Any]]) -> list[Route]:
    """Reconstructs valid Layer-2 Route objects from serialized coordinate specs."""
    node_by_coord = {coord_key(node.lon, node.lat): node for node in city.nodes}
    routes: list[Route] = []

    for route_idx, spec in enumerate(route_specs):
        edge_specs = spec.get("edges", [])
        if not edge_specs:
            raise ValueError(f"Route spec {route_idx + 1} has no edges.")

        path: list[DirEdge] = []
        for edge_idx, edge_spec in enumerate(edge_specs):
            start_lon, start_lat = edge_spec["start"]
            end_lon, end_lat = edge_spec["end"]
            start = node_by_coord.get(coord_key(start_lon, start_lat))
            end = node_by_coord.get(coord_key(end_lon, end_lat))

            if start is None or end is None:
                raise ValueError(
                    f"Cannot reconstruct route {route_idx + 1}, edge {edge_idx + 1}: "
                    f"missing city node for ({start_lon}, {start_lat}) -> ({end_lon}, {end_lat})."
                )

            edge = DirEdge(
                start=start,
                end=end,
                is_drivable=True,
                weight=float(edge_spec.get("weight", 0.0)),
                id=edge_spec.get("id"),
            )
            setattr(edge, "layer", 2)
            path.append(edge)

        for i, edge in enumerate(path):
            edge.next_edges = [path[(i + 1) % len(path)]]

        route = Route(city_graph=city, path=path, id=spec.get("id"))
        if spec.get("designated_color"):
            route.designated_color = spec["designated_color"]
        routes.append(route)

    return routes


def generate_baseline_route_specs(
    config_path: str | Path,
    config: dict[str, Any],
    num_routes: int,
    route_points: int,
    base_seed: int,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """Generates one deterministic baseline route system and serializes it."""
    city, sampler, _ = build_city_and_sampler(config_path, config, seed=base_seed, verbose=verbose)
    route_generator = RouteGenerator(city, sampler, verbose=verbose)

    routes: list[Route] = []
    for route_idx in range(num_routes):
        route_seed = base_seed + route_idx * 1009
        set_reproducible_seed(route_seed)
        route = route_generator.generate(n_points=route_points)
        routes.append(route)
        print(f"  -> Generated baseline route {route_idx + 1}/{num_routes} with {len(route.path)} edges.")

    return serialize_routes(routes)


# =============================================================================
# WORKER EXECUTION
# =============================================================================

def init_abm_worker(
    config_path_str: str,
    route_specs: list[dict[str, Any]],
    base_seed: int,
    normalization_mode: str,
) -> None:
    """Builds heavy objects once inside each worker process."""
    global _WORKER_EVALUATOR, _WORKER_ROUTES, _WORKER_NORMALIZATION_MODE

    config_path = Path(config_path_str)
    config = load_yaml_config(config_path)
    city, sampler, raw_config = build_city_and_sampler(config_path, config, seed=base_seed, verbose=False)
    routes = reconstruct_routes(city, route_specs)

    _WORKER_EVALUATOR = SimulationEvaluator(raw_config, city, None, sampler)
    _WORKER_ROUTES = routes
    _WORKER_NORMALIZATION_MODE = normalization_mode


def normalize_fitness(result: Any, normalization_mode: str) -> tuple[float, int, int, int]:
    """
    Returns normalized fitness while preserving the public column name mean_fitness.

    completed mode:
        Matches the original script more closely:
            result.fitness_score / completed_count

    observed mode:
        Thesis-stronger denominator:
            result.fitness_score / (completed_count + incomplete_count)
    """
    completed_count = int(result.metrics.get("completed_count", 0))
    incomplete_count = int(result.metrics.get("incomplete_count", 0))
    total_observed = completed_count + incomplete_count

    if normalization_mode == "completed":
        denominator = max(1, completed_count)
    elif normalization_mode == "observed":
        denominator = max(1, total_observed)
    else:
        raise ValueError("normalization_mode must be 'completed' or 'observed'.")

    norm_fitness = float(result.fitness_score) / float(denominator)
    return norm_fitness, completed_count, incomplete_count, total_observed


def run_abm_trial(task: dict[str, Any]) -> dict[str, Any]:
    """Runs one ABM trial and returns scalar, pickle-safe results."""
    if _WORKER_EVALUATOR is None or _WORKER_ROUTES is None:
        raise RuntimeError("ABM worker was not initialized.")

    rate = int(task["spawn_rate"])
    trial_idx = int(task["trial_idx"])
    seed = int(task["seed"])

    set_reproducible_seed(seed)

    # Keep each trial isolated from previous pathfinding cache state.
    try:
        TravelGraph.findShortestJourney.cache_clear()
    except AttributeError:
        pass

    _WORKER_EVALUATOR.spawn_rate = float(rate)

    start_time = time.perf_counter()
    result = _WORKER_EVALUATOR.evaluate(_WORKER_ROUTES, verbose=False)
    runtime_sec = time.perf_counter() - start_time

    norm_fitness, completed_count, incomplete_count, total_observed = normalize_fitness(
        result,
        normalization_mode=_WORKER_NORMALIZATION_MODE,
    )

    return {
        "spawn_rate": rate,
        "trial_idx": trial_idx,
        "seed": seed,
        "norm_fitness": norm_fitness,
        "completed_count": completed_count,
        "incomplete_count": incomplete_count,
        "total_observed": total_observed,
        "runtime_sec": runtime_sec,
    }


def build_tasks(spawn_rates: list[int], trials: int, base_seed: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for rate in spawn_rates:
        for trial_idx in range(trials):
            seed = base_seed + rate * 10_000 + trial_idx
            tasks.append({"spawn_rate": rate, "trial_idx": trial_idx, "seed": seed})
    return tasks


# =============================================================================
# PUBLIC CALIBRATION FUNCTION WITH SAME OUTPUT COLUMNS
# =============================================================================

def empirical_abm_calibration(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    spawn_rates: Optional[list[int]] = None,
    num_trials: int = DEFAULT_NUM_TRIALS,
    num_routes: int = DEFAULT_NUM_ROUTES,
    route_points: int = DEFAULT_ROUTE_POINTS,
    base_seed: int = DEFAULT_BASE_SEED,
    normalization_mode: str = DEFAULT_NORMALIZATION_MODE,
    sequential: bool = False,
    allow_partial: bool = False,
    verbose: bool = False,
) -> pd.DataFrame:
    """
    Empirically calibrates ABM variance collapse.

    IMPORTANT: The returned DataFrame intentionally preserves the original output:
        spawn_rate, mean_fitness, std_fitness
    """
    if spawn_rates is None:
        spawn_rates = DEFAULT_SPAWN_RATES

    if normalization_mode not in {"observed", "completed"}:
        raise ValueError("normalization_mode must be either 'observed' or 'completed'.")

    config_path = Path(config_path).resolve()
    config = load_yaml_config(config_path)

    print("Instantiating infrastructure for ABM calibration...")
    print("Generating deterministic baseline transit routes...")
    route_specs = generate_baseline_route_specs(
        config_path=config_path,
        config=config,
        num_routes=num_routes,
        route_points=route_points,
        base_seed=base_seed,
        verbose=verbose,
    )

    tasks = build_tasks(spawn_rates, num_trials, base_seed)
    results_map: dict[int, list[float]] = {rate: [] for rate in spawn_rates}
    diagnostic_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    print(f"\nExecuting variance-vs-volume trials: {len(spawn_rates)} rates × {num_trials} trials.")
    print(f"Normalization mode: {normalization_mode}")

    if sequential:
        print("Running sequentially...")
        init_abm_worker(str(config_path), route_specs, base_seed, normalization_mode)
        for task in tasks:
            try:
                row = run_abm_trial(task)
                diagnostic_rows.append(row)
                results_map[row["spawn_rate"]].append(row["norm_fitness"])
                print(
                    f"  -> [Rate {row['spawn_rate']:3d}] Trial {row['trial_idx'] + 1}/{num_trials}: "
                    f"Normalized Fitness = {row['norm_fitness']:8.4f} "
                    f"(Completed: {row['completed_count']}, Incomplete: {row['incomplete_count']})"
                )
            except Exception as exc:
                failures.append({"task": task, "error": repr(exc), "traceback": traceback.format_exc()})
                print(f"  -> [!] Trial failed for rate {task['spawn_rate']}: {exc}")
    else:
        cpu_cores = os.cpu_count() or 1
        max_workers = max(1, min(cpu_cores - 1 if cpu_cores > 1 else 1, len(tasks)))
        print(f"Running concurrently across {max_workers} worker process(es)...")

        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=init_abm_worker,
            initargs=(str(config_path), route_specs, base_seed, normalization_mode),
        ) as executor:
            futures = {executor.submit(run_abm_trial, task): task for task in tasks}

            for future in as_completed(futures):
                task = futures[future]
                try:
                    row = future.result()
                    diagnostic_rows.append(row)
                    results_map[row["spawn_rate"]].append(row["norm_fitness"])
                    print(
                        f"  -> [Rate {row['spawn_rate']:3d}] Trial {row['trial_idx'] + 1}/{num_trials}: "
                        f"Normalized Fitness = {row['norm_fitness']:8.4f} "
                        f"(Completed: {row['completed_count']}, Incomplete: {row['incomplete_count']})"
                    )
                except Exception as exc:
                    failures.append({"task": task, "error": repr(exc), "traceback": traceback.format_exc()})
                    print(f"  -> [!] Trial failed for rate {task['spawn_rate']}: {exc}")

    if failures and not allow_partial:
        first = failures[0]
        raise RuntimeError(
            f"{len(failures)} trial(s) failed. First failure: {first['error']}\n"
            "Use --allow-partial only for diagnostics, not for final thesis output."
        )

    mean_fitness: list[float] = []
    std_fitness: list[float] = []

    for rate in spawn_rates:
        scores = results_map[rate]
        if len(scores) < num_trials and not allow_partial:
            raise RuntimeError(
                f"Spawn rate {rate} completed only {len(scores)}/{num_trials} trials. "
                "Rerun the experiment or use --allow-partial only for diagnostics."
            )

        if not scores:
            if allow_partial:
                mean_fitness.append(math.nan)
                std_fitness.append(math.nan)
                continue
            raise RuntimeError(f"No successful trials for spawn rate {rate}.")

        mean_fitness.append(float(np.mean(scores)))
        # Sample standard deviation is better for repeated stochastic trials.
        std_fitness.append(float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0)

    # SAME OUTPUT AS ORIGINAL: only these three columns.
    return pd.DataFrame(
        {
            "spawn_rate": spawn_rates,
            "mean_fitness": mean_fitness,
            "std_fitness": std_fitness,
        }
    )


# =============================================================================
# PLOT WITH SAME FIGURE FILENAME
# =============================================================================

def plot_variance_collapse(
    df: pd.DataFrame,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    relative_std_threshold: float = DEFAULT_RELATIVE_STD_THRESHOLD,
) -> Path:
    """
    Generates the same final figure file name as the original script:
        fig_7_simulation_variance_collapse.png
    """
    required_cols = {"spawn_rate", "mean_fitness", "std_fitness"}
    missing = required_cols.difference(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {sorted(missing)}")

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

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    color_main = "#2A9D8F"
    x = df["spawn_rate"].astype(float)
    y = df["mean_fitness"].astype(float)
    err = df["std_fitness"].fillna(0.0).astype(float)

    ax.plot(
        x,
        y,
        color=color_main,
        linewidth=3,
        marker="o",
        markersize=8,
        markeredgecolor="white",
        markeredgewidth=1.5,
        label=r"Mean $F_{sim} / N$",
    )

    ax.fill_between(
        x,
        y - err,
        y + err,
        color=color_main,
        alpha=0.2,
        label=r"$\pm 1\sigma$ Error Band",
    )

    ax.set_xlabel("Passenger Spawn Rate (Passengers/Hour)", fontsize=14, fontweight="bold", labelpad=12)
    ax.set_ylabel(r"Mean Normalized Simulation Fitness ($F_{sim} / N$)", fontsize=14, fontweight="bold", labelpad=12)
    ax.tick_params(labelsize=12)

    # Same threshold logic as the original: std < 15% of mean.
    stable_points = df[df["std_fitness"] < relative_std_threshold * df["mean_fitness"]]
    if not stable_points.empty:
        collapse_rate = float(stable_points.iloc[0]["spawn_rate"])
        collapse_mean = float(stable_points.iloc[0]["mean_fitness"])
        max_err = float(np.nanmax(err)) if len(err) else 0.0

        ax.axvline(x=collapse_rate, color="black", linestyle="--", linewidth=2, alpha=0.8)
        ax.annotate(
            "Variance Threshold Reached",
            xy=(collapse_rate, collapse_mean),
            xytext=(collapse_rate + 20, collapse_mean + max(max_err * 0.6, 1.0)),
            arrowprops={"facecolor": "black", "shrink": 0.05, "width": 1.5, "headwidth": 8},
            fontsize=12,
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.5", "fc": "white", "ec": "black", "lw": 1.2, "alpha": 0.9},
        )

    ax.grid(True, which="both", linestyle=":", linewidth=1, alpha=0.6)
    ax.legend(loc="upper right", fontsize=12, frameon=True, shadow=True, borderpad=1, edgecolor="#333333")
    plt.title("Simulation Fidelity Calibration: Variance Collapse vs Volume", fontsize=16, fontweight="bold", pad=20)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_FIGURE_FILENAME

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"\nVisualization successfully generated and saved to: {output_path.absolute()}")
    return output_path


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ABM variance-collapse calibration with same output format as original.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to simulation YAML config.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for the output figure.")
    parser.add_argument("--spawn-rates", type=parse_spawn_rates, default=DEFAULT_SPAWN_RATES, help="Comma-separated spawn rates. Example: 25,50,100")
    parser.add_argument("--trials", type=int, default=DEFAULT_NUM_TRIALS, help="Number of trials per spawn rate.")
    parser.add_argument("--routes", type=int, default=DEFAULT_NUM_ROUTES, help="Number of baseline routes to generate.")
    parser.add_argument("--route-points", type=int, default=DEFAULT_ROUTE_POINTS, help="RouteGenerator waypoint count per route.")
    parser.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED, help="Base random seed.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_RELATIVE_STD_THRESHOLD, help="Relative std threshold. Default: 0.15")
    parser.add_argument("--normalization", choices=["observed", "completed"], default=DEFAULT_NORMALIZATION_MODE, help="Fitness denominator.")
    parser.add_argument("--sequential", action="store_true", help="Run without multiprocessing.")
    parser.add_argument("--allow-partial", action="store_true", help="Allow incomplete trial sets. Use only for diagnostics.")
    parser.add_argument("--verbose", action="store_true", help="Verbose infrastructure build.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.trials <= 0:
        raise ValueError("--trials must be positive.")
    if args.routes <= 0:
        raise ValueError("--routes must be positive.")
    if args.route_points < 2:
        raise ValueError("--route-points must be at least 2.")
    if args.threshold <= 0:
        raise ValueError("--threshold must be positive.")

    print("===============================================================")
    print("ABM Simulation Variance-Collapse Calibration")
    print("Same public output as original: spawn_rate, mean_fitness, std_fitness")
    print(f"Figure output: {Path(args.output_dir) / DEFAULT_FIGURE_FILENAME}")
    print(f"Spawn rates : {args.spawn_rates}")
    print(f"Trials/rate : {args.trials}")
    print(f"Routes      : {args.routes}")
    print(f"Normalization: {args.normalization}")
    print("===============================================================\n")

    if not args.yes:
        response = input("Press Enter to execute the ABM simulation (or type 'q' to quit)... ").strip().lower()
        if response == "q":
            print("Execution cancelled by user.")
            return

    calibration_data = empirical_abm_calibration(
        config_path=args.config,
        spawn_rates=args.spawn_rates,
        num_trials=args.trials,
        num_routes=args.routes,
        route_points=args.route_points,
        base_seed=args.base_seed,
        normalization_mode=args.normalization,
        sequential=args.sequential,
        allow_partial=args.allow_partial,
        verbose=args.verbose,
    )

    print("\nCalibration DataFrame:")
    print(calibration_data.to_string(index=False))

    plot_variance_collapse(
        calibration_data,
        output_dir=args.output_dir,
        relative_std_threshold=args.threshold,
    )
    print("Process complete.")


if __name__ == "__main__":
    main()
