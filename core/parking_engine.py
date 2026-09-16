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

import contextlib
from dataclasses import dataclass, field
import math
import re
from typing import Any
from qgis.core import QgsFeature, QgsGeometry


def _norm_text(val: Any) -> str:
    text = str(val or "").strip().upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


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
    "KONUT": ("KONUT", "GELISME_KONUT", "MESKUN", "YERLESIK_KONUT", "DUSUK_YOGUNLUK", "ORTA_YOGUNLUK", "YUKSEK_YOGUNLUK"),
    "TICARET": ("TICARET", "TICARI", "CARSI", "IS_MERKEZI", "OFIS", "BURO", "AVM"),
    "KARMA": ("TICARET_KONUT", "KARMA", "TICK", "KONUT_TICARET"),
    "SANAYI": ("SANAYI", "ORGANIZED_SANAYI", "OSB", "ENDUSTRI", "FABRIKA"),
    "KUCUK_SANAYI": ("KUCUK_SANAYI", "KSS", "IMALATHANE", "TAMIRHANE"),
    "TURIZM": ("TURIZM", "OTEL", "MOTEL", "PANSIYON", "TATIL_KOYU"),
    "SAGLIK": ("SAGLIK", "HASTANE", "AILE_SAGLIGI", "ASM", "POLIKLINIK"),
    "EGITIM": ("EGITIM", "ILKOKUL", "ORTAOKUL", "LISE", "ANAOKULU", "OKUL", "KAMPUS"),
    "SOSYAL_KULTUR": ("SOSYAL", "KULTUR", "KUTUPHANE", "MUZE", "YURT", "GENCLIK_MERKEZI"),
    "IBADET": ("IBADET", "CAMI", "MESCIT", "DINI"),
    "KAMU_BELEDIYE": ("BHA", "BELEDIYE_HIZMET", "KHA", "KAMU_HIZMET", "RESMI_KURUM"),
}

PUBLIC_PARKING_KEYWORDS = (
    "OTOPARK", "ACIK_OTOPARK", "KATLI_OTOPARK", "BOLGE_OTOPARKI", "GENEL_OTOPARK", "YERALTI_OTOPARKI"
)


def classify_parking_category(function_name: str, group_name: str = "") -> str:
    combined = f"{_norm_text(function_name)}_{_norm_text(group_name)}"
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
        fn_keys = ("uipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK", "plan_fonk", "catalog_id", "detay_katalogu")
        grp_keys = ("ustkonugrup", "ust_konu_grup", "ust_grup_adi", "ana_grup")
        kaks_keys = ("kaks", "emsal", "P_EMSAL", "P_KAKS")

        results: list[ParcelParkingResult] = []
        summary = ParkingSummary()

        cat_aggregates: dict[str, dict[str, Any]] = {}
        total_public_parking_m2 = 0.0

        for feat in features:
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area_m2 = round(geom.area(), 2)
            if area_m2 <= 0:
                continue

            # Extract Function
            fn_val = ""
            for k in fn_keys:
                idx = feat.fields().indexFromName(k)
                if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                    fn_val = str(feat[idx]).strip()
                    break

            grp_val = ""
            for gk in grp_keys:
                idx = feat.fields().indexFromName(gk)
                if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                    grp_val = str(feat[idx]).strip()
                    break

            norm_fn = _norm_text(fn_val)

            # Check if this polygon is a dedicated public parking lot
            is_pub_parking = any(p_kw in norm_fn for p_kw in PUBLIC_PARKING_KEYWORDS)
            if is_pub_parking:
                total_public_parking_m2 += area_m2
                continue

            # Extract KAKS / Emsal
            emsal = default_kaks
            for kk in kaks_keys:
                idx = feat.fields().indexFromName(kk)
                if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                    try:
                        val = float(feat[idx])
                        if val > 0:
                            emsal = val
                            break
                    except (ValueError, TypeError):
                        pass

            cat = classify_parking_category(fn_val, grp_val)
            insaat_m2 = round(area_m2 * emsal, 2)
            rate_m2 = PARKING_RATES_M2_PER_VEHICLE.get(cat, 100.0)

            # Required parking vehicles (rounded up)
            req_cars = max(1, math.ceil(insaat_m2 / rate_m2)) if insaat_m2 >= 30.0 else 0
            req_m2 = round(req_cars * area_per_car_m2, 2)

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
        summary.toplam_otopark_ihtiyaci_m2 = round(summary.toplam_otopark_ihtiyaci_arac * area_per_car_m2, 2)

        summary.planda_ayrilan_otopark_m2 = round(total_public_parking_m2, 2)
        summary.planda_ayrilan_otopark_kapasite_arac = int(total_public_parking_m2 // area_per_car_m2)

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
