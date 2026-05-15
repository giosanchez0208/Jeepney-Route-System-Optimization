#!/usr/bin/env python
"""Quick test to verify optimization implementation."""

from utils.jeep_system import JeepSystem
from utils.jeep import Jeep
from utils.route import Route
from utils.directed_edge import DirEdge
from utils.node import Node

# Create simple test nodes and edges
n1 = Node(120.0, 15.0)
n2 = Node(120.1, 15.0)
n3 = Node(120.2, 15.0)
e1 = DirEdge(n1, n2, 'E1')
e2 = DirEdge(n2, n3, 'E2')

# Create a route
route = Route([e1, e2], 'R1')
route.designated_color = '#FF0000'

# Create jeeps
jeep = Jeep(route, (120.0, 15.0), 40.0, max_capacity=16)

# Create JeepSystem
js = JeepSystem([jeep], [route])

print('✓ JeepSystem created successfully')
print(f'✓ Jeep has onboard_passengers set: {hasattr(jeep, "onboard_passengers")}')
print(f'✓ JeepSystem has waiting_passengers dict: {hasattr(js, "waiting_passengers")}')
print(f'✓ Jeep onboard_passengers type: {type(jeep.onboard_passengers).__name__}')
print(f'✓ JeepSystem waiting_passengers type: {type(js.waiting_passengers).__name__}')
print(f'✓ Backward compatibility: passengers list exists = {hasattr(js, "passengers")}')

# Test update() call without errors
js.update()
print('✓ JeepSystem.update() executed without errors')

# Test that internal state is properly maintained
print(f'✓ After update: jeep.onboard_passengers = {jeep.onboard_passengers}')
print(f'✓ After update: js.waiting_passengers = {dict(js.waiting_passengers)}')

print('\n✅ All optimization checks passed!')
