"""Freeze the local MpyyUipDb drawing template into the plugin.

Run with a QGIS Python (not shipped in the plugin zip):

    python-qgis-ltr.bat tools/extract_local_uip_template.py <MpyyUipDb.gpkg>

The source GeoPackage carries a QGIS project ("çizim şablonu") whose layer
definitions are newer than its ``layer_styles`` rows, so the project is the
source of truth. For every template layer the complete QGIS style (symbology,
form, widgets, defaults, constraints) is exported through QGIS itself, never
by editing XML text. Schema and lookup rows are read from the same file.

Two deliberate deviations from the source are applied and recorded:
* the ``uip-notasyonlar.ustkonugrup`` default referenced a layer id that exists
  only in an older project; it is rewritten to the name-based
  ``overlay_intersects`` form its sibling fields already use;
* the ``uipfonksiyon`` relation widget stores the source file path; the loader
  rebinds it to the workspace being opened.
"""

import hashlib
import json
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "forms" / "yerel_uip"

SPATIAL = ("uip-alanlar", "uip_cizgiler", "uip-notasyonlar", "yapi_yaklasma")
LOOKUPS = ("uipPolygonTable", "uipLineTable")
STALE_DEFAULT = "uipPolygonDemo_46ee9637_3c46_4dc4_8cff_71a930649f30"


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


def main(source):
    source = Path(source).resolve()
    app = QgsApplication([], False)
    app.initQgis()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as con:
        name, content = con.execute("SELECT name, content FROM qgis_projects").fetchone()
        data = bytes.fromhex(content) if isinstance(content, str) else content
        schema = [_schema(con, t) for t in SPATIAL + LOOKUPS]
        lookups = {
            t: [
                dict(zip(("id1", "ust_konu_grup", "id2", "uip_fonksiyon", "id3", "uip_tabaka"), row))
                for row in con.execute(
                    f'SELECT id1, ust_konu_grup, id2, uip_fonksiyon, id3, uip_tabaka FROM "{t}" ORDER BY fid'
                )
            ]
            for t in LOOKUPS
        }

    work = Path(tempfile.mkdtemp())
    archive = zipfile.ZipFile(__import__("io").BytesIO(data))
    qgs_name = next(n for n in archive.namelist() if n.endswith(".qgs"))
    text = archive.read(qgs_name).decode("utf-8").replace("./" + source.name, source.as_posix())
    # Basemap XYZ layers would block on the network and are not template layers.
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
        if table == "uip-notasyonlar":
            index = layer.fields().indexFromName("ustkonugrup")
            if STALE_DEFAULT in layer.defaultValueDefinition(index).expression():
                definition = layer.defaultValueDefinition(index)
                definition.setExpression("array_first(overlay_intersects('uip-alanlar', \"ustkonugrup\"))")
                layer.setDefaultValueDefinition(index, definition)
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
        "deviations": [
            "uip-notasyonlar.ustkonugrup default: stale layer id replaced by overlay_intersects('uip-alanlar', \"ustkonugrup\")",
            "relation widget data source is rebound to the opened workspace at load time",
        ],
    }
    (OUT / "template.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (OUT / "lookups.json").write_text(json.dumps(lookups, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "tables"}, ensure_ascii=False, indent=1))
    project.clear()
    sys.stdout.flush()
    # QgsApplication.exitQgis() blocks on Windows after reading a project.
    os._exit(0)


if __name__ == "__main__":
    main(sys.argv[1])
