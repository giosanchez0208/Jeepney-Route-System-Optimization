import os
import sys
import time
import cProfile
import pstats
import yaml

class Logger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.terminal.flush()
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.simulation import SimulationEvaluator

def main():
    log_path = "scratch/profile_eval.log"
    sys.stdout = Logger(log_path)
    sys.stderr = sys.stdout

    print("Loading config...")
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config["cg_pkl"] = "rnd/pkl/profile_p1.pkl"
    config["ddm_pkl"] = "rnd/pkl/ddm_8am.pkl"

    print("Loading CityGraph and DDM...")
    cg = reuse_citygraph(config["cg_pkl"])
    ddm = reuse_ddm(config["ddm_pkl"])

    print("Generating route system of size 38...")
    routes = generate_route_system(38, cg, ddm)

    print("Setting up SimulationEvaluator...")
    evaluator = SimulationEvaluator(
        config=config,
        city_graph=cg,
        travel_graph=None,
        demand_sampler=ddm
    )

    print("Running a single evaluation under cProfile...")
    profiler = cProfile.Profile()
    profiler.enable()
    
    t0 = time.time()
    result = evaluator.evaluate(routes, verbose=True)
    t1 = time.time()
    
    profiler.disable()
    print(f"Evaluation finished in {t1 - t0:.2f} seconds.")
    
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(50)

if __name__ == "__main__":
    main()
