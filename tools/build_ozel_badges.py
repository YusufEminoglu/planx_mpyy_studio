"""Draw the small marker badges the Ek-1e catalog never printed a dedicated page for.

Ozel Sosyal/Kulturel Tesis Alani ve Ozel Acik/Kapali Spor Tesisi Alani (UIP/NIP, Sosyal ve
Kulturel Tesis Alanlari alt sinifi): the catalog's own convention for an "Ozel" (private) variant
elsewhere is not a separate pictogram -- Ozel Saglik Tesisi Alani (s.122) and Ozel Sosyal Altyapi
Alani (s.125) both just reuse their box with a plain "O"/"OZEL" mark, nothing else. These four
"Ozel X Tesis/Spor Alani" rules each have a working, separately-catalogued *non-Ozel* sibling in
the same SLD type (Sosyal/Kulturel/Acik Spor/Kapali Spor Tesisi Alani all have their own page and
their own pictogram, s.124-127) -- reusing that sibling's own glyph with "O" added below it, split
by a rule the way s.122/125 do, is a documented, non-guessed synthesis, not an invented symbol.

Ozel Sosyal Kulturel Tesis Alani (MUIP, SosyalKulturelAlan; the M-series scale variant of the
same map): identical situation one scale down -- its SLD rule asks the unshipped Intelli Eplan
font for 'V', while the sibling Sosyal Kulturel Tesis Alani rule in that very same SLD draws the
MUIPE_10_2 pictogram at 'V', a box around "STK". Same synthesis, same sibling.

Yayla Turizmi (CDP TurizmAlani): the SLD points at an SVG the catalog never published, and there
is no dedicated page for it at all (unlike Gunubirlik/Kis/Eko/Saglik Turizmi, which do have one --
see docx cross-reference). Its area fill/hatch/colour already carry the meaning; a plain "YT" box
matches the family's own GTB/GTA/GTT-style short-code convention (s.57, Golf Turizmi).

Needs Pillow (developer only):

    py -3 tools/build_ozel_badges.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "resources" / "fonts"
OUT_DIR = ROOT / "resources" / "katalog_sembol"

SUPERSAMPLE = 720
FINAL_SIZE = 360
BORDER = 12
MARGIN = 36


def _canvas():
    image = Image.new("RGBA", (SUPERSAMPLE, SUPERSAMPLE), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        [MARGIN, MARGIN, SUPERSAMPLE - MARGIN, SUPERSAMPLE - MARGIN],
        outline=(0, 0, 0, 255), width=BORDER,
    )
    return image, draw


def _fit_font(path, text, max_w, max_h, start=560):
    size = start
    while size > 16:
        font = ImageFont.truetype(str(path), size)
        bbox = font.getbbox(text)
        if bbox[2] - bbox[0] <= max_w and bbox[3] - bbox[1] <= max_h:
            return font, bbox
        size -= 4
    return font, bbox


def _draw_centered(draw, text, font, bbox, cx, cy):
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - w / 2 - bbox[0], cy - h / 2 - bbox[1]), text, font=font, fill=(0, 0, 0, 255))


def _save(image, name):
    path = OUT_DIR / name
    image.resize((FINAL_SIZE, FINAL_SIZE), Image.LANCZOS).save(path)
    print("wrote", path)


def compose_ozel(name, sibling_ttf, sibling_char):
    """Sibling rule's own working glyph on top, a ruled-off "Ö" band below -- s.122/125 convention."""
    image, draw = _canvas()
    inner = SUPERSAMPLE - 2 * MARGIN - 2 * BORDER
    icon_h = int(SUPERSAMPLE * 0.58)
    label_h = SUPERSAMPLE - MARGIN - BORDER - icon_h - (MARGIN + BORDER)

    icon_font, icon_bbox = _fit_font(FONTS / sibling_ttf, sibling_char, inner - 40, icon_h - 40)
    _draw_centered(draw, sibling_char, icon_font, icon_bbox, SUPERSAMPLE / 2, MARGIN + BORDER + icon_h / 2)

    label_font, label_bbox = _fit_font(FONTS / "DejaVuSans-Bold.ttf", "Ö", inner - 40, label_h - 20, start=280)
    _draw_centered(draw, "Ö", label_font, label_bbox, SUPERSAMPLE / 2, SUPERSAMPLE - MARGIN - BORDER - label_h / 2)

    sep_y = MARGIN + BORDER + icon_h
    draw.line([MARGIN + BORDER, sep_y, SUPERSAMPLE - MARGIN - BORDER, sep_y], fill=(0, 0, 0, 255), width=6)
    _save(image, name)


def compose_text(name, text):
    image, draw = _canvas()
    inner = SUPERSAMPLE - 2 * MARGIN - 2 * BORDER
    font, bbox = _fit_font(FONTS / "DejaVuSans-Bold.ttf", text, inner - 20, inner - 20, start=400)
    _draw_centered(draw, text, font, bbox, SUPERSAMPLE / 2, SUPERSAMPLE / 2)
    _save(image, name)


def main():
    compose_ozel("ozel_kulturel_tesis.png", "uygulama_imar_02.ttf", "s")   # UIP Kulturel Tesis Alani
    compose_ozel("ozel_sosyal_tesis.png", "uygulama_imar_03.ttf", "W")     # UIP Sosyal Tesis Alani
    compose_ozel("ozel_acik_spor_tesis.png", "uygulama_imar_02.ttf", "\"")  # UIP Acik Spor Tesisi Alani
    compose_ozel("ozel_kapali_spor_tesis.png", "UIP_10_2.ttf", "j")        # UIP Kapali Spor Tesisi Alan
    compose_ozel("ozel_sosyal_kulturel_tesis.png", "MUIPE_10_2.ttf", "V")  # MUIP (bkz. modul docstring'i)
    compose_text("yayla_turizmi.png", "YT")


if __name__ == "__main__":
    main()
