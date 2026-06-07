# Changelog — Jeepney Route System Optimization

Detailed log of all files modified, when the change was completed, why it was made, and what it achieves.

---

## 📅 June 7, 2026

### 1. Memetic Optimizer Lamarckian Mutation Wiring
* **File Modified:** [`utils/genetic.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/utils/genetic.py)
* **Time Done:** 05:22 UTC
* **Why:** In the original GA path, the chromosome `allocation` was never populated (`allocate_by_mohring` was dead code). As a result, the gap calculator computed demand-service gaps subtracting zero supply ($S_{ij} = 0$), making the stored disparity constantly $1.000$ and independent of routes. This rendered the Lamarckian local search mutation operator completely inert, as the mutated disparity was never less than the baseline.
* **What it achieves:** Populates chromosome `allocation` by running `allocate_by_mohring` inside `apply_lamarckian_mutation` and during population evaluations. This provides a valid demand-service gap signal to the local search operators, enabling acceptance of route modifications that improve actual spatial demand alignment.

### 2. Flexible Gap Calculator Signature
* **File Modified:** [`utils/pheromone.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/utils/pheromone.py)
* **Time Done:** 05:22 UTC
* **Why:** The gap calculator `calculate_demand_service_gaps` originally extracted allocations directly from a simulated `JeepSystem` object. To evaluate chromosomes offline during local search mutations without launching a full microscopic simulation, it needed to accept a manual allocation mapping.
* **What it achieves:** Allows passing an optional `allocation` dictionary directly to `calculate_demand_service_gaps`, enabling fast, simulation-free spatial disparity calculations during optimizer iterations.

### 3. 2D Wasserstein Coverage Matrix Bug Fix
* **File Modified:** [`opt_eval.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/opt_eval.py)
* **Time Done:** 05:24 UTC (initial fix), 05:42 UTC (performance calibration)
* **Why:** The 2D Wasserstein distance calculation in `opt_eval.py` used the exact linear programming solver. Passing the raw coordinate set (~100k nodes for 38-route systems) caused an $O(n^2 m^2)$ memory explosion (~80 GB RAM), crashing the solver silently and rendering the robustness heatmaps empty (showing blank white rectangles).
* **What it achieves:** Implemented spatial subsampling (under `WASS_MAX_NODES = 200`) in `_subsample_nodes`. This preserves the spatial distribution shape while capping pairwise comparisons at ~0.3 seconds, enabling the Chapter 4 robustness figures (`robustness_reproducibility.png` and `robustness_temporal.png`) to compile successfully with clean, annotated heatmaps.

### 4. Side-by-Side Initial vs. Final Route System Visualization
* **File Modified:** [`opt_eval.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/opt_eval.py)
* **Time Done:** 05:24 UTC
* **Why:** The results chapter required a visual comparison showing how the route systems evolve from their initial random configurations (Generation 2) to their final converged states (Generation 31) under the corrected allocation model.
* **What it achieves:** Implemented `plot_initial_vs_final` which plots route layouts over the faint Iligan City basemap, color-coded by route ID and annotated with their exact evaluated simulation fitness scores ($F_{\text{sim}}$). Saves the visual to `route_system_initial_vs_final.png`.

### 5. Advanced Evaluation Telemetry for Operational Analysis
* **File Modified:** [`opt_eval.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/opt_eval.py)
* **Time Done:** 06:21 UTC
* **Why:** To support a thorough operational analysis in Chapter 4, the post-evaluation needed to report how equal the fleet distribution is across routes and what the real demand-service gap is under a simulated run.
* **What it achieves:** 
  * Computes and logs the Gini coefficient and Coefficient of Variation (CV) of the fleet allocations across routes for both optimized and baseline systems.
  * Computes the realized L1 demand-service disparity index $D(R) = \sum |P_{ij} - S_{ij}|$ by constructing a `PheromoneMatrix` directly from the simulation passenger flows (`SimulationResult.recorded_paths`) and subtracting the active route-supply weights.
  * Prints summary stats (Mean $\pm$ Std) and comparison statistics (gain/reduction percentages) for both baseline and optimized groups.

### 6. Automatic Simulation Result Archiving
* **File Modified:** [`utils/optimizer.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/utils/optimizer.py)
* **Time Done:** 07:56 UTC
* **Why:** Running full microscopic simulations for evaluation is extremely slow (~20+ minutes for 14 setups). Since the optimizer already runs the microscopic simulation of the best chromosome of each generation, we can archive these results directly at runtime and skip re-running them during post-evaluation.
* **What it achieves:** Evaluates and saves the best chromosome from the initial population as `initial_best_sim_result.pkl` and the best chromosome from the final population as `best_sim_result.pkl` in the run directory. This captures the complete `SimulationResult` objects (including passenger commute times and edge traversal paths) with no significant execution overhead.

### 7. Instant Post-Evaluation via Pre-Saved Pickles
* **File Modified:** [`opt_eval.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/opt_eval.py)
* **Time Done:** 07:56 UTC
* **Why:** To prevent having to re-run heavy microscopic simulations during evaluation.
* **What it achieves:** Modifies `resim_evaluation` to check if `best_sim_result.pkl` and `initial_best_sim_result.pkl` exist for the target runs. If found, it bypasses the parallel simulation pool entirely and loads the archived results directly. This reconstructs the graph/route references and computes all post-evaluation metrics (fitness gains, commute time reductions, Gini/CV stats, Shannon entropy, and travel-time histograms) in less than a second, while retaining the parallel simulation fallback for backward compatibility.

### 8. LaTeX Refinement & Academic Alignment
* **Files Modified:** [`abstract.tex`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/abstract.tex), [`research_description_main.tex`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/research_description_main.tex), [`rrl_main.tex`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/rrl_main.tex), [`research_methodology.tex`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/research_methodology.tex), [`results_and_discussion.tex`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/results_and_discussion.tex)
* **Time Done:** 14:03 UTC
* **Why:** To align all chapters of the manuscript with the corrected fleet allocation model, the stigmergic pheromone local search mechanics, and the Total User Cost fitness metric.
* **What it achieves:** 
  * Refined Chapter 3 (Methodology) to specify the exact genetic algorithm parameters ($N_{\text{elite}} = 1$, $k_{\text{tournament}} = 3$) and the mathematical formula scaling the local search window sizes ($W$) based on local search intensity ($I_{\text{local}}(g)$) for repulsion and pruning.
  * Fleshed out all empty placeholders, outlines, and discussion visual comments in Chapter 4 (Results & Discussion) with complete, rigorous academic text, referencing the compiled robustness matrices, temporal demand graphs, travel time distributions, and Shannon entropy diversity metrics.
  * Harmonized the abstract, Chapter 1 (Introduction), and Chapter 2 (Literature Review) to frame the problem within the Transit Route Network Design Problem (TRNDP) sub-class, and replaced inaccurate references to "commute time minimization" with the formal multi-dimensional "Total User Cost" objective.
  * Structured and expanded the Scope and Limitations section in Chapter 1 to explicitly categorize inclusions and exclusions (static demand matrix, simplified historical traffic, purely user-centric objectives, static route trajectories, lack of street safety/pedestrian modeling, and system-level focus).
  * Fixed a syntax error in Chapter 4 (`results_and_discussion.tex`) where a missing closing brace `}` on a figure caption and missing `\label` / `\end{figure}` tags prevented successful compilation in LaTeX (Overleaf).

### 9. Optimization and Performance Overhaul for Lamarckian Mutation & Local Search
* **Files Modified:** [`utils/city_graph.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/utils/city_graph.py), [`utils/genetic.py`](file:///c:/Users/lifei/OneDrive/Desktop/Portfolio/Jeepney-Route-System-Optimization/utils/genetic.py)
* **Time Done:** 16:45 UTC
* **Why:** The recent bug fix that activated the spatial disparity local search signals and Lamarckian mutation gating also introduced severe computational bottlenecks: (1) Tortuosity pruning was running thousands of un-cached Python A* queries on the 26k-edge road network graph, and (2) Lamarckian mutation was running a full 2,000-sample Mohring fleet allocation (involving a multi-layer graph build and 2,000 A* queries) three times per mutation event.
* **What it achieves:**
  * **Shortest Path Caching:** Decorated `CityGraph.find_shortest_path` with an LRU cache (`maxsize=30000`). Since the road network is static, caching routes between repeated origin/destination nodes reduces A* pathfinding time to $O(1)$ after the first query.
  * **Surrogate Fleet Allocation Scaling:** Added a `sample_size` parameter to `_allocate_fleet_mohring` and scaled the passenger sample size from `2000` down to `150` *only* during mutation gating checks. A sample size of 150 yields highly stable relative demand shares while speeding up Mohring allocation runs by $\approx 13\times$.
  * **Removal of Rejection Redundancy:** Eliminated the third, redundant fleet allocation call when a mutation is rejected. Since any child's allocation is overwritten by the exact post-simulation allocation during main generation evaluation anyway, this redundant graph rebuild and pathfinding pass was completely bypassed.

