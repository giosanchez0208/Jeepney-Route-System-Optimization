"""Jeepney route network optimization toolkit.

A hybrid GA/ACO memetic optimizer for informal paratransit route networks, evaluated by
an agent-based commuter simulation. See docs/architecture.md for module-level detail.

Conventions
-----------
* All speed values on simulation-facing modules are km/h.
* One simulation tick equals ``seconds_per_tick`` seconds (10 s in the production profile).
* Underscore-prefixed helpers are internal to their file; the names below are the public API.

Environment
-----------
* ``node``                  -> ``Node(lon, lat, layer=None)``
* ``directed_edge``         -> ``DirEdge(start, end, is_drivable, weight=1, id=None,
                                next_edges=None, type=None)``
* ``city_graph``            -> ``CityGraph(bbox=None, name="UrbanNetwork", landmarks=None,
                                pbf_path=..., use_api=False, verbose=False)``
* ``toy_city``              -> ``build_toy_city(ToyCityConfig)``, ``ToyDDM``,
                                ``toy_setup_from_yaml(...)``. Drop-in replacements for
                                ``CityGraph`` / ``DirectDemandSampler`` that build in
                                milliseconds with no OSM or TomTom dependency.
* ``direct_demand_sampler`` -> ``DirectDemandSampler``, ``DDMConfig``, ``TrafficClient``

Routes and pathfinding
----------------------
* ``route``                 -> ``Route(city_graph, path, id=None)``,
                                ``RouteGenerator(city_graph, sampler, verbose=False)``
* ``travel_graph``          -> ``TravelGraph(cg, config, routes=None, route_generator=None,
                                n_routes=5, n_points=4)``. The three-layer walk/ride/transfer
                                construction that passengers are routed through.

Agents and simulation
---------------------
* ``passenger``             -> ``Passenger(start_pos, journey, speed, spawn_time=0,
                                seconds_per_tick=1)``
* ``passenger_generator``   -> ``PassengerGenerator(tg, od_gen, rate_per_100, stdev,
                                speed=5.0, seconds_per_tick=1)``
* ``jeep``                  -> ``Jeep(route, currPos, speed, max_capacity=16,
                                seconds_per_tick=1)``
* ``jeep_system``           -> ``JeepSystem(jeeps, routes, weight_tolerance=50.0,
                                equidistant_spawn=True)``, ``FleetAllocator``
* ``simulation``            -> ``SimulationSetup``, ``Simulation``, ``SimulationResult``
* ``simulation_parallel``   -> ``ParallelSimulationRunner``. Evaluates a population across a
                                process pool; each worker holds the environment once.

Optimization
------------
* ``pheromone``             -> ``PheromoneMatrix(all_edges, initial_tau=1.0, rho=0.1, q=1000.0)``
* ``local_search``          -> ``ACOLocalSearch(cg, p_local=0.5, base_window_size=15)``.
                                The three Lamarckian operators: spatial attraction,
                                redundancy repulsion, circuity pruning.
* ``genetic``               -> ``Chromosome(routes, allocation, pheromones)``,
                                ``MemeticAlgorithm(cg, local_search, target_route_count)``
* ``optimizer_config``      -> ``ExperimentConfig``
* ``optimizer_adaptive``    -> ``AdaptiveController``
* ``optimizer_engine``      -> ``MemeticEngine``
* ``optimizer_telemetry``   -> ``TelemetryEngine``
* ``optimizer_orchestrator_io`` -> ``StatePreservationEngine``, ``OptimizerBuilder``
* ``optimizer``             -> ``Optimizer``. The master orchestrator; start here.

Evaluation and visualization
----------------------------
* ``evaluation_metrics``    -> stateless metrics over primitives: Jaccard, cosine, graph edit
                                distance, discrete Frechet, 1D/2D Wasserstein, KS, Shannon
                                entropy, Spearman/Kendall.
* ``post_evaluation``       -> the same metrics lifted onto ``Route`` / ``Chromosome`` /
                                ``SimulationResult`` objects.
* ``visualization``         -> ``draw_all(...)``, ``compile_to_gif(...)``,
                                ``LiveTkinterVisualizer``
* ``travel_graph_3d_vis``   -> ``TravelGraph3DVisualizer``. Renders the three layers as
                                stacked planes so one journey can be traced across them.

Convenience
-----------
* ``pipeline``              -> ``reuse_citygraph(path)``, ``reuse_ddm(path)``,
                                ``generate_route_system(...)``, ``build_pheromone_matrix(...)``,
                                ``mutate_attraction`` / ``mutate_repulsion`` / ``mutate_pruning``.
                                The facade the scripts and notebooks use instead of wiring the
                                layers by hand.
"""
