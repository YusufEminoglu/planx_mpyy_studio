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
| Last commit | `12bc49e` "Referans el kitabi ve portal sayfasi eklendi" |
| Latest gate result | **`VERIFY OK`**, both runtimes, 11 QGIS suites each, 3/3 pure |

**Do not read "1.0.0" as "released".** It is a *working* version number. The 2.x numbering
was deliberately voided and the tree reset to 1.0.0 for a first public release that has
not happened yet.

### STANDING ORDER (from Yusuf, 2026-09-20) — stay on 1.0.0

> "mpyy eklentisi tamamen bitene kadar tüm gelişmeler V1.0 olarak kalmaya devam edecek."

Every further change keeps the version at **1.0.0**: do **not** bump `metadata.txt`, do
**not** cut a tag, do **not** add a new `CHANGELOG.md` section. **Ask before any bump.**

---

## 3. ⚠️ Uncommitted work — read this before you touch anything

The tree is **dirty**. A regression fix was completed and fully verified but
**deliberately not committed** (Yusuf's pattern is to say "commit et" explicitly; he had
not as of this writing).

```
 M core/mpyy_styler.py
 M dock.py
 M docs/GUI_ARCHITECTURE.md
 M gui/actions.py
 M tests/__init__.py
 M tests/test_forms_dropdowns_qgis.py
 M tests/test_gui_qgis.py
?? tests/test_engine_wiring_pure.py
```

Plus, in the **workspace root** (not a git repo, so it never shows in any `git status`):

- `plugins.toml` line 35 — `tests_pure` was `[]`, now
  `["tests/test_engine_wiring_pure.py"]`.

**Decide with Yusuf what to do with this before starting new work.** Options: commit it as
one focused commit, or verify it again from scratch. Do **not** `git add -A` — `scratch/`
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

**The fix (in the uncommitted diff):**

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
  [PASS] pure: pytest (1 files) — 3 passed
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

## 6. Open items — and which ones are NOT yours to close

### Not an agent's to decide (escalate to Yusuf)

1. **`styles/provenance.json` says `distribution_status = "unverified; local development
   only until source redistribution rights are established"`** — the same unresolved
   status applies to the Ministry's source XML and to the bundled fonts. This is a
   **publication blocker** for a first public release, and it is a rights decision, not a
   code change. **Do not write anywhere that public distribution is approved.** Fixing
   `THIRD_PARTY_NOTICES.md` wording to *match* reality is fine; inventing a right is not.
2. **The real-desktop font proof.** With system fonts uninstalled
   (`install_mpyy_fonts.ps1 -Uninstall`), restart QGIS and open
   `Downloads\PlanGML_Sembol_Kontrol_Grid\konak_sembol_kontrol.qgz`. No
   `Font "…" not available on system` warning may appear, and symbols must draw correctly.
   A headless `QT_QPA_PLATFORM=offscreen` metrics check **does not substitute** for this.
   If it fails, **shorten the text** rather than re-tuning dimensions.
3. **Whether an English manual is wanted.**

### Genuine engineering backlog

4. **Symbol and line sizes must look right for every user.** The Ministry's SLD sizes carry
   no consistent scale (measured ratio to catalogue millimetres: **1.07–5.65**). The agreed
   direction is to make the catalogue's paper millimetres the sizing authority, converted
   as `ground m = mm × scale / 1000`. A border audit against the catalogue found
   **218 conforming, 45 problematic** (28 unit mismatches, 14 missing borders, 3 missing
   dash patterns).
5. **5 drawable symbols can never appear with the test data** — 4 are `symbolizer = ''`
   rules against a **NULL** GPKG column (`NULL = ''` is false in QGIS; it is the Ministry's
   own SLD, and our `mapping.json` records `literal: null`), and the 5th is
   `UIP · YayaYolu` requiring `"Genislik" > 0`. Separately, 240 layers carry the
   "no official representation" **ELSE** fallback, and the generated style emits some rules
   **twice** (e.g. `AskeriBolgeTip = 'X' OR AskeriBolgeTip = 'X'`).
6. **Large-extent warning** before an as-is download (carried over from a sibling plugin's
   backlog — check whether it applies here before acting).

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
5. Ask Yusuf which of §6 he wants next. Item 1 (distribution rights) blocks publication
   and is his call; item 4 (symbol sizing) is the largest real engineering task.
6. Commit only under **Yusuf Eminoğlu's** name, with no trailer of any kind.
