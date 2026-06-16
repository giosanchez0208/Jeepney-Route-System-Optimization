"""Smoke test for nb_optimization_showcase.ipynb / showcase_optimization.py.

Runs the whole pipeline at a deliberately tiny scale (a couple of very short sims + a 2-generation
optimization) so a regression in any building block surfaces in seconds. It does NOT produce
slide-quality output -- that is the notebook's job on a strong machine.

    ./.venv/Scripts/python.exe nb_optimization_showcase_tiny_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import showcase_optimization as S
from fig_memetic import fig_hub_crossover, fig_pheromone_blend


def main():
    tmp = tempfile.mkdtemp(prefix="showcase_tiny_")
    cfg = S.make_config(
        smoke=True, population=2, num_routes=4, fleet=12,
        sim_ticks=24, spawn_rate=120.0, frame_stride=8, frame_size=240,
        preview_generations=2, preview_population=3, out_dir=tmp,
    )
    env = S.setup_env(cfg)

    members = S.build_population(env, cfg)
    assert len(members) == 2 and all(m["fsim"] > 0 for m in members), members
    assert members[0]["fsim"] <= members[1]["fsim"], "not sorted by fitness"
    for kind, name in [("routes", "02"), ("pheromone", "03"), ("gap", "04")]:
        assert os.path.getsize(S.render_population_grid(env, members, kind, os.path.join(tmp, f"{name}.png"))) > 0

    _, frames = S.simulate_with_frames(env, members[0]["routes"], cfg)
    assert len(frames) >= 2 and frames[0].size == (cfg["frame_size"], cfg["frame_size"]), frames[0].size
    assert os.path.getsize(S.save_gif(frames, os.path.join(tmp, "01.gif"), cfg["gif_ms"])) > 0

    scene = S.build_crossover_scene(env, members, cfg)
    assert len(scene["child"].routes) >= 1 and scene["stats"]["child_fsim"] > 0
    assert os.path.getsize(fig_hub_crossover(scene, os.path.join(tmp, "05.png"))) > 0
    assert os.path.getsize(fig_pheromone_blend(scene, os.path.join(tmp, "05b.png"))) > 0

    child = scene["child"]
    mut = S.apply_obvious_mutation(env, child.routes, child.pheromones, cfg, base_cost=child.cost)
    mut["base_cost"] = child.cost
    assert os.path.getsize(S.render_mutation(env, mut, os.path.join(tmp, "06.png"))) > 0

    # the full-optimization views: a short real optimization -> convergence + evolution animation
    run_dir = S.select_optimization_run(cfg)
    try:
        assert os.path.getsize(S.render_convergence(run_dir, cfg)["07_convergence"]) > 0
        gif = S.render_evolution_animation(run_dir, os.path.join(tmp, "evolution.gif"),
                                           max_frames=3, hold_last=1)
        assert os.path.getsize(gif) > 0
    finally:
        import shutil
        shutil.rmtree(run_dir, ignore_errors=True)

    print("PASS  pop=%d  best_F=%.0f  child_F=%.0f  mutation=%s(%d edges)  frames=%d  evolution=ok"
          % (len(members), members[0]["fsim"], scene["stats"]["child_fsim"],
             mut.get("op"), mut.get("n_changed", 0), len(frames)))
    print("  artifacts in", tmp)


if __name__ == "__main__":
    main()
