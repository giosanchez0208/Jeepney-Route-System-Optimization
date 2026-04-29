"""travel_graph.py

WALK_WT: float, RIDE_WT: float, WAIT_WT: float, TRANSFER_WT: float, DIRECT_WT: float, and ALIGHT_WT: float store edge weights.
TravelGraph(cg: CityGraph, routes: list[Route]) -> None creates cg: CityGraph, routes: list[Route], travel_graph: list[DirEdge], and _outgoing_edges: dict[Node, list[DirEdge]].
_construct(self) -> None builds the layered travel graph.
findShortestJourney(self, start: Node, end: Node) -> list[DirEdge] returns the best journey path or an empty list.
_reconstruct_path(self, came_from: dict[Node, tuple[Node, DirEdge]], start: Node, end: Node) -> list[DirEdge] returns the recovered journey path.
calculateJourneyDistance(self, start: Node, end: Node) -> float returns the total walk, ride, and walk distance in meters.
calculateJourneyWeight(self, start: Node, end: Node) -> float returns the summed journey weight.
"""

from collections import defaultdict
from heapq import heappush, heappop
from itertools import count

from node import Node
from directed_edge import DirEdge
from city_graph import CityGraph
from route import Route

WALK_WT = 0.0142
RIDE_WT = 0.0071
WAIT_WT = 8.5
TRANSFER_WT = 14.2
DIRECT_WT = 0.0
ALIGHT_WT = 0.0

class TravelGraph:
    def __init__(self, cg: CityGraph, routes: list[Route]) -> None:
        self.cg = cg
        self.routes = routes
        self.travel_graph: list[DirEdge] = []
        self._outgoing_edges: dict[Node, list[DirEdge]] = defaultdict(list)
        self._construct()

    def _construct(self) -> None:
        l1_nodes: dict[tuple[float, float], Node] = {}
        l2_nodes_by_route: dict[int, dict[tuple[float, float], Node]] = defaultdict(dict)
        l3_nodes: dict[tuple[float, float], Node] = {}

        for n in self.cg.nodes:
            coord = (n.lon, n.lat)
            n1 = Node(n.lon, n.lat)
            n1.layer = 1
            l1_nodes[coord] = n1

            n3 = Node(n.lon, n.lat)
            n3.layer = 3
            l3_nodes[coord] = n3

        for r_idx, r in enumerate(self.routes):
            for e in r.path:
                for n in (e.start, e.end):
                    coord = (n.lon, n.lat)
                    if coord not in l2_nodes_by_route[r_idx]:
                        n2 = Node(n.lon, n.lat)
                        n2.layer = 2
                        l2_nodes_by_route[r_idx][coord] = n2

        sw_c = count(1); ri_c = count(1); ew_c = count(1)
        di_c = count(1); al_c = count(1); tr_c = count(1); wa_c = count(1)

        sw_edges = []
        ew_edges = []
        ride_edges = []
        di_edges = []
        al_edges = []
        tr_edges = []
        wa_edges = []

        # Layer 1 and Layer 3 Walking Edges
        for e in self.cg.graph:
            c_start = (e.start.lon, e.start.lat)
            c_end = (e.end.lon, e.end.lat)

            sw_edge = DirEdge(l1_nodes[c_start], l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
            sw_edge.weight = WALK_WT * sw_edge.getLength()
            sw_edges.append(sw_edge)

            ew_edge = DirEdge(l3_nodes[c_start], l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
            ew_edge.weight = WALK_WT * ew_edge.getLength()
            ew_edges.append(ew_edge)

        # Layer 2 Riding Edges
        for r_idx, r in enumerate(self.routes):
            r_edges = []
            l2_nodes = l2_nodes_by_route[r_idx]
            for e in r.path:
                c_start = (e.start.lon, e.start.lat)
                c_end = (e.end.lon, e.end.lat)
                ri_edge = DirEdge(l2_nodes[c_start], l2_nodes[c_end], True, id=f"RI{next(ri_c):05d}")
                ri_edge.weight = RIDE_WT * ri_edge.getLength()
                r_edges.append(ri_edge)
                ride_edges.append(ri_edge)

            for i in range(len(r_edges) - 1):
                r_edges[i].next_edges.append(r_edges[i+1].id)
            if r_edges and r_edges[-1].end == r_edges[0].start:
                r_edges[-1].next_edges.append(r_edges[0].id)

        # Inter-layer Edges
        for coord, n1 in l1_nodes.items():
            n3 = l3_nodes[coord]
            di_edges.append(DirEdge(n1, n3, True, weight=DIRECT_WT, id=f"DI{next(di_c):05d}"))

            for r_idx in range(len(self.routes)):
                if coord in l2_nodes_by_route[r_idx]:
                    n2 = l2_nodes_by_route[r_idx][coord]
                    wa_edges.append(DirEdge(n1, n2, True, weight=WAIT_WT, id=f"WA{next(wa_c):05d}"))
                    al_edges.append(DirEdge(n2, n3, True, weight=ALIGHT_WT, id=f"AL{next(al_c):05d}"))
                    tr_edges.append(DirEdge(n3, n2, True, weight=TRANSFER_WT, id=f"TR{next(tr_c):05d}"))

        # Lookups for Stitching
        l1_out = defaultdict(list)
        l2_out = defaultdict(list)
        l3_out = defaultdict(list)
        ri_out = defaultdict(list)

        for e in sw_edges + wa_edges + di_edges: l1_out[e.start].append(e)
        for e in ew_edges + tr_edges: l3_out[e.start].append(e)
        for e in al_edges: l2_out[e.start].append(e)
        for e in ride_edges: ri_out[e.start].append(e)

        # Cross-layer Stitching
        for e in sw_edges: e.next_edges.extend([out.id for out in l1_out[e.end]])
        for e in ew_edges: e.next_edges.extend([out.id for out in l3_out[e.end]])
        for e in di_edges: e.next_edges.extend([out.id for out in l3_out[e.end]])
        for e in al_edges: e.next_edges.extend([out.id for out in l3_out[e.end]])
        for e in wa_edges: e.next_edges.extend([out.id for out in ri_out[e.end]])
        for e in tr_edges: e.next_edges.extend([out.id for out in ri_out[e.end]])
        for e in ride_edges: e.next_edges.extend([out.id for out in l2_out[e.end]])

        self.travel_graph = sw_edges + ew_edges + ride_edges + di_edges + al_edges + tr_edges + wa_edges
        for e in self.travel_graph:
            self._outgoing_edges[e.start].append(e)

        # Free memory constraints
        del l1_nodes, l2_nodes_by_route, l3_nodes
        del sw_edges, ew_edges, ride_edges, di_edges, al_edges, tr_edges, wa_edges
        del l1_out, l2_out, l3_out, ri_out

    def findShortestJourney(self, start: Node, end: Node) -> list[DirEdge]:
        l1_start = next((n for n in self._outgoing_edges.keys() if n.layer == 1 and n.lon == start.lon and n.lat == start.lat), None)
        l3_end = next((n for n in self._outgoing_edges.keys() if n.layer == 3 and n.lon == end.lon and n.lat == end.lat), None)

        if not l1_start or not l3_end:
            return []

        frontier: list[tuple[float, float, int, Node]] = []
        sequence = count()
        heappush(frontier, (0.0, 0.0, next(sequence), l1_start))

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
                    priority = new_cost
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
        path = self.findShortestJourney(start, end)
        return sum(e.weight for e in path)

if __name__ == "__main__":
    from random import sample
    from layered_visualizer import LayeredVisualizer

    print("Constructing CityGraph...")
    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")

    print("Generating sample routes...")
    routes = [Route(cg, None) for _ in range(5)]

    print("Constructing TravelGraph...")
    tg = TravelGraph(cg, routes)
    print(f"TravelGraph configured with {len(tg.travel_graph)} total edges.")

    start_node, end_node = sample(cg.nodes, 2)
    print("\nFinding shortest journey...")
    journey = tg.findShortestJourney(start_node, end_node)

    if journey:
        distance = tg.calculateJourneyDistance(start_node, end_node)
        weight = tg.calculateJourneyWeight(start_node, end_node)
        print(f"Path Discovered! Visit points: {len(journey) + 1}")
        print(f"Distance: {distance:.2f} m")
        print(f"Total Weight: {weight:.4f}")
        
        journey_layer_2_coords = [
            (e.start.lon, e.start.lat, e.end.lon, e.end.lat) 
            for e in journey if e.id.startswith("RI")
        ]
        
        used_routes = []
        if journey_layer_2_coords:
            assigned_indices = set()
            for j_coord in journey_layer_2_coords:
                for idx, route in enumerate(routes):
                    if any((e.start.lon, e.start.lat, e.end.lon, e.end.lat) == j_coord for e in route.path):
                        assigned_indices.add(idx)
                        break 
            
            used_routes = [routes[i] for i in assigned_indices]
                    
        print(f"Used {len(used_routes)} route(s) during journey. Generating visualization...")
        
        vis = LayeredVisualizer(
            cg,
            journey,
            title="TravelGraph Journey",
            labels_on=False,
            node_radius=1,
            edge_color="#bdbdbd",
            edge_thickness=1,
            journey_color="#d62728",
            journey_thickness=2,
            Routes=used_routes,
            nodes_on=False
        )
        vis.export("results/test/travel_graph_layered.png", scale_up=3)
        print("Exported to results/test/travel_graph_layered.png")

    else:
        print("No route available between nodes.")
