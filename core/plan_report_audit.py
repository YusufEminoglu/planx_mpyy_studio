"""MPYY Article 9 plan-report content audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class PlanReportFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class PlanReportAuditResult:
    plan_level: str
    report_purpose: str
    status: str
    findings: list[PlanReportFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class PlanReportAuditEngine:
    """Checks declared report sections without assessing their professional adequacy."""

    COMMON_SECTIONS = (
        "plan_type_scale_scope",
        "vision_objectives_targets_strategies",
        "protection_use_principles",
        "land_use_decisions",
        "density_and_building_principles",
        "implementation_principles",
        "open_green_system",
        "transport",
        "accessibility",
        "efficient_use_of_space",
        "area_distribution_table",
    )
    PURPOSES = {"NEW_PLAN", "REVISION", "ADDITION", "PLAN_CHANGE"}

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> PlanReportAuditResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        purpose = str(manifest.get("report_purpose", "")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
        if purpose not in cls.PURPOSES:
            raise ValueError('report_purpose NEW_PLAN, REVISION, ADDITION veya PLAN_CHANGE olmalıdır.')
        sections = manifest.get("sections", {})
        if not isinstance(sections, Mapping):
            raise ValueError('sections bir JSON nesnesi olmalıdır.')
        not_applicable = manifest.get("not_applicable_sections", {})
        if not isinstance(not_applicable, Mapping):
            raise ValueError('not_applicable_sections bir JSON nesnesi olmalıdır.')
        findings = []
        for section in cls.COMMON_SECTIONS:
            exemption_reason = not_applicable.get(section)
            exempted = isinstance(exemption_reason, str) and bool(exemption_reason.strip())
            if not cls._present(sections.get(section)) and not exempted:
                findings.append(PlanReportFinding(
                    "MISSING_" + section.upper(), "ERROR", "MPYY 9/2",
                    section + ' plan raporu içerik listesinde dayanaklandırılmamış.',
                ))
        if purpose == "PLAN_CHANGE":
            for section in ("detailed_change_rationale", "necessity_analyses"):
                if not cls._present(sections.get(section)):
                    findings.append(PlanReportFinding(
                        "MISSING_" + section.upper(), "ERROR", "MPYY 9/4",
                        section + ' plan değişikliği raporu için zorunludur.',
                    ))
        if cls._boolean(manifest.get("contains_mixed_use")):
            for section in (
                "mixed_use_ratios", "parking_details", "green_area_details",
                "social_technical_infrastructure_details",
            ):
                if not cls._present(sections.get(section)):
                    findings.append(PlanReportFinding(
                        "MISSING_" + section.upper(), "ERROR", "MPYY 9/5",
                        section + ' karma kullanım kararları için gereklidir.',
                    ))
            if not cls._present(sections.get("independent_unit_count")):
                findings.append(PlanReportFinding(
                    "MISSING_INDEPENDENT_UNIT_COUNT", "WARNING", "MPYY 9/5",
                    'Bağımsız bölüm sayısı kaydedilmemiş; gerekli olup olmadığını doğrulayın.',
                ))
        status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLETE"
        )
        return PlanReportAuditResult(level, purpose, status, findings)

    @classmethod
    def audit_file(cls, manifest_path: str | Path):
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Plan raporu bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('Plan raporu bildiriminin kökü bir JSON nesnesi olmalıdır.')
        return cls.audit(payload)

    @staticmethod
    def write_report(result: PlanReportAuditResult, output_path: str | Path) -> str:
        path = Path(output_path)
        payload = asdict(result)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return str(path)

    @staticmethod
    def _present(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return value not in (None, "", "NULL", [], {})

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "evet"}
