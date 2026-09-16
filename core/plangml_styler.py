"""Resmî e-Plan derlemesini varsayılan QGIS gösterimine dönüştürür."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsRasterFillSymbolLayer,
    QgsRendererCategory,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsUnitTypes,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from .localization import localized_category

from .eplan_catalog import EPLAN_CATALOG


@dataclass(frozen=True)
class PlanGMLResult:
    catalog_rows: int
    official_styles: int
    fallback_styles: int
    ambiguous_codes: tuple[str, ...]


def _normalize(value):
    text = str(value or "").strip().upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    text = re.sub(r"^(PL|HAT|SNR|KA|KST)_", "", text)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


# MPYY Standard Group Palettes for all 23 Polygon Groups and 10 Line Groups
MPYY_GROUP_PALETTES = {
    # POLYGON GROUPS
    (101000, "POLYGON"): {"fill": "#81C784", "stroke": "#2E7D32", "stroke_width": 0.35},  # Açık ve Yeşil Alanlar
    (102000, "POLYGON"): {"fill": "#FF8A80", "stroke": "#C62828", "stroke_width": 0.4},   # Afet Tehlikeli Alanlar
    (103000, "POLYGON"): {"fill": "#A5D6A7", "stroke": "#388E3C", "stroke_width": 0.35},  # Bugünkü Arazi Kullanımı Korunacak
    (104000, "POLYGON"): {"fill": "#BCAAA4", "stroke": "#4E342E", "stroke_width": 0.4},   # Demiryolları
    (105000, "POLYGON"): {"fill": "#90CAF9", "stroke": "#1565C0", "stroke_width": 0.35},  # Eğitim Tesisleri
    (106000, "POLYGON"): {"fill": "#FFAB91", "stroke": "#D84315", "stroke_width": 0.35},  # Enerji Üretim Dağıtım
    (107000, "POLYGON"): {"fill": "#CFD8DC", "stroke": "#37474F", "stroke_width": 0.4},   # Havayolları
    (108000, "POLYGON"): {"fill": "#C5CAE9", "stroke": "#283593", "stroke_width": 0.35},  # İbadet Alanları
    (109000, "POLYGON"): {"fill": "#FFE0B2", "stroke": "#EF6C00", "stroke_width": 0.35},  # Karayolları
    (110000, "POLYGON"): {"fill": "#CE93D8", "stroke": "#6A1B9A", "stroke_width": 0.35},  # Kentsel Çalışma Alanları
    (111000, "POLYGON"): {"fill": "#B0BEC5", "stroke": "#37474F", "stroke_width": 0.35},  # Kentsel Toplu Taşıma
    (112000, "POLYGON"): {"fill": "#FFE082", "stroke": "#F57F17", "stroke_width": 0.35},  # Konut / Yerleşim
    (113000, "POLYGON"): {"fill": "#80CBC4", "stroke": "#004D40", "stroke_width": 0.35},  # Korunacak Alanlar
    (114000, "POLYGON"): {"fill": "#FFCC80", "stroke": "#E65100", "stroke_width": 0.35},  # Özel Kanunlarla Belirlenen Alanlar
    (115000, "POLYGON"): {"fill": "#80CBC4", "stroke": "#00695C", "stroke_width": 0.35},  # Sağlık Tesisleri
    (116000, "POLYGON"): {"fill": "#F48FB1", "stroke": "#AD1457", "stroke_width": 0.35},  # Sosyal ve Kültürel Tesisler
    (117000, "POLYGON"): {"fill": "#81D4FA", "stroke": "#0277BD", "stroke_width": 0.35},  # Su - Atıksu Sistemleri
    (118000, "POLYGON"): {"fill": "#80DEEA", "stroke": "#00838F", "stroke_width": 0.35},  # Turizm Alanları
    (119000, "POLYGON"): {"fill": "#FFCCBC", "stroke": "#BF360C", "stroke_width": 0.35},  # Yapı Sınırlaması Korumaları
    (120000, "POLYGON"): {"fill": "#80DEEA", "stroke": "#006064", "stroke_width": 0.35},  # Denizyolları
    (121000, "POLYGON"): {"fill": "#ECEFF1", "stroke": "#263238", "stroke_width": 0.5},   # İdari Sınırlar
    (122000, "POLYGON"): {"fill": "#ECEFF1", "stroke": "#263238", "stroke_width": 0.5},   # Planlama Sınırları
    (123000, "POLYGON"): {"fill": "#C8E6C9", "stroke": "#2E7D32", "stroke_width": 0.35},  # Sosyal Altyapı Alanları

    # LINE GROUPS
    (104000, "LINE"): {"line_color": "#4E342E", "line_width": 0.6, "dash": [6, 2, 2, 2]}, # Demiryolları
    (106000, "LINE"): {"line_color": "#D84315", "line_width": 0.5, "dash": [5, 2]},       # Enerji / Boru Hatları
    (111000, "LINE"): {"line_color": "#00838F", "line_width": 0.6, "dash": [4, 2]},       # Toplu Taşıma / Havaray
    (114000, "LINE"): {"line_color": "#E65100", "line_width": 0.5, "dash": [6, 3]},       # Özel Kanun Sınırları / Sahil
    (117000, "LINE"): {"line_color": "#0277BD", "line_width": 0.5, "dash": [4, 2]},       # Su - Atıksu Hatları
    (119000, "LINE"): {"line_color": "#C62828", "line_width": 0.5, "dash": [3, 2]},       # Yapı Sınırlaması / Mania
    (120000, "LINE"): {"line_color": "#006064", "line_width": 0.6},                        # Denizyolu
    (130000, "LINE"): {"line_color": "#000000", "line_width": 0.5},                        # Ada Kenarı
    (132000, "LINE"): {"line_color": "#D32F2F", "line_width": 0.6, "dash": [4, 2]},       # Cephe Çizgileri
    (133000, "LINE"): {"line_color": "#37474F", "line_width": 0.5},                        # Karayolları
}

# Function-specific overrides for distinct legislative appearance
MPYY_FUNCTION_PALETTES = {
    # Yeşil & Spor
    "ARBORETUM_BOTANIK_PARKI": {"fill": "#43A047", "stroke": "#1B5E20"},
    "FUAR_PANAYIR_VE_FESTIVAL_ALANI": {"fill": "#66BB6A", "stroke": "#1B5E20"},
    "HAYVANAT_BAHCESI": {"fill": "#4CAF50", "stroke": "#2E7D32"},
    "HIPODROM": {"fill": "#81C784", "stroke": "#2E7D32"},
    "COCUK_BAHCESI_VE_OYUN_ALANI": {"fill": "#A5D6A7", "stroke": "#2E7D32"},
    "BOTANIK_BAHCESI": {"fill": "#43A047", "stroke": "#1B5E20"},
    # Afet
    "ONLEMLI_ALAN": {"fill": "#FFE082", "stroke": "#FF8F00", "stroke_width": 0.45},
    "YAPI_YASAKLI_ALAN": {"fill": "#FF8A80", "stroke": "#D50000", "stroke_width": 0.5},
    # Eğitim & Sağlık
    "ANAOKULU_ALANI": {"fill": "#90CAF9", "stroke": "#1565C0"},
    "OZEL_ANAOKULU_ALANI": {"fill": "#BBDEFB", "stroke": "#0D47A1"},
    "AILE_SAGLIGI_MERKEZI": {"fill": "#80CBC4", "stroke": "#00695C"},
    # Ulaşım
    "TERMINAL_OTOGAR": {"fill": "#FFCC80", "stroke": "#E65100"},
    "TIR_KAMYON_MAKINE_PARKI_VE_GARAJ_ALANI": {"fill": "#FFE0B2", "stroke": "#EF6C00"},
    "ELEKTRIKLI_ARAC_SARJ_ISTASYONU": {"fill": "#B2DFDB", "stroke": "#00695C"},
    "HAVAALANI_HAVALIMANI": {"fill": "#CFD8DC", "stroke": "#37474F"},
    "HELIKOPTER_INIS_ALANI": {"fill": "#ECEFF1", "stroke": "#455A64"},
    "BALIKCI_BARINAGI": {"fill": "#80DEEA", "stroke": "#006064"},
    "ISKELE": {"fill": "#4DD0E1", "stroke": "#00838F"},
    "TERSANE_ALANI": {"fill": "#B0BEC5", "stroke": "#37474F"},
    "YAT_LIMANI": {"fill": "#26C6DA", "stroke": "#006064"},
    "LIMAN": {"fill": "#00ACC1", "stroke": "#006064"},
    # Turizm
    "GOLF_ALANI": {"fill": "#C8E6C9", "stroke": "#2E7D32"},
    "GOLF_TURIZMI": {"fill": "#C8E6C9", "stroke": "#2E7D32"},
    "EKOTURIZM_KIRSAL_TURIZM": {"fill": "#DCEDC8", "stroke": "#558B2F"},
    "HOSTEL_ALANI": {"fill": "#80DEEA", "stroke": "#00838F"},
    "MOTEL_ALANI": {"fill": "#80DEEA", "stroke": "#00838F"},
    "KIS_SPORLARI_VE_KAYAK_TESISI_ALANI": {"fill": "#B3E5FC", "stroke": "#0277BD"},
    # Sosyal Tesisler
    "KONGRE_VE_SERGI_MERKEZI_ALANI": {"fill": "#F48FB1", "stroke": "#AD1457"},
    "KULTUREL_TESIS_ALANI": {"fill": "#F06292", "stroke": "#C2185B"},
    "OZEL_KULTUREL_TESIS_ALANI": {"fill": "#F8BBD0", "stroke": "#880E4F"},
    "SEFKAT_EVLERI_ALANI": {"fill": "#CE93D8", "stroke": "#7B1FA2"},
    "YASLI_BAKIMEVI_ALANI": {"fill": "#D1C4E9", "stroke": "#512DA8"},
    "SOKAK_HAYVANLARI_BARINAGI_ALANI": {"fill": "#C8E6C9", "stroke": "#2E7D32"},
    # İbadet
    "KILISE": {"fill": "#C5CAE9", "stroke": "#283593"},
    "SAPEL": {"fill": "#D1C4E9", "stroke": "#311B92"},
    "SINAGOG_HAVRA": {"fill": "#9FA8DA", "stroke": "#1A237E"},
    # Lines
    "HAT_HIZLI_TREN": {"line_color": "#B71C1C", "line_width": 0.8, "dash": [8, 2, 2, 2]},
    "HIZLI_TREN_HATTI": {"line_color": "#B71C1C", "line_width": 0.8, "dash": [8, 2, 2, 2]},
    "HAT_TRIYAJ": {"line_color": "#4E342E", "line_width": 0.6, "dash": [4, 2]},
    "HAT_BORU_HATTI": {"line_color": "#E65100", "line_width": 0.5, "dash": [6, 2]},
    "BORU_HATTI": {"line_color": "#E65100", "line_width": 0.5, "dash": [6, 2]},
    "HAT_CEBRI_BORU": {"line_color": "#BF360C", "line_width": 0.6, "dash": [5, 2]},
    "CEBRI_BORU_HATTI": {"line_color": "#BF360C", "line_width": 0.6, "dash": [5, 2]},
    "HAT_DOGALGAZ": {"line_color": "#F57C00", "line_width": 0.5, "dash": [6, 2, 2, 2]},
    "DOGALGAZ_BORU_HATTI": {"line_color": "#F57C00", "line_width": 0.5, "dash": [6, 2, 2, 2]},
    "HAT_HAVAI": {"line_color": "#00838F", "line_width": 0.6, "dash": [6, 3]},
    "HAVAI_HAT": {"line_color": "#00838F", "line_width": 0.6, "dash": [6, 3]},
    "HAT_HAVARAY": {"line_color": "#0097A7", "line_width": 0.7, "dash": [5, 2]},
    "HAVARAY": {"line_color": "#0097A7", "line_width": 0.7, "dash": [5, 2]},
    "HAT_RAYLI_TOPLU_TAS": {"line_color": "#D32F2F", "line_width": 0.7, "dash": [6, 2]},
    "RAYLI_TOPLU_TASIMA_HATTI": {"line_color": "#D32F2F", "line_width": 0.7, "dash": [6, 2]},
    "SNR_SAHIL_SERIDI": {"line_color": "#00838F", "line_width": 0.6, "dash": [6, 3]},
    "SAHIL_SERIDI": {"line_color": "#00838F", "line_width": 0.6, "dash": [6, 3]},
    "HAT_ANA_ICME_SUYU": {"line_color": "#0288D1", "line_width": 0.6, "dash": [6, 2]},
    "ICME_SUYU_ANA_HATTI": {"line_color": "#0288D1", "line_width": 0.6, "dash": [6, 2]},
    "HAT_ATIKSU_KOLLEKTOR": {"line_color": "#5D4037", "line_width": 0.6, "dash": [6, 2]},
    "ATIK_SU_ANA_KOLLEKTORU": {"line_color": "#5D4037", "line_width": 0.6, "dash": [6, 2]},
    "HAT_SOGUTMA_SUYU": {"line_color": "#0097A7", "line_width": 0.5, "dash": [4, 2]},
    "SOGUTMA_SUYU_ALMA_HATTI": {"line_color": "#0097A7", "line_width": 0.5, "dash": [4, 2]},
    "SNR_MANIA_PLAN": {"line_color": "#E53935", "line_width": 0.6, "dash": [6, 2, 2, 2]},
    "MANIA_PLANI": {"line_color": "#E53935", "line_width": 0.6, "dash": [6, 2, 2, 2]},
    "KST_HAVA_KORIDORU": {"line_color": "#D32F2F", "line_width": 0.6, "dash": [6, 3]},
    "HAVAALANI_HAVA_KORIDORU": {"line_color": "#D32F2F", "line_width": 0.6, "dash": [6, 3]},
    "HAT_OTOYOL": {"line_color": "#D84315", "line_width": 0.8},
    "ERISME_KONTROLLU_KARAYOLU_OTOYOL": {"line_color": "#D84315", "line_width": 0.8},
    "BOLUNMUS_TASIT_YOLU": {"line_color": "#37474F", "line_width": 0.7, "dash": [6, 2]},
    "TASIT_YOLU": {"line_color": "#455A64", "line_width": 0.5},
    "KORUNAN_CEPHE_CIZGISI": {"line_color": "#1976D2", "line_width": 0.6, "dash": [4, 2]},
    "DUZELTILEN_CEPHE_CIZGISI": {"line_color": "#FB8C00", "line_width": 0.6, "dash": [4, 2]},
    "ONERILEN_CEPHE_CIZGISI": {"line_color": "#E53935", "line_width": 0.6, "dash": [4, 2]},
}


class PlanGMLStylerEngine:
    def __init__(self):
        root = Path(__file__).resolve().parents[1]
        self._catalog = json.loads(
            (root / "styles" / "plangml_catalog.json").read_text(encoding="utf-8")
        )["rows"]
        self._tarama = root / "resources"
        self._previous = {}

    def _entry(self, row, plan_type):
        raw_tabaka = str(row.get("tabaka_adi") or "").strip().upper()
        candidates = (
            _normalize(row["tabaka_adi"]),
            _normalize(row["fonksiyon_adi"]),
            raw_tabaka,
        )

        # 1. Official EPLAN_CATALOG for primary plan_type
        entries = EPLAN_CATALOG.get(plan_type, {})
        for candidate in candidates:
            if candidate in entries:
                return entries[candidate]
        for candidate in candidates:
            tokens = candidate.split("_")
            matches = [
                (len(key), entry)
                for key, entry in entries.items()
                if all(part in tokens for part in key.split("_"))
            ]
            if matches:
                return max(matches, key=lambda item: item[0])[1]

        # 2. Cross-level fallback across other plan levels in EPLAN_CATALOG
        for other_plan in ("NIP", "CDP", "UIP"):
            if other_plan == plan_type:
                continue
            other_entries = EPLAN_CATALOG.get(other_plan, {})
            for candidate in candidates:
                if candidate in other_entries:
                    return other_entries[candidate]
                tokens = candidate.split("_")
                matches = [
                    (len(key), entry)
                    for key, entry in other_entries.items()
                    if all(part in tokens for part in key.split("_"))
                ]
                if matches:
                    return max(matches, key=lambda item: item[0])[1]

        # 3. Dedicated MPYY Function Palettes
        for candidate in candidates:
            if candidate in MPYY_FUNCTION_PALETTES:
                return MPYY_FUNCTION_PALETTES[candidate]

        # 4. Standard MPYY Group Palettes
        grp_code = int(row.get("ust_grup_kodu", 0))
        geom = row.get("geometry_type")
        if (grp_code, geom) in MPYY_GROUP_PALETTES:
            return MPYY_GROUP_PALETTES[(grp_code, geom)]

        return None

    def _symbol(self, geometry, entry):
        if geometry == "POLYGON":
            symbol = QgsFillSymbol()
            while symbol.symbolLayerCount():
                symbol.takeSymbolLayer(0)
            tarama = self._tarama / entry.get("tarama", "") if entry else None
            if tarama and tarama.is_file():
                raster = QgsRasterFillSymbolLayer(str(tarama))
                size = entry.get("tarama_size")
                if size:
                    raster.setWidth(float(size[0]))
                    raster.setWidthUnit(QgsUnitTypes.RenderUnit.RenderPixels)
                symbol.appendSymbolLayer(raster)
            base = QgsSimpleFillSymbolLayer()
            base.setFillColor(QColor((entry or {}).get("fill", "#D5D9DC")))
            base.setStrokeColor(QColor((entry or {}).get("stroke", "#555555")))
            base.setStrokeWidth(float((entry or {}).get("stroke_width", 0.35) or 0.35))
            if tarama and tarama.is_file():
                base.setBrushStyle(Qt.BrushStyle.NoBrush)
            symbol.appendSymbolLayer(base)
            return symbol
        symbol = QgsLineSymbol()
        layer = QgsSimpleLineSymbolLayer()
        layer.setColor(
            QColor(
                (entry or {}).get("line_color", (entry or {}).get("stroke", "#555555"))
            )
        )
        layer.setWidth(float((entry or {}).get("line_width", 0.4) or 0.4))
        dash = (entry or {}).get("dash")
        if dash:
            layer.setCustomDashVector([float(x) for x in dash])
            layer.setUseCustomDashPattern(True)
        symbol.changeSymbolLayer(0, layer)
        return symbol

    @staticmethod
    def _value(row, field):
        if field == "catalog_id":
            return row["geometry_type"] + ":" + str(row["source_fid"])
        if field in ("fonksiyon_kodu", "detay_kodu"):
            return str(row["fonksiyon_kodu"])
        return row["fonksiyon_adi"]

    def apply(self, layer, field="catalog_id", plan_type="UIP"):
        if layer is None or not layer.isValid():
            raise ValueError('Geçerli bir hedef katman seçin.')
        if layer.fields().indexFromName(field) < 0:
            raise ValueError('Fonksiyon alanı hedef katmanda bulunamadı.')
        geometry = {
            QgsWkbTypes.GeometryType.PolygonGeometry: "POLYGON",
            QgsWkbTypes.GeometryType.LineGeometry: "LINE",
        }.get(layer.geometryType())
        if geometry is None:
            raise ValueError(
                'PlanGML stili yalnızca alan ve çizgi katmanlarına uygulanabilir.'
            )
        plan_type = plan_type if plan_type in EPLAN_CATALOG else "UIP"
        rows = [row for row in self._catalog if row["geometry_type"] == geometry]
        categories, official = [], 0
        code_counts = {}
        seen = set()
        for row in rows:
            # The category value must be what the layer's field actually stores.
            # MpyyUipDb forms write the function *name* into uipfonksiyon; coded
            # layers carry fonksiyon_kodu; catalog_id is geometry + source FID
            # (function codes are not unique, so it keeps every entry addressable).
            code = self._value(row, field)
            if code in seen:
                continue
            seen.add(code)
            code_counts[str(row["fonksiyon_kodu"])] = code_counts.get(str(row["fonksiyon_kodu"]), 0) + 1
            entry = self._entry(row, plan_type)
            official += int(entry is not None)
            label = row["fonksiyon_adi"] + (
                " · " + row["tabaka_adi"]
                if row["tabaka_adi"] not in (None, "YOK")
                else ""
            )
            categories.append(
                localized_category(code, self._symbol(geometry, entry), label)
            )
        categories.append(
            localized_category(None, self._symbol(geometry, None), 'Eşleşmeyen / boş')
        )
        self._previous[layer.id()] = layer.renderer().clone()
        layer.setRenderer(QgsCategorizedSymbolRenderer(field, categories))
        layer.triggerRepaint()
        ambiguous = tuple(
            sorted(code for code, count in code_counts.items() if count > 1)
        )
        return PlanGMLResult(len(categories) - 1, official, len(categories) - 1 - official, ambiguous)

    def restore(self, layer):
        renderer = self._previous.pop(layer.id(), None)
        if renderer is None:
            return False
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        return True
