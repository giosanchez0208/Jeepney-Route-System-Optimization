"""mutator_experiment.py -- find a mutator that more consistently lowers F_sim (evaluate-mutate-evaluate).

The production Lamarckian mutator accepts a move iff it lowers the demand-service PROXY D(R), not
the simulation fitness. This harness tests whether gating on the simulation itself (and a few move
variants) improves the fraction of mutations that actually reduce F_sim.

For each randomly generated toy network we measure F0 (averaged over k sims to suppress the ~noise),
apply each strategy, then measure F1 (again averaged). We report, per strategy, how often F1 < F0
and the mean/median percentage change.

Strategies:
  A proxy_gate      : current behavior. Apply all 3 operators, accept iff D(R) decreases.
  B sim_gate        : apply all 3 operators, accept iff a single re-sim shows F_sim decreases.
  C sim_best_op     : try each operator alone, keep the best single-op move if it beats F0 (by sim).
  D iter_sim_gate   : iterated sim-gated hill-climb (up to 3 accepted rounds, refreshing the gap each time).

    python mutator_experiment.py --bases 6 --k 3
"""
import argparse
import statistics as stats

import numpy as np

CFG = "configs/_mutator_toy.yaml"


def build():
    from utils.optimizer import Optimizer
    from utils.route import RouteGenerator
    from utils.genetic import Chromosome
    from utils.pheromone import PheromoneMatrix
    opt = Optimizer.create(CFG)
    return opt, RouteGenerator, Chromosome, PheromoneMatrix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", type=int, default=6)
    ap.add_argument("--k", type=int, default=3, help="sims averaged per fitness measurement")
    ap.add_argument("--seed", type=int, default=20)
    ap.add_argument("--kg", type=int, default=2, help="sims averaged for the accept gate (robust to noise)")
    ap.add_argument("--N", type=int, default=3, help="candidate moves for best-of-N")
    args = ap.parse_args()

    import random
    random.seed(args.seed); np.random.seed(args.seed)

    opt, RouteGenerator, Chromosome, PheromoneMatrix = build()
    fitness = opt.fitness
    algo = opt.engine.algo
    ls = algo.local_search
    cg, sampler = opt.cg, opt.sampler
    fleet = opt.config.total_allocatable_jeeps
    n_routes = opt.config.num_routes
    rg = RouteGenerator(cg, sampler)
    phero_cfg = {"initial_tau": opt.config.initial_tau, "rho": opt.config.rho,
                 "q": opt.config.q, "default_jeep_weight": opt.config.default_jeep_weight}

    def copy_sys(routes):
        from utils.route import Route
        return [Route(path=r.path[:], city_graph=cg) for r in routes]

    def avg_fit(routes, k):
        return float(np.mean([fitness.evaluate(routes).fitness_score for _ in range(k)]))

    def one_fit(routes):
        return float(fitness.evaluate(routes).fitness_score)

    def make_eval_chrom(routes):
        ch = Chromosome(routes=routes, allocation={},
                        pheromones=PheromoneMatrix(all_edges=cg.graph, config=phero_cfg), generation=0)
        algo.evaluate_chromosome(ch, fleet)  # sets ch.cost + ch.pheromones.gaps from one sim
        return ch

    def apply_all(routes, phero):
        ls.strategy_spatial_attraction(routes, phero)
        ls.strategy_redundancy_repulsion(routes, phero)
        ls.strategy_tortuosity_pruning(routes, phero)

    def gate(routes):
        return avg_fit(routes, args.kg)  # averaged accept-gate: robust to the ~noise floor

    # -- strategies: each returns the final route system. f0g is the averaged baseline. --
    def strat_proxy(R0, ch0, f0g):
        Rc = copy_sys(R0)
        a0 = algo._allocate_fleet_mohring(Rc, fleet, sample_size=150)
        d0 = algo._total_disparity(ch0.pheromones.calculate_demand_service_gaps(Rc, a0))
        apply_all(Rc, ch0.pheromones)
        a1 = algo._allocate_fleet_mohring(Rc, fleet, sample_size=150)
        d1 = algo._total_disparity(ch0.pheromones.calculate_demand_service_gaps(Rc, a1))
        return Rc if d1 < d0 else R0

    def strat_avg_gate(R0, ch0, f0g):
        Rc = copy_sys(R0)
        apply_all(Rc, ch0.pheromones)
        return Rc if gate(Rc) < f0g else R0

    def strat_best_op(R0, ch0, f0g):
        best, bestf = R0, f0g
        for op in (ls.strategy_spatial_attraction, ls.strategy_redundancy_repulsion,
                   ls.strategy_tortuosity_pruning):
            Rc = copy_sys(R0)
            op(Rc, ch0.pheromones)
            f = gate(Rc)
            if f < bestf:
                best, bestf = Rc, f
        return best

    def strat_bestN(R0, ch0, f0g):
        best, bestf = R0, f0g
        for _ in range(args.N):
            Rc = copy_sys(R0)
            apply_all(Rc, ch0.pheromones)
            f = gate(Rc)
            if f < bestf:
                best, bestf = Rc, f
        return best

    def strat_iter(R0, ch0, f0g):
        cur, curf, phero = copy_sys(R0), f0g, ch0.pheromones
        for _ in range(3):
            Rc = copy_sys(cur)
            apply_all(Rc, phero)
            f = gate(Rc)
            if f < curf:
                cur, curf = Rc, f
                phero = make_eval_chrom(copy_sys(cur)).pheromones  # refresh gap signal
            else:
                break
        return cur

    strategies = [("A proxy", strat_proxy), ("B avg_gate", strat_avg_gate),
                  ("C best_op", strat_best_op), ("D best_of_N", strat_bestN),
                  ("E iter_avg", strat_iter)]

    # -- noise floor: repeat-sim spread on one fixed network --
    R_noise = [rg.generate(n_points=4) for _ in range(n_routes)]
    fs = [one_fit(R_noise) for _ in range(6)]
    print(f"[noise] same network, 6 sims: mean={np.mean(fs):.0f} sd={np.std(fs):.0f} "
          f"cv={100*np.std(fs)/np.mean(fs):.1f}%  (delta below this is noise)\n")

    results = {name: [] for name, _ in strategies}
    for b in range(args.bases):
        R0 = [rg.generate(n_points=4) for _ in range(n_routes)]
        ch0 = make_eval_chrom(copy_sys(R0))   # populates pheromone gaps for the operators
        F0 = avg_fit(R0, args.k)              # averaged baseline, used for both gating and measurement
        line = f"base {b+1}/{args.bases}  F0={F0:.0f} | "
        for name, strat in strategies:
            final = strat(R0, ch0, F0)
            F1 = avg_fit(final, args.k)
            d = 100.0 * (F1 - F0) / F0
            results[name].append(d)
            line += f"{name.split()[0]}:{d:+5.1f}%  "
        print(line)

    print("\n=== strategy summary (delta F_sim %, negative = improvement) ===")
    print(f"{'strategy':16s} {'%improved':>9s} {'mean d%':>8s} {'median d%':>9s}")
    for name, _ in strategies:
        ds = results[name]
        pct_imp = 100.0 * sum(1 for x in ds if x < 0) / len(ds)
        print(f"{name:16s} {pct_imp:8.0f}% {np.mean(ds):7.1f}% {stats.median(ds):8.1f}%")


if __name__ == "__main__":
    main()
