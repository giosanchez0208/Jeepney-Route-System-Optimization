"""
consistency_engine.py

Consistency & Graph Comparison Engine
Calculates post-optimization solution consistency metrics across distinct configuration profiles.
"""

import math
from typing import Any, Dict, List, Set, Tuple

class ConsistencyEngine:
    """
    Consistency & Graph Comparison Engine

    Coordinates post-optimization topological and distribution-based comparison checks
    across different configuration runs to mathematically prove solution consistency.
    """

    @staticmethod
    def extract_active_elements(chromosome: Any) -> Tuple[Set[str], Dict[str, int]]:
        """
        Extracts active edge IDs and node degree counts for a given chromosome.

        Parameters:
            chromosome: Candidate chromosome containing routes.
        Returns:
            Tuple containing:
              - Set of active edge IDs (DirEdge ids).
              - Dictionary mapping node IDs to their active degree counts.
        """
        active_edges = set()
        node_degrees = {}
        
        for route in chromosome.routes:
            for edge in route.path:
                active_edges.add(edge.id)
                # Count degrees for start and end nodes of the active transit segment
                node_degrees[edge.start.id] = node_degrees.get(edge.start.id, 0) + 1
                node_degrees[edge.end.id] = node_degrees.get(edge.end.id, 0) + 1
                
        return active_edges, node_degrees

    @classmethod
    def calculate_jaccard_similarity(cls, edges_a: Set[str], edges_b: Set[str]) -> float:
        """
        Calculates the topological Jaccard similarity of two edge sets:
        J(G_A, G_B) = |E_A intersection E_B| / |E_A union E_B|

        Parameters:
            edges_a: Set of active edges in profile A.
            edges_b: Set of active edges in profile B.
        Returns:
            Topological similarity score [0.0, 1.0].
        """
        union_set = edges_a.union(edges_b)
        if not union_set:
            return 1.0
        return len(edges_a.intersection(edges_b)) / len(union_set)

    @classmethod
    def calculate_degree_cosine_similarity(cls, degrees_a: Dict[str, int], degrees_b: Dict[str, int]) -> float:
        """
        Extracts the degree vectors across the union of active node spaces
        and computes the cosine similarity.

        Parameters:
            degrees_a: Node degrees for profile A.
            degrees_b: Node degrees for profile B.
        Returns:
            Degree distribution alignment score [0.0, 1.0].
        """
        all_nodes = set(degrees_a.keys()).union(set(degrees_b.keys()))
        if not all_nodes:
            return 1.0
            
        vector_a = []
        vector_b = []
        for node_id in all_nodes:
            vector_a.append(degrees_a.get(node_id, 0))
            vector_b.append(degrees_b.get(node_id, 0))
            
        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        norm_a = math.sqrt(sum(a * a for a in vector_a))
        norm_b = math.sqrt(sum(b * b for b in vector_b))
        
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0 if norm_a == norm_b else 0.0
            
        return dot_product / (norm_a * norm_b)

    @classmethod
    def analyze_consistency(cls, chromosomes: List[Any]) -> Dict[str, Any]:
        """
        Executes topological comparisons across a list of optimized chromosomes representing
        different configuration runs.

        Parameters:
            chromosomes: List of optimized chromosomes.
        Returns:
            Dictionary containing similarity matrices, mean Jaccard, mean cosine, and success indicator.
        """
        n = len(chromosomes)
        if n < 2:
            return {
                "jaccard_matrix": [[1.0]],
                "cosine_matrix": [[1.0]],
                "mean_jaccard": 1.0,
                "mean_cosine": 1.0,
                "success": True
            }
            
        # Extract edge sets and degree maps
        profiles_data = [cls.extract_active_elements(c) for c in chromosomes]
        
        jaccard_matrix = [[0.0] * n for _ in range(n)]
        cosine_matrix = [[0.0] * n for _ in range(n)]
        
        jaccard_sums = 0.0
        cosine_sums = 0.0
        pair_count = 0
        
        for i in range(n):
            jaccard_matrix[i][i] = 1.0
            cosine_matrix[i][i] = 1.0
            for j in range(i + 1, n):
                edges_a, degs_a = profiles_data[i]
                edges_b, degs_b = profiles_data[j]
                
                jac = cls.calculate_jaccard_similarity(edges_a, edges_b)
                cos = cls.calculate_degree_cosine_similarity(degs_a, degs_b)
                
                jaccard_matrix[i][j] = jaccard_matrix[j][i] = jac
                cosine_matrix[i][j] = cosine_matrix[j][i] = cos
                
                jaccard_sums += jac
                cosine_sums += cos
                pair_count += 1
                
        mean_jaccard = jaccard_sums / pair_count
        mean_cosine = cosine_sums / pair_count
        
        # Success Condition: mean topological Jaccard similarity must remain >= 0.80
        success = mean_jaccard >= 0.80
        
        return {
            "jaccard_matrix": jaccard_matrix,
            "cosine_matrix": cosine_matrix,
            "mean_jaccard": mean_jaccard,
            "mean_cosine": mean_cosine,
            "success": success
        }
