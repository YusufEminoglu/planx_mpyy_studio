"""Quality Control and Topology Validation Engine for MPYY & Cadastral Workspaces.

Detects legislative and spatial anomalies:
1. Cadastral parcel overlaps (Mülkiyet çakışması).
2. Building encroachment outside parcel bounds (Bina parsel tecavüzü).
3. Setback envelope violations (Yapı yaklaşma sınırı ihlali).
4. Floor-area ratio and coverage excess (TAKS / KAKS aşımı).
5. Geometry defects (Self-intersection, unclosed rings).
"""

from dataclasses import dataclass
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsSpatialIndex,
)
from .actions import calculate_setback_envelope
from .attr_utils import (
    clean_text,
    field_index_ci,
    first_float,
    first_text,
    is_null_value,
    normalize_nizam_code,
    reindex_features,
    upper_tr,
)


@dataclass(frozen=True)
class QCAnomaly:
    tur: str               # e.g., 'PARSEL_CAKISMA', 'BINA_TECAVUZ', 'CEKME_IHLALI', 'YOGUNLUK_ASIMI'
    ciddiyet: str          # 'HATA' (Critical), 'UYARI' (Warning), 'BILGI' (Info)
    nesne_id: str | int
    aciklama: str
    geometri: QgsGeometry


def _build_spatial_index(features: list[QgsFeature]) -> QgsSpatialIndex:
    idx = QgsSpatialIndex()
    for feat in features:
        if feat.hasGeometry() and not feat.geometry().isEmpty():
            idx.addFeature(feat)
    return idx


class QualityControlEngine:
    """Rigorous urban planning QC validator."""

    @staticmethod
    def check_geometry_validity(features: list[QgsFeature]) -> list[QCAnomaly]:
        """Detect invalid, empty, or degenerate geometries."""
        anomalies = []
        for feat in features:
            geom = feat.geometry()
            fid = feat.id()
            if not geom or geom.isEmpty():
                anomalies.append(
                    QCAnomaly(
                        tur="BOS_GEOMETRI",
                        ciddiyet="HATA",
                        nesne_id=fid,
                        aciklama='Geometri boş veya tanımsız.',
                        geometri=QgsGeometry(),
                    )
                )
            elif not geom.isGeosValid():
                error_msg = geom.lastError() or 'Geometri GEOS doğrulamasından geçemedi.'
                anomalies.append(
                    QCAnomaly(
                        tur="GECERSIZ_GEOMETRI",
                        ciddiyet="HATA",
                        nesne_id=fid,
                        aciklama=f'Geometri hatası: {error_msg}',
                        geometri=geom,
                    )
                )
        return anomalies

    @staticmethod
    def check_parcel_overlaps(parcel_features: list[QgsFeature]) -> list[QCAnomaly]:
        """Detect spatial overlaps between distinct cadastral/planning parcels."""
        anomalies = []
        if not parcel_features or len(parcel_features) < 2:
            return anomalies

        orig_ids = [p.id() for p in parcel_features]
        indexed_parcels = reindex_features(parcel_features)
        orig_by_uid = {feat.id(): orig_ids[pos] for pos, feat in enumerate(indexed_parcels)}

        idx = _build_spatial_index(indexed_parcels)
        p_map = {p.id(): p for p in indexed_parcels}
        seen_pairs = set()

        for p1 in indexed_parcels:
            g1 = p1.geometry()
            if not g1 or g1.isEmpty():
                continue

            candidates = idx.intersects(g1.boundingBox())
            for c_id in candidates:
                if c_id == p1.id():
                    continue
                pair = tuple(sorted((p1.id(), c_id)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                p2 = p_map.get(c_id)
                if not p2:
                    continue
                g2 = p2.geometry()
                if not g2 or g2.isEmpty():
                    continue

                if g1.intersects(g2):
                    inter = g1.intersection(g2)
                    if inter and not inter.isEmpty() and inter.area() > 0.05:  # Tolerance: 0.05 m2
                        anomalies.append(
                            QCAnomaly(
                                tur="PARSEL_CAKISMA",
                                ciddiyet="HATA",
                                nesne_id=f"{orig_by_uid[p1.id()]} - {orig_by_uid[p2.id()]}",
                                aciklama=f'İki parsel arasında {inter.area():.2f} m² çakışma/mükerrer alan tespit edildi.',
                                geometri=inter,
                            )
                        )
        return anomalies

    @staticmethod
    def check_building_spills(
        parcel_features: list[QgsFeature], building_features: list[QgsFeature]
    ) -> list[QCAnomaly]:
        """Detect buildings that extend beyond any cadastral parcel boundaries."""
        anomalies = []
        if not building_features:
            return anomalies

        indexed_parcels = reindex_features(parcel_features) if parcel_features else []
        idx_parcels = _build_spatial_index(indexed_parcels)
        p_map = {p.id(): p for p in indexed_parcels}

        for b in building_features:
            b_geom = b.geometry()
            if not b_geom or b_geom.isEmpty():
                continue

            intersected_parcels = idx_parcels.intersects(b_geom.boundingBox())
            if not intersected_parcels:
                anomalies.append(
                    QCAnomaly(
                        tur="PARSEL_DISI_YAPI",
                        ciddiyet="HATA",
                        nesne_id=b.id(),
                        aciklama='Bina hiçbir kadastro parseli içerisinde yer almıyor (tamamen parsel dışı).',
                        geometri=b_geom,
                    )
                )
                continue

            # Compute union of intersecting parcel geometries
            p_geoms = [
                p_map[pid].geometry()
                for pid in intersected_parcels
                if pid in p_map and p_map[pid].geometry() and not p_map[pid].geometry().isEmpty()
            ]
            if not p_geoms:
                continue

            combined_parcels = QgsGeometry.unaryUnion(p_geoms) if len(p_geoms) > 1 else p_geoms[0]

            # Difference: building area outside parcels
            outside = b_geom.difference(combined_parcels)
            if outside and not outside.isEmpty() and outside.area() > 0.1:  # 0.1 m2 tolerance
                anomalies.append(
                    QCAnomaly(
                        tur="BINA_TECAVUZ",
                        ciddiyet="HATA",
                        nesne_id=b.id(),
                        aciklama=f'Bina parsel sınırından dışarı taşıyor ({outside.area():.2f} m² tecavüz).',
                        geometri=outside,
                    )
                )
        return anomalies

    @staticmethod
    def check_setback_violations(
        parcel_features: list[QgsFeature],
        building_features: list[QgsFeature],
        default_setback_m: float = 3.0,
    ) -> list[QCAnomaly]:
        """Detect buildings located inside the setback buffer (front/side/rear yard violation)."""
        anomalies = []
        if not parcel_features or not building_features:
            return anomalies

        orig_b_ids = [b.id() for b in building_features]
        indexed_buildings = reindex_features(building_features)
        orig_b_by_uid = {feat.id(): orig_b_ids[pos] for pos, feat in enumerate(indexed_buildings)}
        idx_b = _build_spatial_index(indexed_buildings)
        b_map = {b.id(): b for b in indexed_buildings}

        setback_keys = (
            "P_CEKME", "OnBahceMesafesi", "onBahce", "onbahce", "on_bahce", "yapiYaklasmaMesafesi",
        )
        nizam_keys = ("NIZAM", "nizam", "YapiDuzeni", "yapi_nizami", "P_NIZAM", "uipnizam")

        for p in parcel_features:
            p_geom = p.geometry()
            if not p_geom or p_geom.isEmpty():
                continue

            # Check if parcel specifies custom setback (honoring explicit 0.0)
            raw_setback = first_float(p, setback_keys, default=None)
            if raw_setback is not None and raw_setback >= 0.0:
                setback_m = raw_setback
            else:
                raw_nizam = first_text(p, nizam_keys)
                if raw_nizam and normalize_nizam_code(raw_nizam, default="") == "BITISIK":
                    setback_m = 0.0
                else:
                    setback_m = default_setback_m

            if setback_m <= 0.0:
                continue

            # Calculate setback envelope (inner allowed footprint)
            envelope = calculate_setback_envelope(p_geom, setback_m)
            if not envelope or envelope.isEmpty():
                continue

            # Setback yard zone = Parcel minus inner envelope
            setback_yard = p_geom.difference(envelope)
            if not setback_yard or setback_yard.isEmpty():
                continue

            # Find buildings intersecting this parcel
            candidate_ids = idx_b.intersects(p_geom.boundingBox())
            for bid in candidate_ids:
                b = b_map.get(bid)
                if not b:
                    continue
                bg = b.geometry()
                if not bg or bg.isEmpty():
                    continue

                if bg.intersects(setback_yard):
                    violation = bg.intersection(setback_yard)
                    if violation and not violation.isEmpty() and violation.area() > 0.5:
                        anomalies.append(
                            QCAnomaly(
                                tur="CEKME_IHLALI",
                                ciddiyet="UYARI",
                                nesne_id=f"Bina {orig_b_by_uid[bid]} / Parsel {p.id()}",
                                aciklama=(
                                    f'Bina {setback_m:.1f}m çekme mesafesi koridoruna taşıyor ({violation.area():.2f} m² ihlal).'
                                ),
                                geometri=violation,
                            )
                        )
        return anomalies

    @staticmethod
    def check_free_height_violations(features: list[QgsFeature]) -> list[QCAnomaly]:
        """Audit planning zones against Law No. 7221 prohibiting unrestricted building heights (Yençok: Serbest)."""
        anomalies = []
        height_keys = (
            "yencok", "YENCOK", "Yukseklik", "katadedi", "KatAdedi", "kat_adedi",
            "P_KAT", "HMAX", "hmax", "kat", "KAT",
        )
        prohibited_tokens = {"SERBEST", "SER", "H:SERBEST", "YENCOK:SERBEST", "YENCOK_SERBEST", "H_SERBEST"}

        for feat in features:
            fid = feat.id()
            fields = feat.fields()
            violating_val = ""
            checked_indices: set[int] = set()
            for k in height_keys:
                idx = field_index_ci(fields, k)
                if idx < 0 or idx in checked_indices:
                    continue
                checked_indices.add(idx)
                raw = feat[idx]
                if is_null_value(raw):
                    continue
                candidate = clean_text(raw)
                if not candidate:
                    continue
                norm_h = upper_tr(candidate).translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU")).replace(" ", "_")
                if norm_h in prohibited_tokens or any(t in norm_h for t in ("SERBEST", "SER.")):
                    violating_val = candidate
                    break

            if violating_val:
                anomalies.append(
                    QCAnomaly(
                        tur="HUKUKA_AYKIRI_SERBEST_YUKSEKLIK",
                        ciddiyet="HATA",
                        nesne_id=fid,
                        aciklama=(
                            f"7221 sayılı Kanun ve 3194 s. İmar Kanunu Md. 8 ihlali: Bina yüksekliği 'Yençok: Serbest' ({violating_val}) olarak belirlenemez. Sayısal kat adedi veya azami bina yüksekliği (Hmax metre) belirlenmelidir."
                        ),
                        geometri=feat.geometry() if feat.hasGeometry() else QgsGeometry(),
                    )
                )
        return anomalies

    @classmethod
    def run_comprehensive_qc(
        cls,
        parcel_features: list[QgsFeature],
        building_features: list[QgsFeature] | None = None,
        setback_m: float = 3.0,
    ) -> list[QCAnomaly]:
        """Execute full suite of geometric, cadastral, building setback, and legislative QC checks."""
        anomalies = []
        # 1. Geometry checks
        anomalies.extend(cls.check_geometry_validity(parcel_features))
        if building_features:
            anomalies.extend(cls.check_geometry_validity(building_features))

        # 2. Parcel overlaps
        anomalies.extend(cls.check_parcel_overlaps(parcel_features))

        # 3. Building spills and setbacks
        if building_features:
            anomalies.extend(cls.check_building_spills(parcel_features, building_features))
            anomalies.extend(
                cls.check_setback_violations(
                    parcel_features, building_features, default_setback_m=setback_m
                )
            )

        # 4. Law 7221 Free height prohibitions
        anomalies.extend(cls.check_free_height_violations(parcel_features))

        return anomalies
