"""
opt_run.py — shared runner for the final Iligan optimizations.

Each opt_pN.py is a one-line wrapper around run_profile() so that launching a run on a machine
is brain-dead: `python opt_pN.py`. This module does the actual work:

  * seeds random / numpy (the optimizer itself does NOT seed, so reproducibility-by-seed lives here),
  * loads configs/profile_p1.yaml and applies the per-profile overrides (DDM pkl, output tag),
  * writes a tagged run config and launches Optimizer.create(...).start().

Outputs land under outputs/final_runs/<tag>/opt_<timestamp>/ so opt_eval.py can discover and group
them by profile tag.
"""
from __future__ import annotations

import os
import sys
import random
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import yaml

BASE_CONFIG = "configs/profile_p1.yaml"
FINAL_ROOT = "outputs/final_runs"


def run_profile(tag: str, seed: int, ddm_pkl: str | None = None, start: bool = True):
    """
    Launch one final optimization.

    Args:
        tag:     profile label, e.g. "p1" or "p8_1pm". Becomes the output sub-folder.
        seed:    RNG seed for the GA's stochastic decisions (initial population, crossover, mutation).
                 Worker passenger spawning remains independently stochastic by design.
        ddm_pkl: optional DDM pickle override (e.g. rnd/pkl/ddm_1pm.pkl) for temporal-regime runs.
        start:   if False, builds the optimizer and returns without running (used for dry-run checks).
    """
    random.seed(seed)
    np.random.seed(seed)

    with open(BASE_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if ddm_pkl is not None:
        cfg["ddm_pkl"] = ddm_pkl
    cfg["optimization"]["output_root"] = f"{FINAL_ROOT}/{tag}"
    cfg["seed"] = seed  # recorded into the run's configs.yaml for traceability

    out_root = Path(f"{FINAL_ROOT}/{tag}")
    out_root.mkdir(parents=True, exist_ok=True)
    cfg_path = out_root / "_run_config.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    print("=" * 70)
    print(f"[FINAL RUN] tag={tag} | seed={seed} | ddm={cfg.get('ddm_pkl')}")
    print(f"[FINAL RUN] routes={cfg['simulation']['num_routes']} "
          f"fleet={cfg['simulation']['total_allocatable_jeeps']} "
          f"g_max={cfg['optimization']['g_max']} pop={cfg['optimization']['n_population']}")
    print(f"[FINAL RUN] output -> {out_root}/opt_<timestamp>/")
    print("=" * 70)

    from utils.optimizer import Optimizer
    opt = Optimizer.create(cfg_path)
    if start:
        opt.start()
    return opt
