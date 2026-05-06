"""
optimizer_engine.py

Executes the generational logic (Phases A-D) using the underlying utils.
"""

import random
from .genetic import Chromosome, MemeticAlgorithm
from .pheromone import PheromoneMatrix
from .local_search import ACOLocalSearch
from .route import Route
from .city_graph import CityGraph
from .optimizer_config import ExperimentConfig, OptimizationState

class MemeticEngine:
    def __init__(self, config: ExperimentConfig, cg: CityGraph):
        self.config = config
        self.cg = cg
        self.local_search = ACOLocalSearch(cg=self.cg, p_local=self.config.p_local_search)
        self.algo = MemeticAlgorithm(cg=self.cg, local_search=self.local_search, target_route_count=self.config.k_routes)

    def initialize_state(self) -> OptimizationState:
        pheromones = PheromoneMatrix(all_edges=self.cg.graph, initial_tau=self.config.initial_pheromone, rho=self.config.rho_evaporation, q=self.config.q_pheromone_intensity)
        population = []
        
        for _ in range(self.config.n_population):
            routes = []
            for _ in range(self.config.k_routes):
                origin = random.choice(self.cg.nodes)
                dest = random.choice(self.cg.nodes)
                path = self.cg.findShortestPath(origin, dest)
                if path:
                    routes.append(Route(city_graph=self.cg, path=path))
                else:
                    routes.append(Route(city_graph=self.cg, path=[])) # Fallback
            
            chrom = Chromosome(routes=routes, allocation={}, pheromones=pheromones)
            self.algo.evaluate_chromosome(chrom, self.config.total_fleet)
            population.append(chrom)

        population.sort(key=lambda c: c.cost)
        return OptimizationState(population=population, pheromones=pheromones, best_fitness=population[0].cost)

    def step_generation(self, state: OptimizationState, current_mutation_rate: float) -> OptimizationState:
        population = state.population
        next_gen = population[:self.config.n_elite]
        
        while len(next_gen) < self.config.n_population:
            tournament = random.sample(population, self.config.k_tournament)
            tournament.sort(key=lambda c: c.cost)
            parent_a, parent_b = tournament[0], tournament[1]
            
            child_routes = self.algo.crossover_topological_hub(parent_a, parent_b)
            child_phero = self.algo.inherit_pheromones(parent_a, parent_b)
            child = Chromosome(child_routes, {}, child_phero)
            
            self.algo.evaluate_chromosome(child, self.config.total_fleet)
            
            if random.random() < current_mutation_rate:
                self.algo.apply_lamarckian_mutation(child, parent_a.cost, self.config.total_fleet)
                
            next_gen.append(child)

        next_gen.sort(key=lambda c: c.cost)
        
        current_best = next_gen[0].cost
        if current_best < state.best_fitness:
            state.stagnation_counter = 0
            state.best_fitness = current_best
        else:
            state.stagnation_counter += 1

        state.population = next_gen
        state.generation += 1
        return state