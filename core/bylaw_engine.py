"""Configurable metropolitan by-law compliance profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from qgis.core import QgsFeature

from .attr_utils import is_null_value, parse_float


@dataclass(frozen=True)
class BylawProfile:
    code: str
    display_name: str
    min_ceiling_height_m: float = 2.60
    min_unit_net_area_m2: float = 0.0
    permitted_roof_slopes_percent: tuple[float, ...] = (33.0, 45.0)
    min_subbasement_height_m: float = 0.50
    max_overhang_m: float | None = None
    parking_on_parcel_required: bool = False
    source_note: str = 'Yapılandırma profili; güncel onaylı plan ve belediye düzenleme metniyle karşılaştırarak doğrulayın.'
    profile_version: str = "1.0"
    effective_date: str = ""
    source_reference: str = ""


@dataclass(frozen=True)
class BylawViolation:
    rule_code: str
    field_name: str
    observed_value: str
    required_value: str
    message: str


@dataclass
class BylawAuditResult:
    profile_code: str
    compliant: bool
    status: str
    violations: list[BylawViolation] = field(default_factory=list)
    checked_rules: int = 0
    missing_rules: list[str] = field(default_factory=list)
    invalid_rules: list[str] = field(default_factory=list)


_PROFILE_FIELDS = {
    field_name for field_name in BylawProfile.__dataclass_fields__
}
_DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "bylaws" / "municipal_profiles.json"
)


def load_bylaw_profiles(profile_path: str | Path | None = None) -> dict[str, BylawProfile]:
    """Load a validated, versioned municipal profile registry from JSON."""
    path = Path(profile_path).resolve() if profile_path else _DEFAULT_PROFILE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'Belediye profili dosyası okunamadı: {path}') from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError('Belediye profili schema_version değeri 1 olmalıdır.')
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ValueError('Belediye profili dosyası boş olmayan bir profiles listesi içermelidir.')

    profiles: dict[str, BylawProfile] = {}
    for index, raw_profile in enumerate(raw_profiles, start=1):
        if not isinstance(raw_profile, dict):
            raise ValueError(f'{index} numaralı belediye profili bir nesne olmalıdır.')
        unknown = set(raw_profile) - _PROFILE_FIELDS
        if unknown:
            raise ValueError('Bilinmeyen belediye profili alanları: ' + ", ".join(sorted(unknown)))
        values = dict(raw_profile)
        code = str(values.get("code", "")).strip().upper()
        if not re.fullmatch(r"[A-Z0-9_]+", code):
            raise ValueError(f'{index} numaralı belediye profilinin kodu geçersizdir.')
        if code in profiles:
            raise ValueError("Yinelenen belediye profili kodu: " + code)
        display_name = str(values.get("display_name", "")).strip()
        if not display_name:
            raise ValueError('Belediye profili display_name alanı boş olamaz.')
        values["code"] = code
        values["display_name"] = display_name

        numeric_fields = (
            "min_ceiling_height_m", "min_unit_net_area_m2", "min_subbasement_height_m"
        )
        for field_name in numeric_fields:
            if field_name in values:
                values[field_name] = _validated_nonnegative_number(values[field_name], field_name)
        if values.get("max_overhang_m") is not None:
            values["max_overhang_m"] = _validated_nonnegative_number(
                values["max_overhang_m"], "max_overhang_m"
            )
        slopes = values.get("permitted_roof_slopes_percent", (33.0, 45.0))
        if not isinstance(slopes, (list, tuple)) or not slopes:
            raise ValueError('permitted_roof_slopes_percent boş olmayan bir liste olmalıdır.')
        values["permitted_roof_slopes_percent"] = tuple(
            _validated_bounded_number(value, "permitted_roof_slopes_percent", 0.0, 100.0)
            for value in slopes
        )
        parking = values.get("parking_on_parcel_required", False)
        if not isinstance(parking, bool):
            raise ValueError('parking_on_parcel_required true veya false olmalıdır.')
        values["parking_on_parcel_required"] = parking
        profiles[code] = BylawProfile(**values)
    return profiles


def _validated_nonnegative_number(value: Any, field_name: str) -> float:
    return _validated_bounded_number(value, field_name, 0.0, float("inf"))


def _validated_bounded_number(value: Any, field_name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError(field_name + ' sayısal olmalıdır.')
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(field_name + ' sayısal olmalıdır.') from error
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ValueError(field_name + ' izin verilen aralığın dışındadır.')
    return number


BYLAW_PROFILES = load_bylaw_profiles()


class MunicipalBylawEngine:
    """Audits common parcel/building attributes against a selected profile."""

    @classmethod
    def profile(
        cls, code: str, profiles: Mapping[str, BylawProfile] | None = None
    ) -> BylawProfile:
        key = str(code or "PAIY_DEFAULT").strip().upper()
        registry = profiles or BYLAW_PROFILES
        if key not in registry:
            raise ValueError(f'Bilinmeyen belediye imar yönetmeliği profili: {code}')
        return registry[key]

    @classmethod
    def audit(
        cls,
        values: QgsFeature | Mapping[str, Any],
        profile_code: str,
        profiles: Mapping[str, BylawProfile] | None = None,
    ) -> BylawAuditResult:
        profile = cls.profile(profile_code, profiles)
        data = cls._as_mapping(values)
        violations: list[BylawViolation] = []
        missing: list[str] = []
        invalid: list[str] = []
        checked = 0

        checked += cls._check_minimum(
            data, ("ceiling_height_m", "tavan_yuksekligi", "kat_yuksekligi"),
            profile.min_ceiling_height_m, "MIN_CEILING_HEIGHT", violations, missing, invalid,
        )
        if profile.min_unit_net_area_m2 > 0:
            checked += cls._check_minimum(
                data, ("unit_net_area_m2", "bagimsiz_bolum_net_m2", "net_alan_m2"),
                profile.min_unit_net_area_m2, "MIN_UNIT_NET_AREA", violations, missing, invalid,
            )
        checked += cls._check_minimum(
            data, ("subbasement_height_m", "su_basman_kotu", "subasman_m"),
            profile.min_subbasement_height_m, "MIN_SUBBASEMENT_HEIGHT", violations, missing, invalid,
        )

        roof_value, roof_state = cls._number_state(
            data, ("roof_slope_percent", "cati_egimi", "cati_egimi_yuzde")
        )
        if roof_state == "MISSING":
            missing.append("ROOF_SLOPE")
        elif roof_state == "INVALID":
            invalid.append("ROOF_SLOPE")
        else:
            checked += 1
            if not any(abs(roof_value - allowed) <= 0.01 for allowed in profile.permitted_roof_slopes_percent):
                violations.append(BylawViolation(
                    "ROOF_SLOPE", "roof_slope_percent", str(roof_value),
                    ", ".join(str(value) for value in profile.permitted_roof_slopes_percent),
                    'Çatı eğimi yapılandırılmış belediye profilinin dışındadır.',
                ))

        if profile.max_overhang_m is not None:
            overhang, overhang_state = cls._number_state(data, ("overhang_m", "cikma_m", "konsol_m"))
            if overhang_state == "MISSING":
                missing.append("MAX_OVERHANG")
            elif overhang_state == "INVALID":
                invalid.append("MAX_OVERHANG")
            else:
                checked += 1
                if overhang > profile.max_overhang_m + 1e-9:
                    violations.append(BylawViolation(
                        "MAX_OVERHANG", "overhang_m", str(overhang), str(profile.max_overhang_m),
                        'Çıkma, yapılandırılmış belediye üst sınırını aşmaktadır.',
                    ))

        if profile.parking_on_parcel_required:
            parking = cls._first_value(data, ("parking_on_parcel", "otopark_parselde", "parsel_ici_otopark"))
            if parking is None:
                missing.append("PARKING_ON_PARCEL")
            else:
                parking_value = cls._as_bool(parking)
                if parking_value is None:
                    invalid.append("PARKING_ON_PARCEL")
                elif not parking_value:
                    checked += 1
                    violations.append(BylawViolation(
                        "PARKING_ON_PARCEL", "parking_on_parcel", str(parking), "true",
                        'Gerekli parsel içi otopark belgelenmemiştir.',
                    ))
                else:
                    checked += 1

        if violations:
            status = "NON_COMPLIANT"
        elif invalid:
            status = "INVALID_DATA"
        elif missing:
            status = "INSUFFICIENT_DATA"
        else:
            status = "COMPLIANT"
        return BylawAuditResult(
            profile_code=profile.code,
            compliant=status == "COMPLIANT",
            status=status,
            violations=violations,
            checked_rules=checked,
            missing_rules=missing,
            invalid_rules=invalid,
        )

    @staticmethod
    def _as_mapping(values: QgsFeature | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(values, QgsFeature):
            return {field.name().lower(): values[field.name()] for field in values.fields()}
        return {str(key).lower(): value for key, value in values.items()}

    @staticmethod
    def _first_value(data: Mapping[str, Any], names: tuple[str, ...]) -> Any:
        for name in names:
            value = data.get(name.lower())
            if not is_null_value(value):
                return value
        return None

    @classmethod
    def _first_number(cls, data: Mapping[str, Any], names: tuple[str, ...]) -> float | None:
        value, state = cls._number_state(data, names)
        return value if state == "VALID" else None

    @classmethod
    def _number_state(cls, data: Mapping[str, Any], names: tuple[str, ...]) -> tuple[float | None, str]:
        value = cls._first_value(data, names)
        if value is None:
            return None, "MISSING"
        number = parse_float(value)
        if number is None:
            return None, "INVALID"
        return number, "VALID"

    @classmethod
    def _check_minimum(cls, data, names, minimum, code, violations, missing, invalid) -> int:
        value, state = cls._number_state(data, names)
        if state == "MISSING":
            missing.append(code)
            return 0
        if state == "INVALID":
            invalid.append(code)
            return 0
        if value + 1e-9 < minimum:
            violations.append(BylawViolation(
                code, names[0], str(value), str(minimum),
                f"{names[0]} yapılandırılmış asgari değerin ({minimum}) altındadır.",
            ))
        return 1

    @staticmethod
    def _as_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "evet", "var"}:
            return True
        if normalized in {"0", "false", "no", "hayir", "hayır", "yok"}:
            return False
        return None
