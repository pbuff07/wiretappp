#!/usr/bin/env python3
"""Generate platform icons from desktop/assets/logo.png."""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:
    print(
        "[icons] Pillow 未安装。请先执行 ./manage.sh install，或在虚拟环境中安装 Pillow。",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
ASSETS_DIR = ROOT / "assets"
SOURCE_LOGO = ASSETS_DIR / "logo.png"

# Superellipse exponent — 4~5 reads as a modern squircle on taskbars/docks.
ICON_SQUIRCLE_N = 4.6
# Inset before drawing the dark panel so the glyph breathes at 16–32 px.
ICON_CONTENT_INSET_RATIO = 0.055
# CSS / UI hint (~Apple continuous corner).
ICON_CSS_RADIUS_RATIO = 0.225

BG = (7, 9, 7)
ACCENT = (214, 255, 74)
ACCENT_DIM = (143, 181, 42)
RING = (143, 181, 42, 90)


@lru_cache(maxsize=32)
def squircle_mask(size: int) -> Image.Image:
    """Superellipse silhouette used for dock / taskbar / favicon exports."""
    mask = Image.new("L", (size, size), 0)
    px = mask.load()
    center = (size - 1) / 2.0
    radius = center
    n = ICON_SQUIRCLE_N
    for y in range(size):
        ny = abs(y - center) / radius
        ny_n = ny**n
        for x in range(size):
            nx = abs(x - center) / radius
            if nx**n + ny_n <= 1.0:
                px[x, y] = 255
    return mask


def apply_icon_mask(img: Image.Image) -> Image.Image:
    size = img.size[0]
    mask = squircle_mask(size)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def draw_logo(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size // 2
    outer = int(size * 0.40)
    mid = int(size * 0.28)
    inner = int(size * 0.17)
    inset = max(1, int(size * ICON_CONTENT_INSET_RATIO))

    panel = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    panel.paste(BG + (255,), (0, 0), squircle_mask(size))
    img = Image.alpha_composite(img, panel)

    # Subtle rim — keeps the round silhouette readable on dark taskbars.
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    rim_width = max(1, size // 180)
    rim_inset = inset + rim_width
    rim_draw.rounded_rectangle(
        (rim_inset, rim_inset, size - rim_inset, size - rim_inset),
        radius=int(size * ICON_CSS_RADIUS_RATIO),
        outline=ACCENT_DIM + (110,),
        width=rim_width,
    )
    img = Image.alpha_composite(img, rim)
    draw = ImageDraw.Draw(img)

    for radius, width, color in (
        (outer, max(2, size // 64), ACCENT_DIM + (180,)),
        (mid, max(2, size // 80), RING),
        (inner, max(1, size // 96), ACCENT_DIM + (120,)),
    ):
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            outline=color,
            width=width,
        )

    sweep = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sweep)
    for i in range(90):
        angle = math.radians(-90 + i * 0.9)
        alpha = int(180 * (i / 90))
        length = outer - size // 32
        x = cx + int(math.cos(angle) * length)
        y = cy + int(math.sin(angle) * length)
        sdraw.line((cx, cy, x, y), fill=ACCENT + (alpha,), width=max(2, size // 128))
    img = Image.alpha_composite(img, sweep)
    draw = ImageDraw.Draw(img)

    node_r = max(3, size // 48)
    for angle_deg in (35, 145, 260):
        angle = math.radians(angle_deg)
        nx = cx + int(math.cos(angle) * mid * 0.72)
        ny = cy + int(math.sin(angle) * mid * 0.72)
        draw.ellipse(
            (nx - node_r, ny - node_r, nx + node_r, ny + node_r),
            fill=ACCENT,
        )
        draw.line((cx, cy, nx, ny), fill=ACCENT_DIM + (160,), width=max(1, size // 180))

    draw.ellipse(
        (cx - node_r, cy - node_r, cx + node_r, cy + node_r),
        fill=ACCENT,
    )
    return apply_icon_mask(img)


def ensure_source_logo() -> Image.Image:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    master = draw_logo(1024)
    master.save(SOURCE_LOGO, format="PNG")
    return master


def render_logo(size: int, source: Image.Image) -> Image.Image:
    if source.size != (size, size):
        source = source.resize((size, size), Image.Resampling.LANCZOS)
    else:
        source = source.copy()
    return apply_icon_mask(source)


def write_png(path: Path, size: int, source: Image.Image) -> None:
    render_logo(size, source).save(path, format="PNG")


def write_ico(path: Path, source: Image.Image) -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [render_logo(s, source) for s in sizes]
    images[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


def write_icns(path: Path, source: Image.Image) -> None:
    iconset = BUILD_DIR / "icon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    mapping = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for px, name in mapping:
        write_png(iconset / name, px, source)

    if shutil.which("iconutil"):
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(path)],
            check=True,
        )
        shutil.rmtree(iconset)
        return

    write_png(path.with_suffix(".png"), 512, source)
    print("[icons] iconutil not found; wrote build/icon.png instead of .icns", file=sys.stderr)


def sync_frontend_assets(source: Image.Image) -> None:
    public_dir = ROOT.parent / "frontend" / "public"
    public_dir.mkdir(parents=True, exist_ok=True)
    render_logo(1024, source).save(public_dir / "logo.png", format="PNG")
    for favicon_size in (32, 48):
        render_logo(favicon_size, source).save(
            public_dir / f"favicon-{favicon_size}.png",
            format="PNG",
        )
    render_logo(32, source).save(public_dir / "favicon.png", format="PNG")


def main() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    source = ensure_source_logo()

    write_png(BUILD_DIR / "icon.png", 1024, source)
    write_ico(BUILD_DIR / "icon.ico", source)
    write_icns(BUILD_DIR / "icon.icns", source)
    write_png(ASSETS_DIR / "favicon.png", 32, source)
    sync_frontend_assets(source)

    print(
        "[icons] squircle icons:",
        SOURCE_LOGO,
        "-> build/icon.{png,icns,ico}, frontend/public/{logo,favicon}.png",
    )


if __name__ == "__main__":
    main()
