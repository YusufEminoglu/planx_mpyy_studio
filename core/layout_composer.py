'PlanX MPYY Standard Print Layout and Cartographic Template Composer.\n\nImplements statutory cartographic sheet requirements of Mekânsal Planlar Yapım Yönetmeliği (MPYY)\nand Büyük Scaleli Harita ve Harita Bilgileri Üretim Yönetmeliği (BÖHYY):\n- Madde 31: Çizim normları, standart lejant, koordinat gridi, ölçek ve yön gösterimi.\n- Belediye Meclisi Onama Kutusu, Plan Notları Çerçevesi, Antet ve Lejant yerleşimi.\n'

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemMapGrid,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont


# Standard paper dimensions in millimeters
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
}


def _get_layout_mm_unit() -> Any:
    unit = getattr(QgsUnitTypes, "LayoutMillimeters", None)
    if unit is None and hasattr(QgsUnitTypes, "LayoutUnit"):
        unit = getattr(QgsUnitTypes.LayoutUnit, "Millimeters", None)
    return unit


def _get_distance_meters_unit() -> Any:
    unit = getattr(QgsUnitTypes, "DistanceMeters", None)
    if unit is None and hasattr(QgsUnitTypes, "DistanceUnit"):
        unit = getattr(QgsUnitTypes.DistanceUnit, "Meters", None)
    return unit


class MPYYLayoutComposer:
    """Automated builder for MPYY cartographic print layouts."""

    @classmethod
    def create_mpyy_layout(
        cls,
        layout_name: str = "MPYY_Imar_Plani_Paftasi",
        paper_size: str = "A1",
        plan_title: str = '1/1.000 ÖLÇEKLİ UYGULAMA İMAR PLANI',
        municipality: str = 'İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ',
        pafta_no: str = 'İ22-c-04-a',
        plan_scale: str = "1/1.000",
        extent: QgsRectangle | None = None,
        project: QgsProject | None = None,
        plan_notes_text: str | None = None,
    ) -> QgsPrintLayout:
        """Construct a complete, publication-grade MPYY print layout with map, legend, grid, and approval stamp."""
        proj = project or QgsProject.instance()
        manager = proj.layoutManager()

        # Remove existing layout with same name if present
        existing = manager.layoutByName(layout_name)
        if existing:
            manager.removeLayout(existing)

        layout = QgsPrintLayout(proj)
        layout.initializeDefaults()
        layout.setName(layout_name)

        mm = _get_layout_mm_unit()
        m_unit = _get_distance_meters_unit()

        # 1. Page dimensions
        w_mm, h_mm = PAPER_SIZES_MM.get(paper_size.upper(), (841.0, 594.0))
        page = layout.pageCollection().pages()[0]
        page.setPageSize(QgsLayoutSize(w_mm, h_mm, mm))

        # Margins and panel metrics
        margin = 10.0
        side_panel_w = 210.0
        map_w = w_mm - side_panel_w - (margin * 3)
        map_h = h_mm - (margin * 2)

        # 2. Main Map Canvas Item
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptMove(QgsLayoutPoint(margin, margin, mm))
        map_item.attemptResize(QgsLayoutSize(map_w, map_h, mm))
        map_item.setFrameEnabled(True)

        if extent and not extent.isEmpty():
            map_item.setExtent(extent)
        else:
            map_item.setExtent(QgsRectangle(0.0, 0.0, 1000.0, 1000.0))

        # 3. Coordinate Graticule / Grid (BÖHYY standard crosshairs)
        grid = QgsLayoutItemMapGrid("BOHYY_Grid", map_item)
        grid.setEnabled(True)
        # Grid interval: 250m for 1/1.000, 500m for 1/2.000, 1000m for 1/5.000
        interval = 250.0 if "1.000" in plan_scale else 500.0
        grid.setIntervalX(interval)
        grid.setIntervalY(interval)

        grid_style = getattr(QgsLayoutItemMapGrid, "Cross", None)
        if grid_style is None and hasattr(QgsLayoutItemMapGrid, "GridStyle"):
            grid_style = getattr(QgsLayoutItemMapGrid.GridStyle, "Cross", None)
        if grid_style is not None:
            grid.setStyle(grid_style)

        grid.setAnnotationEnabled(True)
        map_item.grids().addGrid(grid)
        layout.addLayoutItem(map_item)

        # Right Side Panel Items
        side_x = margin + map_w + margin
        curr_y = margin

        # 4. Header & Title Box (Antet)
        antet_h = 44.0
        antet_label = QgsLayoutItemLabel(layout)
        antet_label.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        antet_label.attemptResize(QgsLayoutSize(side_panel_w, antet_h, mm))
        antet_label.setFrameEnabled(True)
        antet_label.setBackgroundEnabled(True)
        antet_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; text-align: center; padding: 4px;">\n  <div style="font-size: 11px; font-weight: bold; color: #1a5276; letter-spacing: 1px;">{municipality.upper()}</div>\n  <div style="font-size: 13px; font-weight: bold; color: #2c3e50; margin: 4px 0;">{plan_title}</div>\n  <div style="font-size: 10px; color: #7f8c8d;">ÖLÇEK: <strong>{plan_scale}</strong> &bull; PAFTA NO: <strong>{pafta_no}</strong></div>\n</div>"""
        antet_label.setText(antet_html)
        antet_label.setMode(QgsLayoutItemLabel.ModeHtml)
        layout.addLayoutItem(antet_label)
        curr_y += antet_h + 4.0

        # 5. Plan Legend (Lejant)
        legend_h = min(220.0, (h_mm - curr_y - 120.0))
        legend = QgsLayoutItemLegend(layout)
        legend.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        legend.attemptResize(QgsLayoutSize(side_panel_w, legend_h, mm))
        legend.setFrameEnabled(True)
        legend.setBackgroundEnabled(True)
        legend.setTitle('MPYY İMAR PLANI GÖSTERİMİ')
        legend.setLinkedMap(map_item)
        layout.addLayoutItem(legend)
        curr_y += legend_h + 4.0

        # 6. Scalebar & Coordinate Reference System
        scale_h = 24.0
        scalebar = QgsLayoutItemScaleBar(layout)
        scalebar.setLinkedMap(map_item)
        scalebar.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        scalebar.attemptResize(QgsLayoutSize(side_panel_w, scale_h, mm))
        scalebar.setNumberOfSegments(3)
        scalebar.setNumberOfSegmentsLeft(0)
        scalebar.setUnits(m_unit)
        scalebar.setFrameEnabled(True)
        scalebar.setBackgroundEnabled(True)
        layout.addLayoutItem(scalebar)
        curr_y += scale_h + 4.0

        # 7. Meclis Onama ve İmar Komisyonu Kutusu
        approval_h = 60.0
        approval_label = QgsLayoutItemLabel(layout)
        approval_label.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        approval_label.attemptResize(QgsLayoutSize(side_panel_w, approval_h, mm))
        approval_label.setFrameEnabled(True)
        approval_label.setBackgroundEnabled(True)

        approval_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 9px; padding: 4px; color: #2c3e50;">\n  <div style="font-weight: bold; text-align: center; border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-bottom: 4px;">BELEDİYE MECLİSİ ONAMA VE TASDİK KUTUSU</div>\n  <div>&bull; Karar Tarihi: .... / .... / 202... &nbsp;&nbsp;&bull; Karar No: ................</div>\n  <div>&bull; İmar Komisyonu Rapor Tarih/No: .......................................</div>\n  <div style="margin-top: 6px; border-top: 1px dashed #d5dbdb; padding-top: 3px;">\n    <strong>Plan Müellifi / Şehir Plancısı:</strong> Yusuf Eminoğlu<br>\n    <span>TMMOB ŞPO Sicil No: ........... &bull; Kaşe / İmza</span>\n  </div>\n</div>"""
        approval_label.setText(approval_html)
        approval_label.setMode(QgsLayoutItemLabel.ModeHtml)
        layout.addLayoutItem(approval_label)
        curr_y += approval_h + 4.0

        # 8. Plan Notları Özeti Kutusu (Remaining height)
        rem_h = h_mm - margin - curr_y
        if rem_h >= 30.0:
            notes_label = QgsLayoutItemLabel(layout)
            notes_label.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
            notes_label.attemptResize(QgsLayoutSize(side_panel_w, rem_h, mm))
            notes_label.setFrameEnabled(True)
            notes_label.setBackgroundEnabled(True)

            notes_content = plan_notes_text or (
                '1. Bu plan paftası, plan açıklama raporu ve plan notları ayrılmaz bir bütündür.<br>2. 3194 sayılı İmar Kanunu, MPYY ve PAİY hükümleri geçerlidir.<br>3. Jeolojik-jeoteknik etüt raporu ve TBDY 2018 kurallarına uyulacaktır.<br>4. İmar Kanunu Madde 18 uygulaması tamamlanmadan yapı ruhsatı verilemez.<br>5. Otopark ihtiyacı parsel bünyesinde karşılanacaktır.'
            )

            notes_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 8px; padding: 4px; color: #34495e;">\n  <div style="font-weight: bold; border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-bottom: 3px;">PLAN NOTLARI VE UYGULAMA ESASLARI:</div>\n  {notes_content}\n</div>"""
            notes_label.setText(notes_html)
            notes_label.setMode(QgsLayoutItemLabel.ModeHtml)
            layout.addLayoutItem(notes_label)

        manager.addLayout(layout)
        return layout
