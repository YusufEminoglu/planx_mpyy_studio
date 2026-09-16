"""Compare two networks and facility sets against the same demand features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from qgis.core import QgsFeature

from .multimodal_accessibility import (
    MPYYMultimodalAccessibilityEngine,
    MultimodalAccessibilityRecord,
    MultimodalAccessibilityResult,
)


@dataclass(frozen=True)
class AccessibilityScenarioRecord:
    baseline: MultimodalAccessibilityRecord
    proposed: MultimodalAccessibilityRecord
    change: str
    time_change_min: float | None


@dataclass(frozen=True)
class AccessibilityScenarioResult:
    records: tuple[AccessibilityScenarioRecord, ...]
    baseline: MultimodalAccessibilityResult
    proposed: MultimodalAccessibilityResult


class MPYYAccessibilityScenarioEngine:
    @classmethod
    def compare(
        cls,
        baseline_network: Iterable[QgsFeature],
        proposed_network: Iterable[QgsFeature],
        demand_features: Iterable[QgsFeature],
        baseline_facilities: Iterable[QgsFeature],
        proposed_facilities: Iterable[QgsFeature],
        maximum_time_min: float,
        **options: Any,
    ) -> AccessibilityScenarioResult:
        # Materialize once: feature IDs from separate demand exports need not coincide.
        demand = tuple(demand_features)
        baseline = MPYYMultimodalAccessibilityEngine.analyze(
            baseline_network, demand, baseline_facilities, maximum_time_min, **options
        )
        proposed = MPYYMultimodalAccessibilityEngine.analyze(
            proposed_network, demand, proposed_facilities, maximum_time_min, **options
        )
        records = []
        for first, second in zip(baseline.records, proposed.records):
            delta = None
            if first.status == "UNSNAPPED" or second.status == "UNSNAPPED":
                change = "SNAP_REVIEW"
            elif first.status == "UNREACHABLE" and second.status == "UNREACHABLE":
                change = "STILL_UNREACHABLE"
            elif first.status == "UNREACHABLE":
                change = "NEWLY_REACHABLE"
            elif second.status == "UNREACHABLE":
                change = "LOST_ROUTE"
            else:
                delta = second.route_time_min - first.route_time_min
                change = "FASTER" if delta < -1e-9 else (
                    "SLOWER" if delta > 1e-9 else "UNCHANGED"
                )
            records.append(AccessibilityScenarioRecord(first, second, change, delta))
        return AccessibilityScenarioResult(tuple(records), baseline, proposed)
