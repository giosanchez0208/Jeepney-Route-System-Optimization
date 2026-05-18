"""
utils/analysis.py

Mathematical verification and statistical analysis functions for Route Optimization results.
Includes Jaccard Index, Pearson Correlation, Shannon Entropy, KS-test,
Coefficient of Variation, MAPE, and Graph Edit Distance.
"""

import math
import numpy as np
import networkx as nx
from scipy import stats
from typing import Any, Iterable, Union, Dict, List, Tuple

def calculate_jaccard_similarity(edges_a: Iterable[Any], edges_b: Iterable[Any]) -> float:
    """
    Calculates the Jaccard similarity index between two edge sets or lists of edges.
    Supports DirEdge instances, tuple representation, or raw string identifiers.
    
    Formula:
        J(A, B) = |A ∩ B| / |A ∪ B|
    """
    def to_set(edges) -> set:
        if edges is None:
            return set()
        try:
            if len(edges) == 0:
                return set()
        except TypeError:
            return set()
        s = set()
        for e in edges:
            if hasattr(e, 'id'):
                s.add(e.id)
            elif isinstance(e, tuple):
                s.add(e)
            elif hasattr(e, 'start') and hasattr(e, 'end'):
                s.add((e.start.id, e.end.id))
            else:
                s.add(e)
        return s
        
    set_a = to_set(edges_a)
    set_b = to_set(edges_b)
    
    if not set_a and not set_b:
        return 1.0
    return len(set_a.intersection(set_b)) / len(set_a.union(set_b))

def calculate_graph_edit_distance(edges_a: Iterable[Any], edges_b: Iterable[Any], max_nodes: int = 15) -> float:
    """
    Quantifies structural network divergence using Graph Edit Distance (GED).
    To prevent exponential time complexity (since GED is NP-complete), this extracts
    the induced subgraphs of the highest-degree nodes up to 'max_nodes'.
    
    Returns the minimum number of edge/node additions, deletions, or substitutions.
    """
    def to_nx_graph(edges) -> nx.Graph:
        G = nx.Graph()
        for e in edges:
            if hasattr(e, 'start') and hasattr(e, 'end'):
                G.add_edge(e.start.id, e.end.id)
            elif isinstance(e, tuple) and len(e) == 2:
                G.add_edge(e[0], e[1])
        return G
        
    G1 = to_nx_graph(edges_a)
    G2 = to_nx_graph(edges_b)
    
    if G1.number_of_nodes() == 0 and G2.number_of_nodes() == 0:
        return 0.0
        
    # Sample down to top-k high-degree nodes for computational tractability
    if G1.number_of_nodes() > max_nodes:
        top_nodes = sorted(G1.nodes(), key=lambda n: G1.degree(n), reverse=True)[:max_nodes]
        G1 = G1.subgraph(top_nodes)
    if G2.number_of_nodes() > max_nodes:
        top_nodes = sorted(G2.nodes(), key=lambda n: G2.degree(n), reverse=True)[:max_nodes]
        G2 = G2.subgraph(top_nodes)
        
    try:
        # Run optimize_graph_edit_distance with a strict timeout of 1.0 second
        ged = next(nx.optimize_graph_edit_distance(G1, G2, timeout=1.0))
    except StopIteration:
        ged = nx.graph_edit_distance(G1, G2, timeout=1.0)
    except Exception:
        # Fallback to scalar difference bounds if search times out
        ged = abs(G1.number_of_nodes() - G2.number_of_nodes()) + abs(G1.number_of_edges() - G2.number_of_edges())
        
    return float(ged) if ged is not None else 0.0

def calculate_pearson_correlation(vector_a: Iterable[float], vector_b: Iterable[float]) -> float:
    """
    Measures the linear correlation between two continuous variables (e.g. DDM imputed weights).
    """
    a = np.array(vector_a, dtype=float)
    b = np.array(vector_b, dtype=float)
    
    if len(a) != len(b):
        raise ValueError(f"Vectors must have the same length, got {len(a)} and {len(b)}")
    if np.std(a) == 0.0 or np.std(b) == 0.0:
        return 0.0
        
    return float(np.corrcoef(a, b)[0, 1])

def compute_path_entropy(path_frequencies: Union[List[float], Dict[Any, float]]) -> float:
    """
    Quantifies routing diversity and system flexibility using Shannon Entropy.
    
    Formula:
        H = - Σ P(path_i) * log2(P(path_i))
    """
    if path_frequencies is None:
        return 0.0
    try:
        if len(path_frequencies) == 0:
            return 0.0
    except TypeError:
        return 0.0
        
    if isinstance(path_frequencies, dict):
        counts = list(path_frequencies.values())
    else:
        counts = list(path_frequencies)
        
    total = sum(counts)
    if total == 0:
        return 0.0
        
    probs = [c / total for c in counts if c > 0]
    return float(-sum(p * math.log2(p) for p in probs))

def run_ks_test(dist_a: Iterable[float], dist_b: Iterable[float]) -> Tuple[float, float]:
    """
    Executes a two-sample Kolmogorov-Smirnov test to verify if two stochastic runs
    draw travel/wait times from identical probability distributions.
    
    Returns (ks_statistic, p_value).
    """
    res = stats.ks_2samp(dist_a, dist_b)
    return float(res.statistic), float(res.pvalue)

def calculate_coefficient_of_variation(data: Iterable[float]) -> float:
    """
    Calculates the Coefficient of Variation (CV = σ / μ) to identify the 
    stabilization point for stochastic sample sizes.
    """
    arr = np.array(data, dtype=float)
    mean = np.mean(arr)
    if mean == 0.0:
        return 0.0
    return float(np.std(arr) / mean)

def compute_mape(baseline_data: Iterable[float], test_data: Iterable[float]) -> float:
    """
    Calculates Mean Absolute Percentage Error (MAPE) to quantify discretization error.
    """
    y_true = np.array(baseline_data, dtype=float)
    y_pred = np.array(test_data, dtype=float)
    
    if len(y_true) != len(y_pred):
        raise ValueError(f"Lengths must match, got {len(y_true)} and {len(y_pred)}")
        
    mask = y_true != 0.0
    if not np.any(mask):
        return 0.0
        
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)

def calculate_spearman_correlation(surrogate_scores: Iterable[float], actual_scores: Iterable[float]) -> float:
    """
    Calculates the Spearman rank correlation coefficient between surrogate and actual scores.
    """
    res = stats.spearmanr(surrogate_scores, actual_scores)
    return float(res.correlation) if not np.isnan(res.correlation) else 0.0

def calculate_kendall_tau(surrogate_scores: Iterable[float], actual_scores: Iterable[float]) -> float:
    """
    Calculates the Kendall rank correlation coefficient (tau) between surrogate and actual scores.
    """
    res = stats.kendalltau(surrogate_scores, actual_scores)
    return float(res.correlation) if not np.isnan(res.correlation) else 0.0

def calculate_top_k_overlap(surrogate_ranking: Iterable[Any], actual_ranking: Iterable[Any], k_threshold: int) -> Tuple[float, float]:
    """
    Calculates the precision and recall of the surrogate ranking compared to the actual ranking 
    for the top-k elements.
    
    Returns (precision, recall).
    """
    list_surr = list(surrogate_ranking)
    list_act = list(actual_ranking)
    
    k = min(k_threshold, len(list_surr), len(list_act))
    if k <= 0:
        return 0.0, 0.0
        
    top_surr = set(list_surr[:k])
    top_act = set(list_act[:k])
    
    overlap = len(top_surr.intersection(top_act))
    precision = float(overlap / k)
    recall = float(overlap / k)
    return precision, recall

def calculate_normalized_rmse(surrogate_scores: Iterable[float], actual_scores: Iterable[float]) -> float:
    """
    Calculates the Normalized Root-Mean-Square Error (NRMSE) between surrogate and actual scores
    after normalizing both to the [0, 1] range.
    """
    surr = np.array(surrogate_scores, dtype=float)
    act = np.array(actual_scores, dtype=float)
    
    if len(surr) != len(act):
        raise ValueError(f"Lengths must match, got {len(surr)} and {len(act)}")
    if len(surr) == 0:
        return 0.0
        
    def normalize_array(arr):
        a_min = np.min(arr)
        a_max = np.max(arr)
        if a_max == a_min:
            return np.zeros_like(arr)
        return (arr - a_min) / (a_max - a_min)
        
    norm_surr = normalize_array(surr)
    norm_act = normalize_array(act)
    
    rmse = np.sqrt(np.mean((norm_surr - norm_act) ** 2))
    return float(rmse)
