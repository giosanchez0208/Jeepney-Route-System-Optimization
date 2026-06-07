"""Quick test of PART 1 only — convergence + similarity matrices (Wasserstein fix)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
from opt_eval import (discover_runs, plot_convergence, similarity_matrix,
                      network_edges, network_nodes, REPRO_TAGS, TEMPORAL,
                      load_final_routes)

runs = discover_runs()
print(f"Discovered {len(runs)} run(s): {list(runs)}")

plot_convergence(runs)

nets = {}
for tag, run_dir in runs.items():
    routes = load_final_routes(run_dir)
    if routes:
        nets[tag] = {"edges": network_edges(routes), "nodes": network_nodes(routes)}

for t in list(nets)[:3]:
    print(f"  {t}: {len(nets[t]['edges'])} edges, {len(nets[t]['nodes'])} nodes")

repro = {t: nets[t] for t in REPRO_TAGS if t in nets}
similarity_matrix(repro, "4.5.2 Cross-run robustness (reproducibility)", "robustness_reproducibility.png")

temporal = {t: nets[t] for t in TEMPORAL if t in nets}
similarity_matrix(temporal, "4.5.3 Demand-regime robustness (temporal DDM)", "robustness_temporal.png")

print("PART 1 done.")
