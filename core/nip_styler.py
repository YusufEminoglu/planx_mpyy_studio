"""Native NİP renderer generated from official E-Plan NİP & MNIP SLD rules and EK-1e Detay Kataloğu."""

import json
from pathlib import Path
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRendererCategory,
    QgsRuleBasedRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from .localization import localized_category

from .fonts import create_font_marker_symbol


def _hex_or_rgb(val: str, alpha: int = 255) -> QColor:
    if not val:
        return QColor(180, 180, 180, alpha)
    val = val.strip()
    if val.startswith("#"):
        c = QColor(val)
        c.setAlpha(alpha)
        return c
    if "/" in val:
        parts = val.split("/")
        return QColor(int(parts[0]), int(parts[1]), int(parts[2]), alpha)
    return QColor(val)


NIP_DEFAULT_PALETTE = {
    # Konut Alanları ve Yoğunluk Zonları
    "MEVCUT_KONUT": "#FDD835",
    "KONUT": "#FDD835",
    "KONUT_ALANLARI": "#FDD835",
    "GELISME_KONUT": "#FFA726",
    "KENTSEL_GELISME": "#FFA726",
    "DONUSUM_KONUT_ALANLARI": "#FF7043",
    "KIRSAL_YERLESIK_ALAN_SINIR": "#BCAAA4",
    # Açık ve Yeşil Alanlar
    "ACIK_YESIL_ALAN": "#4CAF50",
    "PARK": "#4CAF50",
    "PARK_VE_YESIL_ALAN": "#4CAF50",
    "PASIF_YESIL_ALAN": "#81C784",
    "REKREASYON_ALANI": "#388E3C",
    "AGACLANDIRILACAK_ALAN": "#2E7D32",
    "ORMAN": "#1B5E20",
    "MERA": "#AED581",
    "TARIM": "#CDDC39",
    # Eğitim Tesisleri
    "EGITIM_TESIS_ALANI": "#2196F3",
    "EGITIM": "#2196F3",
    "EGITIM_ALANI": "#2196F3",
    "OZEL_EGITIM_ALANI": "#1976D2",
    "YUKSEK_OGRETIM_ALANI": "#1565C0",
    # Sağlık Tesisleri
    "SAGLIK_TESIS_ALANI": "#00ACC1",
    "SAGLIK": "#00ACC1",
    "SAGLIK_TESISI": "#00ACC1",
    "OZEL_SAGLIK_TESISI_ALANI": "#00838F",
    # Sosyal, Kültürel ve İbadet
    "SOSYAL_KULTUREL_ALAN": "#E91E63",
    "SOSYAL_TESIS": "#E91E63",
    "KULTUREL_TESIS": "#D81B60",
    "IBADET_ALANI": "#7E57C2",
    "CAMI": "#7E57C2",
    # Ticaret, Çalışma ve Sanayi
    "TICARET": "#E53935",
    "TICARET_ALANI": "#E53935",
    "MIA": "#C62828",
    "KENTSEL_CALISMA": "#AB47BC",
    "SANAYI": "#8E24AA",
    "ORGANIZE_SANAYI_BOLGESI": "#6A1B9A",
    "KUCUK_SANAYI": "#BA68C8",
    "DEPOLAMA_ALANI": "#512DA8",
    "TEKNIK_ALTYAPI": "#546E7A",
    "BELEDIYE_HIZMET_ALANI": "#607D8B",
    # Ulaşım ve Altyapı
    "TERMINAL": "#F57F17",
    "OTOGAR": "#F57F17",
    "TOPLU_TASIMA_AKTAR_ALAN": "#FB8C00",
    "HAVAALANI_HAVALIMANI": "#78909C",
    "DEMIRYOLU": "#455A64",
    # Su Alanları
    "SU_YUZEYI": "#0288D1",
    "SU_KAPTAJ": "#0288D1",
    "ICME_KULLANMA_SU_KORUMA": "#03A9F4",
    "SULAK_ALAN": "#26A69A",
    # Koruma ve Güvenlik
    "SIT_ALANLARI": "#D84315",
    "DOGAL_KARAKTER": "#66BB6A",
    "ASKERI_YASAK_BOLGE": "#78909C",
    "AFET_TEHLIKELI_ALANLAR": "#E53935",
    "AFET_HIZMET_ALANI": "#C62828",
    "TURIZM_ALANI": "#0097A7",
    # Çizgiler, Hatlar ve Sınırlar (Lines & Boundaries)
    "ADA_KENARI": "#000000",
    "AFET_KONUT_ALAN_SINIR": "#E65100",
    "KIYI": "#0288D1",
    "MANIA_PLANI": "#E53935",
    "MANIA_SINIRI": "#E53935",
    "SU_YUZEYI_CIZGI": "#0288D1",
    "YAPI_YAKLASMA_SINIRI": "#D32F2F",
    "YAYA_YOLU": "#8D6E63",
    "YOL_NESNESI": "#37474F",
    "DENIZ_ULASIM_BAGLANTISI": "#01579B",
    "SU_ULASIM_BAGLANTISI": "#01579B",
    "OZEL_KANUNLARLA_BELIRLENEN_ALAN": "#F4511E",
}

NIP_CODE_ALIASES = {
    "ACIK_YESIL_ALAN": ["PARK", "PARK_VE_YESIL_ALAN", "Park ve Yeşil Alan", "Açık ve Yeşil Alan"],
    "MEVCUT_KONUT": ["KONUT", "KONUT_ALANLARI", "Meskun Konut", "Mevcut Konut Alanı", "Konut Alanı"],
    "GELISME_KONUT": ["KENTSEL_GELISME", "Gelişme Konut Alanı", "Kentsel Gelişme Alanı"],
    "EGITIM_TESIS_ALANI": ["EGITIM", "EGITIM_ALANI", "Eğitim Tesis Alanı", "Eğitim Alanı", "İlkokul Alanı"],
    "SAGLIK_TESIS_ALANI": ["SAGLIK", "SAGLIK_TESISI", "Sağlık Tesis Alanı", "Sağlık Alanı", "Sağlık Tesisi"],
    "IBADET_ALANI": ["İbadet Alanı", "Cami"],
    "SOSYAL_KULTUREL_ALAN": ["Sosyal Tesis Alanı", "Kültürel Tesis Alanı"],
    "KENTSEL_CALISMA": ["SANAYI", "Sanayi Alanı", "Kentsel Çalışma Alanı"],
    "ORMAN": ["ORMAN_ALANI", "Orman Alanı"],
    "TARIM": ["TARIM_ALANI", "Tarım Alanı"],
    "SU_YUZEYI": ["Su Yüzeyi", "Göl / Baraj"],
}


class NIPStylerEngine:
    """Applies official Nazım İmar Planı (NİP) symbology and MNIP point notations."""

    def __init__(self):
        cat_path = Path(__file__).resolve().parents[1] / "styles" / "nip_catalog.json"
        data = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else {}
        self.entries = data.get("entries", [])
        self._previous = {}

    def _area_symbol(self, entry: dict, code: str = "") -> QgsFillSymbol:
        rules = entry.get("rules", [])
        entry_code = entry.get("layer_code", "")
        lookup_key = code or entry_code

        fill_hex = ""
        stroke_hex = ""
        stroke_w = 0.3

        for r in rules:
            f = r.get("fill_color")
            # In E-Plan SLDs, "#000000" on area rules was for text/markers, not polygon background
            if f and f.upper() not in ("#000000", "#000"):
                fill_hex = f
            s = r.get("stroke_color")
            if s and s.upper() not in ("#000000", "#000"):
                stroke_hex = s
            w = r.get("stroke_width")
            if w:
                try:
                    stroke_w = float(w)
                except (ValueError, TypeError):
                    pass
            if fill_hex:
                break

        # Fallback to authentic MPYY 1/5.000 Nazım İmar Planı palette
        if not fill_hex or fill_hex.upper() in ("#000000", "#000", "#C0C0C0", "#B4B4B4", "#E6C280"):
            fill_hex = (
                NIP_DEFAULT_PALETTE.get(lookup_key)
                or NIP_DEFAULT_PALETTE.get(entry_code)
                or "#ffee58"
            )

        if not stroke_hex or stroke_hex.upper() in ("#000000", "#000"):
            stroke_hex = "#37474f"

        symbol = QgsFillSymbol()
        symbol.deleteSymbolLayer(0)
        fill_layer = QgsSimpleFillSymbolLayer()
        fill_layer.setFillColor(_hex_or_rgb(fill_hex, 210))
        fill_layer.setStrokeColor(_hex_or_rgb(stroke_hex, 255))
        fill_layer.setStrokeWidth(stroke_w)
        fill_layer.setStrokeWidthUnit(QgsUnitTypes.RenderMillimeters)
        symbol.appendSymbolLayer(fill_layer)
        return symbol

    def _line_symbol(self, entry: dict) -> QgsLineSymbol:
        rules = entry.get("rules", [])
        rule = rules[0] if rules else {}
        stroke_hex = rule.get("stroke_color") or rule.get("fill_color") or "#C00000"
        stroke_w = float(rule.get("stroke_width") or 0.6)

        symbol = QgsLineSymbol()
        line_layer = QgsSimpleLineSymbolLayer()
        line_layer.setColor(_hex_or_rgb(stroke_hex, 255))
        line_layer.setWidth(stroke_w)
        line_layer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
        symbol.changeSymbolLayer(0, line_layer)
        return symbol

    def _notation_symbol(self, entry: dict) -> QgsMarkerSymbol:
        # Find a rule with well_known_name (ttf font glyph)
        for r in entry.get("rules", []):
            wkn = r.get("well_known_name", "")
            if wkn.startswith("ttf://"):
                # Format: ttf://font_name#0xhex
                parts = wkn[6:].split("#")
                font_name = parts[0]
                glyph_code = parts[1] if len(parts) > 1 else "0x0041"
                fill_c = _hex_or_rgb(r.get("fill_color") or "#000000", 255)
                return create_font_marker_symbol(font_name, glyph_code, size=14.0, color=fill_c)

        # Fallback circle marker if no TTF glyph specified
        return QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": "#D2691E",
            "outline_color": "#000000",
            "size": "4.0",
        })

    def apply(self, layer: QgsVectorLayer) -> int:
        """Apply NİP categorized styling or MNIP font notation styling."""
        if layer is None or not layer.isValid():
            raise ValueError('Geçerli bir NİP katmanı seçin')

        geom_type = layer.geometryType()
        self._previous[layer.id()] = layer.renderer().clone()

        if geom_type == QgsWkbTypes.GeometryType.PointGeometry:
            # Notation styling using MNIP rules
            notation_entries = [e for e in self.entries if e.get("is_notation")]
            field = "merkez_turu" if layer.fields().indexFromName("merkez_turu") >= 0 else ("fonksiyon_adi" if layer.fields().indexFromName("fonksiyon_adi") >= 0 else "catalog_id")

            categories = []
            seen_values = set()
            for entry in notation_entries:
                code = entry.get("layer_code", "")
                title = code.replace("_", " ")
                symbol = self._notation_symbol(entry)
                if code and code not in seen_values:
                    categories.append(localized_category(code, symbol.clone(), title))
                    seen_values.add(code)
                if title and title not in seen_values:
                    categories.append(localized_category(title, symbol.clone(), title))
                    seen_values.add(title)

                # Add specific subrules with their own TTF glyphs
                for r in entry.get("rules", []):
                    r_title = r.get("title", "")
                    wkn = r.get("well_known_name", "")
                    if r_title and wkn.startswith("ttf://"):
                        parts = wkn[6:].split("#")
                        font_name = parts[0]
                        glyph_code = parts[1] if len(parts) > 1 else "0x0041"
                        fill_c = _hex_or_rgb(r.get("fill_color") or "#000000", 255)
                        r_sym = create_font_marker_symbol(font_name, glyph_code, size=14.0, color=fill_c)
                        if r_title not in seen_values:
                            categories.append(localized_category(r_title, r_sym.clone(), r_title.replace("_", " ")))
                            seen_values.add(r_title)
                        r_clean = r_title.replace("_", " ")
                        if r_clean not in seen_values:
                            categories.append(localized_category(r_clean, r_sym.clone(), r_clean))
                            seen_values.add(r_clean)

            categories.append(localized_category(None, self._notation_symbol({}), 'Diğer NİP Notasyonu'))
            renderer = QgsCategorizedSymbolRenderer(field, categories)
            layer.setRenderer(renderer)
            layer.setCustomProperty("mpyy/nip_catalog_source", 'E-Plan MNIP Font Notasyonları')
            layer.triggerRepaint()
            return len(categories) - 1

        if geom_type == QgsWkbTypes.GeometryType.LineGeometry:
            line_entries = [e for e in self.entries if not e.get("is_notation") and any("Line" in r.get("rule_name", "") or "YOL" in e.get("layer_code", "") or "HAT" in e.get("layer_code", "") for r in e.get("rules", []))]
            if not line_entries:
                line_entries = [e for e in self.entries if not e.get("is_notation")]

            field = "yol_kademesi" if layer.fields().indexFromName("yol_kademesi") >= 0 else ("fonksiyon_adi" if layer.fields().indexFromName("fonksiyon_adi") >= 0 else "catalog_id")
            categories = []
            seen_values = set()
            for entry in line_entries:
                code = entry.get("layer_code", "")
                title = code.replace("_", " ")
                sym = self._line_symbol(entry)
                if code and code not in seen_values:
                    categories.append(localized_category(code, sym.clone(), title))
                    seen_values.add(code)
                if title and title not in seen_values:
                    categories.append(localized_category(title, sym.clone(), title))
                    seen_values.add(title)

            # Road hierarchy standards (1/5.000 Nazım İmar Planı Karayolu ve Ulaşım Ağı)
            road_hierarchy = [
                ("BIRINCI_DERECE_YOL", "1. Derece Yol (Ana Arter)", "#D84315", 0.9),
                ("IKINCI_DERECE_YOL", "2. Derece Yol (Tali Arter)", "#F57C00", 0.65),
                ("UCUNCU_DERECE_YOL", "3. Derece Yol (Toplayıcı Yol)", "#37474F", 0.45),
                ("YOLORTA", "Yol Ekseni", "#D32F2F", 0.7),
                ("YOL_NESNESI", "Taşıt Yolu", "#37474F", 0.5),
                ("YAYA_YOLU", "Yaya Yolu", "#8D6E63", 0.5),
                ("DEMIRYOLU", "Demiryolu", "#455A64", 0.6),
            ]
            for r_code, r_title, r_color, r_width in road_hierarchy:
                if r_code not in seen_values:
                    r_sym = QgsLineSymbol()
                    r_layer = QgsSimpleLineSymbolLayer()
                    r_layer.setColor(QColor(r_color))
                    r_layer.setWidth(r_width)
                    r_layer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
                    r_sym.changeSymbolLayer(0, r_layer)
                    categories.append(localized_category(r_code, r_sym.clone(), r_title))
                    seen_values.add(r_code)
                    r_clean = r_code.replace("_", " ")
                    if r_clean not in seen_values:
                        categories.append(localized_category(r_clean, r_sym.clone(), r_title))
                        seen_values.add(r_clean)

            categories.append(localized_category(None, self._line_symbol({}), 'Diğer Hat/Yol'))
            renderer = QgsCategorizedSymbolRenderer(field, categories)
            layer.setRenderer(renderer)
            layer.setCustomProperty("mpyy/nip_catalog_source", 'E-Plan NİP Hat Kuralları')
            layer.triggerRepaint()
            return len(categories) - 1

        # Polygon styling (NİP Alanları)
        area_entries = [e for e in self.entries if not e.get("is_notation")]
        field = "fonksiyon_adi" if layer.fields().indexFromName("fonksiyon_adi") >= 0 else "catalog_id"
        categories = []
        seen_values = set()
        for entry in area_entries:
            code = entry.get("layer_code", "")
            title = code.replace("_", " ")
            symbol = self._area_symbol(entry, code=code)
            if code and code not in seen_values:
                categories.append(localized_category(code, symbol.clone(), title))
                seen_values.add(code)
            if title and title not in seen_values:
                categories.append(localized_category(title, symbol.clone(), title))
                seen_values.add(title)

            # Bind common aliases so features with variant names match instantly
            for alias in NIP_CODE_ALIASES.get(code, []):
                if alias not in seen_values:
                    alias_sym = self._area_symbol(entry, code=alias)
                    categories.append(localized_category(alias, alias_sym.clone(), alias.replace("_", " ")))
                    seen_values.add(alias)
                    alias_clean = alias.replace("_", " ")
                    if alias_clean not in seen_values:
                        categories.append(localized_category(alias_clean, alias_sym.clone(), alias_clean))
                        seen_values.add(alias_clean)

            # Add subrules with distinct fills
            for r in entry.get("rules", []):
                r_title = r.get("title", "")
                if r_title and r.get("fill_color") and r.get("fill_color").upper() not in ("#000000", "#000"):
                    sub_sym = self._area_symbol(dict(entry, rules=[r]), code=r_title)
                    if r_title not in seen_values:
                        categories.append(localized_category(r_title, sub_sym.clone(), r_title.replace("_", " ")))
                        seen_values.add(r_title)
                    r_clean = r_title.replace("_", " ")
                    if r_clean not in seen_values:
                        categories.append(localized_category(r_clean, sub_sym.clone(), r_clean))
                        seen_values.add(r_clean)

        # Include all explicit palette definitions (e.g. TICARET, MIA, SANAYI, etc.)
        for pal_code in NIP_DEFAULT_PALETTE:
            if pal_code not in seen_values:
                pal_sym = self._area_symbol({}, code=pal_code)
                pal_title = pal_code.replace("_", " ")
                categories.append(localized_category(pal_code, pal_sym.clone(), pal_title))
                seen_values.add(pal_code)
                pal_clean = pal_code.replace("_", " ")
                if pal_clean not in seen_values:
                    categories.append(localized_category(pal_clean, pal_sym.clone(), pal_title))
                    seen_values.add(pal_clean)

        categories.append(localized_category(None, self._area_symbol({}, code="MEVCUT_KONUT"), 'Diğer NİP Alanı'))
        renderer = QgsCategorizedSymbolRenderer(field, categories)
        layer.setRenderer(renderer)
        layer.setCustomProperty("mpyy/nip_catalog_source", 'E-Plan NİP Alan Kuralları')
        layer.triggerRepaint()
        return len(categories) - 1

    def restore(self, layer: QgsVectorLayer) -> bool:
        renderer = self._previous.pop(layer.id(), None)
        if renderer is None:
            return False
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True
