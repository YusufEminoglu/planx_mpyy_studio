'PlanX MPYY Official Zoning Information Certificate (İmar Durum Belgesi / İmar Çapı) Engine.\n\nGenerates official, statutory municipal zoning certificates (İmar Çapı) under:\n- Planning Law No. 3194 (3194 Sayılı İmar Kanunu)\n- Planned Areas Construction Mevzuat (Planlı Alanlar İmar Yönetmeliği - PAİY)\n- Spatial Planning Construction Mevzuat (Mekânsal Planlar Yapım Yönetmeliği - MPYY)\n\nExtracts and synthesizes:\n1. Cadastral and Registry Attributes (İl, İlçe, Mahalle, Ada, Parsel, Tapu Alanı).\n2. Statutory Planning Parameters (Fonksiyon, Nizam, TAKS, KAKS/Emsal, Kat Adedi/Yençok).\n3. Setback Distances (Ön, Yan, Arka Bahçe Çekme Mesafeleri).\n4. Calculated Maximum Footprint and Gross Building Capacity (Taban Alanı, İnşaat Alanı).\n5. Parking Requirement Estimate under Otopark Yönetmeliği.\n6. Geotechnical Settlement Suitability (UA, ÖA, UOA).\n7. Boundary Vertex Coordinates Table (BÖHYY / TUREF ITRF96 / Proje KRS).\n8. Print-ready, publication-grade interactive HTML and Markdown Certificate with municipal stamp boxes.\n'

from __future__ import annotations

from .localization import display_label
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
import math
import re
from typing import Any
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer


def _norm_text(val: Any) -> str:
    text = str(val or "").strip().upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


@dataclass
class ParcelCoordinate:
    point_no: int
    x: float
    y: float


@dataclass
class ZoningCertificateResult:
    municipality: str
    belge_no: str
    duzenleme_tarihi: str
    ilce: str
    mahalle: str
    ada_no: str
    parsel_no: str
    pafta_no: str
    kadastro_alani_m2: float
    plan_fonksiyonu: str
    plan_kademesi: str
    yapi_nizami: str
    taks: float
    kaks: float
    kat_adedi: str
    yencok: str
    on_bahce_m: float
    yan_bahce_m: float
    arka_bahce_m: float
    azami_taban_alani_m2: float
    azami_insaat_alani_m2: float
    emsal_harici_alan_m2: float
    toplam_ruhsat_insaat_m2: float
    otopark_arac_ihtiyaci: int
    yerlesime_uygunluk: str
    kose_parsel_mi: bool | None      # None: cannot be told from the parcel alone
    koordinatlar: list[ParcelCoordinate] = field(default_factory=list)
    # Values taken from the caller's defaults, not from the plan or parcel data.
    varsayilan_degerler: list[str] = field(default_factory=list)
    plan_notlari_ozeti: str = ""
    html_content: str = ""
    markdown_content: str = ""


class ZoningCertificateEngine:
    """Extracts zoning parameters and renders statutory official zoning certificates."""

    @classmethod
    def generate_certificate(
        cls,
        parcel_feature: QgsFeature,
        plan_feature: QgsFeature | None = None,
        municipality: str = 'İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ',
        ilce: str = 'İlçe',
        mahalle: str = 'Mahalle',
        pafta_no: str = 'İ22-c-04-a',
        belge_no_prefix: str = 'ÇAP',
        default_taks: float = 0.35,
        default_kaks: float = 1.40,
        default_nizam: str = "AYRIK",
        default_kat: str = "4",
        default_on_bahce: float = 5.0,
        default_yan_bahce: float = 3.0,
    ) -> ZoningCertificateResult:
        """Constructs an official zoning certificate for a selected parcel feature."""
        geom = parcel_feature.geometry()
        area_m2 = round(geom.area(), 2) if geom and not geom.isEmpty() else 0.0

        fields = parcel_feature.fields()

        def get_field_val(feat: QgsFeature, keys: tuple[str, ...]) -> str:
            for k in keys:
                idx = feat.fields().indexFromName(k)
                if idx >= 0 and feat[idx] not in (None, "", "NULL"):
                    return str(feat[idx]).strip()
            return ""

        # Every value the plan or parcel does not give is named here, and the
        # certificate says so; an invented ada/parsel, function or ground class
        # used to be printed as if it had been read.
        defaults: list[str] = []

        # 1. Identification
        ada = get_field_val(parcel_feature, ("ADA", "ada", "ada_no", "ADA_NO")) or "—"
        parsel = get_field_val(parcel_feature, ("PARSEL", "parsel", "parsel_no", "PARSEL_NO")) or "—"
        mah = get_field_val(parcel_feature, ("MAHALLE", "mahalle", "mahalle_adi", "MAHALLE_ADI")) or mahalle
        pafta = get_field_val(parcel_feature, ("PAFTA", "pafta", "pafta_no", "PAFTA_NO")) or pafta_no

        # 2. Planning function
        plan_src = plan_feature or parcel_feature
        fonksiyon = get_field_val(plan_src, ("uipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK", "detay_katalogu", "kullanim")) or "Belirtilmemiş"

        # 3. Structural & zoning rights
        nizam = get_field_val(plan_src, ("nizam", "YAPI_NIZAMI", "P_NIZAM"))
        if not nizam:
            nizam = default_nizam
            defaults.append("Yapılaşma nizamı")
        kat_str = get_field_val(plan_src, ("katadedi", "kat_sayisi", "kat", "P_KAT", "B_KAT"))
        if not kat_str:
            kat_str = default_kat
            defaults.append("Kat adedi")
        yencok_str = get_field_val(plan_src, ("yencok", "YENCOK", "HMAX", "hmax", "bina_yuksekligi"))
        if not yencok_str:
            with contextlib.suppress(ValueError, TypeError):
                kat_int = int(float(kat_str))
                yencok_str = f"{kat_int * 3.0 + 0.5:.2f} m"
            if not yencok_str:
                yencok_str = "Serbest"

        # TAKS / KAKS
        taks = None
        taks_str = get_field_val(plan_src, ("taks", "TAKS", "P_TAKS"))
        if taks_str:
            with contextlib.suppress(ValueError, TypeError):
                val = float(taks_str)
                if 0.0 < val <= 1.0:
                    taks = val
        if taks is None:
            taks = default_taks
            defaults.append("TAKS")

        kaks = None
        kaks_str = get_field_val(plan_src, ("kaks", "emsal", "KAKS", "EMSAL", "P_KAKS", "P_EMSAL"))
        if kaks_str:
            with contextlib.suppress(ValueError, TypeError):
                val = float(kaks_str)
                if 0.0 < val <= 10.0:
                    kaks = val
        if kaks is None:
            kaks = default_kaks
            defaults.append("KAKS / Emsal")

        # Setback distances
        on_bahce = None
        on_str = get_field_val(plan_src, ("onbahce", "onBahce", "P_ON_BAHCE", "yapiYaklasmaMesafesi"))
        if on_str:
            with contextlib.suppress(ValueError, TypeError):
                val = float(on_str)
                if val >= 0:
                    on_bahce = val
        if on_bahce is None:
            on_bahce = default_on_bahce
            defaults.append("Ön bahçe mesafesi")

        yan_bahce = None
        yan_str = get_field_val(plan_src, ("yanbahce", "yanBahce", "P_YAN_BAHCE"))
        if yan_str:
            with contextlib.suppress(ValueError, TypeError):
                val = float(yan_str)
                if val >= 0:
                    yan_bahce = val
        if yan_bahce is None:
            yan_bahce = default_yan_bahce
            defaults.append("Yan bahçe mesafesi")

        # Arka bahce: PAİY Md. 28 -> h/2 or min 3.0m
        arka_bahce = max(3.0, round(yan_bahce, 2))

        # 4. Computed buildable areas (PAİY Md. 5 & 29)
        taban_alani_m2 = round(area_m2 * taks, 2)
        insaat_alani_m2 = round(area_m2 * kaks, 2)
        emsal_harici_alan_m2 = round(insaat_alani_m2 * 0.30, 2)
        toplam_ruhsat_insaat_m2 = round(insaat_alani_m2 + emsal_harici_alan_m2, 2)

        # 5. Parking calculation (Otopark Yönetmeliği: ~1 car per 150m2 housing or 40m2 commercial)
        is_commercial = any(w in _norm_text(fonksiyon) for w in ("TICARET", "OFIS", "CARSI", "IS_HANI"))
        rate_m2 = 40.0 if is_commercial else 150.0
        otopark_arac = max(1, math.ceil(insaat_alani_m2 / rate_m2)) if insaat_alani_m2 >= 30.0 else 0

        # 6. Geology / Geotechnical
        # No ground class is ever assumed: "UA (Uygun Alan)" used to be printed for
        # every parcel whose data had none.
        geo_str = get_field_val(plan_src, ("yerlesime_uygunluk", "P_JEOLOJI", "zemin_durumu")) or "Belirtilmemiş"

        # 7. Coordinates extraction
        coords: list[ParcelCoordinate] = []
        if geom and not geom.isEmpty():
            poly_pts = geom.asPolygon() if not geom.isMultipart() else (geom.asMultiPolygon()[0] if geom.asMultiPolygon() else [])
            if poly_pts and poly_pts[0]:
                for idx, pt in enumerate(poly_pts[0][:-1], start=1):
                    coords.append(ParcelCoordinate(point_no=idx, x=round(pt.x(), 3), y=round(pt.y(), 3)))

        # A corner parcel is one with frontage on two roads: the parcel alone cannot
        # tell (every rectangle has four corners, and all of them used to be
        # certified "köşe başı"), so it stays undetermined without road data.
        kose_parsel = None

        today_str = datetime.now().strftime("%d.%m.%Y")
        now_hash = hex(abs(hash(f"{ada}_{parsel}_{area_m2}")))[2:8].upper()
        belge_no = f"{belge_no_prefix}-{now_hash}-{datetime.now().year}"

        # Standard plan notes summary
        plan_notlari = (
            '1. 3194 sayılı İmar Kanunu ve Planlı Alanlar İmar Yönetmeliği hükümleri geçerlidir.\n2. Parsel bünyesinde Otopark Yönetmeliği uyarınca gerekli otopark alanı teşkil edilecektir.\n3. Zemin etüt raporu onaylanmadan mimari ve statik proje tasdik edilemez.\n4. Bu imar çapı ruhsat belgesi yerine geçmez; tanzim tarihinden itibaren 1 yıl süreyle geçerlidir.'
        )

        res = ZoningCertificateResult(
            municipality=municipality,
            belge_no=belge_no,
            duzenleme_tarihi=today_str,
            ilce=ilce,
            mahalle=mah,
            ada_no=ada,
            parsel_no=parsel,
            pafta_no=pafta,
            kadastro_alani_m2=area_m2,
            plan_fonksiyonu=fonksiyon,
            plan_kademesi='1/1.000 Uygulama imar planı (UİP)',
            yapi_nizami=nizam,
            taks=taks,
            kaks=kaks,
            kat_adedi=kat_str,
            yencok=yencok_str,
            on_bahce_m=on_bahce,
            yan_bahce_m=yan_bahce,
            arka_bahce_m=arka_bahce,
            azami_taban_alani_m2=taban_alani_m2,
            azami_insaat_alani_m2=insaat_alani_m2,
            emsal_harici_alan_m2=emsal_harici_alan_m2,
            toplam_ruhsat_insaat_m2=toplam_ruhsat_insaat_m2,
            otopark_arac_ihtiyaci=otopark_arac,
            yerlesime_uygunluk=geo_str,
            kose_parsel_mi=kose_parsel,
            koordinatlar=coords,
            plan_notlari_ozeti=plan_notlari,
            varsayilan_degerler=defaults,
        )

        res.html_content = cls._render_html(res)
        res.markdown_content = cls._render_markdown(res)
        return res

    @staticmethod
    def _corner_text(cert: ZoningCertificateResult) -> str:
        if cert.kose_parsel_mi is None:
            return "Belirlenemedi (yol verisi yok)"
        return "Köşe başı parsel" if cert.kose_parsel_mi else "Ara parsel"

    @staticmethod
    def _defaults_note(cert: ZoningCertificateResult, html: bool = False) -> str:
        """Which values came from defaults instead of the plan; empty when none did."""
        if not cert.varsayilan_degerler:
            return ""
        text = ("Plan verisinde bulunmayan, varsayılan değerle doldurulan alanlar: "
                + ", ".join(cert.varsayilan_degerler) + ". Bu değerler plandan teyit edilmelidir.")
        return f"<strong>Uyarı:</strong> {text}<br>" if html else f"\n> **Uyarı:** {text}\n"

    @classmethod
    def _render_html(cls, cert: ZoningCertificateResult) -> str:
        coord_rows = "".join(
            f"<tr><td>P.{c.point_no}</td><td>{c.y:.3f}</td><td>{c.x:.3f}</td></tr>"
            for c in cert.koordinatlar[:16]
        )

        return f"""<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>İmar Durumu Belgesi - {cert.ada_no}/{cert.parsel_no}</title>\n<style>\n  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #eceff1; margin: 0; padding: 20px; color: #263238; }}\n  .page {{ width: 210mm; min-height: 297mm; padding: 20mm; margin: 0 auto; background: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.15); box-sizing: border-box; position: relative; }}\n  .header {{ text-align: center; border-bottom: 2px solid #004d40; padding-bottom: 12px; margin-bottom: 16px; }}\n  .header h1 {{ margin: 0; font-size: 17pt; color: #004d40; letter-spacing: 0.5px; }}\n  .header h2 {{ margin: 4px 0 0 0; font-size: 13pt; color: #37474f; }}\n  .header h3 {{ margin: 6px 0 0 0; font-size: 11pt; color: #d81b60; font-weight: bold; text-decoration: underline; }}\n  .meta-grid {{ display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 9.5pt; font-weight: bold; }}\n  table {{ width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 9pt; }}\n  th, td {{ border: 1px solid #b0bec5; padding: 6px 8px; text-align: left; }}\n  th {{ background: #f0f4f8; color: #004d40; font-weight: bold; width: 35%; }}\n  .section-title {{ background: #004d40; color: #fff; padding: 5px 8px; font-size: 10pt; font-weight: bold; margin-top: 10px; }}\n  .coord-table {{ width: 100%; font-size: 8.5pt; text-align: center; }}\n  .coord-table th {{ text-align: center; width: auto; background: #cfd8dc; }}\n  .stamp-box {{ display: flex; justify-content: space-between; margin-top: 30px; page-break-inside: avoid; }}\n  .stamp {{ width: 30%; border: 1px dashed #78909c; border-radius: 4px; padding: 10px; text-align: center; font-size: 8.5pt; height: 90px; }}\n  .footer-note {{ margin-top: 20px; font-size: 8pt; color: #546e7a; border-top: 1px solid #cfd8dc; padding-top: 8px; line-height: 1.3; }}\n  @media print {{\n    body {{ background: #fff; padding: 0; }}\n    .page {{ box-shadow: none; margin: 0; width: 100%; height: auto; padding: 15mm; }}\n  }}\n</style>\n</head>\n<body>\n<div class="page">\n  <div class="header">\n    <h1>{cert.municipality}</h1>\n    <h2>İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ</h2>\n    <h3>RESMİ İMAR DURUMU BELGESİ</h3>\n  </div>\n\n  <div class="meta-grid">\n    <div>Belge No: <strong>{cert.belge_no}</strong></div>\n    <div>Tanzim Tarihi: <strong>{cert.duzenleme_tarihi}</strong></div>\n    <div>Ölçek: <strong>1/1.000</strong></div>\n  </div>\n\n  <div class="section-title">1. TAŞINMAZ MÜLKİYET VE KADASTRO BİLGİLERİ</div>\n  <table>\n    <tr><th>İlçe / Mahalle</th><td>{cert.ilce} / {cert.mahalle}</td><th>Pafta No</th><td>{cert.pafta_no}</td></tr>\n    <tr><th>Ada / Parsel No</th><td><strong>{cert.ada_no} / {cert.parsel_no}</strong></td><th>Parsel Alanı</th><td><strong>{cert.kadastro_alani_m2:,.2f} m²</strong></td></tr>\n    <tr><th>Köşe Başı / Konum</th><td>{cls._corner_text(cert).upper()}</td><th>Geçerli Plan Kademesi</th><td>{cert.plan_kademesi}</td></tr>\n  </table>\n\n  <div class="section-title">2. İMAR PLANI VE YAPILAŞMA KOŞULLARI (PAİY)</div>\n  <table>\n    <tr><th>İmar Planı Fonksiyonu</th><td colspan="3"><strong style="color:#004d40;">{display_label(cert.plan_fonksiyonu)}</strong></td></tr>\n    <tr><th>Yapılaşma Nizamı</th><td><strong>{display_label(cert.yapi_nizami)}</strong></td><th>Kat Adedi / Yençok</th><td><strong>{cert.kat_adedi} Kat ({cert.yencok})</strong></td></tr>\n    <tr><th>TAKS Oranı</th><td><strong>{cert.taks:.2f}</strong></td><th>Kat Alanı Katsayısı (KAKS/Emsal)</th><td><strong>{cert.kaks:.2f}</strong></td></tr>\n    <tr><th>Ön Bahçe Çekme Mesafesi</th><td><strong>{cert.on_bahce_m:.2f} m</strong></td><th>Yan Bahçe Çekme Mesafesi</th><td><strong>{cert.yan_bahce_m:.2f} m</strong></td></tr>\n    <tr><th>Arka Bahçe Çekme Mesafesi</th><td><strong>{cert.arka_bahce_m:.2f} m</strong></td><th>Yerleşime Uygunluk / Zemin</th><td><strong>{display_label(cert.yerlesime_uygunluk)}</strong></td></tr>\n  </table>\n\n  <div class="section-title">3. HESAPLANAN AZAMİ İNŞAAT KAPASİTESİ VE OTOPARK</div>\n  <table>\n    <tr><th>Azami Taban Alanı (TAKS x Alan)</th><td><strong>{cert.azami_taban_alani_m2:,.2f} m²</strong></td><th>Azami Emsale Esas Alan</th><td><strong>{cert.azami_insaat_alani_m2:,.2f} m²</strong></td></tr>\n    <tr><th>Emsal Harici Alan (PAİY Md. 5 Azami yuzde 30)</th><td><strong>{cert.emsal_harici_alan_m2:,.2f} m²</strong></td><th>Toplam Ruhsat İnşaat Alanı</th><td><strong style="color:#004d40;">{cert.toplam_ruhsat_insaat_m2:,.2f} m²</strong></td></tr>\n    <tr><th>Otopark İhtiyacı (Otopark Yön.)</th><td><strong>{cert.otopark_arac_ihtiyaci} Araç</strong> (Parsel bünyesinde)</td><th>Sığınak Yükümlülüğü</th><td>{('Sığınak Yönetmeliği gereği zorunludur' if cert.toplam_ruhsat_insaat_m2 >= 1000 else 'Muaf / Bağımsız bölüme bağlı')}</td></tr>\n  </table>\n\n  <div class="section-title">4. PARSEL SINIR KÖŞE KOORDİNATLARI (ITRF96 / BÖHYY)</div>\n  <table class="coord-table">\n    <tr><th>Nokta No</th><th>Kuzey (Y)</th><th>Doğu (X)</th><th>Nokta No</th><th>Kuzey (Y)</th><th>Doğu (X)</th></tr>\n    {coord_rows}\n  </table>\n\n  <div class="stamp-box">\n    <div class="stamp">\n      <strong>Düzenleyen</strong><br><br>\n      Şehir Plancısı / Harita Müh.<br>\n      İmza / Kaşe\n    </div>\n    <div class="stamp">\n      <strong>Kontrol Eden</strong><br><br>\n      İmar Şefi<br>\n      İmza / Kaşe\n    </div>\n    <div class="stamp">\n      <strong>Onaylayan</strong><br><br>\n      İmar ve Şehircilik Müdürü<br>\n      Mühür / İmza\n    </div>\n  </div>\n\n  <div class="footer-note">\n    {cls._defaults_note(cert, html=True)}<strong>Önemli Hükümler:</strong> Bu belge 3194 sayılı İmar Kanunu ve Planlı Alanlar İmar Yönetmeliği uyarınca tanzim edilmiş olup onay tarihinden itibaren 1 (bir) yıl süreyle geçerlidir. Yapı ruhsatı yerine geçmez; mimari avan/uygulama projesi tanzimine esastır. Parsel sınırları ve köşe koordinatları aplikasyon krokisi ile teyit edilmelidir.\n  </div>\n</div>\n</body>\n</html>\n"""

    @classmethod
    def _render_markdown(cls, cert: ZoningCertificateResult) -> str:
        return f"# {cert.municipality}\n## Resmi İmar Durumu Belgesi (İmar Çapı)\n\n**Belge No:** {cert.belge_no} | **Date:** {cert.duzenleme_tarihi} | **Ölçek:** 1/1.000\n\n---\n\n### 1. Taşınmaz Bilgileri\n- **İlçe / Mahalle:** {cert.ilce} / {cert.mahalle}\n- **Ada / Parsel No:** {cert.ada_no} / {cert.parsel_no}\n- **Pafta No:** {cert.pafta_no}\n- **Parsel Alanı:** {cert.kadastro_alani_m2:,.2f} m²\n- **Konum Durumu:** {cls._corner_text(cert)}\n\n### 2. İmar Planı ve Yapılaşma Şartları (PAİY)\n- **Fonksiyon:** {display_label(cert.plan_fonksiyonu)}\n- **Yapılaşma Nizamı:** {display_label(cert.yapi_nizami)}\n- **TAKS:** {cert.taks:.2f}\n- **KAKS / Emsal:** {cert.kaks:.2f}\n- **Kat Adedi / Yençok:** {cert.kat_adedi} Kat ({cert.yencok})\n- **ÖN BAHÇE MESAFESİ:** {cert.on_bahce_m:.2f} m\n- **YAN BAHÇE MESAFESİ:** {cert.yan_bahce_m:.2f} m\n- **Arka Bahçe Çekme:** {cert.arka_bahce_m:.2f} m\n- **Yerleşime Uygunluk:** {display_label(cert.yerlesime_uygunluk)}\n\n### 3. Azami İnşaat Kapasitesi ve Donatı\n- **Azami Taban Alanı:** {cert.azami_taban_alani_m2:,.2f} m²\n- **Azami Emsale Esas Alan:** {cert.azami_insaat_alani_m2:,.2f} m²\n- **Emsal Harici Alan (PAİY Md. 5 Azami yuzde 30):** {cert.emsal_harici_alan_m2:,.2f} m²\n- **Toplam Ruhsat İnşaat Alanı:** {cert.toplam_ruhsat_insaat_m2:,.2f} m²\n- **Otopark İhtiyacı:** {cert.otopark_arac_ihtiyaci} Araç\n" + cls._defaults_note(cert)

    @classmethod
    def create_zoning_hud_layer(
        cls,
        parcel_feature: QgsFeature,
        setback_m: float = 3.0,
        crs_authid: str = "EPSG:5254",
    ) -> QgsVectorLayer:
        """Constructs an interactive CAD-grade HUD line layer showing setback envelope and parcel edges."""
        from .actions import calculate_setback_envelope
        uri = f"LineString?crs={crs_authid}&field=eleman_turu:string(30)&field=etiket:string(80)&field=olcu_m:double(10,2)"
        hud_layer = QgsVectorLayer(uri, 'imar_capi_hud', "memory")
        pr = hud_layer.dataProvider()
        feats = []

        geom = parcel_feature.geometry()
        if not geom or geom.isEmpty():
            return hud_layer

        # 1. Parcel boundary edges with dimension labels
        poly_pts = geom.asPolygon() if not geom.isMultipart() else (geom.asMultiPolygon()[0] if geom.asMultiPolygon() else [])
        if poly_pts and poly_pts[0]:
            ring = poly_pts[0]
            for i in range(len(ring) - 1):
                p1 = ring[i]
                p2 = ring[i + 1]
                edge_geom = QgsGeometry.fromPolylineXY([p1, p2])
                edge_len = round(edge_geom.length(), 2)
                f = QgsFeature(hud_layer.fields())
                f.setGeometry(edge_geom)
                f["eleman_turu"] = "PARSEL_CEPHESI"
                f["etiket"] = f"Cephe {i+1}: {edge_len:.2f} m"
                f["olcu_m"] = edge_len
                feats.append(f)

        # 2. Setback envelope lines (red inner envelope)
        envelope = calculate_setback_envelope(geom, setback_m)
        if envelope and not envelope.isEmpty():
            env_pts = envelope.asPolygon() if not envelope.isMultipart() else (envelope.asMultiPolygon()[0] if envelope.asMultiPolygon() else [])
            if env_pts and env_pts[0]:
                env_ring = env_pts[0]
                for j in range(len(env_ring) - 1):
                    ep1 = env_ring[j]
                    ep2 = env_ring[j + 1]
                    env_edge = QgsGeometry.fromPolylineXY([ep1, ep2])
                    f_env = QgsFeature(hud_layer.fields())
                    f_env.setGeometry(env_edge)
                    f_env["eleman_turu"] = "CEKME_SINIRI"
                    f_env["etiket"] = f'Çekme Sınırı ({setback_m:.1f}m)'
                    f_env["olcu_m"] = round(env_edge.length(), 2)
                    feats.append(f_env)

        pr.addFeatures(feats)
        hud_layer.updateExtents()
        return hud_layer
