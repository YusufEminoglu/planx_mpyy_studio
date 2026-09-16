"""CAD tabaka → PlanGML import and PlanGML schema audit, on real GeoPackages."""

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer  # noqa: E402

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()

from planx_mpyy_studio.core.plangml_import import (  # noqa: E402
    CROSSWALK_PATH,
    audit_plangml_workspace,
    import_cad_layer,
    normalize_tabaka,
)
from planx_mpyy_studio.core.plangml_workspace import create_plangml_workspace, level_schema  # noqa: E402


def cad_layer(rows, geometry="Polygon"):
    layer = QgsVectorLayer(f"{geometry}?crs=EPSG:5254&field=Layer:string", "cad", "memory")
    features = []
    for tabaka, wkt in rows:
        feature = QgsFeature(layer.fields())
        feature["Layer"] = tabaka
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        features.append(feature)
    ok, _ = layer.dataProvider().addFeatures(features)
    assert ok and layer.featureCount() == len(rows)
    return layer


def count(path, table):
    with sqlite3.connect(path) as con:
        return con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]


class PlanGMLImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def test_every_crosswalk_entry_is_valid_for_its_level(self):
        crosswalk = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))["levels"]
        for level, table in crosswalk.items():
            schema = level_schema(level)
            types = {t["name"]: {f["name"]: f for f in t["fields"]} for t in schema["feature_types"]}
            self.assertGreater(len(table["entries"]), 100)
            for tabaka, entry in table["entries"].items():
                with self.subTest(level=level, tabaka=tabaka):
                    self.assertEqual(tabaka, normalize_tabaka(tabaka))
                    self.assertIn(entry["feature"], types)
                    for field, value in entry["attrs"].items():
                        definition = types[entry["feature"]][field]
                        if definition["type"] == "enum":  # e.g. ÇDP SitTip is free text in the XSD
                            self.assertIn(value, schema["codelists"][definition["codelist"]])
        # Level-specific repairs of the source table.
        self.assertEqual(crosswalk["NIP"]["entries"]["PL_GELISME_KONUT"]["feature"], "GelismeKonut")
        self.assertEqual(crosswalk["CDP"]["entries"]["PL_GELISME_KONUT"]["feature"], "KentselGelismeKonut")
        self.assertEqual(crosswalk["NIP"]["entries"]["PL_REKREASYON"]["attrs"], {"YesilTip": "RekreasyonAlani"})
        self.assertNotIn("SNR_JEOLOJIK_ETUT", crosswalk["CDP"]["entries"])

    def test_cad_features_land_in_plangml_tables_with_codes(self):
        path = Path(self.tmp.name) / "uip.gpkg"
        create_plangml_workspace(path, "EPSG:5254", "UIP")
        square = "POLYGON((500000 4250000,500100 4250000,500100 4250100,500000 4250100,500000 4250000))"
        closed = "LINESTRING(500200 4250000,500300 4250000,500300 4250100,500200 4250000)"
        areas = cad_layer([
            ("PL_KONUT", square),
            ("ADA_KENARI", square),  # an area on a line type
            ("PAFTA", square),
            ("BILINMEYEN_TABAKA", square),
        ])
        lines = cad_layer([
            ("pl-ticaret", closed),  # closed CAD polyline, different spelling
            ("HAT_HIZLI_TREN", "MULTILINESTRING((500000 4250200,500100 4250300),(500200 4250200,500300 4250300))"),
        ], "MultiLineString")
        report = {row["tabaka"]: row for row in import_cad_layer(areas, "Layer", path) + import_cad_layer(lines, "Layer", path)}

        self.assertEqual(report["PL_KONUT"]["aktarilan"], 1)
        self.assertEqual(report["pl-ticaret"]["aktarilan"], 1)
        self.assertEqual(report["HAT_HIZLI_TREN"]["aktarilan"], 2)  # split for the LineString type
        self.assertEqual(report["ADA_KENARI"]["aktarilan"], 0)
        self.assertEqual(report["ADA_KENARI"]["durum"], "Geometri uyuşmuyor (şema: çizgi, veri: alan)")
        self.assertEqual(report["PAFTA"]["durum"], "yardımcı çizim tabakası")
        self.assertEqual(report["BILINMEYEN_TABAKA"]["durum"], "eşleşme tablosunda yok")

        with sqlite3.connect(path) as con:
            self.assertEqual(con.execute('SELECT KonutTip FROM "Konut"').fetchall(), [("YerlesikKonut",)])
            self.assertEqual(con.execute('SELECT CalismaTip FROM "KentselCalisma"').fetchall(), [("TicaretAlani",)])
            self.assertEqual(con.execute('SELECT DISTINCT DemirTip FROM "Demiryolu"').fetchall(), [("HizliTrenHat",)])
        self.assertEqual(count(path, "AdaKenari"), 0)

    def test_audit_reports_schema_violations(self):
        path = Path(self.tmp.name) / "nip.gpkg"
        create_plangml_workspace(path, "EPSG:5254", "NIP")
        square = "POLYGON((500000 4250000,500100 4250000,500100 4250100,500000 4250100,500000 4250000))"
        import_cad_layer(cad_layer([("PL_TICARET", square)]), "Layer", path)
        layer = QgsVectorLayer(f"{path}|layername=KentselCalisma", "k", "ogr")
        index = layer.fields().indexFromName("CalismaTip")
        self.assertTrue(layer.dataProvider().changeAttributeValues({next(layer.getFeatures()).id(): {index: "TICARET"}}))
        del layer
        extra = QgsVectorLayer("Polygon?crs=EPSG:5254&field=x:string", "cad_artigi", "memory")
        from qgis.core import QgsVectorFileWriter

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = "cad_artigi"
        options.actionOnExistingFile = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
        error = QgsVectorFileWriter.writeAsVectorFormatV3(extra, str(path), QgsProject.instance().transformContext(), options)
        self.assertEqual(error[0], QgsVectorFileWriter.WriterError.NoError, error)

        findings = audit_plangml_workspace(path)
        problems = {(f["katman"], f["sorun"], f["ayrinti"]) for f in findings}
        self.assertIn(("KentselCalisma", "Kod listesinde olmayan değer", "CalismaTip=TICARET"), problems)
        self.assertIn(("KentselCalisma", "Zorunlu alan boş", "Adi"), problems)  # NİP KentselCalisma has no TAKS
        self.assertIn(("cad_artigi", "Şemada olmayan katman",
                       "NIP PlanGML 1.1.7 şemasında 'cad_artigi' tipi yok; GML'e aktarılmaz."), problems)
        self.assertFalse(any(f["katman"] == "Konut" for f in findings))
        self.assertFalse(any(f["sorun"] == "Şema sürümü farklı" for f in findings))

    def test_audit_flags_a_workspace_built_with_an_older_schema(self):
        path = Path(self.tmp.name) / "old.gpkg"
        create_plangml_workspace(path, "EPSG:5254", "UIP")
        with sqlite3.connect(path) as con:  # plain table, no GeoPackage triggers
            con.execute("UPDATE plangml_sema SET xsd_dosyasi = 'uip.V.1.1.6.xsd'")
            con.execute('DROP TABLE "ManiaSiniri"')
            con.execute("DELETE FROM gpkg_contents WHERE table_name = 'ManiaSiniri'")
            con.execute("DELETE FROM gpkg_geometry_columns WHERE table_name = 'ManiaSiniri'")
        problems = {(f["katman"], f["sorun"]) for f in audit_plangml_workspace(path)}
        self.assertIn(("plangml_sema", "Şema sürümü farklı"), problems)
        self.assertIn(("ManiaSiniri", "Şemadaki katman dosyada yok"), problems)


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
