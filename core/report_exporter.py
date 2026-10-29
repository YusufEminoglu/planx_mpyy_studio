"""Urban Planning Balance and Explanatory Report Exporter (HTML & CSV).

Implements statutory reporting requirements of Mekânsal Planlar Yapım Yönetmeliği:
- Madde 21: "Plan açıklama raporunda; planlama alanının konumu, genel özellikleri,
  nüfus projeksiyonları, donatı alanları dengesi, mekânsal kararlar ve uygulama esasları
  ayrıntılı olarak açıklanır."
- Madde 24 & EK-2: Kentsel donatı standartları tablosu ve arazi kullanım bilançosu.
"""

from __future__ import annotations

import contextlib
import csv
from dataclasses import dataclass, field
import html as _html
from pathlib import Path
import sqlite3
from typing import Any

from qgis.core import QgsFeature, QgsGeometry

from .attr_utils import extract_plan_function, first_text, norm_tr, upper_tr
from .db_factory import _connect_ro
from .localization import display_label, field_alias


def _norm_str(val: Any) -> str:
    return norm_tr(val)


KNOWN_VIEWS = [
    ("v_saha_parsel_kullanim_ozet", 'Mevcut Arazi Kullanımı Dağılımı ve Fonksiyon Dengesi'),
    ("v_saha_yapi_kat_ve_durum_ozet", 'Bina Envanteri: Kat Adetleri, Taşıyıcı Sistem ve Fiziksel Durum'),
    ("v_saha_mahalle_bilancosu", 'Mahalle Bazlı Parsel, Bağımsız Bölüm ve Nüfus Dağılımı'),
    ("v_saha_yol_envanteri", 'Ulaşım Altyapısı: Yol Kademelenmesi ve Kaplama Türleri'),
    ("v_uip_fonksiyon_bilancosu", 'UİP 1/1000 Fonksiyon Dağılımı ve Alan Bilançosu'),
    ("v_uip_yol_kademelenmesi", 'UİP 1/1.000 Yol Kademelenmesi ve Metraj Tablosu'),
    ("v_nip_yogunluk_ve_alan_dagilimi", 'NİP 1/5.000 Brüt Yoğunluk ve Alan Dağılımı'),
]

KNOWN_VIEW_QUERIES: dict[str, str] = {
    "v_saha_parsel_kullanim_ozet": "SELECT * FROM v_saha_parsel_kullanim_ozet",
    "v_saha_yapi_kat_ve_durum_ozet": "SELECT * FROM v_saha_yapi_kat_ve_durum_ozet",
    "v_saha_mahalle_bilancosu": "SELECT * FROM v_saha_mahalle_bilancosu",
    "v_saha_yol_envanteri": "SELECT * FROM v_saha_yol_envanteri",
    "v_uip_fonksiyon_bilancosu": "SELECT * FROM v_uip_fonksiyon_bilancosu",
    "v_uip_yol_kademelenmesi": "SELECT * FROM v_uip_yol_kademelenmesi",
    "v_nip_yogunluk_ve_alan_dagilimi": "SELECT * FROM v_nip_yogunluk_ve_alan_dagilimi",
}


def export_planning_report(
    gpkg_path: str | Path,
    output_dir: str | Path,
    report_title: str = 'PlanX MPYY - Plan Açıklama Raporu Tabloları ve Arazi Analizi',
) -> dict[str, Any]:
    """Export summary reporting views from GeoPackage into HTML report and individual CSV files."""
    db_file = Path(gpkg_path).resolve()
    if not db_file.is_file():
        raise FileNotFoundError(f'Veritabanı dosyası bulunamadı: {db_file}')

    out_folder = Path(output_dir).resolve()
    out_folder.mkdir(parents=True, exist_ok=True)
    csv_folder = out_folder / "csv_tablolari"
    csv_folder.mkdir(parents=True, exist_ok=True)

    exported_tables = []

    with contextlib.closing(_connect_ro(db_file)) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Check existing views/tables in sqlite_master
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
        existing_names = {row["name"] for row in cur.fetchall()}

        for view_name, display_title in KNOWN_VIEWS:
            if view_name not in existing_names:
                continue
            query = KNOWN_VIEW_QUERIES.get(view_name)
            if not query:
                continue
            cur.execute(query)
            rows = cur.fetchall()
            if not rows:
                continue

            col_names = list(rows[0].keys())

            # Export to CSV
            csv_path = csv_folder / f"{view_name}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([field_alias(col) for col in col_names])
                for row in rows:
                    writer.writerow([display_label(value) if isinstance(value, str) else value for value in row])

            exported_tables.append(
                {
                    "view_name": view_name,
                    "title": display_title,
                    "columns": col_names,
                    "rows": [list(r) for r in rows],
                    "csv_path": str(csv_path),
                }
            )

        # Fallback for Yerel UİP, Yerel NİP, MPYY 1.1.7 XSD, and MSP Ek-1e GeoPackages without SQL views
        if not exported_tables and "gpkg_contents" in existing_names:
            if "gpkg_ogr_contents" in existing_names:
                cur.execute(
                    "SELECT c.table_name AS katman_adi, c.identifier AS gosterim_basligi, "
                    "c.data_type AS veri_tipi, c.srs_id AS krs_kodu, "
                    "COALESCE(o.feature_count, 0) AS kayit_adedi "
                    "FROM gpkg_contents c "
                    "LEFT JOIN gpkg_ogr_contents o ON o.table_name = c.table_name "
                    "ORDER BY c.table_name"
                )
            else:
                cur.execute(
                    "SELECT table_name AS katman_adi, identifier AS gosterim_basligi, "
                    "data_type AS veri_tipi, srs_id AS krs_kodu "
                    "FROM gpkg_contents ORDER BY table_name"
                )
            fallback_rows = cur.fetchall()
            if fallback_rows:
                col_names = list(fallback_rows[0].keys())
                csv_path = csv_folder / "gpkg_katman_envanteri.csv"
                with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([field_alias(col) for col in col_names])
                    for row in fallback_rows:
                        writer.writerow([display_label(value) if isinstance(value, str) else value for value in row])
                exported_tables.append(
                    {
                        "view_name": "gpkg_katman_envanteri",
                        "title": "Çalışma Alanı Katman ve Tablo Envanteri",
                        "columns": col_names,
                        "rows": [list(r) for r in fallback_rows],
                        "csv_path": str(csv_path),
                    }
                )

    esc_title = _html.escape(str(report_title))
    esc_db = _html.escape(db_file.name)

    # Generate HTML Document
    html_lines = [
        "<!DOCTYPE html>",
        "<html lang='tr'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"  <title>{esc_title}</title>",
        "  <style>",
        "    body { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; background: #f8f9fa; color: #333; margin: 0; padding: 24px; }",
        "    .container { max-width: 1100px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }",
        "    h1 { color: #1a5276; margin-top: 0; border-bottom: 2px solid #1a5276; padding-bottom: 12px; font-size: 24px; }",
        "    .meta { font-size: 13px; color: #7f8c8d; margin-bottom: 24px; }",
        "    .table-section { margin-bottom: 36px; }",
        "    h2 { font-size: 17px; color: #2c3e50; border-left: 4px solid #2980b9; padding-left: 10px; margin-bottom: 14px; }",
        "    table { width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 13px; }",
        "    th { background: #eaeded; color: #2c3e50; font-weight: 600; text-align: left; padding: 10px 12px; border: 1px solid #d5dbdb; }",
        "    td { padding: 8px 12px; border: 1px solid #e5e8e8; }",
        "    tr:nth-child(even) { background: #fdfefe; }",
        "    tr:hover { background: #ebf5fb; }",
        "    .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background: #d4efdf; color: #1e8449; }",
        "    @media print { body { background: #fff; padding: 0; } .container { box-shadow: none; padding: 0; } h2 { page-break-before: always; } }",
        "  </style>",
        "</head>",
        "<body>",
        "  <div class='container'>",
        f"    <h1>{esc_title}</h1>",
        f"    <div class='meta'>Veri Kaynağı: <code>{esc_db}</code> &bull; Raporlama Motoru: PlanX MPYY Studio &bull; Yazar: Geophilo</div>",
    ]

    if not exported_tables:
        html_lines.append('<p>Veritabanında raporlanabilir özet görünüm bulunamadı.</p>')
    else:
        for tbl in exported_tables:
            html_lines.append("    <div class='table-section'>")
            html_lines.append(f"      <h2>{_html.escape(str(tbl['title']))}</h2>")
            html_lines.append("      <table>")
            html_lines.append("        <thead><tr>")
            for col in tbl["columns"]:
                formatted_col = _html.escape(str(field_alias(col)))
                html_lines.append(f"          <th>{formatted_col}</th>")
            html_lines.append("        </tr></thead>")
            html_lines.append("        <tbody>")
            for row in tbl["rows"]:
                html_lines.append("          <tr>")
                for cell in row:
                    val_str = f"{cell:,.2f}" if isinstance(cell, float) else display_label(cell if cell is not None else "-")
                    html_lines.append(f"            <td>{_html.escape(str(val_str))}</td>")
                html_lines.append("          </tr>")
            html_lines.append("        </tbody>")
            html_lines.append("      </table>")
            html_lines.append("    </div>")

    html_lines.extend(["  </div>", "</body>", "</html>"])

    html_path = out_folder / "plan_aciklama_raporu.html"
    html_path.write_text("\n".join(html_lines), encoding="utf-8")

    return {
        "html_report": str(html_path),
        "csv_directory": str(csv_folder),
        "table_count": len(exported_tables),
    }


@dataclass
class LandUseBalanceRow:
    fonksiyon_adi: str
    ust_grup: str
    alan_m2: float
    alan_hektar: float
    yuzde: float
    adet: int
    kamusal_mi: bool


class PlanReportEngine:
    """Comprehensive MPYY Urban Planning Explanation Report Generator."""

    @classmethod
    def compute_land_use_balance(cls, features: list[QgsFeature]) -> tuple[list[LandUseBalanceRow], float]:
        """Group plan polygons across all 5 MPYY Studio schemas by function and calculate areas and percentages."""
        grp_keys = ("ustkonugrup", "ust_konu_grup", "ust_grup_adi", "ust_grup_kodu", "ana_grup", "strateji_bolgesi")

        # Amenity keywords to mark public infrastructure
        pub_kws = (
            "PARK", "YESIL", "MEYDAN", "REKREASYON", "COCUK", "EGITIM", "OKUL",
            "ANAOKULU", "ILKOKUL", "ORTAOKUL", "LISE", "SAGLIK", "HASTANE",
            "IBADET", "CAMI", "MESCIT", "SOSYAL", "KULTUR", "SPOR", "TEKNIK",
            "TRAFO", "ARITMA", "OTOPARK", "MEZARLIK", "BELEDIYE", "KAMU",
            "RESMI", "IDARI", "BHA", "KHA", "YOL",
        )

        cat_stats: dict[str, dict[str, Any]] = {}
        total_area = 0.0

        for feat in features:
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area = round(geom.area(), 2)
            if area <= 0:
                continue

            fn_val = extract_plan_function(feat, default='DİĞER KULLANIMLAR')
            grp_val = first_text(feat, grp_keys)

            norm_fn = _norm_str(fn_val)
            is_pub = any(kw in norm_fn for kw in pub_kws)

            if fn_val not in cat_stats:
                cat_stats[fn_val] = {
                    "ust_grup": grp_val,
                    "alan_m2": 0.0,
                    "adet": 0,
                    "kamusal": is_pub,
                }
            cat_stats[fn_val]["alan_m2"] += area
            cat_stats[fn_val]["adet"] += 1
            total_area += area

        rows: list[LandUseBalanceRow] = []
        for fn_name, data in sorted(cat_stats.items(), key=lambda x: x[1]["alan_m2"], reverse=True):
            a_m2 = round(data["alan_m2"], 2)
            pct = round((a_m2 / total_area) * 100.0, 2) if total_area > 0 else 0.0
            rows.append(
                LandUseBalanceRow(
                    fonksiyon_adi=fn_name,
                    ust_grup=data["ust_grup"],
                    alan_m2=a_m2,
                    alan_hektar=round(a_m2 / 10000.0, 4),
                    yuzde=pct,
                    adet=data["adet"],
                    kamusal_mi=data["kamusal"],
                )
            )

        return rows, round(total_area, 2)

    @classmethod
    def generate_comprehensive_report(
        cls,
        output_dir: str | Path,
        plan_features: list[QgsFeature] | None = None,
        report_title: str = 'Plan Açıklama Raporu',
        plan_scale: str = "1/1.000",
        crs_authid: str = "EPSG:5256",
        capacity_summary: Any = None,
        amenity_results: list[Any] | None = None,
        dop_summary: Any = None,
        compliance_summary: Any = None,
        pafta_summary: Any = None,
        plan_notes: Any = None,
    ) -> dict[str, str]:
        """Compile an exhaustive, publication-grade MPYY Plan Explanation Report."""
        out_folder = Path(output_dir).resolve()
        out_folder.mkdir(parents=True, exist_ok=True)

        rows: list[LandUseBalanceRow] = []
        total_area_m2 = 0.0
        if plan_features:
            rows, total_area_m2 = cls.compute_land_use_balance(plan_features)

        # Write CSV Balance Table
        csv_path = out_folder / "arazi_kullanimi_bilancosu.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(['Fonksiyon Adı', 'Üst Konu Grubu', 'Alan (m²)', 'Alan (Ha)', 'Oran (%)', 'Adet', 'Kamusal Donatı'])
            for r in rows:
                writer.writerow([display_label(r.fonksiyon_adi), display_label(r.ust_grup), r.alan_m2, r.alan_hektar, r.yuzde, r.adet, 'Evet' if r.kamusal_mi else 'Hayır'])

        # Compute Public Amenity vs Development Ratio
        public_area_m2 = sum(r.alan_m2 for r in rows if r.kamusal_mi)
        public_pct = round((public_area_m2 / total_area_m2) * 100.0, 1) if total_area_m2 > 0 else 0.0

        # Resolve both real dataclass attributes and legacy mock attributes seamlessly
        cap_pop = None
        cap_const_m2_num = 0.0
        cap_konut_m2 = 0.0
        cap_kaks = 0.0
        cap_units = 0
        if capacity_summary is not None:
            cap_pop = getattr(capacity_summary, "toplam_kapasite_nufusu", getattr(capacity_summary, "ongorulen_nufus", 0))
            cap_const_m2_num = float(getattr(capacity_summary, "toplam_insaat_m2", getattr(capacity_summary, "toplam_insaat_alani_m2", 0.0)) or 0.0)
            cap_konut_m2 = float(getattr(capacity_summary, "toplam_konut_alani_m2", 0.0) or 0.0)
            cap_kaks = float(getattr(capacity_summary, "ortalama_kaks", getattr(capacity_summary, "ortalama_emsal", 0.0)) or 0.0)
            cap_units = int(getattr(capacity_summary, "toplam_konut_sayisi", getattr(capacity_summary, "ongorulen_konut_adedi", 0)) or 0)

        dop_pct_num = None
        dop_exceeded = False
        if dop_summary is not None:
            if hasattr(dop_summary, "dop_orani_yuzde"):
                dop_pct_num = float(getattr(dop_summary, "dop_orani_yuzde") or 0.0)
            elif hasattr(dop_summary, "dop_orani_percent"):
                dop_pct_num = float(getattr(dop_summary, "dop_orani_percent") or 0.0)
            else:
                dop_pct_num = float(getattr(dop_summary, "dop_orani", 0.0) or 0.0) * 100.0
            if hasattr(dop_summary, "yasal_sinir_asildi_mi"):
                dop_exceeded = bool(getattr(dop_summary, "yasal_sinir_asildi_mi"))
            else:
                dop_exceeded = not bool(getattr(dop_summary, "yasal_uygun", True))

        def _amenity_tuple(item: Any) -> tuple[str, bool, float, float, float, float]:
            raw_name = getattr(item, "donati_adi", None)
            if not raw_name:
                bolge = str(getattr(item, "bolge_adi", "-") or "-")
                raw_name = bolge.split(" - ", 1)[-1] if " - " in bolge else bolge
            if hasattr(item, "yeterli_mi"):
                is_ok = bool(getattr(item, "yeterli_mi"))
            else:
                is_ok = norm_tr(getattr(item, "yeterlilik_durumu", "")) == "YETERLI"
            std = float(getattr(item, "kisi_basi_standart_m2", getattr(item, "standart_m2_kisi", 0.0)) or 0.0)
            req = float(getattr(item, "mevzuat_ihtiyac_m2", getattr(item, "gerekli_yesil_alan_m2", 0.0)) or 0.0)
            cur = float(getattr(item, "planda_ayrilan_m2", getattr(item, "mevcut_yesil_alan_m2", 0.0)) or 0.0)
            pc = float(getattr(item, "kisi_basi_fiili_m2", getattr(item, "kisi_basi_mevcut_m2", 0.0)) or 0.0)
            return str(raw_name), is_ok, std, req, cur, pc

        comp_total = 0
        comp_buildable = 0
        comp_tevhid = 0
        comp_ifraz = 0
        if compliance_summary is not None:
            comp_total = int(getattr(compliance_summary, "toplam_parsel_sayisi", getattr(compliance_summary, "toplam_parsel", 0)) or 0)
            comp_buildable = int(getattr(compliance_summary, "yapilasabilir_sayisi", getattr(compliance_summary, "yapilasabilir_parseller", 0)) or 0)
            comp_tevhid = int(getattr(compliance_summary, "tevhid_zorunlu_sayisi", getattr(compliance_summary, "tevhid_zorunlu_parseller", 0)) or 0)
            comp_ifraz = int(getattr(compliance_summary, "ifraz_edilebilir_sayisi", getattr(compliance_summary, "ifraz_edilebilir_parseller", 0)) or 0)

        esc_title = _html.escape(str(report_title))
        esc_scale = _html.escape(str(plan_scale))
        esc_crs = _html.escape(str(crs_authid))

        # Build HTML
        html: list[str] = [
            "<!DOCTYPE html>",
            "<html lang='tr'>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"  <title>{esc_title} — PlanX MPYY Studio</title>",
            "  <style>",
            "    body { font-family: 'Segoe UI', -apple-system, Roboto, sans-serif; background: #f4f6f7; color: #2c3e50; margin: 0; padding: 24px; }",
            "    .doc-container { max-width: 1080px; margin: 0 auto; background: #ffffff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }",
            "    .header { border-bottom: 3px solid #1a5276; padding-bottom: 16px; margin-bottom: 24px; }",
            "    .header h1 { color: #1a5276; font-size: 24px; margin: 0 0 6px 0; }",
            "    .header .subtitle { color: #7f8c8d; font-size: 13px; font-weight: 500; }",
            "    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 28px; }",
            "    .kpi-card { background: #f8f9fa; border: 1px solid #e5e8e8; border-radius: 6px; padding: 14px; text-align: center; }",
            "    .kpi-title { font-size: 11px; color: #7f8c8d; font-weight: bold; text-transform: uppercase; margin-bottom: 4px; }",
            "    .kpi-value { font-size: 20px; color: #1a5276; font-weight: bold; }",
            "    .kpi-sub { font-size: 11px; color: #95a5a6; margin-top: 3px; }",
            "    h2 { color: #1a5276; font-size: 17px; border-left: 4px solid #2980b9; padding-left: 10px; margin-top: 32px; margin-bottom: 14px; }",
            "    table { width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 13px; }",
            "    th { background: #eaeded; color: #2c3e50; font-weight: 600; text-align: left; padding: 9px 12px; border: 1px solid #d5dbdb; }",
            "    td { padding: 8px 12px; border: 1px solid #e5e8e8; }",
            "    tr:nth-child(even) { background: #fafbfc; }",
            "    tr:hover { background: #ebf5fb; }",
            "    .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }",
            "    .badge-success { background: #d4efdf; color: #1e8449; }",
            "    .badge-warning { background: #fcf3cf; color: #b7950b; }",
            "    .badge-danger { background: #fadbd8; color: #922b21; }",
            "    .badge-info { background: #d6eaf8; color: #2471a3; }",
            "    .footer { font-size: 12px; color: #95a5a6; text-align: center; margin-top: 40px; border-top: 1px solid #e5e8e8; padding-top: 14px; }",
            "    @media print { body { background: #fff; padding: 0; } .doc-container { box-shadow: none; padding: 0; } h2 { page-break-before: always; } }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='doc-container'>",
            "    <div class='header'>",
            f"      <h1>{esc_title}</h1>",
            f"      <div class='subtitle'>Ölçek: <strong>{esc_scale}</strong> &bull; Koordinat Referans Sistemi: <strong>{esc_crs}</strong> &bull; Mevzuat: <strong>Mekânsal Planlar Yapım Yönetmeliği (MPYY)</strong></div>",
            "    </div>",
        ]

        # KPI Banners
        pop_val = f"{int(cap_pop):,}" if cap_pop is not None else "-"
        const_m2 = f"{cap_const_m2_num:,.0f} m²" if capacity_summary is not None else "-"
        dop_val = f"%{dop_pct_num:.2f}" if dop_pct_num is not None else "-"

        html.append("    <div class='kpi-grid'>")
        html.append(f"      <div class='kpi-card'><div class='kpi-title'>Toplam Plan Alanı</div><div class='kpi-value'>{total_area_m2:,.1f} m²</div><div class='kpi-sub'>{total_area_m2 / 10000.0:.2f} ha</div></div>")
        html.append(f"      <div class='kpi-card'><div class='kpi-title'>Öngörülen Nüfus</div><div class='kpi-value'>{pop_val}</div><div class='kpi-sub'>Kapasite Projeksiyonu</div></div>")
        html.append(f"      <div class='kpi-card'><div class='kpi-title'>Kamusal Donatı Oranı</div><div class='kpi-value'>%{public_pct}</div><div class='kpi-sub'>{public_area_m2:,.1f} m² Altyapı</div></div>")
        html.append(f"      <div class='kpi-card'><div class='kpi-title'>DOP Kesinti Oranı</div><div class='kpi-value'>{dop_val}</div><div class='kpi-sub'>Yasal Tavan: %45</div></div>")
        html.append("    </div>")

        # 1. Arazi Kullanım Dengesi Tablosu
        html.append('    <h2>1. Arazi Kullanımı Dağılımı ve Fonksiyon Dengesi</h2>')
        if rows:
            html.append("    <table>")
            html.append('      <thead><tr><th>Fonksiyon Adı</th><th>Üst Konu Grubu</th><th>Alan (m²)</th><th>Alan (Ha)</th><th>Oran (%)</th><th>Nitelik</th></tr></thead>')
            html.append("      <tbody>")
            for r in rows:
                badge_cls = "badge-info" if r.kamusal_mi else "badge-success"
                tip_txt = 'Donatı / Kamusal' if r.kamusal_mi else 'Kentsel Gelişme'
                html.append(f"        <tr><td><strong>{_html.escape(str(display_label(r.fonksiyon_adi)))}</strong></td><td>{_html.escape(str(display_label(r.ust_grup or '-')))}</td><td>{r.alan_m2:,.2f}</td><td>{r.alan_hektar:.4f}</td><td>%{r.yuzde:.2f}</td><td><span class='badge {badge_cls}'>{tip_txt}</span></td></tr>")
            html.append("      </tbody>")
            html.append("    </table>")
        else:
            html.append('    <p>İncelenen katmanda geçerli mekânsal fonksiyon kaydı tespit edilemedi.</p>')

        # 2. MPYY EK-2 Donatı Yeterlilik Matrisi
        if amenity_results:
            html.append('    <h2>2. MPYY EK-2 Kentsel Donatı Standartları Yeterlilik Analizi</h2>')
            html.append("    <table>")
            html.append('      <thead><tr><th>Donatı Kategorisi</th><th>Kişi Başı Asgari (m²)</th><th>Mevzuat İhtiyacı (m²)</th><th>Planda Ayrılan (m²)</th><th>Kişi Başı Fiili (m²)</th><th>Durum</th></tr></thead>')
            html.append("      <tbody>")
            for a in amenity_results:
                a_name, a_ok, a_std, a_req, a_cur, a_pc = _amenity_tuple(a)
                status_cls = "badge-success" if a_ok else "badge-danger"
                status_txt = 'YETERLİ' if a_ok else 'YETERSİZ'
                html.append(
                    f"        <tr><td>{_html.escape(str(display_label(a_name)))}</td><td>{a_std:.2f} m²</td><td>{a_req:,.1f} m²</td>"
                    f"<td>{a_cur:,.1f} m²</td><td>{a_pc:.2f} m²</td>"
                    f"<td><span class='badge {status_cls}'>{status_txt}</span></td></tr>"
                )
            html.append("      </tbody>")
            html.append("    </table>")

        # 3. İmar Kapasitesi ve Projeksiyon Nüfusu
        if capacity_summary:
            html.append('    <h2>3. İmar Kapasitesi ve Projeksiyon Nüfusu Modellemesi</h2>')
            html.append("    <table>")
            html.append('      <thead><tr><th>Gösterge</th><th>Değer</th><th>Açıklama</th></tr></thead>')
            html.append("      <tbody>")
            html.append(f'        <tr><td>Konut Zonlama Alanı</td><td>{cap_konut_m2:,.2f} m²</td><td>Konut ve Karma Fonksiyonlar</td></tr>')
            html.append(f'        <tr><td>Ortalama Ağırlıklı Emsal (KAKS)</td><td>{cap_kaks:.2f}</td><td>Plan yoğunluk katsayısı</td></tr>')
            html.append(f'        <tr><td>Toplam İnşaat Alanı</td><td>{cap_const_m2_num:,.2f} m²</td><td>Konut yapılaşma hacmi</td></tr>')
            html.append(f'        <tr><td>Öngörülen Konut / Bağımsız Bölüm</td><td>{cap_units:,} birim</td><td>100 m² ortalama birim</td></tr>')
            html.append(f'        <tr><td>Öngörülen Kapasite Nüfusu</td><td><strong>{int(cap_pop or 0):,} Kişi</strong></td><td>3.2 kişi/hane halkı büyüklüğü</td></tr>')
            html.append("      </tbody>")
            html.append("    </table>")

        # 4. İmar Kanunu Madde 18 DOP Özeti
        if dop_summary:
            html.append('    <h2>4. 3194 Sayılı İmar Kanunu Madde 18 DOP Dengesi</h2>')
            html.append("    <table>")
            html.append('      <thead><tr><th>Parametre</th><th>Miktar</th><th>Yasal Değerlendirme</th></tr></thead>')
            html.append("      <tbody>")
            html.append(f'        <tr><td>Toplam Kadastro Alanı</td><td>{float(getattr(dop_summary, "toplam_kadastro_m2", 0.0)):,.2f} m²</td><td>İşleme giren mülkiyetler</td></tr>')
            html.append(f'        <tr><td>Toplam Terk / Kamusal Alan</td><td>{float(getattr(dop_summary, "toplam_terk_m2", 0.0)):,.2f} m²</td><td>Yol, park, okul, sağlık donatıları</td></tr>')
            html.append(f'        <tr><td>Hesaplanan DOP Oranı</td><td><strong>%{float(dop_pct_num or 0.0):.2f}</strong></td><td>Yasal Sınır: %45.00</td></tr>')
            dop_badge = "badge-success" if not dop_exceeded else "badge-danger"
            dop_stat = 'YASAL TAVAN AŞILMADI (UYGUN)' if not dop_exceeded else 'YASAL SINIR AŞILDI (KOP / KAMULAŞTIRMA GEREKLİ)'
            html.append(f"        <tr><td>Mevzuat Uygunluğu</td><td colspan='2'><span class='badge {dop_badge}'>{dop_stat}</span></td></tr>")
            html.append("      </tbody>")
            html.append("    </table>")

        # 5. PAİY Parsel Yapılaşabilirlik ve İfraz-Tevhit
        if compliance_summary:
            html.append('    <h2>5. PAİY Yapılaşabilirlik ve İfraz-Tevhit Denetimi</h2>')
            html.append("    <table>")
            html.append('      <thead><tr><th>Parsel Sınıfı</th><th>Adet</th><th>Oran (%)</th><th>Yasal Durum</th></tr></thead>')
            html.append("      <tbody>")
            b_pct = round((comp_buildable / max(comp_total, 1)) * 100.0, 1)
            t_pct = round((comp_tevhid / max(comp_total, 1)) * 100.0, 1)
            i_pct = round((comp_ifraz / max(comp_total, 1)) * 100.0, 1)
            html.append(f"        <tr><td>Yapılaşabilir Müstakil Parseller</td><td>{comp_buildable}</td><td>%{b_pct}</td><td><span class='badge badge-success'>Ruhsata Uygun</span></td></tr>")
            html.append(f"        <tr><td>Tevhit Zorunlu Parseller (Yetersiz Cephe/Derinlik)</td><td>{comp_tevhid}</td><td>%{t_pct}</td><td><span class='badge badge-warning'>PAİY Md. 15-16 Tevhit Şartı</span></td></tr>")
            html.append(f"        <tr><td>İfraz Edilebilir Geniş Parseller</td><td>{comp_ifraz}</td><td>%{i_pct}</td><td><span class='badge badge-info'>Bölünmeye Müsait</span></td></tr>")
            html.append("      </tbody>")
            html.append("    </table>")

        # 6. Standart Pafta İndeksi
        if pafta_summary:
            html.append('    <h2>6. Standart İmar Planı Pafta İndeksi (BÖHYY / MPYY)</h2>')
            html.append(f'    <p>Toplam <strong>{pafta_summary.toplam_pafta_sayisi}</strong> pafta ({pafta_summary.satir_sayisi} satır &times; {pafta_summary.sutun_sayisi} sütun). Kapsanan Net Plan Alanı: <strong>{pafta_summary.kapsanan_plan_alani_m2:,.1f} m²</strong>.</p>')

        # 7. Plan Notları Özeti
        if plan_notes:
            html.append('    <h2>7. İmar Planı Notları ve Uygulama Esasları</h2>')
            html.append(f"    <p>Tespit Edilen Fonksiyon Grupları: <strong>{_html.escape(', '.join(map(display_label, plan_notes.tespit_edilen_kategoriler)))}</strong></p>")
            html.append('    <h3>Genel Hükümler</h3><ol>')
            for gh in plan_notes.genel_hukumler[:5]:
                html.append(f"      <li>{_html.escape(str(gh))}</li>")
            html.append("    </ol>")

        html.append("    <div class='footer'>Raporlama Motoru: <strong>PlanX MPYY Studio</strong> &bull; Yazar: <strong>Geophilo</strong></div>")
        html.extend(["  </div>", "</body>", "</html>"])

        html_file = out_folder / "plan_aciklama_raporu_kapsamli.html"
        html_file.write_text("\n".join(html), encoding="utf-8")

        # Build Markdown Document
        md: list[str] = [
            f"# {upper_tr(report_title)}",
            f'**Ölçek:** {plan_scale} | **Koordinat sistemi:** {crs_authid} | **Mevzuat:** Mekânsal Planlar Yapım Yönetmeliği (MPYY)',
            "",
            "---",
            "",
            '## 1. YÖNETİCİ ÖZETİ VE TEMEL GÖSTERGELER',
            f'- **Toplam plan alanı:** {total_area_m2:,.2f} m² ({total_area_m2 / 10000.0:.2f} ha)',
            f'- **Kamu donatı alanı:** {public_area_m2:,.2f} m² (%{public_pct})',
            f'- **Tahmini öngörülen nüfus:** {pop_val} Kişi',
            f'- **Tahmini toplam inşaat alanı:** {const_m2}',
            f'- **DOP kesinti oranı:** {dop_val}',
            "",
            '## 2. ARAZİ KULLANIM DAĞILIMI VE DENGESİ',
            '| Fonksiyon adı | Üst grup | Alan (m²) | Alan (ha) | Pay (%) | Tür |',
            "| :--- | :--- | :---: | :---: | :---: | :--- |",
        ]
        for r in rows:
            tip_str = 'Kamusal Donatı' if r.kamusal_mi else 'Kentsel Gelişme'
            md.append(f"| {display_label(r.fonksiyon_adi)} | {display_label(r.ust_grup or '-')} | {r.alan_m2:,.2f} | {r.alan_hektar:.4f} | %{r.yuzde:.2f} | {tip_str} |")

        if amenity_results:
            md.extend([
                "",
                '## 3. MPYY EK-2 DONATI YETERLİLİK ANALİZİ',
                '| Donatı kategorisi | Asgari standart (m²/kişi) | Gerekli alan (m²) | Ayrılan alan (m²) | Fiilî standart (m²/kişi) | Durum |',
                "| :--- | :---: | :---: | :---: | :---: | :--- |",
            ])
            for a in amenity_results:
                a_name, a_ok, a_std, a_req, a_cur, a_pc = _amenity_tuple(a)
                st_txt = 'YETERLİ' if a_ok else 'YETERSİZ'
                md.append(f"| {display_label(a_name)} | {a_std:.2f} | {a_req:,.1f} | {a_cur:,.1f} | {a_pc:.2f} | {st_txt} |")

        if capacity_summary:
            md.extend([
                "",
                '## 4. İMAR KAPASİTESİ VE NÜFUS PROJEKSİYONU',
                f'- **Konut imar alanı:** {cap_konut_m2:,.2f} m²',
                f'- **Ortalama emsal (KAKS):** {cap_kaks:.2f}',
                f'- **Toplam inşaat alanı:** {cap_const_m2_num:,.2f} m²',
                f'- **Tahmini konut sayısı:** {cap_units:,}',
                f'- **Tahmini öngörülen nüfus:** {int(cap_pop or 0):,} Kişi',
            ])

        if dop_summary:
            md.extend([
                "",
                '## 5. İMAR KANUNU 18. MADDE DOP DENGESİ',
                f'- **Toplam kadastro alanı:** {float(getattr(dop_summary, "toplam_kadastro_m2", 0.0)):,.2f} m²',
                f'- **Toplam terk alanı:** {float(getattr(dop_summary, "toplam_terk_m2", 0.0)):,.2f} m²',
                f'- **Hesaplanan DOP oranı:** %{float(dop_pct_num or 0.0):.2f}',
                f"- **Mevzuata uygunluk:** {('Yasal Tavan Aşılmadı (Uygun)' if not dop_exceeded else 'Yasal Tavan Aşıldı (KOP / Kamulaştırma Zorunlu)')}",
            ])

        if compliance_summary:
            md.extend([
                "",
                '## 6. PAİY PARSEL YAPILAŞABİLİRLİK DEĞERLENDİRMESİ',
                f'- **Toplam parsel sayısı:** {comp_total}',
                f'- **Bağımsız yapılaşabilir parseller:** {comp_buildable}',
                f'- **Tevhit gerektiren parseller:** {comp_tevhid}',
                f'- **İfraza uygun parseller:** {comp_ifraz}',
            ])

        if plan_notes:
            md.extend([
                "",
                '## 7. İMAR PLANI NOTLARI ÖZETİ',
                '### Genel hükümler:',
            ])
            for gh in plan_notes.genel_hukumler[:5]:
                md.append(f"- {gh}")

        md.extend([
            "",
            "---",
            '*Rapor üreticisi: PlanX MPYY Studio | Yazar: Geophilo*',
        ])

        md_file = out_folder / "plan_aciklama_raporu.md"
        md_file.write_text("\n".join(md), encoding="utf-8")

        return {
            "html_report": str(html_file),
            "markdown_report": str(md_file),
            "csv_balance": str(csv_path),
            "total_area_m2": total_area_m2,
        }
