"""MPYY Article 26 density, height, and facade-distance checks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class DensityChangeFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class DensityChangeAudit:
    status: str
    required_facade_distance_m: float | None
    population_change: float | None
    findings: tuple[DensityChangeFinding, ...]


class DensityChangeAuditEngine:
    """Evaluates declared plan-change values and preserves the evidence gap."""

    @classmethod
    def audit(cls, values: Mapping[str, Any]) -> DensityChangeAudit:
        findings = []
        current_height = cls._number(values.get("current_height_m"))
        proposed_height = cls._number(values.get("proposed_height_m"))
        opposite_height = cls._number(values.get("opposite_height_m"))
        actual_distance = cls._number(values.get("actual_facade_distance_m"))
        current_population = cls._number(values.get("current_population"))
        proposed_population = cls._number(values.get("proposed_population"))
        current_intensity = cls._number(values.get("current_intensity"))
        proposed_intensity = cls._number(values.get("proposed_intensity"))

        height_increase = (
            current_height is not None and proposed_height is not None
            and proposed_height > current_height + 1e-9
        )
        population_change = None
        if current_population is not None and proposed_population is not None:
            population_change = proposed_population - current_population
        density_increase = (
            population_change is not None and population_change > 1e-9
        ) or (
            current_intensity is not None and proposed_intensity is not None
            and proposed_intensity > current_intensity + 1e-9
        )

        if current_height is None or proposed_height is None:
            findings.append(DensityChangeFinding(
                "MISSING_HEIGHT_COMPARISON", "ERROR",
                'Eksiksiz değişiklik denetimi için mevcut ve öneri yükseklikleri gereklidir.',
            ))
        if (
            current_population is None or proposed_population is None
        ) and (
            current_intensity is None or proposed_intensity is None
        ):
            findings.append(DensityChangeFinding(
                "MISSING_DENSITY_COMPARISON", "ERROR",
                'Eksiksiz nüfus veya plan yoğunluğu karşılaştırması gereklidir.',
            ))

        required_distance = None
        if height_increase:
            if opposite_height is None or proposed_height is None:
                findings.append(DensityChangeFinding(
                    "MISSING_OPPOSITE_HEIGHT", "ERROR",
                    'Madde 26 mesafe hesabı için karşı cephe yüksekliği gereklidir.',
                ))
            else:
                required_distance = ((proposed_height + opposite_height) / 2.0) + 7.0
                if actual_distance is None:
                    findings.append(DensityChangeFinding(
                "MISSING_FACADE_DISTANCE", "ERROR", 'Gerçek cephe mesafesi gereklidir.'
                    ))
                elif actual_distance + 1e-9 < required_distance:
                    findings.append(DensityChangeFinding(
                        "FACADE_DISTANCE", "ERROR",
                        'Gerçek cephe mesafesi K = ((Y1 + Y2) / 2) + 7 değerinin altındadır.',
                    ))
        if height_increase and not cls._boolean(values.get("silhouette_assessment")):
            findings.append(DensityChangeFinding(
                "SILHOUETTE_EVIDENCE", "WARNING", 'Silüet ve yönelim kanıtı kaydedilmemiştir.'
            ))
        if density_increase and not cls._boolean(values.get("infrastructure_impact_report")):
            findings.append(DensityChangeFinding(
                "INFRASTRUCTURE_IMPACT_REPORT", "ERROR",
                'Yoğunluk artışı kentsel teknik altyapı etki raporu gerektirir.',
            ))
        if density_increase and not cls._boolean(values.get("social_infrastructure_balance")):
            findings.append(DensityChangeFinding(
                "SOCIAL_INFRASTRUCTURE_BALANCE", "ERROR",
                'Sosyal ve teknik altyapı dengesi belgelenmemiştir.',
            ))
        if not height_increase and not density_increase:
            findings.append(DensityChangeFinding(
                "NO_DECLARED_INCREASE", "INFO", 'Beyan edilen değerlerde yükseklik veya yoğunluk artışı saptanmadı.'
            ))

        status = "NON_COMPLIANT" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if any(item.severity == "WARNING" for item in findings) else "COMPLIANT"
        )
        return DensityChangeAudit(status, required_distance, population_change, tuple(findings))

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number >= 0.0 else None

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "evet"}
