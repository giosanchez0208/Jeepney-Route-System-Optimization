"""run_ablation_toy_tiny_test.py -- smoke test for the GA/ACO ablation harness.

Runs all three arms for 2 generations at a tiny population and a very short horizon, purely
to prove the ablation branches execute end-to-end and write a history:
  - hybrid   : crossover + inherit_pheromones + Lamarckian local search
  - ga_only  : crossover + blank pheromone + random route mutation (no local search)
  - aco_only : single-parent clone + inherited pheromone + forced local search (no crossover)
This is NOT a quality run; it only guards against the new branches crashing.
"""
import os as _os, sys as _sys
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)

import os
import types
from datetime import datetime

import scripts.run_ablation_toy as R


def main():
    args = types.SimpleNamespace(routes=4, generations=2, population=3, fleet=20,
                                 num_ticks=30, spawn=600.0, seed=7,
                                 arms="hybrid,ga_only,aco_only")
    stamp = "tinytest_" + datetime.now().strftime("%H%M%S")
    for name in ("hybrid", "ga_only", "aco_only"):
        run_dir = R.run_arm(name, R.ARMS[name], args, stamp)
        assert os.path.exists(os.path.join(run_dir, "history.csv")), f"no history for {name}"
        gens, best = R.load_history(run_dir)
        assert best, f"empty history for {name}"
        print(f"[tiny] {name:8s}: {len(best)} gens, final F={best[-1]:.0f}")
    print("[tiny] ablation harness OK")


if __name__ == "__main__":
    main()
