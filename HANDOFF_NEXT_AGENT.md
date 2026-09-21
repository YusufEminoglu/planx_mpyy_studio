# HANDOFF_NEXT_AGENT.md — `planx_mpyy_studio`

> **Written:** 2026-09-20
> **For:** the next AI agent taking over this plugin
> **Author and sole contributor of everything in the git history:** Yusuf Eminoğlu
> (`geospacephilo@gmail.com`) — see Rule 0 below, it is not negotiable.

**This file is internal. It must never ship in the Hub zip.** It is listed in the
plugin's `.zipignore`; if you add another handoff/work-order document, add it there too
(see *Traps*, item 3 — nothing else will catch it).

---

## 0. Rule 0 — before you write a single commit

**No AI is ever credited as a contributor. Ever.** Every commit ships under **Yusuf
Eminoğlu's** name alone.

- Never add a `Co-Authored-By:` trailer, never "Generated with …", never a bot signature,
  never an AI-looking `user.name` / `user.email`.
- This is enforced, not advisory: local git hooks reject it, a `no-ai-attribution` GitHub
  Actions workflow fails the build in every repo, and `py -3 packaging/pf.py attribution`
  audits the git history and the live GitHub contributor list.
- If you cannot comply, **stop and say so** instead of committing.

Also: **ask before pushing to a remote or uploading anything outward-facing.** This
plugin currently has **no remote at all** (see §2), so there is nothing to push to yet.

---

## 1. Orientation — this is a monorepo of independent repos

`C:\Users\YE\PyCharmMiscProject\qgis_plugins` is the workspace root, and **it is not a git
repo**. Each plugin directory is its **own** repo. `planx_mpyy_studio` is at:

```
C:\Users\YE\PyCharmMiscProject\qgis_plugins\planx_mpyy_studio
```

Read these first, in this order — they are the canonical briefs, not this file:

1. **`AGENTS.md`** (workspace root) — the brief for every AI agent. `CLAUDE.md`,
   `GEMINI.md` and the Cursor/Copilot files are byte-identical thin pointers to it.
2. **`docs/TRAPS.md`** (workspace root) — ~25 traps as symptom → cause → fix.
3. **`plugins.toml`** (workspace root) — the **only** plugin list. Never hard-code one.
   The `planx_mpyy_studio` entry is at lines 26–36 and carries the test commands.

One command runs every gate and both test suites:

```powershell
py -3 packaging/pf.py verify planx_mpyy_studio
```

(`pf gate <plugin>` for just the packaging gates; `pf status --hub` for what is actually
published. `pf drift` cross-checks the registry against disk.)

**Only the QGIS Hub's security scan blocks a version** (Bandit / detect-secrets). Flake8
and Qt6 findings are informational — `hub_qt6_scan.py` is an *advisor*, and there is no
blocking Qt6 gate. A genuinely blocked version number is **burned**; you cannot reuse it.

---

## 2. Where this plugin actually stands

| | |
|---|---|
| `metadata.txt` version | **`1.0.0`** |
| `experimental` | `False` |
| `qgisMinimumVersion` / `Maximum` | `3.44` / `4.99` |
| git remote | **none** (`git remote -v` is empty; `plugins.toml` has `repo = ""`) |
| git tags | **none** |
| Published to the QGIS Hub? | **NEVER.** Not once. |
| Last commit | `f8fbb5e` "Packaging: keep docs/ out of the release zip" (`12bc49e` is an older ancestor, not HEAD) |
| Latest gate result | **`VERIFY OK`**, both runtimes, 11 QGIS suites each, 10 passed / 39 subtests (2 pure files) |

**Do not read "1.0.0" as "released".** It is a *working* version number. The 2.x numbering
was deliberately voided and the tree reset to 1.0.0 for a first public release that has
not happened yet.

### STANDING ORDER (from Yusuf, 2026-09-20) — stay on 1.0.0

> "mpyy eklentisi tamamen bitene kadar tüm gelişmeler V1.0 olarak kalmaya devam edecek."

Every further change keeps the version at **1.0.0**: do **not** bump `metadata.txt`, do
**not** cut a tag, do **not** add a new `CHANGELOG.md` section. **Ask before any bump.**

---

## 3. ⚠️ Uncommitted work — read this before you touch anything

The engine-wiring regression described below was committed as `f40ffee` and the stale
development-history cleanup as `bde68c6`. The tree was clean when the 2026-09-20 follow-up
started. The current uncommitted work is two source-backed changes that were developed together —
the ground-metre sizing pass and the Ek-1e detail-hierarchy integration:

```
 M CHANGELOG.md
 M HANDOFF_NEXT_AGENT.md
 M core/mpyy_detail_catalog.py
 M core/mpyy_workspace.py
 M core/styler.py
 M styles/mpyy_detail_catalog/decisions.json
 M tests/test_fonts_qgis.py
 M tests/test_mpyy_levels_qgis.py
 M tests/test_mpyy_workspace_qgis.py
?? core/mpyy_detail_hierarchy.py
?? styles/mpyy_detail_hierarchy.json
?? tools/compile_mpyy_detail_hierarchy.py
```

No workspace-root file changed in this follow-up. `plugins.toml` already contains
`tests/test_engine_wiring_pure.py` from the committed wiring fix.

### 3.1 Ground-metre sizing

The sizing work converts every catalog paper measurement to ground metres at the nominal
plan scale (`mm × scale / 1000`) across widths, marker sizes, offsets, intervals, hatch
spacing, dash vectors and repeated text. The scale table is UİP/MUİP 1:1,000; NİP/MNİP
1:5,000; ÇDP/MÇDP25 1:25,000; MÇDP100 1:100,000. A runtime audit expands **221** border
decision rows to **236 concrete rules** and asserts every target exists, generates its
boundary, preserves required dash patterns and uses map metres. Both counts are pinned in
`tests/test_mpyy_levels_qgis.py`, and they move independently: a wildcard address covers
every rule of its type, so one added decision row can shift the second count by more than
one. It passes in isolation on QGIS 3.44 and 4.2. The same isolation run exposed and fixed
two state-dependent symbol-tree assumptions: `MarkerLine` containers are no longer
mistaken for sized marker leaves, and a layer reporting `RasterFill` is touched only when
it actually exposes `imageFilePath()`. The same pass also made ordinary text fallback
explicitly portable: catalog loading registers the bundled fonts even when the engine is
used outside `initGui()`, and missing Arial/Calibri-style text families fall back to
bundled DejaVu Sans. No system font install is required.

One `cross` family needed a geometry fix, not just a unit change. The annex's "2 mm" is the
clear **gap after** a 3 mm mark, not its centre-to-centre interval; the old reading made
the marks overlap, most visibly on Toplu Konut and Gecekondu Önleme. Those four decision
rows were renamed `interval_mm` → `gap_mm`, and the resulting interval — 5 mm of paper,
i.e. 5 m at 1:1,000 and 25 m at 1:5,000 — is asserted exactly, in both values and both
units, in `tests/test_mpyy_levels_qgis.py`.

### 3.2 Ek-1e detail hierarchy

`styles/mpyy_detail_hierarchy.json` holds the Ek-1e polygon/line classification: **592
records** (UİP 275, NİP 199, ÇDP 118), each with symbol name, detail class and subclass,
plan level, geometry, SLD rule and source page. It is compiled by
`tools/compile_mpyy_detail_hierarchy.py` — which does **not** ship, because `tools` is in
`.zipignore` — and read at runtime by `core/mpyy_detail_hierarchy.py`.

`create_mpyy_workspace` writes it into a **companion table, `mpyy_detay_katalogu`**, beside
the XSD-backed tables rather than inside them: it adds no field to any feature type and
leaves every code list untouched. `test_catalog_recompiles_identically_from_the_official_zip`
is what proves that promise — it recompiles the schema from
`~/Downloads/planGMLShema_1_7.zip` and asserts the result equals the bundled catalog, so a
hand-edited code list fails there. The table loads as one more layer, "Detay kataloğu
hiyerarşisi", and its rows feed the rule descriptions (`sembol adı → detay sınıfı → detay
alt sınıfı`) and the layer custom properties `mpyy/detay_sinifi`, `mpyy/detay_alt_sinifi`
and `mpyy/detay_hiyerarsisi`.

Two traps this work produced, both now guarded:

- **The INSERT is a plain literal, and that is deliberate.** The Hub's Bandit gate (B608)
  reads *any* f-string whose text reads `INSERT INTO ... VALUES` as a SQL injection vector
  and blocks the upload. Bandit inspects only strings built by f-string / `%` / `+` /
  `.format()` / `.replace()`; a plain literal passed to `execute` is not a string-building
  operation, so it is not flagged at all. Do not "tidy" it back into an f-string, and do
  not reach for `# nosec` — neither is needed, and the suppression would be the worse
  answer. The adjacent-string-literal form is still one `Constant` after parsing, so the
  statement stays readable across lines.
- **`tests/test_mpyy_workspace_qgis.py` compares the stored rows column by column**, in
  `DETAIL_HIERARCHY_COLUMNS` order, because a bare row count cannot see a column-order
  drift in the INSERT. No two columns of a level hold the same value in every one of its
  rows, so any swap fails the assertion; that was measured by performing the swap.

Residual, and now **decided: leave the matching exactly as it is.** 38 of the 592 records —
exactly one for each of 38 level/type pairs, including `IcmesuTesis` and `KatiAtikTesis` at
all three levels — carry `sld_kurali: "*"`. `record_for_rule`
matches a rule by exact label, so a `*` record never matches and its rule-level description
is never applied. That is the correct behaviour; turning it into a fallback would write
wrong data. Measured 2026-09-21 across `UIP/SuYuzeyi`, `UIP/PlanSiniri`, `UIP/KiyiYapilari`,
`NIP/TeknikAltyapi`, `NIP/EnerjiUretim`, the three `KatiAtikTesis` types and several more:

- **`*` does not mean "every rule of this type."** On `UIP/KiyiYapilari` the `*` record is
  "LİMAN" while the type's other 14 rules each have their own record. A fallback would
  stamp "LİMAN" on the one remaining rule — which is the `ELSE` catch-all the engine
  appends, "Kodu girilmemiş / resmî gösterimi yok". All 38 types would get their umbrella
  name glued to that rule.
- **Where the type's rules are genuinely distinct, the umbrella name is simply wrong.**
  `UIP/PlanSiniri`'s `*` is "PLAN ONAMA SINIRI" sitting over the rules PLAN, REVIZYON,
  ILAVE and ILAVE_REVIZYON — a revision boundary is not the plan approval boundary. Same
  shape on `NIP/TeknikAltyapi`, whose `*` is "TEKNİK ALTYAPI ALANI" over ENERJI, ICMESUYU,
  ATIKSU, KATI_ATIK, KANALIZASYON and ULASTIRMA.
- **Nothing is lost by leaving it.** The annex data reaches the user at layer level,
  computed from all of a type's records: `mpyy/detay_sinifi`, `mpyy/detay_alt_sinifi` and
  the full `mpyy/detay_hiyerarsisi` JSON are all set even when `*` is the type's only
  record (verified on `UIP/SuYuzeyi`, `UIP/PlanSiniri`, `NIP/BoruHatti`), and
  `UIP/KiyiYapilari`'s 14 named rules keep their own descriptions.

So `*` means "this annex row is keyed to the **type**, not to a single SLD rule label" —
which is the same statement as the 32 of 38 pairs that have no other record at all. Do not
implement a fallback, and do not edit the JSON to invent rule labels for those rows.

Two defects reached that metadata, both resolved 2026-09-21. They are one investigation:
fixing the second is what made the last of the first visible. A third change to the same
field — the label set itself, fourteen pairs in all — is recorded in §6.

**Defect 1 — the annex does not treat one spelling as canonical; it prints both, and labels
were shipping as two.** `UIP/KiyiYapilari`'s `mpyy/detay_alt_sinifi` read
`DENIZYOLLARI | DENİZYOLLARI` because the compiled catalogue carried both spellings and
`apply_renderer_hierarchy` joins a type's distinct subclasses with a pipe. **Nine labels were
affected**: four found and repaired first (60 rows), the pairing fix below exposing the rest
(9 further rows, 69 in all), the plural/singular merge of §6 adding 14 — **82 distinct rows,
one of them counted in both passes**. Five further labels were *not* duplicates anywhere in
the catalogue and were invisible to that hunt; they were found by a label-versus-code-list
pass and repaired the same day, **79 rows** (§6). **161 rows of 592 carry a label this work
renamed**, shipped by a change set of **113 records** against the recorded baseline — 109
`detay_alt_sinifi` and 6 `detay_sinifi` field changes. The table below is all fourteen:

| shipped before | shipped now | rows repaired | why that spelling |
| --- | --- | --- | --- |
| `DENIZYOLLARI` | `DENİZYOLLARI` | 31 | code-list group `DENİZYOLLARI` |
| `AÇIK VE YEŞIL ALANLAR` | `AÇIK VE YEŞİL ALANLAR` | 26 | code-list group `AÇIK VE YEŞİL ALANLAR` |
| `YERLEŞIM ALANLARI` | `YERLEŞİM ALANLARI` | 2 | code list spells it so, inside `KONUT ALANLARI / YERLEŞİM ALANLARI` |
| `SOSYALVE KÜLTÜREL TESIS ALANLARI` | `SOSYAL VE KÜLTÜREL TESİS ALANI` | 1 | run-together word split; the singular is where the row below ends up |
| `ALAN KULANIMLARI` | `ALAN KULLANIMLARI` | 2 | 509 rows against 2; misspelling of the DETAY SINIFI value |
| `SOSYAL ALTYAPI ALANLARI` | `SOSYAL ALT YAPI ALANLARI` | 2 | code-list group `SOSYAL ALT YAPI ALANLARI` |
| `ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLARI` | `ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLAR` | 3 | code-list group `… VE SINIRLAR` |
| `ALAN KULLANIMI` | `ALAN KULLANIMLARI` | 2 | 509 rows against 2; singular of the same DETAY SINIFI value |
| `SOSYAL VE KÜLTÜREL TESIS ALANLARI` | `SOSYAL VE KÜLTÜREL TESİS ALANI` | 14 | code-list group `SOSYAL VE KÜLTÜREL TESİS ALANI`; **merged**, not respelled — see §6 |
| `DEMIRYOLLARI` | `DEMİRYOLLARI` | 11 | code-list group `DEMİRYOLLARI`; shipped undotted only |
| `ENERJI ÜRETIM, DAĞITIM VE DEPOLAMA` | `ENERJI ÜRETİM DAĞITIM VE DEPOLAMA` | 34 | code-list group name exactly, which dots `ÜRETİM`, leaves `ENERJI` undotted and drops the comma |
| `İDARI SINIRLAR` | `İDARİ SINIRLAR` | 18 | code-list group `İDARİ SINIRLAR`; shipped undotted only |
| `SAĞLIK TESISLERI ALANLARI` | `SAĞLIK TESİSLERİ ALANI` | 5 | code-list group is the **singular**; merged |
| `EĞITIM TESISLERI ALANLARI` | `EĞİTİM TESİSLERİ ALANI` | 11 | code-list group is the **singular**; merged |

**Read that last column exactly as written; an earlier draft of this file said "what the
code list says" for all of them and that is false.** Ten of the twelve distinct kept
spellings *are* `ust_grup_adi` values in `styles/mpyy_detail_catalog.json`: `DENİZYOLLARI`,
`AÇIK VE YEŞİL ALANLAR`, `SOSYAL ALT YAPI ALANLARI`, `ÖZEL KANUNLARLA BELİRLENEN ALAN VE
SINIRLAR`, `SOSYAL VE KÜLTÜREL TESİS ALANI`, `DEMİRYOLLARI`, `ENERJI ÜRETİM DAĞITIM VE
DEPOLAMA`, `İDARİ SINIRLAR`, `SAĞLIK TESİSLERİ ALANI` and `EĞİTİM TESİSLERİ ALANI`. The other
two are not settled by the code list at all: `YERLEŞİM ALANLARI` appears in it only inside the
longer group name `KONUT ALANLARI / YERLEŞİM ALANLARI`, and `ALAN KULLANIMLARI` is a DETAY
SINIFI value with no code-list counterpart that wins on count. The tie-break is *not* "the
majority spelling": for `DENİZYOLLARI` the kept form was the minority one before the repair.

The last row is the one to understand before deleting anything. p.64 prints the singular
`ALAN KULLANIMI` in exactly one DETAY SINIFI cell in the entire annex — 302 cells print the
plural — and that cell belongs to `ELEKTRİKLİ ARAÇ ŞARJ İSTASYONU`, whose own block the
pairing fix now reads. Those two rows (UIP and NIP) are repaired rather than spelling-swapped,
which is why the table counts them: their class reads `ALAN KULLANIMLARI` before and after,
because the old pairing had given them a *different* row's plural. Measured by removing the
entry and recompiling: the two rows then ship `ALAN KULLANIMI` while 507 others ship the
plural. Its sibling `ALAN KULANIMLARI` is not dead weight either — it prints in one DETAY
SINIFI cell as well (p.96, the `… MAKİLİK-FUNDALIK ALAN` row) and carries its own 2 rows, so
removing that entry likewise puts 2 more rows on a second spelling.
`_assert_one_spelling_per_label` does **not** fire on either — the two spellings fold to
different keys — so the one-letter check in `tests/test_detail_hierarchy_pure.py` is the only
thing standing between the catalogue and a duplicate the plugin's own fold-based guards
cannot see.

Each pair is one label. Most differ only by the Turkish dotted İ, by a word that ran together,
by a dropped letter or plural, or by a trailing `-I`; four (the three merges of §6 and the
run-together plural that reaches one of them) go further and file one concept under two names,
and those are three characters apart folded rather than one letter. Every variant **is printed
in EK-1e itself**, so nothing was invented and no third spelling was added — the only question
was which of the annex's own spellings to keep. `EK-1e.docx` cannot answer that alone either.
Measured on its own `word/document.xml` (runs concatenated; the file carries real U+0130 İ, so
an exact substring count is the count): it prints **both** spellings for **ten of the fourteen**
pairs, and for the other four it prints only the annex's own form — `İDARI SINIRLAR` (7 cells),
`SAĞLIK TESISLERI ALANLARI` (5), `EĞITIM TESISLERI ALANLARI` (9) and `ENERJI ÜRETIM, DAĞITIM VE
DEPOLAMA` (19, the comma'd spelling); it never dots or singularises any of those four. Where it
does lean on the ten, it leans against the compiler: it prints the undotted `DENIZYOLLARI` in 18
cells against 2 dotted, so the dotted form that ships wins on the code list alone, not on any
reproduction's preference.
The rule the compiler follows is therefore two tiers, and the table above spells out which
label falls in which: the Ministry's
machine-readable list (`ust_grup_adi` in `styles/mpyy_detail_catalog.json`) where the label
is a code-list value, and otherwise the spelling the catalogue itself already carries on the
most rows. Either way the same value reaches `resources/turkish_labels.tsv` and the rule
descriptions, so a planner sees one classification, not two.

**Defect 2 — the extractor's text order is not the printed order, so a title borrowed the
class of the symbol printed above it.** `pypdf`'s plain `extract_text()` does not emit a
page's blocks in printed (top-to-bottom) order. Measured on p.64: the stream is
`ELEKTRİKLİ ARAÇ ŞARJ İSTASYONU` (y=773.8, top of page), then `AKARYAKIT VE SERVİS
İSTASYONU ALANI` (y=430.5), then **that second symbol's** block at y=401.2
(`ALAN KULLANIMLARI` / `KENTSEL ÇALIŞMA ALANLARI`), and only then the top symbol's own
block at y=740.1 (`KARAYOLLARI`). The blocks come out bottom-up while the titles come out
top-down, so a block's own title is not the nearest title before it in the text — pairing
around a block's text position hands a symbol the classification of its neighbour. 13
records inherited a whole classification that way. `_page_hierarchy` now pairs by printed
position — the block directly below the title's own printed line, with no other title
between them — using per-character y from the same `visitor_text` extraction the file
already used, so no shipped value changed except the ones that were wrong. Two further
faults surfaced and are handled: a title that **wraps onto a second 12 pt line** (the
anchor is the bottom line of the title, not the top), and an **empty `DETAY SINIFI` cell**,
whose missing whitespace lets the lazy regex run on and swallow the rest of the page (a
match that ends below the next printed title is rejected). p.19's
`İMAR HAKKI AKTARIM ALANI SINIRI` has both label cells blank in the annex *and* in
`EK-1e.docx`, so its class comes from the Ministry's code list, which files layer
`SNR_IMAR_HAKKI_AKT` under `ust_grup_adi` = PLANLAMA SINIRLARI, same as every other
`*_SINIRI` continuation on those pages — recorded in `CONTINUATION_HIERARCHY`.

The 13 re-paired records, by page (only `detay_sinifi` / `detay_alt_sinifi` moved; no
`sembol_adi`, `sld_kurali` or `plan_gml_tipi` was touched anywhere):

| page | symbol | was | now |
| --- | --- | --- | --- |
| 19 | `İMAR HAKKI AKTARIM ALANI SINIRI` | (page-spill garbage class) | `SINIRLAR` / `PLANLAMA SINIRLARI` |
| 23 | `ORGANİZE SANAYİ BÖLGESİ HİZMET VE DESTEK ALANI (HDA)` | `SINIRLAR` / `ÖZEL KANUNLARLA…` | `KENTSEL ÇALIŞMA ALANLARI` / `ORGANİZE SANAYİ BÖLGESİ HİZMET VE DESTEK ALANLARI` |
| 64 | `ELEKTRİKLİ ARAÇ ŞARJ İSTASYONU` | `ALAN KULLANIMLARI` / `KENTSEL ÇALIŞMA ALANLARI` | `ALAN KULLANIMLARI` / `KARAYOLLARI` |
| 160 | `SU ULAŞIM BAĞLANTISI` | `ALAN KULLANIMLARI` / `DENİZYOLLARI` | `ALAN KULLANIMLARI` / `DİĞER SU YOLLARI` |
| 191 | `FAY SAKINIM ZONU/TAMPON ALANI` | `ALAN KULLANIMLARI` / `SU, ATIKSU VE ATIK SİSTEMLERİ` | `ALAN KULLANIMLARI` / `AFET TEHLİKELİ ALANLAR` |
| 192 | `SOKAK HAYVANLARI BARINAĞI ALANI` | `ALAN KULLANIMLARI` / `KARAYOLLARI` | `ALAN KULLANIMLARI` / `SOSYAL ALT YAPI ALANLARI` |

p.61 `ÜNİVERSİTE ALANI`, p.138 `MESİRE ALANI`, p.96 `MAKİLİK- FUNDALIK ALAN` and p.34
`DİĞER ÖZEL KANUNLARLA BELİRLENEN ALAN SINIRLARI` changed for the spelling reason only, so
the two defects account for all 20 changed records.

**Independent confirmation, from two sources apart from the annex's printed blocks.** The
Ministry's code list agrees with three of the corrected pairings outright — `ELEKTRİKLİ ARAÇ
ŞARJ İSTASYONU` and `SOKAK HAYVANLARI BARINAĞI ALANI` under their new upper groups, and
`SNR_IMAR_HAKKI_AKT` under PLANLAMA SINIRLARI. `EK-1e.docx` gives the same *alt sınıfı* the
fix now ships for five of the six re-paired symbols — `KARAYOLLARI` (p.64), `KENTSEL ÇALIŞMA
ALANLARI` as the *sınıfı* of the `ORGANİZE SANAYİ BÖLGESİ HİZMET VE DESTEK ALANLARI` row
(p.23), `DİĞER SU YOLLARI` (p.160), `AFET TEHLİKELİ ALANLAR` (p.191) and `SOSYAL ALT YAPI
ALANLARI` (p.192); its p.64 block even repeats the annex's lone singular `ALAN KULLANIMI`.
The p.23 attribution is the one to sanity-check, because the docx prints that row's title
against two neighbours' blocks: the pair the fix ships sits beside the `ORGANİZE SANAYİ
BÖLGESİ HİZMET VE DESTEK ALANI (HDA)` / `ENDÜSTRİ BÖLGESİ` titles, and the *other* block there
— `SINIRLAR` / `ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLAR` — is the one our own catalogue
gives to the separate p.23 `ENDÜSTRİ BÖLGESİ` symbol, i.e. exactly the pair the old code had
wrongly lent to the HDA row. The sixth cannot be checked: p.19's symbol is in the docx with
**both label cells empty** (which is why it needed `CONTINUATION_HIERARCHY`), and the code
list is the only thing that classifies it.
So that is five of five checkable, and it is the strongest evidence here:
the docx was parsed by a different tool, from a different file format, and had never been
fed to the compiler.

`tools/compile_mpyy_detail_hierarchy.py` repairs each variant (`SPELLING_REPAIRS`), applies
it to the three human-facing label fields only — never to `sld_kurali` or `plan_gml_tipi`,
which `record_for_rule` and the XSD match on — and then **raises** if any two spellings of
one label survive (`_assert_one_spelling_per_label`). So a re-extraction that reintroduces a
spelling fails the build instead of shipping. `tests/test_detail_hierarchy_pure.py` holds
both invariants over the shipped JSON, plus one guard per renamed label: it reports **28
failed, 5 passed, 8 subtests passed** against the recorded baseline
(`~/Downloads/mpyy_detail_hierarchy.BEFORE.json`; every repaired spelling, both label fields,
and all ten pinned symbols named in the output) and **7 passed, 39 subtests passed** now.
Recompiling is byte-reproducible — verified on **raw bytes**, not on decoded text, since
`write_text` emits CRLF here and `read_text` hides it (TRAPS §6.1): a fresh compile and the
shipped file are both 207 496 bytes, sha256 `99e599d81de23365…`. The only fields that moved
are the two label fields, in **113 of 592 records** (109 `detay_alt_sinifi` + 6
`detay_sinifi`; no `sembol_adi` moved), and the provenance block is byte-identical.
`detay_sinifi` carries 4 distinct labels in the baseline and 3 here, `detay_alt_sinifi` 29 in
both: the repairs split one value in two net and the merge put two back into one, so the
vocabulary count returned to where it started while 113 rows changed spelling.

**Both invariants now hold over the two label fields** (`detay_sinifi`, `detay_alt_sinifi`):
no value is a second spelling of another by `label_fold`, and none is one letter away from
another. `sembol_adi` is checked for fold-duplicates only, and deliberately not for one-letter
pairs — it holds 10 of those and every one is legitimate: `MOTEL ALANI`/`OTEL ALANI`,
`ÖÇK BÖLGESİ HASSAS ALAN (A)`/`(B)`/`(C)`, and the `1.`/`2.`/`3.DERECE` arkeolojik and doğal
`SİT ALANI` symbols, which the code list names separately. A one-letter check over
`sembol_adi` would fail on correct data.

Do not commit unless Yusuf explicitly says `commit et`. Do **not** `git add -A` — `scratch/`
and similar paths are untracked but **not** gitignored in this plugin.

---

## 4. The regression that was just fixed (and why nothing caught it)

A mechanical "PlanGML → MPYY" rename (commit `725e1ee`) renamed **both a class name and
the instance attribute holding it**, which silently collapsed **two genuinely different
styling engines** into one name and one attribute slot:

| | before the rename | after |
|---|---|---|
| `dock.py` import | `from .core.plangml_styler import PlanGMLStylerEngine` | `from .core.mpyy_styler import MPYYStylerEngine` |
| | `from .core.styler import MPYYStylerEngine` | same line — **shadows the one above** |
| attributes | `self.plangml_engine` / `self.mpyy_engine` | **both** became `self.mpyy_engine` (2nd assignment wins) |

The two classes were not redundant:

- `core/mpyy_styler.py` — `apply(layer, field, plan_type)` → `MPYYResult(official_styles, fallback_styles)`
- `core/styler.py` — `apply(layer, field_name, plan_level)` → `StyleResult(matched, …)`

Because the second import and the second assignment both won, the detail engine was
**never constructed**, and `gui/actions.py`'s `MPYY_UIP` branch called the surviving class
with the shadowed class's keywords:

```
TypeError: apply() got an unexpected keyword argument 'field'
```

…on **every** use of that branch.

**Why the green gate missed it:** a same-name shadow is not an `ImportError`; no suite
read either engine object; and no suite drove that branch. Green gate, dead feature.

**The fix (committed as `f40ffee`):**

- `core/mpyy_styler.py` — the class is now **`MPYYDetailStylerEngine`** (named after
  `styles/mpyy_detail_catalog.json`), with a docstring explaining it is *not* the same
  engine as `core.styler.MPYYStylerEngine` despite the shared job description.
- `dock.py` — two distinct imports, two distinct attributes: `self.mpyy_detail_engine`
  and `self.mpyy_engine`.
- `gui/actions.py:218-219` — the e-Plan branch now points at the detail engine.

**The guard:** `tests/test_engine_wiring_pure.py` (new, QGIS-free, AST-based, 3 tests).
It asserts (1) no module imports one local name from two sources; (2) the dock binds two
**distinct** engine classes from two **distinct** modules; (3) every
`self.<engine>.<method>(kwargs)` call in `gui/actions.py` matches the **real signature** of
the class the dock binds.

**Proof it bites:** with the fix stashed, the test reports **3/3 FAILED** naming `dock.py`
and `tests/test_forms_dropdowns_qgis.py`; unstashed, **3 passed**. Do not weaken these
assertions — this is the only thing standing between the repo and the same class of
defect.

### It required unblocking mpyy's QGIS-free test path first

`tests/__init__.py` loaded `apps/qt6/bin/Qt6Core.dll` **unconditionally**. With
`OSGEO4W_ROOT` / `QGIS_PREFIX_PATH` unset, `Path("")` collapses to `.`, so importing the
`tests` package raised `FileNotFoundError: Could not find module '…\apps\qt6\bin\Qt6Core.dll'`.
pytest imports that package, so **any** pytest-form `tests_pure` entry died at collection —
which is why mpyy's `tests_pure` was empty and the plugin had **no cheap QGIS-free home for
a regression guard at all**. Now guarded with `if _qt_core.is_file():` (behaviour-identical
wherever the DLL exists, because the OSGeo4W launcher sets the env vars).

Also in the same change set:

- `tests/test_forms_dropdowns_qgis.py` — removed a **dead, shadowed** import of
  `MPYYStylerEngine` (its only usage deliberately exercises `core/styler.py`'s engine).
- `tests/test_gui_qgis.py` — added a runtime counterpart: both engines must be distinct
  instances, and `apply`'s real keyword names are asserted (`field`/`plan_type` present,
  `plan_level` absent on the detail engine).
- `docs/GUI_ARCHITECTURE.md:7` — "iki panel aracı" → "üç panel aracı" (three panel tools,
  verified against `gui/catalog.py`).

### Last verified gate output (exit 0)

```
=== planx_mpyy_studio — verify  [OK] ===
  [PASS] validate_plugin — 0 warnings
  [PASS] Hub gate: security scan (blocking) — CLEAN
  [PASS] Qt6 compatibility (advisory) — no Qt6 errors
  [PASS] pure: pytest (2 files) — 10 passed, 39 subtests passed
  [PASS] qgis[ltr]  — 11 suites, all PASS
  [PASS] qgis[qgis4] — 11 suites, all PASS
VERIFY OK: 1 plugin(s)
```

Re-run this after any further change. `qgis[ltr]` is QGIS 3.44 via
`C:\OSGeo4W\bin\python-qgis-ltr.bat`; `qgis[qgis4]` is QGIS 4.2 via `python-qgis.bat`.

---

## 5. Verified facts about this plugin — trust these, not older notes

- **86 algorithms** = 77 literal `def name()` returns + 9 `ALGORITHM_NAME` constants;
  `provider.py`'s `addAlgorithm` count is also 86. Older documents saying **83 are wrong**.
- **7 categories**: Çalışma alanı ve veri 10, Parsel tasarımı 8, Kentsel analiz 10,
  Ulaşım ve erişim 6, Plan denetimleri 17, Plan dosyası ve dayanaklar 20, Raporlar ve
  teslim 15.
- **3 panel tools** (not Processing algorithms): `create_workspace`, `style_and_forms`,
  `database_report`.
- **131 TTF** in `resources/fonts` across 27 families; `styles/provenance.json` records
  only 4 families.
- **Reference manual + portal page exist and are LIVE**:
  `https://geophilo.com/planx_mpyy_studio/`. Both are generated by
  `tools/generate_reference_manual.py`, which parses the catalogue out of `gui/catalog.py`
  and **fails loudly** if `provider.py` registers an algorithm with no catalogue row — so
  the manual cannot silently drift. Regenerate it after any algorithm change.
- Every stale predecessor document was **deleted** on 2026-09-20:
  `MASTER_AGENT_SPECIFICATION.md`, `NEXT_AGENT_MASTER_DIRECTIVE.md` (both 2.5.2 era,
  claiming 83 algorithms and two dock utilities) and `docs/DEVELOPMENT_HISTORY.md`
  ("through 2.5.1", same wrong count). **This file is the only handoff that exists** — if
  you find any of those three cited anywhere, the citation is dead. If this file ever
  stops being accurate, rewrite it rather than adding a second one.

---

## 6. Open items and owner decisions

### Owner decisions recorded on 2026-09-20

1. **Do not work on legal/provenance questions for now.** Yusuf stated that he created
   the styles and explicitly directed agents to leave the legal topic alone at this stage.
   Preserve the existing provenance and notice files unless he asks for a change; legal
   review is not part of the current engineering backlog.
2. **Font portability, not typeface identity, is the requirement.** Arial or any other
   readable sans-serif is acceptable, but the plugin must not depend on fonts installed on
   Yusuf's workstation. The implementation registers bundled notation fonts in the QGIS
   process and substitutes unavailable ordinary text families with bundled DejaVu Sans.
   The automated payload/registration tests are the acceptance guard; the former manual
   "uninstall system fonts and prove this exact desktop" step is not a release blocker.
3. **Whether an English manual is wanted.**

### Resolved 2026-09-21 — the plural/singular label pair, merged on Yusuf's instruction

The catalogue shipped two forms of one classification. This pass first left them **unmerged**,
because the difference is the plural morpheme (`ALANLARI`/`ALANI`) and not a dropped *letter* —
folding erases the dotted İ, so the two are three characters apart once folded — and because
**no symbol carried both**:

| label | `detay_alt_sinifi` rows | symbols |
| --- | --- | --- |
| `SOSYAL VE KÜLTÜREL TESIS ALANLARI` (plural) | 14 | 12 |
| `SOSYAL VE KÜLTÜREL TESİS ALANI` (singular, dotted İ) | 2 | **1** — `SEMT SPOR ALANI` |

Yusuf's decision was **merge**, into the singular, and the direction is not a coin toss: the
plural occurs **zero** times in the plugin's own code list (`styles/mpyy_detail_catalog.json`),
while the singular is `ust_grup_adi` on 15 of its 274 rows and is also what the plugin already
reads elsewhere — 15 times in `core/mpyy_catalog.py`, 10 in `forms/yerel_nip/lookups.json`, once
in `core/crosswalk.py`. So the plural was the outlier, and merging aligns the catalogue with the
rest of the plugin instead of renaming a classification the code list endorses. The two official
sources still disagree — `EK-1e.docx` prints the plural 12 times against the singular once
(re-measured 2026-09-21), the opposite majority — so this was settled on the code-list tier, the
same tier that decided ten of the twelve spelling repairs. The annex's third, run-together
variant (`SOSYALVE KÜLTÜREL TESIS ALANLARI`, 1 row) was repaired into the plural form first,
because that one differs by a word split rather than by a plural; it reaches the singular with
the rest.

Effect: 14 rows renamed (pages 123–129), `detay_alt_sinifi` 30 → 29 distinct values, 16 rows on
the singular. Guarded by `SPELLING_REPAIRS`, `REPAIRED` and
`test_the_plural_class_merged_into_the_singular`; measured by putting the 16 rows back on the
plural, which is what a recompile without that entry produces — `tests/test_detail_hierarchy_pure.py`
then reports **3 failed, 6 passed, 37 subtests passed** and the other file stays green.

Measured across both label fields: **no two distinct labels in a field share a symbol** — so
every symbol maps to exactly one classification.

### Resolved 2026-09-21 — five labels that shipped undotted, 79 rows

Measuring the merge turned up a wider set, left as an open question for one pass and then
repaired on Yusuf's instruction the same day. These values shipped the annex's own undotted İ
where the Ministry's code list dots it:

| shipped value | code-list spelling | rows | what `EK-1e.docx` prints (exact substring count) |
| --- | --- | --- | --- |
| `DEMIRYOLLARI` | `DEMİRYOLLARI` | 11 | both — 5 undotted against 1 dotted |
| `ENERJI ÜRETIM, DAĞITIM VE DEPOLAMA` | `ENERJI ÜRETİM DAĞITIM VE DEPOLAMA` | 34 | the undotted, **comma'd** form only, 19 times; the comma-less spelling the code list uses appears 0 times |
| `İDARI SINIRLAR` | `İDARİ SINIRLAR` | 18 | the undotted form only, 7 times |
| `SAĞLIK TESISLERI ALANLARI` | `SAĞLIK TESİSLERİ ALANI` | 5 | the undotted plural only, 5 times |
| `EĞITIM TESISLERI ALANLARI` | `EĞİTİM TESİSLERİ ALANI` | 11 | the undotted plural only, 9 times |

"Only for `DEMİRYOLLARI` does the reproduction print the spelling that was kept" is also the
answer to why the passes before this one did not see them: four the annex never prints in the
kept form at all, and the fifth only once. The `SAĞLIK TESİSİ ALANI` / `ÖZEL SAĞLIK TESİSİ
ALANI` cells the docx also carries are its own catalog symbols, not variants of this group name,
so they are not counted here.

None of the five was a duplicate **inside** the catalogue: each shipped in exactly one form, so
no layer metadata read `A | B`, no two values folded together, and neither invariant in
`tests/test_detail_hierarchy_pure.py` fired. That is why the duplicate hunt this entry is about
could not reach them and a label-versus-code-list pass was needed instead. `İDARI SINIRLAR` is
the pure İ case, and no singular form of it arises; the last two are the plural/singular shape
one group over, so repairing them was also a merge.

The repair took the code-list tier for all five, and it is worth reading what that did **not**
change: the ENERJI group name the code list carries is itself undotted in `ENERJI` while dotting
`ÜRETİM`, and it has no comma — so the shipped label is `ENERJI ÜRETİM DAĞITIM VE DEPOLAMA`, one
comma shorter than the annex and no better accented than the annex in its first word. The
plugin's own files agree with the code list, not with the annex: `core/mpyy_catalog.py` carries
`ENERJI ÜRETİM DAĞITIM VE DEPOLAMA` 18 times, and `SAĞLIK TESİSLERİ ALANI` / `EĞİTİM TESİSLERİ
ALANI` in the singular that `core/crosswalk.py` also uses. That is the same evidence that
settled the SOSYAL merge, applied to five more labels.

Effect: **79 rows renamed in place** (pages 12–15, 116–123, 157–159, 173–182), `detay_alt_sinifi`
still 29 distinct values because none of the five merged into an existing label. Guarded by
`SPELLING_REPAIRS`, `REPAIRED`, `UNDOTTED_REPAIRED` and
`test_the_undotted_labels_ship_the_code_list_spelling`, which pins each label's row count;
restoring the pre-repair catalogue makes `tests/test_detail_hierarchy_pure.py` report **11
failed, 6 passed** while the shipped catalogue gives **7 passed, 39 subtests passed**.

### Completed follow-up audits (not backlog)

4. **The old “28 SLD-only borders” item was a classification error, not an unfinished
   style set.** A fresh runtime inventory found 35 polygon rules with top-level line/marker
   layers outside the catalogue boundary geometry generator. Seven are clearly road/fill
   graphics; the remaining 28 mix catalogue symbols, hatches, protected-area borders and
   raw Ministry SLD constructs. The Ek-1e comparison workbook marks all 617 schema-backed
   catalogue rows complete (the other eight have no PlanGML 1.1.7 counterpart), while the
   catalogue decision table's 235 concrete boundary targets all pass their runtime audit.
   Do not bulk-scale or restyle the residual group: it is not a list of 28 missing borders,
   and Yusuf explicitly owns the style decisions.
5. **The old “5 drawable symbols never appear” item is stale.** The current Konak control
   project contains 252 layers and 795 features. After reapplying the current styles, all
   **785 non-else drawable rules** match at least one feature; unmatched count is zero.
6. **The sibling-plugin large-extent download warning does not apply.** This plugin has no
   as-is/Overpass data-download workflow. Its only remote-looking features are user-triggered
   web actions and an optional OSM XYZ base map in a local QField package.

There is no known technical release blocker after the complete verification matrix. Two owner
choices are open: whether an English manual is wanted, and the plural/singular label pair
above. Legal/provenance work remains explicitly deferred by Yusuf.

---

## 7. Traps that will bite you on this plugin

1. **A `tests_pure` entry is a PATH, and its basename decides how it runs.** In
   `packaging/pf.py`, a basename starting with `test_` runs under **pytest**
   (`-o pythonpath=.. -q -p no:cacheprovider`, cwd = plugin dir); anything else runs as a
   **script**. The `-m module.path` form is valid in `tests_qgis` but **invalid** in
   `tests_pure` — its basename starts with `-`, so Python tries to *open* `-m …` as a file.
2. **A pytest *collection* error naming a Qt DLL is not a broken test** — it is a
   `tests/__init__.py` that assumes a QGIS runtime. That exact trap had mpyy's pure-test
   path dead. The guard is in place now; keep it.
3. **`packaging/zip_hub.py` will NOT exclude a named `.md` at the plugin root.**
   `DEV_DOC_GLOBS` only matches `ENHANCEMENT_PLAN_*`, `DEEPSEEK_PROMPT_*` and `REPORT_v*`,
   despite its own comment saying agent work-orders must never ship. The only thing that
   drops a file like this one is the plugin's own **`.zipignore`**. Always:
   - add the filename to `.zipignore`, **and**
   - grep the plugin for references to it first — an excluded file with a live link from
     `README.md` leaves a dead link for a Hub user.
   - To answer "does X ship?", **mirror `build_zip`'s walk**, never re-derive it from the
     glob list: `_should_skip()` tests the *file* basename, but `build_zip` **also prunes
     directories**, which is what keeps `.git` out. A file-only inventory inflates the count.
4. **Never `git add -A`** in this plugin — untracked-but-not-ignored paths exist
   (`scratch/`, QGIS profile dirs). Stage explicit paths.
5. **No literal `%` in `metadata.txt`** — it breaks the Hub upload via configparser
   interpolation.
6. **In `postProcessAlgorithm`, always `context.getMapLayer(id)`**, never
   `QgsProject.instance().mapLayer(id)` — the latter silently no-ops **all** styling and
   metadata. Assert the renderer class and the field alias in tests, not just the feature
   count. (A sibling plugin shipped 22 tools with zero symbology this way for several
   releases before a user caught it in real QGIS.)
7. **`QgsField(name, int)` is a hard `TypeError` on QGIS 4** — unlike the cosmetic
   `QVariant.*` advisory. `hub_qt6_scan.py` cannot see it; grep for it.
8. **Headless font metrics ≠ real render.** A `QFontMetrics`-vs-rect check passing under
   `QT_QPA_PLATFORM=offscreen` does not guarantee it fits on a real desktop.
9. **`tests/test_mpyy_levels_qgis.py` had a native-crash flake** (a wrapper into a destroyed
   renderer tree kept alive in the caller's frame). It is fixed — leave the assertions in
   the helper where they are. Do not re-open the SIP-ownership lead; it was measured and
   ruled out.
10. **The workspace root is not a git repo**, so changes to `plugins.toml`,
    `packaging/pf.py` and `docs/TRAPS.md` are uncommittable by design. That is expected,
    not drift.

---

## 8. Suggested first moves

1. Read `AGENTS.md`, `docs/TRAPS.md` and the `planx_mpyy_studio` entry in `plugins.toml`.
2. `git status` in the plugin dir; reconcile §3 with Yusuf **before** writing anything.
3. Re-run `py -3 packaging/pf.py verify planx_mpyy_studio` and confirm `VERIFY OK`.
4. Read `tests/test_engine_wiring_pure.py` and understand why it exists — then never
   weaken it.
5. Do not reopen the deferred legal/provenance topic or restyle Yusuf's source styles unless
   he explicitly asks for it.
6. Commit only under **Yusuf Eminoğlu's** name, with no trailer of any kind.
