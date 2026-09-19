"""Yerel kaynak GeoPackage'lerden gömülü QML tanımlarını yeniden üret."""

import argparse
from pathlib import Path
import sqlite3


def extract(source, output):
    output.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as con:
        rows = con.execute(
            "SELECT id,f_table_name,styleQML FROM layer_styles ORDER BY id"
        )
        for style_id, table, qml in rows:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in table)
            # newline="\n": the repo is committed as LF (.gitattributes, * text=auto eol=lf),
            # so a CRLF worktree file would only show up as a phantom modification.
            (output / f"{style_id:02d}_{safe}.qml").write_text(qml, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    extract(args.source, args.output)
