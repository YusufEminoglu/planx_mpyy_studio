"""PlanX urban analytics adapted as MPYY planning-report evidence tools."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from qgis.core import QgsFeature, QgsGeometry, QgsSpatialIndex


@dataclass(frozen=True)
class BuildingMorphologyRecord:
    feature: QgsFeature
    area_m2: float
    perimeter_m: float
    compactness: float
    convexity: float
    rectangularity: float
    elongation: float
    orientation_deg: float
    shared_wall_ratio: float
    status: str


class MPYYBuildingMorphologyEngine:
    """Measures existing/proposed building form without imposing typology thresholds."""

    @classmethod
    def analyze(cls, features: Iterable[QgsFeature]) -> tuple[BuildingMorphologyRecord, ...]:
        valid = [
            feature for feature in features
            if feature.geometry() and not feature.geometry().isEmpty()
        ]
        index = QgsSpatialIndex()
        for indexed_feature in valid:
            index.addFeature(indexed_feature)
        by_id = {feature.id(): feature for feature in valid}
        records = []
        for feature in valid:
            geometry = feature.geometry()
            if not geometry.isGeosValid() or geometry.area() <= 0:
                records.append(BuildingMorphologyRecord(
                    feature, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                    "GECERSIZ_GEOMETRI",
                ))
                continue
            area = geometry.area()
            perimeter = geometry.length()
            hull_area = geometry.convexHull().area()
            _box, box_area, angle, width, height = geometry.orientedMinimumBoundingBox()
            long_side = max(width, height)
            short_side = min(width, height)
            shared = 0.0
            boundary = QgsGeometry(geometry.constGet().boundary())
            for neighbor_id in index.intersects(geometry.boundingBox()):
                if neighbor_id == feature.id():
                    continue
                neighbor = by_id.get(neighbor_id)
                if neighbor is None or not geometry.intersects(neighbor.geometry()):
                    continue
                other_boundary = QgsGeometry(neighbor.geometry().constGet().boundary())
                intersection = boundary.intersection(other_boundary)
                if intersection and not intersection.isEmpty():
                    shared += intersection.length()
            records.append(BuildingMorphologyRecord(
                feature, area, perimeter,
                4.0 * math.pi * area / (perimeter * perimeter) if perimeter > 0 else 0.0,
                area / hull_area if hull_area > 0 else 0.0,
                area / box_area if box_area > 0 else 0.0,
                1.0 - short_side / long_side if long_side > 0 else 0.0,
                float(angle) % 180.0,
                min(1.0, shared / perimeter) if perimeter > 0 else 0.0,
                "OLCULDU",
            ))
        return tuple(records)


@dataclass(frozen=True)
class SpacematrixRecord:
    feature: QgsFeature
    building_count: int
    footprint_m2: float
    floor_area_m2: float
    gsi: float
    fsi: float
    osr: float
    mean_levels: float
    status: str


class MPYYSpacematrixEngine:
    """Computes GSI, FSI, OSR, and mean floors for MPYY report analysis units."""

    @classmethod
    def analyze(
        cls, buildings: Iterable[QgsFeature], blocks: Iterable[QgsFeature],
        levels_field: str = "", default_levels: float = 2.0,
    ) -> tuple[SpacematrixRecord, ...]:
        if not math.isfinite(default_levels) or default_levels < 0:
            raise ValueError('Varsayılan kat sayısı sonlu ve negatif olmayan bir değer olmalıdır.')
        building_rows = []
        index = QgsSpatialIndex()
        for position, feature in enumerate(buildings):
            geometry = feature.geometry()
            if not geometry or geometry.isEmpty() or geometry.area() <= 0:
                continue
            levels = default_levels
            if levels_field:
                try:
                    candidate = float(feature[levels_field])
                    if math.isfinite(candidate) and candidate >= 0:
                        levels = candidate
                except (KeyError, TypeError, ValueError):
                    levels = default_levels
            indexed = QgsFeature(position)
            indexed.setGeometry(geometry)
            index.addFeature(indexed)
            building_rows.append((position, geometry, levels))
        by_index = {position: (geometry, levels) for position, geometry, levels in building_rows}
        records = []
        for block in blocks:
            geometry = block.geometry()
            if not geometry or geometry.isEmpty() or geometry.area() <= 0:
                records.append(SpacematrixRecord(
                    block, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "GECERSIZ_GEOMETRI"
                ))
                continue
            footprint = 0.0
            floor_area = 0.0
            count = 0
            for building_id in index.intersects(geometry.boundingBox()):
                row = by_index.get(building_id)
                if row is None:
                    continue
                building_geometry, levels = row
                intersection = geometry.intersection(building_geometry)
                if not intersection or intersection.isEmpty():
                    continue
                area = intersection.area()
                if area <= 0:
                    continue
                footprint += area
                floor_area += area * levels
                count += 1
            block_area = geometry.area()
            gsi = footprint / block_area
            fsi = floor_area / block_area
            records.append(SpacematrixRecord(
                block, count, footprint, floor_area, gsi, fsi,
                (1.0 - gsi) / fsi if fsi > 0 else 0.0,
                fsi / gsi if gsi > 0 else 0.0,
                "OLCULDU",
            ))
        return tuple(records)


@dataclass(frozen=True)
class StreetMorphologyResult:
    node_count: int
    edge_count: int
    component_count: int
    dead_end_count: int
    intersection_count: int
    total_length_m: float
    mean_segment_length_m: float
    orientation_entropy: float
    orientation_order: float
    alpha: float
    beta: float
    gamma: float


class MPYYStreetMorphologyEngine:
    """Adapts PlanX orientation and meshedness metrics for MPYY transport evidence."""

    @classmethod
    def analyze(
        cls, features: Iterable[QgsFeature], snap_tolerance_m: float = 1.0,
        orientation_bins: int = 36,
    ) -> StreetMorphologyResult:
        if not math.isfinite(snap_tolerance_m) or snap_tolerance_m <= 0:
            raise ValueError('Yakalama toleransı sonlu pozitif bir metrik değer olmalıdır.')
        if orientation_bins < 8 or orientation_bins > 180:
            raise ValueError('Yönelim sınıfı sayısı 8 ile 180 arasında olmalıdır.')
        adjacency = {}
        bearings = []
        lengths = []
        for feature in features:
            geometry = feature.geometry()
            if not geometry or geometry.isEmpty():
                continue
            lines = geometry.asMultiPolyline() if geometry.isMultipart() else [geometry.asPolyline()]
            for line in lines:
                for index in range(len(line) - 1):
                    first, second = line[index], line[index + 1]
                    length = math.hypot(second.x() - first.x(), second.y() - first.y())
                    if length <= 0:
                        continue
                    first_node = cls._node(first.x(), first.y(), snap_tolerance_m)
                    second_node = cls._node(second.x(), second.y(), snap_tolerance_m)
                    if first_node == second_node:
                        continue
                    adjacency.setdefault(first_node, set()).add(second_node)
                    adjacency.setdefault(second_node, set()).add(first_node)
                    bearing = math.degrees(math.atan2(
                        second.x() - first.x(), second.y() - first.y()
                    )) % 180.0
                    bearings.append(bearing)
                    lengths.append(length)
        nodes = len(adjacency)
        edges = sum(len(value) for value in adjacency.values()) // 2
        components = cls._components(adjacency)
        entropy, order = cls._orientation(bearings, lengths, orientation_bins)
        alpha_denominator = 2 * nodes - 5
        gamma_denominator = 3 * (nodes - 2)
        return StreetMorphologyResult(
            nodes, edges, components,
            sum(len(value) == 1 for value in adjacency.values()),
            sum(len(value) >= 3 for value in adjacency.values()),
            sum(lengths), sum(lengths) / len(lengths) if lengths else 0.0,
            entropy, order,
            max(0.0, (edges - nodes + max(1, components)) / alpha_denominator)
            if alpha_denominator > 0 else 0.0,
            edges / nodes if nodes else 0.0,
            max(0.0, edges / gamma_denominator) if gamma_denominator > 0 else 0.0,
        )

    @staticmethod
    def _components(adjacency) -> int:
        seen = set()
        count = 0
        for start in adjacency:
            if start in seen:
                continue
            count += 1
            stack = [start]
            seen.add(start)
            while stack:
                node = stack.pop()
                for neighbor in adjacency[node]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        return count

    @staticmethod
    def _orientation(bearings, lengths, bins):
        if not bearings or sum(lengths) <= 0:
            return 0.0, 0.0
        histogram = [0.0] * bins
        width = 180.0 / bins
        for bearing, length in zip(bearings, lengths):
            histogram[min(bins - 1, int(((bearing + width / 2.0) % 180.0) / width))] += length
        total = sum(histogram)
        probabilities = [value / total for value in histogram if value > 0]
        entropy = -sum(value * math.log(value) for value in probabilities)
        maximum = math.log(bins)
        grid = math.log(2.0)
        order = 1.0 - ((entropy - grid) / (maximum - grid)) ** 2 if maximum > grid else 0.0
        return entropy, min(1.0, max(0.0, order))

    @staticmethod
    def _node(x, y, tolerance):
        return round(x / tolerance), round(y / tolerance)


class MPYYScenarioComparisonEngine:
    DIRECTIONS = {"HIGHER", "LOWER", "NEUTRAL"}

    @classmethod
    def compare(cls, first: Mapping[str, Any], second: Mapping[str, Any]) -> list[dict[str, Any]]:
        first_name = str(first.get("name", "")).strip()
        second_name = str(second.get("name", "")).strip()
        if not first_name or not second_name:
            raise ValueError('İki senaryo için de ad gereklidir.')
        left = cls._metrics(first)
        right = cls._metrics(second)
        rows = []
        for key in sorted(set(left) | set(right)):
            a = left.get(key)
            b = right.get(key)
            if a is None or b is None:
                rows.append({
                    "key": key, "label": (a or b)["label"],
                    "value_a": a["value"] if a else None,
                    "value_b": b["value"] if b else None,
                    "delta": None, "delta_ratio": None, "preferred": "EKSIK_VERI",
                })
                continue
            if a["direction"] != b["direction"]:
                raise ValueError('Gösterge yönü senaryolar arasında farklıdır: ' + key)
            delta = b["value"] - a["value"]
            direction = a["direction"]
            if direction == "NEUTRAL" or abs(delta) <= 1e-12:
                preferred = "ESIT_NÖTR"
            elif (direction == "HIGHER" and delta > 0) or (direction == "LOWER" and delta < 0):
                preferred = second_name
            else:
                preferred = first_name
            rows.append({
                "key": key, "label": a["label"], "value_a": a["value"],
                "value_b": b["value"], "delta": delta,
                "delta_ratio": delta / abs(a["value"]) if a["value"] != 0 else None,
                "preferred": preferred,
            })
        return rows

    @classmethod
    def read_and_compare(cls, first_path: str | Path, second_path: str | Path):
        return cls.compare(cls._read(first_path), cls._read(second_path))

    @classmethod
    def _metrics(cls, scenario):
        metrics = scenario.get("metrics", [])
        if not isinstance(metrics, list):
            raise ValueError('Senaryo göstergeleri bir JSON dizisi olmalıdır.')
        result = {}
        for item in metrics:
            if not isinstance(item, Mapping):
                raise ValueError('Her senaryo göstergesi bir JSON nesnesi olmalıdır.')
            key = str(item.get("key", "")).strip()
            direction = str(item.get("direction", "NEUTRAL")).strip().upper()
            if not key or key in result or direction not in cls.DIRECTIONS:
                raise ValueError('Senaryo göstergesi anahtarı/yönü geçersiz veya yinelenmiştir.')
            try:
                value = float(item.get("value"))
            except (TypeError, ValueError) as error:
                raise ValueError('Senaryo göstergesi değeri sayısal olmalıdır: ' + key) from error
            if not math.isfinite(value):
                raise ValueError('Senaryo göstergesi değeri sonlu olmalıdır: ' + key)
            result[key] = {
                "label": str(item.get("label", key)).strip() or key,
                "value": value, "direction": direction,
            }
        return result

    @staticmethod
    def _read(path):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError('Senaryo dosyası okunamadı: ' + str(error)) from error
        if not isinstance(payload, Mapping):
            raise ValueError('Senaryo kökü bir JSON nesnesi olmalıdır.')
        return payload


@dataclass(frozen=True)
class AccessEquityResult:
    unit_count: int
    population: float
    weighted_mean: float
    weighted_median: float
    gini: float
    coefficient_of_variation: float
    p90_p10: float
    threshold_share: float | None


class MPYYAccessEquityEngine:
    """Pure-Python weighted access distribution metrics adapted from PlanX."""

    @classmethod
    def analyze(
        cls, values: Iterable[float], weights: Iterable[float] | None = None,
        threshold: float | None = None, higher_is_better: bool = True,
    ) -> AccessEquityResult:
        raw_values = list(values)
        raw_weights = list(weights) if weights is not None else [1.0] * len(raw_values)
        if len(raw_values) != len(raw_weights):
            raise ValueError('Değerler ile nüfus ağırlıkları aynı uzunlukta olmalıdır.')
        cleaned = []
        for value, weight in zip(raw_values, raw_weights):
            try:
                numeric = float(value)
                population = float(weight)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric) and math.isfinite(population) and population > 0:
                cleaned.append((max(0.0, numeric), population))
        if not cleaned:
            raise ValueError('Pozitif nüfus ağırlığına sahip sonlu değer bulunamadı.')
        cleaned.sort(key=lambda item: item[0])
        total_weight = sum(item[1] for item in cleaned)
        total_value = sum(value * weight for value, weight in cleaned)
        mean = total_value / total_weight
        variance = sum(weight * (value - mean) ** 2 for value, weight in cleaned) / total_weight
        gini_numerator = 0.0
        weight_below = 0.0
        value_below = 0.0
        for value, weight in cleaned:
            gini_numerator += weight * (value * weight_below - value_below)
            weight_below += weight
            value_below += weight * value
        gini = gini_numerator / (total_weight * total_value) if total_value > 0 else 0.0
        p10 = cls._quantile(cleaned, 0.10, total_weight)
        p50 = cls._quantile(cleaned, 0.50, total_weight)
        p90 = cls._quantile(cleaned, 0.90, total_weight)
        threshold_share = None
        if threshold is not None:
            threshold_value = float(threshold)
            if not math.isfinite(threshold_value):
                raise ValueError('Eşik değeri sonlu olmalıdır.')
            selected = sum(
                weight for value, weight in cleaned
                if (value < threshold_value if higher_is_better else value > threshold_value)
            )
            threshold_share = selected / total_weight
        return AccessEquityResult(
            len(cleaned), total_weight, mean, p50, gini,
            math.sqrt(max(0.0, variance)) / abs(mean) if mean != 0 else 0.0,
            p90 / p10 if p10 > 0 else 0.0, threshold_share,
        )

    @staticmethod
    def _quantile(rows, quantile, total_weight):
        target = quantile * total_weight
        cumulative = 0.0
        for value, weight in rows:
            cumulative += weight
            if cumulative >= target:
                return value
        return rows[-1][0]
