"""Kaynak MPYY GeoPackage içindeki tüm UİP katalog satırlarını JSON'a derle."""

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3


def compile_catalog(source: Path, output: Path):
    rows = []
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as con:
        for table, geometry in (
            ("uipPolygonTable", "POLYGON"),
            ("uipLineTable", "LINE"),
        ):
            for row in con.execute(
                f'SELECT fid,id1,ust_konu_grup,id2,uip_fonksiyon,id3,uip_tabaka FROM "{table}" ORDER BY fid'
            ):
                rows.append(
                    dict(
                        zip(
                            (
                                "source_fid",
                                "ust_grup_kodu",
                                "ust_grup_adi",
                                "fonksiyon_kodu",
                                "fonksiyon_adi",
                                "detay_kodu",
                                "tabaka_adi",
                            ),
                            row,
                        )
                    )
                    | {"geometry_type": geometry}
                )
    payload = {
        "version": 1,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "rows": rows,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(compile_catalog(args.source, args.output))
