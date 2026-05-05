"""jeep.py

Public API:
- Jeep(route, currPos, speed) models a moving vehicle on a circular route.
- update() advances the jeep and tracks nodes crossed in the current frame.
- nodes_passed_this_frame(), modifyPassenger(), returnPathFrom(), and
  getWeightIf() are the external behavior/query methods.
- route, currPos, heading, passenger_max, and curr_passenger_count are the
  primary public attributes.

Internal API:
- _snap_to_route() and _update_heading() keep the jeep aligned to its path.
- _edge_idx, _edge_progress, and currNodesPassed store private movement state.
"""

import math
from typing import Optional

from .node import Node
from .route import Route
from .directed_edge import DirEdge, _getDistance

class Jeep:
    def __init__(self, route: Route, currPos: tuple[float, float], speed: float) -> None:
        self.route = route
        self.speed = speed
        self.currPos = currPos
        self.currNodesPassed: Optional[list[tuple[Node, Route]]] = None
        self.heading: float = 0.0
        
        self.passenger_max: int = 16
        self.curr_passenger_count: int = 0
        
        self._edge_idx = 0
        self._edge_progress = 0.0
        
        self._snap_to_route()
        self._update_heading()

    def _snap_to_route(self) -> None:
        best_idx = 0
        min_dist = float('inf')
        
        temp_node = Node(self.currPos[1], self.currPos[0])
        
        for i, edge in enumerate(self.route.path):
            dist = _getDistance(temp_node, edge.start)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
                
        self._edge_idx = best_idx
        self._edge_progress = 0.0

    def _update_heading(self) -> None:
        if not self.route.path:
            return
        edge = self.route.path[self._edge_idx]
        dy = edge.end.lat - edge.start.lat
        dx = edge.end.lon - edge.start.lon
        self.heading = math.degrees(math.atan2(dy, dx)) - 90.0

    def update(self) -> None:
        self.currNodesPassed = []
        distance_to_move = self.speed
        
        while distance_to_move > 0:
            current_edge = self.route.path[self._edge_idx]
            edge_length = current_edge.getLength()
            remaining_edge_dist = edge_length - self._edge_progress
            
            if distance_to_move >= remaining_edge_dist:
                distance_to_move -= remaining_edge_dist
                self.currNodesPassed.append((current_edge.end, self.route))
                self._edge_progress = 0.0
                self._edge_idx = (self._edge_idx + 1) % len(self.route.path)
                self._update_heading()
            else:
                self._edge_progress += distance_to_move
                distance_to_move = 0.0
                
        current_edge = self.route.path[self._edge_idx]
        edge_length = current_edge.getLength()
        
        if edge_length > 0:
            ratio = self._edge_progress / edge_length
            lat = current_edge.start.lat + ratio * (current_edge.end.lat - current_edge.start.lat)
            lon = current_edge.start.lon + ratio * (current_edge.end.lon - current_edge.start.lon)
            self.currPos = (lat, lon)
        else:
            self.currPos = (current_edge.start.lat, current_edge.start.lon)
            
        if not self.currNodesPassed:
            self.currNodesPassed = None

    def nodes_passed_this_frame(self) -> Optional[list[tuple[Node, Route]]]:
        return self.currNodesPassed

    def modifyPassenger(self, amt: int) -> None:
        self.curr_passenger_count += amt
        if self.curr_passenger_count < 0:
            self.curr_passenger_count = 0
        elif self.curr_passenger_count > self.passenger_max:
            self.curr_passenger_count = self.passenger_max

    def returnPathFrom(self, start_node: Node, end_node: Node) -> list[DirEdge]:
        start_idx = -1
        for i, edge in enumerate(self.route.path):
            if edge.start == start_node:
                start_idx = i
                break

        if start_idx == -1:
            return []

        path = []
        curr_idx = start_idx
        for _ in range(len(self.route.path)):
            edge = self.route.path[curr_idx]
            path.append(edge)
            if edge.end == end_node:
                return path
            curr_idx = (curr_idx + 1) % len(self.route.path)

        return []

    def getWeightIf(self, start_node: Node, end_node: Node) -> Optional[float]:
        path = self.returnPathFrom(start_node, end_node)
        if not path:
            return None
        return sum(e.weight for e in path)
