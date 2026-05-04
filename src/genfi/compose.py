"""Image compositing: arrange video frames inside a folder-shaped icon."""

import logging
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

CROP_FILL = "fill"
CROP_FIT = "fit"
CROP_CENTER = "center"

# Adwaita/Yaru-inspired colour palette.
# back     = darker back piece visible as the "tab" above the front body
# front    = main lighter body colour
# highlight= shimmer peak colour blended into the horizontal gradient
# edge_top = subtle top-edge highlight line on the front body
# interior_bg = dark tint drawn behind the media mosaic
FOLDER_COLORS = {
    "back":         (67,  141, 230),  # #438de6
    "front":        (98,  160, 234),  # #62a0ea
    "highlight":    (175, 212, 255),  # #afd4ff
    "edge_top":     (164, 202, 238),  # #a4caee
    "interior_bg":  (30,  90,  160),
}


def compose_grid(
    frame_paths: list[Path],
    output_path: Path,
    icon_size: int = 512,
    crop_mode: str = CROP_CENTER,
    background: Path | None = None,
) -> bool:
    """Compose frames inside a folder-shaped icon and save as PNG.

    Returns True on success.
    """
    count = min(len(frame_paths), 4)
    if count == 0:
        return False

    icon = _draw_folder_base(icon_size)

    if background is not None:
        icon = _apply_body_background(icon, background, icon_size)

    interior = _get_interior_rect(icon_size)
    frames = _load_and_crop_frames(frame_paths[:count], interior, crop_mode)

    if len(frames) == 0:
        return False

    _draw_interior_background(icon, interior)
    _place_frames(icon, frames, interior, count)
    _draw_folder_overlay(icon, icon_size)

    try:
        icon.save(output_path, "PNG")
        return True
    except Exception as e:
        logger.error("Failed to save icon to %s: %s", output_path, e)
        return False


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _folder_geometry(size: int) -> dict:
    """Return all proportional measurements for the folder shape."""
    bl = int(size * 0.06)
    br = int(size * 0.94)
    bb = int(size * 0.91)
    r  = int(size * 0.07)
    tab_h   = int(size * 0.10)   # how far the back piece protrudes above front
    back_top = int(size * 0.14)
    front_top = back_top + tab_h
    back_bottom = int(size * 0.88)
    tab_w   = int(size * 0.44)   # width of the tab notch
    back_r  = int(size * 0.06)
    return dict(
        bl=bl, br=br, bb=bb, r=r,
        tab_h=tab_h, back_top=back_top, front_top=front_top,
        back_bottom=back_bottom, tab_w=tab_w, back_r=back_r,
    )


# ── Folder base drawing ───────────────────────────────────────────────────────

def _draw_folder_base(size: int) -> Image.Image:
    """Draw an Adwaita/Yaru-style folder on a transparent canvas.

    Layers (bottom to top):
      1. Soft drop shadow beneath the front body
      2. Darker back piece — tab notch + body rectangle
      3. Lighter front body rectangle
      4. Horizontal shimmer gradient masked to the front body
      5. Thin top-edge highlight line
    """
    g = _folder_geometry(size)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 1. Drop shadow
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [g["bl"] + 2, g["front_top"] + 4, g["br"] + 4, g["bb"] + 6],
        radius=g["r"],
        fill=(0, 0, 0, 90),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(2, int(size * 0.018))))
    img = Image.alpha_composite(img, shadow)

    # 2. Back piece (darker colour, draws tab notch + body)
    back = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(back)
    tab_pts = _tab_polygon(g)
    bd.polygon(tab_pts, fill=FOLDER_COLORS["back"])
    bd.rounded_rectangle(
        [g["bl"], g["front_top"] - 2, g["br"], g["back_bottom"]],
        radius=g["r"],
        fill=FOLDER_COLORS["back"],
    )
    img = Image.alpha_composite(img, back)

    # 3. Front body
    front = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fd = ImageDraw.Draw(front)
    fd.rounded_rectangle(
        [g["bl"], g["front_top"], g["br"], g["bb"]],
        radius=g["r"],
        fill=FOLDER_COLORS["front"],
    )
    img = Image.alpha_composite(img, front)

    # 4. Shimmer gradient (horizontal, masked to front body shape)
    img = _apply_shimmer(img, g, size)

    # 5. Top-edge highlight line
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hld = ImageDraw.Draw(hl)
    lw = max(1, size // 256)
    hld.line(
        [(g["bl"] + g["r"], g["front_top"] + lw),
         (g["br"] - g["r"], g["front_top"] + lw)],
        fill=(*FOLDER_COLORS["edge_top"], 190),
        width=lw,
    )
    img = Image.alpha_composite(img, hl)

    return img


def _tab_polygon(g: dict) -> list[tuple[int, int]]:
    """Return polygon points for the tab (back-piece notch above the front body).

    The tab has rounded top-left and top-right corners and a flat bottom edge
    flush with front_top, matching the Adwaita two-layer folder look.
    """
    x0, y0 = g["bl"], g["back_top"]
    x1, y1 = g["bl"] + g["tab_w"], g["front_top"]
    r  = g["back_r"]
    cr = int(r * 0.7)   # softer curve on the top-right corner of the tab
    pts: list[tuple[int, int]] = []
    # Top-left rounded corner
    for deg in range(180, 271, 10):
        a = math.radians(deg)
        pts.append((x0 + r + int(r * math.cos(a)),
                    y0 + r + int(r * math.sin(a))))
    # Top-right rounded corner (smaller radius for a natural taper)
    for deg in range(270, 361, 10):
        a = math.radians(deg)
        pts.append((x1 - cr + int(cr * math.cos(a)),
                    y0 + cr + int(cr * math.sin(a))))
    # Straight bottom edge
    pts.append((x1, y1))
    pts.append((x0, y1))
    return pts


def _apply_shimmer(img: Image.Image, g: dict, size: int) -> Image.Image:
    """Composite a horizontal shimmer gradient onto the front body."""
    bl, br = g["bl"], g["br"]
    front_top, bb = g["front_top"], g["bb"]
    body_w = br - bl

    # Gradient stops: (position 0–1, alpha 0–255)
    stops = [
        (0.00,  80),
        (0.06, 180),
        (0.13,  60),
        (0.87,  60),
        (0.96, 120),
        (1.00,  70),
    ]
    fr2, fg2, fb2 = FOLDER_COLORS["front"]
    hr,  hg,  hb  = FOLDER_COLORS["highlight"]

    shimmer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sh = ImageDraw.Draw(shimmer)

    for x in range(bl, br):
        t = (x - bl) / body_w
        a = _interp_stops(stops, t)
        blend = a / 180.0
        px_r = int(fr2 + (hr - fr2) * blend)
        px_g = int(fg2 + (hg - fg2) * blend)
        px_b = int(fb2 + (hb - fb2) * blend)
        sh.line([(x, front_top), (x, bb)], fill=(px_r, px_g, px_b, int(a)))

    # Mask to front body shape
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([bl, front_top, br, bb], radius=g["r"], fill=255)
    _apply_mask_to_alpha(shimmer, mask)

    return Image.alpha_composite(img, shimmer)


def _apply_mask_to_alpha(img: Image.Image, mask: Image.Image) -> None:
    """Clip img's alpha channel in-place using mask (L-mode)."""
    r, g, b, a = img.split()
    a_bytes = a.tobytes()
    m_bytes = mask.tobytes()
    clipped = bytes(min(av, mv) for av, mv in zip(a_bytes, m_bytes))
    img.putalpha(Image.frombytes("L", img.size, clipped))


def _interp_stops(stops: list[tuple[float, float]], t: float) -> float:
    """Linearly interpolate a value across gradient stops [(position, value)]."""
    for i in range(len(stops) - 1):
        t0, v0 = stops[i]
        t1, v1 = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return v0 + (v1 - v0) * f
    return stops[-1][1]


# ── Custom background ─────────────────────────────────────────────────────────

def _apply_body_background(
    folder_img: Image.Image,
    background: Path,
    size: int,
) -> Image.Image:
    """Replace the folder body fill with a user-supplied image.

    The image is scaled/cropped to cover the front body rectangle, then masked
    to the body's rounded-rectangle shape and composited onto the folder.
    The tab, drop shadow, shimmer, and overlay effects are all preserved.
    """
    g = _folder_geometry(size)
    bl, br = g["bl"], g["br"]
    front_top, bb, r = g["front_top"], g["bb"], g["r"]
    body_w = br - bl
    body_h = bb - front_top

    # Load the background image
    bg = _load_background_image(background, body_w, body_h)
    if bg is None:
        return folder_img

    # Build a mask for the front body rounded rectangle
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([bl, front_top, br, bb], radius=r, fill=255)

    # Place the background image at the body position on a full-size canvas
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(bg, (bl, front_top))
    _apply_mask_to_alpha(layer, mask)

    return Image.alpha_composite(folder_img, layer)


def _load_background_image(
    path: Path, target_w: int, target_h: int
) -> Image.Image | None:
    """Load a JPEG, PNG, or SVG file and scale/crop it to (target_w, target_h)."""
    suffix = path.suffix.lower()

    if suffix == ".svg":
        try:
            import cairosvg  # type: ignore
            png_bytes = cairosvg.svg2png(
                url=str(path),
                output_width=target_w,
                output_height=target_h,
            )
            from io import BytesIO
            img = Image.open(BytesIO(png_bytes)).convert("RGBA")
        except ImportError:
            logger.warning(
                "SVG background requested but cairosvg is not installed; "
                "falling back to default folder colour. "
                "Install it with: pip install cairosvg"
            )
            return None
        except Exception as e:
            logger.warning("Could not rasterize SVG background %s: %s", path, e)
            return None
    else:
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            logger.warning("Could not open background image %s: %s", path, e)
            return None

    return _crop_and_resize(img, target_w, target_h, CROP_CENTER)


# ── Interior ──────────────────────────────────────────────────────────────────

def _get_interior_rect(size: int) -> tuple[int, int, int, int]:
    """Return the (x0, y0, x1, y1) rectangle inside the folder for frames."""
    g = _folder_geometry(size)
    pad = int(size * 0.07)
    x0 = g["bl"] + pad
    y0 = g["front_top"] + pad
    x1 = g["br"] - pad
    y1 = g["bb"] - pad
    return (x0, y0, x1, y1)


def _draw_interior_background(img: Image.Image, interior: tuple[int, int, int, int]):
    """Draw the dark interior area where frames will be placed."""
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = interior
    draw.rounded_rectangle([x0, y0, x1, y1], radius=6, fill=FOLDER_COLORS["interior_bg"])


# ── Frame loading and placement ───────────────────────────────────────────────

def _load_and_crop_frames(
    frame_paths: list[Path],
    interior: tuple[int, int, int, int],
    crop_mode: str,
) -> list[Image.Image]:
    """Load frame images and prepare them for placement."""
    int_w = interior[2] - interior[0]
    int_h = interior[3] - interior[1]
    frames = []
    for fp in frame_paths:
        try:
            img = Image.open(fp).convert("RGBA")
            img = _crop_and_resize(img, int_w, int_h, crop_mode)
            frames.append(img)
        except Exception as e:
            logger.warning("Could not open frame %s: %s", fp, e)
    return frames


def _place_frames(
    img: Image.Image,
    frames: list[Image.Image],
    interior: tuple[int, int, int, int],
    count: int,
):
    """Place frames inside the folder interior with proper layout."""
    x0, y0, x1, y1 = interior
    int_w = x1 - x0
    int_h = y1 - y0
    gap = max(3, int_w // 80)

    if count == 1:
        cell_x0 = x0 + gap
        cell_y0 = y0 + gap
        cell_x1 = x1 - gap
        cell_y1 = y1 - gap
        frame = _crop_and_resize(frames[0], cell_x1 - cell_x0, cell_y1 - cell_y0, CROP_CENTER)
        frame = _round_corners(frame, 8)
        img.paste(frame, (cell_x0, cell_y0), frame)

    elif count == 2:
        half_w = (int_w - gap * 3) // 2
        for i in range(2):
            cx0 = x0 + gap + i * (half_w + gap)
            cy0 = y0 + gap
            cx1 = cx0 + half_w
            cy1 = y1 - gap
            frame = _crop_and_resize(frames[i], cx1 - cx0, cy1 - cy0, CROP_CENTER)
            frame = _round_corners(frame, 6)
            img.paste(frame, (cx0, cy0), frame)

    elif count == 3:
        half_w = (int_w - gap * 3) // 2
        half_h = (int_h - gap * 3) // 2
        positions = [
            (x0 + gap,           y0 + gap,           x0 + gap + half_w,           y0 + gap + half_h * 2 + gap),
            (x0 + gap * 2 + half_w, y0 + gap,        x0 + gap * 2 + half_w * 2,  y0 + gap + half_h),
            (x0 + gap * 2 + half_w, y0 + gap * 2 + half_h, x0 + gap * 2 + half_w * 2, y0 + gap * 2 + half_h * 2),
        ]
        for i, (cx0, cy0, cx1, cy1) in enumerate(positions):
            frame = _crop_and_resize(frames[i], cx1 - cx0, cy1 - cy0, CROP_CENTER)
            frame = _round_corners(frame, 6)
            img.paste(frame, (cx0, cy0), frame)

    elif count == 4:
        half_w = (int_w - gap * 3) // 2
        half_h = (int_h - gap * 3) // 2
        for i in range(4):
            col = i % 2
            row = i // 2
            cx0 = x0 + gap + col * (half_w + gap)
            cy0 = y0 + gap + row * (half_h + gap)
            cx1 = cx0 + half_w
            cy1 = cy0 + half_h
            frame = _crop_and_resize(frames[i], cx1 - cx0, cy1 - cy0, CROP_CENTER)
            frame = _round_corners(frame, 6)
            img.paste(frame, (cx0, cy0), frame)


# ── Overlay effects ───────────────────────────────────────────────────────────

def _draw_folder_overlay(img: Image.Image, size: int):
    """Draw a subtle bottom-edge inner shadow on the front body."""
    g = _folder_geometry(size)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for offset in range(6):
        alpha = int(20 * (1 - offset / 6))
        od.line(
            [(g["bl"] + g["r"], g["bb"] - 4 + offset),
             (g["br"] - g["r"], g["bb"] - 4 + offset)],
            fill=(0, 0, 0, alpha),
        )
    img.alpha_composite(overlay)


# ── Image utilities ───────────────────────────────────────────────────────────

def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners to an image using a mask."""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    w, h = img.size
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _crop_and_resize(img: Image.Image, target_w: int, target_h: int, mode: str) -> Image.Image:
    """Resize image to fit the target cell."""
    img_w, img_h = img.size
    if img_w == 0 or img_h == 0:
        return Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))

    if mode == CROP_FILL:
        img = img.resize((target_w, target_h), Image.LANCZOS)

    elif mode == CROP_FIT:
        ratio = min(target_w / img_w, target_h / img_h)
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        new_img = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        paste_x = (target_w - new_w) // 2
        paste_y = (target_h - new_h) // 2
        new_img.paste(resized, (paste_x, paste_y))
        img = new_img

    elif mode == CROP_CENTER:
        ratio = max(target_w / img_w, target_h / img_h)
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top  = (new_h - target_h) // 2
        img  = resized.crop((left, top, left + target_w, top + target_h))

    return img
