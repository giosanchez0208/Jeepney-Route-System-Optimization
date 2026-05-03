"""city_graph.py

_DRIVABLE_HIGHWAY_TYPES: set[str] stores highway tags treated as drivable.
CityGraph(query: str) -> None creates query: str, nodes: list[Node], graph: list[DirEdge], _road_graph: nx.MultiDiGraph, _node_lookup: dict[int, Node], _node_set: set[Node], and _outgoing_edges: dict[Node, list[DirEdge]].
stitch_graph(self) -> None clears and rebuilds edge stitching.
info(self) -> str returns node and edge counts.
findShortestPath(self, start: Node, end: Node) -> list[DirEdge] returns the shortest drivable path or raises ValueError.
_build_nodes(self) -> None populates nodes from the OSM graph.
_build_graph(self) -> None populates directed edges from the OSM graph.
_load_road_graph(self, query: str) -> nx.MultiDiGraph loads the road network for the query.
_build_outgoing_edges(self) -> None rebuilds the outgoing-edge lookup.
_reconstruct_path(self, came_from: dict[Node, tuple[Node, DirEdge]], start: Node, end: Node) -> list[DirEdge] returns the recovered path.
"""

from collections import defaultdict
from heapq import heappop, heappush
from itertools import count

import networkx as nx
import osmnx as ox
from osmnx._errors import InsufficientResponseError
from directed_edge import DirEdge, _getDistance, _stitch
from node import Node

_DRIVABLE_HIGHWAY_TYPES = {
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "unclassified", "residential",
    "living_street", "service", "road",
}

class CityGraph:
    def __init__(self, query: str) -> None:
        self.query = query
        self.nodes: list[Node] = []
        self.graph: list[DirEdge] = []

        self._road_graph: nx.MultiDiGraph = self._load_road_graph(query)
        self._node_lookup: dict[int, Node] = {}
        self._node_set: set[Node] = set()
        self._outgoing_edges: dict[Node, list[DirEdge]] = defaultdict(list)
        
        # O(1) lookup structure specifically built to accelerate A* search
        self._fast_edges: dict[Node, list[tuple[DirEdge, Node, float]]] = defaultdict(list)

        self._build_nodes()
        self._build_graph()
        self.stitch_graph()

    def stitch_graph(self) -> None:
        for edge in self.graph:
            edge.next_edges.clear()

        _stitch(self.graph, self.graph)
        self._build_outgoing_edges()

    def info(self) -> str:
        return f"Nodes: {len(self.nodes)}\nEdges: {len(self.graph)}"

    def findShortestPath(self, start: Node, end: Node) -> list[DirEdge]:
        if start not in self._node_set:
            raise ValueError("start must belong to this CityGraph.")
        if end not in self._node_set:
            raise ValueError("end must belong to this CityGraph.")
        if start is end:
            return []

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        
        # OPTIMIZATION: Memoize heuristic calculations to avoid redundant trig functions
        h_cache = {}
        def get_h(n: Node) -> float:
            if n not in h_cache:
                h_cache[n] = _getDistance(n, end)
            return h_cache[n]

        heappush(frontier, (get_h(start), 0.0, next(sequence), start))

        came_from: dict[Node, tuple[Node, DirEdge]] = {}
        cost_so_far: dict[Node, float] = {start: 0.0}
        fast_edges = self._fast_edges

        while frontier:
            _, current_cost, _, current = heappop(frontier)

            if current is end:
                return self._reconstruct_path(came_from, start, end)

            if current_cost > cost_so_far.get(current, float("inf")):
                continue

            # OPTIMIZATION: Unpack precalculated lengths, bypassing object methods entirely
            for edge, next_node, edge_length in fast_edges.get(current, []):
                new_cost = current_cost + edge_length
                
                if new_cost >= cost_so_far.get(next_node, float("inf")):
                    continue

                cost_so_far[next_node] = new_cost
                came_from[next_node] = (current, edge)
                priority = new_cost + get_h(next_node)
                heappush(frontier, (priority, new_cost, next(sequence), next_node))

        raise ValueError("No path found between the provided nodes.")

    def _build_nodes(self) -> None:
        for osm_id, data in self._road_graph.nodes(data=True):
            lon = data.get("x")
            lat = data.get("y")
            if lon is None or lat is None:
                continue

            node = Node(lon, lat)
            self._node_lookup[osm_id] = node
            self._node_set.add(node)
            self.nodes.append(node)

    def _build_graph(self) -> None:
        seen_pairs: set[tuple[int, int]] = set()
        node_lookup = self._node_lookup
        
        for start_osm_id, end_osm_id, _, data in self._road_graph.edges(keys=True, data=True):
            start = node_lookup.get(start_osm_id)
            end = node_lookup.get(end_osm_id)
            if start is None or end is None:
                continue

            if start_osm_id <= end_osm_id:
                pair = (start_osm_id, end_osm_id)
            else:
                pair = (end_osm_id, start_osm_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            highway = data.get("highway", "")
            if isinstance(highway, list):
                highway_types = set(highway)
            else:
                highway_types = {highway}
            is_drivable = bool(highway_types & _DRIVABLE_HIGHWAY_TYPES)

            self.graph.append(DirEdge(start, end, is_drivable))
            self.graph.append(DirEdge(end, start, is_drivable))

    def _load_road_graph(self, query: str) -> nx.MultiDiGraph:
        try:
            return ox.graph_from_place(query, network_type="drive", simplify=True)
        except (ValueError, TypeError, IndexError, AttributeError, InsufficientResponseError):
            try:
                place = ox.geocode_to_gdf(query)
            except (ValueError, TypeError, IndexError, AttributeError, InsufficientResponseError):
                lat, lon = ox.geocode(query)
                return ox.graph_from_point((lat, lon), dist=5000, network_type="drive", simplify=True)

            geometry = place.iloc[0].geometry
            centroid = geometry.centroid
            bounds = geometry.bounds

            lat_span = max(bounds[3] - bounds[1], 0.0)
            lon_span = max(bounds[2] - bounds[0], 0.0)
            dist = max(5000, int(max(lat_span, lon_span) * 111000 * 1.25))

            return ox.graph_from_point((centroid.y, centroid.x), dist=dist, network_type="drive", simplify=True)

    def _build_outgoing_edges(self) -> None:
        self._outgoing_edges = defaultdict(list)
        self._fast_edges = defaultdict(list)
        
        for edge in self.graph:
            self._outgoing_edges[edge.start].append(edge)
            
            # OPTIMIZATION: Pre-filter out non-drivable edges and precalculate distances
            if edge.is_drivable:
                self._fast_edges[edge.start].append((edge, edge.end, edge.getLength()))

    def _reconstruct_path(self, came_from: dict[Node, tuple[Node, DirEdge]], start: Node, end: Node) -> list[DirEdge]:
        path: list[DirEdge] = []
        current = end

        while current is not start:
            previous, edge = came_from[current]
            path.append(edge)
            current = previous

        path.reverse()
        return path

"""
if __name__ == "__main__":
    cg = CityGraph("City of Manila, Philippines")

    print(cg.info())

    from visualizer import StaticVisualizer

    # all edges
    vis = StaticVisualizer(
        cg.nodes,
        cg.graph,
        title="CityGraph Test",
        query=cg.query,
        mode="light_nolabels",
        labels_on=False,
        node_radius=1,
        edge_color="#d62728",
        edge_thickness=1,
        landmarks="MSU-IIT, Robinsons, Tibanga, Tambo, Tubod",
    )
    vis.export("results/test/city_graph_full.png", scale_up=3)
    del vis

    # print how many edges are drivable vs non-drivable
    drivable_count = sum(1 for edge in cg.graph if edge.is_drivable)
    non_drivable_count = len(cg.graph) - drivable_count
    print(f"Drivable edges: {drivable_count}")
    print(f"Non-drivable edges: {non_drivable_count}")
    
    # only drivable edges
    vis = StaticVisualizer(
        cg.nodes,
        [edge for edge in cg.graph if edge.is_drivable],
        title="CityGraph Test (Drivable Edges Only)",
        query=cg.query,
        mode="light_nolabels",
        labels_on=False,
        node_radius=1,
        edge_color="#1f77b4",
        edge_thickness=1,
        landmarks="MSU-IIT, Robinsons, Tibanga, Tambo, Tubod",
    )
    vis.export("results/test/city_graph_drivable.png", scale_up=3)
    del vis
"""