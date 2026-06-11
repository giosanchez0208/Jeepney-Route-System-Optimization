# DECK 05 — Chapter 6: Conclusions
*(★ spine · detail = skim. End strong — this is the part the panel remembers.)*

---

## Slide 5-1 — Summary of the project (detail)
**On-slide:** A complete **data-driven paratransit optimization pipeline**: survey-calibrated behavior → multi-layer
travel graph → DDM demand → agent simulation → parallel **Lamarckian Memetic GA–ACO**. Iligan as testbed.
**🎤** "To summarize: we built an end-to-end pipeline — calibrate behavior, model demand, simulate passengers, and
optimize whole networks with a parallel memetic algorithm — and demonstrated it on the real Iligan network."
**📝** One breath. The detail is in the chapters; this is the recap.

---

## Slide 5-2 — Objectives met ★
**On-slide:**
1. ✅ Survey (N=214) → 864 m WTW, 15.78-min transfer penalty.
2. ✅ Tick-by-tick (Δt=10 s) agent simulation on the real OSM network.
3. ✅ Memetic GA–ACO with pheromone-memory local search + epigenetic inheritance.
4. ✅ Parallel evaluation pool.
5. ✅ Benchmarked vs. baseline — reproducible (Jaccard 0.73), equitable, resilient (entropy 3.2) — *final cost numbers landing.*

**🎤** "Closing the loop on our five objectives: the survey is calibrated, the simulation runs on the real road graph,
the memetic optimizer with its inherited pheromone memory is built and demonstrated, it runs in parallel, and the
validation shows reproducible, equitable, resilient networks — with the final headline numbers arriving from the
production runs."
**📝** Map each ✅ back to Intro Slide 12. Be honest on #5 (Appendix A3).

---

## Slide 5-3 — Key results at a glance (detail)
**On-slide:** Robust (Jaccard 0.73, Wasserstein 0.009) · temporally stable backbone (J>0.70) · equitable (compressed
tail) · resilient (entropy 3.2) · opportunistic riding cuts delay (U=953, p=0.0022) · gap↔fitness r=−0.41 · ⚠ commute
−15–20% finalizing.
**🎤** "The evidence in one view — robustness, temporal stability, equity, resilience, a validated behavioral mechanism,
and the headline commute reduction finalizing now."
**📝** A single dashboard slide for the panel to anchor on.

---

## Slide 5-4 — Limitations (own them) ★
**On-slide:**
- **Sample skew** (93% students/young) — misses seniors, laborers, cargo carriers.
- **Static congestion** — hourly speeds, no vehicle-to-vehicle queueing feedback.
- **Hail-and-ride** — boarding anywhere; real stop friction not fully modeled.
- **Passenger-centric objective** — no operator economics yet.

**🎤** "We're candid about the limits. The behavioral sample skews young. We use static hourly speeds, not dynamic
queueing. We assume hail-and-ride boarding. And the objective is passenger-centric — it doesn't yet model operator fuel
or wages. Each is a deliberate scope boundary, and — importantly — the cost function is modular, so each maps directly
to a future-work extension."
**📝** Stating limits proactively disarms the panel. Lead with these *before* future work.

---

## Slide 5-5 — Evolution from Sanchez (2025) ★
**On-slide:**
- **GRASP → Lamarckian Memetic search** (global recombination + inherited local refinement vs. single-start greedy).
- **Uniform → data-driven demand** (DDM grounded in traffic + centrality).
- **Grid → real Iligan topology** (capacity limits, boarding delays, survey-calibrated parameters).

**🎤** "It's worth stating exactly how we advanced the baseline. Sanchez 2025 used a greedy single-start search on a grid
with uniform demand — a proof of concept. We replace the search with a memetic algorithm that recombines globally and
inherits local improvements; we replace uniform demand with a data-driven model; and we move from a grid to the real
Iligan road network with real constraints. That's the jump from concept to an operationally grounded system."
**📝** This is your 'what did *you* contribute' slide — the panel weighs novelty here. Three crisp upgrades.

---

## Slide 5-6 — Future work (detail)
**On-slide:**
- **Dynamic congestion** (SUMO/MATSim coupling).
- **Demographic cohorts** (per-group WTW/transfer parameters).
- **Multi-modal feeders** (tricycles/pedicabs in the 3-layer graph).
- **Operator economics** in the objective (fuel, wages, emissions).
- **Scale the 3-layer model** (fares, transfers, time-dependent scheduling).

**🎤** "The roadmap follows directly from the limitations: couple to a traffic microsimulator, calibrate behavior per
demographic group, add tricycle and pedicab feeders, fold in operator costs, and extend the graph to fares and
scheduling."
**📝** Each bullet pairs with a limitation on Slide 5-4 — say so.

---

## Slide 5-7 — Why NOT real-time dispatch (detail)
**On-slide:** Deliberately excluded: decentralized owner-operator franchises follow pre-assigned routes, not central
dispatch. **Static route + Mohring fleet allocation** is the realistic lever.
**🎤** "One thing we deliberately exclude is real-time dispatch — it's infeasible for independent owner-operators. Static
route and fleet design is the lever that actually fits this system."
**📝** This is a *strength* (operational realism), not a gap. Pre-empts "why not dynamic routing?"

---

## Slide 5-8 — Contribution to computer science (detail)
**On-slide:** Unifies **parallel hybrid metaheuristics** + **behaviorally-calibrated ABM** for informal transit; novel
**epigenetic pheromone inheritance** + **gap-gated Lamarckian acceptance**; a reproducible, transferable framework.
**🎤** "On the CS side, the contribution is the unification — parallel hybrid metaheuristics with a behaviorally
calibrated agent model — plus two genuinely novel mechanisms: epigenetic pheromone inheritance and gap-gated local
search."
**📝** For a CS panel, name the *algorithmic* novelty explicitly.

---

## Slide 5-9 — Final remarks ★
**On-slide:**
- Informal transit isn't chaos — it has **spatial self-organization that can be modeled and optimized.**
- We don't replace jeepneys; we give them **the computational tools to evolve** — efficient, equitable, resilient.

**🎤** "To close: informal transport is usually framed as a problem to be replaced. We argue the opposite — paratransit
has a latent spatial logic that can be measured and improved. Our contribution isn't replacing jeepneys; it's giving an
informal system the data-driven tools to become more efficient, more equitable, and more resilient — in a way other
resource-scarce cities can reuse. Thank you. I'd welcome your questions."
**📝** Land the "tools to evolve, not replace" line — it's the thesis's soul and it's memorable. Then breathe and go to
Q&A; the appendix (DECK_00) is your net.

---

## Slide 5-10 — Thank you / Q&A
**On-slide:** "Thank you — questions welcome." · [contact] · [acknowledgments]
**🎤** "Thank you."
**📝** For tough questions: **Appendix A3** (run status), **A4** (rapid answers), and the 3 honesty anchors in DECK_00.
You disclosed your own biggest caveat in the chapter — that earns the room's trust. Defend from strength.
