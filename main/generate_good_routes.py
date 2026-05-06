"""generate_good_routes.py

Generates candidate routes, evaluates them against random background systems using a standardized OD test bank, and extracts the top 5% highest performing, lowest volatility routes to a CSV.
"""

import csv
import json
import random
import multiprocessing as mp
import os
from pathlib import Path

import numpy as np
from tqdm import tqdm

from utils.city_graph import CityGraph
from utils.route import Route
from utils.travel_graph import StaticTravelGraph, TravelGraph
from utils.od_generator import TrafficAwareODGenerator

ROOT_DIR = Path(__file__).resolve().parent
DATA_PATH = ROOT_DIR / "data" / "iligan_node_with_traffic_data.csv"
OUT_DIR = ROOT_DIR / "results" / "data"

_CG = None
_STG = None
_OD_GEN = None
_TEST_ORIGINS = None
_TEST_DESTINATIONS = None

def _build_shared_state():
    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
    stg = StaticTravelGraph(cg)
    od_gen = TrafficAwareODGenerator(cg, DATA_PATH)

    np.random.seed()
    points = od_gen.generate_origins(n_points=200)
    test_origins = points[:100]
    test_destinations = points[100:]
    np.random.seed()

    return cg, stg, od_gen, test_origins, test_destinations

def _init_worker(cg, stg, od_gen, test_origins, test_destinations):
    global _CG, _STG, _OD_GEN, _TEST_ORIGINS, _TEST_DESTINATIONS
    
    _CG = cg
    _STG = stg
    _OD_GEN = od_gen
    _TEST_ORIGINS = test_origins
    _TEST_DESTINATIONS = test_destinations

def _evaluate_candidate(seed: int) -> dict:
    global _CG, _STG, _OD_GEN, _TEST_ORIGINS, _TEST_DESTINATIONS
    
    cand_route = Route(_CG, od_gen=_OD_GEN)
    system_averages = []
    
    for _ in range(5):
        num_bg = random.randint(3, 6)
        bg_routes = [Route(_CG, od_gen=_OD_GEN) for _ in range(num_bg)]
        
        tg = TravelGraph(_STG, [cand_route] + bg_routes)
        
        total_weight = 0.0
        paths_found = 0
        
        for o, d in zip(_TEST_ORIGINS, _TEST_DESTINATIONS):
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
    
    coords = [(edge.start.lat, edge.start.lon) for edge in cand_route.path]
    if cand_route.path:
        coords.append((cand_route.path[-1].end.lat, cand_route.path[-1].end.lon))
        
    return {
        "path_coords": json.dumps(coords),
        "score": score,
        "mu": mu,
        "cv": cv
    }

if __name__ == "__main__":
    os.chdir(ROOT_DIR)
    mp.freeze_support()

    N_CANDIDATES = 40
    K_TOP_PERCENT = 0.05

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing traffic data file: {DATA_PATH}")
    
    print(f"Spinning up pool to evaluate {N_CANDIDATES} routes...")
    
    shared_state = _build_shared_state()
    results = []
    with mp.Pool(processes=mp.cpu_count(), initializer=_init_worker, initargs=shared_state) as pool:
        for result in tqdm(pool.imap_unordered(_evaluate_candidate, range(N_CANDIDATES)), total=N_CANDIDATES, desc="Evaluating Routes", unit="route"):
            results.append(result)
            
    valid_results = [r for r in results if r is not None]
    
    print(f"Evaluation complete. {len(valid_results)} routes successfully routed passengers.")
    
    valid_results.sort(key=lambda x: x["score"])
    
    cutoff_idx = max(1, int(len(valid_results) * K_TOP_PERCENT))
    good_routes = valid_results[:cutoff_idx]
    
    print(f"Extracted the top {len(good_routes)} 'Good Routes'.")
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / "good_routes.csv"
    
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path_coords", "score", "mu", "cv"])
        writer.writeheader()
        writer.writerows(good_routes)
        
    print(f"Saved to {out_file.resolve()}")
