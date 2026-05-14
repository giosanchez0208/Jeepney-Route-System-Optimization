"""Flow: import utils -> access the jeepney routing toolkit.

Main modules exposed by this package:
- node.py -> Node(lon: float, lat: float, layer: Optional[int] = None) -> None
- directed_edge.py -> DirEdge(start: Node, end: Node, is_drivable: bool, weight: int = 1, id: Optional[str] = None, next_edges: Optional[list[str]] = None, type: Optional[str] = None) -> None
- city_graph.py -> CityGraph(query: str) -> None
- route.py -> Route(city_graph: CityGraph, path: Optional[list[DirEdge]] = None, od_gen: Optional[TrafficAwareODGenerator] = None) -> None
- travel_graph.py -> StaticTravelGraph(cg: CityGraph) -> None and TravelGraph(stg: StaticTravelGraph, routes: list[Route]) -> None
- passenger.py -> Passenger(start_pos: tuple[float, float], journey: list[DirEdge], speed: float, spawn_tick: int = 0) -> None
- passenger_generator.py -> PassengerGenerator(tg: TravelGraph, od_gen: TrafficAwareODGenerator, rate_per_100: float, stdev: float, speed: float = 5.0) -> None
- od_generator.py -> TrafficAwareODGenerator(cg: CityGraph, traffic_csv_path: str | Path, betas: Optional[dict[str, float]] = None) -> None
- jeep.py -> Jeep(route: Route, currPos: tuple[float, float], speed: float) -> None
- jeep_system.py -> JeepSystem(jeeps: list[Jeep], routes: list[Route], weight_tolerance: float = 50.0, equidistant_spawn: bool = True) -> None
- pheromone.py -> PheromoneMatrix(all_edges: Iterable[Any], initial_tau: float = 1.0, rho: float = 0.1, q: float = 1000.0) -> None
- local_search.py -> ACOLocalSearch(cg: Any, p_local: float = 0.5, base_window_size: int = 15) -> None
- genetic.py -> Chromosome(routes: list[Route], allocation: dict[Route, int], pheromones: PheromoneMatrix) -> None and MemeticAlgorithm(cg: Any, local_search: ACOLocalSearch, target_route_count: int) -> None
- visualizer.py -> StaticVisualizer(bounds: tuple[float, float, float, float], ...) -> None, DynamicVisualizer(StaticVisualizers: list[StaticVisualizer], title: Optional[str] = None) -> None, LiveVisualizer(bounds: tuple[float, float, float, float], ...) -> None
- travel_graph_3d_vis.py -> TravelGraph3DVisualizer(travel_graph: TravelGraph, journey: Optional[list[DirEdge]] = None, *, mode: MapMode = "light_nolabels", edge_thickness: float = 2.6, journey_thickness: float = 4.2, node_radius: float = 42, layer_opacity: float = 0.56) -> None
- simulation.py -> SimulationSetup(city_query: str, config: dict, routes: Optional[list[Route]] = None) -> None, SimulationResult(fitness_score: float, metrics: dict[str, Any], recorded_paths: list[tuple[Any, float]], jeep_system: Optional[JeepSystem] = None, pheromones: Optional[PheromoneMatrix] = None, sim_id: Optional[str] = None) -> None, and Simulation(city_query: str, bounds: tuple[float, float, float, float], jeep_system: JeepSystem, passenger_generator: PassengerGenerator, max_ticks: int, beta_penalty: float = 2.0, alpha_std_penalty: float = 0.5, visualizer: bool = False, vis_kwargs: Optional[dict[str, Any]] = None, config: Optional[dict] = None) -> None

Use these module files for the public API; underscore-prefixed helpers stay
internal to their file.
"""

