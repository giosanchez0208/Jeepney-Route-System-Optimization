from __future__ import annotations
import os
import io
from typing import Any, Optional
from PIL import Image

def compile_to_gif(
    frames: list[Image.Image], 
    fps: int, 
    export_to: Optional[str] = None, 
    verbose: bool = False
) -> bytes:
    """
    Compiles a sequence of PIL Images into a GIF byte stream.
    Saves to disk if a valid path within utils/.cache/ is provided.
    """
    if not isinstance(frames, list) or not all(isinstance(f, Image.Image) for f in frames):
        raise TypeError("[VISUALIZATION] Frames parameter must be a list of Image.Image objects.")
    if not frames:
        raise ValueError("[VISUALIZATION] Frame list is empty.")
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError(f"[VISUALIZATION] FPS must be a positive integer. Received: {fps}")

    duration_ms: int = int(1000 / fps)
    out_stream = io.BytesIO()

    frames[0].save(
        out_stream,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0
    )

    if export_to is not None:
        if not isinstance(export_to, str):
            raise TypeError(f"[VISUALIZATION] Invalid export_to type: {type(export_to)}. Expected str.")
        if "utils/.cache" not in export_to:
            raise ValueError("[VISUALIZATION] Export path must be within utils/.cache/ per directory hygiene standards.")
        
        os.makedirs(os.path.dirname(export_to), exist_ok=True)
        with open(export_to, "wb") as file:
            file.write(out_stream.getvalue())
        if verbose:
            print(f"GIF exported successfully to {export_to}")

    return out_stream.getvalue()


def draw_all(
    drawable_objects: list[Any], 
    context: tuple[tuple[float, float], tuple[float, float]], 
    base_image: Optional[Image.Image] = None, 
    resolution: int = 1000, 
    text: Optional[str] = None,
    verbose: bool = False
) -> Image.Image:
    """
    Sequentially executes the draw method on a list of objects over a single base image.
    Enforces square aspect ratios and strict Image.Image return types.
    """
    if not isinstance(drawable_objects, list):
        raise TypeError(f"[VISUALIZATION] Invalid drawable_objects type: {type(drawable_objects)}. Expected list.")
    if not isinstance(context, tuple) or len(context) != 2:
        raise TypeError("[VISUALIZATION] Context must be a spatial boundary tuple of two coordinate tuples.")
        
    if base_image is not None:
        if not isinstance(base_image, Image.Image):
            raise TypeError(f"[VISUALIZATION] Invalid base_image type: {type(base_image)}. Expected Image.Image.")
        if base_image.width != base_image.height:
            raise ValueError(f"[VISUALIZATION] Base image aspect ratio must be 1:1. Received: {base_image.width}x{base_image.height}.")
        img: Image.Image = base_image.copy()
    else:
        img = Image.new("RGBA", (resolution, resolution), (255, 255, 255, 255))

    for idx, obj in enumerate(drawable_objects):
        if not hasattr(obj, "draw") or not callable(getattr(obj, "draw")):
            raise AttributeError(f"[VISUALIZATION] Object at index {idx} lacks a callable draw method.")
        
        img = obj.draw(context=context, image=img)
        
        if not isinstance(img, Image.Image):
            raise TypeError(f"[VISUALIZATION] Object at index {idx} failed to return an Image.Image object from draw().")

    if text:
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", int(img.height * 0.025))
        except IOError:
            font = ImageFont.load_default()
        
        pad = int(img.height * 0.02)
        # Black outline
        for dx, dy in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            draw.text((pad + dx, pad + dy), text, fill="black", font=font)
        # White fill
        draw.text((pad, pad), text, fill="white", font=font)

    if verbose:
        print(f"Rendered {len(drawable_objects)} objects into the composite image.")

    return img

################################################################################################

import tkinter as tk
import threading
import time
from typing import Callable, Any
from PIL import Image, ImageTk

class LiveTkinterVisualizer:
    def __init__(self, initial_state: Any, update_func: Callable[[Any], None], draw_func: Callable[[Any], Image.Image], fps: int = 30) -> None:
        self.state = initial_state
        self.update_func = update_func
        self.draw_func = draw_func
        
        self.fps = fps
        self.delay_ms = int(1000 / fps)
        
        self.state_lock = threading.Lock()
        self.running = False
        
        self.root = tk.Tk()
        self.root.title("Live Visualizer")
        
        # Initialize with dummy dimensions; will expand to fit the first image
        self.canvas = tk.Canvas(self.root, width=800, height=800, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Prevent garbage collection of the Tkinter image
        self._tk_image = None 
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _simulation_worker(self) -> None:
        """Runs asynchronously. Mutates state."""
        while self.running:
            with self.state_lock:
                self.update_func(self.state)
            # Yield control briefly to prevent CPU locking
            time.sleep(0.001)

    def _render_loop(self) -> None:
        """Runs on the main GUI thread. Fetches state and draws."""
        if not self.running:
            return

        with self.state_lock:
            pil_img = self.draw_func(self.state)

        if pil_img:
            self._tk_image = ImageTk.PhotoImage(image=pil_img)
            self.canvas.config(width=pil_img.width, height=pil_img.height)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_image)

        self.root.after(self.delay_ms, self._render_loop)

    def _on_closing(self) -> None:
        self.running = False
        self.root.destroy()

    def display(self) -> None:
        """Blocks execution and starts the visualizer."""
        self.running = True
        
        sim_thread = threading.Thread(target=self._simulation_worker, daemon=True)
        sim_thread.start()
        
        self._render_loop()
        self.root.mainloop()