import io
import tkinter as tk
from functools import lru_cache
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import contextily as ctx
import osmnx as ox
from PIL import Image, ImageTk, ImageSequence
import requests

from typing import Literal, Optional
try:
    from osmnx._errors import InsufficientResponseError
except ImportError:  # pragma: no cover
    class InsufficientResponseError(Exception):
        pass

from directed_edge import DirEdge
from node import Node

WINDOW_SIZE = 800
MapMode = Literal["street", "terrain", "satellite", "light", "light_nolabels", "dark", "dark_nolabels"]
_PROVIDERS = {
    "street": ctx.providers.OpenStreetMap.Mapnik,
    "terrain": ctx.providers.OpenTopoMap,
    "satellite": ctx.providers.Esri.WorldImagery,
    "light": ctx.providers.CartoDB.Positron,
    "light_nolabels": ctx.providers.CartoDB.PositronNoLabels,
    "dark": ctx.providers.CartoDB.DarkMatter,
    "dark_nolabels": ctx.providers.CartoDB.DarkMatterNoLabels,
}


class StaticVisualizer:
    def __init__(
        self,
        Nodes: list[Node],
        DirEdges: list[DirEdge],
        title: Optional[str] = None,
        *,
        query: Optional[str] = None,
        mode: MapMode = "light_nolabels",
        labels_on: bool = False,
        node_color: str = "#6fbaf0",
        node_radius: float = 40,
        edge_color: str = "#d1d1d1",
        edge_thickness: float = 2,
        landmarks: Optional[str] = None,
    ) -> None:
        self.Nodes = Nodes
        self.DirEdges = DirEdges
        self.title = title
        self.query = query
        self.mode = mode
        self.labels_on = labels_on
        self.node_color = node_color
        self.node_radius = node_radius
        self.edge_color = edge_color
        self.edge_thickness = edge_thickness
        self.landmarks = landmarks

    def draw(
        self,
        mode: Optional[MapMode] = None,
        labels_on: Optional[bool] = None,
        node_color: Optional[str] = None,
        node_radius: Optional[float] = None,
        edge_color: Optional[str] = None,
        edge_thickness: Optional[float] = None,
        landmarks: Optional[str] = None,
    ) -> Image.Image:
        if not self.Nodes:
            raise ValueError("Nodes needed to give visualizer context for basemap.")

        mode = self.mode if mode is None else mode
        labels_on = self.labels_on if labels_on is None else labels_on
        node_color = self.node_color if node_color is None else node_color
        node_radius = self.node_radius if node_radius is None else node_radius
        edge_color = self.edge_color if edge_color is None else edge_color
        edge_thickness = self.edge_thickness if edge_thickness is None else edge_thickness
        landmarks = self.landmarks if landmarks is None else landmarks

        lats = [node.lat for node in self.Nodes]
        lons = [node.lon for node in self.Nodes]
        bounds = _map_bounds(lats, lons)
        landmark_points = _resolve_landmarks(landmarks, area_query=self.query, bounds=bounds)
        if landmark_points:
            lats.extend(lat for _, lat, _ in landmark_points)
            lons.extend(lon for _, _, lon in landmark_points)

        fig, ax = _build_figure(lats, lons)

        _add_basemap_or_blank(ax, mode)
        _draw_nodes(ax, self.Nodes, node_color, node_radius, labels_on)
        _draw_edges(ax, self.DirEdges, edge_color, edge_thickness, labels_on)
        _draw_landmarks(ax, landmark_points)

        return _render_to_image(fig)

    def display(
        self,
        mode: Optional[MapMode] = None,
        labels_on: Optional[bool] = None,
        node_color: Optional[str] = None,
        node_radius: Optional[float] = None,
        edge_color: Optional[str] = None,
        edge_thickness: Optional[float] = None,
        landmarks: Optional[str] = None,
    ) -> None:
        image = self.draw(mode, labels_on, node_color, node_radius, edge_color, edge_thickness, landmarks)
        _open_window(image, self.title or "Static Visualizer")

    def export(
        self,
        filename: str,
        mode: Optional[MapMode] = None,
        labels_on: Optional[bool] = None,
        node_color: Optional[str] = None,
        node_radius: Optional[float] = None,
        edge_color: Optional[str] = None,
        edge_thickness: Optional[float] = None,
        landmarks: Optional[str] = None,
        scale_up: int = 1,
    ) -> None:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        image = self.draw(mode, labels_on, node_color, node_radius, edge_color, edge_thickness, landmarks)
        _save_scaled_image(image, filename, scale_up)


class DynamicVisualizer:
    def __init__(self, StaticVisualizers: list[StaticVisualizer], title: Optional[str] = None) -> None:
        self.StaticVisualizers = StaticVisualizers
        self.title = title
        self.frames: list[Image.Image] = []
        self.gif: Optional[io.BytesIO] = None

    def draw(self, mode: MapMode = "light_nolabels", fps: int = 2) -> Image.Image:
        if not self.StaticVisualizers:
            raise ValueError("At least one static visualizer is required to build a GIF.")

        duration = max(1, round(1000 / fps))
        self.frames = [visualizer.draw(mode) for visualizer in self.StaticVisualizers]
        self.gif = _frames_to_gif(self.frames, duration=duration)
        self.gif.seek(0)
        return Image.open(self.gif)

    def display(self, mode: MapMode = "light_nolabels", fps: int = 2) -> None:
        image = self.draw(mode, fps)
        _open_gif_window(image, self.title or "Dynamic Visualizer")

    def export(self, filename: str, mode: MapMode = "light_nolabels", fps: int = 2, scale_up: int = 1) -> None:
        duration = max(1, round(1000 / fps))
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        image = self.draw(mode, fps)
        _save_scaled_gif(image, self.frames, filename, scale_up=scale_up, duration=duration)



### HELPER FUNCTIONS ###

def _get_provider(mode: MapMode):
    return _PROVIDERS[mode]


def _build_figure(lats: list[float], lons: list[float]) -> tuple[plt.Figure, plt.Axes]:
    lat_pad = max((max(lats) - min(lats)) * 0.15, 0.001)
    lon_pad = max((max(lons) - min(lons)) * 0.15, 0.001)

    dpi = 100
    fig, ax = plt.subplots(figsize=(WINDOW_SIZE / dpi, WINDOW_SIZE / dpi), dpi=dpi)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(min(lons) - lon_pad, max(lons) + lon_pad)
    ax.set_ylim(min(lats) - lat_pad, max(lats) + lat_pad)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    return fig, ax


def _draw_nodes(ax: plt.Axes, nodes: list[Node], node_color: str, node_radius: float, labels_on: bool) -> None:
    ax.scatter([node.lon for node in nodes], [node.lat for node in nodes], s=node_radius, c=node_color, zorder=3)
    if labels_on:
        for node in nodes:
            ax.annotate(node.id, (node.lon, node.lat), textcoords="offset points", xytext=(5, 5), fontsize=8)


def _draw_edges(ax: plt.Axes, edges: list[DirEdge], edge_color: str, edge_thickness: float, labels_on: bool) -> None:
    segments = [((edge.start.lon, edge.start.lat), (edge.end.lon, edge.end.lat)) for edge in edges]
    if segments:
        ax.add_collection(LineCollection(segments, colors=edge_color, linewidths=edge_thickness, zorder=2))

    if labels_on:
        for edge in edges:
            mid_lon = (edge.start.lon + edge.end.lon) / 2
            mid_lat = (edge.start.lat + edge.end.lat) / 2
            ax.annotate(edge.id, (mid_lon, mid_lat), textcoords="offset points", xytext=(0, 6), fontsize=7)


def _draw_landmarks(ax: plt.Axes, landmarks: list[tuple[str, float, float]]) -> None:
    for label, lat, lon in landmarks:
        ax.text(
            lon,
            lat,
            label,
            fontsize=7,
            fontweight="bold",
            color="black",
            ha="center",
            va="center",
            zorder=4,
        )


def _resolve_landmarks(
    landmarks: Optional[str],
    *,
    area_query: Optional[str] = None,
    bounds: Optional[tuple[float, float, float, float]] = None,
) -> list[tuple[str, float, float]]:
    if landmarks is None:
        return []

    labels = [label.strip() for label in landmarks.split(",") if label.strip()]
    resolved = []
    for label in labels:
        candidate_queries = [label]
        if area_query:
            candidate_queries.insert(0, f"{label}, {area_query}")
            candidate_queries.append(f"{label} near {area_query}")

        for candidate_query in candidate_queries:
            try:
                resolved_point = _geocode_landmark(candidate_query, label)
            except ValueError:
                continue
            if bounds is not None and not _within_bounds(resolved_point[1], resolved_point[2], bounds):
                continue
            resolved.append(resolved_point)
            break
    return resolved


@lru_cache(maxsize=256)
def _geocode_landmark(query: str, label: str) -> tuple[str, float, float]:
    try:
        place = ox.geocode_to_gdf(query)
        if place.empty:
            raise ValueError

        geometry = place.iloc[0].geometry
        centroid = geometry.centroid
        return label, centroid.y, centroid.x
    except (TypeError, ValueError, IndexError, AttributeError, InsufficientResponseError):
        try:
            lat, lon = ox.geocode(query)
        except (TypeError, ValueError, IndexError, AttributeError, InsufficientResponseError) as exc:
            raise ValueError(f"Could not geocode landmark query: {label}") from exc
        return label, lat, lon


def _within_bounds(lat: float, lon: float, bounds: tuple[float, float, float, float]) -> bool:
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def _map_bounds(lats: list[float], lons: list[float]) -> tuple[float, float, float, float]:
    lat_pad = max((max(lats) - min(lats)) * 0.15, 0.001)
    lon_pad = max((max(lons) - min(lons)) * 0.15, 0.001)
    return min(lats) - lat_pad, max(lats) + lat_pad, min(lons) - lon_pad, max(lons) + lon_pad


def _add_basemap_or_blank(ax: plt.Axes, mode: MapMode) -> None:
    try:
        ctx.add_basemap(ax, crs="EPSG:4326", source=_get_provider(mode), zorder=1)
    except (requests.RequestException, OSError, ValueError):
        ax.set_facecolor("#f7f7f7")


def _render_to_image(fig: plt.Figure) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


def _save_scaled_image(image: Image.Image, filename: str, scale_up: int) -> None:
    scaled = _scale_image(image, scale_up)
    scaled.save(filename)


def _save_scaled_gif(image: Image.Image, frames: list[Image.Image], filename: str, scale_up: int, duration: int) -> None:
    scaled_frames = [_scale_image(frame, scale_up).convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    if not scaled_frames:
        raise ValueError("No frames available to build a GIF.")

    first, *rest = scaled_frames
    first.save(
        filename,
        format="GIF",
        save_all=True,
        append_images=rest,
        duration=duration,
        loop=0,
        disposal=2,
    )


def _scale_image(image: Image.Image, scale_up: int) -> Image.Image:
    if scale_up < 1:
        raise ValueError("scale_up must be at least 1.")
    if scale_up == 1:
        return image
    return image.resize((image.width * scale_up, image.height * scale_up), Image.LANCZOS)


def _frames_to_gif(frames: list[Image.Image], duration: int = 400) -> io.BytesIO:
    if not frames:
        raise ValueError("No frames available to build a GIF.")

    buf = io.BytesIO()
    first, *rest = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    first.save(
        buf,
        format="GIF",
        save_all=True,
        append_images=rest,
        duration=duration,
        loop=0,
        disposal=2,
    )
    return buf


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


def _open_gif_window(image: Image.Image, title: str) -> None:
    root = tk.Tk()
    root.title(title)
    root.geometry(f"{WINDOW_SIZE}x{WINDOW_SIZE}")
    root.resizable(False, False)

    frames = [frame.copy().resize((WINDOW_SIZE, WINDOW_SIZE), Image.LANCZOS) for frame in ImageSequence.Iterator(image)]
    if not frames:
        raise ValueError("GIF has no frames.")

    label = tk.Label(root, bd=0)
    label.pack()

    photos = [ImageTk.PhotoImage(frame) for frame in frames]

    def animate(index: int = 0) -> None:
        label.configure(image=photos[index])
        root.after(image.info.get("duration", 400), animate, (index + 1) % len(photos))

    animate()
    root.mainloop()

"""

### SANITY CHECK ###

if __name__ == "__main__":
    a = Node(120.985, 14.599)
    b = Node(120.990, 14.604)

    edge = DirEdge(a, b, True)
    visualizer = StaticVisualizer([a, b], [edge], title="Test Map")

    visualizer.display(labels_on=False)
    
    nodes = [
        Node(120.980, 14.598),
        Node(120.984, 14.600),
        Node(120.988, 14.603),
        Node(120.992, 14.606),
    ]

    gif_frames = []
    for start in nodes:
        for end in nodes:
            if start is not end:
                gif_frames.append(
                    StaticVisualizer(
                        nodes,
                        [DirEdge(start, end, True)],
                        title=f"GIF Frame {start.id} to {end.id}",
                    )
                )
                
    gif_visualizer = DynamicVisualizer(gif_frames, title="GIF Test")
    gif_visualizer.display("light_nolabels", fps=10)
"""
