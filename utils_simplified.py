import os
import yaml
import pickle
from typing import Optional

from datetime import datetime
from dataclasses import dataclass
import concurrent.futures
import gc

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.route import Route, RouteGenerator
from utils.jeep_system import JeepSystem, FleetAllocator
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.simulation import Simulation, SimulationResult
from utils.passenger_generator import PassengerGenerator
from utils.pheromone import PheromoneMatrix
from utils.local_search import ACOLocalSearch
from utils.simulation_parallel import ParallelSimulationRunner

# =========================================================
# City Graph
# =========================================================

def build_citygraph(yaml_file: str, pkl_path: Optional[str] = None) -> CityGraph:
    print(f"[INFO] Building CityGraph from YAML file: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) 
    cg_config = config.get('city_graph', {})
    if 'bbox' in cg_config and isinstance(cg_config['bbox'], list):
        cg_config['bbox'] = tuple(cg_config['bbox'])
    cg = CityGraph(**cg_config)
    
    if pkl_path:
        import os
        os.makedirs(os.path.dirname(pkl_path), exist_ok=True)
        print(f"[INFO] Serializing CityGraph to pickle file: {pkl_path}")
        with open(pkl_path, 'wb') as f:
            pickle.dump(cg, f)
        print(f"[INFO] CityGraph successfully serialized to pickle file: {pkl_path}")
            
    return cg

def reuse_citygraph(pkl_file: str) -> CityGraph:
    print(f"[INFO] Reusing CityGraph from pickle file: {pkl_file}")
    with open(pkl_file, 'rb') as f:
        cg = pickle.load(f)
    return cg

# =========================================================
# Direct Demand Model
# =========================================================

def build_ddm(yaml_file: str, cg: CityGraph, target_time: Optional[datetime], pkl_path: Optional[str] = None) -> DirectDemandSampler:
    print(f"[INFO] Building DirectDemandSampler from YAML file: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
        
    ddm_config_data = config_data.get('ddm', {})
    
    ddm_config = DDMConfig(
        alpha=ddm_config_data.get('alpha', 0.6),
        beta=ddm_config_data.get('beta', 0.4),
        target_time=target_time
    )
    
    # use_cache=False to avoid relying on pre-existing DDM internal cache
    ddm = DirectDemandSampler(city=cg, config=ddm_config, verbose=True, use_cache=False)
    if pkl_path:
        import os
        os.makedirs(os.path.dirname(pkl_path), exist_ok=True)
        print(f"[INFO] Serializing DirectDemandSampler to pickle file: {pkl_path}")
        with open(pkl_path, 'wb') as f:
            pickle.dump(ddm, f)
        print(f"[INFO] DirectDemandSampler successfully serialized to pickle file: {pkl_path}")
            
    return ddm

def reuse_ddm(pkl_file: str) -> DirectDemandSampler:
    print(f"[INFO] Reusing DirectDemandSampler from pickle file: {pkl_file}")
    with open(pkl_file, 'rb') as f:
        ddm = pickle.load(f)
    return ddm

# =========================================================
# Jeep and Route Systems
# =========================================================

def generate_route_system(num_routes: int, cg: CityGraph, sampler: DirectDemandSampler) -> list[Route]:
    print(f"[INFO] Generating {num_routes} routes...")
    generator = RouteGenerator(city_graph=cg, sampler=sampler, verbose=True)
    return [generator.generate(n_points=4) for _ in range(num_routes)]

def generate_jeep_system(routes: list[Route], num_jeeps: int, sampler: DirectDemandSampler, tg: TravelGraph, mohring_sample_size = 200) -> JeepSystem:
    print(f"[INFO] Allocating fleet of {num_jeeps} jeeps across {len(routes)} routes using Mohring Effect...")
    allocations = FleetAllocator.allocate_by_mohring(
        total_fleet=num_jeeps,
        routes=routes,
        sampler=sampler,
        tg=tg,
        mohring_sample_size=mohring_sample_size
    )
    
    jeeps = []
    for route, count in allocations.items():
        for _ in range(count):
            start_coord = (route.path[0].start.lon, route.path[0].start.lat)
            jeeps.append(Jeep(route, curr_pos=start_coord, speed=40.0, max_capacity=16))
            
    print(f"[INFO] JeepSystem created with {len(jeeps)} jeeps.")
    return JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=50.0, equidistant_spawn=True)

# =========================================================
# Travel Graph
# =========================================================

def build_travelgraph(cg: CityGraph, yaml_file: str, routes: list[Route], pkl_path: Optional[str] = None) -> TravelGraph:
    print(f"[INFO] Building TravelGraph using config from: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
        
    tg_config = config_data.get('travel_graph', {})
    tg = TravelGraph(cg=cg, config=tg_config, routes=routes)
    
    if pkl_path:
        import os
        os.makedirs(os.path.dirname(pkl_path), exist_ok=True)
        print(f"[INFO] Serializing TravelGraph to pickle file: {pkl_path}")
        with open(pkl_path, 'wb') as f:
            pickle.dump(tg, f)
        print(f"[INFO] TravelGraph successfully serialized to pickle file: {pkl_path}")
            
    return tg

def reuse_travelgraph(pkl_file: str) -> TravelGraph:
    print(f"[INFO] Reusing TravelGraph from pickle file: {pkl_file}")
    with open(pkl_file, 'rb') as f:
        tg = pickle.load(f)
    return tg

# =========================================================
# Simulation
# =========================================================

@dataclass
class SimEnvironment:
    """
    Lightweight container for a simulation setup.
    """
    tg: TravelGraph
    yaml_file: str
    jeep_system: JeepSystem
    sampler: DirectDemandSampler
    delete_yaml_when_done: bool = False

def generate_dummy_yaml(export_loc: str, **kwargs) -> str:
    print(f"[INFO] Generating dummy YAML at {export_loc} with overrides: {kwargs}")
    with open('configs/profile_p1.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    for k, v in kwargs.items():
        parts = k.split('.')
        target = config
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = v
        
    os.makedirs(os.path.dirname(export_loc), exist_ok=True)
    with open(export_loc, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)
    
    return export_loc

def run_simulation(tg: TravelGraph, yaml_file: str, jeep_system: JeepSystem, sampler: DirectDemandSampler, delete_yaml_when_done = False) -> Simulation:
    print(f"[INFO] Initializing simulation from YAML: {yaml_file}")
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    sim_cfg = config.get('simulation', {})
    seconds_per_tick = sim_cfg.get("seconds_per_tick", 1)
    
    passenger_generator = PassengerGenerator(
        tg=tg,
        sampler=sampler,
        rate_per_hour=sim_cfg.get("spawn_rate_per_hour", 40.0),
        stdev=sim_cfg.get("spawn_stdev", 5.0),
        speed=sim_cfg.get("passenger_speed_kmh", 5.0),
        seconds_per_tick=seconds_per_tick
    )
    
    if jeep_system and jeep_system.jeeps:
        for jeep in jeep_system.jeeps:
            jeep.seconds_per_tick = seconds_per_tick
            
    sim = Simulation(
        city_query=config.get("city_graph", {}).get("name", "City"),
        bounds=tg.cg.get_bounds(),
        jeep_system=jeep_system,
        passenger_generator=passenger_generator,
        max_ticks=sim_cfg.get("num_ticks", 3600),
        beta_penalty=config.get("BETA_PENALTY", 2.0),
        alpha_std_penalty=config.get("ALPHA_STD_PENALTY", 0.5),
        config=config
    )
    
    print(f"[INFO] Running simulation for {sim.max_ticks} ticks...")
    # Just run it silently since it has its own tqdm
    sim.run() 

    # Delete YAML if requested
    if delete_yaml_when_done:
        print(f"[INFO] Deleting YAML file: {yaml_file}")
        os.remove(yaml_file)

    return sim

def collect_metrics(sim: Simulation, export_loc: str) -> SimulationResult:
    if not export_loc:
        raise ValueError("[INFO] collect_metrics requires a valid export_loc.")
        
    print(f"[INFO] Collecting metrics and exporting to {export_loc}...")
    result = sim.evaluate_fitness()
    result.export_report(export_loc)
    
    return result

def run_simulation_env(env: SimEnvironment) -> Simulation:
    """
    Wrapper to run a simulation using a SimEnvironment object.
    """
    return run_simulation(
        tg=env.tg,
        yaml_file=env.yaml_file,
        jeep_system=env.jeep_system,
        sampler=env.sampler,
        delete_yaml_when_done=env.delete_yaml_when_done
    )

def run_simulations_parallel(envs: list[SimEnvironment], max_workers: Optional[int] = None) -> list[SimulationResult]:
    """
    Runs an array of SimEnvironment setups in parallel using the ParallelSimulationRunner.
    Requires that all environments share the same base configuration parameters (from the first yaml_file).
    """
    if not envs:
        return []
        
    base_yaml = envs[0].yaml_file
    with open(base_yaml, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    runner = ParallelSimulationRunner(config=config, max_workers=max_workers)
    routes_list = [env.jeep_system.routes for env in envs]
    
    results = runner.run_parallel(routes_list)
    
    for env in envs:
        if env.delete_yaml_when_done:
            try:
                os.remove(env.yaml_file)
            except OSError:
                pass
                
    return results

def create_persistent_runner(yaml_file: str, max_workers: Optional[int] = None) -> ParallelSimulationRunner:
    """
    Creates a ParallelSimulationRunner with a persistent worker pool.
    
    Workers are initialized ONCE and survive across multiple run_parallel() calls.
    This eliminates the ~90s per-call overhead of loading CityGraph + DDM pickles
    in each worker process — critical for sweep notebooks that call evaluate dozens
    of times.
    
    Usage:
        runner = create_persistent_runner("configs/profile_p1.yaml")
        runner.open_pool()      # workers start and load heavy objects once
        ...
        results = run_simulations_with_runner(runner, envs)
        results = run_simulations_with_runner(runner, envs2)  # reuses same workers
        ...
        runner.close_pool()     # cleanup when done
        
    Or as a context manager:
        with create_persistent_runner("configs/profile_p1.yaml") as runner:
            results = run_simulations_with_runner(runner, envs)
    """
    with open(yaml_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return ParallelSimulationRunner(config=config, max_workers=max_workers)

def run_simulations_with_runner(runner: ParallelSimulationRunner, envs: list[SimEnvironment]) -> list[SimulationResult]:
    """
    Runs simulations using an existing (potentially persistent) ParallelSimulationRunner.
    Unlike run_simulations_parallel(), this does NOT create a new runner per call.
    """
    if not envs:
        return []
    
    routes_list = [env.jeep_system.routes for env in envs]
    results = runner.run_parallel(routes_list)

    for env in envs:
        if env.delete_yaml_when_done:
            try:
                os.remove(env.yaml_file)
            except OSError:
                pass

    return results

def run_reps_overrides(runner: ParallelSimulationRunner, routes: list[Route], n_reps: int, overrides: dict) -> list[SimulationResult]:
    """
    Runs `n_reps` stochastic replications of the SAME route system through a
    (persistent) ParallelSimulationRunner, applying `overrides` to every replication.

    Because num_ticks / spawn_rate_per_hour / seconds_per_tick / total_allocatable_jeeps
    are passed as per-call overrides, a persistent pool reuses its workers and cached
    TravelGraph across the entire sweep — no ~90s worker reload, no TravelGraph rebuild.

    Example:
        results = run_reps_overrides(runner, routes, 7,
                                     {"num_ticks": 540, "spawn_rate_per_hour": 900,
                                      "seconds_per_tick": 10, "total_allocatable_jeeps": 50})
        scores = [r.score for r in results if r is not None]
    """
    routes_list = [routes for _ in range(n_reps)]
    overrides_list = [overrides for _ in range(n_reps)]
    return runner.run_parallel_overrides(routes_list, overrides_list)


# =========================================================
# Pheromones and Mutators
# =========================================================

def build_pheromone_matrix(cg: CityGraph, sim_result: SimulationResult) -> PheromoneMatrix:
    """
    Initializes a fresh PheromoneMatrix from the CityGraph and immediately
    stamps the passenger flows from the SimulationResult onto it.
    """
    config = sim_result.metrics.get("config", {}) if hasattr(sim_result, "metrics") else {}
    phero = PheromoneMatrix(all_edges=cg.graph, config=config, sim_result=sim_result)
    
    # Pre-compute gaps if jeep_system is available (if not stripped by IPC)
    if hasattr(sim_result, "jeep_system") and sim_result.jeep_system is not None:
        phero.gaps = phero.calculate_demand_service_gaps(sim_result.jeep_system)
    else:
        phero.gaps = {}
        
    return phero

def blend_pheromone_matrix(parentA, parentB, cg: CityGraph) -> PheromoneMatrix:
    """
    Blends two parent Chromosomes (or objects with .pheromones and .cost) 
    using a fitness-weighted arithmetic crossover.
    """
    if not hasattr(parentA, 'cost') or not hasattr(parentA, 'pheromones'):
        raise ValueError("[UTILS] parentA must have 'cost' and 'pheromones' attributes.")
        
    total_cost = parentA.cost + parentB.cost
    if total_cost == 0.0:
        total_cost = 1.0

    weight_a = parentB.cost / total_cost
    weight_b = parentA.cost / total_cost

    parent_cfg = {
        "optimization": {
            "initial_tau": parentA.pheromones.initial_tau,
            "rho": parentA.pheromones.rho,
            "q": parentA.pheromones.q,
            "default_jeep_weight": parentA.pheromones.default_jeep_weight,
        }
    }
    
    child_phero = PheromoneMatrix(all_edges=cg.graph, config=parent_cfg)
    
    all_edges = set(parentA.pheromones.tau.keys()).union(parentB.pheromones.tau.keys())
    for e in all_edges:
        tau_a = parentA.pheromones.tau.get(e, 0.0)
        tau_b = parentB.pheromones.tau.get(e, 0.0)
        blended = (weight_a * tau_a) + (weight_b * tau_b)
        if blended > 0.0:
            child_phero.tau[e] = blended

    return child_phero

def mutate_attraction(matrix: PheromoneMatrix, route_system: list[Route], cg: CityGraph, intensity: float = 1.0) -> list[Route]:
    """
    Applies the Spatial Attraction (Or-Opt Transplant) operator to the route system.
    """
    import copy
    routes_copy = [Route(path=r.path[:], city_graph=cg) for r in route_system]
    
    ls = ACOLocalSearch(cg)
    # Ensure gaps are populated
    if not matrix.gaps:
        matrix.gaps = matrix.calculate_demand_service_gaps(routes_copy)
        
    result = ls.strategy_spatial_attraction(routes_copy, matrix, intensity)
    return routes_copy if result else route_system

def mutate_repulsion(matrix: PheromoneMatrix, route_system: list[Route], cg: CityGraph, intensity: float = 1.0) -> list[Route]:
    """
    Applies the Redundancy Repulsion (2-Opt Exchange) operator to the route system.
    """
    import copy
    routes_copy = [Route(path=r.path[:], city_graph=cg) for r in route_system]
    
    ls = ACOLocalSearch(cg)
    if not matrix.gaps:
        matrix.gaps = matrix.calculate_demand_service_gaps(routes_copy)
        
    result = ls.strategy_redundancy_repulsion(routes_copy, matrix, intensity)
    return routes_copy if result else route_system

def mutate_pruning(matrix: PheromoneMatrix, route_system: list[Route], cg: CityGraph, intensity: float = 1.0) -> list[Route]:
    """
    Applies the Tortuosity Pruning operator to the route system.
    """
    import copy
    routes_copy = [Route(path=r.path[:], city_graph=cg) for r in route_system]
    
    ls = ACOLocalSearch(cg)
    if not matrix.gaps:
        matrix.gaps = matrix.calculate_demand_service_gaps(routes_copy)
        
    n_prunes, _ = ls.strategy_tortuosity_pruning(routes_copy, matrix, intensity)
    return routes_copy if n_prunes > 0 else route_system

def crossover_routes(routesA: list[Route], matrixA: PheromoneMatrix, routesB: list[Route], cg: CityGraph, target_route_count: int = 4) -> list[Route]:
    """
    Executes a topological crossover utilizing a high-demand sub-graph cluster,
    blending the structural properties of two parent route systems.
    """
    from utils.genetic import MemeticAlgorithm
    from utils.local_search import ACOLocalSearch
    
    ls = ACOLocalSearch(cg)
    ma = MemeticAlgorithm(cg, ls, target_route_count)
    
    class DummyChrom:
        def __init__(self, r, p):
            self.routes = r
            self.pheromones = p
            
    pA = DummyChrom(routesA, matrixA)
    pB = DummyChrom(routesB, None)
    
    return ma.crossover_topological_hub(pA, pB)


# =========================================================
# Evolutionary Optimizer & Telemetry Facade
# =========================================================

def build_optimizer(yaml_file: str, resume_dir: Optional[str] = None):
    """
    Constructs a genetic algorithm Optimizer instance from a YAML config file.
    If resume_dir is provided, it attempts to load from the latest state checkpoint.
    """
    from utils.optimizer import Optimizer
    from pathlib import Path
    
    if resume_dir:
        print(f"[INFO] Resuming Optimizer from run directory: {resume_dir}")
        return Optimizer(Path(resume_dir))
    else:
        print(f"[INFO] Building fresh Optimizer using config: {yaml_file}")
        return Optimizer.create(Path(yaml_file))

def process_telemetry(run_dir: str) -> dict:
    """
    Parses telemetry files (history.csv and lineage.csv) from an optimizer run directory.
    Returns a dictionary containing pandas DataFrames for easy plotting and analysis.
    """
    import pandas as pd
    from pathlib import Path
    
    run_path = Path(run_dir)
    history_file = run_path / "history.csv"
    lineage_file = run_path / "lineage.csv"
    
    result = {}
    
    if history_file.exists():
        print(f"[INFO] Parsing history file: {history_file}")
        try:
            df_history = pd.read_csv(history_file)
            result["history"] = df_history
        except Exception as e:
            print(f"[WARNING] Failed to parse history.csv: {e}")
            result["history"] = pd.DataFrame()
    else:
        print(f"[WARNING] history.csv not found in {run_dir}")
        result["history"] = pd.DataFrame()
        
    if lineage_file.exists():
        print(f"[INFO] Parsing lineage file: {lineage_file}")
        try:
            df_lineage = pd.read_csv(lineage_file)
            result["lineage"] = df_lineage
        except Exception as e:
            print(f"[WARNING] Failed to parse lineage.csv: {e}")
            result["lineage"] = pd.DataFrame()
    else:
        print(f"[WARNING] lineage.csv not found in {run_dir}")
        result["lineage"] = pd.DataFrame()
        
    return result

def load_generation_snapshot(run_dir: str, generation: int) -> dict:
    """
    Loads a specific generation JSON snapshot from the run directory snapshots.
    """
    import json
    from pathlib import Path
    
    snapshot_path = Path(run_dir) / "snapshots" / f"network_state_gen_{generation}.json"
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot for generation {generation} not found at {snapshot_path}")
        
    with open(snapshot_path, "r", encoding="utf-8") as f:
        return json.load(f)

    