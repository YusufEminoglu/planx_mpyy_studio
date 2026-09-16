"""Attribute forms must be usable, not just configured.

Earlier suites asserted that a form "has tabs" and a relation "is registered".
Both stayed true while the dropdowns were broken: a generic form builder
replaced the template's conditional tabs and wrote dropdown codes that the
GeoPackage CHECK constraints reject, and the PlanGML renderer classified a
field no form ever fills. These tests drive the real widgets and the real
database instead.
"""

import os
import sqlite3
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsGeometry,
    QgsProject,
    QgsVectorLayerUtils,
)

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from qgis.gui import QgsAttributeEditorContext, QgsAttributeForm, QgsGui, QgsRelationReferenceWidget  # noqa: E402
from qgis.PyQt.QtWidgets import QComboBox  # noqa: E402

QgsGui.editorWidgetRegistry().initEditors()

from planx_mpyy_studio.core.db_factory import (  # noqa: E402
    create_land_use_workspace,
    create_planning_workspace,
    read_dataset_info,
)
from planx_mpyy_studio.core.form_designer import MPYYFormDesigner  # noqa: E402
from planx_mpyy_studio.core.local_uip_workspace import (  # noqa: E402
    KIND,
    TEMPLATE_DIR,
    create_local_uip_workspace,
    template,
)
from planx_mpyy_studio.core.plangml_styler import PlanGMLStylerEngine  # noqa: E402
from planx_mpyy_studio.core.project_binding import load_project_layers  # noqa: E402
from planx_mpyy_studio.core.styler import MPYYStylerEngine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POLYGON = "MULTIPOLYGON(((500000 4250000,500100 4250000,500100 4250100,500000 4250100,500000 4250000)))"
TEMPLATE_TABS = ["VeriKontrol", "1000 PLAN DETAY ALT SINIFI VE FONKSİYONU", "YAPI DÜZENİ VE YOĞUNLUKLARI"]


def value_map_values(layer, field):
    config = layer.editorWidgetSetup(layer.fields().indexFromName(field)).config()
    entries = config.get("map", [])
    if isinstance(entries, dict):
        return list(entries.values())
    return [value for entry in entries for value in entry.values()]


def wait_until(predicate, seconds=15):
    deadline = time.time() + seconds
    while time.time() < deadline:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    return False


class FormDropdownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def _load(self, create, *args):
        path = Path(self.tmp.name) / "workspace.gpkg"
        create(path, "EPSG:5254", *args)
        return path, {layer.name(): layer for layer in load_project_layers(path)}

    def assert_function_dropdown_works(self, layer):
        """Pick an upper group and the chained function list must offer its functions."""
        feature = QgsVectorLayerUtils.createFeature(layer, QgsGeometry.fromWkt(POLYGON), {}, layer.createExpressionContext())
        form = QgsAttributeForm(layer, feature, QgsAttributeEditorContext())
        form.show()
        widgets = form.findChildren(QgsRelationReferenceWidget)
        self.assertEqual(len(widgets), 1, "uipfonksiyon must be a relation dropdown")
        combos = widgets[0].findChildren(QComboBox)
        self.assertTrue(wait_until(lambda: any(c.count() > 20 for c in combos)), [c.count() for c in combos])
        group = next(c for c in combos if c.count() > 20)
        functions = next(c for c in combos if c is not group)
        group.setCurrentIndex(group.findText("KONUT ALANLARI / YERLEŞİM ALANLARI"))
        self.assertTrue(wait_until(lambda: functions.count() >= 2))
        offered = {functions.itemText(i) for i in range(functions.count())}
        self.assertLessEqual({"GELİŞME KONUT ALANI", "YERLEŞİK KONUT ALANI"}, offered)
        form.close()

    def assert_every_dropdown_value_saves(self, layer, fields):
        layer.startEditing()
        added = 0
        for field in fields:
            for value in value_map_values(layer, field):
                if value in (None, "{2839923C-8B7D-419E-B84B-CA2FE9B80EC7}"):
                    continue  # QGIS' NULL sentinel
                feature = QgsVectorLayerUtils.createFeature(
                    layer, QgsGeometry.fromWkt(POLYGON), {}, layer.createExpressionContext()
                )
                feature[field] = value
                self.assertTrue(layer.addFeature(feature))
                added += 1
        self.assertGreater(added, 0)
        self.assertTrue(layer.commitChanges(), layer.commitErrors())

    # --- Yerel UİP: the author's MpyyUipDb structure --------------------------------

    def test_local_uip_workspace_reproduces_template_structure(self):
        path = Path(self.tmp.name) / "yerel.gpkg"
        create_local_uip_workspace(path, "EPSG:5254")
        self.assertEqual(read_dataset_info(path)["workspace_kind"], KIND)
        spec = template()
        with sqlite3.connect(path) as con:
            for table in spec["tables"]:
                columns = {row[1]: row[2] for row in con.execute(f'PRAGMA table_info("{table["table"]}")')}
                for field in table["fields"]:
                    self.assertEqual(columns.get(field["name"]), field["type"], (table["table"], field["name"]))
            self.assertEqual(con.execute('SELECT count(*) FROM "uipPolygonTable"').fetchone()[0], 241)
            self.assertEqual(con.execute('SELECT count(*) FROM "uipLineTable"').fetchone()[0], 33)
            styled = {row[0] for row in con.execute("SELECT f_table_name FROM layer_styles WHERE useAsDefault")}
        self.assertEqual(styled, {t["table"] for t in spec["tables"]})

    def test_local_uip_form_dropdowns_render_and_save(self):
        _, layers = self._load(lambda p, crs: create_local_uip_workspace(p, crs))
        alan = layers["uip-alanlar"]
        self.assertEqual([t.name() for t in alan.editFormConfig().tabs()], TEMPLATE_TABS)
        self.assertEqual(value_map_values(alan, "nizam"), ["A", "B", "BL"])
        self.assert_function_dropdown_works(alan)
        self.assert_every_dropdown_value_saves(alan, ["nizam", "katadedi", "onbahce", "yanbahce", "ustkonugrup"])
        feature = QgsVectorLayerUtils.createFeature(alan, QgsGeometry.fromWkt(POLYGON), {}, alan.createExpressionContext())
        self.assertEqual(feature["AlanM2"], 10000.0)
        cizgi = layers["uip_cizgiler"]
        self.assertIn("ERİŞME KONTROLLÜ KARAYOLU (OTOYOL)", value_map_values(cizgi, "uipfonksiyon"))

    def test_local_uip_symbology_matches_dropdown_values(self):
        _, layers = self._load(lambda p, crs: create_local_uip_workspace(p, crs))
        renderer = layers["uip-alanlar"].renderer()
        self.assertIsInstance(renderer, QgsCategorizedSymbolRenderer)
        self.assertEqual(renderer.classAttribute(), "uipfonksiyon")
        self.assertIn("YERLEŞİK KONUT ALANI", {c.value() for c in renderer.categories()})

    # --- PlanGML planning workspace: same template form on plangml_uip_* ------------

    def test_planning_uip_form_is_template_and_survives_form_designer(self):
        _, layers = self._load(create_planning_workspace, ("UIP",))
        alan = layers["plangml_uip_alan"]
        self.assertEqual([t.name() for t in alan.editFormConfig().tabs()], TEMPLATE_TABS)
        MPYYFormDesigner.apply_complete_form_experience(alan)
        self.assertEqual([t.name() for t in alan.editFormConfig().tabs()], TEMPLATE_TABS)
        self.assertEqual(value_map_values(alan, "nizam"), ["A", "B", "BL"])
        self.assert_function_dropdown_works(alan)
        self.assert_every_dropdown_value_saves(alan, ["nizam", "katadedi", "yapiYaklasmaDurumu", "ustkonugrup"])
        notasyon = layers["plangml_uip_notasyon"]
        expressions = [notasyon.defaultValueDefinition(i).expression() for i in range(notasyon.fields().count())]
        self.assertTrue(any("'plangml_uip_alan'" in e for e in expressions))
        self.assertFalse(any("'uip-alanlar'" in e for e in expressions))

    def test_plangml_style_classifies_the_value_the_form_writes(self):
        _, layers = self._load(create_planning_workspace, ("UIP",))
        alan = layers["plangml_uip_alan"]
        result = PlanGMLStylerEngine().apply(alan, field="uipfonksiyon", plan_type="UIP")
        values = {c.value() for c in alan.renderer().categories()}
        self.assertIn("YERLEŞİK KONUT ALANI", values)
        self.assertGreater(result.official_styles, 0)
        self.assertFalse(any(str(v).startswith("POLYGON:") for v in values))

    # --- Arazi / saha survey forms ----------------------------------------------------

    def test_survey_forms_keep_their_tabs_and_accept_their_dropdown_codes(self):
        _, layers = self._load(lambda p, crs: create_land_use_workspace(p, crs))
        for name in ("parsel_saha", "yapi_saha", "yol_saha"):
            with self.subTest(layer=name):
                layer = layers[name]
                tabs = [t.name() for t in layer.editFormConfig().tabs()]
                self.assertNotIn("Plan fonksiyonu ve alanı", tabs, "generic form replaced the survey form")
                coded = [
                    layer.fields().at(i).name()
                    for i in range(layer.fields().count())
                    if layer.editorWidgetSetup(i).type() == "ValueMap"
                ]
                self.assertTrue(coded)
                geometry = "MULTILINESTRING((500000 4250000,500100 4250100))" if name == "yol_saha" else POLYGON
                layer.startEditing()
                for field in coded:
                    for value in value_map_values(layer, field):
                        feature = QgsVectorLayerUtils.createFeature(
                            layer, QgsGeometry.fromWkt(geometry), {}, layer.createExpressionContext()
                        )
                        feature[field] = value
                        layer.addFeature(feature)
                self.assertTrue(layer.commitChanges(), (name, layer.commitErrors()[:4]))

    # --- Shipped style resources ------------------------------------------------------

    def test_shipped_qml_property_collections_are_not_translated(self):
        for path in (ROOT / "forms").rglob("*.qml"):
            with self.subTest(path=path.name):
                for option in ET.parse(path).getroot().iter("Option"):
                    if option.get("value") == "collection":
                        self.assertEqual(option.get("name"), "type")

    def test_template_files_match_manifest(self):
        import hashlib

        for name, style in template()["styles"].items():
            data = (TEMPLATE_DIR / style["qml"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), style["sha256"], name)

    def test_local_xml_catalog_keeps_field_names_and_setback_generators(self):
        engine = MPYYStylerEngine()
        self.assertNotIn("disabled_setback_layers", engine.inventory)
        symbol = engine._style.symbol("AKARYAKIT VE SERVİS İSTASYONU ALANI")
        self.assertIsNotNone(symbol)
        generators = [
            symbol.symbolLayer(i)
            for i in range(symbol.symbolLayerCount())
            if symbol.symbolLayer(i).layerType() == "GeometryGenerator"
        ]
        self.assertTrue(generators)
        self.assertTrue(all(g.enabled() for g in generators))
        self.assertIn('"yapiYaklasmaMesafesi"', generators[0].geometryExpression())


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
