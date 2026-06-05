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

    # When several runs share one machine, the launcher caps workers per run via OPT_N_WORKERS
    # so the pools don't oversubscribe cores / RAM. Env overrides the YAML.
    env_workers = os.environ.get("OPT_N_WORKERS")
    if env_workers:
        cfg["optimization"]["n_workers"] = int(env_workers)

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


def run_batch(tags, workers_per_run=None):
    """
    Launch several opt_<tag>.py runs IN PARALLEL on this machine, then wait for all to finish.
    One command, then walk away. Each run is a separate process with its own worker pool; the
    worker count is auto-sized (cores / runs - 1) so the pools share the machine without
    oversubscribing -- override with the OPT_N_WORKERS env var or the workers_per_run argument.
    """
    import subprocess

    n_cores = os.cpu_count() or 4
    if workers_per_run is None:
        env_w = os.environ.get("OPT_N_WORKERS")
        workers_per_run = int(env_w) if env_w else max(1, n_cores // len(tags) - 1)
    est_gb = len(tags) * (workers_per_run * 1.5 + 1.5)

    print("=" * 70)
    print(f"BATCH: {len(tags)} runs in parallel -> {tags}")
    print(f"cores={n_cores} | workers/run={workers_per_run} | est. RAM ~{est_gb:.0f} GB")
    print("If RAM is tight or it swaps, set  OPT_N_WORKERS=<smaller>  and re-launch.")
    print("=" * 70)

    here = os.path.dirname(os.path.abspath(__file__))
    logs = Path(here) / "logs"
    logs.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["OPT_N_WORKERS"] = str(workers_per_run)

    procs = []
    for tag in tags:
        logp = logs / f"opt_{tag}.log"
        lf = open(logp, "w", encoding="utf-8")
        p = subprocess.Popen([sys.executable, f"opt_{tag}.py"], stdout=lf, stderr=subprocess.STDOUT,
                             env=env, cwd=here)
        procs.append((tag, p, lf))
        print(f"  started opt_{tag}.py (PID {p.pid}) -> logs/opt_{tag}.log")

    print("\nAll launched. Keep this window open until it says BATCH COMPLETE.")
    print("Watch progress with:  tail -f logs/opt_<tag>.log\n")

    failed = []
    for tag, p, lf in procs:
        p.wait()
        lf.close()
        if p.returncode == 0:
            print(f"  [OK]     opt_{tag}.py finished")
        else:
            print(f"  [FAILED] opt_{tag}.py exit {p.returncode} (see logs/opt_{tag}.log)")
            failed.append(tag)

    print("\nBATCH COMPLETE." + (f"  Failed: {failed}" if failed else "  All runs finished cleanly."))
