"""run_ablation_toy.py -- GA-only vs ACO-only vs hybrid ablation on the toy city (Ask #5).

Runs three short toy-city optimizations that differ ONLY in which operators are active:

  hybrid   : crossover + pheromone inheritance + Lamarckian local search  (the full system)
  ga_only  : crossover + plain random mutation, no ACO memory, no Lamarckian search
  aco_only : single-lineage pheromone memory + Lamarckian local search, no crossover

All three are launched from the SAME seed, so they start from the same initial population
and see the same selection draws; the separation in their convergence curves is therefore
attributable to the operators rather than to luck. The harness itself is just three config
flags (use_crossover / use_pheromone_inheritance / use_local_search) read by ExperimentConfig.

    python run_ablation_toy.py
    python run_ablation_toy.py --generations 20 --population 12 --num-ticks 300

Writes per-arm runs under outputs/ablation/<stamp>/<arm>/ and a convergence-comparison
figure to outputs/ablation/<stamp>/ablation_convergence.png (plus a stable copy at
outputs/ablation/ablation_convergence.png). The identical flags drive the real Iligan
ablation too (see configs/ablation/, for the groupmate's overnight run).
"""
import argparse
import csv
import os
import random
from datetime import datetime

import numpy as np
import yaml

BASE_CONFIG = "configs/toy_city_memetic.yaml"

# Each arm is fully defined by the three ablation flags. Order matters only for plotting.
ARMS = {
    "hybrid":   dict(use_crossover=True,  use_pheromone_inheritance=True,  use_local_search=True),
    "ga_only":  dict(use_crossover=True,  use_pheromone_inheritance=False, use_local_search=False),
    "aco_only": dict(use_crossover=False, use_pheromone_inheritance=True,  use_local_search=True),
}
ARM_LABEL = {"hybrid": "Hybrid GA-ACO", "ga_only": "GA only", "aco_only": "ACO only"}
ARM_COLOR = {"hybrid": "#2F8F57", "ga_only": "#C9821B", "aco_only": "#33608C"}


def run_arm(name: str, flags: dict, args, stamp: str) -> str:
    """Launch one ablation arm and return its run directory."""
    with open(BASE_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    sim = cfg.setdefault("simulation", {})
    sim["num_routes"] = args.routes
    sim["total_allocatable_jeeps"] = args.fleet
    sim["num_ticks"] = args.num_ticks
    sim["spawn_rate_per_hour"] = args.spawn

    opt = cfg.setdefault("optimization", {})
    opt["telemetry_interval"] = 1
    opt["checkpoint_interval"] = max(5, args.generations)
    opt["g_max"] = args.generations
    opt["n_population"] = args.population
    opt["output_root"] = f"outputs/ablation/{stamp}/{name}"
    opt.update(flags)  # the only thing that differs across arms
    cfg["disable_tqdm"] = True

    run_root = f"outputs/ablation/{stamp}"
    os.makedirs(run_root, exist_ok=True)
    cfg_path = os.path.join(run_root, f"cfg_{name}.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    # Identical seed across arms -> identical initial population and GA draws.
    random.seed(args.seed)
    np.random.seed(args.seed)

    from utils.optimizer import Optimizer
    o = Optimizer.create(cfg_path)
    print(f"[ablation:{name}] flags={flags} run_dir={o.run_dir}")
    o.start()
    return str(o.run_dir)


def load_history(run_dir: str):
    """Return (generations, global_best_cost) from a run's history.csv."""
    gens, best = [], []
    with open(os.path.join(run_dir, "history.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gens.append(int(row["Generation"]))
            best.append(float(row["Global_Best_Cost"]))
    return gens, best


def plot(results: dict, out_path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    for name in ("ga_only", "aco_only", "hybrid"):
        if name not in results:
            continue
        gens, best = results[name]
        if not best:
            continue
        improve = 100.0 * (best[0] - best[-1]) / best[0] if best[0] else 0.0
        ax.plot(gens, best, color=ARM_COLOR[name], lw=2.2, marker="o", ms=3,
                label=f"{ARM_LABEL[name]}  (final {best[-1]:.0f}, -{improve:.1f}%)")
    ax.set_xlabel("Generation")
    ax.set_ylabel(r"Global best $F_{\mathrm{sim}}$ (lower is better)")
    ax.set_title("Operator ablation on the toy city: GA-only vs ACO-only vs hybrid")
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    fig.savefig("outputs/ablation/ablation_convergence.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[ablation] wrote {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--routes", type=int, default=6)
    ap.add_argument("--generations", type=int, default=18)
    ap.add_argument("--population", type=int, default=12)
    ap.add_argument("--fleet", type=int, default=60)
    ap.add_argument("--num-ticks", type=int, default=300, help="short horizon for the toy preview")
    ap.add_argument("--spawn", type=float, default=600.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--arms", default="hybrid,ga_only,aco_only")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}
    for name in [a.strip() for a in args.arms.split(",") if a.strip()]:
        if name not in ARMS:
            raise SystemExit(f"unknown arm '{name}'; choose from {list(ARMS)}")
        results[name] = load_history(run_arm(name, ARMS[name], args, stamp))

    plot(results, f"outputs/ablation/{stamp}/ablation_convergence.png")
    print("\n[ablation] summary (lower final F_sim is better):")
    for name in ("ga_only", "aco_only", "hybrid"):
        if name in results and results[name][1]:
            best = results[name][1]
            print(f"  {ARM_LABEL[name]:14s} final={best[-1]:.0f}  start={best[0]:.0f}")


if __name__ == "__main__":
    main()
