"""Verify declared profile identities without asserting issuer authenticity."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Mapping

from .digital_governance import GovernanceAuditResult, GovernanceFinding


def profile_content_hash(profile: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in profile.items() if key != "content_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_profile_json(path: str | Path) -> Mapping[str, Any]:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON value: " + value)

    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"),
                         object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(payload, Mapping):
        raise ValueError('Profil JSON kökü bir nesne olmalıdır.')
    return payload


class MPYYProfileIdentityEngine:
    @classmethod
    def audit(
        cls, profile: Mapping[str, Any], source_path: str | Path | None = None,
        expected_sha256: str = "",
    ) -> GovernanceAuditResult:
        findings = []

        def error(code, message):
            findings.append(GovernanceFinding(code, "ERROR", "Declared profile integrity", message))

        computed = profile_content_hash(profile)
        for key in ("profile_id", "profile_version"):
            if not isinstance(profile.get(key), str) or not profile[key].strip():
                error("INVALID_PROFILE_METADATA", 'Boş olmayan metin gereklidir: ' + key)
        if not isinstance(profile.get("tables"), list) or not profile["tables"]:
            error("INVALID_PROFILE_TABLES", 'Profil tabloları boş olmayan bir dizi olmalıdır.')
        declared = cls._digest(profile.get("content_sha256"))
        if declared is None:
            error("MISSING_OR_INVALID_PROFILE_HASH", 'Geçerli content_sha256 gereklidir.')
        elif not hmac.compare_digest(declared, computed):
            error("PROFILE_HASH_MISMATCH", "Profile content differs from its declared SHA-256.")
        pinned = None
        if expected_sha256:
            pinned = cls._digest(expected_sha256)
            if pinned is None:
                error("INVALID_EXPECTED_PROFILE_HASH", 'Bağımsız saklanan özet SHA-256 olmalıdır.')
            elif not hmac.compare_digest(pinned, computed):
                error("EXPECTED_PROFILE_HASH_MISMATCH", "Profile differs from the independently retained digest.")
        source_digest = cls._digest(profile.get("source_sha256"))
        if "import_mapping" in profile and source_digest is None:
            error("MISSING_OR_INVALID_SOURCE_HASH", "An imported profile requires a valid source_sha256.")
        source_verified = False
        reconstruction_verified = False
        if source_path is not None:
            digest = hashlib.sha256()
            with Path(source_path).open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if source_digest is None or not hmac.compare_digest(source_digest, digest.hexdigest()):
                error("SOURCE_DICTIONARY_HASH_MISMATCH", "Dictionary bytes differ from the declared source identity.")
            else:
                source_verified = True
            mapping = profile.get("import_mapping")
            if not isinstance(mapping, Mapping):
                error("MISSING_IMPORT_MAPPING", "Reconstruction from CSV requires an explicit import mapping.")
            else:
                from .schema_profile_import import MPYYSchemaProfileImportEngine

                try:
                    reconstructed = MPYYSchemaProfileImportEngine.convert(source_path, mapping)
                except ValueError as exception:
                    error("DICTIONARY_RECONSTRUCTION_FAILED", str(exception))
                else:
                    if not hmac.compare_digest(reconstructed["content_sha256"], computed):
                        error("DICTIONARY_PROFILE_MISMATCH", "Profile differs from the dictionary and retained mapping.")
                    else:
                        reconstruction_verified = True
        return GovernanceAuditResult(
            "MPYY_SCHEMA_PROFILE_IDENTITY", "INCOMPLETE" if findings else "COMPLETE", findings,
            {
                "profile_id": profile.get("profile_id", ""),
                "profile_version": profile.get("profile_version", ""),
                "computed_content_sha256": computed,
                "declared_content_sha256": declared or "",
                "expected_hash_supplied": bool(expected_sha256),
                "source_dictionary_supplied": source_path is not None,
                "source_bytes_verified": source_verified,
                "dictionary_reconstruction_verified": reconstruction_verified,
                "issuer_authenticity": "NOT_VERIFIED",
            },
        )

    @classmethod
    def audit_files(cls, profile_path: str | Path, source_path: str | Path | None = None,
                    expected_sha256: str = "") -> GovernanceAuditResult:
        return cls.audit(read_profile_json(profile_path), source_path, expected_sha256)

    @staticmethod
    def _digest(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip().lower()
        return text if len(text) == 64 and all(char in "0123456789abcdef" for char in text) else None
