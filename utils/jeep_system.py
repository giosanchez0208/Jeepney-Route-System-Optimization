from __future__ import annotations
import math
from uuid import uuid4
from typing import Optional, TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from .direct_demand_sampler import DirectDemandSampler
    from .travel_graph import TravelGraph

from .jeep import Jeep
from .passenger import Passenger
from .route import Route

class FleetAllocator:
    _edge_length_cache: dict[str, float] = {}
    _route_length_cache: dict[str, float] = {}

    @classmethod
    def allocate_by_mohring(
        cls,
        total_fleet: int, 
        routes: list[Route], 
        sampler: 'DirectDemandSampler', 
        tg: 'TravelGraph', 
        mohring_sample_size: int = 2000
    ) -> dict[Route, int]:
        if not routes:
            raise ValueError("[FLEET ALLOCATOR] Routes list cannot be empty.")
        if total_fleet <= 0:
            raise ValueError("[FLEET ALLOCATOR] Total fleet must be positive.")

        # Estimate route demand using DirectDemandSampler
        route_demand: dict[Route, float] = {r: 0.0 for r in routes}
        
        for _ in range(mohring_sample_size):
            origin = sampler.get_point()
            dest = sampler.get_point()
            journey = tg.findShortestJourney(origin, dest)
            if journey:
                # Count usage of RI edges for routes
                for edge in journey:
                    if edge.id.startswith("RI_R"):
                        try:
                            r_idx = int(edge.id.split("_")[1][1:])
                            route_demand[routes[r_idx]] += 1.0
                        except (IndexError, ValueError):
                            continue

        # Mohring effect: allocate fleet proportional to the square root of demand
        route_tau: dict[Route, float] = {r: math.sqrt(max(1.0, demand)) for r, demand in route_demand.items()}
            
        total_sqrt_tau = sum(route_tau.values())
        if total_sqrt_tau == 0: 
            total_sqrt_tau = 1.0
        
        allocation: dict[Route, int] = {}
        remaining: int = total_fleet
        for r in routes[:-1]:
            count = max(1, int(round(total_fleet * (route_tau[r] / total_sqrt_tau))))
            allocation[r] = count
            remaining -= count
            
        allocation[routes[-1]] = max(1, remaining)
        return allocation

    @classmethod
    def evaluate_allocation(cls, allocation: dict[Route, int], sampler: 'DirectDemandSampler') -> dict[Route, dict[str, float]]:
        total_fleet = sum(allocation.values())
        if total_fleet == 0: 
            return {}
            
        report: dict[Route, dict[str, float]] = {}
        for route, count in allocation.items():
            if route.id not in cls._route_length_cache:
                length_sum = 0.0
                for e in route.path:
                    if e.id not in cls._edge_length_cache:
                        cls._edge_length_cache[e.id] = e.getLength()
                    length_sum += cls._edge_length_cache[e.id]
                cls._route_length_cache[route.id] = length_sum
            
            length_sum = cls._route_length_cache[route.id]
            
            # Simple placeholder demand for report since we don't recalculate tau here
            demand = count * count  
            
            load_factor = demand / count if count > 0 else float('inf')
            headway = length_sum / count if count > 0 else float('inf')
            
            report[route] = {
                "jeeps": float(count),
                "length": length_sum,
                "load_factor": load_factor,
                "headway": headway,
            }
        return report

class JeepSystem:
    def __init__(
        self, 
        jeeps: list[Jeep], 
        routes: list[Route], 
        weight_tolerance: float = 50.0, 
        equidistant_spawn: bool = True
    ) -> None:
        if not jeeps:
            raise ValueError("[JEEP SYSTEM] jeeps list cannot be empty.")
        if not routes:
            raise ValueError("[JEEP SYSTEM] routes list cannot be empty.")
        if weight_tolerance < 0:
            raise ValueError("[JEEP SYSTEM] weight_tolerance cannot be negative.")

        self.id: str = f"JS{uuid4().hex}"
        self.jeeps: list[Jeep] = jeeps
        self.routes: list[Route] = routes
        self.passengers: list[Passenger] = []
        self.weight_tolerance: float = float(weight_tolerance)

        if equidistant_spawn:
            self._space_jeeps_equidistantly()

    def __str__(self) -> str:
        return f"JeepSystem({self.id}): {len(self.jeeps)} jeeps on {len(self.routes)} routes, {len(self.passengers)} active passengers"

    def _space_jeeps_equidistantly(self) -> None:
        route_jeeps: dict[Route, list[Jeep]] = {r: [] for r in self.routes}
        for j in self.jeeps:
            if j.route in route_jeeps:
                route_jeeps[j.route].append(j)
                
        for route, assigned_jeeps in route_jeeps.items():
            if not assigned_jeeps:
                continue
                
            total_length = sum(e.getLength() for e in route.path)
            if total_length <= 0:
                continue
                
            spacing = total_length / len(assigned_jeeps)
            
            for i, jeep in enumerate(assigned_jeeps):
                target_dist = i * spacing
                accumulated = 0.0
                
                for idx, edge in enumerate(route.path):
                    edge_len = edge.getLength()
                    
                    if accumulated + edge_len >= target_dist - 1e-5:
                        jeep._edge_idx = idx
                        jeep._edge_progress = target_dist - accumulated
                        
                        if edge_len > 0:
                            ratio = jeep._edge_progress / edge_len
                            lat = edge.start.lat + ratio * (edge.end.lat - edge.start.lat)
                            lon = edge.start.lon + ratio * (edge.end.lon - edge.start.lon)
                            jeep.curr_pos = (lon, lat)
                        else:
                            jeep.curr_pos = (edge.start.lon, edge.start.lat)
                            
                        jeep._update_heading()
                        break
                    accumulated += edge_len

    def add_passenger(self, passenger: Passenger) -> None:
        if not isinstance(passenger, Passenger):
            raise TypeError("[JEEP SYSTEM] Must add a Passenger object.")
        self.passengers.append(passenger)

    def update(self) -> None:
        # Spatial queues mapping coordinate tuples to active passengers
        waiting_queue: dict[tuple[float, float], list[Passenger]] = {}
        jeep_riders: dict[Jeep, list[Passenger]] = {}

        # 1. Update all passengers and sort them into immediate lookup maps
        for p in self.passengers:
            p.update()
            if p.state == "WAITING":
                coord = (p.curr_lat, p.curr_lon)
                if coord not in waiting_queue:
                    waiting_queue[coord] = []
                waiting_queue[coord].append(p)
            elif p.state == "RIDING" and p.current_jeep:
                if p.current_jeep not in jeep_riders:
                    jeep_riders[p.current_jeep] = []
                jeep_riders[p.current_jeep].append(p)

        # 2. Update jeeps and handle boarding/alighting via direct queue lookups
        for jeep in self.jeeps:
            jeep.update()
            passed_nodes_data = jeep.nodes_passed_this_frame()
            
            if not passed_nodes_data:
                continue
                
            for node, route in passed_nodes_data:
                try:
                    route_idx = self.routes.index(route)
                except ValueError:
                    continue
                
                # Check for alighting passengers in this specific jeep
                riders = jeep_riders.get(jeep, [])
                if riders:
                    still_riding = []
                    for p in riders:
                        target_node = p.get_target_alight_node()
                        if target_node and target_node.lat == node.lat and target_node.lon == node.lon:
                            p.state = "WALKING"
                            p.current_jeep = None
                            p.curr_lat = node.lat
                            p.curr_lon = node.lon
                            p.complete_ride()
                            jeep.modify_passenger(-1)
                        else:
                            still_riding.append(p)
                    jeep_riders[jeep] = still_riding
                            
                # Check for boarding passengers at this exact node coordinate
                coord = (node.lat, node.lon)
                waiting_at_node = waiting_queue.get(coord, [])
                
                if waiting_at_node and jeep.curr_passenger_count < jeep.passenger_max:
                    still_waiting = []
                    for p in waiting_at_node:
                        if jeep.curr_passenger_count >= jeep.passenger_max:
                            still_waiting.append(p)
                            continue
                            
                        target_route_idx = p.get_target_route_idx()
                        boarded = False
                        
                        if target_route_idx == route_idx:
                            boarded = True
                        else:
                            target_node = p.get_target_alight_node()
                            if target_node:
                                alt_weight = jeep.get_weight_if(node, target_node)
                                if alt_weight is not None:
                                    planned_weight = p.get_planned_ride_weight()
                                    if alt_weight <= planned_weight + self.weight_tolerance:
                                        boarded = True
                                        
                        if boarded:
                            p.state = "RIDING"
                            p.current_jeep = jeep
                            p.wait_ticks = 0
                            jeep.modify_passenger(1)
                            # Append to riders in case they alight at another node passed THIS same frame
                            if jeep not in jeep_riders:
                                jeep_riders[jeep] = []
                            jeep_riders[jeep].append(p)
                        else:
                            still_waiting.append(p)
                            
                    if still_waiting:
                        waiting_queue[coord] = still_waiting
                    else:
                        del waiting_queue[coord]

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, radius: int = 12) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[JEEP SYSTEM] Visualization requires a square image.")
        
        for jeep in self.jeeps:
            image = jeep.draw(context, image, radius)
            
        return image