"""Generate results_and_discussion_5_fixed.ipynb"""
import json, sys, os
import uuid

def md(source_lines):
    if isinstance(source_lines, str):
        source_lines = [line + "\n" for line in source_lines.split("\n")]
    return {"cell_type": "markdown", "id": uuid.uuid4().hex[:12], "metadata": {}, "source": source_lines}

def code(source_lines):
    if isinstance(source_lines, str):
        source_lines = [line + "\n" for line in source_lines.split("\n")]
    return {"cell_type": "code", "execution_count": None, "id": uuid.uuid4().hex[:12], "metadata": {}, "outputs": [], "source": source_lines}

cells = []

# =========================================================
# TITLE
# =========================================================
cells.append(md([
    "# Phase E Validation: Temporal Resolution and Discretization Limits",
    "This notebook runs empirical sweeps to bound the parameters of the microscopic simulation:",
    "1. **`seconds_per_tick`**: How coarse can we make the temporal discretization before vehicle and passenger movement dynamics break down?",
    "2. **`num_ticks`**: How short can a simulation run be while still producing stable, converged evaluation fitness signals?",
    "",
    "By establishing the boundary points where stochastic evaluation error (CV) spikes, we tune the simulation for maximal iteration speed during optimization."
]))

# =========================================================
# CELL 1: SETUP
# =========================================================
cells.append(code([
    "import os",
    "import sys",
    "import random",
    "import time",
    "import yaml",
    "import gc",
    "import numpy as np",
    "import pandas as pd",
    "import matplotlib.pyplot as plt",
    "import seaborn as sns",
    "",
    "# Academic Reproducibility",
    "random.seed(42)",
    "np.random.seed(42)",
    "",
    "sns.set_theme(style=\"whitegrid\")",
    "plt.rcParams['font.family'] = 'sans-serif'",
    "",
    "from utils_simplified import (",
    "    reuse_citygraph, reuse_ddm, generate_route_system,",
    "    generate_dummy_yaml, build_travelgraph, run_simulation",
    ")",
    "from utils.jeep import Jeep",
    "from utils.jeep_system import JeepSystem",
    "",
    "cg = reuse_citygraph(\"results_and_discussion/pkl/profile_p1.pkl\")",
    "ddm = reuse_ddm(\"results_and_discussion/pkl/ddm_8am.pkl\")",
    "os.makedirs(\"configs\", exist_ok=True)"
]))

# =========================================================
# CELL 2: TOPOLOGY GENERATION
# =========================================================
cells.append(md([
    "## 1. Topographic Initialization",
    "We test across varying system complexities (3 routes vs 5 routes) to ensure our parameter boundaries hold across different densities. We set up an environment expected to reach steady-state (120 spawns/hr, 25 jeeps)."
]))

cells.append(code([
    "NUM_JEEPS = 25",
    "SPAWN_RATE = 120.0",
    "ROUTE_COUNTS = [3, 5]",
    "",
    "print(\"[SETUP] Generating route systems...\")",
    "route_systems = {}",
    "for n_routes in ROUTE_COUNTS:",
    "    random.seed(42 + n_routes)",
    "    np.random.seed(42 + n_routes)",
    "    route_systems[n_routes] = generate_route_system(n_routes, cg, ddm)",
    "    total_edges = sum(len(r.path) for r in route_systems[n_routes])",
    "    print(f\"  Generated {n_routes} routes ({total_edges} total edges)\")",
    "",
    "def make_jeep_system(routes, spt):",
    "    \"\"\"Factory to build JeepSystems dynamically tailored to seconds_per_tick.\"\"\"",
    "    jeeps = []",
    "    per_route = max(1, NUM_JEEPS // len(routes))",
    "    for r in routes:",
    "        for _ in range(per_route):",
    "            start = (r.path[0].start.lon, r.path[0].start.lat)",
    "            jeeps.append(Jeep(r, curr_pos=start, speed=20.0, max_capacity=16, seconds_per_tick=spt))",
    "    return JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=50.0, equidistant_spawn=True)",
    "",
    "def run_one(routes, spt, num_ticks, rep_seed):",
    "    \"\"\"Run a single microscopic simulation payload.\"\"\"",
    "    yaml_path = f\"configs/_nb5_tmp_{spt}_{num_ticks}_{rep_seed}.yaml\"",
    "    generate_dummy_yaml(",
    "        yaml_path,",
    "        **{",
    "            \"simulation.num_ticks\": num_ticks,",
    "            \"simulation.seconds_per_tick\": spt,",
    "            \"simulation.total_allocatable_jeeps\": NUM_JEEPS,",
    "            \"simulation.spawn_rate_per_hour\": SPAWN_RATE,",
    "            \"simulation.mohring_sample_size\": 2, # Lightweight for evaluation loops",
    "        }",
    "    )",
    "    random.seed(rep_seed)",
    "    np.random.seed(rep_seed)",
    "    ",
    "    js = make_jeep_system(routes, spt)",
    "    tg = build_travelgraph(cg, yaml_path, routes)",
    "    sim = run_simulation(tg, yaml_path, js, ddm, delete_yaml_when_done=True)",
    "    res = sim.evaluate_fitness()",
    "    return res.fitness_score, res.metrics"
]))

# =========================================================
# CELL 3: EXPERIMENT 1
# =========================================================
cells.append(md([
    "## 2. Sensitivity Analysis: Temporal Discretization (`seconds_per_tick`)",
    "We sweep `seconds_per_tick` from 5 to 30 while modifying `num_ticks` correspondingly to guarantee **the exact same simulated duration** (1800 simulated seconds = 30 simulated minutes). We test for the point where the simulation's discretization error spikes."
]))

cells.append(code([
    "TOTAL_SIM_SECONDS = 1800  # Fixed 30 min duration",
    "SPT_VALUES = [5, 10, 20, 30]",
    "N_REPS_EXP1 = 5",
    "",
    "spt_rows = []",
    "for n_routes in ROUTE_COUNTS:",
    "    routes = route_systems[n_routes]",
    "    for spt in SPT_VALUES:",
    "        num_ticks = max(10, TOTAL_SIM_SECONDS // spt)",
    "        print(f\"\\n--- Testing R={n_routes} | spt={spt:2d} | ticks={num_ticks:3d} ---\")",
    "        ",
    "        for rep in range(N_REPS_EXP1):",
    "            rep_seed = 1000 + n_routes * 100 + spt * 10 + rep",
    "            t0 = time.time()",
    "            ",
    "            fitness, metrics = run_one(routes, spt, num_ticks, rep_seed)",
    "            wall = time.time() - t0",
    "            ",
    "            spt_rows.append({",
    "                \"n_routes\": n_routes, \"spt\": spt, \"num_ticks\": num_ticks,",
    "                \"rep\": rep, \"fitness\": fitness,",
    "                \"completed\": metrics.get(\"completed_count\", 0),",
    "                \"incomplete\": metrics.get(\"incomplete_count\", 0),",
    "                \"mean_commute\": metrics.get(\"mean_commute_time\", 0),",
    "                \"wall_s\": wall",
    "            })",
    "            print(f\"  rep {rep} | fit={fitness:10.2f} | wall={wall:4.1f}s | completed={spt_rows[-1]['completed']}\")",
    "            gc.collect()"
]))

# =========================================================
# CELL 4: EXP 1 PLOT
# =========================================================
cells.append(code([
    "df_spt = pd.DataFrame(spt_rows)",
    "agg_spt = df_spt.groupby([\"n_routes\", \"spt\"]).agg(",
    "    mean_fit=(\"fitness\", \"mean\"),",
    "    std_fit=(\"fitness\", \"std\"),",
    "    mean_wall=(\"wall_s\", \"mean\")",
    ").reset_index()",
    "agg_spt[\"cv_fit\"] = agg_spt[\"std_fit\"] / agg_spt[\"mean_fit\"]",
    "",
    "fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))",
    "",
    "# 1. Fitness CV (Consistency)",
    "sns.lineplot(data=agg_spt, x=\"spt\", y=\"cv_fit\", hue=\"n_routes\", marker=\"o\", linewidth=2.5, ax=ax1, palette=\"Set1\")",
    "ax1.set_title(\"Fitness Consistency across Discretization Step\", fontsize=13, fontweight=\"bold\")",
    "ax1.set_xlabel(\"Seconds per Tick (spt)\", fontsize=11)",
    "ax1.set_ylabel(\"Coefficient of Variation (CV)\", fontsize=11)",
    "ax1.axvline(10, color='red', linestyle='--', alpha=0.5, label=\"Optimal Anchor (10s)\")",
    "ax1.legend()",
    "",
    "# 2. Wall Time (Performance)",
    "sns.lineplot(data=agg_spt, x=\"spt\", y=\"mean_wall\", hue=\"n_routes\", marker=\"s\", linewidth=2.5, ax=ax2, palette=\"Set2\")",
    "ax2.set_title(\"Execution Wall-Time scaling\", fontsize=13, fontweight=\"bold\")",
    "ax2.set_xlabel(\"Seconds per Tick (spt)\", fontsize=11)",
    "ax2.set_ylabel(\"Average Runtime (s)\", fontsize=11)",
    "ax2.invert_xaxis() # Lower SPT = more computation",
    "",
    "plt.suptitle(\"Visual 1: Temporal Discretization Limits\", fontsize=15, fontweight='bold', y=1.05)",
    "plt.tight_layout()",
    "plt.show()"
]))

# =========================================================
# CELL 5: EXPERIMENT 2
# =========================================================
cells.append(md([
    "## 3. Sensitivity Analysis: Simulation Duration Bounds (`num_ticks`)",
    "With `seconds_per_tick` anchored at 10s (based on Exp 1 findings), we now sweep the number of ticks from 60 (10 min) up to 270 (45 min) to find the minimum horizon necessary for steady-state variance collapse."
]))

cells.append(code([
    "SPT_FIXED = 10",
    "TICK_VALUES = [60, 120, 180, 270]",
    "N_REPS_EXP2 = 5",
    "",
    "tick_rows = []",
    "for n_routes in ROUTE_COUNTS:",
    "    routes = route_systems[n_routes]",
    "    for n_ticks in TICK_VALUES:",
    "        sim_min = (n_ticks * SPT_FIXED) / 60.0",
    "        print(f\"\\n--- Testing R={n_routes} | ticks={n_ticks:3d} ({sim_min:.0f}m) ---\")",
    "        ",
    "        for rep in range(N_REPS_EXP2):",
    "            rep_seed = 2000 + n_routes * 100 + n_ticks + rep",
    "            t0 = time.time()",
    "            ",
    "            fitness, metrics = run_one(routes, SPT_FIXED, n_ticks, rep_seed)",
    "            wall = time.time() - t0",
    "            ",
    "            tick_rows.append({",
    "                \"n_routes\": n_routes, \"num_ticks\": n_ticks, \"sim_min\": sim_min,",
    "                \"rep\": rep, \"fitness\": fitness,",
    "                \"completed\": metrics.get(\"completed_count\", 0),",
    "                \"incomplete\": metrics.get(\"incomplete_count\", 0),",
    "                \"wall_s\": wall",
    "            })",
    "            print(f\"  rep {rep} | fit={fitness:10.2f} | wall={wall:4.1f}s | completed={tick_rows[-1]['completed']}\")",
    "            gc.collect()"
]))

# =========================================================
# CELL 6: EXP 2 PLOT
# =========================================================
cells.append(code([
    "df_ticks = pd.DataFrame(tick_rows)",
    "agg_ticks = df_ticks.groupby([\"n_routes\", \"sim_min\"]).agg(",
    "    mean_fit=(\"fitness\", \"mean\"),",
    "    std_fit=(\"fitness\", \"std\"),",
    "    mean_wall=(\"wall_s\", \"mean\")",
    ").reset_index()",
    "agg_ticks[\"cv_fit\"] = agg_ticks[\"std_fit\"] / agg_ticks[\"mean_fit\"]",
    "",
    "fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))",
    "",
    "# 1. Fitness CV vs Simulated Duration",
    "sns.lineplot(data=agg_ticks, x=\"sim_min\", y=\"cv_fit\", hue=\"n_routes\", marker=\"o\", linewidth=2.5, ax=ax1, palette=\"Set1\")",
    "ax1.set_title(\"Variance Collapse Over Simulated Duration\", fontsize=13, fontweight=\"bold\")",
    "ax1.set_xlabel(\"Simulated Time Horizon (minutes)\", fontsize=11)",
    "ax1.set_ylabel(\"Coefficient of Variation (CV)\", fontsize=11)",
    "ax1.axvline(30, color='red', linestyle='--', alpha=0.5, label=\"Stability Threshold (30m)\")",
    "ax1.legend()",
    "",
    "# 2. Fitness vs Wall Time scatter",
    "sns.scatterplot(data=df_ticks, x=\"wall_s\", y=\"fitness\", hue=\"n_routes\", style=\"sim_min\", s=100, ax=ax2, palette=\"Set2\")",
    "ax2.set_title(\"Fitness Distribution vs Execution Effort\", fontsize=13, fontweight=\"bold\")",
    "ax2.set_xlabel(\"Wall Execution Time (s)\", fontsize=11)",
    "ax2.set_ylabel(\"Evaluation Fitness Score\", fontsize=11)",
    "ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')",
    "",
    "plt.suptitle(\"Visual 2: Simulation Duration Consistency\", fontsize=15, fontweight='bold', y=1.05)",
    "plt.tight_layout()",
    "plt.show()"
]))

# Build the notebook
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": ".venv",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.11.3"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

out_path = "results_and_discussion_5_fixed.ipynb"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"[DONE] Generated {out_path} with {len(cells)} cells.")
