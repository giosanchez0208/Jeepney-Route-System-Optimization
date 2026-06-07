# Chapter 4 Numbers — reference

Single source of truth for the statistics, initial conditions, and run results behind Chapter 4.
Last updated 2026-06-06. Each entry notes its **source**: `Ch3`/`Ch4` = stated in the `.tex`
(author-written); `computed` = produced by a script in this repo; `config` = from a YAML.

> ⚠️ Read the **Known issues** section at the bottom before citing any *demand-service gap* number.
> The optimizer telemetry's gap is supply-less; use the corrected `D(R)` values recorded here.

---

## Production configuration — final Iligan runs (`configs/profile_p1.yaml`)
| Knob | Value | Source |
|---|---|---|
| `num_routes` | 38 | config |
| `total_allocatable_jeeps` | 2000 | config |
| `mohring_sample_size` | 2000 | config (calibrated, §4.3.1) |
| `num_ticks` | 540 (= 90 min at 10 s/tick) | config (calibrated, §4.3.3) |
| `seconds_per_tick` | 10 | config |
| `spawn_rate_per_hour` | 600 | config (calibrated, §4.3.3) |
| `weight_tolerance` | 14.44 EIVM | config (= `wait_wt`) |
| `walk_wt` | 0.0563 EIVM/m | config (was a 10× typo 0.563, fixed) |
| Runs | 9 total: p1–p7 = identical config, seeds 1–7 (reproducibility); p8_1pm, p9_5pm = swap `ddm_pkl` (temporal robustness) | run plan |

## Calibrated travel-cost parameters (Ch3, survey-derived, in EIVM)
| Param | Value | Note | Source |
|---|---|---|---|
| `walk_wt` | 0.05630 EIVM/m | θ_walk 4.05 EIVM/min ÷ 72 m/min | Ch3 §3.1.4 |
| `ride_wt` | 0.00632 EIVM/m | 1 ÷ 158.33 m/min (jeep 9.5 km/h) | Ch3 §3.1.4 |
| `wait_wt` | 14.44 EIVM/event | mean wait 7.22 min × θ_wait 2.0 | Ch3 §3.1.4 |
| `transfer_wt` | 15.78 EIVM/event | logistic 50% threshold S\* = −α/β | Ch3 §3.1.4 |
| `direct_wt`, `alight_wt` | 0.00 | structural connectors (no double-count) | Ch3 §3.1.4 |
| Logistic transfer model | α = −2.1242, β = 0.1346 min⁻¹ → S\* ≈ 15.78 min | 856 binary obs, 346 acceptances | Ch3 §3.1.4 |
| Survey N | 214 valid responses (93% aged 18–24; 93.5% students) | Cochran target 385; achieved ≈ ±6.7% | Ch3 §3.1.3 |
| Baseline speeds | walk 1.2 m/s (72 m/min); jeep 9.5 km/h (158.33 m/min) | | Ch3 §3.1.4 |
| 85th-pct walking tolerance | 864 m (12 min) | access-radius reference only | Ch3 §3.1.4 |

---

## §4.1 — Environment & Demand
| Quantity | Value | Source |
|---|---|---|
| Bounding box | [8.1500, 8.3300, 124.1500, 124.4000] (min_lat,max_lat,min_lon,max_lon) | Ch4 §4.1 |
| CityGraph nodes | 36,866 | Ch4 §4.1 |
| CityGraph directed edges | 76,310 | Ch4 §4.1 |
| Non-drivable (pruned) | 50,286 (65.9%) | Ch4 §4.1 |
| Drivable arterial edges | 26,024 (34.1%) | Ch4 §4.1 |
| Pre-imputed TomTom centroids | 381 (centrality-weighted reservoir sample) | Ch4 §4.1 |
| OD demand score | P_i = W_i^α · C_i^β (IDW traffic × betweenness centrality) | Ch3 §3.3 / Ch4 §4.1 |
| IDW traffic weight 08:00 | mean 1.188, max 3.013 | Ch4 §4.1 |
| IDW traffic weight 13:00 | mean 1.132, max 2.547 | Ch4 §4.1 |
| IDW traffic weight 17:00 | mean 1.228, max 3.164 | Ch4 §4.1 |

## §4.3.1 — Mohring fleet-allocation stability (38 routes, fleet 2000)
| Quantity | Value | Source |
|---|---|---|
| Mean per-route allocation CV | 0.21 (500 samples) → 0.11 (2000 samples) | Ch4 §4.3.1 |
| Max per-route CV (worst-served route) | ≈ 0.69 (residual; integer rounding on a marginal route) | Ch4 §4.3.1 |
| Journeys using a transit route | 94% (not walk-only → low mean CV is real) | Ch4 §4.3.1 |
| Production sample size | 2000 (mean & worst-case CV both minimized) | Ch4 §4.3.1 |
| Smaller systems hit CV ≤ 0.5 by | 4 routes: 150; 8: 50; 16: 300; 32: 450 samples | Ch4 §4.3.1 |

## §4.3.3 — Simulation horizon & demand volume
| Quantity | Value | Source |
|---|---|---|
| Production horizon | `num_ticks` = 540 (90 min at Δt = 10 s) | Ch4 §4.3.3 |
| Production spawn rate | 600 pax/hr (smallest rate putting 5-route CV < 5%) | Ch4 §4.3.3 |
| 5-route F_sim CV | 0.076 at 250 pax/hr → < 5% beyond ~550–600 pax/hr | Ch4 §4.3.3 |
| 10-route F_sim CV | < 5% by 500 pax/hr | Ch4 §4.3.3 |
| Δt (time step) | 10 s (sub-tick rounding unbiased; no standalone sweep) | Ch4 §4.3.2 |

## §4.3.4 — Opportunistic riding / weight tolerance (Mann–Whitney U, one-sided)
| Tolerance δ | Group A median Δt | Group B median Δt | U | p | Opportunistic share |
|---|---|---|---|---|---|
| 0 EIVM | 6.47 min (baseline; no alternatives) | — | — | — | 0% |
| 14.44 EIVM (production) | 6.71 min | 0.70 min | 953 | 0.0022 | ~0.7% (6 of 895) |
| 100 EIVM | 6.28 min | 4.36 min | 20,275 | 0.037 | ~6% (57) |
- Δt = T_actual − T_expected (realized delay vs friction-free walk+ride). Both positive tolerances reject H₀ at p < 0.05.
- Source: Ch4 §4.3.4.

## §4.3.6 — Lamarckian operator mechanics (toy showcase)
| Quantity | Value | Source |
|---|---|---|
| Gap–vs–fitness Pearson r (toy scatter) | _record from `nb_4_3_6_lamarckian.ipynb` output_ | TODO |
| Operator firing | attraction fires only with a positive-gap corridor (~1 in 6 systems); pruning/repulsion fire broadly | Ch4 §4.3.6 / HANDOFF |

---

## §4.4 — Optimization mechanics (toy showcase run)
**Run:** `outputs/opt_20260606_174038` · Manhattan toy (50×50 grid) · Gaussian "real-city" demand
(CBD + Port, `configs/toy_city_memetic.yaml`) · 20 generations logged (gen 2–21, converged at gen 11).

**Run config** (`config`): num_routes 10 · pop 20 · g_max 30 · fleet 100 · num_ticks 540 · spt 10 ·
spawn 600 · weight_tol 14.44 · telemetry every generation.

| Quantity | Value | Source |
|---|---|---|
| Best-fitness improvement generations | 2, 3, 4, 5, 6, 11 | computed (`history.csv`) |
| `F_sim` within-run (first snapshot → converged) | 663,842 → 614,660 (−7.4%) | computed (`history.csv`) |
| **`F_sim` vs random baseline** (re-sim, n=5 base / n=3 opt) | **729,592 → 635,768 (−12.9%)** | computed (`scratch/_compute_dr.py`) |
| **Real demand-service disparity `D(R)=Σ\|P−S\|`** (even-split supply, fresh single-sim pheromone) | **baseline 0.591 ±0.033 → optimized 0.490 ±0.009 (−17.1%)** | computed (`scratch/_compute_dr.py`) |
| Completed passengers / run (~600 pax/hr, 540 ticks) | ~750–780 | computed |

> The figures' on-screen gap numbers (chokepoint sum 1.41 → 0.85, "−39.8%") are the **supply-less**
> demand concentration, **not** `D(R)`. Cite the corrected `D(R)` above (−17.1%) for the real gap.

---

## Issues & Verification Status (Updated 2026-06-07)
1. **Demand-service gap is supply-less in the optimizer (RESOLVED):** Chromosome `allocation` is now populated by executing `allocate_by_mohring` during population evaluation, propagating the dynamic fleet count to the gap calculator. Pheromone updates and Lamarckian mutation acceptance now operate on the correct proportional demand-service gap.
2. **Lamarckian local search is inert (RESOLVED):** With the supply-less gap bug fixed, the disparity metric $D(R)$ is route-dependent and dynamic. The Lamarckian local-search moves are successfully accepted or reverted based on a real improvement signal.
3. **Mohring vs even-split (RESOLVED):** Verified that `simulation.py` allocates the active fleet using `FleetAllocator.allocate_by_mohring` across the routes rather than an even split.
4. **Toy run, not Iligan:** Note that §4.4 numbers are from the toy showcase. The production runs on Iligan City (38 routes, fleet 2000, 9 profiles) will be evaluated using `opt_eval.py` once the final runs complete.

