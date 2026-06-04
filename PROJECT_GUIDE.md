# Index

**Core Modules**
- [Node](#Node)
- [DirEdge](#DirEdge)
- [CityGraph](#CityGraph)
- [DirectDemandModel](#DirectDemandModel)
- [Routes](#Routes)
- [TravelGraph](#TravelGraph)

**Simulation Agents**
- [Jeep](#Jeep)
- [JeepSystem](#JeepSystem)
- [Passenger](#Passenger)
- [PassengerGenerator](#PassengerGenerator)

**Simulation Environment**
- [Simulation](#Simulation)

**Optimization Modules**
- [Pheromone](#Pheromone)
- [LocalSearch](#LocalSearch)
- [Genetic](#Genetic)

**Optimizer Orchestration**
- [ExperimentConfig](#ExperimentConfig)
- [AdaptiveController](#AdaptiveController)
- [MemeticEngine](#MemeticEngine)
- [StatePreservationEngine](#StatePreservationEngine)
- [TelemetryEngine](#TelemetryEngine)
- [Optimizer](#Optimizer)

**Configuration**
- [YAML-Configs](#YAML-Configs)

**Post-Optimization Evaluation**
- [EvaluationMetrics](#EvaluationMetrics)
- [PostEvaluation](#PostEvaluation)

**Simplified Facade**
- [SimplifiedFacade](#SimplifiedFacade)

___
# Core Modules
___
## Node
### Implementation

`Node` is initialized with `lon`, `lat`, and `layer` (in that order).
- `lon` and `lat` must be valid coordinates: `lon` $\in$ \[-180, 180\], `lat` $\in$ \[-90, 90\]
- `layer` must be a valid layer: `layer` $\in$`[0-3]`
___
## DirEdge
### Implementation

`DirEdge` is a **directed edge** initialized with two [nodes](#Node), where the first node is the beginning of this directed edge, and the second node is the end.

_Valid_ directed edges have nodes that have
1. different coordinates, but belong to the same layer
2. identical coordinates, but belong to different layers
3. layer transitions, provided they belong to the ff:
	- 0 $\rightarrow$ 0 : `default` 
	- 1 $\rightarrow$ 1 : `start_walk`
	- 2 $\rightarrow$ 2 : `ride`
	- 3 $\rightarrow$ 3 : `end_walk`
	- 1 $\rightarrow$ 2 : `wait`
	- 1 $\rightarrow$ 3 : `direct`
	- 2 $\rightarrow$ 3 : `alight`
	- 3 $\rightarrow$ 2 : `transfer`
	- *__NOTE__ :  The three-layer graph architecture will be further explained under [TravelGraph](#TravelGraph)*

To illustrate bi-directional edges, the researchers opted to use two directed edges to reduce architectural bloat.
___
## CityGraph

### Implementation

The CityGraph denotes the _traversable graph_ on `layer 0`. Here, we do two things:

1. Initialize the geographical area and its road network as [directed edges](#DirEdge) 
	- Information on the bounds is taken from a [config file](#YAML-Configs) as a `(lat1, lat2, lon1, lon2)` tuple.
	- Edge information is extracted from a `pbf` file, independently downloaded from [extract.bbbike.org](extract.bbbike.org) (although the code has implementation to download area itself, this is done for efficiency)
	- Assumption: All roads are bi-directional
	- Limitation: Does not account for one-way roads
	
2. Define which edges are "drivable"
	- More on [PUJ Arterial Function](#On-PUJ-Arterial-Function)

It is important to place the restriction on where jeeps are allowed to traverse to limit the exploration area to those roads. However, since passengers do not have the same restrictions, other roads must also be considered.
### On-PUJ-Arterial-Function

Guillen, Ishida, and Okamoto[^1] identify Public Utility Jeepneys (PUJs) as major modes of transportation utilized primarily for long-distance trips of 10 kilometers or more. Meanwhile, Tricycles and Pedicabs are used for short-distance trips of 1-3 kilometers to connect passengers to PUJ routes.
The study *specifies* that tricycles operate within tertiary routes and service residential areas. It does not state that they're exclusive to tricycles, so this was included regardless as the required structural bridge between restricted local access networks and larger secondary/primary arteries.
Thus, PUJs require routing exclusively on arterial roads because they act as the central transit arteries. They do not penetrate local, residential, or unclassified street networks.

**The following are a list of all the possible attributes for a road, what was included, what was left out, and why:**

Included:
- `primary`: Major transport routes linking large towns.
- `primary_link`: Slip roads and ramps connecting primary roads.
- `secondary`: Main transport arteries connecting districts.
- `secondary_link`: Slip roads and ramps connecting secondary roads.
- `tertiary`: Roads connecting local centers to the arterial network.
- `tertiary_link`: Slip roads and ramps connecting tertiary roads.
- `trunk`: High performance national routes.
- `trunk_link`: Slip roads and ramps connecting trunk roads.

Excluded:
- `residential`: Roads exclusively lined with housing.
- `living_street`: Shared spaces with pedestrian priority.
- `service`: Access roads for alleys, driveways, or commercial estates.
- `pedestrian`: Roads designated exclusively for foot traffic.
- `unclassified`: Minor local roads serving low traffic volumes.
- `motorway`: Controlled access highways restricted from PUJ use.
- `motorway_link`: Slip roads for controlled access highways.
- `footway`: Dedicated pedestrian walkways.
- `cycleway`: Dedicated bicycle infrastructure.
- `path`: Unspecified non-motorized transport routes.
- `track`: Unpaved agricultural or forestry roads.
- `steps`: Public stairways.

### TODO: Export images of the ff to include in study:

- Real image of used "Iligan City" region
- Road network
- Road types with legend
- Included edges
___
## DirectDemandModel
### Logic

The `DirectDemandSampler` synthesizes realistic spatial demand distributions across the [`CityGraph`](#CityGraph). Instead of sampling nodes uniformly, the direct demand model samples from empirically grounded probability distributions (based on traffic data from [Tomtom API](#On-Tomtom-API), more on converting traffic data to direct demand later) to generate a point more likely to land on a busy point than a point with no traffic.
### Implementation

1. **Centrality-Weighted Spatial Sampling**
	Because of external rate limits, we cannot query the live traffic API for every topological node, naive random sampling is structurally invalid for this task. As demonstrated by Xie and Levinson (2007), urban road networks exhibit extreme topological heterogeneity. A purely random spatial sample would disproportionately waste the limited API budget on low-volume residential streets while critically undersampling the arterials that govern actual traffic flow. Instead, we employ centrality-weighted spatial sampling: by utilizing [betweenness centrality](#On-Betweeness-Centrality) as the statistical sampling weight, the algorithm stochastically directs the limited API queries toward the structural backbone of the network. To execute this weighted sampling without replacement efficiently over thousands of nodes, the model implements the algorithm proposed by Efraimidis and Spirakis (2006). For each node, a random variate $U \in (0,1)$ is generated, and a selection key is calculated as $k_i = \ln(U) / c_i$, where $c_i$ is the node's betweenness centrality score. By sorting nodes by this key in descending order, the algorithm extracts a mathematically exact weighted random sample in a single pass.

2. **Arterial-Anchored Spatial Interpolation**
	We estimate traffic weights for all unqueried nodes using [Inverse Distance Weighting (IDW)](#On-Inverse-Distance-Weighting). Crucially, because the known data points are concentrated on the network's major arterials—the exact locations where urban congestion originates—the IDW algorithm is anchored to the network's choke points. The resulting interpolation naturally mimics real-world diffusion of traffic, accurately reflecting how congestion spillover gradients radiate outward from primary corridors into secondary and local streets. The model applies the [Haversine formula](#On-Haversine-Formula) to compute true great-circle distances [^4], ensuring spherical accuracy and numerical stability across geographic coordinates. This prevents distortion caused by planar geometry during the spatial interpolation process.

3. **Structural Weighting**
	We calculate [Betweenness Centrality](#On-Betweeness-Centrality) to identify structural network importance, which measures the exact frequency a node appears on the shortest paths across the graph [^5]. It establishes a baseline topological weight independent of live traffic conditions.

4. **Probability Resolution**
	Lowry (2014)[^3] proved that [Origin-Destination Centrality](#On-Origin-Destination-Centrality) operates as a highly accurate variable for interpolating traffic volumes across unmeasured nodes. 	The final demand probability ($P_i$) per node is calculated by fusing the empirical or imputed traffic weight ($W_i$) and the betweenness centrality ($C_i$). These are scaled by calibration parameters ($\alpha, \beta$) using the equation $P_i = W_i^\alpha \times C_i^\beta$.

5. **Alias Table Construction**
	The resolved probabilities are scaled and structured into a [Walker's Alias table](#On-Walker's-Alias-Table). This data structure guarantees $O(1)$ time complexity for all subsequent spatial sampling during route generation [^6].

#### Traffic Data Ingestion via TomTom API
The `TrafficClient` strictly isolates external network requests from the core mathematical engine. It queries the TomTom Traffic Flow API exclusively for the centrally-weighted target nodes selected in the sampling step above. The use of TomTom as a primary source for real-time and historical urban traffic data has been validated for generating reliable spatial-temporal traffic matrices in megacity environments (Sayed et al., 2026). From the API responses, the system extracts the real-time speed and the free-flow speed (expected travel speed under uncongested conditions). The empirical traffic weight is then calculated as the ratio of free-flow speed to current speed: $V_i = \frac{v_i^{\text{free}}}{v_i^{\text{cur}}}$, where a higher ratio indicates heavier congestion. To eliminate redundant network operations during iterative simulation loops, all API responses are persistently cached as JSON payloads indexed by MD5 coordinate hashes, ensuring reproducibility across runs.
#### On-Inverse-Distance-Weighting
Objects physically closer share more similar properties than objects further apart. this algorithm calculates the value of an unknown location by averaging the known values of surrounding points, applying a mathematical decay function to assign higher influence to points that are geographically closer. This is given by 
			 $$W_j = \frac{\sum_{i=1}^{n} (V_i / d_{ij}^p)}{\sum_{i=1}^{n} (1 / d_{ij}^p)}$$
where 
- $W_j$: The imputed traffic weight for the unqueried target node $j$.
- $n$: The total count of empirical data points queried from the TomTom API.
- $V_i$: The known traffic weight at empirical node $i$.
- $d_{ij}$: The exact geographical distance between node $j$ and node $i$. You must compute this using the Haversine formula to maintain spherical accuracy.
- $p$: The power parameter. This dictates the decay rate. Higher values force the algorithm to heavily favor only the nearest nodes.

#### On-Haversine-Formula
While planar geometry uses the Pythagorean theorem (flat surface), the Haversine formula calculates the shortest distance between two points on the surface of a sphere. It utilizes the longitudes and latitudes of points to compute the great-circle distance. This formula is required for the [Inverse Distance Weighting Interpolation](On-Inverse-Distance-Weighting). 

The computation converts coordinate degrees to radians and applies the following operations:

$a = \sin^2(\frac{\Delta \phi}{2}) + \cos(\phi_1) \cdot \cos(\phi_2) \cdot \sin^2(\frac{\Delta \lambda}{2})$
$c = 2 \cdot \text{atan2}(\sqrt{a}, \sqrt{1-a})$
$d = R \cdot c$
- $\phi_1, \phi_2$: Latitude of point 1 and point 2.
- $\Delta \phi$: Difference between the two latitudes.
- $\Delta \lambda$: Difference between the two longitudes.
- $R$: Mean radius of the Earth (approximately 6,371,000 meters).
- $d$: Final computed distance.

This method maintains numerical stability for small distances. It prevents the precision errors common in the spherical law of cosines when evaluating coordinates that are physically close.

#### On-Betweenness Centrality
If you drop a pin on a random house and another pin on a random grocery store, what is the absolute shortest path between them? Now, do that for _every single house_ and _every single store_ in the entire city. The specific intersections that get crossed the most times have high Betweenness Centrality.

Betweenness centrality quantifies the influence of a specific node on the flow of traffic across a network. It calculates the exact fraction of shortest paths that pass through a target node.

The mathematical formulation is defined by Freeman (1977). $$C_B(v) = \sum_{s \neq v \neq t \in V} \frac{\sigma_{st}(v)}{\sigma_{st}}$$where
$v$: The target node.
$s, t$: All other pairs of nodes in the graph.
$\sigma_{st}$: The total number of shortest paths from node $s$ to node $t$.
$\sigma_{st}(v)$: The number of those shortest paths that pass directly through node $v$.

#### On-Origin-Destination-Centrality
Origin-Destination Centrality is an upgrade to the standard Betweenness Centrality. Here is where the math ($P_i = W_i^\alpha \times C_i^\beta$) creates the magic. By multiplying the structural geometry by the live traffic, we create a true map of travel demand. Here is why multiplying them works perfectly for finding jeepney routes:

- **Scenario A (High Structure + High Traffic):** This is the main downtown avenue during rush hour. It's built to connect places, and it's currently full of people. The multiplication creates a massive final score. This is the absolute perfect place to route a jeepney.
    
- **Scenario B (High Structure + Low Traffic):** Many people use this road, but there's barely any traffic. It is still a structurally important bridge (High Structure), but the API shows nobody is there (Low Traffic). Because you are multiplying, the zero-traffic score tanks the final number. 
    
- **Scenario C (Low Structure + High Traffic):** Imagine a random residential cul-de-sac where many cars and jeeps traverse. The TomTom API flags it as heavily congested (High Traffic), but it's a dead-end street that doesn't connect to anything (Low Structure). The low structure score tanks the final number. You don't want your algorithm routing a public transit jeepney into a dead-end street.

Alpha ($\alpha$) and Beta ($\beta$) represent how much the algorithm should "care" about live traffic versus how much it should "care" about the physical road structure.

- **If Alpha is high and Beta is low:** The algorithm becomes obsessed with the TomTom API. It will chase live traffic jams, even if it means routing a jeepney into a random residential dead-end just because there is a temporary traffic spike there (Scenario C).
    
- **If Beta is high and Alpha is low:** The algorithm becomes obsessed with the map geometry. It will stick stubbornly to major highways and bridges, ignoring the fact that it is 3:00 AM and there are zero passengers on those roads (Scenario B).
    
- **The Perfect Balance:** By adjusting $\alpha$ and $\beta$, you force the algorithm to find the sweet spot: roads that are structurally important _and_ actively populated.

By fusing them together, Origin-Destination Centrality proves that a viable transit corridor needs **both**: the structural capacity to connect destinations, and the empirical proof that people actually want to travel there.

We did not invent the relationship between network structure and traffic volume. Lowry (2014) established that Origin-Destination Centrality is a valid explanatory variable for interpolating traffic. However, he used static, historical traffic counts (e.g. people on the side of the road with clikers). Our contribution is computational: we automated Lowry's static theory by substituting his historical census data with dynamic TomTom API data, allowing us to generate Origin-Destination Centrality in using queried data for an agent-based simulation.

#### On-Walker's-Alias-Table
Walker's Alias Method is an algorithm for efficiently sampling from a discrete probability distribution. You compute it once in $O(N)$ time to construct two arrays: a probability table and an alias table. Subsequent random sampling executes in constant $O(1)$ time.

This is mandatory for our framework. Metaheuristic algorithms evaluate thousands of route combinations. Using a standard cumulative distribution function requires an $O(\log N)$ binary search per sample. Walker's method eliminates this computational bottleneck.

The algorithm scales the probabilities so their mean is 1.0. It classifies probabilities as underfull (less than 1.0) or overfull (greater than 1.0). It redistributes the excess probability from the overfull nodes to fill the underfull nodes exactly to 1.0. Each index in the final array contains at most two outcomes: the original node and its designated alias node.

In the parallelized agent-based framework, Walker's Alias Method operates as the spatial sampling engine for the GA-ACO models. Standard roulette wheel selection requires an $O(\log N)$ binary search. Executing this search across millions of agent decisions in a parallelized environment causes a severe computational bottleneck. The alias table reduces spatial sampling to $O(1)$ constant time. An agent generates a random integer and a random float, checks the array index, and instantly retrieves a valid topological node.

This structural implementation allows the metaheuristic engine to run at scale without being throttled by probability lookups.
___
## Routes
### Logic

The `Route` module governs the structural definition, validation, and generation of jeepney transit loops. Jeepneys are only able to traverse [drivable](#On-PUJ-Arterial-Function) edges, which was a distinction made during the construction of the [`CityGraph`](#CityGraph)
### Implementation

1. **Route Validation**
	A `Route` is defined as a closed, continuous sequence of directed edges ([`DirEdge`](#DirEdge)). Upon initialization, the structure undergoes strict topological validation:
	 - **Loop Continuity:** The terminal edge must connect directly to the initial edge. Contiguity is verified at every index to prevent broken paths.
	 - **Layer Isolation:** All edges comprising a route must belong strictly to Layer 2 of the three-layer architecture.
	 - **Branching Constraint:** Each edge within the route must possess exactly one outgoing Layer 2 edge. This prevents ambiguous pathfinding for agents traversing the transit loop.
	
2. **Arterial Constraint Integration**
	The `RouteGenerator` leverages the `DirectDemandSampler` to synthesize waypoints. Crucially, the generator enforces an `only_drivable=True` constraint during spatial sampling. This ensures that the generated routes strictly adhere to the [PUJ Arterial Function](#On-PUJ-Arterial-Function). 
	
3. **Path Generation and Promotion** 
	Between the sampled drivable nodes, the generator queries the `CityGraph` to compute the shortest viable paths. Once a complete, continuous loop is established on the base graph, the generator executes a promotion sequence. The base edges are duplicated, explicitly assigned to `layer = 2`, and geometrically linked to construct the final Layer 2 route loop. The generator utilizes a retry mechanism to discard and re-sample points if a drivable path between two nodes cannot be computed.
	
	This approach to generating initial candidate routes is justified by Farahani et al. [^7], who validate that candidate transit loops are standardly generated using shortest-path-based algorithms. Furthermore, the decision to sample these initial waypoints exclusively from the computed demand distribution is supported by Mandl [^8]. Step 4 of Mandl's heuristic algorithm provides scientific justification for making route structures explicitly demand-responsive by prioritizing the inclusion of high-demand nodes during transit loop construction. Our framework automates the integration of these two proven methodologies into a single computational pipeline.
	
4. **Coordinate Snapping** 
	To support custom route ingestion, the module implements a `route_from_coords` pipeline. It processes raw JSON coordinate sequences and projects them onto the `CityGraph`. The system utilizes a `cKDTree` for rapid spatial querying, snapping raw coordinates to the nearest valid topological nodes. Once snapped and filtered for duplicates, the system calculates the shortest paths between these nodes to synthesize the continuous Layer 2 transit loop.
	
___
## TravelGraph
### Logic

The `TravelGraph` module constructs a multi-modal, three-layer directed graph to simulate realistic passenger journeys across the [`CityGraph`](#CityGraph). A standard flat graph cannot accurately model public transit because it fails to distinguish between a pedestrian walking across an intersection and a passenger riding a vehicle through that same intersection.

To solve this, the architecture separates travel states into distinct topological layers. Passengers must traverse explicit transition edges (representing waiting, alighting, or transferring) to move between these layers. This forces the pathfinding algorithm to account for the time penalties and structural constraints of utilizing public transit.
### Implementation

1. **Layer Initialization**    
    The graph duplicates the base `CityGraph` into distinct layers and initializes generated transit loops:
    - **Layer 1 (Start Walk):** Represents the pedestrian network for the origin leg of the journey. Contains `SW` (Start Walk) edges.
    - **Layer 2 (Ride):** Represents the transit network. Contains `RI` (Ride) edges generated by the `RouteGenerator`.
    - **Layer 3 (End Walk):** Represents the pedestrian network for the final destination leg. Contains `EW` (End Walk) edges.
    
2. **Transition Mechanics**
    To move between layers, the graph constructs structural bridges with configurable penalty weights (e.g., `wait_wt`, `transfer_wt`).
    - `DI` (Direct): Connects Layer 1 to Layer 3. Allows pedestrians to walk directly to their destination without riding.
    - `WA` (Wait): Connects Layer 1 to Layer 2. Simulates a passenger waiting at a node to board a jeepney.
    - `AL` (Alight): Connects Layer 2 to Layer 3. Simulates a passenger disembarking the vehicle.
    - `TR` (Transfer): Connects Layer 3 back to Layer 2. Simulates a passenger who has alighted one vehicle and is boarding a different route.
    
3. **Graph Stitching and Route Isolation**
    The module connects these layers using a custom `_stitch` function. Crucially, Layer 2 nodes and edges are strictly isolated by their specific route index. The graph only stitches wait (`WA`) and alight (`AL`) edges to the specific Layer 2 nodes belonging to that transit loop. This prevents agents from bypassing the transit logic and teleporting between two different jeepney routes that happen to share the same physical road.
    
4. **Journey Pathfinding**
    The module computes the most efficient multi-modal transit route using the A* search algorithm. The A* implementation utilizes a priority queue (`heappush`, `heappop`) to evaluate nodes based on their current traversal cost plus a heuristic estimate to the destination.
    

### On-Graph-Stitching-and-Route-Isolation

The multi-layer architecture requires a mechanism to connect pedestrian pathways to transit loops. This is handled by the internal `_stitch` function.

**How Stitching Works**

The `_stitch` function takes two distinct lists of directed edges (for example, a list of Layer 1 Start Walk edges and a list of Wait transition edges). It iterates through them and evaluates their terminal and initial nodes. If the destination node of Edge A shares the exact same spatial coordinates and layer designation as the origin node of Edge B, the function binds them, creating a valid, continuous topological path for the pathfinding algorithm to traverse.

**The Route Isolation Constraint**

If we were to stitch all Layer 2 (Ride) edges together universally, the graph would suffer from the "teleportation anomaly." Imagine Route A and Route B crossing at a busy intersection. If their Layer 2 nodes are connected directly to one another, an agent could instantly switch from moving jeepney A to moving jeepney B without incurring a time penalty, alighting the vehicle, or paying a new fare.

To prevent this, Layer 2 is strictly isolated by a route index (`r_idx`). Think of Layer 2 as a series of separate, parallel treadmills. You cannot jump directly from one moving treadmill to another. The implementation enforces this by filtering the nodes. The algorithm isolates the `RI` (Ride) edges for Route 0. It then stitches the `WA` (Wait) and `AL` (Alight) edges _exclusively_ to the specific nodes belonging to Route 0.

If an agent wants to transfer to Route 1, they are forced to step off the treadmill. They must traverse an `AL` edge down to Layer 3, walk to the transfer point via a `TR` edge, and stitch back into the specific Layer 2 nodes of Route 1. This mathematical isolation guarantees that agents behave like real passengers bound by physical reality.

### On-cKDTree-and-Spatial-Partitioning

When a passenger requests a ride from a random coordinate to another, those exact GPS coordinates almost never exist perfectly on our predefined graph intersections. The system must "snap" the passenger's raw location to the nearest valid topological node on Layer 1.

A naive brute-force approach calculates the distance between the passenger and every single node in the city network to find the minimum value. This requires $O(N)$ time complexity per query. In a parallelized agent-based simulation where thousands of passengers make dynamic decisions every tick, executing an $O(N)$ search millions of times creates a catastrophic computational bottleneck.

To solve this, the framework utilizes a `cKDTree` (K-Dimensional Tree) implemented via the SciPy library. A KDTree is a space-partitioning data structure that organizes points in a $k$-dimensional space [^9]. Instead of checking every node, the algorithm recursively splits the geographic map into binary half-spaces along the latitude and longitude axes.

Once the tree is constructed in memory, searching for the nearest topological node becomes a binary search through these spatial partitions. This reduces the query time complexity from $O(N)$ down to $O(\log N)$ (Bentley, 1975). This specific algorithmic choice allows the simulation to process massive volumes of dynamic passenger origins and destinations near-instantly without sacrificing spatial accuracy.

### On-A-Star-Heuristic

Dijkstra's Algorithm searches uniformly in all directions. A* improves upon this by using a heuristic function to "guide" the search direction toward the target, significantly reducing the number of nodes evaluated.

For A* to guarantee the absolute shortest path, the heuristic must be **admissible**. This means the heuristic must never overestimate the true cost of reaching the destination. In our implementation, the heuristic is defined as:

$$h(n) = \text{Distance}(n, \text{end}) \times \min(W_{walk}, W_{ride})$$

By calculating the straight-line geographical distance to the destination and multiplying it by the absolute lowest possible travel weight in the configuration (usually the ride weight), we ensure the algorithm always assumes the "best possible scenario." Because it never overestimates the penalty, the A* implementation remains mathematically admissible and is guaranteed to find the true optimal multi-modal path.
### Justification: The Three-Layer Architecture as a Behavioral Contribution

Traditional macro-level transit simulations heavily rely on static Origin-Destination (OD) matrices and planar graph topologies. While efficient for broad traffic flow estimation, a standard planar graph treats a pedestrian crossing a street and a vehicle driving through that same street as identical states. This limitation is well-documented in complex network analysis; as Peng et al. [^10] established, aggregating a large-scale transportation network into a single flat layer completely ignores the distinct operational states and physical interdependencies of the network.

The core scientific contribution of this framework is the explicit parameterization of transit friction through the Three-Layer TravelGraph. Real-world passengers exhibit strong transfer aversion. The decision to board a public utility jeepney is heavily influenced by the waiting time at the terminal, the physical walk to the stop, and the penalty of transferring between routes. To build realistic public transit simulations, standard node-based algorithms must be adapted to accurately calculate these hybrid, multi-modal journey times [^11].

By stratifying the graph into pedestrian (Layer 1, Layer 3) and transit (Layer 2) states, and forcing multi-modal connections through weighted transition edges (WA, AL, TR), our framework physically encodes behavioral friction into the graph topology. The A* pathfinding algorithm is forced to optimize not just for geographic distance, but for passenger comfort and transfer penalties. This architecture bridges the gap between static graph theory and dynamic, agent-based behavioral modeling, providing a scalable infrastructure to test highly realistic transit routing scenarios.

**TODO:** Justify the specific numerical values for penalty weights (walk, wait, ride, transfer) using empirical transfer penalty literature. We need to prove these are not arbitrary numbers.

 **TODO:** Provide a formal mathematical proof that the custom A* heuristic remains strictly admissible under all possible transition weight combinations to guarantee optimal pathfinding.

## Improvements to Sanchez & Llantos' (2025) framework

1. Utilizing Real City (no longer manhattan graph proof of concept)
2. Utilizing Direct Demand Model
3. Utilize Travel Graph for passenger 
# Simulation Agents
## Jeep

### Logic

The `Jeep` module defines the active public transit agent operating exclusively within Layer 2 of the `TravelGraph`. Unlike passenger agents that dynamically calculate shortest paths, the Jeep agent is strictly bound to a predefined `Route` loop. Its primary function is to track its kinematic state, manage its physical capacity constraints, and traverse its assigned topological edges over discrete time steps.

### Implementation

1. **Agent Initialization**
    
    A `Jeep` is initialized with a unique `jeep_id`, an assigned `route`, a maximum passenger `capacity` and a constant scalar `speed`. It maintains a set of `passengers` to track current occupancy.
    
2. **Kinematic State Tracking**
    
    The agent's position is not stored as a static geographic coordinate. Instead, it is tracked topologically using two variables:
    - `current_edge_index`: An integer pointing to the specific directed edge within the `route.path` list.
    - `progress`: A floating-point value representing the exact distance in meters the agent has traveled along that specific edge.
        
3. **Temporal Updates**
    During each simulation tick, the `update(dt)` method computes the scalar distance traveled using the basic kinematic formula $d = v \times dt$. This distance is added to the `progress` variable.
    
4. **Edge Transitions**
    If the updated `progress` exceeds the total length of the current edge, the agent subtracts the edge length from its progress and increments its `current_edge_index`. Because transit loops are continuous, the index update utilizes a modulo operation (`% len(self.route.path)`) to seamlessly wrap around to the beginning of the route.
    
5. **Event Emission**
    Upon completing an edge, the `update` method yields the destination node and the specific edge traversed. This allows the macro system to process passenger boarding and alighting exactly at the nodes.

### Limitation
Jeeps operate at a constant speed not accounting for stopping time and waiting time.

TODO: Make illustration to describe wrapping behavior of Jeep upon update.
___
## JeepSystem

### Logic

The `JeepSystem` module functions as the fleet manager. It is mathematically inefficient and structurally complex to have the main simulation loop iterate over and manage the internal states of hundreds of independent vehicles. The `JeepSystem` encapsulates this by controlling the initialization, spatial distribution, dynamic allocation, and batch updating of the entire transit fleet across all designated routes.

### Implementation

1. **System Initialization** The system is initialized with a list of valid routes. It instantiates an empty list for the global fleet and a dictionary mapping `jeeps_by_route` to organize agents by their assigned transit loops.
    
2. **Fleet Spacing and Instantiation** The `spawn_jeeps` method populates the system. Instead of dropping all vehicles at the starting node of a route, it computes the total geographic length of the transit loop and divides it by the requested number of vehicles to determine the optimal spatial headway. It then iterates through the route edges to instantiate `Jeep` agents at exact progress intervals.
    
3. **Dynamic Fleet Allocation (Mohring Effect)** Prior to vehicle instantiation, the system utilizes a `FleetAllocator` to handle the macro-level distribution of the total available fleet across the optimized routes. It evaluates expected passenger volume via demand sampling and applies a square root allocation formula. Any remaining fractional vehicles are distributed greedily, ensuring 100 percent of the fleet is deployed efficiently.
    
4. **Batch Temporal Processing** The system exposes a single `update(dt)` method to the main simulation loop. When called, it iterates through the entire fleet, executing the kinematic updates for every agent.
    
5. **Event Collection** As individual jeeps report edge transitions, the `JeepSystem` aggregates these into a list of `JeepEvent` tuples containing the specific jeep, the node it reached, and the edge it just completed. It returns this aggregated list to the main simulation environment.

### On-Kinematic-State-Updates

To maintain optimal computational efficiency, our framework does not calculate physical GPS coordinates for the moving vehicles at every tick. A standard spatial query to project a coordinate back onto a graph is computationally expensive.

Instead, the framework relies entirely on 1D topological progression. By keeping the agent bound to an edge index and tracking its linear progress in meters, the system executes vehicle movement in strict $O(1)$ constant time. The geographic coordinate is only computed if explicitly required for visual rendering. This distinction is critical for scaling the simulation to handle parallelized metaheuristic algorithms.

### On-Spatial-Headway-Distribution

When initializing a transit simulation, a naive approach spawns all agents at index 0 of their route. This immediately creates "bus bunching", a phenomenon where transit vehicles clump together with short headways, creating a positive feedback loop of delays that significantly reduces the operational efficiency of the system [^12]).

To ensure realistic service frequency, the `spawn_jeeps` method enforces strict spatial headway. The required spacing distance $S$ is computed as:

$$S = \frac{D_{total}}{N}$$

where $D_{total}$ is the total metric length of the continuous route loop and $N$ is the total number of jeeps assigned to that route. By distributing the vehicles optimally at time $t=0$, the system maintains consistent headways, which is an established requirement for ensuring reliable transit service [^12].

### On-The-Mohring-Effect-and-Fleet-Optimization

To answer why vehicles are not simply assigned linearly proportional to demand, the framework relies on the Mohring Effect to justify its macro-level allocation.

Linear allocation creates severe inefficiencies in public transit. Mohring [^17] proved that because waiting time is a substantial cost to the user, a welfare-maximizing transit system must increase frequency at a decreasing rate (the square root) relative to demand. By explicitly embedding the Mohring square root allocation into the fleet distribution logic, the framework mathematically guarantees that high-demand routes receive enough vehicles to minimize wait penalties without starving lower-demand feeder routes. This proves that fleet distribution is a theoretically validated optimization strategy, complimenting the micro-level headway controls.

### On-Event-Driven-Architecture

Notice that neither the `Jeep` nor the `JeepSystem` handles the logic for transferring passengers between the vehicle and the graph nodes.

This is an explicit design choice based on the principle of separation of concerns. The `JeepSystem` acts purely as a kinematic physics engine. It moves the boxes and reports when a box hits a valid checkpoint (a node). It generates a `JeepEvent` and hands it off to the main simulation loop.

This prevents the vehicle objects from needing access to the multi-layered `TravelGraph`. The main simulation loop acts as the supreme controller, taking the `JeepEvent`, checking the `TravelGraph` Layer 2 nodes for waiting passengers, and executing the boarding logic. This structural isolation keeps the codebase modular and prevents circular dependencies during the parallelization phase.

**TODO:** Address the limitation of constant vehicle speed. We need a cited justification for excluding dynamic traffic congestion and acceleration kinematics from this specific simulation scope.
___
## Passenger

### Logic

The `Passenger` module defines the autonomous agent traversing the multi-modal `TravelGraph`. Unlike the `Jeep` agent, which acts as a closed kinematic loop, the passenger agent executes a dynamic, goal-oriented path. The agent's core function is to transition through a predefined set of behavioral states to physically complete the multi-modal journey computed by the A* algorithm.

### Implementation

1. **Agent Initialization**
    
    A `Passenger` is initialized with a `passenger_id`, an origin `start_node`, a destination `end_node`, and a pre-computed `journey` (a list of `DirEdge` objects). The agent initializes its progress along the start of the first edge.
    
2. **State Machine Configuration**
    
    The agent's behavior is governed by the `PassengerState` enumeration, which restricts the agent to exactly five valid states:
    
    - `WALKING`: The agent is actively traversing pedestrian edges (`SW`, `EW`, `DI`).
        
    - `WAITING`: The agent has reached a transit stop (`WA`) and is idle until a vehicle arrives.
        
    - `RIDING`: The agent is inside a `Jeep`, its physical location bound to the vehicle's progress.
        
    - `ALIGHTING`: The agent has reached its target transfer/drop-off node (`AL`) and is transitioning back to the pedestrian network.
        
    - `ARRIVED`: The agent has completed the final edge of its journey.
        
3. **Pedestrian Kinematics**
    
    When the state is `WALKING`, the agent's `update(dt)` method computes movement using the standard kinematic equation $d = v_{walk} \times dt$. Upon completing a pedestrian edge, the agent increments its journey index. If the next edge in the sequence is a Wait (`WA`) edge, the agent automatically transitions to the `WAITING` state.
    
4. **Transit Synchronization**
    
    The passenger does not control the `Jeep`. When `RIDING`, the passenger's local `update()` method is effectively paused. Instead, it monitors the `Jeep` object it is assigned to. If the `Jeep` reaches the specific topological node matching the passenger's predetermined `alight_node`, the passenger triggers the `ALIGHTING` state, disembarks onto Layer 3, and resumes pedestrian kinematics.
    

### On-Finite-State-Machine-Behavior

Traditional macro-level transit models evaluate travel time using algebraic formulas or aggregate flow equations. They calculate the time it _should_ take a volume of people to get from Point A to Point B.

However, to accurately simulate public transit, we must model the friction of the journey itself. Our framework utilizes a Finite State Machine (FSM) to explicitly parameterize this friction. By forcing the agent to physically transition from `WALKING` to `WAITING` to `RIDING`, the simulation dynamically captures the compounding effects of missed transfers, vehicle capacity limits, and bus bunching. If a jeepney arrives but is full, the agent remains trapped in the `WAITING` state, naturally accruing delay time. This micro-level behavioral modeling is a primary advantage of Agent-Based Models over static traffic assignment [^13].

___
## PassengerGenerator

### Logic

The `PassengerGenerator` serves as the demand-synthesis engine for the simulation. It bridges the mathematical probability distributions of the `DirectDemandSampler` with the spatial architecture of the `TravelGraph`. It operates as a factory pattern, continuously generating valid `Passenger` agents based on real-time simulation requirements.

### Implementation

1. **Dependency Injection**
    
    The generator is initialized with the active `TravelGraph` (for routing) and the `DirectDemandSampler` (for spatial probability).
    
2. **Demand Sampling**
    
    When a passenger is requested, the generator triggers the `DirectDemandSampler`. The sampler utilizes its pre-computed Walker's Alias Table to execute two $O(1)$ operations, returning two statistically weighted topological coordinates representing the `origin` and `destination`.
    
3. **Journey Validation and Instantiation**
    
    The generator queries the `TravelGraph` to compute the A* shortest path between the generated origin and destination. If a valid multi-modal path exists, the generator instantiates a new `Passenger` object containing the route sequence and returns it to the main simulation loop.
    
4. **Rejection Sampling**
    
    Because the origin and destination are sampled probabilistically across a massive urban network, it is geometrically possible to sample two nodes that cannot be connected (e.g., an origin inside an isolated, disconnected graph component). If the A* algorithm fails to find a path, it throws a `JourneyError`. The generator catches this exception, discards the invalid coordinate pair, and recursively triggers a new sample.
    
### On-Dynamic-Demand-Synthesis

Standard transit routing optimization heavily relies on a static Origin-Destination (OD) matrix—a fixed grid dictating exactly how many people travel between specific zones. While functional for historical analysis, a static matrix cannot dynamically scale to test different metaheuristic load parameters without manually recalculating the entire matrix.

By integrating Walker's Alias Method directly into an active generator class, our architecture synthesizes demand dynamically. The system does not loop through a static list of predefined passengers; it procedurally generates statistically accurate agents at runtime. This allows us to evaluate candidate jeepney routes under infinite, stochastic traffic conditions, ensuring the optimized transit loops are robust against daily variance rather than overfitted to a single historical dataset.

**TODO:** Calibrate the probabilities within the DirectDemandSampler. We need to explicitly state how the Walker's Alias Table distribution will be validated against real-world origin-destination survey data.

____

# Simulation Environment

## Simulation

### Logic

The `simulation.py` module serves as the master controller for the agent-based framework. It is responsible for instantiating the topological environment (`TravelGraph`), executing the demand synthesis (`PassengerGenerator`), and managing the transit fleet (`JeepSystem`). Furthermore, it provides the critical fitness evaluation interfaces required by the overarching Genetic Algorithm and Ant Colony Optimization (GA-ACO) metaheuristics.

### Implementation

1. **Environment Initialization**
    
    The environment is bootstrapped via the `SimulationSetup` class. This wrapper encapsulates the target `CityGraph`, the configuration parameters (penalty weights, speed limits), and the specific set of `Route` objects to be tested. This structural isolation ensures that every simulation run is executed in a clean, deterministic environment, preventing data leakage between evolutionary generations.
    
2. **The Main Simulation Loop**
    
    The `run(ticks)` method governs the temporal execution of the full agent-based model. During each discrete time step (tick), the loop executes the following sequence:
    
    - **Demand Generation:** Triggers the `PassengerGenerator` to spawn new agents probabilistically and update the kinematic states of active pedestrians.
        
    - **Fleet Progression:** Triggers the `JeepSystem` to advance the kinematic states of the entire transit fleet along Layer 2 edges.
        
    - **Event Handling (Boarding/Alighting):** The loop catches `JeepEvent` reports from the fleet. It queries the Layer 1 wait nodes corresponding to the vehicle's current topological position. If a `Passenger` is waiting and the vehicle has capacity, the simulation transfers the agent from the pedestrian layer to the vehicle layer, updating their Finite State Machine to `RIDING`.
        
3. **Post-Simulation Fitness Evaluation**
    
    After the simulation stops, `evaluate_fitness()` calls the internal `_calculate_results()` routine to convert the final passenger states into a scalar objective. The score is built from three terms:

    | Component | Formula | Code Reference | Meaning |
    |-----------|---------|-----------------|---------|
    | **Term 1: Total User Cost** | $\sum_{i \in \mathcal{C}} T_i$ | `sum_completed_time` | Sum of realized door-to-door travel times for all completed passengers |
    | **Term 2: Underservice Penalty** | $\sum_{j \in \mathcal{I}} (T_j^{\text{elapsed}} + \beta \cdot \hat{T}_j^{\text{rem}})$ | `sum_penalty_time` | Elapsed time + penalty multiplier × remaining cost for incomplete passengers |
    | **Term 3: Equity Regularizer** | $\alpha \cdot \sigma(T_i \mid i \in \mathcal{C})$ | `equity_penalty` | Population standard deviation of completed travel times, weighted by α |
    | **Final Fitness** | $F(\mathbf{R}) = \text{Term 1} + \text{Term 2} + \text{Term 3}$ | `fitness_score` | Lower is better |

    **Parameters:**
    - $\beta$ (`beta_penalty`, default 2.0): Multiplier for incomplete passenger remaining cost
    - $\alpha$ (`alpha_std_penalty`, default 0.5): Weight for equity regularizer

    The returned `SimulationResult` keeps the scalar `fitness_score` plus a metric breakdown (`completed_count`, `incomplete_count`, `sum_completed_time`, `sum_incomplete_elapsed_time`, `sum_incomplete_remaining_time`, `sum_penalty_time`, `equity_penalty`) so the final evaluation is auditable.


          #### Term 1: Total User Cost — $\sum_{i \in \mathcal{C}} T_i$
     
     **What it is.** The aggregate realized travel time across all passengers who successfully completed their journey within the simulation window.
     
     **Why this is the correct objective.** The Transit Network Design Problem (TNDP) literature overwhelmingly converges on Total Travel Time (TTT) as the primary user-side objective function. This is not an arbitrary choice — it arises directly from microeconomic theory of time allocation.
     
     **Formal derivation.** In the random utility framework underlying discrete transport choice models, the disutility of a trip is dominated by its time cost. Ortúzar & Willumsen (2011, Ch. 5) define the user cost of a transit trip as a generalized cost function:
     
     $$C_i^{\text{gen}} = w_{\text{walk}} \cdot t_{i,\text{walk}} + w_{\text{wait}} \cdot t_{i,\text{wait}} + w_{\text{ride}} \cdot t_{i,\text{ride}} + w_{\text{transfer}} \cdot n_{i,\text{transfer}}$$
     
     where $w_\cdot$ are perception weights reflecting that passengers experience walking and waiting time as more onerous than in-vehicle time. In our simulation, $T_i$ is already measured in generalized-cost units because the TravelGraph's A* pathfinding assigns weighted edges that encode these perception factors (see travel_graph config: `walk_wt`, `ride_wt`, `wait_wt`, `transfer_wt`). The `despawn_tick - spawn_tick` measurement thus captures the full realized generalized cost including all modal transitions.
     
     Summing over all passengers yields the system-level Total User Cost. This is the canonical TNDP objective used by:
     
     - **Ceder & Wilson (1986)** — who define the bus network design problem as minimizing total passenger travel time subject to fleet and frequency constraints. Their formulation is the foundational reference for the two-phase TNDP (route design + frequency setting).
     - **Kepaptsoglou & Karlaftis (2009)** — whose survey of 40+ years of TNDP research confirms that "minimization of total (or average) user travel time" is the most widely adopted single-objective formulation, appearing in the majority of published solution approaches.
     - **Fan & Machemehl (2006)** — who use total user cost as the fitness function in their Genetic Algorithm for transit route optimization, directly analogous to our metaheuristic architecture.
     
     **Why not average travel time?** Averaging would allow the optimizer to improve the score by simply not generating difficult-to-serve passengers (since fewer passengers = lower denominator). The sum penalizes every unserved or poorly-served passenger proportionally, preventing this failure mode.
     
     #### Term 2: Underservice Penalty — $\sum_{j \in \mathcal{I}} \left( T_j^{\text{elapsed}} + \beta \cdot \hat{T}_j^{\text{rem}} \right)$
     
     **What it is.** For each passenger who has not completed their journey by tick $T$, the penalty adds their elapsed time plus a multiplied estimate of their remaining travel cost. The multiplier $\beta > 1$ inflates the remaining cost to ensure that incomplete journeys are strictly more expensive than completed ones of equivalent length.
     
     **Why it's necessary.** Without this term, the optimizer could "game" the fitness by generating route systems that efficiently serve easy-to-reach OD pairs while completely ignoring hard-to-reach neighborhoods. A route system that serves 80% of passengers in 5 minutes each but strands the remaining 20% indefinitely would score better than a system that serves 100% in 8 minutes each — clearly the wrong incentive.
     
     **Formal grounding.** This is an instance of the exterior penalty function method for converting constrained optimization into unconstrained optimization, enabling metaheuristic search. The implicit constraint is:
     
     $$\text{All passengers must complete their journey: } |\mathcal{I}| = 0$$
     
     Since evolutionary algorithms cannot natively handle hard constraints, the standard approach is to relax the constraint into the objective via a penalty term. Coello Coello (2002) provides the definitive survey of constraint-handling techniques in evolutionary computation and classifies our approach as a static penalty — a fixed multiplier $\beta$ that inflates the cost of constraint-violating solutions.
     
     The specific penalty structure — `elapsed_time + β × remaining_cost` — has two properties that make it well-behaved for metaheuristic search:
     
     - **Monotonicity:** As a passenger gets closer to completion (remaining cost decreases), the penalty decreases smoothly, providing gradient signal to the optimizer.
     - **Dominance:** Since $\beta > 1$, an incomplete passenger always contributes more to $F(\mathbf{R})$ than an equivalent completed passenger. This guarantees that the optimizer prefers route systems that complete more journeys, all else being equal.
     
     The remaining cost estimate $\hat{T}_j^{\text{rem}}$ is computed from the passenger's pre-planned A* journey (`utils/passenger.py:L207–221`). This is a deterministic quantity — the sum of untraversed edge weights in the originally planned path — making it reproducible across evaluations.
     
     **Default value:** $\beta = 2.0$. This means an incomplete passenger's remaining journey costs twice what a completed passenger's equivalent segment would cost. The value is set at the lower end of penalty multipliers recommended in the evolutionary optimization literature (Coello Coello reports effective ranges of 1.5–10× depending on constraint severity). A value of 2.0 is conservative: strong enough to prevent the optimizer from ignoring coverage, but not so aggressive that it dominates the fitness landscape and prevents exploration.
     
     #### Term 3: Equity Regularizer — $\alpha \cdot \sigma(T_i \mid i \in \mathcal{C})$
     
     **What it is.** The population standard deviation of completed travel times, weighted by coefficient $\alpha$. This penalizes route systems where travel time quality is unevenly distributed across passengers.
     
     **Why it's necessary.** Consider two route systems both averaging 10-minute commutes. System A delivers everyone in 9–11 minutes. System B delivers half in 3 minutes and half in 17 minutes. By Term 1 alone, both systems are equivalent. The equity regularizer correctly identifies System A as superior because it provides consistent service quality.
     
     **Formal grounding.** The inclusion of a variance-based penalty in transit objective functions is grounded in the concept of horizontal equity — the principle that similarly situated individuals should receive similar levels of service.
     
     Welch & Mishra (2013) formalize equity metrics for public transit connectivity evaluation and demonstrate that dispersion-based measures (standard deviation, Gini coefficient, coefficient of variation) effectively capture the spatial equity of transit service distribution. They argue that mean-only optimization systematically produces networks with unacceptable service disparities between well-connected and peripheral communities — precisely the failure mode the regularizer prevents.
     
     From the transport economics perspective, Jara-Díaz & Gschwender (2003) incorporate travel time variance into their microeconomic model of public transport operations, deriving that the social welfare function for transit includes both the expected travel time and its variance:
     
     $$W = -\left(\mathbb{E}[T] + \lambda \cdot \text{Var}(T)\right)$$
     
     where $\lambda$ reflects society's risk aversion toward travel time uncertainty. Our formulation uses standard deviation rather than variance, which has the practical advantage of sharing the same units (seconds) as the other terms.
     
     **Default value:** $\alpha = 0.5$. This weights one standard deviation of commute time as equivalent to half a second of aggregate travel cost. The relatively modest value ensures the regularizer acts as a tiebreaker rather than dominating the objective — it steers the optimizer toward equitable solutions among configurations with similar total cost, without sacrificing overall efficiency.
     
4. **Surrogate Mutation Check**
    
    The optimizer's GA search uses the microscopic fitness evaluator. `StaticSurrogateEvaluator.evaluate()` is reserved for local-search mutation checks, where it computes the static multi-modal A* cost for a fixed set of origin-destination pairs and returns a `SimulationResult` with `surrogate_cost`. The full simulation remains the authoritative score for selection, elitism, and replacement.
    

### On-Event-Driven-State-Transitions

As established in the Jeep System documentation, individual vehicles and passengers do not directly interact with one another in the codebase. The `Simulation` class acts as the supreme mediator.

When a jeepney reaches a node, it does not search for passengers. It simply reports its state to the simulation controller. The controller then queries the `TravelGraph` and handles the complex logic of boarding, capacity checking, and alighting. This event-driven architecture strictly enforces the separation of concerns. It allows the mathematical physics engine to run independently of the behavioral state machines, drastically reducing computational overhead during high-density simulations.

### On-Surrogate-Fitness-Evaluation-in-Metaheuristics

The framework is designed to optimize jeepney routes using a hybrid GA-ACO algorithm. Evolutionary algorithms require evaluating thousands of candidate solutions (route sets) across multiple generations. Running a full tick-based, micro-level agent simulation to evaluate every single candidate chromosome is computationally prohibitive.

To solve this, the framework implements `StaticSurrogateEvaluator.evaluate()` as a separate mutation-check proxy. In complex combinatorial optimization, surrogate models or approximation functions are useful when a cheaper acceptance test is needed before running the expensive objective. Here, the proxy bypasses the temporal physics engine and directly computes the static multi-modal A* costs for a representative sample of OD pairs, but it is only used to decide whether a Lamarckian local-search mutation should be kept. Its scalar is stored as `surrogate_cost`, while the microscopic run keeps `fitness_score` for the GA objective.

TODO: Prove the direct mathematical correlation between the static surrogate routing cost and the dynamic temporal cost of the full agent-based simulation.

TODO: Modify all instances mentioning surrogate in codebase to avoid pedantic panelists

___

# Optimization Modules

## Pheromone

### Logic

The `PheromoneMatrix` serves as the global memory structure for the hybrid GA-ACO framework. In a standard Genetic Algorithm (GA), crossover and mutation are largely stochastic. By integrating a pheromone matrix, the framework tracks the historical success and demand of specific geographic corridors across multiple evolutionary generations. This allows the metaheuristic to replace purely random mutations with probabilistically biased decisions, effectively guiding the search space toward high-demand, underserved transit corridors.

### On-ACO-Inspired-Validity

A defense panel will legitimately question how this framework is "ACO-inspired" when it makes a fundamental structural shift from traditional Ant Colony Optimization. In standard ACO, the "ants" are the algorithmic agents actively constructing the solution (e.g., drawing the jeepney routes). In this framework, the transit routes are generated by a GA, and the "ants" are actually the simulated _passengers_ navigating the A* graph.

Despite this inversion, the architecture rigorously adheres to the foundational pillars of ACO theory by utilizing *stigmergy* (indirect communication via the environment). By shifting the pheromone deposition from the _solution constructor_ to the _environmental evaluator_, the framework organically captures transit demand. Using "expected passenger paths" to lay pheromones accurately simulates real-world desire lines. As passengers traverse a corridor, they signal a demand for transit; the more efficient the path, the stronger the signal[^15].

The algorithm remains theoretically sound because it preserves the three mathematical invariants of ACO:

1. **Path-Cost Deposition:** Pheromones are deposited strictly in inverse proportion to the total journey cost.
    
2. **Generational Evaporation:** A strict decay parameter actively prevents search stagnation.
    
3. **Probabilistic Biasing:** The matrix actively weights the probability distributions of the GA operators.
    

### On-Probabilistic-Nudging-vs-Greedy-Snapping

The framework utilizes the computed passenger demand to _nudge_ the GA route generation rather than forcing it to _snap_ directly to the highest-demand corridors.

If the algorithm greedily snapped routes to the strongest pheromone trails, the search would suffer from premature convergence. This occurs when an algorithm wastes time in already explored regions or gets trapped in a local optimum instead of identifying new regions of the search space with high quality solutions [^16].

To prevent this, the pheromone values are used as weighted probabilities during mutation. The algorithm is highly likely to mutate a route to follow a high-demand avenue, but there remains a mathematical probability it explores a lower-demand, alternate street. This probabilistic nudging perfectly manages the dynamic balance between two critical forces: _diversification_ (the exploration of the search space) and _intensification_ (the exploitation of accumulated search experience) [^16]. By intentionally keeping the pheromone guided decisions less greedy and less deterministic, the framework inherently increases its diversifying effect [^16]. This preserves the genetic diversity of the GA while intelligently exploiting the ACO local search data.

### Implementation & Pheromone Mechanics

1. **Spatial Initialization and Mapping**
    
    The matrix initializes with a base pheromone level (`initial_tau`) across all valid topological edges. Pheromones are keyed to a spatial `_CoordKey` (a tuple of start and end coordinates). This guarantees that overlapping transit routes covering the exact same physical road segment deposit pheromones into a shared geographic pool.
    
2. **The Evaporation and Deposition Cycle**
    
    After a candidate solution is evaluated via the `SimulationController`, the `update_pheromones` method executes the core ACO mathematical lifecycle derived from Dorigo et al. [^15]:
    
    - **Evaporation:** All existing pheromones $\tau_{ij}$ on edge $ij$ are reduced by a decay factor $\rho$ to simulate time passing and to clear outdated demand data:        $$\tau_{ij}(t+1) = (1 - \rho)\tau_{ij}(t)$$
    - **Deposition:** The algorithm iterates through the recorded passenger journeys. It deposits new pheromones inversely proportional to the path cost $C$, utilizing the deposition constant $Q$:$$\Delta\tau_{ij} = \frac{Q}{C}$$        
3. **Demand-Service Gap Computation**
    
    The module actively computes the Demand-Service Gap for every edge to evaluate spatial transit coverage. Instead of raw differences, it calculates the normalized proportional disparity gap:
    $$\text{gap}_e = \frac{\tau_e}{\sum \tau} - \frac{\text{supply}_e}{\sum \text{supply}}$$
    where:
    - $\tau_e$ is the pheromone density on edge $e$.
    - $\sum \tau$ is the sum of all pheromone densities across all edges.
    - $\text{supply}_e$ is the service supply on edge $e$, computed as the sum of fleet sizes of all routes traversing edge $e$ multiplied by `default_jeep_weight`.
    - $\sum \text{supply}$ is the sum of service supplies across all edges.
	
	- A **positive gap** indicates an underserved corridor (the edge's share of network demand exceeds its share of fleet supply).
	    
	- A **negative gap** indicates an over-served corridor (the edge receives a larger share of the fleet than its demand warrants).
	    
    This metric is cached and directly utilized by the GA operators to intelligently guide spatial mutation. By tracking both positive and negative values, the framework generates a comprehensive topological map of service disparities across the city. The GA uses this full spectrum to dynamically adjust mutation parameters (Eiben et al., 1999). It mathematically biases the algorithm to pull route topologies away from heavily negative, over-served regions and push them toward highly positive, underserved corridors. Once the physical routes are spatially balanced by this push and pull dynamic, the framework defers the actual vehicle volume distribution to the `FleetAllocator` utilizing the Mohring allocation.

**TODO:** Generate a map visualization showing the step-by-step execution of the "cheapest-insertion cost scoring" to demonstrate exactly how the route bends toward a demand hotspot.
    
**TODO:** Provide a statistical breakdown of route lengths before and after the pruning operator is applied to empirically validate the reduction in tortuosity as defined by Ceder and Wilson.

___
## LocalSearch 
(The Lamarckian Mutation Part)
### Logic

The `ACOLocalSearch` module functions as the active mutation engine of the framework. Rather than relying on stochastic Darwinian mutation, the framework deploys three targeted Lamarckian operators. These operators read the Demand-Service Gaps mapped by the `PheromoneMatrix` and actively modify the topological structure of the candidate routes before they are evaluated. By allowing candidate solutions to learn from environmental feedback and pass those improvements to the next generation, the algorithm operates as a highly efficient Memetic Algorithm.

### 1. Demand-Driven Attraction (Or-opt Segment Transplant)

**Academic Justification:** In TRNDP metaheuristics, transit networks must constantly adapt to capture unmet passenger demand. Much like Baaj and Mahmassani [^18]  did in their Route Generation Algorithm by employing specific "node selection and insertion strategies" to connect high-demand pairs, this framework utilizes a Demand-Driven Attraction mechanism. Kepaptsoglou and Karlaftis [^19] explicitly noted in their comprehensive review that demand-guided node addition is a primary heuristic for capturing unserved market share.

**Implementation Strategy:**

This operator identifies contiguous route segments operating on low-demand corridors and mathematically transplants them toward high Demand-Service Gap clusters. By utilizing a continuous Or-opt routing mechanic [^37], the algorithm physically detaches a poorly performing sequence of edges and stitches it directly across underserved nodes. This cleanly pulls the route into high-demand areas, effectively capturing massive unmet transit demand while rigorously preserving the structural validity of the topological loop.

### 2. Redundancy Repulsion (2-opt Segment Reversal)

**Academic Justification:** Operator viability requires minimizing redundant vehicle kilometers. Fan and Machemehl [^21] explicitly modeled the Transit Route Network Design Problem to balance user costs against operator costs and the penalties. Kepaptsoglou and Karlaftis [^19] reviewed several models that deliberately constrained route overlap to maximize spatial coverage and disperse fleet resources efficiently. Moving a highly useful route segment away from a low-served area provides no mathematical benefit, but if multiple routes share the same highly served segment, they create fleet redundancy.

**Implementation Strategy:**

The repulsion operator identifies segments where multiple routes overlap redundantly across a negative-gap (overserved) corridor. Instead of globally penalizing the graph weights, it executes a localized 2-opt geometric reversal [^38].

- **Constrained 2-opt Detour:** The algorithm geometrically slices the redundant sequence and actively reroutes the connection around the congested zone via a parallel detour. This organically disperses the overlapping routes, maximizing spatial coverage without polluting the globally shared `TravelGraph` with artificial edge weights.
    

### 3. Demand-Aware Tortuosity Pruning (Node Deletion & Circuity Reduction)

**Academic Justification:** A robust public transit network relies on directness of service. Ceder and Wilson [^20] established that minimizing the difference between indirect and direct passenger-hours (a concept known as circuity or tortuosity) is critical for effective bus network design. To combat tortuosity, Baaj and Mahmassani [^18] incorporated route improvement algorithms specifically designed to fix inefficiencies and ensure directness of service.

**Implementation Strategy:**

This operator identifies segments that meander inefficiently between high-demand hubs. It amputates the detour and bridges the gap using a strict A* shortest-path calculation on the base `CityGraph`.

The mathematical robustness of this operator relies on two critical safeguards:

- **True Geometric Tortuosity ($\kappa$):** The algorithm computes true geometric circuity by explicitly dividing the length of the traversed path by the theoretical shortest A* path between the segment endpoints ($\kappa = L_{path} / L_{direct}$). By separating this pure geometric ratio from the pheromone utility score (used only as a tiebreaker), the operator correctly targets genuinely meandering, tortuous loops rather than simply amputating straight, low-demand edges.
    
- **Gap Immunity:** Without intervention, a pruning function would naturally target the exact detours created by the Attraction operator. By granting algorithmic immunity to any segment containing a positive-gap (underserved) edge, the framework ensures the node insertion and node deletion operators remain mathematically orthogonal, working in tandem rather than in opposition.

**TODO:** Generate a map visualization showing the step-by-step execution of the "cheapest-insertion cost scoring" to demonstrate exactly how the route bends toward a demand hotspot.
    
**TODO:** Provide a statistical breakdown of route lengths before and after the pruning operator is applied to empirically validate the reduction in tortuosity as defined by Ceder and Wilson.
___
## Genetic
(The Memetic Part)
### Logic

The `MemeticAlgorithm` module functions as the overarching evolutionary controller for the jeepney routing system. While standard Genetic Algorithms rely entirely on blind random mutations, this framework operates as a Lamarckian Memetic Algorithm.

This framework treats passenger demand patterns as inheritable traits. Reynolds [^22] established the concept of Cultural Algorithms where evolution occurs on two levels: the population space (the physical routes) and the belief space (the cultural memory of the environment). By passing down this belief space (the `PheromoneMatrix`), the algorithm utilizes Lamarckian inheritance. Offspring inherit the acquired knowledge of their parents, meaning they do not have to waste computational time relearning where the city's high demand corridors are located.

### 1. Topological Hub Crossover (Trunk and Feeder Preservation)

**Academic Justification:**

Standard genetic crossover operators randomly slice and swap route arrays, which can blindly destroy high performing transit corridors. To prevent this, the framework artificially engineers a hierarchical transit structure.

Gschwender, Jara-Díaz, and Bravo [^23] demonstrated mathematically that a feeder-trunk scheme is vastly superior in urban areas due to the presence of "economies of density" (decreasing average operating costs) along the main avenues served by trunk lines. Building on this, Risso, Nesmachnow, and Faller [^24] proved that Evolutionary Algorithms can be explicitly designed to optimize a "Backbone Network" (the trunk) in combination with a broader, peripheral bus network (the feeders) to reduce overall travel times.

The "Topological Hub" crossover acts as a spatial preservation tool modeled after these exact concepts. It ensures the algorithm protects the strongest economies of density (the trunk) while hybridizing the peripheral coverage (the feeders).

**Implementation Strategy (Simplified):**

Instead of randomly mixing routes, this crossover acts like a strategic city planner combining two different transit blueprints into a unified Trunk and Feeder hierarchy:

- **Identify the Core:** The algorithm scans the inherited pheromone map to find the "Topological Hub," which represents the busiest, most congested street corridors where economies of density are highest.
    
- **Preserve the Trunk (Parent A):** It extracts the routes from the first parent that heavily intersect this busy hub. Following the principles of Risso et al. [^24], these routes become the permanent "trunk" or backbone of the new child network.
    
- **Expand the Feeders (Parent B):** To complete the network, the algorithm scans the second parent and selects peripheral "feeder" routes that do not geometrically overlap with the established trunk.
    

By combining the strong urban core of Parent A with the wide suburban coverage of Parent B, the algorithm mathematically guarantees that the child network maintains high capacity in the center and broad spatial coverage on the edges, perfectly mirroring the optimal hierarchical transit design principles established by Gschwender et al. [^23] and Risso et al. [^24].

### 2. Epigenetic Inheritance (Fitness Weighted Pheromones)

**Academic Justification:**

If two transit networks are going to produce an offspring, that offspring needs a map of passenger demand to guide its future local search. Middendorf, Reischle, and Schmeck [^25] proved that in multi colony ant algorithms, allowing different solutions to exchange information about their successful paths prevents the search from stagnating and accelerates the discovery of the global optimum.

**Implementation Strategy:**

The `inherit_pheromones` method executes this information exchange. It blends the pheromone matrices of both parents to create a master demand map for the child. However, it does not blend them equally. The algorithm uses a fitness proportional weighting mechanism. The child inherits a merged map that is heavily biased toward the parent with the lower surrogate system cost.

$$w_A = \frac{cost_B}{cost_A + cost_B}$$

This gives the child's initial `FleetAllocator` a massive mathematical head start by inheriting a culturally mature, highly accurate map of passenger behavior directly proportional to its parents' success.

### 3. Surrogate Cost Evaluation and Lamarckian Mutation

**Academic Justification:**

Evaluating every candidate chromosome via a full agent based temporal simulation is computationally prohibitive. In complex combinatorial optimization, the use of low cost surrogate models is standard practice to bypass bottlenecks during the primary search phase.

**Implementation Strategy:**

The `evaluate_chromosome` method runs the microscopic fitness evaluator, so every GA decision is scored against the full simulation `fitness_score`. The surrogate is not used for selection or ranking; it is only consulted inside Lamarckian mutation checks before the full fitness is recomputed.

Furthermore, the algorithm actively applies Lamarckian mutation by running the `ACOLocalSearch` operators to physically manipulate the routes. The mutation step compares surrogate cost before and after the local edit; only if the surrogate improves is the chromosome kept, after which the full fitness score is recomputed for GA use. If the mutation degrades the network, the algorithm reverts to the original backup routes.

**TODO:** Provide a convergence graph in your results chapter comparing the generational cost reduction of this Lamarckian Memetic Algorithm against a standard Darwinian control group to empirically prove the acceleration provided by the Belief Space.

**TODO:** Validate the correlation between the $O(1)$ surrogate cost estimate and the final agent-based simulation cost to prove the surrogate's accuracy.
___
# Optimizer Orchestration

The modules documented under [Optimization Modules](#Optimization-Modules) define the algorithmic primitives: the pheromone memory, the local search mutations, and the genetic crossover/inheritance operators. However, algorithms do not run themselves. The Optimizer Orchestration layer is responsible for coordinating these primitives into a reproducible, interruptible, and auditable evolutionary search loop.

This section documents, in dependency order, the six modules that bridge the gap between "we have a Memetic Algorithm" and "we can run, pause, resume, and analyze a multi-generational optimization experiment."
___
## ExperimentConfig

### Logic

Metaheuristic optimization involves dozens of interacting parameters: population sizes, mutation rates, pheromone decay constants, travel graph penalties, fleet allocations, simulation tick counts, and vehicle speeds. Hardcoding these values inside source code creates two critical failures:

1. **Reproducibility Collapse:** If a parameter is changed inline, there is no auditable record of what configuration produced a specific result. For a thesis defense, every result must trace back to an exact, immutable parameter set.

2. **Experiment Throughput:** Testing the sensitivity of the algorithm to different hyperparameter values requires modifying source code for every run. This is error-prone and structurally prevents queuing multiple experiments.

### Implementation

1. **YAML Ingestion**
	The `ExperimentConfig` class method `from_yaml` parses a structured YAML file and maps every field to a typed Python attribute. The parser handles two distinct city topologies: real-world OSM bounding boxes (`city_graph.bbox`) and synthetic toy city grids (`toy_city` origin + step + grid size), computing a rough bounding box from the grid geometry when no explicit bbox is provided.

2. **Immutable Frozen Dataclass**
	The configuration is implemented as a `@dataclass(frozen=True)`. Once instantiated, no attribute can be mutated. This guarantees that the parameter set governing a run cannot be accidentally altered by any downstream module during execution.

3. **Parameter Grouping**
	The YAML structure mirrors the architectural layers of the framework:
	- **Orchestrator IO:** Output paths, telemetry intervals, checkpoint frequencies.
	- **Genetic Algorithm:** Population size, max generations, stagnation limit, elitism count, tournament size, mutation rate, crossover coefficient, Jaccard patience.
	- **Local Search & Pheromone:** Initial pheromone concentration, evaporation rate, deposition constant, operator probabilities, default jeep weight.
	- **System Cost:** Headway variance penalty ($\alpha$), underservice penalty ($\beta$).
	- **System Definition:** Number of routes, total fleet, city bounds.
	- **Travel Graph:** Walk, ride, wait, and transfer weight penalties.
	- **Simulation:** Tick count, speeds, capacity, spawn rates, boarding tolerance, dispatch spacing.

### OptimizationState

The `OptimizationState` is the mutable counterpart to the immutable `ExperimentConfig`. It is implemented as a standard (non-frozen) dataclass that tracks the live evolutionary state:

- `generation`: The current generation index.
- `stagnation_counter`: The number of consecutive generations without fitness improvement.
- `best_fitness`: The lowest system cost observed across all generations.
- `population`: The active list of `Chromosome` objects.
- `pheromones`: The master `PheromoneMatrix` (typically mirrored from the fittest chromosome).
- `random_state`: The captured pseudorandom number generator state via `random.getstate()`. This is critical for [deterministic replay](#On-Deterministic-Replay).

The separation between immutable configuration and mutable state is not accidental. The `ExperimentConfig` defines _what_ the experiment is. The `OptimizationState` tracks _where_ the experiment currently is. By keeping them structurally isolated, the framework guarantees that serialization, checkpointing, and resumption operate on the state without risk of parameter contamination.

___
## AdaptiveController

### Logic

A static mutation rate creates a fundamental trade-off that cannot be resolved at compile time. If the rate is set high, the algorithm explores aggressively but wastes computational cycles on random perturbations even after it has already located a promising region. If the rate is set low, the algorithm exploits efficiently but gets permanently trapped the moment it reaches a local optimum.

The `AdaptiveController` solves this by dynamically adjusting the mutation intensity based on real-time population feedback. When the algorithm stagnates, the controller escalates mutation to force exploration. The moment progress resumes, the controller snaps back to the baseline to resume fine-grained exploitation.

### Implementation

1. **Quadratic Stagnation Scaling**
	The controller monitors the `stagnation_counter` (generations without improvement). As stagnation increases, the mutation probability scales quadratically toward a hard cap of 0.8:

	$$P_{mut} = P_{base} + (P_{max} - P_{base}) \times \left(\frac{s}{S_{limit}}\right)^2$$

	where $s$ is the current stagnation count and $S_{limit}$ is the configured stagnation threshold. The quadratic curve is deliberate: it provides a gentle initial increase (giving the algorithm time to naturally escape), but accelerates sharply as stagnation persists. A linear scaling would either react too aggressively too early or too slowly near the limit.

2. **Exploitation Reset**
	The instant the population registers a new best fitness, the stagnation counter resets to zero, and the controller immediately reverts the mutation rate to the baseline. This prevents the controller from continuing to force exploration after the algorithm has already broken free.

3. **Linear Decay of Local Search Probability**
	The probability of triggering a local search mutation decays linearly across generations:

	$$P_{local}(g) = P_{min} + (P_{max} - P_{min}) \times \left(1 - \frac{g}{G_{max}}\right)$$

	Early generations apply heavy local search to rapidly improve raw candidate routes. Later generations reduce this to prevent the local search operators from destroying topologies that the algorithm has already refined.

4. **Dynamic Radius Tightening**
	The `intensity` parameter, which controls the spatial aggressiveness of the local search operators (window sizes, detour lengths), follows the same linear decay formula. Early generations cast a wide net. Late generations make small, surgical adjustments.

### On-Adaptive-Parameter-Control

The theoretical foundation for dynamic mutation scaling is established by Eiben, Hinterding, and Michalewicz (1999)[^26]. Their seminal survey on parameter control in evolutionary algorithms formally categorizes three control strategies: deterministic (fixed schedule), adaptive (feedback-driven), and self-adaptive (encoded in the chromosome). Our controller implements the _adaptive_ strategy, using population stagnation as the feedback signal. Eiben et al. explicitly identify stagnation-driven mutation scaling as one of the most effective adaptive mechanisms for escaping local optima in combinatorial optimization.

The decision to use quadratic rather than linear scaling is a refinement on the standard approach. Linear scaling applies uniform pressure across the entire stagnation window, which means the algorithm pays the same exploration cost at stagnation count 1 (where natural escape is still likely) as at stagnation count $S_{limit} - 1$ (where aggressive intervention is required). Quadratic scaling front-loads patience and back-loads force, which better matches the empirical observation that most local optima traps resolve naturally within the first few stagnant generations.

___
## MemeticEngine

### Logic

The `MemeticEngine` is the computational core that connects the algorithmic primitives ([Pheromone](#Pheromone), [LocalSearch](#LocalSearch), [Genetic](#Genetic)) into a single executable generational pipeline. Without this module, the `MemeticAlgorithm` class knows _how_ to cross over and mutate, but has no concept of populations, generations, elitism, or tournament selection. The engine provides the structural loop that turns individual genetic operations into an evolutionary search.

### Implementation

1. **Engine Initialization**
	The engine is constructed with the immutable `ExperimentConfig`, the active `CityGraph`, and an optional `DirectDemandSampler`. It internally instantiates the `ACOLocalSearch` operator suite (with probabilities loaded from the config) and the `MemeticAlgorithm` coordinator.

2. **Population Initialization (`initialize_state`)**
	The engine generates the initial population of `Chromosome` objects. For each chromosome in `n_population`:
	- A `RouteGenerator` synthesizes `num_routes` candidate transit loops from the demand distribution.
	- A **fresh, decoupled** `PheromoneMatrix` is instantiated exclusively for that chromosome. This is a critical design decision explained under [On-Decoupled-Pheromone-Initialization](#On-Decoupled-Pheromone-Initialization).
	- The chromosome is immediately evaluated via `evaluate_chromosome` to compute its initial fitness score.
	The population is sorted by cost, and the fittest chromosome's pheromone matrix is promoted to the master state.

3. **Generational Step (`step_generation`)**
	Each call to `step_generation` advances the population by one evolutionary cycle. The pipeline executes in strict sequential order:

	- **Elitism:** The top $n_{elite}$ chromosomes are copied directly into the next generation without modification.
	- **Tournament Selection:** For each remaining slot, $k$ chromosomes are sampled uniformly from the current population. The two fittest become Parent A and Parent B.
	- **Topological Hub Crossover:** The engine calls `crossover_topological_hub(parent_a, parent_b)` to generate the offspring's route set.
	- **Epigenetic Pheromone Inheritance:** The engine calls `inherit_pheromones(parent_a, parent_b)` to blend the parents' demand memory.
	- **Surrogate Evaluation:** The offspring is immediately evaluated to compute its baseline cost.
	- **Lamarckian Mutation Gate:** If a random draw falls below the current mutation rate, the engine triggers `apply_lamarckian_mutation`. The local search operators physically modify the offspring's routes. If the resulting cost is lower than the parent's cost, the mutation is accepted. Otherwise, the original routes are restored.
	- **State Update:** The new population is sorted. If the best cost improved, the stagnation counter resets. Otherwise, it increments.

### On-Decoupled-Pheromone-Initialization

Each chromosome in the initial population receives its own independent `PheromoneMatrix` rather than sharing a single global matrix. This is not a memory optimization — it is an architectural requirement.

If all chromosomes shared one pheromone matrix, the evaporation and deposition operations performed during the evaluation of one chromosome would contaminate the demand signal used to evaluate the next. Because the fitness evaluator refreshes pheromones as part of evaluation, sharing a matrix would create an order-dependent bias: chromosomes evaluated later would inherit the accumulated demand artifacts of chromosomes evaluated earlier.

By decoupling the matrices, each chromosome maintains a private demand map that reflects exclusively its own route topology and evaluated passenger journeys. When two chromosomes are selected for crossover, their private matrices are blended via `inherit_pheromones`, creating a child matrix that is a mathematically weighted fusion of two independently evolved demand surfaces. This preserves the integrity of the epigenetic inheritance mechanism described under [Genetic](#Genetic).

### On-Generational-Pipeline-Order

The strict ordering of operations within `step_generation` is not arbitrary:

1. **Elitism first** guarantees that the best-known solution is never lost, even if every crossover and mutation in that generation produces worse offspring. This monotonic guarantee is a foundational requirement of elitist genetic algorithms [^27].

2. **Evaluation before mutation** establishes the offspring's baseline cost. This baseline becomes the Lamarckian acceptance threshold. Without it, there is no reference point to determine whether a mutation improved or degraded the offspring.

3. **Mutation last** ensures that the local search operators act on a fully formed, evaluated chromosome with a populated pheromone matrix. The operators depend on demand-service gaps, which require an evaluated pheromone state to compute.

___
## StatePreservationEngine

### Logic

Evolutionary optimization runs are computationally expensive. A single Iligan City optimization at 30 generations with 10 chromosomes per population requires building and evaluating hundreds of candidate transit networks. If the process is interrupted — whether by a power failure, a manual stop, or a system crash — all generational progress is lost unless the state has been serialized to disk.

The `StatePreservationEngine` handles this serialization with two guarantees: **atomicity** (a checkpoint file is never left in a partially written, corrupted state) and **deterministic replay** (a resumed run produces the exact same results as if it had never been interrupted).

### Implementation

1. **Checkpoint Serialization**
	The `save_state` method serializes the entire `OptimizationState` (population, pheromone matrices, generation counter, stagnation counter, best fitness, and random state) into a Python pickle file indexed by generation number (`state_gen_{G}.pkl`).

2. **Atomic Write Pattern**
	The serialization writes to a temporary `.tmp` file first and only renames it to the final `.pkl` extension after the write completes successfully. If the process crashes mid-write, the `.tmp` file is discarded on the next run, and the previous valid checkpoint remains intact. This prevents the framework from ever loading a partially written, corrupted state file.

3. **Deterministic State Capture**
	Before serialization, the engine captures the Python pseudorandom number generator state via `random.getstate()` and stores it inside the `OptimizationState`. On resume, the `Optimizer` restores this exact state via `random.setstate()` _after_ all deterministic infrastructure (the `CityGraph`, `DirectDemandSampler`, and `MemeticEngine`) has been initialized. This ordering is critical: if `setstate()` were called before infrastructure initialization, any random calls during setup would consume random numbers that were intended for the evolutionary search.

### OptimizerBuilder

The `OptimizerBuilder` is a static factory class responsible for constructing isolated run environments:

- **`build_new_run`** creates a timestamped output directory under the configured `output_root` and copies the source YAML configuration file into it. This copy serves as a permanent, immutable record of the exact parameter set used for that experiment.
- **`resume_run`** locates the most recent valid checkpoint in an existing run directory, deserializes it, and reconstructs the `ExperimentConfig` from the stored YAML copy.

### On-Deterministic-Replay

Reproducibility in stochastic optimization is not optional — it is a scientific requirement. Two researchers running the same configuration on the same machine must produce identical results. The framework achieves this by capturing and restoring the pseudorandom state at every checkpoint boundary.

However, deterministic replay is fragile. It requires that the sequence of random number calls between the checkpoint and the next evolutionary step is identical on resume. If any module consumes random numbers during initialization (e.g., building a KDTree with random sampling), those calls must occur _before_ the captured state is restored. The `Optimizer` enforces this by calling `random.setstate()` strictly after `_init_engines()` completes, ensuring the random sequence for the evolutionary search is mathematically identical to the sequence that would have occurred without interruption.

___
## TelemetryEngine

### Logic

Evolutionary algorithms are opaque by default. A standard GA reports only the final best solution. But in a thesis defense, you must explain _how_ the algorithm arrived at that solution: which generations showed improvement, when stagnation occurred, which parent chromosomes produced the best offspring, and how the demand surface evolved across the search.

The `TelemetryEngine` makes the search transparent by logging three parallel data streams at configurable intervals throughout the optimization.

### Implementation

1. **Generational Metrics (`history.csv`)**
	Each logged generation appends a row containing: generation index, global best cost, population mean cost, active mutation rate, and stagnation counter. This provides the raw data for convergence plots in the results chapter.

2. **Lineage Tracking (`lineage.csv`)**
	Every chromosome in every generation is logged with: its unique ID, birth generation, fitness cost, and the UIDs of both parents. This creates a complete genealogical record. You can trace any chromosome in the final population back through its entire ancestral chain to the initial random population.

3. **JSON Network Snapshots**
	At each telemetry interval, the engine exports a high-fidelity JSON payload containing:
	- The best chromosome's route geometries (lat/lon coordinate sequences).
	- The pheromone intensity values for all edges above a configurable threshold.
	- The demand-service gap chokepoints (nodes with high positive gap values).
	- The topological hub coordinates (the node with the highest accumulated pheromone demand).
	- Population-level fitness distributions and unserved demand proxy values.

	These snapshots are designed for external GIS visualization clients. A downstream dashboard can consume the JSON sequence to render an animated visualization of the optimization's spatial evolution.

### On-Lineage-Tracking

Standard fitness convergence curves show _what_ happened. Lineage tracking shows _why_. If Generation 15 shows a sudden fitness improvement, the lineage CSV identifies exactly which two parents crossed over to produce that breakthrough chromosome. If the best solution at Generation 30 shares 80% of its edges with the best solution at Generation 5, the lineage trace proves that the algorithm preserved a high-quality trunk structure across 25 generations of crossover and mutation.

This data is also critical for validating the [Topological Hub Crossover](#Genetic). If the crossover operator is working correctly, the lineage should show that fitter parents disproportionately contribute trunk routes to their offspring. If fitter and weaker parents contribute equally, the hub extraction is failing to identify the correct high-demand corridors.

___
## Optimizer

### Logic

The `Optimizer` is the user-facing master orchestrator. Every module documented in this guide — the `CityGraph`, the `DirectDemandSampler`, the `TravelGraph`, the `MemeticEngine`, the `StatePreservationEngine`, the `TelemetryEngine`, and the `AdaptiveController` — is instantiated, wired, and executed by this single class. It is the entry point for running the optimization and the exit point for extracting results.

### Implementation

1. **Unified Infrastructure Initialization (`_init_engines`)**
	The optimizer loads the stored YAML configuration, detects the city topology (OSM real-city vs. synthetic toy grid), and constructs the complete spatial stack: `CityGraph`, `DirectDemandSampler`, `MemeticEngine`, `SimulationEvaluator`, `StaticSurrogateEvaluator`, `StatePreservationEngine`, `TelemetryEngine`, and `AdaptiveController`.

2. **Dual Evaluators**
	After initialization, the optimizer wires the memetic engine with two evaluators: a full fitness evaluator for GA scoring and a separate surrogate evaluator for local-search mutation checks:

	- **Surrogate Cost Computation:** The `StaticSurrogateEvaluator` computes the multi-modal A* routing cost for a fixed set of pre-sampled Origin-Destination pairs against the candidate's route topology during mutation checking only.
	- **Pheromone Lifecycle:** The evaluated passenger paths are used to perform a full evaporation-deposition cycle on the chromosome's private `PheromoneMatrix`.
	- **Gap Recalculation:** The chromosome's demand-service gaps are recomputed against its updated route system, preparing the spatial intelligence required by the next generation's local search operators.

	This fusion is a critical optimization. Without it, these three operations would require separate passes over the route topology, tripling the computational overhead per evaluation.

3. **The Main Search Loop (`start`)**
	The `start` method executes the evolutionary search. On each generation, it:
	- Queries the `AdaptiveController` for the current local search probability and intensity.
	- Boosts the mutation rate if stagnation is active.
	- Advances the population via `engine.step_generation`.
	- Logs lineage data via the `TelemetryEngine`.
	- Evaluates multi-dimensional convergence criteria (see [On-Multi-Dimensional-Convergence](#On-Multi-Dimensional-Convergence)).
	- Periodically exports telemetry snapshots and serializes checkpoints.

4. **State Reconstruction on Resume**
	When an `Optimizer` is instantiated from an existing run directory, the `_reconstruct_state_references` method rebuilds the object references that were lost during pickle serialization. Route paths are re-linked to the live `CityGraph` edge objects. Pheromone matrices are re-wired to their representative edge objects. This reconstruction is necessary because Python's `pickle` serializes object state but cannot preserve cross-module object identity.

### On-Unified-Evaluate-Gate

The GA path always stores the microscopic `fitness_score` in `Chromosome.cost`, while the surrogate remains a private heuristic for mutation acceptance and local-search guidance.

In a naive implementation, evaluation and pheromone updates would be separate operations. The engine would evaluate a chromosome, then separately trigger pheromone evaporation and deposition. This separation creates a timing hazard: between evaluation and pheromone update, the chromosome's demand-service gaps are stale. If the Lamarckian mutation gate triggers in this window, the local search operators would read outdated gap data, potentially directing route mutations toward corridors that are no longer underserved.

By fusing evaluation, pheromone lifecycle, and gap recalculation into a single atomic operation, the framework guarantees that every chromosome's spatial intelligence is temporally consistent at the exact moment mutation decisions are made.

### On-Multi-Dimensional-Convergence

The standard termination criterion for evolutionary algorithms is a stagnation limit: if the best fitness does not improve for $N$ consecutive generations, the search halts. This catches the case where the algorithm is stuck in a local optimum. However, it misses a subtler failure mode: _phenotypic convergence without fitness convergence_.

Consider a population where all chromosomes have slightly different costs but their route topologies are structurally identical. The fitness variance is non-zero (the algorithm appears to still be searching), but the genotypic diversity has collapsed. Every crossover produces an offspring that looks like its parents because there is no structural variation left to recombine.

To detect this, the optimizer computes two independent convergence metrics:

1. **Elite Jaccard Similarity:** The top 10% of the population (ranked by cost) are selected. For every pair of elites, the Jaccard similarity of their route edge sets is calculated:

	$$J(A, B) = \frac{|E_A \cap E_B|}{|E_A \cup E_B|}$$

	If the average pairwise Jaccard remains $\geq 0.95$ for a configurable number of consecutive generations (`jaccard_patience`), the optimizer terminates due to phenotypic saturation. This threshold indicates that the elite chromosomes share 95% or more of their topological structure — further crossover cannot meaningfully recombine them [^27].

2. **Fitness Variance:** If the population fitness variance falls below $10^{-6}$, the optimizer terminates due to genotypic convergence. At this point, the cost differences between chromosomes are negligible, and the algorithm has exhausted its ability to differentiate solutions.

By monitoring both structural topology and fitness distribution, the optimizer terminates efficiently regardless of which convergence failure mode occurs first.

### On-Fail-Safe-State-Preservation

The search loop is wrapped in a `try/except KeyboardInterrupt/finally` block. If the user manually interrupts execution (Ctrl+C), the `finally` clause triggers an immediate state checkpoint via the `StatePreservationEngine`. This guarantees that no generational progress is lost, even on forced termination. The optimizer reports the save location and exits cleanly.

**TODO:** The current stagnation limit and Jaccard patience values are configured but not empirically justified. We need to run ablation experiments to determine the optimal convergence thresholds for the Iligan City network topology.

**TODO:** Profile the computational overhead of the unified evaluate gate versus a separated evaluation-then-pheromone pipeline to empirically confirm the performance benefit.
___
# YAML-Configs

The optimization framework is configured exclusively through structured YAML files. No hyperparameter, penalty weight, or simulation constraint is hardcoded in the source. This section documents the configuration philosophy and the rationale behind the parameter groupings.

### Configuration Philosophy

Every optimization run copies its source YAML file into the run's output directory at initialization. This means every result in the `outputs/` folder carries a permanent, immutable record of the exact configuration that produced it. You can reproduce any experiment by pointing the `OptimizerBuilder` at the stored YAML copy.

### Parameter Groups

**City Graph**
Defines the spatial domain: bounding box coordinates, PBF file path, cache prefix, and optional named landmarks. The bounding box `[8.1500, 8.3300, 124.1500, 124.4000]` was selected to enclose all currently active Iligan City jeepney routes and terminal nodes, ensuring geographic parity with the existing transit system.

**Direct Demand Model**
Controls the demand surface synthesis. The `alpha` and `beta` coefficients weight the fusion of live traffic data and structural centrality respectively. The current split ($\alpha = 0.6$, $\beta = 0.4$) is justified by Ramos-Santiago's finding that local activity indicators exert a statistically heavier pull on ridership generation than pure geometric network location.

**Travel Graph Weights**
Defines the generalized cost penalties for each transition type in the multi-modal A* pathfinding. `walk_wt` and `ride_wt` are per-meter distance costs. `wait_wt` and `transfer_wt` are fixed penalties applied once per boarding and once per vehicle transfer, respectively. These penalties encode the behavioral friction that forces the pathfinding algorithm to prefer direct routes over multi-transfer journeys.

**Simulation Parameters**
Configures the agent-based simulation: vehicle capacity, tick granularity, speeds, fleet size, and passenger spawn rates. All numerical values are annotated with their empirical sources directly in the YAML comments (JICA congestion studies for vehicle speed, UP Diliman NCTS benchmarks for pedestrian speed, Iligan population statistics for spawn rates).

**Optimization Parameters**
Governs the evolutionary search: population size, generation limit, stagnation threshold, elitism count, tournament size, mutation rate, crossover coefficient, Jaccard patience, pheromone initialization/evaporation/deposition constants, local search operator probabilities, and system cost penalty weights.

### Current Limitation

The optimization parameters (lines 63–87 of `iligan_configs.yaml`) carry an explicit `[TODO] RESEARCH AND JUSTIFY THESE VALUES` comment. The current values are engineering defaults selected for computational tractability. A formal hyperparameter sensitivity analysis is required to justify these choices for the thesis.

___
# Post-Optimization Evaluation

The optimization loop produces candidate route systems. But a candidate is not a result. Before a route system can be presented in a thesis defense, it must be rigorously evaluated: "How similar is this system to the previous generation's system?" "By how much did that mutation actually change the route?" "Does the surrogate evaluator actually rank solutions correctly?" "How diverse are the routing options available to passengers?"

These questions cannot be answered by the fitness function alone. The fitness function compresses an entire route system into a single scalar cost. To actually understand what the optimizer produced, we need a vocabulary of comparison metrics — topological, geometric, distributional, and statistical.

The framework addresses this with a two-layer architecture:

1. **`evaluation_metrics.py`** — The mathematical toolkit. Pure, stateless functions that operate on primitive data types (sets, lists, vectors). No domain knowledge. This module knows nothing about routes or chromosomes — it knows about Jaccard similarity, Fréchet distance, and Wasserstein transport.

2. **`post_evaluation.py`** — The domain-specific evaluation workflows. This module knows about routes, chromosomes, and simulation results. It extracts the right data from domain objects, calls the metrics, and returns meaningful evaluation reports.

___
## EvaluationMetrics

### Logic

Every evaluation question reduces to a mathematical operation on a specific data representation. "How topologically similar are two edge sets?" is a set overlap problem (Jaccard). "How geometrically similar are two ordered coordinate sequences?" is a trajectory comparison problem (Fréchet). "How much work to reshape one demand distribution into another?" is an optimal transport problem (Wasserstein).

By isolating these operations as pure functions with no domain coupling, the toolkit becomes independently testable, reusable across modules (the optimizer already uses Jaccard internally for convergence detection), and transparent in its mathematical assumptions.

### Implementation

The metrics are organized into five categories:

1. **Topological Similarity** — Metrics that operate on sets and graph structures.
	- `jaccard_similarity(set_a, set_b)` — Proportion of shared elements between two sets.
	- `cosine_similarity(vector_a, vector_b)` — Angular alignment of two sparse feature vectors.
	- `graph_edit_distance(edges_a, edges_b)` — Minimum structural edit operations to transform one graph into another.

2. **Geometric Similarity** — Metrics that operate on ordered coordinate sequences.
	- `discrete_frechet_distance(P, Q)` — Minimum leash length for two traversals (order-preserving).

3. **Distributional Distance** — Metrics that compare probability distributions.
	- `wasserstein_1d(dist_a, dist_b)` — Earth Mover's Distance between two univariate samples.
	- `wasserstein_2d(coords_a, weights_a, coords_b, weights_b)` — Optimal transport cost between two weighted spatial distributions.
	- `ks_test(dist_a, dist_b)` — Kolmogorov-Smirnov two-sample test for distributional equivalence.

4. **Diversity & Structure** — Metrics that characterize a single distribution.
	- `shannon_entropy(frequencies)` — Information-theoretic diversity measure.
	- `coefficient_of_variation(data)` — Relative dispersion (σ/μ).

5. **Ranking Fidelity** — Metrics that compare two ranked orderings.
	- `spearman_correlation(scores_a, scores_b)` — Rank correlation coefficient.
	- `kendall_tau(scores_a, scores_b)` — Concordance of pairwise orderings.
	- `pearson_correlation(vector_a, vector_b)` — Linear correlation.
	- `top_k_overlap(ranking_a, ranking_b, k)` — Precision/recall of top-k sets.
	- `normalized_rmse(predicted, actual)` — Scale-independent prediction error.
	- `mape(baseline, test)` — Mean Absolute Percentage Error.

### On-Jaccard-Similarity

Jaccard similarity is the simplest topological comparison: it counts how many elements two sets share, normalized by the total number of distinct elements across both sets.

$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$

For route systems, the "elements" are edge IDs. If System A uses 100 street segments and System B uses 100 street segments, and 80 of those segments are identical, then $J = 80 / 120 = 0.667$. The metric is symmetric, bounded $[0, 1]$, and requires no parameter tuning.

The Jaccard index appears throughout the framework: inside the optimizer for convergence detection ([On-Multi-Dimensional-Convergence](#On-Multi-Dimensional-Convergence)), in the crossover operator for trunk identification ([Genetic](#Genetic)), and here in post-evaluation for system comparison. By centralizing it in `evaluation_metrics.py`, all three use cases call the same implementation.

### On-Discrete-Fréchet-Distance

The Fréchet distance is often explained as the "dog walker" metric: imagine a person walking along path $P$ and a dog walking along path $Q$, both connected by a leash. Neither can backtrack. The Fréchet distance is the minimum leash length required for both to complete their traversals.

The discrete variant — introduced by Eiter and Mannila (1994)[^28] — restricts the comparison to the vertex sequences of each path and computes the result via a standard $O(n \times m)$ dynamic programming recurrence:

$$ca(i, j) = \max\left(\min\left(ca(i-1, j),\ ca(i, j-1),\ ca(i-1, j-1)\right),\ d(P_i, Q_j)\right)$$

where $d(P_i, Q_j)$ is the Euclidean distance between the $i$-th vertex of $P$ and the $j$-th vertex of $Q$.

Critically, Fréchet respects traversal order. Two routes sharing identical streets but traveling in opposite directions correctly register as dissimilar. This makes it strictly more informative than Hausdorff distance (which is order-agnostic) for evaluating route mutations, where the question "did the mutation reverse a segment?" is diagnostically important.

### On-Wasserstein-Distance

The Wasserstein distance (Earth Mover's Distance) asks: "What is the minimum cost to reshape one pile of demand into the shape of another?" The "cost" is mass × distance moved.

Formally, given two probability distributions $\mu$ and $\nu$ over a metric space, the 1-Wasserstein distance is:

$$W_1(\mu, \nu) = \inf_{\gamma \in \Gamma(\mu, \nu)} \int_{X \times X} d(x, y) \, d\gamma(x, y)$$

where $\Gamma(\mu, \nu)$ is the set of all joint distributions (transport plans) with marginals $\mu$ and $\nu$.

The framework implements two variants:

- **1D Wasserstein** (`scipy.stats.wasserstein_distance`): Compares univariate empirical distributions (e.g., travel time samples from two different runs). This has a closed-form solution via sorted quantile matching.

- **2D Wasserstein** (linear programming formulation): Compares two weighted spatial point distributions. Given node coordinates and demand weights for two route systems, the LP solver finds the minimum-cost plan to redistribute demand mass from System A's configuration to System B's. This is computationally expensive ($O(n^3)$ for the simplex method) but exact.

De Bacco et al. (2023)[^29] applied optimal transport theory to compare multi-layer urban network structures. Their formulation is directly analogous to comparing the demand coverage distributions of two candidate route systems — both involve weighted spatial graphs with multi-modal connectivity.

Unlike Jaccard (which is purely topological) or Fréchet (which is purely geometric), Wasserstein is demand-aware. Two systems that cover different streets but serve the same demand surface will have a low Wasserstein distance. Two systems that cover the same streets but serve different demand distributions will have a high Wasserstein distance. This makes it the correct metric for the question "how differently do these systems serve the city?"

### On-Shannon-Entropy-for-Path-Diversity

Shannon entropy quantifies the diversity of a distribution:

$$H = -\sum_{i} P(x_i) \log_2 P(x_i)$$

Applied to the passenger path frequency distribution, entropy measures how many distinct routing options a transit system offers. A system where 90% of passengers take the same path has low entropy (bottleneck). A system where passengers are distributed across many distinct paths has high entropy (genuine multi-modal choice).

Levinson (2012)[^30] applied entropy measures specifically to urban transportation networks, demonstrating that structural diversity correlates with network resilience — systems with higher routing entropy are more robust to link failures and demand perturbations.

### On-Spearman-for-Surrogate-Validation

The surrogate evaluator computes a fast proxy cost. The critical question is not "does the surrogate predict the exact cost?" but "does the surrogate correctly rank solutions?"

Evolutionary selection is ranking-based: tournament selection picks the fittest of $k$ random chromosomes, elitism preserves the top $n$. These operations depend entirely on relative ordering, not absolute magnitude. If the surrogate says Chromosome A costs 500 and Chromosome B costs 600, and the true costs are 7000 and 8000, the surrogate is perfectly useful despite being wildly inaccurate — it correctly identified A as better than B.

Jin (2005)[^31] explicitly establishes Spearman rank correlation as the primary validation metric for fitness approximation in evolutionary computation. A Spearman $\rho \geq 0.7$ indicates that the surrogate preserves enough ranking fidelity for reliable selection pressure. Below $0.5$, the surrogate is actively misleading the search.

The framework additionally reports Kendall $\tau$ (more robust for small sample sizes), NRMSE (scale-independent magnitude error), and MAPE (percentage error) — but Spearman is the decision-making metric.

### On-KS-Test-for-Stochastic-Consistency

The Kolmogorov-Smirnov two-sample test determines whether two sets of observations are drawn from the same underlying probability distribution. It computes the maximum vertical distance between the two empirical cumulative distribution functions:

$$D_{n,m} = \sup_x |F_n(x) - G_m(x)|$$

For transit evaluation, this validates stochastic consistency: if the same route system is simulated twice with different random seeds, the resulting travel time distributions should be statistically identical ($p \geq 0.05$). If they are not, the simulation has insufficient sample size or a non-deterministic bug.

___
## PostEvaluation

### Logic

The mathematical metrics in `evaluation_metrics.py` operate on primitive types — sets, lists, tuples. But the questions we actually need to answer involve domain objects: "Compare these two Chromosomes." "Track how this route system evolved across 30 generations." "Validate whether our surrogate evaluator is trustworthy."

The `post_evaluation.py` module bridges this gap. It extracts the right data from domain objects (`Route.path` → coordinate sequences, `Chromosome.routes` → aggregate edge sets, `SimulationResult.recorded_paths` → path frequency distributions), calls the appropriate metric, and returns a meaningful result.

It is the post-run analysis layer for answering questions about the final score itself: whether the surrogate ranking matches the full simulation, whether topology changes correlate with fitness improvement, and whether the passenger paths remain diverse after optimization.

### Implementation

1. **Route Similarity**
	- `compare_routes_geometric(route_a, route_b)` — Extracts coordinate sequences from each route's edge path and computes the discrete Fréchet distance. This is the correct metric for quantifying how much a Lamarckian mutation physically displaced a route.
	- `compare_routes_topological(route_a, route_b)` — Extracts edge ID sets and computes Jaccard similarity. This answers whether two routes share the same infrastructure, regardless of geometry.

2. **System Similarity**
	- `compare_systems_topological(chrom_a, chrom_b)` — Aggregates all edge IDs across all routes in each chromosome and computes Jaccard. This is the system-level version of "do these systems serve the same streets?"
	- `compare_systems_structural(chrom_a, chrom_b)` — Computes Graph Edit Distance between the two network topologies. Unlike Jaccard (which measures overlap), GED quantifies the minimum number of structural modifications to transform one system into another.
	- `compare_systems_degree_distribution(chrom_a, chrom_b)` — Extracts node degree distributions and computes cosine similarity. This captures whether the same nodes serve as hubs in both systems, even if the specific edges differ.
	- `compare_systems_demand_coverage(chrom_a, chrom_b, sampler)` — Computes the 2D Wasserstein distance between the demand coverage distributions. This is the demand-aware comparison: "how differently do these systems serve the city's passengers?"

3. **Generational Tracking**
	- `track_topological_drift(gen_chromosomes)` — Given a sequence of best-chromosomes across generations, computes consecutive Jaccard similarities. A drift trace that stabilizes near 1.0 indicates convergence. A drift trace that oscillates indicates the optimizer is cycling.
	- `track_fitness_correlation(gen_chromosomes)` — Correlates topological change ($1 - J$) with fitness improvement ($\Delta cost$). A strong negative Pearson $r$ means topology changes reliably improve fitness. A weak or positive $r$ means the optimizer is making structural changes that don't help.
	- `compute_path_diversity(recorded_paths)` — Shannon entropy over the passenger path frequency distribution from a simulation result.

4. **Surrogate Fidelity**
	- `validate_surrogate_ranking(surrogate_scores, true_scores)` — Compares `surrogate_cost` values against the full simulation `fitness_score` values and returns Spearman $\rho$, Kendall $\tau$, NRMSE, and MAPE. This is the comprehensive surrogate validation suite.
	- `validate_surrogate_top_k(surrogate_ranking, true_ranking, k)` — Precision/recall of the surrogate's top-$k$ against the true evaluator's top-$k$.
	- `validate_distribution_consistency(dist_a, dist_b)` — KS-test with a human-readable report.

**TODO:** Run `validate_surrogate_ranking` on actual optimization telemetry data and report the Spearman $\rho$ in the results chapter. This directly addresses the existing TODO: "Prove the direct mathematical correlation between the static surrogate routing cost and the dynamic temporal cost of the full agent-based simulation."

**TODO:** Integrate `track_topological_drift` into the `TelemetryEngine` to automatically log structural evolution alongside fitness convergence.


**TODO:** Establish baseline path diversity (Shannon entropy) thresholds for the Iligan City network using historical jeepney route data.

___
## SimplifiedFacade

### Logic

The `utils_simplified.py` file implements a unified Facade Pattern to simplify interactions with the complex paratransit optimization system. The backend consists of multi-layered road networks, agent-based simulations, TomTom traffic clients, genetic algorithms, and local search operators. Managing their interdependencies requires extensive boilerplate. The facade hides these complex details behind high-level, procedural functions, making the optimization framework more accessible for research, testing, and pipeline orchestration.

### Key API Functions

#### 1. City Graph
- `build_citygraph(yaml_file: str, pkl_path: Optional[str] = None) -> CityGraph`
  - Loads a YAML configuration file, extracts the bounding box and parameters, instantiates a `CityGraph` representing the street layer (Layer 0), and optionally serializes it to a pickle file for high-performance reuse.
- `reuse_citygraph(pkl_file: str) -> CityGraph`
  - Deserializes a cached `CityGraph` from a pickle file to bypass expensive road network parsing.

#### 2. Direct Demand Model
- `build_ddm(yaml_file: str, cg: CityGraph, target_time: Optional[datetime], pkl_path: Optional[str] = None) -> DirectDemandSampler`
  - Instantiates `DDMConfig` and `DirectDemandSampler`, queries the TomTom API for traffic data matching the target time, and optionally caches the sampler.
- `reuse_ddm(pkl_file: str) -> DirectDemandSampler`
  - Deserializes a cached `DirectDemandSampler` from a pickle file.

#### 3. Travel Graph and Transit Infrastructure
- `generate_route_system(num_routes: int, cg: CityGraph, sampler: DirectDemandSampler) -> list[Route]`
  - Generates a set of transit routes using a `RouteGenerator` weighted by spatial passenger demand.
- `build_travelgraph(cg: CityGraph, yaml_file: str, routes: list[Route], pkl_path: Optional[str] = None) -> TravelGraph`
  - Compiles the multi-layer topological graph (`TravelGraph`) by stitching together the street layer and the transit routes.
- `reuse_travelgraph(pkl_file: str) -> TravelGraph`
  - Deserializes a cached `TravelGraph` from a pickle file.

#### 4. Simulation Execution
- `generate_jeep_system(routes: list[Route], num_jeeps: int, sampler: DirectDemandSampler, tg: TravelGraph, mohring_sample_size=200) -> JeepSystem`
  - Allocates fleet vehicles across the routes using Mohring square-root demand balancing and instantiates a `JeepSystem` with equidistant vehicle spacing.
- `run_simulation(tg: TravelGraph, yaml_file: str, jeep_system: JeepSystem, sampler: DirectDemandSampler, delete_yaml_when_done=False) -> Simulation`
  - Initializes and runs a microscopic agent-based simulation for the configured number of ticks.
- `run_simulation_env(env: SimEnvironment) -> Simulation`
  - A helper function that executes a simulation using a lightweight `SimEnvironment` container object.
- `run_simulations_parallel(envs: list[SimEnvironment], max_workers: Optional[int] = None) -> list[SimulationResult]`
  - Runs multiple simulation setups in parallel using the `ParallelSimulationRunner` to leverage multi-core processors.

#### 5. Pheromones and Local Search Mutators
- `build_pheromone_matrix(cg: CityGraph, sim_result: SimulationResult) -> PheromoneMatrix`
  - Initializes a `PheromoneMatrix` and registers passenger travel paths and demand-service gaps.
- `blend_pheromone_matrix(parentA, parentB, cg: CityGraph) -> PheromoneMatrix`
  - Blends two parent pheromone distributions using a fitness-weighted arithmetic crossover.
- `mutate_attraction`, `mutate_repulsion`, and `mutate_pruning`
  - High-level wrappers for applying individual local search operations (`strategy_spatial_attraction`, `strategy_redundancy_repulsion`, and `strategy_tortuosity_pruning`) to a route system.

#### 6. Optimizer and Telemetry
- `build_optimizer(yaml_file: str, resume_dir: Optional[str] = None) -> Optimizer`
  - Constructs or resumes a multi-generational evolutionary search run.
- `process_telemetry(run_dir: str) -> dict`
  - Parses an optimizer run's `history.csv` and `lineage.csv` files into pandas DataFrames for downstream data analysis and plotting.
- `load_generation_snapshot(run_dir: str, generation: int) -> dict`
  - Loads a JSON snapshot representing the network state at a specific generation.

# References

[^1]: Guillen, M. D., Ishida, H., & Okamoto, N. (2013). Is the use of informal public transport modes in developing countries habitual? An empirical study in Davao City, Philippines. _Transport Policy_, _26_, 31-42.
[^2]: Bowling, S. T., & Aultman-Hall, L. I. S. A. (2003). Development of a Random Sampling Procedure for. _Journal of Transportation and Statistics_, _6_, N1.
[^3]: Lowry, M. (2014). Spatial interpolation of traffic counts based on origin–destination centrality. _Journal of Transport Geography_, _36_, 98-105.
[^4]: Snyder, J. P. (1987). _Map projections: A working manual_ (U.S. Geological Survey Professional Paper 1395). U.S. Government Printing Office.
[^5]: Freeman, L. C. (1977). A set of measures of centrality based on betweenness. _Sociometry_, 35-41.
[^6]: Walker, A. J. (1977). An efficient method for generating discrete random variables with general distributions. _ACM Transactions on Mathematical Software (TOMS)_, _3_(3), 253-256.
[^7]: Farahani, R. Z., Miandoabchi, E., Szeto, W. Y., & Rashidi, H. (2013). A review of urban transportation network design problems. _European journal of operational research_, _229_(2), 281-302.
[^8]: Mandl, C. E. (1980). Evaluation and optimization of urban public transportation networks. _European Journal of Operational Research_, _5_(6), 396-404.
[^9]: Bentley, J. L. (1975). Multidimensional binary search trees used for associative searching. _Communications of the ACM_, _18_(9), 509-517.
[^10]: Peng, P., Claramunt, C., Cheng, S., Yang, Y., & Lu, F. (2023). A multi-layer modelling approach for mining versatile ports of a global maritime transportation network. _International Journal of Digital Earth_, _16_(1), 2129-2151.
[^11]: Heyken Soares, P. (2021). Zone-based public transport route optimisation in an urban network. _Public Transport_, _13_(1), 197-231.
[^12]: Yang, Y., Cheng, J., & Liu, Y. (2024). An overview of solutions to the bus bunching problem in urban bus systems. _Frontiers of Engineering Management_, _11_(4), 661-675.
[^13]: Samson, B. P. V., Marcaida, C. N. P., Gervasio, E. A. B., Militar, R. D., & Ibanez, J. (2017). Analyzing Congestion Dynamics in Mass Rapid Transit using Agent-Based Modeling. In _17th Philippine Computing Science Congress. Computing Society of the Philippines, Cebu City, Philippines_ (pp. 209-214).
[^14]: He, C., Zhang, Y., Gong, D., & Ji, X. (2023). A review of surrogate-assisted evolutionary algorithms for expensive optimization problems. _Expert Systems with Applications_, _217_, 119495.
[^15]: Dorigo, M., Maniezzo, V., & Colorni, A. (1996). Ant system: optimization by a colony of cooperating agents. _IEEE transactions on systems, man, and cybernetics, part b (cybernetics)_, _26_(1), 29-41.
[^16]: Blum, C., & Roli, A. (2003). Metaheuristics in combinatorial optimization: Overview and conceptual comparison. _ACM computing surveys (CSUR)_, _35_(3), 268-308.
[^17]: Mohring, H. (1971). Optimization and Scale Economies in Urban Bus Transportation.
[^18]: Baaj, M. H., & Mahmassani, H. S. (1991). An AI‐based approach for transit route system planning and design. _Journal of advanced transportation_, _25_(2), 187-209.
[^19]: Kepaptsoglou, K., & Karlaftis, M. (2009). Transit route network design problem. _Journal of transportation engineering_, _135_(8), 491-505.
[^20]: Ceder, A., & Wilson, N. H. (1986). Bus network design. _Transportation Research Part B: Methodological_, _20_(4), 331-344.
[^21]: Fan, W., & Machemehl, R. B. (2006). Optimal transit route network design problem with variable transit demand: genetic algorithm approach. _Journal of transportation engineering_, _132_(1), 40-51.
[^22]: Reynolds, R. G. (1994, February). An introduction to cultural algorithms. In _Proceedings of the third annual conference on evolutionary programming_ (Vol. 24, No. 26, pp. 131-139).
[^23]: Gschwender, A., Jara-Díaz, S., & Bravo, C. (2016). Feeder-trunk or direct lines? Economies of density, transfer costs and transit structure in an urban context. _Transportation Research Part A: Policy and Practice_, _88_, 209-222.
[^24]: Risso, C., Nesmachnow, S., & Faller, G. (2023). Optimized design of a backbone network for public transportation in Montevideo, Uruguay. _Sustainability_, _15_(23), 16402.
[^25]: Middendorf, M., Reischle, F., & Schmeck, H. (2002). Multi colony ant algorithms. _Journal of Heuristics_, _8_(3), 305-320.
[^26]: Eiben, Á. E., Hinterding, R., & Michalewicz, Z. (1999). Parameter control in evolutionary algorithms. IEEE Transactions on evolutionary computation, 3(2), 124-141.
[^27]: Sastry, K., Goldberg, D. E., & Kendall, G. (2013). Genetic algorithms. In Search methodologies: Introductory tutorials in optimization and decision support techniques (pp. 93-117). Boston, MA: Springer US.
[^28]: Eiter, T., & Mannila, H. (1994). Computing discrete Fréchet distance. _Technical Report CD-TR 94/64_, Technische Universität Wien.
[^29]: De Bacco, C., Baptista, D., Sarkar, S., & Kalantzis, V. (2023). Optimal transport in multilayer networks for traffic flow optimization. _Physical Review Research_, _5_(4), 043028.
[^30]: Levinson, D. (2012). Network structure and city size. _PLoS ONE_, _7_(1), e29721.
[^31]: Jin, Y. (2005). A comprehensive survey of fitness approximation in evolutionary computation. _Soft Computing_, _9_(1), 3-12.
[^32]: Ortúzar, J. de D., & Willumsen, L. G. (2011). _Modelling Transport_ (4th ed.). Wiley.
[^33]: Coello Coello, C. A. (2002). Theoretical and numerical constraint-handling techniques used with evolutionary algorithms: a survey of the state of the art. _Computer Methods in Applied Mechanics and Engineering_, _191_(11-12), 1245-1287.
[^34]: Welch, T. F., & Mishra, S. (2013). A measure of equity for public transit connectivity. _Journal of Transport Geography_, _33_, 29-41.
[^35]: Jara-Díaz, S., & Gschwender, A. (2003). Towards a general microeconomic model for the operation of public transport. _Transport Reviews_, _23_(4), 453-469.
[^36]: Iseki, H., & Taylor, B. D. (2009). Not all transfers are created equal: Towards a framework relating transfer connectivity to travel behaviour. _Transport Reviews_, _29_(6), 777-800.
[^37]: Laporte, G., & Semet, F. (2002). Classical heuristics for the capacitated VRP. In _The vehicle routing problem_ (pp. 109-128). Society for Industrial and Applied Mathematics.
[^38]: Ciaffi, F., Cipriani, E., & Petrelli, M. (2012). Feeder bus network design problem: A new metaheuristic procedure and real size applications. _Procedia-Social and Behavioral Sciences_, _54_, 798-807.
