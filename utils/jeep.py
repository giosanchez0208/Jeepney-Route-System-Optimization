from __future__ import annotations
import math
from uuid import uuid4
from typing import Optional

from .node import Node
from .route import Route
from .directed_edge import DirEdge, _getDistance
from PIL import Image, ImageDraw

_KMH_TO_METERS_PER_TICK: float = 1000.0 / 3600.0

class Jeep:
    def __init__(self, route: Route, curr_pos: tuple[float, float], speed: float, max_capacity: int = 16, seconds_per_tick: int = 1) -> None:
        if not hasattr(route, 'path') or not hasattr(route, 'designated_color'):
            raise TypeError("[JEEP] route must have 'path' and 'designated_color' attributes.")
        if not isinstance(curr_pos, tuple) or len(curr_pos) != 2:
            raise TypeError("[JEEP] curr_pos must be a tuple of exactly 2 elements (lon, lat).")
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
        self._initial_pos: tuple[float, float] = curr_pos
        self.designated_color: str = route.designated_color
        self.curr_nodes_passed: Optional[list[tuple[Node, Route]]] = None
        self.heading: float = 0.0
        
        self.passenger_max: int = max_capacity
        self.curr_passenger_count: int = 0
        self.seconds_per_tick: int = seconds_per_tick
        
        self.onboard_passengers: set = set()

        self._edge_idx: int = 0
        self._edge_progress: float = 0.0
        
        # Shared route weight cache (saves massive memory and computation)
        if not hasattr(route, '_node_indices'):
            import collections
            route._node_indices = collections.defaultdict(list)
            path = route.path
            n = len(path)
            route._prefix_sums = [0.0] * (n + 1)
            for i, e in enumerate(path):
                route._prefix_sums[i + 1] = route._prefix_sums[i] + e.weight
                route._node_indices[(e.start.lon, e.start.lat)].append(i)
            route._route_length = route._prefix_sums[-1] if n > 0 else 0.0
            route._min_weight_cache = {}
        
        self._snap_to_route()
        self._update_heading()
        
    def __str__(self) -> str:
        return (
            f"Jeep({self.id}): route={self.route.id}, "
            f"pos=({self.curr_pos[0]:.4f}, {self.curr_pos[1]:.4f}), heading={self.heading:.2f}°, "
            f"passengers={self.curr_passenger_count}/{self.passenger_max}, "
            f"speed={self.speed_kmph} km/h"
        )

    def _snap_to_route(self) -> None:
        best_idx: int = 0
        min_dist: float = float('inf')
        
        temp_node: Node = Node(self._initial_pos[0], self._initial_pos[1])
        
        for i, edge in enumerate(self.route.path):
            dist: float = _getDistance(temp_node, edge.start)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
                
        self._edge_idx = best_idx
        self._edge_progress = 0.0

    def _update_heading(self) -> None:
        if not self.route.path:
            return
        edge: DirEdge = self.route.path[self._edge_idx]
        dy: float = edge.end.lat - edge.start.lat
        dx: float = edge.end.lon - edge.start.lon
        self.heading = math.degrees(math.atan2(dy, dx)) - 90.0

    def update(self) -> None:
        self.curr_nodes_passed = []
        distance_to_move: float = self.speed_kmph * _KMH_TO_METERS_PER_TICK * self.seconds_per_tick
        
        while distance_to_move > 0:
            current_edge: DirEdge = self.route.path[self._edge_idx]
            remaining_edge_dist: float = current_edge._length - self._edge_progress
            
            if distance_to_move >= remaining_edge_dist:
                distance_to_move -= remaining_edge_dist
                self.curr_nodes_passed.append((current_edge.end, self.route))
                self._edge_progress = 0.0
                self._edge_idx = (self._edge_idx + 1) % len(self.route.path)
                self._update_heading()
            else:
                self._edge_progress += distance_to_move
                distance_to_move = 0.0
                
        if not self.curr_nodes_passed:
            self.curr_nodes_passed = None

    @property
    def curr_pos(self) -> tuple[float, float]:
        if not self.route.path:
            return (0.0, 0.0)

        current_edge = self.route.path[self._edge_idx]
        
        if current_edge._length > 0 and self._edge_progress > 0:
            ratio = self._edge_progress / current_edge._length
            lon = current_edge.start.lon + ratio * (current_edge.end.lon - current_edge.start.lon)
            lat = current_edge.start.lat + ratio * (current_edge.end.lat - current_edge.start.lat)
            return (lon, lat)
            
        return (current_edge.start.lon, current_edge.start.lat)

    def nodes_passed_this_frame(self, format_as_str: bool = False) -> Optional[list[tuple[Node, Route]]]:
        if format_as_str:
            return [f"{node} ({route.id})" for node, route in self.curr_nodes_passed] if self.curr_nodes_passed else None
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
        
        # O(1) dictionary lookup instead of O(N) linear search
        start_key = (start_node.lon, start_node.lat)
        start_indices = self.route._node_indices.get(start_key)
        
        if not start_indices:
            return []
            
        start_idx = start_indices[0] 
        
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
            
        # Match by COORDINATE, not object identity. Layer-2 promotion gives every route its
        # own Node copies, so a passenger's planned-alight node (built on a DIFFERENT route)
        # could never match this route's nodes by id() -- which silently made opportunistic
        # boarding impossible. Coordinate keys let an alternative jeep recognize a shared stop.
        start_key = (start_node.lon, start_node.lat)
        end_key = (end_node.lon, end_node.lat)
        cache_key = (start_key, end_key)
        if cache_key in self.route._min_weight_cache:
            return self.route._min_weight_cache[cache_key]

        start_indices = self.route._node_indices.get(start_key)
        end_indices = self.route._node_indices.get(end_key)
        
        if not start_indices or not end_indices:
            self.route._min_weight_cache[cache_key] = None
            return None
            
        min_weight = float('inf')
        for s in start_indices:
            for e in end_indices:
                if e > s:
                    weight = self.route._prefix_sums[e] - self.route._prefix_sums[s]
                elif e < s:
                    weight = self.route._route_length - self.route._prefix_sums[s] + self.route._prefix_sums[e]
                else:
                    weight = self.route._route_length # full loop if same node
                
                if weight < min_weight:
                    min_weight = weight
                    
        result = min_weight if min_weight != float('inf') else None
        self.route._min_weight_cache[cache_key] = result
        return result

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

        x = image.width * (self.curr_pos[0] - tl_lon) / lon_range
        y = image.height * (tl_lat - self.curr_pos[1]) / lat_range

        x = max(0, min(image.width - 1, int(x)))
        y = max(0, min(image.height - 1, int(y)))

        # Convert the internal compass-style heading into screen coordinates.
        # PIL uses x-right / y-down, so the rendering angle needs to be flipped.
        angle = math.radians(-self.heading - 90.0)

        # Draw a small isosceles triangle instead of a symmetric marker so the
        # vehicle direction reads more clearly in motion.
        rear_offset = math.radians(150.0)
        rear_radius = radius * 0.75
        front = (x + radius * math.cos(angle), y + radius * math.sin(angle))
        left = (x + rear_radius * math.cos(angle + rear_offset), y + rear_radius * math.sin(angle + rear_offset))
        right = (x + rear_radius * math.cos(angle - rear_offset), y + rear_radius * math.sin(angle - rear_offset))

        draw.polygon([front, left, right], fill=self.designated_color, outline="black")

        # Draw number of passengers on top
        text = str(self.curr_passenger_count)
        
        # Approximate text bounding box (centering)
        draw.text((x - 4, y - radius - 10), text, fill="white", stroke_width=1, stroke_fill="black")

        return image
