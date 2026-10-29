"PlanX MPYY Urban Transformation Financial & Floor-Area Feasibility Engine.\n\nImplements financial, spatial, and entitlement feasibility modeling under Law No. 6306\n(6306 Sayılı Afet Riski Altındaki Alanların Dönüştürülmesi Hakkında Kanun):\n1. Evaluates Existing Built Stock (Mevcut Durum): Calculates current gross building area,\n   dwelling units, and current site coverage.\n2. Models Öneri Zoning Capacity (Yeni İmar Durumu): Computes proposed floor-area rights\n   (KAKS/Emsal) and allowable licensed construction space.\n3. Computes Contractor & Property Owner Entitlement Shares (Hakediş & Paylaşım):\n   - Contractor Share Ratio (Müteahhit Paylaşım Oranı, e.g. %45)\n   - Property Owners' Net Entitlement Area (Hak Sahiplerine Kalan İnşaat Alanı)\n   - Independent Unit Entitlement Coefficient (Hakediş Katsayısı = Hak Sahipleri / Mevcut)\n   - Floor Area Surplus / Deficit (Alan Fazlası veya Borçlanma Gerektiren Alan Açığı)\n4. Financial Feasibility Analysis: Evaluates total development cost (m² maliyet), projected\n   gross sales revenue (m² satış değeri), and developer margin / financial viability.\n5. Produces publication-grade, print-ready HTML and CSV transformation feasibility reports.\n\nAuthor & Sole Contributor: Geophilo\n"

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import html
from typing import Any

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsSpatialIndex,
    QgsVectorLayer,
)

from .attr_utils import (
    first_float,
    first_int,
    first_text,
    parse_floor_count,
    reindex_features,
)


@dataclass
class TransformationFeasibilityItem:
    fid: Any
    ada_parsel: str
    parsel_alani_m2: float
    mevcut_bina_adedi: int
    mevcut_insaat_alani_m2: float
    mevcut_bagimsiz_bolum: int
    yeni_kaks: float
    yeni_insaat_alani_m2: float
    muteahhit_payi_orani: float
    muteahhit_insaat_m2: float
    hak_sahibi_insaat_m2: float
    hakedis_katsayisi: float
    alan_farki_m2: float
    fizibilite_durumu: str  # 'ALAN_FAZLASI_POZITIF', 'DENGEDE', 'ALAN_ACIGI_BORCLANMA'
    tahmini_maliyet_tl: float
    tahmini_ciro_tl: float
    tahmini_kar_zarar_tl: float
    geometri: QgsGeometry | None = None


@dataclass
class TransformationFeasibilitySummary:
    toplam_parsel_sayisi: int = 0
    toplam_parsel_alani_m2: float = 0.0
    toplam_mevcut_insaat_m2: float = 0.0
    toplam_yeni_insaat_m2: float = 0.0
    toplam_muteahhit_m2: float = 0.0
    toplam_hak_sahibi_m2: float = 0.0
    ortalama_hakedis_katsayisi: float = 0.0
    toplam_maliyet_tl: float = 0.0
    toplam_ciro_tl: float = 0.0
    net_finansal_bakiye_tl: float = 0.0
    fizibilite_yorumu: str = ""
    items: list[TransformationFeasibilityItem] = field(default_factory=list)
    html_report: str = ""


class UrbanTransformationFeasibilityEngine:
    """Rigorous financial and floor-area feasibility model for urban renewal under Law 6306."""

    @classmethod
    def _extract_float(cls, feat: QgsFeature, keys: tuple[str, ...], default: float = 0.0) -> float:
        val = first_float(feat, keys, default=None)
        if val is not None and val >= 0.0:
            return val
        return default

    @classmethod
    def _extract_int(cls, feat: QgsFeature, keys: tuple[str, ...], default: int = 1) -> int:
        val = first_int(feat, keys, default=None)
        if val is not None and val >= 0:
            return val
        return default

    @classmethod
    def _extract_text(cls, feat: QgsFeature, keys: tuple[str, ...], default: str = "") -> str:
        return first_text(feat, keys, default=default)

    @classmethod
    def evaluate_feasibility(
        cls,
        parcel_features: list[QgsFeature],
        building_features: list[QgsFeature] | None = None,
        contractor_ratio: float = 0.45,
        unit_construction_cost_tl: float = 25000.0,
        unit_sale_price_tl: float = 50000.0,
        default_new_kaks: float = 2.0,
        feedback: Any = None,
    ) -> tuple[list[TransformationFeasibilityItem], TransformationFeasibilitySummary]:
        """Calculates area entitlements, financial balances, and feasibility classifications."""
        items: list[TransformationFeasibilityItem] = []
        summary = TransformationFeasibilitySummary()

        if not parcel_features:
            return items, summary

        # Spatial index for buildings if provided (reindex to prevent fid<=0 collisions)
        b_index: QgsSpatialIndex | None = None
        b_map: dict[int, QgsFeature] = {}
        has_building_layer = building_features is not None and len(building_features) > 0
        if has_building_layer:
            b_index = QgsSpatialIndex()
            for bf in reindex_features(building_features):
                if bf.hasGeometry() and not bf.geometry().isEmpty():
                    b_index.addFeature(bf)
                    b_map[bf.id()] = bf

        total_parcels = len(parcel_features)

        for idx, p_feat in enumerate(parcel_features):
            if feedback and feedback.isCanceled():
                break

            geom = p_feat.geometry()
            area_m2 = round(geom.area(), 2) if geom and not geom.isEmpty() else 0.0
            if area_m2 <= 0.05:
                continue

            ada = cls._extract_text(p_feat, ("ADA", "ada", "ada_no"), default="100")
            parsel = cls._extract_text(p_feat, ("PARSEL", "parsel", "parsel_no"), default=str(p_feat.id()))
            ada_parsel = f"{ada}/{parsel}"

            # 1. Existing built area (from building geometries or attributes)
            mevcut_insaat = 0.0
            mevcut_bina = 0
            mevcut_bb = 0

            if b_index and geom:
                candidate_b_ids = b_index.intersects(geom.boundingBox())
                for bid in candidate_b_ids:
                    bf = b_map[bid]
                    bg = bf.geometry()
                    if bg and bg.intersects(geom):
                        inter_area = bg.intersection(geom).area()
                        if bg.area() > 0 and (inter_area / bg.area()) >= 0.40:
                            mevcut_bina += 1
                            raw_kat = first_text(bf, ("B_KAT", "KatAdedi", "kat", "kat_adedi", "KAT"))
                            kat = parse_floor_count(raw_kat, default=1) if raw_kat else 1
                            if kat <= 0:
                                kat = 1
                            mevcut_insaat += round(bg.area() * kat, 2)
                            bb = first_int(bf, ("B_B_BOLUM", "bagimsiz_bolum", "bagimsiz_bolum_sayisi"), default=None)
                            mevcut_bb += bb if (bb is not None and bb > 0) else kat

            if mevcut_bina == 0 and mevcut_insaat <= 0.0:
                attr_insaat = first_float(
                    p_feat,
                    ("mevcut_insaat_m2", "insaat_m2", "toplam_insaat_alani_m2"),
                    default=None,
                )
                if attr_insaat is not None and attr_insaat >= 0.0:
                    mevcut_insaat = attr_insaat
                    mevcut_bina = cls._extract_int(
                        p_feat, ("yapi_adedi", "bina_sayisi", "P_YAPI_ADET"),
                        default=(1 if mevcut_insaat > 0 else 0),
                    )
                    mevcut_bb = cls._extract_int(
                        p_feat,
                        ("bagimsiz_bolum_sayisi", "P_BAGIMSIZ_BOLUM"),
                        default=(max(1, int(mevcut_insaat / 100.0)) if mevcut_insaat > 0 else 0),
                    )
                elif not has_building_layer:
                    # Attribute-only mode fallback when no building layer was supplied
                    mevcut_insaat = round(area_m2 * 1.0, 2)
                    mevcut_bina = cls._extract_int(p_feat, ("yapi_adedi", "bina_sayisi", "P_YAPI_ADET"), default=1)
                    mevcut_bb = cls._extract_int(
                        p_feat, ("bagimsiz_bolum_sayisi", "P_BAGIMSIZ_BOLUM"), default=max(1, int(mevcut_insaat / 100.0))
                    )

            # 2. Proposed new zoning rights
            raw_new_kaks = first_float(
                p_feat,
                ("yeni_kaks", "kaks", "KAKS", "EmsalKaks", "emsal", "EMSAL", "P_KAKS", "P_EMSAL"),
                default=None,
            )
            yeni_kaks = raw_new_kaks if (raw_new_kaks is not None and raw_new_kaks >= 0.0) else default_new_kaks
            yeni_insaat = round(area_m2 * yeni_kaks, 2)

            # 3. Entitlement sharing
            muteahhit_m2 = round(yeni_insaat * contractor_ratio, 2)
            hak_sahibi_m2 = round(yeni_insaat - muteahhit_m2, 2)

            # Coefficient of entitlement: owners' new area / existing area
            hakedis = round(hak_sahibi_m2 / mevcut_insaat, 3) if mevcut_insaat > 0 else 1.0
            alan_farki = round(hak_sahibi_m2 - mevcut_insaat, 2)

            if alan_farki > 10.0:
                durum = "ALAN_FAZLASI_POZITIF"
            elif alan_farki >= -10.0:
                durum = "DENGEDE"
            else:
                durum = "ALAN_ACIGI_BORCLANMA"

            # 4. Financial projections
            maliyet = round(yeni_insaat * unit_construction_cost_tl, 2)
            ciro = round(muteahhit_m2 * unit_sale_price_tl, 2)
            kar_zarar = round(ciro - maliyet, 2)

            item = TransformationFeasibilityItem(
                fid=p_feat.id(),
                ada_parsel=ada_parsel,
                parsel_alani_m2=area_m2,
                mevcut_bina_adedi=mevcut_bina,
                mevcut_insaat_alani_m2=round(mevcut_insaat, 2),
                mevcut_bagimsiz_bolum=mevcut_bb,
                yeni_kaks=round(yeni_kaks, 2),
                yeni_insaat_alani_m2=yeni_insaat,
                muteahhit_payi_orani=contractor_ratio,
                muteahhit_insaat_m2=muteahhit_m2,
                hak_sahibi_insaat_m2=hak_sahibi_m2,
                hakedis_katsayisi=hakedis,
                alan_farki_m2=alan_farki,
                fizibilite_durumu=durum,
                tahmini_maliyet_tl=maliyet,
                tahmini_ciro_tl=ciro,
                tahmini_kar_zarar_tl=kar_zarar,
                geometri=geom,
            )
            items.append(item)

            if feedback and total_parcels > 0 and idx % 200 == 0:
                feedback.setProgress(int(100 * idx / total_parcels))

        # 5. Summary statistics
        summary.items = items
        summary.toplam_parsel_sayisi = len(items)
        summary.toplam_parsel_alani_m2 = round(sum(i.parsel_alani_m2 for i in items), 2)
        summary.toplam_mevcut_insaat_m2 = round(sum(i.mevcut_insaat_alani_m2 for i in items), 2)
        summary.toplam_yeni_insaat_m2 = round(sum(i.yeni_insaat_alani_m2 for i in items), 2)
        summary.toplam_muteahhit_m2 = round(sum(i.muteahhit_insaat_m2 for i in items), 2)
        summary.toplam_hak_sahibi_m2 = round(sum(i.hak_sahibi_insaat_m2 for i in items), 2)
        summary.toplam_maliyet_tl = round(sum(i.tahmini_maliyet_tl for i in items), 2)
        summary.toplam_ciro_tl = round(sum(i.tahmini_ciro_tl for i in items), 2)
        summary.net_finansal_bakiye_tl = round(summary.toplam_ciro_tl - summary.toplam_maliyet_tl, 2)

        if summary.toplam_mevcut_insaat_m2 > 0:
            summary.ortalama_hakedis_katsayisi = round(
                summary.toplam_hak_sahibi_m2 / summary.toplam_mevcut_insaat_m2, 3
            )
        else:
            summary.ortalama_hakedis_katsayisi = 1.0

        if summary.net_finansal_bakiye_tl >= 0:
            summary.fizibilite_yorumu = 'Finansal ve Mekânsal Olarak Sürdürülebilir (Kendi Kendini Finanse Eden Proje).'
        else:
            summary.fizibilite_yorumu = 'Finansal Açık / Kamu Teşviki veya Ek Yoğunluk Artışı Gerektiren Dönüşüm Alanı.'

        summary.html_report = cls.generate_html_report(summary)
        return items, summary

    @classmethod
    def generate_html_report(cls, summary: TransformationFeasibilitySummary) -> str:
        """Renders an official, publication-ready Urban Transformation Feasibility Report."""
        today = datetime.now().strftime("%d.%m.%Y")
        rows = []
        for it in summary.items:
            durum_badge = {
                "ALAN_FAZLASI_POZITIF": "<span style='color:#16a34a; font-weight:bold;'>POZİTİF FAZLA</span>",
                "DENGEDE": "<span style='color:#0284c7; font-weight:bold;'>DENGEDE</span>",
                "ALAN_ACIGI_BORCLANMA": "<span style='color:#dc2626; font-weight:bold;'>BORÇLANMA</span>",
            }.get(it.fizibilite_durumu, it.fizibilite_durumu)

            safe_ada_parsel = html.escape(str(it.ada_parsel))
            rows.append(
                f"<tr>"
                f"<td><b>{safe_ada_parsel}</b></td>"
                f"<td style='text-align:right;'>{it.parsel_alani_m2:,.2f}</td>"
                f"<td style='text-align:right;'>{it.mevcut_insaat_alani_m2:,.2f}</td>"
                f"<td style='text-align:center;'>{it.yeni_kaks:.2f}</td>"
                f"<td style='text-align:right;'><b>{it.yeni_insaat_alani_m2:,.2f}</b></td>"
                f"<td style='text-align:right; background:#f0fdf4;'>{it.hak_sahibi_insaat_m2:,.2f}</td>"
                f"<td style='text-align:right; background:#eff6ff;'>{it.muteahhit_insaat_m2:,.2f}</td>"
                f"<td style='text-align:center;'><b>{it.hakedis_katsayisi:.3f}</b></td>"
                f"<td style='text-align:center;'>{durum_badge}</td>"
                f"</tr>"
            )

        html_out = f"""<!DOCTYPE html>\n<html lang="tr">\n<head>\n<meta charset="UTF-8">\n<title>6306 Sayılı Kanun Kentsel Dönüşüm Hakediş ve Fizibilite Raporu</title>\n<style>\n  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 25px; color: #1e293b; background: #fff; }}\n  .header {{ text-align: center; border-bottom: 2px solid #0f172a; padding-bottom: 12px; margin-bottom: 20px; }}\n  .header h2 {{ margin: 0; color: #0f172a; font-size: 18pt; text-transform: uppercase; }}\n  .header h3 {{ margin: 5px 0 0 0; color: #475569; font-size: 12pt; font-weight: normal; }}\n  .summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}\n  .summary-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center; }}\n  .summary-card .num {{ font-size: 15pt; font-weight: bold; color: #0f766e; }}\n  .summary-card .lbl {{ font-size: 9pt; color: #64748b; margin-top: 4px; }}\n  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 9pt; }}\n  th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; }}\n  th {{ background: #0f172a; color: #fff; font-weight: 600; text-align: center; }}\n  tr:nth-child(even) {{ background: #f8fafc; }}\n</style>\n</head>\n<body>\n  <div class="header">\n    <h2>6306 Sayılı Kanun Kentsel Dönüşüm Hakediş ve Fizibilite Raporu</h2>\n    <h3>Alan Paylaşım Matrisi, Müteahhit/Hak Sahibi Hakedişi ve Finansal Projeksiyon</h3>\n    <p style="font-size: 9pt; color: #64748b; margin: 4px 0 0 0;">Tanzim Tarihi: {today} | Değerlendirme: {html.escape(str(summary.fizibilite_yorumu))}</p>\n  </div>\n\n  <div class="summary-grid">\n    <div class="summary-card">\n      <div class="num">{summary.toplam_mevcut_insaat_m2:,.2f} m²</div>\n      <div class="lbl">Toplam Mevcut İnşaat Alanı</div>\n    </div>\n    <div class="summary-card">\n      <div class="num">{summary.toplam_yeni_insaat_m2:,.2f} m²</div>\n      <div class="lbl">Yeni İmar Planı İnşaat Kapasitesi</div>\n    </div>\n    <div class="summary-card">\n      <div class="num">{summary.ortalama_hakedis_katsayisi:.3f}</div>\n      <div class="lbl">Ortalama Hak Sahipliği Katsayısı</div>\n    </div>\n    <div class="summary-card">\n      <div class="num">{summary.net_finansal_bakiye_tl:,.2f} TL</div>\n      <div class="lbl">Net Finansal Proje Bakiyesi</div>\n    </div>\n  </div>\n\n  <table>\n    <thead>\n      <tr>\n        <th>Ada / Parsel</th>\n        <th>Parsel Alanı (m²)</th>\n        <th>Mevcut İnşaat (m²)</th>\n        <th>Yeni KAKS</th>\n        <th>Yeni İmar Alanı (m²)</th>\n        <th>Hak Sahibi Alanı (m²)</th>\n        <th>Müteahhit Payı (m²)</th>\n        <th>Hakediş Oranı</th>\n        <th>Fizibilite Durumu</th>\n      </tr>\n    </thead>\n    <tbody>\n      {''.join(rows)}\n    </tbody>\n    <tfoot>\n      <tr style="background: #e2e8f0; font-weight: bold;">\n        <td style="text-align:center;">GENEL TOPLAM</td>\n        <td style="text-align:right;">{summary.toplam_parsel_alani_m2:,.2f}</td>\n        <td style="text-align:right;">{summary.toplam_mevcut_insaat_m2:,.2f}</td>\n        <td style="text-align:center;">-</td>\n        <td style="text-align:right;">{summary.toplam_yeni_insaat_m2:,.2f}</td>\n        <td style="text-align:right;">{summary.toplam_hak_sahibi_m2:,.2f}</td>\n        <td style="text-align:right;">{summary.toplam_muteahhit_m2:,.2f}</td>\n        <td style="text-align:center;">{summary.ortalama_hakedis_katsayisi:.3f}</td>\n        <td style="text-align:center;">-</td>\n      </tr>\n    </tfoot>\n  </table>\n</body>\n</html>\n"""
        return html_out

    @classmethod
    def create_feasibility_memory_layer(
        cls,
        summary: TransformationFeasibilitySummary,
        crs_authid: str = "EPSG:5254",
    ) -> QgsVectorLayer:
        """Converts feasibility items into a spatial memory layer."""
        uri = (
            f"MultiPolygon?crs={crs_authid}"
            f"&field=ada_parsel:string(40)"
            f"&field=parsel_m2:double(10,2)"
            f"&field=mevcut_insaat_m2:double(10,2)"
            f"&field=yeni_kaks:double(5,2)"
            f"&field=yeni_insaat_m2:double(10,2)"
            f"&field=hak_sahibi_m2:double(10,2)"
            f"&field=muteahhit_m2:double(10,2)"
            f"&field=hakedis_orani:double(6,3)"
            f"&field=fizibilite_durumu:string(30)"
            f"&field=maliyet_tl:double(14,2)"
            f"&field=ciro_tl:double(14,2)"
            f"&field=kar_zarar_tl:double(14,2)"
        )
        layer = QgsVectorLayer(uri, "donusum_fizibilite_analizi", "memory")
        pr = layer.dataProvider()

        feats = []
        for it in summary.items:
            f = QgsFeature(layer.fields())
            if it.geometri and not it.geometri.isEmpty():
                f.setGeometry(it.geometri)
            f["ada_parsel"] = it.ada_parsel
            f["parsel_m2"] = it.parsel_alani_m2
            f["mevcut_insaat_m2"] = it.mevcut_insaat_alani_m2
            f["yeni_kaks"] = it.yeni_kaks
            f["yeni_insaat_m2"] = it.yeni_insaat_alani_m2
            f["hak_sahibi_m2"] = it.hak_sahibi_insaat_m2
            f["muteahhit_m2"] = it.muteahhit_insaat_m2
            f["hakedis_orani"] = it.hakedis_katsayisi
            f["fizibilite_durumu"] = it.fizibilite_durumu
            f["maliyet_tl"] = it.tahmini_maliyet_tl
            f["ciro_tl"] = it.tahmini_ciro_tl
            f["kar_zarar_tl"] = it.tahmini_kar_zarar_tl
            feats.append(f)

        pr.addFeatures(feats)
        layer.updateExtents()
        return layer
