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

# -----------------------------------------------------------------------------
# Worker Process Global State
# -----------------------------------------------------------------------------
# These will be initialized exactly once per CPU worker process to avoid pickling
# heavy objects repeatedly across the IPC (Inter-Process Communication) boundary.
_WORKER_CONFIG = None
_WORKER_CITY_GRAPH = None
_WORKER_DEMAND_SAMPLER = None
_WORKER_TG_CACHE = None          # Cached TravelGraph (reused if routes unchanged)
_WORKER_ROUTES_CACHE = None      # Cached restored routes
_WORKER_ROUTES_KEY = None        # Hash key to detect route changes


def _worker_init(config: dict):
    """
    Called once when a worker process starts.
    We rebuild the heavy CityGraph and DemandSampler here so they persist
    for all simulation runs assigned to this specific worker core.
    """
    global _WORKER_CONFIG, _WORKER_CITY_GRAPH, _WORKER_DEMAND_SAMPLER
    _WORKER_CONFIG = config
    
    print(f"[Worker {os.getpid()}] Initializing static CityGraph and Sampler...")
    
    # Check if pre-computed pickle files are provided to bypass slow initialization
    cg_pkl = config.get("cg_pkl")
    ddm_pkl = config.get("ddm_pkl")
    
    if cg_pkl and os.path.exists(cg_pkl):
        print(f"[Worker {os.getpid()}] Loading CityGraph from {cg_pkl}...")
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
        print(f"[Worker {os.getpid()}] Loading DirectDemandSampler from {ddm_pkl}...")
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
    print(f"[Worker {os.getpid()}] Initialization complete.")


def _restore_route(route: Route, cg: CityGraph) -> Route:
    """
    When a Route is sent across IPC, its custom __setstate__ clears its path
    and cg references, leaving only path_keys to keep it lightweight.
    This reconstructs the heavy path objects securely in the worker memory.
    """
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
            
        # Promote to Layer 2 Edge as defined in Route promotion logic
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
    """Backward-compatible entry point. Runs with the frozen worker config (no overrides)."""
    return _worker_run_override((routes, None))


def _worker_run_override(arg) -> SimulationResult:
    """
    Executes a single simulation run within the worker process using the lightweight routes.
    Caches the TravelGraph so it's only rebuilt when the route set changes.

    `arg` is a tuple ``(routes, overrides)``. ``overrides`` is an optional dict of
    per-call simulation-parameter overrides (e.g. ``num_ticks``, ``spawn_rate_per_hour``,
    ``seconds_per_tick``, ``total_allocatable_jeeps``). When ``None`` the frozen worker
    config is used unchanged — byte-for-byte identical to the original behavior.
    Crucially, none of the override keys affect the heavy objects (CityGraph,
    DemandSampler, cached TravelGraph), so a PERSISTENT pool can sweep these scalars
    without any worker re-initialization or TravelGraph rebuild.
    """
    routes, overrides = arg
    global _WORKER_CONFIG, _WORKER_CITY_GRAPH, _WORKER_DEMAND_SAMPLER
    global _WORKER_TG_CACHE, _WORKER_ROUTES_CACHE, _WORKER_ROUTES_KEY

    if _WORKER_CITY_GRAPH is None or _WORKER_DEMAND_SAMPLER is None:
        raise RuntimeError(f"[Worker {os.getpid()}] process was not properly initialized with static objects.")

    # 1. Check if we can reuse cached TravelGraph
    route_key = tuple(getattr(r, 'id', i) for i, r in enumerate(routes))
    
    if _WORKER_TG_CACHE is not None and _WORKER_ROUTES_KEY == route_key:
        restored_routes = _WORKER_ROUTES_CACHE
        tg = _WORKER_TG_CACHE
    else:
        # Restore Lightweight Routes to Heavy Routes
        restored_routes = [_restore_route(r, _WORKER_CITY_GRAPH) for r in routes]
        tg = TravelGraph(
            cg=_WORKER_CITY_GRAPH,
            config=_WORKER_CONFIG.get("travel_graph", {}).copy(),
            routes=restored_routes
        )
        _WORKER_TG_CACHE = tg
        _WORKER_ROUTES_CACHE = restored_routes
        _WORKER_ROUTES_KEY = route_key
        print(f"[Worker {os.getpid()}] Built TravelGraph ({len(tg.travel_graph)} edges)")

    # 2. Build Local Heavy Objects
    # Merge per-call overrides over the frozen worker config. When overrides is
    # None this is an exact shallow copy of the original simulation config.
    sim_cfg = {**_WORKER_CONFIG.get("simulation", {}), **(overrides or {})}
    total_jeeps = sim_cfg.get("total_allocatable_jeeps", 25)
    jeep_speed_kmh = sim_cfg.get("jeep_speed_kmh", 40.0)
    jeep_capacity = sim_cfg.get("jeep_capacity", 16)
    weight_tol = sim_cfg.get("weight_tolerance", 50.0)
    seconds_per_tick = sim_cfg.get("seconds_per_tick", 1)
    jeeps_per_route = max(1, total_jeeps // len(restored_routes)) if restored_routes else 0
    
    jeeps = []
    for route in restored_routes:
        for _ in range(jeeps_per_route):
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

    
    # 3. Execute Simulation
    result = sim.run()
    
    # 4. Cleanup & Memory Isolation
    # Detach the complex jeep_system (which holds graph nodes) from the result
    # to prevent ProcessPoolExecutor from pickling it.
    result.jeep_system = None
    
    # Delete only the local simulation objects.
    # Do NOT delete tg / restored_routes — they are aliased to the global
    # _WORKER_TG_CACHE / _WORKER_ROUTES_CACHE and must survive for reuse.
    del passenger_generator
    del jeep_system
    del sim
    del jeeps
    gc.collect()  # 2000-jeep sims form reference cycles; reclaim them before the worker's next eval

    # Return the lightweight object
    return result


class ParallelSimulationRunner:
    """
    Manages a pool of worker processes to execute multiple simulations concurrently.
    
    Supports two modes:
    1. One-shot (original): Each run_parallel() call creates and destroys a pool.
    2. Persistent pool: Call open_pool() / close_pool() or use as a context manager
       to keep workers alive across multiple run_parallel() calls. This avoids
       the ~90s-per-call worker initialization overhead in sweep loops.
    """
    def __init__(self, config: dict, max_workers: int = None):
        self.config = config
        self.max_workers = max_workers or max(1, os.cpu_count() - 1)
        self._executor = None
        
    def open_pool(self):
        """Starts a persistent worker pool. Workers survive across run_parallel() calls."""
        if self._executor is not None:
            return  # Already open
        self._executor = concurrent.futures.ProcessPoolExecutor(
            max_workers=self.max_workers,
            initializer=_worker_init,
            initargs=(self.config,)
        )
        print(f"[ParallelRunner] Opened persistent pool with {self.max_workers} workers.")
        
    def close_pool(self):
        """Shuts down the persistent worker pool."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
            print("[ParallelRunner] Persistent pool closed.")
            
    def __enter__(self):
        self.open_pool()
        return self
        
    def __exit__(self, *args):
        self.close_pool()
        
    def run_parallel(self, routes_list: List[List[Route]]) -> List[SimulationResult]:
        """
        Executes simulations for a list of route configurations in parallel.
        
        Args:
            routes_list: A list where each element is a list of Route objects
                         representing a single simulation setup.
                         
        Returns:
            A list of SimulationResult objects.
        """
        print(f"[ParallelRunner] Starting parallel execution across {self.max_workers} CPU cores for {len(routes_list)} setups...")
        results = []
        
        if self._executor is not None:
            # Persistent pool mode — reuse existing workers
            for result in self._executor.map(_worker_run, routes_list):
                results.append(result)
        else:
            # One-shot mode (backward compatible) — create and destroy pool
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=_worker_init,
                initargs=(self.config,)
            ) as executor:
                for result in executor.map(_worker_run, routes_list):
                    results.append(result)
                
        print(f"[ParallelRunner] Successfully completed {len(results)} parallel simulations.")
        return results

    def run_parallel_overrides(self, routes_list: List[List[Route]], overrides_list: List[dict]) -> List[SimulationResult]:
        """
        Like run_parallel(), but applies a per-setup dict of simulation-parameter
        overrides to each run. This lets a PERSISTENT pool sweep scalars such as
        num_ticks / spawn_rate_per_hour / seconds_per_tick / total_allocatable_jeeps
        WITHOUT re-initializing workers or rebuilding the cached TravelGraph — the
        decisive speedup for parameter-sweep notebooks.

        Args:
            routes_list:    list of route-systems (one per setup).
            overrides_list: list of override dicts (same length); each is merged over
                            the frozen 'simulation' config for its setup.
        """
        if len(routes_list) != len(overrides_list):
            raise ValueError("routes_list and overrides_list must have the same length.")

        print(f"[ParallelRunner] Sweeping {len(routes_list)} setups across {self.max_workers} cores (override mode)...")
        results = []
        args = list(zip(routes_list, overrides_list))

        if self._executor is not None:
            # Persistent pool mode — reuse existing workers and their cached TravelGraph
            for result in self._executor.map(_worker_run_override, args):
                results.append(result)
        else:
            # One-shot mode (backward compatible)
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=_worker_init,
                initargs=(self.config,)
            ) as executor:
                for result in executor.map(_worker_run_override, args):
                    results.append(result)

        print(f"[ParallelRunner] Completed {len(results)} simulations (override mode).")
        return results
