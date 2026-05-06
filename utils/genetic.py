"""genetic.py

Implements the Lamarckian Memetic Algorithm for Phase D.
Handles Chromosome data structures, Topological Hub Exchange crossover, 
fitness-weighted pheromone inheritance, tiered local search, and the main execution loop.
"""

import math
import random
import pickle
import time
from pathlib import Path
from typing import Any
from .route import Route
from .pheromone import PheromoneMatrix
from .local_search import ACOLocalSearch
from .allocator import FleetAllocator 

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

    def _execute_soft_prune(self, route: Route) -> Route:
        if len(route.path) <= 2:
            return route
        return Route(path=route.path[:-1], city_graph=self.cg)

    def evaluate_chromosome(self, chrom: Chromosome, total_fleet: int) -> float:
        allocation = FleetAllocator.allocate_by_mohring(total_fleet, chrom.routes, chrom.pheromones, self.cg)
        report = FleetAllocator.evaluate_allocation(allocation, chrom.pheromones)
        
        system_cost = 0.0
        for r_data in report.values():
            if r_data["jeeps"] > 0:
                system_cost += (r_data["headway"] * 0.4) + (r_data["length"] * 0.6)
            else:
                system_cost += 10000.0 
        chrom.allocation = allocation
        chrom.cost = system_cost
        return system_cost

    def apply_lamarckian_mutation(self, child: Chromosome, target_cost: float, total_fleet: int) -> bool:
        target_route_idx = random.randint(0, len(child.routes) - 1)
        original_route = child.routes[target_route_idx]

        # Tier 1: Soft-Body Mutation (O(1) Prune)
        soft_route = self._execute_soft_prune(original_route)
        child.routes[target_route_idx] = soft_route
        soft_cost = self.evaluate_chromosome(child, total_fleet)
        
        if soft_cost < target_cost:
            return True

        # Tier 2: Hard-Body Mutation (O(N^2) Topological Overhaul)
        hard_route = self.local_search.mutate_route(original_route)
        child.routes[target_route_idx] = hard_route
        hard_cost = self.evaluate_chromosome(child, total_fleet)

        if hard_cost < target_cost:
            return True

        # Rejection: Restore original state
        child.routes[target_route_idx] = original_route
        self.evaluate_chromosome(child, total_fleet)
        return False

    def run_evolution(self, population: list[Chromosome], generations: int, total_fleet: int, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        history = []

        for gen in range(1, generations + 1):
            population.sort(key=lambda c: c.cost)
            
            parent_a = population[0] 
            parent_b = random.choice(population[1:max(2, len(population)//4)])
            
            child_routes = self.crossover_topological_hub(parent_a, parent_b)
            child_phero = self.inherit_pheromones(parent_a, parent_b)
            child = Chromosome(child_routes, {}, child_phero)
            
            raw_cost = self.evaluate_chromosome(child, total_fleet)
            gate_target = parent_a.cost

            self.apply_lamarckian_mutation(child, gate_target, total_fleet)
            
            population[-1] = child

            if gen % 100 == 0:
                best_cost = population[0].cost
                worst_cost = population[-1].cost
                history.append((gen, best_cost, worst_cost))

            if gen % 1000 == 0:
                checkpoint_path = out_dir / f"checkpoint_gen_{gen}.pkl"
                with open(checkpoint_path, 'wb') as f:
                    pickle.dump(population, f)
                    
        return population, history