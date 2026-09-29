"""Ek-1e notation on points read from a drawing: each circle sits where it was drawn.

Netcad draws the nizam / kat circle and the TAKS / KAKS circle as separate
objects (Tire UİP: 1368 and 739, one holding both), so a point layer must put
a circle on its own point, not half a pair-width to the side as a plan area's
two circles are laid out. Measured by rendering the labels.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMapRendererCustomPainterJob,
    QgsMapSettings,
    QgsPointXY,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType, QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage, QPainter  # noqa: E402

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from planx_mpyy_studio.core.mpyy_workspace import (  # noqa: E402
    BUILDING_FIELDS,
    NOTATION_CIRCLE_M,
    apply_building_notation,
    apply_road_width_notation,
)

X0, Y0 = 500000.0, 4200000.0
DPI = 96.0
SCALE = 1000.0
PIXELS = 600


def point_layer(fields, values):
    types = {"KatAdedi": QMetaType.Type.Int, "YapiDuzeni": QMetaType.Type.QString,
             "TaksTip": QMetaType.Type.QString, "EmsalKaksTip": QMetaType.Type.QString,
             "YapiYuksekligiTip": QMetaType.Type.QString}
    layer = QgsVectorLayer("Point?crs=EPSG:5254", "notation", "memory")
    layer.dataProvider().addAttributes([QgsField(n, types.get(n, QMetaType.Type.Double)) for n in fields])
    layer.updateFields()
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X0, Y0)))
    for name, value in values.items():
        feature[name] = value
    layer.dataProvider().addFeatures([feature])
    return layer


def ink_box_m(layer):
    """Bounding box of everything drawn, in metres relative to the point (x right, y up)."""
    settings = QgsMapSettings()
    settings.setLayers([layer])
    settings.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:5254"))
    settings.setOutputDpi(DPI)
    settings.setOutputSize(QSize(PIXELS, PIXELS))
    half = PIXELS / DPI * 0.0254 * SCALE / 2
    settings.setExtent(QgsRectangle(X0 - half, Y0 - half, X0 + half, Y0 + half))
    image = QImage(PIXELS, PIXELS, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    job = QgsMapRendererCustomPainterJob(settings, painter)
    job.renderSynchronously()
    painter.end()
    xs, ys = [], []
    for y in range(PIXELS):
        for x in range(0, PIXELS):
            if QColor(image.pixel(x, y)).lightness() < 128:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    metre = 2 * half / PIXELS
    return ((min(xs) - PIXELS / 2) * metre, (max(xs) - PIXELS / 2) * metre,
            (PIXELS / 2 - max(ys)) * metre, (PIXELS / 2 - min(ys)) * metre)


class NotationOnPoints(unittest.TestCase):
    def test_a_single_circle_sits_on_its_point(self):
        for values in ({"YapiDuzeni": "Ayrik", "KatAdedi": 4, "OnBahceMesafesi": 5.0, "YanBahceMesafesi": 3.0},
                       {"Taks": 0.30, "TaksTip": "Deger", "EmsalKaks": 1.20, "EmsalKaksTip": "Deger"}):
            with self.subTest(values=sorted(values)):
                layer = point_layer(BUILDING_FIELDS, values)
                self.assertGreater(apply_building_notation(layer), 0)
                left, right, bottom, top = ink_box_m(layer)
                self.assertAlmostEqual((left + right) / 2, 0.0, delta=1.5)   # centred on the point ...
                self.assertLess(right - left, NOTATION_CIRCLE_M + 3)          # ... and a single circle

    def test_a_point_holding_both_keeps_them_side_by_side(self):
        layer = point_layer(BUILDING_FIELDS, {"YapiDuzeni": "Ayrik", "KatAdedi": 4, "Taks": 0.30, "TaksTip": "Deger",
                                              "EmsalKaks": 1.20, "EmsalKaksTip": "Deger"})
        apply_building_notation(layer)
        left, right, _bottom, _top = ink_box_m(layer)
        self.assertGreater(right - left, 2 * NOTATION_CIRCLE_M)
        self.assertAlmostEqual((left + right) / 2, 0.0, delta=1.5)

    def test_a_road_width_point_draws_its_circle(self):
        layer = point_layer(("YolGenisligi",), {"YolGenisligi": 15.0})
        self.assertTrue(apply_road_width_notation(layer))
        left, right, bottom, top = ink_box_m(layer)
        self.assertAlmostEqual((left + right) / 2, 0.0, delta=1.5)
        self.assertGreater(right - left, 15.0 * 2.5 * 0.5)       # the circle, not a dot


class CepheWidthFromTheField(unittest.TestCase):
    def test_onerilen_cephe_is_drawn_at_its_cizgi_kalinligi(self):
        """The SLD draws AdaKenari cephe at CizgiKalinligi; QGIS's SLD reader dropped it."""
        from qgis.core import QgsExpressionContext, QgsSymbolLayer

        from planx_mpyy_studio.core.mpyy_workspace import apply_eplan_symbology

        layer = QgsVectorLayer("LineString?crs=EPSG:5254&field=AdaKenariCizgiTip:string&field=CizgiKalinligi:double",
                               "ada", "memory")
        self.assertTrue(apply_eplan_symbology(layer, "UIP", "AdaKenari"))
        rules = {rule.label(): rule for rule in layer.renderer().rootRule().children()}
        onerilen = rules["ONERILEN"].symbol().clone()
        line = onerilen.symbolLayer(0)
        expression = line.dataDefinedProperties().property(QgsSymbolLayer.Property.StrokeWidth).expressionString()
        self.assertIn('"CizgiKalinligi"', expression)
        feature = QgsFeature(layer.fields())
        context = QgsExpressionContext()
        context.setFields(layer.fields())
        for value, expected in ((2.5, 2.5), (None, line.width())):
            feature["CizgiKalinligi"] = value
            context.setFeature(feature)
            width, _ok = line.dataDefinedProperties().valueAsDouble(
                QgsSymbolLayer.Property.StrokeWidth, context, -1.0)
            self.assertAlmostEqual(width, expected, msg=str(value))


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
