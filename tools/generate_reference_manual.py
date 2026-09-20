"""Generate MPYY_REFERENCE_MANUAL.html from the plugin's own catalog.

The tool catalogue is read from ``gui/catalog.py`` and cross-checked against the
algorithm ids actually registered in ``provider.py``. Nothing about the tool list
is typed by hand, so the manual cannot drift from the shipped plugin: if an
algorithm is added or renamed without a catalog row, this script fails loudly
instead of publishing a manual that lies.

Run from the plugin root:

    py -3 tools/generate_reference_manual.py

`tools/` is excluded from the Hub zip via .zipignore, so this generator does not
ship to users; only its output does.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "MPYY_REFERENCE_MANUAL.html"
STUB = ROOT / "docs" / "index.html"
# The stub lives in docs/ while the manual sits in the plugin root, so the link
# needs one "../". That spelling is correct in all three places the file lands:
# the source repo, the Hub zip, and the public portal — build_web_portal.py
# strips "../" before inlining the target over index.html.
STUB_TARGET = "../MPYY_REFERENCE_MANUAL.html"
VERSION = "1.0.0"

# A catalog row is (id, title, purpose, inputs, output); the category is the
# group key it sits under. Everything is normalized to
# (id, title, category, purpose, inputs, output) before use.
Row = tuple[str, str, str, str, str, str]

# Section prose. Written from the plugin's own README, docs/GUI_ARCHITECTURE.md
# and styles/provenance.json — every claim below is traceable to one of them.
SECTIONS: list[tuple[str, str]] = [
    (
        "genel-bakis",
        """
        <h2 id="genel-bakis">Genel bakış</h2>
        <p><strong>PlanX MPYY Studio</strong>, Türkiye planlama pratiğinde MPYY uyumlu
        mekânsal planlama iş akışları için bir QGIS eklentisidir. Taşınabilir GeoPackage
        çalışma alanları, Bakanlık kaynaklı gösterimler, plan denetimleri, saha
        araştırması ve rapor üretimini tek bir panelde birleştirir.</p>

        <table>
          <tbody>
            <tr><th>Eklenti adı</th><td>PlanX MPYY Studio</td></tr>
            <tr><th>Sürüm</th><td>%(version)s</td></tr>
            <tr><th>Sağlayıcı kimliği</th><td><code>planx_mpyy_studio</code></td></tr>
            <tr><th>Hedef QGIS</th><td>3.44 LTR ve 4.x (4.99'a kadar)</td></tr>
            <tr><th>Lisans</th><td>GPL-2.0-or-later</td></tr>
            <tr><th>Yazar</th><td>Yusuf Eminoğlu</td></tr>
            <tr><th>Kapsam</th><td>%(algo_count)s işlem algoritması, %(tool_count)s panel aracı</td></tr>
          </tbody>
        </table>

        <p>Arayüz dili Türkçedir: araç adları, yardım metinleri, parametre etiketleri,
        seçenekler, bildirimler, form sekmeleri, alan etiketleri, kısıt açıklamaları,
        lejantlar, harita bilgi kartları ve üretilen raporlar. Mevzuat kodları, özgün
        kataloglar, saklanan değerler, alan adları ve kullanıcının verdiği adlar
        değiştirilmez. QGIS'in kendi iletişim kutularının dili QGIS dil ayarını izler.</p>

        <p>Eklenti bir <em>hesap aracı</em> değil, <em>plan üretim ve denetim ortamıdır</em>.
        Analizler karar vermez; bulguyu, kullanılan varsayımı ve incelenmesi gereken
        kaydı ayrı ayrı raporlar.</p>
        """,
    ),
    (
        "kurulum",
        """
        <h2 id="kurulum">Kurulum</h2>
        <p>Yerel ZIP paketini QGIS eklenti yöneticisindeki <strong>ZIP'ten kur</strong>
        seçeneğiyle yükleyin. Geliştirme için <code>QGIS_PLUGINPATH</code> değerini
        eklentilerin kök klasörüne ayarlayıp QGIS'i yeniden başlatabilirsiniz.</p>
        <p>Sembol yazı tipleri paketle birlikte gelir ve eklenti yüklenirken kaydedilir;
        sisteme font kurmak gerekmez. QGIS 4 tarafında da aynı kayıt yolu kullanılır.</p>
        <pre><code>py -3 packaging/pf.py verify planx_mpyy_studio</code></pre>
        <p>Bu komut kapıları ve test paketini iki QGIS çalışma zamanında birlikte koşar.</p>
        """,
    ),
    (
        "calisma-alanlari",
        """
        <h2 id="calisma-alanlari">Çalışma alanları</h2>
        <p>Eklenti dört ayrı çalışma alanı türü tanır. Hepsi taşınabilir GeoPackage
        dosyasıdır ve aynı QGIS projesine birlikte yüklenebilir.</p>

        <h3>1. MPYY 1.1.7 çalışma alanı (UİP / NİP / ÇDP)</h3>
        <p>Bakanlığın XSD şemasından birebir üretilir: tablo ve alan adları GML öğe
        adlarıdır, kod listeleri açılır listedir. Gösterim Bakanlığın e-Plan SLD
        setinden gelir. Sit ve koruma sınırlarına detay kataloğundaki kısaltmalar
        (A1, KS, YKK…) yazılır.</p>
        <p>UİP alan formunda MPYY kimliği, fonksiyon kataloğu, yapı nizamı, TAKS,
        KAKS/emsal, yükseklik ve çekme mesafeleri bulunur.</p>

        <h3>2. Yerel UİP çalışma alanı (çizim şablonu)</h3>
        <p>Ayrı bir çalışma alanı türüdür. <code>uip-alanlar</code>,
        <code>uip_cizgiler</code>, <code>uip-notasyonlar</code>,
        <code>yapi_yaklasma</code>, <code>uipPolygonTable</code> ve
        <code>uipLineTable</code> tabloları kaynak şablonla aynı alan ve türlerle
        oluşturulur. Semboloji, koşullu sekmeler, açılır listeler ve varsayılan
        değerler şablonun QGIS projesinden alınır ve <code>forms/yerel_uip</code>
        altında saklanır.</p>
        <p>UİP fonksiyonu zincirli listedir: önce üst konu grubu, sonra o gruptaki
        fonksiyon seçilir. Nizam <code>A</code>, <code>B</code>, <code>BL</code>
        olarak saklanır. Aynı form MPYY çalışma alanındaki <code>mpyy_uip_*</code>
        katmanlarında da kullanılır.</p>

        <h3>3. Saha / arazi kullanımı çalışma alanı</h3>
        <p>Arazi kullanımı ayrı bir çalışma alanıdır. TUCBS arazi katmanları ile
        parsel, yapı ve yol araştırma tabloları plan kararlarından ayrı tutulur.
        Saha işlevleri plan işlevlerine ayrı bir eşleştirme adımıyla bağlanır.</p>

        <h3>4. Mekânsal strateji planı (MSP)</h3>
        <p>MSP için gereklilik denetimi ve eylem izleme araçları ayrı bir grup
        oluşturur. MSP sembolleri EK-1e kataloğundan yerel QGIS sembollerine
        dönüştürülür; GeoServer gerektirmez.</p>

        <h3>Kademe dönüşümü</h3>
        <p>UİP çalışma alanı NİP veya ÇDP şemasına, NİP çalışma alanı ÇDP şemasına
        tip ve kod karşılıklarıyla aktarılır. Karşılığı olmayan ya da planlamacının
        doldurması gereken kodlar tahmin edilmez, ayrıca raporlanır.</p>

        <h3>Geometri onarımı ve sürüm birleştirme</h3>
        <p>Poligon hataları temizlenebilir; isteğe bağlı yakalama toleransı ile küçük
        sınır farklılıkları giderilir. Çalışma alanı sürümleri birleştirilmeden önce
        farklar önizlenebilir; birleştirme politikası kullanıcı tarafından seçilir ve
        çözülemeyen çakışmalar ayrı raporlanır.</p>
        """,
    ),
    (
        "gosterim",
        """
        <h2 id="gosterim">Gösterim ve semboloji</h2>
        <p>Varsayılan stil motoru MPYY/e-Plan gösterimidir. Yerel MPYY stilleri
        seçilebilir alternatiftir. Uygulamadan önce seçilen profili inceleyin.</p>

        <table>
          <thead><tr><th>Profil</th><th>Kaynak</th><th>Durum</th></tr></thead>
          <tbody>
            <tr><td>e-Plan SLD</td><td>Bakanlık e-Plan SLD seti</td><td>Varsayılan</td></tr>
            <tr><td>Detay kataloğu</td><td>Ek-1e detay sembol kataloğu</td><td>Kısaltma notasyonu</td></tr>
            <tr><td>Yerel MPYY stilleri</td><td>Paketle gelen yerel setler</td><td>Alternatif</td></tr>
            <tr><td>UİP</td><td>Yerel çizim şablonu</td><td>Kullanılabilir</td></tr>
            <tr><td>NİP</td><td>Yerel set</td><td>Taslak</td></tr>
            <tr><td>ÇDP</td><td>Bakanlık yedek stili</td><td>Resmî yedek</td></tr>
            <tr><td>MSP</td><td>EK-1e kataloğu</td><td>Yerel QGIS sembolüne dönüştürülür</td></tr>
          </tbody>
        </table>

        <p>Gösterim kaynağı kayıt altındadır. <code>styles/provenance.json</code>
        dosyası kaynak dosyaların boyutunu ve SHA-256 özetini, eşleştirme yöntemini,
        belirsiz olduğu için dışarıda bırakılan kodları ve geometri uyuşmazlıklarını
        kaydeder. Bu dosyaya göre kaynak gösterim setinde <strong>300 üst düzey
        sembol</strong> ve toplam <strong>1100 sembol düğümü</strong> bulunur; 800
        düğüm yalnızca iç içe geçmiş durumdadır.</p>

        <p>Özgün QML dosyaları izlenebilirlik için korunur; temel katmanlar programatik
        formlarla oluşturulur. Kayıtlı projelerde yerel QGIS ifadeleri kullanılır;
        özel Python ifade kaydı gerekmez.</p>
        """,
    ),
    (
        "veri-alisverisi",
        """
        <h2 id="veri-alisverisi">Veri alışverişi</h2>

        <h3>MPYY GML içe aktarma</h3>
        <p><code>import_mpyy_gml</code> e-Plan MPYY dosyasını şemasına göre okur.
        Güncel şemaların yanında Bakanlık paketindeki M serisi (MUİP, MNİP, MÇDP —
        1/25.000 ve 1/100.000, sürüm 1.1.6) da desteklenir; bu şemalar eski yönetmelik
        gösterimlerini ve <code>YeniKod</code> alanını taşır. Şema
        <code>xsi:schemaLocation</code> alanından, yoksa öğe adlarından belirlenir.</p>
        <p><strong>Şemada olmayan öğe ve öznitelikler, kod listesi dışı değerler ve
        okunamayan geometriler tahmin edilmez, raporlanır.</strong> MUİP ve MNİP
        katmanları Bakanlık SLD gösterimiyle açılır; MÇDP için SLD setinde stil
        yoktur.</p>

        <h3>CAD tabakalarını aktarma</h3>
        <p><code>import_cad_to_mpyy</code> CAD/NCZ tabaka adlarını MPYY 1.1.7 nesne
        tiplerine ve kodlarına çevirerek çalışma alanına yazar. Eşleşmeyen tabakalar
        sessizce düşürülmez; tabaka bazında aktarım raporunda listelenir.</p>

        <h3>Şema profili ve kimlik denetimi</h3>
        <p>İdarenin UTF-8 CSV sözlüğü açık JSON sütun eşlemesiyle şema profiline
        dönüştürülebilir. Tablo, alan ve SQLite türü zorunludur. Boş değer, birincil
        anahtar, geometri ve koordinat sistemi sütunları isteğe bağlıdır. Belirsiz
        başlıklar, yinelenen alanlar ve çelişkili geometri tanımları reddedilir.</p>
        <p>Kimlik denetimi gömülü SHA-256 özetini, isteğe bağlı kaynak sözlüğünü ve
        ayrı saklanan bağımsız özeti karşılaştırır. <strong>İçerik tutarlılığı kurumun
        özgünlüğünü tek başına kanıtlamaz;</strong> sonuç raporunda
        <code>issuer_authenticity: NOT_VERIFIED</code> korunur. Şema denetimi
        GeoPackage dosyasını salt okunur açar.</p>

        <h3>Sayısal teslim</h3>
        <p>Teslim paketi için dosya envanteri (boyut ve SHA-256), içerik listesi
        denetimi ve tarih sırası incelemesi ayrı araçlardır. Denetim raporları
        makine tarafından okunabilir biçimde birleştirilebilir.</p>
        """,
    ),
    (
        "fontlar",
        """
        <h2 id="fontlar">Yazı tipleri</h2>
        <p>Eklenti, sembol çizimi için gereken <strong>131 TTF dosyasını</strong>
        <code>resources/fonts</code> altında paketle birlikte taşır ve
        <code>core/fonts.py</code> içindeki <code>register_mpyy_fonts()</code> ile
        kaydeder. Kayıt, panel kurulurken yapılır; QGIS açılışında eklenti yüklüyse
        proje okunmadan önce fontlar hazırdır. Bu sıra önemlidir: sembol katmanı
        ailesini oluşturulma anında çözer, dolayısıyla geç kayıt çizimi düzeltmez.</p>
        <p>Okunabilir arayüz yazı tipinin CAD sembol fontları tarafından ele
        geçirilmemesi için metin fontları (DejaVu ailesi) önce kaydedilir ve
        uygulamanın varsayılan ailesi korunur.</p>
        <p class="warn">Paketlenen yazı tiplerinin yeniden dağıtım durumu
        <code>styles/provenance.json</code> içinde <em>doğrulanmamış</em> olarak
        kayıtlıdır ve bu dosya aile envanterinin yalnızca bir bölümünü listeler.
        Ayrıntı için <a href="#sinirlar">Sınırlar</a> bölümüne bakın.</p>
        """,
    ),
    (
        "arayuz",
        """
        <h2 id="arayuz">Arayüz</h2>
        <p>Panelin üç sekmesi vardır:</p>
        <ul>
          <li><strong>Başlangıç:</strong> çalışma alanı oluşturma, veri aktarma,
          biçimlendirme, karar inceleme ve teslim adımları.</li>
          <li><strong>Araçlar:</strong> %(algo_count)s işlem algoritması ve
          %(tool_count)s panel aracı; kategori, arama, kaydedilen kısayollar ve son
          açılanlar.</li>
          <li><strong>İşlem Kaydı:</strong> yapılandırma açılışları ve sonuçlar; tam
          ayrıntıları kopyalayabilirsiniz.</li>
        </ul>
        <p>Araç seçildiğinde amacı, gerekli girdileri ve beklenen sonucu görürsünüz.
        <strong>Aracı aç</strong> yapılandırmayı açar; hesaplamayı İşlem Araç
        Kutusunda başlatırsınız. Hafif işler için <strong>Kısa formu kullan</strong>
        sonuçları mevcut projeye uygular. Geri dönüldüğünde girdiler korunur.</p>

        <h3>Klavye ve arama</h3>
        <p><kbd>Ctrl</kbd>+<kbd>K</kbd> aramaya geçer, ok tuşları araç seçer,
        <kbd>Enter</kbd> veya <kbd>Alt</kbd>+<kbd>O</kbd> aracı açar,
        <kbd>Tab</kbd> kontroller arasında ilerler. Arama Türkçe karakterlere duyarlı
        değildir: <code>erişilebilirlik</code> ve <code>erisilebilirlik</code> aynı
        eşleşmeleri verir. Algoritma kimlikleriyle de arayabilirsiniz.</p>

        <h3>Erişilebilirlik</h3>
        <p>Panel QGIS yazı tipi ve renk paletini izler. Metinler dar panellerde satıra
        bölünür; formlar dikey kayar. Uzun sonuçlar İşlem Kaydı sekmesinde saklanır.
        Test paletlerinde metin kontrastı 4,5:1 altına düşmez. Bu kontroller tüm ekran
        okuyucular veya işletim sistemi temaları için uyumluluk belgesi değildir.</p>
        """,
    ),
    (
        "denetim",
        """
        <h2 id="denetim">Denetim yaklaşımı</h2>
        <p>Denetim araçları iki ilkeye uyar.</p>
        <ol>
          <li><strong>Eksik dayanak uydurulmaz.</strong> Eksik güzergâha süre atanmaz,
          şemada olmayan öğe tahmin edilmez, karşılığı olmayan kod boş bırakılır.</li>
          <li><strong>Bulgu, varsayım ve kayıt ayrı raporlanır.</strong> Her araç
          hangi varsayımla çalıştığını ve hangi kaydın incelenmesi gerektiğini
          çıktısında taşır.</li>
        </ol>
        <p>Ölçütler mevzuat ve idare verisinden gelir; eklenti kendi başına bir
        uygunluk kararı vermez. Denetim sonuçları <em>inceleme listesi</em>dir,
        <em>onay</em> değildir.</p>
        <p>Erişilebilirlik analizlerinde girdiler aynı, metre birimli projeksiyonlu
        koordinat sistemini kullanmalıdır. Ağ kesişimleri ortak düğümlerle temsil
        edilmelidir; yakalama ağ kenarına değil düğümlerine yapılır. Süre eşiği,
        hızlar ve aktarma cezası kullanıcı girdileridir. Güzergâh kazanımı/kaybı ve
        yakalama belirsizliği ayrı sınıflardır.</p>
        """,
    ),
    ("katalog", ""),  # replaced by the generated tool catalogue
    (
        "panel-araclari",
        """
        <h2 id="panel-araclari">Panel araçları</h2>
        <p>Aşağıdaki araçlar İşlem Araç Kutusuna çıkmaz; doğrudan panelden çalışır ve
        bir GeoPackage çıktısı üretmez.</p>
        %(panel_tools)s
        """,
    ),
    (
        "kalite",
        """
        <h2 id="kalite">Kalite güvencesi</h2>
        <p>Eklentinin kapıları ve test paketi tek komutla, iki QGIS çalışma zamanında
        koşulur:</p>
        <pre><code>py -3 packaging/pf.py verify planx_mpyy_studio</code></pre>
        <p>Kapsam: kod kapıları, güvenlik taraması, Qt6 uyum taraması, çalışma alanı
        ve içe aktarma testleri, kademe ve GML testleri, font kayıt testi, dil
        testleri ve arayüz görüntü üretimi (360/600 piksel panel, 10/15 punto,
        açık/koyu palet; çıktı klasöründe <code>index.html</code>,
        <code>qa.json</code> ve PNG dosyaları).</p>
        <p>Dil testleri %(algo_count)s aracın adını, yardımını, parametrelerini ve
        seçeneklerini; plan/saha formlarını, alan etiketlerini, kısıtları, açılır
        listeleri, lejantları ve QML gösterimlerini tarar. Kaynak kodlar, şema
        kimlikleri, filtreler ve kullanıcı adları değişmez.</p>
        """,
    ),
    (
        "sinirlar",
        """
        <h2 id="sinirlar">Sınırlar ve doğrulanmamış durumlar</h2>
        <p>Bu bölüm, eklentinin ne <em>iddia etmediğini</em> kaydeder.</p>
        <ul>
          <li><strong>Gösterim kaynaklarının yeniden dağıtım durumu
          doğrulanmamıştır.</strong> <code>styles/provenance.json</code> içindeki
          <code>distribution_status</code> alanı
          <em>"unverified; local development only until source redistribution rights
          are established"</em> değerini taşır. Bu, kaynak gösterim setinin ve
          paketlenen 131 yazı tipi dosyasının yeniden dağıtım hakkının belgelenmiş
          olmadığı anlamına gelir.</li>
          <li><strong>Yazı tipi envanteri eksiktir.</strong> Aynı dosyadaki
          <code>font_families</code> alanı yalnızca dört aile kaydeder; pakette 131
          TTF dosyası vardır. Dosya bazında provenance kaydı yoktur.</li>
          <li><strong>MÇDP için SLD gösterimi yoktur.</strong> M serisi şemaları
          okunur, ancak Bakanlık SLD setinde MÇDP stili bulunmaz.</li>
          <li><strong>NİP stili taslaktır</strong>, ÇDP resmî yedek stili kullanır.</li>
          <li><strong>Bazı eski katmanlar güncel şemada yoktur.</strong>
          <code>meri_1000_alan</code> ve eski paralel UİP katmanları güncel şemada
          bulunmaz.</li>
          <li><strong>Kimlik denetimi özgünlük kanıtı değildir.</strong> İçerik
          kimliği doğrulanabilir; düzenleyen kurumun özgünlüğü doğrulanmaz
          (<code>NOT_VERIFIED</code>).</li>
          <li><strong>Arayüz uyumluluk belgesi değildir.</strong> Kontrast ve klavye
          testleri tüm ekran okuyucular veya işletim sistemi temaları için uyumluluk
          iddiası taşımaz.</li>
        </ul>
        """,
    ),
    (
        "lisans",
        """
        <h2 id="lisans">Lisans ve atıf</h2>
        <p><strong>PlanX MPYY Studio</strong> — Yusuf Eminoğlu. Lisans:
        GPL-2.0-or-later.</p>
        <p>Bakanlığın e-Plan şema ve gösterim kaynakları ile üçüncü taraf bileşenlerin
        atıfları eklenti kökündeki <code>THIRD_PARTY_NOTICES.md</code> dosyasındadır.
        Kaynak dosyaların özetleri ve eşleştirme kararları
        <code>styles/provenance.json</code> içinde tutulur.</p>
        <p>"e-Plan", "MPYY", "TUCBS" ve ilgili mevzuat adları ilgili kurumların ürün ve
        düzenleme adlarıdır; bu eklenti bağımsız bir araçtır ve adı geçen kurumlar
        tarafından geliştirilmemiş veya onaylanmamıştır.</p>
        """,
    ),
]

TOC: list[tuple[str, str]] = [
    ("genel-bakis", "Genel bakış"),
    ("kurulum", "Kurulum"),
    ("calisma-alanlari", "Çalışma alanları"),
    ("gosterim", "Gösterim ve semboloji"),
    ("veri-alisverisi", "Veri alışverişi"),
    ("fontlar", "Yazı tipleri"),
    ("arayuz", "Arayüz"),
    ("denetim", "Denetim yaklaşımı"),
    ("katalog", "Araç kataloğu"),
    ("panel-araclari", "Panel araçları"),
    ("kalite", "Kalite güvencesi"),
    ("sinirlar", "Sınırlar"),
    ("lisans", "Lisans ve atıf"),
]

CSS = """
:root{
  --ink:#16232a; --muted:#5a6f78; --paper:#f6f8f5; --card:#ffffff;
  --line:#d9e0da; --teal:#156f6a; --copper:#a85729; --blue:#2d5a80;
  --code:#eef2ee; --th:#e8f1ef; --stripe:rgba(0,0,0,.018);
}
@media (prefers-color-scheme: dark){
  :root{
    --ink:#e4eae8; --muted:#9aa9ae; --paper:#101619; --card:#161d21;
    --line:#2a353a; --teal:#5fc9c0; --copper:#e0915c; --blue:#8fb8d8;
    --code:#1d262b; --th:#1c2a2c; --stripe:rgba(255,255,255,.028);
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  line-height:1.68; font-size:15.5px;
}
#layout{display:flex; min-height:100vh; align-items:flex-start}
#sidebar{
  width:288px; min-width:288px; position:sticky; top:0; height:100vh; overflow-y:auto;
  background:var(--card); border-right:1px solid var(--line); padding:26px 18px 40px;
}
#sidebar .brand{font-weight:800; font-size:16px; line-height:1.35; display:block}
#sidebar .brand small{display:block; font-weight:600; font-size:12px; color:var(--copper);
  text-transform:uppercase; letter-spacing:.07em; margin-top:6px}
#toc{list-style:none; margin:20px 0 0; padding:0; font-size:13.5px}
#toc a{display:block; padding:5px 10px; border-radius:5px; border-left:3px solid transparent;
  color:var(--ink); text-decoration:none}
#toc a:hover,#toc a:focus{background:rgba(21,111,106,.09); border-left-color:var(--teal); color:var(--teal)}
#toc .sub a{padding-left:24px; font-size:12.7px; color:var(--muted)}
#main{flex:1; max-width:1010px; padding:38px 44px 90px; min-width:0}
h1{font-size:2rem; line-height:1.25; margin:0 0 6px; color:var(--teal)}
.lede{color:var(--muted); font-size:1rem; margin:0 0 34px}
h2{font-size:1.45rem; color:var(--blue); border-bottom:2px solid var(--line);
  padding-bottom:.35rem; margin:2.6rem 0 1rem; scroll-margin-top:16px}
h3{font-size:1.1rem; color:var(--copper); margin:1.7rem 0 .5rem; scroll-margin-top:16px}
p{margin:0 0 .85rem}
ul,ol{margin:.5rem 0 .9rem 1.4rem}
li{margin-bottom:.32rem}
a{color:var(--teal)}
code{background:var(--code); padding:.1em .38em; border-radius:4px;
  font-family:"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace; font-size:.88em}
pre{background:var(--code); border:1px solid var(--line); border-left:3px solid var(--teal);
  border-radius:6px; padding:.8rem 1rem; overflow-x:auto}
pre code{background:none; padding:0}
kbd{background:var(--card); border:1px solid var(--line); border-bottom-width:2px;
  border-radius:4px; padding:.08em .4em; font-size:.82em; font-family:inherit}
table{width:100%; border-collapse:collapse; margin:1rem 0 1.4rem; font-size:.9rem}
th,td{border:1px solid var(--line); padding:.48rem .68rem; text-align:left; vertical-align:top}
th{background:var(--th); font-weight:650}
tbody tr:nth-child(even){background:var(--stripe)}
.table-wrap{overflow-x:auto; margin:1rem 0 1.4rem}
.table-wrap table{margin:0; min-width:760px}
td.id code{white-space:nowrap; font-size:.84em}
.cat{margin-top:2rem}
.cat h3{margin-bottom:.15rem}
.cat .count{color:var(--muted); font-size:.85rem; margin:0 0 .7rem}
.warn{border-left:3px solid var(--copper); background:var(--code);
  padding:.7rem .95rem; border-radius:0 6px 6px 0}
footer{margin-top:3.4rem; padding-top:1.2rem; border-top:1px solid var(--line);
  color:var(--muted); font-size:.86rem}
@media (max-width:880px){
  #layout{flex-direction:column}
  #sidebar{position:static; width:100%; min-width:0; height:auto; border-right:0;
    border-bottom:1px solid var(--line)}
  #main{padding:24px 18px 70px; max-width:100%}
  #toc{columns:2; column-gap:14px}
}
@media print{
  #sidebar{display:none} #main{max-width:100%; padding:0}
  body{background:#fff; font-size:11pt; color:#000}
  h2{page-break-after:avoid} tr{page-break-inside:avoid}
}
"""


def read_groups() -> dict[str, list[tuple[str, str, str, str, str]]]:
    """Return {category: [(id, title, purpose, inputs, output)]} from _GROUPS."""
    source = (ROOT / "gui" / "catalog.py").read_text(encoding="utf-8")
    body = source.split("_GROUPS = {", 1)[1].split("\n}\n", 1)[0]

    heads = [(m.start(), m.group(1)) for m in re.finditer(r"\n    '([^']+)': \(\n", body)]
    groups: dict[str, list[tuple[str, str, str, str, str]]] = {}
    for index, (position, name) in enumerate(heads):
        end = heads[index + 1][0] if index + 1 < len(heads) else len(body)
        groups[name] = re.findall(
            r'\(\s*"([a-z0-9_]+)"\s*,\s*\'([^\']*)\'\s*,\s*\'([^\']*)\'\s*,\s*'
            r"\'([^\']*)\'\s*,\s*\'([^\']*)\'",
            body[position:end],
            re.S,
        )
    return groups


def read_literal_panel_tools() -> list[Row]:
    """Panel tools appended as ToolDescription(...) literals after the group table."""
    source = (ROOT / "gui" / "catalog.py").read_text(encoding="utf-8")
    return [
        (match[0], match[1], match[2], match[3], match[4], match[5])
        for match in re.findall(
            r'ToolDescription\(\s*"([a-z0-9_]+)"\s*,\s*\'([^\']*)\'\s*,\s*\'([^\']*)\'\s*,\s*'
            r"\'([^\']*)\'\s*,\s*\'([^\']*)\'\s*,\s*\'([^\']*)\'\s*,\s*False",
            source,
            re.S,
        )
    ]


def algorithm_ids() -> set[str]:
    """Ids actually registered in provider.py: literal name() plus ALGORITHM_NAME."""
    source = (ROOT / "provider.py").read_text(encoding="utf-8")
    literal = set(re.findall(r'def name\(self\)[^\n]*\n\s+return "([a-z0-9_]+)"', source))
    constant = set(re.findall(r'^\s*ALGORITHM_NAME\s*=\s*"([a-z0-9_]+)"', source, re.M))
    return literal | constant


def build_catalogue() -> tuple[str, int, list[tuple[str, str, int]], list[Row]]:
    groups = read_groups()
    registered = algorithm_ids()

    catalogued = {row[0] for rows in groups.values() for row in rows}
    if registered - catalogued:
        raise SystemExit(
            "provider.py registers algorithms with no catalog row: "
            + ", ".join(sorted(registered - catalogued))
        )

    sections: list[str] = []
    toc: list[tuple[str, str, int]] = []
    total = 0
    for name, rows in groups.items():
        algorithms = [row for row in rows if row[0] in registered]
        if not algorithms:
            continue
        total += len(algorithms)
        anchor = f"kat-{len(toc) + 1}"
        toc.append((anchor, name, len(algorithms)))
        body = "\n".join(
            "                <tr><td>{}</td><td>{}</td>"
            '<td class="id"><code>{}</code></td>'
            "<td>{}</td><td>{}</td><td>{}</td></tr>".format(
                index,
                html.escape(title),
                html.escape(tool_id),
                html.escape(purpose),
                html.escape(inputs),
                html.escape(output),
            )
            for index, (tool_id, title, purpose, inputs, output) in enumerate(algorithms, 1)
        )
        sections.append(
            f"""        <div class="cat">
          <h3 id="{anchor}">{html.escape(name)}</h3>
          <p class="count">{len(algorithms)} algoritma</p>
          <div class="table-wrap">
            <table>
              <thead><tr><th style="width:2.6rem">#</th><th>Araç</th><th>Kimlik</th>
              <th>Amaç</th><th>Girdiler</th><th>Çıktı</th></tr></thead>
              <tbody>
{body}
              </tbody>
            </table>
          </div>
        </div>"""
        )

    # Panel tools: the catalog row of a non-Processing entry, plus the two
    # literals declared after the group table.
    panel: list[Row] = []
    for category, rows in groups.items():
        for row in rows:
            if row[0] not in registered:
                panel.append((row[0], row[1], category, row[2], row[3], row[4]))
    panel.extend(read_literal_panel_tools())
    panel.sort(key=lambda row: row[1])

    return "\n".join(sections), total, toc, panel


def build_panel_tools_table(panel: list[Row]) -> str:
    rows = "\n".join(
        "            <tr><td>{}</td><td>{}</td>"
        '<td class="id"><code>{}</code></td>'
        "<td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(title),
            html.escape(category),
            html.escape(tool_id),
            html.escape(purpose),
            html.escape(inputs),
            html.escape(output),
        )
        for tool_id, title, category, purpose, inputs, output in panel
    )
    return f"""        <div class="table-wrap">
          <table>
            <thead><tr><th>Panel aracı</th><th>Kategori</th><th>Kimlik</th>
            <th>Amaç</th><th>Girdiler</th><th>Sonuç</th></tr></thead>
            <tbody>
{rows}
            </tbody>
          </table>
        </div>"""


def main() -> int:
    catalogue, algorithm_count, catalogue_toc, panel = build_catalogue()
    panel_count = len(panel)

    catalogue_section = f"""        <h2 id="katalog">Araç kataloğu</h2>
        <p>Eklenti <strong>{algorithm_count} işlem algoritması</strong> kaydeder ve bunları
        {len(catalogue_toc)} kategoride sunar. Aşağıdaki liste <code>gui/catalog.py</code>
        dosyasındaki kullanıcı açıklamalarından üretilir; <em>Kimlik</em> sütunu İşlem Araç
        Kutusunda ve Python ifadelerinde kullanılan algoritma kimliğidir.</p>
        <p>Her araç bir <em>inceleme</em> üretir; hiçbiri tek başına uygunluk kararı
        vermez. Eşleşmeyen kod, eksik dayanak ve okunamayan geometri tahmin edilmez,
        bulgu olarak raporlanır.</p>
{catalogue}
"""

    values = {
        "version": VERSION,
        "algo_count": algorithm_count,
        "tool_count": panel_count,
        "panel_tools": build_panel_tools_table(panel),
    }

    rendered = {
        key: prose.strip() % values for key, prose in SECTIONS if key != "katalog"
    }

    # Prose order is fixed by SECTIONS; the catalogue goes where its key sits.
    keys = [key for key, _ in SECTIONS if key != "katalog"]
    split_at = [key for key, _ in SECTIONS].index("katalog")
    before = "\n".join(rendered[key] for key in keys[:split_at])
    after = "\n".join(rendered[key] for key in keys[split_at:])

    toc_html = ['          <li><a href="#genel-bakis">Genel bakış</a></li>']
    for key, label in TOC:
        if key == "genel-bakis":
            continue
        toc_html.append(f'          <li><a href="#{key}">{html.escape(label)}</a></li>')
        if key == "katalog":
            for anchor, name, count in catalogue_toc:
                toc_html.append(
                    f'          <li class="sub"><a href="#{anchor}">'
                    f"{html.escape(name)} ({count})</a></li>"
                )

    document = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PlanX MPYY Studio — Referans El Kitabı</title>
<meta name="description" content="PlanX MPYY Studio QGIS eklentisinin {algorithm_count} işlem algoritması, çalışma alanı modeli, gösterim profilleri ve veri alışverişi için referans el kitabı.">
<style>{CSS}</style>
</head>
<body>
<div id="layout">
  <nav id="sidebar">
    <span class="brand">PlanX MPYY Studio<small>Referans El Kitabı · {VERSION}</small></span>
    <ul id="toc">
{chr(10).join(toc_html)}
    </ul>
  </nav>
  <main id="main">
    <h1>PlanX MPYY Studio</h1>
    <p class="lede">{algorithm_count} işlem algoritması ve {panel_count} panel aracıyla MPYY
    uyumlu plan üretimi, denetimi ve teslimi için QGIS ortamı.</p>
{before}
{catalogue_section}
{after}
    <footer>
      <p>PlanX MPYY Studio {VERSION} · Yusuf Eminoğlu · GPL-2.0-or-later<br>
      Bu el kitabı <code>tools/generate_reference_manual.py</code> ile eklentinin kendi
      kataloğundan üretilir; araç listesi elle yazılmaz.</p>
    </footer>
  </main>
</div>
</body>
</html>
"""

    OUT.write_text(document, encoding="utf-8")

    STUB.parent.mkdir(parents=True, exist_ok=True)
    STUB.write_text(
        '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0;url={STUB_TARGET}">'
        "<title>PlanX MPYY Studio — Referans El Kitabı</title></head><body>"
        f'<p>Yönlendiriliyor: <a href="{STUB_TARGET}">PlanX MPYY Studio — '
        "Referans El Kitabı</a></p></body></html>\n",
        encoding="utf-8",
    )

    print(f"yazildi: {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")
    print(f"yazildi: docs/index.html stub ({STUB.stat().st_size} B)")
    print(
        f"  {algorithm_count} algoritma / {len(catalogue_toc)} kategori / "
        f"{panel_count} panel araci"
    )
    for _, name, count in catalogue_toc:
        print(f"    {count:3d}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
