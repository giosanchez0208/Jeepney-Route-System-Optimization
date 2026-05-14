import io
from typing import TYPE_CHECKING, Literal, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from PIL import Image

from .directed_edge import DirEdge

if TYPE_CHECKING:
    from .travel_graph import TravelGraph

MapMode = Literal["light", "light_nolabels", "dark", "dark_nolabels"]

WINDOW_SIZE = 800
_RENDER_DPI = 150
_LAYERS = (1, 2, 3)
_LIGHT_FACE_COLOR = "#f7f7f7"
_DARK_FACE_COLOR = "#171717"
_CITY_EDGE_COLOR = "#CFCFCF"
_TYPE_COLORS = {
    "SW": "#EA4335",
    "WA": "#F29900",
    "RI": "#FBBC05",
    "AL": "#34A853",
    "TR": "#00ACC1",
    "EW": "#4285F4",
    "DI": "#A142F4",
}

_LAYER_BORDER_COLORS = {
    1: "#EA4335",
    2: "#FBBC05",
    3: "#4285F4",
}


class TravelGraph3DVisualizer:
    def __init__(
        self,
        travel_graph: "TravelGraph",
        journey: Optional[list[DirEdge]] = None,
        *,
        mode: MapMode = "light_nolabels",
        edge_thickness: float = 2.6,
        journey_thickness: float = 4.2,
        node_radius: float = 42,
        layer_opacity: float = 0.56,
    ) -> None:
        self.tg = travel_graph
        self.journey = journey or []
        self.mode = mode
        self.edge_thickness = edge_thickness
        self.journey_thickness = journey_thickness
        self.node_radius = node_radius
        self.layer_opacity = layer_opacity

    def draw(
        self,
        *,
        display_walk: bool = True,
        display_wait: bool = True,
        display_ride: bool = True,
        display_alight: bool = True,
        display_end_walk: bool = True,
        display_transfer: bool = True,
        display_direct: bool = True,
        labels_on: bool = False,
        legend_on: bool = True,
        nodes_on: bool = False,
        mode: Optional[MapMode] = None,
        edge_thickness: Optional[float] = None,
        journey_thickness: Optional[float] = None,
        node_radius: Optional[float] = None,
        layer_opacity: Optional[float] = None,
    ) -> Image.Image:
        if not self.tg.cg.nodes:
            raise ValueError("[TRAVEL GRAPH 3D] CityGraph nodes are required for visualization context.")

        mode = self.mode if mode is None else mode
        edge_thickness = self.edge_thickness if edge_thickness is None else edge_thickness
        journey_thickness = self.journey_thickness if journey_thickness is None else journey_thickness
        node_radius = self.node_radius if node_radius is None else node_radius
        layer_opacity = self.layer_opacity if layer_opacity is None else layer_opacity

        flags = {
            "SW": display_walk,
            "WA": display_wait,
            "RI": display_ride,
            "AL": display_alight,
            "EW": display_end_walk,
            "TR": display_transfer,
            "DI": display_direct,
        }

        layer_gap = _layer_gap(self.tg.cg.nodes)
        center_lon, center_lat = _projection_origin(self.tg.cg.nodes)
        points = _collect_points(self.tg.cg.nodes, self.tg.cg.graph, self.journey, layer_gap, center_lon, center_lat)

        fig, ax = _build_figure(points)
        face_color = _DARK_FACE_COLOR if mode.startswith("dark") else _LIGHT_FACE_COLOR
        fig.patch.set_facecolor(face_color)
        ax.set_facecolor(face_color)
        ax.axis("off")
        ax.set_aspect("equal", adjustable="box")

        for layer in _LAYERS:
            _draw_layer_plane(
                ax,
                self.tg.cg.nodes,
                layer,
                layer_gap,
                center_lon,
                center_lat,
                node_radius,
                layer_opacity,
                nodes_on,
            )

        for layer in _LAYERS:
            _draw_city_graph_edges(
                ax,
                self.tg.cg.graph,
                layer,
                layer_gap,
                center_lon,
                center_lat,
                edge_thickness,
            )

        _draw_journey(
            ax,
            self.journey,
            flags,
            layer_gap,
            center_lon,
            center_lat,
            journey_thickness,
            labels_on,
        )

        if legend_on:
            _draw_legend(ax, mode)

        return _render_to_image(fig)


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


def _layer_gap(nodes) -> float:
    lons = [node.lon for node in nodes]
    lats = [node.lat for node in nodes]
    span = max(max(lons) - min(lons), max(lats) - min(lats), 0.001)
    return max(span * 1.12, 0.02)


def _projection_origin(nodes) -> tuple[float, float]:
    lons = [node.lon for node in nodes]
    lats = [node.lat for node in nodes]
    return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


def _collect_points(nodes, edges, journey, layer_gap: float, center_lon: float, center_lat: float) -> list[tuple[float, float]]:
    points = []
    for layer in _LAYERS:
        points.extend(_project_point(node.lon, node.lat, layer, layer_gap, center_lon, center_lat) for node in nodes)

    for layer in _LAYERS:
        for edge in edges:
            points.append(_project_point(edge.start.lon, edge.start.lat, layer, layer_gap, center_lon, center_lat))
            points.append(_project_point(edge.end.lon, edge.end.lat, layer, layer_gap, center_lon, center_lat))

    for edge in journey:
        if edge.start.layer in _LAYERS and edge.end.layer in _LAYERS:
            points.append(_project_point(edge.start.lon, edge.start.lat, edge.start.layer, layer_gap, center_lon, center_lat))
            points.append(_project_point(edge.end.lon, edge.end.lat, edge.end.layer, layer_gap, center_lon, center_lat))

    for layer in _LAYERS:
        points.extend(_layer_border(nodes, layer, layer_gap, center_lon, center_lat))

    return points


def _build_figure(points: list[tuple[float, float]]) -> tuple[plt.Figure, plt.Axes]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    x_pad = max((max(xs) - min(xs)) * 0.12, 0.01)
    y_pad = max((max(ys) - min(ys)) * 0.12, 0.01)
    x_center = (max(xs) + min(xs)) / 2
    y_center = (max(ys) + min(ys)) / 2
    x_extent = max(abs(max(xs) - x_center), abs(min(xs) - x_center)) + x_pad
    y_extent = max(abs(max(ys) - y_center), abs(min(ys) - y_center)) + y_pad

    ratio = x_extent / y_extent if y_extent else 1.0
    if ratio >= 1:
        width_px = WINDOW_SIZE
        height_px = max(int(WINDOW_SIZE / ratio), int(WINDOW_SIZE * 0.55))
    else:
        height_px = WINDOW_SIZE
        width_px = max(int(WINDOW_SIZE * ratio), int(WINDOW_SIZE * 0.55))

    fig, ax = plt.subplots(figsize=(width_px / 100, height_px / 100), dpi=_RENDER_DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(x_center - x_extent, x_center + x_extent)
    ax.set_ylim(y_center - y_extent, y_center + y_extent)
    return fig, ax


def _layer_border(nodes, layer: int, layer_gap: float, center_lon: float, center_lat: float) -> list[tuple[float, float]]:
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


def _draw_layer_plane(
    ax: plt.Axes,
    nodes,
    layer: int,
    layer_gap: float,
    center_lon: float,
    center_lat: float,
    node_radius: float,
    layer_opacity: float,
    nodes_on: bool,
) -> None:
    border = _layer_border(nodes, layer, layer_gap, center_lon, center_lat)
    ax.add_patch(
        Polygon(
            border,
            closed=True,
            fill=False,
            edgecolor=_LAYER_BORDER_COLORS[layer],
            linewidth=1.8,
            alpha=layer_opacity,
            zorder=layer * 3,
        )
    )

    if not nodes_on:
        return

    points = [_project_point(node.lon, node.lat, layer, layer_gap, center_lon, center_lat) for node in nodes]
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    ax.scatter(xs, ys, s=node_radius, c="#6fbaf0", alpha=layer_opacity, zorder=layer * 3 + 1)


def _draw_city_graph_edges(
    ax: plt.Axes,
    edges: list[DirEdge],
    layer: int,
    layer_gap: float,
    center_lon: float,
    center_lat: float,
    edge_thickness: float,
) -> None:
    segments = []

    for edge in edges:
        start = _project_point(edge.start.lon, edge.start.lat, layer, layer_gap, center_lon, center_lat)
        end = _project_point(edge.end.lon, edge.end.lat, layer, layer_gap, center_lon, center_lat)
        segments.append((start, end))

    if segments:
        ax.add_collection(
            LineCollection(
                segments,
                colors=_CITY_EDGE_COLOR,
                linewidths=max(edge_thickness * 0.55, 1.0),
                alpha=0.35,
                zorder=layer * 3 + 0.5,
            )
        )


def _draw_journey(
    ax: plt.Axes,
    journey: list[DirEdge],
    flags: dict[str, bool],
    layer_gap: float,
    center_lon: float,
    center_lat: float,
    journey_thickness: float,
    labels_on: bool,
) -> None:
    if not journey:
        return

    segments = []
    colors = []
    labeled_segments: list[tuple[DirEdge, tuple[tuple[float, float], tuple[float, float]]]] = []

    for edge in journey:
        prefix = edge.id[:2]
        if not flags.get(prefix, False):
            continue
        if edge.start.layer not in _LAYERS or edge.end.layer not in _LAYERS:
            continue

        start = _project_point(edge.start.lon, edge.start.lat, edge.start.layer, layer_gap, center_lon, center_lat)
        end = _project_point(edge.end.lon, edge.end.lat, edge.end.layer, layer_gap, center_lon, center_lat)
        segments.append((start, end))
        colors.append(_TYPE_COLORS.get(prefix, "#FF1744"))
        labeled_segments.append((edge, (start, end)))

    if segments:
        ax.add_collection(LineCollection(segments, colors=colors, linewidths=journey_thickness, zorder=40))

    if labels_on:
        for edge, ((x1, y1), (x2, y2)) in labeled_segments:
            ax.annotate(
                edge.id,
                ((x1 + x2) / 2, (y1 + y2) / 2),
                textcoords="offset points",
                xytext=(0, 6),
                fontsize=7,
            )


def _draw_legend(ax: plt.Axes, mode: MapMode) -> None:
    legend_items = [
        (_TYPE_COLORS["SW"], "start_walk"),
        (_TYPE_COLORS["WA"], "wait"),
        (_TYPE_COLORS["RI"], "ride"),
        (_TYPE_COLORS["AL"], "alight"),
        (_TYPE_COLORS["TR"], "transfer"),
        (_TYPE_COLORS["EW"], "end_walk"),
        (_TYPE_COLORS["DI"], "direct"),
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
