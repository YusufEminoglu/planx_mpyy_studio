"""QField and Mobile Field Survey Packaging Engine for MPYY GeoPackages."""

from __future__ import annotations

import contextlib
from pathlib import Path
import shutil
import sqlite3
import uuid

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
    QgsSnappingConfig,
    QgsTolerance,
    QgsVectorLayer,
)


def _read_layer_style_from_gpkg(gpkg_path: Path, table_name: str) -> str:
    """Retrieve embedded QML style text from GeoPackage layer_styles table if present."""
    if not gpkg_path.is_file():
        return ""
    with contextlib.suppress(sqlite3.Error):
        with sqlite3.connect(gpkg_path) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT styleQML FROM layer_styles WHERE f_table_name = ? ORDER BY useAsDefault DESC, id DESC LIMIT 1",
                (table_name,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
    return ""


def package_for_qfield(
    gpkg_path: str | Path,
    output_dir: str | Path,
    project_title: str = 'PlanX MPYY Saha Anketi Projesi',
    include_osm: bool = True,
    copy_gpkg: bool = True,
) -> dict:
    """Package an MPYY / Arazi Kullanımı GeoPackage into a turn-key QField project folder."""
    src_gpkg = Path(gpkg_path).resolve()
    if not src_gpkg.is_file():
        raise FileNotFoundError(f'Kaynak GeoPackage bulunamadı: {src_gpkg}')

    out_dir = Path(output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    photo_dir = out_dir / "fotograflar"
    photo_dir.mkdir(parents=True, exist_ok=True)

    output_gpkg_path = out_dir / "data.gpkg"
    if copy_gpkg and src_gpkg != output_gpkg_path:
        shutil.copy2(src_gpkg, output_gpkg_path)
    elif not copy_gpkg and src_gpkg != output_gpkg_path:
        output_gpkg_path = src_gpkg

    # Inspect tables inside GeoPackage
    spatial_tables: list[tuple[str, str, str]] = []
    with sqlite3.connect(output_gpkg_path) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT table_name, data_type, identifier FROM gpkg_contents WHERE data_type = 'features' ORDER BY table_name"
        )
        for row in cur.fetchall():
            tbl_name, data_type, ident = row[0], row[1], row[2] or row[0]
            spatial_tables.append((tbl_name, data_type, ident))

    # Determine CRS from GeoPackage
    crs = QgsCoordinateReferenceSystem("EPSG:4326")
    with contextlib.suppress(sqlite3.Error, ValueError):
        with sqlite3.connect(output_gpkg_path) as con:
            cur = con.cursor()
            cur.execute("SELECT srs_id, organization, organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id > 0 LIMIT 1")
            srs_row = cur.fetchone()
            if srs_row:
                org, org_id = srs_row[1], srs_row[2]
                auth_id = f"{org}:{org_id}"
                c = QgsCoordinateReferenceSystem(auth_id)
                if c.isValid():
                    crs = c

    # Build standalone QGIS project instance
    project = QgsProject()
    project.setTitle(project_title)
    project.setCrs(crs)

    # Configure snapping for cadastral boundaries and structures
    snap_cfg = QgsSnappingConfig()
    snap_cfg.setEnabled(True)
    snap_cfg.setMode(QgsSnappingConfig.SnappingMode.AllLayers)
    snap_cfg.setType(QgsSnappingConfig.SnappingType.VertexAndSegment)
    snap_cfg.setTolerance(15.0)
    snap_cfg.setUnits(QgsTolerance.UnitType.Pixels)
    project.setSnappingConfig(snap_cfg)

    # Optional OSM XYZ Basemap
    added_layers = []
    if include_osm:
        osm_uri = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
        osm_layer = QgsRasterLayer(osm_uri, 'OpenStreetMap (Altlık)', "wms")
        if osm_layer.isValid():
            project.addMapLayer(osm_layer, addToLegend=True)
            added_layers.append(osm_layer)

    # Add survey layers
    for tbl_name, _, ident in spatial_tables:
        uri = f"{output_gpkg_path}|layername={tbl_name}"
        layer = QgsVectorLayer(uri, ident, "ogr")
        if not layer.isValid():
            continue

        # Load style from GeoPackage layer_styles if available
        qml = _read_layer_style_from_gpkg(output_gpkg_path, tbl_name)
        if qml:
            from qgis.PyQt.QtXml import QDomDocument
            doc = QDomDocument()
            if doc.setContent(qml):
                layer.importNamedStyle(doc)
        else:
            layer.loadDefaultStyle()

        project.addMapLayer(layer, addToLegend=True)
        added_layers.append(layer)

    # Save .qgs project file in output_dir
    project_file = out_dir / "saha_anketi.qgs"
    project.write(str(project_file))

    # Generate README for field crew
    readme_path = out_dir / "README_QFIELD.md"
    readme_content = f'# {project_title} - QField Mobil Saha Paketi\n\nBu klasör, tablet veya akıllı telefonlar üzerinde **QField** ile yerinde arazi kullanımı ve yapı tespiti yapılmak üzere hazırlanmıştır.\n\n## 📁 Klasör Yapısı\n- `saha_anketi.qgs`: QField ile doğrudan açılacak ana proje dosyası.\n- `data.gpkg`: Katmanların, kod sözlüklerinin, tetikleyicilerin ve SQL rapor görünümlerinin yer aldığı GeoPackage.\n- `fotograflar/`: Tablet kamerası ile çekilen saha ve cephe fotoğraflarının otomatik kaydedildiği klasör.\n\n## 🚀 Sahada Kullanım Adımları\n1. Bu klasörü (`{out_dir.name}`) tabletinize veya telefonunuza USB kablosu, hafıza kartı veya bulut (QFieldCloud / Drive) üzerinden kopyalayın.\n2. **QField** uygulamasını açın ve *Projeyi Aç* -> *Cihazdaki Projeler* -> `saha_anketi.qgs` dosyasını seçin.\n3. GPS konumunuzu açarak harita üzerinde bulunduğunuz ada/parseli seçin veya yeni bir nesne çizin.\n4. Öznitelik formundaki açılır listelerden (Örn: Parsel Kullanımı, Kat Adedi, Taşıyıcı Cinsi, Hasar Durumu) seçim yapın.\n5. **fotograf** alanına tıklayarak cihazınızın kamerasıyla cephe fotoğrafı çekin; fotoğraf otomatik olarak `fotograflar/` klasörüne göreli olarak ilişkilendirilecektir.\n\n## 🏢 Ofise Dönüş ve Veri Aktarımı\nSaha çalışması tamamlandıktan sonra tüm klasörü bilgisayarınıza geri kopyalayın.\nQGIS üzerinde `planx_mpyy_studio` eklentisiyle veri tabanını açarak **Kalite Kontrol (QC)** ve **Plan Açıklama Raporu** tablolarını tek tıkla üretebilirsiniz.\n'
    readme_path.write_text(readme_content, encoding="utf-8")

    return {
        "output_dir": str(out_dir),
        "project_file": str(project_file),
        "gpkg_file": str(output_gpkg_path),
        "photo_dir": str(photo_dir),
        "layer_count": len(added_layers),
    }
