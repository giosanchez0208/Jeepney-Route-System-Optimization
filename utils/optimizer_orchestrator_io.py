"""
orchestrator_io.py

Handles environment building, config preservation, and state checkpointing 
for the MemeticResearchOrchestrator.
"""

import shutil
import pickle
from datetime import datetime
from pathlib import Path

from .optimizer_config import ExperimentConfig, OptimizationState

class StatePreservationEngine:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.checkpoints_dir = self.run_dir / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, state: OptimizationState):
        """Serializes the exact state of the optimization loop."""
        filepath = self.checkpoints_dir / f"state_gen_{state.generation}.pkl"
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

    def load_state(self, filepath: Path) -> OptimizationState:
        """Deserializes a state file to resume execution."""
        with open(filepath, 'rb') as f:
            return pickle.load(f)

class OptimizerBuilder:
    @staticmethod
    def build_new_run(config_path: str | Path) -> tuple[ExperimentConfig, Path]:
        """
        Constructs a new, isolated optimization environment.
        Copies the YAML configuration to guarantee absolute reproducibility.
        """
        config = ExperimentConfig.from_yaml(config_path)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = config.output_root / f"opt_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Lock the configuration into the instance directory
        shutil.copy(config_path, run_dir / "configs.yaml")
        
        return config, run_dir

    @staticmethod
    def resume_run(run_dir: str | Path) -> tuple[ExperimentConfig, OptimizationState, Path]:
        """
        Reconstructs the optimization environment from a previous run directory.
        Locates the most recent checkpoint and loads the immutable configuration.
        """
        run_dir = Path(run_dir)
        config_path = run_dir / "configs.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Corrupted run directory: {config_path} missing.")
            
        config = ExperimentConfig.from_yaml(config_path)
        preservation_engine = StatePreservationEngine(run_dir)
        
        checkpoints = list(preservation_engine.checkpoints_dir.glob("state_gen_*.pkl"))
        if not checkpoints:
            raise FileNotFoundError("No valid .pkl checkpoints found to resume.")
            
        # Extract the highest generation number to resume from the latest state
        latest_checkpoint = max(checkpoints, key=lambda p: int(p.stem.split('_')[-1]))
        state = preservation_engine.load_state(latest_checkpoint)
        
        return config, state, run_dir