# DECK 04 — Chapter 4: Results & Discussion
*(★ spine · detail = skim/jump-to · ⚠ PLACEHOLDER = fill from final runs)*

---

## Slide 4-1 — What we validate, and in what order ★
**On-slide:** Bottom-up: **environment** (is the data sound?) → **architecture** (is the machinery valid?) →
**calibration** (are the knobs right?) → **dynamics** (does the optimizer behave?) → **optimized network** (does it
win?).
**🎤** "We build the evidence from the ground up. First we show the environment and demand are sound; then that the
travel-graph and simulation machinery are valid; then that the calibrated knobs are right; then that the optimizer
behaves as designed; and finally the optimized network itself. By the time we get to the headline result, every layer
underneath it has already been verified."
**📝** This framing is your shield: even with the final run pending, the foundation is fully validated.

---

### §4.1 — Environment & Demand

## Slide 4-2 — CityGraph & arterial pruning (detail)
**On-slide:** OSM → **36,866 nodes / 76,310 edges**; arterial filter → **26,024 drivable (34.1%)**; 50,286 (65.9%)
kept for walking. Landmarks aligned (MSU-IIT, Robinsons).
**🎤** "The arterial filter cleanly separates routable corridors from walking-only roads, and the landmarks confirm the
map is geographically aligned."
**📝** `citygraph_comparison.png`.

## Slide 4-3 — DDM topography (detail)
**On-slide:** 381 TomTom centroids → IDW field. Traffic weights: 08h mean **1.188**/max 3.013 · 13h 1.132/2.547 ·
17h **1.228**/3.164. Fusion → a *coherent demand gradient*, not scattered hotspots.
**🎤** "The demand model produces a coherent gradient that concentrates on real centers and shifts sensibly across
morning, midday, and evening."
**📝** `ddm_3maps_comparison.png`, `ddm_time_comparison.png`.

## Slide 4-4 — DDM is robust to its weighting ★
**On-slide:** Sweep α∈[0.3,0.7]: demand ranking **invariant (Spearman ρ≥0.997)**, 89–100% of top-decile demand nodes
preserved. Surface is **centrality-led, traffic-modulated** (W range ~3× vs C ~3,600×).
**🎤** "We stress-tested the demand model. As you vary the traffic-versus-structure weighting across a wide range, the
demand ranking barely moves — correlation above 0.997. So our results don't hinge on a hand-tuned exponent. To be fully
transparent: the ranking is actually led by structural centrality, with live traffic providing a secondary, time-of-day
modulation. We describe it accurately, and it's robust either way."
**📝** ⚠ Anchor #2 — say the centrality-led line yourself. `ddm_alpha_beta_sensitivity.png`. (CRITICAL_PREP #4 resolved.)

---

### §4.2 — Architectural Validation

## Slide 4-5 — Three-layer transitions carry exact costs (detail)
**On-slide:** All six transitions isolated: SW/EW per-metre walk · WA = 14.44 · RI per-metre ride · TR = 15.78 ·
AL = 0. No double-counting.
**🎤** "Each travel-graph transition charges exactly its own calibrated cost — we checked all six in isolation."
**📝** `layer_transition_*.png` (×6).

## Slide 4-6 — A sample journey (detail)
**On-slide:** A traced passenger journey (incl. a transfer): A\* returns the **min-EIVM** path, not min-distance; route
isolation prevents free vehicle-hopping.
**🎤** "A traced journey confirms the pathfinder picks the cheapest path in our cost units, and that overlapping routes
stay operationally separate."
**📝** `passenger_journey_snapshots.png`, `sample_journey_transfer.png`. Worked numbers: Appendix A1.

## Slide 4-7 — Emergent simulation behavior (detail)
**On-slide:** Capacity-limited waiting (full jeepney → you wait) + maintained headways (no early bunching, `S=L/N`) —
exactly the dynamics a static assignment can't represent.
**🎤** "The simulation reproduces the behaviors that justify an agent model: passengers genuinely get left by full
jeepneys, and vehicles hold their spacing instead of clumping."
**📝** `simulation_temporal_snapshots.png`.

---

### §4.3 — Component Calibration

## Slide 4-8 — Mohring allocation is stable (detail)
**On-slide:** Per-route allocation **CV → 0.11** at 2000 samples (from 0.21 at 500); 94% of trips use transit; worst
single route ~0.69 (integer rounding on a marginally-served route, not instability).
**🎤** "The fleet allocation is reproducible — an 11% coefficient of variation across independent demand draws — so it's
a stable basis for the optimizer."
**📝** `mohring_stability.png`. The 0.69 worst-route is defensible (integer allocation on a tiny-fleet route).

## Slide 4-9 — Horizon & volume calibrated by stability (detail)
**On-slide:** Knobs set by **fitness-CV**, not completion: horizon **540 ticks (90 min)**, spawn **600 pax/hr** (5%-CV
ceiling). Continuous arrivals → completion can't hit 100% (a trailing cohort is always mid-trip).
**🎤** "We picked the simulation length and demand volume where the fitness score becomes stable — not by chasing
completion, which can't reach 100% under continuous arrivals."
**📝** `horizon_volume_calibration.png`. Pre-empts "why isn't everyone completing?"

## Slide 4-10 — Opportunistic riding works (a real finding) ★
**On-slide:** Riders who took an acceptable earlier jeepney: median delay **0.70 min** vs **6.71 min** for waiters
(one-sided Mann–Whitney **U=953, p=0.0022**, at δ=14.44). Used by ~0.7% of riders — a small but genuine benefit.
**🎤** "Here's a real, finished statistical result. When we let passengers board a good-enough earlier jeepney instead
of rigidly waiting, the ones who did cut their delay from about 6.7 minutes to under one — a statistically significant
improvement, p equals 0.002. So the model captures rational boarding behavior, not just scripted movement."
**📝** A *completed, defensible* result — lean on it while the optimization headline finalizes. `weight_tolerance_delta.png`.
δ=14.44 ≈ one wait-event (CRITICAL_PREP #5).

## Slide 4-11 — Lamarckian operators, demonstrated (detail)
**On-slide:** Each operator isolated on the toy grid (before→after): Attraction transplants toward demand, Repulsion
reroutes off oversupply, Pruning straightens detours.
**🎤** "Each local-search operator does exactly what it should — shown here in isolation."
**📝** `lamarckian_operators_toy.png`. ⚠ The *mechanisms* are proven here even though the full Iligan run is pending
(Appendix A3).

## Slide 4-12 — The gap signal is meaningful ★
**On-slide:** Demand-service disparity `D(R)` vs simulated fitness `F_sim`: **Pearson r = −0.41** — lower disparity ↔
lower (better) user cost. Moderate (F_sim also captures capacity/equity the gap doesn't), but the right sign & strength.
**🎤** "Before trusting the local search to *steer* by the gap, we checked the gap actually correlates with quality. It
does — about minus 0.4. It's moderate, not perfect, because the full fitness also captures capacity and equity the gap
ignores, but the sign and strength confirm it's a legitimate, cheap steering signal."
**📝** `gap_vs_fitness.png`. Honesty: "moderate but legitimate" — don't oversell.

## Slide 4-13 — Constructing the gap (detail)
**On-slide:** On one route system: DDM prior → route geometry → post-sim pheromone memory → resulting demand-service
gap that steers the operators.
**🎤** "This shows the whole signal being built on one network — from demand prior to the gap the operators follow."
**📝** `memetic_demand_memory_gap.png`.

---

### §4.4 — Evolutionary Dynamics

## Slide 4-14 — Convergence & adaptive control ★
**On-slide:** Toy showcase: best `F_sim` **663,842 → 614,660**; discrete improvements at gens 2–6, 11; mutation rate
spikes on plateaus, resets on each breakthrough — the quadratic schedule made visible.
**🎤** "On a controlled showcase the optimizer converges in clear improvement steps, and you can literally see the
adaptive mutation ramping during plateaus and resetting each time it finds a better network. The mechanism behaves
exactly as designed."
**📝** `opt_convergence.png`. This is where local search is *definitely* active — emphasize.

## Slide 4-15 — Optimization gain (toy) (detail)
**On-slide:** Optimized vs random baseline: Total User Cost **−12.9%** (729,592 → 635,768); demand-service disparity
**−17.1%** (0.591 → 0.490). % reduction is the robust quantity (stochastic re-sim).
**🎤** "Against a random baseline the optimized network cuts user cost by ~13% and the demand-service mismatch by ~17%."
**📝** `opt_evolution.png`. ⚠ verify 729,592 isn't duplicated toy↔Iligan (CRITICAL_PREP #2).

## Slide 4-16 — Hub crossover & lineage (detail)
**On-slide:** Trunk (top-decile pheromone) of fitter parent + non-conflicting feeders of the other → coherent
trunk-and-feeder child. Lineage log confirms fitter parents transmit their core trunk.
**🎤** "Crossover conserves the high-demand trunk of the fitter parent and grafts feeders from the other — and the
lineage log confirms that's what propagates across generations."
**📝** `memetic_hub_crossover.png`.

## Slide 4-17 — Epigenetic inheritance (detail)
**On-slide:** Child's pheromone = fitness-weighted blend of parents' (`w_A=C_B/(C_A+C_B)`); visibly tracks the fitter
parent while keeping a trace of the other (diversity).
**🎤** "And the child inherits a blended demand memory, biased toward the fitter parent — a warm start for its local
search."
**📝** `memetic_pheromone_blend.png`.

## Slide 4-18 — Crossover reshapes the gap (detail)
**On-slide:** Parent A, Parent B, child disparity `D(R)` on a shared scale — shows recombination + inheritance reshaping
the demand–service match in one reproductive event.
**🎤** "You can see the demand-service match itself being reshaped by a single crossover."
**📝** `memetic_gap_change.png`.

## Slide 4-19 — Phenotypic convergence (detail)
**On-slide:** As `F_sim` falls: Jaccard ↑, GED ↓, 2D Wasserstein ↓, fitness variance ↓ — convergence in **both**
decision and objective space → the search homes in, not wanders.
**🎤** "Convergence happens on every axis at once — structure and fitness together — which proves the search is genuinely
homing in on a consistent region."
**📝** (Figure pending in some builds.)

---

### §4.5 — Optimized Network for Iligan City

## Slide 4-20 — The optimized Iligan network ★
**On-slide:**
- **~8% Total User Cost reduction** vs. random baseline (≈2.36M → 2.17M), **positive in all 9 runs**.
- **Reproducible:** mean cross-run **Jaccard 0.74** (7 seeds) → the same robust backbone, seed-independent.
- Clean **corridor service-intensity** view (trunk + feeders) instead of 38 tangled loops.

**🎤** "Now the real city, with the full memetic framework running. The optimizer reduces Total User Cost by about
8% versus the random baseline — and crucially, that gain is positive in *every one* of the nine runs. The seven seeds
converge to networks sharing 74% of their edges, so it's reproducible, not a lucky draw. And here's the network shown
as a corridor service-intensity map: a clear arterial backbone with feeders branching out, rather than a tangle of 38
overlapping loops."
**📝** Honest framing: the gain is **modest but consistent and reproducible** — that's the strength (Appendix A3 if a
panelist pushes "only 8%?"). Figures: `convergence_reproducibility.png`, `optimized_network_heatmap.png`. The
reproducibility (0.74) is your strongest card — lead with it.

## Slide 4-21 — Stochastic baseline (detail)
**On-slide:** No digitized existing network → baseline = cohort of random gen-0 networks under identical conditions.
Baseline mean Total User Cost **729,592 ± 33,000**; `D(R)` **0.591 ± 0.033** (structural demand–service mismatch).
**🎤** "Since Iligan has no digitized baseline route map, we benchmark against a rigorous cohort of randomly-initialized
networks under identical conditions."
**📝** ⚠ verify 729,592 vs toy. Units note: this is realized time, not EIVM (Anchor #1).

## Slide 4-22 — Cross-run robustness (detail)
**On-slide:** Pairwise similarity matrix (7 runs): mean **Jaccard 0.73**, **Wasserstein 0.009** → the optimizer finds
the same backbone regardless of seed.
**🎤** "The seven runs cluster tightly — the optimizer reliably finds the same robust backbone."
**📝** `robustness_reproducibility.png`.

## Slide 4-23 — Temporal robustness (detail)
**On-slide:** Re-optimized at 08/13/17h: trunk **Jaccard > 0.70** across regimes → a **single static backbone** is
viable; feeder tweaks absorb temporal shifts. Justifies static franchise design (no real-time dispatch).
**🎤** "The optimal backbone barely changes between peak and off-peak — which justifies a single static route design,
the only thing decentralized operators can actually run."
**📝** `robustness_temporal.png`. Ties to the 'no real-time dispatch' stance.

## Slide 4-24 — Where the ~8% gain comes from ★
**On-slide:**
- The gain is in **aggregate Total User Cost** — fewer underserved passengers + lower accumulated waiting penalties.
- *Not* a large change in completed-journey in-vehicle time (that's roughly flat).
- Mechanism: consolidating overlap into high-frequency trunks + Mohring fleet-to-demand matching.

**🎤** "To be precise about where the improvement comes from: it's in *aggregate Total User Cost* — the optimized
network serves more passengers and cuts accumulated waiting, rather than dramatically shortening the in-vehicle time of
any single completed trip. The mechanism is consolidating overlapping routes into high-frequency trunks and sizing the
fleet to demand with Mohring's rule."
**📝** Pre-empts "did commute times drop 15–20%?" — **don't claim that; it's not in the final runs.** The honest gain
is ~8% Total User Cost. Rigorous *per-passenger* significance = the opportunistic-riding test (**S4-10**, U=953,
p=0.0022). (CRITICAL_PREP / honest-reframe.)

## Slide 4-25 — Equity (detail)
**On-slide:** Optimized network **compresses the long tail** of extreme commute times (peripheral districts). Driven
**primarily by total-user-cost minimization** (longest journeys cost most → optimized first); the `α·σ` equity term is
a light complementary regularizer.
**🎤** "The optimized network is more equitable — it shrinks the tail of very long commutes. To be precise about the
mechanism: that compression comes mainly from minimizing total user cost, since the longest journeys dominate the cost
sum; the explicit equity term reinforces it as a light regularizer."
**📝** ⚠ Honest framing (the equity term is ~0.06% of fitness — CRITICAL_PREP). `equity_traveltime_hist.png`. If asked
"is the equity term doing the work?" → "it's a light regularizer; the outcome is primarily from total-cost minimization."

## Slide 4-26 — Resilience / path diversity (detail)
**On-slide:** Path-diversity **Shannon entropy ≈ 3.2 bits** → trips spread across multiple routes/transfers; resilient
to localized capacity shocks (a full vehicle → reroute via the multi-layer graph).
**🎤** "And it's resilient — high path diversity means a localized disruption doesn't break the network; passengers have
alternatives."
**📝** levinson2012 (entropy↔resilience). Bridge to conclusions.
