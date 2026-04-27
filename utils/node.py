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
