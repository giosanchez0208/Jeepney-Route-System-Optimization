#!/usr/bin/env python3
"""
Mohring Stability Calibration
=============================

Purpose
-------
Find the smallest Mohring passenger sample size that produces stable fleet
allocations across repeated stochastic origin-destination sampling runs.

This script does NOT run the microscopic passenger/jeep simulation and does NOT
score the static surrogate cost. It only performs the Mohring allocation step:

    sample OD pairs -> compute shortest TravelGraph journeys -> count route use
    -> apply square-root Mohring fleet allocation -> measure allocation CV

Defense outputs
---------------
The script writes:
    allocation_trials.csv
    cv_by_route.csv
    summary_by_sample_size.csv
    recommended_sample_sizes.csv
    frozen_route_manifest.json
    defense_summary.md
    plots/cv_route_count_*.png
    plots/max_cv_all_cases.png
    plots/recommended_sample_sizes.png

Run
---
Edit the DEFAULT SETTINGS below, then run:

    python mohring_stability_calibration.py

You can still override the defaults using command-line arguments.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    import yaml
except Exception as exc:
    raise RuntimeError("PyYAML is required. Install it with: pip install pyyaml") from exc


# =============================================================================
# DEFAULT SETTINGS YOU CAN EDIT
# =============================================================================

CONFIG_PATH = Path("configs/profile_p1.yaml")

# Explicit real Iligan precomputed assets.
# These are preferred when they exist, so the script does not rebuild the
# CityGraph from the PBF path in profile_p1.yaml.
CITY_GRAPH_PKL = Path("rnd/pkl/profile_p1.pkl")
DEMAND_SAMPLER_PKL = Path("rnd/pkl/ddm_8am.pkl")

# False = auto-generate routes using RouteGenerator.
# True  = use routes from CUSTOM_ROUTES_JSON.
USE_CUSTOM_ROUTES = True
CUSTOM_ROUTES_JSON = Path("configs/custom_mohring_routes.json")

ROUTE_COUNTS = [38]
SAMPLE_SIZES = [500, 1000, 1500, 2000, 3000]
TRIALS = 7
TARGET_CV = 0.50

# Fleet budget setting.
# True  = total fleet per case is route_count * FLEET_PER_ROUTE.
# False = all cases use TOTAL_FLEET.
USE_FLEET_PER_ROUTE = False
FLEET_PER_ROUTE = 10

TOTAL_FLEET = 2000

# Generated route settings.
N_POINTS = 4
ROUTE_MAX_RETRIES = 20
GENERATION_ATTEMPTS = 1000
ALLOW_DUPLICATE_ROUTES = False

# Mohring OD sampling settings.
CELL_SIZE = 0.001
DEMAND_COUNTING = "edge_hits"  # options: "edge_hits" or "unique_routes"
SEED = 20260605

# Warn if too many OD pairs do not touch any ride edge.
MIN_ROUTE_HIT_RATE = 0.05

OUTPUT_DIR = Path("outputs/mohring_stability_2")
MAKE_PLOTS = True
VERBOSE = False


# =============================================================================
# DATA CONTAINERS
# =============================================================================

@dataclass(frozen=True)
class TrialResult:
    route_count: int
    total_fleet: int
    sample_size: int
    trial: int
    allocation: list[int]
    demand_hits: list[float]
    exact_shares: list[float]
    od_without_route_hits: int
    elapsed_sec: float


@dataclass(frozen=True)
class CVSummaryRow:
    route_count: int
    total_fleet: int
    sample_size: int
    route_index: int
    route_id: str
    allocation_mean: float
    allocation_std: float
    allocation_cv: float
    demand_mean: float
    demand_std: float
    demand_cv: float


# =============================================================================
# PROJECT IMPORTS AND ENVIRONMENT LOADING
# =============================================================================

def _install_optional_dependency_stubs() -> None:
    """
    Let toy-city / pickle-based runs import project files even when real-map
    dependencies are not installed. If the real OSM/PBF path is actually used,
    these stubs fail clearly.
    """
    import types

    if "osmnx" not in sys.modules:
        try:
            __import__("osmnx")
        except ModuleNotFoundError:
            ox_stub = types.ModuleType("osmnx")

            def _missing_osmnx(*_args: Any, **_kwargs: Any) -> Any:
                raise ModuleNotFoundError(
                    "osmnx is required for real CityGraph extraction. Install osmnx, "
                    "or use toy_city / cg_pkl."
                )

            ox_stub.graph_from_bbox = _missing_osmnx
            sys.modules["osmnx"] = ox_stub

    if "pyrosm" not in sys.modules:
        try:
            __import__("pyrosm")
        except ModuleNotFoundError:
            pyrosm_stub = types.ModuleType("pyrosm")

            class _MissingOSM:
                def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                    raise ModuleNotFoundError(
                        "pyrosm is required for PBF CityGraph extraction. Install pyrosm, "
                        "or use toy_city / cg_pkl."
                    )

            pyrosm_stub.OSM = _MissingOSM
            sys.modules["pyrosm"] = pyrosm_stub

    if "dotenv" not in sys.modules:
        try:
            __import__("dotenv")
        except ModuleNotFoundError:
            dotenv_stub = types.ModuleType("dotenv")
            dotenv_stub.load_dotenv = lambda *args, **kwargs: None
            sys.modules["dotenv"] = dotenv_stub

    if "rich" not in sys.modules:
        try:
            __import__("rich")
        except ModuleNotFoundError:
            rich_stub = types.ModuleType("rich")
            rich_stub.print = print
            sys.modules["rich"] = rich_stub


def import_project_modules() -> dict[str, Any]:
    """Import project modules from the repository root containing utils/."""
    _install_optional_dependency_stubs()
    try:
        from utils.city_graph import CityGraph
        from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
        from utils.directed_edge import DirEdge
        from utils.route import Route, RouteGenerator
        from utils.toy_city import toy_setup_from_yaml
        from utils.travel_graph import TravelGraph
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Could not import the project `utils` package. Run this script from "
            "the project root where utils/ contains city_graph.py, route.py, "
            "travel_graph.py, toy_city.py, etc.\n\n"
            f"Original import error: {exc}"
        ) from exc

    return {
        "CityGraph": CityGraph,
        "DirectDemandSampler": DirectDemandSampler,
        "DDMConfig": DDMConfig,
        "DirEdge": DirEdge,
        "Route": Route,
        "RouteGenerator": RouteGenerator,
        "toy_setup_from_yaml": toy_setup_from_yaml,
        "TravelGraph": TravelGraph,
    }


def resolve_existing_path(
    path: Optional[Path],
    *,
    config_path: Optional[Path] = None,
    label: str = "path",
    required: bool = False,
) -> Optional[Path]:
    """
    Resolve project-root, config-relative, script-relative, and flat-upload paths.

    This lets the same script work when files are stored in the project layout:
        configs/profile_p1.yaml
        rnd/pkl/profile_p1.pkl
        rnd/pkl/ddm_8am.pkl

    or when the uploaded files are temporarily placed beside the script:
        profile_p1.yaml
        profile_p1.pkl
        ddm_8am.pkl
    """
    if path is None:
        if required:
            raise FileNotFoundError(f"Missing required {label} path.")
        return None

    path = Path(path).expanduser()
    candidates: list[Path] = []

    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(Path.cwd() / path)

        if config_path is not None:
            config_path = Path(config_path).expanduser()
            candidates.append(config_path.parent / path)
            candidates.append(config_path.parent / path.name)

        script_dir = Path(__file__).resolve().parent
        candidates.append(script_dir / path)
        candidates.append(script_dir / path.name)
        candidates.append(Path.cwd() / path.name)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)

        if candidate.exists():
            return candidate.resolve()

    if required:
        checked = "\n  - ".join(str(c) for c in candidates)
        raise FileNotFoundError(
            f"Could not find {label}: {path}\n"
            f"Checked:\n  - {checked}"
        )

    return path


def load_yaml(path: Path) -> dict[str, Any]:
    resolved = resolve_existing_path(path, label="config", required=True)
    with resolved.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a dictionary at the top level: {resolved}")

    return data


def load_environment(
    config_path: Path,
    modules: dict[str, Any],
    city_graph_pkl: Optional[Path] = None,
    demand_sampler_pkl: Optional[Path] = None,
    verbose: bool = False,
) -> tuple[Any, Any, dict[str, Any]]:
    """
    Load CityGraph, demand sampler, and raw config without running Simulation.

    Important:
    - If profile_p1.pkl exists, this function loads it directly.
    - It will not rebuild the Iligan CityGraph from the PBF unless the pickle is missing.
    - If ddm_8am.pkl exists, this function loads it directly and attaches the loaded city.
    """
    resolved_config_path = resolve_existing_path(config_path, label="config", required=True)
    cfg = load_yaml(resolved_config_path)

    cfg_cg_pkl = cfg.get("cg_pkl")
    cfg_ddm_pkl = cfg.get("ddm_pkl")

    resolved_cg_pkl = resolve_existing_path(
        city_graph_pkl or (Path(cfg_cg_pkl) if cfg_cg_pkl else None),
        config_path=resolved_config_path,
        label="CityGraph pickle",
        required=False,
    )

    resolved_ddm_pkl = resolve_existing_path(
        demand_sampler_pkl or (Path(cfg_ddm_pkl) if cfg_ddm_pkl else None),
        config_path=resolved_config_path,
        label="DirectDemandSampler pickle",
        required=False,
    )

    if "toy_city" in cfg and resolved_cg_pkl is None:
        city, sampler, raw_config = modules["toy_setup_from_yaml"](
            str(resolved_config_path),
            verbose=verbose,
        )
        return city, sampler, raw_config

    CityGraph = modules["CityGraph"]
    DirectDemandSampler = modules["DirectDemandSampler"]
    DDMConfig = modules["DDMConfig"]

    if resolved_cg_pkl and resolved_cg_pkl.exists():
        import pickle

        if verbose:
            print(f"[LOAD] CityGraph pickle: {resolved_cg_pkl}")

        with resolved_cg_pkl.open("rb") as f:
            city = pickle.load(f)
    else:
        cg_cfg = cfg.get("city_graph", {})
        if not cg_cfg:
            raise ValueError("Config must contain toy_city, cg_pkl, city_graph, or a valid --city-graph-pkl.")

        city = CityGraph(
            bbox=tuple(cg_cfg.get("bbox")) if "bbox" in cg_cfg else None,
            name=cg_cfg.get("name", "UrbanNetwork"),
            landmarks=cg_cfg.get("landmarks"),
            pbf_path=cg_cfg.get("pbf_path", "utils/data/philippines-latest.osm.pbf"),
            use_api=cg_cfg.get("use_api", False),
            verbose=cg_cfg.get("verbose", False),
        )

    if resolved_ddm_pkl and resolved_ddm_pkl.exists():
        import pickle

        if verbose:
            print(f"[LOAD] DirectDemandSampler pickle: {resolved_ddm_pkl}")

        with resolved_ddm_pkl.open("rb") as f:
            sampler = pickle.load(f)

        sampler.city = city
    else:
        sampler = DirectDemandSampler(
            city=city,
            config=DDMConfig(**cfg.get("ddm", {})),
            verbose=verbose,
        )

    return city, sampler, cfg


# =============================================================================
# ROUTE CONSTRUCTION
# =============================================================================

def route_signature(route: Any) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    return tuple(
        ((round(e.start.lon, 8), round(e.start.lat, 8)), (round(e.end.lon, 8), round(e.end.lat, 8)))
        for e in route.path
    )


def generate_routes(
    city: Any,
    sampler: Any,
    route_count: int,
    modules: dict[str, Any],
    n_points: int,
    route_max_retries: int,
    generation_attempts: int,
    allow_duplicate_routes: bool,
    verbose: bool,
) -> list[Any]:
    """Generate and freeze one route system for a route-count case."""
    RouteGenerator = modules["RouteGenerator"]
    rg = RouteGenerator(city, sampler, verbose=verbose)

    routes: list[Any] = []
    seen: set[Any] = set()
    attempts = 0

    while len(routes) < route_count and attempts < generation_attempts:
        attempts += 1
        try:
            route = rg.generate(n_points=n_points, max_retries=route_max_retries)
        except Exception as exc:
            if verbose:
                print(f"[ROUTES] generation attempt {attempts} failed: {exc}")
            continue

        sig = route_signature(route)
        if not allow_duplicate_routes and sig in seen:
            continue
        seen.add(sig)
        route.id = f"R{len(routes):03d}"
        routes.append(route)

    if len(routes) < route_count:
        raise RuntimeError(
            f"Only generated {len(routes)}/{route_count} routes after {attempts} attempts. "
            "Try increasing --generation-attempts, lowering --n-points, using toy_city, "
            "or passing --allow-duplicate-routes."
        )

    return routes


def build_route_from_lonlat_coords(
    city: Any,
    coords_lonlat: list[list[float]],
    modules: dict[str, Any],
    route_id: Optional[str] = None,
) -> Any:
    """Build a closed Layer-2 Route from [lon, lat] coordinates."""
    import numpy as np
    from scipy.spatial import cKDTree

    DirEdge = modules["DirEdge"]
    Route = modules["Route"]

    if len(coords_lonlat) < 2:
        raise ValueError("A custom route needs at least two coordinates.")

    drivable_nodes: set[Any] = set()
    for city_edge in getattr(city, "graph", []):
        if getattr(city_edge, "is_drivable", False):
            drivable_nodes.add(city_edge.start)
            drivable_nodes.add(city_edge.end)

    nodes = list(drivable_nodes)
    if not nodes:
        raise ValueError("CityGraph has no drivable nodes for custom-route snapping.")

    cg_coords = np.array([(n.lon, n.lat) for n in nodes], dtype=float)
    kdtree = cKDTree(cg_coords)

    query = np.array(coords_lonlat, dtype=float)
    _, idxs = kdtree.query(query)
    snapped = [nodes[int(i)] for i in idxs]

    cleaned = [snapped[0]]
    for node in snapped[1:]:
        if node is not cleaned[-1]:
            cleaned.append(node)

    if len(cleaned) >= 2 and cleaned[-1] is cleaned[0]:
        cleaned.pop()

    if len(cleaned) < 2:
        raise ValueError("Custom route coordinates snapped to one node only.")

    base_path = []
    for i in range(len(cleaned) - 1):
        segment = city.find_shortest_path(cleaned[i], cleaned[i + 1])
        if not segment:
            raise ValueError(f"No path between custom waypoint {i} and {i + 1}.")
        base_path.extend(segment)

    closing_segment = city.find_shortest_path(cleaned[-1], cleaned[0])
    if not closing_segment:
        raise ValueError("No closing path from final waypoint back to first waypoint.")
    base_path.extend(closing_segment)

    l2_path = []
    for edge in base_path:
        l2_edge = DirEdge(
            edge.start,
            edge.end,
            is_drivable=True,
            weight=getattr(edge, "weight", None),
        )
        setattr(l2_edge, "layer", 2)

        if route_id is not None and hasattr(edge, "id"):
            l2_edge.id = f"{route_id}_{edge.id}"

        l2_path.append(l2_edge)

    for i in range(len(l2_path)):
        l2_path[i].next_edges.append(l2_path[(i + 1) % len(l2_path)])

    return Route(city, path=l2_path, id=route_id)


def _coords_from_route_item(item: Any) -> tuple[Optional[str], list[list[float]]]:
    """Parse one custom route item into (route_id, coords_lonlat)."""
    if isinstance(item, list):
        return None, item

    if not isinstance(item, dict):
        raise TypeError("Each custom route must be a coordinate list or dictionary.")

    route_id = item.get("id") or item.get("name")

    if "coords_lonlat" in item:
        return route_id, item["coords_lonlat"]
    if "coordinates_lonlat" in item:
        return route_id, item["coordinates_lonlat"]
    if "coords_latlon" in item:
        return route_id, [[float(lon), float(lat)] for lat, lon in item["coords_latlon"]]
    if "coordinates_latlon" in item:
        return route_id, [[float(lon), float(lat)] for lat, lon in item["coordinates_latlon"]]
    if "coords" in item:
        return route_id, item["coords"]

    raise KeyError(
        "Custom route dictionary must contain coords_lonlat, coordinates_lonlat, "
        "coords_latlon, coordinates_latlon, or coords."
    )


def load_custom_routes(
    city: Any,
    custom_routes_json: Path,
    route_count: int,
    modules: dict[str, Any],
) -> list[Any]:
    """Load a route set for the requested route_count from JSON."""
    with custom_routes_json.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    key = str(route_count)
    route_set: Any = None

    if isinstance(payload, dict) and "route_sets" in payload:
        route_set = payload["route_sets"].get(key) or payload["route_sets"].get(route_count)
    elif isinstance(payload, dict):
        route_set = payload.get(key) or payload.get(route_count)
    elif isinstance(payload, list):
        route_set = payload

    if route_set is None:
        raise KeyError(f"Custom route JSON does not contain route_count={route_count}.")

    route_items = route_set.get("routes") if isinstance(route_set, dict) else route_set
    if not isinstance(route_items, list):
        raise TypeError("Custom route set must be a list or contain a `routes` list.")

    if len(route_items) != route_count:
        raise ValueError(
            f"Custom route set for {route_count} routes contains {len(route_items)} routes. "
            "It must match the requested route count exactly."
        )

    routes = []
    for idx, item in enumerate(route_items):
        route_id, coords_lonlat = _coords_from_route_item(item)
        routes.append(
            build_route_from_lonlat_coords(
                city=city,
                coords_lonlat=coords_lonlat,
                modules=modules,
                route_id=route_id or f"R{idx:03d}",
            )
        )
    return routes


# =============================================================================
# EXACT MOHRING ALLOCATION LOGIC
# =============================================================================

def quantise_node(node: Any, cell_size: float) -> tuple[int, int]:
    """Return (lon_cell, lat_cell), matching the existing FleetAllocator style."""
    return (int(math.floor(node.lon / cell_size)), int(math.floor(node.lat / cell_size)))


def representative_node_from_cell(cell: tuple[int, int], cell_size: float) -> Any:
    lon_centre = (cell[0] + 0.5) * cell_size
    lat_centre = (cell[1] + 0.5) * cell_size
    return type("NodeLike", (), {"lon": lon_centre, "lat": lat_centre})()


def route_indices_from_journey(journey: Iterable[Any], demand_counting: str) -> list[int]:
    indices: list[int] = []
    for edge in journey:
        edge_id = getattr(edge, "id", "")
        if isinstance(edge_id, str) and edge_id.startswith("RI_R"):
            try:
                indices.append(int(edge_id.split("_")[1][1:]))
            except (IndexError, ValueError):
                continue

    if demand_counting == "unique_routes":
        return list(dict.fromkeys(indices))
    if demand_counting == "edge_hits":
        return indices
    raise ValueError("demand_counting must be 'edge_hits' or 'unique_routes'.")


class RouteIndexResolver:
    """
    Cached OD-cell -> route-index resolver.

    One resolver is created per frozen route system and reused across all sample
    sizes and trials for that route_count. Repeated OD cells therefore do not
    rerun A* pathfinding unnecessarily.
    """

    def __init__(self, tg: Any, cell_size: float, demand_counting: str, cache_size: int = 200_000) -> None:
        self.tg = tg
        self.cell_size = cell_size
        self.demand_counting = demand_counting
        self._cached = lru_cache(maxsize=cache_size)(self._uncached)

    def _uncached(self, o_cell: tuple[int, int], d_cell: tuple[int, int]) -> tuple[int, ...]:
        origin = representative_node_from_cell(o_cell, self.cell_size)
        dest = representative_node_from_cell(d_cell, self.cell_size)
        journey = self.tg.findShortestJourney(origin, dest)
        return tuple(route_indices_from_journey(journey, self.demand_counting))

    def __call__(self, o_cell: tuple[int, int], d_cell: tuple[int, int]) -> tuple[int, ...]:
        return self._cached(o_cell, d_cell)

    def cache_info(self) -> Any:
        return self._cached.cache_info()


def allocate_from_demand(route_demand: list[float], total_fleet: int) -> tuple[list[int], list[float]]:
    """Apply square-root Mohring allocation."""
    route_count = len(route_demand)
    if total_fleet <= 0:
        raise ValueError("total_fleet must be positive.")
    if route_count > total_fleet:
        raise ValueError(
            f"Cannot allocate at least one jeep per route: {route_count} routes but total_fleet={total_fleet}."
        )

    route_tau = [math.sqrt(max(1.0, demand)) for demand in route_demand]
    total_sqrt_tau = sum(route_tau) or 1.0
    exact_shares = [total_fleet * tau / total_sqrt_tau for tau in route_tau]

    allocation = [max(1, int(math.floor(x))) for x in exact_shares]
    allocated = sum(allocation)

    while allocated > total_fleet:
        candidates = [idx for idx, value in enumerate(allocation) if value > 1]
        if not candidates:
            break
        idx_dec = max(candidates, key=lambda idx: allocation[idx] - exact_shares[idx])
        allocation[idx_dec] -= 1
        allocated -= 1

    if allocated < total_fleet:
        remainders = [exact - alloc for exact, alloc in zip(exact_shares, allocation)]
        for idx in sorted(range(route_count), key=lambda i: remainders[i], reverse=True):
            if allocated >= total_fleet:
                break
            allocation[idx] += 1
            allocated += 1

    if sum(allocation) != total_fleet:
        raise RuntimeError(
            f"Allocation sanity check failed: sum={sum(allocation)}, total_fleet={total_fleet}."
        )

    return allocation, exact_shares


def allocate_by_mohring_exact(
    total_fleet: int,
    route_count: int,
    sampler: Any,
    resolver: RouteIndexResolver,
    sample_size: int,
    cell_size: float,
) -> tuple[list[int], list[float], list[float], int]:
    """
    Exact-N Mohring allocation for calibration.

    This avoids adaptive early stopping so sample sizes are directly comparable:
    5 means exactly 5 OD pairs, 100 means exactly 100 OD pairs, etc.
    """
    if sample_size <= 0:
        raise ValueError("sample_size must be positive.")
    if route_count <= 0:
        raise ValueError("route_count must be positive.")

    route_demand = [0.0 for _ in range(route_count)]
    od_without_route_hits = 0

    for _ in range(sample_size):
        origin = sampler.get_point()
        dest = sampler.get_point()
        o_cell = quantise_node(origin, cell_size)
        d_cell = quantise_node(dest, cell_size)
        route_indices = resolver(o_cell, d_cell)

        if not route_indices:
            od_without_route_hits += 1
            continue

        for r_idx in route_indices:
            if 0 <= r_idx < route_count:
                route_demand[r_idx] += 1.0

    allocation, exact_shares = allocate_from_demand(route_demand, total_fleet)
    return allocation, route_demand, exact_shares, od_without_route_hits


# =============================================================================
# EXPERIMENT AND STATISTICS
# =============================================================================

def stdev_safe(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def cv_safe(mean_value: float, std_value: float) -> float:
    if mean_value == 0:
        return 0.0 if std_value == 0 else float("inf")
    return std_value / mean_value


def get_case_total_fleet(route_count: int, fleet_mode: str, fleet_per_route: int, total_fleet: int) -> int:
    if fleet_mode == "per_route":
        return route_count * fleet_per_route
    if fleet_mode == "fixed":
        return total_fleet
    raise ValueError("fleet_mode must be 'per_route' or 'fixed'.")


def run_trials_for_sample_size(
    route_count: int,
    total_fleet: int,
    sample_size: int,
    trials: int,
    sampler: Any,
    resolver: RouteIndexResolver,
    cell_size: float,
    seed: int,
    verbose: bool = False,
) -> list[TrialResult]:
    results: list[TrialResult] = []

    for trial in range(trials):
        random.seed(seed + route_count * 1_000_000 + total_fleet * 10_000 + sample_size * 1_000 + trial)
        start = time.perf_counter()
        allocation, demand_hits, exact_shares, od_without_route_hits = allocate_by_mohring_exact(
            total_fleet=total_fleet,
            route_count=route_count,
            sampler=sampler,
            resolver=resolver,
            sample_size=sample_size,
            cell_size=cell_size,
        )
        elapsed = time.perf_counter() - start

        results.append(
            TrialResult(
                route_count=route_count,
                total_fleet=total_fleet,
                sample_size=sample_size,
                trial=trial,
                allocation=allocation,
                demand_hits=demand_hits,
                exact_shares=exact_shares,
                od_without_route_hits=od_without_route_hits,
                elapsed_sec=elapsed,
            )
        )

        if verbose:
            print(
                f"[TRIAL] routes={route_count:>2} fleet={total_fleet:>4} sample={sample_size:>5} "
                f"trial={trial + 1:>3}/{trials} allocation={allocation} "
                f"no_route_od={od_without_route_hits}/{sample_size} elapsed={elapsed:.3f}s"
            )

    return results


def summarize_cv(trials: list[TrialResult], routes: list[Any]) -> tuple[list[CVSummaryRow], dict[str, float]]:
    if not trials:
        raise ValueError("No trials to summarize.")

    route_count = trials[0].route_count
    total_fleet = trials[0].total_fleet
    sample_size = trials[0].sample_size
    rows: list[CVSummaryRow] = []

    for route_idx, route in enumerate(routes):
        alloc_values = [float(t.allocation[route_idx]) for t in trials]
        demand_values = [float(t.demand_hits[route_idx]) for t in trials]

        alloc_mean = statistics.mean(alloc_values)
        alloc_std = stdev_safe(alloc_values)
        demand_mean = statistics.mean(demand_values)
        demand_std = stdev_safe(demand_values)

        rows.append(
            CVSummaryRow(
                route_count=route_count,
                total_fleet=total_fleet,
                sample_size=sample_size,
                route_index=route_idx,
                route_id=getattr(route, "id", f"R{route_idx:03d}"),
                allocation_mean=alloc_mean,
                allocation_std=alloc_std,
                allocation_cv=cv_safe(alloc_mean, alloc_std),
                demand_mean=demand_mean,
                demand_std=demand_std,
                demand_cv=cv_safe(demand_mean, demand_std),
            )
        )

    allocation_cvs = [row.allocation_cv for row in rows]
    demand_cvs = [row.demand_cv for row in rows]
    elapsed_values = [t.elapsed_sec for t in trials]
    no_route_rates = [t.od_without_route_hits / t.sample_size for t in trials]

    system_summary = {
        "route_count": float(route_count),
        "total_fleet": float(total_fleet),
        "sample_size": float(sample_size),
        "mean_allocation_cv": statistics.mean(allocation_cvs),
        "max_allocation_cv": max(allocation_cvs),
        "mean_demand_cv": statistics.mean(demand_cvs),
        "max_demand_cv": max(demand_cvs),
        "mean_no_route_od_rate": statistics.mean(no_route_rates),
        "max_no_route_od_rate": max(no_route_rates),
        "mean_route_hit_rate": 1.0 - statistics.mean(no_route_rates),
        "mean_elapsed_sec": statistics.mean(elapsed_values),
        "total_elapsed_sec": sum(elapsed_values),
    }
    return rows, system_summary


def choose_recommendation(
    system_rows: list[dict[str, Any]],
    route_count: int,
    target_cv: float,
    min_route_hit_rate: float,
) -> dict[str, Any]:
    rows = sorted(
        [r for r in system_rows if int(r["route_count"]) == route_count],
        key=lambda r: int(r["sample_size"]),
    )

    first_below = None
    stable_from_here = None
    usable_first_below = None
    usable_stable_from_here = None

    for idx, row in enumerate(rows):
        stable = row["max_allocation_cv"] <= target_cv
        usable = row["mean_route_hit_rate"] >= min_route_hit_rate

        if stable and first_below is None:
            first_below = int(row["sample_size"])
        if stable and usable and usable_first_below is None:
            usable_first_below = int(row["sample_size"])

        if all(r["max_allocation_cv"] <= target_cv for r in rows[idx:]):
            stable_from_here = int(row["sample_size"])
            break

    for idx, row in enumerate(rows):
        if all(
            r["max_allocation_cv"] <= target_cv and r["mean_route_hit_rate"] >= min_route_hit_rate
            for r in rows[idx:]
        ):
            usable_stable_from_here = int(row["sample_size"])
            break

    return {
        "route_count": route_count,
        "target_cv": target_cv,
        "min_route_hit_rate": min_route_hit_rate,
        "first_below_threshold": first_below,
        "recommended_stable_from_here": stable_from_here,
        "usable_first_below_threshold": usable_first_below,
        "usable_recommended_stable_from_here": usable_stable_from_here,
    }


def _chosen_sample_from_recommendation(rec: dict[str, Any]) -> Optional[int]:
    return (
        rec.get("usable_recommended_stable_from_here")
        or rec.get("recommended_stable_from_here")
        or rec.get("usable_first_below_threshold")
        or rec.get("first_below_threshold")
    )


# =============================================================================
# OUTPUT WRITING
# =============================================================================

def write_trial_rows(path: Path, all_trials: list[TrialResult], routes_by_count: dict[int, list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "route_count", "total_fleet", "sample_size", "trial", "route_index", "route_id",
            "allocation", "demand_hits", "exact_share", "od_without_route_hits", "trial_elapsed_sec",
        ])
        for trial in all_trials:
            routes = routes_by_count[trial.route_count]
            for idx, route in enumerate(routes):
                writer.writerow([
                    trial.route_count,
                    trial.total_fleet,
                    trial.sample_size,
                    trial.trial,
                    idx,
                    getattr(route, "id", f"R{idx:03d}"),
                    trial.allocation[idx],
                    trial.demand_hits[idx],
                    f"{trial.exact_shares[idx]:.8f}",
                    trial.od_without_route_hits,
                    f"{trial.elapsed_sec:.6f}",
                ])


def write_cv_rows(path: Path, rows: list[CVSummaryRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "route_count", "total_fleet", "sample_size", "route_index", "route_id",
            "allocation_mean", "allocation_std", "allocation_cv",
            "demand_mean", "demand_std", "demand_cv",
        ])
        for row in rows:
            writer.writerow([
                row.route_count,
                row.total_fleet,
                row.sample_size,
                row.route_index,
                row.route_id,
                f"{row.allocation_mean:.8f}",
                f"{row.allocation_std:.8f}",
                f"{row.allocation_cv:.8f}",
                f"{row.demand_mean:.8f}",
                f"{row.demand_std:.8f}",
                f"{row.demand_cv:.8f}",
            ])


def write_system_summary(path: Path, rows: list[dict[str, Any]], target_cv: float, min_route_hit_rate: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "route_count", "total_fleet", "sample_size", "mean_allocation_cv", "max_allocation_cv",
            "mean_demand_cv", "max_demand_cv", "mean_no_route_od_rate", "max_no_route_od_rate",
            "mean_route_hit_rate", "stable_by_cv", "usable_by_route_hit_rate",
            "mean_elapsed_sec", "total_elapsed_sec",
        ])
        for row in rows:
            writer.writerow([
                int(row["route_count"]),
                int(row["total_fleet"]),
                int(row["sample_size"]),
                f"{row['mean_allocation_cv']:.8f}",
                f"{row['max_allocation_cv']:.8f}",
                f"{row['mean_demand_cv']:.8f}",
                f"{row['max_demand_cv']:.8f}",
                f"{row['mean_no_route_od_rate']:.8f}",
                f"{row['max_no_route_od_rate']:.8f}",
                f"{row['mean_route_hit_rate']:.8f}",
                bool(row["max_allocation_cv"] <= target_cv),
                bool(row["mean_route_hit_rate"] >= min_route_hit_rate),
                f"{row['mean_elapsed_sec']:.6f}",
                f"{row['total_elapsed_sec']:.6f}",
            ])


def write_recommendations(path: Path, recommendations: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "route_count", "target_cv", "min_route_hit_rate", "first_below_threshold",
            "recommended_stable_from_here", "usable_first_below_threshold",
            "usable_recommended_stable_from_here",
        ])
        for row in recommendations:
            writer.writerow([
                row["route_count"],
                row["target_cv"],
                row["min_route_hit_rate"],
                "" if row["first_below_threshold"] is None else row["first_below_threshold"],
                "" if row["recommended_stable_from_here"] is None else row["recommended_stable_from_here"],
                "" if row["usable_first_below_threshold"] is None else row["usable_first_below_threshold"],
                "" if row["usable_recommended_stable_from_here"] is None else row["usable_recommended_stable_from_here"],
            ])


def write_route_manifest(path: Path, routes_by_count: dict[int, list[Any]]) -> None:
    """Save route geometry so the frozen route systems are auditable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"route_sets": {}}
    for route_count, routes in routes_by_count.items():
        payload["route_sets"][str(route_count)] = {
            "routes": [
                {
                    "id": getattr(route, "id", f"R{idx:03d}"),
                    "edge_count": len(route.path),
                    "coords_lonlat": [[edge.start.lon, edge.start.lat] for edge in route.path]
                    + ([[route.path[-1].end.lon, route.path[-1].end.lat]] if route.path else []),
                }
                for idx, route in enumerate(routes)
            ]
        }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _best_row_for_recommendation(
    system_rows: list[dict[str, Any]],
    route_count: int,
    chosen_sample: Optional[int],
) -> Optional[dict[str, Any]]:
    if chosen_sample is None:
        return None
    for row in system_rows:
        if int(row["route_count"]) == route_count and int(row["sample_size"]) == int(chosen_sample):
            return row
    return None


def write_defense_summary(
    path: Path,
    recommendations: list[dict[str, Any]],
    system_rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Mohring Stability Calibration Defense Summary",
        "",
        "This experiment does not run the microscopic passenger-jeep simulation. It repeatedly samples OD pairs, computes TravelGraph journeys, counts route usage, applies square-root Mohring allocation, and selects the smallest sample size that stabilizes allocation variability.",
        "",
        "| Route count | Total fleet | Chosen sample size | Max allocation CV | Mean allocation CV | Route-hit rate |",
        "|---:|---:|---:|---:|---:|---:|",
    ]

    for rec in recommendations:
        route_count = int(rec["route_count"])
        chosen = _chosen_sample_from_recommendation(rec)
        row = _best_row_for_recommendation(system_rows, route_count, chosen)
        if row is None:
            lines.append(f"| {route_count} | - | Not reached | - | - | - |")
        else:
            lines.append(
                f"| {route_count} | {int(row['total_fleet'])} | {chosen} | "
                f"{row['max_allocation_cv']:.4f} | {row['mean_allocation_cv']:.4f} | "
                f"{row['mean_route_hit_rate']:.4f} |"
            )

    lines.extend([
        "",
        "Recommended defense interpretation:",
        "",
        "> The selected Mohring sample size is the smallest tested value that keeps the worst route-level allocation coefficient of variation at or below the target threshold, while also checking that OD samples actually use the route network.",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


# =============================================================================
# PLOTTING
# =============================================================================

def make_plots(
    out_dir: Path,
    system_rows: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    target_cv: float,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("[PLOT] matplotlib is unavailable; skipping plots.")
        return

    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    route_counts = sorted({int(row["route_count"]) for row in system_rows})

    for route_count in route_counts:
        rows = sorted(
            [row for row in system_rows if int(row["route_count"]) == route_count],
            key=lambda row: int(row["sample_size"]),
        )
        xs = [int(row["sample_size"]) for row in rows]
        mean_cvs = [float(row["mean_allocation_cv"]) for row in rows]
        max_cvs = [float(row["max_allocation_cv"]) for row in rows]

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(xs, mean_cvs, marker="o", label="Mean allocation CV")
        ax.plot(xs, max_cvs, marker="o", label="Max allocation CV")
        ax.axhline(target_cv, linestyle="--", label=f"Target CV = {target_cv}")
        ax.set_xscale("log")
        ax.set_xlabel("Mohring sample size")
        ax.set_ylabel("Coefficient of variation")
        ax.set_title(f"Mohring allocation stability — {route_count} routes")
        ax.grid(True, which="both", alpha=0.25)
        ax.legend()
        fig.tight_layout()
        fig.savefig(plots_dir / f"cv_route_count_{route_count}.png", dpi=160)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for route_count in route_counts:
        rows = sorted(
            [row for row in system_rows if int(row["route_count"]) == route_count],
            key=lambda row: int(row["sample_size"]),
        )
        xs = [int(row["sample_size"]) for row in rows]
        max_cvs = [float(row["max_allocation_cv"]) for row in rows]
        ax.plot(xs, max_cvs, marker="o", label=f"{route_count} routes")
    ax.axhline(target_cv, linestyle="--", label=f"Target CV = {target_cv}")
    ax.set_xscale("log")
    ax.set_xlabel("Mohring sample size")
    ax.set_ylabel("Max allocation CV")
    ax.set_title("Worst-route Mohring allocation stability across route-count cases")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plots_dir / "max_cv_all_cases.png", dpi=160)
    plt.close(fig)

    rec_counts = []
    rec_samples = []
    for rec in recommendations:
        chosen = _chosen_sample_from_recommendation(rec)
        if chosen is not None:
            rec_counts.append(str(rec["route_count"]))
            rec_samples.append(int(chosen))

    if rec_counts:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(rec_counts, rec_samples)
        ax.set_xlabel("Route-count case")
        ax.set_ylabel("Chosen Mohring sample size")
        ax.set_title("Recommended Mohring sample size per route-count case")
        ax.grid(True, axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(plots_dir / "recommended_sample_sizes.png", dpi=160)
        plt.close(fig)


# =============================================================================
# MAIN ORCHESTRATION
# =============================================================================

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    default_route_mode = "custom" if USE_CUSTOM_ROUTES else "generated"
    default_custom_json: Optional[Path] = CUSTOM_ROUTES_JSON if USE_CUSTOM_ROUTES else None
    default_fleet_mode = "per_route" if USE_FLEET_PER_ROUTE else "fixed"

    parser = argparse.ArgumentParser(
        description="Calibrate Mohring sample size using repeated exact-N fleet allocation trials."
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--city-graph-pkl", type=Path, default=CITY_GRAPH_PKL)
    parser.add_argument("--demand-sampler-pkl", type=Path, default=DEMAND_SAMPLER_PKL)
    parser.add_argument("--route-mode", choices=["generated", "custom"], default=default_route_mode)
    parser.add_argument("--custom-routes-json", type=Path, default=default_custom_json)
    parser.add_argument("--route-counts", type=int, nargs="+", default=ROUTE_COUNTS)
    parser.add_argument("--sample-sizes", type=int, nargs="+", default=SAMPLE_SIZES)
    parser.add_argument("--trials", type=int, default=TRIALS)
    parser.add_argument("--target-cv", type=float, default=TARGET_CV)
    parser.add_argument("--fleet-mode", choices=["per_route", "fixed"], default=default_fleet_mode)
    parser.add_argument("--fleet-per-route", type=int, default=FLEET_PER_ROUTE)
    parser.add_argument("--total-fleet", type=int, default=TOTAL_FLEET)
    parser.add_argument("--n-points", type=int, default=N_POINTS)
    parser.add_argument("--route-max-retries", type=int, default=ROUTE_MAX_RETRIES)
    parser.add_argument("--generation-attempts", type=int, default=GENERATION_ATTEMPTS)
    parser.add_argument("--allow-duplicate-routes", action="store_true", default=ALLOW_DUPLICATE_ROUTES)
    parser.add_argument("--cell-size", type=float, default=CELL_SIZE)
    parser.add_argument("--demand-counting", choices=["edge_hits", "unique_routes"], default=DEMAND_COUNTING)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--min-route-hit-rate", type=float, default=MIN_ROUTE_HIT_RATE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--make-plots", action="store_true", default=MAKE_PLOTS)
    parser.add_argument("--no-plots", action="store_false", dest="make_plots")
    parser.add_argument("--verbose", action="store_true", default=VERBOSE)
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    if args.trials < 2:
        raise ValueError("--trials must be at least 2 to compute standard deviation and CV.")
    if any(n <= 0 for n in args.route_counts):
        raise ValueError("All --route-counts must be positive.")
    if any(n <= 0 for n in args.sample_sizes):
        raise ValueError("All --sample-sizes must be positive.")
    if args.route_mode == "custom" and args.custom_routes_json is None:
        raise ValueError("--custom-routes-json is required when --route-mode custom.")
    if args.fleet_mode == "per_route" and args.fleet_per_route <= 0:
        raise ValueError("--fleet-per-route must be positive.")
    if args.fleet_mode == "fixed" and args.total_fleet <= 0:
        raise ValueError("--total-fleet must be positive.")
    if args.cell_size <= 0:
        raise ValueError("--cell-size must be positive.")

    for route_count in args.route_counts:
        case_total_fleet = get_case_total_fleet(
            route_count=route_count,
            fleet_mode=args.fleet_mode,
            fleet_per_route=args.fleet_per_route,
            total_fleet=args.total_fleet,
        )
        if route_count > case_total_fleet:
            raise ValueError(
                f"Route count {route_count} exceeds case total fleet {case_total_fleet}. "
                "Mohring allocation assigns at least one jeep per route."
            )


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    validate_args(args)
    random.seed(args.seed)

    modules = import_project_modules()
    city, sampler, raw_config = load_environment(
        args.config,
        modules,
        city_graph_pkl=args.city_graph_pkl,
        demand_sampler_pkl=args.demand_sampler_pkl,
        verbose=args.verbose,
    )
    TravelGraph = modules["TravelGraph"]

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    all_trials: list[TrialResult] = []
    all_cv_rows: list[CVSummaryRow] = []
    system_rows: list[dict[str, Any]] = []
    routes_by_count: dict[int, list[Any]] = {}

    print("[START] Mohring stability calibration")
    print(f"[CONFIG] route_counts={args.route_counts}")
    print(f"[CONFIG] sample_sizes={args.sample_sizes}")
    print(f"[CONFIG] trials={args.trials}, target_cv={args.target_cv}")
    if args.fleet_mode == "per_route":
        print(f"[CONFIG] fleet_mode=per_route, fleet_per_route={args.fleet_per_route}")
    else:
        print(f"[CONFIG] fleet_mode=fixed, total_fleet={args.total_fleet}")
    print(
        f"[CONFIG] city_graph_pkl="
        f"{resolve_existing_path(args.city_graph_pkl, config_path=args.config, label='CityGraph pickle')}"
    )
    print(
        f"[CONFIG] demand_sampler_pkl="
        f"{resolve_existing_path(args.demand_sampler_pkl, config_path=args.config, label='DirectDemandSampler pickle')}"
    )
    print(f"[CONFIG] route_mode={args.route_mode}, demand_counting={args.demand_counting}")
    print(f"[CONFIG] make_plots={args.make_plots}")

    for route_count in args.route_counts:
        case_total_fleet = get_case_total_fleet(
            route_count=route_count,
            fleet_mode=args.fleet_mode,
            fleet_per_route=args.fleet_per_route,
            total_fleet=args.total_fleet,
        )

        print(f"\n[ROUTE SET] Preparing {route_count} routes...")
        print(f"[FLEET] route_count={route_count}, case_total_fleet={case_total_fleet}")
        random.seed(args.seed + route_count)

        if args.route_mode == "generated":
            routes = generate_routes(
                city=city,
                sampler=sampler,
                route_count=route_count,
                modules=modules,
                n_points=args.n_points,
                route_max_retries=args.route_max_retries,
                generation_attempts=args.generation_attempts,
                allow_duplicate_routes=args.allow_duplicate_routes,
                verbose=args.verbose,
            )
        else:
            routes = load_custom_routes(
                city=city,
                custom_routes_json=args.custom_routes_json,
                route_count=route_count,
                modules=modules,
            )

        routes_by_count[route_count] = routes
        print(f"[ROUTE SET] Built/froze {len(routes)} routes.")

        tg = TravelGraph(cg=city, config=raw_config.get("travel_graph", {}).copy(), routes=routes)
        print(f"[TRAVELGRAPH] {len(getattr(tg, 'travel_graph', []))} edges built.")

        resolver = RouteIndexResolver(
            tg=tg,
            cell_size=args.cell_size,
            demand_counting=args.demand_counting,
        )

        for sample_size in args.sample_sizes:
            print(f"[SAMPLE] route_count={route_count}, fleet={case_total_fleet}, sample_size={sample_size}")
            trials = run_trials_for_sample_size(
                route_count=route_count,
                total_fleet=case_total_fleet,
                sample_size=sample_size,
                trials=args.trials,
                sampler=sampler,
                resolver=resolver,
                cell_size=args.cell_size,
                seed=args.seed,
                verbose=args.verbose,
            )

            cv_rows, system_summary = summarize_cv(trials, routes)
            all_trials.extend(trials)
            all_cv_rows.extend(cv_rows)
            system_rows.append(system_summary)

            route_hit_ok = system_summary["mean_route_hit_rate"] >= args.min_route_hit_rate
            print(
                f"[CV] mean={system_summary['mean_allocation_cv']:.4f}, "
                f"max={system_summary['max_allocation_cv']:.4f}, "
                f"route_hit_rate={system_summary['mean_route_hit_rate']:.3f}, "
                f"stable_by_cv={system_summary['max_allocation_cv'] <= args.target_cv}, "
                f"usable={route_hit_ok}"
            )
            if not route_hit_ok:
                print(
                    "[WARN] Few OD pairs used any ride route. A low CV here may be a false-stable result. "
                    "Check travel_graph weights, route coverage, or use a real/custom route system."
                )

        print(f"[CACHE] OD route-index cache: {resolver.cache_info()}")

    recommendations = [
        choose_recommendation(system_rows, route_count, args.target_cv, args.min_route_hit_rate)
        for route_count in args.route_counts
    ]

    write_trial_rows(out_dir / "allocation_trials.csv", all_trials, routes_by_count)
    write_cv_rows(out_dir / "cv_by_route.csv", all_cv_rows)
    write_system_summary(
        out_dir / "summary_by_sample_size.csv",
        system_rows,
        target_cv=args.target_cv,
        min_route_hit_rate=args.min_route_hit_rate,
    )
    write_recommendations(out_dir / "recommended_sample_sizes.csv", recommendations)
    write_route_manifest(out_dir / "frozen_route_manifest.json", routes_by_count)
    write_defense_summary(out_dir / "defense_summary.md", recommendations, system_rows)

    run_metadata = {
        "config": str(args.config),
        "city_graph_pkl": str(
            resolve_existing_path(
                args.city_graph_pkl,
                config_path=args.config,
                label="CityGraph pickle",
            )
        ),
        "demand_sampler_pkl": str(
            resolve_existing_path(
                args.demand_sampler_pkl,
                config_path=args.config,
                label="DirectDemandSampler pickle",
            )
        ),
        "route_mode": args.route_mode,
        "route_counts": args.route_counts,
        "sample_sizes": args.sample_sizes,
        "trials": args.trials,
        "target_cv": args.target_cv,
        "fleet_mode": args.fleet_mode,
        "fleet_per_route": args.fleet_per_route,
        "fixed_total_fleet": args.total_fleet,
        "cell_size": args.cell_size,
        "demand_counting": args.demand_counting,
        "min_route_hit_rate": args.min_route_hit_rate,
        "seed": args.seed,
        "make_plots": args.make_plots,
        "note": "No microscopic simulation was run; this is exact-N Mohring allocation stability calibration.",
    }
    with (out_dir / "run_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(run_metadata, f, indent=2)

    if args.make_plots:
        make_plots(out_dir, system_rows, recommendations, target_cv=args.target_cv)

    print("\n[DONE] Outputs written to:", out_dir.resolve())
    print("[DONE] Recommendations:")
    for rec in recommendations:
        chosen = _chosen_sample_from_recommendation(rec)
        print(
            f"  routes={rec['route_count']}: "
            f"first_below={rec['first_below_threshold']}, "
            f"stable_from_here={rec['recommended_stable_from_here']}, "
            f"usable_first_below={rec['usable_first_below_threshold']}, "
            f"usable_stable_from_here={rec['usable_recommended_stable_from_here']}, "
            f"chosen_for_defense={chosen}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())