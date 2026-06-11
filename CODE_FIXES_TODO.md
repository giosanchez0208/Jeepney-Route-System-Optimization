# Code ↔ Paper Reconciliation — status log

Finalization pass. **The runs are frozen** — the archived `final_runs/p1–p9` (and the Chapter 4 figures derived from
them) were produced by an *earlier* version of the code. The fixes below make the **current code consistent with the
paper** for anyone who uses this repository in the future. Where a fix changes behaviour, future runs will **not**
reproduce the archived artifacts bit-for-bit — this is expected and documented inline.

> Paper is authoritative. Archived results stand as reported. Code now matches the paper's intended methodology.

---

### 1. Jeepney speed — ✅ APPLIED
- **Paper:** `ride_wt` derived from **9.5 km/h** PUJ operating speed (§3.1.4).
- **Was:** `configs/*.yaml → simulation.jeep_speed_kmh: 20.0`.
- **Now:** set to **9.5** in `profile_p1.yaml`, `dummy_nb1.yaml`, `dummy_part3.yaml`, `test_optimizer_fast.yaml`
  (with an inline note that `final_runs/p1–p9` used 20.0). Toy configs left at 40.0 (synthetic; not paper-reported).
- *Effect:* slower jeeps → fewer completions per fixed horizon. Validated end-to-end (sim runs clean).

### 2. Mohring demand `D_r` — edge-COUNT → edge-LENGTH — ✅ APPLIED (+ fixed a latent crash)
- **Paper:** `D_r` = passenger-**distance** (metres ridden on a route's edges), so long corridors weigh proportionally
  more (§3.5.5).
- **Was:** `utils/jeep_system.py → allocate_by_mohring` accumulated `+1.0` per RI edge (edge-count). A half-applied
  refactor had also left a **NameError** (a renamed helper `_get_route_segments_for_cells` defined but the old name
  still called) — `allocate_by_mohring` would have crashed at runtime.
- **Now:** the cached helper returns `(route_idx, ride_metres)` pairs and the accumulator does
  `route_demand[route] += seg_len`. Crash fixed; validated end-to-end.
- *Note:* `allocate_by_mohring_with_trace` (the one-off Mohring-stability diagnostic that produced
  `mohring_stability.png`) is intentionally **left on edge-count** so that figure still matches the paper.

### 3. `idw_power` — ✅ RESOLVED (paper matches code)
- Code hardcodes inverse-square `dist ** 2.0` (p=2) in `direct_demand_sampler.py`; `DDMConfig` has no `idw_power`.
- Paper updated (§3.3.2 / §3.3.5) to state IDW power is fixed at **p=2**. No code change needed.

### 4. Adaptive mutation — ✅ RESOLVED (paper matches code)
- Code (`utils/optimizer_adaptive.py`) uses **one** quadratically-scaled rate (base 0.25 → cap 0.8, `S_limit`=30) +
  three **fixed** local-search probabilities (0.4/0.4/0.6) + linear LS decay.
- Paper §3.7.2 rewritten to match. No code change needed.

### 5. Fitness equity weight `α=0.5` — ⚠ DOCUMENTED, behaviour intentionally UNCHANGED
- **Finding:** the equity term `α·σ` is ~**0.06%** of `F_sim` (Term 1 & 2 are sums over passengers ~1e5–1e6; this is
  α × a single std-dev ~1e2). It is effectively **inert** as an optimization signal; the travel-time-tail compression
  reported in Ch4 is driven by total-user-cost minimization, not this term.
- **Action:** left as-is (changing it changes behaviour → would invalidate the frozen runs). Documented with a comment
  in `utils/simulation.py` and reframed honestly in the paper (§3.5.7 / §4.5.4) and the deck.
- **To make α a genuine equity weight (future, requires re-run):** scale by the completed count, e.g.
  `equity_penalty = alpha_std_penalty * std_commute * n_completed` → at α=0.5 this becomes ≈ `0.5·CV` (~20%) of Term 1.

### Other (paper-side, no code change)
- **Jeepney speed source:** `ranosa2021` reports **10.228 km/h**; paper uses 9.5 (kept — quote the paper value;
  CRITICAL_PREP #3). **Cite-key checks:** Wasserstein PDF is Kolouri/Villani notes (not `debacco2023`); `katsaros2024`
  file is Giannoulaki & Christoforou. **Cobb-Douglas** citation placeholder (`\citep{cobbdouglas}`) in §3.3.5.
- **Ch4 §4.5 WIP box** rewritten from a "corrected runs finish Wednesday" promise into a permanent honest scope note
  (results reflect the global genetic search; local operators validated on the toy showcase).

---
*See `STUDY_GUIDE.md`, `CRITICAL_PREP.md`, and the `DECK_*.md` presentation files.*
