"""pheromone.py

Manages the global pheromone matrix, encoding latent and realized passenger demand.
Calculates the Demand-Service Gap to guide ACO-biased local search.
"""

from typing import Iterable, Any

class PheromoneMatrix:
    def __init__(self, all_edges: Iterable[Any], initial_tau: float = 1.0, rho: float = 0.1, q: float = 1000.0) -> None:
        """
        Initializes the global demand matrix.
        """
        # Dictionary mapping DirEdge objects to their current pheromone level (\tau_e)
        self.tau = {edge: initial_tau for edge in all_edges}
        self.rho = rho
        self.q = q
        self.initial_tau = initial_tau

    def update_pheromones(self, passenger_records: list[tuple[list[Any], float]]) -> None:
        """
        Phase B: Pheromone Update.
        Applies evaporation, then deposits pheromones based on passenger planned paths.
        """
        # 1. Evaporation: \tau_e = (1 - \rho) * \tau_e
        for edge in self.tau:
            self.tau[edge] = (1 - self.rho) * self.tau[edge]
        
        # 2. Deposition: \Delta \tau_p = Q / C(\pi_p)
        for path, cost in passenger_records:
            # Skip invalid paths or zero-cost paths to avoid division by zero
            if not path or cost <= 0:
                continue
                
            deposit_value = self.q / cost
            
            for edge in path:
                if edge in self.tau:
                    self.tau[edge] += deposit_value

    def calculate_demand_service_gaps(self, routes: list[Any], default_jeep_weight: float = 1.0) -> dict[Any, float]:
        """
        Computes the Demand-Service Gap (\Delta_e) for all edges to identify underserved corridors.
        \Delta_e = \tau_e - \sum (1[e \in r] * w_r)
        
        Returns a dictionary mapping edges to their gap values.
        Positive values indicate underserved demand; negative values indicate oversupply.
        """
        gaps = {}
        
        # Pre-calculate service supply per edge across the entire network
        service_supply = {edge: 0.0 for edge in self.tau}
        
        for route in routes:
            # Service weight (w_r) is proportional to fleet size. 
            # We assume route objects have a 'fleet_size' attribute, otherwise fallback to 1.
            fleet_size = getattr(route, 'fleet_size', 1)
            w_r = fleet_size * default_jeep_weight
            
            # Add service supply to every edge covered by this route
            for edge in route.path:
                if edge in service_supply:
                    service_supply[edge] += w_r

        # Calculate the final mismatch (\Delta_e)
        for edge, tau_e in self.tau.items():
            gaps[edge] = tau_e - service_supply[edge]
            
        return gaps