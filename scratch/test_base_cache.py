import os
import sys
import time
import yaml
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
import cProfile
import pstats

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils_simplified import reuse_citygraph, reuse_ddm, generate_route_system
from utils.node import Node
from utils.directed_edge import DirEdge, _stitch
from utils.travel_graph import TravelGraph

class CachedTravelGraph(TravelGraph):
    _base_cache = {}

    def _construct(self) -> None:
        cache_key = (
            id(self.cg),
            self.walk_wt,
            self.ride_wt,
            self.wait_wt,
            self.transfer_wt,
            self.direct_wt,
            self.alight_wt
        )

        if cache_key not in CachedTravelGraph._base_cache:
            # Build and cache
            l1_nodes = {}
            l3_nodes = {}
            for n in self.cg.nodes:
                coord = (n.lon, n.lat)
                n1 = Node(n.lon, n.lat)
                n1.layer = 1
                l1_nodes[coord] = n1

                n3 = Node(n.lon, n.lat)
                n3.layer = 3
                l3_nodes[coord] = n3

            l1_coords = np.array(list(l1_nodes.keys()))
            l1_kdtree = cKDTree(l1_coords)
            
            l3_coords = np.array(list(l3_nodes.keys()))
            l3_kdtree = cKDTree(l3_coords)

            from itertools import count
            sw_c = count(1)
            ew_c = count(1)
            di_c = count(1)

            base_travel_graph = []
            base_outgoing_edges = defaultdict(list)

            for e in self.cg.graph:
                c_start = (e.start.lon, e.start.lat)
                c_end = (e.end.lon, e.end.lat)

                walk_weight = self.walk_wt * e.getLength()

                sw_edge = DirEdge(l1_nodes[c_start], l1_nodes[c_end], e.is_drivable, id=f"SW{next(sw_c):05d}")
                sw_edge.weight = walk_weight
                base_travel_graph.append(sw_edge)
                base_outgoing_edges[sw_edge.start].append(sw_edge)

                ew_edge = DirEdge(l3_nodes[c_start], l3_nodes[c_end], e.is_drivable, id=f"EW{next(ew_c):05d}")
                ew_edge.weight = walk_weight
                base_travel_graph.append(ew_edge)
                base_outgoing_edges[ew_edge.start].append(ew_edge)

            for coord, n1 in l1_nodes.items():
                n3 = l3_nodes[coord]
                di_edge = DirEdge(n1, n3, True, weight=self.direct_wt, id=f"DI{next(di_c):05d}")
                base_travel_graph.append(di_edge)
                base_outgoing_edges[n1].append(di_edge)

            CachedTravelGraph._base_cache[cache_key] = {
                "l1_nodes": l1_nodes,
                "l3_nodes": l3_nodes,
                "l1_coords": l1_coords,
                "l1_kdtree": l1_kdtree,
                "l3_coords": l3_coords,
                "l3_kdtree": l3_kdtree,
                "travel_graph": base_travel_graph,
                "outgoing_edges": base_outgoing_edges
            }

        cache = CachedTravelGraph._base_cache[cache_key]
        self.l1_nodes = cache["l1_nodes"]
        self.l3_nodes = cache["l3_nodes"]
        self._l1_coords = cache["l1_coords"]
        self._l1_kdtree = cache["l1_kdtree"]
        self._l3_coords = cache["l3_coords"]
        self._l3_kdtree = cache["l3_kdtree"]

        self.travel_graph = list(cache["travel_graph"])
        self._outgoing_edges = defaultdict(list, {k: list(v) for k, v in cache["outgoing_edges"].items()})

        l2_nodes_by_route = defaultdict(dict)
        for r_idx, r in enumerate(self.routes):
            for e in r.path:
                for n in (e.start, e.end):
                    coord = (n.lon, n.lat)
                    if coord not in l2_nodes_by_route[r_idx]:
                        n2 = Node(n.lon, n.lat)
                        n2.layer = 2
                        l2_nodes_by_route[r_idx][coord] = n2

        from itertools import count
        ri_c = count(1)
        wa_c = count(1)
        al_c = count(1)
        tr_c = count(1)

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
    print("Loading CityGraph...")
    cg = reuse_citygraph("rnd/pkl/profile_p1.pkl")
    ddm = reuse_ddm("rnd/pkl/ddm_8am.pkl")
    routes = generate_route_system(38, cg, ddm)
    
    with open("configs/profile_p1.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tg_config = config.get("travel_graph", {})
    
    # Run once to warm cache
    tg_cached1 = CachedTravelGraph(cg, config=tg_config, routes=routes)
    
    # Profile 2nd call
    profiler = cProfile.Profile()
    profiler.enable()
    
    tg_cached2 = CachedTravelGraph(cg, config=tg_config, routes=routes)
    
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumulative')
    stats.print_stats(30)

if __name__ == "__main__":
    main()
