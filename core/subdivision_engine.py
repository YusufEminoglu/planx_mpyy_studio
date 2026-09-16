"""Parcel subdivision and amalgamation utilities for PlanX MPYY Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from qgis.core import QgsFeature, QgsGeometry, QgsPointXY


@dataclass(frozen=True)
class SubdivisionConstraint:
    nizam: str
    min_frontage: float
    min_depth: float
    min_area: float
    max_parcels: int = 100

    def __post_init__(self) -> None:
        if not str(self.nizam).strip():
            raise ValueError('Yapı nizamı boş olamaz.')
        if self.min_frontage <= 0 or self.min_depth < 0 or self.min_area < 0:
            raise ValueError('İfraz boyutları negatif olamaz.')
        if self.max_parcels < 1:
            raise ValueError('En fazla parsel sayısı en az bir olmalıdır.')


@dataclass
class SubdivisionResult:
    source_parcel_id: str
    generated_parcels_count: int
    total_original_area: float
    subdivided_geometries: list[QgsGeometry] = field(default_factory=list)
    warning_notes: list[str] = field(default_factory=list)
    parcel_metrics: list["ParcelMetric"] = field(default_factory=list)
    area_balance_error_m2: float = 0.0


@dataclass(frozen=True)
class ParcelMetric:
    area_m2: float
    frontage_m: float
    road_frontage_m: float
    depth_m: float
    compactness: float
    aspect_ratio: float
    compliant: bool
    violations: tuple[str, ...] = ()


class SubdivisionEngine:
    """Creates road-oriented parcel strips and merges undersized remnants."""

    @staticmethod
    def constraint_for(
        nizam: str,
        land_use: str = "KONUT_TICARET",
        floors: int = 3,
        max_parcels: int = 100,
    ) -> SubdivisionConstraint:
        use_key = str(land_use or "").strip().upper()
        nizam_key = str(nizam or "").strip().upper()
        if "SANAYI" in use_key:
            return SubdivisionConstraint(nizam_key, 20.0, 30.0, 2000.0, max_parcels)
        if nizam_key.startswith("BITISIK"):
            return SubdivisionConstraint(nizam_key, 9.0 if floors >= 4 else 6.0, 14.0, 0.0, max_parcels)
        if nizam_key.startswith("BLOK"):
            return SubdivisionConstraint(nizam_key, 18.0, 18.0, 0.0, max_parcels)
        return SubdivisionConstraint(nizam_key or "AYRIK", 12.0, 18.0, 500.0, max_parcels)

    @classmethod
    def subdivide_feature(
        cls,
        parcel: QgsFeature,
        constraint: SubdivisionConstraint,
        target_frontage: float | None = None,
        road_geometries: Iterable[QgsGeometry] | None = None,
    ) -> SubdivisionResult:
        identifier = cls._feature_identifier(parcel)
        return cls.subdivide_geometry(
            parcel.geometry(),
            constraint,
            target_frontage=target_frontage,
            road_geometries=road_geometries,
            source_parcel_id=identifier,
        )

    @classmethod
    def subdivide_geometry(
        cls,
        geometry: QgsGeometry,
        constraint: SubdivisionConstraint,
        target_frontage: float | None = None,
        road_geometries: Iterable[QgsGeometry] | None = None,
        source_parcel_id: str = "",
    ) -> SubdivisionResult:
        if not geometry or geometry.isEmpty():
            return SubdivisionResult(source_parcel_id, 0, 0.0, [], ["EMPTY_GEOMETRY"])
        geom = QgsGeometry(geometry)
        warnings: list[str] = []
        source_area = float(geom.area())
        if not geom.isGeosValid():
            repaired = geom.makeValid()
            if not repaired or repaired.isEmpty():
                return SubdivisionResult(
                    source_parcel_id, 0, source_area, [], ["INVALID_GEOMETRY_COULD_NOT_BE_REPAIRED"]
                )
            geom = repaired
            warnings.append("SOURCE_GEOMETRY_REPAIRED")
        area = float(geom.area())
        if abs(area - source_area) > max(0.01, source_area * 1e-7):
            warnings.append("REPAIR_CHANGED_SOURCE_AREA")
        width = max(float(target_frontage or constraint.min_frontage), constraint.min_frontage)
        corners = cls._ombb_corners(geom)
        if len(corners) != 4:
            return SubdivisionResult(
                source_parcel_id, 1, source_area, [geom],
                warnings + ["OMBB_COULD_NOT_BE_COMPUTED"], area_balance_error_m2=area - source_area,
            )

        roads = [road for road in (road_geometries or []) if road and not road.isEmpty()]
        frontage_start, frontage_end, depth = cls._frontage_axis(corners, roads)
        frontage_length = cls._distance(frontage_start, frontage_end)
        ux = (frontage_end.x() - frontage_start.x()) / frontage_length
        uy = (frontage_end.y() - frontage_start.y()) / frontage_length
        vx, vy = -uy, ux
        if depth + 1e-7 < constraint.min_depth:
            warnings.append("MINIMUM_DEPTH_NOT_MET")
            metric = cls._measure_piece(geom, constraint, ux, uy, vx, vy, roads)
            return SubdivisionResult(
                source_parcel_id, 1, source_area, [geom], warnings, [metric], area - source_area
            )

        by_width = max(1, int(math.floor(frontage_length / width)))
        by_area = constraint.max_parcels
        if constraint.min_area > 0:
            by_area = max(1, int(math.floor(area / constraint.min_area)))
        count = min(by_width, by_area, max(1, constraint.max_parcels))
        if count <= 1:
            warnings.append("PARCEL_TOO_SMALL_FOR_LEGAL_SUBDIVISION")
            metric = cls._measure_piece(geom, constraint, ux, uy, vx, vy, roads)
            return SubdivisionResult(
                source_parcel_id, 1, source_area, [geom], warnings, [metric], area - source_area
            )

        center = geom.centroid().asPoint()
        center_projection = center.x() * vx + center.y() * vy
        span = max(frontage_length, depth, math.sqrt(max(area, 1.0))) * 4.0 + 100.0
        origin_projection = frontage_start.x() * ux + frontage_start.y() * uy
        strip_width = frontage_length / count
        pieces: list[QgsGeometry] = []

        for index in range(count):
            lo = origin_projection + index * strip_width
            hi = origin_projection + (index + 1) * strip_width
            strip = cls._axis_aligned_strip(ux, uy, vx, vy, lo, hi, center_projection, span)
            clipped = geom.intersection(strip)
            pieces.extend(cls._polygon_parts(clipped))

        pieces = [part for part in pieces if part and not part.isEmpty() and part.area() > 1e-7]
        pieces = cls._merge_noncompliant(pieces, constraint, ux, uy, vx, vy, roads, warnings)
        if not pieces:
            pieces = [geom]
            warnings.append("SUBDIVISION_FELL_BACK_TO_SOURCE")

        pieces.sort(key=lambda part: part.centroid().asPoint().x() * ux + part.centroid().asPoint().y() * uy)
        generated_area = sum(part.area() for part in pieces)
        balance_error = generated_area - source_area
        tolerance = max(0.01, source_area * 1e-7)
        if abs(balance_error) > tolerance:
            warnings.append("AREA_BALANCE_REVIEW_REQUIRED")
        metrics = [cls._measure_piece(part, constraint, ux, uy, vx, vy, roads) for part in pieces]
        if any(not metric.compliant for metric in metrics):
            warnings.append("LEGAL_DIMENSIONS_REQUIRE_REVIEW")
        return SubdivisionResult(
            source_parcel_id, len(pieces), source_area, pieces, warnings, metrics, balance_error
        )

    @staticmethod
    def _feature_identifier(feature: QgsFeature) -> str:
        for name in ("global_id", "parsel_id", "PARSEL", "parsel"):
            index = feature.fields().indexFromName(name)
            if index >= 0 and feature[index] not in (None, ""):
                return str(feature[index])
        return str(feature.id())

    @staticmethod
    def _ombb_corners(geometry: QgsGeometry) -> list[QgsPointXY]:
        result = geometry.orientedMinimumBoundingBox()
        box = result[0] if isinstance(result, tuple) else result
        if not box or box.isEmpty():
            return []
        vertices = [QgsPointXY(point) for point in box.vertices()]
        if len(vertices) < 5:
            return []
        return vertices[:4]

    @classmethod
    def _frontage_axis(
        cls,
        corners: list[QgsPointXY],
        road_geometries: Iterable[QgsGeometry] | None,
    ) -> tuple[QgsPointXY, QgsPointXY, float]:
        edges = []
        for index in range(4):
            start = corners[index]
            end = corners[(index + 1) % 4]
            edge = QgsGeometry.fromPolylineXY([start, end])
            edges.append((start, end, edge, edge.length()))

        roads = [road for road in (road_geometries or []) if road and not road.isEmpty()]
        if roads:
            def road_score(item):
                contact = max(
                    item[2].intersection(road.buffer(0.25, 4)).length()
                    for road in roads
                )
                distance = min(item[2].distance(road) for road in roads)
                return contact, -distance, item[3]
            selected = max(edges, key=road_score)
        else:
            selected = max(edges, key=lambda item: item[3])

        opposite = edges[(edges.index(selected) + 2) % 4]
        depth = selected[2].distance(opposite[2])
        return selected[0], selected[1], depth

    @staticmethod
    def _axis_aligned_strip(ux, uy, vx, vy, lo, hi, center_v, span) -> QgsGeometry:
        points = []
        for u_value, v_value in (
            (lo, center_v - span),
            (hi, center_v - span),
            (hi, center_v + span),
            (lo, center_v + span),
            (lo, center_v - span),
        ):
            points.append(QgsPointXY(ux * u_value + vx * v_value, uy * u_value + vy * v_value))
        return QgsGeometry.fromPolygonXY([points])

    @staticmethod
    def _polygon_parts(geometry: QgsGeometry) -> list[QgsGeometry]:
        if not geometry or geometry.isEmpty():
            return []
        if geometry.isMultipart():
            return [QgsGeometry.fromPolygonXY(part) for part in geometry.asMultiPolygon() if part]
        return [QgsGeometry(geometry)]

    @classmethod
    def _merge_noncompliant(
        cls,
        pieces: list[QgsGeometry],
        constraint: SubdivisionConstraint,
        ux: float,
        uy: float,
        vx: float,
        vy: float,
        road_geometries: list[QgsGeometry],
        warnings: list[str],
    ) -> list[QgsGeometry]:
        legal = list(pieces)
        while len(legal) > 1:
            undersized = [
                (index, part)
                for index, part in enumerate(legal)
                if not cls._measure_piece(
                    part, constraint, ux, uy, vx, vy, road_geometries
                ).compliant
            ]
            if not undersized:
                break
            index, remnant = min(undersized, key=lambda item: item[1].area())
            candidates = []
            for other_index, other in enumerate(legal):
                if other_index == index:
                    continue
                shared = remnant.boundary().intersection(other.boundary()).length()
                if shared > 1e-7:
                    candidates.append((shared, other_index))
            if not candidates:
                warnings.append("ISOLATED_SLIVER_REQUIRES_REVIEW")
                break
            _, neighbor_index = min(candidates, key=lambda item: item[0])
            merged = legal[neighbor_index].combine(remnant)
            for remove_index in sorted((index, neighbor_index), reverse=True):
                legal.pop(remove_index)
            legal.append(merged)
            if "NONCOMPLIANT_REMNANT_MERGED" not in warnings:
                warnings.append("NONCOMPLIANT_REMNANT_MERGED")
        return legal

    @classmethod
    def _measure_piece(
        cls,
        geometry: QgsGeometry,
        constraint: SubdivisionConstraint,
        ux: float,
        uy: float,
        vx: float,
        vy: float,
        road_geometries: list[QgsGeometry] | None = None,
    ) -> ParcelMetric:
        vertices = list(geometry.vertices())
        if not vertices:
            return ParcelMetric(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, ("EMPTY_GEOMETRY",))
        frontage_values = [point.x() * ux + point.y() * uy for point in vertices]
        depth_values = [point.x() * vx + point.y() * vy for point in vertices]
        frontage = max(frontage_values) - min(frontage_values)
        depth = max(depth_values) - min(depth_values)
        area = float(geometry.area())
        perimeter = float(geometry.length())
        compactness = 4.0 * math.pi * area / (perimeter * perimeter) if perimeter > 0 else 0.0
        minimum_dimension = min(frontage, depth)
        aspect_ratio = max(frontage, depth) / minimum_dimension if minimum_dimension > 0 else 0.0
        roads = road_geometries or []
        road_frontage = cls._road_frontage(geometry, roads) if roads else 0.0
        legal_frontage = road_frontage if roads else frontage
        violations = []
        if legal_frontage + 1e-7 < constraint.min_frontage:
            violations.append("MIN_FRONTAGE")
        if depth + 1e-7 < constraint.min_depth:
            violations.append("MIN_DEPTH")
        if constraint.min_area > 0 and area + 1e-7 < constraint.min_area:
            violations.append("MIN_AREA")
        return ParcelMetric(
            area, frontage, road_frontage, depth, compactness, aspect_ratio,
            not violations, tuple(violations),
        )

    @staticmethod
    def _road_frontage(geometry: QgsGeometry, roads: list[QgsGeometry]) -> float:
        road_zone = None
        for road in roads:
            buffered = road.buffer(0.25, 4)
            if not buffered or buffered.isEmpty():
                continue
            road_zone = buffered if road_zone is None else road_zone.combine(buffered)
        if road_zone is None:
            return 0.0
        polygons = geometry.asMultiPolygon() if geometry.isMultipart() else [geometry.asPolygon()]
        rings = [
            [QgsPointXY(point) for point in ring]
            for polygon in polygons
            for ring in polygon
            if ring
        ]
        if not rings:
            return 0.0
        boundary = QgsGeometry.fromMultiPolylineXY(rings)
        contact = boundary.intersection(road_zone)
        return max(0.0, float(contact.length())) if contact and not contact.isEmpty() else 0.0

    @staticmethod
    def _distance(first: QgsPointXY, second: QgsPointXY) -> float:
        return math.hypot(second.x() - first.x(), second.y() - first.y())
