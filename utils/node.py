"""Flow: lon/lat -> Node -> identity, layer, and cached coordinate math.

Node(lon: float, lat: float) -> None creates a geospatial point with a
generated id, optional layer, drivability flag, and cached radian values for
distance calculations.

Inputs: longitude and latitude.
Outputs: a Node object with stable identity and coordinate fields.
Imported modules used: math.radians and Optional.
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
