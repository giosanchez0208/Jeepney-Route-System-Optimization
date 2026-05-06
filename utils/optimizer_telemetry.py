"""
optimizer_telemetry.py

Handles synchronous metric logging and artifact generation.
"""

import csv
from pathlib import Path

class TelemetryEngine:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.history_file = self.run_dir / "history.csv"
        self._init_csv()

    def _init_csv(self):
        """Initializes the telemetry log with strictly typed headers."""
        with open(self.history_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "Generation", 
                "Global_Best_Cost", 
                "Population_Mean_Cost", 
                "Active_Mutation_Rate", 
                "Stagnation_Counter"
            ])

    def log_generation(self, gen: int, best_cost: float, mean_cost: float, mut_rate: float, stag: int):
        """Appends generation metrics to the history log."""
        with open(self.history_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                gen, 
                round(best_cost, 4), 
                round(mean_cost, 4), 
                round(mut_rate, 4), 
                stag
            ])