"""visualizer.py

WINDOW_SIZE: int and _RENDER_SCALE: int control output size, MapMode: Literal[...] describes basemap modes.
Passenger(curr_lon: float, curr_lat: float) -> None is a dummy class for passenger tracking.
StaticVisualizer(area_query, ...) -> None creates the static map state.
DynamicVisualizer(StaticVisualizers, ...) -> None creates a GIF visualizer.
LiveVisualizer(area_query, ...) -> None creates an asynchronous parallel simulation visualizer with recording capabilities.
"""

import io
import threading
import time
from datetime import datetime
import tkinter as tk
from functools import lru_cache
from pathlib import Path
from random import sample
from typing import Literal, Optional, Any

import contextily as ctx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PathCollection
from matplotlib.markers import MarkerStyle
from matplotlib.transforms import Affine2D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import osmnx as ox
import requests
from PIL import Image, ImageTk, ImageSequence

try:
    from osmnx._errors import InsufficientResponseError
except ImportError:  # pragma: no cover
    class InsufficientResponseError(Exception):
        pass

from .directed_edge import DirEdge
from .node import Node
from .route import Route
from .jeep import Jeep

WINDOW_SIZE = 800
_RENDER_SCALE = 2
MapMode = Literal["street", "terrain", "satellite", "light", "light_nolabels", "dark", "dark_nolabels"]

_GOOGLE_ROUTE_COLORS = [
    "#EA4335", "#FBBC05", "#34A853", "#4285F4", "#F29900",
    "#A142F4", "#00ACC1", "#E91E63", "#3F51B5", "#009688"
]
_NODE_COLOR = "#4285F4"       
_EDGE_COLOR = "#9E9E9E"       
_JEEP_COLOR = "#EA4335"       
_PASSENGER_COLOR = "#34A853"  

_PROVIDERS = {
    "street": ctx.providers.OpenStreetMap.Mapnik,
    "terrain": ctx.providers.OpenTopoMap,
    "satellite": ctx.providers.Esri.WorldImagery,
    "light": ctx.providers.CartoDB.Positron,
    "light_nolabels": ctx.providers.CartoDB.PositronNoLabels,
    "dark": ctx.providers.CartoDB.DarkMatter,
    "dark_nolabels": ctx.providers.CartoDB.DarkMatterNoLabels,
}

class Passenger:
    def __init__(self, curr_lon: float, curr_lat: float) -> None:
        self.curr_lon = curr_lon
        self.curr_lat = curr_lat

class StaticVisualizer:
    def __init__(
        self,
        area_query: str,
        title: Optional[str] = None,
        nodes: Optional[list[Node]] = None,
        edges: Optional[list[DirEdge]] = None,
        routes: Optional[list[Route]] = None,
        jeeps: Optional[list[Jeep]] = None,
        passengers: Optional[list[Any]] = None,
        system_manager: Optional[Any] = None,
        mode: MapMode = "light_nolabels",
    ) -> None:
        self.area_query = area_query
        self.title = title
        self.nodes = nodes or []
        self.edges = edges or []
        self.routes = routes or []
        self.jeeps = jeeps or []
        self.passengers = passengers or []
        self.system_manager = system_manager
        self.mode = mode
        self.route_colors = _route_colors(len(self.routes))

    def draw(self, mode: Optional[MapMode] = None) -> Image.Image:
        lats, lons = _extract_all_coords(self.nodes, self.edges, self.routes, self.jeeps, self.passengers)
        if lats and lons:
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
        else:
            min_lat, max_lat, min_lon, max_lon = _get_bounds(self.area_query)

        fig, ax = _build_figure(min_lat, max_lat, min_lon, max_lon)

        _add_basemap_or_blank(ax, mode or self.mode)
        _draw_edges(ax, self.edges)
        _draw_routes(ax, self.routes, self.route_colors)
        _draw_nodes(ax, self.nodes)
        _draw_passengers(ax, self.passengers)
        _draw_jeeps_static(ax, self.jeeps, self.routes, self.route_colors)

        return _render_to_image(fig)

    def display(self, mode: Optional[MapMode] = None) -> None:
        image = self.draw(mode)
        _open_window(image, self.title or "Static Visualizer")

    def export(self, filename: str, mode: Optional[MapMode] = None, scale_up: int = 1) -> None:
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        image = self.draw(mode)
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


class LiveVisualizer:
    def __init__(
        self,
        area_query: str,
        title: Optional[str] = None,
        nodes: Optional[list[Node]] = None,
        edges: Optional[list[DirEdge]] = None,
        routes: Optional[list[Route]] = None,
        jeeps: Optional[list[Jeep]] = None,
        passengers: Optional[list[Any]] = None,
        system_manager: Optional[Any] = None,
        mode: MapMode = "light_nolabels",
        sim_tick_rate: float = 0.05, 
        render_fps: int = 30
    ) -> None:
        self.area_query = area_query
        self.title = title
        self.nodes = nodes or []
        self.edges = edges or []
        self.routes = routes or []
        self.jeeps = jeeps or []
        self.passengers = passengers or []
        self.system_manager = system_manager
        self.mode = mode
        self.route_colors = _route_colors(len(self.routes))
        
        self.sim_tick_rate = sim_tick_rate
        self.render_fps = render_fps
        
        self.lock = threading.Lock()
        self._running = False
        self._recording = False
        self._recorded_frames = []

    def display(self) -> None:
        lats, lons = _extract_all_coords(self.nodes, self.edges, self.routes, self.jeeps, self.passengers)
        if lats and lons:
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
        else:
            min_lat, max_lat, min_lon, max_lon = _get_bounds(self.area_query)

        fig, ax = _build_figure(min_lat, max_lat, min_lon, max_lon)

        _add_basemap_or_blank(ax, self.mode)
        _draw_edges(ax, self.edges)
        _draw_routes(ax, self.routes, self.route_colors)
        _draw_nodes(ax, self.nodes)

        j_colors = _get_jeep_colors(self.jeeps, self.routes, self.route_colors)
        if self.jeeps:
            lons = [j.currPos[1] for j in self.jeeps]
            lats = [j.currPos[0] for j in self.jeeps]
            self._jeep_scatter = ax.scatter(lons, lats, marker="^", s=5, c=j_colors, zorder=6)
        else:
            self._jeep_scatter = None

        self._jeep_texts = []
        for j, color in zip(self.jeeps, j_colors):
            tc = _get_contrast_color(color)
            txt = ax.text(j.currPos[1], j.currPos[0], str(getattr(j, 'curr_passenger_count', 0)), 
                          color=tc, fontsize=5, fontweight='bold', ha='center', va='bottom', zorder=7)
            self._jeep_texts.append(txt)

        p_lons = [p.curr_lon for p in self.passengers]
        p_lats = [p.curr_lat for p in self.passengers]
        self._pass_scatter = ax.scatter(p_lons, p_lats, marker="o", s=3, c=_PASSENGER_COLOR, zorder=5)

        root = tk.Tk()
        root.title(self.title or "Live Visualizer")
        root.geometry(f"{WINDOW_SIZE}x{WINDOW_SIZE}")
        root.resizable(False, False)

        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True)

        self._running = True

        def _sim_loop():
            while self._running:
                start_time = time.time()
                with self.lock:
                    if self.system_manager:
                        self.system_manager.update()
                    else:
                        for j in self.jeeps:
                            j.update()
                        for p in self.passengers:
                            if hasattr(p, 'update'):
                                p.update()
                elapsed = time.time() - start_time
                sleep_time = max(0.0, self.sim_tick_rate - elapsed)
                time.sleep(sleep_time)

        sim_thread = threading.Thread(target=_sim_loop, daemon=True)
        sim_thread.start()

        def _render_loop():
            if not self._running:
                return

            with self.lock:
                j_offsets = [[j.currPos[1], j.currPos[0]] for j in self.jeeps]
                p_offsets = [[p.curr_lon, p.curr_lat] for p in self.passengers]
                j_headings = [j.heading for j in self.jeeps]
                j_counts = [getattr(j, 'curr_passenger_count', 0) for j in self.jeeps]

            if self._jeep_scatter and j_offsets:
                self._jeep_scatter.set_offsets(j_offsets)
                base_path = MarkerStyle('^').get_path()
                paths = [base_path.transformed(Affine2D().rotate_deg(h)) for h in j_headings]
                self._jeep_scatter.set_paths(paths)

            for txt, offset, count in zip(self._jeep_texts, j_offsets, j_counts):
                txt.set_position(offset)
                txt.set_text(str(count))

            if self._pass_scatter:
                self._pass_scatter.set_offsets(p_offsets if p_offsets else np.empty((0, 2)))

            canvas.draw_idle()

            if self._recording:
                width, height = fig.canvas.get_width_height()
                buf = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8).reshape(height, width, 3)
                self._recorded_frames.append(Image.fromarray(buf))

            self._after_id = root.after(int(1000 / self.render_fps), _render_loop)

        def _toggle_record(event):
            self._recording = not self._recording
            if self._recording:
                self._recorded_frames = []
                print("Recording started...")
            else:
                print("Recording stopped. Saving to background thread...")
                frames = self._recorded_frames.copy()
                threading.Thread(target=self._save_recording, args=(frames,), daemon=True).start()

        def _on_closing():
            self._running = False
            if hasattr(self, '_after_id'):
                root.after_cancel(self._after_id)
            root.destroy()

        root.bind("<r>", _toggle_record)
        root.protocol("WM_DELETE_WINDOW", _on_closing)
        
        _render_loop()
        root.mainloop()
        sim_thread.join(timeout=1.0)

    def _save_recording(self, frames: list[Image.Image]) -> None:
        if not frames:
            return
        out_dir = Path("results/recordings")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = out_dir / f"record_{timestamp}.gif"
        _save_scaled_gif(frames[0], frames, str(filename), scale_up=1, duration=int(1000 / self.render_fps))
        print(f"Recording saved successfully to {filename}")


### HELPER FUNCTIONS ###

def _get_contrast_color(hex_color: str) -> str:
    # hex_color = hex_color.lstrip('#')
    # r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    # luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    # quick patch
    return 'black'

def _get_jeep_colors(jeeps: list[Jeep], routes: list[Route], route_colors: list[str]) -> list[str]:
    colors = []
    for j in jeeps:
        try:
            idx = routes.index(j.route)
            colors.append(route_colors[idx])
        except ValueError:
            colors.append(_JEEP_COLOR)
    return colors

def _extract_all_coords(nodes, edges, routes, jeeps, passengers) -> tuple[list[float], list[float]]:
    lats, lons = [], []
    for n in nodes:
        lats.append(n.lat)
        lons.append(n.lon)
    for e in edges:
        lats.extend([e.start.lat, e.end.lat])
        lons.extend([e.start.lon, e.end.lon])
    for r in routes:
        for e in r.path:
            lats.extend([e.start.lat, e.end.lat])
            lons.extend([e.start.lon, e.end.lon])
    for j in jeeps:
        lats.append(j.currPos[0])
        lons.append(j.currPos[1])
    for p in passengers:
        lats.append(p.curr_lat)
        lons.append(p.curr_lon)
    return lats, lons

@lru_cache(maxsize=32)
def _get_bounds(area_query: str) -> tuple[float, float, float, float]:
    try:
        place = ox.geocode_to_gdf(area_query)
        min_lon, min_lat, max_lon, max_lat = place.total_bounds
        return min_lat, max_lat, min_lon, max_lon
    except (TypeError, ValueError, IndexError, AttributeError, InsufficientResponseError):
        lat, lon = ox.geocode(area_query)
        pad = 0.05
        return lat - pad, lat + pad, lon - pad, lon + pad

def _get_provider(mode: MapMode):
    return _PROVIDERS[mode]

def _build_figure(min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> tuple[plt.Figure, plt.Axes]:
    lat_pad = max((max_lat - min_lat) * 0.10, 0.002)
    lon_pad = max((max_lon - min_lon) * 0.10, 0.002)

    dpi = 100 * _RENDER_SCALE
    fig, ax = plt.subplots(figsize=(WINDOW_SIZE / dpi, WINDOW_SIZE / dpi), dpi=dpi)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(min_lon - lon_pad, max_lon + lon_pad)
    ax.set_ylim(min_lat - lat_pad, max_lat + lat_pad)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    return fig, ax

def _draw_nodes(ax: plt.Axes, nodes: list[Node]) -> None:
    if not nodes: return
    ax.scatter([n.lon for n in nodes], [n.lat for n in nodes], s=2, c=_NODE_COLOR, zorder=3)

def _draw_edges(ax: plt.Axes, edges: list[DirEdge]) -> None:
    if not edges: return
    segments = [((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)) for e in edges]
    ax.add_collection(LineCollection(segments, colors=_EDGE_COLOR, linewidths=0.5, linestyle="-", zorder=2))

def _draw_routes(ax: plt.Axes, routes: list[Route], route_colors: list[str]) -> None:
    if not routes: return
    for route, color in zip(routes, route_colors):
        segments = [((e.start.lon, e.start.lat), (e.end.lon, e.end.lat)) for e in route.path]
        if segments:
            ax.add_collection(
                LineCollection(segments, colors=color, linewidths=1.0, linestyle=":", capstyle="round", joinstyle="round", zorder=4)
            )

def _draw_jeeps_static(ax: plt.Axes, jeeps: list[Jeep], routes: list[Route], route_colors: list[str]) -> None:
    if not jeeps: return
    lons = [j.currPos[1] for j in jeeps]
    lats = [j.currPos[0] for j in jeeps]
    colors = _get_jeep_colors(jeeps, routes, route_colors)
    
    sc = ax.scatter(lons, lats, marker="^", s=5, c=colors, zorder=6)
    base_path = MarkerStyle('^').get_path()
    paths = [base_path.transformed(Affine2D().rotate_deg(j.heading)) for j in jeeps]
    sc.set_paths(paths)
    
    for j, color in zip(jeeps, colors):
        tc = _get_contrast_color(color)
        ax.text(j.currPos[1], j.currPos[0], str(getattr(j, 'curr_passenger_count', 0)), 
                color=tc, fontsize=5, fontweight='bold', ha='center', va='bottom', zorder=7)

def _draw_passengers(ax: plt.Axes, passengers: list[Passenger]) -> None:
    if not passengers: return
    lons = [p.curr_lon for p in passengers]
    lats = [p.curr_lat for p in passengers]
    ax.scatter(lons, lats, marker="o", s=3, c=_PASSENGER_COLOR, zorder=5)

def _route_colors(count: int) -> list[str]:
    if count <= 0: return []
    colors: list[str] = []
    palette = _GOOGLE_ROUTE_COLORS[:]
    while len(colors) < count:
        colors.extend(sample(palette, len(palette)))
    return colors[:count]

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
    first.save(filename, format="GIF", save_all=True, append_images=rest, duration=duration, loop=0, disposal=2)

def _scale_image(image: Image.Image, scale_up: int) -> Image.Image:
    if scale_up < 1: raise ValueError("scale_up must be at least 1.")
    if scale_up == 1: return image
    return image.resize((image.width * scale_up, image.height * scale_up), Image.LANCZOS)

def _frames_to_gif(frames: list[Image.Image], duration: int = 400) -> io.BytesIO:
    if not frames: raise ValueError("No frames available to build a GIF.")
    buf = io.BytesIO()
    first, *rest = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    first.save(buf, format="GIF", save_all=True, append_images=rest, duration=duration, loop=0, disposal=2)
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
    if not frames: raise ValueError("GIF has no frames.")
    label = tk.Label(root, bd=0)
    label.pack()
    photos = [ImageTk.PhotoImage(frame) for frame in frames]
    def animate(index: int = 0) -> None:
        label.configure(image=photos[index])
        root.after(image.info.get("duration", 400), animate, (index + 1) % len(photos))
    animate()
    root.mainloop()