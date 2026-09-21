"""Compile the Ek-1e detail-class hierarchy for MPYY polygon and line rules.

The generated JSON deliberately keeps the PlanGML type and original SLD rule
identifier alongside the human-facing catalog symbol name.  This lets a QGIS
workspace expose the requested ``sembol adı → detay sınıfı → detay alt sınıfı``
relationship without changing the XSD's legal code lists.

Usage::

    py -3 tools/compile_mpyy_detail_hierarchy.py <Ek-1e.pdf> <comparison.xlsx>
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
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

# These p.18/p.19 entries are printed in the same continuation block as the
# immediately preceding planlama sınırları items, without repeating headers.
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
    """Repair the few ASCII-only Turkish words produced by PDF text extraction."""
    replacements = {
        "TURIZM": "TURİZM",
        "SIT ": "SİT ",
        "SIT VE": "SİT VE",
        "SU-ATIKSU": "SU, ATIKSU",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


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


def _page_hierarchy(page_data: tuple[str, list[float], list[dict]], title: str):
    """Find the detail class block belonging to ``title`` on one printed page.

    The plain extraction does not always hand a page's blocks over in printed
    order -- on some pages it emits every title first and then the blocks -- so
    pairing a block with "the text printed before it" hands the wrong class to
    the title.  Blocks are paired by printed position instead: the one directly
    below the title, with no other title printed in between.
    """
    text, positions, lines = page_data
    title_at = _title_lines(lines, title)
    if title_at is None:
        return CONTINUATION_HIERARCHY.get(title)
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
        return CONTINUATION_HIERARCHY.get(title)
    _, detail, sub = max(blocks, key=lambda block: block[0])
    return _turkish(detail), _turkish(sub)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_hierarchy(pdf_path: Path, workbook_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    pages: dict[int, tuple[str, list[float], list[dict]]] = {}
    workbook = load_workbook(workbook_path, read_only=True, data_only=True)
    sheet = workbook[SHEET]
    headers = [str(value) for value in next(sheet.iter_rows(values_only=True))]

    records = []
    unresolved = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        row = dict(zip(headers, values))
        if _clean(row["Durum"]) != "Tam":
            continue
        geometry = _clean(row["Geometri"])
        if "POLİGON" not in geometry and "ÇİZGİ" not in geometry:
            continue
        title = _clean(row["Katalog kalemi"])
        if "DETAY KATALOĞU" in title:
            title = title.split("DETAY KATALOĞU", 1)[1].strip()
        page = int(row["Sayfa"])
        if page not in pages:
            pages[page] = _read_page(reader.pages[page - 1])
        hierarchy = _page_hierarchy(pages[page], title)
        if hierarchy is None:
            unresolved.append(f"s.{page}: {title}")
            continue
        detail_class, detail_subclass = hierarchy
        records.append({
            # The three labels a planner reads are repaired to one spelling each.
            # `sld_kurali` and `plan_gml_tipi` are left verbatim on purpose: one
            # is matched by record_for_rule() against the SLD's own rule ids and
            # the other names the XSD's feature type, so a spelling repair would
            # silently break the lookup rather than improve a label.
            "sembol_adi": _canonical(title),
            "detay_sinifi": _canonical(detail_class),
            "detay_alt_sinifi": _canonical(detail_subclass),
            "plan_kademesi": _clean(row["Kademe"]),
            "geometri": geometry,
            "plan_gml_tipi": _clean(row["PlanGML tipi"]),
            "sld_kurali": _clean(row["SLD kuralı"]),
            "kaynak_sayfa": page,
        })
    if unresolved:
        raise RuntimeError("Detay sınıfı çözülemedi: " + "; ".join(unresolved))
    _assert_one_spelling_per_label(records)

    records.sort(key=lambda item: (
        item["plan_kademesi"], item["detay_sinifi"], item["detay_alt_sinifi"],
        item["sembol_adi"], item["plan_gml_tipi"], item["sld_kurali"],
    ))
    return {
        "version": 1,
        "source": {
            "catalog_pdf": pdf_path.name,
            "catalog_pdf_sha256": _sha256(pdf_path),
            "comparison_workbook": workbook_path.name,
            "comparison_workbook_sha256": _sha256(workbook_path),
            "sheet": SHEET,
        },
        "record_count": len(records),
        "records": records,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    result = compile_hierarchy(Path(argv[1]), Path(argv[2]))
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUTPUT}: {result['record_count']} alan/çizgi eşlemesi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
