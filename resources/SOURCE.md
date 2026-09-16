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
property names and code-list literals rewritten to the PlanGML 1.1.6 field names
and codes, and tile URLs replaced by a local token. How each rule was resolved is
recorded in `styles/plangml_sld/mapping.json`; regenerate with
`tools/compile_plangml_eplan_styles.py`. The tiles those SLDs reference were
added here byte for byte. Eleven tiles referenced by the SLDs are absent from the
Ministry archive itself and are listed in `mapping.json`.
