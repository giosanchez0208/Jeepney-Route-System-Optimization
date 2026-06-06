"""Tiny smoke test for fig_optimization.py -- synthesizes a stub optimizer run directory (history.csv
+ snapshot JSONs matching utils/optimizer_telemetry.py's schema) and verifies the replay renderer
loads it, detects best-improvement generations, and renders both figures. No pyrosm, no simulation.

Run:  python fig_optimization_tiny_test.py
"""
import csv
import json
import os
import tempfile

import numpy as np

import fig_optimization as fo


def _route(pts):
    return [{"lat": la, "lon": lo} for lo, la in pts]


def _snapshot(gen, best, mean, n_routes=4):
    rng = np.random.default_rng(100 + gen)
    lon0, lat0, step = 124.20, 8.20, 0.01
    routes, phero, chokes = [], [], []
    for _ in range(n_routes):
        pts = [(lon0 + step * int(rng.integers(0, 6)), lat0 + step * int(rng.integers(0, 6))) for _ in range(5)]
        routes.append(_route(pts))
        for i in range(len(pts) - 1):
            phero.append({"edge": [{"lat": pts[i][1], "lon": pts[i][0]},
                                   {"lat": pts[i + 1][1], "lon": pts[i + 1][0]}],
                          "intensity": round(1.1 + float(rng.random()) * 5.0, 2)})
    for _ in range(3):
        chokes.append({"lat": lat0 + step * float(rng.random()) * 6,
                       "lon": lon0 + step * float(rng.random()) * 6,
                       "gap_value": round(5.0 + float(rng.random()) * 10.0, 2)})
    return {
        "generation": gen,
        "metadata": {"best_cost": best, "mean_cost": mean,
                     "topological_hub": {"lat": lat0 + step * 3, "lon": lon0 + step * 3}},
        "distributions": {"fitness": [best, mean], "unserved_proxy": [1.0, 2.0]},
        "layers": {"routes": routes, "pheromones": phero, "chokepoints": chokes},
    }


# best cost decreasing with plateaus -> improvements at gens 0, 2, 5, 9
BESTS = [1000, 1000, 950, 950, 950, 900, 900, 900, 900, 860, 860, 860]


def _make_run(tmp):
    snaps_dir = os.path.join(tmp, "snapshots")
    os.makedirs(snaps_dir, exist_ok=True)
    with open(os.path.join(tmp, "history.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Generation", "Global_Best_Cost", "Population_Mean_Cost",
                    "Active_Mutation_Rate", "Stagnation_Counter"])
        for g, b in enumerate(BESTS):
            mean = b + 120 + (g % 3) * 10
            mut = round(0.2 + 0.3 * ((g % 5) / 5), 3)
            w.writerow([g, b, mean, mut, g % 4])
            with open(os.path.join(snaps_dir, f"network_state_gen_{g}.json"), "w") as sf:
                json.dump(_snapshot(g, b, mean), sf)
    return tmp


def test_load_and_improvements():
    with tempfile.TemporaryDirectory() as tmp:
        run = fo.load_run(_make_run(tmp))
        assert len(run["history"]) == len(BESTS)
        assert len(run["snaps"]) == len(BESTS)
        assert fo.improvement_generations(run["history"]) == [0, 2, 5, 9]


def test_figures_render():
    fo.set_pub_style()
    with tempfile.TemporaryDirectory() as tmp:
        run = fo.load_run(_make_run(tmp))
        for name, fn in fo.FIGS.items():
            out = os.path.join(tmp, f"{name}.png")
            assert fn(run, out) == out
            assert os.path.getsize(out) > 2000, f"{name} produced no/tiny PNG"


def test_sample_columns_caps():
    assert fo._sample_columns(list(range(20)), k=5) == [0, 5, 10, 14, 19] or len(fo._sample_columns(list(range(20)), 5)) <= 5


if __name__ == "__main__":
    test_load_and_improvements()
    test_figures_render()
    test_sample_columns_caps()
    print(f"OK: fig_optimization tiny test passed ({len(fo.FIGS)} figures rendered)")
