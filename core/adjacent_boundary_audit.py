"""MPYY Article 7 adjacent-plan boundary consistency audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from qgis.core import QgsFeature, QgsGeometry, QgsSpatialIndex, QgsWkbTypes

from .attr_utils import reindex_features


@dataclass(frozen=True)
class AdjacentBoundaryRecord:
    feature: QgsFeature
    adjacent_feature_id: str
    status: str
    minimum_distance: float
    matched_length: float
    coverage_ratio: float
    reference_code: str
    adjacent_code: str
    message: str


class AdjacentBoundaryAuditEngine:
    """Matches seam geometries and optionally compares decision codes."""

    @classmethod
    def audit(
        cls,
        reference_features: Iterable[QgsFeature],
        adjacent_features: Iterable[QgsFeature],
        tolerance: float,
        minimum_coverage: float = 0.95,
        reference_code_field: str = "",
        adjacent_code_field: str = "",
    ) -> list[AdjacentBoundaryRecord]:
        if tolerance <= 0 or not 0.0 < minimum_coverage <= 1.0:
            raise ValueError('Tolerans pozitif, kapsam oranı sıfır ile bir arasında olmalıdır.')
        reference_features = reindex_features(reference_features)
        adjacent_features = reindex_features(adjacent_features)
        adjacent_map = {}
        index = QgsSpatialIndex()
        for feature in adjacent_features:
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                adjacent_map[feature.id()] = feature
                index.addFeature(feature)
        records = []
        for reference in reference_features:
            geometry = cls._line_geometry(reference.geometry())
            if not geometry or geometry.isEmpty() or geometry.length() <= 0:
                records.append(AdjacentBoundaryRecord(
                    reference, "", "INVALID_GEOMETRY", 0.0, 0.0, 0.0, "", "",
                    'Referans sınırda ölçülebilir çizgi geometrisi yok.',
                ))
                continue
            search_box = geometry.boundingBox()
            search_box.grow(tolerance)
            candidate_ids = index.intersects(search_box)
            if not candidate_ids:
                candidate_ids = index.nearestNeighbor(geometry.boundingBox().center(), 5)
            best = None
            for feature_id in candidate_ids:
                candidate = adjacent_map[feature_id]
                candidate_geometry = cls._line_geometry(candidate.geometry())
                if not candidate_geometry or candidate_geometry.isEmpty():
                    continue
                distance = geometry.distance(candidate_geometry)
                matched = geometry.intersection(candidate_geometry.buffer(tolerance, 5)).length()
                coverage = min(1.0, max(0.0, matched / geometry.length()))
                score = (coverage, -distance)
                if best is None or score > best[0]:
                    best = (score, candidate, distance, matched, coverage)
            if best is None:
                records.append(AdjacentBoundaryRecord(
                    reference, "", "NO_MATCH", 0.0, 0.0, 0.0,
                    cls._value(reference, reference_code_field), "",
                    'Bitişik plan sınırı adayı bulunamadı.',
                ))
                continue
            _score, candidate, distance, matched, coverage = best
            reference_code = cls._value(reference, reference_code_field)
            adjacent_code = cls._value(candidate, adjacent_code_field)
            if coverage + 1e-9 < minimum_coverage:
                status = "GEOMETRY_GAP"
                message = 'Komşu sınır kapsaması, yapılandırılmış asgari değerin altında.'
            elif reference_code and adjacent_code and reference_code != adjacent_code:
                status = "CODE_CONFLICT"
                message = 'Sınır geometrisi eşleşiyor, ancak bitişik plan kararı kodları çelişiyor.'
            else:
                status = "MATCH"
                message = 'Bitişik plan sınırı geometrisi ve mevcut karar kodları tutarlı.'
            records.append(AdjacentBoundaryRecord(
                reference, str(candidate.id()), status, distance, matched, coverage,
                reference_code, adjacent_code, message,
            ))
        return records

    @staticmethod
    def _line_geometry(geometry: QgsGeometry) -> QgsGeometry | None:
        if not geometry or geometry.isEmpty():
            return None
        geom_type = int(geometry.type())
        if geom_type == 2:  # Polygon
            return geometry.boundary()
        if geom_type == 1:  # Line
            return geometry
        return None

    @staticmethod
    def _value(feature: QgsFeature, field_name: str) -> str:
        if not field_name or feature.fields().indexFromName(field_name) < 0:
            return ""
        value = feature[field_name]
        return "" if value in (None, "", "NULL") else str(value).strip().upper()
