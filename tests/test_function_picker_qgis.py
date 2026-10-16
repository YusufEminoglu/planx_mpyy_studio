"""Draw by plan function in every kind of workspace the plugin creates.

A local template (Yerel UİP / NİP) offers its own functions, read from its own
lookup tables, and a choice fills exactly the values the template defines; an
MPYY 1.1.7 workspace offers the Ek-1e catalogue. The workspace form's default
choice is the local UİP template, so that is the case a planner meets first.
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication, QgsGeometry, QgsProject, QgsVectorLayerUtils  # noqa: E402

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from qgis.gui import QgsGui  # noqa: E402

QgsGui.editorWidgetRegistry().initEditors()

from planx_mpyy_studio.core.function_picker import activate, local_functions, loaded_kinds, plan_functions  # noqa: E402
from planx_mpyy_studio.core.local_nip_workspace import create_local_nip_workspace  # noqa: E402
from planx_mpyy_studio.core.local_uip_workspace import create_local_uip_workspace  # noqa: E402
from planx_mpyy_studio.core.project_binding import load_project_layers  # noqa: E402

POLYGON = "MULTIPOLYGON(((500000 4250000,500100 4250000,500100 4250100,500000 4250100,500000 4250000)))"
LINE = "MULTILINESTRING((500000 4250000,500100 4250100))"


class Recorder:
    """A stand-in for iface that records what drawing asked of QGIS."""

    def __init__(self):
        self.active = None
        self.started = 0
        self.warnings = []

    def setActiveLayer(self, layer):
        self.active = layer

    def activeLayer(self):
        return None

    def actionAddFeature(self):
        recorder = self

        class _Action:
            def trigger(self):
                recorder.started += 1
        return _Action()

    def messageBar(self):
        recorder = self

        class _Bar:
            def pushWarning(self, title, text):
                recorder.warnings.append(text)
        return _Bar()


def new_feature(layer, wkt):
    return QgsVectorLayerUtils.createFeature(layer, QgsGeometry.fromWkt(wkt), {}, layer.createExpressionContext())


class FunctionPickerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        for layer in QgsProject.instance().mapLayers().values():
            if layer.isEditable():
                layer.rollBack()
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def load(self, create, name):
        path = Path(self.tmp.name) / name
        create(path, "EPSG:5254")
        return {layer.name(): layer for layer in load_project_layers(path)}

    def test_local_uip_draws_with_its_own_functions(self):
        layers = self.load(create_local_uip_workspace, "yerel_uip.gpkg")
        self.assertEqual(loaded_kinds(), {"mpyy": False, "yerel": {"UIP"}})
        functions = local_functions("UIP")
        lookup = layers["uipPolygonTable"]
        # Every row of the template's own function table, nothing else.
        areas = [f for f in functions if f.layer_mark == "uip-alanlar"]
        self.assertEqual(len(areas), lookup.featureCount())
        self.assertEqual(len([f for f in functions if f.layer_mark == "uip_cizgiler"]),
                         layers["uipLineTable"].featureCount())
        row = next(feature for feature in lookup.getFeatures() if feature["uip_tabaka"] == "PL_KONUT_TICARET")
        chosen = next(f for f in areas if f.name == row["uip_fonksiyon"])

        recorder = Recorder()
        target = activate(chosen, iface=recorder)
        self.assertEqual(target.name(), "uip-alanlar")
        self.assertTrue(target.isEditable())
        self.assertIs(recorder.active, target)
        self.assertEqual(recorder.started, 1)
        drawn = new_feature(target, POLYGON)
        for field, source in (("uipfonksiyon", "uip_fonksiyon"), ("ustkonugrup", "ust_konu_grup"),
                              ("uip_tabaka", "uip_tabaka"), ("id2", "id2")):
            self.assertEqual(str(drawn[field]), str(row[source]), field)
        # The template's own symbology recognises the value: the drawn area gets a symbol.
        renderer = target.renderer()
        self.assertEqual(renderer.classAttribute(), "uipfonksiyon")
        self.assertIn(row["uip_fonksiyon"], [c.value() for c in renderer.categories()])
        # The template's own defaults stay in place.
        self.assertEqual(target.defaultValueDefinition(target.fields().indexFromName("Tarihilk")).expression(), "now()")

        # Switching function replaces every value of the previous choice.
        other = next(f for f in areas if dict(f.attrs).get("ustkonugrup") != row["ust_konu_grup"])
        activate(other, iface=recorder)
        drawn = new_feature(target, POLYGON)
        self.assertEqual(drawn["uipfonksiyon"], other.name)
        self.assertNotEqual(drawn["ustkonugrup"], row["ust_konu_grup"])

        line = next(f for f in functions if f.layer_mark == "uip_cizgiler")
        cizgi = activate(line, iface=recorder)
        self.assertEqual(cizgi.name(), "uip_cizgiler")
        self.assertEqual(new_feature(cizgi, LINE)["uipfonksiyon"], line.name)

    def test_local_nip_draws_areas_and_lines(self):
        layers = self.load(create_local_nip_workspace, "yerel_nip.gpkg")
        self.assertEqual(loaded_kinds()["yerel"], {"NIP"})
        functions = local_functions("NIP")
        areas = [f for f in functions if f.layer_mark == "alanlar-5000"]
        self.assertEqual(len(areas), layers["fonksiyonlar-5000_tablo"].featureCount())
        chosen = areas[0]
        target = activate(chosen, iface=Recorder())
        self.assertEqual(new_feature(target, POLYGON)["nipfonksiyon"], chosen.name)
        lines = [f for f in functions if f.layer_mark == "cizgiler_5000_v2"]
        self.assertTrue(lines, "the line layer's own value list offers its road functions")
        cizgi = activate(lines[0], iface=Recorder())
        self.assertEqual(new_feature(cizgi, LINE)["nipfonksiyon"], lines[0].name)
        self.assertEqual(local_functions("UIP"), [])

    def test_the_panel_lists_and_draws_what_the_workspace_holds(self):
        from planx_mpyy_studio.dock import MPYYDock

        recorder = Recorder()
        dock = MPYYDock(recorder)
        try:
            dock.fn_level.setCurrentIndex(dock.fn_level.findData("UIP"))
            # Nothing loaded: the catalogue is listed, and drawing says what to open.
            self.assertEqual(dock.fn_choice.count(), len(plan_functions("UIP")))
            self.assertIsNone(dock.draw_plan_function())
            self.assertIn("çalışma alanı açın", recorder.warnings[-1])

            path = Path(self.tmp.name) / "panel_uip.gpkg"
            create_local_uip_workspace(path, "EPSG:5254")
            dock.load_workspace(str(path))
            local = local_functions("UIP")
            self.assertEqual(dock.fn_choice.count(), len(local))
            self.assertTrue(all(dock.fn_choice.itemData(i).startswith("yerel:") for i in range(dock.fn_choice.count())))
            layer = dock.draw_plan_function()
            self.assertIsNotNone(layer)
            self.assertEqual(new_feature(layer, POLYGON)["uipfonksiyon"], local[0].name)
        finally:
            dock.dispose_ui()
            dock.deleteLater()
            APP.processEvents()


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
