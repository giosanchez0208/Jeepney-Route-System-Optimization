"""
Determinism / behaviour-equivalence harness.

Runs ONE fixed, fully-seeded, single-process simulation and prints a compact SIGNATURE
(fitness + passenger metrics). Run the SAME file from two different checkouts (current tree
vs. an old git worktree); if the SIGNATURE lines are byte-identical, the two implementations
are behaviourally identical and the performance refactor is provably result-neutral.

Key design points:
  * sys.path.insert(0, cwd) so `import utils` resolves to THIS checkout's utils/ (run with the
    checkout as the working directory).
  * All input data (pkls, config) is read by ABSOLUTE path from the main repo, so both checkouts
    consume identical inputs.
  * Single-process SimulationEvaluator.evaluate() -> no worker-process RNG, fully reproducible.
  * Small/reduced config -> ~1 min, "lightweight".

Usage:
    cd <checkout-dir>
    <main>/.venv/Scripts/python.exe <main>/scratch/_determinism_check.py
"""
import os
import sys
sys.path.insert(0, os.getcwd())   # import THIS checkout's utils, not wherever the script lives

import json
import random
import traceback

import numpy as np
import yaml

# Inputs always come from the main repo (absolute), so both checkouts see identical data.
MAIN = r"C:\Users\lifei\OneDrive\Desktop\Portfolio\Jeepney-Route-System-Optimization"
SEED = 20260609


def main() -> None:
    from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
    from utils.simulation import SimulationEvaluator

    city = reuse_citygraph(os.path.join(MAIN, "rnd", "pkl", "profile_p1.pkl"))
    ddm = reuse_ddm(os.path.join(MAIN, "rnd", "pkl", "ddm_8am.pkl"))
    config = yaml.safe_load(open(os.path.join(MAIN, "configs", "profile_p1.yaml"), encoding="utf-8"))

    # Reduced, identical-on-both-sides config for a fast check.
    config["disable_tqdm"] = True
    config.setdefault("simulation", {})
    config["simulation"]["num_ticks"] = 180
    config["simulation"]["total_allocatable_jeeps"] = 300
    config["simulation"]["num_routes"] = 12
    config["simulation"]["mohring_sample_size"] = 400

    # Fixed network (route generation is outside the perf refactor; seeded for reproducibility).
    random.seed(SEED)
    np.random.seed(SEED)
    routes = generate_route_system(config["simulation"]["num_routes"], city, ddm)

    # Deterministic single-process evaluation (re-seed right before, so allocation + spawning
    # consume the SAME RNG stream regardless of how many draws route-gen happened to make).
    random.seed(SEED + 1)
    np.random.seed(SEED + 1)
    ev = SimulationEvaluator(config, city, None, ddm)
    res = ev.evaluate(routes)

    m = res.metrics
    sig = {
        "score": round(float(res.score), 4),
        "completed": int(m.get("completed_count", 0)),
        "incomplete": int(m.get("incomplete_count", 0)),
        "sum_completed_time": round(float(m.get("sum_completed_time", 0.0)), 4),
        "sum_penalty_time": round(float(m.get("sum_penalty_time", 0.0)), 4),
        "mean_commute_time": round(float(m.get("mean_commute_time", 0.0)), 6),
        "std_commute_time": round(float(m.get("std_commute_time", 0.0)), 6),
        "n_recorded_paths": len(getattr(res, "recorded_paths", []) or []),
    }
    print("SIGNATURE " + json.dumps(sig, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("HARNESS_ERROR", flush=True)
        traceback.print_exc()
        sys.exit(3)
