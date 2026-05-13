"""
Topological Pruning Justification

Reference: 
Iliopoulou, C., Kepaptsoglou, K., & Vlahogianni, E. I. (2019). 
Metaheuristics for the transit network design problem: a review and comparative analysis. 
Public Transport, 11(3), 487-521. https://doi.org/10.1007/s12469-019-00211-2

Rationale: 
Deploying agent-based routing heuristics on an unpruned network graph causes immediate 
combinatorial explosion. By evaluating the 'highway' tag to isolate the arterial skeleton, 
we artificially restrict the search space. This forces the metaheuristic to converge on 
viable transit corridors rather than wasting iterations evaluating residential dead-ends.

Jeepneys operate under fixed route franchises regulated by the Land Transportation Franchising and Regulatory Board (LTFRB). They function as arterial transit corridors, not point-to-point taxi services. Last-mile residential transport is formally delegated to tricycles and pedicabs.

Guillen, M. D., Ishida, H., & Okamoto, N. (2013). Is the use of informal public transport modes in developing countries habitual? An empirical study in Davao City, Philippines. Transport Policy, 26, 31-42. https://doi.org/10.1016/j.tranpol.2012.12.008

"""

from __future__ import annotations
import hashlib
import os
import pickle
import urllib.request
from collections import defaultdict
from heapq import heappop, heappush
from itertools import count
from typing import Optional, Union

import networkx as nx
import osmnx as ox
from PIL import Image, ImageDraw
from pyrosm import OSM
from tqdm import tqdm

from .directed_edge import DirEdge, _getDistance, _stitch
from .node import Node

def _validate_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if not isinstance(bbox, tuple) or len(bbox) != 4:
        raise ValueError("[CITY GRAPH] Invalid bbox. Must be a tuple of 4 floats: (min_lat, max_lat, min_lon, max_lon).")
    return bbox

def _get_cache_path(name: str, bbox: tuple[float, float, float, float]) -> str:
    os.makedirs("utils/.cache", exist_ok=True)
    base_str = f"{name}_{bbox}_pruned"
    file_hash = hashlib.md5(base_str.encode()).hexdigest()
    return f"utils/.cache/{file_hash}_graph.pkl"

class CityGraph:
    def __init__(
        self, 
        bbox: Optional[tuple[float, float, float, float]] = None, 
        name: str = "UrbanNetwork", 
        landmarks: Optional[dict[str, tuple[float, float]]] = None, 
        pbf_path: str = "utils/data/philippines-latest.osm.pbf",
        use_api: bool = False,
        verbose: bool = False
    ) -> None:
        self.name: str = name
        self.verbose: bool = verbose
        self.landmarks: dict[str, Node] = {}
        
        self.nodes: list[Node] = []
        self.graph: list[DirEdge] = []
        self._outgoing_edges: dict[Node, list[DirEdge]] = defaultdict(list)

        if bbox is not None:
            self.bbox = _validate_bbox(bbox)
            self.pbf_path = pbf_path
            self.use_api = use_api
            
            self._graph_cache_path = _get_cache_path(self.name, self.bbox)
            self._road_graph = self._load_road_graph()
            self._node_lookup: dict[int, Node] = {}
            
            self._build_nodes()
            self._build_graph()
        else:
            self.bbox = (0.0, 0.0, 0.0, 0.0)

        self.stitch_graph()

        if landmarks:
            self._build_landmarks(landmarks)

    def inject_toy_data(self, nodes: list['Node'], edges: list['DirEdge']) -> None:
        """Loads custom topologies into an empty graph and recalculates network adjacencies."""
        if self.bbox != (0.0, 0.0, 0.0, 0.0):
            raise RuntimeError("[CITY GRAPH] Cannot inject toy data into a populated OSM graph.")
            
        self.nodes.extend(nodes)
        self.graph.extend(edges)
        self.stitch_graph()

    def __str__(self) -> str:
        drivable_count = sum(1 for e in self.graph if e.is_drivable)
        return (f"CityGraph({self.name}) | Nodes: {len(self.nodes)} | "
                f"Edges: {len(self.graph)} (Drivable: {drivable_count}) | "
                f"Landmarks: {list(self.landmarks.keys())}")

    def stitch_graph(self) -> None:
        for edge in self.graph:
            edge.next_edges = []
        _stitch(self.graph, self.graph)
        self._build_outgoing_edges()

    def find_shortest_path(self, start: Node, end: Node) -> list[DirEdge]:
        if start not in self.nodes or end not in self.nodes:
            raise ValueError("[CITY GRAPH] Start and end nodes must belong to this CityGraph instance.")
        if start is end:
            return []

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        heappush(frontier, (_getDistance(start, end), 0.0, next(sequence), start))

        came_from: dict[Node, tuple[Node, DirEdge]] = {}
        cost_so_far: dict[Node, float] = {start: 0.0}

        while frontier:
            _, current_cost, _, current = heappop(frontier)

            if current is end:
                return self._reconstruct_path(came_from, start, end)

            if current_cost > cost_so_far.get(current, float("inf")):
                continue

            for edge in self._outgoing_edges.get(current, []):
                if not edge.is_drivable:
                    continue

                next_node = edge.end
                new_cost = current_cost + _getDistance(edge.start, edge.end)
                if new_cost >= cost_so_far.get(next_node, float("inf")):
                    continue

                cost_so_far[next_node] = new_cost
                came_from[next_node] = (current, edge)
                priority = new_cost + _getDistance(next_node, end)
                heappush(frontier, (priority, new_cost, next(sequence), next_node))

        raise ValueError(f"[CITY GRAPH] No path found between {start.id} and {end.id}.")

    def _load_road_graph(self) -> nx.MultiDiGraph:
        if os.path.exists(self._graph_cache_path):
            if self.verbose:
                print("[CITY GRAPH] Loading graph from binary cache.")
            with open(self._graph_cache_path, "rb") as f:
                return pickle.load(f)

        match self.use_api:
            case True:
                return self._extract_from_api()
            case False:
                if not os.path.exists(self.pbf_path):
                    self._download_pbf()
                return self._extract_from_pbf()

    def _extract_from_pbf(self) -> nx.MultiDiGraph:
        if self.verbose:
            print(f"[CITY GRAPH] Extracting graph from PBF: {self.pbf_path}")
            
        min_lat, max_lat, min_lon, max_lon = self.bbox
        osm = OSM(self.pbf_path, bounding_box=[min_lon, min_lat, max_lon, max_lat])
        nodes, edges = osm.get_network(network_type="driving", nodes=True)
        graph = osm.to_graph(nodes, edges, graph_type="networkx")
        
        with open(self._graph_cache_path, "wb") as f:
            pickle.dump(graph, f)
            
        return graph

    def _extract_from_api(self) -> nx.MultiDiGraph:
        if self.verbose:
            print("[CITY GRAPH] Extracting via Overpass API.")
        min_lat, max_lat, min_lon, max_lon = self.bbox
        graph = ox.graph_from_bbox(bbox=(max_lat, min_lat, max_lon, min_lon), network_type="drive", simplify=True)
        
        with open(self._graph_cache_path, "wb") as f:
            pickle.dump(graph, f)
            
        return graph

    def _download_pbf(self) -> None:
        url = "https://download.geofabrik.de/asia/philippines-latest.osm.pbf"
        if self.verbose:
            print(f"[CITY GRAPH] PBF not found. Downloading from {url}...")
        os.makedirs(os.path.dirname(self.pbf_path), exist_ok=True)
        urllib.request.urlretrieve(url, self.pbf_path)

    def _build_nodes(self) -> None:
        iterable = self._road_graph.nodes(data=True)
        if self.verbose:
            iterable = tqdm(iterable, desc="[CITY GRAPH] Building nodes")

        for osm_id, data in iterable:
            lon = data.get("x") if data.get("x") is not None else data.get("lon")
            lat = data.get("y") if data.get("y") is not None else data.get("lat")
            if lon is None or lat is None:
                continue

            node = Node(lon, lat)
            self._node_lookup[osm_id] = node
            self.nodes.append(node)

    def _is_arterial(self, highway_tag: Union[str, list[str]]) -> bool:
        arterials = {
            "primary", "primary_link", "secondary", "secondary_link", 
            "tertiary", "tertiary_link", "trunk", "trunk_link"
        }
        match highway_tag:
            case list():
                return any(h in arterials for h in highway_tag)
            case str():
                return highway_tag in arterials
            case _:
                return False

    def _build_graph(self) -> None:
        seen_pairs: set[tuple[int, int]] = set()
        edges = list(self._road_graph.edges(keys=True, data=True))
        
        iterable = edges
        if self.verbose:
            iterable = tqdm(iterable, desc="[CITY GRAPH] Building edges")

        for start_id, end_id, _, data in iterable:
            if start_id not in self._node_lookup or end_id not in self._node_lookup:
                continue
            if start_id == end_id:
                continue

            pair = tuple(sorted((start_id, end_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            start, end = self._node_lookup[start_id], self._node_lookup[end_id]
            if start.lon == end.lon and start.lat == end.lat:
                continue
            is_drivable = self._is_arterial(data.get("highway"))
            
            self.graph.append(DirEdge(start, end, is_drivable=is_drivable))
            self.graph.append(DirEdge(end, start, is_drivable=is_drivable))

    def _build_outgoing_edges(self) -> None:
        self._outgoing_edges = defaultdict(list)
        for edge in self.graph:
            self._outgoing_edges[edge.start].append(edge)

    def _build_landmarks(self, landmarks: dict[str, tuple[float, float]]) -> None:
        for name, coords in landmarks.items():
            lat, lon = coords
            temp_node = Node(lon, lat)
            nearest_node = min(self.nodes, key=lambda n: _getDistance(n, temp_node))
            self.landmarks[name] = nearest_node

    def _reconstruct_path(self, came_from: dict[Node, tuple[Node, DirEdge]], start: Node, end: Node) -> list[DirEdge]:
        path: list[DirEdge] = []
        current = end
        while current is not start:
            previous, edge = came_from[current]
            path.append(edge)
            current = previous
        path.reverse()
        return path

    def get_bounds(self, margin: float = 0.05) -> tuple[tuple[float, float], tuple[float, float]]:
        min_lon = min(n.lon for n in self.nodes)
        max_lon = max(n.lon for n in self.nodes)
        min_lat = min(n.lat for n in self.nodes)
        max_lat = max(n.lat for n in self.nodes)
        
        lon_span, lat_span = max_lon - min_lon, max_lat - min_lat
        max_span = max(lon_span, lat_span)
        
        c_lon, c_lat = (min_lon + max_lon) / 2.0, (min_lat + max_lat) / 2.0
        half_span = (max_span / 2.0) * (1.0 + margin)
        
        return ((c_lon - half_span, c_lat + half_span), (c_lon + half_span, c_lat - half_span))

    def draw(self, size: int = 800, only_drivable: bool = False) -> Image.Image:
        if size <= 0:
            raise ValueError("[CITY GRAPH] Draw size must be positive.")
            
        context = self.get_bounds()
        image = Image.new("RGB", (size, size), "white")
        
        for edge in self.graph:
            if only_drivable and not edge.is_drivable:
                continue
            color = "#8C8C8C" if edge.is_drivable else "#B5B5B5"
            edge.draw(context, image, color=color)
            
        return image

    def draw_landmarks(self, image: Image.Image) -> Image.Image:
        if image.width != image.height:
            raise ValueError("[CITY GRAPH] Landmark overlay requires a square image.")
            
        context = self.get_bounds()
        draw = ImageDraw.Draw(image)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        
        lon_range, lat_range = br_lon - tl_lon, tl_lat - br_lat

        for name, node in self.landmarks.items():
            x = (node.lon - tl_lon) / lon_range * image.width
            y = (tl_lat - node.lat) / lat_range * image.height
            draw.text((x + 5, y + 5), name, fill="black")
            draw.ellipse([x-3, y-3, x+3, y+3], fill="red")
            
        return image