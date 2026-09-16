"""Rigorous QGIS tests for PlanGML and Arazi Kullanımı database isolation."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsProject, QgsVectorLayer
from planx_mpyy_studio.core.db_factory import (
    create_land_use_workspace,
    create_planning_workspace,
    read_dataset_info,
)
from planx_mpyy_studio.core.project_binding import load_project_layers
from planx_mpyy_studio.core.schema import LAND_TABLES

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def test_isolated_msp_cdp_nip_uip_workspaces(self):
        """Kriter 1 & 2: MSP, ÇDP, NİP ve UİP ayrı ayrı oluşturulur ve şemalar kesinlikle izoledir."""
        crs = QgsCoordinateReferenceSystem("EPSG:5254")

        # 1. MSP
        p_msp = Path(self.tmp.name) / "msp.gpkg"
        create_planning_workspace(p_msp, crs, ("MSP",))
        info_msp = read_dataset_info(p_msp)
        self.assertEqual(info_msp["plan_levels"], ("MSP",))
        lyr_msp = QgsVectorLayer(f"{p_msp}|layername=plangml_msp_alan", "msp_alan", "ogr")
        self.assertTrue(lyr_msp.isValid())
        msp_fields = [f.name() for f in lyr_msp.fields()]
        self.assertIn("alan_ha", msp_fields)
        self.assertNotIn("taks", msp_fields)
        self.assertNotIn("kaks", msp_fields)
        self.assertNotIn("yencok", msp_fields)

        # 2. ÇDP
        p_cdp = Path(self.tmp.name) / "cdp.gpkg"
        create_planning_workspace(p_cdp, crs, ("CDP",))
        lyr_cdp = QgsVectorLayer(f"{p_cdp}|layername=plangml_cdp_alan", "cdp_alan", "ogr")
        self.assertTrue(lyr_cdp.isValid())
        cdp_fields = [f.name() for f in lyr_cdp.fields()]
        self.assertIn("bolge_turu", cdp_fields)
        self.assertNotIn("taks", cdp_fields)
        self.assertNotIn("kaks", cdp_fields)

        # 3. NİP
        p_nip = Path(self.tmp.name) / "nip.gpkg"
        create_planning_workspace(p_nip, crs, ("NIP",))
        lyr_nip = QgsVectorLayer(f"{p_nip}|layername=plangml_nip_alan", "nip_alan", "ogr")
        self.assertTrue(lyr_nip.isValid())
        nip_fields = [f.name() for f in lyr_nip.fields()]
        self.assertIn("brut_yogunluk_kisi_ha", nip_fields)
        self.assertNotIn("taks", nip_fields)
        self.assertNotIn("kaks", nip_fields)

        # 4. UİP
        p_uip = Path(self.tmp.name) / "uip.gpkg"
        create_planning_workspace(p_uip, crs, ("UIP",))
        lyr_uip = QgsVectorLayer(f"{p_uip}|layername=plangml_uip_alan", "uip_alan", "ogr")
        self.assertTrue(lyr_uip.isValid())
        uip_fields = [f.name() for f in lyr_uip.fields()]
        self.assertIn("taks", uip_fields)
        self.assertIn("kaks", uip_fields)
        self.assertIn("uipfonksiyon", uip_fields)
        self.assertIn("yapiYaklasmaMesafesi", uip_fields)

    def test_msp_catalog_and_uip_lookups_in_database(self):
        """Kriter 3: MSP PDF kataloğundaki tüm kayıtlar sayfa referanslarıyla veritabanına alınır."""
        p = Path(self.tmp.name) / "full_plan.gpkg"
        create_planning_workspace(p, "EPSG:32635", ("MSP", "UIP"))

        with sqlite3.connect(p) as con:
            # Check MSP catalog table
            cur = con.cursor()
            cur.execute("SELECT count(*) FROM mpyy_msp_katalogu")
            self.assertEqual(cur.fetchone()[0], 28)

            cur.execute("SELECT source_pdf_page FROM mpyy_msp_katalogu WHERE msp_catalog_id = 'MSP-001'")
            self.assertEqual(cur.fetchone()[0], 1)

            cur.execute("SELECT source_pdf_page FROM mpyy_msp_katalogu WHERE msp_catalog_id = 'MSP-028'")
            self.assertEqual(cur.fetchone()[0], 11)

            # Check UIP Lookup tables
            cur.execute("SELECT count(*) FROM uipPolygonTable")
            self.assertEqual(cur.fetchone()[0], 241)

            cur.execute("SELECT count(*) FROM uipLineTable")
            self.assertEqual(cur.fetchone()[0], 33)

            # Check layer_styles table exists and has entries
            cur.execute("SELECT count(*) FROM layer_styles")
            self.assertGreater(cur.fetchone()[0], 0)

    def test_land_use_workspace_complete_and_valid(self):
        """Kriter 7: Arazi Kullanımı GeoPackage’ı oluşturulur, açılır ve formları çalışır."""
        p = Path(self.tmp.name) / "arazi.gpkg"
        create_land_use_workspace(p, "EPSG:32635")
        info = read_dataset_info(p)
        self.assertEqual(info["workspace_kind"], "ARAZI_KULLANIMI")

        for table_name in LAND_TABLES:
            lyr = QgsVectorLayer(f"{p}|layername={table_name}", table_name, "ogr")
            self.assertTrue(lyr.isValid(), f"Table {table_name} must be a valid vector layer")
            f_names = [f.name() for f in lyr.fields()]
            self.assertIn("fotograf", f_names)
            self.assertIn("global_id", f_names)

        with sqlite3.connect(p) as con:
            cur = con.cursor()
            cur.execute("SELECT count(*) FROM saha_kullanim_kodlari")
            self.assertEqual(cur.fetchone()[0], 58)

            cur.execute("SELECT count(*) FROM saha_yapi_durum_kodlari")
            self.assertEqual(cur.fetchone()[0], 6)

            cur.execute("SELECT count(*) FROM saha_yapi_cins_kodlari")
            self.assertEqual(cur.fetchone()[0], 8)

            cur.execute("SELECT count(*) FROM saha_nizam_kodlari")
            self.assertEqual(cur.fetchone()[0], 5)

            cur.execute("SELECT count(*) FROM saha_parsel_durum_kodlari")
            self.assertEqual(cur.fetchone()[0], 5)


            cur.execute("SELECT count(*) FROM saha_yol_tip_kodlari")
            self.assertEqual(cur.fetchone()[0], 6)

            cur.execute("SELECT count(*) FROM saha_mulkiyet_kodlari")
            self.assertEqual(cur.fetchone()[0], 6)

            cur.execute("SELECT count(*) FROM saha_yapi_kalite_kodlari")
            self.assertEqual(cur.fetchone()[0], 5)

            cur.execute("SELECT count(*) FROM saha_yol_kaplama_kodlari")
            self.assertEqual(cur.fetchone()[0], 9)

            cur.execute("SELECT count(*) FROM saha_koruma_kodlari")
            self.assertEqual(cur.fetchone()[0], 5)

            cur.execute("SELECT count(*) FROM saha_cati_kodlari")
            self.assertEqual(cur.fetchone()[0], 6)

            cur.execute("SELECT count(*) FROM saha_isitma_kodlari")
            self.assertEqual(cur.fetchone()[0], 5)

            cur.execute("SELECT count(*) FROM saha_hasar_kodlari")
            self.assertEqual(cur.fetchone()[0], 5)

            # Check views registered in gpkg_contents
            cur.execute("SELECT table_name FROM gpkg_contents WHERE data_type = 'attributes' AND table_name LIKE 'v_saha_%'")
            views = {row[0] for row in cur.fetchall()}
            self.assertIn("v_saha_parsel_kullanim_ozet", views)
            self.assertIn("v_saha_yapi_kat_ve_durum_ozet", views)
            self.assertIn("v_saha_mahalle_bilancosu", views)
            self.assertIn("v_saha_yol_envanteri", views)

        # Check survey insert trigger auto-populates global_id and tarih
        lyr_parsel = QgsVectorLayer(f"{p}|layername=parsel_saha", "parsel_saha", "ogr")
        self.assertTrue(lyr_parsel.isValid())
        f = QgsFeature(lyr_parsel.fields())
        f["ADA"] = "101"
        f["PARSEL"] = "1"
        f["P_FONK"] = "KONUT"
        lyr_parsel.startEditing()
        self.assertTrue(lyr_parsel.addFeature(f))
        self.assertTrue(lyr_parsel.commitChanges())

        with sqlite3.connect(p) as con:
            cur = con.cursor()
            cur.execute("SELECT global_id, tarih FROM parsel_saha WHERE ADA='101' AND PARSEL='1'")
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertTrue(len(row[0]) > 20, "global_id must be auto-generated UUID")
            self.assertTrue(len(row[1]) > 5, "tarih must be auto-generated timestamp")

    def test_qfield_packager(self):
        """QField paketleyici test: proje klasörü, .qgs, fotograflar ve data.gpkg oluşturulur."""
        from planx_mpyy_studio.core.qfield_packager import package_for_qfield

        gpkg_path = Path(self.tmp.name) / "saha_src.gpkg"
        create_land_use_workspace(gpkg_path, "EPSG:5254")

        out_dir = Path(self.tmp.name) / "qfield_bundle"
        res = package_for_qfield(gpkg_path, out_dir, project_title="Test QField Survey", include_osm=True)

        self.assertTrue(Path(res["output_dir"]).is_dir())
        self.assertTrue(Path(res["project_file"]).is_file())
        self.assertTrue(Path(res["photo_dir"]).is_dir())
        self.assertTrue(Path(res["gpkg_file"]).is_file())
        self.assertGreater(res["layer_count"], 0)

        readme = out_dir / "README_QFIELD.md"
        self.assertTrue(readme.is_file())
        self.assertIn("QField", readme.read_text(encoding="utf-8"))

    def test_geom_cleaner(self):
        """Geometri temizleme testi: geçersiz geometri ve mikro-sliver onarılır."""
        from qgis.core import QgsGeometry
        from planx_mpyy_studio.core.geom_cleaner import clean_planning_geometry

        # Self-intersecting bowtie polygon
        wkt = "POLYGON((0 0, 0 10, 10 0, 10 10, 0 0))"
        bad_geom = QgsGeometry.fromWkt(wkt)
        self.assertFalse(bad_geom.isGeosValid())

        cleaned, was_repaired = clean_planning_geometry(bad_geom, snap_tolerance=0.01, min_area_m2=0.5)
        self.assertTrue(was_repaired)
        self.assertTrue(cleaned.isGeosValid())

    def test_report_exporter(self):
        """Bilanço ve açıklama raporu testi: HTML ve CSV dosyaları üretilir."""
        from planx_mpyy_studio.core.report_exporter import export_planning_report

        gpkg_path = Path(self.tmp.name) / "report_src.gpkg"
        create_land_use_workspace(gpkg_path, "EPSG:5254")

        out_dir = Path(self.tmp.name) / "report_out"
        res = export_planning_report(gpkg_path, out_dir, report_title="Test Plan Raporu")

        self.assertTrue(Path(res["html_report"]).is_file())
        self.assertTrue(Path(res["csv_directory"]).is_dir())
        html_content = Path(res["html_report"]).read_text(encoding="utf-8")
        self.assertIn("Test Plan Raporu", html_content)


if __name__ == "__main__":
    unittest.main()

