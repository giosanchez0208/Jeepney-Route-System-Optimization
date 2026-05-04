"""test.py

Tests the LiveVisualizer with one Route, one Passenger, and the centralized JeepSystem.
The passenger is continuously regenerated until their journey necessitates a ride edge.
"""

from utils.city_graph import CityGraph
from utils.route import Route
from utils.jeep import Jeep
from utils.passenger import Passenger
from utils.jeep_system import JeepSystem
from utils.visualizer import LiveVisualizer
from utils.travel_graph import StaticTravelGraph, TravelGraph
from utils.od_generator import TrafficAwareODGenerator

def test_passenger_system() -> None:
    area = "Iligan City, Lanao del Norte, Philippines"
    
    print("Constructing CityGraph (this may take a moment)...")
    cg = CityGraph(area)
    
    print("Initializing StaticTravelGraph...")
    stg = StaticTravelGraph(cg)
    
    print("Loading OD Generator...")
    od_gen = TrafficAwareODGenerator(cg, "data/iligan_node_with_traffic_data.csv")
    
    print("Generating 1 random Route...")
    route = Route(cg, od_gen=od_gen)
    
    print("Constructing TravelGraph...")
    tg = TravelGraph(stg, [route])
    
    print("Searching for a valid passenger journey involving a jeep ride...")
    passenger = None
    attempts = 0
    
    while True:
        attempts += 1
        points = od_gen.generate_origins(n_points=2)
        journey = tg.findShortestJourney(points[0], points[1])
        
        # Check if the journey uses the route we generated
        if any(e.id.startswith("RI") for e in journey):
            print(f"Success! Generated a journey with a ride after {attempts} attempts.")
            
            # Speed is set relatively high (15.0m/tick walking) so you aren't waiting forever 
            # for the passenger to walk to the waiting shed.
            passenger = Passenger((points[0].lat, points[0].lon), journey, speed=15.0)
            break
            
    print("Initializing Jeep and binding to JeepSystem...")
    start_node = route.path[0].start
    
    # Fast jeep speed so it completes its route quickly and meets the passenger
    jeep = Jeep(route, currPos=(start_node.lat, start_node.lon), speed=25.0)
    
    system = JeepSystem([jeep], [route], weight_tolerance=50.0)
    system.add_passenger(passenger)
    
    print("Launching Live Visualizer... Close the Tkinter window to terminate.")
    
    vis = LiveVisualizer(
        area_query=area,
        title="Passenger & JeepSystem Integration Test",
        nodes=[],
        edges=[e for e in cg.graph if e.is_drivable],
        routes=[route],
        jeeps=[jeep],
        passengers=[passenger],
        system_manager=system,
        mode="light_nolabels",
        sim_tick_rate=0.05,
        render_fps=30
    )

    vis.display()
    print("\nSimulation terminated gracefully.")

if __name__ == "__main__":
    test_passenger_system()