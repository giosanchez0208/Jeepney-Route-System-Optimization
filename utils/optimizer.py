"""
optimizer.py

Main orchestrator. Controls execution flow, handles interrupts, and manages sub-engines.
"""

from pathlib import Path
import yaml
import math
from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.toy_city import toy_setup_from_yaml
from .optimizer_config import OptimizationState
from .optimizer_orchestrator_io import OptimizerBuilder, StatePreservationEngine
from .optimizer_telemetry import TelemetryEngine
from .optimizer_adaptive import AdaptiveController
from .optimizer_engine import MemeticEngine
from .simulation import SimulationEvaluator, StaticSurrogateEvaluator

class Optimizer:
    def __init__(self, run_dir: Path):
        self.config, self.state, self.run_dir = OptimizerBuilder.resume_run(run_dir)
        self._init_engines()
        self._reconstruct_state_references()
        
        # Synchronize engine's generation state to prevent lineage numbering resets on resume
        if self.state:
            self.engine.current_generation = self.state.generation - 1
            if hasattr(self.state, 'random_state') and self.state.random_state is not None:
                import random
                random.setstate(self.state.random_state)

    def _reconstruct_state_references(self):
        if not self.state:
            return
            
        edge_lookup = {((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)): e for e in self.cg.graph}
        
        # 1. Reconstruct main pheromones
        if self.state.pheromones:
            from utils.pheromone import _TauView
            self.state.pheromones._edge_repr = {}
            for k in self.state.pheromones._tau.keys():
                repr_edge = edge_lookup.get(k)
                if repr_edge:
                    self.state.pheromones._edge_repr[k] = repr_edge
            self.state.pheromones.tau = _TauView(self.state.pheromones._tau, self.state.pheromones._edge_repr)
            
        # 2. Reconstruct each Chromosome in the population
        if self.state.population:
            for chrom in self.state.population:
                # Reconstruct chromosome's routes
                for route in chrom.routes:
                    route.cg = self.cg
                    route.path = [edge_lookup[k] for k in route.path_keys if k in edge_lookup]
                    
                # Reconstruct route keys in allocation dictionary
                new_alloc = {}
                for r, val in chrom.allocation.items():
                    new_alloc[r] = val
                chrom.allocation = new_alloc
                
                # Reconstruct chromosome's pheromones
                if chrom.pheromones:
                    from utils.pheromone import _TauView
                    chrom.pheromones._edge_repr = {}
                    for k in chrom.pheromones._tau.keys():
                        repr_edge = edge_lookup.get(k)
                        if repr_edge:
                            chrom.pheromones._edge_repr[k] = repr_edge
                    chrom.pheromones.tau = _TauView(chrom.pheromones._tau, chrom.pheromones._edge_repr)

    @classmethod
    def create(cls, config_path: str | Path):
        config, run_dir = OptimizerBuilder.build_new_run(config_path)
        instance = cls.__new__(cls)
        instance.config = config
        instance.run_dir = run_dir
        instance.state = None
        instance._init_engines()
        return instance

    def _init_engines(self):
        config_path = self.run_dir / "configs.yaml"
        with open(config_path, "r") as f:
            yaml_data = yaml.safe_load(f)

        # Unified setup for both OSM real graphs and synthetic Toy Cities
        if "toy_city" in yaml_data:
            self.cg, self.sampler, self.raw_config = toy_setup_from_yaml(config_path, verbose=False)
        else:
            self.raw_config = yaml_data
            cg_cfg = yaml_data.get("city_graph", {})
            self.cg = CityGraph(
                bbox=tuple(cg_cfg.get("bbox")) if "bbox" in cg_cfg else None,
                name=cg_cfg.get("name", "UrbanNetwork"),
                landmarks=cg_cfg.get("landmarks"),
                pbf_path=cg_cfg.get("pbf_path", "utils/data/philippines-latest.osm.pbf"),
                use_api=cg_cfg.get("use_api", False),
                verbose=cg_cfg.get("verbose", False)
            )
            
            ddm_cfg = yaml_data.get("ddm", {})
            self.sampler = DirectDemandSampler(
                city=self.cg,
                config=DDMConfig(**ddm_cfg),
                verbose=False
            )

        self.engine = MemeticEngine(self.config, self.cg, self.sampler)
        
        # Instantiate the full fitness evaluator for GA scoring.
        self.fitness = SimulationEvaluator(
            config=self.raw_config,
            city_graph=self.cg,
            travel_graph=None,
            demand_sampler=self.sampler
        )

        # Instantiate the static surrogate for local-search mutation checks only.
        self.surrogate = StaticSurrogateEvaluator(
            config=self.raw_config,
            city_graph=self.cg,
            demand_sampler=self.sampler,
            num_samples=100
        )
        self.engine.algo.set_fitness_evaluator(self.fitness)
        self.engine.algo.set_surrogate_evaluator(self.surrogate)

        self.preservation = StatePreservationEngine(self.run_dir)
        self.telemetry = TelemetryEngine(self.run_dir, self.config.city_bounds)
        self.adaptive = AdaptiveController(self.config.p_mutation, self.config.n_stagnation)

    def start(self):
        # Initialize optimization state if not resuming from an existing run
        if self.state is None:
            print("[OPTIMIZER] Initializing fresh state...")
            self.state = self.engine.initialize_state()
            self.telemetry.log_lineage(self.state.population)

        self.jaccard_patience_counter = 0

        print(f"[OPTIMIZER] Launching optimization search loop. Max generations: {self.config.g_max}")
        from tqdm import tqdm
        try:
            # Nested tqdm bar tracking generations with live telemetry updates
            with tqdm(
                total=self.config.g_max, 
                initial=self.state.generation, 
                desc="Memetic Generations", 
                leave=False
            ) as pbar:
                while self.state.generation <= self.config.g_max:
                    if self.state.stagnation_counter >= self.config.n_stagnation:
                        print(f"[OPTIMIZER] Stagnation limit reached at generation {self.state.generation}. Terminating.")
                        break

                    p_local = self.adaptive.get_local_search_prob(self.state.generation, self.config.g_max)
                    intensity = self.adaptive.get_local_search_intensity(self.state.generation, self.config.g_max)
                    
                    # Scale up to escape local optima if stagnation is active
                    if self.state.stagnation_counter > 0:
                        stagnation_boost = self.adaptive.update(self.state.stagnation_counter) - self.config.p_mutation
                        p_local = min(p_local + max(0.0, stagnation_boost), 0.95)
                    
                    # Advance optimization generation
                    self.state = self.engine.step_generation(self.state, p_local, intensity=intensity)
                    self.state.generation += 1
                    pbar.update(1)

                    mean_cost = sum(c.cost for c in self.state.population) / len(self.state.population)
                    
                    # Synchronously log lineage relationships and parentage UIDs
                    self.telemetry.log_lineage(self.state.population)

                    # Calculate multi-dimensional phenotypic & fitness convergence metrics
                    elite_jaccard = self.calculate_elite_jaccard(self.state.population)
                    fitness_variance = self.calculate_fitness_variance(self.state.population)

                    # Update progress bar statistics in real-time
                    pbar.set_postfix({
                        "best_fit": f"{self.state.best_fitness:.2f}",
                        "jaccard": f"{elite_jaccard:.2f}",
                        "variance": f"{fitness_variance:.2e}",
                        "stagnation": self.state.stagnation_counter
                    })

                    print(f"[OPTIMIZER] Generation {self.state.generation} metrics: Elite Jaccard = {elite_jaccard:.4f}, Fitness Variance = {fitness_variance:.4e}")

                    if elite_jaccard >= 0.95:
                        self.jaccard_patience_counter += 1
                    else:
                        self.jaccard_patience_counter = 0

                    if self.jaccard_patience_counter >= self.config.jaccard_patience:
                        print(f"[OPTIMIZER] Phenotypic convergence reached (Elite Jaccard >= 0.95 for {self.config.jaccard_patience} consecutive generations) at generation {self.state.generation}. Terminating.")
                        break

                    if fitness_variance < 1e-6:
                        print(f"[OPTIMIZER] Genotypic convergence reached (Fitness Variance < 1e-6) at generation {self.state.generation}. Terminating.")
                        break

                    if self.state.generation % self.config.telemetry_interval == 0:
                        self.telemetry.log_generation(
                            self.state.generation, self.state.best_fitness, mean_cost, p_local, self.state.stagnation_counter
                        )
                        self.telemetry.export_json_snapshot(
                            self.state.generation, self.state.best_fitness, mean_cost, self.state.population
                        )

                    if self.state.generation % self.config.checkpoint_interval == 0:
                        print(f"[OPTIMIZER] Saving checkpoint at generation {self.state.generation}...")
                        self.preservation.save_state(self.state)

        except KeyboardInterrupt:
            print("\n[OPTIMIZER] Execution interrupted by user. Saving final state...")
        finally:
            self.preservation.save_state(self.state)
            print(f"[OPTIMIZER] State successfully saved to {self.run_dir}. Exiting.")

    def calculate_elite_jaccard(self, population) -> float:
        """
        Calculates the average Jaccard similarity of route edge sets among the top 10% elite chromosomes.

        Literature Citation:
            This convergence checker is grounded in traditional population diversity metrics:
            Goldberg, D. E. (1989). Genetic Algorithms in Search, Optimization, and Machine Learning. Addison-Wesley.
        """
        sorted_pop = sorted(population, key=lambda c: c.cost)
        elite_count = max(2, int(math.ceil(0.1 * len(population))))
        elites = sorted_pop[:elite_count]
        
        edge_sets = []
        for chrom in elites:
            chrom_edges = set()
            for r in chrom.routes:
                for edge in r.path:
                    chrom_edges.add(edge.id)
            edge_sets.append(chrom_edges)
            
        similarities = []
        for i in range(len(edge_sets)):
            for j in range(i + 1, len(edge_sets)):
                u = edge_sets[i].union(edge_sets[j])
                if not u:
                    similarities.append(1.0)
                else:
                    similarities.append(len(edge_sets[i].intersection(edge_sets[j])) / len(u))
                    
        return sum(similarities) / len(similarities) if similarities else 0.0

    def calculate_fitness_variance(self, population) -> float:
        """
        Calculates the population fitness variance.
        """
        costs = [c.cost for c in population]
        mean_cost = sum(costs) / len(costs)
        variance = sum((x - mean_cost) ** 2 for x in costs) / len(costs)
        return variance
