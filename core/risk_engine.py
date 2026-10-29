"""PlanX MPYY Urban Transformation and Disaster Risk Prioritization Engine.

Evaluates building stock, parcel structural attributes, and geotechnical conditions
under Law No. 6306 on Transformation of Areas Under Disaster Risk
(6306 Sayılı Afet Riski Altındaki Alanların Dönüştürülmesi Hakkında Kanun ve Uygulama Yönetmeliği).

Key Evaluation Criteria:
1. Building Age / Seismic Code Period (Pre-1999, 2000-2007, 2008-2018, Post-2019).
2. Structural Construction System (B_YAPI_CINSI: Kerpiç, Ahşap, Yığma, Betonarme, Çelik).
3. Physical and Damage Condition (B_DURUM, B_HASAR_DURUMU: Yıkık, Ağır, Orta, Az, Hasarsız).
4. Storey Count and Soft Storey Indicator (Kat adedi, zemin ticari kullanımı).
5. Geotechnical Settlement Suitability (UA, ÖA, UOA - Yerleşime Uygunluk).

Calculates a composite statutory risk score (0-100) and classifies priorities:
- ACIL_DONUSUM (Score >= 75): Critical / Urgent Intervention Required
- ONCELIKLI_DONUSUM (Score 50-74): High Priority Phase 1 Transformation
- ORTA_RISK_ETAPLAMA (Score 25-49): Moderate Risk Phase 2 / Retrofitting
- DUSUK_RISK_KONTROLLU (Score < 25): Low Risk / Regular Monitoring
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from qgis.core import QgsFeature

from .attr_utils import (
    field_index_ci,
    first_raw,
    first_text,
    is_null_value,
    lower_tr,
    norm_tr,
    parse_floor_count,
    parse_int,
)


def _norm_text(val: Any) -> str:
    return norm_tr(val)


@dataclass
class BuildingRiskResult:
    feature_id: Any
    bina_kodu: str
    yapim_yili: int | None
    yapi_cinsi: str
    hasar_durumu: str
    kat_adedi: int
    yerlesime_uygunluk: str
    skor_yas: float
    skor_yapi: float
    skor_hasar: float
    skor_kat: float
    skor_jeoloji: float
    toplam_risk_skoru: float
    oncelik_grubu: str
    alan_m2: float
    insaat_alani_m2: float


@dataclass
class RiskSummary:
    toplam_bina_adedi: int = 0
    toplam_taban_alani_m2: float = 0.0
    toplam_insaat_alani_m2: float = 0.0
    ortalama_risk_skoru: float = 0.0
    acil_donusum_adedi: int = 0
    acil_donusum_alani_m2: float = 0.0
    oncelikli_donusum_adedi: int = 0
    oncelikli_donusum_alani_m2: float = 0.0
    orta_risk_adedi: int = 0
    orta_risk_alani_m2: float = 0.0
    dusuk_risk_adedi: int = 0
    dusuk_risk_alani_m2: float = 0.0
    acil_oncelikli_yuzde: float = 0.0
    oncelik_dagilimi: dict[str, int] = field(default_factory=dict)


class UrbanTransformationRiskEngine:
    """Evaluates disaster risk and urban transformation priorities under Law No. 6306."""

    @classmethod
    def evaluate_risk(
        cls,
        features: list[QgsFeature],
        reference_year: int = 2026,
    ) -> tuple[list[BuildingRiskResult], RiskSummary]:
        """Calculates multicriteria building risk scores and urban transformation priorities."""
        results: list[BuildingRiskResult] = []
        summary = RiskSummary()

        age_keys = ("yapim_yili", "bina_yasi", "B_YAS", "insaat_yili", "B_YIL", "YAPIM_YILI")
        age_delta_fields = frozenset({"bina_yasi", "b_yas"})
        struct_keys = ("B_YAPI_CINSI", "yapi_cinsi", "tasiyici_sistem", "yapi_turu", "STRUKTUR", "YapiCinsi")
        damage_keys = ("B_HASAR_DURUMU", "B_DURUM", "hasar_durumu", "fiziki_durum", "DURUM", "HasarDurumu")
        floor_keys = ("kat_adedi", "kat_sayisi", "B_KAT", "KatAdedi", "katadedi", "P_KAT", "KAT", "kat")
        geo_keys = ("yerlesime_uygunluk", "P_JEOLOJI", "ZEMIN_TIP", "jeoloji", "zemin_durumu", "UYGUNLUK", "JeolojikDurum")
        id_keys = ("bina_kodu", "B_KOD", "bina_no", "global_id", "id", "fid", "ada_parsel")

        for feat in features:
            geom = feat.geometry()
            area_m2 = round(geom.area(), 2) if geom and not geom.isEmpty() else 0.0

            # 1. Bina Kodu
            bina_kodu = first_text(feat, id_keys) or str(feat.id())

            # 2. Yapım Yılı / Yaş
            yapim_yili: int | None = None
            fields = feat.fields()
            for k in age_keys:
                idx = field_index_ci(fields, k)
                if idx >= 0 and not is_null_value(feat[idx]):
                    val = parse_int(feat[idx])
                    if val is None:
                        continue
                    is_age_col = lower_tr(k) in age_delta_fields
                    if 1800 <= val <= reference_year + 5:
                        yapim_yili = val
                        break
                    if is_age_col and 0 <= val <= 150:
                        yapim_yili = reference_year - val
                        break
                    if not is_age_col and 0 < val <= 150:
                        yapim_yili = reference_year - val
                        break

            # Age score (max 30 pts)
            skor_yas = 15.0  # default moderate
            if yapim_yili is not None:
                if yapim_yili < 1999:
                    skor_yas = 30.0  # Pre-1999 seismic code
                elif yapim_yili <= 2007:
                    skor_yas = 18.0  # 1998/2000 code
                elif yapim_yili <= 2018:
                    skor_yas = 8.0   # 2007 code
                else:
                    skor_yas = 2.0   # 2018 TBDY modern code

            # 3. Yapı Cinsi (max 25 pts)
            yapi_cinsi = first_text(feat, struct_keys)

            norm_yapi = _norm_text(yapi_cinsi)
            skor_yapi = 15.0  # default
            if any(w in norm_yapi for w in ("KERPIC", "AHSAP", "TAS", "KERPIC_YIGMA")):
                skor_yapi = 25.0
            elif "YIGMA" in norm_yapi or "BRICKET" in norm_yapi or "BRIKET" in norm_yapi or "TUGLA" in norm_yapi:
                skor_yapi = 22.0
            elif "BETONARME" in norm_yapi or "KARKAS" in norm_yapi:
                skor_yapi = 15.0
            elif any(w in norm_yapi for w in ("CELIK", "PREFABRIK", "TUNEL", "TUNEL_KALIP")):
                skor_yapi = 5.0

            # 4. Hasar / Fiziki Durum (max 25 pts)
            hasar_durumu = first_text(feat, damage_keys)

            norm_hasar = _norm_text(hasar_durumu)
            padded_hasar = f"_{norm_hasar}_"
            skor_hasar = 5.0  # default
            if any(w in norm_hasar for w in ("AGIR", "YIKIK", "ACIL_YIKILACAK", "METRUK", "HARABE", "COKUK")):
                skor_hasar = 25.0
            elif any(w in norm_hasar for w in ("HASARSIZ", "IYI", "YENI", "SAGLAM")):
                skor_hasar = 1.0
            elif any(f"_{w}_" in padded_hasar for w in ("AZ", "AZ_HASARLI", "HAFIF", "HAFIF_HASARLI")):
                skor_hasar = 8.0
            elif any(w in norm_hasar for w in ("ORTA", "HASARLI", "BAKIMSIZ", "ESKI", "KOTU")):
                skor_hasar = 16.0

            # 5. Kat Adedi ve Geometrik Zafiyet (max 10 pts)
            kat_adedi = 1
            raw_floor = first_raw(feat, floor_keys)
            parsed_floor = parse_floor_count(raw_floor)
            if parsed_floor is not None and parsed_floor >= 1:
                kat_adedi = parsed_floor

            skor_kat = 2.0
            if kat_adedi >= 8:
                skor_kat = 10.0
            elif kat_adedi >= 5:
                skor_kat = 7.0
            elif kat_adedi >= 3:
                skor_kat = 4.0

            # Extra vulnerability for high masonry
            if "YIGMA" in norm_yapi and kat_adedi >= 3:
                skor_kat = min(10.0, skor_kat + 4.0)

            # 6. Yerleşime Uygunluk / Zemin (max 10 pts)
            yerlesime_uygunluk = first_text(feat, geo_keys)

            norm_geo = _norm_text(yerlesime_uygunluk)
            padded_geo = f"_{norm_geo}_"
            skor_jeoloji = 2.0
            if "_UOA_" in padded_geo or any(w in norm_geo for w in ("UOA", "UYGUN_OLMAYAN", "HEYELAN", "FAY", "SIVILASMA", "TASKIN")):
                skor_jeoloji = 10.0
            elif "_OA_" in padded_geo or any(w in norm_geo for w in ("ONLEMLI", "ONLEM")):
                skor_jeoloji = 6.0
            elif "_UA_" in padded_geo or "UYGUN" in norm_geo:
                skor_jeoloji = 1.0

            # Total score
            toplam_risk = min(100.0, round(skor_yas + skor_yapi + skor_hasar + skor_kat + skor_jeoloji, 1))

            # Priority classification
            if toplam_risk >= 75.0:
                oncelik = "ACIL_DONUSUM"
            elif toplam_risk >= 50.0:
                oncelik = "ONCELIKLI_DONUSUM"
            elif toplam_risk >= 25.0:
                oncelik = "ORTA_RISK_ETAPLAMA"
            else:
                oncelik = "DUSUK_RISK_KONTROLLU"

            insaat_m2 = round(area_m2 * kat_adedi, 2)

            item = BuildingRiskResult(
                feature_id=feat.id(),
                bina_kodu=bina_kodu,
                yapim_yili=yapim_yili,
                yapi_cinsi=yapi_cinsi or "BELIRTILMEMIS",
                hasar_durumu=hasar_durumu or "BELIRTILMEMIS",
                kat_adedi=kat_adedi,
                yerlesime_uygunluk=yerlesime_uygunluk or "BELIRTILMEMIS",
                skor_yas=skor_yas,
                skor_yapi=skor_yapi,
                skor_hasar=skor_hasar,
                skor_kat=skor_kat,
                skor_jeoloji=skor_jeoloji,
                toplam_risk_skoru=toplam_risk,
                oncelik_grubu=oncelik,
                alan_m2=area_m2,
                insaat_alani_m2=insaat_m2,
            )
            results.append(item)

            # Update summary metrics
            summary.toplam_bina_adedi += 1
            summary.toplam_taban_alani_m2 += area_m2
            summary.toplam_insaat_alani_m2 += insaat_m2

            if oncelik == "ACIL_DONUSUM":
                summary.acil_donusum_adedi += 1
                summary.acil_donusum_alani_m2 += area_m2
            elif oncelik == "ONCELIKLI_DONUSUM":
                summary.oncelikli_donusum_adedi += 1
                summary.oncelikli_donusum_alani_m2 += area_m2
            elif oncelik == "ORTA_RISK_ETAPLAMA":
                summary.orta_risk_adedi += 1
                summary.orta_risk_alani_m2 += area_m2
            else:
                summary.dusuk_risk_adedi += 1
                summary.dusuk_risk_alani_m2 += area_m2

            summary.oncelik_dagilimi[oncelik] = summary.oncelik_dagilimi.get(oncelik, 0) + 1

        if results:
            summary.ortalama_risk_skoru = round(sum(r.toplam_risk_skoru for r in results) / len(results), 1)
            summary.toplam_taban_alani_m2 = round(summary.toplam_taban_alani_m2, 2)
            summary.toplam_insaat_alani_m2 = round(summary.toplam_insaat_alani_m2, 2)
            summary.acil_donusum_alani_m2 = round(summary.acil_donusum_alani_m2, 2)
            summary.oncelikli_donusum_alani_m2 = round(summary.oncelikli_donusum_alani_m2, 2)
            summary.orta_risk_alani_m2 = round(summary.orta_risk_alani_m2, 2)
            summary.dusuk_risk_alani_m2 = round(summary.dusuk_risk_alani_m2, 2)

            urgent_high = summary.acil_donusum_adedi + summary.oncelikli_donusum_adedi
            summary.acil_oncelikli_yuzde = round((urgent_high / len(results)) * 100.0, 1)

        return results, summary
