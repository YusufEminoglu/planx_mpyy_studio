"""MPYY Article 16 MSP action-plan implementation monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import Any, Iterable

from qgis.core import QgsFeature


@dataclass(frozen=True)
class MSPActionRecord:
    feature: QgsFeature
    action_id: str
    progress_ratio: float | None
    status: str
    message: str


@dataclass(frozen=True)
class MSPMonitoringResult:
    records: tuple[MSPActionRecord, ...]
    weighted_progress_ratio: float | None
    complete_count: int
    delayed_count: int
    missing_data_count: int


class MSPMonitoringEngine:
    """Summarizes measurable MSP actions while retaining missing-data findings."""

    @classmethod
    def evaluate(
        cls,
        features: Iterable[QgsFeature],
        evaluation_date: date | str | None = None,
    ) -> MSPMonitoringResult:
        evaluated_on = cls._date(evaluation_date) if evaluation_date else date.today()
        records = []
        weighted_total = 0.0
        weight_sum = 0.0
        for feature in features:
            data = {field.name().lower(): feature[field.name()] for field in feature.fields()}
            action_id = str(data.get("action_id") or feature.id())
            baseline = cls._number(data.get("baseline_value"))
            target = cls._number(data.get("target_value"))
            actual = cls._number(data.get("actual_value"))
            weight = cls._number(data.get("weight"))
            due_date = cls._date(data.get("due_date"), allow_none=True)
            responsible = str(data.get("responsible_institution") or "").strip()

            if baseline is None or target is None or actual is None or weight is None or weight <= 0:
                progress = None
                status = "MISSING_DATA"
                message = 'Başlangıç, hedef, gerçekleşen ve pozitif ağırlık değerleri gereklidir.'
            elif not responsible:
                progress = cls._progress(baseline, target, actual)
                status = "MISSING_DATA"
                message = 'Sorumlu kurum kaydedilmemiştir.'
            elif due_date is None:
                progress = cls._progress(baseline, target, actual)
                status = "MISSING_DATA"
                message = 'YYYY-AA-GG biçiminde geçerli bir bitiş tarihi kaydedilmemiştir.'
            else:
                progress = cls._progress(baseline, target, actual)
                weighted_total += progress * weight
                weight_sum += weight
                if progress >= 1.0 - 1e-9:
                    status = "COMPLETE"
                    message = 'Ölçülebilir eylem hedefine ulaşılmıştır.'
                elif due_date and due_date < evaluated_on:
                    status = "DELAYED"
                    message = 'Eylem beyan edilen bitiş tarihinden sonra hâlâ tamamlanmamıştır.'
                else:
                    status = "IN_PROGRESS"
                    message = 'Eylem beyan edilen izleme süresi içindedir.'
            records.append(MSPActionRecord(feature, action_id, progress, status, message))

        record_tuple = tuple(records)
        return MSPMonitoringResult(
            record_tuple,
            weighted_total / weight_sum if weight_sum > 0 else None,
            sum(item.status == "COMPLETE" for item in record_tuple),
            sum(item.status == "DELAYED" for item in record_tuple),
            sum(item.status == "MISSING_DATA" for item in record_tuple),
        )

    @staticmethod
    def _progress(baseline: float, target: float, actual: float) -> float:
        if abs(target - baseline) <= 1e-12:
            return 1.0 if abs(actual - target) <= 1e-12 else 0.0
        return max(0.0, min(1.0, (actual - baseline) / (target - baseline)))

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _date(value: Any, allow_none: bool = False) -> date | None:
        if value in (None, "", "NULL") and allow_none:
            return None
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except (TypeError, ValueError) as error:
            if allow_none:
                return None
            raise ValueError('Değerlendirme tarihi YYYY-AA-GG biçimini kullanmalıdır.') from error
