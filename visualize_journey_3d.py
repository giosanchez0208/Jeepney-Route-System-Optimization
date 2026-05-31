import os
import sys
import random
from PIL import Image

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
from utils.route import RouteGenerator
from utils.travel_graph import TravelGraph
import utils.travel_graph_3d_vis as vis
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

def mock_data_generator():
    pass

def draw_base_city(ax, tg, layer, layer_gap, center_lon, center_lat, edge_thickness):
    base_segments = []
    # Layer 1 and 3: all edges. Layer 2: arterials only (is_drivable == True)
    for e in tg.cg.graph:
        if layer == 2 and not e.is_drivable:
            continue
            
        start = vis._project_point(e.start.lon, e.start.lat, layer, layer_gap, center_lon, center_lat)
        end = vis._project_point(e.end.lon, e.end.lat, layer, layer_gap, center_lon, center_lat)
        base_segments.append((start, end))

    if base_segments:
        ax.add_collection(
            LineCollection(
                base_segments,
                colors='#D3D3D3', # Light gray
                linewidths=max(edge_thickness * 0.4, 0.5),
                alpha=0.35,
                zorder=layer * 3 + 0.1,
                capstyle='round',
                joinstyle='round'
            )
        )

def make_route_system_draw(tg):
    def custom_draw(ax, edges, layer, layer_gap, center_lon, center_lat, edge_thickness):
        draw_base_city(ax, tg, layer, layer_gap, center_lon, center_lat, edge_thickness)
        
        # Now draw the colored routes on Layer 2
        if layer == 2:
            route_segments = []
            route_colors = []
            r_colors = ["#E63946", "#1D3557", "#2A9D8F"]
            
            for edge in tg.travel_graph:
                if edge.id.startswith("RI"):
                    start = vis._project_point(edge.start.lon, edge.start.lat, layer, layer_gap, center_lon, center_lat)
                    end = vis._project_point(edge.end.lon, edge.end.lat, layer, layer_gap, center_lon, center_lat)
                    parts = edge.id.split("_")
                    r_idx = int(parts[1][1:])
                    color = r_colors[r_idx % len(r_colors)]
                    route_segments.append((start, end))
                    route_colors.append(color)

            if route_segments:
                ax.add_collection(
                    LineCollection(
                        route_segments,
                        colors=route_colors,
                        linewidths=edge_thickness * 1.8,
                        alpha=0.9,
                        zorder=layer * 3 + 1.0,
                        capstyle='round',
                        joinstyle='round'
                    )
                )
    return custom_draw

def make_journey_city_draw(tg):
    def custom_draw(ax, edges, layer, layer_gap, center_lon, center_lat, edge_thickness):
        draw_base_city(ax, tg, layer, layer_gap, center_lon, center_lat, edge_thickness)
    return custom_draw

def custom_draw_journey(
    ax, journey, flags, layer_gap, center_lon, center_lat, journey_thickness, labels_on,
):
    if not journey:
        return

    grouped_paths = []
    current_prefix = None
    current_path = []
    
    for edge in journey:
        prefix = edge.id[:2]
        if not flags.get(prefix, False):
            continue
        if edge.start.layer not in vis._LAYERS or edge.end.layer not in vis._LAYERS:
            continue

        start_pt = vis._project_point(edge.start.lon, edge.start.lat, edge.start.layer, layer_gap, center_lon, center_lat)
        end_pt = vis._project_point(edge.end.lon, edge.end.lat, edge.end.layer, layer_gap, center_lon, center_lat)
        
        if prefix == current_prefix:
            current_path.append(end_pt)
        else:
            if current_path:
                grouped_paths.append((current_prefix, current_path))
            current_prefix = prefix
            if grouped_paths:
                last_pt = grouped_paths[-1][1][-1]
                if abs(start_pt[0] - last_pt[0]) < 1e-6 and abs(start_pt[1] - last_pt[1]) < 1e-6:
                    current_path = [last_pt, end_pt]
                else:
                    current_path = [start_pt, end_pt]
            else:
                current_path = [start_pt, end_pt]

    if current_path:
        grouped_paths.append((current_prefix, current_path))
        
    for prefix, path in grouped_paths:
        xs = [pt[0] for pt in path]
        ys = [pt[1] for pt in path]
        color = vis._TYPE_COLORS.get(prefix, "#FF1744")
        
        ax.plot(
            xs, ys,
            color=color,
            linewidth=journey_thickness,
            solid_capstyle='round',
            solid_joinstyle='round',
            zorder=40
        )

def make_route_system_legend():
    def custom_draw_legend(ax, mode):
        r_colors = ["#E63946", "#1D3557", "#2A9D8F"]
        legend_items = [
            (r_colors[0], "Route 0"),
            (r_colors[1], "Route 1"),
        ]
        handles = [Line2D([0], [0], color=color, linewidth=3, linestyle="solid", label=label) for color, label in legend_items]
        
        legend = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=True, framealpha=0.9, facecolor="#FFFFFF", edgecolor="#CCCCCC", fontsize=10)
        for text in legend.get_texts(): text.set_color("#111111")
    return custom_draw_legend

def custom_draw_legend_journey(ax, mode):
    legend_items = [
        (vis._TYPE_COLORS["SW"], "Start Walk (SW)"),
        (vis._TYPE_COLORS["WA"], "Wait (WA)"),
        (vis._TYPE_COLORS["RI"], "Ride (RI)"),
        (vis._TYPE_COLORS["AL"], "Alight (AL)"),
        (vis._TYPE_COLORS["EW"], "End Walk (EW)"),
        (vis._TYPE_COLORS["TR"], "Transfer (TR)"),
    ]
    handles = [Line2D([0], [0], color=color, linewidth=3.5, linestyle="solid", label=label) for color, label in legend_items]
    
    legend = ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=True, framealpha=0.9, facecolor="#FFFFFF", edgecolor="#CCCCCC", fontsize=10)
    for text in legend.get_texts(): text.set_color("#111111")

def get_collapsed_signature(journey):
    if not journey: return []
    sig = [journey[0].id[:2]]
    for e in journey[1:]:
        prefix = e.id[:2]
        if prefix != sig[-1]:
            sig.append(prefix)
    return sig

def generate_visuals():
    print("Instantiating CityGraph...")
    bbox = (8.1500, 8.3300, 124.1500, 124.4000)
    city = CityGraph(name="Iligan City", bbox=bbox, pbf_path="utils/data/iligan-city.pbf", cache_prefix="iligan_arterial", verbose=True)
    
    config = DDMConfig()
    sampler = DirectDemandSampler(city, config=config, verbose=True)
    rg = RouteGenerator(city, sampler, verbose=True)

    print("Generating 2 NON-INTERSECTING transit loops...")
    routes = []
    routes.append(rg.generate(n_points=5))
    
    while len(routes) < 2:
        r = rg.generate(n_points=5)
        # Check intersection
        r0_nodes = {e.start for e in routes[0].path}
        r1_nodes = {e.start for e in r.path}
        if not r0_nodes.intersection(r1_nodes):
            routes.append(r)
        
    updated_weights = {'walk_wt': 0.5630, 'ride_wt': 0.00632, 'wait_wt': 14.44, 'transfer_wt': 15.78, 'direct_wt': 0.0, 'alight_wt': 0.0}
    
    print("Building TravelGraph...")
    travel_graph = TravelGraph(cg=city, config=updated_weights, routes=routes)
    
    # We do NOT need to force EW between AL and TR anymore because they don't intersect!
    
    print("Simulating journey to find exact signature: ['SW', 'WA', 'RI', 'AL', 'EW', 'TR', 'RI', 'AL', 'EW']...", flush=True)
    
    l1_nodes_list = list(travel_graph.l1_nodes.values())
    l3_nodes_list = list(travel_graph.l3_nodes.values())
    
    best_journey = None
    target_sig = ['SW', 'WA', 'RI', 'AL', 'EW', 'TR', 'RI', 'AL', 'EW']
    
    attempts = 0
    while True:
        attempts += 1
        start = random.choice(l1_nodes_list)
        end = random.choice(l3_nodes_list)
        
        journey = travel_graph.findShortestJourney(start, end)
        if not journey: continue
        
        sig = get_collapsed_signature(journey)
        if sig == target_sig:
            best_journey = journey
            break
            
        if attempts % 50 == 0:
            print(f"Searched {attempts} OD pairs... signature was {sig}", flush=True)

    print(f"Found EXACT journey signature! Length: {len(best_journey)} edges. Signature: {target_sig}", flush=True)
    
    vis._RENDER_DPI = 400
    vis._LIGHT_FACE_COLOR = "#FFFFFF"
    
    print("Rendering Route System Image...")
    vis._draw_city_graph_edges = make_route_system_draw(travel_graph)
    vis._draw_journey = lambda *args, **kwargs: None
    vis._draw_legend = make_route_system_legend()
    
    visualizer1 = vis.TravelGraph3DVisualizer(travel_graph, journey=[], mode="light", edge_thickness=1.5, layer_opacity=0.4)
    img_routes = visualizer1.draw(nodes_on=False)
    
    print("Rendering Passenger Journey Image...")
    vis._TYPE_COLORS = {"SW": "#4CAF50", "WA": "#FF9800", "RI": "#2196F3", "AL": "#E91E63", "TR": "#9C27B0", "EW": "#F44336", "DI": "#607D8B"}
    
    vis._draw_city_graph_edges = make_journey_city_draw(travel_graph)
    vis._draw_journey = custom_draw_journey
    vis._draw_legend = custom_draw_legend_journey
    
    visualizer2 = vis.TravelGraph3DVisualizer(travel_graph, journey=best_journey, mode="light", journey_thickness=2.5, layer_opacity=0.3)
    img_journey = visualizer2.draw(nodes_on=False)
    
    print("Combining images side-by-side...")
    total_width = img_routes.width + img_journey.width
    max_height = max(img_routes.height, img_journey.height)
    
    combined = Image.new("RGBA", (total_width, max_height), "#FFFFFF")
    combined.paste(img_routes, (0, (max_height - img_routes.height) // 2))
    combined.paste(img_journey, (img_routes.width, (max_height - img_journey.height) // 2))
    
    out_dir = "documentation/phase_2"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fig_4b_passenger_journey_3d.png")
    
    combined.save(out_path)
    print(f"Saved combined visualization to {out_path}!")

if __name__ == "__main__":
    generate_visuals()
