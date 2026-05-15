from __future__ import annotations
from typing import Iterable, Optional, TYPE_CHECKING
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from .directed_edge import DirEdge
    from .simulation import SimulationResult
    from .jeep_system import JeepSystem

class PheromoneMatrix:
    def __init__(self, all_edges: Iterable['DirEdge'], config: dict, sim_result: Optional['SimulationResult'] = None) -> None:
        """
        Initializes the global demand matrix. 
        Optionally accepts a SimulationResult to seed the initial generation.
        """
        opt_cfg = config.get("optimization", {})
        self.initial_tau: float = float(opt_cfg.get("initial_tau", 1.0))
        self.rho: float = float(opt_cfg.get("rho", 0.1))
        self.q: float = float(opt_cfg.get("q", 1000.0))
        self.default_jeep_weight: float = float(opt_cfg.get("default_jeep_weight", 1.0))
        
        self.tau: dict['DirEdge', float] = {edge: self.initial_tau for edge in all_edges}

        if sim_result:
            self.update_pheromones(sim_result)

    def update_pheromones(self, sim_result: 'SimulationResult') -> None:
        """
        Pheromone Update.
        Applies evaporation, then deposits pheromones based on recorded passenger paths.
        """
        for edge in self.tau:
            self.tau[edge] = (1.0 - self.rho) * self.tau[edge]
            
        for path, cost in sim_result.recorded_paths:
            if not path or cost <= 0:
                continue
                
            deposit_value = self.q / cost
            
            for edge in path:
                if edge in self.tau:
                    self.tau[edge] += deposit_value

    def calculate_demand_service_gaps(self, jeep_system: 'JeepSystem') -> dict['DirEdge', float]:
        """
        Computes the Demand-Service Gap (\Delta_e) for all edges to identify underserved corridors.
        \Delta_e = \tau_e - \sum (1[e \in r] * w_r)
        """
        gaps: dict['DirEdge', float] = {}
        service_supply: dict['DirEdge', float] = {edge: 0.0 for edge in self.tau}
        
        fleet_counts = {r: 0 for r in jeep_system.routes}
        for j in jeep_system.jeeps:
            if j.route in fleet_counts:
                fleet_counts[j.route] += 1
                
        for route, fleet_size in fleet_counts.items():
            w_r = fleet_size * self.default_jeep_weight
            for edge in route.path:
                if edge in service_supply:
                    service_supply[edge] += w_r

        for edge, tau_e in self.tau.items():
            gaps[edge] = tau_e - service_supply[edge]
            
        return gaps

    def draw(
        self, 
        context: tuple[tuple[float, float], tuple[float, float]], 
        image: Image.Image, 
        gaps: Optional[dict['DirEdge', float]] = None,
        gap_threshold: float = 0.0
    ) -> Image.Image:
        """
        Draws the pheromone matrix as a spectrum from purple (least) to yellow (most).
        If a gap dictionary is provided, highly underserved edges are drawn in bright red on top.
        """
        if image.width != image.height:
            raise ValueError("[PHEROMONE] Visualization requires a square image.")

        img = image.copy()
        draw = ImageDraw.Draw(img, "RGBA")

        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0 or not self.tau:
            return img

        min_tau = min(self.tau.values())
        max_tau = max(self.tau.values())
        tau_range = max_tau - min_tau
        if tau_range == 0:
            tau_range = 1.0  # Prevent division by zero

        # Draw base pheromones (Purple -> Yellow)
        for edge, tau_val in self.tau.items():
            t = (tau_val - min_tau) / tau_range
            
            # Interpolate Purple (128, 0, 128) to Yellow (255, 255, 0)
            r = int(128 + 127 * t)
            g = int(255 * t)
            b = int(128 - 128 * t)
            color = (r, g, b, 200)
            
            # Scale line width exponentially to highlight critical corridors
            width = 1 + int(5 * (t ** 2))

            x1 = (edge.start.lon - tl_lon) / lon_range * img.width
            y1 = (tl_lat - edge.start.lat) / lat_range * img.height
            x2 = (edge.end.lon - tl_lon) / lon_range * img.width
            y2 = (tl_lat - edge.end.lat) / lat_range * img.height

            draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

        # Draw underserved edges on top (Red)
        if gaps:
            for edge, gap_val in gaps.items():
                if gap_val > gap_threshold:
                    x1 = (edge.start.lon - tl_lon) / lon_range * img.width
                    y1 = (tl_lat - edge.start.lat) / lat_range * img.height
                    x2 = (edge.end.lon - tl_lon) / lon_range * img.width
                    y2 = (tl_lat - edge.end.lat) / lat_range * img.height
                    
                    draw.line([(x1, y1), (x2, y2)], fill=(255, 0, 0, 255), width=6)

        return img
    
