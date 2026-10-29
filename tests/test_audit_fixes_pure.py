"""Pure-Python regression tests for PlanX MPYY Studio comprehensive audit fixes."""

from pathlib import Path
import unittest

from planx_mpyy_studio.core.attr_utils import (
    clean_text,
    is_non_buildable_open_space,
    is_non_residential_work_zone,
    is_null_value,
    norm_tr,
    normalize_nizam_code,
    parse_float,
    parse_floor_count,
    parse_iso_date,
    upper_tr,
)
from planx_mpyy_studio.core.density_change_audit import DensityChangeAuditEngine
from planx_mpyy_studio.core.mixed_use_audit import MPYYMixedUseAuditEngine
from planx_mpyy_studio.core.road_change_audit import RoadChangeAuditEngine


class TestAuditFixesPure(unittest.TestCase):
    def test_attr_utils_normalization(self):
        self.assertEqual(norm_tr("Konut Alanı"), "KONUT_ALANI")
        self.assertEqual(norm_tr("Ağaçlandırılacak Alan"), "AGACLANDIRILACAK_ALAN")
        self.assertEqual(upper_tr("şemsiye çeşme iğne"), "ŞEMSİYE ÇEŞME İĞNE")
        self.assertEqual(clean_text("  İstanbul  "), "İstanbul")
        self.assertEqual(clean_text(None), "")

    def test_attr_utils_null_detection(self):
        self.assertTrue(is_null_value(None))
        self.assertTrue(is_null_value(""))
        self.assertTrue(is_null_value("   "))
        self.assertTrue(is_null_value("NULL"))
        self.assertTrue(is_null_value("null"))
        self.assertTrue(is_null_value("None"))
        self.assertFalse(is_null_value("0"))
        self.assertFalse(is_null_value(0))
        self.assertFalse(is_null_value(0.0))
        self.assertFalse(is_null_value("AYRIK"))

    def test_parse_float_turkish_locale(self):
        self.assertEqual(parse_float(12.5), 12.5)
        self.assertEqual(parse_float("12.5"), 12.5)
        self.assertEqual(parse_float("12,5"), 12.5)
        self.assertEqual(parse_float("0"), 0.0)
        self.assertEqual(parse_float(0), 0.0)
        self.assertIsNone(parse_float(None))
        self.assertIsNone(parse_float("NULL"))
        self.assertIsNone(parse_float("abc"))

    def test_parse_floor_count(self):
        self.assertEqual(parse_floor_count(5), 5)
        self.assertEqual(parse_floor_count("5"), 5)
        self.assertEqual(parse_floor_count("Z+4"), 5)
        self.assertEqual(parse_floor_count("B+Z+3"), 4)
        self.assertEqual(parse_floor_count("4 Kat"), 4)
        self.assertEqual(parse_floor_count("4.0"), 4)
        self.assertIsNone(parse_floor_count(None))

    def test_parse_iso_date(self):
        from datetime import date
        self.assertEqual(parse_iso_date("2026-10-29"), date(2026, 10, 29))
        self.assertEqual(parse_iso_date("2026-10-29T14:30:00"), date(2026, 10, 29))
        self.assertIsNone(parse_iso_date(None))
        self.assertIsNone(parse_iso_date("invalid"))

    def test_normalize_nizam_code(self):
        self.assertEqual(normalize_nizam_code("A"), "AYRIK")
        self.assertEqual(normalize_nizam_code("ayrık"), "AYRIK")
        self.assertEqual(normalize_nizam_code("B"), "BITISIK")
        self.assertEqual(normalize_nizam_code("bitişik"), "BITISIK")
        self.assertEqual(normalize_nizam_code("BL"), "BLOK")
        self.assertEqual(normalize_nizam_code("blok"), "BLOK")
        self.assertEqual(normalize_nizam_code("İKİZ"), "IKIZ")
        self.assertEqual(normalize_nizam_code("Serbest"), "SERBEST")
        self.assertEqual(normalize_nizam_code(None), "AYRIK")

    def test_function_classification(self):
        self.assertTrue(is_non_residential_work_zone("KONUT_DISI_KENTSEL_CALISMA"))
        self.assertTrue(is_non_residential_work_zone("KDKCA"))
        self.assertFalse(is_non_residential_work_zone("KONUT_ALANI"))

        self.assertTrue(is_non_buildable_open_space("PARK"))
        self.assertTrue(is_non_buildable_open_space("COCUK_BAHCESI"))
        self.assertTrue(is_non_buildable_open_space("YOL"))
        self.assertFalse(is_non_buildable_open_space("KONUT_ALANI"))
        self.assertFalse(is_non_buildable_open_space("TICARET_ALANI"))

    def test_density_change_audit(self):
        audit = DensityChangeAuditEngine.audit({
            "current_height_m": 12.5,
            "proposed_height_m": 18.5,
            "opposite_height_m": 12.5,
            "actual_facade_distance_m": 25.0,
            "current_population": 100,
            "proposed_population": 100,
            "silhouette_assessment": True,
        })
        self.assertEqual(audit.status, "COMPLIANT")
        self.assertIsNotNone(audit.required_facade_distance_m)

    def test_mixed_use_audit(self):
        result = MPYYMixedUseAuditEngine.audit({
            "use_code": "TICARET+KONUT",
            "residential_ratio": 0.40,
            "ratios_in_plan_report": True,
            "ratios_in_plan_notes": True,
            "parking_details": True,
            "green_area_details": True,
            "social_technical_infrastructure_details": True,
            "residential_infrastructure_allocated": True,
        })
        self.assertEqual(result.status, "COMPLIANT")
        self.assertEqual(result.effective_residential_ratio, 0.40)

    def test_road_change_audit(self):
        audit = RoadChangeAuditEngine.audit({
            "current_width_m": 10.0,
            "proposed_width_m": 12.0,
            "area_context": "DEVELOPMENT",
            "traffic_impact_assessment": True,
        })
        self.assertEqual(audit.status, "COMPLIANT")

    def test_no_corrupt_strings_in_repository(self):
        needle = "sat" + "ır bulundu"
        root = Path(__file__).resolve().parents[1]
        for path in root.rglob("*.py"):
            if path.name == "test_audit_fixes_pure.py":
                continue
            text = path.read_text(encoding="utf-8")
            if needle in text:
                # The only valid place is provider.py line 3464 (genuine Turkish output string)
                lines = [
                    (num, line)
                    for num, line in enumerate(text.splitlines(), start=1)
                    if needle in line
                ]
                for num, line in lines:
                    if path.name == "provider.py" and "Önizlemede yalnızca gelen dosyada bulunan" in line:
                        continue
                    self.fail(f"Corrupt needle found in {path.name}:{num} -> {line}")


if __name__ == "__main__":
    unittest.main()
