"""Smoke test for nb_optimization_showcase_iligan.ipynb (Iligan-specific paths).

The shared mechanics are covered by nb_optimization_showcase_tiny_test.py; this exercises the parts
unique to the real-city run: loading the cached CityGraph/DDM, simulating + rendering on the real
network, and the evolution animation rendered from existing production telemetry. Heavier than the toy
test (it loads ~100 MB of pickles and runs a couple of real-city sims) but still a short sanity check.

    ./.venv/Scripts/python.exe nb_optimization_showcase_iligan_tiny_test.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import showcase_optimization as S
from fig_memetic import fig_hub_crossover


def main():
    if not os.path.exists("rnd/pkl/profile_p1.pkl"):
        print("SKIP  cached Iligan CityGraph pickle not present (rnd/pkl/profile_p1.pkl)")
        return

    tmp = tempfile.mkdtemp(prefix="showcase_iligan_tiny_")
    cfg = S.make_config(
        smoke=True, city="iligan", num_routes=3, population=2, fleet=12,
        sim_ticks=24, spawn_rate=200.0, frame_stride=8, frame_size=300, out_dir=tmp,
    )
    assert cfg["city"] == "iligan" and cfg["convergence_mode"] == "existing"

    env = S.setup_env(cfg)                       # loads cached CityGraph + DDM
    assert env["city"] is not None and env["ctx"] is not None

    members = S.build_population(env, cfg)        # real-city route gen + sims
    assert len(members) == 2 and all(m["fsim"] > 0 for m in members), members
    assert os.path.getsize(S.render_population_grid(env, members, "gap", os.path.join(tmp, "gap.png"))) > 0

    _, frames = S.simulate_with_frames(env, members[0]["routes"], cfg)
    assert len(frames) >= 2 and frames[0].size == (cfg["frame_size"], cfg["frame_size"])

    scene = S.build_crossover_scene(env, members, cfg)
    assert len(scene["child"].routes) >= 1
    assert os.path.getsize(fig_hub_crossover(scene, os.path.join(tmp, "05.png"))) > 0

    # the full-optimization views: pick the most dynamic production run + render the evolution animation
    run_dir = S.select_optimization_run(cfg)
    if run_dir:
        gif = S.render_evolution_animation(run_dir, os.path.join(tmp, "evolution.gif"),
                                           max_frames=3, hold_last=1)
        assert os.path.getsize(gif) > 0
        evo = "ok (%s)" % os.path.basename(run_dir)
    else:
        evo = "skipped (no final_runs_2 telemetry)"

    print("PASS  iligan  candidates=%d  best_F=%.0f  child_F=%.0f  frames=%d  evolution=%s"
          % (len(members), members[0]["fsim"], scene["stats"]["child_fsim"], len(frames), evo))
    print("  artifacts in", tmp)


if __name__ == "__main__":
    main()
