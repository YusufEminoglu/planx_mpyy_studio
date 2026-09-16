"""Turkish presentation for Processing; parameter identities and enum indices stay stable."""
from qgis.core import QgsProcessingAlgorithm, QgsProcessingParameterEnum, QgsProcessingParameterFileDestination

from .catalog import build_catalog
from ..core.localization import field_alias

TOOLS = {tool.id: tool for tool in build_catalog(())}
from .catalog import _GROUPS, ToolDescription
TOOLS.update({row[0]: ToolDescription(row[0], row[1], category, *row[2:])
              for category, rows in _GROUPS.items() for row in rows})

PARAMETERS = {
    'AGRICULTURE_FOREST': 'Tarım ve orman dayanakları',
    'BICYCLE_SPEED_KMH': 'Varsayılan bisiklet hızı (km/sa)',
    'CHANGED_SPATIAL_DYNAMICS': 'Mekânsal dinamikler değişmiş',
    'COAST_INFRASTRUCTURE': 'Kıyı ve altyapı dayanakları',
    'DEFAULT_LEVELS': 'Varsayılan kat sayısı',
    'FACILITIES_A': 'Başlangıç senaryosu tesisleri',
    'FACILITIES_B': 'Önerilen senaryo tesisleri',
    'FLOOD_HYDROLOGY': 'Taşkın ve hidroloji dayanakları',
    'GEOLOGY_HAZARD': 'Jeoloji ve tehlike dayanakları',
    'IMPLEMENTATION_IMPOSSIBLE': 'Uygulama olanaksız',
    'KRS': 'Koordinat referans sistemi',
    'LAND_USE_CONTINUITY_DOCUMENTED': 'Arazi kullanım sürekliliği belgelenmiş',
    'MAIN_DECISIONS_AFFECTED': 'Ana kararlar etkilenmiş',
    'MAIN_STRATEGY_CHANGED': 'Ana strateji değişmiş',
    'MAX_HEIGHT': 'Azami yapı yüksekliği (m)',
    'MAX_ROOF_RISE': 'Azami çatı yükselmesi (m)',
    'NEED_NOT_MET': 'İhtiyaç karşılanmamış',
    'NETWORK_A': 'Başlangıç senaryosu ağı',
    'NETWORK_B': 'Önerilen senaryo ağı',
    'REGIONAL_INVESTMENT': 'Bölgesel yatırım değişikliği',
    'REGIONAL_LAND_USE_DEMAND': 'Bölgesel arazi kullanım talebi',
    'ROOF_SLOPE': 'Çatı eğimi',
    'SUBBASEMENT_HEIGHT': 'Subasman yüksekliği (m)',
    'TRANSFER_PENALTY_MIN': 'Ulaşım türü aktarma cezası (dakika)',
    'TRANSIT_SPEED_KMH': 'Varsayılan toplu taşıma hızı (km/sa)',
    'TRAVEL_TIME_FIELD': 'Yolculuk süresi alanı',
    'UPPER_PLAN_ALIGNMENT': 'Üst kademe plana uyum',
    'WALK_SPEED_KMH': 'Varsayılan yürüme hızı (km/sa)',
    'WATER_BASIN': 'Su havzası dayanakları',
    'POPULATION_REQUIREMENT': 'Nüfus gereksinimi',
    'MAX_TIME_MIN': 'Azami yolculuk süresi (dakika)',
    'GROUND_FLOOR_HEIGHT': 'Zemin kat yüksekliği',
    'TYPICAL_FLOOR_HEIGHT': 'Tipik kat yüksekliği',
    'PROTECTED_AREA': 'Koruma alanı',
    'CRS': 'Çalışma alanı koordinat sistemi', 'LEVELS': 'Plan kademeleri',
    'TABAKA_FIELD': 'Tabaka adı alanı', 'WORKSPACE': 'PlanGML çalışma alanı', 'OUTPUT_REPORT': 'Rapor dosyası (CSV)',
    'PLAN_LEVEL': 'Plan kademesi', 'TARGET_LEVEL': 'Hedef kademe', 'WRITTEN': 'Yazılan nesne sayısı', 'FINDINGS': 'Bulgu sayısı',
    'INPUT': 'Girdi katmanı', 'OUTPUT': 'Çıktı katmanı', 'DISTANCE': 'Çekme Mesafesi (m)',
    'FIELD': 'İşlev kodu alanı', 'PARCELS': 'Parsel poligonları', 'BUILDINGS': 'Yapı poligonları',
    'PLANS': 'Plan işlevi poligonları', 'SETBACK': 'Çekme Mesafesi (m)',
    'TARGET_LAYER': 'Hedef GeoPackage katmanı', 'INPUT_GPKG': 'Plan GeoPackage dosyası',
    'OUTPUT_DIR': 'Çıktı klasörü', 'PROJECT_TITLE': 'Proje başlığı', 'INCLUDE_OSM': 'OSM altlığını ekle',
    'SNAP_TOLERANCE': 'Yakalama toleransı (m)', 'MIN_AREA': 'Asgari poligon alanı (m²)',
    'AUTO_HEAL_GAPS': 'Küçük boşlukları otomatik onar', 'REPORT_TITLE': 'Rapor başlığı',
    'PLAN_LAYER': 'Plan poligonları', 'POPULATION': 'Çalışma nüfusu',
    'CURRENT_PLAN': 'Onaylı plan', 'REVISED_PLAN': 'Önerilen plan', 'SERVICE_RADIUS': 'Hizmet yarıçapı (m)',
    'CADASTRE_LAYER': 'Kadastro parsel poligonları', 'PUBLIC_LAYER': 'Kamu alanı poligonları (isteğe bağlı)',
    'MANUAL_PUBLIC_M2': 'Elle girilen kamu alanı (m²)', 'FORCED_DOP_RATIO': 'DOP oranını değiştir (isteğe bağlı)',
    'DEFAULT_KAKS': 'Varsayılan emsal (KAKS)',
    'DEFAULT_TAKS': 'Varsayılan taban alanı oranı (TAKS)', 'AVG_UNIT_M2': 'Ortalama konut alanı (m²)',
    'HOUSEHOLD_SIZE': 'Ortalama hane halkı büyüklüğü', 'PARCEL_LAYER': 'Parsel poligonları',
    'DEFAULT_NIZAM': 'Varsayılan yapı nizamı', 'DEFAULT_FLOORS': 'Varsayılan kat sayısı',
    'FRONT_SETBACK': 'Ön bahçe mesafesi (m)', 'SIDE_SETBACK': 'Yan bahçe mesafesi (m)',
    'MIN_CORE_M2': 'Asgari yapılaşabilir çekirdek alanı (m²)', 'SCALE': 'Pafta ölçeği',
    'PREFIX': 'Pafta adı öneki', 'PLAN_TITLE': 'Plan başlığı', 'PLAN_SCALE': 'Plan ölçeği',
    'INCLUDE_GEOLOGY': 'Jeolojik hükümleri ekle', 'INCLUDE_ARTICLE18': '18. madde hükümlerini ekle',
    'OUTPUT_MD': 'Markdown çıktı dosyası', 'OUTPUT_HTML': 'HTML çıktı dosyası', 'OUTPUT_FOLDER': 'Çıktı klasörü',
    'CHAMFER_DISTANCE': 'Pah mesafesi (m)', 'MIN_ANGLE': 'Asgari köşe açısı (derece)',
    'MAX_ANGLE': 'Azami köşe açısı (derece)', 'LAYOUT_NAME': 'Düzen adı', 'PAPER_SIZE': 'Kâğıt boyutu',
    'MUNICIPALITY': 'Belediye / idare', 'PAFTA_NO': 'Pafta kimliği',
    'AREA_PER_CAR': 'Araç başına otopark alanı (m²)', 'REF_YEAR': 'Referans yılı',
    'ILCE': 'İlçe', 'MAHALLE': 'Mahalle', 'AREA_PER_PERSON': 'Kişi başına sığınak alanı (m²)',
    'CADASTRE': 'Kadastro parselleri', 'ZONING_PARCELS': 'İmar parselleri', 'DOP_RATIO': 'DOP Kesinti Oranı',
    'CONTRACTOR_RATIO': 'Müteahhit Payı', 'UNIT_COST': 'Metrekare başına inşaat maliyeti',
    'UNIT_PRICE': 'Metrekare başına satış fiyatı', 'ROADS': 'Komşu yollar (isteğe bağlı)', 'NIZAM': 'Yapılaşma Nizamı',
    'LAND_USE': 'Arazi kullanım sınıfı', 'FLOORS': 'Kat Sayısı', 'TARGET_FRONTAGE': 'Hedef parsel cephesi (m)',
    'MAX_PARCELS': 'Kaynak parsel başına azami bölünme sayısı', 'DOCUMENT_NUMBER': 'Belge numarası',
    'PAGE_SIZE': 'Sayfa boyutu ve yönü', 'BUFFER': 'Harita tampon mesafesi (m)', 'DPI': 'Dışa aktarma çözünürlüğü (dpi)',
    'DOCUMENT_PREFIX': 'Belge numarası öneki', 'SELECTED_ONLY': 'Yalnızca seçilen parselleri dışa aktar',
    'OUTPUT_DIRECTORY': 'Çıktı klasörü', 'INCLUDE_ROOF': 'Çatıları ekle', 'PROFILE': 'Kural / şema profili',
    'CUSTOM_PROFILE_FILE': 'Özel profil kayıt dosyası (isteğe bağlı)', 'CUSTOM_PROFILE_CODE': 'Özel profil kodu',
    'BASE_WORKSPACE': 'Başlangıç GeoPackage dosyası', 'INCOMING_WORKSPACE': 'Gelen GeoPackage dosyası',
    'CONFLICT_STRATEGY': 'Çakışma çözüm politikası', 'OUTPUT_REPORT': 'JSON rapor dosyası',
    'MAP_SCALE': 'Belirtilen harita ölçeği paydası', 'PARENT': 'Üst kademe plan katmanı',
    'PARENT_LEVEL': 'Üst plan kademesi', 'CHILD': 'Alt kademe plan katmanı', 'CHILD_LEVEL': 'Alt plan kademesi',
    'MINIMUM_COVERAGE': 'Asgari kapsama oranı', 'MANIFEST': 'JSON içerik listesi dosyası',
    'REVIEW_RATIO': 'İnceleme eşik oranı', 'EVALUATION_DATE': 'Değerlendirme tarihi (YYYY-AA-GG)',
    'CURRENT': 'Mevcut plan katmanı', 'PROPOSED': 'Önerilen plan katmanı',
    'RATIONALE_DOCUMENTED': 'Revizyon gerekçesi belgelenmiş',
    'INFRASTRUCTURE_IMPACT_DOCUMENTED': 'Altyapı etkileri belgelenmiş',
    'NETWORK': 'Çizgi ağ katmanı', 'CENTERS': 'Etkinlik merkezleri (isteğe bağlı)',
    'CENTER_ACCESS_DISTANCE': 'Merkez erişim mesafesi (m)', 'VERIFY_LOCAL_FILES': 'Yerel dayanak dosyalarını doğrula',
    'REGISTER': 'JSON kayıt dosyası', 'DEMAND': 'Talep nokta katmanı', 'FACILITIES': 'Tesis nokta katmanı',
    'MAX_ROUTE_DISTANCE': 'Azami güzergâh mesafesi (m)', 'MAX_SNAP_DISTANCE': 'Azami yakalama mesafesi (m)',
    'REFERENCE': 'Referans plan katmanı', 'REFERENCE_CODE_FIELD': 'Referans karar kodu alanı',
    'ADJACENT': 'Komşu plan katmanı', 'ADJACENT_CODE_FIELD': 'Komşu karar kodu alanı',
    'TOLERANCE': 'Sınır toleransı (m)', 'DECISIONS': 'Plan karar poligonları',
    'BOUNDARY': 'Plan sınırı (isteğe bağlı)', 'AREA_TOLERANCE': 'Alan toleransı (m²)', 'GAPS': 'Boşluk poligonları',
    'DEMAND_SERVICE_FIELD': 'Talep hizmet türü alanı', 'FACILITY_TYPE_FIELD': 'Tesis türü alanı',
    'CODE_FIELD': 'Gösterim kodu alanı', 'PLAN_LEVEL': 'Plan kademesi', 'ADJACENCY_TOLERANCE': 'Komşuluk toleransı (m)',
    'INPUT_DIRECTORY': 'Girdi klasörü', 'PURPOSE': 'Plan amacı', 'AS_OF_DATE': 'Değerlendirme tarihi (YYYY-AA-GG)',
    'GEOPACKAGE': 'GeoPackage dosyası', 'OUTPUT_PROFILE': 'JSON şema profili çıktısı',
    'DICTIONARY': 'Kaynak CSV sözlüğü (isteğe bağlı)', 'EXPECTED_SHA256': 'Bağımsız SHA-256 özeti (isteğe bağlı)',
    'LEVELS_FIELD': 'Kat sayısı alanı (isteğe bağlı)', 'BLOCKS': 'Çalışma ada poligonları (isteğe bağlı)',
    'ORIENTATION_BINS': 'Yönlenme histogramı sınıf sayısı', 'SCENARIO_A': 'Başlangıç senaryosu JSON dosyası',
    'SCENARIO_B': 'Önerilen senaryo JSON dosyası', 'VALUE_FIELD': 'Erişilebilirlik değeri alanı',
    'WEIGHT_FIELD': 'Nüfus / ağırlık alanı (isteğe bağlı)', 'USE_THRESHOLD': 'Belirtilen erişim eşiğini uygula',
    'THRESHOLD': 'Erişim eşiği', 'HIGHER_IS_BETTER': 'Yüksek değerler daha iyi erişimi gösterir',
    'OUTPUT_UNITS': 'Çalışma birimi başına eşitlik sonuçları', 'OUTPUT_SUMMARY': 'Eşitlik özeti tablosu',
    'MODE_FIELD': 'Ulaşım türü alanı', 'SPEED_FIELD': 'Yolculuk hızı alanı', 'TIME_FIELD': 'Yolculuk süresi alanı',
    'DIRECTION_FIELD': 'Yolculuk yönü alanı', 'DEFAULT_SPEED': 'Varsayılan yolculuk hızı',
    'CSV_DICTIONARY': 'CSV veri sözlüğü', 'MAPPING': 'JSON sütun eşleme dosyası',
    'SOURCE_INSTITUTION': 'Kaynak kurum', 'SOURCE_REFERENCE': 'Kaynak referansı', 'PROFILE_VERSION': 'Profil sürümü',
}

ENUM_OPTIONS = {
    'TARGET_LEVEL': ['Nazım imar planı (NİP)', 'Çevre düzeni planı (ÇDP)'],
    'PLAN_LEVEL': ['Dosyadan oku', 'Uygulama imar planı (UİP)', 'Nazım imar planı (NİP)', 'Çevre düzeni planı (ÇDP)'],
    'LEVELS': ['Tüm kademeler (MSP, ÇDP, NİP, UİP)', 'Yalnızca uygulama imar planı (UİP 1:1.000)',
               'Yalnızca nazım imar planı (NİP 1:5.000)', 'Yalnızca çevre düzeni planı (ÇDP 1:50.000 - 1:100.000)',
               'Yalnızca mekânsal strateji planı (MSP 1:250.000 - 1:500.000)', 'İmar planları (NİP + UİP)'],
    'DEFAULT_NIZAM': ['Ayrık', 'Bitişik', 'İkiz', 'Blok', 'Serbest nizam'],
    'NIZAM': ['Ayrık', 'Bitişik', 'Blok'], 'LAND_USE': ['Konut / ticaret', 'Sanayi'],
    'PAGE_SIZE': ['A3 yatay', 'A4 dikey'],
    'CONFLICT_STRATEGY': ['Elle inceleme', 'Gelen sürümü tercih et', 'Daha yeni tarihli kaydı tercih et'],
    'PARENT_LEVEL': ['MSP', 'CDP', 'NIP'], 'CHILD_LEVEL': ['CDP', 'NIP', 'UIP'],
    'PLAN_LEVEL': ['MSP', 'CDP', 'NIP', 'UIP'],
    'SCALE': ['1:1.000 (500 m × 500 m - UİP)', '1:2.000 (1.000 m × 1.000 m)', '1:5.000 (2.500 m × 2.000 m - NİP)'],
    'PURPOSE': ['Yeni plan', 'Revizyon', 'İlave plan', 'Plan değişikliği'],
}


def tool_text(algorithm, attribute):
    tool = TOOLS[algorithm.name()]
    if attribute == 'help':
        return f'{tool.purpose}\n\nBaşlamadan önce: {tool.inputs}\n\nÇıktılar: {tool.output}\n\nPlan kararlarını benimsemeden önce üretilen bulguları inceleyin.'
    return getattr(tool, attribute)


class LocalizedProcessingAlgorithm(QgsProcessingAlgorithm):
    def addOutput(self, output):
        output.setDescription(PARAMETERS.get(output.name(), field_alias(output.name())))
        return super().addOutput(output)

    def parameterAsSink(self, parameters, name, context, fields, *args, **kwargs):
        from ..core.localization import localized_fields
        return super().parameterAsSink(parameters, name, context, localized_fields(fields), *args, **kwargs)

    def addParameter(self, parameter, *args, **kwargs):
        name = parameter.name()
        prefix = ''
        for scenario in ('BASELINE_', 'PROPOSED_'):
            if name.startswith(scenario):
                prefix = ('Başlangıç' if scenario == 'BASELINE_' else 'Önerilen') + ' - '
                name = name[len(scenario):]
                break
        parameter.setDescription(prefix + PARAMETERS.get(name, field_alias(name)))
        if name == 'OUTPUT' and isinstance(parameter, QgsProcessingParameterFileDestination):
            parameter.setDescription('GeoPackage çıktı dosyası' if '*.gpkg' in parameter.fileFilter() else 'Belge çıktı dosyası')
        if isinstance(parameter, QgsProcessingParameterEnum) and name in ENUM_OPTIONS:
            options = ENUM_OPTIONS[name]
            if len(options) != len(parameter.options()):
                raise ValueError('Türkçe seçenek etiketleri özgün sıralamayı korumalıdır: ' + name)
            parameter.setOptions(options)
        return super().addParameter(parameter, *args, **kwargs)
