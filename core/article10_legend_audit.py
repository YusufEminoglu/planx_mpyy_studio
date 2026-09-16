"""MPYY Article 10 official plan-display catalog audit."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from qgis.core import QgsFeature

from .eplan_catalog import EPLAN_CATALOG
from .plan_stage_audit import PLAN_LEVELS, PlanStageAuditEngine


@dataclass(frozen=True)
class LegendAuditRecord:
    feature: QgsFeature
    raw_code: str
    normalized_code: str
    status: str
    catalog_source: str
    message: str


class Article10LegendAuditEngine:
    @classmethod
    def audit(
        cls, features: Iterable[QgsFeature], plan_level: str, code_field: str
    ) -> list[LegendAuditRecord]:
        level = str(plan_level).strip().upper()
        if level not in PLAN_LEVELS:
            raise ValueError('Plan kademesi MSP, ÇDP, NİP veya UİP olmalıdır.')
        official, sources = cls._official_codes(level)
        records = []
        for feature in features:
            if feature.fields().indexFromName(code_field) < 0:
                raw = ""
            else:
                value = feature[code_field]
                raw = "" if value in (None, "", "NULL") else str(value).strip()
            code = PlanStageAuditEngine.normalize(raw)
            if not code:
                status = "MISSING_CODE"
                source = ""
                message = 'Plan gösterim kodu eksiktir.'
            elif code in official:
                status = "OFFICIAL_MATCH"
                source = sources.get(code, "MPYY EK-1")
                message = "Display code matches a shipped official catalog entry."
            else:
                status = "UNMAPPED_REVIEW"
                source = ""
                message = 'Resmî katalogda tam eşleşme bulunamadı; Bakanlık yayım durumu doğrulanmalıdır.'
            records.append(LegendAuditRecord(feature, raw, code, status, source, message))
        return records

    @classmethod
    def _official_codes(cls, level: str):
        codes = set()
        sources = {}
        for key, entry in EPLAN_CATALOG.get(level, {}).items():
            for value in (key, entry.get("rule"), entry.get("style"), entry.get("label")):
                normalized = PlanStageAuditEngine.normalize(value)
                if normalized:
                    codes.add(normalized)
                    sources[normalized] = "e-Plan EK-1"
        if level == "MSP":
            path = Path(__file__).resolve().parents[1] / "styles" / "msp_catalog.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            for row in payload.get("rows", []):
                for value in (row.get("id"), row.get("detay_adi")):
                    normalized = PlanStageAuditEngine.normalize(value)
                    if normalized:
                        codes.add(normalized)
                        sources[normalized] = "MPYY EK-1e MSP"
        additions = PlanStageAuditEngine.load_2026_catalog()
        for symbol in additions["symbols"]:
            if level not in symbol.get("levels", []):
                continue
            for value in (symbol.get("code"), symbol.get("name")):
                normalized = PlanStageAuditEngine.normalize(value)
                if normalized:
                    codes.add(normalized)
                    sources[normalized] = "MPYY EK-1 2026"
        return codes, sources
