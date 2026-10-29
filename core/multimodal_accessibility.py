"""Time-weighted multimodal accessibility for MPYY transport review."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Any, Callable, Iterable, Mapping

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsSpatialIndex

from .attr_utils import linearize_geometry


@dataclass(frozen=True)
class MultimodalAccessibilityRecord:
    feature: QgsFeature
    status: str
    route_time_min: float | None
    facility_id: str
    modes: str
    snap_distance_m: float | None
    message: str


@dataclass(frozen=True)
class MultimodalAccessibilityResult:
    records: tuple[MultimodalAccessibilityRecord, ...]
    accessible_count: int
    inaccessible_count: int
    unreachable_count: int
    unsnapped_count: int
    graph_node_count: int
    graph_edge_count: int
    skipped_edge_count: int


@dataclass(frozen=True, slots=True, eq=False)
class _ModeChain:
    mode: str
    tail: _ModeChain | None


class MPYYMultimodalAccessibilityEngine:
    MODES = {"WALK", "BICYCLE", "TRANSIT"}
    MODE_MAP = {
        "WALK": "WALK", "YAYA": "WALK", "PEDESTRIAN": "WALK",
        "BICYCLE": "BICYCLE", "BISIKLET": "BICYCLE", "BIKE": "BICYCLE",
        "TRANSIT": "TRANSIT", "TOPLU_TASIMA": "TRANSIT", "BUS": "TRANSIT",
        "METRO": "TRANSIT", "TRAMVAY": "TRANSIT",
    }

    @classmethod
    def analyze(
        cls,
        network_features: Iterable[QgsFeature],
        demand_features: Iterable[QgsFeature],
        facility_features: Iterable[QgsFeature],
        maximum_time_min: float,
        mode_field: str = "mode",
        speed_field: str = "speed_kmh",
        travel_time_field: str = "travel_time_min",
        direction_field: str = "direction",
        walk_speed_kmh: float = 4.8,
        bicycle_speed_kmh: float = 15.0,
        transit_speed_kmh: float = 25.0,
        transfer_penalty_min: float = 3.0,
        snap_tolerance_m: float = 1.0,
        maximum_snap_distance_m: float = 50.0,
        cancel_check: Callable[[], bool] | None = None,
    ) -> MultimodalAccessibilityResult:
        numbers = (
            maximum_time_min, walk_speed_kmh, bicycle_speed_kmh, transit_speed_kmh,
            snap_tolerance_m,
        )
        if any(not math.isfinite(value) or value <= 0 for value in numbers):
            raise ValueError('Süre, hızlar ve yakalama toleransı sonlu pozitif değerler olmalıdır.')
        if not math.isfinite(transfer_penalty_min) or transfer_penalty_min < 0:
            raise ValueError('Aktarma cezası sonlu ve negatif olmayan bir değer olmalıdır.')
        if not math.isfinite(maximum_snap_distance_m) or maximum_snap_distance_m < 0:
            raise ValueError('En fazla yakalama mesafesi sonlu ve negatif olmayan bir değer olmalıdır.')
        speeds = {
            "WALK": walk_speed_kmh, "BICYCLE": bicycle_speed_kmh,
            "TRANSIT": transit_speed_kmh,
        }
        cls._check_canceled(cancel_check)
        incoming, coordinates, edge_count, skipped = cls._build_graph(
            network_features, snap_tolerance_m, mode_field, speed_field,
            travel_time_field, direction_field, speeds, reverse=True, cancel_check=cancel_check,
        )
        spatial_index, node_by_id = cls._node_index(coordinates, cancel_check)
        distances = {}
        facility_by_state = {}
        modes_by_state = {}
        queue = []
        sequence = 0
        for facility in facility_features:
            cls._check_canceled(cancel_check)
            snapped = cls._snap(facility, spatial_index, node_by_id, coordinates)
            if snapped is None or snapped[1] > maximum_snap_distance_m:
                continue
            node, snap_distance = snapped
            initial_time = cls._minutes(snap_distance, walk_speed_kmh)
            state = (node, "")
            if initial_time < distances.get(state, math.inf):
                distances[state] = initial_time
                facility_by_state[state] = str(facility.id())
                modes_by_state[state] = None
                sequence += 1
                heapq.heappush(queue, (initial_time, sequence, node, ""))
        while queue:
            cls._check_canceled(cancel_check)
            distance, _order, node, current_mode = heapq.heappop(queue)
            state = (node, current_mode)
            if distance > distances.get(state, math.inf) + 1e-9:
                continue
            for neighbor, next_mode, edge_time in incoming.get(node, ()):
                transfer = transfer_penalty_min if current_mode and current_mode != next_mode else 0.0
                candidate = distance + edge_time + transfer
                next_state = (neighbor, next_mode)
                if candidate + 1e-9 < distances.get(next_state, math.inf):
                    distances[next_state] = candidate
                    facility_by_state[next_state] = facility_by_state[state]
                    old_modes = modes_by_state[state]
                    modes_by_state[next_state] = (
                        old_modes if old_modes and old_modes.mode == next_mode
                        else _ModeChain(next_mode, old_modes)
                    )
                    sequence += 1
                    heapq.heappush(queue, (candidate, sequence, neighbor, next_mode))
        best_by_node = {}
        for state, value in distances.items():
            node = state[0]
            if node not in best_by_node or value < best_by_node[node][0]:
                best_by_node[node] = (value, state)
        records = []
        mode_text = {}
        for demand in demand_features:
            cls._check_canceled(cancel_check)
            snapped = cls._snap(demand, spatial_index, node_by_id, coordinates)
            if snapped is None or snapped[1] > maximum_snap_distance_m:
                records.append(MultimodalAccessibilityRecord(
                    demand, "UNSNAPPED", None, "", "", snapped[1] if snapped else None,
                    'Talep nesnesi maksimum ağ yakalama mesafesinin dışındadır.',
                ))
                continue
            node, snap_distance = snapped
            best = best_by_node.get(node)
            if best is None:
                records.append(MultimodalAccessibilityRecord(
                    demand, "UNREACHABLE", None, "", "", snap_distance,
                    'Bu ağ bileşeninde bir donatıya çok türlü ulaşım güzergâhı yoktur.',
                ))
                continue
            network_time, best_state = best
            total_time = network_time + cls._minutes(snap_distance, walk_speed_kmh)
            status = "ACCESSIBLE" if total_time <= maximum_time_min + 1e-9 else "INACCESSIBLE"
            chain = modes_by_state.get(best_state)
            if chain not in mode_text:
                # Persistent tails avoid copying an entire route into every search state.
                modes = []
                current = chain
                while current is not None:
                    modes.append(current.mode)
                    current = current.tail
                mode_text[chain] = ">".join(modes)
            records.append(MultimodalAccessibilityRecord(
                demand, status, total_time, facility_by_state.get(best_state, ""),
                mode_text[chain], snap_distance,
                'Bir donatıya beyan edilen yolculuk süresi eşiği içinde ulaşılabilmektedir.'
                if status == "ACCESSIBLE"
                else 'En yakın çok türlü erişilebilir donatı beyan edilen yolculuk süresi eşiğini aşmaktadır.',
            ))
        records_tuple = tuple(records)
        return MultimodalAccessibilityResult(
            records_tuple,
            sum(item.status == "ACCESSIBLE" for item in records_tuple),
            sum(item.status == "INACCESSIBLE" for item in records_tuple),
            sum(item.status == "UNREACHABLE" for item in records_tuple),
            sum(item.status == "UNSNAPPED" for item in records_tuple),
            len(coordinates), edge_count, skipped,
        )

    @classmethod
    def _build_graph(
        cls, features, tolerance, mode_field, speed_field, time_field, direction_field, speeds,
        reverse=False, cancel_check=None,
    ):
        adjacency = {}
        coordinates = {}
        edge_count = 0
        skipped = 0
        for feature in features:
            cls._check_canceled(cancel_check)
            values = cls._attributes(feature)
            raw_mode = str(values.get(mode_field.lower(), "")).strip().upper()
            mode = cls.MODE_MAP.get(raw_mode, raw_mode)
            direction = str(values.get(direction_field.lower(), "BOTH") or "BOTH").strip().upper()
            geometry = feature.geometry()
            if mode not in cls.MODES or direction not in {"BOTH", "FT", "TF", "FORWARD", "REVERSE"}:
                skipped += 1
                continue
            if not geometry or geometry.isEmpty():
                skipped += 1
                continue
            speed = cls._positive(values.get(speed_field.lower())) or speeds[mode]
            explicit_time = cls._positive(values.get(time_field.lower()))
            total_length = geometry.length()
            geom_lin = linearize_geometry(geometry)
            lines = geom_lin.asMultiPolyline() if geom_lin.isMultipart() else [geom_lin.asPolyline()]
            feature_added = False
            for line in lines:
                for index in range(len(line) - 1):
                    if index % 1024 == 0:
                        cls._check_canceled(cancel_check)
                    first, second = line[index], line[index + 1]
                    length = math.hypot(second.x() - first.x(), second.y() - first.y())
                    if length <= 0:
                        continue
                    first_node = cls._node(first.x(), first.y(), tolerance)
                    second_node = cls._node(second.x(), second.y(), tolerance)
                    coordinates.setdefault(first_node, (first.x(), first.y()))
                    coordinates.setdefault(second_node, (second.x(), second.y()))
                    travel_time = (
                        explicit_time * length / total_length
                        if explicit_time and total_length > 0 else cls._minutes(length, speed)
                    )
                    if direction in {"BOTH", "FT", "FORWARD"}:
                        origin, target = (second_node, first_node) if reverse else (first_node, second_node)
                        adjacency.setdefault(origin, []).append((target, mode, travel_time))
                        edge_count += 1
                    if direction in {"BOTH", "TF", "REVERSE"}:
                        origin, target = (first_node, second_node) if reverse else (second_node, first_node)
                        adjacency.setdefault(origin, []).append((target, mode, travel_time))
                        edge_count += 1
                    feature_added = True
            if not feature_added:
                skipped += 1
        return adjacency, coordinates, edge_count, skipped

    @staticmethod
    def _node_index(coordinates, cancel_check=None):
        index = QgsSpatialIndex()
        node_by_id = {}
        for feature_id, (node, point) in enumerate(coordinates.items()):
            MPYYMultimodalAccessibilityEngine._check_canceled(cancel_check)
            feature = QgsFeature()
            feature.setId(feature_id)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
            index.addFeature(feature)
            node_by_id[feature_id] = node
        return index, node_by_id

    @staticmethod
    def _snap(feature, index, node_by_id, coordinates):
        geometry = feature.geometry()
        if not geometry or geometry.isEmpty() or not coordinates:
            return None
        point = geometry.pointOnSurface().asPoint()
        nearest = index.nearestNeighbor(QgsPointXY(point), 1)
        if not nearest:
            return None
        node = node_by_id[nearest[0]]
        coordinate = coordinates[node]
        return node, math.hypot(point.x() - coordinate[0], point.y() - coordinate[1])

    @staticmethod
    def _attributes(feature: QgsFeature) -> Mapping[str, Any]:
        return {field.name().lower(): feature[field.name()] for field in feature.fields()}

    @staticmethod
    def _minutes(distance_m: float, speed_kmh: float) -> float:
        return distance_m / (speed_kmh * 1000.0 / 60.0)

    @staticmethod
    def _positive(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    @staticmethod
    def _node(x: float, y: float, tolerance: float) -> tuple[int, int]:
        return round(x / tolerance), round(y / tolerance)

    @staticmethod
    def _check_canceled(cancel_check: Callable[[], bool] | None) -> None:
        if cancel_check is not None and cancel_check():
            raise ValueError("Erişilebilirlik analizi iptal edildi (canceled).")
