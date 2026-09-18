"""Ek-1e Mekânsal Planlar Detay Katalogları on top of the Ministry SLD styles.

The catalog annexed to the regulation is the authority. Where the Ministry's GeoServer
SLDs disagree with it or reference assets that were never published, this module
corrects the QGIS symbols after the SLD has been loaded:

* symbols: an unpublished TaramaSembol SVG or a glyph of the unshipped Intelli Eplan
  font is replaced by the symbol cut from the catalog page (``resources/katalog_sembol``);
  rules the catalog gives a symbol and the SLD does not receive it;
* vectors: symbols the catalog defines by measurement (ÇDP idari merkezler, ÇDP yolları,
  bisiklet yolu) are drawn from those measurements;
* fills and hatches: colours taken from the catalog swatches, hatches the SLD lacks.

Every decision and its catalog page lives in ``styles/plangml_katalog/decisions.json``.
"""

import base64
import json
from functools import lru_cache
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsCentroidFillSymbolLayer,
    QgsFillSymbol,
    QgsGeometryGeneratorSymbolLayer,
    QgsHashedLineSymbolLayer,
    QgsLineSymbol,
    QgsMarkerLineSymbolLayer,
    QgsMarkerSymbol,
    QgsPointPatternFillSymbolLayer,
    QgsRasterMarkerSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = PLUGIN_ROOT / "styles" / "plangml_katalog"
CURRENT_OF = {"MUIP": "UIP", "MNIP": "NIP", "MCDP25": "CDP", "MCDP100": "CDP"}
MM = Qgis.RenderUnit.Millimeters
MAP_METERS = Qgis.RenderUnit.MetersInMapUnits


@lru_cache(maxsize=1)
def catalog():
    decisions = json.loads((CATALOG_DIR / "decisions.json").read_text(encoding="utf-8"))
    extracted = json.loads((CATALOG_DIR / "symbols.json").read_text(encoding="utf-8"))["symbols"]
    by_svg, by_glyph = {}, {}
    for key, entry in decisions["symbols"].items():
        for name in entry.get("svg", []):
            by_svg[name] = key
        for glyph in entry.get("glyphs", []):
            by_glyph[glyph] = key
    return {"decisions": decisions, "symbols": extracted, "svg": by_svg, "glyph": by_glyph}


@lru_cache(maxsize=None)
def _image(key):
    entry = catalog()["symbols"][key]
    data = (PLUGIN_ROOT / entry["file"]).read_bytes()
    width, height = entry["pixels"]
    return "base64:" + base64.b64encode(data).decode("ascii"), height / width


def raster_marker(key, height, unit, angle=0.0):
    """The catalog symbol ``key`` as a marker ``height`` tall (width follows the image)."""
    path, aspect = _image(key)
    marker = QgsRasterMarkerSymbolLayer(path, height / aspect, angle)
    marker.setFixedAspectRatio(aspect)
    marker.setSizeUnit(unit)
    return marker


def symbol_for_svg(name):
    return catalog()["svg"].get(name)


def symbol_for_glyph(family, character):
    return catalog()["glyph"].get(f"{family}#{character}")


def catalog_labels(level, type_name):
    """Label specs of the current level for this type (``labels`` in decisions.json)."""
    if level in CURRENT_OF:
        return []
    table = catalog()["decisions"].get("labels", {})
    return [spec for key, spec in table.items() if key == f"{level}/{type_name}/*"]


def _color(rgb):
    return QColor(*[int(v) for v in rgb.split("/")])


def _specs(section, level, type_name, label, include_borrowed):
    """Specs of ``section`` that apply to this rule, most specific key first."""
    table = catalog()["decisions"].get(section, {})
    levels = [level]
    if include_borrowed and level in CURRENT_OF:
        levels.append(CURRENT_OF[level])
    for candidate in levels:
        for key in (f"{candidate}/{type_name}/{label}", f"{candidate}/{type_name}/*"):
            if key in table:
                yield key, table[key]
                break
        else:
            continue
        break


def _rules(renderer):
    """(label, getter, setter) for every rule of a rule-based or single-symbol renderer."""
    if renderer is None:
        return []
    if renderer.type() == "RuleRenderer":
        return [(rule.label(), rule.symbol, rule.setSymbol) for rule in renderer.rootRule().children() if rule.symbol()]
    if hasattr(renderer, "symbol") and renderer.symbol() is not None:
        return [("*", renderer.symbol, renderer.setSymbol)]
    return []


def _merkez(spec):
    outer = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, spec["outer_m"])
    outer.setSizeUnit(MAP_METERS)
    outer.setColor(_color(spec["ring"]))
    outer.setStrokeColor(_color(spec["color"]))
    outer.setStrokeWidth(spec["stroke_mm"])
    outer.setStrokeWidthUnit(MM)
    inner = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, spec["inner_m"])
    inner.setSizeUnit(MAP_METERS)
    inner.setColor(_color(spec["color"]))
    inner.setStrokeStyle(Qt.PenStyle.NoPen)
    return QgsMarkerSymbol([outer, inner])


def _line(color, width):
    layer = QgsSimpleLineSymbolLayer(_color(color), width)
    layer.setWidthUnit(MM)
    return layer


def _road(spec):
    # cephe çizgileri outside the road body, kaldırım between them, yol platformu in the middle
    return QgsLineSymbol([
        _line(spec["color"], spec["total_mm"] + 2 * spec["cephe_mm"]),
        _line(spec["kaldirim"], spec["total_mm"]),
        _line(spec["color"], spec["platform_mm"]),
    ])


def _ladder(spec):
    layers = []
    for offset in (-spec["rung_mm"] / 2, spec["rung_mm"] / 2):
        rail = _line(spec["color"], spec["width_mm"])
        rail.setOffset(offset)
        rail.setOffsetUnit(MM)
        layers.append(rail)
    rung = QgsHashedLineSymbolLayer()
    rung.setInterval(spec["interval_mm"])
    rung.setIntervalUnit(MM)
    rung.setHashLength(spec["rung_mm"])
    rung.setHashLengthUnit(MM)
    rung.setSubSymbol(QgsLineSymbol([_line(spec["color"], spec["width_mm"])]))
    layers.append(rung)
    badge = QgsMarkerLineSymbolLayer()
    badge.setPlacements(Qgis.MarkerLinePlacement.CentralPoint)
    badge.setSubSymbol(QgsMarkerSymbol([raster_marker(spec["symbol"], spec["symbol_mm"], MM)]))
    layers.append(badge)
    return QgsLineSymbol(layers)


def _pattern(marker, spacing_mm):
    fill = QgsPointPatternFillSymbolLayer()
    fill.setDistanceX(spacing_mm)
    fill.setDistanceY(spacing_mm)
    fill.setDistanceXUnit(MM)
    fill.setDistanceYUnit(MM)
    fill.setSubSymbol(QgsMarkerSymbol([marker]))
    return fill


def _dot(spec):
    dot = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, spec["dot_mm"])
    dot.setSizeUnit(MM)
    dot.setColor(_color(spec["color"]))
    dot.setStrokeStyle(Qt.PenStyle.NoPen)
    return dot


def _hatch(symbol, spec, level, type_name, geometry_type):
    kind = spec["kind"]
    if kind == "motif":
        if "keep_fills" in spec:
            fills = [i for i in range(symbol.symbolLayerCount()) if symbol.symbolLayer(i).layerType() == "SimpleFill"]
            for index in reversed(fills[spec["keep_fills"]:]):  # grey stand-ins for the dropped SVG hatch
                symbol.deleteSymbolLayer(index)
        symbol.appendSymbolLayer(_pattern(raster_marker(spec["motif"], spec["size_mm"], MM), spec["spacing_mm"]))
    elif kind == "dots":
        symbol.appendSymbolLayer(_pattern(_dot(spec), spec["spacing_mm"]))
    elif kind == "random_dots":
        from qgis.core import QgsRandomMarkerFillSymbolLayer

        for index in range(symbol.symbolLayerCount()):
            if symbol.symbolLayer(index).layerType() == "SimpleFill":
                symbol.symbolLayer(index).setColor(_color(spec["fill"]))
                break
        random_fill = QgsRandomMarkerFillSymbolLayer(1, Qgis.PointCountMethod.DensityBasedCount, spec["area_per_dot_mm2"], 1)
        random_fill.setDensityAreaUnit(MM)
        random_fill.setSubSymbol(QgsMarkerSymbol([_dot(spec)]))
        symbol.appendSymbolLayer(random_fill)
    elif kind == "tile":
        from qgis.core import QgsRasterFillSymbolLayer

        path, _ = _image(spec["tile"])
        tile = QgsRasterFillSymbolLayer(path)
        tile.setWidth(catalog()["symbols"][spec["tile"]]["width_mm"])
        tile.setSizeUnit(MM)
        symbol.appendSymbolLayer(tile)
    elif kind == "copy":
        source = _copied_symbol(spec["from"], geometry_type)
        if source is not None:
            return source
    return symbol


def _copied_symbol(address, geometry_type):
    from qgis.core import QgsVectorLayer

    from .plangml_workspace import apply_eplan_symbology

    level, type_name, label = address.split("/", 2)
    kinds = {Qgis.GeometryType.Polygon: "MultiPolygon", Qgis.GeometryType.Line: "MultiLineString", Qgis.GeometryType.Point: "Point"}
    probe = QgsVectorLayer(f"{kinds[geometry_type]}?crs=EPSG:5254", "katalog", "memory")
    if not apply_eplan_symbology(probe, level, type_name):
        return None
    for rule_label, getter, _ in _rules(probe.renderer()):
        if rule_label == label:
            return getter().clone()
    return None


def _added_symbol(symbol, key, level, geometry_type):
    entry = catalog()["symbols"][key]
    scale = catalog()["decisions"]["levels_scale"].get(CURRENT_OF.get(level, level), 1000)
    marker = raster_marker(key, entry["height_mm"] * scale / 1000, MAP_METERS)
    if geometry_type == Qgis.GeometryType.Polygon:
        centroid = QgsCentroidFillSymbolLayer()
        centroid.setPointOnSurface(True)
        centroid.setSubSymbol(QgsMarkerSymbol([marker]))
        symbol.appendSymbolLayer(centroid)
    elif geometry_type == Qgis.GeometryType.Line:
        middle = QgsMarkerLineSymbolLayer()
        middle.setPlacements(Qgis.MarkerLinePlacement.CentralPoint)
        middle.setSubSymbol(QgsMarkerSymbol([marker]))
        symbol.appendSymbolLayer(middle)


def _border(symbol, spec):
    """Redraw a polygon boundary the way the catalog measures it: a line with a cross every interval."""
    for index in reversed(range(symbol.symbolLayerCount())):
        if symbol.symbolLayer(index).layerType() in ("MarkerLine", "SimpleLine"):
            symbol.deleteSymbolLayer(index)  # the SLD's own attempt at this boundary
    outline = _line(spec["color"], spec["width_mm"])
    cross = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Cross2, spec["size_mm"])
    cross.setSizeUnit(MM)
    cross.setColor(_color(spec["color"]))
    cross.setStrokeColor(_color(spec["color"]))
    cross.setStrokeWidth(spec["width_mm"])
    cross.setStrokeWidthUnit(MM)
    marks = QgsMarkerLineSymbolLayer()
    marks.setInterval(spec["interval_mm"])
    marks.setIntervalUnit(MM)
    marks.setSubSymbol(QgsMarkerSymbol([cross]))
    for layer in (outline, marks):
        generator = QgsGeometryGeneratorSymbolLayer.create({"geometryModifier": "boundary($geometry)", "SymbolType": "Line"})
        generator.setSubSymbol(QgsLineSymbol([layer]))
        symbol.appendSymbolLayer(generator)


def apply_catalog_overrides(layer, level, type_name):
    """Correct the SLD-derived renderer of ``layer`` to the catalog.

    Returns (notes of what was applied, labels of rules redrawn entirely from catalog measurements)."""
    applied, redrawn = [], set()
    geometry_type = layer.geometryType()
    current = level not in CURRENT_OF
    for label, getter, setter in _rules(layer.renderer()):
        symbol = getter().clone()
        for key, spec in _specs("vectors", level, type_name, label, include_borrowed=True):
            if spec["kind"] == "merkez" and geometry_type == Qgis.GeometryType.Point:
                symbol = _merkez(spec)
            elif spec["kind"] == "road" and geometry_type == Qgis.GeometryType.Line:
                symbol = _road(spec)
            elif spec["kind"] == "ladder" and geometry_type == Qgis.GeometryType.Line:
                symbol = _ladder(spec)
            else:
                continue
            applied.append(f"{label}: s.{spec['page']} ölçüleri")
            redrawn.add(label)
        if current:
            for key, spec in _specs("borders", level, type_name, label, include_borrowed=False):
                if spec["kind"] == "cross" and geometry_type == Qgis.GeometryType.Polygon:
                    _border(symbol, spec)
                    applied.append(f"{label}: s.{spec['page']} sınır çizgisi")
            for key, spec in _specs("fills", level, type_name, label, include_borrowed=False):
                for index in range(symbol.symbolLayerCount()):
                    if symbol.symbolLayer(index).layerType() == "SimpleFill":
                        symbol.symbolLayer(index).setColor(_color(spec["rgb"]))
                        applied.append(f"{label}: s.{spec['page']} renk {spec['rgb']}")
                        break
            for key, spec in _specs("hatches", level, type_name, label, include_borrowed=False):
                if isinstance(symbol, QgsFillSymbol):
                    symbol = _hatch(symbol, spec, level, type_name, geometry_type)
                    applied.append(f"{label}: s.{spec['page']} tarama")
        for key, entry in catalog()["decisions"]["symbols"].items():
            for target in entry.get("rules", []):
                if level in target["levels"] and target["type"] == type_name and target["rule"] in ("*", label):
                    _added_symbol(symbol, key, level, geometry_type)
                    applied.append(f"{label}: s.{entry['page']} sembol")
        setter(symbol)
    return applied, redrawn
