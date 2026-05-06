"""
optimizer.py

Main orchestrator. Controls execution flow, handles interrupts, and manages sub-engines.
"""

from pathlib import Path
from utils.city_graph import CityGraph
from .optimizer_config import OptimizationState
from .optimizer_orchestrator_io import OptimizerBuilder, StatePreservationEngine
from .optimizer_telemetry import TelemetryEngine
from .optimizer_adaptive import AdaptiveController
from .optimizer_engine import MemeticEngine

class Optimizer:
    def __init__(self, run_dir: Path):
        self.config, self.state, self.run_dir = OptimizerBuilder.resume_run(run_dir)
        self._init_engines()

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
        self.cg = CityGraph(query="Iligan City, Philippines")
        self.cg.stitch_graph()
        self.engine = MemeticEngine(self.config, self.cg)
        self.preservation = StatePreservationEngine(self.run_dir)
        self.telemetry = TelemetryEngine(self.run_dir)
        self.adaptive = AdaptiveController(self.config.p_mutation, self.config.n_stagnation)

    def start(self):
        if self.state is None:
            self.state = self.engine.initialize_state()

        try:
            while self.state.generation <= self.config.g_max:
                if self.state.stagnation_counter >= self.config.n_stagnation:
                    print(f"Stagnation limit reached at generation {self.state.generation}. Terminating.")
                    break

                mut_rate = self.adaptive.update(self.state.stagnation_counter)
                self.state = self.engine.step_generation(self.state, mut_rate)

                mean_cost = sum(c.cost for c in self.state.population) / len(self.state.population)
                
                if self.state.generation % self.config.telemetry_interval == 0:
                    self.telemetry.log_generation(
                        self.state.generation, self.state.best_fitness, mean_cost, mut_rate, self.state.stagnation_counter
                    )

                if self.state.generation % self.config.checkpoint_interval == 0:
                    self.preservation.save_state(self.state)

        except KeyboardInterrupt:
            print("\nExecution interrupted. Saving state.")
        finally:
            self.preservation.save_state(self.state)
            print(f"State saved to {self.run_dir}. Exiting.")