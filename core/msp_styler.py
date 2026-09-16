"""Native MSP renderer generated from verified EK-1e PDF catalogue records (Pages 1-11)."""

import json
from pathlib import Path
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRendererCategory,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor


from .localization import localized_category

def _color(rgb_str: str | None, alpha: int = 255) -> QColor:
    if not rgb_str:
        return QColor(0, 0, 0, 0)
    try:
        parts = rgb_str.split(";")[0].split("/")
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return QColor(r, g, b, int(alpha if alpha is not None else 255))
    except (ValueError, IndexError):
        return QColor(160, 160, 160, alpha or 255)


class MSPStylerEngine:
    """Applies official EK-1e Mekânsal Strateji Planı (MSP) symbology."""

    def __init__(self):
        cat_path = Path(__file__).resolve().parents[1] / "styles" / "msp_catalog.json"
        data = json.loads(cat_path.read_text(encoding="utf-8"))
        self.rows = data.get("rows", [])
        self._previous = {}

    def _symbol(self, row: dict, geom_kind: str):
        tarama_rgb = row.get("tarama_rgb")
        tarama_alpha = row.get("tarama_alpha", 255)
        sinir_rgb = row.get("sinir_rgb")
        stroke_width = float(row.get("stroke_width_mm") or 0.3)
        stroke_desc = row.get("stroke_desc", "")

        if geom_kind == "polygon":
            symbol = QgsFillSymbol()
            symbol.deleteSymbolLayer(0)
            fill_layer = QgsSimpleFillSymbolLayer()
            fill_layer.setFillColor(_color(tarama_rgb, tarama_alpha))
            fill_layer.setStrokeColor(_color(sinir_rgb or "0/0/0", 255 if sinir_rgb else 0))
            fill_layer.setStrokeWidth(stroke_width)
            fill_layer.setStrokeWidthUnit(QgsUnitTypes.RenderMillimeters)

            if "boşluk" in stroke_desc or "kesik" in stroke_desc or "noktalama" in stroke_desc:
                fill_layer.setStrokeStyle(Qt.PenStyle.DashLine)

            symbol.appendSymbolLayer(fill_layer)
            return symbol

        if geom_kind == "line":
            symbol = QgsLineSymbol()
            line_layer = QgsSimpleLineSymbolLayer()
            line_layer.setColor(_color(sinir_rgb or tarama_rgb or "0/0/0", 255))
            line_layer.setWidth(stroke_width)
            line_layer.setWidthUnit(QgsUnitTypes.RenderMillimeters)

            if "boşluk" in stroke_desc or "kesik" in stroke_desc:
                line_layer.setPenStyle(Qt.PenStyle.DashLine)

            symbol.changeSymbolLayer(0, line_layer)
            return symbol

        # Point / Notation
        color = _color(tarama_rgb or sinir_rgb or "255/0/0", tarama_alpha)
        outline = _color(sinir_rgb or "0/0/0", 255)
        return QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": f"#{color.alpha():02x}{color.red():02x}{color.green():02x}{color.blue():02x}",
            "outline_color": outline.name(),
            "size": "4.0",
            "size_unit": "MM",
        })

    def apply(self, layer: QgsVectorLayer) -> int:
        """Apply MSP categorized styling to layer based on catalog_id or detay_adi."""
        if layer is None or not layer.isValid():
            raise ValueError('Geçerli bir MSP katmanı seçin')

        geom_map = {
            QgsWkbTypes.GeometryType.PolygonGeometry: "polygon",
            QgsWkbTypes.GeometryType.LineGeometry: "line",
            QgsWkbTypes.GeometryType.PointGeometry: "point",
        }
        geom_kind = geom_map.get(layer.geometryType())
        if not geom_kind:
            raise ValueError('MSP sembolojisi yalnızca alan, çizgi veya nokta katmanlarına uygulanabilir')

        # Determine target attribute field
        field = "catalog_id" if layer.fields().indexFromName("catalog_id") >= 0 else "fonksiyon_adi"

        rows = [
            r for r in self.rows
            if geom_kind.upper() in r.get("geometri", "").upper()
            or (geom_kind == "polygon" and "POLYGON" in r.get("geometri", "").upper())
            or (geom_kind == "point" and "POINT" in r.get("geometri", "").upper())
            or (geom_kind == "line" and "LINE" in r.get("geometri", "").upper())
        ]

        self._previous[layer.id()] = layer.renderer().clone()
        categories = []

        seen = set()
        for row in rows:
            label = f"{row['id']} - {row['detay_adi']} (s.{row['page']})"
            sym = self._symbol(row, geom_kind)
            rid = row.get("id")
            if rid and rid not in seen:
                categories.append(localized_category(rid, sym.clone(), label))
                seen.add(rid)
            detay = row.get("detay_adi")
            if detay and detay not in seen:
                categories.append(localized_category(detay, sym.clone(), label))
                seen.add(detay)

        # Default fallback category
        categories.append(localized_category(None, self._symbol({}, geom_kind), 'Diğer / Tanımsız'))

        renderer = QgsCategorizedSymbolRenderer(field, categories)
        layer.setRenderer(renderer)
        layer.setCustomProperty("mpyy/msp_catalog_source", "EK-1e PDF Sayfa 1-11")
        layer.triggerRepaint()
        return len(rows)

    def restore(self, layer: QgsVectorLayer) -> bool:
        renderer = self._previous.pop(layer.id(), None)
        if renderer is None:
            return False
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True
