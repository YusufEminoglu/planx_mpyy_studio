# Third-party and source notices

The plugin code is Copyright (C) 2026 Yusuf Eminoğlu, GPL-2.0-or-later.

## Local UIP source catalog

`styles/UIPMPYYSTYLE.xml.gz` is a lossless development copy of
`UIPMPYYSTYLE-2026_02_27.xml`. Source hashes and mapping omissions are recorded
in `styles/provenance.json`. The accompanying source GeoPackage is not shipped.
The source database compilation is attributed to Yusuf Eminoğlu in the existing
02CadGis notices. No Ministry endorsement or statutory compliance is claimed.

This file **is shipped**: `core/styler.py` loads it as the default notation
style. The source's separate redistribution terms remain undocumented, so the
terms on which the package carries this copy are unresolved rather than
approved. `styles/provenance.json` records that state as `distribution_status`.

The source has 300 top-level symbols and 1,100 symbols including nested ones.
270 lookup rows have unambiguous code/name/geometry matches. The source code
118200 is ambiguous; polygon codes 119004 and 114200 lack fill symbols.
No source point code mapping exists. These limitations are not filled by guesses.

## Ministry tarama tiles and annex artwork

Two groups of images in this package come from the Ministry's own published
material. None of them is this plugin's artwork, none has been redrawn, and for
none of them has a redistribution term been established — they ship under the
same unverified `distribution_status` as the copy above. This section records
what the package contains; it does not assert a right to redistribute it.

**`resources/*.png`** — 956 tarama (hatch pattern) tiles. They are
redistributed **byte for byte, unmodified**, under the Ministry's own file
names, from the plan gösterimleri SLD style set published on the e-Plan portal
of the T.C. Çevre, Şehircilik ve İklim Değişikliği Bakanlığı — Coğrafi Bilgi
Sistemleri Genel Müdürlüğü (<https://eplan.csb.gov.tr/>), and carry the official
planning symbology defined in Ek-2 of the Mekânsal Planlar Yapım Yönetmeliği.
853 of the 956 are **BMP** bytes despite the `.png` extension; that is how the
Ministry ships them, and they are left exactly as published rather than
re-encoded. `resources/patterns/` holds a second, unreferenced copy of the same
tiles; see [`resources/SOURCE.md`](resources/SOURCE.md).

**`resources/katalog_sembol/*.png`** — 45 point symbols cut from **Ek-1e
Mekânsal Planlar Detay Katalogları** by `tools/build_catalog_symbols.py`. Each is
the SEMBOL cell of a catalogue table rendered at 600 dpi, near-white made
transparent and the image trimmed. They replace point symbols the Ministry SLDs
load from unpublished `TaramaSembol` SVGs or from the unshipped `Intelli Eplan`
font, which this package does not substitute.

Ek-1e is an annex to the Mekânsal Planlar Yapım Yönetmeliği. Its source file
name and sha256 digest are recorded in the `source` block of
`styles/mpyy_detail_catalog/symbols.json`.

## Embedded SVG dependencies

`styles/water.svg`: Font Awesome Free 6.7.2, Copyright 2024 Fonticons, Inc.
Source: https://github.com/FortAwesome/Font-Awesome/blob/6.x/svgs/solid/water.svg
License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
License information: https://fontawesome.com/license/free
The SVG is unmodified except for the trailing newline. It resolves the source's
missing Font Awesome water icon; exact original source icon version is unknown.

`styles/Cross4.svg`: supplied by the installed QGIS SVG library,
`svg/crosses/Cross4.svg`, redistributed under the QGIS GPL-2.0-or-later license.
Source: https://github.com/qgis/QGIS/blob/master/images/svg/crosses/Cross4.svg

At import, both SVGs are embedded as base64 in symbols for portable project
saving.

## Bundled font payload

The package ships 131 TTF files under `resources/fonts/`, covering 58 families,
and registers all of them when the plugin loads. Source font markers reference
Arial, Arial Black, Times New Roman and Calibri; where a referenced family is
absent, the fallback is reported.

22 files in 4 families are DejaVu (DejaVu Sans, DejaVu Sans Mono, DejaVu Serif,
DejaVu Math TeX Gyre) and are redistributed under the DejaVu / Bitstream Vera
license, which permits it.

The other 109 files in 54 families are plan-notation and marker fonts. 51 of
those families are named after Turkish plan levels and authorities: the UIP, NIP
and CDP series together with their M- and ME-prefixed variants
(`MCDP_*`, `MCDPE_*`, `MNIP_*`, `MNIPE_*`, `MUIP_*`, `MUIPE_*`), the `OG_V_*`
line, and lowercase names for plan products and tabaka groups —
`uygulama_imar_*`, `nazim_imar_*`, `yerlesim`, `cevre_duzeni_plani_*`,
`mekansal_strateji_planlari_*` and `mulga_*`. The remaining 3 are named after
unrelated third parties: `ESRI Default Marker`, `Intelli Eplan Extra` and
`ISKI`.

No license file, license header or attribution record accompanies any of these
109 files, and no redistribution term has been established for them. They ship
under the `distribution_status` recorded in `styles/provenance.json`, which is
unverified. This notice records what the package contains; it does not assert a
right to redistribute it.
