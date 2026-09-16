"""Create a deterministic local gzip copy and native QGIS preview sheets.

Run in QGIS Python: build_style_catalog.py source.xml --output directory.
This tool does not establish redistribution rights or certify compliance.
"""

import argparse
import gzip
import json
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsSingleSymbolRenderer,
    QgsMapSettings,
    QgsRectangle,
    QgsMapRendererSequentialJob,
)
from qgis.PyQt.QtCore import QSize, QRect
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPdfWriter, QFont

from planx_mpyy_studio.core.styler import MPYYStylerEngine


def build(source, output):
    output.mkdir(parents=True, exist_ok=True)
    engine = MPYYStylerEngine(source)
    raw = source.read_bytes()
    compressed = gzip.compress(raw, mtime=0)
    (output / "UIPMPYYSTYLE.xml.gz").write_bytes(compressed)
    inventory = dict(engine.inventory)
    inventory["gzip_bytes"] = len(compressed)
    inventory["redistribution_status"] = "Unverified; local development only"
    (output / "catalog_inventory.json").write_text(
        json.dumps(inventory, indent=2), encoding="utf-8"
    )
    names = sorted(engine._style.symbolNames())
    pdf = QPdfWriter(str(output / "catalog_previews.pdf"))
    pdf.setResolution(96)
    pdf_painter = QPainter(pdf)
    for page, start in enumerate(range(0, len(names), 30)):
        image = QImage(1000, 1080, QImage.Format.Format_ARGB32)
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setFont(QFont("Arial", 8))
        for offset, name in enumerate(names[start : start + 30]):
            x, y = (offset % 5) * 200, (offset // 5) * 180
            symbol = engine._style.symbol(name)
            kind, wkt = {
                0: ("Point", "POINT(22 16)"),
                1: ("LineString", "LINESTRING(4 16,41 16)"),
                2: ("Polygon", "POLYGON((4 4,41 4,41 28,4 28,4 4))"),
            }[int(symbol.type())]
            fields = (
                "&field=refuj_m:double&field=sag_serit_sayisi:integer"
                "&field=kaldirim_m:double&field=yol_genislik_m:double"
            )
            layer = QgsVectorLayer(kind + "?crs=EPSG:5254" + fields, name, "memory")
            feature = QgsFeature(layer.fields())
            feature.setAttributes([2.0, 2, 2.0, 20.0])
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            layer.dataProvider().addFeatures([feature])
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
            settings = QgsMapSettings()
            settings.setLayers([layer])
            settings.setDestinationCrs(layer.crs())
            settings.setOutputSize(QSize(170, 120))
            settings.setExtent(QgsRectangle(0, 0, 45, 32))
            job = QgsMapRendererSequentialJob(settings)
            job.start()
            job.waitForFinished()
            painter.drawImage(x + 15, y + 5, job.renderedImage())
            painter.drawText(QRect(x + 5, y + 130, 190, 48), 0x1000, name)
        painter.end()
        image.save(str(output / f"catalog_{page + 1:02d}.png"))
        if page:
            pdf.newPage()
        ratio = min(pdf.width() / image.width(), pdf.height() / image.height())
        width, height = round(image.width() * ratio), round(image.height() * ratio)
        pdf_painter.drawImage(
            QRect((pdf.width() - width) // 2, 0, width, height), image
        )
    pdf_painter.end()
    print(json.dumps(inventory))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    app = QgsApplication([], False)
    app.initQgis()
    build(args.source, args.output)
