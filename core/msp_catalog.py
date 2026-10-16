"""MSP Ek-1e detail catalogue: reading, grouping and legend decoding.

``styles/msp_catalog.json`` is the only machine-readable MSP source the plugin
has.  The MPYY 1.1.7 XSD set the rest of the plugin compiles from carries
UIP/NIP/CDP only -- there is no MSP schema to follow -- so the Mekânsal
Strateji Planı (MSP) annex is the definition, and this module is the single
place that reads it.  Nothing here imports QGIS: the styler, the workspace
builder and the pure test all consume the same decoded values, and a pure test
can prove the decoding without a QGIS runtime.

The annex describes each symbol in print prose (``stroke_desc``,
``hatch_desc``), not in a legend file.  The decoders below turn that prose into
numbers with rules that read the text rather than keying off row ids, so a
re-extraction that renumbers the catalogue keeps working and a row that gains a
pattern is decoded rather than ignored.

Eleven layers, not twenty-eight.  The annex draws a symbol once per geometry it
appears in, so the four ``POLYGON, POINT`` rows (MSP-002, MSP-018, MSP-021,
MSP-022) have to be drawable as either -- and a QGIS layer holds one geometry
type.  The catalogue is therefore split by its own ``detay_alt_sinifi`` group
and by geometry, which is also how the annex prints it: one group per spread.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .localization import label_key


CATALOG_NAME = "msp_catalog.json"

#: Value the MSP layers carry in ``plan_kademesi``; ``core.plan_stage_audit``
#: matches it exactly, case-sensitively.
PLAN_KADEMESI = "MSP"

#: The official catalogue table stored inside an MSP workspace, the counterpart
#: of ``mpyy_detay_katalogu`` for the XSD workspaces.
CATALOG_TABLE = "msp_katalogu"

#: The Article 16 action-plan table ``core.msp_monitoring`` evaluates.
ACTION_TABLE = "msp_eylem_plani"

#: The annex states its measurements in printed millimetres, so a renderer has
#: to name the scale they belong to.  ``core.plan_stage_audit`` puts MSP between
#: 1:250 000 and 1:500 000 and this is its lower end, the scale an MSP drawing
#: is actually produced at; one printed millimetre is therefore 250 m on the
#: ground.  Declared here rather than in the styler so the conversion is the
#: same number for the renderer and for anything that audits it.
NOMINAL_SCALE = 250000

#: The annex draws MSP point symbols as pictograms and states no dimension for
#: them, so a marker diameter has to come from somewhere.  Two printed
#: millimetres is that choice -- 500 m on the ground at the nominal scale -- and
#: every layer that uses it records the substitution in its metadata instead of
#: passing the size off as the Ministry's measurement.
MARKER_SIZE_MM = 2.0

#: Dots at a karolaj's centres, where the annex names the grid but no diameter.
KAROLAJ_DOT_MM = 0.5

#: Hatch lines, where the annex names the spacing but no line width.
HATCH_LINE_WIDTH_MM = 0.2

#: A boundary the annex gives a colour for but no width.  The drawing needs a
#: number and the annex states none, so the width is this choice -- the value
#: five of the annex's own boundaries print -- and every layer whose rows use it
#: records the substitution in its metadata instead of passing the number off as
#: the Ministry's measurement.  Rows the annex *does* measure keep their own.
BOUNDARY_WIDTH_MM = 0.5

#: Half-separation of the four official energy-source colours when the annex's
#: source-dependent point colouring is drawn as one marker.
CATEGORICAL_OFFSET_MM = 0.6

#: Layer metadata keys recording what could not be reproduced exactly.
PICTOGRAM_PROPERTY = "mpyy/msp_pictogram_missing"
APPROXIMATED_PROPERTY = "mpyy/msp_approximated"
LAYER_PROPERTY = "mpyy/msp_layer"

#: ``detay_alt_sinifi`` is the annex's own seven-way split and the only group
#: the catalogue is organised by, so it is what a feature's ``strateji_bolgesi``
#: carries.  A new value here is a new official group: it must be added to
#: ``GROUP_SLUGS`` in the same change, which ``msp_layer_specs`` enforces by
#: raising rather than naming a layer after a group it does not know.
GROUP_SLUGS = {
    "PLAN SINIRI": "plan_siniri",
    "YERLEŞMELER SİSTEMİ VE ŞEHİRLEŞME": "yerlesme",
    "ANA ULAŞIM SİSTEMİ": "ulasim",
    "ANA ALTYAPI": "altyapi",
    "EKONOMİK İHTİSAS BÖLGELERİ VE KORİDORLARI": "ekonomi",
    "AFETLER AÇISINDAN RİSKLİ ALANLAR": "afet",
    "SU, DOĞAL PEYZAJ VE EKOSİSTEMLER": "su_peyzaj",
}

#: The three geometries the annex draws, in the order its legend prints them.
GEOMETRY_KINDS = ("POLYGON", "LINE", "POINT")

GEOMETRY_SUFFIX = {"POLYGON": "alan", "LINE": "cizgi", "POINT": "nokta"}

#: Decoded from ``hatch_desc`` / ``stroke_desc`` / ``sinif_kurali``; see
#: :func:`pattern`.
PATTERN_NONE = ""
PATTERN_GRADIENT = "gradient"
PATTERN_CATEGORICAL = "categorical"
PATTERN_LINE_HATCH = "line_hatch"
PATTERN_DOT_HATCH = "dot_hatch"
PATTERN_GRID_DOT = "grid_dot"
#: A fill the annex draws as a small number of *discrete* tones keyed to a class
#: (MSP-002), as opposed to a ramp: the annex prints three stops and EK-1b draws
#: three separate bullseyes, so the fill is a rule, not an interpolation.
PATTERN_CLASSED = "classed"

PATTERN_KINDS = (
    PATTERN_NONE,
    PATTERN_GRADIENT,
    PATTERN_CATEGORICAL,
    PATTERN_LINE_HATCH,
    PATTERN_DOT_HATCH,
    PATTERN_GRID_DOT,
    PATTERN_CLASSED,
)

#: EK-1b's SEMBOL vocabulary, as ``sembol_sekli`` carries it.  Eleven names, and
#: the table is the *whole* vocabulary: a re-extraction that names a twelfth
#: shape fails the pure test rather than drawing a grey circle, which is the one
#: failure that looks like a working renderer.
#:
#: ``MARKER_SHAPES`` maps a name to its ``Qgis.MarkerShape`` attribute; the
#: attribute is resolved against the runtime by the styler, so the same table
#: cannot silently reach a shape one QGIS version has and the other does not.
MARKER_SHAPES = {
    # 5 uçlu yıldız ile 8 uçlu yıldız iki ayrı şekildir: QGIS'te ``Star`` beş
    # uçludur ve sekiz uçlu olan ``AsteriskFill``'dır.  Adları karıştırmak
    # MSP-019 ile MSP-005'i birbirine çevirir.
    "yildiz5": "Star",
    "yildiz8": "AsteriskFill",
    "daire": "Circle",
    "kare": "Square",
    "altigen": "Hexagon",
}

#: Shapes drawn as more than one marker layer, because QGIS has no single
#: ``MarkerShape`` for them: a bullseye's nested discs (MSP-002, MSP-004), the
#: four source-coloured triangles (MSP-014) and a disc with a cross through it
#: (MSP-022).  They are built by the styler from the row's own measured geometry
#: -- ``sembol_halkalar`` -- and never from a fixed guess.
COMPOUND_SHAPES = ("hedef", "dort_ucgen", "daire_arti")

#: ``sembol_dolgu`` values: a filled mark and an outlined one.  EK-1b prints
#: MSP-020's star hollow and MSP-019's solid, so the two are different symbols
#: rather than one symbol with a styling choice.
SOLID_MARK = "dolu"
HOLLOW_MARK = "bos"

_RGB = re.compile(r"^\s*(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\s*$")
#: The same triplet, anywhere in a prose cell.  The annex writes an outline as
#: "<width> mm <colour> gölge", so the colour is no longer the whole cell.
_RGB_ANYWHERE = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

#: The annex opens an açıklama cell with the line's thickness and then states the
#: pattern, in that order: "ÇİZGİ KALINLIĞI: 0.7 mm 2mm düz çizgi, 2mm boşluk",
#: "ÇİZGİ KALINLIĞI: 0.2 mm 2 mm aralıklı".  The thickness is a measurement of
#: the line itself, not of the pattern, so it is cut out before any reader takes
#: the cell's first number as a spacing or a dash.  Both regexes are written
#: against a ``label_key``-folded cell, which is what makes one pattern cover the
#: annex's spelling and the plugin's ("ÇİZGİ" and "Cizgi" both fold to "CIZGI").
_WIDTH_CLAUSE = re.compile(r"CIZGI\s*KALINLIGI\s*:?\s*\d+(?:[.,]\d+)?\s*MM")
#: A dot diameter, stated the same way and just as positional: the number that
#: follows the phrase is the diameter and the one left over is the spacing.
_DIAMETER = re.compile(r"NOKTA\s*CAPI\D{0,12}?(\d+(?:[.,]\d+)?)")


@dataclass(frozen=True)
class MSPCode:
    """One annex row as a selectable code on one layer."""

    id: str
    detay_adi: str

    @property
    def caption(self) -> str:
        return f"{self.id} · {self.detay_adi}"


@dataclass(frozen=True)
class MSPLayer:
    """One drawable layer: a group's symbols for a single geometry type."""

    name: str
    group: str
    geometry: str
    codes: tuple[MSPCode, ...]

    @property
    def table_title(self) -> str:
        return f"MSP {self.group} — {self.geometry}"


@dataclass(frozen=True)
class MSPPattern:
    """A fill pattern decoded from the annex prose.

    ``spacing_mm`` and ``size_mm`` are the millimetres the annex prints; they are
    zero when the pattern does not carry the measure.
    """

    kind: str
    spacing_mm: float
    size_mm: float
    #: The discrete tones of a classed fill, in the annex's own printed order.
    #: Empty for every other kind.
    tones: tuple[tuple[int, int, int], ...] = ()

    @property
    def is_solid(self) -> bool:
        return self.kind == PATTERN_NONE


@dataclass(frozen=True)
class MSPRow:
    """A catalogue row with its decoded legend, so nothing decodes twice."""

    id: str
    page: int
    detay_adi: str
    detay_sinifi: str
    detay_alt_sinifi: str
    geometri: str
    gosterim: str
    #: The colours the annex states for the mark itself: its own ``SEMBOL`` cell
    #: where it has one -- a point symbol's colour is printed there and nowhere
    #: else -- and the fill's cell otherwise.  A dual-geometry row whose two
    #: forms differ (MSP-018 draws a 110/50/160 point over a 180/160/200 area)
    #: therefore keeps both, each in its own field.
    colors: tuple[tuple[int, int, int], ...]
    fill: tuple[int, int, int, int] | None
    stroke: tuple[int, int, int, int] | None
    stroke_width_mm: float
    dash_mm: tuple[float, float] | None
    shadow: tuple[int, int, int] | None
    pattern: MSPPattern
    #: EK-1b's SEMBOL vocabulary name, or empty.  ``sembol_rgb`` above is the
    #: mark's colour; this is its *shape*, which no earlier version of the
    #: catalogue carried -- which is why every point used to be drawn as a dot.
    sembol_sekli: str = ""
    #: ``dolu`` / ``bos``: a solid mark or an outlined one (see ``SOLID_MARK``).
    sembol_dolgu: str = ""
    #: Path to the cropped artwork, for the pictograms QGIS has no shape for.
    sembol_ikon: str | None = None
    #: EK-1b's measured extent of the drawn mark, in printed millimetres.
    sembol_boyut_mm: float | None = None
    #: For a bullseye: ``(ratio of the outer disc, role)`` per disc, largest
    #: first.  Measured from the annex's own drawing, so the nested rings are
    #: EK-1b's geometry and not a plausible-looking reconstruction.
    sembol_halkalar: tuple[tuple[float, str], ...] = ()
    #: The hatch's rotation in degrees, measured off EK-1b's TARAMA cell.  The
    #: annex states the spacing in prose but never the axis, so this is the only
    #: place the axis exists; ``None`` means it was not measured.
    tarama_aci_derece: float | None = None
    #: The class rule of a fill whose tone and mark size are data-driven.
    sinif_kurali: dict | None = None

    @property
    def marker_size_mm(self) -> float:
        """The mark's diameter: EK-1b's measurement, else the documented default.

        The annex draws each point symbol at its own size -- MSP-019's star is
        twice MSP-008's disc -- so one fixed diameter would flatten a
        distinction the annex makes.  Only a row EK-1b measured nothing for
        falls back to :data:`MARKER_SIZE_MM`.
        """

        return self.sembol_boyut_mm or MARKER_SIZE_MM

    @property
    def is_hollow(self) -> bool:
        """True for a mark the annex draws as an outline rather than a solid."""

        return self.sembol_dolgu == HOLLOW_MARK

    @property
    def shape_kind(self) -> str:
        """"raster", "native", "compound" or "none" -- how the styler draws it.

        Ordered, because the three are not alternatives a row can pick between:
        artwork wins over a native shape, and a name in neither table is ``none``
        so the fallback is reached rather than guessed at.  A pure test asserts
        the vocabulary is total over the catalogue, so ``none`` is a bug and not
        a case.
        """

        if self.sembol_ikon:
            return "raster"
        if self.sembol_sekli in MARKER_SHAPES:
            return "native"
        if self.sembol_sekli in COMPOUND_SHAPES:
            return "compound"
        return "none"

    @property
    def drawn_stroke_width_mm(self) -> float:
        """The thickness to draw a boundary with.

        The annex's own where it measured one, and ``BOUNDARY_WIDTH_MM`` where it
        coloured the boundary without measuring it -- QGIS has no zero-width
        line, so a stated colour has to have a thickness.  The row says which of
        the two this is through :attr:`measures_its_boundary`, so a substitution
        is recorded on the layer rather than passed off as the Ministry's number.
        """

        return self.stroke_width_mm or BOUNDARY_WIDTH_MM

    @property
    def measures_its_boundary(self) -> bool:
        """True when the annex states the thickness of the boundary it colours.

        Only a row that *has* a boundary can leave one unmeasured: an area the
        annex draws with no outline is drawn with none, so there is nothing for a
        default to stand in for.
        """

        return self.stroke is None or self.stroke_width_mm > 0.0

    @property
    def geometry_kinds(self) -> tuple[str, ...]:
        return geometry_kinds(self.geometri)

    @property
    def caption(self) -> str:
        return f"{self.id} · {self.detay_adi}"

    def is_pictogram_for(self, geometry: str) -> bool:
        """True when this row drawn as ``geometry`` is a glyph the plugin cannot draw.

        The annex draws several symbols twice ("POLYGON, POINT"): the area form is
        a fill with an outline and the point form is a glyph, so whether a row is
        a glyph at all depends on which of the two is being drawn.

        Being a glyph is not the same as being *missing*, and this is the second
        question.  Every point row EK-1b draws now reaches one of three drawings --
        the annex's own cropped artwork, a native ``MarkerShape``, or a compound
        built from the row's measured rings -- so the answer is that the glyph is
        drawn as the Ministry draws it.  A row reaches this only when it has none
        of the three, which today is no row at all: that is the point, because the
        failure this reports is the one that looks like a working renderer.
        """

        return (
            geometry == "POINT"
            and "POINT" in self.geometry_kinds
            and self.shape_kind == "none"
        )


def catalog_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    return Path(__file__).resolve().parents[1] / "styles" / CATALOG_NAME


def load_catalog(path=None) -> dict:
    return json.loads(catalog_path(path).read_text(encoding="utf-8"))


def decode_rows(document_or_path=None) -> tuple[MSPRow, ...]:
    """Every catalogue row with its legend decoded, in the order the annex prints."""

    if isinstance(document_or_path, dict):
        document = document_or_path
    else:
        document = load_catalog(document_or_path)
    rows = []
    for raw in document["rows"]:
        rows.append(
            MSPRow(
                id=str(raw["id"]),
                page=int(raw["page"]),
                detay_adi=str(raw["detay_adi"]),
                detay_sinifi=str(raw["detay_sinifi"]),
                detay_alt_sinifi=str(raw["detay_alt_sinifi"]),
                geometri=str(raw.get("geometri") or ""),
                gosterim=str(raw.get("gosterim") or ""),
                colors=(rgb_triplets(raw.get("sembol_rgb"))
                        or rgb_triplets(raw.get("tarama_rgb"))),
                fill=fill_rgba(raw),
                stroke=stroke_rgba(raw),
                stroke_width_mm=stroke_width_mm(raw),
                dash_mm=dash_mm(raw),
                shadow=shadow_rgb(raw),
                pattern=pattern(raw),
                sembol_sekli=str(raw.get("sembol_sekli") or ""),
                sembol_dolgu=str(raw.get("sembol_dolgu") or ""),
                sembol_ikon=_icon_path(raw.get("sembol_ikon")),
                sembol_boyut_mm=_millimetres(raw.get("sembol_boyut_mm")),
                sembol_halkalar=_rings(raw.get("sembol_halkalar")),
                tarama_aci_derece=_degrees(raw.get("tarama_aci_derece")),
                sinif_kurali=raw.get("sinif_kurali") or None,
            )
        )
    return tuple(rows)


def _icon_path(value) -> str | None:
    """The artwork path, only when it is one the plugin actually ships.

    A catalogue that names a file the plugin does not carry would draw nothing at
    all for that code -- the mark would vanish rather than fall back -- so the
    path is resolved here, against the plugin root, and a missing file is treated
    as "no artwork" so the native shape or the documented fallback applies.
    """

    text = str(value or "").strip()
    if not text:
        return None
    return text if (_plugin_root() / text).is_file() else None


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _millimetres(value) -> float | None:
    """A printed millimetre, or ``None`` when the annex measured nothing."""

    try:
        measured = float(value)
    except (TypeError, ValueError):
        return None
    return measured if measured > 0.0 else None


def _degrees(value) -> float | None:
    """A measured angle.  Zero is a real axis -- a horizontal hatch -- not "none"."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rings(value) -> tuple[tuple[float, str], ...]:
    """Decode ``[[ratio, role], ...]``, dropping a disc that does not decode."""

    rings = []
    for entry in value or ():
        try:
            ratio, role = entry
            rings.append((float(ratio), str(role)))
        except (TypeError, ValueError):
            continue
    return tuple(rings)


def class_rule(decoded=None) -> dict:
    """The one class rule the catalogue carries, or an empty mapping.

    Read from the catalogue rather than restated as a constant here: the tones and
    the sizes are EK-1b's measurements and live in ``styles/msp_catalog.json``
    with their provenance, so a second copy in code would be a second number that
    no test compares to the first.
    """

    source = decode_rows() if decoded is None else decoded
    for row in source:
        if row.sinif_kurali:
            return dict(row.sinif_kurali)
    return {}


def rows(path=None) -> tuple[dict, ...]:
    """The raw annex rows, for callers that only need the printed fields."""

    return tuple(load_catalog(path)["rows"])


def groups(source=None) -> tuple[str, ...]:
    """The seven official MSP strategic groups, in annex order.

    Accepts either the raw annex rows or :func:`decode_rows` output, because the
    layer specs have to keep annex order while working on decoded rows.
    """

    source = rows() if source is None else source
    seen = []
    for row in source:
        group = row.detay_alt_sinifi if isinstance(row, MSPRow) else row["detay_alt_sinifi"]
        if group not in seen:
            seen.append(group)
    return tuple(seen)


def geometry_kinds(geometri: str) -> tuple[str, ...]:
    """"POLYGON, POINT" -> ("POLYGON", "POINT"), in the annex's own order."""

    parts = [part.strip().upper() for part in str(geometri or "").split(",")]
    return tuple(part for part in parts if part)


def rgb_triplets(value) -> tuple[tuple[int, int, int], ...]:
    """Decode ``"225/165/100;180/110/0"`` into its ordered colour list.

    The annex writes a graded or category-dependent symbol as several colours in
    one cell; an entry that does not decode is dropped rather than guessed at.
    """

    triplets = []
    for chunk in str(value or "").split(";"):
        match = _RGB.match(chunk)
        if match:
            channel = tuple(int(part) for part in match.groups())
            triplets.append(channel)
    return tuple(triplets)


def fill_rgba(row) -> tuple[int, int, int, int] | None:
    """The symbol's fill, or ``None`` when the annex draws no fill at all.

    ``tarama_alpha == 0`` is the annex saying the symbol has no area fill --
    used by the boundary, hatch and dot symbols, whose meaning is carried by the
    outline or the pattern instead.
    """

    triplets = rgb_triplets(row.get("tarama_rgb"))
    if not triplets or int(row.get("tarama_alpha") or 0) <= 0:
        return None
    return triplets[0] + (int(row["tarama_alpha"]),)


def stroke_rgba(row) -> tuple[int, int, int, int] | None:
    triplets = rgb_triplets(row.get("sinir_rgb"))
    return triplets[0] + (255,) if triplets else None


def stated_line_width_mm(*texts) -> float:
    """The thickness the annex states with ``ÇİZGİ KALINLIĞI``, or ``0.0``.

    The clause is the annex's own way of measuring a line and the only thing in
    its açıklama cells that is a line width.  A cell that prints a bare measure
    is measuring something else -- a dot diameter, a hatch spacing, a karolaj
    grid -- so anchoring on the words is what keeps, say, ``NOKTA ÇAPI: 0.7 mm
    1 mm aralıklı`` from being read as a 0.7 mm boundary.  Zero therefore means
    "not stated", and the renderer's ``BOUNDARY_WIDTH_MM`` takes over.
    """

    for text in texts:
        match = _WIDTH_CLAUSE.search(label_key(text))
        if match:
            return float(_NUMBER.search(match.group(0)).group(0).replace(",", "."))
    return 0.0


def stroke_width_mm(row) -> float:
    """The boundary's thickness, or ``0.0`` when the annex states none.

    Read from both açıklama cells: ``SINIR TİPİ AÇIKLAMASI`` where the record has
    an outline, and ``TARAMA TİPİ AÇIKLAMASI`` where it has none and the cell is
    describing the tarama's own lines (MSP-024, MSP-025).  Either way it is the
    annex's own number, read rather than substituted.
    """

    return stated_line_width_mm(row.get("stroke_desc"), row.get("hatch_desc"))


def shadow_rgb(row) -> tuple[int, int, int] | None:
    """The annex's drop shadow, a bare colour printed with the word ``gölge``."""

    text = str(row.get("stroke_desc") or "")
    if "GOLGE" not in label_key(text):
        return None
    match = _RGB_ANYWHERE.search(text)
    return tuple(int(part) for part in match.groups()) if match else None


def dash_mm(row) -> tuple[float, float] | None:
    """The outline's dash and gap in millimetres, when the annex prints both.

    Only ``stroke_desc`` carries a dash: it is the field the annex uses for the
    line style, and it states the two measures in prose ("ÇİZGİ KALINLIĞI: 0.7
    mm 2mm düz çizgi, 2mm boşluk").  A row that names a measure without a gap is
    a hatch, not a dash, so requiring the word ``boşluk`` is what keeps the two
    apart, and the leading thickness is cut out because it is not part of the
    dash the sentence goes on to describe.
    """

    text = _WIDTH_CLAUSE.sub(" ", label_key(row.get("stroke_desc")))
    if "BOSLUK" not in text:
        return None
    numbers = _numbers(text)
    if len(numbers) < 2:
        return None
    return (numbers[0], numbers[1])


def pattern(row) -> MSPPattern:
    """Decode the annex's two açıklama cells into a drawable fill pattern.

    A fill that a class *rule* drives is read first, from ``sinif_kurali``: the
    annex prints three tones and EK-1b draws three separate bullseyes, so the
    fill is a discrete rule and not the ramp a cell listing several colours would
    otherwise look like.  That is the one pattern the colour cells cannot tell
    apart on their own, and it is why the rule is read before them.

    The remaining two are stated by the colour cells rather than in prose: a fill
    cell holding a ramp of colours is a graded fill and a symbol cell holding a
    palette is a point whose colour is a category (MSP-014 prints four).  A row
    that prints one colour in each is neither, which is why the test is on
    *distinct* colours and not on how many the cell happens to list.

    The rest is read from the prose, in the annex's own order: a karolaj is a
    grid of points and a stated dot diameter is a dot hatch, so both are read
    before the colour cells -- they name the shape outright.  ``aralıklı``, the
    annex's word for a spacing, is the broadest of the tests and comes last, so a
    point symbol whose sentence happens to contain it is still read from its
    palette.  The thickness clause that opens the same sentence is cut out
    first: it measures the line, not the spacing.
    """

    text = _WIDTH_CLAUSE.sub(
        " ",
        label_key(
            str(row.get("hatch_desc") or "") + " " + str(row.get("stroke_desc") or "")
        ),
    )
    numbers = _numbers(text)
    diameter = _diameter(text, numbers)
    # The stated diameter is one of the numbers in the sentence, so the spacing
    # is the other one; with only a diameter printed there is no spacing to read.
    spacing = next(
        (number for number in numbers if not diameter or number != diameter),
        numbers[0] if numbers else 0.0,
    )

    tones = _tones(row.get("sinif_kurali"))
    if tones:
        return MSPPattern(PATTERN_CLASSED, 0.0, 0.0, tones)
    if "KAROLAJ" in text:
        # A "5*5 mm" karolaj states the grid, not a dot diameter: reading the
        # second number as a size would draw 5 mm dots in a 5 mm grid.
        return MSPPattern(PATTERN_GRID_DOT, spacing, diameter)
    if "NOKTA CAPI" in text:
        return MSPPattern(PATTERN_DOT_HATCH, spacing, diameter)
    if _distinct(rgb_triplets(row.get("tarama_rgb"))) > 1:
        return MSPPattern(PATTERN_GRADIENT, 0.0, 0.0)
    if _distinct(rgb_triplets(row.get("sembol_rgb"))) > 1:
        return MSPPattern(PATTERN_CATEGORICAL, 0.0, 0.0)
    if "ARALIKLI" in text:
        return MSPPattern(PATTERN_LINE_HATCH, spacing, 0.0)
    return MSPPattern(PATTERN_NONE, 0.0, 0.0)


def msp_layer_specs(decoded=None) -> tuple[MSPLayer, ...]:
    """The catalogue split into one layer per official group and geometry.

    Raises ``ValueError`` on a group the slug table does not name: a
    re-extraction that adds an eighth MSP group must be given a layer name in
    the same change rather than be silently dropped or misnamed.
    """

    source = decode_rows() if decoded is None else decoded
    slots: dict[tuple[str, str], list[MSPCode]] = {}
    order: list[tuple[str, str]] = []
    for row in source:
        slug = GROUP_SLUGS.get(row.detay_alt_sinifi)
        if slug is None:
            raise ValueError(
                "Bilinmeyen MSP strateji grubu: " + str(row.detay_alt_sinifi)
            )
        for geometry in row.geometry_kinds:
            key = (row.detay_alt_sinifi, geometry)
            if key not in slots:
                slots[key] = []
                order.append(key)
            slots[key].append(MSPCode(row.id, row.detay_adi))
    group_order = groups(source)
    return tuple(
        MSPLayer(
            name="msp_" + GROUP_SLUGS[group] + "_" + GEOMETRY_SUFFIX[geometry],
            group=group,
            geometry=geometry,
            codes=tuple(slots[(group, geometry)]),
        )
        for group, geometry in sorted(
            order,
            key=lambda key: (group_order.index(key[0]), GEOMETRY_KINDS.index(key[1])),
        )
    )


def rows_for_layer(decoded, layer: MSPLayer) -> tuple[MSPRow, ...]:
    """The catalogue rows a layer draws, in catalogue order."""

    codes = {code.id for code in layer.codes}
    return tuple(
        row
        for row in decoded
        if row.id in codes and layer.geometry in row.geometry_kinds
    )


def codes_for_layer(layer: MSPLayer) -> tuple[str, ...]:
    return tuple(code.id for code in layer.codes)


def _diameter(text: str, numbers: list[float]) -> float:
    """The dot diameter, only where the annex actually prints one.

    Read from where the annex states it -- the number that follows ``NOKTA
    ÇAPI`` -- and never from a position: the annex prints the diameter first and
    the spacing after it ("NOKTA ÇAPI: 0.7 mm 1 mm aralıklı"), which is the
    opposite of the order the pattern's other measures come in.

    Zero means "not stated" rather than "not measured", so the styler applies its
    documented default instead of inventing a size the annex never gave.
    """

    match = _DIAMETER.search(text)
    if match is None:
        return 0.0
    return float(match.group(1).replace(",", "."))


def _tones(sinif_kurali) -> tuple[tuple[int, int, int], ...]:
    """A class rule's own tones, in the order the annex printed them.

    The order is the annex's, not a sort: it is what ties the first tone to the
    first class, and re-ordering them would silently pair each density with the
    wrong colour.  A tone that does not decode to three channels is dropped
    rather than clamped.
    """

    if not isinstance(sinif_kurali, dict):
        return ()
    tones = []
    for tone in sinif_kurali.get("tonlar") or ():
        try:
            channels = tuple(int(channel) for channel in tone)
        except (TypeError, ValueError):
            continue
        if len(channels) == 3:
            tones.append(channels)
    return tuple(tones)


def _distinct(triplets) -> int:
    """How many different colours a cell lists, counting each one once."""

    return len({tuple(triplet) for triplet in triplets})


def _numbers(text: str) -> list[float]:
    return [float(number.replace(",", ".")) for number in _NUMBER.findall(text)]
