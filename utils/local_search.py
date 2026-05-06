"""Flow: routes + pheromones + demand gaps -> local edits -> improved route layout.

ACOLocalSearch(cg: Any, p_local: float = 0.5, base_window_size: int = 15) -> None owns the Phase C route refinement logic.
calculate_route_similarity(self, route_a: Route, route_b: Route) -> float compares route shapes.
strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict, intensity: float = 1.0) -> Optional[Route], strategy_redundancy_repulsion(self, routes: list[Route], gaps: dict, intensity: float = 1.0) -> Optional[Route], strategy_tortuosity_pruning(self, routes: list[Route], intensity: float = 1.0) -> tuple[int, Optional[Route]], and optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict, intensity: float = 1.0) -> dict are the public search methods.

Inputs: CityGraph access, routes, pheromone matrix, demand gaps, and intensity.
Outputs: optional route replacements plus an action summary from optimize_system().
Imported modules used: Route and PheromoneMatrix, plus math and random helpers.
"""

import math
import random
from typing import Any, Optional
from .route import Route
from .pheromone import PheromoneMatrix

class ACOLocalSearch:
    def __init__(self, cg: Any, p_local: float = 0.5, base_window_size: int = 15):
        self.cg = cg
        self.p_local = p_local
        self.base_window_size = base_window_size

    def calculate_route_similarity(self, route_a: Route, route_b: Route) -> float:
        if not route_a.path or not route_b.path: return float('inf')
        P = [(e.start.lat, e.start.lon) for e in route_a.path]
        Q = [(e.start.lat, e.start.lon) for e in route_b.path]
        n, m = len(P), len(Q)
        ca = [[0.0 for _ in range(m)] for _ in range(n)]
        for i in range(n):
            for j in range(m):
                dist = math.sqrt((P[i][0] - Q[j][0])**2 + (P[i][1] - Q[j][1])**2)
                if i == 0 and j == 0: ca[i][j] = dist
                elif i > 0 and j == 0: ca[i][j] = max(ca[i-1][0], dist)
                elif i == 0 and j > 0: ca[i][j] = max(ca[0][j-1], dist)
                else: ca[i][j] = max(min(ca[i-1][j], ca[i][j-1], ca[i-1][j-1]), dist)
        return ca[n-1][m-1]

    def _get_shortest_path_edges(self, start_node: Any, end_node: Any) -> list[Any]:
        if start_node == end_node: return []
        try:
            path = self.cg.findShortestPath(start_node, end_node)
            return path if path else []
        except:
            return []

    def _stitch_path(self, raw_edges: list) -> Optional[list]:
        if not raw_edges: return None
        stitched = [raw_edges[0]]
        for i in range(1, len(raw_edges)):
            prev_edge = stitched[-1]
            next_edge = raw_edges[i]
            if prev_edge.end != next_edge.start:
                bridge = self._get_shortest_path_edges(prev_edge.end, next_edge.start)
                if not bridge: return None 
                stitched.extend(bridge)
            stitched.append(next_edge)
        if stitched[-1].end != stitched[0].start:
            loop_bridge = self._get_shortest_path_edges(stitched[-1].end, stitched[0].start)
            if not loop_bridge: return None
            stitched.extend(loop_bridge)
        return stitched

    def _safe_splice(self, path: list, start_idx: int, end_idx: int, new_segment: list) -> Optional[list]:
        if not new_segment: return None
        raw_path = path[:start_idx] + new_segment + path[end_idx:]
        return self._stitch_path(raw_path)

    def strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict, intensity: float = 1.0) -> Optional[Route]:
        if not routes or not gaps: return None

        route_pheromones = {r: sum(pheromones.tau.get(e, 0) for e in r.path) for r in routes}
        r_star = min(route_pheromones, key=route_pheromones.get)
        
        path_len = len(r_star.path)
        if path_len < 2: 
            return None

        # Clamp window to the current path length
        window = min(path_len, max(2, int(self.base_window_size * intensity)))
        
        best_idx = 0
        lowest_segment_tau = float('inf')
        
        # Ensure the loop runs even if path_len == window
        search_range = max(1, path_len - window + 1)
        for i in range(search_range):
            seg_tau = sum(pheromones.tau.get(e, 0) for e in r_star.path[i:i+window])
            if seg_tau < lowest_segment_tau:
                lowest_segment_tau = seg_tau
                best_idx = i

        # Guard against index overflow
        node_center_idx = min(path_len - 1, best_idx + window // 2)
        node_center = r_star.path[node_center_idx].start
        
        max_radius = 0.02 * intensity
        
        candidate_edges = []
        for e, gap in gaps.items():
            if gap > 0:
                dist = math.sqrt((e.start.lat - node_center.lat)**2 + (e.start.lon - node_center.lon)**2)
                if dist <= max_radius:
                    candidate_edges.append((e, gap))
        
        if not candidate_edges:
            e_star = max(gaps, key=gaps.get)
        else:
            e_star = max(candidate_edges, key=lambda x: x[1])[0]

        healed_raw = r_star.path[:best_idx] + r_star.path[best_idx + window:]
        if not healed_raw: return None
        healed_path = self._stitch_path(healed_raw)
        if not healed_path: return None

        insert_idx = 0
        min_dist = float('inf')
        for i, edge in enumerate(healed_path):
            dist = (edge.end.lat - e_star.start.lat)**2 + (edge.end.lon - e_star.start.lon)**2
            if dist < min_dist:
                min_dist = dist
                insert_idx = i

        raw_new = healed_path[:insert_idx+1] + [e_star] + healed_path[insert_idx+1:]
        final_path = self._stitch_path(raw_new)

        if final_path:
            r_star.path = final_path
            return r_star
        return None

    def strategy_redundancy_repulsion(self, routes: list[Route], gaps: dict, intensity: float = 1.0) -> Optional[Route]:
        if not routes or not gaps: return None

        e_overserved = min(gaps, key=gaps.get)
        if gaps[e_overserved] >= 0: return None

        overlapping_routes = [r for r in routes if e_overserved in r.path]
        if len(overlapping_routes) < 2: return None 

        r_target = random.choice(overlapping_routes)
        idx = r_target.path.index(e_overserved)
        
        window = max(1, int((self.base_window_size / 2) * intensity))
        start_idx = max(0, idx - window // 2)
        end_idx = min(len(r_target.path), idx + window // 2 + 1)
        
        node_before = r_target.path[start_idx].start
        node_after = r_target.path[end_idx - 1].end

        target_radius = 0.015 * intensity
        candidate_nodes = [n for n in self.cg.nodes if n != node_before and n != node_after]
        
        valid_detours = []
        for n in candidate_nodes:
            dist_start = math.sqrt((n.lat - node_before.lat)**2 + (n.lon - node_before.lon)**2)
            dist_end = math.sqrt((n.lat - node_after.lat)**2 + (n.lon - node_after.lon)**2)
            if dist_start < target_radius and (dist_start + dist_end) < (target_radius * 3):
                valid_detours.append((n, dist_start + dist_end))
        
        valid_detours.sort(key=lambda x: x[1], reverse=True)
        
        for detour_node, _ in valid_detours[:20]:
            bridge_in = self._get_shortest_path_edges(node_before, detour_node)
            if not bridge_in: continue
            bridge_out = self._get_shortest_path_edges(detour_node, node_after)
            if not bridge_out: continue
            
            if e_overserved in bridge_in or e_overserved in bridge_out:
                continue
            
            new_path = self._safe_splice(r_target.path, start_idx, end_idx, bridge_in + bridge_out)
            if new_path:
                r_target.path = new_path
                return r_target
        return None

    def strategy_tortuosity_pruning(self, routes: list[Route], intensity: float = 1.0) -> tuple[int, Optional[Route]]:
        prunes = 0
        target_route = None
        window = max(3, int(self.base_window_size * intensity))
        
        for r in routes:
            if len(r.path) <= window: continue
            best_reduction = 0
            best_path = None
            
            for i in range(len(r.path) - window):
                if i + window >= len(r.path): break
                segment_start = r.path[i].start
                segment_end = r.path[i + window - 1].end
                direct_path = self._get_shortest_path_edges(segment_start, segment_end)
                
                if direct_path and len(direct_path) < window:
                    reduction = window - len(direct_path)
                    if reduction > best_reduction:
                        candidate_path = self._safe_splice(r.path, i, i + window, direct_path)
                        if candidate_path:
                            best_reduction = reduction
                            best_path = candidate_path
            
            if best_path:
                r.path = best_path
                prunes += 1
                target_route = r
                break 
        return prunes, target_route

    def optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict, intensity: float = 1.0) -> dict:
        actions = {"attraction": False, "repulsion": False, "prunes": 0}
        if random.random() < self.p_local:
            actions["attraction"] = self.strategy_spatial_attraction(routes, pheromones, gaps, intensity) is not None
        if random.random() < self.p_local:
            actions["repulsion"] = self.strategy_redundancy_repulsion(routes, gaps, intensity) is not None
        if random.random() < (self.p_local * 1.5):
            actions["prunes"], _ = self.strategy_tortuosity_pruning(routes, intensity)
        return actions
