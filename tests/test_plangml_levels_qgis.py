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
    Qgis,
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

from planx_mpyy_studio.core.plangml_catalog import catalog  # noqa: E402
from planx_mpyy_studio.core.plangml_level_conversion import convert_workspace  # noqa: E402
from planx_mpyy_studio.core.plangml_import import audit_plangml_workspace  # noqa: E402
from planx_mpyy_studio.core.plangml_workspace import (  # noqa: E402
    PLUGIN_ROOT,
    SLD_DIR,
    all_levels,
    apply_building_notation,
    apply_eplan_symbology,
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


def typed_layer(level, type_name, rows):
    feature_type = next(t for t in all_levels()[level]["feature_types"] if t["name"] == type_name)
    kinds = {"double": "double", "int": "integer", "long": "integer"}
    fields = "&".join(f"field={f['name']}:{kinds.get(f['type'], 'string')}" for f in feature_type["fields"])
    layer = QgsVectorLayer(f"{feature_type['geometry']}?crs=EPSG:5254&{fields}", type_name, "memory")
    for wkt, values in rows:
        add(layer, values, wkt)
    return layer


def walk_layers(symbol, into_sub=True):
    """Symbol layers depth first; ``into_sub`` False keeps the containers (marker lines, fills)."""
    for index in range(symbol.symbolLayerCount()):
        layer = symbol.symbolLayer(index)
        if not into_sub or layer.subSymbol() is None or layer.layerType() in ("SimpleFill", "SimpleLine", "SimpleMarker"):
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
        # Every Turizm Alanı sub-type now resolves to a real Ek-1e page or a documented synthesis
        # (Yayla Turizmi has no page at all, s.57 GTB/GTA/GTT short-code convention -> "YT"):
        # confirm all six land on a RasterMarker, none fall back to the "?" placeholder.
        layer = typed_layer("CDP", "TurizmAlani", [])
        self.assertTrue(apply_eplan_symbology(layer, "CDP", "TurizmAlani"))
        self.assertIsNone(layer.customProperty("mpyy/missing_symbols"))
        for label in ("EKOTURIZM", "GUNUBIRLIK_TURIZM", "KIS_TURIZMI", "SAGLIK_TURIZMI", "YAYLA_TURIZMI"):
            rule = next(r for r in layer.renderer().rootRule().children() if r.label() == label)
            kinds = [layer_.layerType() for layer_ in walk_layers(rule.symbol())]
            self.assertIn("RasterMarker", kinds, label)

        # The "unpublished SVG, no catalog symbol registered yet -> stays a visible gap, never a
        # silent SvgMarker" mechanism itself: simulate a not-yet-catalogued placeholder by making
        # the lookup miss for just this call, independent of which items are already fixed today.
        from unittest.mock import patch

        with patch("planx_mpyy_studio.core.plangml_catalog.symbol_for_svg", return_value=None):
            layer2 = typed_layer("CDP", "TurizmAlani", [])
            self.assertTrue(apply_eplan_symbology(layer2, "CDP", "TurizmAlani"))
            self.assertEqual(layer2.customProperty("mpyy/missing_symbols"), "TaramaSembol SVG")
            rule = next(r for r in layer2.renderer().rootRule().children() if r.label() == "YAYLA_TURIZMI")
            kinds = [layer_.layerType() for layer_ in walk_layers(rule.symbol())]
            self.assertNotIn("SvgMarker", kinds)
            self.assertIn("FontMarker", kinds)

    def test_ministry_glyphs_on_codepoint_3f_are_drawn_unless_the_catalog_overrides_them(self):
        # The Ministry's SLD points an *installed* pictogram font at codepoint 0x003f ('?') in a
        # handful of rules. That is not their "we never mapped this glyph" marker: rendering
        # MUIP_10_1/UIP_10_1/uygulama_imar_07_2/UIP_10_2 against the Ek-1e catalog at 600 dpi
        # shows an ordinary designed slot there (İl Sınırı's dash-dot on MUIP_10_1, the arboretum
        # tree group on UIP_10_1, a "KSM" box, a beach parasol). So the catalog is what decides:
        # where it registers a symbol for that exact family+codepoint the symbol replaces the
        # glyph (Kumsal-Plaj s.97, Kongre ve Sergi Merkezi Alanı s.128); everywhere else the
        # glyph is drawn as it stands, never greyed out.
        naive = ("MUIP", "IlSiniri", "MUIP_IL_SINIRI")
        along = ("MUIP", "KentinGGBolgeSiniri", "MUIP_KENTIN_GG_BOLGE_SINIRI")
        arboretum = ("MUIP", "AcikYesilAlan", "ARBORETUM_BOTANIK_PARKI")
        for level, type_name, label in (naive, along, arboretum):
            with self.subTest(type_name=type_name):
                layer = typed_layer(level, type_name, [])
                apply_eplan_symbology(layer, level, type_name)
                self.assertIsNone(layer.customProperty("mpyy/missing_symbols"))
                rule = next(r for r in layer.renderer().rootRule().children() if r.label() == label)
                fonts = [l for l in walk_layers(rule.symbol()) if l.layerType() == "FontMarker"]
                # Kentin GG Bölge Sınırı carries a "U" mark beside its "?" band, so only assert
                # that the 0x003f slot itself is drawn in the family's own black, not greyed.
                self.assertIn("?", {l.character() for l in fonts}, label)
                self.assertTrue(all(l.color().name() == "#000000" for l in fonts), label)
                self.assertNotIn("RasterMarker", [l.layerType() for l in walk_layers(rule.symbol())], label)

        kumsal = typed_layer("UIP", "KumsalPlaj", [])
        apply_eplan_symbology(kumsal, "UIP", "KumsalPlaj")
        self.assertIsNone(kumsal.customProperty("mpyy/missing_symbols"))
        kinds = [l.layerType() for l in walk_layers(kumsal.renderer().rootRule().children()[0].symbol())]
        self.assertIn("RasterMarker", kinds)

        sosyal = typed_layer("UIP", "SosyalKulturelAlan", [])
        apply_eplan_symbology(sosyal, "UIP", "SosyalKulturelAlan")
        rule = next(r for r in sosyal.renderer().rootRule().children() if r.label() == "KONGRE_SERGI_MERKEZI_ALANI")
        self.assertIn("RasterMarker", [l.layerType() for l in walk_layers(rule.symbol())])
        # OZEL_SOSYAL_TESIS_ALANI, once a genuine gap, is now a documented synthesis too (s.124's
        # own SOSYAL_TESIS_ALANI pictogram + "Ö", matching the catalog's own s.122/125 convention).
        rule = next(r for r in sosyal.renderer().rootRule().children() if r.label() == "OZEL_SOSYAL_TESIS_ALANI")
        self.assertIn("RasterMarker", [l.layerType() for l in walk_layers(rule.symbol())])
        self.assertIsNone(sosyal.customProperty("mpyy/missing_symbols"))

        # The "installed font, literal '?' codepoint, no catalog symbol yet -> stays a visible gap"
        # mechanism itself, independent of which specific glyphs are already fixed today.
        from unittest.mock import patch

        with patch("planx_mpyy_studio.core.plangml_catalog.symbol_for_glyph", return_value=None):
            sosyal2 = typed_layer("UIP", "SosyalKulturelAlan", [])
            apply_eplan_symbology(sosyal2, "UIP", "SosyalKulturelAlan")
            self.assertIn("Intelli Eplan", sosyal2.customProperty("mpyy/missing_symbols") or "")

    def test_road_width_is_written_in_a_circle(self):
        line = "LINESTRING(500000 4250000, 500200 4250000)"
        layer = typed_layer("UIP", "Yolorta", [(line, {"YolGenisligi": 12.5}), (line, {"YolGenisligi": 10.0}), (line, {})])
        self.assertTrue(apply_eplan_symbology(layer, "UIP", "Yolorta"))
        self.assertTrue(layer.labelsEnabled())
        self.assertEqual(evaluate(layer, layer.labeling().settings().fieldName), ["12<u>50</u>", "10", None])
        rule = layer.renderer().rootRule().children()[0]
        self.assertEqual((rule.minimumScale(), rule.filterExpression()), (2000, '"YolGenisligi" > 0'))

    def test_missing_private_symbol_font_is_marked_not_substituted(self):
        # Every "Intelli Eplan" glyph this SLD needs is now covered by a catalog substitute (the
        # Özel Sosyal/Kültürel/Açık-Kapalı Spor Tesis Alanı synthesis badges) -- exercise the
        # underlying "family not shipped, no catalog symbol -> flagged, DejaVu fallback, not a
        # silently wrong glyph" mechanism directly, independent of which glyphs are fixed today.
        from unittest.mock import patch

        layer = typed_layer("UIP", "SosyalKulturelAlan", [])
        with patch("planx_mpyy_studio.core.plangml_catalog.symbol_for_glyph", return_value=None):
            apply_eplan_symbology(layer, "UIP", "SosyalKulturelAlan")
        self.assertIn("Intelli Eplan", layer.customProperty("mpyy/missing_symbols") or "")

    def test_catalog_symbols_replace_unpublished_assets(self):
        symbols = json.loads((PLUGIN_ROOT / "styles" / "plangml_katalog" / "symbols.json").read_text(encoding="utf-8"))["symbols"]
        for key, entry in symbols.items():
            data = (PLUGIN_ROOT / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"], key)
        cases = (
            ("UIP", "AfetHizmetAlani", "AfetLojistikAlani"),  # TaramaSembol SVG, s.136
            ("UIP", "AcikYesilAlan", "MILLET_BAHCESI"),  # Intelli Eplan glyph, s.137
            ("CDP", "SitAlanlari", "KENTSEL_ARKEOLOJIK_SIT"),  # s.83
            # M series (MUIP/MNIP and the other scale variants): the same "unshipped Intelli Eplan
            # glyph, catalog has the real item" gap one scale down -- s.120 YÜKSEK ÖĞRETİM ALANI
            # for Intelli Eplan#O, and the s.125 "Ö" convention over the sibling "STK" pictogram
            # for Intelli Eplan#V.
            ("MUIP", "EgitimTesisAlani", "YUKSEK_OGRETIM_TESIS_KAMPUS_ALANI"),
            ("MUIP", "SosyalKulturelAlan", "OZEL_SOSYAL_KULTUREL_TESIS_ALANI"),
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

    def test_marker_lines_keep_the_sld_interval_and_size(self):
        # QGIS imports every SLD graphic inside a stroke or fill without its size and with interval 0,
        # so the symbols pile up on the line's first vertex.
        power = typed_layer("CDP", "EnerjiNakilHatti", [])
        self.assertTrue(apply_eplan_symbology(power, "CDP", "EnerjiNakilHatti"))
        symbol = power.renderer().rootRule().children()[0].symbol()
        line = next(l for l in walk_layers(symbol, into_sub=False) if l.layerType() == "MarkerLine")
        # s.182: the SLD declares uom="...units/metre" here, but that is the Ministry's own
        # mislabelling -- these are millimetre design values (a real 15m mark spacing on a power
        # line symbol would be absurd), corrected by _fix_metre_uom_units/_unit_name.
        self.assertEqual((line.interval(), int(line.intervalUnit())), (15, int(Qgis.RenderUnit.Millimeters)))
        marker = line.subSymbol().symbolLayer(0)
        self.assertEqual((marker.size(), int(marker.sizeUnit())), (15, int(Qgis.RenderUnit.Millimeters)))
        for level in ("UIP", "NIP", "CDP", "MUIP", "MNIP"):
            for type_name in [t["name"] for t in all_levels()[level]["feature_types"] if t["geometry"]]:
                layer = typed_layer(level, type_name, [])
                if not apply_eplan_symbology(layer, level, type_name):
                    continue
                renderer = layer.renderer()
                rules = renderer.rootRule().children() if renderer.type() == "RuleRenderer" else []
                for rule in rules:
                    for item in walk_layers(rule.symbol()) if rule.symbol() else []:
                        if item.layerType() == "MarkerLine":
                            self.assertGreater(item.interval(), 0, f"{level}/{type_name}/{rule.label()}")
                del layer  # 500+ styled layers in one process otherwise pile up

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

    def test_administrative_boundary_lines_use_catalog_dot_and_tick_patterns(self):
        # Ek-1e s.12: dash - perpendicular tick - open circle - tick, repeating; catalog mm, not
        # the SLD's own GraphicStroke glyph.
        ulke = typed_layer("UIP", "UlkeSiniri", [])
        apply_eplan_symbology(ulke, "UIP", "UlkeSiniri")
        rule = next(r for r in ulke.renderer().rootRule().children() if r.label() == "UIP_ULKE_SINIRI")
        layers = list(walk_layers(rule.symbol()))
        outline = next(l for l in layers if l.layerType() == "SimpleLine")
        self.assertEqual(round(outline.width(), 2), 1.2)
        self.assertEqual([round(v, 2) for v in outline.customDashVector()], [10.0, 3.0])
        markers = [l for l in layers if l.layerType() == "SimpleMarker"]
        ticks = [l for l in markers if l.shape() == Qgis.MarkerShape.Line]
        circles = [l for l in markers if l.shape() == Qgis.MarkerShape.Circle]
        self.assertEqual(len(ticks), 2)
        self.assertEqual(len(circles), 1)
        self.assertEqual(round(circles[0].size(), 2), 3.0)
        self.assertEqual(circles[0].color().alpha(), 0)  # içi boş daire

        # s.12: dash - 1mm ara - tek 1mm nokta, simetrik.
        il = typed_layer("UIP", "IlSiniri", [])
        apply_eplan_symbology(il, "UIP", "IlSiniri")
        rule = next(r for r in il.renderer().rootRule().children() if r.label() == "UIP_IL_SINIRI")
        layers = list(walk_layers(rule.symbol()))
        outline = next(l for l in layers if l.layerType() == "SimpleLine")
        self.assertEqual(round(outline.width(), 2), 1.0)
        self.assertEqual([round(v, 2) for v in outline.customDashVector()], [10.0, 3.0])
        dots = [l for l in layers if l.layerType() == "SimpleMarker"]
        self.assertEqual([round(d.size(), 2) for d in dots], [1.0])

        # s.13: dash - 2mm ara - iki bitişik 1mm nokta (aralık katalogda verilmez, 0 alınır).
        ilce = typed_layer("UIP", "IlceSiniri", [])
        apply_eplan_symbology(ilce, "UIP", "IlceSiniri")
        rule = next(r for r in ilce.renderer().rootRule().children() if r.label() == "UIP_ILCE_SINIRI")
        dots = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual([round(d.size(), 2) for d in dots], [1.0, 1.0])

        # s.13: çizginin iki ucunda 2mm 'kelepçe' noktası + 1mm aralıklı iki küçük nokta öbeği.
        belediye = typed_layer("UIP", "BelediyeSiniri", [])
        apply_eplan_symbology(belediye, "UIP", "BelediyeSiniri")
        rule = next(r for r in belediye.renderer().rootRule().children() if r.label() == "UIP_BELEDIYE_SINIRI")
        dots = sorted(round(l.size(), 2) for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(dots, [1.0, 1.0, 2.0, 2.0])

    def test_planning_boundary_lines_use_catalog_circle_chains(self):
        # s.15: PlanSiniri has four SLD rules (Nitelik=Plan/Revizyon/Ilave/IlaveRevizyon); the
        # catalog gives one boundary for all of them, so every rule must be redrawn.
        plan = typed_layer("UIP", "PlanSiniri", [(SQUARE, {"Nitelik": "Plan"})])
        apply_eplan_symbology(plan, "UIP", "PlanSiniri")
        rules = plan.renderer().rootRule().children()
        self.assertEqual({r.label() for r in rules if r.label() != "Kodu girilmemiş / resmî gösterimi yok"},
                          {"PLAN", "REVIZYON", "ILAVE", "ILAVE_REVIZYON"})
        circles = [l for l in walk_layers(rules[0].symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(len(circles), 1)
        self.assertEqual(round(circles[0].size(), 2), 5.0)
        self.assertEqual(circles[0].color().alpha(), 0)  # içi boş daire

        # s.16: 1cm çizgi, 1mm ara, 0.6mm nokta.
        degisiklik = typed_layer("UIP", "PlanDegisiklikSiniri", [])
        apply_eplan_symbology(degisiklik, "UIP", "PlanDegisiklikSiniri")
        rule = next(r for r in degisiklik.renderer().rootRule().children() if r.label() == "UIP_PLAN_DEGISIKLIK_SINIRI")
        outline = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine")
        self.assertEqual(round(outline.width(), 2), 0.6)
        dot = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(round(dot.size(), 2), 0.6)

        # s.16: 1 dolu 1 boş daire sırayla, çizgisiz.
        etap = typed_layer("UIP", "EtaplamaSiniri", [])
        apply_eplan_symbology(etap, "UIP", "EtaplamaSiniri")
        rule = next(r for r in etap.renderer().rootRule().children() if r.label() == "UIP_ETAPLAMA_SINIRI")
        circles = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(sorted(c.color().alpha() for c in circles), [0, 255])  # biri boş, biri dolu
        self.assertFalse(any(l.layerType() == "SimpleLine" for l in walk_layers(rule.symbol())))

        # s.20: 4mm dolu daire, aralarında 2.5mm bağlantı çizgisi.
        ozel = typed_layer("UIP", "OzelProjeAlanSiniri", [])
        apply_eplan_symbology(ozel, "UIP", "OzelProjeAlanSiniri")
        rule = next(r for r in ozel.renderer().rootRule().children() if r.label() == "UIP_OZEL_PROJE_ALAN_SINIRI")
        self.assertTrue(any(l.layerType() == "SimpleLine" for l in walk_layers(rule.symbol())))
        circle = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(circle.color().alpha(), 255)  # içi dolu

    def test_special_law_area_borders_use_catalog_gear_chains(self):
        # s.21-23: IlanEdilenClsmaAlan carries four distinct "dişli" borders on one SLD type;
        # each rule must get its own gear count, and the connecting dash must sit in the gap next
        # to the gear cluster, not underneath it (it draws from boundary position 0).
        layer = typed_layer("UIP", "IlanEdilenClsmaAlan", [
            (SQUARE, {"IlanEdilenCalismaTip": "TeknolojiGelistirmeBolgesi"}),
        ])
        apply_eplan_symbology(layer, "UIP", "IlanEdilenClsmaAlan")
        rules = {r.label(): r.symbol() for r in layer.renderer().rootRule().children()}
        self.assertEqual(
            {r for r in rules if r != "Kodu girilmemiş / resmî gösterimi yok"},
            {"TEKNOLOJI_GELISTIRME_BOLGESI", "SERBEST_BOLGE", "OSB", "ENDUSTRI_BOLGESI"},
        )

        def gears(label):
            return [l for l in walk_layers(rules[label]) if l.layerType() == "RasterMarker"]

        self.assertEqual(len(gears("TEKNOLOJI_GELISTIRME_BOLGESI")), 3)  # s.21: 3 adet dişli
        self.assertEqual(len(gears("OSB")), 1)  # s.22: 1 adet dişli
        self.assertEqual(len(gears("ENDUSTRI_BOLGESI")), 2)  # s.23: 2 adet dişli
        self.assertEqual(len(gears("SERBEST_BOLGE")), 2)  # s.21: içi boş + içi dolu, sırayla

        dash = next(l for l in walk_layers(rules["TEKNOLOJI_GELISTIRME_BOLGESI"]) if l.layerType() == "SimpleLine")
        self.assertEqual(round(dash.width(), 2), 0.3)
        on, off = dash.customDashVector()
        self.assertEqual(round(on, 2), 7.0)  # 7 mm çizgi
        # the dash's own "on" run starts at boundary position 0: the gear cluster (3 gears, 7 mm
        # each, 1 mm apart = 23 mm wide) must be offset past it (dash_mm + gap_mm), not centred
        # at half its own width -- which would sit it on top of the dash instead of the gap.
        marker_line = next(
            l.subSymbol().symbolLayer(0)
            for l in rules["TEKNOLOJI_GELISTIRME_BOLGESI"].symbolLayers()
            if l.layerType() == "GeometryGenerator" and l.subSymbol().symbolLayer(0).layerType() == "MarkerLine"
        )
        cluster_width = 3 * 7 + 2 * 1
        self.assertGreaterEqual(marker_line.offsetAlongLine() - cluster_width / 2, on)

    def test_plain_dashed_and_concentric_ring_borders(self):
        # s.17-18: MudahaleSiniri's three rules share one plain dash-gap border, no marks.
        layer = typed_layer("NIP", "MudahaleSiniri", [
            (SQUARE, {"MudahaleSiniriTip": "SagliklastirmaAlanSiniri"}),
        ])
        apply_eplan_symbology(layer, "NIP", "MudahaleSiniri")
        rule = next(r for r in layer.renderer().rootRule().children() if r.label() == "SAGLIKLASTIRMA_ALAN_SINIRI")
        lines = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine"]
        self.assertEqual(len(lines), 1)  # katalog çizgisi SLD'nin "K/Y/S" rozetini değiştirmez
        self.assertEqual(round(lines[0].width(), 2), 0.5)
        self.assertEqual([round(v, 2) for v in lines[0].customDashVector()], [10.0, 2.0])

        # s.19: İmar Hakkı Aktarım Alanı Sınırı -- two concentric hollow red circles per mark.
        imar = typed_layer("UIP", "ImarHakkiAktarimSiniri", [])
        apply_eplan_symbology(imar, "UIP", "ImarHakkiAktarimSiniri")
        rule = next(r for r in imar.renderer().rootRule().children() if r.label() == "UIP_IMAR_HAK_AKTARIM_SINIR")
        circles = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(sorted(round(c.size(), 2) for c in circles), [3.0, 5.5])
        self.assertTrue(all(c.color().alpha() == 0 for c in circles))  # boş daireler
        self.assertTrue(all(c.strokeColor().name() == "#ff0000" for c in circles))

    def test_square_cross_triangle_and_compound_borders(self):
        # s.25: Boğaziçi Etkilenme Bölgesi Sınırı -- a cluster of 3 filled squares, no gap either
        # side of the connecting dash.
        bogazici = typed_layer("UIP", "BogaziciSinirlari", [
            (SQUARE, {"BogaziciBolgeTip": "BogaziciEtkilenmeBolgeSiniri"}),
        ])
        apply_eplan_symbology(bogazici, "UIP", "BogaziciSinirlari")
        rule = next(r for r in bogazici.renderer().rootRule().children() if r.label() == "BOGAZICI_ETKILENME_BOLGE_SINIRI")
        squares = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(len(squares), 3)
        self.assertTrue(all(s.shape() == Qgis.MarkerShape.Square for s in squares))

        # s.26: Gecekondu Önleme Bölgesi Sınırı -- upright "artı" marks (not the AYB "çarpı" X).
        gecekondu = typed_layer("UIP", "DonusumKonutAlanlari", [
            (SQUARE, {"DonusumTip": "GecekonduOnlemeBolgesi"}),
        ])
        apply_eplan_symbology(gecekondu, "UIP", "DonusumKonutAlanlari")
        rule = next(r for r in gecekondu.renderer().rootRule().children() if r.label() == "GECEKONDU_ONLEME_BOLGESI")
        cross = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(cross.shape(), Qgis.MarkerShape.Cross)

        # s.34: Diğer Özel Kanunlarla Belirlenen Alan Sınırları -- 2 filled + 1 hollow triangle.
        diger = typed_layer("UIP", "DigerOzelSinir", [])
        apply_eplan_symbology(diger, "UIP", "DigerOzelSinir")
        rule = next(r for r in diger.renderer().rootRule().children() if r.label() == "UIP_DIGER_OZEL_SINIR")
        triangles = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(sorted(t.color().alpha() for t in triangles), [0, 255, 255])

        # s.27-28: Sahil Şeridi / Kıyı Kenar Çizgisi are LINE features -- a mark on every vertex,
        # not at a fixed interval (the catalog: "tespit edilen koordinat noktaları").
        sahil = typed_layer("UIP", "SahilSeridi", [])
        apply_eplan_symbology(sahil, "UIP", "SahilSeridi")
        rule = next(r for r in sahil.renderer().rootRule().children() if r.label() == "UIP_SAHIL_SERIDI")
        vertex_marker = next(l for l in walk_layers(rule.symbol(), into_sub=False) if l.layerType() == "MarkerLine")
        self.assertEqual(vertex_marker.placements(), Qgis.MarkerLinePlacement.Vertex)

    def test_border_text_repeats_along_the_perimeter_per_rule(self):
        # s.24: "Uygun aralıklarla sınır üzerine AYB yazılacak" -- a repeating label around the
        # polygon boundary, filtered to just the AYB rule (not every AskeriYasakBolge feature).
        ayb = typed_layer("UIP", "AskeriYasakBolge", [])
        apply_eplan_symbology(ayb, "UIP", "AskeriYasakBolge")
        self.assertTrue(ayb.labelsEnabled())
        labeling = ayb.labeling()
        rules = labeling.rootRule().children()
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].settings().fieldName, "'AYB'")
        self.assertEqual(rules[0].settings().placement, Qgis.LabelPlacement.PerimeterCurved)
        askeri_rule = next(r for r in ayb.renderer().rootRule().children() if r.label() == "UIP_ASKERI_YASAK_BOLGE")
        self.assertEqual(rules[0].filterExpression(), askeri_rule.filterExpression())

        # s.29-30: three different rules of the same SLD type, three different words -- only the
        # matching rule's features get their word.
        donusum = typed_layer("NIP", "KentselDonusumSinirlari", [
            (SQUARE, {"KentselDonusumSinirlariTip": "RezervYapiAlanSiniri"}),
        ])
        apply_eplan_symbology(donusum, "NIP", "KentselDonusumSinirlari")
        words = {r.description(): r.settings().fieldName for r in donusum.labeling().rootRule().children()}
        self.assertEqual(words, {
            "RISKLI_ALAN_SINIRI": "'RA'",
            "REZERV_YAPI_ALAN_SINIRI": "'RYA'",
            "YENILEME_ALAN_SINIRI": "'YENİLEME'",
        })

    def test_protected_site_borders_use_catalog_dot_hatch_and_letters(self):
        # s.31-33: SitAlanlari carries 13 rules on one SLD type; 1/2/3. Derece Doğal Sit Alanı
        # (only these three) also get a 45-degree hatch band along the whole boundary.
        layer = typed_layer("UIP", "SitAlanlari", [
            (SQUARE, {"SitTip": "1DereceDogalSit"}),
        ])
        apply_eplan_symbology(layer, "UIP", "SitAlanlari")
        d1 = next(r for r in layer.renderer().rootRule().children() if r.label() == "1_DERECE_DOGAL_SIT")
        dots = [l for l in walk_layers(d1.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(len(dots), 1)
        self.assertTrue(all(d.color().alpha() == 255 for d in dots))  # dolu daire
        # dash outline + the hash tick's own sub-line = 2 plain lines; without a hatch there is
        # only the dash outline.
        d1_lines = [l for l in walk_layers(d1.symbol()) if l.layerType() == "SimpleLine"]
        self.assertEqual(len(d1_lines), 2)

        a1 = next(r for r in layer.renderer().rootRule().children() if r.label() == "1_DERECE_ARKEOLOJIK_SIT")
        a1_lines = [l for l in walk_layers(a1.symbol()) if l.layerType() == "SimpleLine"]
        self.assertEqual(len(a1_lines), 1)

        words = {r.description(): r.settings().fieldName for r in layer.labeling().rootRule().children()}
        self.assertEqual(words["1_DERECE_DOGAL_SIT"], "'D1'")
        self.assertEqual(words["KENTSEL_SIT"], "'KS'")  # sembol kutusu "K" yazsa da metin "KS"

        # s.84: Sit Etkileşim Geçiş Alanı Sınırı -- hollow 5.5mm ring around a filled 3mm dot.
        seg = next(r for r in layer.renderer().rootRule().children() if r.label() == "SIT_ETKILESIMLI_ALANI")
        circles = sorted(
            (round(c.size(), 2), c.color().alpha())
            for c in walk_layers(seg.symbol()) if c.layerType() == "SimpleMarker"
        )
        self.assertEqual(circles, [(3.0, 255), (5.5, 0)])

    def test_protection_corridors_and_plain_lines(self):
        # s.111: KorumaKusaklari carries many "X every 7mm + YKK/BHK/..." rules on one SLD type.
        kusak = typed_layer("UIP", "KorumaKusaklari", [
            (SQUARE, {"KusakTip": "KarayoluKorumaKusagi"}),
        ])
        apply_eplan_symbology(kusak, "UIP", "KorumaKusaklari")
        rule = next(r for r in kusak.renderer().rootRule().children() if r.label() == "KARAYOLU_KORUMA_KUSAGI")
        cross = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(cross.shape(), Qgis.MarkerShape.Cross2)  # çarpı, artı değil
        words = {r.description(): r.settings().fieldName for r in kusak.labeling().rootRule().children()}
        self.assertEqual(words["KARAYOLU_KORUMA_KUSAGI"], "'YKK'")

        # s.77-79: TescilliAlan -- a plain solid line, no dash, no marks.
        tescilli = typed_layer("UIP", "TescilliAlan", [
            (SQUARE, {"TescilTip": "TescilliBina"}),
        ])
        apply_eplan_symbology(tescilli, "UIP", "TescilliAlan")
        rule = next(r for r in tescilli.renderer().rootRule().children() if r.label() == "TESCILLI_BINA")
        lines = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine"]
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines[0].useCustomDashPattern())
        self.assertEqual(round(lines[0].width(), 2), 0.4)

        # s.109-110: ManiaPlani and HavaalaniHavaKoridoru are LINE features handled through
        # "vectors", not "borders" (no boundary($geometry) generator involved).
        mania = typed_layer("UIP", "ManiaPlani", [])
        apply_eplan_symbology(mania, "UIP", "ManiaPlani")
        rule = next(r for r in mania.renderer().rootRule().children() if r.label() == "UIP_MANIA_PLANI")
        lines = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine"]
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines[0].useCustomDashPattern())
        self.assertEqual(round(lines[0].width(), 2), 0.4)

        koridor = typed_layer("UIP", "HavaalaniHavaKoridoru", [])
        apply_eplan_symbology(koridor, "UIP", "HavaalaniHavaKoridoru")
        rule = next(r for r in koridor.renderer().rootRule().children() if r.label() == "UIP_HAVAALANI_HAVA_KORIDORU")
        tick = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(tick.shape(), Qgis.MarkerShape.Line)

    def test_catalog_overrides_target_the_schemas_real_geometry_type(self):
        # The Ek-1e catalog's own "GEOMETRİ TİPİ" column is occasionally wrong (Mania Planı Alanı
        # and Havaalanı Hava Koridoru say "ÇOKLU ÇİZGİ" but plangml_schema.json has them as
        # MultiPolygon) -- a "borders" entry keyed to a LineString type, or a line-only "vectors"
        # kind keyed to a polygon type, would silently never fire. Catch that for every entry.
        geometry = {
            (level, ft["name"]): ft["geometry"]
            for level in ("UIP", "NIP", "CDP")
            for ft in level_schema(level)["feature_types"]
        }
        decisions = catalog()["decisions"]
        for key in decisions.get("borders", {}):
            if key.startswith("_") or key == "note":
                continue
            level, type_name, label = key.split("/", 2)
            geom = geometry.get((level, type_name))
            if geom is not None:
                self.assertEqual(geom, "MultiPolygon", key)
        line_kinds = {
            "line_solid", "line_dashed", "vertex_chain", "road", "ladder",
            "line_ties", "line_overlay", "line_marked", "line_tick_tie", "line_circles",
            "line_ticks",
        }
        for key, spec in decisions.get("vectors", {}).items():
            if key.startswith("_") or key == "note" or not isinstance(spec, dict):
                continue
            if spec.get("kind") not in line_kinds:
                continue
            level, type_name, label = key.split("/", 2)
            geom = geometry.get((level, type_name))
            if geom is not None:
                self.assertEqual(geom, "LineString", key)

    def test_nature_conservation_borders_use_mixed_fill_clusters(self):
        # s.88: ÖÇK Bölgesi Hassas Alan A/B/C -- catalog "biri dolu" cluster: hollow-filled-hollow.
        ock = typed_layer("UIP", "OckHassasAlan", [
            (SQUARE, {"HassaslikDerecesi": "OckBolgesiHassasAlanA"}),
        ])
        apply_eplan_symbology(ock, "UIP", "OckHassasAlan")
        rule = next(r for r in ock.renderer().rootRule().children() if r.label() == "OCK_BOLGESI_HASSAS_ALAN_A")
        fills = [c.color().alpha() for c in walk_layers(rule.symbol()) if c.layerType() == "SimpleMarker"]
        self.assertEqual(fills, [0, 255, 0])

    def test_water_protection_borders_use_dotted_circle_clusters(self):
        # s.102: İçme ve Kullanma Suyu Mutlak Koruma Alanı -- 4 touching hollow circles, each
        # with a small filled dot inside (the outer ring must be hollow or the inner dot would be
        # invisible against a filled circle of the same colour).
        icme = typed_layer("UIP", "IcmeKullanmaSuyuKoruma", [
            (SQUARE, {"KorumaDerecesi": "MutlakKorumaAlani"}),
        ])
        apply_eplan_symbology(icme, "UIP", "IcmeKullanmaSuyuKoruma")
        rule = next(r for r in icme.renderer().rootRule().children() if r.label() == "MUTLAK_KORUMA_ALANI")
        marks = [c for c in walk_layers(rule.symbol()) if c.layerType() == "SimpleMarker"]
        sizes = sorted(round(m.size(), 2) for m in marks)
        self.assertEqual(sizes, [0.5, 0.5, 0.5, 0.5, 2.0, 2.0, 2.0, 2.0])  # 4 iç nokta + 4 dış daire
        outer = [m for m in marks if round(m.size(), 2) == 2.0]
        self.assertTrue(all(m.color().alpha() == 0 for m in outer))  # dış daireler boş

        # s.104: Sulak Alan -- catalog's wavy line is approximated as a plain dash (documented).
        sulak = typed_layer("UIP", "SulakAlan", [
            (SQUARE, {"SulakTip": "SulakAlanSiniri"}),
        ])
        apply_eplan_symbology(sulak, "UIP", "SulakAlan")
        rule = next(r for r in sulak.renderer().rootRule().children() if r.label() == "SULAK_ALAN_SINIRI")
        dots = [c for c in walk_layers(rule.symbol()) if c.layerType() == "SimpleMarker"]
        self.assertEqual(len(dots), 2)

    def test_transport_lines_use_catalog_overlay_tie_and_marked_patterns(self):
        # s.150: 3. Derece Yol (ÇDP only) -- a thin yellow line centred on a wide black one.
        road = typed_layer("CDP", "Yolorta", [])
        apply_eplan_symbology(road, "CDP", "Yolorta")
        rule = next(r for r in road.renderer().rootRule().children() if r.label() == "3_DERECE_YOL")
        widths = sorted(round(l.width(), 2) for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine")
        self.assertEqual(widths, [0.4, 1.0])

        # s.157: Demiryolu -- 2x5mm dolu dikdörtgen ties on a plain rail; Hızlı Tren Hattı
        # alternates dolu/boş and adds a double side rail 1mm/2mm out.
        rail = typed_layer("UIP", "Demiryolu", [])
        apply_eplan_symbology(rail, "UIP", "Demiryolu")
        demiryolu = next(r for r in rail.renderer().rootRule().children() if r.label() == "DEMIRYOLU")
        ties = [l for l in walk_layers(demiryolu.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(len(ties), 1)  # every tie dolu -> one marker layer for all of them
        self.assertEqual(round(ties[0].strokeWidth(), 2), 2.0)

        hizli = next(r for r in rail.renderer().rootRule().children() if r.label() == "HIZLI_TREN_HAT")
        offsets = sorted(
            round(l.offset(), 2) for l in walk_layers(hizli.symbol(), into_sub=False)
            if l.layerType() == "SimpleLine" and l.offset()
        )
        self.assertEqual(offsets, [-2.0, -1.0, 1.0, 2.0])  # s.157: çift düz çizgi, 1mm/2mm uzaklıkta

        # s.169-171: Toplu Taşıma Hattı -- Raylı (tek yan çizgi), Havai Hat (dolu dikdörtgen),
        # Havaray (boş dikdörtgen) on the same SLD type.
        toplu = typed_layer("UIP", "TopluTasimaHatti", [])
        apply_eplan_symbology(toplu, "UIP", "TopluTasimaHatti")
        havai = next(r for r in toplu.renderer().rootRule().children() if r.label() == "HAVAI_HAT")
        havaray = next(r for r in toplu.renderer().rootRule().children() if r.label() == "HAVARAY")
        havai_box = next(l for l in walk_layers(havai.symbol()) if l.layerType() == "SimpleMarker" and l.angle() == 90)
        havaray_box = next(l for l in walk_layers(havaray.symbol()) if l.layerType() == "SimpleMarker" and l.angle() == 90)
        self.assertEqual(havai_box.color().alpha(), 255)  # içi dolu
        self.assertEqual(havaray_box.color().alpha(), 0)  # içi boş

        # s.180-181: İletim Hattı -- Boru Hattı (düz), Doğalgaz Boru Hattı (kesikli) share the
        # eşkenar üçgen marker; Cebri Boru Hattı is a plain line with no marker at all.
        iletim = typed_layer("UIP", "IletimHatti", [])
        apply_eplan_symbology(iletim, "UIP", "IletimHatti")
        boru = next(r for r in iletim.renderer().rootRule().children() if r.label() == "BORU_HATTI")
        dogalgaz = next(r for r in iletim.renderer().rootRule().children() if r.label() == "DOGALGAZ_BORU_HATTI")
        cebri = next(r for r in iletim.renderer().rootRule().children() if r.label() == "CEBRI_BORU_HATTI")
        self.assertFalse(next(l for l in walk_layers(boru.symbol(), into_sub=False) if l.layerType() == "SimpleLine").useCustomDashPattern())
        self.assertTrue(next(l for l in walk_layers(dogalgaz.symbol(), into_sub=False) if l.layerType() == "SimpleLine").useCustomDashPattern())
        self.assertEqual([l.layerType() for l in walk_layers(cebri.symbol())], ["SimpleLine"])

        # s.175: Tünel Etki Alanı -- a çarpı-marked border plus a repeating "TEA" perimeter label.
        tunel = typed_layer("UIP", "TunelEtkiAlani", [])
        apply_eplan_symbology(tunel, "UIP", "TunelEtkiAlani")
        cross = next(l for l in walk_layers(tunel.renderer().rootRule().children()[0].symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(cross.shape(), Qgis.MarkerShape.Cross2)
        self.assertEqual(tunel.labeling().rootRule().children()[0].settings().fieldName, "'TEA'")

        # s.183: Soğutma Suyu Alma Hattı -- chevrons plus a repeating "S" *along the line itself*
        # (Qgis.LabelPlacement.Line), not the polygon perimeter placement borders use.
        sogutma = typed_layer("UIP", "SogutmaSuyuAlmaHatti", [])
        apply_eplan_symbology(sogutma, "UIP", "SogutmaSuyuAlmaHatti")
        rule = sogutma.labeling().rootRule().children()[0]
        self.assertEqual(rule.settings().fieldName, "'S'")
        self.assertEqual(rule.settings().placement, Qgis.LabelPlacement.Line)

        # s.184: İçme Suyu Ana İletim Hattı -- hollow circles tangent to (not centred on) the line.
        icmesu = typed_layer("UIP", "IcmesuAnaHat", [])
        apply_eplan_symbology(icmesu, "UIP", "IcmesuAnaHat")
        circle = next(l for l in walk_layers(icmesu.renderer().rootRule().children()[0].symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(circle.color().alpha(), 0)  # içi boş
        self.assertEqual(round(circle.offset().y(), 2), round(circle.size() / 2, 2))  # teğet

        # s.185-186: Atıksu Sistemi -- Ana Kollektörü'nün dolu oku, Derin Deniz Deşarj'ın boş üçgeni.
        atiksu = typed_layer("UIP", "AtiksuSistemi", [])
        apply_eplan_symbology(atiksu, "UIP", "AtiksuSistemi")
        kollektor = next(r for r in atiksu.renderer().rootRule().children() if r.label() == "ATIKSU_ANA_KOLLEKTORU")
        desarj = next(r for r in atiksu.renderer().rootRule().children() if r.label() == "ATIKSU_DERIN_DENIZ_DESARJ_HATTI")
        ok = next(l for l in walk_layers(kollektor.symbol()) if l.layerType() == "SimpleMarker")
        ucgen = next(l for l in walk_layers(desarj.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(ok.shape(), Qgis.MarkerShape.ArrowHeadFilled)
        self.assertEqual(ok.color().alpha(), 255)
        self.assertEqual(ucgen.shape(), Qgis.MarkerShape.EquilateralTriangle)
        self.assertEqual(ucgen.color().alpha(), 0)  # içi boş

    def test_disaster_hazard_borders_use_dashed_and_open_triangle_patterns(self):
        # s.189/144: Kentsel Risk Alanı / Yapı Yasaklı Alan -- a plain black dash, no marks.
        afet = typed_layer("UIP", "AfetTehlikeliAlanlar", [
            (SQUARE, {"AfetTip": "KentselRiskAlani"}),
        ])
        apply_eplan_symbology(afet, "UIP", "AfetTehlikeliAlanlar")
        rule = next(r for r in afet.renderer().rootRule().children() if r.label() == "KENTSEL_RISK_ALANI")
        line = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine")
        self.assertTrue(line.useCustomDashPattern())
        self.assertEqual(round(line.color().redF() * 255), 0)

        # s.189: Tsunami Riskli Alan -- a single hollow triangle every 7mm, red, on a continuous
        # (not dashed) base line -- the 'tabanı eksik üçgen' is approximated by a hollow triangle
        # whose own base coincides with, and is hidden by, that continuous line.
        tsunami = typed_layer("UIP", "AfetTehlikeliAlanlar", [
            (SQUARE, {"AfetTip": "TsunamiRiskliAlan"}),
        ])
        apply_eplan_symbology(tsunami, "UIP", "AfetTehlikeliAlanlar")
        rule = next(r for r in tsunami.renderer().rootRule().children() if r.label() == "TSUNAMI_RISKLI_ALAN")
        line = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleLine")
        self.assertFalse(line.useCustomDashPattern())  # taban çizgisi kesintisiz
        triangle = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(triangle.shape(), Qgis.MarkerShape.EquilateralTriangle)
        self.assertEqual(triangle.color().alpha(), 0)
        self.assertEqual(round(triangle.color().redF()), 0)  # boş üçgenin dolgusu yok, kontur kırmızı
        self.assertEqual(triangle.strokeColor().name(), "#ff0000")

        # s.145: Afete Maruz Bölge (NİP only) -- a 3-triangle cluster, 1mm apart, then a gap.
        maruz = typed_layer("NIP", "AfetTehlikeliAlanlar", [
            (SQUARE, {"AfetTip": "AfeteMaruzBolge"}),
        ])
        apply_eplan_symbology(maruz, "NIP", "AfetTehlikeliAlanlar")
        rule = next(r for r in maruz.renderer().rootRule().children() if r.label() == "AFETE_MARUZ_BOLGE")
        triangles = [l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker"]
        self.assertEqual(len(triangles), 3)

        # s.153: Bisiklet Yolu -- a LINE feature with a perpendicular tick every 3mm, no rectangle.
        bike = typed_layer("UIP", "BisikletYolu", [])
        apply_eplan_symbology(bike, "UIP", "BisikletYolu")
        rule = bike.renderer().rootRule().children()[0]
        tick = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(tick.shape(), Qgis.MarkerShape.Line)
        self.assertEqual([l.layerType() for l in walk_layers(rule.symbol())], ["SimpleLine", "SimpleMarker"])

        # s.99: Sulama Hattı -- catalog says ÇİZGİ but schema has it as MultiPolygon (same bug
        # class as ManiaPlani/HavaalaniHavaKoridoru), so it must be a "borders" entry, not "vectors".
        sulama = typed_layer("UIP", "SulamaHatti", [])
        apply_eplan_symbology(sulama, "UIP", "SulamaHatti")
        rule = sulama.renderer().rootRule().children()[0]
        tick = next(l for l in walk_layers(rule.symbol()) if l.layerType() == "SimpleMarker")
        self.assertEqual(tick.shape(), Qgis.MarkerShape.Line)

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
