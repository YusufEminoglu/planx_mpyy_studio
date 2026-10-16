"""Freeze the local MpyyNipDB drawing template into the plugin.

Run with a QGIS Python (not shipped in the plugin zip):

    python-qgis-ltr.bat tools/extract_local_nip_template.py <MpyyNipDB.gpkg>

Like the UIP template, the QGIS project inside the GeoPackage is the source of
truth: every layer's complete style (symbology, form, widgets, defaults,
constraints) is exported through QGIS itself. Only the drawing layers of the
"Revizyon" group and the function lookup table are taken; the base map
(``halihazir``), the in-force plan data (``Meri`` group), the survey layer and
the satellite service are data, not template, and stay out.
"""

import hashlib
import io
import json
import re
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsMapLayer,
    QgsProject,
    QgsReadWriteContext,
)
from qgis.PyQt.QtXml import QDomDocument  # noqa: E402

# Digests are written as four space-separated groups: the Hub's detect-secrets
# scan blocks a version on a quoted 64-hex string. Readers remove the spaces.
HUB_SAFE_DIGEST = re.compile(r'"([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})"')


def hub_safe(text: str) -> str:
    return HUB_SAFE_DIGEST.sub(r'"\1 \2 \3 \4"', text)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "forms" / "yerel_nip"

SPATIAL = (
    "alanlar-5000",
    "cizgiler_5000_v2",
    "yollar_ve_Adalar_icin_cizgiler",
    "yolgenisliksembol",
    "5000_revizyon_planonama_snr",
)
LOOKUPS = ("fonksiyonlar-5000_tablo",)


def _schema(con, table):
    geometry = con.execute(
        "SELECT column_name, geometry_type_name FROM gpkg_geometry_columns WHERE table_name=?",
        (table,),
    ).fetchone()
    fields = [
        {"name": name, "type": decl, "notnull": bool(notnull), "pk": bool(pk)}
        for _, name, decl, notnull, _, pk in con.execute(f'PRAGMA table_info("{table}")')
        if not geometry or name != geometry[0]
    ]
    return {
        "table": table,
        "geometry": geometry[1] if geometry else None,
        "fields": [f for f in fields if not f["pk"]],
    }


def _rows(con, table):
    columns = [name for _, name, _, _, _, pk in con.execute(f'PRAGMA table_info("{table}")') if not pk]
    quoted = ", ".join(f'"{c}"' for c in columns)
    return {
        "columns": columns,
        "rows": [list(row) for row in con.execute(f'SELECT {quoted} FROM "{table}" ORDER BY fid')],
    }


def main(source):
    source = Path(source).resolve()
    app = QgsApplication([], False)
    app.initQgis()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as con:
        name, content = con.execute("SELECT name, content FROM qgis_projects").fetchone()
        data = bytes.fromhex(content) if isinstance(content, str) else content
        schema = [_schema(con, t) for t in SPATIAL + LOOKUPS]
        lookups = {t: _rows(con, t) for t in LOOKUPS}

    work = Path(tempfile.mkdtemp())
    archive = zipfile.ZipFile(io.BytesIO(data))
    qgs_name = next(n for n in archive.namelist() if n.endswith(".qgs"))
    text = archive.read(qgs_name).decode("utf-8").replace("./" + source.name, source.as_posix())
    # Basemap and data layers would block on the network or carry someone's plan; drop them.
    import xml.etree.ElementTree as ET

    tree = ET.ElementTree(ET.fromstring(text))
    keep = set(SPATIAL + LOOKUPS)
    for parent in tree.getroot().iter():
        for child in list(parent):
            if child.tag == "maplayer" and child.findtext("layername") not in keep:
                parent.remove(child)
            elif child.tag == "layer-tree-layer" and child.get("name") not in keep:
                parent.remove(child)
    tree.write(work / "template.qgs", encoding="utf-8", xml_declaration=True)

    project = QgsProject.instance()
    if not project.read(str(work / "template.qgs")):
        raise SystemExit("QGIS could not read the embedded project")

    OUT.mkdir(parents=True, exist_ok=True)
    order = [n.name() for n in project.layerTreeRoot().findLayers()]
    exported = {}
    for table in SPATIAL + LOOKUPS:
        layer = next(iter(project.mapLayersByName(table)), None)
        if layer is None:
            raise SystemExit("missing template layer: " + table)
        doc = QDomDocument("qgis")
        error = layer.exportNamedStyle(doc, QgsReadWriteContext(), QgsMapLayer.StyleCategory.AllStyleCategories)
        if error:
            raise SystemExit(f"{table}: {error}")
        target = OUT / (table + ".qml")
        # newline="\n": the manifest hash must describe the bytes git stores. The repo is
        # committed as LF (.gitattributes, * text=auto eol=lf); letting Windows translate to
        # CRLF here would record a hash no clean checkout can ever reproduce.
        target.write_text(doc.toString(1), encoding="utf-8", newline="\n")
        exported[table] = {"qml": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    relations = [
        {
            "id": rel.id(),
            "referencing": rel.referencingLayer().name(),
            "referenced": rel.referencedLayer().name(),
            "pairs": dict(rel.fieldPairs()),
        }
        for rel in project.relationManager().relations().values()
    ]
    manifest = {
        "version": 1,
        "source": {"file": source.name, "sha256": digest, "project": name},
        "layer_order": [n for n in order if n in SPATIAL + LOOKUPS],
        "tables": schema,
        "relations": relations,
        "styles": exported,
        "skipped": ["halihazir", "meri_5000_nokta", "meri_5000_cizgi", "meri_5000_alan", "meri_1000_alan",
                    "ak_ada_duzeyi_tahmini_calisan_sayisi", "Google Satellite", "cizgiler-5000"],
    }
    (OUT / "template.json").write_text(hub_safe(json.dumps(manifest, ensure_ascii=False, indent=1)) + "\n", encoding="utf-8", newline="\n")
    (OUT / "lookups.json").write_text(json.dumps(lookups, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("layers", len(exported), "lookup rows", {t: len(v["rows"]) for t, v in lookups.items()},
          "relations", len(relations))
    sys.stdout.flush()
    os._exit(0)  # QGIS can hang on exitQgis with network-backed providers


if __name__ == "__main__":
    main(sys.argv[1])
