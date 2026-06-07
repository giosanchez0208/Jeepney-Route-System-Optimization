import os
import sys
import time
import pickle
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.city_graph import CityGraph
from utils.direct_demand_sampler import DirectDemandSampler
from utils.route import RouteGenerator, Route
from utils.travel_graph import TravelGraph
from utils.jeep_system import FleetAllocator
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger_generator import PassengerGenerator
from utils.simulation import Simulation

def main():
    print("1. Loading CityGraph...")
    with open("results_and_discussion/pkl/profile_p1.pkl", "rb") as f:
        cg = pickle.load(f)
    print("CityGraph loaded.")

    print("2. Loading DirectDemandSampler...")
    with open("results_and_discussion/pkl/ddm_8am.pkl", "rb") as f:
        ddm = pickle.load(f)
    ddm.city = cg
    print("DirectDemandSampler loaded.")

    print("3. Generating 5 random routes...")
    rg = RouteGenerator(cg, ddm)
    routes = [rg.generate(n_points=4) for _ in range(5)]
    print("Routes generated.")

    print("4. Building TravelGraph...")
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg = TravelGraph(cg=cg, config=config.get("travel_graph", {}).copy(), routes=routes)
    print("TravelGraph built.")

    print("5. Running FleetAllocator.allocate_by_mohring...")
    t0 = time.time()
    allocation = FleetAllocator.allocate_by_mohring(
        total_fleet=10,
        routes=routes,
        sampler=ddm,
        tg=tg,
        mohring_sample_size=2000
    )
    t1 = time.time()
    print(f"Allocation completed in {t1 - t0:.2f} seconds.")
    print("Allocation:", {r.id: count for r, count in allocation.items()})

    print("6. Spawning Jeeps...")
    jeeps = []
    for route, count in allocation.items():
        for _ in range(count):
            start_coord = (route.path[0].start.lon, route.path[0].start.lat)
            jeeps.append(Jeep(route, curr_pos=start_coord, speed=20.0, max_capacity=16, seconds_per_tick=10))
    js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=14.4, equidistant_spawn=True)

    print("7. Setting up Simulation...")
    pg = PassengerGenerator(
        tg=tg,
        sampler=ddm,
        rate_per_hour=600.0,
        stdev=10.0,
        speed=4.5,
        seconds_per_tick=10
    )
    sim = Simulation(
        city_query="Iligan",
        bounds=cg.get_bounds(),
        jeep_system=js,
        passenger_generator=pg,
        max_ticks=50,
        beta_penalty=2.0,
        alpha_std_penalty=0.5,
        config=config
    )
    print("Simulation setup complete. Running for 50 ticks...")
    t0 = time.time()
    res = sim.run()
    t1 = time.time()
    print(f"Simulation completed in {t1 - t0:.2f} seconds.")
    print("Simulation fitness:", res.fitness_score)
    print("Simulation metrics:", res.metrics)

if __name__ == "__main__":
    main()
