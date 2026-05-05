"""test.py

Deep Diagnostic Suite for Phase B: Pheromone Engine & Demand-Service Gaps.
Validates mathematical accuracy and pipeline integration before Phase C execution.
"""

import yaml
import random
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[!] Config load failed: {e}")
        return {}

def run_diagnostics():
    CITY = "Iligan City, Philippines"
    
    print("="*60)
    print(" BOOTING DIAGNOSTIC ENVIRONMENT")
    print("="*60)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    
    base_graph = sim.jeep_system.routes[0].cg.graph
    
    # Initialize matrix with explicit test constants
    RHO = 0.1
    Q = 1000.0
    INITIAL_TAU = 1.0
    
    pheromones = PheromoneMatrix(
        all_edges=base_graph, 
        initial_tau=INITIAL_TAU,
        rho=RHO,
        q=Q
    )
    
    print(f"[*] Matrix initialized tracking {len(pheromones.tau)} edges.")

    print("\n" + "="*60)
    print(" TEST 1: CONTROLLED MATHEMATICAL VERIFICATION")
    print("="*60)
    
    # 1. Grab a random edge
    test_edge = random.choice(base_graph)
    pre_tau = pheromones.tau[test_edge]
    
    # 2. Inject a controlled fake passenger payload
    # Payload: 1 passenger took this exact edge, total path cost was 10.0
    fake_cost = 10.0
    fake_payload = [([test_edge], fake_cost)]
    
    print(f"[*] Injecting 1 dummy passenger taking a single edge.")
    print(f"[*] Path Cost: {fake_cost} | Q: {Q} | Rho: {RHO}")
    
    # 3. Calculate mathematically expected outcome
    # Formula: (pre_tau * (1 - rho)) + (Q / cost)
    expected_tau = (pre_tau * (1 - RHO)) + (Q / fake_cost)
    
    # 4. Run update
    pheromones.update_pheromones(fake_payload)
    actual_tau = pheromones.tau[test_edge]
    
    print(f"[*] Expected Tau : {expected_tau:.4f}")
    print(f"[*] Actual Tau   : {actual_tau:.4f}")
    
    if abs(expected_tau - actual_tau) < 1e-5:
        print("[+] PASS: Deposition and Evaporation formulas are exact.")
    else:
        print("[-] FAIL: Mathematical mismatch detected.")

    print("\n" + "="*60)
    print(" TEST 2: PIPELINE INTEGRATION & PAYLOAD PROCESSING")
    print("="*60)
    
    # Run a quick 500-tick simulation to generate real passenger paths
    print("[*] Running 500-tick headless simulation to generate real payload...")
    sim.max_ticks = 500
    result = sim.run()
    
    real_payload = result.recorded_paths
    total_passengers = len(real_payload)
    valid_paths = sum(1 for path, cost in real_payload if path and cost > 0)
    
    print(f"[*] Simulation Complete. Generated {total_passengers} passenger records.")
    print(f"[*] Valid paths for deposition: {valid_paths}")
    
    # Reset the test edge so it doesn't skew the real data
    pheromones.tau[test_edge] = INITIAL_TAU * (1 - RHO) 
    
    # Apply real payload
    pheromones.update_pheromones(real_payload)
    
    # Calculate statistics
    all_taus = list(pheromones.tau.values())
    max_tau = max(all_taus)
    avg_tau = sum(all_taus) / len(all_taus)
    
    print(f"[+] PASS: Real payload processed without crashing.")
    print(f"[*] Global Max Tau : {max_tau:.4f}")
    print(f"[*] Global Avg Tau : {avg_tau:.4f}")

    print("\n" + "="*60)
    print(" TEST 3: DEMAND-SERVICE GAP EVALUATION")
    print("="*60)
    
    print("[*] Computing Delta (Gap) across all edges...")
    gaps = pheromones.calculate_demand_service_gaps(sim.jeep_system.routes)
    
    # Sort edges by gap value
    sorted_edges = sorted(gaps.items(), key=lambda item: item[1], reverse=True)
    
    highest_gap_edge, highest_gap_val = sorted_edges[0]
    lowest_gap_edge, lowest_gap_val = sorted_edges[-1]
    
    print(f"[*] Top Underserved Edge (Highest Positive Delta):")
    print(f"    Edge: {highest_gap_edge.start.lat:.4f},{highest_gap_edge.start.lon:.4f} -> {highest_gap_edge.end.lat:.4f},{highest_gap_edge.end.lon:.4f}")
    print(f"    Gap Value : +{highest_gap_val:.4f} (High Demand, Low/No Service)")
    
    print(f"\n[*] Top Overserved Edge (Lowest Negative Delta):")
    print(f"    Edge: {lowest_gap_edge.start.lat:.4f},{lowest_gap_edge.start.lon:.4f} -> {lowest_gap_edge.end.lat:.4f},{lowest_gap_edge.end.lon:.4f}")
    print(f"    Gap Value : {lowest_gap_val:.4f} (Low Demand, High Service)")
    
    # Verify that the overserved edge actually has a route on it
    routes_on_lowest = sum(1 for r in sim.jeep_system.routes if lowest_gap_edge in r.path)
    print(f"\n[*] Verification: Does the 'Overserved' edge have active routes on it? : {routes_on_lowest > 0} ({routes_on_lowest} routes)")
    
    if routes_on_lowest > 0 and highest_gap_val > 0:
        print("[+] PASS: Gap calculation successfully separates served vs. stranded corridors.")
    else:
        print("[-] WARNING: Gap separation may not be polarizing correctly. Check routing density.")

if __name__ == "__main__":
    run_diagnostics()