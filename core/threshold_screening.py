"""MPYY Article 22 spatial threshold overlay screening."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from qgis.core import QgsFeature, QgsGeometry, QgsSpatialIndex

from .attr_utils import reindex_features


@dataclass(frozen=True)
class ThresholdScreeningRecord:
    feature: QgsFeature
    status: str
    proposal_area: float
    overlap_area: float
    overlap_ratio: float
    category_ratios: dict[str, float]
    categories: tuple[str, ...]
    message: str


class ThresholdScreeningEngine:
    """Measures proposal intersections without making a legal suitability decision."""

    CATEGORIES = (
        "GEOLOGY_HAZARD",
        "FLOOD_HYDROLOGY",
        "PROTECTED_AREA",
        "AGRICULTURE_FOREST",
        "WATER_BASIN",
        "COAST_INFRASTRUCTURE",
    )

    @classmethod
    def screen(
        cls,
        proposal_features: Iterable[QgsFeature],
        constraints: Mapping[str, Iterable[QgsFeature]],
        review_ratio: float = 0.0,
    ) -> list[ThresholdScreeningRecord]:
        if not 0.0 <= float(review_ratio) <= 1.0:
            raise ValueError('İnceleme oranı sıfır ile bir arasında olmalıdır.')

        stores = {}
        for raw_category, features in constraints.items():
            category = str(raw_category).upper()
            if category not in cls.CATEGORIES:
                raise ValueError('Bilinmeyen eşik kategorisi: ' + category)
            reindexed_constraints = reindex_features(features)
            feature_map = {}
            index = QgsSpatialIndex()
            for feature in reindexed_constraints:
                if feature.hasGeometry() and not feature.geometry().isEmpty():
                    feature_map[feature.id()] = feature
                    index.addFeature(feature)
            stores[category] = (index, feature_map)

        records = []
        for feature in reindex_features(proposal_features):
            geometry = feature.geometry()
            if not geometry or geometry.isEmpty():
                records.append(ThresholdScreeningRecord(
                    feature, "INVALID_GEOMETRY", 0.0, 0.0, 0.0, {}, (),
                    'Öneri geometrisi boştur; eşik taraması tamamlanamadı.',
                ))
                continue
            if not geometry.isGeosValid():
                geometry = geometry.makeValid()
            proposal_area = max(0.0, float(geometry.area()))
            if proposal_area <= 0.0:
                records.append(ThresholdScreeningRecord(
                    feature, "INVALID_GEOMETRY", proposal_area, 0.0, 0.0, {}, (),
                    'Önerinin ölçülebilir poligon alanı olmalıdır.',
                ))
                continue

            category_intersections = {}
            all_intersections = []
            for category, (index, feature_map) in stores.items():
                intersections = []
                for feature_id in index.intersects(geometry.boundingBox()):
                    constraint_geometry = feature_map[feature_id].geometry()
                    if not constraint_geometry.isGeosValid():
                        constraint_geometry = constraint_geometry.makeValid()
                    if not geometry.intersects(constraint_geometry):
                        continue
                    intersection = geometry.intersection(constraint_geometry)
                    if intersection and not intersection.isEmpty():
                        intersections.append(intersection)
                        all_intersections.append(intersection)
                if intersections:
                    dissolved = QgsGeometry.unaryUnion(intersections)
                    category_intersections[category] = max(0.0, float(dissolved.area()))

            if all_intersections:
                overlap_area = min(
                    proposal_area,
                    max(0.0, float(QgsGeometry.unaryUnion(all_intersections).area())),
                )
            else:
                overlap_area = 0.0
            ratios = {
                category: min(1.0, area / proposal_area)
                for category, area in category_intersections.items()
            }
            categories = tuple(sorted(
                category for category, ratio in ratios.items()
                if ratio > float(review_ratio) + 1e-12
            ))
            ratio = min(1.0, overlap_area / proposal_area)
            if categories:
                status = "REVIEW_REQUIRED"
                message = (
                    'Öneri 22. madde eşik katmanlarıyla kesişiyor; kaydedilen örtüşmeler planlama ve uzman incelemesi gerektirir.'
                )
            else:
                status = "CLEAR_SCREENING"
                message = 'Yapılandırılmış eşik çakışmalarının hiçbiri inceleme oranını aşmadı.'
            records.append(ThresholdScreeningRecord(
                feature, status, proposal_area, overlap_area, ratio, ratios, categories, message,
            ))
        return records
