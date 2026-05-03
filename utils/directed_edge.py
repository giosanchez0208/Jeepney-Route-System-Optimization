"""directed_edge.py

DirEdge(start: Node, end: Node, is_drivable: bool, weight: int = 1, id: Optional[str] = None, next_edges: Optional[list[str]] = None) -> None creates start: Node, end: Node, is_drivable: bool, weight: int, id: str, and next_edges: list[str].
getLength(self) -> float returns the edge distance in meters.
isConnectedTo(self, other: DirEdge) -> bool returns whether two edges share matching boundary nodes.
_getDistance(node1: Node, node2: Node) -> float returns the great-circle distance in meters.
_connect(dir_edge_s: DirEdge, dir_edge_e: DirEdge, weight: int = 1) -> bool links compatible edges and returns success.
_stitch(dir_edges_s: list[DirEdge], dir_edges_e: list[DirEdge], weight: int = 1) -> int connects matching edges and returns the stitch count.
"""

from math import radians, sin, cos, sqrt, asin
from typing import Optional

from node import Node

class DirEdge:
    def __init__(
        self,
        start: Node,
        end: Node,
        is_drivable: bool,
        weight: int = 1,
        id: Optional[str] = None,
        next_edges: Optional[list[str]] = None,
        type: Optional[str] = None
    ) -> None:
        if start is None or end is None:
            raise ValueError("DirEdge requires both start and end nodes.")

        self.start = start
        self.end = end
        self.is_drivable = is_drivable
        self.weight = weight
        self.id = id if id is not None else f"{start.id}{end.id}"
        self.next_edges = next_edges if next_edges is not None else []
        self.type = type if type is not None else self.getType()

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
                raise ValueError(f"Invalid layer combination: {self.start.layer} to {self.end.layer}")

def _nodes_match(node1: Node, node2: Node) -> bool:
    return node1.lon == node2.lon and node1.lat == node2.lat and node1.layer == node2.layer

def _getDistance(node1: Node, node2: Node) -> float:
    lat1, lon1 = radians(node1.lat), radians(node1.lon)
    lat2, lon2 = radians(node2.lat), radians(node2.lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371000.0 * c

def _connect(dir_edge_s: DirEdge, dir_edge_e: DirEdge, weight: int = 1) -> bool:
    if dir_edge_s.isConnectedTo(dir_edge_e):
        dir_edge_s.next_edges.append(dir_edge_e.id)
        dir_edge_s.weight = weight
        return True
    return False


def _stitch(dir_edges_s: list[DirEdge], dir_edges_e: list[DirEdge], weight: int = 1) -> int:
    stitched = 0
    for dir_edge_s in dir_edges_s:
        for dir_edge_e in dir_edges_e:
            if _connect(dir_edge_s, dir_edge_e, weight):
                stitched += 1
    return stitched

"""
### SANITY CHECK ###

if __name__ == "__main__":
    a = Node(120.0, 14.0)
    b = Node(120.0001, 14.0002)
    c = Node(120.0002, 14.0001)

    ab = DirEdge(a, b, True)
    bc = DirEdge(b, c, True)
    ca = DirEdge(c, a, True)
    
    print("AB ID:", ab.id)
    print("BC ID:", bc.id)
    print("CA ID:", ca.id)
    
    print("AB Length: {:.2f} meters".format(ab.getLength()))
    print("BC Length: {:.2f} meters".format(bc.getLength()))
    print("CA Length: {:.2f} meters".format(ca.getLength()))

    print("AB connected to BC (should be true):", ab.isConnectedTo(bc))
    print("AB connected to CA (should be false):", ab.isConnectedTo(ca))

    DirEdgeArr = [ab, bc, ca]
    print("Before stitching:")
    for edge in DirEdgeArr:
        print(f"  {edge.id}: {edge.next_edges}")
    
    _stitch(DirEdgeArr, DirEdgeArr)
    print("After stitching:")
    for edge in DirEdgeArr:
        print(f"  {edge.id}: {edge.next_edges}")
        
"""
