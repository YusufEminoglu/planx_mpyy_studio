# Third-party and source notices

The plugin code is Copyright (C) 2026 Yusuf Eminoğlu, GPL-2.0-or-later.

## Local UIP source catalog

`styles/UIPMPYYSTYLE.xml.gz` is a lossless local development copy of
`UIPMPYYSTYLE-2026_02_27.xml`. Source hashes and mapping omissions are recorded
in `styles/provenance.json`. The accompanying source GeoPackage is not shipped.
The source database compilation is attributed to Yusuf Eminoğlu in the existing
02CadGis notices. The XML's separate redistribution terms remain undocumented;
this build is for local testing and is not approved for public distribution.
No Ministry endorsement or statutory compliance is claimed.

The source has 300 top-level symbols and 1,100 symbols including nested ones.
270 lookup rows have unambiguous code/name/geometry matches. The source code
118200 is ambiguous; polygon codes 119004 and 114200 lack fill symbols.
No source point code mapping exists. These limitations are not filled by guesses.

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
saving. No system font files are distributed. Source font markers reference
Arial, Arial Black, Times New Roman and Calibri; missing fonts are reported.
