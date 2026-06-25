"""run_scenarios.py -- Ask #1: synthetic behavioral scenarios / agent archetypes.

Demonstrates that the framework is behavior-agnostic: one fixed Iligan network is evaluated under
four synthetic commuter archetypes, realized purely by overriding the calibrated behavioral
parameters (no fabricated survey data). The metrics shift with the archetype, showing the simulation
responds to agent heterogeneity. Fills Table tab:panel_scenarios in paper/revisions_panel.tex.

    python run_scenarios.py
"""
import copy
import random

import numpy as np
import yaml

from analyze_benchmarks import transfer_stats


def sim_with_routes(city, ddm, config, route_objs):
    """Simulate a fixed set of Route objects under `config` (mirrors opt_eval._resim but takes
    Route objects directly, so the TravelGraph picks up the scenario's behavioral weights)."""
    from utils.travel_graph import TravelGraph
    from utils.jeep import Jeep
    from utils.jeep_system import JeepSystem
    from utils.passenger_generator import PassengerGenerator
    from utils.simulation import Simulation
    SIM = config["simulation"]
    spt = int(SIM.get("seconds_per_tick", 10))
    total = int(SIM.get("total_allocatable_jeeps", 2000))
    jpr = max(1, total // len(route_objs))
    tg = TravelGraph(city, config=config.get("travel_graph", {}), routes=route_objs)
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                  speed=float(SIM.get("jeep_speed_kmh", 20.0)), max_capacity=int(SIM.get("jeep_capacity", 16)),
                  seconds_per_tick=spt)
             for r in route_objs for _ in range(jpr)]
    js = JeepSystem(jeeps=jeeps, routes=route_objs, weight_tolerance=float(SIM.get("weight_tolerance", 14.4)),
                    equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=ddm, rate_per_hour=float(SIM.get("spawn_rate_per_hour", 600.0)),
                            stdev=float(SIM.get("spawn_stdev", 10.0)), speed=float(SIM.get("passenger_speed_kmh", 4.5)),
                            seconds_per_tick=spt)
    cfg = copy.deepcopy(config); cfg["disable_tqdm"] = True
    sim = Simulation(city_query="Iligan", bounds=city.get_bounds(), jeep_system=js, passenger_generator=pg,
                     max_ticks=int(SIM.get("num_ticks", 540)), beta_penalty=2.0, alpha_std_penalty=0.5, config=cfg)
    return sim.run()


SCENARIOS = {
    "Survey-calibrated": {},
    "Time-sensitive":    {"tg": {"transfer_wt": 25.0}, "sim": {"weight_tolerance": 7.0}},
    "Walk-averse":       {"tg": {"walk_wt": 0.1126}},
    "Transfer-tolerant": {"tg": {"transfer_wt": 8.0}, "sim": {"weight_tolerance": 20.0}},
}


def main():
    from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
    city = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    base = yaml.safe_load(open("configs/profile_p1.yaml", encoding="utf-8"))
    base.setdefault("simulation", {})["jeep_speed_kmh"] = 20.0

    random.seed(123); np.random.seed(123)
    net = generate_route_system(38, city, ddm)

    print(f"{'Archetype':20s} {'commute':>8s} {'tr/trip':>8s} {'completion':>11s}")
    for name, ov in SCENARIOS.items():
        cfg = copy.deepcopy(base)
        cfg.setdefault("travel_graph", {}).update(ov.get("tg", {}))
        cfg.setdefault("simulation", {}).update(ov.get("sim", {}))
        random.seed(123); np.random.seed(123)  # same demand draw -> differences are behavioral
        res = sim_with_routes(city, ddm, cfg, net)
        m = res.metrics
        done, und = int(m.get("completed_count", 0)), int(m.get("incomplete_count", 0))
        comp = 100.0 * done / (done + und) if (done + und) else float("nan")
        commute = m.get("mean_commute_time", float("nan")) / 60.0
        tr, _trp = transfer_stats(res)
        print(f"{name:20s} {commute:7.1f}m {tr:7.2f} {comp:10.1f}%")


if __name__ == "__main__":
    main()
