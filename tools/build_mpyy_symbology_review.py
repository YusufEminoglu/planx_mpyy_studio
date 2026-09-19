"""Build the MPYY → e-Plan symbology review workbook for the author to approve.

    py -3 tools/build_mpyy_symbology_review.py <output.xlsx>

One row per symbology unit: a MPYY feature type and the value of its own
classifying code list (for example ``KentselCalisma.CalismaTip = TicaretAlani``);
types without such a list are one unit. Shared lists that do not change the
land-use legend (value kind, building order, ownership, plan kind, change
reason, voltage) are not classifiers.

Status is computed, never assumed:
  TAM       exactly one catalog entry whose key/label/rule folds to the code
  BELİRSİZ  several catalog entries fold to the code
  YOK       none do
Candidates are ranked by shared words only and are *suggestions*; nothing is
applied until a row's "Onay" column is filled in by the author.
"""

import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
GENERIC_CODELISTS = {"DegerTip", "YapiDuzenTip", "MulkiyetTip", "NitelikTip", "DegismeSebepTip", "GerilimKw"}
FILLER = {"TESIS", "TESISI", "TESISLERI", "ALAN", "ALANI", "ALANLARI", "ALANLAR", "VE", "ILE", "TIP", "TUR", "SINIF", "UIP", "NIP", "CDP", "PL", "HAT", "SNR", "KA", "KST"}
APPROVAL = ["Öneri 1", "Öneri 2", "Öneri 3", "Diğer (anahtarı yaz)", "Gösterim yok"]


def load_catalog():
    spec = importlib.util.spec_from_file_location("eplan_catalog", ROOT / "core" / "eplan_catalog.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EPLAN_CATALOG


def fold(text):
    text = str(text or "").replace("ı", "i").replace("İ", "I")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def words(text):
    text = str(text or "").replace("ı", "i").replace("İ", "I")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return {w for w in re.split(r"[^A-Za-z0-9]+", text.upper()) if w and w not in FILLER}


def caption(code):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", code)


def geometry_family(geometry):
    return {"MultiPolygon": "ALAN", "Polygon": "ALAN", "LineString": "ÇİZGİ", "MultiLineString": "ÇİZGİ", "Point": "NOKTA"}.get(geometry)


def entry_family(entry):
    if "fill" in entry or "tarama" in entry:
        return "ALAN"
    if "line_color" in entry:
        return "ÇİZGİ"
    return "NOKTA"


def units(schema):
    for level, compiled in schema["levels"].items():
        for feature_type in compiled["feature_types"]:
            if feature_type["geometry"] is None:
                continue
            classifiers = [
                f for f in feature_type["fields"]
                if f["type"] == "enum" and f["codelist"] not in GENERIC_CODELISTS
            ]
            if not classifiers:
                yield level, feature_type, None, None, [c["name"] for c in classifiers]
                continue
            primary = classifiers[-1]  # the type's own list is declared last in the inheritance chain
            others = [c["name"] for c in classifiers[:-1]]
            for code in compiled["codelists"][primary["codelist"]]:
                yield level, feature_type, primary["name"], code, others


def match(level, feature_type, code, catalog):
    entries = catalog[level]
    target = fold(code or feature_type["name"])
    targets = {target, target + "ALANI", target + "ALAN", re.sub("ALANI$", "", target)}
    exact = sorted({
        key for key, entry in entries.items()
        if targets & {fold(key), fold(entry.get("label")), fold(entry.get("rule")), fold(entry.get("style"))}
    })
    family = geometry_family(feature_type["geometry"])
    code_words = words(code) if code else words(feature_type["name"])
    type_words = words(feature_type["name"]) - code_words if code else set()
    scored = []
    for key, entry in entries.items():
        names = (key, entry.get("label"), entry.get("rule"), entry.get("style"))
        have = set().union(*(words(n) for n in names))
        folded = [fold(n) for n in names if n]
        shared = code_words & have
        contained = any(target in f or (len(f) >= 5 and f in target) for f in folded)
        if not shared and not contained and key not in exact:
            continue  # a suggestion must share a word of the code itself
        score = len(shared) / max(len(code_words), 1) + 0.3 * len(type_words & have) / max(len(type_words), 1)
        score += 0.8 * contained + 0.25 * (entry_family(entry) == family) + 2.0 * (key in exact)
        scored.append((score, key))
    ranked = [key for _, key in sorted(scored, key=lambda item: (-item[0], item[1]))]
    # One catalog style is often stored under several tabaka spellings; show each style once.
    seen, candidates = set(), []
    for key in ranked:
        style = entries[key].get("style") or key
        if style not in seen:
            seen.add(style)
            candidates.append(key)
    status = "TAM" if len({entries[k].get("style") or k for k in exact}) == 1 else ("BELİRSİZ" if exact else "YOK")
    return status, candidates[:3]


def describe(level, key, catalog):
    if not key:
        return ""
    entry = catalog[level][key]
    return f'{key} — {entry.get("label", "")}'


def swatch(level, key, catalog):
    if not key:
        return None
    entry = catalog[level][key]
    colour = entry.get("fill") or entry.get("line_color")
    return colour.lstrip("#").upper() if colour and len(colour) == 7 else None


def main(output):
    schema = json.loads((ROOT / "styles" / "mpyy_schema.json").read_text(encoding="utf-8"))
    catalog = load_catalog()
    book = Workbook()
    review = book.active
    review.title = "Onay listesi"
    headers = [
        "Sıra", "Kademe", "MPYY tipi", "Geometri", "Sınıflandırma alanı", "Kod", "Kod (okunur)",
        "Durum", "Öneri 1", "Öneri 2", "Öneri 3", "Renk (Öneri 1)", "Onay", "Diğer katalog anahtarı", "Not",
    ]
    review.append(headers)
    for cell in review[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    exact_sheet = book.create_sheet("Tam eşleşenler")
    exact_sheet.append(["Kademe", "MPYY tipi", "Sınıflandırma alanı", "Kod", "e-Plan anahtarı", "Etiket", "Renk"])

    counts = {"TAM": 0, "BELİRSİZ": 0, "YOK": 0}
    row_number = 0
    for level, feature_type, field, code, others in units(schema):
        status, candidates = match(level, feature_type, code, catalog)
        counts[status] += 1
        if status == "TAM":
            key = candidates[0]
            exact_sheet.append([level, feature_type["name"], field or "", code or "", key,
                                catalog[level][key].get("label", ""), ""])
            colour = swatch(level, key, catalog)
            if colour:
                exact_sheet.cell(exact_sheet.max_row, 7).fill = PatternFill("solid", fgColor=colour)
            continue
        row_number += 1
        note = ("Ayrıca sınıflandıran alan(lar): " + ", ".join(others)) if others else ""
        padded = candidates + [None] * (3 - len(candidates))
        review.append([
            row_number, level, feature_type["name"], geometry_family(feature_type["geometry"]), field or "(tip)",
            code or "", caption(code or feature_type["name"]), status,
            describe(level, padded[0], catalog), describe(level, padded[1], catalog), describe(level, padded[2], catalog),
            "", "", "", note,
        ])
        colour = swatch(level, padded[0], catalog)
        if colour:
            review.cell(review.max_row, 12).fill = PatternFill("solid", fgColor=colour)

    last = review.max_row
    approval = DataValidation(type="list", formula1='"' + ",".join(APPROVAL) + '"', allow_blank=True)
    review.add_data_validation(approval)
    approval.add(f"M2:M{last}")
    waiting = PatternFill("solid", fgColor="FFF2CC")
    review.conditional_formatting.add(f"M2:M{last}", FormulaRule(formula=['LEN($M2)=0'], fill=waiting))
    widths = [6, 8, 26, 9, 22, 26, 28, 11, 42, 42, 42, 12, 20, 26, 30]
    for index, width in enumerate(widths, start=1):
        review.column_dimensions[get_column_letter(index)].width = width
    review.freeze_panes = "D2"
    review.auto_filter.ref = f"A1:O{last}"

    catalog_sheet = book.create_sheet("e-Plan kataloğu")
    catalog_sheet.append(["Kademe", "Anahtar", "Etiket", "Kural", "Stil", "Tür", "Dolgu", "Çizgi", "Tarama", "Üst grup", "Renk"])
    for level in ("UIP", "NIP", "CDP"):
        for key, entry in sorted(catalog[level].items()):
            catalog_sheet.append([level, key, entry.get("label"), entry.get("rule"), entry.get("style"), entry_family(entry),
                                  entry.get("fill"), entry.get("line_color"), "var" if entry.get("tarama") else "",
                                  entry.get("ust_grup"), ""])
            colour = swatch(level, key, catalog)
            if colour:
                catalog_sheet.cell(catalog_sheet.max_row, 11).fill = PatternFill("solid", fgColor=colour)
    for sheet in (exact_sheet, catalog_sheet):
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        sheet.freeze_panes = "A2"
        for column in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(column)].width = 24

    guide = book.create_sheet("Nasıl onaylanır", 0)
    lines = [
        "MPYY → e-Plan gösterim eşleşmesi onay listesi",
        "",
        f'Tam eşleşen: {counts["TAM"]} (ayrı sayfada, bilgi için)   Belirsiz: {counts["BELİRSİZ"]}   Eşleşmeyen: {counts["YOK"]}',
        "",
        "1. 'Onay listesi' sayfasında her satırın 'Onay' sütunundan seçim yapın:",
        "   Öneri 1 / 2 / 3  → o e-Plan gösterimi kullanılır",
        "   Diğer (anahtarı yaz) → 'Diğer katalog anahtarı' sütununa 'e-Plan kataloğu' sayfasındaki Anahtarı yazın",
        "   Gösterim yok → bu kod için resmî gösterim yoktur, nötr kalır",
        "2. Boş bıraktığınız satırlar uygulanmaz (sarı görünür).",
        "3. Öneriler yalnızca ortak kelimelere göre sıralanmıştır; doğruluğu garanti edilmez.",
        "4. Kaydedip dosya adını değiştirmeden bana haber verin.",
        "",
        "Kaynaklar: MPYY 1.1.7 XSD (eplan.csb.gov.tr) ve eklentideki e-Plan SLD kataloğu (core/eplan_catalog.py).",
    ]
    for line in lines:
        guide.append([line])
    guide["A1"].font = Font(bold=True, size=14)
    guide.column_dimensions["A"].width = 110

    book.save(output)
    print(json.dumps(counts, ensure_ascii=False), "review rows:", row_number)


if __name__ == "__main__":
    main(sys.argv[1])
