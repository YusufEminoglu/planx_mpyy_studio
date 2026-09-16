"""MPYY Articles 23-24 routed accessibility analysis."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Iterable

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsSpatialIndex


@dataclass(frozen=True)
class RoutedAccessibilityRecord:
    feature: QgsFeature
    status: str
    route_distance_m: float | None
    facility_id: str
    snap_distance_m: float | None
    message: str


@dataclass(frozen=True)
class RoutedAccessibilityResult:
    records: tuple[RoutedAccessibilityRecord, ...]
    accessible_count: int
    inaccessible_count: int
    unreachable_count: int
    unsnapped_count: int
    graph_node_count: int
    graph_edge_count: int


class RoutedAccessibilityEngine:
    """Uses a snapped line graph and multi-source Dijkstra shortest paths."""

    @classmethod
    def analyze(
        cls,
        network_features: Iterable[QgsFeature],
        demand_features: Iterable[QgsFeature],
        facility_features: Iterable[QgsFeature],
        maximum_route_distance_m: float,
        snap_tolerance_m: float = 1.0,
        maximum_snap_distance_m: float = 50.0,
    ) -> RoutedAccessibilityResult:
        if maximum_route_distance_m <= 0 or snap_tolerance_m <= 0 or maximum_snap_distance_m < 0:
            raise ValueError('Güzergâh ve yakalama mesafeleri geçerli pozitif metrik değerler olmalıdır.')
        adjacency, coordinates, edge_count = cls._build_graph(network_features, snap_tolerance_m)
        index = QgsSpatialIndex()
        node_by_feature_id = {}
        for feature_id, (node, point) in enumerate(coordinates.items()):
            feature = QgsFeature()
            feature.setId(feature_id)
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
            index.addFeature(feature)
            node_by_feature_id[feature_id] = node

        distances = {node: math.inf for node in coordinates}
        facility_for_node = {}
        queue = []
        for facility in facility_features:
            snapped = cls._snap(facility, index, node_by_feature_id, coordinates)
            if snapped is None or snapped[1] > maximum_snap_distance_m:
                continue
            node, snap_distance = snapped
            if snap_distance < distances[node]:
                distances[node] = snap_distance
                facility_for_node[node] = str(facility.id())
                heapq.heappush(queue, (snap_distance, node, str(facility.id())))
        while queue:
            distance, node, facility_id = heapq.heappop(queue)
            if distance > distances[node] + 1e-9:
                continue
            for neighbor, weight in adjacency.get(node, {}).items():
                candidate = distance + weight
                if candidate + 1e-9 < distances[neighbor]:
                    distances[neighbor] = candidate
                    facility_for_node[neighbor] = facility_id
                    heapq.heappush(queue, (candidate, neighbor, facility_id))

        records = []
        for demand in demand_features:
            snapped = cls._snap(demand, index, node_by_feature_id, coordinates)
            if snapped is None or snapped[1] > maximum_snap_distance_m:
                records.append(RoutedAccessibilityRecord(
                    demand, "UNSNAPPED", None, "", snapped[1] if snapped else None,
                    "Demand feature is outside the maximum network snap distance.",
                ))
                continue
            node, snap_distance = snapped
            network_distance = distances.get(node, math.inf)
            if not math.isfinite(network_distance):
                records.append(RoutedAccessibilityRecord(
                    demand, "UNREACHABLE", None, "", snap_distance,
                    'Bu ağ bileşeninde bir donatıya ulaşan güzergâh bağlantısı yoktur.',
                ))
                continue
            total_distance = snap_distance + network_distance
            status = "ACCESSIBLE" if total_distance <= maximum_route_distance_m + 1e-9 else "INACCESSIBLE"
            records.append(RoutedAccessibilityRecord(
                demand, status, total_distance, facility_for_node.get(node, ""), snap_distance,
                'Bir donatıya güzergâh eşiği içinde ulaşılabilmektedir.'
                if status == "ACCESSIBLE"
                else "Nearest routed facility exceeds the route threshold.",
            ))
        record_tuple = tuple(records)
        return RoutedAccessibilityResult(
            record_tuple,
            sum(item.status == "ACCESSIBLE" for item in record_tuple),
            sum(item.status == "INACCESSIBLE" for item in record_tuple),
            sum(item.status == "UNREACHABLE" for item in record_tuple),
            sum(item.status == "UNSNAPPED" for item in record_tuple),
            len(coordinates), edge_count,
        )

    @classmethod
    def _build_graph(cls, features: Iterable[QgsFeature], tolerance: float):
        adjacency = {}
        coordinates = {}
        for feature in features:
            geometry = feature.geometry()
            if not geometry or geometry.isEmpty():
                continue
            lines = geometry.asMultiPolyline() if geometry.isMultipart() else [geometry.asPolyline()]
            for line in lines:
                for index in range(len(line) - 1):
                    first, second = line[index], line[index + 1]
                    first_node = cls._node(first.x(), first.y(), tolerance)
                    second_node = cls._node(second.x(), second.y(), tolerance)
                    coordinates.setdefault(first_node, (first.x(), first.y()))
                    coordinates.setdefault(second_node, (second.x(), second.y()))
                    weight = math.hypot(second.x() - first.x(), second.y() - first.y())
                    if first_node == second_node or weight <= 0:
                        continue
                    old_weight = adjacency.setdefault(first_node, {}).get(second_node, math.inf)
                    adjacency[first_node][second_node] = min(old_weight, weight)
                    adjacency.setdefault(second_node, {})[first_node] = min(old_weight, weight)
        edge_count = sum(len(neighbors) for neighbors in adjacency.values()) // 2
        return adjacency, coordinates, edge_count

    @staticmethod
    def _snap(feature, index, node_by_feature_id, coordinates):
        geometry = feature.geometry()
        if not geometry or geometry.isEmpty() or not coordinates:
            return None
        point = geometry.pointOnSurface().asPoint()
        nearest = index.nearestNeighbor(QgsPointXY(point), 1)
        if not nearest:
            return None
        node = node_by_feature_id[nearest[0]]
        coordinate = coordinates[node]
        distance = math.hypot(point.x() - coordinate[0], point.y() - coordinate[1])
        return node, distance

    @staticmethod
    def _node(x: float, y: float, tolerance: float) -> tuple[int, int]:
        return round(x / tolerance), round(y / tolerance)
