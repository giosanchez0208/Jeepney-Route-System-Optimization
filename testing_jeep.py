"""Quick test for Jeep movement and passenger management.

This file provides a minimal test harness for the Jeep class using mock objects.
For comprehensive diagnostics, see diagnostic_jeep.ipynb.
"""

from utils.jeep import Jeep

class FakeNode:
    def __init__(self, lat: float, lon: float) -> None:
        self.lat: float = lat
        self.lon: float = lon

    def __repr__(self) -> str:
        return f"Node({self.lat}, {self.lon})"

class FakeEdge:
    def __init__(self, start: FakeNode, end: FakeNode, weight: float = 1.0) -> None:
        self.start: FakeNode = start
        self.end: FakeNode = end
        self.weight: float = weight

    def getLength(self) -> float:
        dx: float = self.end.lon - self.start.lon
        dy: float = self.end.lat - self.start.lat
        return (dx * dx + dy * dy) ** 0.5

class FakeRoute:
    def __init__(self, path: list[FakeEdge], route_id: str = "R_TEST") -> None:
        self.path: list[FakeEdge] = path
        self.id: str = route_id
        self.designated_color: str = "#FF5733"  # Orange-red for testing

n1 = FakeNode(0.0, 0.0)
n2 = FakeNode(0.0, 1.0)
n3 = FakeNode(1.0, 1.0)

e1 = FakeEdge(n1, n2)
e2 = FakeEdge(n2, n3)
e3 = FakeEdge(n3, n1)

route = FakeRoute([e1, e2, e3])

jeep = Jeep(route=route, curr_pos=(0.0, 0.0), speed=0.3)

print("=" * 50)
print("Jeep Initialization Test")
print("=" * 50)
print(jeep)
print()

print("=" * 50)
print("Jeep Movement Simulation (15 steps)")
print("=" * 50)

for i in range(15):
    jeep.update()

    print(f"\nStep {i+1}")
    print(f"  Position:  {jeep.curr_pos}")
    print(f"  Heading:   {jeep.heading:.2f}°")
    print(f"  Passengers: {jeep.curr_passenger_count}/{jeep.passenger_max}")

    nodes = jeep.nodes_passed_this_frame()
    if nodes:
        print("  Passed nodes:")
        for n, _ in nodes:
            print(f"    -> {n}")

print("\n" + "=" * 50)