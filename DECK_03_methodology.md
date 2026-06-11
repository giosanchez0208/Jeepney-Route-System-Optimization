# DECK 03 — Chapter 3: Methodology
*(★ spine = narrate · detail = skim / jump-to. Figures named where relevant.)*

---

## Slide 3-1 — The pipeline (one slide) ★
**On-slide:** *(Diagram `fig_system_pipeline.png`)* Survey → **EIVM**; OSM → **CityGraph**; TomTom + centrality →
**Demand Model**; CityGraph + routes + weights → **3-layer TravelGraph**; agents → **simulation = F_sim**;
**Memetic GA–ACO** proposes networks scored by simulation → optimized network.
**🎤** "Here's the whole method on one slide. Empirical inputs on the left feed three environment objects; the agent
simulation turns any candidate network into one fitness number; and the optimizer loops — propose, simulate, learn,
repeat. I'll walk each block in order."
**📝** Spend time. This is the map. Emphasize the *loop* (simulation is the evaluator inside the optimizer).

---

### §3.1 — Survey & EIVM Calibration

## Slide 3-2 — One cost unit: EIVM ★
**On-slide:** Everything priced in **EIVM** = "1 minute riding inside a jeepney." A journey mixes metres + minutes +
transfers → convert all to one scale so A\* can compare whole journeys.
**🎤** "The foundation is one unit. A trip mixes metres walked, minutes waited, and a transfer — things you can't add
directly. So we convert everything into Equivalent In-Vehicle Minutes. Once it's all one currency, the pathfinder can
compare entire journeys fairly."
**📝** ⚠ Anchor #1: EIVM drives *path choice*; the fitness is realized *seconds*. ortuzar2011 (generalized cost).

## Slide 3-3 — The survey (detail)
**On-slide:** 214 respondents, bilingual (English/Cebuano), Google Forms, May 2026. Six sections: Usual Trip · Walking
Tolerance · Waiting Tolerance · Transfer Behavior · Demographics · Comments. Consent + Data Privacy Act.
**🎤** "A 214-respondent stated-preference survey, bilingual, measuring the four tolerances that become our four cost
weights."
**📝** Section B/C/D map to walk/wait/transfer weights.

## Slide 3-4 — Sample size (own it) (detail)
**On-slide:** Cochran ⇒ 385 for ±5% citywide proportion; we have **214 (≈±6.7%)**. But we **calibrate parameters**, not
estimate proportions — transfer logit has **346 events / 1 predictor** (≫ 10–20/predictor). 80.8% habitual riders.
**🎤** "We're below the Cochran number for citywide proportion estimation — but that's not our purpose. We're calibrating
behavioral parameters, and on that test the sample is more than adequate."
**📝** Cochran1977, peduzzi1996. (CRITICAL_PREP #6.) Have this ready — it *will* be asked.

## Slide 3-5 — The four calibrated weights (detail)
**On-slide:** `walk` 0.0563 EIVM/m · `ride` 0.00632 EIVM/m · `wait` 14.44 EIVM/event ·
**`transfer` 15.78 EIVM/event** · `direct`/`alight` = 0 (structural connectors, avoid double-counting).
**🎤** "Four behavioral weights plus two zero-cost structural connectors. The headline: one transfer feels like ~16
minutes of riding."
**📝** spiess1989 (zero-cost connectors). Table 3.2.

## Slide 3-6 — Deriving ride_wt (detail)
**On-slide:** 9.5 km/h jeepney speed → 158.33 m/min → `ride_wt = 1 ÷ 158.33 ≈ 0.00632 EIVM/m`.
**🎤** "Riding cost: at a ~9.5–10 km/h operating speed, one metre of riding is about 0.006 EIVM."
**📝** ranosa2021. *(Internal: source says 10.228 — CRITICAL_PREP #3; quote the paper value.)*

## Slide 3-7 — Deriving wait_wt (detail)
**On-slide:** A8 mean wait **7.22 min**; C2 ⇒ waiting valued **2.0×** in-vehicle (5 min wait = 10 min ride) →
`wait_wt = 7.22 × 2.0 = 14.44 EIVM/event`.
**🎤** "Waiting: people accept 5 minutes of waiting to save 10 of riding, so a waiting minute is worth two riding
minutes; times the typical 7.2-minute wait gives 14.44."
**📝** Value-of-time literature agrees out-of-vehicle time is penalized more.

## Slide 3-8 — Deriving walk_wt & transfer_wt ★
**On-slide:**
- `walk_wt`: B3/B4 trade-off → 4.93 extra walk-min buy 20 EIVM → 4.05 EIVM/min ÷ 72 m/min ≈ **0.0563 EIVM/m**.
- `transfer_wt`: binary **logistic** on 856 choices → break-even (P=0.5, equal utility) at **S\* = −α/β = 15.78 min**.
- External anchor: García-Martínez (2018) report a pure transfer penalty of **15.2–17.7 in-vehicle min**.

**🎤** "Two derivations the panel will probe. Walking cost comes from a revealed walk-versus-wait trade-off. The transfer
penalty is the interesting one: transfer choice is yes/no, so we fit a logistic curve to 856 stated choices and find the
time-saving where a commuter is *indifferent* — 15.78 minutes. And that lands right inside the 15.2-to-17.7 range
international transfer studies report. So a locally-derived number is externally validated."

**📝** Train2002 (50% = equal utility), garciamartinez2018 (the external anchor — your strongest "not made up" card).
Figure: logistic curve. Worked example: Appendix A1.

---

### §3.2 — CityGraph & Network Construction

## Slide 3-9 — The CityGraph ★
**On-slide:** OSM → directed road graph **(36,866 nodes · 76,310 edges)** = Layer 0. Nodes `(lon,lat)`, **Haversine**
distances. Cached for repeatable runs.
**🎤** "Step two is the road network. We extract Iligan from OpenStreetMap into a directed graph — about 37,000
intersections — and that's the physical layer everything else is built on. Distances are great-circle, not flat,
because these are real geographic coordinates."
**📝** boeing2017 (OSMnx). MD5 = cache key, not security.

## Slide 3-10 — Extraction & simplification (detail)
**On-slide:** PBF via pyrosm (offline, reproducible) → NetworkX; drop self-loops, degenerate edges, duplicate pairs;
two opposing DirEdges per road; stitch adjacency by coordinate+layer.
**🎤** "We clean the raw OSM into a proper directed graph and pre-compute adjacency so pathfinding is fast."
**📝** Algorithm 1 (node/edge construction).

## Slide 3-11 — PUJ arterial filter (detail)
**On-slide:** **26,024 of 76,310 edges (34.1%)** flagged `is_drivable` = eligible for *routing*; rest kept for
*walking access*. Stops the optimizer routing down dead-ends (combinatorial blow-up).
**🎤** "We restrict routing to realistic jeepney corridors — a third of the edges — but keep the small roads for
walking. Routing and walking are different things."
**📝** guillen2013 (PUJ/tricycle hierarchy).

## Slide 3-12 — Route construction & validation (detail)
**On-slide:** Demand-weighted waypoints → A\* connect → close loop → promote to **Layer 2** (copy, not in-place) →
validate (loop continuity · layer isolation · single out-pointer). Invalid → regenerate.
**🎤** "Candidate routes are built from demand-biased waypoints, connected by shortest paths, closed into loops, and
strictly validated as clean closed loops."
**📝** mandl1980 (demand-weighted heuristic), hart1968 (A\*), farahani2013.

## Slide 3-13 — Coordinate snapping (cKDTree) (detail)
**On-slide:** Raw coords rarely hit a node → **cKDTree** nearest-neighbor = **O(log N)** vs O(N). Used for route
ingestion + passenger endpoint binding. LRU-cached OD queries.
**🎤** "Snapping millions of agent coordinates to graph nodes uses a KD-tree, so it's logarithmic, not linear — the
difference between feasible and not in a parallel simulation."
**📝** virtanen2020 (SciPy), Bentley1975 (KD-tree).

---

### §3.3 — Direct Demand Model

## Slide 3-14 — Where trips start & end (DDM) ★
**On-slide:** No official OD matrix → build one. `S_i = W_iᵅ · C_iᵝ` (α=0.6, β=0.4): demand = **traffic × structure**,
normalized to a sampling probability. Biggest upgrade over Sanchez's uniform demand.
**🎤** "Step three: demand. With no origin-destination data, we estimate it. A node is a likely trip endpoint if it's
both *busy* — from live TomTom traffic — and *structurally important* — from network centrality. We combine them and
normalize into a sampling probability. This is the single biggest upgrade over the baseline's uniform demand."
**📝** sanchez2025 (baseline), lowry2014 (OD-centrality).

## Slide 3-15 — Traffic ingestion: V_i (detail)
**On-slide:** TomTom routing API at 381 sampled centroids → congestion ratio **V_i = t_travel / t_free** (≥1; matches
the Congestion Index). Cached by coord+timestamp.
**🎤** "Traffic comes from TomTom — the ratio of real travel time to free-flow time, the standard congestion index."
**📝** munoz2021, zafar2020 (five states), vladut2025, leong2020. (V_i ≡ W_i — same number.)

## Slide 3-16 — Spatial interpolation: IDW (detail)
**On-slide:** Query 381/36,866 nodes → diffuse to the rest via **Inverse Distance Weighting (p=2)** over **Haversine**
distance. Stable, geographic.
**🎤** "We can't query every node, so we interpolate the traffic field with inverse-square distance weighting on
great-circle distances."
**📝** Snyder1987. (p=2 fixed — CRITICAL_PREP-adjacent; not tunable.)

## Slide 3-17 — OD-centrality fusion (detail)
**On-slide:** Fuse traffic `W_i` with **betweenness centrality** `C_i` (Freeman): `S_i = W_iᵅ C_iᵝ`; normalize
`P_i = S_i/ΣS`. Cobb-Douglas / weighted geometric mean — high only if *both* are high.
**🎤** "We fuse traffic with betweenness centrality as a weighted geometric mean — a node must score on both axes to
count."
**📝** freeman1977 (betweenness), lowry2014. ⚠ Anchor #2: centrality-led, traffic-modulated.

## Slide 3-18 — Alias table, config & robustness (detail)
**On-slide:** Probabilities → **Walker's alias table** = O(1) sampling. Exponents **robust**: over α∈[0.3,0.7] demand
ranking invariant (Spearman ρ≥0.997), 89–100% top-decile nodes preserved.
**🎤** "We store the demand in an alias table for constant-time sampling, and we verified the result barely changes if
you move the traffic/structure weighting around — so it's not a fragile hand-tuned number."
**📝** walker1977 (alias), `ddm_alpha_beta_sensitivity.png`. ⚠ reframe: centrality-led. (CRITICAL_PREP #4 — resolved.)

---

### §3.4 — The Three-Layer TravelGraph

## Slide 3-19 — Why three layers (the key idea) ★
**On-slide:** Split travel **state** into layers: **L1 walk-to-stop · L2 ride · L3 walk-from-stop/transfer**. A flat
graph would let a walker and a rider at the same corner share edges → free vehicle-hopping. Layers make the *graph*
enforce the rules.
**🎤** "Step four is the core modeling idea. A normal road graph can't tell a walking passenger from a riding one at the
same intersection — so it would let someone hop between jeepneys for free, with no transfer. We fix that by splitting
travel *state* into three topological layers: walking to a stop, riding, and walking after. Now the graph itself
enforces realistic behavior."
**📝** peng2023 (multilayer), `travel_graph_visualization.jpg`.

## Slide 3-20 — Layers & edge costs (detail)
**On-slide:** L1 Start-Walk & L3 End-Walk: `d·walk_wt`. L2 Ride: `d·ride_wt` (route loops only, not full road net).
**🎤** "Walking layers charge per metre at the walk rate; the ride layer charges per metre at the ride rate, and only
contains actual route loops."
**📝**

## Slide 3-21 — Inter-layer transitions (detail)
**On-slide:** **Wait** (L1→L2) = `wait_wt`; **Transfer** (L3→L2) = `transfer_wt`; **Alight** (L2→L3) = 0;
**Direct** (L1→L3) = 0. Costs are *events*, not roads.
**🎤** "Four transitions move you between states: waiting to board and transferring carry their penalties; alighting and
the pure-walk option are free structural connectors."
**📝** Wait ≠ Transfer is deliberate (first boarding vs. trip interruption) — jara-diaz, garciamartinez.

## Slide 3-22 — Route isolation (detail)
**On-slide:** Layer 2 has **separate nodes per route** → no connection at shared corners → changing vehicles *forces* an
Alight → Transfer. Kills the "teleportation anomaly."
**🎤** "Each route lives on its own ride layer, so overlapping corridors stay operationally distinct — you can't switch
jeepneys for free."
**📝** This is what makes transfer penalties *actually apply*.

## Slide 3-23 — A\* admissibility (detail)
**On-slide:** `h(n) = D_straight · min(walk_wt, ride_wt) ≤ h*(n)` (drop ≥0 event penalties + triangle inequality) ⇒
admissible ⇒ A\* returns the true min-EIVM journey.
**🎤** "Pathfinding is A\* with a straight-line heuristic we *prove* never overestimates, so the journey it returns is
guaranteed optimal in our cost units."
**📝** Full proof on Appendix A2. hart1968, russell2010.

---

### §3.5 — Agent-Based Simulation

## Slide 3-24 — The simulation = the evaluator ★
**On-slide:** Passengers + jeepneys as agents over a 90-min service window (Δt=10 s). Capacity binds (16 pax). Per
tick: spawn → move jeeps → update passengers → board/alight → record. Output = **F_sim**.
**🎤** "Step five turns a network into a score. We release passengers and jeepneys as agents and run 90 simulated
minutes, tick by tick. Vehicles move before boarding is resolved, capacity is hard — a full jeepney leaves you
waiting — and at the end we read out the fitness."
**📝** `simulation_temporal_snapshots.png`, `fig_simulation_loop.png`.

## Slide 3-25 — Passenger generation (detail)
**On-slide:** Continuous **Poisson** arrivals; per-node rate `λ_i` coupled to the DDM (traffic + centrality);
scheduled in 100-tick windows with Gaussian perturbation; sampled via alias table.
**🎤** "Passengers arrive as a continuous Poisson stream, with each node's arrival rate driven by the demand model."
**📝** Links micro-arrivals to macro demand — behavioral realism.

## Slide 3-26 — Passenger state machine (detail)
**On-slide:** **walk → wait → ride → done.** Walk `d=v·Δt` along edges; hit a Wait edge → wait; jeepney arrives → ride;
reach alight node → walk; finish → done (absorbing).
**🎤** "Each passenger is a four-state machine — walking, waiting, riding, done — driven by the least-cost journey from
the graph."
**📝** `passenger_graph.jpg`.

## Slide 3-27 — Jeeps & opportunistic boarding (detail)
**On-slide:** Jeeps loop routes (`d=v·Δt`, capacity 16). **Opportunistic boarding:** take an earlier non-planned jeepney
iff `c_alt ≤ c_plan + δ_tol` (δ=14.44 EIVM) *and* it reaches your stop. Models rational riders.
**🎤** "Jeepneys loop their routes, and passengers can rationally board a good-enough earlier vehicle instead of rigidly
waiting — within a tolerance."
**📝** iseki2009. δ=14.44 ≈ one wait-event (CRITICAL_PREP #5). Result on Slide 4-10.

## Slide 3-28 — Fitness: Total User Cost (F_sim) ★
**On-slide:** `F_sim = Σ T_i (completed) + Σ(T_elapsed + β·T_remaining) (incomplete) + α·σ(T_i)`.
Term 1 = realized travel **time** · Term 2 = **underservice penalty** (β=2) · Term 3 = **equity** (α=0.5).
**🎤** "The fitness is Total User Cost, in three parts. First, the realized travel time of everyone who completed their
trip. Second, a penalty for anyone still stranded at the cutoff — with the multiplier above one, an unfinished trip is
strictly worse than a finished one, so the optimizer can't cheat by abandoning hard passengers. Third, an equity term
that penalizes unequal service. One crucial clarification: this is realized *time*, in seconds — the EIVM weights chose
each passenger's *path*; the fitness measures the actual *outcome*."
**📝** ⚠ Anchor #1 — say the EIVM-vs-seconds line out loud. kepaptsoglou2009, fan2006, coello2002 (penalty), welch2013
(equity). α/β here ≠ DDM/logistic α/β. Neither α nor β is data-calibrated (penalty/trade-off weights): β only needs
β>1; α=0.5 is a *light* regularizer (~0.06% of fitness — see A4). Don't claim the equity term drives the results.

## Slide 3-29 — Mohring fleet allocation (detail)
**On-slide:** Equidistant spawn (anti-bunching, `S=L/N`); **√-rule** `f_r = F_tot·√D_r / Σ√D_k` — demand-responsive but
subsidizes long/low-demand routes (economies of scale).
**🎤** "We size each route's fleet with Mohring's square-root rule — responsive to demand, but the square root keeps
low-demand routes alive so the network stays connected."
**📝** mohring1972 (economies of scale; √ = standard operationalization — CRITICAL_PREP cheat). guillermo2022.

## Slide 3-30 — Event architecture (detail)
**On-slide:** Deterministic per-tick order (jeeps move *before* boarding); event-driven (jeeps emit, controller
resolves); clean setup per evaluation (no state leak).
**🎤** "The tick order is deliberate — vehicles advance before passengers interact — which keeps the simulation
deterministic and modular."
**📝** Determinism matters for the GA's reproducibility.

---

### §3.6 — The Hybrid GA–ACO Memetic Algorithm

## Slide 3-31 — Stigmergy & the demand-service gap ★
**On-slide:** Pheromone = **stigmergic demand memory** per corridor; deposit `Δτ=Q/C` (cheaper journeys = stronger),
evaporate (ρ). **Gap** = normalize demand & supply to shares: `Δ_ij = P_ij − S_ij`; `D(R)=Σ|P_ij−S_ij|`. `Δ>0`
underserved, `Δ<0` oversupplied.
**🎤** "Now the optimizer's intelligence. After each simulation, every road a passenger used gets a demand deposit —
cheaper journeys leave stronger trails, exactly like ant pheromone — and old trails evaporate. Then we compare each
corridor's *share* of demand to its *share* of the fleet. A positive gap means underserved; negative means we're wasting
vehicles. That gap, summed, is our cheap measure of how well service matches demand."
**📝** dorigo1996 (stigmergy/Δτ=Q/C), welch1313→welch2013 (equity-as-distribution). Normalizing to shares kills the
τ-vs-vehicle-count dimensional mismatch. Validity check: Slide 4-12 (r=−0.41).

## Slide 3-32 — Pheromone collection & update (detail)
**On-slide:** Post-simulation, coordinate-keyed deposit so the *same physical road* pools demand across chromosomes &
generations; evaporate-then-deposit preserves ACO's invariants.
**🎤** "The pheromone is keyed by physical coordinate, so demand evidence accumulates on real corridors across the whole
search, not just one candidate."
**📝** dorigo1996, dorigo2004.

## Slide 3-33 — Lamarckian local search ★
**On-slide:** Three gap-guided operators: **Attraction** (Or-opt → pull toward underserved) · **Repulsion** (2-opt →
away from oversupplied) · **Tortuosity pruning** (straighten detours; never prune an underserved edge). **Gap-gated:**
keep a move only if it lowers `D(R)` — no re-simulation per tweak.
**🎤** "The local search has three moves, all steered by the gap. Attraction transplants route segments toward
underserved demand; repulsion pushes routes off oversupplied corridors; pruning straightens wasteful detours but is
forbidden from cutting an underserved corridor. And we accept a move only if it improves the *cheap* gap signal — we
don't re-run the expensive simulation for every little tweak. That's what makes the memetic search tractable."
**📝** ⚠ Tie to Appendix A3 (this is the operator that was inert in the first Iligan run). laporte2002 (Or-opt),
ciaffi2012 (2-opt), ceder1986/baaj1991 (circuity), nurcahyadi2022 (negative learning → repulsion).

## Slide 3-34 — The three operators, visually (detail)
**On-slide:** *(Figure `lamarckian_operators_toy.png`)* before→after on a toy grid: removed edges red, added green.
**🎤** "Here's each operator isolated on a grid so the structural effect is unambiguous."
**📝** Demonstrated & finished — lean on it (the *mechanisms* are proven even where the full run is pending).

## Slide 3-35 — Why gate on the gap, not the simulation (detail)
**On-slide:** Full sim per micro-move = bottleneck. The gap is O(1)-cached, internally consistent, and the *same* signal
that **directs** the move also **accepts** it. Surrogate-assisted memetic practice.
**🎤** "Re-simulating every tweak would be hopeless, so we accept moves on the cheap gap — the same signal that aims
them."
**📝** jin2005 (surrogate-assisted), neri2012 (meta-Lamarckian), liang2021.

## Slide 3-36 — Topological Hub Crossover ★
**On-slide:** Keep the fitter parent's high-demand **trunk** (top-decile pheromone corridors); graft the other parent's
non-conflicting **feeders**. Economies of density: trunk corridors are cheaper per passenger.
**🎤** "Crossover is where the novelty concentrates. Random splicing destroys good corridors, so instead we find the
busiest trunk of the *fitter* parent and keep it, then add complementary feeder routes from the other parent. That's the
feeder-trunk hierarchy transit economists recommend — trunk corridors get cheaper per passenger as volume grows."
**📝** gschwender2016 (economies of density), risso2023 (backbone GA). `memetic_hub_crossover.png`.

## Slide 3-37 — Crossover keeps validity (detail)
**On-slide:** Recombination respects closed-loop validity + route isolation → every child is a structurally valid route
system, not a fragmented edge set.
**🎤** "The recombination is constrained, so every child is a coherent, valid network."
**📝**

## Slide 3-38 — Epigenetic Inheritance ★
**On-slide:** Child inherits a **fitness-weighted blend** of both parents' pheromone maps:
`τ_child = w_A τ_A + w_B τ_B`, `w_A = C_B/(C_A+C_B)` (fitter parent weighted more) → offspring **warm-start** on inherited
demand memory.
**🎤** "And the child doesn't just inherit geometry — it inherits a *blended demand memory* from both parents, weighted
toward the fitter one. So its local search starts informed about where demand is, instead of relearning the city from a
blank slate. We call that epigenetic inheritance, and it's a big part of why the search is efficient."
**📝** Weights inverted because lower cost = fitter. `memetic_pheromone_blend.png`. Legitimacy on next slide.

## Slide 3-39 — Why this is still valid ACO (detail)
**On-slide:** PACO: *pheromone ≙ population members* (Guntsch); weighted multi-matrix combination = Pareto-ACO
(García-Martínez); cross-solution transfer accelerates convergence (Middendorf); population+belief space = Cultural
Algorithm (Reynolds).
**🎤** "Blending pheromone matrices isn't a hack — it's exactly population-based and multi-objective ACO, and the
population-plus-belief-space idea is a known Cultural Algorithm."
**📝** guntsch2002, garcia2004, middendorf2002, reynolds1994 — all verbatim-excerpted (STUDY_GUIDE §13b).

---

### §3.7 — Orchestration & Adaptive Control

## Slide 3-40 — The generational pipeline (detail)
**On-slide:** Per gen: (1) evaluate parents by simulation (→ fitness + pheromone) · (2) elitism (N=1) + tournament
(k=3) · (3) hub crossover + epigenetic inheritance (warm-start, no pre-sim) · (4) gap-gated local search · (5) **one**
final simulation of the child. Goal: **simulate each child exactly once.**
**🎤** "Each generation evaluates parents, selects, recombines with inherited memory, runs the cheap local search, and
then simulates the finished child exactly once — the whole design minimizes calls to the expensive simulation."
**📝** `fig_optimization_pipeline.png`. sastry2013.

## Slide 3-41 — Adaptive control ★
**On-slide:** Mutation rate scales **quadratically** with stagnation (0.25 → 0.8 cap, resets on improvement) — patience
early, force when stuck. Local-search probability & intensity decay **linearly** (broad → surgical).
**🎤** "Two adaptive pieces. When the search stalls, the mutation rate ramps up quadratically to escape local optima,
then snaps back the moment it finds something better — patience early, force late. And the local search starts with
broad edits and tightens to surgical ones as it converges."
**📝** eiben1999 (static params inappropriate — verbatim §13b), abulail2025/farda2024 (quadratic). *(We corrected the
paper: single adaptive rate + fixed operators — CODE_FIXES_TODO #4.)*

## Slide 3-42 — Convergence criteria (detail)
**On-slide:** Stop only when **both** saturate: structural (**Jaccard** of elites high) *and* objective (**fitness
variance** low). Both needed: transit landscapes have "neutral networks" (different structure, same travel time).
**🎤** "We stop only when the population has converged on *both* structure and fitness — that avoids premature stopping
and avoids spinning on a flat landscape."
**📝** ⚠ exact Jaccard threshold / variance ε pending from corrected runs. sastry2013.

## Slide 3-43 — Parallel execution (detail)
**On-slide:** Process-pool workers (bypass GIL); each caches CityGraph + DDM once; routes ship as lightweight
`path_keys`; TravelGraphs cached per route-set. → Objective 4.
**🎤** "Evaluating thousands of networks is parallelized across CPU cores, with the heavy objects cached per worker — that
closes our parallelization objective."
**📝**

## Slide 3-44 — Telemetry & deterministic replay (detail)
**On-slide:** Logs history + lineage + JSON snapshots; atomic checkpoints (incl. RNG state) → exact resumable, replayable
runs. *(We independently verified run-to-run determinism: same seed → identical fitness.)*
**🎤** "Everything is logged and checkpointed, including the random state, so runs are exactly reproducible — which we
verified."
**📝** Determinism harness result: old vs new code differ <0.06% (float noise).

---

### §3.8 — Post-Optimization Metrics

## Slide 3-45 — Structural similarity metrics (detail)
**On-slide:** **Jaccard** (shared-edge overlap), **Discrete Fréchet** (order-aware geometry), **GED** (topological edit
cost) — three orthogonal "are two networks the same?" lenses.
**🎤** "We compare networks three ways — shared edges, route shape, and connectivity — because two networks can match on
one and differ on another."
**📝** eiter1994 (Fréchet), sanfeliu1983 (GED — verbatim §13b).

## Slide 3-46 — Demand-aware & diversity metrics (detail)
**On-slide:** **Wasserstein / Earth-Mover** = demand-aware coverage distance; **Shannon entropy** `H=−Σp log p` =
path diversity / resilience.
**🎤** "And two more: Wasserstein asks whether coverage matches demand, and entropy measures how spread-out (resilient)
the routing is."
**📝** debacco2023 (⚠ verify cite — file is Kolouri/Villani notes), levinson2012 (entropy resilience). Bridge to results.
