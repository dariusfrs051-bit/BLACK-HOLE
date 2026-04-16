"""
Black Hole API — feed it an image, watch it get spaghettified.

Run with:
    pip install fastapi uvicorn pillow numpy python-multipart
    python -m uvicorn api:app --reload
"""

import io
import base64
import asyncio
import math
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Black Hole API 🕳️")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory image store (one at a time for simplicity)
stored_image_bytes: Optional[bytes] = None

# ─────────────────────────────────────────────
# Physics helpers
# ─────────────────────────────────────────────

def schwarzschild_time_dilation(r_normalized: float) -> float:
    """
    r_normalized: distance as multiple of Schwarzschild radius (must be > 1).
    Returns clock rate ratio vs. infinity (0 = stopped, 1 = normal).
    """
    if r_normalized <= 1.0:
        return 0.0
    return math.sqrt(1.0 - 1.0 / r_normalized)


# ─────────────────────────────────────────────
# Distortion pipeline
# ─────────────────────────────────────────────

def apply_gravitational_lensing(arr: np.ndarray, progress: float) -> np.ndarray:
    """
    Warp pixels toward/around center using a radial lens distortion.
    At low progress this is subtle; near the horizon it's extreme.
    """
    h, w = arr.shape[:2]
    cx, cy = w / 2, h / 2
    strength = progress ** 2 * 3.5  # lens strength grows non-linearly

    # Build destination coordinate grids
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = xs - cx
    dy = ys - cy
    r = np.sqrt(dx**2 + dy**2) + 1e-9
    r_max = math.sqrt(cx**2 + cy**2)
    r_norm = r / r_max

    # Pincushion / pull-toward-center warp
    warp = 1.0 - strength * (1.0 - r_norm) * r_norm
    src_x = cx + dx * warp
    src_y = cy + dy * warp

    src_x = np.clip(src_x, 0, w - 1).astype(np.float32)
    src_y = np.clip(src_y, 0, h - 1).astype(np.float32)

    # Bilinear sample
    x0 = np.floor(src_x).astype(int)
    y0 = np.floor(src_y).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    fx = (src_x - x0)[..., None]
    fy = (src_y - y0)[..., None]

    out = (arr[y0, x0] * (1 - fx) * (1 - fy)
         + arr[y0, x1] *      fx  * (1 - fy)
         + arr[y1, x0] * (1 - fx) *      fy
         + arr[y1, x1] *      fx  *      fy)

    return np.clip(out, 0, 255).astype(np.uint8)


def apply_spaghettification(img: Image.Image, progress: float) -> Image.Image:
    """
    Stretch vertically (radial tidal force) and compress horizontally.
    Follows tidal force ∝ M/r³ — effect is mild at first, catastrophic near horizon.
    """
    w, h = img.size
    t = progress  # 0 → 1

    # Non-linear scaling — slow start, explosive near horizon
    squeeze_x = max(0.05, 1.0 - t**2 * 0.95)
    stretch_y = 1.0 + t**3 * 12.0

    new_w = max(2, int(w * squeeze_x))
    new_h = int(h * stretch_y)

    distorted = img.resize((new_w, new_h), Image.LANCZOS)

    # Place on black canvas, centered
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    x_off = (w - new_w) // 2
    y_off = max(0, (h - new_h) // 2)  # clip top/bottom when stretched beyond canvas

    # Crop distorted if taller than canvas
    if new_h > h:
        crop_top = (new_h - h) // 2
        distorted = distorted.crop((0, crop_top, new_w, crop_top + h))
        y_off = 0

    canvas.paste(distorted, (x_off, y_off))
    return canvas


def apply_redshift(img: Image.Image, progress: float) -> Image.Image:
    """
    Gravitational redshift — light loses energy climbing out of a gravity well.
    Image reddens and dims as progress → 1.
    """
    if progress < 0.2:
        return img

    t = (progress - 0.2) / 0.8  # normalized 0-1 after 20% mark

    r, g, b, a = img.split()

    # Suppress green and blue channels
    g_factor = max(0.0, 1.0 - t * 0.85)
    b_factor = max(0.0, 1.0 - t * 0.98)

    g = ImageEnhance.Brightness(g).enhance(g_factor)
    b = ImageEnhance.Brightness(b).enhance(b_factor)

    # Overall brightness drop from redshift energy loss
    overall = max(0.05, 1.0 - t * 0.7)
    r = ImageEnhance.Brightness(r).enhance(overall)

    return Image.merge("RGBA", (r, g, b, a))


def apply_chromatic_aberration(arr: np.ndarray, progress: float) -> np.ndarray:
    """
    Near the photon sphere, extreme lensing separates colors.
    Shift R and B channels in opposite directions radially.
    """
    if progress < 0.4:
        return arr

    shift = int((progress - 0.4) / 0.6 * 12)
    if shift < 1:
        return arr

    out = arr.copy()
    # Shift red channel left, blue right
    out[:, shift:, 0] = arr[:, :-shift, 0]   # R shifts right
    out[:, :-shift, 2] = arr[:, shift:, 2]   # B shifts left
    return out


def apply_event_horizon_fade(img: Image.Image, progress: float) -> Image.Image:
    """Past 90% progress, the image crushes to black — crossing the horizon."""
    if progress < 0.88:
        return img
    t = (progress - 0.88) / 0.12
    fade = ImageEnhance.Brightness(img).enhance(max(0.0, 1.0 - t))
    return fade


def distort_frame(source_img: Image.Image, progress: float) -> Image.Image:
    """Full distortion pipeline for a single frame."""
    img = source_img.copy().convert("RGBA")

    # 1. Gravitational lensing (pixel warp)
    arr = np.array(img)
    arr = apply_gravitational_lensing(arr, progress)
    img = Image.fromarray(arr, "RGBA")

    # 2. Spaghettification (tidal stretch/squeeze)
    img = apply_spaghettification(img, progress)

    # 3. Chromatic aberration
    arr = np.array(img)
    arr = apply_chromatic_aberration(arr, progress)
    img = Image.fromarray(arr, "RGBA")

    # 4. Gravitational redshift
    img = apply_redshift(img, progress)

    # 5. Final fade past event horizon
    img = apply_event_horizon_fade(img, progress)

    return img


def frame_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return base64.b64encode(buf.getvalue()).decode()


# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@app.put("/feed", summary="Upload an image to feed into the black hole")
async def feed_image(file: UploadFile = File(...)):
    global stored_image_bytes
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image")
    stored_image_bytes = await file.read()
    return {
        "status": "consumed",
        "filename": file.filename,
        "message": "Connect to GET /stream to watch it fall in.",
    }


@app.get("/stream", summary="SSE stream of the image falling into the black hole")
async def stream_fall(
    steps: int = 80,
    delay_ms: int = 50,
):
    """
    Streams Server-Sent Events. Each event contains a base64-encoded PNG frame.
    - steps: number of animation frames (default 80)
    - delay_ms: milliseconds between frames (default 50)
    """
    if stored_image_bytes is None:
        raise HTTPException(404, "No image uploaded. PUT /feed first.")

    source = Image.open(io.BytesIO(stored_image_bytes)).convert("RGBA")
    # Cap size for performance
    source.thumbnail((600, 600), Image.LANCZOS)
    delay = max(10, delay_ms) / 1000.0

    async def generate():
        # Send original frame first
        yield f"data: {frame_to_b64(source)}\n\n"
        await asyncio.sleep(delay)

        for i in range(1, steps + 1):
            # Use ease-in curve so it accelerates toward horizon
            t = (i / steps) ** 1.4
            progress = min(t, 1.0)

            frame = distort_frame(source, progress)
            b64 = frame_to_b64(frame)
            yield f"data: {b64}\n\n"
            await asyncio.sleep(delay)

        yield "data: SINGULARITY\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    here = Path(__file__).parent
    with open(here / "index.html", encoding="utf-8") as f:
        return f.read()
