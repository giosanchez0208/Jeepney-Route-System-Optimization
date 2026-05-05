"""test.py

Phase C Diagnostic: Edge Substitution & Continuity Verification.
Ensures ACO local search maintains valid graph topology when mutating routes.
"""

import yaml
import random
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.local_search import ACOLocalSearch

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def is_route_continuous(path: list) -> bool:
    """Verifies that the end of every edge connects exactly to the start of the next."""
    if not path: return False
    for i in range(len(path) - 1):
        if path[i].end != path[i+1].start:
            print(f"    [!] BREAK DETECTED: {path[i].end} does not connect to {path[i+1].start}")
            return False
    # Check loop closure
    if path[-1].end != path[0].start:
        print(f"    [!] LOOP BROKEN: Last node {path[-1].end} != First node {path[0].start}")
        return False
    return True

def run_diagnostics():
    CITY = "Iligan City, Philippines"
    print("="*60)
    print(" BOOTING PHASE C DIAGNOSTIC")
    print("="*60)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    
    routes = sim.jeep_system.routes
    cg = routes[0].cg
    
    print("[*] Generating fake global demand profile...")
    pheromones = PheromoneMatrix(all_edges=cg.graph)
    
    # Artificially spike demand on one random, unserved edge
    target_edge = random.choice(cg.graph)
    while any(target_edge in r.path for r in routes):
        target_edge = random.choice(cg.graph)
        
    pheromones.tau[target_edge] = 5000.0  # Massive demand
    gaps = pheromones.calculate_demand_service_gaps(routes)

    local_search = ACOLocalSearch(cg)

    print("\n" + "="*60)
    print(" TEST 1: STRATEGY 1 (Least-Served Extension)")
    print("="*60)
    
    # Store original state
    least_served_route = min(routes, key=lambda r: sum(pheromones.tau.get(e, 0) for e in r.path))
    original_length = len(least_served_route.path)
    
    print(f"[*] Target High-Demand Edge : {target_edge}")
    print(f"[*] Pre-Mutation Route Length: {original_length} edges")
    
    success = local_search.strategy_1_least_served_extension(routes, pheromones, gaps)
    
    if success:
        print("[+] Mutation Executed.")
        print(f"[*] Post-Mutation Route Length: {len(least_served_route.path)} edges")
        print(f"[*] Did the route incorporate the target edge? : {target_edge in least_served_route.path}")
        
        if is_route_continuous(least_served_route.path):
            print("[+] PASS: Route connectivity and loop closure successfully maintained via shortest-path bridging.")
        else:
            print("[-] FAIL: The mutation shattered the route continuity.")
    else:
        print("[-] FAIL: Strategy 1 declined to mutate. Check bridging logic.")

if __name__ == "__main__":
    run_diagnostics()