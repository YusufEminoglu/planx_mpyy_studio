"""MPYY Articles 8, 21, and 22 evidence provenance audit."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class EvidenceFinding:
    code: str
    severity: str
    category: str
    message: str


@dataclass
class EvidenceProvenanceResult:
    plan_level: str
    status: str
    item_count: int
    verified_file_count: int
    findings: list[EvidenceFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class EvidenceProvenanceAuditEngine:
    """Checks whether planning evidence can be traced and reproduced."""

    BASE_CATEGORIES = (
        "TOPOGRAPHY",
        "GEOLOGY",
        "HYDROGEOLOGY",
        "CURRENT_LAND_USE",
        "AGRICULTURE_FOREST",
        "INFRASTRUCTURE",
    )
    CONDITIONAL_CATEGORIES = {
        "coastal": "COAST",
        "water_basin": "WATER_BASIN",
        "protected_area": "PROTECTED_AREA",
        "hazard_exposure": "HAZARD",
    }

    @classmethod
    def audit(
        cls,
        manifest: Mapping[str, Any],
        verify_local_files: bool = True,
    ) -> EvidenceProvenanceResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('Kanıt plan_level değeri MSP, CDP, NIP veya UIP olmalıdır.')
        items = manifest.get("evidence_items", [])
        if not isinstance(items, list):
            raise ValueError('evidence_items bir JSON dizisi olmalıdır.')
        context = manifest.get("context_flags", {})
        if not isinstance(context, Mapping):
            raise ValueError('context_flags bir JSON nesnesi olmalıdır.')

        findings = []
        verified_files = 0
        categories = set()
        seen_ids = set()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                findings.append(EvidenceFinding(
                    "INVALID_ITEM", "ERROR", "", f'Evidence item {index} bir JSON nesnesi olmalıdır.'
                ))
                continue
            category = str(item.get("category", "")).strip().upper()
            item_id = str(item.get("evidence_id", "")).strip()
            categories.add(category)
            if not item_id:
                findings.append(EvidenceFinding(
                    "MISSING_EVIDENCE_ID", "ERROR", category, 'Dayanak kimliği gereklidir.'
                ))
            elif item_id in seen_ids:
                findings.append(EvidenceFinding(
                    "DUPLICATE_EVIDENCE_ID", "ERROR", category, "Evidence ID is duplicated."
                ))
            seen_ids.add(item_id)
            for field_name in ("source_institution", "version", "crs_authid"):
                if not str(item.get(field_name, "")).strip():
                    findings.append(EvidenceFinding(
                        "MISSING_" + field_name.upper(), "ERROR", category,
                        field_name + ' tekrarlanabilir dayanak için gereklidir.',
                    ))
            if cls._date(item.get("acquisition_date")) is None:
                findings.append(EvidenceFinding(
                    "INVALID_ACQUISITION_DATE", "ERROR", category,
                    'acquisition_date alanı YYYY-AA-GG biçiminde olmalıdır.',
                ))
            scale = cls._positive_number(item.get("scale_denominator"))
            resolution = cls._positive_number(item.get("resolution_m"))
            if scale is None and resolution is None:
                findings.append(EvidenceFinding(
                    "MISSING_SCALE_RESOLUTION", "WARNING", category,
                    "Scale denominator or metric resolution is not recorded.",
                ))
            declared_hash = str(item.get("sha256", "")).strip().lower()
            if len(declared_hash) != 64 or any(char not in "0123456789abcdef" for char in declared_hash):
                findings.append(EvidenceFinding(
                    "INVALID_SHA256", "ERROR", category, 'Geçerli SHA-256 kimliği gereklidir.'
                ))
            local_path = str(item.get("local_path", "")).strip()
            if verify_local_files and local_path:
                path = Path(local_path)
                if not path.is_file():
                    findings.append(EvidenceFinding(
                        "LOCAL_FILE_MISSING", "ERROR", category, 'Belirtilen yerel dayanak dosyası eksik.'
                    ))
                elif declared_hash and cls._file_hash(path) != declared_hash:
                    findings.append(EvidenceFinding(
                        "CHECKSUM_MISMATCH", "ERROR", category,
                        "Local evidence file does not match its declared SHA-256 identity.",
                    ))
                else:
                    verified_files += 1

        required = set(cls.BASE_CATEGORIES)
        required.update(
            category for flag, category in cls.CONDITIONAL_CATEGORIES.items()
            if cls._boolean(context.get(flag))
        )
        for missing in sorted(required - categories):
            findings.append(EvidenceFinding(
                "MISSING_THRESHOLD_CATEGORY", "ERROR", missing,
                'Gerekli 22. madde dayanak kategorisi temsil edilmiyor.',
            ))
        status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLETE"
        )
        return EvidenceProvenanceResult(level, status, len(items), verified_files, findings)

    @classmethod
    def audit_file(cls, manifest_path: str | Path, verify_local_files: bool = True):
        path = Path(manifest_path)
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Kanıt bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(manifest, Mapping):
            raise ValueError('Kanıt bildiriminin kökü bir JSON nesnesi olmalıdır.')
        return cls.audit(manifest, verify_local_files)

    @staticmethod
    def write_report(result: EvidenceProvenanceResult, output_path: str | Path) -> str:
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
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _date(value: Any) -> date | None:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _positive_number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0.0 else None

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "evet"}
