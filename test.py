"""test.py

Tests the LiveVisualizer with multiple routes and multiple staggered Jeeps.
Prints the nodes passed by each Jeep in real-time.
"""

from utils.city_graph import CityGraph
from utils.route import Route
from utils.jeep import Jeep
from utils.visualizer import LiveVisualizer

class LoggingJeep(Jeep):
    """A wrapper for the Jeep class that prints to the console whenever it passes a node."""
    def __init__(self, route: Route, currPos: tuple[float, float], speed: float, name: str) -> None:
        super().__init__(route, currPos, speed)
        self.name = name

    def update(self) -> None:
        super().update()
        passed_nodes = self.nodes_passed_this_frame()
        if passed_nodes:
            for node in passed_nodes:
                print(f"[{self.name}] crossed node {node.id}")

def test_live_visualizer_multi() -> None:
    area = "Iligan City, Lanao del Norte, Philippines"
    
    print("Constructing CityGraph (this may take a moment)...")
    cg = CityGraph(area)
    
    print("Generating 2 random looping Routes...")
    routes = [Route(cg, path=None, od_gen=None) for _ in range(2)]
    
    print("Initializing 3 Jeeps per Route (staggered spacing)...")
    jeeps = []
    
    for r_idx, route in enumerate(routes):
        n_edges = len(route.path)
        
        # Stagger jeeps at ~0%, ~33%, and ~66% along the route length
        spacing_indices = [0, max(1, n_edges // 3), max(2, 2 * n_edges // 3)]
        
        for j_idx, edge_idx in enumerate(spacing_indices):
            start_node = route.path[edge_idx].start
            name = f"Route {r_idx+1} - Jeep {j_idx+1}"
            
            # Speed of 15.0m per tick = 300m/s. Fast enough to track visually.
            j = LoggingJeep(route, currPos=(start_node.lat, start_node.lon), speed=15.0, name=name)
            jeeps.append(j)
    
    print(f"Launching Live Visualizer with {len(routes)} routes and {len(jeeps)} jeeps...")
    print("Close the Tkinter window to terminate the simulation.")
    
    vis = LiveVisualizer(
        area_query=area,
        title="Multi-Jeep Live Tracking Simulation",
        nodes=[], 
        edges=[e for e in cg.graph if e.is_drivable],
        routes=routes,
        jeeps=jeeps,
        passengers=[],
        mode="light_nolabels",
        sim_tick_rate=0.05, 
        render_fps=30
    )

    vis.display()
    
    print("\nSimulation terminated gracefully.")

if __name__ == "__main__":
    test_live_visualizer_multi()