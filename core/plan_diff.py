"""PlanX MPYY Plan Revision and Equivalent Area Analysis Engine (Madde 26).

Implements statutory requirements of Mekânsal Planlar Yapım Yönetmeliği:
- Madde 26: "İmar planında yer alan bir sosyal ve teknik altyapı alanının kaldırılabilmesi
  veya küçültülebilmesi ancak bu tesisin hizmet edeceği etki alanı içinde eşdeğer bir
  alanın ayrılması suretiyle yapılabilir."

Performs geometric overlay between Current Plan (Yürürlükteki Plan) and Revised Plan
(Öneri Plan Değişikliği / Tadilat), identifying:
1. Korunan Alanlar (Identical zoning maintained)
2. Fonksiyon Değişiklikleri (Zoning changes between development classes)
3. Kaldırılan Donatılar (Amenity removed or reduced in size)
4. Yeni Önerilen Donatılar (New amenity introduced)
5. Equivalent Area Verification: Evaluates whether replacement amenities exist within
   the specified service radius (e.g. 500m walking distance).
"""

from dataclasses import dataclass, field
import re
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsSpatialIndex,
    QgsRectangle,
)

from .attr_utils import extract_plan_function, norm_tr, reindex_features


def _norm(val: Any) -> str:
    return norm_tr(val)


DONATI_KEYWORDS = {
    "YESIL": (
        "PARK", "COCUK_BAHCESI", "OYUN_ALANI", "REKREASYON", "MEYDAN",
        "BOTANIK", "MESIRE", "AGACLANDIRILACAK", "YESIL_ALAN", "ARBORETUM",
        "PASIF_YESIL", "KENT_PARKI",
    ),
    "EGITIM": (
        "ANAOKULU", "KRES", "ILKOKUL", "ORTAOKUL", "LISE", "EGITIM",
        "TEMEL_EGITIM", "MESLEK_LISESI", "OZEL_EGITIM", "OKUL", "KAMPUS",
    ),
    "SAGLIK": (
        "SAGLIK", "AILE_SAGLIGI", "ASM", "HASTANE", "DISPANSER", "POLIKLINIK",
        "SAGLIK_OCAGI", "SAGLIK_TESISI",
    ),
    "SOSYAL_KULTUR": (
        "SOSYAL", "KULTUR", "KULTUREL", "KUTUPHANE", "MUZE", "YASLI_BAKIMEVI",
        "HUZUREVI", "SEFKAT_EVI", "SERGI", "YURT", "GENCLIK_MERKEZI", "TOPLUM_MERKEZI",
    ),
    "IBADET": (
        "IBADET", "CAMI", "MESCIT", "CEMEVI", "KILISE", "SINAGOG", "HAVRA", "DINI",
    ),
    "SPOR": (
        "SPOR", "STADYUM", "KAPALI_SPOR", "HIPODROM", "YUZME_HAVUZU", "SAHA",
    ),
    "TEKNIK_ALTYAPI": (
        "TEKNIK_ALTYAPI", "TRAFO", "SU_DEPOSU", "ARITMA", "TERFI", "TELEKOM",
        "KATI_ATIK", "REGULATOR", "DOGALGAZ_DAGITIM", "ELEKTRONIK_HABERLESME",
        "ENERJI_DEPOLAMA", "AFET_LOJISTIK",
    ),
    "KAMU_BELEDIYE": (
        "BHA", "BELEDIYE_HIZMET", "KHA", "KAMU_HIZMET", "RESMI_KURUM", "IDARI_TESIS",
    ),
}


def classify_amenity_category(function_name: str, group_name: str = "") -> str | None:
    """Returns the statutory amenity category name if the function is public infrastructure, or None."""
    combined = f"{_norm(function_name)}_{_norm(group_name)}"
    for cat_name, keywords in DONATI_KEYWORDS.items():
        for kw in keywords:
            if f"_{kw}_" in f"_{combined}_" or combined == kw:
                return cat_name
    return None


@dataclass
class PlanDiffFeature:
    geometri: QgsGeometry
    alan_m2: float
    onceki_fonk: str
    onceki_grup: str
    onceki_donati_kodu: str | None
    yeni_fonk: str
    yeni_grup: str
    yeni_donati_kodu: str | None
    degisim_turu: str  # 'KORUNAN', 'FONKSIYON_DEGISIMI', 'DONATI_KALDIRILDI', 'YENI_DONATI_EKLENDI'
    esdeger_alan_uygun: bool = False
    aciklama: str = ""


@dataclass
class PlanDiffSummary:
    toplam_alan_m2: float = 0.0
    korunan_alan_m2: float = 0.0
    degisen_alan_m2: float = 0.0
    kaldirilan_donati_m2: float = 0.0
    yeni_eklenen_donati_m2: float = 0.0
    net_donati_degisimi_m2: float = 0.0
    madde_26_uygunlugu: bool = True
    kategori_bilancosu: dict[str, dict[str, float]] = field(default_factory=dict)
    uyarilar: list[str] = field(default_factory=list)


class PlanRevisionDiffEngine:
    """Spatial overlay and planning legislation engine for plan amendments (Madde 26)."""

    @staticmethod
    def _extract_field(feat: QgsFeature, preferred_names: tuple[str, ...]) -> str:
        for name in preferred_names:
            idx = feat.fields().indexFromName(name)
            if idx >= 0:
                val = feat[idx]
                if val not in (None, "", "NULL"):
                    return str(val).strip()
        return ""

    @classmethod
    def evaluate_revision(
        cls,
        current_features: list[QgsFeature],
        revised_features: list[QgsFeature],
        service_radius_m: float = 500.0,
        feedback: Any = None,
    ) -> tuple[list[PlanDiffFeature], PlanDiffSummary]:
        """Performs spatial intersection diff between two planning stages."""
        diff_features: list[PlanDiffFeature] = []
        summary = PlanDiffSummary()

        if not current_features or not revised_features:
            return diff_features, summary

        current_features = reindex_features(current_features)
        revised_features = reindex_features(revised_features)

        # 1. Build spatial index for revised and current features
        rev_index = QgsSpatialIndex()
        rev_map: dict[int, QgsFeature] = {}
        for rf in revised_features:
            if rf.hasGeometry() and not rf.geometry().isEmpty():
                rev_index.addFeature(rf)
                rev_map[rf.id()] = rf

        curr_index = QgsSpatialIndex()
        curr_map: dict[int, QgsFeature] = {}
        for cf in current_features:
            if cf.hasGeometry() and not cf.geometry().isEmpty():
                curr_index.addFeature(cf)
                curr_map[cf.id()] = cf

        # Track added amenities for equivalent area proximity lookups
        added_amenity_geoms: list[tuple[str, QgsGeometry, float]] = []

        grp_keys = ("ustkonugrup", "ust_konu_grup", "ust_grup_adi", "ana_grup")
        total_curr = len(current_features)
        # 2. Overlay each current feature against intersecting revised features
        for idx, cf in enumerate(current_features):
            if feedback and feedback.isCanceled():
                break

            c_geom = cf.geometry()
            if not c_geom or c_geom.isEmpty():
                continue

            c_fonk = extract_plan_function(cf) or "BELIRTILMEMIS"
            c_grp = cls._extract_field(cf, grp_keys)
            c_donati = classify_amenity_category(c_fonk, c_grp)

            candidate_ids = rev_index.intersects(c_geom.boundingBox())
            if not candidate_ids:
                # Completely uncovered in revision -> Treated as removed
                area_m2 = round(c_geom.area(), 2)
                turu = "DONATI_KALDIRILDI" if c_donati else "FONKSIYON_DEGISIMI"
                diff_features.append(
                    PlanDiffFeature(
                        geometri=c_geom,
                        alan_m2=area_m2,
                        onceki_fonk=c_fonk,
                        onceki_grup=c_grp,
                        onceki_donati_kodu=c_donati,
                        yeni_fonk="PLAN_DISI",
                        yeni_grup="",
                        yeni_donati_kodu=None,
                        degisim_turu=turu,
                        esdeger_alan_uygun=False,
                        aciklama='Yeni planda kapsam dışı bırakıldı.',
                    )
                )
                continue

            # Intersect with all candidates
            rem_c = QgsGeometry(c_geom)
            for r_id in candidate_ids:
                rf = rev_map[r_id]
                r_geom = rf.geometry()
                if not r_geom or not c_geom.intersects(r_geom):
                    continue

                inter = c_geom.intersection(r_geom)
                if not inter or inter.isEmpty() or inter.area() < 0.1:
                    continue

                if not rem_c.isEmpty():
                    rem_c = rem_c.difference(r_geom)

                inter_area = round(inter.area(), 2)
                r_fonk = extract_plan_function(rf) or "BELIRTILMEMIS"
                r_grp = cls._extract_field(rf, grp_keys)
                r_donati = classify_amenity_category(r_fonk, r_grp)

                # Determine change type
                if _norm(c_fonk) == _norm(r_fonk):
                    degisim = "KORUNAN"
                    aciklama = 'Fonksiyon aynı şekilde korunmuştur.'
                elif c_donati and not r_donati:
                    degisim = "DONATI_KALDIRILDI"
                    aciklama = f'MPYY Madde 26: {c_donati} donatısı kaldırılmıştır. Eşdeğer alan ayrılması yasal zorunluluktur.'
                elif not c_donati and r_donati:
                    degisim = "YENI_DONATI_EKLENDI"
                    aciklama = f'Yeni {r_donati} donatısı kazandırılmıştır.'
                    added_amenity_geoms.append((r_donati, inter, inter_area))
                elif c_donati and r_donati and c_donati != r_donati:
                    degisim = "FONKSIYON_DEGISIMI"
                    aciklama = f'Donatı türü değişimi: {c_donati} → {r_donati}'
                else:
                    degisim = "FONKSIYON_DEGISIMI"
                    aciklama = f'Gelişme/çalışma fonksiyonu değişimi: {c_fonk} → {r_fonk}'

                diff_features.append(
                    PlanDiffFeature(
                        geometri=inter,
                        alan_m2=inter_area,
                        onceki_fonk=c_fonk,
                        onceki_grup=c_grp,
                        onceki_donati_kodu=c_donati,
                        yeni_fonk=r_fonk,
                        yeni_grup=r_grp,
                        yeni_donati_kodu=r_donati,
                        degisim_turu=degisim,
                        esdeger_alan_uygun=False,  # Evaluated in pass 2
                        aciklama=aciklama,
                    )
                )

            # Part of current feature outside all revised features
            if not rem_c.isEmpty() and rem_c.area() >= 0.1:
                rem_area = round(rem_c.area(), 2)
                turu = "DONATI_KALDIRILDI" if c_donati else "FONKSIYON_DEGISIMI"
                diff_features.append(
                    PlanDiffFeature(
                        geometri=rem_c,
                        alan_m2=rem_area,
                        onceki_fonk=c_fonk,
                        onceki_grup=c_grp,
                        onceki_donati_kodu=c_donati,
                        yeni_fonk="PLAN_DISI",
                        yeni_grup="",
                        yeni_donati_kodu=None,
                        degisim_turu=turu,
                        esdeger_alan_uygun=False,
                        aciklama='Yeni planda kapsam dışı bırakıldı.',
                    )
                )

            if feedback and total_curr > 0 and idx % 100 == 0:
                feedback.setProgress(int(50 * idx / total_curr))

        # 2b. Detect areas introduced in revised plan that were not in current plan (İlave Plan)
        for rf in revised_features:
            if feedback and feedback.isCanceled():
                break
            r_geom = rf.geometry()
            if not r_geom or r_geom.isEmpty():
                continue

            r_fonk = extract_plan_function(rf) or "BELIRTILMEMIS"
            r_grp = cls._extract_field(rf, grp_keys)
            r_donati = classify_amenity_category(r_fonk, r_grp)

            candidate_c_ids = curr_index.intersects(r_geom.boundingBox())
            if not candidate_c_ids:
                area_m2 = round(r_geom.area(), 2)
                turu = "YENI_DONATI_EKLENDI" if r_donati else "FONKSIYON_DEGISIMI"
                aciklama = f'Yeni {r_donati} donatısı kazandırılmıştır (İlave Plan).' if r_donati else 'Yeni planlama alanı (İlave Plan).'
                diff_features.append(
                    PlanDiffFeature(
                        geometri=r_geom,
                        alan_m2=area_m2,
                        onceki_fonk="PLAN_DISI",
                        onceki_grup="",
                        onceki_donati_kodu=None,
                        yeni_fonk=r_fonk,
                        yeni_grup=r_grp,
                        yeni_donati_kodu=r_donati,
                        degisim_turu=turu,
                        esdeger_alan_uygun=True,
                        aciklama=aciklama,
                    )
                )
                if r_donati:
                    added_amenity_geoms.append((r_donati, r_geom, area_m2))
                continue

            rem_r = QgsGeometry(r_geom)
            for c_id in candidate_c_ids:
                cg = curr_map[c_id].geometry()
                if cg and rem_r.intersects(cg):
                    rem_r = rem_r.difference(cg)
                    if rem_r.isEmpty() or rem_r.area() < 0.1:
                        break

            if not rem_r.isEmpty() and rem_r.area() >= 0.1:
                area_m2 = round(rem_r.area(), 2)
                turu = "YENI_DONATI_EKLENDI" if r_donati else "FONKSIYON_DEGISIMI"
                aciklama = f'Yeni {r_donati} donatısı kazandırılmıştır (İlave Plan).' if r_donati else 'Yeni planlama alanı (İlave Plan).'
                diff_features.append(
                    PlanDiffFeature(
                        geometri=rem_r,
                        alan_m2=area_m2,
                        onceki_fonk="PLAN_DISI",
                        onceki_grup="",
                        onceki_donati_kodu=None,
                        yeni_fonk=r_fonk,
                        yeni_grup=r_grp,
                        yeni_donati_kodu=r_donati,
                        degisim_turu=turu,
                        esdeger_alan_uygun=True,
                        aciklama=aciklama,
                    )
                )
                if r_donati:
                    added_amenity_geoms.append((r_donati, rem_r, area_m2))

        # 3. Pass 2: Equivalent Area (Madde 26) Service Radius Evaluation
        # Pre-index added amenities for O(log M) proximity lookups
        added_amenity_index = QgsSpatialIndex()
        added_amenity_map: dict[int, tuple[str, QgsGeometry, float]] = {}
        for idx_a, (a_cat, a_geom, a_area) in enumerate(added_amenity_geoms):
            if a_geom and not a_geom.isEmpty():
                a_feat = QgsFeature(idx_a)
                a_feat.setGeometry(a_geom)
                added_amenity_index.addFeature(a_feat)
                added_amenity_map[idx_a] = (a_cat, a_geom, a_area)

        for item in diff_features:
            if item.degisim_turu == "DONATI_KALDIRILDI" and item.onceki_donati_kodu:
                req_cat = item.onceki_donati_kodu
                req_area = item.alan_m2

                # Look for matching added amenities within service_radius_m via bounding box search
                found_equivalent_area = 0.0
                search_box = item.geometri.boundingBox()
                search_box.grow(service_radius_m)
                candidate_a_ids = added_amenity_index.intersects(search_box)

                for aid in candidate_a_ids:
                    added_cat, added_geom, added_area = added_amenity_map[aid]
                    if added_cat == req_cat:
                        dist = item.geometri.distance(added_geom)
                        if dist <= service_radius_m:
                            found_equivalent_area += added_area

                if found_equivalent_area >= (req_area * 0.95):  # 95% threshold for geometric rounding
                    item.esdeger_alan_uygun = True
                    item.aciklama += f' ({int(service_radius_m)}m etki alanında {round(found_equivalent_area, 1)} m² eşdeğer alan sağlandı - UYGUN)'
                else:
                    item.esdeger_alan_uygun = False
                    item.aciklama += f' (DİKKAT: {int(service_radius_m)}m etki alanında yeterli eşdeğer alan tespit edilemedi - YETERSİZ)'

        # 4. Compute overall statistics
        summary.toplam_alan_m2 = round(sum(f.alan_m2 for f in diff_features), 2)
        summary.korunan_alan_m2 = round(sum(f.alan_m2 for f in diff_features if f.degisim_turu == "KORUNAN"), 2)
        summary.degisen_alan_m2 = round(sum(f.alan_m2 for f in diff_features if f.degisim_turu != "KORUNAN"), 2)
        summary.kaldirilan_donati_m2 = round(sum(f.alan_m2 for f in diff_features if f.degisim_turu == "DONATI_KALDIRILDI"), 2)
        summary.yeni_eklenen_donati_m2 = round(sum(f.alan_m2 for f in diff_features if f.degisim_turu == "YENI_DONATI_EKLENDI"), 2)
        summary.net_donati_degisimi_m2 = round(summary.yeni_eklenen_donati_m2 - summary.kaldirilan_donati_m2, 2)

        # Unfulfilled equivalent areas
        unfulfilled = [f for f in diff_features if f.degisim_turu == "DONATI_KALDIRILDI" and not f.esdeger_alan_uygun]
        if unfulfilled:
            summary.madde_26_uygunlugu = False
            summary.uyarilar.append(
                f'MPYY Madde 26 İhlali: Toplam {len(unfulfilled)} parçada ({round(sum((u.alan_m2 for u in unfulfilled)), 1)} m²) kaldırılan sosyal ve teknik altyapı alanına karşılık {int(service_radius_m)}m etki alanında eşdeğer alan ayrılmamıştır!'
            )
        else:
            summary.madde_26_uygunlugu = True

        return diff_features, summary
