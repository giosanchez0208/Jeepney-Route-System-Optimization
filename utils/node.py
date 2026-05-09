from math import radians
from typing import Optional

_NODE_ID_COUNTER = 1

def _validate_layer(layer: Optional[int]) -> Optional[int]:
	if layer is None:
		return None
	if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0 or layer > 3:
		raise ValueError(f"[NODE] Invalid layer value {layer}. Must be an integer from 0 to 3, or None.")
	return layer

class Node:
	def __init__(self, lon: float, lat: float, layer: Optional[int] = None):
		global _NODE_ID_COUNTER
		self.lon: float = lon
		self.lat: float = lat
		self._layer: Optional[int] = None
		self.layer = layer
		self.id: str = f"N{_NODE_ID_COUNTER:05d}"
		_NODE_ID_COUNTER += 1

	def __str__(self) -> str:
		return f"Node({self.id}): lon={self.lon}, lat={self.lat}, layer={self.layer}"

	@property
	def layer(self) -> Optional[int]:
		return self._layer

	@layer.setter
	def layer(self, value: Optional[int]) -> None:
		self._layer = _validate_layer(value)
