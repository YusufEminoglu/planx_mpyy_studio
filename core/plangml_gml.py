"""PlanGML GML dosyası içe aktarma (M serisi ve güncel şemalar).

Reads a PlanGML FeatureCollection strictly by the XSD structure: every element
whose local name is a feature type of the chosen schema is one feature; its
``GeometryProperty`` child holds a GML geometry (GML 2 ``coordinates`` or GML 3 /
3.2 ``posList``, surfaces and curves included; parsed by GDAL), its other children are attributes named like the schema fields.
Values are written to a PlanGML workspace GeoPackage of the same schema, so the
import gets the schema's dropdowns and the Ministry's MUIP/MNIP symbology.

The schema is taken from ``xsi:schemaLocation`` when the file names one of the
Ministry XSDs, otherwise from which schema declares the most element names found
in the file (``YeniKod`` breaks ties in favour of the M series). Nothing that does
not match the schema is guessed: unknown elements, unknown attributes, codes
outside a code list and unreadable geometries are counted in the report.
"""

import re
from pathlib import Path

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QDateTime, QFile, QIODevice, Qt
from qgis.PyQt.QtXml import QDomDocument

from osgeo import ogr

from .plangml_import import FAMILY
from .plangml_workspace import all_levels, create_plangml_workspace

CONTAINERS = {"FeatureCollection", "featureMember", "featureMembers", "features"}


def _local(node):
    return node.localName() or node.nodeName().split(":")[-1]


def _children(element):
    child = element.firstChildElement()
    while not child.isNull():
        yield child
        child = child.nextSiblingElement()


def load_document(path):
    stream = QFile(str(path))
    if not stream.open(QIODevice.OpenModeFlag.ReadOnly):
        raise ValueError('GML dosyası açılamadı: ' + str(path))
    document = QDomDocument()
    result = document.setContent(stream, True)  # namespace aware
    stream.close()
    ok = result[0] if isinstance(result, tuple) else result
    if not ok:
        detail = result[1] if isinstance(result, tuple) and len(result) > 1 else ""
        raise ValueError('GML/XML okunamadı: ' + str(detail))
    return document


def feature_elements(document, type_names):
    """Feature elements in document order; descends only through collection wrappers."""
    found, unknown = [], {}

    def walk(element):
        for child in _children(element):
            name = _local(child)
            if name in type_names:
                found.append(child)
            elif name in CONTAINERS:
                walk(child)
            elif name not in ("boundedBy",):
                unknown[name] = unknown.get(name, 0) + 1

    walk(document.documentElement())
    return found, unknown


def detect_level(document):
    """(level, reason) for the PlanGML schema this document was written against."""
    levels = all_levels()
    root = document.documentElement()
    location = " ".join(
        root.attributeNS("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation").split()
        + [root.attribute("xsi:schemaLocation")]
    ).lower()
    for level, schema in levels.items():
        if schema["xsd"]["file"].lower() in location:
            return level, "xsi:schemaLocation " + schema["xsd"]["file"]
    names, has_new_code = set(), False

    def walk(element, depth=0):
        nonlocal has_new_code
        for child in _children(element):
            names.add(_local(child))
            if _local(child) == "YeniKod":
                has_new_code = True
            if depth < 3:
                walk(child, depth + 1)

    walk(root)
    scores = []
    for level, schema in levels.items():
        types = {t["name"] for t in schema["feature_types"]}
        hits = len(names & types)
        if hits:
            scores.append((hits, has_new_code == level.startswith("M"), -len(types), level))
    if not scores:
        raise ValueError('Dosyada PlanGML nesne tipi bulunamadı; şema belirlenemedi.')
    best = max(scores)
    return best[3], f"{best[0]} nesne tipi adı eşleşti" + (" ve YeniKod alanı var" if has_new_code else "")


def _geometry(element, target_crs, default_crs, project):
    for child in _children(element):
        if _local(child) != "GeometryProperty":
            continue
        geometry_element = child.firstChildElement()
        if geometry_element.isNull():
            return None, "GeometryProperty boş"
        holder = QDomDocument()
        holder.appendChild(holder.importNode(geometry_element, True))
        parsed = ogr.CreateGeometryFromGML(holder.toString(-1))
        if parsed is None:
            return None, "GML geometrisi okunamadı: " + _local(geometry_element)
        if parsed.HasCurveGeometry():
            parsed = parsed.GetLinearGeometry()
        geometry = QgsGeometry.fromWkt(parsed.ExportToIsoWkt())
        if geometry.isNull():
            return None, "GML geometrisi okunamadı: " + _local(geometry_element)
        geometry.get().dropZValue()
        geometry.get().dropMValue()
        srs = geometry_element.attribute("srsName")
        crs = QgsCoordinateReferenceSystem.fromOgcWmsCrs(srs) if srs else default_crs
        if not crs.isValid():
            crs = QgsCoordinateReferenceSystem(srs) if srs else default_crs
        if crs.isValid() and target_crs.isValid() and crs != target_crs:
            geometry.transform(QgsCoordinateTransform(crs, target_crs, project))
        return geometry, None
    return None, "GeometryProperty yok"


def _value(text, field):
    text = text.strip()
    if text == "":
        return None
    if field["type"] in ("int", "long"):
        return int(float(text.replace(",", ".")))
    if field["type"] == "double":
        return float(text.replace(",", "."))
    if field["type"] == "dateTime":
        value = QDateTime.fromString(text, Qt.DateFormat.ISODate)
        return value if value.isValid() else text
    return text


def import_plangml_gml(gml_path, output_path, level=None, crs=None, feedback=None, project=None):
    project = project or QgsProject.instance()
    document = load_document(gml_path)
    reason = "kullanıcı seçimi"
    if level is None:
        level, reason = detect_level(document)
    schema = all_levels()[level]
    types = {t["name"]: t for t in schema["feature_types"]}
    elements, unknown_elements = feature_elements(document, set(types))
    if not elements:
        raise ValueError(f'Dosyada {level} şemasına ait nesne yok.')

    default_crs = crs if crs is not None and crs.isValid() else QgsCoordinateReferenceSystem()
    if not default_crs.isValid():
        srs = re.search(r'srsName="([^"]+)"', document.toString())
        if srs:
            default_crs = QgsCoordinateReferenceSystem.fromOgcWmsCrs(srs.group(1))
    if not default_crs.isValid():
        raise ValueError('GML dosyasında koordinat sistemi (srsName) yok; koordinat sistemini seçin.')
    create_plangml_workspace(output_path, default_crs, level)

    report, targets, batches = {}, {}, {}
    for step, element in enumerate(elements):
        if feedback is not None:
            if feedback.isCanceled():
                break
            if step % 200 == 0:
                feedback.setProgress(100 * step / len(elements))
        type_name = _local(element)
        feature_type = types[type_name]
        row = report.setdefault(type_name, {"tip": type_name, "adet": 0, "aktarilan": 0, "geometri_sorunu": 0,
                                            "bilinmeyen_oznitelik": "", "kod_listesi_disi": 0, "ornek_sorun": ""})
        row["adet"] += 1
        target = targets.get(type_name)
        if target is None:
            target = QgsVectorLayer(f"{Path(output_path).resolve()}|layername={type_name}", type_name, "ogr")
            targets[type_name], batches[type_name] = target, []
        out = QgsFeature(target.fields())
        fields = {f["name"]: f for f in feature_type["fields"]}
        unknown = set(filter(None, row["bilinmeyen_oznitelik"].split(", ")))
        for child in _children(element):
            name = _local(child)
            if name == "GeometryProperty":
                continue
            field = fields.get(name)
            if field is None:
                unknown.add(name)
                continue
            try:
                value = _value(child.text(), field)
            except ValueError:
                row["ornek_sorun"] = row["ornek_sorun"] or f"{name} değeri sayı değil: {child.text()[:30]}"
                continue
            if field["type"] == "enum" and value is not None and value not in schema["codelists"][field["codelist"]]:
                row["kod_listesi_disi"] += 1
                row["ornek_sorun"] = row["ornek_sorun"] or f"{name}={value}"
            out[name] = value
        row["bilinmeyen_oznitelik"] = ", ".join(sorted(unknown))
        if feature_type["geometry"] is not None:
            geometry, problem = _geometry(element, target.crs(), default_crs, project)
            if geometry is not None and geometry.type() != FAMILY[feature_type["geometry"]]:
                geometry, problem = None, "geometri türü şemaya uymuyor"
            if geometry is None:
                row["geometri_sorunu"] += 1
                row["ornek_sorun"] = row["ornek_sorun"] or problem
                continue
            if feature_type["geometry"].startswith("Multi"):
                geometry.convertToMultiType()
            elif geometry.isMultipart():
                parts = geometry.asGeometryCollection()
                if len(parts) != 1:
                    row["geometri_sorunu"] += 1
                    row["ornek_sorun"] = row["ornek_sorun"] or "çok parçalı geometri tek parçalı tipte"
                    continue
                geometry = parts[0]
            out.setGeometry(geometry)
        batches[type_name].append(out)
        row["aktarilan"] += 1
    for type_name, features in batches.items():
        if features:
            ok, _ = targets[type_name].dataProvider().addFeatures(features)
            if not ok:
                raise RuntimeError(f'{type_name}: nesneler yazılamadı: ' + "; ".join(targets[type_name].dataProvider().errors()[-3:]))
    summary = {"kademe": level, "sema": schema["xsd"]["file"], "belirleme": reason,
               "bilinmeyen_ogeler": unknown_elements}
    return str(output_path), summary, sorted(report.values(), key=lambda r: r["tip"])
