"""export_ablation.py -- pull everything we need from a finished Iligan ablation into ONE small text file.

Run this on the machine where the ablation outputs live. It reads the run folders (no heavy pickles,
stdlib only) and writes a compact text file containing, per arm (hybrid / ga_only / aco_only):
  - start and final F_sim, the reduction %, and the generation count
  - the full per-generation best-cost trajectory (so the convergence figure can be regenerated)
  - the run configuration (g_max, population, routes, fleet, ticks, seed)

Then just send back that one text file (a few KB). Nothing else needs to be pushed.

    python export_ablation.py                  # auto-scans outputs/ablation_iligan/
    python export_ablation.py --root outputs/ablation_iligan --out ablation_export.txt
"""
import argparse
import csv
import glob
import os
from datetime import datetime

ARMS = ["hybrid", "ga_only", "aco_only"]
CFG_KEYS = ["g_max", "n_population", "num_routes", "total_allocatable_jeeps", "num_ticks", "seed",
            "jeep_speed_kmh", "use_crossover", "use_pheromone_inheritance", "use_local_search"]


def find_runs(root):
    """Map arm -> most recently modified opt_* run dir with a history.csv, matching the arm in the path."""
    found = {}  # arm -> (run_dir, mtime)
    for hist in glob.glob(os.path.join(root, "**", "history.csv"), recursive=True):
        run_dir = os.path.dirname(hist)
        low = run_dir.replace("\\", "/").lower()
        for arm in ARMS:
            if f"/{arm}/" in low or low.endswith(f"/{arm}"):
                m = os.path.getmtime(hist)
                if arm not in found or m > found[arm][1]:
                    found[arm] = (run_dir, m)
    return {arm: rd for arm, (rd, _m) in found.items()}


def read_history(run_dir):
    gens, best = [], []
    with open(os.path.join(run_dir, "history.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                gens.append(int(row["Generation"]))
                best.append(float(row["Global_Best_Cost"]))
            except (KeyError, ValueError):
                continue
    return gens, best


def read_cfg(run_dir):
    """Lightweight text scan of configs.yaml (no yaml dependency)."""
    cfg = {}
    for name in ("configs.yaml", "_run_config.yaml"):
        p = os.path.join(run_dir, name)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            s = line.strip()
            for k in CFG_KEYS:
                if s.startswith(k + ":"):
                    cfg.setdefault(k, s.split(":", 1)[1].strip())
        break
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/ablation_iligan",
                    help="folder to scan for the ablation runs")
    ap.add_argument("--out", default="ablation_export.txt")
    args = ap.parse_args()

    runs = find_runs(args.root)
    if not runs:
        # Fall back: scan everything under outputs/ in case the folder name differs.
        runs = find_runs("outputs")
    if not runs:
        raise SystemExit(f"No history.csv found under '{args.root}' or outputs/. "
                         f"Point --root at the ablation output folder.")

    lines = []
    w = lines.append
    w("=== ILIGAN ABLATION EXPORT ===")
    w(f"generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    w(f"arms found: {', '.join(a for a in ARMS if a in runs)}")
    w("")

    # config (report from whichever arm we have)
    any_arm = next(iter(runs.values()))
    cfg = read_cfg(any_arm)
    w("--- run configuration ---")
    for k in CFG_KEYS:
        if k in cfg:
            w(f"{k}: {cfg[k]}")
    w("")

    # summary table
    w("--- summary (lower final F_sim is better) ---")
    w(f"{'arm':10s} {'start_F':>14s} {'final_F':>14s} {'reduction%':>11s} {'gens':>5s}")
    summary = {}
    for arm in ARMS:
        if arm not in runs:
            w(f"{arm:10s}   (not found)")
            continue
        gens, best = read_history(runs[arm])
        if not best:
            w(f"{arm:10s}   (empty history)")
            continue
        start, final = best[0], best[-1]
        red = 100.0 * (start - final) / start if start else 0.0
        summary[arm] = (start, final, red, gens, best)
        w(f"{arm:10s} {start:14.0f} {final:14.0f} {red:10.1f}% {gens[-1]:5d}")
    w("")

    if summary:
        order = sorted(summary, key=lambda a: summary[a][1])
        w(f"best (lowest final F_sim): {order[0]}")
        w("ordering (final F_sim, ascending = best first): " + " < ".join(order))
        w("")

    # full trajectories for replotting the convergence figure
    w("--- per-generation trajectories (gen,best_cost) ---")
    for arm in ARMS:
        if arm in summary:
            gens, _, _, gl, best = summary[arm]
            w(f"[{arm}]")
            for g, b in zip(gl, best):
                w(f"{g},{b:.4f}")
    w("=== END ===")

    text = "\n".join(lines)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print(f"\n[export] wrote {args.out}  ->  send this one file back (a few KB).")


if __name__ == "__main__":
    main()
