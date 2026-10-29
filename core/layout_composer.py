'PlanX MPYY Standard Print Layout and Cartographic Template Composer.\n\nImplements statutory cartographic sheet requirements of Mekânsal Planlar Yapım Yönetmeliği (MPYY)\nand Büyük Scaleli Harita ve Harita Bilgileri Üretim Yönetmeliği (BÖHYY):\n- Madde 31: Çizim normları, standart lejant, koordinat gridi, ölçek ve yön gösterimi.\n- Belediye Meclisi Onama Kutusu, Plan Notları Çerçevesi, Antet ve Lejant yerleşimi.\n'

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import html as _html
from pathlib import Path
import re
from typing import Any

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemMapGrid,
    QgsLayoutItemPicture,
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

from .attr_utils import upper_tr


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


def _get_label_html_mode() -> Any:
    mode_ns = getattr(QgsLayoutItemLabel, "Mode", QgsLayoutItemLabel)
    return getattr(mode_ns, "ModeHtml", getattr(QgsLayoutItemLabel, "ModeHtml", 1))


def _bohyy_grid_interval(plan_scale: str, map_extent: QgsRectangle) -> float:
    digits = re.sub(r"[^0-9]", "", str(plan_scale or "").split("/")[-1].split(":")[-1])
    denom = int(digits) if digits else 1000
    if denom >= 100000:
        base = 20000.0
    elif denom >= 25000:
        base = 5000.0
    elif denom >= 5000:
        base = 1000.0
    elif denom >= 2000:
        base = 500.0
    else:
        base = 250.0
    max_span = max(map_extent.width(), map_extent.height(), 1.0)
    return max(base, round(max_span / 40.0, 2))


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
            map_ext = QgsRectangle(extent)
        else:
            map_ext = QgsRectangle(0.0, 0.0, 1000.0, 1000.0)
        map_item.setExtent(map_ext)

        # 3. Coordinate Graticule / Grid (BÖHYY standard crosshairs)
        grid = QgsLayoutItemMapGrid("BOHYY_Grid", map_item)
        grid.setEnabled(True)
        interval = _bohyy_grid_interval(plan_scale, map_ext)
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
        html_mode = _get_label_html_mode()

        # 4. Header & Title Box (Antet)
        antet_h = 44.0
        antet_label = QgsLayoutItemLabel(layout)
        antet_label.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        antet_label.attemptResize(QgsLayoutSize(side_panel_w, antet_h, mm))
        antet_label.setFrameEnabled(True)
        antet_label.setBackgroundEnabled(True)
        esc_mun = _html.escape(upper_tr(municipality))
        esc_title = _html.escape(str(plan_title))
        esc_scale = _html.escape(str(plan_scale))
        esc_pafta = _html.escape(str(pafta_no))
        antet_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; text-align: center; padding: 4px;">\n  <div style="font-size: 11px; font-weight: bold; color: #1a5276; letter-spacing: 1px;">{esc_mun}</div>\n  <div style="font-size: 13px; font-weight: bold; color: #2c3e50; margin: 4px 0;">{esc_title}</div>\n  <div style="font-size: 10px; color: #7f8c8d;">ÖLÇEK: <strong>{esc_scale}</strong> &bull; PAFTA NO: <strong>{esc_pafta}</strong></div>\n</div>"""
        antet_label.setText(antet_html)
        antet_label.setMode(html_mode)
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

        # 6. Scalebar & North Arrow (MPYY Md. 31 ölçek ve kuzey yönü)
        scale_h = 24.0
        arrow_w = 24.0
        scalebar = QgsLayoutItemScaleBar(layout)
        scalebar.setLinkedMap(map_item)
        scalebar.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        scalebar.attemptResize(QgsLayoutSize(side_panel_w - arrow_w - 4.0, scale_h, mm))
        scalebar.setNumberOfSegments(3)
        scalebar.setNumberOfSegmentsLeft(0)
        scalebar.setUnits(m_unit)
        scalebar.setFrameEnabled(True)
        scalebar.setBackgroundEnabled(True)
        layout.addLayoutItem(scalebar)

        north_arrow = QgsLayoutItemPicture(layout)
        north_arrow.attemptMove(QgsLayoutPoint(side_x + side_panel_w - arrow_w, curr_y, mm))
        north_arrow.attemptResize(QgsLayoutSize(arrow_w, scale_h, mm))
        for svg_root in QgsApplication.svgPaths():
            candidate = Path(svg_root) / "arrows" / "NorthArrow_01.svg"
            if candidate.exists():
                north_arrow.setPicturePath(str(candidate))
                break
        north_arrow.setLinkedMap(map_item)
        north_arrow.setFrameEnabled(True)
        north_arrow.setBackgroundEnabled(True)
        layout.addLayoutItem(north_arrow)
        curr_y += scale_h + 4.0

        # 7. Meclis Onama ve İmar Komisyonu Kutusu
        approval_h = 60.0
        approval_label = QgsLayoutItemLabel(layout)
        approval_label.attemptMove(QgsLayoutPoint(side_x, curr_y, mm))
        approval_label.attemptResize(QgsLayoutSize(side_panel_w, approval_h, mm))
        approval_label.setFrameEnabled(True)
        approval_label.setBackgroundEnabled(True)

        approval_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 9px; padding: 4px; color: #2c3e50;">\n  <div style="font-weight: bold; text-align: center; border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-bottom: 4px;">BELEDİYE MECLİSİ ONAMA VE TASDİK KUTUSU</div>\n  <div>&bull; Karar Tarihi: .... / .... / 202... &nbsp;&nbsp;&bull; Karar No: ................</div>\n  <div>&bull; İmar Komisyonu Rapor Tarih/No: .......................................</div>\n  <div style="margin-top: 6px; border-top: 1px dashed #d5dbdb; padding-top: 3px;">\n    <strong>Plan Müellifi / Şehir Plancısı:</strong> Geophilo<br>\n    <span>TMMOB ŞPO Sicil No: ........... &bull; Kaşe / İmza</span>\n  </div>\n</div>"""
        approval_label.setText(approval_html)
        approval_label.setMode(html_mode)
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

            if plan_notes_text:
                notes_content = "<br>".join(_html.escape(line) for line in str(plan_notes_text).replace("<br>", "\n").splitlines())
            else:
                notes_content = (
                    '1. Bu plan paftası, plan açıklama raporu ve plan notları ayrılmaz bir bütündür.<br>2. 3194 sayılı İmar Kanunu, MPYY ve PAİY hükümleri geçerlidir.<br>3. Jeolojik-jeoteknik etüt raporu ve TBDY 2018 kurallarına uyulacaktır.<br>4. İmar Kanunu Madde 18 uygulaması tamamlanmadan yapı ruhsatı verilemez.<br>5. Otopark ihtiyacı parsel bünyesinde karşılanacaktır.'
                )

            notes_html = f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 8px; padding: 4px; color: #34495e;">\n  <div style="font-weight: bold; border-bottom: 1px solid #bdc3c7; padding-bottom: 2px; margin-bottom: 3px;">PLAN NOTLARI VE UYGULAMA ESASLARI:</div>\n  {notes_content}\n</div>"""
            notes_label.setText(notes_html)
            notes_label.setMode(html_mode)
            layout.addLayoutItem(notes_label)

        manager.addLayout(layout)
        return layout
