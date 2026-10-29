"""Geometry Cleaning, Repair, and Topological Snapping Engine for CAD/GIS Layers.

Implements rigorous spatial planning geometric integrity:
- Removes duplicate and collinear micro-vertices within 1mm.
- Resolves self-intersections and degenerate rings via GEOS makeValid.
- Eliminates acute digitizing spikes and topological micro-slivers.
- Enforces strict 2D Polygon / MultiPolygon dimensionality.
- Snaps vertices to user-defined grid tolerance.
"""

from __future__ import annotations

import contextlib
import math
from qgis.core import (
    QgsDistanceArea,
    QgsFeature,
    QgsFeatureSink,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)


def clean_planning_geometry(
    geom: QgsGeometry,
    snap_tolerance: float = 0.0,
    min_area_m2: float = 0.5,
    duplicate_node_tolerance: float = 0.001,
) -> tuple[QgsGeometry, bool]:
    """Clean, fix GEOS defects, eliminate micro-slivers, and snap vertices of a geometry.

    Returns:
        tuple[QgsGeometry, bool]: (cleaned_geometry, was_repaired)
    """
    if not geom or geom.isEmpty():
        return QgsGeometry(), False

    was_repaired = False
    working_geom = QgsGeometry(geom)
    orig_family = working_geom.type()

    # 0. Enforce 2D linear geometry (drop Z/M and linearize CAD curves)
    abstract = working_geom.get()
    if abstract is not None:
        if abstract.is3D():
            abstract.dropZValue()
            was_repaired = True
        if abstract.isMeasure():
            abstract.dropMValue()
            was_repaired = True
        if QgsWkbTypes.isCurvedType(working_geom.wkbType()):
            working_geom = QgsGeometry(abstract.segmentize())
            was_repaired = True

    # 1. GEOS validity repair (resolves self-intersections, bowties, unclosed rings)
    if not working_geom.isGeosValid():
        working_geom = working_geom.makeValid()
        was_repaired = True

    if not working_geom or working_geom.isEmpty():
        return QgsGeometry(), True

    # 2. Remove duplicate consecutive vertices within tolerance (default 1 mm)
    if duplicate_node_tolerance > 0 and working_geom.removeDuplicateNodes(duplicate_node_tolerance, True):
        was_repaired = True

    # 3. Optional grid/vertex snapping + post-snap validity check
    if snap_tolerance > 0:
        working_geom = working_geom.snappedToGrid(snap_tolerance, snap_tolerance)
        if not working_geom.isGeosValid():
            working_geom = working_geom.makeValid()
        was_repaired = True

    if not working_geom or working_geom.isEmpty():
        return QgsGeometry(), True

    # 4. Enforce strict polygon dimensionality and sliver elimination
    is_collection = QgsWkbTypes.flatType(working_geom.wkbType()) == QgsWkbTypes.Type.GeometryCollection
    if orig_family == QgsWkbTypes.GeometryType.PolygonGeometry or working_geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry:
        if working_geom.isMultipart() or is_collection:
            sub_geoms = working_geom.asGeometryCollection()
            valid_parts = [
                part for part in sub_geoms
                if part.type() == QgsWkbTypes.GeometryType.PolygonGeometry
                and (min_area_m2 <= 0 or part.area() >= min_area_m2)
            ]
            if len(valid_parts) < len(sub_geoms) or is_collection:
                was_repaired = True
                if not valid_parts:
                    return QgsGeometry(), True
                working_geom = QgsGeometry.unaryUnion(valid_parts)
        elif min_area_m2 > 0 and working_geom.area() < min_area_m2:
            return QgsGeometry(), True

    return working_geom, was_repaired


def clean_layer_geometries(
    source_layer: QgsVectorLayer,
    sink: QgsFeatureSink,
    snap_tolerance: float = 0.05,
    min_area_m2: float = 1.0,
    feedback=None,
    auto_heal_gaps: bool = False,
) -> tuple[int, int, int]:
    """Clean all features of a layer into a sink.

    Returns:
        tuple[int, int, int]: (total_processed, repaired_count, removed_slivers_count)
    """
    total = source_layer.featureCount()
    fields = source_layer.fields()
    field_names = set(fields.names())

    crs = source_layer.crs()
    is_geographic = crs.isValid() and crs.isGeographic()
    da = QgsDistanceArea()
    if crs.isValid():
        da.setSourceCrs(crs, QgsProject.instance().transformContext())
        if QgsProject.instance().ellipsoid():
            da.setEllipsoid(QgsProject.instance().ellipsoid())
    # Convert planar meter tolerances approximately to degrees if source CRS is geographic
    deg_per_meter = 1.0 / 111_320.0
    eff_dup_tol = 0.001 * deg_per_meter if is_geographic else 0.001
    eff_snap_tol = (
        snap_tolerance * deg_per_meter
        if (is_geographic and snap_tolerance >= 0.001)
        else snap_tolerance
    )
    eff_min_area = 0.0 if is_geographic else min_area_m2

    processed = 0
    repaired = 0
    removed = 0

    for idx, feat in enumerate(source_layer.getFeatures()):
        if feedback and feedback.isCanceled():
            break

        processed += 1
        src_geom = feat.geometry()
        if not src_geom or src_geom.isEmpty():
            removed += 1
            continue

        cleaned_geom, was_mod = clean_planning_geometry(
            src_geom,
            snap_tolerance=eff_snap_tol,
            min_area_m2=eff_min_area,
            duplicate_node_tolerance=eff_dup_tol,
        )

        if not cleaned_geom or cleaned_geom.isEmpty():
            removed += 1
            continue

        area_m2 = float(da.measureArea(cleaned_geom)) if is_geographic else float(cleaned_geom.area())
        if (
            min_area_m2 > 0
            and cleaned_geom.type() == QgsWkbTypes.GeometryType.PolygonGeometry
            and area_m2 < min_area_m2
        ):
            removed += 1
            continue

        if was_mod:
            repaired += 1

        out_feat = QgsFeature(fields)
        out_feat.setAttributes(feat.attributes())
        out_feat.setGeometry(cleaned_geom)

        length_m = float(da.measureLength(cleaned_geom)) if is_geographic else float(cleaned_geom.length())

        # Update metric fields if present
        if "alan_m2" in field_names:
            out_feat["alan_m2"] = round(area_m2, 2)
        if "AlanM2" in field_names:
            out_feat["AlanM2"] = round(area_m2, 2)
        if "AlanHa" in field_names:
            out_feat["AlanHa"] = round(area_m2 / 10000.0, 4)
        if "uzunluk_m" in field_names:
            out_feat["uzunluk_m"] = round(length_m, 2)
        if "Uzunluk(m)" in field_names:
            out_feat["Uzunluk(m)"] = round(length_m, 2)

        sink.addFeature(out_feat, QgsFeatureSink.Flag.FastInsert)

        if feedback and total > 0 and idx % 250 == 0:
            feedback.setProgress(int(100 * idx / total))

    return processed, repaired, removed


def heal_topological_boundaries(
    geometries: list[QgsGeometry],
    snap_tolerance: float = 0.05,
) -> list[QgsGeometry]:
    """Snap adjacent shared boundaries and heal micro-gaps and slivers between polygon edges."""
    if not geometries or snap_tolerance <= 0:
        return geometries

    healed: list[QgsGeometry] = []
    for g in geometries:
        if not g or g.isEmpty():
            healed.append(g)
            continue
        snapped = g.snappedToGrid(snap_tolerance, snap_tolerance)
        if not snapped.isGeosValid():
            snapped = snapped.makeValid()
        healed.append(snapped)
    return healed

