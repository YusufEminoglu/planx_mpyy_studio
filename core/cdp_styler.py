"""Native ÇDP renderer generated from official E-Plan ÇDP SLD rules and EK-1e Detay Kataloğu."""

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


CDP_DEFAULT_PALETTE = {
    # Orman ve Doğal Koruma Alanları
    "ORMAN": "#2e7d32",
    "ORMAN_ALANI": "#2e7d32",
    "AGACLANDIRILACAK_ALAN": "#43a047",
    "MERA": "#aed581",
    "MERA_ALANI": "#aed581",
    "DOGAL_KARAKTER": "#66bb6a",
    "DOGAL_KARAKTERI_KORUNACAK_ALAN": "#66bb6a",
    "MILLI_PARK": "#1b5e20",
    "TABIAT_PARKI": "#33691e",
    "OZEL_EKOSISTEM": "#558b2f",
    "SULAK_ALAN": "#26a69a",
    # Tarım Alanları
    "TARIM": "#c0ca33",
    "TARIM_ALANI": "#c0ca33",
    "DIKILI_TARIM": "#afb42b",
    "MUTLAK_TARIM": "#9e9d24",
    "ZEYTINLIK": "#827717",
    # Kentsel ve Kırsal Yerleşimler
    "KENTSEL_YERLESIK": "#8d6e63",
    "KENTSEL_YERLESIK_ALAN": "#8d6e63",
    "KENTSEL_MESKUN": "#8d6e63",
    "KENTSEL_GELISME_KONUT": "#ff9800",
    "KENTSEL_GELISME_ALANI": "#ff9800",
    "KENTSEL_GELISME": "#ff9800",
    "KIRSAL_YERLESIK_KONUT": "#bcaaa4",
    "KIRSAL_YERLESIK": "#bcaaa4",
    "KIRSAL_YERLESIK_ALAN": "#bcaaa4",
    "YERLESIM_ALANI": "#a1887f",
    "TERCIHLI_KULLANIM_BOLGESI": "#ffb300",
    "TERCIHLI_KULLANIM": "#ffb300",
    "TURIZM_ALANI": "#00acc1",
    "TURIZM_MERKEZI": "#0097a7",
    "TM_KTKGB_ALANLARI": "#00838f",
    # Çalışma, Sanayi ve Enerji
    "KENTSEL_CALISMA": "#ab47bc",
    "SANAYI_ALANI": "#8e24aa",
    "ORGANIZE_SANAYI_BOLGESI": "#6a1b9a",
    "KUCUK_SANAYI": "#ba68c8",
    "TEKNIK_ALTYAPI": "#7e57c2",
    "ENERJI_URETIM": "#ff7043",
    "YENILENEBILIR_ENERJI_KAYNAGINA_DAYALI_URETIM_TESIS_ALANI": "#26a69a",
    "ENERJI_DAGITIM_DEPOLAMA": "#e64a19",
    "KATI_ATIK_TESIS": "#795548",
    "ATIKSU_TESIS": "#5d4037",
    # Su ve Havza Koruma
    "SU_YUZEYI": "#0288d1",
    "SU_YUZEYI_CIZGI": "#0288d1",
    "SU_TOPLAMA_HAVZASI": "#0288d1",
    "ICME_KULLANMA_SU_KORUMA": "#03a9f4",
    "ICMESU_TESIS": "#039be5",
    "SU_KAPTAJ": "#0288d1",
    "DENIZ_ULASIM_BAGLANTI": "#01579b",
    "SU_ULASIM_BAGLANTISI": "#01579b",
    # Yeşil ve Sosyal Donatı
    "ACIK_YESIL_ALAN": "#4caf50",
    "SOSYAL_KULTUREL_ALAN": "#e91e63",
    "EGITIM_TESIS_ALANI": "#3f51b5",
    "SAGLIK_TESISI": "#00bcd4",
    "IDARI_MERKEZ": "#5c6bc0",
    # Koruma ve Kısıtlar
    "SIT_ALANLARI": "#d84315",
    "OCK_BOLGE": "#c2185b",
    "OCK_HASSAS_ALAN": "#ad1457",
    "OZEL_KANUNLARLA_BELIRLENEN_ALAN": "#f4511e",
    "ASKERI_YSK_GUVENLIK_BLG": "#78909c",
    "AFET_TEHLIKELI_ALANLAR": "#e53935",
    "AFET_HIZMET_ALANI": "#d32f2f",
    "STRATEJIK_ALT_BOLGE": "#ba68c8",
    "STRATEJIK_KARAR": "#ec407a",
    "MANIA_PLANI": "#90a4ae",
    "MANIA_SINIRI": "#b0bec5",
}

CDP_CODE_ALIASES = {
    "TARIM": ["TARIM_ALANI", "Tarım Alanı", "Tarım"],
    "ORMAN": ["ORMAN_ALANI", "Orman Alanı", "Orman"],
    "KENTSEL_GELISME_KONUT": [
        "KENTSEL_GELISME_ALANI",
        "KENTSEL_GELISME",
        "Kentsel Gelişme Alanı",
        "Kentsel Gelişme Konut Alanı",
    ],
    "KENTSEL_YERLESIK": ["KENTSEL_YERLESIK_ALAN", "KENTSEL_MESKUN", "Kentsel Yerleşik Alan"],
    "KIRSAL_YERLESIK_KONUT": ["KIRSAL_YERLESIK", "KIRSAL_YERLESIK_ALAN", "Kırsal Yerleşik Alan"],
    "SU_YUZEYI": ["SU_TOPLAMA_HAVZASI", "Su Yüzeyi", "Su Toplama Havzası", "Gölet / Baraj"],
    "ICME_KULLANMA_SU_KORUMA": ["SU_TOPLAMA_HAVZASI", "İçme ve Kullanma Suyu Koruma Havzası"],
    "MERA": ["MERA_ALANI", "Mera Alanı", "Mera"],
    "ACIK_YESIL_ALAN": ["Açık ve Yeşil Alan", "Bölgesel Yeşil Alan"],
    "TURIZM_ALANI": ["TURIZM_MERKEZI", "Turizm Alanı", "Turizm Tesis Alanı"],
    "KENTSEL_CALISMA": ["Sanayi ve Çalışma Alanı", "Kentsel Çalışma Alanı"],
}


class CDPStylerEngine:
    """Applies official Çevre Düzeni Planı (ÇDP) symbology."""

    def __init__(self):
        cat_path = Path(__file__).resolve().parents[1] / "styles" / "cdp_catalog.json"
        data = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else {}
        self.entries = data.get("entries", [])
        self._previous = {}

    def _symbol(self, entry: dict, geom_kind: str, code: str = ""):
        # Extract first rule fill and stroke, scanning all rules if initial is empty
        rules = entry.get("rules", [])
        fill_hex = ""
        stroke_hex = ""
        stroke_w = 0.3

        for r in rules:
            f = r.get("fill_color")
            if f and not fill_hex:
                fill_hex = f
            s = r.get("stroke_color")
            if s and not stroke_hex:
                stroke_hex = s
            w = r.get("stroke_width")
            if w:
                try:
                    stroke_w = float(w)
                except (ValueError, TypeError):
                    pass
            if fill_hex and stroke_hex:
                break

        # Fallback to authentic ÇDP palette if fill_color is empty or gray
        entry_code = entry.get("layer_code", "")
        lookup_key = code or entry_code
        if not fill_hex or fill_hex.upper() in ("#C0C0C0", "#B4B4B4", "#808080"):
            fill_hex = (
                CDP_DEFAULT_PALETTE.get(lookup_key)
                or CDP_DEFAULT_PALETTE.get(entry_code)
                or "#81c784"
            )

        if not stroke_hex:
            stroke_hex = "#37474f"

        if geom_kind == "polygon":
            symbol = QgsFillSymbol()
            symbol.deleteSymbolLayer(0)
            fill_layer = QgsSimpleFillSymbolLayer()
            fill_layer.setFillColor(_hex_or_rgb(fill_hex, 210))
            fill_layer.setStrokeColor(_hex_or_rgb(stroke_hex, 255))
            fill_layer.setStrokeWidth(stroke_w)
            fill_layer.setStrokeWidthUnit(QgsUnitTypes.RenderMillimeters)
            symbol.appendSymbolLayer(fill_layer)
            return symbol

        if geom_kind == "line":
            symbol = QgsLineSymbol()
            line_layer = QgsSimpleLineSymbolLayer()
            line_layer.setColor(_hex_or_rgb(stroke_hex or fill_hex or "#000000", 255))
            line_layer.setWidth(stroke_w or 0.5)
            line_layer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
            symbol.changeSymbolLayer(0, line_layer)
            return symbol

        # Point
        return QgsMarkerSymbol.createSimple({
            "name": "square",
            "color": _hex_or_rgb(fill_hex, 255).name(),
            "outline_color": _hex_or_rgb(stroke_hex or "#000000", 255).name(),
            "size": "3.5",
            "size_unit": "MM",
        })

    def apply(self, layer: QgsVectorLayer) -> int:
        """Apply ÇDP categorized symbology based on layer_code or bolge_turu."""
        if layer is None or not layer.isValid():
            raise ValueError('Geçerli bir ÇDP katmanı seçin')

        geom_map = {
            QgsWkbTypes.GeometryType.PolygonGeometry: "polygon",
            QgsWkbTypes.GeometryType.LineGeometry: "line",
            QgsWkbTypes.GeometryType.PointGeometry: "point",
        }
        geom_kind = geom_map.get(layer.geometryType())
        if not geom_kind:
            raise ValueError('ÇDP sembolojisi yalnızca alan, çizgi veya nokta katmanlarına uygulanabilir')

        field = "bolge_turu" if layer.fields().indexFromName("bolge_turu") >= 0 else (
            "koridor_turu" if layer.fields().indexFromName("koridor_turu") >= 0 else (
                "odak_adi" if layer.fields().indexFromName("odak_adi") >= 0 else (
                    "fonksiyon_adi" if layer.fields().indexFromName("fonksiyon_adi") >= 0 else "catalog_id"
                )
            )
        )


        self._previous[layer.id()] = layer.renderer().clone()
        categories = []
        seen = set()

        for entry in self.entries:
            code = entry.get("layer_code", "")
            if not code:
                continue
            title = code.replace("_", " ").title()
            symbol = self._symbol(entry, geom_kind, code=code)

            if code not in seen:
                categories.append(localized_category(code, symbol.clone(), title))
                seen.add(code)

            # Also bind human-readable title
            if title not in seen:
                categories.append(localized_category(title, symbol.clone(), title))
                seen.add(title)

            # Bind common aliases so features with variant names match instantly
            for alias in CDP_CODE_ALIASES.get(code, []):
                if alias not in seen:
                    alias_sym = self._symbol(entry, geom_kind, code=alias)
                    categories.append(localized_category(alias, alias_sym.clone(), alias))
                    seen.add(alias)

        # Catch-all for other / unspecified zones (soft olive rather than bleak gray)
        default_fallback_sym = self._symbol({}, geom_kind, code="DOGAL_KARAKTER")
        categories.append(localized_category(None, default_fallback_sym, 'Diğer ÇDP Alanı'))

        renderer = QgsCategorizedSymbolRenderer(field, categories)
        layer.setRenderer(renderer)
        layer.setCustomProperty("mpyy/cdp_catalog_source", 'E-Plan ÇDP SLD & EK-1e')
        layer.triggerRepaint()
        return len(categories) - 1

    def restore(self, layer: QgsVectorLayer) -> bool:
        renderer = self._previous.pop(layer.id(), None)
        if renderer is None:
            return False
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True

