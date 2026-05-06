# UTILS Guide

## `__init__.py`
Flow: import utils -> access the jeepney routing toolkit.

Main modules exposed by this package:
- node.py -> `Node(lon: float, lat: float) -> None`
- directed_edge.py -> `DirEdge(start: Node, end: Node, is_drivable: bool, weight: int = 1, id: Optional[str] = None, next_edges: Optional[list[str]] = None, type: Optional[str] = None) -> None`
- city_graph.py -> `CityGraph(query: str) -> None`
- route.py -> `Route(city_graph: CityGraph, path: Optional[list[DirEdge]] = None, od_gen: Optional[TrafficAwareODGenerator] = None) -> None`
- travel_graph.py -> `StaticTravelGraph(cg: CityGraph) -> None` and `TravelGraph(stg: StaticTravelGraph, routes: list[Route]) -> None`
- passenger.py -> `Passenger(start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_tick: int = 0) -> None`
- passenger_generator.py -> `PassengerGenerator(tg: TravelGraph, od_gen: TrafficAwareODGenerator, rate_per_100: float, stdev: float, speed: float = 5.0) -> None`
- od_generator.py -> `TrafficAwareODGenerator(cg: CityGraph, traffic_csv_path: str | Path, betas: Optional[dict[str, float]] = None) -> None`
- jeep.py -> `Jeep(route: Route, currPos: tuple[float, float], speed: float) -> None`
- jeep_system.py -> `JeepSystem(jeeps: list[Jeep], routes: list[Route], weight_tolerance: float = 50.0, equidistant_spawn: bool = True) -> None`
- pheromone.py -> `PheromoneMatrix(all_edges: Iterable[Any], initial_tau: float = 1.0, rho: float = 0.1, q: float = 1000.0) -> None`
- local_search.py -> `ACOLocalSearch(cg: Any, p_local: float = 0.5, base_window_size: int = 15) -> None`
- genetic.py -> `Chromosome(routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix) -> None` and `MemeticAlgorithm(cg: Any, local_search: ACOLocalSearch, target_route_count: int) -> None`
- visualizer.py -> `StaticVisualizer(bounds: tuple[float, float, float, float], ...) -> None`, `DynamicVisualizer(StaticVisualizers: list[StaticVisualizer], title: Optional[str] = None) -> None`, and `LiveVisualizer(bounds: tuple[float, float, float, float], ...) -> None`
- layered_visualizer.py -> `LayeredVisualizer(city_graph: CityGraph, journey: list[DirEdge], title: Optional[str] = None, *, mode: MapMode = "light_nolabels", labels_on: bool = False, node_color: str = "#6fbaf0", node_radius: float = 40, edge_color: str = "#d1d1d1", edge_thickness: float = 2, journey_color: str = "#d62728", journey_thickness: float = 2.0, layer_opacity: float = 0.5, legend_on: bool = True, Routes: Optional[list["Route"]] = None, route_thickness: float = 2.0, nodes_on: bool = True) -> None`
- simulation.py -> `SimulationSetup(city_query: str, config: dict, routes: Optional[list[Route]] = None) -> None`, `SimulationResult(fitness_score: float, metrics: dict[str, Any], recorded_paths: list[tuple[Any, float]], jeep_system: Optional[JeepSystem] = None, pheromones: Optional[PheromoneMatrix] = None, sim_id: Optional[str] = None) -> None`, and `Simulation(city_query: str, bounds: tuple[float, float, float, float], jeep_system: JeepSystem, passenger_generator: PassengerGenerator, max_ticks: int, beta_penalty: float = 2.0, alpha_std_penalty: float = 0.5, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None, config: Optional[dict] = None) -> None`

Use these module files for the public API; underscore-prefixed helpers stay internal.

## `node.py`
Flow: lon/lat -> Node -> identity, layer, and cached coordinate math.

Constructor:
- `Node(lon: float, lat: float) -> None`

Inputs: longitude and latitude.
Outputs: a Node object with stable identity and coordinate fields.
Imported modules used: `math.radians` and `Optional`.

## `directed_edge.py`
Flow: Node pair -> DirEdge -> length, connectivity, and type checks -> stitched route links.

Constructor:
- `DirEdge(start: Node, end: Node, is_drivable: bool, weight: int = 1, id: Optional[str] = None, next_edges: Optional[list[str]] = None, type: Optional[str] = None) -> None`

Methods:
- `getLength(self) -> float`
- `isConnectedTo(self, other: DirEdge) -> bool`
- `getType(self) -> str`

Inputs: two Node objects plus edge metadata.
Outputs: length in meters, connectivity boolean, and a layer-based edge type.
Imported modules used: `Node` and math trig helpers.

## `city_graph.py`
Flow: place query -> OSM drive graph -> Node/DirEdge objects -> stitched graph -> cached shortest paths.

Constructor:
- `CityGraph(query: str) -> None`

Methods:
- `stitch_graph(self) -> None`
- `info(self) -> str`
- `findShortestPath(self, start: Node, end: Node) -> list[DirEdge]`

Inputs: query string.
Outputs: a CityGraph with nodes, graph, info(), and shortest-path edge lists.
Imported modules used: `networkx`, `osmnx`, `InsufficientResponseError`, `Node`, `DirEdge`, `_getDistance`, and `_stitch`.

## `route.py`
Flow: CityGraph + optional OD sample or saved coordinates -> DirEdge path -> Route.

Constructor:
- `Route(city_graph: CityGraph, path: Optional[list[DirEdge]] = None, od_gen: Optional[TrafficAwareODGenerator] = None) -> None`

Methods:
- `route_from_coords(city_graph: CityGraph, coords_json: str) -> Route`

Inputs: a CityGraph, optional path data, OD generator output, or coordinate JSON.
Outputs: a Route object containing a list of DirEdge segments.
Imported modules used: `json`, `sample`, `cKDTree`, `numpy`, `Node`, `DirEdge`, `CityGraph`, and `TrafficAwareODGenerator`.

## `travel_graph.py`
Flow: CityGraph + routes + config weights -> layered travel network -> shortest journey queries.

Constructors:
- `StaticTravelGraph(cg: CityGraph) -> None`
- `TravelGraph(stg: StaticTravelGraph, routes: list[Route]) -> None`

Methods:
- `findShortestJourney(self, start: Node, end: Node) -> list[DirEdge]`
- `calculateJourneyDistance(self, start: Node, end: Node) -> float`
- `calculateJourneyWeight(self, start: Node, end: Node) -> float`

Inputs: a CityGraph and route list.
Outputs: layered DirEdge paths, journey distances, and journey weights.
Imported modules used: `yaml`, `Path`, `Node`, `DirEdge`, `_getDistance`, `CityGraph`, and `Route`.

## `passenger.py`
Flow: start position + journey -> passenger state machine -> walking, waiting, riding, done.

Constructor:
- `Passenger(start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_tick: int = 0) -> None`

Methods:
- `update(self) -> None`
- `get_target_route_idx(self) -> Optional[int]`
- `get_target_alight_node(self) -> Optional[Node]`
- `get_planned_ride_weight(self) -> float`
- `complete_ride(self) -> None`
- `get_remaining_time(self) -> float`

Inputs: a start position, a DirEdge journey, movement speed, and spawn tick.
Outputs: updated passenger state plus route and timing queries.
Imported modules used: `Node`, `DirEdge`, `Jeep`, and `Optional`.

## `passenger_generator.py`
Flow: OD demand + travel graph + spawn schedule -> new passengers -> archived journeys.

Constructor:
- `PassengerGenerator(tg: TravelGraph, od_gen: TrafficAwareODGenerator, rate_per_100: float, stdev: float, speed: float = 5.0) -> None`

Methods:
- `update(self) -> None`
- `get_all_generated_journeys(self) -> list[list[DirEdge]]`

Inputs: a TravelGraph, TrafficAwareODGenerator, spawn rate, deviation, and speed.
Outputs: active passengers, archived passengers, and generated journey lists.
Imported modules used: `DirEdge`, `Passenger`, `TravelGraph`, `TrafficAwareODGenerator`, and `random`.

## `od_generator.py`
Flow: traffic CSV + CityGraph nodes -> KDTree match -> pedestrian demand -> weighted origin sampling.

Constructor:
- `TrafficAwareODGenerator(cg: CityGraph, traffic_csv_path: str | Path, betas: Optional[dict[str, float]] = None) -> None`

Methods:
- `generate_origins(self, n_points: int = 10000) -> list[Node]`

Inputs: a CityGraph, a traffic CSV path, and optional beta coefficients.
Outputs: node_vped values and sampled Node origin lists.
Imported modules used: `numpy`, `pandas`, `cKDTree`, `Path`, `CityGraph`, and `Node`.

## `jeep.py`
Flow: route + start position + speed -> moving jeep state -> passenger and node queries.

Constructor:
- `Jeep(route: Route, currPos: tuple[float, float], speed: float) -> None`

Methods:
- `update(self) -> None`
- `nodes_passed_this_frame(self) -> Optional[list[tuple[Node, Route]]]`
- `modifyPassenger(self, amt: int) -> None`
- `returnPathFrom(self, start_node: Node, end_node: Node) -> list[DirEdge]`
- `getWeightIf(self, start_node: Node, end_node: Node) -> Optional[float]`

Inputs: a Route, a starting coordinate pair, and speed.
Outputs: updated position, heading, and per-frame node crossings.
Imported modules used: `Node`, `Route`, `DirEdge`, and `_getDistance`.

## `jeep_system.py`
Flow: routes + jeeps + pheromones -> fleet allocation -> passenger boarding -> system update loop.

FleetAllocator methods:
- `allocate_by_mohring(total_fleet: int, routes: list, pheromones: Any, cg: Any, gen0_sample_size: int = 2000, route_baseline_tau: float = 100.0) -> dict`
- `evaluate_allocation(allocation: dict, pheromones: Any) -> dict`

Constructor:
- `JeepSystem(jeeps: list[Jeep], routes: list[Route], weight_tolerance: float = 50.0, equidistant_spawn: bool = True) -> None`

Methods:
- `add_passenger(self, passenger: Passenger) -> None`
- `update(self) -> None`

Inputs: jeeps, routes, weight tolerance, pheromones, and the city graph.
Outputs: fleet allocations, allocation reports, and a live system state.
Imported modules used: `Jeep`, `Passenger`, `Route`, plus math and random helpers.

## `pheromone.py`
Flow: passenger paths + route supply -> evaporated pheromone matrix -> demand-service gap.

Constructor:
- `PheromoneMatrix(all_edges: Iterable[Any], initial_tau: float = 1.0, rho: float = 0.1, q: float = 1000.0) -> None`

Methods:
- `update_pheromones(self, passenger_records: list[tuple[list[Any], float]]) -> None`
- `calculate_demand_service_gaps(self, routes: list[Any], default_jeep_weight: float = 1.0) -> dict[Any, float]`

Inputs: all network edges, passenger records, and route lists.
Outputs: updated tau values and a gap dictionary keyed by edge.
Imported modules used: `Iterable` and `Any`.

## `local_search.py`
Flow: routes + pheromones + demand gaps -> local edits -> improved route layout.

Constructor:
- `ACOLocalSearch(cg: Any, p_local: float = 0.5, base_window_size: int = 15) -> None`

Methods:
- `calculate_route_similarity(self, route_a: Route, route_b: Route) -> float`
- `strategy_spatial_attraction(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict, intensity: float = 1.0) -> Optional[Route]`
- `strategy_redundancy_repulsion(self, routes: list[Route], gaps: dict, intensity: float = 1.0) -> Optional[Route]`
- `strategy_tortuosity_pruning(self, routes: list[Route], intensity: float = 1.0) -> tuple[int, Optional[Route]]`
- `optimize_system(self, routes: list[Route], pheromones: PheromoneMatrix, gaps: dict, intensity: float = 1.0) -> dict`

Inputs: CityGraph access, routes, pheromone matrix, demand gaps, and intensity.
Outputs: optional route replacements plus an action summary from optimize_system().
Imported modules used: `Route` and `PheromoneMatrix`, plus math and random helpers.

## `genetic.py`
Flow: parent routes + pheromones -> crossover -> mutation -> scored child population.

Constructors:
- `Chromosome(routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix) -> None`
- `MemeticAlgorithm(cg: Any, local_search: ACOLocalSearch, target_route_count: int) -> None`

Methods:
- `crossover_topological_hub(self, parent_a: Chromosome, parent_b: Chromosome) -> list[Route]`
- `inherit_pheromones(self, parent_a: Chromosome, parent_b: Chromosome) -> PheromoneMatrix`
- `evaluate_chromosome(self, chrom: Chromosome, total_fleet: int) -> float`
- `apply_lamarckian_mutation(self, child: Chromosome, target_cost: float, total_fleet: int) -> bool`
- `run_evolution(self, population: list[Chromosome], generations: int, total_fleet: int, out_dir: Path) -> tuple[list[Chromosome], list[tuple[int, float, float]]]`

Inputs: CityGraph-like data, local search, parent chromosomes, generations, and fleet size.
Outputs: updated chromosomes, costs, history samples, and saved checkpoints.
Imported modules used: `Route`, `PheromoneMatrix`, `ACOLocalSearch`, and `FleetAllocator`.

## `visualizer.py`
Flow: map bounds + nodes/edges/routes/jeeps/passengers -> rendered image, GIF, or live window.

Constructor:
- `Passenger(curr_lon: float, curr_lat: float) -> None`
- `StaticVisualizer(bounds: tuple[float, float, float, float], title: Optional[str] = None, nodes: Optional[list[Node]] = None, edges: Optional[list[DirEdge]] = None, routes: Optional[list[Route]] = None, jeeps: Optional[list[Jeep]] = None, passengers: Optional[list[Any]] = None, pheromones: Optional[dict[tuple[float, float, float, float], float]] = None, system_manager: Optional[Any] = None, mode: MapMode = "light_nolabels") -> None`
- `DynamicVisualizer(StaticVisualizers: list[StaticVisualizer], title: Optional[str] = None) -> None`
- `LiveVisualizer(bounds: tuple[float, float, float, float], title: Optional[str] = None, nodes: Optional[list[Node]] = None, edges: Optional[list[DirEdge]] = None, routes: Optional[list[Route]] = None, jeeps: Optional[list[Jeep]] = None, passengers: Optional[list[Any]] = None, system_manager: Optional[Any] = None, mode: MapMode = "light_nolabels", sim_tick_rate: float = 0.05, render_fps: int = 30) -> None`

Methods:
- `StaticVisualizer.draw(self, mode: Optional[MapMode] = None) -> Image.Image`
- `StaticVisualizer.display(self, mode: Optional[MapMode] = None) -> None`
- `StaticVisualizer.export(self, filename: str, mode: Optional[MapMode] = None, scale_up: int = 1) -> None`
- `DynamicVisualizer.draw(self, mode: MapMode = "light_nolabels", fps: int = 2) -> Image.Image`
- `DynamicVisualizer.display(self, mode: MapMode = "light_nolabels", fps: int = 2) -> None`
- `DynamicVisualizer.export(self, filename: str, mode: MapMode = "light_nolabels", fps: int = 2, scale_up: int = 1) -> None`
- `LiveVisualizer.display(self) -> None`

Inputs: bounds, map mode, and optional network objects.
Outputs: PIL images, exported files, or a Tkinter display window.
Imported modules used: `contextily`, `matplotlib`, `tkinter`, `numpy`, `requests`, `PIL`, `Node`, `DirEdge`, `Route`, and `Jeep`.

## `layered_visualizer.py`
Flow: layered city graph + journey + routes -> projected canvas -> image export or display.

Constructor:
- `LayeredVisualizer(city_graph: CityGraph, journey: list[DirEdge], title: Optional[str] = None, *, mode: MapMode = "light_nolabels", labels_on: bool = False, node_color: str = "#6fbaf0", node_radius: float = 40, edge_color: str = "#d1d1d1", edge_thickness: float = 2, journey_color: str = "#d62728", journey_thickness: float = 2.0, layer_opacity: float = 0.5, legend_on: bool = True, Routes: Optional[list["Route"]] = None, route_thickness: float = 2.0, nodes_on: bool = True) -> None`

Methods:
- `draw(self, mode: Optional[MapMode] = None, labels_on: Optional[bool] = None, node_color: Optional[str] = None, node_radius: Optional[float] = None, edge_color: Optional[str] = None, edge_thickness: Optional[float] = None, journey_color: Optional[str] = None, journey_thickness: Optional[float] = None, layer_opacity: Optional[float] = None, legend_on: Optional[bool] = None, nodes_on: Optional[bool] = None) -> Image.Image`
- `display(self, mode: Optional[MapMode] = None, labels_on: Optional[bool] = None, node_color: Optional[str] = None, node_radius: Optional[float] = None, edge_color: Optional[str] = None, edge_thickness: Optional[float] = None, journey_color: Optional[str] = None, journey_thickness: Optional[float] = None, layer_opacity: Optional[float] = None, legend_on: Optional[bool] = None, nodes_on: Optional[bool] = None) -> None`
- `export(self, filename: str, mode: Optional[MapMode] = None, labels_on: Optional[bool] = None, node_color: Optional[str] = None, node_radius: Optional[float] = None, edge_color: Optional[str] = None, edge_thickness: Optional[float] = None, journey_color: Optional[str] = None, journey_thickness: Optional[float] = None, layer_opacity: Optional[float] = None, legend_on: Optional[bool] = None, nodes_on: Optional[bool] = None, scale_up: int = 1) -> None`

Inputs: CityGraph, journey edges, optional routes, styling options, and map mode.
Outputs: layered PNG-style images or an on-screen window.
Imported modules used: `matplotlib`, `tkinter`, `PIL`, `CityGraph`, `DirEdge`, `Node`, `Path`, `sample`, and typing helpers.

## `simulation.py`
Flow: setup -> graphs, routes, jeeps, passengers -> simulation ticks -> result export.

Constructors:
- `SimulationSetup(city_query: str, config: dict, routes: Optional[list[Route]] = None) -> None`
- `SimulationResult(fitness_score: float, metrics: dict[str, Any], recorded_paths: list[tuple[Any, float]], jeep_system: Optional[JeepSystem] = None, pheromones: Optional[PheromoneMatrix] = None, sim_id: Optional[str] = None) -> None`
- `Simulation(city_query: str, bounds: tuple[float, float, float, float], jeep_system: JeepSystem, passenger_generator: PassengerGenerator, max_ticks: int, beta_penalty: float = 2.0, alpha_std_penalty: float = 0.5, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None, config: Optional[dict] = None) -> None`

Methods:
- `SimulationSetup.build(self, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None) -> Simulation`
- `SimulationResult.export_map(self, area_query: str, out_dir: str, draw_pheromones: bool = True, draw_routes: bool = True) -> None`
- `SimulationResult.export_report(self, out_dir: str) -> None`
- `SimulationResult.from_file(cls, filepath: str) -> SimulationResult`
- `Simulation.update(self) -> None`
- `Simulation.run(self) -> SimulationResult`
- `Simulation.export_snapshot(self, filename: str, draw_routes: bool = True, draw_jeeps: bool = True, draw_passengers: bool = True) -> None`

Inputs: city query, configuration, routes, and runtime components.
Outputs: live simulation state plus serialized results, maps, and reports.
Imported modules used: `CityGraph`, `StaticTravelGraph`, `TravelGraph`, `TrafficAwareODGenerator`, `PassengerGenerator`, `JeepSystem`, `Route`, `Jeep`, `LiveVisualizer`, `StaticVisualizer`, `Passenger`, `PheromoneMatrix`, and `threading`.
