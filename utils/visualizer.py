import io
import tkinter as tk

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import contextily as ctx
from PIL import Image, ImageTk, ImageSequence
import requests

from typing import Literal, Optional
from directed_edge import DirEdge
from node import Node

WINDOW_SIZE = 800
MapMode = Literal["street", "terrain", "satellite", "light", "light_nolabels", "dark", "dark_nolabels"]


class StaticVisualizer:
    def __init__(self, Nodes: list[Node], DirEdges: list[DirEdge], title: Optional[str] = None) -> None:
        self.Nodes = Nodes
        self.DirEdges = DirEdges
        self.title = title

    def draw(
        self,
        mode: MapMode = "light_nolabels",
        labels_on: bool = False,
        node_color: str = "#6fbaf0",
        node_radius: float = 40,
        edge_color: str = "#d1d1d1",
        edge_thickness: float = 2,
    ) -> Image.Image:
        if not self.Nodes:
            raise ValueError("Nodes needed to give visualizer context for basemap.")

        lats = [node.lat for node in self.Nodes]
        lons = [node.lon for node in self.Nodes]

        fig, ax = _build_figure(lats, lons)

        _add_basemap_or_blank(ax, mode)
        _draw_nodes(ax, self.Nodes, node_color, node_radius, labels_on)
        _draw_edges(ax, self.DirEdges, edge_color, edge_thickness, labels_on)

        return _render_to_image(fig)

    def display(
        self,
        mode: MapMode = "light_nolabels",
        labels_on: bool = False,
        node_color: str = "#6fbaf0",
        node_radius: float = 40,
        edge_color: str = "#d1d1d1",
        edge_thickness: float = 2,
    ) -> None:
        image = self.draw(mode, labels_on, node_color, node_radius, edge_color, edge_thickness)
        _open_window(image, self.title or "Static Visualizer")

    def export(
        self,
        filename: str,
        mode: MapMode = "light_nolabels",
        labels_on: bool = False,
        node_color: str = "#6fbaf0",
        node_radius: float = 40,
        edge_color: str = "#d1d1d1",
        edge_thickness: float = 2,
    ) -> None:
        image = self.draw(mode, labels_on, node_color, node_radius, edge_color, edge_thickness)
        image.save(filename)


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

    def export(self, filename: str, mode: MapMode = "light_nolabels", fps: int = 2) -> None:
        duration = max(1, round(1000 / fps))
        image = self.draw(mode, fps)
        image.save(filename, format="GIF", save_all=True, append_images=self.frames[1:], duration=duration, loop=0)



### HELPER FUNCTIONS ###

def _get_provider(mode: MapMode):
    return {
        "street":          ctx.providers.OpenStreetMap.Mapnik,
        "terrain":         ctx.providers.OpenTopoMap,
        "satellite":       ctx.providers.Esri.WorldImagery,
        "light":           ctx.providers.CartoDB.Positron,
        "light_nolabels":  ctx.providers.CartoDB.PositronNoLabels,
        "dark":            ctx.providers.CartoDB.DarkMatter,
        "dark_nolabels":   ctx.providers.CartoDB.DarkMatterNoLabels,
    }[mode]


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
    for node in nodes:
        ax.scatter(node.lon, node.lat, s=node_radius, c=node_color, zorder=3)
        if labels_on:
            ax.annotate(node.id, (node.lon, node.lat), textcoords="offset points", xytext=(5, 5), fontsize=8)


def _draw_edges(ax: plt.Axes, edges: list[DirEdge], edge_color: str, edge_thickness: float, labels_on: bool) -> None:
    for edge in edges:
        ax.plot(
            [edge.start.lon, edge.end.lon],
            [edge.start.lat, edge.end.lat],
            color=edge_color, linewidth=edge_thickness, zorder=2,
        )
        if labels_on:
            mid_lon = (edge.start.lon + edge.end.lon) / 2
            mid_lat = (edge.start.lat + edge.end.lat) / 2
            ax.annotate(edge.id, (mid_lon, mid_lat), textcoords="offset points", xytext=(0, 6), fontsize=7)


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
