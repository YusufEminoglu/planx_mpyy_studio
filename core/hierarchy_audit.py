"""Spatial and explicit-code consistency checks across MPYY plan levels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from qgis.core import QgsFeature, QgsGeometry, QgsSpatialIndex, QgsWkbTypes

from .plan_stage_audit import PLAN_LEVELS, PlanStageAuditEngine


@dataclass(frozen=True)
class HierarchyAuditRecord:
    child_feature: QgsFeature
    child_id: str
    parent_id: str
    coverage_ratio: float
    linkage_status: str
    message: str


class PlanHierarchyAuditEngine:
    """Checks lower plan decisions against an upper-level spatial decision layer."""

    @classmethod
    def audit(
        cls,
        parent_features: Iterable[QgsFeature],
        child_features: Iterable[QgsFeature],
        parent_level: str,
        child_level: str,
        minimum_coverage: float = 0.99,
    ) -> list[HierarchyAuditRecord]:
        parent_key = str(parent_level).upper()
        child_key = str(child_level).upper()
        if parent_key not in PLAN_LEVELS or child_key not in PLAN_LEVELS:
            raise ValueError('Plan kademeleri MSP, ÇDP, NİP veya UİP olmalıdır.')
        if PLAN_LEVELS.index(parent_key) >= PLAN_LEVELS.index(child_key):
            raise ValueError('Üst plan, alt plana göre daha üst bir kademede olmalıdır.')
        if not 0.0 < float(minimum_coverage) <= 1.0:
            raise ValueError('En az kapsam oranı sıfırdan büyük ve en çok bir olmalıdır.')

        parent_map: dict[int, QgsFeature] = {}
        index = QgsSpatialIndex()
        for parent in parent_features:
            if parent.hasGeometry() and not parent.geometry().isEmpty():
                parent_map[parent.id()] = parent
                index.addFeature(parent)

        records = []
        for child in child_features:
            geometry = child.geometry()
            child_data = cls._mapping(child)
            child_id = str(cls._first(child_data, "global_id", "plan_id") or child.id())
            if not geometry or geometry.isEmpty():
                records.append(HierarchyAuditRecord(
                    child, child_id, "", 0.0, "OUTSIDE", 'Alt kararın geometrisi yok.'
                ))
                continue
            total_measure = cls._measure(geometry)
            covered_measure = 0.0
            dominant_measure = 0.0
            dominant_parent = None
            for parent_id in index.intersects(geometry.boundingBox()):
                parent = parent_map[parent_id]
                parent_geometry = parent.geometry()
                if not geometry.intersects(parent_geometry):
                    continue
                intersection = geometry.intersection(parent_geometry)
                measure = cls._measure(intersection)
                covered_measure += measure
                if measure > dominant_measure:
                    dominant_measure = measure
                    dominant_parent = parent
            coverage = min(1.0, covered_measure / total_measure) if total_measure > 0 else 0.0
            if dominant_parent is None or coverage + 1e-9 < minimum_coverage:
                records.append(HierarchyAuditRecord(
                    child, child_id, "", coverage, "OUTSIDE",
                    "Child decision is not sufficiently covered by the upper plan.",
                ))
                continue

            parent_data = cls._mapping(dominant_parent)
            parent_identifier = str(
                cls._first(parent_data, "global_id", "plan_id", "fonksiyon_kodu", "catalog_id")
                or dominant_parent.id()
            )
            upper_link = PlanStageAuditEngine.normalize(cls._first(child_data, "ust_grup_kodu"))
            parent_codes = {
                PlanStageAuditEngine.normalize(cls._first(parent_data, name))
                for name in ("fonksiyon_kodu", "catalog_id", "detay_grup_kodu", "lejant_kodu")
            } - {""}
            if upper_link and parent_codes and upper_link not in parent_codes:
                status = "CONFLICT"
                message = "Explicit upper-group code does not match the dominant upper-plan decision."
            elif not upper_link:
                status = "UNLINKED"
                message = 'Mekânsal kapsama geçerli, ancak alt kararın açık ust_grup_kodu bağlantısı yok.'
            else:
                status = "MATCH"
                message = 'Mekânsal kapsama ve açık üst plan bağlantısı tutarlı.'
            records.append(HierarchyAuditRecord(
                child, child_id, parent_identifier, coverage, status, message
            ))
        return records

    @staticmethod
    def _measure(geometry: QgsGeometry) -> float:
        geometry_type = QgsWkbTypes.geometryType(geometry.wkbType())
        if geometry_type == QgsWkbTypes.GeometryType.PolygonGeometry:
            return max(0.0, float(geometry.area()))
        if geometry_type == QgsWkbTypes.GeometryType.LineGeometry:
            return max(0.0, float(geometry.length()))
        return 1.0 if geometry and not geometry.isEmpty() else 0.0

    @staticmethod
    def _mapping(feature: QgsFeature) -> dict[str, Any]:
        return {field.name().lower(): feature[field.name()] for field in feature.fields()}

    @staticmethod
    def _first(data: dict[str, Any], *names: str) -> Any:
        for name in names:
            value = data.get(name.lower())
            if value not in (None, "", "NULL"):
                return value
        return None
