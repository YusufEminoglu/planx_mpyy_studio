# PLANX MPYY STUDIO — MASTER AGENT EXECUTION SPECIFICATION & BLUEPRINT
**Canonical Autonomous Implementation Directive for Production-Grade Spatial Planning Suite**
**Author & Sole Contributor:** Yusuf Eminoğlu (`yusuf.eminoglu@deu.edu.tr`)
**Workspace Target:** `C:\Users\YE\PyCharmMiscProject\qgis_plugins\planx_mpyy_studio`
**Target Runtimes:** QGIS 3.44 LTR (`C:\OSGeo4W\bin\python-qgis-ltr.bat`) & QGIS 4.2 (`C:\OSGeo4W\bin\python-qgis.bat`)
**Attribution Law (Rule 0):** Absolutely ZERO AI attribution, co-author trailers, or bot signatures. All commits and code attribute solely to Yusuf Eminoğlu.

---

## 1. MISYON VE ÇALIŞMA PROTOKOLÜ (EXECUTIVE DIRECTIVE)

Bu şartname; `planx_mpyy_studio` eklentisini Türkiye'deki mekânsal planlama mevzuatı (*Mekânsal Planlar Yapım Yönetmeliği - MPYY*, *3194 Sayılı İmar Kanunu*, *Planlı Alanlar İmar Yönetmeliği - PAİY*, *Otopark Yönetmeliği*, *Sığınak Yönetmeliği*, *6306 Sayılı Afet Riski Altındaki Alanların Dönüştürülmesi Hakkında Kanun* ve *BÖHYY* standartları) çerçevesinde dünya standartlarında, hatasız, ultra optimize ve eksiksiz bir üretim stüdyosuna dönüştürmek için hazırlanmış **nihai tek-seferde uygulama protokolüdür**.

Bu dosyayı devralan süper-zeki yapay zekâ ajanı, hiçbir ek soru sormaksızın aşağıdaki tüm çalışma paketlerini (Work Packages), kod optimizasyonlarını, yeni algoritmaları, form koşullarını ve testleri **tek bir oturumda, eksiksiz olarak** hayata geçirecektir.

---

## 2. MUTLAK UYULMASI GEREKEN 6 ALTIN KURAL (NON-NEGOTIABLE INVARIANTS)

1. **Rule 0 — Atıf Mutlaktır:**
   - Asla `Co-Authored-By: Assistant`, `Generated with AI`, bot imzası veya yapay zekâ çağrıştıran isim/e-posta yazma.
   - Bütün kod, dokümantasyon, docstring ve commit'ler münhasıran **Yusuf Eminoğlu** adına olacaktır.
   - `py -3 packaging/pf.py attribution` denetiminden %100 temiz (`clean`) geçmelidir.
2. **QGIS Hub Güvenlik Kapısı (Bandit & Detect-Secrets):**
   - Bandit B110 (`try/except: pass`) QGIS Hub tarafından **bloke edilir** ve o sürüm numarası ebediyen yakılır.
   - Asla çıplak `except: pass` kullanma; daima `contextlib.suppress(...)` kullan.
   - Kod içinde parola, token, API anahtarı veya sahte secret yer alamaz.
   - `py -3 packaging/hub_security_scan.py planx_mpyy_studio` daima `CLEAN` vermelidir.
3. **`metadata.txt` İçinde Literal `%` Karakteri YASAKTIR:**
   - QGIS Hub upload scripti Python `configparser` ile interpolation yapar. `metadata.txt` içinde geçen literal `%` karakteri yükleme anında `ValueError: invalid interpolation` hatası verir.
   - Yüzde ifadeleri yerine daima metin olarak `yuzde` yazılmalıdır.
4. **Çift Çalışma Zamanı (Dual Runtime) Uyumluluğu:**
   - Kod ve testler **hem QGIS 3.44 LTR hem de QGIS 4.2 (Qt6)** üzerinde sıfır hata ile çalışmalıdır.
   - `Qt.LeftDockWidgetArea` yerine `Qt.DockWidgetArea.LeftDockWidgetArea`, `Qt.AlignCenter` yerine `Qt.AlignmentFlag.AlignCenter` kullanılmalıdır (`hub_qt6_scan.py` sıfır hata).
5. **Geometri ve Sayısallaştırma Güvenliği (Multipart & Topology):**
   - Asla korumasız `geom.asPolygon()` veya `geom.asPolyline()` çağırma.
   - Daima `isMultipart()` kontrolü yap veya `asGeometryCollection()` / `parts()` kullan.
6. **Klasör ve Paket İsmi Eşitliği:**
   - Klasör adı (`planx_mpyy_studio`) = Zip kök adı = Python import paket adı. Tire veya boşluk bulunamaz.

---

## 3. MEVCUT KOD MİMARİSİ VE DOSYA ENVANTERİ

```text
planx_mpyy_studio/
├── __init__.py                   # classFactory(iface) -> PlanXMPYYStudioPlugin
├── metadata.txt                  # QGIS Hub metadata (version, experimental, icon)
├── main_plugin.py                # Action, toolbar ve dock widget entegrasyonu
├── provider.py                   # QgsProcessingProvider (24 algoritma)
├── dock.py                       # QDockWidget: 4 sekme (Çalışma Ortamları, Stiller, Arazi, Analiz/Sentez)
├── ui_theme.py                   # PlanX Studio kurumsal modern CSS teması
├── .zipignore                    # Paketleme dışlama kuralları
├── CHANGELOG.md                  # Keep a Changelog formatında sürüm tarihçesi
├── LICENSE                       # GPL-2.0-or-later
├── README.md                     # Teknik dokümantasyon
├── forms/                        # PlanGML UİP/NİP/ÇDP/MSP QML formları
├── icons/                        # icon.png (Hub onaylı PNG formatı)
├── styles/                       # Resmi mevzuat QML ve SLD semboloji kütüphanesi
├── tests/                        # unittest test suitleri (LTR ve QGIS 4)
│   ├── test_database_qgis.py     # GeoPackage şemaları ve tablo izolasyon testleri
│   ├── test_styler_qgis.py       # Lejant ve semboloji motor testleri
│   └── test_integration_qgis.py  # 25 adet kapsamlı entegrasyon testi
└── core/                         # 32 adet bağımsız planlama çekirdek motoru
    ├── actions.py                # Harita katman eylemleri (Street View, TKGM, Çekme Zarfı)
    ├── capacity_engine.py        # İmar kapasitesi, emsal hacmi ve nüfus modellemesi
    ├── cdp_styler.py             # ÇDP (1/50.000 - 1/100.000) semboloji motoru
    ├── chamfer_engine.py         # PAİY Md. 20 köşe pahı (chamfer) kırım motoru
    ├── compliance_engine.py      # PAİY Md. 15, 16, 22 yapılaşabilirlik & ifraz-tevhit denetimi
    ├── crosswalk.py              # Saha anketinden PlanGML imar fonksiyonuna eşleme
    ├── db_factory.py             # Taşınabilir GeoPackage ve katalog tabloları fabrikası
    ├── dop_engine.py             # İmar Kanunu Madde 18 DOP hesabı ve tavan (%45) kontrolü
    ├── eplan_catalog.py          # e-Plan Otomasyonu hiyerarşik fonksiyon sözlüğü
    ├── fonts.py                  # Truetype sembol yazı tipleri kaydedici
    ├── form_designer.py          # 5-sekmeli drag-and-drop form, Türkçe takma adlar, kısıtlar
    ├── geom_cleaner.py           # GEOS topoloji onarımı, düğüm silici, saçak temizleyici
    ├── layout_composer.py        # A0-A3 standart baskı paftası, BÖHYY gridi ve Meclis Anteti
    ├── mpyy_catalog.py           # MPYY Detay Kataloğu
    ├── msp_styler.py             # MSP (1/250.000 - 1/500.000) makro strateji semboloji motoru
    ├── nip_styler.py             # NİP (1/5.000 - 1/25.000) nazım plan semboloji motoru
    ├── notation.py               # Yapılaşma ve plan notasyonları
    ├── pafta_index.py            # 1/1.000, 1/2.000, 1/5.000 standart pafta indeks gridi
    ├── parking_engine.py         # Otopark Yönetmeliği araç ihtiyacı ve denge analizi
    ├── plan_diff.py              # MPYY Md. 26 plan tadilatı ve eşdeğer alan denetimi
    ├── plan_notes.py             # Mevzuata uygun dinamik imar planı notları ve lejant hükümleri
    ├── plangml_styler.py         # PlanGML izole stil motoru
    ├── project_binding.py        # Katman ağacı, QgsRelation ilişkileri ve form bağlama
    ├── qc_engine.py              # Mekânsal kalite kontrolü, çekme ihlali ve çakışma tespiti
    ├── qfield_packager.py        # Mobil QField saha çalışması paketleyicisi
    ├── report_exporter.py        # Basıma hazır HTML/MD/CSV Plan Açıklama Raporu motoru
    ├── risk_engine.py            # 6306 s. Afet Riski ve Kentsel Dönüşüm Önceliklendirme motoru
    ├── schema.py                 # Plan kademeleri kesin şema sözleşmesi (MSP, ÇDP, NİP, UİP)
    ├── shelter_engine.py         # Sığınak Yönetmeliği ihtiyaç ve bölge genel sığınak motoru
    ├── styler.py                 # MPYY yerel XML alternatif semboloji motoru
    ├── synthesis.py              # Parsel-bina yoğunluğu ve MPYY EK-2 asgari donatı analizi
    └── zoning_certificate.py     # Resmi İmar Durumu Belgesi (İmar Çapı) üretim motoru
```

---

## 4. TAMAMLANACAK GELİŞTİRME VE OPTİMİZASYON İŞ PAKETLERİ (WORK PACKAGES)

Aşağıdaki 8 İş Paketi, eklentinin kalan eksiklerini, mevzuat boşluklarını ve büyük veri darboğazlarını sıfırlamak üzere tasarlanmıştır:

### İŞ PAKETİ 1: Mekânsal İndeksleme ve $O(N \log M)$ Performans Motoru
- **Sorun/Darboğaz:** `qc_engine.py` (çekme ihlali ve çakışma), `synthesis.py` (parsel-bina sentezi) ve `plan_diff.py` (plan karşılaştırma) algoritmaları $N$ parsel ve $M$ bina üzerinde iç içe döngüyle ($O(N \times M)$) çalışmaktadır. 10.000+ nesneli gerçek kent projelerinde işlem dakikalar sürebilmektedir.
- **Çözüm / Uygulama:**
  - `QgsSpatialIndex` entegrasyonu: Hedef katmanın nesneleri taranmadan önce bir kez `spatial_index = QgsSpatialIndex(target_layer.getFeatures())` oluşturulmalıdır.
  - Geometri kesişiminde `spatial_index.intersects(geom.boundingBox())` ile sadece aday nesneler çekilmeli, ardından `geom.intersects(candidate_geom)` hassas GEOS testi yapılmalıdır.
  - Bu optimizasyon işlem süresini 50 kat hızlandırarak $O(N \log M)$ seviyesine çeker.

### İŞ PAKETİ 2: İmar Parselasyonu ve Şuyulandırma Dağıtım Cetveli Motoru (`core/allocation_engine.py`)
- **Mevzuat Dayanağı:** 3194 Sayılı İmar Kanunu 18. Madde ve *Arazi ve Arsa Düzenlemeleri Hakkında Yönetmelik*.
- **İşlev:**
  - `DOPEngine` kesinti oranını hesapladıktan sonra, kadastro parsellerinin imar adası ve parsellerine dağıtılmasını sağlayan resmi **İmar Dağıtım ve Tahsis Cetveli (Şuyulandırma Matrisi)** motorunu kur.
  - Giren Kadastro Parselleri Cetveli: Ada, Parsel, Malik, Kadastro Alanı ($m^2$), DOP Kesintisi ($m^2$), Net Tahsis Edilecek Alan ($m^2$).
  - Çıkan İmar Parselleri Cetveli: İmar Adası, İmar Parseli, İmar Alanı ($m^2$), Tahsis Edilen Kadastro Hisseleri.
  - Dağıtım Matrisi: `Kadastro (Ada/Parsel) -> İmar (Ada/Parsel)` tahsis oranları tablosu.
  - Hem bellek katmanı (`allocation_layer`) hem de basıma hazır resmi HTML/CSV Dağıtım Cetveli çıktısı verilsin.
  - Processing algoritması: `generate_land_readjustment_matrix` (`İmar Kanunu Madde 18 Parselasyon Dağıtım ve Tahsis Cetveli Üret`).

### İŞ PAKETİ 3: PAİY Madde 5 ve 29 Emsal Harici Alan (%30 Kuralı) ve Net Taban Alanı Motoru
- **Mevzuat Dayanağı:** Planlı Alanlar İmar Yönetmeliği Madde 5 (Emsal Harici Alanlar) ve Madde 29 (Taban Alanı İstisnaları).
- **İşlev:**
  - Yapılaşma hakkı hesaplanırken sadece basit $Area \times KAKS$ değil, **Azami Emsale Dahil Alan** ve **Azami %30 Emsal Harici Alan** (ortak alan, sığınak, otopark, yangın holü vb.) ayrımı yapılsın.
  - Taban alanından muaf olan yapılar: Trafo, su deposu, açık otopark, sığınak girişleri, sarnıç vb.
  - `capacity_engine.py` ve `zoning_certificate.py` motorlarına `%30 Emsal Harici Alan Hakkı ($m^2$)` ve `Toplam Ruhsat İnşaat Alanı (Emsale Esas + Emsal Harici)` alanları eklensin.

### İŞ PAKETİ 4: 7221 Sayılı Kanun Uyarınca "Yençok Serbest" Yasağı ve Hmax Denetimi
- **Mevzuat Dayanağı:** 20.02.2020 tarihli ve 7221 sayılı Kanun ile 3194 sayılı İmar Kanunu 8. maddesine eklenen fıkra: *"İmar planlarında bina yükseklikleri Yençok: Serbest olarak belirlenemez."*
- **İşlev:**
  - Kalite Kontrol Motoruna (`qc_engine.py`) `check_free_height_violations` fonksiyonu eklensin.
  - Planda `yencok`, `katadedi`, `P_KAT`, `HMAX` alanlarında `SERBEST`, `SER`, `H:SERBEST`, `YENCOK:SERBEST` veya `NULL`/boş bırakılmış konut/ticaret adaları tespit edilerek yasal aykırılık hatası (`HUKUKA_AYKIRI_SERBEST_YUKSEKLIK`) raporlansın.
  - Processing algoritması: `validate_quality_control` içine otomatik entegre edilsin.

### İŞ PAKETİ 5: QGIS Dinamik Formlarında Koşullu Görünürlük (Conditional Field Visibility)
- **Kullanıcı Deneyimi:** Form açıldığında kullanıcıyı boğmamak için akıllı form mantığı (`form_designer.py`):
  - Eğer `nizam == 'BITISIK'` ise, formda `yanBahce` alanı otomatik gizlensin (veya pasif olsun); çünkü bitişik nizamda yan bahçe çekmesi $0$'dır.
  - Eğer `nizam == 'BLOK'` ise, blok ebadı ve derinliği alanları görünür olsun.
  - Eğer `yapiYaklasmaDurumu == 'YOK'` ise, çekme mesafesi giriş alanları gizlensin.
  - QGIS `QgsAttributeEditorContainer` üzerinde `setVisibilityExpression()` kullanılarak koşullu sekme ve grup görünürlüğü dinamik hale getirilsin.

### İŞ PAKETİ 6: Topolojik Mikro Yırtık ve Boşluk Onarımı (Sliver & Gap Auto-Healing Engine)
- **Sorun:** CAD'den aktarılan planlarda iki ada/parsel arasında 1cm - 5cm aralığında mikron düzeyinde sahipsiz boşluklar (gaps) veya mikro çakışmalar (slivers) oluşur.
- **Çözüm:**
  - `geom_cleaner.py` içine `heal_topological_boundaries(layers, snap_tolerance=0.05)` fonksiyonu eklensin.
  - Bitişik sınırları tarayıp belirlenen tolerans dahilindeki ($0.05\text{ m}$) ayrık düğümleri ortak doğruya yapıştırsın (shared boundary snapping).
  - Processing algoritması: `clean_planning_geometries` parametrelerine `AUTO_HEAL_GAPS` (Boolean, default True) seçeneği eklensin.

### İŞ PAKETİ 7: Kentsel Dönüşüm Hakediş ve Alan Fizibilite Motoru (`core/feasibility_engine.py`)
- **Mevzuat Dayanağı:** 6306 sayılı Kanun ve Kentsel Dönüşüm Finansal/Alansal Uygulama Esasları.
- **İşlev:**
  - `risk_engine.py` ile tespit edilen `ACIL_DONUSUM` ve `ONCELIKLI_DONUSUM` adalarında mevcut toplam inşaat alanı ($M_{\text{mevcut}}$) ile yeni imar planı inşaat alanı ($M_{\text{yeni}}$) karşılaştırılsın.
  - Müteahhit paylaşım oranı (varsayılan: %45), Hak Sahiplerine düşen net inşaat alanı, Bağımsız Bölüm Hakediş Katsayısı ve Alan Fazlası/Açığı modellensin.
  - Processing algoritması: `evaluate_transformation_feasibility` (`Kentsel Dönüşüm Alan ve Hakediş Fizibilite Analizi`).

### İŞ PAKETİ 8: İmar Çapı Canlı Harita HUD ve Dinamik Çizim Katmanı
- **İşlev:**
  - Harita üzerinde seçilen parselin etrafında; bahçe çekme mesafelerini (kesikli kırmızı çizgiyle çekme zarfı), köşe kot/numaralarını ($P_1, P_2, \dots$) ve cephe uzunluklarını (metre cinsinden etiketlerle) anında canlı çizim geçici bellek katmanına (`memory:imar_capi_hud`) dönüştüren bir görselleştirici eklensin.
  - Şehir plancısı veya belediye görevlisi parseli seçtiği anda ekranda CAD kalitesinde interaktif çap krokisini görsün.

---

## 5. ÇEKİRDEK KOD ŞABLONLARI VE REFERANS KODLAR

### 5.1. `core/allocation_engine.py` (İmar Dağıtım ve Tahsis Cetveli)
```python
"""PlanX MPYY Land Readjustment and Allocation Engine under Planning Law Article 18.
Sole Contributor: Yusuf Eminoğlu
"""
from __future__ import annotations
import contextlib
from dataclasses import dataclass, field
from typing import Any
from qgis.core import QgsFeature

@dataclass
class AllocationItem:
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

@dataclass
class AllocationReport:
    toplam_kadastro_m2: float = 0.0
    toplam_dop_kesinti_m2: float = 0.0
    toplam_tahsis_imar_m2: float = 0.0
    dop_orani: float = 0.0
    items: list[AllocationItem] = field(default_factory=list)
    html_report: str = ""

class AllocationEngine:
    @classmethod
    def calculate_allocation_matrix(
        cls,
        cadastral_features: list[QgsFeature],
        zoning_parcels: list[QgsFeature],
        dop_ratio: float,
    ) -> AllocationReport:
        # Cadastral entitlements calculated via (area * (1 - dop_ratio))
        # Distributed across available zoning parcels using proportional share matching.
        ...
```

### 5.2. `QgsSpatialIndex` ile Hızlandırılmış QC Kesişim Şablonu
```python
from qgis.core import QgsSpatialIndex, QgsGeometry

# Index building (O(M log M))
spatial_index = QgsSpatialIndex()
feature_map = {}
for feat in target_features:
    spatial_index.addFeature(feat)
    feature_map[feat.id()] = feat

# Candidate query (O(log M) per search)
for p_feat in parcel_features:
    p_geom = p_feat.geometry()
    candidate_ids = spatial_index.intersects(p_geom.boundingBox())
    for cid in candidate_ids:
        candidate_geom = feature_map[cid].geometry()
        if p_geom.intersects(candidate_geom):
            # Exact GEOS evaluation
            ...
```

---

## 6. TEST VE DOĞRULAMA ÇERÇEVESİ

Yapılacak tüm geliştirmeler, `tests/test_integration_qgis.py` test paketinde doğrulanmalıdır:
1. `test_processing_provider_and_all_algorithms`: Toplam algoritma sayısını **26'ya** yükselterek test et (`generate_land_readjustment_matrix`, `evaluate_transformation_feasibility` dahil).
2. `test_spatial_index_optimization`: 500 parsel üzerinde kesişim süresinin $1$ saniyenin altında kaldığını doğrula.
3. `test_allocation_matrix_engine_and_algorithm`: Kadastro $\rightarrow$ İmar tahsis cetvelinin alan denkliğini ($\sum \text{Tahsis} + \sum \text{DOP} = \sum \text{Kadastro}$) doğrula.
4. `test_conditional_form_visibility`: Bitişik nizamda yan bahçenin koşullu gizlendiğini doğrula.
5. `test_free_height_violation_detector`: 7221 sayılı Kanun uyarınca "Serbest" yükseklik içeren imar adalarının hata verdiğini doğrula.

---

## 7. TEK KOMUTLA TAM DOĞRULAMA VE PAKETLEME (VERIFICATION PIPELINE)

Geliştirici veya çalışan süper-zeki ajan, tüm kodlamayı bitirdikten sonra terminalde şu komut zincirini sırasıyla çalıştıracaktır:

```powershell
# 1. Plugin Validasyonu (0 warnings olmalı)
py -3 packaging/validate_plugin.py planx_mpyy_studio

# 2. QGIS Hub Güvenlik Taraması (CLEAN olmalı, Bandit B110 ve detect-secrets kontrolü)
py -3 packaging/hub_security_scan.py planx_mpyy_studio

# 3. Qt6 Uyumluluk Taraması (CLEAN olmalı)
py -3 packaging/hub_qt6_scan.py planx_mpyy_studio

# 4. Çift Çalışma Zamanlı (LTR + QGIS 4) Tam Doğrulama ve Entegrasyon Testleri
py -3 packaging/pf.py verify planx_mpyy_studio

# 5. Rule 0 Atıf Denetimi (Yalnızca Yusuf Eminoğlu - CLEAN olmalı)
py -3 packaging/pf.py attribution

# 6. Dağıtım Zip Paketinin Üretilmesi
powershell -ExecutionPolicy Bypass -File packaging/Build-PluginZip.ps1 -PluginDir planx_mpyy_studio
```

---

## 8. SÜRÜM YÖNETİMİ VE METADATA TALİMATI

- Yapılan geliştirmeler sonucunda `version` numarası `1.0.0` (Production Milestone) olarak güncellenecektir.
- `metadata.txt` içinde **kesinlikle hiçbir `%` karakteri bulunmayacaktır**.
- `CHANGELOG.md` güncellenecek, Keep a Changelog standardına uygun olarak tüm yeni motorlar ve algoritmalar listelenecektir.

*Bu belge, PlanX MPYY Studio monorepo geliştirme standardının nihai teknik referansıdır.*
