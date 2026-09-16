"""Normalize an administration-supplied CSV dictionary using explicit column mappings."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping
import uuid

from .profile_identity import profile_content_hash, read_profile_json


class MPYYSchemaProfileImportEngine:
    @classmethod
    def convert(cls, source_path: str | Path, mapping: Mapping[str, Any]) -> dict[str, Any]:
        metadata = {}
        for key in ("profile_id", "profile_version", "source_institution", "source_reference"):
            value = mapping.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Import mapping requires a non-empty string: " + key)
            metadata[key] = value.strip()
        columns = mapping.get("columns")
        if not isinstance(columns, Mapping) or any(
            not isinstance(columns.get(key), str) or not columns[key].strip()
            for key in ("table", "field", "type")
        ):
            raise ValueError('Tablo, alan ve tür sütunları için açık eşleme gereklidir.')
        allowed = {"table", "field", "type", "not_null", "primary_key", "geometry_type", "srs_id"}
        if set(columns) - allowed or any(
            not isinstance(value, str) or not value.strip() for value in columns.values()
        ):
            raise ValueError("Column mappings contain an unsupported or empty entry.")
        delimiter = mapping.get("delimiter", ",")
        if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in "\r\n\x00":
            raise ValueError('CSV ayırıcı tek bir yazdırılabilir karakter olmalıdır.')
        data = Path(source_path).read_bytes()
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), delimiter=delimiter)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)) or not set(columns.values()).issubset(headers):
                raise ValueError('CSV başlıkları yinelenmiş veya eşlenen sütunlar eksik.')
            tables = {}
            seen = set()
            row_count = 0
            for row_count, row in enumerate(reader, start=1):
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("CSV row has the wrong number of columns: " + str(row_count))
                values = {key: row[column].strip() for key, column in columns.items()}
                table, name, field_type = values["table"], values["field"], values["type"].upper()
                if not table or not name or not field_type:
                    raise ValueError("Table, field and type cannot be empty at row " + str(row_count))
                if (table, name) in seen:
                    raise ValueError("Duplicate dictionary field: " + table + ' satır bulundu.' + name)
                seen.add((table, name))
                definition = tables.setdefault(table, {"name": table, "fields": []})
                field = {"name": name, "type": field_type}
                for key in ("not_null", "primary_key"):
                    if values.get(key, ""):
                        text = values[key].lower()
                        if text not in {"true", "false", "1", "0", "yes", "no"}:
                            raise ValueError('Geçersiz mantıksal değer: ' + table + ' satır bulundu.' + name + ": " + key)
                        field[key] = text in {"true", "1", "yes"}
                definition["fields"].append(field)
                for key in ("geometry_type", "srs_id"):
                    if not values.get(key, ""):
                        continue
                    value = values[key].upper() if key == "geometry_type" else int(values[key])
                    if key in definition and definition[key] != value:
                        raise ValueError("Conflicting table geometry declaration: " + table)
                    definition[key] = value
            if not row_count:
                raise ValueError('CSV sözlüğü en az bir alan içermelidir.')
        except (UnicodeError, csv.Error) as error:
            raise ValueError('CSV sözlüğü okunabilir UTF-8 olmalıdır: ' + str(error)) from error
        profile = {
            **metadata,
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "import_mapping": dict(mapping),
            "tables": [
                {**tables[name], "fields": sorted(tables[name]["fields"], key=lambda item: item["name"])}
                for name in sorted(tables)
            ],
        }
        profile["content_sha256"] = profile_content_hash(profile)
        return profile

    @classmethod
    def convert_files(cls, source_path: str | Path, mapping_path: str | Path) -> dict[str, Any]:
        mapping = read_profile_json(mapping_path)
        return cls.convert(source_path, mapping)

    @staticmethod
    def write(profile: Mapping[str, Any], output_path: str | Path) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return str(path)
