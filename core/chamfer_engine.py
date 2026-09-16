"""PlanX MPYY Parcel and Block Corner Chamfer (Pah Kırımı) Engine.

Implements statutory corner truncation requirements of Planlı Alanlar İmar Yönetmeliği (PAİY):
- Madde 20: "Köşe başı parsellerde köşe pahı: Yollara cephesi olan parsellerin köşelerinde,
  kavşaklarda görüş mesafesini ve dönüş kolaylığını sağlamak amacıyla köşe pahı yapılması zorunludur.
  Genişliği 10.00 metreye kadar olan yolların kesiştiği köşelerde en az 3.00 metre,
  10.00 metreden daha geniş yolların kesiştiği köşelerde en az 4.50 metre köşe pahı kırılır.
  Köşe pahı kırılan kesimler yol alanı olarak kabul edilir ve DOP veya terk hesabına dâhil edilir."
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import math
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
)


@dataclass
class ChamferResult:
    geometri: QgsGeometry
    kesilen_alan_m2: float
    pah_adedi: int
    orijinal_alan_m2: float
    yeni_alan_m2: float


class ChamferEngine:
    """Rigorous geometric engine for corner chamfering under PAİY Madde 20."""

    @classmethod
    def chamfer_ring(
        cls,
        ring: list[QgsPointXY],
        parent_geom: QgsGeometry,
        chamfer_dist: float = 3.0,
        min_angle_deg: float = 60.0,
        max_angle_deg: float = 120.0,
    ) -> tuple[list[QgsPointXY], int]:
        """Truncate convex corners in a single closed polygon ring."""
        if len(ring) < 4:  # At least triangle + closing vertex
            return ring, 0

        # Unique vertices (exclude closing vertex if identical to first)
        pts = ring[:-1] if ring[0] == ring[-1] else list(ring)
        n = len(pts)
        if n < 3:
            return ring, 0

        new_pts: list[QgsPointXY] = []
        chamfer_count = 0

        for i in range(n):
            v_curr = pts[i]
            v_prev = pts[(i - 1) % n]
            v_next = pts[(i + 1) % n]

            ax, ay = v_prev.x() - v_curr.x(), v_prev.y() - v_curr.y()
            bx, by = v_next.x() - v_curr.x(), v_next.y() - v_curr.y()

            la = math.hypot(ax, ay)
            lb = math.hypot(bx, by)

            # Check if adjacent edges are long enough to chamfer without collapsing
            if la < (chamfer_dist * 1.15) or lb < (chamfer_dist * 1.15):
                new_pts.append(v_curr)
                continue

            # Calculate corner angle
            dot = (ax * bx + ay * by) / (la * lb)
            dot = max(-1.0, min(1.0, dot))
            angle_rad = math.acos(dot)
            angle_deg = math.degrees(angle_rad)

            if not (min_angle_deg <= angle_deg <= max_angle_deg):
                new_pts.append(v_curr)
                continue

            # Offset points along incoming and outgoing edges
            p1 = QgsPointXY(
                v_curr.x() + (chamfer_dist / la) * ax,
                v_curr.y() + (chamfer_dist / la) * ay,
            )
            p2 = QgsPointXY(
                v_curr.x() + (chamfer_dist / lb) * bx,
                v_curr.y() + (chamfer_dist / lb) * by,
            )

            # Midpoint test: must be INSIDE parent polygon to ensure corner is convex
            mid = QgsPointXY((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
            mid_geom = QgsGeometry.fromPointXY(mid)

            if parent_geom.contains(mid_geom) or parent_geom.intersects(mid_geom):
                # Valid convex corner to chamfer
                new_pts.append(p1)
                new_pts.append(p2)
                chamfer_count += 1
            else:
                # Reflex / concave interior corner, preserve
                new_pts.append(v_curr)

        # Close the ring
        if new_pts:
            new_pts.append(new_pts[0])

        return new_pts, chamfer_count

    @classmethod
    def apply_chamfer(
        cls,
        geometry: QgsGeometry,
        chamfer_dist: float = 3.0,
        min_angle_deg: float = 60.0,
        max_angle_deg: float = 120.0,
    ) -> ChamferResult:
        """Apply corner chamfers to a Polygon or MultiPolygon geometry."""
        if not geometry or geometry.isEmpty():
            return ChamferResult(
                geometri=QgsGeometry(),
                kesilen_alan_m2=0.0,
                pah_adedi=0,
                orijinal_alan_m2=0.0,
                yeni_alan_m2=0.0,
            )

        orig_area = round(geometry.area(), 2)
        total_chamfers = 0

        if geometry.isMultipart():
            multi_poly = geometry.asMultiPolygon()
            new_multi_poly = []
            for poly in multi_poly:
                new_poly = []
                for idx, ring in enumerate(poly):
                    if idx == 0:  # Only chamfer exterior ring
                        c_ring, count = cls.chamfer_ring(
                            ring, geometry, chamfer_dist, min_angle_deg, max_angle_deg
                        )
                        new_poly.append(c_ring)
                        total_chamfers += count
                    else:
                        new_poly.append(ring)
                new_multi_poly.append(new_poly)
            new_geom = QgsGeometry.fromMultiPolygonXY(new_multi_poly)
        else:
            poly = geometry.asPolygon()
            new_poly = []
            for idx, ring in enumerate(poly):
                if idx == 0:  # Only chamfer exterior ring
                    c_ring, count = cls.chamfer_ring(
                        ring, geometry, chamfer_dist, min_angle_deg, max_angle_deg
                    )
                    new_poly.append(c_ring)
                    total_chamfers += count
                else:
                    new_poly.append(ring)
            new_geom = QgsGeometry.fromPolygonXY(new_poly)

        if not new_geom.isGeosValid():
            new_geom = new_geom.makeValid()

        new_area = round(new_geom.area(), 2)
        cut_area = round(max(0.0, orig_area - new_area), 2)

        return ChamferResult(
            geometri=new_geom,
            kesilen_alan_m2=cut_area,
            pah_adedi=total_chamfers,
            orijinal_alan_m2=orig_area,
            yeni_alan_m2=new_area,
        )
