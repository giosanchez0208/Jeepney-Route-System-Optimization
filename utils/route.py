import json
from typing import Optional
from scipy.spatial import cKDTree
import numpy as np
from PIL import ImageDraw, Image

from .node import Node
from .directed_edge import DirEdge
from .city_graph import CityGraph
from .direct_demand_sampler import DirectDemandSampler

class Route:
    def __init__(self, city_graph: CityGraph, path: list[DirEdge]) -> None:
        if not path:
            raise ValueError("[Route] Path array cannot be empty.")
        
        self.cg = city_graph
        self.path = path
        
        self._validate_loop()
        self._validate_layer()
        self._validate_branching()

    def _validate_loop(self) -> None:
        if self.path[-1].end is not self.path[0].start:
            raise ValueError("[Route] Path fails to loop. Terminal edge must connect to initial edge.")
            
        for i in range(len(self.path) - 1):
            if self.path[i].end is not self.path[i+1].start:
                raise ValueError(f"[Route] Contiguity broken at index {i}. Edges do not form a continuous sequence.")

    def _validate_layer(self) -> None:
        for edge in self.path:
            if getattr(edge, 'layer', None) != 2:
                raise ValueError(f"[Route] Invalid edge layer. Edge {edge} does not belong strictly to Layer 2.")

    def _validate_branching(self) -> None:
        for edge in self.path:
            layer_2_out = [e for e in getattr(edge, 'next_edges', []) if getattr(e, 'layer', None) == 2]
            if len(layer_2_out) != 1:
                raise ValueError(f"[Route] Branching violation. Edge {edge} must have exactly one outgoing Layer 2 edge. Found {len(layer_2_out)}.")

    def draw(self, img_map: Image.Image, context: tuple[tuple[float, float], tuple[float, float]], color: tuple[int, int, int, int] = (255, 0, 0, 255), thickness: int = 3) -> None:
        draw = ImageDraw.Draw(img_map)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        for edge in self.path:
            x1 = (edge.start.lon - tl_lon) / lon_range * img_map.width
            y1 = (tl_lat - edge.start.lat) / lat_range * img_map.height
            x2 = (edge.end.lon - tl_lon) / lon_range * img_map.width
            y2 = (tl_lat - edge.end.lat) / lat_range * img_map.height
            
            draw.line([(x1, y1), (x2, y2)], fill=color, width=thickness)

    def __str__(self) -> str:
        return f"Route(edges={len(self.path)}, valid_loop=True, layer=2)"

class RouteGenerator:
    def __init__(self, city_graph: CityGraph, sampler: DirectDemandSampler):
        self.cg = city_graph
        self.sampler = sampler

    def generate(self, n_points: int = 4) -> Route:
        nodes = [self.sampler.get_point() for _ in range(n_points)]
        base_path = []
        
        for i in range(n_points):
            start_node = nodes[i]
            end_node = nodes[(i + 1) % n_points]
            segment = self.cg.findShortestPath(start_node, end_node)
            
            if not segment:
                raise ValueError(f"[Route] Spatial disconnect. Cannot find path between {start_node} and {end_node}.")
            base_path.extend(segment)
            
        return self._promote_to_route(base_path)

    def _promote_to_route(self, base_path: list[DirEdge]) -> Route:
        layer_2_path = []
        for edge in base_path:
            l2_edge = DirEdge(edge.start, edge.end, weight=edge.weight, layer=2)
            layer_2_path.append(l2_edge)
            
        for i in range(len(layer_2_path)):
            next_edge = layer_2_path[(i + 1) % len(layer_2_path)]
            layer_2_path[i].next_edges.append(next_edge)
            
        return Route(self.cg, layer_2_path)

def route_from_coords(city_graph: CityGraph, coords_json: str) -> Route:
    coords = json.loads(coords_json)
    if not coords or len(coords) < 2:
        raise ValueError("[Route] Invalid coordinate sequence. Minimum 2 points required.")
    
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
        raise ValueError("[Route] Coordinates map to a single topological node. Route generation impossible.")
    
    base_path = []
    for i in range(len(cleaned_nodes) - 1):
        segment = city_graph.findShortestPath(cleaned_nodes[i], cleaned_nodes[i+1])
        base_path.extend(segment)
        
    closing_segment = city_graph.findShortestPath(cleaned_nodes[-1], cleaned_nodes[0])
    base_path.extend(closing_segment)
    
    layer_2_path = []
    for edge in base_path:
        l2_edge = DirEdge(edge.start, edge.end, weight=edge.weight, layer=2)
        layer_2_path.append(l2_edge)
        
    for i in range(len(layer_2_path)):
        next_edge = layer_2_path[(i + 1) % len(layer_2_path)]
        layer_2_path[i].next_edges.append(next_edge)
        
    return Route(city_graph, path=layer_2_path)