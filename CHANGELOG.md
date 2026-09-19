# Changelog

## [2.8.0] - 2026-09-19

### Düzeltilen
- **Sınır/çizgi desenlerinde ölçü birimi hataları.** Ek-1e Mekânsal Planlar Detay Katalogları'nın kendi "GEOMETRİ TİPİ" sütunu bazı kalemlerde yanlış: `ManiaPlani`, `HavaalaniHavaKoridoru` ve `SulamaHatti` katalogda "ÇİZGİ" diye geçer ama şemada `MultiPolygon`'dur; bu üçü `vectors` (yalnız LINE) yerine `borders` (POLYGON) altına taşındı — önceki hâlde geometri denetimi hiç eşleşmediği için sınır deseni sessizce hiç uygulanmıyordu. Aynı sınıf hatayı yakalayan `test_catalog_overrides_target_the_schemas_real_geometry_type` denetimi kalıcı hâle getirildi.
- **`create_workspace` menü/form referansı eklentiyi çökertiyordu.** v2.7.0'da Processing algoritması kaldırılmıştı ama satır içi form kaydı ve başlangıç sayfası düğme referansı kalmıştı; `gui/catalog.py`'a araç açıklaması eklendi.
- **Demiryolu ailesinde "boş dikdörtgen" görsel olarak "dolu" ile aynıydı.** Şeffaf dolgu + kalın kontur tekniği, çizgi şekilli işaretçide tüm alanı konturla dolduruyordu (dolgu hiç görünmüyordu); artık gerçekten iki ince kenardan oluşan bir dikdörtgen çiziliyor (Hızlı Tren Hattı).

### Eklenen
- **Ulaşım ve Altyapı Güzergâhları ailesi tamamlandı** (Ek-1e s.147-182): Üçüncü Derece Yol, Demiryolu/Hızlı Tren Hattı/Katar Düzenleme Alanı, Raylı Toplu Taşıma Hattı/Havai Hat/Havaray, Deniz/Su Ulaşım Bağlantısı, Tünel Etki Alanı, İletim Tüneli/Cebri Boru Hattı/Boru Hattı/Doğalgaz Boru Hattı/Akaryakıt Boru Hattı, Sulama Hattı, Bisiklet Yolu. Gerçek ölçüsü olmayanlar (Tünel, Köprü, Yaya Geçitleri, Taşıt Yolu, Enerji Nakil Hattı'nın zikzak genliği) `decisions.json`'a not düşülerek bilinçli atlandı.
- **Su, Atıksu ve Atık Sistemleri ailesi tamamlandı** (s.183-186): Soğutma Suyu Alma Hattı (üçgen + tekrarlayan "S" harfi, çizgi üzerinde), İçme Suyu Ana İletim Hattı (teğet boş daire zinciri), Atık Su Ana Kollektörü/Derin Deniz Deşarj Hattı (dolu ok / boş üçgen).
- **Afet Tehlikeli Alanlar ailesi tamamlandı** (s.144-146, 189-191): Kentsel Risk Alanı/Yapı Yasaklı Alan (kesikli çizgi), Tsunami Riskli Alan/Kütle Hareketi Riskli Alan/Fay Sakınım Zonu/Taşkına Maruz Alan/Heyelan Alanı (tabanı eksik üçgen dizisi), Afete Maruz Bölge (3'lü üçgen öbeği).
- **Sınır üzerinde tekrarlayan yazı artık çizgi (LINE) geometrisinde de çalışıyor**, önceden yalnız poligon çevresinde (`PerimeterCurved`) vardı; Soğutma Suyu Alma Hattı'nın "S" harfi `Qgis.LabelPlacement.Line` ile çizginin kendisi boyunca tekrarlanıyor.
- Yeni çizim türleri: iki katmanlı ray+bağ (`line_ties`, dolu/boş sıra ve çift yan ray desteğiyle), çizgi üstü ikinci çizgi (`line_overlay`), tekrarlayan işaretli çizgi (`line_marked`, üçgen/ok, dolu/boş), dik çentik+dikdörtgen (`line_tick_tie`), çizgiye teğet daire zinciri (`line_circles`), dik çentik tarağı (`line_ticks`).

## [2.7.0] - 2026-09-18

### Kaldırılan
- **Eski MSP/ÇDP/NİP/UİP çalışma alanı şeması kaldırıldı.** `mpyy_<kademe>_alan/cizgi/notasyon` tabloları gerçek MPYY değildi: geometri türleri katalogla uyuşmuyordu, tekrar eden alanlar vardı ve öznitelik formlarında açılır liste yoktu. Bununla birlikte kaldırılanlar: `create_workspace` işlem algoritması (86 algoritma kaldı), MSP/ÇDP/NİP stil motorları, panelin plan kademesi seçenekleri ve bu şemaya bağlı testler. Kalan çalışma alanları: **MPYY 1.1.7 şemaları**, **Yerel UİP (MpyyUipDb)**, **Yerel NİP (MpyyNipDB)** ve **Arazi kullanımı / saha anketi**.

### Eklenen
- **Yerel NİP çalışma alanı (MpyyNipDB 1/5.000 çizim şablonu).** Kullanıcının kendi GeoPackage'ındaki QGIS projesinden dondurulan katmanlar, stiller, formlar, 169 satırlık fonksiyon tablosu ve fonksiyon ilişkisi; `tools/extract_local_nip_template.py` ile üretilir. Yalnız çizim katmanları alınır: halihazır, meri plan katmanları, saha katmanı ve uydu servisi şablona girmez.
- **Askeri yasak ve güvenlik bölgesi sınırı** Ek-1e s.24'e göre çizilir: 0,3 mm kırmızı çizgi, 7 mm'de bir 3 mm'lik çarpı ve sınır üzerinde AYB yazısı. SLD'den gelen kırmızı daireler kaldırıldı.

## [2.6.1] - 2026-09-18

### Düzeltilen
- **Çizgi desenlerinde aralık yoktu, semboller ilk kırılma noktasında üst üste biniyordu.** QGIS, SLD'de bir çizgi ya da dolgu içindeki grafiği boyutu olmadan okuyor ve işaret çizgisini 0 aralıkla bırakıyor. MPYY stillerindeki 629 işaret çizgisinin tamamı bundan etkileniyordu (ÇDP enerji nakil hattı, askeri yasak bölge sınırı, taşkın ve tsunami sınırları). Aralık artık GeoServer'ın çizdiği gibi çizgi deseninin toplamından, desen yoksa sembolün kendi boyundan alınıyor; sembol boyutları da SLD'deki ölçü ve birimle uygulanıyor.
- **Sembol katmanları indeks yoluyla çözülüyor.** Alt sembolden alınan bir katman, ağaç dolaşılırken geçerli kalmıyordu; bu QGIS'i çökertiyordu.
- Paket `.claude` çalışma ağaçlarını içermiyor (QGIS bu kopyayı ayrı bir eklenti sanıp yükleme hatası veriyordu) ve satır sonları LF.

## [2.6.0] - 2026-09-17

### Düzeltilen
- **Öznitelik formu açılır listeleri çalışmıyordu.** Stil uygulandıktan ve çalışma alanı yüklendikten sonra genel form tasarımcısı QML formunu siliyor, koşullu sekmelerin yerine genel sekmeler koyuyordu. Nizam listesine `BITISIK`, `IKIZ` gibi GeoPackage CHECK kısıtının reddettiği kodlar yazdığı için kayıt hiç kaydedilemiyordu. Yazılmış formu olan katmanlara artık dokunulmuyor.
- **UİP fonksiyon listesi grup adı gösteriyordu.** MPYY çalışma alanında `uipPolygonTable` stilsiz yüklendiği için zincirli listede fonksiyon yerine üst grup adı çıkıyordu.
- **QML dosyaları metin düzeyinde bozulmuştu.** Çeviri turları QGIS'in iç `type` anahtarını `Nitelik` yapmış (11 dosyada 887 yer), notasyon SVG sembollerini yazı tipi sembolüne çevirmişti. UİP formları artık kullanıcının çalışan şablonundan QGIS ile dışa aktarılıyor; arazi formlarındaki anahtarlar onarıldı.
- **MPYY UİP stili hiçbir nesneyle eşleşmiyordu.** Kategoriler hiçbir formun doldurmadığı `catalog_id` (`POLYGON:1`) alanına kuruluyordu; artık formun yazdığı `uipfonksiyon` değeriyle eşleşiyor.
- **Yerel XML stil kataloğu** `katadedi`, `yolGenislik` gibi alan adlarını var olmayan adlara çeviriyor ve yapı yaklaşma sınırını çizen 79 geometri üretecini kapatıyordu. İkisi de kaldırıldı; fonksiyon adıyla eşleşme eklendi.

### Eklenen
- **Gösterim Ek-1e Mekânsal Planlar Detay Katalogları'na (22.01.2026) göre tamamlandı.** Katalog 192 sayfa kalem kalem eklentiyle karşılaştırıldı (`Downloads\MPYY_Ek1e_katalog_karsilastirma.xlsx`); Bakanlık SLD'siyle çeliştiği yerde katalog esas alındı (`core/mpyy_detail_catalog.py`, kararlar ve sayfa numaraları `styles/mpyy_detail_catalog/decisions.json`).
  - Bakanlığın yayımlamadığı `TaramaSembol` SVG'leri ve arşivde olmayan `Intelli Eplan` karakterleri yerine aynı kalemin katalog sembolü kullanılır (24 sembol, katalog sayfasından 600 dpi kesit): askeri alan, sınır kapısı, stratejik karar, afet lojistik, kentsel arkeolojik sit, kentsel risk, tsunami, kütle hareketi, vahşi çöp, sokak hayvanları barınağı, millet bahçesi, yapay ada, ekoturizm, sağlıklaştırma…
  - Ölçüyle tanımlananlar kataloğun ölçüsüyle çizilir: ÇDP il/ilçe/belde/köy merkezleri (s.35–38), ÇDP otoyol, 1. ve 2. derece yol kesitleri (s.147–149), bisiklet yolu (s.153).
  - Katalog renk kutusundan alınan renkler: yapay ada, ÇDP kıyı tesisleri, toplu taşım aktarma, atık geri kazanım. Eksik taramalar: doğal ve ekolojik alan ile ekolojik öneme sahip alan diken taramaları (QGIS'e aktarılamıyordu), atık geri kazanım noktalaması, ÇDP fuar alanı serbest noktalaması, NİP taşkına maruz alan, havai hat istasyonu. Makilik-fundalık ve tarımsal nitelikli alana katalog sembolü eklendi; yaya yolu genişliği taşıt yolundaki gibi daire içinde yazılır.
  - Katalogda kalemi olmayan, bu yüzden hâlâ gri `?` ile işaretlenen semboller: UİP/NİP özel sosyal, kültürel, açık ve kapalı spor tesisi alanları; ÇDP günübirlik, yayla, kış, sağlık ve ekoturizm; MUİP özel sosyal kültürel tesis ve yüksek öğretim kampüsü. Cemevi alanı, motokurye park alanı ve turizm merkezi alt bölge sınırı MPYY 1.1.7 şemasında yoktur.
- **Detay kataloğu gösterim boşlukları kapatıldı.**
  - Bakanlık SLD'lerinde UUID'si bozuk yazılmış 11 tarama karosu (`bc40m`, `40mm40mm`; aynı dosyada `<Size>40m</Size>` olan toplu bir `40`→`40m` düzenlemesi) arşivdeki doğru karoya bağlandı; eksik karo kalmadı.
  - Tek kurallı SLD'ler (UİP/NİP/ÇDP `ManiaSiniri`, ÇDP `StratejikKarar`, `Planlama_AltBolge`, `Stratejik_AltBolge`, `YenilenebilirEnerji…`) QGIS'e tek sembol olarak geldiği için reddediliyordu; artık uygulanıyor.
  - **Yol genişliği yazısı** (UİP/NİP/MNİP `Yolorta`): Bakanlık stilindeki gibi aks ortasında ESRI Default Marker dairesi (çap = yol genişliği × 1,75 m) ve içinde genişlik (ondalık kısmı altı çizili), 1:2000 ve büyük ölçeklerde.
  - **Yapılaşma notasyonu** (TAKS/KAKS alanları olan tüm UİP/MUİP katmanları), Ek-1e Mekânsal Planlar Detay Katalogları (22.01.2026, s.39–43) düzeninde: 18 mm'lik yapı düzeni dairesi (solda `A-`/`B-`/`BL-`, sağda kat adedi, üstte ön bahçe, altta yan bahçe), 18 mm'lik TAKS/KAKS dairesi (TAKS çizginin üstünde, KAKS altında), `E =` ve `Yençok = … m` yazıları; yazı 5 mm, 1/1000 ölçekte harita birimi. `SembolPoz` iki koordinat içeriyorsa notasyon oraya konur. Katalogda İkiz ve Serbest nizam için harf tanımlı olmadığından bu ikisinde harf yazılmaz.
  - M serisinde Bakanlık stili olmayan tipler güncel kademenin aynı (ya da `m_borrow` ile anlamca eşlenen: `KentselDogalmge`→`KentselImge`, `DevletSinir`→`UlkeSiniri`, `MucavirSahaSiniri`→`MucavirAlanSiniri` …) tipinin stilini kullanır; yalnızca alanı ve kodu M şemasında bulunan kurallar alınır. MÇDP25 45, MÇDP100 48 tip gösterim kazandı.
  - Bakanlık SLD'lerinde şemadaki alan adıyla eşleşmeyen filtre özellikleri bağlandı; bu kurallar hiçbir nesneyle eşleşmiyordu: NİP `KentselDonusumSinirlari` (`kent_don_sinir_tip`), MUİP `AdaKenari` ve `IcmesuTesis`, MNİP `DonusumKonutAlanlari` ve `OckHassasAlan` (şemadaki alan adı noktasız ı ile `HassaslıkDerecesi`). MUİP `AdaKenari`'nda iki kural da 'ONERILEN' başlıklı olduğundan Korunan cephe hattı liste sırasıyla çözüldü.
  - SLD etiketlerindeki bozuk Türkçe karakterler (`YENÝLEME`, `ÝSK`) düzeltildi.
  - Arşivde olmayan `Intelli Eplan` fontu ve Bakanlık sunucusundaki `TaramaSembol` SVG'leri başka bir sembolle **ikame edilmez**: yerlerine gri `?` çizilir ve katmana `mpyy/missing_symbols` notu düşülür. Tahoma yoksa aynı Unicode karakter DejaVu Sans ile çizilir.
- **MPYY 1.1.7'ye yükseltme.** Bakanlığın güncel şema paketi (`https://eplan.csb.gov.tr/e-plan/doc/planGMLShema_1_7.zip`; UİP/NİP 1.1.7 7 Eylül 2026, ÇDP 1.1.7 Temmuz 2026) esas alındı: UİP 96, NİP 87, ÇDP 72 nesne tipi. Farklar `docs/MPYY_1.1.6_1.1.7_FARKLAR.md` içinde (`tools/diff_mpyy_versions.py`). 1.1.7 önceki sürümün boşluklarını kapattı: `TuzlaAlani`, `KentselArkeolojikSit`, `ManiaSiniri`, ÇDP'de `DepolamaAlani`, `KamuHizmetAlani`, `AgaclandirilacakAlan`, tanımlı `EnerjiDagitimDepolama`, `OrganizeTarimVeHayvancilikAlani` yazımı. Bakanlık SLD setinde çözülemeyen kural kalmadı; yeni `AraziKullanimiDevamEttirilerekKorunacakAlanlar` tipi `*_ARAZI_KULLANIMI_KORUNACAK_ALAN` stiline bağlandı; 'Kentsel Arkeolojik Sit' için KA hat etiketi eklendi.
- 1.1.6 ile oluşturulmuş çalışma alanları hata vermeden açılır; şema denetimi 'Şema sürümü farklı', 'Şemadaki katman dosyada yok' ve 'Şemadaki alan tabloda yok' bulgularını raporlar.
- **Hat etiketleri.** Detay kataloğunda sınır üzerine yazılması istenen kısaltmalar (sit alanlarında A1–A3, D1–D3, KK, ND, SK, KS, TS, SEG; koruma kuşaklarında HKK, YKK, BHK, SKK, İSK, YSK, DKK, YPK, SKB, ENH; AYB, TEA, NİP'te RA, RYA, YENİLEME) ilgili MPYY kodunun sınırı boyunca, sınır renginde tekrarlı yazılır (`styles/mpyy_line_labels.json`). UİP 26, NİP 17, ÇDP 12 kural; MPYY 1.1.6'da kodu olmayan 'Kentsel Arkeolojik Sit' alınmadı.
- **MPYY GML dosyasını içe aktar** (`import_mpyy_gml`): e-Plan GML dosyasını GeoPackage çalışma alanına okur. M serisi şemalar (MUİP, MNİP, MÇDP25, MÇDP100 1.1.6) Bakanlık paketinden derlendi (`styles/mpyy_m_schema.json`); güncel UİP/NİP/ÇDP şemaları da seçilebilir. Şema otomatik belirlenir (`xsi:schemaLocation`, yoksa öğe adları ve `YeniKod`). GML 2 ve GML 3/3.2 geometrileri GDAL ile okunur, `srsName` koordinat sistemine dönüştürülür. Rapor: tip başına adet, aktarılan, geometri sorunu, bilinmeyen öznitelik ve kod listesi dışı değer. MUİP/MNİP katmanları e-Plan SLD gösterimini alır. Gerçek bir e-Plan GML örneğiyle değil, şemaya uygun sentetik dosyalarla sınandı.
- **MPYY kademesini dönüştür** (`convert_mpyy_level`): UİP → NİP / ÇDP ve NİP → ÇDP. Tip ve kod karşılıkları UİP/NİP/ÇDP tabaka eşdeğerlik tablosundan, iki yandaki doğrulanmış tabaka eşleşmesi üzerinden kurulur (`styles/mpyy_level_conversion.json`). Üst kademenin kendi karar vermesi gereken kodlar (yoğunluk kademesi gibi) boş bırakılır ve raporlanır; farklı tipler arasında eşit oylu karşılıklar için kural kurulmaz. Geometri genelleştirilmez.
- Tabaka eşleşmesinde XSD'ye uyan ama anlamca yanlış satırlar düzeltildi: ÇDP'de yeşil spor alanı ve organize tarım-hayvancılık il idari merkezine, kıyı tesisleri meraya gidiyordu; etaplama/mahalle/kentsel tasarım sınırları plan onama sınırına yazılıyordu.
- **CAD tabakalarını MPYY çalışma alanına aktar** (`import_cad_to_mpyy`): CAD/NCZ tabaka adları (ör. `PL_TICARET`) MPYY 1.1.6 nesne tipine ve koduna (`KentselCalisma`, `CalismaTip=TicaretAlani`) çevrilerek yazılır. Kapalı CAD çizgileri alana dönüştürülür, çok parçalı çizgiler tek parçalı tiplere bölünür; eşleşmeyen tabakalar ve geometri uyuşmazlıkları (`şema: çizgi, veri: alan`) raporlanır. Eşleşme tablosu (`styles/mpyy_tabaka_crosswalk.json`) yazarın uygulamasındaki tablolardan alınıp XSD'ye karşı denetlenmiştir; NİP/ÇDP'ye uymayan satırlar kademe karşılığıyla düzeltilmiş (ör. gelişme konut → NİP `GelismeKonut`, ÇDP `KentselGelismeKonut`) ya da gerekçesiyle dışarıda bırakılmıştır.
- **MPYY şema uygunluğunu denetle** (`audit_mpyy_workspace`): zorunlu boş alanlar, kod listesinde olmayan değerler, geometri türü uyuşmazlığı, geçersiz geometri ve şemada olmayan katmanlar CSV olarak raporlanır.
- SLD setinde karşılığı eksik gösterimler için anlamsal kararlar (`styles/mpyy_sld/decisions.json`): kısaltılmış/yakın resmî stiller, boş değer kuralı ve detay kataloğu tanımından çizilen Kentsel Tasarım Projesi Sınırı.
- **MPYY çalışma alanı (UİP / NİP / ÇDP).** Tablolar, alan adları, sırası, türleri, zorunluluk bilgisi ve kod listeleri Bakanlığın resmî XSD şemasından (`https://eplan.csb.gov.tr/e-plan/planGML/planGMLShema_1_6.zip`) `tools/compile_mpyy_schema.py` ile türetiliyor: UİP 90, NİP 81, ÇDP 60 nesne tipi. Kod listeleri şemanın kendi değerini saklayan açılır listelerdir; zorunlu alanlar taslağı engellemeyen uyarı olarak işaretlenir, eksikler `audit_required_fields` ile raporlanır. Formlar GeoPackage'a varsayılan stil olarak yazıldığından eklenti olmadan açılan QGIS'te de açılır listeler gelir. ÇDP şemasında listelenip tanımlanmamış `EnerjiDagitimDepolama` için tablo oluşturulmaz ve kayıt altındadır. Semboloji Bakanlığın e-Plan GeoServer SLD'lerinden gelir: stil adı tip adından, filtre kod listesindeki sıradan çözülür (`tools/compile_mpyy_eplan_styles.py`); taramalar kayıpsız PNG olarak stile gömülür, QGIS'in düz daireye çevirdiği `ttf://` işaretleri font sembolü olarak geri kurulur. Sıra ile başlığın çeliştiği, çözülemeyen ya da kısaltılmış adla eşleşen kurallar `mapping.json`'da kayıtlıdır ve onaya sunulmuştur. SLD'si olmayan 4 tip ve QGIS'in aktaramadığı `Yolorta` (yalnız yazı sembolü) nötr kalır.
- **Yerel UİP çalışma alanı (MpyyUipDb çizim şablonu):** `uip-alanlar`, `uip_cizgiler`, `uip-notasyonlar`, `yapi_yaklasma`, `uipPolygonTable` ve `uipLineTable` kaynak şablonla aynı tablo, alan ve tür yapısında oluşturuluyor. Sembolojiyi, sekmeleri, açılır listeleri ve varsayılan değerleri taşıyan katman tanımları `tools/extract_local_uip_template.py` ile şablondan QGIS üzerinden alınıyor (`forms/yerel_uip`, SHA-256 manifestli).
- Açılır listeleri gerçek widget'larla dolduran, her liste değerini veritabanına yazan ve stilin girilen değerle eşleştiğini doğrulayan `test_forms_dropdowns_qgis` (9 test, QGIS 3.44 ve 4.2).

## [2.5.3] - 2026-09-17

- Upgraded official plugin icon to high-end tactile 3D brand identity (isometric 45°, slim teal pedestal, full bleed transparent canvas).
- Synchronized documentation, repository and issue tracker endpoints to GeoPhilo and GitLab.

## [2.5.2] - 2026-09-15

### Değişen
- Kullanıcının son dil tercihine göre eklentiye ait arayüz, işlem yardımı, parametreler, seçenekler, bildirimler, formlar, lejantlar, harita bilgi kartları ve raporlar Türkçeleştirildi.
- Türkçe gösterim sözlüğü ve yerel QGIS ifadeleri; kaynak kataloglar, mevzuat kodları, şema alanları ve kullanıcı adları korundu.
- Türkçe karakterlerden bağımsız arama, Türkçe dil denetimleri ve kullanıcı kılavuzu güncellendi. Önceki teknik ayrıntılar geliştirme geçmişinde korundu.

## 2.5.1 - 2026-09-15

- Completed English interface copy across all 83 Processing tools, parameter captions, enum options, help and operation messages.
- Translated planning and survey form tabs, field aliases, constraints, dropdown captions and renderer legends.
- Translated generated plan provisions, report text, zoning certificates, allocation and feasibility schedules, MapTips, layer actions and QField package instructions.
- Added reviewed English display labels separate from statutory catalogs and stored code values.
- Added portable native QGIS lookup displays and preserved raw keys, filter expressions, schema field identities and user-supplied names.
- Added six language regression checks covering Processing, real workspace forms and legends, lookup representations, reports, MapTips and shipped QML labels. The registered suites now contain 126 tests.

## 2.5.0 - 2026-09-15

- Replaced four overloaded dock tabs with Start, Tools and Activity.
- Added daily workflow guidance and an 83-algorithm catalog grouped by task, with purpose, required inputs and expected outputs.
- Added accent-insensitive search, category filters, saved shortcuts and recent tools.
- Added explicit configuration opening, keyboard search and activation, focused compact forms and input preservation when navigating back.
- Split the dock into navigation, metadata, reusable widgets, form construction and action modules; preserved existing engine calls and parameter defaults.
- Replaced free-text function-field inputs with layer-bound field selectors; left target layer selectors empty until a user chooses one.
- Added wrapping labels and action buttons, inherited QGIS font sizes, control names and label buddies.
- Corrected selected-item contrast and Windows dark-theme numeric editors while preserving native spin arrows.
- Kept long result details in a copyable Activity log and shortened the dock status summary.
- Added twelve GUI interaction/layout regression tests and a reproducible real Qt screenshot harness for narrow/wide docks, normal/enlarged text and light/dark palettes.
- Preserved 83 algorithms; the registered suites contain 120 tests.

## 2.4.0 - 2026-09-15

- Added standalone schema profile identity verification with optional independent SHA-256 pin and source CSV reconstruction.
- Added deterministic identity reports that explicitly leave issuer authenticity unverified.
- Added automatic declared identity checks before inspecting a GeoPackage schema; changed imported profiles cannot produce a complete audit.
- Preserved unsigned legacy schema profiles while requiring identities on imported profiles.
- Rejected duplicate JSON keys and non-finite JSON values in profiles and import mappings.
- Protected profile and dictionary inputs against identity-report overwrite.
- Replaced full route-mode tuple copies with immutable shared mode tails and demand-time rendering caches.
- Built incoming graph arcs directly to avoid retaining a duplicate outgoing graph.
- Added cancellation checks during graph construction, spatial indexing, destination initialization, search and demand evaluation.
- Removed the 80-character route-mode field limit from multimodal output.
- Added a reproducible synthetic two-scenario benchmark at 1,000, 3,000 and 6,000 edges on both target QGIS runtimes.
- Preserved exact reference result identities; the 6,000-edge fixture reduced traced Python peak memory from about 167 MB to 6.7 MB.
- Added eight regression tests, bringing the registered suites to 108 tests and the provider to 83 algorithms.

## 2.3.0 - 2026-09-15

- Added paired network and facility accessibility scenarios evaluated against a single shared demand layer.
- Added per-demand status, facility, mode sequence, snap distance, travel time and proposed-minus-baseline time change outputs.
- Distinguished faster/slower travel, route gain/loss, unchanged unreachable demand and snap uncertainty without inventing missing travel times.
- Added common projected metre CRS, mode-field, input and output-writing guards for scenario comparison.
- Corrected directed multimodal traversal to measure demand-to-facility travel and report modes in travel order.
- Added an explicit CSV dictionary-to-GeoPackage-profile importer with source institution, reference, version, mapping and SHA-256 provenance.
- Rejected duplicate fields, malformed rows, ambiguous headers, invalid booleans and conflicting geometry declarations.
- Protected dictionary and mapping inputs against output overwrite.
- Enforced declared primary-key requirements in the read-only GeoPackage profile audit.
- Added editable CSV dictionary and JSON import mapping examples, explicitly marked as illustrative.
- Documented the existing building morphology, Spacematrix density, street morphology, plan-metric scenario comparison and accessibility equity tools.
- Registered two new Processing algorithms and dock actions; the provider now exposes 82 algorithms.
- Added ten value-based dual-runtime regression tests; the registered suites now contain 100 tests.

## 2.2.0 - 2026-09-15

- Added a read-only GeoPackage schema audit driven by an administration-supplied, versioned JSON profile.
- Added required table, field, SQLite type, nullability, primary-key, geometry-registration, geometry-type, and SRS checks.
- Kept Ministry data structures outside hard-coded plugin logic so an authoritative profile can be replaced without a code release.
- Added deterministic recursive dossier inventories with normalized relative paths, file sizes, SHA-256 identities, and total byte counts.
- Excluded the inventory output itself from repeated inventory runs.
- Added explicit plan-note to decision-code relationship auditing under the Article 7 plan-component integrity principle.
- Added unknown decision references, empty note text, duplicate note identity, duplicate decision code, and optional unlinked-decision findings.
- Added chronological plan version chains using unique SHA-256 content identities and exact parent hashes.
- Added root-parent, broken-chain, duplicate-version, duplicate-content, invalid timestamp, and non-chronological version checks.
- Added time-weighted multimodal accessibility across walking, bicycle, and transit edges.
- Added per-feature mode, optional speed, optional explicit travel time, bidirectional or directional travel, and configurable transfer penalties.
- Distributed explicit feature travel time across its segments by measured length.
- Added walking-time costs for demand and facility network snapping.
- Added projected and common CRS guards in the Processing interface.
- Indexed the best multimodal state per graph node after Dijkstra traversal for constant-time demand lookup.
- Kept travel-time thresholds user-declared rather than presenting them as statutory MPYY limits.
- Expanded the dossier initializer with plan-note link and version-chain manifests.
- Added four editable profile and manifest examples.
- Registered five new Processing algorithms and five dock actions, bringing the provider to 75 algorithms.
- Expanded the dual-runtime suite to 85 tests.

## 2.1.0 - 2026-09-15

- Added an MPYY Article 7 participation register audit with documented method, date, stakeholder groups, announcement, attendance, outcome, and input-disposition checks.
- Added MSP-specific stakeholder coverage for public institutions, development agencies, universities, local governments, civil society, professional chambers, and private-sector representatives under Article 14/1-e.
- Added an Article 7/1-k cancelled-plan evidence re-evaluation register.
- Distinguished reused, superseded, and rejected institution opinions, analysis, and synthesis without assuming that old evidence remains current.
- Added cancelled-plan and cancellation-decision traceability plus current-version references for reused evidence.
- Added identity consistency auditing across plan sheets, official displays, plan notes, and plan reports under Article 7/1-b.
- Added common plan ID, version, level, purpose, duplicate-role, and SHA-256 checks.
- Added an Article 32 approval-sheet register for Plan Transaction Number, approval date and number, front-face marking, stamp status, sheet identity, and duplicate detection.
- Added Articles 34-35 digital delivery package auditing for required plan components, geological studies, geospatial plan data, Ministry format-profile declaration, CRS, delivery receipt, destination, and fifteen-day delivery period.
- Added path-containment, physical-file, SHA-256, and machine-readable geospatial dataset checks to digital delivery.
- Expanded the dossier initializer with five new editable administrative-integrity manifests.
- Added five standalone example manifests.
- Registered five new Processing algorithms and five dock actions, bringing the provider to 70 algorithms.
- Expanded the dual-runtime suite to 80 tests.

## 2.0.0 - 2026-09-15

- Added a non-destructive MPYY plan-dossier initializer with dedicated plan, research, opinion, approval, publication, delivery, and audit-report directories.
- Added context-sensitive dossier completeness profiles for MSP, CDP, NIP, and UIP under MPYY Articles 7 and 31-35.
- Added plan-change, mixed-use, coastal, conservation, urban-design, and finalized-plan role expansion.
- Added dossier path-containment checks, local file existence checks, duplicate-role detection, and SHA-256 identity verification.
- Added owner-declared evidence freshness auditing based on explicit validity dates or review intervals.
- Kept evidence-age policy separate from statutory requirements; the tool does not invent a legal expiration period.
- Added empty-register, invalid-date, future-verification, invalid-interval, and expired-evidence findings.
- Added feature-level mixed-use auditing under Articles 9/5 and 21/10.
- Applied the Article 21/10 residential maximum default of 0.30 only when a residential mixed-use ratio is not stated, with an explicit review finding.
- Added plan-report, plan-note, parking, green-area, social and technical infrastructure, residential infrastructure, and conditional independent-unit checks.
- Added Article 33 physical and web publication synchronization, publication-period, minute-signature, and local-announcement auditing.
- Added objection receipt, forwarding, decision chronology, and plan-change republication checks.
- Added four editable manifests and field-reference examples for the new workflows.
- Registered five new Processing algorithms and five dock actions, bringing the provider to 65 algorithms.
- Expanded the dual-runtime suite to 75 tests.

## 1.9.0 - 2026-09-14

- Added an MPYY Article 8 research dossier audit for institution data, digital sources, National Geographic Information System portal review, numerical delivery, threshold work, current-plan evaluation, research, and reporting.
- Added conditional Article 8 checks for disaster risk, large-scale land uses, conservation plans, and NIP institution service-area needs.
- Corrected institution-opinion expiry semantics under Article 8/2: no response within the applicable period is recorded as `DEEMED_NO_NEGATIVE_OPINION`, not a violation.
- Separated genuinely late responses as `LATE_RESPONSE_REVIEW` and retained invalid-date detection.
- Added an MPYY Article 10 exact official-display catalog audit across MSP, CDP, NIP, and UIP.
- Merged shipped e-Plan, MSP EK-1e, and 22 January 2026 supplemental catalogs for exact code matching.
- Reported unknown display codes as `UNMAPPED_REVIEW` rather than making an automatic legality claim.
- Added an MPYY Article 11 contextual standards dossier audit.
- Added conditional alternative-standard, settled-area, conservation-site, seasonal-tourism, infrastructure, permanent-population, and parking evidence checks.
- Added an MPYY Article 25 code-aware plan intervention classifier.
- Distinguished revision, contiguous addition, ordinary plan change, and no-change review using measured current/proposed geometry and decision codes.
- Added explicit addition contiguity, need, land-use continuity, integrity, compatibility, and revision-rationale findings.
- Added a consolidated MPYY audit bundle with deterministic SHA-256 identity verification.
- Kept aggregation status-based and deliberately omitted a synthetic compliance score.
- Rejected tampered reports, missing hashes, malformed JSON, and unknown report statuses from a complete bundle result.
- Added editable Article 8 and Article 11 example manifests.
- Registered five new Processing algorithms and five dock actions, bringing the provider to 60 algorithms.
- Expanded the dual-runtime suite to 70 tests.

## 1.8.0 - 2026-09-14

- Added an MPYY Article 9 plan-report content audit covering vision, objectives, strategies, protection-use principles, land use, density, implementation, open-green systems, transport, accessibility, and area distribution.
- Added mandatory plan-change rationale and necessity-analysis checks under Article 9/4.
- Added mixed-use ratio, parking, green-area, infrastructure, and independent-unit detail checks under Article 9/5.
- Added reasoned `not_applicable_sections` support for content governed by plan type, scale, scope, and characteristics.
- Added an MPYY Article 12 routed walking-distance audit with automatic facility-type profiles.
- Added the approximate 500 m, 1,000 m, 2,500 m, 250 m, 400 m, and 150 m statutory screening distances.
- Added official-name aliases for family health centers, district mosques, open district sports, and child play areas.
- Separated low-density, dispersed-rural, and natural/artificial-barrier cases as Article 12/4 exception review rather than automatic compliance.
- Added an MPYY Article 27 conservation plan dossier audit.
- Added site coverage, settlement relationship, site-specific strategy, disaster resilience, board/commission decision, asset inventory, historic fabric, and harmful-function-change checks.
- Added conditional competent-authority opinion evidence for overlapping protection statuses.
- Added an MPYY Articles 28-29 integrated coastal area plan dossier audit with planning-boundary rationale and twenty strategy/analysis themes.
- Added an MPYY Article 30 urban design project prerequisite audit.
- Prevented an implementation-ready result when the implementation plan approval is not evidenced.
- Added solid-void, building relationship, pedestrian/vehicle movement, natural, cultural, social-economic, transport, and infrastructure evidence checks.
- Added four editable MPYY dossier manifest examples and deterministic SHA-256 audit reports.
- Registered five new Processing algorithms and five dock actions, bringing the provider to 55 algorithms.
- Expanded the dual-runtime suite to 65 tests.

## 1.7.0 - 2026-09-14

- Added MPYY Article 22 evidence provenance auditing for source institution, acquisition date, version, CRS, scale or resolution, and SHA-256 identity.
- Added conditional coastal, water-basin, protected-area, and hazard evidence coverage requirements.
- Added optional verification of declared local evidence files against their SHA-256 identities.
- Added MPYY Article 8 institution-opinion register auditing with initial and extended thirty-day periods.
- Distinguished timely, pending, overdue, late-response, and invalid opinion records.
- Added atomic JSON evidence and opinion reports with deterministic content identities.
- Added valid evidence-provenance and institution-opinion example manifests.
- Added actual NIP-UIP network accessibility based on multi-source Dijkstra shortest paths.
- Distinguished accessible, over-threshold, disconnected, and unsnapped demand features.
- Used a single facility-seeded graph traversal for efficient large demand-layer evaluation.
- Added MPYY Article 7 adjacent-plan seam coverage and optional decision-code consistency auditing.
- Added whole-plan polygon fabric auditing for invalid decisions and internal overlaps.
- Added a dedicated polygon output for uncovered areas inside the declared plan boundary.
- Added spatial indexes to seam matching, network snapping, and plan-fabric candidate searches.
- Added projected and common CRS guards to all new metric workflows.
- Rejected invalid dates, non-finite scale values, missing evidence categories, and checksum mismatches explicitly.
- Registered five new Processing algorithms and five dock actions, bringing the provider to 50 algorithms.
- Expanded the dual-runtime suite to 60 tests.

## 1.6.0 - 2026-09-14

- Added MPYY Article 22 threshold overlay screening for geology, hazard, hydrology, protected-area, agriculture, forest, drinking-water basin, coast, and infrastructure evidence.
- Dissolved overlapping threshold geometries so overlap areas are not double-counted.
- Kept threshold outputs as specialist-review signals rather than automated legal suitability decisions.
- Added Article 26 road plan-change checks for narrowing, lane reduction, development-area minimum widths, parcel access, dead ends, and traffic-impact evidence.
- Added Article 26 density and height change checks with the statutory facade-distance formula.
- Added explicit silhouette, infrastructure impact report, and social-infrastructure balance evidence checks.
- Added finite-number and missing-comparison guards for road, density, height, and monitoring inputs.
- Added Article 16 MSP action monitoring with baseline-to-target progress, weights, deadlines, responsibility, and portfolio totals.
- Added Articles 18-20 CDP revision-scope classification based on explicit statutory triggers.
- Made CDP spatial change measurement decision-code aware, including land-use changes within an unchanged plan boundary.
- Added Articles 23-24 pedestrian and bicycle network component and center-access auditing.
- Added projected-CRS and matching-CRS guards to every new metric spatial workflow.
- Registered six new Processing algorithms and six dock actions, bringing the provider to 45 algorithms.
- Expanded the dual-runtime suite to 56 tests.

## 1.5.0 - 2026-09-14

- Added separate MSP, CDP, NIP, and UIP content-audit Processing tools grounded in MPYY plan-level rules.
- Added persistent identifier, plan identifier, declared level, classification, geometry, and duplicate-ID checks.
- Added configured plan-scale checks for all four statutory plan levels.
- Added MSP strategic-role and thematic coverage diagnostics under Articles 14-17.
- Added CDP region-role diagnostics under Articles 18-20.
- Added NIP gross-density checks and prohibited UIP-detail leakage detection under Article 23.
- Added conditional UIP building-order, intensity, height, and setback checks under Article 24.
- Added spatial upper/lower plan coverage and explicit upper-group linkage auditing under Articles 6 and 35.
- Added MPYY Articles 21 and 31-35 submission dossier auditing with lifecycle deadline validation.
- Added atomic submission audit reports with deterministic SHA-256 content identities.
- Added a machine-readable 22 January 2026 supplemental display catalog with plan-level applicability.
- Embedded the filtered 2026 display catalog in every new planning GeoPackage and raised the schema to version 5.
- Added a ready-to-use plan submission manifest example.
- Added cemevi to worship amenity accounting and new electronic communications, energy storage, and disaster logistics classifications.
- Expanded the provider to 39 algorithms and the dual-runtime suite to 52 tests.

## 1.4.0 - 2026-09-14

- Added measured parcel-to-road boundary frontage and used it for legal frontage compliance when roads are supplied.
- Added parcel compactness and aspect-ratio quality metrics to engine and Processing outputs.
- Moved municipal profiles into a shipped, versioned JSON registry.
- Added strict schema, code, numeric range, roof slope, and boolean validation for profile registries.
- Added custom municipal profile file and profile-code selection to the by-law audit algorithm.
- Added read-only GeoPackage reconciliation previews with per-table impact summaries.
- Added atomic JSON preview reports with deterministic content SHA-256 identifiers.
- Added incoming-only table and schema mismatch diagnostics before merge execution.
- Added a dedicated reconciliation preview Processing algorithm and dock action.
- Added a map-linked QGIS legend to official parcel atlas layouts.
- Added visible CRS and approximate scale identity to official atlas documents.
- Replaced the atlas QR placeholder with an explicit verification URI and full document hash.
- Expanded the provider to 33 algorithms and extended dual-runtime integration coverage.

## 1.3.0 - 2026-09-14

- Added strict construction-time validation for subdivision constraint profiles.
- Added automatic repair and explicit diagnostics for invalid source parcel geometries.
- Improved frontage orientation by prioritizing measured road-edge contact before proximity.
- Made generated parcel ordering deterministic along the selected frontage axis.
- Added explicit source-to-output area-balance error reporting.
- Rejected non-finite 3D massing parameters and out-of-range roof slopes.
- Replaced unsafe concave-polygon roof centroids with guaranteed interior anchor points.
- Added configurable roof-rise caps with a visible cap warning.
- Added gross floor area and parcel floor-area-ratio metrics to 3D outputs.
- Distinguished invalid by-law values from genuinely missing input fields, including tri-state booleans.
- Excluded UUID and timestamp bookkeeping from reconciliation content hashes.
- Added GeoPackage schema mismatch diagnostics.
- Added manual, prefer-incoming, and prefer-newer conflict resolution strategies with an audit record.
- Added overwrite protection, atomic manifests, actual PDF hashes, batch rollback, cancellation, and progress reporting to atlas export.
- Expanded dual-runtime assertions for every new guard while retaining 49 independent test cases.

## 1.2.0 - 2026-09-14

- Added frontage, depth, area, and violation metrics to every generated subdivision parcel.
- Extended remnant amalgamation to handle every failed legal dimension, not only minimum area.
- Added Hmax clamping, internal floor slabs, and explicit floor-elevation output to procedural 3D massing.
- Added `INSUFFICIENT_DATA` by-law audit results so missing attributes cannot be reported as compliant.
- Escaped user-provided atlas attributes before HTML layout rendering.
- Added batch official-atlas PDF export with deterministic document numbers and a SHA-256 JSON manifest.
- Expanded the provider to 32 algorithms and the dual-runtime suite to 49 tests.

## 1.1.0 - 2026-09-14

- Added OMBB and road-oriented parcel subdivision with legal minimum checks and remnant amalgamation.
- Added official A3/A4 zoning atlas layouts with metric scale, north arrow, approval block, document hash, and PDF/image export.
- Added procedural PolygonZ building massing with setback envelopes, floor-height calculation, pitched roof surfaces, and volume metrics.
- Added configurable PAIY, Istanbul, Ankara, and Izmir by-law audit profiles.
- Added GeoPackage WAL preparation, optimistic revision fields, incoming-row merge, and persistent conflict records.
- Registered five Processing algorithms and five dock actions, bringing the provider to 31 algorithms.
- Expanded the integration suite to 37 tests and the complete plugin suite to 48 tests on both supported QGIS runtimes.

## 1.0.0 - 2026-09-14

- **Production Milestone — Master Specification Tam Uygulaması:**
  - `MASTER_AGENT_SPECIFICATION.md` kapsamında tanımlanan tüm 8 İş Paketi (Work Packages) tek seferde, sıfır hata ile hayata geçirildi.
- **Mekânsal İndeksleme ve $O(N \log M)$ Büyük Veri Performans Motoru (`core/synthesis.py`, `core/plan_diff.py`):**
  - `SynthesisEngine.batch_synthesize_parcels`: Parsel sentezi ve bina analiz döngüleri `QgsSpatialIndex` ile optimize edildi; 10.000+ nesneli projelerde işlem süresi $O(N \times M)$'den $O(N \log M)$ seviyesine çekildi.
  - `PlanRevisionDiffEngine`: Eşdeğer alan arama mekanizması (Madde 26) uzamsal arama kutusu ve `QgsSpatialIndex` ile hızlandırıldı.
- **İmar Parselasyonu ve Şuyulandırma Dağıtım Cetveli Motoru (`core/allocation_engine.py`):**
  - 3194 Sayılı İmar Kanunu 18. Madde ve *Arazi ve Arsa Düzenlemeleri Hakkında Yönetmelik* uyarınca kadastro parsellerinden DOP kesintisini düşerek imar adası ve parsellerine dağıtan resmi `AllocationEngine` geliştirildi.
  - Dağıtım matrisi, hisse oranları hesaplaması, `memory:imar_dagitim_tahsis_cetveli` bellek katmanı ve resmi encümen onaylı HTML/CSV dağıtım cetveli üretimi sağlandı.
- **PAİY Madde 5 ve 29 Emsal Harici Alan (%30 Kuralı) ve Net Taban Alanı Motoru (`core/capacity_engine.py`, `core/zoning_certificate.py`):**
  - Planlı Alanlar İmar Yönetmeliği Madde 5 uyarınca emsale dahil olmayan azami %30 alan hakkı (sığınak, otopark, tesisat katı, yangın holleri, ortak alanlar) ve toplam ruhsat inşaat alanı ($Emsale Esas + Emsal Harici$) modellemelere eklendi.
  - İmar Çapı ve İmar Kapasite belgelerinde bu alanlar ayrı kalemler halinde gösterildi.
- **7221 Sayılı Kanun Uyarınca "Yençok Serbest" Yasağı ve Hmax Denetimi (`core/qc_engine.py`):**
  - Kalite Kontrol Motoruna `check_free_height_violations` eklendi; planda `yencok`, `katadedi`, `P_KAT`, `HMAX` alanlarında mevzuata aykırı `SERBEST` değerleri tespit edilerek `HUKUKA_AYKIRI_SERBEST_YUKSEKLIK` kritik hatası raporlanır.
- **QGIS Dinamik Formlarında Koşullu Görünürlük (`core/form_designer.py`):**
  - `QgsAttributeEditorContainer.setVisibilityExpression`: Bitişik nizam seçildiğinde yan bahçe çekmesi alanının (`yanBahce`) formda otomatik gizlenmesi sağlandı.
- **Topolojik Mikro Yırtık ve Boşluk Onarımı (`core/geom_cleaner.py`):**
  - `heal_topological_boundaries`: Paylaşılan sınırları tarayıp belirlenen tolerans dahilindeki ($0.05\text{ m}$) ayrık düğümleri ortak doğruya yapıştıran topolojik onarım fonksiyonu eklendi.
  - `clean_planning_geometries` algoritmasına `AUTO_HEAL_GAPS` parametresi entegre edildi.
- **Kentsel Dönüşüm Hakediş ve Alan Fizibilite Motoru (`core/feasibility_engine.py`):**
  - 6306 sayılı Kanun kapsamında mevcut yapı inşaat alanı ile yeni imar planı kapasitesini karşılaştıran, müteahhit paylaşım oranını (%45), hak sahipleri inşaat alanını, bağımsız bölüm hakediş katsayısını ve alan fazlası/borçlanma bakiyesini hesaplayan `UrbanTransformationFeasibilityEngine` kuruldu.
- **Canlı İmar Çapı ve Çekme HUD Çizim Katmanı (`core/zoning_certificate.py`):**
  - Seçilen parsel için kırmızı kesikli çekme zarfı çizgileri ve metrik cephe ölçü etiketleri içeren dinamik CAD HUD katmanı (`memory:imar_capi_hud`) üretici eklendi.
- **İki Yeni QGIS Processing Algoritması (`provider.py`):**
  - `generate_land_readjustment_matrix`: İmar Kanunu Madde 18 Parselasyon Dağıtım ve Tahsis Cetveli.
  - `evaluate_transformation_feasibility`: Kentsel Dönüşüm Hakediş ve Alan Fizibilite Analizi.
  - Toplam algoritma sayısı 24'ten **26'ya** yükseltildi.
- **Test ve Doğrulama:**
  - Entegrasyon testleri 25'ten **32 teste** çıkarıldı (toplam 43 test). Hem QGIS 3.44 LTR hem de QGIS 4.2 üzerinde 0 hata ile çalışmaktadır.

## 0.9.0 - 2026-09-14

- **Resmi İmar Durumu Belgesi (İmar Çapı) Motoru (`core/zoning_certificate.py`):**
  - 3194 Sayılı İmar Kanunu, Planlı Alanlar İmar Yönetmeliği (PAİY) ve MPYY standartlarına tam uyumlu resmi İmar Durum Belgesi (İmar Çapı) motoru (`ZoningCertificateEngine`) geliştirildi.
  - Parsel kadastro bilgileri (Ada, Parsel, Mahalle, Pafta, Alan), imar planı fonksiyonu, yapılaşma hakları (Nizam, TAKS, KAKS/Emsal, Kat Adedi, Yençok, Çekme Mesafeleri), azami taban alanı ve inşaat alanı hesaplamaları, otopark ihtiyacı, jeolojik yerleşime uygunluk ve BÖHYY/ITRF96 parsel köşe koordinatları tablosu sentezlenir.
  - Basıma hazır, resmi belediye mühür/imza kutuları ve A4 baskı CSS stilleri içeren interaktif HTML ve Markdown formatında belge üretimi.
- **Sığınak Yönetmeliği İhtiyaç ve Yeterlilik Motoru (`core/shelter_engine.py`):**
  - 3194 sayılı Kanun ve *Sığınak Yönetmeliği* (Resmî Gazete 25.08.1990 / 20616) Madde 7 ve 8 uyarınca konut (12+ bağımsız bölüm veya $\ge 1500\text{ m}^2$), ticaret ($\ge 1000\text{ m}^2$), sanayi ($\ge 1000\text{ m}^2$), kamu ($\ge 800\text{ m}^2$) ve otel/konaklama yapılarında zorunlu serpiştirme sığınak alanlarını ($1.2\text{ m}^2/\text{kişi}$) hesaplayan motor geliştirildi.
  - Bölge nüfusu ($\ge 15.000$) eşiğine göre imar planında bağımsız 'Genel Sığınak' ayrılma zorunluluğunu denetler.
- **İki Yeni QGIS Processing Algoritması (`provider.py`):**
  - `generate_zoning_certificate`: Resmi İmar Durumu Belgesi (İmar Çapı) üretim algoritması.
  - `calculate_shelter_requirement`: Sığınak Yönetmeliği ihtiyaç ve yeterlilik analizi algoritması. Sağlayıcı algoritma sayısı 22'den **24'e** çıkarıldı.
- **Dock Arayüzü ve Test Paketi Genişletmesi (`dock.py`, `tests/test_integration_qgis.py`):**
  - "Analiz ve Sentez" sekmesine "Resmi İmar Durumu Belgesi (İmar Çapı) Üretici" ve "Sığınak Yönetmeliği İhtiyaç Analizi" arayüz grupları eklendi.
  - Entegrasyon testleri 25 teste genişletildi (toplam 36 test); QGIS 3.44 LTR ve QGIS 4.2 çift çalışma zamanında sıfır hata ile doğrulandı.

## 0.8.0 - 2026-09-14


- **Otopark Yönetmeliği İhtiyaç ve Yeterlilik Denge Motoru (`core/parking_engine.py`):**
  - Resmî Gazete 22.02.2018 / 30340 sayılı Otopark Yönetmeliği hükümlerine uygun olarak plan fonksiyonları ve emsal inşaat alanlarına göre zorunlu otopark ihtiyacı hesaplama motoru geliştirildi.
  - Konut, Ticaret, Karma, Sanayi, Turizm, Sağlık, Eğitim, Sosyal/Kültür fonksiyonları için yasal $m^2/\text{araç}$ oranları tanımlandı.
  - Planda ayrılan umumi ve bölge otoparkları ($25\text{ m}^2/\text{araç}$) ile karşılaştırılarak net otopark açığı/fazlası, karşılama oranı ve yeterlilik denetimi üretildi.
- **6306 Sayılı Kanun Kapsamında Çok Ölçütlü Afet Risk ve Kentsel Dönüşüm Önceliklendirme Motoru (`core/risk_engine.py`):**
  - 6306 sayılı Afet Riski Altındaki Alanların Dönüştürülmesi Hakkında Kanun uyarınca bina yapı stoku ve parsel afet zafiyetini sentezleyen motor (`UrbanTransformationRiskEngine`) geliştirildi.
  - Değerlendirme kriterleri: Bina yapım yılı / deprem yönetmeliği dönemi (1999 öncesi, 2000-2007, 2008-2018, 2018 sonrası TBDY), taşıyıcı sistem cinsi (`B_YAPI_CINSI`: kerpiç, ahşap, yığma, betonarme, çelik), hasar ve fiziki durum (`B_HASAR_DURUMU`: ağır, orta, az, hasarsız), kat adedi ve zemin jeolojik yerleşime uygunluk durumu (UA, ÖA, UOA).
  - Bileşik afet risk skoru ($0 - 100$) ve yasal dönüşüm öncelik sınıfları (`ACIL_DONUSUM`, `ONCELIKLI_DONUSUM`, `ORTA_RISK_ETAPLAMA`, `DUSUK_RISK_KONTROLLU`) üretildi.
- **İki Yeni QGIS Processing Algoritması (`provider.py`):**
  - `calculate_parking_requirement`: Otopark Yönetmeliği ihtiyaç ve yeterlilik analizi algoritması.
  - `prioritize_urban_transformation`: 6306 s. Kentsel dönüşüm ve afet risk önceliklendirme algoritması. Sağlayıcı algoritma sayısı 20'den **22'ye** yükseltildi.
- **Sütun İlişkileri (Relations) ve Türkçe Profesyonel Takma Adlar (Field Aliases) (`core/project_binding.py`, `core/form_designer.py`):**
  - `mpyy_uip_cizgi` ve `uipLineTable` arasında `uipLine_uipfonksiyon_uipLine_uip_fonksiyon` ilişkisi (`QgsRelation`) kuruldu.
  - Form ve öznitelik tablolarında teknik veritabanı adları yerine Türkçe anlaşılır, emojili ve hiyerarşik takma adlar (`setFieldAlias`) uygulandı.
- **Dock Arayüzü ve Test Paketi Genişletmesi (`dock.py`, `tests/test_integration_qgis.py`):**
  - "Analiz ve Sentez" sekmesine "Otopark Yönetmeliği İhtiyaç ve Yeterlilik Analizi" ile "6306 s. Kentsel Dönüşüm ve Afet Risk Önceliklendirmesi" kontrol panelleri eklendi.
  - Entegrasyon testleri 23 teste genişletildi (toplam 34 test); QGIS 3.44 LTR ve QGIS 4.2 çift çalışma zamanında sıfır hata ile doğrulandı.

## 0.7.0 - 2026-09-14


- **PAİY Madde 20 Köşe Pahı (Corner Chamfer) Kırım Motoru (`core/chamfer_engine.py`):**
  - Planlı Alanlar İmar Yönetmeliği Madde 20 uyarınca ada ve parsel köşe başı dönüşlerinde kavşak görüş emniyetini sağlamak amacıyla geometrik köşe pahı kırım motoru (`ChamferEngine`) geliştirildi.
  - Vektörel dış halka noktalarını tarayarak konveks açıları ($60^\circ - 120^\circ$) tespit eder; yasal standartlara uygun olarak $\le 10$m yollar için 3.0m, $>10$m yollar için 4.5m pah kırımı uygular ve terk/yol alanını ($m^2$) hesaplar.
- **MPYY Standart İmar Planı Baskı Paftası ve Meclis Onama Anteti Şablon Motoru (`core/layout_composer.py`):**
  - MPYY Madde 31 ve BÖHYY standartlarına uygun olarak A0, A1, A2, A3 ebatlarında tam donanımlı kartografik baskı paftası oluşturan `MPYYLayoutComposer` geliştirildi.
  - Ana harita çerçevesi, 250m/500m aralıklı BÖHYY koordinat gridi/artıları, projede aktif plan katmanlarına duyarlı dinamik lejant, kuzey oku, metrik ölçek çubuğu, başlık anteti ve Belediye Meclisi Onama ve Tasdik Kutusu (Karar Tarihi/No, Komisyon Raporu, Şehir Plancısı / Müellif Kaşe-İmza alanı) entegre edildi.
- **Akıllı Sekmeli Form Tasarımı, Değer Haritaları, Dinamik İfadeler ve Mevzuat Kısıtları (`core/form_designer.py`):**
  - `MPYYFormDesigner`: Düzensiz ve hantal öznitelik formları yerine 5 sekmeli, modern ve duyarlı drag-and-drop form arayüzü oluşturuldu:
    1. 🏛️ Plan Fonksiyonu ve Alan
    2. 🏗️ Yapılaşma ve Çekme (PAİY)
    3. 📜 Mülkiyet ve Kadastro
    4. ⚠️ Afet ve Jeolojik Önlemler
    5. ℹ️ Sistem ve Metaveriler
  - **Sütun İlişkileri ve Değer Haritaları:** `nizam` (Ayrık, Bitişik, İkiz, Blok, Serbest), `MULKIYET_TURU`, `dop_durumu`, `yerlesime_uygunluk` (UA, ÖA, UOA), `B_YAPI_CINSI`, `B_DURUM`, `B_HASAR_DURUMU` alanlarına resmi mevzuat açılır liste (ValueMap) bileşenleri bağlandı.
  - **Dinamik Sütun İfadeleri:** Geometri çizilirken veya güncellenirken `alan_m2` ($area), inşaat alanı ($area \times \text{kaks}$), taban alanı ($area \times \text{taks}$) ve ada-parsel metinleri otomatik hesaplanır (`applyOnUpdate=True`).
  - **Mevzuat Kısıtları (Constraints):** PAİY Madde 5 uyarınca $0 < \text{TAKS} \le 1.00$, $0 < \text{KAKS} \le 10.00$, $\text{Kat} \ge 1$ ve $\text{Çekme} \ge 0$ kural ihlallerinde kullanıcıya Türkçe açıklayıcı hata bildiren kısıtlar uygulandı.
- **Geometri Doğruluğu ve Topoloji Onarımı Zenginleştirmesi (`core/geom_cleaner.py`):**
  - `clean_planning_geometry`: Kendini kesen poligonlar, düğüm hataları, mikro-kıvrımlar ve mikron düzeyindeki saçak geometriler GEOS standardında temizlenip onarılır.
- **İki Yeni QGIS Processing Algoritması (`provider.py`):**
  - `apply_corner_chamfer`: Ada ve parsel katmanlarına PAİY Madde 20 köşe pahı uygulayan Processing algoritması.
  - `generate_print_layout`: A0-A3 ebatlarında standart MPYY imar planı pafta şablonu oluşturan Processing algoritması. Sağlayıcı algoritma sayısı 18'den **20'ye** çıkarıldı.
- **Dock Arayüzü ve Test Paketi Genişletmesi:**
  - Dock sekmesine "Akıllı Sekmeli Form, Değer Haritaları ve Kısıtları Uygula", "PAİY Madde 20 Köşe Pahı" ve "Baskı Paftası Şablonu Oluşturucu" panelleri entegre edildi.
  - Entegrasyon testleri 21 teste genişletildi (toplam 32 test); QGIS 3.44 LTR ve QGIS 4.2 üzerinde sıfır hata ile doğrulandı.

## 0.6.0 - 2026-09-14

- **PAİY Madde 15, 16 ve 22 Yapılaşabilirlik ve İfraz-Tevhit Denetim Motoru (`core/compliance_engine.py`):**
  - Planlı Alanlar İmar Yönetmeliği uyarınca 5 yapı nizamında (`AYRIK`, `BITISIK`, `IKIZ`, `BLOK`, `SERBEST`) asgari parsel cephesi, derinliği, yüzölçümü ve çekme mesafeleri ($A_{\text{zarf}}$) kontrolü.
  - Parselleri `YAPILASABILIR`, `TEVHID_ZORUNLU`, `IFRAZ_EDILEBILIR`, `CEKME_YETERSIZ` durumlarına sınıflandıran motor geliştirildi.
- **BÖHYY ve MPYY Standart İmar Planı Pafta İndeksi ve Grid Bölümleme Motoru (`core/pafta_index.py`):**
  - 1/1.000 ($500\text{m} \times 500\text{m}$), 1/2.000 ($1000\text{m} \times 1000\text{m}$) ve 1/5.000 ($2500\text{m} \times 2000\text{m}$) standart pafta indeks ızgarası üretimi.
  - Her pafta hücresi için koordinat sınırları, kapsanan plan alanı ($m^2$) ve nesne adedi hesaplama.
- **MPYY Madde 24 ve 31 Mevzuata Uygun İmar Planı Notları ve Lejant Hükümleri Sentez Motoru (`core/plan_notes.py`):**
  - Plan katmanındaki fonksiyonları dinamik olarak tarayan `PlanNotesEngine` geliştirildi.
  - Genel Hükümler (3194 s. Kanun, MPYY, PAİY, TBDY 2018, Otopark, Sığınak), Fonksiyonlara Özel Hükümler (Konut, Ticaret, Karma, Sanayi, Park/Yeşil, Eğitim, Sağlık, İbadet, Teknik Altyapı vb.), Jeolojik Afet Hükümleri ve Madde 18 Uygulama Hükümleri üretimi; Markdown, HTML ve Düz Metin çıktı formatları.
- **Kapsamlı MPYY Plan Açıklama Raporu ve Arazi Kullanımı Bilançosu Motoru (`core/report_exporter.py`):**
  - `PlanReportEngine` ve `generate_comprehensive_report` ile arazi kullanımı fonksiyon dağılımı, kamu donatısı oranı ($\%$), MPYY EK-2 donatı matrisi, imar kapasitesi ve nüfus projeksiyonu, Madde 18 DOP dengesi ve PAİY yapılaşabilirlik durumunu içeren basıma hazır HTML, Markdown ve CSV rapor ihracı.
- **Dört Yeni QGIS Processing Algoritması (`provider.py`):**
  - `validate_paiy_compliance`: PAİY parsel yapılaşabilirlik ve ifraz-tevhit denetim algoritması.
  - `generate_pafta_grid`: Standart pafta indeksi ve grid üretim algoritması.
  - `generate_plan_notes`: MPYY standartlarına uygun imar planı notları ve lejant hükümleri üretim algoritması.
  - `generate_comprehensive_report`: Kapsamlı MPYY plan açıklama raporu ve arazi bilançosu üretim algoritması. Sağlayıcı algoritma sayısı 14'ten 18'e çıkarıldı.
- **Dock Arayüzü ve Test Paketi Genişletmesi (`dock.py`, `tests/test_integration_qgis.py`):**
  - "Analiz ve Sentez" sekmesine PAİY Mevzuat Denetimi, Standart Pafta İndeksi, Plan Notları Üretimi ve Kapsamlı Plan Açıklama Raporu panelleri entegre edildi.
  - Entegrasyon testleri 18 teste genişletildi (toplam 29 test), QGIS 3.44 LTR ve QGIS 4.2 üzerinde sıfır hata ile doğrulandı.

## 0.5.5 - 2026-09-14

- **İmar Kanunu Madde 18 ve DOP (Düzenleme Ortaklık Payı) Hesaplama Motoru (`core/dop_engine.py`):**
  - 3194 Sayılı İmar Kanunu 18. Madde ve ilgili parselasyon yönetmeliği hükümleri doğrultusunda Düzenleme Ortaklık Payı (DOP) hesaplama ve tahsis cetveli motoru (`DOPEngine`) geliştirildi.
  - Kadastro parselleri toplam alanı ile kamusal terk alanları (yol, park, meydan, otopark, temel eğitim, sağlık tesisi, ibadet yeri vb.) üzerinden DOP Oranı ($\text{DOPO} = \sum \text{Terk} / \sum \text{Kadastro}$) hesaplanır.
  - Yasal azami sınır olan $\%45$ ($0.45$) tavan aşım denetimi uygulanır; $\%45$ üzerindeki oranlarda otomatik uyarı üretilerek aşan alan için KOP / Kamulaştırma zorunluluğu tespit edilir.
  - Parsel bazında kadastro alanı, DOP kesintisi ($m^2$) ve net imar hakedişi hesaplanarak `MPYY_Madde18_Tahsis_Cetveli` bellek katmanı ve öznitelik tablosu oluşturulur.
- **İmar Planı Yapılaşma Kapasitesi ve Öngörülen Nüfus Modellemesi (`core/capacity_engine.py`):**
  - İmar planlarındaki konut ve karma kullanım (Ticaret+Konut) adalarını analiz ederek TAKS ve KAKS (Emsal) katsayıları üzerinden brüt inşaat alanı ve konut inşaat alanını hesaplayan motor (`PlanCapacityEngine`) geliştirildi.
  - Ortalama konut büyüklüğü ($m^2$) ve TÜİK ortalama hanehalkı büyüklüğü ($3.2$ kişi/hane) parametreleriyle öngörülen bağımsız birim sayısı ve planlama kapasite nüfusu hesaplanır.
  - Hesaplanan kapasite nüfusu doğrudan MPYY EK-2 Asgari Donatı Standartları motoruyla eşleştirilerek planın kendi nüfusuna yeterli altyapıyı sağlayıp sağlamadığı otomatik denetlenir.
- **İki Yeni QGIS Processing Algoritması (`provider.py`):**
  - `calculate_dop_reallocation`: Kadastro ve terk katmanları veya manuel metrekare girişiyle Madde 18 DOP tahsis cetveli üreten Processing algoritması.
  - `estimate_plan_capacity`: İmar planı zonlama katmanından toplam inşaat alanı, konut sayısı ve öngörülen nüfusu hesaplayan Processing algoritması. Sağlayıcı algoritma sayısı 12'den 14'e yükseltildi.
- **Dock Arayüzü Genişletmesi (`dock.py`):**
  - "Analiz ve Sentez" sekmesine "İmar Kanunu Madde 18 ve DOP Hesabı" ve "İmar Kapasitesi ve Öngörülen Nüfus Modellemesi" form panelleri eklendi; sonuçlar tematik sembolojiyle haritaya eklendi.
- **Entegrasyon Testleri ve Çift Runtime Doğrulaması:**
  - `test_integration_qgis.py` 14 entegrasyon testine genişletildi; QGIS 3.44 LTR ve QGIS 4.2 üzerinde 25 testin tamamı sıfır hata ile başarıyla doğrulandı.

## 0.5.4 - 2026-09-14

- **MPYY EK-2 Asgari Sosyal ve Teknik Altyapı Standartları Mekânsal Analizi (`core/synthesis.py`):**
  - Mekânsal Planlar Yapım Yönetmeliği EK-2 tablosunda yer alan 8 ana donatı grubu (Açık ve Yeşil Alan, Eğitim Tesisleri, Sağlık Tesisleri, Sosyal ve Kültürel Tesisler, İbadet Alanları, Teknik Altyapı, Spor Alanları, Kamu ve Belediye Hizmet Alanları) için kişi başı asgari standartlar tam matris olarak modellendi.
  - `extract_amenities_from_features`: Mekânsal plan katmanlarındaki poligon geometrileri ve öznitelik alanlarını (`uipfonksiyon`, `detay_katalogu`, `fonksiyon_adi`, `P_FONK`, `B_FONK`) dinamik olarak tarayarak her donatı grubu için fiili metrekare toplamlarını otomatik hesaplayan motor geliştirildi.
  - Standart, gerekli alan ($m^2$), mevcut alan ($m^2$, ha), kişi başına düşen fiili alan ($m^2$/kişi), açık/fazlalık ve karşılama oranı (\%) metrikleri ile donatı açığı analizi tam otomatik hale getirildi.
- **MPYY Madde 26 İmar Planı Değişikliği ve Eşdeğer Alan Analiz Motoru (`core/plan_diff.py`):**
  - Mevzuat kuralı: *"İmar planında yer alan bir sosyal ve teknik altyapı alanının kaldırılabilmesi veya küçültülebilmesi ancak bu tesisin hizmet edeceği etki alanı içinde eşdeğer bir alanın ayrılması suretiyle yapılabilir."*
  - `PlanRevisionDiffEngine`: Yürürlükteki cari imar planı ile öneri plan değişikliği (tadilat) veya ilave plan katmanlarını mekânsal olarak kesiştirerek çift yönlü küme farkı analizi ($A \cap B$, $A \setminus B$, $B \setminus A$) uygulayan motor geliştirildi.
  - Değişim parçaları `KORUNAN`, `FONKSIYON_DEGISIMI`, `DONATI_KALDIRILDI` ve `YENI_DONATI_EKLENDI` olarak hassas biçimde sınıflandırılır.
  - `QgsSpatialIndex` ile optimize edilmiş yürüme/etki mesafesi (varsayılan $500m$) yarıçapında eşdeğer donatı ikamesi denetimi gerçekleştirilir; $\%95$ alan eşiği altında kalan kaldırmalar `YETERSİZ` (Mevzuata Aykırı) olarak işaretlenir ve detaylı raporlanır.
- **İki Yeni QGIS Processing Algoritması (`provider.py`):**
  - `analyze_amenity_standards`: `planx_mpyy_studio:analyze_amenity_standards` ile mekânsal plan katmanından otomatik donatı taraması ve geometrisiz öznitelik tablosu (`MPYY_EK2_Donati_Dengesi`) üretimi.
  - `evaluate_plan_revision`: `planx_mpyy_studio:evaluate_plan_revision` ile iki plan kademesi arasında mekânsal fark poligon katmanı üretimi ve Madde 26 uygunluk alanlarının otomatik türetilmesi. Sağlayıcı algoritma sayısı 10'dan 12'ye yükseltildi.
- **Dock Arayüzü Entegrasyonu (`dock.py`):**
  - "Analiz ve Sentez" sekmesine interaktif plan katmanı seçici, fonksiyon alanı belirteci ve tek tıkla EK-2 donatı tablosu üretme butonu eklendi.
  - İmar planı değişikliği karşılaştırma paneli (Cari plan, Öneri planı, Yürüme yarıçapı) entegre edildi; sonuçlar harita tuvalinde renk kodlu tematik semboloji (`QgsCategorizedSymbolRenderer`) ile otomatik görselleştirildi.
- **Entegrasyon Testleri ve Çift Runtime Doğrulaması:**
  - `test_integration_qgis.py` test paketi 12 birim/entegrasyon testine genişletildi; 23 testin tamamı QGIS 3.44 LTR ve QGIS 4.2 üzerinde sıfır hata ile doğrulandı.

## 0.5.3 - 2026-09-13

- **Crosswalk Eşleme Güvencesi ve Belirsizlik Denetimi (`core/crosswalk.py`):**
  - Alt kelime çakışmalarını önlemek amacıyla tam eşleşme önceliği ve belirteç sınırı (`token-boundary`) eşlemesi uygulandı; tekil kelimelerin (`PARK`, `KONUT`) birleşik veya bağımsız terimleri (`OTOPARK`, `TOPLU_KONUT`) yanlış sınıflandırması engellendi.
  - Karmaşık veya çoklu karşılığı olan fonksiyonların (`KONUT_TICARET`, `TICARET_TURIZM`) otomatik karar olarak atanması engellenerek mevzuat gereği `ONAY_BEKLIYOR` statüsünde şehir plancısı onayına sunulması sağlandı.
  - `"OTEL ALANI "` sondaki gereksiz boşluk giderildi, kullanılmayan `QVariant` modülü kaldırıldı.
- **QGIS Eylemleri ve QField Paketleyici Düzeltmeleri (`core/actions.py`, `core/qfield_packager.py`):**
  - `actions.py` içinde tırnaksız `[% @layer_id %]` ifadesi kaldırılarak Python eylem çalıştırıcısındaki sözdizimi/çalışma zamanı hatası giderildi; panoya kopyalama dizesi temizlendi.
  - `qfield_packager.py` katman biçem aktarımında GeoPackage dosya URI'sini doğrudan `loadNamedStyle`'a vermek yerine `QDomDocument` ile `importNamedStyle` ve varsayılan biçem yükleme geri dönüşüyle güçlendirildi.
- **QML Biçem ve Form İyileştirmeleri (`forms/`):**
  - `06_uip-alanlar.qml` dosyasındaki sabit harici veritabanı yolu kaldırıldı; `core/project_binding.py` ve `core/db_factory.py` içinde dinamik `ReferencedLayerDataSource` yolu enjekte edilerek SQL hata günlükleri sıfırlandı.
  - `01_uip-notasyonlar.qml` dosyasındaki sabit SVG sembolü yerine dinamik veri-tanımlı yol genişliği `FontMarker` yerleştirildi.
- **QC ve Sentez Motoru Performans ve Hata Optimizasyonları (`core/qc_engine.py`, `core/synthesis.py`, `provider.py`):**
  - `QualityControlEngine`: Aday arama döngülerindeki O(N) `next(...)` taramaları O(1) sözlük eşlemesine dönüştürüldü; geometri birleştirmelerinde ardışık `combine()` yerine `QgsGeometry.unaryUnion()` kullanıldı.
  - `SynthesisEngine`: Fonksiyon adı alanları için çoklu alan fallbacks (`uipfonksiyon`, `P_FONK`, `B_FONK`, `fonksiyon_kodu`, `catalog_id`) eklendi (`KeyError` önlendi); kat adedi dönüşümünde güvenli tamsayı ayrıştırma ve genişletilmiş hasar kodu desteği getirildi.
  - `provider.py`: `IngestVectorDatasetAlgorithm` içinde `tgt_names` kümesi döngü dışına taşındı, kaynak katman için null denetimi eklendi.
- **Qt6 / QGIS 4 ve GDAL 4.0 Tam Uyumluluğu:**
  - `provider.py` ve `dock.py` içinde kullanım dışı kalan `QVariant.*` tipleri `QMetaType.Type.*` (`QString`, `Double`, `Int`) ile değiştirildi; yerel `hub_qt6_scan.py` taramasında sıfır hata ile tam uyumluluk sağlandı.
  - `core/db_factory.py` içinde `gdal.UseExceptions()` etkinleştirilerek GDAL 4.0 uyarısı giderildi.
- **Test ve Temizlik:**
  - Test sınıflarında `tearDown` sırasında geçici dizinlerin açık temizliği (`self.tmp.cleanup()`) sağlandı ve kullanılmayan importlar ayıklandı.

## 0.5.2 - 2026-09-13

- **Tam QML Form ve Veri Tabanı Sütun Eşitlemesi:** Şemadaki tüm sütunlar (`SAHA_PARSEL_FIELDS`, `SAHA_YAPI_FIELDS`, `SAHA_YOL_FIELDS`, `COMMON_FIELDS`, `UIP_AREA_FIELDS`, `UIP_LINE_FIELDS`, `UIP_NOTATION_FIELDS`) QML formları ile birebir (yüzde 100) hizalandı. Eksik tüm `fieldConfiguration`, `aliases`, `defaults`, `constraints` ve sekmeli `attributeEditorForm` alanları tamamlandı; arayüz ve form açıkta kalan sütun sayısı sıfırlandı.
- **Yeni Alan ve Yapı Sörveyi Kod Tabloları:** `saha_nizam_kodlari` (Ayrık, Bitişik, Blok, Serbest, İkiz) ve `saha_parsel_durum_kodlari` (Dolu, Boş, İnşaat, Metruk, Tescil Harici) bağımsız GeoPackage öznitelik tabloları olarak eklendi; `saha_yapi_cins_kodlari` 8 sınıfa genişletildi (Kâgir/Taş Yapı ve Geçici/Baraka eklendi).
- **Otomatik Katalog Katmanı Yükleme (`core/project_binding.py`):** Arazi Kullanımı çalışma alanı açıldığında 58 sınıflı `saha_kullanim_kodlari` sözlüğü doğrudan katman ağacına eklenir. Planlama çalışma alanlarında ise seçili kademeye göre `mpyy_msp_katalogu`, `mpyy_cdp_katalogu`, `mpyy_nip_katalogu` veya `uipPolygonTable`/`uipLineTable` ilgili kademe grubunda otomatik açılır.
- **UİP Mevzuat ve Plan Üstverisi Form Sekmesi:** `mpyy_uip_alan`, `mpyy_uip_cizgi` ve `mpyy_uip_notasyon` QML formlarına "Mevzuat ve Plan Üstverisi" sekmesi entegre edilerek `plan_id`, `plan_kademesi`, `catalog_id`, hiyerarşik grup/fonksiyon kodları ve denetim alanları tam erişilebilir hale getirildi.
- **ÇDP Çizgi ve Odak Koridoru Semboloji Eşleme:** `CDPStylerEngine` çizgi ve nokta katmanlarında `koridor_turu`, `odak_adi` ve `fonksiyon_adi` alanlarını otomatik algılayacak şekilde güçlendirildi.

## 0.5.1 - 2026-09-13

- **Tam Katalog Semboloji ve Sütun Kapsama Güvencesi:** Sistemdeki tüm detay katalogları (MSP, ÇDP, NİP, UİP, Arazi Kullanımı) ve şema sütunları denetlendi, eksik sembolojiler tamamlandı ve sıfır gri düşüş (`#D5D9DC` / `#808080`) garanti altına alındı.
- **MPYY Styler Revizyonu (`core/mpyy_styler.py`):** 241 poligon ve 33 çizgi olmak üzere 274 katalog satırının tamamı 23 üst konu grubu ve fonksiyonel paletler üzerinden çok aşamalı (primary EPLAN -> cross-plan EPLAN -> MPYY Function Palettes -> MPYY Group Palettes) çözümlemeye kavuşturuldu. Çözülemeyen/griye düşen satır sayısı 127'den 0'a indirildi.
- **NİP Sembolojisi ve Ulaşım Hiyerarşisi (`core/nip_styler.py`):** 170 NİP kuralının tamamı çözümlendi; 1. ve 2. derece ana arter ulaşım ağları, ada kenarı, mania ve kıyı çizgileri eklendi. Konut alanları mevzuata uygun sıcak sarı (`#FDD835`) tona kavuşturuldu.
- **Görsel Doğrulama ve Harita Sahneleri (`10_render_nip_symbology.png`):** NİP sahnesi konut, ticaret, donatı ve yeşil alan zonları, içinden geçen arter ulaşım aksları ve tam eşleşen MNIP font glifleri ile revize edilerek yeniden üretildi.
- **Çift Stil Mimarisi Güvencesi:** Yusuf Eminoğlu'nun özgün yerel stilleri (1/1.000 UİP XML ve 58 sınıflı Saha Sörveyi QML) ile Bakanlık resmî MPYY/E-Plan stilleri (MSP, ÇDP, NİP, UİP) arasındaki kademe ve profil sınırları teyit edildi.

## 0.5.0 - 2026-09-13

- Arazi Kullanımı Sözlüğü 58 sınıfa çıkarıldı: Lojman, Gecekondu/İmar Dışı Yerleşim, Kentsel Dönüşüm, Banka/Finans, Pazar Yeri, Enerji Üretim Tesisi, Belediye Hizmet Alanı (BHA), Kreş/Gündüz Bakımevi, Botanik/Hayvanat Bahçesi.
- Mobil Saha Paketi (QField) Motoru ve Algoritması: `package_for_qfield` ile tek tıkla QField'a hazır proje klasörü, `fotograflar/` dizini, otomatik yakalama kuralları ve OSM altlığı ile tam mobil saha paketi ihracı.
- CAD/GIS Geometri Onarma Motoru ve Algoritması: `clean_planning_geometries` ile GEOS geçerlilik onarımı, mikro-sliver eliminasyonu, köşe kenetleme ve metrik alan/uzunluk güncellemesi.
- Plan Açıklama Raporu Bilanço İhracı Motoru ve Algoritması: `export_planning_report` ile GeoPackage içindeki tüm bilanço SQL görünümlerini basıma hazır interaktif HTML raporuna ve bağımsız CSV dosyalarına dönüştürme.
- Dock arayüzüne doğrudan 1-tıkla erişim butonları entegre edildi.
- 21/21 QGIS birim ve entegrasyon testleri her iki runtime üzerinde (3.44 LTR ve 4.2) tam uyumlulukla doğrulandı.

## 0.4.0 - 2026-09-13

- Genişletilmiş Mevcut Arazi Kullanımı Sözlüğü: 49 kapsamlı planlama ve saha sörveyi sınıfı (Ulaşım/Terminal/İstasyon, Sosyal/Yurt/Bakımevi, Adliye/Cezaevi, Kırsal/Mera/Otlak, Sulak Alan/Sazlık, Kıyı/Kumsal).
- Arazi Kullanımı GeoPackage sözlük tabloları: `saha_cati_kodlari`, `saha_isitma_kodlari`, `saha_hasar_kodlari`.
- GeoPackage içi otomatik SQL raporlama ve bilanço görünümleri: `v_saha_parsel_kullanim_ozet`, `v_saha_yapi_kat_ve_durum_ozet`, `v_saha_mahalle_bilancosu`, `v_saha_yol_envanteri`, `v_uip_fonksiyon_bilancosu`, `v_uip_yol_kademelenmesi`, `v_nip_yogunluk_ve_alan_dagilimi`.
- Otomatik SQLite tetikleyicileri (Triggers): Saha anketinde yeni nesnelerde RFC-4122 UUID v4 (`global_id`) ve yerel zaman damgası (`tarih`) otomatik oluşturulur.
- Yeni Processing Algoritması: `ingest_vector_dataset` (Harici CAD/GIS katmanlarını otomatik öznitelik eşleme ve metrik hesaplama ile MPYY tablolarına aktarır).
- Çift stil profili ayrımı: "Özgün Yerel Stiller (Yusuf Eminoğlu)" (1/1.000 UİP + 49 sınıflı Arazi Kullanımı) ve "MPYY / E-Plan (Resmî Mevzuat)".

## 0.3.3 - 2026-09-12

- Made Processing provider registration safe across QGIS plugin reloads.
- A stale provider no longer prevents the dock from loading.

## 0.3.2 - 2026-09-12

- Fixed QGIS 3.44 notation label placement enum handling.
- Fixed Arazi Kullanımı workspace creation indices for tables without `catalog_id`.

## 0.3.1 - 2026-09-12

- Added the EK-1e MSP detail catalogue (28 verified classes from pages 1-11).
- Added native MSP renderer for PDF RGB, hatch, boundary and geometry rules.
- Kept GeoServer SLD as an optional source format, not a runtime dependency.

## 0.3.0 - 2026-09-12

- Made MPYY/e-Plan the functional default style provider.
- Kept MPYY native XML as an explicit alternative.
- Added the complete 241 polygon and 33 line source catalogs.
- Replaced the mixed legacy schema with four ordered MPYY levels (MSP → ÇDP → NİP → UİP).
- Added canonical UİP conditional attribute forms and native SLD notation rendering.
- Added an independent Arazi Kullanımı workspace and Processing algorithm.
- Removed `meri_1000_alan` and all parallel legacy UİP layers from generated databases.

## [0.1.0] - 2026-09-11

### Added
- Portable UIP GeoPackage creation with explicit CRS and dataset identity.
- Code-mapped native QGIS symbology with renderer restoration.
- Dock workflow and Processing workspace creation.

This is a local experimental build, not a published or certified planning product.
