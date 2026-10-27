# Changelog

## [1.0.1] - 2026-10-27

- Hub listing text rewritten; author Geophilo; university affiliation removed; documentation links use the standard geophilo.com pages (manual.html, guide/); manual HTML no longer ships in the plugin package.

## [1.0.0] - 2026-10-16

İlk kamusal sürüm. Eklenti bugüne kadar hiç yayınlanmadı; sürüm numarası bu
yayınla 1.0.0 olarak başlıyor. Daha önce yalnızca yerelde kullanılan 2.x
numaraları geçersizdir ve bu dosyada tutulmaz.

### Çalışma alanları

- **MPYY 1.1.7 şemaları (UİP, NİP, ÇDP).** Taşınabilir GeoPackage çalışma
  alanı; gerçek nesne tipi tabloları, kod listelerine bağlı açılır listeler ve
  Bakanlık gösterimi.
- **Yerel UİP ve Yerel NİP çalışma alanları.** Kullanıcının kendi çizim
  şablonundan (MpyyUipDb, MpyyNipDB 1/5.000) dondurulan katmanlar, stiller ve
  formlar.
- **Arazi kullanımı ve saha anketi çalışma alanı.** Saha kararlarını plan
  kararlarından ayrı saklar.
- **Kademe dönüşümü.** UİP → NİP/ÇDP, NİP → ÇDP. Karşılığı olmayan ya da
  planlamacının doldurması gereken kodlar sessizce düşmez, raporlanır.
- **e-Plan MPYY GML içe aktarma.** Şema otomatik belirlenir; eski yönetmelik
  gösterimlerini taşıyan M serisi (MUİP, MNİP, MÇDP) dahildir.
- **CAD/NCZ aktarımı ve şema denetimi.** Tabaka adları MPYY nesne tiplerine ve
  kodlarına çevrilir; eşleşmeyen tabakalar ile şema aykırılıkları raporlanır.
- **Mekânsal Strateji Planı (MSP) çalışma alanı.** MPYY 1.1.7 XSD seti UİP, NİP ve
  ÇDP taşır; MSP'nin kendi şeması yoktur, bu yüzden çalışma alanı Bakanlığın
  Ek-1e MSP kataloğundan üretilir. Katalogun yedi strateji grubu ile üç geometri
  türünün kesişiminden 11 çizim katmanı ve 32 kod yuvası çıkar; her katman açılır
  listede yalnızca kendi grubunun ve kendi geometrisinin kodlarını sunar. Yanında
  iki eşlikçi tablo gelir: çalışma alanının çizildiği kataloğun kendisi
  (`msp_katalogu`, 28 satır) ve Madde 16 eylem planı (`msp_eylem_plani`). Katmanlar
  MSP kademesinin istediği alanları taşır (`strateji_bolgesi`, `oncelik_durumu`) ve
  MSP-002'nin veriye bağlı gösterimi için `yerlesme_kademesi` ile
  `yerlesme_yogunlugu` alanlarını da açarlar; parsel düzeyinde uygulama alanı
  (TAKS, KAKS, nizam, çekme mesafesi) hiç
  oluşturulmaz, çünkü bir MSP parsel planı değildir ve kademe denetimi bu alanları
  UİP üstünde reddeder.

### Gösterim

- Bakanlığın Ek-1e Mekânsal Planlar Detay Katalogları'na göre semboloji: çizgi
  desenleri, çizgi üzerinde tekrarlayan yazı, işaret zincirleri, dik çentik
  tarakları ve iki katmanlı ray+bağ çizimleri.
- Ek-1e pafta ölçüleri kademenin nominal ölçeğinde harita metresine çevrilir
  (`mm × ölçek / 1000`); UİP, NİP, ÇDP ve M serisinde çizgi, işaret, kesik,
  aralık, ofset, tarama ve tekrarlayan yazılar aynı birim sözleşmesini kullanır.
- Ek-1e detay kataloğunun alan-çizgi eşlemesi (UİP, NİP ve ÇDP için 592 kayıt:
  sembol adı, detay sınıfı ve alt sınıfı, plan kademesi, geometri, SLD kuralı ve
  kaynak sayfa) çalışma alanına ayrı bir `mpyy_detay_katalogu` katmanı olarak
  yazılır; sınıflandırma kural açıklamalarına ve katman üst verisine işlenir.
  Şema alanlarına ve kod listelerine karışmaz.
- Ek-1e'nin aynı etiketi birden çok yazımla bastığı on dört detay sınıfı/alt sınıfı
  etiketi tek yazıma indirilir; aralarında onunda noktalı İ düşer, ikisi bitişik
  yazılmış sözcüğü ayırır, birinde `ALAN KULLANIMLARI` içinden bir L, birinde çoğul
  eki, birinde sondaki `-I`, birinde de Ek-1e'nin bastığı virgül düşer
  (`DENIZYOLLARI` / `DENİZYOLLARI`, `ALAN KULANIMLARI` / `ALAN KULLANIMLARI`,
  `DEMIRYOLLARI` / `DEMİRYOLLARI`). Hangi yazımın kaldığı Bakanlığın makine okunur
  kod listesine göre belirlenir; etiket o listede bir üst grup adı olarak
  geçmiyorsa katalogun kendi yaygın yazımı korunur. Böylece bir etiket katman üst
  verisinde iki ayrı sınıf gibi görünmez ve kural açıklamaları aynı sınıfı
  gösterir. Derleyici, tekilleştirmeden sonra hâlâ iki yazım kalmışsa hata vererek
  durur.
- Bunlardan üçü yazım değil adlandırma farkıdır: aynı sınıf Ek-1e'de hem çoğul
  (`SOSYAL VE KÜLTÜREL TESIS ALANLARI`; bitişik yazımı `SOSYALVE …`) hem tekil
  (`SOSYAL VE KÜLTÜREL TESİS ALANI`) adla geçer, `SAĞLIK TESISLERI ALANLARI` ve
  `EĞITIM TESISLERI ALANLARI` de kod listesinde tekil grup adıyla yer alır. Üçü de
  kod listesinin adını taşıyan tekile birleştirilir; 16 satır artık tek sınıf adı
  taşır ve detay alt sınıfı sözlüğü 30 değerden 29'a iner. Çoğul yazım eklentinin
  kod listesinde hiç geçmiyordu, tekil yazım hem o listede hem eklentinin geri
  kalanında kullanılıyordu, yani aykırı olan çoğuldu. Çoğul ve tekil ad ne
  katlamayla ne tek harf denetimiyle görülebildiği için birleşmelerini
  `tests/test_detail_hierarchy_pure.py` korur.
- Ek-1e'de bir sembolün detay sınıfı bloğu, sayfada **basıldığı yere** göre eşlenir;
  metnin çıkarılma sırasına göre değil. Böylece `ELEKTRİKLİ ARAÇ ŞARJ İSTASYONU`
  kendisinden önceki sembolün sınıfını değil kendi sınıfını (`KARAYOLLARI`) alır.
  Aynı düzeltme 13 kaydı ilgilendirir; hiçbir sembol adı, SLD kuralı ya da PlanGML
  tipi değişmez.
- Sembol fontları paketle birlikte gelir (131 TTF, 58 aile) ve eklenti
  yüklenirken kaydedilir; kullanıcının sistemine font kurması gerekmez.
- Cihazda bulunmayan normal metin fontları, eklentiyle gelen DejaVu Sans'a
  düşer; katalog yükleme akışı sistemde Arial/Calibri bulunmasına bağlı değildir.
- MSP çizimi Bakanlığın iki ekini birden okur ve ikisi farklı soruları yanıtlar:
  hangi kodun hangi işaretle çizildiği, işaretin rengi, çapı ve tarama ekseni
  `EK-1b Mekansal Strateji Planlar Gösterimleri` ekini, alan ve sınır renk
  kodları Ek-1e detay kataloğunu ilgilendirir. Düz ve kademeli renk dolgusu, nokta
  ve çizgi taraması, karolaj, kesik sınır, gölge ve kaynak türüne göre renkli
  nokta bu iki kaynaktan gelen değerlerle çizilir. Bir dolgu katmanı kesik desen
  taşıyamadığı için kesik sınır yalnızca dış halkaya sınırlanmış ayrı bir çizgi
  katmanı olarak çizilir; aksi hâlde çok parçalı bir poligonun iç halkaları da
  aynı kesikle çizilirdi.
- Yerel karşılığı olmayan üç işaret (liman çapası, havalimanı uçağı, lojistik
  merkezinin düşey yarıklı karesi) EK-1b'nin kendi çiziminden kesilip paketle
  gelir; kalan on üç nokta işareti QGIS'in yerel işaret şekilleriyle ya da ekin
  ölçülen çaplarından yeniden kurulur. Böylece nokta kodları eşleşmeyen kodun
  düştüğü gri daireye artık düşmez.
- Ek iki yerde kendi kendisiyle çelişir: MSP-024 ve MSP-025'in tarama aralığını
  çizimi başka, altındaki yazı başka basar. Ekin yazıyla bastığı değer çizilir ve
  çelişki kayda geçer; arada bir değer uydurulmaz.
- Ölçü basmadığı yerlerde çizim belgelenmiş bir varsayılana düşer: tarama çizgisi
  kalınlığı, karolajın merkez noktası, sınır kalınlığı ve MSP-002'nin üç tonunun
  hangi yerleşme yoğunluğuna, üç işaret boyutunun hangi kademeye karşılık geldiği.
  Katman hangi kodları Bakanlığın gösterdiğinden farklı çizdiğini kendi üst
  verisinde kaydeder (`mpyy/msp_approximated`; `mpyy/msp_pictogram_missing`
  yalnızca Bakanlığın çizdiği bir işaret hiçbir yolla çizilemediğinde dolar ve bu
  sürümde hiçbir kod için dolmaz). Böylece bir ikame Bakanlığın kendi ölçüsü gibi
  görünmez, projeyi açan planlamacı hangi sembolün ne olduğunu okur. Bu kayıt hem
  çizim uygulanırken hem de çalışma alanı katmanı yapılandırılırken yazılır; özel
  katman özelliği kaydedilmiş bir stille taşınmadığı için tek başına çizim yoluna
  bırakılırsa stil yeniden uygulanmayan bir çalışma alanı bu kaydı hiç taşımazdı.
- MSP-002'nin gösterimi veriye bağlıdır: alan tonu `yerlesme_yogunlugu`, işaret
  boyutu `yerlesme_kademesi` alanından gelir. İki alan da ekin kendi
  sözcükleriyle adlandırılır, değerleri 1/2/3'tür ve bağlama bir ifadeyle kurulur;
  böylece katman sınıflandırılmış çizici türünde kalır ve kural, stil
  kaydedildiğinde de taşınır. Üç ton ile üç çap da ekin kendi değerleridir
  (çaplar EK-1b'de çizilen hedef işaretlerinden ölçülür); yalnızca hangi tonun en
  alt kademe olduğu ekte yazmadığı için artan sıra bir çizici kararıdır.
- Katman formları, görüntüleme alan adları ve değer eşlemeleri Türkçeleştirilir.
  Kalıcı veri ve kod kimlikleri değişmez. MSP eylem planı tablosu bunun dışındadır:
  alan adları Bakanlığın izleme sözleşmesindeki adlardır (`baseline_value`,
  `target_value`, `actual_value`, `weight`, `due_date`, `responsible_institution`)
  ve `evaluate_msp_action_monitoring` algoritması bu adlarla okur, bu yüzden
  çevrilmezler.

### Araçlar

86 Processing algoritması ve 3 panel aracı; panelde 7 kategoride toplam 89
girdi. Panel araçları bir algoritma çalıştırmaz, doğrudan eklenti içinde iş
yapar: `create_workspace` (çalışma alanı oluşturma), `style_and_forms` (katmanı
biçimlendir ve formları düzenle), `database_report` (etkin GeoPackage'ı incele).

| Kategori | Araç |
| --- | --- |
| Çalışma alanı ve veri | 13 |
| Parsel tasarımı | 8 |
| Kentsel analiz | 10 |
| Ulaşım ve erişim | 6 |
| Plan denetimleri | 17 |
| Plan dosyası ve dayanaklar | 20 |
| Raporlar ve teslim | 15 |

### Arayüz

- Yeni çalışma paneli: eklenti ikonu, sürüm ve çevrimiçi kılavuz bağlantısı taşıyan bir başlık;
  planın yapılış sırasıyla beş bölüm (Çalışma, Stil, Denetim, Araçlar, Kayıt); çalışma alanı,
  fonksiyon seçerek çizim ve saha araştırması tek sayfada numaralı kartlar olarak. QGIS'in açık ve
  koyu temasına uyar; metinler her iki temada 4,5:1 kontrastı korur.

- **Fonksiyon seçerek çizim her çalışma alanında.** Yerel UİP ve Yerel NİP şablonlarında liste
  şablonun kendi fonksiyon tablolarından gelir (UİP alanları ve çizgileri, NİP alanları ve yol
  çizgileri); seçim, şablonun tanımladığı değerleri doldurur ve çizimi başlatır. MPYY 1.1.7
  çalışma alanında Ek-1e kataloğu sunulur. Liste bir çalışma alanı yüklenince yenilenir; çizilecek
  katman yoksa hangi çalışma alanının açılacağı açıkça söylenir.

### Bilinen sınırlar

- Bu sürümden önce üretilmiş yerel çalışma alanları ve kaydedilmiş Processing
  model dosyaları açılmaz; algoritma kimlikleri bu sürümde yeniden
  adlandırıldı.
- MSP kademesinin kendi XSD'si yoktur ve MPYY 1.1.7 setini yayımlayan kaynakta
  MSP için ayrı bir şema görülmemiştir; MSP çalışma alanı bu yüzden Ek-1e MSP
  kataloğundan üretilir. Katalog 28 kayıttır ve başka bir makine okunur kaynakla
  karşılaştırılamamıştır, yalnızca kendi içinde tutarlıdır.
- MSP'nin çizim tarafı henüz gerçek QGIS masaüstünde bir planlamacı tarafından
  gözle doğrulanmamıştır; kabul testleri katmanları, kod yuvalarını, açılır
  listeleri, sınıflandırma değerlerini, seçilen işaret şeklini ve ölçülen tarama
  açısını ve kaydedilen ikameleri okur, çizilen pikseli okumaz.
- Paketlenen kaynak XML'in, Bakanlığın tarama karolarının, iki ekinden kesilen
  sembollerin ve sembol fontlarının yeniden dağıtım şartları belgesizdir. Durum
  `styles/provenance.json` içinde kayıtlıdır; ayrıntı `THIRD_PARTY_NOTICES.md`
  dosyasındadır.
