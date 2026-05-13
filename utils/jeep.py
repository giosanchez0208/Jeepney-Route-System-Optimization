"""Flow: route + start position + speed -> moving jeep state -> passenger and node queries.

Jeep(route: Route, currPos: tuple[float, float], speed: float) -> None initializes the vehicle, snaps it to the nearest route edge, and keeps heading plus passenger counts in sync with movement.
update(self) -> None advances the jeep.
nodes_passed_this_frame(self) -> Optional[list[tuple[Node, Route]]], modifyPassenger(self, amt: int) -> None, returnPathFrom(self, start_node: Node, end_node: Node) -> list[DirEdge], and getWeightIf(self, start_node: Node, end_node: Node) -> Optional[float] are the main query methods.

Inputs: a Route, a starting coordinate pair, and speed.
Outputs: updated position, heading, and per-frame node crossings.
Imported modules used: Node, Route, DirEdge, and _getDistance.
"""

# To test run - "python jeep_testing.py"
# To validate/diagnostic run - jeep_diagnostic.ipynb

from __future__ import annotations
import math
from uuid import uuid4
from typing import Optional

from .node import Node
from .route import Route
from .directed_edge import DirEdge, _getDistance
from PIL import Image, ImageDraw

class Jeep:
    def __init__(self, route: Route, curr_pos: tuple[float, float], speed: float) -> None:
        if not hasattr(route, 'path') or not hasattr(route, 'designated_color'):
            raise TypeError("[JEEP] route must have 'path' and 'designated_color' attributes.")
        if not isinstance(curr_pos, tuple) or len(curr_pos) != 2:
            raise TypeError("[JEEP] curr_pos must be a tuple of exactly 2 elements (lat, lon).")
        if not isinstance(speed, (int, float)) or isinstance(speed, bool):
            raise TypeError("[JEEP] speed must be a numeric value.")
        if speed < 0:
            raise ValueError("[JEEP] speed cannot be negative.")
        if not route.path:
            raise ValueError("[JEEP] route.path cannot be empty.")
        
        self.id: str = f"J{uuid4().hex}"
        self.route: Route = route
        self.speed_kmph: float = float(speed)
        self.speed: float = self.speed_kmph
        self.curr_pos: tuple[float, float] = curr_pos
        self.designated_color: str = route.designated_color
        self.curr_nodes_passed: Optional[list[tuple[Node, Route]]] = None
        self.heading: float = 0.0
        
        self.passenger_max: int = 16
        self.curr_passenger_count: int = 0

        self._edge_idx: int = 0
        self._edge_progress: float = 0.0
        
        self._snap_to_route()
        self._update_heading()

    def __str__(self) -> str:
        return (
            f"Jeep({self.id}): route={self.route.id}, "
            f"pos={self.curr_pos}, heading={self.heading:.2f}°, "
            f"passengers={self.curr_passenger_count}/{self.passenger_max}, "
            f"speed={self.speed} m/s, color={self.designated_color}"
        )

    def _snap_to_route(self) -> None:
        best_idx: int = 0
        min_dist: float = float('inf')
        temp_node: Node = Node(self.curr_pos[0], self.curr_pos[1])
        
        for i, edge in enumerate(self.route.path):
            dist: float = _getDistance(temp_node, edge.start)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
                
        self._edge_idx = best_idx
        self._edge_progress = 0.0
        snapped_edge: DirEdge = self.route.path[self._edge_idx]
        self.curr_pos = (snapped_edge.start.lat, snapped_edge.start.lon)

    def _update_heading(self) -> None:
        if not self.route.path:
            return
        edge: DirEdge = self.route.path[self._edge_idx]
        dy: float = edge.end.lat - edge.start.lat
        dx: float = edge.end.lon - edge.start.lon
        self.heading = math.degrees(math.atan2(dy, dx)) - 90.0

    def update(self) -> None:
        self.curr_nodes_passed = []
        distance_to_move: float = self.speed
        
        while distance_to_move > 0:
            current_edge: DirEdge = self.route.path[self._edge_idx]
            edge_length: float = current_edge.getLength()
            remaining_edge_dist: float = edge_length - self._edge_progress
            
            if distance_to_move >= remaining_edge_dist:
                distance_to_move -= remaining_edge_dist
                self.curr_nodes_passed.append((current_edge.end, self.route))
                self._edge_progress = 0.0
                self._edge_idx = (self._edge_idx + 1) % len(self.route.path)
                self._update_heading()
            else:
                self._edge_progress += distance_to_move
                distance_to_move = 0.0
                
        current_edge = self.route.path[self._edge_idx]
        edge_length = current_edge.getLength()
        
        if edge_length > 0:
            ratio: float = self._edge_progress / edge_length
            lat: float = current_edge.start.lat + ratio * (current_edge.end.lat - current_edge.start.lat)
            lon: float = current_edge.start.lon + ratio * (current_edge.end.lon - current_edge.start.lon)
            self.curr_pos = (lat, lon)
        else:
            self.curr_pos = (current_edge.start.lat, current_edge.start.lon)
            
        if not self.curr_nodes_passed:
            self.curr_nodes_passed = None

    def nodes_passed_this_frame(self) -> Optional[list[tuple[Node, Route]]]:
        return self.curr_nodes_passed

    def modify_passenger(self, amt: int) -> None:
        if not isinstance(amt, int) or isinstance(amt, bool):
            raise TypeError("[JEEP] amt must be an integer.")
        
        self.curr_passenger_count += amt
        if self.curr_passenger_count < 0:
            self.curr_passenger_count = 0
        elif self.curr_passenger_count > self.passenger_max:
            self.curr_passenger_count = self.passenger_max

    def return_path_from(self, start_node: Node, end_node: Node) -> list[DirEdge]:
        if not isinstance(start_node, Node) or not isinstance(end_node, Node):
            raise TypeError("[JEEP] Both start_node and end_node must be Node objects.")
        
        start_idx: int = -1
        for i, edge in enumerate(self.route.path):
            if edge.start == start_node:
                start_idx = i
                break

        if start_idx == -1:
            return []

        path: list[DirEdge] = []
        curr_idx: int = start_idx
        for _ in range(len(self.route.path)):
            edge: DirEdge = self.route.path[curr_idx]
            path.append(edge)
            if edge.end == end_node:
                return path
            curr_idx = (curr_idx + 1) % len(self.route.path)

        return []

    def get_weight_if(self, start_node: Node, end_node: Node) -> Optional[float]:
        if not isinstance(start_node, Node) or not isinstance(end_node, Node):
            raise TypeError("[JEEP] Both start_node and end_node must be Node objects.")
        
        path: list[DirEdge] = self.return_path_from(start_node, end_node)
        if not path:
            return None
        return sum(e.weight for e in path)

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, radius: int = 12) -> Image.Image:

        if image.width != image.height:
            raise ValueError("[JEEP] Visualization requires a square image.")

        draw = ImageDraw.Draw(image)

        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]

        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0:
            return image

        x = image.width * (self.curr_pos[1] - tl_lon) / lon_range
        y = image.height * (tl_lat - self.curr_pos[0]) / lat_range

        x = max(0, min(image.width - 1, int(x)))
        y = max(0, min(image.height - 1, int(y)))

        angle = math.radians(self.heading)

        front = (x + radius * math.cos(angle), y + radius * math.sin(angle))
        left = (x + radius * math.cos(angle + 2.5), y + radius * math.sin(angle + 2.5))
        right = (x + radius * math.cos(angle - 2.5), y + radius * math.sin(angle - 2.5))

        draw.polygon([front, left, right], fill=self.designated_color, outline="white")

        ratio = self.curr_passenger_count / self.passenger_max
        bar_w = radius * 2
        bar_h = 6

        bx1 = x - bar_w // 2
        by1 = y + radius + 8
        bx2 = bx1 + bar_w
        by2 = by1 + bar_h

        draw.rectangle([bx1, by1, bx2, by2], fill="gray")
        draw.rectangle([bx1, by1, bx1 + int(bar_w * ratio), by2], fill=self.designated_color)

        text = f"{self.curr_passenger_count}/{self.passenger_max}"
        draw.text((x - radius, y + radius + 18), text, fill="black")

        return image