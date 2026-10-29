"""MapTips, QGIS Layer Actions, and Setback Geometry Tools for MPYY Layers."""

import re
from qgis.core import (
    QgsAction,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
)

from .attr_utils import is_null_value
from .localization import display_expression, display_label

_MANAGED_ACTION_NAMES = frozenset({
    "Google Street View Aç",
    "TKGM Parsel Sorgu Aç",
    "Öznitelik Özetini Panoya Kopyala",
})


def _localized_template(template, layer=None):
    """Use native editor representations for codes, keeping conditional tests raw and missing columns NULL."""
    fields = {
        'uipfonksiyon', 'nipfonksiyon', 'fonksiyon_adi', 'gosterim_adi', 'msp_kodu',
        'ustkonugrup', 'ust_grup_adi', 'nizam', 'yogunluk_kademesi', 'P_FONK',
        'MULKIYET_TURU', 'B_FONK', 'B_DURUM', 'B_YAPI_CINSI', 'B_HASAR_DURUMU',
        'B_TESCIL', 'Y_TIP', 'Y_KAPLAMA', 'QC',
    }
    expressions = {}
    present_cols = None
    if layer is not None:
        present_cols = set(layer.fields().names())
        for name in fields:
            index = layer.fields().indexFromName(name)
            if index < 0:
                continue
            setup = layer.editorWidgetSetup(index)
            config = setup.config()
            labels = {}
            if setup.type() == 'ValueMap':
                entries = config.get('map', [])
                if isinstance(entries, dict):
                    entries = [entries]
                labels = {
                    str(value): display_label(label)
                    for entry in entries
                    for label, value in entry.items()
                    if not is_null_value(value)
                }
            elif setup.type() == 'RelationReference':
                lookup = QgsProject.instance().mapLayer(config.get('ReferencedLayerId', ''))
                relation = QgsProject.instance().relationManager().relation(config.get('Relation', ''))
                if lookup and relation.isValid():
                    column = next(iter(relation.fieldPairs().values()))
                    col_idx = lookup.fields().indexFromName(column)
                    if col_idx >= 0:
                        labels = {
                            str(value): display_label(value)
                            for value in lookup.uniqueValues(col_idx)
                            if not is_null_value(value)
                        }
            values = layer.uniqueValues(index)
            labels.update({
                str(value): display_label(value)
                for value in values
                if not is_null_value(value) and str(value) not in labels
            })
            expressions[name] = '(' + display_expression(name, labels, labels) + ')'

    def display(field):
        name = field.group(1)
        if present_cols is not None and name not in present_cols:
            return 'NULL'
        column = '"' + name + '"'
        return expressions.get(name, 'represent_value(' + column + ')') if name in fields else column

    def transform_expr_block(block_match):
        expr = block_match.group(1)
        expr = re.sub(r'coalesce\([^)]*\)', lambda m: re.sub(r'"([^"]+)"', display, m.group(0)), expr)
        expr = re.sub(
            r'\|\|\s*"([^"]+)"\s*\|\|',
            lambda field: '|| ' + display(field) + ' ||' if field.group(1) in fields else field.group(0),
            expr,
        )
        if present_cols is not None:
            expr = re.sub(
                r'"([^"]+)"',
                lambda m: m.group(0) if m.group(1) in present_cols else 'NULL',
                expr,
            )
        return '[%' + expr + '%]'

    template = re.sub(r'\[%(.*?)%\]', transform_expr_block, template, flags=re.DOTALL)
    return (
        template.replace("'ÖZEL'", "'Özel'")
        .replace("'YAPI'", "'Yapı'")
        .replace("'HASARSIZ'", "'Hasarsız'")
        .replace("'HAYIR'", "'Hayır'")
    )


def generate_uip_maptip_html(layer=None) -> str:
    """Return responsive, publication-grade HTML MapTip card for UİP alan layers."""
    return _localized_template(
        '<div style="font-family: \'Segoe UI\', Arial, sans-serif; font-size: 11px; background: #ffffff; color: #2b2b2b; border: 1px solid #c0c0c0; border-radius: 4px; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); width: 260px; overflow: hidden;">\n'
        '  <div style="background: #1a5276; color: #ffffff; padding: 6px 10px; font-weight: bold; font-size: 12px;">\n'
        '    [% coalesce("uipfonksiyon", "fonksiyon_adi", \'Fonksiyon belirtilmemiş\') %]\n'
        '  </div>\n'
        '  <div style="padding: 8px 10px;">\n'
        '    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Üst Grup:</td><td style="font-weight: bold; text-align: right;">[% coalesce("ustkonugrup", "ust_grup_adi", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Alan (m²):</td><td style="font-weight: bold; text-align: right;">[% format_number(coalesce("AlanM2", "alan_m2", $area), 1) %] m²</td></tr>\n'
        '      [% CASE WHEN "nizam" IS NOT NULL THEN \'<tr><td style="color: #666; padding: 2px 0;">Yapı Nizamı:</td><td style="font-weight: bold; color: #b03a2e; text-align: right;">\' || "nizam" || \'</td></tr>\' ELSE \'\' END %]\n'
        '      [% CASE WHEN "taks" IS NOT NULL THEN \'<tr><td style="color: #666; padding: 2px 0;">TAKS:</td><td style="font-weight: bold; text-align: right;">\' || "taks" || \'</td></tr>\' ELSE \'\' END %]\n'
        '      [% CASE WHEN coalesce("emsal", "kaks") IS NOT NULL THEN \'<tr><td style="color: #666; padding: 2px 0;">KAKS (Emsal):</td><td style="font-weight: bold; text-align: right;">\' || coalesce("emsal", "kaks", \'-\') || \'</td></tr>\' ELSE \'\' END %]\n'
        '      [% CASE WHEN coalesce("katadedi", "yencok") IS NOT NULL THEN \'<tr><td style="color: #666; padding: 2px 0;">Kat Adedi / Yençok:</td><td style="font-weight: bold; text-align: right;">\' || coalesce("katadedi", "yencok", \'-\') || \'</td></tr>\' ELSE \'\' END %]\n'
        '      [% CASE WHEN "yapiYaklasmaDurumu" = \'VAR\' THEN \'<tr><td style="color: #666; padding: 2px 0;">Çekme Mesafesi:</td><td style="font-weight: bold; color: #1e8449; text-align: right;">\' || coalesce("yapiYaklasmaMesafesi", 0) || \' m</td></tr>\' ELSE \'\' END %]\n'
        '    </table>\n'
        '  </div>\n'
        '</div>',
        layer,
    )


def generate_nip_maptip_html(layer=None) -> str:
    """Return HTML MapTip card for NİP alan layers."""
    return _localized_template(
        '<div style="font-family: \'Segoe UI\', Arial, sans-serif; font-size: 11px; background: #ffffff; color: #2b2b2b; border: 1px solid #c0c0c0; border-radius: 4px; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); width: 260px; overflow: hidden;">\n'
        '  <div style="background: #784212; color: #ffffff; padding: 6px 10px; font-weight: bold; font-size: 12px;">\n'
        '    [% coalesce("nipfonksiyon", "fonksiyon_adi", \'NAZIM İMAR PLANI ALANI\') %]\n'
        '  </div>\n'
        '  <div style="padding: 8px 10px;">\n'
        '    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Yoğunluk:</td><td style="font-weight: bold; text-align: right;">[% coalesce("yogunluk_kademesi", "UST_SNR", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Brüt Yoğunluk:</td><td style="font-weight: bold; text-align: right;">[% coalesce("brut_yogunluk_kisi_ha", "UST_SNR", \'-\') %] k/ha</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Alan:</td><td style="font-weight: bold; text-align: right;">[% format_number(coalesce("alan_m2", $area), 1) %] m²</td></tr>\n'
        '    </table>\n'
        '  </div>\n'
        '</div>',
        layer,
    )


def generate_parsel_saha_maptip_html(layer=None) -> str:
    """Return responsive HTML MapTip card for surveyed parcel layers."""
    return _localized_template(
        '<div style="font-family: \'Segoe UI\', Arial, sans-serif; font-size: 11px; background: #ffffff; color: #2b2b2b; border: 1px solid #d4ac0d; border-radius: 4px; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); width: 270px; overflow: hidden;">\n'
        '  <div style="background: #b7950b; color: #ffffff; padding: 6px 10px; font-weight: bold; font-size: 12px;">\n'
        '    Ada/Parsel: [% coalesce("ADA", \'-\') %] / [% coalesce("PARSEL", \'-\') %] &bull; [% coalesce("MAHALLE", \'-\') %]\n'
        '  </div>\n'
        '  <div style="padding: 8px 10px;">\n'
        '    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Kullanım:</td><td style="font-weight: bold; text-align: right; color: #7d6608;">[% coalesce("P_FONK", \'Belirtilmemiş\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Mülkiyet:</td><td style="font-weight: bold; text-align: right;">[% coalesce("MULKIYET_TURU", \'Özel\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Parsel Alanı:</td><td style="font-weight: bold; text-align: right;">[% format_number(coalesce("alan_m2", $area), 1) %] m²</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Kat / Yapı Adedi:</td><td style="font-weight: bold; text-align: right;">[% coalesce("P_KAT", \'-\') %] Kat / [% coalesce("P_YAPI_ADET", 1) %] yapı</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Nüfus / B.Bölüm:</td><td style="font-weight: bold; text-align: right;">[% coalesce("P_NUFUS", 0) %] Kişi / [% coalesce("P_BAGIMSIZ_BOLUM", 0) %] bağımsız bölüm</td></tr>\n'
        '      [% CASE WHEN "QC" IS NOT NULL AND "QC" != \'OK\' THEN \'<tr><td style="color: #c0392b; padding: 2px 0;">Kalite Kontrol:</td><td style="font-weight: bold; color: #c0392b; text-align: right;">\' || "QC" || \'</td></tr>\' ELSE \'\' END %]\n'
        '    </table>\n'
        '  </div>\n'
        '</div>',
        layer,
    )


def generate_yapi_saha_maptip_html(layer=None) -> str:
    """Return responsive HTML MapTip card for surveyed building layers."""
    return _localized_template(
        '<div style="font-family: \'Segoe UI\', Arial, sans-serif; font-size: 11px; background: #ffffff; color: #2b2b2b; border: 1px solid #7d3c98; border-radius: 4px; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); width: 270px; overflow: hidden;">\n'
        '  <div style="background: #6c3483; color: #ffffff; padding: 6px 10px; font-weight: bold; font-size: 12px;">\n'
        '    Bina: [% coalesce("B_FONK", \'Yapı\') %] ([% coalesce("B_KAT", 1) %] Kat)\n'
        '  </div>\n'
        '  <div style="padding: 8px 10px;">\n'
        '    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Ada/Parsel:</td><td style="font-weight: bold; text-align: right;">[% coalesce("ADA", \'-\') %] / [% coalesce("PARSEL", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Yapı Durumu:</td><td style="font-weight: bold; text-align: right;">[% coalesce("B_DURUM", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Taşıyıcı Cinsi:</td><td style="font-weight: bold; text-align: right;">[% coalesce("B_YAPI_CINSI", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Bina Yaşı:</td><td style="font-weight: bold; text-align: right;">[% coalesce("B_YAS", \'-\') %] yıl</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Taban Alanı:</td><td style="font-weight: bold; text-align: right;">[% format_number(coalesce("alan_m2", $area), 1) %] m²</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Hasar / Tescil:</td><td style="font-weight: bold; text-align: right;">[% coalesce("B_HASAR_DURUMU", \'Hasarsız\') %] / [% coalesce("B_TESCIL", \'Hayır\') %]</td></tr>\n'
        '    </table>\n'
        '  </div>\n'
        '</div>',
        layer,
    )


def generate_yol_saha_maptip_html(layer=None) -> str:
    """Return responsive HTML MapTip card for surveyed road layers."""
    return _localized_template(
        '<div style="font-family: \'Segoe UI\', Arial, sans-serif; font-size: 11px; background: #ffffff; color: #2b2b2b; border: 1px solid #922b21; border-radius: 4px; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); width: 260px; overflow: hidden;">\n'
        '  <div style="background: #922b21; color: #ffffff; padding: 6px 10px; font-weight: bold; font-size: 12px;">\n'
        '    [% coalesce("Y_AD", \'İsimsiz yol kesimi\') %]\n'
        '  </div>\n'
        '  <div style="padding: 8px 10px;">\n'
        '    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Kademesi:</td><td style="font-weight: bold; text-align: right;">[% coalesce("Y_TIP", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Kaplama Türü:</td><td style="font-weight: bold; text-align: right;">[% coalesce("Y_KAPLAMA", \'-\') %]</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Genişlik:</td><td style="font-weight: bold; text-align: right;">[% coalesce("Y_GENISLIK", \'-\') %] m</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Segment Boyu:</td><td style="font-weight: bold; text-align: right;">[% format_number(coalesce("uzunluk_m", $length), 1) %] m</td></tr>\n'
        '      <tr><td style="color: #666; padding: 2px 0;">Kaldırım / Şerit:</td><td style="font-weight: bold; text-align: right;">[% coalesce("Y_KALDIRIM_GEN", 0) %] m / [% coalesce("Y_SERIT", 2) %] şerit</td></tr>\n'
        '    </table>\n'
        '  </div>\n'
        '</div>',
        layer,
    )


def attach_layer_actions(layer: QgsVectorLayer) -> int:
    """Attach standard urban planning actions (TKGM, Google Street View, Clipboard, Setbacks) to layer."""
    if not layer or not layer.isValid():
        return 0

    actions = layer.actions()
    for existing in list(actions.actions()):
        if existing.name() in _MANAGED_ACTION_NAMES:
            actions.removeAction(existing.id())

    pt_wgs84 = "transform(point_on_surface($geometry), @layer_crs, 'EPSG:4326')"

    # 1. Google Street View / Maps Link Action
    view_action = QgsAction(
        QgsAction.ActionType.OpenUrl,
        'Google Street View Aç',
        f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=[% y({pt_wgs84}) %],[% x({pt_wgs84}) %]",
        "",
        False,
        'Google Sokak Görünümünü tarayıcıda açar',
    )
    actions.addAction(view_action)

    # 2. TKGM Parsel Sorgu Link Action
    tkgm_action = QgsAction(
        QgsAction.ActionType.OpenUrl,
        'TKGM Parsel Sorgu Aç',
        f"https://parselsorgu.tkgm.gov.tr/#ara/cografi/[% y({pt_wgs84}) %]/[% x({pt_wgs84}) %]",
        "",
        False,
        'Konumun TKGM kadastro kaydını sorgular',
    )
    actions.addAction(tkgm_action)

    # 3. Panoya Kopyalama (Injection-safe Python Action via @layer_id and $id)
    copy_script = (
        "from qgis.core import QgsProject\n"
        "from qgis.PyQt.QtWidgets import QApplication\n"
        "_lyr = QgsProject.instance().mapLayer('[% @layer_id %]')\n"
        "_raw_id = '[% $id %]'.strip()\n"
        "_fid = int(_raw_id) if _raw_id.lstrip('-').isdigit() else -1\n"
        "_feat = _lyr.getFeature(_fid) if (_lyr is not None and _fid >= 0) else None\n"
        "if _feat is not None and _feat.isValid():\n"
        "    _fn = '-'\n"
        "    for _k in ('uipfonksiyon', 'nipfonksiyon', 'fonksiyon_adi', 'gosterim_adi', 'P_FONK', 'B_FONK', 'Y_AD'):\n"
        "        _i = _feat.fields().indexFromName(_k)\n"
        "        if _i >= 0 and _feat[_i] is not None and str(_feat[_i]).strip() not in ('', 'NULL'):\n"
        "            _fn = str(_feat[_i]).strip()\n"
        "            break\n"
        "    _area = round(_feat.geometry().area(), 1) if not _feat.geometry().isEmpty() else 0.0\n"
        "    QApplication.clipboard().setText(f'Fonksiyon: {_fn} | Alan: {_area} m²')\n"
    )
    copy_action = QgsAction(
        QgsAction.ActionType.GenericPython,
        'Öznitelik Özetini Panoya Kopyala',
        copy_script,
        "",
        False,
        'Seçilen nesnenin plan fonksiyonu ve alan bilgisini panoya kopyalar',
    )
    actions.addAction(copy_action)

    # Configure MapTip
    lname = layer.name().lower()
    col_names = set(layer.fields().names())
    if "uip" in lname or "uipfonksiyon" in col_names:
        layer.setMapTipTemplate(generate_uip_maptip_html(layer))
    elif "nip" in lname or "5000" in lname or "nipfonksiyon" in col_names:
        layer.setMapTipTemplate(generate_nip_maptip_html(layer))
    elif lname == "parsel_saha":
        layer.setMapTipTemplate(generate_parsel_saha_maptip_html(layer))
    elif lname == "yapi_saha":
        layer.setMapTipTemplate(generate_yapi_saha_maptip_html(layer))
    elif lname == "yol_saha":
        layer.setMapTipTemplate(generate_yol_saha_maptip_html(layer))

    return len(actions.actions())


def calculate_setback_envelope(parcel_geometry: QgsGeometry, setback_distance_m: float) -> QgsGeometry:
    """Calculate the inner building footprint envelope using negative buffer for setbacks."""
    if not parcel_geometry or parcel_geometry.isEmpty() or setback_distance_m <= 0:
        return parcel_geometry

    inner_envelope = parcel_geometry.buffer(-abs(setback_distance_m), 5)
    return inner_envelope if not inner_envelope.isEmpty() else QgsGeometry()
