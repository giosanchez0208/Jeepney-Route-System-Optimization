import math
import random
from typing import Any, Optional
from .route import Route
from .pheromone import PheromoneMatrix
from .directed_edge import DirEdge
from .evaluation_metrics import discrete_frechet_distance


class ACOLocalSearch:
    def __init__(self, cg: Any, p_attraction: float = 0.4, p_repulsion: float = 0.4, p_pruning: float = 0.6, base_window_size: int = 15):
        self.cg = cg
        self.p_attraction = p_attraction
        self.p_repulsion = p_repulsion
        self.p_pruning = p_pruning
        self.base_window_size = base_window_size

    def calculate_route_similarity(self, route_a: Route, route_b: Route) -> float:
        if not route_a.path or not route_b.path: return float('inf')
        P = [(e.start.lat, e.start.lon) for e in route_a.path]
        Q = [(e.start.lat, e.start.lon) for e in route_b.path]
        return discrete_frechet_distance(P, Q)

    def _get_shortest_path_edges(self, start_node: Any, end_node: Any) -> list[Any]:
        if start_node == end_node: return []
        try:
            path = self.cg.find_shortest_path(start_node, end_node)
            return path if path else []
        except Exception:
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
                for e in bridge:
                    if not stitched or stitched[-1].id != e.id:
                        stitched.append(e)

            if not stitched or stitched[-1].id != next_edge.id:
                stitched.append(next_edge)

        if stitched and stitched[-1].end != stitched[0].start:
            loop_bridge = self._get_shortest_path_edges(stitched[-1].end, stitched[0].start)
            if not loop_bridge: return None
            for e in loop_bridge:
                if not stitched or stitched[-1].id != e.id:
                    stitched.append(e)

        return stitched

    def _safe_splice(self, path: list, start_idx: int, end_idx: int, new_segment: list) -> Optional[list]:
        if not new_segment: return None
        raw_path = path[:start_idx] + new_segment + path[end_idx:]
        return self._stitch_path(raw_path)

    def _edge_id(self, edge: Any) -> Any:
        """Stable identity key for an edge, robust to missing __eq__/__hash__."""
        return getattr(edge, 'id', id(edge))

    def _finalize_path(self, raw_path: list) -> list:
        """Upgrades a mixed-layer path into a strictly compliant Layer 2 transit loop."""
        if not raw_path: return []
        l2_path = []
        for e in raw_path:
            l2_e = DirEdge(e.start, e.end, weight=e.weight)
            setattr(l2_e, 'layer', 2)
            if hasattr(e, 'id'):
                l2_e.id = e.id
            l2_path.append(l2_e)
            
        for i in range(len(l2_path)):
            l2_path[i].next_edges = [l2_path[(i + 1) % len(l2_path)]]
            
        return l2_path

    def strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> Optional[Route]:
        """
        Operator: Demand-Driven Attraction (Coverage / Spatial Attraction Heuristic).

        Academic Justification:
            Gravity-Based Local Search / Spatial Attraction Heuristic.
            Transit networks must adapt to underserved demand hotspots to maximize coverage and market capture
            (Nielsen et al., 2005). Demand-based node insertion is the primary local search operator in TNDP
            metaheuristics to capture unserved market share (Iliopoulou et al., 2019).
            Instead of replacing an entire route, this operator identifies contiguous sequences of low-pheromone 
            (underutilized) edges, computes the proximity to high Demand-Service Gap (delta_e) clusters, and 
            probabilistically bends the route toward those hotspots via cheapest-insertion path stitching,
            extending coverage without destroying existing connectivity.

        Fix 1 (v1): Removed the inverted pheromone gate that blocked the best candidate routes.
        Fix 2 (v1): Replaced closest-edge proximity with cheapest-insertion cost scoring.
        Fix 3 (v2): Corrected splice from window-based replacement to a true zero-width insertion.
          The v1 code excised a window of existing edges around the insertion point and replaced
          them with just the target edge — deleting coverage, not adding it. A pure insertion
          uses path[:idx] + [target_edge] + path[idx:] before stitching, preserving all existing
          edges.
        Fix 4 (v2): Removed the dead `saved` term from the cheapest-insertion score. On a
          properly connected loop path[i].end == path[i+1].start always, so saved == 0 always.
          The score is simply d_entry + d_exit.
        """
        gaps = pheromones.gaps
        if not routes or not gaps: return None

        positive_gaps = {e: gap for e, gap in gaps.items() if gap > 0}
        if not positive_gaps: return None

        sorted_gaps = sorted(positive_gaps.items(), key=lambda x: x[1], reverse=True)
        candidate_targets = sorted_gaps[:max(1, int(len(sorted_gaps) * 0.3))]
        random.shuffle(candidate_targets)

        for target_edge, _ in candidate_targets:
            target_id = self._edge_id(target_edge)

            best_route      = None
            best_insert_idx = -1
            min_detour_cost = float('inf')

            for r in routes:
                route_edge_ids = {self._edge_id(e) for e in r.path}
                if target_id in route_edge_ids:
                    continue  

                n = len(r.path)
                for i in range(n):
                    entry_node = r.path[i].end
                    exit_node  = r.path[(i + 1) % n].start

                    d_entry = math.sqrt(
                        (entry_node.lat - target_edge.start.lat) ** 2 +
                        (entry_node.lon - target_edge.start.lon) ** 2
                    )
                    d_exit = math.sqrt(
                        (target_edge.end.lat - exit_node.lat) ** 2 +
                        (target_edge.end.lon - exit_node.lon) ** 2
                    )
                    detour_cost = d_entry + d_exit

                    if detour_cost < min_detour_cost:
                        min_detour_cost = detour_cost
                        best_route      = r
                        best_insert_idx = i + 1  

            if best_route is not None and best_insert_idx != -1:
                raw_path   = best_route.path[:best_insert_idx] + [target_edge] + best_route.path[best_insert_idx:]
                final_path = self._stitch_path(raw_path)
                if final_path:
                    best_route.path = self._finalize_path(final_path)
                    return best_route

        return None

    def strategy_redundancy_repulsion(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> Optional[Route]:
        """
        Operator: Oversupply Repulsion (Efficiency / Dispersion Routing).

        Academic Justification:
            Dispersion Routing / Route Overlap Minimization.
            Operator viability requires minimizing redundant vehicle kilometers and deadhead trips. If multiple
            lines overlap entirely, parallel corridors are starved (Silva, 2024). Informal transit networks
            naturally cluster on main arterials, creating hyper-redundancy (Global GNPT & UNDP, 2024).
            Moving a highly useful segment away from a low-served area provides no mathematical benefit. If a
            segment is highly useful, it is exactly where passengers need it to be. However, if multiple routes
            share the same segment, they create fleet redundancy. This operator isolates one of the overlapping 
            routes and "repels" its segment to a parallel street, maintaining general directional utility 
            while expanding spatial coverage to adjacent blocks.

        Fix 1 (v1): Detour candidates sorted ascending — short, reachable detours tried first.
        Fix 2 (v1): Overserved-edge exclusion uses stable IDs instead of object identity.
        Fix 3 (v2): Excision window clamped to at most 20% of route length. The old formula
          (base_window_size/2 * intensity) at intensity=3 gave window ~22, large enough to excise
          half a short route. The ascending-sort nearby candidates then can't bridge the gap,
          causing consistent fallthrough despite the sort fix.
        """
        gaps = pheromones.gaps
        if not routes or not gaps: return None

        e_overserved = min(gaps, key=gaps.get)
        if gaps[e_overserved] >= 0: return None

        overserved_id      = self._edge_id(e_overserved)
        overlapping_routes = [r for r in routes if any(self._edge_id(e) == overserved_id for e in r.path)]
        if len(overlapping_routes) < 2: return None

        r_target = random.choice(overlapping_routes)

        idx = next((i for i, e in enumerate(r_target.path) if self._edge_id(e) == overserved_id), None)
        if idx is None: return None

        raw_window = max(1, int((self.base_window_size / 2) * intensity))
        max_window = max(1, len(r_target.path) // 5)
        window     = min(raw_window, max_window)

        start_idx = max(0, idx - window // 2)
        end_idx   = min(len(r_target.path), idx + window // 2 + 1)

        node_before = r_target.path[start_idx].start
        node_after  = r_target.path[end_idx - 1].end

        target_radius   = 0.015 * intensity
        candidate_nodes = [n for n in self.cg.nodes if n != node_before and n != node_after]

        valid_detours = []
        for n in candidate_nodes:
            dist_start = math.sqrt((n.lat - node_before.lat) ** 2 + (n.lon - node_before.lon) ** 2)
            dist_end   = math.sqrt((n.lat - node_after.lat)  ** 2 + (n.lon - node_after.lon)  ** 2)
            if dist_start < target_radius and (dist_start + dist_end) < (target_radius * 3):
                valid_detours.append((n, dist_start + dist_end))

        valid_detours.sort(key=lambda x: x[1])

        for detour_node, _ in valid_detours[:20]:
            bridge_in  = self._get_shortest_path_edges(node_before, detour_node)
            if not bridge_in: continue
            bridge_out = self._get_shortest_path_edges(detour_node, node_after)
            if not bridge_out: continue

            bridge_ids = {self._edge_id(e) for e in bridge_in + bridge_out}
            if overserved_id in bridge_ids:
                continue

            new_path = self._safe_splice(r_target.path, start_idx, end_idx, bridge_in + bridge_out)
            if new_path:
                r_target.path = self._finalize_path(new_path)
                return r_target

        return None

    def strategy_tortuosity_pruning(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> tuple[int, Optional[Route]]:
        """
        Operator: Demand-Aware Tortuosity Pruning (Gap-Immune / Tortuosity Reduction).

        Academic Justification:
            Tortuosity Reduction / Route Directness Optimization.
            A robust network relies on a simple structure with clearly defined corridors rather than a highly
            diffuse, complex mesh (Ceder & Wilson, 1986). Circuity or tortuosity penalizes passengers and wastes
            fleet travel time. This operator identifies low-pheromone segments that meander meander between two
            high-demand hubs, amputates the detour entirely, and bridges the gap using the strictly shortest-path 
            calculation available on the city graph. This straightens the route, converting detour cycles into
            high-frequency service along direct corridors.

        Fix (v3): Added gap immunity. The pheromone-weighted score (distance / utility) correctly
          prioritizes low-pheromone detours for pruning — but underserved edges have low pheromone
          by definition, since nothing routes through them yet. This caused pruning to
          preferentially target exactly the detours that attraction added to serve those edges,
          creating a generational feedback loop where attraction's coverage gains were continuously
          erased. Segments containing any positive-gap (underserved) edge are now skipped entirely
          as pruning candidates, making the two operators orthogonal rather than antagonistic.
        """
        if not routes or not pheromones: return 0, None

        prunes       = 0
        target_route = None
        window = max(3, min(int(self.base_window_size * intensity), 30))

        tau_by_id       = {self._edge_id(k): v for k, v in pheromones.tau.items()}
        gaps            = pheromones.gaps
        underserved_ids = {self._edge_id(e) for e, g in gaps.items() if g > 0} if gaps else set()

        for r in routes:
            if len(r.path) <= window: continue

            candidates = []
            for i in range(len(r.path) - window):
                current_segment = r.path[i:i + window]

                if any(self._edge_id(e) in underserved_ids for e in current_segment):
                    continue

                current_distance = sum(e.getLength() for e in current_segment)
                local_utility    = sum(tau_by_id.get(self._edge_id(e), 0.0) for e in current_segment)
                safe_utility     = max(1.0, local_utility)
                score            = current_distance / safe_utility
                candidates.append((score, i, current_segment, current_distance))

            candidates.sort(key=lambda x: x[0], reverse=True)

            best_path = None
            for score, i, current_segment, current_distance in candidates:
                segment_start = current_segment[0].start
                segment_end   = current_segment[-1].end

                direct_path = self._get_shortest_path_edges(segment_start, segment_end)
                if not direct_path: continue

                direct_distance = sum(e.getLength() for e in direct_path)

                if direct_distance < current_distance * 0.95:
                    candidate_path = self._safe_splice(r.path, i, i + window, direct_path)
                    if candidate_path:
                        best_path = candidate_path
                        break

            if best_path:
                r.path = self._finalize_path(best_path)
                prunes      += 1
                target_route = r
                break

        return prunes, target_route

    def optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> dict:
        actions = {"attraction": False, "repulsion": False, "prunes": 0}
        if random.random() < self.p_attraction:
            actions["attraction"] = self.strategy_spatial_attraction(routes, pheromones, intensity) is not None
        if random.random() < self.p_repulsion:
            actions["repulsion"] = self.strategy_redundancy_repulsion(routes, pheromones, intensity) is not None
        if random.random() < self.p_pruning:
            actions["prunes"], _ = self.strategy_tortuosity_pruning(routes, pheromones, intensity)
        return actions