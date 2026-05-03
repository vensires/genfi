"""Image compositing: arrange video frames inside a folder-shaped icon."""

import logging
from pathlib import Path

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

CROP_FILL = "fill"
CROP_FIT = "fit"
CROP_CENTER = "center"


FOLDER_COLORS = {
    "body": (53, 132, 228),
    "body_dark": (41, 121, 214),
    "tab": (64, 145, 236),
    "tab_dark": (53, 132, 228),
    "edge": (30, 90, 170),
    "interior_bg": (20, 70, 150),
    "separator": (80, 160, 240),
}


def compose_grid(
    frame_paths: list[Path],
    output_path: Path,
    icon_size: int = 512,
    crop_mode: str = CROP_CENTER,
) -> bool:
    """Compose frames inside a folder-shaped icon and save as PNG.

    Returns True on success.
    """
    count = min(len(frame_paths), 4)
    if count == 0:
        return False

    icon = _draw_folder_base(icon_size)

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


def _draw_folder_base(size: int) -> Image.Image:
    """Draw the base folder shape on a transparent canvas."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    tab_w = int(size * 0.38)
    tab_h = int(size * 0.09)
    body_top = int(size * 0.17)
    body_left = int(size * 0.06)
    body_right = int(size * 0.94)
    body_bottom = int(size * 0.92)
    radius = int(size * 0.035)

    tab_path = [
        (body_left + radius, body_top),
        (body_left + radius + tab_w - radius, body_top),
        (body_left + radius + tab_w, body_top + tab_h - radius),
        (body_left + radius + tab_w, body_top + tab_h),
        (body_left, body_top + tab_h),
        (body_left, body_top + radius),
    ]
    draw.polygon(tab_path, fill=FOLDER_COLORS["tab"], outline=FOLDER_COLORS["edge"], width=2)

    body_path = _rounded_rect_path(body_left, body_top + tab_h - 2, body_right, body_bottom, radius)
    draw.polygon(body_path, fill=FOLDER_COLORS["body"], outline=FOLDER_COLORS["edge"], width=2)

    inner_body = (body_left + 4, body_top + tab_h + 2, body_right - 4, body_bottom - 4)
    inner_r = max(radius - 2, 2)
    inner_path = _rounded_rect_path(*inner_body, inner_r)
    draw.polygon(inner_path, fill=FOLDER_COLORS["body_dark"])

    highlight = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(highlight)
    grad_top = body_top + tab_h
    grad_bottom = body_bottom
    for y in range(grad_top, grad_bottom):
        alpha = int(40 * (1 - (y - grad_top) / (grad_bottom - grad_top)))
        hdraw.line([(body_left + 4, y), (body_right - 4, y)], fill=(255, 255, 255, alpha))
    img = Image.alpha_composite(img, highlight)

    return img


def _rounded_rect_path(x0: int, y0: int, x1: int, y1: int, r: int) -> list[tuple[int, int]]:
    """Return polygon points for a rounded rectangle."""
    r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)
    if r < 1:
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    steps = 6
    points = []
    for i in range(steps):
        angle = (i / steps) * 3.14159 / 2
        points.append((x1 - r + int(r * (1 - 3.14159 / 2 + angle) * 2 / 3.14159), y0 + r - int(r * (1 - 3.14159 / 2 + angle) * 2 / 3.14159)))
    points = []
    import math
    for angle_deg in range(0, 91, 30):
        a = math.radians(angle_deg)
        points.append((x1 - r + int(r * math.cos(a)), y0 + r - int(r * math.sin(a))))
    for angle_deg in range(0, 91, 30):
        a = math.radians(angle_deg)
        points.append((x1 - r + int(r * math.sin(a)), y1 - r + int(r * math.cos(a))))
    for angle_deg in range(0, 91, 30):
        a = math.radians(angle_deg)
        points.append((x0 + r - int(r * math.cos(a)), y1 - r + int(r * math.sin(a))))
    for angle_deg in range(0, 91, 30):
        a = math.radians(angle_deg)
        points.append((x0 + r - int(r * math.sin(a)), y0 + r - int(r * math.cos(a))))
    return points


def _get_interior_rect(size: int) -> tuple[int, int, int, int]:
    """Return the (x0, y0, x1, y1) rectangle inside the folder for frames."""
    padding = int(size * 0.08)
    tab_h = int(size * 0.09)
    body_top = int(size * 0.17)
    body_bottom = int(size * 0.92)
    x0 = int(size * 0.06) + padding
    y0 = body_top + tab_h + padding
    x1 = int(size * 0.94) - padding
    y1 = body_bottom - padding
    return (x0, y0, x1, y1)


def _draw_interior_background(img: Image.Image, interior: tuple[int, int, int, int]):
    """Draw the dark interior area where frames will be placed."""
    draw = ImageDraw.Draw(img)
    r = int(6)
    x0, y0, x1, y1 = interior
    w = x1 - x0
    h = y1 - y0
    path = _rounded_rect_path(x0, y0, x1, y1, r)
    draw.polygon(path, fill=FOLDER_COLORS["interior_bg"])


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
            (x0 + gap, y0 + gap, x0 + gap + half_w, y0 + gap + half_h * 2 + gap),
            (x0 + gap * 2 + half_w, y0 + gap, x0 + gap * 2 + half_w + half_w, y0 + gap + half_h),
            (x0 + gap * 2 + half_w, y0 + gap * 2 + half_h, x0 + gap * 2 + half_w + half_w, y0 + gap * 2 + half_h + half_h),
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


def _round_corners(img: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners to an image using a mask."""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    w, h = img.size
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _draw_folder_overlay(img: Image.Image, size: int):
    """Draw subtle overlay effects on top of the folder."""
    draw = ImageDraw.Draw(img)
    body_top = int(size * 0.17)
    body_bottom = int(size * 0.92)
    body_left = int(size * 0.06)
    body_right = int(size * 0.94)

    bottom_shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bottom_shadow)
    for y_offset in range(8):
        alpha = int(25 * (1 - y_offset / 8))
        bdraw.line(
            [(body_left + 6, body_bottom - 6 + y_offset), (body_right - 6, body_bottom - 6 + y_offset)],
            fill=(0, 0, 0, alpha),
        )
    img = Image.alpha_composite(img, bottom_shadow)

    edge_hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    edraw = ImageDraw.Draw(edge_hl)
    edraw.line(
        [(body_left + 2, body_top + 2), (body_right - 2, body_top + 2)],
        fill=(255, 255, 255, 40),
    )
    img = Image.alpha_composite(img, edge_hl)


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
        top = (new_h - target_h) // 2
        right = left + target_w
        bottom = top + target_h
        img = resized.crop((left, top, right, bottom))

    return img
