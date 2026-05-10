"""test.py"""

import yaml
import time
import threading
from utils.simulation import SimulationSetup

def load_config(path: str = "utils/configs/configs.yaml") -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def visual_memory_observer(sim):
    """Background thread to interrogate the visualizer's memory state."""
    time.sleep(2)  # Wait for visualizer to boot
    while not sim.is_complete:
        # Access the list directly through the visualizer reference chain
        vis_passengers = sim.jeep_system.passengers
        loaded_jeeps = sum(1 for j in sim.jeep_system.jeeps if getattr(j, 'curr_passenger_count', 0) > 0)
        
        print(f"[Observer] Tick {sim.current_tick}: Visualizer sees {len(vis_passengers)} passengers | {loaded_jeeps} Jeeps loaded")
        time.sleep(1)

def main():
    CITY = "Iligan City, Philippines"
    TICKS = 3600
    
    print("[*] Loading Configurations...")
    config = load_config()

    print("[*] Booting Simulation Setup...")
    # Routes are now automatically generated via OD_Gen inside the builder
    setup = SimulationSetup(city_query=CITY, config=config)
    
    vis_kwargs = {
        "title": f"Diagnostic: Live Execution ({CITY})", 
        "mode": "light_nolabels",
    }
    
    sim = setup.build(visualizer=True, vis_kwargs=vis_kwargs)
    sim.speed_multiplier = 2
    sim.max_ticks = TICKS

    observer = threading.Thread(target=visual_memory_observer, args=(sim,), daemon=True)
    observer.start()

    print(f"\n[*] Executing Phase A Simulation ({TICKS} Ticks)...")
    sim.run()

if __name__ == "__main__":
    main()