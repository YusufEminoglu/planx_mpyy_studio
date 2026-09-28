"""Compile the Ek-1e detail-class hierarchy for MPYY polygon and line rules.

The generated JSON deliberately keeps the PlanGML type and original SLD rule
identifier alongside the human-facing catalog symbol name.  This lets a QGIS
workspace expose the requested ``sembol adı → detay sınıfı → detay alt sınıfı``
relationship without changing the XSD's legal code lists.

Every record also carries a ``kaynak`` entry, outside ``records``, holding the
two source cells it was read from and the named kind of reading that supplied
them -- so a shipped classification can be traced to the printed block it came
from instead of to the page it shares with forty others.  The transform tables
themselves ship alongside it, under ``duzeltmeler``, which is what makes the
whole file re-derivable from its own evidence.

Usage::

    py -3 tools/compile_mpyy_detail_hierarchy.py <Ek-1e.pdf> <comparison.xlsx>
    py -3 tools/compile_mpyy_detail_hierarchy.py --diff
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from planx_mpyy_studio.core.localization import label_fold  # noqa: E402

OUTPUT = ROOT / "styles" / "mpyy_detail_hierarchy.json"
SHEET = "Karşılaştırma"

#: The catalog-item cell of three p.12 rows carries the whole section heading
#: glued to the front of the symbol name.  It is not part of the label, so it is
#: cut off before matching -- and the record's ``kaynak`` keeps the cell verbatim,
#: which is what lets a reader see that the cut happened at all.
TITLE_PREFIX = "DETAY KATALOĞU"

# These p.18/p.19 entries are printed in the same continuation block as the
# immediately preceding planlama sınırları items, without repeating headers.
#
# All six reach this table the same way: the page *does* print the title, but no
# DETAY SINIFI / DETAY ALT SINIFI block could be paired to it, so the page
# contributed nothing to the classification and this table stands in.  A record
# that takes its pair from here says so in its own ``kaynak`` entry
# (``"hiyerarsi_kaynak": "devam_tablosu"``) and carries empty ``baski_*`` cells,
# because "the annex never printed this" and "the annex printed this" must not
# look alike in the shipped file.
CONTINUATION_HIERARCHY = {
    "MEVCUT PLANDAKİ DURUMU KORUNACAK ALAN SINIRI": ("SINIRLAR", "PLANLAMA SINIRLARI"),
    "YENİDEN DÜZENLENECEK ALAN SINIRI": ("SINIRLAR", "PLANLAMA SINIRLARI"),
    "SAĞLIKLAŞTIRMA ALANI SINIRI": ("SINIRLAR", "PLANLAMA SINIRLARI"),
    "KIRSAL YERLEŞİK ALAN SINIRI": ("SINIRLAR", "PLANLAMA SINIRLARI"),
    # p.19 prints this one with both label cells left blank, and EK-1e.docx
    # leaves its table cell empty as well, so the page itself says nothing.  The
    # Ministry's machine readable code list does: the symbol is layer
    # SNR_IMAR_HAKKI_AKT, and `ust_grup_adi` in styles/mpyy_detail_catalog.json
    # files it under PLANLAMA SINIRLARI -- the same upper group every other
    # *_SINIRI continuation on those pages carries.
    "İMAR HAKKI AKTARIM ALANI SINIRI": ("SINIRLAR", "PLANLAMA SINIRLARI"),
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


# Ek-1e prints one catalogue label more than one way and the compiled catalogue
# must not ship two: `apply_renderer_hierarchy` joins a type's distinct
# subclasses into `mpyy/detay_alt_sinifi` with a pipe, so a label stored twice
# reads as two classifications and each rule description then picks one of them
# at random.
#
# Fourteen pairs, and the kept spelling is the value on the right.  Ten of them
# lose the Turkish dotted İ, two run two words together that the kept spelling
# separates (one of those also loses the İ), one drops an L out of KULLANIMLARI,
# one drops the plural -LARI, one carries a trailing -I, and one drops a comma
# the annex prints.  Three go further and file one concept under the annex's
# plural where the code list names a singular -- the SOSYAL VE KÜLTÜREL pair,
# merged on Yusuf's instruction (2026-09-21), and the SAĞLIK and EĞİTİM TESİSLERİ
# rows, repaired on the same rule.  That is why this table is not only about
# spelling: merging changes what 16 rows read, not just how a word is accented.
#
# The rule for the kept spelling is two-tier, and no entry below should be read
# as "what the code list says": ten of the twelve distinct targets are
# `ust_grup_adi` values in the Ministry's own machine readable list
# (styles/mpyy_detail_catalog.json, 25 group names, 24 of which core/mpyy_catalog.py
# repeats and which core/crosswalk.py and forms/yerel_nip/lookups.json follow as
# well), so the code list settles those.  It does not settle the other two:
# `YERLEŞİM ALANLARI` appears in it only inside the longer group name `KONUT
# ALANLARI / YERLEŞİM ALANLARI`, and `ALAN KULLANIMLARI` is a DETAY SINIFI value,
# not an upper group, that wins on 509 rows against exactly 2 for each defective
# spelling.  Where the code list has an opinion it also outranks the annex:
# `EK-1e.docx` prints `DENIZYOLLARI` undotted in 18 cells against 2 dotted, i.e.
# its own majority is the form that was *not* kept, and the ENERJI group name is
# kept as the code list writes it -- dotting ÜRETİM, leaving ENERJI undotted, and
# without the comma the annex prints.
#
# The pair most easily mistaken for dead code is `ALAN KULLANIMI`: it is printed
# in exactly one DETAY SINIFI cell in the whole annex (p.64, against 302 of the
# plural), and it reaches a shipped row only because the block pairing below now
# finds that symbol's *own* block -- the p.64 cell belongs to `ELEKTRİKLİ ARAÇ
# ŞARJ İSTASYONU`.  Remove this one entry and those two rows (UIP and NIP) ship
# `ALAN KULLANIMI` while 507 others ship the plural, a duplicate that
# `_assert_one_spelling_per_label` cannot see because the two spellings fold to
# different keys; the one-letter check in tests/test_detail_hierarchy_pure.py is
# what catches that class.  Its sibling `ALAN KULANIMLARI` is not dead weight
# either: it prints in one cell too (p.96, `... MAKİLİK-FUNDALIK ALAN`) and
# carries its own 2 rows.
#
# Neither does `EK-1e.docx` settle any of this: it prints both variants for all
# fourteen.  A pair the merge makes invisible to both guards -- a plural and its
# singular are neither fold-equal nor one letter apart -- is held by this table
# plus the REPAIRED checks in tests/test_detail_hierarchy_pure.py; once merged it
# is a single fold key, so `_assert_one_spelling_per_label` guards it from then
# on.
#
# A duplicate hunt only finds the labels the extractor caught twice, and five
# labels shipped undotted for a while because of it (DEMIRYOLLARI, ENERJI ÜRETIM,
# ..., İDARI SINIRLAR, SAĞLIK TESISLERI ALANLARI, EĞITIM TESISLERI ALANLARI; 79
# rows): each was extracted in one form only, so nothing folded together and no
# guard could see it.  They were found by a label-versus-code-list pass and
# repaired on the same tier on 2026-09-21 -- the check to repeat after any
# re-extraction.
#
# Either way exactly one spelling ships, so the duplicate cannot reach the layer
# metadata or the rule descriptions.
SPELLING_REPAIRS = {
    "DENIZYOLLARI": "DENİZYOLLARI",
    "AÇIK VE YEŞIL ALANLAR": "AÇIK VE YEŞİL ALANLAR",
    "YERLEŞIM ALANLARI": "YERLEŞİM ALANLARI",
    "SOSYALVE KÜLTÜREL TESIS ALANLARI": "SOSYAL VE KÜLTÜREL TESİS ALANI",
    "ALAN KULLANIMI": "ALAN KULLANIMLARI",
    "ALAN KULANIMLARI": "ALAN KULLANIMLARI",
    "SOSYAL ALTYAPI ALANLARI": "SOSYAL ALT YAPI ALANLARI",
    "ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLARI": "ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLAR",
    "DEMIRYOLLARI": "DEMİRYOLLARI",
    "ENERJI ÜRETIM, DAĞITIM VE DEPOLAMA": "ENERJI ÜRETİM DAĞITIM VE DEPOLAMA",
    "İDARI SINIRLAR": "İDARİ SINIRLAR",
    "SOSYAL VE KÜLTÜREL TESIS ALANLARI": "SOSYAL VE KÜLTÜREL TESİS ALANI",
    "SAĞLIK TESISLERI ALANLARI": "SAĞLIK TESİSLERİ ALANI",
    "EĞITIM TESISLERI ALANLARI": "EĞİTİM TESİSLERİ ALANI",
}
SPELLING_KEYS = {label_fold(source): target for source, target in SPELLING_REPAIRS.items()}


def _canonical(value: object) -> str:
    """One spelling per label: repair the variant Ek-1e prints for a label it also prints correctly."""
    return SPELLING_KEYS.get(label_fold(value), _clean(value))


def _assert_one_spelling_per_label(records: list[dict]) -> None:
    """Two spellings of one label is a defect, not a detail.

    `apply_renderer_hierarchy` joins the distinct subclasses of a feature type
    into `mpyy/detay_alt_sinifi`, so a label stored twice reads as two
    classifications joined by a pipe -- and every rule description picks one of
    them at random.  A repair that misses a variant must fail here rather than
    ship, which is also what stops a new PDF re-extraction from reintroducing a
    spelling nobody chose.
    """
    for field in ("sembol_adi", "detay_sinifi", "detay_alt_sinifi"):
        spellings: dict[str, set[str]] = {}
        for record in records:
            spellings.setdefault(label_fold(record[field]), set()).add(record[field])
        ambiguous = {key: sorted(values) for key, values in spellings.items() if len(values) > 1}
        if ambiguous:
            raise RuntimeError(f"Aynı etiketin birden çok yazımı var ({field}): {ambiguous}")


def _turkish(value: str) -> str:
    """Repair the fragments of Turkish the PDF's text layer gets wrong.

    A substring rewrite, not a label lookup: it fires inside a longer label.

    Three of the four are pure accents the Ministry's typesetting dropped.  The
    fourth is not: the annex prints this one label two ways, `SU, ATIKSU` on
    p.185 and `SU-ATIKSU` on p.183, and its own `EK-1e.docx` prints the comma'd
    form fourteen times against the hyphen once -- so the hyphen is the annex
    disagreeing with itself, and the majority spelling is the one kept.  The two
    documents are renderings of one Ministry source, so that count is not a
    second opinion; it is the same document being more consistent in one
    rendering than the other.

    The fix belongs to the *reading*, not to the annex: a re-extraction that
    produced all four correctly would leave this table nothing to do, which is
    why the shipped file records each record's pre-repair reading beside the rule
    that changed it.
    """

    for old, new in TURKISH_REPAIRS.items():
        value = value.replace(old, new)
    return value


#: The three fragments of Turkish the PDF's text layer gets wrong, and the repair.
#:
#: Three, not four: a `"SIT VE": "SİT VE"` entry stood here until the readings
#: were recorded and the table could be checked against itself.  It could never
#: have fired -- every string containing `SIT VE` contains `SIT `, which the rule
#: above rewrites first, so by the time the table reached it there was nothing
#: left to match.  A rule that cannot fire is worse than a missing one: it reads
#: as though the case is handled.  `test_no_declared_rule_can_never_fire` holds
#: that shut for the rules that remain.
TURKISH_REPAIRS = {
    "TURIZM": "TURİZM",
    "SIT ": "SİT ",
    "SU-ATIKSU": "SU, ATIKSU",
}


@dataclass(frozen=True)
class Hierarchy:
    """One symbol's detail class, and the reading it was read from.

    ``detay_sinifi`` and ``detay_alt_sinifi`` are the shipped pair, after both
    repair tables have run.  ``baski_detay_sinifi``/``baski_detay_alt_sinifi``
    are the same two cells as the page's own text layer spells them, before any
    repair, and are empty when no printed page supplied them at all -- so a
    reader can always tell a page reading from a table lookup, and can apply the
    declared rules to the raw text and arrive back at the shipped value.
    """

    detay_sinifi: str
    detay_alt_sinifi: str
    #: ``"sayfa"`` when the pair came off the printed page, ``"devam_tablosu"``
    #: when ``CONTINUATION_HIERARCHY`` stood in because no block could be paired.
    kaynak: str
    baski_detay_sinifi: str = ""
    baski_detay_alt_sinifi: str = ""


def _from_page(detail: str, sub: str) -> Hierarchy:
    return Hierarchy(
        _turkish(detail), _turkish(sub), "sayfa", detail, sub
    )


def _from_continuation(title: str) -> Hierarchy | None:
    """The table's pair for ``title``, as a reading with no printed cells behind it."""

    pair = CONTINUATION_HIERARCHY.get(title)
    if pair is None:
        return None
    return Hierarchy(pair[0], pair[1], "devam_tablosu")


# A page prints a full-width stack of [title][DETAY SINIFI / DETAY ALT SINIFI
# block][GÖSTERİM] rows.  Titles are set at 12 pt or more, every table cell at 9
# to 10 pt, so font size alone tells the two apart.
TITLE_MIN_SIZE = 11.0
LINE_Y_TOLERANCE = 3.0

BLOCK = re.compile(
    r"DETAY\s+SINIFI\s+(?P<detail>.*?)\s+DETAY\s+ALT\s+SINIFI\s+(?P<sub>.*?)\s+GÖSTERİM",
    re.IGNORECASE,
)


def _read_page(page) -> tuple[str, list[float], list[dict]]:
    """A page's cleaned text, the printed y of each of its characters, and its lines.

    The text is `_clean(page.extract_text())` character for character, because
    the shipped values must not drift, but it is rebuilt from the per-chunk
    visitor so that every character keeps the y it was printed at.
    """
    chunks = []

    def visit(text, cm, tm, font, size):
        if text:
            chunks.append((text, round(tm[4], 1), round(tm[5], 1), float(size or 0)))

    page.extract_text(visitor_text=visit)
    characters: list[str] = []
    positions: list[float] = []
    for value, _, y, _ in chunks:
        for character in value:
            if character.isspace():
                # The same run-collapse `_clean` does, one character at a time.
                if characters and characters[-1] != " ":
                    characters.append(" ")
                    positions.append(y)
            else:
                characters.append(character)
                positions.append(y)
    while characters and characters[0] == " ":
        characters.pop(0)
        positions.pop(0)
    while characters and characters[-1] == " ":
        characters.pop()
        positions.pop()

    lines = []
    for value, x, y, size in sorted(chunks, key=lambda chunk: (-chunk[2], chunk[1])):
        if not value.strip():
            continue
        if not lines or abs(lines[-1]["y"] - y) > LINE_Y_TOLERANCE:
            lines.append({"y": y, "size": 0.0, "parts": []})
        lines[-1]["parts"].append((x, value))
        lines[-1]["size"] = max(lines[-1]["size"], size)
    for line in lines:
        line["parts"].sort()
        line["text"] = _clean(" ".join(part[1] for part in line["parts"]))
    return "".join(characters), positions, lines


def _title_lines(lines: list[dict], title: str) -> list[int] | None:
    """The printed line(s) spelling ``title``, or None when the page does not show it.

    Most labels print on one 12 pt line; the ones carrying a density range wrap
    onto a second, so a title is one line or two consecutive ones.
    """
    wanted = label_fold(title)
    for index, line in enumerate(lines):
        if line["size"] >= TITLE_MIN_SIZE and label_fold(line["text"]) == wanted:
            return [index]
    for index, line in enumerate(lines):
        if line["size"] < TITLE_MIN_SIZE:
            continue
        window = label_fold(line["text"])
        for step in range(1, 3):
            if index + step >= len(lines):
                break
            window += label_fold(lines[index + step]["text"])
            if window == wanted:
                return list(range(index, index + step + 1))
    return None


def _page_hierarchy(page_data: tuple[str, list[float], list[dict]], title: str) -> Hierarchy | None:
    """Find the detail class block belonging to ``title`` on one printed page.

    The plain extraction does not always hand a page's blocks over in printed
    order -- on some pages it emits every title first and then the blocks -- so
    pairing a block with "the text printed before it" hands the wrong class to
    the title.  Blocks are paired by printed position instead: the one directly
    below the title, with no other title printed in between.

    Returns ``None`` only when neither the page nor the continuation table has
    anything for ``title``; the reading says which of the two it was.
    """
    text, positions, lines = page_data
    title_at = _title_lines(lines, title)
    if title_at is None:
        return _from_continuation(title)
    # Some titles wrap, so the anchor is the bottom line of the printed title.
    anchor = min(lines[index]["y"] for index in title_at)
    own = {lines[index]["y"] for index in title_at}
    others = [line["y"] for line in lines
              if line["size"] >= TITLE_MIN_SIZE
              and label_fold(line["text"]) != "DETAYKATALOGU"
              and line["y"] not in own]
    next_below = max((y for y in others if y < anchor - 1), default=None)

    blocks = []
    for match in BLOCK.finditer(text):
        detail = _clean(match.group("detail"))
        sub = _clean(match.group("sub"))
        if not detail or not sub:
            continue
        start = positions[match.start()]
        if start >= anchor - 1:
            continue
        # A DETAY SINIFI cell the Ministry left empty makes the lazy regex run on
        # into the following block and swallow the rest of the page; such a match
        # ends below the next printed title and cannot belong to this one.
        if next_below is not None and positions[match.end() - 1] < next_below:
            continue
        if any(start < y < anchor for y in others):
            continue
        blocks.append((start, detail, sub))
    if not blocks:
        return _from_continuation(title)
    _, detail, sub = max(blocks, key=lambda block: block[0])
    return _from_page(detail, sub)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_labels_derive_from_source(records: list[dict], kaynak: dict) -> None:
    """Every shipped label has to follow from that record's own recorded reading.

    This is what makes ``kaynak`` evidence rather than commentary: take one
    record's raw cells, apply the two tables this file declares, and the labels
    it ships have to come back.  A value with nothing behind it -- the failure
    the MSP reconciliation found 67 of, in a catalogue that looked complete --
    fails here at compile time instead of shipping.

    The two pipelines are mirrored exactly, including the one place they differ:
    a page reading goes through ``_turkish`` before ``_canonical``, a
    ``CONTINUATION_HIERARCHY`` pair is hand-written and carries no extraction
    artifact, so it goes through ``_canonical`` alone.
    """

    for record in records:
        known = kaynak[record["id"]]
        if known["hiyerarsi_kaynak"] == "sayfa":
            expected = [
                _canonical(_turkish(known["baski_detay_sinifi"])),
                _canonical(_turkish(known["baski_detay_alt_sinifi"])),
            ]
        else:
            pair = CONTINUATION_HIERARCHY.get(known["baslik"])
            if pair is None:
                raise RuntimeError(
                    f"{record['id']}: baski_* boş ama {known['baslik']!r} "
                    "devam tablosunda yok"
                )
            expected = [_canonical(pair[0]), _canonical(pair[1])]
        for field, value in zip(("detay_sinifi", "detay_alt_sinifi"), expected):
            if record[field] != value:
                raise RuntimeError(
                    f"{record['id']}.{field} kaynaktan türetilemiyor: "
                    f"{record[field]!r} ≠ {value!r}"
                )
        if record["sembol_adi"] != _canonical(known["baslik"]):
            raise RuntimeError(
                f"{record['id']}.sembol_adi kaynaktan türetilemiyor: "
                f"{record['sembol_adi']!r} ≠ {_canonical(known['baslik'])!r}"
            )


def _identity(record: dict) -> str:
    """The key two compilations of this file are matched on, whatever their version.

    The sort tuple, not ``id``: it is unique across all 592 records -- the
    property that let ``id`` be introduced at all -- and unlike ``id`` it exists
    in a version-1 file too, so a diff can pair the two.  ``id`` names a record
    in the report; it is never what the two sides are joined on.
    """

    return "|".join(record.get(key, "") for key in (
        "plan_kademesi", "detay_sinifi", "detay_alt_sinifi",
        "sembol_adi", "plan_gml_tipi", "sld_kurali",
    ))


def _diff(compiled: dict, committed: dict) -> list[str]:
    """Every place the committed file and a fresh read of the sources disagree.

    Records first, by identity, then the evidence beside them, then the declared
    tables -- a rule table that moved is a difference even when no record's value
    did, which is exactly the shape a single line count cannot show.  A file that
    predates the ``kaynak`` map is reported as missing it once rather than once
    per record.
    """

    findings = []
    for key in ("version", "duzeltmeler", "devam_tablosu"):
        if committed.get(key) != compiled[key]:
            findings.append(
                f"{key}: katalogda {committed.get(key)!r}, Ek-1e'de {compiled[key]!r}"
            )
    old = {_identity(record): record for record in committed.get("records", [])}
    for record in compiled["records"]:
        previous = old.get(_identity(record))
        if previous is None:
            findings.append(f"{record['id']}: committed katalogda yok")
            continue
        for key, value in record.items():
            if key == "id":
                continue
            if previous.get(key) != value:
                findings.append(
                    f"{record['id']}.{key}: katalogda {previous.get(key)!r}, "
                    f"Ek-1e'de {value!r}"
                )
    for identifier in sorted(set(old) - {_identity(record) for record in compiled["records"]}):
        findings.append(f"{identifier}: Ek-1e'de yok")
    old_kaynak = committed.get("kaynak")
    if old_kaynak is None:
        findings.append("kaynak: committed katalogda yok")
        return findings
    # The provenance a version-1 file has none of is keyed by identity, so the
    # same record is found on both sides by identity and reported by its new id.
    identity_of = {record["id"]: _identity(record) for record in compiled["records"]}
    for identifier, known in compiled["kaynak"].items():
        previous = old_kaynak.get(identifier) or old_kaynak.get(identity_of[identifier], {})
        if not previous:
            findings.append(f"{identifier}.kaynak: committed katalogda yok")
            continue
        for key, value in known.items():
            if previous.get(key) != value:
                findings.append(
                    f"{identifier}.kaynak.{key}: katalogda {previous.get(key)!r}, "
                    f"Ek-1e'de {value!r}"
                )
    return findings


def compile_hierarchy(pdf_path: Path, workbook_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    pages: dict[int, tuple[str, list[float], list[dict]]] = {}
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheet = workbook[SHEET]
    headers = [str(value) for value in next(sheet.iter_rows(values_only=True))]

    # One entry per record, in the same order: (workbook cell verbatim, title as
    # matched, page, reading).  The two lists are zipped into pairs before the
    # sort so a record and its reading cannot drift apart there, and `kaynak` is
    # built from the pairs once the ids are out.
    readings: list[tuple[str, str, int, Hierarchy]] = []
    records = []
    unresolved = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values))
        if _clean(row["Durum"]) != "Tam":
            continue
        geometry = _clean(row["Geometri"])
        if "POLİGON" not in geometry and "ÇİZGİ" not in geometry:
            continue
        # The cell verbatim, before the whitespace collapse below: it is what the
        # record's `kaynak` keeps, so a reader can see the heading cut and the
        # match that followed rather than only the label that resulted.
        item = str(row["Katalog kalemi"] or "")
        title = _clean(item)
        if TITLE_PREFIX in title:
            title = title.split(TITLE_PREFIX, 1)[1].strip()
        page = int(row["Sayfa"])
        if page not in pages:
            pages[page] = _read_page(reader.pages[page - 1])
        hierarchy = _page_hierarchy(pages[page], title)
        if hierarchy is None:
            unresolved.append(f"s.{page}: {title}")
            continue
        records.append({
            # The three labels a planner reads are repaired to one spelling each.
            # `sld_kurali` and `plan_gml_tipi` are left verbatim on purpose: one
            # is matched by record_for_rule() against the SLD's own rule ids and
            # the other names the XSD's feature type, so a spelling repair would
            # silently break the lookup rather than improve a label.
            "id": "",
            "sembol_adi": _canonical(title),
            "detay_sinifi": _canonical(hierarchy.detay_sinifi),
            "detay_alt_sinifi": _canonical(hierarchy.detay_alt_sinifi),
            "plan_kademesi": _clean(row["Kademe"]),
            "geometri": geometry,
            "plan_gml_tipi": _clean(row["PlanGML tipi"]),
            "sld_kurali": _clean(row["SLD kuralı"]),
            "kaynak_sayfa": page,
        })
        readings.append((item, title, page, hierarchy))
    if unresolved:
        raise RuntimeError("Detay sınıfı çözülemedi: " + "; ".join(unresolved))
    _assert_one_spelling_per_label(records)

    # The record and its reading have to travel together through the sort, so the
    # ids are handed out in the order the file ships rather than in extraction
    # order -- MPYY-<n> then names a position in the catalogue a planner can see,
    # the same way MSP-<n> does in styles/msp_catalog.json.
    ordered = list(zip(records, readings))
    ordered.sort(key=lambda pair: (
        pair[0]["plan_kademesi"], pair[0]["detay_sinifi"], pair[0]["detay_alt_sinifi"],
        pair[0]["sembol_adi"], pair[0]["plan_gml_tipi"], pair[0]["sld_kurali"],
    ))
    records, kaynak = [], {}
    for index, (record, (item, title, page, hierarchy)) in enumerate(ordered, start=1):
        identifier = f"MPYY-{index:03d}"
        record["id"] = identifier
        records.append(record)
        kaynak[identifier] = {
            "sayfa": page,
            "katalog_kalemi": item,
            "baslik": title,
            "hiyerarsi_kaynak": hierarchy.kaynak,
            "baski_detay_sinifi": hierarchy.baski_detay_sinifi,
            "baski_detay_alt_sinifi": hierarchy.baski_detay_alt_sinifi,
        }
    _assert_labels_derive_from_source(records, kaynak)
    return {
        "version": 2,
        "source": {
            "catalog_pdf": pdf_path.name,
            "catalog_pdf_sha256": _sha256(pdf_path),
            "comparison_workbook": workbook_path.name,
            "comparison_workbook_sha256": _sha256(workbook_path),
            "sheet": SHEET,
        },
        "record_count": len(records),
        # The rules that stand between the readings above and the labels below,
        # shipped so the file can be re-derived from its own evidence: applying
        # them to a record's `baski_*` cells reproduces its shipped labels.
        "duzeltmeler": {
            "baslik_oneki": TITLE_PREFIX,
            "yazim": SPELLING_REPAIRS,
            "turkce": TURKISH_REPAIRS,
        },
        # The one fallback in the pipeline, named as such: these titles print on
        # their page, but no DETAY SINIFI block could be paired to them, so the
        # pair below stands in and the record's `baski_*` cells stay empty.
        "devam_tablosu": {
            title: list(pair) for title, pair in CONTINUATION_HIERARCHY.items()
        },
        "records": records,
        "kaynak": kaynak,
    }


def main(argv: list[str]) -> int:
    arguments = [value for value in argv[1:] if not value.startswith("--")]
    if len(arguments) != 2:
        print(__doc__.strip())
        return 2
    compiled = compile_hierarchy(Path(arguments[0]), Path(arguments[1]))

    if "--diff" in argv:
        committed = json.loads(OUTPUT.read_text(encoding="utf-8"))
        findings = _diff(compiled, committed)
        if not findings:
            print(f"{OUTPUT.name}: Ek-1e ile uyuşuyor ({compiled['record_count']} kayıt)")
            return 0
        print(f"{len(findings)} fark:")
        for finding in findings:
            print("  " + finding)
        return 1

    OUTPUT.write_text(json.dumps(compiled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUTPUT}: {compiled['record_count']} alan/çizgi eşlemesi, Ek-1e'den derlendi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
