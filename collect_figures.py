"""
collect_figures.py — gather every Chapter 4 figure into one Overleaf-ready folder.

The figures are produced in scattered places (rnd/documentation/, rnd/images/,
outputs/rnd_weight_tolerance/, results_and_discussion/images/). This copies each into
chap4/figures/ under the exact filename the LaTeX \\includegraphics{chap4/figures/...} expects.

Safe to run anytime / repeatedly: it copies whatever exists now and lists what is still
pending (e.g. figures that only appear after the opt runs + opt_eval.py finish).

    python collect_figures.py
"""
import os
import shutil
from pathlib import Path

DEST = Path("chap4/figures")

# dest filename  ->  list of candidate source paths (first existing wins)
FIGURES = {
    # ---- 4.1 Environment & Demand (already produced) ----
    "citygraph_comparison.png":    ["rnd/documentation/citygraph_comparison.png"],
    "ddm_pre_imputed.png":         ["rnd/documentation/ddm_pre_imputed.png"],
    "ddm_3maps_comparison.png":    ["rnd/documentation/ddm_3maps_comparison.png"],
    "ddm_time_comparison.png":     ["rnd/documentation/ddm_time_comparison.png"],
    "ddm_distributions.png":       ["rnd/documentation/ddm_distributions.png"],
    "ddm_whole_vs_arterials.png":  ["rnd/documentation/ddm_whole_vs_arterials.png"],

    # ---- 4.2 Architectural validation ----
    "constructed_travelgraph.png":     ["rnd/documentation/constructed travelgraph.png",
                                        "rnd/documentation/constructed_travelgraph.png"],
    "passenger_journey_snapshots.png": ["rnd/documentation/passenger_journey_snapshots.png"],

    # ---- 4.3 Calibration & verification ----
    # 4.3.1 Mohring (friend)
    "mohring_stability.png":       ["results_and_discussion/images/mohring_variance_collapse.png",
                                    "outputs/mohring_stability/plots/cv_route_count_38.png",
                                    ".cache/analysis/mohring_convergence.png"],
    # 4.3.3 Horizon + volume (done)
    "horizon_volume_calibration.png": ["rnd/images/rnd1_horizon_and_volume.png",
                                       "results_and_discussion/images/rnd1_horizon_and_volume.png"],
    # 4.3.4 Weight tolerance / opportunistic riding (friend)
    "weight_tolerance_t0.png":     ["outputs/rnd_weight_tolerance/weight_tolerance_delta_box_t0p0.png"],
    "weight_tolerance_t14.png":    ["outputs/rnd_weight_tolerance/weight_tolerance_delta_box_t14p44.png"],
    "weight_tolerance_t100.png":   ["outputs/rnd_weight_tolerance/weight_tolerance_delta_box_t100p0.png"],
    "weight_tolerance_box.png":    ["outputs/rnd_weight_tolerance/weight_tolerance_delta_box.png"],
    # 4.3.6 Lamarckian operators (nb_4_3_6_lamarckian.ipynb)
    "lamarckian_operators_toy.png":    ["results_and_discussion/images/lamarckian_operators_toy.png"],
    "lamarckian_operators_iligan.png": ["results_and_discussion/images/lamarckian_operators_iligan.png"],
    "gap_vs_fitness.png":              ["results_and_discussion/images/gap_vs_fitness.png"],
    "demand_service_gap_field.png":   ["results_and_discussion/images/demand_service_gap_field.png"],
    # 4.3.6 / 4.4.2 / 4.4.3 Memetic mechanics (fig_memetic.py)
    "memetic_demand_memory_gap.png":  ["results_and_discussion/images/memetic_demand_memory_gap.png"],
    "memetic_hub_crossover.png":      ["results_and_discussion/images/memetic_hub_crossover.png"],
    "memetic_pheromone_blend.png":    ["results_and_discussion/images/memetic_pheromone_blend.png"],
    "memetic_gap_change.png":         ["results_and_discussion/images/memetic_gap_change.png"],

    # ---- 4.4 / 4.5 Evolution + optimized network (opt_eval.py, after the 8h runs) ----
    "convergence_curves.png":          ["results_and_discussion/images/convergence_curves.png"],
    "robustness_reproducibility.png":  ["results_and_discussion/images/robustness_reproducibility.png"],
    "robustness_temporal.png":         ["results_and_discussion/images/robustness_temporal.png"],
    "baseline_vs_optimized.png":       ["results_and_discussion/images/baseline_vs_optimized.png"],
    "equity_traveltime_hist.png":      ["results_and_discussion/images/equity_traveltime_hist.png"],
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    copied, missing = [], []
    for dest_name, candidates in FIGURES.items():
        src = next((c for c in candidates if os.path.exists(c)), None)
        if src is None:
            missing.append(dest_name)
            continue
        shutil.copy2(src, DEST / dest_name)
        copied.append((dest_name, src))

    print(f"Gathered into {DEST}/  ({len(copied)} copied, {len(missing)} pending)\n")
    for dest_name, src in copied:
        print(f"  [copied]  {dest_name:34s} <- {src}")
    if missing:
        print("\n  Still pending (generate, then re-run this script):")
        for dest_name in missing:
            print(f"  [pending] {dest_name}")
    print(f"\nDrop the {DEST}/ folder into your Overleaf chap4/figures/.")


if __name__ == "__main__":
    main()
