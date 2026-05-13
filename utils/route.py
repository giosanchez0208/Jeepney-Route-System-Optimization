from __future__ import annotations
import json
from uuid import uuid4
from typing import Optional, Any
from scipy.spatial import cKDTree
import numpy as np
from PIL import ImageDraw, Image

from .node import Node
from .directed_edge import DirEdge
from .city_graph import CityGraph
from .direct_demand_sampler import DirectDemandSampler

import colorsys
import random
import math
from collections import defaultdict

def generate_color() -> str:
    """
    Generates high-saturation, mid-lightness colors suitable for transit maps.
    Returns hex color string.
    """
    h = random.random()
    s = 0.7 + random.random() * 0.3 
    l = 0.4 + random.random() * 0.2 
    r, g, b = [int(c * 255) for c in colorsys.hls_to_rgb(h, l, s)]
    return f"#{r:02x}{g:02x}{b:02x}"

# Modify your existing Route class __init__ to include:
# self.designated_color: str = generate_mini_metro_color()

class Route:
    def __init__(self, city_graph: CityGraph, path: list[DirEdge], id: Optional[str] = None) -> None:
        if not path:
            raise ValueError("[ROUTE] Path array cannot be empty.")
        if not isinstance(path, list):
            raise TypeError("[ROUTE] Path must be a list of DirEdge objects.")
        
        self.cg: CityGraph = city_graph
        self.path: list[DirEdge] = path
        self.id: str = id if id is not None else f"R{uuid4().hex}"
        self.designated_color: str = generate_color()
        self._validate_loop()
        self._validate_layer()
        self._validate_branching()

    def _validate_loop(self) -> None:
        if self.path[-1].end is not self.path[0].start:
            raise ValueError("[ROUTE] Path fails to loop. Terminal edge must connect to initial edge.")
            
        for i in range(len(self.path) - 1):
            if self.path[i].end is not self.path[i+1].start:
                raise ValueError(f"[ROUTE] Contiguity broken at index {i}. Edges do not form a continuous sequence.")

    def _validate_layer(self) -> None:
        for edge in self.path:
            if getattr(edge, 'layer', None) != 2:
                raise ValueError(f"[ROUTE] Invalid edge layer. Edge {edge.id} does not belong strictly to Layer 2.")

    def _validate_branching(self) -> None:
        for edge in self.path:
            layer_2_out = [e for e in getattr(edge, 'next_edges', []) if getattr(e, 'layer', None) == 2]
            if len(layer_2_out) != 1:
                raise ValueError(f"[ROUTE] Branching violation. Edge {edge.id} must have exactly one outgoing Layer 2 edge. Found {len(layer_2_out)}.")

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, color: str = "#FF0000", width: int = 3) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[ROUTE] Visualization requires a square image.")

        draw = ImageDraw.Draw(image)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0:
            return image

        for edge in self.path:
            x1 = (edge.start.lon - tl_lon) / lon_range * image.width
            y1 = (tl_lat - edge.start.lat) / lat_range * image.height
            x2 = (edge.end.lon - tl_lon) / lon_range * image.width
            y2 = (tl_lat - edge.end.lat) / lat_range * image.height
            
            draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
            
        return image

    def __str__(self) -> str:
        return f"Route({self.id}) | Edges: {len(self.path)} | Valid Loop: True | Layer: 2"

class RouteGenerator:
    def __init__(self, city_graph: CityGraph, sampler: DirectDemandSampler, verbose: bool = False) -> None:
        if city_graph is None or sampler is None:
            raise ValueError("[ROUTE GENERATOR] CityGraph and DirectDemandSampler are required.")
        self.cg: CityGraph = city_graph
        self.sampler: DirectDemandSampler = sampler
        self.verbose: bool = verbose

    def generate(self, n_points: int = 4, max_retries: int = 10) -> Route:
        if n_points < 2:
            raise ValueError("[ROUTE GENERATOR] Minimum of 2 points required to generate a route.")
        
        for attempt in range(max_retries):
            nodes = [self.sampler.get_point() for _ in range(n_points)]
            base_path: list[DirEdge] = []
            failed_segment = None
            
            for i in range(n_points):
                start_node = nodes[i]
                end_node = nodes[(i + 1) % n_points]
                
                segment = self.cg.find_shortest_path(start_node, end_node)
                
                if not segment:
                    failed_segment = (start_node, end_node)
                    break
                base_path.extend(segment)
            
            if failed_segment is None:
                return self._promote_to_route(base_path)
            
            if self.verbose and attempt < max_retries - 1:
                start, end = failed_segment
                print(f"[ROUTE GENERATOR] Attempt {attempt + 1}/{max_retries}: No drivable path between {start.id} and {end.id}. Retrying...")
        
        start, end = failed_segment
        raise ValueError(f"[ROUTE GENERATOR] Failed to generate route after {max_retries} attempts. Could not find drivable path between {start.id} and {end.id}.")

    def _promote_to_route(self, base_path: list[DirEdge]) -> Route:
        layer_2_path: list[DirEdge] = []
        for edge in base_path:
            l2_edge = DirEdge(edge.start, edge.end, weight=edge.weight)
            setattr(l2_edge, 'layer', 2)
            layer_2_path.append(l2_edge)
            
        for i in range(len(layer_2_path)):
            next_edge = layer_2_path[(i + 1) % len(layer_2_path)]
            layer_2_path[i].next_edges.append(next_edge)
            
        return Route(self.cg, layer_2_path)

def route_from_coords(city_graph: CityGraph, coords_json: str) -> Route:
    coords = json.loads(coords_json)
    if not coords or len(coords) < 2:
        raise ValueError("[ROUTE GENERATOR] Invalid coordinate sequence. Minimum 2 points required.")
    
    cg_nodes = city_graph.nodes
    cg_coords = np.array([(n.lat, n.lon) for n in cg_nodes])
    kdtree = cKDTree(cg_coords)
    
    query_coords = np.array(coords)
    _, matched_indices = kdtree.query(query_coords)
    snapped_nodes = [cg_nodes[idx] for idx in matched_indices]
    
    cleaned_nodes = [snapped_nodes[0]]
    for node in snapped_nodes[1:]:
        if node is not cleaned_nodes[-1]:
            cleaned_nodes.append(node)
            
    if len(cleaned_nodes) < 2:
        raise ValueError("[ROUTE GENERATOR] Coordinates map to a single topological node. Route generation impossible.")
    
    base_path: list[DirEdge] = []
    for i in range(len(cleaned_nodes) - 1):
        segment = city_graph.find_shortest_path(cleaned_nodes[i], cleaned_nodes[i+1])
        base_path.extend(segment)
        
    closing_segment = city_graph.find_shortest_path(cleaned_nodes[-1], cleaned_nodes[0])
    base_path.extend(closing_segment)
    
    layer_2_path: list[DirEdge] = []
    for edge in base_path:
        l2_edge = DirEdge(edge.start, edge.end, weight=edge.weight)
        setattr(l2_edge, 'layer', 2)
        layer_2_path.append(l2_edge)
        
    for i in range(len(layer_2_path)):
        next_edge = layer_2_path[(i + 1) % len(layer_2_path)]
        layer_2_path[i].next_edges.append(next_edge)
        
    return Route(city_graph, path=layer_2_path)

import math
from collections import defaultdict
from typing import Optional
from PIL import ImageDraw, Image

def _get_vector(start: 'Node', end: 'Node') -> tuple[float, float]:
    dx = end.lon - start.lon
    dy = start.lat - end.lat 
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length

def _get_relative_angle(v_base: tuple[float, float], v_target: tuple[float, float]) -> float:
    angle = math.atan2(v_target[1], v_target[0]) - math.atan2(v_base[1], v_base[0])
    return (angle + math.pi) % (2 * math.pi) - math.pi

class RouteSystem:
    def __init__(self) -> None:
        self.routes: list['Route'] = []

    def add_route(self, route: 'Route') -> None:
        self.routes.append(route)

    def _get_screen_coords(self, node: 'Node', context: tuple[tuple[float, float], tuple[float, float]], width: int, height: int) -> tuple[float, float]:
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        x = (node.lon - tl_lon) / lon_range * width
        y = (tl_lat - node.lat) / lat_range * height
        return x, y

    def _build_lane_registry(self) -> dict:
        edge_registry = defaultdict(list)
        for route in self.routes:
            for i, edge in enumerate(route.path):
                edge_key = frozenset([edge.start.id, edge.end.id])
                
                prev_edge = route.path[i - 1]
                v_base = _get_vector(edge.start, edge.end)
                v_entry = _get_vector(prev_edge.start, edge.start)
                
                if prev_edge.start.id == edge.end.id:
                    angle = math.pi 
                else:
                    angle = _get_relative_angle(v_base, v_entry)
                    
                edge_registry[edge_key].append((angle, route.id))

        for key in edge_registry:
            edge_registry[key].sort(key=lambda x: x[0])
            edge_registry[key] = [r_id for _, r_id in edge_registry[key]]
            
        return edge_registry

    def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, line_width: int = 4, spacing: int = 5) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[ROUTE SYSTEM] Visualization requires a square image.")

        draw = ImageDraw.Draw(image)
        edge_registry = self._build_lane_registry()

        for route in self.routes:
            path_length = len(route.path)
            segments = []
            turnarounds = set()

            for i in range(path_length):
                edge = route.path[i]

                key = frozenset([edge.start.id, edge.end.id])
                lanes = edge_registry[key]
                idx = lanes.index(route.id)
                off_mult = idx - (len(lanes) - 1) / 2.0

                x1, y1 = self._get_screen_coords(edge.start, context, image.width, image.height)
                x2, y2 = self._get_screen_coords(edge.end, context, image.width, image.height)

                v = _get_vector(edge.start, edge.end)
                n = (-v[1], v[0])

                ox1 = x1 + n[0] * off_mult * spacing
                oy1 = y1 + n[1] * off_mult * spacing
                ox2 = x2 + n[0] * off_mult * spacing
                oy2 = y2 + n[1] * off_mult * spacing

                segments.append(((ox1, oy1), (ox2, oy2), n))

                next_edge = route.path[(i + 1) % path_length]
                if edge.end.id == next_edge.start.id and edge.start.id == next_edge.end.id:
                    turnarounds.add(i)

            for i in range(path_length):
                seg_curr = segments[i]
                draw.line([seg_curr[0], seg_curr[1]], fill=route.designated_color, width=line_width)

                if i in turnarounds:
                    x, y = seg_curr[1]
                    n = seg_curr[2]
                    
                    cap_extension = line_width * 2.5
                    
                    cap_x1 = x + n[0] * cap_extension
                    cap_y1 = y + n[1] * cap_extension
                    cap_x2 = x - n[0] * cap_extension
                    cap_y2 = y - n[1] * cap_extension
                    draw.line([(cap_x1, cap_y1), (cap_x2, cap_y2)], fill=route.designated_color, width=line_width)
                else:
                    seg_next = segments[(i + 1) % path_length]
                    draw.line([seg_curr[1], seg_next[0]], fill=route.designated_color, width=line_width)

        return image