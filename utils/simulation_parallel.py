import os
import gc
import concurrent.futures
from typing import List, Dict, Any, Tuple

from .city_graph import CityGraph
from .direct_demand_sampler import DirectDemandSampler, DDMConfig
from .travel_graph import TravelGraph
from .jeep_system import JeepSystem
from .passenger_generator import PassengerGenerator
from .simulation import Simulation, SimulationResult
from .route import Route
from .jeep import Jeep
from .directed_edge import DirEdge

_WORKER_CONFIG = None
_WORKER_CITY_GRAPH = None
_WORKER_DEMAND_SAMPLER = None
_WORKER_TG_CACHE = None          
_WORKER_ROUTES_CACHE = None      
_WORKER_ROUTES_KEY = None        


def _worker_init(config: dict):
    global _WORKER_CONFIG, _WORKER_CITY_GRAPH, _WORKER_DEMAND_SAMPLER
    _WORKER_CONFIG = config

    if "toy_city" in config:
        from .toy_city import toy_setup_from_dict
        _WORKER_CITY_GRAPH, _WORKER_DEMAND_SAMPLER, _ = toy_setup_from_dict(config, verbose=False)
        return

    cg_pkl = config.get("cg_pkl")
    ddm_pkl = config.get("ddm_pkl")
    
    if cg_pkl and os.path.exists(cg_pkl):
        import pickle
        with open(cg_pkl, 'rb') as f:
            _WORKER_CITY_GRAPH = pickle.load(f)
    else:
        cg_cfg = config.get("city_graph", {})
        _WORKER_CITY_GRAPH = CityGraph(
            bbox=tuple(cg_cfg.get("bbox")) if "bbox" in cg_cfg else None,
            name=cg_cfg.get("name", "UrbanNetwork"),
            landmarks=cg_cfg.get("landmarks"),
            pbf_path=cg_cfg.get("pbf_path")
        )
        
    if ddm_pkl and os.path.exists(ddm_pkl):
        import pickle
        with open(ddm_pkl, 'rb') as f:
            _WORKER_DEMAND_SAMPLER = pickle.load(f)
        _WORKER_DEMAND_SAMPLER.city = _WORKER_CITY_GRAPH
    else:
        _WORKER_DEMAND_SAMPLER = DirectDemandSampler(
            city=_WORKER_CITY_GRAPH,
            config=DDMConfig(**config.get("ddm", {})),
            verbose=False
        )


def _restore_route(route: Route, cg: CityGraph) -> Route:
    if route.path:
        return route
        
    if not hasattr(cg, '_edge_lookup'):
        lookup = {}
        for edge in cg.graph:
            key = ((edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat))
            lookup[key] = edge
        cg._edge_lookup = lookup

    restored_path = []
    for key in getattr(route, 'path_keys', []):
        edge = cg._edge_lookup.get(key)
        if not edge:
            raise ValueError(f"[Worker {os.getpid()}] Could not restore route edge {key} in worker CityGraph.")
            
        l2_edge = DirEdge(edge.start, edge.end, weight=edge.weight)
        setattr(l2_edge, 'layer', 2)
        restored_path.append(l2_edge)
        
    for i in range(len(restored_path)):
        next_edge = restored_path[(i + 1) % len(restored_path)]
        restored_path[i].next_edges.append(next_edge)
        
    restored_route = Route(cg, restored_path, id=route.id)
    restored_route.designated_color = route.designated_color
    return restored_route


def _worker_run(routes: List[Route]) -> SimulationResult:
    return _worker_run_override((routes, None))


def _worker_run_override(arg) -> SimulationResult:
    routes, overrides = arg
    global _WORKER_CONFIG, _WORKER_CITY_GRAPH, _WORKER_DEMAND_SAMPLER
    global _WORKER_TG_CACHE, _WORKER_ROUTES_CACHE, _WORKER_ROUTES_KEY

    if _WORKER_CITY_GRAPH is None or _WORKER_DEMAND_SAMPLER is None:
        raise RuntimeError(f"[Worker {os.getpid()}] process was not properly initialized with static objects.")

    route_key = tuple(getattr(r, 'id', i) for i, r in enumerate(routes))
    
    if _WORKER_TG_CACHE is not None and _WORKER_ROUTES_KEY == route_key:
        restored_routes = _WORKER_ROUTES_CACHE
        tg = _WORKER_TG_CACHE
    else:
        restored_routes = [_restore_route(r, _WORKER_CITY_GRAPH) for r in routes]
        tg = TravelGraph(
            cg=_WORKER_CITY_GRAPH,
            config=_WORKER_CONFIG.get("travel_graph", {}).copy(),
            routes=restored_routes
        )
        _WORKER_TG_CACHE = tg
        _WORKER_ROUTES_CACHE = restored_routes
        _WORKER_ROUTES_KEY = route_key

    sim_cfg = {**_WORKER_CONFIG.get("simulation", {}), **(overrides or {})}
    total_jeeps = sim_cfg.get("total_allocatable_jeeps", 25)
    jeep_speed_kmh = sim_cfg.get("jeep_speed_kmh", 40.0)
    jeep_capacity = sim_cfg.get("jeep_capacity", 16)
    weight_tol = sim_cfg.get("weight_tolerance", 50.0)
    seconds_per_tick = sim_cfg.get("seconds_per_tick", 1)
    
    from .jeep_system import FleetAllocator
    allocation = FleetAllocator.allocate_by_mohring(
        total_fleet=total_jeeps,
        routes=restored_routes,
        sampler=_WORKER_DEMAND_SAMPLER,
        tg=tg,
        mohring_sample_size=sim_cfg.get("mohring_sample_size", 2000)
    )
    
    jeeps = []
    for route, count in allocation.items():
        for _ in range(count):
            start_coord = (route.path[0].start.lon, route.path[0].start.lat)
            jeeps.append(Jeep(route, curr_pos=start_coord, speed=jeep_speed_kmh, max_capacity=jeep_capacity, seconds_per_tick=seconds_per_tick))
            
    jeep_system = JeepSystem(
        jeeps=jeeps, 
        routes=restored_routes, 
        weight_tolerance=weight_tol,
        equidistant_spawn=True
    )
    
    passenger_generator = PassengerGenerator(
        tg=tg,
        sampler=_WORKER_DEMAND_SAMPLER,
        rate_per_hour=sim_cfg.get("spawn_rate_per_hour", 40.0),
        stdev=sim_cfg.get("spawn_stdev", 5.0),
        speed=sim_cfg.get("passenger_speed_kmh", 5.0),
        seconds_per_tick=seconds_per_tick
    )
    
    worker_cfg = _WORKER_CONFIG.copy()
    worker_cfg["disable_tqdm"] = True
    sim = Simulation(
        city_query=worker_cfg.get("city_graph", {}).get("name", "City"),
        bounds=_WORKER_CITY_GRAPH.get_bounds(),
        jeep_system=jeep_system,
        passenger_generator=passenger_generator,
        max_ticks=sim_cfg.get("num_ticks", 3600),
        beta_penalty=float(worker_cfg.get("BETA_PENALTY", 2.0)),
        alpha_std_penalty=float(worker_cfg.get("ALPHA_STD_PENALTY", 0.5)),
        config=worker_cfg
    )

    result = sim.run()
    
    # 4. Cleanup & Memory Isolation
    result.jeep_system = None
    
    try:
        result.metrics["commute_times_min"] = [
            (p.despawn_tick - p.spawn_tick) / 60.0
            for p in passenger_generator.archived_passengers
            if getattr(p, "despawn_tick", None) is not None
        ]
    except Exception:
        pass

    # --- NEW: Flatten DirEdge objects into primitive coordinate tuples for lightning-fast IPC transfer ---
    flattened_paths = []
    for path, cost in result.recorded_paths:
        if path:
            # Only send the primitive coordinates across the boundary, saving gigabytes of pickling overhead
            flat_path = [((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)) for e in path]
            flattened_paths.append((flat_path, cost))
    result.recorded_paths = flattened_paths
    # ---------------------------------------------------------------------------------------------------

    for j in jeeps:
        j.onboard_passengers.clear()
        
    for p in passenger_generator.passengers + passenger_generator.archived_passengers:
        p.current_jeep = None

    del passenger_generator
    del jeep_system
    del sim
    del jeeps
    
    return result


class ParallelSimulationRunner:
    def __init__(self, config: dict, max_workers: int = None):
        self.config = config
        self.max_workers = max_workers or max(1, os.cpu_count() - 1)
        self._executor = None
        
    def open_pool(self):
        if self._executor is not None:
            return
        self._executor = concurrent.futures.ProcessPoolExecutor(
            max_workers=self.max_workers,
            initializer=_worker_init,
            initargs=(self.config,)
        )
        
    def close_pool(self):
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
            
    def __enter__(self):
        self.open_pool()
        return self
        
    def __exit__(self, *args):
        self.close_pool()
        
    def run_parallel(self, routes_list: List[List[Route]]) -> List[SimulationResult]:
        results = []
        
        if self._executor is not None:
            for result in self._executor.map(_worker_run, routes_list):
                results.append(result)
        else:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=_worker_init,
                initargs=(self.config,)
            ) as executor:
                for result in executor.map(_worker_run, routes_list):
                    results.append(result)
                
        return results

    def run_parallel_overrides(self, routes_list: List[List[Route]], overrides_list: List[dict]) -> List[SimulationResult]:
        if len(routes_list) != len(overrides_list):
            raise ValueError("routes_list and overrides_list must have the same length.")

        results = []
        args = list(zip(routes_list, overrides_list))

        if self._executor is not None:
            for result in self._executor.map(_worker_run_override, args):
                results.append(result)
        else:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=_worker_init,
                initargs=(self.config,)
            ) as executor:
                for result in executor.map(_worker_run_override, args):
                    results.append(result)

        return results