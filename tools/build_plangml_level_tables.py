"""Hat etiketleri and kademe dönüşümü tables for MPYY Studio.

    py -3 tools/build_plangml_level_tables.py <bundle .js>

Sources (the author's own application, copied into MPYY Studio's own files):
  * boundary line catalog entries with a ``{tur:"etiket", metin:"A1"}`` pattern part
    -> ``styles/plangml_line_labels.json``
  * the UİP/NİP/ÇDP tabaka equivalence table (``ese``)
    -> ``styles/plangml_level_conversion.json``

Catalog names are tied to PlanGML types/codes only through ``LABEL_TARGETS`` below
(written by hand, checked against the XSD catalog). Level conversion goes
tabaka -> PlanGML identity through ``styles/plangml_tabaka_crosswalk.json`` on both
sides, so it inherits that table's validation.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_plangml_tabaka_crosswalk import normalize_tabaka  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "styles" / "plangml_schema.json").read_text(encoding="utf-8"))["levels"]
CROSSWALK = json.loads((ROOT / "styles" / "plangml_tabaka_crosswalk.json").read_text(encoding="utf-8"))["levels"]

# Detail catalog name -> PlanGML (type, field, code) per level. None code: the type itself.
KUSAK = "KorumaKusaklari", "KusakTip"
LABEL_TARGETS = {
    "ASKERİ YASAK VE GÜVENLİK BÖLGESİ": {"UIP": ("AskeriYasakBolge", None, None), "NIP": ("AskeriYasakBolge", None, None),
                                         "CDP": ("AskeriYskGuvenlikBlg", None, None)},
    "RİSKLİ ALAN SINIRI": {"NIP": ("KentselDonusumSinirlari", "KentselDonusumSinirlariTip", "RiskliAlanSiniri")},
    "REZERV YAPI ALANI SINIRI": {"NIP": ("KentselDonusumSinirlari", "KentselDonusumSinirlariTip", "RezervYapiAlanSiniri")},
    "YENİLEME ALANI SINIRI": {"NIP": ("KentselDonusumSinirlari", "KentselDonusumSinirlariTip", "YenilemeAlanSiniri")},
    "1.DERECE DOĞAL SİT ALANI": "1DereceDogalSit",
    "2.DERECE DOĞAL SİT ALANI": "2DereceDogalSit",
    "3.DERECE DOĞAL SİT ALANI": "3DereceDogalSit",
    "1.DERECE ARKEOLOJİK SİT ALANI": "1DereceArkeolojikSit",
    "2.DERECE ARKEOLOJİK SİT ALANI": "2DereceArkeolojikSit",
    "3.DERECE ARKEOLOJİK SİT ALANI": "3DereceArkeolojikSit",
    "KESİN KORUNACAK HASSAS ALAN": "KesinKorunacakHassasAlan",
    "NİTELİKLİ DOĞAL KORUMA ALANI": "NitelikliDogalKorumaAlani",
    "SÜRDÜRÜLEBİLİR KORUMA VE KONTROLLÜ KULLANIM ALANI": "SurdurulebilirKorumaKontrolluKullanimAlani",
    "KENTSEL SİT ALANI": "KentselSit",
    "TARİHİ SİT ALANI": "TarihiSit",
    "SİT ETKİLEŞİM GEÇİŞ ALANI SINIRI": "SitEtkilesimAlani",
    "KENTSEL ARKEOLOJİK SİT ALANI": "KentselArkeolojikSit",  # added to SitTip in PlanGML 1.1.7
    "HAVAALANI/HAVALİMANI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "HavaalaniKorumaKusagi")},
    "KARAYOLLARI YOL KENARI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "KarayoluKorumaKusagi")},
    "BORU HATTI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "BoruHattiKorumaKusagi")},
    "SU KANALLARI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "SuKanaliKorumaKusagi")},
    "İÇME SUYU ANA İLETİM HATTI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "IcmesuyuKorumaKusagi")},
    "YER ALTI SU KAYNAKLARI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "YeraltiSuKorumaKusagi")},
    "YER ALTI SU KAYNAKLARI KORUMA ALANLARI": {"UIP": ("YeraltiSuKaynakKoruma", None, None), "NIP": ("YeraltiSuKaynakKoruma", None, None),
                                              "CDP": ("YeraltiSuKaynakKoruma", None, None)},
    "DEMİRYOLLARI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "DemiryoluKorumaKusagi")},
    "YANICI PARLAYICI ve PATLAYICI MADDELER KORUMA KUŞAĞI (GÜVENLİK MESAFESİ)": {"UIP": (*KUSAK, "YaniciPatlayiciMaddeKorumaKusagi")},
    "SAĞLIK KORUMA BANDI": {"UIP": (*KUSAK, "SaglikKorumaBandi")},
    "ENERJİ NAKİL HATTI KORUMA KUŞAĞI": {"UIP": (*KUSAK, "EnerjiNakilHattiKorumaKusagi")},
    "TÜNEL ETKİ ALANI": {"UIP": ("TunelEtkiAlani", None, None)},
    "SOĞUTMA SUYU ALMA HATTI": {"UIP": ("SogutmaSuyuAlmaHatti", None, None), "NIP": ("SogutmaSuyuAlmaHatti", None, None)},
}
EXCLUDED = {}

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
            if s[i] != ":":
                raise ValueError("bad object")
            obj[key], i = parse_value(s, i + 1)
    if c == "[":
        arr, i = [], i + 1
        while True:
            while s[i] in " ,\n\t":
                i += 1
            if s[i] == "]":
                return arr, i + 1
            value, i = parse_value(s, i)
            arr.append(value)
    if c in "\"'`":
        j = i + 1
        while s[j] != c:
            j += 2 if s[j] == "\\" else 1
        return s[i + 1:j], j + 1
    if s.startswith("!0", i):
        return True, i + 2
    if s.startswith("!1", i):
        return False, i + 2
    m = re.compile(r"-?(\d+\.?\d*|\.\d+)(e-?\d+)?").match(s, i)
    if m:
        return float(m.group(0)), m.end()
    m = re.compile(r"[A-Za-z_$][\w$]*").match(s, i)
    if not m:
        raise ValueError("bad token")
    return None if m.group(0) == "null" else {"$ref": m.group(0)}, m.end()


def check(level, feature, field, code):
    types = {t["name"]: {f["name"]: f for f in t["fields"]} for t in SCHEMA[level]["feature_types"]}
    if feature not in types:
        raise SystemExit(f"{level}: {feature} yok")
    if field is None:
        return
    definition = types[feature].get(field)
    if definition is None:
        raise SystemExit(f"{level}: {feature}.{field} yok")
    if definition["type"] == "enum" and code not in SCHEMA[level]["codelists"][definition["codelist"]]:
        raise SystemExit(f"{level}: {feature}.{field}={code} kod listesinde yok")


def build_labels(text):
    entries = []
    for m in re.finditer(r"\{ad:\"", text):
        try:
            obj, _ = parse_value(text, m.start())
        except (ValueError, IndexError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("tanim"), dict) and "planTuru" in obj:
            entries.append(obj)
    labels = defaultdict(dict)
    skipped = {}
    for entry in entries:
        texts = [p["metin"] for p in entry["tanim"].get("desen", []) if isinstance(p, dict) and p.get("tur") == "etiket"]
        if not texts:
            continue
        name, level = entry["ad"], entry["planTuru"]
        if name in EXCLUDED:
            skipped[name] = EXCLUDED[name]
            continue
        target = LABEL_TARGETS.get(name)
        if target is None:
            raise SystemExit("etiketli katalog kaydı eşlenmemiş: " + name)
        if isinstance(target, str):
            feature, field, code = "SitAlanlari", "SitTip", target  # ÇDP SitTip is free text; check() allows it
        else:
            if level not in target:
                skipped[f"{level} {name}"] = "bu kademede PlanGML karşılığı yok"
                continue
            feature, field, code = target[level]
        try:
            check(level, feature, field, code)
        except SystemExit as error:
            skipped[f"{level} {name}"] = str(error)
            continue
        rgb = entry.get("sinirRgb")
        color = "#%02X%02X%02X" % tuple(int(v) for v in rgb.split("/")) if isinstance(rgb, str) else "#000000"
        key = f"{feature}|{field}={code}" if field else feature
        labels[level][key] = {"feature": feature, "field": field, "code": code, "text": texts[0], "color": color,
                              "kaynak": name}
    return {"version": 1, "source": "sınır çizgisi kataloğu (detay kataloğu çizgi tanımları)",
            "levels": {lv: dict(sorted(v.items())) for lv, v in labels.items()}, "skipped": skipped}


def identity(entry):
    attrs = "".join(f"|{k}={v}" for k, v in sorted(entry["attrs"].items()))
    return entry["feature"] + attrs


def build_conversion(text):
    table, _ = parse_value(text, re.search(r"ese=\[", text).end() - 1)
    pairs = {}
    for source, target in (("UIP", "NIP"), ("UIP", "CDP"), ("NIP", "CDP")):
        votes = defaultdict(Counter)
        no_counterpart = Counter()
        for row in table:
            src_tabaka, tgt_tabaka = row.get(source.lower()), row.get(target.lower())
            src = CROSSWALK[source]["entries"].get(normalize_tabaka(src_tabaka)) if src_tabaka else None
            if src is None:
                continue
            tgt = CROSSWALK[target]["entries"].get(normalize_tabaka(tgt_tabaka)) if tgt_tabaka else None
            if tgt is None:
                no_counterpart[identity(src)] += 1
            else:
                votes[identity(src)][json.dumps(tgt, sort_keys=True, ensure_ascii=False)] += 1
        rules, ambiguous = {}, {}
        for key, counter in votes.items():
            candidates = [json.loads(k) for k in counter]
            if len(candidates) > 1:
                ambiguous[key] = {c["feature"] + str(c["attrs"]): counter[json.dumps(c, sort_keys=True, ensure_ascii=False)] for c in candidates}
            features = {c["feature"] for c in candidates}
            if len(features) == 1:
                # Same type, different codes (e.g. density classes): keep only what all agree on;
                # the differing field is left for the planner to fill in.
                shared = dict(set.intersection(*(set(c["attrs"].items()) for c in candidates)))
                open_fields = sorted({f for c in candidates for f in c["attrs"]} - set(shared))
                rules[key] = {"feature": candidates[0]["feature"], "attrs": shared}
                if open_fields:
                    rules[key]["doldurulacak"] = open_fields
                continue
            (best, count), *rest = counter.most_common()
            if rest and rest[0][1] == count:
                continue  # tie between different types: no rule rather than a coin toss
            target_entry = json.loads(best)
            rules[key] = {"feature": target_entry["feature"], "attrs": target_entry["attrs"]}
        pairs[f"{source}>{target}"] = {
            "rules": dict(sorted(rules.items())),
            "no_counterpart": sorted(k for k in no_counterpart if k not in rules),
            "ambiguous": ambiguous,
        }
        print(source, "->", target, "rules", len(rules), "no counterpart", len(pairs[f"{source}>{target}"]["no_counterpart"]),
              "ambiguous", len(ambiguous))
    return {"version": 1, "source": "UİP/NİP/ÇDP tabaka eşdeğerlik tablosu + MPYY tabaka eşleşmesi", "pairs": pairs}


def main(bundle):
    text = Path(bundle).read_text(encoding="utf-8", errors="replace")
    labels = build_labels(text)
    (ROOT / "styles" / "plangml_line_labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    print("labels", {lv: len(v) for lv, v in labels["levels"].items()}, "skipped", labels["skipped"])
    conversion = build_conversion(text)
    (ROOT / "styles" / "plangml_level_conversion.json").write_text(json.dumps(conversion, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
