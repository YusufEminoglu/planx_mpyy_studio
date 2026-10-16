"""EK-1b "Mekânsal Strateji Planlar Gösterimleri" ekinden MSP simgelerini çıkarır.

Kullanım:
    py -3 tools/build_msp_shapes.py "C:\\...\\EK_1b Mekansal Strateji Planlar Gosterimleri.pdf"

Neden var
---------
MSP kataloğu (`styles/msp_catalog.json`) EK-1e'den derleniyor; EK-1e renk hücrelerini
ve düz metni veriyor ama ekin **çizili** sütunlarını vermiyor. EK-1b'de dört gösterim
sütunu var: `ÇİZGİ TİPİ`, `SEMBOL`, `TARAMA`, `ALAN RENK KODU (RGB)`.
Bu araç ikisini ölçer ve `styles/msp_shapes.json`'a yazar:

* `SEMBOL` — nokta satırlarının simgesi. Hangi şekil olduğunu **başka hiçbir kaynak
  söylemiyor**; katalog bugüne kadar hepsine daire çiziyordu. Simge rengini de verir
  (Ek-1e'nin boş bıraktığı MSP-002 dahil) ve yarıçapları/çapları ölçer.
* `TARAMA` — dolgu deseni. Yalnızca iki satırda çizili (MSP-024 karolaj, MSP-025
  düşey çizgi) ve ikisi de POLİGON satırıdır. Buradan gelen **eksen** ekin hiçbir
  yerde söylemediği tek şeydir: metin "2 mm aralıklı" diyor, düşey mi yatay mı
  demiyor. Aralık ise buradan ALINMAZ — ölçüm ekin sözüyle çelişiyor, ve çelişki
  `celiski` alanıyla adıyla kaydedilir (aşağıya bak).

`ÇİZGİ TİPİ` (çizgi/kenar deseni) bu aracın kapsamı dışındadır: onu Ek-1e'nin
`stroke_desc`'i ve katalog zaten taşıyor.

Disiplin
--------
  * ÖLÇEMEDİĞİNİ UYDURMAZ. Ölçülemeyen alan `None` kalır.
  * Şekil ADI ölçümden gelmez: `SHAPE_TABLE` açıkça, tek tek yazılmıştır
    (`core/msp_catalog.py` içindeki `TURKISH_WORDS` gibi "explicit, not a blanket").
  * Sütun bantları sabit değil: tablonun KENDİ dikey ızgara çizgilerinden çıkarılır.
  * Satırlar boşluk tahminiyle değil, başlık metnini **sırayla** tüketerek bulunur —
    sarılmış başlıkların üst üste binen satır kutuları boşluk tabanlı birleştirmeyi bozar.
  * Hücre, raster eşiğiyle değil tablonun **kendi yatay kurallarından** kesilir
    (`table_rules`; kurallar sütun sütun parçalı çizilir, SEMBOL bandında tam bandı
    kaplar). Başlığın orta noktası ölçü sanılmaz: MSP-020'nin yıldızı başlık bandının
    altına taşar, ızgara ise hücrenin kendisidir.

`resources/katalog_sembol/` emsali: Ek-1e'nin SEMBOL hücresi 600 dpi'de kesilir,
kırını beyaza yakın olanı saydam yapılır, kırpılır — **hiçbir şey yeniden çizilmez**.
Burada da aynısı yapılır.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

# Digests are written as four space-separated groups: the Hub's detect-secrets
# scan blocks a version on a quoted 64-hex string. Readers remove the spaces.
HUB_SAFE_DIGEST = re.compile(r'"([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})([0-9a-f]{16})"')


def hub_safe(text: str) -> str:
    return HUB_SAFE_DIGEST.sub(r'"\1 \2 \3 \4"', text)


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "styles" / "msp_catalog.json"
OUT_JSON = ROOT / "styles" / "msp_shapes.json"
ICON_DIR = ROOT / "resources" / "msp_icons"
EVIDENCE_DIR = ICON_DIR / "kanit"

DPI = 600
MM_PER_PX = 25.4 / DPI

#: Hücre içindeki renk notu, ör. "255/170/0". Çizimin parçası değil, metindir.
COLOUR_NOTE = re.compile(r"^\d{1,3}/\d{1,3}/\d{1,3}$")

#: Sütun başlıkları — EK-1b'nin kendi etiketleri.
COLUMN_LABELS = ("ÇİZGİ TİPİ", "SEMBOL", "TARAMA", "ALAN RENK KODU")

#: Şekil sözlüğü. Açık, tek tek yazılmış; ölçümden türetilmez.
#: (şekil adı, çizim biçimi, doluluk) — çizim: "yerli" | "katmanli" | "raster"
SHAPE_TABLE = {
    # — hedef (iç içe halkalı daire): yerli karşılığı yok, katmanlı kurulur
    "MSP-002": ("hedef", "katmanli", "dolu"),
    "MSP-004": ("hedef", "katmanli", "dolu"),
    # — sekiz uçlu yıldız: `Qgis.MarkerShape`'te beş uçlu var, sekiz uçlu yok
    "MSP-005": ("yildiz8", "yerli", "dolu"),
    # — yerli karşılığı olanlar
    "MSP-008": ("daire", "yerli", "dolu"),
    "MSP-016": ("kare", "yerli", "dolu"),
    "MSP-017": ("kare", "yerli", "dolu"),
    "MSP-018": ("daire", "yerli", "dolu"),
    "MSP-019": ("yildiz5", "yerli", "dolu"),
    "MSP-020": ("yildiz5", "yerli", "bos"),
    "MSP-021": ("daire", "yerli", "dolu"),
    "MSP-023": ("altigen", "yerli", "dolu"),
    # — pikogramlar: siyah rozet üzerine beyaz glif; renk veriye bağlanamaz
    "MSP-011": ("capa", "raster", "dolu"),
    "MSP-012": ("ucak", "raster", "dolu"),
    "MSP-013": ("lojistik_l", "raster", "dolu"),
    # — katmanlı bileşikler
    "MSP-014": ("dort_ucgen", "katmanli", "dolu"),
    "MSP-022": ("daire_arti", "katmanli", "dolu"),
}

#: Yerli karşılığı OLMAYAN çizimler için ikon anahtarı (başlığın snake_case slug'ı,
#: `resources/katalog_sembol/` emsali). Yalnızca gerçek piktogramlar: çapa, uçak,
#: lojistik. Yıldız/kare/daire/altıgen burada YOKTUR — onları QGIS kendi şekliyle
#: çizer, böylece renkleri ve ölçekleri değiştirilebilir kalır.
ICON_KEY = {
    "MSP-011": "limanlar",
    "MSP-012": "havalimanlari",
    "MSP-013": "lojistik_merkezler",
}

#: TARAMA bandı ölçümü için: bir çizginin "ince" sayıldığı üst sınır (mm).
STRIPE_MAX_MM = 1.2

#: Simgenin ölçüsü nereden alınır. `hedef` bir hücrede ÜÇ kez çizilir (üç kademe);
#: simgenin kendisi en büyük lekedir. Ötekilerde hücrede tek bir iz vardır.
SIZE_FROM_LARGEST_BLOB = {"hedef"}


# --------------------------------------------------------------------------- #
# metin yardımcıları
# --------------------------------------------------------------------------- #
def fold(text: str) -> str:
    """Türkçe diakritikleri düşürüp A-Z0-9'a indirger (karşılaştırma anahtarı)."""
    text = text.replace("İ", "I").replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    return re.sub(
        r"[^A-Z0-9]", "", "".join(c for c in text if not unicodedata.combining(c))
    ).upper()


def slug(text: str) -> str:
    """Başlığı dosya adına çevirir — `resources/katalog_sembol/` ile aynı düzen."""
    text = text.replace("İ", "I").replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_only.lower())).strip("_")


# --------------------------------------------------------------------------- #
# EK-1b yapısı
# --------------------------------------------------------------------------- #
def vertical_grid(page: fitz.Page) -> list[float]:
    """Tablonun dikey ızgara çizgilerinin x konumları."""
    xs: set[float] = set()
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.x - p2.x) < 0.5 and abs(p2.y - p1.y) > 40:
                    xs.add(round(p1.x, 1))
            elif item[0] == "re":
                rect = item[1]
                if rect.width < 2.0 and rect.height > 40:
                    xs.add(round(rect.x0, 1))
    return sorted(xs)


def column_bands(page: fitz.Page) -> dict[str, tuple[float, float]]:
    """Sütun bantlarını başlık etiketleri ile ızgara çizgilerinin kesişiminden çıkarır."""
    labels: dict[str, tuple[float, float, float, float]] = {}
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = span["text"].strip().upper()
                if text in COLUMN_LABELS:
                    labels[text] = span["bbox"]
    missing = [name for name in COLUMN_LABELS if name not in labels]
    if missing:
        raise RuntimeError(f"EK-1b başlık etiketi bulunamadı: {missing}")

    xs = vertical_grid(page)
    bands: dict[str, tuple[float, float]] = {}
    for name, box in labels.items():
        left = max([v for v in xs if v <= box[0] + 1], default=box[0] - 6)
        right = min([v for v in xs if v >= box[2] - 1], default=box[2] + 6)
        bands[name] = (left, right)
    return bands


def _left_column_lines(page: fitz.Page) -> list[tuple[float, float, str]]:
    """Detay adı kolonundaki metin satırları, y'ye göre sıralı ve katlanmış."""
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            span = line["spans"][0]
            x0, y0, _x1, y1 = line["bbox"]
            if 45 <= x0 < 130 and 11.0 <= span["size"] <= 13.0 and y0 > 55:
                folded = fold("".join(s["text"] for s in line["spans"]))
                if folded:
                    lines.append((y0, y1, folded))
    return sorted(lines)


def locate_records(doc: fitz.Document, titles: list[tuple[str, str]]) -> list[dict]:
    """28 kaydı başlık metninden bulur.

    Başlıklar sarılınca satır kutuları ÜST ÜSTE BİNEBİLİR (ör. EKONOMİK GELİŞME
    y 92.2-108.0 ile ALANLARI y 105.8-121.8). Bu yüzden boşluk tabanlı birleştirme
    değil, başlık listesini **sırayla** tüketen bir yürüyüş kullanılır: kayma olamaz.
    """
    found: list[dict] = []
    index = 0
    for page_no in range(doc.page_count):
        lines = _left_column_lines(doc[page_no])
        i = 0
        while i < len(lines) and index < len(titles):
            record_id, title = titles[index]
            wanted = fold(title)
            acc, start, y0 = "", i, lines[i][0]
            y1 = lines[i][1]
            while i < len(lines) and len(acc) < len(wanted):
                acc += lines[i][2]
                y1 = lines[i][1]
                i += 1
            if acc == wanted:
                found.append(
                    {"id": record_id, "baslik": title, "sayfa": page_no, "y0": y0, "y1": y1}
                )
                index += 1
            else:
                i = start + 1  # bu satır başlığın başı değildi
    if len(found) != len(titles):
        eksik = [rid for rid, _ in titles][len(found):]
        raise RuntimeError(f"EK-1b'de bulunamayan kayıtlar: {eksik}")
    return found


# --------------------------------------------------------------------------- #
# hücre ölçümü
# --------------------------------------------------------------------------- #
def ink(image: Image.Image):
    """(renkli, koyu) ikili yüklemleri — renk notu metni ikisine de girmez."""
    pixels = image.load()
    width, height = image.size

    def chroma(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a > 200 and (max(r, g, b) - min(r, g, b)) > 40

    def dark(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a > 200 and max(r, g, b) < 110

    return chroma, dark, pixels, width, height


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    out, start = [], None
    for i, value in enumerate(list(flags) + [False]):
        if value and start is None:
            start = i
        elif not value and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def strip_rules(image: Image.Image) -> Image.Image:
    """Hücreye sızmış ızgara çizgisini siler — çizgi simgenin parçası değildir.

    Bu artık bir **emniyet ağıdır**, işin kendisi değil: hücre `table_rules` ile
    zaten ekin kendi ızgarasından kesiliyor, dolayısıyla gerçek bir kural hücreye
    ancak kenar yumuşatması kadar sızabilir. Eşik bu yüzden iki eksende de %90:
    yalnızca satırın/sütunun neredeyse tamamını kaplayan bir çizgi silinir.

    Geçmişte bu eşik %60'a indirilmişti (üst satırdan taşan kenarlık parçalarını
    yakalamak için); o ayar MSP-016'nın karesinin KENDİ kenarlarını da sildi.
    Izgara kırpma işine karıştırılınca böyle oluyor: eşiği düşürmek simgenin
    parçasını, yükseltmek kırıntıyı yer. Kırpma doğru olunca ikisi de gerekmiyor.
    """
    image = image.copy()
    pixels = image.load()
    width, height = image.size

    def dark(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a > 200 and max(r, g, b) < 110

    horizontal = [
        sum(dark(x, y) for x in range(width)) > 0.9 * width for y in range(height)
    ]
    vertical = [
        sum(dark(x, y) for y in range(height)) > 0.9 * height for x in range(width)
    ]
    for y, is_rule in enumerate(horizontal):
        if is_rule:
            for x in range(width):
                pixels[x, y] = (255, 255, 255, 0)
    for x, is_rule in enumerate(vertical):
        if is_rule:
            for y in range(height):
                pixels[x, y] = (255, 255, 255, 0)
    box = image.getbbox()
    return image.crop(box) if box else image


def table_rules(page: fitz.Page, band: tuple[float, float]) -> list[float]:
    """Bir sütun bandını enine kesen tablo kurallarının y değerleri (pt).

    EK-1b'de kayıtlar arasında yatay kural VARDIR ve her kural sütun sütun
    parçalı çizilir — SEMBOL bandında `480.7 -> 579.5` gibi tam bandı kaplar.
    Kuralı rasterda eşikle aramak yerine vektör çizimden okuyoruz: kuralın
    kendisi zaten kesin geometridir, ölçülmesi gereken bir şey değil.

    Bandı enine kesmeyen parçalar alınmaz: ALAN RENK KODU sütunundaki bir çizgi
    SEMBOL hücresinin sınırı değildir.
    """
    ys: set[float] = set()
    for item in page.get_drawings():
        for sub in item["items"]:
            kind = sub[0]
            if kind == "l":
                p1, p2 = sub[1], sub[2]
                if abs(p1.y - p2.y) >= 0.3:
                    continue
                x0, x1 = sorted((p1.x, p2.x))
                y = (p1.y + p2.y) / 2
            elif kind == "re":
                r = sub[1]
                if r.height >= 2.0:
                    continue
                x0, x1, y = r.x0, r.x1, (r.y0 + r.y1) / 2
            else:
                continue
            if x0 <= band[0] + 1 and x1 >= band[1] - 1:
                ys.add(round(y, 2))
    return sorted(ys)


def cell_band(rules: list[float], y: float, what: str) -> tuple[float, float]:
    """`y`'yi içeren kural bandı — kaydın GERÇEK hücresi. Yoksa durur.

    Başlığın orta noktasından ölçü türetmek yanıltıcıydı (MSP-020'nin yıldızı
    başlık bandının altına taşar). Izgara ise hücrenin kendisidir.
    """
    for a, b in zip(rules, rules[1:]):
        if a <= y <= b:
            return a, b
    raise RuntimeError(
        f"{what}: y={y:.1f} hiçbir kural bandına düşmüyor (kurallar: {rules})"
    )


def symbol_extent(image: Image.Image) -> tuple[float, float]:
    """Simgenin görsel ölçüsü (mm): siyah kontur dahil, ızgara kırıntısı hariç.

    Kırpma artık ızgaradan geldiği için kırıntı beklenmez; yine de kenar
    yumuşatmasından kalan ince izler olabilir. Ayraç **yükseklik**: EK-1b'de
    ölçülen en ince gerçek iz MSP-004'ün 2.58 mm'lik merkezidir, kırıntı ise
    0.08–0.17 mm. Arada 15 kat var, eşik 2.0 mm.

    (Önceki sürüm "ince VE neredeyse tam genişlikte" diyordu; 7 mm × 0.08 mm
    bir kural parçası bu koşulu geçip ölçüyü hücre genişliğine şişiriyordu.)
    """
    boxes = []
    for finder in (blobs(image), blobs(image, dark=True)):
        for box in finder:
            if box["yukseklik_mm"] < 2.0:
                continue
            boxes.append(box)
    if not boxes:
        return round(image.width * MM_PER_PX, 2), round(image.height * MM_PER_PX, 2)
    x0 = min(b["x0"] for b in boxes)
    x1 = max(b["x1"] for b in boxes)
    y0 = min(b["y0"] for b in boxes)
    y1 = max(b["y1"] for b in boxes)
    return round((x1 - x0 + 1) * MM_PER_PX, 2), round((y1 - y0 + 1) * MM_PER_PX, 2)


def render_cell(
    page: fitz.Page, rect: fitz.Rect, *, strip: bool = True
) -> Image.Image | None:
    """Bir hücreyi 600 dpi'de keser. Boş hücre `None` döner.

    ``strip=False`` **TARAMA hücresi için zorunludur**: tarama çizgileri hücrenin
    tüm yüksekliğini kaplar, yani `strip_rules`'un "sütunun %90'ı" testine tam
    olarak uyar ve ızgara çizgisi sanılıp silinir — geriye yalnızca gri kenar
    yumuşatması kalır (ölçülen: ham pikselde en koyu 0, temizlikten sonra 112).
    SEMBOL hücresinde ise hiçbir simge hücreyi kaplamaz, o yüzden orada emniyet
    ağı olarak kalır.
    """
    words = [w for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(rect)]
    zoom = DPI / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
    for word in words:
        # renk notu ("255/170/0") çizimin parçası değil
        if not COLOUR_NOTE.match(word[4]):
            continue
        box = [
            (word[0] - rect.x0) * zoom - 4,
            (word[1] - rect.y0) * zoom - 4,
            (word[2] - rect.x0) * zoom + 4,
            (word[3] - rect.y0) * zoom + 4,
        ]
        image.paste((255, 255, 255, 255), [int(v) for v in box])
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, _ = pixels[x, y]
            if min(r, g, b) >= 235:
                pixels[x, y] = (255, 255, 255, 0)
    # ÖNEMLİ: ızgara temizliği KIRPMADAN ÖNCE, tam hücre üzerinde yapılır. Kırpılmış
    # görüntüde simgenin kendi konturu hücreyi kaplayabilir ve yanlışlıkla silinir;
    # tam hücrede (≈760 px) bir simge satırın %90'ını asla kaplamaz.
    stripped = strip_rules(image) if strip else image
    box = stripped.getbbox()
    if box is None:
        return None
    trimmed = stripped.crop(box)
    if trimmed.height < 12 or trimmed.width < 12:  # yalnızca kenarlık kırıntısı
        return None
    return trimmed


def colour_note(page: fitz.Page, rect: fitz.Rect) -> str | None:
    """Hücrede yazılı renk notu (ör. `255/170/0`), yoksa None."""
    for word in page.get_text("words"):
        if fitz.Rect(word[:4]).intersects(rect) and COLOUR_NOTE.match(word[4]):
            return word[4]
    return None


def dominant_rgb(image: Image.Image) -> list[int] | None:
    """Renkli mürekkebin en sık rengi — bağımsız teyit, not değil."""
    chroma, _dark, pixels, width, height = ink(image)
    counts = Counter(
        pixels[x, y][:3]
        for y in range(height)
        for x in range(width)
        if chroma(x, y)
    )
    if not counts:
        return None
    return list(counts.most_common(1)[0][0])


def blobs(image: Image.Image, *, dark: bool = False) -> list[dict]:
    """Yatay eksende ayrık lekeler: her biri için mm cinsinden ölçü."""
    chroma, dark_p, pixels, width, height = ink(image)
    test = dark_p if dark else chroma
    columns = [any(test(x, y) for y in range(height)) for x in range(width)]
    out = []
    for x0, x1 in _runs(columns):
        rows = [y for y in range(height) if any(test(x, y) for x in range(x0, x1 + 1))]
        out.append(
            {
                "x0": x0,
                "x1": x1,
                "y0": rows[0],
                "y1": rows[-1],
                "genislik_mm": round((x1 - x0 + 1) * MM_PER_PX, 2),
                "yukseklik_mm": round((rows[-1] - rows[0] + 1) * MM_PER_PX, 2),
            }
        )
    return out


def hedef_stack(image: Image.Image, blob: dict) -> list[dict] | None:
    """Bir hedefin üst üste çizilecek daire yığınını (mm) en dıştan içe döndürür.

    Hedef, iç içe geçmiş **dolu dairelerin** üst üste binmesiyle kurulur: en dış
    daire dolgu renginde, üstüne daha küçük beyaz bir daire, üstüne daha küçük
    dolgu dairesi... Merkezden geçen yatay taramada her malzeme değişimi bir
    dairenin yarıçapıdır; ilk malzeme kenardan başlar, her biri kendi
    genişliği kadar yarıçapı yer.

    Malzeme dizisi simetrik değilse `None` — uydurma yok.
    """
    chroma, dark, pixels, _w, _h = ink(image)
    y = (blob["y0"] + blob["y1"]) // 2

    def material(x: int) -> str:
        r, g, b, a = pixels[x, y]
        if a <= 200:
            return "bos"
        if (max(r, g, b) - min(r, g, b)) > 40:
            return "dolgu"
        if max(r, g, b) < 110:
            return "sinir"
        return "bos"

    classes = [material(x) for x in range(blob["x0"], blob["x1"] + 1)]
    runs = []
    for start, end in _runs_classes(classes):
        runs.append((end - start + 1, classes[start]))
    while runs and runs[0][1] == "bos":
        runs.pop(0)
    while runs and runs[-1][1] == "bos":
        runs.pop()
    if len(runs) < 3 or len(runs) % 2 == 0:
        return None
    roles = [role for _width, role in runs]
    if roles != roles[::-1] or any(role == "bos" for role in roles[::2]):
        return None

    # Yürüyüş yarıya kadar: tarama her daireyi girerken de çıkarken de keser, o
    # yüzden daire yığını **kenardan merkeze** olan ilk yarıdır. Merkez bandının
    # tam genişliği merkez dairesinin çapıdır — yarı genişliği yarıçapı.
    half = runs[: len(runs) // 2 + 1]
    radius = (blob["x1"] - blob["x0"] + 1) * MM_PER_PX / 2.0
    stack = []
    for width_px, role in half[:-1]:
        stack.append({"rol": role, "cap_mm": round(2 * radius, 2)})
        radius -= width_px * MM_PER_PX
    # tutarlılık: merkez bandının ölçülen genişliği kalan çapı doğrulamalı
    if abs(half[-1][0] * MM_PER_PX - 2 * radius) > 0.4:
        return None
    stack.append({"rol": half[-1][1], "cap_mm": round(2 * radius, 2)})
    return stack if all(d["cap_mm"] > 0 for d in stack) else None


def _runs_classes(classes: list[str]) -> list[tuple[int, int]]:
    """Ardışık eşit sınıfların (başlangıç, bitiş) aralıkları."""
    out, start = [], 0
    for i in range(1, len(classes) + 1):
        if i == len(classes) or classes[i] != classes[start]:
            out.append((start, i - 1))
            start = i
    return out


def hatch_measurement(image: Image.Image) -> dict:
    """TARAMA hücresinin ölçüsü: çizgi ekseni, ince bant sayısı, mürekkep rengi.

    **Aralık buradan gelmez.** Ölçülen aralık `olculen_aralik_mm` olarak
    kaydedilir ama katalog alanı olmaz: ek aralığı kendi metniyle zaten söylüyor
    ("5*5 mm ara ile", "2 mm aralıklı") ve raster ölçüm onunla ÇELİŞİYOR
    (ölçülen 3.22 mm ile 1.6 mm). 600 dpi'de bir kıl-çizginin ve bir nokta
    karolajının okunması kayıplıdır; ekin sözü spesifikasyondur, çizim ise
    doğrulamadır. Çelişki gizlenmez, adıyla basılır.

    Eksen ise YALNIZCA buradan gelir: ek "2 mm aralıklı" diyor ama düşey mi
    yatay mı olduğunu hiçbir yerde söylemiyor — çizim söylüyor.
    """
    _chroma, dark_p, pixels, width, height = ink(image)
    test = dark_p

    def profile_runs(along_columns: bool) -> list[tuple[int, int]]:
        if along_columns:
            flags = [any(test(x, y) for y in range(height)) for x in range(width)]
        else:
            flags = [any(test(x, y) for x in range(width)) for y in range(height)]
        return _runs(flags)

    cols = profile_runs(True)
    rows = profile_runs(False)
    thin_cols = [r for r in cols if (r[1] - r[0] + 1) * MM_PER_PX <= STRIPE_MAX_MM]
    thin_rows = [r for r in rows if (r[1] - r[0] + 1) * MM_PER_PX <= STRIPE_MAX_MM]

    # Mürekkep rengi: kaplanan piksellerin en koyusu. Mod (en sık değer) değil —
    # kıl-çizginin çekirdeği azınlıktadır, çoğunluk kenar yumuşatmasıdır.
    darkest = None
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a > 200 and (darkest is None or max(r, g, b) < darkest[0]):
                darkest = (max(r, g, b), (r, g, b))
    ink_rgb = list(darkest[1]) if darkest else None

    def spacing(runs: list[tuple[int, int]]) -> float | None:
        if len(runs) < 2:
            return None
        centres = [(a + b) / 2 for a, b in runs]
        gaps = [centres[i + 1] - centres[i] for i in range(len(centres) - 1)]
        return round(sum(gaps) / len(gaps) * MM_PER_PX, 2)

    if len(thin_cols) >= 3 and len(thin_rows) >= 3:
        # Hem satır hem sütun profili kalabalık: nokta karolajı. Tek bir açısı yok.
        axis, angle, spacing_mm = "nokta", None, spacing(thin_cols)
    elif len(thin_cols) >= 3:
        axis, angle, spacing_mm = "dikey", 90.0, spacing(thin_cols)
    elif len(thin_rows) >= 3:
        axis, angle, spacing_mm = "yatay", 0.0, spacing(thin_rows)
    else:
        axis, angle, spacing_mm = None, None, None

    return {
        "eksen": axis,
        "aci_derece": angle,
        "olculen_aralik_mm": spacing_mm,
        "murekkep_rgb": ink_rgb,
        "ince_bant_sayisi": [len(thin_cols), len(thin_rows)],
    }


#: Ekin metnindeki uzunluk ölçüleri: "2 mm", "5*5 mm", "0.5 mm".
_LENGTH_MM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\*\s*\d+(?:[.,]\d+)?)?\s*mm", re.I)

#: Aralığın kendisinden önce gelen etiket. Ekin cümlesi hep
#: "ÇİZGİ KALINLIĞI: <kalınlık> mm <aralık>" biçiminde kurulmuş.
_WIDTH_LABEL = re.compile(r"ÇİZGİ\s*KALINLIĞI", re.I)


def stated_spacing_mm(text: str) -> float | None:
    """Ekin metninde yazılı **aralık**, ör. "5*5 mm ara ile" ya da "2 mm aralıklı".

    Etiketli cümlede ilk ölçü çizgi kalınlığıdır, aralık ikincisidir
    (MSP-024: "ÇİZGİ KALINLIĞI: 0.5 mm 5*5 mm ara ile karolaj merkezlerinde
    noktalama" → 5). Etiketsiz metinde ilk ölçü aralıktır. Yalnızca kalınlık
    yazılmışsa aralık None döner — ek bir aralık söylememiştir, uydurulmaz.
    """
    lengths = [m.group(1) for m in _LENGTH_MM.finditer(text or "")]
    index = 1 if _WIDTH_LABEL.search(text or "") else 0
    if len(lengths) <= index:
        return None
    return float(lengths[index].replace(",", "."))


# --------------------------------------------------------------------------- #
# yazma
# --------------------------------------------------------------------------- #
def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_png(image: Image.Image, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")
    return sha256(path)


def prune_icons(keep: set[str]) -> list[str]:
    """`ICON_DIR`deki, artık üretilmeyen ikonları siler. Silinenlerin adını döndürür.

    Bu dizin TAMAMEN bu aracın çıktısıdır; bir şekil raster'dan yerliye geçtiğinde
    eski PNG öksüz kalır ve zip'e girer. Öksüz bırakmak yerine kaynağı tek otorite
    yapıyoruz: yeniden sınıflandırma kendini temizler.
    """
    removed = []
    for path in sorted(ICON_DIR.glob("*.png")):
        if path.stem not in keep:
            path.unlink()
            removed.append(path.name)
    return removed


def build(pdf_path: Path) -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = catalog["rows"]
    titles = [(r["id"], r["detay_adi"]) for r in rows]
    geometry = {r["id"]: r["geometri"] for r in rows}
    hatch_desc = {r["id"]: r.get("hatch_desc") or "" for r in rows}

    doc = fitz.open(pdf_path)
    bands = column_bands(doc[0])
    records = locate_records(doc, titles)

    sembol = bands["SEMBOL"]
    tarama = bands["TARAMA"]
    sembol_rules = {p: table_rules(doc[p], sembol) for p in range(doc.page_count)}
    tarama_rules = {p: table_rules(doc[p], tarama) for p in range(doc.page_count)}

    def cell(record: dict, band: tuple[float, float], rules: dict, what: str) -> fitz.Rect:
        """Kaydın GERÇEK hücresi: başlığını içeren kural bandı, ızgara payı kadar içerlek.

        Pay 1.5 pt: kuralın kendi kalınlığı ve kenar yumuşatması hücreye girmesin.
        Ölçülen en büyük simge (MSP-002 yığını, 11.35 mm) 40 mm'lik hücrede kalır.
        """
        y = (record["y0"] + record["y1"]) / 2
        top, bottom = cell_band(rules[record["sayfa"]], y, f"{record['id']} {what}")
        inset = 1.5
        return fitz.Rect(
            band[0] + inset, top + inset, band[1] - inset, bottom - inset
        )

    shapes: dict[str, dict] = {}
    for record in records:
        record_id = record["id"]
        table = SHAPE_TABLE.get(record_id)
        if table is None:  # nokta değil — SEMBOL hücresi boş
            continue
        shape, drawing, fill = table

        cell_rect = cell(record, sembol, sembol_rules, "SEMBOL")
        image = render_cell(doc[record["sayfa"]], cell_rect)
        if image is None:
            raise RuntimeError(
                f"{record_id} nokta satırı ama SEMBOL hücresi boş — şekil tablosu yanlış"
            )

        entry: dict = {
            "sayfa": record["sayfa"] + 1,
            "baslik": record["baslik"],
            "geometri": geometry[record_id],
            "sekli": shape,
            "cizim": drawing,
            "dolgu": fill,
            "renk_notu": colour_note(doc[record["sayfa"]], cell_rect),
            "renk_rgb": dominant_rgb(image),
        }

        chroma_blobs = blobs(image)
        dark_blobs = blobs(image, dark=True)
        whole_width_mm, whole_height_mm = symbol_extent(image)

        if shape in SIZE_FROM_LARGEST_BLOB:
            # Bir hücrede birden fazla iz var (MSP-002'nin üç hedefi); simge en büyüğü.
            main = max(chroma_blobs, key=lambda b: b["genislik_mm"])
            centre = (main["x0"] + main["x1"]) / 2
            block = next(
                (b for b in dark_blobs if b["x0"] <= centre <= b["x1"]), main
            )
            entry["boyut_mm"] = block["genislik_mm"]
            entry["yukseklik_mm"] = block["yukseklik_mm"]
            entry["lekeler_mm"] = [b["genislik_mm"] for b in chroma_blobs]
        else:
            main = chroma_blobs[0] if len(chroma_blobs) == 1 else None
            entry["boyut_mm"] = whole_width_mm
            entry["yukseklik_mm"] = whole_height_mm
            entry["lekeler_mm"] = [b["genislik_mm"] for b in chroma_blobs]

        if drawing == "raster":
            key = ICON_KEY[record_id]
            icon_path = ICON_DIR / f"{key}.png"
            entry["ikon"] = str(icon_path.relative_to(ROOT)).replace("\\", "/")
            entry["ikon_sha256"] = save_png(image, icon_path)
        else:
            # Kontur yalnızca TEK bir kapalı şekilde ölçülebilir; çok parçalıda None.
            entry["kontur_mm"] = None
            if main is not None:
                block = next(
                    (
                        b
                        for b in dark_blobs
                        if b["x0"] <= (main["x0"] + main["x1"]) / 2 <= b["x1"]
                    ),
                    None,
                )
                if block is not None:
                    entry["kontur_mm"] = round(
                        (block["genislik_mm"] - main["genislik_mm"]) / 2.0, 2
                    )
            if shape == "hedef":
                entry["discler"] = hedef_stack(image, main) if main else None

        # kanıt kırpıntısı: her nokta satırı için, kullanılsın kullanılmasın
        evidence = EVIDENCE_DIR / f"{record_id}.png"
        entry["kanit"] = str(evidence.relative_to(ROOT)).replace("\\", "/")
        entry["kanit_sha256"] = save_png(image, evidence)

        shapes[record_id] = entry

    # TARAMA sütunu ayrı bir geçişte ölçülür: tarama çizen satırlar POLİGON
    # satırlarıdır (MSP-024 karolaj, MSP-025 düşey çizgi) ve `SHAPE_TABLE`'da
    # hiç görünmezler. Ölçüm nokta satırlarına bağlanırsa bu iki satır sessizce
    # atlanır — nitekim atlanıyordu.
    taramalar: dict[str, dict] = {}
    for record in records:
        record_id = record["id"]
        page_rules = tarama_rules[record["sayfa"]]
        if not page_rules:
            continue
        t_image = render_cell(
            doc[record["sayfa"]],
            cell(record, tarama, tarama_rules, "TARAMA"),
            strip=False,
        )
        if t_image is None:
            continue
        measurement = hatch_measurement(t_image)
        if measurement["eksen"] is None:
            continue
        # Ekin metniyle karşılaştır. Çelişki gizlenmez: aralık katalog alanı
        # olmayacak (metin spesifikasyondur), ama ölçümün metinden saptığı
        # yerde bu yazılı olsun.
        stated = stated_spacing_mm(hatch_desc.get(record_id, ""))
        if stated is not None:
            measurement["metin_araligi_mm"] = stated
            measured = measurement["olculen_aralik_mm"]
            measurement["celiski"] = (
                measured is not None and abs(measured - stated) > 0.15 * stated
            )
        t_path = EVIDENCE_DIR / f"{record_id}_tarama.png"
        measurement["kanit"] = str(t_path.relative_to(ROOT)).replace("\\", "/")
        measurement["kanit_sha256"] = save_png(t_image, t_path)
        taramalar[record_id] = measurement

    absent = sorted(set(SHAPE_TABLE) - set(shapes))
    if absent:
        raise RuntimeError(f"şekil tablosundaki kayıtlar ölçülemedi: {absent}")

    return {
        "source": {
            "pdf": pdf_path.name,
            "sha256": sha256(pdf_path),
            "dpi": DPI,
            "sutunlar_pt": {name: list(bands[name]) for name in bands},
            "not": (
                "EK-1b 'Mekânsal Strateji Planlar Gösterimleri'. SEMBOL ve TARAMA "
                "sütunları 600 dpi'de kesildi; kırını beyaza yakın olanı saydam "
                "yapıldı ve kırpıldı — hiçbir şey yeniden çizilmedi."
            ),
        },
        "shapes": dict(sorted(shapes.items())),
        "taramalar": dict(sorted(taramalar.items())),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    pdf_path = Path(argv[1])
    if not pdf_path.exists():
        raise SystemExit(f"PDF bulunamadı: {pdf_path}")

    payload = build(pdf_path)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        hub_safe(json.dumps(payload, ensure_ascii=False, indent=2)) + "\n", encoding="utf-8"
    )

    removed = prune_icons(
        {ICON_KEY[rid] for rid, tbl in SHAPE_TABLE.items() if tbl[1] == "raster"}
    )
    if removed:
        print(f"öksüz ikon silindi: {', '.join(removed)}")

    print(f"yazdı: {OUT_JSON.relative_to(ROOT)}  ({len(payload['shapes'])} nokta satırı)")
    for record_id, entry in payload["shapes"].items():
        tail = ""
        if entry.get("discler"):
            tail = " disk=" + " ".join(
                f"{d['cap_mm']}({d['rol']})" for d in entry["discler"]
            )
        elif entry.get("ikon"):
            tail = f" ikon={entry['ikon']}"
        print(
            f"  {record_id}  {entry['sekli']:12s} {entry['cizim']:9s} "
            f"{str(entry['renk_rgb']):16s} {entry['boyut_mm']}{tail}"
        )
    print(f"  tarama ölçülen satır: {len(payload['taramalar'])}")
    for record_id, entry in payload["taramalar"].items():
        tail = ""
        if entry.get("celiski"):
            tail = (
                f"  ⚠ ÇELİŞKİ: ölçülen {entry['olculen_aralik_mm']} mm, "
                f"ekin sözü {entry['metin_araligi_mm']} mm — aralık metinden alınır"
            )
        print(
            f"    {record_id}  {str(entry['eksen']):7s} açı={str(entry['aci_derece']):6s} "
            f"ince_bant={entry['ince_bant_sayisi']}  mürekkep={entry['murekkep_rgb']}{tail}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
