"""Declared-policy freshness checks for MPYY planning evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class FreshnessFinding:
    code: str
    severity: str
    evidence_id: str
    message: str


@dataclass
class EvidenceFreshnessResult:
    plan_level: str
    as_of_date: str
    status: str
    current_count: int
    expired_count: int
    findings: list[FreshnessFinding] = field(default_factory=list)


class EvidenceFreshnessAuditEngine:
    """Applies only validity dates or review intervals declared by the dossier owner."""

    @classmethod
    def audit(cls, manifest: Mapping[str, Any], as_of_date: str | date) -> EvidenceFreshnessResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
        as_of = as_of_date if isinstance(as_of_date, date) else cls._date(as_of_date)
        if as_of is None:
            raise ValueError('as_of_date YYYY-AA-GG biçimini kullanmalıdır.')
        items = manifest.get("evidence_items", [])
        if not isinstance(items, list):
            raise ValueError('evidence_items bir JSON dizisi olmalıdır.')
        findings: list[FreshnessFinding] = []
        current_count = 0
        expired_count = 0
        seen = set()
        if not items:
            findings.append(FreshnessFinding(
                "EMPTY_EVIDENCE_REGISTER", "ERROR", "",
                'Güncellik incelemesi için kullanılabilir dayanak yok.',
            ))
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                findings.append(FreshnessFinding(
                    "INVALID_ITEM", "ERROR", "", f'Evidence item {index} bir nesne olmalıdır.'
                ))
                continue
            evidence_id = str(item.get("evidence_id", "")).strip()
            if not evidence_id:
                findings.append(FreshnessFinding(
                    "MISSING_EVIDENCE_ID", "ERROR", "", f'Evidence item {index} kimliği yok.'
                ))
                continue
            if evidence_id in seen:
                findings.append(FreshnessFinding(
                    "DUPLICATE_EVIDENCE_ID", "ERROR", evidence_id, "Evidence ID is duplicated."
                ))
                continue
            seen.add(evidence_id)
            valid_through = cls._date(item.get("valid_through"))
            last_verified = cls._date(item.get("last_verified"))
            interval = cls._positive_integer(item.get("review_interval_days"))
            if cls._present(item.get("valid_through")) and valid_through is None:
                findings.append(FreshnessFinding(
                    "INVALID_VALID_THROUGH", "ERROR", evidence_id,
                    'valid_through alanı YYYY-AA-GG biçiminde olmalıdır.',
                ))
                continue
            if cls._present(item.get("last_verified")) and last_verified is None:
                findings.append(FreshnessFinding(
                    "INVALID_LAST_VERIFIED", "ERROR", evidence_id,
                    'last_verified alanı YYYY-AA-GG biçiminde olmalıdır.',
                ))
                continue
            if cls._present(item.get("review_interval_days")) and interval is None:
                findings.append(FreshnessFinding(
                    "INVALID_REVIEW_INTERVAL", "ERROR", evidence_id,
                    'review_interval_days alanı pozitif tam sayı olmalıdır.',
                ))
                continue
            if last_verified and last_verified > as_of:
                findings.append(FreshnessFinding(
                    "FUTURE_VERIFICATION_DATE", "ERROR", evidence_id,
                    "last_verified cannot be after the audit date.",
                ))
                continue
            policy_deadline = last_verified + timedelta(days=interval) if last_verified and interval else None
            deadlines = [value for value in (valid_through, policy_deadline) if value is not None]
            if not deadlines:
                findings.append(FreshnessFinding(
                    "FRESHNESS_POLICY_NOT_DECLARED", "WARNING", evidence_id,
                    'Geçerlilik tarihi veya veri sahibinin belirttiği inceleme aralığı yok.',
                ))
                continue
            effective_deadline = min(deadlines)
            if effective_deadline < as_of:
                expired_count += 1
                findings.append(FreshnessFinding(
                    "EVIDENCE_EXPIRED", "ERROR", evidence_id,
                    'Dayanağın belirtilen geçerlilik veya inceleme süresi aşılmış.',
                ))
            else:
                current_count += 1
        status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLETE"
        )
        return EvidenceFreshnessResult(
            level, as_of.isoformat(), status, current_count, expired_count, findings
        )

    @classmethod
    def audit_file(cls, manifest_path: str | Path, as_of_date: str | date):
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Kanıt güncelliği bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('Kanıt güncelliği bildiriminin kökü bir JSON nesnesi olmalıdır.')
        return cls.audit(payload, as_of_date)

    @staticmethod
    def write_report(result: EvidenceFreshnessResult, output_path: str | Path) -> str:
        path = Path(output_path)
        payload = asdict(result)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return str(path)

    @staticmethod
    def _date(value: Any) -> date | None:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _positive_integer(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number) or number <= 0 or not number.is_integer():
            return None
        return int(number)

    @staticmethod
    def _present(value: Any) -> bool:
        return value not in (None, "", [], {})
