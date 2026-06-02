import json
import os

notebook_path = r"c:\Users\lifei\OneDrive\Desktop\Portfolio\Jeepney-Route-System-Optimization\results_and_discussion.ipynb"

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# The new cell content
cell_edge_type = {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "## 7. Edge Type vs Traffic Weight (Point Plot with Error Bars)\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "from collections import defaultdict\n",
    "\n",
    "# Map edge types (highway tags) to their imputed IDW traffic weights using the 1 PM DDM.\n",
    "# Since weights are computed per node, we average the start and end node weights for each edge.\n",
    "edge_weights_by_type = defaultdict(list)\n",
    "\n",
    "for edge in cg.graph:\n",
    "    if not edge.is_drivable or not edge.osm_highway:\n",
    "        continue\n",
    "        \n",
    "    highway = edge.osm_highway\n",
    "    if isinstance(highway, list):\n",
    "        highway = highway[0] # Take the primary tag if it's a list\n",
    "        \n",
    "    w_start = ddm_1pm.traffic_weights.get(edge.start)\n",
    "    w_end = ddm_1pm.traffic_weights.get(edge.end)\n",
    "    \n",
    "    if w_start is not None and w_end is not None:\n",
    "        avg_weight = (w_start + w_end) / 2.0\n",
    "        edge_weights_by_type[highway].append(avg_weight)\n",
    "\n",
    "# Calculate means and standard deviations\n",
    "categories = []\n",
    "means = []\n",
    "stdevs = []\n",
    "\n",
    "# Sort by mean weight descending\n",
    "sorted_types = sorted(edge_weights_by_type.items(), key=lambda x: np.mean(x[1]), reverse=True)\n",
    "\n",
    "for hw_type, weights in sorted_types:\n",
    "    if len(weights) > 5: # Only include categories with a meaningful sample size\n",
    "        categories.append(hw_type)\n",
    "        means.append(np.mean(weights))\n",
    "        stdevs.append(np.std(weights))\n",
    "\n",
    "fig, ax = plt.subplots(figsize=(10, 6))\n",
    "\n",
    "x_pos = np.arange(len(categories))\n",
    "ax.errorbar(x_pos, means, yerr=stdevs, fmt='o', color='royalblue', \n",
    "            ecolor='lightcoral', elinewidth=3, capsize=5, capthick=2, markersize=8)\n",
    "\n",
    "ax.set_xticks(x_pos)\n",
    "ax.set_xticklabels(categories, rotation=45, ha='right', fontsize=12)\n",
    "ax.set_ylabel('Friction Weight (Travel Time / Free Flow)', fontsize=12)\n",
    "ax.set_title('Average IDW Traffic Weight by Road Type (1 PM)', fontsize=14, pad=15)\n",
    "ax.grid(axis='y', linestyle='--', alpha=0.7)\n",
    "\n",
    "plt.tight_layout()\n",
    "out_path = os.path.join(IMG_DIR, \"edge_type_weights_errorbars.png\")\n",
    "plt.savefig(out_path, dpi=300, bbox_inches='tight')\n",
    "plt.show()\n"
   ]
}

# Append this right at the end of the notebook (which is under "DDM Metrics & Distributions")
nb['cells'].append(cell_edge_type)

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Edge type cell appended successfully.")
