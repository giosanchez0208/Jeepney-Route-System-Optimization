"""
rnd1_diag.py - Tiny-scale diagnostic for rnd_1_ticks_and_rate.ipynb crash.

Tests the FIXED code path using persistent worker pool.
Workers initialize CityGraph + DDM ONCE instead of every call.

Run: python rnd1_diag.py
"""

import os, sys, time, gc, random, traceback
import numpy as np


def compute_cv(scores):
    if len(scores) < 2:
        return 1.0
    arr = np.array(scores, dtype=float)
    m = arr.mean()
    return (arr.std(ddof=1) / m) if m > 1e-9 else 1.0


class MockJS:
    def __init__(self, routes):
        self.routes = routes


# ── TINY PARAMETERS ──
ROUTE_COUNTS     = [3]
PAX_PER_ROUTE_HR = [150]
REPLICATIONS     = 3
JEEPS_PER_ROUTE  = 5
SPT_VALUES       = [10]
SWEEP_SIM_S      = 1200
BISECT_BOUNDS    = (50, 200)
CV_THRESHOLD     = 0.05

cg_pkl = "rnd/pkl/profile_p1.pkl"
ddm_pkl = "rnd/pkl/ddm_8am.pkl"


def evaluate_cv_persistent(routes, spt, num_ticks, total_pass_rate, ddm, runner):
    """Uses a persistent runner - workers stay alive across calls."""
    from utils_simplified import (
        generate_dummy_yaml, SimEnvironment, run_simulations_with_runner
    )

    n_jeeps = len(routes) * JEEPS_PER_ROUTE
    yaml_path = f"rnd/configs/_diag_s{spt}_t{num_ticks}_r{len(routes)}_p{int(total_pass_rate)}.yaml"

    generate_dummy_yaml(
        yaml_path,
        **{
            "simulation.seconds_per_tick":        spt,
            "simulation.num_ticks":               num_ticks,
            "simulation.spawn_rate_per_hour":     total_pass_rate,
            "simulation.total_allocatable_jeeps": n_jeeps,
            "cg_pkl": cg_pkl,
            "ddm_pkl": ddm_pkl,
        }
    )

    envs = [
        SimEnvironment(
            tg=None, yaml_file=yaml_path,
            jeep_system=MockJS(routes), sampler=ddm,
            delete_yaml_when_done=(i == REPLICATIONS - 1)
        )
        for i in range(REPLICATIONS)
    ]

    results = run_simulations_with_runner(runner, envs)
    scores = [r.score for r in results if r is not None]
    cv = compute_cv(scores)

    del envs, results
    return cv, np.mean(scores) if scores else float('nan'), scores


def main():
    sys.path.insert(0, os.getcwd())
    random.seed(42)
    np.random.seed(42)

    from utils_simplified import (
        reuse_citygraph, reuse_ddm, generate_route_system,
        generate_dummy_yaml, create_persistent_runner
    )

    # ── LOAD HEAVY OBJECTS ──
    print("=" * 60)
    print("RND1 DIAGNOSTIC (PERSISTENT POOL) - Loading...")
    t0 = time.time()
    G_city = reuse_citygraph(cg_pkl)
    ddm = reuse_ddm(ddm_pkl)
    print(f"  Loaded in {time.time()-t0:.1f}s | {len(G_city.nodes)} nodes, {len(G_city.graph)} edges")

    os.makedirs("rnd/csv", exist_ok=True)
    os.makedirs("rnd/configs", exist_ok=True)

    print(f"\nDiagnostic config:")
    print(f"  Route counts:  {ROUTE_COUNTS}")
    print(f"  Densities:     {PAX_PER_ROUTE_HR}")
    print(f"  Replications:  {REPLICATIONS}")
    print(f"  SPT sweep:     {SPT_VALUES}")
    print(f"  Bisect bounds: {BISECT_BOUNDS}")
    print(f"  Sweep sim:     {SWEEP_SIM_S}s")

    # Create a bootstrap YAML for the runner (any valid config works)
    bootstrap_yaml = "rnd/configs/_diag_bootstrap.yaml"
    generate_dummy_yaml(
        bootstrap_yaml,
        **{
            "simulation.seconds_per_tick":        SPT_VALUES[0],
            "simulation.num_ticks":               100,
            "simulation.spawn_rate_per_hour":     150,
            "simulation.total_allocatable_jeeps": 15,
            "cg_pkl": cg_pkl,
            "ddm_pkl": ddm_pkl,
        }
    )

    all_results = []
    total_scenarios = len(ROUTE_COUNTS) * len(PAX_PER_ROUTE_HR)
    scenario_i = 0
    total_eval_calls = 0

    try:
        runner = create_persistent_runner(bootstrap_yaml, max_workers=3)
        runner.open_pool()
        print(f"\n[DIAG] Persistent pool opened. Workers will initialize once.\n")

        for n_routes in ROUTE_COUNTS:
            random.seed(42 + n_routes)
            np.random.seed(42 + n_routes)
            print(f"\n{'='*60}")
            print(f"GENERATING {n_routes} ROUTES...")
            t0 = time.time()
            routes = generate_route_system(n_routes, G_city, ddm)
            print(f"  {n_routes} routes, {sum(len(r.path) for r in routes)} edges, "
                  f"{n_routes*JEEPS_PER_ROUTE} jeeps | {time.time()-t0:.1f}s")

            for pax_density in PAX_PER_ROUTE_HR:
                scenario_i += 1
                total_pass_rate = pax_density * n_routes

                print(f"\n{'-'*50}")
                print(f"SCENARIO {scenario_i}/{total_scenarios}: R={n_routes}, "
                      f"Density={pax_density}/route/hr (Total: {total_pass_rate}/hr)")

                # -- Phase 1: SPT Sweep --
                print(f"  [SPT Sweep] fixed_sim={SWEEP_SIM_S}s")
                optimal_spt = SPT_VALUES[0]

                for spt in SPT_VALUES:
                    num_ticks = max(10, SWEEP_SIM_S // spt)
                    t0 = time.time()
                    total_eval_calls += 1
                    print(f"    [eval #{total_eval_calls}] SPT={spt}s ticks={num_ticks}...")

                    cv, mean_fit, scores = evaluate_cv_persistent(
                        routes, spt, num_ticks, total_pass_rate, ddm, runner
                    )

                    wall = time.time() - t0
                    status = 'PASS' if cv <= CV_THRESHOLD else 'FAIL'
                    print(f"    SPT={spt:3d}s ticks={num_ticks:4d} | "
                          f"CV={cv:.4f} mean={mean_fit:.1f} | {wall:.0f}s | {status}")

                    if cv <= CV_THRESHOLD:
                        optimal_spt = spt
                    else:
                        break

                print(f"  -> Optimal SPT: {optimal_spt}s")

                # -- Phase 2: Bisection --
                print(f"  [Ticks Bisect] spt={optimal_spt}s, range={BISECT_BOUNDS}")
                lo, hi = BISECT_BOUNDS
                optimal_ticks = hi
                cv_history = []
                bi = 0

                while lo <= hi:
                    bi += 1
                    mid = (lo + hi) // 2
                    t0 = time.time()
                    total_eval_calls += 1
                    print(f"    [eval #{total_eval_calls}] bisect iter {bi}: ticks={mid}...")

                    cv, mean_fit, scores = evaluate_cv_persistent(
                        routes, optimal_spt, mid, total_pass_rate, ddm, runner
                    )

                    wall = time.time() - t0
                    status = 'PASS' if cv <= CV_THRESHOLD else 'FAIL'
                    print(f"    iter {bi}: ticks={mid:4d} | "
                          f"CV={cv:.4f} mean={mean_fit:.1f} | {wall:.0f}s | {status}")
                    cv_history.append(cv)

                    if len(cv_history) >= 3:
                        recent = cv_history[-3:]
                        if max(recent) - min(recent) < 0.001 and cv > CV_THRESHOLD:
                            print("    -> [CIRCUIT BREAKER] Variance flatlined.")
                            break

                    if cv <= CV_THRESHOLD:
                        optimal_ticks = mid
                        hi = mid - 1
                    else:
                        lo = mid + 1

                sim_min = (optimal_ticks * optimal_spt) / 60
                print(f"  -> Optimal ticks: {optimal_ticks} ({sim_min:.0f} sim min)")

            del routes
            gc.collect()

        runner.close_pool()

        print(f"\n{'='*60}")
        print(f"DIAGNOSTIC COMPLETE - {total_eval_calls} evaluate calls succeeded")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\n{'!'*60}")
        print(f"DIAGNOSTIC CAUGHT ERROR after {total_eval_calls} evaluate calls:")
        print(f"{'!'*60}")
        traceback.print_exc()
        print(f"\nError type: {type(e).__name__}")
        print(f"Error message: {e}")
        print(f"{'!'*60}")
        # Try to close pool on error
        try:
            runner.close_pool()
        except:
            pass
        sys.exit(1)

    # Cleanup bootstrap yaml
    try:
        os.remove(bootstrap_yaml)
    except OSError:
        pass


if __name__ == '__main__':
    main()
