"""local_search.py

Executes Phase C: ACO-Biased Local Search.
Applies system-level heuristics (Gravity, Dispersion, and Pruning) to 
reshape the Jeepney network based on global pheromone and gap data.
Integrates Geographic Nearest-Neighbor Insertion to prevent route tangling.
"""

import random
from typing import Any, Optional
from .route import Route
from .pheromone import PheromoneMatrix

class ACOLocalSearch:
    def __init__(self, cg: Any, p_local: float = 0.5, window_size: int = 5):
        self.cg = cg
        self.p_local = p_local
        self.window_size = window_size

    def _get_shortest_path_edges(self, start_node: Any, end_node: Any) -> list[Any]:
        if start_node == end_node: return []
        try:
            path = self.cg.findShortestPath(start_node, end_node)
            return path if path else []
        except:
            return []

    def _stitch_path(self, raw_edges: list) -> Optional[list]:
        """
        The Sweeper: Iterates through a rough array of edges. If it finds a gap 
        between edge[i].end and edge[i+1].start, it dynamically paths a bridge to stitch them.
        Guarantees 100% graph continuity.
        """
        if not raw_edges: return None
        
        stitched = [raw_edges[0]]
        for i in range(1, len(raw_edges)):
            prev_edge = stitched[-1]
            next_edge = raw_edges[i]
            
            if prev_edge.end != next_edge.start:
                # Loose end detected! Stitch it together.
                bridge = self._get_shortest_path_edges(prev_edge.end, next_edge.start)
                if not bridge: 
                    return None # Irreparable graph gap
                stitched.extend(bridge)
                
            stitched.append(next_edge)
            
        # Final Loop Closure Check
        if stitched[-1].end != stitched[0].start:
            loop_bridge = self._get_shortest_path_edges(stitched[-1].end, stitched[0].start)
            if not loop_bridge: 
                return None
            stitched.extend(loop_bridge)
            
        return stitched

    def _safe_splice(self, path: list, start_idx: int, end_idx: int, new_segment: list) -> Optional[list]:
        """Replaces a segment and runs the result through the stitcher."""
        if not new_segment: return None
        raw_path = path[:start_idx] + new_segment + path[end_idx:]
        return self._stitch_path(raw_path)

    def strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict) -> Optional[Route]:
        """
        GRAVITY (Attraction): Uses Geographic Nearest-Neighbor Insertion to bend
        the route toward demand without causing geometric U-turns.
        """
        if not routes or not gaps: return None

        route_pheromones = {r: sum(pheromones.tau.get(e, 0) for e in r.path) for r in routes}
        r_star = min(route_pheromones, key=route_pheromones.get)

        e_star = max(gaps, key=gaps.get)
        if gaps[e_star] <= 0: return None

        # 1. Identify the worst contiguous segment in the route
        best_idx = 0
        lowest_segment_tau = float('inf')
        for i in range(len(r_star.path) - self.window_size):
            segment = r_star.path[i:i+self.window_size]
            seg_tau = sum(pheromones.tau.get(e, 0) for e in segment)
            if seg_tau < lowest_segment_tau:
                lowest_segment_tau = seg_tau
                best_idx = i

        # 2. Prune the bad segment and heal the route
        healed_raw = r_star.path[:best_idx] + r_star.path[best_idx + self.window_size:]
        if not healed_raw: return None
        healed_path = self._stitch_path(healed_raw)
        if not healed_path: return None

        # 3. Scan the healed route to find the edge geographically closest to our target
        insert_idx = 0
        min_dist = float('inf')
        for i, edge in enumerate(healed_path):
            # Calculate squared Euclidean distance to avoid math.sqrt overhead
            dist = (edge.end.lat - e_star.start.lat)**2 + (edge.end.lon - e_star.start.lon)**2
            if dist < min_dist:
                min_dist = dist
                insert_idx = i

        # 4. Splice the target edge right after the closest natural point and run the final stitch
        raw_new = healed_path[:insert_idx+1] + [e_star] + healed_path[insert_idx+1:]
        final_path = self._stitch_path(raw_new)

        if final_path:
            r_star.path = final_path
            return r_star
        return None

    def strategy_redundancy_repulsion(self, routes: list[Route], gaps: dict) -> Optional[Route]:
        """
        DISPERSION (Repulsion): Forces an overserved route to detour slightly 
        off the main corridor to spread fleet coverage.
        """
        if not routes or not gaps: return None

        e_overserved = min(gaps, key=gaps.get)
        if gaps[e_overserved] >= 0: return None

        overlapping_routes = [r for r in routes if e_overserved in r.path]
        if len(overlapping_routes) < 2: return None 

        r_target = random.choice(overlapping_routes)
        idx = r_target.path.index(e_overserved)

        node_before = r_target.path[idx].start
        
        # Pick a nearby node to detour through
        nearby_nodes = [n for n in self.cg.nodes if abs(n.lat - node_before.lat) < 0.005 and abs(n.lon - node_before.lon) < 0.005]
        nearby_nodes = [n for n in nearby_nodes if n != node_before and n != r_target.path[idx].end]
        if not nearby_nodes: return None
        
        detour_node = random.choice(nearby_nodes)
        
        # We need an edge to use as a waypoint. Force a path to the detour node.
        detour_waypoint_path = self._get_shortest_path_edges(node_before, detour_node)
        if not detour_waypoint_path: return None

        # Replace the bad edge with the detour, let the stitcher heal the exit
        new_path = self._safe_splice(r_target.path, idx, idx + 1, detour_waypoint_path)
        if new_path:
            r_target.path = new_path
            return r_target
        return None

    def strategy_tortuosity_pruning(self, routes: list[Route]) -> tuple[int, Optional[Route]]:
        """PRUNING: Scans all routes for circuitous detours and snaps them to the shortest path."""
        prunes = 0
        target_route = None
        
        for r in routes:
            if len(r.path) <= self.window_size: continue
            for i in range(len(r.path) - self.window_size):
                if i + self.window_size >= len(r.path): break
                
                segment_start = r.path[i].start
                segment_end = r.path[i + self.window_size - 1].end
                direct_path = self._get_shortest_path_edges(segment_start, segment_end)
                
                if direct_path and len(direct_path) < self.window_size:
                    new_path = self._safe_splice(r.path, i, i + self.window_size, direct_path)
                    if new_path:
                        r.path = new_path
                        prunes += 1
                        target_route = r
                        break # Process one prune per route per generation to avoid index shifting
        return prunes, target_route

    def optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict) -> dict:
        """The Memetic Wrapper."""
        actions = {"attraction": False, "repulsion": False, "prunes": 0}
        if random.random() < self.p_local:
            actions["attraction"] = self.strategy_spatial_attraction(routes, pheromones, gaps) is not None
        if random.random() < self.p_local:
            actions["repulsion"] = self.strategy_redundancy_repulsion(routes, gaps) is not None
        if random.random() < (self.p_local * 1.5):
            actions["prunes"], _ = self.strategy_tortuosity_pruning(routes)
        return actions