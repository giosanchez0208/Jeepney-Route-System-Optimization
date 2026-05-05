"""test.py

System-Level Heuristic Diagnostic with Isolated Visuals.
Fires Gravity, Dispersion, and Pruning algorithms and visually isolates 
the target route to prove the loose-end stitcher works.
"""

import yaml
import random
from pathlib import Path
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.local_search import ACOLocalSearch
from utils.visualizer import StaticVisualizer

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def is_route_continuous(path: list, tag: str = "CHECK") -> bool:
    if not path: 
        print(f"    [!] {tag} FAIL: Path is empty.")
        return False
        
    for i in range(len(path) - 1):
        if path[i].end != path[i+1].start: 
            print(f"    [!] {tag} BREAK at index {i}:")
            print(f"        Edge {i} ends at ({path[i].end.lat:.5f}, {path[i].end.lon:.5f})")
            print(f"        Edge {i+1} starts at ({path[i+1].start.lat:.5f}, {path[i+1].start.lon:.5f})")
            return False
            
    if path[-1].end != path[0].start: 
        print(f"    [!] {tag} LOOP BREAK:")
        print(f"        Last edge ends at ({path[-1].end.lat:.5f}, {path[-1].end.lon:.5f})")
        print(f"        First starts at ({path[0].start.lat:.5f}, {path[0].start.lon:.5f})")
        return False
        
    return True

def export_diagnostic_visual(filename: str, title: str, target_route: list, bounds: tuple, pheromone_matrix: PheromoneMatrix = None):
    """Helper to isolate and render a single route."""
    pheromone_data = {}
    if pheromone_matrix:
        for edge, tau in pheromone_matrix.tau.items():
            if tau > 0:  
                coords = (edge.start.lon, edge.start.lat, edge.end.lon, edge.end.lat)
                pheromone_data[coords] = tau
                
    vis = StaticVisualizer(
        bounds=bounds,
        title=title,
        routes=[target_route], # Isolated single route!
        pheromones=pheromone_data,
        mode="dark_nolabels"
    )
    vis.export(filename, scale_up=1)
    print(f"    [Visual] Saved: {Path(filename).name}")

def run_diagnostics():
    CITY = "Iligan City, Philippines"
    print("="*60)
    print(" BOOTING PHASE C: STITCHER DIAGNOSTIC")
    print("="*60)
    
    out_dir = Path("results/phase_c_visuals")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    
    routes = sim.jeep_system.routes
    cg = routes[0].cg
    bounds = sim.bounds
    
    # Pre-check baseline
    pre_check = all(is_route_continuous(r.path, "PRE-MUTATION") for r in routes)
    print(f"[*] Baseline Routes Continuous: {pre_check}")
    
    print("[*] Generating baseline data...")
    pheromones = PheromoneMatrix(all_edges=cg.graph)
    
    target_edge = random.choice(cg.graph)
    pheromones.tau[target_edge] = 8000.0  
    
    redundant_edge = routes[0].path[len(routes[0].path)//2]
    routes[1].path.insert(len(routes[1].path)//2, redundant_edge) 
    
    gaps = pheromones.calculate_demand_service_gaps(routes)
    gaps[redundant_edge] = -5000.0 

    local_search = ACOLocalSearch(cg, window_size=5)

    # ==========================================
    # HEURISTIC 1: SPATIAL ATTRACTION
    # ==========================================
    print("\n[*] TESTING HEURISTIC 1: SPATIAL ATTRACTION")
    # Identify which route will be targeted (Least-served)
    route_pheromones = {r: sum(pheromones.tau.get(e, 0) for e in r.path) for r in routes}
    target_1 = min(route_pheromones, key=route_pheromones.get)
    
    export_diagnostic_visual(str(out_dir / "01_before_attraction.png"), "Before Attraction", target_1, bounds, pheromones)
    
    mutated_route_1 = local_search.strategy_spatial_attraction(routes, pheromones, gaps)
    
    if mutated_route_1:
        export_diagnostic_visual(str(out_dir / "02_after_attraction.png"), "After Attraction", mutated_route_1, bounds, pheromones)
        print(f"    Executed: True | Continuity Intact: {is_route_continuous(mutated_route_1.path, 'ATTR')}")
    else:
        print("    Executed: False")

    # ==========================================
    # HEURISTIC 2: REDUNDANCY REPULSION
    # ==========================================
    print("\n[*] TESTING HEURISTIC 2: REDUNDANCY REPULSION")
    overlapping_routes = [r for r in routes if redundant_edge in r.path]
    target_2 = overlapping_routes[0] if overlapping_routes else routes[0]
    
    export_diagnostic_visual(str(out_dir / "03_before_repulsion.png"), "Before Repulsion", target_2, bounds)
    
    mutated_route_2 = local_search.strategy_redundancy_repulsion(routes, gaps)
    
    if mutated_route_2:
        export_diagnostic_visual(str(out_dir / "04_after_repulsion.png"), "After Repulsion", mutated_route_2, bounds)
        print(f"    Executed: True | Continuity Intact: {is_route_continuous(mutated_route_2.path, 'REP')}")
    else:
         print("    Executed: False")

    # ==========================================
    # HEURISTIC 3: TORTUOSITY PRUNING
    # ==========================================
    print("\n[*] TESTING HEURISTIC 3: TORTUOSITY PRUNING")
    # Pick a random route to display before pruning
    target_3 = routes[0]
    export_diagnostic_visual(str(out_dir / "05_before_pruning.png"), "Before Pruning", target_3, bounds)
    
    prunes, mutated_route_3 = local_search.strategy_tortuosity_pruning(routes)
    
    if mutated_route_3:
        export_diagnostic_visual(str(out_dir / "06_after_pruning.png"), f"After Pruning ({prunes} cuts)", mutated_route_3, bounds)
        print(f"    Segments Pruned: {prunes} | Continuity Intact: {is_route_continuous(mutated_route_3.path, 'PRUN')}")
    else:
        print("    Segments Pruned: 0")

if __name__ == "__main__":
    run_diagnostics()