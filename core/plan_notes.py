'PlanX MPYY Plan Notes and Legend Specification Engine.\n\nImplements statutory requirements of Mekânsal Planlar Yapım Yönetmeliği:\n- Madde 24: "İmar planı notları; plan kararlarının uygulanmasını yönlendiren, plan paftası\n  üzerinde gösterilemeyen veya gösterilmesinde güçlük bulunan hükümlerdir. Plan notları;\n  mevzuata, üst ölçekli plan kararlarına ve plan ana kararlarına aykırı olamaz."\n- Madde 31: Çizim normları, gösterimler ve plan notları standartları.\n\nScans the active plan layer to extract present zoning categories, land use classifications,\nand structural tags (TAKS, KAKS, Kat Adedi, Çekme Mesafeleri), then automatically\nsynthesizes standardized, legally sound Turkish planning provisions:\n1. Genel Hükümler (3194 s. Kanun, MPYY, PAİY, TBDY 2018 Deprem, Otopark, Sığınak)\n2. Özel Hükümler (Fonksiyon Bazlı Yapılaşma ve Kullanım Şartları)\n3. Jeolojik ve Afet Hükümleri (Zemin etütleri, yerleşime uygunluk)\n4. Uygulama ve Parselasyon Hükümleri (Madde 18 DOP, Kamu Terkleri, İfraz-Tevhit)\n'

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
import re
from typing import Any
from qgis.core import QgsFeature, QgsVectorLayer


def _norm_text(val: Any) -> str:
    text = str(val or "").strip().upper().translate(str.maketrans("ÇĞİÖŞÜ", "CGIOSU"))
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


# Statutory function classifications for custom clause dispatching
FUNCTION_TAXONOMY: dict[str, tuple[str, ...]] = {
    "KONUT": (
        "KONUT", "GELISME_KONUT", "MESKUN_KONUT", "YERLESIK_KONUT", "DUSUK_YOGUNLUK",
        "ORTA_YOGUNLUK", "YUKSEK_YOGUNLUK", "TOPLU_KONUT",
    ),
    "TICARET": (
        "TICARET", "TICARI", "CARSI", "IS_MERKEZI", "OFIS", "BURO", "AVM",
    ),
    "KARMA_TICARET_KONUT": (
        "TICARET_KONUT", "KARMA", "TICK", "TICARET_VE_KONUT", "KONUT_TICARET",
    ),
    "SANAYI": (
        "SANAYI", "ORGANIZED_SANAYI", "OSB", "ENDUSTRI", "FABRIKA",
    ),
    "KUCUK_SANAYI": (
        "KUCUK_SANAYI", "KSS", "SANAYI_SITESI", "IMALATHANE", "TAMIRHANE",
    ),
    "TURIZM": (
        "TURIZM", "OTEL", "MOTEL", "PANSIYON", "TATIL_KOYU", "GUNUBIRLIK",
    ),
    "PARK_YESIL": (
        "PARK", "COCUK_BAHCESI", "OYUN_ALANI", "REKREASYON", "MEYDAN", "BOTANIK",
        "MESIRE", "AGACLANDIRILACAK", "YESIL_ALAN", "ARBORETUM", "KENT_PARKI",
    ),
    "EGITIM": (
        "ANAOKULU", "KRES", "ILKOKUL", "ORTAOKUL", "LISE", "EGITIM", "TEMEL_EGITIM",
        "MESLEK_LISESI", "OZEL_EGITIM", "OKUL", "KAMPUS",
    ),
    "SAGLIK": (
        "SAGLIK", "AILE_SAGLIGI", "ASM", "HASTANE", "DISPANSER", "POLIKLINIK",
        "SAGLIK_OCAGI", "SAGLIK_TESISI",
    ),
    "SOSYAL_KULTUR": (
        "SOSYAL", "KULTUR", "KULTUREL", "KUTUPHANE", "MUZE", "YASLI_BAKIMEVI",
        "HUZUREVI", "SEFKAT_EVI", "SERGI", "YURT", "GENCLIK_MERKEZI", "TOPLUM_MERKEZI",
    ),
    "IBADET": (
        "IBADET", "CAMI", "MESCIT", "KILISE", "SINAGOG", "HAVRA", "DINI",
    ),
    "SPOR": (
        "SPOR", "STADYUM", "KAPALI_SPOR", "HIPODROM", "YUZME_HAVUZU", "SAHA",
    ),
    "TEKNIK_ALTYAPI": (
        "TEKNIK_ALTYAPI", "TRAFO", "SU_DEPOSU", "ARITMA", "TERFI", "TELEKOM",
        "KATI_ATIK", "REGULATOR", "DOGALGAZ_DAGITIM",
    ),
    "KAMU_BELEDIYE": (
        "BHA", "BELEDIYE_HIZMET", "KHA", "KAMU_HIZMET", "RESMI_KURUM", "IDARI_TESIS",
    ),
}


@dataclass
class PlanNotesResult:
    plan_adi: str
    plan_olcegi: str
    tespit_edilen_kategoriler: list[str] = field(default_factory=list)
    genel_hukumler: list[str] = field(default_factory=list)
    ozel_hukumler: dict[str, list[str]] = field(default_factory=dict)
    jeolojik_hukumler: list[str] = field(default_factory=list)
    uygulama_hukumleri: list[str] = field(default_factory=list)
    markdown_text: str = ""
    html_text: str = ""
    plain_text: str = ""


class PlanNotesEngine:
    """Automated statutory plan notes and legend text generator under MPYY."""

    @classmethod
    def detect_categories(cls, features: list[QgsFeature]) -> list[str]:
        """Inspect features and return matching taxonomy categories."""
        keys = (
            "uipfonksiyon", "fonksiyon_adi", "P_FONK", "B_FONK", "plan_fonk",
            "catalog_id", "detay_katalogu", "ustkonugrup", "ust_konu_grup",
        )
        detected = set()

        for feat in features:
            val_str = ""
            for k in keys:
                idx = feat.fields().indexFromName(k)
                if idx >= 0:
                    v = feat[idx]
                    if v not in (None, "", "NULL"):
                        val_str += f" {_norm_text(v)}"

            if not val_str:
                continue

            for cat, kws in FUNCTION_TAXONOMY.items():
                for kw in kws:
                    if f"_{kw}_" in f"_{val_str}_" or kw in val_str:
                        detected.add(cat)
                        break

        # Maintain consistent order
        return [c for c in FUNCTION_TAXONOMY if c in detected]

    @classmethod
    def generate_plan_notes(
        cls,
        plan_title: str = '1/1.000 Ölçekli Uygulama İmar Planı',
        scale: str = "1/1.000",
        categories: list[str] | None = None,
        features: list[QgsFeature] | None = None,
        include_geology: bool = True,
        include_article18: bool = True,
    ) -> PlanNotesResult:
        """Synthesize comprehensive, legally compliant plan notes."""
        if categories is None:
            if features:
                categories = cls.detect_categories(features)
            else:
                categories = ["KONUT", "TICARET", "PARK_YESIL", "EGITIM", "SAGLIK", "IBADET", "TEKNIK_ALTYAPI"]

        res = PlanNotesResult(
            plan_adi=plan_title,
            plan_olcegi=scale,
            tespit_edilen_kategoriler=categories,
        )

        # 1. Genel Hükümler
        res.genel_hukumler = [
            'Bu plan; plan paftaları, plan açıklama raporu ve plan uygulama hükümleri ile bir bütündür.',
            'Plan onama sınırı içerisinde 3194 sayılı İmar Kanunu, Mekânsal Planlar Yapım Yönetmeliği, Planlı Alanlar İmar Yönetmeliği ve yürürlükteki ilgili mevzuat hükümleri geçerlidir.',
            'Plan çiziminde ve gösteriminde Mekânsal Planlar Yapım Yönetmeliği standart gösterim normları esastır.',
            'Tüm yapılarda Türkiye Bina Deprem Yönetmeliği (TBDY 2018) ile Afet Bölgelerinde Yapılacak Yapılar Hakkındaki Yönetmelik şartlarına uyulması zorunludur.',
            'Otopark ihtiyacı yürürlükteki Otopark Yönetmeliği doğrultusunda parsel bünyesinde karşılanacaktır. Parsel sınırları içinde gerekli otopark alanı ayrılmadan yapı kullanma izin belgesi (iskân) düzenlenemez.',
            'Sığınak ihtiyacı yürürlükteki Sığınak Yönetmeliği hükümlerine uygun olarak bina bünyesinde sağlanacaktır.',
            'Binaların Yangından Korunması Hakkında Yönetmelik kurallarına ve itfaiye teşkilatı standartlarına uyulacaktır.',
            'Kentsel mekânlarda, yollarda ve yapılarda engelli erişilebilirliğini temin etmek amacıyla TS 9111 ve TS 12576 standartları ile ilgili ulusal erişilebilirlik mevzuatına uyulması mecburidir.',
            "Planlama alanında her türlü katı, sıvı ve gaz atıkların bertarafında Çevre Kanunu ve mer'i çevre yönetmeliklerine uyulacaktır.",
        ]

        # 2. Özel Hükümler (Fonksiyon Bazlı)
        if "KONUT" in categories:
            res.ozel_hukumler['KONUT ALANLARI'] = [
                'Konut alanlarında yalnızca yerleşme amacına yönelik konut ve konut sakinlerinin günlük ihtiyaçlarını karşılayacak bağımsız ticari birimler yer alabilir.',
                'Yapılaşma nizamı, TAKS, KAKS / Emsal ve Yençok (kat adedi) değerleri plan paftasında belirtilen değerleri aşamaz.',
                'Zemin veya açığa çıkan bodrum katlarda emsal harici alanlar Planlı Alanlar İmar Yönetmeliği Madde 5 ve 22 sınırları dâhilinde değerlendirilecektir.',
            ]

        if "TICARET" in categories:
            res.ozel_hukumler['Ticaret Alanları'] = [
                'Ticaret alanlarında iş merkezleri, ofis, büro, çarşı, çok katlı mağaza, banka, otel, finans kurumları ve benzeri ticari ve yönetsel birimler yer alabilir.',
                'Bu alanlarda zemin ve bodrum katlarda kapalı veya açık yükleme-boşaltma alanları parsel bünyesinde çözümlenecektir.',
            ]

        if "KARMA_TICARET_KONUT" in categories:
            res.ozel_hukumler['Ticaret + Konut (Karma) Alanları'] = [
                'Ticaret+Konut karma kullanım alanlarında zemin ve varsa açığa çıkan bodrum katlar ticari kullanım, üst katlar ise konut veya büro/ofis amaçlı kullanılabilir.',
                'Girişler, yangın kaçış merdivenleri ve otopark dolaşımları ticari ve konut kullanıcıları için ayrıştırılacaktır.',
            ]

        if "SANAYI" in categories:
            res.ozel_hukumler['Sanayi Alanları'] = [
                'Sanayi alanlarında gayrisıhhi müesseseler mevzuatı, ÇED hükümleri ve İşyeri Açma ve Çalışma Ruhsatlarına İlişkin Yönetmelik şartları aranacaktır.',
                'Parsel sınırından en az 10.00 metre yapı yaklaşma mesafesi bırakılacak ve komşu parseller ile arasına koruyucu yeşil bant tesis edilecektir.',
            ]

        if "KUCUK_SANAYI" in categories:
            res.ozel_hukumler['Küçük Sanayi Sitesi Alanları'] = [
                'Küçük sanayi alanlarında oto tamir, demir-marangoz atölyeleri, torna, hafif imalat ve depolama birimleri yer alabilir.',
                'Çevre sağlığı, gürültü ve hava kalitesi koruma tedbirlerinin alınması zorunludur.',
            ]

        if "TURIZM" in categories:
            res.ozel_hukumler['Turizm Tesis Alanları'] = [
                'Turizm tesis alanlarında Kültür ve Turizm Bakanlığı Turizm Tesislerinin Niteliklerine İlişkin Yönetmelik kuralları geçerlidir.',
                'Otel, tatil köyü veya günübirlik tesis projeleri ilgili kamu idaresince onaylanmadan inşaat ruhsatı verilemez.',
            ]

        if "PARK_YESIL" in categories:
            res.ozel_hukumler['Park ve Yeşil Alanlar'] = [
                'Park ve çocuk bahçesi alanlarında hiçbir şekilde kalıcı betonarme konut veya ticari yapı yapılamaz.',
                'Bu alanlarda dinlenme, gezinti, açık spor alanları, çocuk oyun üniteleri ve Planlı Alanlar İmar Yönetmeliği Madde 19 uyarınca sökülüp takılabilir büfe (en fazla 10 m²), çay ocağı ve pergolalar yer alabilir.',
                'Park alanlarının altına yalnızca kamu yararı gerektiren zorunlu hallerde yer altı otoparkı veya teknik altyapı trafosu inşa edilebilir.',
            ]

        if "EGITIM" in categories:
            res.ozel_hukumler['Eğitim Tesis Alanları'] = [
                'Anaokulu, ilkokul, ortaokul ve lise alanları kamu eline geçmeden özel veya kamu yapılaşmasına açılamaz.',
                'Milli Eğitim Bakanlığı Tip Proje ve Okul Yapıları Standartları doğrultusunda okul bahçesi ve yangın tahliyesi düzenlenecektir.',
            ]

        if "SAGLIK" in categories:
            res.ozel_hukumler['Sağlık Tesis Alanları'] = [
                'Sağlık alanlarında Aile Sağlığı Merkezi, Poliklinik veya Hastane tesisleri yer alabilir.',
                'Tesis girişinde acil ambulans intikal yolları ve hasta indirme-bindirme cepleri açık tutulacaktır.',
            ]

        if "SOSYAL_KULTUR" in categories:
            res.ozel_hukumler['Sosyal ve Kültürel Tesis Alanları'] = [
                'Sosyal-kültürel tesislerde kütüphane, müze, kreş, gençlik merkezi, sergi salonu ve çok amaçlı toplantı mekânları planlanabilir.',
                'Tüm kapalı ve açık alanlarda engelli erişilebilirliği eksiksiz sağlanacaktır.',
            ]

        if "IBADET" in categories:
            res.ozel_hukumler['İBADET ALANLARI'] = [
                'Cami ve ibadethane yapılarında şadırvan, abdesthane ve müştemilatlar vaziyet planı uyarınca ana kütleyle uyumlu düzenlenecektir.',
                'Cami avlusu afet anında acil toplanma alanı olarak kullanılabilecek şekilde planlanacaktır.',
            ]

        if "TEKNIK_ALTYAPI" in categories:
            res.ozel_hukumler['Teknik Altyapı ve Tesis Alanları'] = [
                'Trafo, terfi istasyonu, su deposu, regülatör vb. teknik tesislerin çevresinde ilgili dağıtım şirketinin güvenlik mesafesi şartı aranır.',
                'Teknik altyapı tesisleri çevresi mimari çit ve yeşil perde ile kapatılacaktır.',
            ]

        if "KAMU_BELEDIYE" in categories:
            res.ozel_hukumler['Belediye Hizmet ve Resmi Kurum Alanları'] = [
                'Belediye Hizmet Alanı (BHA) ve Resmi Kurum Alanlarında (KHA) kamu hizmetlerine yönelik idari, teknik veya operasyonel tesisler yer alabilir.',
            ]

        # 3. Jeolojik ve Afet Hükümleri
        if include_geology:
            res.jeolojik_hukumler = [
                'İmar planına esas onaylı Jeolojik-Jeoteknik Etüt Raporunda belirlenen yerleşime uygunluk bölgeleri (Uygun Alanlar - UA, Önlemli Alanlar - ÖA, Ayrıntılı Jeoteknik Etüt Gerektiren Alanlar) kararlarına uyulması mecburidir.',
                'ÖA (Önlemli Alan) olarak tanımlanan kesimlerde yapı ruhsatı aşamasında zemin etüt raporları doğrultusunda öngörülen zemin iyileştirme, temel kazısı şev güvenliği ve drenaj tedbirleri eksiksiz projelendirilecektir.',
                'Yeraltı suyu seviyesi yüksek parsellerde temel altı bohçalama su yalıtımı ve çevre drenajı yapılacaktır.',
            ]

        # 4. Uygulama ve Parselasyon Hükümleri
        if include_article18:
            res.uygulama_hukumleri = [
                'Plan onama sınırı içerisindeki tüm kadastro parsellerinde 3194 sayılı İmar Kanununun 18. maddesi uyarınca Arsa ve Arazi Düzenlemesi (Parselasyon) uygulaması yapılması esastır.',
                'Düzenleme Ortaklık Payı (DOP) kesinti oranı yüzde 45 yasal tavan sınırını aşamaz. DOP kesintisi ile karşılanamayan kamu donatı alanları için Kamulaştırma Ortaklık Payı (KOP) veya ilgili idarelerce kamulaştırma yoluna gidilecektir.',
                'Planlama alanında kamuya ayrılmış yol, yeşil alan, eğitim, sağlık ve ibadet gibi donatı alanları kamu eline geçmeden ve yol altyapısı fiilen tamamlanmadan inşaat ruhsatı düzenlenemez.',
                'Planlı Alanlar İmar Yönetmeliği Madde 15, 16 ve 22 gereği asgari parsel cephesi ve derinliğini sağlamayan parseller tevhit edilmeden müstakilen yapılaşamaz.',
                'İmar parsellerinde çekme mesafeleri; ön bahçelerde asgari 5.00 metre, yan ve arka bahçelerde asgari 3.00 metre olup plan paftasında aksi belirtilmedikçe bu mesafeler daraltılamaz.',
            ]

        # Synthesize Text Formats
        res.markdown_text = cls._build_markdown(res)
        res.html_text = cls._build_html(res)
        res.plain_text = cls._build_plain(res)

        return res

    @staticmethod
    def _build_markdown(res: PlanNotesResult) -> str:
        md = [
            f'# {res.plan_adi.upper()} — PLAN NOTES AND IMPLEMENTATION PROVISIONS',
            f'**Scale:** {res.plan_olcegi} | **Mevzuat:** 3194 sayılı İmar Kanunu ve MPYY',
            "",
            "---",
            "",
            '## 1. GENERAL PROVISIONS',
        ]
        for idx, rule in enumerate(res.genel_hukumler, 1):
            md.append(f"1.{idx}. {rule}")

        md.append("")
        md.append('## 2. FONKSİYONA ÖZGÜ HÜKÜMLER')
        for f_idx, (group, rules) in enumerate(res.ozel_hukumler.items(), 1):
            md.append(f"### 2.{f_idx}. {group}")
            for r_idx, rule in enumerate(rules, 1):
                md.append(f'- **2.{f_idx} satır bulundu.{r_idx}.** {rule}')
            md.append("")

        if res.jeolojik_hukumler:
            md.append('## 3. GEOLOGICAL AND HAZARD PROVISIONS')
            for idx, rule in enumerate(res.jeolojik_hukumler, 1):
                md.append(f"3.{idx}. {rule}")
            md.append("")

        if res.uygulama_hukumleri:
            sec_no = 4 if res.jeolojik_hukumler else 3
            md.append(f'## {sec_no}. IMPLEMENTATION AND LAND READJUSTMENT PROVISIONS')
            for idx, rule in enumerate(res.uygulama_hukumleri, 1):
                md.append(f'{sec_no} satır bulundu.{idx}. {rule}')
            md.append("")

        return "\n".join(md)

    @staticmethod
    def _build_plain(res: PlanNotesResult) -> str:
        lines = [
            f"{res.plan_adi.upper()} PLAN NOTLARI",
            f'Ölçek: {res.plan_olcegi}',
            "=" * 60,
            "",
            '1. GENERAL PROVISIONS',
            "-" * 40,
        ]
        for idx, rule in enumerate(res.genel_hukumler, 1):
            lines.append(f"1.{idx}. {rule}")

        lines.append("")
        lines.append('2. SPECIFIC PROVISIONS')
        lines.append("-" * 40)
        for f_idx, (group, rules) in enumerate(res.ozel_hukumler.items(), 1):
            lines.append(f"2.{f_idx}. {group}:")
            for r_idx, rule in enumerate(rules, 1):
                lines.append(f'   2.{f_idx} satır bulundu.{r_idx}. {rule}')

        if res.jeolojik_hukumler:
            lines.append("")
            lines.append('3. GEOLOGICAL AND HAZARD PROVISIONS')
            lines.append("-" * 40)
            for idx, rule in enumerate(res.jeolojik_hukumler, 1):
                lines.append(f"3.{idx}. {rule}")

        if res.uygulama_hukumleri:
            sec_no = 4 if res.jeolojik_hukumler else 3
            lines.append("")
            lines.append(f'{sec_no}. IMPLEMENTATION AND LAND READJUSTMENT PROVISIONS')
            lines.append("-" * 40)
            for idx, rule in enumerate(res.uygulama_hukumleri, 1):
                lines.append(f'{sec_no} satır bulundu.{idx}. {rule}')

        return "\n".join(lines)

    @staticmethod
    def _build_html(res: PlanNotesResult) -> str:
        html = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "  <meta charset='UTF-8'>",
            f'  <title>{res.plan_adi} Plan Notları</title>',
            "  <style>",
            "    body { font-family: 'Segoe UI', -apple-system, Roboto, sans-serif; background: #fdfefe; color: #2c3e50; padding: 28px; }",
            "    .container { max-width: 960px; margin: 0 auto; background: #fff; border: 1px solid #d5dbdb; padding: 36px; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }",
            "    h1 { color: #1a5276; font-size: 22px; margin-top: 0; border-bottom: 2px solid #2980b9; padding-bottom: 10px; }",
            "    h2 { color: #2e4053; font-size: 16px; border-left: 4px solid #1a5276; padding-left: 8px; margin-top: 24px; }",
            "    h3 { color: #34495e; font-size: 14px; margin-top: 14px; margin-bottom: 6px; }",
            "    p, li { font-size: 13px; line-height: 1.6; }",
            "    ol, ul { padding-left: 22px; }",
            "    .badge { background: #ebf5fb; color: #1a5276; border: 1px solid #aed6f1; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }",
            "    @media print { body { padding: 0; background: #fff; } .container { box-shadow: none; border: none; padding: 0; } }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='container'>",
            f"    <h1>{res.plan_adi}</h1>",
            f"    <p><span class='badge'>Ölçek: {res.plan_olcegi}</span> &nbsp; <span class='badge'>Mevzuat: MPYY & PAİY</span></p>",
            '    <h2>1. GENEL HÜKÜMLER</h2>',
            "    <ol>",
        ]
        for rule in res.genel_hukumler:
            html.append(f"      <li>{rule}</li>")
        html.append("    </ol>")

        html.append('    <h2>2. FONKSİYONLARA ÖZEL HÜKÜMLER</h2>')
        for group, rules in res.ozel_hukumler.items():
            html.append(f"    <h3>{group}</h3>")
            html.append("    <ul>")
            for rule in rules:
                html.append(f"      <li>{rule}</li>")
            html.append("    </ul>")

        if res.jeolojik_hukumler:
            html.append('    <h2>3. JEOLOJİK VE AFET HÜKÜMLERİ</h2>')
            html.append("    <ol>")
            for rule in res.jeolojik_hukumler:
                html.append(f"      <li>{rule}</li>")
            html.append("    </ol>")

        if res.uygulama_hukumleri:
            sec_no = 4 if res.jeolojik_hukumler else 3
            html.append(f'    <h2>{sec_no}. UYGULAMA VE PARSELASYON HÜKÜMLERİ</h2>')
            html.append("    <ol>")
            for rule in res.uygulama_hukumleri:
                html.append(f"      <li>{rule}</li>")
            html.append("    </ol>")

        html.extend(["  </div>", "</body>", "</html>"])
        return "\n".join(html)
