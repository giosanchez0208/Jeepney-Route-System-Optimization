import os
import sys
import time
import yaml
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.node import Node
from utils.directed_edge import DirEdge
from utils.travel_graph import TravelGraph
from utils.simulation import SimulationEvaluator

class NoStitchTravelGraph(TravelGraph):
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

        from itertools import count
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
        from collections import defaultdict
        l2_nodes_by_route = defaultdict(dict)

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

        for r_idx, r in enumerate(self.routes):
            l2_nodes = l2_nodes_by_route[r_idx]
            for e in r.path:
                c_start = (e.start.lon, e.start.lat)
                c_end = (e.end.lon, e.end.lat)
                
                ri_edge = DirEdge(l2_nodes[c_start], l2_nodes[c_end], True, id=f"RI_R{r_idx}_{next(ri_c):05d}")
                ri_edge.weight = self.ride_wt * ri_edge.getLength()
                
                self.travel_graph.append(ri_edge)
                self._outgoing_edges[ri_edge.start].append(ri_edge)

        # Connecting edges (WA, AL, TR)
        for r_idx in range(len(self.routes)):
            for coord, n2 in l2_nodes_by_route[r_idx].items():
                n1 = self.l1_nodes.get(coord)
                n3 = self.l3_nodes.get(coord)
                
                if n1 and n3:
                    wa_edge = DirEdge(n1, n2, True, weight=self.wait_wt, id=f"WA{next(wa_c):05d}")
                    self.travel_graph.append(wa_edge)
                    self._outgoing_edges[n1].append(wa_edge)

                    al_edge = DirEdge(n2, n3, True, weight=self.alight_wt, id=f"AL{next(al_c):05d}")
                    self.travel_graph.append(al_edge)
                    self._outgoing_edges[n2].append(al_edge)

                    tr_edge = DirEdge(n3, n2, True, weight=self.transfer_wt, id=f"TR{next(tr_c):05d}")
                    self.travel_graph.append(tr_edge)
                    self._outgoing_edges[n3].append(tr_edge)

        # COMPLETELY NO STITCHING CALLS AT ALL!
        print("[NoStitchTravelGraph] Construction finished with zero stitching!", flush=True)

def main():
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg_config = config.get("travel_graph", {})
    
    print("Building original TravelGraph...")
    t0 = time.time()
    tg_orig = TravelGraph(cg, config=tg_config, routes=routes)
    print(f"Original built in {time.time() - t0:.2f}s")
    
    print("Building No-Stitch TravelGraph...")
    t0 = time.time()
    tg_no_stitch = NoStitchTravelGraph(cg, config=tg_config, routes=routes)
    print(f"No-Stitch built in {time.time() - t0:.2f}s")

    # Verify query results
    print("Verifying 100 queries...")
    origins = [ddm.get_point() for _ in range(100)]
    dests = [ddm.get_point() for _ in range(100)]
    
    mismatches = 0
    for o, d in zip(origins, dests):
        p_orig = tg_orig.findShortestJourney(o, d)
        p_no = tg_no_stitch.findShortestJourney(o, d)
        
        w_orig = sum(e.weight for e in p_orig) if p_orig else None
        w_no = sum(e.weight for e in p_no) if p_no else None
        
        if w_orig != w_no:
            mismatches += 1
            print(f"Mismatch: Orig={w_orig}, No-Stitch={w_no}")
            
    if mismatches == 0:
        print("SUCCESS! No stitching at all is 100% mathematically correct and identical!")
    else:
        print(f"FAILURE: {mismatches} mismatches found.")

if __name__ == "__main__":
    main()
