"""MPYY Article 26 road-plan change checks."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .attr_utils import parse_float


@dataclass(frozen=True)
class RoadChangeFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class RoadChangeAudit:
    status: str
    findings: tuple[RoadChangeFinding, ...]


class RoadChangeAuditEngine:
    """Audits explicit before/after road attributes supplied by the plan author."""

    @classmethod
    def audit(cls, values: Mapping[str, Any]) -> RoadChangeAudit:
        findings = []
        current_width = cls._number(values.get("current_width_m"))
        proposed_width = cls._number(values.get("proposed_width_m"))
        current_lanes = cls._number(values.get("current_lanes"))
        proposed_lanes = cls._number(values.get("proposed_lanes"))
        road_type = str(values.get("road_type") or "TRAFFIC").strip().upper()
        context = str(values.get("area_context") or "SETTLED").strip().upper()

        if current_width is None or proposed_width is None:
            findings.append(RoadChangeFinding(
                "MISSING_WIDTH", "ERROR", 'Mevcut ve öneri yol genişlikleri gereklidir.'
            ))
        elif proposed_width + 1e-9 < current_width:
            findings.append(RoadChangeFinding(
                "ROAD_NARROWING", "ERROR", 'Öneri süreklilik gösteren yol kesimi daha dardır.'
            ))
        if current_lanes is not None and proposed_lanes is not None and proposed_lanes < current_lanes:
            findings.append(RoadChangeFinding(
                "LANE_REDUCTION", "ERROR", 'Öneri süreklilik gösteren yol kesiminde şerit sayısı azalmaktadır.'
            ))
        if proposed_width is not None and context == "DEVELOPMENT":
            if road_type in {"PEDESTRIAN", "PEDESTRIAN_PATH"} and proposed_width < 3.0:
                findings.append(RoadChangeFinding(
                "PEDESTRIAN_WIDTH", "ERROR", 'Gelişme alanındaki yaya yolları en az 3 m olmalıdır.'
                ))
            elif road_type not in {"PEDESTRIAN", "PEDESTRIAN_PATH"} and proposed_width < 10.0:
                findings.append(RoadChangeFinding(
                "TRAFFIC_ROAD_WIDTH", "ERROR", 'Gelişme alanındaki taşıt yolları en az 10 m olmalıdır.'
                ))
        if proposed_width is not None and cls._boolean(values.get("parcel_access")) and proposed_width < 7.0:
            findings.append(RoadChangeFinding(
                "PARCEL_ACCESS_WIDTH", "ERROR", "7 m'den dar parsel erişim yolu düzeltme gerektirir."
            ))
        if cls._boolean(values.get("dead_end")) and not cls._boolean(values.get("turning_curve")):
            findings.append(RoadChangeFinding(
                "DEAD_END_TURNING", "ERROR", 'Çıkmaz yol için dönüş düzenlemesi gereklidir.'
            ))
        if not cls._boolean(values.get("traffic_impact_assessment")):
            findings.append(RoadChangeFinding(
                "TRAFFIC_IMPACT_EVIDENCE", "WARNING", 'Trafik etkisi kanıtı kaydedilmemiştir.'
            ))

        status = "NON_COMPLIANT" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLIANT"
        )
        return RoadChangeAudit(status, tuple(findings))

    @staticmethod
    def _number(value: Any) -> float | None:
        number = parse_float(value)
        if number is None:
            return None
        return number if math.isfinite(number) and number >= 0.0 else None

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "evet"}
