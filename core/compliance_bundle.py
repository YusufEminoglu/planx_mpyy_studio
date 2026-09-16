"""Consolidates verified MPYY JSON audit reports without inventing a score."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid


class MPYYComplianceBundleEngine:
    FAILURE_STATUSES = {"INCOMPLETE", "NON_COMPLIANT", "INVALID"}
    REVIEW_STATUSES = {"REVIEW_REQUIRED", "PENDING", "EXCEPTION_REVIEW"}
    SUCCESS_STATUSES = {"COMPLETE", "COMPLIANT"}

    @classmethod
    def consolidate(cls, input_directory: str | Path, output_path: str | Path) -> dict[str, Any]:
        directory = Path(input_directory)
        output = Path(output_path).resolve()
        if not directory.is_dir():
            raise ValueError('Girdi denetim raporları klasörü bulunamadı.')
        reports = []
        for path in sorted(directory.glob("*.json")):
            if path.resolve() == output:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                reports.append({"file": path.name, "status": "INVALID", "hash_valid": False, "error": str(error)})
                continue
            if not isinstance(payload, Mapping):
                reports.append({"file": path.name, "status": "INVALID", "hash_valid": False})
                continue
            declared_hash = str(payload.get("content_sha256", "")).lower()
            content = dict(payload)
            content.pop("content_sha256", None)
            canonical = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            status = str(payload.get("status", "UNKNOWN")).strip().upper()
            reports.append({
                "file": path.name,
                "audit_type": payload.get("audit_type") or payload.get("plan_level") or "",
                "status": status,
                "hash_valid": declared_hash == actual_hash,
                "content_sha256": declared_hash,
            })
        if not reports:
            overall = "EMPTY"
        elif any(
            not item["hash_valid"]
            or item["status"] in cls.FAILURE_STATUSES
            or item["status"] not in cls.FAILURE_STATUSES | cls.REVIEW_STATUSES | cls.SUCCESS_STATUSES
            for item in reports
        ):
            overall = "INCOMPLETE"
        elif any(item["status"] in cls.REVIEW_STATUSES for item in reports):
            overall = "REVIEW_REQUIRED"
        else:
            overall = "COMPLETE"
        result = {
            "schema_version": 1,
            "status": overall,
            "report_count": len(reports),
            "verified_report_count": sum(item["hash_valid"] for item in reports),
            "reports": reports,
        }
        canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        result["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)
        return result
