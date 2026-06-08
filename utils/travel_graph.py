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
    _base_cache: dict = {}
    _global_search_id: int = 0

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
        self._findShortestJourney_cached = lru_cache(maxsize=16384)(self._findShortestJourney_impl)

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("_findShortestJourney_cached", None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._findShortestJourney_cached = lru_cache(maxsize=16384)(self._findShortestJourney_impl)

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
        cache_key = (
            id(self.cg),
            self.walk_wt,
            self.ride_wt,
            self.wait_wt,
            self.transfer_wt,
            self.direct_wt,
            self.alight_wt
        )

        if cache_key not in TravelGraph._base_cache:
            # Build and cache base layers
            l1_nodes = {}
            l3_nodes = {}
            for n in self.cg.nodes:
                coord = (n.lon, n.lat)
                n1 = Node(n.lon, n.lat)
                n1.layer = 1
                l1_nodes[coord] = n1

                n3 = Node(n.lon, n.lat)
                n3.layer = 3
                l3_nodes[coord] = n3

            l1_coords = np.array(list(l1_nodes.keys()))
            l1_kdtree = cKDTree(l1_coords)
            
            l3_coords = np.array(list(l3_nodes.keys()))
            l3_kdtree = cKDTree(l3_coords)

            sw_c = count(1)
            ew_c = count(1)
            di_c = count(1)

            base_travel_graph = []
            base_outgoing_edges = defaultdict(list)

            # Base edges for layer 1 and 3
            for e in self.cg.graph:
                c_start = (e.start.lon, e.start.lat)
                c_end = (e.end.lon, e.end.lat)

                walk_weight = self.walk_wt * e.getLength()

                sw_edge = DirEdge(l1_nodes[c_start], l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
                sw_edge.weight = walk_weight
                base_travel_graph.append(sw_edge)
                base_outgoing_edges[sw_edge.start].append(sw_edge)

                ew_edge = DirEdge(l3_nodes[c_start], l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
                ew_edge.weight = walk_weight
                base_travel_graph.append(ew_edge)
                base_outgoing_edges[ew_edge.start].append(ew_edge)

            # Direct edges 1 -> 3
            for coord, n1 in l1_nodes.items():
                n3 = l3_nodes[coord]
                di_edge = DirEdge(n1, n3, True, weight=self.direct_wt, id=f"DI{next(di_c):05d}")
                base_travel_graph.append(di_edge)
                base_outgoing_edges[n1].append(di_edge)

            TravelGraph._base_cache[cache_key] = {
                "l1_nodes": l1_nodes,
                "l3_nodes": l3_nodes,
                "l1_coords": l1_coords,
                "l1_kdtree": l1_kdtree,
                "l3_coords": l3_coords,
                "l3_kdtree": l3_kdtree,
                "travel_graph": base_travel_graph,
                "outgoing_edges": base_outgoing_edges
            }

        # Retrieve static base layers from cache
        cache = TravelGraph._base_cache[cache_key]
        self.l1_nodes = cache["l1_nodes"]
        self.l3_nodes = cache["l3_nodes"]
        self._l1_coords = cache["l1_coords"]
        self._l1_kdtree = cache["l1_kdtree"]
        self._l3_coords = cache["l3_coords"]
        self._l3_kdtree = cache["l3_kdtree"]

        # Copy edge lists (shallow copies to prevent pollution)
        self.travel_graph = list(cache["travel_graph"])
        self._outgoing_edges = defaultdict(list, {k: list(v) for k, v in cache["outgoing_edges"].items()})

        # Layer 2 nodes and edges (route-specific)
        l2_nodes_by_route = defaultdict(dict)
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

        # Collect and initialize node search fields to avoid AttributeError
        all_nodes = set()
        for edge in self.travel_graph:
            all_nodes.add(edge.start)
            all_nodes.add(edge.end)
        for node in all_nodes:
            if "_search_id" not in node.__dict__:
                node.__dict__["_search_id"] = 0
                node.__dict__["_cost"] = 0.0
                node.__dict__["_came_from"] = None
                node.__dict__["_h"] = 0.0
                node.__dict__["_h_search_id"] = 0


    def _snap_node(self, target: Node, layer: int) -> Node:
        # --- O(1) Dictionary Lookup Bypass ---
        coord = (target.lon, target.lat)
        if layer == 1 and coord in self.l1_nodes: return self.l1_nodes[coord]
        if layer == 3 and coord in self.l3_nodes: return self.l3_nodes[coord]
        # ------------------------------------------
        
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
    
    def findShortestJourney(self, start: Node, end: Node) -> list[DirEdge]:
        l1_start = self._snap_node(start, 1)
        l3_end = self._snap_node(end, 3)
        return self._findShortestJourney_cached(l1_start, l3_end)

    def _findShortestJourney_impl(self, l1_start: Node, l3_end: Node) -> list[DirEdge]:
        if l1_start is None or l3_end is None:
            raise ValueError("[TRAVEL GRAPH] Start and end nodes cannot be None.")
            
        import math
        LAT_TO_METERS = 110574.0
        LON_TO_METERS = 110175.0
        end_lat = l3_end.lat
        end_lon = l3_end.lon

        # Pre-bind heap functions and collections lookup
        heappush_fn = heappush
        heappop_fn = heappop
        outgoing_edges_get = self._outgoing_edges.get
        
        walk_wt = self.walk_wt
        ride_wt = self.ride_wt
        wait_wt = self.wait_wt
        crossover_dist = wait_wt / (walk_wt - ride_wt) if walk_wt > ride_wt else float("inf")
        
        # Increment global search ID
        TravelGraph._global_search_id += 1
        search_id = TravelGraph._global_search_id
        
        # Calculate start node heuristic
        dlat = (l1_start.lat - end_lat) * LAT_TO_METERS
        dlon = (l1_start.lon - end_lon) * LON_TO_METERS
        dist_start = math.sqrt(dlat * dlat + dlon * dlon)
        h_start = dist_start * walk_wt if dist_start < crossover_dist else dist_start * ride_wt + wait_wt
        
        start_dict = l1_start.__dict__
        start_dict["_h"] = h_start
        start_dict["_h_search_id"] = search_id

        frontier: list[tuple[float, float, int, Node]] = [(h_start, 0.0, 0, l1_start)]
        
        start_dict["_cost"] = 0.0
        start_dict["_search_id"] = search_id
        start_dict["_came_from"] = None
        
        seq = 0

        while frontier:
            _, current_cost, _, current = heappop_fn(frontier)

            if current is l3_end:
                return self._reconstruct_path(l1_start, l3_end, search_id)

            current_cost_limit = current._cost if current._search_id == search_id else float("inf")
            if current_cost > current_cost_limit:
                continue

            for edge in outgoing_edges_get(current, []):
                next_node = edge.end
                new_cost = current_cost + edge.weight

                old_cost = next_node._cost if next_node._search_id == search_id else float("inf")
                if new_cost < old_cost:
                    next_dict = next_node.__dict__
                    next_dict["_cost"] = new_cost
                    next_dict["_search_id"] = search_id
                    next_dict["_came_from"] = (current, edge)
                    
                    h = next_node._h if next_node._h_search_id == search_id else None
                    if h is None:
                        dlat = (next_node.lat - end_lat) * LAT_TO_METERS
                        dlon = (next_node.lon - end_lon) * LON_TO_METERS
                        dist = math.sqrt(dlat * dlat + dlon * dlon)
                        h = dist * walk_wt if dist < crossover_dist else dist * ride_wt + wait_wt
                        next_dict["_h"] = h
                        next_dict["_h_search_id"] = search_id
                        
                    seq += 1
                    heappush_fn(frontier, (new_cost + h, new_cost, seq, next_node))

        return []

    def _reconstruct_path(self, start: Node, end: Node, search_id: int) -> list[DirEdge]:
        path = []
        current = end
        while current is not start:
            if current._search_id != search_id or current._came_from is None:
                break
            previous, edge = current._came_from
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

        visualizer = TravelGraph3DVisualizer(self.travel_graph, highlight_edges=journey)
        
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

