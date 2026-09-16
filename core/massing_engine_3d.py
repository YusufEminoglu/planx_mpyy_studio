"""Procedural PolygonZ building massing generation."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from qgis.core import QgsGeometry, QgsPointXY

from .actions import calculate_setback_envelope


@dataclass
class MassingResult:
    geometry: QgsGeometry
    footprint_area_m2: float
    gross_volume_m3: float
    space_efficiency_ratio: float
    floor_count: int
    wall_top_z: float
    roof_top_z: float
    roof_rise_m: float
    gross_floor_area_m2: float
    floor_area_ratio: float
    floor_elevations_m: tuple[float, ...] = ()
    warning_notes: list[str] = field(default_factory=list)


class ProceduralMassingEngine:
    """Builds a closed multipolygon Z shell from a two-dimensional parcel."""

    @classmethod
    def generate(
        cls,
        parcel_geometry: QgsGeometry,
        setback_m: float = 3.0,
        max_height_m: float = 15.5,
        subbasement_height_m: float = 0.5,
        ground_floor_height_m: float = 4.0,
        typical_floor_height_m: float = 3.0,
        roof_slope_percent: float = 33.0,
        include_roof: bool = True,
        max_roof_rise_m: float = 6.0,
    ) -> MassingResult:
        if not parcel_geometry or parcel_geometry.isEmpty():
            raise ValueError('Boş olmayan bir parsel geometrisi gereklidir.')
        numeric_values = (
            setback_m, max_height_m, subbasement_height_m, ground_floor_height_m,
            typical_floor_height_m, roof_slope_percent, max_roof_rise_m,
        )
        if not all(math.isfinite(float(value)) for value in numeric_values):
            raise ValueError('Yapı kütlesi parametreleri sonlu sayılar olmalıdır.')
        if min(setback_m, max_height_m, subbasement_height_m, max_roof_rise_m) < 0:
            raise ValueError('Çekme mesafesi ve yükseklik değerleri negatif olamaz.')
        if ground_floor_height_m <= 0 or typical_floor_height_m <= 0:
            raise ValueError('Kat yükseklikleri pozitif olmalıdır.')
        if roof_slope_percent < 0 or roof_slope_percent > 100:
            raise ValueError('Çatı eğimi sıfır ile yüz arasında olmalıdır.')

        footprint = calculate_setback_envelope(parcel_geometry, setback_m)
        if not footprint or footprint.isEmpty():
            raise ValueError('Çekme mesafeleri yapılaşabilir taban alanı bırakmıyor.')
        warnings: list[str] = []
        if footprint.isMultipart():
            parts = footprint.asGeometryCollection()
            footprint = max(parts, key=lambda part: part.area())
            warnings.append("MULTIPART_FOOTPRINT_LARGEST_PART_USED")
        if not footprint.isGeosValid():
            repaired = footprint.makeValid()
            if not repaired or repaired.isEmpty():
                raise ValueError('Yapılaşabilir taban alanı onarılamadı.')
            footprint = repaired
            if footprint.isMultipart():
                footprint = max(footprint.asGeometryCollection(), key=lambda part: part.area())
            warnings.append("FOOTPRINT_GEOMETRY_REPAIRED")

        polygons = footprint.asPolygon()
        if not polygons or len(polygons[0]) < 4:
            raise ValueError('Yapılaşabilir taban alanı geçerli bir poligon değildir.')
        ring = [QgsPointXY(point) for point in polygons[0]]
        if len(polygons) > 1:
            warnings.append("FOOTPRINT_HOLES_OMITTED_FROM_3D_SHELL")

        if max_height_m + 1e-9 < ground_floor_height_m:
            typical_count = 0
            floor_count = 1
            wall_height = max_height_m
            warnings.append("GROUND_FLOOR_HEIGHT_CLAMPED_TO_HMAX")
        else:
            typical_count = max(
                0,
                int(math.floor((max_height_m - ground_floor_height_m) / typical_floor_height_m)),
            )
            floor_count = 1 + typical_count
            wall_height = ground_floor_height_m + typical_count * typical_floor_height_m
        wall_top_z = subbasement_height_m + wall_height
        floor_elevations = [subbasement_height_m]
        first_floor_top = subbasement_height_m + min(ground_floor_height_m, wall_height)
        floor_elevations.append(first_floor_top)
        for floor_index in range(1, typical_count + 1):
            floor_elevations.append(first_floor_top + floor_index * typical_floor_height_m)
        floor_elevations[-1] = wall_top_z
        footprint_area = float(footprint.area())
        bounds = footprint.boundingBox()
        half_span = max(0.0, min(bounds.width(), bounds.height()) / 2.0)
        raw_roof_rise = half_span * roof_slope_percent / 100.0 if include_roof else 0.0
        roof_rise = min(raw_roof_rise, max_roof_rise_m)
        if raw_roof_rise > max_roof_rise_m + 1e-9:
            warnings.append("ROOF_RISE_CAPPED")
        roof_top_z = wall_top_z + roof_rise

        surfaces: list[list[tuple[float, float, float]]] = []
        surfaces.append([(point.x(), point.y(), 0.0) for point in reversed(ring)])
        for index in range(len(ring) - 1):
            first, second = ring[index], ring[index + 1]
            surfaces.append([
                (first.x(), first.y(), 0.0),
                (second.x(), second.y(), 0.0),
                (second.x(), second.y(), wall_top_z),
                (first.x(), first.y(), wall_top_z),
                (first.x(), first.y(), 0.0),
            ])
        for elevation in floor_elevations:
            if elevation + 1e-7 < wall_top_z:
                surfaces.append([(point.x(), point.y(), elevation) for point in ring])

        if include_roof and roof_rise > 0:
            center = footprint.pointOnSurface().asPoint()
            for index in range(len(ring) - 1):
                first, second = ring[index], ring[index + 1]
                surfaces.append([
                    (first.x(), first.y(), wall_top_z),
                    (second.x(), second.y(), wall_top_z),
                    (center.x(), center.y(), roof_top_z),
                    (first.x(), first.y(), wall_top_z),
                ])
        else:
            surfaces.append([(point.x(), point.y(), wall_top_z) for point in ring])

        shell = QgsGeometry.fromWkt(cls._multipolygon_z_wkt(surfaces))
        if not shell or shell.isEmpty():
            raise ValueError('QGIS PolygonZ yapı kütlesi kabuğunu oluşturamadı.')
        volume = footprint_area * wall_top_z
        if include_roof:
            volume += footprint_area * roof_rise / 3.0
        parcel_area = max(float(parcel_geometry.area()), 1e-9)
        gross_floor_area = footprint_area * floor_count
        return MassingResult(
            geometry=shell,
            footprint_area_m2=footprint_area,
            gross_volume_m3=volume,
            space_efficiency_ratio=volume / parcel_area,
            floor_count=floor_count,
            wall_top_z=wall_top_z,
            roof_top_z=roof_top_z,
            roof_rise_m=roof_rise,
            gross_floor_area_m2=gross_floor_area,
            floor_area_ratio=gross_floor_area / parcel_area,
            floor_elevations_m=tuple(floor_elevations),
            warning_notes=warnings,
        )

    @staticmethod
    def _multipolygon_z_wkt(surfaces: list[list[tuple[float, float, float]]]) -> str:
        polygons = []
        for surface in surfaces:
            coords = ", ".join(f"{x:.9f} {y:.9f} {z:.9f}" for x, y, z in surface)
            polygons.append(f"(({coords}))")
        return "MULTIPOLYGON Z (" + ", ".join(polygons) + ")"
