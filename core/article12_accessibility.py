"""MPYY Article 12 function-specific walking-distance audit."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable

from qgis.core import QgsFeature

from .attr_utils import norm_tr, parse_float
from .routed_accessibility import RoutedAccessibilityEngine


@dataclass(frozen=True)
class Article12AccessibilityRecord:
    feature: QgsFeature
    service_type: str
    threshold_m: float | None
    route_distance_m: float | None
    facility_id: str
    status: str
    exception_basis: str
    message: str


@dataclass(frozen=True)
class Article12AccessibilityResult:
    records: tuple[Article12AccessibilityRecord, ...]
    compliant_count: int
    review_count: int
    non_compliant_count: int
    invalid_count: int


class Article12AccessibilityEngine:
    """Selects approximate statutory distances from the requested service type."""

    THRESHOLDS = {
        "COCUK_BAHCESI": 500.0,
        "OYUN_ALANI": 500.0,
        "ACIK_SEMT_SPOR_ALANI": 500.0,
        "AILE_SAGLIK_MERKEZI": 500.0,
        "KRES": 500.0,
        "ANAOKULU": 500.0,
        "ILKOKUL": 500.0,
        "ORTAOKUL": 1000.0,
        "LISE": 2500.0,
        "KUCUK_CAMI": 250.0,
        "ORTA_CAMI": 400.0,
        "SEMT_CAMI": 400.0,
        "MESCIT": 150.0,
    }
    ALIASES = {
        "AILE_SAGLIGI_MERKEZI": "AILE_SAGLIK_MERKEZI",
        "ORTA_SEMT_CAMI": "ORTA_CAMI",
        "SEMT_ORTA_CAMI": "ORTA_CAMI",
        "ACIK_SEMT_SPOR": "ACIK_SEMT_SPOR_ALANI",
        "COCUK_OYUN_ALANI": "OYUN_ALANI",
    }

    @classmethod
    def audit(
        cls,
        network_features: Iterable[QgsFeature],
        demand_features: Iterable[QgsFeature],
        facility_features: Iterable[QgsFeature],
        demand_service_field: str,
        facility_type_field: str,
        snap_tolerance_m: float = 1.0,
        maximum_snap_distance_m: float = 50.0,
    ) -> Article12AccessibilityResult:
        network = list(network_features)
        demands = list(demand_features)
        facilities = list(facility_features)
        grouped_demands = {}
        invalid_records = []
        for demand in demands:
            service_type = cls._field_value(demand, demand_service_field)
            normalized = cls.canonical_type(service_type)
            if normalized not in cls.THRESHOLDS:
                invalid_records.append(Article12AccessibilityRecord(
                    demand, normalized, None, None, "", "UNKNOWN_SERVICE_TYPE", "",
                    'Talep hizmet türü için MPYY 12. madde mesafe profili yok.',
                ))
            else:
                grouped_demands.setdefault(normalized, []).append(demand)

        records = list(invalid_records)
        for service_type, service_demands in grouped_demands.items():
            matching_facilities = [
                feature for feature in facilities
                if cls.canonical_type(cls._field_value(feature, facility_type_field)) == service_type
            ]
            threshold = cls.THRESHOLDS[service_type]
            routed = RoutedAccessibilityEngine.analyze(
                network, service_demands, matching_facilities, threshold,
                snap_tolerance_m, maximum_snap_distance_m,
            )
            for route in routed.records:
                exception_basis = cls._exception_basis(route.feature)
                if route.status == "ACCESSIBLE":
                    status = "COMPLIANT_SCREENING"
                    message = 'Talep noktası yaklaşık Madde 12 yürüme mesafesi içindedir.'
                elif exception_basis:
                    status = "EXCEPTION_REVIEW"
                    message = (
                        'Mesafe karşılanmıyor; ancak uzman incelemesi için Madde 12/4 bağlamı beyan edilmiştir.'
                    )
                elif route.status in {"INACCESSIBLE", "UNREACHABLE", "UNSNAPPED"}:
                    status = "NON_COMPLIANT_SCREENING"
                    message = 'Yapılandırılmış yaya ağı yaklaşık mesafeyi karşılamıyor.'
                else:
                    status = "INVALID"
                    message = route.message
                records.append(Article12AccessibilityRecord(
                    route.feature, service_type, threshold, route.route_distance_m,
                    route.facility_id, status, exception_basis, message,
                ))
        order = {feature.id(): index for index, feature in enumerate(demands)}
        records.sort(key=lambda item: order.get(item.feature.id(), len(order)))
        record_tuple = tuple(records)
        return Article12AccessibilityResult(
            record_tuple,
            sum(item.status == "COMPLIANT_SCREENING" for item in record_tuple),
            sum(item.status == "EXCEPTION_REVIEW" for item in record_tuple),
            sum(item.status == "NON_COMPLIANT_SCREENING" for item in record_tuple),
            sum(item.status in {"INVALID", "UNKNOWN_SERVICE_TYPE"} for item in record_tuple),
        )

    @classmethod
    def _exception_basis(cls, feature: QgsFeature) -> str:
        data = {field.name().lower(): feature[field.name()] for field in feature.fields()}
        reasons = []
        density = cls._number(data.get("gross_density_ppha"))
        if density is not None and density <= 100.0:
            reasons.append("GROSS_DENSITY_AT_OR_BELOW_100")
        if cls._boolean(data.get("rural_settlement")):
            reasons.append("DISPERSED_RURAL_SETTLEMENT")
        justification = str(data.get("barrier_justification") or "").strip()
        if justification:
            reasons.append("NATURAL_OR_ARTIFICIAL_BARRIER")
        return ";".join(reasons)

    @staticmethod
    def normalize(value: Any) -> str:
        text = str(value or "").strip().upper().translate(str.maketrans(
            "ÇĞİÖŞÜÂÎÛ", "CGIOSUAIU"
        ))
        return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")

    @classmethod
    def canonical_type(cls, value: Any) -> str:
        normalized = cls.normalize(value)
        return cls.ALIASES.get(normalized, normalized)

    @staticmethod
    def _field_value(feature: QgsFeature, field_name: str) -> Any:
        if not field_name or feature.fields().indexFromName(field_name) < 0:
            return None
        return feature[field_name]

    @staticmethod
    def _number(value: Any) -> float | None:
        number = parse_float(value)
        if number is None:
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "evet"}
