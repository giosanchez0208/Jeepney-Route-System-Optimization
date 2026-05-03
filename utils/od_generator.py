"""od_generator.py

TrafficAwareODGenerator(cg: CityGraph, traffic_csv_path: str, betas: Optional[dict] = None) -> None creates the passenger generation model.
_bind_data(self) -> None spatially maps dynamic CityGraph nodes to static traffic data and calculates v_ped.
generate_origins(self, n_points: int) -> list[Node] returns a list of sampled Node objects based on pedestrian volume weights.
"""

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pathlib import Path
from typing import Optional

from .city_graph import CityGraph
from .node import Node

class TrafficAwareODGenerator:
    """Spatially binds static traffic data to dynamic CityGraph nodes to generate demand."""

    DEFAULT_BETAS = {
        'beta_0': 0.5,   # Intercept
        'beta_1': 0.6,   # ln(ADT_prop) - Traffic Intensity
        'beta_2': 0.3,   # ln(D_bldg) - Building Density
        'beta_3': 0.2,   # ln(C_B) - Betweenness Centrality
        'epsilon': 0.05  # Error term
    }

    def __init__(self, cg: CityGraph, traffic_csv_path: str | Path, betas: Optional[dict[str, float]] = None) -> None:
        self.cg = cg
        self.traffic_csv_path = Path(traffic_csv_path)
        self.betas = betas if betas is not None else self.DEFAULT_BETAS
        
        if not self.traffic_csv_path.exists():
            raise FileNotFoundError(f"Traffic data file not found at: {self.traffic_csv_path}")
            
        self.df_traffic = pd.read_csv(self.traffic_csv_path)
        
        # We will store the calculated pedestrian volume for each dynamic Node
        self.node_vped: dict[Node, float] = {}
        
        self._bind_data()

    def _bind_data(self) -> None:
        """Uses a KD-Tree to snap CityGraph nodes to the nearest CSV data point."""
        
        # 1. Extract coordinates from the static traffic CSV
        csv_coords = np.column_stack((self.df_traffic['lat'], self.df_traffic['lon']))
        
        # 2. Build the spatial index
        kdtree = cKDTree(csv_coords)
        
        # 3. Extract coordinates from the dynamic CityGraph nodes
        cg_coords = np.array([(n.lat, n.lon) for n in self.cg.nodes])
        
        # 4. Query the nearest neighbor in the CSV for every CityGraph node
        # We only care about the indices of the matches
        _, matched_indices = kdtree.query(cg_coords)
        
        # 5. Extract the matched rows from the traffic dataframe
        matched_df = self.df_traffic.iloc[matched_indices].copy()
        
        # 6. Apply the log-linear regression model (Equation 2)
        eps = 1e-6 
        b = self.betas
        
        ln_v_ped = (
            b['beta_0'] +
            b['beta_1'] * np.log(matched_df['ADT_prop'] + eps) +
            b['beta_2'] * np.log(matched_df['bldg_density'] + eps) +
            b['beta_3'] * np.log(matched_df['bc'] + eps) +
            b['epsilon']
        )
        v_ped_values = np.exp(ln_v_ped).values
        
        # 7. Map the calculated v_ped back to the actual Node objects
        for node, v_ped in zip(self.cg.nodes, v_ped_values):
            self.node_vped[node] = v_ped

    def generate_origins(self, n_points: int = 10000) -> list[Node]:
        """Samples actual Node objects weighted by their calculated v_ped."""
        
        nodes = list(self.node_vped.keys())
        weights = np.array(list(self.node_vped.values()))
        
        if weights.sum() == 0:
            raise ValueError("Total pedestrian volume is 0. Cannot generate probabilities.")
            
        # Normalize weights to create a probability distribution
        probabilities = weights / weights.sum()
        
        # Sample the nodes
        sampled_nodes = np.random.choice(nodes, size=n_points, p=probabilities, replace=True)
        
        return list(sampled_nodes)


### SANITY CHECK ###
if __name__ == "__main__":
    import io
    import tkinter as tk
    from collections import Counter
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from PIL import Image, ImageTk
    import numpy as np
    from scipy.stats import gaussian_kde

    print("Constructing CityGraph...")
    cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
    
    print(f"CityGraph built with {len(cg.nodes)} nodes.")
    
    data_path = "data/iligan_node_with_traffic_data.csv" 
    
    print("Binding traffic data and calculating probabilities...")
    od_gen = TrafficAwareODGenerator(cg, data_path)
    
    n_passengers = 10000
    print(f"Generating {n_passengers} passenger origins...")
    origins = od_gen.generate_origins(n_points=n_passengers)
    
    print("Rendering in-memory smooth heatmap with network overlay...")
    
    counts = Counter(origins)
    lons = [n.lon for n in counts.keys()]
    lats = [n.lat for n in counts.keys()]
    freqs = list(counts.values())

    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)
    fig.patch.set_facecolor('#0f0f0f')
    ax.set_facecolor('#0f0f0f')
    
    # 1. Prepare data for KDE
    xy = np.vstack([lons, lats])
    kde = gaussian_kde(xy, weights=freqs, bw_method=0.15) 

    # 2. Create a dense 2D grid covering the bounds
    grid_size = 200
    lon_grid, lat_grid = np.mgrid[min(lons):max(lons):grid_size*1j, min(lats):max(lats):grid_size*1j]
    grid_coords = np.vstack([lon_grid.ravel(), lat_grid.ravel()])

    # 3. Evaluate the KDE
    z = kde(grid_coords).reshape(grid_size, grid_size)

    # 4. Plot filled contours at the bottom (zorder=1)
    ax.contourf(lon_grid, lat_grid, z, levels=25, cmap='turbo', alpha=0.85, zorder=1)
    
    # 5. Overlay contour lines (zorder=2)
    ax.contour(lon_grid, lat_grid, z, levels=25, colors='white', linewidths=0.2, alpha=0.4, zorder=2)

    # 6. Draw base graph ON TOP for structural context (zorder=3)
    segments = [((edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat)) for edge in cg.graph]
    lc = LineCollection(segments, colors="#ffffff", linewidths=0.5, alpha=0.3, zorder=3)
    ax.add_collection(lc)
    
    ax.axis("off")
    ax.set_aspect("equal", adjustable="box")
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    image = Image.open(buf).convert("RGBA")

    WINDOW_SIZE = 800
    # Add a slight crop/resize to fit the window cleanly
    image = image.resize((WINDOW_SIZE, WINDOW_SIZE), Image.LANCZOS)
    
    root = tk.Tk()
    root.title("Passenger Generation Heatmap")
    root.geometry(f"{WINDOW_SIZE}x{WINDOW_SIZE}")
    root.resizable(False, False)
    
    photo = ImageTk.PhotoImage(image)
    label = tk.Label(root, image=photo, bd=0)
    label.pack()
    label.image = photo
    
    root.mainloop()