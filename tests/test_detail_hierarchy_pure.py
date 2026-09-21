"""Ek-1e prints labels more than one way and the catalog must ship one spelling each.

`apply_renderer_hierarchy` writes a feature type's distinct subclasses into the
layer's `mpyy/detay_alt_sinifi` metadata as a `" | "`-joined list and copies one
of them into every rule description.  Three defects reach that metadata, plus the
merge of a classification's two names:

Duplicates.  A label stored in two spellings reads as two classifications joined
by a pipe -- `UIP/KiyiYapilari` shipped `DENIZYOLLARI | DENİZYOLLARI` -- and each
rule description then picked one of the two at random.  The variants are one
label: Ek-1e prints `ALAN KULLANIMI` once against `ALAN KULLANIMLARI` 302 times,
prints `ALAN KULANIMLARI` beside the correct spelling on the same page, and
elsewhere loses the dotted İ, runs two words together, drops the plural -LARI or
carries a trailing -I.  Nothing here is a new value and nothing is invented: each
pair is repaired to one spelling by a two-tier rule -- the Ministry's machine
readable code list where it has an opinion (10 of the 12 distinct kept spellings
are `ust_grup_adi` values, and that list is what the rest of the plugin reads),
otherwise the spelling the catalogue itself carries on the most rows.  `EK-1e.docx`
prints both variants for all fourteen, so it cannot settle the choice either.

Three pairs are not a spelling slip at all.  Ek-1e files one concept under the
plural `SOSYAL VE KÜLTÜREL TESIS ALANLARI` and under the singular
`SOSYAL VE KÜLTÜREL TESİS ALANI` -- which it also prints run together, as
`SOSYALVE ...` -- and the plurals `SAĞLIK TESISLERI ALANLARI` and
`EĞITIM TESISLERI ALANLARI` are the same shape one group over.  All three merge
into the singular the code list names, the SOSYAL one on Yusuf's instruction
(2026-09-21).  These are the pairs no other check would have caught: the two
forms fold to different keys *and* differ by more than one letter, so neither the
fold-based duplicate guard nor the one-letter check sees one label, and nothing
would notice a re-extraction that brought a plural back.
`test_the_plural_class_merged_into_the_singular` and
`test_the_undotted_labels_ship_the_code_list_spelling` are what hold them.

Labels the annex also prints undotted were once left alone here, and the reason
was never that they are few: they are 79 rows.  `DEMIRYOLLARI`,
`ENERJI ÜRETIM, DAĞITIM VE DEPOLAMA`, `İDARI SINIRLAR`, `SAĞLIK TESISLERI
ALANLARI` and `EĞITIM TESISLERI ALANLARI` each shipped in exactly one form, so
nothing folded together, no guard fired, and a duplicate hunt could not see them
-- only a label-versus-code-list pass could.  Repaired on Yusuf's instruction
(2026-09-21) on the same two-tier rule, the code list settling all five; for
`ENERJI` that keeps the group name the code list itself carries, which dots
`ÜRETİM`, leaves `ENERJI` undotted and drops the comma the annex prints.

Wrong block.  The plain extraction does not always hand a page's blocks over in
printed order, so pairing a block with "the text printed before it" handed some
titles the class belonging to the symbol above them -- `ELEKTRİKLİ ARAÇ ŞARJ
İSTASYONU` shipped `KENTSEL ÇALIŞMA ALANLARI` where its own block prints
`KARAYOLLARI`, which the code list files under KARAYOLLARI as well.  The compiler
now pairs by printed position, and PINNED below holds the corrected pairings.

Measured 2026-09-21 on the shipped catalogue: 592 records, 29 `detay_alt_sinifi`
and 3 `detay_sinifi` labels, and no label is a second spelling of another --
neither by `label_fold`, which drops spaces and punctuation and so cannot see
`ALAN KULLANIMI`, nor one letter away from it.  The count was 30 before the
plural/singular merge and is 29 after it, because two of those values were one
classification; the five undotted labels were renamed in place, so they did not
move it.

These checks are qgis-free, so they run on both runtimes and cannot be skipped
for want of a QGIS import.
"""

from __future__ import annotations

import itertools
import json
import unittest
from pathlib import Path

from planx_mpyy_studio.core.localization import label_fold


HIERARCHY = Path(__file__).resolve().parents[1] / "styles" / "mpyy_detail_hierarchy.json"
LABEL_FIELDS = ("sembol_adi", "detay_sinifi", "detay_alt_sinifi")
# `sembol_adi` is left out of the one-letter check on purpose: the catalog ships
# `MOTEL ALANI` next to `OTEL ALANI`, `ÖÇK BÖLGESİ HASSAS ALAN (A)` next to (B)
# and (C), and the `1.`/`2.`/`3.DERECE` arkeolojik and doğal `SİT ALANI`
# symbols -- 10 pairs, all of them distinct catalog items the code list names
# separately, so a one-letter check over this field would fail on correct data.
# The two label fields hold a closed vocabulary instead, where a one-letter pair
# is a typo, and this is the check `label_fold` cannot make: the repaired
# `ALAN KULANIMLARI` / `ALAN KULLANIMLARI` fold to different keys, so the
# fold-based duplicate guard passes while both spellings ship.
CLOSED_FIELDS = ("detay_sinifi", "detay_alt_sinifi")

# Each pair the source prints twice, and the spelling the catalog keeps.  The
# first element is written out letter for letter so the test names the defect it
# guards rather than only the invariant.  Four entries below are not two spellings
# of two labels: the annex prints the run-together `SOSYALVE ...` and the spaced
# plural `SOSYAL VE ... ALANLARI` for one classification, and `SAĞLIK` and `EĞİTİM
# ... ALANLARI` are plurals whose code-list group name is a singular; all four are
# merged into the singular the code list and the rest of the plugin use.
REPAIRED = (
    ("DENIZYOLLARI", "DENİZYOLLARI"),
    ("AÇIK VE YEŞIL ALANLAR", "AÇIK VE YEŞİL ALANLAR"),
    ("YERLEŞIM ALANLARI", "YERLEŞİM ALANLARI"),
    ("SOSYALVE KÜLTÜREL TESIS ALANLARI", "SOSYAL VE KÜLTÜREL TESİS ALANI"),
    ("ALAN KULLANIMI", "ALAN KULLANIMLARI"),
    ("ALAN KULANIMLARI", "ALAN KULLANIMLARI"),
    ("SOSYAL ALTYAPI ALANLARI", "SOSYAL ALT YAPI ALANLARI"),
    ("ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLARI", "ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLAR"),
    ("DEMIRYOLLARI", "DEMİRYOLLARI"),
    ("ENERJI ÜRETIM, DAĞITIM VE DEPOLAMA", "ENERJI ÜRETİM DAĞITIM VE DEPOLAMA"),
    ("İDARI SINIRLAR", "İDARİ SINIRLAR"),
    ("SOSYAL VE KÜLTÜREL TESIS ALANLARI", "SOSYAL VE KÜLTÜREL TESİS ALANI"),
    ("SAĞLIK TESISLERI ALANLARI", "SAĞLIK TESİSLERİ ALANI"),
    ("EĞITIM TESISLERI ALANLARI", "EĞİTİM TESİSLERİ ALANI"),
)

# The five labels that shipped undotted in one form only, so no duplicate hunt
# could find them, with the rows each carried.  Keyed by the kept spelling, so a
# re-extraction that reintroduces the annex's undotted form fails on the count
# rather than silently shipping again.
UNDOTTED_REPAIRED = (
    ("DEMİRYOLLARI", 11),
    ("ENERJI ÜRETİM DAĞITIM VE DEPOLAMA", 34),
    ("İDARİ SINIRLAR", 18),
    ("SAĞLIK TESİSLERİ ALANI", 5),
    ("EĞİTİM TESİSLERİ ALANI", 11),
)

# Every symbol whose class the old block pairing got wrong, with the pair its own
# printed block carries.  Keyed by page and symbol, because the same catalog item
# ships once per plan level and all of those copies must agree.
PINNED = (
    (19, "İMAR HAKKI AKTARIM ALANI SINIRI", "SINIRLAR", "PLANLAMA SINIRLARI"),
    (23, "ORGANİZE SANAYİ BÖLGESİ HİZMET VE DESTEK ALANI (HDA)",
     "KENTSEL ÇALIŞMA ALANLARI", "ORGANİZE SANAYİ BÖLGESİ HİZMET VE DESTEK ALANLARI"),
    (34, "DİĞER ÖZEL KANUNLARLA BELİRLENEN ALAN SINIRLARI",
     "SINIRLAR", "ÖZEL KANUNLARLA BELİRLENEN ALAN VE SINIRLAR"),
    (61, "ÜNİVERSİTE ALANI", "ALAN KULLANIMLARI", "SOSYAL ALT YAPI ALANLARI"),
    (64, "ELEKTRİKLİ ARAÇ ŞARJ İSTASYONU", "ALAN KULLANIMLARI", "KARAYOLLARI"),
    (96, "MAKİLİK- FUNDALIK ALAN", "ALAN KULLANIMLARI",
     "BUGÜNKÜ ARAZİ KULLANIMI DEVAM ETTİRİLEREK KORUNACAK ALANLAR"),
    (138, "MESİRE ALANI", "ALAN KULLANIMLARI", "SOSYAL ALT YAPI ALANLARI"),
    (160, "SU ULAŞIM BAĞLANTISI", "ALAN KULLANIMLARI", "DİĞER SU YOLLARI"),
    (191, "FAY SAKINIM ZONU/TAMPON ALANI", "ALAN KULLANIMLARI", "AFET TEHLİKELİ ALANLAR"),
    (192, "SOKAK HAYVANLARI BARINAĞI ALANI", "ALAN KULLANIMLARI", "SOSYAL ALT YAPI ALANLARI"),
)


def _one_letter_apart(first: str, second: str) -> bool:
    """True when the two differ by exactly one insertion, deletion or substitution."""
    if first == second or abs(len(first) - len(second)) > 1:
        return False
    if len(first) == len(second):
        return sum(a != b for a, b in zip(first, second)) == 1
    shorter, longer = (first, second) if len(first) < len(second) else (second, first)
    index = 0
    while index < len(shorter) and shorter[index] == longer[index]:
        index += 1
    return shorter[index:] == longer[index + 1:]


class DetailHierarchyLabelTests(unittest.TestCase):
    def setUp(self):
        self.text = HIERARCHY.read_text(encoding="utf-8")
        self.catalogue = json.loads(self.text)
        self.records = self.catalogue["records"]

    def test_every_label_is_shipped_in_exactly_one_spelling(self):
        for field in LABEL_FIELDS:
            with self.subTest(field=field):
                spellings = {}
                for record in self.records:
                    spellings.setdefault(label_fold(record[field]), set()).add(record[field])
                self.assertEqual(
                    {key: sorted(values) for key, values in spellings.items() if len(values) > 1},
                    {},
                    f"{field}: aynı etiketin birden çok yazımı",
                )

    def test_no_label_is_one_letter_away_from_another(self):
        """One letter apart is the same label, not a second one."""
        for field in CLOSED_FIELDS:
            with self.subTest(field=field):
                labels = sorted({record[field] for record in self.records})
                near = [
                    (first, second)
                    for first, second in itertools.combinations(labels, 2)
                    if _one_letter_apart(label_fold(first), label_fold(second))
                ]
                self.assertEqual(near, [], f"{field}: bir harf farklı etiketler")

    def test_each_pair_ships_only_the_spelling_the_catalog_keeps(self):
        """Not "the code-list spelling": only ten of the twelve kept spellings are code-list values."""
        for defective, official in REPAIRED:
            with self.subTest(label=official):
                self.assertIn(official, self.text)
                # Substring, not equality: this also catches a defective spelling
                # left behind in a row the repair did not visit.
                self.assertNotIn(defective, self.text)

    def test_the_plural_class_merged_into_the_singular(self):
        """The one pair that is not a spelling slip, so REPAIRED alone would not show it landed.

        It differs by the plural morpheme *and* by the dotted İ -- two changes,
        three characters apart folded -- so neither `label_fold` nor the
        one-letter check can see the two as one label and neither would catch a
        re-extraction that brought the plural back.
        """
        rows = [record for record in self.records
                if "SOSYAL VE KÜLTÜREL TES" in record["detay_alt_sinifi"]]
        self.assertEqual(len(rows), 16, "çoğul/tekil birleşmesi tüm satırlara inmedi")
        self.assertEqual({record["detay_alt_sinifi"] for record in rows},
                         {"SOSYAL VE KÜLTÜREL TESİS ALANI"})
        # The merge is what took the vocabulary from 30 values to 29: two of them
        # were one classification.  Pin it, so a future extraction that brings the
        # plural back fails here rather than only in the row count above.
        self.assertEqual(len({record["detay_alt_sinifi"] for record in self.records}), 29)

    def test_the_undotted_labels_ship_the_code_list_spelling(self):
        """The five the duplicate hunt could not find: each shipped in one form only.

        Nothing folded together, so no guard could see them; they were found by
        comparing the shipped vocabulary against the Ministry's code list, which
        names all five.  Pinning the row counts also pins the merge for `SAĞLIK`
        and `EĞİTİM`, whose code-list name is a singular.
        """
        counts = {}
        for record in self.records:
            counts[record["detay_alt_sinifi"]] = counts.get(record["detay_alt_sinifi"], 0) + 1
        shipped = 0
        for label, rows in UNDOTTED_REPAIRED:
            with self.subTest(label=label):
                self.assertEqual(counts.get(label), rows, label)
            shipped += counts.get(label, 0)
        # Measured from the catalogue, not from the constants above: this is the
        # 79 rows the five labels carry in total, and it is what a re-extraction
        # that dropped one of them would move.
        self.assertEqual(shipped, 79)
        for undotted in ("DEMIRYOLLARI", "ENERJI ÜRETIM, DAĞITIM VE DEPOLAMA",
                         "İDARI SINIRLAR", "SAĞLIK TESISLERI ALANLARI",
                         "EĞITIM TESISLERI ALANLARI"):
            with self.subTest(undotted=undotted):
                self.assertNotIn(undotted, self.text)

    def test_rows_the_old_pairing_mis_assigned_keep_their_own_class(self):
        for page, symbol, detail_class, subclass in PINNED:
            with self.subTest(symbol=symbol):
                rows = [record for record in self.records
                        if record["kaynak_sayfa"] == page and record["sembol_adi"] == symbol]
                self.assertTrue(rows, f"s.{page}: {symbol} katalogda yok")
                self.assertEqual(
                    {(row["detay_sinifi"], row["detay_alt_sinifi"]) for row in rows},
                    {(detail_class, subclass)},
                    f"s.{page}: {symbol}",
                )

    def test_records_cover_every_level_and_are_all_counted(self):
        self.assertEqual(self.catalogue["record_count"], len(self.records))
        self.assertEqual(
            {record["plan_kademesi"] for record in self.records}, {"UIP", "NIP", "CDP"}
        )
        for record in self.records:
            self.assertEqual(sorted(record), sorted(self.records[0]), record)


if __name__ == "__main__":
    unittest.main()
