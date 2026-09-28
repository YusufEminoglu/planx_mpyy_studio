"""Tabaka -> MPYY resolution tiers: what may apply by itself, and what may only be proposed.

Cases are real tabaka from a Tire UİP (TIRE_MERKEZ_UIP_19012024): exact table
matching resolved 31 of its 155 tabaka.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from planx_mpyy_studio.core import tabaka_matching as tm  # noqa: E402


class ResolutionTiers(unittest.TestCase):
    def test_exact_names_resolve_exactly(self):
        m = tm.resolve("UIP", "PL_KONUT", user={})
        self.assertEqual((m.method, m.key), ("tam", "PL_KONUT"))

    def test_spelling_rules_resolve_without_asking(self):
        cases = {
            "PL_ILKOKUL": "PL_ILKOKUL_ALANI",          # area ending
            "PL_KAPALI_SPOR": "PL_KAPALI_SPOR_TES",
            "PL_DERE_2": "PL_DERE",                    # copy number
            "PL_KONUT_TICARET2": "PL_KONUT_TICARET",
            "ADAKENARI_NETCAD": "ADAKENARI",           # Netcad export suffix
            "PL_BAKIMAKARYAKIT": "PL_BAKIM_AKARYAKIT",  # words run together
            "SNR_YAPI_YAKLASMA": "SNR_YAPIYAKLASMA",
        }
        for name, key in cases.items():
            with self.subTest(name=name):
                m = tm.resolve("UIP", name, user={})
                self.assertEqual((m.method, m.key), ("kural", key))
                self.assertTrue(m.rule)

    def test_meaning_is_never_guessed(self):
        # String similarity proposed PL_DINI_TESIS -> Sanayi Tesis and HAT_DERE ->
        # Kademe hattı on the Tire plan: nothing but an exact/confirmed/rule match applies.
        for name in ("PL_DINI_TESIS", "HAT_DERE", "HAT_REFUJ", "PL_YESIL_ALAN", "PL_SANAT_OKULU"):
            with self.subTest(name=name):
                self.assertFalse(tm.resolve("UIP", name, user={}).resolved)

    def test_cancelled_or_contested_is_neither_resolved_nor_proposed(self):
        for name in ("PL_KONUT_IPTAL", "PL_PARK_ITIRAZ"):
            with self.subTest(name=name):
                self.assertFalse(tm.resolve("UIP", name, user={}).resolved)
                self.assertEqual(tm.suggest("UIP", name), [])

    def test_suggestions_lead_with_meaning_not_spelling(self):
        dini = [s.key for s in tm.suggest("UIP", "PL_DINI_TESIS")]
        self.assertTrue(dini)
        self.assertIn(dini[0], ("PL_CAMI", "PL_MESCIT"))
        self.assertNotIn("PL_SANAYI_TESIS", dini)
        self.assertEqual(tm.suggest("UIP", "PL_OYUN_ALANI")[0].key, "PL_COCUK_BAHCESI")

    def test_a_confirmed_mapping_is_remembered_and_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "eslesme.json"
            tm.confirm("UIP", "PL_DINI_TESIS", "PL_CAMI", path=path)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["levels"]["UIP"]["PL_DINI_TESIS"], "PL_CAMI")
            m = tm.resolve("UIP", "pl dini tesis", user=tm.load_user_mappings(path))
            self.assertEqual((m.method, m.key), ("onayli", "PL_CAMI"))
            with self.assertRaises(KeyError):
                tm.confirm("UIP", "X", "NOT_A_KEY", path=path)

    def test_the_env_override_points_every_caller_at_one_file(self):
        with tempfile.TemporaryDirectory() as folder:
            os.environ["MPYY_TABAKA_ESLESME"] = str(Path(folder) / "e.json")
            try:
                self.assertEqual(tm.user_mappings_path(), Path(folder) / "e.json")
            finally:
                del os.environ["MPYY_TABAKA_ESLESME"]


if __name__ == "__main__":
    unittest.main()
