import os
import sys
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import seaborn as sns

# Ensure we can import from utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig

def mock_data_generator():
    from utils.node import Node
    from utils.directed_edge import DirEdge
    
    mock_city = CityGraph(name="MockCity")
    n1 = Node(124.0, 8.0)
    n2 = Node(124.1, 8.1)
    e = DirEdge(n1, n2, is_drivable=True)
    mock_city.inject_toy_data([n1, n2], [e])
    
    return mock_city, [n1, n2]

def generate_visualization():
    print("Setting up styling...")
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({
        'font.family': 'serif',
        'figure.dpi': 300,
        'axes.labelsize': 12,
        'axes.titlesize': 14
    })
    
    print("Instantiating CityGraph from scratch...")
    # Iligan bbox based on the existing configuration
    bbox = (8.1500, 8.3300, 124.1500, 124.4000)
    
    # Using a unique cache prefix to force raw parsing from the .pbf file instead of loading cache
    city = CityGraph(
        name="Iligan City",
        bbox=bbox,
        pbf_path="utils/data/iligan-city.pbf",
        cache_prefix="fig1_fresh_parse",
        verbose=True
    )
    
    print("Instantiating DirectDemandSampler...")
    config = DDMConfig()
    sampler = DirectDemandSampler(city, config=config, verbose=True)
    sampled_nodes = sampler.target_centroids

    print("Extracting edges for visualization...")
    all_edges = []
    drivable_edges = []
    
    # Iterate through all directed edges in the graph
    for edge in city.graph:
        segment = [(edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat)]
        all_edges.append(segment)
        if edge.is_drivable:
            drivable_edges.append(segment)

    print("Creating plots...")
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    
    # --- Subplot 1: Arterial Pruning ---
    ax1 = axes[0]
    ax1.set_title("Topological Pruning: All Edges vs. Arterial (is_drivable)")
    ax1.set_xlabel("Longitude")
    ax1.set_ylabel("Latitude")
    
    # Plot all parsed edges in faint gray
    lc_all = LineCollection(all_edges, colors='lightgray', linewidths=0.5, alpha=0.6, zorder=1)
    ax1.add_collection(lc_all)
    
    # Plot drivable (arterial) edges in thick black
    lc_drivable = LineCollection(drivable_edges, colors='black', linewidths=1.2, zorder=2, label='Arterial Skeleton')
    ax1.add_collection(lc_drivable)
    
    ax1.autoscale()
    ax1.margins(0.05)
    ax1.legend(loc='upper right')
    
    # --- Subplot 2: Efraimidis Sampling ---
    ax2 = axes[1]
    ax2.set_title("DDM Efraimidis Sampling (Weighted Reservoir on POIs)")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Latitude")
    
    # Plot the arterial skeleton in faint gray for context
    lc_arterial = LineCollection(drivable_edges, colors='gray', linewidths=0.8, alpha=0.4, zorder=1)
    ax2.add_collection(lc_arterial)
    
    # Plot sampled nodes (centroids) from the Direct Demand Model
    lon_vals = [n.lon for n in sampled_nodes]
    lat_vals = [n.lat for n in sampled_nodes]
    ax2.scatter(lon_vals, lat_vals, c='red', s=15, alpha=0.5, zorder=3, edgecolors='none', label=f'Sampled POIs (n={len(sampled_nodes)})')
    
    ax2.autoscale()
    ax2.margins(0.05)
    ax2.legend(loc='upper right')
    
    plt.tight_layout()
    
    # Save the output
    out_dir = "documentation/phase_1"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fig_1_environment_sampling.png")
    
    print(f"Saving visualization to {out_path}...")
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print("Process complete!")

if __name__ == "__main__":
    generate_visualization()
