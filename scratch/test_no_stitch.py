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
from utils.travel_graph import TravelGraph

def log(msg):
    print(msg, flush=True)

class OptimizedTravelGraph(TravelGraph):
    def _construct(self) -> None:
        # Layer 1 and 3 nodes
        for n in self.cg.nodes:
            coord = (n.lon, n.lat)
            n1 = Node(n.lon, n.lat)
            n1.layer = 1
            self.l1_nodes[coord] = n1

            n3 = Node(n.lon, n.lat)
            n3.layer = 3
            self.l3_nodes[coord] = n3

        self._l1_coords = np.array(list(self.l1_nodes.keys()))
        self._l1_kdtree = cKDTree(self._l1_coords)
        
        self._l3_coords = np.array(list(self.l3_nodes.keys()))
        self._l3_kdtree = cKDTree(self._l3_coords)

        sw_c = count(1)
        ew_c = count(1)
        di_c = count(1)

        # Base edges for layer 1 and 3
        for e in self.cg.graph:
            c_start = (e.start.lon, e.start.lat)
            c_end = (e.end.lon, e.end.lat)

            walk_weight = self.walk_wt * e.getLength()

            sw_edge = DirEdge(self.l1_nodes[c_start], self.l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
            sw_edge.weight = walk_weight
            self.travel_graph.append(sw_edge)
            self._outgoing_edges[sw_edge.start].append(sw_edge)

            ew_edge = DirEdge(self.l3_nodes[c_start], self.l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
            ew_edge.weight = walk_weight
            self.travel_graph.append(ew_edge)
            self._outgoing_edges[ew_edge.start].append(ew_edge)

        # Direct edges 1 -> 3
        for coord, n1 in self.l1_nodes.items():
            n3 = self.l3_nodes[coord]
            di_edge = DirEdge(n1, n3, True, weight=self.direct_wt, id=f"DI{next(di_c):05d}")
            self.travel_graph.append(di_edge)
            self._outgoing_edges[n1].append(di_edge)

        # Layer 2 nodes and edges
        l2_nodes_by_route: dict[int, dict[tuple[float, float], Node]] = defaultdict(dict)

        for r_idx, r in enumerate(self.routes):
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

        # Pre-group list containers to avoid O(N) filtering comprehensions later
        ri_by_route = defaultdict(list)
        wa_by_route = defaultdict(list)
        al_by_route = defaultdict(list)
        tr_by_route = defaultdict(list)

        for r_idx, r in enumerate(self.routes):
            l2_nodes = l2_nodes_by_route[r_idx]
            for e in r.path:
                c_start = (e.start.lon, e.start.lat)
                c_end = (e.end.lon, e.end.lat)
                
                ri_edge = DirEdge(l2_nodes[c_start], l2_nodes[c_end], True, id=f"RI_R{r_idx}_{next(ri_c):05d}")
                ri_edge.weight = self.ride_wt * ri_edge.getLength()
                
                self.travel_graph.append(ri_edge)
                self._outgoing_edges[ri_edge.start].append(ri_edge)
                ri_by_route[r_idx].append(ri_edge)

        # Connecting edges (WA, AL, TR)
        for r_idx in range(len(self.routes)):
            for coord, n2 in l2_nodes_by_route[r_idx].items():
                n1 = self.l1_nodes.get(coord)
                n3 = self.l3_nodes.get(coord)
                
                if n1 and n3:
                    wa_edge = DirEdge(n1, n2, True, weight=self.wait_wt, id=f"WA{next(wa_c):05d}")
                    self.travel_graph.append(wa_edge)
                    self._outgoing_edges[n1].append(wa_edge)
                    wa_by_route[r_idx].append(wa_edge)

                    al_edge = DirEdge(n2, n3, True, weight=self.alight_wt, id=f"AL{next(al_c):05d}")
                    self.travel_graph.append(al_edge)
                    self._outgoing_edges[n2].append(al_edge)
                    al_by_route[r_idx].append(al_edge)

                    tr_edge = DirEdge(n3, n2, True, weight=self.transfer_wt, id=f"TR{next(tr_c):05d}")
                    self.travel_graph.append(tr_edge)
                    self._outgoing_edges[n3].append(tr_edge)
                    tr_by_route[r_idx].append(tr_edge)

        # We completely skip base layer stitching!
        # Route-specific layer 2 stitching
        saved_weights = {e: e.weight for e in self.travel_graph}
        for r_idx in range(len(self.routes)):
            r_ri = ri_by_route[r_idx]
            r_wa = wa_by_route[r_idx]
            r_al = al_by_route[r_idx]
            r_tr = tr_by_route[r_idx]
            
            _stitch(r_wa, r_ri)
            _stitch(r_wa, r_al)
            
            _stitch(r_ri, r_ri)
            _stitch(r_ri, r_al)
            
            _stitch(r_tr, r_ri)
            _stitch(r_tr, r_al)
            
        for e in self.travel_graph:
            e.weight = saved_weights[e]

def main():
    log("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg_config = config.get("travel_graph", {})
    
    log("Building original TravelGraph...")
    t0 = time.time()
    tg_orig = TravelGraph(cg, config=tg_config, routes=routes)
    t_orig = time.time() - t0
    log(f"Original TravelGraph built in {t_orig:.3f}s")
    
    log("Building optimized TravelGraph (no base stitch, no O(N) filters)...")
    t0 = time.time()
    tg_opt = OptimizedTravelGraph(cg, config=tg_config, routes=routes)
    t_opt = time.time() - t0
    log(f"Optimized TravelGraph built in {t_opt:.3f}s (Speedup: {t_orig / t_opt:.1f}x)")
    
    log("Comparing 100 shortest path queries...")
    origins = [ddm.get_point() for _ in range(100)]
    dests = [ddm.get_point() for _ in range(100)]
    
    failures = 0
    for idx, (o, d) in enumerate(zip(origins, dests)):
        path_orig = tg_orig._findShortestJourney_impl(o, d)
        path_opt = tg_opt._findShortestJourney_impl(o, d)
        
        len_orig = sum(e.weight for e in path_orig) if path_orig else None
        len_opt = sum(e.weight for e in path_opt) if path_opt else None
        
        if len_orig != len_opt:
            log(f"Mismatch at index {idx}: original length {len_orig}, optimized length {len_opt}")
            failures += 1
            
    if failures == 0:
        log("SUCCESS! All 100 shortest path results match exactly!")
    else:
        log(f"FAILURE! {failures}/100 shortest path results mismatched.")

if __name__ == "__main__":
    main()
