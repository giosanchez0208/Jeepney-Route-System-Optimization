from __future__ import annotations
import collections
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
        """
        Post-Pheromone Allocation:
        Apply the Mohring Effect via square root scaling. Pheromones represent empirical demand. 
        Linear allocation starves low-demand transfer routes and destroys network cooperation. 
        Square root scaling flattens the distribution curve. It subsidizes long routes while 
        adequately serving dense corridors.

        Formula:
            F_i = F_total * (sqrt(tau_i) / sum(sqrt(tau)))

        Academic Basis: 
            Mohring, H. (1972), Optimization and Scale Economies in Urban Bus Transportation. 
            The American Economic Review, 62(4), 591-604. 
            This mathematical principle balances fleet operating costs against aggregate passenger wait times.
        """
        if not routes:
            raise ValueError("[FLEET ALLOCATOR] Routes list cannot be empty.")
        if total_fleet <= 0:
            raise ValueError("[FLEET ALLOCATOR] Total fleet must be positive.")

        route_demand: dict[Route, float] = {r: 0.0 for r in routes}
        
        for _ in range(mohring_sample_size):
            origin = sampler.get_point()
            dest = sampler.get_point()
            journey = tg.findShortestJourney(origin, dest)
            if journey:
                for edge in journey:
                    if edge.id.startswith("RI_R"):
                        try:
                            r_idx = int(edge.id.split("_")[1][1:])
                            route_demand[routes[r_idx]] += 1.0
                        except (IndexError, ValueError):
                            continue

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
        """
        Evaluates the efficiency and headway of the allocated vehicle distribution.

        Metrics Calculated:
        1. Route Load Factor (Demand per Jeep):
           Measures operator efficiency and passenger crowding. It divides the total pheromone
           accumulation (demand) on a route by the number of assigned jeeps:
               Load = sum(tau_route) / F_route
           A high value indicates overcrowding and missed revenue. A low value indicates empty
           vehicles and operator financial loss.

        2. Estimated Headway (Distance per Jeep):
           Primary metric for passenger wait times. Since baseline speed is constant, route
           distance is directly proportional to cycle time:
               Headway proportional to sum(L_route) / F_route
           Quantifies the spatial gap between jeeps. High headway degrades connectivity.

        Demand-Service Parity (Equity Ratio) Note:
           Theoretical Formula: 
               Parity = (F_route / F_total) / (tau_route / tau_total)
           A ratio below 1.0 means the route is underserved relative to its demand, which the 
           Mohring effect naturally causes to subsidize longer, lower-demand routes.
        """
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
        
        # Maintain total list for metrics, active set for execution loops.
        self.passengers: list[Passenger] = []
        self.active_passengers: set[Passenger] = set()
        
        self.weight_tolerance: float = float(weight_tolerance)
        
        self.waiting_passengers: dict[tuple[float, float], set[Passenger]] = collections.defaultdict(set)
        self._waiting_coord_by_passenger: dict[Passenger, tuple[float, float]] = {}
        self._route_indices: dict[Route, int] = {route: idx for idx, route in enumerate(self.routes)}

        if equidistant_spawn:
            self._space_jeeps_equidistantly()

    def __str__(self) -> str:
        return f"JeepSystem({self.id}): {len(self.jeeps)} jeeps on {len(self.routes)} routes, {len(self.active_passengers)} active passengers"

    def _space_jeeps_equidistantly(self) -> None:
        route_jeeps: dict[Route, list[Jeep]] = collections.defaultdict(list)
        for j in self.jeeps:
            route_jeeps[j.route].append(j)
                
        for route, assigned_jeeps in route_jeeps.items():
            if not assigned_jeeps:
                continue
                
            total_length = sum(e._length for e in route.path)
            if total_length <= 0:
                continue
                
            spacing = total_length / len(assigned_jeeps)
            
            for i, jeep in enumerate(assigned_jeeps):
                target_dist = i * spacing
                accumulated = 0.0
                
                for idx, edge in enumerate(route.path):
                    edge_len = edge._length
                    
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
        self.active_passengers.add(passenger)
        
        if passenger.state == Passenger.WAITING:
            self._register_waiting_passenger(passenger)
        elif passenger.state == Passenger.RIDING and passenger.current_jeep:
            passenger.current_jeep.onboard_passengers.add(passenger)

    def _register_waiting_passenger(self, passenger: Passenger) -> None:
        new_coord = (passenger.curr_lat, passenger.curr_lon)
        prev_coord = self._waiting_coord_by_passenger.get(passenger)
        
        if prev_coord == new_coord:
            return
            
        if prev_coord is not None:
            prev_set = self.waiting_passengers.get(prev_coord)
            if prev_set is not None:
                prev_set.discard(passenger)
                if not prev_set:
                    del self.waiting_passengers[prev_coord]
                    
        self.waiting_passengers[new_coord].add(passenger)
        self._waiting_coord_by_passenger[passenger] = new_coord

    def _unregister_waiting_passenger(self, passenger: Passenger, coord: Optional[tuple[float, float]] = None) -> None:
        known_coord = self._waiting_coord_by_passenger.pop(passenger, None)
        target_coord = known_coord if coord is None else coord
        
        if target_coord is None:
            return
            
        target_set = self.waiting_passengers.get(target_coord)
        if target_set is not None:
            target_set.discard(passenger)
            if not target_set:
                del self.waiting_passengers[target_coord]

    def update(self) -> None:
        completed_passengers = []

        for p in self.active_passengers:
            prev_state = p.state
            prev_jeep = p.current_jeep
            prev_wait_coord = (p.curr_lat, p.curr_lon) if prev_state == Passenger.WAITING else None
            
            p.update()

            if p.state == Passenger.DONE:
                completed_passengers.append(p)

            if prev_state == Passenger.WAITING and p.state != Passenger.WAITING:
                self._unregister_waiting_passenger(p, prev_wait_coord)
            elif p.state == Passenger.WAITING:
                self._register_waiting_passenger(p)

            if prev_state == Passenger.RIDING and prev_jeep and (p.state != Passenger.RIDING or p.current_jeep is not prev_jeep):
                prev_jeep.onboard_passengers.discard(p)
            if p.state == Passenger.RIDING and p.current_jeep and (prev_state != Passenger.RIDING or p.current_jeep is not prev_jeep):
                p.current_jeep.onboard_passengers.add(p)
                
        for p in completed_passengers:
            self.active_passengers.discard(p)

        for jeep in self.jeeps:
            jeep.update()
            passed_nodes_data = jeep.nodes_passed_this_frame()
            
            if not passed_nodes_data:
                continue
            
            for node, route in passed_nodes_data:
                route_idx = self._route_indices.get(route)
                if route_idx is None:
                    continue
                
                # Alighting phase
                for p in tuple(jeep.onboard_passengers):
                    target_node = p.get_target_alight_node()
                    if target_node is not None and target_node is node:
                        p.state = Passenger.WALKING
                        p.current_jeep = None
                        p.curr_lat = node.lat
                        p.curr_lon = node.lon
                        p.complete_ride()
                        jeep.modify_passenger(-1)
                        jeep.onboard_passengers.discard(p)
                
                coord = (node.lat, node.lon)
                waiting_at_node = self.waiting_passengers.get(coord)
                
                # Boarding phase
                if waiting_at_node and jeep.curr_passenger_count < jeep.passenger_max:
                    for p in tuple(waiting_at_node):
                        if p.state != Passenger.WAITING:
                            self._waiting_coord_by_passenger.pop(p, None)
                            waiting_at_node.discard(p)
                            continue

                        current_coord = (p.curr_lat, p.curr_lon)
                        if current_coord != coord:
                            self._waiting_coord_by_passenger.pop(p, None)
                            waiting_at_node.discard(p)
                            self._register_waiting_passenger(p)
                            continue

                        if jeep.curr_passenger_count >= jeep.passenger_max:
                            break
                        
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
                            p.state = Passenger.RIDING
                            p.current_jeep = jeep
                            p.wait_ticks = 0
                            jeep.modify_passenger(1)
                            jeep.onboard_passengers.add(p)
                            self._waiting_coord_by_passenger.pop(p, None)
                            waiting_at_node.discard(p)
                            
                    if not waiting_at_node:
                        del self.waiting_passengers[coord]

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, radius: int = 12) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[JEEP SYSTEM] Visualization requires a square image.")
        
        for jeep in self.jeeps:
            image = jeep.draw(context, image, radius)
            
        return image