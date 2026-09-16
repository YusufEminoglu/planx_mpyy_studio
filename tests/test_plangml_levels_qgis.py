"""Hat etiketleri and kademe dönüşümü on real layers and GeoPackages."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsMapRendererSequentialJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from planx_mpyy_studio.core.plangml_level_conversion import convert_workspace  # noqa: E402
from planx_mpyy_studio.core.plangml_import import audit_plangml_workspace  # noqa: E402
from planx_mpyy_studio.core.plangml_workspace import (  # noqa: E402
    PLUGIN_ROOT,
    apply_line_labels,
    create_plangml_workspace,
    level_schema,
)

SQUARE = "MULTIPOLYGON(((500000 4250000,500200 4250000,500200 4250200,500000 4250200,500000 4250000)))"


def memory_layer(level, type_name):
    feature_type = next(t for t in level_schema(level)["feature_types"] if t["name"] == type_name)
    fields = "&".join(f"field={f['name']}:string" for f in feature_type["fields"])
    return QgsVectorLayer(f"MultiPolygon?crs=EPSG:5254&{fields}", type_name, "memory")


def add(layer, values, wkt=SQUARE):
    feature = QgsFeature(layer.fields())
    for key, value in values.items():
        feature[key] = value
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    ok, _ = layer.dataProvider().addFeatures([feature])
    assert ok


class LineLabelTests(unittest.TestCase):
    def test_label_table_targets_exist_in_the_schema(self):
        table = json.loads((PLUGIN_ROOT / "styles" / "plangml_line_labels.json").read_text(encoding="utf-8"))
        for level, rules in table["levels"].items():
            types = {t["name"]: {f["name"]: f for f in t["fields"]} for t in level_schema(level)["feature_types"]}
            for key, rule in rules.items():
                with self.subTest(level=level, key=key):
                    self.assertIn(rule["feature"], types)
                    self.assertTrue(rule["text"])
                    if rule["field"]:
                        definition = types[rule["feature"]][rule["field"]]
                        if definition["type"] == "enum":
                            self.assertIn(rule["code"], level_schema(level)["codelists"][definition["codelist"]])
        self.assertEqual(table["levels"]["UIP"]["SitAlanlari|SitTip=1DereceArkeolojikSit"]["text"], "A1")
        self.assertEqual(table["levels"]["UIP"]["KorumaKusaklari|KusakTip=KarayoluKorumaKusagi"]["text"], "YKK")
        self.assertEqual(table["levels"]["NIP"]["KentselDonusumSinirlari|KentselDonusumSinirlariTip=RiskliAlanSiniri"]["text"], "RA")

    def test_only_the_matching_code_is_labelled_and_the_label_is_drawn(self):
        layer = memory_layer("UIP", "SitAlanlari")
        self.assertGreaterEqual(apply_line_labels(layer, "UIP", "SitAlanlari"), 12)
        self.assertEqual(apply_line_labels(memory_layer("UIP", "Konut"), "UIP", "Konut"), 0)
        add(layer, {"SitTip": "1DereceArkeolojikSit"})
        add(layer, {"SitTip": "KentselSit"}, SQUARE.replace("500000", "500400").replace("500200", "500600"))
        settings = QgsMapSettings()
        settings.setLayers([layer])
        settings.setDestinationCrs(layer.crs())
        settings.setExtent(QgsRectangle(499900, 4249900, 500700, 4250300))
        settings.setOutputSize(QSize(1600, 800))
        job = QgsMapRendererSequentialJob(settings)
        job.start()
        job.waitForFinished()
        texts = {label.labelText for label in job.takeLabelingResults().allLabels()}
        self.assertEqual(texts, {"A1", "KS"})


class LevelConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()
        self.source = Path(self.tmp.name) / "uip.gpkg"
        create_plangml_workspace(self.source, "EPSG:5254", "UIP")
        for type_name, values in (
            ("Konut", {"KonutTip": "YerlesikKonut", "Adi": "Konut 1", "Taks": 0.4, "KatAdedi": 4}),
            ("SitAlanlari", {"SitTip": "1DereceArkeolojikSit", "Adi": "Höyük"}),
            ("AcikYesilAlan", {"AcikYesilTip": "Park", "Adi": "Park"}),
        ):
            layer = QgsVectorLayer(f"{self.source}|layername={type_name}", type_name, "ogr")
            feature = QgsFeature(layer.fields())
            for key, value in values.items():
                feature[key] = value
            feature.setGeometry(QgsGeometry.fromWkt(SQUARE))
            self.assertTrue(layer.dataProvider().addFeatures([feature])[0])
            del layer

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def test_uip_to_nip_keeps_codes_and_leaves_density_to_the_planner(self):
        target = Path(self.tmp.name) / "nip.gpkg"
        _, report = convert_workspace(self.source, target, "NIP")
        rows = {r["kaynak"]: r for r in report}
        self.assertEqual(rows["Konut|KonutTip=YerlesikKonut"]["hedef"], "MevcutKonut")
        self.assertEqual(rows["Konut|KonutTip=YerlesikKonut"]["doldurulacak"], "MevcutKonutYogunluk")
        self.assertEqual(rows["SitAlanlari|SitTip=1DereceArkeolojikSit"]["aktarilan"], 1)
        with sqlite3.connect(target) as con:
            self.assertEqual(con.execute('SELECT MevcutKonutYogunluk FROM "MevcutKonut"').fetchall(), [(None,)])
            self.assertEqual(con.execute('SELECT SitTip FROM "SitAlanlari"').fetchall(), [("1DereceArkeolojikSit",)])
            self.assertEqual(con.execute('SELECT YesilTip FROM "AcikYesilAlan"').fetchall(), [("ParkVeYesilAlan",)])
        audit = {(f["katman"], f["sorun"], f["ayrinti"]) for f in audit_plangml_workspace(target)}
        self.assertIn(("MevcutKonut", "Zorunlu alan boş", "MevcutKonutYogunluk"), audit)

    def test_uip_to_cdp_and_direction_guard(self):
        target = Path(self.tmp.name) / "cdp.gpkg"
        _, report = convert_workspace(self.source, target, "CDP")
        rows = {r["kaynak"]: r for r in report}
        self.assertEqual(rows["Konut|KonutTip=YerlesikKonut"]["hedef"], "KentselYerlesik")
        with sqlite3.connect(target) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM "KentselYerlesik"').fetchone()[0], 1)
            self.assertEqual(con.execute('SELECT SitTip FROM "SitAlanlari"').fetchall(), [("1DereceArkeolojikSit",)])
        with self.assertRaises(ValueError):
            convert_workspace(target, Path(self.tmp.name) / "back.gpkg", "NIP")


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
