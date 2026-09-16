"""Atomic, isolated GeoPackage generators for PlanGML and Arazi Kullanımı."""

import json
import os
from pathlib import Path
import sqlite3
import uuid
import contextlib
from contextlib import closing
from osgeo import gdal, ogr, osr
from qgis.core import QgsCoordinateReferenceSystem

gdal.UseExceptions()

from .schema import (
    LAND_TABLES,
    LAND_USE_CLASSES,
    PLAN_LEVEL_CODES,
    PLAN_LEVELS,
    SAHA_CATI_KODLARI,
    SAHA_HASAR_KODLARI,
    SAHA_ISITMA_KODLARI,
    SAHA_NIZAM_KODLARI,
    SAHA_PARSEL_DURUM_KODLARI,
    SAHA_YAPI_CINS_KODLARI,
    SCHEMA_VERSION,
    planning_tables,
    selected_tables,
)


def _crs(value):
    crs = value if isinstance(value, QgsCoordinateReferenceSystem) else QgsCoordinateReferenceSystem(str(value))
    if not crs.isValid():
        raise ValueError('Geçerli bir KRS gereklidir')
    srs = osr.SpatialReference()
    if srs.SetFromUserInput(crs.authid() or crs.toWkt()) != 0:
        raise ValueError("GDAL seçilen KRS'yi okuyamıyor")
    return srs


def _quote(name: str) -> str:
    cleaned = name.replace('"', '').replace("'", "")
    return f'"{cleaned}"'


def _msp_rows():
    path = Path(__file__).resolve().parents[1] / "styles" / "msp_catalog.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("rows", [])
    return []


def _uip_lookups():
    path = Path(__file__).resolve().parents[1] / "styles" / "uip_lookup_tables.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"polygon_functions": [], "line_functions": []}


def _nip_entries():
    path = Path(__file__).resolve().parents[1] / "styles" / "nip_catalog.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    return []


def _cdp_entries():
    path = Path(__file__).resolve().parents[1] / "styles" / "cdp_catalog.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    return []


def _mpyy_2026_symbols():
    path = Path(__file__).resolve().parents[1] / "resources" / "mpyy_2026_additions.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("symbols", [])
    return []


def _read_qml(rel_path: str) -> str:
    path = Path(__file__).resolve().parents[1] / rel_path
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


_SQL_AUDIT_INSERT = """
CREATE TRIGGER "__TRG__" AFTER INSERT ON "__TBL__"
WHEN NEW.olusturma_tarihi = '' OR NEW.olusturma_tarihi IS NULL
BEGIN
    UPDATE "__TBL__"
    SET olusturma_tarihi = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
        guncelleme_tarihi = strftime('%Y-%m-%dT%H:%M:%fZ','now')
    WHERE fid = NEW.fid;
END;
"""

_SQL_AUDIT_UPDATE = """
CREATE TRIGGER "__TRG__" AFTER UPDATE OF geom ON "__TBL__"
WHEN NEW.guncelleme_tarihi = OLD.guncelleme_tarihi OR NEW.guncelleme_tarihi IS NULL
BEGIN
    UPDATE "__TBL__"
    SET guncelleme_tarihi = strftime('%Y-%m-%dT%H:%M:%fZ','now')
    WHERE fid = NEW.fid;
END;
"""


def _create_audit_triggers(con: sqlite3.Connection, table: str, fields: dict) -> None:
    if "olusturma_tarihi" in fields:
        trg_name = f"audit_insert_{table}"
        sql_ins = _SQL_AUDIT_INSERT.replace("__TRG__", trg_name).replace("__TBL__", table)
        con.execute(sql_ins)
    if "guncelleme_tarihi" in fields:
        trg_name = f"audit_update_{table}"
        sql_upd = _SQL_AUDIT_UPDATE.replace("__TRG__", trg_name).replace("__TBL__", table)
        con.execute(sql_upd)


_SQL_SURVEY_INSERT = """
CREATE TRIGGER "__TRG__" AFTER INSERT ON "__TBL__"
BEGIN
    UPDATE "__TBL__"
    SET global_id = CASE WHEN NEW.global_id = '' OR NEW.global_id IS NULL
            THEN lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || substr(hex(randomblob(2)), 2) || '-a' || substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6)))
            ELSE NEW.global_id END,
        tarih = CASE WHEN NEW.tarih = '' OR NEW.tarih IS NULL
            THEN strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
            ELSE NEW.tarih END
    WHERE fid = NEW.fid;
END;
"""

_SQL_SURVEY_UPDATE = """
CREATE TRIGGER "__TRG__" AFTER UPDATE OF geom ON "__TBL__"
WHEN NEW.tarih = OLD.tarih OR NEW.tarih IS NULL
BEGIN
    UPDATE "__TBL__"
    SET tarih = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
    WHERE fid = NEW.fid;
END;
"""


def _create_survey_audit_triggers(con: sqlite3.Connection, table: str, fields: dict) -> None:
    if "global_id" in fields and "tarih" in fields:
        trg_ins = f"survey_insert_{table}"
        sql_ins = _SQL_SURVEY_INSERT.replace("__TRG__", trg_ins).replace("__TBL__", table)
        con.execute(sql_ins)
    if "tarih" in fields:
        trg_upd = f"survey_update_{table}"
        sql_upd = _SQL_SURVEY_UPDATE.replace("__TRG__", trg_upd).replace("__TBL__", table)
        con.execute(sql_upd)


def _create(output_path, crs, tables, kind, levels=()):
    output = Path(output_path).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    if output.suffix.lower() != ".gpkg":
        raise ValueError('Çıktı .gpkg uzantısını kullanmalıdır')

    geometry_types = {
        "MultiPolygon": ogr.wkbMultiPolygon,
        "MultiLineString": ogr.wkbMultiLineString,
        "Point": ogr.wkbPoint,
    }

    staging = output.parent / (".mpyy-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / "dataset.gpkg"

    try:
        ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(staged))
        if ds is None:
            raise RuntimeError('GeoPackage oluşturulamadı')

        srs = _crs(crs)
        for table, (geom_type, _) in tables.items():
            layer = ds.CreateLayer(
                table,
                srs,
                geometry_types[geom_type],
                options=["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES"],
            )
            if layer is None:
                raise RuntimeError('Katman oluşturulamadı: ' + table)
        ds = None

        with closing(sqlite3.connect(staged)) as con, con:
            con.execute("PRAGMA foreign_keys=ON")

            # 1. Metadata table
            con.execute(
                "CREATE TABLE mpyy_metadata (dataset_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, workspace_kind TEXT NOT NULL, plan_levels TEXT NOT NULL)"
            )
            con.execute(
                "INSERT INTO mpyy_metadata VALUES (?,?,?,?)",
                (str(uuid.uuid4()), SCHEMA_VERSION, kind, ",".join(levels)),
            )

            # 2. Layer styles table (OGC GPKG standard style table)
            con.execute(
                """CREATE TABLE IF NOT EXISTS layer_styles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    f_table_catalog TEXT,
                    f_table_schema TEXT,
                    f_table_name TEXT NOT NULL,
                    f_geometry_column TEXT,
                    styleName TEXT NOT NULL,
                    styleQML TEXT,
                    styleSLD TEXT,
                    useAsDefault BOOLEAN,
                    description TEXT,
                    owner TEXT,
                    ui TEXT,
                    update_time DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )"""
            )
            con.execute(
                "INSERT OR IGNORE INTO gpkg_contents(table_name,data_type,identifier) VALUES ('layer_styles','attributes','QGIS katman stilleri')"
            )

            # 3. If Planning workspace, add catalogs & lookups
            if kind == "PLANLAMA":
                con.execute(
                    """CREATE TABLE mpyy_2026_gosterim_katalogu (
                        symbol_code TEXT PRIMARY KEY,
                        symbol_name TEXT NOT NULL,
                        applicable_levels TEXT NOT NULL,
                        effective_date TEXT NOT NULL,
                        official_gazette_number TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) "
                    "VALUES ('mpyy_2026_gosterim_katalogu','attributes','MPYY 2026 supplemental display catalog')"
                )
                symbol_rows = [
                    (
                        row.get("code", ""),
                        row.get("name", ""),
                        ",".join(row.get("levels", [])),
                        "2026-01-22",
                        "33145",
                    )
                    for row in _mpyy_2026_symbols()
                    if row.get("code") and set(row.get("levels", [])) & set(levels)
                ]
                con.executemany(
                    "INSERT INTO mpyy_2026_gosterim_katalogu VALUES (?,?,?,?,?)", symbol_rows
                )

                # MSP Catalog
                if "MSP" in levels:
                    con.execute(
                        """CREATE TABLE mpyy_msp_katalogu (
                            msp_catalog_id TEXT PRIMARY KEY,
                            detay_sinifi TEXT NOT NULL,
                            detay_alt_sinifi TEXT,
                            gosterim TEXT,
                            geometri TEXT NOT NULL,
                            tarama_rgb TEXT,
                            tarama_alpha INTEGER,
                            sinir_rgb TEXT,
                            stroke_width_mm REAL,
                            stroke_desc TEXT,
                            hatch_desc TEXT,
                            source_pdf_page INTEGER NOT NULL
                        )"""
                    )
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('mpyy_msp_katalogu','attributes','MSP Annex 1e detail catalog')"
                    )
                    msp_data = [
                        (
                            r["id"],
                            r["detay_adi"],
                            r.get("detay_alt_sinifi", ""),
                            r.get("gosterim", ""),
                            r.get("geometri", "POLYGON"),
                            r.get("tarama_rgb"),
                            r.get("tarama_alpha", 255),
                            r.get("sinir_rgb"),
                            float(r.get("stroke_width_mm") or 0.3),
                            r.get("stroke_desc", ""),
                            r.get("hatch_desc", ""),
                            int(r.get("page", 1)),
                        )
                        for r in _msp_rows()
                    ]
                    con.executemany("INSERT INTO mpyy_msp_katalogu VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", msp_data)

                # CDP Catalog
                if "CDP" in levels:
                    con.execute(
                        """CREATE TABLE mpyy_cdp_katalogu (
                            layer_code TEXT PRIMARY KEY,
                            tanim TEXT NOT NULL,
                            kural_sayisi INTEGER NOT NULL
                        )"""
                    )
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('mpyy_cdp_katalogu','attributes','CDP E-Plan detail catalog')"
                    )
                    cdp_rows = [
                        (e.get("layer_code", ""), e.get("layer_code", "").replace("_", " ").title(), len(e.get("rules", [])))
                        for e in _cdp_entries() if e.get("layer_code")
                    ]
                    con.executemany("INSERT OR IGNORE INTO mpyy_cdp_katalogu VALUES (?,?,?)", cdp_rows)

                # NIP Catalog
                if "NIP" in levels:
                    con.execute(
                        """CREATE TABLE mpyy_nip_katalogu (
                            layer_code TEXT PRIMARY KEY,
                            tanim TEXT NOT NULL,
                            is_notation BOOLEAN NOT NULL,
                            kural_sayisi INTEGER NOT NULL
                        )"""
                    )
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('mpyy_nip_katalogu','attributes','NIP E-Plan and MNIP detail catalog')"
                    )
                    nip_rows = [
                        (e.get("layer_code", ""), e.get("layer_code", "").replace("_", " ").title(), bool(e.get("is_notation")), len(e.get("rules", [])))
                        for e in _nip_entries() if e.get("layer_code")
                    ]
                    con.executemany("INSERT OR IGNORE INTO mpyy_nip_katalogu VALUES (?,?,?,?)", nip_rows)

                # If UIP is selected, create uipPolygonTable and uipLineTable
                if "UIP" in levels:
                    con.execute(
                        """CREATE TABLE uipPolygonTable (
                            fid INTEGER PRIMARY KEY AUTOINCREMENT,
                            id1 INTEGER,
                            ust_konu_grup TEXT,
                            id2 INTEGER,
                            uip_fonksiyon TEXT,
                            id3 INTEGER,
                            uip_tabaka TEXT
                        )"""
                    )
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('uipPolygonTable','attributes','UIP polygon function catalog')"
                    )

                    con.execute(
                        """CREATE TABLE uipLineTable (
                            fid INTEGER PRIMARY KEY AUTOINCREMENT,
                            id1 TEXT,
                            ust_konu_grup TEXT,
                            id2 TEXT,
                            uip_fonksiyon TEXT,
                            id3 TEXT,
                            uip_tabaka TEXT
                        )"""
                    )
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('uipLineTable','attributes','UIP line function catalog')"
                    )

                    lookups = _uip_lookups()
                    poly_data = [
                        (p.get("id1"), p.get("ust_konu_grup"), p.get("id2"), p.get("uip_fonksiyon"), p.get("id3"), p.get("uip_tabaka"))
                        for p in lookups.get("polygon_functions", [])
                    ]
                    con.executemany("INSERT INTO uipPolygonTable(id1, ust_konu_grup, id2, uip_fonksiyon, id3, uip_tabaka) VALUES (?,?,?,?,?,?)", poly_data)

                    line_data = [
                        (
                            line_item.get("id1"),
                            line_item.get("ust_konu_grup"),
                            line_item.get("id2"),
                            line_item.get("uip_fonksiyon"),
                            line_item.get("id3"),
                            line_item.get("uip_tabaka"),
                        )
                        for line_item in lookups.get("line_functions", [])
                    ]
                    con.executemany("INSERT INTO uipLineTable(id1, ust_konu_grup, id2, uip_fonksiyon, id3, uip_tabaka) VALUES (?,?,?,?,?,?)", line_data)

                    # Embed the MpyyUipDb drawing template definitions for the UIP layers.
                    from .local_uip_workspace import TEMPLATE_DIR, template

                    styles = template()["styles"]
                    uip_styles = [
                        ("plangml_uip_alan", "uip-alanlar"),
                        ("plangml_uip_cizgi", "uip_cizgiler"),
                        ("plangml_uip_notasyon", "uip-notasyonlar"),
                        ("uipPolygonTable", "uipPolygonTable"),
                        ("uipLineTable", "uipLineTable"),
                    ]
                    for target_layer, template_layer in uip_styles:
                        qml_text = (TEMPLATE_DIR / styles[template_layer]["qml"]).read_text(encoding="utf-8")
                        for old, new in (("uip-alanlar", "plangml_uip_alan"), ("uip_cizgiler", "plangml_uip_cizgi")):
                            qml_text = qml_text.replace(f"'{old}'", f"'{new}'")
                        con.execute(
                            """INSERT INTO layer_styles(f_table_name, styleName, styleQML, useAsDefault, description)
                               VALUES (?, ?, ?, 1, ?)""",
                            (target_layer, target_layer, qml_text, 'MpyyUipDb çizim şablonu'),
                        )

            elif kind == "ARAZI_KULLANIMI":
                # 1. Non-TUCBS Urban Land Use Code Dictionary (Mevcut Arazi Kullanımı Sözlüğü)
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_kullanim_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL,
                        ana_grup TEXT NOT NULL,
                        renk_hex TEXT NOT NULL,
                        aciklama TEXT
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_kullanim_kodlari','attributes','Land use / field survey use code dictionary')"
                )
                from .schema import LAND_USE_CLASSES
                con.executemany(
                    "INSERT INTO saha_kullanim_kodlari (kod, ad, ana_grup, renk_hex, aciklama) VALUES (?,?,?,?,?)",
                    LAND_USE_CLASSES,
                )

                # 2. Building physical condition lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_yapi_durum_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_yapi_durum_kodlari','attributes','Building physical condition codes')"
                )
                con.executemany(
                    "INSERT INTO saha_yapi_durum_kodlari (kod, ad) VALUES (?,?)",
                    [
                        ("İYİ", 'İyi durumda / bakımlı'),
                        ("ORTA", 'Orta durumda / basit onarım gerektirir'),
                        ("KÖTÜ", 'Kötü durumda / esaslı onarım gerektirir'),
                        ("METRUK", 'Metruk / terk edilmiş bina'),
                        ("HARABE", 'Yıkık / harabe yapı'),
                        ("İNŞAAT", 'İnşaat Halindeki Yapı'),
                    ],
                )

                # 3. Building structural system lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_yapi_cins_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_yapi_cins_kodlari','attributes','Building structural system codes')"
                )
                con.executemany(
                    "INSERT INTO saha_yapi_cins_kodlari (kod, ad) VALUES (?,?)",
                    SAHA_YAPI_CINS_KODLARI,
                )

                # 3b. Building layout / zoning order lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_nizam_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_nizam_kodlari','attributes','Building arrangement codes')"
                )
                con.executemany(
                    "INSERT INTO saha_nizam_kodlari (kod, ad) VALUES (?,?)",
                    SAHA_NIZAM_KODLARI,
                )

                # 3c. Parcel development state lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_parsel_durum_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_parsel_durum_kodlari','attributes','Parcel occupation status codes')"
                )
                con.executemany(
                    "INSERT INTO saha_parsel_durum_kodlari (kod, ad) VALUES (?,?)",
                    SAHA_PARSEL_DURUM_KODLARI,
                )


                # 4. Road hierarchy classification lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_yol_tip_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL,
                        oneri_genislik_m REAL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_yol_tip_kodlari','attributes','Road hierarchy type codes')"
                )
                con.executemany(
                    "INSERT INTO saha_yol_tip_kodlari (kod, ad, oneri_genislik_m) VALUES (?,?,?)",
                    [
                        ("ANA_ARTER", "Ana Arter / Bulvar (1. Derece)", 30.0),
                        ("TOPLAYICI_YOL", 'Toplayıcı Yol (2. Derece)', 15.0),
                        ("SERVIS_YOLU", 'Servis / İmar Yolu (3. Derece)', 10.0),
                        ("YAYA_YOLU", 'Yaya Yolu / Yayalaştırılmış Bölge', 8.0),
                        ("CIKMAZ_SOKAK", 'Çıkmaz Sokak', 6.0),
                        ("KIRSAL_YOL", 'Kırsal / Tarla Yolu', 5.0),
                    ],
                )

                # 5. Land ownership classification lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_mulkiyet_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_mulkiyet_kodlari','attributes','Ownership type codes')"
                )
                con.executemany(
                    "INSERT INTO saha_mulkiyet_kodlari (kod, ad) VALUES (?,?)",
                    [
                        ("ÖZEL", 'Özel Mülkiyet (Şahıs / Şirket)'),
                        ("BELEDİYE", 'Belediye Mülkiyeti'),
                        ("HAZİNE", 'Maliye Hazinesi'),
                        ("VAKIF", 'Vakıflar Genel Müdürlüğü'),
                        ("KAMU_DİĞER", 'Diğer Kamu Kurumları (TCDD, DSİ vb.)'),
                        ("TESCİL_HARİCİ", "Tescil Harici / Yol / Terkin"),
                    ],
                )

                # 6. Building quality lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_yapi_kalite_kodlari (
                        kod INTEGER PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_yapi_kalite_kodlari','attributes','Building quality classes')"
                )
                con.executemany(
                    "INSERT INTO saha_yapi_kalite_kodlari (kod, ad) VALUES (?,?)",
                    [
                        (1, '1 - Çok Kötü / Yıkılacak'),
                        (2, '2 - Kötü / Esaslı Onarım'),
                        (3, '3 - Orta / Bakımlı'),
                        (4, '4 - İyi / Yeni'),
                        (5, '5 - Çok İyi / Lüks'),
                    ],
                )

                # 7. Road paving surface lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_yol_kaplama_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_yol_kaplama_kodlari','attributes','Road surface material codes')"
                )
                con.executemany(
                    "INSERT INTO saha_yol_kaplama_kodlari (kod, ad) VALUES (?,?)",
                    [
                        ("ASFALT_BSK", 'Asfalt (Sıcak/BSK)'),
                        ("ASFALT_SATHI", "Asfalt (Sathi)"),
                        ("KILIT_PARKE", 'Kilit Parke Taşı'),
                        ("BETON", "Beton"),
                        ("GRANIT_KUP", 'Granit Küptaş'),
                        ("ARNAVUT", 'Arnavut Kaldırımı'),
                        ("STABILIZE", 'Stabilize (Çakıl)'),
                        ("TOPRAK", "Toprak (Tesviye)"),
                        ("HAM_YOL", 'Ham Yol (İz)'),
                    ],
                )

                # 8. Protection status lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_koruma_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_koruma_kodlari','attributes','Protection and heritage designation codes')"
                )
                con.executemany(
                    "INSERT INTO saha_koruma_kodlari (kod, ad) VALUES (?,?)",
                    [
                        ("YOK", 'Herhangi Bir Sit / Koruma Statüsü Yok'),
                        ("KENTSEL_SİT", 'Kentsel Sit Alanı İçi'),
                        ("DOĞAL_SİT", 'Doğal Sit Alanı İçi'),
                        ("ARKEOLOJİK_SİT", 'Arkeolojik Sit Alanı İçi'),
                        ("TESCİLLİ_YAPI", 'Tescilli Kültür Varlığı / Yapı'),
                    ],
                )

                # 9. Roof types lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_cati_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_cati_kodlari','attributes','Building roof type codes')"
                )
                con.executemany(
                    "INSERT INTO saha_cati_kodlari (kod, ad) VALUES (?,?)",
                    SAHA_CATI_KODLARI,
                )

                # 10. Heating types lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_isitma_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_isitma_kodlari','attributes','Building heating type codes')"
                )
                con.executemany(
                    "INSERT INTO saha_isitma_kodlari (kod, ad) VALUES (?,?)",
                    SAHA_ISITMA_KODLARI,
                )

                # 11. Damage status lookup table
                con.execute(
                    """CREATE TABLE IF NOT EXISTS saha_hasar_kodlari (
                        kod TEXT PRIMARY KEY,
                        ad TEXT NOT NULL
                    )"""
                )
                con.execute(
                    "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('saha_hasar_kodlari','attributes','Building damage condition codes')"
                )
                con.executemany(
                    "INSERT INTO saha_hasar_kodlari (kod, ad) VALUES (?,?)",
                    SAHA_HASAR_KODLARI,
                )

                # 12. Embed official QML styles for Arazi Kullanımı layers
                arazi_styles = [
                    ("parsel_saha", "forms/arazi/01_parsel_saha.qml"),
                    ("Tucbs_1000_alan", "forms/arazi/02_Tucbs_1000_alan.qml"),
                    ("Tucbs_1000_Cizgi", "forms/arazi/03_Tucbs_1000_Cizgi.qml"),
                    ("yapi_saha", "forms/arazi/04_yapi_saha.qml"),
                    ("yol_saha", "forms/arazi/05_yol_saha.qml"),
                ]
                for target_layer, qml_file in arazi_styles:
                    qml_text = _read_qml(qml_file)
                    if qml_text:
                        con.execute(
                            """INSERT INTO layer_styles(f_table_name, styleName, styleQML, useAsDefault, description)
                               VALUES (?, ?, ?, 1, ?)""",
                            (target_layer, target_layer, qml_text, f"{target_layer} saha anket stili"),
                        )

            # 4. Add columns, indexes and triggers to spatial tables
            for table, (geometry, fields) in tables.items():
                for field, definition in fields.items():
                    con.execute(f"ALTER TABLE {_quote(table)} ADD COLUMN {_quote(field)} {definition}")

                # Unique index on global_id
                if "global_id" in fields:
                    con.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {_quote('idx_' + table + '_gid')} ON {_quote(table)}({_quote('global_id')})")

                if "catalog_id" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_cat')} ON {_quote(table)}({_quote('catalog_id')})")

                if "fonksiyon_kodu" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_fonk')} ON {_quote(table)}({_quote('fonksiyon_kodu')})")

                if "ADA" in fields and "PARSEL" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_ada_parsel')} ON {_quote(table)}({_quote('ADA')}, {_quote('PARSEL')})")

                if "P_FONK" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_p_fonk')} ON {_quote(table)}({_quote('P_FONK')})")

                if "B_FONK" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_b_fonk')} ON {_quote(table)}({_quote('B_FONK')})")

                if "Y_TIP" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_y_tip')} ON {_quote(table)}({_quote('Y_TIP')})")

                if "MAHALLE" in fields:
                    con.execute(f"CREATE INDEX IF NOT EXISTS {_quote('idx_' + table + '_mahalle')} ON {_quote(table)}({_quote('MAHALLE')})")

                if table.startswith("plangml_"):
                    _create_audit_triggers(con, table, fields)
                elif table in ("parsel_saha", "yapi_saha", "yol_saha"):
                    _create_survey_audit_triggers(con, table, fields)

            # 5. Summary and reporting SQL views (registered in gpkg_contents as attribute layers)
            if kind == "ARAZI_KULLANIMI":
                views_arazi = [
                    (
                        "v_saha_parsel_kullanim_ozet",
                        """CREATE VIEW IF NOT EXISTS v_saha_parsel_kullanim_ozet AS
                        SELECT 
                            COALESCE(P_FONK, 'BELİRTİLMEMİŞ') AS kullanim_fonksiyonu,
                            COUNT(*) AS parsel_sayisi,
                            ROUND(SUM(COALESCE(alan_m2, 0)), 2) AS toplam_alan_m2,
                            ROUND(AVG(COALESCE(alan_m2, 0)), 2) AS ortalama_alan_m2,
                            SUM(COALESCE(P_NUFUS, 0)) AS tahmini_nufus,
                            SUM(COALESCE(P_BAGIMSIZ_BOLUM, 0)) AS toplam_bagimsiz_bolum,
                            SUM(COALESCE(P_YAPI_ADET, 0)) AS toplam_bina_sayisi
                        FROM parsel_saha
                        GROUP BY P_FONK
                        ORDER BY toplam_alan_m2 DESC""",
                        'Saha Parsel Kullanım Fonksiyonu Dağılım Özeti',
                    ),
                    (
                        "v_saha_yapi_kat_ve_durum_ozet",
                        """CREATE VIEW IF NOT EXISTS v_saha_yapi_kat_ve_durum_ozet AS
                        SELECT 
                            COALESCE(B_FONK, 'BELİRTİLMEMİŞ') AS yapi_fonksiyonu,
                            COALESCE(B_KAT, 0) AS kat_adedi,
                            COALESCE(B_DURUM, 'BELİRSİZ') AS yapi_durumu,
                            COALESCE(B_YAPI_CINSI, 'BELİRSİZ') AS yapi_cinsi,
                            COUNT(*) AS bina_adedi,
                            ROUND(SUM(COALESCE(alan_m2, 0)), 2) AS toplam_taban_alani_m2,
                            ROUND(AVG(COALESCE(B_YAS, 0)), 1) AS ortalama_bina_yasi
                        FROM yapi_saha
                        GROUP BY B_FONK, B_KAT, B_DURUM, B_YAPI_CINSI""",
                        'Saha Yapı Kat, Durum ve Taşıyıcı Cins Dağılım Özeti',
                    ),
                    (
                        "v_saha_mahalle_bilancosu",
                        """CREATE VIEW IF NOT EXISTS v_saha_mahalle_bilancosu AS
                        SELECT 
                            COALESCE(MAHALLE, 'BELİRSİZ') AS mahalle_adi,
                            COUNT(DISTINCT ADA || '-' || PARSEL) AS parsel_adedi,
                            ROUND(SUM(COALESCE(alan_m2, 0)), 2) AS toplam_parsel_alani_m2,
                            SUM(COALESCE(P_NUFUS, 0)) AS toplam_nufus,
                            SUM(COALESCE(P_BAGIMSIZ_BOLUM, 0)) AS toplam_bagimsiz_bolum
                        FROM parsel_saha
                        GROUP BY MAHALLE
                        ORDER BY mahalle_adi""",
                        'Mahalle Bazlı Parsel ve Nüfus Bilançosu',
                    ),
                    (
                        "v_saha_yol_envanteri",
                        """CREATE VIEW IF NOT EXISTS v_saha_yol_envanteri AS
                        SELECT 
                            COALESCE(Y_TIP, 'DİĞER') AS yol_kademesi,
                            COALESCE(Y_KAPLAMA, 'BELİRSİZ') AS kaplama_turu,
                            COUNT(*) AS segment_sayisi,
                            ROUND(SUM(COALESCE(uzunluk_m, 0)), 2) AS toplam_uzunluk_m,
                            ROUND(SUM(COALESCE(uzunluk_m, 0)) / 1000.0, 3) AS toplam_uzunluk_km,
                            ROUND(AVG(COALESCE(Y_GENISLIK, 0)), 2) AS ortalama_genislik_m
                        FROM yol_saha
                        GROUP BY Y_TIP, Y_KAPLAMA
                        ORDER BY toplam_uzunluk_m DESC""",
                        'Yol Ağı Hiyerarşi ve Kaplama Envanteri',
                    ),
                ]
                for view_name, view_sql, view_ident in views_arazi:
                    con.execute(view_sql)
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES (?, 'attributes', ?)",
                        (view_name, view_ident),
                    )

            elif kind == "PLANLAMA":
                if "UIP" in levels:
                    views_uip = [
                        (
                            "v_uip_fonksiyon_bilancosu",
                            """CREATE VIEW IF NOT EXISTS v_uip_fonksiyon_bilancosu AS
                            SELECT 
                                COALESCE(uipfonksiyon, 'BELİRTİLMEMİŞ') AS plan_fonksiyonu,
                                COALESCE(ustkonugrup, 'BELİRTİLMEMİŞ') AS ust_konu_grubu,
                                COUNT(*) AS poligon_sayisi,
                                ROUND(SUM(COALESCE(AlanM2, 0)), 2) AS toplam_alan_m2,
                                ROUND(SUM(COALESCE(AlanM2, 0)) / 10000.0, 4) AS toplam_alan_ha
                            FROM plangml_uip_alan
                            GROUP BY uipfonksiyon, ustkonugrup
                            ORDER BY toplam_alan_m2 DESC""",
                            'UİP 1/1000 Fonksiyon Dağılımı ve Alan Bilançosu',
                        ),
                        (
                            "v_uip_yol_kademelenmesi",
                            """CREATE VIEW IF NOT EXISTS v_uip_yol_kademelenmesi AS
                            SELECT 
                                COALESCE(yolTipi, 'BELİRSİZ') AS yol_tipi,
                                COALESCE(yolGenislik, 0) AS plan_genisligi_m,
                                COUNT(*) AS cizgi_sayisi,
                                ROUND(SUM(COALESCE("Uzunluk(m)", 0)), 2) AS toplam_uzunluk_m,
                                ROUND(SUM(COALESCE("Uzunluk(m)", 0)) / 1000.0, 3) AS toplam_uzunluk_km
                            FROM plangml_uip_cizgi
                            GROUP BY yolTipi, yolGenislik
                            ORDER BY plan_genisligi_m DESC""",
                            'UİP 1/1000 Yol Kademelenmesi ve Metraj Bilançosu',
                        ),
                    ]
                    for view_name, view_sql, view_ident in views_uip:
                        con.execute(view_sql)
                        con.execute(
                            "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES (?, 'attributes', ?)",
                            (view_name, view_ident),
                        )

                if "NIP" in levels:
                    v_nip_sql = """CREATE VIEW IF NOT EXISTS v_nip_yogunluk_ve_alan_dagilimi AS
                    SELECT 
                        COALESCE(fonksiyon_adi, 'BELİRTİLMEMİŞ') AS nazim_fonksiyon,
                        COALESCE(yogunluk_kademesi, 'BELİRSİZ') AS yogunluk,
                        COUNT(*) AS bolge_sayisi,
                        ROUND(SUM(COALESCE(alan_m2, 0)), 2) AS toplam_alan_m2,
                        ROUND(SUM(COALESCE(alan_m2, 0)) / 10000.0, 4) AS toplam_alan_ha
                    FROM plangml_nip_alan
                    GROUP BY fonksiyon_adi, yogunluk_kademesi
                    ORDER BY toplam_alan_m2 DESC"""
                    con.execute(v_nip_sql)
                    con.execute(
                        "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES (?, 'attributes', ?)",
                        ("v_nip_yogunluk_ve_alan_dagilimi", 'NİP 1/5000 Yoğunluk ve Alan Dağılım Bilançosu'),
                    )

            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError('Veritabanı bütünlüğü doğrulanamadı: ' + str(integrity))

        # Rename atomic staging file to target
        if os.name == "nt":
            os.replace(staged, output)
        else:
            os.rename(staged, output)

    finally:
        for item in staging.glob("*"):
            with contextlib.suppress(Exception):
                item.unlink(missing_ok=True)
        with contextlib.suppress(Exception):
            staging.rmdir()

    return str(output)


def create_planning_workspace(output_path, crs, plan_levels=None):
    """Create a GeoPackage containing strictly isolated tables for the selected planning levels."""
    levels = tuple(plan_levels or PLAN_LEVEL_CODES)
    ordered = tuple(code for code, _, _ in PLAN_LEVELS if code in levels)
    if not ordered:
        raise ValueError('En az bir plan kademesi seçilmelidir')
    return _create(output_path, crs, selected_tables(ordered), "PLANLAMA", ordered)


def create_land_use_workspace(output_path, crs):
    """Create an independent Arazi Kullanımı GeoPackage containing TUCBS and field survey tables."""
    return _create(output_path, crs, LAND_TABLES, "ARAZI_KULLANIMI", ())


def create_geopackage(output_path, crs, catalog_rows=None):
    """Backward-compatible alias: creates all four PlanGML levels."""
    return create_planning_workspace(output_path, crs, ("MSP", "CDP", "NIP", "UIP"))


def read_dataset_info(path):
    """Read metadata from a PlanX MPYY GeoPackage."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as con:
        row = con.execute(
            "SELECT dataset_id, schema_version, workspace_kind, plan_levels FROM mpyy_metadata"
        ).fetchone()
    if not row or row[1] != SCHEMA_VERSION:
        raise ValueError('Desteklenmeyen veya geçersiz MPYY şema sürümü')
    uuid.UUID(row[0])
    return {
        "dataset_id": row[0],
        "schema_version": row[1],
        "workspace_kind": row[2],
        "plan_levels": tuple(filter(None, row[3].split(","))),
    }


def read_dataset_id(path):
    return read_dataset_info(path)["dataset_id"]
