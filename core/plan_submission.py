"""MPYY Articles 31-35 plan submission and publication dossier audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class SubmissionFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class SubmissionAuditResult:
    plan_level: str
    lifecycle_status: str
    status: str
    findings: list[SubmissionFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class PlanSubmissionAuditEngine:
    """Validates documentary evidence without claiming administrative approval."""

    COMMON_DOCUMENTS = ("plan_sheet", "plan_notes", "plan_report", "author_signed")
    STAGE_DOCUMENTS = {
        "MSP": ("thematic_maps", "action_plan"),
        "CDP": ("analysis_report",),
        "NIP": ("threshold_analysis", "geological_survey"),
        "UIP": ("upper_plan_analysis", "geological_survey", "accessibility_analysis"),
    }

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> SubmissionAuditResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        lifecycle = str(manifest.get("lifecycle_status", "DRAFT")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('Sunum plan_level değeri MSP, CDP, NIP veya UIP olmalıdır.')
        if lifecycle not in {"DRAFT", "APPROVED", "FINALIZED"}:
            raise ValueError('lifecycle_status DRAFT, APPROVED veya FINALIZED olmalıdır.')
        documents = manifest.get("documents", {})
        if not isinstance(documents, Mapping):
            raise ValueError('documents bir JSON nesnesi olmalıdır.')
        findings: list[SubmissionFinding] = []

        for document in cls.COMMON_DOCUMENTS + cls.STAGE_DOCUMENTS[level]:
            if not cls._present(documents.get(document)):
                findings.append(SubmissionFinding(
                    "MISSING_" + document.upper(), "ERROR", "MPYY 31",
                    'Gerekli plan dosyası dayanağı eksik: ' + document,
                ))
        if level in {"NIP", "UIP"} and not cls._present(documents.get("current_base_map")):
            findings.append(SubmissionFinding(
                "MISSING_CURRENT_BASE_MAP", "ERROR", "MPYY 21",
                'Güncel onaylı hâlihazır harita dayanağı eksik.',
            ))

        if lifecycle in {"APPROVED", "FINALIZED"}:
            for key, label in (
                ("plan_transaction_number", "Plan Transaction Number"),
                ("approval_date", "approval date"),
                ("approval_number", "approval decision number"),
            ):
                if not cls._present(manifest.get(key)):
                    findings.append(SubmissionFinding(
                        "MISSING_" + key.upper(), "ERROR", "MPYY 32",
                        label + ' onaylı plan için gereklidir.',
                    ))

        if lifecycle == "FINALIZED":
            findings.extend(cls._finalization_findings(manifest, documents))

        status = "NON_COMPLIANT" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLIANT"
        )
        return SubmissionAuditResult(level, lifecycle, status, findings)

    @classmethod
    def audit_file(cls, manifest_path: str | Path) -> SubmissionAuditResult:
        path = Path(manifest_path).resolve()
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Sunum bildirimi okunamadı.') from error
        if not isinstance(manifest, dict):
            raise ValueError('Sunum bildirimi bir JSON nesnesi içermelidir.')
        return cls.audit(manifest)

    @classmethod
    def write_report(cls, result: SubmissionAuditResult, output_path: str | Path) -> str:
        output = Path(output_path).resolve()
        if output.suffix.lower() != ".json":
            raise ValueError('Sunum denetim raporu .json uzantısını kullanmalıdır.')
        if output.exists():
            raise FileExistsError(str(output))
        output.parent.mkdir(parents=True, exist_ok=True)
        findings = [item.__dict__ for item in result.findings]
        core = {
            "plan_level": result.plan_level,
            "lifecycle_status": result.lifecycle_status,
            "status": result.status,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "findings": findings,
        }
        canonical = json.dumps(core, ensure_ascii=True, sort_keys=True)
        report = dict(core)
        report["schema_version"] = 1
        report["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        report["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        temporary = output.with_name(' satır bulundu.' + output.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(output)
        return str(output)

    @classmethod
    def _finalization_findings(cls, manifest, documents) -> list[SubmissionFinding]:
        findings: list[SubmissionFinding] = []
        for document in ("suspension_start_minutes", "suspension_end_minutes", "digital_dataset"):
            if not cls._present(documents.get(document)):
                findings.append(SubmissionFinding(
                    "MISSING_" + document.upper(), "ERROR", "MPYY 33-35",
                    'Kesinleşmiş plan dayanağı eksik: ' + document,
                ))
        approval = cls._date(manifest.get("approval_date"), "approval_date", findings)
        suspension_start = cls._date(
            manifest.get("suspension_start_date"), "suspension_start_date", findings
        )
        suspension_end = cls._date(
            manifest.get("suspension_end_date"), "suspension_end_date", findings
        )
        finalization = cls._date(
            manifest.get("finalization_date"), "finalization_date", findings
        )
        delivery = cls._date(
            manifest.get("provincial_delivery_date"), "provincial_delivery_date", findings
        )
        holiday_values = manifest.get("official_holidays", [])
        holidays: set[date] = set()
        if not isinstance(holiday_values, list):
            findings.append(SubmissionFinding(
                "INVALID_OFFICIAL_HOLIDAYS", "ERROR", "MPYY 33/1",
                'official_holidays alanı YYYY-AA-GG tarihlerinden oluşan liste olmalıdır.',
            ))
        else:
            for value in holiday_values:
                parsed = cls._optional_date(value)
                if parsed is None:
                    findings.append(SubmissionFinding(
                        "INVALID_OFFICIAL_HOLIDAY", "ERROR", "MPYY 33/1",
                        'Resmî tatil tarihleri YYYY-AA-GG biçiminde olmalıdır.',
                    ))
                else:
                    holidays.add(parsed)
        if approval and suspension_start and suspension_start < approval:
            findings.append(SubmissionFinding(
                "INVALID_SUSPENSION_ORDER", "ERROR", "MPYY 33/1",
                'Askı onaydan önce başlayamaz.',
            ))
        elif approval and suspension_start and cls._business_days_after(
            approval, suspension_start, holidays
        ) > 15:
            findings.append(SubmissionFinding(
                "LATE_SUSPENSION_START", "ERROR", "MPYY 33/1",
                "The suspension/publication process started after fifteen business days.",
            ))
        if suspension_start and suspension_end and (suspension_end - suspension_start).days < 30:
            findings.append(SubmissionFinding(
                "SHORT_SUSPENSION_PERIOD", "ERROR", "MPYY 33/1",
                "The suspension/publication period is shorter than thirty days.",
            ))
        if suspension_end and finalization and finalization < suspension_end:
            findings.append(SubmissionFinding(
                "INVALID_FINALIZATION_ORDER", "ERROR", "MPYY 33",
                "Finalization cannot precede the end of the suspension period.",
            ))
        if finalization and delivery and delivery < finalization:
            findings.append(SubmissionFinding(
                "INVALID_DELIVERY_ORDER", "ERROR", "MPYY 34/4, 35/2",
                "Provincial delivery cannot precede finalization.",
            ))
        elif finalization and delivery and (delivery - finalization).days > 15:
            findings.append(SubmissionFinding(
                "LATE_PROVINCIAL_DELIVERY", "ERROR", "MPYY 34/4, 35/2",
                "The finalized plan was delivered after the fifteen-day period.",
            ))
        return findings

    @staticmethod
    def _business_days_after(start: date, end: date, holidays: set[date] | None = None) -> int:
        if end <= start:
            return 0
        current = start + timedelta(days=1)
        count = 0
        while current <= end:
            if current.weekday() < 5 and current not in (holidays or set()):
                count += 1
            current += timedelta(days=1)
        return count

    @staticmethod
    def _date(value: Any, field_name: str, findings: list[SubmissionFinding]) -> date | None:
        if not PlanSubmissionAuditEngine._present(value):
            findings.append(SubmissionFinding(
                "MISSING_" + field_name.upper(), "ERROR", "MPYY 32-35",
                'Gerekli süreç tarihi eksik: ' + field_name,
            ))
            return None
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            findings.append(SubmissionFinding(
                "INVALID_" + field_name.upper(), "ERROR", "MPYY 32-35",
                field_name + ' YYYY-AA-GG biçiminde olmalıdır.',
            ))
            return None

    @staticmethod
    def _optional_date(value: Any) -> date | None:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _present(value: Any) -> bool:
        return value is True or (isinstance(value, str) and bool(value.strip()))
