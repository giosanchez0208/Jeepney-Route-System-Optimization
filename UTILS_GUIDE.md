# Jeepney System Utils Guide

This guide provides a detailed technical overview of the utility modules in the Jeepney Route System Optimization repository. It defines class interfaces, data standards, and operational patterns to enable autonomous interaction with the codebase.

---

## 1. Global Standards and Units

- **Coordinates**: Always a tuple of `(longitude, latitude)` as `float`.
- **Distance**: Meters (m), calculated via Haversine formula.
- **Speed**: Kilometers per hour (km/h) in configurations; internally processed as meters per tick.
- **Time**: One simulation tick represents 1 second.
- **Layers**:
    - **Layer 1**: Pedestrian level (walking, origins).
    - **Layer 2**: Transit level (jeepney routes, riding).
    - **Layer 3**: Destination level (alighting, transfers).
- **Coordinate Ordering**: Strict adherence to `(lon, lat)` is required. Swapping these will result in calculation errors.

---

## 2. Core Spatial Utilities

### node.py

#### Node
The atomic spatial unit used throughout the system.

- **Attributes**
  - `id` (str): Unique string identifier, defaults to f"N{uuid.uuid4().hex}".
  - `lon` (float): Longitude geographical coordinate.
  - `lat` (float): Latitude geographical coordinate.
  - `layer` (int): Spatial layer identifier (0 to 3).

- **Methods**
  - `__init__(self, lon: float, lat: float, layer: Optional[int] = None) -> None`
    - Parameters:
      - `lon` (float): Geographical longitude.
      - `lat` (float): Geographical latitude.
      - `layer` (Optional[int]): Layer level, defaults to None.
    - Outputs: None.
    - Primary Purpose: Instantiates a spatial Node, validating coordinate ranges and layer values.
  - `_validate_lon(self, lon: float) -> float`
    - Parameters:
      - `lon` (float): Longitude value to validate.
    - Outputs: float (validated longitude).
    - Primary Purpose: Internal checker verifying longitude is a valid number within [-180, 180].
  - `_validate_lat(self, lat: float) -> float`
    - Parameters:
      - `lat` (float): Latitude value to validate.
    - Outputs: float (validated latitude).
    - Primary Purpose: Internal checker verifying latitude is a valid number within [-90, 90].
  - `_validate_layer(self, layer: Optional[int]) -> Optional[int]`
    - Parameters:
      - `layer` (Optional[int]): Layer value to validate.
    - Outputs: Optional[int] (validated layer index).
    - Primary Purpose: Internal checker verifying layer is either None or an integer within [0, 3].
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns a coordinate representation string: "(lon, lat)".
  - `__repr__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns a detailed representation string including coordinates and layer.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, color: str = "red", radius: int = 5) -> PIL.Image.Image`
    - Parameters:
      - `context` (tuple): Spatial boundaries defined as `((min_lon, max_lat), (max_lon, min_lat))`.
      - `image` (PIL.Image.Image): Base square canvas to render on.
      - `color` (str): Circle fill color, defaults to "red".
      - `radius` (int): Radius in pixels, defaults to 5.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Draws a solid colored circle representing the node onto a square PIL image context.

---

### directed_edge.py

- **Top-Level Helper Functions**
  - `_nodes_match(n1: Node, n2: Node) -> bool`
    - Parameters:
      - `n1` (Node): First node.
      - `n2` (Node): Second node.
    - Outputs: bool.
    - Primary Purpose: Checks if two Node objects share identical coordinates and layer values.
  - `_getDistance(n1: Node, n2: Node) -> float`
    - Parameters:
      - `n1` (Node): Origin node.
      - `n2` (Node): Destination node.
    - Outputs: float.
    - Primary Purpose: Calculates geographical distance in meters between two Nodes using the Haversine formula.
  - `_connect(e1: DirEdge, e2: DirEdge) -> None`
    - Parameters:
      - `e1` (DirEdge): First edge.
      - `e2` (DirEdge): Second edge.
    - Outputs: None.
    - Primary Purpose: Appends `e2` to the outgoing `next_edges` list of `e1` if their coordinates connect.
  - `_stitch(edges_from: list[DirEdge], edges_to: list[DirEdge]) -> None`
    - Parameters:
      - `edges_from` (list[DirEdge]): Source edge list.
      - `edges_to` (list[DirEdge]): Target edge list.
    - Outputs: None.
    - Primary Purpose: Connects disjoint edges between two lists using a fast O(1) hash coordinate lookup `(lon, lat, layer) -> edges`.

#### DirEdge
A directed link representing a physical or logical step between two nodes.

- **Attributes**
  - `start` (Node): Start node of the directed edge.
  - `end` (Node): End node of the directed edge.
  - `is_drivable` (bool): True if vehicles can navigate this edge.
  - `weight` (float): Cost weight, defaults to computed distance.
  - `id` (str): Unique string identifier.
  - `next_edges` (list[DirEdge]): References to connected outgoing edges.
  - `_edge_type` (int): Bitwise or integer edge type constant (e.g. EDGE_RI, EDGE_WA).
  - `_length` (float): Pre-computed Haversine length in meters.

- **Methods**
  - `__init__(self, start: Node, end: Node, is_drivable: bool = False, weight: Optional[float] = None, id: Optional[str] = None, next_edges: Optional[list[DirEdge]] = None, type: Optional[str] = None) -> None`
    - Parameters:
      - `start` (Node): Origin node.
      - `end` (Node): Destination node.
      - `is_drivable` (bool): Navigability flag, defaults to False.
      - `weight` (Optional[float]): Travel cost, defaults to distance.
      - `id` (Optional[str]): Custom identifier, defaults to UUID.
      - `next_edges` (Optional[list[DirEdge]]): Outgoing edges.
      - `type` (Optional[str]): Semantic type classification.
    - Outputs: None.
    - Primary Purpose: Instantiates a directed edge, pre-computing its Haversine length and setting up connectivity.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns basic information string showing edge terminal node IDs.
  - `__repr__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns detailed debug string representation.
  - `getLength(self) -> float`
    - Parameters: None.
    - Outputs: float.
    - Primary Purpose: Returns the pre-computed Haversine distance in meters.
  - `isConnectedTo(self, other: DirEdge) -> bool`
    - Parameters:
      - `other` (DirEdge): The edge to test.
    - Outputs: bool.
    - Primary Purpose: Checks if this edge connects to the start node of another edge by coordinate matching.
  - `getType(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Evaluates transition layers and returns a semantic string ("walk", "wait", "ride", "alight", "transfer", "direct").
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, color: str = "black", width: int = 2) -> PIL.Image.Image`
    - Parameters:
      - `context` (tuple): Spatial boundaries defined as `((min_lon, max_lat), (max_lon, min_lat))`.
      - `image` (PIL.Image.Image): Canvas to render on.
      - `color` (str): Line drawing color, defaults to "black".
      - `width` (int): Width in pixels, defaults to 2.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Draws a line representing the edge onto the square PIL canvas context.

---

### city_graph.py

#### CityGraph
Manages the physical road network skeleton, typically pruned to arterial corridors.

- **Attributes**
  - `name` (str): Urban network identifier name.
  - `nodes` (list[Node]): List of physical street nodes.
  - `graph` (list[DirEdge]): Street directed edges.
  - `landmarks` (dict): Custom landmarks coordinates.
  - `_node_map` (dict): Map of spatial coordinates `(lon, lat)` to Node objects.

- **Methods**
  - `__init__(self, bbox: Optional[tuple[float, float, float, float]] = None, name: str = "UrbanNetwork", landmarks: Optional[dict] = None, pbf_path: Optional[str] = None, use_api: bool = False, verbose: bool = False, cache_dir: str = ".cache", cache_prefix: str = "graph") -> None`
    - Parameters:
      - `bbox` (Optional[tuple]): `(min_lon, min_lat, max_lon, max_lat)` coordinates.
      - `name` (str): City graph name.
      - `landmarks` (Optional[dict]): Map landmarks coordinates.
      - `pbf_path` (Optional[str]): Path to OpenStreetMap PBF network file.
      - `use_api` (bool): API fetching toggle, defaults to False.
      - `verbose` (bool): Output details, defaults to False.
      - `cache_dir` (str): Storage path, defaults to ".cache".
      - `cache_prefix` (str): Cache prefix name.
    - Outputs: None.
    - Primary Purpose: Loads or generates physical city networks, resolving topologies and caching results.
  - `_load_road_graph(self, bbox: tuple[float, float, float, float], pbf_path: Optional[str], use_api: bool) -> None`
    - Parameters:
      - `bbox` (tuple): Coordinates boundary box.
      - `pbf_path` (Optional[str]): OSM file path.
      - `use_api` (bool): API loader query toggle.
    - Outputs: None.
    - Primary Purpose: Internal loader utilizing Overpass APIs or local PBF files to construct the road graph.
  - `stitch_graph(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Establishes street intersections and outgoing links on all Layer 1 edge paths.
  - `inject_toy_data(self, nodes: list[Node], edges: list[DirEdge]) -> None`
    - Parameters:
      - `nodes` (list[Node]): Grid nodes.
      - `edges` (list[DirEdge]): Bidirectional grid edges.
    - Outputs: None.
    - Primary Purpose: Replaces OSM datasets with synthetic data for fast testing.
  - `find_shortest_path(self, start: Node, end: Node) -> list[DirEdge]`
    - Parameters:
      - `start` (Node): Origin node.
      - `end` (Node): Destination node.
    - Outputs: list[DirEdge].
    - Primary Purpose: Standard A* pathfinder finding the optimal street route between two physical nodes.
  - `get_bounds(self, margin: float = 0.05) -> tuple[tuple[float, float], tuple[float, float]]`
    - Parameters:
      - `margin` (float): Percent padding around boundaries, defaults to 0.05.
    - Outputs: tuple of tuples: `((min_lon, max_lat), (max_lon, min_lat))`.
    - Primary Purpose: Computes spatial context extents suitable for visualization.
  - `draw(self, size: int = 800, only_drivable: bool = False) -> PIL.Image.Image`
    - Parameters:
      - `size` (int): Width/height, defaults to 800.
      - `only_drivable` (bool): Filter edges, defaults to False.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Generates a square static PIL image rendering the physical street map skeleton.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns formatted overview string containing name, nodes, and edges counts.

---

### travel_graph.py

#### TravelGraph
A multi-layered graph (L1, L2, L3) that enables complex journey planning involving walking, waiting, riding, and transfers.

- **Attributes**
  - `cg` (CityGraph): Underlying physical road network graph.
  - `walk_wt` (float): Pedestrian distance cost factor.
  - `ride_wt` (float): Vehicle distance cost factor.
  - `wait_wt` (float): Boarding time penalty cost factor.
  - `transfer_wt` (float): Route transfer penalty cost factor.
  - `routes` (list[Route]): Deployed transit routes on Layer 2.
  - `l1_nodes` (dict): Mapping coordinates to Layer 1 nodes.
  - `l3_nodes` (dict): Mapping coordinates to Layer 3 nodes.
  - `travel_graph` (list[DirEdge]): Complete list of multi-layered travel graph edges.
  - `_outgoing_edges` (dict): Maps Node to outgoing travel edges.

- **Methods**
  - `__init__(self, cg: CityGraph, config: dict, routes: Optional[list[Route]] = None, route_generator: Optional[RouteGenerator] = None, n_routes: int = 5, n_points: int = 4) -> None`
    - Parameters:
      - `cg` (CityGraph): Physical street graph.
      - `config` (dict): Configuration dictionary containing weight factors.
      - `routes` (Optional[list[Route]]): Pre-computed route list.
      - `route_generator` (Optional[RouteGenerator]): Generator fallback.
      - `n_routes` (int): Target count if using fallback.
      - `n_points` (int): Route waypoint count if using fallback.
    - Outputs: None.
    - Primary Purpose: Instantiates the multi-layered travel graph, mapping layers, generating routes if missing, and constructing transition links.
  - `_generate_routes(self, route_generator: RouteGenerator, n_routes: int, n_points: int) -> list[Route]`
    - Parameters:
      - `route_generator` (RouteGenerator): Generator tool.
      - `n_routes` (int): Target count.
      - `n_points` (int): Target waypoints.
    - Outputs: list[Route].
    - Primary Purpose: Internal fallback to construct routes if not explicitly provided.
  - `_construct(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Multi-layered assembly logic: duplicates nodes across Layer 1 and Layer 3, copies Layer 2 routes, creates wait/alight/transfer edges, and stitches everything strictly.
  - `_snap_node(self, target: Node, layer: int) -> Node`
    - Parameters:
      - `target` (Node): The node coordinates to snap.
      - `layer` (int): Target snapping layer (1 or 3).
    - Outputs: Node.
    - Primary Purpose: Uses spatial KDTree query lookups to snap any coordinate node to the nearest Layer 1 or Layer 3 node.
  - `findShortestJourney(self, start: Node, end: Node) -> list[DirEdge]`
    - Parameters:
      - `start` (Node): Spatial origin node.
      - `end` (Node): Spatial destination node.
    - Outputs: list[DirEdge].
    - Primary Purpose: Executes A* search on the multi-layered graph to find the complete optimal journey (walking, waiting, riding, alighting).
  - `_reconstruct_path(self, came_from: dict, start: Node, end: Node) -> list[DirEdge]`
    - Parameters:
      - `came_from` (dict): Back-pointer came_from trace.
      - `start` (Node): Origin.
      - `end` (Node): Destination.
    - Outputs: list[DirEdge].
    - Primary Purpose: Backtracks along solved links to yield the chronological journey edge sequence.
  - `calculateJourneyDistance(self, start: Node, end: Node) -> float`
    - Parameters:
      - `start` (Node): Spatial origin.
      - `end` (Node): Spatial destination.
    - Outputs: float.
    - Primary Purpose: Computes total geographical distance in meters along walk, ride, and end-walk edges.
  - `calculateJourneyWeight(self, start: Node, end: Node) -> float`
    - Parameters:
      - `start` (Node): Spatial origin.
      - `end` (Node): Spatial destination.
    - Outputs: float.
    - Primary Purpose: Returns total path weight along the multi-layered shortest path using A* search.
  - `draw(self, context: tuple, image: PIL.Image.Image, display_walk: bool = False, display_wait: bool = False, display_ride: bool = False, display_alight: bool = False, display_end_walk: bool = False, display_transfer: bool = False, display_direct: bool = False, journey: Optional[list[DirEdge]] = None) -> PIL.Image.Image`
    - Parameters:
      - `context` (tuple): Spatial boundaries coordinates.
      - `image` (PIL.Image.Image): Base map image to draw on.
      - `display_...` (bool): Toggles for rendering different edge types.
      - `journey` (Optional[list[DirEdge]]): Solved path overlay.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Generates a 2D square image mapping the travel graph's layers and paths.
  - `create_3d(self, journey: Optional[list[DirEdge]] = None, display_walk: bool = True, display_wait: bool = True, display_ride: bool = True, display_alight: bool = True, display_end_walk: bool = True, display_transfer: bool = True, display_direct: bool = True, labels_on: bool = False, legend_on: bool = True, nodes_on: bool = False) -> PIL.Image.Image`
    - Parameters:
      - `journey` (Optional[list[DirEdge]]): Solved path overlay.
      - `display_...` (bool): Toggles for rendering.
      - `labels_on` (bool): Annotations flag.
      - `legend_on` (bool): Map legend flag.
      - `nodes_on` (bool): Scatter nodes flag.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Visualizes the multi-layered graph as an isometric 3D canvas rendering using Matplotlib.

---

### travel_graph_3d_vis.py

- **Top-Level Helper Functions**
  - `_project_point(lon: float, lat: float, layer: int, layer_gap: float, center_lon: float, center_lat: float) -> tuple[float, float]`
    - Parameters:
      - `lon`, `lat` (float): Coordinates.
      - `layer` (int): Node layer.
      - `layer_gap` (float): Vertical separation scale.
      - `center_lon`, `center_lat` (float): Centroid coordinates.
    - Outputs: tuple of `(x, y)` projected coordinates.
    - Primary Purpose: Projects geo-coordinates and layers into 2D isometric screen space.
  - `_layer_gap(nodes: list[Node]) -> float`
    - Parameters:
      - `nodes` (list[Node]): Reference nodes.
    - Outputs: float.
    - Primary Purpose: Computes vertical separation height proportional to geographical coordinate spans.
  - `_projection_origin(nodes: list[Node]) -> tuple[float, float]`
    - Parameters:
      - `nodes` (list[Node]): Reference nodes.
    - Outputs: tuple of `(lon, lat)`.
    - Primary Purpose: Evaluates geographical centroid coordinates of nodes.
  - `_collect_points(nodes, edges, journey, layer_gap, center_lon, center_lat) -> list[tuple[float, float]]`
    - Parameters: Coordinates and configuration values.
    - Outputs: list of tuples.
    - Primary Purpose: Aggregates all projected point vertices to format bounding boxes.
  - `_build_figure(points: list[tuple[float, float]]) -> tuple[plt.Figure, plt.Axes]`
    - Parameters:
      - `points` (list): Projected coordinates.
    - Outputs: tuple of Matplotlib Figure and Axes.
    - Primary Purpose: Sets up DPI, proportions, and aspect ratios of the drawing canvas.
  - `_layer_border(nodes, layer, layer_gap, center_lon, center_lat) -> list[tuple[float, float]]`
    - Parameters: Coordinates and layout bounds.
    - Outputs: list of tuples.
    - Primary Purpose: Returns the projected four corners of a transparent layer plane polygon.
  - `_draw_layer_plane(...) -> None`
    - Primary Purpose: Renders the colored polygon borders representing layer planes.
  - `_draw_city_graph_edges(...) -> None`
    - Primary Purpose: Renders background street segments transparently on each layer.
  - `_draw_journey(...) -> None`
    - Primary Purpose: Highlights color-coded segments representing active journeys.
  - `_draw_legend(ax: plt.Axes, mode: MapMode) -> None`
    - Primary Purpose: Renders a clean structured legend box on the plot.
  - `_render_to_image(fig: plt.Figure) -> PIL.Image.Image`
    - Parameters:
      - `fig` (plt.Figure): Complete Matplotlib plot figure.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Converts the Matplotlib figure into a square PIL RGBA image.

#### TravelGraph3DVisualizer
Visualizes multi-layered travel graphs as high-contrast isometric 3D canvas projections.

- **Attributes**
  - `tg` (TravelGraph): Travel graph network coordinates.
  - `journey` (list[DirEdge]): Active passenger trip edges.
  - `mode` (MapMode): Style selector ("light", "dark", etc.).
  - `edge_thickness` (float): Background line width.
  - `journey_thickness` (float): Journey line width.
  - `node_radius` (float): Coordinate scatter dot size.
  - `layer_opacity` (float): Opacity of plane border lines.

- **Methods**
  - `__init__(self, travel_graph: TravelGraph, journey: Optional[list[DirEdge]] = None, *, mode: MapMode = "light_nolabels", edge_thickness: float = 2.6, journey_thickness: float = 4.2, node_radius: float = 42, layer_opacity: float = 0.56) -> None`
    - Parameters: Visual configurations and object references.
    - Outputs: None.
    - Primary Purpose: Instantiates the visualizer with the specified drawing configurations.
  - `draw(self, *, display_walk: bool = True, display_wait: bool = True, display_ride: bool = True, display_alight: bool = True, display_end_walk: bool = True, display_transfer: bool = True, display_direct: bool = True, labels_on: bool = False, legend_on: bool = True, nodes_on: bool = False, mode: Optional[MapMode] = None, edge_thickness: Optional[float] = None, journey_thickness: Optional[float] = None, node_radius: Optional[float] = None, layer_opacity: Optional[float] = None) -> PIL.Image.Image`
    - Parameters: Visual drawing and toggling arguments.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Renders the multi-layered 3D network, snaps coordinates, adds indicators, and outputs a square PIL canvas.

---

## 3. Transit and Simulation Actors

### route.py

- **Top-Level Helper Functions**
  - `generate_color() -> str`
    - Parameters: None.
    - Outputs: str (hex code).
    - Primary Purpose: Generates high-saturation, mid-lightness colors suitable for transit lines.
  - `route_from_coords(city_graph: CityGraph, coords_json: str) -> Route`
    - Parameters:
      - `city_graph` (CityGraph): Road network.
      - `coords_json` (str): Coordinate list in JSON format.
    - Outputs: Route.
    - Primary Purpose: Snaps coordinates to nodes using KDTree queries, matches paths via A*, and returns a Layer 2 Route.

#### Route
A closed-loop transit line operating on Layer 2.

- **Attributes**
  - `cg` (CityGraph): Base physical network.
  - `path` (list[DirEdge]): Continuous sequence of directed L2 edges forming a loop.
  - `id` (str): Unique route identifier.
  - `designated_color` (str): Assigned color hex string.

- **Methods**
  - `__init__(self, city_graph: CityGraph, path: list[DirEdge], id: Optional[str] = None) -> None`
    - Parameters:
      - `city_graph` (CityGraph): Road skeleton.
      - `path` (list[DirEdge]): L2 edge loop sequence.
      - `id` (Optional[str]): Route ID.
    - Outputs: None.
    - Primary Purpose: Instantiates a Layer 2 transit line, validating looping and connectivity attributes.
  - `_validate_loop(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Verifies the path loops correctly and the end node of each edge matches the start node of the next.
  - `_validate_layer(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Asserts every edge in the route belongs strictly to Layer 2.
  - `_validate_branching(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Asserts every edge has exactly one Layer 2 out-pointer in `next_edges`.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, color: Optional[str] = None, width: int = 3) -> PIL.Image.Image`
    - Parameters: Bounds context, image canvas, color override, line width.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Draws the route path line on the PIL canvas using either its designated or override color.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns structured route status text.

#### RouteGenerator
Automates the creation of transit lines based on demand sampling.

- **Attributes**
  - `cg` (CityGraph): Street network.
  - `sampler` (DirectDemandSampler): Demand sampling matrix.
  - `verbose` (bool): Prints setup details.

- **Methods**
  - `__init__(self, city_graph: CityGraph, sampler: DirectDemandSampler, verbose: bool = False) -> None`
    - Parameters: Graph, sampler, and verbose mode.
    - Outputs: None.
    - Primary Purpose: Instantiates the route generation engine.
  - `generate(self, n_points: int = 4, max_retries: int = 10) -> Route`
    - Parameters:
      - `n_points` (int): Count of demand-sampled waypoints, defaults to 4.
      - `max_retries` (int): Limit before failing, defaults to 10.
    - Outputs: Route.
    - Primary Purpose: Creates a valid transit loop by sampling waypoints, finding A* paths between them, promoting edges to L2, and establishing next-pointers.
  - `_promote_to_route(self, base_path: list[DirEdge]) -> Route`
    - Parameters:
      - `base_path` (list[DirEdge]): Physical street edges.
    - Outputs: Route.
    - Primary Purpose: Internal helper copying edges, setting their layer to 2, and wiring circular next_edges pointers.

#### RouteSystem
A container for multiple routes, primarily used for visualization.

- **Attributes**
  - `routes` (list[Route]): List of stored routes.

- **Methods**
  - `__init__(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Instantiates an empty route system container.
  - `add_route(self, route: Route) -> None`
    - Parameters:
      - `route` (Route): Transit line to append.
    - Outputs: None.
    - Primary Purpose: Appends a Route object to the container.
  - `_get_screen_coords(self, node: Node, context: tuple, width: int, height: int) -> tuple[float, float]`
    - Parameters: Node, bounds context, and canvas dimensions.
    - Outputs: tuple of `(x, y)` pixels.
    - Primary Purpose: Transforms geographical coordinates to screen pixels.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, line_width: int = 6, dash_length: int = 15) -> PIL.Image.Image`
    - Parameters: Bounds context, canvas, line width, dash spacing.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Draws all routes on a square PIL canvas, rendering shared corridors as alternating dashed lines.

---

### jeep.py

#### Jeep
A vehicle actor following a specific Route.

- **Attributes**
  - `id` (str): Unique jeepney ID.
  - `route` (Route): The Route the vehicle follows.
  - `speed_kmph` (float): Configured speed in km/h.
  - `curr_pos` (tuple): Current `(lon, lat)` coordinate position.
  - `designated_color` (str): Visual route color hex code.
  - `curr_nodes_passed` (Optional[list[tuple[Node, Route]]]): Traversed nodes.
  - `heading` (float): Vector compass angle in degrees.
  - `passenger_max` (int): Seat capacity limit, defaults to 16.
  - `curr_passenger_count` (int): Number of onboard passengers.
  - `seconds_per_tick` (int): Simulation tick multiplier.
  - `onboard_passengers` (set[Passenger]): Set of active riding passengers.
  - `_edge_idx` (int): Current index of the edge in the route.
  - `_edge_progress` (float): Distance traveled on the current edge in meters.
  - `_route_weight_cache` (dict): Cache mapping start/end nodes to pre-computed weights.

- **Methods**
  - `__init__(self, route: Route, curr_pos: tuple[float, float], speed: float, max_capacity: int = 16, seconds_per_tick: int = 1) -> None`
    - Parameters: Route, start coordinate, speed, capacity, seconds per tick.
    - Outputs: None.
    - Primary Purpose: Instantiates a Jeep vehicle, pre-computes route path weights into `_route_weight_cache` for O(1) weight lookups, snaps to route, and sets heading.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns vehicle state summary.
  - `_snap_to_route(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Snaps the vehicle's position to the nearest route node to ensure coordinate alignment.
  - `_update_heading(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Computes the orientation angle of the current route edge to update the heading.
  - `update(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Moves the vehicle along its route path based on speed, tracking which nodes are passed.
  - `nodes_passed_this_frame(self, format_as_str: bool = False) -> Optional[list[tuple[Node, Route]]]`
    - Parameters:
      - `format_as_str` (bool): Return strings instead of objects.
    - Outputs: Optional list of tuples or string items.
    - Primary Purpose: Returns the nodes traversed in the current time step.
  - `modify_passenger(self, amt: int) -> None`
    - Parameters:
      - `amt` (int): Increment/decrement value.
    - Outputs: None.
    - Primary Purpose: Adjusts the passenger count by `amt` while clamping the value between 0 and `max_capacity`.
  - `return_path_from(self, start_node: Node, end_node: Node) -> list[DirEdge]`
    - Parameters: Start and end route nodes.
    - Outputs: list[DirEdge].
    - Primary Purpose: Returns the sequence of directed edges along the route between two nodes.
  - `get_weight_if(self, start_node: Node, end_node: Node) -> Optional[float]`
    - Parameters: Start and end route nodes.
    - Outputs: Optional[float] weight cost.
    - Primary Purpose: Looks up the travel weight cost between two nodes in O(1) time using `_route_weight_cache`.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, radius: int = 12) -> PIL.Image.Image`
    - Parameters: Bounds context, image canvas, shape size.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Renders the jeep as a directional triangle and passenger load text overlay onto a square PIL image.

---

### jeep_system.py

#### FleetAllocator
Calculates optimal vehicle distribution across routes using Mohring's square root rule.

- **Attributes**
  - `_edge_length_cache` (dict): Cache for edge lengths.
  - `_route_length_cache` (dict): Cache for total route lengths.

- **Methods**
  - `allocate_by_mohring(cls, total_fleet: int, routes: list[Route], sampler: DirectDemandSampler, tg: TravelGraph, mohring_sample_size: int = 2000) -> dict[Route, int]`
    - Parameters: Total fleet size, routes list, sampler, travel graph, and sample size.
    - Outputs: dict[Route, int] mapping routes to jeep counts.
    - Primary Purpose: Distributes fleet across routes based on Mohring's square root rule: stochastically samples journeys, counts route utilization, and scales/rounds counts (ensuring at least 1 jeep per route).
  - `evaluate_allocation(cls, allocation: dict[Route, int], sampler: DirectDemandSampler) -> dict[Route, dict[str, float]]`
    - Parameters: Allocation dictionary and sampler.
    - Outputs: dict of metrics.
    - Primary Purpose: Evaluates fleet distribution, generating metrics for route lengths, load factors, and headways.

#### JeepSystem
Coordinates the fleet, passenger boarding, and alighting logic.

- **Attributes**
  - `id` (str): Unique system identifier.
  - `jeeps` (list[Jeep]): Deployed jeep vehicles.
  - `routes` (list[Route]): Deployed transit routes.
  - `passengers` (list[Passenger]): Complete list of simulation passengers.
  - `active_passengers` (set[Passenger]): Set of currently active passengers.
  - `weight_tolerance` (float): Penalty buffer for boarding alternative lines.
  - `waiting_passengers` (dict): Map of coordinates to sets of waiting passengers.
  - `_waiting_coord_by_passenger` (dict): Lookup map of passengers to their current coordinates.
  - `_route_indices` (dict): Lookup map of route objects to indices.

- **Methods**
  - `__init__(self, jeeps: list[Jeep], routes: list[Route], weight_tolerance: float = 50.0, equidistant_spawn: bool = True) -> None`
    - Parameters: Jeeps, routes, tolerance, and spacing toggle.
    - Outputs: None.
    - Primary Purpose: Instantiates the coordination system, indexing routes and spacing vehicles evenly if selected.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns system status overview text.
  - `_space_jeeps_equidistantly(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Spreads vehicles on each route evenly along their total path length, snapping positions and updating headings.
  - `add_passenger(self, passenger: Passenger) -> None`
    - Parameters:
      - `passenger` (Passenger): Passenger to add.
    - Outputs: None.
    - Primary Purpose: Adds a passenger to the active simulation, registering them at waiting coordinates or onboarding them if riding.
  - `_register_waiting_passenger(self, passenger: Passenger) -> None`
    - Parameters:
      - `passenger` (Passenger): The waiting passenger.
    - Outputs: None.
    - Primary Purpose: Internal helper adding a passenger to the spatial coordinate waiting map.
  - `_unregister_waiting_passenger(self, passenger: Passenger, coord: Optional[tuple[float, float]] = None) -> None`
    - Parameters: Passenger and target coordinates.
    - Outputs: None.
    - Primary Purpose: Internal helper removing a passenger from the coordinate waiting map.
  - `update(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Executes a single simulation step: updates passengers, moves vehicles, and processes passenger alighting and boarding.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, radius: int = 12) -> PIL.Image.Image`
    - Parameters: Bounds context, image canvas, marker size.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Draws all vehicles onto the provided square PIL image canvas.

---

### passenger.py

#### Passenger
A state-machine actor managing live coordinates, state transitions, ride planning, and remaining travel time.

- **Attributes**
  - `WALKING`, `WAITING`, `RIDING`, `DONE` (int): State constants.
  - `id` (str): Unique passenger ID.
  - `journey` (list[DirEdge]): Sequence of travel edges.
  - `speed_kmph` (float): Walking speed in km/h.
  - `seconds_per_tick` (int): Tick multiplier.
  - `state` (int): Active state constant.
  - `wait_ticks` (int): Duration spent waiting at stops.
  - `current_jeep` (Optional[Jeep]): Assigned vehicle if riding.
  - `spawn_tick` (int): Birth tick of passenger.
  - `despawn_tick` (Optional[int]): Death tick of passenger.
  - `total_path_cost` (float): Total expected cost of journey.
  - `_cost_prefix_sums` (list[float]): Pre-computed cost sums.
  - `_target_alight_nodes` (list[Node]): Pre-computed alighting nodes.
  - `_planned_ride_weights` (list[float]): Pre-computed travel weights.
  - `_target_route_indices` (list[int]): Pre-computed target route indices.

- **Methods**
  - `__init__(self, start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_time: int = 0, seconds_per_tick: int = 1) -> None`
    - Parameters: Start position, journey path, walking speed, spawn tick, seconds per tick.
    - Outputs: None.
    - Primary Purpose: Instantiates the passenger and pre-computes cost prefix sums, target alight nodes, planned ride weights, and target route indices for O(1) lookups.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns coordinate-state overview text.
  - `curr_lat(self) -> float`
    - Property returning latitude coordinate (jeep's latitude if riding).
  - `curr_lon(self) -> float`
    - Property returning longitude coordinate (jeep's longitude if riding).
  - `curr_lat(self, value: float) -> None`
    - Setter updating internal latitude coordinate.
  - `curr_lon(self, value: float) -> None`
    - Setter updating internal longitude coordinate.
  - `update(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Steps the passenger state machine forward, advancing through walking and waiting states.
  - `_walk(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Simulates foot-travel along pedestrian edges by incrementing progress.
  - `get_target_route_idx(self) -> Optional[int]`
    - Parameters: None.
    - Outputs: Optional[int].
    - Primary Purpose: Returns the index of the route the passenger is waiting for at the current step.
  - `get_target_alight_node(self) -> Optional[Node]`
    - Parameters: None.
    - Outputs: Optional[Node].
    - Primary Purpose: Returns the Node where the passenger must exit the vehicle.
  - `get_planned_ride_weight(self) -> float`
    - Parameters: None.
    - Outputs: float.
    - Primary Purpose: Returns the pre-computed weight expected for the current transit ride segment.
  - `complete_ride(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Advances index pointers past alighting or transfer edges when leaving a vehicle.
  - `get_remaining_time(self) -> float`
    - Parameters: None.
    - Outputs: float.
    - Primary Purpose: Returns remaining travel weight using pre-computed cost prefix sums.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, size: int = 4) -> PIL.Image.Image`
    - Parameters: Bounds context, image canvas, marker size.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Draws active, non-riding passengers as gray circles (waiting) or blue circles (walking) on a square PIL image context.

---

### passenger_generator.py

#### PassengerGenerator
Manages stochastic passenger spawning and lifecycle tracking.

- **Attributes**
  - `id` (str): Unique generator ID.
  - `tg` (TravelGraph): Travel graph network coordinates.
  - `sampler` (DirectDemandSampler): Demand sampling matrix.
  - `rate_per_hour` (float): Spawning rate per hour.
  - `stdev` (float): Spawning standard deviation.
  - `speed_kmh` (float): Walking speed in km/h.
  - `seconds_per_tick` (int): Tick multiplier.
  - `simulated_time` (int): Elapsed simulation time.
  - `total_spawned` (int): Total generated passengers count.
  - `passengers` (list[Passenger]): List of active simulation passengers.
  - `new_passengers_this_tick` (list[Passenger]): Passengers spawned in the current tick.
  - `archived_passengers` (list[Passenger]): Completed simulation passengers.
  - `tick_counter` (int): Elapsed simulation ticks.
  - `spawn_schedule` (list[int]): Spawning schedule for a 100-tick window.

- **Methods**
  - `__init__(self, tg: TravelGraph, sampler: DirectDemandSampler, rate_per_hour: float, stdev: float, speed: float = 5.0, seconds_per_tick: int = 1) -> None`
    - Parameters: TravelGraph, sampler, hourly spawn rate, standard deviation, walking speed, seconds per tick.
    - Outputs: None.
    - Primary Purpose: Instantiates the coordinator and builds the initial 100-tick spawn schedule.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns generator status overview text.
  - `_generate_schedule(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Internal scheduling logic: samples spawn counts using a Gaussian distribution and distributes spawns across a 100-tick window.
  - `update(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Advances the generation tick: samples Origin-Destination pairs, solves journey paths, spawns passengers, and archives completed ones.
  - `get_all_generated_journeys(self) -> list[list[DirEdge]]`
    - Parameters: None.
    - Outputs: list of journey edge lists.
    - Primary Purpose: Returns the planned route edge list for all active and archived passengers (used for depositing pheromones).

---

## 4. Demand Surface and Models

### direct_demand_sampler.py

- **Top-Level Helper Functions**
  - `_get_betweenness_centrality(cg: CityGraph) -> dict[Node, float]`
    - Parameters:
      - `cg` (CityGraph): Road network.
    - Outputs: dict mapping Node to centrality score.
    - Primary Purpose: Internal helper using NetworkX to calculate street node betweenness centrality.

#### DDMConfig
Demand Sampler configuration container.

- **Attributes**
  - `beta_traffic` (float): TomTom weight coefficient.
  - `beta_centrality` (float): Structural centrality weight coefficient.
  - `beta_pop` (float): Population density weight coefficient.
  - `power_base` (float): Power scaling value.
  - `traffic_csv` (Optional[str]): TomTom data file path.
  - `pop_density_tif` (Optional[str]): Population raster file path.
  - `cache_prefix` (str): Cache prefix name.

- **Methods**
  - `__init__(self, beta_traffic: float = 0.5, beta_centrality: float = 0.5, beta_pop: float = 0.0, power_base: float = 1.0, traffic_csv: Optional[str] = None, pop_density_tif: Optional[str] = None, cache_prefix: str = "ddm") -> None`
    - Primary Purpose: Instantiates the DDMConfig data container.

#### DirectDemandSampler
Models passenger demand by blending TomTom traffic flow with structural centrality.

- **Attributes**
  - `city` (CityGraph): City road network.
  - `config` (DDMConfig): Sampler configurations.
  - `drivable_nodes` (set[Node]): Set of drivable street nodes.
  - `node_probabilities` (dict[Node, float]): Map of nodes to demand probabilities.
  - `max_prob` (float): Maximum probability value.
  - `prob` (list[float]): Alias method probability table.
  - `alias` (list[int]): Alias method index table.

- **Methods**
  - `__init__(self, city: CityGraph, config: DDMConfig, verbose: bool = False) -> None`
    - Parameters: CityGraph, configurations, and verbose mode.
    - Outputs: None.
    - Primary Purpose: Instantiates the sampler, imputing traffic data, calculating centrality, blending weights, and building O(1) Walker's Alias tables.
  - `_impute_missing_traffic(self, traffic_data: dict) -> dict[Node, float]`
    - Parameters:
      - `traffic_data` (dict): Raw traffic flow data.
    - Outputs: dict mapping Node to flow value.
    - Primary Purpose: Internal helper using Inverse Distance Weighting (IDW) to impute missing TomTom traffic flows.
  - `_build_alias_tables(self, raw_probs: list[float]) -> None`
    - Parameters:
      - `raw_probs` (list[float]): Raw demand scores.
    - Outputs: None.
    - Primary Purpose: Constructs Walker's Alias Method tables for O(1) sampling.
  - `get_point(self, only_drivable: bool = False) -> Node`
    - Parameters:
      - `only_drivable` (bool): Filter nodes, defaults to False.
    - Outputs: Node.
    - Primary Purpose: Returns a Node sampled proportional to its demand probability in O(1) time.
  - `draw_density(self, img_map: PIL.Image.Image, context: tuple, num_points: int = 2000, only_drivable: bool = False) -> None`
    - Parameters: Image canvas, bounds context, sample points count, and filter toggle.
    - Outputs: None.
    - Primary Purpose: Overlays a demand density heatmap (blue to yellow to red scatter dots) on the canvas.

---

### pheromone.py

- **Top-Level Helper Functions**
  - `_edge_key(edge: DirEdge) -> tuple[tuple[float, float], tuple[float, float]]`
    - Parameters:
      - `edge` (DirEdge): The edge to key.
    - Outputs: Tuple of start and end coordinates.
    - Primary Purpose: Maps an edge object to its immutable coordinate-pair tuple.

#### PheromoneMatrix
Tracks spatial network demand and passenger traffic history across the city graph.

- **Attributes**
  - `initial_tau` (float): Baseline pheromone score value.
  - `rho` (float): Evaporation decay rate.
  - `q` (float): Deposition scaling weight.
  - `default_jeep_weight` (float): Capacity weight scalar.
  - `_tau` (dict): Internal coordinate-pair pheromone store.
  - `_edge_repr` (dict): Maps coordinate keys to representative edges.
  - `tau` (_TauView): Compatibility dict view shim.
  - `gaps` (dict): Cached demand-service gap values.

- **Methods**
  - `__init__(self, all_edges: Iterable[DirEdge], config: dict, sim_result: Optional[SimulationResult] = None) -> None`
    - Parameters: All edges list, configuration dictionary, and simulation results.
    - Outputs: None.
    - Primary Purpose: Instantiates the spatial pheromone matrix, mapping duplicate physical segments to a single logical corridor and optionally seeding values.
  - `_get(self, edge: DirEdge) -> Optional[float]`
    - Parameters:
      - `edge` (DirEdge): The edge to query.
    - Outputs: Optional[float] pheromone value.
    - Primary Purpose: Internal helper looking up pheromone values by coordinate key.
  - `_set(self, edge: DirEdge, value: float) -> None`
    - Parameters: Edge and value.
    - Outputs: None.
    - Primary Purpose: Internal helper updating coordinate pheromones and caching edge representatives.
  - `update_pheromones(self, sim_result: SimulationResult) -> None`
    - Parameters:
      - `sim_result` (SimulationResult): Headless simulation result.
    - Outputs: None.
    - Primary Purpose: Updates pheromone values: evaporates values by factor `rho` and deposits `Q / cost` along simulated passenger paths.
  - `calculate_demand_service_gaps(self, jeep_system: JeepSystem) -> dict[DirEdge, float]`
    - Parameters:
      - `jeep_system` (JeepSystem): Deployed system.
    - Outputs: dict[DirEdge, float] mapping edges to gap values.
    - Primary Purpose: Computes the demand-service gap (`gap = demand - supply`) for all tracked corridors.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image) -> PIL.Image.Image`
    - Parameters: Bounds context and image canvas.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Renders a high-contrast demand heatmap (purple to yellow) onto a square PIL image.
  - `draw_pheromone_difference(self, other: PheromoneMatrix, context: tuple, image: PIL.Image.Image, global_max: float = None) -> PIL.Image.Image`
    - Parameters: Comparison matrix, bounds, canvas, and scale cap.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Renders the absolute difference between two matrices as a red color gradient.

#### _TauView
A read-only dict view of the pheromone store keyed by representative DirEdge.

- **Methods**
  - `__init__(self, tau_store: dict, repr_store: dict) -> None`
    - Primary Purpose: Instantiates the read-only dict view helper.
  - `__iter__(self)`
    - Primary Purpose: Iterates over cached representative edges.
  - `get(self, edge, default=None)`
    - Primary Purpose: Looks up coordinate-mapped values.
  - `items(self)`
    - Primary Purpose: Iterates over `(edge_repr, float)` items.
  - `values(self)`
    - Primary Purpose: Iterates over raw float values.
  - `keys(self)`
    - Primary Purpose: Iterates over representative edges.
  - `__contains__(self, edge) -> bool`
    - Primary Purpose: Checks if coordinate key is mapped.
  - `__getitem__(self, edge)`
    - Primary Purpose: Retrieves coordinate-mapped value.
  - `__setitem__(self, edge, value)`
    - Primary Purpose: Sets coordinate-mapped value.

---

### toy_city.py

- **Top-Level Helper Functions**
  - `build_toy_city(config: ToyCityConfig = ToyCityConfig()) -> CityGraph`
    - Parameters:
      - `config` (ToyCityConfig): Geometry configurations.
    - Outputs: CityGraph.
    - Primary Purpose: Generates a Manhattan-grid road network of Node and DirEdge objects.
  - `toy_setup_from_yaml(yaml_path: str = "configs/toy_city_configs.yaml", verbose: bool = True) -> tuple[CityGraph, ToyDDM, dict]`
    - Parameters: Config file path and verbose mode.
    - Outputs: tuple of CityGraph, ToyDDM, and parsed configurations dictionary.
    - Primary Purpose: Loader constructing synthetic grids and ToyDDM demand samplers in milliseconds.

#### ToyHotspot
A named demand attractor with a geographic position and intensity weight.

- **Attributes**
  - `name` (str): Hotspot identifier.
  - `lon`, `lat` (float): Geographical coordinates.
  - `weight` (float): Demand intensity weight.

#### ToyCityConfig
Grid geometry configuration parameters for the toy city.

- **Attributes**
  - `grid_size` (int): Grid dimensions (N x N), defaults to 10.
  - `origin_lon`, `origin_lat` (float): Base coordinates, defaults to 124.200, 8.200.
  - `step_deg` (float): Step increment size, defaults to 0.001.

#### ToyDDMConfig
Demand surface configuration parameters.

- **Attributes**
  - `idw_power` (float): Proximity decay power, defaults to 2.0.
  - `hotspots` (list[ToyHotspot]): Target hotspot weights.

#### ToyDDM
Spatially-varied demand sampler for synthetic toy grids.

- **Attributes**
  - `city` (CityGraph): Road network.
  - `config` (ToyDDMConfig): Sampler configurations.
  - `node_list` (list[Node]): List of stored nodes.
  - `n` (int): Count of stored nodes.
  - `drivable_nodes` (set[Node]): Set of drivable nodes.
  - `node_probabilities` (dict[Node, float]): Map of nodes to demand probabilities.
  - `max_prob` (float): Maximum probability value.
  - `prob` (list[float]): Alias method probability table.
  - `alias` (list[int]): Alias method index table.

- **Methods**
  - `__init__(self, city: CityGraph, config: ToyDDMConfig = ToyDDMConfig(), verbose: bool = False) -> None`
    - Parameters: CityGraph, configurations, and verbose mode.
    - Outputs: None.
    - Primary Purpose: Instantiates the synthetic sampler, computing IDW demand scores and building Walker's Alias tables.
  - `_extract_drivable_nodes(self) -> set[Node]`
    - Parameters: None.
    - Outputs: set[Node].
    - Primary Purpose: Internal helper extracting nodes connected by drivable edges.
  - `_compute_raw_probs(self) -> list[float]`
    - Parameters: None.
    - Outputs: list[float] of raw probabilities.
    - Primary Purpose: Internal helper evaluating IDW demand scores using hotspot weights.
  - `_build_alias_tables(self, raw_probs: list[float]) -> None`
    - Parameters: Raw probabilities.
    - Outputs: None.
    - Primary Purpose: Constructs Walker's Alias Method tables.
  - `get_point(self, only_drivable: bool = False) -> Node`
    - Parameters:
      - `only_drivable` (bool): Filter nodes.
    - Outputs: Node.
    - Primary Purpose: Returns a Node sampled proportional to its demand probability in O(1) time.
  - `draw_density(self, img_map: PIL.Image.Image, context: tuple, num_points: int = 2000, only_drivable: bool = False) -> None`
    - Parameters: Image canvas, bounds, sample count, and filter.
    - Outputs: None.
    - Primary Purpose: Overlays a demand density heatmap on the canvas.

---

## 5. Evolutionary Optimization

### genetic.py

#### Chromosome
Represents a specific transit route layout and fleet allocation in the GA population.

- **Attributes**
  - `uid` (str): Unique chromosome ID.
  - `routes` (list[Route]): Deployed transit routes.
  - `allocation` (dict[Route, int]): Fleet allocation counts.
  - `pheromones` (PheromoneMatrix): Demand pheromone matrix.
  - `generation` (int): Birth generation index.
  - `parents` (list[str]): Parent ID references.
  - `cost` (float): Cost score.

- **Methods**
  - `__init__(self, routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix, generation: int = 0, parents: Optional[list[str]] = None) -> None`
    - Parameters: Routes, allocation dict, pheromones, generation index, parent IDs.
    - Outputs: None.
    - Primary Purpose: Instantiates the chromosome, setting up initial properties.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns formatted status overview text.

#### MemeticAlgorithm
Integrates Lamarckian local search with genetic operators to optimize route networks.

- **Attributes**
  - `cg` (CityGraph): City road network.
  - `local_search` (ACOLocalSearch): Mutation search operator engine.
  - `target_route_count` (int): Number of routes in each network layout.
  - `verbose` (bool): Prints search progress details.

- **Methods**
  - `__init__(self, cg: Any, local_search: ACOLocalSearch, target_route_count: int, verbose: bool = False) -> None`
    - Parameters: Graph, local search engine, target route count, and verbose mode.
    - Outputs: None.
    - Primary Purpose: Instantiates the genetic search coordinator.
  - `_get_hub_edges(self, routes: list[Route], pheromones: PheromoneMatrix) -> set[Any]`
    - Parameters: Routes list and pheromone matrix.
    - Outputs: set of hub edge objects.
    - Primary Purpose: Internal helper identifying the top 10% highest-demand edges (hubs) based on their pheromone values.
  - `crossover_topological_hub(self, parent_a: Chromosome, parent_b: Chromosome) -> list[Route]`
    - Parameters: Parent chromosomes.
    - Outputs: list of Route objects.
    - Primary Purpose: Executes topological crossover: extracts Parent A's routes touching high-demand hub edges and completes the route set with non-overlapping routes from Parent B.
  - `inherit_pheromones(self, parent_a: Chromosome, parent_b: Chromosome) -> PheromoneMatrix`
    - Parameters: Parent chromosomes.
    - Outputs: PheromoneMatrix.
    - Primary Purpose: Blends parent pheromone matrices using inverse fitness-weighted interpolation.
  - `evaluate_chromosome(self, chrom: Chromosome, total_fleet: int) -> float`
    - Parameters: Chromosome and fleet size.
    - Outputs: float (fitness cost score).
    - Primary Purpose: Allocates fleet using Mohring's square root rule, evaluates travel headways/lengths, and updates chromosome cost.
  - `apply_lamarckian_mutation(self, child: Chromosome, target_cost: float, total_fleet: int) -> bool`
    - Parameters: Child chromosome, target cost threshold, and fleet size.
    - Outputs: bool (True if mutation was accepted).
    - Primary Purpose: Triggers local search mutation, accepting it if the mutated route cost improves (Lamarckian inheritance).

---

### local_search.py

#### ACOLocalSearch
Applies demand-driven mutations and spatial heuristics to optimize route systems.

- **Attributes**
  - `cg` (CityGraph): City road network.
  - `p_attraction` (float): Spatial attraction mutation probability.
  - `p_repulsion` (float): Redundancy repulsion mutation probability.
  - `p_pruning` (float): Tortuosity pruning mutation probability.
  - `base_window_size` (int): Window size for segment manipulation.

- **Methods**
  - `__init__(self, cg: Any, p_attraction: float = 0.4, p_repulsion: float = 0.4, p_pruning: float = 0.6, base_window_size: int = 15) -> None`
    - Parameters: CityGraph, mutation probabilities, and window size.
    - Outputs: None.
    - Primary Purpose: Instantiates the search engine.
  - `calculate_route_similarity(self, route_a: Route, route_b: Route) -> float`
    - Parameters: Route objects.
    - Outputs: float (similarity score).
    - Primary Purpose: Evaluates route similarity using the discrete Fréchet distance algorithm over node coordinates.
  - `_get_shortest_path_edges(self, start_node: Any, end_node: Any) -> list[Any]`
    - Parameters: Start and end nodes.
    - Outputs: list of edges.
    - Primary Purpose: Internal helper returning A* shortest path street edges between two nodes.
  - `_stitch_path(self, raw_edges: list) -> Optional[list]`
    - Parameters: Unstitched edges.
    - Outputs: Optional list of edges.
    - Primary Purpose: Internal helper sequentially connecting disjoint edges and closing the circular loop.
  - `_safe_splice(self, path: list, start_idx: int, end_idx: int, new_segment: list) -> Optional[list]`
    - Parameters: Original path, splice indexes, and replacement segment.
    - Outputs: Optional list of edges.
    - Primary Purpose: Internal helper safely replacing a path slice and re-stitching the circular path.
  - `_edge_id(self, edge: Any) -> Any`
    - Parameters: Edge.
    - Outputs: ID value.
    - Primary Purpose: Internal helper extracting a stable identifier for an edge.
  - `_finalize_path(self, raw_path: list) -> list`
    - Parameters: Edge list.
    - Outputs: list of Layer 2 edges.
    - Primary Purpose: Internal helper converting a mixed-layer path to a strictly compliant Layer 2 transit loop.
  - `strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> Optional[Route]`
    - Parameters: Routes list, pheromones, and intensity scalar.
    - Outputs: Optional[Route].
    - Primary Purpose: Detours routes toward underserved demand corridors (positive gap scores) using cheapest-insertion heuristics.
  - `strategy_redundancy_repulsion(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> Optional[Route]`
    - Parameters: Routes list, pheromones, and intensity scalar.
    - Outputs: Optional[Route].
    - Primary Purpose: Detours routes away from overserved corridors (negative gap scores) by detouring around overserved segments.
  - `strategy_tortuosity_pruning(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> tuple[int, Optional[Route]]`
    - Parameters: Routes list, pheromones, and intensity.
    - Outputs: tuple of prunes count and the modified Route.
    - Primary Purpose: Smooths out geometrically inefficient wiggles in routes, utilizing gap immunity to skip underserved segments.
  - `optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> dict`
    - Parameters: Routes list, pheromones, and intensity.
    - Outputs: dict of actions taken.
    - Primary Purpose: One-shot coordinator applying all active mutation operators stochastically.

---

### optimizer_adaptive.py

#### AdaptiveController
Dynamically scales mutation probabilities to escape local optima and decays local search intensities.

- **Attributes**
  - `base_mutation` (float): Baseline mutation probability.
  - `stagnation_limit` (int): Maximum generation count before hard capping.
  - `max_mutation` (float): Maximum mutation probability limit.
  - `current_mutation` (float): Active mutation probability.

- **Methods**
  - `__init__(self, base_mutation: float, stagnation_limit: int, max_mutation: float = 0.8) -> None`
    - Parameters: Baseline, stagnation limit, and max mutation limit.
    - Outputs: None.
    - Primary Purpose: Instantiates the controller.
  - `update(self, stagnation_counter: int) -> float`
    - Parameters:
      - `stagnation_counter` (int): Generations without improvement.
    - Outputs: float (updated mutation probability).
    - Primary Purpose: Non-linearly scales mutation intensity as stagnation increases, resetting to base immediately upon improvement.
  - `get_local_search_prob(self, generation: int, g_max: int, p_min: float = 0.05, p_max: float = 0.8) -> float`
    - Primary Purpose: Computes the linearly decaying local search mutation probability: $P_{local}(g) = P_{min} + (P_{max} - P_{min}) * (1 - g / G_{max})$.
  - `get_local_search_intensity(self, generation: int, g_max: int, i_min: float = 0.1, i_max: float = 1.0) -> float`
    - Primary Purpose: Computes the dynamically tightening local search intensity/radius: $I_{local}(g) = I_{min} + (I_{max} - I_{min}) * (1 - g / G_{max})$.

---

### optimizer_config.py

#### ExperimentConfig
Configuration container handling YAML ingestion, type validation, and boundary definitions.

- **Attributes**
  - `output_root` (Path): Root directory for output logs and checkpoints.
  - `telemetry_interval` (int): Frequency of logging generations.
  - `checkpoint_interval` (int): Frequency of serializing states.
  - `n_population` (int): Population size.
  - `g_max` (int): Maximum GA generations.
  - `n_stagnation` (int): Stagnation limit.
  - `n_elite` (int): Count of elite survivors.
  - `k_tournament` (int): Tournament size.
  - `p_mutation` (float): Mutation rate.
  - `gamma_crossover` (float): Crossover blend rate.
  - `initial_tau` (float): Pheromone base score.
  - `rho` (float): Pheromone decay rate.
  - `q` (float): Pheromone scaling weight.
  - `p_ls_attraction`, `p_ls_repulsion`, `p_ls_pruning` (float): Mutation probabilities.
  - `default_jeep_weight` (float): Fleet capacity scale.
  - `alpha_std_penalty`, `beta_penalty` (float): Cost penalty coefficients.
  - `num_routes` (int): Total routes per network.
  - `total_allocatable_jeeps` (int): Total jeep fleet.
  - `city_bounds` (tuple): Spatial coordinate bounds.
  - `walk_wt`, `ride_wt`, `wait_wt`, `transfer_wt` (float): Travel weight factors.
  - `max_ticks` (int): Simulation ticks.
  - `passenger_speed`, `jeep_speed` (float): Movement speeds in km/h.
  - `jeep_capacity` (int): Seat capacity.
  - `spawn_rate_per_hour` (float): Passenger spawn rate.
  - `spawn_stdev` (float): Spawning schedule standard deviation.
  - `weight_tolerance` (float): Boarding alternative routes penalty buffer.
  - `equidistant_spawn` (bool): Spawn jeep spacing flag.

- **Methods**
  - `from_yaml(cls, path: str | Path) -> ExperimentConfig`
    - Parameters: Configuration YAML file path.
    - Outputs: ExperimentConfig.
    - Primary Purpose: Ingests, parses, and validates the configurations.

#### OptimizationState
Structured state tracker.

- **Attributes**
  - `generation` (int): Active generation index.
  - `stagnation_counter` (int): Generations without improvement.
  - `best_fitness` (float): Best fitness score.
  - `population` (list): Live Chromosome population.
  - `pheromones` (PheromoneMatrix): Active pheromone matrix.
  - `random_state` (Optional[tuple]): Captured pseudorandom state (`random.getstate()`) for deterministic Pause/Resume recovery.

---

### optimizer_orchestrator_io.py

#### StatePreservationEngine
Manages serialized optimization state checkpoints.

- **Attributes**
  - `run_dir` (Path): Path to output directory.
  - `checkpoints_dir` (Path): Path to checkpoints subfolder.

- **Methods**
  - `__init__(self, run_dir: Path) -> None`
    - Parameters: Active run directory.
    - Outputs: None.
    - Primary Purpose: Instantiates the engine, creating target checkpoint directories.
  - `save_state(self, state: OptimizationState) -> None`
    - Parameters: Active optimization state.
    - Outputs: None.
    - Primary Purpose: Serializes the state using an atomic write pattern (`.tmp` write then atomic replace) to prevent corruption.
  - `load_state(self, filepath: Path) -> OptimizationState`
    - Parameters: Checkpoint file path.
    - Outputs: OptimizationState.
    - Primary Purpose: Deserializes the checkpoint file.

#### OptimizerBuilder
Constructs isolated optimization environments and resumes runs.

- **Methods**
  - `build_new_run(config_path: str | Path) -> tuple[ExperimentConfig, Path]`
    - Parameters: YAML config file path.
    - Outputs: tuple of ExperimentConfig and the output Path.
    - Primary Purpose: Sets up a fresh, isolated run directory, copying configurations to ensure reproducibility.
  - `resume_run(run_dir: str | Path) -> tuple[ExperimentConfig, OptimizationState, Path]`
    - Parameters: Run directory path.
    - Outputs: tuple of ExperimentConfig, loaded OptimizationState, and the run directory Path.
    - Primary Purpose: Resumes an existing run by loading the configuration and deserializing the latest checkpoint file.

---

### optimizer_telemetry.py

- **Top-Level Helper Classes**
  - `_DummyJeep`
    - Mocks Jeep actors to bridge Chromosome allocations with the JeepSystem API.
  - `_DummySystem`
    - Mocks environments to fulfill PheromoneMatrix gap calculation requirements.

#### TelemetryEngine
Handles synchronous metrics logging, lineage tracking, and JSON exports.

- **Attributes**
  - `run_dir` (Path): Active run directory.
  - `bounds` (tuple): Spatial coordinate bounds.
  - `history_file` (Path): CSV file path for metrics history.
  - `lineage_file` (Path): CSV file path for chromosome lineages.
  - `snapshots_dir` (Path): JSON state snapshots directory.

- **Methods**
  - `__init__(self, run_dir: Path, bounds: tuple[float, float, float, float]) -> None`
    - Parameters: Run directory and spatial coordinate bounds.
    - Outputs: None.
    - Primary Purpose: Instantiates the telemetry logger.
  - `_init_csvs(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Internal helper initializing CSV structures if they do not exist.
  - `log_generation(self, gen: int, best_cost: float, mean_cost: float, mut_rate: float, stag: int) -> None`
    - Parameters: Logging parameters for generation, costs, rates, and stagnation.
    - Outputs: None.
    - Primary Purpose: Appends generation performance metrics to `history.csv`.
  - `log_lineage(self, population: list) -> None`
    - Parameters: Active chromosome population.
    - Outputs: None.
    - Primary Purpose: Logs UIDs, costs, and parent lineage mappings to `lineage.csv`.
  - `export_json_snapshot(self, generation: int, best_cost: float, mean_cost: float, population: list) -> None`
    - Parameters: Generation details and population.
    - Outputs: None.
    - Primary Purpose: Exports a complete network snapshot (routes, pheromone intensities, unserved gaps, and cost distributions) in JSON format.

---

## 6. Simulation and Analysis

### simulation.py

#### SimulationSetup
Orchestrates the instantiation sequence for the simulation stack.

- **Attributes**
  - `id` (str): Unique setup ID.
  - `city_query` (str): City name identifier.
  - `config` (dict): Complete configuration dictionary.
  - `bounds` (tuple): Spatial boundaries coordinates.
  - `routes` (list[Route]): Routes list.

- **Methods**
  - `__init__(self, city_query: str, config: dict, routes: list[Route]) -> None`
    - Parameters: City name, configuration dictionary, and routes.
    - Outputs: None.
    - Primary Purpose: Instantiates the setup wrapper, validating that routes are provided.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns status summary text.
  - `build(self) -> Simulation`
    - Parameters: None.
    - Outputs: Simulation.
    - Primary Purpose: Headless factory method instantiating CityGraph, DirectDemandSampler, TravelGraph, JeepSystem, PassengerGenerator, and constructing the Simulation.

#### SimulationResult
Holds performance metrics and passenger path histories.

- **Attributes**
  - `sim_id` (str): Simulation ID.
  - `fitness_score` (float): Cost score.
  - `metrics` (dict): Operational metrics.
  - `recorded_paths` (list): Passenger travel paths and costs.
  - `jeep_system` (Optional[JeepSystem]): Simulation jeep system state.

- **Methods**
  - `__init__(self, fitness_score: float, metrics: dict[str, Any], recorded_paths: list[tuple[Any, float]], jeep_system: Optional[JeepSystem] = None, sim_id: Optional[str] = None) -> None`
    - Parameters: Costs, metrics, paths, jeep system state, and ID.
    - Outputs: None.
    - Primary Purpose: Instantiates the results container.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns basic status summary text.
  - `export_report(self, out_dir: str) -> None`
    - Parameters: Output directory path.
    - Outputs: None.
    - Primary Purpose: Writes an operational report file containing the metrics and an embedded JSON data block.
  - `from_file(cls, filepath: str) -> SimulationResult`
    - Parameters: Report file path.
    - Outputs: SimulationResult.
    - Primary Purpose: Parses a report file to reconstruct the results container.

#### Simulation
Headless simulation loop runner and dashboard renderer.

- **Attributes**
  - `id` (str): Unique simulation ID.
  - `city_query` (str): City name.
  - `bounds` (tuple): Spatial boundaries.
  - `jeep_system` (JeepSystem): Deployed vehicle fleet coordinator.
  - `passenger_generator` (PassengerGenerator): Passenger spawner.
  - `max_ticks` (int): Ticks limit.
  - `beta_penalty` (float): Penalty coefficient for incomplete journeys.
  - `alpha_std_penalty` (float): Penalty coefficient for commute variance.
  - `config` (dict): Complete configuration dictionary.
  - `current_tick` (int): Elapsed simulation ticks.
  - `is_complete` (bool): True if simulation is finished.
  - `speed_multiplier` (int): Playback speed.

- **Methods**
  - `__init__(self, city_query: str, bounds: tuple[float, float, float, float], jeep_system: JeepSystem, passenger_generator: PassengerGenerator, max_ticks: int, beta_penalty: float = 2.0, alpha_std_penalty: float = 0.5, config: Optional[dict] = None) -> None`
    - Parameters: Configurations, actors, and coefficients.
    - Outputs: None.
    - Primary Purpose: Instantiates the simulation coordinator.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns status summary text.
  - `update(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Steps the simulation forward: updates passenger generator, spawns passengers, updates vehicle states, and increments ticks.
  - `run(self) -> SimulationResult`
    - Parameters: None.
    - Outputs: SimulationResult.
    - Primary Purpose: headless loop runner ticking until `max_ticks` is reached, returning results.
  - `run_until_drained(self, safety_cap: int = 100000) -> SimulationResult`
    - Parameters: Ticks safety limit.
    - Outputs: SimulationResult.
    - Primary Purpose: Ticks until all spawned passengers complete their journeys.
  - `_calculate_results(self) -> SimulationResult`
    - Parameters: None.
    - Outputs: SimulationResult.
    - Primary Purpose: Internal evaluator summing commute times, incomplete commute penalties, and commute variance to calculate fitness cost.
  - `draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: PIL.Image.Image, draw_jeeps: bool = True, draw_passengers: bool = True) -> PIL.Image.Image`
    - Parameters: Bounds context, image canvas, vehicle toggle, passenger toggle.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Renders vehicles and active passengers onto a square PIL image context.
  - `draw_dashboard(self, image: PIL.Image.Image) -> PIL.Image.Image`
    - Parameters: Image canvas.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Overlays a dashboard overlay (TICK, JEEPS, ACTIVE PAX, DONE PAX) onto the canvas frame.

#### SimulationEvaluator
Evaluates route configurations against static network and demand structures during search phases.

- **Attributes**
  - `config` (dict): Complete configuration dictionary.
  - `city_graph` (CityGraph): Road network.
  - `travel_graph` (TravelGraph): Multi-layer graph.
  - `demand_sampler` (DirectDemandSampler): Demand sampling matrix.
  - `total_jeeps` (int): Vehicle fleet size.
  - `jeep_speed`, `jeep_capacity`, `weight_tol` (various): Deployed fleet values.
  - `spawn_rate`, `spawn_stdev`, `pax_speed` (various): Passenger values.
  - `max_ticks` (int): Simulation ticks.
  - `beta_penalty`, `alpha_std_penalty` (float): Cost penalty coefficients.

- **Methods**
  - `__init__(self, config: dict, city_graph: CityGraph, travel_graph: TravelGraph, demand_sampler: DirectDemandSampler) -> None`
    - Parameters: Graph, travel graph, sampler, and configurations.
    - Outputs: None.
    - Primary Purpose: Instantiates the evaluator.
  - `evaluate(self, routes: list[Route], verbose: bool = False) -> SimulationResult`
    - Parameters: Routes list to test, verbose mode.
    - Outputs: SimulationResult.
    - Primary Purpose: Instantiates a mock fleet, passenger generator, and headless Simulation, executing it and returning results (safely detaching jeep system references to prevent pickling issues).

#### StaticSurrogateEvaluator
Evaluates route configurations against pre-sampled Origin-Destination pairs to avoid heavy simulation costs.

- **Attributes**
  - `config` (dict): Configuration dictionary.
  - `city_graph` (CityGraph): Road network.
  - `demand_sampler` (DirectDemandSampler): Demand sampler.
  - `num_samples` (int): Pre-sampled OD pairs count.
  - `od_pairs` (list): Pre-sampled OD coordinates.

- **Methods**
  - `__init__(self, config: dict, city_graph: CityGraph, demand_sampler: DirectDemandSampler, num_samples: int = 500) -> None`
    - Parameters: Configurations, graph, sampler, sample size.
    - Outputs: None.
    - Primary Purpose: Instantiates the evaluator, sampling OD pairs.
  - `evaluate(self, routes: list[Route], verbose: bool = False) -> SimulationResult`
    - Parameters: Routes list to test.
    - Outputs: SimulationResult.
    - Primary Purpose: Rebuilds travel graphs using inflated transfer weights, solves A* paths for pre-sampled OD coordinates, aggregates path weights, and returns results.

---

## 7. Visualization and Support Interfaces

### visualization.py

- **Top-Level Helper Functions**
  - `compile_to_gif(frames: list[PIL.Image.Image], fps: int, export_to: Optional[str] = None, verbose: bool = False) -> bytes`
    - Parameters: Image frames list, frame rate, export path, verbose mode.
    - Outputs: bytes.
    - Primary Purpose: Compiles a sequence of PIL images into a GIF byte stream, validating formats and checking that export paths fall within `utils/.cache/`.
  - `draw_all(drawable_objects: list[Any], context: tuple, base_image: Optional[PIL.Image.Image] = None, resolution: int = 1000, text: Optional[str] = None, verbose: bool = False) -> PIL.Image.Image`
    - Parameters: Objects list, bounds context, base image, resolution, overlay text, verbose.
    - Outputs: PIL.Image.Image.
    - Primary Purpose: Sequentially executes the draw method of multiple objects on a base image context, adding outline text overlays.

#### LiveTkinterVisualizer
A threaded Tkinter GUI class for real-time simulation playback.

- **Attributes**
  - `state` (Any): Active simulation state.
  - `update_func` (Callable): State mutation update callback.
  - `draw_func` (Callable): Frame rendering callback.
  - `fps` (int): Playback frame rate.
  - `delay_ms` (int): Thread sleep duration in milliseconds.
  - `state_lock` (threading.Lock): Sync lock.
  - `running` (bool): Active execution flag.
  - `root` (tk.Tk): Tkinter GUI window.
  - `canvas` (tk.Canvas): GUI canvas widget.
  - `_tk_image` (ImageTk.PhotoImage): Canvas image frame.

- **Methods**
  - `__init__(self, initial_state: Any, update_func: Callable[[Any], None], draw_func: Callable[[Any], PIL.Image.Image], fps: int = 30) -> None`
    - Parameters: State, callbacks, and playback rate.
    - Outputs: None.
    - Primary Purpose: Instantiates and sets up the GUI elements.
  - `_simulation_worker(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Asynchronous worker thread loop updating state.
  - `_render_loop(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Main GUI thread callback rendering updates.
  - `_on_closing(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Gracefully stops worker threads and destroys GUI elements on window closing.
  - `display(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Blocks the execution and runs the visualizer.

---

### __init__.py

- **Package Level Interface**
  - Defines and documents the public API and package-level symbols exported by the `utils/` package.
  - Documents standard speed interpretations (km/h) and tick multiplier standards.
  - Explicitly exports:
    - `Node` (`utils/node.py`)
    - `DirEdge` (`utils/directed_edge.py`)
    - `CityGraph` (`utils/city_graph.py`)
    - `Route`, `RouteGenerator` (`utils/route.py`)
    - `TravelGraph` (`utils/travel_graph.py`)
    - `Passenger` (`utils/passenger.py`)
    - `PassengerGenerator` (`utils/passenger_generator.py`)
    - `Jeep` (`utils/jeep.py`)
    - `JeepSystem` (`utils/jeep_system.py`)
    - `PheromoneMatrix` (`utils/pheromone.py`)
    - `ACOLocalSearch` (`utils/local_search.py`)
    - `Chromosome`, `MemeticAlgorithm` (`utils/genetic.py`)
    - `TravelGraph3DVisualizer` (`utils/travel_graph_3d_vis.py`)
    - `SimulationSetup`, `SimulationResult`, `Simulation` (`utils/simulation.py`)

---

## 8. Genetic and Evolutionary Optimization Utilities

### genetic.py

#### Chromosome
A data structure representing a candidate route system and fleet allocation configuration within the genetic algorithm.

- **Attributes**
  - `uid` (str): A unique identifier string generated using uuid.
  - `generation` (int): The evolutionary generation index at which the chromosome was born.
  - `parents` (list[str]): A list of parent chromosome UIDs if bred from a crossover, else empty.
  - `routes` (list[Route]): The list of closed transit Route objects in this candidate solution.
  - `allocation` (dict[Route, int]): The optimal fleet allocation mapping each Route to its assigned number of jeepneys.
  - `pheromones` (PheromoneMatrix): The localized epigenetic PheromoneMatrix instance mapped to this chromosome.
  - `cost` (float): The calculated overall system fitness cost (lower is better).

- **Methods**
  - `__init__(self, routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix, generation: int = 0, parents: Optional[list[str]] = None) -> None`
    - Parameters:
      - `routes` (list[Route]): Target candidate route paths.
      - `allocation` (dict[Route, int]): Fleet allocation map.
      - `pheromones` (PheromoneMatrix): Decoupled pheromone database.
      - `generation` (int): Evolutionary birth index, defaults to 0.
      - `parents` (Optional[list[str]]): List of parent chromosome UIDs, defaults to None.
    - Outputs: None.
    - Primary Purpose: Instantiates a candidate solution chromosome with a unique identifier and tracks lineage relationships.
  - `__str__(self) -> str`
    - Parameters: None.
    - Outputs: str.
    - Primary Purpose: Returns a summary string including UID, generation, cost, and number of routes.

#### MemeticAlgorithm
The class executing Lamarckian evolutionary operations on candidate Chromosome systems.

- **Attributes**
  - `cg` (Any): The active CityGraph instance.
  - `local_search` (ACOLocalSearch): The local search operator engine.
  - `target_route_count` (int): The required number of routes per candidate system.
  - `verbose` (bool): Verbosity flag for standard out.

- **Methods**
  - `__init__(self, cg: Any, local_search: ACOLocalSearch, target_route_count: int, verbose: bool = False) -> None`
    - Parameters:
      - `cg` (Any): Base spatial graph database.
      - `local_search` (ACOLocalSearch): Heuristic local search operator.
      - `target_route_count` (int): Target number of route tracks.
      - `verbose` (bool): Console reporting verbosity flag.
    - Outputs: None.
    - Primary Purpose: Instantiates and configures the Lamarckian operator suite, checking parameters for valid bounds.
  - `_get_hub_edges(self, routes: list[Route], pheromones: PheromoneMatrix) -> set[Any]`
    - Parameters:
      - `routes` (list[Route]): Route system.
      - `pheromones` (PheromoneMatrix): Edge pheromone density matrix.
    - Outputs: set[Any].
    - Primary Purpose: Identifies the high-value topological corridor sub-graph consisting of the top 10% highest demand edges.
  - `crossover_topological_hub(self, parent_a: Chromosome, parent_b: Chromosome) -> list[Route]`
    - Parameters:
      - `parent_a` (Chromosome): Fitter parent candidate.
      - `parent_b` (Chromosome): Less fit parent candidate.
    - Outputs: list[Route].
    - Primary Purpose: Generates offspring routes by extracting high-demand hub corridors from Parent A and completing remaining slots using distinct, non-overlapping routes from Parent B.
  - `inherit_pheromones(self, parent_a: Chromosome, parent_b: Chromosome) -> PheromoneMatrix`
    - Parameters:
      - `parent_a` (Chromosome): Parent A candidate.
      - `parent_b` (Chromosome): Parent B candidate.
    - Outputs: PheromoneMatrix.
    - Primary Purpose: Blends parent pheromone databases using a fitness-weighted arithmetic crossover to construct the child's epigenetic matrix.
  - `evaluate_chromosome(self, chrom: Chromosome, total_fleet: int) -> float`
    - Parameters:
      - `chrom` (Chromosome): Candidate system to evaluate.
      - `total_fleet` (int): Total allocatable fleet size.
    - Outputs: float (system cost).
    - Primary Purpose: Allocates fleet across routes using Mohring square-root fractions, calculates distance and headway metrics, applies structural penalties for unallocated fleets, and sets the chromosome's cost.
  - `apply_lamarckian_mutation(self, child: Chromosome, target_cost: float, total_fleet: int) -> bool`
    - Parameters:
      - `child` (Chromosome): Candidate chromosome to mutate.
      - `target_cost` (float): Cost threshold that must be surpassed for acceptance.
      - `total_fleet` (int): Total vehicle fleet size.
    - Outputs: bool (whether mutation succeeded in lowering cost and was retained).
    - Primary Purpose: Calculates unserved demand corridors, applies heuristic local searches (attraction, repulsion, pruning) on route geometries, evaluates results, and retains improvements.

---

### optimizer_config.py

#### ExperimentConfig
A frozen, immutable dataclass containing all system, travel-graph, genetic, local search, and simulation parameters.

- **Attributes**
  - `output_root` (Path): Path to store telemetry and checkpoints.
  - `telemetry_interval` (int): Generational interval for exporting lineage and snapshots.
  - `checkpoint_interval` (int): Generational interval for saving serialized states.
  - `n_population` (int): Chromosome population size.
  - `g_max` (int): Maximum evolutionary generations.
  - `n_stagnation` (int): Generations before search termination due to stagnation.
  - `n_elite` (int): Number of top chromosomes preserved directly across generations.
  - `k_tournament` (int): Tournament selection size.
  - `p_mutation` (float): Base probability of mutation.
  - `gamma_crossover` (float): Crossover blending coefficient.
  - `initial_tau` (float): Base pheromone concentration value.
  - `rho` (float): Generational pheromone evaporation rate.
  - `q` (float): Pheromone deposition scaling factor.
  - `p_ls_attraction` (float): Local search attraction probability.
  - `p_ls_repulsion` (float): Local search repulsion probability.
  - `p_ls_pruning` (float): Local search pruning probability.
  - `default_jeep_weight` (float): Fleet allocator default weight.
  - `alpha_std_penalty` (float): Headway variance penalty coefficient.
  - `beta_penalty` (float): Underservice penalty coefficient.
  - `num_routes` (int): Required routes in route systems.
  - `total_allocatable_jeeps` (int): Total jeepney count.
  - `city_bounds` (tuple): Geographical bounding box.
  - `walk_wt` (float): Travel graph walking weight penalty.
  - `ride_wt` (float): Travel graph riding weight penalty.
  - `wait_wt` (float): Travel graph waiting weight penalty.
  - `transfer_wt` (float): Travel graph transfer weight penalty.
  - `max_ticks` (int): Simulation run duration ticks.
  - `passenger_speed` (float): Walking speed in km/h.
  - `jeep_speed` (float): Vehicle movement speed in km/h.
  - `jeep_capacity` (int): Maximum passengers per vehicle.
  - `spawn_rate_per_hour` (float): Base passenger spawn rate.
  - `spawn_stdev` (float): Passenger spawn normal distribution standard deviation.
  - `weight_tolerance` (float): Waiting tolerance limit.
  - `equidistant_spawn` (bool): Dispatch spacing flag.

- **Methods**
  - `from_yaml(cls, path: str | Path) -> ExperimentConfig`
    - Parameters:
      - `path` (str | Path): Config file path.
    - Outputs: ExperimentConfig.
    - Primary Purpose: Instantiates an immutable config dataclass, loading parameters and parsing fallback bounding boxes for synthetic toy cities and real OSM cities.

#### OptimizationState
A mutable dataclass tracking live generational state.

- **Attributes**
  - `generation` (int): Active generation index.
  - `stagnation_counter` (int): Generations passed without fitness improvements.
  - `best_fitness` (float): Fittest score registered so far.
  - `population` (list[Chromosome]): Fittest chromosomes in active generation.
  - `pheromones` (PheromoneMatrix): Master pheromone database.
  - `random_state` (Optional[tuple]): Captured state tuple for deterministic auditing.

---

### optimizer_adaptive.py

#### AdaptiveController
A controller dynamically scaling mutation probability using stagnation metrics to assist search loops in escaping local optima and decaying local search parameters.

- **Attributes**
  - `base_mutation` (float): Base mutation rate.
  - `stagnation_limit` (int): Stagnation threshold.
  - `max_mutation` (float): Maximum mutation cap limit.
  - `current_mutation` (float): Active scaling mutation rate.

- **Methods**
  - `__init__(self, base_mutation: float, stagnation_limit: int, max_mutation: float = 0.8) -> None`
    - Parameters:
      - `base_mutation` (float): Minimum mutation rate.
      - `stagnation_limit` (int): Maximum stagnation generation length.
      - `max_mutation` (float): Maximum cap, defaults to 0.8.
    - Outputs: None.
    - Primary Purpose: Instantiates the controller, verifying bounds are correct.
  - `update(self, stagnation_counter: int) -> float`
    - Parameters:
      - `stagnation_counter` (int): Live stagnation counter.
    - Outputs: float (scaled mutation rate).
    - Primary Purpose: Scales mutation intensity quadratically as stagnation persists, and resets instantly to baseline once improvements occur.
  - `get_local_search_prob(self, generation: int, g_max: int, p_min: float = 0.05, p_max: float = 0.8) -> float`
    - Primary Purpose: Computes the linearly decaying local search mutation probability: $P_{local}(g) = P_{min} + (P_{max} - P_{min}) * (1 - g / G_{max})$.
  - `get_local_search_intensity(self, generation: int, g_max: int, i_min: float = 0.1, i_max: float = 1.0) -> float`
    - Primary Purpose: Computes the dynamically tightening local search intensity/radius: $I_{local}(g) = I_{min} + (I_{max} - I_{min}) * (1 - g / G_{max})$.

---

### optimizer_telemetry.py

#### TelemetryEngine
The engine responsible for metric logging, lineage tracking, and continuous JSON state exports.

- **Attributes**
  - `run_dir` (Path): Path to output workspace.
  - `bounds` (tuple): Geographical bounding box boundary.
  - `history_file` (Path): Path to history.csv log.
  - `lineage_file` (Path): Path to lineage.csv log.
  - `snapshots_dir` (Path): Subdirectory for JSON snapshots.

- **Methods**
  - `__init__(self, run_dir: Path, bounds: tuple[float, float, float, float]) -> None`
    - Parameters:
      - `run_dir` (Path): Target outputs directory.
      - `bounds` (tuple): Bounding box bounds.
    - Outputs: None.
    - Primary Purpose: Prepares directory paths, creates snapshots folder, and initializes tracking files.
  - `_init_csvs(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Initializes csv logs with headers only if they do not exist, protecting data on resumes.
  - `log_generation(self, gen: int, best_cost: float, mean_cost: float, mut_rate: float, stag: int) -> None`
    - Parameters: Generation, best fitness, mean cost, active mutation rate, stagnation.
    - Outputs: None.
    - Primary Purpose: Appends overall generational fitness telemetry to history.csv.
  - `log_lineage(self, population: list[Chromosome]) -> None`
    - Parameters: Active population list.
    - Outputs: None.
    - Primary Purpose: Appends genealogical parent-child relationships and chromosome costs to lineage.csv.
  - `export_json_snapshot(self, generation: int, best_cost: float, mean_cost: float, population: list[Chromosome]) -> None`
    - Parameters: Generation, best cost, mean cost, active population.
    - Outputs: None.
    - Primary Purpose: Exports high-fidelity, client-compatible JSON files containing routes geometry, high-intensity pheromone coordinates, and demand chokepoints.

---

### optimizer_orchestrator_io.py

#### StatePreservationEngine
The engine handling binary pickling and serialization of evolutionary state checkpoints.

- **Attributes**
  - `run_dir` (Path): Workspace root path.
  - `checkpoints_dir` (Path): Checkpoint file storage directory.

- **Methods**
  - `__init__(self, run_dir: Path) -> None`
    - Parameters: Workspace root.
    - Outputs: None.
    - Primary Purpose: Instantiates the engine and creates checkpoints folder.
  - `save_state(self, state: OptimizationState) -> None`
    - Parameters: Active state object.
    - Outputs: None.
    - Primary Purpose: Serializes optimization state using an atomic write pattern (writing to `.tmp` first, then replacing), preventing corruptions from sudden interrupts.
  - `load_state(self, filepath: Path) -> OptimizationState`
    - Parameters: Pickled file path.
    - Outputs: OptimizationState.
    - Primary Purpose: Deserializes the pickling stream to restore optimization execution.

#### OptimizerBuilder
A static builder factory to construct new runs or resume existing ones.

- **Methods**
  - `build_new_run(config_path: str | Path) -> tuple[ExperimentConfig, Path]`
    - Parameters:
      - `config_path` (str | Path): Config file path.
    - Outputs: tuple[ExperimentConfig, Path] (parsed config and run workspace path).
    - Primary Purpose: Creates a new timestamped output directory and copies the configuration YAML for absolute reproducibility.
  - `resume_run(run_dir: str | Path) -> tuple[ExperimentConfig, OptimizationState, Path]`
    - Parameters:
      - `run_dir` (str | Path): Path to a past run workspace.
    - Outputs: tuple[ExperimentConfig, OptimizationState, Path] (loaded config, deserialized state, workspace path).
    - Primary Purpose: Reconstructs runtime state, locating the most recent valid pickle checkpoint.

---

### optimizer_engine.py

#### MemeticEngine
The core engine coordinating Phases A through D of the memetic optimization algorithm.

- **Attributes**
  - `config` (ExperimentConfig): Immutable experiment configurations.
  - `cg` (CityGraph): Drivable city network.
  - `sampler` (Optional[Any]): Passenger demand sampler.
  - `current_generation` (int): Generation counter index.
  - `local_search` (ACOLocalSearch): Heuristic local search operator database.
  - `algo` (MemeticAlgorithm): High-level genetic operator suite.

- **Methods**
  - `__init__(self, config: ExperimentConfig, cg: CityGraph, sampler: Optional[Any] = None) -> None`
    - Parameters: Immutable configurations, city graph, optional demand sampler.
    - Outputs: None.
    - Primary Purpose: Instantiates engines and configures the local search and genetic classes.
  - `initialize_state(self) -> OptimizationState`
    - Parameters: None.
    - Outputs: OptimizationState.
    - Primary Purpose: Generates the initial population of chromosomes, instantiating fresh, decoupled PheromoneMatrix objects for each, evaluating initial costs, and loading the fittest.
  - `step_generation(self, state: OptimizationState, current_mutation_rate: float) -> OptimizationState`
    - Parameters:
      - `state` (OptimizationState): Active optimization state.
      - `current_mutation_rate` (float): Scaled mutation rate.
    - Outputs: OptimizationState (the next generational state).
    - Primary Purpose: Implements elitism (directly retaining the fittest), executes tournament selection, triggers crossover and epigenetic inheritance, performs Lamarckian local search mutations, and increments generation counters.

---

### optimizer.py

#### Optimizer
The master user-facing orchestrator class coordinating the entire memetic search process, handling keyboard interrupts, and managing telemetry systems.

- **Attributes**
  - `config` (ExperimentConfig): System configuration settings.
  - `state` (OptimizationState): Evolutionary search state.
  - `run_dir` (Path): Output run folder.
  - `cg` (CityGraph): Underlying drivable street network.
  - `sampler` (DirectDemandSampler): Demand distribution model.
  - `raw_config` (dict): raw YAML parsed dictionary.
  - `engine` (MemeticEngine): Main algorithm engine.
  - `surrogate` (StaticSurrogateEvaluator): Fast surrogate evaluator database.
  - `preservation` (StatePreservationEngine): State checkpointing engine.
  - `telemetry` (TelemetryEngine): Telemetry logger engine.
  - `adaptive` (AdaptiveController): Stagnation mutation scaler.

- **Methods**
  - `__init__(self, run_dir: Path) -> None`
    - Parameters: Past run folder to resume.
    - Outputs: None.
    - Primary Purpose: Instantiates the optimizer by loading the configuration and deserializing checkpoint data.
  - `create(cls, config_path: str | Path) -> Optimizer`
    - Parameters: YAML config path.
    - Outputs: Optimizer instance.
    - Primary Purpose: Instantiates a fresh optimizer run, creating standard workspace outputs.
  - `_init_engines(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Initializes components, maps synthetic and real city geometries, configures surrogate evaluators, and injects a custom, high-fidelity evaluate override that evaporates and deposits pheromones during the genetic search.
  - `start(self) -> None`
    - Parameters: None.
    - Outputs: None.
    - Primary Purpose: Executes the main generational search loop. Monitors stagnation counts, updates adaptive mutation rates, logs lineage csv and JSON snapshot telemetry, saves periodic checkpoints, and guarantees atomic state serialization upon manual keyboard interrupts.

---

## 9. Operational Workflow: How to Get Started

To build and run a simulation from scratch, modules must be instantiated in the following dependency order.

### Step 1: Configuration and Environment
Load your project configuration (YAML) and initialize the base spatial graph.
```python
import yaml
from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler

# Load config
with open('configs/iligan_configs.yaml', 'r') as f:
    cfg = yaml.safe_load(f)

# Initialize CityGraph (Physical Road Network)
city = CityGraph(bbox=tuple(cfg["city_graph"]["bbox"]))

# Initialize Sampler (Demand Surface)
sampler = DirectDemandSampler(city=city, config=cfg.get("ddm"))
```

### Step 2: Transit Infrastructure
Generate the jeepney routes. This step relies on the demand sampler to find high-value corridors.
```python
from utils.route import RouteGenerator

generator = RouteGenerator(city, sampler)
routes = [generator.generate(n_points=5) for _ in range(3)]
```

### Step 3: Multi-Layer Graph Assembly
Initialize the `TravelGraph`. This stitches the physical street layer (L1) to your new transit loops (L2) to allow passenger pathfinding.
```python
from utils.travel_graph import TravelGraph

tg = TravelGraph(city, config=cfg.get("travel_graph"), routes=routes)
```

### Step 4: Simulation Orchestration
Use the `SimulationSetup` wrapper to handle the complex instantiation of jeeps, passengers, and systems.
```python
from utils.simulation import SimulationSetup

setup = SimulationSetup("IliganCity", cfg, routes)
sim = setup.build()

# The simulation is now fully 'hydrated' with:
# - sim.jeep_system
# - sim.passenger_generator
```

### Step 5: Optimization & Local Search
Initialize the global pheromone landscape and apply spatial mutation operators to improve the route system under active passenger demand.
```python
from utils.pheromone import PheromoneMatrix
from utils.local_search import ACOLocalSearch

# 1. Initialize Pheromone demand matrix
pheromones = PheromoneMatrix(city.graph, cfg)

# 2. Compute demand-service gaps based on current fleet deployment
pheromones.gaps = pheromones.calculate_demand_service_gaps(sim.jeep_system)

# 3. Initialize the optimization local search engine
engine = ACOLocalSearch(cg=city, base_window_size=15)

# 4. Mutate routes (e.g. apply Spatial Attraction to capture underserved demand)
engine.strategy_spatial_attraction(routes, pheromones, intensity=2.0)
```

### Step 6: Execution
Run the simulation and extract the resulting metrics and paths.
```python
# Run the simulation
result = sim.run()

# Access metrics
print(f"Completed Journeys: {result.metrics['completed_count']}")
```

### Step 7: Visualization
Compile the collected simulation frames into a GIF for review.
```python
from utils.visualization import compile_to_gif

gif_bytes = compile_to_gif(sim.frames, fps=10, export_to="utils/.cache/latest_sim.gif")
```
