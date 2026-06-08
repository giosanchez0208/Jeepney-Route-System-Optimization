import os
import sys
import time
import yaml
from collections import defaultdict
from itertools import count
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.node import Node
from utils.directed_edge import DirEdge, _stitch

def log(msg):
    print(msg, flush=True)

def main():
    log("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    log("Generating 38 routes...")
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg_config = config.get("travel_graph", {})
    
    walk_wt = tg_config.get("walk_wt", 1.0)
    direct_wt = tg_config.get("direct_wt", 0.0)
    wait_wt = tg_config.get("wait_wt", 5.0)
    alight_wt = tg_config.get("alight_wt", 0.0)
    transfer_wt = tg_config.get("transfer_wt", 5.0)
    ride_wt = tg_config.get("ride_wt", 1.0)

    log("Timing TravelGraph._construct() steps:")
    
    # Step 1: Layer 1 & 3 node creation
    t0 = time.time()
    l1_nodes = {}
    l3_nodes = {}
    for n in cg.nodes:
        coord = (n.lon, n.lat)
        n1 = Node(n.lon, n.lat)
        n1.layer = 1
        l1_nodes[coord] = n1

        n3 = Node(n.lon, n.lat)
        n3.layer = 3
        l3_nodes[coord] = n3
    log(f"  Step 1 (Node creation): {time.time() - t0:.3f}s")
    
    # Step 2: KDTree creation
    t0 = time.time()
    l1_coords = np.array(list(l1_nodes.keys()))
    l1_kdtree = cKDTree(l1_coords)
    l3_coords = np.array(list(l3_nodes.keys()))
    l3_kdtree = cKDTree(l3_coords)
    log(f"  Step 2 (KDTree): {time.time() - t0:.3f}s")
    
    # Step 3: Base edge creation
    t0 = time.time()
    sw_c = count(1)
    ew_c = count(1)
    di_c = count(1)
    travel_graph = []
    _outgoing_edges = defaultdict(list)
    for e in cg.graph:
        c_start = (e.start.lon, e.start.lat)
        c_end = (e.end.lon, e.end.lat)
        walk_weight = walk_wt * e.getLength()
        sw_edge = DirEdge(l1_nodes[c_start], l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
        sw_edge.weight = walk_weight
        travel_graph.append(sw_edge)
        _outgoing_edges[sw_edge.start].append(sw_edge)
        ew_edge = DirEdge(l3_nodes[c_start], l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
        ew_edge.weight = walk_weight
        travel_graph.append(ew_edge)
        _outgoing_edges[ew_edge.start].append(ew_edge)
    log(f"  Step 3 (Base edge creation): {time.time() - t0:.3f}s")
    
    # Step 4: Direct edges 1 -> 3
    t0 = time.time()
    for coord, n1 in l1_nodes.items():
        n3 = l3_nodes[coord]
        di_edge = DirEdge(n1, n3, True, weight=direct_wt, id=f"DI{next(di_c):05d}")
        travel_graph.append(di_edge)
        _outgoing_edges[n1].append(di_edge)
    log(f"  Step 4 (Direct edges): {time.time() - t0:.3f}s")
    
    # Step 5: Layer 2 nodes and edges
    t0 = time.time()
    l2_nodes_by_route = defaultdict(dict)
    for r_idx, r in enumerate(routes):
        for e in r.path:
            for n in (e.start, e.end):
                coord = (n.lon, n.lat)
                if coord not in l2_nodes_by_route[r_idx]:
                    n2 = Node(n.lon, n.lat)
                    n2.layer = 2
                    l2_nodes_by_route[r_idx][coord] = n2
    
    ri_c = count(1)
    wa_c = count(1)
    al_c = count(1)
    tr_c = count(1)
    
    for r_idx, r in enumerate(routes):
        l2_nodes = l2_nodes_by_route[r_idx]
        for e in r.path:
            c_start = (e.start.lon, e.start.lat)
            c_end = (e.end.lon, e.end.lat)
            ri_edge = DirEdge(l2_nodes[c_start], l2_nodes[c_end], True, id=f"RI_R{r_idx}_{next(ri_c):05d}")
            ri_edge.weight = ride_wt * ri_edge.getLength()
            travel_graph.append(ri_edge)
            _outgoing_edges[ri_edge.start].append(ri_edge)
            
    for r_idx in range(len(routes)):
        for coord, n2 in l2_nodes_by_route[r_idx].items():
            n1 = l1_nodes.get(coord)
            n3 = l3_nodes.get(coord)
            if n1 and n3:
                wa_edge = DirEdge(n1, n2, True, weight=wait_wt, id=f"WA{next(wa_c):05d}")
                travel_graph.append(wa_edge)
                _outgoing_edges[n1].append(wa_edge)
                al_edge = DirEdge(n2, n3, True, weight=alight_wt, id=f"AL{next(al_c):05d}")
                travel_graph.append(al_edge)
                _outgoing_edges[n2].append(al_edge)
                tr_edge = DirEdge(n3, n2, True, weight=transfer_wt, id=f"TR{next(tr_c):05d}")
                travel_graph.append(tr_edge)
                _outgoing_edges[n3].append(tr_edge)
    log(f"  Step 5 (Layer 2 nodes and edges): {time.time() - t0:.3f}s")
    
    # Step 6: Stitching
    t0 = time.time()
    sw_edges = [e for e in travel_graph if e.id[:2] == "SW"]
    ew_edges = [e for e in travel_graph if e.id[:2] == "EW"]
    di_edges = [e for e in travel_graph if e.id[:2] == "DI"]
    wa_edges = [e for e in travel_graph if e.id[:2] == "WA"]
    al_edges = [e for e in travel_graph if e.id[:2] == "AL"]
    tr_edges = [e for e in travel_graph if e.id[:2] == "TR"]
    log(f"  Step 6.0 (Filter lists): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(sw_edges, sw_edges)
    log(f"  Step 6.1 (_stitch sw_edges, sw_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(sw_edges, di_edges)
    log(f"  Step 6.2 (_stitch sw_edges, di_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(sw_edges, wa_edges)
    log(f"  Step 6.3 (_stitch sw_edges, wa_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(di_edges, ew_edges)
    log(f"  Step 6.4 (_stitch di_edges, ew_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(al_edges, ew_edges)
    log(f"  Step 6.5 (_stitch al_edges, ew_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(al_edges, tr_edges)
    log(f"  Step 6.6 (_stitch al_edges, tr_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(ew_edges, ew_edges)
    log(f"  Step 6.7 (_stitch ew_edges, ew_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    _stitch(ew_edges, tr_edges)
    log(f"  Step 6.8 (_stitch ew_edges, tr_edges): {time.time() - t0:.3f}s")
    
    t0 = time.time()
    for r_idx in range(len(routes)):
        l2_nodes_set = set(l2_nodes_by_route[r_idx].values())
        r_ri = [e for e in travel_graph if e.id.startswith(f"RI_R{r_idx}_")]
        r_wa = [e for e in wa_edges if e.end in l2_nodes_set]
        r_al = [e for e in al_edges if e.start in l2_nodes_set]
        r_tr = [e for e in tr_edges if e.end in l2_nodes_set]
        
        _stitch(r_wa, r_ri)
        _stitch(r_wa, r_al)
        _stitch(r_ri, r_ri)
        _stitch(r_ri, r_al)
        _stitch(r_tr, r_ri)
        _stitch(r_tr, r_al)
    log(f"  Step 6.9 (Route-specific stitching): {time.time() - t0:.3f}s")

if __name__ == "__main__":
    main()
