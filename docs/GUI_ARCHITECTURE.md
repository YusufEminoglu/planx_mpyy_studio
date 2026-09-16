# MPYY Studio GUI mimarisi

## İnceleme ve düzenleme

Önceki 2.135 satırlık panel dosyası gezinme, 18 form ve 57 gelişmiş araç düğmesini aynı yapıda tutuyordu. Dört uzun sekme 440 pikselde kesiliyor, sabit 9 punto yazı kullanıcı tercihlerini izlemiyordu. Girdi ve çıktıların ne olduğu yapılandırma açılmadan açıklanmıyordu.

Yeni panel **Başlangıç**, **Araçlar**, **Kayıt** sekmelerini kullanır. 86 işlem algoritması ve iki panel aracı korunmuştur. Kategoriler, Türkçe arama, kaydedilen kısayollar ve son açılanlar araç keşfini destekler. Kullanıcının son dil tercihi bu eklenti için Türkçedir.

## Sorumluluklar

| Modül | Sorumluluk |
| --- | --- |
| `dock.py` | Panel bileşimi, QGIS arayüzü ve stil motorları |
| `gui/catalog.py` | Araç kimlikleri, Türkçe amaç/girdi/çıktı açıklamaları ve arama; Qt bağımlılığı yok |
| `gui/processing_text.py` | İşlem açıklamaları, parametre etiketleri ve sırası korunmuş seçenekler |
| `core/localization.py` | Türkçe gösterim, alan etiketleri ve yerel QGIS ifadeleri; veri kimlikleri korunur |
| `resources/turkish_labels.tsv` | Mevzuat kodlarından bağımsız Türkçe gösterim sözlüğü |
| `gui/workbench.py` | Gezinme, filtreler, kısayollar, yapılandırma açma ve işlem kaydı |
| `gui/forms.py` | Mevcut varsayılanları koruyan odaklı formlar |
| `gui/actions.py` | Çalışma alanı, biçimlendirme ve analiz çağrıları |
| `gui/widgets.py` | Satıra bölünen düğmeler, gerçek alan seçicileri ve erişilebilir etiketler |
| `ui_theme.py` | QGIS paletinden renkler, kontrast ve yerel düzenleyici görünümü |

Araç seçimi veya arama hesaplama başlatmaz. Yapılandırma açılması tamamlanmış analiz olarak kaydedilmez. Hafif formlar sonuçları doğrudan projeye uygular. Formlar bir kez oluşturulur; geri gezinmede değerler korunur. QGIS sinyalleri eklenti kaldırılırken ayrılır. Hesap motorlarının veri sözleşmesi korunur; bu düzenleme yeni bir arka plan yürütme sistemi değildir.

## Dil ve erişilebilirlik doğrulaması

Dil testleri 86 aracın adını, yardımını, parametrelerini ve seçeneklerini; plan/saha formlarını, alan etiketlerini, kısıtları, açılır listeleri, lejantları ve QML gösterimlerini tarar. Yerel QGIS ifadeleri ve harita bilgi kartları değerlendirilir; raporların isteğe bağlı bölümleri de kontrol edilir. Kaynak kodlar, şema kimlikleri, filtreler ve kullanıcı adları değişmez.

Değer ilişkilerinde sanal gösterim alanı, referans ilişkilerinde yerel gösterim ifadesi kullanılır. Kaydedilen projeler özel Python ifade kaydı gerektirmez.

QGIS 3.44 ve 4.2 için 360/600 piksel panel, 10/15 punto, açık/koyu palet görüntüleri üretilir. Klavye gezinmesi, etiket bağlantıları, alan yeniden bağlama, kaydedilen/son açılan araçlar ve form durumu test edilir. Test paletlerinde metin kontrastı 4,5:1 altına düşmez. Sayı kutularının okları yerel çizilir; yalnız gömülü metin düzenleyicisinin görünümü değiştirilir. Uzun sonuçlar Kayıt sekmesinde tutulur.

Bu kontroller tüm ekran okuyucular veya işletim sistemi temaları için uyumluluk belgesi değildir. QGIS'in kendi iletişim kutuları QGIS dil ayarını izler.

```powershell
& C:\OSGeo4W\bin\python-qgis-ltr.bat -m planx_mpyy_studio.tests.render_workbench_qgis --output scratch/gui_ltr
& C:\OSGeo4W\bin\python-qgis.bat -m planx_mpyy_studio.tests.render_workbench_qgis --output scratch/gui_qgis4
py -3 packaging/pf.py verify planx_mpyy_studio
```

Görüntü klasörlerinde `index.html`, `qa.json` ve PNG dosyaları bulunur.
