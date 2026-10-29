"""Renders the MSP Ek-1e/EK-1b catalogue as a native QGIS renderer.

``core.msp_catalog`` decodes the annexes; this module draws them.  Every
measurement the annexes print is a *printed* millimetre, so the symbols are built
in map metres through ``NOMINAL_SCALE`` -- the same conversion
``core.mpyy_detail_catalog`` applies to the UİP/NİP/ÇDP annex, and for the same
reason: at 1:250 000 a 0.2 mm hatch is 50 m of ground, and a symbol built in
millimetres would be invisible.

Three sources, in this order.  A Ministry pictogram EK-1b draws and QGIS has no
shape for is drawn from the annex's own cropped artwork (``sembol_ikon``); a
symbol EK-1b draws with a shape QGIS has is drawn as that shape
(``MARKER_SHAPES``), so it stays recolourable and sharp at any zoom; and the few
marks EK-1b draws as more than one piece -- a bullseye's nested discs, four
source-coloured triangles, a disc with a cross through it -- are built from the
row's own measured geometry (``sembol_halkalar``).  Only a row with none of the
three reaches the grey fallback, which is why a pure test asserts the shape
vocabulary covers the whole catalogue: a grey circle is the one failure that
looks like a working renderer.

What the annexes state is drawn as stated.  What they do not state -- the dot at
a karolaj's centre, the hatch line width, the thickness of a boundary coloured
but not measured, the outline of a mark printed hollow -- is drawn at a
documented default (``KAROLAJ_DOT_MM``, ``HATCH_LINE_WIDTH_MM``,
``BOUNDARY_WIDTH_MM``), and every layer that uses one records it in
``mpyy/msp_approximated`` so the substitution is visible in the project rather
than passing for the Ministry's own measurement.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsGradientFillSymbolLayer,
    QgsLinePatternFillSymbolLayer,
    QgsLineSymbol,
    QgsLineSymbolLayer,
    QgsMarkerSymbol,
    QgsPointPatternFillSymbolLayer,
    QgsProperty,
    QgsRasterMarkerSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbolLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import QColor, QImage

from .legend_scope import FULL_PROPERTY, MODE_PROPERTY, full_renderer
from .localization import localized_category
from .msp_catalog import (
    APPROXIMATED_PROPERTY,
    CATEGORICAL_OFFSET_MM,
    HATCH_LINE_WIDTH_MM,
    KAROLAJ_DOT_MM,
    LAYER_PROPERTY,
    MARKER_SHAPES,
    MARKER_SIZE_MM,
    NOMINAL_SCALE,
    PATTERN_CATEGORICAL,
    PATTERN_CLASSED,
    PATTERN_DOT_HATCH,
    PATTERN_GRADIENT,
    PATTERN_GRID_DOT,
    PATTERN_LINE_HATCH,
    PICTOGRAM_PROPERTY,
    PLAN_KADEMESI,
    MSPLayer,
    MSPRow,
    decode_rows,
    msp_layer_specs,
    rows_for_layer,
)

MAP_METERS = Qgis.RenderUnit.MetersInMapUnits

#: One printed millimetre in metres on the ground at the MSP nominal scale.
MM_TO_GROUND = NOMINAL_SCALE / 1000.0

#: The hatch angle for a row EK-1b's TARAMA cell did not yield an axis for.  The
#: annex states a hatch's spacing in prose and never its direction, so the
#: direction is either measured off the drawing (``tarama_aci_derece``) or this
#: documented 45 degrees; a hard-coded angle would draw MSP-025's vertical hatch
#: at 45 and no test that only checks the renderer's type would notice.
HATCH_ANGLE_DEFAULT = 45.0

#: A mark printed hollow with no stated line width, e.g. MSP-020's star.
HOLLOW_STROKE_MM = HATCH_LINE_WIDTH_MM


@lru_cache(maxsize=None)
def _icon_image(path: str) -> tuple[str, float]:
    """An EK-1b pictogram as a base64 marker path and its height/width ratio.

    Embedded rather than referenced by file name: the artwork has to travel with
    the style when a workspace is saved to a GeoPackage and opened elsewhere, and
    ``core.mpyy_detail_catalog`` embeds its crops for the same reason.  The ratio
    is read from the image itself, so a re-crop at another resolution cannot
    silently squash the mark.
    """

    data = (Path(__file__).resolve().parents[1] / path).read_bytes()
    image = QImage.fromData(data)
    if image.isNull() or image.width() <= 0:
        raise RuntimeError(f"MSP ikonu okunamadı: {path}")
    return "base64:" + base64.b64encode(data).decode("ascii"), image.height() / image.width()

GEOMETRY_OF_LAYER = {
    QgsWkbTypes.GeometryType.PolygonGeometry: "POLYGON",
    QgsWkbTypes.GeometryType.LineGeometry: "LINE",
    QgsWkbTypes.GeometryType.PointGeometry: "POINT",
}


@dataclass(frozen=True)
class MSPResult:
    """What the renderer did, so the panel can report it without guessing."""

    catalog_rows: int
    styled_codes: int
    pictogram_missing: int
    approximated_codes: tuple[str, ...]


def _color(rgba):
    return QColor(*[int(channel) for channel in rgba])


def _mm(value):
    """A printed millimetre as map metres."""

    return float(value) * MM_TO_GROUND


class MSPStylerEngine:
    """MSP Ek-1e catalogue renderer, distinct from the UİP/NİP/ÇDP engines."""

    def __init__(self):
        self._decoded = decode_rows()
        self._previous = {}

    @property
    def catalog_rows(self) -> int:
        return len(self._decoded)

    def layer_specs(self) -> tuple[MSPLayer, ...]:
        return msp_layer_specs(self._decoded)

    def layer_spec(self, layer) -> MSPLayer | None:
        """The catalogue layer a QGIS layer corresponds to, matched by name.

        A layer the plugin did not create -- a user's own ``msp_kodu`` layer --
        has no spec, and ``apply`` then offers every catalogue code of its
        geometry instead of only the ones its group draws.
        """

        if layer is None:
            return None
        name = str(layer.name())
        for spec in self.layer_specs():
            if spec.name == name:
                return spec
        return None

    def rows_for(self, layer, geometry: str) -> tuple[MSPRow, ...]:
        spec = self.layer_spec(layer)
        if spec is not None and spec.geometry == geometry:
            return rows_for_layer(self._decoded, spec)
        return tuple(
            row for row in self._decoded if geometry in row.geometry_kinds
        )

    def _outline(self, row: MSPRow, colour, width_mm: float, dashed: bool):
        """The polygon's own boundary as a line layer.

        A fill layer cannot carry a dash pattern, so a boundary the annex draws
        dashed has to be a line symbol layer restricted to the exterior ring;
        without that restriction it would also draw every interior ring of a
        multi-part polygon with the same dash.
        """

        line = QgsSimpleLineSymbolLayer(_color(colour), _mm(width_mm))
        line.setWidthUnit(MAP_METERS)
        line.setRingFilter(QgsLineSymbolLayer.RenderRingFilter.ExteriorRingOnly)
        if dashed:
            line.setCustomDashVector([_mm(row.dash_mm[0]), _mm(row.dash_mm[1])])
            line.setCustomDashPatternUnit(MAP_METERS)
            line.setUseCustomDashPattern(True)
        return line

    def _poligon(self, row: MSPRow) -> QgsFillSymbol:
        symbol = QgsFillSymbol()
        while symbol.symbolLayerCount():
            symbol.takeSymbolLayer(0)
        pattern = row.pattern
        # A hatch or a karolaj is the symbol's meaning, so the flat fill goes
        # behind it only when the annex gives one; the pattern layer is drawn on
        # top of a NoBrush base otherwise.
        base = QgsSimpleFillSymbolLayer()
        if row.fill is None or pattern.kind in (
            PATTERN_GRID_DOT,
            PATTERN_DOT_HATCH,
            PATTERN_LINE_HATCH,
        ):
            base.setBrushStyle(Qt.BrushStyle.NoBrush)
        else:
            base.setColor(_color(row.fill))
            base.setBrushStyle(Qt.BrushStyle.SolidPattern)
        # The outline is drawn by its own line layer whenever the annex dashes
        # it, and by the fill layer otherwise; drawing it twice would double the
        # line weight where the two overlap.
        base.setStrokeStyle(Qt.PenStyle.NoPen if row.dash_mm or row.stroke is None else Qt.PenStyle.SolidLine)
        if row.stroke is not None and not row.dash_mm:
            base.setStrokeColor(_color(row.stroke))
            base.setStrokeWidth(_mm(row.drawn_stroke_width_mm))
            base.setStrokeWidthUnit(MAP_METERS)
        symbol.appendSymbolLayer(base)

        if pattern.kind == PATTERN_CLASSED:
            self._classed_fill(base, row)
        elif pattern.kind == PATTERN_GRADIENT:
            gradient = QgsGradientFillSymbolLayer()
            colours = _fill_colours(row)
            gradient.setColor(_color(colours[0]))
            gradient.setColor2(_color(colours[-1]))
            symbol.appendSymbolLayer(gradient)
        elif pattern.kind == PATTERN_GRID_DOT:
            diameter = pattern.size_mm or KAROLAJ_DOT_MM
            symbol.appendSymbolLayer(
                self._point_pattern(
                    _color(row.stroke or (0, 0, 0, 255)), diameter, pattern.spacing_mm
                )
            )
        elif pattern.kind == PATTERN_DOT_HATCH:
            symbol.appendSymbolLayer(
                self._point_pattern(
                    _color(row.stroke or (0, 0, 0, 255)), pattern.size_mm, pattern.spacing_mm
                )
            )
        elif pattern.kind == PATTERN_LINE_HATCH:
            symbol.appendSymbolLayer(
                self._line_pattern(
                    _color(row.stroke or (0, 0, 0, 255)),
                    pattern.spacing_mm,
                    # The annex states the hatch's own line width in the tarama
                    # cell and ``stroke_width_mm`` reads it there (MSP-025 prints
                    # 0.2 mm); a row that names only the spacing gets the
                    # documented hatch width.
                    row.stroke_width_mm or HATCH_LINE_WIDTH_MM,
                    # The axis is EK-1b's measurement or nothing at all: the
                    # annex's own sentence gives the spacing and never the
                    # direction, so this is the only place the direction exists.
                    row.tarama_aci_derece,
                )
            )
        if row.shadow is not None:
            # The annex's drop shadow ("178/178/178 gölge") is a grey band behind
            # the boundary.  QGIS has no symbol shadow, so the grey is drawn as a
            # wider under-layer stroke; the layer records the substitution.
            shadow = self._outline(
                row, row.shadow + (255,), row.drawn_stroke_width_mm * 2, False
            )
            symbol.insertSymbolLayer(0, shadow)
        if row.stroke is not None and row.dash_mm:
            symbol.appendSymbolLayer(
                self._outline(row, row.stroke, row.drawn_stroke_width_mm, True)
            )
        return symbol

    def _point_pattern(self, colour, diameter_mm, spacing_mm):
        marker = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, _mm(diameter_mm))
        marker.setSizeUnit(MAP_METERS)
        marker.setColor(colour)
        marker.setStrokeStyle(Qt.PenStyle.NoPen)
        fill = QgsPointPatternFillSymbolLayer()
        fill.setDistanceX(_mm(spacing_mm))
        fill.setDistanceY(_mm(spacing_mm))
        fill.setDistanceXUnit(MAP_METERS)
        fill.setDistanceYUnit(MAP_METERS)
        fill.setSubSymbol(QgsMarkerSymbol([marker]))
        return fill

    def _line_pattern(self, colour, spacing_mm, width_mm, angle=None) -> QgsLinePatternFillSymbolLayer:
        pattern = QgsLinePatternFillSymbolLayer()
        pattern.setLineAngle(HATCH_ANGLE_DEFAULT if angle is None else float(angle))
        pattern.setDistance(_mm(spacing_mm))
        pattern.setDistanceUnit(MAP_METERS)
        line = QgsSimpleLineSymbolLayer(colour, _mm(width_mm))
        line.setWidthUnit(MAP_METERS)
        pattern.setSubSymbol(QgsLineSymbol([line]))
        return pattern

    def _cizgi(self, row: MSPRow) -> QgsLineSymbol:
        layer = QgsSimpleLineSymbolLayer(
            _color(row.stroke or row.fill or (0, 0, 0, 255)),
            # A line's own width, never below the hatch width: at 1:250 000 the
            # hairline a zero would draw disappears entirely.
            _mm(max(row.drawn_stroke_width_mm, HATCH_LINE_WIDTH_MM)),
        )
        layer.setWidthUnit(MAP_METERS)
        if row.dash_mm:
            layer.setCustomDashVector([_mm(row.dash_mm[0]), _mm(row.dash_mm[1])])
            layer.setCustomDashPatternUnit(MAP_METERS)
            layer.setUseCustomDashPattern(True)
        symbol = QgsLineSymbol()
        symbol.changeSymbolLayer(0, layer)
        return symbol

    def _marker(self, colour, alpha=255) -> QgsSimpleMarkerSymbolLayer:
        marker = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, _mm(MARKER_SIZE_MM))
        marker.setSizeUnit(MAP_METERS)
        marker.setColor(QColor(colour[0], colour[1], colour[2], alpha))
        marker.setStrokeStyle(Qt.PenStyle.NoPen)
        return marker

    def _shape_layer(self, shape: str, size_mm: float) -> QgsSimpleMarkerSymbolLayer:
        """One native ``Qgis.MarkerShape``, at a size in printed millimetres.

        The attribute is looked up on the runtime rather than imported by name:
        ``MARKER_SHAPES`` stores the name, so a shape that exists in one QGIS
        version and not the other raises ``AttributeError`` here -- loudly, in the
        test that applies the style -- instead of at import time for every user.
        """

        marker = QgsSimpleMarkerSymbolLayer(getattr(Qgis.MarkerShape, shape), _mm(size_mm))
        marker.setSizeUnit(MAP_METERS)
        return marker

    def _native_marker(self, row: MSPRow, colour, alpha, size_mm: float):
        """EK-1b's mark as a QGIS shape: filled, or outlined where the annex is.

        A marker is filled by default and EK-1b prints some marks hollow -- its
        MSP-020 star is an outline -- so a hollow row moves its colour to the
        outline and clears the fill.  Painting the fill instead would draw a
        different symbol rather than a differently styled one.
        """

        marker = self._shape_layer(MARKER_SHAPES[row.sembol_sekli], size_mm)
        if row.is_hollow:
            marker.setColor(QColor(0, 0, 0, 0))
            marker.setStrokeColor(QColor(colour[0], colour[1], colour[2], alpha))
            marker.setStrokeWidth(_mm(row.stroke_width_mm or HOLLOW_STROKE_MM))
            marker.setStrokeWidthUnit(MAP_METERS)
            marker.setStrokeStyle(Qt.PenStyle.SolidLine)
        else:
            marker.setColor(QColor(colour[0], colour[1], colour[2], alpha))
            marker.setStrokeStyle(Qt.PenStyle.NoPen)
        return marker

    def _icon_marker(self, row: MSPRow, size_mm: float) -> QgsRasterMarkerSymbolLayer:
        """EK-1b's own cropped pictogram, so the glyph is the Ministry's artwork.

        Nothing is redrawn and nothing is recoloured: the crop already carries the
        annex's own strokes and colours, and a raster marker has no fill of its
        own to override them with.
        """

        path, aspect = _icon_image(row.sembol_ikon)
        marker = QgsRasterMarkerSymbolLayer(path, _mm(size_mm))
        marker.setFixedAspectRatio(aspect)
        marker.setSizeUnit(MAP_METERS)
        return marker

    def _bullseye(self, row: MSPRow, colour, alpha, size_mm: float):
        """EK-1b's nested discs, largest first (MSP-002, MSP-004).

        ``sembol_halkalar`` is the annex's own measurement, so the number of
        rings and each ring's width relative to the outer disc are the drawing's
        and not a reconstruction.  The discs are appended largest to smallest
        because each smaller one then paints over the centre of the one before it,
        which is what leaves a ring: drawing them the other way round would bury
        every ring under the largest disc and leave a plain circle.
        """

        boundary = row.stroke[:3] if row.stroke else (0, 0, 0)
        layers = []
        for ratio, role in row.sembol_halkalar:
            if role == "sinir":
                rgb = boundary
            elif role == "bos":
                # "boş" is the empty ring the annex leaves between two coloured
                # ones.  It is drawn as the paper colour it shows in the annex
                # illustration, because a QGIS marker has no hole to leave.
                rgb = (255, 255, 255)
            else:
                rgb = tuple(colour[:3])
            marker = self._shape_layer("Circle", size_mm * ratio)
            marker.setColor(QColor(rgb[0], rgb[1], rgb[2], alpha))
            if ratio == 1.0:
                marker.setStrokeColor(_color(boundary + (255,)))
                marker.setStrokeWidth(_mm(row.drawn_stroke_width_mm))
                marker.setStrokeWidthUnit(MAP_METERS)
                marker.setStrokeStyle(Qt.PenStyle.SolidLine)
            else:
                marker.setStrokeStyle(Qt.PenStyle.NoPen)
            layers.append(marker)
        return layers

    def _triangles(self, row: MSPRow, alpha):
        """EK-1b's four source-coloured triangles in its own 2x2 block (MSP-014).

        The annex prints "Kaynak türüne göre renkli nokta" -- one triangle per
        energy source, coloured by it -- and its legend block shows all four at
        once.  A categorized renderer carries one symbol per code and the plugin
        cannot know a feature's source, so all four are drawn as the annex's own
        block: ``sembol_boyut_mm`` measures the block, so each triangle is half of
        it and the quadrant offsets are a quarter.
        """

        block = row.marker_size_mm
        size = block / 2.0
        offset = block / 4.0
        layers = []
        for index, rgb in enumerate(row.colors):
            marker = self._shape_layer("Triangle", size)
            marker.setColor(QColor(rgb[0], rgb[1], rgb[2], alpha))
            marker.setStrokeStyle(Qt.PenStyle.NoPen)
            # The offset is in the unit that was set below it, so it is converted
            # like every other length here.  Passing the printed millimetres and
            # declaring metres puts each triangle 0.015 mm off centre instead of
            # 3.84 mm, which draws the last one over the other three.
            marker.setOffset(
                QPointF(_mm(-offset if index % 2 == 0 else offset),
                        _mm(-offset if index < 2 else offset))
            )
            marker.setOffsetUnit(MAP_METERS)
            layers.append(marker)
        return layers

    def _disc_with_cross(self, row: MSPRow, colour, alpha):
        """EK-1b's circled cross (MSP-022): the annex's disc under its own cross."""

        boundary = row.stroke[:3] if row.stroke else (0, 0, 0)
        size = row.marker_size_mm
        disc = self._shape_layer("Circle", size)
        disc.setColor(QColor(colour[0], colour[1], colour[2], alpha))
        disc.setStrokeColor(_color(boundary + (255,)))
        disc.setStrokeWidth(_mm(row.stroke_width_mm or HOLLOW_STROKE_MM))
        disc.setStrokeWidthUnit(MAP_METERS)
        disc.setStrokeStyle(Qt.PenStyle.SolidLine)
        cross = self._shape_layer("Cross", size)
        cross.setColor(QColor(boundary[0], boundary[1], boundary[2], alpha))
        cross.setStrokeStyle(Qt.PenStyle.NoPen)
        return [disc, cross]

    def _classed_fill(self, layer, row: MSPRow) -> None:
        """Bind a classed fill's tone to the row's own class field.

        The tones are the annex's and their order is the order it printed them, so
        the expression is a table lookup rather than an interpolation between the
        first and the last: a gradient would put a tone on the map the annex never
        printed, which is what this fill used to be drawn as.  *Which* end of the
        list is the lowest class is not something the annex states -- it prints
        three tones and no ranking -- so the pairing is the renderer's reading and
        the layer records it as an approximation.  A feature with no class
        recorded keeps the annex's first tone rather than turning invisible.
        """

        rule = row.sinif_kurali or {}
        field = str(rule.get("alan_alani") or "")
        tones = row.pattern.tones
        if not field or not tones:
            return
        fallback = row.fill[:3] if row.fill else tones[0]
        layer.setDataDefinedProperty(
            QgsSymbolLayer.Property.FillColor,
            QgsProperty.fromExpression(_tone_expression(field, tones, fallback)),
        )

    def _classed_size(self, layers, row: MSPRow, base_mm: float) -> None:
        """Bind a classed mark's size to the row's own class field.

        Each layer is scaled by the ratio it was already built with, so a
        bullseye's rings keep their measured proportions as the whole mark grows,
        and the ratio is read back off the layer rather than recomputed -- which
        is why the size the drawing uses and the size the expression names cannot
        drift apart.  ``base_mm`` is the same diameter the rings were measured
        against, so a class at the top of the list draws exactly EK-1b's own
        largest bullseye.
        """

        rule = row.sinif_kurali or {}
        field = str(rule.get("simge_alani") or "")
        sizes = [float(value) for value in rule.get("simge_boyutlari_mm") or ()]
        if not field or not sizes or base_mm <= 0:
            return
        for layer in layers:
            ratio = layer.size() / _mm(base_mm)
            branches = " ".join(
                f'WHEN to_int("{field}") = {index + 1} THEN {_mm(size) * ratio}'
                for index, size in enumerate(sizes)
            )
            layer.setDataDefinedProperty(
                QgsSymbolLayer.Property.Size,
                QgsProperty.fromExpression(
                    f"CASE {branches} ELSE {_mm(base_mm) * ratio} END"
                ),
            )

    def _marker_layers(self, row: MSPRow, colour, alpha, size_mm=None):
        """The marker symbol layers for one point code, by EK-1b's own shape."""

        size = row.marker_size_mm if size_mm is None else size_mm
        kind = row.shape_kind
        if kind == "raster":
            return [self._icon_marker(row, size)]
        if kind == "compound":
            if row.sembol_halkalar:
                return self._bullseye(row, colour, alpha, size)
            if row.sembol_sekli == "dort_ucgen":
                return self._triangles(row, alpha)
            return self._disc_with_cross(row, colour, alpha)
        if kind == "native":
            return [self._native_marker(row, colour, alpha, size)]
        return [self._marker(colour, alpha)]

    def _categorical(self, row: MSPRow, alpha):
        """The annex's palette as one quadrant marker per colour, offset apart.

        Reached only by a row that prints several colours for its mark and that
        EK-1b gives no shape for: every point row the annex actually draws now has
        one, so today this is the code path a re-extraction would land on rather
        than one the catalogue exercises.  The offsets keep the colours apart --
        at the same centre they would overlap into one blob and the palette would
        be invisible.
        """

        offset = _mm(CATEGORICAL_OFFSET_MM)
        layers = []
        for index, rgb in enumerate(row.colors):
            marker = self._marker(rgb, alpha)
            marker.setOffset(QPointF(-offset if index % 2 == 0 else offset,
                                     -offset if index < 2 else offset))
            marker.setOffsetUnit(MAP_METERS)
            layers.append(marker)
        return layers

    def _nokta(self, row: MSPRow) -> QgsMarkerSymbol:
        colours = _fill_colours(row)
        alpha = row.fill[3] if row.fill else 255
        base = _classed_size_base(row)
        if row.shape_kind != "none":
            layers = self._marker_layers(row, colours[0], alpha, base)
        elif row.pattern.kind == PATTERN_CATEGORICAL and len(row.colors) > 1:
            layers = self._categorical(row, alpha)
        else:
            marker = self._marker(colours[0], alpha)
            if row.stroke is not None:
                marker.setStrokeColor(_color(row.stroke))
                marker.setStrokeWidth(_mm(row.drawn_stroke_width_mm))
                marker.setStrokeWidthUnit(MAP_METERS)
                marker.setStrokeStyle(Qt.PenStyle.SolidLine)
            layers = [marker]
        if row.sinif_kurali:
            self._classed_size(layers, row, base)
        return QgsMarkerSymbol(layers)

    def _symbol(self, geometry: str, row: MSPRow):
        if geometry == "POLYGON":
            return self._poligon(row)
        if geometry == "LINE":
            return self._cizgi(row)
        return self._nokta(row)

    def apply(self, layer, field="msp_kodu"):
        if layer is None or not layer.isValid():
            raise ValueError('Geçerli bir hedef katman seçin.')
        if layer.fields().indexFromName(field) < 0:
            raise ValueError('MSP kod alanı hedef katmanda bulunamadı.')
        geometry = GEOMETRY_OF_LAYER.get(layer.geometryType())
        if geometry is None:
            raise ValueError(
                'MSP stili yalnızca alan, çizgi ve nokta katmanlarına uygulanabilir.'
            )
        rows = self.rows_for(layer, geometry)
        categories = [
            localized_category(row.id, self._symbol(geometry, row), row.caption)
            for row in rows
        ]
        categories.append(
            localized_category(None, _fallback_symbol(geometry), 'Eşleşmeyen / boş')
        )
        if layer.id() not in self._previous:
            base_renderer = full_renderer(layer)
            if base_renderer is not None:
                self._previous[layer.id()] = base_renderer
        layer.removeCustomProperty(FULL_PROPERTY)
        layer.removeCustomProperty(MODE_PROPERTY)
        layer.setRenderer(QgsCategorizedSymbolRenderer(field, categories))
        layer.triggerRepaint()

        pictograms, approximated = annotate_layer(
            layer, self.layer_spec(layer), rows, geometry
        )
        return MSPResult(
            self.catalog_rows,
            len(categories) - 1,
            len(pictograms),
            approximated,
        )

    def restore(self, layer):
        renderer = self._previous.pop(layer.id(), None)
        if renderer is None:
            return False
        layer.removeCustomProperty(FULL_PROPERTY)
        layer.removeCustomProperty(MODE_PROPERTY)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True


def annotate_layer(layer, spec, rows, geometry=None):
    """Record on the layer which of its codes are not drawn as the annex states.

    A custom property is not part of a saved style, so this runs from both ends:
    ``apply`` sets it when the MSP renderer is applied, and the workspace builder
    sets it when it configures a layer it opened -- otherwise a workspace reopened
    without the plugin re-applying the style would carry no record at all of the
    pictograms it substitutes, which is the one thing a planner has to be told.
    """

    geometry = geometry or (
        spec.geometry if spec is not None else GEOMETRY_OF_LAYER.get(layer.geometryType())
    )
    pictograms = tuple(row.id for row in rows if row.is_pictogram_for(geometry))
    approximated = tuple(row.id for row in rows if _is_approximated(row, geometry))
    layer.setCustomProperty(PICTOGRAM_PROPERTY, ",".join(pictograms))
    layer.setCustomProperty(APPROXIMATED_PROPERTY, ",".join(approximated))
    layer.setCustomProperty(LAYER_PROPERTY, spec.name if spec is not None else "")
    layer.setCustomProperty("mpyy/plan_kademesi", PLAN_KADEMESI)
    return pictograms, approximated


#: Colour of a feature whose code is empty or not in the catalogue.
FALLBACK_RGB = (140, 140, 140)


def _classed_size_base(row: MSPRow) -> float:
    """The diameter a classed mark's proportions are measured against.

    A class rule's sizes are EK-1b's own drawn bullseyes, and its rings are
    measured against the largest of them rather than against the mark's whole ink
    extent -- the extent includes the outline, the disc does not.  Using the
    extent would leave the top class marginally smaller than the drawing it was
    measured from, so the largest stated size is the base and the largest class
    reproduces the annex exactly.
    """

    rule = row.sinif_kurali or {}
    sizes = [float(value) for value in rule.get("simge_boyutlari_mm") or ()]
    return max(sizes) if sizes else row.marker_size_mm


def _tone_expression(field: str, tones, fallback) -> str:
    """A CASE lookup from a class field to the annex's own tones.

    ``to_int`` wraps the field because the class is stored as text in the
    workspace GeoPackage: comparing the text directly would match ``'1'`` and miss
    an integer ``1``, and a missing value has to reach the ``ELSE`` rather than
    compare equal to something.
    """

    branches = " ".join(
        f'WHEN to_int("{field}") = {index + 1} '
        f"THEN color_rgb({rgb[0]},{rgb[1]},{rgb[2]})"
        for index, rgb in enumerate(tones)
    )
    return (
        f"CASE {branches} "
        f"ELSE color_rgb({fallback[0]},{fallback[1]},{fallback[2]}) END"
    )


def _fill_colours(row: MSPRow) -> tuple[tuple[int, int, int], ...]:
    """Every colour the annex prints for the row, falling back to its outline."""

    if row.colors:
        return row.colors
    if row.fill is not None:
        return (row.fill[:3],)
    if row.stroke is not None:
        return (row.stroke[:3],)
    return (FALLBACK_RGB,)


def _fallback_symbol(geometry: str):
    """The symbol for a feature whose code is empty or not in the catalogue."""

    grey = _color(FALLBACK_RGB + (255,))
    if geometry == "POLYGON":
        fill = QgsSimpleFillSymbolLayer()
        fill.setColor(QColor(grey.red(), grey.green(), grey.blue(), 60))
        fill.setStrokeColor(grey)
        fill.setStrokeWidth(_mm(HATCH_LINE_WIDTH_MM))
        fill.setStrokeWidthUnit(MAP_METERS)
        symbol = QgsFillSymbol()
        while symbol.symbolLayerCount():
            symbol.takeSymbolLayer(0)
        symbol.appendSymbolLayer(fill)
        return symbol
    if geometry == "LINE":
        line = QgsSimpleLineSymbolLayer(grey, _mm(HATCH_LINE_WIDTH_MM))
        line.setWidthUnit(MAP_METERS)
        symbol = QgsLineSymbol()
        symbol.changeSymbolLayer(0, line)
        return symbol
    marker = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, _mm(MARKER_SIZE_MM))
    marker.setSizeUnit(MAP_METERS)
    marker.setColor(grey)
    marker.setStrokeStyle(Qt.PenStyle.NoPen)
    return QgsMarkerSymbol([marker])


def _is_approximated(row: MSPRow, geometry: str) -> bool:
    """True when the drawing is not the annex's own mark.

    A pictogram is drawn as a neutral marker, the boundary's drop shadow as an
    under-stroke, a graded three-stop fill as its two ends, the source-dependent
    point colouring as one multi-colour marker, and a karolaj's centre dot at a
    stated default the annex never gave: in each case the annex states something
    a QGIS categorized renderer cannot carry, and the layer says so instead of
    looking official.  A boundary the annex colours but never measures is the
    same kind of substitution -- ``BOUNDARY_WIDTH_MM`` is what a planner is
    looking at, not the Ministry's number.
    """

    if row.is_pictogram_for(geometry):
        return True
    if row.shadow is not None:
        return True
    if row.pattern.kind == PATTERN_GRADIENT:
        return True
    if row.pattern.kind == PATTERN_GRID_DOT:
        return True
    if geometry == "POINT" and not row.pattern.is_solid:
        return True
    if row.sinif_kurali:
        # The tones and the sizes are the annex's, but *which* tone is the lowest
        # class and which size belongs to which tier are not: it prints three of
        # each and ranks neither.  The order the renderer reads them in is a
        # choice, so the layer says so.
        return True
    if row.sembol_sekli == "dort_ucgen":
        # One triangle per energy source in the annex, all four at once here: a
        # categorized renderer carries one symbol per code and a feature's source
        # is not in the catalogue.
        return True
    if row.is_hollow and not row.stroke_width_mm:
        # A mark the annex prints hollow and does not measure: its outline is the
        # documented stroke width, not the Ministry's number.
        return True
    return not row.measures_its_boundary
