"""PlanX MPYY Statutory Parking Requirement and Capacity Engine.

Implements the official statutory parking standards of Turkey's Otopark Yönetmeliği
(Resmî Gazete Tarihi: 22.02.2018 / 30340 ve güncel değişiklikler):
- Konut Alanları (Mesken): Daire büyüklüklerine göre kademeli veya ortalama 2 konut / 1 araç (0.50).
- Ticaret / Ofis / İş Merkezi: Her 40 m² veya 50 m² brüt inşaat alanı için 1 araç.
- Turizm / Konaklama (Otel, Motel): Her 3 oda için 1 araç.
- Sanayi / Depolama: Her 150 m² inşaat alanı için 1 araç.
- Sağlık Tesisleri (Hastane): Her 75 m² brüt inşaat alanı için 1 araç.
- Eğitim Tesisleri: Her 300 m² brüt inşaat alanı için 1 araç.
- Sosyal / Kültür / İbadet: Her 100 m² için 1 araç.

Calculates parking requirements, compares against planned public parking spaces (25 m² per vehicle),
and reports parking surplus/deficit across the planning area.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any
from qgis.core import QgsFeature

from .attr_utils import (
    extract_plan_function,
    first_float,
    first_text,
    is_non_buildable_open_space,
    is_non_residential_work_zone,
    norm_tr,
)


def _norm_text(val: Any) -> str:
    return norm_tr(val)


# Statutory rates: gross m2 per required vehicle space
PARKING_RATES_M2_PER_VEHICLE: dict[str, float] = {
    "KONUT": 150.0,       # ~0.67 vehicle per 100 m2 housing unit
    "TICARET": 40.0,      # 1 vehicle per 40 m2 retail/office
    "KARMA": 65.0,        # Weighted retail + residential
    "SANAYI": 150.0,      # 1 vehicle per 150 m2 factory/storage
    "KUCUK_SANAYI": 100.0,# 1 vehicle per 100 m2 workshop
    "TURIZM": 60.0,       # 1 vehicle per ~60 m2 hotel area (approx 1 per 2-3 rooms)
    "SAGLIK": 75.0,       # 1 vehicle per 75 m2 clinic/hospital
    "EGITIM": 300.0,      # 1 vehicle per 300 m2 school
    "SOSYAL_KULTUR": 80.0,# 1 vehicle per 80 m2
    "IBADET": 120.0,      # 1 vehicle per 120 m2
    "KAMU_BELEDIYE": 60.0,# 1 vehicle per 60 m2 municipal/administrative
    "DIGER": 100.0,
}

PARKING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "KARMA": ("TICARET_KONUT", "TICARET_TURIZM_KONUT", "KARMA", "TICK", "TICKONUT", "KONUT_TICARET"),
    "KUCUK_SANAYI": ("KUCUK_SANAYI", "KSS", "IMALATHANE", "TAMIRHANE"),
    "SANAYI": ("SANAYI", "ORGANIZE_SANAYI", "ORGANIZED_SANAYI", "OSB", "ENDUSTRI", "FABRIKA", "DEPOLAMA", "LOJISTIK"),
    "TICARET": ("TICARET", "TICARI", "CARSI", "IS_MERKEZI", "OFIS", "BURO", "AVM", "TOPTAN_TICARET", "MERKEZI_IS", "MIA", "PAZAR"),
    "TURIZM": ("TURIZM", "OTEL", "MOTEL", "PANSIYON", "TATIL_KOYU", "GUNUBIRLIK"),
    "SAGLIK": ("SAGLIK", "HASTANE", "AILE_SAGLIGI", "ASM", "POLIKLINIK"),
    "EGITIM": ("EGITIM", "ILKOKUL", "ORTAOKUL", "LISE", "ANAOKULU", "KRES", "OKUL", "KAMPUS", "UNIVERSITE"),
    "SOSYAL_KULTUR": ("SOSYAL", "KULTUR", "KUTUPHANE", "MUZE", "YURT", "GENCLIK_MERKEZI", "HUZUREVI"),
    "IBADET": ("IBADET", "CAMI", "MESCIT", "DINI", "CEMEVI"),
    "KAMU_BELEDIYE": ("BHA", "BELEDIYE_HIZMET", "KHA", "KAMU_HIZMET", "RESMI_KURUM", "IDARI"),
    "KONUT": ("KONUT", "GELISME_KONUT", "MESKUN", "YERLESIK_KONUT", "DUSUK_YOGUNLUK", "ORTA_YOGUNLUK", "YUKSEK_YOGUNLUK"),
}

PUBLIC_PARKING_KEYWORDS = (
    "OTOPARK", "ACIK_OTOPARK", "KATLI_OTOPARK", "BOLGE_OTOPARKI", "GENEL_OTOPARK", "YERALTI_OTOPARKI"
)


def classify_parking_category(function_name: str, group_name: str = "") -> str:
    combined = "_".join(part for part in (_norm_text(function_name), _norm_text(group_name)) if part)
    if not combined:
        return "DIGER"
    if is_non_residential_work_zone(combined):
        return "SANAYI" if "SANAYI" in combined else "TICARET"
    for cat, kws in PARKING_KEYWORDS.items():
        for kw in kws:
            if f"_{kw}_" in f"_{combined}_" or combined == kw:
                return cat
    return "DIGER"


@dataclass
class ParcelParkingResult:
    feature_id: Any
    fonksiyon: str
    kategori: str
    alan_m2: float
    emsal: float
    insaat_alani_m2: float
    otopark_ihtiyaci_arac: int
    tahsis_edilen_m2: float


@dataclass
class ParkingSummary:
    toplam_plan_alani_m2: float = 0.0
    toplam_insaat_alani_m2: float = 0.0
    toplam_otopark_ihtiyaci_arac: int = 0
    toplam_otopark_ihtiyaci_m2: float = 0.0
    planda_ayrilan_otopark_m2: float = 0.0
    planda_ayrilan_otopark_kapasite_arac: int = 0
    otopark_acigi_fazlasi_arac: int = 0
    otopark_acigi_fazlasi_m2: float = 0.0
    karsilama_orani_yuzde: float = 0.0
    yeterli_mi: bool = False
    kategori_detaylari: dict[str, dict[str, Any]] = field(default_factory=dict)


class ParkingEngine:
    """Calculates statutory parking requirements and balances under Otopark Yönetmeliği."""

    @classmethod
    def evaluate_parking_balance(
        cls,
        features: list[QgsFeature],
        default_kaks: float = 1.2,
        area_per_car_m2: float = 25.0,
    ) -> tuple[list[ParcelParkingResult], ParkingSummary]:
        """Compute parking requirements and compare against public parking polygons."""
        fn_keys = (
            "uipfonksiyon", "nipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK",
            "plan_fonk", "catalog_id", "detay_katalogu",
        )
        grp_keys = ("ustkonugrup", "ust_konu_grup", "ust_grup_adi", "ana_grup", "strateji_bolgesi")
        kaks_keys = ("kaks", "KAKS", "emsal", "EMSAL", "EmsalKaks", "P_EMSAL", "P_KAKS")

        results: list[ParcelParkingResult] = []
        summary = ParkingSummary()

        cat_aggregates: dict[str, dict[str, Any]] = {}
        total_public_parking_m2 = 0.0
        safe_area_per_car = max(1.0, float(area_per_car_m2))

        for feat in features:
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area_m2 = round(geom.area(), 2)
            if area_m2 <= 0:
                continue

            fn_val = extract_plan_function(feat, extra_keys=fn_keys)
            grp_val = first_text(feat, grp_keys)
            norm_fn = _norm_text(fn_val)

            # Check if this polygon is a dedicated public parking lot
            is_pub_parking = any(p_kw in norm_fn for p_kw in PUBLIC_PARKING_KEYWORDS)
            if is_pub_parking:
                total_public_parking_m2 += area_m2
                continue

            # Extract KAKS / Emsal (preserve explicit 0.0; exempt open spaces without explicit KAKS > 0)
            raw_kaks = first_float(feat, kaks_keys, default=None)
            if raw_kaks is not None and raw_kaks >= 0.0:
                emsal = raw_kaks
            elif is_non_buildable_open_space(norm_fn):
                continue
            else:
                emsal = default_kaks

            cat = classify_parking_category(fn_val, grp_val)
            insaat_m2 = round(area_m2 * emsal, 2)
            rate_m2 = PARKING_RATES_M2_PER_VEHICLE.get(cat, 100.0)

            # Required parking vehicles (rounded up)
            req_cars = max(1, math.ceil(insaat_m2 / rate_m2)) if insaat_m2 >= 30.0 else 0
            req_m2 = round(req_cars * safe_area_per_car, 2)

            results.append(
                ParcelParkingResult(
                    feature_id=feat.id(),
                    fonksiyon=fn_val or "BELIRTILMEMIS",
                    kategori=cat,
                    alan_m2=area_m2,
                    emsal=emsal,
                    insaat_alani_m2=insaat_m2,
                    otopark_ihtiyaci_arac=req_cars,
                    tahsis_edilen_m2=req_m2,
                )
            )

            # Aggregate by category
            if cat not in cat_aggregates:
                cat_aggregates[cat] = {
                    "toplam_insaat_m2": 0.0,
                    "toplam_arac": 0,
                    "toplam_parsel": 0,
                }
            cat_aggregates[cat]["toplam_insaat_m2"] += insaat_m2
            cat_aggregates[cat]["toplam_arac"] += req_cars
            cat_aggregates[cat]["toplam_parsel"] += 1

        # Calculate Summary Metrics
        summary.toplam_plan_alani_m2 = round(sum(r.alan_m2 for r in results) + total_public_parking_m2, 2)
        summary.toplam_insaat_alani_m2 = round(sum(r.insaat_alani_m2 for r in results), 2)
        summary.toplam_otopark_ihtiyaci_arac = sum(r.otopark_ihtiyaci_arac for r in results)
        summary.toplam_otopark_ihtiyaci_m2 = round(summary.toplam_otopark_ihtiyaci_arac * safe_area_per_car, 2)

        summary.planda_ayrilan_otopark_m2 = round(total_public_parking_m2, 2)
        summary.planda_ayrilan_otopark_kapasite_arac = int(total_public_parking_m2 // safe_area_per_car)

        summary.otopark_acigi_fazlasi_arac = summary.planda_ayrilan_otopark_kapasite_arac - summary.toplam_otopark_ihtiyaci_arac
        summary.otopark_acigi_fazlasi_m2 = round(summary.planda_ayrilan_otopark_m2 - summary.toplam_otopark_ihtiyaci_m2, 2)

        if summary.toplam_otopark_ihtiyaci_arac > 0:
            summary.karsilama_orani_yuzde = round(
                (summary.planda_ayrilan_otopark_kapasite_arac / summary.toplam_otopark_ihtiyaci_arac) * 100.0, 2
            )
        else:
            summary.karsilama_orani_yuzde = 100.0

        summary.yeterli_mi = summary.otopark_acigi_fazlasi_arac >= 0
        summary.kategori_detaylari = cat_aggregates

        return results, summary
