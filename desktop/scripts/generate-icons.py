#!/usr/bin/env python3
"""Generate platform icons from desktop/assets/logo.png."""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
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

BG = (7, 9, 7)
ACCENT = (214, 255, 74)
ACCENT_DIM = (143, 181, 42)
RING = (143, 181, 42, 90)


def draw_logo(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG + (255,))
    draw = ImageDraw.Draw(img)
    cx = cy = size // 2
    outer = int(size * 0.42)
    mid = int(size * 0.30)
    inner = int(size * 0.18)

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

    pad = size // 10
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=size // 8,
        outline=ACCENT_DIM + (100,),
        width=max(1, size // 128),
    )
    return img


def ensure_source_logo() -> Image.Image:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_LOGO.exists():
        return Image.open(SOURCE_LOGO).convert("RGBA")
    master = draw_logo(1024)
    master.save(SOURCE_LOGO, format="PNG")
    return master


def render_logo(size: int, source: Image.Image) -> Image.Image:
    if source.size == (size, size):
        return source.copy()
    return source.resize((size, size), Image.Resampling.LANCZOS)


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
        "[icons] source:",
        SOURCE_LOGO,
        "-> build/icon.{png,icns,ico}, frontend/public/{logo,favicon}.png",
    )


if __name__ == "__main__":
    main()
