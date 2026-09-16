"""PlanGML notation rendering derived from the verified UIP SLD properties.

The source SLD uses ``dairemi``, ``yazi``, ``taksyazi``, ``kaksyazi``,
``yazi_buyukluk`` and ``yaricap``.  They are retained as fields and rendered
with native QGIS markers/labels, so no external SVG or font package is needed.
"""
from qgis.core import QgsCategorizedSymbolRenderer, QgsMarkerSymbol, QgsRendererCategory, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling
from qgis.PyQt.QtGui import QColor

def apply_plan_gml_notation(layer):
    if layer is None or layer.fields().indexFromName('sembol_tipi') < 0: return False
    categories=[]
    for value, label, color in (('YAPILASMA','Yapılaşma notasyonu','#6b4e71'),('YERLESIM','Yerleşim notasyonu','#2c5c8a'),('DIGER','Diğer notasyon','#555555')):
        symbol=QgsMarkerSymbol.createSimple({'name':'circle','color':color,'outline_color':'#222222','size':'2.2'})
        categories.append(QgsRendererCategory(value,symbol,label))
    layer.setRenderer(QgsCategorizedSymbolRenderer('sembol_tipi',categories))
    settings=QgsPalLayerSettings(); settings.isExpression=True
    settings.fieldName="coalesce(nullif(\"etiket_metni\",''),nullif(\"yazi\",''),concat_ws(' ',\"taksyazi\",\"kaksyazi\"))"
    settings.size=8
    # QGIS 3.44 exposes two different enum families with similar names:
    # LabelPlacement is required by ``placement``; OverPoint on the class is
    # the predefined-point-position enum and raises TypeError.
    placement_enum = getattr(QgsPalLayerSettings, 'LabelPlacement', None)
    if placement_enum is not None and hasattr(placement_enum, 'OverPoint'):
        settings.placement = placement_enum.OverPoint
    layer.setLabelsEnabled(True); layer.setLabeling(QgsVectorLayerSimpleLabeling(settings)); layer.setCustomProperty('mpyy/notation_renderer','PlanGML SLD: dairemi + yazi/taksyazi/kaksyazi')
    layer.triggerRepaint(); return True
