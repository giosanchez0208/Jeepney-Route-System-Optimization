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

## 2. Spatial Data Atoms

### Node (`utils/node.py`)
The atomic spatial unit used throughout the system.
- **Attributes**: `id` (unique string), `lon`, `lat`, `layer` (0-3).
- **Immutability**: `lon` and `lat` cannot be modified after initialization.
- **Methods**:
    - `__init__(lon: float, lat: float, layer: Optional[int] = None)`
    - `draw(context: tuple, image: PIL.Image, color: str, radius: int)`

### DirEdge (`utils/directed_edge.py`)
A directed link representing a physical or logical step between two nodes.
- **Attributes**: `start` (Node), `end` (Node), `is_drivable` (bool), `weight` (float), `type` (string).
- **Methods**:
    - `__init__(start, end, is_drivable=False, weight=None, id=None, next_edges=None, type=None)`
    - `getLength() -> float`: Returns the pre-computed Haversine distance in meters.
    - `isConnectedTo(other: DirEdge) -> bool`: Checks if this edge's end node matches the other's start node.
    - `getType() -> str`: Returns the semantic type based on start/end layers (e.g., `ride`, `wait`, `alight`).
    - `draw(context, image, color, width)`

---

## 3. Graph Infrastructure

### CityGraph (`utils/city_graph.py`)
Manages the physical road network skeleton, typically pruned to arterial corridors.
- **Attributes**: `nodes` (list), `graph` (list of DirEdges), `landmarks` (dict).
- **Methods**:
    - `__init__(bbox, name, landmarks, pbf_path, use_api, verbose, cache_dir, cache_prefix)`
    - `inject_toy_data(nodes, edges)`: Populates the graph with synthetic data for fast testing.
    - `find_shortest_path(start: Node, end: Node) -> list[DirEdge]`: Returns the A* optimal path.
    - `get_bounds(margin: float = 0.05) -> tuple`: Returns `((min_lon, max_lat), (max_lon, min_lat))`.
    - `draw(size=800, only_drivable=False) -> Image`: Renders the network skeleton.
    - `stitch_graph()`: Internal logic to establish DirEdge connectivity.

### DirectDemandSampler (`utils/direct_demand_sampler.py`)
Models passenger demand by blending TomTom traffic flow with structural centrality.
- **Attributes**: `node_probabilities` (dict), `max_prob` (float).
- **Methods**:
    - `__init__(city, config, verbose)`
    - `get_point(only_drivable: bool = False) -> Node`: Returns a node sampled via O(1) alias method.
    - `draw_density(img_map, context, num_points, only_drivable)`: Renders a demand heatmap.

### TravelGraph (`utils/travel_graph.py`)
A multi-layered graph (L1, L2, L3) that enables complex journey planning involving walking and transfers.
- **Methods**:
    - `__init__(cg, config, routes, route_generator, n_routes, n_points, verbose)`
    - `findShortestJourney(origin: Node, destination: Node) -> list[DirEdge]`: Returns a full passenger trip.
    - `draw(context, image, color_by_layer)`

---

## 4. Transit System Modules

### Route (`utils/route.py`)
A closed-loop transit line operating on Layer 2.
- **Attributes**: `id`, `path` (list of DirEdges), `designated_color`.
- **Methods**:
    - `__init__(city_graph, path, id)`
    - `draw(context, image, color, width)`

### RouteGenerator (`utils/route.py`)
Automates the creation of transit lines based on demand sampling.
- **Methods**:
    - `generate(n_points=4, max_retries=10) -> Route`: Creates a valid transit loop.

### RouteSystem (`utils/route.py`)
A container for multiple routes, primarily used for visualization.
- **Methods**:
    - `add_route(route)`
    - `draw(context, image, line_width, dash_length)`: Renders all routes with dashed overlap handling.

### Jeep (`utils/jeep.py`)
A vehicle actor following a specific Route.
- **Attributes**: `curr_pos`, `onboard_passengers` (set), `curr_passenger_count`.
- **Methods**:
    - `update()`: Advances position along the route.
    - `nodes_passed_this_frame() -> list[tuple[Node, Route]]`: Returns nodes passed in the current tick.
    - `get_weight_if(start_node, end_node) -> float`: Predicts remaining travel weight.
    - `draw(context, image, radius)`

### JeepSystem (`utils/jeep_system.py`)
Coordinates the fleet, passenger boarding, and alighting logic.
- **Methods**:
    - `__init__(jeeps, routes, weight_tolerance, equidistant_spawn)`
    - `add_passenger(passenger: Passenger)`
    - `update()`: Executes a single simulation step for all vehicles and active passengers.
    - `draw(context, image, radius)`

### FleetAllocator (`utils/jeep_system.py`)
Calculates optimal vehicle distribution across routes using Mohring's square root rule.
- **Methods**:
    - `allocate_by_mohring(total_fleet, routes, sampler, tg, sample_size) -> dict[Route, int]`
    - `evaluate_allocation(allocation, sampler) -> dict`

## 5. Optimization and Local Search

### PheromoneMatrix (`utils/pheromone.py`)
Tracks spatial network demand and passenger traffic history across the city graph.
- **Attributes**: `initial_tau` (float), `rho` (float), `q` (float), `tau` (dict-like view), `gaps` (dict mapping DirEdge to float gap scores).
- **Methods**:
    - `__init__(all_edges: Iterable[DirEdge], config: dict, sim_result: Optional[SimulationResult] = None)`
    - `update_pheromones(sim_result: SimulationResult)`: Evaporates pheromones and deposits new ones based on simulated passenger travel costs.
    - `calculate_demand_service_gaps(jeep_system: JeepSystem) -> dict[DirEdge, float]`: Computes the difference between demand and supply (`gap = tau - supply`).
    - `draw(context: tuple, image: PIL.Image) -> PIL.Image`: Renders a high-contrast demand heatmap (purple to yellow) with linewidths scaling quadratically with density.

### ACOLocalSearch (`utils/local_search.py`)
Applies demand-driven mutations and spatial heuristics to optimize route systems.
- **Attributes**: `cg` (CityGraph), `p_local` (float), `base_window_size` (int).
- **Methods**:
    - `__init__(cg: CityGraph, p_local: float = 0.5, base_window_size: int = 15)`
    - `calculate_route_similarity(route_a: Route, route_b: Route) -> float`: Computes the discrete Fréchet distance between two routes.
    - `strategy_spatial_attraction(routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> Optional[Route]`: Splices a detour toward an underserved demand corridor.
    - `strategy_redundancy_repulsion(routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> Optional[Route]`: Removes redundant overlaps in overserved corridors.
    - `strategy_tortuosity_pruning(routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> tuple[int, Optional[Route]]`: Smooths out inefficient wiggles while preserving gap immunity.
    - `optimize_system(routes: list[Route], pheromones: PheromoneMatrix, intensity: float = 1.0) -> dict`: One-shot runner applying all active mutations stochastically.

---

## 6. Passenger Lifecycle

### Passenger (`utils/passenger.py`)
A state-machine actor (WALKING -> WAITING -> RIDING -> DONE).
- **Attributes**: `state`, `journey` (list of DirEdges), `current_jeep`.
- **Methods**:
    - `update()`: Advances the passenger through their journey.
    - `get_target_route_idx() -> int`: Returns the ID of the route the passenger is waiting for.
    - `get_target_alight_node() -> Node`: Returns the node where the passenger must exit the vehicle.
    - `draw(context, image, size)`

### PassengerGenerator (`utils/passenger_generator.py`)
Manages stochastic passenger spawning and lifecycle tracking.
- **Methods**:
    - `update()`: Spawns new passengers and advances existing ones.
    - `get_all_generated_journeys() -> list[list[DirEdge]]`: Exports journey data for demand analysis.

---

## 7. Simulation and Analysis

### Simulation (`utils/simulation.py`)
The primary execution engine.
- **Methods**:
    - `run() -> SimulationResult`: Executes the full simulation loop.
    - `update()`: Steps the simulation forward by 1 tick.
    - `draw() -> Image`: Generates a composite dashboard frame.

### SimulationSetup (`utils/simulation.py`)
Orchestrates the instantiation sequence for the simulation stack.
- **Methods**:
    - `build() -> Simulation`: Constructs a ready-to-run environment.

---

## 8. Setup and Visualization Helpers

### Toy City (`utils/toy_city.py`)
Synthetic environment for rapid diagnostics.
- **Methods**:
    - `build_toy_city(config) -> CityGraph`: Generates a Manhattan-grid road network.
    - `toy_setup_from_yaml(yaml_path) -> (CityGraph, ToyDDM, dict)`: One-shot environment loader.

### Visualization Helpers (`utils/visualization.py`)
- **compile_to_gif(frames, fps, export_to) -> bytes**: Encodes a list of PIL Images into a GIF.
- **draw_all(drawable_objects, context, base_image, resolution, text) -> Image**: Layers multiple objects (routes, jeeps, passengers) onto a single canvas.
- **LiveTkinterVisualizer**: A threaded GUI class for real-time simulation playback.

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

