"""Hat etiketleri and kademe dönüşümü on real layers and GeoPackages."""

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
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
    SLD_DIR,
    all_levels,
    apply_building_notation,
    apply_eplan_symbology,
    apply_line_labels,
    installed_font_families,
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


def typed_layer(level, type_name, rows):
    feature_type = next(t for t in all_levels()[level]["feature_types"] if t["name"] == type_name)
    kinds = {"double": "double", "int": "integer", "long": "integer"}
    fields = "&".join(f"field={f['name']}:{kinds.get(f['type'], 'string')}" for f in feature_type["fields"])
    layer = QgsVectorLayer(f"{feature_type['geometry']}?crs=EPSG:5254&{fields}", type_name, "memory")
    for wkt, values in rows:
        add(layer, values, wkt)
    return layer


def walk_layers(symbol):
    """Symbol layers depth first, sub-symbols included."""
    for index in range(symbol.symbolLayerCount()):
        layer = symbol.symbolLayer(index)
        if layer.subSymbol() is None or layer.layerType() in ("SimpleFill", "SimpleLine", "SimpleMarker"):
            yield layer
        else:
            yield from walk_layers(layer.subSymbol())


def evaluate(layer, expression):
    context = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    parsed = QgsExpression(expression)
    values = []
    for feature in layer.getFeatures():
        context.setFeature(feature)
        values.append(parsed.evaluate(context))
        assert not parsed.hasEvalError(), parsed.evalErrorString()
    return values


class SymbologyGapTests(unittest.TestCase):
    def test_ministry_tile_names_with_a_stray_m_resolve_to_shipped_tiles(self):
        images = json.loads((SLD_DIR / "mapping.json").read_text(encoding="utf-8"))["images"]
        self.assertEqual(images["absent_from_source"], [])
        self.assertEqual(images["repaired_names"]["b01b0c76-7204-40mm40mm-aa56-b3cba23b1f44.png"],
                         "b01b0c76-7204-4040-aa56-b3cba23b1f44.png")
        for repaired in images["repaired_names"].values():
            self.assertTrue((PLUGIN_ROOT / "resources" / repaired).is_file(), repaired)
        text = (SLD_DIR / "UIP" / "SosyalKulturelAlan.sld").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"mpyy-tarama:[^\"]*m[^\"]*\.png", text), [])
        self.assertIn("<Label>YENİLEME</Label>", (SLD_DIR / "NIP" / "KentselDonusumSinirlari.sld").read_text(encoding="utf-8"))

    def test_single_rule_styles_are_applied(self):
        for level, type_name in (("UIP", "ManiaSiniri"), ("CDP", "StratejikKarar"), ("CDP", "Planlama_AltBolge")):
            with self.subTest(type_name=type_name):
                layer = typed_layer(level, type_name, [])
                self.assertTrue(apply_eplan_symbology(layer, level, type_name))
                self.assertEqual(layer.customProperty("mpyy/symbology"), f"e-Plan SLD: {level}/{type_name}")

    def test_unpublished_svg_without_a_catalog_symbol_is_marked(self):
        # Ekoturizm.svg (ÇDP) has no counterpart in the Ek-1e catalog: the gap stays visible.
        layer = typed_layer("CDP", "TurizmAlani", [])
        self.assertTrue(apply_eplan_symbology(layer, "CDP", "TurizmAlani"))
        self.assertEqual(layer.customProperty("mpyy/missing_symbols"), "TaramaSembol SVG")
        rule = next(r for r in layer.renderer().rootRule().children() if r.label() == "EKOTURIZM")
        kinds = [layer_.layerType() for layer_ in walk_layers(rule.symbol())]
        self.assertNotIn("SvgMarker", kinds)
        self.assertIn("FontMarker", kinds)

    def test_road_width_is_written_in_a_circle(self):
        line = "LINESTRING(500000 4250000, 500200 4250000)"
        layer = typed_layer("UIP", "Yolorta", [(line, {"YolGenisligi": 12.5}), (line, {"YolGenisligi": 10.0}), (line, {})])
        self.assertTrue(apply_eplan_symbology(layer, "UIP", "Yolorta"))
        self.assertTrue(layer.labelsEnabled())
        self.assertEqual(evaluate(layer, layer.labeling().settings().fieldName), ["12<u>50</u>", "10", None])
        rule = layer.renderer().rootRule().children()[0]
        self.assertEqual((rule.minimumScale(), rule.filterExpression()), (2000, '"YolGenisligi" > 0'))

    def test_missing_private_symbol_font_is_marked_not_substituted(self):
        # OZEL_*_TESIS_ALANI glyphs of Intelli Eplan have no catalog item; SOKAK_HAYVANLARI now uses the catalog symbol.
        layer = typed_layer("UIP", "SosyalKulturelAlan", [])
        apply_eplan_symbology(layer, "UIP", "SosyalKulturelAlan")
        if "Intelli Eplan" in installed_font_families():
            self.skipTest("Intelli Eplan is installed on this machine")
        self.assertEqual(layer.customProperty("mpyy/missing_symbols"), "Intelli Eplan")

    def test_catalog_symbols_replace_unpublished_assets(self):
        symbols = json.loads((PLUGIN_ROOT / "styles" / "plangml_katalog" / "symbols.json").read_text(encoding="utf-8"))["symbols"]
        for key, entry in symbols.items():
            data = (PLUGIN_ROOT / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"], key)
        cases = (
            ("UIP", "AfetHizmetAlani", "AfetLojistikAlani"),  # TaramaSembol SVG, s.136
            ("UIP", "AcikYesilAlan", "MILLET_BAHCESI"),  # Intelli Eplan glyph, s.137
            ("CDP", "SitAlanlari", "KENTSEL_ARKEOLOJIK_SIT"),  # s.83
        )
        for level, type_name, label in cases:
            with self.subTest(type_name=type_name):
                layer = typed_layer(level, type_name, [])
                self.assertTrue(apply_eplan_symbology(layer, level, type_name))
                self.assertIsNone(layer.customProperty("mpyy/missing_symbols"))
                rule = next(r for r in layer.renderer().rootRule().children() if r.label() == label)
                rasters = [l for l in walk_layers(rule.symbol()) if l.layerType() == "RasterMarker"]
                self.assertTrue(rasters and rasters[0].path().startswith("base64:iVBOR"))
        single = typed_layer("CDP", "StratejikKarar", [])
        apply_eplan_symbology(single, "CDP", "StratejikKarar")
        self.assertIsNone(single.customProperty("mpyy/missing_symbols"))

    def test_pedestrian_path_width_is_written_like_a_road(self):
        line = "LINESTRING(500000 4250000, 500200 4250000)"
        layer = typed_layer("UIP", "YayaYolu", [(line, {"Genislik": 3.5})])
        self.assertTrue(apply_eplan_symbology(layer, "UIP", "YayaYolu"))
        self.assertTrue(layer.labelsEnabled())  # Ek-1e s.155
        self.assertEqual(evaluate(layer, layer.labeling().settings().fieldName), ["3<u>50</u>"])
        labels = [rule.label() for rule in layer.renderer().rootRule().children()]
        self.assertIn("UIP_YAYA_YOLU", labels)
        self.assertIn("Yol genişliği", labels)

    def test_catalog_measurements_colours_and_hatches(self):
        merkez = typed_layer("CDP", "IdariMerkez", [])
        apply_eplan_symbology(merkez, "CDP", "IdariMerkez")
        il = next(r for r in merkez.renderer().rootRule().children() if r.label() == "IL").symbol()
        self.assertEqual([(l.size(), l.color().name()) for l in walk_layers(il)], [(80, "#ffff00"), (50, "#000000")])  # s.35
        self.assertIsNone(merkez.customProperty("mpyy/missing_symbols"))
        road = typed_layer("CDP", "Yolorta", [])
        apply_eplan_symbology(road, "CDP", "Yolorta")
        otoyol = next(r for r in road.renderer().rootRule().children() if r.label() == "ERISME_KONTROLLU_KARAYOLU_OTOYOL").symbol()
        self.assertEqual([round(l.width(), 2) for l in walk_layers(otoyol)], [3.6, 3.0, 1.0])  # s.147
        island = typed_layer("NIP", "YapayAda", [])
        apply_eplan_symbology(island, "NIP", "YapayAda")
        fills = [l.color().getRgb()[:3] for l in walk_layers(island.renderer().rootRule().children()[0].symbol()) if l.layerType() == "SimpleFill"]
        self.assertIn((225, 225, 225), fills)  # s.100
        protected = typed_layer("UIP", "AraziKullanimiDevamEttirilerekKorunacakAlanlar", [])
        apply_eplan_symbology(protected, "UIP", "AraziKullanimiDevamEttirilerekKorunacakAlanlar")
        rules = {r.label(): [l.layerType() for l in walk_layers(r.symbol())] for r in protected.renderer().rootRule().children()}
        self.assertEqual(rules["EkolojikOnemeSahipAlan"], ["RasterMarker"])  # thorn motif of the point pattern
        self.assertNotIn("SimpleFill", rules["EkolojikOnemeSahipAlan"])  # s.90: no ground colour
        self.assertEqual(rules["Dogal Ekolojik Korunacak Alan"].count("SimpleFill"), 1)
        self.assertIn("katalog", " ".join(protected.customPropertyKeys()))

    def test_m_series_borrows_current_level_styles_only_for_matching_rules(self):
        mapping = json.loads((SLD_DIR / "mapping.json").read_text(encoding="utf-8"))["levels"]
        mera = mapping["MCDP100"]["types"]["MeraCayir"]
        self.assertEqual((mera["style_match"], mera["borrowed_from"]), ("current_level", "CDP/Mera"))
        green = mapping["MCDP100"]["types"]["AcikYesilAlan"]
        self.assertTrue(any(r["dropped"] and r["borrow_reasons"] == ["kod yok: MilletBahcesi"] for r in green["rules"]))
        self.assertIn("<ogc:PropertyName>YesilTip</ogc:PropertyName>", (SLD_DIR / "MCDP100" / "AcikYesilAlan.sld").read_text(encoding="utf-8"))
        self.assertIn("ManiaSiniri", mapping["MCDP100"]["missing_styles"])  # polygon here, a line at CDP
        layer = typed_layer("MCDP100", "MeraCayir", [])
        self.assertTrue(apply_eplan_symbology(layer, "MCDP100", "MeraCayir"))

    def test_building_notation_follows_the_detail_catalog(self):
        square = "MULTIPOLYGON(((500000 4250000,500090 4250000,500090 4250090,500000 4250090,500000 4250000)))"
        layer = typed_layer("UIP", "Konut", [
            (square, {"Taks": 0.3, "TaksTip": "Deger", "EmsalKaks": 1.2, "EmsalKaksTip": "Deger", "KatAdedi": 4,
                      "YapiDuzeni": "Ayrik", "OnBahceMesafesi": 5.0, "YanBahceMesafesi": 3.0,
                      "YapiYuksekligi": 12.5, "YapiYuksekligiTip": "Deger"}),
            (square, {"TaksTip": "Serbest", "EmsalKaks": 1.5, "EmsalKaksTip": "Deger", "KatAdedi": 5,
                      "YapiDuzeni": "Ikiz", "YapiYuksekligiTip": "Serbest", "SembolPoz": "500050 4250030"}),
        ])
        self.assertEqual(apply_building_notation(layer), 9)
        self.assertEqual(apply_building_notation(typed_layer("UIP", "SitAlanlari", [])), 0)
        rules = {r.description(): r for r in layer.labeling().rootRule().children()}

        def labels(name):
            rule = rules[name]
            shown = evaluate(layer, rule.filterExpression()) if rule.filterExpression() else [True, True]
            return [value if shown[i] else None for i, value in enumerate(evaluate(layer, rule.settings().fieldName))]

        # Ek-1e pages 39-43: nizam letter left, kat adedi right, ön bahçe top, yan bahçe bottom.
        self.assertEqual(labels("Yapı düzeni (A-, B-, BL-)"), ["A-", None])  # no catalog letter for İkiz
        self.assertEqual(labels("Kat adedi"), ["4", "5"])
        self.assertEqual(labels("Ön bahçe mesafesi"), ["5", None])
        self.assertEqual(labels("Yan bahçe mesafesi"), ["3", None])
        self.assertEqual(labels("TAKS"), ["0.30", None])
        self.assertEqual(labels("KAKS"), ["1.20", None])
        self.assertEqual(labels("Emsal ve yençok"), ["Y<sub>ençok</sub> = 12.50 m", "E = 1.50"])
        left = rules["Yapı düzeni dairesi"].settings()
        right = rules["TAKS/KAKS dairesi"].settings()
        self.assertLess(left.xOffset, 0)
        self.assertGreater(right.xOffset, 0)
        self.assertEqual(rules["TAKS"].settings().format().size(), 5)
        anchors = evaluate(layer, rules["TAKS"].settings().geometryGenerator)
        self.assertEqual((anchors[0].asPoint().x(), anchors[1].asWkt()), (500045, "Point (500050 4250030)"))
        self.assertEqual(rules["TAKS"].minimumScale(), 2000)


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
