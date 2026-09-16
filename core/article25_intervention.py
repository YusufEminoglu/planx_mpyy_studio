"""MPYY Article 25 plan revision and addition classifier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from qgis.core import QgsFeature, QgsGeometry

from .cdp_revision import CDPRevisionEngine


@dataclass(frozen=True)
class Article25Assessment:
    classification: str
    current_area: float
    proposed_area: float
    changed_area: float
    added_area: float
    removed_area: float
    addition_contiguous: bool
    findings: tuple[str, ...]


class Article25InterventionEngine:
    @classmethod
    def assess(
        cls,
        current_features: Iterable[QgsFeature],
        proposed_features: Iterable[QgsFeature],
        declarations: Mapping[str, bool],
        adjacency_tolerance: float = 0.01,
    ) -> Article25Assessment:
        if adjacency_tolerance < 0:
            raise ValueError('Bitişiklik toleransı negatif olamaz.')
        current_features = list(current_features)
        proposed_features = list(proposed_features)
        current = CDPRevisionEngine._union(current_features)
        proposed = CDPRevisionEngine._union(proposed_features)
        current_area = max(0.0, float(current.area())) if current else 0.0
        proposed_area = max(0.0, float(proposed.area())) if proposed else 0.0
        added = proposed.difference(current) if current and proposed else proposed
        removed = current.difference(proposed) if current and proposed else current
        added_area = max(0.0, float(added.area())) if added else 0.0
        removed_area = max(0.0, float(removed.area())) if removed else 0.0
        changed_parts = []
        current_classes = CDPRevisionEngine._class_geometries(current_features)
        proposed_classes = CDPRevisionEngine._class_geometries(proposed_features)
        for code in set(current_classes) | set(proposed_classes):
            before = current_classes.get(code)
            after = proposed_classes.get(code)
            changed_parts.append(
                before.symDifference(after) if before and after else (before if before else after)
            )
        changed_parts = [item for item in changed_parts if item and not item.isEmpty()]
        changed_area = (
            max(0.0, float(QgsGeometry.unaryUnion(changed_parts).area()))
            if changed_parts else 0.0
        )
        contiguous = not bool(added_area)
        if added and current and added_area > 0:
            contiguous = added.distance(current) <= adjacency_tolerance + 1e-9

        strong_revision_basis = any(bool(declarations.get(name)) for name in (
            "IMPLEMENTATION_IMPOSSIBLE", "UPPER_PLAN_ALIGNMENT", "MAIN_DECISIONS_AFFECTED",
        ))
        revision_basis = strong_revision_basis or (
            bool(declarations.get("NEED_NOT_MET")) and added_area <= adjacency_tolerance
        )
        findings = []
        if revision_basis:
            classification = "REVISION_REVIEW"
            if not bool(declarations.get("RATIONALE_DOCUMENTED")):
                findings.append('Madde 25 revizyon dayanağı beyan edilmiş ancak gerekçesi belgelenmemiştir.')
        elif added_area > adjacency_tolerance:
            classification = "ADDITION_REVIEW"
            if not bool(declarations.get("NEED_NOT_MET")):
                findings.append('İlave plan gereksinimi belgelenmemiştir.')
            if not contiguous:
                findings.append('İlave plan alanı mevcut planla bitişik değildir.')
            if not bool(declarations.get("LAND_USE_CONTINUITY_DOCUMENTED")):
                findings.append('Genel arazi kullanım sürekliliği, bütünlüğü ve uyumu belgelenmemiştir.')
        elif changed_area > adjacency_tolerance:
            classification = "PLAN_CHANGE_REVIEW"
            findings.append("Code-aware plan decisions changed without a declared Article 25 revision basis.")
        else:
            classification = "NO_CHANGE"
        return Article25Assessment(
            classification, current_area, proposed_area, changed_area, added_area,
            removed_area, contiguous, tuple(findings),
        )
