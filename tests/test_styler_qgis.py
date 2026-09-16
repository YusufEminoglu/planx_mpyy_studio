"""Rigorous QGIS tests for all 4 plan level symbology profiles and font notations."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import (
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsFontMarkerSymbolLayer,
    QgsMarkerSymbol,
    QgsVectorLayer,
)
from planx_mpyy_studio.core.cdp_styler import CDPStylerEngine
from planx_mpyy_studio.core.fonts import create_font_marker_symbol, register_mpyy_fonts
from planx_mpyy_studio.core.msp_styler import MSPStylerEngine
from planx_mpyy_studio.core.nip_styler import NIPStylerEngine
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

    def test_msp_styler_all_geometries(self):
        """Kriter 3 & 4: MSP kataloğu alan, çizgi ve nokta katmanlarına uygulanır."""
        engine = MSPStylerEngine()

        # Polygon
        p_poly = QgsVectorLayer("Polygon?crs=epsg:4326&field=catalog_id:string", "plangml_msp_alan", "memory")
        c_poly = engine.apply(p_poly)
        self.assertGreaterEqual(c_poly, 10)
        self.assertIsInstance(p_poly.renderer(), QgsCategorizedSymbolRenderer)
        self.assertEqual(p_poly.customProperty("mpyy/msp_catalog_source"), "EK-1e PDF Sayfa 1-11")

        # Line
        p_line = QgsVectorLayer("LineString?crs=epsg:4326&field=catalog_id:string", "plangml_msp_cizgi", "memory")
        c_line = engine.apply(p_line)
        self.assertGreaterEqual(c_line, 2)

        # Point
        p_pt = QgsVectorLayer("Point?crs=epsg:4326&field=catalog_id:string", "plangml_msp_notasyon", "memory")
        c_pt = engine.apply(p_pt)
        self.assertGreaterEqual(c_pt, 10)

    def test_cdp_styler(self):
        """Kriter 4: ÇDP kendi katalog ve stil profiliyle render edilir."""
        engine = CDPStylerEngine()
        p_poly = QgsVectorLayer("Polygon?crs=epsg:4326&field=bolge_turu:string", "plangml_cdp_alan", "memory")
        count = engine.apply(p_poly)
        self.assertGreaterEqual(count, 50)
        self.assertIsInstance(p_poly.renderer(), QgsCategorizedSymbolRenderer)

    def test_nip_styler_and_font_notations(self):
        """Kriter 4 & 5: NİP brüt yoğunluk ve MNIP font marker kurallarıyla render edilir."""
        engine = NIPStylerEngine()

        # NIP Alan
        p_poly = QgsVectorLayer("Polygon?crs=epsg:4326&field=fonksiyon_adi:string", "plangml_nip_alan", "memory")
        cnt_poly = engine.apply(p_poly)
        self.assertGreaterEqual(cnt_poly, 50)

        # NIP Notasyon (Point - uses MNIP font symbols)
        p_pt = QgsVectorLayer("Point?crs=epsg:4326&field=merkez_turu:string", "plangml_nip_notasyon", "memory")
        cnt_pt = engine.apply(p_pt)
        self.assertGreaterEqual(cnt_pt, 50)
        renderer = p_pt.renderer()
        self.assertIsInstance(renderer, QgsCategorizedSymbolRenderer)
        cats = renderer.categories()
        first_cat = cats[0]
        cat_sym = first_cat.symbol()
        sl = cat_sym.symbolLayer(0)
        self.assertIsInstance(sl, QgsFontMarkerSymbolLayer)

    def test_uip_official_plangml_form_and_styler(self):
        """Kriter 6: UİP katmanına MpyyUipDb şablon formu ve sembolojisi uygulanır."""
        from planx_mpyy_studio.core.schema import planning_tables

        fields_def = planning_tables("UIP")["plangml_uip_alan"][1]
        field_strs = "&".join(f"field={name}:string" for name in fields_def.keys())
        layer = QgsVectorLayer(f"Polygon?crs=epsg:4326&{field_strs}", "plangml_uip_alan", "memory")
        self.assertTrue(layer.isValid())

        apply_layer_style_and_form(layer)
        self.assertEqual(layer.customProperty("mpyy/form"), 'MpyyUipDb çizim şablonu: uip-alanlar')
        efc = layer.editFormConfig()
        self.assertEqual(efc.layout(), 1)  # TabLayout
        self.assertGreaterEqual(len(efc.invisibleRootContainer().children()), 3)


if __name__ == "__main__":
    unittest.main()
