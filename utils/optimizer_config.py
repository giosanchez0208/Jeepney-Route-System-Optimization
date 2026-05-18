"""
optimizer_config.py

Handles YAML ingestion, type validation, and mutable state tracking.
"""

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class ExperimentConfig:
    """
    Configuration Manager

    Function: 
        Ingests strict YAML configuration files and exposes validated parameter properties.
    Utility: 
        Enables queuing multiple experiments with different target route counts, fleet sizes,
        and pheromone parameters without altering source code.
    """
    # Orchestrator IO
    output_root: Path
    telemetry_interval: int
    checkpoint_interval: int
    
    # Genetic Algorithm Params
    n_population: int
    g_max: int
    n_stagnation: int
    n_elite: int
    k_tournament: int
    p_mutation: float
    gamma_crossover: float
    
    # Local Search & Pheromone Params
    initial_tau: float
    rho: float
    q: float
    p_ls_attraction: float
    p_ls_repulsion: float
    p_ls_pruning: float
    default_jeep_weight: float

    # System Cost Penalties
    alpha_std_penalty: float
    beta_penalty: float

    # System Definition
    num_routes: int
    total_allocatable_jeeps: int
    city_bounds: tuple[float, float, float, float]
    
    # Travel Graph Weights
    walk_wt: float
    ride_wt: float
    wait_wt: float
    transfer_wt: float
    
    # Simulation Params
    max_ticks: int
    passenger_speed: float
    jeep_speed: float
    jeep_capacity: int
    spawn_rate_per_hour: float
    spawn_stdev: float
    weight_tolerance: float
    equidistant_spawn: bool

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
            
        opt = data.get("optimization", {})
        sim = data.get("simulation", {})
        tg = data.get("travel_graph", {})
        
        # Bbox fallback for toy_city vs real city
        if "city_graph" in data:
            bbox = tuple(data["city_graph"].get("bbox", [0.0, 0.0, 0.0, 0.0]))
        else:
            # Generate a rough bbox from toy city origin and grid size
            tc = data.get("toy_city", {})
            lon1 = tc.get("origin_lon", 0.0)
            lat1 = tc.get("origin_lat", 0.0)
            step = tc.get("step_deg", 0.0)
            size = tc.get("grid_size", 0)
            bbox = (lon1, lat1, lon1 + (step * size), lat1 + (step * size))

        return cls(
            output_root=Path(opt.get("output_root", "outputs/")),
            telemetry_interval=int(opt.get("telemetry_interval", 5)),
            checkpoint_interval=int(opt.get("checkpoint_interval", 10)),
            
            n_population=int(opt.get("n_population", 20)),
            g_max=int(opt.get("g_max", 50)),
            n_stagnation=int(opt.get("n_stagnation", 10)),
            n_elite=int(opt.get("n_elite", 2)),
            k_tournament=int(opt.get("k_tournament", 3)),
            p_mutation=float(opt.get("p_mutation", 0.2)),
            gamma_crossover=float(opt.get("gamma_crossover", 0.5)),
            
            initial_tau=float(opt.get("initial_tau", 1.0)),
            rho=float(opt.get("rho", 0.1)),
            q=float(opt.get("q", 1000.0)),
            p_ls_attraction=float(opt.get("p_ls_attraction", 0.4)),
            p_ls_repulsion=float(opt.get("p_ls_repulsion", 0.4)),
            p_ls_pruning=float(opt.get("p_ls_pruning", 0.6)),
            default_jeep_weight=float(opt.get("default_jeep_weight", 1.0)),
            
            alpha_std_penalty=float(opt.get("alpha_std_penalty", 0.5)),
            beta_penalty=float(opt.get("beta_penalty", 2.0)),
            
            num_routes=int(sim.get("num_routes", 5)),
            total_allocatable_jeeps=int(sim.get("total_allocatable_jeeps", 20)),
            city_bounds=bbox,
            
            walk_wt=float(tg.get("walk_wt", 0.0142)),
            ride_wt=float(tg.get("ride_wt", 0.0071)),
            wait_wt=float(tg.get("wait_wt", 8.5)),
            transfer_wt=float(tg.get("transfer_wt", 14.2)),
            
            max_ticks=int(sim.get("num_ticks", 1000)),
            passenger_speed=float(sim.get("passenger_speed_kmh", 4.5)),
            jeep_speed=float(sim.get("jeep_speed_kmh", 20.0)),
            jeep_capacity=int(sim.get("jeep_capacity", 16)),
            spawn_rate_per_hour=float(sim.get("spawn_rate_per_hour", 120.0)),
            spawn_stdev=float(sim.get("spawn_stdev", 10.0)),
            weight_tolerance=float(sim.get("weight_tolerance", 50.0)),
            equidistant_spawn=bool(sim.get("equidistant_spawn", True))
        )

@dataclass
class OptimizationState:
    generation: int = 1
    stagnation_counter: int = 0
    best_fitness: float = float('inf')
    population: list[Any] = None
    pheromones: Any = None