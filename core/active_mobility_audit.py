"""MPYY Articles 23-24 pedestrian and bicycle network connectivity audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from qgis.core import QgsFeature, QgsGeometry


@dataclass(frozen=True)
class ActiveMobilityRecord:
    feature: QgsFeature
    component_id: int
    component_feature_count: int
    status: str
    dead_end_count: int
    message: str


@dataclass(frozen=True)
class ActiveMobilityAuditResult:
    records: tuple[ActiveMobilityRecord, ...]
    component_count: int
    disconnected_feature_count: int
    center_count: int
    unserved_center_count: int


class ActiveMobilityAuditEngine:
    """Builds an endpoint graph and reports disconnected network components."""

    @classmethod
    def audit(
        cls,
        network_features: Iterable[QgsFeature],
        center_features: Iterable[QgsFeature] = (),
        snap_tolerance: float = 1.0,
        center_access_distance: float = 25.0,
    ) -> ActiveMobilityAuditResult:
        if snap_tolerance <= 0.0 or center_access_distance < 0.0:
            raise ValueError('Yakalama toleransı pozitif olmalı ve merkez mesafesi negatif olmamalıdır.')
        features = list(network_features)
        nodes_by_feature = {}
        adjacency = {}
        for feature in features:
            endpoint_pairs = cls._segments(feature.geometry())
            feature_nodes = set()
            for first, last in endpoint_pairs:
                first_key = cls._node_key(first.x(), first.y(), snap_tolerance)
                last_key = cls._node_key(last.x(), last.y(), snap_tolerance)
                adjacency.setdefault(first_key, set()).add(last_key)
                adjacency.setdefault(last_key, set()).add(first_key)
                feature_nodes.update((first_key, last_key))
            nodes_by_feature[feature.id()] = feature_nodes

        component_by_node = {}
        components = []
        for node in adjacency:
            if node in component_by_node:
                continue
            component_id = len(components)
            stack = [node]
            component_nodes = set()
            while stack:
                current = stack.pop()
                if current in component_nodes:
                    continue
                component_nodes.add(current)
                component_by_node[current] = component_id
                stack.extend(adjacency[current] - component_nodes)
            components.append(component_nodes)

        feature_components = {}
        for feature in features:
            nodes = nodes_by_feature.get(feature.id(), set())
            feature_components[feature.id()] = component_by_node[next(iter(nodes))] if nodes else -1
        component_sizes = {
            component_id: sum(value == component_id for value in feature_components.values())
            for component_id in range(len(components))
        }
        main_component = max(component_sizes, key=component_sizes.get) if component_sizes else -1
        records = []
        for feature in features:
            component_id = feature_components[feature.id()]
            if component_id < 0:
                status = "INVALID_GEOMETRY"
                message = 'Ağ nesnesinin kullanılabilir çizgi uç noktaları yok.'
                dead_ends = 0
            else:
                dead_ends = sum(
                    len(adjacency[node]) == 1 for node in nodes_by_feature[feature.id()]
                )
                status = "CONNECTED" if component_id == main_component else "DISCONNECTED"
                message = (
                    'Nesne ana aktif ulaşım ağına bağlıdır.'
                    if status == "CONNECTED"
                    else 'Nesne bağlantısız bir ikincil ağ bileşenine bağlıdır.'
                )
            records.append(ActiveMobilityRecord(
                feature, component_id, component_sizes.get(component_id, 0),
                status, dead_ends, message,
            ))

        network_geometries = [
            feature.geometry() for feature in features
            if feature.hasGeometry() and not feature.geometry().isEmpty()
        ]
        centers = list(center_features)
        unserved = 0
        for center in centers:
            geometry = center.geometry()
            if not geometry or geometry.isEmpty() or not network_geometries:
                unserved += 1
                continue
            point_geometry = QgsGeometry.fromPointXY(geometry.pointOnSurface().asPoint())
            if min(point_geometry.distance(line) for line in network_geometries) > center_access_distance:
                unserved += 1
        record_tuple = tuple(records)
        return ActiveMobilityAuditResult(
            record_tuple,
            len(components),
            sum(item.status == "DISCONNECTED" for item in record_tuple),
            len(centers),
            unserved,
        )

    @staticmethod
    def _node_key(x: float, y: float, tolerance: float) -> tuple[int, int]:
        return round(x / tolerance), round(y / tolerance)

    @staticmethod
    def _segments(geometry: QgsGeometry):
        if not geometry or geometry.isEmpty():
            return []
        polylines = geometry.asMultiPolyline() if geometry.isMultipart() else [geometry.asPolyline()]
        return [
            (line[index], line[index + 1])
            for line in polylines
            for index in range(len(line) - 1)
        ]
