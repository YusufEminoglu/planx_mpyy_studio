"""The local MpyyNipDB 1/5000 drawing template as a workspace kind.

Same contract as :mod:`local_uip_workspace`: the tables, styles, forms and the
function lookup rows are the ones frozen from the user's own GeoPackage by
``tools/extract_local_nip_template.py``; nothing here re-describes them. Only
the drawing layers were taken, not the base map or the in-force plan data.
"""

import contextlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from osgeo import ogr
from qgis.core import QgsProject, QgsVectorLayer
from qgis.PyQt.QtXml import QDomDocument

from .local_uip_workspace import _GEOMETRY, _crs_srs, _field_defn, bind_function_relation
from .schema import SCHEMA_VERSION

KIND = "YEREL_NIP"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "forms" / "yerel_nip"
GROUP_NAME = "Yerel NİP (MpyyNipDB şablonu)"
STYLE_NAME = "MpyyNipDB çizim şablonu"

_STALE_AUTHORING_IDS = {
    "alanlar_5000_036a85d6_1692_4ff4_a30f_a9f24e60068f": "alanlar-5000",
    "cizgiler_5000_v2_a86154de_7425_4232_a5be_f10abd851137": "cizgiler_5000_v2",
    "fonksiyonlar_5000_tablo_9eb58dc6_fc07_4e4c_b15b_cf0ffd2c07b5": "fonksiyonlar-5000_tablo",
}


def _normalize_nip_qml(text: str, rename_layers: dict | None = None) -> str:
    """Rewrite authoring-time layer UUIDs in memory while keeping disk QML hashes intact."""
    for old_id, canonical_name in _STALE_AUTHORING_IDS.items():
        text = text.replace(f"'{old_id}'", f"'{canonical_name}'")
    # Ensure aggregate filters match both trimmed and trailing-space lookup value for Çok Yüksek
    text = text.replace(
        "'GELİŞME KONUT ALANI (ÇOK YÜKSEK)', 'MEVCUT KONUT ALANI",
        "'GELİŞME KONUT ALANI (ÇOK YÜKSEK)', 'GELİŞME KONUT ALANI (ÇOK YÜKSEK) ', 'MEVCUT KONUT ALANI",
    )
    for old, new in (rename_layers or {}).items():
        text = text.replace(f"'{old}'", f"'{new}'")
    return text


def template():
    return json.loads((TEMPLATE_DIR / "template.json").read_text(encoding="utf-8"))


def _lookups():
    return json.loads((TEMPLATE_DIR / "lookups.json").read_text(encoding="utf-8"))


def create_local_nip_workspace(output_path, crs):
    """Create a GeoPackage with the MpyyNipDB template's exact tables, rows and styles."""
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
        source = ogr.GetDriverByName("GPKG").CreateDataSource(str(staged))
        if source is None:
            raise RuntimeError('GeoPackage oluşturulamadı')
        for table in spec["tables"]:
            geometry = table["geometry"]
            options = ["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES", "FID=fid"] if geometry else ["FID=fid"]
            layer = source.CreateLayer(table["table"], srs if geometry else None, _GEOMETRY[geometry], options=options)
            if layer is None:
                raise RuntimeError('Katman oluşturulamadı: ' + table["table"])
            for field in table["fields"]:
                if layer.CreateField(_field_defn(field["name"], field["type"])) != 0:
                    raise RuntimeError(f'Alan oluşturulamadı: {table["table"]}.{field["name"]}')
        for table, data in _lookups().items():
            layer = source.GetLayerByName(table)
            if layer is None:
                raise RuntimeError('Tablo bulunamadı: ' + table)
            for row in data["rows"]:
                feature = ogr.Feature(layer.GetLayerDefn())
                for column, value in zip(data["columns"], row):
                    if value is None:
                        feature.SetFieldNull(column)
                    else:
                        feature.SetField(column, value)
                if layer.CreateFeature(feature) != 0:
                    raise RuntimeError('Satır yazılamadı: ' + table)
        source = None

        with closing(sqlite3.connect(staged)) as con, con:
            con.execute(
                "CREATE TABLE mpyy_metadata (dataset_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                "workspace_kind TEXT NOT NULL, plan_levels TEXT NOT NULL)"
            )
            con.execute(
                "INSERT INTO mpyy_metadata VALUES (?,?,?,?)",
                (str(uuid.uuid4()), SCHEMA_VERSION, KIND, "NIP"),
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
                qml_text = _normalize_nip_qml(
                    (TEMPLATE_DIR / spec["styles"][name]["qml"]).read_text(encoding="utf-8")
                )
                con.execute(
                    "INSERT INTO layer_styles(f_table_catalog, f_table_schema, f_table_name, f_geometry_column, "
                    "styleName, styleQML, useAsDefault, description) VALUES ('', '', ?, ?, ?, ?, 1, ?)",
                    (
                        name,
                        "geom" if table["geometry"] else "",
                        name,
                        qml_text,
                        STYLE_NAME,
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
    """Apply one frozen MpyyNipDB layer definition to ``layer``."""
    spec = template()["styles"][template_table]
    text = _normalize_nip_qml(
        (TEMPLATE_DIR / spec["qml"]).read_text(encoding="utf-8"),
        rename_layers=rename_layers,
    )
    document = QDomDocument("qgis")
    parsed = document.setContent(text)
    if not (parsed[0] if isinstance(parsed, tuple) else parsed):
        raise ValueError(f"{template_table}: QML şablonu ayrıştırılamadı.")
    ok, message = layer.importNamedStyle(document)
    if not ok:
        raise RuntimeError(f"{layer.name()}: {message}")
    layer.setCustomProperty("mpyy/form", STYLE_NAME + ": " + template_table)
    layer.setCustomProperty("mpyy/template", template_table)
    layer.triggerRepaint()


def load_local_nip_layers(path, project=None, dataset_id=None):
    """Open every template layer of a local NİP workspace in the template's own order."""
    project = project or QgsProject.instance()
    spec = template()
    gpkg = str(Path(path).resolve())
    root = project.layerTreeRoot()
    group = root.findGroup(GROUP_NAME) or root.insertGroup(0, GROUP_NAME)
    loaded = {}
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
        loaded[name] = layer
    for relation in spec["relations"]:
        referencing, referenced = loaded.get(relation["referencing"]), loaded.get(relation["referenced"])
        if referencing is not None and referenced is not None:
            bind_function_relation(project, referencing, referenced, relation["pairs"], relation["id"])
    return list(loaded.values())
