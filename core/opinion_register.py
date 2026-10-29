"""MPYY Article 8 institution-opinion deadline audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid


@dataclass(frozen=True)
class OpinionRecord:
    institution: str
    status: str
    deadline: str
    response_date: str
    days_late: int
    message: str


@dataclass(frozen=True)
class OpinionRegisterResult:
    status: str
    evaluation_date: str
    records: tuple[OpinionRecord, ...]
    late_response_count: int
    deemed_no_negative_count: int
    pending_count: int
    invalid_count: int


class OpinionRegisterAuditEngine:
    """Audits initial and extended thirty-day opinion periods."""

    @classmethod
    def audit(
        cls,
        manifest: Mapping[str, Any],
        evaluation_date: date | str | None = None,
    ) -> OpinionRegisterResult:
        declared_evaluation_date = evaluation_date or manifest.get("evaluation_date")
        evaluated_on = cls._date(declared_evaluation_date)
        if declared_evaluation_date not in (None, "", "NULL") and evaluated_on is None:
            raise ValueError('evaluation_date YYYY-AA-GG biçimini kullanmalıdır.')
        if evaluated_on is None:
            evaluated_on = date.today()
        entries = manifest.get("institutions", [])
        if not isinstance(entries, list):
            raise ValueError('institutions bir JSON dizisi olmalıdır.')
        records = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                records.append(OpinionRecord(
                    "", "INVALID", "", "", 0, 'Kurum kaydı bir JSON nesnesi olmalıdır.'
                ))
                continue
            institution = str(entry.get("institution", "")).strip()
            requested_on = cls._date(entry.get("request_date"))
            raw_response_date = entry.get("response_date")
            responded_on = cls._date(raw_response_date, allow_empty=True)
            extension = cls._boolean(entry.get("extension_granted"))
            if not institution or requested_on is None:
                records.append(OpinionRecord(
                    institution, "INVALID", "", str(entry.get("response_date") or ""), 0,
                    'Kurum ve YYYY-AA-GG biçiminde request_date alanı gereklidir.',
                ))
                continue
            if raw_response_date not in (None, "", "NULL") and responded_on is None:
                records.append(OpinionRecord(
                    institution, "INVALID", "", str(raw_response_date), 0,
                    'response_date alanı YYYY-AA-GG biçiminde olmalıdır.',
                ))
                continue
            deadline = requested_on + timedelta(days=60 if extension else 30)
            if responded_on:
                days_late = max(0, (responded_on - deadline).days)
                status = "LATE_RESPONSE_REVIEW" if days_late else "RESPONDED"
                message = (
                    "Opinion response was received after the applicable deadline."
                    if days_late else "Opinion response was received within the applicable period."
                )
            elif evaluated_on > deadline:
                days_late = (evaluated_on - deadline).days
                status = "DEEMED_NO_NEGATIVE_OPINION"
                message = (
                    'Geçerli süre içinde yanıt kaydı yok; 8/2. madde olumsuz görüş bulunmadığını kabul eder.'
                )
            else:
                days_late = 0
                status = "PENDING"
                message = "Opinion request remains within the applicable period."
            records.append(OpinionRecord(
                institution, status, deadline.isoformat(),
                responded_on.isoformat() if responded_on else "", days_late, message,
            ))
        record_tuple = tuple(records)
        invalid = sum(item.status == "INVALID" for item in record_tuple)
        late = sum(item.status == "LATE_RESPONSE_REVIEW" for item in record_tuple)
        deemed = sum(item.status == "DEEMED_NO_NEGATIVE_OPINION" for item in record_tuple)
        pending = sum(item.status == "PENDING" for item in record_tuple)
        status = "INCOMPLETE" if invalid else (
            "REVIEW_REQUIRED" if late else ("PENDING" if pending else "COMPLETE")
        )
        return OpinionRegisterResult(
            status, evaluated_on.isoformat(), record_tuple, late, deemed, pending, invalid
        )

    @classmethod
    def audit_file(cls, manifest_path: str | Path, evaluation_date: date | str | None = None):
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Kurum görüşü kayıtları okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('Kurum görüşü kayıtlarının kökü bir JSON nesnesi olmalıdır.')
        return cls.audit(payload, evaluation_date)

    @staticmethod
    def write_report(result: OpinionRegisterResult, output_path: str | Path) -> str:
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
    def _date(value: Any, allow_empty: bool = False) -> date | None:
        if value in (None, "", "NULL") and allow_empty:
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "evet"}
