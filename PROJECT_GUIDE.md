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

1. **Empirical Sampling Limitation**
	Because of external rate limits, we cannot query the live traffic API for every topological node. We use a random sampling procedure instead to extract a statistically viable subset of discrete geographical nodes. Bowling and Aultman-Hall (2003)[^2] validated this approach for applying random sampling directly to local road networks when constrained by resources.

2. **Spatial Interpolation**
	We estimate traffic weights for all unqueried nodes using [Inverse Distance Weighting (IDW)](#On-Inverse-Distance-Weighting). The model applies the [Haversine formula](#On-Haversine-Formula) to compute true great-circle distances [^4]. This prevents spherical distortion caused by planar geometry during the spatial interpolation process.

3. **Structural Weighting**
	We calculate [Betweenness Centrality](#On-Betweeness-Centrality) to identify structural network importance, which measures the exact frequency a node appears on the shortest paths across the graph [^5]. It establishes a baseline topological weight independent of live traffic conditions.

4. **Probability Resolution**
	Lowry (2014)[^3] proved that [Origin-Destination Centrality](#On-Origin-Destination-Centrality) operates as a highly accurate variable for interpolating traffic volumes across unmeasured nodes. 	The final demand probability ($P_i$) per node is calculated by fusing the empirical or imputed traffic weight ($W_i$) and the betweenness centrality ($C_i$). These are scaled by calibration parameters ($\alpha, \beta$) using the equation $P_i = W_i^\alpha \times C_i^\beta$.

5. **Alias Table Construction**
	The resolved probabilities are scaled and structured into a [Walker's Alias table](#On-Walker's-Alias-Table). This data structure guarantees $O(1)$ time complexity for all subsequent spatial sampling during route generation [^6].

#### On-Tomtom-API
The `TrafficClient` isolates network requests from the mathematical engine. It queries the TomTom Traffic Flow API exclusively for the randomly sampled target centroids. The system extracts real-time speed and free-flow speed data to calculate the empirical traffic weight as the ratio of free-flow speed to current speed. To eliminate redundant network operations, all API responses are persistently cached as JSON payloads indexed by MD5 coordinate hashes.
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
        
3. **Surrogate Fitness Evaluation**
    
    The module exposes a `surrogate_evaluate()` method. Instead of running the full tick-by-tick temporal simulation, this method computes the static A* multi-modal journey cost for a predefined set of Origin-Destination (OD) pairs on the `TravelGraph`. It returns a `SimulationResult` containing the aggregate passenger routing cost and the fleet operational cost (total distance of the route loops).
    

### On-Event-Driven-State-Transitions

As established in the Jeep System documentation, individual vehicles and passengers do not directly interact with one another in the codebase. The `Simulation` class acts as the supreme mediator.

When a jeepney reaches a node, it does not search for passengers. It simply reports its state to the simulation controller. The controller then queries the `TravelGraph` and handles the complex logic of boarding, capacity checking, and alighting. This event-driven architecture strictly enforces the separation of concerns. It allows the mathematical physics engine to run independently of the behavioral state machines, drastically reducing computational overhead during high-density simulations.

### On-Surrogate-Fitness-Evaluation-in-Metaheuristics

The framework is designed to optimize jeepney routes using a hybrid GA-ACO algorithm. Evolutionary algorithms require evaluating thousands of candidate solutions (route sets) across multiple generations. Running a full tick-based, micro-level agent simulation to evaluate every single candidate chromosome is computationally prohibitive.

To solve this, the framework implements `surrogate_evaluate()`. In complex combinatorial optimization, surrogate models or approximation functions are utilized to replace computationally expensive objective evaluations during the primary search phases (He et al., 2024). By bypassing the temporal physics engine and directly computing the static multi-modal A* costs for a representative sample of OD pairs, the surrogate evaluation provides a mathematically sound, high-speed objective cost proxy. The algorithm can evaluate thousands of route sets using this $O(1)$ temporal approximation, reserving the expensive, full agent-based simulation strictly for the final validation of the optimal route sets.

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
    
    The module actively computes the Demand-Service Gap for every edge to evaluate spatial transit coverage. It calculates the total pheromone demand ($\tau$) on a specific corridor and subtracts the current service supply (the number of jeeps currently assigned to traverse that edge multiplied by a `default_jeep_weight`).
	
	- A **positive gap** indicates an underserved corridor (demand exceeds supply).
	    
	- A **negative gap** indicates an over-served corridor.
	    
    This metric is cached and directly utilized by the GA operators to intelligently guide spatial mutation. By tracking both positive and negative values, the framework generates a comprehensive topological map of service disparities across the city. The GA uses this full spectrum to dynamically adjust mutation parameters (Eiben et al., 1999). It mathematically biases the algorithm to pull route topologies away from heavily negative, over-served regions and push them toward highly positive, underserved corridors. Once the physical routes are spatially balanced by this push and pull dynamic, the framework defers the actual vehicle volume distribution to the `FleetAllocator` utilizing the Mohring allocation.

**TODO:** Generate a map visualization showing the step-by-step execution of the "cheapest-insertion cost scoring" to demonstrate exactly how the route bends toward a demand hotspot.
    
**TODO:** Provide a statistical breakdown of route lengths before and after the pruning operator is applied to empirically validate the reduction in tortuosity as defined by Ceder and Wilson.

___
## LocalSearch 
(The Lamarckian Mutation Part)
### Logic

The `ACOLocalSearch` module functions as the active mutation engine of the framework. Rather than relying on stochastic Darwinian mutation, the framework deploys three targeted Lamarckian operators. These operators read the Demand-Service Gaps mapped by the `PheromoneMatrix` and actively modify the topological structure of the candidate routes before they are evaluated. By allowing candidate solutions to learn from environmental feedback and pass those improvements to the next generation, the algorithm operates as a highly efficient Memetic Algorithm.

### 1. Demand-Driven Attraction (Node Insertion)

**Academic Justification:** In TRNDP metaheuristics, transit networks must constantly adapt to capture unmet passenger demand. Much like Baaj and Mahmassani [^18]  did in their Route Generation Algorithm by employing specific "node selection and insertion strategies" to connect high-demand pairs, this framework utilizes a Demand-Driven Attraction mechanism. Kepaptsoglou and Karlaftis [^19] explicitly noted in their comprehensive review that demand-guided node addition is a primary heuristic for capturing unserved market share.

**Implementation Strategy:**

This operator identifies contiguous sequences of underutilized edges and computes their proximity to high Demand-Service Gap clusters. To execute this, the algorithm employs a cheapest-insertion cost scoring mechanism rather than a naive closest-edge approach. It calculates the optimal entry and exit nodes along the existing route and executes a true zero-width insertion. This mathematically bends the route toward the hotspot without destroying existing structural connectivity, completely eliminating the risk of generating inefficient hairpin detours.

### 2. Oversupply Repulsion (Route Overlap Minimization)

**Academic Justification:** Operator viability requires minimizing redundant vehicle kilometers. Fan and Machemehl [^21] explicitly modeled the Transit Route Network Design Problem to balance user costs against operator costs and the penalties. Kepaptsoglou and Karlaftis [^19] reviewed several models that deliberately constrained route overlap to maximize spatial coverage and disperse fleet resources efficiently. Moving a highly useful route segment away from a low-served area provides no mathematical benefit, but if multiple routes share the same highly served segment, they create fleet redundancy.

**Implementation Strategy:**

The repulsion operator isolates one of the overlapping routes on a negative-gap corridor and mathematically repels it to a parallel street.

- **Haversine Similarity:** To accurately identify overlapping routes on a global scale, the algorithm replaces flat Euclidean distance with the Haversine formula. This computes the true great-circle distance between route nodes, guaranteeing spatial accuracy for the similarity matrix.
    
- **Constrained Detour Routing:** By applying a spatial exclusion window, the algorithm forces a detour. It temporarily penalizes the overserved edges, forcing the A* search to bridge the gap via adjacent, underserved blocks, thereby maintaining general directional utility while explicitly expanding spatial coverage.
    

### 3. Demand-Aware Tortuosity Pruning (Node Deletion & Circuity Reduction)

**Academic Justification:** A robust public transit network relies on directness of service. Ceder and Wilson [^20] established that minimizing the difference between indirect and direct passenger-hours (a concept known as circuity or tortuosity) is critical for effective bus network design. To combat tortuosity, Baaj and Mahmassani [^18] incorporated route improvement algorithms specifically designed to fix inefficiencies and ensure directness of service.

**Implementation Strategy:**

This operator identifies segments that meander inefficiently between high-demand hubs. It amputates the detour and bridges the gap using a strict A* shortest-path calculation on the base `CityGraph`.

The mathematical robustness of this operator relies on two critical safeguards:

- **Zero-Utility Correction:** When evaluating the passenger utility of a route segment, edges that have no recorded passenger traffic must strictly evaluate to a pheromone value of 0.0 rather than a baseline default. This ensures that unused, dead-end detours receive an infinite cost penalty, immediately flagging them as targets for algorithmic node deletion.
    
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

The `evaluate_chromosome` method bypasses the tick by tick physics engine. It utilizes the `FleetAllocator` to quickly estimate headways and route lengths via Mohring fractions, generating a heuristic system cost in $O(1)$ time.

Furthermore, the algorithm actively applies Lamarckian mutation by running the `ACOLocalSearch` operators to physically manipulate the routes. If the resulting surrogate cost is lower than the target, the acquired improvements are permanently locked into the chromosome's genotype. If the mutation degrades the network, the algorithm reverts to the original backup routes, ensuring monotonic generational improvement.

**TODO:** Provide a convergence graph in your results chapter comparing the generational cost reduction of this Lamarckian Memetic Algorithm against a standard Darwinian control group to empirically prove the acceleration provided by the Belief Space.

**TODO:** Validate the correlation between the $O(1)$ surrogate cost estimate and the final agent-based simulation cost to prove the surrogate's accuracy.
___
# YAML-Configs

___
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
