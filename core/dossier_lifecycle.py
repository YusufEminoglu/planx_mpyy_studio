"""MPYY plan-dossier scaffolding, completeness, and publication audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class DossierFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class DossierAuditResult:
    audit_type: str
    plan_level: str
    status: str
    findings: list[DossierFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class MPYYDossierScaffoldEngine:
    """Creates a non-destructive, traceable MPYY dossier directory."""

    PURPOSES = {"NEW_PLAN", "REVISION", "ADDITION", "PLAN_CHANGE"}
    DIRECTORIES = (
        "01_plan_components", "02_research_evidence", "03_institution_opinions",
        "04_approval", "05_publication_objections", "06_digital_delivery",
        "07_audit_reports",
    )

    @classmethod
    def create(
        cls, output_directory: str | Path, plan_level: str, purpose: str
    ) -> dict[str, Any]:
        level = str(plan_level).strip().upper()
        normalized_purpose = str(purpose).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
        if normalized_purpose not in cls.PURPOSES:
            raise ValueError('purpose NEW_PLAN, REVISION, ADDITION veya PLAN_CHANGE olmalıdır.')
        root = Path(output_directory).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise ValueError('Çıktı plan dosyası klasörü boş olmalıdır.')
        for directory in cls.DIRECTORIES:
            (root / directory).mkdir()
        manifest = {
            "schema_version": 1,
            "plan_level": level,
            "purpose": normalized_purpose,
            "lifecycle_status": "DRAFT",
            "context_flags": {
                "mixed_use": False,
                "coastal": False,
                "conservation": False,
                "urban_design": False,
            },
            "files": [],
        }
        cls._atomic_json(root / "dossier_manifest.json", manifest)
        cls._atomic_json(root / "02_research_evidence" / "evidence_freshness_manifest.json", {
            "schema_version": 1, "plan_level": level, "evidence_items": []
        })
        cls._atomic_json(root / "05_publication_objections" / "publication_manifest.json", {
            "schema_version": 1, "plan_level": level, "lifecycle_status": "DRAFT",
            "publication": {}, "objections": [],
        })
        cls._atomic_json(root / "02_research_evidence" / "participation_manifest.json", {
            "schema_version": 1, "plan_level": level, "events": [],
        })
        cls._atomic_json(root / "02_research_evidence" / "cancelled_plan_evidence.json", {
            "schema_version": 1, "plan_level": level, "prior_plan_cancelled": False,
            "reevaluations": [],
        })
        cls._atomic_json(root / "01_plan_components" / "component_manifest.json", {
            "schema_version": 1, "plan_id": "", "plan_version": "",
            "plan_level": level, "purpose": normalized_purpose, "components": [],
        })
        cls._atomic_json(root / "04_approval" / "approval_sheet_manifest.json", {
            "schema_version": 1, "plan_level": level, "plan_transaction_number": "",
            "approval_date": "", "approval_number": "", "sheets": [],
        })
        cls._atomic_json(root / "06_digital_delivery" / "digital_delivery_manifest.json", {
            "schema_version": 1, "plan_level": level, "plan_transaction_number": "",
            "format_profile_id": "", "crs_authid": "", "delivery_receipt": "",
            "destination_authority": "PROVINCIAL_DIRECTORATE",
            "finalization_date": "", "delivery_date": "", "files": [],
        })
        cls._atomic_json(root / "01_plan_components" / "plan_note_links.json", {
            "schema_version": 1, "plan_level": level, "decision_codes": [],
            "require_every_decision_linked": False, "notes": [],
        })
        cls._atomic_json(root / "01_plan_components" / "version_chain.json", {
            "schema_version": 1, "plan_id": "", "versions": [],
        })
        return {
            "output_directory": str(root),
            "manifest": str(root / "dossier_manifest.json"),
            "directory_count": len(cls.DIRECTORIES),
        }

    @staticmethod
    def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(path)


class MPYYDossierCompletenessEngine:
    """Checks role coverage, file presence, and declared file identities."""

    COMMON_ROLES = {
        "plan_sheet": "MPYY 7/1-b, 31/3",
        "official_display": "MPYY 10",
        "plan_notes": "MPYY 7/1-b, 31/3",
        "plan_report": "MPYY 7/1-b, 9, 31/3",
        "author_signature": "MPYY 21/4, 31/3",
    }
    LEVEL_ROLES = {
        "MSP": {"thematic_maps": "MPYY 15", "action_plan": "MPYY 15/4, 16"},
        "CDP": {"analysis_synthesis": "MPYY 19-20"},
        "NIP": {
            "current_base_map": "MPYY 21/1", "geological_survey": "MPYY 21/6-7",
            "analysis_synthesis": "MPYY 21/3", "institution_opinions": "MPYY 8",
        },
        "UIP": {
            "current_base_map": "MPYY 21/1", "geological_survey": "MPYY 21/6-7",
            "upper_plan_analysis": "MPYY 6/2, 21/2", "institution_opinions": "MPYY 8",
        },
    }
    CONTEXT_ROLES = {
        "mixed_use": {
            "mixed_use_ratios": "MPYY 9/5, 21/10",
            "mixed_use_infrastructure": "MPYY 9/5, 21/10",
        },
        "coastal": {"coastal_boundary": "MPYY 21/1"},
        "conservation": {"conservation_inventory": "MPYY 27"},
        "urban_design": {"urban_design_project": "MPYY 30"},
    }
    PURPOSE_ROLES = {
        "PLAN_CHANGE": {
            "detailed_change_rationale": "MPYY 9/4",
            "necessity_analyses": "MPYY 9/4",
        }
    }
    FINALIZED_ROLES = {
        "approval_decision": "MPYY 32",
        "suspension_start_minutes": "MPYY 33/3",
        "suspension_end_minutes": "MPYY 33/3",
        "digital_dataset": "MPYY 34/4-5, 35/3",
        "provincial_delivery_receipt": "MPYY 34/4, 35/2",
    }

    @classmethod
    def audit(cls, manifest: Mapping[str, Any], base_directory: str | Path) -> DossierAuditResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        purpose = str(manifest.get("purpose", "NEW_PLAN")).strip().upper()
        lifecycle = str(manifest.get("lifecycle_status", "DRAFT")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
        if purpose not in MPYYDossierScaffoldEngine.PURPOSES:
            raise ValueError('Plan dosyası amacı geçersizdir.')
        if lifecycle not in {"DRAFT", "APPROVED", "FINALIZED"}:
            raise ValueError('lifecycle_status DRAFT, APPROVED veya FINALIZED olmalıdır.')
        flags = manifest.get("context_flags", {})
        files = manifest.get("files", [])
        if not isinstance(flags, Mapping) or not isinstance(files, list):
            raise ValueError('context_flags bir nesne, files ise bir dizi olmalıdır.')
        required = dict(cls.COMMON_ROLES)
        required.update(cls.LEVEL_ROLES[level])
        required.update(cls.PURPOSE_ROLES.get(purpose, {}))
        for flag, roles in cls.CONTEXT_ROLES.items():
            if cls._boolean(flags.get(flag)):
                required.update(roles)
        if lifecycle == "FINALIZED":
            required.update(cls.FINALIZED_ROLES)

        findings: list[DossierFinding] = []
        base = Path(base_directory).resolve()
        by_role: dict[str, Mapping[str, Any]] = {}
        for index, item in enumerate(files, start=1):
            if not isinstance(item, Mapping):
                findings.append(DossierFinding(
                    "INVALID_FILE_ENTRY", "ERROR", "MPYY 31", f"File entry {index} is not an object."
                ))
                continue
            role = str(item.get("role", "")).strip().lower()
            if not role:
                findings.append(DossierFinding(
                    "MISSING_FILE_ROLE", "ERROR", "MPYY 31", f'File entry {index} rolü yok.'
                ))
                continue
            if role in by_role:
                findings.append(DossierFinding(
                    "DUPLICATE_FILE_ROLE", "ERROR", "MPYY 31", "Duplicate file role: " + role
                ))
                continue
            by_role[role] = item
            cls._audit_file(item, role, base, findings)
        for role, article in required.items():
            if role not in by_role:
                findings.append(DossierFinding(
                    "MISSING_" + role.upper(), "ERROR", article,
                    'Gerekli plan dosyası rolü belirtilmemiş: ' + role,
                ))
        status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLETE"
        )
        return DossierAuditResult("MPYY_DOSSIER_COMPLETENESS", level, status, findings)

    @classmethod
    def audit_file(cls, manifest_path: str | Path) -> DossierAuditResult:
        path = Path(manifest_path).resolve()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Plan dosyası bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('Plan dosyası bildiriminin kökü bir JSON nesnesi olmalıdır.')
        return cls.audit(payload, path.parent)

    @staticmethod
    def _audit_file(
        item: Mapping[str, Any], role: str, base: Path, findings: list[DossierFinding]
    ) -> None:
        relative = str(item.get("path", "")).strip()
        if not relative:
            findings.append(DossierFinding(
                "MISSING_FILE_PATH", "ERROR", "MPYY 31", 'Rol için dosya yolu belirtilmemiş: ' + role
            ))
            return
        path = (base / relative).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            findings.append(DossierFinding(
                "PATH_OUTSIDE_DOSSIER", "ERROR", "MPYY 31",
                "Declared file is outside the dossier directory: " + role,
            ))
            return
        if not path.is_file():
            findings.append(DossierFinding(
                "FILE_NOT_FOUND", "ERROR", "MPYY 31", 'Belirtilen plan dosyası eksik: ' + role
            ))
            return
        declared = str(item.get("sha256", "")).strip().lower()
        if len(declared) != 64 or any(char not in "0123456789abcdef" for char in declared):
            findings.append(DossierFinding(
                "INVALID_FILE_SHA256", "ERROR", "MPYY 34-35",
                'Rol için geçerli SHA-256 kimliği gereklidir: ' + role,
            ))
        elif MPYYDossierCompletenessEngine._file_hash(path) != declared:
            findings.append(DossierFinding(
                "FILE_CHECKSUM_MISMATCH", "ERROR", "MPYY 34-35",
                "File content does not match the declared identity: " + role,
            ))

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _boolean(value: Any) -> bool:
        return value is True or str(value).strip().lower() in {"1", "true", "yes", "evet"}


class MPYYPublicationRegisterEngine:
    """Audits Article 33 publication and objection chronology."""

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> DossierAuditResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
        publication = manifest.get("publication", {})
        objections = manifest.get("objections", [])
        if not isinstance(publication, Mapping) or not isinstance(objections, list):
            raise ValueError('publication bir nesne, objections ise bir dizi olmalıdır.')
        findings: list[DossierFinding] = []
        approval = cls._required_date(publication, "approval_date", findings, "MPYY 33/1")
        physical = cls._required_date(publication, "physical_start_date", findings, "MPYY 33/1")
        web = cls._required_date(publication, "web_start_date", findings, "MPYY 33/1")
        end = cls._required_date(publication, "end_date", findings, "MPYY 33/1")
        holidays = cls._holidays(publication.get("official_holidays", []), findings)
        if approval and physical and physical < approval:
            findings.append(DossierFinding(
                "PUBLICATION_BEFORE_APPROVAL", "ERROR", "MPYY 33/1",
                'Askı plan onayından önce başlayamaz.',
            ))
        elif approval and physical and cls._business_days_after(approval, physical, holidays) > 15:
            findings.append(DossierFinding(
                "LATE_PUBLICATION", "ERROR", "MPYY 33/1",
                "Physical publication started after fifteen business days.",
            ))
        if physical and web and physical != web:
            findings.append(DossierFinding(
                "PUBLICATION_NOT_SIMULTANEOUS", "ERROR", "MPYY 33/1",
                "Physical and web publication start dates are not simultaneous.",
            ))
        if physical and end and end < physical:
            findings.append(DossierFinding(
                "INVALID_PUBLICATION_ORDER", "ERROR", "MPYY 33/1",
                "Publication end date cannot precede its start date.",
            ))
        elif physical and end and (end - physical).days < 30:
            findings.append(DossierFinding(
                "SHORT_PUBLICATION_PERIOD", "ERROR", "MPYY 33/1",
                "Publication period is shorter than thirty days.",
            ))
        for key in ("start_minutes_two_signatures", "end_minutes_two_signatures", "unit_head_signed"):
            if not cls._boolean(publication.get(key)):
                findings.append(DossierFinding(
                    "MISSING_" + key.upper(), "ERROR", "MPYY 33/3",
                    'Askı tutanağı imza dayanağı eksik: ' + key,
                ))
        if level in {"NIP", "UIP"} and not cls._boolean(publication.get("local_announcement_evidenced")):
            findings.append(DossierFinding(
                "MISSING_LOCAL_ANNOUNCEMENT", "ERROR", "MPYY 33/2",
                'İmar planı için yerel ilan dayanağı gereklidir.',
            ))
        for index, objection in enumerate(objections, start=1):
            if not isinstance(objection, Mapping):
                findings.append(DossierFinding(
                    "INVALID_OBJECTION", "ERROR", "MPYY 33/4-5",
                    f'Objection {index} bir JSON nesnesi olmalıdır.',
                ))
                continue
            cls._audit_objection(objection, index, physical, end, findings)
        status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLETE"
        )
        return DossierAuditResult("MPYY_PUBLICATION_REGISTER", level, status, findings)

    @classmethod
    def _audit_objection(cls, item, index, start, end, findings) -> None:
        received = cls._optional_date(item.get("received_date"))
        forwarded = cls._optional_date(item.get("forwarded_date"))
        decided = cls._optional_date(item.get("decision_date"))
        if received is None:
            findings.append(DossierFinding(
                "INVALID_OBJECTION_DATE", "ERROR", "MPYY 33/4",
                f'Objection {index} received_date alanı eksik veya geçersiz.',
            ))
        elif start and end and not start <= received <= end:
            findings.append(DossierFinding(
                "OBJECTION_OUTSIDE_PUBLICATION", "ERROR", "MPYY 33/4",
                f"Objection {index} was not received during the publication period.",
            ))
        if forwarded is None or (end and (forwarded < end or (forwarded - end).days > 30)):
            findings.append(DossierFinding(
                "LATE_OR_MISSING_OBJECTION_FORWARDING", "ERROR", "MPYY 33/5",
                f"Objection {index} was not forwarded within thirty days after publication.",
            ))
        if decided is None or (
            forwarded and (decided < forwarded or (decided - forwarded).days > 30)
        ):
            findings.append(DossierFinding(
                "LATE_OR_MISSING_OBJECTION_DECISION", "ERROR", "MPYY 33/5",
                f"Objection {index} was not decided within thirty days after forwarding.",
            ))
        if cls._boolean(item.get("plan_changed")) and not cls._present(item.get("republication_start_date")):
            findings.append(DossierFinding(
                "MISSING_REPUBLICATION", "ERROR", "MPYY 33/6",
                f"Objection {index} changed the plan but republication is not evidenced.",
            ))

    @staticmethod
    def write_report(result: DossierAuditResult, output_path: str | Path) -> str:
        path = Path(output_path)
        payload = asdict(result)
        payload["error_count"] = result.error_count
        payload["warning_count"] = result.warning_count
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return str(path)

    @classmethod
    def audit_file(cls, manifest_path: str | Path) -> DossierAuditResult:
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('İlan bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('İlan bildiriminin kökü bir JSON nesnesi olmalıdır.')
        return cls.audit(payload)

    @staticmethod
    def _required_date(source, key, findings, article):
        parsed = MPYYPublicationRegisterEngine._optional_date(source.get(key))
        if parsed is None:
            findings.append(DossierFinding(
                "INVALID_" + key.upper(), "ERROR", article, key + ' eksik veya geçersiz.'
            ))
        return parsed

    @staticmethod
    def _holidays(values, findings) -> set[date]:
        if not isinstance(values, list):
            findings.append(DossierFinding(
                "INVALID_OFFICIAL_HOLIDAYS", "ERROR", "MPYY 33/1",
                'official_holidays alanı YYYY-AA-GG tarihlerinden oluşan bir dizi olmalıdır.',
            ))
            return set()
        result = set()
        for value in values:
            parsed = MPYYPublicationRegisterEngine._optional_date(value)
            if parsed is None:
                findings.append(DossierFinding(
                    "INVALID_OFFICIAL_HOLIDAY", "ERROR", "MPYY 33/1",
                    'Resmî tatil tarihi geçersiz.',
                ))
            else:
                result.add(parsed)
        return result

    @staticmethod
    def _business_days_after(start: date, end: date, holidays: set[date]) -> int:
        current = start + timedelta(days=1)
        count = 0
        while current <= end:
            if current.weekday() < 5 and current not in holidays:
                count += 1
            current += timedelta(days=1)
        return count

    @staticmethod
    def _optional_date(value: Any) -> date | None:
        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _boolean(value: Any) -> bool:
        return value is True or str(value).strip().lower() in {"1", "true", "yes", "evet"}

    @staticmethod
    def _present(value: Any) -> bool:
        return value not in (None, "", [], {})


def write_dossier_report(result: DossierAuditResult, output_path: str | Path) -> str:
    """Writes a deterministic-identity report for dossier completeness."""
    return MPYYPublicationRegisterEngine.write_report(result, output_path)
