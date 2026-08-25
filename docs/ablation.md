# Operator ablation

The framework's two departures from a plain genetic algorithm are the ACO pheromone
memory (inherited by offspring as an epigenetic blend) and the gap-gated Lamarckian local
search. This ablation isolates what each contributes by disabling them independently.

The harness is three boolean flags read by `ExperimentConfig`. All three default to `True`,
so nothing about a normal `profile_p1` run changes.

| Arm | `use_crossover` | `use_pheromone_inheritance` | `use_local_search` | What it is |
|---|:---:|:---:|:---:|---|
| `hybrid` | on | on | on | the full system |
| `ga_only` | on | off | off | plain Darwinian GA: crossover plus random mutation |
| `aco_only` | off | on | on | a single lineage improved only by pheromone-guided local search |

Every arm launches from the same seed, so all three start from the same initial population
and see the same selection draws. Any separation in their convergence curves is
attributable to the operators rather than to luck.

## Running it

On the toy city, which takes minutes:

```bash
python -m scripts.run_ablation_toy
```

```bash
python -m scripts.run_ablation_toy --generations 20 --population 12 --num-ticks 300
```

At full Iligan scale, where each arm is a complete 38-route, 2000-vehicle, 30-generation
optimization. Expect a long wall clock per arm and run it on a machine you can leave alone:

```bash
python -m scripts.run_ablation_iligan --tag run1
```

Arms can be split across terminals or machines. Sharing a `--tag` collects them into one
output folder:

```bash
python -m scripts.run_ablation_iligan --tag run1 --arms hybrid
```

If RAM is tight, cap the pool with `OPT_N_WORKERS` or uncomment `n_workers` in
`configs/profile_p1.yaml`. Each worker holds roughly 1 to 2 GB at this problem size.

Arms write to `outputs/ablation_iligan/<tag>/<arm>/opt_<timestamp>/`. Once they finish,
build the comparison figure from whichever arms completed:

```bash
python -m scripts.run_ablation_iligan --tag run1 --plot-only
```

To move results off the machine that ran them, `scripts/analysis/export_ablation.py`
collapses a finished ablation into a single few-kilobyte text file holding the per-arm
cost trajectories and run configuration, without touching the heavy checkpoint pickles:

```bash
python -m scripts.analysis.export_ablation
```

## Results

At full Iligan scale (38 routes, 2000 vehicles, 30 generations):

| Configuration | Start `F_sim` | Final `F_sim` | Reduction |
|---|---:|---:|---:|
| Hybrid | 2,427,616 | **2,350,255** | **3.2%** |
| GA-only | 2,394,836 | 2,355,158 | 1.7% |
| ACO-only | 2,404,936 | 2,361,386 | 1.8% |

![Operator ablation on Iligan](figures/ablation_iligan.png)

The ordering (hybrid < GA-only < ACO-only) is the result the ablation was designed to
test. The descent trajectories are the more informative part:

- **ACO-only stalls from generation 15 onward.** Without recombination, a single lineage
  exhausts the local improvements reachable from wherever it started. This is the clearest
  effect in the experiment and it reproduces at both scales.
- **GA-only descends steadily but modestly**, finishing at 1.7%.
- **The hybrid keeps improving into the final third of the budget**, with a decisive drop
  at generation 26 that carries it past both ablated arms.

On the toy instance (artifacts in `results/ablation_toy/`), GA-only and hybrid finish
within evaluation variance of each other. That is expected rather than contradictory: on a
six-route grid the combinatorial space is small enough that a plain GA nearly saturates
it, leaving the local search little room to add value (Eiben et al., 1999). ACO-only
stalls there too.

## Reading the margins honestly

The absolute gaps between arms are roughly 5,000 to 11,000 on costs near 2.35 million.
The agent-based objective has a per-evaluation variance of about 12%, which is larger than
those gaps.

So the ablation supports the expected ordering and, more strongly, the qualitative claim
that ACO-only stalls while the hybrid is still descending. It does not support treating
"3.2% versus 1.7%" as a precise measured margin. A stronger version of this experiment
would run each arm under several seeds and report distributions, which the compute budget
for the thesis did not allow.
