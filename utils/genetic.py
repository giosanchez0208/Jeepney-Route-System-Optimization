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


class Chromosome:
    """
    Represents a transit route configuration within the genetic algorithm.

    Lamarckian Memetics & Epigenetics:
    Standard Genetic Algorithms strictly separate the genotype (the route array code) 
    from the phenotype (the simulated experience). Because we want to pass acquired 
    passenger flow and demand patterns down to offspring, this class implements a 
    Lamarckian Chromosome containing:
      1. Route Array (Genotype): N specific Route objects defining spatial paths.
      2. Fleet Array (Genotype): The integer distribution of jeeps across those routes.
      3. Epigenetic Map (Phenotype): The PheromoneMatrix representing the passenger demand 
         acquired from simulation.
      4. System Fitness Score: The final quantified balance of passenger utility vs. operator cost.
    """

    def __init__(self, routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix, generation: int = 0, parents: Optional[list[str]] = None) -> None:
        self.uid: str = f"chrom_{uuid.uuid4().hex[:8]}"
        self.generation: int = generation
        self.parents: list[str] = parents if parents is not None else []
        self.routes: list[Route] = routes
        self.allocation: dict[Route, int] = allocation
        self.pheromones: PheromoneMatrix = pheromones
        self.cost: float = 0.0

    def __str__(self) -> str:
        return f"Chromosome(uid={self.uid}, generation={self.generation}, fitness={self.cost:.2f}, routes={len(self.routes)})"


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
        self.fitness_evaluator: Any = None
        self.surrogate_evaluator: Any = None

    def set_fitness_evaluator(self, evaluator: Any) -> None:
        self.fitness_evaluator = evaluator

    def set_surrogate_evaluator(self, evaluator: Any) -> None:
        self.surrogate_evaluator = evaluator

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
        """
        Executes a fitness-weighted arithmetic crossover for pheromone matrix inheritance.

        Formula:
            tau_child(e) = (w_A * tau_A(e)) + (w_B * tau_B(e))
            where w_A = cost_B / (cost_A + cost_B) and w_B = cost_A / (cost_A + cost_B).
            The child inherits a map heavily biased toward the more successful (lower cost)
            parent's passenger flow, giving its initial Gen-0 fleet allocator a massive head start.

        Academic Backing:
        1. Multi-Colony Information Exchange (Middendorf et al., 2002):
           Blending the pheromone matrices of different populations/solutions significantly 
           accelerates finding the global optimum by performing information exchange.
        2. The "Belief Space" in Cultural Algorithms (Reynolds, 1994):
           Evolution occurs on two levels: Population Space (chromosomes) and Belief Space (pheromones).
           Allowing the fittest individuals to update the Belief Space proportional to their success
           lets children inherit parents' cultural memory of passenger demand.
        3. Arithmetic Crossover of Real-Valued Vectors (Michalewicz, 1992):
           A multidimensional application of arithmetic crossover on the epigenetic layer (the pheromones)
           so that the fitter parent exerts a mathematically heavier pull on the child's fleet allocation.
        """
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
        """
        Evaluates the chromosome with the microscopic fitness objective.

        The GA path must use the full fitness score so selection, elitism, and
        replacement all operate on the same objective. Surrogate scores are
        reserved for local-search mutation checks only.
        """
        if chrom is None:
            raise ValueError("[MEMETIC ALGO] Chromosome cannot be None.")
        if total_fleet <= 0:
            raise ValueError(f"[MEMETIC ALGO] Total fleet must be positive, got {total_fleet}.")

        if self.fitness_evaluator is None:
            raise RuntimeError("[MEMETIC ALGO] Fitness evaluator has not been configured.")

        sim_result = self.fitness_evaluator.evaluate(chrom.routes)
        if sim_result.fitness_score is None:
            raise ValueError("[MEMETIC ALGO] Fitness evaluator did not return a fitness score.")

        chrom.cost = sim_result.fitness_score
        chrom.pheromones.update_pheromones(sim_result)
        chrom.pheromones.gaps = chrom.pheromones.calculate_demand_service_gaps(chrom.routes)
        return chrom.cost

    def _evaluate_surrogate_cost(self, routes: list[Route]) -> float:
        if self.surrogate_evaluator is None:
            raise RuntimeError("[MEMETIC ALGO] Surrogate evaluator has not been configured.")

        sim_result = self.surrogate_evaluator.evaluate(routes)
        if sim_result.surrogate_cost is None:
            raise ValueError("[MEMETIC ALGO] Surrogate evaluator did not return a surrogate cost.")
        return sim_result.surrogate_cost

    def apply_lamarckian_mutation(self, child: Chromosome, total_fleet: int, intensity: float = 1.0) -> bool:
        if child is None:
            raise ValueError("[MEMETIC ALGO] Child chromosome cannot be None.")

        original_routes_backup = [Route(path=r.path[:], city_graph=self.cg) for r in child.routes]

        baseline_surrogate = self._evaluate_surrogate_cost(child.routes)
        child.pheromones.gaps = child.pheromones.calculate_demand_service_gaps(child.routes)
        self.local_search.optimize_system(child.routes, child.pheromones, intensity=intensity)

        mutated_surrogate = self._evaluate_surrogate_cost(child.routes)

        if mutated_surrogate < baseline_surrogate:
            self.evaluate_chromosome(child, total_fleet)
            return True

        child.routes = original_routes_backup
        child.pheromones.gaps = child.pheromones.calculate_demand_service_gaps(child.routes)
        return False
