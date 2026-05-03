"""travel_graph.py

WALK_WT: float, RIDE_WT: float, WAIT_WT: float, TRANSFER_WT: float, DIRECT_WT: float, and ALIGHT_WT: float store edge weights.
StaticTravelGraph(cg: CityGraph) -> None precomputes static walking and direct transfer layers.
TravelGraph(stg: StaticTravelGraph, routes: list[Route]) -> None creates a dynamic graph instance.
findShortestJourney(self, start: Node, end: Node) -> list[DirEdge] returns the best journey path.
calculateJourneyDistance(self, start: Node, end: Node) -> float returns the total walk, ride, and walk distance.
calculateJourneyWeight(self, start: Node, end: Node) -> float returns the summed journey weight using A*.
"""

from collections import defaultdict
from heapq import heappush, heappop
from itertools import count
from pathlib import Path

import yaml

from .node import Node
from .directed_edge import DirEdge, _getDistance
from .city_graph import CityGraph
from .route import Route

_CONSTS_PATH = Path(__file__).with_name("configs").joinpath("consts.yaml")
with _CONSTS_PATH.open("r", encoding="utf-8") as f:
    _CONSTS = yaml.safe_load(f)

WALK_WT = _CONSTS["WALK_WT"]
RIDE_WT = _CONSTS["RIDE_WT"]
WAIT_WT = _CONSTS["WAIT_WT"]
TRANSFER_WT = _CONSTS["TRANSFER_WT"]
DIRECT_WT = _CONSTS["DIRECT_WT"]
ALIGHT_WT = _CONSTS["ALIGHT_WT"]


class StaticTravelGraph:
    def __init__(self, cg: CityGraph) -> None:
        self.cg = cg
        self.l1_nodes: dict[tuple[float, float], Node] = {}
        self.l3_nodes: dict[tuple[float, float], Node] = {}
        
        self._l1_lookup: dict[tuple[float, float], Node] = {}
        self._l3_lookup: dict[tuple[float, float], Node] = {}
        
        self.base_outgoing: dict[Node, list[DirEdge]] = defaultdict(list)
        self.base_edges: list[DirEdge] = []
        
        self._construct()

    def _construct(self) -> None:
        for n in self.cg.nodes:
            coord = (n.lon, n.lat)
            
            n1 = Node(n.lon, n.lat)
            n1.layer = 1
            self.l1_nodes[coord] = n1
            self._l1_lookup[coord] = n1

            n3 = Node(n.lon, n.lat)
            n3.layer = 3
            self.l3_nodes[coord] = n3
            self._l3_lookup[coord] = n3

        sw_c = count(1)
        ew_c = count(1)
        di_c = count(1)

        for e in self.cg.graph:
            c_start = (e.start.lon, e.start.lat)
            c_end = (e.end.lon, e.end.lat)

            walk_weight = WALK_WT * e.getLength()

            sw_edge = DirEdge(self.l1_nodes[c_start], self.l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
            sw_edge.weight = walk_weight
            self.base_edges.append(sw_edge)
            self.base_outgoing[sw_edge.start].append(sw_edge)

            ew_edge = DirEdge(self.l3_nodes[c_start], self.l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
            ew_edge.weight = walk_weight
            self.base_edges.append(ew_edge)
            self.base_outgoing[ew_edge.start].append(ew_edge)

        for coord, n1 in self.l1_nodes.items():
            n3 = self.l3_nodes[coord]
            di_edge = DirEdge(n1, n3, True, weight=DIRECT_WT, id=f"DI{next(di_c):05d}")
            self.base_edges.append(di_edge)
            self.base_outgoing[n1].append(di_edge)


class TravelGraph:
    def __init__(self, stg: StaticTravelGraph, routes: list[Route]) -> None:
        self.stg = stg
        self.routes = routes
        
        self._outgoing_edges = defaultdict(list, {node: list(edges) for node, edges in stg.base_outgoing.items()})
        self.travel_graph: list[DirEdge] = list(stg.base_edges)
        
        self._construct()

    def _construct(self) -> None:
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
                
                # ENCODED ROUTE INDEX IN EDGE ID
                ri_edge = DirEdge(l2_nodes[c_start], l2_nodes[c_end], True, id=f"RI_R{r_idx}_{next(ri_c):05d}")
                ri_edge.weight = RIDE_WT * ri_edge.getLength()
                
                self.travel_graph.append(ri_edge)
                self._outgoing_edges[ri_edge.start].append(ri_edge)

        for r_idx in range(len(self.routes)):
            for coord, n2 in l2_nodes_by_route[r_idx].items():
                n1 = self.stg._l1_lookup.get(coord)
                n3 = self.stg._l3_lookup.get(coord)
                
                if n1 and n3:
                    wa_edge = DirEdge(n1, n2, True, weight=WAIT_WT, id=f"WA{next(wa_c):05d}")
                    self.travel_graph.append(wa_edge)
                    self._outgoing_edges[n1].append(wa_edge)

                    al_edge = DirEdge(n2, n3, True, weight=ALIGHT_WT, id=f"AL{next(al_c):05d}")
                    self.travel_graph.append(al_edge)
                    self._outgoing_edges[n2].append(al_edge)

                    tr_edge = DirEdge(n3, n2, True, weight=TRANSFER_WT, id=f"TR{next(tr_c):05d}")
                    self.travel_graph.append(tr_edge)
                    self._outgoing_edges[n3].append(tr_edge)

    def findShortestJourney(self, start: Node, end: Node) -> list[DirEdge]:
        l1_start = self.stg._l1_lookup.get((start.lon, start.lat))
        l3_end = self.stg._l3_lookup.get((end.lon, end.lat))

        if not l1_start or not l3_end:
            return []

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        
        h_cache = {}
        min_wt = min(WALK_WT, RIDE_WT)
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
        l1_start = self.stg._l1_lookup.get((start.lon, start.lat))
        l3_end = self.stg._l3_lookup.get((end.lon, end.lat))

        if not l1_start or not l3_end:
            return 0.0

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        
        h_cache = {}
        min_wt = min(WALK_WT, RIDE_WT)
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