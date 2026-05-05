"""test.py

Phase D Memetic Architecture Diagnostic.
Tests the Topological Hub Exchange against two entirely independent Route Systems,
using matured pheromone matrices, and evaluates genetic inheritance and performance.
"""

import yaml
import random
from pathlib import Path
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.jeep_system import FleetAllocator
from utils.local_search import ACOLocalSearch
from utils.genetic import Chromosome, MemeticAlgorithm
from utils.route import Route
from utils.visualizer import StaticVisualizer

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def export_chromosome_visual(chrom: Chromosome, filename: str, title: str, bounds: tuple):
    p_data = {}
    if chrom.pheromones:
        for e, t in chrom.pheromones.tau.items():
            if t > 0: p_data[(e.start.lon, e.start.lat, e.end.lon, e.end.lat)] = t
            
    vis = StaticVisualizer(
        bounds=bounds, 
        title=title, 
        routes=chrom.routes, 
        pheromones=p_data, 
        mode="dark_nolabels"
    )
    vis.export(filename, scale_up=1)

def construct_matured_chromosome(cg, routes, target_fleet):
    phero = PheromoneMatrix(all_edges=cg.graph)
    alloc = FleetAllocator.allocate_by_mohring(target_fleet, routes, phero, cg)
    chrom = Chromosome(routes=routes, allocation=alloc, pheromones=phero)
    
    for r in routes:
        for edge in r.path:
            chrom.pheromones.tau[edge] = chrom.pheromones.tau.get(edge, 0) + 100.0
            
    report = FleetAllocator.evaluate_allocation(alloc, chrom.pheromones)
    chrom.cost = sum(m["headway"] for m in report.values()) / len(report)
    return chrom

def generate_independent_routes(cg, count, min_edges=30):
    routes = []
    valid_nodes = cg.nodes
    while len(routes) < count:
        start = random.choice(valid_nodes)
        end = random.choice(valid_nodes)
        path = cg.findShortestPath(start, end)
        if path and len(path) >= min_edges:
            routes.append(Route(path=path, city_graph=cg))
    return routes

def run_diagnostics():
    CITY = "Iligan City, Philippines"
    TOTAL_FLEET = 100
    ROUTE_SUBSET_SIZE = 5

    out_dir = Path("results/phase_d_memetic")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print(" BOOTING PHASE D: MATURED CHROMOSOME DIAGNOSTIC")
    print("="*60)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    bounds = sim.bounds
    
    cg = sim.jeep_system.routes[0].cg
    local_search = ACOLocalSearch(cg, p_local=1.0, base_window_size=15)
    memetic_algo = MemeticAlgorithm(cg, local_search, target_route_count=ROUTE_SUBSET_SIZE)
    
    print("[*] Generating Parent A (Urban Baseline)...")
    parent_a_routes = [Route(path=r.path[:], city_graph=cg) for r in sim.jeep_system.routes[:ROUTE_SUBSET_SIZE]]
    parent_a = construct_matured_chromosome(cg, parent_a_routes, TOTAL_FLEET)
    export_chromosome_visual(parent_a, str(out_dir / "01_parent_a.png"), "Parent A (Hub Core)", bounds)

    print("[*] Generating Parent B (Independent Spatial Anchors)...")
    parent_b_routes = generate_independent_routes(cg, ROUTE_SUBSET_SIZE)
    parent_b = construct_matured_chromosome(cg, parent_b_routes, TOTAL_FLEET)
    export_chromosome_visual(parent_b, str(out_dir / "02_parent_b.png"), "Parent B (Periphery)", bounds)

    print("\n[*] Evaluating Genetic Divergence (A vs B)...")
    divergence = memetic_algo.calculate_system_divergence(parent_a, parent_b)
    print(f"    System Trajectory Fréchet: {divergence['frechet_divergence']:<10.6f}")
    print(f"    Pheromone Belief Space MSE: {divergence['pheromone_mse']:<10.2f}")

    print("\n[*] Executing Topological Hub Exchange Crossover...")
    child_routes = memetic_algo.crossover_topological_hub(parent_a, parent_b)
    print(f"    Inherited Route Count: {len(child_routes)}")
    
    print("[*] Executing Fitness-Weighted Pheromone Inheritance...")
    child_phero = memetic_algo.inherit_pheromones(parent_a, parent_b)
    child_alloc = FleetAllocator.allocate_by_mohring(TOTAL_FLEET, child_routes, child_phero, cg)
    child = Chromosome(routes=child_routes, allocation=child_alloc, pheromones=child_phero)
    
    child_report = FleetAllocator.evaluate_allocation(child_alloc, child.pheromones)
    child.cost = sum(m["headway"] for m in child_report.values()) / len(child_report)

    print("\n[*] Evaluating Performance Metrics (Cost Proxy)...")
    print(f"    Parent A Cost: {parent_a.cost:.2f}")
    print(f"    Parent B Cost: {parent_b.cost:.2f}")
    print(f"    Child Cost:    {child.cost:.2f}")

    print("\n[*] Evaluating Genetic Divergence (Child vs Parent A)...")
    child_div = memetic_algo.calculate_system_divergence(parent_a, child)
    print(f"    System Trajectory Fréchet: {child_div['frechet_divergence']:<10.6f}")
    print(f"    Pheromone Belief Space MSE: {child_div['pheromone_mse']:<10.2f}")
    
    export_chromosome_visual(child, str(out_dir / "03_child_chromosome.png"), "Child Chromosome (Synthesis)", bounds)
    print(f"\n[*] Diagnostics complete. Visuals exported to {out_dir}")

if __name__ == "__main__":
    run_diagnostics()