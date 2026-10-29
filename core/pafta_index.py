"""PlanX MPYY Standard Sheet Indexing & Grid Generation Engine (BÖHYY / MPYY).

Generates statutory topographic cadastral map sheet grids (Standart Pafta İndeksi):
- Computes coordinate-rounded regular sheet boundaries covering plan extents.
- Standard Turkish planning scales:
  - 1/1.000: 500m x 500m (Uygulama İmar Planı)
  - 1/2.000: 1000m x 1000m
  - 1/5.000: 2500m x 2000m (Nazım İmar Planı)
- Computes per-sheet zoning statistics:
  - Sheet number / code (Pafta No)
  - Covered plan area (m² and ha)
  - Intersecting zoning block count (Ada Sayısı)
  - Public infrastructure & amenity area inside the sheet
"""

from dataclasses import dataclass, field
import math
from typing import Any
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsSpatialIndex,
)

from .attr_utils import reindex_features_with_map


@dataclass
class PaftaSheetItem:
    pafta_no: str
    satir: int
    sutun: int
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    pafta_alani_m2: float
    kesisen_plan_m2: float
    kesisen_ozellik_adedi: int
    geometri: QgsGeometry


@dataclass
class PaftaGridSummary:
    toplam_pafta_sayisi: int = 0
    kapsanan_plan_alani_m2: float = 0.0
    satir_sayisi: int = 0
    sutun_sayisi: int = 0
    hucre_genisligi_m: float = 500.0
    hucre_yuksekligi_m: float = 500.0
    olcek: str = "1/1.000"


class PaftaGridEngine:
    """Standard Turkish topographic-cadastral sheet grid generator."""

    SCALE_DIMENSIONS: dict[str, tuple[float, float]] = {
        "1/1.000": (500.0, 500.0),
        "1/2.000": (1000.0, 1000.0),
        "1/5.000": (2500.0, 2000.0),
    }

    @classmethod
    def generate_sheet_grid(
        cls,
        extent: QgsRectangle,
        scale_name: str = "1/1.000",
        custom_width_m: float | None = None,
        custom_height_m: float | None = None,
        plan_features: list[QgsFeature] | None = None,
        prefix: str = "P",
        feedback: Any = None,
    ) -> tuple[list[PaftaSheetItem], PaftaGridSummary]:
        """Generates coordinate-rounded standard map sheet polygons."""
        sheets: list[PaftaSheetItem] = []

        std_w, std_h = cls.SCALE_DIMENSIONS.get(scale_name, (500.0, 500.0))
        width_m = custom_width_m if (custom_width_m and custom_width_m > 0) else std_w
        height_m = custom_height_m if (custom_height_m and custom_height_m > 0) else std_h

        if (
            extent is None
            or extent.isEmpty()
            or not all(
                math.isfinite(val)
                for val in (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum())
            )
        ):
            return [], PaftaGridSummary(
                toplam_pafta_sayisi=0,
                satir_sayisi=0,
                sutun_sayisi=0,
                hucre_genisligi_m=width_m,
                hucre_yuksekligi_m=height_m,
                olcek=scale_name,
            )

        # Snap extent outwards to nearest multiples of width_m and height_m
        snap_x_min = math.floor(extent.xMinimum() / width_m) * width_m
        snap_y_min = math.floor(extent.yMinimum() / height_m) * height_m
        snap_x_max = math.ceil(extent.xMaximum() / width_m) * width_m
        snap_y_max = math.ceil(extent.yMaximum() / height_m) * height_m

        cols = max(1, int(round((snap_x_max - snap_x_min) / width_m)))
        rows = max(1, int(round((snap_y_max - snap_y_min) / height_m)))

        summary = PaftaGridSummary(
            toplam_pafta_sayisi=0,
            satir_sayisi=rows,
            sutun_sayisi=cols,
            hucre_genisligi_m=width_m,
            hucre_yuksekligi_m=height_m,
            olcek=scale_name,
        )

        # Build spatial index for plan features if provided (reindexed safely for memory/merged features)
        plan_index: QgsSpatialIndex | None = None
        plan_map: dict[int, QgsFeature] = {}
        if plan_features:
            plan_index = QgsSpatialIndex()
            indexed_plans, _ = reindex_features_with_map(
                pf for pf in plan_features if pf.hasGeometry() and not pf.geometry().isEmpty()
            )
            for pf in indexed_plans:
                plan_index.addFeature(pf)
                plan_map[pf.id()] = pf

        total_covered_m2 = 0.0
        sheet_count = 0

        # Generate from North to South (top row to bottom row) and West to East
        for r in range(rows):
            if feedback and feedback.isCanceled():
                break
            # Y goes from snap_y_max downwards
            y_top = snap_y_max - r * height_m
            y_bot = y_top - height_m

            for c in range(cols):
                x_left = snap_x_min + c * width_m
                x_right = x_left + width_m

                rect = QgsRectangle(x_left, y_bot, x_right, y_top)
                sheet_geom = QgsGeometry.fromRect(rect)
                sheet_area = rect.area()

                kesisen_plan_m2 = 0.0
                kesisen_sayisi = 0

                # If plan features provided, calculate intersection metrics
                if plan_index is not None:
                    candidate_ids = plan_index.intersects(rect)
                    if not candidate_ids:
                        # Empty pafta outside plan area: skip if user only wants covering paftas
                        continue

                    clipped_parts: list[QgsGeometry] = []
                    for pid in candidate_ids:
                        pf = plan_map.get(pid)
                        if pf is None:
                            continue
                        pg = pf.geometry()
                        if pg and sheet_geom.intersects(pg):
                            inter = sheet_geom.intersection(pg)
                            if inter and not inter.isEmpty() and inter.area() > 0:
                                clipped_parts.append(inter)
                                kesisen_sayisi += 1

                    if clipped_parts:
                        unioned = QgsGeometry.unaryUnion(clipped_parts) if len(clipped_parts) > 1 else clipped_parts[0]
                        raw_area = unioned.area() if (unioned and not unioned.isEmpty()) else sum(g.area() for g in clipped_parts)
                        kesisen_plan_m2 = min(sheet_area, raw_area)

                    if kesisen_sayisi == 0 or kesisen_plan_m2 < 1.0:
                        continue  # Skip marginal touches

                sheet_count += 1
                pafta_code = f"{prefix}-{sheet_count:02d}"

                sheets.append(
                    PaftaSheetItem(
                        pafta_no=pafta_code,
                        satir=r + 1,
                        sutun=c + 1,
                        min_x=x_left,
                        min_y=y_bot,
                        max_x=x_right,
                        max_y=y_top,
                        pafta_alani_m2=round(sheet_area, 2),
                        kesisen_plan_m2=round(kesisen_plan_m2, 2),
                        kesisen_ozellik_adedi=kesisen_sayisi,
                        geometri=sheet_geom,
                    )
                )
                total_covered_m2 += kesisen_plan_m2

        summary.toplam_pafta_sayisi = len(sheets)
        summary.kapsanan_plan_alani_m2 = round(total_covered_m2, 2)
        return sheets, summary
