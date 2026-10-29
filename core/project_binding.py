"""Bind canonical MPYY and Arazi Kullanımı layers into a structured Turkish layer tree with authentic styles and forms."""

import os
from pathlib import Path
from qgis.core import (
    QgsDefaultValue,
    QgsEditorWidgetSetup,
    QgsMapLayer,
    QgsProject,
    QgsProviderRegistry,
    QgsRelation,
    QgsVectorLayer,
)
from qgis.PyQt.QtXml import QDomDocument

from .actions import attach_layer_actions
from .db_factory import read_dataset_info
from .fonts import register_mpyy_fonts
from .localization import configure_localized_layer
from .mpyy_workspace import KIND as MPYY_XSD_KIND, load_mpyy_layers
from .msp_workspace import KIND as MSP_EK1E_KIND, load_msp_layers
from .local_nip_workspace import (
    KIND as LOCAL_NIP_KIND,
    import_template_style as import_nip_template_style,
    load_local_nip_layers,
    template as nip_template,
)
from .local_uip_workspace import (
    KIND as LOCAL_UIP_KIND,
    bind_function_relation,
    import_template_style,
    load_local_uip_layers,
    template as uip_template,
)

# Tables of the MpyyUipDb drawing template, by their own names.
UIP_TEMPLATE_TABLES = {"uipPolygonTable": "uipPolygonTable", "uipLineTable": "uipLineTable"}


def _forms_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "forms"


def _field_index(layer: QgsVectorLayer, name: str) -> int:
    return layer.fields().indexFromName(name)


def configure_layer_defaults(layer: QgsVectorLayer) -> None:
    """Set default UUID and timestamp expressions on canonical layers."""
    gid_idx = _field_index(layer, "global_id")
    if gid_idx >= 0:
        layer.setDefaultValueDefinition(
            gid_idx,
            QgsDefaultValue("replace(replace(uuid(),'{',''),'}','')"),
        )

    for time_col in ("olusturma_tarihi", "guncelleme_tarihi", "tarih"):
        idx = _field_index(layer, time_col)
        if idx >= 0:
            layer.setDefaultValueDefinition(
                idx,
                QgsDefaultValue("format_date(now(), 'yyyy-MM-dd HH:mm:ss')"),
            )

    pk_idx = _field_index(layer, "plan_kademesi")
    if pk_idx >= 0 and layer.name().startswith("mpyy_"):
        level = layer.name().split("_")[1].upper()
        layer.setDefaultValueDefinition(pk_idx, QgsDefaultValue(f"'{level}'"))

    from .form_designer import MPYYFormDesigner
    MPYYFormDesigner.apply_complete_form_experience(layer)


def apply_layer_style_and_form(layer: QgsVectorLayer) -> None:
    """Apply authentic QML forms, styles, or dedicated level engines."""
    name = layer.name()
    fdir = _forms_dir()

    # Register fonts so glyph markers are rendered properly
    register_mpyy_fonts()

    # 1. UIP layers use the frozen MpyyUipDb drawing template (form, dropdowns, symbology)
    template_table = UIP_TEMPLATE_TABLES.get(name) or (name if name in uip_template()["styles"] else None)
    if template_table:
        import_template_style(layer, template_table)
        return

    # 1b. NIP layers use the frozen MpyyNipDB drawing template
    if name in nip_template()["styles"]:
        import_nip_template_style(layer, name)
        return

    # 2. Arazi Kullanımı Layers
    arazi_qmls = {
        "parsel_saha": fdir / "arazi" / "01_parsel_saha.qml",
        "Tucbs_1000_alan": fdir / "arazi" / "02_Tucbs_1000_alan.qml",
        "Tucbs_1000_Cizgi": fdir / "arazi" / "03_Tucbs_1000_Cizgi.qml",
        "yapi_saha": fdir / "arazi" / "04_yapi_saha.qml",
        "yol_saha": fdir / "arazi" / "05_yol_saha.qml",
    }
    if name in arazi_qmls and arazi_qmls[name].exists():
        _msg, ok = layer.loadNamedStyle(str(arazi_qmls[name]))
        if ok:
            layer.setCustomProperty("mpyy/form", f"Saha Anket Formu: {name}")
            layer.triggerRepaint()


def setup_project_relations(project: QgsProject) -> None:
    """Connect the MpyyUipDb template relations: uip-alanlar -> uipPolygonTable, uip_cizgiler -> uipLineTable."""
    alan_layer = None
    table_layer = None

    for layer in project.mapLayers().values():
        if layer.name() == "uip-alanlar":
            alan_layer = layer
        elif layer.name() == "uipPolygonTable":
            table_layer = layer

    if alan_layer and table_layer and alan_layer.isValid() and table_layer.isValid():
        template_relation = uip_template()["relations"][0]
        bind_function_relation(project, alan_layer, table_layer, template_relation["pairs"], template_relation["id"])

    # Connect uip_cizgiler and uipLineTable if both exist
    cizgi_layer = None
    line_table_layer = None
    for layer in project.mapLayers().values():
        if layer.name() == "uip_cizgiler":
            cizgi_layer = layer
        elif layer.name() == "uipLineTable":
            line_table_layer = layer

    if cizgi_layer and line_table_layer and cizgi_layer.isValid() and line_table_layer.isValid():
        line_rel_id = "uipLine_uipfonksiyon_uipLine_uip_fonksiyon"
        bind_function_relation(
            project,
            cizgi_layer,
            line_table_layer,
            {"uipfonksiyon": "uip_fonksiyon"},
            line_rel_id,
        )

    # Connect Yerel NİP relations (alanlar-5000 -> fonksiyonlar-5000_tablo) if present
    by_name = {lyr.name(): lyr for lyr in project.mapLayers().values() if lyr.isValid()}
    for rel in nip_template().get("relations", ()):
        referencing = by_name.get(rel["referencing"])
        referenced = by_name.get(rel["referenced"])
        if referencing is not None and referenced is not None:
            bind_function_relation(project, referencing, referenced, rel["pairs"], rel["id"])


    # Connect parsel_saha and yapi_saha if both exist in project
    parsel_layer = None
    yapi_layer = None
    for layer in project.mapLayers().values():
        if layer.name() == "parsel_saha":
            parsel_layer = layer
        elif layer.name() == "yapi_saha":
            yapi_layer = layer

    if parsel_layer and yapi_layer and parsel_layer.isValid() and yapi_layer.isValid():
        py_rel_id = "rel_parsel_yapi_saha"
        if not project.relationManager().relation(py_rel_id).isValid():
            py_rel = QgsRelation()
            py_rel.setId(py_rel_id)
            py_rel.setName('Parsel - Yapı İlişkisi')
            py_rel.setReferencingLayer(yapi_layer.id())
            py_rel.setReferencedLayer(parsel_layer.id())
            py_rel.addFieldPair("ADA", "ADA")
            py_rel.addFieldPair("PARSEL", "PARSEL")
            if py_rel.isValid():
                project.relationManager().addRelation(py_rel)



def load_project_layers(path: str | Path, project: QgsProject | None = None) -> list[QgsVectorLayer]:
    """Load canonical layers from a PlanX MPYY GeoPackage into the QGIS project tree."""
    project = project or QgsProject.instance()
    info = read_dataset_info(path)
    dataset_id = info["dataset_id"]
    kind = info["workspace_kind"]
    if kind == LOCAL_UIP_KIND:
        return load_local_uip_layers(path, project, dataset_id)
    if kind == LOCAL_NIP_KIND:
        return load_local_nip_layers(path, project, dataset_id)
    if kind == MPYY_XSD_KIND:
        levels = info.get("plan_levels") or ()
        return load_mpyy_layers(path, project, dataset_id, levels[0] if levels else None)
    if kind == MSP_EK1E_KIND:
        return load_msp_layers(path, project, dataset_id)

    root = project.layerTreeRoot()
    if kind != "ARAZI_KULLANIMI":
        raise RuntimeError('Bu çalışma alanı türü artık desteklenmiyor: ' + str(kind))
    base_group = root.findGroup('Arazi Kullanımı ve Saha Anketi') or root.addGroup('Arazi Kullanımı ve Saha Anketi')

    from .schema import LAND_TABLES
    tables = LAND_TABLES

    loaded_layers = []
    gpkg_str = str(Path(path).resolve())

    # Auto-load official catalog and domain lookup tables
    if kind == "ARAZI_KULLANIMI":
        for lookup_tbl in ("saha_kullanim_kodlari",):
            uri = f"{gpkg_str}|layername={lookup_tbl}"
            tbl_layer = QgsVectorLayer(uri, lookup_tbl, "ogr")
            if tbl_layer.isValid():
                tbl_layer.setCustomProperty("mpyy/dataset_id", dataset_id)
                project.addMapLayer(tbl_layer, False)
                base_group.addLayer(tbl_layer)
                loaded_layers.append(tbl_layer)


    for table_name in tables.keys():
        uri = f"{gpkg_str}|layername={table_name}"
        layer = QgsVectorLayer(uri, table_name, "ogr")
        if not layer.isValid():
            continue

        layer.setCustomProperty("mpyy/dataset_id", dataset_id)
        layer.setCustomProperty("mpyy/workspace_kind", kind)

        apply_layer_style_and_form(layer)
        configure_layer_defaults(layer)

        project.addMapLayer(layer, False)
        base_group.addLayer(layer)

        loaded_layers.append(layer)

    # Establish relations
    setup_project_relations(project)
    for layer in loaded_layers:
        configure_localized_layer(layer, project)
        if layer.name() in tables:
            attach_layer_actions(layer)
    return loaded_layers
