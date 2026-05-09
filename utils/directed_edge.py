from math import radians, sin, cos, sqrt, asin
from typing import Optional

from .node import Node

### HELPER FUNCTIONS FOR DIR EDGE INITIALIZATION ###
def _nodes_match(node1: Node, node2: Node) -> bool:
    return node1.lon == node2.lon and node1.lat == node2.lat and node1.layer == node2.layer

### DIR EDGE CLASS ###
class DirEdge:
    def __init__(
        self,
        start: Node,
        end: Node,
        is_drivable: bool = False,
        weight: Optional[int] = None,
        id: Optional[str] = None,
        next_edges: Optional[list[str]] = None,
        type: Optional[str] = None
    ) -> None:
        if start is None and end is None:
            raise ValueError("[DIR EDGE] No start and end node provided.")
        if start is None:
            raise ValueError("[DIR EDGE] No start node provided.")
        if end is None:
            raise ValueError("[DIR EDGE] No end node provided.")
        if _nodes_match(start, end):
            raise ValueError("[DIR EDGE] Start and end nodes cannot be identical.")
        
        # a few more safeguards that are very specific to this project
        # 1. if same layer, must have different coordinates
        if start.layer == end.layer and start.lon == end.lon and start.lat == end.lat:
            raise ValueError("[DIR EDGE] Start and end nodes cannot have same coordinates on same layer.")
        #2. if different layers, must have same coordinates
        if start.layer != end.layer and (start.lon != end.lon or start.lat != end.lat):
            raise ValueError("[DIR EDGE] Start and end nodes on different layers must have same coordinates.")
        
        self.start = start
        self.end = end
        self.is_drivable = is_drivable
        self.weight = weight
        self.id = id if id is not None else f"{start.id}{end.id}"
        self.next_edges = next_edges if next_edges is not None else []
        self.type = type if type is not None else self.getType()

    def __str__(self) -> str:
        return f"DirEdge({self.id}): {self.start.id} -> {self.end.id}, type={self.type}, weight={self.weight}, drivable={self.is_drivable}"
    
    def getLength(self) -> float:
        return _getDistance(self.start, self.end)

    def isConnectedTo(self, other: DirEdge) -> bool:
        return _nodes_match(self.end, other.start)
    
    def getType(self) -> str:
        match (self.start.layer, self.end.layer):
            case (1, 1):
                return "start_walk"
            case (1, 2):
                return "wait"
            case (2, 2):
                return "ride"
            case (2, 3):
                return "alight"
            case (3, 2):
                return "transfer"
            case (3, 3):
                return "end_walk"
            case (1, 3):
                return "direct"
            case (0, 0) | (None, None):
                return None
            case _:
                raise ValueError(f"[DIR EDGE] Invalid layer combination: {self.start.layer} to {self.end.layer}")
        

### HELPER FUNCTIONS FOR DIR EDGE METHODS ###
def _getDistance(node1: Node, node2: Node) -> float:
    lat1, lon1 = radians(node1.lat), radians(node1.lon)
    lat2, lon2 = radians(node2.lat), radians(node2.lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371000.0 * c

### EXTERNAL HELPER FUNCTIONS FOR DIR EDGE CONNECTIVITY, used by CityGraph and TravelGraph ###
def _connect(dir_edge_s: DirEdge, dir_edge_e: DirEdge, weight: int = 1, verbose: bool = False) -> None:
    if dir_edge_s.isConnectedTo(dir_edge_e):
        dir_edge_s.next_edges.append(dir_edge_e.id)
        dir_edge_s.weight = weight
        if verbose:
            print(f"[DIR EDGE] Connected {dir_edge_s.id} -> {dir_edge_e.id} with weight {weight}")
    else:
        if verbose:
            print(f"[DIR EDGE] Cannot connect {dir_edge_s.id} -> {dir_edge_e.id} (not connected)")
    return

def _stitch(dir_edges_s: list[DirEdge], dir_edges_e: list[DirEdge], weight: int = 1, verbose: bool = False) -> None:
    stitched = 0
    for dir_edge_s in dir_edges_s:
        for dir_edge_e in dir_edges_e:
            _connect(dir_edge_s, dir_edge_e, weight, verbose)
            stitched += 1
    if verbose:
        print(f"Stitched {stitched} edges between sets of size {len(dir_edges_s)} and {len(dir_edges_e)}")