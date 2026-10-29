'PlanX MPYY Dynamic Form Designer, Attribute Expressions, Relations, and Validation Constraints.\n\nImplements high-productivity, publication-grade user experience for QGIS spatial planning:\n1. Column Relations & Code-Lists: Maps statutory domains (PAİY Nizam, Mülkiyet, Taşıyıcı Sistem, vb.)\n   into clean ValueMap / ValueRelation dropdown widgets.\n2. Dynamic Default Expressions: Automatically calculates $area (Alan m²), Block/parcel strings,\n   inşaat alanı (kaks * area), taban alanı (taks * area) on feature creation and update.\n3. Statutory Field Constraints: Hard and soft constraints (TAKS <= 1.0, KAKS <= 10.0, Kat >= 1,\n   Çekme >= 0) with clear, actionable Turkish error prompts.\n4. Drag-and-Drop Tabbed Form Layout: Replaces raw attribute lists with an elegant 5-tab form:\n   - Planning function and area\n   - 🏗️ Yapılaşma ve Çekme (PAİY)\n   - Ownership and cadastre\n   - Hazards and geological mitigation\n   - System and metadata\n'

from __future__ import annotations

import contextlib
from typing import Any
from qgis.core import (
    Qgis,
    QgsAttributeEditorContainer,
    QgsAttributeEditorField,
    QgsDefaultValue,
    QgsEditFormConfig,
    QgsEditorWidgetSetup,
    QgsExpression,
    QgsOptionalExpression,
    QgsVectorLayer,
)


# Standard statutory domain value mappings (PAİY & MPYY)
STATUTORY_VALUE_MAPS: dict[str, list[dict[str, str]]] = {
    "nizam": [
        {'Ayrık Nizam (A)': "AYRIK"},
        {'Bitişik Nizam (B)': "BITISIK"},
        {'İkiz Nizam (İ)': "IKIZ"},
        {'Blok Nizam (BL)': "BLOK"},
        {'Serbest Nizam (S)': "SERBEST"},
    ],
    "yapiYaklasmaDurumu": [
        {'Çekme Mesafesi Var': "VAR"},
        {'Özel Çekme Mesafesi Yok': "YOK"},
    ],
    "MULKIYET_TURU": [
        {'Özel Mülkiyet': "OZEL"},
        {'Hazine Mülkiyeti': "HAZINE"},
        {'Belediye Mülkiyeti': "BELEDIYE"},
        {'Vakıf Mülkiyeti': "VAKIF"},
        {'Kamu Terki / Donatı': "KAMU_TERKI"},
        {'Hisseli Mülkiyet': "HISSELI"},
    ],
    "mulkiyet": [
        {'Özel Mülkiyet': "OZEL"},
        {'Hazine Mülkiyeti': "HAZINE"},
        {'Belediye Mülkiyeti': "BELEDIYE"},
        {'Vakıf Mülkiyeti': "VAKIF"},
        {'Kamu Terki / Donatı': "KAMU_TERKI"},
        {'Hisseli Mülkiyet': "HISSELI"},
    ],
    "dop_durumu": [
        {'Madde 18 DOP Uygulandı (İmar Parseli)': "UYGULANDI"},
        {'Madde 18 DOP Bekliyor (Kadastro)': "BEKLIYOR"},
        {'KOP / Kamulaştırma Gerektiren Donatı': "KAMULASTIRMA"},
        {'Düzenleme Dışı / Muaf': "MUAF"},
    ],
    "yerlesime_uygunluk": [
        {'Yerleşime Uygun Alanlar (UA)': "UA"},
        {'Önlemli Alanlar (ÖA)': "OA"},
        {'Ayrıntılı Jeoteknik Etüt Gerektiren Alanlar (AJE)': "AJE"},
        {'Yerleşime Uygun Olmayan Alanlar (UOA)': "UOA"},
    ],
    "B_YAPI_CINSI": [
        {'Betonarme Karkas': "BETONARME"},
        {'Çelik Konstrüksiyon': "CELIK"},
        {'Yığma Yapı': "YIGMA"},
        {'Ahşap Yapı': "AHSAP"},
        {'Prefabrik / Hafif Çelik': "PREFABRIK"},
    ],
    "B_DURUM": [
        {'İyi Durumda (Bakımlı)': "IYI"},
        {'Orta Durumda': "ORTA"},
        {'Kötü Durumda (Bakımsız)': "KOTU"},
        {'Metruk / Harabe': "METRUK"},
    ],
    "B_HASAR_DURUMU": [
        {'Hasarsız': "HASARSIZ"},
        {'Az Hasarlı': "AZ_HASARLI"},
        {'Orta Hasarlı': "ORTA_HASARLI"},
        {'Ağır Hasarlı / Yıkılacak': "AGIR_HASARLI"},
    ],
    "B_TESCIL": [
        {'Tescilsiz Standart Yapı': "HAYIR"},
        {'Tescilli Kültür Varlığı': "EVET"},
    ],
    "yol_kademesi": [
        {"1. Derece Ana Arter / Bulvar (≥30m)": "ANA_ARTER"},
        {'2. Derece Toplayıcı Yol (15m - 25m)': "TOPLAYICI"},
        {'3. Derece Servis Yolu (10m - 12m)': "SERVIS"},
        {'Konut / Çıkmaz Sokak (7m - 8m)': "KONUT_YOLU"},
        {'Yaya Yolu / Meydan / Bölge': "YAYA_YOLU"},
        {"Bisiklet Yolu": "BISIKLET_YOLU"},
    ],
    "kaplama_turu": [
        {'Sıcak Karışım Asfalt (BSK)': "ASFALT"},
        {'Kilitli Parke Taşı': "KILIT_PARKE"},
        {"Beton Kaplama": "BETON"},
        {'Doğal Taş / Granit / Küp Taş': "DOGAL_TAS"},
        {"Stabilize / Toprak": "TOPRAK"},
    ],
}

STATUTORY_FIELD_ALIASES: dict[str, str] = {
    "uipfonksiyon": '🏛️ Plan Fonksiyonu (UİP)',
    "nipfonksiyon": '🏛️ Plan Fonksiyonu (NİP)',
    "gosterim_adi": 'Gösterim Adı',
    "msp_kodu": 'MSP Kodu',
    "fonksiyon_adi": 'Fonksiyon Adı',
    "ustkonugrup": 'Üst Konu Grubu',
    "ust_konu_grup": 'Üst Konu Grubu',
    "detay_katalogu": 'MPYY Detay Kataloğu',
    "alan_m2": 'Parsel / Zon Alanı (m²)',
    "AlanM2": 'Parsel / Zon Alanı (m²)',
    "ALAN": 'Alan (m²)',
    "nizam": '🏗️ Yapı Nizamı (A/B/BL/S)',
    "taks": 'TAKS Oranı',
    "kaks": 'Kat Alanı Katsayısı (KAKS/Emsal)',
    "emsal": 'KAKS DEĞERİ',
    "katadedi": 'Maksimum Kat Sayısı',
    "yencok": 'Yençok DEĞERİ',
    "yapiYaklasmaDurumu": 'Çekme Mesafesi Durumu',
    "yapiYaklasmaMesafesi": 'Yapı Yaklaşma / Çekme (m)',
    "cekme_mesafesi": 'Çekme Mesafesi (m)',
    "toplam_insaat_alani_m2": 'Toplam İnşaat Alanı (m²)',
    "taban_alani_m2": 'Taban Oturum Alanı (m²)',
    "bagimsiz_bolum_sayisi": 'Bağımsız Bölüm Sayısı',
    "ADA": 'İmar / Kadastro Adası',
    "PARSEL": 'İmar / Kadastro Parseli',
    "ada": 'İmar / Kadastro Adası',
    "parsel": 'İmar / Kadastro Parseli',
    "ada_parsel": 'Ada / parsel no',
    "MULKIYET_TURU": 'Mülkiyet Türü',
    "mulkiyet": 'Mülkiyet Türü',
    "malik": 'Taşınmaz Maliki',
    "dop_durumu": 'Madde 18 DOP Statüsü',
    "yerlesime_uygunluk": '⚠️ Yerleşime Uygunluk (Jeoloji)',
    "B_YAPI_CINSI": 'Bina Taşıyıcı Sistemi',
    "B_DURUM": 'Bina Fiziksel Durumu',
    "B_HASAR_DURUMU": 'Afet Hasar Durumu',
    "yolTipi": 'Yol Sınıfı / Tipi',
    "yolGenislik": 'Yol Platform Genişliği (m)',
    "kaldirimGenislik": 'Kaldırım Genişliği (m)',
    "refujGenislik": 'Orta Refüj Genişliği (m)',
    "SolSeritSayisi": 'SOL ŞERİT SAYISI',
    "SagSeritSayisi": 'SAĞ ŞERİT SAYISI',
    "global_id": 'Evrensel Kimlik (UUID)',
    "olusturma_tarihi": 'Kayıt Tarihi',
}


class MPYYFormDesigner:
    """Configures professional QGIS form layouts, value maps, expressions, and validation constraints."""

    @classmethod
    def configure_field_aliases(cls, layer: QgsVectorLayer) -> None:
        """Attach clear, professional Turkish aliases to layer fields."""
        fields = layer.fields()
        for col_name, alias in STATUTORY_FIELD_ALIASES.items():
            idx = fields.indexFromName(col_name)
            if idx >= 0:
                layer.setFieldAlias(idx, alias)

    @classmethod
    def configure_value_maps(cls, layer: QgsVectorLayer) -> None:
        """Attach statutory code-list dropdowns (ValueMap) to layer columns."""
        fields = layer.fields()
        for col_name, val_map in STATUTORY_VALUE_MAPS.items():
            idx = fields.indexFromName(col_name)
            if idx >= 0:
                cfg = {"map": val_map}
                layer.setEditorWidgetSetup(idx, QgsEditorWidgetSetup("ValueMap", cfg))


    @classmethod
    def configure_expressions_and_constraints(cls, layer: QgsVectorLayer) -> None:
        """Apply dynamic QGIS expressions ($area, constructions, IDs) and legislative validation rules."""
        fields = layer.fields()

        # 1. Automatic Area calculation on insert and update
        for a_col in ("alan_m2", "AlanM2", "ALAN"):
            idx = fields.indexFromName(a_col)
            if idx >= 0:
                layer.setDefaultValueDefinition(idx, QgsDefaultValue("round($area, 2)", True))
                layer.setConstraintExpression(idx, f'"{a_col}" IS NULL OR "{a_col}" > 0.0', 'Alan sıfırdan büyük olmalıdır.')

        # 2. Insaat Alani calculation (Area * KAKS)
        insaat_idx = fields.indexFromName("toplam_insaat_alani_m2")
        if insaat_idx >= 0:
            layer.setDefaultValueDefinition(
                insaat_idx,
                QgsDefaultValue('round(coalesce("alan_m2", $area) * coalesce("kaks", "emsal", 1.0), 2)', True),
            )

        # 3. Taban Alani calculation (Area * TAKS)
        taban_idx = fields.indexFromName("taban_alani_m2")
        if taban_idx >= 0:
            layer.setDefaultValueDefinition(
                taban_idx,
                QgsDefaultValue('round(coalesce("alan_m2", $area) * coalesce("taks", 0.35), 2)', True),
            )

        # 4. Ada/Parsel composite string
        ap_idx = fields.indexFromName("ada_parsel")
        if ap_idx >= 0:
            layer.setDefaultValueDefinition(
                ap_idx,
                QgsDefaultValue("concat(coalesce(\"ADA\", '0'), '/', coalesce(\"PARSEL\", '0'))", True),
            )

        # 5. TAKS Constraint (PAİY Md. 5: 0.00 < TAKS <= 1.00)
        taks_idx = fields.indexFromName("taks")
        if taks_idx >= 0:
            layer.setConstraintExpression(
                taks_idx,
                '"taks" IS NULL OR ("taks" > 0.0 AND "taks" <= 1.0)',
                'PAİY Madde 5: TAKS (Taban Alanı Katsayısı) 0.00 ile 1.00 arasında olmalıdır.',
            )

        # 6. KAKS/Emsal Constraint (0.00 < KAKS <= 10.00)
        for k_col in ("kaks", "emsal"):
            k_idx = fields.indexFromName(k_col)
            if k_idx >= 0:
                layer.setConstraintExpression(
                    k_idx,
                    f'"{k_col}" IS NULL OR ("{k_col}" > 0.0 AND "{k_col}" <= 10.0)',
                    'KAKS (Emsal) katsayısı 0.00 ile 10.00 arasında olmalıdır.',
                )

        # 7. Kat Adedi Constraint (Kat >= 1)
        for c_col in ("katadedi", "yencok", "kat", "P_KAT", "B_KAT"):
            c_idx = fields.indexFromName(c_col)
            if c_idx >= 0:
                layer.setConstraintExpression(
                    c_idx,
                    f'"{c_col}" IS NULL OR "{c_col}" >= 1',
                    'Kat adedi en az 1 olmalıdır.',
                )

        # 8. Çekme Mesafesi Constraint (Mesafesi >= 0)
        for ym_col in ("yapiYaklasmaMesafesi", "cekme_mesafesi", "P_CEKME"):
            ym_idx = fields.indexFromName(ym_col)
            if ym_idx >= 0:
                layer.setConstraintExpression(
                    ym_idx,
                    f'"{ym_col}" IS NULL OR "{ym_col}" >= 0.0',
                    'Çekme mesafesi negatif olamaz.',
                )

    @classmethod
    def configure_tabbed_drag_and_drop_form(cls, layer: QgsVectorLayer) -> None:
        """Construct an authentic, categorized 5-tab drag-and-drop form layout."""
        fields = layer.fields()
        if fields.isEmpty():
            return

        form_config = layer.editFormConfig()
        layout_val = (
            Qgis.AttributeFormLayout.DragAndDrop
            if hasattr(Qgis, "AttributeFormLayout")
            else QgsEditFormConfig.TabLayout
        )
        form_config.setLayout(layout_val)
        form_config.clearTabs()

        root = form_config.invisibleRootContainer()

        tab_specs = [
            (
                'Plan fonksiyonu ve alanı',
                [
                    ('Fonksiyon ve imar tanımı', ["uipfonksiyon", "nipfonksiyon", "fonksiyon_adi", "gosterim_adi", "msp_kodu", "ustkonugrup", "ust_konu_grup", "detay_katalogu", "P_FONK", "B_FONK", "aciklama"]),
                    ('Boyutlar ve alan', ["alan_m2", "AlanM2", "ALAN", "alan_hektar", "yogunluk_kademesi", "brut_yogunluk_kisi_ha"]),
                ],
            ),
            (
                'Yapılaşma ve çekme koşulları (PAİY)',
                [
                    ('İmar Yoğunluğu Parametreleri', ["nizam", "taks", "kaks", "emsal", "katadedi", "yencok", "kat", "P_KAT", "B_KAT"]),
                    ('Yapı çekme sınırları', ["yapiYaklasmaDurumu", "yapiYaklasmaMesafesi", "cekme_mesafesi", "P_CEKME", "onBahce", "yanBahce", "arkaBahce"]),
                    ('İnşaat ve taban alanı', ["toplam_insaat_alani_m2", "taban_alani_m2", "bagimsiz_bolum_sayisi", "P_BAGIMSIZ_BOLUM"]),
                ],
            ),
            (
                '📜 Mülkiyet ve Kadastro',
                [
                    ('Kadastro Tanımları', ["ADA", "PARSEL", "ada", "parsel", "ada_parsel", "MAHALLE", "mahalle", "pafta"]),
                    ('Mülkiyet ve Hakediş', ["MULKIYET_TURU", "mulkiyet", "malik", "dop_durumu", "tapunoktasi", "P_NUFUS"]),
                ],
            ),
            (
                '⚠️ Afet ve Jeolojik Önlemler',
                [
                    ('Yerleşime Uygunluk ve Zemin', ["yerlesime_uygunluk", "zemin_grubu", "jeolojik_aciklama", "afet_riski"]),
                    ('Yapının fiziksel durumu', ["B_YAPI_CINSI", "B_DURUM", "B_HASAR_DURUMU", "B_YAS", "B_TESCIL", "QC"]),
                ],
            ),
            (
                'ℹ️ Sistem ve Metaveriler',
                [
                    ('Sistem Kimlikleri', ["global_id", "dataset_id", "plan_kademesi", "olusturma_tarihi", "guncelleme_tarihi", "tarih"]),
                ],
            ),
        ]

        added_field_names: set[str] = set()

        for tab_title, groups in tab_specs:
            tab_container = QgsAttributeEditorContainer(tab_title, root)
            if hasattr(Qgis, "AttributeEditorContainerType"):
                tab_container.setType(Qgis.AttributeEditorContainerType.Tab)
            else:
                tab_container.setIsGroupBox(False)

            has_tab_fields = False

            for grp_title, col_candidates in groups:
                grp_container = QgsAttributeEditorContainer(grp_title, tab_container)
                if hasattr(Qgis, "AttributeEditorContainerType"):
                    grp_container.setType(Qgis.AttributeEditorContainerType.GroupBox)
                else:
                    grp_container.setIsGroupBox(True)

                has_grp_fields = False
                for col_name in col_candidates:
                    idx = fields.indexFromName(col_name)
                    if idx >= 0:
                        # Conditional Visibility: PAİY Bitişik nizamda yan bahçe çekmesi olmaz
                        if col_name in ("yanBahce", "P_YAN_BAHCE") and fields.indexFromName("nizam") >= 0:
                            yan_sub = QgsAttributeEditorContainer('YAN BAHÇE MESAFESİ', grp_container)
                            if hasattr(Qgis, "AttributeEditorContainerType"):
                                yan_sub.setType(Qgis.AttributeEditorContainerType.Row)
                            else:
                                yan_sub.setIsGroupBox(False)
                            yan_expr = QgsOptionalExpression(
                                QgsExpression("coalesce(\"nizam\", '') != 'BITISIK'"), True
                            )
                            yan_sub.setVisibilityExpression(yan_expr)
                            yan_sub.addChildElement(QgsAttributeEditorField(col_name, idx, yan_sub))
                            grp_container.addChildElement(yan_sub)
                        else:
                            grp_container.addChildElement(QgsAttributeEditorField(col_name, idx, grp_container))

                        added_field_names.add(col_name)
                        has_grp_fields = True

                if has_grp_fields:
                    tab_container.addChildElement(grp_container)
                    has_tab_fields = True

            if has_tab_fields:
                root.addChildElement(tab_container)

        # If any miscellaneous columns exist that were not explicitly listed, collect them into an Ekstra tab
        remaining_cols = [f.name() for f in fields if f.name() not in added_field_names]
        if remaining_cols:
            misc_tab = QgsAttributeEditorContainer('📋 Diğer Nitelikler', root)
            if hasattr(Qgis, "AttributeEditorContainerType"):
                misc_tab.setType(Qgis.AttributeEditorContainerType.Tab)
            else:
                misc_tab.setIsGroupBox(False)

            misc_grp = QgsAttributeEditorContainer('Ekstra Alanlar', misc_tab)
            if hasattr(Qgis, "AttributeEditorContainerType"):
                misc_grp.setType(Qgis.AttributeEditorContainerType.GroupBox)
            else:
                misc_grp.setIsGroupBox(True)

            for col_name in remaining_cols:
                idx = fields.indexFromName(col_name)
                misc_grp.addChildElement(QgsAttributeEditorField(col_name, idx, misc_grp))

            misc_tab.addChildElement(misc_grp)
            root.addChildElement(misc_tab)

        layer.setEditFormConfig(form_config)

    @classmethod
    def apply_complete_form_experience(cls, layer: QgsVectorLayer) -> None:
        """Apply the entire suite of ValueMaps, expressions, constraints, and tabbed forms."""
        if not layer or not layer.isValid():
            return
        if layer.customProperty("mpyy/form"):
            # The layer already carries an authored QML form (MpyyUipDb template or
            # survey form). Rebuilding tabs and value maps here would replace its
            # conditional tabs and write dropdown codes its own schema rejects.
            return
        cls.configure_field_aliases(layer)
        cls.configure_value_maps(layer)
        cls.configure_expressions_and_constraints(layer)
        cls.configure_tabbed_drag_and_drop_form(layer)
        from .localization import configure_localized_layer
        configure_localized_layer(layer)
