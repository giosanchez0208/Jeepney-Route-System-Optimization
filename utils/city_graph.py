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
"""

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
    """
    Validates that the bounding box contains exactly four float coordinates.
    """
    if not isinstance(bbox, tuple) or len(bbox) != 4:
        raise ValueError("[CITY GRAPH] Invalid bbox. Must be a tuple of 4 floats: (min_lat, max_lat, min_lon, max_lon).")
    return bbox

def _get_cache_path(name: str, bbox: tuple[float, float, float, float]) -> str:
    """
    Generates a unique MD5 hash for the binary graph cache based on spatial limits.
    """
    os.makedirs(".cache", exist_ok=True)
    base_str = f"{name}_{bbox}_pruned"
    file_hash = hashlib.md5(base_str.encode()).hexdigest()
    return f".cache/{file_hash}_graph.pkl"

class CityGraph:
    def __init__(
        self, 
        bbox: tuple[float, float, float, float], 
        name: str = "UrbanNetwork", 
        landmarks: Optional[dict[str, tuple[float, float]]] = None, 
        pbf_path: str = "utils/data/philippines-latest.osm.pbf",
        verbose: bool = False
    ) -> None:
        self.bbox: tuple[float, float, float, float] = _validate_bbox(bbox)
        self.name: str = name
        self.pbf_path: str = pbf_path
        self.verbose: bool = verbose
        
        self.nodes: list[Node] = []
        self.graph: list[DirEdge] = []
        self.landmarks: dict[str, Node] = {}

        self._graph_cache_path: str = _get_cache_path(self.name, self.bbox)
        self._road_graph: nx.MultiDiGraph = self._load_road_graph()
        self._node_lookup: dict[int, Node] = {}
        self._outgoing_edges: dict[Node, list[DirEdge]] = defaultdict(list)

        self._build_nodes()
        self._build_graph()
        self.stitch_graph()

        if landmarks:
            self._build_landmarks(landmarks)

    def __str__(self) -> str:
        """
        Returns a formatted string representing the network composition.
        """
        drivable_count = sum(1 for e in self.graph if e.is_drivable)
        return f"CityGraph({self.name}) | Nodes: {len(self.nodes)} | Edges: {len(self.graph)} (Drivable: {drivable_count}) | Landmarks: {len(self.landmarks)}"

    def stitch_graph(self) -> None:
        """
        Clears existing edge links and rebuilds the connectivity matrix.
        """
        for edge in self.graph:
            edge.next_edges = []
        _stitch(self.graph, self.graph)
        self._build_outgoing_edges()

    def info(self) -> str:
        """
        Returns standard integer metrics for nodes and edges.
        """
        return f"Nodes: {len(self.nodes)}\nEdges: {len(self.graph)}"

    def findShortestPath(self, start: Node, end: Node) -> list[DirEdge]:
        """
        Calculates the optimal sequence of DirEdges using the A* algorithm.
        """
        if start not in self.nodes:
            raise ValueError("[CITY GRAPH] start node must belong to this CityGraph.")
        if end not in self.nodes:
            raise ValueError("[CITY GRAPH] end node must belong to this CityGraph.")
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

        raise ValueError("[CITY GRAPH] No path found between the provided nodes.")

    def _load_road_graph(self) -> nx.MultiDiGraph:
        """
        Retrieves spatial data via binary pickle cache, local PBF file, or Overpass API fallback.
        """
        if os.path.exists(self._graph_cache_path):
            if self.verbose:
                print("[CITY GRAPH] Loading graph from binary cache.")
            with open(self._graph_cache_path, "rb") as f:
                return pickle.load(f)

        if not os.path.exists(self.pbf_path):
            print(f"[CITY GRAPH] PBF file not found at '{self.pbf_path}'.")
            user_choice = input("Enter 'download' to fetch PBF, 'api' to use Overpass API, or 'abort': ").strip().lower()
            
            if user_choice == "download":
                self._download_pbf()
            elif user_choice == "api":
                return self._extract_from_api()
            else:
                raise FileNotFoundError("[CITY GRAPH] Graph extraction aborted by user.")

        if self.verbose:
            print("[CITY GRAPH] Extracting graph offline from PBF file.")
            
        min_lat, max_lat, min_lon, max_lon = self.bbox
        osm = OSM(self.pbf_path, bounding_box=[min_lon, min_lat, max_lon, max_lat])
        nodes, edges = osm.get_network(network_type="driving", nodes=True)
        graph = osm.to_graph(nodes, edges, graph_type="networkx")
        
        with open(self._graph_cache_path, "wb") as f:
            pickle.dump(graph, f)
            
        return graph

    def _extract_from_api(self) -> nx.MultiDiGraph:
        """
        Pulls road data directly from the Overpass API using the bounding box.
        """
        if self.verbose:
            print("[CITY GRAPH] Extracting via Overpass API. Latency expected.")
        min_lat, max_lat, min_lon, max_lon = self.bbox
        graph = ox.graph_from_bbox(bbox=(max_lat, min_lat, max_lon, min_lon), network_type="drive", simplify=True)
        
        with open(self._graph_cache_path, "wb") as f:
            pickle.dump(graph, f)
            
        return graph

    def _download_pbf(self) -> None:
        """
        Downloads the standard Geofabrik PBF dataset for the Philippines.
        """
        url = "https://download.geofabrik.de/asia/philippines-latest.osm.pbf"
        if self.verbose:
            print(f"[CITY GRAPH] Downloading {url}...")
        os.makedirs(os.path.dirname(self.pbf_path), exist_ok=True)
        urllib.request.urlretrieve(url, self.pbf_path)
        if self.verbose:
            print("[CITY GRAPH] Download complete.")

    def _build_nodes(self) -> None:
        """
        Instantiates Node objects from NetworkX node data.
        """
        iterable = self._road_graph.nodes(data=True)
        if self.verbose:
            iterable = tqdm(iterable, desc="Building nodes")

        for osm_id, data in iterable:
            lon = data.get("x") if data.get("x") is not None else data.get("lon")
            lat = data.get("y") if data.get("y") is not None else data.get("lat")
            if lon is None or lat is None:
                continue

            node = Node(lon, lat)
            self._node_lookup[osm_id] = node
            self.nodes.append(node)

    def _is_arterial(self, highway_tag: Union[str, list[str]]) -> bool:
        """
        Evaluates OSM highway tags against valid jeepney routing corridors.
        """
        arterials = {
            "primary", "primary_link", 
            "secondary", "secondary_link", 
            "tertiary", "tertiary_link", 
            "trunk", "trunk_link"
        }
        if isinstance(highway_tag, list):
            return any(h in arterials for h in highway_tag)
        return highway_tag in arterials

    def _build_graph(self) -> None:
        """
        Instantiates bidirectional DirEdge objects, defining drivability based on topology.
        """
        seen_pairs: set[tuple[int, int]] = set()
        edges = list(self._road_graph.edges(keys=True, data=True))
        
        iterable = edges
        if self.verbose:
            iterable = tqdm(iterable, desc="Building graph edges")

        for start_osm_id, end_osm_id, _, data in iterable:
            if start_osm_id not in self._node_lookup or end_osm_id not in self._node_lookup:
                continue
            if start_osm_id == end_osm_id:
                continue

            pair = tuple(sorted((start_osm_id, end_osm_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            start = self._node_lookup[start_osm_id]
            end = self._node_lookup[end_osm_id]
            
            is_drivable = self._is_arterial(data.get("highway"))
            
            try:
                self.graph.append(DirEdge(start, end, is_drivable))
                self.graph.append(DirEdge(end, start, is_drivable))
            except ValueError:
                continue

    def _build_outgoing_edges(self) -> None:
        """
        Maps outgoing valid connections to their origin nodes for pathfinding.
        """
        self._outgoing_edges = defaultdict(list)
        iterable = self.graph
        if self.verbose:
            iterable = tqdm(iterable, desc="Mapping outgoing edges")

        for edge in iterable:
            self._outgoing_edges[edge.start].append(edge)

    def _build_landmarks(self, landmarks: dict[str, tuple[float, float]]) -> None:
        """
        Snaps provided coordinates to the nearest physical road Node.
        """
        if self.verbose:
            print("[CITY GRAPH] Snapping explicit coordinates to network.")
            
        for name, coords in landmarks.items():
            lat, lon = coords
            temp_node = Node(lon, lat)
            if not self.nodes:
                continue
            nearest_node = min(self.nodes, key=lambda n: _getDistance(n, temp_node))
            self.landmarks[name] = nearest_node

    def _reconstruct_path(self, came_from: dict[Node, tuple[Node, DirEdge]], start: Node, end: Node) -> list[DirEdge]:
        """
        Backtracks calculated route to return chronological DirEdge sequence.
        """
        path: list[DirEdge] = []
        current = end

        while current is not start:
            previous, edge = came_from[current]
            path.append(edge)
            current = previous

        path.reverse()
        return path

    def get_context(self, margin: float = 0.05) -> tuple[tuple[float, float], tuple[float, float]]:
        """
        Calculates a square spatial bounding box for visualization mapping.
        """
        if not self.nodes:
            return ((0.0, 0.0), (0.0, 0.0))
            
        min_lon = min(n.lon for n in self.nodes)
        max_lon = max(n.lon for n in self.nodes)
        min_lat = min(n.lat for n in self.nodes)
        max_lat = max(n.lat for n in self.nodes)
        
        lon_span = max_lon - min_lon
        lat_span = max_lat - min_lat
        max_span = max(lon_span, lat_span)
        
        center_lon = (min_lon + max_lon) / 2.0
        center_lat = (min_lat + max_lat) / 2.0
        
        half_span = (max_span / 2.0) * (1.0 + margin)
        
        return (
            (center_lon - half_span, center_lat + half_span), 
            (center_lon + half_span, center_lat - half_span)
        )

    def draw(self, size: int = 800, only_drivable: bool = False) -> tuple[Image.Image, tuple[tuple[float, float], tuple[float, float]]]:
        """
        Renders the base network grid onto a standardized Image object.
        Applies functional contrast to differentiate arterials from dead-ends.
        """
        context = self.get_context()
        image = Image.new("RGB", (size, size), "white")
        
        for edge in self.graph:
            if only_drivable and not edge.is_drivable:
                continue
            
            line_color = "#8C8C8C" if edge.is_drivable else "#B5B5B5"
            
            try:
                edge.draw(context, image, color=line_color)
            except TypeError:
                edge.draw(context, image)
            
        return image, context

    def draw_landmarks(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image) -> None:
        """
        Overlays landmark names as text onto the base network Image.
        """
        draw = ImageDraw.Draw(image)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0:
            return

        for name, node in self.landmarks.items():
            x = (node.lon - tl_lon) / lon_range * image.width
            y = (tl_lat - node.lat) / lat_range * image.height
            draw.text((x, y), name, fill="black")