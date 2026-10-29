"""Shared attribute, QGIS NULL, Turkish normalization, and geometry sink helpers.

Provides consistent handling across all five MPYY Studio workspace schemas
(Yerel UİP, Yerel NİP, MPYY 1.1.7 XSD, MSP Ek-1e, Arazi Kullanımı) on both
QGIS 3.44 LTR (PyQt5) and QGIS 4.2+ (PyQt6).
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime
import math
import re
from typing import Any, Iterable

try:
    from qgis.core import (
        NULL as _QGIS_NULL,
        Qgis,
        QgsFeature,
        QgsGeometry,
        QgsVariantUtils,
        QgsWkbTypes,
    )
    _HAS_QGIS = True
except ImportError:  # pragma: no cover - pure-Python test environments
    _QGIS_NULL = object()
    _HAS_QGIS = False

_TR_ASCII_MAP = str.maketrans("ÇĞİÖŞÜçğıöşü", "CGIOSUCGIOSU")

NON_FUNCTION_TIP_FIELDS = frozenset({
    "takstip",
    "emsalkakstip",
    "yapiyuksekligitip",
    "yoltipi",
    "y_tip",
    "zemin_tip",
    "sembol_tipi",
    "hattip",
    "kademetip",
})

PLAN_FUNCTION_FIELDS: tuple[str, ...] = (
    # Yerel UİP & Yerel NİP
    "uipfonksiyon",
    "nipfonksiyon",
    # Generic / crosswalk / catalog
    "fonksiyon_adi",
    "fonksiyon_kodu",
    "plan_fonk",
    "use_code",
    # Arazi Kullanımı & TUÇBS
    "P_FONK",
    "B_FONK",
    "tucbs_sinifi",
    # MSP Ek-1e
    "gosterim_adi",
    "msp_kodu",
    # MPYY 1.1.7 XSD explicit enum columns
    "KonutTip",
    "TicaretTip",
    "TicaretKonutTip",
    "KentselCalismaTip",
    "TurizmTip",
    "EgitimTesisTip",
    "SaglikTesisTip",
    "SosyalKulturelTesisTip",
    "SosyalAltyapiTip",
    "IbadetTip",
    "SporTesisTip",
    "IdariHizmetTip",
    "BelediyeHizmetTip",
    "KamuHizmetTip",
    "AcikYesilTip",
    "TeknikAltyapiTip",
    "EnerjiUretimTip",
    "KatiAtikTip",
    "AtiksuTesisTip",
    "IcmeSuyuTesisTip",
    "UlasimTip",
    "OtoparkTip",
    "TarimTip",
    "OrmanTip",
    "MeraTip",
    "SuYuzeyiTip",
    "KorumaAlanTip",
    "SitAlanTip",
    "AfetTehlikeliAlanTip",
    "AskeriAlanTip",
    "OzelKanunAlanTip",
    "Fonksiyon",
    "KullanimTuru",
    # Secondary catalog & group fallbacks
    "catalog_id",
    "detay_katalogu",
    "detay_grup_kodu",
    "lejant_kodu",
    "uip_tabaka",
    "ustkonugrup",
    "ust_konu_grup",
    "ust_grup_adi",
    "ust_grup_kodu",
    "strateji_bolgesi",
)


def upper_tr(text: Any) -> str:
    """Turkish-aware uppercase preserving dotted İ and dotless I."""
    return str(text or "").replace("i", "İ").replace("ı", "I").upper()


def lower_tr(text: Any) -> str:
    """Turkish-aware lowercase preserving dotted i and dotless ı."""
    return str(text or "").replace("İ", "i").replace("I", "ı").lower()


def norm_tr(val: Any) -> str:
    """Normalize Turkish text into uppercase ASCII token form (`A-Z0-9_`)."""
    if is_null_value(val):
        return ""
    raw = str(val).strip()
    # Split camelCase (e.g. MPYY 1.1.7 XSD `GelismeKonut` -> `GELISME_KONUT`)
    raw = re.sub(r"([a-zçğıöşü])([A-ZÇĞİÖŞÜ])", r"\1_\2", raw)
    folded = raw.translate(_TR_ASCII_MAP).upper()
    return re.sub(r"[^A-Z0-9]+", "_", folded).strip("_")


def is_null_value(val: Any) -> bool:
    """Return True iff ``val`` is Python None, PyQGIS NULL / null QVariant, or blank/'NULL'."""
    if val is None:
        return True
    if isinstance(val, bool):
        return False
    if _HAS_QGIS:
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            if val == _QGIS_NULL:
                return True
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            if QgsVariantUtils.isNull(val):
                return True
    if hasattr(val, "isNull") and callable(val.isNull):
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            if val.isNull():
                return True
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped or stripped.upper() in ("NULL", "NONE") or stripped.startswith("<PyQt"):
            return True
    return False


def clean_text(val: Any, default: str = "") -> str:
    """Convert non-null value to stripped string, returning ``default`` on NULL/empty."""
    if is_null_value(val):
        return default
    text = str(val).strip()
    if not text or text in ("NULL", "None") or text.startswith("<PyQt"):
        return default
    return text


def parse_float(val: Any) -> float | None:
    """Parse numeric or Turkish comma-decimal string (`'1,25'`, `'1.250,50'`), preserving `0.0`."""
    if isinstance(val, bool) or is_null_value(val):
        return None
    if isinstance(val, (int, float)):
        num = float(val)
        return num if math.isfinite(num) else None
    text = str(val).strip()
    if not text or text in ("NULL", "None"):
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    with contextlib.suppress(ValueError, TypeError):
        num = float(text)
        if math.isfinite(num):
            return num
    return None


def parse_int(val: Any) -> int | None:
    """Parse integer or integer-valued float/comma string, preserving `0`."""
    if isinstance(val, bool) or is_null_value(val):
        return None
    if isinstance(val, int):
        return val
    num = parse_float(val)
    if num is None:
        return None
    return int(round(num)) if abs(num - round(num)) < 1e-6 else int(num)


def parse_floor_count(val: Any, default: int | None = None) -> int | None:
    """Parse floor counts including Turkish planning notations (`'4'`, `'Z+3'`, `'4 Kat'`)."""
    direct = parse_int(val)
    if direct is not None:
        return direct
    text = clean_text(val)
    if not text:
        return default
    norm = norm_tr(text)
    if "SERBEST" in norm:
        return default
    # Match patterns like Z+3 (1 + 3 = 4) or B+Z+4
    z_match = re.search(r"\bZ\s*\+\s*(\d+)\b", text.upper())
    if z_match:
        return 1 + int(z_match.group(1))
    digits = re.search(r"(\d+)", text)
    if digits:
        return int(digits.group(1))
    return default


def parse_iso_date(val: Any) -> date | None:
    """Parse `datetime.date`, `datetime`, PyQt5/PyQt6 `QDate`/`QDateTime`, or ISO `YYYY-MM-DD`."""
    if is_null_value(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if hasattr(val, "toPyDate") and callable(val.toPyDate):
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            result = val.toPyDate()
            if isinstance(result, date):
                return result
    if hasattr(val, "date") and callable(val.date):
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            return parse_iso_date(val.date())
    if all(hasattr(val, attr) and callable(getattr(val, attr)) for attr in ("year", "month", "day")):
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            y, m, d = int(val.year()), int(val.month()), int(val.day())
            if y > 0 and 1 <= m <= 12 and 1 <= d <= 31:
                return date(y, m, d)
    text = clean_text(val)
    if not text:
        return None
    with contextlib.suppress(ValueError):
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    return None


def field_index_ci(fields: Any, name: str) -> int:
    """Resolve field index by exact name first, then case-insensitive / Turkish-folded match."""
    if fields is None or not name:
        return -1
    idx = fields.indexFromName(name)
    if idx >= 0:
        return idx
    if hasattr(fields, "lookupField"):
        idx = fields.lookupField(name)
        if idx >= 0:
            return idx
    target = lower_tr(name)
    for i in range(fields.count()):
        if lower_tr(fields.at(i).name()) == target:
            return i
    return -1


def first_raw(feat: Any, keys: Iterable[str]) -> Any:
    """Return the first non-null attribute value on ``feat`` across ``keys``."""
    fields = feat.fields()
    for key in keys:
        if not key:
            continue
        idx = field_index_ci(fields, key)
        if idx >= 0:
            val = feat[idx]
            if not is_null_value(val):
                return val
    return None


def first_text(feat: Any, keys: Iterable[str], default: str = "") -> str:
    """Return the first non-null stripped string attribute across ``keys``."""
    raw = first_raw(feat, keys)
    return clean_text(raw, default=default)


def first_float(feat: Any, keys: Iterable[str], default: float | None = None) -> float | None:
    """Return the first valid float attribute across ``keys``, preserving explicit `0.0`."""
    fields = feat.fields()
    for key in keys:
        if not key:
            continue
        idx = field_index_ci(fields, key)
        if idx >= 0:
            val = feat[idx]
            parsed = parse_float(val)
            if parsed is not None:
                return parsed
    return default


def first_int(feat: Any, keys: Iterable[str], default: int | None = None) -> int | None:
    """Return the first valid integer attribute across ``keys``, preserving explicit `0`."""
    fields = feat.fields()
    for key in keys:
        if not key:
            continue
        idx = field_index_ci(fields, key)
        if idx >= 0:
            val = feat[idx]
            parsed = parse_int(val)
            if parsed is not None:
                return parsed
    return default


def extract_plan_function(
    feat: Any,
    extra_keys: Iterable[str] = (),
    layer_name: str = "",
    default: str = "",
) -> str:
    """Extract the planning/land-use function across all 5 MPYY Studio workspace schemas."""
    keys = tuple(k for k in extra_keys if k) + PLAN_FUNCTION_FIELDS
    found = first_text(feat, keys, default="")
    if found:
        return found
    fields = feat.fields()
    for i in range(fields.count()):
        fname = fields.at(i).name()
        low = lower_tr(fname)
        if (low.endswith("tip") or low.endswith("tipi")) and low not in NON_FUNCTION_TIP_FIELDS:
            text = clean_text(feat[i])
            if text:
                return text
    if layer_name:
        clean_layer = layer_name.split(":")[-1].strip()
        if clean_layer and norm_tr(clean_layer) not in (
            "ALANLAR", "ALANLAR_5000", "UIP_ALANLAR", "PARSEL_SAHA", "YAPI_SAHA",
            "YOL_SAHA", "MSP_PLAN_KARARLARI", "PLAN_ONERI", "FIXTURE", "MEMORY",
        ):
            return clean_layer
    return default


def is_non_residential_work_zone(func_text: Any) -> bool:
    """True for `KONUT DIŞI KENTSEL ÇALIŞMA ALANI` (KDKÇA) so `KONUT` checks exclude it."""
    norm = f"_{norm_tr(func_text)}_"
    return any(tok in norm for tok in ("_KONUT_DISI_", "_KDKCA_", "_KONUTDISI_"))


def is_non_buildable_open_space(func_text: Any) -> bool:
    """True for parks, forests, cemeteries, roads, water, and open public spaces."""
    norm = f"_{norm_tr(func_text)}_"
    if norm == "__":
        return False
    # Exclude buildable facility types that may share words like YOL/SU/PARK (e.g. OTOPARK, ARITMA TESISI)
    if any(b in norm for b in ("_OTOPARK_", "_TESIS_", "_TESISI_", "_TESISLERI_", "_BINA_", "_KONUT_", "_TICARET_", "_SANAYI_")):
        return False
    open_tokens = (
        "_PARK_",
        "_PARK_ALANI_",
        "_PARK_VE_YESIL_",
        "_COCUK_BAHCESI_",
        "_COCUK_OYUN_",
        "_OYUN_ALANI_",
        "_AKTIF_YESIL_",
        "_PASIF_YESIL_",
        "_ACIK_VE_YESIL_",
        "_ACIK_YESIL_",
        "_YESIL_ALAN_",
        "_AGACLANDIRILACAK_",
        "_MEZARLIK_",
        "_ORMAN_",
        "_MERA_",
        "_MEYDAN_",
        "_YAYA_YOLU_",
        "_BISIKLET_YOLU_",
        "_TASIT_YOLU_",
        "_YOL_",
        "_YOL_ALANI_",
        "_SU_YUZEYI_",
        "_AKARSU_",
        "_DERE_",
        "_GOL_",
        "_GOLET_",
        "_DENIZ_",
        "_KUMSAL_",
        "_PLAJ_",
        "_REFUJ_",
    )
    return any(tok in norm for tok in open_tokens)


def normalize_nizam_code(raw: Any, default: str = "AYRIK") -> str:
    """Normalize PAİY / Yerel UİP / MPYY 1.1.7 building arrangement codes (`A`/`B`/`BL`/`İ`)."""
    norm = norm_tr(raw)
    if not norm:
        norm = norm_tr(default) or "AYRIK"
    if norm in ("B", "BITISIK", "BITISIK_NIZAM") or "BITISIK" in norm:
        return "BITISIK"
    if norm in ("I", "IK", "IKIZ", "IKIZ_NIZAM") or "IKIZ" in norm:
        return "IKIZ"
    if norm in ("BL", "BLOK", "BLOK_NIZAM") or "BLOK" in norm:
        return "BLOK"
    if norm in ("S", "SERBEST", "SERBEST_NIZAM") or "SERBEST" in norm:
        return "SERBEST"
    if norm in ("A", "AYRIK", "AYRIK_NIZAM") or "AYRIK" in norm:
        return "AYRIK"
    fallback = norm_tr(default)
    if fallback in ("BITISIK", "IKIZ", "BLOK", "SERBEST", "AYRIK"):
        return fallback
    return "AYRIK"


def reindex_features_with_map(features: Iterable[Any]) -> tuple[list[Any], dict[int, Any]]:
    """Assign unique sequential IDs `1..N` to feature copies, returning (indexed_list, seq_to_orig_map)."""
    indexed: list[Any] = []
    mapping: dict[int, Any] = {}
    for seq_id, feat in enumerate(features, start=1):
        clone = QgsFeature(feat)
        clone.setId(seq_id)
        indexed.append(clone)
        mapping[seq_id] = feat
    return indexed, mapping


def reindex_features(features: Iterable[Any]) -> list[Any]:
    """Assign unique sequential IDs `1..N` to feature copies for safe `QgsSpatialIndex` lookup."""
    indexed, _ = reindex_features_with_map(features)
    return indexed


def linearize_geometry(geom: Any) -> Any:
    """Ensure geometry has no curved segments (convert CircularString/CompoundCurve to straight segments)."""
    if not _HAS_QGIS or geom is None or geom.isEmpty():
        return geom
    with contextlib.suppress(Exception):
        if QgsWkbTypes.isCurvedType(geom.wkbType()):
            conv = geom.curveToLine()
            if conv and not conv.isEmpty():
                return conv
    return geom


def adapt_geometry_for_sink(geom: Any, target_wkb: Any) -> Any:
    """Adapt ``geom`` (single/multi, 2D/Z/M, curved, or GeometryCollection) to ``target_wkb``."""
    if not _HAS_QGIS:
        return geom
    if geom is None or geom.isEmpty():
        return QgsGeometry()
    work = QgsGeometry(geom)
    target_geom_type = QgsWkbTypes.geometryType(target_wkb)
    want_multi = QgsWkbTypes.isMultiType(target_wkb)
    want_z = QgsWkbTypes.hasZ(target_wkb)
    want_m = QgsWkbTypes.hasM(target_wkb)

    # Linearize curves if target is not a curve WKB type
    if QgsWkbTypes.isCurvedType(work.wkbType()) and not QgsWkbTypes.isCurvedType(target_wkb):
        with contextlib.suppress(TypeError, ValueError, RuntimeError, AttributeError):
            abs_geom = work.constGet()
            if abs_geom is not None and hasattr(abs_geom, "segmentize"):
                work = QgsGeometry(abs_geom.segmentize())

    # Extract matching dimension parts from GeometryCollection or mismatched collection
    if work.type() != target_geom_type or QgsWkbTypes.flatType(work.wkbType()) == QgsWkbTypes.Type.GeometryCollection:
        extracted = work.convertToType(target_geom_type, want_multi)
        if extracted is not None and not extracted.isNull() and not extracted.isEmpty():
            work = extracted
        else:
            parts = [
                QgsGeometry(part.clone())
                for part in work.asGeometryCollection()
                if QgsGeometry(part.clone()).type() == target_geom_type and not part.isEmpty()
            ]
            if not parts:
                return QgsGeometry()
            work = QgsGeometry.collectGeometry(parts) if len(parts) > 1 else parts[0]

    if not want_z and QgsWkbTypes.hasZ(work.wkbType()):
        work.get().dropZValue()
    if not want_m and QgsWkbTypes.hasM(work.wkbType()):
        work.get().dropMValue()

    if want_multi and not QgsWkbTypes.isMultiType(work.wkbType()):
        work.convertToMultiType()
    elif not want_multi and QgsWkbTypes.isMultiType(work.wkbType()):
        parts = [p for p in work.asGeometryCollection() if not p.isEmpty()]
        if parts:
            work = max(parts, key=lambda g: g.area() if target_geom_type == Qgis.GeometryType.Polygon else g.length())

    return work
