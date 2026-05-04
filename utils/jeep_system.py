"""jeep_system.py

JeepSystem(jeeps: list[Jeep], routes: list[Route], weight_tolerance: float) -> None creates the orchestrator.
add_passenger(self, passenger: Passenger) -> None injects a passenger into the system.
update(self) -> None triggers system-wide ticks and handles boarding, alighting, and dynamic route substitution.
"""

from .jeep import Jeep
from .passenger import Passenger
from .route import Route

class JeepSystem:
    def __init__(self, jeeps: list[Jeep], routes: list[Route], weight_tolerance: float = 50.0) -> None:
        self.jeeps = jeeps
        self.routes = routes
        self.passengers: list[Passenger] = []
        self.weight_tolerance = weight_tolerance

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