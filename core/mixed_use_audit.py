"""Feature-level MPYY Articles 9/5 and 21/10 mixed-use audit."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping


@dataclass(frozen=True)
class MixedUseFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class MixedUseAuditResult:
    status: str
    effective_residential_ratio: float | None
    findings: list[MixedUseFinding] = field(default_factory=list)


class MPYYMixedUseAuditEngine:
    RESIDENTIAL_MIXED_CODES = {
        "TICARET+KONUT", "TICARET KONUT", "TICARET+TURIZM+KONUT",
        "TICARET TURIZM KONUT", "TURIZM+TICARET+KONUT", "TURIZM TICARET KONUT",
    }

    @classmethod
    def audit(cls, record: Mapping[str, Any]) -> MixedUseAuditResult:
        normalized = {str(key).strip().lower(): value for key, value in record.items()}
        use_code = cls._normalize_code(normalized.get("use_code") or normalized.get("fonksiyon_kodu"))
        component_count = cls._integer(normalized.get("use_component_count"))
        is_mixed = use_code in cls.RESIDENTIAL_MIXED_CODES or (component_count or 0) > 1
        findings: list[MixedUseFinding] = []
        if not is_mixed:
            return MixedUseAuditResult("NOT_APPLICABLE", None, findings)
        for key in (
            "ratios_in_plan_report", "ratios_in_plan_notes", "parking_details",
            "green_area_details", "social_technical_infrastructure_details",
        ):
            if not cls._boolean(normalized.get(key)):
                findings.append(MixedUseFinding(
                    "MISSING_" + key.upper(), "ERROR", "MPYY 9/5",
                    'Karma kullanım belgesi eksik: ' + key,
                ))
        effective_ratio = None
        if use_code in cls.RESIDENTIAL_MIXED_CODES:
            ratio = cls._ratio(normalized.get("residential_ratio"))
            if cls._present(normalized.get("residential_ratio")) and ratio is None:
                findings.append(MixedUseFinding(
                    "INVALID_RESIDENTIAL_RATIO", "ERROR", "MPYY 21/10",
                    'Konut oranı sıfır ile bir arasında olmalıdır.',
                ))
            elif ratio is None:
                effective_ratio = 0.30
                findings.append(MixedUseFinding(
                    "DEFAULT_RESIDENTIAL_RATIO", "WARNING", "MPYY 21/10",
                    "Konut oranı belirtilmemiş; 21/10. madde varsayılan azami değeri 0,30'dur.",
                ))
            else:
                effective_ratio = ratio
            if not cls._boolean(normalized.get("residential_infrastructure_allocated")):
                findings.append(MixedUseFinding(
                    "MISSING_RESIDENTIAL_INFRASTRUCTURE", "ERROR", "MPYY 21/10",
                    "Social and technical infrastructure for residential use is not evidenced.",
                ))
        if cls._boolean(normalized.get("independent_unit_count_required")):
            units = cls._integer(normalized.get("independent_unit_count"))
            if units is None or units <= 0:
                findings.append(MixedUseFinding(
                    "MISSING_INDEPENDENT_UNIT_COUNT", "ERROR", "MPYY 9/5",
                    'Belirtilen bağlamda pozitif bağımsız bölüm sayısı gereklidir.',
                ))
        status = "NON_COMPLIANT" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLIANT"
        )
        return MixedUseAuditResult(status, effective_ratio, findings)

    @staticmethod
    def _normalize_code(value: Any) -> str:
        return " ".join(str(value or "").strip().upper().replace("İ", "I").split())

    @staticmethod
    def _boolean(value: Any) -> bool:
        return value is True or str(value).strip().lower() in {"1", "true", "yes", "evet"}

    @staticmethod
    def _present(value: Any) -> bool:
        return value not in (None, "")

    @staticmethod
    def _ratio(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and 0.0 <= number <= 1.0 else None

    @staticmethod
    def _integer(value: Any) -> int | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return int(number) if math.isfinite(number) and number.is_integer() else None
