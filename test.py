"""test_vis.py

A lightweight diagnostic script to test the new LiveVisualizer 
without running the full simulation orchestrator.
"""

import random
import yaml
from utils.city_graph import CityGraph
from utils.route import Route
from utils.jeep import Jeep
from utils.visualizer import LiveVisualizer, Passenger

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def main():
    CITY = "Iligan City, Philippines"
    
    print("[*] Loading Configurations...")
    config = load_config()

    print("[*] Initializing Base City Graph...")
    cg = CityGraph(CITY)

    print("[*] Generating 1 random test route...")
    # By not passing od_gen, it defaults to a completely random 4-node walk
    route = Route(cg) 

    print("[*] Deploying 2 Jeeps...")
    start_node = route.path[0].start
    # Give them different speeds so you can see them separate
    jeep1 = Jeep(route, currPos=(start_node.lat, start_node.lon), speed=15.0)
    jeep2 = Jeep(route, currPos=(start_node.lat, start_node.lon), speed=25.0)
    
    # Space them out slightly at tick 0
    for _ in range(10): jeep2.update() 
    
    jeeps = [jeep1, jeep2]

    print("[*] Generating 50 static dummy Passengers...")
    random_nodes = random.sample(cg.nodes, 50)
    passengers = [Passenger(curr_lon=n.lon, curr_lat=n.lat) for n in random_nodes]

    print(f"\n[*] Launching LiveVisualizer in Standalone Mode...")
    
    # Grab the precise geographic square from configs.yaml
    bounds = tuple(config.get("CITY_BOUNDS", [8.1500, 8.3000, 124.1500, 124.3000]))
    
    vis = LiveVisualizer(
        bounds=bounds,
        title="LiveVisualizer Standalone Test",
        nodes=[], # Opt-out of rendering nodes
        edges=[e for e in cg.graph if e.is_drivable], # Render base streets
        routes=[route],
        jeeps=jeeps,
        passengers=passengers, 
        system_manager=None, # Run without the Simulation orchestrator
        mode="dark_nolabels"
    )
    
    vis.display()

if __name__ == "__main__":
    main()