"""Area centre pictograms are drawn at the regulated 10 / 7 / 5 mm (Ek-1e), measured by rendering."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import Qgis, QgsApplication, QgsVectorLayer  # noqa: E402

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from planx_mpyy_studio.core.centre_symbols import (  # noqa: E402
    SYMBOL_MM,
    _table,
    centre_markers,
    in_millimetres,
    measure_ink,
    scale_factor,
)
from planx_mpyy_studio.core.mpyy_detail_catalog import _level_scale  # noqa: E402
from planx_mpyy_studio.core.mpyy_workspace import all_levels, apply_eplan_symbology  # noqa: E402

LEVELS = ("UIP", "NIP", "CDP")
TOLERANCE_MM = 0.25  # measured at 384 dpi: anti-aliasing plus a 2.4x scale-up of the smallest glyphs


def styled(level, type_name, centre_sizes=True):
    layer = QgsVectorLayer("MultiPolygon?crs=EPSG:5254", type_name, "memory")
    if not apply_eplan_symbology(layer, level, type_name, centre_sizes=centre_sizes):
        return None
    return layer


def polygon_types(level):
    return [spec["name"] for spec in all_levels()[level]["feature_types"] if "Polygon" in (spec.get("geometry") or "")]


class CentreSymbolSizeTests(unittest.TestCase):
    def test_every_centre_pictogram_is_drawn_at_its_levels_size(self):
        checked = 0
        for level in LEVELS:
            scale = _level_scale(level)
            for type_name in polygon_types(level):
                layer = styled(level, type_name)
                if layer is None:
                    continue
                renderer = layer.renderer()
                for (label, holder), entry in zip(centre_markers(renderer), _table()[level].get(type_name, [])):
                    marker = holder.subSymbol()
                    units = {marker.symbolLayer(i).sizeUnit() for i in range(marker.symbolLayerCount())}
                    self.assertNotIn(Qgis.RenderUnit.Pixels, units, f"{level}/{type_name}/{label} in screen pixels")
                    if entry["carpan"] is None:
                        continue
                    ink = measure_ink(marker, scale)
                    with self.subTest(level=level, type=type_name, rule=label, ink=ink):
                        self.assertAlmostEqual(min(ink), SYMBOL_MM[level], delta=TOLERANCE_MM)
                    checked += 1
        self.assertGreater(checked, 400)

    def test_the_reported_small_symbols_are_now_full_size(self):
        # TIRE UİP: askeri alan and ticaret(-konut) were drawn about 4 mm high at 1:1000.
        layer = styled("UIP", "KentselCalisma")
        sizes = {label: measure_ink(holder.subSymbol(), 1000) for label, holder in centre_markers(layer.renderer())}
        for rule in ("ASKERI_ALAN", "TICARET_ALANI", "TICARET_KONUT_ALANI"):
            self.assertGreaterEqual(min(sizes[rule]), SYMBOL_MM["UIP"] - TOLERANCE_MM, rule)
        # ÇDP pictograms came at 15 mm, three times the regulated 5 mm.
        layer = styled("CDP", polygon_types("CDP")[0])
        for type_name in polygon_types("CDP"):
            layer = styled("CDP", type_name)
            if layer is not None and centre_markers(layer.renderer()):
                break
        for label, holder in centre_markers(layer.renderer()):
            self.assertLessEqual(min(measure_ink(holder.subSymbol(), _level_scale("CDP"))),
                                 SYMBOL_MM["CDP"] + TOLERANCE_MM, label)

    def test_marks_that_are_not_pictograms_are_left_as_drawn(self):
        self.assertIsNone(scale_factor([53.98, 15.35], "UIP"))   # the word PARK
        self.assertIsNone(scale_factor([0.79, 0.79], "NIP"))     # a dot
        self.assertAlmostEqual(scale_factor([4.2, 4.2], "UIP"), 10 / 4.2)
        layer = styled("UIP", "AcikYesilAlan")
        park = [holder for label, holder in centre_markers(layer.renderer()) if label == "PARK"][0]
        stored = [e for e in _table()["UIP"]["AcikYesilAlan"] if e["kural"] == "PARK"][0]
        self.assertIsNone(stored["carpan"])
        self.assertEqual(measure_ink(park.subSymbol(), 1000), stored["murekkep_mm"])

    def test_stored_measurements_match_the_current_styles(self):
        # The table is generated (tools/measure_centre_symbols.py); an SLD, catalogue or font
        # change that moves a symbol must regenerate it, or the scaling would be off.
        for level in LEVELS:
            scale = _level_scale(level)
            for type_name in polygon_types(level):
                layer = styled(level, type_name, centre_sizes=False)
                if layer is None:
                    continue
                renderer = layer.renderer()
                measured = [(label, measure_ink(in_millimetres(holder.subSymbol()), scale))
                            for label, holder in centre_markers(renderer)]
                stored = [(e["kural"], e["murekkep_mm"]) for e in _table()[level].get(type_name, [])]
                with self.subTest(level=level, type=type_name):
                    self.assertEqual([m[0] for m in measured], [s[0] for s in stored])
                    for (_, got), (_, want) in zip(measured, stored):
                        if want is None:
                            self.assertIsNone(got)
                            continue
                        self.assertAlmostEqual(got[0], want[0], delta=TOLERANCE_MM)
                        self.assertAlmostEqual(got[1], want[1], delta=TOLERANCE_MM)


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
