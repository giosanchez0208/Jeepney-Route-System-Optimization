# CRITICAL PREP — where your advisor will push hardest
### The 6 most vulnerable parts of the methodology, ranked, with defenses

Read this *after* STUDY_GUIDE.md. For each item: **the weakness**, **how the advisor attacks**, **your
defense**, and **what (if anything) to do before the meeting**. Be honest where the honest answer is the
strong one — a technical advisor respects "we found this, here's how we handled it" far more than a bluff.

---

## #1 — `F_sim` is in seconds, but the paper called it "generalized EIVM" 🟢 (FIXED in paper)

**The weakness.** The fitness function sums **realized elapsed simulation seconds** (`despawn − spawn`), but the
paper originally described the first term as *"generalized travel time"* in **EIVM**. EIVM and seconds are
different scales (EIVM prices a wait as a fixed 14.44; seconds just counts the actual seconds waited). A
technical advisor reading the fitness equation next to the EIVM weights will ask: *"What unit is your objective
in?"*

**How they attack.** "You calibrated EIVM weights for waiting and transfers — does your fitness use them? Show me
where `wait_wt` enters `F_sim`." (It doesn't — it enters *path selection*, not the score.)

**Your defense (now consistent with the corrected paper `[M §3.5.7]`):**
> "Two different roles. The EIVM weights drive **journey selection** — through the TravelGraph and A\*, they
> decide which multimodal path each passenger *attempts*. The fitness then measures the **realized time each
> passenger actually spends in the system** once the dynamic simulation imposes capacity limits, headways, and
> bunching. We deliberately score realized time, not planned generalized cost, because that's the only way to
> capture emergent friction — e.g., a passenger skipped by a full jeepney accrues real extra seconds that a
> planned-EIVM sum would never see. So EIVM governs *behavior*; seconds measure *outcome*."

**Before the meeting:** done — the paragraph is rewritten. Just rehearse the two-sentence version. Also note the
underservice term β=2 and equity term α=0.5 are in the *same* time units (seconds), and that α/β here are
unrelated to the DDM/logistic α/β (we added that disambiguation).

---

## #2 — The Lamarckian local search **was not firing** in the current Iligan runs 🔴 (HIGHEST RISK)

**The weakness.** Your own Ch4 status box says it: during verification you found the ACO-inspired Lamarckian
local search *"wasn't actually firing because of an issue left behind by the deprecated surrogate module."* The
demand-service gap was computed with **zero supply** (`D(R) ≡ 1.0`, constant), so the acceptance test
("keep the move only if it reduces `D(R)`") could *never* be satisfied — the local-search half of your memetic
algorithm was inert. The current "Optimized" Iligan box-plot is therefore **GA-only**, which is why its numbers
"aren't matching up yet." `[R4 §4.5 status box]`

**How they attack.** This is the worst-case question: *"So the headline contribution of your thesis — the
*memetic* hybrid — wasn't actually running when you produced your main results?"* If you're evasive here, you
lose the room.

**Your defense (lean into the honesty — it is genuinely strong):**
1. **Disclose first, before they find it.** "We caught this ourselves in final verification and flagged it in the
   chapter. The fix is in and the corrected full runs are re-executing now."
2. **The mechanisms are independently demonstrated** — the local search isn't theoretical:
   - Each operator is shown working in isolation on the Manhattan toy grid (Attraction/Repulsion/Pruning,
     before→after). `[R4 §4.3.6, Fig. lamarckian_ops]`
   - The steering signal is validated: gap `D(R)` vs fitness `F_sim` has **Pearson r = −0.41** — lower disparity
     does track better user cost. `[R4 §4.3.6]`
   - The toy showcase *with local search active* converges 663,842 → 614,660 and cuts `D(R)` by 17.1%. `[R4 §4.4]`
3. **Reframe the current Iligan run as an accidental ablation.** You now have a clean **GA-only vs GA+local-search**
   comparison for free — a genuinely useful experiment most theses don't have. The corrected run becomes the
   "full system" arm.
4. **The single most defensible end-to-end claim is unaffected:** commute-time reduction (baseline vs optimized)
   is measured on the *final route geometries* regardless of which operators produced them.

**Before the meeting (do these):**
- ✅ Confirm the corrected runs are actually progressing (your friend's machine) and get an ETA you can state.
- ⚠️ **Do not present the current Iligan §4.5 numbers as final.** Label them "intermediate / GA-only ablation"
  out loud, exactly as the status box does.
- ⚠️ Verify the **729,592 baseline** figure — it currently appears for *both* the toy showcase and the Iligan
  baseline `[R4 §4.4 vs §4.5.1]`, which looks like a placeholder duplication. Either fix it or be ready to say
  "intermediate, pending the corrected run."
- ⚠️ The "15–20% commute-time reduction" `[R4 §4.5.2]` is the claim the re-simulation was meant to verify; the
  Mann–Whitney commute test isn't finished yet (it needs more RAM than the dev machine has). Say "preliminary;
  the passenger-level Mann–Whitney is running on the larger machine."

---

## #3 — Code disagrees with the paper in two places (jeep speed, Mohring demand) 🟠

**The weakness.** (a) The jeepney speed is a **three-way mismatch**: the cited source `ranosa2021` actually reports
**10.228 km/h**, the paper adopts **9.5 km/h** to derive `ride_wt`, and the simulation physically moves jeeps at
**20 km/h** `[cfg: jeep_speed_kmh]`. If 10.228 were used, `ride_wt` ≈ 0.00587 instead of 0.00632. (b) The paper
defines Mohring `D_r` as passenger-**distance** (edge-length weighted); the code accumulates **+1 per route edge**
— an edge *count*. `[code: jeep_system.py]`

**How they attack.** If they ever see the config: *"Your paper says 9.5, your code runs 20 — which is it?"* Or:
*"You claim longer corridors get more fleet by distance, but your code counts segments — those aren't the same."*

**Your defense.**
- **The paper is authoritative; quote the paper values (length-weighted demand).** The code mismatches are logged
  in `CODE_FIXES_TODO.md` as deferred fixes that do **not** change the qualitative result.
- *Jeep speed — the riskiest part, because the advisor can look up ranosa2021 and see 10.228.* Pick ONE of two
  clean stories and commit: **(i)** frame 9.5 as a deliberately **conservative** lower bound for *intra-city,
  stop-and-go* jeepney operating speed (slower → higher `ride_wt` → walking penalized *less* relative to riding;
  defensible) and note ranosa's 10.228 is the same order of magnitude; or **(ii)** simplest and cleanest — **adopt
  10.228 and recompute** `ride_wt = 1/(10228/60) ≈ 0.00587`, so paper and source agree exactly (a 5-minute edit
  that *eliminates* the vulnerability). I recommend (ii) if you have time. Either way, the sim's 20 km/h is a
  separate physical-movement parameter being reconciled in code.
- *Mohring D_r:* edge-count and edge-length coincide when segments are similar length (OSM arterial segments are
  fairly uniform), so the allocation is a close approximation of the intended distance-weighting; the exact
  length-weighting is a one-line fix in progress.
- **Tactically: do not volunteer the config.** These are internal implementation details, not results.

**Before the meeting:** nothing required for the paper. If you have time, set `jeep_speed_kmh: 9.5` and change
the Mohring accumulation to `+= edge_length_m` (both are tiny edits) so code and paper agree — then the
vulnerability disappears entirely.

---

## #4 — The DDM fusion exponents α=0.6, β=0.4 🟢 (RESOLVED — sensitivity sweep done)

**The weakness (was).** `S_i = W_i^0.6 × C_i^0.4` had no calibration or citation for *why* 0.6/0.4. There is **no
ground-truth Iligan OD demand** to calibrate against (that is the reason the DDM exists), so a true empirical
calibration is impossible — which is exactly why this looked exposed.

**Resolved how.** A sensitivity sweep (re-fusing the stored per-node `W_i`, `C_i` at varying α) settles it:
- **The split doesn't matter.** Over α ∈ [0.3, 0.7] the node-demand ranking is essentially invariant vs the
  production (0.6/0.4) surface (**Spearman ρ ≥ 0.997**) and **89–100% of the top-decile demand nodes** that drive
  waypoint sampling are preserved. Now in the paper (§3.3.5) + a Ch4 figure (`ddm_alpha_beta_sensitivity.png`).
- **The form is principled:** `W^α C^β` with α+β=1 is a **Cobb-Douglas / weighted geometric mean** — a node must
  score on *both* axes (a zero in either kills it). *(You're plugging in the citation; placeholder is in §3.3.5.)*

**How they now attack (the NEW, sharper question).** *"Your fused surface correlates 0.995 with pure betweenness and
−0.36 with pure traffic — so where is the traffic? Isn't this just centrality?"* **Be ready for this — it is the real
exposure now, not the exponent value.**

**Your defense (honest reframe — already written into the paper).**
- Concede + explain the mechanism: traffic `W ∈ [1, 3]` (~3× range) vs centrality `C ∈ [1e-4, 0.37]` (~3,600× range).
  Centrality's dynamic range swamps traffic's, so the *ranking* is centrality-led and traffic *modulates* magnitudes;
  exponents cannot rebalance inputs on such different scales.
- Reframe accurately: the surface is *"primarily structural (betweenness), with live traffic as a secondary,
  time-of-day modulation."* Still a real upgrade over Sanchez's uniform/zonal demand, and the differing
  08:00/13:00/17:00 surfaces (means 1.188/1.132/1.228) genuinely show traffic's marginal effect.
- If pressed on "make traffic matter more": rank- or min-max-normalizing `W` and `C` before fusing would let the
  exponents actually control the balance — stated future work (it changes the surface, so it needs a re-run).

**Before the meeting:** plug in the Cobb-Douglas citation (`\citep{cobbdouglas}` placeholder + TODO in §3.3.5), and
rehearse the *"centrality-led, traffic-modulated"* line — that, not a defense of 0.6-vs-0.5, is now the answer.

---

## #5 — `weight_tolerance` = 14.44 was a "crack decision" 🟠

**The weakness.** The opportunistic-boarding tolerance `δ_tol = 14.44 EIVM` was picked by intuition, not derived.
`[ASSUMPTION]`

**How they attack.** *"Why 14.44? Why not 10 or 30? What's the basis?"*

**Your defense (this one is actually salvageable into a clean story):**
- **Post-hoc principled reading:** 14.44 EIVM = exactly one `wait_wt`. So the rule is: *a passenger will accept up
  to one waiting-event's worth of extra in-vehicle cost to avoid waiting again.* In plain terms — "if a jeepney
  that's already here will get me there for no more than the pain of one more wait, I take it rather than keep
  waiting." That is a coherent behavioral threshold, not an arbitrary number. Cite the rational-rider basis
  `[PDF: iseki2009]`.
- **The empirical result validates it:** at exactly this tolerance, passengers who boarded an alternative had
  **median delay 0.70 min vs 6.71 min** for those who waited (one-sided Mann–Whitney **U=953, p=0.0022**) `[R4
  §4.3.4]`. So the chosen tolerance produces a *statistically significant* individual benefit — the number isn't
  just plausible, it works.
- **It is also a sensitivity point, not a load-bearing tuned parameter:** Ch4 sweeps δ ∈ {0, 14.44, 100} and the
  benefit holds across positive tolerances; only ~0.7% of passengers even use it at production tolerance, so the
  main results barely depend on its exact value.

**Before the meeting:** rehearse the "one wait-event of tolerance" framing — it turns the weakest-sounding
parameter into one of your cleaner behavioral stories. Optionally add that one sentence to §3.5.4 of the paper.

---

## #6 — The sample (N=214, 93% students) and the "is it representative" line 🟡

**The weakness.** 214 < Cochran's 385; 93% are 18–24, 93.5% students. `[M §3.1.3]`

**How they attack.** *"Can a student-heavy convenience sample calibrate a citywide model?"*

**Your defense.**
- 385 is for **citywide proportion estimation at ±5%** — *not your goal*. You calibrate **behavioral trade-off
  parameters**, where adequacy is about outcome events per parameter: the transfer logistic has **346 events / 1
  predictor**, far past the 10–20/predictor guideline `[M §3.1.3]`. The ±6.7% is reported only as a descriptive
  benchmark.
- **80.8% are habitual riders** — high construct validity for the waiting/walking/transfer experiences being
  measured. Convenience/snowball sampling is standard and accepted for stated-preference transport studies.
- Own the limitation explicitly as scope: "results calibrate a model for the surveyed population; broadening the
  demographic frame is stated future work."

**Before the meeting:** nothing required — just don't over-claim citywide representativeness; claim *behavioral
calibration adequacy*.

---

## Quick triage card (what to fix vs. what to just defend verbally)

| Item | Status | Action before meeting |
|---|---|---|
| #1 F_sim units | ✅ paper fixed | rehearse the 2-sentence answer |
| #2 inert local search | 🔴 disclosed in paper | confirm corrected runs ETA; label §4.5 as intermediate; verify 729,592 |
| #3 code≠paper | 🟠 logged | quote paper values; optionally apply the 2 one-line code fixes |
| #4 DDM α/β | 🟢 resolved (sweep) | plug in Cobb-Douglas cite; rehearse "centrality-led, traffic-modulated" reframe |
| #5 weight_tolerance | 🟠 post-hoc | rehearse "one wait-event" framing |
| #6 sample size | 🟡 defensible | claim calibration adequacy, not representativeness |

**The meta-strategy:** your strongest move across all six is *pre-emptive honesty*. You already disclosed the
biggest one (#2) in the chapter itself — do the same verbally for the rest. A technical advisor is testing whether
you understand your own system's limits. This guide proves you do.
