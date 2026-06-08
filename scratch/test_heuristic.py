import os
import sys
import time
import math
import yaml
from collections import defaultdict
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.travel_graph import TravelGraph

def main():
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    print("Generating 38 routes...")
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg_config = config.get("travel_graph", {})
    
    print("Building TravelGraph...")
    tg = TravelGraph(cg, config=tg_config, routes=routes)
    
    # Generate queries
    origins = [ddm.get_point() for _ in range(100)]
    dests = [ddm.get_point() for _ in range(100)]
    
    # Original search
    print("Running original A* queries...")
    t0 = time.time()
    for o, d in zip(origins, dests):
        tg._findShortestJourney_impl(o, d)
    t_orig = time.time() - t0
    print(f"Original A* time for 100 queries: {t_orig:.3f}s")
    
    # Equirectangular search
    # Let's override _findShortestJourney_impl with a fast version
    LAT_TO_METERS = 110574.0
    LON_TO_METERS = 110175.0
    
    def fast_find(self, start, end):
        if start is None or end is None:
            raise ValueError("[TRAVEL GRAPH] Start and end nodes cannot be None.")
            
        l1_start = self._snap_node(start, 1)
        l3_end = self._snap_node(end, 3)

        from heapq import heappush, heappop
        from itertools import count
        
        frontier = []
        sequence = count()
        
        h_cache = {}
        min_wt = min(self.walk_wt, self.ride_wt)
        
        # Pre-cache end lat/lon to avoid attribute lookups in loop
        end_lat = l3_end.lat
        end_lon = l3_end.lon
        
        def get_h(n) -> float:
            if n not in h_cache:
                dlat = (n.lat - end_lat) * LAT_TO_METERS
                dlon = (n.lon - end_lon) * LON_TO_METERS
                h_cache[n] = math.sqrt(dlat*dlat + dlon*dlon) * min_wt
            return h_cache[n]

        heappush(frontier, (get_h(l1_start), 0.0, next(sequence), l1_start))
        came_from = {}
        cost_so_far = {l1_start: 0.0}

        while frontier:
            _, current_cost, _, current = heappop(frontier)

            if current == l3_end:
                # Reconstruct path
                path = []
                curr = l3_end
                while curr != l1_start:
                    previous, edge = came_from[curr]
                    path.append(edge)
                    curr = previous
                path.reverse()
                return path

            if current_cost > cost_so_far.get(current, float("inf")):
                continue

            for edge in self._outgoing_edges.get(current, []):
                next_node = edge.end
                new_cost = current_cost + edge.weight

                if new_cost < cost_so_far.get(next_node, float("inf")):
                    cost_so_far[next_node] = new_cost
                    came_from[next_node] = (current, edge)
                    priority = new_cost + get_h(next_node)
                    heappush(frontier, (priority, new_cost, next(sequence), next_node))

        return []

    # Bind the fast search
    import types
    tg._findShortestJourney_impl = types.MethodType(fast_find, tg)
    
    print("Running fast equirectangular A* queries...")
    t0 = time.time()
    for o, d in zip(origins, dests):
        tg._findShortestJourney_impl(o, d)
    t_fast = time.time() - t0
    print(f"Fast A* time for 100 queries: {t_fast:.3f}s (Speedup: {t_orig / t_fast:.1f}x)")

if __name__ == "__main__":
    main()
