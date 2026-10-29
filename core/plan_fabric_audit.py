"""MPYY Articles 7 and 21 plan decision fabric topology audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from qgis.core import QgsFeature, QgsGeometry, QgsSpatialIndex

from .attr_utils import reindex_features


@dataclass(frozen=True)
class PlanFabricRecord:
    feature: QgsFeature
    status: str
    feature_area: float
    overlap_area: float
    overlap_ratio: float
    conflicting_feature_ids: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class PlanFabricAuditResult:
    records: tuple[PlanFabricRecord, ...]
    gap_geometry: QgsGeometry | None
    gap_area: float
    overlap_feature_count: int
    invalid_feature_count: int


class PlanFabricAuditEngine:
    """Finds internal polygon overlaps and uncovered areas inside a plan boundary."""

    @classmethod
    def audit(
        cls,
        decision_features: Iterable[QgsFeature],
        boundary_features: Iterable[QgsFeature] = (),
        area_tolerance: float = 0.01,
    ) -> PlanFabricAuditResult:
        if area_tolerance < 0:
            raise ValueError('Alan toleransı negatif olamaz.')
        features = reindex_features(decision_features)
        feature_map = {}
        geometries = {}
        index = QgsSpatialIndex()
        invalid_ids = set()
        for feature in features:
            geometry = feature.geometry()
            if not geometry or geometry.isEmpty() or geometry.area() <= 0:
                invalid_ids.add(feature.id())
                continue
            if not geometry.isGeosValid():
                geometry = geometry.makeValid()
            if not geometry or geometry.isEmpty() or geometry.area() <= 0:
                invalid_ids.add(feature.id())
                continue
            feature_map[feature.id()] = feature
            geometries[feature.id()] = geometry
            indexed = QgsFeature(feature)
            indexed.setGeometry(geometry)
            index.addFeature(indexed)

        records = []
        for feature in features:
            if feature.id() in invalid_ids:
                records.append(PlanFabricRecord(
                    feature, "INVALID_GEOMETRY", 0.0, 0.0, 0.0, (),
                    'Karar nesnesinin geçerli ve ölçülebilir poligon geometrisi yok.',
                ))
                continue
            geometry = geometries[feature.id()]
            intersections = []
            conflicts = []
            for candidate_id in index.intersects(geometry.boundingBox()):
                if candidate_id == feature.id():
                    continue
                intersection = geometry.intersection(geometries[candidate_id])
                if intersection and not intersection.isEmpty() and intersection.area() > area_tolerance:
                    intersections.append(intersection)
                    conflicts.append(str(candidate_id))
            overlap_area = (
                max(0.0, float(QgsGeometry.unaryUnion(intersections).area()))
                if intersections else 0.0
            )
            feature_area = max(0.0, float(geometry.area()))
            status = "OVERLAP" if overlap_area > area_tolerance else "CLEAR"
            records.append(PlanFabricRecord(
                feature, status, feature_area, overlap_area,
                min(1.0, overlap_area / feature_area) if feature_area else 0.0,
                tuple(sorted(conflicts)),
                'Karar geometrisi başka bir plan poligonu ile çakışmaktadır.'
                if status == "OVERLAP" else 'Alan toleransını aşan iç çakışma yoktur.',
            ))

        decision_union = QgsGeometry.unaryUnion(list(geometries.values())) if geometries else None
        boundary_geometries = [
            feature.geometry().makeValid() if not feature.geometry().isGeosValid() else feature.geometry()
            for feature in boundary_features
            if feature.hasGeometry() and not feature.geometry().isEmpty()
        ]
        boundary_union = QgsGeometry.unaryUnion(boundary_geometries) if boundary_geometries else None
        gap = None
        if boundary_union:
            gap = boundary_union.difference(decision_union) if decision_union else boundary_union
            if not gap or gap.isEmpty() or gap.area() <= area_tolerance:
                gap = None
        record_tuple = tuple(records)
        return PlanFabricAuditResult(
            record_tuple, gap, max(0.0, float(gap.area())) if gap else 0.0,
            sum(item.status == "OVERLAP" for item in record_tuple),
            sum(item.status == "INVALID_GEOMETRY" for item in record_tuple),
        )
