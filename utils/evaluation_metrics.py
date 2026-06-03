"""
evaluation_metrics.py

Mathematical Verification and Evaluation Metrics Toolkit.

Pure, stateless mathematical functions for evaluating transit route systems.
Each function operates on primitive data types (sets, lists, tuples, dicts)
and has no knowledge of domain objects (Routes, Chromosomes, Pheromones).

Metric Categories:
    1. Topological Similarity  — Jaccard, Cosine, Graph Edit Distance
    2. Geometric Similarity    — Discrete Fréchet Distance
    3. Distributional Distance — Wasserstein (Earth Mover's Distance), KS-Test
    4. Diversity & Structure   — Shannon Path Entropy, Coefficient of Variation
    5. Ranking Fidelity        — Spearman ρ, Kendall τ, Top-k Overlap, NRMSE, MAPE, Pearson r
"""

import math
import numpy as np
import networkx as nx
from scipy import stats
from scipy.spatial.distance import cdist
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TOPOLOGICAL SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════════

def jaccard_similarity(set_a: Iterable[Any], set_b: Iterable[Any]) -> float:
    """
    Computes the Jaccard similarity index between two sets.

    Formula:
        J(A, B) = |A ∩ B| / |A ∪ B|

    Returns 1.0 when both sets are empty (vacuously identical).

    Academic Grounding:
        Real & Vargas (1996) validated set-overlap metrics for comparing the
        structural composition of transit network topologies, demonstrating that
        Jaccard similarity captures the proportion of shared infrastructure
        between two route configurations.

    Parameters:
        set_a: First collection of elements (edge IDs, node IDs, etc.).
        set_b: Second collection of elements.

    Returns:
        float ∈ [0.0, 1.0]. 1.0 = identical sets, 0.0 = disjoint sets.
    """
    a = _to_id_set(set_a)
    b = _to_id_set(set_b)

    if not a and not b:
        return 1.0
    return len(a.intersection(b)) / len(a.union(b))


def cosine_similarity(vector_a: Dict[Any, float], vector_b: Dict[Any, float]) -> float:
    """
    Computes the cosine similarity between two sparse vectors keyed by
    arbitrary identifiers (e.g., node degree distributions).

    Formula:
        cos(A, B) = (A · B) / (||A|| × ||B||)

    Projects both vectors into the union of their key spaces, filling
    missing keys with 0.0. Returns 1.0 when both vectors are zero.

    Parameters:
        vector_a: First sparse vector as {key: value}.
        vector_b: Second sparse vector as {key: value}.

    Returns:
        float ∈ [0.0, 1.0]. 1.0 = perfectly aligned distributions.
    """
    all_keys = set(vector_a.keys()).union(set(vector_b.keys()))
    if not all_keys:
        return 1.0

    a_vals = [vector_a.get(k, 0.0) for k in all_keys]
    b_vals = [vector_b.get(k, 0.0) for k in all_keys]

    dot = sum(a * b for a, b in zip(a_vals, b_vals))
    norm_a = math.sqrt(sum(a * a for a in a_vals))
    norm_b = math.sqrt(sum(b * b for b in b_vals))

    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0 if norm_a == norm_b else 0.0

    return dot / (norm_a * norm_b)


def graph_edit_distance(
    edges_a: Iterable[Any],
    edges_b: Iterable[Any],
    max_nodes: int = 15
) -> float:
    """
    Quantifies structural network divergence using Graph Edit Distance (GED).

    GED is the minimum number of edge/node insertions, deletions, or
    substitutions required to transform one graph into another. Because exact
    GED is NP-hard, this implementation extracts the induced subgraphs of
    the highest-degree nodes (up to `max_nodes`) to guarantee tractability.

    Academic Grounding:
        Sanfeliu & Fu (1983) defined GED as an error-tolerant graph matching
        metric. The subgraph sampling strategy addresses the NP-completeness
        they identified by limiting the search space to topologically
        significant hub nodes.

    Parameters:
        edges_a: First edge collection (DirEdge objects or (start, end) tuples).
        edges_b: Second edge collection.
        max_nodes: Maximum hub nodes to retain per graph (controls complexity).

    Returns:
        float. 0.0 = identical structure, higher = more divergent.
    """
    G1 = _to_nx_graph(edges_a)
    G2 = _to_nx_graph(edges_b)

    if G1.number_of_nodes() == 0 and G2.number_of_nodes() == 0:
        return 0.0

    # Sample down to the top-k highest-degree nodes for tractability
    if G1.number_of_nodes() > max_nodes:
        top = sorted(G1.nodes(), key=lambda n: G1.degree(n), reverse=True)[:max_nodes]
        G1 = G1.subgraph(top)
    if G2.number_of_nodes() > max_nodes:
        top = sorted(G2.nodes(), key=lambda n: G2.degree(n), reverse=True)[:max_nodes]
        G2 = G2.subgraph(top)

    try:
        ged = next(nx.optimize_graph_edit_distance(G1, G2, timeout=1.0))
    except StopIteration:
        ged = nx.graph_edit_distance(G1, G2, timeout=1.0)
    except Exception:
        # Fallback to scalar difference bound if all solvers time out
        ged = (abs(G1.number_of_nodes() - G2.number_of_nodes()) +
               abs(G1.number_of_edges() - G2.number_of_edges()))

    return float(ged) if ged is not None else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GEOMETRIC SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════════

def discrete_frechet_distance(
    P: List[Tuple[float, float]],
    Q: List[Tuple[float, float]]
) -> float:
    """
    Computes the discrete Fréchet distance between two ordered coordinate
    sequences using the standard O(n*m) dynamic programming algorithm.

    Intuitively, the Fréchet distance is the minimum leash length required
    for two entities to traverse their respective paths from start to finish
    without backtracking. The discrete variant considers only the vertices.

    Unlike Hausdorff distance, Fréchet respects traversal order: two routes
    sharing the same streets but traveling in opposite directions correctly
    register as dissimilar.

    Academic Grounding:
        Eiter & Mannila (1994) introduced the discrete variant and proved the
        O(n*m) DP recurrence used here. Their algorithm is the standard
        implementation for trajectory comparison in GIS and transit applications.

    Parameters:
        P: First coordinate sequence as [(lat, lon), ...].
        Q: Second coordinate sequence as [(lat, lon), ...].

    Returns:
        float. 0.0 = identical sequences, higher = more geometrically divergent.
        Returns inf if either sequence is empty.
    """
    n, m = len(P), len(Q)
    if n == 0 or m == 0:
        return float('inf')

    ca = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            dist = math.sqrt((P[i][0] - Q[j][0]) ** 2 + (P[i][1] - Q[j][1]) ** 2)
            if i == 0 and j == 0:
                ca[i][j] = dist
            elif i > 0 and j == 0:
                ca[i][j] = max(ca[i - 1][0], dist)
            elif i == 0 and j > 0:
                ca[i][j] = max(ca[0][j - 1], dist)
            else:
                ca[i][j] = max(min(ca[i - 1][j], ca[i][j - 1], ca[i - 1][j - 1]), dist)

    return ca[n - 1][m - 1]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DISTRIBUTIONAL DISTANCE
# ═══════════════════════════════════════════════════════════════════════════════

def wasserstein_1d(dist_a: Iterable[float], dist_b: Iterable[float]) -> float:
    """
    Computes the 1-dimensional Wasserstein distance (Earth Mover's Distance)
    between two empirical distributions.

    Intuitively, the Wasserstein distance is the minimum "work" required to
    reshape one pile of dirt (distribution A) into the shape of another pile
    (distribution B), where "work" is mass × distance moved. Unlike KL
    divergence, Wasserstein is defined even when the distributions have
    non-overlapping supports.

    Academic Grounding:
        Villani (2009) formalized optimal transport theory. For transit
        applications, De Bacco et al. (2023) applied Wasserstein distances
        to compare multi-layer urban network structures — directly analogous
        to comparing the demand coverage distributions of two route systems.

    Parameters:
        dist_a: First empirical distribution as a sequence of float samples.
        dist_b: Second empirical distribution as a sequence of float samples.

    Returns:
        float ≥ 0.0. 0.0 = identical distributions, higher = more divergent.
    """
    return float(stats.wasserstein_distance(dist_a, dist_b))


def wasserstein_2d(
    coords_a: List[Tuple[float, float]],
    weights_a: List[float],
    coords_b: List[Tuple[float, float]],
    weights_b: List[float]
) -> float:
    """
    Computes the 2-dimensional Wasserstein distance between two weighted
    spatial point distributions using an exact optimal transport solution.

    This is the full spatial version: given two sets of geographic coordinates
    with associated demand weights, it computes the minimum cost of
    redistributing demand mass from configuration A to configuration B,
    where cost is proportional to Euclidean distance between points.

    Parameters:
        coords_a: Coordinates [(lat, lon), ...] for distribution A.
        weights_a: Demand weights for each point in A (must sum > 0).
        coords_b: Coordinates [(lat, lon), ...] for distribution B.
        weights_b: Demand weights for each point in B (must sum > 0).

    Returns:
        float ≥ 0.0. The optimal transport cost.
    """
    a = np.array(coords_a, dtype=float)
    b = np.array(coords_b, dtype=float)
    wa = np.array(weights_a, dtype=float)
    wb = np.array(weights_b, dtype=float)

    # Normalize to probability distributions
    sum_a, sum_b = wa.sum(), wb.sum()
    if sum_a == 0 or sum_b == 0:
        return 0.0
    wa = wa / sum_a
    wb = wb / sum_b

    # Build pairwise Euclidean cost matrix
    cost_matrix = cdist(a, b, metric='euclidean')

    # Solve via the linear sum assignment (Hungarian algorithm) on discretized transport
    # For exact OT: use the POT library or scipy linprog. Here we use the
    # closed-form 1D-sliced approximation for computational tractability.
    # Exact LP formulation for small problems:
    from scipy.optimize import linprog

    n, m = len(wa), len(wb)
    c = cost_matrix.flatten()

    # Equality constraints: row sums = wa, col sums = wb
    A_eq_rows = np.zeros((n, n * m))
    for i in range(n):
        A_eq_rows[i, i * m:(i + 1) * m] = 1.0

    A_eq_cols = np.zeros((m, n * m))
    for j in range(m):
        for i in range(n):
            A_eq_cols[j, i * m + j] = 1.0

    A_eq = np.vstack([A_eq_rows, A_eq_cols])
    b_eq = np.concatenate([wa, wb])

    bounds = [(0.0, None)] * (n * m)

    result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')

    if result.success:
        return float(result.fun)
    else:
        # Fallback: return 1D Wasserstein on the marginals
        return wasserstein_1d(
            np.repeat(np.arange(n), (wa * 1000).astype(int)),
            np.repeat(np.arange(m), (wb * 1000).astype(int))
        )


def ks_test(dist_a: Iterable[float], dist_b: Iterable[float]) -> Tuple[float, float]:
    """
    Executes a two-sample Kolmogorov-Smirnov test to determine whether two
    samples are drawn from the same underlying probability distribution.

    Academic Grounding:
        The KS-test is the standard non-parametric tool for verifying
        distributional equivalence in stochastic simulation validation.
        In transit evaluation, it verifies that travel time distributions
        from repeated stochastic runs remain statistically stable.

    Parameters:
        dist_a: First sample of continuous values (e.g., commute times).
        dist_b: Second sample of continuous values.

    Returns:
        (ks_statistic, p_value). If p_value < 0.05, the distributions
        are statistically different at the 95% confidence level.
    """
    res = stats.ks_2samp(dist_a, dist_b)
    return float(res.statistic), float(res.pvalue)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DIVERSITY & STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

def shannon_entropy(frequencies: Union[List[float], Dict[Any, float]]) -> float:
    """
    Quantifies the diversity of a frequency distribution using Shannon Entropy.

    Formula:
        H = -Σ P(x_i) × log₂(P(x_i))

    High entropy indicates a uniform, diverse distribution (many distinct
    routing options with similar usage). Low entropy indicates concentration
    on a few dominant paths.

    Academic Grounding:
        Shannon (1948) defined the information-theoretic measure. For transit
        networks, Levinson (2012) applied entropy measures to quantify the
        structural diversity and connectivity of urban transportation networks,
        demonstrating that higher routing entropy correlates with network
        resilience.

    Parameters:
        frequencies: Raw counts or weights. Can be a list or a dict of values.

    Returns:
        float ≥ 0.0 in bits. 0.0 = all mass on one element.
    """
    if frequencies is None:
        return 0.0
    try:
        if len(frequencies) == 0:
            return 0.0
    except TypeError:
        return 0.0

    counts = list(frequencies.values()) if hasattr(frequencies, 'values') else list(frequencies)
    total = sum(counts)
    if total == 0:
        return 0.0

    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * math.log2(p) for p in probs))


def coefficient_of_variation(data: Iterable[float]) -> float:
    """
    Calculates the Coefficient of Variation (CV = σ / μ) to determine the
    relative dispersion of a sample. Useful for identifying the stabilization
    point of stochastic sample sizes.

    Parameters:
        data: Sequence of numerical values.

    Returns:
        float ≥ 0.0. Lower values indicate more stable measurements.
    """
    arr = np.array(data, dtype=float)
    mean = np.mean(arr)
    if mean == 0.0:
        return 0.0
    return float(np.std(arr) / mean)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. RANKING FIDELITY
# ═══════════════════════════════════════════════════════════════════════════════

def spearman_correlation(scores_a: Iterable[float], scores_b: Iterable[float]) -> float:
    """
    Computes the Spearman rank correlation coefficient between two score vectors.

    Spearman ρ measures whether the relative ordering (ranking) of solutions
    is preserved, regardless of the absolute magnitude of the scores. This is
    the correct validation metric for surrogate models in evolutionary search,
    because selection operators (tournament, elitism) are ranking-based.

    Academic Grounding:
        Jin (2005) explicitly identifies Spearman rank correlation as the
        primary validation metric for fitness approximation in evolutionary
        computation, because evolutionary selection depends on relative
        ordering rather than absolute predictive accuracy.

    Parameters:
        scores_a: First score vector (e.g., surrogate fitness values).
        scores_b: Second score vector (e.g., true simulation costs).

    Returns:
        float ∈ [-1.0, 1.0]. 1.0 = perfect rank agreement.
    """
    res = stats.spearmanr(scores_a, scores_b)
    return float(res.correlation) if not np.isnan(res.correlation) else 0.0


def kendall_tau(scores_a: Iterable[float], scores_b: Iterable[float]) -> float:
    """
    Computes the Kendall rank correlation coefficient (τ) between two score vectors.

    Kendall τ counts concordant and discordant pairs directly, making it more
    robust than Spearman for small sample sizes. It measures the probability
    that two randomly chosen pairs are ranked in the same order.

    Parameters:
        scores_a: First score vector.
        scores_b: Second score vector.

    Returns:
        float ∈ [-1.0, 1.0]. 1.0 = all pairs concordant.
    """
    res = stats.kendalltau(scores_a, scores_b)
    return float(res.correlation) if not np.isnan(res.correlation) else 0.0


def pearson_correlation(vector_a: Iterable[float], vector_b: Iterable[float]) -> float:
    """
    Measures the linear correlation between two continuous variables.

    Parameters:
        vector_a: First variable values.
        vector_b: Second variable values (must be same length as vector_a).

    Returns:
        float ∈ [-1.0, 1.0]. 1.0 = perfect positive linear correlation.
    """
    a = np.array(vector_a, dtype=float)
    b = np.array(vector_b, dtype=float)

    if len(a) != len(b):
        raise ValueError(f"Vectors must have the same length, got {len(a)} and {len(b)}")
    if np.std(a) == 0.0 or np.std(b) == 0.0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def top_k_overlap(
    ranking_a: Iterable[Any],
    ranking_b: Iterable[Any],
    k: int
) -> Tuple[float, float]:
    """
    Calculates the precision and recall of one ranking against another
    for the top-k elements. Validates whether a surrogate model identifies
    the same top-performing solutions as the true evaluator.

    Parameters:
        ranking_a: First ranking (e.g., surrogate-sorted chromosome UIDs).
        ranking_b: Second ranking (e.g., true-fitness-sorted UIDs).
        k: Number of top elements to compare.

    Returns:
        (precision, recall) tuple. Both are float ∈ [0.0, 1.0].
    """
    list_a = list(ranking_a)
    list_b = list(ranking_b)

    k = min(k, len(list_a), len(list_b))
    if k <= 0:
        return 0.0, 0.0

    top_a = set(list_a[:k])
    top_b = set(list_b[:k])

    overlap = len(top_a.intersection(top_b))
    precision = float(overlap / k)
    recall = float(overlap / k)
    return precision, recall


def normalized_rmse(predicted: Iterable[float], actual: Iterable[float]) -> float:
    """
    Calculates the Normalized Root-Mean-Square Error (NRMSE) between predicted
    and actual values after normalizing both to [0, 1].

    Parameters:
        predicted: Predicted values (e.g., surrogate costs).
        actual: Ground truth values (e.g., simulation costs).

    Returns:
        float ≥ 0.0. Lower = more accurate predictions.
    """
    p = np.array(predicted, dtype=float)
    a = np.array(actual, dtype=float)

    if len(p) != len(a):
        raise ValueError(f"Lengths must match, got {len(p)} and {len(a)}")
    if len(p) == 0:
        return 0.0

    def _normalize(arr):
        lo, hi = np.min(arr), np.max(arr)
        return np.zeros_like(arr) if hi == lo else (arr - lo) / (hi - lo)

    return float(np.sqrt(np.mean((_normalize(p) - _normalize(a)) ** 2)))


def mape(baseline: Iterable[float], test: Iterable[float]) -> float:
    """
    Calculates the Mean Absolute Percentage Error (MAPE).

    Parameters:
        baseline: Ground truth values (denominator — must not contain zeros
                  in positions where comparison is needed).
        test: Test/predicted values.

    Returns:
        float ≥ 0.0 as a percentage. 0.0 = perfect match.
    """
    y_true = np.array(baseline, dtype=float)
    y_pred = np.array(test, dtype=float)

    if len(y_true) != len(y_pred):
        raise ValueError(f"Lengths must match, got {len(y_true)} and {len(y_pred)}")

    mask = y_true != 0.0
    if not np.any(mask):
        return 0.0

    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


# ═══════════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _to_id_set(elements: Iterable[Any]) -> set:
    """Converts an iterable of edges/IDs into a hashable set of identifiers."""
    if elements is None:
        return set()
    try:
        if len(elements) == 0:
            return set()
    except TypeError:
        return set()

    s = set()
    for e in elements:
        if hasattr(e, 'id'):
            s.add(e.id)
        elif isinstance(e, tuple):
            s.add(e)
        elif hasattr(e, 'start') and hasattr(e, 'end'):
            s.add((e.start.id, e.end.id))
        else:
            s.add(e)
    return s


def _to_nx_graph(edges: Iterable[Any]) -> nx.Graph:
    """Converts an edge iterable into a NetworkX undirected graph."""
    G = nx.Graph()
    for e in edges:
        if hasattr(e, 'start') and hasattr(e, 'end'):
            G.add_edge(e.start.id, e.end.id)
        elif isinstance(e, tuple) and len(e) == 2:
            G.add_edge(e[0], e[1])
    return G
