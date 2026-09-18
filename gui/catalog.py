"""Task descriptions kept separate from widgets and Processing implementations."""

from __future__ import annotations

from dataclasses import dataclass, replace
import unicodedata
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ToolDescription:
    id: str
    title: str
    category: str
    purpose: str
    inputs: str
    output: str
    processing: bool = True
    keywords: str = ""


# Each row describes the user's task, its prerequisites and its result.
_GROUPS = {
    'Çalışma alanı ve veri': (
        ("create_workspace", 'Plan çalışma alanı oluştur', 'Yerel UİP çizim şablonundan ya da PlanGML 1.1.7 şemasından taşınabilir bir çalışma alanı üretir.', 'Koordinat sistemi ile çalışma alanı türünü (Yerel UİP veya PlanGML kademesi) ve yeni bir GeoPackage dosyası seçin.', 'Katmanları, formları ve gösterimi hazır GeoPackage dosyası.', False),
        ("create_land_use_workspace", 'Saha çalışma alanı oluştur', 'Arazi kullanım araştırmalarını plan kararlarından ayrı saklar.', 'Koordinat sistemi ve yeni bir GeoPackage dosyası seçin.', 'Arazi kullanımı ve saha katmanlarını içeren GeoPackage dosyası.'),
        ("ingest_vector_dataset", 'Vektör veri içe aktar', 'Mevcut CBS veya CAD vektörlerini çalışma alanına aktarır.', 'Kaynak vektör katmanı ve hedef GeoPackage katmanı.', 'Aktarılan nesneler ve içe aktarma özeti.'),
        ("import_cad_to_plangml", 'CAD tabakalarını PlanGML çalışma alanına aktar', 'CAD/NCZ tabaka adlarını PlanGML 1.1.7 nesne tiplerine ve kodlarına çevirerek çalışma alanına yazar; eşleşmeyen tabakaları raporlar.', 'Tabaka adı alanı olan CAD veya CBS vektör katmanı ve PlanGML 1.1.7 çalışma alanı.', 'PlanGML tablolarına yazılan nesneler ve tabaka bazında aktarım raporu.'),
        ("audit_plangml_workspace", 'PlanGML şema uygunluğunu denetle', 'Zorunlu alanları, kod listesi değerlerini, geometri türünü ve şemada olmayan katmanları denetler.', 'PlanGML 1.1.7 çalışma alanı GeoPackage dosyası.', 'Katman ve nesne bazında şema aykırılıkları raporu.'),
        ("convert_plangml_level", 'PlanGML kademesini dönüştür', 'UİP çalışma alanını NİP veya ÇDP şemasına, NİP çalışma alanını ÇDP şemasına tip ve kod karşılıklarıyla aktarır.', 'PlanGML 1.1.7 UİP veya NİP çalışma alanı ve hedef kademe.', 'Yeni PlanGML çalışma alanı ve karşılığı olmayan ya da planlamacının doldurması gereken kodların raporu.'),
        ("import_plangml_gml", 'PlanGML GML dosyasını içe aktar (M serisi dahil)', 'e-Plan PlanGML dosyasını şemasına göre okur; eski yönetmelik gösterimlerini taşıyan M serisi (MUİP, MNİP, MÇDP) ve güncel şemalar desteklenir.', 'PlanGML GML dosyası; şema otomatik belirlenir, koordinat sistemi dosyada yoksa seçilmelidir.', 'Şemanın tablolarını, açılır listelerini ve Bakanlık gösterimini taşıyan GeoPackage ile içe aktarma raporu.'),
        ("clean_planning_geometries", 'Plan geometrisini onar', 'Poligon hatalarını temizler; isteğe bağlı olarak küçük sınır farklılıklarını yakalama toleransı ile giderir.', 'Plan poligonları ve belirtilmiş yakalama toleransı.', 'Onarılmış geometri katmanı; kullanmadan önce değişiklikleri inceleyin.'),
        ("preview_workspace_reconciliation", 'Çalışma alanı farklarını önizle', 'Çalışma alanı sürümlerini birleştirmeden önce farkları gösterir.', 'Başlangıç ve düzenlenmiş GeoPackage sürümleri.', 'Birleştirme önizlemesi ve çakışma bulguları.'),
        ("reconcile_workspace_versions", 'Çalışma alanı sürümlerini birleştir', 'Seçilen sürüm birleştirme politikasını uygular.', 'Çalışma alanı sürümleri, birleştirme politikası ve hedef dosya.', 'Birleştirilmiş çalışma alanı ve çözülemeyen çakışmalar.'),
        ("crosswalk_saha_to_plan", 'Saha arazi kullanım kodlarını eşleştir', 'Kaynak saha işlevlerini plan işlevleriyle eşleştirir.', 'Saha katmanı ve işlev kodu alanı. Kısa formda hedef plan katmanı da gerekir.', 'Eşleşen kodlar ve incelenmesi gereken belirsiz eşleşmeler.'),
    ),
    'Parsel tasarımı': (
        ("calculate_building_envelope", 'Yapılaşma zarfını hesapla', 'Parselde çekme mesafelerinin içinde kalan yapılaşabilir alanı belirler.', 'Parsel poligonları ve çekme mesafeleri.', 'Yapılaşma zarfı poligonları.'),
        ("validate_paiy_compliance", 'Parsel yapılaşabilirliğini denetle', 'Parsel boyutlarını ve belirtilen imar parametrelerini ön denetimden geçirir.', 'Parsel poligonları, yapı nizamı, kat sayısı ve çekme mesafeleri.', 'Parsel uygunluk ön denetimi katmanı.'),
        ("optimize_parcel_subdivision", 'Parsel bölünmelerini tasarla', 'Büyük parselleri belirtilen cephe, derinlik ve alan kısıtlarına göre böler.', 'Kaynak parseller, isteğe bağlı komşu yollar, yapı nizamı, kullanım, kat sayısı ve hedef cephe.', 'Önerilen parsel geometrileri ve inceleme notları.'),
        ("apply_corner_chamfer", 'Parsel köşelerine pah uygula', 'Parsel köşelerini belirtilen pah mesafesine göre keser.', 'Ada veya parsel poligonları ve pah mesafesi.', 'Pah uygulanmış poligonlar.'),
        ("calculate_dop_reallocation", 'Düzenleme ortaklık payını hesapla', 'DOP kesintisini ve net tahsis alanlarını hesaplar.', 'Kadastro parselleri, kamu alanı geometrisi ve kesinti varsayımları.', 'DOP ve net alan sonuçları.'),
        ("generate_land_readjustment_matrix", 'Tahsis matrisi oluştur', 'Kadastro parsellerinden imar parsellerine tahsis kayıtlarını hazırlar.', 'Kadastro ve imar parselleri ile belirtilmiş DOP oranı.', 'Tahsis matrisi ve alan dengesi sonuçları.'),
        ("evaluate_transformation_feasibility", 'Dönüşüm fizibilitesini değerlendir', 'Dönüşüm hakedişlerini ve mali varsayımları karşılaştırır.', 'Dönüşüm parselleri ve malik/müteahhit payı varsayımları.', 'Hakediş ve fizibilite sonuçları.'),
        ("generate_procedural_3d_massing", 'Üç boyutlu yapı kütleleri oluştur', 'İmar ve çatı parametrelerinden yapı hacimleri oluşturur.', 'İmar öznitelikli parseller ve çatı oluşturma tercihi.', 'Üç boyutlu kütle geometrisi ve hacim ölçümleri.'),
    ),
    'Kentsel analiz': (
        ("synthesize_parcel_density", 'Parsel, plan ve yapıları sentezle', 'Parsel doluluğunu, yapı yoğunluğunu ve plan işlevlerini ölçer.', 'Parsel, plan işlevi ve isteğe bağlı yapı poligonları.', 'Yoğunluk özniteliklerini içeren parsel sentezi katmanı.'),
        ("estimate_plan_capacity", 'Yapı ve nüfus kapasitesini hesapla', 'Belirtilen inşaat alanı ve konut varsayımlarıyla kapasiteyi hesaplar.', 'Plan poligonları, emsal, taban alanı oranı ve ortalama konut alanı.', 'İnşaat alanı ve nüfus kapasitesi tahminleri.'),
        ("analyze_amenity_standards", 'Donatı yeterliliğini değerlendir', 'Ölçülen donatı alanlarını nüfusa dayalı ön denetim standartlarıyla karşılaştırır.', 'Plan poligonları, işlev kodları ve çalışma nüfusu.', 'Donatı arzı ve açık sonuçları.'),
        ("calculate_parking_requirement", 'Otopark ihtiyacını hesapla', 'Otopark kapasitesini ve belirtilen yapı varsayımlarını karşılaştırır.', 'Plan/parsel poligonları, emsal ve otopark alanı varsayımları.', 'Otopark ihtiyacı ve denge sonuçları.'),
        ("calculate_shelter_requirement", 'Sığınak ihtiyacını hesapla', 'Belirtilen kullanıcı sayısı varsayımlarıyla sığınak kapasitesini ön denetimden geçirir.', 'Plan/parsel poligonları ve kişi başına sığınak alanı varsayımları.', 'Sığınak ihtiyacı ve kapasite sonuçları.'),
        ("prioritize_urban_transformation", 'Dönüşüm önceliklerini belirle', 'Mevcut yapıları belirtilen risk göstergelerine göre sıralar.', 'Yapı veya parsel katmanı ve değerlendirme yılı.', 'Risk ön değerlendirme puanları ve öncelik grupları.'),
        ("analyze_mpyy_building_morphology", 'Yapı biçimini ölç', 'Kompaktlık, yönlenme ve ortak duvar ilişkilerini ölçer.', 'Projeksiyonlu koordinat sisteminde yapı taban poligonları.', 'Yapı morfolojisi katmanı.'),
        ("analyze_mpyy_spacematrix_density", 'Kentsel yoğunluğu ölç', 'Çalışma birimleri için Spacematrix yoğunluk ölçütlerini hesaplar.', 'Yapı tabanları, kat sayısı alanı veya varsayılan kat sayısı ve isteğe bağlı çalışma adaları.', 'FSI, GSI ve ilgili yoğunluk ölçütleri.'),
        ("analyze_mpyy_street_network_morphology", 'Yol ağı biçimini ölç', 'Ağ bağlantılılığını ve yol yapısını ölçer.', 'Projeksiyonlu koordinat sisteminde çizgi yol ağı.', 'Yol ve ağ morfolojisi ölçütleri.'),
        ("compare_mpyy_plan_scenarios", 'Plan göstergelerini karşılaştır', 'Adlandırılmış sayısal göstergeleri, birleşik bir puan üretmeden karşılaştırır.', 'Göstergeleri ve tercihleri belirtilmiş iki senaryo JSON dosyası.', 'Gösterge farkları ve belirtilen tercih yönleri.'),
    ),
    'Ulaşım ve erişim': (
        ("analyze_nip_uip_routed_accessibility", 'Ağ üzerinden yürüme erişimini ölç', 'Bağlantılı ağda talep noktalarından tesislere olan mesafeyi ölçer.', 'Aynı projeksiyonlu koordinat sisteminde ağ, talep ve tesis katmanları.', 'Her talep nesnesi için ağ mesafesi ve erişilebilirlik durumu.'),
        ("audit_mpyy_article12_walking_distances", 'Tesislere yürüme mesafelerini denetle', 'Tesis türüne göre mesafe ön denetimi yapar; istisnaları ayrıca inceler.', 'Yürüme ağı, talep katmanı ve türleri belirtilmiş tesis katmanı.', 'Yürüme mesafesi ön denetimi ve istisna bulguları.'),
        ("audit_nip_uip_active_mobility_network", 'Aktif ulaşım sürekliliğini denetle', 'Yaya ve bisiklet ağlarının sürekliliğini denetler.', 'NİP/UİP ulaşım ağı, isteğe bağlı merkezler ve yakalama/erişim mesafesi toleransları.', 'Ağ sürekliliği bulguları.'),
        ("analyze_mpyy_multimodal_accessibility", 'Çok modlu yolculuk süresini ölç', 'Tesislere yürüme, bisiklet ve toplu taşıma yolculuklarını ölçer.', 'Aynı projeksiyonlu koordinat sisteminde ulaşım türü kodlanmış bağlantılı ağ, talep ve tesisler.', 'Yolculuk süresi, ulaşım türü sırası, tesis ve erişim durumu.'),
        ("compare_mpyy_accessibility_scenarios", 'Erişilebilirlik senaryolarını karşılaştır', 'Ağ ve tesis değişikliklerini aynı talep katmanını kullanarak karşılaştırır.', 'Metre birimli aynı koordinat sisteminde iki ağ, iki tesis grubu ve ortak talep.', 'Süre farkları, kazanılan/kaybedilen güzergâhlar ve yakalama incelemesi sonuçları.'),
        ("analyze_mpyy_accessibility_equity", 'Erişilebilirlik eşitliğini ölç', 'Erişilebilirlik dağılımını nüfus ağırlıklarıyla karşılaştırır.', 'Erişilebilirlik ölçümleri ve nüfus/ağırlık öznitelikleri.', 'Ağırlıklı dağılım ve eşitsizlik ölçütleri.'),
    ),
    'Plan denetimleri': (
        ("validate_quality_control", 'Topoloji ve çekme mesafelerini denetle', 'Çakışan parselleri ve yapı/çekme mesafesi ihlallerini belirler.', 'Parsel poligonları, isteğe bağlı yapı poligonları ve çekme mesafesi.', 'Geometri ve çekme mesafesi sorunları katmanı.'),
        ("evaluate_plan_revision", 'Plan revizyonlarını karşılaştır', 'Mevcut ve önerilen plan geometrilerini ve donatı değişikliklerini karşılaştırır.', 'Mevcut ve önerilen plan katmanları ile inceleme mesafesi varsayımları.', 'Plan değişikliği ve eşdeğer alan bulguları.'),
        ("audit_municipal_bylaw_compliance", 'Belediye düzenleme parametrelerini denetle', 'Belirtilen parametreleri seçilen kural profiliyle karşılaştırır.', 'Parsel/yapı öznitelikleri ve belirtilmiş belediye profili.', 'İncelenmesi gereken parametre uyuşmazlıkları.'),
        ("audit_msp_plan_requirements", 'Mekânsal strateji planı gerekliliklerini denetle', 'MSP için belirtilen plan dayanaklarını ve gerekliliklerini denetler.', 'MSP plan nesneleri ve belirtilmiş harita ölçeği.', 'MSP gereklilik bulguları katmanı.'),
        ("audit_cdp_plan_requirements", 'Çevre düzeni planı gerekliliklerini denetle', 'ÇDP için belirtilen plan dayanaklarını ve gerekliliklerini denetler.', 'ÇDP plan nesneleri ve belirtilmiş harita ölçeği.', 'ÇDP gereklilik bulguları katmanı.'),
        ("audit_nip_plan_requirements", 'Nazım imar planı gerekliliklerini denetle', 'NİP için belirtilen plan dayanaklarını ve gerekliliklerini denetler.', 'NİP plan nesneleri ve belirtilmiş harita ölçeği.', 'NİP gereklilik bulguları katmanı.'),
        ("audit_uip_plan_requirements", 'Uygulama imar planı gerekliliklerini denetle', 'UİP için belirtilen plan dayanaklarını ve gerekliliklerini denetler.', 'UİP plan nesneleri ve belirtilmiş harita ölçeği.', 'UİP gereklilik bulguları katmanı.'),
        ("audit_plan_hierarchy_consistency", 'Plan kademeleri tutarlılığını denetle', 'Üst ve alt kademe plan kararlarını karşılaştırır.', 'İlgili plan kademelerinin katmanları.', 'Plan kademeleri tutarlılık bulguları.'),
        ("screen_mpyy_threshold_constraints", 'Eşik kısıtlarını ön denetimden geçir', 'Plan kararlarını belirtilen kısıtlarla çakıştırır.', 'Eşik kısıtı öznitelikleri belirtilmiş plan nesneleri ve inceleme oranı.', 'İncelenmesi gereken kısıt kesişimleri.'),
        ("audit_mpyy_road_plan_change", 'Yol planı değişikliklerini denetle', 'Yol değişikliği geometrisini ve destekleyici dayanakları inceler.', 'Mevcut/önerilen yol planı verisi ve değişiklik dayanakları.', 'Yol değişikliği denetim bulguları.'),
        ("audit_mpyy_density_height_change", 'Yoğunluk ve yükseklik değişikliklerini denetle', 'Değişen yoğunluk/yükseklik parametrelerini ve dayanaklarını inceler.', 'Mevcut/önerilen plan öznitelikleri ve değişiklik dayanakları.', 'Yoğunluk ve yükseklik değişikliği bulguları.'),
        ("classify_cdp_revision_scope", 'Çevre düzeni planı revizyon kapsamını sınıflandır', 'Belirtilen ÇDP müdahalesinin kapsamını ön denetimden geçirir.', 'Mevcut/önerilen çevre düzeni planı verisi.', 'Revizyon kapsamı sınıflandırması ve inceleme notları.'),
        ("audit_adjacent_plan_boundary_consistency", 'Komşu plan sınırlarını denetle', 'Komşu planların sınır uyuşmazlıklarını belirler.', 'Ortak projeksiyonlu koordinat sisteminde komşu plan katmanları.', 'Sınır tutarlılığı bulguları.'),
        ("audit_plan_fabric_topology", 'Plan dokusunu denetle', 'Plan kararlarındaki boşlukları ve çakışmaları belirler.', 'Plan karar poligonları ve topoloji toleransları.', 'Plan dokusu topoloji bulguları.'),
        ("audit_mpyy_article10_official_legend", 'Resmî gösterim kodlarını denetle', 'Belirtilen gösterim kodlarını eklentiyle gelen kataloglarla eşleştirir.', 'Gösterim kodu öznitelikli plan nesneleri ve plan kademesi.', 'Tam eşleşmeler ve incelenmesi gereken eşleşmeyen kodlar.'),
        ("classify_mpyy_article25_plan_intervention", 'Plan müdahalesini sınıflandır', 'Revizyon, ilave ve plan değişikliği inceleme durumlarını ayırt eder.', 'Mevcut/önerilen kararlar ve müdahale dayanakları.', 'Destekleyici bulgularla birlikte müdahale sınıflandırması.'),
        ("audit_mpyy_mixed_use_details", 'Karma kullanım ayrıntılarını denetle', 'Belirtilen konut oranlarını ve destekleyici plan ayrıntılarını denetler.', 'Karma kullanım karar nesneleri ve destekleyici ayrıntı öznitelikleri.', 'Eksik ayrıntı ve karma kullanım inceleme bulguları.'),
    ),
    'Plan dosyası ve dayanaklar': (
        ("initialize_mpyy_plan_dossier", 'Plan dosyası başlat', 'Düzenlenebilir kayıtlarla düzenli bir yerel plan dosyası oluşturur.', 'Plan kimliği, kapsamı ve hedef klasör.', 'Plan dosyası klasörleri ve örnek içerik listeleri.'),
        ("audit_plan_submission_dossier", 'Teslim dayanaklarını denetle', 'Plan teslimini destekleyen dayanakları denetler.', 'Plan teslim dosyasının içerik listesi.', 'Teslim dayanakları denetim raporu.'),
        ("audit_mpyy_dossier_completeness", 'Plan dosyası bütünlüğünü denetle', 'Belirtilen bağlam için gerekli plan bileşenlerini denetler.', 'Plan dosyası klasörü ve bileşen listesi.', 'Eksik bileşen ve dosya kimliği bulguları.'),
        ("audit_mpyy_evidence_provenance", 'Dayanak kaynaklarını denetle', 'Kurum, sürüm, tarih, ölçek ve kimlik izlenebilirliğini denetler.', 'Dayanak kaynak listesi ve isteğe bağlı yerel dosyalar.', 'Dayanak kaynak izlenebilirliği bulguları.'),
        ("audit_mpyy_evidence_freshness", 'Dayanak güncelliğini denetle', 'Veri sahibinin belirttiği inceleme/geçerlilik sürelerini uygular.', 'Dayanak kayıtları ve belirtilmiş güncellik politikası.', 'Süresi dolmuş, ileri tarihli ve geçersiz dayanak bulguları.'),
        ("audit_institution_opinion_register", 'Kurum görüşlerini denetle', 'Talep/yanıt tarih sırasını ve belirtilen süre uzatımlarını inceler.', 'Kurum görüşleri kayıt dosyası.', 'Görüş tarih sırası ve beklenen yanıt bulguları.'),
        ("audit_mpyy_plan_report_content", 'Rapor içeriğini denetle', 'Belirtilen plan bağlamı için rapor bölümlerini denetler.', 'Plan raporu içerik listesi.', 'Eksik bölüm ve uygulanabilirlik bulguları.'),
        ("audit_conservation_plan_dossier", 'Koruma amaçlı plan dayanaklarını denetle', 'Koruma bağlamındaki dayanakları ve belirtilen kararları denetler.', 'Koruma amaçlı plan dosyası içerik listesi.', 'Koruma dayanağı bulguları.'),
        ("audit_integrated_coastal_plan_dossier", 'Kıyı planı dayanaklarını denetle', 'Kıyı analizi temalarını ve strateji dayanaklarını denetler.', 'Bütünleşik kıyı planı dosyasının içerik listesi.', 'Kıyı dayanağı bulguları.'),
        ("audit_urban_design_project_prerequisites", 'Kentsel tasarım ön koşullarını denetle', 'Plan onayını ve tasarımı destekleyen dayanakları denetler.', 'Kentsel tasarım ön koşulları içerik listesi.', 'Ön koşul ve uygulamaya hazırlık bulguları.'),
        ("audit_mpyy_article8_research_dossier", 'Araştırma dayanaklarını denetle', 'Belirtilen araştırma, kaynak ve kurum dayanaklarını denetler.', 'Araştırma dosyası içerik listesi.', 'Araştırma dayanağı bulguları.'),
        ("audit_mpyy_article11_standards_context", 'Standartların uygulama bağlamını denetle', 'Bağlama bağlı standartların dayanaklarını denetler.', 'Standart bağlamı içerik listesi.', 'Eksik gerekçe ve bağlam bulguları.'),
        ("audit_mpyy_publication_objection_register", 'Askı ve itiraz kayıtlarını denetle', 'Askı sürelerini ve itirazların tarih sırasını inceler.', 'Askı ve itiraz kayıt dosyası.', 'Tarih sırası, ilan ve itiraz bulguları.'),
        ("audit_mpyy_participation_register", 'Katılım dayanaklarını denetle', 'Katılım yöntemlerini, paydaşları ve önerilerin değerlendirilmesini denetler.', 'Katılım etkinlikleri kayıt dosyası.', 'Katılım dayanağı ve kapsama bulguları.'),
        ("audit_mpyy_cancelled_plan_evidence", 'İptal edilen planın yeniden kullanılan dayanaklarını denetle', 'Yeniden kullanılan, geçersiz kılınan ve reddedilen dayanakların yeniden değerlendirilmesini denetler.', 'İptal edilen plan dayanakları kayıt dosyası.', 'Dayanak yeniden kullanımı ve güncel sürüm bulguları.'),
        ("audit_mpyy_plan_component_consistency", 'Plan bileşeni kimliklerini denetle', 'Plan dosyası bileşenlerinin plan kimliklerini ve sürümlerini karşılaştırır.', 'Plan bileşeni kimlik listesi.', 'Kimlik ve sürüm tutarlılığı bulguları.'),
        ("audit_mpyy_approval_sheet_register", 'Onay paftalarını denetle', 'Belirtilen onay işaretlerini, tarihleri ve pafta kimliklerini denetler.', 'Onay paftası kayıt dosyası.', 'Onay kayıt bulguları.'),
        ("audit_mpyy_plan_note_decision_links", 'Plan notu bağlantılarını denetle', 'Not-karar referanslarını ve yinelenen kimlikleri inceler.', 'Plan notu/karar bağlantı listesi.', 'Bağlantısız, yinelenen ve metni eksik kayıt bulguları.'),
        ("audit_mpyy_version_chain", 'Plan sürüm geçmişini denetle', 'İçerik özetlerini, tam üst sürüm bağlantılarını ve tarih sırasını denetler.', 'Tarih sıralı sürüm zinciri listesi.', 'Kopuk zincir ve sürüm tarih sırası bulguları.'),
        ("evaluate_msp_action_monitoring", 'Strateji eylem izlemeyi denetle', 'Belirtilen eylem hedeflerini ve izleme dayanaklarını karşılaştırır.', 'Eylem izleme nesneleri ve değerlendirme tarihi.', 'Eylem ilerlemesi ve izleme bulguları.'),
    ),
    'Raporlar ve teslim': (
        ("export_planning_report", 'Plan özetini dışa aktar', 'Plan alanlarını ve arazi kullanım dengesini özetler.', 'Plan GeoPackage dosyası, rapor başlığı ve çıktı klasörü.', 'HTML/CSV plan özeti.'),
        ("generate_comprehensive_report", 'Plan raporu hazırla', 'Yazdırılabilir plan açıklaması ve arazi kullanım dengesi hazırlar.', 'Plan nesneleri, rapor başlığı ve hedef dosyalar.', 'Yazdırılabilir HTML raporu ve CSV arazi kullanım dengesi.'),
        ("generate_plan_notes", 'Plan notları hazırla', 'Seçilen plan bağlamı ve kodlarından plan notları üretir.', 'Plan nesneleri, plan başlığı ve ölçek.', 'İncelenmesi gereken üretilmiş plan notları.'),
        ("generate_pafta_grid", 'Pafta indeksi oluştur', 'Seçilen ölçek için pafta poligonları oluşturur.', 'Plan sınırı, pafta ölçeği ve adlandırma öneki.', 'Pafta indeks katmanı.'),
        ("generate_print_layout", 'Baskı düzeni oluştur', 'Plan ve idare bilgileriyle pafta baskı düzeni oluşturur.', 'Kâğıt boyutu, başlık, idare ve pafta bilgileri.', 'QGIS baskı düzeni.'),
        ("generate_zoning_certificate", 'İmar durumu belgesi hazırla', 'Parsel imar bilgilerini ve yapılaşma zarfını hazırlar.', 'Seçilen parsel/imar verisi ve belge bilgileri.', 'HTML ve Markdown imar durumu belgesi dosyaları.'),
        ("export_official_zoning_atlas", 'Parsel atlas paftasını dışa aktar', 'Parsel merkezli imar paftasını dışa aktarır.', 'Parsel, harita katmanları ve belge bilgileri.', 'Dışa aktarılmış atlas paftası.'),
        ("export_official_zoning_atlas_batch", 'Parsel atlasını toplu dışa aktar', 'Birden fazla parsel merkezli imar paftasını dışa aktarır.', 'Parsel nesneleri, harita katmanları ve toplu belge bilgileri.', 'Dışa aktarılmış atlas paftaları.'),
        ("package_for_qfield", 'Mobil saha paketi hazırla', 'Çalışma alanı verisini saha araştırması için paketler.', 'Çalışma alanı ve yerel hedef klasör.', 'Taşınabilir saha araştırması paketi.'),
        ("audit_mpyy_digital_delivery_package", 'Sayısal teslim içeriğini denetle', 'Dosyaları, kimlikleri ve belirtilen teslim tarih sırasını inceler.', 'Teslim paketi klasörü ve içerik listesi.', 'Sayısal teslim denetim bulguları.'),
        ("generate_mpyy_dossier_inventory", 'Plan dosyası envanteri oluştur', 'Alt klasörlerdeki dosya boyutlarını ve SHA-256 kimliklerini kaydeder.', 'Plan dosyası klasörü ve envanter çıktı dosyası.', 'Tekrarlanabilir dosya envanteri.'),
        ("consolidate_mpyy_audit_reports", 'Denetim raporlarını birleştir', 'Önceki denetim raporlarının kimliklerini doğrular ve raporları birleştirir.', 'Makine tarafından okunabilir denetim raporlarını içeren klasör.', 'Birleştirilmiş denetim paketi.'),
        ("audit_mpyy_gpkg_schema_profile", 'GeoPackage şema uygunluğunu denetle', 'Tabloları, alanları, geometri kaydını ve belirtilen profil kimliğini inceler.', 'GeoPackage dosyası ve idarenin sağladığı JSON şema profili.', 'Veriyi değiştirmeyen şema denetim raporu.'),
        ("import_mpyy_gpkg_schema_profile", 'Şema sözlüğünü içe aktar', 'İdarenin CSV sözlüğünü denetim profiline dönüştürür.', 'UTF-8 CSV sözlüğü ve açık JSON sütun eşlemesi.', 'Kaynak kimliklerini içeren sürümlü şema profili.'),
        ("audit_mpyy_schema_profile_identity", 'Şema profili kimliğini doğrula', 'Gömülü kimliği ve isteğe bağlı kaynak yeniden oluşturmasını veya bağımsız özeti denetler.', 'Profil JSON dosyası; isteğe bağlı kaynak CSV ve ayrı saklanan SHA-256 özeti.', 'İçerik kimliği raporu; düzenleyen kurumun özgünlüğü doğrulanmaz.'),
    ),
}


def normalized_search(text: str) -> str:
    text = text.casefold().replace("ı", "i")
    return "".join(char for char in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(char))


def build_catalog(algorithm_ids: Iterable[str], search_aliases: Mapping[str, str] | None = None) -> tuple[ToolDescription, ...]:
    descriptions = {row[0]: ToolDescription(row[0], row[1], category, *row[2:])
                    for category, rows in _GROUPS.items() for row in rows}
    tools = []
    for algorithm_id in algorithm_ids:
        tool = descriptions.get(algorithm_id) or ToolDescription(
            algorithm_id, algorithm_id.replace("_", " ").capitalize(), 'Diğer araçlar',
            'Bu aracı QGIS İşlem Araç Kutusu iletişim kutusunda yapılandırın.',
            'İşlem iletişim kutusunda girdi gereksinimlerini inceleyin.',
            'Çıktılar işlem iletişim kutusunda belirtilir.',
        )
        tools.append(replace(tool, keywords=(search_aliases or {}).get(algorithm_id, "")))
    tools.append(descriptions["create_workspace"])
    tools.append(ToolDescription(
        "style_and_forms", 'Katmanı biçimlendir ve formları düzenle', 'Çalışma alanı ve veri',
        'Vektör katmanına plan stili ve öznitelik formu uygular.',
        'Vektör katmanı, plan profili ve stil ailesi.',
        'Güncellenmiş katman stili ve öznitelik formları; önceki stil geri yüklenebilir.', False,
    ))
    tools.append(ToolDescription(
        "database_report", 'Etkin GeoPackage dosyasını incele', 'Çalışma alanı ve veri',
        'Veri sayımlarını ve çalışma alanı istatistiklerini okur.',
        'QGIS projesinde etkin GeoPackage vektör katmanı.',
        'İşlem Kaydı sekmesinde veritabanı durum özeti.', False,
    ))
    return tuple(sorted(tools, key=lambda tool: (tool.category, tool.title)))


def matches(tool: ToolDescription, query: str, category: str = "") -> bool:
    if category and tool.category != category:
        return False
    haystack = normalized_search(" ".join((tool.title, tool.category, tool.purpose, tool.inputs, tool.id, tool.keywords)))
    return all(word in haystack for word in normalized_search(query).split())
