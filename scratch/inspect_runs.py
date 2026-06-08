import opt_eval, yaml, pickle, numpy as np, copy
from pathlib import Path
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger_generator import PassengerGenerator
from utils.simulation import Simulation

def run_direct_sim(city, ddm, config, route_objs):
    SIM = config["simulation"]
    spt = int(SIM.get("seconds_per_tick", 10))
    total = int(SIM.get("total_allocatable_jeeps", 2000))
    jpr = max(1, total // len(route_objs))
    
    tg = TravelGraph(city, config=config.get("travel_graph", {}), routes=route_objs)
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat),
                  speed=float(SIM.get("jeep_speed_kmh", 20.0)), max_capacity=int(SIM.get("jeep_capacity", 16)),
                  seconds_per_tick=spt)
             for r in route_objs for _ in range(jpr)]
    js = JeepSystem(jeeps=jeeps, routes=route_objs, weight_tolerance=float(SIM.get("weight_tolerance", 14.4)), equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=ddm, rate_per_hour=float(SIM.get("spawn_rate_per_hour", 600.0)),
                            stdev=float(SIM.get("spawn_stdev", 10.0)), speed=float(SIM.get("passenger_speed_kmh", 4.5)),
                            seconds_per_tick=spt)
    cfg = copy.deepcopy(config); cfg["disable_tqdm"] = True
    sim = Simulation(city_query="Iligan", bounds=city.get_bounds(), jeep_system=js, passenger_generator=pg,
                     max_ticks=int(SIM.get("num_ticks", 540)), beta_penalty=2.0, alpha_std_penalty=0.5, config=cfg)
    result = sim.run()
    times = [(p.despawn_tick - p.spawn_tick) / 60.0
             for p in sim.passenger_generator.archived_passengers if p.despawn_tick is not None]
    return result, times

city, ddm, config = opt_eval._load_env()
runs = opt_eval.discover_runs()
opt_tags = [t for t in opt_eval.REPRO_TAGS if t in runs]

print("Loading saved results and evaluating...")
for tag in opt_tags:
    run_dir = runs[tag]
    elook = {((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)): e for e in city.graph}
    routes_opt = opt_eval.final_routes_from_checkpoint(run_dir, city, elook)
    
    if tag == "p1":
        print("\n--- DETAILED COMPARISON FOR P1 vs BASELINE_0 ---")
        # Run optimized P1
        res_opt, times_opt = run_direct_sim(city, ddm, config, routes_opt)
        print(f"Optimized P1:")
        print(f"  Score: {res_opt.score:.2f}")
        print(f"  Completed: {res_opt.metrics['completed_count']}")
        print(f"  Incomplete: {res_opt.metrics['incomplete_count']}")
        print(f"  Total Spawned: {res_opt.metrics['completed_count'] + res_opt.metrics['incomplete_count']}")
        print(f"  Mean Commute: {res_opt.metrics['mean_commute_time']:.2f}")
        print(f"  Sum Completed: {res_opt.metrics['sum_completed_time']:.2f}")
        print(f"  Sum Penalty: {res_opt.metrics['sum_penalty_time']:.2f}")
        print(f"  Equity Penalty: {res_opt.metrics['equity_penalty']:.2f}")
        
        # Run baseline
        import random
        random.seed(9000)
        np.random.seed(9000)
        routes_base = opt_eval.generate_route_system(38, city, ddm)
        res_base, times_base = run_direct_sim(city, ddm, config, routes_base)
        print(f"\nBaseline 0:")
        print(f"  Score: {res_base.score:.2f}")
        print(f"  Completed: {res_base.metrics['completed_count']}")
        print(f"  Incomplete: {res_base.metrics['incomplete_count']}")
        print(f"  Total Spawned: {res_base.metrics['completed_count'] + res_base.metrics['incomplete_count']}")
        print(f"  Mean Commute: {res_base.metrics['mean_commute_time']:.2f}")
        print(f"  Sum Completed: {res_base.metrics['sum_completed_time']:.2f}")
        print(f"  Sum Penalty: {res_base.metrics['sum_penalty_time']:.2f}")
        print(f"  Equity Penalty: {res_base.metrics['equity_penalty']:.2f}")
        break
