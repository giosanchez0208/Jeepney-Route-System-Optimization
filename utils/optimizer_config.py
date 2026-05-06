"""
config.py

Handles YAML ingestion, type validation, and mutable state tracking.
"""

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class ExperimentConfig:
    traffic_csv_path: Path
    city_bounds: tuple[float, float, float, float]
    
    k_routes: int
    total_fleet: int
    
    output_root: Path
    telemetry_interval: int
    checkpoint_interval: int
    
    n_population: int
    g_max: int
    n_stagnation: int
    n_elite: int
    k_tournament: int
    p_mutation: float
    gamma_crossover: float
    
    initial_pheromone: float
    rho_evaporation: float
    q_pheromone_intensity: float
    p_local_search: float
    
    walk_wt: float
    ride_wt: float
    wait_wt: float
    transfer_wt: float
    alpha_std_penalty: float
    beta_penalty: float
    
    max_ticks: int
    passenger_speed: float
    jeep_speed: float
    jeep_capacity: int
    spawn_rate_per_100: float
    spawn_stdev: float
    weight_tolerance: float
    equidistant_spawn: bool

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        return cls(
            traffic_csv_path=Path(data["TRAFFIC_CSV_PATH"]),
            city_bounds=tuple(data["CITY_BOUNDS"]),
            k_routes=int(data["K_ROUTES"]),
            total_fleet=int(data["TOTAL_FLEET"]),
            output_root=Path(data["OUTPUT_ROOT"]),
            telemetry_interval=int(data["TELEMETRY_INTERVAL"]),
            checkpoint_interval=int(data["CHECKPOINT_INTERVAL"]),
            n_population=int(data["N_POPULATION"]),
            g_max=int(data["G_MAX"]),
            n_stagnation=int(data["N_STAGNATION"]),
            n_elite=int(data["N_ELITE"]),
            k_tournament=int(data["K_TOURNAMENT"]),
            p_mutation=float(data["P_MUTATION"]),
            gamma_crossover=float(data["GAMMA_CROSSOVER"]),
            initial_pheromone=float(data["INITIAL_PHEROMONE"]),
            rho_evaporation=float(data["RHO_EVAPORATION"]),
            q_pheromone_intensity=float(data["Q_PHEROMONE_INTENSITY"]),
            p_local_search=float(data["P_LOCAL_SEARCH"]),
            walk_wt=float(data["WALK_WT"]),
            ride_wt=float(data["RIDE_WT"]),
            wait_wt=float(data["WAIT_WT"]),
            transfer_wt=float(data["TRANSFER_WT"]),
            alpha_std_penalty=float(data["ALPHA_STD_PENALTY"]),
            beta_penalty=float(data["BETA_PENALTY"]),
            max_ticks=int(data["MAX_TICKS"]),
            passenger_speed=float(data["PASSENGER_SPEED"]),
            jeep_speed=float(data["JEEP_SPEED"]),
            jeep_capacity=int(data["JEEP_CAPACITY"]),
            spawn_rate_per_100=float(data["SPAWN_RATE_PER_100"]),
            spawn_stdev=float(data["SPAWN_STDEV"]),
            weight_tolerance=float(data["WEIGHT_TOLERANCE"]),
            equidistant_spawn=bool(data["EQUIDISTANT_SPAWN"])
        )

@dataclass
class OptimizationState:
    generation: int = 1
    stagnation_counter: int = 0
    best_fitness: float = float('inf')
    population: list[Any] = None
    pheromones: Any = None