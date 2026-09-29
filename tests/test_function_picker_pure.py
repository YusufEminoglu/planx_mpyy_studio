"""Plan function -> MPYY type and code, straight from the Ek-1e hierarchy and the SLD rules."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from planx_mpyy_studio.core.function_picker import plan_functions  # noqa: E402


class PlanFunctionCatalogue(unittest.TestCase):
    def test_every_level_offers_its_catalogue(self):
        counts = {level: len(plan_functions(level)) for level in ("UIP", "NIP", "CDP")}
        # every hierarchy record once, but the six road records drawn by three
        # tables at once (Yolorta + AdaKenari + DigerYolNesneleri): no single layer
        self.assertEqual(sum(counts.values()), 592 - 6)
        self.assertTrue(all(counts.values()))
        for level in counts:
            self.assertFalse([f for f in plan_functions(level) if "+" in f.feature_type])

    def test_functions_carry_the_ministry_rule_values(self):
        by_name = {f.name: f for f in plan_functions("UIP")}
        cases = {
            "YERLEŞİK KONUT ALANI": ("Konut", (("KonutTip", "YerlesikKonut"),)),
            "GELİŞME KONUT ALANI": ("Konut", (("KonutTip", "GelismeKonut"),)),
            "CAMİ": ("IbadetAlani", (("IbadetTip", "Cami"),)),
            "PARK": ("AcikYesilAlan", (("AcikYesilTip", "Park"),)),
        }
        for name, (feature, attrs) in cases.items():
            with self.subTest(name=name):
                self.assertEqual((by_name[name].feature_type, by_name[name].attrs), (feature, attrs))

    def test_a_whole_type_rule_sets_no_value(self):
        # rows drawn by the whole type ('*') choose the table only; nothing is invented
        whole = [f for f in plan_functions("CDP") if f.feature_type == "Mera"]
        self.assertTrue(whole)
        self.assertTrue(all(f.attrs == () for f in whole))


if __name__ == "__main__":
    unittest.main()
