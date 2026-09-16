"""MPYY special-plan dossier audits for Articles 27-30."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
import uuid


@dataclass(frozen=True)
class SpecialPlanFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass(frozen=True)
class SpecialPlanAuditResult:
    audit_type: str
    status: str
    findings: tuple[SpecialPlanFinding, ...]

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


class SpecialPlanAuditEngine:
    """Validates evidence declarations while leaving approval to competent authorities."""

    CONSERVATION_REQUIREMENTS = {
        "site_boundary_coverage": "MPYY 27/1-a",
        "settlement_relationship": "MPYY 27/1-a,e",
        "site_specific_strategies": "MPYY 27/1-c,ç",
        "disaster_resilience_strategy": "MPYY 27/1-c",
        "protection_board_or_commission_decision": "MPYY 27/1-d,f",
        "unregistered_asset_inventory": "MPYY 27/1-g",
        "historic_building_and_street_decisions": "MPYY 27/1-ı",
        "harmful_function_change_screening": "MPYY 27/1-h",
    }
    COASTAL_REQUIREMENTS = {
        "integrated_coastal_strategy": "MPYY 29/1-a",
        "land_and_sea_public_access": "MPYY 29/1-b",
        "institution_sector_coordination_model": "MPYY 29/1-c",
        "current_coastal_profile": "MPYY 29/1-d",
        "potential_problem_constraint_analysis": "MPYY 29/1-e",
        "subregion_spatial_strategies": "MPYY 29/1-f",
        "participatory_management_model": "MPYY 29/1-g",
        "coastal_ecosystem": "MPYY 29/2-a",
        "disaster_hazards": "MPYY 29/2-b",
        "wave_wind_water_cycle": "MPYY 29/2-c",
        "coastline_and_shore_practice": "MPYY 29/2-ç",
        "transport_connections": "MPYY 29/2-d",
        "ports_and_coastal_facilities": "MPYY 29/2-e",
        "marine_trade_and_transport": "MPYY 29/2-f",
        "energy_storage_transmission": "MPYY 29/2-g",
        "tourism_and_accommodation": "MPYY 29/2-ğ",
        "fisheries_and_aquaculture": "MPYY 29/2-h",
        "water_waste_and_air_quality": "MPYY 29/2-ı",
        "coast_guard_and_restricted_areas": "MPYY 29/2-i",
        "coastal_settlement_expansion": "MPYY 29/2-j",
    }
    URBAN_DESIGN_REQUIREMENTS = {
        "development_and_building_targets": "MPYY 30/2",
        "solid_void_analysis": "MPYY 30/5",
        "building_relationships": "MPYY 30/5",
        "vehicle_pedestrian_movements": "MPYY 30/5",
        "natural_data": "MPYY 30/5",
        "cultural_data": "MPYY 30/5",
        "social_economic_data": "MPYY 30/5",
        "transport_data": "MPYY 30/5",
        "technical_infrastructure_data": "MPYY 30/5",
    }

    @classmethod
    def audit_conservation(cls, manifest: Mapping[str, Any]) -> SpecialPlanAuditResult:
        findings = cls._required(manifest, cls.CONSERVATION_REQUIREMENTS)
        if cls._boolean(manifest.get("overlapping_protection_statuses")) and not cls._present(
            manifest.get("competent_authority_opinions")
        ):
            findings.append(SpecialPlanFinding(
                "MISSING_COMPETENT_AUTHORITY_OPINIONS", "ERROR", "MPYY 27/1-b,f",
                "Overlapping protection statuses require competent authority opinions.",
            ))
        return cls._result("CONSERVATION_PLAN", findings)

    @classmethod
    def audit_coastal(cls, manifest: Mapping[str, Any]) -> SpecialPlanAuditResult:
        findings = cls._required(manifest, cls.COASTAL_REQUIREMENTS)
        if not cls._present(manifest.get("planning_area_interaction_basis")):
            findings.append(SpecialPlanFinding(
                "MISSING_PLANNING_AREA_INTERACTION_BASIS", "ERROR", "MPYY 28",
                "Coastal planning boundary interaction basis is not documented.",
            ))
        return cls._result("INTEGRATED_COASTAL_PLAN", findings)

    @classmethod
    def audit_urban_design(cls, manifest: Mapping[str, Any]) -> SpecialPlanAuditResult:
        findings = cls._required(manifest, cls.URBAN_DESIGN_REQUIREMENTS)
        boundary_in_plan = cls._present(manifest.get("project_boundary_in_plan"))
        preceded_plan = cls._boolean(manifest.get("project_preceded_plan"))
        details_transferred = cls._present(manifest.get("details_transferred_to_plan"))
        if not boundary_in_plan and not (preceded_plan and details_transferred):
            findings.append(SpecialPlanFinding(
                "MISSING_PLAN_RELATIONSHIP", "ERROR", "MPYY 30/1",
                "Project boundary or transfer of pre-plan project details is not evidenced.",
            ))
        if cls._boolean(manifest.get("implementation_requested")) and not cls._boolean(
            manifest.get("implementation_plan_approved")
        ):
            findings.append(SpecialPlanFinding(
                "IMPLEMENTATION_PLAN_NOT_APPROVED", "ERROR", "MPYY 30/4",
                "Urban design implementation cannot precede implementation-plan approval.",
            ))
        return cls._result("URBAN_DESIGN_PROJECT", findings)

    @classmethod
    def audit_file(cls, manifest_path: str | Path, audit_type: str):
        try:
            payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Özel plan bildirimi okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('Özel plan bildiriminin kökü bir JSON nesnesi olmalıdır.')
        key = str(audit_type).strip().upper()
        if key == "CONSERVATION_PLAN":
            return cls.audit_conservation(payload)
        if key == "INTEGRATED_COASTAL_PLAN":
            return cls.audit_coastal(payload)
        if key == "URBAN_DESIGN_PROJECT":
            return cls.audit_urban_design(payload)
        raise ValueError('Bilinmeyen özel plan denetimi türü.')

    @staticmethod
    def write_report(result: SpecialPlanAuditResult, output_path: str | Path) -> str:
        path = Path(output_path)
        payload = asdict(result)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return str(path)

    @classmethod
    def _required(cls, manifest, requirements):
        findings = []
        for field_name, article in requirements.items():
            if not cls._present(manifest.get(field_name)):
                findings.append(SpecialPlanFinding(
                    "MISSING_" + field_name.upper(), "ERROR", article,
                    field_name + " is not evidenced in the dossier.",
                ))
        return findings

    @staticmethod
    def _result(audit_type, findings):
        status = "INCOMPLETE" if any(item.severity == "ERROR" for item in findings) else (
            "REVIEW_REQUIRED" if findings else "COMPLETE"
        )
        return SpecialPlanAuditResult(audit_type, status, tuple(findings))

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
