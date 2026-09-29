"""Processing labels: a key written twice in one dict literal silently keeps the last value.

PLAN_LEVEL was written twice in ENUM_OPTIONS, so the workspace audit's
"Dosyadan oku / UIP / NIP / CDP" showed "MSP / CDP / NIP / UIP" and picking
"CDP" audited the plan as UIP; OUTPUT_REPORT twice in PARAMETERS called four
CSV reports "JSON rapor dosyası". Neither raises: only the source shows it.
"""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "gui" / "processing_text.py"


class DictLiteralKeys(unittest.TestCase):
    def test_no_dict_literal_repeats_a_key(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        repeated = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            seen = set()
            for key in node.keys:
                if isinstance(key, ast.Constant):
                    if key.value in seen:
                        repeated.append((key.value, key.lineno))
                    seen.add(key.value)
        self.assertEqual(repeated, [])


if __name__ == "__main__":
    unittest.main()
