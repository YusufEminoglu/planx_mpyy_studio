"""The MSP Ek-1e catalogue is the only MSP definition, so it is pinned here.

There is no MSP XSD: the MPYY 1.1.7 set the rest of the plugin compiles from
carries UIP, NIP and CDP only.  The Mekânsal Strateji Planı annex --
``styles/msp_catalog.json``, 28 rows over pages 1-11 -- is therefore the whole
definition of the level, and three separate consumers read it: the workspace
builder (one layer per official group and geometry), the renderer, and the
Ministry-facing audit.  Nothing else would notice if the extraction changed
under them, because every one of those consumers is QGIS-bound and the runtime
matrix only asserts that layers appear, never what they carry.

This file is qgis-free on purpose -- it reads the catalogue and the two modules'
source, not QGIS symbols -- so it runs on both runtimes and cannot be skipped
for want of an import.  What it holds:

1. **The split.**  A symbol the annex draws as "POLYGON, POINT" has to be
   drawable both ways, and a QGIS layer holds one geometry, so the catalogue is
   split by its own ``detay_alt_sinifi`` group *and* by geometry: 11 layers, 32
   code slots.  Both numbers are measured from the file, so a re-extraction that
   moves them fails here rather than shipping a layer nobody draws.
2. **The three ways a row is read.**  ``is_pictogram_for`` depends on the
   geometry it is asked about -- the dual rows are a filled area *and* a
   Ministry glyph -- and since the EK-1b pass it means something narrower than
   it did: not "is this a glyph" but "is this a glyph the plugin cannot draw".
   Every row EK-1b draws now reaches one of three drawings, so the answer is no
   row at all, and that totality is asserted here rather than assumed.
3. **The prose decoders.**  The annex states its legend in Turkish prose
   ("2mm düz çizgi, 2mm boşluk", "5*5 mm ara ile karolaj..."), so the decoders
   read text and are pinned against the rows they were written for, including
   the two the rules deliberately leave alone: a spacing with no gap is a hatch,
   not a dash, and a karolaj's second number is the grid, not a dot diameter.
4. **The contracts the workspace has to satisfy.**  ``LAYER_FIELDS`` is parsed
   out of ``core/msp_workspace.py`` and checked against the audit that judges
   it: no field the audit forbids above UİP (``DETAIL_LEVEL_LEAKAGE`` is an
   ERROR), the fields it requires, and the action table's names against what
   ``core/msp_monitoring`` reads.  ``NOMINAL_SCALE`` is checked against the
   audit's own ``SCALE_RANGES["MSP"]`` floor, because the renderer's
   printed-millimetre conversion has to agree with the scale the audit accepts.
5. **Provenance.**  The catalogue is compiled from two annexes by
   ``tools/compile_msp_catalog.py``.  Ek-1e is the table of records; EK-1b is
   the annex that *draws* them, and the only place a symbol's shape, its ink,
   its measured size and a hatch's axis exist at all.  The compiler keeps every
   cell it read in the top-level ``kaynak`` map, per row and per field.  Those
   tests are the reason the file can be trusted: each emitted value has to be
   traceable to the cell it was read from (or to a named, documented fallback),
   so a value nobody can point at a page for fails here instead of shipping as
   the Ministry's own.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import unittest
import unicodedata
from pathlib import Path

from planx_mpyy_studio.core.localization import label_fold
from planx_mpyy_studio.core.msp_catalog import (
    ACTION_TABLE,
    BOUNDARY_WIDTH_MM,
    CATALOG_TABLE,
    COMPOUND_SHAPES,
    GEOMETRY_KINDS,
    GEOMETRY_SUFFIX,
    GROUP_SLUGS,
    HOLLOW_MARK,
    MARKER_SHAPES,
    MSPRow,
    NOMINAL_SCALE,
    PATTERN_CATEGORICAL,
    PATTERN_CLASSED,
    PATTERN_DOT_HATCH,
    PATTERN_GRADIENT,
    PATTERN_GRID_DOT,
    PATTERN_LINE_HATCH,
    PATTERN_NONE,
    PLAN_KADEMESI,
    SOLID_MARK,
    class_rule,
    dash_mm,
    decode_rows,
    fill_rgba,
    groups,
    load_catalog,
    msp_layer_specs,
    pattern,
    rgb_triplets,
    rows,
    rows_for_layer,
    shadow_rgb,
    stated_line_width_mm,
    stroke_rgba,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "styles" / "msp_catalog.json"
CATALOG_MODULE = ROOT / "core" / "msp_catalog.py"
WORKSPACE_MODULE = ROOT / "core" / "msp_workspace.py"
AUDIT_MODULE = ROOT / "core" / "plan_stage_audit.py"
COMPILER = ROOT / "tools" / "compile_msp_catalog.py"

#: The 28 rows as the annex prints them, group by group, and the geometry each
#: is drawable as.  Written out rather than counted so a re-extraction that
#: files a code under the wrong group fails on the name, not only on a total.
EXPECTED_LAYERS = (
    ("msp_plan_siniri_alan", "PLAN SINIRI", "POLYGON", ("MSP-001",)),
    ("msp_yerlesme_alan", "YERLEŞMELER SİSTEMİ VE ŞEHİRLEŞME", "POLYGON", ("MSP-002", "MSP-003")),
    ("msp_yerlesme_nokta", "YERLEŞMELER SİSTEMİ VE ŞEHİRLEŞME", "POINT", ("MSP-002", "MSP-004", "MSP-005")),
    ("msp_ulasim_alan", "ANA ULAŞIM SİSTEMİ", "POLYGON", ("MSP-006", "MSP-007")),
    ("msp_ulasim_cizgi", "ANA ULAŞIM SİSTEMİ", "LINE", ("MSP-009", "MSP-010")),
    ("msp_ulasim_nokta", "ANA ULAŞIM SİSTEMİ", "POINT", ("MSP-008", "MSP-011", "MSP-012", "MSP-013")),
    ("msp_altyapi_nokta", "ANA ALTYAPI", "POINT", ("MSP-014",)),
    ("msp_ekonomi_alan", "EKONOMİK İHTİSAS BÖLGELERİ VE KORİDORLARI", "POLYGON",
     ("MSP-015", "MSP-018", "MSP-021", "MSP-022")),
    ("msp_ekonomi_nokta", "EKONOMİK İHTİSAS BÖLGELERİ VE KORİDORLARI", "POINT",
     ("MSP-016", "MSP-017", "MSP-018", "MSP-019", "MSP-020", "MSP-021", "MSP-022", "MSP-023")),
    ("msp_afet_alan", "AFETLER AÇISINDAN RİSKLİ ALANLAR", "POLYGON", ("MSP-024", "MSP-025")),
    ("msp_su_peyzaj_alan", "SU, DOĞAL PEYZAJ VE EKOSİSTEMLER", "POLYGON",
     ("MSP-026", "MSP-027", "MSP-028")),
)

#: The rows the annex draws as two geometries at once.  Each is drawn as a fill
#: on its area layer and as a Ministry pictogram on its point layer, so anything
#: that asks "is this a pictogram?" without saying which form it means is wrong.
DUAL_GEOMETRY = ("MSP-002", "MSP-018", "MSP-021", "MSP-022")

#: Every point row whose annex legend is a pictogram the plugin has no artwork
#: for: one flat fill colour and no pattern, so its meaning is the glyph itself.
#: MSP-014 is deliberately absent -- its legend is "Kaynak türüne göre renkli
#: nokta", four official colours, which the renderer *does* draw.
PICTOGRAMS = (
    "MSP-004", "MSP-005", "MSP-008", "MSP-011", "MSP-012", "MSP-013",
    "MSP-016", "MSP-017", "MSP-018", "MSP-019", "MSP-020", "MSP-021",
    "MSP-022", "MSP-023",
)

#: The fields the workspace's drawing layers must carry, and the parcel-level
#: implementation fields the audit rejects above UİP with an ERROR.
REQUIRED_LAYER_FIELDS = ("global_id", "plan_id", "plan_kademesi", "strateji_bolgesi")

#: What ``core/msp_monitoring`` reads off the action table, lower-cased.
MONITORING_FIELDS = (
    "action_id", "baseline_value", "target_value", "actual_value",
    "weight", "due_date", "responsible_institution",
)


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _literal(path: Path, name: str):
    """The literal value assigned to a module-level ``name``."""
    for node in _module(path).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name}: {name} bulunamadı")


def _function(path: Path, name: str) -> ast.FunctionDef:
    for node in ast.walk(_module(path)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{path.name}: {name} bulunamadı")


def _tuple_elements(path: Path, name: str) -> list[ast.expr]:
    """The elements of a module-level tuple literal that is not literal-evaluable."""
    for node in _module(path).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return node.value.elts
    raise AssertionError(f"{path.name}: {name} bulunamadı")


def _returned_keys(path: Path, name: str) -> set[str]:
    """The string keys of the dict literal ``name`` returns."""
    for node in ast.walk(_function(path, name)):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            return {
                key.value for key in node.value.keys if isinstance(key, ast.Constant)
            }
    raise AssertionError(f"{path.name}: {name} bir sözlük döndürmüyor")


def _imported_modules(path: Path) -> set[str]:
    modules = set()
    for node in ast.walk(_module(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _audit_msp_themes() -> dict[str, tuple[str, ...]]:
    """The theme tokens ``_missing_msp_themes`` scores an MSP against.

    Read out of the audit's own source rather than copied: this file cannot
    import the module (it needs ``QgsFeature``), and a copy would be free to
    drift away from the check it is supposed to describe.
    """
    for node in ast.walk(_function(AUDIT_MODULE, "_missing_msp_themes")):
        if isinstance(node, ast.Dict):
            return ast.literal_eval(node)
    raise AssertionError("_missing_msp_themes: tema listesi bulunamadı")


def _normalize(value) -> str:
    """Mirrors ``PlanStageAuditEngine.normalize``; guarded by its own test."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


class MSPCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.document = load_catalog()
        self.records = decode_rows(self.document)
        self.raw = rows()
        self.kaynak = self.document["kaynak"]

    def test_the_annex_is_read_whole(self):
        # Version 4 is the EK-1b pass: the drawing annex is now a second source,
        # and the bump is what tells a reader the rows carry more than Ek-1e.
        self.assertEqual(self.document["version"], 4)
        self.assertEqual(self.document["total_records"], len(self.records))
        self.assertEqual(len(self.records), 28)
        # Pages 1-11, no gap: the catalogue is the annex's own pagination, and a
        # missing page is an extraction that stopped early.
        self.assertEqual(sorted({row.page for row in self.records}), list(range(1, 12)))
        self.assertEqual(
            [row.id for row in self.records],
            [f"MSP-{index:03d}" for index in range(1, 29)],
        )
        keys = {tuple(sorted(row)) for row in self.raw}
        self.assertEqual(len(keys), 1, "katalog satırları aynı alanları taşımıyor")

    def test_every_row_records_the_cells_it_was_read_from(self):
        """The audit trail is per row, and no row's cells are another row's.

        ``kaynak`` lives outside ``rows`` on purpose: ``rows`` is the runtime
        contract ``CATALOG_COLUMNS`` mirrors into the GeoPackage, and a column
        of raw annex prose is not part of it.  What it must be is complete -- an
        id with no cells behind it is a value nobody can check against the page.
        """
        self.assertEqual(
            sorted(self.kaynak), [f"MSP-{index:03d}" for index in range(1, 29)]
        )
        source = self.document["source"]
        self.assertEqual(source["section"], "I- MEKÂNSAL STRATEJİ PLANI DETAY KATALOĞU")
        # Both documents the compiler cross-checks are named, and hashed: a
        # recompile against a different annex cannot pass for the same one.
        for key in ("catalog_docx", "catalog_pdf"):
            with self.subTest(document=key):
                self.assertTrue(source[key].endswith((".docx", ".pdf")), source[key])
        for key in ("catalog_docx_sha256", "catalog_pdf_sha256"):
            with self.subTest(digest=key):
                # Shipped Hub-safe: four groups of 16, spaces removed by readers.
                self.assertRegex(source[key], r"^[0-9a-f]{16}( [0-9a-f]{16}){3}$")

    def test_the_drawing_annex_is_a_named_and_hashed_third_source(self):
        """EK-1b is what a symbol's shape, ink, size and axis are read from.

        It is a *second document* and not a second reading of Ek-1e, so it is
        recorded the same way the other two are: named, hashed, and -- because
        the measurement is a file the compiler reads rather than computes -- the
        measurement file is hashed too.  Without this a catalogue could be
        recompiled against a different EK-1b, or against a stale shapes file,
        and nothing in the committed JSON would say so.
        """
        source = self.document["source"]
        self.assertTrue(source["catalog_1b"].lower().endswith(".pdf"), source["catalog_1b"])
        self.assertNotEqual(source["catalog_1b"], source["catalog_pdf"])
        for key in ("catalog_1b_sha256", "shapes_json_sha256"):
            with self.subTest(digest=key):
                self.assertRegex(source[key], r"^[0-9a-f]{16}( [0-9a-f]{16}){3}$")
        self.assertEqual(source["shapes_json"], "msp_shapes.json")
        # The measurement file is in the repository, so the digest in the
        # catalogue can be re-derived here; the annex it was measured from is not.
        measured = ROOT / "styles" / source["shapes_json"]
        self.assertEqual(
            hashlib.sha256(measured.read_bytes()).hexdigest(), source["shapes_json_sha256"].replace(" ", "")
        )
        payload = json.loads(measured.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"]["sha256"], source["catalog_1b_sha256"])
        self.assertEqual(payload["source"]["pdf"], source["catalog_1b"])

    def test_every_emitted_value_is_traceable_to_the_cell_it_came_from(self):
        """Nothing in the catalogue is a plausible number nobody printed.

        Each emitted value is looked up in the ``kaynak`` entry recorded for the
        same row.  The comparison folds case, accents and punctuation, so the
        annex's own ASCII ``I`` ("HASSAS EKOLOJIK SISTEMLER") and the corrected
        spelling the catalogue carries ("HASSAS EKOLOJİK SİSTEMLER") are the same
        printed words -- while a number, a colour or a word the annex never
        printed still fails.
        """
        for row in self.raw:
            with self.subTest(code=row["id"]):
                source = self.kaynak[row["id"]]
                cells = " ".join(
                    value for value in source.values() if isinstance(value, str)
                )
                folded = label_fold(cells)
                # The title is printed above the table rather than inside it, so
                # it is checked against both readings the compiler took: the
                # paragraph it was named from and the PDF's own print.
                self.assertIn(label_fold(row["detay_adi"]), label_fold(source["baslik"]))
                self.assertEqual(
                    label_fold(row["detay_adi"]), label_fold(source["baslik_pdf"])
                )
                self.assertIn(label_fold(row["detay_alt_sinifi"]), folded)
                # The two prose fields are the annex's cells word for word, not a
                # paraphrase: they are what the pattern decoder reads.
                self.assertIn(row["stroke_desc"], cells)
                self.assertIn(row["hatch_desc"], cells)
                # A colour cell is only ever a colour.
                for key in ("sembol_rgb", "tarama_rgb", "sinir_rgb"):
                    for triplet in str(row[key] or "").split(";"):
                        if triplet:
                            self.assertIn(triplet, cells, f"{row['id']}.{key}")

    def test_every_drawn_value_is_backed_by_the_measurement_it_was_read_off(self):
        """EK-1b's fields are checked against the measurement file, not a memory.

        The shapes file is what the compiler read off the drawing annex, and both
        it and the catalogue are in the repository -- so the gate can re-derive
        this correspondence even though the annex itself is not.  A shape name, an
        ink, a measured size or a bullseye's rings that drifted away from the
        measurement they claim to come from fails here, along with a row that
        starts drawing a shape EK-1b never measured.
        """
        payload = json.loads((ROOT / "styles" / "msp_shapes.json").read_text(encoding="utf-8"))
        shapes = payload["shapes"]
        taramalar = payload["taramalar"]
        self.assertEqual(len(shapes), 16, "ölçüm dosyası nokta satırlarını kapsamıyor")
        for row in self.raw:
            source = self.kaynak[row["id"]]
            shape = shapes.get(row["id"])
            with self.subTest(code=row["id"]):
                if shape is None:
                    # A row EK-1b draws no glyph for keeps every drawn field empty
                    # rather than borrowing another row's: the three that are not
                    # measured are area and line rows.
                    self.assertIsNone(row["sembol_sekli"])
                    self.assertIsNone(row["sembol_boyut_mm"])
                    self.assertEqual(row["sembol_halkalar"], None)
                    self.assertEqual(source["sembol_sekli_kaynak"], "")
                    self.assertEqual(source["sembol_1b_notu"], "")
                    self.assertEqual(source["sembol_boyut_kaynak"], "")
                    continue
                self.assertEqual(row["sembol_sekli"], shape["sekli"])
                self.assertEqual(row["sembol_dolgu"], shape["dolgu"])
                self.assertEqual(row["sembol_ikon"], shape.get("ikon"))
                self.assertEqual(row["sembol_boyut_mm"], shape["boyut_mm"])
                self.assertEqual(source["sembol_sekli_kaynak"], "ek_1b_sembol_hucre")
                self.assertEqual(source["sembol_boyut_kaynak"], "ek_1b_olculen_cizim_kaplami")
                self.assertEqual(source["sembol_cizim"], f"{shape['cizim']}/{shape['dolgu']}")
                self.assertEqual(source["sembol_1b_notu"], shape.get("renk_notu") or "")
                # The rings are the measured discs, ratios of the outermost, and
                # the row has them exactly when the drawing has a bullseye in it.
                discs = shape.get("discler") or []
                if len(discs) >= 2 and row["sembol_halkalar"]:
                    outer = max(float(disc["cap_mm"]) for disc in discs)
                    self.assertEqual(
                        row["sembol_halkalar"],
                        [[round(float(disc["cap_mm"]) / outer, 4), disc["rol"]]
                         for disc in sorted(discs, key=lambda disc: -float(disc["cap_mm"]))],
                    )
                # The crop the reading was taken from is shipped, and still the
                # one recorded -- a re-cut drawing cannot pass for the old one.
                self.assertEqual(
                    hashlib.sha256((ROOT / shape["kanit"]).read_bytes()).hexdigest(),
                    shape["kanit_sha256"].replace(" ", ""),
                )
        for row in self.raw:
            source = self.kaynak[row["id"]]
            measured = (taramalar.get(row["id"]) or {}).get("aci_derece")
            with self.subTest(axis=row["id"]):
                self.assertEqual(row["tarama_aci_derece"], measured)
                self.assertEqual(
                    source["tarama_aci_kaynak"],
                    "ek_1b_tarama_hucre" if measured is not None else "",
                )

    def test_the_ink_the_drawing_annex_supplies_fills_a_blank_never_contradicts_one(self):
        """One row's mark colour is printed only in EK-1b, and only that row's.

        Ek-1e leaves MSP-002's SEMBOL cell empty, so the note EK-1b prints beside
        the drawn bullseye is the only place the ink is stated.  Wherever both
        documents state a colour the note must be *among* the stated ones -- the
        compiler refuses otherwise, and this re-checks the committed file, so an
        edit that let the second source invent an ink fails here rather than
        shipping it as the Ministry's own.
        """
        borrowed = sorted(
            row["id"] for row in self.raw
            if self.kaynak[row["id"]]["sembol_rgb_kaynak"] == "ek_1b_sembol"
        )
        self.assertEqual(borrowed, ["MSP-002"])
        self.assertEqual(
            next(row["sembol_rgb"] for row in self.raw if row["id"] == "MSP-002"),
            "255/170/0",
        )
        notes = 0
        for row in self.raw:
            note = self.kaynak[row["id"]]["sembol_1b_notu"]
            if not note:
                continue
            notes += 1
            self.assertIn(note, str(row["sembol_rgb"] or "").split(";"), row["id"])
        # Twelve of the sixteen drawn marks print a colour note beside them; the
        # four that do not are the three pictograms -- whose colour is in the
        # artwork, not in a note -- and MSP-008's plain red disc.  A drawing pass
        # that stopped reading the notes would leave nothing to compare here.
        self.assertEqual(notes, 12)

    def test_the_class_rule_is_one_rows_and_says_where_both_halves_came_from(self):
        """MSP-002 is the only rule, and each half of it names its own document."""
        ruled = sorted(row["id"] for row in self.raw if row["sinif_kurali"])
        self.assertEqual(ruled, ["MSP-002"])
        for row in self.raw:
            source = self.kaynak[row["id"]]
            with self.subTest(code=row["id"]):
                self.assertEqual(
                    source["sinif_kurali_kaynak"],
                    "ek_1e_tonlar + ek_1b_boyutlar" if row["sinif_kurali"] else "",
                )
        rule = self.raw[1]["sinif_kurali"]
        # The tones are the record annex's, the sizes are the drawing annex's --
        # and the sizes are the *only* half that is a renderer decision, which is
        # why it is the half named as measured rather than as printed.
        self.assertEqual(rule["ton_kaynak"], "ek_1e_tarama_rgb_yazim_sirasi")
        self.assertEqual(rule["boyut_kaynak"], "ek_1b_cizilen_hedef_caplari_artan")
        self.assertEqual(rule["tonlar"], [[225, 165, 100], [180, 110, 0], [140, 85, 25]])

    def test_a_value_the_annex_left_blank_says_which_cell_stood_in(self):
        """The two fallbacks are named, so neither can hide an invented value.

        The annex prints DETAY SINIFI empty on 27 of its 28 tables and states
        MSP-026's boundary colour in the TİPİ column rather than the RGB one;
        both are resolved during compilation, and ``sinif_kaynak``/``sinir_kaynak``
        record which cell the value actually came from.
        """
        classes = set()
        for row in self.raw:
            source = self.kaynak[row["id"]]
            with self.subTest(code=row["id"]):
                self.assertIn(source["sinir_kaynak"], ("sinir_rgb", "sinir_tipi", ""))
                self.assertIn(
                    source["sinif_kaynak"], ("detay_sinifi", "detay_alt_sinifi")
                )
                classes.add(source["sinif_kaynak"])
                if source["sinif_kaynak"] == "detay_alt_sinifi":
                    self.assertEqual(source["detay_sinifi"], "")
                    self.assertEqual(row["detay_sinifi"], row["detay_alt_sinifi"])
                if source["sinir_kaynak"] == "sinir_tipi":
                    self.assertEqual(source["sinir_rgb"], "")
                    self.assertNotEqual(row["sinir_rgb"], None)
        # Each fallback is real: the blank class is the rule and the printed one
        # the exception, and the boundary slip is a single record.
        self.assertEqual(classes, {"detay_sinifi", "detay_alt_sinifi"})
        self.assertEqual(
            [row["id"] for row in self.raw
             if self.kaynak[row["id"]]["sinir_kaynak"] == "sinir_tipi"],
            ["MSP-026"],
        )

    def test_the_compiler_writes_exactly_the_fields_the_catalogue_carries(self):
        """The compile step's row shape and the shipped row shape are one shape.

        The annex is not in the repository, so the gate cannot rerun the
        extraction; what it can prove is that ``_decode_record`` still returns
        exactly the fields the committed catalogue has, alongside the ``kaynak``
        audit map, the two positional fields the compiler adds, and EK-1b's own
        fields.  A field the compiler starts or stops emitting fails here rather
        than disagreeing quietly with the file it wrote.
        """
        rows_fields = set(self.raw[0])
        drawn = set(_literal(COMPILER, "EKB_FIELDS"))
        self.assertEqual(
            _returned_keys(COMPILER, "_decode_record") - {"kaynak"} | drawn,
            rows_fields - {"id", "page"},
        )
        self.assertIn("kaynak", _returned_keys(COMPILER, "_decode_record"))
        self.assertEqual({"id", "page"} - rows_fields, set())
        # The two lists are disjoint: a field named in EKB_FIELDS must be EK-1b's,
        # never a name ``_decode_record`` also produces, or a value would have two
        # writers and the last one would win silently.
        self.assertEqual(_returned_keys(COMPILER, "_decode_record") & drawn, set())

    def test_every_group_the_annex_prints_has_a_layer_name(self):
        printed = groups(self.records)
        self.assertEqual(len(printed), 7)
        self.assertEqual(set(printed), set(GROUP_SLUGS))
        self.assertEqual(tuple(GROUP_SLUGS), printed)

    def test_an_unknown_group_is_refused_rather_than_misnamed(self):
        """A re-extraction that adds an eighth group must not be dropped quietly.

        The check runs through the real entry point -- the JSON document -- rather
        than a hand-built row, so it also proves the new group survives decoding
        far enough to be refused by name instead of raising something else.
        """
        document = dict(self.document)
        document["rows"] = [dict(self.raw[0], detay_alt_sinifi="YENİ STRATEJİ GRUBU")]
        with self.assertRaises(ValueError) as caught:
            msp_layer_specs(decode_rows(document))
        self.assertIn("YENİ STRATEJİ GRUBU", str(caught.exception))

    def test_the_catalogue_splits_into_the_eleven_layers_the_annex_implies(self):
        specs = msp_layer_specs(self.records)
        self.assertEqual(len(specs), 11)
        self.assertEqual(
            [(spec.name, spec.group, spec.geometry) for spec in specs],
            [(name, group, geometry) for name, group, geometry, _ in EXPECTED_LAYERS],
        )
        for spec, (_, _, _, codes) in zip(specs, EXPECTED_LAYERS):
            with self.subTest(layer=spec.name):
                self.assertEqual(tuple(code.id for code in spec.codes), codes)
                # The caption is what a planner picks from, so it must name both.
                self.assertTrue(spec.codes[0].caption.startswith(codes[0] + " · "))

    def test_the_slots_are_the_rows_drawn_once_per_geometry(self):
        """32 slots from 28 rows: the four dual rows are counted twice."""
        specs = msp_layer_specs(self.records)
        self.assertEqual(sum(len(spec.codes) for spec in specs), 32)
        self.assertEqual(
            sum(len(row.geometry_kinds) for row in self.records), 32
        )
        self.assertEqual(
            len(self.records) + len(DUAL_GEOMETRY),
            sum(len(spec.codes) for spec in specs),
        )

    def test_the_four_dual_rows_are_drawable_both_ways(self):
        self.assertEqual(
            tuple(row.id for row in self.records if len(row.geometry_kinds) > 1),
            DUAL_GEOMETRY,
        )
        specs = {spec.name: spec for spec in msp_layer_specs(self.records)}
        for row_id in DUAL_GEOMETRY:
            with self.subTest(code=row_id):
                holders = [
                    spec for spec in specs.values()
                    if row_id in {code.id for code in spec.codes}
                ]
                self.assertEqual(
                    {spec.geometry for spec in holders}, {"POLYGON", "POINT"}, row_id
                )
                # One group, both geometries: the split is by geometry, never a
                # second classification.
                self.assertEqual(len({spec.group for spec in holders}), 1)
                row = next(row for row in self.records if row.id == row_id)
                for spec in holders:
                    drawn = rows_for_layer(self.records, spec)
                    self.assertIn(row, drawn)
                    self.assertEqual(spec.geometry in row.geometry_kinds, True)

    def test_the_plan_boundary_is_the_only_row_whose_class_differs(self):
        """MSP-001 prints SINIRLAR as its class and its own name as the group."""
        differing = [
            (row.id, row.detay_sinifi, row.detay_alt_sinifi)
            for row in self.records
            if row.detay_sinifi != row.detay_alt_sinifi
        ]
        self.assertEqual(differing, [("MSP-001", "SINIRLAR", "PLAN SINIRI")])


class MSPDecoderTests(unittest.TestCase):
    """The annex states its legend in prose; these are the rules that read it."""

    def setUp(self):
        self.by_id = {row.id: row for row in decode_rows()}
        self.raw = {row["id"]: row for row in rows()}

    def test_a_colour_cell_decodes_every_triplet_and_drops_a_bad_one(self):
        self.assertEqual(
            rgb_triplets("225/165/100;180/110/0;140/85/25"),
            ((225, 165, 100), (180, 110, 0), (140, 85, 25)),
        )
        self.assertEqual(rgb_triplets(""), ())
        self.assertEqual(rgb_triplets(None), ())
        self.assertEqual(rgb_triplets("225/165/100;bozuk;0/0/0"), ((225, 165, 100), (0, 0, 0)))

    def test_a_zero_alpha_is_the_annex_saying_there_is_no_area_fill(self):
        """The hatch, dot and boundary symbols carry their meaning elsewhere."""
        self.assertIsNone(fill_rgba({"tarama_rgb": None, "tarama_alpha": 0}))
        self.assertIsNone(fill_rgba({"tarama_rgb": "0/0/0", "tarama_alpha": 0}))
        self.assertEqual(
            fill_rgba({"tarama_rgb": "180/160/200", "tarama_alpha": 128}),
            (180, 160, 200, 128),
        )
        # Every symbol the annex draws without an area fill decodes to none, so
        # the renderer's NoBrush base is driven by the annex, not by a list.
        self.assertIsNone(self.by_id["MSP-001"].fill)
        self.assertIsNone(self.by_id["MSP-003"].fill)
        self.assertEqual(self.by_id["MSP-018"].fill, (180, 160, 200, 128))

    def test_the_outline_decodes_from_its_own_cell(self):
        self.assertEqual(self.by_id["MSP-009"].stroke, (0, 0, 0, 255))
        self.assertIsNone(self.by_id["MSP-002"].stroke)
        self.assertEqual(stroke_rgba({"sinir_rgb": None}), None)
        # MSP-026 is the one record whose boundary colour the annex printed in
        # the TİPİ column; the compiler resolves the slip, so the runtime still
        # reads a single field and `kaynak` still names where it came from.
        self.assertEqual(self.by_id["MSP-026"].stroke, (0, 160, 240, 255))
        self.assertEqual(self.raw["MSP-026"]["sinir_rgb"], "0/160/240")

    def test_a_weight_is_read_only_from_the_clause_that_states_one(self):
        """``ÇİZGİ KALINLIĞI`` states a line width; a bare millimetre does not.

        The trap this guards: MSP-026 opens with "NOKTA ÇAPI: 0.7 mm 1 mm
        aralıklı", and reading the first millimetre in the cell as a boundary
        weight would give the polygon a 0.7 mm outline the annex never measured.
        """
        self.assertEqual(self.by_id["MSP-001"].stroke_width_mm, 1.0)
        self.assertEqual(self.by_id["MSP-003"].stroke_width_mm, 0.7)
        self.assertEqual(self.by_id["MSP-026"].stroke_width_mm, 0.0)
        self.assertEqual(stated_line_width_mm("NOKTA ÇAPI: 0.7 mm 1 mm aralıklı"), 0.0)
        self.assertEqual(stated_line_width_mm("ÇİZGİ KALINLIĞI: 0.7 mm 2mm boşluk"), 0.7)
        self.assertEqual(stated_line_width_mm(""), 0.0)
        self.assertEqual(self.by_id["MSP-025"].stroke_width_mm, 0.2)

    def test_a_coloured_but_unmeasured_boundary_is_drawn_at_the_stated_default(self):
        """Only a boundary that has a colour and no measure can substitute one."""
        substituted = [
            row.id for row in self.by_id.values()
            if row.stroke is not None and not row.measures_its_boundary
        ]
        self.assertEqual(substituted, ["MSP-026"])
        self.assertEqual(self.by_id["MSP-026"].drawn_stroke_width_mm, BOUNDARY_WIDTH_MM)
        # A row the annex drew with no outline at all substitutes nothing: there
        # is no boundary for a default to stand in for.
        for row_id in ("MSP-002", "MSP-006", "MSP-018"):
            with self.subTest(code=row_id):
                self.assertTrue(self.by_id[row_id].measures_its_boundary)
        # And a row the annex did measure keeps its own number.
        self.assertEqual(self.by_id["MSP-001"].drawn_stroke_width_mm, 1.0)

    def test_a_gap_makes_a_dash_and_a_spacing_alone_does_not(self):
        """"2mm düz çizgi, 2mm boşluk" is a dash; "2 mm aralıklı" is a hatch.

        The thickness clause that opens the same sentence is not part of the
        dash: reading "ÇİZGİ KALINLIĞI: 0.7 mm 2mm düz çizgi, 2mm boşluk" from
        the top would make a 0.7 mm dash out of a 2 mm one.
        """
        self.assertEqual(self.by_id["MSP-003"].dash_mm, (2.0, 2.0))
        self.assertIsNone(self.by_id["MSP-025"].dash_mm)
        self.assertIn("boşluk", self.raw["MSP-003"]["stroke_desc"])
        self.assertEqual(dash_mm({"stroke_desc": "ÇİZGİ KALINLIĞI: 0.7 mm 2mm düz çizgi, 2mm boşluk"}),
                         (2.0, 2.0))
        self.assertIsNone(dash_mm({"stroke_desc": "ÇİZGİ KALINLIĞI: 0.2 mm 2 mm aralıklı"}))
        self.assertEqual(dash_mm({"stroke_desc": "2mm kesikli, 1mm boşluk"}), (2.0, 1.0))
        self.assertEqual(
            tuple(row.id for row in self.by_id.values() if row.dash_mm), ("MSP-003",)
        )

    def test_the_drop_shadow_is_the_bare_colour_the_annex_prints(self):
        self.assertEqual(self.by_id["MSP-001"].shadow, (178, 178, 178))
        self.assertEqual(shadow_rgb({"stroke_desc": "178/178/178 gölge"}), (178, 178, 178))
        # The annex prints it after the thickness, not alone in the cell.
        self.assertEqual(
            shadow_rgb({"stroke_desc": "ÇİZGİ KALINLIĞI:1 mm 178/178/178 gölge"}),
            (178, 178, 178),
        )
        # "%50 Saydam" and "Düz çizgi" are line notes, not colours.
        self.assertIsNone(shadow_rgb({"stroke_desc": "%50 Saydam"}))
        self.assertIsNone(shadow_rgb({"stroke_desc": "Düz çizgi"}))
        self.assertEqual(
            tuple(row.id for row in self.by_id.values() if row.shadow), ("MSP-001",)
        )

    def test_a_karolajs_second_number_is_the_grid_not_a_dot(self):
        """Reading 5*5 mm as a diameter would draw 5 mm dots in a 5 mm grid."""
        karolaj = self.by_id["MSP-024"]
        self.assertEqual(karolaj.pattern.kind, PATTERN_GRID_DOT)
        self.assertEqual(karolaj.pattern.spacing_mm, 5.0)
        self.assertEqual(karolaj.pattern.size_mm, 0.0)
        self.assertIn("karolaj", self.raw["MSP-024"]["hatch_desc"].lower())

    def test_each_pattern_kind_is_decoded_from_the_annexs_own_words(self):
        """Every phrase below is a cell as the annex prints it, not a paraphrase.

        The two patterns the annex states in colour rather than in prose are
        read from the cells themselves: a fill cell holding a ramp is a graded
        fill (MSP-002 prints three stops) and a symbol cell holding a palette is
        a category (MSP-014 prints four).  The keywords the older catalogue put
        in these cells -- "Kademeli renk dolgusu", "Kaynak türüne göre renkli
        nokta" -- are pinned as *not* working, because the Ministry never prints
        them and a decoder keyed on them was reading its own prose back.
        """
        self.assertEqual(
            pattern({"hatch_desc":
                     "ÇİZGİ KALINLIĞI: 0.5 mm 5*5 mm ara ile karolaj merkezlerinde noktalama"}).kind,
            PATTERN_GRID_DOT,
        )
        self.assertEqual(
            pattern({"stroke_desc": "NOKTA ÇAPI: 0.7 mm 1 mm aralıklı"}).kind,
            PATTERN_DOT_HATCH,
        )
        self.assertEqual(
            pattern({"hatch_desc": "ÇİZGİ KALINLIĞI: 0.2 mm 2 mm aralıklı"}).kind,
            PATTERN_LINE_HATCH,
        )
        self.assertEqual(
            pattern({"tarama_rgb": "225/165/100;180/110/0;140/85/25"}).kind,
            PATTERN_GRADIENT,
        )
        self.assertEqual(
            pattern({"sembol_rgb": "0/160/0;255/255/0;60/170/250;130/40/255"}).kind,
            PATTERN_CATEGORICAL,
        )
        # One colour in each cell is neither a ramp nor a palette: MSP-021 and
        # MSP-022 print the same colour twice, which is still one colour.
        self.assertEqual(pattern({"tarama_rgb": "250/150/70"}).kind, PATTERN_NONE)
        self.assertEqual(pattern({"sembol_rgb": "250/150/70;250/150/70"}).kind, PATTERN_NONE)
        # A stated shape beats a stated palette, and the broadest test comes
        # last: a dot whose sentence ends in "aralıklı" is still a dot.
        self.assertEqual(
            pattern({"stroke_desc": "NOKTA ÇAPI: 0.7 mm 1 mm aralıklı",
                     "sembol_rgb": "0/160/0;255/255/0"}).kind,
            PATTERN_DOT_HATCH,
        )
        self.assertEqual(pattern({"hatch_desc": "Kademeli renk dolgusu"}).kind, PATTERN_NONE)
        self.assertEqual(
            pattern({"hatch_desc": "Kaynak türüne göre renkli nokta"}).kind, PATTERN_NONE
        )
        self.assertEqual(pattern({}).kind, PATTERN_NONE)
        self.assertTrue(pattern({}).is_solid)
        self.assertFalse(pattern({"tarama_rgb": "1/2/3;4/5/6"}).is_solid)

    def test_a_dot_pattern_carries_the_diameter_the_annex_states(self):
        spot = self.by_id["MSP-026"]
        self.assertEqual(spot.pattern.kind, PATTERN_DOT_HATCH)
        self.assertEqual(spot.pattern.spacing_mm, 1.0)
        self.assertEqual(spot.pattern.size_mm, 0.7)
        # A dot pattern whose diameter the annex never prints reports zero, not a
        # guess: the renderer applies its own documented default instead.
        self.assertEqual(pattern({"stroke_desc": "Nokta çapı belirtilmemiş"}).size_mm, 0.0)

    def test_the_classed_and_categorical_rows_keep_all_their_colours(self):
        """The one multi-colour fill is a *rule*, and MSP-014 is the palette.

        MSP-002's fill cell lists three tones, and a cell listing several colours
        used to decode as a ramp.  EK-1b says otherwise: it draws three separate
        bullseyes and its note ties the tone to the settlement's density, so the
        fill is three discrete classes and not a gradient.  The kind is read from
        the class rule, which is why the rule has to be read before the cells.
        """
        classed = self.by_id["MSP-002"]
        self.assertEqual(classed.pattern.kind, PATTERN_CLASSED)
        # Although the *fill* is three tones, the row's own mark colour is single:
        # EK-1b's note states one ink for the bullseye (255/170/0) and the three
        # tones are what the density picks between.  The two are different fields
        # and must not be confused -- the tones are on the pattern, the ink on
        # the row.
        self.assertEqual(classed.colors, ((255, 170, 0),))
        self.assertEqual(len(classed.pattern.tones), 3)
        # The three tones are the annex's own RGB triplets, in the order it
        # printed them, not a ramp interpolated between the first and last.
        self.assertEqual(
            [tuple(tone) for tone in classed.pattern.tones],
            [(225, 165, 100), (180, 110, 0), (140, 85, 25)],
        )
        categorical = self.by_id["MSP-014"]
        self.assertEqual(categorical.pattern.kind, PATTERN_CATEGORICAL)
        self.assertEqual(len(categorical.colors), 4)
        # A multi-colour *mark* is MSP-014's palette; MSP-002's three tones are a
        # classed fill and live on the pattern, so this list is the one row.
        self.assertEqual(
            sorted(row.id for row in self.by_id.values() if len(row.colors) > 1),
            ["MSP-014"],
        )

    def test_no_row_falls_into_the_graded_fill_the_annex_never_draws(self):
        """``PATTERN_GRADIENT`` has no row left, and that is the EK-1b result.

        Before the drawing annex was read, MSP-002's three-tone cell was decoded
        as a ramp and this was the one gradient in the catalogue.  The branch is
        kept -- the decoder is a total function over the cells and a re-extraction
        could legitimately state one -- but the test *can* fail: a row the annex
        draws as a ramp would move back here, and then the assertion below is the
        one that says so.  Pinned on the decoded kind rather than on the raw cell,
        so it is the decoder's answer and not `len(colors) > 1`.
        """
        graded = [row.id for row in self.by_id.values() if row.pattern.kind == PATTERN_GRADIENT]
        self.assertEqual(graded, [])
        self.assertEqual(
            sorted({row.pattern.kind for row in self.by_id.values()} - {PATTERN_NONE}),
            [PATTERN_CATEGORICAL, PATTERN_CLASSED, PATTERN_DOT_HATCH, PATTERN_GRID_DOT,
             PATTERN_LINE_HATCH],
        )

    def test_only_one_row_is_driven_by_a_class_rule_and_it_is_MSP_002(self):
        """A rule binds a field, so it has to be the row whose note names one.

        ``class_rule`` is read by two consumers that must agree: the workspace
        builds its dropdowns from the rule's own counts and the styler builds its
        expressions from the same numbers.  If a second row grew a rule the two
        would still work, but the audit trail would not -- so the rule's tones are
        checked against the annex's fill cell and its sizes against EK-1b's
        measurement, and both are marked with where they came from.
        """
        ruled = [row.id for row in self.by_id.values() if row.sinif_kurali]
        self.assertEqual(ruled, ["MSP-002"])
        rule = class_rule()
        self.assertEqual(rule, dict(self.by_id["MSP-002"].sinif_kurali))
        # Tones: the annex's own, in its own order.
        self.assertEqual(
            [tuple(tone) for tone in rule["tonlar"]],
            [(225, 165, 100), (180, 110, 0), (140, 85, 25)],
        )
        self.assertEqual(rule["ton_kaynak"], "ek_1e_tarama_rgb_yazim_sirasi")
        # Sizes: EK-1b's measured diameters, ascending -- a renderer decision,
        # and named as one.  Three sizes because EK-1b draws three bullseyes.
        self.assertEqual(rule["boyut_kaynak"], "ek_1b_cizilen_hedef_caplari_artan")
        self.assertEqual(rule["simge_boyutlari_mm"], sorted(rule["simge_boyutlari_mm"]))
        self.assertEqual(len(rule["simge_boyutlari_mm"]), 3)
        # The two fields the rule binds are the two the workspace creates, and
        # the rule is the only place their names are written.
        self.assertEqual(
            {rule["alan_alani"], rule["simge_alani"]},
            {"yerlesme_yogunlugu", "yerlesme_kademesi"},
        )

    def test_every_point_row_reaches_a_drawing_the_plugin_can_make(self):
        """The shape vocabulary is *total* over the 16 point rows.

        This is the guard against the failure that looks like success: a row with
        no shape decodes to a plain grey circle, which renders, exports and audits
        without complaint while saying nothing the Ministry drew.  Every point row
        must therefore be raster artwork, a native ``MarkerShape``, or one of the
        compound drawings built from its own measured rings -- and the three sets
        are disjoint, so a row cannot be two of them.
        """
        point_rows = [row for row in self.by_id.values() if "POINT" in row.geometry_kinds]
        self.assertEqual(len(point_rows), 16)
        self.assertEqual(
            {row.shape_kind for row in point_rows},
            {"raster", "native", "compound"},
        )
        self.assertEqual(
            {row.id for row in point_rows if row.shape_kind == "none"},
            set(),
        )
        # The tables the three names come from are disjoint too, and every row
        # that names one really is in it.
        self.assertEqual(set(MARKER_SHAPES) & set(COMPOUND_SHAPES), set())
        for row in point_rows:
            with self.subTest(code=row.id):
                if row.shape_kind == "raster":
                    self.assertTrue(row.sembol_ikon.startswith("resources/"))
                    self.assertTrue((ROOT / row.sembol_ikon).exists(), row.sembol_ikon)
                elif row.shape_kind == "native":
                    self.assertIn(row.sembol_sekli, MARKER_SHAPES)
                else:
                    self.assertIn(row.sembol_sekli, COMPOUND_SHAPES)
                    # A bullseye is nothing *but* its measured rings, so the one
                    # shape of the three that is built from them must have them.
                    if row.sembol_sekli == "hedef":
                        self.assertTrue(row.sembol_halkalar, "hedef halkasız çizilemez")

    def test_every_row_states_whether_its_ink_is_solid_or_hollow(self):
        """EK-1b draws one star filled and another hollow, so the mark is data.

        The pair is worth pinning because the two rows are otherwise identical:
        MSP-019 and MSP-020 are both five-pointed stars at the same measured size
        and differ only in whether the annex fills them.  A renderer that ignored
        the mark would draw them the same and nothing else would notice.
        """
        point_rows = [row for row in self.by_id.values() if "POINT" in row.geometry_kinds]
        for row in point_rows:
            with self.subTest(code=row.id):
                self.assertIn(row.sembol_dolgu, (SOLID_MARK, HOLLOW_MARK))
        self.assertEqual(self.by_id["MSP-019"].sembol_dolgu, SOLID_MARK)
        self.assertEqual(self.by_id["MSP-020"].sembol_dolgu, HOLLOW_MARK)
        self.assertEqual(
            sorted(row.id for row in self.by_id.values() if row.is_hollow), ["MSP-020"]
        )

    def test_the_measured_symbol_sizes_replace_the_uniform_default(self):
        """Each point symbol is drawn at the diameter EK-1b measured for it.

        A single default would flatten a distinction the annex makes: MSP-019's
        star is measured at more than twice MSP-008's disc.  Only a row EK-1b
        measured nothing for may fall back, and there is no such row.
        """
        point_rows = [row for row in self.by_id.values() if "POINT" in row.geometry_kinds]
        self.assertTrue(all(row.sembol_boyut_mm for row in point_rows))
        self.assertTrue(all(row.marker_size_mm == row.sembol_boyut_mm for row in point_rows))
        self.assertGreater(
            self.by_id["MSP-019"].marker_size_mm, self.by_id["MSP-008"].marker_size_mm
        )

    def test_the_measured_hatch_axis_replaces_the_fixed_default(self):
        """EK-1b measures the hatch axis; the annex's prose never states it.

        The annex says "2 mm aralıklı" and stops -- spacing, no axis -- so a fixed
        45° was standing in for a measurement nobody had taken.  EK-1b draws
        MSP-025's hatch vertically, and the measured value is the one the styler
        reads.  MSP-024's is *not* measured (its cell is a dotted grid, not ruled
        lines), so it stays ``None`` and the renderer's named default applies.
        """
        measured = {row.id: row.tarama_aci_derece for row in self.by_id.values()
                    if row.tarama_aci_derece is not None}
        self.assertEqual(measured, {"MSP-025": 90.0})
        self.assertIsNone(self.by_id["MSP-024"].tarama_aci_derece)
        # 90 is the measurement, not the renderer's 45° default standing in for
        # it: the two are different numbers, which is what makes this failable.
        self.assertNotEqual(measured["MSP-025"], 45.0)

    def test_a_pictogram_depends_on_which_geometry_is_being_drawn(self):
        """A dual row is a filled area *and* a glyph; asking without a geometry is the bug.

        The bug this guards: ``is_pictogram`` used to ignore the geometry it was
        asked about, so every dual row was counted as a missing glyph on its
        *polygon* layer too -- three pictograms reported for ``msp_ekonomi_alan``,
        which draws no glyph at all.

        Since the drawing annex was read the predicate means something narrower
        than "is this a glyph": it means a glyph the plugin cannot draw, and no
        row is one any more.  Both halves are asserted -- that no row is reported
        on a polygon layer, and that no row is reported on its point layer either
        -- because the second is what stops a regression from silently reverting
        to grey circles.

        There is deliberately no geometry-free shorthand: a property that asks
        "is this a pictogram?" without saying which form it means is the bug this
        test was written for, so the only way to ask is with a geometry.
        """
        for row_id in DUAL_GEOMETRY:
            with self.subTest(code=row_id):
                self.assertFalse(self.by_id[row_id].is_pictogram_for("POLYGON"))
        self.assertEqual(
            tuple(row.id for row in self.by_id.values() if row.is_pictogram_for("POLYGON")),
            (),
        )
        self.assertEqual(
            tuple(row.id for row in self.by_id.values() if row.is_pictogram_for("POINT")),
            (),
        )
        self.assertFalse(hasattr(MSPRow, "is_pictogram"), "geometrisiz kısayol geri gelmemeli")
        self.assertNotIn("MSP-002", PICTOGRAMS)
        self.assertFalse(self.by_id["MSP-014"].is_pictogram_for("POINT"),
                         "renkli nokta bir piktogram değil, renkleri çiziliyor")
        # The old list is kept: it names the rows that *were* missing glyphs, so
        # a re-extraction that loses a shape has to find them drawn here instead.
        for row_id in PICTOGRAMS:
            with self.subTest(regression=row_id):
                self.assertNotEqual(self.by_id[row_id].shape_kind, "none")

    def test_the_geometry_column_decodes_in_the_annexs_own_order(self):
        self.assertEqual(self.by_id["MSP-002"].geometry_kinds, ("POLYGON", "POINT"))
        self.assertEqual(self.by_id["MSP-001"].geometry_kinds, ("POLYGON",))
        self.assertEqual(
            {row.geometri for row in self.by_id.values()},
            {"POLYGON", "LINE", "POINT", "POLYGON, POINT"},
        )
        self.assertEqual(set(GEOMETRY_KINDS), {"POLYGON", "LINE", "POINT"})
        self.assertEqual(set(GEOMETRY_SUFFIX), set(GEOMETRY_KINDS))


class MSPContractTests(unittest.TestCase):
    """What the workspace and the renderer must agree with the audit on."""

    def test_the_renderer_scale_is_the_scale_the_audit_accepts(self):
        """A symbol built in printed millimetres needs the scale they belong to."""
        self.assertEqual(PLAN_KADEMESI, "MSP")
        self.assertEqual(_literal(AUDIT_MODULE, "PLAN_LEVELS")[0], PLAN_KADEMESI)
        ranges = _literal(AUDIT_MODULE, "SCALE_RANGES")
        self.assertEqual(ranges["MSP"], (NOMINAL_SCALE, 500000))
        self.assertLessEqual(NOMINAL_SCALE, ranges["MSP"][1])

    def test_the_annexs_own_groups_cover_every_theme_the_audit_scores(self):
        """The audit reads ``strateji_bolgesi``; the groups are what fills it."""
        themes = _audit_msp_themes()
        self.assertEqual(len(themes), 6)
        text = _normalize(" ".join(groups()))
        self.assertEqual([name for name, tokens in themes.items()
                          if not any(token in text for token in tokens)], [])

    def test_the_normalizer_this_file_mirrors_is_still_the_audits(self):
        """This file cannot import the audit, so its copy is pinned to the source."""
        text = AUDIT_MODULE.read_text(encoding="utf-8")
        segment = ast.get_source_segment(text, _function(AUDIT_MODULE, "normalize"))
        self.assertIn("NFKD", segment)
        self.assertIn("ascii", segment)
        self.assertIn("[^A-Z0-9]+", segment)
        # And the copy really does fold the same way as the line it mirrors.
        self.assertEqual(_normalize("YERLEŞMELER SİSTEMİ"), "YERLESMELER_SISTEMI")
        self.assertEqual(_normalize("Su, Doğal Peyzaj ve Ekosistemler"),
                         "SU_DOGAL_PEYZAJ_VE_EKOSISTEMLER")

    def test_no_layer_field_is_one_the_audit_rejects_above_uip(self):
        """``DETAIL_LEVEL_LEAKAGE`` is an ERROR, so a parcel field would fail every MSP."""
        fields = _literal(WORKSPACE_MODULE, "LAYER_FIELDS")
        forbidden = _literal(AUDIT_MODULE, "UIP_DETAIL_FIELDS")
        self.assertEqual(sorted(set(fields) & set(forbidden)), [])
        self.assertEqual(len(fields), len(set(fields)))

    def test_the_layer_fields_carry_what_an_msp_decision_needs(self):
        fields = _literal(WORKSPACE_MODULE, "LAYER_FIELDS")
        for name in REQUIRED_LAYER_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, fields)
        # The audit's MSP branch requires a strategic region *or* a priority
        # status, and reads its classification from these names.
        classifications = _literal(AUDIT_MODULE, "CLASSIFICATION_FIELDS")
        self.assertIn("strateji_bolgesi", fields)
        self.assertIn("strateji_bolgesi", classifications)
        self.assertIn("gosterim_adi", fields)
        self.assertNotIn("bolge_turu", fields)

    def test_the_two_class_fields_the_rule_binds_are_on_every_layer(self):
        """The fields MSP-002's expression names have to exist to be evaluated.

        The rule binds one field to a tone and another to a mark size, so a layer
        without them would evaluate its expression against a name QGIS cannot
        resolve -- which draws nothing and reports nothing.  Both are on the
        template's one field list rather than only on the layer that draws
        MSP-002, because ``LAYER_FIELDS`` is a single list the workspace applies
        to every layer and the workspace test reads back as one contract.

        Their names are the annex's own words from MSP-002's note, and they are
        deliberately *not* the NİP fields: ``DETAIL_LEVEL_LEAKAGE`` would fire on
        a parcel-level field, and reusing another level's name would make one
        column mean two things.
        """
        fields = _literal(WORKSPACE_MODULE, "LAYER_FIELDS")
        rule = class_rule()
        self.assertEqual(rule["alan_alani"], "yerlesme_yogunlugu")
        self.assertEqual(rule["simge_alani"], "yerlesme_kademesi")
        for name in (rule["alan_alani"], rule["simge_alani"]):
            with self.subTest(field=name):
                self.assertIn(name, fields)
                self.assertNotIn(name, _literal(AUDIT_MODULE, "UIP_DETAIL_FIELDS"))
                # ``yogunluk_kademesi`` is the NİP density field, which the audit
                # reads as a NİP classification.  Reusing its name here would make
                # one column mean two things and would score an MSP as a NİP.
                self.assertNotEqual(name, "yogunluk_kademesi")
        # Both are text: the workspace writes the class as a string ("1", "2",
        # "3"), which is what the styler's own decoder reads back through.
        self.assertEqual(
            sorted(name for name in fields if name.startswith("yerlesme_")),
            ["yerlesme_kademesi", "yerlesme_yogunlugu"],
        )

    def test_the_action_table_carries_what_the_monitoring_engine_reads(self):
        """``msp_eylem_plani`` is the Article 16 table; its names are the contract."""
        action_fields = [
            element.elts[0].value
            for element in _tuple_elements(WORKSPACE_MODULE, "ACTION_FIELDS")
        ]
        for name in MONITORING_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, action_fields)
        self.assertIn("plan_kademesi", action_fields)
        self.assertEqual(len(action_fields), len(set(action_fields)))
        self.assertEqual(ACTION_TABLE, "msp_eylem_plani")
        self.assertEqual(CATALOG_TABLE, "msp_katalogu")

    def test_the_companion_table_stores_every_field_the_annex_prints(self):
        """A re-extraction that adds a column must be stored, not silently dropped."""
        columns = _literal(WORKSPACE_MODULE, "CATALOG_COLUMNS")
        names = [column for column, _ in columns]
        self.assertEqual(len(names), len(set(names)))
        source_keys = {source for _, source in columns}
        printed = {key for row in rows() for key in row}
        self.assertEqual(printed - source_keys, set(), "katalog alanı tabloya yazılmıyor")
        self.assertEqual(source_keys - printed, set(), "tabloda katalogda olmayan alan")
        # The catalogue's own order is the annex's order: id first, page second.
        self.assertEqual(names[:2], ["id", "sayfa"])

    def test_the_catalogue_module_never_imports_qgis(self):
        """The decoding is pure so both runtimes and this file can read it."""
        imported = _imported_modules(CATALOG_MODULE)
        self.assertEqual(
            sorted(name for name in imported if name.split(".")[0] in ("qgis", "osgeo")),
            [],
        )
        self.assertIn("json", imported)


if __name__ == "__main__":
    unittest.main()
