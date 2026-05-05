"""jeep_system.py

Public API:
- JeepSystem(jeeps, routes, weight_tolerance=50.0, equidistant_spawn=True)
  coordinates jeep movement and passenger boarding logic.
- add_passenger() injects a passenger into the system.
- update() advances passengers and jeeps, then resolves boarding and alighting.

Internal API:
- _space_jeeps_equidistantly() distributes jeeps across each route at startup.
- passengers is the system-owned passenger list.
"""

from .jeep import Jeep
from .passenger import Passenger
from .route import Route

class JeepSystem:
    def __init__(
        self, 
        jeeps: list[Jeep], 
        routes: list[Route], 
        weight_tolerance: float = 50.0, 
        equidistant_spawn: bool = True
    ) -> None:
        self.jeeps = jeeps
        self.routes = routes
        self.passengers: list[Passenger] = []
        self.weight_tolerance = weight_tolerance

        if equidistant_spawn:
            self._space_jeeps_equidistantly()

    def _space_jeeps_equidistantly(self) -> None:
        route_jeeps = {r: [] for r in self.routes}
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
                    
                    # 1e-5 tolerance prevents skipping edges on exact float boundaries
                    if accumulated + edge_len >= target_dist - 1e-5:
                        jeep._edge_idx = idx
                        jeep._edge_progress = target_dist - accumulated
                        
                        if edge_len > 0:
                            ratio = jeep._edge_progress / edge_len
                            lat = edge.start.lat + ratio * (edge.end.lat - edge.start.lat)
                            lon = edge.start.lon + ratio * (edge.end.lon - edge.start.lon)
                            jeep.currPos = (lat, lon)
                        else:
                            jeep.currPos = (edge.start.lat, edge.start.lon)
                            
                        jeep._update_heading()
                        break
                    accumulated += edge_len

    def add_passenger(self, passenger: Passenger) -> None:
        self.passengers.append(passenger)

    def update(self) -> None:
        for p in self.passengers:
            p.update()

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
                
                # 1. Process Alighting
                for p in self.passengers:
                    if p.state == "RIDING" and p.current_jeep == jeep:
                        target_node = p.get_target_alight_node()
                        if target_node and target_node.lat == node.lat and target_node.lon == node.lon:
                            p.state = "WALKING"
                            p.current_jeep = None
                            p.curr_lat = node.lat
                            p.curr_lon = node.lon
                            p.complete_ride()
                            jeep.modifyPassenger(-1)
                            
                # 2. Process Boarding (Standard and Dynamic Substitution)
                for p in self.passengers:
                    if p.state == "WAITING":
                        dist = ((p.curr_lat - node.lat)**2 + (p.curr_lon - node.lon)**2)**0.5
                        if dist < 1e-5 and jeep.curr_passenger_count < jeep.passenger_max:
                            target_route_idx = p.get_target_route_idx()
                            boarded = False
                            
                            if target_route_idx == route_idx:
                                boarded = True
                            else:
                                target_node = p.get_target_alight_node()
                                if target_node:
                                    alt_weight = jeep.getWeightIf(node, target_node)
                                    if alt_weight is not None:
                                        planned_weight = p.get_planned_ride_weight()
                                        if alt_weight <= planned_weight + self.weight_tolerance:
                                            boarded = True
                                            
                            if boarded:
                                p.state = "RIDING"
                                p.current_jeep = jeep
                                p.wait_ticks = 0
                                jeep.modifyPassenger(1)
