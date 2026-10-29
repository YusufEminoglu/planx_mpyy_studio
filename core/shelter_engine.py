"""PlanX MPYY Statutory Shelter Requirement and Capacity Engine.

Implements the official statutory shelter assessment standards under:
- Planning Law No. 3194 (3194 Sayılı İmar Kanunu)
- Shelter Regulation (Sığınak Yönetmeliği - Resmî Gazete 25.08.1990 / 20616 ve güncellemeleri)

Statutory Thresholds for Compulsory Private Shelters (Madde 7 - Serpiştirme Sığınakları):
1. Konut Yapıları: 12 ve üzeri bağımsız bölüm veya toplam inşaat alanı >= 1500 m².
2. Ticaret, İşyeri, Büro, Çarşı, AVM: Toplam inşaat alanı >= 1000 m².
3. Sanayi, İmalathane ve Fabrika Yapıları: Toplam inşaat alanı >= 1000 m².
4. Otel, Motel, Pansiyon ve Yurtlar: Yatak sayısı >= 50 veya toplam inşaat alanı >= 1200 m².
5. Resmî Kurum, Kamu Binaları, Eğitim ve Sağlık: Toplam inşaat alanı >= 800 m².
6. Sinema, Tiyatro, Düğün Salonu, Spor Salonu: Kapasite >= 100 kişi veya alan >= 800 m².

Statutory Dimensioning Standards:
- Kişi başına asgari 1.0 m² net, 1.2 m² brüt sığınak alanı.
- Konutlarda ortalama 4 kişi/daire x 1.2 = 4.8 m² veya brüt inşaat alanının %2.0'si.
- Ticari yapılarda brüt inşaat alanının %2.5'i.
- Kamu/Sağlık/Eğitim binalarında brüt inşaat alanının %3.0'ü.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from qgis.core import QgsFeature

from .attr_utils import (
    extract_plan_function,
    first_float,
    first_int,
    is_non_buildable_open_space,
    is_non_residential_work_zone,
    norm_tr,
)


def _norm_text(val: Any) -> str:
    return norm_tr(val)


@dataclass
class ParcelShelterResult:
    feature_id: Any
    fonksiyon: str
    kategori: str
    alan_m2: float
    emsal: float
    insaat_alani_m2: float
    siginak_zorunlu_mu: bool
    siginak_durumu: str
    gerekli_siginak_alani_m2: float
    ongorulen_siginak_kapasite_kisi: int
    yasal_dayanak: str


@dataclass
class ShelterSummary:
    toplam_parsel_sayisi: int = 0
    toplam_alan_m2: float = 0.0
    toplam_insaat_alani_m2: float = 0.0
    siginak_zorunlu_parsel_sayisi: int = 0
    muaf_parsel_sayisi: int = 0
    toplam_gerekli_siginak_alani_m2: float = 0.0
    toplam_siginacak_kisi_kapasitesi: int = 0
    zorunlu_parsel_orani_yuzde: float = 0.0
    genel_siginak_ayrilmali_mi: bool = False
    genel_siginak_gerekcesi: str = ""


class ShelterEngine:
    """Evaluates statutory shelter requirements under Turkey's Sığınak Yönetmeliği."""

    @classmethod
    def evaluate_shelter_requirements(
        cls,
        features: list[QgsFeature],
        default_kaks: float = 1.2,
        area_per_person_m2: float = 1.2,
    ) -> tuple[list[ParcelShelterResult], ShelterSummary]:
        """Calculates parcel-level shelter obligations and aggregates planning area shelter capacity."""
        results: list[ParcelShelterResult] = []
        summary = ShelterSummary()

        fn_keys = (
            "uipfonksiyon", "nipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK",
            "plan_fonk", "catalog_id", "detay_katalogu",
        )
        kaks_keys = ("kaks", "KAKS", "emsal", "EMSAL", "EmsalKaks", "P_EMSAL", "P_KAKS")
        unit_keys = ("bagimsiz_bolum_sayisi", "konut_sayisi", "daire_sayisi", "P_BAGIMSIZ_BOLUM", "B_B_BOLUM")
        safe_area_per_person = max(0.1, float(area_per_person_m2))

        for feat in features:
            geom = feat.geometry()
            area_m2 = round(geom.area(), 2) if geom and not geom.isEmpty() else 0.0
            if area_m2 <= 0:
                continue

            fn_val = extract_plan_function(feat, extra_keys=fn_keys)
            norm_fn = _norm_text(fn_val)
            non_res_work = is_non_residential_work_zone(norm_fn)

            # Extract KAKS (preserve explicit 0.0 and exempt open spaces without explicit KAKS > 0)
            raw_kaks = first_float(feat, kaks_keys, default=None)
            if raw_kaks is not None and raw_kaks >= 0.0:
                emsal = raw_kaks
            elif is_non_buildable_open_space(norm_fn):
                emsal = 0.0
            else:
                emsal = default_kaks

            # Extract Units
            raw_units = first_int(feat, unit_keys, default=0)
            units = raw_units if (raw_units is not None and raw_units > 0) else 0

            insaat_m2 = round(area_m2 * emsal, 2)
            is_mixed = not non_res_work and any(w in norm_fn for w in ("TICARET_KONUT", "TICKONUT", "KARMA", "KONUT_TICARET"))
            is_residential = not non_res_work and not is_mixed and any(
                w in norm_fn for w in ("KONUT", "MESKEN", "GELISME_KONUT", "YERLESIK_KONUT")
            )
            if units == 0 and is_residential and insaat_m2 > 0:
                units = max(1, int(insaat_m2 // 110))
            elif units == 0 and is_mixed and insaat_m2 > 0:
                units = max(1, int((insaat_m2 * 0.60) // 110))

            # Threshold and calculation by category
            is_commercial = non_res_work or is_mixed or any(
                w in norm_fn for w in ("TICARET", "OFIS", "CARSI", "IS_MERKEZI", "AVM", "BURO", "MERKEZI_IS", "MIA")
            )
            is_industrial = any(w in norm_fn for w in ("SANAYI", "FABRIKA", "IMALATHANE", "KSS", "DEPO"))
            is_hotel = any(w in norm_fn for w in ("OTEL", "MOTEL", "PANSIYON", "TURIZM", "YURT"))
            is_public_edu_health = any(w in norm_fn for w in ("KAMU", "RESMI", "BELEDIYE", "OKUL", "EGITIM", "SAGLIK", "HASTANE"))

            is_mandatory = False
            cat = "DIGER"
            req_m2 = 0.0
            dayanak = ""

            if is_residential:
                cat = "KONUT"
                if units >= 12 or insaat_m2 >= 1500.0:
                    is_mandatory = True
                    req_m2 = round(max(units * 4.8, insaat_m2 * 0.02), 2)
                    dayanak = 'Md. 7/a: 12+ Bağımsız Bölüm veya >=1500 m² Konut'
                else:
                    dayanak = 'Md. 7: 12 bağımsız bölüm ve 1500 m² altında (Muaf)'
            elif is_commercial:
                cat = "TICARET"
                if insaat_m2 >= 1000.0:
                    is_mandatory = True
                    req_m2 = round(insaat_m2 * 0.025, 2)
                    dayanak = 'Md. 7/b: >=1000 m² Ticari ve İşyeri Yapısı'
                else:
                    dayanak = 'Md. 7: 1000 m² altında ticari yapı (Muaf)'
            elif is_industrial:
                cat = "SANAYI"
                if insaat_m2 >= 1000.0:
                    is_mandatory = True
                    req_m2 = round(insaat_m2 * 0.02, 2)
                    dayanak = 'Md. 7/c: >=1000 m² Sanayi ve Tesis Yapısı'
                else:
                    dayanak = 'Md. 7: 1000 m² altında sanayi (Muaf)'
            elif is_hotel:
                cat = "KONAKLAMA"
                if insaat_m2 >= 1200.0:
                    is_mandatory = True
                    req_m2 = round(insaat_m2 * 0.025, 2)
                    dayanak = "Md. 7/d: >=1200 m² veya 50+ Yatak Konaklama/Yurt"
                else:
                    dayanak = 'Md. 7: 50 yatak / 1200 m² altında (Muaf)'
            elif is_public_edu_health:
                cat = "KAMU_EGITIM_SAGLIK"
                if insaat_m2 >= 800.0:
                    is_mandatory = True
                    req_m2 = round(insaat_m2 * 0.03, 2)
                    dayanak = 'Md. 7/e: >=800 m² Resmî/Eğitim/Sağlık Yapısı'
                else:
                    dayanak = 'Md. 7: 800 m² altında kamu yapısı (Muaf)'
            else:
                cat = "DIGER"
                if insaat_m2 >= 1000.0:
                    is_mandatory = True
                    req_m2 = round(insaat_m2 * 0.02, 2)
                    dayanak = 'Md. 7: >=1000 m² Genel Toplanma Yapısı'
                else:
                    dayanak = "Md. 7: Muaf"

            durum = "SIGINAK_ZORUNLU" if is_mandatory else "SIGINAK_MUAFIYET"
            shelter_cap = int(req_m2 // safe_area_per_person) if is_mandatory else 0

            item = ParcelShelterResult(
                feature_id=feat.id(),
                fonksiyon=fn_val or "BELIRTILMEMIS",
                kategori=cat,
                alan_m2=area_m2,
                emsal=emsal,
                insaat_alani_m2=insaat_m2,
                siginak_zorunlu_mu=is_mandatory,
                siginak_durumu=durum,
                gerekli_siginak_alani_m2=req_m2,
                ongorulen_siginak_kapasite_kisi=shelter_cap,
                yasal_dayanak=dayanak,
            )
            results.append(item)

            summary.toplam_parsel_sayisi += 1
            summary.toplam_alan_m2 += area_m2
            summary.toplam_insaat_alani_m2 += insaat_m2
            if is_mandatory:
                summary.siginak_zorunlu_parsel_sayisi += 1
                summary.toplam_gerekli_siginak_alani_m2 += req_m2
                summary.toplam_siginacak_kisi_kapasitesi += shelter_cap
            else:
                summary.muaf_parsel_sayisi += 1

        summary.toplam_alan_m2 = round(summary.toplam_alan_m2, 2)
        summary.toplam_insaat_alani_m2 = round(summary.toplam_insaat_alani_m2, 2)
        summary.toplam_gerekli_siginak_alani_m2 = round(summary.toplam_gerekli_siginak_alani_m2, 2)

        if summary.toplam_parsel_sayisi > 0:
            summary.zorunlu_parsel_orani_yuzde = round(
                (summary.siginak_zorunlu_parsel_sayisi / summary.toplam_parsel_sayisi) * 100.0, 1
            )

        # General shelter policy (Madde 8: If estimated population >= 15000)
        est_pop = int(summary.toplam_insaat_alani_m2 // 40)
        if est_pop >= 15000 or summary.toplam_siginacak_kisi_kapasitesi >= 5000:
            summary.genel_siginak_ayrilmali_mi = True
            summary.genel_siginak_gerekcesi = (
                f"Sığınak Yönetmeliği Madde 8: Planlama alanında öngörülen toplam kapasite ({summary.toplam_siginacak_kisi_kapasitesi} kişi) ve inşaat hacmi nedeniyle imar planında müstakil 'Genel Sığınak' alanı tahsis edilmesi zorunludur."
            )
        else:
            summary.genel_siginak_ayrilmali_mi = False
            summary.genel_siginak_gerekcesi = (
                'Bölge nüfusu ve inşaat hacmi münferit bina sığınakları (serpiştirme) ile karşılanabilir düzeydedir.'
            )

        return results, summary
