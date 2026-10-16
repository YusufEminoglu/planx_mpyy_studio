"""The MSP workspace is drawn, stored and audited as the Ek-1e annex states.

The MSP level has no XSD of its own -- the MPYY 1.1.7 set carries UİP, NİP and
ÇDP -- so ``styles/msp_catalog.json`` is the definition the workspace is built
from, and its acceptance test has to check the annex's *decisions*, not only
that eleven layers appeared.  Everything asserted below is read back out of the
written GeoPackage: the tables, each layer's geometry, the dropdowns the annex
defines, the renderer's category set, the substitutions a layer records about
itself, and finally the Ministry's own MSP audit run over features written with
annex codes.

Two things this deliberately does not do.  It does not compare rendered pixels:
the renderer is a native QGIS renderer, its categories and recorded metadata are
checked instead, and the printed-millimetre conversion is pinned in
``test_msp_catalog_pure.py`` against the audit's own scale range.  And it does
not restate the catalogue's counts as literals -- the expected layers, codes and
substitutions all come from ``core.msp_catalog``, so a re-extraction moves one
place and this file follows it.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsProject,
    QgsVectorLayer,
    QgsVectorLayerUtils,
    QgsWkbTypes,
)

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()

from planx_mpyy_studio.core.db_factory import read_dataset_info  # noqa: E402
from planx_mpyy_studio.core.localization import field_alias  # noqa: E402
from planx_mpyy_studio.core.msp_catalog import (  # noqa: E402
    ACTION_TABLE,
    CATALOG_TABLE,
    GROUP_SLUGS,
    PLAN_KADEMESI,
    decode_rows,
    groups,
    msp_layer_specs,
    rows,
    rows_for_layer,
)
from planx_mpyy_studio.core.msp_workspace import (  # noqa: E402
    ACTION_LAYER_NAME,
    CATALOG_COLUMNS,
    CATALOG_LAYER_NAME,
    GROUP_NAME,
    KIND,
    LAYER_FIELDS,
    STYLE_NAME,
    TABLE_GROUP_NAME,
    catalog_cell,
    create_msp_workspace,
    load_msp_layers,
)
from planx_mpyy_studio.core.plan_stage_audit import PlanStageAuditEngine  # noqa: E402
from planx_mpyy_studio.core.project_binding import load_project_layers  # noqa: E402

POLYGON = "MULTIPOLYGON(((500000 4250000,500100 4250000,500100 4250100,500000 4250100,500000 4250000)))"
LINE = "MULTILINESTRING((500000 4250000,500100 4250100))"
POINT = "POINT(500050 4250050)"
GEOMETRY_OF = {"POLYGON": POLYGON, "LINE": LINE, "POINT": POINT}

#: What ``gpkg_geometry_columns`` must say for each annex geometry.
WKB_NAME = {"POLYGON": "MULTIPOLYGON", "LINE": "MULTILINESTRING", "POINT": "POINT"}

WKB_KIND = {
    "POLYGON": QgsWkbTypes.GeometryType.PolygonGeometry,
    "LINE": QgsWkbTypes.GeometryType.LineGeometry,
    "POINT": QgsWkbTypes.GeometryType.PointGeometry,
}


def value_map(layer, field):
    """The values a ValueMap dropdown offers, in the order it offers them."""
    entries = layer.editorWidgetSetup(layer.fields().indexFromName(field)).config().get("map", [])
    return [value for entry in entries for value in entry.values()]


def categories(layer):
    """The layer's full MSP symbol set.

    On load the legend is trimmed to the codes a plan uses (core/legend_scope.py),
    so the complete set the annex defines is read from the stored full renderer.
    ``categories()`` returns copies, so the temporary renderer may go.
    """
    from planx_mpyy_studio.core.legend_scope import full_renderer

    return full_renderer(layer).categories()


class MSPWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()
        self.path = Path(self.tmp.name) / "msp.gpkg"
        self.specs = {spec.name: spec for spec in msp_layer_specs()}
        self.rows = {row.id: row for row in decode_rows()}

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def _create(self):
        create_msp_workspace(self.path, "EPSG:5254")

    def _open(self):
        return {layer.name(): layer for layer in load_project_layers(self.path)}

    def _feature(self, layer, spec, code_id, index):
        """A decision written the way the workspace's own form writes one."""
        row = self.rows[code_id]
        feature = QgsVectorLayerUtils.createFeature(
            layer, QgsGeometry.fromWkt(GEOMETRY_OF[spec.geometry]), {},
            layer.createExpressionContext(),
        )
        feature["global_id"] = "b1f0c1d2-0000-4000-8000-%012d" % index
        feature["plan_id"] = "TR-35-IZMIR-MSP-2026"
        feature["plan_kademesi"] = PLAN_KADEMESI
        feature["msp_kodu"] = row.id
        feature["gosterim_adi"] = row.detay_adi
        feature["strateji_bolgesi"] = row.detay_alt_sinifi
        return feature

    def test_the_workspace_holds_the_annexs_layers_and_the_two_companion_tables(self):
        self._create()
        info = read_dataset_info(self.path)
        self.assertEqual((info["workspace_kind"], info["plan_levels"]), (KIND, (PLAN_KADEMESI,)))
        self.assertTrue(info["dataset_id"])
        with sqlite3.connect(self.path) as con:
            contents = dict(con.execute("SELECT table_name, data_type FROM gpkg_contents"))
            geometry = dict(
                con.execute("SELECT table_name, geometry_type_name FROM gpkg_geometry_columns")
            )
        for name, spec in self.specs.items():
            with self.subTest(layer=name):
                self.assertEqual(contents.get(name), "features")
                self.assertEqual(geometry[name], WKB_NAME[spec.geometry])
        self.assertEqual(contents.get(ACTION_TABLE), "attributes")
        self.assertEqual(contents.get(CATALOG_TABLE), "attributes")
        # Exactly the annex's layers plus the two companions and the style table.
        # The catalogue table is created in SQL, so it is the one an OGR-only
        # build would lose; naming layer_styles keeps the count from passing
        # because two of the three were missing.
        self.assertEqual(
            {name for name, kind in contents.items() if kind in ("features", "attributes")},
            set(self.specs) | {ACTION_TABLE, CATALOG_TABLE, "layer_styles"},
        )
        self.assertEqual(len(self.specs), 11)
        self.assertEqual(
            len({spec.geometry for spec in self.specs.values()}), 3, "iki geometrili katman yok"
        )

    def test_the_layers_carry_the_fields_the_annex_drawing_needs(self):
        self._create()
        layers = self._open()
        for name in self.specs:
            with self.subTest(layer=name):
                layer = layers[name]
                # The primary key is OGR's, not part of the annex schema, so it
                # is dropped by index rather than by name: what is asserted is
                # the plugin's fields, in the order the plugin creates them.
                key = set(layer.primaryKeyAttributes())
                drawn = [index for index in range(len(layer.fields())) if index not in key]
                self.assertEqual(key, {0})
                self.assertEqual(
                    [layer.fields().at(index).name() for index in drawn], list(LAYER_FIELDS)
                )
                # Aliases come from the shared table, so a field the form shows
                # raw would fail here rather than in front of a planner.
                self.assertEqual(
                    [layer.fields().at(index).alias() for index in drawn],
                    [field_alias(field) for field in LAYER_FIELDS],
                )
        with sqlite3.connect(self.path) as con:
            columns = [row[1] for row in con.execute(f'PRAGMA table_info("{ACTION_TABLE}")')]
        for name in ("action_id", "responsible_institution", "due_date", "weight"):
            self.assertIn(name, columns)

    def test_the_catalogue_table_stores_every_annex_row_column_by_column(self):
        """Compared column by column, which is what catches a drifted INSERT."""
        self._create()
        with sqlite3.connect(self.path) as con:
            stored = con.execute(
                "SELECT " + ", ".join(column for column, _ in CATALOG_COLUMNS)
                + f" FROM {CATALOG_TABLE}"
            ).fetchall()
        # Both sides go through ``catalog_cell``, the same mapping the INSERT
        # uses: the two structured fields (the bullseye's discs, MSP-002's class
        # rule) are stored as the catalogue's own JSON text, so comparing the
        # raw list against the stored text would fail on a correct table.
        expected = [
            tuple(catalog_cell(row[source]) for _, source in CATALOG_COLUMNS)
            for row in rows()
        ]
        self.assertEqual(len(expected), 28)
        self.assertEqual(sorted(stored), sorted(expected))
        # No two columns of the annex hold the same value on every row, so any
        # swap inside the INSERT changes a stored row and fails above.  (Checked
        # by swapping sinir_kalinligi_mm with sayfa and watching it fail.)
        self.assertEqual(len({tuple(row[1:]) for row in expected}), len(expected))

    def test_each_layer_renders_exactly_the_codes_the_annex_gives_it(self):
        self._create()
        layers = self._open()
        catalogue = decode_rows()
        for name, spec in self.specs.items():
            with self.subTest(layer=name):
                layer = layers[name]
                self.assertEqual(layer.renderer().type(), "categorizedSymbol")
                self.assertEqual(layer.renderer().classAttribute(), "msp_kodu")
                drawn = categories(layer)
                self.assertEqual(
                    [category.value() for category in drawn[:-1]],
                    [code.id for code in spec.codes],
                )
                self.assertEqual(
                    [category.label() for category in drawn[:-1]],
                    [code.caption for code in spec.codes],
                )
                # One fallback category, so a blank or unknown code is drawn
                # visibly rather than not at all.
                self.assertIsNone(drawn[-1].value())
                self.assertEqual(len(drawn), len(rows_for_layer(catalogue, spec)) + 1)
                self.assertEqual(
                    QgsWkbTypes.geometryType(layer.wkbType()), WKB_KIND[spec.geometry]
                )

    def test_the_annexs_own_groups_and_codes_are_the_dropdowns(self):
        self._create()
        layers = self._open()
        for name, spec in self.specs.items():
            with self.subTest(layer=name):
                layer = layers[name]
                self.assertEqual(value_map(layer, "msp_kodu"), [code.id for code in spec.codes])
                self.assertEqual(
                    value_map(layer, "gosterim_adi"), [code.detay_adi for code in spec.codes]
                )
                # The strategic region is the annex's own group, and every layer
                # offers all seven: a decision's group is the planner's choice.
                self.assertEqual(value_map(layer, "strateji_bolgesi"), list(groups()))
        self.assertEqual(len(GROUP_SLUGS), 7)
        self.assertEqual(
            set(value_map(layers["msp_afet_alan"], "strateji_bolgesi")), set(groups())
        )

    def test_the_layer_records_what_it_could_not_draw_as_the_annex_states(self):
        """A reopened workspace must still say which codes are substitutions.

        The property is not part of a saved style, so the workspace builder sets
        it when it configures the layer it opened -- otherwise a file opened
        without the MSP style being re-applied would carry no record at all.

        Since the drawing annex was read no code is a missing glyph: every point
        row reaches EK-1b's own artwork, a native shape or a compound drawing, so
        the property is empty on every layer.  It is still asserted, and asserted
        as empty, because "no layer records a substitution" is exactly the state
        a regression would flip -- and the alternative, checking only that the
        property exists, would pass for a renderer that had gone back to dots.
        """
        self._create()
        layers = self._open()
        catalogue = decode_rows()
        for name, spec in self.specs.items():
            with self.subTest(layer=name):
                layer = layers[name]
                drawn = rows_for_layer(catalogue, spec)
                pictograms = [row.id for row in drawn if row.is_pictogram_for(spec.geometry)]
                self.assertEqual(
                    layer.customProperty("mpyy/msp_pictogram_missing"), ",".join(pictograms)
                )
                self.assertEqual(layer.customProperty("mpyy/msp_layer"), name)
                self.assertEqual(layer.customProperty("mpyy/plan_kademesi"), PLAN_KADEMESI)
                self.assertEqual(pictograms, [], name)
        # Every point row really is drawn: the emptiness above is the annex being
        # reproduced, not the layer failing to see any codes at all.
        self.assertTrue(
            [row.id for row in rows_for_layer(catalogue, self.specs["msp_ekonomi_nokta"])
             if row.shape_kind != "none"]
        )
        # MSP-001's drop shadow is drawn as a flat offset and MSP-002's three-tone
        # class rule is bound to two fields rather than read from one cell; both
        # are recorded.  MSP-003's dash and outline are drawn as the annex states.
        self.assertIn(
            "MSP-001", layers["msp_plan_siniri_alan"].customProperty("mpyy/msp_approximated")
        )
        self.assertIn(
            "MSP-002", layers["msp_yerlesme_alan"].customProperty("mpyy/msp_approximated")
        )
        self.assertNotIn(
            "MSP-003", layers["msp_yerlesme_alan"].customProperty("mpyy/msp_approximated")
        )

    def test_plain_qgis_gets_the_annex_symbology_out_of_the_geopackage(self):
        """The style is stored in the workspace, so it survives without the plugin."""
        self._create()
        with sqlite3.connect(self.path) as con:
            styled = {
                name for (name,) in con.execute(
                    "SELECT f_table_name FROM layer_styles WHERE styleName = ?", (STYLE_NAME,)
                )
            }
        self.assertEqual(styled, set(self.specs))
        for name, spec in self.specs.items():
            with self.subTest(layer=name):
                layer = QgsVectorLayer(f"{self.path}|layername={name}", name, "ogr")
                self.assertTrue(layer.isValid())
                self.assertEqual(layer.renderer().type(), "categorizedSymbol")
                self.assertEqual(
                    [category.value() for category in categories(layer)][:-1],
                    [code.id for code in spec.codes],
                )

    def test_a_decision_written_with_an_annex_code_survives_the_round_trip(self):
        self._create()
        layer = self._open()["msp_afet_alan"]
        spec = self.specs["msp_afet_alan"]
        layer.startEditing()
        self.assertTrue(layer.addFeature(self._feature(layer, spec, spec.codes[0].id, 1)))
        self.assertTrue(layer.commitChanges(), layer.commitErrors())

        row = self.rows[spec.codes[0].id]
        with sqlite3.connect(self.path) as con:
            self.assertEqual(
                con.execute(
                    "SELECT plan_kademesi, msp_kodu, gosterim_adi, strateji_bolgesi "
                    "FROM msp_afet_alan"
                ).fetchone(),
                (PLAN_KADEMESI, row.id, row.detay_adi, row.detay_alt_sinifi),
            )
            # The annex's code resolves against the workspace's own table.
            self.assertEqual(
                con.execute(
                    f"SELECT detay_adi FROM {CATALOG_TABLE} WHERE id = ?", (row.id,)
                ).fetchone()[0],
                row.detay_adi,
            )

    def test_the_msp_audit_passes_over_one_decision_from_each_annex_group(self):
        """End to end: annex codes in annex layers satisfy the Ministry's MSP checks.

        This is the contract the layer fields exist for.  ``DETAIL_LEVEL_LEAKAGE``
        is an ERROR and fires for any non-UİP level carrying a parcel-level field,
        ``MISSING_STRATEGIC_ROLE`` for an MSP decision with neither a strategic
        region nor a priority status, and the six themes ``_missing_msp_themes``
        scores are covered by the annex's own seven groups -- which one decision
        per group is what proves, since a single group leaves five of them unmet.
        """
        self._create()
        layers = self._open()
        features = []
        for group in groups():
            name = next(name for name, spec in self.specs.items() if spec.group == group)
            spec = self.specs[name]
            layer = layers[name]
            features.append(
                self._feature(layer, spec, spec.codes[0].id, len(features))
            )
        self.assertEqual(len(features), 7)

        result = PlanStageAuditEngine.audit_features(features, PLAN_KADEMESI, 250000)
        self.assertEqual(result.level, PLAN_KADEMESI)
        self.assertEqual(result.missing_msp_themes, [])
        self.assertEqual(result.error_count, 0)
        self.assertEqual(
            [finding.code for record in result.records for finding in record.findings], []
        )
        self.assertEqual({record.status for record in result.records}, {"COMPLIANT"})

        # The same decisions read against the audit's scale range: an MSP map
        # scale is 1:250.000-1:500.000, and the renderer's conversion uses the
        # floor, so a scale outside the range is the one thing that would fail.
        outside = PlanStageAuditEngine.audit_features(features, PLAN_KADEMESI, 5000)
        self.assertEqual(
            sorted(finding.code for record in outside.records for finding in record.findings),
            ["SCALE_LEVEL_MISMATCH"] * len(features),
        )

    def test_action_plan_form_matches_what_the_monitoring_reads(self):
        """Weight > 0 and a YYYY-MM-DD due date, or core.msp_monitoring counts nothing."""
        from qgis.core import QgsFeature, QgsFieldConstraints

        self._create()
        table = self._open()[ACTION_LAYER_NAME]
        weight = table.fields().indexFromName("weight")
        due = table.fields().indexFromName("due_date")
        self.assertEqual(table.editorWidgetSetup(weight).type(), "Range")
        self.assertEqual(table.editorWidgetSetup(due).type(), "DateTime")
        self.assertEqual(table.editorWidgetSetup(due).config()["field_format"], "yyyy-MM-dd")

        def ok(feature, index):
            return QgsVectorLayerUtils.validateAttribute(
                table, feature, index, QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard)[0]

        f = QgsFeature(table.fields())
        f["weight"] = 0
        self.assertFalse(ok(f, weight))
        f["weight"] = 0.5
        self.assertTrue(ok(f, weight))
        f["due_date"] = "31.12.2026"
        self.assertFalse(ok(f, due))
        f["due_date"] = "2026-12-31"
        self.assertTrue(ok(f, due))

    def test_legend_lists_only_the_codes_the_plan_uses(self):
        from planx_mpyy_studio.core.legend_scope import full_renderer

        self._create()
        layer = self._open()["msp_afet_alan"]
        spec = self.specs["msp_afet_alan"]
        self.assertGreater(len(spec.codes), 1)
        self.assertEqual(len(layer.renderer().categories()), 0)       # nothing drawn yet
        full = full_renderer(layer)
        self.assertGreaterEqual(len(full.categories()), len(spec.codes))
        layer.startEditing()
        self.assertEqual(len(layer.renderer().categories()), len(full.categories()))
        self.assertTrue(layer.addFeature(self._feature(layer, spec, spec.codes[0].id, 1)))
        self.assertTrue(layer.commitChanges(), layer.commitErrors())
        self.assertEqual([str(c.value()) for c in layer.renderer().categories()], [spec.codes[0].id])

    def test_the_workspace_loads_into_its_own_group_with_its_companion_tables(self):
        """``load_msp_layers`` is reached through the workspace-kind dispatch."""
        self._create()
        loaded = load_project_layers(self.path)
        self.assertEqual(len(loaded), len(self.specs) + 2)
        self.assertEqual(
            {layer.name() for layer in loaded},
            set(self.specs) | {CATALOG_LAYER_NAME, ACTION_LAYER_NAME},
        )
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(GROUP_NAME)
        self.assertIsNotNone(group)
        self.assertEqual(
            {node.layer().name() for node in group.children() if isinstance(node, QgsLayerTreeLayer)},
            set(self.specs),
        )
        tables = group.findGroup(TABLE_GROUP_NAME)
        self.assertIsNotNone(tables)
        self.assertEqual(
            {node.layer().name() for node in tables.children() if isinstance(node, QgsLayerTreeLayer)},
            {CATALOG_LAYER_NAME, ACTION_LAYER_NAME},
        )
        # The catalogue table is the annex itself, feature for feature.
        self.assertEqual(
            next(layer for layer in loaded if layer.name() == CATALOG_LAYER_NAME).featureCount(),
            28,
        )
        # Loading again reuses the group instead of stacking a second one: the
        # tree is keyed by name, which is what keeps a planner from seeing the
        # eleven layers twice after reopening a project.
        load_msp_layers(self.path)
        self.assertEqual(
            [node.name() for node in root.children() if isinstance(node, QgsLayerTreeGroup)],
            [GROUP_NAME],
        )


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    import sys

    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
