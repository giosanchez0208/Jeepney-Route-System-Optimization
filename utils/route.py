from node import Node
from directed_edge import DirEdge
from city_graph import CityGraph
from random import sample
    
class Route:
    def __init__(self, city_graph: CityGraph, path: list[DirEdge]) -> None:
        self.cg = city_graph
        if path is not None:
            self.path = path
        else:
            self.path = _generate_route_path(self.cg)

### HELPER FUNCTIONS ###

def _generate_route_path(city_graph: CityGraph) -> list[DirEdge]:
    
    # choose four random nodes
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

    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
    routes = [Route(cg, None) for _ in range(20)]
    route_visualizers = [
        StaticVisualizer(
            cg.nodes,
            cg.graph,
            title=f"Route {index + 1}",
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

    vis = DynamicVisualizer(route_visualizers, title="Routes Smoke Test")
    vis.export("results/test/routes_test.gif", mode="light_nolabels", fps=1, scale_up=4)

