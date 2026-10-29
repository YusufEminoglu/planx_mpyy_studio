"""MPYY plan-stage content audits and the 2026 supplemental symbol registry."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable

from qgis.core import QgsFeature


PLAN_LEVELS = ("MSP", "CDP", "NIP", "UIP")
SCALE_RANGES = {
    "MSP": (250000, 500000),
    "CDP": (50000, 100000),
    "NIP": (5000, 25000),
    "UIP": (1000, 1000),
}
UIP_DETAIL_FIELDS = (
    "nizam", "katadedi", "taks", "kaks", "emsal", "yencok",
    "onbahce", "yanbahce", "arkabahce", "yapiyaklasmamesafesi",
)
CLASSIFICATION_FIELDS = (
    "fonksiyon_kodu", "fonksiyon_adi", "catalog_id", "gosterim_adi",
    "uipfonksiyon", "uip_fonksiyon", "bolge_turu", "strateji_bolgesi",
)


@dataclass(frozen=True)
class PlanAuditFinding:
    code: str
    severity: str
    article: str
    message: str


@dataclass
class PlanFeatureAudit:
    feature_id: str
    level: str
    status: str
    findings: list[PlanAuditFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(item.severity == "ERROR" for item in self.findings)

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "WARNING" for item in self.findings)


@dataclass
class PlanStageAuditResult:
    level: str
    records: list[PlanFeatureAudit]
    missing_msp_themes: list[str] = field(default_factory=list)
    catalog_version: str = ""

    @property
    def error_count(self) -> int:
        return sum(record.error_count for record in self.records)

    @property
    def warning_count(self) -> int:
        return sum(record.warning_count for record in self.records) + len(self.missing_msp_themes)

    @property
    def compliant_count(self) -> int:
        return sum(record.status == "COMPLIANT" for record in self.records)


class PlanStageAuditEngine:
    """Runs conservative, explainable checks for each MPYY plan level."""

    @classmethod
    def audit_features(
        cls,
        features: Iterable[QgsFeature],
        level: str,
        map_scale: int | None = None,
    ) -> PlanStageAuditResult:
        level_key = str(level or "").strip().upper()
        if level_key not in PLAN_LEVELS:
            raise ValueError('Plan kademesi MSP, ÇDP, NİP veya UİP olmalıdır.')
        feature_list = list(features)
        catalog = cls.load_2026_catalog()
        scale_finding = cls._scale_finding(level_key, map_scale)
        records: list[PlanFeatureAudit] = []
        global_ids: dict[str, list[int]] = {}
        observed_text: list[str] = []

        for index, feature in enumerate(feature_list):
            data = cls._feature_mapping(feature)
            identifier = cls._identifier(feature, data)
            findings = cls._common_findings(feature, data, level_key, catalog)
            findings.extend(cls._level_findings(data, level_key))
            if scale_finding:
                findings.append(scale_finding)
            global_id = cls._first(data, "global_id")
            if global_id:
                global_ids.setdefault(str(global_id), []).append(index)
            observed_text.append(" ".join(str(data.get(name, "")) for name in CLASSIFICATION_FIELDS))
            records.append(PlanFeatureAudit(identifier, level_key, "", findings))

        for duplicate_id, indexes in global_ids.items():
            if len(indexes) < 2:
                continue
            for index in indexes:
                records[index].findings.append(PlanAuditFinding(
                    "DUPLICATE_GLOBAL_ID", "ERROR", "MPYY 34-35",
                    'global_id denetlenen plan katmanında benzersiz değil: ' + duplicate_id,
                ))

        for record in records:
            if record.error_count:
                record.status = "NON_COMPLIANT"
            elif record.warning_count:
                record.status = "REVIEW_REQUIRED"
            else:
                record.status = "COMPLIANT"

        missing_themes = cls._missing_msp_themes(" ".join(observed_text)) if level_key == "MSP" else []
        return PlanStageAuditResult(
            level_key, records, missing_themes, str(catalog.get("catalog_version", ""))
        )

    @staticmethod
    def load_2026_catalog() -> dict[str, Any]:
        path = Path(__file__).resolve().parents[1] / "resources" / "mpyy_2026_additions.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('MPYY 2026 ek gösterim kataloğu okunamadı.') from error
        if payload.get("schema_version") != 1 or not isinstance(payload.get("symbols"), list):
            raise ValueError('MPYY 2026 ek gösterim kataloğunun şeması geçersizdir.')
        return payload

    @classmethod
    def _common_findings(cls, feature, data, level, catalog) -> list[PlanAuditFinding]:
        findings: list[PlanAuditFinding] = []
        geometry = feature.geometry()
        if not geometry or geometry.isEmpty():
            findings.append(PlanAuditFinding(
                "EMPTY_GEOMETRY", "ERROR", "MPYY 7, 34", 'Plan kararının geometrisi yok.'
            ))
        elif not geometry.isGeosValid():
            findings.append(PlanAuditFinding(
                "INVALID_GEOMETRY", "ERROR", "MPYY 7, 34", 'Plan kararı geometrisi geçersiz.'
            ))
        if not cls._first(data, "global_id"):
            findings.append(PlanAuditFinding(
                "MISSING_GLOBAL_ID", "ERROR", "MPYY 34-35", 'Kalıcı global_id gereklidir.'
            ))
        plan_id = cls._first(data, "plan_id")
        if not plan_id or str(plan_id).strip().upper() == "PLAN-UNSET":
            findings.append(PlanAuditFinding(
                "MISSING_PLAN_ID", "ERROR", "MPYY 32, 34", 'Plan kimliği gereklidir.'
            ))
        declared_level = cls._first(data, "plan_kademesi")
        if not declared_level:
            findings.append(PlanAuditFinding(
                "MISSING_PLAN_LEVEL", "ERROR", "MPYY 6", 'plan_kademesi alanı gereklidir.'
            ))
        elif cls.normalize(declared_level) != level:
            findings.append(PlanAuditFinding(
                "PLAN_LEVEL_MISMATCH", "ERROR", "MPYY 6",
                f"Declared plan level {declared_level} does not match the {level} audit.",
            ))
        classification = cls._first(data, *CLASSIFICATION_FIELDS)
        if not classification:
            findings.append(PlanAuditFinding(
                "MISSING_PLAN_DECISION", "ERROR", "MPYY 7, EK-1",
                'Katalog veya plan fonksiyonu sınıflandırması gereklidir.',
            ))
        findings.extend(cls._symbol_level_findings(data, level, catalog))
        return findings

    @classmethod
    def _level_findings(cls, data, level) -> list[PlanAuditFinding]:
        if level == "MSP":
            findings = cls._require_any(
                data, ("strateji_bolgesi", "oncelik_durumu"), "MISSING_STRATEGIC_ROLE",
                "ERROR", "MPYY 14-15", "MSP decisions require a strategic region or priority role."
            )
        elif level == "CDP":
            findings = cls._require_any(
                data, ("bolge_turu", "alt_bolge_kodu"), "MISSING_CDP_REGION_ROLE",
                "ERROR", "MPYY 18-20", "CDP decisions require a region or sub-region role."
            )
        elif level == "NIP":
            findings = []
            function_text = cls.normalize(cls._first(data, *CLASSIFICATION_FIELDS))
            if any(token in function_text for token in ("KONUT", "YERLES", "KENTSEL_GELISME")):
                findings.extend(cls._require_any(
                    data, ("brut_yogunluk_kisi_ha", "yogunluk_kademesi"),
                    "MISSING_GROSS_DENSITY", "ERROR", "MPYY 23",
                    "Residential NIP decisions require gross density or a density class.",
                ))
        else:
            findings = cls._uip_findings(data)

        if level != "UIP":
            populated = [name for name in UIP_DETAIL_FIELDS if cls._first(data, name)]
            if populated:
                findings.append(PlanAuditFinding(
                    "DETAIL_LEVEL_LEAKAGE", "ERROR", "MPYY 23-24",
                    "Parcel-level implementation fields are not permitted at this plan level: "
                    + ", ".join(populated),
                ))
        return findings

    @classmethod
    def _uip_findings(cls, data) -> list[PlanAuditFinding]:
        function_text = cls.normalize(cls._first(data, *CLASSIFICATION_FIELDS))
        buildable = any(
            token in function_text for token in ("KONUT", "TICARET", "TURIZM", "SANAYI", "DEPOLAMA")
        ) and not any(token in function_text for token in ("YOL", "PARK", "MEYDAN", "YESIL"))
        if not buildable:
            return []
        findings: list[PlanAuditFinding] = []
        checks = (
            (("nizam",), "MISSING_BUILDING_ORDER", 'yapı nizamı'),
            (("taks", "kaks", "emsal"), "MISSING_INTENSITY", 'TAKS, KAKS veya emsal'),
            (("katadedi", "yencok"), "MISSING_HEIGHT", 'kat sayısı veya yapı yüksekliği'),
            (("onbahce", "yapiyaklasmamesafesi"), "MISSING_SETBACK", 'yapı çekme mesafesi'),
        )
        for names, code, label in checks:
            findings.extend(cls._require_any(
                data, names, code, "ERROR", "MPYY 24/4",
                f"Yapılaşma kararı içeren UİP kararları için {label} gereklidir.",
            ))
        return findings

    @classmethod
    def _symbol_level_findings(cls, data, level, catalog) -> list[PlanAuditFinding]:
        text = cls.normalize(" ".join(str(data.get(name, "")) for name in CLASSIFICATION_FIELDS))
        findings = []
        for symbol in catalog.get("symbols", []):
            code = cls.normalize(symbol.get("code", ""))
            name = cls.normalize(symbol.get("name", ""))
            if not code and not name:
                continue
            if (code and code not in text) and (not name or name not in text):
                continue
            if level not in symbol.get("levels", []):
                findings.append(PlanAuditFinding(
                    "SYMBOL_LEVEL_MISMATCH", "ERROR", "MPYY EK-1 (22.01.2026)",
                    f"{symbol.get('code')} sembolü {level} plan kademesi için tanımlı değildir.",
                ))
        return findings

    @staticmethod
    def _require_any(data, names, code, severity, article, message) -> list[PlanAuditFinding]:
        if any(PlanStageAuditEngine._first(data, name) for name in names):
            return []
        return [PlanAuditFinding(code, severity, article, message)]

    @staticmethod
    def _scale_finding(level: str, map_scale: int | None) -> PlanAuditFinding | None:
        if map_scale in (None, 0):
            return None
        minimum, maximum = SCALE_RANGES[level]
        if minimum <= int(map_scale) <= maximum:
            return None
        return PlanAuditFinding(
            "SCALE_LEVEL_MISMATCH", "ERROR", "MPYY 4, 6",
            f"1:{int(map_scale)} ölçeği, tanımlanan {level} ölçek aralığı (1:{minimum} - 1:{maximum}) dışındadır.",
        )

    @classmethod
    def _missing_msp_themes(cls, text: str) -> list[str]:
        normalized = cls.normalize(text)
        themes = {
            "SETTLEMENT": ("YERLES", "KENT", "KONUT"),
            "TRANSPORT": ("ULASIM", "YOL", "KORIDOR", "LIMAN", "HAVAALANI"),
            "WATER": ("SU", "HAVZA", "AKARSU"),
            "RISK": ("AFET", "RISK", "DEPREM", "TASKIN"),
            "INFRASTRUCTURE": ("ALTYAPI", "ENERJI", "LOJISTIK"),
            "ECONOMY": ("SANAYI", "TARIM", "TURIZM", "EKONOMI"),
        }
        return [name for name, tokens in themes.items() if not any(token in normalized for token in tokens)]

    @staticmethod
    def _feature_mapping(feature: QgsFeature) -> dict[str, Any]:
        return {field.name().lower(): feature[field.name()] for field in feature.fields()}

    @staticmethod
    def _first(data: dict[str, Any], *names: str) -> Any:
        for name in names:
            value = data.get(name.lower())
            if value not in (None, "", "NULL"):
                return value
        return None

    @classmethod
    def _identifier(cls, feature: QgsFeature, data: dict[str, Any]) -> str:
        return str(cls._first(data, "global_id", "plan_id") or feature.id())

    @staticmethod
    def normalize(value: Any) -> str:
        text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")
