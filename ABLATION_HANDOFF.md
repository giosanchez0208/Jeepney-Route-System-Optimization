# Ablation handoff (GA-only vs ACO-only vs hybrid)

This is the panel's ask #5: show that GA alone and ACO alone each underperform the combined
hybrid. The harness is three config flags (`use_crossover`, `use_pheromone_inheritance`,
`use_local_search`) read by `ExperimentConfig`. Defaults are all `True`, so nothing about the
normal `profile_p1` runs changes.

## The three arms

| Arm | crossover | pheromone inheritance | Lamarckian local search | Meaning |
|-----|-----------|-----------------------|--------------------------|---------|
| `hybrid` | on | on | on | the full system |
| `ga_only` | on | off | off | plain Darwinian GA (crossover + random mutation) |
| `aco_only` | off | on | on | single lineage improved only by pheromone-guided local search |

All arms launch from the same seed, so they start from the same initial population and the
only difference is the operators.

## What to run (on the machine with the good specs)

From the repo root, with the venv active:

```
# all three sequentially, overnight:
python run_ablation_iligan.py --tag run1

# OR split one arm per terminal / machine (same --tag so they collect together):
python run_ablation_iligan.py --tag run1 --arms hybrid
python run_ablation_iligan.py --tag run1 --arms ga_only
python run_ablation_iligan.py --tag run1 --arms aco_only
```

Each arm is a full Iligan optimization (38 routes, 2000 jeeps, 540 ticks, 30 generations), so
expect a long wall-clock time per arm. They write to
`outputs/ablation_iligan/run1/<arm>/opt_<timestamp>/`.

## When the arms finish

```
python run_ablation_iligan.py --tag run1 --plot-only
```

This writes `outputs/ablation_iligan/run1/ablation_convergence_iligan.png` from whatever arms
have completed. Send me that PNG plus the three `history.csv` files and I will write up the
results section.

## Notes

- If RAM is tight, uncomment `n_workers` in `configs/profile_p1.yaml` or set the env var
  `OPT_N_WORKERS=<small number>` before launching.
- A quick toy-city version of the same ablation is already running here for the demo figure;
  the Iligan numbers from your machine are the ones that go in the paper.
