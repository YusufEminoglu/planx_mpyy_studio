"""Draw the small cog/gear ('dişli') markers the Ek-1e detail catalog uses for the 'Özel
Kanunlarla Belirlenen Alan ve Sınırlar' borders (Teknoloji Geliştirme Bölgesi, Serbest Bölge,
Organize Sanayi Bölgesi, Endüstri Bölgesi; s.21-23). The catalog gives the outer/inner diameter
of the ring in millimetres but not a tooth profile, so the tooth count (10) and root radius
(midway between the inner hole and the outer tip) are read off the catalog's own icon and are a
reasonable drawing choice, not a measured value. Needs Pillow (developer only).

    py -3 tools/build_gear_symbols.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "resources" / "katalog_sembol"
TEETH = 10
RENDER_SIZE = 512  # supersampled, then downscaled for anti-aliased edges
FINAL_SIZE = 128

# (outer_mm, inner_mm or None for a filled disc) per level, matching the borders in decisions.json
LEVELS = {
    "uip": (7, 5),
    "nip": (6, 4),
    "cdp": (5, 3),
}


def _gear_polygon(outer_r, root_r, teeth, cx, cy):
    points = []
    n = teeth * 4
    for i in range(n):
        angle = 2 * math.pi * i / n - math.pi / 2
        is_outer = (i % 4) in (0, 1)  # flat-top square teeth
        r = outer_r if is_outer else root_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return points


def render(outer_mm, inner_mm, path):
    cx = cy = RENDER_SIZE / 2
    scale = (RENDER_SIZE * 0.48) / (outer_mm / 2)
    outer_r = (outer_mm / 2) * scale
    inner_r = (inner_mm / 2) * scale if inner_mm else 0
    root_r = inner_r + 0.5 * (outer_r - inner_r) if inner_mm else outer_r * 0.86

    image = Image.new("RGBA", (RENDER_SIZE, RENDER_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon(_gear_polygon(outer_r, root_r, TEETH, cx, cy), fill=(0, 0, 0, 255))
    if inner_mm:
        draw.ellipse((cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r), fill=(0, 0, 0, 0))
    image.resize((FINAL_SIZE, FINAL_SIZE), Image.LANCZOS).save(path)
    print("wrote", path)


def main():
    for level, (outer_mm, inner_mm) in LEVELS.items():
        render(outer_mm, inner_mm, OUT_DIR / f"disli_bos_{level}.png")
        render(outer_mm, None, OUT_DIR / f"disli_dolu_{level}.png")


if __name__ == "__main__":
    main()
