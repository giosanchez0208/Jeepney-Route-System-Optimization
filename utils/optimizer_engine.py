"""optimizer_engine.py

Executes the generational logic (Phases A-D) using the underlying utils.
"""

import random
from typing import Optional, Any
from .genetic import Chromosome, MemeticAlgorithm
from .pheromone import PheromoneMatrix
from .local_search import ACOLocalSearch
from .route import Route, RouteGenerator
from .city_graph import CityGraph
from .optimizer_config import ExperimentConfig, OptimizationState

class MemeticEngine:
    """
    The Memetic Engine

    Function: 
        Executes the main optimization pipeline coordinating the evolutionary phases.
    Utility: 
        Manages population initialization, step-generation loops (tournament selection, 
        crossover, local search, and generational replacement), and updates system states 
        by routing information directly between genetic and local search operators.
    """
    def __init__(self, config: ExperimentConfig, cg: CityGraph, sampler: Optional[Any] = None, runner: Optional[Any] = None):
        self.config = config
        self.cg = cg
        self.sampler = sampler
        self.runner = runner
        self.current_generation = 0

        self.local_search = ACOLocalSearch(
            cg=self.cg,
            p_attraction=config.p_ls_attraction,
            p_repulsion=config.p_ls_repulsion,
            p_pruning=config.p_ls_pruning,
            base_window_size=15
        )

        self.algo = MemeticAlgorithm(
            cg=self.cg,
            local_search=self.local_search,
            target_route_count=self.config.num_routes,
            verbose=False
        )

    def initialize_state(self) -> OptimizationState:
        # Build a plain dict that PheromoneMatrix expects
        phero_config = {
            "initial_tau": self.config.initial_tau,
            "rho": self.config.rho,
            "q": self.config.q,
            "default_jeep_weight": self.config.default_jeep_weight,
        }
        # Create pheromone matrix using the dict
        pheromones = PheromoneMatrix(all_edges=self.cg.graph, config=phero_config)

        population = []
        rg = RouteGenerator(self.cg, self.sampler) if self.sampler else None

        for _ in range(self.config.n_population):
            if rg:
                routes = [rg.generate(n_points=4) for _ in range(self.config.num_routes)]
            else:
                routes = self._generate_random_routes()  # fallback method
            # Instantiate a fresh, decoupled PheromoneMatrix for each chromosome
            chrom_phero = PheromoneMatrix(all_edges=self.cg.graph, config=phero_config)
            chrom = Chromosome(routes=routes, allocation={}, pheromones=chrom_phero, generation=0)
            population.append(chrom)

        if self.runner:
            self.algo.evaluate_population(population, self.runner)
        else:
            for chrom in population:
                self.algo.evaluate_chromosome(chrom, self.config.total_allocatable_jeeps)

        population.sort(key=lambda c: c.cost)
        return OptimizationState(
            population=population,
            pheromones=population[0].pheromones,
            best_fitness=population[0].cost
        )

    def step_generation(self, state: OptimizationState, current_mutation_rate: float, intensity: float = 1.0) -> OptimizationState:
        self.current_generation += 1
        population = state.population
        next_gen = population[:self.config.n_elite]
        
        target_fleet = getattr(self.config, 'total_allocatable_jeeps', 20)
        children_to_evaluate = []
        
        while len(next_gen) + len(children_to_evaluate) < self.config.n_population:
            tournament = random.sample(population, self.config.k_tournament)
            tournament.sort(key=lambda c: c.cost)
            parent_a, parent_b = tournament[0], tournament[1]
            
            child_routes = self.algo.crossover_topological_hub(parent_a, parent_b)
            child_phero = self.algo.inherit_pheromones(parent_a, parent_b)
            
            child = Chromosome(
                routes=child_routes,
                allocation={},
                pheromones=child_phero,
                generation=self.current_generation,
                parents=[parent_a.uid, parent_b.uid]
            )
                
            if random.random() < current_mutation_rate:
                self.algo.apply_lamarckian_mutation(child, target_fleet, intensity=intensity, evaluate_inline=not bool(self.runner))
                
            children_to_evaluate.append(child)

        if self.runner:
            self.algo.evaluate_population(children_to_evaluate, self.runner)
        else:
            for child in children_to_evaluate:
                self.algo.evaluate_chromosome(child, target_fleet)
                
        next_gen.extend(children_to_evaluate)
        next_gen.sort(key=lambda c: c.cost)
        
        current_best = next_gen[0].cost
        if current_best < state.best_fitness:
            state.stagnation_counter = 0
            state.best_fitness = current_best
        else:
            state.stagnation_counter += 1
            
        state.population = next_gen
        state.pheromones = next_gen[0].pheromones
        return state
