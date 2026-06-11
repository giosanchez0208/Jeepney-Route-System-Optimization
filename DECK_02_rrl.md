# DECK 02 — Chapter 2: Review of Related Literature
*(Mostly **detail** slides — skim live, jump to them on questions. Narrate S2-1, S2-15, S2-16.)*

---

## Slide 2-1 — How we reviewed (PRISMA) ★
**On-slide:**
- Systematic review, **PRISMA 2020**. **71 studies** included from **162** records (Jan 2021 – Nov 2025).
- Three Google Scholar queries + 6 supplementary; 156 screened; 97 excluded on title/abstract; 71 after full-text.
- Six themes: landscape · behavior · modernization · ABM · optimization · hybrid metaheuristics.

**🎤** "Our literature base is a systematic PRISMA review — 71 studies screened from 162. I'll move through six themes,
but the point of the review is to land on one specific gap that nobody has filled. Let me get you there."

**📝** Don't read all 71. Signal rigor (PRISMA), then move. Figure: PRISMA flow + the two tables.

---

## Slide 2-2 — Theme 1: Philippine transport landscape (detail)
**On-slide:** Intersections at Level-of-Service **F** (104 s/veh delay); first/last-mile uncoordinated; tricycles/
e-trikes are de-facto feeders but inefficient. Local sims (LocalSim, VISSIM) show *operational tweaks help but
geometric limits demand network-level redesign*.
**🎤** "The landscape: severe congestion, no first/last-mile coordination, and evidence that tuning signals isn't
enough — you need to redesign the network."
**📝** lim2021/2022, sobisol2025, nacion2022, eden2021, eugenio2023.

---

## Slide 2-3 — Theme 1: socio-economic & environmental drivers (detail)
**On-slide:** PUVs dominate transport energy/emissions; fuel-price shocks hit thin-margin operators & raise poverty;
COVID exposed inequity (essential workers can't shift). → system must be **efficient, equitable, resilient**.
**🎤** "Economic and equity pressures make efficiency urgent — and make equity a first-class objective, not an
afterthought."
**📝** vergel2022, salison2025, tuano2021, roquel2022, ancheta2023, chen2025. (Motivates our equity regularizer.)

---

## Slide 2-4 — Theme 2: passenger behavior — satisfaction (detail)
**On-slide:** Satisfaction ≠ speed alone — reliability, comfort, safety, frequency matter (PUB Mindoro; PH mode choice;
Mexican mototaxis). → fitness must be **multidimensional**.
**🎤** "Riders care about more than raw speed, which is why our cost model prices waiting and transfers, not just
travel time."
**📝** jou2023, mallillin2020, romero-torres2023.

---

## Slide 2-5 — Theme 2: walking, accessibility, inclusivity (detail)
**On-slide:** Walkability depends on distance, topography, safety; access varies by gender/age/mobility → simulation
should model **diverse agent types**, not one generic rider.
**🎤** "Accessibility isn't uniform — which we flag as a limitation, since our current sample skews young."
**📝** ferels2025, gazarin2024, mcginnis2025, macfarlane2021, agramon2024. (Connects to Ch1 scope + future work.)

---

## Slide 2-6 — Theme 2: transfer aversion (the key behavioral parameter) ★
**On-slide:**
- The wait-vs-detour trade-off is **formally modeled** in the literature (Lu 2024); riders have **heterogeneous time
  valuations** (Malichova 2020).
- Transfer aversion *substantially reduces transit utility* — yet prior jeepney work largely **ignores** it.
- → We embed a **survey-calibrated transfer penalty (15.78 EIVM)** directly in routing.

**🎤** "This is the behavioral parameter the field says matters most and prior jeepney studies most often skip: transfer
aversion. We don't skip it — we measure it locally and bake a 15.78-minute-equivalent transfer penalty into the
routing graph. That's a core part of our novelty."

**📝** lu2024 (the gap-defining citation), malichova2020. This slide foreshadows the methodology's transfer_wt.

---

## Slide 2-7 — Theme 2: urban structure & agent flow (detail)
**On-slide:** Monocentric & polycentric structures shape demand hierarchies; optimal networks depend on urban form
→ justifies grounding demand in real spatial structure (our DDM).
**🎤** "Demand follows urban structure, so we ground our demand model in the real city, not a uniform grid."
**📝** zhangb2024, david2022, roth2011, burke2025, sonnenschein2022, fielbaum2016.

---

## Slide 2-8 — Theme 3: modernization — shared/smart mobility (detail)
**On-slide:** Jeepneys can evolve via digital coordination; but Global-South modernization ≠ Western models — it
succeeds only if it **protects operator income** + has credible policy.
**🎤** "Modernization works only if it respects the decentralized, owner-operator reality — which shapes our
static-route, static-fleet design choice."
**📝** seng2023, barlis2022, zeeshan2022/2023, saxena2023.

---

## Slide 2-9 — Theme 3: DRT & ride-pooling (detail)
**On-slide:** Demand-responsive transport / pooling raise occupancy & cut VKT in low-density areas, but need robust
operational strategies. *We adopt the demand-responsiveness as static demand-weighted route+fleet design* (real-time
dispatch is infeasible for decentralized operators).
**🎤** "Demand-responsiveness is the right idea; real-time dispatch is the wrong mechanism here — so we make the
*design* demand-aware instead of the *operation*."
**📝** pavanini2023/2025, zwick2022, shen2024, kim2020, gokay2021. (Reinforces the 'no real-time dispatch' stance.)

---

## Slide 2-10 — Theme 4: ABM in data-scarce settings (detail)
**On-slide:** ABM needs behavioral + spatiotemporal feedback; historically needs big surveys — but recent work builds
ABM from alternative data in data-scarce contexts. Large-scale ABM yields fewer lines / higher frequency / higher
ridership.
**🎤** "Agent-based modeling used to require huge surveys; recent work shows it's feasible in data-scarce cities — which
is our exact context."
**📝** lim2023, elgohary2025 (data-scarce ABM — gap element), manser2020.

---

## Slide 2-11 — Theme 4: simulation dynamics (detail)
**On-slide:** Emergent behavior can't be predicted from aggregated models; validated PH cases (Metro Manila rapid
transit) show crowd×operations dynamics + behavioral fidelity vs smart-card/video data.
**🎤** "Validated agent models reproduce dynamics aggregate models miss — the justification for our simulation-in-the-loop
evaluator."
**📝** chandiramani2025, pan2025, torre2021, koch2020, dytckov2020, liu2025.

---

## Slide 2-12 — Theme 5: optimization & network design (detail)
**On-slide:** Sim-based optimization = the standard **"optimize → simulate → evaluate"** loop (Nnene 2023). Routes as
graph data + logit/Total-User-Cost scoring (Guillermo 2022). Fleet assignment must match demand → motivates **Mohring**.
**🎤** "The field's standard is an optimize-simulate-evaluate loop — which is exactly our architecture — and it says fleet
allocation must track demand, which is why we use Mohring's rule."
**📝** nnene2023 (paradigm), guillermo2022a/b, hatzenbuhler2022, borchers2024.

---

## Slide 2-13 — Theme 6: hybrid GA+ACO (why our solver) ★
**On-slide:**
- GA = global exploration but slow local feedback; ACO = strong local refinement but premature convergence.
- Hybrid **GA+ACO** combines them — empirically **−46–47% iterations**, better solution quality (Shi 2022; Ran 2024).
- Non-standard pheromone tricks validated: **negative learning** (repulsion), **GA mutation inside ACO**,
  **meta-Lamarckian** inheritance (overwrite chromosome with the refined solution).

**🎤** "Our solver choice is evidence-based. Genetic algorithms explore globally but refine slowly; ant colony does the
opposite. Hybridizing them cuts iterations by nearly half and improves quality. And the literature even validates the
*non-standard* moves we use — repulsion via negative pheromone, genetic operators inside the ant loop, and
meta-Lamarckian inheritance where the refined solution overwrites the parent. So every novel-looking mechanism we use
has precedent."

**📝** shi2022 (the 46–47%), ran2024, nurcahyadi2022 (negative learning → our Repulsion operator), chari2012,
zhao2026 (GA-in-ACO), neri2012 (meta-Lamarckian → our inheritance). This is the methodological-legitimacy slide.

---

## Slide 2-14 — Theme 7: why not pure ML / autonomous (detail)
**On-slide:** ML predicts demand within *fixed* networks; can't *generate* new route topologies. Autonomous/robotaxi
needs infrastructure & data Philippine paratransit lacks. → **simulation + metaheuristics** fit a resource-scarce,
human-operated system.
**🎤** "Machine learning predicts within an existing network; we need to *generate* networks that don't exist yet — so a
search-and-simulate approach is the right tool, not ML or robotaxis."
**📝** tran2020, ma2023, joseph2020, meinhardt2025, + autonomous cluster. Pre-empts "why not deep learning?"

---

## Slide 2-15 — Synthesis: the research gap ★
**On-slide:**
- Three validated ingredients exist *separately*: structured/monocentric demand · hybrid GA+ACO efficiency ·
  data-scarce ABM.
- **No study integrates all three** into a parallel framework for **informal paratransit** with **calibrated transfer
  aversion** and a **Total-User-Cost** objective.
- Comparative matrix of 15 studies: mostly aggregate demand, single-heuristic, simplified behavior, *no PH agent-based
  jeepney redesign*.

**🎤** "Here's the gap, and it's the heart of the chapter. The literature has proven each ingredient on its own —
structured demand, hybrid GA-ACO efficiency, and agent-based modeling in data-scarce settings. But no one has *combined*
them into a parallel framework for *informal* paratransit that calibrates transfer aversion and optimizes Total User
Cost. Our comparative matrix of fifteen studies confirms it: they use aggregate demand, single algorithms, simplified
behavior — and not one does agent-based jeepney redesign in a Philippine setting."

**📝** This is the most important RRL slide — the panel judges your novelty here. zhangb2024, shi2022, elgohary2025,
lu2024. Figure: the comparative matrix.

---

## Slide 2-16 — How we close it ★
**On-slide:**
- Couple **empirically-calibrated ABM** + **hybrid GA+ACO** in a **parallel, city-scale** optimize-simulate-evaluate loop.
- Survey-grounded behavior (real WTW + transfer aversion); real Iligan GIS network; Total User Cost as a *testable*
  system-level objective.

**🎤** "We close the gap by uniting all three: a survey-calibrated agent model, a hybrid GA–ACO solver, run in parallel
on the real Iligan network — with Total User Cost as a concrete, testable objective. That integration is what's new."

**📝** Bridge to methodology. End the chapter on *your* contribution, not others' work.
