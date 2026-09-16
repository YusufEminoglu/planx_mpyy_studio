"""PlanGML-first MPYY workspace schema contract with strict plan level isolation."""

SCHEMA_VERSION = 5

# Official 4 planning levels in Turkish spatial planning hierarchy (MPYY)
PLAN_LEVELS = (
    ("MSP", 'Mekânsal Strateji Planı', "1"),
    ("CDP", 'Çevre Düzeni Planı', "2"),
    ("NIP", 'Nazım İmar Planı', "3"),
    ("UIP", 'Uygulama İmar Planı', "4"),
)
PLAN_LEVEL_CODES = {x[0] for x in PLAN_LEVELS}

# Common planning metadata fields present on all plan hierarchy layers
COMMON_FIELDS = {
    "global_id": "TEXT",
    "plan_id": "TEXT DEFAULT 'PLAN-UNSET'",
    "plan_kademesi": "TEXT",
    "catalog_id": "TEXT",
    "ust_grup_kodu": "TEXT",
    "ust_grup_adi": "TEXT",
    "alt_grup_kodu": "TEXT",
    "alt_grup_adi": "TEXT",
    "detay_grup_kodu": "TEXT",
    "detay_grup_adi": "TEXT",
    "fonksiyon_kodu": "TEXT",
    "fonksiyon_adi": "TEXT",
    "lejant_kodu": "TEXT",
    "gosterim_adi": "TEXT",
    "aciklama": "TEXT",
    "plan_asamasi": "TEXT DEFAULT 'TASLAK' CHECK(plan_asamasi IN ('TASLAK','ONERI','ONAYLI','IPTAL'))",
    "olusturan": "TEXT",
    "olusturma_tarihi": "TEXT DEFAULT ''",
    "guncelleyen": "TEXT",
    "guncelleme_tarihi": "TEXT DEFAULT ''",
}

# -------------------------------------------------------------------------
# Level-specific fields (STRICT HIERARCHY ISOLATION)
# -------------------------------------------------------------------------

# 1. MSP (Mekânsal Strateji Planı - 1/250.000 - 1/500.000)
# Macro strategy, national/regional corridors and systems. NO parcel zoning.
MSP_AREA_FIELDS = {
    "alan_ha": "REAL CHECK(alan_ha >= 0)",
    "strateji_bolgesi": "TEXT",
    "oncelik_durumu": "TEXT",
}
MSP_LINE_FIELDS = {
    "hat_turu": "TEXT",
    "koridor_kademesi": "TEXT",
    "uzunluk_km": "REAL CHECK(uzunluk_km >= 0)",
}
MSP_NOTATION_FIELDS = {
    "odak_turu": "TEXT",
    "kademelenme": "TEXT",
    "etiket": "TEXT",
}

# 2. CDP (Çevre Düzeni Planı - 1/50.000 - 1/100.000)
# Sub-regional environmental and territorial zones. NO building heights/setbacks.
CDP_AREA_FIELDS = {
    "alan_ha": "REAL CHECK(alan_ha >= 0)",
    "bolge_turu": "TEXT",
    "alt_bolge_kodu": "TEXT",
    "ozel_hukum_var_mi": "TEXT CHECK(ozel_hukum_var_mi IN ('EVET','HAYIR'))",
}
CDP_LINE_FIELDS = {
    "koridor_turu": "TEXT",
    "kusak_genisligi_m": "REAL CHECK(kusak_genisligi_m >= 0)",
    "uzunluk_km": "REAL CHECK(uzunluk_km >= 0)",
}
CDP_NOTATION_FIELDS = {
    "odak_adi": "TEXT",
    "merkez_kademesi": "TEXT",
    "etiket": "TEXT",
}

# 3. NIP (Nazım İmar Planı - 1/5.000 - 1/25.000)
# Master plan, gross density (kişi/ha), general land uses. NO parcel TAKS/KAKS/setbacks.
NIP_AREA_FIELDS = {
    "alan_m2": "REAL CHECK(alan_m2 >= 0)",
    "brut_yogunluk_kisi_ha": "REAL CHECK(brut_yogunluk_kisi_ha >= 0)",
    "yogunluk_kademesi": "TEXT CHECK(yogunluk_kademesi IN ('DÜŞÜK','ORTA','YÜKSEK','ÇOK YÜKSEK','BELİRSİZ'))",
    "etap_no": "TEXT",
    "donati_kisi_basina_m2": "REAL CHECK(donati_kisi_basina_m2 >= 0)",
}
NIP_LINE_FIELDS = {
    "yol_kademesi": "TEXT",
    "ongorulen_genislik_m": "REAL CHECK(ongorulen_genislik_m >= 0)",
    "uzunluk_m": "REAL CHECK(uzunluk_m >= 0)",
}
NIP_NOTATION_FIELDS = {
    "merkez_turu": "TEXT",
    "etiket": "TEXT",
}

# 4. UIP (Uygulama İmar Planı - 1/1.000)
# Parcel-level building rights, setbacks, exact dimensions matching official MpyyUipDb.
UIP_AREA_FIELDS = {
    "id1": "TEXT",
    "ustkonugrup": "TEXT",
    "id2": "TEXT",
    "uipfonksiyon": "TEXT",
    "nizam": "TEXT CHECK(nizam IN ('AYRIK','BİTİŞİK','BLOK','SERBEST','İKİZ','A','B','BL'))",
    "katadedi": "TEXT",
    "taks": "TEXT",
    "kaks": "TEXT",
    "emsal": "TEXT",
    "yencok": "TEXT",
    "onbahce": "TEXT",
    "yanbahce": "TEXT",
    "arkabahce": "TEXT",
    "id3": "TEXT",
    "uip_tabaka": "TEXT",
    "yapiYaklasmaDurumu": "TEXT CHECK(yapiYaklasmaDurumu IN ('VAR','YOK','BELİRSİZ'))",
    "yapiYaklasmaMesafesi": "INTEGER CHECK(yapiYaklasmaMesafesi >= 0)",
    "AlanM2": "REAL CHECK(AlanM2 >= 0)",
    "Kullanici": "TEXT",
    "Tarihilk": "TEXT",
    "Tarihson": "TEXT",
}
UIP_LINE_FIELDS = {
    "uipfonksiyon": "TEXT",
    "yolTipi": "TEXT",
    "yolGenislik": "REAL CHECK(yolGenislik >= 0)",
    "cepheKalinlik": "REAL CHECK(cepheKalinlik >= 0)",
    "kaldirimGenislik": "REAL CHECK(kaldirimGenislik >= 0)",
    "refujGenislik": "REAL CHECK(refujGenislik >= 0)",
    "SolSeritSayisi": "INTEGER CHECK(SolSeritSayisi >= 0)",
    "SagSeritSayisi": "INTEGER CHECK(SagSeritSayisi >= 0)",
    "yolGenislik2": "REAL CHECK(yolGenislik2 >= 0)",
    "Uzunluk(m)": "REAL CHECK(\"Uzunluk(m)\" >= 0)",
    "Kullanici": "TEXT",
    "Tarihilk": "TEXT",
    "Tarihson": "TEXT",
}
UIP_NOTATION_FIELDS = {
    "ustkonugrup": "TEXT",
    "uipfonksiyon": "TEXT",
    "sembolTipi": "TEXT",
    "yolGenislik": "TEXT",
    "yolTipi": "TEXT",
    "nizam": "TEXT",
    "katadedi": "TEXT",
    "onbahce": "TEXT",
    "yanbahce": "TEXT",
    "taks": "TEXT",
    "kaks": "TEXT",
    "emsal": "TEXT",
    "yencok": "TEXT",
}

# -------------------------------------------------------------------------
# Arazi Kullanımı (Land Use & Field Survey) Fields matching bergama_arazi_anket
# -------------------------------------------------------------------------
COMMON_SURVEY_FIELDS = {
    "aciklama": "TEXT",
    "fotograf": "TEXT",
    "global_id": "TEXT",
    "olusturan": "TEXT",
    "duzenleyen": "TEXT",
    "tarih": "TEXT",
    "QC": "TEXT",
}

# Non-TUCBS Urban Planning Field Survey Classes (Mevcut Arazi Kullanımı Sözlüğü)
LAND_USE_CLASSES = [
    # Konut Alanları
    ("KONUT", 'Konut (Müstakil / Apartman)', 'Konut', "#FDD835", 'Müstakil veya apartman tipi konut kullanımı'),
    ("KONUT_TICARET", 'Konut + Ticaret (Karma)', 'Konut', "#FB8C00", 'Zemin kat ticaret, üst katlar konut karma kullanım'),
    ("TOPLU_KONUT", 'Toplu Konut / Site', 'Konut', "#FBC02D", 'Site içi çoklu blok konut yerleşimi'),
    # Ticaret ve Hizmet
    ("TICARET", 'Ticaret / Çarşı', 'Ticaret ve Hizmet', "#E53935", 'Dükkan, mağaza, perakende satış birimleri'),
    ("OFIS_BURO", 'Ofis / Büro / İşhanı', 'Ticaret ve Hizmet', "#D32F2F", 'Hizmet sektörü, büro ve iş merkezleri'),
    ("AVM", 'Alışveriş Merkezi', 'Ticaret ve Hizmet', "#C2185B", 'Büyük ölçekli kapalı alışveriş merkezi'),
    ("TURIZM_TESISI", 'Turizm Tesisi / Otel', 'Ticaret ve Hizmet', "#00ACC1", 'Otel, motel, pansiyon ve konaklama tesisleri'),
    ("YEME_ICME", 'Yeme-İçme (Kafe / Restoran)', 'Ticaret ve Hizmet', "#FF7043", 'Lokanta, pastane, kafe vb. günübirlik tesisler'),
    ("AKARYAKIT", 'Akaryakıt / Servis İstasyonu', 'Ticaret ve Hizmet', "#E64A19", 'Akaryakıt ve LPG ikmal istasyonu'),
    ("OTOPARK", 'Otopark (Açık / Katlı)', 'Ticaret ve Hizmet', "#78909C", 'Açık otopark veya katlı otopark binası'),
    # Sanayi ve Üretim
    ("SANAYI", 'Sanayi / Fabrika', 'Sanayi ve Depolama', "#8E24AA", 'İmalat sanayii ve fabrika binaları'),
    ("KSS", 'İmalathane / KSS / Atölye', 'Sanayi ve Depolama', "#BA68C8", 'Küçük sanayi sitesi, oto tamir, marangoz vb. atölyeler'),
    ("DEPOLAMA", 'Depolama / Lojistik', 'Sanayi ve Depolama', "#5E35B1", 'Antrepo, depo ve lojistik tesisleri'),
    ("TOPTAN_TICARET", 'Toptan Ticaret / Hal', 'Sanayi ve Depolama', "#7E57C2", 'Toptancı hali, inşaat malzemeleri vb.'),
    # Kamu ve İdari Tesisler
    ("RESMI_KURUM", 'Resmî Kurum / İdari Tesis', 'Kamu ve İdari', "#546E7A", 'Belediye, kaymakamlık, kamu kurum binaları'),
    ("GUVENLIK", 'Emniyet / Polis / İtfaiye', 'Kamu ve İdari', "#455A64", 'Polis merkezi, jandarma karakolu, itfaiye'),
    # Sosyal ve Kültürel Donatılar
    ("EGITIM", 'Eğitim (Okul)', 'Sosyal Donatı', "#2196F3", 'Anaokulu, ilkokul, ortaokul, lise'),
    ("YUKSEK_OGRETIM", 'Yükseköğretim / Üniversite', 'Sosyal Donatı', "#1976D2", 'Fakülte, yüksekokul, enstitü binaları'),
    ("SAGLIK", 'Sağlık Tesisi (ASM / Hastane)', 'Sosyal Donatı', "#26A69A", 'Aile sağlığı merkezi, poliklinik, hastane'),
    ("DINI_TESIS", 'Dini Tesis (Cami / Mescit)', 'Sosyal Donatı', "#5C6BC0", 'Cami, mescit, ibadethane'),
    ("SOSYO_KULTUREL_TESIS", 'Sosyo-Kültürel Tesis', 'Sosyal Donatı', "#EC407A", 'Kültür merkezi, kütüphane, müze'),
    ("SPOR_ALANI", 'Spor Tesisi / Saha', 'Sosyal Donatı', "#00897B", 'Kapalı spor salonu, semt sahası, stadyum'),
    # Açık ve Yeşil Alanlar
    ("PARK", 'Park ve Yeşil Alan', 'Açık ve Yeşil Alan', "#4CAF50", 'Aktif yeşil alan, dinlenme parkı'),
    ("COCUK_OYUN", 'Çocuk Oyun Alanı', 'Açık ve Yeşil Alan', "#66BB6A", 'Çocuk parkı ve oyun alanları'),
    ("MEYDAN", 'Meydan / Yaya Bölgesi', 'Açık ve Yeşil Alan', "#81C784", 'Kentsel meydan ve yayalaştırılmış alanlar'),
    ("REKREASYON", 'Rekreasyon Alanı', 'Açık ve Yeşil Alan', "#388E3C", 'Günübirlik eğlence, piknik ve rekreasyon'),
    ("MEZARLIK", 'Mezarlık', 'Açık ve Yeşil Alan', "#2E7D32", 'Şehir ve mahalle mezarlıkları'),
    # Tarım ve Kırsal
    ("TARIM_EKILI", 'Tarım Alanı (Ekili)', 'Tarım ve Kırsal', "#CDDC39", 'Tarla, buğday, sebze tarımı'),
    ("ZEYTINLIK", 'Zeytinlik / Bağ / Bahçe', 'Tarım ve Kırsal', "#9E9D24", 'Meyve bahçesi, zeytinlik, bağ'),
    ("SERA", 'Sera Alanı', 'Tarım ve Kırsal', "#AFB42B", 'Örtü altı tarım / sera'),
    ("HAYVANCILIK", 'Tarımsal Tesis (Ahır/Depo)', 'Tarım ve Kırsal', "#827717", 'Besi çiftliği, ahır, ağıl, tarımsal depo'),
    # Teknik Altyapı
    ("TEKNIK_ALTYAPI", 'Teknik Altyapı', 'Teknik Altyapı', "#6D4C41", 'Trafo, su deposu, arıtma tesisi'),
    ("TRAFO", 'Trafo Merkezi', 'Teknik Altyapı', "#5D4037", 'İndirici merkez ve dağıtım trafosu'),
    # Boş, İnşaat ve Diğer
    ("BOS_PARSEL", 'Boş Parsel', 'Boş ve Diğer', "#EEEEEE", 'Üzerinde yapı bulunmayan imar parseli veya ham arazi'),
    ("INSAAT", 'İnşaat Halinde (Şantiye)', 'Boş ve Diğer', "#FFA726", 'Yapımı devam eden kaba veya ince inşaat'),
    ("HARABE", 'Harabe / Yıkıntı / Metruk', 'Boş ve Diğer', "#757575", 'Kullanılamaz durumda, yıkık veya terk edilmiş yapı'),
    ("ASKERI_ALAN", 'Askeri Alan / Güvenlik', 'Boş ve Diğer', "#556B2F", 'Askeri kışla, garnizon veya güvenlik sahası'),
    # Doğal, Çevre ve Maden
    ("ORMAN", 'Orman / Koruluk Alan', 'Açık ve Yeşil Alan', "#1B5E20", 'Doğal orman veya koruma altındaki ağaçlık alan'),
    ("SU_YUZEYI", 'Su Yüzeyi / Dere / Gölet', 'Su ve Çevre', "#0288D1", 'Dere, nehir, göl, baraj veya su kanalı'),
    ("MADEN_OCAK", 'Maden / Taş Ocağı', 'Sanayi ve Depolama', "#4E342E", 'Maden işletmesi, kum/çakıl veya taş ocağı'),
    # Ulaşım ve Lojistik
    ("TERMINAL", 'Otogar / Şehirlerarası Otobüs Terminali', 'Ulaşım ve Lojistik', "#FF5722", 'Şehirlerarası veya ilçe otobüs terminali'),
    ("DEMIRYOLU_ISTASYON", 'Demiryolu İstasyonu / Gar / Metro', 'Ulaşım ve Lojistik', "#795548", 'TCDD tren garı, banliyö veya metro istasyonu'),
    ("LIMAN_ISKELE", 'Liman / İskele / Yat Limanı / Marina', 'Ulaşım ve Lojistik', "#00838F", 'Yolcu/yük iskelesi, balıkçı barınağı, marina'),
    ("HAVAALANI", 'Havalimanı / Hava Meydanı / Heliport', 'Ulaşım ve Lojistik', "#455A64", 'Havaalanı pisti, terminali veya helikopter iniş pisti'),
    # Sosyal ve İdari Ekler
    ("YURT_BAKIMEVI", 'Öğrenci Yurdu / Huzurevi / Bakımevi', 'Sosyal Donatı', "#5C6BC0", 'Devlet veya özel öğrenci yurdu, huzurevi, bakım merkezi'),
    ("ADLIYE_CEZAEVI", 'Adliye / Ceza İnfaz Kurumu', 'Kamu ve İdari', "#37474F", 'Adalet sarayı, adliye binası veya ceza infaz kurumu'),
    # Doğal ve Kırsal Alanlar
    ("MERA_OTLAK", 'Mera / Otlak / Çayır', 'Tarım ve Kırsal', "#8D6E63", 'Köy tüzel kişiliği veya kamu mülkiyetindeki mera, otlak alanı'),
    ("SAZLIK_SULAK", 'Sulak Alan / Sazlık / Bataklık', 'Su ve Çevre', "#0097A7", 'Doğal sulak alan, sazlık, lagün veya bataklık'),
    ("KIYI_KUMSAL", 'Kıyı Kenar / Kumsal / Plaj Alanı', 'Açık ve Yeşil Alan', "#FFE082", 'Kıyı dolgu alanı, plaj veya doğal kumsal sahil bandı'),
    # Konut Ekleri
    ("LOJMAN", 'Kamu / Kurum Lojmanı', 'Konut', "#FFF59D", 'Devlet dairesi, TCDD veya kamu personeli lojmanları'),
    ("GECEKONDU", 'Gecekondu / İmar Dışı Yerleşim', 'Konut', "#DCE775", 'İmarsız, plansız kentsel konut dokusu'),
    ("KENTSEL_DONUSUM", 'Kentsel Dönüşüm / Riskli Yapı Alanı', 'Konut', "#E6EE9C", 'Kentsel dönüşüm, yenileme veya tasfiye sahası'),
    # Ticaret ve Hizmet Ekleri
    ("BANKA_FINANS", 'Banka / Finans Kurumu', 'Ticaret ve Hizmet', "#1E88E5", 'Banka şubesi, borsa, sigorta ve finans merkezleri'),
    ("PAZAR_YERI", 'Pazar Yeri (Açık / Kapalı)', 'Ticaret ve Hizmet', "#FF8A65", 'Semt pazarı, üretici ve kapalı pazar yerleri'),
    # Sanayi ve Üretim Ekleri
    ("ENERJI_URETIM", 'Enerji Üretim ve Santral Alanı', 'Sanayi ve Depolama', "#F4511E", 'GES, RES, santral ve enerji üretim sahası'),
    # Kamu ve İdari Ekleri
    ("BELEDIYE_HIZMET", 'Belediye Hizmet Alanı (BHA)', 'Kamu ve İdari', "#00838F", 'Belediye şantiyesi, atölyesi, fen işleri ve ek hizmet birimleri'),
    # Sosyal Donatı Ekleri
    ("KRES_GUNDUZ_BAKIM", 'Kreş / Gündüz Bakımevi', 'Sosyal Donatı', "#64B5F6", 'Okul öncesi gündüz kreşi ve bakım merkezi'),
    # Açık ve Yeşil Alan Ekleri
    ("BOTANIK_HAYVANAT_BAHCESI", 'Botanik Bahçesi / Hayvanat Bahçesi', 'Açık ve Yeşil Alan', "#43A047", 'Botanik parkı, arboretum veya hayvanat bahçesi'),
]

SAHA_CATI_KODLARI = [
    ("KİREMİT", 'Kiremit Kaplama / Eğimli Çatı'),
    ("TERAS", 'Düz Teras Çatı'),
    ("SAC_PANEL", 'Sac / Sandviç Panel / Trapez Sac'),
    ("SUNDURMA", 'Sundurma / Açık Çatı'),
    ("ŞINGIL", 'Şıngıl / Membran Kaplama'),
    ("ÇATISIZ", 'Çatısız / Tamamlanmamış'),
]

SAHA_ISITMA_KODLARI = [
    ("DOĞALGAZ_KOMBİ", 'Bireysel Doğalgaz Kombi'),
    ("MERKEZİ", 'Merkezi Isıtma (Kalorifer / Jeotermal)'),
    ("SOBA", 'Bireysel Soba (Kömür / Odun)'),
    ("KLİMA_ISI_POMPASI", 'Klima / Isı Pompası / Elektrikli'),
    ("YOK", 'Isıtma Sistemi Yok'),
]

SAHA_HASAR_KODLARI = [
    ("HASARSIZ", 'Hasarsız / Yapısal Kusur Yok'),
    ("AZ_HASARLI", 'Az Hasarlı / Çatlak ve Sıva Dökülmesi'),
    ("ORTA_HASARLI", 'Orta Hasarlı / Esaslı Onarım Gerektirir'),
    ("AĞIR_HASARLI", 'Ağır Hasarlı / Yapısal Taşıyıcı Hasarı'),
    ("ACİL_YIKILACAK", 'Acil Yıktırılacak / Can Güvenliği Riski'),
]

SAHA_NIZAM_KODLARI = [
    ("AYRIK", 'Ayrık Nizam'),
    ("BİTİŞİK", 'Bitişik Nizam'),
    ("BLOK", 'Blok Nizam'),
    ("SERBEST", 'Serbest Nizam'),
    ("İKİZ", 'İkiz Nizam'),
]

SAHA_PARSEL_DURUM_KODLARI = [
    ("DOLU", 'Dolu (Üzerinde Yapı Var)'),
    ("BOŞ", 'Boş Parsel (Yapısız)'),
    ("İNŞAAT", 'İnşaat Halinde'),
    ("METRUK", 'Metruk / Terk Edilmiş'),
    ("TESCİL_HARİCİ", 'Tescil Harici / Yol / Terkin'),
]

SAHA_YAPI_CINS_KODLARI = [
    ("BETONARME", 'Betonarme karkas'),
    ("YIĞMA", 'Yığma kâgir / tuğla'),
    ("ÇELİK", 'Çelik konstrüksiyon'),
    ("PREFABRİK", 'Prefabrik / modüler yapı'),
    ("AHŞAP", 'Geleneksel ahşap karkas'),
    ("KERPİÇ", 'Geleneksel kerpiç'),
    ("KARGİR_TAS", 'Kâgir / taş yapı'),
    ("GEÇİCİ_BARAKA", 'Geçici / baraka / sundurma'),
]


SAHA_PARSEL_FIELDS = dict(
    COMMON_SURVEY_FIELDS,
    IL="TEXT",
    ILCE="TEXT",
    MAHALLE="TEXT",
    ADA="TEXT",
    PARSEL="TEXT",
    TAPU_ALANI="TEXT",
    NITELIK="TEXT",
    MEVKII="TEXT",
    ZEMIN_TIP="TEXT",
    MULKIYET_TURU="TEXT DEFAULT 'ÖZEL'",
    KORUMA_DURUMU="TEXT DEFAULT 'YOK'",
    P_KULLANIM_ANA="TEXT",
    P_FONK="TEXT",
    P_NIZAM="TEXT",
    P_KAT="INTEGER",
    P_CEKME="INTEGER",
    P_CEPHE="INTEGER",
    P_DERINLIK="REAL",
    P_YOL_GEN="INTEGER",
    P_TAKS="REAL",
    P_KAKS="REAL",
    P_YAPI_ADET="INTEGER DEFAULT 1",
    P_BAGIMSIZ_BOLUM="INTEGER",
    P_NUFUS="INTEGER",
    P_OTOPARK="INTEGER",
    P_DURUM="TEXT DEFAULT 'DOLU'",
    alan_m2="REAL CHECK(alan_m2 >= 0)",
)

SAHA_YAPI_FIELDS = dict(
    COMMON_SURVEY_FIELDS,
    ADA="TEXT",
    PARSEL="TEXT",
    KAPI_NO="TEXT",
    B_FONK_ANA="TEXT",
    B_FONK="TEXT",
    B_ZEMIN_FONK="TEXT",
    B_UST_FONK="TEXT",
    B_KAT="INTEGER",
    B_BODRUM="INTEGER DEFAULT 0",
    B_YAS="INTEGER",
    B_YAPI_CINSI="TEXT",
    B_B_BOLUM="INTEGER",
    B_KALITE="INTEGER",
    B_DURUM="TEXT",
    B_GIRIS="TEXT",
    B_CATI="TEXT",
    B_ISITMA="TEXT",
    B_ASANSOR="TEXT",
    B_OTOPARK="TEXT",
    B_TESCIL="TEXT DEFAULT 'HAYIR'",
    B_HASAR_DURUMU="TEXT DEFAULT 'HASARSIZ'",
    alan_m2="REAL CHECK(alan_m2 >= 0)",
)

SAHA_YOL_FIELDS = dict(
    COMMON_SURVEY_FIELDS,
    Y_AD="TEXT",
    Y_TIP="TEXT",
    Y_KAPLAMA="TEXT",
    Y_KAPLAMA_DURUM="TEXT",
    Y_GENISLIK="REAL",
    Y_KALDIRIM="INTEGER",
    Y_KALDIRIM_GEN="REAL",
    Y_REFUJ="TEXT DEFAULT 'YOK'",
    Y_SERIT="INTEGER DEFAULT 2",
    Y_YON="TEXT DEFAULT 'ÇİFT YÖN'",
    Y_BISIKLET_YOLU="TEXT DEFAULT 'YOK'",
    Y_ISGAL="INTEGER",
    Y_OTOPARK="INTEGER",
    Y_TRAFIK="INTEGER",
    Y_AYDINLATMA="TEXT DEFAULT 'YETERLİ'",
    uzunluk_m="REAL CHECK(uzunluk_m >= 0)",
)

TUCBS_ALAN_FIELDS = dict(
    COMMON_SURVEY_FIELDS,
    tucbs_sinifi="TEXT",
    alan_m2="REAL CHECK(alan_m2 >= 0)",
)

TUCBS_CIZGI_FIELDS = dict(
    COMMON_SURVEY_FIELDS,
    tucbs_sinifi="TEXT",
    uzunluk_m="REAL CHECK(uzunluk_m >= 0)",
)

LAND_TABLES = {
    "Tucbs_1000_alan": ("MultiPolygon", TUCBS_ALAN_FIELDS),
    "Tucbs_1000_Cizgi": ("MultiLineString", TUCBS_CIZGI_FIELDS),
    "parsel_saha": ("MultiPolygon", SAHA_PARSEL_FIELDS),
    "yapi_saha": ("MultiPolygon", SAHA_YAPI_FIELDS),
    "yol_saha": ("MultiLineString", SAHA_YOL_FIELDS),
}


def planning_tables(level: str) -> dict:
    """Return strictly isolated tables and fields for a specific planning level."""
    level = str(level).upper()
    if level not in PLAN_LEVEL_CODES:
        raise ValueError('Geçersiz plan kademesi: ' + level)

    prefix = "plangml_" + level.lower()

    if level == "MSP":
        area_specific = MSP_AREA_FIELDS
        line_specific = MSP_LINE_FIELDS
        notation_specific = MSP_NOTATION_FIELDS
    elif level == "CDP":
        area_specific = CDP_AREA_FIELDS
        line_specific = CDP_LINE_FIELDS
        notation_specific = CDP_NOTATION_FIELDS
    elif level == "NIP":
        area_specific = NIP_AREA_FIELDS
        line_specific = NIP_LINE_FIELDS
        notation_specific = NIP_NOTATION_FIELDS
    elif level == "UIP":
        area_specific = UIP_AREA_FIELDS
        line_specific = UIP_LINE_FIELDS
        notation_specific = UIP_NOTATION_FIELDS
    else:
        raise ValueError("Bilinmeyen seviye: " + level)

    return {
        prefix + "_alan": ("MultiPolygon", dict(COMMON_FIELDS, **area_specific)),
        prefix + "_cizgi": ("MultiLineString", dict(COMMON_FIELDS, **line_specific)),
        prefix + "_notasyon": ("Point", dict(COMMON_FIELDS, **notation_specific)),
    }


def selected_tables(levels: tuple[str, ...] | list[str]) -> dict:
    """Return combined dictionary of tables for specified planning levels."""
    result = {}
    for level in levels:
        result.update(planning_tables(level))
    return result


# Compatibility references
TABLES = planning_tables("UIP")
