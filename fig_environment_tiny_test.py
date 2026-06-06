"""Tiny smoke test for fig_environment.py -- exercises every figure builder on synthetic stub
CityGraph/DDM objects (no pickles, no simulation). Confirms each renders + saves a non-trivial PNG
and that the shared demand norm spans the data. Runs in ~2-4s.

Run:  python fig_environment_tiny_test.py
"""
import os
import tempfile

import numpy as np
from PIL import Image

import fig_environment as fe


class _N:
    def __init__(self, lon, lat):
        self.lon = lon
        self.lat = lat


class _CG:
    def __init__(self):
        self._nodes = [_N(124.20 + 0.012 * i, 8.20 + 0.012 * j) for i in range(6) for j in range(6)]
        self.landmarks = {}

    def get_bounds(self):
        # Mirror CityGraph.get_bounds (derive from nodes) so previews fill the panel like real data
        lons = [n.lon for n in self._nodes]
        lats = [n.lat for n in self._nodes]
        return ((min(lons), max(lats)), (max(lons), min(lats)))

    def draw(self, size=800, only_drivable=False):
        return Image.new("RGB", (size, size), "white")

    def _build_landmarks(self, mapping):
        for name in mapping:
            self.landmarks[name] = self._nodes[0]

    def draw_landmarks(self, image):
        return image


class _DDM:
    def __init__(self, nodes, scale=1.0):
        self.node_probabilities = {n: scale * (0.5 + 0.5 * np.sin(i)) ** 3 for i, n in enumerate(nodes)}
        self.centrality_scores = {n: float(i) for i, n in enumerate(nodes)}
        self.traffic_weights = {n: 1.0 + 0.05 * i for i, n in enumerate(nodes)}
        self.empirical_traffic = {n: 1.0 + 0.1 * i for i, n in enumerate(nodes[:8])}
        self.drivable_nodes = set(nodes[: len(nodes) // 2])


def _assets():
    cg = _CG()
    ddm = {
        "8:00 AM": _DDM(cg._nodes, scale=0.8),
        "1:00 PM": _DDM(cg._nodes, scale=1.0),
        "5:00 PM": _DDM(cg._nodes, scale=1.3),
    }
    return {"cg": cg, "ddm": ddm}


def test_demand_norm_spans_all_ddms():
    A = _assets()
    norm = fe._demand_norm(*A["ddm"].values())
    assert norm.vmin == 0.0
    # vmax must reach the strongest demand across the three time slices (the 1.3-scaled one)
    strongest = max(max(d.node_probabilities.values()) for d in A["ddm"].values())
    assert abs(norm.vmax - strongest) < 1e-9, "shared norm must span the busiest time slice"


def test_every_figure_renders_a_png():
    fe.set_pub_style()
    A = _assets()
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in fe.FIGS.items():
            out = os.path.join(tmp, f"{name}.png")
            returned = fn(A, out)
            assert returned == out
            assert os.path.exists(out), f"{name} did not write a file"
            assert os.path.getsize(out) > 2000, f"{name} produced a suspiciously tiny PNG"


if __name__ == "__main__":
    test_demand_norm_spans_all_ddms()
    test_every_figure_renders_a_png()
    print(f"OK: fig_environment tiny test passed ({len(fe.FIGS)} figures rendered)")
