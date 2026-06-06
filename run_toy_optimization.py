"""
run_toy_optimization.py -- launch a SHORT toy-city optimization with PER-GENERATION telemetry, so
fig_optimization.py can replay the gen 1 -> gen N evolution for Chapter 4.4.1.

It clones configs/toy_city_configs.yaml and overrides only what the showcase needs:
  * simulation : num_routes=10, and the production-calibrated stable values
                 (num_ticks=540, seconds_per_tick=10, spawn_rate_per_hour=600, weight_tolerance=14.44)
  * optimization: telemetry_interval=1 (snapshot EVERY generation) and g_max=<generations>

Press play and leave. At the end it prints the run directory and the exact fig_optimization command.

    python run_toy_optimization.py
    python run_toy_optimization.py --routes 10 --generations 30 --population 20 --fleet 100

Runtime note: this runs ~g_max * n_population toy simulations at num_ticks=540. It is the only piece
of this showcase that actually invokes the simulator (and needs pyrosm); expect several minutes.
"""
import argparse
import os
from datetime import datetime

import yaml

BASE_CONFIG = "configs/toy_city_memetic.yaml"  # Gaussian 'real city' demand (CBD + Port)

# Production-calibrated stable simulation values (Sec 4.3.1 / 4.3.3).
STABLE = {
    "num_ticks": 540,
    "seconds_per_tick": 10,
    "spawn_rate_per_hour": 600.0,
    "weight_tolerance": 14.44,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--routes", type=int, default=10, help="routes per network (default 10)")
    ap.add_argument("--generations", type=int, default=30, help="g_max generations (default 30)")
    ap.add_argument("--population", type=int, default=20, help="n_population (default 20)")
    ap.add_argument("--fleet", type=int, default=100, help="total_allocatable_jeeps (default 100)")
    args = ap.parse_args()

    if not os.path.exists(BASE_CONFIG):
        raise SystemExit(f"Base config not found: {BASE_CONFIG}")
    with open(BASE_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    sim = cfg.setdefault("simulation", {})
    sim["num_routes"] = args.routes
    sim["total_allocatable_jeeps"] = args.fleet
    sim.update(STABLE)

    opt = cfg.setdefault("optimization", {})
    opt["telemetry_interval"] = 1                       # snapshot every generation -> smooth replay
    opt["checkpoint_interval"] = max(5, args.generations // 3)
    opt["g_max"] = args.generations
    opt["n_population"] = args.population
    cfg["disable_tqdm"] = False

    os.makedirs("outputs", exist_ok=True)
    cfg_path = os.path.join("outputs", f"toy_opt_showcase_{datetime.now():%Y%m%d_%H%M%S}.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    print(f"[toy-opt] wrote {cfg_path}")
    print(f"[toy-opt] {args.routes} routes | g_max={args.generations} | pop={args.population} | "
          f"fleet={args.fleet} | num_ticks=540 spt=10 spawn=600 | snapshot every generation")

    from utils.optimizer import Optimizer
    opt_run = Optimizer.create(cfg_path)
    print(f"[toy-opt] run_dir = {opt_run.run_dir}")
    opt_run.start()
    print("\n[toy-opt] DONE. Render the showcase figures with either:")
    print("    python fig_optimization.py                       # auto-finds this (newest) run")
    print(f'    python fig_optimization.py --run-dir "{opt_run.run_dir}"   # or point at it explicitly')


if __name__ == "__main__":
    main()
