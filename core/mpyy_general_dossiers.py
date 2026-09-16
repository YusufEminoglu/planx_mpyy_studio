"""MPYY Articles 8 and 11 documentary audits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid


@dataclass(frozen=True)
class GeneralDossierFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass(frozen=True)
class GeneralDossierResult:
    audit_type: str
    status: str
    findings: tuple[GeneralDossierFinding, ...]

    @property
    def error_count(self):
        return sum(item.severity == "ERROR" for item in self.findings)


class MPYYGeneralDossierEngine:
    ARTICLE8_BASE = {
        "institution_data_opinions": "MPYY 8/1",
        "printed_and_digital_sources": "MPYY 8/5",
        "national_geoportal_review": "MPYY 8/6",
        "numeric_dataset_submission": "MPYY 8/7",
        "current_plan_evaluation": "MPYY 8/9",
        "threshold_and_field_studies": "MPYY 8/9",
        "social_economic_historic_research": "MPYY 8/9",
        "problem_and_potential_analysis": "MPYY 8/9",
        "research_report": "MPYY 8/9",
    }
    ARTICLE11_BASE = {
        "ek2_standards_assessed": "MPYY 11/1",
        "future_requirements_assessed": "MPYY 11/1",
        "transport_plan_considered_for_parking": "MPYY 11/6",
        "resident_and_mobile_population_assessed": "MPYY 11/6",
        "regional_parking_assessed": "MPYY 11/6",
    }

    @classmethod
    def audit_article8(cls, manifest: Mapping[str, Any]) -> GeneralDossierResult:
        findings = cls._required(manifest, cls.ARTICLE8_BASE)
        conditionals = (
            ("high_urban_or_disaster_risk", "risk_or_avoidance_study", "MPYY 8/10"),
            ("large_scale_land_use", "site_selection_analysis", "MPYY 8/11"),
            ("conservation_plan", "conservation_research_bundle", "MPYY 8/12"),
            ("nip_preparation", "institution_service_area_needs", "MPYY 8/3"),
        )
        findings.extend(cls._conditional(manifest, conditionals))
        return cls._result("ARTICLE_8_RESEARCH", findings)

    @classmethod
    def audit_article11(cls, manifest: Mapping[str, Any]) -> GeneralDossierResult:
        findings = cls._required(manifest, cls.ARTICLE11_BASE)
        conditionals = (
            ("alternative_minimum_standard", "ministry_or_cdp_standard_basis", "MPYY 11/2"),
            ("settled_area_size_exception", "competent_institution_opinion", "MPYY 11/3"),
            ("conservation_site", "site_specific_standard_decisions", "MPYY 11/4"),
            ("seasonal_tourism_housing", "permanent_population_assumption", "MPYY 11/5"),
            ("seasonal_tourism_housing", "seasonal_area_infrastructure", "MPYY 11/5"),
            ("seasonal_tourism_housing", "seasonal_area_parking", "MPYY 11/5"),
        )
        findings.extend(cls._conditional(manifest, conditionals))
        return cls._result("ARTICLE_11_STANDARDS", findings)

    @classmethod
    def audit_file(cls, path: str | Path, audit_type: str):
        try:
            manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('MPYY plan dosyası bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(manifest, Mapping):
            raise ValueError('MPYY plan dosyasının kökü bir JSON nesnesi olmalıdır.')
        if audit_type == "ARTICLE_8_RESEARCH":
            return cls.audit_article8(manifest)
        if audit_type == "ARTICLE_11_STANDARDS":
            return cls.audit_article11(manifest)
        raise ValueError('Bilinmeyen MPYY genel dosya denetimi türü.')

    @staticmethod
    def write_report(result: GeneralDossierResult, path: str | Path) -> str:
        output = Path(path)
        payload = asdict(result)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)
        return str(output)

    @classmethod
    def _required(cls, manifest, requirements):
        return [
            GeneralDossierFinding(
                "MISSING_" + field.upper(), "ERROR", article,
                field + " is not evidenced in the dossier.",
            )
            for field, article in requirements.items() if not cls._present(manifest.get(field))
        ]

    @classmethod
    def _conditional(cls, manifest, rules):
        return [
            GeneralDossierFinding(
                "MISSING_" + evidence.upper(), "ERROR", article,
                evidence + ' belirtilen planlama bağlamı için gereklidir.',
            )
            for condition, evidence, article in rules
            if cls._boolean(manifest.get(condition)) and not cls._present(manifest.get(evidence))
        ]

    @staticmethod
    def _result(audit_type, findings):
        return GeneralDossierResult(
            audit_type, "INCOMPLETE" if findings else "COMPLETE", tuple(findings)
        )

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
