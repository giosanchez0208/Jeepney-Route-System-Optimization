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

class Route:
    def __init__(self, city_graph: CityGraph, path: list[DirEdge], id: Optional[str] = None) -> None:
        if not path:
            raise ValueError("[ROUTE] Path array cannot be empty.")
        if not isinstance(path, list):
            raise TypeError("[ROUTE] Path must be a list of DirEdge objects.")
        
        self.cg: CityGraph = city_graph
        self.path: list[DirEdge] = path
        self.id: str = id if id is not None else f"R{uuid4().hex}"
        
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