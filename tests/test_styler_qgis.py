"""Font notations and the MpyyUipDb drawing template applied to a layer."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import (
    QgsApplication,
    QgsFontMarkerSymbolLayer,
    QgsMarkerSymbol,
    QgsVectorLayer,
)
from planx_mpyy_studio.core.fonts import create_font_marker_symbol, register_mpyy_fonts
from planx_mpyy_studio.core.local_uip_workspace import template as uip_template
from planx_mpyy_studio.core.project_binding import apply_layer_style_and_form

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


class StylerTests(unittest.TestCase):
    def setUp(self):
        register_mpyy_fonts()

    def test_font_marker_glyph_generation(self):
        """Kriter 5: E-Plan TTF font glifleri kullanılarak nokta notasyon sembolleri üretilir."""
        sym = create_font_marker_symbol("NIP_10_1", "0x0055", size=14.0)
        self.assertIsInstance(sym, QgsMarkerSymbol)
        sym_layer = sym.symbolLayer(0)
        self.assertIsInstance(sym_layer, QgsFontMarkerSymbolLayer)
        self.assertEqual(sym_layer.character(), chr(0x0055))

    def test_uip_template_form_and_symbology(self):
        """Kriter 6: Yerel UİP katmanına MpyyUipDb şablon formu ve sembolojisi uygulanır."""
        table = next(t for t in uip_template()["tables"] if t["table"] == "uip-alanlar")
        field_strs = "&".join(f"field={f['name']}:string" for f in table["fields"])
        layer = QgsVectorLayer(f"Polygon?crs=epsg:4326&{field_strs}", "uip-alanlar", "memory")
        self.assertTrue(layer.isValid())

        apply_layer_style_and_form(layer)
        self.assertEqual(layer.customProperty("mpyy/form"), 'MpyyUipDb çizim şablonu: uip-alanlar')
        config = layer.editFormConfig()
        self.assertEqual(config.layout(), 1)  # TabLayout
        self.assertGreaterEqual(len(config.invisibleRootContainer().children()), 3)


if __name__ == "__main__":
    unittest.main()
