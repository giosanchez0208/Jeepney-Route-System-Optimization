"""generate_good_routes.py

Generates candidate routes, evaluates them against random background systems, and extracts the top 5% highest performing, lowest volatility routes to a CSV.
"""

import csv
import json
import random
import multiprocessing as mp
from pathlib import Path

import numpy as np
from tqdm import tqdm

from utils.city_graph import CityGraph
from utils.route import Route
from utils.travel_graph import TravelGraph
from utils.od_generator import TrafficAwareODGenerator

# Globals for multiprocessing workers
_CG = None
_OD_GEN = None

def _init_worker():
    global _CG, _OD_GEN
    _CG = CityGraph("Iligan City, Lanao del Norte, Philippines")
    _OD_GEN = TrafficAwareODGenerator(_CG, "data/iligan_node_with_traffic_data.csv")

def _evaluate_candidate(seed: int) -> dict:
    """Evaluates a single candidate route against multiple background systems."""
    global _CG, _OD_GEN
    
    cand_route = Route(_CG, od_gen=_OD_GEN)
    
    points = _OD_GEN.generate_origins(n_points=200)
    origins = points[:100]
    destinations = points[100:]
    
    system_averages = []
    
    for _ in range(5):
        num_bg = random.randint(3, 6)
        bg_routes = [Route(_CG, od_gen=_OD_GEN) for _ in range(num_bg)]
        
        tg = TravelGraph(_CG, [cand_route] + bg_routes)
        
        total_weight = 0.0
        paths_found = 0
        
        for o, d in zip(origins, destinations):
            if o is d:
                continue
                
            weight = tg.calculateJourneyWeight(o, d)
            if weight > 0:
                total_weight += weight
                paths_found += 1
                
        if paths_found > 0:
            system_averages.append(total_weight / paths_found)
            
    if not system_averages:
        return None
        
    mu = np.mean(system_averages)
    sigma = np.std(system_averages)
    cv = sigma / mu if mu > 0 else 0.0
    score = mu * (1 + cv)
    
    # Extract the sequence of coordinates instead of volatile node IDs
    coords = [(edge.start.lat, edge.start.lon) for edge in cand_route.path]
    if cand_route.path:
        coords.append((cand_route.path[-1].end.lat, cand_route.path[-1].end.lon))
        
    return {
        "path_coords": json.dumps(coords), # Serialize list of tuples to JSON string for CSV
        "score": score,
        "mu": mu,
        "cv": cv
    }

if __name__ == "__main__":
    N_CANDIDATES = 20
    K_TOP_PERCENT = 0.05
    
    print(f"Spinning up pool to evaluate {N_CANDIDATES} routes...")
    
    results = []
    with mp.Pool(processes=mp.cpu_count(), initializer=_init_worker) as pool:
        for result in tqdm(pool.imap_unordered(_evaluate_candidate, range(N_CANDIDATES)), total=N_CANDIDATES, desc="Evaluating Routes", unit="route"):
            results.append(result)
            
    valid_results = [r for r in results if r is not None]
    
    print(f"Evaluation complete. {len(valid_results)} routes successfully routed passengers.")
    
    valid_results.sort(key=lambda x: x["score"])
    
    cutoff_idx = max(1, int(len(valid_results) * K_TOP_PERCENT))
    good_routes = valid_results[:cutoff_idx]
    
    print(f"Extracted the top {len(good_routes)} 'Good Routes'.")
    
    out_dir = Path("results/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "good_routes.csv"
    
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path_coords", "score", "mu", "cv"])
        writer.writeheader()
        writer.writerows(good_routes)
        
    print(f"Saved to {out_file.resolve()}")