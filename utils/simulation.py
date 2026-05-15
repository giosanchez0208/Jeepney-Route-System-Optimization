"""Flow: setup -> graphs, routes, jeeps, passengers -> simulation ticks -> result export.

SimulationSetup(city_query: str, config: dict, routes: list[Route]) -> None wraps initialization.
build(self, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None) -> Simulation assembles the runtime stack.
SimulationResult(fitness_score: float, metrics: dict[str, Any], recorded_paths: list[tuple[Any, float]], jeep_system: Optional[JeepSystem] = None, sim_id: Optional[str] = None) -> None stores metrics and export helpers.
export_map(self, area_query: str, out_dir: str, draw_routes: bool = True) -> None, export_report(self, out_dir: str) -> None, and from_file(cls, filepath: str) -> SimulationResult handle saved outputs.
Simulation(city_query: str, bounds: tuple[float, float, float, float], jeep_system: JeepSystem, passenger_generator: PassengerGenerator, max_ticks: int, beta_penalty: float = 2.0, alpha_std_penalty: float = 0.5, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None, config: Optional[dict] = None) -> None runs the simulation.
update(self) -> None, run(self) -> SimulationResult, and export_snapshot(self, filename: str, draw_routes: bool = True, draw_jeeps: bool = True, draw_passengers: bool = True) -> None are the main runtime methods.

Inputs: city query, configuration, routes, and runtime components. All speed values are interpreted as km/h and one simulation tick equals one second.
Outputs: live simulation state plus serialized results, maps, and reports.
Imported modules used: CityGraph, TravelGraph,
DirectDemandSampler, DDMConfig, PassengerGenerator, JeepSystem, Route, Jeep,
LiveVisualizer, StaticVisualizer, Passenger, and threading.
"""

from __future__ import annotations
import math
import uuid
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

from .city_graph import CityGraph
from .travel_graph import TravelGraph
from .direct_demand_sampler import DirectDemandSampler, DDMConfig
from .passenger_generator import PassengerGenerator
from .jeep_system import JeepSystem
from .route import Route
from .jeep import Jeep
from .visualizer import LiveVisualizer, StaticVisualizer
from .passenger import Passenger

class SimulationSetup:
    """Wraps the strict instantiation sequence for the simulation environment."""
    def __init__(self, city_query: str, config: dict, routes: list[Route]) -> None:
        if not routes:
            raise ValueError("[SIMULATION SETUP] Routes must be provided. Fallback generation is deprecated.")
            
        self.id: str = f"SS{uuid.uuid4().hex}"
        self.city_query: str = city_query
        self.config: dict = config
        self.bounds: tuple[float, float, float, float] = tuple(config.get("city_graph", {}).get("bbox", [0.0, 0.0, 0.0, 0.0]))
        self.routes: list[Route] = routes

    def __str__(self) -> str:
        return f"SimulationSetup({self.id}): {self.city_query}, {len(self.routes)} routes provided"

    def build(self, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None) -> 'Simulation':
        print("[Setup] Initializing CityGraph...")
        cg_cfg = self.config.get("city_graph", {})
        cg = CityGraph(
            bbox=tuple(cg_cfg.get("bbox")) if "bbox" in cg_cfg else None,
            name=cg_cfg.get("name", "UrbanNetwork"),
            landmarks=cg_cfg.get("landmarks"),
            pbf_path=cg_cfg.get("pbf_path")
        )

        print("[Setup] Initializing Direct Demand Sampler...")
        sampler = DirectDemandSampler(
            city=cg,
            config=DDMConfig(**self.config.get("ddm", {})),
            only_drivable=True
        )
                    
        print("[Setup] Injecting Transit Routes into Travel Graph...")
        tg = TravelGraph(cg, config=self.config.get("travel_graph", {}), routes=self.routes)
        
        print("[Setup] Deploying Fleet...")
        jeeps = []
        fleet_size = self.config.get("simulation", {}).get("jeep_capacity", 16) # wait, capacity is 16, fleet size from Mohring
        
        # In a real run, you might use FleetAllocator first to distribute jeeps.
        # But if we just spawn a fixed amount per route for now:
        fleet_per_route = self.config.get("F_FLEET_SIZE", 3)
        jeep_speed_kmh = self.config.get("JEEP_SPEED", 10.0)  # km/h; one tick equals one second
        jeep_capacity = self.config.get("simulation", {}).get("jeep_capacity", 16)

        for route in self.routes:
            for _ in range(fleet_per_route):
                start_coord = (route.path[0].start.lon, route.path[0].start.lat)
                jeeps.append(Jeep(route, curr_pos=start_coord, speed=jeep_speed_kmh, max_capacity=jeep_capacity))
                
        jeep_system = JeepSystem(
            jeeps=jeeps, 
            routes=self.routes, 
            weight_tolerance=self.config.get("WEIGHT_TOLERANCE", 50.0),
            equidistant_spawn=self.config.get("EQUIDISTANT_SPAWN", True)
        )
        
        print("[Setup] Initializing Passenger Spawner...")
        passenger_generator = PassengerGenerator(
            tg=tg,
            sampler=sampler,
            rate_per_100=self.config.get("SPAWN_RATE_PER_100", 50.0),
            stdev=self.config.get("SPAWN_STDEV", 10.0),
            speed=self.config.get("PASSENGER_SPEED", 5.0)  # km/h; one tick equals one second
        )
        
        return Simulation(
            city_query=self.city_query,
            bounds=self.bounds,
            jeep_system=jeep_system,
            passenger_generator=passenger_generator,
            max_ticks=self.config.get("simulation", {}).get("num_ticks", 3600),
            beta_penalty=self.config.get("BETA_PENALTY", 2.0),
            alpha_std_penalty=self.config.get("ALPHA_STD_PENALTY", 0.5),
            visualizer=visualizer,
            vis_kwargs=vis_kwargs,
            config=self.config
        )


class SimulationResult:
    """A lightweight target to extract metrics and paths without holding heavy memory."""
    def __init__(
        self, 
        fitness_score: float, 
        metrics: dict[str, Any], 
        recorded_paths: list[tuple[Any, float]], 
        jeep_system: Optional[JeepSystem] = None, 
        sim_id: Optional[str] = None
    ) -> None:
        self.sim_id: str = sim_id or uuid.uuid4().hex[:8]
        self.fitness_score: float = float(fitness_score)
        self.metrics: dict[str, Any] = metrics
        self.recorded_paths: list[tuple[Any, float]] = recorded_paths
        self.jeep_system: Optional[JeepSystem] = jeep_system

    def __str__(self) -> str:
        return f"SimulationResult({self.sim_id}): fitness={self.fitness_score:.2f}, completed={self.metrics.get('completed_count', 0)}"

    def export_map(self, area_query: str, out_dir: str, draw_routes: bool = True) -> None:
        if not self.jeep_system: return
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        filename = out_path / f"map_sim_{self.sim_id}.png"
        
        # Pull bounds from route node bounding box dynamically for the static export
        all_lats = [n.lat for r in self.jeep_system.routes for e in r.path for n in (e.start, e.end)]
        all_lons = [n.lon for r in self.jeep_system.routes for e in r.path for n in (e.start, e.end)]
        dyn_bounds = (min(all_lats), max(all_lats), min(all_lons), max(all_lons)) if all_lats else (0,0,0,0)

        vis = StaticVisualizer(
            bounds=dyn_bounds, 
            title=f"Simulation Output: {self.sim_id}",
            routes=self.jeep_system.routes if draw_routes else [],
            jeeps=[], passengers=[], system_manager=None, mode="dark_nolabels"
        )
        vis.export(str(filename), scale_up=2)

    def export_report(self, out_dir: str) -> None:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        filename = out_path / f"report_sim_{self.sim_id}.txt"
        payload = {"sim_id": self.sim_id, "fitness_score": self.fitness_score, "metrics": self.metrics, "routes_count": len(self.jeep_system.routes) if self.jeep_system else 0, "jeeps_count": len(self.jeep_system.jeeps) if self.jeep_system else 0}
        with open(filename, "w") as f:
            f.write(f"SIMULATION ANNOTATION REPORT\n" + "=" * 40 + "\n")
            f.write(f"Simulation ID : {self.sim_id}\nTimestamp     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nFitness Score : {self.fitness_score:.4f}\n\n--- METRICS ---\n")
            for k, v in self.metrics.items(): f.write(f"{k:<20}: {v:.4f}\n" if isinstance(v, float) else f"{k:<20}: {v}\n")
            f.write(f"\n--- TOPOLOGY OVERVIEW ---\nTotal Routes : {payload['routes_count']}\nTotal Jeeps  : {payload['jeeps_count']}\n\n\n--- DATA PAYLOAD (DO NOT EDIT) ---\n")
            f.write(json.dumps(payload))

    @classmethod
    def from_file(cls, filepath: str) -> 'SimulationResult':
        with open(filepath, "r") as f: content = f.read()
        try: data = json.loads(content.split("--- DATA PAYLOAD (DO NOT EDIT) ---")[1].strip())
        except: raise ValueError("Failed to parse data payload.")
        return cls(sim_id=data["sim_id"], fitness_score=data["fitness_score"], metrics=data["metrics"], recorded_paths=[], jeep_system=None)


class Simulation:
    def __init__(
        self, 
        city_query: str, 
        bounds: tuple[float, float, float, float], 
        jeep_system: JeepSystem, 
        passenger_generator: PassengerGenerator, 
        max_ticks: int, 
        beta_penalty: float = 2.0, 
        alpha_std_penalty: float = 0.5, 
        visualizer: bool = False, 
        vis_kwargs: Optional[dict[str, Any]] = None, 
        config: Optional[dict] = None
    ) -> None:
        self.id: str = f"S{uuid.uuid4().hex}"
        self.city_query: str = city_query
        self.bounds: tuple[float, float, float, float] = bounds 
        self.jeep_system: JeepSystem = jeep_system
        self.passenger_generator: PassengerGenerator = passenger_generator
        self.max_ticks: int = int(max_ticks)
        self.beta_penalty: float = float(beta_penalty)
        self.alpha_std_penalty: float = float(alpha_std_penalty)
        self.visualizer_mode: bool = visualizer
        self.vis_kwargs: dict[str, Any] = vis_kwargs or {}
        self.config: dict = config or {}
        
        self.current_tick: int = 0
        self.is_complete: bool = False
        self.speed_multiplier: int = 1 
        
        # Synchronize passenger memory reference
        self.jeep_system.passengers = self.passenger_generator.passengers

    def __str__(self) -> str:
        return f"Simulation({self.id}): tick={self.current_tick}/{self.max_ticks}, complete={self.is_complete}"

    def update(self) -> None:
        """Advances the simulation state by the speed multiplier."""
        for _ in range(self.speed_multiplier):
            if self.current_tick >= self.max_ticks:
                self.is_complete = True
                break
                
            self.passenger_generator.update()
            self.jeep_system.update()
            self.current_tick += 1

    def run(self) -> SimulationResult:
        """Executes the main loop based on visualizer settings."""
        if self.visualizer_mode:
            self._run_with_visualizer()
        else:
            self._run_headless()
        return self._calculate_results()

    def _run_headless(self) -> None:
        """Runs the simulation as fast as the CPU allows."""
        while not self.is_complete: 
            self.update()

    def _run_with_visualizer(self) -> None:
        """Hands off the simulation state to the GUI."""
        vis = LiveVisualizer(
            bounds=self.bounds, 
            routes=self.jeep_system.routes,
            jeeps=self.jeep_system.jeeps,
            passengers=self.passenger_generator.passengers, 
            system_manager=self,
            **self.vis_kwargs
        )
        print(f"[*] Launching Visual Simulation for {self.max_ticks} ticks...")
        vis.display()
        self.is_complete = True 

    def _calculate_results(self) -> SimulationResult:
        """Computes fitness metrics for the Genetic Algorithm."""
        completed = self.passenger_generator.archived_passengers
        incomplete = self.passenger_generator.passengers
        
        completed_times = [p.despawn_tick - p.spawn_tick for p in completed if p.despawn_tick is not None]
        incomplete_penalties = [self.current_tick - p.spawn_tick + (self.beta_penalty * p.get_remaining_time()) for p in incomplete]
        
        n_completed = len(completed_times)
        if n_completed > 0:
            mean_commute = sum(completed_times) / n_completed
            std_commute = math.sqrt(sum((t - mean_commute) ** 2 for t in completed_times) / n_completed)
        else:
            mean_commute = self.max_ticks * 2 
            std_commute = 0.0

        sum_completed = sum(completed_times)
        sum_incomplete = sum(incomplete_penalties)
        total_fitness = sum_completed + sum_incomplete + (self.alpha_std_penalty * std_commute)
        
        all_recorded_paths = [(p.journey, p.total_path_cost) for p in (completed + incomplete)]

        return SimulationResult(
            fitness_score=total_fitness,
            metrics={
                "completed_count": n_completed, 
                "incomplete_count": len(incomplete), 
                "mean_commute_time": mean_commute, 
                "std_commute_time": std_commute, 
                "sum_completed_time": sum_completed, 
                "sum_penalty_time": sum_incomplete, 
                "ticks_simulated": self.current_tick
            },
            recorded_paths=all_recorded_paths,
            jeep_system=self.jeep_system
        )

    def export_snapshot(self, filename: str, draw_routes: bool = True, draw_jeeps: bool = True, draw_passengers: bool = True) -> None:
        """Public API to take an async snapshot of the current state with specific layers."""
        # Safely extract immutable coordinates so the main thread can keep running
        pass_coords = [(p.curr_lon, p.curr_lat) for p in self.passenger_generator.passengers] if draw_passengers else []
        jeep_data = [(j.route, j.curr_pos, j.heading, getattr(j, 'curr_passenger_count', 0)) for j in self.jeep_system.jeeps] if draw_jeeps else []
        routes = self.jeep_system.routes if draw_routes else []
        
        # Fire and forget the rendering thread
        thread = threading.Thread(
            target=self._async_render_worker, 
            args=(str(filename), pass_coords, jeep_data, routes), 
            daemon=True
        )
        thread.start()

    def _async_render_worker(self, filename: str, pass_coords: list, jeep_data: list, routes: list) -> None:
        """Background worker that builds the image without blocking the CPU."""
        dummy_passengers = [Passenger(start_pos=(lon, lat), journey=[routes[0].path[0]], speed=0) for lon, lat in pass_coords] if routes and routes[0].path else []
        
        dummy_jeeps = []
        for route, pos, heading, count in jeep_data:
            dj = Jeep(route=route, curr_pos=pos, speed=0)
            dj.heading = heading
            dj.curr_passenger_count = count
            dummy_jeeps.append(dj)

        vis = StaticVisualizer(
            bounds=self.bounds,
            title=Path(filename).stem,
            routes=routes,
            jeeps=dummy_jeeps,
            passengers=dummy_passengers,
            system_manager=None,
            mode="dark_nolabels"
        )
        vis.export(filename, scale_up=1)
        print(f"[Async Export] Saved: {filename}")
