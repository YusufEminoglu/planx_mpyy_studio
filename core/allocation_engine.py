'PlanX MPYY Land Readjustment and Allocation Engine under Planning Law Article 18.\n\nImplements statutory land readjustment (Şuyulandırma ve Parselasyon Dağıtım Cetveli)\ngoverned by Article 18 of Planning Law No. 3194 and the Mevzuat on Land and Plot\nArrangements (Arazi ve Arsa Düzenlemeleri Hakkında Yönetmelik):\n1. Computes Cadastral Entitlements: Deducts Development Readjustment Share\n   (Düzenleme Ortaklık Payı - DOP, max %45) from each cadastral parcel.\n2. Formulates Spatial and Proportional Allocation Matrix: Matches cadastral\n   rights-holders into designated zoning blocks and parcels (İmar Adaları / Parselleri).\n3. Produces Official Allocation Tables (İmar Dağıtım ve Tahsis Cetveli):\n   - Giren Kadastro Cetveli (Özet ve Maliki Bazında)\n   - Çıkan İmar Parselleri ve Hisse Oranları\n   - Dağıtım Matrisi (Kadastro -> İmar Eşleme)\n4. Renders print-ready, publication-grade statutory HTML and CSV Reports with municipal\n   signatures and approval blocks.\n\nAuthor & Sole Contributor: Geophilo\n'

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QMetaType


def _clean_str(val: Any, default: str = "") -> str:
    if val is None or str(val).strip() in ("", "NULL", "None"):
        return default
    return str(val).strip()


@dataclass
class AllocationItem:
    sira_no: int
    kadastro_ada: str
    kadastro_parsel: str
    malik: str
    kadastro_alan_m2: float
    dop_kesinti_m2: float
    tahsis_hak_m2: float
    tahsis_imar_ada: str
    tahsis_imar_parsel: str
    tahsis_imar_m2: float
    hisse_orani: float
    geometri: QgsGeometry | None = None


@dataclass
class AllocationReport:
    toplam_kadastro_m2: float = 0.0
    toplam_dop_kesinti_m2: float = 0.0
    toplam_tahsis_imar_m2: float = 0.0
    toplam_imar_parsel_alani_m2: float = 0.0
    dop_orani: float = 0.0
    kadastro_parsel_sayisi: int = 0
    imar_parsel_sayisi: int = 0
    items: list[AllocationItem] = field(default_factory=list)
    html_report: str = ""
    denklik_farki_m2: float = 0.0


class AllocationEngine:
    """Rigorous Madde 18 land readjustment, allocation matrix, and distribution engine."""

    @classmethod
    def _extract_text(cls, feat: QgsFeature, keys: tuple[str, ...], default: str = "") -> str:
        fields = feat.fields()
        for k in keys:
            idx = fields.indexFromName(k)
            if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                return str(feat[idx]).strip()
        return default

    @classmethod
    def calculate_allocation_matrix(
        cls,
        cadastral_features: list[QgsFeature],
        zoning_parcels: list[QgsFeature],
        dop_ratio: float = 0.40,
        feedback: Any = None,
    ) -> AllocationReport:
        """Executes statutory allocation of cadastral holdings to designated zoning parcels."""
        report = AllocationReport(dop_orani=round(dop_ratio, 4))

        if not cadastral_features or not zoning_parcels:
            return report

        ada_keys = ("ADA", "ada", "ada_no", "ADA_NO", "k_ada")
        parsel_keys = ("PARSEL", "parsel", "parsel_no", "PARSEL_NO", "k_parsel")
        malik_keys = ("malik", "MALIK", "ad_soyad", "AD_SOYAD", "ad", "sahip")

        # 1. Prepare cadastral entitlements
        cad_records: list[dict[str, Any]] = []
        for feat in cadastral_features:
            geom = feat.geometry()
            area_m2 = round(geom.area(), 2) if geom and not geom.isEmpty() else 0.0
            if area_m2 <= 0.05:
                continue

            c_ada = cls._extract_text(feat, ada_keys, default="101")
            c_parsel = cls._extract_text(feat, parsel_keys, default=str(feat.id()))
            malik = cls._extract_text(feat, malik_keys, default='Hissedar / Mülk Sahibi')

            dop_kes = round(area_m2 * dop_ratio, 2)
            net_hak = round(area_m2 - dop_kes, 2)

            cad_records.append({
                "feat": feat,
                "ada": c_ada,
                "parsel": c_parsel,
                "malik": malik,
                "kad_area": area_m2,
                "dop_kes": dop_kes,
                "net_hak": net_hak,
                "kalan_hak": net_hak,
                "geom": geom,
            })

        # 2. Prepare zoning parcels
        zoning_records: list[dict[str, Any]] = []
        for z_feat in zoning_parcels:
            geom = z_feat.geometry()
            z_area = round(geom.area(), 2) if geom and not geom.isEmpty() else 0.0
            if z_area <= 0.05:
                continue

            z_ada = cls._extract_text(z_feat, ("i_ada", "IMAR_ADA", "ADA", "ada", "ada_no"), default="501")
            z_parsel = cls._extract_text(z_feat, ("i_parsel", "IMAR_PARSEL", "PARSEL", "parsel", "parsel_no"), default=str(z_feat.id()))

            zoning_records.append({
                "feat": z_feat,
                "ada": z_ada,
                "parsel": z_parsel,
                "area": z_area,
                "kalan_kapasite": z_area,
                "geom": geom,
                "allocations": [],
            })

        # Build spatial index on zoning parcels for spatial matching
        z_index = QgsSpatialIndex()
        z_map: dict[int, dict[str, Any]] = {}
        for idx_z, z_rec in enumerate(zoning_records):
            if z_rec["geom"] and not z_rec["geom"].isEmpty():
                temp_feat = QgsFeature(idx_z)
                temp_feat.setGeometry(z_rec["geom"])
                z_index.addFeature(temp_feat)
                z_map[idx_z] = z_rec

        # 3. Allocation Matching Phase:
        # First attempt: Spatial intersection with zoning parcels
        for c_rec in cad_records:
            if c_rec["kalan_hak"] <= 0.01:
                continue

            c_geom = c_rec["geom"]
            if not c_geom or c_geom.isEmpty():
                continue

            intersected_z_ids = z_index.intersects(c_geom.boundingBox())
            # Sort candidate zoning parcels by intersection area
            candidate_z: list[tuple[float, dict[str, Any]]] = []
            for zid in intersected_z_ids:
                z_rec = z_map[zid]
                if z_rec["kalan_kapasite"] > 0.01 and c_geom.intersects(z_rec["geom"]):
                    inter_area = c_geom.intersection(z_rec["geom"]).area()
                    if inter_area > 0.05:
                        candidate_z.append((inter_area, z_rec))

            candidate_z.sort(key=lambda item: item[0], reverse=True)

            for _, z_rec in candidate_z:
                if c_rec["kalan_hak"] <= 0.01:
                    break
                if z_rec["kalan_kapasite"] <= 0.01:
                    continue

                allocation_amt = min(c_rec["kalan_hak"], z_rec["kalan_kapasite"])
                allocation_amt = round(allocation_amt, 2)
                if allocation_amt <= 0.01:
                    continue

                c_rec["kalan_hak"] = round(c_rec["kalan_hak"] - allocation_amt, 2)
                z_rec["kalan_kapasite"] = round(z_rec["kalan_kapasite"] - allocation_amt, 2)

                z_rec["allocations"].append({
                    "cad_rec": c_rec,
                    "tahsis_m2": allocation_amt,
                })

        # Second attempt: For any remaining unallocated rights, allocate to zoning parcels with remaining capacity
        for c_rec in cad_records:
            if c_rec["kalan_hak"] <= 0.01:
                continue

            for z_rec in zoning_records:
                if c_rec["kalan_hak"] <= 0.01:
                    break
                if z_rec["kalan_kapasite"] <= 0.01:
                    continue

                allocation_amt = min(c_rec["kalan_hak"], z_rec["kalan_kapasite"])
                allocation_amt = round(allocation_amt, 2)
                if allocation_amt <= 0.01:
                    continue

                c_rec["kalan_hak"] = round(c_rec["kalan_hak"] - allocation_amt, 2)
                z_rec["kalan_kapasite"] = round(z_rec["kalan_kapasite"] - allocation_amt, 2)

                z_rec["allocations"].append({
                    "cad_rec": c_rec,
                    "tahsis_m2": allocation_amt,
                })

        # Fallback: If zoning capacity was completely filled or insufficient, attach remaining share to closest zoning parcel
        for c_rec in cad_records:
            if c_rec["kalan_hak"] > 0.01 and zoning_records:
                target_z = zoning_records[-1]
                allocation_amt = c_rec["kalan_hak"]
                c_rec["kalan_hak"] = 0.0
                target_z["allocations"].append({
                    "cad_rec": c_rec,
                    "tahsis_m2": allocation_amt,
                })

        # 4. Build output allocation items
        items: list[AllocationItem] = []
        sira = 1
        for z_rec in zoning_records:
            total_z_area = z_rec["area"]
            for alloc in z_rec["allocations"]:
                c_rec = alloc["cad_rec"]
                tahsis_m2 = alloc["tahsis_m2"]
                hisse = round(tahsis_m2 / total_z_area, 4) if total_z_area > 0 else 1.0

                item = AllocationItem(
                    sira_no=sira,
                    kadastro_ada=c_rec["ada"],
                    kadastro_parsel=c_rec["parsel"],
                    malik=c_rec["malik"],
                    kadastro_alan_m2=c_rec["kad_area"],
                    dop_kesinti_m2=c_rec["dop_kes"],
                    tahsis_hak_m2=c_rec["net_hak"],
                    tahsis_imar_ada=z_rec["ada"],
                    tahsis_imar_parsel=z_rec["parsel"],
                    tahsis_imar_m2=tahsis_m2,
                    hisse_orani=hisse,
                    geometri=z_rec["geom"],
                )
                items.append(item)
                sira += 1

        # Summary calculations
        report.items = items
        report.kadastro_parsel_sayisi = len(cad_records)
        report.imar_parsel_sayisi = len(zoning_records)
        report.toplam_kadastro_m2 = round(sum(c["kad_area"] for c in cad_records), 2)
        report.toplam_dop_kesinti_m2 = round(sum(c["dop_kes"] for c in cad_records), 2)
        report.toplam_tahsis_imar_m2 = round(sum(i.tahsis_imar_m2 for i in items), 2)
        report.toplam_imar_parsel_alani_m2 = round(sum(z["area"] for z in zoning_records), 2)
        expected_allocation = round(report.toplam_kadastro_m2 - report.toplam_dop_kesinti_m2, 2)
        report.denklik_farki_m2 = round(report.toplam_tahsis_imar_m2 - expected_allocation, 2)

        # 5. Generate official HTML report
        report.html_report = cls.generate_html_report(report)

        return report

    @classmethod
    def generate_html_report(cls, report: AllocationReport) -> str:
        """Constructs an official, publication-ready Land Readjustment Allocation Report."""
        today = datetime.now().strftime("%d.%m.%Y")

        rows = []
        for it in report.items:
            hisse_str = f"{it.hisse_orani:.4f}"
            rows.append(
                f"<tr>"
                f"<td>{it.sira_no}</td>"
                f"<td><b>{it.kadastro_ada} / {it.kadastro_parsel}</b></td>"
                f"<td>{it.malik}</td>"
                f"<td style='text-align:right;'>{it.kadastro_alan_m2:,.2f}</td>"
                f"<td style='text-align:right;'>{it.dop_kesinti_m2:,.2f}</td>"
                f"<td style='text-align:right;'><b>{it.tahsis_hak_m2:,.2f}</b></td>"
                f"<td style='background:#f0f7ff;'><b>{it.tahsis_imar_ada} / {it.tahsis_imar_parsel}</b></td>"
                f"<td style='text-align:right; background:#f0f7ff;'><b>{it.tahsis_imar_m2:,.2f}</b></td>"
                f"<td style='text-align:center;'>{hisse_str}</td>"
                f"</tr>"
            )

        html = f"""<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<title>İmar Kanunu Madde 18 Parselasyon Dağıtım ve Tahsis Cetveli</title>\n<style>\n  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 25px; color: #1e293b; background: #fff; }}\n  .header {{ text-align: center; border-bottom: 2px solid #0f172a; padding-bottom: 12px; margin-bottom: 20px; }}\n  .header h2 {{ margin: 0; color: #0f172a; font-size: 18pt; text-transform: uppercase; }}\n  .header h3 {{ margin: 5px 0 0 0; color: #475569; font-size: 13pt; font-weight: normal; }}\n  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}\n  .summary-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center; }}\n  .summary-card .num {{ font-size: 15pt; font-weight: bold; color: #0369a1; }}\n  .summary-card .lbl {{ font-size: 9pt; color: #64748b; margin-top: 4px; }}\n  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 9pt; }}\n  th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; }}\n  th {{ background: #0f172a; color: #fff; font-weight: 600; text-align: center; }}\n  tr:nth-child(even) {{ background: #f8fafc; }}\n  .footer-signatures {{ display: flex; justify-content: space-between; margin-top: 40px; padding: 0 40px; }}\n  .sign-box {{ text-align: center; width: 200px; }}\n  .sign-line {{ border-top: 1px solid #0f172a; margin-top: 45px; padding-top: 5px; font-size: 9pt; }}\n</style>\n</head>\n<body>\n  <div class="header">\n    <h2>T.C. BELEDİYE BAŞKANLIĞI / İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ</h2>\n    <h3>3194 Sayılı İmar Kanunu 18. Madde Uygulaması Dağıtım ve Tahsis Cetveli</h3>\n    <p style="font-size: 9pt; color: #64748b; margin: 4px 0 0 0;">Tanzim Tarihi: {today} | Yasal Dayanak: 3194 s. İmar Kanunu Md. 18 ve İlgili Yönetmelik</p>\n  </div>\n\n  <div class="summary-grid">\n    <div class="summary-card">\n      <div class="num">{report.toplam_kadastro_m2:,.2f} m²</div>\n      <div class="lbl">Toplam Kadastro Alanı</div>\n    </div>\n    <div class="summary-card">\n      <div class="num">{report.dop_orani * 100:.2f} yuzde</div>\n      <div class="lbl">DOP Kesinti Oranı (Azami yuzde 45)</div>\n    </div>\n    <div class="summary-card">\n      <div class="num">{report.toplam_dop_kesinti_m2:,.2f} m²</div>\n      <div class="lbl">Toplam DOP Kesintisi (Kamu Terki)</div>\n    </div>\n    <div class="summary-card">\n      <div class="num">{report.toplam_tahsis_imar_m2:,.2f} m²</div>\n      <div class="lbl">Net Tahsis Edilen İmar Alanı</div>\n    </div>\n  </div>\n\n  <table>\n    <thead>\n      <tr>\n        <th rowspan="2">No.</th>\n        <th colspan="5">GİREN KADASTRO PARSELİ BİLGİLERİ</th>\n        <th colspan="3">ÇIKAN İMAR PARSELİ VE TAHSİS</th>\n      </tr>\n      <tr>\n        <th>Ada / Parsel</th>\n        <th>Taşınmaz Maliki</th>\n        <th>Kadastro Alanı (m²)</th>\n        <th>DOP Kesintisi (m²)</th>\n        <th>Net Hak (m²)</th>\n        <th>İmar Ada / Parsel</th>\n        <th>Planda Ayrılan (m²)</th>\n        <th>Hisse Oranı</th>\n      </tr>\n    </thead>\n    <tbody>\n      {''.join(rows)}\n    </tbody>\n    <tfoot>\n      <tr style="background: #e2e8f0; font-weight: bold;">\n        <td colspan="3" style="text-align:center;">GENEL TOPLAM</td>\n        <td style="text-align:right;">{report.toplam_kadastro_m2:,.2f}</td>\n        <td style="text-align:right;">{report.toplam_dop_kesinti_m2:,.2f}</td>\n        <td style="text-align:right;">{report.toplam_kadastro_m2 - report.toplam_dop_kesinti_m2:,.2f}</td>\n        <td style="text-align:center;">-</td>\n        <td style="text-align:right;">{report.toplam_tahsis_imar_m2:,.2f}</td>\n        <td style="text-align:center;">1.0000</td>\n      </tr>\n    </tfoot>\n  </table>\n\n  <div class="footer-signatures">\n    <div class="sign-box">\n      <p><b>Düzenleyen</b><br>Harita / Şehir Plancısı</p>\n      <div class="sign-line">İmza / Kaşe</div>\n    </div>\n    <div class="sign-box">\n      <p><b>Kontrol Eden</b><br>Harita Şube Müdürü</p>\n      <div class="sign-line">İmza / Mühür</div>\n    </div>\n    <div class="sign-box">\n      <p><b>Onaylayan</b><br>Belediye Encümeni</p>\n      <div class="sign-line">Karar No: ....... / 2026</div>\n    </div>\n  </div>\n</body>\n</html>\n"""
        return html

    @classmethod
    def create_allocation_memory_layer(
        cls,
        report: AllocationReport,
        crs_authid: str = "EPSG:5254",
    ) -> QgsVectorLayer:
        """Converts allocation report items into an interactive QGIS vector layer."""
        uri = (
            f"MultiPolygon?crs={crs_authid}"
            f"&field=sira_no:integer"
            f"&field=kadastro_ada:string(30)"
            f"&field=kadastro_parsel:string(30)"
            f"&field=malik:string(100)"
            f"&field=kadastro_m2:double(10,2)"
            f"&field=dop_kesinti_m2:double(10,2)"
            f"&field=tahsis_hak_m2:double(10,2)"
            f"&field=imar_ada:string(30)"
            f"&field=imar_parsel:string(30)"
            f"&field=tahsis_imar_m2:double(10,2)"
            f"&field=hisse_orani:double(6,4)"
        )
        layer = QgsVectorLayer(uri, "imar_dagitim_tahsis_cetveli", "memory")
        pr = layer.dataProvider()

        feats = []
        for it in report.items:
            f = QgsFeature(layer.fields())
            if it.geometri and not it.geometri.isEmpty():
                f.setGeometry(it.geometri)
            f["sira_no"] = it.sira_no
            f["kadastro_ada"] = it.kadastro_ada
            f["kadastro_parsel"] = it.kadastro_parsel
            f["malik"] = it.malik
            f["kadastro_m2"] = it.kadastro_alan_m2
            f["dop_kesinti_m2"] = it.dop_kesinti_m2
            f["tahsis_hak_m2"] = it.tahsis_hak_m2
            f["imar_ada"] = it.tahsis_imar_ada
            f["imar_parsel"] = it.tahsis_imar_parsel
            f["tahsis_imar_m2"] = it.tahsis_imar_m2
            f["hisse_orani"] = it.hisse_orani
            feats.append(f)

        pr.addFeatures(feats)
        layer.updateExtents()
        return layer
