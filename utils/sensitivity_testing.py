"""
sensitivity_testing.py

Sensitivity Testing Suite for post-optimization paratransit route analysis.
Automates Demand Surface Perturbations, Congestion Scaling, and Behavioral parameter sweeps,
outputting a high-fidelity 3D Pareto scatter plot.
"""

import os
import math
import random
from typing import Any, Dict, List, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class SensitivitySuite:
    """
    Sensitivity Testing Suite

    Executes multi-scenario sensitivity runs against the final optimized paratransit solution
    and generates a 3D Pareto Frontier visual canvas.
    """

    @staticmethod
    def calculate_operator_fleet_variance(chromosome: Any) -> float:
        """
        Calculates the variance of route lengths in the optimized route system.
        Representing Operator Fleet/Route Length Variance.
        """
        lengths = []
        for route in chromosome.routes:
            length = sum(edge.getLength() for edge in route.path)
            lengths.append(length)
            
        if not lengths:
            return 0.0
            
        mean_len = sum(lengths) / len(lengths)
        variance = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
        return variance

    @classmethod
    def run_demand_perturbation(
        cls, 
        evaluator: Any, 
        chromosome: Any, 
        sigma2: float
    ) -> Dict[str, float]:
        """
        Injects Gaussian noise into the Direct Demand Model and evaluates.
        """
        sampler = evaluator.demand_sampler
        original_raw = list(getattr(sampler, "raw_probabilities", sampler.prob))
        
        # Inject Gaussian noise
        perturbed_raw = []
        sigma = math.sqrt(sigma2)
        for p in original_raw:
            noise = random.gauss(0, sigma)
            perturbed_raw.append(max(1e-9, p + noise))
            
        # Re-normalize and rebuild
        total = sum(perturbed_raw)
        normalized = [p / total for p in perturbed_raw]
        sampler._build_alias_tables(normalized)
        
        # Evaluate under perturbed demand
        res = evaluator.evaluate(chromosome.routes)
        
        # Restore sampler
        sampler._build_alias_tables(original_raw)
        
        # Calculate operator length variance
        op_variance = cls.calculate_operator_fleet_variance(chromosome)
        unserved = evaluator.num_samples - res.metrics["completed_routes"]
        
        return {
            "commute_cost": res.fitness_score,
            "operator_variance": op_variance,
            "unserved_demand": float(unserved),
            "scenario": f"Demand Noise (Var={sigma2})"
        }

    @classmethod
    def run_congestion_scaling(
        cls, 
        evaluator: Any, 
        chromosome: Any, 
        gamma: float
    ) -> Dict[str, float]:
        """
        Scales vehicle speed by gamma.
        Mathematically, scaling speed by gamma scales travel time by 1/gamma,
        which corresponds to scaling the ride weight by 1/gamma.
        """
        original_config = evaluator.config.copy()
        tg_config = original_config.get("travel_graph", {}).copy()
        
        ride_wt = tg_config.get("ride_wt", 1.0)
        # Apply scaling
        tg_config["ride_wt"] = ride_wt / gamma
        
        # Re-inject to evaluator config
        evaluator.config["travel_graph"] = tg_config
        
        # Evaluate
        res = evaluator.evaluate(chromosome.routes)
        
        # Restore config
        evaluator.config = original_config
        
        op_variance = cls.calculate_operator_fleet_variance(chromosome)
        unserved = evaluator.num_samples - res.metrics["completed_routes"]
        
        return {
            "commute_cost": res.fitness_score,
            "operator_variance": op_variance,
            "unserved_demand": float(unserved),
            "scenario": f"Congestion Scale (gamma={gamma})"
        }

    @classmethod
    def run_behavioral_sweep(
        cls, 
        evaluator: Any, 
        chromosome: Any, 
        epsilon: float, 
        transfer_wt: float
    ) -> Dict[str, float]:
        """
        Sweeps boarding tolerance epsilon (weight_tolerance) and transfer penalty transfer_wt.
        """
        original_config = evaluator.config.copy()
        tg_config = original_config.get("travel_graph", {}).copy()
        sim_config = original_config.get("simulation", {}).copy()
        
        # Apply parameters
        tg_config["transfer_wt"] = transfer_wt
        sim_config["weight_tolerance"] = epsilon
        
        evaluator.config["travel_graph"] = tg_config
        evaluator.config["simulation"] = sim_config
        
        # Evaluate
        res = evaluator.evaluate(chromosome.routes)
        
        # Restore
        evaluator.config = original_config
        
        op_variance = cls.calculate_operator_fleet_variance(chromosome)
        unserved = evaluator.num_samples - res.metrics["completed_routes"]
        
        return {
            "commute_cost": res.fitness_score,
            "operator_variance": op_variance,
            "unserved_demand": float(unserved),
            "scenario": f"Behavioral Sweep (eps={epsilon}, trans_wt={transfer_wt})"
        }

    @classmethod
    def execute_sensitivity_suite(
        cls, 
        evaluator: Any, 
        chromosome: Any, 
        output_plot_path: str = "outputs/sensitivity_pareto_3d.png"
    ) -> Dict[str, Any]:
        """
        Runs the full paratransit sensitivity testing pipeline and plots the 3D Pareto frontier.
        """
        # Build all scenarios to run
        scenarios_to_run = []
        # 1. Demand Surface Perturbations (Gaussian Noise variance in {0.05, 0.10, 0.20})
        for var in [0.05, 0.10, 0.20]:
            scenarios_to_run.append(("demand", var))
            
        # 2. Congestion Scaling (gamma in {0.5, 1.0, 1.5})
        for gamma in [0.5, 1.0, 1.5]:
            scenarios_to_run.append(("congestion", gamma))
            
        # 3. Behavioral Parameter Sweeps
        for eps in [25.0, 50.0, 100.0]:
            for trans_wt in [5.0, 10.0, 20.0]:
                scenarios_to_run.append(("behavioral", (eps, trans_wt)))
                
        # Execute with progress bar
        from tqdm import tqdm
        for s_type, s_val in tqdm(scenarios_to_run, desc="Sensitivity Scenario Sweeps"):
            if s_type == "demand":
                res = cls.run_demand_perturbation(evaluator, chromosome, s_val)
            elif s_type == "congestion":
                res = cls.run_congestion_scaling(evaluator, chromosome, s_val)
            elif s_type == "behavioral":
                eps, trans_wt = s_val
                res = cls.run_behavioral_sweep(evaluator, chromosome, eps, trans_wt)
            results.append(res)
                
        # 4. Generate 3D Pareto Frontier Plot
        os.makedirs(os.path.dirname(output_plot_path), exist_ok=True)
        
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        x_vals = [r["commute_cost"] for r in results]
        y_vals = [r["operator_variance"] for r in results]
        z_vals = [r["unserved_demand"] for r in results]
        scenarios = [r["scenario"] for r in results]
        
        # Colormap based on unserved demand
        scatter = ax.scatter(x_vals, y_vals, z_vals, c=z_vals, cmap="plasma", s=60, edgecolors='k')
        
        ax.set_xlabel("Passenger Commute Cost", labelpad=10)
        ax.set_ylabel("Operator Fleet Variance", labelpad=10)
        ax.set_zlabel("Unserved Demand (Count)", labelpad=10)
        ax.set_title("3D Paratransit Sensitivity Pareto Frontier", fontsize=14, pad=15)
        
        cbar = fig.colorbar(scatter, ax=ax, shrink=0.6, aspect=12, pad=0.1)
        cbar.set_label("Unserved Demand Intensity")
        
        # Adjust view angle for clarity
        ax.view_init(elev=25, azim=45)
        plt.tight_layout()
        plt.savefig(output_plot_path, dpi=300)
        plt.close()
        
        return {
            "results": results,
            "plot_path": output_plot_path
        }
