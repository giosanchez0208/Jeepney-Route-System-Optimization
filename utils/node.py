from math import isfinite
from uuid import uuid4
from typing import Optional
from PIL import Image, ImageDraw

def _validate_lon(lon: float) -> float:
	if isinstance(lon, bool) or not isinstance(lon, (int, float)) or not isfinite(lon) or lon < -180 or lon > 180:
		raise ValueError(f"[NODE] Invalid lon value {lon}. Must be a number from -180 to 180.")
	return float(lon)

def _validate_lat(lat: float) -> float:
	if isinstance(lat, bool) or not isinstance(lat, (int, float)) or not isfinite(lat) or lat < -90 or lat > 90:
		raise ValueError(f"[NODE] Invalid lat value {lat}. Must be a number from -90 to 90.")
	return float(lat)

def _validate_layer(layer: Optional[int]) -> Optional[int]:
	if layer is None:
		return None
	if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0 or layer > 3:
		raise ValueError(f"[NODE] Invalid layer value {layer}. Must be an integer from 0 to 3, or None.")
	return layer

class Node:
	def __init__(self, lon: float, lat: float, layer: Optional[int] = None):
		self._lon: float = _validate_lon(lon)
		self._lat: float = _validate_lat(lat)
		self._layer: Optional[int] = None
		self.layer = layer
		self.id: str = f"N{uuid4().hex}"

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, Node):
			return NotImplemented
		return self.id == other.id

	def __hash__(self) -> int:
		return hash(self.id)

	def __setattr__(self, name: str, value) -> None:
		if "_lon" in self.__dict__ and "_lat" in self.__dict__ and name in {"lon", "lat", "_lon", "_lat"}:
			raise AttributeError("[NODE] lon and lat are immutable after initialization.")
		super().__setattr__(name, value)

	def __str__(self) -> str:
		return f"Node({self.id}): lon={self.lon}, lat={self.lat}, layer={self.layer}"

	@property
	def lon(self) -> float:
		return self._lon

	@property
	def lat(self) -> float:
		return self._lat

	@property
	def layer(self) -> Optional[int]:
		return self._layer

	@layer.setter
	def layer(self, value: Optional[int]) -> None:
		self._layer = _validate_layer(value)
  
	def draw(self, context: tuple[tuple[float, float], tuple[float, float]], image: Image.Image, color: str = "#AED7FF", radius: int = 1) -> Image.Image:
		if image.width != image.height:
			raise ValueError("[NODE] Image must be square.")

		tl_lon, tl_lat = context[0]
		br_lon, br_lat = context[1]

		lon_range = br_lon - tl_lon
		lat_range = tl_lat - br_lat

		if lon_range == 0 or lat_range == 0:
			return image

		x = (self.lon - tl_lon) / lon_range * image.width
		y = (tl_lat - self.lat) / lat_range * image.height

		draw = ImageDraw.Draw(image)
		draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)

		return image
