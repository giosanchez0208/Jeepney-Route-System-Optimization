"""pheromone.py

Public API:
- PheromoneMatrix(all_edges, initial_tau, rho, q) tracks pheromone levels per
  edge for the ACO workflow.
- update_pheromones(), get_tau(), get_route_pheromone(), and
  compute_demand_gaps() are the exposed operations.

Internal API:
- matrix stores the edge-id to pheromone lookup used by the update logic.
"""

from typing import Sequence
from .route import Route
from .directed_edge import DirEdge

class PheromoneMatrix:
    """Manages pheromone initialization, evaporation, deposition, and scoring."""
    def __init__(self, all_edges: Sequence[DirEdge], initial_tau: float, rho: float, q: float) -> None:
        self.initial_tau = initial_tau
        self.rho = rho
        self.q = q
        
        # Initialize tau_0 for all edges (Phase B Prep)
        self.matrix: dict[str, float] = {edge.id: initial_tau for edge in all_edges}

    def update_pheromones(self, passenger_data: list[tuple[list[DirEdge], float]]) -> None:
        """
        Executes Phase B: Evaporates existing pheromones, then deposits new pheromones.
        passenger_data is a list of tuples containing (planned_journey, total_path_cost).
        """
        # 1. Evaporate (Equation 6)
        for edge_id in self.matrix:
            self.matrix[edge_id] *= (1.0 - self.rho)

        # 2. Deposit (Equations 4 & 5)
        for journey, cost in passenger_data:
            if cost <= 0:
                continue
                
            delta_tau = self.q / cost
            
            for edge in journey:
                if edge.id in self.matrix:
                    self.matrix[edge.id] += delta_tau

    def get_tau(self, edge: DirEdge) -> float:
        """Returns the pheromone level for a specific edge."""
        return self.matrix.get(edge.id, self.initial_tau)

    def get_route_pheromone(self, route: Route) -> float:
        """Calculates the total pheromone accumulated along a route."""
        return sum(self.get_tau(edge) for edge in route.path)

    def compute_demand_gaps(self, routes: list[Route], fleet_sizes: list[int]) -> dict[str, float]:
        """
        Calculates the demand-service gap Delta_e for all edges (Equation 7).
        Delta_e = tau_e - sum(service_weight) for routes containing e.
        """
        supply: dict[str, float] = {edge_id: 0.0 for edge_id in self.matrix}
        
        # Calculate overlapping service supply
        for route, fleet_size in zip(routes, fleet_sizes):
            for edge in route.path:
                if edge.id in supply:
                    supply[edge.id] += fleet_size 
                    
        # Calculate mismatch: Demand (tau) - Supply (fleet coverage)
        gaps: dict[str, float] = {}
        for edge_id, tau in self.matrix.items():
            gaps[edge_id] = tau - supply[edge_id]
            
        return gaps
