"""
JUSTIFICATION FOR STILL BEING A "HYBRID GA WITH ACO-INSPIRED LOCAL SEARCH":

Three pillars met:
1. Path-Cost Deposition: Pheromones are deposited inversely proportional to path cost (Q / C(πp)).
2. Generational Evaporation: Pheromones decay over time (ρ) to prevent search stagnation.
3. Probabilistic Biasing: The algorithm uses the pheromone matrix to weight its decisions (in your case, crossover and mutation probabilities) rather than making purely random choices.

"""

from __future__ import annotations
from typing import Iterable, Optional, TYPE_CHECKING
from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from .directed_edge import DirEdge
    from .simulation import SimulationResult
    from .jeep_system import JeepSystem

_CoordKey = tuple[tuple[float, float], tuple[float, float]]

def _edge_key(edge: 'DirEdge') -> _CoordKey:
    return ((edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat))


class PheromoneMatrix:
    def __init__(self, all_edges: Iterable['DirEdge'], config: dict, sim_result: Optional['SimulationResult'] = None) -> None:
        """
        Initializes the global demand matrix.
        Optionally accepts a SimulationResult to seed the initial generation.

        Pheromone values are keyed by coordinate-pair (start_lon, start_lat) →
        (end_lon, end_lat) so that route.path edges and travel-graph edges
        covering the same physical road are always treated as the same corridor,
        regardless of whether they are the same Python object.
        """
        opt_cfg = config.get("optimization", {})
        self.initial_tau: float = float(opt_cfg.get("initial_tau", 1.0))
        self.rho: float = float(opt_cfg.get("rho", 0.1))
        self.q: float = float(opt_cfg.get("q", 1000.0))
        self.default_jeep_weight: float = float(opt_cfg.get("default_jeep_weight", 1.0))

        # Primary store: coord-key → pheromone value
        self._tau: dict[_CoordKey, float] = {}
        # Keep one representative DirEdge per key so draw() can access geometry
        self._edge_repr: dict[_CoordKey, 'DirEdge'] = {}

        for edge in all_edges:
            k = _edge_key(edge)
            if k not in self._tau:
                self._tau[k] = self.initial_tau
                self._edge_repr[k] = edge

        # Legacy-compat shim: self.tau behaves like {edge: float} for callers
        # that iterate it, but writes go through the coord-keyed store.
        self.tau: dict['DirEdge', float] = _TauView(self._tau, self._edge_repr)

        # Cached demand-service gaps, populated by the ACO loop after each
        # evaluation via: pheromones.gaps = pheromones.calculate_demand_service_gaps(jeep_system)
        # Operators read this directly so gaps don't need to be passed as a parameter.
        self.gaps: dict = {}

        if sim_result:
            self.update_pheromones(sim_result)

    def __getstate__(self):
        return {
            "initial_tau": self.initial_tau,
            "rho": self.rho,
            "q": self.q,
            "default_jeep_weight": self.default_jeep_weight,
            "_tau": self._tau,
            "gaps": self.gaps
        }

    def __setstate__(self, state):
        self.initial_tau = state["initial_tau"]
        self.rho = state["rho"]
        self.q = state["q"]
        self.default_jeep_weight = state["default_jeep_weight"]
        self._tau = state["_tau"]
        self.gaps = state["gaps"]
        self._edge_repr = {}
        self.tau = None

    # ------------------------------------------------------------------
    def _get(self, edge: 'DirEdge') -> Optional[float]:
        return self._tau.get(_edge_key(edge))

    def _set(self, edge: 'DirEdge', value: float) -> None:
        k = _edge_key(edge)
        self._tau[k] = value
        if k not in self._edge_repr:
            self._edge_repr[k] = edge

    # ------------------------------------------------------------------
    def update_pheromones(self, sim_result: 'SimulationResult') -> None:
        """
        Pheromone update: evaporation then deposit along every recorded passenger path.
        Deposit = Q / path_cost so cheaper (better) journeys leave stronger trails.
        """
        # Evaporate
        for k in self._tau:
            self._tau[k] *= (1.0 - self.rho)

        # Deposit
        for path, cost in sim_result.recorded_paths:
            if not path or cost <= 0:
                continue
            deposit = self.q / cost
            for edge in path:
                k = _edge_key(edge)
                if k in self._tau:
                    self._tau[k] += deposit
                # Edges not in the matrix are travel-graph internals (WA/AL/TR/DI);
                # we only track physical road segments.

    # ------------------------------------------------------------------
    def calculate_demand_service_gaps(self, jeep_system: 'JeepSystem' | list['Route']) -> dict['DirEdge', float]:
        """
        Computes the Demand-Service Gap for all tracked corridors.

        gap_e = tau_e - service_supply_e

        service_supply_e = Σ_r  (jeeps_on_r * default_jeep_weight)  for routes covering edge e.

        A positive gap means demand exceeds current supply → underserved corridor.
        A negative gap means the corridor is over-served relative to pheromone demand.
        """
        supply: dict[_CoordKey, float] = {k: 0.0 for k in self._tau}

        if hasattr(jeep_system, "routes"):
            routes = jeep_system.routes
            jeeps = jeep_system.jeeps
        elif isinstance(jeep_system, list):
            routes = jeep_system
            jeeps = []
        else:
            routes = []
            jeeps = []

        fleet_counts: dict = {r: 0 for r in routes}
        for j in jeeps:
            if j.route in fleet_counts:
                fleet_counts[j.route] += 1

        for route, fleet_size in fleet_counts.items():
            w_r = fleet_size * self.default_jeep_weight
            for edge in route.path:
                k = _edge_key(edge)
                if k in supply:
                    supply[k] += w_r

        # Return gaps keyed by representative DirEdge (for draw() compatibility)
        return {
            self._edge_repr[k]: self._tau[k] - supply[k]
            for k in self._tau
        }

    # ------------------------------------------------------------------
    def draw(
        self,
        context: tuple[tuple[float, float], tuple[float, float]],
        image: Image.Image,
    ) -> Image.Image:
        """
        Renders the pheromone matrix onto image.

        Color scale: purple (low demand) → yellow (high demand).
        Line width scales quadratically with normalized tau (2–10 px) so
        high-demand corridors are visually dominant.
        """
        if image.width != image.height:
            raise ValueError("[PHEROMONE] Visualization requires a square image.")

        img = image.copy()
        draw = ImageDraw.Draw(img, "RGBA")

        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        if lon_range == 0 or lat_range == 0 or not self._tau:
            return img

        tau_vals = list(self._tau.values())
        min_tau = min(tau_vals)
        max_tau = max(tau_vals)
        tau_range = max_tau - min_tau or 1.0

        for k, tau_val in self._tau.items():
            edge = self._edge_repr[k]
            t = (tau_val - min_tau) / tau_range  # 0.0 = lowest demand, 1.0 = highest

            # Four-stop ramp: purple → blue → green → yellow
            if t < 1/3:
                s = t * 3                              
                r_ch = int(128 * (1 - s))              
                g_ch = 0
                b_ch = int(128 + 127 * s)              
            elif t < 2/3:
                s = (t - 1/3) * 3                      
                r_ch = 0
                g_ch = int(200 * s)                    
                b_ch = int(255 * (1 - s))              
            else:
                s = (t - 2/3) * 3                      
                r_ch = int(255 * s)                    
                g_ch = int(200 + 55 * s)               
                b_ch = 0
            alpha = 140 + int(115 * t)  
            color = (r_ch, g_ch, b_ch, alpha)
            width = 2 + int(8 * (t ** 2))  

            x1 = (edge.start.lon - tl_lon) / lon_range * img.width
            y1 = (tl_lat - edge.start.lat) / lat_range * img.height
            x2 = (edge.end.lon - tl_lon) / lon_range * img.width
            y2 = (tl_lat - edge.end.lat) / lat_range * img.height

            draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

        return img

    def draw_pheromone_difference(
            self, 
            other: 'PheromoneMatrix', 
            context: tuple[tuple[float, float], tuple[float, float]], 
            image: Image.Image,
            global_max: float = None
        ) -> Image.Image:
            """
            Renders the absolute delta between this matrix and another.
            Color gradient: Translucent Gray (minimal shift) -> Solid Red (maximum shift).
            """
            draw = ImageDraw.Draw(image, "RGBA")
            
            diffs = {}
            all_keys = set(self._tau.keys()).union(other._tau.keys())
            
            for k in all_keys:
                val_self = self._tau.get(k, 0.0)
                val_other = other._tau.get(k, 0.0)
                diffs[k] = abs(val_self - val_other)
                
            if global_max is not None:
                max_diff = global_max
            else:
                max_diff = max(diffs.values()) if diffs else 1.0
                
            if max_diff <= 0: max_diff = 1.0
            
            (c_min_lon, c_max_lat), (c_max_lon, c_min_lat) = context
            img_w, img_h = image.size
            
            def to_px(lon, lat):
                x = (lon - c_min_lon) / (c_max_lon - c_min_lon) * img_w
                y = (c_max_lat - lat) / (c_max_lat - c_min_lat) * img_h
                return x, y
                
            for k, diff in diffs.items():
                if diff < 0.1:
                    continue 
                    
                ratio = diff / max_diff
                ratio = min(1.0, ratio)
                
                r = int(180 + (75 * ratio))
                g = int(180 - (180 * ratio))
                b = int(180 - (180 * ratio))
                alpha = int(100 + (155 * ratio))
                width = max(1, int(8 * ratio))
                
                edge = self._edge_repr.get(k) or other._edge_repr.get(k)
                if not edge:
                    continue
                    
                x0, y0 = to_px(edge.start.lon, edge.start.lat)
                x1, y1 = to_px(edge.end.lon, edge.end.lat)
                
                draw.line([(x0, y0), (x1, y1)], fill=(r, g, b, alpha), width=width)
                
            return image


# ---------------------------------------------------------------------------
# Thin view shim so legacy callers that do `for edge, tau in pheromones.tau.items()`
# still work — iterates the representative edges with their pheromone values.
# ---------------------------------------------------------------------------
class _TauView:
    """Read-only dict-like view of the pheromone store keyed by representative DirEdge."""
    def __init__(self, tau_store: dict, repr_store: dict) -> None:
        self._tau = tau_store
        self._repr = repr_store

    def __iter__(self):
        return iter(self._repr.values())

    def get(self, edge, default=None):
        from utils.pheromone import _edge_key
        return self._tau.get(_edge_key(edge), default)

    def items(self):
        return ((self._repr[k], v) for k, v in self._tau.items())

    def values(self):
        return self._tau.values()

    def keys(self):
        return self._repr.values()

    def __len__(self):
        return len(self._tau)

    def __contains__(self, edge) -> bool:
        from utils.pheromone import _edge_key
        return _edge_key(edge) in self._tau

    def __getitem__(self, edge):
        from utils.pheromone import _edge_key
        return self._tau[_edge_key(edge)]

    def __setitem__(self, edge, value):
        from utils.pheromone import _edge_key
        k = _edge_key(edge)
        self._tau[k] = value
        if k not in self._repr:
            self._repr[k] = edge