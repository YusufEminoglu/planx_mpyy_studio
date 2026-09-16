"""Reproduce exact UIP mappings from a local source DB and XML; no fuzzy guesses."""

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from defusedxml import ElementTree as ET


def normalized(value: str) -> str:
    return value.strip().translate(str.maketrans("iı", "İI")).upper()


def compile_mappings(database: Path, source: Path, output: Path) -> dict:
    raw = source.read_bytes()
    if b"<!ENTITY" in raw.upper() or b"SYSTEM" in raw.upper():
        raise ValueError("External XML entities are not supported")
    root = ET.fromstring(raw)
    symbols, exact_symbols = {}, {}
    for symbol in root.findall("./symbols/symbol"):
        key = (normalized(symbol.get("name", "")), symbol.get("type"))
        symbols.setdefault(key, []).append(symbol.get("name"))
        exact_key = (symbol.get("name"), symbol.get("type"))
        if exact_key in exact_symbols:
            raise ValueError("Duplicate exact symbol identity: " + str(exact_key))
        exact_symbols[exact_key] = symbol.get("name")
    aliases = {"HAVAALANI HAVA KORİDORU": "HAVA ALANI HAVA KORİDORU"}
    entries, omissions = [], []
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    ) as con:
        for query, geometry, symbol_type in (
            (
                "SELECT id2,uip_fonksiyon,uip_tabaka FROM uipPolygonTable",
                "POLYGON",
                "fill",
            ),
            ("SELECT id2,uip_fonksiyon,uip_tabaka FROM uipLineTable", "LINE", "line"),
        ):
            rows = con.execute(query).fetchall()
            counts = Counter(str(row[0]) for row in rows)
            for code, name, tabaka in rows:
                code = str(code)
                target_name = aliases.get(name, name)
                symbol = exact_symbols.get((target_name, symbol_type))
                if symbol is None:
                    candidates = symbols.get((normalized(target_name), symbol_type), [])
                    symbol = candidates[0] if len(candidates) == 1 else None
                if counts[code] != 1 or symbol is None:
                    omissions.append(
                        {
                            "code": code,
                            "function": name,
                            "geometry_type": geometry,
                            "reason": "ambiguous code"
                            if counts[code] != 1
                            else "no matching geometry symbol",
                        }
                    )
                    continue
                entries.append(
                    {
                        "plan_level": "UIP",
                        "geometry_type": geometry,
                        "code": code,
                        "symbol": symbol,
                    }
                )
    result = {
        "version": 1,
        "entries": sorted(
            entries, key=lambda item: (item["geometry_type"], item["code"])
        ),
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "entries": len(entries),
        "omissions": omissions,
        "xml_sha256": hashlib.sha256(raw).hexdigest(),
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "normalized_name_collisions": [
            names for names in symbols.values() if len(names) > 1
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("xml", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            compile_mappings(args.database, args.xml, args.output), ensure_ascii=True
        )
    )
