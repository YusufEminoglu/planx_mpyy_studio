"""CAD tabaka → MPYY 1.1.7 crosswalk for MPYY Studio.

    py -3 tools/build_mpyy_tabaka_crosswalk.py <bundle .js> [<review.xlsx>]

Source idea and rows: tabaka tables composed per plan type:
UIP = dee+Lw+mee, NIP = hee+Lw+pee, CDP = fee+Lw+gee.
MPYY Studio keeps its own copy.

Every row is validated against ``styles/mpyy_schema.json``. A row that does
not fit its level is repaired only by these rules, in order, or left out:
  1. feature_equivalents in styles/mpyy_crosswalk_decisions.json (semantic, per level)
  2. field: the value belongs to exactly one other code list of the same type
  3. code: exactly one code of the list folds to the value (prefix / one typo)
  4. feature: exactly one type name of the level differs by one character
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "styles" / "mpyy_tabaka_crosswalk.json"
COMPOSE = {"UIP": ["dee", "Lw", "mee"], "NIP": ["hee", "Lw", "pee"], "CDP": ["fee", "Lw", "gee"]}


def fold(text):
    text = str(text or "").replace("ı", "i").replace("İ", "I")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def normalize_tabaka(name):
    text = str(name or "").replace("ı", "i").replace("İ", "I")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def one_edit(a, b):
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:] or (len(a) == len(b) and a[i + 1:] == b[i + 1:])


def parse_value(s, i):
    while s[i] in " \n\t":
        i += 1
    c = s[i]
    if c == "{":
        obj, i = {}, i + 1
        while True:
            while s[i] in " ,\n\t":
                i += 1
            if s[i] == "}":
                return obj, i + 1
            if s[i] in "\"'":
                j = s.index(s[i], i + 1)
                key, i = s[i + 1:j], j + 1
            else:
                m = re.compile(r"[^:,}\s]+").match(s, i)
                key, i = m.group(0), m.end()
            value, i = parse_value(s, i + 1)
            obj[key] = value
    if c in "\"'`":
        j = i + 1
        while s[j] != c:
            j += 2 if s[j] == "\\" else 1
        return s[i + 1:j], j + 1
    if s.startswith("!0", i):
        return True, i + 2
    if s.startswith("!1", i):
        return False, i + 2
    m = re.compile(r"[\w.$-]+").match(s, i)
    return m.group(0), m.end()


def extract_tables(bundle):
    text = Path(bundle).read_text(encoding="utf-8", errors="replace")
    wanted = {name for parts in COMPOSE.values() for name in parts}
    tables = {}
    for m in re.finditer(r"(?<![\w$.])([A-Za-z_$][\w$]{0,3})=\{(?=[\"']?[A-ZÇĞİÖŞÜ][^:]{1,60}[\"']?:\{feature:)", text):
        if m.group(1) in wanted:
            tables[m.group(1)], _ = parse_value(text, m.end() - 1)
    missing = wanted - set(tables)
    if missing:
        raise SystemExit("bundle tables not found: " + ", ".join(sorted(missing)))
    composition = re.search(r"LN=\{\.\.\.(\w+),\.\.\.(\w+),\.\.\.(\w+)\},EN=\{\.\.\.(\w+),\.\.\.(\w+),\.\.\.(\w+)\},iE=\{\.\.\.(\w+),\.\.\.(\w+),\.\.\.(\w+)\}", text)
    if composition is None or list(composition.groups()) != COMPOSE["UIP"] + COMPOSE["NIP"] + COMPOSE["CDP"]:
        raise SystemExit("bundle composition changed; review COMPOSE before rebuilding")
    return tables


def validate(level, feature, attrs, schema):
    types = {t["name"]: t for t in schema[level]["feature_types"]}
    if feature not in types:
        return f"'{feature}' bu kademenin şemasında yok"
    fields = {f["name"]: f for f in types[feature]["fields"]}
    for name, value in attrs.items():
        field = fields.get(name)
        if field is None:
            return f"'{feature}.{name}' alanı yok"
        if field["type"] == "enum" and value not in schema[level]["codelists"][field["codelist"]]:
            return f"'{name}={value}' kod listesinde yok"
    return None


def repair(level, feature, attrs, schema, decisions):
    for rule in decisions["feature_equivalents"]:
        target = rule.get(level)
        if target and rule["from"] == feature and all(attrs.get(k) == v for k, v in rule["attrs"].items()):
            return target["feature"], dict(target["attrs"]), "karar: " + rule["gerekce"]
    types = {t["name"]: t for t in schema[level]["feature_types"]}
    codelists = schema[level]["codelists"]
    if feature not in types:
        near = [name for name in types if one_edit(fold(name), fold(feature))]
        if len(near) != 1:
            return None
        feature, note = near[0], f"tip adı yazımı düzeltildi ({feature} → {near[0]})"
        if validate(level, feature, attrs, schema) is None:
            return feature, attrs, note
    fields = {f["name"]: f for f in types[feature]["fields"]}
    fixed, notes = {}, []
    for name, value in attrs.items():
        field = fields.get(name)
        if field is None or field["type"] != "enum":
            candidates = [f for f in fields.values() if f["type"] == "enum" and value in codelists[f["codelist"]]]
            if len(candidates) != 1:
                return None
            notes.append(f"alan adı {name} → {candidates[0]['name']}")
            name, field = candidates[0]["name"], candidates[0]
        codes = codelists[field["codelist"]]
        if value not in codes:
            near = [c for c in codes if fold(c).startswith(fold(value)) or one_edit(fold(c), fold(value))]
            if len(near) != 1:
                return None
            notes.append(f"kod {value} → {near[0]}")
            value = near[0]
        fixed[name] = value
    return feature, fixed, "; ".join(notes)


def main(bundle, review=None):
    schema = json.loads((ROOT / "styles" / "mpyy_schema.json").read_text(encoding="utf-8"))["levels"]
    decisions = json.loads((ROOT / "styles" / "mpyy_crosswalk_decisions.json").read_text(encoding="utf-8"))
    tables = extract_tables(bundle)
    catalog = {"version": 1, "source": "Resmi tabaka tabloları, MPYY 1.1.7 XSD ile denetlendi", "levels": {}}
    review_rows = []
    for level, parts in COMPOSE.items():
        merged = {}
        for part in parts:
            merged.update(tables[part])
        entries, skipped = {}, {}
        for tabaka, row in merged.items():
            key = normalize_tabaka(tabaka)
            if row.get("drop"):
                skipped[key] = "yardımcı çizim tabakası"
                continue
            feature, attrs = row.get("feature") or "", dict(row.get("attrs") or {})
            if row.get("unsupported") or not feature:
                skipped[key] = "bu kademede desteklenmiyor"
                continue
            attrs = {k: v for k, v in attrs.items() if not k.startswith("Ilan")}  # dates are data, not identity
            override = decisions["tabaka_overrides"].get(level, {}).get(key) or decisions["tabaka_overrides"]["*"].get(key)
            if override:
                if override.get("exclude"):
                    skipped[key] = override["gerekce"]
                    review_rows.append([level, tabaka, feature, attrs, "", {}, "Alınmadı (anlam)", "", override["gerekce"]])
                    continue
                if validate(level, override["feature"], override["attrs"], schema) is None:
                    entries[key] = {"feature": override["feature"], "attrs": override["attrs"], "duzeltme": "karar: " + override["gerekce"]}
                    review_rows.append([level, tabaka, feature, attrs, override["feature"], override["attrs"],
                                        "Düzeltildi (anlam)", "", override["gerekce"]])
                    continue
            problem = validate(level, feature, attrs, schema)
            if problem is None:
                entries[key] = {"feature": feature, "attrs": attrs}
                continue
            repaired = repair(level, feature, attrs, schema, decisions)
            if repaired and validate(level, repaired[0], repaired[1], schema) is None:
                entries[key] = {"feature": repaired[0], "attrs": repaired[1], "duzeltme": repaired[2]}
                review_rows.append([level, tabaka, feature, attrs, repaired[0], repaired[1], "Düzeltildi", problem, repaired[2]])
            else:
                skipped[key] = problem
                review_rows.append([level, tabaka, feature, attrs, "", {}, "Alınmadı", problem,
                                    "Bu kademenin şemasında anlamca karşılığı yok"])
        catalog["levels"][level] = {"entries": dict(sorted(entries.items())), "skipped": dict(sorted(skipped.items()))}
        print(level, "entries", len(entries), "skipped", len(skipped),
              "repaired", sum(1 for e in entries.values() if "duzeltme" in e))
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    if review:
        write_review(review, review_rows)


def write_review(path, rows):
    from openpyxl import Workbook
    from openpyxl.formatting.rule import FormulaRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    book = Workbook()
    guide = book.active
    guide.title = "Açıklama"
    for line in [
        "CAD tabaka → MPYY eşleşmesi: son kontrol",
        "",
        "Geçerli satırlar doğrudan alındı. Burada yalnız düzeltilen ve alınmayan satırlar var.",
        "Katılmadığınız satırda 'İtiraz' sütununu seçin.",
        "",
        f"Düzeltilen: {sum(1 for r in rows if r[6] == 'Düzeltildi')}   Alınmayan: {sum(1 for r in rows if r[6] == 'Alınmadı')}",
    ]:
        guide.append([line])
    guide["A1"].font = Font(bold=True, size=14)
    guide.column_dimensions["A"].width = 110
    sheet = book.create_sheet("Son kontrol")
    sheet.append(["Kademe", "Tabaka", "Kaynak tipi", "Kaynak öznitelik", "MPYY tipi", "MPYY öznitelik",
                  "Karar", "Sorun", "Gerekçe", "İtiraz", "Not"])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for level, tabaka, feature, attrs, new_feature, new_attrs, decision, problem, reason in rows:
        fmt = lambda d: ", ".join(f"{k}={v}" for k, v in d.items())
        sheet.append([level, tabaka, feature, fmt(attrs), new_feature, fmt(new_attrs), decision, problem, reason, "", ""])
        for cell in sheet[sheet.max_row]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    last = sheet.max_row
    objection = DataValidation(type="list", formula1='"Doğru değil,Emin değilim"', allow_blank=True)
    sheet.add_data_validation(objection)
    objection.add(f"J2:J{last}")
    sheet.conditional_formatting.add(f"A2:K{last}", FormulaRule(formula=["LEN($J2)>0"], fill=PatternFill("solid", fgColor="F8CBAD")))
    for index, width in enumerate([8, 26, 24, 34, 24, 34, 12, 36, 60, 16, 26], start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = f"A1:K{last}"
    book.save(path)


if __name__ == "__main__":
    main(*sys.argv[1:])
