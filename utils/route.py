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
    from visualizer import StaticVisualizer

    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
    route = Route(cg, None)

    print(f"CityGraph: {cg.info()}")
    print(f"Route edges: {len(route.path)}")

    vis = StaticVisualizer(
        cg.nodes,
        route.path,
        title="Route Smoke Test",
        query=cg.query,
        mode="light_nolabels",
        labels_on=False,
        node_radius=1,
        edge_color="#d62728",
        edge_thickness=1,
        landmarks="MSU-IIT, Robinsons, Tibanga, Tambo, Tubod",
    )
    
    vis.export("results/test/route_test.png", scale_up=6)

