"""Explicit, reversible UIP style application from a user supplied catalog."""

from dataclasses import dataclass
import base64
import gzip
import hashlib
import json
from pathlib import Path

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsStyle,
    QgsSymbol,
    QgsVariantUtils,
    Qgis,
    QgsProject,
)
from qgis.PyQt.QtGui import QColor, QFontDatabase
from qgis.PyQt.QtCore import QTemporaryFile
from qgis.PyQt.QtXml import QDomDocument


from .attr_utils import is_null_value
from .fonts import register_mpyy_fonts
from .legend_scope import FULL_PROPERTY, MODE_PROPERTY, full_renderer
from .localization import localized_category

@dataclass(frozen=True)
class StyleResult:
    matched: int
    unknown_codes: tuple
    null_count: int
    warnings: tuple


class MPYYStylerEngine:
    """No default regulatory mapping is inferred from a display name.

    Mapping JSON: {"version": 1, "entries": [{"plan_level": "UIP",
    "geometry_type": "POLYGON", "code": "123", "symbol": "Exact name"}]}.
    Full native symbols are retained at every scale. This is not NIP/CDP
    generalization. Restoration is available during this engine's lifetime.
    """

    def __init__(self, xml_style_path=None, mappings=None) -> None:
        self._style = None
        self._mappings = {}
        self._previous = {}
        self.inventory = {}
        default_dir = Path(__file__).resolve().parents[1] / "styles"
        if xml_style_path is None and (default_dir / "UIPMPYYSTYLE.xml.gz").exists():
            xml_style_path = default_dir / "UIPMPYYSTYLE.xml.gz"
            if mappings is None:
                mappings = default_dir / "mappings.json"
        if xml_style_path:
            self.load_catalog(xml_style_path)
        if mappings:
            self.load_mappings(mappings)

    def load_catalog(self, path: str | Path) -> dict:
        # Keep catalog rendering independent of fonts installed on the user's
        # operating system.  This also covers direct engine use outside the
        # normal plugin initGui() path.
        register_mpyy_fonts()
        path = Path(path)
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as stream:
                data = stream.read(32 * 1024 * 1024 + 1)
        else:
            with path.open("rb") as stream:
                data = stream.read(32 * 1024 * 1024 + 1)
        if len(data) > 32 * 1024 * 1024:
            raise ValueError('Katalog 32 MiB içe aktarma sınırını aşıyor.')
        if b"<!ENTITY" in data.upper():
            raise ValueError('Harici XML varlıkları desteklenmiyor.')
        original_hash = hashlib.sha256(data).hexdigest()
        dependencies = Path(__file__).resolve().parents[1] / "styles"
        for reference, filename in (
            (
                b"Font Awesome icons (Font Awesome Free icons)/svg/solid/water.svg",
                "water.svg",
            ),
            (b"crosses/Cross4.svg", "Cross4.svg"),
        ):
            if reference in data:
                embedded = b"base64:" + base64.b64encode(
                    (dependencies / filename).read_bytes()
                )
                data = data.replace(reference, embedded)
        doc = QDomDocument()
        parsed = doc.setContent(data.decode("utf-8-sig"))
        if not (parsed[0] if isinstance(parsed, tuple) else parsed):
            raise ValueError("Stil XML'i geçersiz.")
        root = doc.documentElement()
        if root.tagName() != "qgis_style":
            raise ValueError('QGIS stil kataloğu bekleniyordu.')
        names = []
        element = root.firstChildElement("symbols").firstChildElement("symbol")
        while not element.isNull():
            names.append(element.attribute("name"))
            element = element.nextSiblingElement("symbol")
        if len(names) != len(set(names)):
            raise ValueError('Katalogda yinelenen üst düzey sembol adları var.')
        options = doc.elementsByTagName("Option")
        try:
            families = set(QFontDatabase.families())
        except TypeError:
            families = set(QFontDatabase().families())
        text_fallback = "DejaVu Sans"
        missing_fonts = set()
        # QDomNodeList is live: mutating while indexing repeatedly rebuilds it.
        option_elements = [options.at(i).toElement() for i in range(options.count())]
        for option in option_elements:
            value = option.attribute("value")
            if option.attribute("name") == "font" and value and value not in families:
                missing_fonts.add(value)
                # DejaVu Sans ships with the plugin, so ordinary catalog text
                # remains readable on Windows, Linux and macOS without relying
                # on Arial, Calibri or another system-only family.
                option.setAttribute("value", text_fallback)
        data = doc.toString().encode("utf-8")
        style = QgsStyle()
        style.createMemoryDatabase()
        temporary = QTemporaryFile()
        if not temporary.open():
            raise OSError('Geçici katalog dosyası oluşturulamıyor.')
        temporary.write(data)
        temporary.flush()
        if not style.importXml(temporary.fileName()):
            raise ValueError('QGIS stil kataloğunu içe aktaramadı.')
        if set(style.symbolNames()) != set(names):
            raise ValueError('QGIS üst düzey sembollerin tamamını içe aktaramadı.')
        self._style = style
        self.inventory = {
            "sha256": original_hash,
            "bytes": len(data),
            "top_level_symbols": len(names),
        }
        self.inventory["missing_fonts"] = sorted(missing_fonts)
        return dict(self.inventory)

    def load_mappings(self, source: str | Path | dict) -> int:
        payload = (
            json.loads(Path(source).read_text(encoding="utf-8"))
            if isinstance(source, (str, Path))
            else source
        )
        if (
            not isinstance(payload, dict)
            or payload.get("version") != 1
            or not isinstance(payload.get("entries"), list)
        ):
            raise ValueError('Desteklenmeyen eşleştirme sürümü.')
        mappings = {}
        for entry in payload["entries"]:
            key = (entry["plan_level"], entry["geometry_type"], str(entry["code"]))
            if key[0] != "UIP" or key[1] not in ("POLYGON", "LINE", "POINT"):
                raise ValueError(
                        'Yalnızca UİP nokta, çizgi ve alan eşleştirmeleri desteklenir.'
                )
            if not key[2] or key in mappings:
                raise ValueError('Boş veya yinelenen eşleştirme kodu.')
            mappings[key] = entry["symbol"]
        self._mappings = mappings
        return len(mappings)

    def export_lookup_rows(self) -> list[dict]:
        return [
            {
                "plan_duzeyi": level,
                "geometry_type": geometry.title(),
                "fonksiyon_kodu": code,
                "fonksiyon_adi": name,
            }
            for (level, geometry, code), name in sorted(self._mappings.items())
        ]

    def apply(
        self, layer, field_name: str = "fonksiyon_kodu", plan_level: str = "UIP"
    ) -> StyleResult:
        if self._style is None:
            raise ValueError('Önce bir QGIS XML kataloğu içe aktarın.')
        if not layer or not layer.isValid() or not hasattr(layer, "fields"):
            raise ValueError('Geçerli bir vektör katmanı seçin.')
        if plan_level != "UIP":
            raise ValueError("Bu alternatif katalog yalnızca UİP'i destekler.")
        if (
            not layer.crs().isValid()
            or layer.crs().mapUnits() != Qgis.DistanceUnit.Meters
        ):
            raise ValueError(
                'UİP sembolleri metre birimli izdüşümlü bir KRS gerektirir.'
            )
        project = QgsProject.instance()
        if (
            layer.id() in project.mapLayers()
            and project.crs().mapUnits() != Qgis.DistanceUnit.Meters
        ):
            raise ValueError(
                'UİP sembollerini uygulamadan önce proje koordinat sistemini metre birimli projeksiyonlu bir sisteme ayarlayın.'
            )
        index = layer.fields().lookupField(field_name)
        if index < 0:
            raise ValueError('Fonksiyon kodu alanı bulunamadı.')
        geometry = {
            Qgis.GeometryType.Point: "POINT",
            Qgis.GeometryType.Line: "LINE",
            Qgis.GeometryType.Polygon: "POLYGON",
        }.get(layer.geometryType())
        if geometry is None:
            raise ValueError("Desteklenmeyen geometri.")
        categories, unknown = [], []
        warnings = [
            "Yazı tipi ikame edildi: " + name
            for name in self.inventory.get("missing_fonts", [])
        ]
        matched = null_count = 0
        values = list(layer.uniqueValues(index))
        present_codes = {
            str(value) for value in values if not is_null_value(value)
        }
        # Include valid catalog codes even on an empty layer, so newly drawn
        # features immediately receive their mapped style without a second click.
        by_name = field_name.lower() in ("uipfonksiyon", "fonksiyon_adi")
        values.extend(
            dict.fromkeys(
                (symbol if by_name else code)
                for (level, kind, code), symbol in self._mappings.items()
                if level == plan_level and kind == geometry and (symbol if by_name else code) not in present_codes
            )
        )
        values.sort(key=lambda value: "" if is_null_value(value) else str(value))
        symbol_geom_map = {
            Qgis.SymbolType.Marker: Qgis.GeometryType.Point,
            Qgis.SymbolType.Line: Qgis.GeometryType.Line,
            Qgis.SymbolType.Fill: Qgis.GeometryType.Polygon,
        }
        for value in values:
            is_null = is_null_value(value)
            code = None if is_null else str(value)
            name = self._mappings.get((plan_level, geometry, code))
            if name is None and code and self._style.symbol(code) is not None:
                # uipfonksiyon stores the function name, which is the symbol name.
                name = code
            symbol = self._style.symbol(name) if name else None
            if symbol is not None and symbol_geom_map.get(symbol.type()) != layer.geometryType():
                warnings.append('Geometri uyumsuzluğu: ' + (code or ""))
                symbol = None
            if symbol is None:
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                symbol.setColor(QColor("#a7adb5"))
                if is_null:
                    null_count += 1
                else:
                    unknown.append(code)
            else:
                matched += 1
            label = "Kodu bulunmuyor" if is_null else (name or 'Eşleşmeyen: ' + code)
            categories.append(localized_category(value, symbol, label))
        # A final catch-all also makes newly entered codes visible.
        fallback = QgsSymbol.defaultSymbol(layer.geometryType())
        fallback.setColor(QColor("#a7adb5"))
        categories.append(localized_category("", fallback, "Diğer / eşleşmeyen"))
        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        if layer.id() not in self._previous:
            base_renderer = full_renderer(layer)
            self._previous[layer.id()] = (
                base_renderer if base_renderer is not None else (layer.renderer().clone() if layer.renderer() else None),
                layer.hasScaleBasedVisibility(),
                layer.minimumScale(),
                layer.maximumScale(),
            )
        layer.removeCustomProperty(FULL_PROPERTY)
        layer.removeCustomProperty(MODE_PROPERTY)
        layer.setRenderer(renderer)
        layer.setScaleBasedVisibility(False)
        layer.triggerRepaint()
        return StyleResult(matched, tuple(unknown), null_count, tuple(warnings))

    def restore(self, layer) -> bool:
        previous = self._previous.pop(layer.id(), None)
        if previous is None:
            return False
        renderer, enabled, minimum, maximum = previous
        layer.removeCustomProperty(FULL_PROPERTY)
        layer.removeCustomProperty(MODE_PROPERTY)
        if renderer is not None:
            layer.setRenderer(renderer)
        layer.setMinimumScale(minimum)
        layer.setMaximumScale(maximum)
        layer.setScaleBasedVisibility(enabled)
        layer.triggerRepaint()
        return True
