"""
post_evaluation.py

Domain-Specific Evaluation Workflows for Transit Route Optimization.

Provides high-level evaluation methods that operate on transit domain objects
(Route, Chromosome, SimulationResult) and delegate mathematical computation
to evaluation_metrics.py.

Evaluation Categories:
    A. Route Similarity       — Compare two individual routes
    B. System Similarity      — Compare two entire route systems (Chromosomes)
    C. Generational Tracking  — Quantify topological drift and fitness correlation
    D. Surrogate Fidelity     — Validate surrogate evaluator against true simulation
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from .evaluation_metrics import (
    jaccard_similarity,
    cosine_similarity,
    graph_edit_distance,
    discrete_frechet_distance,
    wasserstein_1d,
    wasserstein_2d,
    ks_test,
    shannon_entropy,
    spearman_correlation,
    kendall_tau,
    pearson_correlation,
    top_k_overlap,
    normalized_rmse,
    mape,
)


# ═══════════════════════════════════════════════════════════════════════════════
# A. ROUTE SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════════

def compare_routes_geometric(route_a: Any, route_b: Any) -> float:
    """
    Measures how geometrically similar two routes are, respecting traversal order.

    This is the correct metric for answering: "By how much did the mutation
    change this route?" It captures both spatial displacement and sequential
    deviation — two routes sharing the same streets but traveling in different
    order will register as dissimilar.

    Uses the Discrete Fréchet Distance internally.

    Parameters:
        route_a: A Route object with a .path list of DirEdge objects.
        route_b: A Route object with a .path list of DirEdge objects.

    Returns:
        float ≥ 0.0. 0.0 = identical geometry. Higher = more divergent.
        Returns inf if either route has an empty path.
    """
    if not route_a.path or not route_b.path:
        return float('inf')

    P = [(e.start.lat, e.start.lon) for e in route_a.path]
    Q = [(e.start.lat, e.start.lon) for e in route_b.path]

    return discrete_frechet_distance(P, Q)


def compare_routes_topological(route_a: Any, route_b: Any) -> float:
    """
    Measures the edge set overlap between two routes. Ignores geometry and
    traversal order — asks only "do these routes use the same streets?"

    Uses Jaccard Similarity internally.

    Parameters:
        route_a: A Route object.
        route_b: A Route object.

    Returns:
        float ∈ [0.0, 1.0]. 1.0 = identical edge sets.
    """
    edges_a = _extract_edge_ids(route_a)
    edges_b = _extract_edge_ids(route_b)

    return jaccard_similarity(edges_a, edges_b)


# ═══════════════════════════════════════════════════════════════════════════════
# B. SYSTEM SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════════

def compare_systems_topological(chrom_a: Any, chrom_b: Any) -> float:
    """
    Computes the aggregate topological overlap between two route systems.

    Extracts the union of all edge IDs across all routes in each chromosome
    and computes the Jaccard similarity of the two aggregate edge sets.

    Answers: "How much do these two systems overlap in the streets they serve?"

    Parameters:
        chrom_a: A Chromosome object with a .routes list.
        chrom_b: A Chromosome object with a .routes list.

    Returns:
        float ∈ [0.0, 1.0]. 1.0 = identical network coverage.
    """
    edges_a = _extract_system_edge_ids(chrom_a)
    edges_b = _extract_system_edge_ids(chrom_b)

    return jaccard_similarity(edges_a, edges_b)


def compare_systems_structural(chrom_a: Any, chrom_b: Any, max_nodes: int = 15) -> float:
    """
    Computes the Graph Edit Distance between two route system topologies.

    Unlike Jaccard (which only measures overlap), GED quantifies the minimum
    number of structural modifications (edge/node insertions, deletions,
    substitutions) required to transform System A into System B.

    Answers: "How many structural edits separate these two systems?"

    Parameters:
        chrom_a: A Chromosome object.
        chrom_b: A Chromosome object.
        max_nodes: Maximum hub nodes to retain per system (controls complexity).

    Returns:
        float ≥ 0.0. 0.0 = identical structure.
    """
    edges_a = _collect_all_edges(chrom_a)
    edges_b = _collect_all_edges(chrom_b)

    return graph_edit_distance(edges_a, edges_b, max_nodes=max_nodes)


def compare_systems_degree_distribution(chrom_a: Any, chrom_b: Any) -> float:
    """
    Computes the cosine similarity between the node degree distributions
    of two route systems.

    Answers: "Do these two systems distribute connectivity similarly across
    the city?" High cosine similarity means the same nodes serve as hubs
    in both systems, even if the specific edges differ.

    Parameters:
        chrom_a: A Chromosome object.
        chrom_b: A Chromosome object.

    Returns:
        float ∈ [0.0, 1.0]. 1.0 = identical degree distributions.
    """
    degrees_a = _extract_node_degrees(chrom_a)
    degrees_b = _extract_node_degrees(chrom_b)

    return cosine_similarity(degrees_a, degrees_b)


def compare_systems_demand_coverage(
    chrom_a: Any,
    chrom_b: Any,
    sampler: Any
) -> float:
    """
    Computes the Wasserstein distance between the demand coverage distributions
    of two route systems.

    For each system, this method computes how much of the demand surface each
    route node covers (weighted by the demand probability at that node). The
    Wasserstein distance then measures the minimum "work" to reshape System A's
    coverage into System B's coverage.

    Answers: "How differently do these two systems cover the demand surface?"

    Parameters:
        chrom_a: A Chromosome object.
        chrom_b: A Chromosome object.
        sampler: A DirectDemandSampler with .node_probabilities dict.

    Returns:
        float ≥ 0.0. 0.0 = identical demand coverage.
    """
    coords_a, weights_a = _extract_demand_coverage(chrom_a, sampler)
    coords_b, weights_b = _extract_demand_coverage(chrom_b, sampler)

    if not coords_a or not coords_b:
        return 0.0

    return wasserstein_2d(coords_a, weights_a, coords_b, weights_b)


# ═══════════════════════════════════════════════════════════════════════════════
# C. GENERATIONAL TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def track_topological_drift(gen_chromosomes: List[Any]) -> List[float]:
    """
    Given a sequence of best-chromosomes across generations, computes the
    pairwise Jaccard similarity between consecutive generations to measure
    how much the route topology changed over time.

    Answers: "How much did the topology change from generation to generation?"

    Parameters:
        gen_chromosomes: Ordered list of best Chromosome objects, one per generation.

    Returns:
        List of Jaccard similarity values (length = len(gen_chromosomes) - 1).
        Each value measures the topological overlap between consecutive generations.
    """
    if len(gen_chromosomes) < 2:
        return []

    similarities = []
    for i in range(len(gen_chromosomes) - 1):
        sim = compare_systems_topological(gen_chromosomes[i], gen_chromosomes[i + 1])
        similarities.append(sim)

    return similarities


def track_fitness_correlation(
    gen_chromosomes: List[Any]
) -> Tuple[float, List[float], List[float]]:
    """
    Correlates topological change (1 - Jaccard) with fitness improvement (Δcost)
    across consecutive generations.

    Answers: "Does changing the topology actually improve fitness?"

    A strong negative correlation means topological changes reliably produce
    fitness improvements. A weak or positive correlation suggests the algorithm
    is making structural changes that don't improve (or actively harm) the
    objective function.

    Parameters:
        gen_chromosomes: Ordered list of best Chromosome objects with .cost attributes.

    Returns:
        (pearson_r, topology_deltas, fitness_deltas)
        - pearson_r: The Pearson correlation between topology change and fitness change.
        - topology_deltas: List of (1 - Jaccard) values per generation transition.
        - fitness_deltas: List of cost differences (gen[i+1].cost - gen[i].cost).
    """
    if len(gen_chromosomes) < 3:
        return 0.0, [], []

    topology_deltas = []
    fitness_deltas = []

    for i in range(len(gen_chromosomes) - 1):
        jac = compare_systems_topological(gen_chromosomes[i], gen_chromosomes[i + 1])
        topo_change = 1.0 - jac
        cost_change = gen_chromosomes[i + 1].cost - gen_chromosomes[i].cost

        topology_deltas.append(topo_change)
        fitness_deltas.append(cost_change)

    r = pearson_correlation(topology_deltas, fitness_deltas)
    return r, topology_deltas, fitness_deltas


def compute_path_diversity(recorded_paths: List[Tuple[Any, float]]) -> float:
    """
    Computes the Shannon entropy over the passenger path frequency distribution.

    Answers: "How many distinct routing options does this system offer?"

    High entropy means passengers are distributed across many distinct paths
    (the system offers genuine multi-modal choice). Low entropy means most
    passengers are funneled through the same path (the system is a bottleneck).

    Parameters:
        recorded_paths: A list of (path, cost) tuples from a SimulationResult.

    Returns:
        float ≥ 0.0 in bits. Higher = more diverse routing.
    """
    if not recorded_paths:
        return 0.0

    path_counts: Dict[str, int] = {}
    for path, _ in recorded_paths:
        # Hash path by its sequence of edge IDs
        if hasattr(path, '__iter__'):
            key = tuple(getattr(e, 'id', str(e)) for e in path)
        else:
            key = str(path)
        path_counts[key] = path_counts.get(key, 0) + 1

    return shannon_entropy(path_counts)


# ═══════════════════════════════════════════════════════════════════════════════
# D. SURROGATE FIDELITY
# ═══════════════════════════════════════════════════════════════════════════════

def validate_surrogate_ranking(
    surrogate_scores: List[float],
    true_scores: List[float]
) -> Dict[str, float]:
    """
    Validates whether the surrogate evaluator correctly ranks chromosomes
    relative to the true simulation evaluator.

    The surrogate doesn't need to predict exact costs — it needs to correctly
    identify which systems are better. This is because evolutionary selection
    (tournament, elitism) operates on relative ranking, not absolute values.

    Returns Spearman ρ, Kendall τ, and NRMSE in a single report.

    Parameters:
        surrogate_scores: Fitness values from the surrogate evaluator.
        true_scores: Fitness values from the true simulation evaluator.

    Returns:
        Dict with keys: 'spearman_rho', 'kendall_tau', 'nrmse', 'mape'.
    """
    return {
        'spearman_rho': spearman_correlation(surrogate_scores, true_scores),
        'kendall_tau': kendall_tau(surrogate_scores, true_scores),
        'nrmse': normalized_rmse(surrogate_scores, true_scores),
        'mape': mape(true_scores, surrogate_scores),
    }


def validate_surrogate_top_k(
    surrogate_ranking: List[Any],
    true_ranking: List[Any],
    k: int
) -> Tuple[float, float]:
    """
    Validates whether the surrogate's top-k ranked chromosomes match the
    true evaluator's top-k.

    Parameters:
        surrogate_ranking: UIDs sorted by surrogate fitness (best first).
        true_ranking: UIDs sorted by true fitness (best first).
        k: Number of top elements to compare.

    Returns:
        (precision, recall) tuple.
    """
    return top_k_overlap(surrogate_ranking, true_ranking, k)


def validate_distribution_consistency(
    dist_a: List[float],
    dist_b: List[float]
) -> Dict[str, float]:
    """
    Validates whether two sets of travel times (e.g., from repeated stochastic
    simulation runs) are drawn from the same probability distribution.

    Parameters:
        dist_a: First sample of travel times.
        dist_b: Second sample of travel times.

    Returns:
        Dict with 'ks_statistic', 'p_value', and 'consistent' (True if p >= 0.05).
    """
    stat, p = ks_test(dist_a, dist_b)
    return {
        'ks_statistic': stat,
        'p_value': p,
        'consistent': p >= 0.05,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_edge_ids(route: Any) -> set:
    """Extracts the set of edge IDs from a Route object."""
    if not hasattr(route, 'path') or not route.path:
        return set()
    return {getattr(e, 'id', id(e)) for e in route.path}


def _extract_system_edge_ids(chromosome: Any) -> set:
    """Extracts the aggregate edge ID set across all routes in a Chromosome."""
    if not hasattr(chromosome, 'routes') or not chromosome.routes:
        return set()
    edges = set()
    for route in chromosome.routes:
        edges.update(_extract_edge_ids(route))
    return edges


def _extract_node_degrees(chromosome: Any) -> Dict[str, int]:
    """Extracts the node degree distribution from a Chromosome's route system."""
    degrees: Dict[str, int] = {}
    if not hasattr(chromosome, 'routes'):
        return degrees
    for route in chromosome.routes:
        if not hasattr(route, 'path') or not route.path:
            continue
        for edge in route.path:
            start_id = getattr(edge.start, 'id', str(edge.start))
            end_id = getattr(edge.end, 'id', str(edge.end))
            degrees[start_id] = degrees.get(start_id, 0) + 1
            degrees[end_id] = degrees.get(end_id, 0) + 1
    return degrees


def _collect_all_edges(chromosome: Any) -> list:
    """Collects all edge objects from all routes in a Chromosome."""
    edges = []
    if not hasattr(chromosome, 'routes'):
        return edges
    for route in chromosome.routes:
        if hasattr(route, 'path') and route.path:
            edges.extend(route.path)
    return edges


def _extract_demand_coverage(
    chromosome: Any,
    sampler: Any
) -> Tuple[List[Tuple[float, float]], List[float]]:
    """
    Extracts the demand coverage distribution of a route system.

    For each unique node touched by the system's routes, looks up its
    demand probability in the sampler and returns the (coords, weights) pair.
    """
    node_probs = getattr(sampler, 'node_probabilities', {})
    if not node_probs or not hasattr(chromosome, 'routes'):
        return [], []

    seen_nodes = set()
    coords = []
    weights = []

    for route in chromosome.routes:
        if not hasattr(route, 'path') or not route.path:
            continue
        for edge in route.path:
            for node in [edge.start, edge.end]:
                node_key = getattr(node, 'id', id(node))
                if node_key not in seen_nodes:
                    seen_nodes.add(node_key)
                    prob = node_probs.get(node, 0.0)
                    if prob > 0:
                        coords.append((node.lat, node.lon))
                        weights.append(prob)

    return coords, weights
