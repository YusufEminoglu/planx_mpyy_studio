"""Human-readable difference report between two MPYY XSD versions in one Ministry zip.

    py -3 tools/diff_mpyy_versions.py <planGMLShema_1_7.zip> 1.1.6 1.1.7 <output.md>
"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compile_mpyy_schema import compile_level  # noqa: E402

LEVELS = {"UIP": ("uip", "Uygulama imar planı"), "NIP": ("nip", "Nazım imar planı"), "CDP": ("cdp", "Çevre düzeni planı")}
TYPE_NAMES = {"MultiPolygon": "alan", "Polygon": "alan", "LineString": "çizgi", "MultiLineString": "çizgi", "Point": "nokta", None: "tablo"}


def field_text(field):
    kind = f'kod listesi `{field["codelist"]}`' if field["type"] == "enum" else field["type"]
    return f'`{field["name"]}` ({kind}, {"zorunlu" if field["required"] else "isteğe bağlı"})'


def diff_level(old, new, lines):
    old_types = {t["name"]: t for t in old["feature_types"]}
    new_types = {t["name"]: t for t in new["feature_types"]}
    lines.append(f"Nesne tipi sayısı: {len(old_types)} → {len(new_types)}\n")
    added = sorted(set(new_types) - set(old_types))
    removed = sorted(set(old_types) - set(new_types))
    if added:
        lines.append("**Yeni nesne tipleri**\n")
        for name in added:
            fields = [field_text(f) for f in new_types[name]["fields"] if f["name"] != "symbolizer"]
            lines.append(f'- `{name}` ({TYPE_NAMES[new_types[name]["geometry"]]}): ' + (", ".join(fields) or "öznitelik yok"))
        lines.append("")
    if removed:
        lines.append("**Kaldırılan nesne tipleri**\n")
        lines.extend(f"- `{name}`" for name in removed)
        lines.append("")
    geometry, optional, required, other = [], [], [], []
    for name in sorted(set(old_types) & set(new_types)):
        before, after = old_types[name], new_types[name]
        if before["geometry"] != after["geometry"]:
            geometry.append(f'- `{name}`: {before["geometry"]} → {after["geometry"]}')
        old_fields = {f["name"]: f for f in before["fields"]}
        new_fields = {f["name"]: f for f in after["fields"]}
        for field in sorted(set(new_fields) - set(old_fields)):
            other.append(f"- `{name}`: yeni alan {field_text(new_fields[field])}")
        for field in sorted(set(old_fields) - set(new_fields)):
            other.append(f"- `{name}`: kaldırılan alan `{field}`")
        for field in sorted(set(old_fields) & set(new_fields)):
            a, b = old_fields[field], new_fields[field]
            if a["required"] and not b["required"] and a["type"] == b["type"]:
                optional.append(f"`{name}.{field}`")
            elif not a["required"] and b["required"] and a["type"] == b["type"]:
                required.append(f"`{name}.{field}`")
            elif a["type"] != b["type"] or a.get("codelist") != b.get("codelist"):
                other.append(f"- `{name}.{field}`: {field_text(a)} → {field_text(b)}")
    if geometry:
        lines.append("**Geometri türü değişen tipler**\n")
        lines.extend(geometry)
        lines.append("")
    if other:
        lines.append("**Alan değişiklikleri**\n")
        lines.extend(other)
        lines.append("")
    if optional:
        lines.append("**Zorunluluktan çıkan alanlar**\n")
        lines.append(", ".join(optional) + "\n")
    if required:
        lines.append("**Zorunlu hale gelen alanlar**\n")
        lines.append(", ".join(required) + "\n")
    changes = []
    for name in sorted(set(old["codelists"]) | set(new["codelists"])):
        a, b = old["codelists"].get(name), new["codelists"].get(name)
        if a == b:
            continue
        if a is None:
            changes.append(f"- `{name}` (yeni liste): " + ", ".join(f"`{c}`" for c in b))
        elif b is None:
            changes.append(f"- `{name}` artık kullanılmıyor")
        else:
            parts = []
            if [c for c in b if c not in a]:
                parts.append("eklenen " + ", ".join(f"`{c}`" for c in b if c not in a))
            if [c for c in a if c not in b]:
                parts.append("kaldırılan " + ", ".join(f"`{c}`" for c in a if c not in b))
            if [c for c in a if c in b] != [c for c in b if c in a]:
                parts.append("sıra değişti")
            changes.append(f"- `{name}`: " + "; ".join(parts))
    if changes:
        lines.append("**Kod listesi değişiklikleri**\n")
        lines.extend(changes)
        lines.append("")
    if old["undefined_members"] != new["undefined_members"]:
        lines.append(f'**Tanımsız koleksiyon üyeleri:** {old["undefined_members"] or "yok"} → {new["undefined_members"] or "yok"}\n')


def main(archive, old_version, new_version, output):
    zip_file = zipfile.ZipFile(archive)
    lines = [f"# MPYY {old_version} → {new_version} farkları", "",
             f"Kaynak: Bakanlık şema paketi `{Path(archive).name}` (eplan.csb.gov.tr). "
             "Bu rapor `tools/diff_mpyy_versions.py` ile XSD dosyalarından üretilmiştir.", ""]
    for level, (prefix, title) in LEVELS.items():
        old = compile_level(zip_file.read(f"{prefix}.V.{old_version}.xsd"))
        new = compile_level(zip_file.read(f"{prefix}.V.{new_version}.xsd"))
        lines.append(f"## {title} ({level})\n")
        diff_level(old, new, lines)
    Path(output).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print("written", output)


if __name__ == "__main__":
    main(*sys.argv[1:5])
