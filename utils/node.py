"""node.py

Public API:
- Node(lon: float, lat: float) -> None creates a geospatial node with
  lon, lat, layer, id, is_drivable, and cached radian coordinates.

Internal API:
- _NODE_ID_COUNTER: module-local id sequence used to assign stable node ids.
"""

from math import radians
from typing import Optional

_NODE_ID_COUNTER = 1

class Node:
	def __init__(self, lon: float, lat: float):
		global _NODE_ID_COUNTER
		self.lon: float = lon
		self.lat: float = lat
		self.layer: Optional[int] = None
		self.id: str = f"N{_NODE_ID_COUNTER:05d}"
		_NODE_ID_COUNTER += 1
		self.is_drivable: bool = True
		self._lon_rad = radians(lon)
		self._lat_rad = radians(lat)
