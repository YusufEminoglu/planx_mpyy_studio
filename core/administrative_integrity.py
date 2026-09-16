"""MPYY administrative integrity audits for plan production and delivery."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class AdministrativeFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class AdministrativeAuditResult:
    audit_type: str
    plan_level: str
    status: str
    findings: list[AdministrativeFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class MPYYParticipationRegisterEngine:
    """Audits documented participation under Articles 7/1-j and 14/1-e."""

    METHODS = {
        "SURVEY", "PUBLIC_OPINION_POLL", "RESEARCH", "MEETING", "WORKSHOP",
        "ONLINE_ANNOUNCEMENT", "INFORMATION_SESSION", "OTHER_DOCUMENTED",
    }
    MSP_GROUPS = {
        "PUBLIC_INSTITUTION", "DEVELOPMENT_AGENCY", "UNIVERSITY",
        "LOCAL_GOVERNMENT", "CIVIL_SOCIETY", "PROFESSIONAL_CHAMBER", "PRIVATE_SECTOR",
    }

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> AdministrativeAuditResult:
        level = _plan_level(manifest)
        events = manifest.get("events", [])
        if not isinstance(events, list):
            raise ValueError('events bir JSON dizisi olmalıdır.')
        findings: list[AdministrativeFinding] = []
        seen_ids = set()
        covered_groups = set()
        if not events:
            findings.append(AdministrativeFinding(
                "NO_PARTICIPATION_EVENT", "ERROR", "MPYY 7/1-j",
                'Belgelenmiş katılım etkinliği kaydedilmemiştir.',
            ))
        for index, event in enumerate(events, start=1):
            if not isinstance(event, Mapping):
                findings.append(AdministrativeFinding(
                    "INVALID_EVENT", "ERROR", "MPYY 7/1-j",
                    f'{index} numaralı katılım etkinliği bir JSON nesnesi olmalıdır.',
                ))
                continue
            event_id = str(event.get("event_id", "")).strip()
            if not event_id:
                findings.append(AdministrativeFinding(
                    "MISSING_EVENT_ID", "ERROR", "MPYY 7/1-j",
                    f'{index} numaralı katılım etkinliğinin kimliği yoktur.',
                ))
            elif event_id in seen_ids:
                findings.append(AdministrativeFinding(
                    "DUPLICATE_EVENT_ID", "ERROR", "MPYY 7/1-j",
                    'Katılım etkinliği kimliği yinelenmiştir: ' + event_id,
                ))
            seen_ids.add(event_id)
            method = str(event.get("method", "")).strip().upper()
            if method not in cls.METHODS:
                findings.append(AdministrativeFinding(
                    "INVALID_PARTICIPATION_METHOD", "ERROR", "MPYY 7/1-j",
                    'Katılım yöntemi eksik veya desteklenmiyor: ' + method,
                ))
            if _date(event.get("date")) is None:
                findings.append(AdministrativeFinding(
                    "INVALID_EVENT_DATE", "ERROR", "MPYY 7/1-j",
                    'Katılım etkinliği tarihi YYYY-AA-GG biçimini kullanmalıdır.',
                ))
            groups = event.get("stakeholder_groups", [])
            if not isinstance(groups, list) or not groups:
                findings.append(AdministrativeFinding(
                    "MISSING_STAKEHOLDER_GROUPS", "ERROR", "MPYY 7/1-j",
                    'Katılım etkinliğinde paydaş grubu kaydı yoktur.',
                ))
            else:
                covered_groups.update(str(item).strip().upper() for item in groups if str(item).strip())
            for key in ("announcement_evidence", "attendance_evidence", "outcome_summary"):
                if not _present(event.get(key)):
                    findings.append(AdministrativeFinding(
                        "MISSING_" + key.upper(), "ERROR", "MPYY 7/1-j",
                    'Katılım kanıtı eksiktir: ' + key,
                    ))
            if not _present(event.get("input_disposition")):
                findings.append(AdministrativeFinding(
                    "MISSING_INPUT_DISPOSITION", "WARNING", "MPYY 7/1-j",
                    'Katılım girdisinin plana nasıl yansıdığı belgelenmemiştir.',
                ))
        if level == "MSP":
            for missing in sorted(cls.MSP_GROUPS - covered_groups):
                findings.append(AdministrativeFinding(
                    "MISSING_MSP_GROUP_" + missing, "ERROR", "MPYY 14/1-e",
                    'Şu MSP paydaşı için katılım kanıtlanmamıştır: ' + missing,
                ))
        return _result("MPYY_PARTICIPATION_REGISTER", level, findings)


class MPYYCancelledPlanEvidenceEngine:
    """Audits re-evaluation of earlier opinions, analysis, and synthesis under Article 7/1-k."""

    REQUIRED_KINDS = {"INSTITUTION_OPINIONS", "ANALYSIS", "SYNTHESIS"}
    DECISIONS = {"REUSED", "SUPERSEDED", "REJECTED"}

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> AdministrativeAuditResult:
        level = _plan_level(manifest)
        if not _boolean(manifest.get("prior_plan_cancelled")):
            return AdministrativeAuditResult(
                "MPYY_CANCELLED_PLAN_EVIDENCE", level, "NOT_APPLICABLE", []
            )
        findings: list[AdministrativeFinding] = []
        for key in ("cancelled_plan_reference", "cancellation_decision_reference"):
            if not _present(manifest.get(key)):
                findings.append(AdministrativeFinding(
                    "MISSING_" + key.upper(), "ERROR", "MPYY 7/1-k",
                    'İptal edilen plan izlenebilirliği eksiktir: ' + key,
                ))
        items = manifest.get("reevaluations", [])
        if not isinstance(items, list):
            raise ValueError('reevaluations bir JSON dizisi olmalıdır.')
        represented = set()
        seen_ids = set()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                findings.append(AdministrativeFinding(
                    "INVALID_REEVALUATION", "ERROR", "MPYY 7/1-k",
                    f'{index} numaralı yeniden değerlendirme bir JSON nesnesi olmalıdır.',
                ))
                continue
            evidence_id = str(item.get("evidence_id", "")).strip()
            if not evidence_id:
                findings.append(AdministrativeFinding(
                    "MISSING_EVIDENCE_ID", "ERROR", "MPYY 7/1-k",
                    f'{index} numaralı yeniden değerlendirmenin kanıt kimliği yoktur.',
                ))
            elif evidence_id in seen_ids:
                findings.append(AdministrativeFinding(
                    "DUPLICATE_EVIDENCE_ID", "ERROR", "MPYY 7/1-k",
                    'Yeniden değerlendirilen kanıt kimliği yinelenmiştir: ' + evidence_id,
                ))
            seen_ids.add(evidence_id)
            kind = str(item.get("kind", "")).strip().upper()
            if kind:
                represented.add(kind)
            if kind not in cls.REQUIRED_KINDS:
                findings.append(AdministrativeFinding(
                    "INVALID_EVIDENCE_KIND", "ERROR", "MPYY 7/1-k",
                    'Kanıt türü görüş, analiz veya sentezi tanımlamalıdır.',
                ))
            decision = str(item.get("decision", "")).strip().upper()
            if decision not in cls.DECISIONS:
                findings.append(AdministrativeFinding(
                    "INVALID_REEVALUATION_DECISION", "ERROR", "MPYY 7/1-k",
                    'Yeniden değerlendirme kararı REUSED, SUPERSEDED veya REJECTED olmalıdır.',
                ))
            if _date(item.get("reevaluation_date")) is None:
                findings.append(AdministrativeFinding(
                    "INVALID_REEVALUATION_DATE", "ERROR", "MPYY 7/1-k",
                    'Yeniden değerlendirme tarihi YYYY-AA-GG biçimini kullanmalıdır.',
                ))
            if not _present(item.get("rationale")):
                findings.append(AdministrativeFinding(
                    "MISSING_RATIONALE", "ERROR", "MPYY 7/1-k",
                    'Yeniden değerlendirme gerekçesi eksiktir.',
                ))
            if not _present(item.get("responsible_party")):
                findings.append(AdministrativeFinding(
                    "MISSING_RESPONSIBLE_PARTY", "WARNING", "MPYY 7/1-k",
                    'Yeniden değerlendirmeden sorumlu taraf kaydedilmemiştir.',
                ))
            if decision == "REUSED" and not _present(item.get("current_version_reference")):
                findings.append(AdministrativeFinding(
                    "MISSING_CURRENT_VERSION_REFERENCE", "WARNING", "MPYY 7/1-k",
                    'Yeniden kullanılan kanıtın güncel sürüm başvurusu yoktur.',
                ))
        for missing in sorted(cls.REQUIRED_KINDS - represented):
            findings.append(AdministrativeFinding(
                "MISSING_REEVALUATION_" + missing, "ERROR", "MPYY 7/1-k",
                    'İptal edilen plan malzemesi şu konuda yeniden değerlendirilmemiştir: ' + missing,
            ))
        return _result("MPYY_CANCELLED_PLAN_EVIDENCE", level, findings)


class MPYYPlanComponentConsistencyEngine:
    """Checks identity consistency across sheet, display, notes, and report components."""

    REQUIRED_ROLES = {"PLAN_SHEET", "OFFICIAL_DISPLAY", "PLAN_NOTES", "PLAN_REPORT"}

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> AdministrativeAuditResult:
        level = _plan_level(manifest)
        expected = {
            "plan_id": str(manifest.get("plan_id", "")).strip(),
            "plan_version": str(manifest.get("plan_version", "")).strip(),
            "plan_level": level,
            "purpose": str(manifest.get("purpose", "")).strip().upper(),
        }
        components = manifest.get("components", [])
        if not isinstance(components, list):
            raise ValueError('components bir JSON dizisi olmalıdır.')
        findings: list[AdministrativeFinding] = []
        for key, value in expected.items():
            if not value:
                findings.append(AdministrativeFinding(
                    "MISSING_EXPECTED_" + key.upper(), "ERROR", "MPYY 7/1-b",
                    'Plan dosyası kimliği eksiktir: ' + key,
                ))
        if expected["purpose"] not in {"NEW_PLAN", "REVISION", "ADDITION", "PLAN_CHANGE"}:
            findings.append(AdministrativeFinding(
                "INVALID_PLAN_PURPOSE", "ERROR", "MPYY 7/1-b",
                'purpose NEW_PLAN, REVISION, ADDITION veya PLAN_CHANGE olmalıdır.',
            ))
        represented = set()
        for index, component in enumerate(components, start=1):
            if not isinstance(component, Mapping):
                findings.append(AdministrativeFinding(
                    "INVALID_COMPONENT", "ERROR", "MPYY 7/1-b",
                    f'{index} numaralı plan bileşeni bir JSON nesnesi olmalıdır.',
                ))
                continue
            role = str(component.get("role", "")).strip().upper()
            if role in represented:
                findings.append(AdministrativeFinding(
                    "DUPLICATE_COMPONENT_ROLE", "ERROR", "MPYY 7/1-b",
                    'Plan bileşeni rolü yinelenmiştir: ' + role,
                ))
            represented.add(role)
            for key, expected_value in expected.items():
                actual = str(component.get(key, "")).strip()
                if key in {"plan_level", "purpose"}:
                    actual = actual.upper()
                if actual != expected_value:
                    findings.append(AdministrativeFinding(
                        "INCONSISTENT_" + key.upper(), "ERROR", "MPYY 7/1-b",
                        role + ' bileşeni plan dosyasındaki ' + key + ' değerini kullanmıyor.',
                    ))
            if not _valid_sha256(component.get("sha256")):
                findings.append(AdministrativeFinding(
                    "INVALID_COMPONENT_SHA256", "ERROR", "MPYY 34-35",
                    'Bileşenin geçerli SHA-256 kimliği yoktur: ' + role,
                ))
        for missing in sorted(cls.REQUIRED_ROLES - represented):
            findings.append(AdministrativeFinding(
                "MISSING_COMPONENT_" + missing, "ERROR", "MPYY 7/1-b",
                'Plan bileşeni eksiktir: ' + missing,
            ))
        return _result("MPYY_PLAN_COMPONENT_CONSISTENCY", level, findings)


class MPYYApprovalSheetRegisterEngine:
    """Audits front-face approval markings on every plan sheet under Article 32/6."""

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> AdministrativeAuditResult:
        level = _plan_level(manifest)
        plan_transaction_number = str(manifest.get("plan_transaction_number", "")).strip()
        approval_date = str(manifest.get("approval_date", "")).strip()
        approval_number = str(manifest.get("approval_number", "")).strip()
        sheets = manifest.get("sheets", [])
        if not isinstance(sheets, list):
            raise ValueError('sheets bir JSON dizisi olmalıdır.')
        findings: list[AdministrativeFinding] = []
        if not plan_transaction_number:
            findings.append(AdministrativeFinding(
                "MISSING_PLAN_TRANSACTION_NUMBER", "ERROR", "MPYY 32/2, 32/6",
                'Plan İşlem Numarası eksiktir.',
            ))
        if _date(approval_date) is None:
            findings.append(AdministrativeFinding(
                "INVALID_APPROVAL_DATE", "ERROR", "MPYY 32/6",
                'Onay tarihi eksik veya geçersizdir.',
            ))
        if not approval_number:
            findings.append(AdministrativeFinding(
                "MISSING_APPROVAL_NUMBER", "ERROR", "MPYY 32/6",
                'Onay karar numarası eksiktir.',
            ))
        if not sheets:
            findings.append(AdministrativeFinding(
                "EMPTY_SHEET_REGISTER", "ERROR", "MPYY 32/6",
                'Kayıtlı plan paftası yoktur.',
            ))
        seen_ids = set()
        for index, sheet in enumerate(sheets, start=1):
            if not isinstance(sheet, Mapping):
                findings.append(AdministrativeFinding(
                    "INVALID_SHEET", "ERROR", "MPYY 32/6",
                    f'{index} numaralı plan paftası bir JSON nesnesi olmalıdır.',
                ))
                continue
            sheet_id = str(sheet.get("sheet_id", "")).strip()
            if not sheet_id:
                findings.append(AdministrativeFinding(
                    "MISSING_SHEET_ID", "ERROR", "MPYY 32/6",
                    f'{index} numaralı plan paftasının kimliği yoktur.',
                ))
            elif sheet_id in seen_ids:
                findings.append(AdministrativeFinding(
                    "DUPLICATE_SHEET_ID", "ERROR", "MPYY 32/6",
                    'Plan paftası kimliği yinelenmiştir: ' + sheet_id,
                ))
            seen_ids.add(sheet_id)
            for key, expected in (
                ("front_face_pin", plan_transaction_number),
                ("front_face_approval_date", approval_date),
                ("front_face_approval_number", approval_number),
            ):
                if str(sheet.get(key, "")).strip() != expected:
                    findings.append(AdministrativeFinding(
                        "INCONSISTENT_" + key.upper(), "ERROR", "MPYY 32/6",
                        sheet_id + ' paftasında eksik veya tutarsız ön yüz işareti vardır: ' + key,
                    ))
            if not _boolean(sheet.get("stamped")):
                findings.append(AdministrativeFinding(
                    "SHEET_NOT_STAMPED", "ERROR", "MPYY 32/6",
                    'Plan paftası mühürlü olarak kaydedilmemiştir: ' + sheet_id,
                ))
            if not _valid_sha256(sheet.get("sha256")):
                findings.append(AdministrativeFinding(
                    "INVALID_SHEET_SHA256", "ERROR", "MPYY 34-35",
                    'Plan paftasının geçerli SHA-256 kimliği yoktur: ' + sheet_id,
                ))
        return _result("MPYY_APPROVAL_SHEET_REGISTER", level, findings)


class MPYYDigitalDeliveryEngine:
    """Audits a finalized Article 34-35 digital delivery package."""

    COMMON_ROLES = {
        "PLAN_SHEET", "PLAN_NOTES", "PLAN_REPORT", "APPROVAL_DECISION",
        "SUSPENSION_START_MINUTES", "SUSPENSION_END_MINUTES", "GEOLOGICAL_SURVEY",
        "GEOSPATIAL_PLAN_DATA",
    }
    IMAR_ROLES = {"GEOLOGICAL_SURVEY"}

    @classmethod
    def audit(cls, manifest: Mapping[str, Any], base_directory: str | Path) -> AdministrativeAuditResult:
        level = _plan_level(manifest)
        findings: list[AdministrativeFinding] = []
        for key in (
            "plan_transaction_number", "format_profile_id", "crs_authid",
            "delivery_receipt", "destination_authority",
        ):
            if not _present(manifest.get(key)):
                findings.append(AdministrativeFinding(
                    "MISSING_" + key.upper(), "ERROR", "MPYY 34/4-5, 35/3",
                    'Sayısal teslim üst verisi eksik: ' + key,
                ))
        destination = str(manifest.get("destination_authority", "")).strip().upper()
        if destination and destination != "PROVINCIAL_DIRECTORATE":
            findings.append(AdministrativeFinding(
                "INVALID_DESTINATION_AUTHORITY", "ERROR", "MPYY 34/4, 35/2",
                'destination_authority alanı İl Müdürlüğünü tanımlamalıdır.',
            ))
        finalized = _date(manifest.get("finalization_date"))
        delivered = _date(manifest.get("delivery_date"))
        if finalized is None or delivered is None:
            findings.append(AdministrativeFinding(
                "INVALID_DELIVERY_DATES", "ERROR", "MPYY 34/4, 35/2",
                'Kesinleşme ve teslim tarihleri YYYY-AA-GG biçiminde olmalıdır.',
            ))
        elif delivered < finalized:
            findings.append(AdministrativeFinding(
                "DELIVERY_BEFORE_FINALIZATION", "ERROR", "MPYY 34/4, 35/2",
                "Digital delivery cannot precede plan finalization.",
            ))
        elif (delivered - finalized).days > 15:
            findings.append(AdministrativeFinding(
                "LATE_DIGITAL_DELIVERY", "ERROR", "MPYY 34/4, 35/2",
                "Finalized plan was delivered after the fifteen-day period.",
            ))
        files = manifest.get("files", [])
        if not isinstance(files, list):
            raise ValueError('files bir JSON dizisi olmalıdır.')
        required = set(cls.COMMON_ROLES)
        if level in {"NIP", "UIP"}:
            required.update(cls.IMAR_ROLES)
        represented = set()
        base = Path(base_directory).resolve()
        for index, item in enumerate(files, start=1):
            if not isinstance(item, Mapping):
                findings.append(AdministrativeFinding(
                    "INVALID_DELIVERY_FILE", "ERROR", "MPYY 34-35",
                    f'Delivery file {index} bir JSON nesnesi olmalıdır.',
                ))
                continue
            role = str(item.get("role", "")).strip().upper()
            if role in represented:
                findings.append(AdministrativeFinding(
                    "DUPLICATE_DELIVERY_ROLE", "ERROR", "MPYY 34-35",
                    "Digital delivery role is duplicated: " + role,
                ))
            represented.add(role)
            cls._audit_local_file(item, role, base, findings)
            if role == "GEOSPATIAL_PLAN_DATA" and not _boolean(item.get("machine_readable")):
                findings.append(AdministrativeFinding(
                    "GEOSPATIAL_DATA_NOT_MACHINE_READABLE", "ERROR", "MPYY 34/4-5, 35/3",
                    "Geospatial plan data is not declared machine-readable.",
                ))
        for missing in sorted(required - represented):
            findings.append(AdministrativeFinding(
                "MISSING_DELIVERY_" + missing, "ERROR", "MPYY 34/4, 35/3",
                'Sayısal teslim bileşeni eksik: ' + missing,
            ))
        return _result("MPYY_DIGITAL_DELIVERY", level, findings)

    @classmethod
    def audit_file(cls, manifest_path: str | Path) -> AdministrativeAuditResult:
        path = Path(manifest_path).resolve()
        payload = _read_manifest(path)
        return cls.audit(payload, path.parent)

    @staticmethod
    def _audit_local_file(item, role, base, findings) -> None:
        relative = str(item.get("path", "")).strip()
        if not relative:
            findings.append(AdministrativeFinding(
                "MISSING_DELIVERY_PATH", "ERROR", "MPYY 34-35",
                'Sayısal teslim dosya yolu eksik: ' + role,
            ))
            return
        path = (base / relative).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            findings.append(AdministrativeFinding(
                "DELIVERY_PATH_OUTSIDE_PACKAGE", "ERROR", "MPYY 34-35",
                "Digital delivery file is outside the package: " + role,
            ))
            return
        if not path.is_file():
            findings.append(AdministrativeFinding(
                "DELIVERY_FILE_NOT_FOUND", "ERROR", "MPYY 34-35",
                'Sayısal teslim dosyası eksik: ' + role,
            ))
            return
        declared = str(item.get("sha256", "")).strip().lower()
        if not _valid_sha256(declared):
            findings.append(AdministrativeFinding(
                "INVALID_DELIVERY_SHA256", "ERROR", "MPYY 34-35",
                'Sayısal teslim dosyasının geçerli SHA-256 kimliği yok: ' + role,
            ))
        elif _file_hash(path) != declared:
            findings.append(AdministrativeFinding(
                "DELIVERY_CHECKSUM_MISMATCH", "ERROR", "MPYY 34-35",
                "Digital delivery file content does not match its identity: " + role,
            ))


def audit_manifest_file(engine, manifest_path: str | Path) -> AdministrativeAuditResult:
    """Reads a JSON manifest and dispatches it to a non-file-based engine."""
    return engine.audit(_read_manifest(Path(manifest_path)))


def write_administrative_report(
    result: AdministrativeAuditResult, output_path: str | Path
) -> str:
    path = Path(output_path)
    payload = asdict(result)
    payload["error_count"] = result.error_count
    payload["warning_count"] = result.warning_count
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return str(path)


def _read_manifest(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('İdari denetim bildirimi okunamadı: ' + str(error)) from error
    if not isinstance(payload, Mapping):
        raise ValueError('İdari denetim bildiriminin kökü bir JSON nesnesi olmalıdır.')
    return payload


def _plan_level(manifest: Mapping[str, Any]) -> str:
    level = str(manifest.get("plan_level", "")).strip().upper()
    if level not in PLAN_LEVELS:
        raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
    return level


def _result(
    audit_type: str, plan_level: str, findings: list[AdministrativeFinding]
) -> AdministrativeAuditResult:
    status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
        "REVIEW_REQUIRED" if findings else "COMPLETE"
    )
    return AdministrativeAuditResult(audit_type, plan_level, status, findings)


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _boolean(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "evet"}


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
