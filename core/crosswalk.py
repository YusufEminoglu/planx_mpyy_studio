"""TUCBS / Saha Anketi -> MPYY Fonksiyon Crosswalk Motoru.

Mevzuat ve planlama disiplini gereği:
Belirsiz veya çoklu karşılığı olan arazi kullanım fonksiyonları ASLA otomatik karar
olarak atanmaz; 'ONAY_BEKLIYOR' statüsüyle işaretlenerek şehir plancısının onayına sunulur.
"""

from dataclasses import dataclass
from typing import Any
from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
)

from .attr_utils import adapt_geometry_for_sink, clean_text, field_index_ci

# Doğrudan / Tekil Eşleşmeler (Deterministic Mappings)
DETERMINISTIC_CROSSWALK = {
    # TUCBS ve Özgün Saha Sınıfları -> (UİP Fonksiyonu, Üst Konu Grubu)
    "KONUT": ("YERLEŞİK KONUT ALANI", "KONUT ALANLARI / YERLEŞİM ALANLARI"),
    "TOPLU_KONUT": ("TOPLU KONUT ALANI", "KONUT ALANLARI / YERLEŞİM ALANLARI"),
    "TICARET": ("TİCARET ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "OFIS_BURO": ("TİCARET ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "AVM": ("TİCARET ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "TURIZM_TESISI": ("TURİZM TESİS ALANI", "TURİZM ALANLARI"),
    "YEME_ICME": ("GÜNÜBİRLİK TESİS ALANI", "TURİZM ALANLARI"),
    "AKARYAKIT": ("AKARYAKIT VE SERVİS İSTASYONU ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "PARK": ("PARK", "AÇIK VE YEŞİL ALANLAR"),
    "COCUK_BAHCESI": ("ÇOCUK BAHÇESİ VE OYUN ALANI", "AÇIK VE YEŞİL ALANLAR"),
    "COCUK_OYUN": ("ÇOCUK BAHÇESİ VE OYUN ALANI", "AÇIK VE YEŞİL ALANLAR"),
    "MEYDAN": ("MEYDAN", "AÇIK VE YEŞİL ALANLAR"),
    "REKREASYON": ("REKREASYON ALANI", "AÇIK VE YEŞİL ALANLAR"),
    "ILKOKUL": ("İLKOKUL ALANI", "EĞİTİM TESİSLERİ ALANI"),
    "ORTAOKUL": ("ORTAOKUL ALANI", "EĞİTİM TESİSLERİ ALANI"),
    "LISE": ("LİSE ALANI", "EĞİTİM TESİSLERİ ALANI"),
    "EGITIM": ("EĞİTİM TESİSLERİ ALANI", "EĞİTİM TESİSLERİ ALANI"),
    "YUKSEK_OGRETIM": ("YÜKSEK ÖĞRETİM ALANI", "EĞİTİM TESİSLERİ ALANI"),
    "SAGLIK_OCAGI": ("AİLE SAĞLIĞI MERKEZİ", "SAĞLIK TESİSLERİ ALANI"),
    "HASTANE": ("HASTANE", "SAĞLIK TESİSLERİ ALANI"),
    "SAGLIK": ("SAĞLIK TESİSLERİ ALANI", "SAĞLIK TESİSLERİ ALANI"),
    "CAMI": ("CAMİ", "İBADET ALANLARI"),
    "MESCIT": ("MESCİT", "İBADET ALANLARI"),
    "DINI_TESIS": ("İBADET ALANI", "İBADET ALANLARI"),
    "OTOPARK": ("GENEL OTOPARK ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "MEZARLIK": ("MEZARLIK ALANI", "AÇIK VE YEŞİL ALANLAR"),
    "SANAYI": ("SANAYİ TESİS ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "KUCUK_SANAYI": ("KÜÇÜK SANAYİ ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "KSS": ("KÜÇÜK SANAYİ ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "DEPOLAMA": ("DEPOLAMA ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "TOPTAN_TICARET": ("TOPTAN TİCARET ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "BELEDIYE_HIZMET": ("BELEDİYE HİZMET ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "RESMI_KURUM": ("RESMİ KURUM ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "RESMI_TESIS": ("RESMİ KURUM ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "GUVENLIK": ("EMNİYET / GÜVENLİK TESİS ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "SOSYO_KULTUREL_TESIS": ("SOSYAL VE KÜLTÜREL TESİS ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "SPOR_ALANI": ("AÇIK VE KAPALI SPOR ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "TARIM_EKILI": ("TARIM ALANI", "KIRSAL VE TARIMSAL ALANLAR"),
    "EKILI_TARIM": ("TARIM ALANI", "KIRSAL VE TARIMSAL ALANLAR"),
    "ZEYTINLIK": ("DİKİLİ TARIM ARAZİSİ", "KIRSAL VE TARIMSAL ALANLAR"),
    "SERA": ("ÖRTÜ ALTI TARIM ARAZİSİ", "KIRSAL VE TARIMSAL ALANLAR"),
    "HAYVANCILIK": ("HAYVANCILIK TESİS ALANI", "KIRSAL VE TARIMSAL ALANLAR"),
    "TEKNIK_ALTYAPI": ("TEKNİK ALTYAPI ALANI", "TEKNİK ALTYAPI"),
    "TRAFO": ("TRAFO ALANI", "TEKNİK ALTYAPI"),
    "ASKERI_ALAN": ("ASKERİ ALAN", "KAMU HİZMET ALANLARI"),
    "ORMAN": ("ORMAN ALANI", "ORMAN ALANLARI"),
    "SU_YUZEYI": ("SU YÜZEYİ", "SU ALANLARI"),
    "MADEN_OCAK": ("MADEN OCAKLARI ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "TERMINAL": ("OTOBÜS TERMİNALİ ALANI", "ULAŞIM VE LOJİSTİK"),
    "DEMIRYOLU_ISTASYON": ("DEMİRYOLU İSTASYONU", "ULAŞIM VE LOJİSTİK"),
    "LIMAN_ISKELE": ("LİMAN VE İSKELE ALANI", "ULAŞIM VE LOJİSTİK"),
    "HAVAALANI": ("HAVAALANI ALANI", "ULAŞIM VE LOJİSTİK"),
    "YURT_BAKIMEVI": ("YURT VE HUZUREVİ ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "ADLIYE_CEZAEVI": ("RESMİ KURUM ALANI", "SOSYAL ALT YAPI ALANLARI"),
    "MERA_OTLAK": ("MERA ALANI", "KIRSAL VE TARIMSAL ALANLAR"),
    "SAZLIK_SULAK": ("SULAK ALAN VE SAZLIK", "SU ALANLARI"),
    "KIYI_KUMSAL": ("KIYI KENAR VE KUMSAL ALANI", "AÇIK VE YEŞİL ALANLAR"),
    "LOJMAN": ("LOJMAN ALANI", "KONUT ALANLARI / YERLEŞİM ALANLARI"),
    "BANKA_FINANS": ("TİCARET ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "PAZAR_YERI": ("PAZAR ALANI", "KENTSEL ÇALIŞMA ALANLARI"),
    "ENERJI_URETIM": ("ENERJİ ÜRETİM VE DAĞITIM ALANI", "TEKNİK ALTYAPI"),
    "KRES_GUNDUZ_BAKIM": ("KREŞ VE GÜNDÜZ BAKIMEVİ ALANI", "EĞİTİM TESİSLERİ ALANI"),
    "BOTANIK_HAYVANAT_BAHCESI": ("BOTANİK VE HAYVANAT BAHÇESİ ALANI", "AÇIK VE YEŞİL ALANLAR"),
}

# Çoklu / Belirsiz Eşleşmeler (Ambiguous Mappings - Şehir Plancısı Onayı Zorunlu)
AMBIGUOUS_CROSSWALK = {
    "GECEKONDU": [
        "GELİŞME KONUT ALANI",
        "KENTSEL DÖNÜŞÜM / YENİLEME ALANI",
        "YERLEŞİK KONUT ALANI",
    ],
    "KENTSEL_DONUSUM": [
        "KENTSEL DÖNÜŞÜM / YENİLEME ALANI",
        "GELİŞME KONUT ALANI",
        "TİCARET - KONUT ALANI",
    ],
    "KARMA_KULLANIM": [
        "TİCARET - KONUT ALANI",
        "TİCARET - TURİZM ALANI",
        "TİCARET-TURİZM-KONUT ALANI",
    ],
    "KONUT_TICARET": [
        "TİCARET - KONUT ALANI",
        "TİCARET - TURİZM ALANI",
        "TİCARET-TURİZM-KONUT ALANI",
    ],
    "BOS_ARSA": [
        "GELİŞME KONUT ALANI",
        "PARK",
        "KAMU HİZMET ALANI",
    ],
    "BOS_PARSEL": [
        "GELİŞME KONUT ALANI",
        "PARK",
        "KAMU HİZMET ALANI",
    ],
    "BOS": [
        "GELİŞME KONUT ALANI",
        "PARK",
        "KAMU HİZMET ALANI",
    ],
    "INSAAT": [
        "YERLEŞİK KONUT ALANI",
        "GELİŞME KONUT ALANI",
        "TİCARET ALANI",
    ],
    "HARABE": [
        "KORUNMASI GEREKLİ KÜLTÜR VARLIĞI",
        "KENTSEL DÖNÜŞÜM / YENİLEME ALANI",
        "GELİŞME KONUT ALANI",
    ],
    "KENTSEL_SERVIS": [
        "KENTSEL SERVİS ALANI",
        "KÜÇÜK SANAYİ ALANI",
        "TOPLU İŞYERLERİ",
    ],
    "TURIZM": [
        "OTEL ALANI",
        "GÜNÜBİRLİK TESİS ALANI",
        "PANSİYON ALANI",
        "TATİL KÖYÜ ALANI",
    ],
    "TARIM": [
        "DİKİLİ TARIM ARAZİSİ",
        "MUTLAK TARIM ARAZİSİ",
        "ÖRTÜ ALTI TARIM ARAZİSİ",
    ],
    "SPOR": [
        "AÇIK SPOR TESİSİ ALANI",
        "KAPALI SPOR TESİSİ ALANI",
    ],
}


@dataclass(frozen=True)
class CrosswalkMatch:
    kaynak_deger: str
    eslesen_fonksiyon: str
    ust_grup: str
    durum: str  # 'OTOMATIK_ESLESTI' veya 'ONAY_BEKLIYOR'
    aday_fonksiyonlar: tuple[str, ...]


def evaluate_crosswalk(source_text: str) -> CrosswalkMatch:
    """Evaluate a land use or survey classification string and return structured match result."""
    norm = (
        str(source_text or "")
        .strip()
        .upper()
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
        .replace("Ç", "C")
        .replace(" ", "_")
        .replace("-", "_")
    )

    if not norm:
        return CrosswalkMatch(
            kaynak_deger=source_text,
            eslesen_fonksiyon="",
            ust_grup="",
            durum="TANIMSIZ_KULLANICI_GIRDILMELI",
            aday_fonksiyonlar=(),
        )

    # 1. Exact match checks: ambiguous takes precedence over deterministic
    if norm in AMBIGUOUS_CROSSWALK:
        return CrosswalkMatch(
            kaynak_deger=source_text,
            eslesen_fonksiyon="",
            ust_grup="",
            durum="ONAY_BEKLIYOR",
            aday_fonksiyonlar=tuple(AMBIGUOUS_CROSSWALK[norm]),
        )

    if norm in DETERMINISTIC_CROSSWALK:
        target_fonk, ust_grp = DETERMINISTIC_CROSSWALK[norm]
        return CrosswalkMatch(
            kaynak_deger=source_text,
            eslesen_fonksiyon=target_fonk,
            ust_grup=ust_grp,
            durum="OTOMATIK_ESLESTI",
            aday_fonksiyonlar=(target_fonk,),
        )

    # 2. Token-boundary matching with longer keys evaluated first
    # This guarantees compound keys like TOPLU_KONUT or KONUT_TICARET are never
    # hijacked by single words like KONUT or PARK.
    norm_padded = f"_{norm}_"

    # Check ambiguous compound keys first
    sorted_ambiguous = sorted(AMBIGUOUS_CROSSWALK.items(), key=lambda x: len(x[0]), reverse=True)
    for key, candidates in sorted_ambiguous:
        if f"_{key}_" in norm_padded:
            return CrosswalkMatch(
                kaynak_deger=source_text,
                eslesen_fonksiyon="",
                ust_grup="",
                durum="ONAY_BEKLIYOR",
                aday_fonksiyonlar=tuple(candidates),
            )

    # Check deterministic keys sorted by length descending
    sorted_deterministic = sorted(DETERMINISTIC_CROSSWALK.items(), key=lambda x: len(x[0]), reverse=True)
    for key, (target_fonk, ust_grp) in sorted_deterministic:
        if f"_{key}_" in norm_padded:
            return CrosswalkMatch(
                kaynak_deger=source_text,
                eslesen_fonksiyon=target_fonk,
                ust_grup=ust_grp,
                durum="OTOMATIK_ESLESTI",
                aday_fonksiyonlar=(target_fonk,),
            )

    # 3. Completely unrecognized classification
    return CrosswalkMatch(
        kaynak_deger=source_text,
        eslesen_fonksiyon="",
        ust_grup="",
        durum="TANIMSIZ_KULLANICI_GIRDILMELI",
        aday_fonksiyonlar=(),
    )


def execute_layer_crosswalk(
    source_layer: QgsVectorLayer,
    target_plan_layer: QgsVectorLayer,
    source_field_name: str = "P_FONK",
) -> dict[str, Any]:
    """Transfer geometries from field survey to plan layer with rigorous crosswalk classification."""
    if not source_layer.isValid() or not target_plan_layer.isValid():
        raise ValueError('Geçersiz kaynak veya hedef katman')

    f_idx = field_index_ci(source_layer.fields(), source_field_name)
    if f_idx < 0:
        for alt in ("tucbs_sinifi", "P_FONK", "B_FONK", "Y_TIP"):
            f_idx = field_index_ci(source_layer.fields(), alt)
            if f_idx >= 0:
                source_field_name = source_layer.fields().at(f_idx).name()
                break
    if f_idx < 0:
        raise ValueError(f'Kaynak alanda {source_field_name} sütunu bulunamadı')

    auto_count = 0
    pending_count = 0
    unresolved_count = 0

    src_crs = source_layer.crs()
    dst_crs = target_plan_layer.crs()
    transform = (
        QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance().transformContext())
        if src_crs.isValid() and dst_crs.isValid() and src_crs != dst_crs
        else None
    )
    target_wkb = target_plan_layer.wkbType()
    target_fields = target_plan_layer.fields()
    target_field_names = set(target_fields.names())

    was_editable = target_plan_layer.isEditable()
    if not was_editable and not target_plan_layer.startEditing():
        raise RuntimeError('Hedef plan katmanı düzenleme moduna alınamadı.')
    try:
        for feat in source_layer.getFeatures():
            src_val = clean_text(feat.attributes()[f_idx])
            match = evaluate_crosswalk(src_val)

            new_feat = QgsFeature(target_fields)
            geom = QgsGeometry(feat.geometry())
            if transform is not None and not geom.isEmpty():
                geom.transform(transform)
            new_feat.setGeometry(adapt_geometry_for_sink(geom, target_wkb))

            def safe_set(f_name, val):
                if f_name in target_field_names:
                    new_feat.setAttribute(f_name, val)

            # Set attributes
            if match.durum == "OTOMATIK_ESLESTI":
                auto_count += 1
                safe_set("fonksiyon_adi", match.eslesen_fonksiyon)
                safe_set("ust_grup_adi", match.ust_grup)
                safe_set("uipfonksiyon", match.eslesen_fonksiyon)
                safe_set("nipfonksiyon", match.eslesen_fonksiyon)
                safe_set("ustkonugrup", match.ust_grup)
                safe_set("aciklama", f'TUCBS Saha Aktarımı: {src_val}')
            elif match.durum == "ONAY_BEKLIYOR":
                pending_count += 1
                # CRITICAL: Leave function empty so it requires explicit planner approval
                candidates_str = ", ".join(match.aday_fonksiyonlar)
                safe_set("fonksiyon_adi", "")
                safe_set("uipfonksiyon", "")
                safe_set("nipfonksiyon", "")
                safe_set("aciklama", f"ONAY_BEKLIYOR: Saha='{src_val}' Adaylar: [{candidates_str}]")
            else:
                unresolved_count += 1
                safe_set("fonksiyon_adi", "")
                safe_set("uipfonksiyon", "")
                safe_set("nipfonksiyon", "")
                safe_set("aciklama", f"TANIMSIZ: Saha='{src_val}'")

            if not target_plan_layer.addFeature(new_feat):
                raise RuntimeError('Hedef plan katmanına nesne eklenemedi.')

        if not was_editable and not target_plan_layer.commitChanges():
            errors = "; ".join(target_plan_layer.commitErrors()[-3:])
            raise RuntimeError(f'Hedef plan katmanı değişiklikleri kaydedilemedi: {errors}')
    except Exception as exc:
        if not was_editable and target_plan_layer.isEditable():
            target_plan_layer.rollBack()
        raise RuntimeError(f'Fonksiyon eşleştirmesi sırasında hata: {exc}') from exc

    return {
        "toplam_nesne": source_layer.featureCount(),
        "otomatik_eslesen": auto_count,
        "onay_bekleyen": pending_count,
        "tanimsiz": unresolved_count,
    }
