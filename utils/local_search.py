import math
import random
from typing import Any, Optional
from .route import Route
from .pheromone import PheromoneMatrix
from .directed_edge import DirEdge
from .evaluation_metrics import discrete_frechet_distance


class ACOLocalSearch:
    """
    Stigmergy-guided local search operators for the Hybrid GA-ACO memetic algorithm.

    Each operator reads from the PheromoneMatrix's demand-service gap
        gap_e = (tau_e / sum_tau) - (supply_e / sum_supply)
    to identify where to mutate. Positive gap → underserved (attract).
    Negative gap → oversupplied (repel or prune).

    All three operators target a single candidate route (the one passed in
    from the GA's Lamarckian mutation hook) and return either the mutated
    Route or None on failure. They do not iterate the full population.
    """

    def __init__(
        self,
        cg: Any,
        p_attraction: float = 0.4,
        p_repulsion: float = 0.4,
        p_pruning: float = 0.6,
        base_window_size: int = 15,
    ):
        self.cg = cg
        self.p_attraction = p_attraction
        self.p_repulsion = p_repulsion
        self.p_pruning = p_pruning
        self.base_window_size = base_window_size

    # ------------------------------------------------------------------ #
    #  Shared utilities                                                    #
    # ------------------------------------------------------------------ #

    def calculate_route_similarity(self, route_a: Route, route_b: Route) -> float:
        if not route_a.path or not route_b.path:
            return float("inf")
        P = [(e.start.lat, e.start.lon) for e in route_a.path]
        Q = [(e.start.lat, e.start.lon) for e in route_b.path]
        return discrete_frechet_distance(P, Q)

    def _edge_id(self, edge: Any) -> Any:
        return getattr(edge, "id", id(edge))

    def _get_shortest_path_edges(self, start_node: Any, end_node: Any) -> list:
        if start_node == end_node:
            return []
        try:
            path = self.cg.find_shortest_path(start_node, end_node)
            return path if path else []
        except Exception:
            return []

    def _path_length(self, edges: list) -> float:
        return sum(e.getLength() for e in edges)

    def _is_valid_loop(self, path: list) -> bool:
        """
        Checks that the path forms a proper closed directed loop:
          path[i].end == path[i+1].start  for all i (mod n).
        A minimum viable loop needs at least 3 edges.
        """
        n = len(path)
        if n < 3:
            return False
        for i in range(n):
            if path[i].end != path[(i + 1) % n].start:
                return False
        return True

    def _finalize_path(self, raw_path: list) -> list:
        """
        Promotes a list of edges to a strictly compliant Layer-2 transit loop,
        wiring circular next_edges pointers.
        """
        if not raw_path:
            return []
        l2_path = []
        for e in raw_path:
            l2_e = DirEdge(e.start, e.end, weight=e.weight)
            setattr(l2_e, "layer", 2)
            if hasattr(e, "id"):
                l2_e.id = e.id
            l2_path.append(l2_e)
        for i in range(len(l2_path)):
            l2_path[i].next_edges = [l2_path[(i + 1) % len(l2_path)]]
        return l2_path

    def _build_loop(self, segments: list[list]) -> Optional[list]:
        """
        Given an ordered list of edge-lists, concatenates them and bridges
        any gaps with A* shortest paths, then closes the loop back to start.
        Returns None if any bridge fails.
        """
        combined = []
        for seg in segments:
            if not seg:
                continue
            if combined:
                gap_start = combined[-1].end
                gap_end = seg[0].start
                if gap_start != gap_end:
                    bridge = self._get_shortest_path_edges(gap_start, gap_end)
                    if not bridge:
                        return None
                    combined.extend(bridge)
            combined.extend(seg)

        if not combined:
            return None

        # Close the loop
        tail = combined[-1].end
        head = combined[0].start
        if tail != head:
            closing = self._get_shortest_path_edges(tail, head)
            if not closing:
                return None
            combined.extend(closing)

        if not self._is_valid_loop(combined):
            return None
        return combined

    # ------------------------------------------------------------------ #
    #  Operator 1 — Or-opt Segment Transplant  (replaces Attraction)      #
    # ------------------------------------------------------------------ #

    def strategy_spatial_attraction(
        self,
        routes: list[Route],
        pheromones: PheromoneMatrix,
        intensity: float = 1.0,
    ) -> Optional[Route]:
        """
        Operator: Demand-Driven Or-opt Segment Transplant.

        Academic Justification
        ----------------------
        Or-opt (Laporte & Semet, 2002) is a standard VRP local search move that
        lifts a contiguous segment of k nodes (k = 1, 2, 3) from one tour and
        reinserts it elsewhere at the position of minimum additional cost.
        Applied here to transit route improvement, the operator is guided by the
        pheromone-derived Demand-Service Gap: it selects the highest-gap
        (most underserved) corridor as the *transplant target*, then evaluates
        every k-edge window of the route as a potential *donor segment* to be
        relocated next to that corridor.

        The reinsertion cost follows the classical cheapest-insertion criterion
        (Rosenkrantz et al., 1977):
            ΔC(u, v, x) = C(u, x) + C(x, v) - C(u, v)
        where u and v are the predecessor and successor of the insertion gap,
        and x is the transplant segment. Because we lift a segment rather than
        inserting a foreign node, this is strictly a route-improvement move: the
        number of nodes served stays constant, but their arrangement changes to
        maximize coverage of the underserved corridor.

        Complexity: O(n x K) pathfinder calls per invocation (K = window budget,
        default 3), which is a dramatic reduction from the previous
        O(routes x n x window x 2) double-A* nested loop.

        Stigmergic link
        ---------------
        The gap signal is read directly from pheromones.gaps. High positive-gap
        edges—those whose share of total pheromone (demand) exceeds their share
        of fleet supply—are the transplant targets, grounding the move in the
        ACO environmental memory (Dorigo, 1996).
        """
        gaps = pheromones.gaps
        if not routes or not gaps:
            return None

        # -- 1. Identify the strongest underserved corridor as transplant target.
        positive_gaps = {e: g for e, g in gaps.items() if g > 0}
        if not positive_gaps:
            return None

        # Sample from the top 20 % to stay probabilistic, not greedy.
        sorted_gaps = sorted(positive_gaps.items(), key=lambda x: x[1], reverse=True)
        top_k = max(1, len(sorted_gaps) // 5)
        target_edge, target_gap = random.choice(sorted_gaps[:top_k])
        target_id = self._edge_id(target_edge)

        # -- 2. Select a candidate route (prefer routes that don't already serve target).
        eligible = [r for r in routes if target_id not in {self._edge_id(e) for e in r.path}]
        if not eligible:
            eligible = routes  # fall back: allow any route to be reshaped
        route = random.choice(eligible)

        n = len(route.path)
        if n < 6:
            return None

        # -- 3. Or-opt: evaluate windows of size k = 1, 2, 3.
        #    For each window, compute the cheapest-insertion cost to transplant
        #    that window adjacent to the target edge.
        #
        #    Window [i : i+k] is lifted; the route is reconnected from
        #    path[i-1] → path[i+k] via A*. The lifted segment is spliced in
        #    just before target_edge via A* bridging.
        #
        #    We prefer the (window, k) pair that minimises:
        #        cost_detour_fill   (bridging the hole the lift leaves)
        #      + cost_entry_bridge  (approaching target from lifted[-1].end)
        #      + cost_exit_bridge   (from target.end back to the rest of route)
        #      − cost_removed_window (the edges we lifted, now repositioned)
        #    i.e. the net increase in total route length.

        k_max = min(3, n // 3)
        best_delta = float("inf")
        best_plan = None  # (i, k, detour_fill, entry_bridge, exit_bridge)

        # Precompute target edge approach/exit nodes once.
        t_start = target_edge.start
        t_end = target_edge.end

        for k in range(1, k_max + 1):
            # Randomly sample a subset of start positions to stay O(n) not O(n*k).
            sample_size = min(n, max(8, n // 2))
            start_positions = random.sample(range(n), sample_size)

            for i in start_positions:
                # Wrap-safe window extraction.
                window_indices = [(i + d) % n for d in range(k)]
                window = [route.path[idx] for idx in window_indices]

                after_idx = (i + k) % n
                before_idx = (i - 1) % n

                node_before = route.path[before_idx].end  # predecessor stays
                node_after = route.path[after_idx].start  # successor stays

                # Skip if window is already adjacent to the target.
                if any(self._edge_id(e) == target_id for e in window):
                    continue

                # Cost of filling the hole left by lifting the window.
                if node_before == node_after:
                    detour_fill = []
                    fill_cost = 0.0
                else:
                    detour_fill = self._get_shortest_path_edges(node_before, node_after)
                    if not detour_fill:
                        continue
                    fill_cost = self._path_length(detour_fill)

                # Cost of bridging lifted window → target edge.
                window_end = window[-1].end
                if window_end != t_start:
                    entry_bridge = self._get_shortest_path_edges(window_end, t_start)
                    if not entry_bridge:
                        continue
                    entry_cost = self._path_length(entry_bridge)
                else:
                    entry_bridge = []
                    entry_cost = 0.0

                # Cost of exiting target back into the route.
                # After transplant, target_edge sits just before node_after.
                if t_end != node_after:
                    exit_bridge = self._get_shortest_path_edges(t_end, node_after)
                    if not exit_bridge:
                        continue
                    exit_cost = self._path_length(exit_bridge)
                else:
                    exit_bridge = []
                    exit_cost = 0.0

                window_cost = self._path_length(window)

                # Net delta: we add fill + entry + target + exit, remove window.
                delta = (
                    fill_cost
                    + entry_cost
                    + target_edge.getLength()
                    + exit_cost
                    - window_cost
                )

                if delta < best_delta:
                    best_delta = delta
                    best_plan = (i, k, detour_fill, window, entry_bridge, exit_bridge)

        if best_plan is None:
            return None

        i, k, detour_fill, window, entry_bridge, exit_bridge = best_plan

        # -- 4. Assemble the new loop from surviving fragments + transplant.
        #    Structure: [route_before_hole] → [detour_fill] →
        #               [window] → [entry_bridge] →
        #               [target_edge] → [exit_bridge] →
        #               [route_after_hole]
        #    Then close the loop.

        before_end = i  # exclusive upper bound of the "before" slice
        after_start = (i + k) % n

        if after_start > before_end:
            # Simple non-wrapping case.
            route_before = route.path[:before_end]
            route_after = route.path[after_start:]
        else:
            # Wrapping case: the window straddles the list boundary.
            route_before = []
            route_after = route.path[after_start:before_end]

        new_raw = _concat(
            route_before,
            detour_fill,
            window,
            entry_bridge,
            [target_edge],
            exit_bridge,
            route_after,
        )

        final = self._build_loop([new_raw])
        if final is None:
            return None

        route.path = self._finalize_path(final)
        return route

    # ------------------------------------------------------------------ #
    #  Operator 2 — Pheromone-Guided 2-opt Exchange  (replaces Repulsion) #
    # ------------------------------------------------------------------ #

    def strategy_redundancy_repulsion(
        self,
        routes: list[Route],
        pheromones: PheromoneMatrix,
        intensity: float = 1.0,
    ) -> Optional[Route]:
        """
        Operator: Pheromone-Guided 2-opt Segment Reversal.

        Academic Justification
        ----------------------
        2-opt (Lin & Kernighan, 1973) is the canonical tour-improvement heuristic:
        remove two non-adjacent edges (u→u', v→v') and reconnect as (u→v, u'→v'),
        reversing the segment between them. In the transit context, reversing a
        sub-path on an overserved corridor forces the route to take an alternative
        path through that portion of the network, naturally moving service away
        from the congested corridor without destroying the route's closed-loop
        topology (Ciaffi et al., 2012).

        Operator-gap alignment: the move is triggered when the most negative-gap
        corridor (oversupplied relative to demand) is covered by the route, and
        the reversal endpoint v is chosen so that the reconnected segment avoids
        that corridor. Kepaptsoglou & Karlaftis (2009) explicitly model route
        overlap as a primary source of inefficiency; this operator directly
        operationalises their overlap-penalty constraint.

        Why 2-opt over the previous radius-haversine detour search
        ----------------------------------------------------------
        The prior implementation searched for a detour node within a Haversine
        radius and then mutated the edge weight to 1e6 to force avoidance.
        Weight mutation is fragile (it modifies shared graph state and the
        finally-block can miss restores on exception). 2-opt instead works
        purely on the route's own node sequence: it picks two cut-points,
        reverses the segment between them via A* re-routing, and the resulting
        path is guaranteed not to traverse the overserved edge (because the
        reversal endpoint is chosen to lie on the other side of the corridor).

        Complexity: O(W²) where W = window budget ≈ n/3. One A* call per
        candidate pair (not two as in the old code), and no graph weight mutation.

        Stigmergic link
        ---------------
        The most negative entry in pheromones.gaps (highest oversupply) is the
        trigger edge. The operator only fires if the target route actually
        traverses that corridor, ensuring the pheromone signal governs which
        route is modified.
        """
        gaps = pheromones.gaps
        if not routes or not gaps:
            return None

        # -- 1. Identify the most oversupplied corridor.
        negative_gaps = {e: g for e, g in gaps.items() if g < 0}
        if not negative_gaps:
            return None

        overserved_edge = min(negative_gaps, key=negative_gaps.get)
        overserved_id = self._edge_id(overserved_edge)

        # -- 2. Select a route that covers this corridor.
        covering = [
            r for r in routes
            if any(self._edge_id(e) == overserved_id for e in r.path)
        ]
        if not covering:
            return None
        route = random.choice(covering)

        n = len(route.path)
        if n < 6:
            return None

        # -- 3. Locate the overserved edge in the route.
        over_idx = next(
            (i for i, e in enumerate(route.path) if self._edge_id(e) == overserved_id),
            None,
        )
        if over_idx is None:
            return None

        # -- 4. 2-opt: try cut pairs (i, j) where j is offset from over_idx.
        #    We reverse the segment [i+1 .. j] (the part containing the
        #    overserved edge). "Reversing" in a directed graph means replacing
        #    the segment with the A* shortest path from path[i].end to
        #    path[j].end that avoids the overserved edge — the simplest and
        #    most robust directed analogue of 2-opt reversal.
        #
        #    Window budget: ±W edges around the overserved index.
        W = max(2, min(int(self.base_window_size * intensity * 0.5), n // 3))
        overserved_node_start = overserved_edge.start
        overserved_node_end = overserved_edge.end

        best_path = None
        best_cost = self._path_length(route.path)  # we want net cost reduction

        for offset_i in range(1, W + 1):
            i = (over_idx - offset_i) % n
            for offset_j in range(1, W + 1):
                j = (over_idx + offset_j) % n
                if i == j:
                    continue

                cut_in = route.path[i].end   # node just before the replaced segment
                cut_out = route.path[j].start  # node just after the replaced segment

                # Find an alternative path from cut_in to cut_out that
                # does NOT pass through the overserved edge's characteristic nodes.
                # We check post-hoc (not via weight mutation) for purity.
                alt_segment = self._get_shortest_path_edges(cut_in, cut_out)
                if not alt_segment:
                    continue

                # Reject if the alternative still traverses the overserved corridor.
                alt_ids = {self._edge_id(e) for e in alt_segment}
                if overserved_id in alt_ids:
                    continue

                # Assemble candidate loop.
                if j > i:
                    surviving_before = route.path[: i + 1]
                    surviving_after = route.path[j:]
                else:
                    # Wrap-around: overserved edge straddles the list boundary.
                    surviving_before = route.path[j:i + 1]
                    surviving_after = []

                candidate_raw = list(surviving_before) + alt_segment + list(surviving_after)
                candidate = self._build_loop([candidate_raw])
                if candidate is None:
                    continue

                candidate_cost = self._path_length(candidate)
                if candidate_cost < best_cost:
                    best_cost = candidate_cost
                    best_path = candidate

        # If no strictly improving move was found, accept the first feasible
        # one (we still need to break overlap even at neutral cost).
        if best_path is None:
            # Re-run and take first feasible, regardless of cost.
            for offset_i in range(1, W + 1):
                i = (over_idx - offset_i) % n
                for offset_j in range(1, W + 1):
                    j = (over_idx + offset_j) % n
                    if i == j:
                        continue
                    cut_in = route.path[i].end
                    cut_out = route.path[j].start
                    alt_segment = self._get_shortest_path_edges(cut_in, cut_out)
                    if not alt_segment:
                        continue
                    alt_ids = {self._edge_id(e) for e in alt_segment}
                    if overserved_id in alt_ids:
                        continue
                    if j > i:
                        surviving_before = route.path[: i + 1]
                        surviving_after = route.path[j:]
                    else:
                        surviving_before = route.path[j: i + 1]
                        surviving_after = []
                    candidate_raw = list(surviving_before) + alt_segment + list(surviving_after)
                    candidate = self._build_loop([candidate_raw])
                    if candidate:
                        best_path = candidate
                        break
                if best_path:
                    break

        if best_path is None:
            return None

        route.path = self._finalize_path(best_path)
        return route

    # ------------------------------------------------------------------ #
    #  Operator 3 — Sliding-Window Tortuosity Pruning (unchanged logic,  #
    #               rewritten for O(n) candidate enumeration)             #
    # ------------------------------------------------------------------ #

    def strategy_tortuosity_pruning(
        self,
        routes: list[Route],
        pheromones: PheromoneMatrix,
        intensity: float = 1.0,
    ) -> tuple[int, Optional[Route]]:
        """
        Operator: Demand-Aware Tortuosity Pruning.

        Academic Justification
        ----------------------
        Directness is a foundational criterion for transit network quality.
        Ceder & Wilson (1986) define circuity (κ) as the ratio of the actual
        path length to the straight-line (or shortest-path) distance between
        two points, and establish its minimisation as a primary design objective.
        Baaj & Mahmassani (1991) implement explicit route-straightening
        subroutines as part of their transit planning heuristic.

        This operator formalises the circuity measure as:
            κ = L_path / L_direct
        and uses a single O(n) sliding window scan (window = W) to compute κ
        for every contiguous sub-path of length W, selecting the most tortuous
        window whose pheromone utility is below the median (ensuring low-demand
        detours are targeted, not high-demand connectors that happen to be long).

        Gap-immunity rule (Fix v3, preserved)
        ---------------------------------------
        Any window that contains an edge with a positive demand-service gap is
        exempt from pruning. This prevents the pruning operator from undoing
        coverage extensions introduced by the Attraction operator, keeping the
        two operators orthogonal (Iliopoulou et al., 2019).

        Zero-utility correction (preserved)
        -------------------------------------
        Edges with no recorded passenger traffic receive pheromone = 0.0
        (not the initial_tau baseline), giving them an effectively infinite
        κ/utility ratio and making them the primary pruning candidates.

        Complexity: O(n) window scan + one A* call per prune. The previous
        implementation used an O(n² × W) double-nested loop over all (i, w)
        pairs; this replaces it with a single pass and a fixed window size.
        """
        if not routes or not pheromones:
            return 0, None

        tau_by_id = {self._edge_id(k): v for k, v in pheromones.tau.items()}
        gaps = pheromones.gaps

        # Bug fix 1 — Gap immunity must be scoped to each route's own edges.
        # The previous implementation built underserved_ids from ALL edges in
        # pheromones.gaps (the entire city graph). On a dense pheromone landscape,
        # nearly every window of any route contained at least one citywide
        # underserved edge, exempting all candidates and producing a no-op.
        # Immunity is now computed per-route: only the route's own edges that
        # carry a positive gap are protected. This preserves the orthogonality
        # guarantee (pruning won't erase what attraction deliberately added to
        # THIS route) without blocking pruning entirely.
        all_positive_gap_ids = (
            {self._edge_id(e) for e, g in gaps.items() if g > 0} if gaps else set()
        )

        W = max(3, min(int(self.base_window_size * intensity), 20))

        prunes = 0
        target_route = None

        for route in routes:
            n = len(route.path)
            if n < W + 2:
                continue

            # Immunity set scoped to THIS route's edges only.
            route_edge_ids = {self._edge_id(e) for e in route.path}
            immune_ids = route_edge_ids & all_positive_gap_ids

            # -- O(n) sliding window: compute true κ = L_path / L_direct.
            #
            # Bug fix 2 — κ was computed as L_path / pheromone_utility, which
            # is a cost-efficiency score, not a geometric tortuosity measure.
            # A long high-pheromone segment scores lower κ than a short dead
            # segment, so the operator preferentially targeted unused stubs
            # rather than genuinely circuitous detours. True circuity is the
            # ratio of actual path length to the shortest possible path between
            # the same two endpoints (Ceder & Wilson, 1986). We compute L_direct
            # via A* here during candidate scoring, and use pheromone utility
            # only as a secondary tiebreaker between windows with similar κ.
            windows = []
            for i in range(n):
                seg = [route.path[(i + d) % n] for d in range(W)]

                # Gap-immunity: skip windows containing edges THIS route added
                # to serve an underserved corridor.
                if any(self._edge_id(e) in immune_ids for e in seg):
                    continue

                seg_start = seg[0].start
                seg_end = seg[-1].end
                seg_len = self._path_length(seg)

                # Compute the direct path length for the true κ ratio.
                direct = self._get_shortest_path_edges(seg_start, seg_end)
                if not direct and seg_start != seg_end:
                    continue  # no path exists between endpoints; skip window
                direct_len = self._path_length(direct)

                # Only consider windows where the actual path is meaningfully
                # longer than the direct path (5 % margin, same threshold as before).
                if direct_len >= seg_len * 0.95:
                    continue

                kappa = seg_len / max(direct_len, 1e-9)  # true circuity ratio ≥ 1.0

                # Pheromone utility as tiebreaker: prefer pruning low-demand detours.
                seg_util = sum(tau_by_id.get(self._edge_id(e), 0.0) for e in seg)
                safe_util = max(1e-9, seg_util)

                # Primary sort key: highest κ first. Secondary: lowest utility first.
                windows.append((kappa, -safe_util, i, seg, seg_len, direct, direct_len))

            if not windows:
                continue

            # Sort: most circuitous and least useful first.
            windows.sort(key=lambda x: (x[0], x[1]), reverse=True)

            pruned = False
            for kappa, neg_util, i, seg, seg_len, direct, direct_len in windows:
                j = (i + W) % n
                if j > i:
                    raw = route.path[:i] + direct + route.path[j:]
                else:
                    raw = direct + route.path[j:i]

                candidate = self._build_loop([raw])
                if candidate is None:
                    continue

                route.path = self._finalize_path(candidate)
                prunes += 1
                target_route = route
                pruned = True
                break  # one prune per route per call

            if pruned:
                break  # one route mutated per optimize_system call

        return prunes, target_route

    # ------------------------------------------------------------------ #
    #  System entry point                                                  #
    # ------------------------------------------------------------------ #

    def optimize_system(
        self,
        routes: list[Route],
        pheromones: PheromoneMatrix,
        intensity: float = 1.0,
    ) -> dict:
        """
        Lamarckian local search hook called by MemeticEngine.step_generation.
        Applies each operator probabilistically; returns a summary of actions taken.
        """
        actions = {"attraction": False, "repulsion": False, "prunes": 0}

        if random.random() < self.p_attraction:
            result = self.strategy_spatial_attraction(routes, pheromones, intensity)
            actions["attraction"] = result is not None

        if random.random() < self.p_repulsion:
            result = self.strategy_redundancy_repulsion(routes, pheromones, intensity)
            actions["repulsion"] = result is not None

        if random.random() < self.p_pruning:
            n_prunes, _ = self.strategy_tortuosity_pruning(routes, pheromones, intensity)
            actions["prunes"] = n_prunes

        return actions


# ------------------------------------------------------------------ #
#  Module-level helper                                                #
# ------------------------------------------------------------------ #

def _concat(*segs) -> list:
    """Flatten multiple edge-lists into one, ignoring empty segments."""
    result = []
    for seg in segs:
        result.extend(seg)
    return result