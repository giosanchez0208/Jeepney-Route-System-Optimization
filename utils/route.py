"""route.py

Route(city_graph: CityGraph, path: Optional[list[DirEdge]] = None, od_gen: Optional[TrafficAwareODGenerator] = None) -> None creates cg: CityGraph and path: list[DirEdge].
_generate_route_path(city_graph: CityGraph, od_gen: Optional[TrafficAwareODGenerator] = None) -> list[DirEdge] returns a traffic-aware (or random) closed route path from four sampled nodes.
"""

from typing import Optional
from random import sample

from .node import Node
from .directed_edge import DirEdge
from .city_graph import CityGraph
from .od_generator import TrafficAwareODGenerator
    
class Route:
    def __init__(self, city_graph: CityGraph, path: Optional[list[DirEdge]] = None, od_gen: Optional[TrafficAwareODGenerator] = None) -> None:
        self.cg = city_graph
        if path is not None:
            self.path = path
        else:
            self.path = _generate_route_path(self.cg, od_gen)

### HELPER FUNCTIONS ###

def _generate_route_path(city_graph: CityGraph, od_gen: Optional[TrafficAwareODGenerator] = None) -> list[DirEdge]:
    
    # choose four nodes using the OD generator if provided, else fallback to uniform random
    if od_gen is not None:
        nodes = od_gen.generate_origins(n_points=4)
    else:
        nodes = sample(city_graph.nodes, 4)
    
    # generate paths between the nodes
    a = city_graph.findShortestPath(nodes[0], nodes[1])
    b = city_graph.findShortestPath(nodes[1], nodes[2])
    c = city_graph.findShortestPath(nodes[2], nodes[3])
    d = city_graph.findShortestPath(nodes[3], nodes[0])
    
    # concatenate the paths
    path = a + b + c + d
    return path


if __name__ == "__main__":
    from visualizer import StaticVisualizer, DynamicVisualizer

    print("Constructing CityGraph...")
    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
    
    print("Setting up OD Generator...")
    # Adjust path if your CSV is located elsewhere
    od_gen = TrafficAwareODGenerator(cg, "data/iligan_node_with_traffic_data.csv")
    
    print("Generating traffic-aware routes...")
    routes = [Route(cg, path=None, od_gen=od_gen) for _ in range(20)]
    
    route_visualizers = [
        StaticVisualizer(
            cg.nodes,
            cg.graph,
            title=f"Traffic-Aware Route {index + 1}",
            query=cg.query,
            mode="light_nolabels",
            labels_on=False,
            node_radius=1,
            edge_color="#d6d6d6",
            edge_thickness=0.2,
            landmarks="MSU-IIT, Robinsons, Tibanga, Tambo, Tubod",
            Routes=[route],
            route_thickness=2.0,
        )
        for index, route in enumerate(routes)
    ]

    print(f"CityGraph: {cg.info()}")
    print(f"Routes: {len(routes)}")
    print(f"Route edges: {sum(len(route.path) for route in routes)}")

    vis = DynamicVisualizer(route_visualizers, title="Traffic-Aware Routes Smoke Test")
    vis.export("results/test/ta_routes_test.gif", mode="light_nolabels", fps=1, scale_up=4)
    print("Exported to results/test/ta_routes_test.gif")