"""run_optimization.py -- launcher for the production Iligan optimizations (Chapter 4.5).

One invocation is one seeded run of the full 38-route, 2000-vehicle, 30-generation profile.
The reproducibility result in the paper is seven of these under seven different seeds.

  * seeds random / numpy (the optimizer itself does NOT seed, so reproducibility-by-seed lives here),
  * loads configs/profile_p1.yaml and applies the per-run overrides (DDM pickle, output tag),
  * writes a tagged run config and launches Optimizer.create(...).start().

    # one run
    python -m scripts.run_optimization --tag p1 --seed 1

    # a temporal-regime run against a different demand surface
    python -m scripts.run_optimization --tag p8_1pm --seed 8 --ddm data/cache/ddm_1pm.pkl

    # the seven-seed reproducibility set, in parallel on one machine
    python -m scripts.run_optimization --batch p1 p2 p3 p4 p5 p6 p7

Each arm is a full Iligan optimization, so expect hours of wall clock per run. If RAM is
tight, cap the worker pool with OPT_N_WORKERS or `n_workers` in configs/profile_p1.yaml;
each worker holds roughly 1-2 GB at this problem size.

Outputs land under outputs/final_runs/<tag>/opt_<timestamp>/ so scripts/analysis/evaluate_runs.py
can discover and group them by tag.
"""

from __future__ import annotations

import os as _os, sys as _sys
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _REPO_ROOT not in _sys.path:
    _sys.path.insert(0, _REPO_ROOT)

import argparse
import os
import random
import re
import sys
from pathlib import Path


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
        ddm_pkl: optional DDM pickle override (e.g. data/cache/ddm_1pm.pkl) for temporal-regime runs.
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

    from jeepney.optimizer import Optimizer
    opt = Optimizer.create(cfg_path)
    if start:
        opt.start()
    return opt


def run_batch(tags, workers_per_run=None):
    """
    Launch several tagged runs IN PARALLEL on this machine, then wait for all to finish.
    One command, then walk away. Each run is a separate process with its own worker pool; the
    worker count is auto-sized (cores / runs - 1) so the pools share the machine without
    oversubscribing -- override with the OPT_N_WORKERS env var or the workers_per_run argument.

    The seed for each run is taken from the trailing digits of its tag ("p3" -> 3), which is how
    the paper's seven-seed reproducibility set (p1..p7) was produced.
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

    logs = Path("outputs") / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["OPT_N_WORKERS"] = str(workers_per_run)

    procs = []
    for tag in tags:
        logp = logs / f"opt_{tag}.log"
        lf = open(logp, "w", encoding="utf-8")
        cmd = [sys.executable, "-m", "scripts.run_optimization",
               "--tag", tag, "--seed", str(seed_from_tag(tag))]
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=_REPO_ROOT)
        procs.append((tag, p, lf))
        print(f"  started {tag} (PID {p.pid}) -> {logp}")

    print("\nAll launched. Keep this window open until it says BATCH COMPLETE.")
    print(f"Watch progress with:  tail -f {logs}/opt_<tag>.log\n")

    failed = []
    for tag, p, lf in procs:
        p.wait()
        lf.close()
        if p.returncode == 0:
            print(f"  [OK]     {tag} finished")
        else:
            print(f"  [FAILED] {tag} exit {p.returncode} (see {logs}/opt_{tag}.log)")
            failed.append(tag)

    print("\nBATCH COMPLETE." + (f"  Failed: {failed}" if failed else "  All runs finished cleanly."))


def seed_from_tag(tag: str) -> int:
    """Trailing digits of a tag become its seed: "p3" -> 3, "p8_1pm" -> 8, "run" -> 0."""
    m = re.match(r"[^0-9]*(\d+)", tag)
    return int(m.group(1)) if m else 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run one (or a parallel batch of) production Iligan optimizations.")
    ap.add_argument("--tag", help='run label and output sub-folder, e.g. "p1" or "p8_1pm"')
    ap.add_argument("--seed", type=int,
                    help="RNG seed for the GA; defaults to the trailing digits of --tag")
    ap.add_argument("--ddm", metavar="PKL",
                    help="DDM pickle override for a temporal regime, "
                         "e.g. data/cache/ddm_1pm.pkl (default: whatever profile_p1.yaml names)")
    ap.add_argument("--batch", nargs="+", metavar="TAG",
                    help="launch these tags in parallel instead of a single run")
    ap.add_argument("--workers", type=int,
                    help="worker processes per run (default: auto-sized from core count)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the optimizer and exit without starting the search")
    args = ap.parse_args(argv)

    if args.batch:
        run_batch(args.batch, workers_per_run=args.workers)
        return
    if not args.tag:
        ap.error("one of --tag or --batch is required")

    seed = args.seed if args.seed is not None else seed_from_tag(args.tag)
    run_profile(args.tag, seed, ddm_pkl=args.ddm, start=not args.dry_run)


if __name__ == "__main__":
    main()
