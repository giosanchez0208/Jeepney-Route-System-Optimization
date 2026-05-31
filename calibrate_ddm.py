import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Ensure we can import from utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig

def mock_data_generator():
    """
    Creates structurally accurate dummy data representing the output of the framework.
    NOTE: Provided strictly to fulfill the formatting constraint. The actual 
    execution will 'frankenstein' the existing codebase using the real Iligan graph.
    """
    import random
    
    alpha_vals = np.linspace(0.1, 2.0, 10)
    beta_vals = np.linspace(0.1, 2.0, 10)
    
    mock_matrix = np.zeros((10, 10))
    for i in range(10):
        for j in range(10):
            mock_matrix[i, j] = random.uniform(0.5, 0.9)
            
    return alpha_vals, beta_vals, mock_matrix

def calculate_gini(array: list[float]) -> float:
    """Calculate the Gini coefficient of a numpy array."""
    # All values must be non-negative
    array = np.array(array, dtype=np.float64)
    array = array.flatten()
    if np.amin(array) < 0:
        array -= np.amin(array) # Values cannot be negative
    array += 1e-10 # Values cannot be 0
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return ((np.sum((2 * index - n  - 1) * array)) / (n * np.sum(array)))

def generate_calibration_heatmap():
    print("Setting up styling...")
    sns.set_theme(style="white")
    plt.rcParams.update({
        'font.family': 'serif',
        'figure.dpi': 300,
        'axes.labelsize': 12,
        'axes.titlesize': 14
    })

    print("Instantiating CityGraph...")
    # Load real Iligan City graph (this uses cached parsed data if available)
    bbox = (8.1500, 8.3300, 124.1500, 124.4000)
    city = CityGraph(
        name="Iligan City",
        bbox=bbox,
        pbf_path="utils/data/iligan-city.pbf",
        cache_prefix="iligan_arterial",
        verbose=True
    )
    
    print("Instantiating DirectDemandSampler (baseline)...")
    config = DDMConfig()
    sampler = DirectDemandSampler(city, config=config, verbose=True)

    print("Performing 10x10 Grid Search for Alpha/Beta...")
    alpha_vals = np.linspace(0.1, 2.0, 10)
    beta_vals = np.linspace(0.1, 2.0, 10)
    
    gini_matrix = np.zeros((10, 10))
    
    target_gini = 0.75
    best_diff = float('inf')
    best_idx = (0, 0)
    
    for i, a in enumerate(alpha_vals):
        for j, b in enumerate(beta_vals):
            sampler.config.alpha = a
            sampler.config.beta = b
            
            raw_probs = sampler._apply_ddm(sampler.traffic_weights, sampler.centrality_scores)
            gini = calculate_gini(raw_probs)
            
            gini_matrix[i, j] = gini
            
            diff = abs(gini - target_gini)
            if diff < best_diff:
                best_diff = diff
                best_idx = (i, j)

    print(f"Optimal Configuration: Alpha={alpha_vals[best_idx[0]]:.2f}, Beta={beta_vals[best_idx[1]]:.2f} (Gini={gini_matrix[best_idx]:.4f})")

    print("Generating Heatmap...")
    plt.figure(figsize=(10, 8))
    
    # We want Alpha on X-axis and Beta on Y-axis.
    # The matrix is indexed as gini_matrix[i, j] where i is alpha, j is beta.
    # To plot correctly with seaborn where X is column and Y is row, we transpose.
    # Also, standard heatmaps often have Y going downwards, so we can flip it so Beta goes up, or just use standard labels.
    
    # Let's set up the labels
    xticklabels = [f"{v:.2f}" for v in alpha_vals]
    yticklabels = [f"{v:.2f}" for v in beta_vals]
    
    # Plot heatmap (transpose to put Alpha on X-axis, Beta on Y-axis)
    ax = sns.heatmap(
        gini_matrix.T,
        annot=True,
        fmt=".3f",
        cmap="YlOrRd",
        xticklabels=xticklabels,
        yticklabels=yticklabels,
        cbar_kws={'label': 'Spatial Gini Coefficient'}
    )
    
    ax.set_xlabel(r"$\alpha$ (Traffic Flow Weight)")
    ax.set_ylabel(r"$\beta$ (Betweenness Centrality Weight)")
    ax.set_title(r"DDM Calibration: Spatial Gini Coefficient Grid Search (Target=0.75)", pad=20)
    
    ax.invert_yaxis() # Ensure Y-axis (Beta) goes from 0.1 at bottom to 2.0 at top
    
    # Mark the optimal cell with a distinct star
    # Since we transposed, X is best_idx[0] and Y is best_idx[1]
    best_x = best_idx[0] + 0.5
    best_y = best_idx[1] + 0.5
    
    ax.plot(best_x, best_y, marker='*', markersize=20, color='blue', markeredgecolor='white', label='Optimal (closest to 0.75)')
    ax.legend(loc='lower right')
    
    plt.tight_layout()
    
    out_dir = "documentation/phase_1"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fig_2a_idw_grid_search.png")
    
    print(f"Saving visualization to {out_path}...")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print("Process complete!")

if __name__ == "__main__":
    generate_calibration_heatmap()
