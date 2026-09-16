"""PlanX MPYY Zoning Development Intensity & Population Capacity Engine.

Calculates statutory residential development capacity and projected population
for zoning master plans (NİP) and implementation plans (UİP) under MPYY principles:
- Evaluates zoning polygons: residential (Konut), mixed-use (Ticaret+Konut), etc.
- Determines Building Coverage Ratio (TAKS) and Floor Area Ratio (KAKS / Emsal).
- Computes Gross Floor Area (İnşaat Alanı), Dwelling Count (Konut Sayısı),
  and Projected Population (Öngörülen Nüfus Kapasitesi).
- Interlocks projected population directly into MPYY EK-2 Asgari Donatı Standartları
  to audit whether the plan provides sufficient social & technical infrastructure
  for its own designed population capacity.
"""

from dataclasses import dataclass, field
import re
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
)

from .synthesis import AmenityDeficitResult, SynthesisEngine


def _norm(val: Any) -> str:
    text = str(val or "").strip().upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


@dataclass
class ZoneCapacityItem:
    fid: int
    fonksiyon: str
    alan_m2: float
    taks: float
    kaks: float
    taban_alani_m2: float
    toplam_insaat_m2: float
    emsal_harici_m2: float
    toplam_ruhsat_m2: float
    konut_orani: float
    konut_insaat_m2: float
    konut_sayisi: int
    ongorulen_nufus: int
    geometri: QgsGeometry | None = None


@dataclass
class CapacitySummary:
    toplam_imar_alani_m2: float = 0.0
    toplam_konut_alani_m2: float = 0.0
    toplam_insaat_m2: float = 0.0
    toplam_emsal_harici_m2: float = 0.0
    toplam_ruhsat_insaat_m2: float = 0.0
    toplam_konut_sayisi: int = 0
    toplam_kapasite_nufusu: int = 0
    brut_yogunluk_kisi_ha: float = 0.0
    ortalama_kaks: float = 0.0
    ortalama_konut_m2: float = 100.0
    hane_halki_buyuklugu: float = 3.2
    donati_yeterlilik: list[AmenityDeficitResult] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)


class PlanCapacityEngine:
    """Zoning development capacity and population projection modeling engine."""

    RESIDENTIAL_KEYWORDS = (
        "KONUT", "GELISME_KONUT", "MESKUN_KONUT", "YERLESIK_KONUT", "KONUT_ALANI",
    )
    MIXED_USE_KEYWORDS = (
        "TICARET_KONUT", "TICKONUT", "KARMA", "TIZ", "MERKEZI_IS", "MIA",
    )

    @classmethod
    def _extract_float(cls, feat: QgsFeature, preferred_keys: tuple[str, ...], default: float) -> float:
        fields = feat.fields()
        for k in preferred_keys:
            idx = fields.indexFromName(k)
            if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                try:
                    v = float(str(feat[idx]).replace(",", ' satır bulundu.'))
                    if v > 0:
                        return v
                except (ValueError, TypeError):
                    pass
        return default

    @classmethod
    def _extract_text(cls, feat: QgsFeature, preferred_keys: tuple[str, ...]) -> str:
        fields = feat.fields()
        for k in preferred_keys:
            idx = fields.indexFromName(k)
            if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                return str(feat[idx]).strip()
        return ""

    @classmethod
    def estimate_capacity(
        cls,
        plan_features: list[QgsFeature],
        default_kaks: float = 1.2,
        default_taks: float = 0.35,
        avg_unit_m2: float = 100.0,
        household_size: float = 3.2,
        feedback: Any = None,
    ) -> tuple[list[ZoneCapacityItem], CapacitySummary]:
        """Evaluates all plan zoning features, calculating development intensity and population."""
        items: list[ZoneCapacityItem] = []
        summary = CapacitySummary(
            ortalama_konut_m2=avg_unit_m2,
            hane_halki_buyuklugu=household_size,
        )

        if not plan_features:
            summary.uyarilar.append('Hesaplama için plan katmanında poligon bulunamadı.')
            return items, summary

        fn_keys = ("uipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK", "plan_fonk", "catalog_id", "detay_katalogu")
        kaks_keys = ("KAKS", "kaks", "EMSAL", "emsal", "E", "e", "katsayisi")
        taks_keys = ("TAKS", "taks", "tabankatsayisi", "T", "t")

        total_area = 0.0
        total_res_area = 0.0
        total_construction = 0.0
        total_emsal_harici = 0.0
        total_ruhsat = 0.0
        total_units = 0
        total_pop = 0

        for feat in plan_features:
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area_m2 = geom.area()
            if area_m2 <= 0.1:
                continue

            total_area += area_m2
            fn_val = cls._extract_text(feat, fn_keys) or "BELIRTILMEMIS"
            norm_fn = _norm(fn_val)

            is_mixed = any(kw in norm_fn for kw in cls.MIXED_USE_KEYWORDS)
            is_res = not is_mixed and any(kw in norm_fn for kw in cls.RESIDENTIAL_KEYWORDS)

            if not is_res and not is_mixed:
                continue  # Non-residential zoning (park, school, industrial, road, etc.)

            total_res_area += area_m2
            kaks = cls._extract_float(feat, kaks_keys, default_kaks)
            taks = cls._extract_float(feat, taks_keys, default_taks)

            taban_m2 = round(area_m2 * taks, 2)
            insaat_m2 = round(area_m2 * kaks, 2)
            # PAİY Madde 5: Azami %30 emsal harici alan (sığınak, otopark, yangın holleri, ortak alanlar)
            emsal_harici_m2 = round(insaat_m2 * 0.30, 2)
            ruhsat_m2 = round(insaat_m2 + emsal_harici_m2, 2)

            res_ratio = 1.0 if is_res else 0.60  # Mixed-use assumes 60% residential, 40% commercial
            konut_insaat = round(insaat_m2 * res_ratio, 2)

            units = int(konut_insaat / max(10.0, avg_unit_m2))
            pop = int(units * household_size)

            total_construction += insaat_m2
            total_emsal_harici += emsal_harici_m2
            total_ruhsat += ruhsat_m2
            total_units += units
            total_pop += pop

            items.append(
                ZoneCapacityItem(
                    fid=feat.id(),
                    fonksiyon=fn_val,
                    alan_m2=round(area_m2, 2),
                    taks=round(taks, 2),
                    kaks=round(kaks, 2),
                    taban_alani_m2=taban_m2,
                    toplam_insaat_m2=insaat_m2,
                    emsal_harici_m2=emsal_harici_m2,
                    toplam_ruhsat_m2=ruhsat_m2,
                    konut_orani=res_ratio,
                    konut_insaat_m2=konut_insaat,
                    konut_sayisi=units,
                    ongorulen_nufus=pop,
                    geometri=geom,
                )
            )

        summary.toplam_imar_alani_m2 = round(total_area, 2)
        summary.toplam_konut_alani_m2 = round(total_res_area, 2)
        summary.toplam_insaat_m2 = round(total_construction, 2)
        summary.toplam_emsal_harici_m2 = round(total_emsal_harici, 2)
        summary.toplam_ruhsat_insaat_m2 = round(total_ruhsat, 2)
        summary.toplam_konut_sayisi = total_units
        summary.toplam_kapasite_nufusu = total_pop

        ha_area = total_area / 10000.0
        summary.brut_yogunluk_kisi_ha = round(total_pop / ha_area, 1) if ha_area > 0 else 0.0
        summary.ortalama_kaks = round(total_construction / total_res_area, 2) if total_res_area > 0 else 0.0

        # Run statutory MPYY EK-2 Amenity analysis against this calculated capacity population
        existing_amenities = SynthesisEngine.extract_amenities_from_features(plan_features)
        summary.donati_yeterlilik = SynthesisEngine.analyze_all_amenities(
            population=total_pop if total_pop > 0 else 1000,
            amenity_areas=existing_amenities,
            region_name='Öngörülen İmar Kapasitesi',
        )

        return items, summary
