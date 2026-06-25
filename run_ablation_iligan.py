"""run_ablation_iligan.py -- the REAL GA/ACO ablation on Iligan (Ask #5), for the heavy machine.

Same three arms as run_ablation_toy.py, but built on configs/profile_p1.yaml so it uses the
full Iligan CityGraph + 8am DDM, 38 routes, 2000 jeeps, the 540-tick horizon, and the
production GA settings (pop 10, g_max 30). Each arm is a full optimization and is SLOW; run it
overnight on the dedicated machine.

  hybrid   : crossover + pheromone inheritance + Lamarckian local search  (the full system)
  ga_only  : crossover + plain random mutation, no ACO memory, no Lamarckian search
  aco_only : single-lineage pheromone memory + Lamarckian local search, no crossover

Usage (all arms share one --tag folder so they can be launched in separate terminals/machines):

    # all three sequentially on one machine (simplest, overnight):
    python run_ablation_iligan.py --tag run1

    # or one arm per terminal / machine, same tag:
    python run_ablation_iligan.py --tag run1 --arms hybrid
    python run_ablation_iligan.py --tag run1 --arms ga_only
    python run_ablation_iligan.py --tag run1 --arms aco_only

    # once arms have finished, build the comparison figure from whatever is present:
    python run_ablation_iligan.py --tag run1 --plot-only

Outputs land under outputs/ablation_iligan/<tag>/<arm>/opt_<timestamp>/ and the figure at
outputs/ablation_iligan/<tag>/ablation_convergence_iligan.png.
"""
import argparse
import glob
import os
import random

import numpy as np
import yaml

from run_ablation_toy import ARMS, ARM_LABEL, ARM_COLOR, load_history

BASE_CONFIG = "configs/profile_p1.yaml"


def run_arm(name: str, flags: dict, args) -> str:
    with open(BASE_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    opt = cfg.setdefault("optimization", {})
    if args.generations:
        opt["g_max"] = args.generations
    opt["telemetry_interval"] = 1
    opt["output_root"] = f"outputs/ablation_iligan/{args.tag}/{name}"
    opt.update(flags)  # the only thing that differs across arms
    cfg["seed"] = args.seed

    run_root = f"outputs/ablation_iligan/{args.tag}/{name}"
    os.makedirs(run_root, exist_ok=True)
    cfg_path = os.path.join(run_root, f"_cfg_{name}.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    # Identical seed across arms -> identical initial population and GA draws.
    random.seed(args.seed)
    np.random.seed(args.seed)

    from utils.optimizer import Optimizer
    o = Optimizer.create(cfg_path)
    print(f"[ablation-iligan:{name}] flags={flags} run_dir={o.run_dir}")
    print(f"[ablation-iligan:{name}] this is a FULL Iligan run; expect a long wall-clock time.")
    o.start()
    return str(o.run_dir)


def find_arm_run(tag: str, name: str):
    """Latest opt_* run dir under outputs/ablation_iligan/<tag>/<name>/, if any."""
    runs = sorted(glob.glob(f"outputs/ablation_iligan/{tag}/{name}/opt_*"))
    return runs[-1] if runs else None


def plot(tag: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    found = 0
    for name in ("ga_only", "aco_only", "hybrid"):
        run_dir = find_arm_run(tag, name)
        if not run_dir or not os.path.exists(os.path.join(run_dir, "history.csv")):
            print(f"[plot] arm '{name}' not finished yet (skipping)")
            continue
        gens, best = load_history(run_dir)
        if not best:
            continue
        improve = 100.0 * (best[0] - best[-1]) / best[0] if best[0] else 0.0
        ax.plot(gens, best, color=ARM_COLOR[name], lw=2.2, marker="o", ms=3,
                label=f"{ARM_LABEL[name]}  (final {best[-1]:.0f}, -{improve:.1f}%)")
        found += 1
    ax.set_xlabel("Generation")
    ax.set_ylabel(r"Global best $F_{\mathrm{sim}}$ (lower is better)")
    ax.set_title("Operator ablation on Iligan: GA-only vs ACO-only vs hybrid")
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = f"outputs/ablation_iligan/{tag}/ablation_convergence_iligan.png"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] wrote {out} ({found} arm(s))")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", default="run1", help="folder grouping all arms of one ablation")
    ap.add_argument("--arms", default="hybrid,ga_only,aco_only")
    ap.add_argument("--generations", type=int, default=0, help="override g_max (0 = use profile_p1's 30)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--plot-only", action="store_true", help="just build the figure from finished arms")
    args = ap.parse_args()

    if not args.plot_only:
        for name in [a.strip() for a in args.arms.split(",") if a.strip()]:
            if name not in ARMS:
                raise SystemExit(f"unknown arm '{name}'; choose from {list(ARMS)}")
            run_arm(name, ARMS[name], args)

    plot(args.tag)


if __name__ == "__main__":
    main()
