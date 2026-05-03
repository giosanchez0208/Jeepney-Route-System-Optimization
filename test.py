"""test_travel_graph.py

Tests the static and dynamic TravelGraph construction and visualizes a shortest journey.
Forces resampling of OD pairs until a transit-dependent path is found.
"""

from collections import defaultdict
from random import sample
import sys

from utils.city_graph import CityGraph
from utils.route import Route
from utils.travel_graph import StaticTravelGraph, TravelGraph
from utils.layered_visualizer import LayeredVisualizer

if __name__ == "__main__":
    print("Constructing CityGraph...")
    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
    
    print("Precomputing StaticTravelGraph...")
    stg = StaticTravelGraph(cg)

    print("Generating sample routes...")
    routes = [Route(cg, path=None, od_gen=None) for _ in range(5)]

    print("Constructing dynamic TravelGraph...")
    tg = TravelGraph(stg, routes)
    print(f"TravelGraph configured with {len(tg.travel_graph)} total edges.")

    edge_type_counts = defaultdict(int)
    for edge in tg.travel_graph:
        edge_type_counts[edge.getType()] += 1

    print("TravelGraph stats:")
    for edge_type in ("start_walk", "wait", "ride", "alight", "transfer", "end_walk", "direct"):
        print(f"  {edge_type}: {edge_type_counts.get(edge_type, 0)}")

    print("\nSearching for a journey that requires a jeepney (Layer 2)...")
    
    max_attempts = 5000
    attempts = 0
    journey = []
    start_node = None
    end_node = None

    while attempts < max_attempts:
        attempts += 1
        start_node, end_node = sample(cg.nodes, 2)
        journey = tg.findShortestJourney(start_node, end_node)
        
        if journey and any(e.id.startswith("RI_R") for e in journey):
            break

    if attempts == max_attempts:
        print(f"Failed to find a transit-dependent route after {max_attempts} attempts.")
        print("The generated transit network is too sparse to service random OD pairs.")
        sys.exit(1)

    distance = tg.calculateJourneyDistance(start_node, end_node)
    weight = tg.calculateJourneyWeight(start_node, end_node)
    
    print(f"Path Discovered after {attempts} attempt(s).")
    print(f"Visit points: {len(journey) + 1}")
    print(f"Distance: {distance:.2f} m")
    print(f"Total Weight: {weight:.4f}")
    
    used_routes_indices = set()
    for e in journey:
        if e.id.startswith("RI_R"):
            r_idx = int(e.id.split("_")[1][1:])
            used_routes_indices.add(r_idx)
            
    used_routes = [routes[i] for i in used_routes_indices]
                
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