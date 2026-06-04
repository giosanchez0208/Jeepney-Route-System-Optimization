"""
Toy City — Synthetic fast-setup environment for diagnostic_sim.ipynb.

Replaces the expensive OSM / TomTom / betweenness-centrality stack with
a hand-crafted NxN grid city and a spatially-varied demand model built
from user-defined hotspots + Inverse Distance Weighting.

Setup time: milliseconds.
Interfaces: drop-in compatible with CityGraph and DirectDemandSampler
            so every downstream module (RouteGenerator, TravelGraph,
            PassengerGenerator, Simulation) works identically.

Public API
----------
build_toy_city(config: ToyCityConfig) -> CityGraph
    Returns a fully-stitched NxN grid CityGraph with all drivable edges.

ToyDDM(city, config: ToyDDMConfig, verbose: bool)
    O(1) alias-method sampler with IDW demand surface from hotspots.
    Implements: get_point(), node_probabilities, max_prob, drivable_nodes.

toy_setup_from_yaml(yaml_path: str, verbose: bool) -> (CityGraph, ToyDDM, dict)
    One-shot loader. Returns the city, sampler, and raw config dict.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

import yaml

from .node import Node
from .directed_edge import DirEdge
from .city_graph import CityGraph

if TYPE_CHECKING:
    from PIL import Image


# ──────────────────────────────────────────────────────────────────────────────
# Config dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ToyHotspot:
    """A named demand attractor with a geographic position and intensity weight."""
    name: str
    lon: float
    lat: float
    weight: float   # Relative demand intensity. Higher = more passenger demand nearby.


@dataclass
class ToyCityConfig:
    """Grid geometry for the toy city."""
    grid_size: int = 10          # N × N nodes
    origin_lon: float = 124.200  # Bottom-left corner longitude
    origin_lat: float = 8.200    # Bottom-left corner latitude
    step_deg: float = 0.001      # ~110 m per grid step at lat ≈ 8.2°


@dataclass
class ToyDDMConfig:
    """Demand surface config: IDW power and hotspot list."""
    idw_power: float = 2.0
    hotspots: list[ToyHotspot] = field(default_factory=lambda: [
        ToyHotspot("Market District",   124.202, 8.207, 12.0),
        ToyHotspot("Jeepney Terminal",  124.208, 8.201,  9.0),
        ToyHotspot("University",        124.205, 8.205,  6.0),
        ToyHotspot("Residential North", 124.208, 8.208,  2.0),
        ToyHotspot("Industrial South",  124.201, 8.201,  4.0),
    ])


# ──────────────────────────────────────────────────────────────────────────────
# CityGraph builder
# ──────────────────────────────────────────────────────────────────────────────

def build_toy_city(config: ToyCityConfig = ToyCityConfig()) -> CityGraph:
    """
    Build a synthetic N×N grid CityGraph via CityGraph.inject_toy_data().

    Topology
    --------
    Nodes are placed on a regular lat/lon grid. Every adjacent pair of nodes
    (horizontal and vertical neighbours) is connected by a pair of bidirectional
    drivable DirEdges, giving a Manhattan-grid road network.

    All edges are marked is_drivable=True so RouteGenerator can sample any node
    as a valid waypoint and find drivable paths everywhere on the grid.

    Returns
    -------
    CityGraph
        Fully stitched, ready to pass to DirectDemandSampler / ToyDDM.
    """
    n = config.grid_size
    step = config.step_deg

    # --- Build nodes ---------------------------------------------------------
    nodes: list[Node] = []
    node_grid: dict[tuple[int, int], Node] = {}

    for row in range(n):
        for col in range(n):
            lon = config.origin_lon + col * step
            lat = config.origin_lat + row * step
            node = Node(lon, lat)
            nodes.append(node)
            node_grid[(row, col)] = node

    # --- Build edges (both directions, all drivable) -------------------------
    edges: list[DirEdge] = []

    for row in range(n):
        for col in range(n):
            current = node_grid[(row, col)]

            # Horizontal: current → right
            if col + 1 < n:
                right = node_grid[(row, col + 1)]
                edges.append(DirEdge(current, right, is_drivable=True))
                edges.append(DirEdge(right, current, is_drivable=True))

            # Vertical: current → up
            if row + 1 < n:
                up = node_grid[(row + 1, col)]
                edges.append(DirEdge(current, up, is_drivable=True))
                edges.append(DirEdge(up, current, is_drivable=True))

    # --- Inject into an empty CityGraph shell --------------------------------
    city = CityGraph()          # bbox=None → empty shell, no OSM, no PBF
    city.inject_toy_data(nodes, edges)
    city.name = f"ToyCity({n}×{n})"
    return city


# ──────────────────────────────────────────────────────────────────────────────
# ToyDDM — drop-in for DirectDemandSampler
# ──────────────────────────────────────────────────────────────────────────────

class ToyDDM:
    """
    Spatially-varied demand sampler for the toy city.

    Demand Surface
    --------------
    Each node receives a raw probability proportional to the IDW-weighted
    sum of hotspot intensities:

        raw_i = Σ_h  ( weight_h / dist(node_i, hotspot_h)^p )

    This creates a smooth demand landscape
    with high-demand zones near heavy hotspots and low-demand zones far from all
    hotspots, mimicking the real DDM's output without any API calls.

    Sampling
    --------
    Walker's alias method for O(1) per-sample cost — identical to the real
    DirectDemandSampler so performance characteristics are comparable.

    Interface
    ---------
    Implements exactly the attributes and methods consumed by downstream modules:
        • get_point(only_drivable=False) -> Node
        • node_probabilities: dict[Node, float]
        • max_prob: float
        • drivable_nodes: set[Node]
        • draw_density(img_map, context, num_points, only_drivable)
    """

    def __init__(
        self,
        city: CityGraph,
        config: ToyDDMConfig = ToyDDMConfig(),
        verbose: bool = False,
    ) -> None:
        self.city = city
        self.config = config
        self.verbose = verbose

        self.node_list: list[Node] = list(city.nodes)
        self.n: int = len(self.node_list)

        if self.n == 0:
            raise ValueError("[TOY DDM] CityGraph has no nodes.")

        self.drivable_nodes: set[Node] = self._extract_drivable_nodes()
        self.node_probabilities: dict[Node, float] = {}
        self.max_prob: float = 0.0

        # Alias table storage (Walker's method)
        self.prob: list[float] = [0.0] * self.n
        self.alias: list[int] = [0] * self.n

        raw_probs = self._compute_raw_probs()
        self._build_alias_tables(raw_probs)

        if verbose:
            self._print_summary()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_drivable_nodes(self) -> set[Node]:
        drivable: set[Node] = set()
        for edge in self.city.graph:
            if getattr(edge, "is_drivable", False):
                drivable.add(edge.start)
                drivable.add(edge.end)
        return drivable

    def _compute_raw_probs(self) -> list[float]:
        """
        Compute raw IDW probability for every node in node_list.

        Each node's raw score is the IDW-weighted average of hotspot weights,
        so nodes closest to the heaviest hotspot get the highest score.
        A tiny epsilon guard (1e-9) prevents division-by-zero for the
        degenerate case where a node sits exactly on a hotspot centre.
        """
        p = self.config.idw_power
        raw: list[float] = []

        for node in self.node_list:
            numerator = 0.0
            denominator = 0.0
            for hs in self.config.hotspots:
                dist = math.hypot(node.lon - hs.lon, node.lat - hs.lat)
                if dist < 1e-9:
                    dist = 1e-9
                w = 1.0 / (dist ** p)
                numerator += hs.weight * w
                denominator += w
            raw.append(numerator / denominator if denominator > 0 else 1.0)

        return raw

    def _build_alias_tables(self, raw_probs: list[float]) -> None:
        """Walker's alias method — identical implementation to DirectDemandSampler."""
        total = sum(raw_probs)
        if total == 0:
            raise ValueError("[TOY DDM] All raw probabilities are zero. Check hotspot config.")

        for i, node in enumerate(self.node_list):
            self.node_probabilities[node] = raw_probs[i] / total
        self.max_prob = max(self.node_probabilities.values())

        scaled = [(p / total) * self.n for p in raw_probs]
        small: list[int] = []
        large: list[int] = []

        for i, p in enumerate(scaled):
            (small if p < 1.0 else large).append(i)

        while small and large:
            l = small.pop()
            g = large.pop()
            self.prob[l] = scaled[l]
            self.alias[l] = g
            scaled[g] = (scaled[g] + scaled[l]) - 1.0
            (small if scaled[g] < 1.0 else large).append(g)

        for i in large:
            self.prob[i] = 1.0
        for i in small:
            self.prob[i] = 1.0

    def _print_summary(self) -> None:
        print(f"[TOY DDM] Built demand surface over {self.n} nodes "
              f"({len(self.drivable_nodes)} drivable) "
              f"using {len(self.config.hotspots)} hotspots.")

        # Find the highest-demand node for each hotspot for quick sanity check
        for hs in self.config.hotspots:
            nearest = min(
                self.node_list,
                key=lambda n: math.hypot(n.lon - hs.lon, n.lat - hs.lat)
            )
            p = self.node_probabilities.get(nearest, 0.0)
            print(f"  · [{hs.name}]  weight={hs.weight:.1f}  "
                  f"nearest_node_prob={p:.5f}")

        # Demand contrast: ratio of max to min probability
        min_prob = min(self.node_probabilities.values())
        contrast = self.max_prob / min_prob if min_prob > 0 else float("inf")
        print(f"  Demand contrast (max/min prob): {contrast:.1f}×")

    # ── Public interface (matches DirectDemandSampler) ────────────────────────

    def get_point(self, only_drivable: bool = False) -> Node:
        """
        O(1) alias-method sample. Returns a Node drawn proportional to
        its IDW demand probability. If only_drivable=True, keeps resampling
        until a node on a drivable edge is returned (in the toy grid every
        non-corner node qualifies, so this is fast).
        """
        if only_drivable and not self.drivable_nodes:
            raise ValueError("[TOY DDM] No drivable nodes available.")

        while True:
            i = random.randint(0, self.n - 1)
            node = (
                self.node_list[i]
                if random.random() <= self.prob[i]
                else self.node_list[self.alias[i]]
            )
            if not only_drivable or node in self.drivable_nodes:
                return node

    def draw_density(
        self,
        img_map: "Image.Image",
        context: tuple[tuple[float, float], tuple[float, float]],
        num_points: int = 2000,
        only_drivable: bool = False,
    ) -> None:
        """
        Scatter-plot the demand surface onto img_map.
        Color scale: blue (low) → yellow → red (high), same as DirectDemandSampler.
        """
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img_map)
        tl_lon, tl_lat = context[0]
        br_lon, br_lat = context[1]
        lon_range = br_lon - tl_lon
        lat_range = tl_lat - br_lat

        for _ in range(num_points):
            node = self.get_point(only_drivable=only_drivable)
            prob_ratio = self.node_probabilities[node] / self.max_prob

            if prob_ratio < 0.5:
                t = prob_ratio * 2.0
                r, g, b = int(255 * t), int(255 * t), int(255 * (1.0 - t))
            else:
                t = (prob_ratio - 0.5) * 2.0
                r, g, b = 255, int(255 * (1.0 - t)), 0

            x = (node.lon - tl_lon) / lon_range * img_map.width
            y = (tl_lat - node.lat) / lat_range * img_map.height
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(r, g, b, 160))


# ──────────────────────────────────────────────────────────────────────────────
# One-shot YAML loader
# ──────────────────────────────────────────────────────────────────────────────

def toy_setup_from_yaml(
    yaml_path: str = "configs/toy_city_configs.yaml",
    verbose: bool = True,
) -> tuple[CityGraph, ToyDDM, dict]:
    """
    Load the toy city config from YAML and return:
        city    — fully stitched CityGraph (NxN grid)
        sampler — ToyDDM with IDW demand surface
        cfg     — raw config dict (pass cfg['travel_graph'] to TravelGraph,
                  cfg['simulation'] for sim params, etc.)

    Example
    -------
    city, sampler, cfg = toy_setup_from_yaml()
    sim_cfg = cfg['simulation']
    tg_cfg  = cfg['travel_graph']
    """
    with open(yaml_path, "r") as f:
        cfg = yaml.safe_load(f)

    # --- Build ToyCityConfig -------------------------------------------------
    tc_raw = cfg.get("toy_city", {})
    city_config = ToyCityConfig(
        grid_size=tc_raw.get("grid_size", 10),
        origin_lon=tc_raw.get("origin_lon", 124.200),
        origin_lat=tc_raw.get("origin_lat", 8.200),
        step_deg=tc_raw.get("step_deg", 0.001),
    )

    # --- Build ToyDDMConfig --------------------------------------------------
    td_raw = cfg.get("toy_ddm", {})
    raw_hotspots = td_raw.get("hotspots", [])

    if raw_hotspots:
        hotspots = [
            ToyHotspot(
                name=hs["name"],
                lon=float(hs["lon"]),
                lat=float(hs["lat"]),
                weight=float(hs["weight"]),
            )
            for hs in raw_hotspots
        ]
    else:
        hotspots = ToyDDMConfig().hotspots  # fall back to defaults

    ddm_config = ToyDDMConfig(
        idw_power=float(td_raw.get("idw_power", 2.0)),
        hotspots=hotspots,
    )

    # --- Construct -----------------------------------------------------------
    if verbose:
        print(f"[TOY CITY] Building {city_config.grid_size}×{city_config.grid_size} grid…")

    city = build_toy_city(city_config)

    if verbose:
        print(city)

    sampler = ToyDDM(city, ddm_config, verbose=verbose)

    return city, sampler, cfg
