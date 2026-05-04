"""test_visual_logic.py

Artificial grid simulations visually verifying JeepSystem and Passenger state logic on Rectangular routes.
Test 1: Walk vs Ride (State Transitions).
Test 2: Detour Heuristic (Dynamic Substitution via Weight Tolerance).
Test 3: The Multi-Hop Transfer (Two intersecting square routes).
Test 4: The Overcrowded Hub (Queue processing with partially full jeeps).
"""

import random
from utils.node import Node
from utils.jeep import Jeep
from utils.passenger import Passenger
from utils.jeep_system import JeepSystem
from utils.visualizer import LiveVisualizer

# --- ARTIFICIAL GRID MOCKS ---

class MockEdge:
    def __init__(self, start: Node, end: Node, edge_id: str, weight: float = 100.0):
        self.start = start
        self.end = end
        self.id = edge_id
        self.weight = weight
        self.is_drivable = True

    def getLength(self) -> float:
        return self.weight

class MockRoute:
    def __init__(self, path: list[MockEdge]):
        self.path = path

def make_node(x: float, y: float, nid: str) -> Node:
    # x maps to Longitude, y maps to Latitude
    BASE_LAT = 8.2200
    BASE_LON = 124.2400
    SCALE = 0.002
    n = Node(BASE_LON + (x * SCALE), BASE_LAT + (y * SCALE))
    n.id = nid
    return n

def add_jitter(node: Node) -> tuple[float, float]:
    """Adds visual spread so stacked passengers look like a crowd."""
    olat = random.uniform(-0.0001, 0.0001)
    olon = random.uniform(-0.0001, 0.0001)
    return (node.lat + olat, node.lon + olon)


# --- TEST SCENARIOS ---

def run_test_1() -> None:
    print("\n" + "="*60)
    print("TEST 1: WALK VS RIDE (RECTANGULAR ROUTE)")
    print("Passenger 1 (Fast Walker): Walks from A to B.")
    print("Passenger 2 (Lazy): Waits at A, Rides to C.")
    print("Passenger 3 (Hybrid): Walks A to B, waits, rides to D.")
    print("="*60)
    
    # Rectangular Route: A(0,0) -> B(0,2) -> C(3,2) -> D(3,0) -> A
    A = make_node(0, 0, "A")
    B = make_node(0, 2, "B")
    C = make_node(3, 2, "C")
    D = make_node(3, 0, "D")

    r0_0 = MockEdge(A, B, "RI_R0_0", weight=200.0)
    r0_1 = MockEdge(B, C, "RI_R0_1", weight=300.0)
    r0_2 = MockEdge(C, D, "RI_R0_2", weight=200.0)
    r0_3 = MockEdge(D, A, "RI_R0_3", weight=300.0)
    route0 = MockRoute([r0_0, r0_1, r0_2, r0_3])

    # Passenger 1: Pure Walk
    j1 = [MockEdge(A, B, "SW_AB", weight=200.0)]
    p1 = Passenger(start_pos=(A.lat, A.lon), journey=j1, speed=2.0)
    
    # Passenger 2: Pure Ride
    j2 = [MockEdge(A, A, "WA_A"), r0_0, r0_1, MockEdge(C, C, "AL_C")]
    p2 = Passenger(start_pos=(A.lat, A.lon), journey=j2, speed=2.0)
    
    # Passenger 3: Walk then Ride
    j3 = [MockEdge(A, B, "SW_AB", weight=200.0), MockEdge(B, B, "WA_B"), r0_1, r0_2, MockEdge(D, D, "AL_D")]
    p3 = Passenger(start_pos=(A.lat, A.lon), journey=j3, speed=2.0)

    for p in [p1, p2, p3]: p.update()

    # Jeep spawns behind A so walkers get a head start
    jeep = Jeep(route0, currPos=(D.lat, D.lon), speed=10.0)
    system = JeepSystem([jeep], [route0], weight_tolerance=0.0)
    for p in [p1, p2, p3]: system.add_passenger(p)

    vis = LiveVisualizer(
        area_query="Iligan City", title="Test 1: Walk vs Ride",
        nodes=[A, B, C, D], edges=[r0_0, r0_1, r0_2, r0_3], 
        routes=[route0], jeeps=[jeep], passengers=[p1, p2, p3],
        system_manager=system, mode="light_nolabels"
    )
    vis.display()


def run_test_2() -> None:
    print("\n" + "="*60)
    print("TEST 2: DETOUR HEURISTIC (VARYING BENDS)")
    print("Standard Route (Planned): Weight 400.")
    print("Jeep 1 arrives first on 'Crazy' detour (Weight 1000). Rejected.")
    print("Jeep 2 arrives next on 'Slight' detour (Weight 500). Accepted.")
    print("="*60)
    
    A = make_node(0, 0, "A")
    B = make_node(0, 2, "B")
    C = make_node(2, 2, "C")
    D = make_node(2, 0, "D")
    
    # Route 0 (Standard Rectangle)
    r0_0 = MockEdge(A, B, "RI_R0_0", weight=200.0)
    r0_1 = MockEdge(B, C, "RI_R0_1", weight=200.0)
    r0_2 = MockEdge(C, D, "RI_R0_2", weight=200.0)
    r0_3 = MockEdge(D, A, "RI_R0_3", weight=200.0)
    route0 = MockRoute([r0_0, r0_1, r0_2, r0_3])

    # Route 1 (Crazy Jagged Detour)
    M, N, O = make_node(-2, 0, "M"), make_node(-2, 4, "N"), make_node(2, 4, "O")
    r1_0 = MockEdge(A, M, "RI_R1_0", weight=200.0)
    r1_1 = MockEdge(M, N, "RI_R1_1", weight=400.0)
    r1_2 = MockEdge(N, O, "RI_R1_2", weight=400.0)
    r1_3 = MockEdge(O, C, "RI_R1_3", weight=200.0)
    r1_4 = MockEdge(C, A, "RI_R1_4", weight=400.0) # Return
    route1 = MockRoute([r1_0, r1_1, r1_2, r1_3, r1_4])

    # Route 2 (Slight Detour)
    X = make_node(1, 1, "X")
    r2_0 = MockEdge(A, X, "RI_R2_0", weight=150.0)
    r2_1 = MockEdge(X, C, "RI_R2_1", weight=150.0)
    r2_2 = MockEdge(C, A, "RI_R2_2", weight=300.0) # Return
    route2 = MockRoute([r2_0, r2_1, r2_2])

    # Plans for Route 0. Weight to C = 400.
    j1 = [MockEdge(A, A, "WA_A"), r0_0, r0_1, MockEdge(C, C, "AL_C")]
    p = Passenger(start_pos=(A.lat, A.lon), journey=j1, speed=2.0)
    p.update()

    # Jeep 1 (Crazy) spawns at A. Tests detour logic immediately.
    jeep1 = Jeep(route1, currPos=(A.lat, A.lon), speed=5.0)
    # Jeep 2 (Slight) spawns behind A. Arrives later.
    jeep2 = Jeep(route2, currPos=(C.lat, C.lon), speed=5.0)

    # Tolerance = 200. Max acceptable = 400+200 = 600.
    # Crazy = 1200 (Fail). Slight = 300 (Pass).
    system = JeepSystem([jeep1, jeep2], [route0, route1, route2], weight_tolerance=200.0)
    system.add_passenger(p)

    vis = LiveVisualizer(
        area_query="Iligan City", title="Test 2: Detour Heuristic",
        nodes=[A, B, C, D, M, N, O, X], 
        edges=[r0_0, r0_1, r0_2, r0_3, r1_0, r1_1, r1_2, r1_3, r1_4, r2_0, r2_1, r2_2], 
        routes=[route0, route1, route2], jeeps=[jeep1, jeep2], passengers=[p],
        system_manager=system, mode="light_nolabels"
    )
    vis.display()


def run_test_3() -> None:
    print("\n" + "="*60)
    print("TEST 3: MULTI-HOP TRANSFER (SQUARE ROUTES)")
    print("Passenger starts on Square 1, transfers at the shared corner (C),")
    print("and boards a new jeep on Square 2 to reach their destination.")
    print("="*60)
    
    # Square 1
    S1_A = make_node(0, 0, "S1_A")
    S1_B = make_node(0, 2, "S1_B")
    Trans = make_node(2, 2, "TransferNode")
    S1_D = make_node(2, 0, "S1_D")

    r0_0 = MockEdge(S1_A, S1_B, "RI_R0_0", weight=200.0)
    r0_1 = MockEdge(S1_B, Trans, "RI_R0_1", weight=200.0)
    r0_2 = MockEdge(Trans, S1_D, "RI_R0_2", weight=200.0)
    r0_3 = MockEdge(S1_D, S1_A, "RI_R0_3", weight=200.0)
    route0 = MockRoute([r0_0, r0_1, r0_2, r0_3])

    # Square 2
    S2_B = make_node(2, 4, "S2_B")
    S2_C = make_node(4, 4, "S2_C")
    S2_D = make_node(4, 2, "S2_D")

    r1_0 = MockEdge(Trans, S2_B, "RI_R1_0", weight=200.0)
    r1_1 = MockEdge(S2_B, S2_C, "RI_R1_1", weight=200.0)
    r1_2 = MockEdge(S2_C, S2_D, "RI_R1_2", weight=200.0)
    r1_3 = MockEdge(S2_D, Trans, "RI_R1_3", weight=200.0)
    route1 = MockRoute([r1_0, r1_1, r1_2, r1_3])

    journey = [
        MockEdge(S1_A, S1_A, "WA_A"),
        r0_0, r0_1, 
        MockEdge(Trans, Trans, "AL_Trans"),
        MockEdge(Trans, Trans, "WA_Trans"),
        r1_0, r1_1,
        MockEdge(S2_C, S2_C, "AL_C")
    ]

    p = Passenger(start_pos=(S1_A.lat, S1_A.lon), journey=journey, speed=5.0)
    p.update() 

    jeep0 = Jeep(route0, currPos=(S1_A.lat, S1_A.lon), speed=5.0)
    jeep1 = Jeep(route1, currPos=(S2_D.lat, S2_D.lon), speed=5.0)
    
    system = JeepSystem([jeep0, jeep1], [route0, route1], weight_tolerance=0.0)
    system.add_passenger(p)

    vis = LiveVisualizer(
        area_query="Iligan City", title="Test 3: Multi-Hop Square Transfer",
        nodes=[S1_A, S1_B, Trans, S1_D, S2_B, S2_C, S2_D], 
        edges=[r0_0, r0_1, r0_2, r0_3, r1_0, r1_1, r1_2, r1_3], 
        routes=[route0, route1], jeeps=[jeep0, jeep1], passengers=[p],
        system_manager=system, mode="light_nolabels"
    )
    vis.display()


def run_test_4() -> None:
    print("\n" + "="*60)
    print("TEST 4: THE OVERCROWDED HUB (QUEUE PROCESSING)")
    print("20 passengers waiting. Jeep 1 arrives holding 10 passengers.")
    print("Jeep 1 boards 6 (hits cap of 16), leaving 14 stranded.")
    print("Jeep 2 arrives empty and cleans up the remaining queue.")
    print("="*60)
    
    A = make_node(0, 0, "A")
    B = make_node(0, 2, "B")
    C = make_node(2, 2, "C")
    D = make_node(2, 0, "D")

    r0_0 = MockEdge(A, B, "RI_R0_0", weight=200.0)
    r0_1 = MockEdge(B, C, "RI_R0_1", weight=200.0)
    r0_2 = MockEdge(C, D, "RI_R0_2", weight=200.0)
    r0_3 = MockEdge(D, A, "RI_R0_3", weight=200.0)
    route0 = MockRoute([r0_0, r0_1, r0_2, r0_3])

    journey = [
        MockEdge(B, B, "WA_B"),
        r0_1, r0_2,
        MockEdge(D, D, "AL_D")
    ]

    passengers = []
    for _ in range(20):
        pos = add_jitter(B)
        p = Passenger(start_pos=pos, journey=journey, speed=5.0)
        p.update() 
        passengers.append(p)

    # Jeep 1 arrives first, already carrying 10 dummy passengers
    jeep1 = Jeep(route0, currPos=(A.lat, A.lon), speed=5.0)
    jeep1.modifyPassenger(10) 
    
    # Jeep 2 arrives shortly after, empty
    jeep2 = Jeep(route0, currPos=(D.lat, D.lon), speed=5.0)

    system = JeepSystem([jeep1, jeep2], [route0], weight_tolerance=0.0)
    for p in passengers:
        system.add_passenger(p)

    vis = LiveVisualizer(
        area_query="Iligan City", title="Test 4: Queue Processing (Overcrowded Hub)",
        nodes=[A, B, C, D], edges=[r0_0, r0_1, r0_2, r0_3], 
        routes=[route0], jeeps=[jeep1, jeep2], passengers=passengers,
        system_manager=system, mode="light_nolabels"
    )
    vis.display()


if __name__ == "__main__":
    run_test_1()
    run_test_2()
    run_test_3()
    run_test_4()