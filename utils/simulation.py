from __future__ import annotations
import math
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from PIL import Image, ImageDraw, ImageFont

from .city_graph import CityGraph
from .travel_graph import TravelGraph
from .direct_demand_sampler import DirectDemandSampler, DDMConfig
from .passenger_generator import PassengerGenerator
from .jeep_system import JeepSystem
from .route import Route
from .jeep import Jeep
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

    def build(self) -> 'Simulation':
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
            verbose=False
        )
                    
        print("[Setup] Injecting Transit Routes into Travel Graph...")
        tg = TravelGraph(cg, config=self.config.get("travel_graph", {}), routes=self.routes)
        
        print("[Setup] Deploying Fleet...")
        sim_cfg = self.config.get("simulation", {})
        jeeps = []
        total_jeeps = sim_cfg.get("total_allocatable_jeeps", 25)
        jeep_speed_kmh = sim_cfg.get("jeep_speed_kmh", 40.0) 
        jeep_capacity = sim_cfg.get("jeep_capacity", 16)
        weight_tol = sim_cfg.get("weight_tolerance", 50.0)
        seconds_per_tick = sim_cfg.get("seconds_per_tick", 1)

        jeeps_per_route = max(1, total_jeeps // len(self.routes))

        for route in self.routes:
            for _ in range(jeeps_per_route):
                start_coord = (route.path[0].start.lon, route.path[0].start.lat)
                jeeps.append(Jeep(route, curr_pos=start_coord, speed=jeep_speed_kmh, max_capacity=jeep_capacity, seconds_per_tick=seconds_per_tick))
                
        jeep_system = JeepSystem(
            jeeps=jeeps, 
            routes=self.routes, 
            weight_tolerance=weight_tol,
            equidistant_spawn=True
        )
        
        print("[Setup] Initializing Passenger Spawner...")
        passenger_generator = PassengerGenerator(
            tg=tg,
            sampler=sampler,
            rate_per_hour=sim_cfg.get("spawn_rate_per_hour", 40.0),
            stdev=sim_cfg.get("spawn_stdev", 5.0),
            speed=sim_cfg.get("passenger_speed_kmh", 5.0),
            seconds_per_tick=seconds_per_tick
        )
        
        return Simulation(
            city_query=self.city_query,
            bounds=self.bounds,
            jeep_system=jeep_system,
            passenger_generator=passenger_generator,
            max_ticks=sim_cfg.get("num_ticks", 3600),
            beta_penalty=self.config.get("BETA_PENALTY", 2.0),
            alpha_std_penalty=self.config.get("ALPHA_STD_PENALTY", 0.5),
            config=self.config
        )


class SimulationResult:
    """A lightweight target to extract metrics and paths without holding heavy memory."""
    def __init__(
        self, 
        fitness_score: Optional[float] = None,
        metrics: Optional[dict[str, Any]] = None,
        recorded_paths: Optional[list[tuple[Any, float]]] = None,
        jeep_system: Optional[JeepSystem] = None, 
        sim_id: Optional[str] = None,
        surrogate_cost: Optional[float] = None,
        score_kind: str = "fitness"
    ) -> None:
        if score_kind not in {"fitness", "surrogate"}:
            raise ValueError("[SIMULATION RESULT] score_kind must be 'fitness' or 'surrogate'.")
        if score_kind == "fitness" and fitness_score is None:
            raise ValueError("[SIMULATION RESULT] fitness_score is required for fitness results.")
        if score_kind == "surrogate" and surrogate_cost is None:
            raise ValueError("[SIMULATION RESULT] surrogate_cost is required for surrogate results.")

        self.sim_id: str = sim_id or uuid.uuid4().hex[:8]
        self.score_kind: str = score_kind
        self.fitness_score: Optional[float] = float(fitness_score) if fitness_score is not None else None
        self.surrogate_cost: Optional[float] = float(surrogate_cost) if surrogate_cost is not None else None
        self.metrics: dict[str, Any] = metrics or {}
        self.recorded_paths: list[tuple[Any, float]] = recorded_paths or []
        self.jeep_system: Optional[JeepSystem] = jeep_system

    @property
    def score(self) -> float:
        if self.score_kind == "fitness":
            if self.fitness_score is None:
                raise ValueError("[SIMULATION RESULT] fitness_score is unavailable.")
            return self.fitness_score
        if self.surrogate_cost is None:
            raise ValueError("[SIMULATION RESULT] surrogate_cost is unavailable.")
        return self.surrogate_cost

    def __str__(self) -> str:
        label = "fitness" if self.score_kind == "fitness" else "surrogate_cost"
        return f"SimulationResult({self.sim_id}): {label}={self.score:.2f}, completed={self.metrics.get('completed_count', 0)}"

    def export_report(self, out_dir: str) -> None:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        filename = out_path / f"report_sim_{self.sim_id}.txt"
        payload = {
            "sim_id": self.sim_id,
            "score_kind": self.score_kind,
            "fitness_score": self.fitness_score,
            "surrogate_cost": self.surrogate_cost,
            "metrics": self.metrics,
            "routes_count": len(self.jeep_system.routes) if self.jeep_system else 0,
            "jeeps_count": len(self.jeep_system.jeeps) if self.jeep_system else 0,
        }
        with open(filename, "w") as f:
            f.write(f"SIMULATION ANNOTATION REPORT\n" + "=" * 40 + "\n")
            score_label = "Fitness Score" if self.score_kind == "fitness" else "Surrogate Cost"
            f.write(f"Simulation ID : {self.sim_id}\nTimestamp     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{score_label} : {self.score:.4f}\n\n--- METRICS ---\n")
            for k, v in self.metrics.items(): f.write(f"{k:<20}: {v:.4f}\n" if isinstance(v, float) else f"{k:<20}: {v}\n")
            f.write(f"\n--- TOPOLOGY OVERVIEW ---\nTotal Routes : {payload['routes_count']}\nTotal Jeeps  : {payload['jeeps_count']}\n\n\n--- DATA PAYLOAD (DO NOT EDIT) ---\n")
            f.write(json.dumps(payload))

    @classmethod
    def from_file(cls, filepath: str) -> 'SimulationResult':
        with open(filepath, "r") as f: content = f.read()
        try: data = json.loads(content.split("--- DATA PAYLOAD (DO NOT EDIT) ---")[1].strip())
        except: raise ValueError("Failed to parse data payload.")
        score_kind = data.get("score_kind", "fitness")
        return cls(
            sim_id=data["sim_id"],
            fitness_score=data.get("fitness_score"),
            surrogate_cost=data.get("surrogate_cost"),
            metrics=data.get("metrics", {}),
            recorded_paths=[],
            jeep_system=None,
            score_kind=score_kind,
        )


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
        self.config: dict = config or {}
        
        self.current_tick: int = 0
        self.is_complete: bool = False
        self.speed_multiplier: int = 1 

    def __str__(self) -> str:
        return f"Simulation({self.id}): tick={self.current_tick}/{self.max_ticks}, complete={self.is_complete}"

    def update(self) -> None:
        """Advances the simulation state by the speed multiplier."""
        for _ in range(self.speed_multiplier):
            if self.current_tick >= self.max_ticks:
                self.is_complete = True
                break
                
            self.passenger_generator.update()
            
            # Use the pre-populated new_passengers_this_tick list instead of
            # slicing the full passengers list by a stale counter every tick.
            for p in self.passenger_generator.new_passengers_this_tick:
                self.jeep_system.add_passenger(p)

            self.jeep_system.update()
            self.current_tick += 1

    def run(self) -> SimulationResult:
        """Executes the headless simulation loop until max_ticks is reached."""
        from tqdm import tqdm
        disable_tqdm = self.config.get("disable_tqdm", False)
        with tqdm(total=self.max_ticks, desc="Microscopic Simulation Ticks", leave=False, disable=disable_tqdm) as pbar:
            while not self.is_complete:
                self.update()
                pbar.update(1)
        return self.evaluate_fitness()


    def run_until_drained(self, safety_cap: int = 100_000) -> SimulationResult:
        """Runs until every spawned passenger has completed their journey.

        Unlike run(), this ignores max_ticks and instead terminates as soon as
        passenger_generator.passengers is empty (all active passengers reached DONE).
        The PassengerGenerator will stop spawning new passengers after its internal
        schedule is exhausted (~100-tick windows), so the loop naturally converges.

        Args:
            safety_cap: Hard upper-bound tick limit to prevent truly infinite loops
                        in degenerate cases (e.g. passengers waiting forever with no
                        jeep that can reach them). Defaults to 100,000 ticks.
        """
        tick = 0
        while tick < safety_cap:
            self.passenger_generator.update()
            for p in self.passenger_generator.new_passengers_this_tick:
                self.jeep_system.add_passenger(p)
            self.jeep_system.update()
            self.current_tick += 1
            tick += 1

            # Terminate once no more passengers are actively in the system.
            # archived_passengers are DONE; passengers list holds still-active ones.
            if len(self.passenger_generator.passengers) == 0:
                break

        self.is_complete = True
        return self.evaluate_fitness()

    def evaluate_fitness(self) -> SimulationResult:
        """Computes the post-simulation fitness score and metric breakdown."""
        return self._calculate_results()


    def _calculate_results(self) -> SimulationResult:
        """Computes the post-simulation fitness metrics for the route system."""
        completed = self.passenger_generator.archived_passengers
        incomplete = self.passenger_generator.passengers
        
        completed_times = [p.despawn_tick - p.spawn_tick for p in completed if p.despawn_tick is not None]
        incomplete_elapsed = [self.passenger_generator.simulated_time - p.spawn_tick for p in incomplete]
        incomplete_remaining = [p.get_remaining_time() for p in incomplete]
        incomplete_penalties = [elapsed + (self.beta_penalty * remaining) for elapsed, remaining in zip(incomplete_elapsed, incomplete_remaining)]
        
        n_completed = len(completed_times)
        if n_completed > 0:
            mean_commute = sum(completed_times) / n_completed
            std_commute = math.sqrt(sum((t - mean_commute) ** 2 for t in completed_times) / n_completed)
        else:
            mean_commute = self.max_ticks * 2 
            std_commute = 0.0

        sum_completed = sum(completed_times)
        sum_incomplete_elapsed = sum(incomplete_elapsed)
        sum_incomplete_remaining = sum(incomplete_remaining)
        sum_incomplete = sum(incomplete_penalties)
        equity_penalty = self.alpha_std_penalty * std_commute
        total_fitness = sum_completed + sum_incomplete + equity_penalty
        
        all_recorded_paths = [(p.journey, p.total_path_cost) for p in (completed + incomplete)]

        return SimulationResult(
            fitness_score=total_fitness,
            metrics={
                "completed_count": n_completed, 
                "incomplete_count": len(incomplete), 
                "mean_commute_time": mean_commute, 
                "std_commute_time": std_commute, 
                "sum_completed_time": sum_completed, 
                "sum_incomplete_elapsed_time": sum_incomplete_elapsed,
                "sum_incomplete_remaining_time": sum_incomplete_remaining,
                "sum_penalty_time": sum_incomplete, 
                "equity_penalty": equity_penalty,
                "ticks_simulated": self.current_tick
            },
            recorded_paths=all_recorded_paths,
            jeep_system=self.jeep_system
        )

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, draw_jeeps: bool = True, draw_passengers: bool = True) -> Image.Image:
        """Draws the dynamic simulation state onto the provided base map."""
        if image.width != image.height:
            raise ValueError("[SIMULATION] Visualization requires a square image.")
            
        img = image.copy()
        
        if draw_jeeps:
            img = self.jeep_system.draw(context, img, radius=10)
            
        if draw_passengers:
            for p in self.jeep_system.active_passengers:
                img = p.draw(context, img, size=6)
                
        return img

    def draw_dashboard(self, image: Image.Image) -> Image.Image:
        """Overlays core operational metrics onto the rendering frame."""
        img = image.copy()
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", int(img.height * 0.025))
        except IOError:
            font = ImageFont.load_default()
            
        pad = int(img.height * 0.02)
        active_passengers = len(self.passenger_generator.passengers)
        completed_passengers = len(self.passenger_generator.archived_passengers)
        
        stats_text = (
            f"TICK: {self.current_tick} / {self.max_ticks}\n"
            f"JEEPS: {len(self.jeep_system.jeeps)}\n"
            f"ACTIVE PAX: {active_passengers}\n"
            f"DONE PAX: {completed_passengers}"
        )
        
        for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
            draw.multiline_text((pad + dx, pad + dy), stats_text, fill="black", font=font)
            
        draw.multiline_text((pad, pad), stats_text, fill="white", font=font)
        return img
    
class SimulationEvaluator:
    """
    A persistent factory for rapidly evaluating multiple route configurations 
    against a static city and demand model. Designed for GA loops.
    """
    def __init__(self, config: dict, city_graph: CityGraph, travel_graph: Optional[TravelGraph], demand_sampler: DirectDemandSampler) -> None:
        self.config = config
        self.city_graph = city_graph
        self.travel_graph = travel_graph
        self.demand_sampler = demand_sampler
        self.travel_graph_config = travel_graph.config.copy() if travel_graph is not None else config.get("travel_graph", {}).copy()
        
        self.sim_cfg = config.get("simulation", {})
        self.total_jeeps = self.sim_cfg.get("total_allocatable_jeeps", 25)
        self.jeep_speed = self.sim_cfg.get("jeep_speed_kmh", 40.0)
        self.jeep_capacity = self.sim_cfg.get("jeep_capacity", 16)
        self.weight_tol = self.sim_cfg.get("weight_tolerance", 50.0)
        
        self.spawn_rate = self.sim_cfg.get("spawn_rate_per_hour", 40.0)
        self.spawn_stdev = self.sim_cfg.get("spawn_stdev", 5.0)
        self.pax_speed = self.sim_cfg.get("passenger_speed_kmh", 5.0)
        
        self.max_ticks = self.sim_cfg.get("num_ticks", 3600)
        self.beta_penalty = float(config.get("BETA_PENALTY", 2.0))
        self.alpha_std_penalty = float(config.get("ALPHA_STD_PENALTY", 0.5))

    def evaluate(self, routes: list['Route'], verbose: bool = False) -> SimulationResult:
        jeeps = []
        jeeps_per_route = max(1, self.total_jeeps // len(routes)) if routes else 0

        tg = TravelGraph(
            cg=self.city_graph,
            config=self.travel_graph_config.copy(),
            routes=routes
        )
        
        seconds_per_tick = self.sim_cfg.get("seconds_per_tick", 1)

        for route in routes:
            for _ in range(jeeps_per_route):
                start_coord = (route.path[0].start.lon, route.path[0].start.lat)
                jeeps.append(Jeep(route, curr_pos=start_coord, speed=self.jeep_speed, max_capacity=self.jeep_capacity, seconds_per_tick=seconds_per_tick))
                
        jeep_system = JeepSystem(
            jeeps=jeeps, 
            routes=routes, 
            weight_tolerance=self.weight_tol,
            equidistant_spawn=True
        )
        
        passenger_generator = PassengerGenerator(
            tg=tg,
            sampler=self.demand_sampler,
            rate_per_hour=self.spawn_rate,
            stdev=self.spawn_stdev,
            speed=self.pax_speed,
            seconds_per_tick=seconds_per_tick
        )
        
        sim = Simulation(
            city_query=self.config.get("city_graph", {}).get("name", "City"),
            bounds=self.city_graph.get_bounds(),
            jeep_system=jeep_system,
            passenger_generator=passenger_generator,
            max_ticks=self.max_ticks,
            beta_penalty=self.beta_penalty,
            alpha_std_penalty=self.alpha_std_penalty,
            config=self.config
        )
        
        if verbose:
            print(f"[EVALUATOR] Executing headless simulation for {self.max_ticks} ticks...")
            
        result = sim.run()
        
        # Detach complex graph and system object references prior to returning.
        # This prevents Python ProcessPoolExecutor from attempting to pickle 
        # KD-trees and recursive object nets, ensuring pure scalar extraction.
        result.jeep_system = None
        
        return result
    
class StaticSurrogateEvaluator:
    """
    A persistent factory for rapidly evaluating multiple route configurations 
    against a static OD demand matrix. Designed to replace full agent simulations 
    during the metaheuristic search phase.
    
    The transfer penalty is explicitly overridden to 2.5 times the base transfer weight. 
    This integrates empirical behavioral routing penalties directly into the evaluation layer (Iseki & Taylor, 2009). 
    The evaluator returns a standard SimulationResult object to maintain existing module API compatibility.
    """
    def __init__(self, config: dict, city_graph: CityGraph, demand_sampler: DirectDemandSampler, num_samples: int = 500) -> None:
        self.config = config
        self.city_graph = city_graph
        self.demand_sampler = demand_sampler
        self.num_samples = num_samples
        
        self.od_pairs = []
        for _ in range(self.num_samples):
            start = self.demand_sampler.get_point(only_drivable=False)
            end = self.demand_sampler.get_point(only_drivable=False)
            if start and end and start != end:
                self.od_pairs.append((start, end))

    def evaluate(self, routes: list['Route'], verbose: bool = False) -> SimulationResult:
        tg_cfg = self.config.get("travel_graph", {}).copy()
        base_transfer = tg_cfg.get("transfer_wt", 5.0)
        tg_cfg["transfer_wt"] = base_transfer * 2.5 
        
        tg = TravelGraph(
            cg=self.city_graph, 
            config=tg_cfg, 
            routes=routes
        )
        
        total_weight = 0.0
        completed = 0
        unreachable_penalty = 100000.0
        recorded_paths = []
        
        for start, end in self.od_pairs:
            path = tg.findShortestJourney(start, end)
            if path:
                weight = sum(e.weight for e in path)
                if weight > 0 and weight != float("inf"):
                    total_weight += weight
                    completed += 1
                    recorded_paths.append((path, weight))
                else:
                    total_weight += unreachable_penalty
            else:
                total_weight += unreachable_penalty

        fleet_operational_cost = sum(sum(e.getLength() for e in r.path) for r in routes)

        return SimulationResult(
            surrogate_cost=total_weight,
            metrics={
                "passenger_routing_cost": total_weight,
                "fleet_operational_cost": fleet_operational_cost,
                "surrogate_samples": len(self.od_pairs),
                "completed_routes": completed
            },
            recorded_paths=recorded_paths,
            jeep_system=None,
            sim_id=f"SURR{uuid.uuid4().hex[:8]}",
            score_kind="surrogate"
        )
