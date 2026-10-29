"""Kademe dönüşümü: bir MPYY 1.1.7 çalışma alanını üst kademeye (UİP → NİP → ÇDP) aktarır.

Rules come from ``styles/mpyy_level_conversion.json`` (built by
``tools/build_mpyy_level_tables.py``). A source feature is identified by its
type and code (``Konut|KonutTip=YerlesikKonut``); the rule gives the target type
and code. Codes a coarser plan must decide itself (density classes, the kind of
education area) are left empty and listed in the report; the schema audit then
flags them. Geometry is copied, not generalised: merging parcels into plan-scale
blocks is a planning decision.
"""

import json
from pathlib import Path

from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

from .attr_utils import is_null_value
from .mpyy_import import FAMILY, workspace_level
from .mpyy_workspace import create_mpyy_workspace, level_schema

RULES_PATH = Path(__file__).resolve().parents[1] / "styles" / "mpyy_level_conversion.json"
ORDER = ("UIP", "NIP", "CDP")


def _rules(source, target):
    pairs = json.loads(RULES_PATH.read_text(encoding="utf-8"))["pairs"]
    key = f"{source}>{target}"
    if key not in pairs:
        raise ValueError(f'{source} → {target} dönüşümü desteklenmiyor; yalnız üst kademeye (UİP → NİP → ÇDP) aktarılır.')
    return pairs[key]


def _identities(feature, feature_type):
    """Most specific first: one key per filled code field, then the bare type."""
    keys = []
    for field in feature_type["fields"]:
        if field["type"] == "enum":
            value = feature[field["name"]]
            if not is_null_value(value):
                keys.append(f'{feature_type["name"]}|{field["name"]}={value}')
    return keys + [feature_type["name"]]


def convert_workspace(source_path, target_path, target_level, feedback=None):
    source_level = workspace_level(source_path)
    if source_level is None:
        raise ValueError('Kaynak dosya MPYY 1.1.7 çalışma alanı değil.')
    if source_level not in ORDER:
        raise ValueError(
            f'Kaynak kademe ({source_level}) kademe dönüşümünü desteklemiyor; yalnız UİP → NİP → ÇDP desteklenir.'
        )
    if target_level not in ORDER:
        raise ValueError(f'Geçersiz hedef plan kademesi: {target_level}')
    if ORDER.index(target_level) <= ORDER.index(source_level):
        raise ValueError('Hedef kademe kaynaktan daha üst ölçekli olmalıdır (UİP → NİP → ÇDP).')
    table = _rules(source_level, target_level)
    source_types = level_schema(source_level)["feature_types"]
    target_types = {t["name"]: t for t in level_schema(target_level)["feature_types"]}

    crs = None
    for feature_type in source_types:
        if feature_type["geometry"]:
            probe = QgsVectorLayer(f"{Path(source_path).resolve()}|layername={feature_type['name']}", "probe", "ogr")
            if probe.isValid() and probe.crs().isValid():
                crs = probe.crs()
                break
    if crs is None or not crs.isValid():
        raise ValueError('Kaynak çalışma alanının koordinat sistemi okunamadı.')
    create_mpyy_workspace(target_path, crs, target_level)

    report, targets, batches = {}, {}, {}
    for step, feature_type in enumerate(source_types):
        if feedback is not None:
            if feedback.isCanceled():
                break
            feedback.setProgress(100 * step / len(source_types))
        layer = QgsVectorLayer(f"{Path(source_path).resolve()}|layername={feature_type['name']}", feature_type["name"], "ogr")
        if not layer.isValid() or layer.featureCount() == 0:
            continue
        for feature in layer.getFeatures():
            keys = _identities(feature, feature_type)
            key = next((k for k in keys if k in table["rules"]), None)
            report_key = key or keys[0]
            row = report.setdefault(report_key, {"kaynak": report_key, "adet": 0, "hedef": "", "aktarilan": 0,
                                                 "doldurulacak": "", "durum": ""})
            row["adet"] += 1
            if key is None:
                row["durum"] = f"{target_level} şemasında karşılığı yok"
                continue
            rule = table["rules"][key]
            target_type = target_types[rule["feature"]]
            row["hedef"] = rule["feature"] + "".join(f"|{k}={v}" for k, v in rule["attrs"].items())
            row["doldurulacak"] = ", ".join(rule.get("doldurulacak", []))
            if FAMILY.get(target_type["geometry"]) != FAMILY.get(feature_type["geometry"]):
                row["durum"] = "Geometri uyuşmuyor"
                continue
            target = targets.get(rule["feature"])
            if target is None:
                target = QgsVectorLayer(f"{Path(target_path).resolve()}|layername={rule['feature']}", rule["feature"], "ogr")
                targets[rule["feature"]] = target
                batches[rule["feature"]] = []
            geometry = QgsGeometry(feature.geometry())
            target_geom_type = target_type["geometry"] or ""
            if target_geom_type.startswith("Multi"):
                geometry.convertToMultiType()
                parts = [geometry]
            elif geometry.isMultipart():
                parts = [part for part in geometry.asGeometryCollection() if not part.isEmpty()]
            else:
                parts = [geometry]
            target_fields = {f["name"] for f in target_type["fields"]}
            for part in parts:
                out = QgsFeature(target.fields())
                out.setGeometry(part)
                for field in feature_type["fields"]:
                    if field["name"] in target_fields and field["type"] != "enum":
                        val = feature[field["name"]]
                        if not is_null_value(val):
                            out[field["name"]] = val
                for name, value in rule["attrs"].items():
                    out[name] = value
                batches[rule["feature"]].append(out)
            row["aktarilan"] += len(parts)
            row["durum"] = "aktarıldı" + ("; " + row["doldurulacak"] + " girilmeli" if row["doldurulacak"] else "")
    for name, features in batches.items():
        ok, _ = targets[name].dataProvider().addFeatures(features)
        if not ok:
            raise RuntimeError(f'{name}: nesneler yazılamadı: ' + "; ".join(targets[name].dataProvider().errors()[-3:]))
    return str(target_path), sorted(report.values(), key=lambda r: r["kaynak"])
