"""layered_visualizer.py

Public API:
- WINDOW_SIZE and MapMode define the render size and supported basemap styles.
- LayeredVisualizer(city_graph, journey, ...) renders layered route imagery.
- draw(), display(), and export() are the main external methods.

Internal API:
- _RENDER_DPI, _LAYERS, and the color constants control the layered style.
- _background_for_mode(), _project_point(), _layer_gap(),
  _projection_origin(), _collect_points(), _build_figure(), _draw_layer(),
  _draw_routes(), _draw_journey(), _node_layer(), _route_layer(),
  _journey_color(), _layer_border(), _layer_border_points(), _route_colors(),
  _draw_legend(), _render_to_image(), _save_scaled_image(), _scale_image(),
  _open_window(), _clone_node(), _clone_path(), and _build_demo_journey() are
  implementation helpers.
"""

import io
import tkinter as tk
from pathlib import Path
from random import sample
from typing import Literal, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
from PIL import Image, ImageTk

from .city_graph import CityGraph
from .directed_edge import DirEdge
from .node import Node
WINDOW_SIZE = 800
_RENDER_DPI = 150
_LAYERS = (1, 2, 3)
_LIGHT_FACE_COLOR = "#f7f7f7"
_DARK_FACE_COLOR = "#171717"
MapMode = Literal["street", "terrain", "satellite", "light", "light_nolabels", "dark", "dark_nolabels"]
_GOOGLE_RED = "#EA4335"
_GOOGLE_ORANGE = "#F29900"
_GOOGLE_YELLOW = "#FBBC05"
_GOOGLE_GREEN = "#34A853"
_GOOGLE_BLUE = "#4285F4"
_GOOGLE_PURPLE = "#A142F4"
_GOOGLE_CYAN = "#00ACC1"
_LAYER_EDGE_COLORS = {
	1: _GOOGLE_RED,
	2: _GOOGLE_YELLOW,
	3: _GOOGLE_BLUE,
}
_JUMP_EDGE_COLORS = {
	(1, 2): _GOOGLE_ORANGE,
	(2, 1): _GOOGLE_ORANGE,
	(2, 3): _GOOGLE_GREEN,
	(3, 2): _GOOGLE_CYAN,
	(1, 3): _GOOGLE_PURPLE,
}
_GOOGLE_ROUTE_COLORS = [
	"#EA4335",
	"#FBBC05",
	"#34A853",
	"#4285F4",
	"#F29900",
	"#A142F4",
	"#00ACC1",
	"#E91E63",
	"#3F51B5",
	"#009688",
	"#FF7043",
	"#03A9F4",
	"#8BC34A",
	"#FFC107",
	"#795548",
	"#9E9E9E",
	"#607D8B",
	"#673AB7",
	"#D81B60",
	"#1E88E5",
]


class LayeredVisualizer:
	def __init__(
		self,
		city_graph: CityGraph,
		journey: list[DirEdge],
		title: Optional[str] = None,
		*,
		mode: MapMode = "light_nolabels",
		labels_on: bool = False,
		node_color: str = "#6fbaf0",
		node_radius: float = 40,
		edge_color: str = "#d1d1d1",
		edge_thickness: float = 2,
		journey_color: str = "#d62728",
		journey_thickness: float = 2.0,
		layer_opacity: float = 0.5,
		legend_on: bool = True,
		Routes: Optional[list["Route"]] = None,
		route_thickness: float = 2.0,
		nodes_on: bool = True,
	) -> None:
		self.cg = city_graph
		self.journey = journey
		self.title = title
		self.mode = mode
		self.labels_on = labels_on
		self.node_color = node_color
		self.node_radius = node_radius
		self.edge_color = edge_color
		self.edge_thickness = edge_thickness
		self.journey_color = journey_color
		self.journey_thickness = journey_thickness
		self.layer_opacity = layer_opacity
		self.legend_on = legend_on
		self.Routes = Routes
		self.route_colors = _route_colors(len(Routes)) if Routes is not None else []
		self.route_thickness = route_thickness
		self.nodes_on = nodes_on

	def draw(
		self,
		mode: Optional[MapMode] = None,
		labels_on: Optional[bool] = None,
		node_color: Optional[str] = None,
		node_radius: Optional[float] = None,
		edge_color: Optional[str] = None,
		edge_thickness: Optional[float] = None,
		journey_color: Optional[str] = None,
		journey_thickness: Optional[float] = None,
		layer_opacity: Optional[float] = None,
		legend_on: Optional[bool] = None,
		nodes_on: Optional[bool] = None,
	) -> Image.Image:
		if not self.cg.nodes:
			raise ValueError("Nodes needed to give visualizer context.")

		mode = self.mode if mode is None else mode
		labels_on = self.labels_on if labels_on is None else labels_on
		node_color = self.node_color if node_color is None else node_color
		node_radius = self.node_radius if node_radius is None else node_radius
		edge_color = self.edge_color if edge_color is None else edge_color
		edge_thickness = self.edge_thickness if edge_thickness is None else edge_thickness
		journey_color = self.journey_color if journey_color is None else journey_color
		journey_thickness = self.journey_thickness if journey_thickness is None else journey_thickness
		layer_opacity = self.layer_opacity if layer_opacity is None else layer_opacity
		legend_on = self.legend_on if legend_on is None else legend_on
		nodes_on = self.nodes_on if nodes_on is None else nodes_on

		layer_gap = _layer_gap(self.cg)
		center_lon, center_lat = _projection_origin(self.cg)
		points = _collect_points(self.cg.nodes, self.journey, self.Routes, layer_gap, center_lon, center_lat)
		fig, ax = _build_figure(points)

		face_color = _background_for_mode(mode)
		fig.patch.set_facecolor(face_color)
		ax.set_facecolor(face_color)
		ax.axis("off")
		ax.set_aspect("equal", adjustable="box")

		for layer in _LAYERS:
			_draw_layer(
				ax,
				self.cg.nodes,
				self.cg.graph,
				layer,
				layer_gap,
				center_lon,
				center_lat,
				node_color,
				node_radius,
				edge_color,
				edge_thickness,
				labels_on,
				layer_opacity,
				nodes_on,
			)

		_draw_routes(ax, self.Routes, self.route_colors, layer_gap, center_lon, center_lat, self.route_thickness)
		_draw_journey(
			ax,
			self.journey,
			layer_gap,
			center_lon,
			center_lat,
			journey_color,
			journey_thickness,
			labels_on,
		)
		if legend_on:
			_draw_legend(ax, mode)

		return _render_to_image(fig)

	def display(
		self,
		mode: Optional[MapMode] = None,
		labels_on: Optional[bool] = None,
		node_color: Optional[str] = None,
		node_radius: Optional[float] = None,
		edge_color: Optional[str] = None,
		edge_thickness: Optional[float] = None,
		journey_color: Optional[str] = None,
		journey_thickness: Optional[float] = None,
		layer_opacity: Optional[float] = None,
		legend_on: Optional[bool] = None,
		nodes_on: Optional[bool] = None,
	) -> None:
		image = self.draw(
			mode,
			labels_on,
			node_color,
			node_radius,
			edge_color,
			edge_thickness,
			journey_color,
			journey_thickness,
			layer_opacity,
			legend_on,
			nodes_on,
		)
		_open_window(image, self.title or "Layered Visualizer")

	def export(
		self,
		filename: str,
		mode: Optional[MapMode] = None,
		labels_on: Optional[bool] = None,
		node_color: Optional[str] = None,
		node_radius: Optional[float] = None,
		edge_color: Optional[str] = None,
		edge_thickness: Optional[float] = None,
		journey_color: Optional[str] = None,
		journey_thickness: Optional[float] = None,
		layer_opacity: Optional[float] = None,
		legend_on: Optional[bool] = None,
		nodes_on: Optional[bool] = None,
		scale_up: int = 1,
	) -> None:
		Path(filename).parent.mkdir(parents=True, exist_ok=True)
		image = self.draw(
			mode,
			labels_on,
			node_color,
			node_radius,
			edge_color,
			edge_thickness,
			journey_color,
			journey_thickness,
			layer_opacity,
			legend_on,
			nodes_on,
		)
		_save_scaled_image(image, filename, scale_up)


### HELPER FUNCTIONS ###


def _background_for_mode(mode: MapMode) -> str:
	return _DARK_FACE_COLOR if mode.startswith("dark") else _LIGHT_FACE_COLOR


def _project_point(
	lon: float,
	lat: float,
	layer: int,
	layer_gap: float,
	center_lon: float,
	center_lat: float,
) -> tuple[float, float]:
	shift_lon = lon - center_lon
	shift_lat = lat - center_lat
	layer_offset = (layer - 1) * layer_gap
	return shift_lon - shift_lat, (shift_lon + shift_lat) / 2 + layer_offset


def _layer_gap(city_graph: CityGraph) -> float:
	lons = [node.lon for node in city_graph.nodes]
	lats = [node.lat for node in city_graph.nodes]
	span = max(max(lons) - min(lons), max(lats) - min(lats), 0.001)
	return max(span * 1.15, 0.02)


def _projection_origin(city_graph: CityGraph) -> tuple[float, float]:
	lons = [node.lon for node in city_graph.nodes]
	lats = [node.lat for node in city_graph.nodes]
	return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


def _collect_points(
	nodes: list[Node],
	journey: list[DirEdge],
	routes: Optional[list["Route"]],
	layer_gap: float,
	center_lon: float,
	center_lat: float,
) -> list[tuple[float, float]]:
	points: list[tuple[float, float]] = []

	for layer in _LAYERS:
		points.extend(_project_point(node.lon, node.lat, layer, layer_gap, center_lon, center_lat) for node in nodes)

	for edge in journey:
		start_layer = _node_layer(edge.start)
		end_layer = _node_layer(edge.end)
		points.append(_project_point(edge.start.lon, edge.start.lat, start_layer, layer_gap, center_lon, center_lat))
		points.append(_project_point(edge.end.lon, edge.end.lat, end_layer, layer_gap, center_lon, center_lat))

	for route in routes or []:
		for edge in route.path:
			start_layer = _route_layer(edge.start)
			end_layer = _route_layer(edge.end)
			points.append(_project_point(edge.start.lon, edge.start.lat, start_layer, layer_gap, center_lon, center_lat))
			points.append(_project_point(edge.end.lon, edge.end.lat, end_layer, layer_gap, center_lon, center_lat))

	for layer in _LAYERS:
		points.extend(_layer_border_points(nodes, layer, layer_gap, center_lon, center_lat))

	return points


def _build_figure(points: list[tuple[float, float]]) -> tuple[plt.Figure, plt.Axes]:
	xs = [x for x, _ in points]
	ys = [y for _, y in points]
	x_pad = max((max(xs) - min(xs)) * 0.15, 0.01)
	y_pad = max((max(ys) - min(ys)) * 0.15, 0.01)
	x_center = (max(xs) + min(xs)) / 2
	y_center = (max(ys) + min(ys)) / 2
	x_extent = max(abs(max(xs) - x_center), abs(min(xs) - x_center)) + x_pad
	y_extent = max(abs(max(ys) - y_center), abs(min(ys) - y_center)) + y_pad

	dpi = _RENDER_DPI
	fig, ax = plt.subplots(figsize=(WINDOW_SIZE / 100, WINDOW_SIZE / 100), dpi=dpi)
	fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
	ax.set_xlim(x_center - x_extent, x_center + x_extent)
	ax.set_ylim(y_center - y_extent, y_center + y_extent)
	return fig, ax


def _draw_layer(
	ax: plt.Axes,
	nodes: list[Node],
	edges: list[DirEdge],
	layer: int,
	layer_gap: float,
	center_lon: float,
	center_lat: float,
	node_color: str,
	node_radius: float,
	edge_color: str,
	edge_thickness: float,
	labels_on: bool,
	layer_opacity: float,
	nodes_on: bool,
) -> None:
	layer_edges = edges if layer != 2 else [edge for edge in edges if edge.is_drivable]
	node_points = [_project_point(node.lon, node.lat, layer, layer_gap, center_lon, center_lat) for node in nodes]
	edge_segments = [
		(
			_project_point(edge.start.lon, edge.start.lat, layer, layer_gap, center_lon, center_lat),
			_project_point(edge.end.lon, edge.end.lat, layer, layer_gap, center_lon, center_lat),
		)
		for edge in layer_edges
	]
	layer_border = _layer_border(nodes, layer, layer_gap, center_lon, center_lat)

	xs = [x for x, _ in node_points]
	ys = [y for _, y in node_points]
	ax.add_patch(
		Polygon(
			layer_border,
			closed=True,
			fill=False,
			edgecolor=_LAYER_EDGE_COLORS[layer],
			linewidth=1.5,
			alpha=layer_opacity,
			zorder=layer * 2 - 1,
		)
	)

	if nodes_on:
		ax.scatter(xs, ys, s=node_radius, c=node_color, alpha=layer_opacity, zorder=layer * 2)

		if labels_on:
			for node, (x, y) in zip(nodes, node_points):
				ax.annotate(node.id, (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8, alpha=layer_opacity)

	if edge_segments:
		ax.add_collection(
			LineCollection(
				edge_segments,
				colors=edge_color,
				linewidths=edge_thickness,
				alpha=layer_opacity,
				zorder=layer * 2 + 1,
			)
		)

	if labels_on:
		for edge, ((x1, y1), (x2, y2)) in zip(layer_edges, edge_segments):
			ax.annotate(
				edge.id,
				((x1 + x2) / 2, (y1 + y2) / 2),
				textcoords="offset points",
				xytext=(0, 6),
				fontsize=7,
				alpha=layer_opacity,
			)


def _draw_routes(
	ax: plt.Axes,
	routes: Optional[list["Route"]],
	route_colors: list[str],
	layer_gap: float,
	center_lon: float,
	center_lat: float,
	route_thickness: float,
) -> None:
	if not routes:
		return

	for route, color in zip(routes, route_colors):
		segments = [
			(
				_project_point(edge.start.lon, edge.start.lat, _route_layer(edge.start), layer_gap, center_lon, center_lat),
				_project_point(edge.end.lon, edge.end.lat, _route_layer(edge.end), layer_gap, center_lon, center_lat),
			)
			for edge in route.path
		]
		if segments:
			ax.add_collection(
				LineCollection(
					segments,
					colors=color,
					linewidths=route_thickness,
					capstyle="round",
					joinstyle="round",
					zorder=15,
				)
			)


def _draw_journey(
	ax: plt.Axes,
	journey: list[DirEdge],
	layer_gap: float,
	center_lon: float,
	center_lat: float,
	journey_color: str,
	journey_thickness: float,
	labels_on: bool,
) -> None:
	segments = []
	colors = []
	for edge in journey:
		start_layer = _node_layer(edge.start)
		end_layer = _node_layer(edge.end)
		colors.append(_journey_color(start_layer, end_layer, journey_color))
		segments.append(
			(
				_project_point(edge.start.lon, edge.start.lat, start_layer, layer_gap, center_lon, center_lat),
				_project_point(edge.end.lon, edge.end.lat, end_layer, layer_gap, center_lon, center_lat),
			)
		)

	if segments:
		ax.add_collection(LineCollection(segments, colors=colors, linewidths=journey_thickness, zorder=20))

	if labels_on:
		for edge, ((x1, y1), (x2, y2)) in zip(journey, segments):
			ax.annotate(
				edge.id,
				((x1 + x2) / 2, (y1 + y2) / 2),
				textcoords="offset points",
				xytext=(0, 6),
				fontsize=7,
			)


def _node_layer(node: Node) -> int:
	if node.layer not in _LAYERS:
		raise ValueError("Journey nodes need layer values set to 1, 2, or 3.")
	return node.layer


def _route_layer(node: Node) -> int:
	return 2


def _journey_color(start_layer: int, end_layer: int, fallback: str) -> str:
	if start_layer == end_layer:
		return _LAYER_EDGE_COLORS[start_layer]
	return _JUMP_EDGE_COLORS.get((start_layer, end_layer), fallback)


def _layer_border(
	nodes: list[Node],
	layer: int,
	layer_gap: float,
	center_lon: float,
	center_lat: float,
) -> list[tuple[float, float]]:
	lons = [node.lon for node in nodes]
	lats = [node.lat for node in nodes]
	min_lon, max_lon = min(lons), max(lons)
	min_lat, max_lat = min(lats), max(lats)
	corners = [
		(min_lon, min_lat),
		(max_lon, min_lat),
		(max_lon, max_lat),
		(min_lon, max_lat),
	]
	return [_project_point(lon, lat, layer, layer_gap, center_lon, center_lat) for lon, lat in corners]


def _layer_border_points(
	nodes: list[Node],
	layer: int,
	layer_gap: float,
	center_lon: float,
	center_lat: float,
) -> list[tuple[float, float]]:
	return _layer_border(nodes, layer, layer_gap, center_lon, center_lat)


def _route_colors(count: int) -> list[str]:
	if count <= 0:
		return []

	colors: list[str] = []
	palette = _GOOGLE_ROUTE_COLORS[:]
	while len(colors) < count:
		colors.extend(sample(palette, len(palette)))
	return colors[:count]


def _draw_legend(ax: plt.Axes, mode: MapMode) -> None:
	legend_items = [
		(_GOOGLE_RED, "start_walk"),
		(_GOOGLE_ORANGE, "wait"),
		(_GOOGLE_YELLOW, "ride"),
		(_GOOGLE_GREEN, "alight"),
		(_GOOGLE_CYAN, "transfer"),
		(_GOOGLE_BLUE, "end_walk"),
		(_GOOGLE_PURPLE, "direct"),
	]
	handles = [
		Line2D(
			[0],
			[0],
			linestyle="None",
			marker="s",
			markersize=7,
			markerfacecolor=color,
			markeredgecolor=color,
			label=label,
		)
		for color, label in legend_items
	]
	text_color = "#ffffff" if mode.startswith("dark") else "#111111"
	legend = ax.legend(
		handles=handles,
		loc="upper left",
		bbox_to_anchor=(0.012, 0.988),
		bbox_transform=ax.transAxes,
		frameon=True,
		framealpha=0.9,
		fancybox=True,
		ncol=1,
		handlelength=1.0,
		handletextpad=0.6,
		columnspacing=0.8,
		labelspacing=0.4,
		borderaxespad=0.0,
		fontsize=8,
	)
	legend.get_frame().set_edgecolor("#777777")
	legend.get_frame().set_facecolor(_DARK_FACE_COLOR if mode.startswith("dark") else _LIGHT_FACE_COLOR)
	for text in legend.get_texts():
		text.set_color(text_color)


def _render_to_image(fig: plt.Figure) -> Image.Image:
	buf = io.BytesIO()
	fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
	plt.close(fig)
	buf.seek(0)
	return Image.open(buf).convert("RGBA")


def _save_scaled_image(image: Image.Image, filename: str, scale_up: int) -> None:
	scaled = _scale_image(image, scale_up)
	scaled.save(filename)


def _scale_image(image: Image.Image, scale_up: int) -> Image.Image:
	if scale_up < 1:
		raise ValueError("scale_up must be at least 1.")
	if scale_up == 1:
		return image
	return image.resize((image.width * scale_up, image.height * scale_up), Image.LANCZOS)


def _open_window(image: Image.Image, title: str) -> None:
	image = image.resize((WINDOW_SIZE, WINDOW_SIZE), Image.LANCZOS)

	root = tk.Tk()
	root.title(title)
	root.geometry(f"{WINDOW_SIZE}x{WINDOW_SIZE}")
	root.resizable(False, False)

	photo = ImageTk.PhotoImage(image)
	label = tk.Label(root, image=photo, bd=0)
	label.pack()
	label.image = photo

	root.mainloop()


def _clone_node(node: Node, layer: int, cache: dict[tuple[str, int], Node]) -> Node:
	key = (node.id, layer)
	if key not in cache:
		clone = Node(node.lon, node.lat)
		clone.layer = layer
		cache[key] = clone
	return cache[key]


def _clone_path(path: list[DirEdge], layer: int, cache: dict[tuple[str, int], Node]) -> list[DirEdge]:
	return [
		DirEdge(
			_clone_node(edge.start, layer, cache),
			_clone_node(edge.end, layer, cache),
			edge.is_drivable,
			edge.weight,
		)
		for edge in path
	]


def _build_demo_journey(city_graph: CityGraph) -> list[DirEdge]:
	if len(city_graph.nodes) < 4:
		raise ValueError("At least four nodes are required to build the demo journey.")

	for _ in range(25):
		a, b, c, d = sample(city_graph.nodes, 4)
		cache: dict[tuple[str, int], Node] = {}
		try:
			journey = []
			journey.extend(_clone_path(city_graph.findShortestPath(a, b), 1, cache))
			b1 = _clone_node(b, 1, cache)
			b2 = _clone_node(b, 2, cache)
			journey.append(DirEdge(b1, b2, False))
			journey.extend(_clone_path(city_graph.findShortestPath(b, c), 2, cache))
			c2 = _clone_node(c, 2, cache)
			c3 = _clone_node(c, 3, cache)
			journey.append(DirEdge(c2, c3, False))
			journey.extend(_clone_path(city_graph.findShortestPath(c, d), 3, cache))
			return journey
		except ValueError:
			continue

	raise ValueError("Could not build a demo journey from the available nodes.")


if __name__ == "__main__":
	cg = CityGraph("Iligan City, Lanao del Norte, Philippines")
	journey = _build_demo_journey(cg)

	print(f"CityGraph: {cg.info()}")
	print(f"Journey edges: {len(journey)}")

	visualizer = LayeredVisualizer(
		cg,
		journey,
		title="Layered Route Demo",
		labels_on=False,
		node_radius=1,
		edge_color="#bdbdbd",
		edge_thickness=1,
		journey_color="#d62728",
		journey_thickness=2,
	)
	visualizer.export("results/test/layered_route_demo.png", scale_up=3)
