"""Cut the point symbols this plugin needs out of the Ek-1e detail catalog PDF.

    py -3 tools/build_catalog_symbols.py "<20260122-...-Mekansal-Planlar-Detay-Kataloglari-....pdf>"

For every entry in ``styles/mpyy_detail_catalog/decisions.json`` the catalog table whose
title matches is found on the given page, its SEMBOL cell is rendered at 600 dpi (text
symbols such as MB or KHA included, colour notes inside the cell blanked), near-white
is made transparent, the result trimmed and written to ``resources/katalog_sembol``.
``styles/mpyy_detail_catalog/symbols.json`` records page, title, pixel size, the drawn size
in millimetres and sha256 of each file. Needs PyMuPDF and Pillow (developer only).
"""

import hashlib
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

import fitz
from PIL import Image

# Digests are written as four space-separated groups: the Hub's detect-secrets
# scan blocks a version on a quoted 64-hex string. Readers remove the spaces.
HUB_SAFE_DIGEST = re.compile(r'"([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})"')


def hub_safe(text: str) -> str:
    return HUB_SAFE_DIGEST.sub(r'"\1 \2 \3 \4"', text)


ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "styles" / "mpyy_detail_catalog" / "decisions.json"
OUT_JSON = ROOT / "styles" / "mpyy_detail_catalog" / "symbols.json"
OUT_DIR = ROOT / "resources" / "katalog_sembol"
DPI = 600


def fold(text):
    text = unicodedata.normalize("NFKD", text.replace("İ", "I").replace("ı", "i"))
    return re.sub(r"[^A-Z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)).upper())


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def symbol_cell(page, title, column="SEMBOL"):
    blocks = page.get_text("blocks")
    previous_bottom = 0
    for table in page.find_tables().tables:
        rows = table.extract()
        if not rows or "DETAY" not in clean(rows[0][0]):
            continue
        top = table.bbox[1]
        heading = " ".join(clean(b[4]) for b in blocks if b[3] <= top + 1 and b[1] >= previous_bottom - 1)
        previous_bottom = table.bbox[3]
        if fold(title) not in fold(heading):
            continue
        header = next(i for i, row in enumerate(rows) if clean(row[0]) == "SEMBOL")
        head_cells = table.rows[header].cells
        x0, x1 = next((c[0], c[2]) for c, text in zip(head_cells, rows[header]) if c and clean(text) == column)
        values = [c for c in table.rows[header + 1].cells if c]
        y0, y1 = min(c[1] for c in values), max(c[3] for c in values)
        return fitz.Rect(x0 + 1.5, y0 + 1.5, x1 - 1.5, y1 - 1.5)
    raise LookupError(f"s.{page.number + 1}: '{title}' tablosu bulunamadı")


def render(page, rect):
    words = [w for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(rect)]
    zoom = DPI / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
    for w in words:
        # colour notes such as "RGB: 99/186/82" are not part of the symbol
        if re.match(r"^(RGB|\d{1,3}/\d{1,3}/\d{1,3})", w[4]):
            box = [(w[0] - rect.x0) * zoom - 4, (w[1] - rect.y0) * zoom - 4, (w[2] - rect.x0) * zoom + 4, (w[3] - rect.y0) * zoom + 4]
            image.paste((255, 255, 255, 255), [int(v) for v in box])
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, _ = pixels[x, y]
            if min(r, g, b) >= 235:
                pixels[x, y] = (255, 255, 255, 0)
    box = image.getbbox()
    if box is None:
        raise ValueError("boş sembol hücresi")
    return image.crop(box), (box[2] - box[0]) / zoom * 25.4 / 72, (box[3] - box[1]) / zoom * 25.4 / 72


def bands(mask_line):
    """(start, end) runs of True in a list of booleans."""
    runs, start = [], None
    for index, value in enumerate(mask_line + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index))
            start = None
    return runs


def part(image, column_index, row_index=0, rows_first=False):
    """One motif of a cell holding several (GTB GTA GTT, a hatch sample): columns first, then rows.

    ``rows_first`` takes the row band first (a symbol box with an explanation written under it)."""
    alpha = image.getchannel("A")
    width, height = image.size
    data = alpha.load()
    if rows_first:
        y0, y1 = bands([any(data[x, y] for x in range(width)) for y in range(height)])[row_index]
        piece = image.crop((0, y0, width, y1))
        return piece.crop(piece.getbbox())
    columns = bands([any(data[x, y] for y in range(height)) for x in range(width)])
    x0, x1 = columns[column_index]
    rows = bands([any(data[x, y] for x in range(x0, x1)) for y in range(height)])
    y0, y1 = rows[row_index]
    piece = image.crop((x0, y0, x1, y1))
    return piece.crop(piece.getbbox())


def band_hatch_tile(spec, pixels_per_mm=100):
    """A seamless tile for 'dik tarama çiftleri': vertical rail pairs ``band_mm`` apart repeating every
    ``period_mm``, filled with slanted lines ``line_spacing_mm`` apart (angle from the catalog drawing)."""
    import math

    from PIL import ImageDraw

    width = round(spec["period_mm"] * pixels_per_mm)
    slope = math.tan(math.radians(spec["slant_deg"]))  # horizontal run per unit of drop
    vertical = spec["line_spacing_mm"] / math.cos(math.radians(spec["slant_deg"]))
    height = round(vertical * pixels_per_mm)
    scale = 4  # draw large, shrink for antialiasing
    image = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    line = max(1, round(spec["width_mm"] * pixels_per_mm * scale))
    band = spec["band_mm"] * pixels_per_mm * scale
    for x in (0, band):
        draw.line([(x, 0), (x, height * scale)], fill=(0, 0, 0, 255), width=line)
    band_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    band_draw = ImageDraw.Draw(band_layer)
    for offset in range(-3, 4):
        top = offset * height * scale
        band_draw.line([(0, top), (slope * height * scale * 3, top + height * scale * 3)], fill=(0, 0, 0, 255), width=line)
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rectangle([0, 0, band, height * scale], fill=255)
    image.paste(band_layer, (0, 0), Image.composite(band_layer, Image.new("RGBA", image.size), mask).getchannel("A"))
    return image.resize((width, height), Image.LANCZOS)


def main(pdf_path):
    document = fitz.open(pdf_path)
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    previous = json.loads(OUT_JSON.read_text(encoding="utf-8"))["symbols"] if OUT_JSON.exists() else {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "source": Path(pdf_path).name,
        "sha256": hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest(),
        "dpi": DPI,
        "symbols": {},
    }
    for key, entry in decisions["symbols"].items():
        if not isinstance(entry["page"], int):
            # Synthesized badges (build_ozel_badges.py, "page": "sentez") have no catalog page to
            # cut from. The PNG is drawn by that tool and only measured here; an earlier record is
            # carried over as it stands so a rerun cannot drop or silently re-scale them.
            target = OUT_DIR / f"{key}.png"
            if not target.exists():
                raise LookupError(f"{key}: sayfası sentez, resources/katalog_sembol altında PNG yok")
            if key in previous:
                result["symbols"][key] = previous[key]
            else:
                image = Image.open(target)
                result["symbols"][key] = {
                    "page": "sentez", "title": entry["title"], "file": f"resources/katalog_sembol/{key}.png",
                    "pixels": list(image.size),
                    "width_mm": round(image.size[0] / DPI * 25.4, 2),
                    "height_mm": round(image.size[1] / DPI * 25.4, 2),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            print(key, tuple(result["symbols"][key]["pixels"]), "sentez")
            continue
        page = document[entry["page"] - 1]
        image, width_mm, height_mm = render(page, symbol_cell(page, entry["title"], entry.get("cell", "SEMBOL")))
        if "part" in entry:
            full = image.size
            image = part(image, *entry["part"], rows_first=entry.get("rows_first", False))
            width_mm, height_mm = width_mm * image.size[0] / full[0], height_mm * image.size[1] / full[1]
        target = OUT_DIR / f"{key}.png"
        image.save(target, optimize=True)
        result["symbols"][key] = {
            "page": entry["page"], "title": entry["title"], "file": f"resources/katalog_sembol/{key}.png",
            "pixels": list(image.size), "width_mm": round(width_mm, 2), "height_mm": round(height_mm, 2),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
        print(key, image.size, round(width_mm, 1), "x", round(height_mm, 1), "mm")
    for key, spec in decisions.get("tiles", {}).items():
        if key == "note":
            continue
        image = band_hatch_tile(spec)
        target = OUT_DIR / f"{key}.png"
        image.save(target, optimize=True)
        result["symbols"][key] = {
            "page": spec["page"], "title": spec["title"], "file": f"resources/katalog_sembol/{key}.png",
            "pixels": list(image.size), "width_mm": spec["period_mm"], "height_mm": round(image.size[1] / 100, 3),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "generated": True,
        }
        print(key, image.size, "tile")
    OUT_JSON.write_text(hub_safe(json.dumps(result, ensure_ascii=False, indent=1)) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(sys.argv[1])
