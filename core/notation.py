"""MPYY notation rendering derived from the verified UIP SLD properties.

The source SLD uses ``dairemi``, ``yazi``, ``taksyazi``, ``kaksyazi``,
``yazi_buyukluk`` and ``yaricap``.  They are retained as fields and rendered
with native QGIS markers/labels, so no external SVG or font package is needed.
"""
from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsRendererCategory,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtGui import QColor


def apply_mpyy_notation(layer):
    if layer is None or layer.fields().indexFromName('sembol_tipi') < 0:
        return False
    categories = []
    for value, label, color in (
        ('YAPILASMA', 'Yapılaşma notasyonu', '#6b4e71'),
        ('YERLESIM', 'Yerleşim notasyonu', '#2c5c8a'),
        ('DIGER', 'Diğer notasyon', '#555555'),
    ):
        symbol = QgsMarkerSymbol.createSimple(
            {'name': 'circle', 'color': color, 'outline_color': '#222222', 'size': '2.2'}
        )
        categories.append(QgsRendererCategory(value, symbol, label))
    layer.setRenderer(QgsCategorizedSymbolRenderer('sembol_tipi', categories))
    settings = QgsPalLayerSettings()
    settings.isExpression = True
    settings.fieldName = (
        "coalesce(nullif(\"etiket_metni\",''),nullif(\"yazi\",''),"
        "concat_ws(' ',\"taksyazi\",\"kaksyazi\"))"
    )
    text_format = QgsTextFormat()
    text_format.setSize(8)
    settings.setFormat(text_format)
    placement_enum = getattr(Qgis, 'LabelPlacement', None) or getattr(QgsPalLayerSettings, 'Placement', None)
    if placement_enum is not None and hasattr(placement_enum, 'OverPoint'):
        settings.placement = placement_enum.OverPoint
    layer.setLabelsEnabled(True)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setCustomProperty('mpyy/notation_renderer', 'MPYY SLD: dairemi + yazi/taksyazi/kaksyazi')
    layer.triggerRepaint()
    return True
