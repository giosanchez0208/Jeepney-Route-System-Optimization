"""
optimizer.py

Main orchestrator. Controls execution flow, handles interrupts, and manages sub-engines.
"""

from pathlib import Path
import yaml
from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.toy_city import toy_setup_from_yaml
from .optimizer_config import OptimizationState
from .optimizer_orchestrator_io import OptimizerBuilder, StatePreservationEngine
from .optimizer_telemetry import TelemetryEngine
from .optimizer_adaptive import AdaptiveController
from .optimizer_engine import MemeticEngine
from .simulation import StaticSurrogateEvaluator

class Optimizer:
    def __init__(self, run_dir: Path):
        self.config, self.state, self.run_dir = OptimizerBuilder.resume_run(run_dir)
        self._init_engines()
        
        # Synchronize engine's generation state to prevent lineage numbering resets on resume
        if self.state:
            self.engine.current_generation = self.state.generation - 1

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
        
        # Instantiate high-fidelity StaticSurrogateEvaluator to compute real travel-time costs
        self.surrogate = StaticSurrogateEvaluator(
            config=self.raw_config,
            city_graph=self.cg,
            demand_sampler=self.sampler,
            num_samples=100
        )
        # Dynamic override to resolve evaluate_chromosome logic-only mismatch during metaheuristic search
        def custom_evaluate(chrom, fleet):
            sim_result = self.surrogate.evaluate(chrom.routes)
            chrom.cost = sim_result.fitness_score
            # Perform high-fidelity pheromone updates: evaporate and deposit along evaluated passenger paths
            chrom.pheromones.update_pheromones(sim_result)
            # Recalculate demand service gaps for the chromosome's routes to guide next generation's local search
            chrom.pheromones.gaps = chrom.pheromones.calculate_demand_service_gaps(chrom.routes)
            return chrom.cost

        self.engine.algo.evaluate_chromosome = custom_evaluate

        self.preservation = StatePreservationEngine(self.run_dir)
        self.telemetry = TelemetryEngine(self.run_dir, self.config.city_bounds)
        self.adaptive = AdaptiveController(self.config.p_mutation, self.config.n_stagnation)

    def start(self):
        # Initialize optimization state if not resuming from an existing run
        if self.state is None:
            print("[OPTIMIZER] Initializing fresh state...")
            self.state = self.engine.initialize_state()
            self.telemetry.log_lineage(self.state.population)

        print(f"[OPTIMIZER] Launching optimization search loop. Max generations: {self.config.g_max}")
        try:
            while self.state.generation <= self.config.g_max:
                if self.state.stagnation_counter >= self.config.n_stagnation:
                    print(f"[OPTIMIZER] Stagnation limit reached at generation {self.state.generation}. Terminating.")
                    break

                mut_rate = self.adaptive.update(self.state.stagnation_counter)
                
                # Advance optimization generation
                self.state = self.engine.step_generation(self.state, mut_rate)
                self.state.generation += 1

                mean_cost = sum(c.cost for c in self.state.population) / len(self.state.population)
                
                # Synchronously log lineage relationships and parentage UIDs
                self.telemetry.log_lineage(self.state.population)

                if self.state.generation % self.config.telemetry_interval == 0:
                    self.telemetry.log_generation(
                        self.state.generation, self.state.best_fitness, mean_cost, mut_rate, self.state.stagnation_counter
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