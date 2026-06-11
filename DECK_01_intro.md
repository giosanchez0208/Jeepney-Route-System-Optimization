# DECK 01 — Chapter 1: Research Description
*(★ = spine, narrate fully · detail = skim/jump-to)*

---

## Slide 1 — Title ★
**On-slide:**
- **A Parallel Hybrid Memetic GA–ACO Framework for Optimizing Decentralized Jeepney Route Networks**
- *A Data-Driven TRNDP Approach for Iligan City, Philippines*
- [Authors] · [Program] · [Adviser] · [Panel] · [Date]

**🎤** "Good morning. Our thesis asks a question most transit-optimization tools avoid: how do you redesign an
*informal*, decentralized public transport network — the jeepney system — when there's no schedule, no fixed stops,
and no official demand data? We built a data-driven framework that learns commuter behavior, simulates passengers as
agents, and optimizes whole route systems with a hybrid evolutionary algorithm."

**📝** ~20 s. Don't read the title. Frame: *informal + data-driven + whole-network*.

---

## Slide 2 — Outline ★
**On-slide:** 1) Problem & gap · 2) Objectives & scope · 3) Related literature · 4) Methodology · 5) Results · 6) Conclusion
**🎤** "Here's the path — the problem, our objectives, the literature, the methodology pipeline, results, and conclusions."
**📝** 10 s. Signpost.

---

## Slide 3 — Background: jeepneys & the problem ★
**On-slide:**
- Jeepneys = backbone of Philippine mobility, millions of daily trips.
- But: **overlapping routes, poor stop placement, no coordination** → long commutes, congestion.
- Baguio (2017): load factor **0.84**, utilization **0.95** — high intensity, *no route optimization*.
- Modernization policy focuses on vehicles & fares, **not data-driven route design**.

**🎤** "Jeepneys move millions of people a day, but the route *networks* themselves were never optimized — they grew
organically, so they overlap and leave gaps. The Baguio study shows vehicles running at 84% load and 95% utilization:
intense operation, but no structural optimization. And current modernization policy is about vehicle standards and
fares — nobody is redesigning the route network with data. That's the opening."

**📝** Cite mateo-babiano2020, jica2022, upncts2021b. The Baguio numbers make it concrete — use them.

---

## Slide 4 — This is a TRNDP (formal grounding) ★
**On-slide:**
- The problem is the **Transit Route Network Design Problem (TRNDP)** — a sub-class of the TNDP.
- Inputs: road graph + OD demand. Decide: the spatial set of routes.
- Paratransit twist: **decentralized, hail-and-ride, dynamic boarding** — not the centralized world TRNDP assumes.

**🎤** "We situate this formally. Designing transit routes over a city network is the Transit Route Network Design
Problem — a well-defined, decades-old problem class. What makes ours different is the *paratransit* setting:
decentralized operators, boarding anywhere, strong transfer aversion. So we take a rigorous problem framework and
adapt it to an informal system."

**📝** kepaptsoglou2009, owais2025. Shows the panel you know the field's formal language.

---

## Slide 5 — Why metaheuristics: NP-hardness (detail)
**On-slide:** TRNDP is **combinatorial & NP-hard** — solution space grows exponentially; exact optima are intractable
at city scale → **metaheuristics** are the principled choice → justifies our hybrid Memetic GA–ACO.
**🎤** "Because the problem is NP-hard, exact methods don't scale to a real city — which is exactly why a metaheuristic
is the right tool."
**📝** If asked "why not exact/ILP?" → NP-hardness + the simulation-in-the-loop (no closed form).

---

## Slide 6 — Why agent-based simulation (detail)
**On-slide:** Static assignment assumes equilibrium + homogeneous riders. **ABM** simulates heterogeneous agents →
emergent effects (capacity queues, transfer friction) a static model can't show. Grounded in GIS/OSM.
**🎤** "We evaluate every candidate network by *simulating* passengers, because the effects that matter — full jeepneys,
transfer delays — only emerge from individual interactions."
**📝** mehdizadeh2022, li2025, wozniak2020, boeing2025.

---

## Slide 7 — The behavioral angle (detail)
**On-slide:** Filipino commuters: strong **transfer aversion** + **willingness-to-walk** thresholds (lit. 500–700 m).
Routes must match *real* decisions, not theoretical ideals → we calibrate these from a local survey.
**🎤** "Filipino commuters hate transfers and will only walk so far — and those tolerances vary by city. So we measure
them locally rather than importing values."
**📝** upncts2021b, huang2022, harris2022, ha2023, karesdotter2022.

---

## Slide 8 — Why memetic + Lamarckian + ACO (detail)
**On-slide:** **Memetic** = GA global search + local refinement. **Lamarckian** = local improvements are *inherited*,
not discarded. **ACO** as the local-search operator = pheromone-guided refinement toward high-demand corridors.
**🎤** "Our optimizer is memetic: a genetic algorithm for global search, plus a local search that polishes each
solution — and crucially, those improvements are inherited. The local search is ant-colony-inspired, so it pulls
routes toward where demand actually is."
**📝** ong2004 (memetic/Lamarckian), wu2024/korzen2024 (ACO local search).

---

## Slide 9 — We build on Sanchez (2025) ★
**On-slide:**
- Baseline (Sanchez 2025): grid network, uniform demand, GRASP → 15–25% commute reductions (proof-of-concept).
- We extend with: (1) **survey-calibrated behavior**, (2) **Memetic GA–ACO** w/ inherited local refinement,
  (3) **real multi-route system** w/ capacity, (4) **real Iligan geography & demand**.

**🎤** "We don't start from scratch — we directly extend Sanchez 2025, which proved the concept on a grid with uniform
demand using a simpler search. We upgrade four things: behavior is now calibrated from a survey, the optimizer is a
memetic GA–ACO with inherited learning, the system is a real multi-route network with capacity, and it runs on the
actual Iligan road graph. That's the jump from proof-of-concept to an operationally grounded system."

**📝** This lineage slide matters — the panel will anchor on "what did *you* add?" Have the four points crisp.

---

## Slide 10 — Statement of the Problem ★
**On-slide:**
- Iligan jeepney routes operate **without systematic, data-driven optimization** → overlap, inefficient flows, long
  commutes, congestion.
- And they are **never evaluated against actual commuter behavior**.
- → We address both via behavioral simulation + route optimization.

**🎤** "Stated plainly: Iligan's jeepney routes were never optimized with data, and they've never been checked against
how people actually travel. Our work closes both gaps at once — we simulate real behavior, and we optimize against it."

**📝** Keep it to two sentences. This is the thesis's reason to exist.

---

## Slide 11 — General Objective ★
**On-slide:**
- Design, implement & evaluate a **parallelized hybrid Memetic GA–ACO agent-based optimizer** that minimizes
  **Total User Cost** (travel + waiting + transfer, under capacity limits + fleet equity) for multi-route jeepney
  networks, applied to Iligan City.

**🎤** "Our general objective ties it together: build and evaluate a parallel memetic GA–ACO that minimizes Total User
Cost — travel, waiting, and transfer penalties, under capacity and equity constraints — on Iligan's network."

**📝** "Total User Cost" is the north star — it recurs in every chapter. Define it once, here.

---

## Slide 12 — Specific Objectives (the 5) ★
**On-slide:**
1. **Survey** Iligan commuters → WTW, transfer aversion, mode preference.
2. **Agent-based simulation** of walk/wait/ride/alight on OSM streets.
3. **Memetic GA–ACO** optimizer with pheromone-based local refinement.
4. **Parallel evaluation** of thousands of route configs.
5. **Benchmark** vs. baseline (commute time, transfers, accessibility, coverage).

**🎤** "Five specific objectives — collect the behavioral data, build the simulation, build the optimizer, parallelize
it, and benchmark the result. The whole talk maps onto these five, and I'll confirm each is met at the end."

**📝** Verbatim from Ch1 §1.3.2. Each results section closes one. Note #5's headline number is finalizing (Appendix A3).

---

## Slide 13 — Scope & Limitations ★
**On-slide:** Deliberately bounded:
- **Static demand** (no modal shift / land-use change) · **Simplified traffic** (no micro-queueing) ·
  **User-centric objective** (no operator economics) · **Static two-way routes** (no one-way / real-time dispatch) ·
  **Hail-and-ride** (no physical stops/safety) · **System-level** evaluation. Fleet fixed, capacity 16.

**🎤** "We're explicit about the boundaries. Demand is static, congestion is simplified to hourly speeds, the objective
is passenger-centric not operator-centric, routes are static and two-way, boarding is hail-and-ride, and we evaluate at
the whole-network level. These are deliberate scope choices — and every one maps to a future-work item. Importantly,
the cost function is modular, so an operator-cost or safety term can be added later by changing weights."

**📝** Stating limits *up front* disarms the panel. The "modular cost function" line is your escape hatch for "but what
about X?" — answer: "add a term; the architecture supports it."

---

## Slide 14 — Significance (detail)
**On-slide:** **Theoretical:** unifies parallel hybrid metaheuristics + behaviorally-calibrated ABM for informal
transit. **Practical:** a reproducible, data-driven route-planning tool for jeepney networks; transferable to other
data-scarce cities.
**🎤** "The contribution is both methodological — fusing these techniques for informal transit — and practical: a
reusable tool for cities that lack rich transit data."
**📝** Tie to "intelligent transportation systems / scalable combinatorial optimization" for a CS panel.

---

## Slide 15 — Transition (detail)
**On-slide:** *"Before the method — what does the literature already establish, and what's missing?"*
**🎤** "With the problem framed, let me show what the literature establishes — and the specific gap we fill."
**📝** Bridge into Ch2. 5 s.
