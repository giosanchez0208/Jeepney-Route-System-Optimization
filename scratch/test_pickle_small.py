import os
import sys
sys.path.append(os.path.abspath('.'))
from utils.city_graph import CityGraph, Node
from utils.direct_demand_sampler import DirectDemandSampler, DDMConfig
import pickle
import datetime

# Create a minimal CityGraph manually
cg = CityGraph()
n1 = Node(124.6459, 8.4772)
n2 = Node(124.6500, 8.4812)
n1.layer = 1
n2.layer = 1
cg.nodes.extend([n1, n2])
from utils.directed_edge import DirEdge
cg.graph.append(DirEdge(n1, n2, is_drivable=True, osm_highway='primary'))
cg._node_lookup = {1: n1, 2: n2}

target_time = datetime.datetime.now().replace(hour=13, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
config = DDMConfig(alpha=0.6, beta=0.4, target_time=target_time)

print("Building DDM...")
ddm = DirectDemandSampler(city=cg, config=config, verbose=True, use_cache=False)

print("Pickling DDM...")
try:
    with open("scratch/test_small.pkl", "wb") as f:
        pickle.dump(ddm, f)
    print("Pickled successfully!")
except Exception as e:
    print("Pickle failed:", repr(e))
