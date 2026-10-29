"""QGIS-runtime regression tests for PlanX MPYY Studio comprehensive audit fixes."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import (
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from planx_mpyy_studio.core.capacity_engine import PlanCapacityEngine
from planx_mpyy_studio.core.compliance_engine import ComplianceEngine
from planx_mpyy_studio.core.parking_engine import ParkingEngine
from planx_mpyy_studio.core.plan_diff import PlanRevisionDiffEngine
from planx_mpyy_studio.core.risk_engine import UrbanTransformationRiskEngine
from planx_mpyy_studio.core.shelter_engine import ShelterEngine
from planx_mpyy_studio.core.zoning_certificate import ZoningCertificateEngine

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


class AuditFixesQgisTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()

    def test_compliance_engine_attached_and_detached(self):
        # 1. Attached residential parcel: 10m x 20m = 200 m2 (BITISIK, 3 kat) -> YAPILASABILIR (area >= 150, frontage >= 6)
        layer = QgsVectorLayer("MultiPolygon?crs=EPSG:5254&field=ada:string&field=parsel:string&field=nizam:string&field=kat:integer", "bitisik_layer", "memory")
        f1 = QgsFeature(layer.fields())
        f1["ada"], f1["parsel"], f1["nizam"], f1["kat"] = "101", "1", "BITISIK", 3
        f1.setGeometry(QgsGeometry.fromWkt("MULTIPOLYGON(((0 0, 10 0, 10 20, 0 20, 0 0)))"))
        layer.dataProvider().addFeatures([f1])

        results, summary = ComplianceEngine.evaluate_parcels(list(layer.getFeatures()))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].durum, "YAPILASABILIR")
        self.assertEqual(results[0].nizam, "BITISIK")

        # 2. Detached parcel with depth deficit: 17.5m depth < 18m required -> TEVHID_ZORUNLU
        f2 = QgsFeature(layer.fields())
        f2["ada"], f2["parsel"], f2["nizam"], f2["kat"] = "101", "2", "AYRIK", 4
        f2.setGeometry(QgsGeometry.fromWkt("MULTIPOLYGON(((0 0, 17.5 0, 17.5 17.5, 0 17.5, 0 0)))"))
        layer2 = QgsVectorLayer("MultiPolygon?crs=EPSG:5254&field=ada:string&field=parsel:string&field=nizam:string&field=kat:integer", "ayrik_layer", "memory")
        layer2.dataProvider().addFeatures([f2])
        results2, _ = ComplianceEngine.evaluate_parcels(list(layer2.getFeatures()))
        self.assertEqual(results2[0].durum, "TEVHID_ZORUNLU")
        self.assertIn("Derinlik", results2[0].aciklama)

    def test_capacity_engine_kdkca_and_zero_emsal(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:5254&field=uipfonksiyon:string&field=kaks:double&field=taks:double", "test_plan", "memory")
        pr = layer.dataProvider()

        f1 = QgsFeature(layer.fields())
        f1["uipfonksiyon"] = "KONUT_ALANI"
        f1["kaks"] = 1.5
        f1["taks"] = 0.3
        f1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))"))

        f2 = QgsFeature(layer.fields())
        f2["uipfonksiyon"] = "KONUT_DISI_KENTSEL_CALISMA_ALANI"
        f2["kaks"] = 1.0
        f2["taks"] = 0.5
        f2.setGeometry(QgsGeometry.fromWkt("POLYGON((200 0, 300 0, 300 100, 200 100, 200 0))"))

        pr.addFeatures([f1, f2])

        items, summary = PlanCapacityEngine.estimate_capacity(
            plan_features=list(layer.getFeatures()),
            default_kaks=1.0,
            default_taks=0.3,
            avg_unit_m2=100.0,
            household_size=3.0,
        )
        self.assertGreater(summary.toplam_kapasite_nufusu, 0)
        self.assertEqual(summary.toplam_konut_alani_m2, 10000.0)
        self.assertEqual(summary.toplam_insaat_m2, 15000.0)

    def test_parking_and_shelter_engines_exclude_kdkca(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:5254&field=uipfonksiyon:string&field=kaks:double", "test_p", "memory")
        feat = QgsFeature(layer.fields())
        feat["uipfonksiyon"] = "KONUT_DISI_KENTSEL_CALISMA_ALANI"
        feat["kaks"] = 1.0
        feat.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 100 0, 100 10, 0 10, 0 0))"))
        layer.dataProvider().addFeatures([feat])

        p_items, p_sum = ParkingEngine.evaluate_parking_balance(list(layer.getFeatures()))
        self.assertGreater(p_sum.toplam_otopark_ihtiyaci_arac, 0)

        s_items, s_sum = ShelterEngine.evaluate_shelter_requirements(list(layer.getFeatures()))
        self.assertEqual(len(s_items), 1)

    def test_risk_synthesis_engine_turkish_severity(self):
        layer = QgsVectorLayer("Point?crs=EPSG:5254&field=hasar:string&field=yil:int&field=kat:int", "buildings", "memory")
        pr = layer.dataProvider()
        for attrs in [["AGIR HASARLI", 1970, 5], ["HASARSIZ", 2015, 4], ["HAFIF HASARLI", 2005, 3]]:
            feat = QgsFeature(layer.fields())
            feat.setAttributes(attrs)
            feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(10, 10)))
            pr.addFeatures([feat])

        results, summary = UrbanTransformationRiskEngine.evaluate_risk(list(layer.getFeatures()))
        self.assertEqual(len(results), 3)

    def test_zoning_certificate_engine_7221_compliance(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:5254&field=uipfonksiyon:string&field=yencok:string&field=nizam:string", "parcel", "memory")
        feat = QgsFeature(layer.fields())
        feat["uipfonksiyon"] = "KONUT_ALANI"
        feat["yencok"] = "SERBEST"
        feat["nizam"] = "AYRIK"
        feat.setGeometry(QgsGeometry.fromWkt("POLYGON((500000 4500000, 500050 4500000, 500050 4500050, 500000 4500050, 500000 4500000))"))

        cert = ZoningCertificateEngine.generate_certificate(
            parcel_feature=feat,
            default_kat="",
        )
        self.assertIn("Plandan Belirlenecektir (7221 s. Kanun)", cert.yencok)
        self.assertIn("Sağa (Y)", cert.html_content)
        self.assertIn("Yukarı (X)", cert.html_content)
        self.assertIn("<html lang=\"tr\">", cert.html_content)

    def test_plan_revision_diff_engine(self):
        c_layer = QgsVectorLayer("Polygon?crs=EPSG:5254&field=uipfonksiyon:string", "current", "memory")
        r_layer = QgsVectorLayer("Polygon?crs=EPSG:5254&field=uipfonksiyon:string", "revised", "memory")

        cf = QgsFeature(c_layer.fields())
        cf["uipfonksiyon"] = "PARK"
        cf.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 50 0, 50 50, 0 50, 0 0))"))
        c_layer.dataProvider().addFeatures([cf])

        rf1 = QgsFeature(r_layer.fields())
        rf1["uipfonksiyon"] = "KONUT_ALANI"
        rf1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 50 0, 50 50, 0 50, 0 0))"))

        rf2 = QgsFeature(r_layer.fields())
        rf2["uipfonksiyon"] = "PARK"
        rf2.setGeometry(QgsGeometry.fromWkt("POLYGON((60 0, 120 0, 120 50, 60 50, 60 0))"))
        r_layer.dataProvider().addFeatures([rf1, rf2])

        diff_features, summary = PlanRevisionDiffEngine.evaluate_revision(
            current_features=list(c_layer.getFeatures()),
            revised_features=list(r_layer.getFeatures()),
            service_radius_m=500.0,
        )
        self.assertTrue(summary.madde_26_uygunlugu)
        removed_amenities = [f for f in diff_features if f.degisim_turu == "DONATI_KALDIRILDI"]
        self.assertTrue(len(removed_amenities) > 0)
        self.assertTrue(removed_amenities[0].esdeger_alan_uygun)


if __name__ == "__main__":
    unittest.main()
