"""Verify the isolated-route + segment-highlight drawing (edge.draw) on a toy seed where attraction fires."""
import os, sys
sys.path.insert(0, os.getcwd())
import copy, random
import numpy as np
from PIL import Image

from utils.toy_city import toy_setup_from_yaml
from utils_simplified import generate_route_system, build_pheromone_matrix, mutate_attraction
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger_generator import PassengerGenerator
from utils.simulation import Simulation

city, sampler, config = toy_setup_from_yaml("configs/toy_city_configs.yaml", verbose=False)
ctx = city.get_bounds()

def run_toy_sim(routes, rate=600.0, ticks=1500):
    tg = TravelGraph(city, config=config.get("travel_graph", {}), routes=routes)
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat), speed=40.0, max_capacity=16, seconds_per_tick=1)
             for r in routes for _ in range(5)]
    js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=50.0, equidistant_spawn=True)
    pg = PassengerGenerator(tg=tg, sampler=sampler, rate_per_hour=rate, stdev=10.0, speed=5.0, seconds_per_tick=1)
    cfg = copy.deepcopy(config); cfg["disable_tqdm"] = True
    sim = Simulation(city_query="ToyCity", bounds=ctx, jeep_system=js, passenger_generator=pg,
                     max_ticks=ticks, beta_penalty=2.0, alpha_std_penalty=0.5, config=cfg)
    return sim.run()

def ekeys_of(route):
    return [(round(e.start.lon,6),round(e.start.lat,6),round(e.end.lon,6),round(e.end.lat,6)) for e in route.path]

def most_changed_route(before, after):
    best_i, best_d = 0, -1
    for i in range(min(len(before), len(after))):
        d = len(set(ekeys_of(before[i])) ^ set(ekeys_of(after[i])))
        if d > best_d:
            best_d, best_i = d, i
    return best_i, best_d

def draw_route_highlight(route, highlight_keys, base_color, hi_color, size=900, only_drivable=True):
    img = city.draw(size=size, only_drivable=only_drivable).copy()
    img = route.draw(ctx, img, color=base_color, width=4)
    n = 0
    for e in route.path:
        k = (round(e.start.lon,6), round(e.start.lat,6), round(e.end.lon,6), round(e.end.lat,6))
        if k in highlight_keys:
            img = e.draw(ctx, img, color=hi_color, width=8)
            n += 1
    return img, n

random.seed(0); np.random.seed(0)
routes = generate_route_system(5, city, sampler)
res = run_toy_sim(routes)
ph = build_pheromone_matrix(city, res)
mutated = mutate_attraction(ph, routes, city, intensity=1.0)

i, d = most_changed_route(routes, mutated)
before_i, after_i = routes[i], mutated[i]
removed = set(ekeys_of(before_i)) - set(ekeys_of(after_i))
added   = set(ekeys_of(after_i)) - set(ekeys_of(before_i))
print(f"changed route index={i}, total edge diff={d}, removed={len(removed)}, added={len(added)}")
print(f"before route edges={len(before_i.path)}, after route edges={len(after_i.path)}")

img_b, nb = draw_route_highlight(before_i, removed, "#377eb8", "#e41a1c")
img_a, na = draw_route_highlight(after_i, added, "#377eb8", "#2ca02c")
assert isinstance(img_b, Image.Image) and isinstance(img_a, Image.Image)
print(f"[ok] isolated draw: before highlighted {nb} removed edges (red), after highlighted {na} added edges (green)")
print("SMOKE PASSED")
