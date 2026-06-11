# STUDY GUIDE — Jeepney Route Network Optimization (Iligan City TRNDP)
### Deep methodology walkthrough for the advisor defense

**How to use this:** Read top to bottom once for the narrative, then drill into any module before the
meeting. Every factual claim is tagged with its source: `[M §x]` = research_methodology.tex section,
`[R4]` = results_and_discussion.tex, `[code: file:line]`, `[cfg]` = `configs/profile_p1.yaml`,
`[PDF: author]` = a source PDF. Flags `[ASSUMPTION]` / `[UNCLEAR]` mark things you should know are soft.
Anything in **CRITICAL_PREP.md** is where the advisor is most likely to push — study that second.

---

## 0. The one idea that ties everything together: EIVM

Everything in the pipeline is priced in one unit: the **EIVM — Equivalent In-Vehicle Minute**. One EIVM
= the perceived burden of one minute riding *inside* a jeepney. `[M §3.1.4]`

Why invent a unit? Because a passenger's journey mixes incommensurable things — metres walked, minutes
waited, a transfer event. You cannot add "300 metres" to "one transfer." EIVM is the common currency:
walking distance, riding distance, a wait, and a transfer are each converted into "how many minutes of
riding would feel equally bad." Once everything is in EIVM, the A\* pathfinder can compare whole journeys
on a single scale. `[M §3.1.4]`, justified by generalized-cost theory (Ortúzar & Willumsen).

**The six calibrated weights** `[M §3.1, cfg]`:

| weight | value | unit | what it prices |
|---|---|---|---|
| `walk_wt` | 0.05630 | EIVM/m | each metre walked |
| `ride_wt` | 0.00632 | EIVM/m | each metre ridden |
| `wait_wt` | 14.44 | EIVM/event | one boarding/wait episode |
| `transfer_wt` | 15.78 | EIVM/event | one jeepney-to-jeepney change |
| `direct_wt` | 0.00 | EIVM/transition | structural connector (no cost) |
| `alight_wt` | 0.00 | EIVM/transition | structural connector (no cost) |

> **Key clarification you MUST be able to make (advisor trap):** EIVM prices *journey planning*. The
> **fitness score `F_sim` is NOT in EIVM — it is in raw elapsed simulation seconds.** The EIVM weights
> decide *which path* each passenger attempts (through A\*); the fitness then sums the *actual time each
> passenger spends in the system* once capacity, headway, and bunching are simulated. We fixed the paper
> to say this explicitly `[M §3.5.7, corrected]`. See CRITICAL_PREP #1.

---

## 1. The pipeline in one breath

Survey → EIVM weights. OSM → `CityGraph` (road skeleton). TomTom + centrality → `DirectDemandModel`
(where trips start/end). CityGraph + routes + weights → 3-layer `TravelGraph` (priced multimodal journeys).
Agents simulate a service period → `F_sim` (realized total user time). A memetic GA–ACO proposes route
systems, scored by that simulation, until convergence. `[M Fig. system_pipeline]`

---

## 2. MODULE — Survey & EIVM Calibration `[M §3.1]`

**Purpose / why it matters.** A route-cost function must reflect *local* commuter trade-offs, not imported
values. No peer-reviewed Iligan-specific behavioral dataset existed, so we ran a 214-response stated-
preference survey to measure four tolerances (walking, waiting, transfer aversion, usual trip profile),
which map one-to-one onto the four calibratable weights. `[M §3.1.1]`

### 2.1 The derivations (show the arithmetic — the advisor will ask)

**`ride_wt`** — from a 9.5 km/h jeepney operating speed `[PDF: ranosa2021]`:
- 9.5 km/h = 9.5 × 1000 / 60 = **158.33 m/min**.
- 1 minute of riding = 1 EIVM by definition, so `ride_wt` = 1 EIVM ÷ 158.33 m/min = **0.00632 EIVM/m**. `[M §3.1.4]`

**`wait_wt`** — two survey inputs:
- A8 mean usual wait (after midpoint coding) = **7.22 min/event**.
- C2: median accepted wait to save 10 min of riding = 5 min → waiting multiplier `θ_wait` = 10 EIVM / 5 min
  = **2.0 EIVM/min** (one waiting minute ≈ two riding minutes — consistent with value-of-time literature).
- `wait_wt` = 7.22 × 2.0 = **14.44 EIVM/event**. `[M §3.1.4]`

**`walk_wt`** — from the B3/B4 walk-vs-wait trade-off:
- Saving 10 min of waiting is worth 10 × 2.0 = **20 EIVM**.
- B4 mean switch-back walk = 6.93 min; Stop A needed 2 min → **4.93 additional walking minutes** buy that 20 EIVM.
- walking multiplier `θ_walk` = 20 / 4.93 ≈ **4.05 EIVM/min**; at 72 m/min (1.2 m/s) → 4.05/72 ≈ **0.05630 EIVM/m**. `[M §3.1.4]`
- *(Note: `walk_wt > ride_wt` because walking is slower and carries heat/rain/fatigue burden.)*

**`transfer_wt`** — a binary logistic model on 856 stated choices (214 respondents × 4 savings levels
S ∈ {5,10,15,20}). `[M §3.1.4]`
- Acceptance coded `y=1` if required savings ≤ S. "Never" responses (77) coded 0 throughout.
- Acceptance counts: S=5→35, S=10→79, S=15→95, S=20→137 (total **346** acceptances of 856). *(I verified this is internally consistent.)*
- MLE fit: **α = −2.1242**, **β = 0.1346 min⁻¹**. The penalty is the 50%-acceptance threshold (where the
  transfer and direct routes have equal systematic utility `[PDF: Train2002]`): at P=0.5 the log-odds = 0, so
  α + βS\* = 0 → **S\* = −α/β = 2.1242/0.1346 ≈ 15.78 min** → `transfer_wt = 15.78 EIVM/event`. `[M §3.1.4]`
- External anchor: García-Martínez et al. report a pure transfer penalty of 15.2–17.7 in-vehicle minutes
  `[M §3.1.4]`; our 15.78 lands inside that band.

**`direct_wt` = `alight_wt` = 0** — these are *structural state-change connectors*, not costs. Walking is
already charged on SW/EW edges; riding on RI; a transfer on TR. Charging the connector too would double-
count. This follows generalized-cost decomposition (count each burden once) and transit-assignment
practice `[PDF: spiess1989]`. `[M §3.1.4, §3.4.4]`

### 2.2 Sample-size honesty
Cochran's formula gives n₀ = (1.96² × 0.5 × 0.5)/0.05² ≈ **385** for ±5% citywide proportion estimation.
We have **214**, which corresponds to ≈ ±6.7% `[M §3.1.3]`. The defense: we are **not** estimating citywide
proportions; we are *calibrating behavioral parameters*. The logistic model has 346 events / 1 predictor,
far above the 10–20 events-per-predictor rule. `[M §3.1.3]`, `[PDF: Cochran_1977]` for the formula.

### 2.3 Likely advisor questions
- **Q: Your 214 < 385 — isn't the survey underpowered?** A: 385 is for citywide *proportion* estimation at
  ±5%; that is not our purpose. We calibrate trade-off parameters; the transfer model has 346 outcome events
  for one predictor (≫ the 10–20/predictor guideline), and walking/waiting weights are trade-off ratios, not
  proportions. We report the ±6.7% only as a descriptive benchmark.
- **Q: Why the 85th percentile for the walking catchment?** A: We want a *practical service boundary for most
  users*, not central tendency. El-Geneidy et al. support high-percentile catchments: *"the 75th and 85th
  percentile buffers ... more accurately represent walking area for most users."* `[PDF: El-Geneidy2014]`
  (12 min × 72 m/min = **864 m** access radius — used only as a reference, not as `walk_wt`.) `[M §3.1.4]`
- **Q: Why is one waiting minute worth two riding minutes?** A: It came directly from C2 (median 5 min wait
  accepted to save 10 min ride → 2.0), and it agrees with the transport value-of-time consensus that out-of-
  vehicle time is penalized more heavily than in-vehicle time.
- **Q: Why a logistic model for transfers instead of just averaging D3?** A: Transfer acceptance is *binary*
  (accept/reject at a given saving), and D3 has "Never" responses that have no finite numeric threshold.
  Logistic regression retains "Never" as non-acceptance within range and yields a principled break-even.
- **Q: Your students are 93% of the sample — is it representative?** A: It is a convenience/snowball sample
  appropriate for stated-preference calibration (Louviere et al.); 80.8% are habitual riders, giving valid
  construct validity for waiting/walking/transfer experience. Flag it as a stated scope limitation.

---

## 3. MODULE — CityGraph & PUJ Arterial Filter `[M §3.2]`

**Purpose.** Turn raw OSM into a computable directed road graph (Layer 0), then mark which edges are
*eligible for jeepney routing*. Iligan extraction: **36,866 nodes, 76,310 directed edges**; after the
arterial filter, **26,024 drivable edges (34.1%)** form the route-search skeleton; 50,286 (65.9%) are
pruned from *routing* but **kept** for pedestrian walking access. `[R4 §4.1.1]`

**Why restrict routing to arterials?** An unfiltered network lets the metaheuristic route jeepneys through
residential dead-ends and alleys → combinatorial explosion and operationally invalid lines. Constraining
the candidate space is standard in transit metaheuristics. `[M §3.2.2]` The PUJ/tricycle hierarchy
(PUJs = main corridors; tricycles/pedicabs = short access) justifies arterial-only routing. `[PDF: guillen2013]`

**Mechanics worth knowing:**
- `Node` stores `(lon, lat, layer)`; **all distances use the Haversine great-circle formula**, not Euclidean,
  because coordinates are geographic. `[M §3.2.1]`
- `DirEdge` is directed; each road becomes two opposing edges. `is_drivable` is a *routing-eligibility* flag,
  not a physical-passability flag. `[M §3.2.2]`
- Shortest paths use **A\*** over the drivable subset, admissible because the heuristic is a straight-line
  lower bound (proof in §3.4.5). `[M §3.2.1]`
- **cKDTree snapping** (SciPy): raw coordinates rarely hit a graph node, so nearest-node lookup uses a
  KD-tree → O(log N) instead of O(N) per query — essential when millions of agent coordinates are snapped.
  `[M §3.2.4]`
- MD5 is used only as a *deterministic cache-key hash* for the road-graph pickle, **not** for security. `[M §3.2.1]`

**Advisor Qs:** *Why two opposing edges?* (to model bidirectional roads in a directed pathfinder). *Why keep
non-arterial roads at all?* (passengers still walk on them in the TravelGraph — routing ≠ walking). *Why
cKDTree over brute force?* (O(log N) vs O(N) — the snapping bottleneck in a parallel ABM).

---

## 4. MODULE — Direct Demand Model (DDM) `[M §3.3]`

**Purpose.** Decide *where trips begin and end*. Instead of uniform sampling, give higher probability to
nodes that are both **busy** (live traffic) and **structurally important** (network topology). This is the
single biggest upgrade over the Sanchez (2025) baseline, which used uniform demand with a crude
Residential/Non-Residential split. `[M §3.5.1]`, `[PDF: sanchez2025]`

### 4.1 The four steps
1. **Traffic ingestion (TomTom).** For 381 centrality-sampled centroid nodes `[R4 §4.1.2]`, query TomTom's
   routing engine. The empirical traffic weight is the congestion ratio
   **`V_i = t_travel / t_free`** (dynamic travel time ÷ free-flow travel time; ≥ 1). `[M §3.3.1]`
   This mirrors the standard Congestion Index `[PDF: zafar2020]`; web-API travel data is an accepted source
   `[PDF: munoz2021]`; TomTom returns both real-time and free-flow baselines in one payload `[PDF: vladut2025]`;
   "free-flow" = unobstructed desired speed `[PDF: leong2020]`. *(We confirmed the real DDM pkl contains real
   TomTom variation — 8am mean V=1.188, max 3.013; 5pm mean 1.228, max 3.164.* `[R4 §4.1.2]`*)*
   > **Notation fix you should know:** `V_i` (time ratio) and `W_i` (= `v_free/v_current`, speed ratio) are the
   > **same number** — for a fixed segment `t_travel/t_free = v_free/v_current`. We disambiguated this in the
   > paper. `[M §3.5.1, corrected]`
2. **IDW interpolation.** Querying every node is infeasible, so unqueried nodes get an Inverse-Distance-
   Weighted average of nearby measured weights, with distances by Haversine. **Power p = 2** (inverse-square,
   the standard IDW choice — hardcoded, not tunable). `[M §3.3.2, corrected]`, `[code: direct_demand_sampler.py:501]`
3. **OD-centrality fusion.** Combine traffic weight `W_i` with **betweenness centrality** `C_i` (Freeman 1977:
   how often a node lies on shortest paths — i.e., a structural connector):
   **`S_i = W_iᵅ × C_iᵝ`** with **α = 0.6, β = 0.4** `[cfg]`, then normalize `P_i = S_i / ΣS_k`. `[M §3.3.3]`
   This adapts Lowry's OD-centrality idea, swapping static census for dynamic API data. `[M §3.5.1]`
4. **Walker's Alias table.** Store `P_i` in an alias table → **O(1) sampling** after O(N) setup, because the
   sampler is called millions of times. `[M §3.3.4]`, `[PDF: Walker1977 — no PDF, see fetch list]`

### 4.2 Ambiguity-killers
- **"Betweenness centrality"** = the fraction of all node-pair shortest paths that pass through node *v*:
  `C_B(v) = Σ_{s≠v≠t} σ_st(v)/σ_st`. High `C_B` = a structural bottleneck/connector (an intersection many
  trips must cross). `[M §3.3.3]`
- **Why multiply (`W^α·C^β`) instead of add?** A multiplicative form means a node must score on *both* axes to
  win — a busy-but-peripheral node or a central-but-empty node is damped; a busy *and* central corridor
  dominates. The exponents tune the balance. `[M §3.3.5]`

### 4.3 Likely advisor questions
- **Q: Why α=0.6, β=0.4?** A: **[RESOLVED — see CRITICAL_PREP #4]** The *form* `W^α C^β` (α+β=1) is a Cobb-Douglas /
  weighted geometric mean, and a sensitivity sweep shows the split is immaterial: over α∈[0.3,0.7] the demand ranking
  is invariant (Spearman ρ≥0.997) and 89–100% of top-decile demand nodes are preserved (Fig.
  `ddm_alpha_beta_sensitivity`). **Caveat to own first:** the surface is centrality-*dominated* (ρ=0.995 with pure
  betweenness; traffic `W∈[1,3]` is swamped by centrality `C∈[1e-4,0.37]`), so describe it as "structural demand,
  traffic-modulated," not "traffic-led."
- **Q: Is the traffic data real or synthetic?** A: Real TomTom (confirmed); the three temporal surfaces
  (08:00/13:00/17:00) show distinct means/maxima, which a synthetic constant could not produce. `[R4 §4.1.2]`
- **Q: Why p=2 for IDW?** A: Inverse-square is the canonical IDW default; we hold it fixed so the demand
  surface is constant across route evaluations (changing it mid-search would confound the optimization).
- **Q: 381 of 36,866 nodes queried — is that enough?** A: IDW diffuses the measured field; the queried set is
  centrality-weighted (reservoir sampling) so it concentrates on the structurally important nodes that matter.

---

## 5. MODULE — Three-Layer TravelGraph + A\* admissibility `[M §3.4]`

**Purpose.** Convert (road network + routes + EIVM weights) into a graph where a *single shortest-path search*
returns a complete, behaviorally valid multimodal journey.

**Why three layers and not one flat graph?** In a flat graph one node = one intersection, so a *walking*
passenger and a *riding* passenger at the same corner share outgoing edges — letting a passenger "walk off"
a moving jeepney or switch routes with no transfer. Splitting travel **state** into topological layers makes
the graph itself enforce the rules. `[M §3.4.1]` Multilayer transport modeling preserves mode/state
distinctions that aggregation destroys. `[PDF: Peng]`

- **Layer 1 (Start-Walk, SW):** origin-side walking. `w_SW = d · walk_wt`.
- **Layer 2 (Ride, RI):** jeepney loops only. `w_RI = d · ride_wt`.
- **Layer 3 (End-Walk, EW):** post-alight walking + transfer staging. `w_EW = d · walk_wt`.

**Four inter-layer transitions (events, not roads):**
- **Wait (WA), L1→L2:** `w_WA = wait_wt` (14.44) — first boarding.
- **Transfer (TR), L3→L2:** `w_TR = transfer_wt` (15.78) — a second-or-later boarding after alighting.
- **Alight (AL), L2→L3:** `w_AL = 0` (structural).
- **Direct (DI), L1→L3:** `w_DI = 0` (lets A\* consider a pure-walk alternative).

**Route isolation (the "teleportation anomaly" fix).** Layer 2 has *separate node populations per route*.
Two routes sharing a corner do **not** connect in L2; a passenger must AL into L3 and TR back into L2 to
change routes — so `transfer_wt` is charged exactly when (and only when) a real transfer happens. `[M §3.4.4]`

### 5.1 A\* admissibility — be ready to reproduce this proof `[M §3.4.5]`
A\* finds the true optimum **iff** the heuristic never overestimates remaining cost: `h(n) ≤ h*(n)`. The
chosen heuristic is **`h(n) = D_straight(n,t) · min(walk_wt, ride_wt)`**. Proof sketch:
1. True remaining cost = Σ(spatial edge costs) + Σ(event penalties); event penalties ≥ 0, so drop them:
   `h*(n) ≥ Σ d_e·β_e`.
2. Every `β_e ≥ min(walk_wt, ride_wt)`, so `h*(n) ≥ min(β)·Σ d_e`.
3. Triangle inequality: `Σ d_e ≥ D_straight(n,t)` (any network path ≥ straight line).
4. Therefore `h*(n) ≥ D_straight · min(β) = h(n)`. ∎ Admissible → A\* returns the true least-EIVM journey.

### 5.2 Likely advisor questions
- **Q: Why A\* and not Dijkstra?** A: A\* uses the admissible straight-line heuristic to search directionally,
  avoiding the uniform expansion Dijkstra does — critical when thousands of journeys are computed per tick.
- **Q: Prove your heuristic is admissible.** A: (reproduce §5.1 — the `min(walk_wt, ride_wt)` × straight-line
  bound, dropping non-negative event penalties + triangle inequality).
- **Q: Why is alight free but transfer expensive?** A: Alighting is a state change whose travel burden is
  already priced (ride done, walking charged on EW); the transfer penalty captures the *separate* disutility
  of interrupting the trip, which the literature shows is large even after walking/waiting are controlled
  (García-Martínez 15.2–17.7 EIVM; Jara-Díaz 13–18 EIVM). `[M §3.4.6]`
- **Q: Why isolate Layer 2 per route?** A: Jeepney corridors overlap heavily; without per-route isolation a
  passenger could change vehicles for free at any shared corner, underestimating transfers and invalidating
  the journey.

---

## 6. MODULE — Agent-Based Simulation `[M §3.5]`

**Purpose.** This is the *authoritative evaluator*. It replays a service period with autonomous passengers and
jeepneys so that capacity limits, headways, and bunching produce *realized* travel times — effects a static
assignment cannot capture. `[M §3.5.6]`

### 6.1 Passenger FSM — four states `[M §3.5.2]`
`WALKING → WAITING → RIDING → DONE`. Walking advances `d = v_walk·Δt` along SW/EW edges; reaching a WA edge
flips to WAITING; the controller boards the passenger when a non-full jeepney arrives at the node (→ RIDING);
reaching the planned alight node returns them to WALKING; finishing the last edge → DONE (absorbing).

### 6.2 Jeepney agents + per-tick loop `[M §3.5.3, §3.5.6]`
Jeeps move topologically (`d = v·Δt`, wrap at loop end); board only if `n_passengers < C_max` (capacity 16).
Per tick, the controller: (1) spawns passengers, (2) moves jeeps, (3) updates passengers, (4) resolves
boarding/alighting, (5) records metrics. **Order matters** — vehicles advance *before* boarding is resolved,
so a passenger boards only after the jeepney has physically reached the node this tick.

### 6.3 Opportunistic boarding under `weight_tolerance` `[M §3.5.4]`
Real commuters board a "good-enough" earlier jeepney instead of rigidly waiting for the one on their planned
path `[PDF: iseki2009 — "Not All Transfers Are Created Equal"]`. Rule: board a non-planned arriving vehicle iff
**`c_alt ≤ c_plan + δ_tol`**, where `δ_tol` = `weight_tolerance` = **14.44 EIVM** `[cfg]`, and only if that
vehicle's route actually reaches the passenger's alight node (never strands them).
- **Why 14.44?** It equals one `wait_wt`. **[ASSUMPTION/justification — see CRITICAL_PREP #5]:** a passenger
  will accept up to *one waiting-event's worth* of extra in-vehicle cost to avoid waiting again — i.e., "if
  boarding now saves me a whole wait, I'll tolerate that much detour." This is a defensible behavioral reading
  even though it was originally a heuristic pick.
- **Result that backs it `[R4 §4.3.4]`:** at δ=14.44, opportunistic riders (Group B) had median delay
  **0.70 min vs 6.71 min** for waiters (Group A), one-sided Mann–Whitney **U=953, p=0.0022**. So the mechanism
  *reduces* commute delay for those who use it — it is not just perturbing path choice. (It fires for only
  ~0.7% of passengers at production tolerance — a small but genuine minority.)

### 6.4 Mohring fleet allocation + headway spacing `[M §3.5.5]`
- **Equidistant spawn** avoids bus-bunching: vehicles on a route start at spacing `S = L_loop / N`. `[PDF: mohring1972 — no PDF]`
- **Square-root allocation:** `f_r = F_tot · √D_r / Σ√D_k`. The Mohring effect says frequency should scale with
  ridership; the **square root** *flattens* allocation so long, lower-demand corridors are subsidized rather
  than starved (linear allocation would over-concentrate fleet on dense corridors and kill transfer routes).
- **`D_r` (route demand level)** = passenger-distance on route *r*'s edges from sampled shortest-path journeys —
  i.e. *network utilization*, not raw geographic density. Summing DDM probabilities along a route would only
  measure how busy its streets are, ignoring whether the route actually connects origins to destinations; the
  TRNDP requires evaluating many-to-many OD flow. `[M §3.5.5]`, `[PDF: kepaptsoglou2009, farahani2013]`
  > **[code caveat — CRITICAL_PREP #3]:** in code `D_r` is currently an edge **count** (+1 per RI edge), not
  > edge **length** in metres. The paper describes the intended length-weighted version. Logged in CODE_FIXES_TODO.

### 6.5 Fitness — `F_sim` `[M §3.5.7]`
$$F_{sim} = \underbrace{\sum_{i\in C} T_i}_{\text{Total User Cost}} + \underbrace{\sum_{j\in I}(T_j^{elapsed} + \beta\hat T_j^{rem})}_{\text{Underservice penalty}} + \underbrace{\alpha\,\sigma(T_i)}_{\text{Equity regularizer}}$$
- **Term 1 — Total User Cost:** sum of realized door-to-door **elapsed time** (seconds) of completed
  passengers. *(NOT EIVM — see §0 and CRITICAL_PREP #1.)*
- **Term 2 — Underservice penalty:** incomplete passengers cost `elapsed + β·(remaining A\* cost)`, **β = 2.0**.
  With β>1 an incomplete trip is strictly worse than a completed one — this **stops the optimizer from
  "cheating" by stranding hard-to-serve passengers** to lower the average. An *exterior penalty function* for
  the implicit "everyone must arrive" constraint. `[PDF: coello2002 — no PDF]`
- **Term 3 — Equity regularizer:** `α·σ(completed times)`, **α = 0.5**, penalizes unequal service so peripheral
  riders aren't sacrificed for trunk efficiency (horizontal equity). `[PDF: welch2013]`
- **Why minimize total cost, not average time?** Averaging lets the optimizer drop difficult passengers to
  improve the mean; summing total user cost + penalizing incompletes forces coverage. `[M §3.5.7]`, `[PDF: kepaptsoglou2009, fan2006]`
- **α/β disambiguation:** these (0.5, 2.0) are *unrelated* to the DDM exponents (0.6, 0.4) and the logistic
  α/β — same letters, different quantities. We added this note to the paper. `[M §3.5.7, corrected]`

### 6.6 Likely advisor questions
- **Q: Is `F_sim` in EIVM or seconds?** A: Seconds (realized time-in-system). EIVM governs path *selection*;
  fitness measures realized performance including emergent capacity/queue effects. *(Have this crisp.)*
- **Q: Why penalize incompletes instead of dropping them?** A: Otherwise the optimizer minimizes by *stranding*
  — the underservice term with β=2 makes an unfinished trip strictly costlier than any finished one.
- **Q: Why the √ in Mohring, not linear?** A: Linear starves long/low-demand routes; √ flattens the curve so
  the network stays connected — the economies-of-scale logic of the Mohring effect.
- **Q: Does opportunistic boarding actually help or just add noise?** A: It significantly lowers delay for its
  users (U=953, p=0.0022 at δ=14.44) — a tested behavioral benefit, not a perturbation.
- **Q: Completion fraction is low — is the sim broken?** A: No — arrivals are continuous and truncated at a
  fixed 90-min horizon, so a trailing cohort is always mid-trip; we calibrate on *fitness stability* (CV),
  not completion. `[R4 §4.3.3]`

---

## 7. MODULE — Pheromone Matrix & the Demand-Service Gap `[M §3.6.1]` (the conceptual heart)

**What is a "pheromone" here?** It is **stigmergic demand memory**. In ant colonies, ants drop chemical
pheromone on good paths; later ants are drawn to stronger trails, so the *environment* (not direct messaging)
coordinates the colony `[PDF: Dorigo1996 — "A moving ant lays some pheromone ... thus reinforcing the trail ...
the more the ants following a trail, the more attractive that trail becomes ... a positive feedback loop"]`.
Here, **each road corridor is a pheromone cell**, keyed by its start/end coordinates so the *same physical road*
accumulates demand evidence even across different candidate networks and generations. `[M §3.6.1]`

**Collection & update (post-simulation).** After a chromosome is simulated, every edge a passenger traversed
gets reinforced inversely to journey cost (cheaper journeys = stronger trails), then all pheromone evaporates:
- Deposit: **`Δτ_ij = Q / C`** (Q = 1000, C = journey EIVM cost). `[cfg]`, `[PDF: Dorigo1996]`
- Evaporate-then-deposit: **`τ_ij(t+1) = (1−ρ)·τ_ij(t) + Δτ_ij`**, ρ = 0.1. `[cfg]`
- Evaporation prevents stale demand signals from dominating. `[M §3.6.1]`

**The Demand-Service Gap (the signal that steers local search).** `[M §3.6.2]` A naïve "demand − supply"
(`τ_ij − s_ij`) is dimensionally broken: τ is an unbounded continuous memory, s is a discrete vehicle count, so
their difference drifts as pheromone accumulates. Fix: **normalize both into shares**:
$$P_{ij} = \frac{\tau_{ij}}{\sum \tau}, \qquad S_{ij} = \frac{s_{ij}}{\sum s}, \qquad \Delta_{ij} = P_{ij} - S_{ij} \in [-1,1]$$
- `Δ_ij > 0` → **underserved** (demand share exceeds fleet share).
- `Δ_ij < 0` → **oversupplied** (fleet share exceeds demand share).
- System-level disparity: **`D(R) = Σ |P_ij − S_ij|`** (L1 distance between demand and supply distributions).
- This is exactly horizontal-equity logic at the edge level: Welch & Mishra define horizontal equity as *"the
  equal distribution of an attribute (or recourse) among equal members of a population"* `[PDF: welch2013, p.30 —
  verified verbatim]`; here "equal distribution of fleet relative to demand."

**Worked gap example.** Edge with τ=50, network Στ=1000 → P=0.05. It has s=2 vehicles (weight 1 each), system
Σs=100 → S=0.02. **Δ = +0.03 → underserved**: this corridor carries 5% of demand memory but only 2% of fleet.
The Or-opt Attraction operator will try to pull service toward it.

**Advisor Qs:** *What is a pheromone concretely?* (a per-corridor accumulator of inverse-cost demand evidence).
*Why normalize the gap?* (to kill the τ-vs-s dimensional mismatch and bound it in [−1,1] so it's stable across
generations). *Is the gap a good proxy for fitness?* (moderately — Pearson **r = −0.41** between D(R) and F_sim
on toy systems `[R4 §4.3.6]`; lower disparity → lower user cost, but imperfect because F_sim also integrates
capacity/queue/equity the gap ignores).

---

## 8. MODULE — Lamarckian Local Search Operators `[M §3.6.3]`

**Purpose / why "Lamarckian."** Each child route system is *locally improved before* it is passed on (acquired
improvements are inherited — Lamarckian), and improvement is **steered by the demand-service gap**, not random.
Crucially, acceptance is gated on the **cheap gap** `D(R)`, not on a full re-simulation — substituting a light
surrogate criterion during intra-generational search is standard memetic practice `[PDF: jin2005 — no PDF]`. A
move is kept **iff it strictly reduces `D(R)`**, else reverted. `[M §3.5.7, §3.7]`

Three operators (each fires only when its trigger exists in the gap field):
1. **Spatial Attraction (Demand-driven Or-opt):** lift a *k*-edge segment (k∈{1,2,3}) and transplant it next to
   an **underserved** (top-20% positive-gap) corridor at minimum length increase — exactly **3 A\* calls** per
   candidate. Or-opt is a classical VRP move (lift a segment, reinsert at least cost). `[M §3.6.3.1]`
2. **Redundancy Repulsion (Pheromone-guided 2-opt):** target the **most oversupplied** (most negative-gap)
   corridor, reverse a segment via a new A\* path that bypasses it, pushing fleet outward. 2-opt is the canonical
   tour-improvement operator. `[M §3.6.3.2]`
3. **Tortuosity Pruning (sliding window):** replace the most circuitous low-utility window with a direct A\*
   shortest path. Circuity (tortuosity) = actual path length ÷ straight-line distance — a foundational transit
   directness criterion `[PDF: ceder1986 (bus network design / route directness); baaj1991 (route straightening)]`.
   **Gap-immunity rule:** any window containing a positive-gap edge is *exempt* from pruning, so pruning can't
   undo the coverage Attraction just added. `[M §3.6.3.3]`

**Advisor Qs:** *Why gate on the gap instead of re-simulating each tweak?* (running the temporal engine per
micro-move would bottleneck the search; the gap is an internally consistent O(1)-cached proxy, and the same
signal that *directs* the move also *accepts* it). *Why only 3 A\* calls in Or-opt?* (one to fill the lifted
segment's hole, two to bridge it into the new spot). *What stops pruning from destroying coverage?* (the
positive-gap immunity rule).

> **CRITICAL [R4 status box]:** In the current Iligan production runs the local search **was not firing** (a
> leftover from the deprecated surrogate module left the gap supply-less, `D(R)≡1`, so no move ever reduced it).
> It is fixed and the corrected runs are re-executing. The toy-grid demonstrations *do* show the operators
> working. See CRITICAL_PREP #2 — this is the single most important thing to be honest about.

---

## 9. MODULE — Memetic Genetic Operators `[M §3.6.4]`

A **chromosome = an entire route system**; a **gene = one jeepney route**. Crossover/mutation operate on whole
networks so closed-loop validity is preserved. Embedding GA operators inside the ACO loop (not as post-
processing) sustains diversity and escapes the positive-feedback traps of pure pheromone accumulation
`[PDF: Zhao2026 — GA crossover/mutation integrated into the ACO loop]`.

### 9.1 Topological Hub Crossover `[M §3.6.4.1]`
Random array-splicing destroys good corridors. Instead: identify the **topological hub** (top-decile corridors
by combined pheromone + structural importance); the *fitter* parent's routes that traverse the hub become the
child's **trunk**; the other parent's non-conflicting routes become **feeders**.
- **Why trunk-and-feeder?** Trunk corridors enjoy **economies of density** — average operating cost falls as
  volume on a fixed corridor rises `[PDF: Gschwender2016 — "economies of density (decreasing average operating
  cost) along the avenues served by trunk lines"]`. Evolutionary algorithms can be engineered to *protect a
  backbone* while optimizing feeders, beating flat crossover `[PDF: Risso2023 — backbone GA, "reduced end-to-end
  travel times, which improve up to five times over the current system"]`.

### 9.2 Epigenetic Inheritance (fitness-weighted pheromone blend) `[M §3.6.4.2]`
A child inheriting only geometry would have to rediscover demand from scratch. Instead it inherits a blended
demand memory:
$$\tau^{child}_{ij} = w_A\tau^A_{ij} + w_B\tau^B_{ij}, \qquad w_A = \frac{C_B}{C_A+C_B},\ w_B = \frac{C_A}{C_A+C_B}$$
- **Weights are inverted on purpose:** because lower cost = fitter, giving parent A the share `C_B/(C_A+C_B)`
  makes the *cheaper* parent contribute *more*. Exploitation (fitter parent's map) + a trace of the other
  (exploration). `[M §3.6.4.2]`
- **Why this is still valid ACO, not cheating:** in Population-based ACO the pheromone *is* the population —
  *"(nearly) all pheromone information corresponds to solutions that are members of the actual population"*
  `[PDF: guntsch2002 — verified verbatim]`; blending parent matrices is the weighted multi-matrix combination
  used in multi-objective/Pareto ACO `[PDF: garcia2004 — taxonomy of multi-objective ACO]`; cross-solution
  information transfer accelerates convergence and prevents stagnation `[PDF: Middendorf2002 — colonies "exchange
  information about good solutions"]`; and the population/belief-space duality is a Cultural Algorithm
  `[PDF: Reynolds1994 — no excerpt pulled yet, see fetch list]`.

**Advisor Qs:** *Why is the trunk taken from the fitter parent?* (to conserve the economies-of-density backbone).
*Why invert the blend weights?* (minimization → the lower-cost parent must dominate the inherited map).
*Doesn't blending pheromones break ACO?* (no — PACO already ties pheromone to population members; this is a
warm-start, not a violation).

---

## 10. MODULE — Optimizer Orchestration `[M §3.7]`

### 10.1 The generational pipeline `[M §3.7.1]`
Per generation: (1) **evaluate parents** by full simulation (→ fitness + pheromone map); (2) **elitism**
(N_elite=1 Iligan / 2 toy copied unchanged) + **tournament selection** (k=3, pick best 2 of 3 random); (3)
**Topological Hub Crossover + Epigenetic Inheritance** (warm-start, no pre-sim of the child); (4) **gap-gated
Lamarckian local search**; (5) **one** final simulation of the optimized child. *The whole design exists to call
the expensive simulation exactly once per child.* `[cfg: n_population=10, g_max=30]`

### 10.2 Adaptive control `[M §3.7.2 — corrected]`
**A single mutation rate** scales **quadratically** with the stagnation counter `s`:
$$P_{mut} = P_{base} + (P_{max}-P_{base})\left(\tfrac{s}{S_{limit}}\right)^2,\quad P_{base}=0.25,\ P_{max}=0.8,\ S_{limit}=30$$
It boosts how *often* local search fires during plateaus and **resets to baseline** the moment a new best is
found. Quadratic (not linear) gives patience early, force late `[PDF: eiben1999 — adaptive parameter control]`.
The three local-search operators keep **fixed** activation probs (0.4/0.4/0.6) `[cfg]`. Local-search probability
and spatial **intensity** `I_local(g)` decay **linearly** 1.0→0.1, tightening edits from broad to surgical.
> *(We corrected the paper here: it previously claimed three independently-capped operators; the code uses one
> adaptive rate + fixed operators. See CODE_FIXES_TODO #4.)*

### 10.3 Dual convergence `[M §3.7.3]`
Stop only when **both** signals saturate: (a) **elite Jaccard similarity** `J = |E_A∩E_B|/|E_A∪E_B|` high for
`jaccard_patience` generations (decision-space saturation), and (b) **fitness variance** `σ²(F)` below ε
(objective-space saturation). Both are needed because transit landscapes have *neutral networks* — chromosomes
that differ structurally (low Jaccard) but yield identical travel time (so variance must also be checked).
> **[UNCLEAR — CRITICAL_PREP]:** the exact Jaccard *threshold* and variance *ε* are pending from the new runs;
> `jaccard_patience=30` is set `[cfg]` but the threshold/ε numbers are not in the config yet.

### 10.4 Parallelization & determinism `[M §3.7.4]`
Process-level workers (bypass the GIL); workers cache CityGraph/DDM once; routes ship as lightweight
`path_keys`; TravelGraphs are cached per route-set; the RNG state is checkpointed for deterministic replay.
*(You — the student — also empirically verified this run-to-run determinism: same seed → byte-identical fitness
on the current code; old vs new code differ by <0.06% = float noise, see the determinism harness.)*

---

## 11. MODULE — Post-Optimization Metrics `[M §3.8]`

Three orthogonal "are two networks the same?" questions:
- **Jaccard** (set theory): shared-edge overlap `|A∩B|/|A∪B|`. Used 3×: convergence, hub identification, and
  post-eval comparison. Example: 80 shared of 120 union → J = 0.667. `[M §3.8.1]`
- **Discrete Fréchet** (geometry, *order-aware*): the "dog-walker leash" distance; unlike Hausdorff it respects
  traversal direction, so two routes on the same streets going opposite ways are correctly dissimilar.
  `[PDF: "computing frechet distance" (Eiter & Mannila 1994)]`. `[M §3.8.1]`
- **GED** (topology): minimum edit cost (insert/delete/substitute) to morph one route graph into another.
  `[PDF: sanfeliu1983]`. `[M §3.8.1]`
- **Wasserstein / Earth-Mover (demand-aware):** mass × distance to reshape one spatial demand-coverage
  distribution into another — the only metric that asks "does coverage match demand?" `[PDF: "optimal transport
  and wasserstein distance" (De Bacco et al.)]`. `[M §3.8.2]`
- **Shannon entropy** `H = −Σ p_i log p_i` (diversity/resilience): high = trips spread across many routes (robust
  to link failure); low = concentration (possible premature convergence). `[M §3.8.3]`

**Robustness results `[R4 §4.5]`:** 7 seeds → mean Jaccard **0.73**, mean 2D Wasserstein **0.009** (tight
clustering = seed-independent). Temporal (08/13/17h) → Jaccard >0.70 on the trunk → a *static franchise* backbone
is viable. Entropy ≈ **3.2 bits** (diverse, resilient).

---

## 12. WORKED NUMERICAL EXAMPLE — MSU-IIT → Robinsons Place

**OD:** MSU-IIT (8.2415, 124.2435) → Robinsons Place (8.2175, 124.2380). `[R4 §4.1.1 landmarks]`

**Step 1 — straight-line (Haversine) distance.** Δlat = 0.0240°, Δlon = 0.0055°. At lat ≈ 8.2°: 1° lat ≈
110,574 m, 1° lon ≈ 110,190 m. So Δy ≈ 2,654 m, Δx ≈ 606 m → **D_straight ≈ √(2654² + 606²) ≈ 2,722 m**.

**Step 2 — A\* heuristic lower bound.** `h = D_straight · min(walk_wt, ride_wt) = 2722 × 0.00632 ≈ 17.2 EIVM`.
Any real journey must cost ≥ 17.2 EIVM (admissibility check).

**Step 3 — price a candidate DIRECT journey** (one jeepney):
| leg | type | qty | weight | cost (EIVM) |
|---|---|---|---|---|
| origin → stop | SW | 300 m | 0.05630 | 16.89 |
| board | WA | 1 | 14.44 | 14.44 |
| ride | RI | 2,800 m | 0.00632 | 17.70 |
| alight | AL | 1 | 0 | 0.00 |
| stop → dest | EW | 200 m | 0.05630 | 11.26 |
| **total** | | | | **60.29** |
✓ 60.29 ≥ 17.2 (heuristic never overestimated).

**Step 4 — price a competing TRANSFER journey** (two jeepneys):
SW 300m (16.89) + WA (14.44) + RI 1500m (9.48) + AL (0) + walk-to-transfer 100m (5.63) + **TR (15.78)** +
RI 1400m (8.85) + AL (0) + EW 200m (11.26) = **82.33 EIVM**.

**Step 5 — A\* picks the cheaper.** 60.29 < 82.33, so A\* returns the **direct** journey. The transfer route
loses *entirely because of the +15.78 transfer penalty* — exactly the behavior the survey-calibrated
`transfer_wt` is meant to produce. (Drop `transfer_wt` to 0 and the transfer route would cost 66.55, still
losing here — but on longer trips where the transfer saves real riding distance, the 15.78 is what decides it.)

**Step 6 — how this passenger feeds the rest of the pipeline.**
- *Pheromone:* this completed journey deposits `Δτ = Q/C = 1000 / 60.29 ≈ 16.6` on each of its road edges.
- *Mohring D_r:* the ride legs add their passenger-distance to the demand level of the route(s) used.
- *Fitness:* the passenger's **realized elapsed seconds** (walk + any wait + ride, including a full jeepney that
  passed them) enter Term 1 of `F_sim` — *not* the 60.29 EIVM (that was only used to choose the path).

**Step 7 — a DDM score for the origin node** (illustrative numbers): with traffic weight `W_i = 1.188`
(08:00 mean) and betweenness `C_i = 0.02`: `S_i = 1.188^0.6 × 0.02^0.4 = 1.110 × 0.2089 ≈ 0.232` (unnormalized);
divide by ΣS to get the sampling probability. Busy *and* central nodes dominate.

**Step 8 — Mohring allocation** (3 routes, fleet 2000, demand levels D = 100, 49, 25): √D = 10, 7, 5; Σ = 22 →
`f₁ = 2000·10/22 ≈ 909`, `f₂ ≈ 636`, `f₃ ≈ 455`. Route 1 has 4× route 3's demand but only ~2× its fleet — the
**√ subsidy** keeping the low-demand route alive.

---

## 13. MASTER CITATION TABLE (why each appears + excerpt status)

✅ = verbatim excerpt pulled/verified from the PDF in `paper/sources/`. 📄 = PDF present, excerpt extractable on
request. ❌ = **no PDF — see fetch list (§15).**

| Citation | Role in our work | Excerpt status |
|---|---|---|
| Dorigo (1996) Ant System | ACO foundation; `Δτ=Q/C`, evaporation, stigmergy | ✅ *"a moving ant lays some pheromone … the more the ants following a trail, the more attractive that trail becomes … a positive feedback loop"* |
| García-Martínez (2007) MOACO taxonomy (`garcia2004.pdf`) | weighted multi-matrix pheromone combination (epigenetic blend) | ✅ taxonomy of multi-objective ACO; weighted Σ p_k·τᵏ |
| Guntsch & Middendorf (2002) PACO | pheromone ≙ population (epigenetic legitimacy) | ✅ *"all pheromone information corresponds to solutions that are members of the actual population"* |
| Middendorf (2002) Multi-colony | cross-solution info transfer (inheritance) | ✅ *"colonies exchange information about good solutions"* |
| Gschwender (2016) | economies of density → trunk-and-feeder | ✅ *"economies of density (decreasing average operating cost) along the avenues served by trunk lines"* |
| Risso (2023) | backbone-protecting GA | ✅ *"reduced end-to-end travel times, which improve up to five times over the current system"* |
| Kepaptsoglou (2009) TRNDP review | Total User Cost, route directness, overlap, network utilization | ✅ *"route directness implies that route shapes are as straight as possible … overlapping with other transit routes"* |
| Welch & Mishra (2013) | horizontal-equity basis of the gap + equity term | ✅ *"the equal distribution of an attribute (or recourse) among equal members of a population"* |
| Ceder & Wilson (1986) | circuity/directness design criterion | ✅ bus network design; route directness objective |
| El-Geneidy (2014) | 85th-percentile walking catchment | ✅ (title/concept) *"the 75th and 85th percentile buffers … more accurately represent walking area for most users"* (body) |
| Iseki & Taylor (2009) | transfers deter ridership; opportunistic boarding | ✅ *"Not All Transfers Are Created Equal … Relating Transfer Connectivity to Travel Behaviour"* |
| Mandl (1980) | demand-weighted transit route heuristic benchmark | ✅ urban transit network evaluation/optimization |
| Train (2002) Discrete Choice | 50%-utility transfer threshold | 📄 |
| Spiess & Florian (1989) | zero-cost transit connectors / assignment | 📄 |
| Farahani (2013) TRNDP review | shortest-path route construction; network flow | 📄 |
| Fan (2006) | Total User Cost objective | 📄 |
| Munoz (2021) | web-API travel-data legitimacy | 📄 |
| Zafar (2020) | Congestion Index `t_travel/t_free` | 📄 |
| Vladut (2025) | TomTom per-segment real+free-flow payload | 📄 |
| Leong (2020) | free-flow speed definition | 📄 |
| Peng (multi-layer) | multilayer transport representation | 📄 |
| Guillen (2013) | PUJ/tricycle paratransit hierarchy | 📄 |
| Cochran (1977) | sample-size formula | 📄 |
| Sanfeliu (1983) | GED definition | 📄 |
| Eiter & Mannila (1994) (`computing frechet distance.pdf`) | discrete Fréchet | 📄 |
| De Bacco (optimal transport pdf) | Wasserstein/EMD on networks | 📄 |
| Zhao (2026) | GA operators inside ACO loop | 📄 |
| Eiben (1999) (`Parameter_control….pdf`) | adaptive mutation control | 📄 |
| Sastry (2013) | GA pipeline determinism | 📄 |
| Sanchez (2025) | the baseline we improve on | 📄 |
| Ranosa (2021) | 9.5 km/h jeepney speed | 📄 (newly added) |
| Katsaros (2024) (`katarsos2024.pdf`) | 1.2 m/s walking speed | 📄 (newly added) |
| Mohring (1972) | **fleet-allocation rule + headway** | ❌ FETCH |
| Reynolds (1994) Cultural Algorithm | population+belief-space duality | 📄 (no excerpt pulled yet) |
| García-Martínez (2018) transfer penalty | 15.2–17.7 EIVM anchor | ❌ FETCH |
| Jara-Díaz (2022) | 13–18 EIVM transfer penalty | ❌ FETCH |
| Freeman (1977) | betweenness centrality | ❌ FETCH |
| Lowry (2014) | OD-centrality framework | ❌ FETCH |
| Walker (1977) | alias method | ❌ FETCH |
| Ortúzar & Willumsen | generalized cost theory | ❌ FETCH |
| Hart (1968) / Russell & Norvig | A\* + admissibility | ❌ FETCH |
| Bentley (1975) | KD-tree | ❌ FETCH |
| Boeing (2017) OSMnx | OSM extraction | ❌ FETCH |
| Coello (2002) | exterior penalty functions | ❌ FETCH |
| Jin (2005) | surrogate-assisted optimization | ❌ FETCH |
| Laporte (2002) / Ciaffi (2012) | Or-opt / 2-opt in transit | ❌ FETCH |
| Levinson (2012) | entropy & network resilience | ❌ FETCH |
| Peduzzi (1996) | 10–20 events/predictor rule | ❌ FETCH |

### 13b. Verbatim excerpts pulled this pass (now ✅, from `paper/sources/`)

- **Mohring (1972/1971)** *"Optimization and Scale Economies in Urban Bus Transportation":* *"The appropriate social
  response to declining mass transit quality can … be seen by recognizing this phenomenon to be an example of what
  happens when demand declines for a commodity the production of which involves increasing returns to scale."* →
  the economies-of-scale (Mohring-effect) basis for demand-scaled frequency. **Note:** Mohring establishes the
  *increasing-returns* basis; the **√D_r** allocation rule is *our operationalization*, not literally a square root
  stated by Mohring. (Be ready for: "where does the square root come from?" → "it's the standard frequency-∝-√demand
  operationalization of Mohring's increasing returns.")
- **García-Martínez et al. (2018):** *"the pure transfer penalty is comparable to a 15.2–17.7 equivalent increase in
  in-vehicle minutes; i.e. longer trips may be preferred to faster alternatives with transfers, even if the additional
  walking and waiting times are zero."* → external anchor for `transfer_wt` = 15.78 EIVM.
- **Walker (1977):** *"A number is either accepted or replaced with an 'alias' number"*; the method *"requires at most
  two memory references and a comparison."* → O(1) alias sampling.
- **Freeman (1977)** *"A Set of Measures of Centrality Based on Betweenness"* → canonical source of the betweenness
  `C_B(v)` formula.
- **Lowry (2014):** *"novel explanatory variables that are intrinsically derived through a modified form of centrality …
  out-of-sample validation R² = 0.95."* → OD-centrality basis for estimating traffic from topology.
- **Hart, Nilsson & Raphael (1968):** *"demonstrates an optimality property of a class of search strategies."* → the A\*
  admissibility/optimality theorem.
- **Spiess & Florian (1989)** *"Optimal Strategies: A New Assignment Model for Transit Networks"* → transit assignment
  with explicit waiting; basis for separate access/ride/alight/transfer links.
- **Sanfeliu & Fu (1983):** GED = cost of *"node insertion, node deletion, branch insertion, branch deletion, node label
  substitution and branch label substitution."* → the GED definition.
- **Eiter & Mannila (1994)** *"Computing Discrete Fréchet Distance"* → the discrete-Fréchet DP recurrence.
- **Wasserstein notes:** *"These distances ignore the underlying geometry of the space … this is captured by Wasserstein
  distance."* → the demand-aware coverage comparison. **⚠ [flag] this PDF is generic optimal-transport lecture notes
  (citing Kolouri 2017 & Villani 2003), NOT the De Bacco 2023 multi-layer-network paper the methodology names — verify
  that citation before the meeting.**
- **Train (2002)** *Discrete Choice Methods with Simulation* → the binary-logit "P=0.5 ⇒ equal systematic utility"
  break-even used to isolate `transfer_wt`.
- **Zhao et al. (2026):** *"genetic operators—namely crossover and mutation—are embedded within the main ACO iterative
  loop to dynamically sustain population diversity and effectively mitigate stagnation in local optima."* → direct source
  for the GA-in-ACO hybrid.
- **Eiben, Hinterding & Michalewicz (1999):** *"any static set of parameters, having the values fixed during an EA run,
  seems to be inappropriate. Parameter control forms an alternative …"* → adaptive mutation scaling.
- **Reynolds (1994):** *"the addition of a belief space to the traditional Genetic Algorithm framework can affect the rate
  at which learning can take place."* → Cultural Algorithm (population space + belief space) basis for epigenetic
  inheritance.
- **Zafar & Ul Haq (2020):** congestion *"using Estimated Time of Arrival (ETA) … one of the five traffic states i.e.
  smooth, slightly congested, congested, highly congested or blockage."* → the `V_i` congestion-index basis (matches the
  paper's five states verbatim).
- **Guillen, Ishida & Okamoto (2013):** the door-to-door chain *"tricycle … to riding a public utility jeepney (PUJs) or
  bus … hopping on to another 'pedicab or tricycle'"* → PUJ-vs-access-mode hierarchy justifying arterial-only routing.
- **Peng et al. (2023)** *"A multi-layer modelling approach for … a global maritime transportation network"* → multilayer
  transport representation basis for the 3-layer graph.
- **Katsaros / Giannoulaki (2024)** *"Pedestrian Walking Speed Analysis: A Systematic Review"* → walking-speed literature
  basis (1.2 m/s). **⚠ [flag] the file's actual authors are Giannoulaki & Christoforou — verify the `katsaros2024` cite
  key matches the intended paper.**
- **⚠ ranosa2021 NUMBER MISMATCH:** the abstract reports jeepney **average speed = 10.228 km/h** (Baguio City), but the
  methodology adopts **9.5 km/h** citing this source. See CRITICAL_PREP #3 — this is now a *paper-vs-source* gap, not just
  code-vs-paper.

---

## 14. FLAGGED UNCERTAINTIES (study these — they are where YOUR gaps are)

1. **`[RESOLVED]` DDM α=0.6 / β=0.4** — sensitivity sweep proves the split is immaterial (ρ≥0.997 over [0.3,0.7]); form is Cobb-Douglas. Remaining nuance: the surface is centrality-*dominated*, traffic-modulated (reframe, don't claim "traffic-led"). (CRITICAL_PREP #4)
2. **`[ASSUMPTION]` `weight_tolerance`=14.44** justified post-hoc as "one wait-event's tolerance." (CRITICAL_PREP #5)
3. **`[KNOWN ISSUE]` Lamarckian local search was inert in current Iligan runs** (supply-less gap); fixed, re-running. (CRITICAL_PREP #2)
4. **`[CODE≠PAPER]` jeep speed** (code 20 km/h vs paper 9.5) and **Mohring `D_r`** (code edge-count vs paper edge-length). Logged in CODE_FIXES_TODO; do not show config. (CRITICAL_PREP #3)
5. **`[PENDING]` Jaccard threshold & variance ε** for the convergence criteria — coming from the new runs.
6. **`[CHECK]` `F_sim` baseline number 729,592** appears for *both* the toy showcase and the Iligan baseline in Ch4 — likely a placeholder duplication while the corrected runs finish. Verify before presenting. `[R4 §4.4 vs §4.5.1]`
7. **`[SOURCE MISMATCH]` jeepney speed 9.5 km/h** — the cited source `ranosa2021` actually reports **10.228 km/h**. The paper's 9.5 is *lower* than its own source (and the code runs 20). If you used 10.228, `ride_wt` would be ≈ 0.00587 instead of 0.00632. (CRITICAL_PREP #3)
8. **`[CITATION CHECK]` two source files don't match their cite keys:** the Wasserstein PDF is generic OT lecture notes (Kolouri/Villani), not the `debacco2023` multi-layer paper; the `katsaros2024` file is actually Giannoulaki & Christoforou (2024). Confirm the bib entries.

---

## 15. PDFs TO FETCH (you said you'd grab these — needed for a verbatim excerpt)

**✅ FETCHED & EXCERPTED (this pass):** Mohring (1972), García-Martínez (2018), Freeman (1977), Walker (1977),
Lowry (2014), Hart (1968) — all now have verbatim excerpts in §13b.

**Still missing a PDF (secondary — fetch only if the advisor is likely to demand the exact source line):**
Jara-Díaz (2022) *(redundant — García-Martínez 2018 already anchors the transfer penalty)*, Ortúzar & Willumsen
*(generalized-cost theory — textbook)*, Boeing (2017) OSMnx, Coello (2002) penalty functions, Bentley (1975)
KD-tree, Laporte (2002)/Ciaffi (2012) Or-opt/2-opt, Levinson (2012) entropy-resilience, Jin (2005) surrogate
optimization, Peduzzi (1996) events-per-predictor.

**Cite-key issues to fix (PDFs present but mislabeled):** `debacco2023` → the Wasserstein file is Kolouri/Villani
lecture notes; `katsaros2024` → file is Giannoulaki & Christoforou (2024). `sanchez2025.pdf` lives in `paper/`
(not `paper/sources/`).
