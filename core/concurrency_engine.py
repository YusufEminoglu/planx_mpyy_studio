"""GeoPackage WAL setup and conservative two-workspace reconciliation."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any


_SQL_ADD_UUID = "ALTER TABLE __TABLE__ ADD COLUMN uuid_version TEXT"
_SQL_ADD_TIMESTAMP = "ALTER TABLE __TABLE__ ADD COLUMN last_modified_timestamp TEXT"
_SQL_SELECT_UNTRACKED = (
    "SELECT rowid FROM __TABLE__ "
    "WHERE uuid_version IS NULL OR last_modified_timestamp IS NULL"
)
_SQL_UPDATE_TRACKING = (
    "UPDATE __TABLE__ SET uuid_version=COALESCE(uuid_version, ?), "
    "last_modified_timestamp=COALESCE(last_modified_timestamp, ?) WHERE rowid=?"
)
_SQL_SELECT_COLUMNS = "SELECT __COLUMNS__ FROM __TABLE__"
_SQL_SELECT_ROW = "SELECT __COLUMNS__ FROM __TABLE__ WHERE __PRIMARY_KEY__=?"
_SQL_INSERT_ROW = "INSERT INTO __TABLE__ (__COLUMNS__) VALUES (__PLACEHOLDERS__)"
_SQL_UPDATE_ROW = "UPDATE __TABLE__ SET __ASSIGNMENTS__ WHERE __PRIMARY_KEY__=?"
_SQL_TRACKING_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS "__TRIGGER__" AFTER UPDATE ON "__TABLE_NAME__"
WHEN NEW.uuid_version = OLD.uuid_version
BEGIN
    UPDATE "__TABLE_NAME__"
    SET uuid_version = lower(hex(randomblob(16))),
        last_modified_timestamp = strftime('%Y-%m-%dT%H:%M:%fZ','now')
    WHERE rowid = NEW.rowid;
END;
"""
_SQL_INSERT_TRACKING_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS "__TRIGGER__" AFTER INSERT ON "__TABLE_NAME__"
WHEN NEW.uuid_version IS NULL OR NEW.last_modified_timestamp IS NULL
BEGIN
    UPDATE "__TABLE_NAME__"
    SET uuid_version = COALESCE(NEW.uuid_version, lower(hex(randomblob(16)))),
        last_modified_timestamp = COALESCE(
            NEW.last_modified_timestamp,
            strftime('%Y-%m-%dT%H:%M:%fZ','now')
        )
    WHERE rowid = NEW.rowid;
END;
"""


@dataclass
class ReconciliationConflict:
    table_name: str
    feature_key: str
    target_hash: str
    incoming_hash: str
    reason: str
    resolution: str = "UNRESOLVED"


@dataclass
class ReconciliationResult:
    output_path: str
    tables_processed: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    identical_rows: int = 0
    conflicts: list[ReconciliationConflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    schema_mismatches: list[str] = field(default_factory=list)


@dataclass
class ReconciliationPreview:
    base_path: str
    incoming_path: str
    tables_processed: int = 0
    incoming_only_rows: int = 0
    identical_rows: int = 0
    divergent_rows: int = 0
    schema_mismatches: list[str] = field(default_factory=list)
    incoming_only_tables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    table_summaries: dict[str, dict[str, int]] = field(default_factory=dict)


class GeoPackageConcurrencyEngine:
    """Adds revision metadata and reconciles incoming rows without overwrites."""

    TRACKING_COLUMNS = ("uuid_version", "last_modified_timestamp")

    @classmethod
    def enable_wal(cls, workspace_path: str | Path) -> str:
        path = cls._validate_workspace(workspace_path)
        with closing(sqlite3.connect(path, timeout=5.0)) as connection:
            mode = str(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]).upper()
            connection.execute("PRAGMA busy_timeout=5000")
            connection.commit()
        return mode

    @classmethod
    def prepare_workspace(cls, workspace_path: str | Path) -> list[str]:
        path = cls._validate_workspace(workspace_path)
        prepared: list[str] = []
        with closing(sqlite3.connect(path, timeout=5.0)) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")
            for table in cls._content_tables(connection):
                if not cls._is_table(connection, table):
                    continue
                columns = cls._columns(connection, table)
                quoted = cls._quote(table)
                if "uuid_version" not in columns:
                    connection.execute(_SQL_ADD_UUID.replace("__TABLE__", quoted))
                if "last_modified_timestamp" not in columns:
                    connection.execute(_SQL_ADD_TIMESTAMP.replace("__TABLE__", quoted))
                now = cls._utc_now()
                rows = connection.execute(
                    _SQL_SELECT_UNTRACKED.replace("__TABLE__", quoted)
                ).fetchall()
                for (rowid,) in rows:
                    connection.execute(
                        _SQL_UPDATE_TRACKING.replace("__TABLE__", quoted),
                        (str(uuid.uuid4()), now, rowid),
                    )
                cls._install_tracking_triggers(connection, table)
                prepared.append(table)
        return prepared

    @classmethod
    def preview_workspaces(
        cls, base_workspace: str | Path, incoming_workspace: str | Path
    ) -> ReconciliationPreview:
        """Compare two workspaces read-only and return the prospective merge impact."""
        base = cls._validate_workspace(base_workspace)
        incoming = cls._validate_workspace(incoming_workspace)
        preview = ReconciliationPreview(str(base), str(incoming))
        with closing(sqlite3.connect(base, timeout=5.0)) as target, closing(
            sqlite3.connect(incoming, timeout=5.0)
        ) as source:
            target_tables = set(cls._content_tables(target))
            source_tables = set(cls._content_tables(source))
            preview.incoming_only_tables = sorted(source_tables - target_tables)
            for table in preview.incoming_only_tables:
                preview.warnings.append("INCOMING_ONLY_TABLE:" + table)
            for table in sorted(target_tables & source_tables):
                if not cls._is_table(target, table) or not cls._is_table(source, table):
                    continue
                source_columns = cls._columns(source, table)
                target_columns = cls._columns(target, table)
                source_domain = set(source_columns) - set(cls.TRACKING_COLUMNS)
                target_domain = set(target_columns) - set(cls.TRACKING_COLUMNS)
                if source_domain != target_domain:
                    preview.schema_mismatches.append(table)
                    preview.warnings.append("SCHEMA_MISMATCH:" + table)
                common_columns = [column for column in source_columns if column in target_columns]
                primary_key = cls._primary_key(source, table)
                if not primary_key or primary_key not in common_columns:
                    preview.warnings.append("NO_PRIMARY_KEY:" + table)
                    continue
                summary = cls._preview_table(
                    target, source, table, primary_key, common_columns
                )
                preview.table_summaries[table] = summary
                preview.incoming_only_rows += summary["incoming_only_rows"]
                preview.identical_rows += summary["identical_rows"]
                preview.divergent_rows += summary["divergent_rows"]
                preview.tables_processed += 1
        return preview

    @classmethod
    def write_preview_report(
        cls, preview: ReconciliationPreview, output_path: str | Path
    ) -> str:
        output = Path(output_path).resolve()
        if output.suffix.lower() != ".json":
            raise ValueError('Uzlaştırma önizleme raporu .json uzantısını kullanmalıdır.')
        if output.exists():
            raise FileExistsError(str(output))
        output.parent.mkdir(parents=True, exist_ok=True)
        core_payload = {
            "base_path": preview.base_path,
            "incoming_path": preview.incoming_path,
            "tables_processed": preview.tables_processed,
            "incoming_only_rows": preview.incoming_only_rows,
            "identical_rows": preview.identical_rows,
            "divergent_rows": preview.divergent_rows,
            "schema_mismatches": preview.schema_mismatches,
            "incoming_only_tables": preview.incoming_only_tables,
            "warnings": preview.warnings,
            "table_summaries": preview.table_summaries,
        }
        canonical = json.dumps(core_payload, ensure_ascii=True, sort_keys=True)
        report = dict(core_payload)
        report["schema_version"] = 1
        report["generated_at"] = cls._utc_now()
        report["content_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        temporary = output.with_name(' satır bulundu.' + output.name + ' satır bulundu.' + uuid.uuid4().hex + ".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(output)
        return str(output)

    @classmethod
    def reconcile_workspaces(
        cls,
        base_workspace: str | Path,
        incoming_workspace: str | Path,
        output_workspace: str | Path,
        conflict_strategy: str = "MANUAL",
    ) -> ReconciliationResult:
        base = cls._validate_workspace(base_workspace)
        incoming = cls._validate_workspace(incoming_workspace)
        output = Path(output_workspace).resolve()
        if output.suffix.lower() != ".gpkg":
            raise ValueError('Uzlaştırma çıktısı .gpkg uzantısını kullanmalıdır.')
        if output.exists():
            raise FileExistsError(str(output))
        if output in (base, incoming):
            raise ValueError('Çıktı çalışma alanı iki girdiden de farklı olmalıdır.')
        strategy = str(conflict_strategy or "MANUAL").strip().upper()
        if strategy not in {"MANUAL", "PREFER_INCOMING", "PREFER_NEWER"}:
            raise ValueError('Bilinmeyen çakışma yöntemi: ' + str(conflict_strategy))
        output.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(base, timeout=5.0)) as source_database, closing(
            sqlite3.connect(output, timeout=5.0)
        ) as destination_database:
            source_database.backup(destination_database)
        result = ReconciliationResult(str(output))

        try:
            cls.prepare_workspace(output)
            with closing(sqlite3.connect(output, timeout=5.0)) as target, closing(
                sqlite3.connect(incoming, timeout=5.0)
            ) as source, target:
                target.execute("PRAGMA busy_timeout=5000")
                cls._ensure_conflict_table(target)
                shared = sorted(set(cls._content_tables(target)) & set(cls._content_tables(source)))
                for table in shared:
                    if not cls._is_table(target, table) or not cls._is_table(source, table):
                        continue
                    source_columns = cls._columns(source, table)
                    target_columns = cls._columns(target, table)
                    source_domain = set(source_columns) - set(cls.TRACKING_COLUMNS)
                    target_domain = set(target_columns) - set(cls.TRACKING_COLUMNS)
                    if source_domain != target_domain:
                        result.schema_mismatches.append(table)
                        result.warnings.append("SCHEMA_MISMATCH:" + table)
                    common_columns = [column for column in source_columns if column in target_columns]
                    primary_key = cls._primary_key(source, table)
                    if not primary_key or primary_key not in common_columns:
                        result.warnings.append("NO_PRIMARY_KEY:" + table)
                        continue
                    cls._reconcile_table(
                        target, source, table, primary_key, common_columns, result, strategy
                    )
                    result.tables_processed += 1
            cls.prepare_workspace(output)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        return result

    @classmethod
    def _reconcile_table(cls, target, source, table, primary_key, columns, result, strategy):
        quoted_table = cls._quote(table)
        quoted_pk = cls._quote(primary_key)
        column_sql = ", ".join(cls._quote(column) for column in columns)
        select_all = _SQL_SELECT_COLUMNS.replace("__COLUMNS__", column_sql).replace("__TABLE__", quoted_table)
        incoming_rows = source.execute(select_all).fetchall()
        for incoming_row in incoming_rows:
            incoming_values = dict(zip(columns, incoming_row))
            key = incoming_values[primary_key]
            select_row = (
                _SQL_SELECT_ROW.replace("__COLUMNS__", column_sql)
                .replace("__TABLE__", quoted_table)
                .replace("__PRIMARY_KEY__", quoted_pk)
            )
            target_row = target.execute(select_row, (key,)).fetchone()
            if target_row is None:
                placeholders = ",".join("?" for _ in columns)
                insert_row = (
                    _SQL_INSERT_ROW.replace("__TABLE__", quoted_table)
                    .replace("__COLUMNS__", column_sql)
                    .replace("__PLACEHOLDERS__", placeholders)
                )
                target.execute(insert_row, incoming_row)
                result.inserted_rows += 1
                continue

            target_values = dict(zip(columns, target_row))
            target_hash = cls._row_hash(target_values)
            incoming_hash = cls._row_hash(incoming_values)
            if target_hash == incoming_hash:
                result.identical_rows += 1
                continue

            resolution = cls._resolution_for(strategy, target_values, incoming_values)
            if resolution != "UNRESOLVED":
                update_columns = [column for column in columns if column != primary_key]
                assignments = ", ".join(cls._quote(column) + "=?" for column in update_columns)
                update_sql = (
                    _SQL_UPDATE_ROW.replace("__TABLE__", quoted_table)
                    .replace("__ASSIGNMENTS__", assignments)
                    .replace("__PRIMARY_KEY__", quoted_pk)
                )
                target.execute(
                    update_sql,
                    tuple(incoming_values[column] for column in update_columns) + (key,),
                )
                result.updated_rows += 1

            conflict = ReconciliationConflict(
                table_name=table,
                feature_key=str(key),
                target_hash=target_hash,
                incoming_hash=incoming_hash,
                reason="SAME_PRIMARY_KEY_DIVERGED",
                resolution=resolution,
            )
            if resolution == "UNRESOLVED":
                result.conflicts.append(conflict)
            target.execute(
                "INSERT INTO _reconciliation_conflicts "
                "(table_name, feature_key, target_hash, incoming_hash, reason, resolution, detected_at, incoming_payload) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    conflict.table_name,
                    conflict.feature_key,
                    conflict.target_hash,
                    conflict.incoming_hash,
                    conflict.reason,
                    conflict.resolution,
                    cls._utc_now(),
                    cls._json_payload(incoming_values),
                ),
            )

    @classmethod
    def _preview_table(cls, target, source, table, primary_key, columns) -> dict[str, int]:
        quoted_table = cls._quote(table)
        quoted_pk = cls._quote(primary_key)
        column_sql = ", ".join(cls._quote(column) for column in columns)
        select_all = _SQL_SELECT_COLUMNS.replace("__COLUMNS__", column_sql).replace(
            "__TABLE__", quoted_table
        )
        select_row = (
            _SQL_SELECT_ROW.replace("__COLUMNS__", column_sql)
            .replace("__TABLE__", quoted_table)
            .replace("__PRIMARY_KEY__", quoted_pk)
        )
        summary = {"incoming_only_rows": 0, "identical_rows": 0, "divergent_rows": 0}
        for incoming_row in source.execute(select_all):
            incoming_values = dict(zip(columns, incoming_row))
            target_row = target.execute(select_row, (incoming_values[primary_key],)).fetchone()
            if target_row is None:
                summary["incoming_only_rows"] += 1
                continue
            target_values = dict(zip(columns, target_row))
            key = "identical_rows" if cls._row_hash(target_values) == cls._row_hash(incoming_values) else "divergent_rows"
            summary[key] += 1
        return summary

    @classmethod
    def _install_tracking_triggers(cls, connection: sqlite3.Connection, table: str) -> None:
        safe_name = "".join(character if character.isalnum() else "_" for character in table)
        update_trigger = "mpyy_track_update_" + safe_name
        update_sql = (
            _SQL_TRACKING_TRIGGER.replace("__TRIGGER__", update_trigger)
            .replace("__TABLE_NAME__", table.replace('"', '""'))
        )
        insert_trigger = "mpyy_track_insert_" + safe_name
        insert_sql = (
            _SQL_INSERT_TRACKING_TRIGGER.replace("__TRIGGER__", insert_trigger)
            .replace("__TABLE_NAME__", table.replace('"', '""'))
        )
        connection.execute(update_sql)
        connection.execute(insert_sql)

    @staticmethod
    def _ensure_conflict_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS _reconciliation_conflicts (
                conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                target_hash TEXT NOT NULL,
                incoming_hash TEXT NOT NULL,
                reason TEXT NOT NULL,
                resolution TEXT NOT NULL DEFAULT 'UNRESOLVED',
                detected_at TEXT NOT NULL,
                incoming_payload TEXT NOT NULL
            )"""
        )
        columns = {
            str(row[1]) for row in connection.execute(
                "PRAGMA table_info(_reconciliation_conflicts)"
            ).fetchall()
        }
        if "resolution" not in columns:
            connection.execute(
                "ALTER TABLE _reconciliation_conflicts "
                "ADD COLUMN resolution TEXT NOT NULL DEFAULT 'UNRESOLVED'"
            )
        connection.execute(
            "INSERT OR IGNORE INTO gpkg_contents(table_name,data_type,identifier) "
            "VALUES ('_reconciliation_conflicts','attributes','PlanX reconciliation conflicts')"
        )

    @staticmethod
    def _content_tables(connection: sqlite3.Connection) -> list[str]:
        return [
            str(row[0]) for row in connection.execute(
                "SELECT table_name FROM gpkg_contents WHERE data_type IN ('features','attributes')"
            ).fetchall()
            if str(row[0]) != "_reconciliation_conflicts"
        ]

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
        return [str(row[1]) for row in connection.execute("PRAGMA table_info(" + GeoPackageConcurrencyEngine._quote(table) + ")")]

    @staticmethod
    def _primary_key(connection: sqlite3.Connection, table: str) -> str | None:
        rows = connection.execute("PRAGMA table_info(" + GeoPackageConcurrencyEngine._quote(table) + ")").fetchall()
        keys = sorted((int(row[5]), str(row[1])) for row in rows if int(row[5]) > 0)
        return keys[0][1] if keys else None

    @staticmethod
    def _is_table(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _row_hash(values: dict[str, Any]) -> str:
        digest = hashlib.sha256()
        for key in sorted(values):
            if key in GeoPackageConcurrencyEngine.TRACKING_COLUMNS:
                continue
            digest.update(key.encode("utf-8"))
            value = values[key]
            if isinstance(value, bytes):
                digest.update(value)
            else:
                digest.update(repr(value).encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _resolution_for(strategy: str, target_values: dict, incoming_values: dict) -> str:
        if strategy == "PREFER_INCOMING":
            return "INCOMING_APPLIED"
        if strategy != "PREFER_NEWER":
            return "UNRESOLVED"
        target_time = GeoPackageConcurrencyEngine._parse_timestamp(
            target_values.get("last_modified_timestamp")
        )
        incoming_time = GeoPackageConcurrencyEngine._parse_timestamp(
            incoming_values.get("last_modified_timestamp")
        )
        if target_time is not None and incoming_time is not None and incoming_time > target_time:
            return "NEWER_INCOMING_APPLIED"
        return "UNRESOLVED"

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _json_payload(values: dict[str, Any]) -> str:
        serializable = {
            key: ("<binary>" if isinstance(value, bytes) else value)
            for key, value in values.items()
        }
        return json.dumps(serializable, ensure_ascii=True, default=str, sort_keys=True)

    @staticmethod
    def _quote(identifier: str) -> str:
        return '"' + str(identifier).replace('"', '""') + '"'

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    @staticmethod
    def _validate_workspace(workspace_path: str | Path) -> Path:
        path = Path(workspace_path).resolve()
        if path.suffix.lower() != ".gpkg" or not path.is_file():
            raise FileNotFoundError(str(path))
        return path
