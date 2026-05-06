"""
optimizer_telemetry.py

Handles synchronous metric logging, lineage tracking, and JSON topology exports.
"""

import csv
import json
from pathlib import Path
from typing import Any

class TelemetryEngine:
    def __init__(self, run_dir: Path, bounds: tuple[float, float, float, float]):
        self.run_dir = run_dir
        self.bounds = bounds
        self.history_file = self.run_dir / "history.csv"
        self.lineage_file = self.run_dir / "lineage.csv"
        self.snapshots_dir = self.run_dir / "snapshots"
        self.snapshots_dir.mkdir(exist_ok=True)
        self._init_csvs()

    def _init_csvs(self):
        with open(self.history_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Generation", "Global_Best_Cost", "Population_Mean_Cost", "Active_Mutation_Rate", "Stagnation_Counter"])
        
        with open(self.lineage_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["UID", "Generation", "Cost", "Parent_A", "Parent_B"])

    def log_generation(self, gen: int, best_cost: float, mean_cost: float, mut_rate: float, stag: int):
        with open(self.history_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([gen, round(best_cost, 4), round(mean_cost, 4), round(mut_rate, 4), stag])

    def log_lineage(self, population: list):
        with open(self.lineage_file, 'a', newline='') as f:
            writer = csv.writer(f)
            for chrom in population:
                p_a = chrom.parents[0] if len(chrom.parents) > 0 else "NONE"
                p_b = chrom.parents[1] if len(chrom.parents) > 1 else "NONE"
                writer.writerow([chrom.uid, chrom.generation, round(chrom.cost, 4), p_a, p_b])

    def export_json_snapshot(self, generation: int, best_cost: float, mean_cost: float, population: list):
        best_chrom = population[0]
        
        routes_data = [[{"lat": e.start.lat, "lon": e.start.lon} for e in route.path] + 
                       ([{"lat": route.path[-1].end.lat, "lon": route.path[-1].end.lon}] if route.path else []) 
                       for route in best_chrom.routes]

        pheromones_data = [{"edge": [{"lat": edge.start.lat, "lon": edge.start.lon}, {"lat": edge.end.lat, "lon": edge.end.lon}], "intensity": round(tau, 2)} 
                           for edge, tau in best_chrom.pheromones.tau.items() if tau > 1.1]

        # Aggregate edge gaps into node chokepoints
        gaps = best_chrom.pheromones.calculate_demand_service_gaps(best_chrom.routes)
        node_gaps = {}
        for edge, gap in gaps.items():
            if gap > 0:
                node_gaps[edge.start] = node_gaps.get(edge.start, 0) + gap
                node_gaps[edge.end] = node_gaps.get(edge.end, 0) + gap

        chokepoints_data = [{"lat": node.lat, "lon": node.lon, "gap_value": round(gap, 2)} 
                            for node, gap in node_gaps.items() if gap > 5.0]

        node_demand = {}
        for edge, tau in best_chrom.pheromones.tau.items():
            node_demand[edge.start] = node_demand.get(edge.start, 0) + tau
            node_demand[edge.end] = node_demand.get(edge.end, 0) + tau
        hub_node = max(node_demand, key=node_demand.get) if node_demand else None
        hub_coords = {"lat": hub_node.lat, "lon": hub_node.lon} if hub_node else None

        pop_fitness = [round(c.cost, 2) for c in population]
        pop_gaps = [round(sum(c.pheromones.calculate_demand_service_gaps(c.routes).values()), 2) for c in population]

        payload = {
            "generation": generation,
            "metadata": {
                "best_cost": round(best_cost, 4),
                "mean_cost": round(mean_cost, 4),
                "topological_hub": hub_coords
            },
            "distributions": {
                "fitness": pop_fitness,
                "unserved_proxy": pop_gaps
            },
            "layers": {
                "routes": routes_data,
                "pheromones": pheromones_data,
                "chokepoints": chokepoints_data
            }
        }

        filepath = self.snapshots_dir / f"network_state_gen_{generation}.json"
        with open(filepath, 'w') as f:
            json.dump(payload, f)