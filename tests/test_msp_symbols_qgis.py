"""EK-1b's drawing annex reaches QGIS as the symbols it actually draws.

``styles/msp_catalog.json`` now carries what the Ministry's drawing annex states:
a mark's shape, whether it is filled or outlined, its measured diameter, the
nested discs of a bullseye, and a hatch's axis.  This suite is the half that the
pure file cannot hold -- that the *renderer* turns those into real QGIS symbol
layers rather than into a plausible-looking circle.  Every assertion here reads a
symbol layer back out of a layer's categorized renderer, exactly as QGIS will
paint it, so the gap it closes is the one that shipped a catalogue nothing drew.

Two things it deliberately does not do.  It does not compare pixels: QGIS's own
drawing is not the plugin's to test, and the pixel proof is the owner's desktop.
And it does not restate the catalogue's numbers -- every expected value is read
from ``core.msp_catalog``, so a re-extraction moves one place and this follows.

The last test is the reason the file exists at all: a marker's offset, size and
stroke width all live in a *unit*, and a length written in printed millimetres
while the layer declares metres is off by the map scale -- small enough to look
like a rendering quirk and large enough to bury three of MSP-014's four
triangles under the fourth.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.PyQt.QtCore import Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402
from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsLinePatternFillSymbolLayer,
    QgsRasterMarkerSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbolLayer,
    QgsVectorLayer,
)

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()

from planx_mpyy_studio.core.msp_catalog import (  # noqa: E402
    MARKER_SHAPES,
    decode_rows,
)
from planx_mpyy_studio.core.msp_styler import (  # noqa: E402
    FALLBACK_RGB,
    HATCH_ANGLE_DEFAULT,
    MM_TO_GROUND,
    MSPStylerEngine,
)

#: The fields the engine requires and the two the class rule binds.  The layer is
#: named so that it is not one of the catalogue's own layer names, which makes the
#: engine offer every code of that geometry -- so one layer holds all sixteen
#: point codes and one holds every area code.
FIELDS = (
    "field=msp_kodu:string&field=yerlesme_kademesi:string&field=yerlesme_yogunlugu:string"
)

#: Five of the sixteen point codes, one per ``Qgis.MarkerShape`` EK-1b's SEMBOL
#: vocabulary uses, with the shape each must come back as.  Written out rather
#: than derived from ``MARKER_SHAPES``, because deriving it would make the test
#: agree with the mapping whatever the mapping said: the point is that these rows
#: are drawn as *these* shapes, and MSP-019 versus MSP-005 is the pair that says
#: the five-pointed star and the eight-pointed one are not each other.
NATIVE_SHAPES = {
    "MSP-005": "AsteriskFill",
    "MSP-008": "Circle",
    "MSP-016": "Square",
    "MSP-019": "Star",
    "MSP-023": "Hexagon",
}

#: The three codes whose glyph the Ministry draws and QGIS has no shape for, so
#: the annex's own cropped artwork is drawn instead.
PICTOGRAM_ROWS = ("MSP-011", "MSP-012", "MSP-013")


def point_layer():
    layer = QgsVectorLayer(f"Point?crs=EPSG:5254&{FIELDS}", "msp_nokta_test", "memory")
    assert layer.isValid(), "bellek katmanı açılamadı"
    MSPStylerEngine().apply(layer)
    return layer


def area_layer():
    layer = QgsVectorLayer(f"Polygon?crs=EPSG:5254&{FIELDS}", "msp_alan_test", "memory")
    assert layer.isValid(), "bellek katmanı açılamadı"
    MSPStylerEngine().apply(layer)
    return layer


def symbol_of(layer, code):
    """A copy of the symbol the renderer draws for one annex code.

    Copied rather than borrowed, and the reason is worth stating: the list
    ``categories()`` returns owns the category wrappers and a category owns its
    symbol, so a symbol read out of a list that has already gone out of scope is a
    dangling pointer.  Reading it does not raise -- it kills the interpreter with a
    heap fail-fast (``0xC0000409``) part-way through the suite, which looks like a
    broken test runner rather than a broken assertion.  ``clone()`` is evaluated
    while the list is still alive and hands back a symbol of our own.
    """

    for category in layer.renderer().categories():
        if category.value() == code:
            return category.symbol().clone()
    raise AssertionError(f"{code}: kategorik çizicide yok")


def fallback_symbol(layer):
    for category in layer.renderer().categories():
        if category.value() is None:
            return category.symbol().clone()
    raise AssertionError("eşleşmeyen kod sembolü yok")


def symbol_layers(symbol):
    """Copies of the symbol's layers.

    Copied for the same reason :func:`symbol_of` copies the symbol, one level
    down: ``symbolLayer(index)`` lends a layer that the symbol frees, so in
    ``symbol_layers(symbol_of(...))[0]`` the owner is a temporary and the layer
    read afterwards is dead.  A dead layer does not raise -- it answers with the
    defaults of a freshly built one (``MarkerShape.Circle``, an invalid black
    ``QColor``), so the test fails on a *value* that looks like a real regression
    and moves between runs as the collector runs at different moments.  Cloned,
    every value read below belongs to a layer this module owns.
    """

    return [symbol.symbolLayer(index).clone() for index in range(symbol.symbolLayerCount())]


def expression_for(layer, code, property_id):
    """The expression bound to one data-defined property of one code, as text.

    As *text*, read on the same line as the layer that owns it, and that is not
    tidiness: a ``QgsProperty`` handed out by ``dataDefinedProperties().property()``
    points back into the symbol layer, so a value read after that layer's last
    reference has gone is an access violation (``0xC0000005``) on QGIS 4 -- the
    interpreter dies with no Python traceback and the test that happened to run
    next is blamed.  Holding the layer and the collection in locals and returning
    the string keeps the whole read inside their lifetime, on both runtimes.
    """

    symbol = symbol_of(layer, code)
    for index in range(symbol.symbolLayerCount()):
        value = symbol.symbolLayer(index).dataDefinedProperties().property(property_id)
        if value is not None:
            return str(value.expressionString())
    return None


class MSPSymbolTests(unittest.TestCase):
    def setUp(self):
        self.rows = {row.id: row for row in decode_rows()}
        self.points = point_layer()
        self.areas = area_layer()

    def test_every_shape_name_the_dictionary_holds_exists_on_this_runtime(self):
        """The vocabulary is looked up on the runtime, so a missing name must be loud.

        ``MARKER_SHAPES`` stores ``Qgis.MarkerShape`` *names* rather than the enum
        members precisely so that a shape one runtime has and the other does not
        fails here, in the test, instead of at import time for every user of the
        plugin.  This is that test, and it runs on both runtimes.
        """
        resolved = {}
        # Keyed by the *catalogue's* name, not by the QGIS one: keying the other
        # way round would collapse two catalogue names onto one entry and hide the
        # very case the distinctness check below is for.
        for name, attribute in sorted(MARKER_SHAPES.items()):
            with self.subTest(sekil=name, shape=attribute):
                member = getattr(Qgis.MarkerShape, attribute, None)
                self.assertIsNotNone(member, f"Qgis.MarkerShape.{attribute} bu sürümde yok")
                resolved[name] = member
        # Every name is a different shape: a mapping that pointed two rows at one
        # member would draw two symbols the annex draws differently as one.
        self.assertEqual(len(set(resolved.values())), len(resolved))
        self.assertEqual(len(resolved), len(MARKER_SHAPES))

    def test_a_point_code_is_drawn_as_the_shape_the_annex_draws_it(self):
        """The bug this file was written for: every point used to be a circle."""
        for code, shape in sorted(NATIVE_SHAPES.items()):
            with self.subTest(code=code):
                layers = symbol_layers(symbol_of(self.points, code))
                self.assertEqual(len(layers), 1)
                self.assertIsInstance(layers[0], QgsSimpleMarkerSymbolLayer)
                self.assertEqual(layers[0].shape(), getattr(Qgis.MarkerShape, shape))
                self.assertEqual(self.rows[code].sembol_sekli and
                                 MARKER_SHAPES[self.rows[code].sembol_sekli], shape)

    def test_no_point_code_is_left_as_the_unmatched_grey_marker(self):
        """Sixteen codes, and not one of them drawn as the unmatched default.

        That default is the state the report came from: every point code drew the
        same neutral circle, which looks like a working renderer and tells a
        planner nothing.  The fallback itself stays -- an unknown code still has to
        be drawn visibly -- so this is an inequality per code, and it is an
        equality against nothing: the whole symbol is compared, not one channel,
        because MSP-008's disc is legitimately at that size and shape.
        """
        default = fallback_symbol(self.points)
        self.assertEqual(symbol_layers(default)[0].color(), QColor(*FALLBACK_RGB))
        self.assertEqual(symbol_layers(default)[0].shape(), Qgis.MarkerShape.Circle)
        point_codes = [row.id for row in self.rows.values() if "POINT" in row.geometry_kinds]
        self.assertEqual(len(point_codes), 16)
        for code in point_codes:
            with self.subTest(code=code):
                symbol = symbol_of(self.points, code)
                self.assertGreaterEqual(len(symbol_layers(symbol)), 1)
                self.assertNotEqual(symbol.dump(), default.dump())

    def test_the_three_pictograms_are_the_annexs_own_cropped_artwork(self):
        """Nothing is redrawn: the raster marker carries EK-1b's own crop."""
        for code in PICTOGRAM_ROWS:
            with self.subTest(code=code):
                layers = symbol_layers(symbol_of(self.points, code))
                self.assertEqual(len(layers), 1)
                self.assertIsInstance(layers[0], QgsRasterMarkerSymbolLayer)
                self.assertTrue(layers[0].path().startswith("base64:"))
                # The crop's own proportions are kept, so the anchor is not
                # stretched into a square.
                self.assertGreater(layers[0].fixedAspectRatio(), 0.0)
                self.assertAlmostEqual(
                    layers[0].size(),
                    self.rows[code].marker_size_mm * MM_TO_GROUND,
                    places=3,
                )

    def test_a_mark_the_annex_outlines_is_drawn_hollow(self):
        """MSP-019 and MSP-020 are the same star; only the ink differs."""
        solid = symbol_layers(symbol_of(self.points, "MSP-019"))[0]
        hollow = symbol_layers(symbol_of(self.points, "MSP-020"))[0]
        self.assertEqual(solid.shape(), hollow.shape())
        self.assertEqual(solid.strokeStyle(), Qt.PenStyle.NoPen)
        self.assertEqual(solid.color().alpha(), 255)
        # Hollow is the fill cleared and the ink moved to the outline: painting
        # the fill instead would draw a different symbol, not a differently
        # styled one.
        self.assertEqual(hollow.color().alpha(), 0)
        self.assertEqual(hollow.strokeStyle(), Qt.PenStyle.SolidLine)
        self.assertGreater(hollow.strokeWidth(), 0.0)
        ink = self.rows["MSP-020"].colors[0]
        self.assertEqual(
            (hollow.strokeColor().red(), hollow.strokeColor().green(),
             hollow.strokeColor().blue()),
            tuple(ink),
        )

    def test_a_bullseye_is_the_annexs_own_nested_discs(self):
        """The rings are a measurement, so each disc's width is the drawing's.

        Largest first, because each smaller disc paints over the centre of the one
        before it -- drawn the other way round every ring would disappear under
        the largest disc and the symbol would come back as a plain circle.
        """
        for code in ("MSP-002", "MSP-004"):
            row = self.rows[code]
            with self.subTest(code=code):
                layers = symbol_layers(symbol_of(self.points, code))
                self.assertEqual(len(layers), len(row.sembol_halkalar))
                self.assertTrue(all(isinstance(layer, QgsSimpleMarkerSymbolLayer)
                                    for layer in layers))
                self.assertTrue(all(layer.shape() == Qgis.MarkerShape.Circle
                                    for layer in layers))
                outer = layers[0].size()
                for layer, (ratio, _role) in zip(layers, row.sembol_halkalar):
                    self.assertAlmostEqual(layer.size() / outer, ratio, places=3)
                sizes = [layer.size() for layer in layers]
                self.assertEqual(sizes, sorted(sizes, reverse=True))
        # The empty ring is paper colour and the boundary ring is the row's own
        # outline colour -- MSP-004's centre is black, not white.
        rings = symbol_layers(symbol_of(self.points, "MSP-004"))
        self.assertEqual(self.rows["MSP-004"].sembol_halkalar[1][1], "sinir")
        self.assertEqual(rings[1].color().name(), "#000000")

    def test_the_four_energy_triangles_keep_their_colours_and_their_positions(self):
        """MSP-014 is one block of four source-coloured triangles, as EK-1b draws it."""
        row = self.rows["MSP-014"]
        layers = symbol_layers(symbol_of(self.points, "MSP-014"))
        self.assertEqual(len(layers), 4)
        self.assertTrue(all(layer.shape() == Qgis.MarkerShape.Triangle for layer in layers))
        self.assertEqual(
            [(layer.color().red(), layer.color().green(), layer.color().blue())
             for layer in layers],
            [tuple(rgb) for rgb in row.colors],
        )
        # Four distinct quadrants: two triangles at the same centre would draw
        # one shape and the palette would be invisible.
        offsets = [layer.offset() for layer in layers]
        self.assertEqual(len({(round(o.x(), 3), round(o.y(), 3)) for o in offsets}), 4)
        self.assertTrue(all(o.x() != 0.0 and o.y() != 0.0 for o in offsets))

    def test_the_circled_cross_is_a_disc_under_its_own_cross(self):
        layers = symbol_layers(symbol_of(self.points, "MSP-022"))
        self.assertEqual([layer.shape() for layer in layers],
                         [Qgis.MarkerShape.Circle, Qgis.MarkerShape.Cross])
        # The disc carries the annex's ink and the cross its outline colour; a
        # cross in the ink colour on an ink-coloured disc would be a plain dot.
        ink = self.rows["MSP-022"].colors[0]
        self.assertEqual((layers[0].color().red(), layers[0].color().green(),
                          layers[0].color().blue()), tuple(ink))
        self.assertNotEqual(layers[1].color().name(), layers[0].color().name())

    def test_each_mark_is_drawn_at_the_diameter_the_drawing_measured(self):
        """A fixed default would flatten a distinction the annex makes."""
        measured = {
            code: symbol_layers(symbol_of(self.points, code))[0].size()
            for code in ("MSP-008", "MSP-019", "MSP-011")
        }
        for code, size in measured.items():
            with self.subTest(code=code):
                self.assertAlmostEqual(
                    size, self.rows[code].marker_size_mm * MM_TO_GROUND, places=3
                )
        self.assertGreater(measured["MSP-019"], measured["MSP-008"])

    def test_the_class_rule_binds_both_fields_to_the_annexs_own_numbers(self):
        """MSP-002's tier picks the size and its density the tone, as data.

        The expression is the only place the binding is written, so this reads it
        back: the field it names is the field the workspace creates, and the
        numbers in it are the annex's own measured sizes and printed tones --
        converted to the unit the symbol is drawn in, which is the half a test on
        the expression text alone would miss.
        """
        rule = self.rows["MSP-002"].sinif_kurali
        expression = expression_for(self.points, "MSP-002", QgsSymbolLayer.PropertySize)
        self.assertIsNotNone(expression, "MSP-002'nin boyutu veriye bağlı değil")
        self.assertIn(f'"{rule["simge_alani"]}"', expression)
        for value in rule["simge_boyutlari_mm"]:
            with self.subTest(size_mm=value):
                self.assertIn(str(round(value * MM_TO_GROUND, 4))[:6], expression)
        # The expression is the only place the conversion is written, so it is
        # also the only place it can be lost: a size left in printed millimetres
        # is 250 times too small and would draw the mark as a dot.
        self.assertNotIn(str(rule["simge_boyutlari_mm"][-1]) + " ", expression)

        fill_expression = expression_for(
            self.areas, "MSP-002", QgsSymbolLayer.PropertyFillColor
        )
        self.assertIsNotNone(fill_expression, "MSP-002'nin tonu veriye bağlı değil")
        self.assertIn(f'"{rule["alan_alani"]}"', fill_expression)
        for tone in rule["tonlar"]:
            with self.subTest(tone=tone):
                self.assertIn(f"color_rgb({tone[0]},{tone[1]},{tone[2]})", fill_expression)
        # Both fields are the workspace's own, and they are two different ones:
        # one expression naming the other's field would bind a tier to a density.
        self.assertNotEqual(rule["simge_alani"], rule["alan_alani"])
        self.assertNotIn(f'"{rule["alan_alani"]}"', expression)
        self.assertNotIn(f'"{rule["simge_alani"]}"', fill_expression)

    def test_the_hatch_axis_is_the_measured_one_not_the_default(self):
        """The annex states the spacing and never the axis; EK-1b measures it.

        A fixed 45° would draw a hatch the annex does not draw, and it would be
        invisible to any test that only checked a pattern layer existed.
        """
        row = self.rows["MSP-025"]
        hatches = [layer for layer in symbol_layers(symbol_of(self.areas, "MSP-025"))
                   if isinstance(layer, QgsLinePatternFillSymbolLayer)]
        self.assertEqual(len(hatches), 1)
        self.assertEqual(hatches[0].lineAngle(), row.tarama_aci_derece)
        self.assertEqual(hatches[0].lineAngle(), 90.0)
        self.assertNotEqual(hatches[0].lineAngle(), HATCH_ANGLE_DEFAULT)
        # The row with no measured axis is a dotted grid and has no line hatch at
        # all, so it cannot be drawn at an angle nobody measured.
        self.assertIsNone(self.rows["MSP-024"].tarama_aci_derece)
        self.assertEqual(
            [layer for layer in symbol_layers(symbol_of(self.areas, "MSP-024"))
             if isinstance(layer, QgsLinePatternFillSymbolLayer)],
            [],
        )

    def test_every_length_is_written_in_the_unit_its_layer_declares(self):
        """A millimetre passed to a metre-declared layer is off by the map scale.

        MSP-014's four triangles are the case that found this: their offsets were
        written in printed millimetres while ``setOffsetUnit`` declared map metres,
        which put each one 0.015 mm from the centre instead of 3.84 mm and buried
        three of the four under the last.  Every marker here is checked for the
        same slip -- an offset is a quarter of the block the marker's own size
        measures a half of -- so it fails on any marker, not only on this one.
        """
        layers = symbol_layers(symbol_of(self.points, "MSP-014"))
        for layer in layers:
            with self.subTest(offset=layer.offset()):
                self.assertAlmostEqual(abs(layer.offset().x()) * 2.0, layer.size(), places=3)
                self.assertAlmostEqual(abs(layer.offset().y()) * 2.0, layer.size(), places=3)
        # The same relation cannot hold by accident: a size in millimetres and an
        # offset in metres differ by MM_TO_GROUND, which is not 1.
        self.assertNotAlmostEqual(MM_TO_GROUND, 1.0, places=3)


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
