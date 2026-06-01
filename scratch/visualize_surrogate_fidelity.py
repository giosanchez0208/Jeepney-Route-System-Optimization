from __future__ import annotations

import gc
import os
import random
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
import yaml

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DDMConfig, DirectDemandSampler
from utils.route import Route, RouteGenerator
from utils.simulation import SimulationEvaluator, StaticSurrogateEvaluator
from utils.travel_graph import TravelGraph


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "configs" / "profile_p1.yaml"
OUTPUT_PATH = SCRIPT_DIR / "documentation" / "phase_3" / "fig_8_surrogate_fidelity.png"

N_TRIALS = 30
ROUTES_PER_TRIAL = 3
ROUTE_POINTS = 5
ROUTE_BUILD_RETRIES = 12


def _build_city_stack(config: dict[str, Any]) -> tuple[CityGraph, DirectDemandSampler]:
    cg_cfg = config.get("city_graph")
    if not cg_cfg:
        raise ValueError("[FIDELITY] city_graph configuration is required.")

    cache_dir = config.get("global", {}).get("cache_dir", ".cache")
    city = CityGraph(
        bbox=tuple(cg_cfg.get("bbox")) if cg_cfg.get("bbox") else None,
        name=cg_cfg.get("name", "UrbanNetwork"),
        landmarks=cg_cfg.get("landmarks"),
        pbf_path=cg_cfg.get("pbf_path", "utils/data/philippines-latest.osm.pbf"),
        use_api=cg_cfg.get("use_api", False),
        verbose=False,
        cache_dir=cache_dir,
        cache_prefix=cg_cfg.get("cache_prefix", "city_graph"),
    )

    sampler = DirectDemandSampler(
        city=city,
        config=DDMConfig(**config.get("ddm", {})),
        verbose=False,
    )
    return city, sampler


def _generate_valid_routes(route_generator: RouteGenerator, target_count: int, n_points: int) -> list[Route]:
    routes: list[Route] = []
    attempts = 0
    max_attempts = max(target_count * ROUTE_BUILD_RETRIES, ROUTE_BUILD_RETRIES)

    while len(routes) < target_count and attempts < max_attempts:
        attempts += 1
        route = route_generator.generate(n_points=n_points)
        if getattr(route, "path", None) and len(route.path) > 0:
            routes.append(route)

    if len(routes) < target_count:
        raise RuntimeError(
            f"[FIDELITY] Could not build {target_count} valid routes after {attempts} attempts."
        )

    return routes


def _run_trial(trial_idx: int, config: dict[str, Any]) -> tuple[int, float, float] | str:
    try:
        # Keep each worker isolated and non-deterministic until the surrogate baseline is seeded.
        random.seed()
        TravelGraph.findShortestJourney.cache_clear()

        city, sampler = _build_city_stack(config)
        route_generator = RouteGenerator(city_graph=city, sampler=sampler, verbose=False)
        routes = _generate_valid_routes(route_generator, ROUTES_PER_TRIAL, ROUTE_POINTS)

        if any(len(route.path) == 0 for route in routes):
            raise RuntimeError("[FIDELITY] Generated an empty route path.")

        pre_surrogate_state = random.getstate()
        surrogate_samples = int(config.get("surrogate", {}).get("num_samples", 100))

        random.seed(42)
        try:
            surrogate_eval = StaticSurrogateEvaluator(
                config=config,
                city_graph=city,
                demand_sampler=sampler,
                num_samples=surrogate_samples,
            )
            surrogate_result = surrogate_eval.evaluate(routes, verbose=False)
            if surrogate_result.surrogate_cost is None:
                raise ValueError("[FIDELITY] Surrogate evaluator did not return a surrogate_cost.")
            surrogate_cost = float(surrogate_result.surrogate_cost)
        finally:
            random.setstate(pre_surrogate_state)

        del surrogate_result, surrogate_eval
        TravelGraph.findShortestJourney.cache_clear()

        fitness_eval = SimulationEvaluator(
            config=config,
            city_graph=city,
            travel_graph=None,
            demand_sampler=sampler,
        )
        fitness_result = fitness_eval.evaluate(routes, verbose=False)
        completed = int(fitness_result.metrics.get("completed_count", 0))
        normalized_fitness = float(fitness_result.fitness_score) / max(1, completed)

        del fitness_result, fitness_eval
        del routes, route_generator, sampler, city
        TravelGraph.findShortestJourney.cache_clear()
        gc.collect()

        return trial_idx, surrogate_cost, normalized_fitness
    except Exception:
        return traceback.format_exc()
    finally:
        TravelGraph.findShortestJourney.cache_clear()
        gc.collect()


def _collect_trials(config: dict[str, Any]) -> pd.DataFrame:
    worker_count = min(os.cpu_count() or 4, N_TRIALS)
    rows: list[tuple[int, float, float]] = []
    errors: list[str] = []

    with ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_run_trial, trial_idx, config): trial_idx
            for trial_idx in range(1, N_TRIALS + 1)
        }

        for future in as_completed(futures):
            trial_idx = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                errors.append(f"[TRIAL {trial_idx}] {type(exc).__name__}: {exc}")
                continue

            if isinstance(result, str):
                errors.append(f"[TRIAL {trial_idx}] {result.rstrip()}")
                continue

            rows.append(result)

    if errors:
        for error in errors:
            print(error)
        raise RuntimeError(f"{len(errors)} worker trial(s) failed; see tracebacks above.")

    df = pd.DataFrame(rows, columns=["trial_idx", "surrogate_cost", "normalized_fitness"])
    df = df.sort_values("trial_idx").reset_index(drop=True)

    if len(df) != N_TRIALS:
        raise RuntimeError(f"[FIDELITY] Expected {N_TRIALS} trials, collected {len(df)}.")

    return df


def _academic_style() -> None:
    sns.set_theme(
        style="white",
        rc={
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "axes.edgecolor": "#333333",
            "axes.labelcolor": "#333333",
            "text.color": "#333333",
            "xtick.color": "#333333",
            "ytick.color": "#333333",
        },
    )


def _prime_shared_caches(config: dict[str, Any]) -> None:
    # Warm the on-disk graph and demand caches once so the worker pool only loads them.
    previous_state = random.getstate()
    try:
        random.seed(42)
        city, sampler = _build_city_stack(config)
        del sampler, city
    finally:
        random.setstate(previous_state)
        gc.collect()


def _plot_fidelity(df: pd.DataFrame) -> None:
    valid = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["surrogate_cost", "normalized_fitness"])
    if len(valid) < 2:
        raise ValueError("[FIDELITY] Not enough valid points to plot surrogate fidelity.")

    x = valid["surrogate_cost"].to_numpy(dtype=float)
    y = valid["normalized_fitness"].to_numpy(dtype=float)

    if np.unique(x).size < 2 or np.unique(y).size < 2:
        raise ValueError("[FIDELITY] Degenerate data prevents correlation and regression fitting.")

    try:
        pearson_r, _ = stats.pearsonr(x, y)
        spearman_rho, _ = stats.spearmanr(x, y)
        reg = stats.linregress(x, y)
    except Exception as exc:
        raise ValueError("[FIDELITY] Failed to compute correlation or trendline.") from exc

    if not np.isfinite(pearson_r) or not np.isfinite(spearman_rho):
        raise ValueError("[FIDELITY] Correlation values are not finite.")

    x_line = np.linspace(x.min(), x.max(), 256)
    y_line = reg.intercept + reg.slope * x_line

    _academic_style()
    fig, ax = plt.subplots(figsize=(8, 8), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.scatter(
        x,
        y,
        s=72,
        c="#1E88E5",
        edgecolors="white",
        linewidths=0.9,
        alpha=0.92,
        label="Isolated trials",
        zorder=3,
    )
    ax.plot(
        x_line,
        y_line,
        color="#D90429",
        linewidth=2.6,
        label="Linear regression",
        zorder=4,
    )

    ax.set_xlabel(r"Static Surrogate Cost $\mathcal{O}(1)$", fontsize=13, fontweight="bold", labelpad=12)
    ax.set_ylabel(r"Normalized ABM Simulation Fitness $\mathcal{O}(N)$", fontsize=13, fontweight="bold", labelpad=12)
    ax.set_title("Evaluator Fidelity: Surrogate vs. ABM Simulation", fontsize=16, fontweight="bold", pad=18)

    ax.grid(True, which="major", linestyle=":", linewidth=1.0, alpha=0.65)
    ax.minorticks_on()
    ax.grid(True, which="minor", linestyle=":", linewidth=0.6, alpha=0.25)

    stats_box = (
        rf"Pearson $r = {pearson_r:.2f}$"
        "\n"
        rf"Spearman $\rho = {spearman_rho:.2f}$"
        "\n"
        rf"$N = {len(valid)}$"
    )
    ax.text(
        0.03,
        0.97,
        stats_box,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#333333", lw=1.2, alpha=0.96),
    )

    ax.legend(loc="lower right", frameon=True, edgecolor="#333333", fontsize=10)
    plt.tight_layout()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    print(f"Saved surrogate fidelity figure to: {OUTPUT_PATH}")


def main() -> None:
    config_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"[FIDELITY] Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print(f"Running surrogate fidelity validation with config: {config_path}")
    print("Priming shared caches before worker fan-out...")
    _prime_shared_caches(config)
    df = _collect_trials(config)
    _plot_fidelity(df)


if __name__ == "__main__":
    main()
