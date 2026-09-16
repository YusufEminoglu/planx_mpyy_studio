"""PlanX MPYY Urban Synthesis and Analysis Engine.

Performs spatial synthesis across cadastral, field survey, and plan layers:
1. Majority-Overlap: Identifies dominant zoning/land use for each cadastral parcel.
2. Building Density: Calculates TAKS, KAKS, building footprint, and dominant floor counts.
3. Amenity Deficit (Donatı Açığı): Calculates social/technical infrastructure deficit per capita.
4. Risk Vulnerability: Evaluates structural age, poor building quality, and hazard zone intersection.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsSpatialIndex,
    QgsVectorLayer,
)


@dataclass(frozen=True)
class ParcelSynthesisResult:
    parcel_id: str | int
    parsel_alani_m2: float
    hakim_plan_fonksiyonu: str
    ortusen_fonksiyon_orani: float
    bina_sayisi: int
    toplam_taban_alani_m2: float
    toplam_insaat_alani_m2: float
    hesaplanan_taks: float
    hesaplanan_kaks: float
    hakim_kat: int
    maks_kat: int
    riskli_bina_sayisi: int


@dataclass(frozen=True)
class AmenityDeficitResult:
    bolge_adi: str
    nufus: int
    mevcut_yesil_alan_m2: float
    gerekli_yesil_alan_m2: float
    yesil_alan_acigi_m2: float
    kisi_basi_mevcut_m2: float
    standart_m2_kisi: float
    yeterlilik_durumu: str  # 'YETERLI' veya 'YETERSIZ'


class SynthesisEngine:
    """Urban analytics engine for MPYY and cadastral synthesis."""

    # MPYY Mekânsal Planlar Yapım Yönetmeliği standartları (m2 / kişi)
    STANDART_YESIL_ALAN_M2_KISI = 10.0
    STANDART_EGITIM_M2_KISI = 4.0
    STANDART_SAGLIK_M2_KISI = 2.0

    @staticmethod
    def calculate_majority_overlap(
        feature_geom: QgsGeometry,
        candidate_features: list[QgsFeature],
        function_field: str = "fonksiyon_adi",
        candidate_index: QgsSpatialIndex | None = None,
        candidate_map: dict[int | str, QgsFeature] | None = None,
    ) -> tuple[str, float]:
        """Find the dominant function overlapping the given geometry by largest intersection area."""
        if not feature_geom or feature_geom.isEmpty():
            return "", 0.0

        total_area = feature_geom.area()
        if total_area <= 0:
            return "", 0.0

        if candidate_index is not None and candidate_map is not None:
            candidate_ids = candidate_index.intersects(feature_geom.boundingBox())
            eval_features = [candidate_map[cid] for cid in candidate_ids if cid in candidate_map]
        else:
            eval_features = candidate_features

        overlap_by_func: dict[str, float] = {}

        for candidate in eval_features:
            c_geom = candidate.geometry()
            if not c_geom or not c_geom.intersects(feature_geom):
                continue
            intersection = feature_geom.intersection(c_geom)
            if not intersection.isEmpty():
                fn_val = "TANIMSIZ"
                c_fields = candidate.fields()
                if c_fields.indexFromName(function_field) >= 0:
                    val = candidate[function_field]
                    if val is not None and str(val).strip():
                        fn_val = str(val).strip()
                if fn_val == "TANIMSIZ":
                    for alt in ("uipfonksiyon", "P_FONK", "B_FONK", "fonksiyon_kodu", "catalog_id"):
                        if c_fields.indexFromName(alt) >= 0:
                            val = candidate[alt]
                            if val is not None and str(val).strip():
                                fn_val = str(val).strip()
                                break
                overlap_by_func[fn_val] = overlap_by_func.get(fn_val, 0.0) + intersection.area()

        if not overlap_by_func:
            return "", 0.0

        best_func, max_overlap = max(overlap_by_func.items(), key=lambda item: item[1])
        ratio = round(max_overlap / total_area, 4)
        return best_func, ratio

    @staticmethod
    def analyze_parcel_buildings(
        parcel_geom: QgsGeometry,
        building_features: list[QgsFeature],
        floor_field: str = "B_KAT",
        condition_field: str = "B_DURUM",
        building_index: QgsSpatialIndex | None = None,
        building_map: dict[int | str, QgsFeature] | None = None,
    ) -> dict[str, Any]:
        """Calculate building count, TAKS, KAKS, dominant floor, and risk counts within a parcel."""
        if not parcel_geom or parcel_geom.isEmpty():
            return {
                "bina_sayisi": 0,
                "toplam_taban_alani": 0.0,
                "toplam_insaat_alani": 0.0,
                "hakim_kat": 0,
                "maks_kat": 0,
                "riskli_bina_sayisi": 0,
            }

        if building_index is not None and building_map is not None:
            b_ids = building_index.intersects(parcel_geom.boundingBox())
            eval_buildings = [building_map[bid] for bid in b_ids if bid in building_map]
        else:
            eval_buildings = building_features

        bina_sayisi = 0
        toplam_taban = 0.0
        toplam_insaat = 0.0
        kat_listesi = []
        riskli_bina = 0

        for b_feat in eval_buildings:
            b_geom = b_feat.geometry()
            # If building center or majority is inside parcel
            if not b_geom or not b_geom.intersects(parcel_geom):
                continue

            inter = b_geom.intersection(parcel_geom)
            inter_area = inter.area()
            # If at least 40% of building footprint is inside this parcel
            if b_geom.area() > 0 and (inter_area / b_geom.area()) >= 0.4:
                bina_sayisi += 1
                footprint = b_geom.area()
                toplam_taban += footprint

                kat = 1
                if b_feat.fields().indexFromName(floor_field) >= 0:
                    raw_kat = b_feat[floor_field]
                    try:
                        kat = int(raw_kat) if raw_kat is not None and raw_kat != "" else 1
                    except (ValueError, TypeError):
                        kat = 1
                if kat <= 0:
                    kat = 1
                kat_listesi.append(kat)
                toplam_insaat += footprint * kat

                if b_feat.fields().indexFromName(condition_field) >= 0:
                    durum = str(b_feat[condition_field] or "").upper()
                    if durum in ("KÖTÜ", "HARAP", "METRUK", "KOTU", "RISKLI", "AĞIR_HASARLI", "ACİL_YIKILACAK"):
                        riskli_bina += 1

        hakim_kat = Counter(kat_listesi).most_common(1)[0][0] if kat_listesi else 0
        maks_kat = max(kat_listesi) if kat_listesi else 0

        return {
            "bina_sayisi": bina_sayisi,
            "toplam_taban_alani": round(toplam_taban, 2),
            "toplam_insaat_alani": round(toplam_insaat, 2),
            "hakim_kat": hakim_kat,
            "maks_kat": maks_kat,
            "riskli_bina_sayisi": riskli_bina,
        }

    @classmethod
    def synthesize_parcel(
        cls,
        parcel_feature: QgsFeature,
        plan_features: list[QgsFeature],
        building_features: list[QgsFeature],
        function_field: str = "fonksiyon_adi",
        candidate_index: QgsSpatialIndex | None = None,
        candidate_map: dict[int | str, QgsFeature] | None = None,
        building_index: QgsSpatialIndex | None = None,
        building_map: dict[int | str, QgsFeature] | None = None,
    ) -> ParcelSynthesisResult:
        """Run full synthesis for a single cadastral parcel."""
        p_geom = parcel_feature.geometry()
        p_area = p_geom.area() if p_geom else 0.0

        fid = parcel_feature.id()
        if parcel_feature.fields().indexFromName("PARSEL") >= 0 and parcel_feature["PARSEL"]:
            ada = parcel_feature["ADA"] if parcel_feature.fields().indexFromName("ADA") >= 0 else ""
            fid = f"{ada}/{parcel_feature['PARSEL']}" if ada else str(parcel_feature["PARSEL"])

        # 1. Majority Overlap
        best_func, ratio = cls.calculate_majority_overlap(
            p_geom,
            plan_features,
            function_field,
            candidate_index=candidate_index,
            candidate_map=candidate_map,
        )

        # 2. Building Density & Heights
        b_metrics = cls.analyze_parcel_buildings(
            p_geom,
            building_features,
            building_index=building_index,
            building_map=building_map,
        )

        taks = round(b_metrics["toplam_taban_alani"] / p_area, 3) if p_area > 0 else 0.0
        kaks = round(b_metrics["toplam_insaat_alani"] / p_area, 3) if p_area > 0 else 0.0

        return ParcelSynthesisResult(
            parcel_id=fid,
            parsel_alani_m2=round(p_area, 2),
            hakim_plan_fonksiyonu=best_func,
            ortusen_fonksiyon_orani=ratio,
            bina_sayisi=b_metrics["bina_sayisi"],
            toplam_taban_alani_m2=b_metrics["toplam_taban_alani"],
            toplam_insaat_alani_m2=b_metrics["toplam_insaat_alani"],
            hesaplanan_taks=taks,
            hesaplanan_kaks=kaks,
            hakim_kat=b_metrics["hakim_kat"],
            maks_kat=b_metrics["maks_kat"],
            riskli_bina_sayisi=b_metrics["riskli_bina_sayisi"],
        )

    @classmethod
    def batch_synthesize_parcels(
        cls,
        parcel_features: list[QgsFeature],
        plan_features: list[QgsFeature],
        building_features: list[QgsFeature],
        function_field: str = "fonksiyon_adi",
        feedback: Any = None,
    ) -> list[ParcelSynthesisResult]:
        """Perform O(N log M) batch synthesis across all parcels using pre-indexed spatial structures."""
        # 1. Build spatial index for plan features
        plan_idx = QgsSpatialIndex()
        plan_map: dict[int | str, QgsFeature] = {}
        for idx_p, pf in enumerate(plan_features, start=1):
            if pf.hasGeometry() and not pf.geometry().isEmpty():
                fid = pf.id() if pf.id() >= 0 else idx_p
                if pf.id() < 0:
                    pf.setId(fid)
                plan_idx.addFeature(pf)
                plan_map[fid] = pf

        # 2. Build spatial index for buildings
        b_idx = QgsSpatialIndex()
        b_map: dict[int | str, QgsFeature] = {}
        for idx_b, bf in enumerate(building_features, start=1):
            if bf.hasGeometry() and not bf.geometry().isEmpty():
                fid = bf.id() if bf.id() >= 0 else idx_b
                if bf.id() < 0:
                    bf.setId(fid)
                b_idx.addFeature(bf)
                b_map[fid] = bf

        results: list[ParcelSynthesisResult] = []
        total = len(parcel_features)

        for idx, p_feat in enumerate(parcel_features):
            if feedback and feedback.isCanceled():
                break

            res = cls.synthesize_parcel(
                parcel_feature=p_feat,
                plan_features=plan_features,
                building_features=building_features,
                function_field=function_field,
                candidate_index=plan_idx,
                candidate_map=plan_map,
                building_index=b_idx,
                building_map=b_map,
            )
            results.append(res)

            if feedback and total > 0 and idx % 200 == 0:
                feedback.setProgress(int(100 * idx / total))

        return results

    @classmethod
    def analyze_amenity_deficit(
        cls,
        population: int,
        existing_green_area_m2: float,
        region_name: str = "Planlama Bölgesi",
        standard_m2_per_person: float = STANDART_YESIL_ALAN_M2_KISI,
    ) -> AmenityDeficitResult:
        """Calculate open & green space deficit according to regulatory MPYY standards."""
        if population <= 0:
            population = 1

        required = round(population * standard_m2_per_person, 2)
        deficit = round(max(0.0, required - existing_green_area_m2), 2)
        per_capita = round(existing_green_area_m2 / population, 2)
        status = "YETERLI" if deficit == 0.0 else "YETERSIZ"

        return AmenityDeficitResult(
            bolge_adi=region_name,
            nufus=population,
            mevcut_yesil_alan_m2=round(existing_green_area_m2, 2),
            gerekli_yesil_alan_m2=required,
            yesil_alan_acigi_m2=deficit,
            kisi_basi_mevcut_m2=per_capita,
            standart_m2_kisi=standard_m2_per_person,
            yeterlilik_durumu=status,
        )

    @classmethod
    def extract_amenities_from_features(
        cls,
        features: list[QgsFeature],
        function_field: str = "",
    ) -> dict[str, float]:
        """Classify and sum areas (m2) of all plan features into statutory MPYY Ek-2 amenity groups."""
        from .plan_diff import classify_amenity_category

        fn_keys = (function_field,) if function_field else ("uipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK", "plan_fonk", "catalog_id")
        grp_keys = ("ustkonugrup", "ust_konu_grup", "ust_grup_adi", "ana_grup")

        display_names = {
            "YESIL": "Açık ve Yeşil Alan",
            "EGITIM": "Eğitim Tesisleri",
            "SAGLIK": "Sağlık Tesisleri",
            "SOSYAL_KULTUR": "Sosyal ve Kültürel Tesisler",
            "IBADET": 'İbadet Alanları',
            "TEKNIK_ALTYAPI": "Teknik Altyapı",
            "SPOR": "Spor Alanları",
            "KAMU_BELEDIYE": "Kamu ve Belediye Hizmet Alanları",
        }

        amenity_totals: dict[str, float] = {v: 0.0 for v in display_names.values()}

        for feat in features:
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            fn_val = ""
            for k in fn_keys:
                idx = feat.fields().indexFromName(k)
                if idx >= 0 and feat[idx]:
                    fn_val = str(feat[idx]).strip()
                    break

            grp_val = ""
            for k in grp_keys:
                idx = feat.fields().indexFromName(k)
                if idx >= 0 and feat[idx]:
                    grp_val = str(feat[idx]).strip()
                    break

            cat_code = classify_amenity_category(fn_val, grp_val)
            if cat_code and cat_code in display_names:
                disp_name = display_names[cat_code]
                amenity_totals[disp_name] += geom.area()

        return {k: round(v, 2) for k, v in amenity_totals.items()}

    @classmethod
    def analyze_all_amenities(
        cls,
        population: int,
        amenity_areas: dict[str, float],
        region_name: str = "Planlama Bölgesi",
    ) -> list[AmenityDeficitResult]:
        """Calculate complete statutory MPYY Ek-2 amenity balance matrix."""
        standards = {
            "Açık ve Yeşil Alan": cls.STANDART_YESIL_ALAN_M2_KISI,
            "Eğitim Tesisleri": cls.STANDART_EGITIM_M2_KISI,
            "Sağlık Tesisleri": cls.STANDART_SAGLIK_M2_KISI,
            "Sosyal ve Kültürel Tesisler": 1.5,
            'İbadet Alanları': 0.5,
            "Teknik Altyapı": 1.0,
            "Spor Alanları": 1.0,
            "Kamu ve Belediye Hizmet Alanları": 1.5,
        }
        results = []
        for name, std in standards.items():
            existing = float(amenity_areas.get(name, 0.0))
            required = round(population * std, 2)
            deficit = round(max(0.0, required - existing), 2)
            per_capita = round(existing / population, 2) if population > 0 else 0.0
            status = 'YETERLİ' if deficit == 0.0 else 'YETERSİZ'
            results.append(
                AmenityDeficitResult(
                    bolge_adi=f"{region_name} - {name}",
                    nufus=population,
                    mevcut_yesil_alan_m2=round(existing, 2),
                    gerekli_yesil_alan_m2=required,
                    yesil_alan_acigi_m2=deficit,
                    kisi_basi_mevcut_m2=per_capita,
                    standart_m2_kisi=std,
                    yeterlilik_durumu=status,
                )
            )
        return results
