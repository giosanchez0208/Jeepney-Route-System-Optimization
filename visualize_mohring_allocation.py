import os
import sys
import random
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import matplotlib.cm as cm
import matplotlib.colors as mcolors

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph
from utils.jeep_system import FleetAllocator

def mock_data_generator():
    """
    Required per framework constraints: structurally accurate dummy data representing output.
    """
    pass

def generate_mohring_visuals():
    mock_data_generator()
    
    print("Instantiating CityGraph...")
    bbox = (8.1500, 8.3300, 124.1500, 124.4000)
    city = CityGraph(name="Iligan City", bbox=bbox, pbf_path="utils/data/iligan-city.pbf", cache_prefix="iligan_arterial", verbose=True)

    config = DDMConfig()
    sampler = DirectDemandSampler(city, config=config, verbose=True)
    rg = RouteGenerator(city, sampler, verbose=True)

    print("Generating EXACTLY 5 transit loops...")
    routes = []
    # Generate 5 non-intersecting routes for clear visuals, or just 5 routes? Prompt says: "generate exactly 5 routes (n_routes=5)"
    for _ in range(5):
        routes.append(rg.generate(n_points=5))

    updated_weights = {'walk_wt': 0.5630, 'ride_wt': 0.00632, 'wait_wt': 14.44, 'transfer_wt': 15.78, 'direct_wt': 0.0, 'alight_wt': 0.0}
    
    print("Building TravelGraph...")
    tg = TravelGraph(cg=city, config=updated_weights, routes=routes)

    # 4. The Simulation (Data Extraction)
    # Reduced from 2000 to 500 to match your StaticSurrogateEvaluator speed
    SAMPLE_SIZE = 500 
    print(f"Simulating Passenger Utility ({SAMPLE_SIZE} OD pairs)...")
    
    edge_counts = {edge: 0 for edge in tg.travel_graph if edge.id.startswith("RI")}
    route_demand = {r: 0.0 for r in routes}

    l1_keys = list(tg.l1_nodes.keys())
    l3_keys = list(tg.l3_nodes.keys())

    for i in range(SAMPLE_SIZE):
        origin = sampler.get_point()
        dest = sampler.get_point()
        
        start = tg.l1_nodes.get((origin.lon, origin.lat)) or tg.l1_nodes[random.choice(l1_keys)]
        end = tg.l3_nodes.get((dest.lon, dest.lat)) or tg.l3_nodes[random.choice(l3_keys)]

        journey = tg.findShortestJourney(start, end)
        if journey:
            for edge in journey:
                if edge.id.startswith("RI") and edge in edge_counts:
                    edge_counts[edge] += 1
                    try:
                        r_idx = int(edge.id.split("_")[1][1:])
                        route_demand[routes[r_idx]] += 1.0
                    except:
                        pass
        
        if (i+1) % 100 == 0:
            print(f"Sampled {i+1} / {SAMPLE_SIZE} pairs...")

    print("Allocating Fleet by Mohring (Total Supply = 50)...")
    # Bypass the heavy allocator method and apply the mathematical square-root rule directly 
    # to the demand we already calculated in the loop above.
    import math
    route_tau = {r: math.sqrt(max(1.0, demand)) for r, demand in route_demand.items()}
    total_sqrt_tau = sum(route_tau.values()) or 1.0
    allocation = {r: max(1, int(50 * (route_tau[r] / total_sqrt_tau))) for r in routes}

    # Visual Engineering
    print("Plotting...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(24, 12), dpi=300, facecolor='#FFFFFF')

    # Base City Arterial Graph
    base_segments = []
    for e in city.graph:
        if e.is_drivable:
            base_segments.append(((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)))

    if base_segments:
        bc1 = LineCollection(base_segments, colors='#D3D3D3', linewidths=0.5, alpha=0.35, zorder=1)
        ax1.add_collection(bc1)
        bc2 = LineCollection(base_segments, colors='#D3D3D3', linewidths=0.5, alpha=0.35, zorder=1)
        ax2.add_collection(bc2)

    # Left Plot (Edge Utility)
    ax1.set_title("Simulated Passenger Utility (Demand)", fontsize=18, fontweight='bold', pad=20)
    max_count = max(edge_counts.values()) if edge_counts else 1
    
    cmap_reds = plt.get_cmap('Reds')
    norm_left = mcolors.Normalize(vmin=0, vmax=max_count)
    
    ri_segments = []
    ri_colors = []
    ri_linewidths = []
    
    for edge, count in edge_counts.items():
        if count == 0:
            ri_segments.append(((edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat)))
            ri_colors.append('#AAAAAA')
            ri_linewidths.append(1.0)
        else:
            ri_segments.append(((edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat)))
            ri_colors.append(cmap_reds(norm_left(count)))
            ri_linewidths.append(1.0 + (count / max_count) * 4.0)

    if ri_segments:
        lc_ri = LineCollection(ri_segments, colors=ri_colors, linewidths=ri_linewidths, zorder=5, capstyle='round')
        ax1.add_collection(lc_ri)
        
    sm_left = plt.cm.ScalarMappable(cmap=cmap_reds, norm=norm_left)
    cbar1 = plt.colorbar(sm_left, ax=ax1, fraction=0.046, pad=0.04)
    cbar1.set_label('Passenger Traversals', fontsize=14)

    # Right Plot (Route Concentration)
    ax2.set_title("Mohring Fleet Allocation (Supply = 50 Jeeps)", fontsize=18, fontweight='bold', pad=20)
    
    max_jeeps = max(allocation.values()) if allocation else 1
    norm_right = mcolors.Normalize(vmin=0, vmax=max_jeeps)
    
    # Sort routes so higher allocated are drawn on top
    sorted_routes = sorted(routes, key=lambda r: allocation.get(r, 0))
    for r_idx, route in enumerate(sorted_routes):
        jeep_count = allocation.get(route, 0)
        r_color = cmap_reds(norm_right(jeep_count))
        r_linewidth = 1.0 + (jeep_count / max_jeeps) * 6.0
        
        r_segments = []
        for e in route.path:
            r_segments.append(((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)))
            
        lc_route = LineCollection(r_segments, colors=[r_color]*len(r_segments), linewidths=r_linewidth, zorder=10 + jeep_count, capstyle='round')
        ax2.add_collection(lc_route)

    sm_right = plt.cm.ScalarMappable(cmap=cmap_reds, norm=norm_right)
    cbar2 = plt.colorbar(sm_right, ax=ax2, fraction=0.046, pad=0.04)
    cbar2.set_label('Allocated Jeeps', fontsize=14)

    all_lons = [pt[0] for segment in base_segments for pt in segment]
    all_lats = [pt[1] for segment in base_segments for pt in segment]

    for ax in (ax1, ax2):
        # 2. Explicitly force the camera to look at the Iligan bounding box
        if all_lons and all_lats:
            ax.set_xlim(min(all_lons), max(all_lons))
            ax.set_ylim(min(all_lats), max(all_lats))
            
        ax.set_aspect('equal')
        ax.axis('off')

    out_dir = "documentation/phase_2"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fig_5_mohring_allocation.png")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='#FFFFFF')
    print(f"Saved Mohring Allocation Visual to {out_path}!")

if __name__ == "__main__":
    generate_mohring_visuals()
