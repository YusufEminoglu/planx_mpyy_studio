"""The MSP (Mekânsal Strateji Planı) workspace as a workspace kind.

Unlike the UİP/NİP/ÇDP workspaces there is no MSP schema to compile: the MPYY
1.1.7 XSD set carries UİP, NİP and ÇDP only.  The Ek-1e MSP annex is therefore
the definition, and this module turns it into a GeoPackage -- one layer per
official group and geometry, each with the annex's own codes in a dropdown, plus
the two companion tables an MSP file needs: the catalogue it was drawn from and
the Article 16 action-plan table ``core.msp_monitoring`` evaluates.

The layers carry what ``core.plan_stage_audit`` demands of an MSP decision and
nothing of what it forbids: ``global_id``, ``plan_id`` and ``plan_kademesi``, a
classification (``gosterim_adi``, and ``msp_kodu`` which the annex defines), and
``strateji_bolgesi`` -- the annex's own seven-way group, which is also what
covers the six themes the audit scores.  No parcel-level implementation field
(TAKS, KAKS, nizam, çekme mesafeleri) is created, because an MSP is not a
parcel-level plan and the audit rejects those fields above UİP.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from osgeo import ogr
from qgis.core import (
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsFieldConstraints,
    QgsProject,
    QgsVectorLayer,
)

from .localization import field_alias
from .legend_scope import limit_to_present, watch as watch_legend
from .msp_catalog import (
    ACTION_TABLE,
    CATALOG_TABLE,
    PLAN_KADEMESI,
    class_rule,
    decode_rows,
    groups,
    msp_layer_specs,
    rows_for_layer,
    rows as catalog_rows,
)
from .msp_styler import annotate_layer
from .schema import SCHEMA_VERSION

KIND = "MSP_EK1E"
GROUP_NAME = "MSP (Mekânsal Strateji Planı)"
TABLE_GROUP_NAME = "MSP katalog ve izleme"
CATALOG_LAYER_NAME = "MSP Ek-1e kataloğu"
ACTION_LAYER_NAME = "MSP eylem planı (Madde 16)"
STYLE_NAME = "MSP Ek-1e kataloğu"

#: Every drawing layer's fields, in the order they are created.  Read back by
#: ``tests/test_msp_workspace_qgis.py`` through this list, so a field added here
#: but not written, or written in another order, fails there.
LAYER_FIELDS = (
    "global_id",
    "plan_id",
    "plan_kademesi",
    "msp_kodu",
    "gosterim_adi",
    "strateji_bolgesi",
    # MSP-002 ("YERLEŞMELER VE KADEMELENMESİ") is the one annex row whose mark is
    # not a single symbol: EK-1b draws it as three bullseyes of increasing size
    # and its note says the settlement's *tier* picks the size and its *density*
    # picks the tone.  Two fields therefore carry what one code cannot, and they
    # are named with the annex's own words.  They are on every layer, not only on
    # the one that draws MSP-002: the template's single field list is what the
    # workspace test reads back, and a per-layer list would split that contract.
    "yerlesme_kademesi",
    "yerlesme_yogunlugu",
    "oncelik_durumu",
    "aciklama",
)


#: The companion catalogue table's columns and the annex field each comes from.
#: The annex's own names are kept where they are readable; the rest are Turkish
#: so the table reads like the annex page it was extracted from.
CATALOG_COLUMNS = (
    ("id", "id"),
    ("sayfa", "page"),
    ("detay_adi", "detay_adi"),
    ("detay_sinifi", "detay_sinifi"),
    ("detay_alt_sinifi", "detay_alt_sinifi"),
    ("gosterim", "gosterim"),
    ("geometri", "geometri"),
    ("sembol_rgb", "sembol_rgb"),
    ("tarama_rgb", "tarama_rgb"),
    ("tarama_alpha", "tarama_alpha"),
    ("sinir_rgb", "sinir_rgb"),
    ("sinir_kalinligi_mm", "stroke_width_mm"),
    ("sinir_tanimi", "stroke_desc"),
    ("tarama_tanimi", "hatch_desc"),
    # EK-1b'den gelen yedi alan.  Ekin *çizdiği* sütunlar yalnızca oradadır:
    # simgenin şekli, mürekkebi, ölçülmüş çapı, hedefin iç içe diskleri ve
    # tarama ekseni.  Tabloda duruyorlar çünkü GeoPackage'ı düz QGIS'te açan
    # kişi çizicinin neye uyduğunu eklentiyi açmadan okuyabilmeli -- ekin kendi
    # sütunlarının burada durmasının nedeni de aynı.
    ("sembol_sekli", "sembol_sekli"),
    ("sembol_dolgu", "sembol_dolgu"),
    ("sembol_ikon", "sembol_ikon"),
    ("sembol_boyut_mm", "sembol_boyut_mm"),
    ("sembol_halkalar", "sembol_halkalar"),
    ("tarama_aci_derece", "tarama_aci_derece"),
    ("sinif_kurali", "sinif_kurali"),
)


def catalog_cell(value):
    """A catalogue value as the companion table stores it.

    Most values are strings and numbers and pass straight through.  Two are
    structures -- the bullseye's nested discs and MSP-002's class rule -- and
    those are stored as the catalogue's own JSON text rather than flattened, so
    nothing is lost between the file the compiler writes and the table a reader
    opens.  The storage test normalises through this same function, which is
    what keeps the INSERT and the comparison from drifting apart.
    """
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value

#: The action-plan table.  The first five are what an MPYY layer needs; the rest
#: are read by name, lower-cased, by ``core.msp_monitoring``.
ACTION_FIELDS = (
    ("global_id", ogr.OFTString),
    ("plan_id", ogr.OFTString),
    ("plan_kademesi", ogr.OFTString),
    ("action_id", ogr.OFTString),
    ("eylem_adi", ogr.OFTString),
    ("aciklama", ogr.OFTString),
    ("baseline_value", ogr.OFTReal),
    ("target_value", ogr.OFTReal),
    ("actual_value", ogr.OFTReal),
    ("weight", ogr.OFTReal),
    ("due_date", ogr.OFTString),
    ("responsible_institution", ogr.OFTString),
)

_GEOMETRY = {
    "POLYGON": ogr.wkbMultiPolygon,
    "LINE": ogr.wkbMultiLineString,
    "POINT": ogr.wkbPoint,
}


def _geometry_name_of(layer):
    from qgis.core import QgsWkbTypes

    return {
        QgsWkbTypes.GeometryType.PolygonGeometry: "POLYGON",
        QgsWkbTypes.GeometryType.LineGeometry: "LINE",
        QgsWkbTypes.GeometryType.PointGeometry: "POINT",
    }.get(layer.geometryType())


def layer_specs():
    return msp_layer_specs(decode_rows())


def create_msp_workspace(output_path, crs):
    """Create an MSP GeoPackage: one layer per annex group and geometry."""
    from .db_factory import _crs

    output = Path(output_path).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    if output.suffix.lower() != ".gpkg":
        raise ValueError('Çıktı .gpkg uzantısını kullanmalıdır')
    specs = layer_specs()
    srs = _crs(crs)
    staging = output.parent / (".mpyy-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / "dataset.gpkg"
    try:
        source = ogr.GetDriverByName("GPKG").CreateDataSource(str(staged))
        if source is None:
            raise RuntimeError('GeoPackage oluşturulamadı')
        for spec in specs:
            layer = source.CreateLayer(
                spec.name,
                srs,
                _GEOMETRY[spec.geometry],
                options=["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES", "FID=fid"],
            )
            if layer is None:
                raise RuntimeError('Katman oluşturulamadı: ' + spec.name)
            for name in LAYER_FIELDS:
                if layer.CreateField(ogr.FieldDefn(name, ogr.OFTString)) != 0:
                    raise RuntimeError(f'Alan oluşturulamadı: {spec.name}.{name}')
        # The catalogue table is created in SQL further down, with the typed columns
        # the annex needs; OGR only creates the action table, whose types are ogr's.
        table = source.CreateLayer(ACTION_TABLE, None, ogr.wkbNone, options=["FID=fid"])
        if table is None:
            raise RuntimeError('Tablo oluşturulamadı: ' + ACTION_TABLE)
        for field_name, field_type in ACTION_FIELDS:
            if table.CreateField(ogr.FieldDefn(field_name, field_type)) != 0:
                raise RuntimeError(f'Alan oluşturulamadı: {ACTION_TABLE}.{field_name}')
        source = None

        with closing(sqlite3.connect(staged)) as con, con:
            con.execute(
                "CREATE TABLE mpyy_metadata (dataset_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
                "workspace_kind TEXT NOT NULL, plan_levels TEXT NOT NULL)"
            )
            con.execute(
                "INSERT INTO mpyy_metadata VALUES (?,?,?,?)",
                (str(uuid.uuid4()), SCHEMA_VERSION, KIND, PLAN_KADEMESI),
            )
            _store_catalog(con)
            # The action table is an OGR-created layer, so gpkg_contents already
            # lists it; only the SQL-created catalogue table needs registering.
            con.execute(
                "INSERT INTO gpkg_contents(table_name, data_type, identifier) VALUES (?,?,?)",
                (CATALOG_TABLE, "attributes", "MSP Ek-1e detay kataloğu"),
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

    _store_default_styles(output)
    return str(output)


def _store_catalog(connection):
    """Write the 28 annex rows into the workspace's companion table."""
    # One literal statement, column list included, rather than a string built from
    # CATALOG_COLUMNS: the Hub's Bandit gate reads any SQL whose text is assembled
    # at run time as an injection vector and blocks the upload (B608).  The literal
    # column list and CATALOG_COLUMNS must stay in step -- the acceptance test reads
    # every column back through CATALOG_COLUMNS and compares row by row against
    # styles/msp_catalog.json, so a swap fails there rather than writing each
    # annex field into its neighbour's column.
    connection.execute(
        "CREATE TABLE msp_katalogu (id TEXT PRIMARY KEY, sayfa INTEGER NOT NULL, "
        "detay_adi TEXT NOT NULL, detay_sinifi TEXT NOT NULL, detay_alt_sinifi TEXT NOT NULL, "
        "gosterim TEXT NOT NULL, geometri TEXT NOT NULL, sembol_rgb TEXT, tarama_rgb TEXT, "
        "tarama_alpha INTEGER NOT NULL, "
        "sinir_rgb TEXT, sinir_kalinligi_mm REAL NOT NULL, sinir_tanimi TEXT, tarama_tanimi TEXT, "
        "sembol_sekli TEXT, sembol_dolgu TEXT, sembol_ikon TEXT, sembol_boyut_mm REAL, "
        "sembol_halkalar TEXT, tarama_aci_derece REAL, sinif_kurali TEXT)"
    )
    connection.executemany(
        "INSERT INTO msp_katalogu "
        "(id, sayfa, detay_adi, detay_sinifi, detay_alt_sinifi, gosterim, geometri, "
        "sembol_rgb, tarama_rgb, tarama_alpha, sinir_rgb, sinir_kalinligi_mm, "
        "sinir_tanimi, tarama_tanimi, sembol_sekli, sembol_dolgu, sembol_ikon, "
        "sembol_boyut_mm, sembol_halkalar, tarama_aci_derece, sinif_kurali) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            tuple(catalog_cell(row[source]) for _, source in CATALOG_COLUMNS)
            for row in catalog_rows()
        ],
    )


def _class_entries(values, label: str) -> list[dict[str, str]]:
    """One ValueMap entry per class the annex printed, keyed 1..n as text.

    The count comes from the annex's own rule and not from a list here, so the
    dropdown can never offer a class the drawing has no tone or size for.  The key
    is the string QGIS stores in a text field, and ``msp_styler`` reads these
    back through ``to_int`` so the same number means the same class on both sides.
    """

    return [
        {f"{index + 1}. {label}": str(index + 1)}
        for index in range(len(values or ()))
    ]


def configure_msp_layer(layer, spec=None):
    """Dropdowns, defaults and required-field checks straight from the annex."""
    spec = spec or next((item for item in layer_specs() if item.name == layer.name()), None)
    fields = layer.fields()
    for name in LAYER_FIELDS:
        index = fields.indexFromName(name)
        if index < 0:
            continue
        layer.setFieldAlias(index, field_alias(name))
    gid = fields.indexFromName("global_id")
    if gid >= 0:
        layer.setDefaultValueDefinition(
            gid, QgsDefaultValue("replace(replace(uuid(),'{',''),'}','')")
        )
    kademe = fields.indexFromName("plan_kademesi")
    if kademe >= 0:
        layer.setDefaultValueDefinition(kademe, QgsDefaultValue(f"'{PLAN_KADEMESI}'"))
    if spec is not None:
        rule = class_rule()
        entries_by_field = {
            "yerlesme_kademesi": _class_entries(rule.get("simge_boyutlari_mm"), "kademe"),
            "yerlesme_yogunlugu": _class_entries(rule.get("tonlar"), "yoğunluk"),
        }
        for name, entries in (
            ("msp_kodu", [{code.caption: code.id} for code in spec.codes]),
            ("gosterim_adi", [{code.detay_adi: code.detay_adi} for code in spec.codes]),
            ("strateji_bolgesi", [{group: group} for group in groups()]),
            *entries_by_field.items(),
        ):
            index = fields.indexFromName(name)
            if index >= 0:
                layer.setEditorWidgetSetup(
                    index, QgsEditorWidgetSetup("ValueMap", {"map": entries})
                )
    for name in ("global_id", "plan_id", "plan_kademesi", "msp_kodu"):
        index = fields.indexFromName(name)
        if index >= 0:
            layer.setFieldConstraint(
                index,
                QgsFieldConstraints.Constraint.ConstraintNotNull,
                QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft,
            )
    if spec is not None:
        # Record the substitutions here as well as in the renderer: a custom
        # property does not survive in a saved style, so a workspace reopened
        # without the MSP style being re-applied would otherwise forget which of
        # its codes are drawn as the annex states and which are not.
        annotate_layer(layer, spec, rows_for_layer(decode_rows(), spec))
    layer.setCustomProperty("mpyy/form", "MSP Ek-1e kataloğu: " + layer.name())
    # Set, so the localization pass leaves the annex's own captions verbatim: the
    # dropdown entries are official text, not plugin labels to be translated.
    layer.setCustomProperty("mpyy/template", "msp:" + layer.name())
    layer.setCustomProperty("mpyy/workspace_kind", KIND)
    layer.setCustomProperty("mpyy/plan_kademesi", PLAN_KADEMESI)


def _store_default_styles(path):
    """Render and save each layer's style as the GeoPackage default."""
    from .msp_styler import MSPStylerEngine

    engine = MSPStylerEngine()
    for spec in layer_specs():
        layer = QgsVectorLayer(f"{path}|layername={spec.name}", spec.name, "ogr")
        if not layer.isValid():
            raise RuntimeError('Katman açılamadı: ' + spec.name)
        configure_msp_layer(layer, spec)
        engine.apply(layer)
        # layer_styles.styleName is TEXT(30); the layer name already identifies the row.
        message = layer.saveStyleToDatabase(STYLE_NAME, "MSP Ek-1e kataloğu", True, "")
        if message:
            raise RuntimeError(f'{spec.name}: stil kaydedilemedi: {message}')
        del layer


def configure_msp_action_table(table):
    """Entry for the Article 16 action plan, matched to what core.msp_monitoring reads.

    The monitoring counts an action only with a *positive* weight and a
    ``YYYY-MM-DD`` due date; anything else becomes MISSING_DATA. So the weight
    gets a range widget that cannot go to zero or below, and the due date a
    calendar that writes exactly that text. Baseline, target and actual values
    stay unbounded on purpose: a reduction target is legitimately below its
    baseline, and a value can be negative.
    """
    fields = table.fields()
    weight = fields.indexFromName("weight")
    if weight >= 0:
        table.setEditorWidgetSetup(weight, QgsEditorWidgetSetup(
            "Range", {"Min": 0.0, "Max": 1000000.0, "Step": 0.1, "Precision": 2,
                      "AllowNull": True, "Style": "SpinBox"}))
        table.setConstraintExpression(
            weight, '"weight" IS NULL OR "weight" > 0',
            "Ağırlık 0'dan büyük olmalı; izleme ağırlığı 0 olan eylemi hesaba katmaz.")
        table.setFieldConstraint(
            weight, QgsFieldConstraints.Constraint.ConstraintExpression,
            QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard)
    due = fields.indexFromName("due_date")
    if due >= 0:
        table.setEditorWidgetSetup(due, QgsEditorWidgetSetup(
            "DateTime", {"allow_null": True, "calendar_popup": True,
                         "display_format": "dd.MM.yyyy", "field_format": "yyyy-MM-dd",
                         "field_iso_format": False}))
        table.setConstraintExpression(
            due, "\"due_date\" IS NULL OR regexp_match(\"due_date\", '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')",
            "Bitiş tarihi YYYY-AA-GG biçiminde olmalı.")
        table.setFieldConstraint(
            due, QgsFieldConstraints.Constraint.ConstraintExpression,
            QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard)
    for name in ("action_id", "baseline_value", "target_value", "actual_value", "weight",
                 "due_date", "responsible_institution"):
        index = fields.indexFromName(name)
        if index >= 0:
            table.setFieldConstraint(
                index, QgsFieldConstraints.Constraint.ConstraintNotNull,
                QgsFieldConstraints.ConstraintStrength.ConstraintStrengthSoft)


def load_msp_layers(path, project=None, dataset_id=None):
    """Open an MSP workspace's layers and draw them from the annex."""
    from .msp_styler import MSPStylerEngine

    project = project or QgsProject.instance()
    gpkg = str(Path(path).resolve())
    engine = MSPStylerEngine()
    root = project.layerTreeRoot()
    base = root.findGroup(GROUP_NAME) or root.insertGroup(0, GROUP_NAME)
    specs = layer_specs()
    loaded = []
    for spec in specs:
        layer = QgsVectorLayer(f"{gpkg}|layername={spec.name}", spec.name, "ogr")
        if not layer.isValid():
            # A workspace written by an older catalogue; the audit reports what is absent.
            continue
        configure_msp_layer(layer, spec)
        if layer.renderer() is None or layer.renderer().type() != "categorizedSymbol":
            engine.apply(layer)  # default style missing or replaced
        # Legend lists only the MSP codes this plan uses (core/legend_scope.py).
        limit_to_present(layer)
        watch_legend(layer)
        if dataset_id:
            layer.setCustomProperty("mpyy/dataset_id", dataset_id)
        project.addMapLayer(layer, False)
        base.addLayer(layer)
        loaded.append(layer)
    tables = base.findGroup(TABLE_GROUP_NAME) or base.addGroup(TABLE_GROUP_NAME)
    tables.setExpanded(False)
    for name, title in ((CATALOG_TABLE, CATALOG_LAYER_NAME), (ACTION_TABLE, ACTION_LAYER_NAME)):
        table = QgsVectorLayer(f"{gpkg}|layername={name}", title, "ogr")
        if not table.isValid():
            continue
        if dataset_id:
            table.setCustomProperty("mpyy/dataset_id", dataset_id)
        table.setCustomProperty("mpyy/template", "msp:" + name)
        if name == ACTION_TABLE:
            configure_msp_action_table(table)
        project.addMapLayer(table, False)
        tables.addLayer(table)
        loaded.append(table)
    return loaded
