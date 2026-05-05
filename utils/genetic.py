"""genetic.py

Implements the Lamarckian Memetic Algorithm for Phase D.
Handles Chromosome data structures, Topological Hub Exchange crossover, 
fitness-weighted pheromone inheritance, and genetic divergence metrics.
"""

import math
import random
from typing import Any
from .route import Route
from .pheromone import PheromoneMatrix
from .local_search import ACOLocalSearch

class Chromosome:
    def __init__(self, routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix):
        self.routes = routes
        self.allocation = allocation
        self.pheromones = pheromones
        self.cost = 0.0

class MemeticAlgorithm:
    def __init__(self, cg: Any, local_search: ACOLocalSearch, target_route_count: int):
        self.cg = cg
        self.local_search = local_search
        self.target_route_count = target_route_count

    def _get_busiest_node(self, routes: list[Route], pheromones: PheromoneMatrix) -> Any:
        node_demand = {}
        for r in routes:
            for edge in r.path:
                tau = pheromones.tau.get(edge, 0)
                node_demand[edge.start] = node_demand.get(edge.start, 0) + tau
                node_demand[edge.end] = node_demand.get(edge.end, 0) + tau
                
        if not node_demand: 
            return random.choice(self.cg.nodes)
        return max(node_demand, key=node_demand.get)

    def crossover_topological_hub(self, parent_a: Chromosome, parent_b: Chromosome) -> list[Route]:
        busiest_node = self._get_busiest_node(parent_a.routes, parent_a.pheromones)
        
        touching_routes = []
        for r in parent_a.routes:
            nodes = {e.start for e in r.path}.union({e.end for e in r.path})
            if busiest_node in nodes:
                touching_routes.append(r)
                
        # Restrict hub inheritance to 50% of the target fleet to guarantee Parent B integration
        max_hub_size = math.ceil(self.target_route_count / 2.0)
        
        if len(touching_routes) > max_hub_size:
            def localized_density(route: Route) -> float:
                density = 0.0
                for e in route.path:
                    if e.start == busiest_node or e.end == busiest_node:
                        density += parent_a.pheromones.tau.get(e, 0)
                return density
            
            touching_routes.sort(key=localized_density, reverse=True)
            touching_routes = touching_routes[:max_hub_size]

        hub_cluster = [Route(path=r.path[:], city_graph=self.cg) for r in touching_routes]
                
        if not hub_cluster:
            fallback = random.choice(parent_a.routes)
            hub_cluster = [Route(path=fallback.path[:], city_graph=self.cg)]

        child_routes = hub_cluster[:]
        hub_edges = {e for r in hub_cluster for e in r.path}
            
        candidates = []
        for r in parent_b.routes:
            overlap_count = sum(1 for e in r.path if e in hub_edges)
            candidates.append((overlap_count, r))
            
        candidates.sort(key=lambda x: x[0]) 
        
        for _, r in candidates:
            if len(child_routes) >= self.target_route_count: 
                break
            
            existing_paths = [cr.path for cr in child_routes]
            if r.path not in existing_paths:
                child_routes.append(Route(path=r.path[:], city_graph=self.cg))
                
        while len(child_routes) < self.target_route_count:
            fallback = random.choice(parent_a.routes)
            child_routes.append(Route(path=fallback.path[:], city_graph=self.cg))
            
        return child_routes

    def inherit_pheromones(self, parent_a: Chromosome, parent_b: Chromosome) -> PheromoneMatrix:
        child_phero = PheromoneMatrix(all_edges=self.cg.graph)
        
        total_cost = parent_a.cost + parent_b.cost
        if total_cost == 0: 
            total_cost = 1.0
        
        weight_a = parent_b.cost / total_cost
        weight_b = parent_a.cost / total_cost
        
        all_edges = set(parent_a.pheromones.tau.keys()).union(parent_b.pheromones.tau.keys())
        for e in all_edges:
            tau_a = parent_a.pheromones.tau.get(e, 0)
            tau_b = parent_b.pheromones.tau.get(e, 0)
            blended = (weight_a * tau_a) + (weight_b * tau_b)
            if blended > 0:
                child_phero.tau[e] = blended
                
        return child_phero

    def calculate_system_divergence(self, chrom_a: Chromosome, chrom_b: Chromosome) -> dict:
        total_frechet = 0.0
        for r_a in chrom_a.routes:
            min_frechet = float('inf')
            for r_b in chrom_b.routes:
                dist = self.local_search.calculate_route_similarity(r_a, r_b)
                if dist < min_frechet:
                    min_frechet = dist
            total_frechet += min_frechet
        avg_frechet = total_frechet / len(chrom_a.routes) if chrom_a.routes else 0.0

        all_edges = set(chrom_a.pheromones.tau.keys()).union(chrom_b.pheromones.tau.keys())
        sq_error_sum = 0.0
        for e in all_edges:
            diff = chrom_a.pheromones.tau.get(e, 0) - chrom_b.pheromones.tau.get(e, 0)
            sq_error_sum += diff ** 2
        mse = sq_error_sum / len(all_edges) if all_edges else 0.0

        return {
            "frechet_divergence": avg_frechet,
            "pheromone_mse": mse
        }