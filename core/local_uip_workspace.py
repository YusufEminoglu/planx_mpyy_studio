"""Yerel UİP çalışma alanı: MpyyUipDb çizim şablonunun birebir yapısı.

The table structure, lookup rows and complete QGIS layer definitions (symbology,
attribute form, dropdown widgets, default values, constraints) are frozen from
the author's working ``MpyyUipDb`` template by
``tools/extract_local_uip_template.py``. Nothing here re-describes that form;
it is created and loaded exactly as exported, so the dropdowns behave the way
they do in the source project.
"""

import json
import os
import sqlite3
import uuid
import contextlib
from contextlib import closing
from pathlib import Path

from osgeo import gdal, ogr
from qgis.core import QgsEditorWidgetSetup, QgsProject, QgsRelation, QgsVectorLayer
from qgis.PyQt.QtXml import QDomDocument

from .schema import SCHEMA_VERSION

gdal.UseExceptions()

KIND = "YEREL_UIP"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "forms" / "yerel_uip"
GROUP_NAME = "Yerel UİP (MpyyUipDb şablonu)"

_GEOMETRY = {
    "MULTIPOLYGON": ogr.wkbMultiPolygon,
    "MULTILINESTRING": ogr.wkbMultiLineString,
    "LINESTRING": ogr.wkbLineString,
    "POINT": ogr.wkbPoint,
    None: ogr.wkbNone,
}


_LOOKUP_INSERTS = {
    "uipPolygonTable": 'INSERT INTO "uipPolygonTable" (id1, ust_konu_grup, id2, uip_fonksiyon, id3, uip_tabaka) VALUES (?,?,?,?,?,?)',
    "uipLineTable": 'INSERT INTO "uipLineTable" (id1, ust_konu_grup, id2, uip_fonksiyon, id3, uip_tabaka) VALUES (?,?,?,?,?,?)',
}


def template():
    return json.loads((TEMPLATE_DIR / "template.json").read_text(encoding="utf-8"))


def _lookups():
    return json.loads((TEMPLATE_DIR / "lookups.json").read_text(encoding="utf-8"))


def _field_defn(name, declared):
    declared = declared.upper()
    width = 0
    if "(" in declared:
        declared, width = declared.split("(", 1)
        width = int(width.rstrip(")"))
    kind = {
        "TEXT": ogr.OFTString,
        "INTEGER": ogr.OFTInteger64,
        "MEDIUMINT": ogr.OFTInteger,  # SQLite affinity used by the MpyyNipDB template
        "REAL": ogr.OFTReal,
        "DATETIME": ogr.OFTDateTime,
    }[declared]
    defn = ogr.FieldDefn(name, kind)
    if width:
        defn.SetWidth(width)
    return defn


def _crs_srs(crs):
    from .db_factory import _crs

    return _crs(crs)


def create_local_uip_workspace(output_path, crs):
    """Create a GeoPackage with the MpyyUipDb template's exact tables and styles."""
    output = Path(output_path).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    if output.suffix.lower() != ".gpkg":
        raise ValueError('Çıktı .gpkg uzantısını kullanmalıdır')
    spec = template()
    srs = _crs_srs(crs)
    staging = output.parent / (".mpyy-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / "dataset.gpkg"
    try:
        ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(staged))
        if ds is None:
            raise RuntimeError('GeoPackage oluşturulamadı')
        for table in spec["tables"]:
            geometry = table["geometry"]
            options = ["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES", "FID=fid"] if geometry else ["FID=fid"]
            layer = ds.CreateLayer(table["table"], srs if geometry else None, _GEOMETRY[geometry], options=options)
            if layer is None:
                raise RuntimeError('Katman oluşturulamadı: ' + table["table"])
            for field in table["fields"]:
                if layer.CreateField(_field_defn(field["name"], field["type"])) != 0:
                    raise RuntimeError(f'Alan oluşturulamadı: {table["table"]}.{field["name"]}')
        ds = None

        columns = ("id1", "ust_konu_grup", "id2", "uip_fonksiyon", "id3", "uip_tabaka")
        with closing(sqlite3.connect(staged)) as con, con:
            lookups = _lookups()
            for table, insert in _LOOKUP_INSERTS.items():
                con.executemany(insert, [tuple(row[c] for c in columns) for row in lookups[table]])
            con.execute(
                "CREATE TABLE mpyy_metadata (dataset_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                "workspace_kind TEXT NOT NULL, plan_levels TEXT NOT NULL)"
            )
            con.execute(
                "INSERT INTO mpyy_metadata VALUES (?,?,?,?)",
                (str(uuid.uuid4()), SCHEMA_VERSION, KIND, "UIP"),
            )
            con.execute(
                """CREATE TABLE layer_styles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT(256), f_table_schema TEXT(256),
                    f_table_name TEXT(256), f_geometry_column TEXT(256), styleName TEXT(30), styleQML TEXT,
                    styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30), ui TEXT(30),
                    update_time DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))"""
            )
            con.execute(
                "INSERT INTO gpkg_contents(table_name, data_type, identifier) VALUES ('layer_styles','attributes','layer_styles')"
            )
            for table in spec["tables"]:
                name = table["table"]
                con.execute(
                    "INSERT INTO layer_styles(f_table_catalog, f_table_schema, f_table_name, f_geometry_column, "
                    "styleName, styleQML, useAsDefault, description) VALUES ('', '', ?, ?, ?, ?, 1, ?)",
                    (
                        name,
                        "geom" if table["geometry"] else "",
                        name,
                        (TEMPLATE_DIR / spec["styles"][name]["qml"]).read_text(encoding="utf-8"),
                        "MpyyUipDb çizim şablonu",
                    ),
                )
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError('Veritabanı bütünlüğü doğrulanamadı: ' + str(integrity))
        os.replace(staged, output)
    finally:
        for item in staging.glob("*"):
            with contextlib.suppress(OSError):
                item.unlink()
        with contextlib.suppress(OSError):
            staging.rmdir()
    return str(output)


def import_template_style(layer, template_table, rename_layers=None):
    """Apply one frozen template layer definition to ``layer``.

    ``rename_layers`` maps template layer names used inside expressions
    (``overlay_intersects('uip-alanlar', ...)``) to the names in this project.
    """
    spec = template()["styles"][template_table]
    text = (TEMPLATE_DIR / spec["qml"]).read_text(encoding="utf-8")
    for old, new in (rename_layers or {}).items():
        text = text.replace(f"'{old}'", f"'{new}'")
    doc = QDomDocument("qgis")
    doc.setContent(text)
    ok, message = layer.importNamedStyle(doc)
    if not ok:
        raise RuntimeError(f"{layer.name()}: {message}")
    layer.setCustomProperty("mpyy/form", "MpyyUipDb çizim şablonu: " + template_table)
    layer.setCustomProperty("mpyy/template", template_table)
    layer.triggerRepaint()


def bind_function_relation(project, referencing, referenced, field_pairs, relation_id=None):
    """Create the project relation behind the uipfonksiyon dropdown and point the widget at it."""
    relation_id = relation_id or template()["relations"][0]["id"]
    manager = project.relationManager()
    if manager.relation(relation_id).isValid():
        manager.removeRelation(relation_id)
    relation = QgsRelation()
    relation.setId(relation_id)
    relation.setName('UİP fonksiyon kataloğu')
    relation.setReferencingLayer(referencing.id())
    relation.setReferencedLayer(referenced.id())
    for child, parent in field_pairs.items():
        relation.addFieldPair(child, parent)
    if not relation.isValid():
        raise RuntimeError('UİP fonksiyon ilişkisi kurulamadı: ' + relation.validationError())
    manager.addRelation(relation)
    for child in field_pairs:
        index = referencing.fields().indexFromName(child)
        setup = referencing.editorWidgetSetup(index)
        if setup.type() != "RelationReference":
            continue
        config = dict(setup.config())
        config.update(
            {
                "Relation": relation_id,
                "ReferencedLayerId": referenced.id(),
                "ReferencedLayerName": referenced.name(),
                "ReferencedLayerDataSource": referenced.source(),
                "ReferencedLayerProviderKey": referenced.providerType(),
            }
        )
        referencing.setEditorWidgetSetup(index, QgsEditorWidgetSetup("RelationReference", config))
    return relation


def load_local_uip_layers(path, project=None, dataset_id=None):
    """Load the template layers in the template's own tree order with their frozen definitions."""
    project = project or QgsProject.instance()
    spec = template()
    gpkg = str(Path(path).resolve())
    root = project.layerTreeRoot()
    group = root.findGroup(GROUP_NAME) or root.insertGroup(0, GROUP_NAME)
    layers = {}
    for name in spec["layer_order"]:
        layer = QgsVectorLayer(f"{gpkg}|layername={name}", name, "ogr")
        if not layer.isValid():
            raise RuntimeError('Katman açılamadı: ' + name)
        import_template_style(layer, name)
        layer.setCustomProperty("mpyy/workspace_kind", KIND)
        if dataset_id:
            layer.setCustomProperty("mpyy/dataset_id", dataset_id)
        project.addMapLayer(layer, False)
        group.addLayer(layer)
        layers[name] = layer
    for rel in spec["relations"]:
        bind_function_relation(project, layers[rel["referencing"]], layers[rel["referenced"]], rel["pairs"], rel["id"])
    return list(layers.values())
