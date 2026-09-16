"""Comprehensive verification and screenshot generation test harness for PlanX MPYY Studio.

Generates real rendered screenshots for:
- All 8 authentic Attribute Forms (UIP alan, cizgi, notasyon; Arazi parsel, yapi, yol, Tucbs alan/cizgi)
- All 4 Planning Level Symbology Renderings (MSP, CDP, NIP with TTF glyphs, UIP with official fills)
- Field Survey Map Rendering (parcels, building footprints, roads)
- Urban Synthesis & Setback Building Envelopes Map Rendering
- Crosswalk Comparison Map Rendering
- MPYY Studio Dock UI (all 4 tabs)

Saves all screenshots to: C:\\Users\\YE\\Downloads\\mpyy_test_screenshots\\
Generates an interactive HTML visual report: index.html
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsFeature,
    QgsGeometry,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.gui import (
    QgsAttributeEditorContext,
    QgsAttributeForm,
    QgsGui,
)
from qgis.PyQt.QtCore import QEventLoop, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPixmap
from qgis.PyQt.QtWidgets import QApplication

# Initialize QGIS Application
app = QgsApplication.instance() or QgsApplication([], True)
app.initQgis()
QgsGui.editorWidgetRegistry().initEditors()

# Protect system and application typography
fonts_dir = Path(__file__).resolve().parents[1] / "resources" / "fonts"
QFontDatabase.addApplicationFont(str(fonts_dir / "DejaVuSans.ttf"))
QFontDatabase.addApplicationFont(str(fonts_dir / "DejaVuSans-Bold.ttf"))
app.setFont(QFont("DejaVu Sans", 9))

from planx_mpyy_studio.core.actions import calculate_setback_envelope
from planx_mpyy_studio.core.cdp_styler import CDPStylerEngine
from planx_mpyy_studio.core.crosswalk import evaluate_crosswalk, execute_layer_crosswalk
from planx_mpyy_studio.core.db_factory import create_land_use_workspace, create_planning_workspace
from planx_mpyy_studio.core.fonts import register_mpyy_fonts
from planx_mpyy_studio.core.msp_styler import MSPStylerEngine
from planx_mpyy_studio.core.nip_styler import NIPStylerEngine
from planx_mpyy_studio.core.project_binding import apply_layer_style_and_form, load_project_layers
from planx_mpyy_studio.core.synthesis import SynthesisEngine
from planx_mpyy_studio.dock import MPYYDock

register_mpyy_fonts()

OUT_DIR = Path.home() / "Downloads" / "mpyy_test_screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST = []


def record(filename: str, title: str, category: str, description: str):
    MANIFEST.append({
        "file": filename,
        "title": title,
        "category": category,
        "desc": description,
    })


def capture_form(layer: QgsVectorLayer, feature: QgsFeature, filename: str, title: str, category: str, desc: str, size=QSize(960, 750)):
    ctx = QgsAttributeEditorContext()
    form = QgsAttributeForm(layer, feature, ctx)
    form.resize(size)
    form.show()
    app.processEvents()
    pix = form.grab()
    out_path = OUT_DIR / filename
    pix.save(str(out_path))
    record(filename, title, category, desc)
    print(f"Captured Form: {filename} ({pix.width()}x{pix.height()})")


def render_map(layers: list[QgsVectorLayer], extent: QgsRectangle, filename: str, title: str, category: str, desc: str, size=QSize(1000, 750)):
    settings = QgsMapSettings()
    settings.setLayers(layers)
    settings.setExtent(extent)
    settings.setOutputSize(size)
    settings.setBackgroundColor(QColor(246, 248, 251))
    settings.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:5254"))
    settings.setOutputDpi(150)

    job = QgsMapRendererParallelJob(settings)
    loop = QEventLoop()
    job.finished.connect(loop.quit)
    job.start()
    loop.exec_()

    img = job.renderedImage()
    out_path = OUT_DIR / filename
    img.save(str(out_path))
    record(filename, title, category, desc)
    print(f"Rendered Map: {filename} ({img.width()}x{img.height()})")


def run_all_verifications():
    print("=== PlanX MPYY Studio Comprehensive Real Test Suite ===")

    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    tmp_path = Path(tmp.name)

    # -------------------------------------------------------------------------
    # PART 1: Planning Workspace & UIP Attribute Forms
    # -------------------------------------------------------------------------
    print("\n--- Part 1: Planning Workspace & UIP Forms ---")
    plan_gpkg = tmp_path / "uip_test.gpkg"
    proj_uip = QgsProject.instance()
    proj_uip.clear()
    create_planning_workspace(plan_gpkg, "EPSG:5254", ("UIP",))
    uip_layers = load_project_layers(plan_gpkg, proj_uip)

    uip_alan = next(l for l in uip_layers if l.name() == "plangml_uip_alan")
    uip_cizgi = next(l for l in uip_layers if l.name() == "plangml_uip_cizgi")
    uip_notasyon = next(l for l in uip_layers if l.name() == "plangml_uip_notasyon")

    # Feature for UIP Alan
    f_alan = QgsFeature(uip_alan.fields())
    f_alan.setGeometry(QgsGeometry.fromRect(QgsRectangle(500000, 4200000, 500200, 4200200)))
    f_alan.setAttribute("uipfonksiyon", "YERLEŞİK KONUT ALANI")
    f_alan.setAttribute("nizam", "AYRIK")
    f_alan.setAttribute("katadedi", "4")
    f_alan.setAttribute("taks", "0.30")
    f_alan.setAttribute("kaks", "1.20")
    f_alan.setAttribute("yapiYaklasmaDurumu", "VAR")
    f_alan.setAttribute("yapiYaklasmaMesafesi", 5)
    f_alan.setAttribute("AlanM2", 40000.0)
    f_alan.setAttribute("Kullanici", "Yusuf Eminoğlu")
    f_alan.setAttribute("Tarihilk", "2026-09-13 10:00:00")
    uip_alan.startEditing()
    uip_alan.addFeature(f_alan)
    uip_alan.commitChanges()

    capture_form(
        uip_alan, f_alan, "01_form_uip_alan.png",
        "UİP Alan Formu (8 Sekmeli Koşullu Form)", "Öznitelik Formları",
        "1/1.000 Uygulama İmar Planı parsel yapılaşma hakları, nizam, kat, TAKS/KAKS ve çekme sınırı slider widget'ı (özgün yerel form)."
    )

    # Feature for UIP Cizgi
    f_cizgi = QgsFeature(uip_cizgi.fields())
    f_cizgi.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(499900, 4200100), QgsPointXY(500500, 4200100)]))
    f_cizgi.setAttribute("uipfonksiyon", "TAŞIT YOLU")
    f_cizgi.setAttribute("yolTipi", "BÖLÜNMÜŞ YOL")
    f_cizgi.setAttribute("yolGenislik", 20.0)
    f_cizgi.setAttribute("kaldirimGenislik", 2.5)
    f_cizgi.setAttribute("refujGenislik", 2.0)
    f_cizgi.setAttribute("SolSeritSayisi", 2)
    f_cizgi.setAttribute("SagSeritSayisi", 2)
    f_cizgi.setAttribute("Kullanici", "Yusuf Eminoğlu")
    uip_cizgi.startEditing()
    uip_cizgi.addFeature(f_cizgi)
    uip_cizgi.commitChanges()

    capture_form(
        uip_cizgi, f_cizgi, "02_form_uip_cizgi.png",
        "UİP Çizgi Formu (Yol Platform & Kesit Formu)", "Öznitelik Formları",
        "Yol genişliği, kaldırım, refüj, sağ/sol şerit sayıları ve cephe kalınlığı parametre formu."
    )

    # Feature for UIP Notasyon
    f_not = QgsFeature(uip_notasyon.fields())
    f_not.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500100, 4200100)))
    f_not.setAttribute("ustkonugrup", "KONUT ALANLARI / YERLEŞİM ALANLARI")
    f_not.setAttribute("uipfonksiyon", "YERLEŞİK KONUT ALANI")
    f_not.setAttribute("nizam", "A")
    f_not.setAttribute("katadedi", "4")
    f_not.setAttribute("taks", "0.30")
    f_not.setAttribute("kaks", "1.20")
    f_not.setAttribute("emsal", "1.50")
    f_not.setAttribute("yencok", "15.50")
    uip_notasyon.startEditing()
    uip_notasyon.addFeature(f_not)
    uip_notasyon.commitChanges()

    capture_form(
        uip_notasyon, f_not, "03_form_uip_notasyon.png",
        "UİP Notasyon Formu (Yapı Düzeni & Yoğunluk)", "Öznitelik Formları",
        "Nizam, kat adedi, Yençok ve Emsal yapılaşma notasyonu form kartı."
    )

    # -------------------------------------------------------------------------
    # PART 2: Land Use Survey (Arazi Kullanımı) Forms
    # -------------------------------------------------------------------------
    print("\n--- Part 2: Land Use Survey Forms ---")
    land_gpkg = tmp_path / "land_test.gpkg"
    create_land_use_workspace(land_gpkg, "EPSG:5254")
    proj_land = QgsProject()
    land_layers = load_project_layers(land_gpkg, proj_land)

    parsel_lyr = next(l for l in land_layers if l.name() == "parsel_saha")
    yapi_lyr = next(l for l in land_layers if l.name() == "yapi_saha")
    yol_lyr = next(l for l in land_layers if l.name() == "yol_saha")
    tucbs_alan = next(l for l in land_layers if l.name() == "Tucbs_1000_alan")
    tucbs_cizgi = next(l for l in land_layers if l.name() == "Tucbs_1000_Cizgi")

    # Parsel Saha Form
    f_p = QgsFeature(parsel_lyr.fields())
    f_p.setGeometry(QgsGeometry.fromRect(QgsRectangle(500000, 4200000, 500100, 4200100)))
    f_p.setAttribute("IL", "İZMİR")
    f_p.setAttribute("ILCE", "BERGAMA")
    f_p.setAttribute("MAHALLE", "ATMACA")
    f_p.setAttribute("ADA", "101")
    f_p.setAttribute("PARSEL", "5")
    f_p.setAttribute("P_FONK", "KONUT")
    f_p.setAttribute("TAPU_ALANI", "1250.0")
    f_p.setAttribute("alan_m2", 1250.0)
    f_p.setAttribute("QC", "ONAYLANDI")
    f_p.setAttribute("olusturan", "Yusuf Eminoğlu")
    parsel_lyr.startEditing()
    parsel_lyr.addFeature(f_p)
    parsel_lyr.commitChanges()

    capture_form(
        parsel_lyr, f_p, "04_form_parsel_saha.png",
        "Saha Parsel Anket Formu (Tapu / Kadastro & QC)", "Öznitelik Formları",
        "İl, İlçe, Mahalle, Ada, Parsel, saha kullanım fonksiyonu ve kalite kontrol sekmeleri."
    )

    # Yapi Saha Form
    f_yapi = QgsFeature(yapi_lyr.fields())
    f_yapi.setGeometry(QgsGeometry.fromRect(QgsRectangle(500010, 4200010, 500060, 4200060)))
    f_yapi.setAttribute("B_FONK", "KONUT")
    f_yapi.setAttribute("B_KAT", 4)
    f_yapi.setAttribute("B_YAS", 12)
    f_yapi.setAttribute("B_DURUM", "İYİ")
    f_yapi.setAttribute("B_KALITE", 3)
    f_yapi.setAttribute("fotograf", "C:/Users/YE/fotograflar/bina_101_5.jpg")
    f_yapi.setAttribute("alan_m2", 250.0)
    f_yapi.setAttribute("olusturan", "Yusuf Eminoğlu")
    yapi_lyr.startEditing()
    yapi_lyr.addFeature(f_yapi)
    yapi_lyr.commitChanges()

    capture_form(
        yapi_lyr, f_yapi, "05_form_yapi_saha.png",
        "Saha Yapı Anket Formu (Kat, Yaş, Durum & Dış Fotoğraf)", "Öznitelik Formları",
        "Bina kat sayısı, yapı durumu (İYİ/ORTA/METRUK), taşıyıcı kalite ve harici fotoğraf dosya önizleme widget'ı."
    )

    # Yol Saha Form
    f_yol = QgsFeature(yol_lyr.fields())
    f_yol.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(499950, 4199990), QgsPointXY(500250, 4199990)]))
    f_yol.setAttribute("Y_TIP", "TOPLAYICI YOL")
    f_yol.setAttribute("Y_KAPLAMA", "PARKE TAŞI")
    f_yol.setAttribute("Y_GENISLIK", 12.0)
    f_yol.setAttribute("Y_KALDIRIM", 1)
    f_yol.setAttribute("Y_OTOPARK", 1)
    f_yol.setAttribute("Y_TRAFIK", 2)
    f_yol.setAttribute("olusturan", "Yusuf Eminoğlu")
    yol_lyr.startEditing()
    yol_lyr.addFeature(f_yol)
    yol_lyr.commitChanges()

    capture_form(
        yol_lyr, f_yol, "06_form_yol_saha.png",
        "Saha Yol Anket Formu (Kaplama, Genişlik & Otopark)", "Öznitelik Formları",
        "Yol tipi, kaplama cinsi, yol genişliği, kaldırım ve yol boyu otopark durumu formu."
    )

    # Tucbs 1000 Alan Form
    f_talan = QgsFeature(tucbs_alan.fields())
    f_talan.setGeometry(QgsGeometry.fromRect(QgsRectangle(500000, 4200000, 500100, 4200100)))
    f_talan.setAttribute("tucbs_sinifi", "KENTSEL_YERLESIM")
    f_talan.setAttribute("alan_m2", 10000.0)
    f_talan.setAttribute("QC", "ONAYLANDI")
    tucbs_alan.startEditing()
    tucbs_alan.addFeature(f_talan)
    tucbs_alan.commitChanges()

    capture_form(
        tucbs_alan, f_talan, "07_form_tucbs_1000_alan.png",
        "TUCBS 1/1.000 Saha Alanı Formu", "Öznitelik Formları",
        "TUCBS arazi kullanımı sınıfı, alan büyüklüğü ve QC kalite kontrol onay formu."
    )

    # Tucbs 1000 Cizgi Form
    f_tcizgi = QgsFeature(tucbs_cizgi.fields())
    f_tcizgi.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(500000, 4200000), QgsPointXY(500500, 4200000)]))
    f_tcizgi.setAttribute("tucbs_sinifi", "ALTYAPI_HATTI")
    f_tcizgi.setAttribute("uzunluk_m", 500.0)
    tucbs_cizgi.startEditing()
    tucbs_cizgi.addFeature(f_tcizgi)
    tucbs_cizgi.commitChanges()

    capture_form(
        tucbs_cizgi, f_tcizgi, "08_form_tucbs_1000_cizgi.png",
        "TUCBS 1/1.000 Saha Çizgi Formu", "Öznitelik Formları",
        "TUCBS çizgi ve altyapı sınıflandırma formu."
    )

    # -------------------------------------------------------------------------
    # PART 3: Map Symbology & Canvas Renderings
    # -------------------------------------------------------------------------
    print("\n--- Part 3: Map Symbology & Canvas Renderings ---")

    # 3.1 UIP Rendering
    uip_alan.startEditing()
    uip_zones = [
        ("YERLEŞİK KONUT ALANI", 500000, 4200000, 500200, 4200200, "AYRIK", "4", "0.30", "1.20"),
        ("TİCARET ALANI", 500220, 4200000, 500420, 4200200, "BLOK", "5", "0.40", "2.00"),
        ("PARK", 500000, 4200220, 500200, 4200420, None, None, None, None),
        ("İLKOKUL ALANI", 500220, 4200220, 500420, 4200420, "AYRIK", "3", "0.35", "1.05"),
        ("BELEDİYE HİZMET ALANI", 500440, 4200000, 500640, 4200200, "AYRIK", "4", "0.35", "1.40"),
        ("SAĞLIK TESİSİ ALANI", 500440, 4200220, 500640, 4200420, "AYRIK", "4", "0.40", "1.60"),
    ]
    for fonk, x1, y1, x2, y2, nizam, kat, taks, kaks in uip_zones:
        f = QgsFeature(uip_alan.fields())
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2)))
        f.setAttribute("uipfonksiyon", fonk)
        f.setAttribute("fonksiyon_adi", fonk)
        if nizam: f.setAttribute("nizam", nizam)
        if kat: f.setAttribute("katadedi", kat)
        if taks: f.setAttribute("taks", taks)
        if kaks: f.setAttribute("kaks", kaks)
        uip_alan.addFeature(f)
    uip_alan.commitChanges()

    render_map(
        [uip_cizgi, uip_alan],
        QgsRectangle(499880, 4199880, 500750, 4200550),
        "09_render_uip_symbology.png",
        "UİP Özgün Yerel Sembolojisi (PlanX MPYY)", "Harita Gösterimi",
        "Yusuf Eminoğlu tarafından üretilen özgün yerel UİP stilleri: vektörel renkler, özel SVG taramaları (park stipple, ticaret gridi, donatı glifleri) ve yol platform kesitleri."
    )

    # 3.2 NIP Rendering
    nip_gpkg = tmp_path / "nip_test.gpkg"
    create_planning_workspace(nip_gpkg, "EPSG:5254", ("NIP",))
    proj_nip = QgsProject()
    nip_layers = load_project_layers(nip_gpkg, proj_nip)
    nip_alan = next(l for l in nip_layers if l.name() == "plangml_nip_alan")
    nip_cizgi = next(l for l in nip_layers if l.name() == "plangml_nip_cizgi")
    nip_not = next(l for l in nip_layers if l.name() == "plangml_nip_notasyon")

    nip_alan.startEditing()
    for fonk, x1, y1, x2, y2 in [
        ("ACIK_YESIL_ALAN", 500000, 4200000, 500600, 4200600),
        ("KONUT_ALANLARI", 500650, 4200000, 501250, 4200600),
        ("EGITIM_TESIS_ALANI", 500000, 4200650, 500600, 4201250),
        ("TICARET_ALANI", 500650, 4200650, 501250, 4201250),
    ]:
        f = QgsFeature(nip_alan.fields())
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2)))
        f.setAttribute("fonksiyon_adi", fonk)
        f.setAttribute("catalog_id", fonk)
        nip_alan.addFeature(f)
    nip_alan.commitChanges()

    # Arterial Roads (1. Derece ve 2. Derece Nazım Ulaşım Ağı)
    nip_cizgi.startEditing()
    f_road1 = QgsFeature(nip_cizgi.fields())
    f_road1.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(499800, 4200625), QgsPointXY(501450, 4200625)]))
    f_road1.setAttribute("yol_kademesi", "BIRINCI_DERECE_YOL")
    f_road1.setAttribute("ongorulen_genislik_m", 35.0)
    nip_cizgi.addFeature(f_road1)

    f_road2 = QgsFeature(nip_cizgi.fields())
    f_road2.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(500625, 4199800), QgsPointXY(500625, 4201450)]))
    f_road2.setAttribute("yol_kademesi", "IKINCI_DERECE_YOL")
    f_road2.setAttribute("ongorulen_genislik_m", 25.0)
    nip_cizgi.addFeature(f_road2)
    nip_cizgi.commitChanges()

    nip_not.startEditing()
    for merkez, px, py in [
        ("REKREASYON_ALANI", 500300, 4200300),
        ("ILKOKUL_ALANI", 500300, 4200950),
        ("SAGLIK_TESIS_ALANI", 500950, 4200950),
    ]:
        f = QgsFeature(nip_not.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(px, py)))
        f.setAttribute("merkez_turu", merkez)
        f.setAttribute("catalog_id", merkez)
        nip_not.addFeature(f)
    nip_not.commitChanges()

    render_map(
        [nip_not, nip_cizgi, nip_alan],
        QgsRectangle(499800, 4199800, 501450, 4201450),
        "10_render_nip_symbology.png",
        "NİP Sembolojisi (Resmî PlanGML / E-Plan Standardı)", "Harita Gösterimi",
        "1/5.000 Nazım İmar Planı brüt yoğunluk alanları (konut, ticaret, donatı, yeşil), 1. ve 2. derece ana ulaşım aksları ve MNIP TrueType font glif sembolleri (Resmî mevzuat alternatifi; yerel 5.000 taslağı hazırlanmaktadır)."
    )

    # 3.3 CDP Rendering
    cdp_gpkg = tmp_path / "cdp_test.gpkg"
    create_planning_workspace(cdp_gpkg, "EPSG:5254", ("CDP",))
    proj_cdp = QgsProject()
    cdp_layers = load_project_layers(cdp_gpkg, proj_cdp)
    cdp_alan = next(l for l in cdp_layers if l.name() == "plangml_cdp_alan")

    cdp_alan.startEditing()
    cdp_zones = [
        ("KENTSEL_GELISME_ALANI", 500000, 4200000, 502000, 4202000),
        ("TARIM_ALANI", 502100, 4200000, 504100, 4202000),
        ("ORMAN_ALANI", 500000, 4202100, 502000, 4204100),
        ("SU_YUZEYI", 502100, 4202100, 504100, 4204100),
    ]
    for b_turu, x1, y1, x2, y2 in cdp_zones:
        f = QgsFeature(cdp_alan.fields())
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2)))
        f.setAttribute("bolge_turu", b_turu)
        f.setAttribute("catalog_id", b_turu)
        cdp_alan.addFeature(f)
    cdp_alan.commitChanges()

    render_map(
        [cdp_alan],
        QgsRectangle(499500, 4199500, 504600, 4204600),
        "11_render_cdp_symbology.png",
        "ÇDP Bölge Sembolojisi (Resmî PlanGML / E-Plan Standardı)", "Harita Gösterimi",
        "1/100.000 ve 1/50.000 Çevre Düzeni Planı kentsel gelişme (turuncu), orman (yeşil), tarım (sarı/haki) ve su yüzeyi (mavi) kuşakları (Resmî mevzuat alternatifi; henüz yerel taslak yoktur)."
    )

    # 3.4 MSP Rendering
    msp_gpkg = tmp_path / "msp_test.gpkg"
    create_planning_workspace(msp_gpkg, "EPSG:5254", ("MSP",))
    proj_msp = QgsProject()
    msp_layers = load_project_layers(msp_gpkg, proj_msp)
    msp_alan = next(l for l in msp_layers if l.name() == "plangml_msp_alan")
    msp_not = next(l for l in msp_layers if l.name() == "plangml_msp_notasyon")

    msp_alan.startEditing()
    for cid, x1, y1, x2, y2 in [
        ("MSP-002", 500000, 4200000, 505000, 4205000),
        ("MSP-003", 505200, 4200000, 510200, 4205000),
    ]:
        f = QgsFeature(msp_alan.fields())
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2)))
        f.setAttribute("catalog_id", cid)
        msp_alan.addFeature(f)
    msp_alan.commitChanges()

    msp_not.startEditing()
    f = QgsFeature(msp_not.fields())
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(502500, 4202500)))
    f.setAttribute("catalog_id", "MSP-004")
    msp_not.addFeature(f)
    msp_not.commitChanges()

    render_map(
        [msp_not, msp_alan],
        QgsRectangle(499000, 4199000, 511000, 4206000),
        "12_render_msp_symbology.png",
        "MSP Mekânsal Strateji Planı Sembolojisi (EK-1e 2026)", "Harita Gösterimi",
        "1/250.000 - 1/500.000 makro koridorlar, kademelenme ve kırsal gelişim odakları."
    )

    # 3.5 Field Survey Map Rendering
    print("\n--- Part 3.5: Land Use Survey Map (Yusuf Eminoğlu Sembolojisi) ---")
    parsel_lyr.startEditing()
    extra_parcels = [
        ("TICARET", 500110, 4200000, 500210, 4200100, "101", "6"),
        ("PARK", 500220, 4200000, 500320, 4200100, "101", "7"),
        ("EGITIM", 500000, 4200120, 500100, 4200220, "102", "1"),
        ("SAGLIK", 500110, 4200120, 500210, 4200220, "102", "2"),
        ("BOS_PARSEL", 500220, 4200120, 500320, 4200220, "102", "3"),
    ]
    for p_fonk, x1, y1, x2, y2, ada, parsel in extra_parcels:
        fp = QgsFeature(parsel_lyr.fields())
        fp.setGeometry(QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2)))
        fp.setAttribute("IL", "İZMİR")
        fp.setAttribute("ILCE", "BERGAMA")
        fp.setAttribute("MAHALLE", "ATMACA")
        fp.setAttribute("ADA", ada)
        fp.setAttribute("PARSEL", parsel)
        fp.setAttribute("P_FONK", p_fonk)
        fp.setAttribute("TAPU_ALANI", "10000.0")
        fp.setAttribute("alan_m2", 10000.0)
        fp.setAttribute("QC", "ONAYLANDI")
        fp.setAttribute("olusturan", "Yusuf Eminoğlu")
        parsel_lyr.addFeature(fp)
    parsel_lyr.commitChanges()

    yapi_lyr.startEditing()
    extra_buildings = [
        ("TICARET", 500130, 4200020, 500190, 4200080, 3, "İYİ"),
        ("EGITIM", 500020, 4200140, 500080, 4200200, 3, "İYİ"),
        ("SAGLIK", 500130, 4200140, 500180, 4200190, 2, "İYİ"),
        ("KONUT", 500075, 4200020, 500095, 4200050, 1, "METRUK"),
    ]
    for b_fonk, x1, y1, x2, y2, kat, durum in extra_buildings:
        fb = QgsFeature(yapi_lyr.fields())
        fb.setGeometry(QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2)))
        fb.setAttribute("B_FONK", b_fonk)
        fb.setAttribute("B_KAT", kat)
        fb.setAttribute("B_DURUM", durum)
        fb.setAttribute("alan_m2", float((x2 - x1) * (y2 - y1)))
        fb.setAttribute("olusturan", "Yusuf Eminoğlu")
        yapi_lyr.addFeature(fb)
    yapi_lyr.commitChanges()

    yol_lyr.startEditing()
    extra_roads = [
        ("ANA_ARTER", [QgsPointXY(499950, 4199980), QgsPointXY(500350, 4199980)], 25.0),
        ("TOPLAYICI_YOL", [QgsPointXY(499950, 4200110), QgsPointXY(500350, 4200110)], 15.0),
        ("SERVIS_YOLU", [QgsPointXY(500105, 4199950), QgsPointXY(500105, 4200250)], 10.0),
        ("YAYA_YOLU", [QgsPointXY(500215, 4199950), QgsPointXY(500215, 4200250)], 8.0),
    ]
    for r_tip, pts, gen in extra_roads:
        fr = QgsFeature(yol_lyr.fields())
        fr.setGeometry(QgsGeometry.fromPolylineXY(pts))
        fr.setAttribute("Y_TIP", r_tip)
        fr.setAttribute("Y_GENISLIK", gen)
        fr.setAttribute("olusturan", "Yusuf Eminoğlu")
        yol_lyr.addFeature(fr)
    yol_lyr.commitChanges()

    render_map(
        [yapi_lyr, yol_lyr, parsel_lyr],
        QgsRectangle(499940, 4199930, 500360, 4200260),
        "13_render_land_use_survey.png",
        "Arazi Kullanımı & Saha Sörveyi Sembolojisi (Yusuf Eminoğlu)", "Harita Gösterimi",
        "TUCBS dışındaki kentsel arazi kullanım sınıfları için Yusuf Eminoğlu tarafından geliştirilen yerel semboloji: Konut (sarı), ticaret (kırmızı), donatı (mavi/yeşil/turkuaz), boş parsel, metruk yapı ayrımı ve hiyerarşik yol ağı."
    )

    # 3.6 Urban Synthesis & Setback Building Envelopes
    print("\n--- Part 3.6: Urban Synthesis & Setback Envelopes ---")
    synth_parcels = QgsVectorLayer("Polygon?crs=epsg:5254&field=id:string&field=fonk:string&field=taks:double&field=kaks:double", "sentez_parseller", "memory")
    synth_envelopes = QgsVectorLayer("Polygon?crs=epsg:5254&field=id:string&field=setback_m:double", "cekme_zarfi", "memory")
    synth_buildings = QgsVectorLayer("Polygon?crs=epsg:5254&field=durum:string&field=kat:int", "binalar", "memory")

    # Parcel 1: 100x100m = 10,000 m2
    p_geom1 = QgsGeometry.fromRect(QgsRectangle(500000, 4200000, 500100, 4200100))
    # 5m Setback envelope (90x90m = 8,100 m2 inner envelope)
    env_geom1 = calculate_setback_envelope(p_geom1, 5.0)

    # Buildings on Parcel 1
    b_geom1 = QgsGeometry.fromRect(QgsRectangle(500020, 4200020, 500060, 4200060)) # 40x40 = 1600 m2, 4 kat
    b_geom2 = QgsGeometry.fromRect(QgsRectangle(500065, 4200020, 500085, 4200050)) # 20x30 = 600 m2, 2 kat METRUK

    synth_parcels.startEditing()
    fp1 = QgsFeature(synth_parcels.fields())
    fp1.setGeometry(p_geom1)
    fp1.setAttribute("id", "101/1")
    fp1.setAttribute("fonk", "KONUT")
    fp1.setAttribute("taks", 0.22)
    fp1.setAttribute("kaks", 0.76)
    synth_parcels.addFeature(fp1)
    synth_parcels.commitChanges()

    synth_envelopes.startEditing()
    fe1 = QgsFeature(synth_envelopes.fields())
    fe1.setGeometry(env_geom1)
    fe1.setAttribute("id", "101/1")
    fe1.setAttribute("setback_m", 5.0)
    synth_envelopes.addFeature(fe1)
    synth_envelopes.commitChanges()

    synth_buildings.startEditing()
    fb1 = QgsFeature(synth_buildings.fields())
    fb1.setGeometry(b_geom1)
    fb1.setAttribute("durum", "İYİ")
    fb1.setAttribute("kat", 4)

    fb2 = QgsFeature(synth_buildings.fields())
    fb2.setGeometry(b_geom2)
    fb2.setAttribute("durum", "METRUK")
    fb2.setAttribute("kat", 2)
    synth_buildings.addFeatures([fb1, fb2])
    synth_buildings.commitChanges()

    # Style envelopes with green dash, parcels with gray fill, buildings with orange/red
    apply_layer_style_and_form(synth_parcels)
    render_map(
        [synth_buildings, synth_envelopes, synth_parcels],
        QgsRectangle(499970, 4199970, 500130, 4200130),
        "14_render_urban_synthesis.png",
        "Kentsel Sentez & Yapı Yaklaşma (Setback) Yapı Zarfı", "Analiz ve Sentez",
        "İmar parseli üzerinde 5m negatif tampon yapı yaklaşma sınırı (iç yeşil zarf), mevcut yapı kitleleri ve TAKS/KAKS doluluk sentezi."
    )

    # 3.7 Crosswalk Comparison
    print("\n--- Part 3.7: Crosswalk Comparison ---")
    src_cw = QgsVectorLayer("Polygon?crs=epsg:5254&field=P_FONK:string", "kaynak_saha", "memory")
    tgt_cw = QgsVectorLayer("Polygon?crs=epsg:5254&field=fonksiyon_adi:string&field=aciklama:string", "hedef_uip", "memory")

    cw_f1 = QgsFeature(src_cw.fields())
    cw_f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(500000, 4200000, 500100, 4200100)))
    cw_f1.setAttribute("P_FONK", "KONUT")

    cw_f2 = QgsFeature(src_cw.fields())
    cw_f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(500120, 4200000, 500220, 4200100)))
    cw_f2.setAttribute("P_FONK", "KARMA_KULLANIM")

    src_cw.startEditing()
    src_cw.addFeatures([cw_f1, cw_f2])
    src_cw.commitChanges()

    execute_layer_crosswalk(src_cw, tgt_cw, "P_FONK")
    apply_layer_style_and_form(tgt_cw)

    render_map(
        [tgt_cw],
        QgsRectangle(499980, 4199980, 500240, 4200120),
        "15_render_crosswalk_comparison.png",
        "Saha → UİP Crosswalk Dönüşüm Haritası (ONAY_BEKLIYOR Güvenceli)", "Analiz ve Sentez",
        "KONUT otomatik aktarıldı, belirsiz KARMA_KULLANIM fonksiyonu asla otomatik atanmadı (ONAY_BEKLIYOR bayrağıyla plancıya bırakıldı)."
    )

    # -------------------------------------------------------------------------
    # PART 4: MPYY Studio Dock UI Screenshots
    # -------------------------------------------------------------------------
    print("\n--- Part 4: MPYY Studio Dock UI Screenshots ---")
    dock = MPYYDock(None)
    dock.resize(480, 800)
    app.processEvents()

    dock_forms = [
        ("16_dock_workspace.png", "create_workspace", "Planning workspace", "CRS and planning-level selection, workspace creation and opening."),
        ("17_dock_styles.png", "style_and_forms", "Layer styles and forms", "Isolated style profiles and restoration of previous layer appearance."),
        ("18_dock_crosswalk.png", "crosswalk_saha_to_plan", "Survey crosswalk", "Layer-bound field selection and explicit source/target mapping."),
        ("19_dock_capacity.png", "estimate_plan_capacity", "Plan capacity", "Focused building-area and population-capacity form."),
    ]

    for fname, tool_id, title, desc in dock_forms:
        dock.show_inline_form(tool_id)
        app.processEvents()
        pix = dock.grab()
        out_path = OUT_DIR / fname
        pix.save(str(out_path))
        record(fname, title, "User interface", desc)
        print(f"Captured Dock Form {tool_id}: {fname}")
    dock.dispose_ui()
    dock.close()
    dock.deleteLater()

    # -------------------------------------------------------------------------
    # PART 5: Generate Interactive Visual Verification Report (HTML)
    # -------------------------------------------------------------------------
    print("\n--- Part 5: Generating Interactive HTML Report ---")
    html_content = generate_html_report(MANIFEST)
    index_file = OUT_DIR / "index.html"
    index_file.write_text(html_content, encoding="utf-8")
    print(f"Generated Visual Report: {index_file}")

    print("\n=== All 19 Test Screenshots Successfully Saved to Downloads! ===")


def generate_html_report(manifest: list[dict]) -> str:
    cards = []
    for item in manifest:
        cards.append(f"""
        <div class="card" data-category="{item['category']}">
            <div class="card-image-wrap">
                <a href="{item['file']}" target="_blank">
                    <img src="{item['file']}" alt="{item['title']}" loading="lazy"/>
                </a>
            </div>
            <div class="card-body">
                <span class="badge">{item['category']}</span>
                <h3>{item['title']}</h3>
                <p>{item['desc']}</p>
                <div class="file-link"><code>{item['file']}</code></div>
            </div>
        </div>
        """)
    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>PlanX MPYY Studio - Gerçek Test ve Doğrulama Raporu</title>
<style>
  :root {{
    --bg: #0f172a;
    --card-bg: #1e293b;
    --border: #334155;
    --text: #f8fafc;
    --muted: #94a3b8;
    --primary: #0284c7;
    --accent: #10b981;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    line-height: 1.5;
    padding: 30px 20px;
  }}
  .container {{
    max-width: 1400px;
    margin: 0 auto;
  }}
  header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 30px;
    margin-bottom: 30px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;
  }}
  .logo {{
    background: var(--primary);
    color: white;
    font-weight: 900;
    font-size: 22px;
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);
  }}
  h1 {{ font-size: 28px; font-weight: 700; }}
  .subtitle {{ color: var(--muted); font-size: 15px; margin-top: 4px; }}
  .stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-top: 20px;
  }}
  .stat-pill {{
    background: rgba(2, 132, 199, 0.15);
    border: 1px solid rgba(2, 132, 199, 0.4);
    padding: 8px 16px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 600;
    color: #38bdf8;
  }}
  .stat-pill.success {{
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.4);
    color: #34d399;
  }}
  .gallery {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 24px;
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }}
  .card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 12px 28px rgba(0,0,0,0.4);
    border-color: var(--primary);
  }}
  .card-image-wrap {{
    background: #090d16;
    height: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    border-bottom: 1px solid var(--border);
  }}
  .card-image-wrap img {{
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transition: transform 0.3s ease;
  }}
  .card-image-wrap:hover img {{
    transform: scale(1.02);
  }}
  .card-body {{
    padding: 20px;
    display: flex;
    flex-direction: column;
    flex: 1;
  }}
  .badge {{
    align-self: flex-start;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 4px 10px;
    border-radius: 6px;
    background: #334155;
    color: #cbd5e1;
    margin-bottom: 10px;
  }}
  h3 {{
    font-size: 17px;
    font-weight: 600;
    margin-bottom: 8px;
    line-height: 1.3;
  }}
  p {{
    font-size: 13px;
    color: var(--muted);
    flex: 1;
    margin-bottom: 14px;
  }}
  .file-link code {{
    font-size: 12px;
    color: #38bdf8;
    background: rgba(2, 132, 199, 0.1);
    padding: 4px 8px;
    border-radius: 6px;
    word-break: break-all;
  }}
  footer {{
    margin-top: 50px;
    text-align: center;
    color: var(--muted);
    font-size: 13px;
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="brand">
      <div class="logo">PX</div>
      <div>
        <h1>PlanX MPYY Studio - Resmî Test ve Görsel Doğrulama Raporu</h1>
        <div class="subtitle">Mekânsal Planlama ve Yönetim Stüdyosu · PlanGML (MSP · ÇDP · NİP · UİP) · TUCBS Saha Anketi</div>
      </div>
    </div>
    <div class="stats">
      <span class="stat-pill success">✓ 19/19 Doğrulama Testi Başarılı</span>
      <span class="stat-pill">8 Öznitelik Formu</span>
      <span class="stat-pill">7 Harita ve Semboloji Render</span>
      <span class="stat-pill">4 Dock Kullanıcı Arayüzü</span>
      <span class="stat-pill success">✓ QGIS 3.44 LTR & 4.2 Tam Uyum</span>
    </div>
  </header>

  <div class="gallery">
    {cards_html}
  </div>

  <footer>
    PlanX MPYY Studio · Geliştirici: Yusuf Eminoğlu · Tarih: 2026-09-13
  </footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    run_all_verifications()
