# PlanX MPYY Studio

## Türkçe çalışma alanı — 1.0.0

MPYY planlama iş akışları için QGIS eklentisi. Taşınabilir GeoPackage çalışma alanları, MPYY/e-Plan ve yerel MPYY stilleri, plan denetimleri, saha araştırması ve rapor üretimini bir araya getirir.

Eklentiye ait arayüz **Türkçedir**: araç adları, yardım, parametreler, seçenekler, bildirimler, form sekmeleri, alan etiketleri, kısıt açıklamaları, lejantlar, harita bilgi kartları ve üretilen raporlar. Mevzuat kodları, özgün kataloglar, saklanan değerler, alan adları ve kullanıcının verdiği adlar korunur. QGIS ve MPYY gibi özel adlar değişmez. QGIS'in kendi iletişim kutularının dili QGIS dil ayarına bağlıdır.

Panelin üç sekmesi vardır:

- **Başlangıç:** çalışma alanı oluşturma, veri aktarma, biçimlendirme, karar inceleme ve teslim adımları.
- **Araçlar:** 86 işlem algoritması ve üç panel aracı; kategori, arama, kaydedilen kısayollar ve son açılanlar.
- **İşlem Kaydı:** yapılandırma açılışları ve sonuçlar; tam ayrıntıları kopyalayabilirsiniz.

Araç seçildiğinde amacı, gerekli girdileri ve beklenen sonucu görürsünüz. **Aracı aç** yapılandırmayı açar; hesaplamayı İşlem Araç Kutusunda başlatırsınız. Hafif işler için **Kısa formu kullan** sonuçları mevcut projeye uygular. Geri dönüldüğünde girdiler korunur. Hedef katman seçimi başlangıçta boştur.

**Ctrl+K** aramaya geçer, ok tuşları araç seçer, **Enter** veya **Alt+O** aracı açar. **Tab** kontroller arasında ilerler. Arama Türkçe karakterlere duyarlı değildir: `erişilebilirlik` ve `erisilebilirlik` aynı eşleşmeleri verir. Algoritma kimlikleriyle de arayabilirsiniz.

Panel QGIS yazı tipi ve renk paletini izler. Metinler dar panellerde satıra bölünür; formlar dikey kayar. Uzun sonuçlar Kayıt sekmesinde saklanır.

## Çalışma alanları ve stiller

Plan GeoPackage dosyası MSP → ÇDP → NİP → UİP kademelerini içerir. Her kademenin alan, çizgi ve gösterim katmanları vardır. UİP alan formunda MPYY kimliği, fonksiyon kataloğu, yapı nizamı, TAKS, KAKS/emsal, yükseklik ve çekme mesafeleri bulunur. Koşullu öznitelik formları Türkçedir.

**Yerel UİP (MpyyUipDb çizim şablonu)** ayrı bir çalışma alanı türüdür: `uip-alanlar`, `uip_cizgiler`, `uip-notasyonlar`, `yapi_yaklasma`, `uipPolygonTable` ve `uipLineTable` tabloları kaynak şablonla aynı alan ve türlerle oluşturulur. Semboloji, koşullu sekmeler, açılır listeler ve varsayılan değerler şablonun QGIS projesinden `tools/extract_local_uip_template.py` ile alınır ve `forms/yerel_uip` altında saklanır. UİP fonksiyonu zincirli listedir: önce üst konu grubu, sonra o gruptaki fonksiyon seçilir. Nizam `A`, `B`, `BL` olarak saklanır. Aynı form MPYY çalışma alanındaki `mpyy_uip_*` katmanlarında da kullanılır; genel form düzenleyici yazılmış formu olan katmanlara dokunmaz.

**MPYY 1.1.7 çalışma alanı (UİP / NİP / ÇDP)** Bakanlığın XSD şemasından birebir üretilir: tablo ve alan adları GML öğe adlarıdır, kod listeleri açılır listedir. Gösterim Bakanlığın e-Plan SLD setinden gelir; sit ve koruma sınırlarına detay kataloğundaki kısaltmalar (A1, KS, YKK…) yazılır. CAD tabakaları bu çalışma alanına aktarılabilir, kademe dönüştürülebilir (UİP → NİP → ÇDP) ve şema uygunluğu denetlenebilir. 1.1.6'dan farklar: `docs/MPYY_1.1.6_1.1.7_FARKLAR.md`.

**MPYY GML içe aktarma** (`import_mpyy_gml`) e-Plan GML dosyasını şemasına göre okur. Güncel şemaların yanında Bakanlık paketindeki M serisi (MUİP, MNİP, MÇDP 1/25.000 ve 1/100.000, sürüm 1.1.6) da desteklenir; bu şemalar eski yönetmelik gösterimlerini ve `YeniKod` alanını taşır. Şema `xsi:schemaLocation` alanından, yoksa öğe adlarından belirlenir. Şemada olmayan öğe ve öznitelikler, kod listesi dışı değerler ve okunamayan geometriler tahmin edilmez, raporlanır. MUİP ve MNİP katmanları Bakanlık SLD gösterimiyle açılır; MÇDP için SLD setinde stil yoktur.

Arazi kullanımı ayrı bir çalışma alanıdır. TUCBS arazi katmanları ile parsel, yapı ve yol araştırma tabloları plan kararlarından ayrı tutulur. Her iki çalışma alanını aynı QGIS projesine yükleyebilirsiniz.

MPYY/e-Plan varsayılan stil motorudur. Yerel MPYY stilleri seçilebilir alternatiftir. Yerel UİP ve saha stilleri kullanılabilir; NİP taslak durumundadır, ÇDP resmî yedek stili kullanır. Uygulamadan önce seçilen profili inceleyin. MSP sembolleri EK-1e kataloğundan yerel QGIS sembollerine dönüştürülür; GeoServer gerektirmez.

`meri_1000_alan` ve eski paralel UİP katmanları güncel şemada bulunmaz. Özgün QML dosyaları izlenebilirlik için korunur; temel katmanlar programatik formlarla oluşturulur. Türkçe gösterim `core/localization.py` ve `resources/turkish_labels.tsv` dosyalarındadır. Kayıtlı projelerde yerel QGIS ifadeleri kullanılır; özel Python ifade kaydı gerekmez.

## Araç kapsamı

- Çalışma alanı oluşturma, veri aktarma, geometri onarma ve sürüm birleştirme.
- Yapılaşma zarfı, parsel ön denetimi, bölünme, köşe pahı, DOP ve tahsis matrisi.
- Nüfus ve yapı kapasitesi, donatı, otopark, sığınak ve dönüşüm fizibilitesi.
- Yapı morfolojisi, Spacematrix yoğunluğu, yol ağı morfolojisi ve plan göstergesi karşılaştırması.
- Yürüme, bisiklet ve toplu taşıma erişimi; senaryo karşılaştırması ve nüfus ağırlıklı erişim eşitliği.
- Plan kademeleri, topoloji, resmî gösterimler, karma kullanım ve plan değişikliği denetimleri.
- Plan dosyası bütünlüğü, kurum görüşleri, dayanak güncelliği, katılım, askı, itiraz, onay ve sayısal teslim kayıtları.
- Açıklama raporu, plan notları, imar durumu belgesi, pafta indeksi, atlas, baskı düzeni ve mobil saha paketi.
- İdare kaynaklı şema sözlüğü içe aktarma, GeoPackage şema denetimi ve profil kimliği doğrulama.

Tam liste ve girdi/çıktı açıklamaları **Araçlar** sekmesindedir. İşlem sağlayıcısı kimliği `planx_mpyy_studio` olarak korunur.

## Erişilebilirlik ve şema profilleri

Başlangıç ve önerilen ağ/tesis grupları aynı talep katmanıyla karşılaştırılır. Çıktıda iki erişim durumu, tesis kimlikleri, ulaşım türleri, yakalama mesafeleri, süreler ve önerilen eksi başlangıç süre farkı saklanır. Negatif fark daha hızlı yolculuktur. Güzergâh kazanımı/kaybı ve yakalama belirsizliği ayrı sınıflardır; eksik güzergâha uydurma süre atanmaz.

Girdiler aynı, metre birimli projeksiyonlu koordinat sistemini kullanmalıdır. Ağ kesişimleri ortak düğümlerle temsil edilmelidir. Yakalama ağ kenarına değil düğümlerine yapılır. Süre eşiği, hızlar ve aktarma cezası kullanıcı girdileridir.

İdarenin UTF-8 CSV sözlüğü açık JSON sütun eşlemesiyle şema profiline dönüştürülebilir. Tablo, alan ve SQLite türü zorunludur. Boş değer, birincil anahtar, geometri ve koordinat sistemi sütunları isteğe bağlıdır. Belirsiz başlıklar, yinelenen alanlar ve çelişkili geometri tanımları reddedilir. Örnekler `resources/schema_dictionary.example.csv` ve `resources/schema_import_mapping.example.json` dosyalarındadır; gerçek idarenin verisiyle değiştirin.

Kimlik denetimi gömülü SHA-256 özetini, isteğe bağlı kaynak sözlüğünü ve ayrı saklanan bağımsız özeti karşılaştırır. İçerik tutarlılığı kurumun özgünlüğünü tek başına kanıtlamaz; `issuer_authenticity: NOT_VERIFIED` korunur. Şema denetimi GeoPackage dosyasını salt okunur açar.

## Kurulum ve doğrulama

QGIS 3.44 LTR ve QGIS 4.2 hedeflenir. Yerel ZIP paketini QGIS eklenti yöneticisindeki ZIP'ten kurulum seçeneğiyle yükleyin. Geliştirme için `QGIS_PLUGINPATH` değerini eklentilerin kök klasörüne ayarlayıp QGIS'i yeniden başlatabilirsiniz.

Kayıtlı bütün testler ve taramalar:

```powershell
py -3 packaging/pf.py verify planx_mpyy_studio
```

[GUI mimarisi](docs/GUI_ARCHITECTURE.md) · [Değişiklik kaydı](CHANGELOG.md)

**Yazar:** Yusuf Eminoğlu · **Lisans:** GPL-2.0-or-later
