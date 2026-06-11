# Thesis Defense — COMPLETE DECK (master index)
### Jeepney Route Network Optimization · Iligan City · Hybrid Memetic GA–ACO

This is the **full, section-by-section defense deck**, one file per chapter, mirroring the paper in order:

| File | Chapter | ~Slides |
|---|---|---|
| `DECK_01_intro.md` | Ch 1 — Research Description (problem, objectives, scope) | ~15 |
| `DECK_02_rrl.md` | Ch 2 — Review of Related Literature (PRISMA, 8 themes, gap) | ~20 |
| `DECK_03_methodology.md` | Ch 3 — Methodology (every subsection) | ~46 |
| `DECK_04_results.md` | Ch 4 — Results & Discussion (every subsection + figure) | ~28 |
| `DECK_05_conclusion.md` | Ch 6 — Conclusions | ~12 |
| **this file** | front matter + appendix/backup + checklist | ~8 |
| **Total** | | **~125** |

> `DEFENSE_PRESENTATION.md` (the earlier 30-slide file) is the **condensed 20-min version** — keep it as a fallback
> for a short slot. This complete deck is the real defense artifact.

---

## How to read every slide

Each `## Slide` has: **On-slide** (the sparse bullets that go on the actual slide), **🎤** (what to say),
**📝** (notes / Q&A / placeholders). Two slide tiers:

- **★ SPINE** — the ~40 slides you actually narrate end-to-end. Full script. Pace these to your time slot.
- **(detail)** — section/figure/derivation slides. Terse one-line script. You *flip past or skim* these live, and
  **jump to them when a panelist probes** ("question on Mohring? — that's the detail slide in §3.5"). They make the
  deck complete and turn every likely question into a slide you can land on.

**The #1 failure mode is reading 125 slides aloud. Don't.** Narrate the spine; let the detail slides be your net.

---

## The SPINE (narrate these — your ~22–28 min path)

`Ch1:` S1 Title · S2 Outline · S1-3 Problem · S1-6 TRNDP/NP-hard · S1-9 Objectives · S1-13 Scope
`Ch2:` S2-1 Why a review · S2-15 The research gap · S2-16 Our integration
`Ch3:` S3-1 Pipeline · S3-2 EIVM · S3-9 CityGraph · S3-14 DDM · S3-19 3-layer graph · S3-24 Simulation ·
S3-28 Fitness · S3-31 Demand-service gap · S3-33 Lamarckian search · S3-36 Hub crossover · S3-38 Epigenetic ·
S3-41 Adaptive control
`Ch4:` S4-1 What we validate · S4-4 DDM robustness · S4-10 Opportunistic riding · S4-12 Gap↔fitness ·
S4-14 Convergence · S4-20 Optimized network ⚠ · S4-24 Commute reduction ⚠
`Ch5:` S5-2 Objectives met · S5-4 Limitations · S5-6 Sanchez evolution · S5-9 Final remarks

---

## Three honesty anchors (true the whole way through — see `CRITICAL_PREP.md`)
1. **`F_sim` is realized seconds, not EIVM.** EIVM governs *path choice*; the fitness measures realized *time-in-system*.
2. **Demand is centrality-led, traffic-modulated** — don't oversell "traffic-aware" (range mismatch 3× vs 3,600×).
3. **The optimization gain is modest (~8% TUC) but consistent and reproducible** — positive in all 9 runs; 7 seeds
   converge to 74%-shared networks (Jaccard 0.74). The value is *reliability + the framework*, not a dramatic single
   number; on a strong demand-weighted baseline, single-digit gains are normal. Use Appendix A3 if pushed on "only 8%?".

---
---

# APPENDIX / BACKUP (Q&A safety net — keep at the end of the built deck)

## Slide A1 — Worked example: MSU-IIT → Robinsons Place (detail)
**On-slide:** Straight-line 2,722 m → A\* bound `2722×0.00632 ≈ 17.2 EIVM`. **Direct** = SW 300 m (16.89) + Wait
(14.44) + Ride 2,800 m (17.70) + Alight (0) + EW 200 m (11.26) = **60.29 EIVM**. **Transfer alt = 82.33** (loses on
the +15.78 penalty). A\* picks direct; passenger deposits `Δτ = 1000/60.29 ≈ 16.6`.
**📝** For "show me a concrete journey." Full table: STUDY_GUIDE §12.

## Slide A2 — A\* admissibility (detail)
**On-slide:** `h = D_straight · min(walk_wt, ride_wt)`. `h* ≥ Σd_e·β_e ≥ min(β)·Σd_e ≥ min(β)·D_straight = h`
(drop ≥0 event penalties + triangle inequality) ⇒ admissible ⇒ optimal. (Hart, Nilsson & Raphael 1968.)
**📝** For "prove your pathfinding is correct."

## Slide A3 — Scope of the reported Iligan optimization (the honest one) ★ if asked
**On-slide:** Verification found the Lamarckian local search did **not** activate in the production Iligan runs (a
deprecated-module artifact left the gap supply-less → `D(R)≡1`, so the acceptance test could never pass). So the
reported Iligan results reflect the **global genetic search** (Hub Crossover + epigenetic inheritance) *without* the
local-exploitation operators. Those three operators are **validated on the toy showcase** (isolated before/after +
gap↔fitness `r=−0.41`). Reproducibility (Jaccard 0.73), temporal robustness, equity, and resilience characterize the
converged topologies directly and are **unaffected**.
**📝** **Use this the instant a panelist asks whether the memetic algorithm fully ran for the headline result.** Frame
it as a *stated scope*, not a defect: the global search works and is reproducible; the local operators are proven on
the controlled grid. You disclosed it in Ch4 — owning it wins the room. (CRITICAL_PREP #2.) *Do not* say "re-running" —
the runs are frozen.

## Slide A4 — Rapid-answer cheat sheet (detail)
**On-slide:**
- *F_sim units?* → realized seconds; EIVM drives path choice.
- *Where's the traffic in demand?* → centrality-led, traffic-modulated; robust to α/β (ρ≥0.997). Scale-normalize = future work.
- *weight_tolerance 14.44?* → one wait-event of tolerance; cut delay U=953, p=0.0022.
- *N=214 < 385?* → calibration, not citywide proportion estimation; 346 events / 1 predictor.
- *Jeepney speed?* → ~9.5–10 km/h Philippine operating speed (quote paper). *(Internal: ranosa = 10.228; CRITICAL_PREP #3.)*
- *√ rule = Mohring?* → Mohring = economies of scale; √ is the standard operationalization (freq ∝ √demand).
- *Fitness α (equity) / β (penalty) calibrated?* → No — they're penalty/trade-off weights, not data-calibrated.
  `β=2.0` only needs `β>1` so an incomplete trip is strictly costlier than completing (prevents the optimizer stranding
  passengers). `α=0.5` is a *light regularizer* (~0.06% of fitness) — the tail compression comes from total-cost
  minimization, not the equity term. Honest framing in §3.5.7 / §4.5.4.
**📝** Glance here between questions. Everything maps to `CRITICAL_PREP.md`.

---

## Build checklist before the defense
- [ ] Fill run placeholders (S4-20, S4-24): optimized `F_sim`, % reduction, `D(R)`, Mann–Whitney U/p, box-plots.
- [ ] Verify the **729,592** baseline isn't duplicated toy↔Iligan (CRITICAL_PREP #2).
- [ ] Plug in the **Cobb-Douglas** citation (Methodology DDM slide / §3.3.5).
- [ ] Decide jeep-speed story (9.5 vs 10.228) — CRITICAL_PREP #3.
- [ ] `python collect_figures.py` so every figure (incl. `ddm_alpha_beta_sensitivity.png`) lands in `chap4/figures/`.
- [ ] Print the SPINE list above; rehearse to your time slot; rehearse Appendix A3 + the 3 honesty anchors aloud.
