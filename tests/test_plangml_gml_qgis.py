"""PlanGML GML import (M series) from schema-conformant synthetic GML files.

No real e-Plan GML sample is available; the files below follow the MUIP 1.1.6
XSD element names, a GML 2 ``coordinates`` and a GML 3 ``posList`` encoding.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer  # noqa: E402

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from planx_mpyy_studio.core.plangml_gml import detect_level, import_plangml_gml, load_document  # noqa: E402

HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n'
GML2 = HEADER + """<FeatureCollection xmlns="www.csb.gov.tr" xmlns:gml="http://www.opengis.net/gml"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="www.csb.gov.tr muip.V.1.1.6.xsd">
 <gml:boundedBy><gml:null>unknown</gml:null></gml:boundedBy>
 <featureMember>
  <Konut>
   <GeometryProperty><gml:MultiPolygon srsName="EPSG:5254"><gml:polygonMember><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing>
    <gml:coordinates>500000,4250000 500200,4250000 500200,4250200 500000,4250200 500000,4250000</gml:coordinates>
   </gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></gml:polygonMember></gml:MultiPolygon></GeometryProperty>
   <YeniKod>112002</YeniKod><Adi>Konut Adası</Adi><Taks>0,35</Taks><KatAdedi>4</KatAdedi>
   <YapiDuzeni>Ayrik</YapiDuzeni><KonutTip>YerlesikKonut</KonutTip><EskiAlan>x</EskiAlan>
  </Konut>
 </featureMember>
 <featureMember>
  <Konut>
   <GeometryProperty><gml:MultiPolygon srsName="EPSG:5254"><gml:polygonMember><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing>
    <gml:coordinates>500400,4250000 500600,4250000 500600,4250200 500400,4250200 500400,4250000</gml:coordinates>
   </gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></gml:polygonMember></gml:MultiPolygon></GeometryProperty>
   <KonutTip>SosyalKonut</KonutTip>
  </Konut>
 </featureMember>
 <featureMember>
  <DigerCokluNokta>
   <GeometryProperty><gml:MultiPoint srsName="EPSG:5254"><gml:pointMember><gml:Point><gml:coordinates>500100,4250100</gml:coordinates></gml:Point></gml:pointMember>
    <gml:pointMember><gml:Point><gml:coordinates>500150,4250150</gml:coordinates></gml:Point></gml:pointMember></gml:MultiPoint></GeometryProperty>
   <Aciklama>Kuyu</Aciklama>
  </DigerCokluNokta>
 </featureMember>
 <featureMember><Konut><Adi>geometrisiz</Adi></Konut></featureMember>
 <featureMember><BilinmeyenTip/></featureMember>
</FeatureCollection>
"""
GML3 = HEADER + """<FeatureCollection xmlns="www.csb.gov.tr" xmlns:gml="http://www.opengis.net/gml/3.2">
 <featureMember>
  <Konut>
   <GeometryProperty><gml:MultiSurface srsName="urn:ogc:def:crs:EPSG::5254"><gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing>
    <gml:posList>500000 4250000 500200 4250000 500200 4250200 500000 4250200 500000 4250000</gml:posList>
   </gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface></GeometryProperty>
   <YeniKod>112002</YeniKod><KonutTip>GelismeKonut</KonutTip>
  </Konut>
 </featureMember>
 <featureMember>
  <YapiYaklasmaMes>
   <GeometryProperty><gml:Point srsName="urn:ogc:def:crs:EPSG::5254"><gml:pos>500050 4250050</gml:pos></gml:Point></GeometryProperty>
  </YapiYaklasmaMes>
 </featureMember>
</FeatureCollection>
"""


class PlanGMLFileImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def write(self, name, text):
        path = Path(self.tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_gml2_muip_with_schema_location(self):
        source = self.write("plan.gml", GML2)
        self.assertEqual(detect_level(load_document(source))[0], "MUIP")
        output = Path(self.tmp.name) / "muip.gpkg"
        _, summary, report = import_plangml_gml(source, output)
        self.assertEqual(summary["kademe"], "MUIP")
        self.assertEqual(summary["bilinmeyen_ogeler"], {"BilinmeyenTip": 1})
        rows = {r["tip"]: r for r in report}
        self.assertEqual((rows["Konut"]["adet"], rows["Konut"]["aktarilan"], rows["Konut"]["geometri_sorunu"]), (3, 2, 1))
        self.assertEqual(rows["Konut"]["kod_listesi_disi"], 1)
        self.assertEqual(rows["Konut"]["bilinmeyen_oznitelik"], "EskiAlan")
        self.assertEqual(rows["DigerCokluNokta"]["aktarilan"], 1)
        with sqlite3.connect(output) as con:
            self.assertEqual(
                con.execute('SELECT YeniKod, Adi, Taks, KatAdedi, YapiDuzeni, KonutTip FROM "Konut" ORDER BY fid').fetchall(),
                [(112002, "Konut Adası", 0.35, 4, "Ayrik", "YerlesikKonut"), (None, None, None, None, None, "SosyalKonut")],
            )
            self.assertEqual(con.execute("SELECT count(*) FROM layer_styles WHERE f_table_name='Konut'").fetchone()[0], 1)
        layer = QgsVectorLayer(f"{output}|layername=DigerCokluNokta", "n", "ogr")
        self.assertEqual(layer.crs().authid(), "EPSG:5254")
        point = next(layer.getFeatures()).geometry()
        self.assertEqual(point.asWkt(0), "MultiPoint ((500100 4250100),(500150 4250150))")
        konut = QgsVectorLayer(f"{output}|layername=Konut", "k", "ogr")
        area = sum(f.geometry().area() for f in konut.getFeatures())
        self.assertAlmostEqual(area, 80000, delta=1)

    def test_gml3_detected_by_names_and_reprojected(self):
        source = self.write("plan3.gml", GML3)
        level, reason = detect_level(load_document(source))
        self.assertEqual(level, "MUIP")
        self.assertIn("YeniKod", reason)
        output = Path(self.tmp.name) / "gml3.gpkg"
        _, summary, report = import_plangml_gml(source, output, crs=QgsCoordinateReferenceSystem("EPSG:5254"))
        self.assertEqual({r["tip"]: r["aktarilan"] for r in report}, {"Konut": 1, "YapiYaklasmaMes": 1})
        with sqlite3.connect(output) as con:
            self.assertEqual(con.execute('SELECT KonutTip FROM "Konut"').fetchall(), [("GelismeKonut",)])
        layer = QgsVectorLayer(f"{output}|layername=Konut", "k", "ogr")
        box = layer.extent()
        self.assertAlmostEqual(box.xMinimum(), 500000, delta=0.01)
        self.assertAlmostEqual(box.yMaximum(), 4250200, delta=0.01)

    def test_explicit_schema_without_matching_types_is_refused(self):
        source = self.write("plan3.gml", GML3)
        with self.assertRaises(ValueError):
            import_plangml_gml(source, Path(self.tmp.name) / "x.gpkg", level="MCDP100")
        with self.assertRaises(ValueError):
            load_document(self.write("bozuk.gml", "<FeatureCollection>"))


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
