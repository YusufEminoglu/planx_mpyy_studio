"""Measure the drawn size of every area centre pictogram -> styles/mpyy_centre_symbols.json.

    C:/OSGeo4W/bin/python-qgis-ltr.bat tools/measure_centre_symbols.py [--check]

Each centre marker (sub-symbol of a CentroidFill) of every polygon type of every
level is rendered alone at the level's scale, as the SLD sets it (pixel sizes
read as 96 dpi millimetres) at 384 dpi, and the bounding box of its ink is recorded in
paper mm. ``core/centre_symbols.py`` scales each pictogram from that measurement
to the regulated 10 / 7 / 5 mm. Rerun after any SLD, catalogue or font change;
``--check`` fails when the stored table no longer matches.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsApplication, QgsVectorLayer  # noqa: E402

app = QgsApplication([], False)
app.initQgis()

from planx_mpyy_studio.core.centre_symbols import (  # noqa: E402
    SYMBOL_MM, TABLE_PATH, centre_markers, in_millimetres, measure_ink, scale_factor)
from planx_mpyy_studio.core.mpyy_detail_catalog import _level_scale  # noqa: E402
from planx_mpyy_studio.core.mpyy_workspace import SLD_DIR, all_levels, apply_eplan_symbology  # noqa: E402


def measure_level(level):
    scale = _level_scale(level)
    types = {}
    for spec in all_levels()[level]["feature_types"]:
        if "Polygon" not in (spec.get("geometry") or ""):
            continue
        layer = QgsVectorLayer("MultiPolygon?crs=EPSG:5254", spec["name"], "memory")
        if not apply_eplan_symbology(layer, level, spec["name"], centre_sizes=False):
            continue
        renderer = layer.renderer()
        entries = []
        for label, holder in centre_markers(renderer):
            ink = measure_ink(in_millimetres(holder.subSymbol()), scale)
            factor = scale_factor(ink, level)
            entries.append({"kural": label, "murekkep_mm": ink,
                            "carpan": round(factor, 4) if factor else None})
        if entries:
            types[spec["name"]] = entries
    return types


def main():
    levels = [level for level in SYMBOL_MM if level in all_levels() and (SLD_DIR / level).is_dir()]
    table = {"kaynak": "Ek-1e: Çevre Düzeni Planı 5 mm, Nazım İmar Planı 7 mm, Uygulama İmar Planı 10 mm",
             "olcum": "tools/measure_centre_symbols.py, 384 dpi, plan ölçeğinde",
             "levels": {level: measure_level(level) for level in levels}}
    text = json.dumps(table, ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        current = TABLE_PATH.read_text(encoding="utf-8") if TABLE_PATH.exists() else ""
        if current != text:
            raise SystemExit(f"{TABLE_PATH.name} is stale: rerun tools/measure_centre_symbols.py")
        print(f"{TABLE_PATH.name} up to date")
        return
    TABLE_PATH.write_text(text, encoding="utf-8")
    for level, types in table["levels"].items():
        entries = [e for t in types.values() for e in t]
        kept = [f"{t}/{e['kural']} {e['murekkep_mm']}" for t, es in types.items() for e in es if e["carpan"] is None]
        print(f"{level}: {len(entries)} centre markers, {len(entries) - len(kept)} scaled to {SYMBOL_MM[level]} mm;"
              f" left as drawn: {kept}")


if __name__ == "__main__":
    main()
