"""jeep.py

Jeep(route: Route, currPos: tuple[float, float], speed: float) -> None creates a Jeep entity.
update(self) -> None moves the Jeep along the route and records passed nodes.
nodes_passed_this_frame(self) -> Optional[list[Node]] returns nodes passed during the current update or None.
"""

from typing import Optional

from .node import Node
from .route import Route
from .directed_edge import _getDistance

class Jeep:
    def __init__(self, route: Route, currPos: tuple[float, float], speed: float) -> None:
        self.route = route
        self.speed = speed
        self.currPos = currPos
        self.currNodesPassed: Optional[list[Node]] = None
        
        self._edge_idx = 0
        self._edge_progress = 0.0
        
        self._snap_to_route()

    def _snap_to_route(self) -> None:
        """Snaps the initial coordinate to the closest start node of the route edges to initialize tracking."""
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

    def update(self) -> None:
        """Moves the Jeep along the route by self.speed meters."""
        self.currNodesPassed = []
        distance_to_move = self.speed
        
        while distance_to_move > 0:
            current_edge = self.route.path[self._edge_idx]
            edge_length = current_edge.getLength()
            remaining_edge_dist = edge_length - self._edge_progress
            
            if distance_to_move >= remaining_edge_dist:
                distance_to_move -= remaining_edge_dist
                self.currNodesPassed.append(current_edge.end)
                self._edge_progress = 0.0
                self._edge_idx = (self._edge_idx + 1) % len(self.route.path)
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

    def nodes_passed_this_frame(self) -> Optional[list[Node]]:
        """Returns the nodes passed during the last update, or None if empty."""
        return self.currNodesPassed