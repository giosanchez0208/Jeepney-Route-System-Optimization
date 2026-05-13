"""Quick test for Jeep movement and passenger management.

This file provides a minimal test harness for the Jeep class using mock objects.
For comprehensive diagnostics, see diagnostic_jeep.ipynb.
"""

from utils.jeep import Jeep
from PIL import Image

class FakeNode:
    def __init__(self, lat: float, lon: float) -> None:
        self.lat = lat
        self.lon = lon

    def __repr__(self) -> str:
        return f"Node({self.lat}, {self.lon})"

class FakeEdge:
    def __init__(self, start: FakeNode, end: FakeNode, weight: float = 1.0) -> None:
        self.start = start
        self.end = end
        self.weight = weight

    def getLength(self) -> float:
        dx = self.end.lon - self.start.lon
        dy = self.end.lat - self.start.lat
        return (dx * dx + dy * dy) ** 0.5

class FakeRoute:
    def __init__(self, path: list[FakeEdge], route_id: str = "R_TEST") -> None:
        self.path = path
        self.id = route_id
        self.designated_color = "#FF5733"

n1 = FakeNode(0.0, 0.0)
n2 = FakeNode(0.0, 1.0)
n3 = FakeNode(1.0, 1.0)

e1 = FakeEdge(n1, n2)
e2 = FakeEdge(n2, n3)
e3 = FakeEdge(n3, n1)

route = FakeRoute([e1, e2, e3])

print("Jeep GIF Animation Test\n")

jeep_gif = Jeep(
    route=route, 
    curr_pos=(0.0, 0.0), 
    speed=10.0
)

context = (
    (0.0, 1.0),  # top-left
    (1.0, 0.0)   # bottom-right
)

frames = []

for step in range(40):
    if step % 5 == 0:
        jeep_gif.modify_passenger(1)

    frame = Image.new("RGB", (500, 500), "white")
    frame = jeep_gif.draw(
        context=context, 
        image=frame, 
        radius=15
    )

    frames.append(frame)
    jeep_gif.update()

print(f"Generated {len(frames)} frames.")
frames[0].save("jeep_animation.gif", save_all=True, append_images=frames[1:], duration=120, loop=0)
print("Saved -> jeep_animation.gif")