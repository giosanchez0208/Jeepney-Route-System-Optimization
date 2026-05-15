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
        self.curr_pos: tuple[float, float] = curr_pos
        self.designated_color: str = route.designated_color
        self.curr_nodes_passed: Optional[list[tuple[Node, Route]]] = None
        self.heading: float = 0.0
        
        self.passenger_max: int = max_capacity
        self.curr_passenger_count: int = 0
        self.seconds_per_tick: int = seconds_per_tick
        
        self.onboard_passengers: set = set()

        self._edge_idx: int = 0
        self._edge_progress: float = 0.0
        
        # Pre-compute cumulative weights for every (start_node, end_node) pair along
        # the circular route so get_weight_if() is O(1) instead of O(|path|).
        # Key is (id(start_node), id(end_node)) to avoid coordinate comparisons.
        self._route_weight_cache: dict[tuple[int, int], float] = {}
        path = route.path
        n = len(path)
        if n > 0:
            # Build cumulative prefix sums of edge weights
            cum = [0.0] * (n + 1)
            for i, e in enumerate(path):
                cum[i + 1] = cum[i] + e.weight
            total = cum[n]
            # For every start index s, for every end index e > s (forward only),
            # store cumulative weight. Also handle wrap-around.
            for s in range(n):
                start_key = id(path[s].start)
                running = 0.0
                for k in range(1, n):  # at most n-1 edges forward
                    idx = (s + k) % n
                    running += path[(s + k - 1) % n].weight
                    end_key = id(path[idx].start)
                    cache_key = (start_key, end_key)
                    if cache_key not in self._route_weight_cache:
                        self._route_weight_cache[cache_key] = running
                # Also register the final end node of the last edge from s
                last_end_key = id(path[(s + n - 1) % n].end)
                running_total = sum(path[(s + k) % n].weight for k in range(n))
                cache_key = (start_key, last_end_key)
                if cache_key not in self._route_weight_cache:
                    self._route_weight_cache[cache_key] = running_total
        
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
        temp_node: Node = Node(self.curr_pos[0], self.curr_pos[1])
        
        for i, edge in enumerate(self.route.path):
            dist: float = _getDistance(temp_node, edge.start)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
                
        self._edge_idx = best_idx
        self._edge_progress = 0.0
        snapped_edge: DirEdge = self.route.path[self._edge_idx]
        self.curr_pos = (snapped_edge.start.lon, snapped_edge.start.lat)

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
        edge_length: float = 0.0  # will be set in the loop
        
        while distance_to_move > 0:
            current_edge: DirEdge = self.route.path[self._edge_idx]
            edge_length = current_edge._length
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
        # Reuse the cached length — avoids a second _getDistance call
        edge_length = current_edge._length
        
        if edge_length > 0:
            ratio: float = self._edge_progress / edge_length
            lon: float = current_edge.start.lon + ratio * (current_edge.end.lon - current_edge.start.lon)
            lat: float = current_edge.start.lat + ratio * (current_edge.end.lat - current_edge.start.lat)
            self.curr_pos = (lon, lat)
        else:
            self.curr_pos = (current_edge.start.lon, current_edge.start.lat)
            
        if not self.curr_nodes_passed:
            self.curr_nodes_passed = None

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
        # O(1) lookup using the pre-computed cache built at __init__ time.
        return self._route_weight_cache.get((id(start_node), id(end_node)))

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
