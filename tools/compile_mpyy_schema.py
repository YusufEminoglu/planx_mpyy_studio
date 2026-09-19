"""Compile the Ministry's MPYY XSD set into the plugin's schema catalog.

    py -3 tools/compile_mpyy_schema.py <planGMLShema_1_7.zip>

Source: https://eplan.csb.gov.tr/e-plan/doc/planGMLShema_1_7.zip
(linked from the e-Plan "GML Veri Kontrolü" page). Only the derived structure is
written to ``styles/mpyy_schema.json``; the XSD files are not redistributed.

Every table, field, type, requiredness and code list below is read from the
XSD. Feature types are exactly the members of ``plan:features`` (what a
MPYY FeatureCollection may contain); inherited elements are flattened in
schema order, base type first.
"""

import hashlib
import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

XS = "{http://www.w3.org/2001/XMLSchema}"
LEVELS = {"UIP": "uip.V.1.1.7.xsd", "NIP": "nip.V.1.1.7.xsd", "CDP": "cdp.V.1.1.7.xsd"}
GEOMETRY = {
    "gml:MultiPolygonPropertyType": "MultiPolygon",
    "gml:PolygonPropertyType": "Polygon",
    "gml:LineStringPropertyType": "LineString",
    "gml:MultiLineStringPropertyType": "MultiLineString",
    "gml:PointPropertyType": "Point",
    "gml:MultiPointPropertyType": "MultiPoint",
}
# M series: schemas that also carry the pre-2014 (mülga regulation) legend vocabulary and a YeniKod field.
# Compiled separately; used to read such GML files, not to author new plans.
M_LEVELS = {"MUIP": "muip.V.1.1.6.xsd", "MNIP": "mnip.V.1.1.6.xsd", "MCDP25": "mcdp25.V.1.1.6.xsd", "MCDP100": "mcdp100.V.1.1.6.xsd"}
M_OUT = Path(__file__).resolve().parents[1] / "styles" / "mpyy_m_schema.json"
SCALAR = {"xs:string": "string", "xs:double": "double", "xs:int": "int", "xs:long": "long", "xs:dateTime": "dateTime"}
OUT = Path(__file__).resolve().parents[1] / "styles" / "mpyy_schema.json"


def compile_level(data):
    root = ET.fromstring(data)
    complex_types = {c.get("name"): c for c in root.findall(XS + "complexType")}
    enums = {
        s.get("name"): [e.get("value") for e in s.iter(XS + "enumeration")]
        for s in root.findall(XS + "simpleType")
    }

    def own_elements(name):
        node = complex_types[name]
        extension = node.find(f"{XS}complexContent/{XS}extension")
        base = extension.get("base", "") if extension is not None else ""
        elements = (extension if extension is not None else node).findall(f"{XS}sequence/{XS}element")
        return base, elements

    def flatten(name):
        base, elements = own_elements(name)
        inherited = flatten(base.split(":", 1)[1]) if base.startswith("plan:") else []
        return inherited + elements

    members = complex_types["features"].findall(f"{XS}choice/{XS}element")
    feature_types, undefined = [], []
    for member in members:
        type_name = member.get("type").split(":", 1)[1]
        if type_name not in complex_types:
            # Listed as a collection member but never defined in this XSD; the
            # official validator cannot accept it either, so no table is made.
            undefined.append(member.get("name"))
            continue
        geometry, fields = None, []
        for element in flatten(type_name):
            name, xsd_type = element.get("name"), element.get("type")
            if xsd_type in GEOMETRY:
                geometry = GEOMETRY[xsd_type]
                continue
            if xsd_type in SCALAR:
                field = {"name": name, "type": SCALAR[xsd_type]}
            elif xsd_type.startswith("plan:") and xsd_type[5:] in enums:
                field = {"name": name, "type": "enum", "codelist": xsd_type[5:]}
            else:
                raise SystemExit(f"{type_name}.{name}: unsupported type {xsd_type}")
            field["required"] = element.get("minOccurs", "1") != "0"
            fields.append(field)
        feature_types.append({"name": member.get("name"), "geometry": geometry, "fields": fields})
    used = {f["codelist"] for t in feature_types for f in t["fields"] if f["type"] == "enum"}
    return {
        "target_namespace": root.get("targetNamespace"),
        "feature_types": feature_types,
        "undefined_members": undefined,
        "codelists": {name: enums[name] for name in sorted(used)},
    }


def build(archive_path, levels, out):
    raw = Path(archive_path).read_bytes()
    archive = zipfile.ZipFile(io.BytesIO(raw))
    catalog = {
        "version": 1,
        "source": {
            "file": Path(archive_path).name,
            "url": "https://eplan.csb.gov.tr/e-plan/doc/planGMLShema_1_7.zip",
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "levels": {},
    }
    for level, member in levels.items():
        data = archive.read(member)
        compiled = compile_level(data)
        compiled["xsd"] = {"file": member, "sha256": hashlib.sha256(data).hexdigest()}
        catalog["levels"][level] = compiled
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    for level, compiled in catalog["levels"].items():
        types = compiled["feature_types"]
        print(level, len(types), "types", sum(1 for t in types if t["geometry"] is None), "without geometry",
              len(compiled["codelists"]), "codelists", "undefined:", compiled["undefined_members"])


def main(archive_path):
    build(archive_path, LEVELS, OUT)
    build(archive_path, M_LEVELS, M_OUT)


if __name__ == "__main__":
    main(sys.argv[1])
