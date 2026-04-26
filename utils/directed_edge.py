from math import radians, sin, cos, sqrt, asin
from typing import Optional

from node import Node

class DirEdge:
    def __init__(
        self,
        start: Node,
        end: Node,
        isDrivable: bool,
        weight: int = 1,
        id: Optional[str] = None,
        nextEdges: Optional[list[DirEdge]] = None,
    ) -> None:
        self.start = start
        self.end = end
        self.isDrivable = isDrivable
        self.weight = weight
        self.id = id if id is not None else f"{start.id}{end.id}"
        self.nextEdges = nextEdges

    def getLength(self) -> float:
        lat1, lon1 = radians(self.start.lat), radians(self.start.lon)
        lat2, lon2 = radians(self.end.lat), radians(self.end.lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371000.0 * c

    def isConnectedTo(self, other: DirEdge) -> bool:
        return self.end is other.start


### TEST CODE ###

if __name__ == "__main__":
    a = Node(120.0, 14.0)
    b = Node(120.0001, 14.0002)
    c = Node(120.0002, 14.0001)

    ab = DirEdge(a, b, True)
    bc = DirEdge(b, c, True)
    ca = DirEdge(c, a, True)
    
    print("AB Length: {:.2f} meters".format(ab.getLength()))
    print("BC Length: {:.2f} meters".format(bc.getLength()))
    print("CA Length: {:.2f} meters".format(ca.getLength()))

    print("AB connected to BC (should be true):", ab.isConnectedTo(bc))
    print("AB connected to CA (should be false):", ab.isConnectedTo(ca))
