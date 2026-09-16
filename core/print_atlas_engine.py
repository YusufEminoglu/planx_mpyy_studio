"""Official A3/A4 zoning atlas layout and export engine."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
import json
from pathlib import Path
from typing import Any
import uuid

from qgis.core import (
    QgsApplication,
    QgsFeature,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
    QgsVectorLayer,
)


@dataclass
class AtlasExportResult:
    output_path: str
    document_hash: str
    page_size: str
    dpi: int
    file_hash: str


@dataclass
class AtlasBatchResult:
    output_directory: str
    manifest_path: str
    documents: list[AtlasExportResult]


def _layout_millimeters() -> Any:
    unit = getattr(QgsUnitTypes, "LayoutMillimeters", None)
    if unit is None and hasattr(QgsUnitTypes, "LayoutUnit"):
        unit = getattr(QgsUnitTypes.LayoutUnit, "Millimeters", None)
    return unit


def _distance_meters() -> Any:
    unit = getattr(QgsUnitTypes, "DistanceMeters", None)
    if unit is None and hasattr(QgsUnitTypes, "DistanceUnit"):
        unit = getattr(QgsUnitTypes.DistanceUnit, "Meters", None)
    return unit


class OfficialPrintAtlasEngine:
    """Assembles an inspectable QGIS layout and exports it at print quality."""

    @classmethod
    def create_layout(
        cls,
        layer: QgsVectorLayer,
        feature: QgsFeature,
        municipality: str,
        document_number: str,
        page_size: str = "A3_LANDSCAPE",
        buffer_m: float = 30.0,
        project: QgsProject | None = None,
    ) -> tuple[QgsPrintLayout, str]:
        if not layer or not layer.isValid():
            raise ValueError('Geçerli bir parsel katmanı gereklidir.')
        geometry = feature.geometry()
        if not geometry or geometry.isEmpty():
            raise ValueError('Boş olmayan bir parsel nesnesi gereklidir.')
        page_key = str(page_size).upper()
        dimensions = {"A3_LANDSCAPE": (420.0, 297.0), "A4_PORTRAIT": (210.0, 297.0)}
        if page_key not in dimensions:
            raise ValueError('Sayfa boyutu A3_LANDSCAPE veya A4_PORTRAIT olmalıdır.')

        proj = project or QgsProject.instance()
        layout = QgsPrintLayout(proj)
        layout.initializeDefaults()
        document_hash = cls.document_hash(feature, municipality, document_number)
        layout.setName("Official_Zoning_Atlas_" + document_hash[:10])
        mm = _layout_millimeters()
        width, height = dimensions[page_key]
        layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(width, height, mm))

        margin = 10.0
        side_width = 116.0 if page_key == "A3_LANDSCAPE" else 72.0
        map_width = width - side_width - margin * 3.0
        map_height = height - margin * 2.0
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptMove(QgsLayoutPoint(margin, margin, mm))
        map_item.attemptResize(QgsLayoutSize(map_width, map_height, mm))
        map_item.setFrameEnabled(True)
        map_item.setLayers([layer])
        extent = QgsRectangle(geometry.boundingBox())
        extent.grow(max(20.0, min(50.0, float(buffer_m))))
        map_item.setExtent(extent)
        layout.addLayoutItem(map_item)

        x = margin * 2.0 + map_width
        y = margin
        cls._add_html_label(
            layout, x, y, side_width, 34.0,
            f"<b>{html.escape(str(municipality))}</b><br>PLANNING AND URBAN DEVELOPMENT DIRECTORATE"
            f"<br><b>OFFICIAL ZONING STATUS / PARCEL ATLAS</b>", mm,
        )
        y += 38.0

        fields = cls._feature_values(feature)
        attribute_rows = [
            ("Block / Parcel", cls._pick(fields, "ada", "ada_no") + " / " + cls._pick(fields, "parsel", "parsel_no")),
            ("Area", f"{geometry.area():,.2f} m2"),
            ("KAKS / TAKS", cls._pick(fields, "kaks", "emsal") + " / " + cls._pick(fields, "taks")),
            ("Hmax", cls._pick(fields, "yencok", "hmax")),
            ("Setbacks", cls._setback_text(fields)),
            ("CRS", layer.crs().authid() or layer.crs().description()),
            ("Approx. scale", "1:" + f"{max(1, round(map_item.scale())):,}"),
            ("Document No", document_number),
        ]
        rows = "".join(
            f"<tr><td><b>{html.escape(str(name))}</b></td>"
            f"<td>{html.escape(str(value or '-'))}</td></tr>"
            for name, value in attribute_rows
        )
        cls._add_html_label(layout, x, y, side_width, 76.0, "<table>" + rows + "</table>", mm)
        y += 80.0

        legend = QgsLayoutItemLegend(layout)
        legend.setTitle("MAP LEGEND")
        legend.setLinkedMap(map_item)
        legend.attemptMove(QgsLayoutPoint(x, y, mm))
        legend.attemptResize(QgsLayoutSize(side_width, 30.0, mm))
        legend.setFrameEnabled(True)
        layout.addLayoutItem(legend)
        y += 34.0

        scalebar = QgsLayoutItemScaleBar(layout)
        scalebar.setLinkedMap(map_item)
        scalebar.setUnits(_distance_meters())
        scalebar.setNumberOfSegments(4)
        scalebar.setNumberOfSegmentsLeft(0)
        scalebar.attemptMove(QgsLayoutPoint(x, y, mm))
        scalebar.attemptResize(QgsLayoutSize(side_width - 28.0, 16.0, mm))
        scalebar.setFrameEnabled(True)
        layout.addLayoutItem(scalebar)
        cls._add_north_arrow(layout, x + side_width - 24.0, y, 20.0, mm)
        y += 24.0

        cls._add_html_label(
            layout, x, y, side_width, 46.0,
            '<b>BELEDİYE ONAYI VE MÜHÜR</b><br><br>Düzenleyen: ____________________<br>Onaylayan Şehir Plancısı: ____________________<br>Tarih / Belge No: ____________________', mm,
        )
        y += 50.0
        remaining = max(28.0, height - margin - y)
        cls._add_html_label(
            layout, x, y, side_width, remaining,
            "<b>DIGITAL DOCUMENT VERIFICATION</b>"
            f"<br><span style='font-size:7px'>planx://verify/{document_hash}</span>"
            f"<br><span style='font-size:6px'>SHA-256: {document_hash}</span>", mm,
        )
        return layout, document_hash

    @classmethod
    def export(
        cls,
        layout: QgsPrintLayout,
        output_path: str | Path,
        document_hash: str,
        page_size: str,
        dpi: int = 300,
    ) -> AtlasExportResult:
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(str(output))
        exporter = QgsLayoutExporter(layout)
        if output.suffix.lower() == ".pdf":
            settings = QgsLayoutExporter.PdfExportSettings()
            result = exporter.exportToPdf(str(output), settings)
        elif output.suffix.lower() in {".png", ".tif", ".tiff"}:
            settings = QgsLayoutExporter.ImageExportSettings()
            settings.dpi = int(dpi)
            result = exporter.exportToImage(str(output), settings)
        else:
            raise ValueError('Atlas çıktısı PDF, PNG, TIF veya TIFF olmalıdır.')
        if result != QgsLayoutExporter.Success:
            raise RuntimeError(f'QGIS pafta dışa aktarımı {int(result)} koduyla başarısız oldu')
        if not output.is_file() or output.stat().st_size <= 0:
            raise RuntimeError('QGIS işlemi başarılı bildirdi ancak atlas dosyası üretmedi.')
        return AtlasExportResult(
            str(output), document_hash, page_size, int(dpi), cls._file_hash(output)
        )

    @classmethod
    def create_and_export(cls, layer, feature, output_path, municipality, document_number, page_size="A3_LANDSCAPE", buffer_m=30.0, dpi=300, project=None):
        layout, document_hash = cls.create_layout(
            layer, feature, municipality, document_number, page_size, buffer_m, project
        )
        return cls.export(layout, output_path, document_hash, page_size, dpi)

    @classmethod
    def export_batch(
        cls,
        layer: QgsVectorLayer,
        features,
        output_directory: str | Path,
        municipality: str,
        document_prefix: str = "ATLAS",
        page_size: str = "A3_LANDSCAPE",
        buffer_m: float = 30.0,
        dpi: int = 300,
        project: QgsProject | None = None,
        progress_callback=None,
        cancel_callback=None,
    ) -> AtlasBatchResult:
        output_dir = Path(output_directory).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "atlas_manifest.json"
        if manifest_path.exists():
            raise FileExistsError(str(manifest_path))
        prefix = cls._safe_filename(document_prefix)
        documents: list[AtlasExportResult] = []
        manifest_rows = []
        created_paths: list[Path] = []
        feature_list = list(features)
        try:
            for index, feature in enumerate(feature_list, start=1):
                if cancel_callback and cancel_callback():
                    raise RuntimeError('Toplu atlas dışa aktarımı iptal edildi.')
                values = cls._feature_values(feature)
                block = cls._pick(values, "ada", "ada_no") or "block"
                parcel = cls._pick(values, "parsel", "parsel_no") or str(feature.id())
                document_number = f"{prefix}-{index:04d}"
                stem = cls._safe_filename(f"{block}_{parcel}_{document_number}")
                output_path = output_dir / (stem + ".pdf")
                if output_path.exists():
                    raise FileExistsError(str(output_path))
                exported = cls.create_and_export(
                    layer, feature, output_path, municipality, document_number,
                    page_size, buffer_m, dpi, project,
                )
                created_paths.append(output_path)
                documents.append(exported)
                manifest_rows.append({
                    "block": block,
                    "parcel": parcel,
                    "document_number": document_number,
                    "file": output_path.name,
                    "document_sha256": exported.document_hash,
                    "file_sha256": exported.file_hash,
                })
                if progress_callback:
                    progress_callback(index, len(feature_list))
        except Exception:
            for created_path in created_paths:
                created_path.unlink(missing_ok=True)
            raise
        if not documents:
            raise ValueError('Toplu dışa aktarım için parsel nesnesi sağlanmadı.')
        document_payload = json.dumps(manifest_rows, ensure_ascii=True, sort_keys=True)
        manifest = {
            "municipality": municipality,
            "page_size": page_size,
            "dpi": int(dpi),
            "document_count": len(manifest_rows),
            "documents_sha256": hashlib.sha256(document_payload.encode("utf-8")).hexdigest(),
            "documents": manifest_rows,
        }
        temporary_manifest = output_dir / (".atlas_manifest_" + uuid.uuid4().hex + ".tmp")
        temporary_manifest.write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary_manifest.replace(manifest_path)
        return AtlasBatchResult(str(output_dir), str(manifest_path), documents)

    @staticmethod
    def document_hash(feature: QgsFeature, municipality: str, document_number: str) -> str:
        values = OfficialPrintAtlasEngine._feature_values(feature)
        payload = json.dumps(
            {"attributes": values, "municipality": municipality, "document_number": document_number},
            ensure_ascii=True, default=str, sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(payload)
        geometry = feature.geometry()
        if geometry and not geometry.isEmpty():
            digest.update(bytes(geometry.asWkb()))
        return digest.hexdigest()

    @staticmethod
    def _feature_values(feature: QgsFeature) -> dict[str, Any]:
        return {field.name().lower(): feature[field.name()] for field in feature.fields()}

    @staticmethod
    def _pick(values: dict[str, Any], *names: str) -> str:
        for name in names:
            value = values.get(name)
            if value not in (None, ""):
                return str(value)
        return ""

    @classmethod
    def _setback_text(cls, values: dict[str, Any]) -> str:
        front = cls._pick(values, "onbahce", "on_bahce") or "-"
        side = cls._pick(values, "yanbahce", "yan_bahce") or "-"
        rear = cls._pick(values, "arkabahce", "arka_bahce") or "-"
        return f"Front {front} / Side {side} / Rear {rear} m"

    @staticmethod
    def _safe_filename(value: str) -> str:
        cleaned = "".join(character if character.isalnum() or character in "-_" else "_" for character in value)
        return cleaned.strip("_")[:120] or "atlas_document"

    @staticmethod
    def _file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _add_html_label(layout, x, y, width, height, html, mm):
        label = QgsLayoutItemLabel(layout)
        label.attemptMove(QgsLayoutPoint(x, y, mm))
        label.attemptResize(QgsLayoutSize(width, height, mm))
        label.setFrameEnabled(True)
        label.setBackgroundEnabled(True)
        label.setText(html)
        label.setMode(QgsLayoutItemLabel.ModeHtml)
        layout.addLayoutItem(label)
        return label

    @staticmethod
    def _add_north_arrow(layout, x, y, size, mm):
        picture = QgsLayoutItemPicture(layout)
        picture.attemptMove(QgsLayoutPoint(x, y, mm))
        picture.attemptResize(QgsLayoutSize(size, size, mm))
        for root in QgsApplication.svgPaths():
            candidate = Path(root) / "arrows" / "NorthArrow_01.svg"
            if candidate.exists():
                picture.setPicturePath(str(candidate))
                break
        picture.setFrameEnabled(True)
        layout.addLayoutItem(picture)
        return picture
