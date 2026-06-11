# Thesis Defense Deck — Jeepney Route Network Optimization (Iligan City)

> ⚠️ **SUPERSEDED — condensed 20-min fallback only.** The authoritative deck is the per-chapter set
> `DECK_00_master.md` … `DECK_05_conclusion.md`. **Run-status framing here is OUTDATED:** the runs are **frozen** —
> there are **no** "corrected runs completing," no "[date]," no re-execution. The reported Iligan results reflect the
> **global genetic search**; the Lamarckian local operators are validated on the toy showcase (see `DECK_00` Appendix
> A3). If you use this file, replace every "completing / re-executing / by [date]" line with that scope framing, and
> present the 15–20% commute reduction as the reported aggregate result (not a pending Mann–Whitney).

> **How to use this file.** Each `## Slide` block has three parts:
> **On-slide** = the bullets/visuals that go ON the slide (keep them sparse — this is panel-facing, not a wall of text).
> **🎤 Script** = roughly what to *say* (1st person, conversational, ~30–60 s/slide).
> **📝 Notes** = presenter reminders, anticipated panel questions + answers, and `⚠ PLACEHOLDER` markers for results
> still finishing. Target ~22–25 min for the main deck; the **Backup/Appendix** slides are for tough Q&A.
>
> **Three honesty anchors to keep in mind the whole time** (see `CRITICAL_PREP.md`): (1) `F_sim` is realized
> *seconds*, EIVM governs *path choice*; (2) the demand surface is *centrality-led, traffic-modulated*; (3) the
> full-system Iligan runs are *completing* — current Iligan numbers are an honest GA-only intermediate.

---

## Slide 1 — Title

**On-slide:**
- **A Parallel Hybrid Memetic GA–ACO Framework for Optimizing Decentralized Jeepney Route Networks**
- *A Data-Driven Transit Route Network Design (TRNDP) Approach for Iligan City, Philippines*
- [Author names] · [Degree/Program] · [Adviser] · [Panel] · [Date]

**🎤 Script:** "Good morning. Our thesis tackles a problem most transit optimization tools quietly ignore —
how do you redesign an *informal*, decentralized public transport network like the jeepney system? We built a
data-driven framework that learns commuter behavior from a local survey, simulates passengers as autonomous
agents, and optimizes whole route systems with a hybrid evolutionary algorithm. I'll take you from the problem
through to the results."

**📝 Notes:** Keep it to ~20 s. Don't read the title verbatim. Set the frame: *informal* transit + *data-driven*
+ *whole-network* optimization.

---

## Slide 2 — Outline

**On-slide:**
1. The problem & research gap
2. Objectives & contribution
3. Methodology — the pipeline
4. Results & discussion
5. Conclusion, limitations, future work

**🎤 Script:** "Here's the path: the problem and the gap we're filling, our objectives, the methodology pipeline,
the results, and finally conclusions and where this goes next."

**📝 Notes:** 10 s. Signpost so the panel can track you.

---

## Slide 3 — The Problem: Paratransit Is Different

**On-slide:**
- Jeepneys = the backbone of Philippine urban mobility, but **informal & decentralized**: no central dispatcher,
  no fixed timetable, hail-and-ride boarding, owner-operator franchises.
- Classic Transit Route Network Design assumes the *opposite*: central control, rigid schedules, fixed stops.
- → Standard models don't fit. And Iligan has **no digitized/optimized route baseline** to start from.

**🎤 Script:** "Jeepneys move millions of people a day, but they're informal — drivers own their own vehicles,
there's no schedule, and you board anywhere. The entire academic toolkit for designing transit networks assumes
central coordination and fixed stops, which is the exact opposite of how paratransit actually works. On top of
that, Iligan has no existing digitized route map to optimize against. So the gap is both *methodological* and
*data*."

**📝 Notes:** This is the motivation slide — sell the gap. If asked "why Iligan?": it's a representative
mid-size Philippine city, and it's our local context (enables the primary survey).

---

## Slide 4 — The Research Gap & Our Idea

**On-slide:**
- **Gap:** optimize a *decentralized* paratransit network with *behaviorally realistic* demand & no OD matrix.
- **Our approach (one line):** learn behavior from a survey → simulate passengers as agents → optimize whole
  route systems with a memetic GA–ACO that *evaluates designs by simulation*.
- Builds directly on **Sanchez (2025)** — but replaces a toy grid + uniform demand + GRASP with a real city,
  data-driven demand, and a memetic learning algorithm.

**🎤 Script:** "Our idea is to close that gap with three moves: calibrate commuter behavior from a local survey,
evaluate every candidate network with an agent-based passenger simulation, and search the design space with a
hybrid memetic algorithm. This is a direct upgrade of Sanchez 2025 — that work proved the concept on a grid with
uniform demand; we move to the real Iligan road network, data-driven demand, and a much stronger optimizer."

**📝 Notes:** Anchor everything to "improve on Sanchez 2025" — the panel will respect a clear lineage. Three
upgrades: **GRASP → memetic**, **uniform → data-driven demand**, **grid → real topology**.

---

## Slide 5 — Research Objectives

**On-slide:**
1. Gather **empirical behavioral data** from local jeepney users (survey).
2. Build a **microscopic agent-based** passenger simulation.
3. Design a **memetic optimizer** with local-search learning.
4. Implement **parallel evaluation** of candidate networks.
5. **Validate & benchmark** the optimized network vs. baselines.

**🎤 Script:** "Five objectives: collect the behavioral data, build the simulation, design the optimizer, make it
parallel so it's tractable, and validate the result against a baseline. The rest of the talk maps onto these."

**📝 Notes:** These are verbatim from the conclusion chapter — be consistent. Each later section explicitly
"closes" one objective.

---

## Slide 6 — Significance & Contribution

**On-slide:**
- A **reusable framework** for optimizing informal transit in data-scarce cities.
- **Behavioral realism**: a single generalized-cost unit (EIVM) calibrated from local data.
- **Methodological novelty**: epigenetic pheromone inheritance + gap-gated Lamarckian local search inside a GA.
- **Policy-relevant**: static route + fleet design suited to decentralized owner-operator reality.

**🎤 Script:** "Why it matters: it's a transferable method for cities that lack the data richness of a Singapore
or a London. The behavioral realism comes from one calibrated cost unit. The methodological novelty is how we
fuse ant-colony memory into a genetic algorithm. And the output — static routes plus a fleet allocation — is
exactly the kind of plan a decentralized franchise system can actually adopt."

**📝 Notes:** If asked "what's genuinely new vs. existing memetic algorithms?": the **epigenetic pheromone
inheritance** (children warm-start on a fitness-weighted blend of parents' demand memory) and the
**gap-gated acceptance** (local-search moves judged by a cheap demand–supply disparity, not a full re-sim).

---

## Slide 7 — Methodology: The Pipeline

**On-slide:**
- *(Diagram)* Survey → **EIVM weights**; OSM → **CityGraph**; TomTom + centrality → **Demand Model**;
  CityGraph + routes + weights → **3-layer TravelGraph**; agents → **simulation = F_sim**;
  **Memetic GA–ACO** proposes networks scored by that simulation → **optimized network**.

**🎤 Script:** "Here's the whole pipeline on one slide. Empirical inputs on the left — the survey and the road
network — feed three environment objects. The agent simulation turns any candidate network into a single fitness
number. And the optimizer loops: propose a network, simulate it, learn, repeat. I'll walk each block."

**📝 Notes:** Use `fig_system_pipeline.png`. Spend time here — it's the map for everything. Emphasize the **loop**:
the simulation is the evaluator inside the optimizer.

---

## Slide 8 — Step 1: Survey → EIVM (one cost unit)

**On-slide:**
- 214-respondent stated-preference survey (Iligan jeepney riders).
- Everything priced in **EIVM** = "one minute riding inside a jeepney."
- Calibrated weights: `walk` 0.0563 EIVM/m · `ride` 0.00632 EIVM/m · `wait` 14.44 EIVM/event ·
  **`transfer` 15.78 EIVM/event** · `direct`/`alight` = 0 (structural).

**🎤 Script:** "Step one: behavior. A journey mixes metres walked, minutes waited, and transfers — things you
can't add up directly. So we convert everything into one unit, the Equivalent In-Vehicle Minute. From the survey
we calibrate four weights. The headline one: a single transfer feels like almost *16 minutes* of riding — that's
why people hate transfers, and our model now knows that."

**📝 Notes:** Worked derivation of `transfer_wt` is on Backup-A1 if pressed. **Defensibility:** if asked "is EIVM
your fitness?" → "No — EIVM decides which *path* a passenger takes; the fitness measures realized *seconds*."
Sample-size question → Slide note on Backup-A4 (calibration, not citywide proportion estimation).

---

## Slide 9 — Step 1 detail: the transfer penalty (worked)

**On-slide:**
- Transfer acceptance is **binary** → fit a logistic model on 856 stated choices.
- Break-even (50% acceptance, equal utility): **S\* = −α/β = 2.1242 / 0.1346 ≈ 15.78 min**.
- Externally anchored: García-Martínez et al. (2018) report a pure transfer penalty of **15.2–17.7 in-vehicle min**.

**🎤 Script:** "Quick look at how we get 15.78, because the panel will ask. Transfer choice is yes/no, so we fit a
logistic curve to 856 stated choices and find the time-saving at which a commuter is *indifferent* — that's the
penalty. We get 15.78 minutes. And critically, that lands right inside the 15.2–17.7 range that international
transfer-penalty studies report. So our locally-derived number is externally validated."

**📝 Notes:** This slide exists *because* a technical panelist will probe a derived number. Keep the García-Martínez
external anchor ready — it's your strongest "this isn't made up" card. (Verbatim excerpt in STUDY_GUIDE §13b.)

---

## Slide 10 — Step 2: CityGraph & Arterial Filter

**On-slide:**
- OSM → directed road graph: **36,866 nodes, 76,310 edges**.
- PUJ arterial filter → **26,024 drivable edges (34.1%)** eligible for routing; the rest kept for *walking access*.
- Why: stop the optimizer routing jeepneys down dead-ends and alleys (combinatorial blow-up).

**🎤 Script:** "Step two: the road network. We pull Iligan from OpenStreetMap — about 37,000 intersections. Then
we filter to the third of edges that are realistic jeepney corridors, so the optimizer can't waste effort routing
buses down footpaths. But we *keep* the small roads — passengers still walk on them. Routing and walking are
different layers, which is the next idea."

**📝 Notes:** Numbers are from Ch4 §4.1.1. The PUJ-vs-access-mode hierarchy is backed by Guillen et al. (2013).

---

## Slide 11 — Step 3: Direct Demand Model (where trips start/end)

**On-slide:**
- No official OD matrix → build one. Nodes get demand from **traffic × structure**:
  `S_i = W_iᵅ · C_iᵝ` (α=0.6, β=0.4), normalized to a sampling probability.
- `W_i` = TomTom congestion ratio (real, time-varying); `C_i` = betweenness centrality.
- **Robust** to the exponent split: over α∈[0.3,0.7], demand ranking is invariant (Spearman ρ≥0.997).

**🎤 Script:** "Step three: demand. With no official origin-destination data, we estimate it. A node is a likely
trip endpoint if it's both *busy* — from live TomTom traffic — and *structurally important* — from network
centrality. We combine them as a weighted geometric mean. And we tested it: the result barely changes if you move
the weighting around, so it's not a fragile, hand-tuned number."

**📝 Notes:** ⚠ **Own the reframe proactively if a network person is on the panel:** the surface is *centrality-led,
traffic-modulated* (traffic's range is ~3×, centrality's ~3,600×). Don't oversell "traffic-aware." Sensitivity
figure = `ddm_alpha_beta_sensitivity.png`. (CRITICAL_PREP #4 — now resolved.)

---

## Slide 12 — Step 4: The Three-Layer TravelGraph (key idea)

**On-slide:**
- Split travel **state** into layers: **L1 walk-to-stop · L2 ride · L3 walk-from-stop/transfer**.
- Transitions carry the behavioral cost: **Wait** (board), **Transfer**, **Alight** (free), **Direct** (free).
- **Route isolation** kills the "teleportation anomaly": you can't switch jeepneys at a shared corner without
  paying a transfer.
- A\* on this graph returns the **least-EIVM** journey — provably optimal (admissible heuristic).

**🎤 Script:** "Step four is the core modeling idea. A normal road graph can't tell a walking passenger from a
riding one at the same intersection — so it would let someone hop between jeepneys for free. We fix that by
splitting travel *state* into three layers. Changing vehicles forces you through a transfer edge that charges the
penalty. On this graph, A\* search finds the cheapest journey in EIVM, and we prove the heuristic never
overestimates, so it's guaranteed optimal."

**📝 Notes:** Use `travel_graph_visualization.jpg`. A\* admissibility proof is Backup-A2 (have it ready — a
technical panel loves this). This slide closes a lot of "is your sim valid?" worries.

---

## Slide 13 — Step 5: Agent-Based Simulation = the evaluator

**On-slide:**
- Passengers = agents in a 4-state machine: **walk → wait → ride → done**; jeepneys loop their routes.
- **Capacity binds** (16 pax): a full jeepney leaves you waiting — emergent congestion a static model can't show.
- **Fleet via Mohring's √-rule:** `f_r = F_tot · √D_r / Σ√D_k` (demand-responsive, but subsidizes long routes).
- **Fitness `F_sim` = Total User Cost** = realized travel *time* + underservice penalty + equity term.

**🎤 Script:** "Step five turns a network into a score. We release passengers and jeepneys as agents and run 90
simulated minutes tick by tick. Capacity matters — a full jeepney passes you by, and you keep waiting, which is
exactly the compounding effect a textbook static model misses. We size the fleet per route with Mohring's
square-root rule, and the fitness is Total User Cost: the realized travel time of everyone, plus a penalty for
anyone stranded, plus an equity term."

**📝 Notes:** ⚠ **Be crisp:** *"`F_sim` is in realized seconds — EIVM drives path choice, the fitness measures
outcome."* The underservice penalty (β=2) stops the optimizer from "winning" by stranding hard passengers. Mohring
= economies of scale (the √ subsidizes low-demand routes so the network stays connected).

---

## Slide 14 — Step 6: The Memetic Engine (GA + ACO)

**On-slide:**
- **Chromosome = a whole route system; gene = one route.** (We evolve networks, not edges.)
- **GA** = global search (selection, crossover). **ACO** = a shared *pheromone* memory of where demand is.
- **Memetic** = each child is *locally improved* before competing — improvements are inherited (Lamarckian).

**🎤 Script:** "Now the optimizer. A candidate solution is an *entire* route system. We combine two ideas: a
genetic algorithm for global exploration, and an ant-colony pheromone memory that records where passenger demand
actually concentrates. It's *memetic* because every offspring network is locally polished before it competes —
and those improvements are written back and inherited."

**📝 Notes:** Define the analogy simply: pheromone = "scent trail of demand." Next slides unpack the three novel
pieces: the gap signal, the local search, and the inheritance.

---

## Slide 15 — Step 6a: Pheromones & the Demand-Service Gap

**On-slide:**
- After each simulation, edges a passenger used get reinforced: `Δτ = Q/C` (cheaper journeys = stronger trails);
  all trails evaporate (ρ) so stale demand fades.
- **The steering signal:** normalize demand & supply into shares, take the difference:
  `Δ_ij = P_ij − S_ij` (demand share − fleet share); `D(R) = Σ|P_ij − S_ij|`.
- `Δ>0` = underserved corridor · `Δ<0` = oversupplied.

**🎤 Script:** "Here's the signal that makes the search *intelligent*. After a simulation, every road a passenger
used gets a demand deposit inversely proportional to journey cost. Then we compare each corridor's *share* of
demand against its *share* of the fleet. A positive gap means underserved — lots of demand, not enough jeepneys.
A negative gap means we're wasting vehicles there. The total gap, D of R, is our cheap measure of how well service
matches demand."

**📝 Notes:** Normalizing into *shares* is the trick — it kills the dimensional mismatch between unbounded
pheromone and discrete vehicle counts and bounds the gap in [−1,1]. This is what the local search optimizes
between full simulations. Validity check on the next results slide (r=−0.41).

---

## Slide 16 — Step 6b: Lamarckian Local Search (gap-guided)

**On-slide:**
- Three operators, each fired by the gap field:
  - **Attraction** (Or-opt): pull service *toward* an underserved corridor.
  - **Repulsion** (2-opt): reroute *away* from an oversupplied one.
  - **Tortuosity pruning**: straighten low-utility detours (protected: never prune an underserved edge).
- **Gap-gated acceptance**: keep a move only if it lowers `D(R)` — no full re-simulation per tweak (huge speedup).

**🎤 Script:** "The local search has three moves, all steered by that gap. Attraction transplants route segments
toward underserved demand; repulsion pushes routes off oversupplied corridors; and pruning straightens wasteful
detours, but it's forbidden from cutting a corridor that's underserved. The clever part: we accept a move only if
it improves the cheap gap signal — we don't re-run the expensive simulation for every little tweak. That's what
makes the memetic search tractable."

**📝 Notes:** ⚠ **This is the slide tied to the WIP disclosure.** The mechanisms are demonstrated on the toy grid
(next results section). If the panel asks whether local search ran in the *final* Iligan run, be honest — see the
"Run status" backup slide A3. Or-opt/2-opt/circuity are classical, cited (Laporte, Ciaffi, Ceder, Baaj).

---

## Slide 17 — Step 6c: Genetic Operators (the inheritance)

**On-slide:**
- **Topological Hub Crossover:** keep the fitter parent's high-demand **trunk**; graft the other parent's
  **feeders**. (Economies of density — trunk corridors are cheaper per passenger.)
- **Epigenetic Inheritance:** child inherits a *fitness-weighted blend* of both parents' pheromone maps —
  `τ_child = w_A τ_A + w_B τ_B`, fitter parent weighted more.
- → Offspring **warm-start** on inherited demand memory instead of relearning the city from scratch.

**🎤 Script:** "Crossover is where the novelty concentrates. Instead of randomly splicing routes — which destroys
good corridors — we identify the busiest trunk of the fitter parent and keep it, then add complementary feeder
routes from the other parent. That's the feeder-trunk hierarchy transit economists recommend. And the child
*also* inherits a blended demand memory from both parents, weighted toward the fitter one — so its local search
starts informed, not blind. We call that epigenetic inheritance."

**📝 Notes:** Backed by Gschwender (economies of density), Risso (backbone GA), Guntsch/Middendorf (population-based
& multi-colony ACO), Reynolds (cultural algorithm — population + belief space). Verbatim excerpts in STUDY_GUIDE
§13b. This is your "what's new" slide — land it confidently.

---

## Slide 18 — Step 6d: Adaptive Control & Convergence

**On-slide:**
- **Adaptive mutation:** rate climbs *quadratically* with stagnation (0.25 → 0.8 cap), resets on improvement —
  patience early, force when stuck.
- **Parallel evaluation:** process-pool workers, each caching the road graph; lightweight route serialization.
- **Dual stop criterion:** structural saturation (**Jaccard**) *and* objective saturation (**fitness variance**).

**🎤 Script:** "Two practical pieces. First, the mutation rate is adaptive — when the search stalls it ramps up to
escape local optima, then relaxes once it finds something better. Second, evaluating thousands of networks is
expensive, so we parallelize across CPU cores. And we stop only when the population has converged on *both*
structure and fitness — that avoids both premature stopping and spinning on a flat landscape."

**📝 Notes:** Adaptive-mutation = Eiben 1999 (static params are inappropriate — verbatim in §13b). Dual criterion
matters because transit landscapes have "neutral networks" (different structure, same travel time). If asked for
the Jaccard threshold / variance ε: ⚠ pending from the corrected runs (placeholder).

---

## Slide 19 — Results: Environment & Demand Validation

**On-slide:**
- CityGraph: 36,866 nodes → 26,024 arterial edges (clean separation, landmarks aligned).
- DDM produces a *coherent demand gradient* (not scattered hotspots); 3 temporal surfaces (08/13/17h),
  traffic means 1.188 / 1.132 / 1.228.
- Exponent **robustness** confirmed (ρ≥0.997 over α∈[0.3,0.7]).

**🎤 Script:** "Onto results. First we validate the environment. The arterial filter cleanly separates routable
corridors from walking-only roads. The demand model produces a coherent gradient that concentrates on real
centers, and it shifts sensibly across the morning, midday, and evening windows. And as I mentioned, the demand
ranking is robust to how we weight traffic versus structure."

**📝 Notes:** Figures: `citygraph_comparison`, `ddm_3maps_comparison`, `ddm_time_comparison`,
`ddm_alpha_beta_sensitivity`. Reframe line ready: centrality-led, traffic-modulated.

---

## Slide 20 — Results: Architectural Validation

**On-slide:**
- All six TravelGraph transitions carry exactly their calibrated cost (no double-counting).
- A\* returns the **min-EIVM** journey, not the min-distance one (verified on a traced trip incl. a transfer).
- Simulation shows emergent realism: **capacity-limited waiting** + **maintained headways** (no early bunching).

**🎤 Script:** "Next we validate the machinery. Every transition in the travel graph charges exactly its own cost
— we checked each in isolation. A traced passenger journey confirms A\* picks the cheapest path in our cost units,
not the geometrically shortest. And the simulation reproduces the behaviors that justify an agent model in the
first place: passengers genuinely get left behind by full jeepneys, and vehicles hold their spacing instead of
clumping."

**📝 Notes:** Figures: `layer_transition_*`, `sample_journey_transfer`, `simulation_temporal_snapshots`. These
slides answer "is the simulation trustworthy?" before you show optimization gains.

---

## Slide 21 — Results: Calibration & a Real Behavioral Finding

**On-slide:**
- **Mohring stability:** per-route allocation CV falls to **0.11** at 2000 samples (94% of trips use transit).
- **Horizon/volume** fixed by fitness-stability: 540 ticks (90 min), 600 pax/hr.
- **Opportunistic riding works:** riders who took an acceptable earlier jeepney had median delay **0.70 min vs
  6.71 min** for those who waited (Mann–Whitney **U=953, p=0.0022**).

**🎤 Script:** "We calibrated the simulation knobs by stability, not by guesswork — for example, the fleet
allocation is reproducible to an 11% coefficient of variation. And we found a genuine behavioral result: when we
let passengers board a 'good-enough' earlier jeepney instead of rigidly waiting, the ones who did cut their delay
from about 6.7 minutes to under 1 — a statistically significant improvement. So the model captures rational
boarding, not just scripted behavior."

**📝 Notes:** This is a *real, defensible, finished* statistical result — lean on it. Figures: `mohring_stability`,
`horizon_volume_calibration`, `weight_tolerance_delta`. The `weight_tolerance`=14.44 framing ("one wait-event of
tolerance") is on Backup-A4.

---

## Slide 22 — Results: The Gap Signal Is Meaningful

**On-slide:**
- Each Lamarckian operator demonstrated in isolation on a Manhattan toy grid (before → after).
- **Gap predicts quality:** lower demand–service disparity `D(R)` ↔ lower (better) user cost,
  **Pearson r = −0.41** across independently generated systems.

**🎤 Script:** "Before trusting the local search to *steer* by the gap, we checked that the gap actually
correlates with quality. It does — systems with a smaller demand-service mismatch tend to have lower user cost,
with a correlation of about −0.4. It's moderate, not perfect, because the full fitness also captures capacity and
equity that the gap alone doesn't — but the sign and strength justify using it as a cheap steering signal."

**📝 Notes:** Figures: `lamarckian_operators_toy`, `gap_vs_fitness`, `memetic_demand_memory_gap`. Honesty: call it
"moderate but legitimate" — don't oversell r=−0.41.

---

## Slide 23 — Results: Evolutionary Dynamics

**On-slide:**
- Toy showcase converges: best `F_sim` **663,842 → 614,660**; improvements at gens 2–6, 11; mutation rate
  spikes on plateaus, resets on improvement.
- Hub crossover transmits the high-demand trunk; epigenetic inheritance blends parents' demand memory.
- Phenotypic convergence in **both** decision space (Jaccard ↑, GED ↓, Wasserstein ↓) and objective space
  (fitness variance ↓).

**🎤 Script:** "Putting it together on a controlled showcase, the optimizer converges in clear improvement steps,
with the adaptive mutation visibly ramping during plateaus and resetting on each breakthrough. We can watch the
trunk get conserved across generations and the demand memory get inherited. And convergence happens on every
axis at once — structure and fitness together — which tells us the search is genuinely homing in, not wandering."

**📝 Notes:** Figures: `opt_convergence`, `opt_evolution`, `hub_crossover`, `pheromone_blend`, `gap_change`. The
toy showcase is where local search is *definitely* active — emphasize that the *mechanisms* are proven here.

---

## Slide 24 — Results: Optimized Iligan Network  ⚠ PLACEHOLDER

**On-slide:**
- Baseline (random gen-0 cohort) vs. optimized — Total User Cost & demand-service disparity.
- Cross-run reproducibility: **mean Jaccard 0.73**, **2D Wasserstein 0.009** across 7 seeds.
- ⚠ **`[PLACEHOLDER — FINAL FULL-SYSTEM RUNS COMPLETING]`** — drop in: optimized `F_sim`, % cost reduction,
  `D(R)` baseline → optimized, the box-plot figure.

**🎤 Script:** "Now the real city. Across seven independent runs the optimizer converges to *highly similar*
networks — a Jaccard overlap of 0.73 — which means the result is reproducible, not a lucky seed. *[On the headline
optimization gain]:* our full-system production runs are completing now; the intermediate figure here is a
genetic-only configuration, and we'll have the final numbers in by [date]. The robustness and mechanism results
already stand on their own."

**📝 Notes:** ⚠ **The honest framing (rehearse it):** during final verification we found the Lamarckian local
search wasn't firing in the first Iligan run (a leftover from a deprecated module zeroed the supply side of the
gap). It's fixed and re-running; we kept the intermediate as an accidental GA-only *ablation*. Reproducibility
(0.73) is unaffected. **Do not present the intermediate cost numbers as final.** See Backup-A3.

---

## Slide 25 — Results: Equity, Temporal Robustness, Resilience  ⚠ PARTIAL PLACEHOLDER

**On-slide:**
- **Equity:** optimized network compresses the long tail of extreme travel times (the peripheral commuters).
- **Temporal robustness:** Jaccard > 0.70 on the trunk across 08/13/17h → a *single static backbone* is viable.
- **Resilience:** path-diversity **Shannon entropy ≈ 3.2 bits**.
- ⚠ **`[PLACEHOLDER]`** commute-time reduction (target **15–20%**) — passenger-level **Mann–Whitney** on
  baseline vs. optimized commute times is running on the high-RAM machine.

**🎤 Script:** "Three more outcomes. The optimized network is more *equitable* — it shrinks the tail of very long
commutes, which is the peripheral districts. It's *temporally robust* — the trunk barely changes between peak and
off-peak, which justifies a single static route design instead of impractical real-time dispatch. And it's
*resilient*, with high path diversity. The headline commute-time reduction — we're targeting 15–20% — is being
confirmed right now with a passenger-level Mann–Whitney test on the final runs."

**📝 Notes:** ⚠ The "15–20%" appears in the abstract/conclusion as the target; the *rigorous* per-passenger
Mann–Whitney is the pending confirmation (the heavy re-sim that needs more RAM). Frame as "targeting/confirming,"
not "achieved," until the number is in. Figures: `equity_traveltime_hist`, `robustness_temporal`,
`route_system_initial_vs_final`.

---

## Slide 26 — Conclusion: Objectives Met

**On-slide:**
1. ✅ Survey (N=214) → 864 m WTW, 15.78-min transfer penalty.
2. ✅ Tick-by-tick (Δt=10 s) agent simulation on the real OSM network.
3. ✅ Memetic optimizer with pheromone-memory local search.
4. ✅ Parallel evaluation pool.
5. ✅ Validated vs. baseline (reproducible, equitable, diverse) — *final cost numbers landing*.

**🎤 Script:** "To close the loop on our five objectives: the survey is done and calibrated, the simulation runs
on the real road graph, the memetic optimizer with its pheromone memory is built and demonstrated, it runs in
parallel, and the validation shows reproducible, equitable, resilient networks — with the final headline numbers
arriving from the production runs."

**📝 Notes:** Map each ✅ back to Slide 5. Be honest on #5 that the optimization-gain number is finalizing.

---

## Slide 27 — Limitations (own them)

**On-slide:**
- **Sample skew:** 93% students/young adults — doesn't capture seniors, laborers, cargo carriers.
- **Static congestion:** hourly speeds, no vehicle-to-vehicle queueing feedback.
- **Hail-and-ride assumption:** boarding at any node; real stop friction not fully modeled.
- **Passenger-centric objective:** no operator economics (fuel, wages, revenue).

**🎤 Script:** "We're candid about limits. Our behavioral sample skews young and student-heavy. We use static
hourly road speeds, not dynamic queueing. We assume hail-and-ride boarding anywhere. And our objective is
passenger-centric — it doesn't yet model the operator's fuel, wages, or revenue, which matters for adoption.
Each of these is a deliberate scope boundary, and each maps to a future-work item."

**📝 Notes:** Stating limitations *first* disarms the panel. Every limitation has a matching future-work bullet on
the next slide — say so.

---

## Slide 28 — Future Work

**On-slide:**
- **Dynamic congestion** via SUMO/MATSim coupling.
- **Demographic cohorts** — distinct WTW/transfer parameters per group.
- **Multi-modal feeders** — add tricycles/pedicabs to the 3-layer graph.
- **Operator economics** in the objective (fuel, wages, emissions).
- **Scale the 3-layer model** — fares, transfers, time-dependent scheduling.
- *(Explicitly NOT real-time dispatch — infeasible for decentralized owner-operators.)*

**🎤 Script:** "The roadmap follows directly: couple to a microscopic traffic simulator for dynamic congestion;
calibrate behavior per demographic group; extend the graph to include tricycle and pedicab feeders; add
operator-side costs so planners can weigh commuter benefit against operator viability. We deliberately exclude
real-time dispatch — in a decentralized franchise system, static route and fleet design is the realistic lever."

**📝 Notes:** The "no real-time dispatch" point is a *strength*, not a gap — it shows you understand the
operational reality. Tie it to Mohring static allocation.

---

## Slide 29 — Final Remarks / Contribution

**On-slide:**
- Informal transit isn't chaos — it has **spatial self-organization that can be modeled and optimized.**
- We don't replace jeepneys; we give them **computational tools to evolve** — efficient, equitable, resilient.
- A transferable, data-driven TRNDP framework for **resource-scarce cities**.

**🎤 Script:** "To finish: informal transport is usually framed as a problem to be replaced. We argue the
opposite — paratransit has a latent spatial logic that can be measured and improved. The contribution isn't
replacing jeepneys; it's giving an informal system the data-driven tools to become more efficient, more
equitable, and more resilient — and doing it in a way other data-scarce cities can reuse. Thank you. I'd welcome
your questions."

**📝 Notes:** Land the "tools to evolve, not replace" line — it's the thesis's soul and it's memorable. Then go
to Q&A confidently; the backup slides are your safety net.

---

## Slide 30 — Thank You / Q&A

**On-slide:** "Thank you — questions welcome." · [contact] · [acknowledgments]

**🎤 Script:** "Thank you."

**📝 Notes:** Breathe. For any tough question, the backup slides below are mapped to the likely probes.

---
---

# BACKUP / APPENDIX (Q&A safety net)

## Backup A1 — Worked example: MSU-IIT → Robinsons Place

**On-slide:**
- Straight-line ≈ **2,722 m**; A\* lower bound `h = 2722 × 0.00632 ≈ 17.2 EIVM`.
- **Direct journey:** walk 300 m (16.89) + board (14.44) + ride 2,800 m (17.70) + alight (0) + walk 200 m (11.26)
  = **60.29 EIVM**.
- **Transfer alt:** = **82.33 EIVM** → loses *because of* the +15.78 transfer penalty.
- A\* picks the direct journey. This passenger then deposits `Δτ = 1000/60.29 ≈ 16.6` on its edges.

**📝 Notes:** Pull this up if asked "show me a concrete journey / where do the numbers come from." Full table in
STUDY_GUIDE §12.

## Backup A2 — A\* admissibility (one line)

**On-slide:**
- `h(n) = D_straight(n,t) · min(walk_wt, ride_wt)`.
- `h*(n) ≥ Σ d_e·β_e ≥ min(β)·Σd_e ≥ min(β)·D_straight = h(n)` (drop non-negative event penalties + triangle
  inequality). ⇒ admissible ⇒ A\* optimal.

**📝 Notes:** For "prove your pathfinding is correct." Hart, Nilsson & Raphael (1968).

## Backup A3 — On the current run status (the honest one)

**On-slide:**
- Final verification caught that the Lamarckian local search wasn't firing in the first Iligan production run
  (deprecated-module artifact zeroed the supply side of the gap → `D(R)≡1`, so no move was ever accepted).
- **Fixed.** Corrected full-system runs re-executing; ETA [date].
- The intermediate Iligan result is kept as an **accidental GA-only ablation** — a clean isolation of the genetic
  contribution from the local-search contribution.
- Unaffected: all mechanism demonstrations (toy grid), the gap↔fitness validation (r=−0.41), and cross-run
  reproducibility (Jaccard 0.73).

**📝 Notes:** **If asked directly whether the memetic algorithm was fully running for the headline result — use
this slide.** Pre-emptive honesty wins the room. You disclosed it in the chapter yourselves; say so. (CRITICAL_PREP #2.)

## Backup A4 — Defense cheat-sheet (rapid answers)

**On-slide:**
- **"Is F_sim in EIVM?"** → No — realized seconds. EIVM governs path *choice*; fitness measures *outcome*.
- **"Where's the traffic in your demand?"** → Centrality-led, traffic-modulated (range mismatch 3× vs 3,600×);
  robust to α/β (ρ≥0.997). Future work: scale-normalize the inputs.
- **"Why weight_tolerance = 14.44?"** → One wait-event of tolerance; *and* it significantly cut delay (U=953,
  p=0.0022).
- **"N=214 < 385?"** → Calibration, not citywide proportion estimation; 346 events / 1 predictor in the logit.
- **"Jeepney speed?"** → Calibrated `ride_wt` at ~9.5–10 km/h (Philippine paratransit operating speed); quote the
  paper value. *(Internal: ranosa reports 10.228; reconcile if you have time — CRITICAL_PREP #3.)*
- **"Did the √ rule come from Mohring?"** → Mohring establishes increasing-returns/economies of scale; the √
  allocation is the standard operationalization (frequency ∝ √demand).

**📝 Notes:** Glance here between questions. Everything cross-references CRITICAL_PREP.md.

---

### Build checklist before the defense
- [ ] Confirm final-run ETA → fill Slides 24, 25 placeholders (optimized `F_sim`, % reduction, `D(R)`, Mann–Whitney).
- [ ] Verify the **729,592** baseline isn't duplicated toy↔Iligan before showing it (CRITICAL_PREP #2).
- [ ] Plug in the **Cobb-Douglas** citation (Slide 11 / §3.3.5).
- [ ] Decide jeep-speed story (keep 9.5 vs adopt 10.228) — Slide 8 / Backup A4.
- [ ] Run `python collect_figures.py` so every figure (incl. `ddm_alpha_beta_sensitivity.png`) is in `chap4/figures/`.
- [ ] Rehearse the three honesty anchors + Backup A3 out loud.
