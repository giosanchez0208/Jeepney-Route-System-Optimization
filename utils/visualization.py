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

    if verbose:
        print(f"Rendered {len(drawable_objects)} objects into the composite image.")

    return img