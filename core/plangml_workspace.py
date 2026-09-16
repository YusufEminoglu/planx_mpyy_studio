"""PlanGML çalışma alanı: Bakanlığın PlanGML 1.1.7 XSD şemasından birebir GeoPackage.

One table per member of the schema's ``plan:features`` collection, named exactly
like the GML element. Fields keep the XSD element names, order and types; code
lists become dropdowns that store the schema's own enumeration value;
``minOccurs="1"`` becomes a not-null constraint. The structure comes only from
``styles/plangml_schema.json`` (compiled by ``tools/compile_plangml_schema.py``).

Not-null constraints are *soft*: QGIS warns but lets a draft be saved, because
a plan is drawn before every attribute is known. Conformance of a finished plan
is reported by :func:`audit_required_fields`.

Symbology is the Ministry's own e-Plan GeoServer SLD for the same feature type,
compiled by ``tools/compile_plangml_eplan_styles.py`` with its filters rewritten
to this schema. QGIS' SLD reader turns ``ttf://`` marks into plain circles, so
those markers are restored from the SLD; tarama images are embedded in the
style so a GeoPackage stays portable. Types without an official SLD stay neutral.
"""

import base64
import contextlib
import json
import tempfile
import os
import re
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from osgeo import gdal, ogr
from qgis.core import (
    Qgis,
    QgsEditorWidgetSetup,
    QgsFieldConstraints,
    QgsFontMarkerSymbolLayer,
    QgsProject,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QColor

from .schema import SCHEMA_VERSION

gdal.UseExceptions()

KIND = "PLANGML_XSD"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "styles" / "plangml_schema.json"
SLD_DIR = PLUGIN_ROOT / "styles" / "plangml_sld"
TARAMA_PLACEHOLDER = "mpyy-tarama:"
LEVEL_TITLES = {
    "UIP": "Uygulama imar planı (UİP)",
    "NIP": "Nazım imar planı (NİP)",
    "CDP": "Çevre düzeni planı (ÇDP)",
}
QGIS_NULL = "{2839923C-8B7D-419E-B84B-CA2FE9B80EC7}"

_OGR_GEOMETRY = {
    "MultiPolygon": ogr.wkbMultiPolygon,
    "Polygon": ogr.wkbPolygon,
    "LineString": ogr.wkbLineString,
    "MultiLineString": ogr.wkbMultiLineString,
    "Point": ogr.wkbPoint,
    None: ogr.wkbNone,
}
_OGR_FIELD = {
    "string": ogr.OFTString,
    "enum": ogr.OFTString,
    "double": ogr.OFTReal,
    "int": ogr.OFTInteger,
    "long": ogr.OFTInteger64,
    "dateTime": ogr.OFTDateTime,
}
_GROUPS = (
    ("Alanlar", ("MultiPolygon", "Polygon")),
    ("Çizgiler", ("LineString", "MultiLineString")),
    ("Noktalar", ("Point",)),
    ("Tablolar", (None,)),
)


def catalog():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def level_schema(level):
    levels = catalog()["levels"]
    if level not in levels:
        raise ValueError('PlanGML şemasında olmayan plan kademesi: ' + str(level))
    return levels[level]


def caption(code):
    """Readable caption for a schema identifier without changing its spelling."""
    text = re.sub(r"(?<=[a-zçğıöşü0-9])(?=[A-ZÇĞİÖŞÜ])", " ", str(code))
    return re.sub(r"(?<=[A-Za-z])(?=[0-9])|(?<=[0-9])(?=[A-Za-z])", " ", text)


def _ordered_fields(feature_type):
    # symbolizer is an optional rendering hint inherited by every type; keep it last in forms.
    fields = [f for f in feature_type["fields"] if f["name"] != "symbolizer"]
    return fields + [f for f in feature_type["fields"] if f["name"] == "symbolizer"]


def create_plangml_workspace(output_path, crs, level):
    """Create an empty GeoPackage whose tables are the PlanGML feature types of ``level``."""
    output = Path(output_path).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    if output.suffix.lower() != ".gpkg":
        raise ValueError('Çıktı .gpkg uzantısını kullanmalıdır')
    schema = level_schema(level)
    source = catalog()["source"]
    from .db_factory import _crs

    srs = _crs(crs)
    staging = output.parent / (".mpyy-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / "dataset.gpkg"
    try:
        ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(staged))
        if ds is None:
            raise RuntimeError('GeoPackage oluşturulamadı')
        for feature_type in schema["feature_types"]:
            geometry = feature_type["geometry"]
            options = ["FID=fid"] + (["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES"] if geometry else [])
            layer = ds.CreateLayer(
                feature_type["name"], srs if geometry else None, _OGR_GEOMETRY[geometry], options=options
            )
            if layer is None:
                raise RuntimeError('Katman oluşturulamadı: ' + feature_type["name"])
            for field in _ordered_fields(feature_type):
                if layer.CreateField(ogr.FieldDefn(field["name"], _OGR_FIELD[field["type"]])) != 0:
                    raise RuntimeError(f'Alan oluşturulamadı: {feature_type["name"]}.{field["name"]}')
        ds = None

        with closing(sqlite3.connect(staged)) as con, con:
            con.execute(
                "CREATE TABLE mpyy_metadata (dataset_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                "workspace_kind TEXT NOT NULL, plan_levels TEXT NOT NULL)"
            )
            con.execute("INSERT INTO mpyy_metadata VALUES (?,?,?,?)", (str(uuid.uuid4()), SCHEMA_VERSION, KIND, level))
            con.execute(
                "CREATE TABLE plangml_sema (plan_kademesi TEXT PRIMARY KEY, xsd_dosyasi TEXT NOT NULL, "
                "xsd_sha256 TEXT NOT NULL, hedef_ad_alani TEXT NOT NULL, kaynak_url TEXT NOT NULL, "
                "arsiv_sha256 TEXT NOT NULL)"
            )
            con.execute(
                "INSERT INTO gpkg_contents(table_name, data_type, identifier) "
                "VALUES ('plangml_sema', 'attributes', 'PlanGML şema kaynağı')"
            )
            con.execute(
                "INSERT INTO plangml_sema VALUES (?,?,?,?,?,?)",
                (
                    level,
                    schema["xsd"]["file"],
                    schema["xsd"]["sha256"],
                    schema["target_namespace"],
                    source["url"],
                    source["sha256"],
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

    _store_default_forms(output, schema)
    return str(output)


def configure_plangml_layer(layer, feature_type, codelists):
    """Dropdowns, captions and required-field checks straight from the schema."""
    fields = layer.fields()
    fid = fields.indexFromName("fid")
    if fid >= 0:
        layer.setEditorWidgetSetup(fid, QgsEditorWidgetSetup("Hidden", {}))
    missing = []
    for field in feature_type["fields"]:
        index = fields.indexFromName(field["name"])
        if index < 0:
            # A workspace created with an older PlanGML version; the audit reports it.
            missing.append(field["name"])
            continue
        layer.setFieldAlias(index, caption(field["name"]))
        if field["type"] == "enum":
            entries = [] if field["required"] else [{"(boş)": QGIS_NULL}]
            entries += [{caption(code): code} for code in codelists[field["codelist"]]]
            layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup("ValueMap", {"map": entries}))
        elif field["type"] == "dateTime":
            layer.setEditorWidgetSetup(
                index,
                QgsEditorWidgetSetup(
                    "DateTime",
                    {"allow_null": not field["required"], "calendar_popup": True,
                     "display_format": "dd.MM.yyyy HH:mm", "field_format": "yyyy-MM-ddTHH:mm:ss",
                     "field_iso_format": True},
                ),
            )
        if field["required"]:
            layer.setFieldConstraint(
                index, QgsFieldConstraints.Constraint.ConstraintNotNull,
                QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft,
            )
            if field["type"] == "enum":
                allowed = ", ".join("'" + code.replace("'", "''") + "'" for code in codelists[field["codelist"]])
                layer.setConstraintExpression(
                    index, f'"{field["name"]}" IS NULL OR "{field["name"]}" IN ({allowed})',
                    f'{caption(field["name"])}: PlanGML kod listesinde olmayan değer.',
                )
    layer.setCustomProperty("mpyy/schema_missing_fields", ", ".join(missing))
    layer.setCustomProperty("mpyy/form", "PlanGML şeması: " + feature_type["name"])
    layer.setCustomProperty("mpyy/template", "plangml:" + feature_type["name"])
    layer.setCustomProperty("mpyy/workspace_kind", KIND)


def _store_default_forms(path, schema):
    """Save each layer's form as the GeoPackage default style so plain QGIS gets the dropdowns too."""
    for feature_type in schema["feature_types"]:
        layer = QgsVectorLayer(f"{path}|layername={feature_type['name']}", feature_type["name"], "ogr")
        if not layer.isValid():
            raise RuntimeError('Katman açılamadı: ' + feature_type["name"])
        configure_plangml_layer(layer, feature_type, schema["codelists"])
        apply_eplan_symbology(layer, schema_level(schema), feature_type["name"])
        apply_line_labels(layer, schema_level(schema), feature_type["name"])
        # layer_styles.styleName is TEXT(30); the table name already identifies the row.
        message = layer.saveStyleToDatabase("PlanGML " + schema["xsd"]["file"].split(".V.")[1][:-4], "PlanGML şeması formu", True, "")
        if message:
            raise RuntimeError(f'{feature_type["name"]}: stil kaydedilemedi: {message}')
        del layer


def load_plangml_layers(path, project=None, dataset_id=None, level=None):
    project = project or QgsProject.instance()
    if level is None:
        with closing(sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)) as con:
            level = con.execute("SELECT plan_kademesi FROM plangml_sema").fetchone()[0]
    schema = level_schema(level)
    gpkg = str(Path(path).resolve())
    root = project.layerTreeRoot()
    title = f'PlanGML {LEVEL_TITLES.get(level, level)}'
    base = root.findGroup(title) or root.insertGroup(0, title)
    loaded = []
    for group_name, geometries in _GROUPS:
        members = sorted(
            (t for t in schema["feature_types"] if t["geometry"] in geometries), key=lambda t: t["name"]
        )
        if not members:
            continue
        group = base.findGroup(group_name) or base.addGroup(group_name)
        group.setExpanded(False)
        for feature_type in members:
            layer = QgsVectorLayer(f"{gpkg}|layername={feature_type['name']}", feature_type["name"], "ogr")
            if not layer.isValid():
                raise RuntimeError('Katman açılamadı: ' + feature_type["name"])
            configure_plangml_layer(layer, feature_type, schema["codelists"])
            if not isinstance(layer.renderer(), QgsRuleBasedRenderer):
                apply_eplan_symbology(layer, level, feature_type["name"])  # default style missing or replaced
            if not layer.labelsEnabled():
                apply_line_labels(layer, level, feature_type["name"])
            if dataset_id:
                layer.setCustomProperty("mpyy/dataset_id", dataset_id)
            project.addMapLayer(layer, False)
            group.addLayer(layer)
            loaded.append(layer)
    return loaded


def audit_required_fields(layers):
    """Count features whose schema-required attributes are empty, per layer."""
    report = {}
    for layer in layers:
        name = str(layer.customProperty("mpyy/template") or "")
        if not name.startswith("plangml:"):
            continue
        required = [
            layer.fields().at(i).name()
            for i in range(layer.fields().count())
            if layer.fields().at(i).constraints().constraints() & QgsFieldConstraints.Constraint.ConstraintNotNull
        ]
        missing = {}
        for feature in layer.getFeatures():
            for field in required:
                value = feature[field]
                if value is None or value == "" or (hasattr(value, "isNull") and value.isNull()):
                    missing[field] = missing.get(field, 0) + 1
        if missing:
            report[layer.name()] = missing
    return report


def schema_level(schema):
    return next(level for level, compiled in catalog()["levels"].items() if compiled["xsd"] == schema["xsd"])


def _sld_marks(sld_text):
    """Per rule, the marks in document order: (family, character) for ttf marks, None otherwise."""
    from qgis.PyQt.QtXml import QDomDocument

    doc = QDomDocument()
    doc.setContent(sld_text, True)  # namespace aware
    sld = "http://www.opengis.net/sld"
    rules = []
    rule_nodes = doc.elementsByTagNameNS(sld, "Rule")
    for i in range(rule_nodes.count()):
        marks = []
        mark_nodes = rule_nodes.at(i).toElement().elementsByTagNameNS(sld, "Mark")
        for j in range(mark_nodes.count()):
            name = mark_nodes.at(j).toElement().firstChildElement("WellKnownName").text()
            found = re.match(r"ttf://(?P<family>[^#]+)#0x(?P<code>[0-9A-Fa-f]+)", name)
            marks.append((found.group("family"), chr(int(found.group("code"), 16))) if found else None)
        rules.append(marks)
    return rules


def _marker_slots(symbol):
    """(owner symbol, index) of every marker symbol layer, depth first, in drawing order."""
    slots = []
    for index in range(symbol.symbolLayerCount()):
        layer = symbol.symbolLayer(index)
        if layer.type() == Qgis.SymbolType.Marker:
            slots.append((symbol, index))
        sub = layer.subSymbol()
        if sub is not None:
            slots.extend(_marker_slots(sub))
    return slots


def apply_eplan_symbology(layer, level, type_name):
    """Apply the official SLD of this PlanGML type; returns False when the Ministry set has none."""
    source = SLD_DIR / level / f"{type_name}.sld"
    if not source.exists():
        return _apply_catalog_symbol(layer, level, type_name)
    from .fonts import register_mpyy_fonts

    register_mpyy_fonts()
    text = source.read_text(encoding="utf-8").replace(TARAMA_PLACEHOLDER, (PLUGIN_ROOT / "resources").as_uri() + "/")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"{type_name}.sld"
        path.write_text(text, encoding="utf-8")
        message, ok = layer.loadSldStyle(str(path))
    if not ok or not isinstance(layer.renderer(), QgsRuleBasedRenderer):
        # e.g. UIP_YOLORTA only carries text symbolizers, which QGIS cannot turn into a renderer.
        layer.setCustomProperty("mpyy/symbology", "e-Plan SLD QGIS'e aktarılamadı: " + level + "/" + type_name)
        return False

    root = layer.renderer().rootRule()
    marks = _sld_marks(text)
    for rule, rule_marks in zip(root.children(), marks):
        symbol = rule.symbol()
        if symbol is None:
            continue
        slots = _marker_slots(symbol)
        if len(slots) == len(rule_marks):
            for (owner, index), mark in zip(slots, rule_marks):
                if mark is None:
                    continue
                old = owner.symbolLayer(index)
                font = QgsFontMarkerSymbolLayer(mark[0], mark[1], old.size(), old.color(), old.angle())
                font.setSizeUnit(old.sizeUnit())
                font.setStrokeWidth(0)
                font.setStrokeColor(QColor(0, 0, 0, 0))
                owner.changeSymbolLayer(index, font)
        _embed_images(symbol)

    fallback = QgsSymbol.defaultSymbol(layer.geometryType())
    fallback.setColor(QColor("#9aa3ab"))
    else_rule = QgsRuleBasedRenderer.Rule(fallback, 0, 0, "ELSE", "Kodu girilmemiş / resmî gösterimi yok")
    root.appendChild(else_rule)
    layer.setCustomProperty("mpyy/symbology", "e-Plan SLD: " + level + "/" + type_name)
    layer.triggerRepaint()
    return True


def _embed_images(symbol):
    for index in range(symbol.symbolLayerCount()):
        layer = symbol.symbolLayer(index)
        if layer.layerType() == "RasterFill":
            path = layer.imageFilePath()
            if path.startswith("file:"):
                from qgis.PyQt.QtCore import QUrl

                path = QUrl(path).toLocalFile()
            if path and not path.startswith("base64:") and Path(path).is_file():
                layer.setImageFilePath("base64:" + base64.b64encode(_png_bytes(Path(path))).decode("ascii"))
        sub = layer.subSymbol()
        if sub is not None:
            _embed_images(sub)


def _png_bytes(path):
    """Most Ministry tiles are uncompressed BMP despite the .png name; re-encode losslessly as PNG."""
    from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice
    from qgis.PyQt.QtGui import QImage

    image = QImage(str(path))
    if image.isNull():
        return path.read_bytes()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    encoded = bytes(data)
    return encoded if encoded and len(encoded) < path.stat().st_size else path.read_bytes()


def _apply_catalog_symbol(layer, level, type_name):
    """Types absent from the Ministry SLD set, drawn from the detail catalog's line definition."""
    decisions = json.loads((SLD_DIR / "decisions.json").read_text(encoding="utf-8"))
    spec = decisions.get("catalog_symbols", {}).get(level, {}).get(type_name)
    if not spec:
        return False
    from qgis.core import (
        QgsFillSymbol,
        QgsLineSymbol,
        QgsMarkerLineSymbolLayer,
        QgsMarkerSymbol,
        QgsSimpleLineSymbolLayer,
        QgsSimpleMarkerSymbolLayer,
        QgsSingleSymbolRenderer,
    )

    color = QColor(*[int(v) for v in spec["rgb"].split("/")])
    millimeters = Qgis.RenderUnit.Millimeters
    carrier = QgsSimpleLineSymbolLayer(color, spec["line_width_mm"])
    carrier.setWidthUnit(millimeters)
    layers = [carrier]
    cursor, markers = 0.0, []
    for part in spec["pattern"]:
        if part["kind"] == "circle":
            markers.append((cursor + part["diameter_mm"] / 2, part))
            cursor += part["diameter_mm"]
        else:
            cursor += part["length_mm"]
    for center, part in markers:
        circle = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Circle, part["diameter_mm"])
        circle.setSizeUnit(millimeters)
        circle.setColor(color if part["filled"] else QColor("white"))
        circle.setStrokeColor(color)
        circle.setStrokeWidth(spec["line_width_mm"])
        circle.setStrokeWidthUnit(millimeters)
        line = QgsMarkerLineSymbolLayer(False, cursor)
        line.setIntervalUnit(millimeters)
        line.setOffsetAlongLine(center)
        line.setOffsetAlongLineUnit(millimeters)
        line.setSubSymbol(QgsMarkerSymbol([circle]))
        layers.append(line)
    if layer.geometryType() == Qgis.GeometryType.Polygon:
        from qgis.core import QgsGeometryGeneratorSymbolLayer

        symbol = QgsFillSymbol()
        symbol.deleteSymbolLayer(0)
        outline = QgsGeometryGeneratorSymbolLayer.create({"geometryModifier": "boundary($geometry)", "SymbolType": "Line"})
        outline.setSubSymbol(QgsLineSymbol(layers))
        symbol.appendSymbolLayer(outline)
    else:
        symbol = QgsLineSymbol(layers)
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.setCustomProperty("mpyy/symbology", "Detay kataloğu: " + level + "/" + type_name)
    layer.triggerRepaint()
    return True


def apply_line_labels(layer, level, type_name):
    """Boundary abbreviations (A1, KS, YKK ...) written along the line, as the detail catalog requires.

    Returns the number of label rules; 0 when this type carries no catalog abbreviation."""
    from qgis.core import (
        QgsPalLayerSettings,
        QgsRuleBasedLabeling,
        QgsTextBufferSettings,
        QgsTextFormat,
    )

    table = json.loads((PLUGIN_ROOT / "styles" / "plangml_line_labels.json").read_text(encoding="utf-8"))
    rules = [r for r in table["levels"].get(level, {}).values() if r["feature"] == type_name]
    if not rules:
        return 0
    root = QgsRuleBasedLabeling.Rule(None)
    polygon = layer.geometryType() == Qgis.GeometryType.Polygon
    for rule in rules:
        settings = QgsPalLayerSettings()
        settings.fieldName = "'" + rule["text"].replace("'", "''") + "'"
        settings.isExpression = True
        settings.placement = Qgis.LabelPlacement.PerimeterCurved if polygon else Qgis.LabelPlacement.Curved
        settings.repeatDistance = 60
        settings.repeatDistanceUnit = Qgis.RenderUnit.Millimeters
        line_settings = settings.lineSettings()
        line_settings.setPlacementFlags(Qgis.LabelLinePlacementFlag.OnLine)
        settings.setLineSettings(line_settings)
        text_format = QgsTextFormat()
        text_format.setSize(2.5)
        text_format.setSizeUnit(Qgis.RenderUnit.Millimeters)
        text_format.setColor(QColor(rule["color"]))
        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(0.6)
        buffer.setSizeUnit(Qgis.RenderUnit.Millimeters)
        buffer.setColor(QColor("white"))
        text_format.setBuffer(buffer)
        settings.setFormat(text_format)
        child = QgsRuleBasedLabeling.Rule(settings)
        child.setDescription(rule["text"] + " — " + rule["kaynak"])
        if rule["field"]:
            child.setFilterExpression('"{}" = \'{}\''.format(rule["field"], rule["code"].replace("'", "''")))
        root.appendChild(child)
    layer.setLabeling(QgsRuleBasedLabeling(root))
    layer.setLabelsEnabled(True)
    layer.setCustomProperty("mpyy/line_labels", ", ".join(r["text"] for r in rules))
    layer.triggerRepaint()
    return len(rules)
