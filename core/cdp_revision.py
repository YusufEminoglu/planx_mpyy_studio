"""MPYY Articles 18-20 CDP revision and plan-change classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from qgis.core import QgsFeature, QgsGeometry


@dataclass(frozen=True)
class CDPRevisionAssessment:
    classification: str
    current_area: float
    proposed_area: float
    changed_area: float
    changed_area_ratio: float
    triggers: tuple[str, ...]
    findings: tuple[str, ...]


class CDPRevisionEngine:
    """Classifies scope from explicit statutory triggers and measured geometry change."""

    TRIGGERS = (
        "POPULATION_REQUIREMENT",
        "REGIONAL_INVESTMENT",
        "REGIONAL_LAND_USE_DEMAND",
        "CHANGED_SPATIAL_DYNAMICS",
        "MAIN_STRATEGY_CHANGED",
    )

    @classmethod
    def assess(
        cls,
        current_features: Iterable[QgsFeature],
        proposed_features: Iterable[QgsFeature],
        triggers: Mapping[str, bool],
        infrastructure_impact_documented: bool = False,
        rationale_documented: bool = False,
    ) -> CDPRevisionAssessment:
        active_triggers = tuple(
            trigger for trigger in cls.TRIGGERS if bool(triggers.get(trigger, False))
        )
        current_features = list(current_features)
        proposed_features = list(proposed_features)
        current = cls._union(current_features)
        proposed = cls._union(proposed_features)
        current_area = max(0.0, float(current.area())) if current else 0.0
        proposed_area = max(0.0, float(proposed.area())) if proposed else 0.0
        changed_geometries = []
        current_classes = cls._class_geometries(current_features)
        proposed_classes = cls._class_geometries(proposed_features)
        for code in set(current_classes) | set(proposed_classes):
            before = current_classes.get(code)
            after = proposed_classes.get(code)
            if before and after:
                changed_geometries.append(before.symDifference(after))
            elif before:
                changed_geometries.append(before)
            elif after:
                changed_geometries.append(after)
        changed_geometries = [item for item in changed_geometries if item and not item.isEmpty()]
        changed_area = (
            max(0.0, float(QgsGeometry.unaryUnion(changed_geometries).area()))
            if changed_geometries else 0.0
        )
        reference_area = max(current_area, proposed_area)
        changed_ratio = min(1.0, changed_area / reference_area) if reference_area else 0.0

        if active_triggers:
            classification = "REVISION_REVIEW"
        elif changed_area > 1e-9:
            classification = "PLAN_CHANGE_REVIEW"
        else:
            classification = "NO_SPATIAL_CHANGE"
        findings = []
        if classification != "NO_SPATIAL_CHANGE" and not rationale_documented:
            findings.append('Açık ve nesnel planlama gerekçesi belgelenmemiştir.')
        if classification != "NO_SPATIAL_CHANGE" and not infrastructure_impact_documented:
            findings.append('Altyapı etkileri ve hizmet dengesi belgelenmemiş.')
        if active_triggers:
            findings.append("One or more Article 18 whole-plan revision triggers were declared.")
        return CDPRevisionAssessment(
            classification, current_area, proposed_area, changed_area, changed_ratio,
            active_triggers, tuple(findings),
        )

    @staticmethod
    def _union(features: Iterable[QgsFeature]) -> QgsGeometry | None:
        geometries = []
        for feature in features:
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                geometry = feature.geometry()
                geometries.append(geometry.makeValid() if not geometry.isGeosValid() else geometry)
        return QgsGeometry.unaryUnion(geometries) if geometries else None

    @staticmethod
    def _class_geometries(features: Iterable[QgsFeature]) -> dict[str, QgsGeometry]:
        grouped = {}
        for feature in features:
            if not feature.hasGeometry() or feature.geometry().isEmpty():
                continue
            data = {field.name().lower(): feature[field.name()] for field in feature.fields()}
            code = ""
            for field_name in ("fonksiyon_kodu", "catalog_id", "detay_grup_kodu", "lejant_kodu"):
                if data.get(field_name) not in (None, "", "NULL"):
                    code = str(data[field_name]).strip().upper()
                    break
            code = code or "UNCLASSIFIED"
            geometry = feature.geometry()
            geometry = geometry.makeValid() if not geometry.isGeosValid() else geometry
            grouped.setdefault(code, []).append(geometry)
        return {code: QgsGeometry.unaryUnion(items) for code, items in grouped.items()}
