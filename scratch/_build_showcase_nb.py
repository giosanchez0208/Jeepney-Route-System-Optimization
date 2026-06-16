"""Generate the showcase notebooks from showcase_optimization.py (one-time bootstrap).

    nb_optimization_showcase.ipynb          (Manhattan toy -- FULL mechanics walkthrough + the breadth)
    nb_optimization_showcase_iligan.ipynb   (real Iligan -- sim, crossover, 30-gen evolution, outcome)

    ./.venv/Scripts/python.exe scratch/_build_showcase_nb.py
"""
import os
import nbformat as nbf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- shared code ----------
CFG_CODE = """
import showcase_optimization as S
from IPython.display import Image, display

# ── the one knob ──  set smoke=False for slide-quality (slow); keep True to sanity-check fast
cfg = S.make_config(smoke=True, city="{city}")

env = S.setup_env(cfg)
members = S.build_population(env, cfg)   # generate + simulate the candidate route systems
print(f"{{'SMOKE' if cfg['smoke'] else 'FULL'}} {city}  |  {{len(members)}} candidates, "
      f"{{cfg['sim_ticks']}}-tick sims  |  best F_sim = {{members[0]['fsim']:.0f}}  |  -> {{cfg['out_dir']}}/")
"""
BEAT1_CODE = """
_, frames = S.simulate_with_frames(env, members[0]["routes"], cfg)
gif = S.save_gif(frames, S._p(cfg, "01_simulation.gif"), cfg["gif_ms"])
print(f"{len(frames)} frames"); display(Image(gif))
"""
GRID_CODE = """
display(Image(S.render_population_grid(env, members, "{kind}", S._p(cfg, "{out}"), cfg["dpi"])))
"""
CROSS_FULL_CODE = """
from fig_memetic import fig_hub_crossover, fig_pheromone_blend
scene = S.build_crossover_scene(env, members, cfg)
s = scene["stats"]
print(f"child F_sim = {s['child_fsim']:.0f}   (parents {s['A_fsim']:.0f}, {s['B_fsim']:.0f})")
display(Image(fig_hub_crossover(scene, S._p(cfg, "05_hub_crossover.png"))))
display(Image(fig_pheromone_blend(scene, S._p(cfg, "05b_pheromone_blend.png"))))
"""
CROSS_TRIM_CODE = """
from fig_memetic import fig_hub_crossover
scene = S.build_crossover_scene(env, members, cfg)
s = scene["stats"]
print(f"child F_sim = {s['child_fsim']:.0f}   (parents {s['A_fsim']:.0f}, {s['B_fsim']:.0f})")
display(Image(fig_hub_crossover(scene, S._p(cfg, "05_hub_crossover.png"))))
"""
BEAT6_CODE = """
child = scene["child"]
mut = S.apply_obvious_mutation(env, child.routes, child.pheromones, cfg, base_cost=child.cost)
mut["base_cost"] = child.cost
print(f"{mut['op']}: {mut['n_changed']} edges changed   F_sim {child.cost:.0f} -> {mut.get('after_cost', float('nan')):.0f}")
display(Image(S.render_mutation(env, mut, S._p(cfg, "06_local_search.png"), cfg["dpi"])))
"""
OPT_VIEWS_CODE = """
paths = S.run_optimization_views(cfg)    # convergence curve + per-gen storyboard + evolution ANIMATION
if "evolution" in paths:                  # the generation-by-generation animation is the centerpiece
    display(Image(paths["evolution"]))
for k in ("07_convergence", "07b_evolution"):
    if k in paths:
        display(Image(paths[k]))
"""
OUTCOME_CODE = """
# The real Iligan outcome from the production runs (§4.5) -- the defensible headline, not a preview.
for fig in ["chap4/figures/optimized_network_heatmap.png",
            "chap4/figures/convergence_reproducibility.png"]:
    display(Image(fig))
"""

# ---------- shared mechanics markdown (toy) ----------
BEAT2 = r"## Beat 2 — candidate route systems and their fitness" + "\n" + \
        r"The optimizer generates many route systems and scores each by **simulated Total User Cost** ($F_{sim}$, lower is better). These are the raw material the genetic operators recombine."
BEAT3 = r"## Beat 3 — realized demand memory (pheromone $\tau$)" + "\n" + \
        r"Each simulation leaves a **stigmergic pheromone trace** on the edges passengers actually flowed through — the network's realized demand memory. Brighter = more realized travel."
BEAT4 = r"## Beat 4 — demand-service gap" + "\n" + \
        r"Realized demand vs fleet supply gives the **Proportional Demand-Service Gap** ($\Delta = P-S$): red corridors *underserved*, blue *oversupplied*. This signed field steers the local search in Beat 6; $D(R)=\sum|\Delta|$ summarizes the mismatch."
BEAT5 = r"## Beat 5 — Topological Hub Crossover (memetic recombination)" + "\n" + \
        r"The two fittest candidates become parents. The **topological hub** (top-decile pheromone corridors) of the fitter parent is preserved as the child's **trunk** (red); non-conflicting routes from the other parent are grafted on as **feeders** (green), plus a fitness-weighted pheromone blend. We keep the better of the two parent orderings."
BEAT6 = r"## Beat 6 — Lamarckian local search (\"mutation\") at bumped intensity" + "\n" + \
        r"The three operators refine the child along the demand-service gap. At default intensity they barely perturb the network, so we **bump the intensity** (`mut_intensity`) to make the move unmistakable. We run all three and keep the best re-simulated result; touched routes are highlighted."

BEAT1_MD_TOY = r"## Beat 1 — the simulation we are optimizing" + "\n" + \
    r"`Jeep` agents run their loops while `Passenger` agents spawn, walk, wait, board (under capacity) and ride. The number on each jeep is its onboard count; the dashboard tracks live tick / active / done. Captured every *N*-th tick."
PARTB_MD_TOY = r"## Beat 7 — the full optimization (feel the breadth)" + "\n" + \
    r"The beats above are one loop. Here is the **whole run**: a generation-by-generation **animation** — the best network, its realized demand memory $\tau$, its demand-service gap, and the convergence curve (best in red, population mean in blue) all advancing together — plus the per-generation storyboard and the convergence curve." + "\n\n" + \
    r"> **Scale note.** At `smoke=True` the toy run is short, so the animation is brief and nearly flat. Set `smoke=False` for a real multi-generation descent. The Iligan companion animates the **real 30-generation production run** — that is the breadth slide to show."

INTRO_TOY = r"""
# Optimization Showcase — defense preview (Manhattan toy)

A **slide-ready walkthrough of one memetic optimization loop** on the Manhattan toy city, then the
**whole optimization run** — stitched from the pieces the thesis already uses. The grid is deliberately
simple so each mechanism is visually unambiguous. Beats: simulation, candidates + fitness, pheromone,
gap, hub crossover, local search, and finally the full multi-generation evolution.

> A companion notebook, `nb_optimization_showcase_iligan.ipynb`, runs the same pipeline on the **real
> Iligan network** and animates the real 30-generation production run. Use the toy here for **clarity of
> mechanism**; use Iligan for **realism + breadth**. One knob: `smoke=True` (fast) → `smoke=False` (slow).
"""
CLOSING_TOY = r"""
---
### Producing the slide-quality set
Re-run with **`cfg = S.make_config(smoke=False)`** on a strong machine; for a richer Beat-7 evolution bump
`S.make_config(smoke=False, preview_generations=30, preview_population=20)`. Figures save under
`cfg['out_dir']` at `cfg['dpi']`. One-shot: `python showcase_optimization.py --full`.
"""

# ---------- Iligan: sim + crossover + 30-gen evolution + outcome ----------
INTRO_ILIGAN = r"""
# Iligan showcase — the real city, with breadth

The toy notebook teaches the *mechanism*. This one proves the **identical pipeline runs on the real
Iligan City network** (loaded from cached pickles) and shows the **scale** of the optimization — four
slides:

1. **The simulation**, live on the real road network
2. **Topological hub crossover**, on real arterials
3. **The full optimization** — the real ~30-generation run, animated
4. **The optimized network & reproducibility** — the real §4.5 result

> Each section is built to be **one slide**, sized to project cleanly. Visuals export to `cfg['out_dir']/`;
> the outcome figures are your existing paper figures. `smoke=False` for full-res. (The full 7-beat
> mechanics live in the toy notebook.) The setup cell loads the real city and simulates a few candidates.
"""
SLIDE1_ILIGAN = r"""
## Slide 1 — the simulation, live on the real Iligan network
The agent-based engine on Iligan's arterial skeleton: `Jeep` agents (triangles, with onboard counts) run
real corridors; `Passenger` agents spawn from the empirical Direct Demand Model, wait and board under the
capacity limit.

> **PPT:** a ~640 px **square GIF**. On a 16:9 slide, center it with the caption, or place it left with
> 2–3 bullets right (*real OSM network*, *capacity-limited boarding*, *DDM demand*). PowerPoint loops GIFs.
"""
SLIDE2_ILIGAN = r"""
## Slide 2 — Topological Hub Crossover, on real arterials
The fitter parent's **topological hub** (top-decile pheromone corridors — tracing Iligan's main arterial
spine) is preserved as the child's **trunk** (red); the other parent's non-conflicting routes become
**feeders** (green). The child typically out-scores both parents.

> **PPT:** a wide **3-panel band** (parent A → parent B → child); full-width slide, one takeaway bullet —
> *"the high-demand trunk is conserved; complementary coverage is grafted on as feeders."*
"""
SLIDE3_ILIGAN = r"""
## Slide 3 — the full optimization, generation by generation (the breadth)
The **real ~30-generation production run** as an animation: at every generation, the 38-route network,
the realized demand memory $\tau$ concentrating on the busiest corridors, the demand-service gap receding,
and the convergence curve stepping down (best in red ~7% below the start; the population mean in blue is
still exploring). One illustrative run; the cross-run headline is the next slide.

> **PPT:** your **"the scale of what we built" slide** — play the GIF full-screen and narrate one sentence
> per panel. The static storyboard + curve below it are the print-friendly companions.
"""
SLIDE4_ILIGAN = r"""
## Slide 4 — the optimized network & reproducibility (the real result)
The outcome is the **real §4.5 result**, not a preview: the corridor service-intensity map of the
optimized network, then the cross-run reproducibility.

> **PPT:** ideally **two slides** — first the **heat-map** (*"the optimized Iligan network: a
> trunk-and-feeder hierarchy"*), then the **reproducibility panel** (*"~8% lower Total User Cost,
> positive across all 9 runs, mean Jaccard 0.74"*). This cross-run reframe is the defensible headline.
"""
CLOSING_ILIGAN = r"""
---
Slides 1–3 export to `cfg['out_dir']/` (set `smoke=False` for crisper exports); Slide 4 reuses your
existing slide-quality figures under `chap4/figures/`. The Slide-3 animation is rendered from the real
production telemetry in `final_runs_2/`, so it needs no re-run.
"""


def build(city):
    nb = nbf.v4.new_notebook()
    cells = []
    md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))
    code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip("\n")))

    if city == "toy":
        md(INTRO_TOY)
        code(CFG_CODE.format(city=city))
        md(BEAT1_MD_TOY); code(BEAT1_CODE)
        md(BEAT2); code(GRID_CODE.format(kind="routes", out="02_route_systems.png"))
        md(BEAT3); code(GRID_CODE.format(kind="pheromone", out="03_pheromones.png"))
        md(BEAT4); code(GRID_CODE.format(kind="gap", out="04_demand_service_gaps.png"))
        md(BEAT5); code(CROSS_FULL_CODE)
        md(BEAT6); code(BEAT6_CODE)
        md(PARTB_MD_TOY); code(OPT_VIEWS_CODE)
        md(CLOSING_TOY)
        name = "nb_optimization_showcase.ipynb"
    else:  # iligan
        md(INTRO_ILIGAN)
        code(CFG_CODE.format(city=city))
        md(SLIDE1_ILIGAN); code(BEAT1_CODE)
        md(SLIDE2_ILIGAN); code(CROSS_TRIM_CODE)
        md(SLIDE3_ILIGAN); code(OPT_VIEWS_CODE)
        md(SLIDE4_ILIGAN); code(OUTCOME_CODE)
        md(CLOSING_ILIGAN)
        name = "nb_optimization_showcase_iligan.ipynb"

    nb["cells"] = cells
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                      "language_info": {"name": "python"}}
    with open(os.path.join(REPO, name), "w", encoding="utf-8") as f:
        nbf.write(nb, f)
    print("wrote", name, "with", len(cells), "cells")


if __name__ == "__main__":
    build("toy")
    build("iligan")
