"""genetic.py

Implements the Lamarckian Memetic Algorithm for Phase D.
Handles Chromosome data structures, lineage tracking, crossover,
fitness-weighted pheromone inheritance, and local search execution.
"""

from __future__ import annotations
import math
import random
import uuid
from typing import Any, Optional

from .route import Route
from .pheromone import PheromoneMatrix
from .local_search import ACOLocalSearch
from .jeep_system import FleetAllocator


class Chromosome:
    """Represents a transit route configuration within the genetic algorithm."""

    def __init__(self, routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix, generation: int = 0, parents: Optional[list[str]] = None) -> None:
        self.uid: str = f"chrom_{uuid.uuid4().hex[:8]}"
        self.generation: int = generation
        self.parents: list[str] = parents if parents is not None else []
        self.routes: list[Route] = routes
        self.allocation: dict[Route, int] = allocation
        self.pheromones: PheromoneMatrix = pheromones
        self.cost: float = 0.0

    def __str__(self) -> str:
        return f"Chromosome(uid={self.uid}, generation={self.generation}, cost={self.cost:.2f}, routes={len(self.routes)})"


class MemeticAlgorithm:
    """Executes Lamarckian evolutionary operations on Chromosome instances."""

    def __init__(self, cg: Any, local_search: ACOLocalSearch, target_route_count: int, verbose: bool = False) -> None:
        if cg is None:
            raise ValueError("[MEMETIC ALGO] CityGraph cannot be None.")
        if local_search is None:
            raise ValueError("[MEMETIC ALGO] ACOLocalSearch cannot be None.")
        if target_route_count <= 0:
            raise ValueError(f"[MEMETIC ALGO] Target route count must be positive, got {target_route_count}.")

        self.cg: Any = cg
        self.local_search: ACOLocalSearch = local_search
        self.target_route_count: int = target_route_count
        self.verbose: bool = verbose

    def __str__(self) -> str:
        return f"MemeticAlgorithm(target_route_count={self.target_route_count}, verbose={self.verbose})"

    def _get_hub_edges(self, routes: list[Route], pheromones: PheromoneMatrix) -> set[Any]:
        """Identifies the topological sub-graph of the top 10% highest demand edges."""
        if not routes:
            raise ValueError("[MEMETIC ALGO] Routes list is empty.")
            
        edge_demand: list[tuple[float, Any]] = []
        for r in routes:
            for edge in r.path:
                tau: float = pheromones.tau.get(edge, 0.0)
                edge_demand.append((tau, edge))
                
        if not edge_demand:
            return set()
            
        edge_demand.sort(key=lambda x: x[0], reverse=True)
        top_k: int = max(1, len(edge_demand) // 10)
        
        return {getattr(e, 'id', id(e)) for _, e in edge_demand[:top_k]}

    def crossover_topological_hub(self, parent_a: Chromosome, parent_b: Chromosome) -> list[Route]:
        """
        Executes a topological crossover utilizing a high-demand sub-graph cluster.
        """
        if parent_a is None or parent_b is None:
            raise ValueError("[MEMETIC ALGO] Parents cannot be None for crossover.")

        hub_edge_ids = self._get_hub_edges(parent_a.routes, parent_a.pheromones)

        touching_routes: list[Route] = []
        for r in parent_a.routes:
            intersects = any(getattr(e, 'id', id(e)) in hub_edge_ids for e in r.path)
            if intersects:
                touching_routes.append(r)

        max_hub_size: int = math.ceil(self.target_route_count / 2.0)

        if len(touching_routes) > max_hub_size:
            def _localized_density(route: Route) -> float:
                density: float = 0.0
                for e in route.path:
                    if getattr(e, 'id', id(e)) in hub_edge_ids:
                        density += parent_a.pheromones.tau.get(e, 0.0)
                return density

            touching_routes.sort(key=_localized_density, reverse=True)
            touching_routes = touching_routes[:max_hub_size]

        hub_cluster: list[Route] = [Route(path=r.path[:], city_graph=self.cg) for r in touching_routes]

        if not hub_cluster:
            fallback = random.choice(parent_a.routes)
            hub_cluster = [Route(path=fallback.path[:], city_graph=self.cg)]

        child_routes: list[Route] = hub_cluster[:]
        current_child_edge_ids = {getattr(e, 'id', id(e)) for r in hub_cluster for e in r.path}

        candidates: list[tuple[int, Route]] = []
        for r in parent_b.routes:
            overlap_count: int = sum(1 for e in r.path if getattr(e, 'id', id(e)) in current_child_edge_ids)
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
        if parent_a is None or parent_b is None:
            raise ValueError("[MEMETIC ALGO] Parents cannot be None for inheritance.")

        parent_cfg = {
            "optimization": {
                "initial_tau": parent_a.pheromones.initial_tau,
                "rho": parent_a.pheromones.rho,
                "q": parent_a.pheromones.q,
                "default_jeep_weight": parent_a.pheromones.default_jeep_weight,
            }
        }
        child_phero = PheromoneMatrix(all_edges=self.cg.graph, config=parent_cfg)
        
        total_cost: float = parent_a.cost + parent_b.cost
        if total_cost == 0.0:
            total_cost = 1.0

        weight_a: float = parent_b.cost / total_cost
        weight_b: float = parent_a.cost / total_cost

        all_edges = set(parent_a.pheromones.tau.keys()).union(parent_b.pheromones.tau.keys())
        for e in all_edges:
            tau_a: float = parent_a.pheromones.tau.get(e, 0.0)
            tau_b: float = parent_b.pheromones.tau.get(e, 0.0)
            blended: float = (weight_a * tau_a) + (weight_b * tau_b)
            if blended > 0.0:
                child_phero.tau[e] = blended

        return child_phero

    def evaluate_chromosome(self, chrom: Chromosome, total_fleet: int) -> float:
        if chrom is None:
            raise ValueError("[MEMETIC ALGO] Chromosome cannot be None.")
        if total_fleet <= 0:
            raise ValueError(f"[MEMETIC ALGO] Total fleet must be positive, got {total_fleet}.")

        allocation = FleetAllocator.allocate_by_mohring(total_fleet, chrom.routes, chrom.pheromones, self.cg)
        report = FleetAllocator.evaluate_allocation(allocation, chrom.pheromones)

        system_cost: float = 0.0
        for r_data in report.values():
            if r_data["jeeps"] > 0:
                system_cost += (r_data["headway"] * 0.4) + (r_data["length"] * 0.6)
            else:
                system_cost += 10000.0
        chrom.allocation = allocation
        chrom.cost = system_cost
        return system_cost

    def apply_lamarckian_mutation(self, child: Chromosome, target_cost: float, total_fleet: int) -> bool:
        if child is None:
            raise ValueError("[MEMETIC ALGO] Child chromosome cannot be None.")

        original_routes_backup = [Route(path=r.path[:], city_graph=self.cg) for r in child.routes]
        
        child.pheromones.gaps = child.pheromones.calculate_demand_service_gaps(child.routes)
        self.local_search.optimize_system(child.routes, child.pheromones, intensity=1.0)
        
        hard_cost: float = self.evaluate_chromosome(child, total_fleet)

        if hard_cost < target_cost:
            return True

        child.routes = original_routes_backup
        self.evaluate_chromosome(child, total_fleet)
        return False