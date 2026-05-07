from math import radians
from typing import Optional

_NODE_ID_COUNTER = 1

def _validate_layer(layer: Optional[int]) -> Optional[int]:
	if layer is None:
		return None
	if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0 or layer > 3:
		raise ValueError("Node.layer must be None or an integer in the range 0..3.")
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

	@property
	def layer(self) -> Optional[int]:
		return self._layer

	@layer.setter
	def layer(self, value: Optional[int]) -> None:
		self._layer = _validate_layer(value)
