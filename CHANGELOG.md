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
- Sembol fontları paketle birlikte gelir (131 TTF, 58 aile) ve eklenti
  yüklenirken kaydedilir; kullanıcının sistemine font kurması gerekmez.
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
