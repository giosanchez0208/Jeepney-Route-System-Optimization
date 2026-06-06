# HANDOFF — context for the next session

You are the thesis research partner (TRNDP expert) for a jeepney route-network optimization
project (Iligan City). This file is a point-in-time snapshot so you can pick up where the previous
session left off. Read this first, then `PROJECT_GUIDE.md` (deep), `UTILS_GUIDE.md` (quick), and
`research_methodology.tex` (Chapter 3) as needed. Also read the user's memory files at
`~/.claude/projects/<this-project>/memory/MEMORY.md`.

The user is mid-thesis, time-pressured, and values: blunt honesty, catching "looks-fine-but-isn't"
bugs, and not running long things. **Do NOT run tests > ~2 min** (verify by inspection instead);
≤10 s static checks (py_compile, imports, tiny smokes) are fine and encouraged.

---

## TL;DR — current state

- **Chapter 4 scaffold** exists (`results_and_discussion.tex`). §4.1, §4.2 are written by the user
  (real numbers + figures). §4.3.3 is done. The rest are placeholders awaiting run results.
- **The final optimization runs have NOT happened yet.** The user is about to launch them on 3
  machines (~8 h each, 3 runs per machine, all 9 at once). When they report back, your job is to
  **fill Chapter 4 §4.3.1, §4.3.4, §4.3.6, §4.4, §4.5 with the real numbers + figures.**
- A lot of code was fixed this session (see "Key changes"). Config is set for the final runs.
- **Git: many uncommitted changes; the user manages git manually** (pulling friends' work, pushing).
  A branch `chapter4-scaffold-and-walkwt-fix` exists but a push was auth-blocked earlier; don't
  assume anything is committed. Commit/push only when asked.

---

## The run pipeline (what the user is executing)

| Step | Command | Produces | Where |
|---|---|---|---|
| 1. Final optimizations (~8 h) | `python run_machine_1.py` / `_2` / `_3` | telemetry + snapshots | `outputs/final_runs/<tag>/opt_<ts>/` |
| 2. Lamarckian demo (~10 min) | run `nb_4_3_6_lamarckian.ipynb` | §4.3.6 figures | `results_and_discussion/images/` |
| 3. Aggregate (after step 1) | `python opt_eval.py` | §4.4/§4.5 figures + stats | `results_and_discussion/images/` |
| 4. Gather figures | `python collect_figures.py` | all PNGs → one folder | `chap4/figures/` |

- `run_machine_1.py` → p1,p2,p3 ; `_2` → p4,p5,p6 ; `_3` → p7,p8_1pm,p9_5pm. Each launcher runs its
  3 profiles in parallel, auto-caps workers (`cores//3 - 1`, override `OPT_N_WORKERS`), logs to
  `logs/opt_<tag>.log`, waits. Press-play-and-leave. Needs ~24–32 GB RAM per machine.
- **Profiles:** p1–p7 = identical `profile_p1.yaml`, seeds 1–7 (reproducibility, §4.5.2). p8_1pm /
  p9_5pm = swap `ddm_pkl` to 1pm/5pm (temporal robustness, §4.5.3). `opt_run.py:run_profile` does the
  seeding (the optimizer itself does NOT seed) + config overrides; `run_batch` does the parallel launch.

---

## Key changes made this session (all in the repo)

**Config — `configs/profile_p1.yaml` (FINAL-RUN values):**
- `num_routes: 38`, `total_allocatable_jeeps: 2000`, `mohring_sample_size: 2000`
- `num_ticks: 540`, `seconds_per_tick: 10`, `spawn_rate_per_hour: 600`, `weight_tolerance: 14.4`
- `walk_wt: 0.0563` (was a 10× typo `0.563` — **fixed across all configs**; it poisoned every sim)
- Added top-level `cg_pkl: rnd/pkl/profile_p1.pkl`, `ddm_pkl: rnd/pkl/ddm_8am.pkl`
- Removed the dead `surrogate:` block; added commented `n_workers` knob.

**Surrogate REMOVED → gap-gated local search (Path B).** The static surrogate was mis-scaled
(route-length term dominated), not actually O(1) (rebuilt the 36k-node TravelGraph per call), and
had config/code disconnects. `StaticSurrogateEvaluator` was deleted from `utils/simulation.py`.
`genetic.py:apply_lamarckian_mutation` now gates mutation acceptance on the **Proportional
Demand-Service Disparity** `D(R) = Σ|P_ij − S_ij|` (the `_total_disparity` helper) — the same
pheromone signal that steers the operators. Full `F_sim` remains the exclusive GA objective.
§4.3.5 (surrogate fidelity) was removed from Chapter 4; methodology subsection rewritten to
"Gap-Gated Lamarckian Acceptance".

**Double-step bug fixed.** Passengers were stepped twice per tick (both `PassengerGenerator.update`
and `JeepSystem.update` called `p.update()`), making walking legs 2× too fast. `PassengerGenerator`
no longer steps; `JeepSystem` is the sole stepping authority.

**Spawn model = continuous arrivals + fixed horizon (abrupt stop).** Considered one-shot+drain,
then reverted — real sims stop at a tick cutoff, and the underservice penalty (Term 2 of `F_sim`)
scores in-flight passengers. So completion fraction is a *diagnostic, not a target* (it can't reach
100% under continuous spawn). `num_ticks` is chosen by fitness-CV stability, not completion plateau.

**Optimizer memory / speed (critical for the 8 h runs) — `utils/optimizer.py`,
`utils/simulation_parallel.py`:** the optimizer was respawning the worker pool *every generation*
(one-shot) AND workers rebuilt the CityGraph from the PBF each spawn. Fixed: `open_pool()` in
`start()` + `close_pool()` in `finally` (persistent pool); workers load from `cg_pkl`/`ddm_pkl`;
`gc.collect()` per generation and per worker-sim (2000-jeep objects are reference cycles);
`max_workers` now configurable via `optimization.n_workers` or `OPT_N_WORKERS` env.

**Calibration runtime fix (`utils_simplified.py` + `simulation_parallel.py`):** added
`run_parallel_overrides` / `run_reps_overrides` + `_worker_run_override` so sweep notebooks reuse a
persistent pool and vary `num_ticks`/`spawn_rate`/`seconds_per_tick` per call instead of respawning.
`rnd_1_ticks_and_rate.ipynb` was rewritten to use it (§4.3.3 — done, gave `num_ticks=540`,
`spawn_rate=600`).

**Methodology (`research_methodology.tex`, Chapter 3) updated:** surrogate→gap-gated subsection;
new "Opportunistic Boarding under Weight Tolerance" subsection (`c_alt ≤ c_plan + δ_tol`;
`T_exp = d_walk/v_walk + d_ride/v_ride`; `ΔT = T_act − T_exp`; Group A/B Mann–Whitney). Kept existing
citations, added none. **Do NOT touch `documentation/methodology_apa.md`** (user said so; it's stale
and describes the old surrogate-as-primary design).

---

## Chapter 4 status (results_and_discussion.tex)

| Section | Status |
|---|---|
| 4.1 Environment / DDM | **Done** by user (numbers + figs in `rnd/documentation/`) |
| 4.2 Architecture (travel graph, journey) | figures done; `\includegraphics` not wired yet |
| 4.3.1 Mohring stability | friend ran it (`mohring_stability_calibration.py`, 38 routes / fleet 2000). **Result: max allocation CV ~0.6, mean CV ~0.11.** Prose PENDING — frame honestly: *mean* CV is the systemic-stability headline; the *max* (one thinly-served route bouncing between small integers) sits above the 0.5 target but is operationally trivial. Data in `outputs/mohring_stability/`. |
| 4.3.2 Δt | dropped (stochastic-averaging argument; no figure) |
| 4.3.3 Horizon + volume | **Done** (CV-hump/variance-collapse framing; fig `horizon_volume_calibration.png`) |
| 4.3.4 Weight tolerance / opportunistic riding | friend ran `rnd_weight_tolerance.ipynb`; result good ("rational transfers significantly reduce actual travel time"). Methodology added. Prose PENDING (use the Mann–Whitney results + box plots `weight_tolerance_t{0,14,100}.png`). |
| 4.3.5 Surrogate fidelity | **Removed** (surrogate dropped) |
| 4.3.6 Lamarckian operators | `nb_4_3_6_lamarckian.ipynb` built (toy + Iligan; isolates the changed route + red=removed/green=added segment). Needs running. Prose PENDING. |
| 4.4 Evolution / 4.5 Optimized network | PENDING the opt runs + `opt_eval.py` |

**Figure naming:** use the `collect_figures.py` dest names when wiring `\includegraphics{chap4/figures/...}`
(e.g. `lamarckian_operators_toy.png`, `robustness_reproducibility.png`, `baseline_vs_optimized.png`,
`equity_traveltime_hist.png`, `mohring_stability.png`, `weight_tolerance_t14.png`).

---

## Files created this session (repo root unless noted)

- `results_and_discussion.tex` — Chapter 4 scaffold
- `opt_run.py` — shared runner (`run_profile`, `run_batch`)
- `opt_p1.py … opt_p9_5pm.py` — 9 thin per-profile wrappers
- `run_machine_1.py / _2 / _3` — press-play parallel launchers (3 runs each)
- `opt_eval.py` — §4.4/§4.5 aggregator (Part 1 no-sim: convergence + robustness matrices via
  Jaccard/Wasserstein; Part 2 re-sims final networks for baseline/equity/entropy. **GED is guarded**
  — caps at 15 nodes, won't scale to 38 routes.)
- `nb_4_3_6_lamarckian.ipynb` — §4.3.6 (generated by `scratch/_gen_lam.py`)
- `collect_figures.py` — gathers Chapter-4 PNGs → `chap4/figures/` (idempotent; 14 staged, 8 pending)
- `rnd_1_tiny_test.py` — tiny smoke companion for the ticks/rate notebook (continuous+fixed model)
- `scratch/_gen_*.py` — throwaway notebook generators (kept for regeneration)

---

## Gotchas / conventions

- **Persistent pool everywhere.** Never use one-shot `run_simulations_parallel` for repeated evals —
  it reloads workers + rebuilds the TravelGraph each call. See memory `rnd-runtime-overhead-fix`.
- **Use `utils_simplified` + the pkls** (`rnd/pkl/profile_p1.pkl`, `ddm_8am/1pm/5pm.pkl`). Never let
  `SimulationSetup.build()` run for sweeps — it rebuilds CityGraph+DDM from the PBF every call.
- **Operators fire conditionally:** pruning/repulsion ~always; **attraction only when a positive
  demand-service gap exists (~1/6 systems)**. Repulsion needs *oversupply*, so it won't fire on a
  sparse demo fleet on Iligan (legitimate, not a bug).
- **Publishing-ready figures via the project's native PIL draw methods** (`city.draw`, `route.draw`,
  `edge.draw`, `visualization.draw_all`) wrapped in matplotlib for panels/labels.
- Tiny-test-companion convention is relaxed for this trusted phase (a thorough written report
  substitutes); see memory `tiny-test-companion`.

---

## Next actions (when results land)

1. Run `collect_figures.py` again to pull the 8 pending figures into `chap4/figures/`.
2. Write **§4.3.1** (Mohring, mean/max CV framing), **§4.3.4** (opportunistic riding, Mann–Whitney +
   box plots), **§4.3.6** (Lamarckian), **§4.4** (convergence, hub, pheromone, phenotypic),
   **§4.5** (baseline, cross-run robustness, equity, entropy) — real numbers, wire the figures.
3. Keep methodology (`research_methodology.tex`) and Chapter 4 consistent (full `F_sim` objective +
   gap-gated acceptance; no surrogate).
