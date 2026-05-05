"""test.py

Phase D Initialization Diagnostic.
Verifies the integrated Gen-0 OD routing and Mohring fleet allocation pipeline.
"""

import yaml
from pathlib import Path
from utils.simulation import SimulationSetup
from utils.pheromone import PheromoneMatrix
from utils.jeep_system import FleetAllocator, JeepSystem
from utils.jeep import Jeep
from utils.visualizer import StaticVisualizer

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f: return yaml.safe_load(f)

def run_diagnostics():
    CITY = "Iligan City, Philippines"
    TOTAL_FLEET = 100
    ROUTE_SUBSET_SIZE = 5

    out_dir = Path("results/phase_d_init")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*60)
    print(" BOOTING PHASE D: INTEGRATED GEN-0 DIAGNOSTIC")
    print("="*60)
    
    config = load_config()
    setup = SimulationSetup(city_query=CITY, config=config)
    sim = setup.build(visualizer=False)
    
    routes = sim.jeep_system.routes[:ROUTE_SUBSET_SIZE]
    cg = routes[0].cg
    bounds = sim.bounds
    
    pheromones = PheromoneMatrix(all_edges=cg.graph)
    
    print("[*] Processing empty pheromone map via FleetAllocator...")
    allocation = FleetAllocator.allocate_by_mohring(TOTAL_FLEET, routes, pheromones, cg)
    
    jeeps = []
    for route, count in allocation.items():
        print(f"    Route {sim.jeep_system.routes.index(route)}: Allocated {count} Jeeps")
        start_pos = (route.path[0].start.lat, route.path[0].start.lon)
        for _ in range(count):
            jeep = Jeep(route=route, currPos=start_pos, speed=0.0005)
            jeep.passenger_max = 16
            jeeps.append(jeep)
            
    print("[*] Spacing Fleet Equidistantly...")
    JeepSystem(jeeps=jeeps, routes=routes, equidistant_spawn=True)

    print("[*] Rendering Visual Proof...")
    p_data = { (e.start.lon, e.start.lat, e.end.lon, e.end.lat): t for e, t in pheromones.tau.items() if t > 0 }

    vis = StaticVisualizer(
        bounds=bounds,
        title="Integrated Gen-0 Allocation",
        routes=routes,
        jeeps=jeeps,
        pheromones=p_data,
        mode="dark_nolabels"
    )
    
    export_path = str(out_dir / "gen_0_integrated.png")
    vis.export(export_path, scale_up=1)
    print(f"    Exported to: {export_path}")

if __name__ == "__main__":
    run_diagnostics()