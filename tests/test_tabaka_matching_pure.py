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
            "PL_ADAKENARI": "ADAKENARI",                 # PL_ only says "plan layer"
            "PL_KALDIRIM": "KALDIRIM",
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

    def test_proposals_read_the_functions_own_names(self):
        # Tire UİP tabaka the old whole-name similarity proposed nothing, or the
        # wrong thing, for (SIT_3_ARKEOLOJIK -> Jeolojik etüt).
        cases = {
            "PL_ARITMA": ("AtiksuTesis", {}),
            "PL_DISPANSER": ("SaglikTesisAlani", {"SaglikTip": "SaglikTesisAlani"}),
            "PL_ORTAOGRETIM": ("EgitimTesisAlani", {"EgitimTesisTip": "LiseAlani"}),
            "PL_HAZIRE": ("AcikYesilAlan", {"AcikYesilTip": "MezarlikAlani"}),
            "SNR_SIT_3_ARKEOLOJIK": ("SitAlanlari", {"SitTip": "3DereceArkeolojikSit"}),
            "KA_TESCIL_ANIT": ("TescilliAlan", {"TescilTip": "TescilliAnitYapi"}),
            "PL_DOGALGAZ_REGULATR": ("EnerjiDagitimDepolama", {"EnerjiTesisTip": "RegulatorAlani"}),
            "PL_SU_DEPOSU": ("IcmesuTesis", {}),
        }
        for name, (feature, attrs) in cases.items():
            with self.subTest(name=name):
                proposals = tm.suggest("UIP", name, geometry="polygon")
                self.assertTrue(proposals, name)
                self.assertEqual((proposals[0].entry["feature"], proposals[0].entry["attrs"]), (feature, attrs))
                self.assertTrue(proposals[0].label)
                self.assertFalse(tm.resolve("UIP", name, user={}).resolved)  # still only a proposal
        self.assertNotIn("Jeolojik", " ".join(s.label.title() for s in tm.suggest("UIP", "SNR_SIT_3_ARKEOLOJIK")))

    def test_the_layer_geometry_limits_the_proposals(self):
        functions = tm.targets("UIP")
        for geometry in ("polygon", "line"):
            for proposal in tm.suggest("UIP", "PL_SPOR_TESISLERI", geometry=geometry, limit=20):
                self.assertEqual(functions[proposal.key].geometry, geometry)
        self.assertEqual(tm.suggest("UIP", "HAT_DERE", geometry="line"), [])

    def test_netcad_notation_layers_are_not_functions(self):
        # ... nor are the cadastre, texts, sheet indexes or notes (PARSEL drew
        # "Tescilli parsel" for 20 700 Tire parcels), nor a bare "other".
        for name in ("SM_YAPILASMA", "SM_KAKS", "SM_ADA_NO", "PARSEL", "PARSEL_YENI", "ADA_NO", "ADA_AYRIM",
                     "YAZI_FONKSIYON", "EKLE_TESCILLI_YAPI", "PINDEX_1000", "BELEDIYE_NOT", "SNR_DIGER", "T_H"):
            self.assertEqual(tm.suggest("UIP", name), [], name)

    def test_abbreviations_endings_and_run_together_words(self):
        self.assertTrue(tm._is_abbreviation("KULTR", "KULTUR"))
        self.assertTrue(tm._is_abbreviation("VRLIGI", "VARLIGI"))
        self.assertTrue(tm._is_abbreviation("REGULATR", "REGULATOR"))
        self.assertFalse(tm._word_match("YAPILASMA", "YAPI")[0])      # a longer word is not its prefix
        self.assertEqual(tm._singular("TESISLERI"), "TESIS")
        self.assertEqual(tm._singular("DEPOSU"), "DEPO")
        self.assertEqual(tm._singular("SANAYI"), "SANAYI")
        words = tm._vocabulary("UIP").words
        self.assertIn("KORUMA", tm._segment("TESCILCEPHEKORUMA", words))
        self.assertEqual(tm._segment("ORTAOGRETIM", words), ["ORTAOGRETIM"])   # a listed word stays whole

    def test_one_word_that_fits_many_functions_is_not_guessed(self):
        # A_SINIR ("boundary") drew "Önlemli alan" 0.93; KORUMA fits 29 functions.
        for name in ("A_SiNiR", "PL_KORUMA_SAHASI"):
            self.assertEqual(tm.suggest("UIP", name, geometry="polygon"), [], name)
        self.assertTrue(tm.suggest("UIP", "PL_ISTASYON", geometry="polygon"))    # 4 stations: still offered

    def test_only_single_mpyy_tables_are_offered(self):
        # Six Ek-1e road records name "Yolorta + AdaKenari + DigerYolNesneleri":
        # confirming one made the import look for a table of that name.
        for level in ("UIP", "NIP", "CDP"):
            self.assertFalse([k for k, t in tm.targets(level).items() if "+" in t.entry["feature"]], level)
        stale = {"UIP": {"A_SERVISYOLU": "fn:MPYY-410"}}          # BÖLÜNMÜŞ TAŞIT YOLU, composite
        self.assertFalse(tm.resolve("UIP", "A_SERVISYOLU", user=stale).resolved)

    def test_a_function_without_a_ministry_tabaka_can_be_confirmed(self):
        only_ek1e = [key for key in tm.targets("UIP") if key.startswith("fn:")]
        self.assertTrue(only_ek1e)
        key = only_ek1e[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "eslesme.json"
            tm.confirm("UIP", "PL_OZEL_ADI", key, path=path)
            m = tm.resolve("UIP", "PL_OZEL_ADI", user=tm.load_user_mappings(path))
            self.assertEqual((m.method, m.key, m.entry), ("onayli", key, tm.targets("UIP")[key].entry))

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
