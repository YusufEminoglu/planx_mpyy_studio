"""Turkish display labels independent of statutory identities and stored values."""
from pathlib import Path
import re
import unicodedata


def label_key(text):
    text = str(text).strip().replace('ı', 'i').upper()
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c))


def label_fold(text):
    """Letters-only key: two spellings of one label compare equal.

    Ek-1e prints the same catalog label with and without the Turkish dotted İ
    ('DENIZYOLLARI' for 'DENİZYOLLARI'), and one label runs its words together.
    Folding case, spacing, punctuation and the İ/ı dots away is what makes those
    compare as one label instead of two, so a catalog compiler can prove it
    ships one spelling per label.  `label_key` cannot do that job: it keeps
    spaces, which is right for looking up a printed label and wrong for
    deciding whether two labels are the same.
    """
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).upper()) if c.isalnum())


LABELS = {}
for line in (Path(__file__).resolve().parents[1] / 'resources' / 'turkish_labels.tsv').read_text(encoding='utf-8').splitlines():
    if '\t' in line:
        key, value = line.split('\t', 1)
        LABELS[key] = value


def display_label(value):
    """Translate known plugin labels; keep names and supplied data verbatim."""
    if value is None:
        return ''
    text = str(value)
    page = re.match(r'^(.*) \([sp]\.(\d+)\)$', text)
    if page:
        return display_label(page.group(1)) + ' (s.' + page.group(2) + ')'
    key = label_key(text)
    if key in LABELS:
        return LABELS[key]
    key = key.replace('_', ' ')
    for prefix in ('CDP ', 'NIP ', 'MNIP ', 'UIP ', 'MSP '):
        if key.startswith(prefix):
            key = key[len(prefix):]
            break
    for candidate in (key, key + ' ALANI', key + ' ALAN'):
        if candidate in LABELS:
            return LABELS[candidate]
    for separator in (' — ', ' - ', ' | ', ': '):
        if separator in text:
            return separator.join(display_label(part) for part in text.split(separator))
    return text


FIELD_WORDS = {'alan': 'alan', 'alani': 'alanı', 'adi': 'adı', 'ad': 'ad', 'kodu': 'kodu', 'kod': 'kod', 'ust': 'üst', 'alt': 'alt', 'grup': 'grup', 'konu': 'konu', 'fonksiyon': 'fonksiyon', 'detay': 'ayrıntı', 'katalogu': 'kataloğu', 'kademesi': 'kademesi', 'yerlesme': 'yerleşme', 'yogunlugu': 'yoğunluğu', 'asamasi': 'aşaması', 'olusturan': 'oluşturan', 'olusturma': 'oluşturma', 'guncelleyen': 'güncelleyen', 'guncelleme': 'güncelleme', 'tarihi': 'tarihi', 'tarih': 'tarih', 'aciklama': 'açıklama', 'gosterim': 'gösterim', 'lejant': 'lejant', 'parsel': 'parsel', 'ada': 'ada', 'mahalle': 'mahalle', 'yapi': 'yapı', 'yapiyaklasma': 'yapı yaklaşma', 'yaklasma': 'yaklaşma', 'mesafesi': 'mesafesi', 'durumu': 'durumu', 'durum': 'durum', 'yol': 'yol', 'tipi': 'tipi', 'turu': 'türü', 'nizam': 'nizam', 'kat': 'kat', 'adedi': 'adedi', 'adet': 'adet', 'sayisi': 'sayısı', 'yencok': 'en çok yükseklik', 'katadedi': 'kat adedi', 'katadeti': 'kat adedi', 'kullanim': 'kullanım', 'mulkiyet': 'mülkiyet', 'malik': 'malik', 'yan': 'yan', 'on': 'ön', 'arka': 'arka', 'bahce': 'bahçe', 'brut': 'brüt', 'yogunluk': 'yoğunluk', 'kisi': 'kişi', 'nufus': 'nüfus', 'toplam': 'toplam', 'ortalama': 'ortalama', 'taban': 'taban', 'insaat': 'inşaat', 'bagimsiz': 'bağımsız', 'bolum': 'bölüm', 'bina': 'bina', 'sinif': 'sınıf', 'cinsi': 'cinsi', 'tasiyici': 'taşıyıcı', 'hasar': 'hasar', 'isitma': 'ısıtma', 'cati': 'çatı', 'yas': 'yaş', 'yasi': 'yaşı', 'kalite': 'kalite', 'kalitesi': 'kalitesi', 'kaplama': 'kaplama', 'koruma': 'koruma', 'saha': 'saha', 'genislik': 'genişlik', 'genisligi': 'genişliği', 'uzunluk': 'uzunluk', 'refuj': 'refüj', 'kaldirim': 'kaldırım', 'serit': 'şerit', 'sol': 'sol', 'sag': 'sağ', 'tapu': 'tapu', 'tescil': 'tescil', 'yerlesime': 'yerleşime', 'uygunluk': 'uygunluk', 'uygunlugu': 'uygunluğu', 'emsal': 'emsal', 'kaks': 'emsal (KAKS)', 'taks': 'taban alanı oranı (TAKS)', 'fark': 'fark', 'sonuc': 'sonuç', 'not': 'not', 'notlar': 'notlar', 'kontrol': 'denetim', 'hata': 'hata', 'oran': 'oran', 'orani': 'oranı', 'gereken': 'gereken', 'mevcut': 'mevcut', 'eksik': 'eksik', 'konut': 'konut', 'ticaret': 'ticaret', 'donati': 'donatı', 'net': 'net', 'otopark': 'otopark', 'siginak': 'sığınak', 'hak': 'hak', 'hakedis': 'hakediş', 'sinifi': 'sınıfı', 'geometri': 'geometri', 'tarama': 'tarama', 'sinir': 'sınır', 'tabaka': 'tabaka', 'tanim': 'tanım', 'kural': 'kural', 'strateji': 'strateji', 'bolgesi': 'bölgesi', 'bolge': 'bölge', 'oncelik': 'öncelik', 'hat': 'hat', 'koridor': 'koridor', 'odak': 'odak', 'kademelenme': 'kademelenme', 'etiket': 'etiket', 'ozel': 'özel', 'hukum': 'hüküm', 'var': 'var', 'mi': 'mi', 'kusak': 'kuşak', 'merkez': 'merkez', 'etap': 'etap', 'basina': 'başına', 'kullanici': 'kullanıcı', 'tarihilk': 'ilk kayıt tarihi', 'tarihson': 'son güncelleme tarihi', 'ongorulen': 'öngörülen', 'ana': 'ana', 'renk': 'renk', 'fotograf': 'fotoğraf', 'duzenleyen': 'düzenleyen', 'fonk': 'fonksiyon', 'fiziki': 'fiziki', 'fiziksel': 'fiziksel', 'afet': 'afet', 'cadde': 'cadde', 'sokak': 'sokak', 'acigi': 'açığı', 'yesil': 'yeşil', 'gerekli': 'gerekli', 'hesaplanan': 'hesaplanan', 'hakim': 'hâkim', 'maks': 'azami', 'riskli': 'riskli', 'uygun': 'uygun', 'yapilasabilir': 'yapılaşabilir', 'tevhid': 'tevhit', 'zorunlu': 'zorunlu', 'ifraz': 'ifraz', 'edilebilir': 'edilebilir', 'cekme': 'çekme', 'yetersiz': 'yetersiz', 'fonksiyonu': 'fonksiyonu', 'grubu': 'grubu', 'poligon': 'poligon', 'cizgi': 'çizgi', 'esdeger': 'eşdeğer', 'madde': 'madde', 'notu': 'notu', 'miktari': 'miktarı', 'puan': 'puan', 'puani': 'puanı', 'oneri': 'öneri', 'kaynak': 'kaynak', 'area': 'alan', 'name': 'ad', 'title': 'başlık', 'code': 'kod', 'function': 'fonksiyon', 'status': 'durum', 'result': 'sonuç', 'layer': 'katman', 'source': 'kaynak', 'target': 'hedef', 'network': 'ağ', 'node': 'düğüm', 'edge': 'kenar', 'distance': 'mesafe', 'length': 'uzunluk', 'width': 'genişlik', 'height': 'yükseklik', 'floor': 'kat', 'floors': 'katlar', 'count': 'sayı', 'total': 'toplam', 'mean': 'ortalama', 'average': 'ortalama', 'population': 'nüfus', 'weight': 'ağırlık', 'value': 'değer', 'ratio': 'oran', 'baseline': 'başlangıç', 'proposed': 'önerilen', 'scenario': 'senaryo', 'facility': 'tesis', 'demand': 'talep', 'mode': 'ulaşım türü', 'time': 'süre', 'speed': 'hız', 'access': 'erişim', 'accessibility': 'erişilebilirlik', 'equity': 'eşitlik', 'score': 'puan', 'priority': 'öncelik', 'type': 'tür', 'class': 'sınıf', 'group': 'grup', 'description': 'açıklama', 'note': 'not', 'issue': 'sorun', 'error': 'hata', 'date': 'tarih', 'year': 'yıl', 'version': 'sürüm', 'parcel': 'parsel', 'building': 'yapı', 'road': 'yol', 'land': 'arazi', 'use': 'kullanım', 'id': 'kimlik', 'added': 'eklenen', 'addition': 'ilave', 'adjacent': 'komşu', 'agirligi': 'ağırlığı', 'arac': 'araç', 'article': 'madde', 'article12': '12. madde', 'articles': 'maddeler', 'aspect': 'en-boy', 'audit': 'denetim', 'basis': 'dayanak', 'birim': 'birim', 'bylaw': 'belediye düzenlemesi', 'catalog': 'katalog', 'categories': 'kategoriler', 'changed': 'değişen', 'ciddiyet': 'ciddiyet', 'codes': 'kodlar', 'compactness': 'kompaktlık', 'compliant': 'uygun', 'component': 'bileşen', 'conflicting': 'çakışan', 'contiguous': 'bitişik', 'coverage': 'kapsama', 'crosswalk': 'kod eşlemesi', 'dead': 'çıkmaz', 'degeri': 'değeri', 'degisim': 'değişim', 'delta': 'fark', 'depth': 'derinlik', 'effective': 'geçerli', 'end': 'uç', 'esik': 'eşik', 'esitlik': 'eşitlik', 'exception': 'istisna', 'fabric': 'doku', 'farki': 'farkı', 'finding': 'bulgu', 'findings': 'bulgular', 'footprint': 'taban alanı', 'front': 'ön', 'frontage': 'cephe', 'gap': 'boşluk', 'gosterge': 'gösterge', 'gross': 'brüt', 'ihtiyaci': 'ihtiyacı', 'intervention': 'müdahale', 'invalid': 'geçersiz', 'is': 'durumu', 'karsilama': 'karşılama', 'legend': 'lejant', 'levels': 'kat sayısı', 'link': 'bağlantı', 'matched': 'eşleşen', 'max': 'azami', 'min': 'asgari', 'missing': 'eksik', 'mix': 'karma', 'modes': 'ulaşım türleri', 'monitor': 'izleme', 'muteahhit': 'müteahhit', 'normalized': 'normalleştirilmiş', 'notes': 'notlar', 'onceki': 'önceki', 'overlap': 'örtüşme', 'parent': 'üst', 'part': 'parça', 'profile': 'profil', 'progress': 'ilerleme', 'removed': 'kaldırılan', 'required': 'gerekli', 'revision': 'revizyon', 'rise': 'yükselme', 'roof': 'çatı', 'route': 'güzergâh', 'rule': 'kural', 'rules': 'kurallar', 'satir': 'satır', 'scope': 'kapsam', 'seam': 'ortak sınır', 'service': 'hizmet', 'sira': 'sıra', 'size': 'boyut', 'snap': 'yakalama', 'sutun': 'sütun', 'threshold': 'eşik', 'top': 'üst', 'triggers': 'tetikleyiciler', 'violation': 'ihlal', 'violations': 'ihlaller', 'volume': 'hacim', 'wall': 'duvar', 'warning': 'uyarı', 'warnings': 'uyarılar', 'yonu': 'yönü', 'acik': 'açık', 'adaylar': 'adaylar', 'analiz': 'analiz', 'cephe': 'cephe', 'ciro': 'ciro', 'dayanak': 'dayanak', 'derinlik': 'derinlik', 'dop': 'DOP', 'edilen': 'edilen', 'fid': 'FID', 'fiili': 'fiilî', 'fizibilite': 'fizibilite', 'ha': 'ha', 'hisse': 'hisse', 'ids': 'kimlikler', 'jeoloji': 'jeoloji', 'kadastro': 'kadastro', 'kar': 'kâr', 'kategori': 'kategori', 'kes': 'kes', 'kesinti': 'kesinti', 'm2': 'm²', 'm3': 'm³', 'maliyet': 'maliyet', 'mpyy': 'MPYY', 'nesne': 'nesne', 'no': 'no', 'pafta': 'pafta', 'pah': 'pah', 'plan': 'plan', 'risk': 'risk', 'sahibi': 'sahibi', 'skor': 'puan', 'standart': 'standart', 'tahsis': 'tahsis', 'tercih': 'tercih', 'tl': 'TL', 'yasal': 'yasal', 'yeni': 'yeni', 'yeterlilik': 'yeterlilik', 'yoksun': 'yoksun', 'zarar': 'zarar', 'zarf': 'zarf'}


def field_alias(name):
    direct = display_label(name)
    if direct != name:
        return direct
    words = re.sub(r'([a-z])([A-Z])', r'\1_\2', name).replace('(', '_').replace(')', '').split('_')
    label = ' '.join(FIELD_WORDS.get(label_key(word).lower(), word) for word in words if word)
    return label[:1].replace('i', 'İ').upper() + label[1:]


def localized_fields(fields):
    from qgis.core import QgsField, QgsFields
    result = QgsFields()
    for field in fields:
        field = QgsField(field)
        field.setAlias(field_alias(field.name()))
        result.append(field)
    return result


def localized_category(value, symbol, label, *args):
    from qgis.core import QgsRendererCategory
    return QgsRendererCategory(value, symbol, display_label(label), *args)


def add_localized_layer(layer, project=None):
    from qgis.core import QgsProject
    project = project or QgsProject.instance()
    configure_localized_layer(layer, project)
    return project.addMapLayer(layer)


def display_expression(column, values=None, translations=None):
    """Portable native expression: requires no registered Python function."""
    from qgis.core import QgsExpression
    original = QgsExpression.quotedColumnRef(column)
    if values is not None:
        branches = ' '.join(
            f'WHEN {original} = {QgsExpression.quotedString(str(value))} THEN {QgsExpression.quotedString((translations or {}).get(str(value), display_label(value)))}'
            for value in sorted(values, key=str)
            if value is not None and (translations or {}).get(str(value), display_label(value)) != str(value)
        )
        return f'CASE {branches} ELSE {original} END' if branches else original
    key = f'upper(replace({original}, {QgsExpression.quotedString("ı")}, \'i\'))'
    for source, target in zip('ÇĞİÖŞÜ', 'CGIOSU'):
        key = f'replace({key}, {QgsExpression.quotedString(source)}, {QgsExpression.quotedString(target)})'
    branches = ' '.join(f'WHEN {key} = {QgsExpression.quotedString(k)} THEN {QgsExpression.quotedString(v)}' for k,v in LABELS.items())
    return f'CASE {branches} ELSE {original} END'


def configure_localized_layer(layer, project=None):
    """Translate presentation while retaining filters, lookup keys and layer identities."""
    from qgis.core import QgsCategorizedSymbolRenderer, QgsEditorWidgetSetup, QgsField, QgsProject, QgsRuleBasedRenderer
    from qgis.PyQt.QtCore import QMetaType
    project = project or QgsProject.instance()
    if layer.customProperty("mpyy/template"):
        # Template layers are already Turkish; rewriting their value-map captions or
        # the lookup display expression would diverge from the working source form.
        return
    for index, field in enumerate(layer.fields()):
        alias = layer.attributeAlias(index)
        layer.setFieldAlias(index, display_label(alias) if alias else field_alias(field.name()))
        setup = layer.editorWidgetSetup(index)
        config = setup.config()
        if setup.type() == 'ValueMap':
            values = config.get('map', [])
            if isinstance(values, dict):
                config['map'] = {display_label(k):v for k,v in values.items()}
            else:
                config['map'] = [{display_label(k):v for k,v in entry.items()} for entry in values]
            layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup('ValueMap', config))
        elif setup.type() == 'ValueRelation':
            lookup = project.mapLayer(config.get('Layer', ''))
            if lookup is None:
                candidates = project.mapLayersByName(config.get('LayerName', ''))
                lookup = candidates[0] if candidates else None
            column = config.get('Value', '')
            if lookup and column and lookup.fields().indexFromName(column) >= 0 and not column.startswith('_mpyy_display_'):
                display_column = '_mpyy_display_' + column
                if lookup.fields().indexFromName(display_column) < 0:
                    values = lookup.uniqueValues(lookup.fields().indexFromName(column))
                    lookup.addExpressionField(display_expression(column, values), QgsField(display_column, QMetaType.Type.QString))
                config['Layer'] = lookup.id()
                config['Value'] = display_column
                layer.setEditorWidgetSetup(index, QgsEditorWidgetSetup('ValueRelation', config))
        elif setup.type() == 'RelationReference':
            lookup = project.mapLayer(config.get('ReferencedLayerId', ''))
            relation = project.relationManager().relation(config.get('Relation', ''))
            if lookup and relation.isValid():
                columns = list(relation.fieldPairs().values())
                if columns:
                    column = columns[0]
                    values = lookup.uniqueValues(lookup.fields().indexFromName(column))
                    lookup.setDisplayExpression(display_expression(column, values))
    renderer = layer.renderer()
    if isinstance(renderer, QgsCategorizedSymbolRenderer):
        for index, category in enumerate(renderer.categories()):
            renderer.updateCategoryLabel(index, display_label(category.label()))
    elif isinstance(renderer, QgsRuleBasedRenderer):
        def visit(rule):
            rule.setLabel(display_label(rule.label()))
            for child in rule.children():
                visit(child)
        visit(renderer.rootRule())
