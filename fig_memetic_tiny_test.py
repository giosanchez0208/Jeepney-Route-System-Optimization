"""Tiny smoke test for fig_memetic.py -- exercises all four memetic showcase figures on a synthetic
stub scene (no pyrosm, no simulation, no optimizer). Verifies each renders + saves a non-trivial PNG
and that the edge-field renderer handles the empty-pheromone edge case. Runs in ~2-4s.

Run:  python fig_memetic_tiny_test.py
"""
import os
import random
import tempfile

from PIL import Image

import fig_memetic as fm


# ---- minimal stand-ins matching the renderer contracts -------------------------------
class _N:
    def __init__(self, lon, lat, i):
        self.lon = lon; self.lat = lat; self.id = i


class _E:
    _c = 0
    def __init__(self, a, b):
        self.start = a; self.end = b
        self.id = _E._c; _E._c += 1


class _R:
    def __init__(self, edges):
        self.path = edges


class _PH:
    def __init__(self, tau, gaps):
        self.tau = tau; self.gaps = gaps


class _Chrom:
    def __init__(self, routes, ph, cost):
        self.routes = routes; self.pheromones = ph; self.cost = cost


class _CG:
    def __init__(self, nodes):
        self._n = nodes
    def get_bounds(self):
        lons = [n.lon for n in self._n]; lats = [n.lat for n in self._n]
        return ((min(lons), max(lats)), (max(lons), min(lats)))
    def draw(self, size=800, only_drivable=False):
        return Image.new("RGB", (size, size), "white")


class _Sampler:
    def __init__(self, node_probs):
        self.node_probabilities = node_probs


def _grid(n=5, step=0.01, lon0=124.2, lat0=8.2):
    return {(i, j): _N(lon0 + step * i, lat0 + step * j, 1000 + i * n + j) for i in range(n) for j in range(n)}


def _make_parent(nodes, n_routes, rng, cost):
    coords = list(nodes.values())
    routes, all_edges = [], []
    for _ in range(n_routes):
        seq = rng.sample(coords, 4)
        edges = [_E(seq[k], seq[k + 1]) for k in range(3)]
        routes.append(_R(edges)); all_edges += edges
    tau = {e: 1.0 + rng.random() * 5.0 for e in all_edges}   # several above the 1.1 floor
    gaps = {e: rng.uniform(-0.4, 0.5) for e in all_edges}
    return _Chrom(routes, _PH(tau, gaps), cost)


def _stub_scene():
    nodes = _grid(5)
    cg = _CG(list(nodes.values()))
    rng = random.Random(7)
    A = _make_parent(nodes, 3, rng, cost=1200.0)
    B = _make_parent(nodes, 3, rng, cost=1500.0)

    tau_a = A.pheromones.tau
    k = max(1, len(tau_a) // 10)
    hub_ids = {e.id for e in sorted(tau_a, key=lambda e: tau_a[e], reverse=True)[:k]}
    trunk = [r for r in A.routes if any(e.id in hub_ids for e in r.path)] or [A.routes[0]]

    child_routes = [_R(r.path[:]) for r in trunk] + [_R(B.routes[0].path[:])]
    prov = ["trunk"] * len(trunk) + ["feeder"]
    child_tau = {e: 1.0 + rng.random() * 4.0 for r in child_routes for e in r.path}
    child_gaps = {e: rng.uniform(-0.3, 0.3) for r in child_routes for e in r.path}
    child = _Chrom(child_routes, _PH(child_tau, child_gaps), cost=1300.0)

    blend = _PH({e: tau_a[e] for r in A.routes for e in r.path}, {})
    sampler = _Sampler({n: rng.random() for n in nodes.values()})

    stats = {
        "A_fsim": A.cost, "B_fsim": B.cost, "child_fsim": child.cost,
        "A_disp": fm.total_disparity(A.pheromones), "B_disp": fm.total_disparity(B.pheromones),
        "child_disp": fm.total_disparity(child.pheromones), "A_completed": 123,
        "hub_edges": len(hub_ids), "hub_share": 0.27,
        "wA": B.cost / (A.cost + B.cost), "wB": A.cost / (A.cost + B.cost),
    }
    return {
        "cg": cg, "ctx": cg.get_bounds(), "extent": fm._extent(cg), "base": cg.draw(400),
        "sampler": sampler, "A": A, "B": B, "child": child, "child_blend_ph": blend,
        "hub_edge_ids": hub_ids, "trunk_routes": trunk, "feeder_routes": [B.routes[0]],
        "child_provenance": prov, "stats": stats,
    }


def test_every_figure_renders_a_png():
    fm.set_pub_style()
    scene = _stub_scene()
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn in fm.FIGS.items():
            out = os.path.join(tmp, f"{name}.png")
            assert fn(scene, out) == out
            assert os.path.exists(out) and os.path.getsize(out) > 2000, f"{name} produced no/tiny PNG"


def test_edge_field_handles_empty():
    import matplotlib.pyplot as plt
    from matplotlib.colors import PowerNorm
    fig, ax = plt.subplots()
    sm = fm._edge_field(ax, None, [124.2, 124.3, 8.2, 8.3], [], "viridis", PowerNorm(0.5, 1.0, 6.0))
    fig.colorbar(sm, ax=ax)  # must not raise even with no edges
    plt.close(fig)


def test_total_disparity_sums_abs_gaps():
    ph = _PH({}, {1: 0.3, 2: -0.2, 3: 0.5})
    assert abs(fm.total_disparity(ph) - 1.0) < 1e-9


if __name__ == "__main__":
    test_every_figure_renders_a_png()
    test_edge_field_handles_empty()
    test_total_disparity_sums_abs_gaps()
    print(f"OK: fig_memetic tiny test passed ({len(fm.FIGS)} figures rendered)")
