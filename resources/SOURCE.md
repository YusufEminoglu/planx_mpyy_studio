# Source of these files

These 451 tarama (hatch pattern) tiles are **not** original 02CadGis artwork.
They are redistributed **byte for byte, unmodified**, under their original file
names, from the plan gösterimleri SLD style set published on the e-Plan portal
of the **T.C. Çevre, Şehircilik ve İklim Değişikliği Bakanlığı — Coğrafi Bilgi
Sistemleri Genel Müdürlüğü**: <https://eplan.csb.gov.tr/>

They carry the official planning symbology defined in **Ek-2 of the Mekânsal
Planlar Yapım Yönetmeliği**, so that an imar plan imported from CAD is drawn the
way the regulation requires.

Two things worth knowing before touching them:

- Despite the `.png` extension, 119 of the 131 files are **BMP** bytes — that is
  how the Ministry ships them. Qt detects the format from content, so they are
  left exactly as published rather than being re-encoded.
- The file names are the Ministry's own UUIDs and are referenced by
  `core/eplan_catalog.py`. Renaming one breaks the catalog; regenerate with
  `tools/compile_eplan_catalog.py` instead.

Copyright and the basis for redistribution are recorded in
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

## PlanGML workspace symbology

`styles/plangml_sld/<LEVEL>/<Type>.sld` are the same Ministry GeoServer SLDs
(`E-Plan SLD.zip`, `gs-data/workspaces/eplan/styles`) with only their filter
property names and code-list literals rewritten to the PlanGML 1.1.7 field names
and codes (MUIP/MNIP styles: the M-series 1.1.6 schemas from the same package), and tile URLs replaced by a local token. How each rule was resolved is
recorded in `styles/plangml_sld/mapping.json`; regenerate with
`tools/compile_plangml_eplan_styles.py`. The tiles those SLDs reference were
added here byte for byte. Eleven SLDs name their tile with a stray `m` inside the
UUID (the same file carries `<Size>40m</Size>`, i.e. a bulk `40` -> `40m` edit); UUIDs
are hexadecimal, so the compiler drops the `m` and the archive's tile of that name is
used (`mapping.json` -> `images.repaired_names`).

Two things the Ministry set references but does not ship, and that this plugin does
not substitute: the `Intelli Eplan` symbol font (only `Intelli Eplan Extra` is in the
archive) and the point symbols loaded from `http://localhost/TaramaSembol/*.svg`.
Those markers are drawn as a grey `?` and the layer carries `mpyy/missing_symbols`.

M-series types without a Ministry style borrow the current-level style of the same
type (or of the type named in `decisions.json` -> `m_borrow`), keeping only rules
whose fields and codes exist in the M schema (`style_match: current_level`).

## Ek-1e detail catalog symbols

`resources/katalog_sembol/*.png` are cut from **Ek-1e Mekânsal Planlar Detay Katalogları**
(annex to the Mekânsal Planlar Yapım Yönetmeliği, file
`20260122-2-5-Ek1e-Mekansal-Planlar-Detay-Kataloglari-20260122155150.pdf`, sha256 in
`styles/plangml_katalog/symbols.json`) by `tools/build_catalog_symbols.py`: the SEMBOL
cell of each catalog table is rendered at 600 dpi, near-white made transparent and the
image trimmed; nothing is redrawn. `havai_hat_istasyonu_tarama.png` is generated from the
measurements written on catalog page 171. They replace the point symbols the Ministry SLDs
load from unpublished `TaramaSembol` SVGs or the unshipped `Intelli Eplan` font; the catalog
page of every use is recorded in `styles/plangml_katalog/decisions.json`.

