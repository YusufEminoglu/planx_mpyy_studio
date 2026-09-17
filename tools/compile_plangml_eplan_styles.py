"""Official e-Plan GeoServer SLDs -> styles for the PlanGML 1.1.7 workspace tables.

    py -3 tools/compile_plangml_eplan_styles.py "<E-Plan SLD.zip>"

The Ministry's SLDs render PlanGML data directly:
  * style name   = <LEVEL>_ + SNAKE_CASE(feature type)   (KentselCalisma -> UIP_KENTSEL_CALISMA)
  * property     = snake_case(field)                     (CalismaTip -> calisma_tip)
  * literal      = position of the code in the XSD code list (0 -> TicaretAlani)
and every rule carries a title naming its code (TICARET_ALANI).

Filters are rewritten to this plugin's schema ("CalismaTip" = 'TicaretAlani').
A rule's code is resolved and the method recorded in ``mapping.json``:
  index           list position and title agree
  index_untitled  title is not a name (e.g. "0"); list position used
  title           title names a different code than the position -> title used, flagged for review
  unresolved      neither yields a code -> rule dropped, flagged for review
Tarama images referenced by the rules are copied byte for byte from the archive
into ``resources/`` (same source and notice as the existing tiles). Eleven Ministry
SLDs name a tile with a stray ``m`` inside its UUID (``bc40m``, ``40mm40mm``); a UUID
is hexadecimal, so the ``m`` is dropped when that yields a tile present in the archive.
M series types the Ministry set has no style for borrow the style of the same type at the
current level (MUIP<-UIP, MNIP<-NIP, MCDP25/MCDP100<-CDP) when the geometry is the same.
Only rules whose fields and codes exist in the M schema are kept; legacy codes then fall
to the plugin's grey ELSE rule. Borrowed styles are recorded as ``style_match: current_level``.
Point symbols the SLDs load from ``http://localhost/TaramaSembol/*.svg`` are not in the
archive (nor anywhere public); they are listed per rule as ``missing_svg_symbols``.
A few label texts were saved as Windows-1254 bytes read as Latin-1 (``YENÝLEME``); only
the six letters that differ between those code pages are mapped back (Ý→İ, ý→ı, Þ→Ş,
þ→ş, Ð→Ğ, ð→ğ), and only inside ``<Label>`` text.
"""

import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "styles" / "plangml_sld"
RESOURCES = ROOT / "resources"
SLD = "http://www.opengis.net/sld"
OGC = "http://www.opengis.net/ogc"
XLINK = "http://www.w3.org/1999/xlink"
for prefix, uri in (("", SLD), ("ogc", OGC), ("xlink", XLINK), ("xsi", "http://www.w3.org/2001/XMLSchema-instance")):
    ET.register_namespace(prefix, uri)
TARAMA_URL = re.compile(r"^https?://[^/]+/TaramaResim/(?P<name>[\w\-]+\.png)$", re.IGNORECASE)
TARAMA_PLACEHOLDER = "mpyy-tarama:"
MISSING_SYMBOL_PLACEHOLDER = "mpyy-eksik-sembol:"
LATIN1_AS_1254 = str.maketrans("ÝýÞþÐð", "İıŞşĞğ")
M_BASE = {"MUIP": "UIP", "MNIP": "NIP", "MCDP25": "CDP", "MCDP100": "CDP"}
AVAILABLE_TILES = set()
REPAIRED_TILES = {}
DECISIONS = json.loads((OUT / "decisions.json").read_text(encoding="utf-8"))


def snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()


def fold(text):
    text = str(text or "").replace("ı", "i").replace("İ", "I")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def title_code(title, codes):
    """The code a rule title names, if exactly one does."""
    folded = fold(title)
    if not folded or folded.isdigit():
        return None
    exact = [c for c in codes if fold(c) == folded or fold(re.sub("Alani$", "", c)) == folded]
    if len(exact) == 1:
        return exact[0]
    near = [c for c in codes if fold(c) in folded or folded in fold(c)]
    near = sorted(near, key=lambda c: -len(fold(c)))
    if near and (len(near) == 1 or len(fold(near[0])) > len(fold(near[1]))):
        return near[0]
    return None


def title_words_in(title, code):
    """True when every word of the title occurs in the code (titles are often abbreviated)."""
    words = [fold(w) for w in re.split(r"[_\s\-]+", str(title or "")) if fold(w) and fold(w) not in ("ALANI", "ALAN")]
    return bool(words) and not any(w.isdigit() for w in words) and all(w in fold(code) for w in words)


def find_style(level, feature_type, styles):
    alias = DECISIONS["style_aliases"].get(level, {}).get(feature_type)
    if alias:
        return alias["style"], "decision"
    exact = f"{level}_{snake(feature_type).upper()}"
    if exact in styles:
        return exact, "exact"
    candidates = [s for s in styles if s.startswith(level + "_") and fold(s[len(level) + 1:]) == fold(feature_type)]
    if len(candidates) == 1:
        return candidates[0], "folded"
    # The Ministry abbreviates long names (UIP_IMAR_HAK_AKTARIM_SINIR, NIP_RAYLI_TOPLU_TASIMA_HAT):
    # same word count, each style word the start of the type word; singular/plural tolerated.
    def singular(word):
        return re.sub(r"(LARI|LERI)$", "I", re.sub(r"(LAR|LER)$", "", word))
    type_words = [fold(w) for w in snake(feature_type).split("_")]
    abbreviated = []
    for style in styles:
        if not style.startswith(level + "_"):
            continue
        style_words = [fold(w) for w in style[len(level) + 1:].split("_")]
        if len(style_words) == len(type_words) and all(
            t.startswith(w) or singular(t).startswith(w) or singular(t) == singular(w)
            for w, t in zip(style_words, type_words)
        ):
            abbreviated.append(style)
    if len(abbreviated) == 1:
        return abbreviated[0], "abbreviated"
    return None, None


def tile_name(name):
    if name in AVAILABLE_TILES:
        return name
    stem, extension = name.rsplit(".", 1)
    repaired = stem.replace("m", "") + "." + extension
    if repaired in AVAILABLE_TILES and re.fullmatch(r"[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}", repaired[:-4]):
        REPAIRED_TILES[name] = repaired
        return repaired
    return name


def compile_style(root, level, feature_type, schema, images):
    fields = {snake(f["name"]): f for f in feature_type["fields"]}
    alias = DECISIONS["style_aliases"].get(level, {}).get(feature_type["name"], {})
    by_name = {f["name"]: f for f in feature_type["fields"]}
    for sld_property, field_name in alias.get("property_aliases", {}).items():
        fields[sld_property] = by_name[field_name]
    null_rules = {
        (r["sld_property"], r["literal"]) for r in DECISIONS["literal_rules"]
        if r["level"] == level and r["type"] == feature_type["name"] and r["action"] == "is_null"
    }
    index_rules = {
        (r["sld_property"], r["literal"]) for r in DECISIONS["literal_rules"]
        if r["level"] == level and r["type"] == feature_type["name"] and r["action"] == "index"
    }
    codelists = schema["codelists"]
    report = []
    unknown_properties = set()
    for style in root.iter(f"{{{SLD}}}FeatureTypeStyle"):
        for rule in list(style.findall(f"{{{SLD}}}Rule")):
            title = rule.findtext(f"{{{SLD}}}Title") or rule.findtext(f"{{{SLD}}}Name") or ""
            entry = {"title": title, "conditions": [], "dropped": False, "font_marks": []}
            keep = True
            parents = {child: parent for parent in rule.iter() for child in parent}
            for comparison in list(rule.iter(f"{{{OGC}}}PropertyIsEqualTo")):
                prop = comparison.find(f"{{{OGC}}}PropertyName")
                literal = comparison.find(f"{{{OGC}}}Literal")
                if prop is not None and literal is not None and ((prop.text or "").strip(), literal.text) in null_rules:
                    field = fields[prop.text.strip()]
                    is_null = ET.Element(f"{{{OGC}}}PropertyIsNull")
                    name = ET.SubElement(is_null, f"{{{OGC}}}PropertyName")
                    name.text = field["name"]
                    parent = parents[comparison]
                    parent.insert(list(parent).index(comparison), is_null)
                    parent.remove(comparison)
                    entry["conditions"].append({"field": field["name"], "sld_property": prop.text.strip(),
                                                "literal": literal.text, "code": None, "resolution": "decision_is_null"})
                    continue
                field = fields.get((prop.text or "").strip()) if prop is not None else None
                if field is None or literal is None:
                    continue
                condition = {"field": field["name"], "sld_property": prop.text.strip(), "literal": literal.text}
                if field["type"] == "enum":
                    codes = codelists[field["codelist"]]
                    try:
                        by_index = codes[int(literal.text)]
                    except (TypeError, ValueError, IndexError):
                        by_index = None
                    by_title = title_code(title, codes)
                    if by_index and title_words_in(title, by_index):
                        by_title = by_index  # e.g. VAHSI_COP_DEPOLAMA_ALANI is a shortened VahsiCopDepolamaVeKapatmaAlani
                    if by_index and (prop.text.strip(), literal.text) in index_rules:
                        code, resolution = by_index, "decision_index"
                    elif by_index and (by_title in (None, by_index)):
                        code = by_index
                        resolution = "index" if by_title == by_index else "index_untitled"
                    elif by_title:
                        code, resolution = by_title, "title"
                    else:
                        code, resolution = None, "unresolved"
                    condition.update({"code": code, "by_index": by_index, "resolution": resolution})
                    if code is None:
                        keep = False
                    else:
                        literal.text = code
                entry["conditions"].append(condition)
            for prop in rule.iter(f"{{{OGC}}}PropertyName"):
                name = (prop.text or "").strip()
                if name in fields:
                    prop.text = fields[name]["name"]
                elif name != "geometry":
                    unknown_properties.add(name)
            for label in rule.iter(f"{{{SLD}}}Label"):
                if label.text:
                    label.text = label.text.translate(LATIN1_AS_1254)
            for resource in rule.iter(f"{{{SLD}}}OnlineResource"):
                match = TARAMA_URL.match(resource.get(f"{{{XLINK}}}href", ""))
                if match:
                    tile = tile_name(match.group("name"))
                    images.add(tile)
                    resource.set(f"{{{XLINK}}}href", TARAMA_PLACEHOLDER + tile)
            for resource in rule.iter(f"{{{SLD}}}OnlineResource"):
                symbol = re.search(r"/TaramaSembol/(?P<name>[\w\-]+\.svg)$", resource.get(f"{{{XLINK}}}href", ""))
                if symbol:
                    # The Ministry's GeoServer served these from its own host; they are not in the archive.
                    entry.setdefault("missing_svg_symbols", []).append(symbol.group("name"))
                    resource.set(f"{{{XLINK}}}href", MISSING_SYMBOL_PLACEHOLDER + symbol.group("name"))
            for mark in rule.iter(f"{{{SLD}}}Mark"):
                name = mark.findtext(f"{{{SLD}}}WellKnownName") or ""
                font = re.match(r"ttf://(?P<family>[^#]+)#0x(?P<code>[0-9A-Fa-f]+)", name)
                if font:
                    fill = mark.find(f"{{{SLD}}}Fill/{{{SLD}}}CssParameter[@name='fill']")
                    entry["font_marks"].append({
                        "family": font.group("family"),
                        "character": int(font.group("code"), 16),
                        "color": fill.text if fill is not None else "#000000",
                    })
            if not keep:
                entry["dropped"] = True
                style.remove(rule)
            report.append(entry)
    return report, sorted(unknown_properties)


def borrow_current_level(mapping, levels):
    for level, base in M_BASE.items():
        report, base_report = mapping["levels"][level], mapping["levels"][base]
        types = {t["name"]: t for t in levels[level]["feature_types"]}
        base_types = {t["name"]: t for t in levels[base]["feature_types"]}
        still_missing = []
        decided = DECISIONS.get("m_borrow", {}).get(level, {})
        for name in report["missing_styles"]:
            origin = decided.get(name, {}).get("from", name)
            aliases = decided.get(name, {}).get("property_aliases", {})  # M field -> current field
            source = base_report["types"].get(origin)
            if source is None or origin not in base_types or types[name]["geometry"] != base_types[origin]["geometry"]:
                still_missing.append(name)
                continue
            current_to_m = {v: k for k, v in aliases.items()}
            fields = {f["name"] if f["name"] not in aliases else aliases[f["name"]]: f for f in types[name]["fields"]}
            root = ET.parse(OUT / base / f"{origin}.sld").getroot()
            for prop in root.iter(f"{{{OGC}}}PropertyName"):
                if prop.text and prop.text.strip() in current_to_m:
                    prop.text = current_to_m[prop.text.strip()]
            sld_rules = [r for r in root.iter(f"{{{SLD}}}Rule")]
            kept_rules, report_rules = 0, []
            for element, rule in zip(sld_rules, [r for r in source["rules"] if not r["dropped"]]):
                reasons = []
                for condition in rule["conditions"]:
                    field = fields.get(condition["field"])
                    if field is None:
                        reasons.append("alan yok: " + condition["field"])
                    elif field["type"] == "enum" and condition.get("code") and condition["code"] not in levels[level]["codelists"][field["codelist"]]:
                        reasons.append("kod yok: " + condition["code"])
                entry = dict(rule, dropped=bool(reasons), borrow_reasons=reasons)
                if reasons:
                    for style in root.iter(f"{{{SLD}}}FeatureTypeStyle"):
                        if element in list(style):
                            style.remove(element)
                else:
                    kept_rules += 1
                report_rules.append(entry)
            if not kept_rules:
                still_missing.append(name)
                continue
            for title in root.iter(f"{{{SLD}}}Name"):
                title.text = (title.text or "").replace(base + "_", level + "_", 1)
                break
            ET.ElementTree(root).write(OUT / level / f"{name}.sld", encoding="utf-8", xml_declaration=True)
            report["types"][name] = {
                "style": source["style"], "style_match": "current_level", "borrowed_from": f"{base}/{origin}",
                "rules": report_rules, "unknown_properties": [],
            }
        report["missing_styles"] = still_missing


def main(archive_path):
    archive = zipfile.ZipFile(archive_path)
    styles = {
        name.rsplit("/", 1)[1][:-4]: name
        for name in archive.namelist()
        if name.startswith("gs-data/") and name.endswith(".sld")
    }
    levels = {}
    for catalog_file in ("plangml_schema.json", "plangml_m_schema.json"):  # M series: MUIP/MNIP styles exist, MCDP do not
        levels.update(json.loads((ROOT / "styles" / catalog_file).read_text(encoding="utf-8"))["levels"])
    AVAILABLE_TILES.update(
        info.filename.rsplit("/", 1)[1]
        for info in archive.infolist()
        if info.filename.startswith("TaramaResim/") and not info.is_dir()
    )
    mapping = {"source": Path(archive_path).name, "levels": {}}
    images = set()
    for level, schema in levels.items():
        level_dir = OUT / level
        level_dir.mkdir(parents=True, exist_ok=True)
        level_report = {"types": {}, "missing_styles": []}
        for feature_type in schema["feature_types"]:
            if feature_type["geometry"] is None:
                continue
            style_name, how = find_style(level, feature_type["name"], styles)
            if style_name is None:
                level_report["missing_styles"].append(feature_type["name"])
                continue
            root = ET.fromstring(archive.read(styles[style_name]))
            rules, unknown = compile_style(root, level, feature_type, schema, images)
            ET.ElementTree(root).write(level_dir / f'{feature_type["name"]}.sld', encoding="utf-8", xml_declaration=True)
            level_report["types"][feature_type["name"]] = {
                "style": style_name, "style_match": how, "rules": rules, "unknown_properties": unknown,
            }
        mapping["levels"][level] = level_report
    borrow_current_level(mapping, levels)

    available = {
        info.filename.rsplit("/", 1)[1]: info
        for info in archive.infolist()
        if info.filename.startswith("TaramaResim/") and not info.is_dir()
    }
    copied = 0
    for name in sorted(images):
        target = RESOURCES / name
        if name in available and not target.exists():
            target.write_bytes(archive.read(available[name]))
            copied += 1
    mapping["images"] = {
        "referenced": len(images),
        "copied_now": copied,
        "absent_from_source": sorted(n for n in images if n not in available),
        "repaired_names": dict(sorted(REPAIRED_TILES.items())),
    }
    (OUT / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")

    for level, report in mapping["levels"].items():
        rules = [r for t in report["types"].values() for r in t["rules"]]
        resolutions = {}
        for rule in rules:
            for condition in rule["conditions"]:
                if "resolution" in condition:
                    resolutions[condition["resolution"]] = resolutions.get(condition["resolution"], 0) + 1
        print(level, "styled types", len(report["types"]), "missing", report["missing_styles"],
              "rules", len(rules), resolutions)
    print("images", mapping["images"]["referenced"], "copied", copied,
          "absent", len(mapping["images"]["absent_from_source"]))


if __name__ == "__main__":
    main(sys.argv[1])
