import yaml
import pickle
from typing import Optional
from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig

from utils.route import Route, RouteGenerator
from utils.jeep_system import JeepSystem, FleetAllocator
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.simulation import Simulation, SimulationResult
from utils.passenger_generator import PassengerGenerator
from utils.travel_graph import TravelGraph

from datetime import datetime

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

def generate_jeep_system(routes: list[Route], num_jeeps: int, sampler: DirectDemandSampler, tg: TravelGraph) -> JeepSystem:
    print(f"[INFO] Allocating fleet of {num_jeeps} jeeps across {len(routes)} routes using Mohring Effect...")
    allocations = FleetAllocator.allocate_by_mohring(
        total_fleet=num_jeeps,
        routes=routes,
        sampler=sampler,
        tg=tg,
        mohring_sample_size=2000
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

# =========================================================
# Simulation
# =========================================================

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
    passenger_generator = PassengerGenerator(
        tg=tg,
        sampler=sampler,
        rate_per_hour=sim_cfg.get("spawn_rate_per_hour", 40.0),
        stdev=sim_cfg.get("spawn_stdev", 5.0),
        speed=sim_cfg.get("passenger_speed_kmh", 5.0)
    )
    
    sim = Simulation(
        city_query=config.get("city_graph", {}).get("name", "City"),
        bounds=tg.city_graph.get_bounds(),
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