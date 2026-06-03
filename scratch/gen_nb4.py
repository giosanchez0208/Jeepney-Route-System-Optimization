"""Generate results_and_discussion_4_fixed.ipynb from the tested & fixed code."""
import json, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Read the original notebook to extract markdown cells
with open("results_and_discussion_4.ipynb", "r", encoding="utf-8") as f:
    orig = json.load(f)

# Extract markdown sources from the original
md_cells = [c for c in orig["cells"] if c["cell_type"] == "markdown"]

def md(source_lines):
    return {"cell_type": "markdown", "id": None, "metadata": {}, "source": source_lines}

def code(source_lines):
    return {"cell_type": "code", "execution_count": None, "id": None, "metadata": {}, "outputs": [], "source": source_lines}

cells = []

# Cell 0: Title markdown (from original)
cells.append(md(md_cells[0]["source"]))

# Cell 1: Imports
cells.append(code([
    "import os\n",
    "import random\n",
    "import yaml\n",
    "import time\n",
    "import numpy as np\n",
    "import pandas as pd\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "import warnings\n",
    "from tqdm.notebook import tqdm\n",
    "\n",
    "# Set seeds for academic reproducibility\n",
    "random.seed(42)\n",
    "np.random.seed(42)\n",
    "\n",
    "sns.set_theme(style=\"whitegrid\")\n",
    "plt.rcParams['font.family'] = 'sans-serif'\n",
    "plt.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']\n",
    "\n",
    "from utils_simplified import (\n",
    "    reuse_citygraph, reuse_ddm, generate_route_system, SimEnvironment, generate_dummy_yaml, run_simulations_parallel,\n",
    "    build_pheromone_matrix, blend_pheromone_matrix, mutate_attraction, mutate_repulsion, mutate_pruning, crossover_routes,\n",
    "    build_optimizer, process_telemetry, load_generation_snapshot\n",
    ")\n",
    "from utils.route import Route\n",
    "from utils.jeep import Jeep\n",
    "from utils.jeep_system import JeepSystem\n",
    "from utils.genetic import Chromosome\n",
    "from utils.evaluation_metrics import jaccard_similarity, graph_edit_distance, wasserstein_2d"
]))

# Cell 2: Setup markdown (from original)
cells.append(md(md_cells[1]["source"]))

# Cell 3: Setup code with production-reasonable params
cells.append(code([
    "cg = reuse_citygraph(\"results_and_discussion/pkl/profile_p1.pkl\")\n",
    "ddm = reuse_ddm(\"results_and_discussion/pkl/ddm_8am.pkl\")\n",
    "\n",
    "os.makedirs(\"configs\", exist_ok=True)\n",
    "opt_yaml = \"configs/opt_nb4.yaml\"\n",
    "generate_dummy_yaml(\n",
    "    opt_yaml,\n",
    "    **{\n",
    "        \"simulation.num_ticks\": 300,\n",
    "        \"simulation.total_allocatable_jeeps\": 40,\n",
    "        \"simulation.spawn_rate_per_hour\": 120.0,\n",
    "        \"optimization.n_population\": 8,\n",
    "        \"optimization.n_elite\": 1,\n",
    "        \"optimization.g_max\": 15,\n",
    "        \"optimization.k_tournament\": 3,\n",
    "        \"optimization.telemetry_interval\": 1,\n",
    "        \"optimization.checkpoint_interval\": 1,\n",
    "        \"optimization.output_root\": \"outputs/opt_nb4\",\n",
    "        \"cg_pkl\": \"results_and_discussion/pkl/profile_p1.pkl\",\n",
    "        \"ddm_pkl\": \"results_and_discussion/pkl/ddm_8am.pkl\"\n",
    "    }\n",
    ")\n",
    "\n",
    "optimizer = build_optimizer(opt_yaml)\n",
    "optimizer.runner = None\n",
    "optimizer.engine.runner = None\n",
    "print(f\"Run directory: {optimizer.run_dir}\")\n",
    "print(f\"Config: pop={optimizer.config.n_population}, g_max={optimizer.config.g_max}, ticks={optimizer.config.max_ticks}, jeeps={optimizer.config.total_allocatable_jeeps}\")"
]))

# Cell 4: Pipeline markdown (from original)
cells.append(md(md_cells[2]["source"]))

# Cell 5: Pipeline code with verbose progress reporting
cells.append(code([
    "import time as _time\n",
    "all_populations = {}\n",
    "mutation_history = []\n",
    "_pipeline_start = _time.time()\n",
    "\n",
    "print(\"[GEN 0] Initializing population...\")\n",
    "_t0 = _time.time()\n",
    "optimizer.state = optimizer.engine.initialize_state()\n",
    "optimizer.telemetry.log_lineage(optimizer.state.population)\n",
    "print(f\"[GEN 0] Done in {_time.time()-_t0:.1f}s. Best={optimizer.state.best_fitness:.2f}\")\n",
    "\n",
    "# Deep copy population, preserving original UIDs for lineage tracking\n",
    "all_populations[0] = [Chromosome(\n",
    "    routes=[Route(path=r.path[:], city_graph=cg, id=r.id) for r in c.routes],\n",
    "    allocation=c.allocation.copy(),\n",
    "    pheromones=c.pheromones,\n",
    "    generation=c.generation\n",
    ") for c in optimizer.state.population]\n",
    "for idx, c in enumerate(all_populations[0]):\n",
    "    c.cost = optimizer.state.population[idx].cost\n",
    "    c.uid = optimizer.state.population[idx].uid\n",
    "    c.parents = optimizer.state.population[idx].parents\n",
    "\n",
    "mutation_history.append(optimizer.config.p_mutation)\n",
    "\n",
    "g_max = optimizer.config.g_max\n",
    "for gen in range(1, g_max + 1):\n",
    "    p_local = optimizer.adaptive.get_local_search_prob(gen, g_max)\n",
    "    intensity = optimizer.adaptive.get_local_search_intensity(gen, g_max)\n",
    "    \n",
    "    current_mut = optimizer.config.p_mutation\n",
    "    if optimizer.state.stagnation_counter > 0:\n",
    "        stagnation_boost = optimizer.adaptive.update(optimizer.state.stagnation_counter) - optimizer.config.p_mutation\n",
    "        p_local = min(p_local + max(0.0, stagnation_boost), 0.95)\n",
    "        current_mut = min(optimizer.adaptive.update(optimizer.state.stagnation_counter), 0.95)\n",
    "    \n",
    "    _t0 = _time.time()\n",
    "    optimizer.state = optimizer.engine.step_generation(optimizer.state, p_local, intensity=intensity)\n",
    "    optimizer.state.generation = gen + 1\n",
    "    _elapsed = _time.time() - _t0\n",
    "    \n",
    "    mean_cost = sum(c.cost for c in optimizer.state.population) / len(optimizer.state.population)\n",
    "    total_elapsed = _time.time() - _pipeline_start\n",
    "    print(f\"[GEN {gen}/{g_max}] {_elapsed:.1f}s | Best={optimizer.state.best_fitness:.2f} Mean={mean_cost:.2f} | Stag={optimizer.state.stagnation_counter} p_mut={current_mut:.3f} | Total={total_elapsed:.0f}s\")\n",
    "    \n",
    "    optimizer.telemetry.log_lineage(optimizer.state.population)\n",
    "    optimizer.telemetry.log_generation(gen + 1, optimizer.state.best_fitness, mean_cost, p_local, optimizer.state.stagnation_counter)\n",
    "    optimizer.telemetry.export_json_snapshot(gen + 1, optimizer.state.best_fitness, mean_cost, optimizer.state.population)\n",
    "    \n",
    "    gen_pop = [Chromosome(\n",
    "        routes=[Route(path=r.path[:], city_graph=cg, id=r.id) for r in c.routes],\n",
    "        allocation=c.allocation.copy(),\n",
    "        pheromones=c.pheromones,\n",
    "        generation=c.generation\n",
    "    ) for c in optimizer.state.population]\n",
    "    for idx, c in enumerate(gen_pop):\n",
    "        c.cost = optimizer.state.population[idx].cost\n",
    "        c.uid = optimizer.state.population[idx].uid\n",
    "        c.parents = optimizer.state.population[idx].parents\n",
    "    \n",
    "    all_populations[gen] = gen_pop\n",
    "    mutation_history.append(current_mut)\n",
    "\n",
    "print(f\"\\nPipeline complete. Total wall time: {_time.time()-_pipeline_start:.0f}s\")"
]))

# Cell 6: Convergence markdown (from original)
cells.append(md(md_cells[3]["source"]))

# Cell 7: Convergence plot code (from original cell 7 — no changes needed)
cells.append(code(orig["cells"][7]["source"]))

# Cell 8: Trunk preservation markdown (from original)
cells.append(md(md_cells[4]["source"]))

# Cell 9: Trunk preservation code — FIXED: division-by-zero guard on top_edges
cells.append(code([
    "# 1. Identify best chromosome in final generation\n",
    "best_chrom_final = sorted(all_populations[g_max], key=lambda c: c.cost)[0]\n",
    "\n",
    "# 2. Identify the core \"trunk\" edges (top 15% highest pheromone edges in the final elite matrix)\n",
    "best_matrix = best_chrom_final.pheromones\n",
    "sorted_edges = sorted(best_matrix.tau.items(), key=lambda x: x[1], reverse=True)\n",
    "top_k = max(2, int(len(sorted_edges) * 0.15))\n",
    "top_edges = {e.id for e, tau in sorted_edges[:top_k]}\n",
    "\n",
    "# 3. Trace back ancestors in memory\n",
    "all_chroms_by_uid = {}\n",
    "for gen, pop in all_populations.items():\n",
    "    for c in pop:\n",
    "        all_chroms_by_uid[c.uid] = (c, gen)\n",
    "\n",
    "lineage_path = []\n",
    "curr_uid = best_chrom_final.uid\n",
    "while curr_uid:\n",
    "    if curr_uid in all_chroms_by_uid:\n",
    "        c, gen = all_chroms_by_uid[curr_uid]\n",
    "        lineage_path.append((c, gen))\n",
    "        curr_uid = c.parents[0] if c.parents else None\n",
    "    else:\n",
    "        break\n",
    "lineage_path = lineage_path[::-1]  # from Gen 0 to Gen N\n",
    "\n",
    "# 4. Calculate preservation percentages\n",
    "generations_lineage = []\n",
    "trunk_preservations = []\n",
    "for c, gen in lineage_path:\n",
    "    c_edges = {e.id for r in c.routes for e in r.path}\n",
    "    shared = c_edges.intersection(top_edges)\n",
    "    pct = (len(shared) / len(top_edges)) * 100 if top_edges else 0.0\n",
    "    generations_lineage.append(gen)\n",
    "    trunk_preservations.append(pct)\n",
    "\n",
    "# 5. Plot maps of route segment preservation\n",
    "def plot_lineage_generation(ax, chrom, top_edges, title):\n",
    "    # Sample background roads to prevent over-cluttering\n",
    "    for e in random.sample(list(cg.graph), min(800, len(cg.graph))):\n",
    "        ax.plot([e.start.lon, e.end.lon], [e.start.lat, e.end.lat], color='#cbd5e1', alpha=0.15, linewidth=0.5)\n",
    "        \n",
    "    # Draw standard routes\n",
    "    for r in chrom.routes:\n",
    "        lons = [e.start.lon for e in r.path] + [r.path[-1].end.lon]\n",
    "        lats = [e.start.lat for e in r.path] + [r.path[-1].end.lat]\n",
    "        ax.plot(lons, lats, color='#94a3b8', linewidth=1.5, alpha=0.4)\n",
    "        \n",
    "    # Highlight final trunk edges\n",
    "    for r in chrom.routes:\n",
    "        for e in r.path:\n",
    "            if e.id in top_edges:\n",
    "                ax.plot([e.start.lon, e.end.lon], [e.start.lat, e.end.lat], color='#f97316', linewidth=3.0, alpha=0.95)\n",
    "                \n",
    "    ax.set_title(title, fontsize=11, fontweight=\"bold\")\n",
    "    ax.axis(\"off\")\n",
    "\n",
    "fig, axes = plt.subplots(1, len(lineage_path), figsize=(4 * len(lineage_path), 4))\n",
    "if len(lineage_path) == 1:\n",
    "    axes = [axes]\n",
    "for idx, (c, gen) in enumerate(lineage_path):\n",
    "    plot_lineage_generation(axes[idx], c, top_edges, f\"Gen {gen}\\nTrunk Preserved: {trunk_preservations[idx]:.1f}%\")\n",
    "    \n",
    "plt.suptitle(\"Visual 2: Segment Mappings & Trunk Segment Propagation across Ancestry Path\", fontsize=15, fontweight='bold', y=1.05)\n",
    "plt.tight_layout()\n",
    "plt.show()\n",
    "\n",
    "# Render the timeline curve of preservation\n",
    "plt.figure(figsize=(8, 4))\n",
    "sns.lineplot(x=generations_lineage, y=trunk_preservations, marker=\"o\", color=\"#f97316\", linewidth=2.5)\n",
    "plt.title(\"Trunk Route Segment Discovery and Propagation Timeline\", fontsize=12, fontweight=\"bold\")\n",
    "plt.xlabel(\"Generation\", fontsize=11)\n",
    "plt.ylabel(\"% of Final Trunk Segments present in Genome\", fontsize=11)\n",
    "plt.ylim(0, 105)\n",
    "plt.xticks(generations_lineage)\n",
    "plt.show()"
]))

# Cell 10: Heuristic efficacy markdown (from original)
cells.append(md(md_cells[5]["source"]))

# Cell 11: Heuristic efficacy code (from original cell 11 — unchanged, works correctly)
cells.append(code(orig["cells"][11]["source"]))

# Cell 12: Phenotypic convergence markdown (from original)
cells.append(md(md_cells[6]["source"]))

# Cell 13: Phenotypic convergence code — FIXED: Wasserstein sampling
cells.append(code([
    "mean_jaccards = []\n",
    "mean_geds = []\n",
    "mean_wassersteins = []\n",
    "fitness_variances = []\n",
    "\n",
    "# FIX: Helper to deduplicate edge coordinates AND sample to a tractable size.\n",
    "# The wasserstein_2d LP solver builds an (n+m, n*m) constraint matrix. With ~5000\n",
    "# unique coords per chromosome, n*m = ~25M decision variables, causing 800 GiB OOM.\n",
    "# Weighted sampling to 200 points keeps the LP tractable (200*200 = 40K variables).\n",
    "MAX_WASSERSTEIN_POINTS = 200\n",
    "\n",
    "def _sample_coord_weights(routes, pheromones, max_pts):\n",
    "    \"\"\"Deduplicate edges by coordinate, then sample to max_pts for Wasserstein.\"\"\"\n",
    "    coord_weights = {}\n",
    "    for r in routes:\n",
    "        for e in r.path:\n",
    "            key = (e.start.lat, e.start.lon)\n",
    "            coord_weights[key] = coord_weights.get(key, 0.0) + pheromones.tau.get(e, 1.0)\n",
    "    coords = list(coord_weights.keys())\n",
    "    weights = list(coord_weights.values())\n",
    "    if len(coords) > max_pts:\n",
    "        w_arr = np.array(weights)\n",
    "        w_arr = w_arr / w_arr.sum()\n",
    "        indices = np.random.choice(len(coords), size=max_pts, replace=False, p=w_arr)\n",
    "        coords = [coords[i] for i in indices]\n",
    "        weights = [weights[i] for i in indices]\n",
    "    return coords, weights\n",
    "\n",
    "print(f\"[METRICS] Computing phenotypic convergence across {g_max+1} generations...\")\n",
    "for gen in range(g_max + 1):\n",
    "    pop = all_populations[gen]\n",
    "    pop_sorted = sorted(pop, key=lambda c: c.cost)\n",
    "    elite = pop_sorted[0]\n",
    "    \n",
    "    elite_edges = set(e for r in elite.routes for e in r.path)\n",
    "    elite_coords, elite_weights = _sample_coord_weights(elite.routes, elite.pheromones, MAX_WASSERSTEIN_POINTS)\n",
    "    \n",
    "    jaccards = []\n",
    "    geds = []\n",
    "    wassersteins = []\n",
    "    \n",
    "    for chrom in pop_sorted[1:]:\n",
    "        chrom_edges = set(e for r in chrom.routes for e in r.path)\n",
    "        jaccards.append(jaccard_similarity(elite_edges, chrom_edges))\n",
    "        geds.append(graph_edit_distance(elite_edges, chrom_edges, max_nodes=8))\n",
    "        \n",
    "        chrom_coords, chrom_weights = _sample_coord_weights(chrom.routes, chrom.pheromones, MAX_WASSERSTEIN_POINTS)\n",
    "        try:\n",
    "            w_dist = wasserstein_2d(elite_coords, elite_weights, chrom_coords, chrom_weights)\n",
    "        except Exception:\n",
    "            w_dist = 0.0\n",
    "        wassersteins.append(w_dist)\n",
    "        \n",
    "    mean_jaccards.append(np.mean(jaccards))\n",
    "    mean_geds.append(np.mean(geds))\n",
    "    mean_wassersteins.append(np.mean(wassersteins))\n",
    "    \n",
    "    costs = [c.cost for c in pop]\n",
    "    fitness_variances.append(np.var(costs))\n",
    "    print(f\"  Gen {gen}: Jaccard={np.mean(jaccards):.4f} GED={np.mean(geds):.4f} Wass={np.mean(wassersteins):.6f} FitVar={np.var(costs):.2f}\")\n",
    "\n",
    "# Normalize GED and Wasserstein to start at 1.0 for visual comparison of convergence rates\n",
    "norm_jaccards = np.array(mean_jaccards)\n",
    "norm_geds = np.array(mean_geds) / (mean_geds[0] if mean_geds[0] > 0 else 1.0)\n",
    "norm_wassersteins = np.array(mean_wassersteins) / (mean_wassersteins[0] if mean_wassersteins[0] > 0 else 1.0)\n",
    "\n",
    "fig, ax1 = plt.subplots(figsize=(12, 6))\n",
    "\n",
    "ax1.plot(range(g_max + 1), norm_jaccards, label=\"Jaccard Similarity to Elite (\u2191)\", color=\"#0ea5e9\", linewidth=2.5, marker=\"o\")\n",
    "ax1.plot(range(g_max + 1), norm_geds, label=\"Normalized GED to Elite (\u2193)\", color=\"#f43f5e\", linewidth=2.5, marker=\"s\")\n",
    "ax1.plot(range(g_max + 1), norm_wassersteins, label=\"Normalized 2D Wasserstein to Elite (\u2193)\", color=\"#10b981\", linewidth=2.5, marker=\"^\")\n",
    "ax1.set_xlabel(\"Generations\", fontsize=12)\n",
    "ax1.set_ylabel(\"Normalized Phenotypic Distance/Similarity metric\", fontsize=12)\n",
    "ax1.set_ylim(-0.05, 1.05)\n",
    "ax1.set_title(\"Visual 4: Multi-Dimensional Phenotypic Convergence and Fitness Collapse\", fontsize=14, fontweight=\"bold\")\n",
    "ax1.legend(loc=\"upper left\")\n",
    "\n",
    "ax2 = ax1.twinx()\n",
    "ax2.plot(range(g_max + 1), fitness_variances, label=\"Population Fitness Variance (Objective Space)\", color=\"#8b5cf6\", linewidth=2.0, marker=\"x\", linestyle=\":\")\n",
    "ax2.set_ylabel(\"Fitness Variance (Objective Space - $\\\\sigma^2$)\", color=\"#8b5cf6\", fontsize=12)\n",
    "ax2.tick_params(axis='y', labelcolor=\"#8b5cf6\")\n",
    "ax2.grid(False)\n",
    "ax2.legend(loc=\"upper right\")\n",
    "\n",
    "plt.tight_layout()\n",
    "plt.show()\n",
    "\n",
    "# Final cleanups of dummy YAML file\n",
    "try:\n",
    "    if os.path.exists(opt_yaml):\n",
    "        os.remove(opt_yaml)\n",
    "except Exception as e:\n",
    "    pass"
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

# Assign unique IDs
import uuid
for i, cell in enumerate(nb["cells"]):
    cell["id"] = uuid.uuid4().hex[:12]

out_path = "results_and_discussion_4_fixed.ipynb"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"[DONE] Generated {out_path} with {len(cells)} cells.")
