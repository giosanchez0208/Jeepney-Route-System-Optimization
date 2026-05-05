"""test.py

Intensity Scaling and Similarity Evaluation Grid.
Generates an evaluation matrix showing the impact of varying mutation intensities 
on a single baseline route, backed by the Discrete Fréchet Distance metric.
"""

import yaml
import random
from pathlib import Path
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.local_search import ACOLocalSearch
from utils.visualizer import StaticVisualizer
from utils.route import Route

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def export_visual(filename: str, title: str, route: Route, bounds: tuple, pheromones: PheromoneMatrix = None):
    p_data = {}
    if pheromones:
        for e, t in pheromones.tau.items():
            if t > 0: p_data[(e.start.lon, e.start.lat, e.end.lon, e.end.lat)] = t
    vis = StaticVisualizer(bounds=bounds, title=title, routes=[route], pheromones=p_data, mode="dark_nolabels")
    vis.export(filename, scale_up=1)

def run_diagnostics():
    CITY = "Iligan City, Philippines"
    out_dir = Path("results/eval_matrix")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*60)
    print(" EVALUATING INTENSITY SCALING & FRÉCHET SIMILARITY")
    print("="*60)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    
    routes = sim.jeep_system.routes
    cg = routes[0].cg
    bounds = sim.bounds
    
    pheromones = PheromoneMatrix(all_edges=cg.graph)
    target_edge = random.choice(cg.graph)
    pheromones.tau[target_edge] = 8000.0  
    
    redundant_edge = routes[0].path[len(routes[0].path)//2]
    routes[1].path.insert(len(routes[1].path)//2, redundant_edge) 
    gaps = pheromones.calculate_demand_service_gaps(routes)
    gaps[redundant_edge] = -5000.0 

    local_search = ACOLocalSearch(cg, base_window_size=15)
    intensities = [i / 10.0 for i in range(1, 11)]

    # Lock target to route[0] to guarantee it contains the redundant edge
    target_route = routes[0]
    baseline_path = target_route.path[:]
    
    export_visual(str(out_dir / "00_baseline.png"), "Baseline Route", target_route, bounds, pheromones)
    
    strategies = [
        ("Attraction", lambda i: local_search.strategy_spatial_attraction([target_route], pheromones, gaps, intensity=i)),
        # Pass the target route twice to artificially satisfy the overlap constraint
        ("Repulsion", lambda i: local_search.strategy_redundancy_repulsion([target_route, target_route], gaps, intensity=i)),
        ("Pruning", lambda i: local_search.strategy_tortuosity_pruning([target_route], intensity=i)[1])
    ]

    for strat_name, strat_func in strategies:
        print(f"\n[*] Evaluating {strat_name}")
        for intensity in intensities:
            target_route.path = baseline_path[:]
            mutated = strat_func(intensity)
            
            if mutated:
                baseline_route_obj = Route(path=baseline_path, city_graph=cg)
                frechet_score = local_search.calculate_route_similarity(baseline_route_obj, mutated)
                filename = out_dir / f"{strat_name.lower()}_{intensity:.1f}.png"
                export_visual(str(filename), f"{strat_name} (Int: {intensity})", mutated, bounds, pheromones)
                print(f"    Intensity: {intensity:.1f} | Fréchet Distance: {frechet_score:.6f} | Exported: {filename.name}")
            else:
                print(f"    Intensity: {intensity:.1f} | Mutation rejected due to strict graph constraints.")

if __name__ == "__main__":
    run_diagnostics()