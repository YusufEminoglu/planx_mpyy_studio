"""MPYY 1.1.7 workspace: tables, fields and dropdowns come from the Ministry XSD."""

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsFieldConstraints,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
    QgsVectorLayerUtils,
    QgsWkbTypes,
)

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from qgis.gui import QgsAttributeEditorContext, QgsAttributeForm, QgsGui  # noqa: E402
from qgis.PyQt.QtWidgets import QComboBox  # noqa: E402

QgsGui.editorWidgetRegistry().initEditors()

from planx_mpyy_studio.core.db_factory import read_dataset_info  # noqa: E402
from planx_mpyy_studio.core.mpyy_workspace import (  # noqa: E402
    KIND,
    QGIS_NULL,
    audit_required_fields,
    catalog,
    create_mpyy_workspace,
    level_schema,
)
from planx_mpyy_studio.core.project_binding import load_project_layers  # noqa: E402

POLYGON = "MULTIPOLYGON(((500000 4250000,500100 4250000,500100 4250100,500000 4250100,500000 4250000)))"
DOWNLOADED_SCHEMA = Path.home() / "Downloads" / "planGMLShema_1_7.zip"
SQL_TYPES = {"string": "TEXT", "enum": "TEXT", "double": "REAL", "int": "MEDIUMINT", "long": "INTEGER", "dateTime": "DATETIME"}


def value_map(layer, field):
    entries = layer.editorWidgetSetup(layer.fields().indexFromName(field)).config().get("map", [])
    return [value for entry in entries for value in entry.values()]


class MPYYWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def test_catalog_reflects_facts_read_from_the_xsd(self):
        uip = {t["name"]: t for t in level_schema("UIP")["feature_types"]}
        konut = {f["name"]: f for f in uip["Konut"]["fields"]}
        self.assertEqual(uip["Konut"]["geometry"], "MultiPolygon")
        self.assertEqual(konut["Taks"], {"name": "Taks", "type": "double", "required": True})
        self.assertEqual(konut["KatAdedi"]["type"], "int")
        self.assertFalse(konut["MudahaleYontemi"]["required"])
        self.assertEqual(level_schema("UIP")["codelists"]["YapiDuzenTip"], ["Ayrik", "Bitisik", "Blok", "Serbest", "Ikiz"])
        self.assertEqual(level_schema("UIP")["codelists"]["KonutTip"], ["YerlesikKonut", "GelismeKonut"])
        self.assertEqual(uip["Yolorta"]["geometry"], "LineString")
        self.assertIsNone(uip["PlanNotu"]["geometry"])
        self.assertEqual([f["name"] for f in uip["PlanSiniri"]["fields"]], ["symbolizer", "Pin", "PlanAdi", "Nitelik"])
        self.assertEqual({k: v["xsd"]["file"] for k, v in catalog()["levels"].items()},
                         {"UIP": "uip.V.1.1.7.xsd", "NIP": "nip.V.1.1.7.xsd", "CDP": "cdp.V.1.1.7.xsd"})
        self.assertEqual({k: len(v["feature_types"]) for k, v in catalog()["levels"].items()},
                         {"UIP": 96, "NIP": 87, "CDP": 72})
        # Gaps of 1.1.6 that 1.1.7 closes.
        self.assertEqual(level_schema("CDP")["undefined_members"], [])
        self.assertIn("KentselArkeolojikSit", level_schema("UIP")["codelists"]["SitTip"])
        self.assertIn("TuzlaAlani", level_schema("UIP")["codelists"]["CalismaTip"])
        self.assertIn("OrganizeTarimVeHayvancilikAlani", level_schema("CDP")["codelists"]["TarimTip"])
        cdp_sit = next(t for t in level_schema("CDP")["feature_types"] if t["name"] == "SitAlanlari")
        self.assertEqual(next(f for f in cdp_sit["fields"] if f["name"] == "SitTip")["type"], "enum")
        self.assertEqual(uip["ManiaPlani"]["geometry"], "MultiPolygon")

    @unittest.skipUnless(DOWNLOADED_SCHEMA.exists(), "official MPYY zip not present")
    def test_catalog_recompiles_identically_from_the_official_zip(self):
        import importlib.util
        import json

        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("compiler", root / "tools" / "compile_mpyy_schema.py")
        compiler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(compiler)
        compiler.OUT = Path(self.tmp.name) / "schema.json"
        compiler.main(str(DOWNLOADED_SCHEMA))
        self.assertEqual(json.loads(compiler.OUT.read_text(encoding="utf-8")), catalog())

    def test_every_level_creates_exactly_the_schema_tables(self):
        for level in ("UIP", "NIP", "CDP"):
            with self.subTest(level=level):
                path = Path(self.tmp.name) / f"{level}.gpkg"
                create_mpyy_workspace(path, "EPSG:5254", level)
                info = read_dataset_info(path)
                self.assertEqual((info["workspace_kind"], info["plan_levels"]), (KIND, (level,)))
                schema = level_schema(level)
                with sqlite3.connect(path) as con:
                    contents = dict(con.execute("SELECT table_name, data_type FROM gpkg_contents"))
                    geometry = dict(con.execute("SELECT table_name, geometry_type_name FROM gpkg_geometry_columns"))
                    for feature_type in schema["feature_types"]:
                        name = feature_type["name"]
                        expected_kind = "features" if feature_type["geometry"] else "attributes"
                        self.assertEqual(contents.get(name), expected_kind, name)
                        if feature_type["geometry"]:
                            self.assertEqual(geometry[name], feature_type["geometry"].upper(), name)
                        columns = {row[1]: row[2] for row in con.execute(f'PRAGMA table_info("{name}")')}
                        for field in feature_type["fields"]:
                            self.assertEqual(columns.get(field["name"]), SQL_TYPES[field["type"]], (name, field["name"]))
                    tables = {n for n, kind in contents.items() if kind in ("features", "attributes")}
                    self.assertEqual(tables - {"mpyy_sema", "layer_styles"},
                                     {t["name"] for t in schema["feature_types"]})
                    self.assertEqual(con.execute("SELECT xsd_sha256 FROM mpyy_sema").fetchone()[0],
                                     schema["xsd"]["sha256"])

    def test_uip_forms_offer_codelists_and_store_schema_codes(self):
        path = Path(self.tmp.name) / "uip.gpkg"
        create_mpyy_workspace(path, "EPSG:5254", "UIP")
        layers = {layer.name(): layer for layer in load_project_layers(path)}
        self.assertEqual(len(layers), 96)
        konut = layers["Konut"]
        self.assertEqual(value_map(konut, "YapiDuzeni"), ["Ayrik", "Bitisik", "Blok", "Serbest", "Ikiz"])
        self.assertEqual(QgsWkbTypes.geometryType(konut.wkbType()), QgsWkbTypes.GeometryType.PolygonGeometry)

        feature = QgsVectorLayerUtils.createFeature(konut, QgsGeometry.fromWkt(POLYGON), {}, konut.createExpressionContext())
        form = QgsAttributeForm(konut, feature, QgsAttributeEditorContext())
        form.show()
        def offered():
            return [{c.itemData(i) for i in range(c.count())} - {None, QGIS_NULL} for c in form.findChildren(QComboBox)]

        deadline = time.time() + 5
        while time.time() < deadline and not any(o for o in offered()):
            APP.processEvents()
        # An empty required dropdown also lists the current NULL; the schema codes must all be there.
        self.assertIn({"Ayrik", "Bitisik", "Blok", "Serbest", "Ikiz"}, offered())
        self.assertIn({"YerlesikKonut", "GelismeKonut"}, offered())
        form.close()

        konut.startEditing()
        for yapi_duzeni in value_map(konut, "YapiDuzeni"):
            for konut_tip in value_map(konut, "KonutTip"):
                f = QgsVectorLayerUtils.createFeature(konut, QgsGeometry.fromWkt(POLYGON), {}, konut.createExpressionContext())
                f["YapiDuzeni"], f["KonutTip"], f["Taks"], f["KatAdedi"] = yapi_duzeni, konut_tip, 0.4, 4
                self.assertTrue(konut.addFeature(f))
        self.assertTrue(konut.commitChanges(), konut.commitErrors())
        stored = {(f["YapiDuzeni"], f["KonutTip"]) for f in konut.getFeatures()}
        self.assertIn(("Bitisik", "GelismeKonut"), stored)

    def test_required_fields_warn_but_allow_drafts_and_are_audited(self):
        path = Path(self.tmp.name) / "uip.gpkg"
        create_mpyy_workspace(path, "EPSG:5254", "UIP")
        layers = {layer.name(): layer for layer in load_project_layers(path)}
        konut = layers["Konut"]
        index = konut.fields().indexFromName("Taks")
        self.assertEqual(
            konut.fields().at(index).constraints().constraintStrength(QgsFieldConstraints.Constraint.ConstraintNotNull),
            QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft,
        )
        optional = konut.fields().indexFromName("MudahaleYontemi")
        self.assertFalse(konut.fields().at(optional).constraints().constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull)
        konut.startEditing()
        draft = QgsVectorLayerUtils.createFeature(konut, QgsGeometry.fromWkt(POLYGON), {}, konut.createExpressionContext())
        draft["KonutTip"] = "YerlesikKonut"
        konut.addFeature(draft)
        self.assertTrue(konut.commitChanges(), konut.commitErrors())
        report = audit_required_fields(layers.values())
        self.assertIn("Taks", report["Konut"])
        self.assertNotIn("KonutTip", report["Konut"])
        self.assertNotIn("MudahaleYontemi", report["Konut"])

        wrong = next(konut.getFeatures())
        wrong["YapiDuzeni"] = "AYRIK"  # legacy code, not in the MPYY code list
        valid, _ = QgsVectorLayerUtils.validateAttribute(
            konut, wrong, konut.fields().indexFromName("YapiDuzeni"),
            QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard,
        )
        self.assertFalse(valid)

    def test_official_sld_symbology_is_applied_with_schema_codes(self):
        import json

        from planx_mpyy_studio.core.mpyy_workspace import SLD_DIR

        path = Path(self.tmp.name) / "uip.gpkg"
        create_mpyy_workspace(path, "EPSG:5254", "UIP")
        layers = {layer.name(): layer for layer in load_project_layers(path)}

        def rules(layer):
            return {rule.label(): rule for rule in layer.renderer().rootRule().children()}

        konut = rules(layers["Konut"])
        self.assertEqual(konut["YERLESIK_KONUT"].filterExpression().replace('"', ""), "KonutTip = 'YerlesikKonut'")
        self.assertEqual(konut["YERLESIK_KONUT"].symbol().color().name().upper(), "#8C541A")
        self.assertEqual(konut["GELISME_KONUT"].symbol().color().name().upper(), "#FFFA26")
        self.assertIn("Kodu girilmemiş / resmî gösterimi yok", konut)

        ticaret = rules(layers["KentselCalisma"])["TICARET_ALANI"].symbol()
        kinds = [ticaret.symbolLayer(i).layerType() for i in range(ticaret.symbolLayerCount())]
        self.assertEqual(kinds, ["RasterFill", "CentroidFill"])
        self.assertTrue(ticaret.symbolLayer(0).imageFilePath().startswith("base64:"))
        marker = ticaret.symbolLayer(1).subSymbol().symbolLayer(0)
        self.assertEqual((marker.layerType(), marker.fontFamily(), marker.character()), ("FontMarker", "OG_V_1_2", "D"))

        # UIP_YOLORTA only has text symbolizers: the road width is written in a circle instead.
        self.assertEqual(layers["Yolorta"].customProperty("mpyy/symbology"), "e-Plan SLD (yol genişliği yazısı): UIP/Yolorta")

        # Reopened without the plugin, the GeoPackage alone carries the official symbology.
        plain = QgsVectorLayer(f"{path}|layername=KentselCalisma", "plain", "ogr")
        first = plain.renderer().rootRule().children()[0].symbol()
        self.assertTrue(first.symbolLayer(0).imageFilePath().startswith("base64:iVBOR"))  # lossless PNG

        mapping = json.loads((SLD_DIR / "mapping.json").read_text(encoding="utf-8"))
        for level, report in mapping["levels"].items():
            codes = {c for c in level_schema(level)["codelists"].values() for c in c}
            for type_name, entry in report["types"].items():
                text = (SLD_DIR / level / f"{type_name}.sld").read_text(encoding="utf-8")
                for rule in entry["rules"]:
                    for condition in rule["conditions"]:
                        if condition.get("code") and not rule["dropped"]:
                            self.assertIn(condition["code"], codes)
                            self.assertIn(f"<ogc:Literal>{condition['code']}</ogc:Literal>", text)
        # Only this type lacks an SLD; it is drawn from the detail catalog definition in decisions.json.
        self.assertEqual(mapping["levels"]["UIP"]["missing_styles"], ["KentselTasarimProjeSiniri"])
        self.assertEqual(layers["KentselTasarimProjeSiniri"].customProperty("mpyy/symbology"),
                         "Detay kataloğu: UIP/KentselTasarimProjeSiniri")
        self.assertEqual(mapping["levels"]["UIP"]["types"]["YapiYaklasC"]["style"], "UIP_YAPI_YAKLASMA_MES")
        self.assertEqual(mapping["levels"]["NIP"]["missing_styles"], [])
        self.assertEqual(mapping["levels"]["CDP"]["missing_styles"], [])
        # 1.1.7 added the codes these Ministry rules already pointed at; nothing is left unresolved.
        resolutions = [c.get("resolution") for lv in mapping["levels"].values() for t in lv["types"].values()
                       for r in t["rules"] for c in r["conditions"]]
        self.assertNotIn("unresolved", resolutions)
        tuzla = [c["code"] for t in [mapping["levels"]["UIP"]["types"]["KentselCalisma"]] for r in t["rules"]
                 if r["title"] == "TUZLA_ALANI" for c in r["conditions"]]
        self.assertEqual(tuzla, ["TuzlaAlani"])

    def test_plain_qgis_gets_the_dropdowns_from_the_geopackage(self):
        path = Path(self.tmp.name) / "nip.gpkg"
        create_mpyy_workspace(path, "EPSG:5254", "NIP")
        schema = {t["name"]: t for t in level_schema("NIP")["feature_types"]}
        name, field = next(
            (t["name"], f) for t in schema.values() for f in t["fields"] if f["type"] == "enum"
        )
        layer = QgsVectorLayer(f"{path}|layername={name}", name, "ogr")  # no plugin configuration
        self.assertTrue(layer.isValid())
        expected = level_schema("NIP")["codelists"][field["codelist"]]
        values = [v for v in value_map(layer, field["name"]) if v != QGIS_NULL]
        self.assertEqual(values, expected)


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
