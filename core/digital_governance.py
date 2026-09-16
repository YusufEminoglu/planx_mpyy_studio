"""Profile-driven MPYY digital package and document governance tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping
import uuid

from .plan_stage_audit import PLAN_LEVELS


@dataclass(frozen=True)
class GovernanceFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class GovernanceAuditResult:
    audit_type: str
    status: str
    findings: list[GovernanceFinding] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class MPYYGeoPackageProfileEngine:
    """Validates a GeoPackage against an externally supplied schema profile."""

    @classmethod
    def audit(cls, gpkg_path: str | Path, profile: Mapping[str, Any]) -> GovernanceAuditResult:
        path = Path(gpkg_path).resolve()
        if not path.is_file() or path.suffix.lower() != ".gpkg":
            raise ValueError('Okunabilir bir .gpkg dosyası gereklidir.')
        profile_id = str(profile.get("profile_id", "")).strip()
        profile_version = str(profile.get("profile_version", "")).strip()
        tables = profile.get("tables", [])
        if not profile_id or not profile_version:
            raise ValueError('Şema için profile_id ve profile_version gereklidir.')
        if not isinstance(tables, list) or not tables:
            raise ValueError('Şema profili tabloları boş olmayan bir JSON dizisi olmalıdır.')
        identity_details = {}
        if "content_sha256" in profile or "import_mapping" in profile:
            from .profile_identity import MPYYProfileIdentityEngine

            identity = MPYYProfileIdentityEngine.audit(profile)
            identity_details = {"profile_identity": identity.details}
            if identity.error_count:
                return _result("MPYY_GPKG_SCHEMA_PROFILE", identity.findings, {
                    "profile_id": profile_id, "profile_version": profile_version,
                    "checked_table_count": 0, "declared_table_count": len(tables),
                    **identity_details,
                })
        findings: list[GovernanceFinding] = []
        checked_tables = 0
        try:
            with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
                available = {
                    row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
                    )
                }
                geometry_rows = {}
                if "gpkg_geometry_columns" in available:
                    geometry_rows = {
                        row[0]: {"column": row[1], "type": row[2], "srs_id": row[3]}
                        for row in connection.execute(
                            "SELECT table_name,column_name,geometry_type_name,srs_id "
                            "FROM gpkg_geometry_columns"
                        )
                    }
                seen = set()
                for index, table_profile in enumerate(tables, start=1):
                    if not isinstance(table_profile, Mapping):
                        findings.append(GovernanceFinding(
                            "INVALID_TABLE_PROFILE", "ERROR", "MPYY 34-35",
                            f'Table profile {index} bir JSON nesnesi olmalıdır.',
                        ))
                        continue
                    table = str(table_profile.get("name", "")).strip()
                    if not table:
                        findings.append(GovernanceFinding(
                            "MISSING_TABLE_NAME", "ERROR", "MPYY 34-35",
                            f'Table profile {index} adı yok.',
                        ))
                        continue
                    if table in seen:
                        findings.append(GovernanceFinding(
                            "DUPLICATE_TABLE_PROFILE", "ERROR", "MPYY 34-35",
                            "Schema profile repeats table: " + table,
                        ))
                        continue
                    seen.add(table)
                    if table not in available:
                        findings.append(GovernanceFinding(
                            "MISSING_REQUIRED_TABLE", "ERROR", "MPYY 34-35",
                            'GeoPackage tablosu eksik: ' + table,
                        ))
                        continue
                    checked_tables += 1
                    fields = cls._fields(connection, table)
                    cls._audit_fields(table_profile, table, fields, findings)
                    cls._audit_geometry(table_profile, table, geometry_rows.get(table), findings)
        except sqlite3.Error as error:
            raise ValueError('GeoPackage şeması incelenemedi: ' + str(error)) from error
        return _result("MPYY_GPKG_SCHEMA_PROFILE", findings, {
            "profile_id": profile_id, "profile_version": profile_version,
            "checked_table_count": checked_tables, "declared_table_count": len(tables),
            **identity_details,
        })

    @classmethod
    def audit_files(cls, gpkg_path: str | Path, profile_path: str | Path):
        from .profile_identity import read_profile_json

        return cls.audit(gpkg_path, read_profile_json(profile_path))

    @staticmethod
    def _fields(connection, table):
        quoted = '"' + table.replace('"', '""') + '"'
        return {
            row[1]: {"type": str(row[2]).upper(), "not_null": bool(row[3]), "primary_key": bool(row[5])}
            for row in connection.execute("PRAGMA table_info(" + quoted + ")")
        }

    @staticmethod
    def _audit_fields(profile, table, fields, findings):
        declared = profile.get("fields", [])
        if not isinstance(declared, list):
            findings.append(GovernanceFinding(
                "INVALID_FIELD_PROFILE", "ERROR", "MPYY 34-35",
                'fields alanı tablo için dizi olmalıdır: ' + table,
            ))
            return
        for item in declared:
            if not isinstance(item, Mapping):
                findings.append(GovernanceFinding(
                    "INVALID_FIELD_PROFILE", "ERROR", "MPYY 34-35",
                    'Alan profili tabloda bir nesne olmalıdır: ' + table,
                ))
                continue
            name = str(item.get("name", "")).strip()
            if not name or name not in fields:
                findings.append(GovernanceFinding(
                    "MISSING_REQUIRED_FIELD", "ERROR", "MPYY 34-35",
                    table + ' için gerekli alan eksik: ' + name,
                ))
                continue
            expected_type = str(item.get("type", "")).strip().upper()
            if expected_type and not fields[name]["type"].startswith(expected_type):
                findings.append(GovernanceFinding(
                    "FIELD_TYPE_MISMATCH", "ERROR", "MPYY 34-35",
                    table + ' satır bulundu.' + name + " does not match declared type " + expected_type + ' satır bulundu.',
                ))
            if item.get("not_null") is True and not (
                fields[name]["not_null"] or fields[name]["primary_key"]
            ):
                findings.append(GovernanceFinding(
                    "FIELD_NULLABILITY_MISMATCH", "ERROR", "MPYY 34-35",
                    table + ' satır bulundu.' + name + " is not declared NOT NULL.",
                ))
            if item.get("primary_key") is True and not fields[name]["primary_key"]:
                findings.append(GovernanceFinding(
                    "FIELD_PRIMARY_KEY_MISMATCH", "ERROR", "MPYY 34-35",
                    table + ' satır bulundu.' + name + " is not declared as a primary key.",
                ))

    @staticmethod
    def _audit_geometry(profile, table, geometry, findings):
        expected_type = str(profile.get("geometry_type", "")).strip().upper()
        expected_srs = profile.get("srs_id")
        if not expected_type and expected_srs in (None, ""):
            return
        if geometry is None:
            findings.append(GovernanceFinding(
                "MISSING_GEOMETRY_REGISTRATION", "ERROR", "MPYY 34-35",
                "Spatial table is not registered in gpkg_geometry_columns: " + table,
            ))
            return
        if expected_type and str(geometry["type"]).upper() != expected_type:
            findings.append(GovernanceFinding(
                "GEOMETRY_TYPE_MISMATCH", "ERROR", "MPYY 34-35",
                table + " geometry type does not match the profile.",
            ))
        if expected_srs not in (None, ""):
            try:
                srs_matches = int(expected_srs) == int(geometry["srs_id"])
            except (TypeError, ValueError):
                srs_matches = False
            if not srs_matches:
                findings.append(GovernanceFinding(
                    "SRS_ID_MISMATCH", "ERROR", "MPYY 34-35",
                    table + " SRS ID does not match the profile.",
                ))


class MPYYDossierInventoryEngine:
    """Builds a deterministic recursive file inventory for an MPYY dossier."""

    @classmethod
    def build(cls, input_directory: str | Path, output_path: str | Path) -> GovernanceAuditResult:
        root = Path(input_directory).resolve()
        output = Path(output_path).resolve()
        if not root.is_dir():
            raise ValueError('Girdi plan dosyası klasörü bulunamadı.')
        entries = []
        findings: list[GovernanceFinding] = []
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().lower()):
            if path.resolve() == output or not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(root)
            except ValueError:
                findings.append(GovernanceFinding(
                    "FILE_OUTSIDE_DOSSIER", "ERROR", "MPYY 34-35",
                    "A linked file resolves outside the dossier: " + str(path),
                ))
                continue
            entries.append({
                "path": relative.as_posix(), "size_bytes": resolved.stat().st_size,
                "sha256": _file_hash(resolved),
            })
        if not entries:
            findings.append(GovernanceFinding(
                "EMPTY_DOSSIER", "ERROR", "MPYY 31, 34-35",
                'Plan dosyası envanteri için kullanılabilir dosya yok.',
            ))
        result = _result("MPYY_DOSSIER_INVENTORY", findings, {
            "root_name": root.name, "file_count": len(entries),
            "total_size_bytes": sum(item["size_bytes"] for item in entries), "files": entries,
        })
        write_governance_report(result, output)
        return result


class MPYYPlanNoteDecisionLinkEngine:
    """Audits explicit links between plan decisions and plan notes."""

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> GovernanceAuditResult:
        level = str(manifest.get("plan_level", "")).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('plan_level MSP, CDP, NIP veya UIP olmalıdır.')
        decisions = manifest.get("decision_codes", [])
        notes = manifest.get("notes", [])
        if not isinstance(decisions, list) or not isinstance(notes, list):
            raise ValueError('decision_codes ve notes birer JSON dizisi olmalıdır.')
        decision_set = {str(item).strip() for item in decisions if str(item).strip()}
        findings: list[GovernanceFinding] = []
        if len(decision_set) != len(decisions):
            findings.append(GovernanceFinding(
                "INVALID_OR_DUPLICATE_DECISION_CODE", "ERROR", "MPYY 7/1-b",
                "Decision code list contains an empty or duplicate value.",
            ))
        linked = set()
        seen_notes = set()
        for index, note in enumerate(notes, start=1):
            if not isinstance(note, Mapping):
                findings.append(GovernanceFinding(
                    "INVALID_PLAN_NOTE", "ERROR", "MPYY 7/1-b",
                    f'Plan note {index} bir JSON nesnesi olmalıdır.',
                ))
                continue
            note_id = str(note.get("note_id", "")).strip()
            if not note_id or note_id in seen_notes:
                findings.append(GovernanceFinding(
                    "MISSING_OR_DUPLICATE_NOTE_ID", "ERROR", "MPYY 7/1-b",
                    f'Plan note {index} kimliği eksik veya yinelenmiş.',
                ))
            seen_notes.add(note_id)
            if not str(note.get("text", "")).strip():
                findings.append(GovernanceFinding(
                    "EMPTY_PLAN_NOTE", "ERROR", "MPYY 7/1-b",
                    "Plan note text is empty: " + note_id,
                ))
            codes = note.get("decision_codes", [])
            if not isinstance(codes, list):
                findings.append(GovernanceFinding(
                    "INVALID_NOTE_DECISION_LINKS", "ERROR", "MPYY 7/1-b",
                    'Plan notu decision_codes alanı bir dizi olmalıdır: ' + note_id,
                ))
                continue
            for code in {str(item).strip() for item in codes if str(item).strip()}:
                if code not in decision_set:
                    findings.append(GovernanceFinding(
                        "UNKNOWN_NOTE_DECISION_CODE", "ERROR", "MPYY 7/1-b",
                        note_id + " references an unknown plan decision: " + code,
                    ))
                else:
                    linked.add(code)
        if manifest.get("require_every_decision_linked") is True:
            for missing in sorted(decision_set - linked):
                findings.append(GovernanceFinding(
                    "UNLINKED_PLAN_DECISION", "WARNING", "MPYY 7/1-b",
                    'Karara açıkça bağlanan plan notu yok: ' + missing,
                ))
        return _result("MPYY_PLAN_NOTE_DECISION_LINKS", findings, {
            "plan_level": level, "decision_count": len(decision_set),
            "note_count": len(notes), "linked_decision_count": len(linked),
        })


class MPYYVersionChainEngine:
    """Audits a single-parent content-identity chain for plan dossier versions."""

    @classmethod
    def audit(cls, manifest: Mapping[str, Any]) -> GovernanceAuditResult:
        plan_id = str(manifest.get("plan_id", "")).strip()
        versions = manifest.get("versions", [])
        if not plan_id:
            raise ValueError("plan_id gereklidir.")
        if not isinstance(versions, list) or not versions:
            raise ValueError('versions boş olmayan bir JSON dizisi olmalıdır.')
        findings: list[GovernanceFinding] = []
        seen_versions = set()
        seen_hashes = set()
        previous_hash = ""
        previous_time = None
        for index, item in enumerate(versions, start=1):
            if not isinstance(item, Mapping):
                findings.append(GovernanceFinding(
                    "INVALID_VERSION_ENTRY", "ERROR", "MPYY 7, 31-35",
                    f'Version entry {index} bir JSON nesnesi olmalıdır.',
                ))
                continue
            version = str(item.get("version", "")).strip()
            content_hash = str(item.get("content_sha256", "")).strip().lower()
            parent_hash = str(item.get("parent_sha256", "")).strip().lower()
            timestamp = _datetime(item.get("created_at"))
            if not version or version in seen_versions:
                findings.append(GovernanceFinding(
                    "MISSING_OR_DUPLICATE_VERSION", "ERROR", "MPYY 7, 31-35",
                    'Sürüm kimliği eksik veya yinelenmiş: ' + version,
                ))
            seen_versions.add(version)
            if not _valid_sha256(content_hash) or content_hash in seen_hashes:
                findings.append(GovernanceFinding(
                    "INVALID_OR_DUPLICATE_CONTENT_HASH", "ERROR", "MPYY 34-35",
                    'Sürüm içerik kimliği geçersiz veya yinelenmiş: ' + version,
                ))
            seen_hashes.add(content_hash)
            if index == 1 and parent_hash:
                findings.append(GovernanceFinding(
                    "ROOT_VERSION_HAS_PARENT", "ERROR", "MPYY 7, 31-35",
                    'İlk sürüm bir üst sürüm kimliği belirtmemelidir.',
                ))
            elif index > 1 and parent_hash != previous_hash:
                findings.append(GovernanceFinding(
                    "BROKEN_VERSION_CHAIN", "ERROR", "MPYY 7, 31-35",
                    "Version does not reference the preceding content identity: " + version,
                ))
            if timestamp is None:
                findings.append(GovernanceFinding(
                    "INVALID_VERSION_TIMESTAMP", "ERROR", "MPYY 7, 31-35",
                    'Sürüm zaman damgası ISO-8601 biçiminde olmalıdır: ' + version,
                ))
            elif previous_time and timestamp <= previous_time:
                findings.append(GovernanceFinding(
                    "NON_CHRONOLOGICAL_VERSION", "ERROR", "MPYY 7, 31-35",
                    "Version timestamp is not later than its parent: " + version,
                ))
            previous_hash = content_hash
            previous_time = timestamp or previous_time
        return _result("MPYY_VERSION_CHAIN", findings, {
            "plan_id": plan_id, "version_count": len(versions), "head_sha256": previous_hash,
        })


def audit_governance_manifest(engine, manifest_path: str | Path) -> GovernanceAuditResult:
    return engine.audit(_read_json(manifest_path))


def write_governance_report(result: GovernanceAuditResult, output_path: str | Path) -> str:
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


def _result(audit_type, findings, details):
    status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
        "REVIEW_REQUIRED" if findings else "COMPLETE"
    )
    return GovernanceAuditResult(audit_type, status, findings, details)


def _read_json(path: str | Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('JSON bildirimi okunamadı: ' + str(error)) from error
    if not isinstance(payload, Mapping):
        raise ValueError('JSON kökü bir nesne olmalıdır.')
    return payload


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
