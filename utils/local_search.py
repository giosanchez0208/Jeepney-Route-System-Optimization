"""local_search.py

Executes Phase C: ACO-Biased Local Search.
Applies system-level heuristics (Gravity, Dispersion, and Pruning) to 
reshape the Jeepney network based on global pheromone and gap data.
"""

import random
from typing import Any
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

    def strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict) -> bool:
        """
        GRAVITY: Moves the worst segment of the least-served route towards the highest demand.
        """
        if not routes or not gaps: return False

        # 1. Target: Route with lowest total utility
        route_pheromones = {r: sum(pheromones.tau.get(e, 0) for e in r.path) for r in routes}
        r_star = min(route_pheromones, key=route_pheromones.get)

        # 2. Target: Highest Demand Gap
        e_star = max(gaps, key=gaps.get)
        if gaps[e_star] <= 0: return False

        # 3. Identify the worst contiguous segment in the route
        best_idx = 0
        lowest_segment_tau = float('inf')
        
        for i in range(len(r_star.path) - self.window_size):
            segment = r_star.path[i:i+self.window_size]
            seg_tau = sum(pheromones.tau.get(e, 0) for e in segment)
            if seg_tau < lowest_segment_tau:
                lowest_segment_tau = seg_tau
                best_idx = i

        # 4. Rip out the segment and bridge through e_star
        node_before = r_star.path[best_idx].start
        node_after = r_star.path[best_idx + self.window_size - 1].end

        bridge_in = self._get_shortest_path_edges(node_before, e_star.start)
        bridge_out = self._get_shortest_path_edges(e_star.end, node_after)

        if (node_before != e_star.start and not bridge_in) or (e_star.end != node_after and not bridge_out):
            return False

        r_star.path = r_star.path[:best_idx] + bridge_in + [e_star] + bridge_out + r_star.path[best_idx + self.window_size:]
        return True

    def strategy_redundancy_repulsion(self, routes: list[Route], gaps: dict) -> bool:
        """
        DISPERSION: Finds the most overserved edge (negative gap) and forces one route to detour.
        """
        if not routes or not gaps: return False

        # 1. Find most overserved edge (lowest negative gap)
        e_overserved = min(gaps, key=gaps.get)
        if gaps[e_overserved] >= 0: return False

        # 2. Find routes using this edge
        overlapping_routes = [r for r in routes if e_overserved in r.path]
        if len(overlapping_routes) < 2: return False # Not redundant if only 1 route uses it

        # 3. Pick one route to repel
        r_target = random.choice(overlapping_routes)
        idx = r_target.path.index(e_overserved)

        node_before = r_target.path[idx].start
        node_after = r_target.path[idx].end

        # 4. Proxy for detour: Pick a random nearby node from the CityGraph that is NOT on the bad edge
        # (Assuming self.cg.nodes is a list of all nodes)
        nearby_nodes = [n for n in self.cg.nodes if abs(n.lat - node_before.lat) < 0.005 and abs(n.lon - node_before.lon) < 0.005]
        nearby_nodes = [n for n in nearby_nodes if n != node_before and n != node_after]
        
        if not nearby_nodes: return False
        detour_node = random.choice(nearby_nodes)

        # 5. Bridge through the detour node
        bridge_in = self._get_shortest_path_edges(node_before, detour_node)
        bridge_out = self._get_shortest_path_edges(detour_node, node_after)

        if not bridge_in or not bridge_out: return False

        r_target.path = r_target.path[:idx] + bridge_in + bridge_out + r_target.path[idx+1:]
        return True

    def strategy_tortuosity_pruning(self, routes: list[Route]) -> int:
        """
        PRUNING: Scans all routes for circuitous detours and snaps them to the shortest path.
        Returns the number of prunes executed.
        """
        prunes = 0
        for r in routes:
            if len(r.path) <= self.window_size: continue
            
            # Slide window across the route
            for i in range(len(r.path) - self.window_size):
                if i + self.window_size >= len(r.path): break
                
                segment_start = r.path[i].start
                segment_end = r.path[i + self.window_size - 1].end
                
                # Check if the graph has a faster way between these two points
                direct_path = self._get_shortest_path_edges(segment_start, segment_end)
                
                # If the direct path is strictly shorter than the window, prune it
                if direct_path and len(direct_path) < self.window_size:
                    r.path = r.path[:i] + direct_path + r.path[i + self.window_size:]
                    prunes += 1
                    break # Break to avoid index shifting issues; will catch others next generation
        return prunes

    def optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict) -> dict:
        """
        The Memetic Wrapper. Rolls probability and orchestrates the system mutations.
        Returns a dictionary of what actions were taken for logging.
        """
        actions_taken = {"attraction": False, "repulsion": False, "prunes": 0}
        
        if random.random() < self.p_local:
            actions_taken["attraction"] = self.strategy_spatial_attraction(routes, pheromones, gaps)
            
        if random.random() < self.p_local:
            actions_taken["repulsion"] = self.strategy_redundancy_repulsion(routes, gaps)
            
        # Pruning is highly beneficial and computationally cheap, apply it frequently
        if random.random() < (self.p_local * 1.5):
            actions_taken["prunes"] = self.strategy_tortuosity_pruning(routes)
            
        return actions_taken