from collections import defaultdict
from functools import lru_cache
from heapq import heappush, heappop
from itertools import count

from .node import Node
from .directed_edge import DirEdge, _getDistance
from .city_graph import CityGraph
from .route import Route, RouteGenerator

import numpy as np
from scipy.spatial import cKDTree

from PIL import Image
from typing import Optional

class TravelGraph:
    def __init__(self, cg: CityGraph, config: dict, routes: Optional[list[Route]] = None, route_generator: Optional[RouteGenerator] = None, n_routes: int = 5, n_points: int = 4) -> None:
        if not cg:
            raise ValueError("[TRAVEL GRAPH] CityGraph cannot be None.")
        if not config:
            raise ValueError("[TRAVEL GRAPH] Configuration dictionary cannot be None.")
        if routes is None and route_generator is None:
            raise ValueError("[TRAVEL GRAPH] Must provide either 'routes' or 'route_generator'.")
            
        self.cg = cg
        self.config = config
        if config == {}:
            print("[TRAVEL GRAPH] Warning: Empty config provided, using default weights.")
            
        self.walk_wt = config.get("walk_wt", 1.0)
        self.ride_wt = config.get("ride_wt", 1.0)
        self.wait_wt = config.get("wait_wt", 5.0)
        self.transfer_wt = config.get("transfer_wt", 5.0)
        self.direct_wt = config.get("direct_wt", 0.0)
        self.alight_wt = config.get("alight_wt", 0.0)

        if routes is not None:
            self.routes: list[Route] = routes
        else:
            self.routes: list[Route] = self._generate_routes(route_generator, n_routes, n_points)
        
        self.l1_nodes: dict[tuple[float, float], Node] = {}
        self.l3_nodes: dict[tuple[float, float], Node] = {}
        
        self._outgoing_edges: dict[Node, list[DirEdge]] = defaultdict(list)
        self.travel_graph: list[DirEdge] = []
        
        self._construct()

    def _generate_routes(self, route_generator: RouteGenerator, n_routes: int, n_points: int) -> list[Route]:
        routes = []
        for i in range(n_routes):
            try:
                route = route_generator.generate(n_points=n_points)
                routes.append(route)
            except ValueError as e:
                print(f"[TRAVEL GRAPH] Skipping route {i + 1}/{n_routes}: {e}")
        if not routes:
            raise ValueError("[TRAVEL GRAPH] No routes could be generated. Check RouteGenerator configuration.")
        return routes

    def _construct(self) -> None:
        # Layer 1 and 3 nodes
        for n in self.cg.nodes:
            coord = (n.lon, n.lat)
            n1 = Node(n.lon, n.lat)
            n1.layer = 1
            self.l1_nodes[coord] = n1

            n3 = Node(n.lon, n.lat)
            n3.layer = 3
            self.l3_nodes[coord] = n3

        self._l1_coords = np.array(list(self.l1_nodes.keys()))
        self._l1_kdtree = cKDTree(self._l1_coords)
        
        self._l3_coords = np.array(list(self.l3_nodes.keys()))
        self._l3_kdtree = cKDTree(self._l3_coords)

        sw_c = count(1)
        ew_c = count(1)
        di_c = count(1)

        # Base edges for layer 1 and 3
        for e in self.cg.graph:
            c_start = (e.start.lon, e.start.lat)
            c_end = (e.end.lon, e.end.lat)

            walk_weight = self.walk_wt * e.getLength()

            sw_edge = DirEdge(self.l1_nodes[c_start], self.l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
            sw_edge.weight = walk_weight
            self.travel_graph.append(sw_edge)
            self._outgoing_edges[sw_edge.start].append(sw_edge)

            ew_edge = DirEdge(self.l3_nodes[c_start], self.l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
            ew_edge.weight = walk_weight
            self.travel_graph.append(ew_edge)
            self._outgoing_edges[ew_edge.start].append(ew_edge)

        # Direct edges 1 -> 3
        for coord, n1 in self.l1_nodes.items():
            n3 = self.l3_nodes[coord]
            di_edge = DirEdge(n1, n3, True, weight=self.direct_wt, id=f"DI{next(di_c):05d}")
            self.travel_graph.append(di_edge)
            self._outgoing_edges[n1].append(di_edge)

        # Layer 2 nodes and edges
        l2_nodes_by_route: dict[int, dict[tuple[float, float], Node]] = defaultdict(dict)

        for r_idx, r in enumerate(self.routes):
            for e in r.path:
                for n in (e.start, e.end):
                    coord = (n.lon, n.lat)
                    if coord not in l2_nodes_by_route[r_idx]:
                        n2 = Node(n.lon, n.lat)
                        n2.layer = 2
                        l2_nodes_by_route[r_idx][coord] = n2

        ri_c = count(1)
        wa_c = count(1)
        al_c = count(1)
        tr_c = count(1)

        for r_idx, r in enumerate(self.routes):
            l2_nodes = l2_nodes_by_route[r_idx]
            for e in r.path:
                c_start = (e.start.lon, e.start.lat)
                c_end = (e.end.lon, e.end.lat)
                
                ri_edge = DirEdge(l2_nodes[c_start], l2_nodes[c_end], True, id=f"RI_R{r_idx}_{next(ri_c):05d}")
                ri_edge.weight = self.ride_wt * ri_edge.getLength()
                
                self.travel_graph.append(ri_edge)
                self._outgoing_edges[ri_edge.start].append(ri_edge)

        # Connecting edges (WA, AL, TR)
        for r_idx in range(len(self.routes)):
            for coord, n2 in l2_nodes_by_route[r_idx].items():
                n1 = self.l1_nodes.get(coord)
                n3 = self.l3_nodes.get(coord)
                
                if n1 and n3:
                    wa_edge = DirEdge(n1, n2, True, weight=self.wait_wt, id=f"WA{next(wa_c):05d}")
                    self.travel_graph.append(wa_edge)
                    self._outgoing_edges[n1].append(wa_edge)

                    al_edge = DirEdge(n2, n3, True, weight=self.alight_wt, id=f"AL{next(al_c):05d}")
                    self.travel_graph.append(al_edge)
                    self._outgoing_edges[n2].append(al_edge)

                    tr_edge = DirEdge(n3, n2, True, weight=self.transfer_wt, id=f"TR{next(tr_c):05d}")
                    self.travel_graph.append(tr_edge)
                    self._outgoing_edges[n3].append(tr_edge)

        # ── Stitch Graph ──────────────────────────────────────────────────
        from .directed_edge import _stitch
        
        # Save intrinsic weights since _connect mutates weights
        saved_weights = {e: e.weight for e in self.travel_graph}
        
        sw_edges = [e for e in self.travel_graph if e.id[:2] == "SW"]
        ew_edges = [e for e in self.travel_graph if e.id[:2] == "EW"]
        di_edges = [e for e in self.travel_graph if e.id[:2] == "DI"]
        wa_edges = [e for e in self.travel_graph if e.id[:2] == "WA"]
        al_edges = [e for e in self.travel_graph if e.id[:2] == "AL"]
        tr_edges = [e for e in self.travel_graph if e.id[:2] == "TR"]
        
        # Base layer stitching
        _stitch(sw_edges, sw_edges)
        _stitch(sw_edges, di_edges)
        _stitch(sw_edges, wa_edges)
        
        _stitch(di_edges, ew_edges)
        _stitch(al_edges, ew_edges)
        _stitch(al_edges, tr_edges)
        _stitch(ew_edges, ew_edges)
        
        # Route-specific layer 2 stitching
        # To avoid teleporting between routes, we must stitch L2 edges strictly per route.
        for r_idx in range(len(self.routes)):
            # Filter connecting edges that interact with this route's L2 nodes
            l2_nodes_set = set(l2_nodes_by_route[r_idx].values())
            
            r_ri = [e for e in self.travel_graph if e.id.startswith(f"RI_R{r_idx}_")]
            r_wa = [e for e in wa_edges if e.end in l2_nodes_set]
            r_al = [e for e in al_edges if e.start in l2_nodes_set]
            r_tr = [e for e in tr_edges if e.end in l2_nodes_set]
            
            _stitch(r_wa, r_ri)
            _stitch(r_wa, r_al) # In case of direct alight
            
            _stitch(r_ri, r_ri)
            _stitch(r_ri, r_al)
            
            _stitch(r_tr, r_ri)
            _stitch(r_tr, r_al)
            
        # Restore weights
        for e in self.travel_graph:
            e.weight = saved_weights[e]

    def _snap_node(self, target: Node, layer: int) -> Node:
        coords = np.array([[target.lon, target.lat]])
        if layer == 1:
            _, idx = self._l1_kdtree.query(coords)
            matched_coord = tuple(self._l1_coords[idx[0]])
            return self.l1_nodes[matched_coord]
        elif layer == 3:
            _, idx = self._l3_kdtree.query(coords)
            matched_coord = tuple(self._l3_coords[idx[0]])
            return self.l3_nodes[matched_coord]
        else:
            raise ValueError("[TRAVEL GRAPH] Invalid snap layer. Must be 1 or 3.")
    
    @lru_cache(maxsize=4096)
    def findShortestJourney(self, start: Node, end: Node) -> list[DirEdge]:
        if start is None or end is None:
            raise ValueError("[TRAVEL GRAPH] Start and end nodes cannot be None.")
            
        l1_start = self._snap_node(start, 1)
        l3_end = self._snap_node(end, 3)

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        
        h_cache = {}
        min_wt = min(self.walk_wt, self.ride_wt)
        def get_h(n: Node) -> float:
            if n not in h_cache:
                h_cache[n] = _getDistance(n, l3_end) * min_wt
            return h_cache[n]

        heappush(frontier, (get_h(l1_start), 0.0, next(sequence), l1_start))
        came_from = {}
        cost_so_far = {l1_start: 0.0}

        while frontier:
            _, current_cost, _, current = heappop(frontier)

            if current == l3_end:
                return self._reconstruct_path(came_from, l1_start, l3_end)

            if current_cost > cost_so_far.get(current, float("inf")):
                continue

            for edge in self._outgoing_edges.get(current, []):
                next_node = edge.end
                new_cost = current_cost + edge.weight

                if new_cost < cost_so_far.get(next_node, float("inf")):
                    cost_so_far[next_node] = new_cost
                    came_from[next_node] = (current, edge)
                    priority = new_cost + get_h(next_node)
                    heappush(frontier, (priority, new_cost, next(sequence), next_node))

        return []

    def _reconstruct_path(self, came_from: dict[Node, tuple[Node, DirEdge]], start: Node, end: Node) -> list[DirEdge]:
        path = []
        current = end
        while current != start:
            previous, edge = came_from[current]
            path.append(edge)
            current = previous
        path.reverse()
        return path

    def calculateJourneyDistance(self, start: Node, end: Node) -> float:
        path = self.findShortestJourney(start, end)
        return sum(e.getLength() for e in path if e.id[:2] in {"SW", "RI", "EW"})

    def calculateJourneyWeight(self, start: Node, end: Node) -> float:
        if start is None or end is None:
            return 0.0
            
        l1_start = self._snap_node(start, 1)
        l3_end = self._snap_node(end, 3)

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        
        h_cache = {}
        min_wt = min(self.walk_wt, self.ride_wt)
        def get_h(n: Node) -> float:
            if n not in h_cache:
                h_cache[n] = _getDistance(n, l3_end) * min_wt
            return h_cache[n]

        heappush(frontier, (get_h(l1_start), 0.0, next(sequence), l1_start))
        cost_so_far = {l1_start: 0.0}

        while frontier:
            _, current_cost, _, current = heappop(frontier)

            if current == l3_end:
                return current_cost

            if current_cost > cost_so_far.get(current, float("inf")):
                continue

            for edge in self._outgoing_edges.get(current, []):
                next_node = edge.end
                new_cost = current_cost + edge.weight

                if new_cost < cost_so_far.get(next_node, float("inf")):
                    cost_so_far[next_node] = new_cost
                    priority = new_cost + get_h(next_node)
                    heappush(frontier, (priority, new_cost, next(sequence), next_node))

        return 0.0

    def draw(
        self,
        context: tuple[tuple[float, float], tuple[float, float]],
        image: 'Image.Image',
        display_walk: bool = False,
        display_wait: bool = False,
        display_ride: bool = False,
        display_alight: bool = False,
        display_end_walk: bool = False,
        display_transfer: bool = False,
        display_direct: bool = False,
        journey: Optional[list[DirEdge]] = None,
    ) -> 'Image.Image':
        if image.width != image.height:
            raise ValueError("[TRAVEL GRAPH] Image must be square.")

        img = image.copy()
        BASE_EDGE_WIDTH = 2
        RIDE_EDGE_WIDTH = 3
        TRANSITION_NODE_RADIUS = 2
        JOURNEY_EDGE_WIDTH = 5
        JOURNEY_TRANSITION_RADIUS = 3

        ROUTE_PALETTE = ["#FF6B6B", "#FFD93D", "#6BCB77", "#4D96FF", "#C77DFF", "#E63946", "#F4A261", "#E76F51", "#2A9D8F", "#0077B6", "#9C27B0", "#FF9F1C", "#00B4D8", "#388E3C", "#F50057", "#FF5252", "#FB8500", "#4CAF50", "#1E88E5", "#7B1FA2", "#D90429", "#FFB703", "#0096C7", "#00C9A7", "#3F51B5", "#673AB7", "#C51162", "#795548", "#607D8B", "#455A64"]
        EDGE_COLORS = {
            "SW": "#7EB8DA", "EW": "#7ECFC0",
            "WA": "#FFB74D", "AL": "#81C784", "TR": "#E57373", "DI": "#CE93D8",
        }

        FLAG_MAP = {
            "SW": display_walk, "WA": display_wait, "RI": display_ride,
            "AL": display_alight, "EW": display_end_walk,
            "TR": display_transfer, "DI": display_direct,
        }

        SAME_LAYER = {"SW", "RI", "EW"}

        # ── Base layer rendering ──────────────────────────────────────
        for e in self.travel_graph:
            prefix = e.id[:2]
            if not FLAG_MAP.get(prefix, False):
                continue

            if prefix in SAME_LAYER:
                if prefix == "RI":
                    r_idx = int(e.id.split("_")[1][1:])
                    c = ROUTE_PALETTE[r_idx % len(ROUTE_PALETTE)]
                    img = e.draw(context, img, color=c, width=RIDE_EDGE_WIDTH)
                else:
                    img = e.draw(context, img, color=EDGE_COLORS[prefix], width=BASE_EDGE_WIDTH)
            else:
                img = e.start.draw(context, img, color=EDGE_COLORS[prefix], radius=TRANSITION_NODE_RADIUS)

        # ── Journey overlay ───────────────────────────────────────────
        if journey:
            for e in journey:
                prefix = e.id[:2]
                if not FLAG_MAP.get(prefix, False):
                    continue

                if prefix in SAME_LAYER:
                    img = e.draw(context, img, color="#FF0000", width=JOURNEY_EDGE_WIDTH)
                else:
                    img = e.start.draw(context, img, color="#FF0000", radius=JOURNEY_TRANSITION_RADIUS)

        return img

    def create_3d(
        self,
        journey: Optional[list[DirEdge]] = None,
        display_walk: bool = True,
        display_wait: bool = True,
        display_ride: bool = True,
        display_alight: bool = True,
        display_end_walk: bool = True,
        display_transfer: bool = True,
        display_direct: bool = True,
        labels_on: bool = False,
        legend_on: bool = True,
        nodes_on: bool = False,
    ) -> 'Image.Image':
        from .travel_graph_3d_vis import TravelGraph3DVisualizer

        visualizer = TravelGraph3DVisualizer(self, journey=journey)
        return visualizer.draw(
            display_walk=display_walk,
            display_wait=display_wait,
            display_ride=display_ride,
            display_alight=display_alight,
            display_end_walk=display_end_walk,
            display_transfer=display_transfer,
            display_direct=display_direct,
            labels_on=labels_on,
            legend_on=legend_on,
            nodes_on=nodes_on,
        )

