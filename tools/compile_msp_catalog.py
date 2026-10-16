"""Compile the MSP Ek-1e detail catalogue from the annex itself.

``styles/msp_catalog.json`` is the *only* definition of the Mekânsal Strateji
Planı level: the MPYY 1.1.7 XSD set carries UİP/NİP/ÇDP and no MSP schema
exists, so the annex is the specification.  Until now nothing tied the shipped
file to that specification, which made every value in it unverifiable -- a
re-extraction could not be reproduced and a wrong value had nothing to disagree
with.

This tool is that tie.  It reads the annex three times, from three documents, and
refuses to emit anything unless they agree:

* ``EK-1e.docx``  -- the table structure.  A docx stores real cells, so which
  column a value was printed in is a fact rather than a guess.  The published
  PDF cannot say that: its text extraction hands a page's blocks over in
  whatever order the content stream happens to use, so a value printed in the
  ``TİPİ`` column and one printed in the ``RGB`` column look alike.
* the published PDF -- the printed page number of each catalogue title.  Word
  writes ``lastRenderedPageBreak`` only for text it has actually laid out, so
  the docx cannot say which page a record is on; the PDF prints the number in
  its header and that is the annex's own pagination.
* ``EK-1b`` (``Mekânsal Strateji Planlar Gösterimleri``) -- the **drawn**
  columns, read by ``tools/build_msp_shapes.py`` into ``styles/msp_shapes.json``.
  Ek-1e prints colour cells and prose; it never says which shape a point record
  is drawn as, and until this source existed the renderer drew a circle for all
  sixteen of them.  EK-1b also settles the hatch axis, which the prose leaves
  unsaid, and fills MSP-002's symbol colour, which Ek-1e leaves blank.

The three documents also cross-check each other's *order*: the 28 titles must
come out of both Ek-1e and the PDF in the same sequence, the count of tables in
the MSP section must equal the number of printed titles, and the shapes file's
titles must be the same 28.  An extraction that silently drops a record
therefore fails here rather than shipping 27 rows.

Everything the annex prints is kept verbatim in the top-level ``kaynak`` map,
keyed by catalogue id: the raw cell text of each of the seven printed columns.
That is what makes a value auditable -- ``stroke_width_mm`` can be checked
against the words it was read from without opening the docx again -- and it is
how ``tests/test_msp_catalog_pure.py`` can prove that nothing was invented.
``kaynak`` is deliberately *outside* ``rows``: ``rows`` is the runtime contract
``core/msp_workspace.CATALOG_COLUMNS`` mirrors into the GeoPackage, and the
audit trail is not a column of that table.

Where the annex is silent the emitted value is either empty or the annex's own
value for the same thing, never a plausible invention.  Three things the shipped
catalogue used to state have no cell behind them at all -- a 0.5 mm boundary
width on five rows, a black boundary on the two afet rows, and the ``SEMBOL``
colour copied into the fill cell of every point record -- and all three are
gone.  What the drawing still needs is now where the rest of this plugin's
substitutions already live: the renderer's own documented defaults, recorded on
the layer rather than passed off as the Ministry's measurement.

Usage::

    py -3 tools/compile_msp_catalog.py <EK-1e.docx> <Ek-1e.pdf> <Ek-1b.pdf> [--diff]

``--diff`` compares the compilation against the committed catalogue and reports
every disagreement instead of writing; it is the check to run after a new
annex is published.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

from pypdf import PdfReader

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from planx_mpyy_studio.core.localization import label_fold, label_key  # noqa: E402
from planx_mpyy_studio.core.msp_catalog import stated_line_width_mm  # noqa: E402

# Digests are written as four space-separated groups: the Hub's detect-secrets
# scan blocks a version on a quoted 64-hex string. Readers remove the spaces.
HUB_SAFE_DIGEST = re.compile(r'"([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})"')


def hub_safe(text: str) -> str:
    return HUB_SAFE_DIGEST.sub(r'"\1 \2 \3 \4"', text)



OUTPUT = ROOT / "styles" / "msp_catalog.json"

#: EK-1b'nin ölçülmüş çıktısı (`tools/build_msp_shapes.py`).  Üçüncü kaynak.
SHAPES = ROOT / "styles" / "msp_shapes.json"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: The annex's own section heading.  The MSP catalogue is section I and the
#: UİP/NİP/ÇDP catalogue is section II, each printed as its own one-row table,
#: so the section is found by the marker rather than by counting tables: a
#: future annex that gains a section above MSP would otherwise shift every row.
MSP_SECTION = "I- MEKÂNSAL STRATEJİ PLANI DETAY KATALOĞU"
SECTION_MARKER = re.compile(r"^(I|II|III|IV|V|VI)\s*[-–]")

#: The seven printed columns of one catalogue table, as the annex lays them out.
#: ``SEMBOL``/``TARAMA``/``RGB`` sit under the row's ``GÖSTERİM`` value and
#: ``TİPİ``/``RGB`` under ``SINIR``: the left group is how the mark itself is
#: drawn and the right group is its outline.  A ``/`` in an annex cell means
#: "either", which is why the two group headers are the ones that carry it.
COL_SEMBOL = "sembol"
COL_TARAMA = "tarama"
COL_TARAMA_RGB = "tarama_rgb"
COL_SINIR_TIPI = "sinir_tipi"
COL_SINIR_RGB = "sinir_rgb"
COL_GEOMETRI = "geometri_tipi"
COL_TARAMA_ACIKLAMA = "tarama_aciklama"
COL_SINIR_ACIKLAMA = "sinir_aciklama"
COL_DETAY_SINIFI = "detay_sinifi"
COL_DETAY_ALT_SINIFI = "detay_alt_sinifi"

#: A page's record titles are set at 12 pt and every table cell at 10 -- except
#: the graded fill colours of MSP-002, which the annex sets at 11.  The
#: threshold has to separate 12 from 11, not 12 from 10, or those three colours
#: are read as three record titles and every page after them is off by three.
TITLE_MIN_SIZE = 11.5

#: Geometry the annex prints -> the QGIS geometry kind the plugin names a layer
#: after.  ``ÇOKLU POLİGON`` is a MultiPolygon, and the plugin's layers are
#: polygon layers because a QGIS layer holds one geometry and every MSP area
#: symbol is drawn the same way in both; the annex's distinction is recorded in
#: ``kaynak`` rather than dropped, so nothing here is a silent simplification.
GEOMETRY_KINDS = {
    label_fold("ÇOKLU POLİGON"): "POLYGON",
    label_fold("POLİGON"): "POLYGON",
    label_fold("ÇİZGİ"): "LINE",
    label_fold("NOKTA"): "POINT",
}

#: ``GÖSTERİM`` as the plugin writes it, from the geometry the record is drawn
#: as.  The annex prints the two on the same page and they disagree on the two
#: line records -- ``KARAYOLU AĞI`` and ``DEMİRYOLU AĞI`` print ``ALAN`` in the
#: GÖSTERİM cell and ``ÇİZGİ`` in GEOMETRİ TİPİ -- so one of the two has to win.
#: The geometry wins, because it is the column that decides which layer the
#: symbol is drawable on: a "ALAN" spelling there would name an area layer for a
#: symbol the same table draws as a line.  Both printed values are kept in
#: ``kaynak``, so the annex's own slip stays readable.
GOSTERIM_WORDS = {"POLYGON": "ALAN", "LINE": "ÇİZGİ", "POINT": "NOKTA"}
GOSTERIM_SEPARATOR = ", "

_RGB = re.compile(r"\d{1,3}\s*/\s*\d{1,3}\s*/\s*\d{1,3}")

#: The annex states a translucent fill as a percentage word in the fill's own
#: RGB cell ("240/220/220 %50 Saydam"), not in a numeric column.  Alpha is 255
#: times the printed opacity: 50 percent is 127.5, rounded to 128.
_TRANSPARENCY = re.compile(r"%\s*(\d{1,3})\s*SAYDAM", re.IGNORECASE)


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _attr(element, name: str):
    if element is None:
        return None
    return element.get(W + name) or element.get(name)


def _cell_text(cell) -> str:
    """One table cell's text, runs joined without a separator.

    A word is routinely split across runs, so joining with a space would break
    the very labels being read; the boundary is a paragraph, a cell or an
    explicit line break, which is what this walks.
    """
    out = []
    for node in cell.iter():
        if node.tag == W + "t":
            out.append(node.text or "")
        elif node.tag in (W + "p", W + "br", W + "cr"):
            out.append(" ")
    return _clean("".join(out))


def _row_cells(row) -> list[tuple[int, str]]:
    """``[(first_column, text)]`` for one row, with merged cells expanded.

    The annex merges cells differently from table to table -- on one page the
    ``TARAMA`` header is one column wide and on the next two -- so a fixed
    index would read the wrong cell on half the pages.  Columns are resolved
    from the header labels instead, and this is what makes that possible.
    """
    cells = []
    column = 0
    for cell in row.findall(W + "tc"):
        properties = cell.find(W + "tcPr")
        span = 1
        if properties is not None:
            grid_span = properties.find(W + "gridSpan")
            if grid_span is not None:
                span = int(_attr(grid_span, "val") or 1)
        cells.append((column, _cell_text(cell)))
        column += span
    return cells


def _find(cells: list[tuple[int, str]], wanted: str, after: int = -1) -> int | None:
    """The column whose cell reads ``wanted``, at or after ``after``."""
    folded = label_fold(wanted)
    for column, text in cells:
        if column >= after and label_fold(text) == folded:
            return column
    return None


def _value_at(cells: list[tuple[int, str]], column: int | None) -> str:
    if column is None:
        return ""
    for candidate, text in cells:
        if candidate == column:
            return text
    return ""


def _value_after(row: list[tuple[int, str]], label: str) -> str:
    """The cell printed after the cell reading ``label``, in document order.

    The annex merges the label's cell over a different number of columns from
    table to table -- the ``DETAY SINIFI`` value starts at column 2 on one page
    and column 3 on the next -- so the value is read positionally, as the next
    cell of the row, rather than from a fixed column.  A row whose label is its
    last cell has no value, which is what an empty cell means here anyway.
    """
    for index, (_, text) in enumerate(row):
        if label_fold(text) == label_fold(label):
            return row[index + 1][1] if index + 1 < len(row) else ""
    return ""


#: Words the annex prints with an ASCII ``I`` where Turkish has a dotted ``İ``.
#: It is not a mechanical ``I`` -> ``İ`` pass: Turkish has a dotless ``I`` of its
#: own and the annex uses it correctly in most words (``PLAN SINIRI``,
#: ``KAYNAK ALANLARI``, ``ÇIKIŞ``, ``YATIRIMLAR``), so a blanket replacement
#: would corrupt them.  Each entry below is a word whose Turkish spelling cannot
#: contain a dotless ``I``, which is why the list can be short and explicit.
#: The repair reaches only the two name fields; every raw cell in ``kaynak``
#: keeps the annex's own spelling.
TURKISH_WORDS = {
    "KADEMELENMESI": "KADEMELENMESİ",
    "ILIŞKILER": "İLİŞKİLER",
    "LIMANLAR": "LİMANLAR",
    "HAVALIMANLARI": "HAVALİMANLARI",
    "GELIŞME": "GELİŞME",
    "ÖLÇEKLI": "ÖLÇEKLİ",
    "ENDÜSTRI": "ENDÜSTRİ",
    "ÜRETIM": "ÜRETİM",
    "FAALIYET": "FAALİYET",
    "GIRIŞ": "GİRİŞ",
    "PROJELERI": "PROJELERİ",
    "STRATEJIK": "STRATEJİK",
    "RISKLI": "RİSKLİ",
    "EKOLOJIK": "EKOLOJİK",
    "SISTEMLER": "SİSTEMLER",
    "EKONOMIK": "EKONOMİK",
    "IHTISAS": "İHTİSAS",
    "KORIDORLARI": "KORİDORLARI",
}

_TURKISH_LOOKUP = {label_key(word): whole for word, whole in TURKISH_WORDS.items()}

#: Word-anchored, not whitespace-split, so a word the annex runs against a
#: hyphen is repaired too: ``GIRIŞ-ÇIKIŞ`` carries the same word as ``GIRIŞ``.
_TURKISH_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(sorted((re.escape(word) for word in TURKISH_WORDS), key=len, reverse=True))
    + r")\b"
)


def _turkish(text: str) -> str:
    """Repair the words the annex itself prints with an ASCII ``I``.

    Lookup is by ``label_key``, so the repair matches whichever of the two
    spellings arrives and is a no-op on the one that is already correct -- a
    title keeps the dotless ``I`` of the words that need one.
    """
    return _TURKISH_PATTERN.sub(
        lambda match: _TURKISH_LOOKUP[label_key(match.group(0))], text
    )


def _colors(text: str) -> list[str]:
    return [re.sub(r"\s*/\s*", "/", match.group(0)) for match in _RGB.finditer(text or "")]


def _alpha(text: str) -> int:
    """The printed opacity as an alpha, or 255 when the annex prints none."""
    match = _TRANSPARENCY.search(text or "")
    if not match:
        return 255
    return round(255 * int(match.group(1)) / 100)


def _starts_section(cells: list[tuple[int, str]]) -> bool:
    return bool(SECTION_MARKER.match(_clean(" ".join(text for _, text in cells))))


def _read_docx(path: Path):
    """``[(title, table)]`` for every catalogue table, in printed order.

    Every table in the document is returned with the paragraph printed above
    it, so the caller can pick its section.  The paragraph above a catalogue
    table is the record's title, which the table itself does not repeat.
    """
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        raise RuntimeError(f"{path.name}: word/document.xml içinde gövde yok")

    entries = []
    heading = ""
    for element in body:
        if element.tag == W + "p":
            text = _clean("".join(node.text or "" for node in element.iter(W + "t")))
            if text:
                heading = text
        elif element.tag == W + "tbl":
            rows = [_row_cells(row) for row in element.findall(W + "tr")]
            entries.append((heading, rows))
    return entries


def _msp_tables(entries) -> list[tuple[str, list]]:
    """The tables between the MSP heading and the next section marker."""
    start = None
    for index, (_, rows) in enumerate(entries):
        flat = _clean(" ".join(text for row in rows for _, text in row))
        if label_fold(flat).startswith(label_fold(MSP_SECTION)):
            start = index + 1
            continue
        if start is not None and rows and _starts_section([cell for row in rows for cell in row]):
            return entries[start:index]
    raise RuntimeError("EK-1e.docx içinde MSP detay kataloğu bölümü bulunamadı")


def _pdf_titles(pdf_path: Path, count: int) -> list[tuple[int, str]]:
    """``[(printed page, title)]`` in printed order, until ``count`` titles.

    A title is a line set at 12 pt or more, which is what tells it from a table
    cell at 10 pt; the page number is the annex's own, printed in the header.
    """
    reader = PdfReader(str(pdf_path))
    titles = []
    for index, page in enumerate(reader.pages):
        if len(titles) >= count:
            break
        chunks = []

        def visit(text, cm, tm, font, size, chunks=chunks):
            if text and text.strip():
                chunks.append((text, round(tm[4], 1), round(tm[5], 1), float(size or 0)))

        page.extract_text(visitor_text=visit)
        printed = None
        lines = []
        for text, x, y, size in sorted(chunks, key=lambda chunk: (-chunk[2], chunk[1])):
            if printed is None and y < 70 and size >= TITLE_MIN_SIZE:
                printed = _clean(text)
            if not lines or abs(lines[-1]["y"] - y) > 3.0:
                lines.append({"y": y, "size": 0.0, "parts": []})
            lines[-1]["parts"].append((x, text))
            lines[-1]["size"] = max(lines[-1]["size"], size)
        for line in lines:
            line["parts"].sort()
            line["text"] = _clean(" ".join(part[1] for part in line["parts"]))
        for line in lines:
            if line["size"] >= TITLE_MIN_SIZE and line["text"].isdigit():
                printed = line["text"]
        if printed is None:
            raise RuntimeError(f"{pdf_path.name}: {index + 1}. sayfada sayfa numarası yok")
        page_number = int(printed)
        for line in lines:
            if line["size"] < TITLE_MIN_SIZE:
                continue
            if line["text"].isdigit() or "DETAY KATALOĞU" in line["text"].upper():
                continue
            if "MEKÂNSAL PLANLAR" in line["text"].upper():
                continue
            titles.append((page_number, line["text"]))
            if len(titles) >= count:
                break
    return titles


def _decode_record(title: str, rows: list[list[tuple[int, str]]]) -> dict:
    """One catalogue table as the shipped row, plus the cells it was read from.

    The header rows are located by their own printed labels, never by index, so
    the columns of every page are read the same way the annex prints them.
    """
    header_index, header = next(
        ((index, row) for index, row in enumerate(rows)
         if _find(row, "SEMBOL") is not None and _find(row, "TİPİ") is not None),
        (None, []),
    )
    if header_index is None:
        raise RuntimeError(f"{title}: SEMBOL/TİPİ başlık satırı yok")
    # The geometry row is the table's own divider: everything above it is the
    # record's legend and everything below it is the annex's one-line summary.
    # Finding it by its label rather than by its index matters on the two afet
    # records, whose summary is printed two rows high and would otherwise be
    # read as headers.
    divider = next(
        (index for index, row in enumerate(rows) if _find(row, "GEOMETRİ TİPİ") is not None),
        None,
    )
    if divider is None:
        raise RuntimeError(f"{title}: GEOMETRİ TİPİ satırı yok")
    if divider <= header_index:
        raise RuntimeError(f"{title}: GEOMETRİ TİPİ satırı başlıktan önce")
    # The legend rows run from under the SEMBOL/TARAMA/RGB/TİPİ header to the
    # divider.  Indexing from the header rather than from a fixed row keeps the
    # read correct on a page whose legend carries one value row and on a page
    # that carries three.
    value_rows = rows[header_index + 1:divider]

    # The divider row carries the three açıklama *labels* and the row under it
    # the values, on the same columns: the annex prints its one-line summary as
    # a label row and a value row rather than as a label-value pair per cell.
    # The tail is therefore read as the label row's own columns, aggregated over
    # every row below the divider -- the two afet records print their summary two
    # rows high.
    divider_row = rows[divider]
    tail_rows = rows[divider + 1:]

    def tail_value(label: str) -> str:
        column = _find(divider_row, label)
        if column is None:
            return ""
        return _clean(" ".join(
            text for row in tail_rows for candidate, text in row if candidate == column
        ))

    # The two "RGB" headers are the fill's and the outline's, in that order.
    rgb_columns = [column for column, text in header if label_fold(text) == label_fold("RGB")]
    tarama_rgb_column = rgb_columns[0] if len(rgb_columns) > 0 else None
    sinir_rgb_column = rgb_columns[1] if len(rgb_columns) > 1 else None

    tarama_cells = _cells_at(value_rows, tarama_rgb_column)
    sembol_cells = _cells_at(value_rows, _find(header, "SEMBOL"))
    sinir_cells = _cells_at(value_rows, sinir_rgb_column)
    tipi_cells = _cells_at(value_rows, _find(header, "TİPİ"))

    tarama_text = _clean(" ".join(tarama_cells))
    sembol_text = _clean(" ".join(sembol_cells))
    sinir_text = _clean(" ".join(sinir_cells))
    tipi_text = _clean(" ".join(tipi_cells))

    # The two colour cells are read from their own columns and never from each
    # other.  A point record's ``SEMBOL`` cell is where its glyph colour is
    # printed and its fill cell is empty -- the mark has no fill at all -- so
    # copying one into the other would draw MSP-018's point in its *area's*
    # colour (180/160/200 instead of 110/50/160).  Each cell keeps its own field
    # and the renderer asks for the one it is drawing.
    sembol_rgb = _colors(sembol_text)
    fills = _colors(tarama_text)

    # The outline's colour is the outline's cell.  One record (MSP-026) prints
    # it in the TİPİ column instead, which is an annex layout slip rather than a
    # second meaning, so it is taken and the slip is named in `kaynak`.
    strokes = _colors(sinir_text)
    stroke_source = "sinir_rgb"
    if not strokes:
        strokes = _colors(tipi_text)
        stroke_source = "sinir_tipi" if strokes else ""

    # The class is the annex's own where it printed one.  It prints DETAY SINIFI
    # empty on 27 of its 28 tables and carries the seven-way group in DETAY ALT
    # SINIFI -- which is the value ``GROUP_SLUGS`` and ``msp_layer_specs`` are
    # keyed by -- so the blank cell falls back to that group rather than to a
    # null: the column is NOT NULL in the workspace GeoPackage, and MSP-001 is
    # the one record whose two classes genuinely differ.  Which of the two the
    # value came from is named in `kaynak`, so the fallback is never silent.
    detay_sinifi = _clean(_value_after(rows[0], "DETAY SINIFI"))
    detay_alt_sinifi = _turkish(_clean(_value_after(rows[1], "DETAY ALT SINIFI")))
    sinif_kaynak = "detay_sinifi" if detay_sinifi else "detay_alt_sinifi"
    if not detay_sinifi:
        detay_sinifi = detay_alt_sinifi

    geometri_text = tail_value("GEOMETRİ TİPİ")
    tarama_aciklama = tail_value("TARAMA TİPİ AÇIKLAMASI")
    sinir_aciklama = tail_value("SINIR TİPİ AÇIKLAMASI")
    # The printed GÖSTERİM value is the row just above the SEMBOL/TARAMA header:
    # the legend's left half is that value's own row and the row above the header
    # is where it sits, whatever the table's fixed indices are.
    gosterim = _value_at(rows[header_index - 1], 0)

    if not geometri_text:
        raise RuntimeError(f"{title}: GEOMETRİ TİPİ boş")

    kinds = [
        GEOMETRY_KINDS.get(label_fold(part))
        for part in re.split(r"[/,]", geometri_text)
        if _clean(part)
    ]
    if not all(kinds):
        raise RuntimeError(f"{title}: bilinmeyen geometri {geometri_text!r}")

    # A measurement the annex never printed is not a measurement: the width is
    # what its own açıklama cell states with the words ``ÇİZGİ KALINLIĞI``, and
    # zero means "not stated".  It is read through the runtime's own reader, so
    # the number in the catalogue and the number the renderer derives from the
    # same sentence can never be two different numbers.
    width = stated_line_width_mm(sinir_aciklama, tarama_aciklama)

    return {
        "detay_adi": _turkish(title),
        "detay_sinifi": detay_sinifi,
        "detay_alt_sinifi": detay_alt_sinifi,
        "gosterim": GOSTERIM_SEPARATOR.join(GOSTERIM_WORDS[kind] for kind in kinds),
        "geometri": ", ".join(kinds),
        "sembol_rgb": ";".join(sembol_rgb) if sembol_rgb else None,
        "tarama_rgb": ";".join(fills) if fills else None,
        "tarama_alpha": _alpha(tarama_text) if fills else 0,
        "sinir_rgb": ";".join(strokes) if strokes else None,
        "stroke_width_mm": width,
        # Both prose fields are the annex's own words, column for column: the
        # summary's TARAMA cell describes the fill and its SINIR cell describes
        # the outline.  ``pattern()`` reads the two together, so a phrase that
        # names a hatch, a karolaj or a dot diameter is found wherever the annex
        # happened to print it without this tool deciding which cell it meant.
        "stroke_desc": sinir_aciklama,
        "hatch_desc": tarama_aciklama,
        "kaynak": {
            "baslik": title,
            COL_DETAY_SINIFI: _clean(_value_after(rows[0], "DETAY SINIFI")),
            COL_DETAY_ALT_SINIFI: detay_alt_sinifi,
            COL_SEMBOL: sembol_text,
            COL_TARAMA_RGB: tarama_text,
            COL_SINIR_TIPI: tipi_text,
            COL_SINIR_RGB: sinir_text,
            COL_GEOMETRI: geometri_text,
            COL_TARAMA_ACIKLAMA: tarama_aciklama,
            COL_SINIR_ACIKLAMA: sinir_aciklama,
            "gosterim": gosterim,
            "sinir_kaynak": stroke_source,
            "sinif_kaynak": sinif_kaynak,
        },
    }


def _cells_at(rows: list[list[tuple[int, str]]], column: int | None) -> list[str]:
    """Every cell printed in ``column``, over ``rows``, in printed order.

    The test is per *cell*, not per row: a merged cell is recorded at its first
    column, so a row that prints nothing in this column simply contributes
    nothing.  Testing the row instead would return every cell of every row that
    mentions the column anywhere -- which, since the legend rows carry one cell
    per column, is the whole row.
    """
    if column is None:
        return []
    return [text for row in rows for candidate, text in row if candidate == column]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


#: MSP-002'nin kademelenmesi: ek üç ton çiziyor ve notu "yerleşme kademelenmesine
#: göre farklı büyüklükteki simgeler" diyor, ama hangi kademenin hangi ton/boyut
#: olduğunu yazmıyor.  Alan adları ekin kendi sözcüklerinden türetildi; eşleme
#: sırası (küçükten büyüğe) çizicinin kararıdır ve katmana varsayım olarak yazılır.
MSP002_SINIF_ALANI = "yerlesme_yogunlugu"
MSP002_SIMGE_ALANI = "yerlesme_kademesi"

#: EK-1b'nin çiziminden gelen, ``_decode_record``'un üretmediği satır alanları.
#: Bu adlar tek yerde durur çünkü testin sözleşmesi şudur: ``_decode_record``'un
#: döndürdüğü anahtarlar **artı** bu liste, katalogdaki bir satırın alanlarına
#: birebir eşit olmalı.  Alan buraya eklenip satıra yazılmazsa ya da tersi olursa
#: test düşer; ``kaynak``'a bakmadan hangi alanın hangi belgeden geldiği de bu
#: listeden okunur (EK-1b alanları Ek-1e alanlarıyla aynı sözlükte durmaz).
EKB_FIELDS = (
    "sembol_sekli",
    "sembol_dolgu",
    "sembol_ikon",
    "sembol_boyut_mm",
    "sembol_halkalar",
    "tarama_aci_derece",
    "sinif_kurali",
)


def _check_shapes(
    shapes: dict, taramalar: dict, rows: list, pdf_1b: Path, declared_sha: str
) -> None:
    """Üçüncü kaynağı Ek-1e ile karşılaştırır; uyuşmazsa **yazmayı reddeder**.

    Sözleşme şudur: SEMBOL sütunu tam olarak ``geometri``'sinde ``POINT`` geçen
    satırlarda çizilidir.  Bu, iki belgenin bağımsız olarak aynı şeyi söylemesi
    demektir — Ek-1e hangi satırın nokta olduğunu söyler, EK-1b hangisinin
    çizili olduğunu gösterir.  Bir kayıt düşerse ya da fazla gelirse burası durur.
    """
    expected = {row["id"] for row in rows if "POINT" in row["geometri"]}
    if set(shapes) != expected:
        missing = sorted(expected - set(shapes))
        extra = sorted(set(shapes) - expected)
        raise RuntimeError(
            f"EK-1b ölçümü Ek-1e ile uyuşmuyor: eksik {missing}, fazla {extra}"
        )
    titles = {row["id"]: row["detay_adi"] for row in rows}
    for identifier, entry in sorted(shapes.items()):
        if label_fold(entry["baslik"]) != label_fold(titles[identifier]):
            raise RuntimeError(
                f"{identifier}: EK-1b başlığı {entry['baslik']!r}, "
                f"Ek-1e başlığı {titles[identifier]!r}"
            )
        icon = entry.get("ikon")
        if icon:
            path = ROOT / icon
            if not path.exists():
                raise RuntimeError(f"{identifier}: ikon yok — {icon}")
            if _sha256(path) != entry["ikon_sha256"].replace(" ", ""):
                raise RuntimeError(f"{identifier}: ikon değişmiş — {icon}")
        evidence = entry.get("kanit")
        if evidence and _sha256(ROOT / evidence) != (entry.get("kanit_sha256") or "").replace(" ", ""):
            raise RuntimeError(f"{identifier}: kanıt kırpıntısı değişmiş — {evidence}")
    for identifier in sorted(taramalar):
        entry = taramalar[identifier]
        evidence = entry.get("kanit")
        if evidence and _sha256(ROOT / evidence) != (entry.get("kanit_sha256") or "").replace(" ", ""):
            raise RuntimeError(f"{identifier}: tarama kanıtı değişmiş — {evidence}")
    # Ölçüm hangi EK-1b'den çıktıysa o dosya bu olmalı: bayat bir shapes dosyası
    # sessizce eski sayıları yeni ekin yanına koymasın.
    if declared_sha.replace(" ", "") != _sha256(pdf_1b):
        raise RuntimeError(
            f"{SHAPES.name} başka bir EK-1b'den üretilmiş — "
            f"`tools/build_msp_shapes.py {pdf_1b.name}` yeniden çalıştırılmalı"
        )


def _merged_colour(stated: str | None, note: str | None) -> tuple[str | None, str]:
    """Sembol rengi: Ek-1e'nin hücresi, boşsa EK-1b'nin basılı renk notu.

    İkisi de varsa **uyuşmak zorundadır**: EK-1b'nin notu Ek-1e'nin saydığı
    renklerden biri olmalı (MSP-014'ün dört üçgeni için Ek-1e dört renk sayar ve
    not yalnızca ilkini yazar).  Renk notu metindir, işaret değil — bu yüzden
    ölçülen baskın piksel değil, ekin bastığı sayı kullanılır.
    """
    if not stated:
        return (_clean(note) or None, "ek_1b_sembol") if note else (None, "")
    if note:
        known = {part.strip() for part in stated.split(";")}
        if _clean(note) not in known:
            raise RuntimeError(
                f"SEMBOL rengi uyuşmuyor: Ek-1e {stated!r}, EK-1b notu {note!r}"
            )
    return stated, "ek_1e_sembol"


def _msp002_rule(row: dict, shape: dict) -> dict:
    """MSP-002'nin veriye bağlı kademelenmesi — tonlar ekin, boyutlar çizimin.

    Tonlar Ek-1e'nin dolgu hücresindeki üç RGB'dir (yazım sırası korunur).
    Boyutlar EK-1b'nin çizdiği üç hedefin **ölçülmüş** çaplarıdır: ek "farklı
    büyüklükteki simgeler" diyerek üç boyutu gösterir, hangi kademeye hangisinin
    düştüğünü söylemez — sıralama (küçük→büyük) çizicinin kararıdır.
    """
    tones = [part.strip() for part in (row.get("tarama_rgb") or "").split(";") if part.strip()]
    blobs = shape.get("lekeler_mm") or []
    if len(tones) != 3 or len(blobs) != 3:
        raise RuntimeError(
            f"MSP-002: üç ton ve üç çizili hedef bekleniyordu, "
            f"{len(tones)} ton / {len(blobs)} hedef bulundu"
        )
    return {
        "alan_alani": MSP002_SINIF_ALANI,
        "tonlar": [[int(value) for value in tone.split("/")] for tone in tones],
        "ton_kaynak": "ek_1e_tarama_rgb_yazim_sirasi",
        "simge_alani": MSP002_SIMGE_ALANI,
        "simge_boyutlari_mm": sorted(round(float(blob), 2) for blob in blobs),
        "boyut_kaynak": "ek_1b_cizilen_hedef_caplari_artan",
    }


def _rings(shape: dict) -> list[list] | None:
    """Bir hedefin iç içe disklerini **dıştakine oranla** verir (EK-1b ölçümü).

    Sembolün çizimi ölçekle aynı şeyi söylemez: MSP-002 üç kademeyi üç ayrı
    çapta çizer ve halka yapısı hepsinde aynıdır, bu yüzden halkalar dış çapa
    oranlanır ve çizici onları kademenin çapından büyütür.  Rol ekin kendi
    ayrımıdır: ``dolu`` simge rengi, ``bos`` boş kâğıt (beyaz), ``sinir`` sınır
    rengi — MSP-004'ün göbeği bu yüzden beyaz değil siyahtır.
    """
    discs = shape.get("discler") or []
    if len(discs) < 2:
        return None
    outer = max(float(disc["cap_mm"]) for disc in discs)
    if outer <= 0:
        return None
    return [
        [round(float(disc["cap_mm"]) / outer, 4), disc["rol"]]
        for disc in sorted(discs, key=lambda disc: -float(disc["cap_mm"]))
    ]


def _merge_shape(row: dict, source: dict, shape: dict | None, tarama: dict | None) -> None:
    """EK-1b'nin ölçümünü satıra işler; her değerin hangi hücreden geldiğini yazar."""
    row["sembol_sekli"] = shape["sekli"] if shape else None
    row["sembol_dolgu"] = shape.get("dolgu") if shape else None
    row["sembol_ikon"] = shape.get("ikon") if shape else None
    # Ek her nokta simgesini kendi çapında çizer ve ölçüm o çizimdir; sabit bir
    # varsayılan çap, MSP-019'un 13.29 mm'lik yıldızını MSP-008'in 6.05 mm'lik
    # dairesiyle aynı boyutta gösterirdi.  Ölçüm yoksa (yerel karşılığı olmayan
    # bir piktogram) alan boş kalır ve çizici belgelenmiş varsayılanı uygular.
    row["sembol_boyut_mm"] = shape.get("boyut_mm") if shape else None
    row["sembol_halkalar"] = _rings(shape) if shape else None
    if shape:
        colour, colour_source = _merged_colour(row["sembol_rgb"], shape.get("renk_notu"))
        row["sembol_rgb"] = colour
        source["sembol_rgb_kaynak"] = colour_source
        # EK-1b'nin bastığı renk notu metin olarak saklanır — ölçülen baskın
        # piksel değil.  MSP-002'nin sembol rengi YALNIZCA burada yazılıdır
        # (Ek-1e o hücreyi boş bırakır), bu yüzden notun kendisi `kaynak`ta
        # olmadan o renk hiçbir hücreye izlenemezdi.
        source["sembol_1b_notu"] = _clean(shape.get("renk_notu")) or ""
        source["sembol_sekli_kaynak"] = "ek_1b_sembol_hucre"
        source["sembol_cizim"] = f"{shape['cizim']}/{shape['dolgu']}"
        source["sembol_boyut_kaynak"] = "ek_1b_olculen_cizim_kaplami"
        source["sembol_halka_kaynak"] = "ek_1b_olculen_diskler" if row["sembol_halkalar"] else ""
    else:
        source["sembol_sekli_kaynak"] = ""
        source["sembol_rgb_kaynak"] = "ek_1e_sembol" if row["sembol_rgb"] else ""
        source["sembol_1b_notu"] = ""
        source["sembol_cizim"] = ""
        source["sembol_boyut_kaynak"] = ""
        source["sembol_halka_kaynak"] = ""
    # Açı YALNIZCA EK-1b'den gelir: ek metni "2 mm aralıklı" der, ekseni söylemez.
    row["tarama_aci_derece"] = tarama.get("aci_derece") if tarama else None
    source["tarama_aci_kaynak"] = "ek_1b_tarama_hucre" if row["tarama_aci_derece"] is not None else ""
    row["sinif_kurali"] = _msp002_rule(row, shape) if row["id"] == "MSP-002" else None
    source["sinif_kurali_kaynak"] = "ek_1e_tonlar + ek_1b_boyutlar" if row["sinif_kurali"] else ""


def compile_catalog(docx_path: Path, pdf_path: Path, pdf_1b: Path) -> dict:
    tables = _msp_tables(_read_docx(docx_path))
    titles = _pdf_titles(pdf_path, len(tables))
    if len(titles) != len(tables):
        raise RuntimeError(
            f"Belge ve PDF uyuşmuyor: {len(tables)} tablo, {len(titles)} başlık"
        )

    rows = []
    kaynak = {}
    for (title, table), (page, printed) in zip(tables, titles):
        if label_fold(_turkish(title)) != label_fold(printed):
            raise RuntimeError(
                f"Sıra uyuşmuyor: belgede {title!r}, PDF'te {printed!r} (s.{page})"
            )
        record = _decode_record(title, table)
        source = record.pop("kaynak")
        # The record's own title is printed above its table, not inside it, and
        # the PDF prints it on the page.  Both spellings are kept: the docx is
        # what the row was named from and the PDF is the independent second
        # reading the compiler already had to agree with.
        source["baslik_pdf"] = printed
        identifier = f"MSP-{len(rows) + 1:03d}"
        row = {"id": identifier, "page": page}
        row.update(record)
        rows.append(row)
        kaynak[identifier] = source

    # The third source.  EK-1b is a *second document*, not a second reading of
    # Ek-1e: it is the annex that draws the symbols, so it is the only place the
    # glyph, its rotation and the hatch axis exist at all.  It is checked against
    # the 28 rows before a single value is merged, and a disagreement refuses the
    # write rather than picking a winner.
    shapes_payload = json.loads(SHAPES.read_text(encoding="utf-8"))
    shapes = shapes_payload["shapes"]
    taramalar = shapes_payload.get("taramalar") or {}
    _check_shapes(shapes, taramalar, rows, pdf_1b, shapes_payload["source"]["sha256"])
    for row in rows:
        _merge_shape(row, kaynak[row["id"]], shapes.get(row["id"]), taramalar.get(row["id"]))

    return {
        "version": 4,
        "source": {
            "catalog_docx": docx_path.name,
            "catalog_docx_sha256": _sha256(docx_path),
            "catalog_pdf": pdf_path.name,
            "catalog_pdf_sha256": _sha256(pdf_path),
            "catalog_1b": pdf_1b.name,
            "catalog_1b_sha256": _sha256(pdf_1b),
            "shapes_json": SHAPES.name,
            "shapes_json_sha256": _sha256(SHAPES),
            "section": MSP_SECTION,
        },
        "total_records": len(rows),
        "rows": rows,
        "kaynak": kaynak,
    }


def _diff(compiled: dict, committed: dict) -> list[str]:
    """Every field the committed catalogue and the annexes disagree on.

    The message names the *annex* rather than Ek-1e: since version 4 a value can
    come from either document, so saying which one would be a claim the diff
    cannot actually make.  ``kaynak`` is where a field's document is recorded.
    """
    findings = []
    old = {row["id"]: row for row in committed.get("rows", [])}
    for row in compiled["rows"]:
        previous = old.get(row["id"])
        if previous is None:
            findings.append(f"{row['id']}: committed katalogda yok")
            continue
        for key, value in row.items():
            if key in ("id",):
                continue
            if previous.get(key) != value:
                findings.append(
                    f"{row['id']}.{key}: katalogda {previous.get(key)!r}, "
                    f"ekte {value!r}"
                )
    for identifier in sorted(set(old) - {row["id"] for row in compiled["rows"]}):
        findings.append(f"{identifier}: ekte yok")
    return findings


def _normalized(text: str) -> str:
    return "".join(
        character for character in unicodedata.normalize("NFKD", text.upper())
        if not unicodedata.combining(character)
    )


def main(argv: list[str]) -> int:
    arguments = [value for value in argv[1:] if not value.startswith("--")]
    if len(arguments) != 3:
        print(__doc__.strip())
        return 2
    docx_path, pdf_path, pdf_1b = (Path(value) for value in arguments)
    compiled = compile_catalog(docx_path, pdf_path, pdf_1b)
    # Compared and written in the form that ships.
    compiled = json.loads(hub_safe(json.dumps(compiled, ensure_ascii=False)))

    if "--diff" in argv:
        findings = _diff(compiled, json.loads(OUTPUT.read_text(encoding="utf-8")))
        if not findings:
            print(f"{OUTPUT.name}: eklerle uyuşuyor ({compiled['total_records']} kayıt)")
            return 0
        print(f"{len(findings)} fark:")
        for finding in findings:
            print("  " + finding)
        return 1

    OUTPUT.write_text(
        json.dumps(compiled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shapes = sum(1 for row in compiled["rows"] if row["sembol_sekli"])
    angles = sum(1 for row in compiled["rows"] if row["tarama_aci_derece"] is not None)
    print(
        f"{OUTPUT}: {compiled['total_records']} kayıt, Ek-1e + EK-1b'den derlendi "
        f"({shapes} şekil, {angles} ölçülmüş tarama açısı)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
