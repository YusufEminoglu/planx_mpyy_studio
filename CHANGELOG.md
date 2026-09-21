# Changelog

## [1.0.0] - 2026-09-20

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
- Katman formları, görüntüleme alan adları ve değer eşlemeleri Türkçeleştirilir.
  Kalıcı veri ve kod kimlikleri değişmez.

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

### Bilinen sınırlar

- Bu sürümden önce üretilmiş yerel çalışma alanları ve kaydedilmiş Processing
  model dosyaları açılmaz; algoritma kimlikleri bu sürümde yeniden
  adlandırıldı.
- Paketlenen kaynak XML'in ve sembol fontlarının yeniden dağıtım şartları
  belgesizdir. Durum `styles/provenance.json` içinde kayıtlıdır; ayrıntı
  `THIRD_PARTY_NOTICES.md` dosyasındadır.
