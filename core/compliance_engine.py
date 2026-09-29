"""PlanX MPYY Statutory Zoning Code & Parcel Buildability Engine (PAİY).

Implements statutory requirements of Turkish Planlı Alanlar İmar Yönetmeliği (PAİY):
- Madde 15: Parsel Genişlikleri, Derinlikleri ve Asgari Büyüklükler.
  - Ayrık Nizam: Asgari cephe 12.0m, asgari derinlik 18.0m, asgari alan 300m² (4 kata kadar) / 500m² (5+ kat).
  - Bitişik Nizam: Asgari cephe 6.0m, asgari derinlik 15.0m, asgari alan 150m².
  - Blok Nizam: Asgari cephe 18.0m, asgari derinlik 18.0m, asgari alan 400m².
  - İkiz Nizam: Asgari cephe 9.0m, asgari derinlik 18.0m, asgari alan 250m².
  - Serbest Nizam: Asgari cephe 20.0m, asgari derinlik 25.0m, asgari alan 600m².
- Madde 16: Parsel İfraz ve Tevhit Şartları.
  - Tevhid Zorunlu: Asgari boyutları sağlamayan parseller tek başına yapı ruhsatı alamaz.
  - İfraz Edilebilir: Alanı ve cephesi en az iki asgari parsel boyutunu aşan parseller.
- Madde 22: Yapı Yaklaşma Mesafeleri ve Taban Oturum Çekme Zarfı.
  - Ön bahçe (5m), yan bahçe (3m), arka bahçe (3m veya H/2).
"""

from dataclasses import dataclass, field
import re
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
)


def _norm(val: Any) -> str:
    text = str(val or "").strip().upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


@dataclass
class ParcelStandardRule:
    nizam: str
    min_cephe_m: float
    min_derinlik_m: float
    min_alan_m2: float


# PAİY Madde 15 Asgari Standart Tablosu
PAIY_STANDARDS: dict[str, ParcelStandardRule] = {
    "AYRIK": ParcelStandardRule("AYRIK", min_cephe_m=12.0, min_derinlik_m=18.0, min_alan_m2=300.0),
    "BITISIK": ParcelStandardRule("BITISIK", min_cephe_m=6.0, min_derinlik_m=15.0, min_alan_m2=150.0),
    "IKIZ": ParcelStandardRule("IKIZ", min_cephe_m=9.0, min_derinlik_m=18.0, min_alan_m2=250.0),
    "BLOK": ParcelStandardRule("BLOK", min_cephe_m=18.0, min_derinlik_m=18.0, min_alan_m2=400.0),
    "SERBEST": ParcelStandardRule("SERBEST", min_cephe_m=20.0, min_derinlik_m=25.0, min_alan_m2=600.0),
}


@dataclass
class ParcelComplianceResult:
    fid: int
    ada: str
    parsel: str
    alan_m2: float
    cephe_m: float
    derinlik_m: float
    nizam: str
    kat_adedi: int
    asgari_alan_m2: float
    asgari_cephe_m: float
    asgari_derinlik_m: float
    cekme_zarf_alani_m2: float
    durum: str  # 'YAPILASABILIR', 'TEVHID_ZORUNLU', 'IFRAZ_EDILEBILIR', 'CEKME_YETERSIZ'
    aciklama: str
    geometri: QgsGeometry | None = None


@dataclass
class ComplianceSummary:
    toplam_parsel_sayisi: int = 0
    yapilasabilir_sayisi: int = 0
    tevhid_zorunlu_sayisi: int = 0
    ifraz_edilebilir_sayisi: int = 0
    cekme_yetersiz_sayisi: int = 0
    uygunluk_orani_yuzde: float = 0.0
    uyarilar: list[str] = field(default_factory=list)


class ComplianceEngine:
    """PAİY zoning parcel compliance, setback viability, and subdivision/amalgamation audit engine."""

    @classmethod
    def _extract_text(cls, feat: QgsFeature, preferred_keys: tuple[str, ...]) -> str:
        fields = feat.fields()
        for k in preferred_keys:
            idx = fields.indexFromName(k)
            if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                return str(feat[idx]).strip()
        # Case-insensitive fallback
        lower_map = {f.name().lower(): f.name() for f in fields}
        for k in preferred_keys:
            if k.lower() in lower_map:
                v = feat[lower_map[k.lower()]]
                if v not in (None, "", "NULL"):
                    return str(v).strip()
        return ""

    @classmethod
    def _extract_int(cls, feat: QgsFeature, preferred_keys: tuple[str, ...], default: int = 4) -> int:
        fields = feat.fields()
        for k in preferred_keys:
            idx = fields.indexFromName(k)
            if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                try:
                    v = int(str(feat[idx]))
                    if v > 0:
                        return v
                except (ValueError, TypeError):
                    pass
        return default

    @classmethod
    def evaluate_parcels(
        cls,
        parcel_features: list[QgsFeature],
        default_nizam: str = "AYRIK",
        default_floors: int = 4,
        default_front_setback_m: float = 5.0,
        default_side_setback_m: float = 3.0,
        min_building_core_m2: float = 30.0,
        feedback: Any = None,
    ) -> tuple[list[ParcelComplianceResult], ComplianceSummary]:
        """Evaluates cadastral / zoning parcels for PAİY compliance."""
        results: list[ParcelComplianceResult] = []
        summary = ComplianceSummary()

        if not parcel_features:
            summary.uyarilar.append('Değerlendirme için parsel katmanında geometri bulunamadı.')
            return results, summary

        ada_keys = ("ADA", "ada", "ada_no", "block", "ADANO")
        parsel_keys = ("PARSEL", "parsel", "parsel_no", "lot", "PARSELNO")
        nizam_keys = ("NIZAM", "nizam", "yapi_nizami", "P_NIZAM", "uipnizam")
        kat_keys = ("KAT", "kat", "kat_adedi", "P_KAT", "bina_kat", "kat_sayisi")

        total_parcels = 0
        buildable = 0
        tevhid_req = 0
        subdivisible = 0
        setback_fail = 0

        for feat in parcel_features:
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area_m2 = geom.area()
            if area_m2 <= 0.1:
                continue

            total_parcels += 1
            fid = feat.id()
            ada = cls._extract_text(feat, ada_keys) or "-"
            parsel = cls._extract_text(feat, parsel_keys) or str(fid)

            # Determine typology
            raw_nizam = cls._extract_text(feat, nizam_keys)
            norm_n = _norm(raw_nizam)
            active_nizam = "AYRIK"
            for k in ("BITISIK", "IKIZ", "BLOK", "SERBEST", "AYRIK"):
                if k in norm_n:
                    active_nizam = k
                    break
            if not raw_nizam:
                active_nizam = default_nizam.upper()

            floors = cls._extract_int(feat, kat_keys, default=default_floors)
            rule = PAIY_STANDARDS.get(active_nizam, PAIY_STANDARDS["AYRIK"])

            min_area = rule.min_alan_m2
            if active_nizam == "AYRIK" and floors >= 5:
                min_area = 500.0  # PAİY: Ayrık nizamda 5 ve üzeri katlarda asgari 500 m2
                rule_frontage = rule.min_cephe_m + max(0, floors - 4) * 0.5
            else:
                rule_frontage = rule.min_cephe_m

            min_depth = rule.min_derinlik_m

            # Geometric dimensions using Oriented Bounding Box
            obb_res = geom.orientedMinimumBoundingBox()
            # obb_res: (geometry, area, angle, width, height)
            dim1 = round(float(obb_res[3]), 2)
            dim2 = round(float(obb_res[4]), 2)
            # Frontage is usually shorter or longer depending on street orientation;
            # in plan evaluation, frontage is typically the primary access width (min dimension in regular lots)
            cephe = min(dim1, dim2) if min(dim1, dim2) > 0 else dim1
            derinlik = max(dim1, dim2)

            # Calculate building envelope with setbacks
            # Average setback buffer
            avg_setback = (default_front_setback_m + default_side_setback_m) / 2.0
            envelope = geom.buffer(-avg_setback, 5)
            envelope_area = round(envelope.area(), 2) if (envelope and not envelope.isEmpty()) else 0.0

            # Statutory Evaluation
            reasons: list[str] = []
            durum = "YAPILASABILIR"

            # 1. Check if parcel qualifies for subdivision (İfraz Edilebilir)
            can_subdivide = (area_m2 >= 2.0 * min_area) and (cephe >= 2.0 * rule_frontage)

            # 2. Check if parcel fails minimum dimensions (Tevhid Zorunlu)
            area_deficit = area_m2 < min_area
            frontage_deficit = cephe < rule_frontage
            depth_deficit = derinlik < min_depth

            # Depth was computed but never checked, while a passing parcel is
            # told it meets "alan, cephe, derinlik ve çekme" standards.
            if area_deficit or frontage_deficit or depth_deficit:
                durum = "TEVHID_ZORUNLU"
                tevhid_req += 1
                if area_deficit:
                    reasons.append(f"Alan ({area_m2:.1f} m² < {min_area:.0f} m²) yetersiz")
                if frontage_deficit:
                    reasons.append(f"Cephe ({cephe:.1f} m < {rule_frontage:.1f} m) yetersiz")
                if depth_deficit:
                    reasons.append(f"Derinlik ({derinlik:.1f} m < {min_depth:.1f} m) yetersiz")
                aciklama = 'PAİY Madde 16: ' + ", ".join(reasons) + '. Komşu parsel ile tevhit zorunludur.'
            elif envelope_area < min_building_core_m2:
                durum = "CEKME_YETERSIZ"
                setback_fail += 1
                aciklama = (
                    f'Çekme mesafeleri ({default_front_setback_m}m ön, {default_side_setback_m}m yan) sonrası kalan yapı oturum alanı ({envelope_area:.1f} m² < {min_building_core_m2:.0f} m²) yetersizdir.'
                )
            elif can_subdivide:
                durum = "IFRAZ_EDILEBILIR"
                subdivisible += 1
                potential_lots = int(area_m2 / min_area)
                aciklama = f'PAİY Madde 15: Parsel boyutları uygun olup ~{potential_lots} müstakil imar parseline ifraz edilebilir.'
                buildable += 1
            else:
                durum = "YAPILASABILIR"
                buildable += 1
                aciklama = 'PAİY Madde 15-22: Parsel alan, cephe, derinlik ve çekme standartlarını tam karşılar. Bağımsız yapılaşabilir.'

            results.append(
                ParcelComplianceResult(
                    fid=fid,
                    ada=ada,
                    parsel=parsel,
                    alan_m2=round(area_m2, 2),
                    cephe_m=cephe,
                    derinlik_m=derinlik,
                    nizam=active_nizam,
                    kat_adedi=floors,
                    asgari_alan_m2=min_area,
                    asgari_cephe_m=rule_frontage,
                    asgari_derinlik_m=min_depth,
                    cekme_zarf_alani_m2=envelope_area,
                    durum=durum,
                    aciklama=aciklama,
                    geometri=geom,
                )
            )

        summary.toplam_parsel_sayisi = total_parcels
        summary.yapilasabilir_sayisi = buildable
        summary.tevhid_zorunlu_sayisi = tevhid_req
        summary.ifraz_edilebilir_sayisi = subdivisible
        summary.cekme_yetersiz_sayisi = setback_fail
        summary.uygunluk_orani_yuzde = round(100.0 * buildable / total_parcels, 1) if total_parcels > 0 else 100.0

        if tevhid_req > 0:
            summary.uyarilar.append(
                f'Toplam {tevhid_req} parsel PAİY asgari alan/cephe şartlarını sağlamadığı için tek başına yapı ruhsatı alamaz (Tevhid Zorunlu)!'
            )
        if setback_fail > 0:
            summary.uyarilar.append(
                f'Toplam {setback_fail} parselde çekme mesafeleri bina tabanını aşırı daraltmaktadır (Çekme Yetersiz)!'
            )

        return results, summary
