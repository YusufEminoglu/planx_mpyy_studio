"""Processing algorithms for PlanX MPYY Studio."""

from .core.localization import display_label
from .gui.processing_text import LocalizedProcessingAlgorithm, tool_text

from pathlib import Path
import math
import sqlite3
import uuid
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterDistance,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorLayer,
    QgsProcessingProvider,
    QgsProject,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import QMetaType


class CreateLandUseWorkspace(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "create_land_use_workspace"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "workspace"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CreateLandUseWorkspace()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterCrs('KRS', 'Çalışma alanı koordinat sistemi'))
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OUTPUT", 'Çıktı katmanı', 'GeoPackage (*.gpkg)'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.db_factory import create_land_use_workspace

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')
        path = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        crs = self.parameterAsCrs(parameters, 'KRS', context)
        try:
            result = create_land_use_workspace(path, crs)
        except (ValueError, OSError, RuntimeError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        feedback.pushInfo('Arazi Kullanımı çalışma ortamı oluşturuldu: ' + result)
        return {"OUTPUT": result}


class CalculateBuildingEnvelopeAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "calculate_building_envelope"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "analysis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CalculateBuildingEnvelopeAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "DISTANCE", 'Çekme Mesafesi (m)', defaultValue=3.0, parentParameterName="INPUT"
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT", 'Çıktı katmanı'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.actions import calculate_setback_envelope

        source = self.parameterAsSource(parameters, "INPUT", context)
        dist = self.parameterAsDouble(parameters, "DISTANCE", context)

        (sink, dest_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, source.fields(), source.wkbType(), source.sourceCrs()
        )

        features = source.getFeatures()
        for current, feat in enumerate(features):
            if feedback.isCanceled():
                break
            in_geom = feat.geometry()
            out_geom = calculate_setback_envelope(in_geom, dist)
            out_feat = QgsFeature(feat)
            out_feat.setGeometry(out_geom)
            sink.addFeature(out_feat)

        return {"OUTPUT": dest_id}


class ExecuteCrosswalkAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "crosswalk_saha_to_plan"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "crosswalk"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ExecuteCrosswalkAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                "FIELD", 'İşlev kodu alanı', defaultValue="P_FONK", parentLayerParameterName="INPUT"
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı')
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.crosswalk import evaluate_crosswalk

        source = self.parameterAsSource(parameters, "INPUT", context)
        field_name = self.parameterAsString(parameters, "FIELD", context)

        fields = QgsFields(source.fields())
        fields.append(QgsField("crosswalk_fonk", QMetaType.Type.QString, len=100))
        fields.append(QgsField("crosswalk_ust_grup", QMetaType.Type.QString, len=100))
        fields.append(QgsField("crosswalk_durum", QMetaType.Type.QString, len=30))
        fields.append(QgsField("crosswalk_adaylar", QMetaType.Type.QString, len=254))

        (sink, dest_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )

        total = source.featureCount()
        for idx, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            val = feat[field_name] if feat.fields().indexFromName(field_name) >= 0 else ""
            match = evaluate_crosswalk(str(val or ""))

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(feat.geometry())
            for fn in feat.fields().names():
                out_feat[fn] = feat[fn]

            out_feat["crosswalk_fonk"] = match.eslesen_fonksiyon
            out_feat["crosswalk_ust_grup"] = match.ust_grup
            out_feat["crosswalk_durum"] = match.durum
            out_feat["crosswalk_adaylar"] = ", ".join(match.aday_fonksiyonlar)
            sink.addFeature(out_feat)

            if total > 0 and idx % 200 == 0:
                feedback.setProgress(int(100 * idx / total))

        return {"OUTPUT": dest_id}


class SynthesizeParcelDensityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "synthesize_parcel_density"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "analysis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return SynthesizeParcelDensityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PARCELS", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
            "BUILDINGS", 'Yapı poligonları', [QgsProcessing.SourceType.TypeVectorPolygon], optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
            "PLANS", 'Plan işlevi poligonları', [QgsProcessing.SourceType.TypeVectorPolygon], optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı')
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.synthesis import SynthesisEngine

        p_source = self.parameterAsSource(parameters, "PARCELS", context)
        b_source = self.parameterAsSource(parameters, "BUILDINGS", context)
        plan_source = self.parameterAsSource(parameters, "PLANS", context)

        b_feats = list(b_source.getFeatures()) if b_source else []
        plan_feats = list(plan_source.getFeatures()) if plan_source else []

        fields = QgsFields(p_source.fields())
        fields.append(QgsField("fiili_taks", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("fiili_kaks", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("yapi_adedi", QMetaType.Type.Int))
        fields.append(QgsField("taban_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("insaat_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("hakim_kat", QMetaType.Type.Int))
        fields.append(QgsField("maks_kat", QMetaType.Type.Int))
        fields.append(QgsField("riskli_bina", QMetaType.Type.Int))
        fields.append(QgsField("hakim_plan_fonk", QMetaType.Type.QString, len=100))

        (sink, dest_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, p_source.wkbType(), p_source.sourceCrs()
        )

        plan_idx = QgsSpatialIndex()
        plan_map = {}
        for pf in plan_feats:
            if pf.hasGeometry() and not pf.geometry().isEmpty():
                plan_idx.addFeature(pf)
                plan_map[pf.id()] = pf

        b_idx = QgsSpatialIndex()
        b_map = {}
        for bf in b_feats:
            if bf.hasGeometry() and not bf.geometry().isEmpty():
                b_idx.addFeature(bf)
                b_map[bf.id()] = bf

        total = p_source.featureCount()
        for idx, p_feat in enumerate(p_source.getFeatures()):
            if feedback.isCanceled():
                break
            res = SynthesisEngine.synthesize_parcel(
                p_feat,
                plan_feats,
                b_feats,
                candidate_index=plan_idx,
                candidate_map=plan_map,
                building_index=b_idx,
                building_map=b_map,
            )

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(p_feat.geometry())
            for fn in p_feat.fields().names():
                out_feat[fn] = p_feat[fn]

            out_feat["fiili_taks"] = res.hesaplanan_taks
            out_feat["fiili_kaks"] = res.hesaplanan_kaks
            out_feat["yapi_adedi"] = res.bina_sayisi
            out_feat["taban_m2"] = res.toplam_taban_alani_m2
            out_feat["insaat_m2"] = res.toplam_insaat_alani_m2
            out_feat["hakim_kat"] = res.hakim_kat
            out_feat["maks_kat"] = res.maks_kat
            out_feat["riskli_bina"] = res.riskli_bina_sayisi
            out_feat["hakim_plan_fonk"] = res.hakim_plan_fonksiyonu
            sink.addFeature(out_feat)

            if total > 0 and idx % 200 == 0:
                feedback.setProgress(int(100 * idx / total))

        return {"OUTPUT": dest_id}


class ValidateQualityControlAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "validate_quality_control"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "qc"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ValidateQualityControlAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PARCELS", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
            "BUILDINGS", 'Yapı poligonları', [QgsProcessing.SourceType.TypeVectorPolygon], optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "SETBACK", 'Çekme Mesafesi (m)', defaultValue=3.0, parentParameterName="PARCELS"
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı')
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.qc_engine import QualityControlEngine

        p_source = self.parameterAsSource(parameters, "PARCELS", context)
        b_source = self.parameterAsSource(parameters, "BUILDINGS", context)
        setback_m = self.parameterAsDouble(parameters, "SETBACK", context)

        p_feats = list(p_source.getFeatures())
        b_feats = list(b_source.getFeatures()) if b_source else []

        anomalies = QualityControlEngine.run_comprehensive_qc(p_feats, b_feats, setback_m=setback_m)

        fields = QgsFields()
        fields.append(QgsField("hata_turu", QMetaType.Type.QString, len=50))
        fields.append(QgsField("ciddiyet", QMetaType.Type.QString, len=20))
        fields.append(QgsField("nesne_id", QMetaType.Type.QString, len=100))
        fields.append(QgsField("aciklama", QMetaType.Type.QString, len=254))

        (sink, dest_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, QgsProcessing.SourceType.TypeVectorPolygon, p_source.sourceCrs()
        )

        for anom in anomalies:
            if feedback.isCanceled():
                break
            if not anom.geometri or anom.geometri.isEmpty():
                continue
            feat = QgsFeature(fields)
            feat.setGeometry(anom.geometri)
            feat["hata_turu"] = anom.tur
            feat["ciddiyet"] = anom.ciddiyet
            feat["nesne_id"] = str(anom.nesne_id)
            feat["aciklama"] = anom.aciklama
            sink.addFeature(feat)

        feedback.pushInfo(f'Kalite kontrolü tamamlandı: {len(anomalies)} anomali tespit edildi.')
        return {"OUTPUT": dest_id, "ANOMALY_COUNT": len(anomalies)}


class IngestVectorDatasetAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "ingest_vector_dataset"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "workspace"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return IngestVectorDatasetAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "TARGET_LAYER", 'Hedef GeoPackage katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        target_param = parameters.get("TARGET_LAYER")
        target_layer = target_param if isinstance(target_param, QgsVectorLayer) else self.parameterAsVectorLayer(parameters, "TARGET_LAYER", context)

        if target_layer is None or not target_layer.isValid():
            raise QgsProcessingException('Hedef MPYY katmanı geçerli değil.')

        source = self.parameterAsSource(parameters, "INPUT", context)
        if source is None:
            input_param = parameters.get("INPUT")
            if isinstance(input_param, QgsVectorLayer):
                source = input_param

        if source is None:
            raise QgsProcessingException('Kaynak katman okunamadı veya parametre geçersiz.')

        src_fields = source.fields()
        tgt_fields = target_layer.fields()
        tgt_names = set(tgt_fields.names())

        alias_map = {
            "ADA": ("ada", "ada_no", "adano", "block"),
            "PARSEL": ("parsel", "parsel_no", "parselno", "lot"),
            "MAHALLE": ("mahalle", "mahalle_adi", "mah", "koy"),
            "IL": ("il", "il_adi", "sehir"),
            "ILCE": ("ilce", "ilce_adi"),
            "NITELIK": ("nitelik", "cins", "tapu_cinsi"),
            "MEVKII": ("mevkii", "mevki"),
            "B_KAT": ("kat", "kat_adedi", "kat_sayisi", "kat_sayi", "b_kat"),
            "P_KAT": ("kat", "kat_adedi", "kat_sayisi", "p_kat"),
            "B_FONK": ("bina_fonk", "bina_kullanimi", "fonksiyon", "kullanim", "b_fonk"),
            "P_FONK": ("parsel_fonk", "fonksiyon", "kullanim", "p_fonk"),
            "Y_AD": ("yol_adi", "yol_ad", "cadde", "sokak", "ad", "y_ad"),
            "Y_TIP": ("yol_tipi", "kademe", "y_tip", "tip"),
            "Y_GENISLIK": ("genislik", "yol_genisligi", "y_genislik", "yol_gen"),
            "Y_KAPLAMA": ("kaplama", "kaplama_turu", "y_kaplama"),
            "uipfonksiyon": ("uip_fonksiyon", "fonksiyon", "plan_fonk", "uipfonksiyon"),
        }

        mapping = {}
        for tgt_f in tgt_fields:
            tgt_name = tgt_f.name()
            idx = src_fields.indexFromName(tgt_name)
            if idx >= 0:
                mapping[tgt_name] = src_fields.at(idx).name()
                continue
            for src_f in src_fields:
                if src_f.name().lower() == tgt_name.lower():
                    mapping[tgt_name] = src_f.name()
                    break
            if tgt_name in mapping:
                continue
            aliases = alias_map.get(tgt_name, ())
            for src_f in src_fields:
                if src_f.name().lower() in aliases:
                    mapping[tgt_name] = src_f.name()
                    break

        transform = QgsCoordinateTransform(source.sourceCrs(), target_layer.crs(), context.transformContext())

        target_layer.startEditing()
        added_count = 0
        total = source.featureCount()

        features_to_add = []
        for idx, src_feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break

            geom = src_feat.geometry()
            if geom and not geom.isEmpty():
                new_geom = QgsGeometry(geom)
                if source.sourceCrs() != target_layer.crs():
                    new_geom.transform(transform)
            else:
                new_geom = QgsGeometry()

            out_feat = QgsFeature(tgt_fields)
            out_feat.setGeometry(new_geom)

            for tgt_col, src_col in mapping.items():
                val = src_feat[src_col]
                if val is not None:
                    out_feat[tgt_col] = val

            if "alan_m2" in tgt_names and not out_feat["alan_m2"] and not new_geom.isEmpty():
                out_feat["alan_m2"] = round(new_geom.area(), 2)
            if "AlanM2" in tgt_names and not out_feat["AlanM2"] and not new_geom.isEmpty():
                out_feat["AlanM2"] = round(new_geom.area(), 2)
            if "uzunluk_m" in tgt_names and not out_feat["uzunluk_m"] and not new_geom.isEmpty():
                out_feat["uzunluk_m"] = round(new_geom.length(), 2)
            if "Uzunluk(m)" in tgt_names and not out_feat["Uzunluk(m)"] and not new_geom.isEmpty():
                out_feat["Uzunluk(m)"] = round(new_geom.length(), 2)

            if "global_id" in tgt_names and not out_feat["global_id"]:
                out_feat["global_id"] = str(uuid.uuid4())

            features_to_add.append(out_feat)
            added_count += 1

            if len(features_to_add) >= 500:
                target_layer.addFeatures(features_to_add)
                features_to_add.clear()

            if total > 0 and idx % 200 == 0:
                feedback.setProgress(int(100 * idx / total))

        if features_to_add:
            target_layer.addFeatures(features_to_add)

        target_layer.commitChanges()
        target_layer.updateExtents()
        feedback.pushInfo(f"Başarıyla {added_count} adet nesne '{target_layer.name()}' katmanına aktarıldı.")
        return {"IMPORTED_COUNT": added_count, "OUTPUT": target_layer.id()}


class PackageForQFieldAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "package_for_qfield"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "field_survey"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return PackageForQFieldAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFile(
                "INPUT_GPKG",
                'Plan GeoPackage dosyası',
                extension="gpkg",
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                "OUTPUT_DIR",
                'Çıktı klasörü',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PROJECT_TITLE",
                'Proje başlığı',
                defaultValue='PlanX MPYY Saha Anketi Projesi',
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "INCLUDE_OSM",
                'OSM altlığını ekle',
                defaultValue=True,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.qfield_packager import package_for_qfield

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        gpkg_path = self.parameterAsFile(parameters, "INPUT_GPKG", context)
        out_dir = self.parameterAsString(parameters, "OUTPUT_DIR", context)
        title = self.parameterAsString(parameters, "PROJECT_TITLE", context)
        include_osm = self.parameterAsBoolean(parameters, "INCLUDE_OSM", context)

        if not gpkg_path:
            raise QgsProcessingException("Kaynak GeoPackage yolu belirtilmelidir.")
        if not out_dir:
            raise QgsProcessingException('Çıktı klasörü belirtilmelidir.')

        try:
            res = package_for_qfield(
                gpkg_path=gpkg_path,
                output_dir=out_dir,
                project_title=title,
                include_osm=include_osm,
            )
        except Exception as err:
            raise QgsProcessingException(f'QField paketi oluşturulurken hata: {err}') from err

        feedback.pushInfo(f"QField paketi başarıyla oluşturuldu: {res['output_dir']}")
        return {
            "OUTPUT_DIR": res["output_dir"],
            "PROJECT_FILE": res["project_file"],
            "GPKG_FILE": res["gpkg_file"],
        }


class CleanPlanningGeometriesAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "clean_planning_geometries"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "geometry"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CleanPlanningGeometriesAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT",
                'Girdi katmanı',
                types=[QgsProcessing.SourceType.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "SNAP_TOLERANCE",
                'Yakalama toleransı (m)',
                defaultValue=0.05,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "MIN_AREA",
            'Asgari poligon alanı (m²)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.5,
                minValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "AUTO_HEAL_GAPS",
                'Küçük boşlukları otomatik onar',
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.geom_cleaner import clean_layer_geometries

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        source = self.parameterAsSource(parameters, "INPUT", context)
        snap_tol = self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context)
        min_area = self.parameterAsDouble(parameters, "MIN_AREA", context)

        sink, dest_id = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        processed, repaired, removed = clean_layer_geometries(
            source_layer=source,
            sink=sink,
            snap_tolerance=snap_tol,
            min_area_m2=min_area,
            feedback=feedback,
        )

        feedback.pushInfo(
            f'İşlem tamamlandı: {processed} nesne incelendi, {repaired} geometri onarıldı, {removed} boş/sliver nesne elendi.'
        )
        return {
            "OUTPUT": dest_id,
            "PROCESSED_COUNT": processed,
            "REPAIRED_COUNT": repaired,
            "REMOVED_COUNT": removed,
        }


class ExportPlanningReportAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "export_planning_report"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "reporting"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ExportPlanningReportAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFile(
                "INPUT_GPKG",
                'Plan GeoPackage dosyası',
                extension="gpkg",
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                "OUTPUT_DIR",
                'Çıktı klasörü',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "REPORT_TITLE",
                'Rapor başlığı',
                defaultValue='PlanX MPYY - Plan Açıklama Raporu Tabloları ve Arazi Analizi',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.report_exporter import export_planning_report

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        gpkg_path = self.parameterAsFile(parameters, "INPUT_GPKG", context)
        out_dir = self.parameterAsString(parameters, "OUTPUT_DIR", context)
        title = self.parameterAsString(parameters, "REPORT_TITLE", context)

        if not gpkg_path:
            raise QgsProcessingException("Kaynak GeoPackage yolu belirtilmelidir.")
        if not out_dir:
            raise QgsProcessingException('Çıktı klasörü belirtilmelidir.')

        try:
            res = export_planning_report(
                gpkg_path=gpkg_path,
                output_dir=out_dir,
                report_title=title,
            )
        except Exception as err:
            raise QgsProcessingException(f'Rapor üretilirken hata oluştu: {err}') from err

        feedback.pushInfo(f"Rapor başarıyla üretildi: {res['html_report']} ({res['table_count']} tablo)")
        return {
            "HTML_REPORT": res["html_report"],
            "CSV_DIRECTORY": res["csv_directory"],
            "TABLE_COUNT": res["table_count"],
        }


class AnalyzeAmenityStandardsAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "analyze_amenity_standards"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "standards"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeAmenityStandardsAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PLAN_LAYER",
                'Plan poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "POPULATION",
                'Çalışma nüfusu',
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=10000,
                minValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                "FIELD",
                'İşlev kodu alanı',
                optional=True,
                parentLayerParameterName="PLAN_LAYER",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.synthesis import SynthesisEngine

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        source = self.parameterAsSource(parameters, "PLAN_LAYER", context)
        if source is None:
            p = parameters.get("PLAN_LAYER")
            if isinstance(p, QgsVectorLayer):
                source = p
        population = self.parameterAsInt(parameters, "POPULATION", context) or int(parameters.get("POPULATION", 1000))
        field_name = self.parameterAsString(parameters, "FIELD", context) or str(parameters.get("FIELD", "detay_katalogu"))

        if source is None:
            raise QgsProcessingException('Geçerli bir plan katmanı seçilmelidir.')

        features = list(source.getFeatures())
        amenity_totals = SynthesisEngine.extract_amenities_from_features(features, function_field=field_name)
        results = SynthesisEngine.analyze_all_amenities(population, amenity_totals, region_name=source.sourceName())

        fields = QgsFields()
        fields.append(QgsField("kategori", QMetaType.Type.QString, len=50))
        fields.append(QgsField("mevcut_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("mevcut_ha", QMetaType.Type.Double, prec=4))
        fields.append(QgsField("standart_m2_kisi", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("gerekli_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("fiili_m2_kisi", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("acik_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("yeterlilik", QMetaType.Type.QString, len=20))
        fields.append(QgsField("karsilama_orani", QMetaType.Type.Double, prec=1))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            QgsWkbTypes.Type.NoGeometry,
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı tablosu oluşturulamadı.')

        total_amenity_m2 = 0.0
        total_deficit_m2 = 0.0
        deficit_count = 0

        for r in results:
            cat_name = r.bolge_adi.split(" - ")[-1]
            total_amenity_m2 += r.mevcut_yesil_alan_m2
            total_deficit_m2 += r.yesil_alan_acigi_m2
            if r.yeterlilik_durumu != 'YETERLİ':
                deficit_count += 1

            karsilama = round(100.0 * r.mevcut_yesil_alan_m2 / r.gerekli_yesil_alan_m2, 1) if r.gerekli_yesil_alan_m2 > 0 else 100.0

            feat = QgsFeature(fields)
            feat["kategori"] = cat_name
            feat["mevcut_m2"] = r.mevcut_yesil_alan_m2
            feat["mevcut_ha"] = round(r.mevcut_yesil_alan_m2 / 10000.0, 4)
            feat["standart_m2_kisi"] = r.standart_m2_kisi
            feat["gerekli_m2"] = r.gerekli_yesil_alan_m2
            feat["fiili_m2_kisi"] = r.kisi_basi_mevcut_m2
            feat["acik_m2"] = r.yesil_alan_acigi_m2
            feat["yeterlilik"] = r.yeterlilik_durumu
            feat["karsilama_orani"] = karsilama
            sink.addFeature(feat)

        feedback.pushInfo(
            f'MPYY EK-2 Donatı analizi tamamlandı: {len(results)} kategori, {round(total_amenity_m2, 1)} m² donatı, {deficit_count} yetersiz alan.'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_POPULATION": population,
            "TOTAL_AMENITY_M2": round(total_amenity_m2, 2),
            "DEFICIT_COUNT": deficit_count,
            "TOTAL_DEFICIT_M2": round(total_deficit_m2, 2),
        }


class EvaluatePlanRevisionAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "evaluate_plan_revision"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "revision"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return EvaluatePlanRevisionAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "CURRENT_PLAN",
                'Onaylı plan',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "REVISED_PLAN",
                'Önerilen plan',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "SERVICE_RADIUS",
                'Hizmet yarıçapı (m)',
                defaultValue=500.0,
                minValue=50.0,
                parentParameterName="CURRENT_PLAN",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plan_diff import PlanRevisionDiffEngine

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        curr_source = self.parameterAsSource(parameters, "CURRENT_PLAN", context)
        if curr_source is None:
            p = parameters.get("CURRENT_PLAN")
            if isinstance(p, QgsVectorLayer):
                curr_source = p

        rev_source = self.parameterAsSource(parameters, "REVISED_PLAN", context)
        if rev_source is None:
            p = parameters.get("REVISED_PLAN")
            if isinstance(p, QgsVectorLayer):
                rev_source = p

        radius = self.parameterAsDouble(parameters, "SERVICE_RADIUS", context) or float(parameters.get("SERVICE_RADIUS", 500.0))

        if curr_source is None or rev_source is None:
            raise QgsProcessingException('Her iki plan katmanı da belirtilmelidir.')

        curr_feats = list(curr_source.getFeatures())
        rev_feats = list(rev_source.getFeatures())

        diff_features, summary = PlanRevisionDiffEngine.evaluate_revision(
            current_features=curr_feats,
            revised_features=rev_feats,
            service_radius_m=radius,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("degisim_turu", QMetaType.Type.QString, len=40))
        fields.append(QgsField("onceki_fonk", QMetaType.Type.QString, len=100))
        fields.append(QgsField("onceki_grup", QMetaType.Type.QString, len=100))
        fields.append(QgsField("onceki_donati", QMetaType.Type.QString, len=50))
        fields.append(QgsField("yeni_fonk", QMetaType.Type.QString, len=100))
        fields.append(QgsField("yeni_grup", QMetaType.Type.QString, len=100))
        fields.append(QgsField("yeni_donati", QMetaType.Type.QString, len=50))
        fields.append(QgsField("alan_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("esdeger_uygun", QMetaType.Type.QString, len=20))
        fields.append(QgsField("madde_26_notu", QMetaType.Type.QString, len=254))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            QgsWkbTypes.Type.MultiPolygon,
            curr_source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        for df in diff_features:
            if feedback.isCanceled():
                break
            if not df.geometri or df.geometri.isEmpty():
                continue

            feat = QgsFeature(fields)
            feat.setGeometry(df.geometri)
            feat["degisim_turu"] = df.degisim_turu
            feat["onceki_fonk"] = df.onceki_fonk
            feat["onceki_grup"] = df.onceki_grup
            feat["onceki_donati"] = df.onceki_donati_kodu or "-"
            feat["yeni_fonk"] = df.yeni_fonk
            feat["yeni_grup"] = df.yeni_grup
            feat["yeni_donati"] = df.yeni_donati_kodu or "-"
            feat["alan_m2"] = df.alan_m2
            feat["esdeger_uygun"] = "UYGUN" if df.esdeger_alan_uygun else ('YETERSİZ' if df.degisim_turu == "DONATI_KALDIRILDI" else "UYGULANMAZ")
            feat["madde_26_notu"] = df.aciklama
            sink.addFeature(feat)

        for u in summary.uyarilar:
            feedback.pushWarning(u)

        feedback.pushInfo(
            f'Plan değişikliği analizi tamamlandı: {len(diff_features)} parça. Kaldırılan donatı: {summary.kaldirilan_donati_m2} m², Yeni donatı: {summary.yeni_eklenen_donati_m2} m².'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_DIFF_FEATURES": len(diff_features),
            "REMOVED_AMENITY_M2": summary.kaldirilan_donati_m2,
            "ADDED_AMENITY_M2": summary.yeni_eklenen_donati_m2,
            "NET_AMENITY_CHANGE_M2": summary.net_donati_degisimi_m2,
            "MADDE_26_COMPLIANT": summary.madde_26_uygunlugu,
        }


class CalculateDOPAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "calculate_dop_reallocation"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "reallocation"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CalculateDOPAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "CADASTRE_LAYER",
                'Kadastro parsel poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PUBLIC_LAYER",
                'Kamu alanı poligonları (isteğe bağlı)',
                [QgsProcessing.SourceType.TypeVectorPolygon],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "MANUAL_PUBLIC_M2",
                'Elle girilen kamu alanı (m²)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
                minValue=0.0,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "FORCED_DOP_RATIO",
                'DOP oranını değiştir (isteğe bağlı)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.0,
                minValue=0.0,
                maxValue=1.0,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.dop_engine import DOPEngine

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        cad_source = self.parameterAsSource(parameters, "CADASTRE_LAYER", context)
        if cad_source is None:
            p = parameters.get("CADASTRE_LAYER")
            if isinstance(p, QgsVectorLayer):
                cad_source = p

        if cad_source is None:
            raise QgsProcessingException('Kadastro parsel katmanı seçilmelidir.')

        pub_source = self.parameterAsSource(parameters, "PUBLIC_LAYER", context)
        if pub_source is None:
            p = parameters.get("PUBLIC_LAYER")
            if isinstance(p, QgsVectorLayer):
                pub_source = p

        manual_public = self.parameterAsDouble(parameters, "MANUAL_PUBLIC_M2", context) or float(parameters.get("MANUAL_PUBLIC_M2", 0.0))
        forced_ratio = self.parameterAsDouble(parameters, "FORCED_DOP_RATIO", context) or float(parameters.get("FORCED_DOP_RATIO", 0.0))

        cad_feats = list(cad_source.getFeatures())
        pub_feats = list(pub_source.getFeatures()) if pub_source else []

        ratio_arg = forced_ratio if forced_ratio > 0 else None
        results, summary = DOPEngine.calculate_dop(
            cadastral_features=cad_feats,
            public_features=pub_feats if pub_feats else None,
            manual_public_area_m2=manual_public,
            forced_dop_ratio=ratio_arg,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("ada", QMetaType.Type.QString, len=30))
        fields.append(QgsField("parsel", QMetaType.Type.QString, len=30))
        fields.append(QgsField("malik", QMetaType.Type.QString, len=100))
        fields.append(QgsField("kadastro_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("dop_orani", QMetaType.Type.Double, prec=4))
        fields.append(QgsField("dop_kesinti_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("net_tahsis_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("yasal_durum", QMetaType.Type.QString, len=30))
        fields.append(QgsField("aciklama", QMetaType.Type.QString, len=254))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            QgsWkbTypes.Type.MultiPolygon,
            cad_source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        for r in results:
            feat = QgsFeature(fields)
            if r.geometri and not r.geometri.isEmpty():
                feat.setGeometry(r.geometri)
            feat["ada"] = r.ada
            feat["parsel"] = r.parsel
            feat["malik"] = r.malik
            feat["kadastro_m2"] = r.kadastro_alani_m2
            feat["dop_orani"] = r.dop_orani
            feat["dop_kesinti_m2"] = r.dop_kesintisi_m2
            feat["net_tahsis_m2"] = r.net_tahsis_m2
            feat["yasal_durum"] = r.yasal_durum
            feat["aciklama"] = r.aciklama
            sink.addFeature(feat)

        for u in summary.uyarilar:
            feedback.pushWarning(u)

        feedback.pushInfo(
            f'DOP hesabı tamamlandı. Toplam kadastro alanı: {summary.toplam_kadastro_m2} m², Terk: {summary.toplam_terk_m2} m², DOPO: %{summary.dop_orani * 100:.2f} satır bulundu.'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_CADASTRE_M2": summary.toplam_kadastro_m2,
            "TOTAL_PUBLIC_M2": summary.toplam_terk_m2,
            "TOTAL_ALLOCATION_M2": summary.toplam_tahsis_m2,
            "DOP_RATIO": summary.dop_orani,
            "COMPLIANT_WITH_CEILING": summary.yasal_uygun,
            "EXCESS_AREA_M2": summary.kop_veya_kamulastirma_gerekli_m2,
            "PARCEL_COUNT": summary.parsel_sayisi,
        }


class EstimatePlanCapacityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "estimate_plan_capacity"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "capacity"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return EstimatePlanCapacityAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PLAN_LAYER",
                'Plan poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DEFAULT_KAKS",
                'Varsayılan emsal (KAKS)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=1.2,
                minValue=0.1,
                maxValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DEFAULT_TAKS",
                'Varsayılan taban alanı oranı (TAKS)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.35,
                minValue=0.05,
                maxValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "AVG_UNIT_M2",
                'Ortalama konut alanı (m²)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=100.0,
                minValue=20.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "HOUSEHOLD_SIZE",
                'Ortalama hane halkı büyüklüğü',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=3.2,
                minValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.capacity_engine import PlanCapacityEngine

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        plan_source = self.parameterAsSource(parameters, "PLAN_LAYER", context)
        if plan_source is None:
            p = parameters.get("PLAN_LAYER")
            if isinstance(p, QgsVectorLayer):
                plan_source = p

        if plan_source is None:
            raise QgsProcessingException('İmar planı katmanı seçilmelidir.')

        kaks = self.parameterAsDouble(parameters, "DEFAULT_KAKS", context) or float(parameters.get("DEFAULT_KAKS", 1.2))
        taks = self.parameterAsDouble(parameters, "DEFAULT_TAKS", context) or float(parameters.get("DEFAULT_TAKS", 0.35))
        unit_m2 = self.parameterAsDouble(parameters, "AVG_UNIT_M2", context) or float(parameters.get("AVG_UNIT_M2", 100.0))
        household = self.parameterAsDouble(parameters, "HOUSEHOLD_SIZE", context) or float(parameters.get("HOUSEHOLD_SIZE", 3.2))

        features = list(plan_source.getFeatures())
        items, summary = PlanCapacityEngine.estimate_capacity(
            plan_features=features,
            default_kaks=kaks,
            default_taks=taks,
            avg_unit_m2=unit_m2,
            household_size=household,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("fonksiyon", QMetaType.Type.QString, len=100))
        fields.append(QgsField("alan_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("taks", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("kaks", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("taban_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("insaat_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("konut_orani", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("konut_insaat_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("konut_sayisi", QMetaType.Type.Int))
        fields.append(QgsField("ongorulen_nufus", QMetaType.Type.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            QgsWkbTypes.Type.MultiPolygon,
            plan_source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        for item in items:
            feat = QgsFeature(fields)
            if item.geometri and not item.geometri.isEmpty():
                feat.setGeometry(item.geometri)
            feat["fonksiyon"] = item.fonksiyon
            feat["alan_m2"] = item.alan_m2
            feat["taks"] = item.taks
            feat["kaks"] = item.kaks
            feat["taban_m2"] = item.taban_alani_m2
            feat["insaat_m2"] = item.toplam_insaat_m2
            feat["konut_orani"] = item.konut_orani
            feat["konut_insaat_m2"] = item.konut_insaat_m2
            feat["konut_sayisi"] = item.konut_sayisi
            feat["ongorulen_nufus"] = item.ongorulen_nufus
            sink.addFeature(feat)

        feedback.pushInfo(
            f'Kapasite modellemesi tamamlandı: Toplam Konut Alanı: {summary.toplam_konut_alani_m2} m², İnşaat Alanı: {summary.toplam_insaat_m2} m², Konut Sayısı: {summary.toplam_konut_sayisi}, Öngörülen Nüfus: {summary.toplam_kapasite_nufusu} kişi, Brüt Yoğunluk: {summary.brut_yogunluk_kisi_ha} kişi/ha.'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_ZONING_AREA_M2": summary.toplam_imar_alani_m2,
            "TOTAL_RESIDENTIAL_AREA_M2": summary.toplam_konut_alani_m2,
            "TOTAL_CONSTRUCTION_M2": summary.toplam_insaat_m2,
            "TOTAL_UNITS": summary.toplam_konut_sayisi,
            "TOTAL_POPULATION": summary.toplam_kapasite_nufusu,
            "GROSS_DENSITY_PER_HA": summary.brut_yogunluk_kisi_ha,
            "AVERAGE_KAKS": summary.ortalama_kaks,
        }


class ValidatePAIYComplianceAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "validate_paiy_compliance"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "compliance"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ValidatePAIYComplianceAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PARCEL_LAYER",
                'Parsel poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "DEFAULT_NIZAM",
                'Varsayılan yapı nizamı',
                options=[
                    "Ayrık Nizam (AYRIK)",
                    "Bitişik Nizam (BITISIK)",
                    "İkiz Nizam (IKIZ)",
                    "Blok Nizam (BLOK)",
                    "Serbest Nizam (SERBEST)",
                ],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DEFAULT_FLOORS",
                'Varsayılan kat sayısı',
                type=QgsProcessingParameterNumber.Type.Integer,
                defaultValue=4,
                minValue=1,
                maxValue=50,
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "FRONT_SETBACK",
                'Ön bahçe mesafesi (m)',
                defaultValue=5.0,
                minValue=0.0,
                parentParameterName="PARCEL_LAYER",
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "SIDE_SETBACK",
                'Yan bahçe mesafesi (m)',
                defaultValue=3.0,
                minValue=0.0,
                parentParameterName="PARCEL_LAYER",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "MIN_CORE_M2",
                'Asgari yapılaşabilir çekirdek alanı (m²)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=30.0,
                minValue=5.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.compliance_engine import ComplianceEngine

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        source = self.parameterAsSource(parameters, "PARCEL_LAYER", context)
        if source is None:
            p = parameters.get("PARCEL_LAYER")
            if isinstance(p, QgsVectorLayer):
                source = p

        if source is None:
            raise QgsProcessingException('Lütfen parsel katmanını seçin.')

        nizam_opt = self.parameterAsEnum(parameters, "DEFAULT_NIZAM", context)
        nizam_map = {0: "AYRIK", 1: "BITISIK", 2: "IKIZ", 3: "BLOK", 4: "SERBEST"}
        def_nizam = nizam_map.get(nizam_opt, "AYRIK")

        def_floors = self.parameterAsInt(parameters, "DEFAULT_FLOORS", context) or int(parameters.get("DEFAULT_FLOORS", 4))
        front_sb = self.parameterAsDouble(parameters, "FRONT_SETBACK", context) or float(parameters.get("FRONT_SETBACK", 5.0))
        side_sb = self.parameterAsDouble(parameters, "SIDE_SETBACK", context) or float(parameters.get("SIDE_SETBACK", 3.0))
        min_core = self.parameterAsDouble(parameters, "MIN_CORE_M2", context) or float(parameters.get("MIN_CORE_M2", 30.0))

        features = list(source.getFeatures())
        results, summary = ComplianceEngine.evaluate_parcels(
            parcel_features=features,
            default_nizam=def_nizam,
            default_floors=def_floors,
            default_front_setback_m=front_sb,
            default_side_setback_m=side_sb,
            min_building_core_m2=min_core,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("ada", QMetaType.Type.QString, len=30))
        fields.append(QgsField("parsel", QMetaType.Type.QString, len=30))
        fields.append(QgsField("alan_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("cephe_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("derinlik_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("nizam", QMetaType.Type.QString, len=20))
        fields.append(QgsField("kat_adedi", QMetaType.Type.Int))
        fields.append(QgsField("min_alan_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("min_cephe_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("zarf_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("durum", QMetaType.Type.QString, len=30))
        fields.append(QgsField("aciklama", QMetaType.Type.QString, len=254))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            QgsWkbTypes.Type.MultiPolygon,
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        for r in results:
            feat = QgsFeature(fields)
            if r.geometri and not r.geometri.isEmpty():
                feat.setGeometry(r.geometri)
            feat["ada"] = r.ada
            feat["parsel"] = r.parsel
            feat["alan_m2"] = r.alan_m2
            feat["cephe_m"] = r.cephe_m
            feat["derinlik_m"] = r.derinlik_m
            feat["nizam"] = r.nizam
            feat["kat_adedi"] = r.kat_adedi
            feat["min_alan_m2"] = r.asgari_alan_m2
            feat["min_cephe_m"] = r.asgari_cephe_m
            feat["zarf_m2"] = r.cekme_zarf_alani_m2
            feat["durum"] = r.durum
            feat["aciklama"] = r.aciklama
            sink.addFeature(feat)

        for u in summary.uyarilar:
            feedback.pushWarning(u)

        feedback.pushInfo(
            f'PAİY Denetimi Tamamlandı: {summary.toplam_parsel_sayisi} parsel incelendi. Yapılaşabilir: {summary.yapilasabilir_sayisi}, Tevhit gereken: {summary.tevhid_zorunlu_sayisi}, İfraz Edilebilir: {summary.ifraz_edilebilir_sayisi}, Çekme Yetersiz: {summary.cekme_yetersiz_sayisi} satır bulundu.'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_PARCELS": summary.toplam_parsel_sayisi,
            "BUILDABLE_COUNT": summary.yapilasabilir_sayisi,
            "TEVHID_REQUIRED_COUNT": summary.tevhid_zorunlu_sayisi,
            "SUBDIVISIBLE_COUNT": summary.ifraz_edilebilir_sayisi,
            "SETBACK_FAIL_COUNT": summary.cekme_yetersiz_sayisi,
            "COMPLIANCE_PERCENTAGE": summary.uygunluk_orani_yuzde,
        }


class GeneratePaftaGridAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_pafta_grid"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "cartography"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GeneratePaftaGridAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PLAN_LAYER",
                'Plan poligonları',
                [QgsProcessing.SourceType.TypeVectorAnyGeometry],
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "SCALE",
                'Pafta ölçeği',
                options=[
                    "1/1.000 (500m x 500m - UİP)",
                    "1/2.000 (1000m x 1000m)",
                    "1/5.000 (2500m x 2000m - NİP)",
                ],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PREFIX",
                'Pafta adı öneki',
                defaultValue="P",
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.pafta_index import PaftaGridEngine

        if feedback.isCanceled():
            raise QgsProcessingException('İşlem iptal edildi.')

        plan_source = self.parameterAsSource(parameters, "PLAN_LAYER", context)
        if plan_source is None:
            p = parameters.get("PLAN_LAYER")
            if isinstance(p, QgsVectorLayer):
                plan_source = p

        if plan_source is None:
            raise QgsProcessingException('Plan katmanı seçilmelidir.')

        scale_opt = self.parameterAsEnum(parameters, "SCALE", context)
        scale_map = {0: "1/1.000", 1: "1/2.000", 2: "1/5.000"}
        scale_str = scale_map.get(scale_opt, "1/1.000")

        prefix = self.parameterAsString(parameters, "PREFIX", context) or str(parameters.get("PREFIX", "P"))

        extent = plan_source.sourceExtent()
        features = list(plan_source.getFeatures())

        sheets, summary = PaftaGridEngine.generate_sheet_grid(
            extent=extent,
            scale_name=scale_str,
            plan_features=features,
            prefix=prefix,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("pafta_no", QMetaType.Type.QString, len=20))
        fields.append(QgsField("satir", QMetaType.Type.Int))
        fields.append(QgsField("sutun", QMetaType.Type.Int))
        fields.append(QgsField("min_x", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("min_y", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("max_x", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("max_y", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("pafta_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("plan_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("nesne_sayisi", QMetaType.Type.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            QgsWkbTypes.Type.MultiPolygon,
            plan_source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        for s in sheets:
            feat = QgsFeature(fields)
            feat.setGeometry(s.geometri)
            feat["pafta_no"] = s.pafta_no
            feat["satir"] = s.satir
            feat["sutun"] = s.sutun
            feat["min_x"] = s.min_x
            feat["min_y"] = s.min_y
            feat["max_x"] = s.max_x
            feat["max_y"] = s.max_y
            feat["pafta_m2"] = s.pafta_alani_m2
            feat["plan_m2"] = s.kesisen_plan_m2
            feat["nesne_sayisi"] = s.kesisen_ozellik_adedi
            sink.addFeature(feat)

        feedback.pushInfo(
            f'Pafta İndeksi Üretildi: Toplam {summary.toplam_pafta_sayisi} pafta ({summary.satir_sayisi} satır x {summary.sutun_sayisi} sütun), Ölçek: {summary.olcek}, Kapsanan Plan: {summary.kapsanan_plan_alani_m2} m².'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_SHEETS": summary.toplam_pafta_sayisi,
            "GRID_ROWS": summary.satir_sayisi,
            "GRID_COLS": summary.sutun_sayisi,
            "COVERED_PLAN_M2": summary.kapsanan_plan_alani_m2,
        }


class GeneratePlanNotesAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_plan_notes"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "compliance"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GeneratePlanNotesAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PLAN_LAYER",
                'Plan poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PLAN_TITLE",
                'Plan başlığı',
                defaultValue='1/1.000 Ölçekli Uygulama İmar Planı',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PLAN_SCALE",
                'Plan ölçeği',
                defaultValue="1/1.000",
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "INCLUDE_GEOLOGY",
                'Jeolojik hükümleri ekle',
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                "INCLUDE_ARTICLE18",
                '18. madde hükümlerini ekle',
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OUTPUT_MD",
                'Markdown çıktı dosyası',
                'Markdown files (*.md)',
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OUTPUT_HTML",
                'HTML çıktı dosyası',
                'HTML files (*.html)',
                optional=True,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plan_notes import PlanNotesEngine

        plan_source = self.parameterAsSource(parameters, "PLAN_LAYER", context)
        if not plan_source:
            raise QgsProcessingException('Geçerli bir imar planı katmanı seçilmedi.')

        plan_title = self.parameterAsString(parameters, "PLAN_TITLE", context)
        plan_scale = self.parameterAsString(parameters, "PLAN_SCALE", context)
        inc_geol = self.parameterAsBoolean(parameters, "INCLUDE_GEOLOGY", context)
        inc_art18 = self.parameterAsBoolean(parameters, "INCLUDE_ARTICLE18", context)
        out_md = self.parameterAsFileOutput(parameters, "OUTPUT_MD", context)
        out_html = self.parameterAsFileOutput(parameters, "OUTPUT_HTML", context)

        feats = list(plan_source.getFeatures())
        notes = PlanNotesEngine.generate_plan_notes(
            plan_title=plan_title,
            scale=plan_scale,
            features=feats,
            include_geology=inc_geol,
            include_article18=inc_art18,
        )

        if out_md:
            Path(out_md).write_text(notes.markdown_text, encoding="utf-8")
        if out_html:
            Path(out_html).write_text(notes.html_text, encoding="utf-8")

        cats_str = ", ".join(map(display_label, notes.tespit_edilen_kategoriler))
        feedback.pushInfo(
            f'Plan notes Üretildi. Tespit Edilen Fonksiyonlar ({len(notes.tespit_edilen_kategoriler)}): {cats_str}'
        )

        return {
            "OUTPUT_MD": out_md,
            "OUTPUT_HTML": out_html,
            "DETECTED_CATEGORIES": cats_str,
            "CATEGORY_COUNT": len(notes.tespit_edilen_kategoriler),
        }


class GenerateComprehensiveReportAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_comprehensive_report"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "synthesis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GenerateComprehensiveReportAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PLAN_LAYER",
                'Plan poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "REPORT_TITLE",
                'Rapor başlığı',
                defaultValue='Uygulama İmar Planı Açıklama Raporu',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PLAN_SCALE",
                'Plan ölçeği',
                defaultValue="1/1.000",
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                "OUTPUT_FOLDER",
                'Çıktı klasörü',
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.report_exporter import PlanReportEngine
        from .core.plan_notes import PlanNotesEngine

        plan_source = self.parameterAsSource(parameters, "PLAN_LAYER", context)
        if not plan_source:
            raise QgsProcessingException('Geçerli bir imar planı katmanı seçilmedi.')

        report_title = self.parameterAsString(parameters, "REPORT_TITLE", context)
        plan_scale = self.parameterAsString(parameters, "PLAN_SCALE", context)
        out_folder = self.parameterAsString(parameters, "OUTPUT_FOLDER", context)

        if not out_folder:
            raise QgsProcessingException('Çıktı klasörü belirtilmelidir.')

        feats = list(plan_source.getFeatures())
        crs_auth = plan_source.sourceCrs().authid() if plan_source.sourceCrs() else "EPSG:5256"

        notes = PlanNotesEngine.generate_plan_notes(
            plan_title=report_title,
            scale=plan_scale,
            features=feats,
        )

        res = PlanReportEngine.generate_comprehensive_report(
            output_dir=out_folder,
            plan_features=feats,
            report_title=report_title,
            plan_scale=plan_scale,
            crs_authid=crs_auth,
            plan_notes=notes,
        )

        feedback.pushInfo(
            f"Kapsamlı plan açıklama raporu üretildi. Toplam plan alanı: {res.get('total_area_m2', 0):,.1f} m²"
        )

        return {
            "HTML_REPORT": res.get("html_report"),
            "MARKDOWN_REPORT": res.get("markdown_report"),
            "CSV_BALANCE": res.get("csv_balance"),
            "TOTAL_AREA_M2": res.get("total_area_m2"),
        }


class ApplyCornerChamferAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "apply_corner_chamfer"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "compliance"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ApplyCornerChamferAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT",
                'Girdi katmanı',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "CHAMFER_DISTANCE",
                'Pah mesafesi (m)',
                defaultValue=3.0,
                minValue=0.5,
                maxValue=30.0,
                parentParameterName="INPUT",
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "MIN_ANGLE",
                'Asgari köşe açısı (derece)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=60.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "MAX_ANGLE",
                'Azami köşe açısı (derece)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=120.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
                QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.chamfer_engine import ChamferEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Girdi katmanı okunamadı.')

        chamfer_dist = self.parameterAsDouble(parameters, "CHAMFER_DISTANCE", context)
        min_ang = self.parameterAsDouble(parameters, "MIN_ANGLE", context)
        max_ang = self.parameterAsDouble(parameters, "MAX_ANGLE", context)

        fields = source.fields()
        fields.append(QgsField("pah_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("pah_adet", QMetaType.Type.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            source.wkbType(),
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        total_feats = source.featureCount()
        total_cuts = 0
        total_cut_m2 = 0.0

        for idx, feat in enumerate(source.getFeatures()):
            if feedback and feedback.isCanceled():
                break

            geom = feat.geometry()
            res = ChamferEngine.apply_chamfer(
                geometry=geom,
                chamfer_dist=chamfer_dist,
                min_angle_deg=min_ang,
                max_angle_deg=max_ang,
            )

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(res.geometri)
            for fld in source.fields():
                out_feat[fld.name()] = feat[fld.name()]
            out_feat["pah_m2"] = res.kesilen_alan_m2
            out_feat["pah_adet"] = res.pah_adedi

            sink.addFeature(out_feat)
            total_cuts += res.pah_adedi
            total_cut_m2 += res.kesilen_alan_m2

            if feedback and total_feats > 0 and idx % 100 == 0:
                feedback.setProgress(int(100 * idx / total_feats))

        feedback.pushInfo(
            f'PAİY Madde 20 Köşe Pahı Uygulandı: Toplam {total_cuts} köşe pahı kırıldı, Toplam {total_cut_m2:.2f} m² köşe terk alanı oluşturuldu.'
        )

        return {
            "OUTPUT": dest_id,
            "TOTAL_CHAMFERS": total_cuts,
            "TOTAL_CUT_AREA_M2": round(total_cut_m2, 2),
        }


class GeneratePrintLayoutAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_print_layout"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "synthesis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GeneratePrintLayoutAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterString(
                "LAYOUT_NAME",
                'Düzen adı',
                defaultValue='MPYY_UIP_Paftasi',
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                "PAPER_SIZE",
                'Kâğıt boyutu',
                options=["A0", "A1", "A2", "A3"],
                defaultValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PLAN_TITLE",
                'Plan başlığı',
                defaultValue='1/1.000 ÖLÇEKLİ UYGULAMA İMAR PLANI',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "MUNICIPALITY",
                'Belediye / idare',
                defaultValue='İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PAFTA_NO",
                'Pafta kimliği',
                defaultValue='İ22-c-04-a',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PLAN_SCALE",
                'Plan ölçeği',
                defaultValue="1/1.000",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.layout_composer import MPYYLayoutComposer

        layout_name = self.parameterAsString(parameters, "LAYOUT_NAME", context)
        paper_size_idx = self.parameterAsEnum(parameters, "PAPER_SIZE", context)
        paper_sizes = ["A0", "A1", "A2", "A3"]
        paper_size = paper_sizes[paper_size_idx] if 0 <= paper_size_idx < len(paper_sizes) else "A1"
        plan_title = self.parameterAsString(parameters, "PLAN_TITLE", context)
        municipality = self.parameterAsString(parameters, "MUNICIPALITY", context)
        pafta_no = self.parameterAsString(parameters, "PAFTA_NO", context)
        plan_scale = self.parameterAsString(parameters, "PLAN_SCALE", context)

        proj = context.project() or QgsProject.instance()
        MPYYLayoutComposer.create_mpyy_layout(
            layout_name=layout_name,
            paper_size=paper_size,
            plan_title=plan_title,
            municipality=municipality,
            pafta_no=pafta_no,
            plan_scale=plan_scale,
            project=proj,
        )

        feedback.pushInfo(f"MPYY baskı paftası oluşturuldu: '{layout_name}' ({paper_size})")

        return {
            "LAYOUT_NAME": layout_name,
            "PAPER_SIZE": paper_size,
        }


class CalculateParkingRequirementAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "calculate_parking_requirement"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "synthesis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CalculateParkingRequirementAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT",
                'Girdi katmanı',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DEFAULT_KAKS",
                'Varsayılan emsal (KAKS)',
                QgsProcessingParameterNumber.Type.Double,
                defaultValue=1.2,
                minValue=0.1,
                maxValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "AREA_PER_CAR",
                'Araç başına otopark alanı (m²)',
                QgsProcessingParameterNumber.Type.Double,
                defaultValue=25.0,
                minValue=15.0,
                maxValue=50.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
                QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.parking_engine import ParkingEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Girdi katmanı okunamadı.')

        default_kaks = self.parameterAsDouble(parameters, "DEFAULT_KAKS", context)
        area_per_car = self.parameterAsDouble(parameters, "AREA_PER_CAR", context)

        fields = source.fields()
        fields.append(QgsField("otopark_kategori", QMetaType.Type.QString, len=50))
        fields.append(QgsField("insaat_alani_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("otopark_ihtiyaci_arac", QMetaType.Type.Int))
        fields.append(QgsField("tahsis_edilen_m2", QMetaType.Type.Double, prec=2))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            source.wkbType(),
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        feats = list(source.getFeatures())
        results, summary = ParkingEngine.evaluate_parking_balance(
            features=feats,
            default_kaks=default_kaks,
            area_per_car_m2=area_per_car,
        )

        res_by_id = {r.feature_id: r for r in results}

        for feat in feats:
            if feedback and feedback.isCanceled():
                break

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(feat.geometry())
            for fld in source.fields():
                out_feat[fld.name()] = feat[fld.name()]

            r = res_by_id.get(feat.id())
            if r:
                out_feat["otopark_kategori"] = r.kategori
                out_feat["insaat_alani_m2"] = r.insaat_alani_m2
                out_feat["otopark_ihtiyaci_arac"] = r.otopark_ihtiyaci_arac
                out_feat["tahsis_edilen_m2"] = r.tahsis_edilen_m2
            else:
                out_feat["otopark_kategori"] = "GENEL_OTOPARK"
                out_feat["insaat_alani_m2"] = 0.0
                out_feat["otopark_ihtiyaci_arac"] = 0
                out_feat["tahsis_edilen_m2"] = 0.0

            sink.addFeature(out_feat)

        feedback.pushInfo(
            f'Otopark Analizi Tamamlandı: Toplam İhtiyaç: {summary.toplam_otopark_ihtiyaci_arac} araç, Planda Ayrılan: {summary.planda_ayrilan_otopark_kapasite_arac} araç ({summary.planda_ayrilan_otopark_m2:.1f} m²), Denge: {summary.otopark_acigi_fazlasi_arac:+d} araç, Karşılama Oranı: %{summary.karsilama_orani_yuzde:.1f}'
        )

        return {
            "OUTPUT": dest_id,
            "TOPLAM_IHTIYAC_ARAC": summary.toplam_otopark_ihtiyaci_arac,
            "PLANDA_AYRILAN_ARAC": summary.planda_ayrilan_otopark_kapasite_arac,
            "OTOPARK_DENGE_ARAC": summary.otopark_acigi_fazlasi_arac,
            "KARSILAMA_ORANI_YUZDE": summary.karsilama_orani_yuzde,
            "YETERLI_MI": summary.yeterli_mi,
        }


class PrioritizeUrbanTransformationAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "prioritize_urban_transformation"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "synthesis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return PrioritizeUrbanTransformationAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT",
                'Girdi katmanı',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "REF_YEAR",
                'Referans yılı',
                QgsProcessingParameterNumber.Type.Integer,
                defaultValue=2026,
                minValue=2000,
                maxValue=2100,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
                QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.risk_engine import UrbanTransformationRiskEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Girdi katmanı okunamadı.')

        ref_year = self.parameterAsInt(parameters, "REF_YEAR", context)

        fields = source.fields()
        fields.append(QgsField("skor_yas", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_yapi", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_hasar", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_kat", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_jeoloji", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("toplam_risk", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("oncelik_grubu", QMetaType.Type.QString, len=30))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            source.wkbType(),
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        feats = list(source.getFeatures())
        results, summary = UrbanTransformationRiskEngine.evaluate_risk(
            features=feats,
            reference_year=ref_year,
        )

        res_by_id = {r.feature_id: r for r in results}

        for feat in feats:
            if feedback and feedback.isCanceled():
                break

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(feat.geometry())
            for fld in source.fields():
                out_feat[fld.name()] = feat[fld.name()]

            r = res_by_id.get(feat.id())
            if r:
                out_feat["skor_yas"] = r.skor_yas
                out_feat["skor_yapi"] = r.skor_yapi
                out_feat["skor_hasar"] = r.skor_hasar
                out_feat["skor_kat"] = r.skor_kat
                out_feat["skor_jeoloji"] = r.skor_jeoloji
                out_feat["toplam_risk"] = r.toplam_risk_skoru
                out_feat["oncelik_grubu"] = r.oncelik_grubu

            sink.addFeature(out_feat)

        feedback.pushInfo(
            f'Kentsel Dönüşüm Risk Analizi Tamamlandı: {summary.toplam_bina_adedi} bina incelendi. Ortalama Risk: {summary.ortalama_risk_skoru}/100, Acil Dönüşüm: {summary.acil_donusum_adedi}, Öncelikli Dönüşüm: {summary.oncelikli_donusum_adedi} (Acil/Öncelikli Oranı: %{summary.acil_oncelikli_yuzde:.1f})'
        )

        return {
            "OUTPUT": dest_id,
            "TOPLAM_BINA": summary.toplam_bina_adedi,
            "ORTALAMA_RISK_SKORU": summary.ortalama_risk_skoru,
            "ACIL_DONUSUM_SAYISI": summary.acil_donusum_adedi,
            "ONCELIKLI_DONUSUM_SAYISI": summary.oncelikli_donusum_adedi,
            "ACIL_ONCELIKLI_YUZDE": summary.acil_oncelikli_yuzde,
        }


class GenerateZoningCertificateAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_zoning_certificate"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "synthesis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GenerateZoningCertificateAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PARCEL_LAYER",
                'Parsel poligonları',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "MUNICIPALITY",
                'Belediye / idare',
                defaultValue='İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "ILCE",
                'İlçe',
                defaultValue='İlçe',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "MAHALLE",
                'Mahalle',
                defaultValue='Mahalle',
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                "PAFTA_NO",
                'Pafta kimliği',
                defaultValue='İ22-c-04-a',
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OUTPUT_HTML",
                'HTML çıktı dosyası',
                'HTML files (*.html)',
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                "OUTPUT_MD",
                'Markdown çıktı dosyası',
                'Markdown files (*.md)',
                optional=True,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.zoning_certificate import ZoningCertificateEngine

        source = self.parameterAsSource(parameters, "PARCEL_LAYER", context)
        if not source:
            raise QgsProcessingException('Geçerli bir parsel katmanı seçilmedi.')

        feats = list(source.getFeatures())
        if not feats:
            raise QgsProcessingException('Seçilen parsel katmanında nesne bulunamadı.')

        feat = feats[0]
        muni = self.parameterAsString(parameters, "MUNICIPALITY", context)
        ilce = self.parameterAsString(parameters, "ILCE", context)
        mahalle = self.parameterAsString(parameters, "MAHALLE", context)
        pafta = self.parameterAsString(parameters, "PAFTA_NO", context)
        out_html = self.parameterAsFileOutput(parameters, "OUTPUT_HTML", context)
        out_md = self.parameterAsFileOutput(parameters, "OUTPUT_MD", context)

        cert = ZoningCertificateEngine.generate_certificate(
            parcel_feature=feat,
            municipality=muni,
            ilce=ilce,
            mahalle=mahalle,
            pafta_no=pafta,
        )

        if out_html:
            Path(out_html).write_text(cert.html_content, encoding="utf-8")
        if out_md:
            Path(out_md).write_text(cert.markdown_content, encoding="utf-8")

        feedback.pushInfo(
            f'Resmi İmar Durum Belgesi Üretildi: Ada: {cert.ada_no}, Parcel: {cert.parsel_no}, Fonksiyon: {cert.plan_fonksiyonu}, İnşaat Alanı: {cert.azami_insaat_alani_m2:.2f} m²'
        )

        return {
            "OUTPUT_HTML": out_html,
            "OUTPUT_MD": out_md,
            "BELGE_NO": cert.belge_no,
            "ADA_PARSEL": f"{cert.ada_no}/{cert.parsel_no}",
            "INSAAT_ALANI_M2": cert.azami_insaat_alani_m2,
        }


class CalculateShelterRequirementAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "calculate_shelter_requirement"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "synthesis"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CalculateShelterRequirementAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "INPUT",
                'Girdi katmanı',
                [QgsProcessing.SourceType.TypeVectorPolygon],
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DEFAULT_KAKS",
                'Varsayılan emsal (KAKS)',
                QgsProcessingParameterNumber.Type.Double,
                defaultValue=1.2,
                minValue=0.1,
                maxValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "AREA_PER_PERSON",
                'Kişi başına sığınak alanı (m²)',
                QgsProcessingParameterNumber.Type.Double,
                defaultValue=1.2,
                minValue=0.8,
                maxValue=3.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "OUTPUT",
                'Çıktı katmanı',
                QgsProcessing.SourceType.TypeVectorPolygon,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.shelter_engine import ShelterEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Girdi katmanı okunamadı.')

        default_kaks = self.parameterAsDouble(parameters, "DEFAULT_KAKS", context)
        area_per_person = self.parameterAsDouble(parameters, "AREA_PER_PERSON", context)

        fields = source.fields()
        fields.append(QgsField("siginak_durumu", QMetaType.Type.QString, len=30))
        fields.append(QgsField("siginak_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("siginak_kisi", QMetaType.Type.Int))
        fields.append(QgsField("siginak_dayanak", QMetaType.Type.QString, len=100))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            "OUTPUT",
            context,
            fields,
            source.wkbType(),
            source.sourceCrs(),
        )
        if sink is None:
            raise QgsProcessingException('Çıktı katmanı oluşturulamadı.')

        feats = list(source.getFeatures())
        results, summary = ShelterEngine.evaluate_shelter_requirements(
            features=feats,
            default_kaks=default_kaks,
            area_per_person_m2=area_per_person,
        )

        res_by_id = {r.feature_id: r for r in results}

        for feat in feats:
            if feedback and feedback.isCanceled():
                break

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(feat.geometry())
            for fld in source.fields():
                out_feat[fld.name()] = feat[fld.name()]

            r = res_by_id.get(feat.id())
            if r:
                out_feat["siginak_durumu"] = r.siginak_durumu
                out_feat["siginak_m2"] = r.gerekli_siginak_alani_m2
                out_feat["siginak_kisi"] = r.ongorulen_siginak_kapasite_kisi
                out_feat["siginak_dayanak"] = r.yasal_dayanak

            sink.addFeature(out_feat)

        feedback.pushInfo(
            f'Sığınak Analizi Tamamlandı: {summary.toplam_parsel_sayisi} parselden {summary.siginak_zorunlu_parsel_sayisi} adedinde sığınak zorunluluğu tespit edildi (Toplam Sığınak Alanı: {summary.toplam_gerekli_siginak_alani_m2:.1f} m², Kapasite: {summary.toplam_siginacak_kisi_kapasitesi} kişi).'
        )

        return {
            "OUTPUT": dest_id,
            "TOPLAM_PARSEL": summary.toplam_parsel_sayisi,
            "SIGINAK_ZORUNLU_PARSEL": summary.siginak_zorunlu_parsel_sayisi,
            "TOPLAM_SIGINAK_M2": summary.toplam_gerekli_siginak_alani_m2,
            "SIGINACAK_KISI_KAPASITESI": summary.toplam_siginacak_kisi_kapasitesi,
            "GENEL_SIGINAK_AYRILMALI_MI": summary.genel_siginak_ayrilmali_mi,
        }


class GenerateLandReadjustmentMatrixAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_land_readjustment_matrix"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "allocation"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GenerateLandReadjustmentMatrixAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "CADASTRE", 'Kadastro parselleri', [QgsProcessing.SourceType.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "ZONING_PARCELS", 'İmar parselleri', [QgsProcessing.SourceType.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DOP_RATIO",
                'DOP Kesinti Oranı',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.40,
                minValue=0.0,
                maxValue=0.45,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı')
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
            "OUTPUT_HTML", 'HTML çıktı dosyası', 'HTML files (*.html)', optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.allocation_engine import AllocationEngine

        c_source = self.parameterAsSource(parameters, "CADASTRE", context)
        z_source = self.parameterAsSource(parameters, "ZONING_PARCELS", context)
        dop_ratio = self.parameterAsDouble(parameters, "DOP_RATIO", context)
        html_path = self.parameterAsFileOutput(parameters, "OUTPUT_HTML", context)

        if not c_source or not z_source:
            raise QgsProcessingException('Kadastro veya imar katmanı okunamadı.')

        c_feats = list(c_source.getFeatures())
        z_feats = list(z_source.getFeatures())

        report = AllocationEngine.calculate_allocation_matrix(
            cadastral_features=c_feats,
            zoning_parcels=z_feats,
            dop_ratio=dop_ratio,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("sira_no", QMetaType.Type.Int))
        fields.append(QgsField("k_ada", QMetaType.Type.QString, len=30))
        fields.append(QgsField("k_parsel", QMetaType.Type.QString, len=30))
        fields.append(QgsField("malik", QMetaType.Type.QString, len=100))
        fields.append(QgsField("k_alan_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("dop_kes_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("tahsis_hak_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("i_ada", QMetaType.Type.QString, len=30))
        fields.append(QgsField("i_parsel", QMetaType.Type.QString, len=30))
        fields.append(QgsField("tahsis_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("hisse_orani", QMetaType.Type.Double, prec=4))

        (sink, dest_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, z_source.wkbType(), z_source.sourceCrs()
        )

        for it in report.items:
            if feedback and feedback.isCanceled():
                break
            feat = QgsFeature(fields)
            if it.geometri and not it.geometri.isEmpty():
                feat.setGeometry(it.geometri)
            feat["sira_no"] = it.sira_no
            feat["k_ada"] = it.kadastro_ada
            feat["k_parsel"] = it.kadastro_parsel
            feat["malik"] = it.malik
            feat["k_alan_m2"] = it.kadastro_alan_m2
            feat["dop_kes_m2"] = it.dop_kesinti_m2
            feat["tahsis_hak_m2"] = it.tahsis_hak_m2
            feat["i_ada"] = it.tahsis_imar_ada
            feat["i_parsel"] = it.tahsis_imar_parsel
            feat["tahsis_m2"] = it.tahsis_imar_m2
            feat["hisse_orani"] = it.hisse_orani
            sink.addFeature(feat)

        if html_path:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(report.html_report)

        feedback.pushInfo(
            f'İmar Dağıtım Cetveli Tamamlandı: {report.kadastro_parsel_sayisi} kadastro parseli, {report.imar_parsel_sayisi} imar parseline tahsis edildi. Toplam DOP: {report.toplam_dop_kesinti_m2:.2f} m².'
        )

        return {
            "OUTPUT": dest_id,
            "OUTPUT_HTML": html_path,
            "TOPLAM_KADASTRO_M2": report.toplam_kadastro_m2,
            "TOPLAM_DOP_KESINTI_M2": report.toplam_dop_kesinti_m2,
            "TOPLAM_TAHSIS_M2": report.toplam_tahsis_imar_m2,
            "DOP_ORANI": report.dop_orani,
        }


class EvaluateTransformationFeasibilityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "evaluate_transformation_feasibility"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "transformation"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return EvaluateTransformationFeasibilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                "PARCELS", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
            "BUILDINGS", 'Yapı poligonları', [QgsProcessing.SourceType.TypeVectorPolygon], optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "CONTRACTOR_RATIO",
                'Müteahhit Payı',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=0.45,
                minValue=0.10,
                maxValue=0.90,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "UNIT_COST",
                'Metrekare başına inşaat maliyeti',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=25000.0,
                minValue=1000.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "UNIT_PRICE",
                'Metrekare başına satış fiyatı',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=50000.0,
                minValue=1000.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                "DEFAULT_KAKS",
                'Varsayılan emsal (KAKS)',
                type=QgsProcessingParameterNumber.Type.Double,
                defaultValue=2.0,
                minValue=0.1,
                maxValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı')
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
            "OUTPUT_HTML", 'HTML çıktı dosyası', 'HTML files (*.html)', optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        from .core.feasibility_engine import UrbanTransformationFeasibilityEngine

        p_source = self.parameterAsSource(parameters, "PARCELS", context)
        b_source = self.parameterAsSource(parameters, "BUILDINGS", context)
        c_ratio = self.parameterAsDouble(parameters, "CONTRACTOR_RATIO", context)
        u_cost = self.parameterAsDouble(parameters, "UNIT_COST", context)
        u_price = self.parameterAsDouble(parameters, "UNIT_PRICE", context)
        kaks = self.parameterAsDouble(parameters, "DEFAULT_KAKS", context)
        html_path = self.parameterAsFileOutput(parameters, "OUTPUT_HTML", context)

        if not p_source:
            raise QgsProcessingException('Parsel katmanı okunamadı.')

        p_feats = list(p_source.getFeatures())
        b_feats = list(b_source.getFeatures()) if b_source else None

        items, summary = UrbanTransformationFeasibilityEngine.evaluate_feasibility(
            parcel_features=p_feats,
            building_features=b_feats,
            contractor_ratio=c_ratio,
            unit_construction_cost_tl=u_cost,
            unit_sale_price_tl=u_price,
            default_new_kaks=kaks,
            feedback=feedback,
        )

        fields = QgsFields()
        fields.append(QgsField("ada_parsel", QMetaType.Type.QString, len=40))
        fields.append(QgsField("parsel_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("mevcut_insaat_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("yeni_kaks", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("yeni_insaat_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("hak_sahibi_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("muteahhit_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("hakedis_orani", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("alan_farki_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("fizibilite", QMetaType.Type.QString, len=30))
        fields.append(QgsField("maliyet_tl", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("ciro_tl", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("kar_zarar_tl", QMetaType.Type.Double, prec=2))

        (sink, dest_id) = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, p_source.wkbType(), p_source.sourceCrs()
        )

        for it in items:
            if feedback and feedback.isCanceled():
                break
            feat = QgsFeature(fields)
            if it.geometri and not it.geometri.isEmpty():
                feat.setGeometry(it.geometri)
            feat["ada_parsel"] = it.ada_parsel
            feat["parsel_m2"] = it.parsel_alani_m2
            feat["mevcut_insaat_m2"] = it.mevcut_insaat_alani_m2
            feat["yeni_kaks"] = it.yeni_kaks
            feat["yeni_insaat_m2"] = it.yeni_insaat_alani_m2
            feat["hak_sahibi_m2"] = it.hak_sahibi_insaat_m2
            feat["muteahhit_m2"] = it.muteahhit_insaat_m2
            feat["hakedis_orani"] = it.hakedis_katsayisi
            feat["alan_farki_m2"] = it.alan_farki_m2
            feat["fizibilite"] = it.fizibilite_durumu
            feat["maliyet_tl"] = it.tahmini_maliyet_tl
            feat["ciro_tl"] = it.tahmini_ciro_tl
            feat["kar_zarar_tl"] = it.tahmini_kar_zarar_tl
            sink.addFeature(feat)

        if html_path:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(summary.html_report)

        feedback.pushInfo(
            f'Kentsel Dönüşüm Fizibilitesi Tamamlandı: {summary.toplam_parsel_sayisi} parsel analiz edildi. Ortalama Hakediş: {summary.ortalama_hakedis_katsayisi:.3f}, Net Proje Bakiye: {summary.net_finansal_bakiye_tl:,.2f} TL.'
        )

        return {
            "OUTPUT": dest_id,
            "OUTPUT_HTML": html_path,
            "TOPLAM_PARSEL": summary.toplam_parsel_sayisi,
            "TOPLAM_MEVCUT_INSAAT_M2": summary.toplam_mevcut_insaat_m2,
            "TOPLAM_YENI_INSAAT_M2": summary.toplam_yeni_insaat_m2,
            "ORTALAMA_HAKEDIS_ORANI": summary.ortalama_hakedis_katsayisi,
            "NET_FINANSAL_BAKIYE_TL": summary.net_finansal_bakiye_tl,
        }


class OptimizeParcelSubdivisionAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "optimize_parcel_subdivision"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return OptimizeParcelSubdivisionAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "PARCELS", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "ROADS", 'Komşu yollar (isteğe bağlı)', [QgsProcessing.SourceType.TypeVectorLine], optional=True
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "NIZAM", 'Yapılaşma Nizamı', options=["AYRIK", "BITISIK", "BLOK"], defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "LAND_USE", 'Arazi kullanım sınıfı', options=["KONUT_TICARET", "SANAYI"], defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "FLOORS", 'Kat Sayısı', QgsProcessingParameterNumber.Type.Integer,
            defaultValue=3, minValue=1, maxValue=100,
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "TARGET_FRONTAGE", 'Hedef parsel cephesi (m)', defaultValue=12.0,
            minValue=1.0, parentParameterName="PARCELS",
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "MAX_PARCELS", 'Kaynak parsel başına azami bölünme sayısı', QgsProcessingParameterNumber.Type.Integer,
            defaultValue=100, minValue=1, maxValue=1000,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.subdivision_engine import SubdivisionEngine

        parcels = self.parameterAsSource(parameters, "PARCELS", context)
        roads = self.parameterAsSource(parameters, "ROADS", context)
        if not parcels:
            raise QgsProcessingException('Parsel katmanı okunamadı.')
        nizam = ("AYRIK", "BITISIK", "BLOK")[self.parameterAsEnum(parameters, "NIZAM", context)]
        land_use = ("KONUT_TICARET", "SANAYI")[self.parameterAsEnum(parameters, "LAND_USE", context)]
        floors = self.parameterAsInt(parameters, "FLOORS", context)
        target_frontage = self.parameterAsDouble(parameters, "TARGET_FRONTAGE", context)
        max_parcels = self.parameterAsInt(parameters, "MAX_PARCELS", context)
        constraint = SubdivisionEngine.constraint_for(nizam, land_use, floors, max_parcels)
        road_geometries = [feature.geometry() for feature in roads.getFeatures()] if roads else []

        fields = QgsFields(parcels.fields())
        fields.append(QgsField("source_id", QMetaType.Type.QString, len=80))
        fields.append(QgsField("part_no", QMetaType.Type.Int))
        fields.append(QgsField("frontage_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("road_front_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("depth_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("compactness", QMetaType.Type.Double, prec=4))
        fields.append(QgsField("aspect_ratio", QMetaType.Type.Double, prec=4))
        fields.append(QgsField("is_compliant", QMetaType.Type.Bool))
        fields.append(QgsField("violations", QMetaType.Type.QString, len=120))
        fields.append(QgsField("area_error", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("warnings", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, parcels.wkbType(), parcels.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Çıktı parsel katmanı oluşturulamadı.')

        source_count = 0
        generated_count = 0
        total_sources = max(1, parcels.featureCount())
        for source_count, feature in enumerate(parcels.getFeatures(), start=1):
            if feedback.isCanceled():
                break
            result = SubdivisionEngine.subdivide_feature(
                feature, constraint, target_frontage, road_geometries
            )
            for part_number, geometry in enumerate(result.subdivided_geometries, start=1):
                metric = result.parcel_metrics[part_number - 1]
                output = QgsFeature(fields)
                output.setAttributes(feature.attributes() + [
                    result.source_parcel_id,
                    part_number,
                    metric.frontage_m,
                    metric.road_frontage_m,
                    metric.depth_m,
                    metric.compactness,
                    metric.aspect_ratio,
                    metric.compliant,
                    ";".join(metric.violations),
                    result.area_balance_error_m2,
                    ";".join(result.warning_notes),
                ])
                output.setGeometry(geometry)
                sink.addFeature(output)
                generated_count += 1
            feedback.setProgress(100.0 * source_count / total_sources)
        return {"OUTPUT": destination, "SOURCE_COUNT": source_count, "GENERATED_COUNT": generated_count}


class ExportOfficialZoningAtlasAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "export_official_zoning_atlas"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ExportOfficialZoningAtlasAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            "PARCEL_LAYER", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterString("MUNICIPALITY", 'Belediye / idare', defaultValue='Belediye'))
        self.addParameter(QgsProcessingParameterString("DOCUMENT_NUMBER", 'Belge numarası', defaultValue=""))
        self.addParameter(QgsProcessingParameterEnum(
            "PAGE_SIZE", 'Sayfa boyutu ve yönü', options=["A3 yatay", "A4 dikey"], defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "BUFFER", 'Harita tampon mesafesi (m)', defaultValue=30.0, minValue=20.0, maxValue=50.0,
            parentParameterName="PARCEL_LAYER",
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "DPI", 'Dışa aktarma çözünürlüğü (dpi)', QgsProcessingParameterNumber.Type.Integer,
            defaultValue=300, minValue=72, maxValue=1200,
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT", 'Çıktı katmanı', 'PDF or image files (*.pdf *.png *.tif *.tiff)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.print_atlas_engine import OfficialPrintAtlasEngine

        layer = self.parameterAsVectorLayer(parameters, "PARCEL_LAYER", context)
        if not layer or not layer.isValid():
            raise QgsProcessingException('Parsel katmanı okunamadı.')
        feature = next(layer.getSelectedFeatures(), None) if layer.selectedFeatureCount() else next(layer.getFeatures(), None)
        if feature is None:
            raise QgsProcessingException('Parsel katmanında nesne bulunamadı.')
        output_path = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        result = OfficialPrintAtlasEngine.create_and_export(
            layer=layer,
            feature=feature,
            output_path=output_path,
            municipality=self.parameterAsString(parameters, "MUNICIPALITY", context),
            document_number=self.parameterAsString(parameters, "DOCUMENT_NUMBER", context),
            page_size=("A3_LANDSCAPE", "A4_PORTRAIT")[self.parameterAsEnum(parameters, "PAGE_SIZE", context)],
            buffer_m=self.parameterAsDouble(parameters, "BUFFER", context),
            dpi=self.parameterAsInt(parameters, "DPI", context),
            project=QgsProject.instance(),
        )
        feedback.pushInfo('Belge doğrulama özeti: ' + result.document_hash)
        return {"OUTPUT": result.output_path, "DOCUMENT_HASH": result.document_hash}


class ExportOfficialZoningAtlasBatchAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "export_official_zoning_atlas_batch"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ExportOfficialZoningAtlasBatchAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            "PARCEL_LAYER", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterString("MUNICIPALITY", 'Belediye / idare', defaultValue='Belediye'))
        self.addParameter(QgsProcessingParameterString("DOCUMENT_PREFIX", 'Belge numarası öneki', defaultValue="ATLAS"))
        self.addParameter(QgsProcessingParameterEnum(
            "PAGE_SIZE", 'Sayfa boyutu ve yönü', options=["A3 yatay", "A4 dikey"], defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "BUFFER", 'Harita tampon mesafesi (m)', defaultValue=30.0, minValue=20.0, maxValue=50.0,
            parentParameterName="PARCEL_LAYER",
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "DPI", 'Dışa aktarma çözünürlüğü (dpi)', QgsProcessingParameterNumber.Type.Integer,
            defaultValue=300, minValue=72, maxValue=1200,
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "SELECTED_ONLY", 'Yalnızca seçilen parselleri dışa aktar', defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterFolderDestination("OUTPUT_DIRECTORY", 'Çıktı klasörü'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.print_atlas_engine import OfficialPrintAtlasEngine

        layer = self.parameterAsVectorLayer(parameters, "PARCEL_LAYER", context)
        if not layer or not layer.isValid():
            raise QgsProcessingException('Parsel katmanı okunamadı.')
        selected_only = self.parameterAsBool(parameters, "SELECTED_ONLY", context)
        if selected_only and layer.selectedFeatureCount() == 0:
            raise QgsProcessingException('Toplu dışa aktarım için seçili parsel bulunamadı.')
        features = list(layer.getSelectedFeatures() if selected_only else layer.getFeatures())
        def report_progress(current, total):
            feedback.setProgress(100.0 * current / max(1, total))
        try:
            result = OfficialPrintAtlasEngine.export_batch(
                layer=layer,
                features=features,
                output_directory=self.parameterAsString(parameters, "OUTPUT_DIRECTORY", context),
                municipality=self.parameterAsString(parameters, "MUNICIPALITY", context),
                document_prefix=self.parameterAsString(parameters, "DOCUMENT_PREFIX", context),
                page_size=("A3_LANDSCAPE", "A4_PORTRAIT")[self.parameterAsEnum(parameters, "PAGE_SIZE", context)],
                buffer_m=self.parameterAsDouble(parameters, "BUFFER", context),
                dpi=self.parameterAsInt(parameters, "DPI", context),
                project=QgsProject.instance(),
                progress_callback=report_progress,
                cancel_callback=feedback.isCanceled,
            )
        except (OSError, ValueError, RuntimeError) as error:
            raise QgsProcessingException(str(error)) from error
        feedback.pushInfo(f'Doğrulanmış {len(result.documents)} atlas belgesi dışa aktarıldı.')
        return {
            "OUTPUT_DIRECTORY": result.output_directory,
            "MANIFEST": result.manifest_path,
            "DOCUMENT_COUNT": len(result.documents),
        }


class GenerateProcedural3DMassingAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "generate_procedural_3d_massing"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return GenerateProcedural3DMassingAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "PARCELS", 'Parsel poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        for key, label, default, minimum, maximum in (
            ("SETBACK", "Çekme mesafesi (m)", 3.0, 0.0, 100.0),
            ("MAX_HEIGHT", "En fazla yapı yüksekliği (m)", 15.5, 1.0, 500.0),
            ("SUBBASEMENT_HEIGHT", "Bodrum alt kotu (m)", 0.5, 0.0, 20.0),
            ("GROUND_FLOOR_HEIGHT", "Zemin kat yüksekliği (m)", 4.0, 2.0, 20.0),
            ("TYPICAL_FLOOR_HEIGHT", "Normal kat yüksekliği (m)", 3.0, 2.0, 10.0),
            ("ROOF_SLOPE", "Çatı eğimi (yüzde)", 33.0, 0.0, 100.0),
            ("MAX_ROOF_RISE", "En fazla çatı yükselmesi (m)", 6.0, 0.0, 30.0),
        ):
            self.addParameter(QgsProcessingParameterNumber(
                key, label, QgsProcessingParameterNumber.Type.Double,
                defaultValue=default, minValue=minimum, maxValue=maximum,
            ))
        self.addParameter(QgsProcessingParameterBoolean("INCLUDE_ROOF", 'Çatıları ekle', defaultValue=True))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.massing_engine_3d import ProceduralMassingEngine

        source = self.parameterAsSource(parameters, "PARCELS", context)
        if not source:
            raise QgsProcessingException('Parsel katmanı okunamadı.')
        values = {
            "setback_m": self.parameterAsDouble(parameters, "SETBACK", context),
            "max_height_m": self.parameterAsDouble(parameters, "MAX_HEIGHT", context),
            "subbasement_height_m": self.parameterAsDouble(parameters, "SUBBASEMENT_HEIGHT", context),
            "ground_floor_height_m": self.parameterAsDouble(parameters, "GROUND_FLOOR_HEIGHT", context),
            "typical_floor_height_m": self.parameterAsDouble(parameters, "TYPICAL_FLOOR_HEIGHT", context),
            "roof_slope_percent": self.parameterAsDouble(parameters, "ROOF_SLOPE", context),
            "max_roof_rise_m": self.parameterAsDouble(parameters, "MAX_ROOF_RISE", context),
            "include_roof": self.parameterAsBool(parameters, "INCLUDE_ROOF", context),
        }
        fields = QgsFields(source.fields())
        fields.append(QgsField("footprint_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("volume_m3", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("volume_ratio", QMetaType.Type.Double, prec=4))
        fields.append(QgsField("floor_count", QMetaType.Type.Int))
        fields.append(QgsField("wall_top_z", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("roof_top_z", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("roof_rise_m", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("gross_floor_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("floor_area_ratio", QMetaType.Type.Double, prec=4))
        fields.append(QgsField("floor_levels", QMetaType.Type.QString, len=254))
        output_type = QgsWkbTypes.addZ(QgsWkbTypes.MultiPolygon)
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, output_type, source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('3B çıktı katmanı oluşturulamadı.')
        generated = 0
        total_features = max(1, source.featureCount())
        for feature_number, feature in enumerate(source.getFeatures(), start=1):
            if feedback.isCanceled():
                break
            try:
                massing = ProceduralMassingEngine.generate(feature.geometry(), **values)
            except ValueError as error:
                feedback.reportError(f'Nesne {feature.id()}: {error}')
                continue
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                massing.footprint_area_m2, massing.gross_volume_m3,
                massing.space_efficiency_ratio, massing.floor_count,
                massing.wall_top_z, massing.roof_top_z,
                massing.roof_rise_m, massing.gross_floor_area_m2, massing.floor_area_ratio,
                ";".join(f"{level:.2f}" for level in massing.floor_elevations_m),
            ])
            output.setGeometry(massing.geometry)
            sink.addFeature(output)
            generated += 1
            feedback.setProgress(100.0 * feature_number / total_features)
        return {"OUTPUT": destination, "GENERATED_COUNT": generated}


class AuditMunicipalBylawComplianceAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_municipal_bylaw_compliance"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMunicipalBylawComplianceAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "PROFILE", 'Kural / şema profili',
            options=["PAIY_DEFAULT", "ISTANBUL_IBB", "ANKARA_ABB", "IZMIR_IBB"],
            defaultValue=0,
        ))
        self.addParameter(QgsProcessingParameterFile(
            "CUSTOM_PROFILE_FILE", 'Özel profil kayıt dosyası (isteğe bağlı)',
            behavior=QgsProcessingParameterFile.File, extension="json", optional=True,
        ))
        self.addParameter(QgsProcessingParameterString(
            "CUSTOM_PROFILE_CODE", 'Özel profil kodu', optional=True,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.bylaw_engine import MunicipalBylawEngine, load_bylaw_profiles

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Girdi katmanı okunamadı.')
        profile = ("PAIY_DEFAULT", "ISTANBUL_IBB", "ANKARA_ABB", "IZMIR_IBB")[
            self.parameterAsEnum(parameters, "PROFILE", context)
        ]
        custom_profile_file = self.parameterAsFile(parameters, "CUSTOM_PROFILE_FILE", context)
        profiles = None
        if custom_profile_file:
            try:
                profiles = load_bylaw_profiles(custom_profile_file)
            except ValueError as error:
                raise QgsProcessingException(str(error)) from error
            profile = self.parameterAsString(parameters, "CUSTOM_PROFILE_CODE", context).strip().upper()
            if not profile:
                raise QgsProcessingException('Özel kayıt dosyasıyla birlikte özel profil kodu belirtilmelidir.')
        fields = QgsFields(source.fields())
        fields.append(QgsField("bylaw_profile", QMetaType.Type.QString, len=30))
        fields.append(QgsField("is_compliant", QMetaType.Type.Bool))
        fields.append(QgsField("audit_status", QMetaType.Type.QString, len=30))
        fields.append(QgsField("violation_count", QMetaType.Type.Int))
        fields.append(QgsField("violations", QMetaType.Type.QString, len=254))
        fields.append(QgsField("missing_rules", QMetaType.Type.QString, len=254))
        fields.append(QgsField("invalid_rules", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Yönetmelik denetimi çıktı katmanı oluşturulamadı.')
        non_compliant = 0
        total_features = max(1, source.featureCount())
        for feature_number, feature in enumerate(source.getFeatures(), start=1):
            if feedback.isCanceled():
                break
            try:
                audit = MunicipalBylawEngine.audit(feature, profile, profiles)
            except ValueError as error:
                raise QgsProcessingException(str(error)) from error
            messages = "; ".join(violation.rule_code for violation in audit.violations)
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                profile, audit.compliant, audit.status, len(audit.violations), messages,
                "; ".join(audit.missing_rules), "; ".join(audit.invalid_rules),
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
            if not audit.compliant:
                non_compliant += 1
            feedback.setProgress(100.0 * feature_number / total_features)
        return {"OUTPUT": destination, "NON_COMPLIANT_COUNT": non_compliant}


class ReconcileWorkspaceVersionsAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "reconcile_workspace_versions"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ReconcileWorkspaceVersionsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "BASE_WORKSPACE", 'Başlangıç GeoPackage dosyası', behavior=QgsProcessingParameterFile.File, extension="gpkg"
        ))
        self.addParameter(QgsProcessingParameterFile(
            "INCOMING_WORKSPACE", 'Gelen GeoPackage dosyası', behavior=QgsProcessingParameterFile.File, extension="gpkg"
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT", 'Çıktı katmanı', 'GeoPackage (*.gpkg)'
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "CONFLICT_STRATEGY", 'Çakışma çözüm politikası',
            options=["Elle incele", "Geleni tercih et", "Yeni zaman damgasını tercih et"],
            defaultValue=0,
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.concurrency_engine import GeoPackageConcurrencyEngine

        try:
            result = GeoPackageConcurrencyEngine.reconcile_workspaces(
                self.parameterAsFile(parameters, "BASE_WORKSPACE", context),
                self.parameterAsFile(parameters, "INCOMING_WORKSPACE", context),
                self.parameterAsFileOutput(parameters, "OUTPUT", context),
                ("MANUAL", "PREFER_INCOMING", "PREFER_NEWER")[
                    self.parameterAsEnum(parameters, "CONFLICT_STRATEGY", context)
                ],
            )
        except (OSError, ValueError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        feedback.pushInfo(
            f'{result.inserted_rows} satır birleştirildi, {result.updated_rows} satır güncellendi ve {len(result.conflicts)} çözülemeyen çakışma kaydedildi.'
        )
        return {
            "OUTPUT": result.output_path,
            "TABLES_PROCESSED": result.tables_processed,
            "INSERTED_ROWS": result.inserted_rows,
            "UPDATED_ROWS": result.updated_rows,
            "CONFLICT_COUNT": len(result.conflicts),
            "SCHEMA_MISMATCH_COUNT": len(result.schema_mismatches),
        }


class PreviewWorkspaceReconciliationAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "preview_workspace_reconciliation"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "advanced_production"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return PreviewWorkspaceReconciliationAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "BASE_WORKSPACE", 'Başlangıç GeoPackage dosyası',
            behavior=QgsProcessingParameterFile.File, extension="gpkg",
        ))
        self.addParameter(QgsProcessingParameterFile(
            "INCOMING_WORKSPACE", 'Gelen GeoPackage dosyası',
            behavior=QgsProcessingParameterFile.File, extension="gpkg",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.concurrency_engine import GeoPackageConcurrencyEngine

        try:
            preview = GeoPackageConcurrencyEngine.preview_workspaces(
                self.parameterAsFile(parameters, "BASE_WORKSPACE", context),
                self.parameterAsFile(parameters, "INCOMING_WORKSPACE", context),
            )
            report = GeoPackageConcurrencyEngine.write_preview_report(
                preview, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        feedback.pushInfo(
            f'Önizlemede yalnızca gelen dosyada bulunan {preview.incoming_only_rows} satır ve ayrışan {preview.divergent_rows} satır bulundu.'
        )
        return {
            "OUTPUT_REPORT": report,
            "TABLES_PROCESSED": preview.tables_processed,
            "INCOMING_ONLY_ROWS": preview.incoming_only_rows,
            "IDENTICAL_ROWS": preview.identical_rows,
            "DIVERGENT_ROWS": preview.divergent_rows,
            "SCHEMA_MISMATCH_COUNT": len(preview.schema_mismatches),
            "INCOMING_ONLY_TABLE_COUNT": len(preview.incoming_only_tables),
        }


class _PlanStageAuditAlgorithm(LocalizedProcessingAlgorithm):
    LEVEL = ""
    ALGORITHM_NAME = ""
    DISPLAY_NAME = ""

    def name(self) -> str:
        return self.ALGORITHM_NAME

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_plan_level_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return self.__class__()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", f"{self.LEVEL} plan kararları",
            [QgsProcessing.SourceType.TypeVectorAnyGeometry],
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "MAP_SCALE", 'Belirtilen harita ölçeği paydası',
            QgsProcessingParameterNumber.Type.Integer,
            defaultValue={"MSP": 250000, "CDP": 100000, "NIP": 5000, "UIP": 1000}[self.LEVEL],
            minValue=1,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", f"{self.LEVEL} denetim sonuçları"))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plan_stage_audit import PlanStageAuditEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Plan kararı katmanı okunamadı.')
        source_features = list(source.getFeatures())
        result = PlanStageAuditEngine.audit_features(
            source_features, self.LEVEL, self.parameterAsInt(parameters, "MAP_SCALE", context)
        )
        fields = QgsFields(source.fields())
        fields.append(QgsField("audit_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("error_count", QMetaType.Type.Int))
        fields.append(QgsField("warning_count", QMetaType.Type.Int))
        fields.append(QgsField("rule_codes", QMetaType.Type.QString, len=254))
        fields.append(QgsField("articles", QMetaType.Type.QString, len=120))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Plan denetimi çıktısı oluşturulamadı.')
        total = max(1, len(source_features))
        for index, (feature, record) in enumerate(zip(source_features, result.records), start=1):
            if feedback.isCanceled():
                break
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                record.status,
                record.error_count,
                record.warning_count,
                ";".join(item.code for item in record.findings),
                ";".join(sorted({item.article for item in record.findings})),
                " ".join(item.message for item in record.findings)[:254],
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
            feedback.setProgress(100.0 * index / total)
        for theme in result.missing_msp_themes:
            feedback.pushWarning("MSP tematik kapsamı inceleme gerektiriyor: " + theme)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(result.records),
            "COMPLIANT_COUNT": result.compliant_count,
            "ERROR_COUNT": result.error_count,
            "WARNING_COUNT": result.warning_count,
            "MISSING_THEME_COUNT": len(result.missing_msp_themes),
            "CATALOG_VERSION": result.catalog_version,
        }


class AuditMSPPlanRequirementsAlgorithm(_PlanStageAuditAlgorithm):
    LEVEL = "MSP"
    ALGORITHM_NAME = "audit_msp_plan_requirements"
    DISPLAY_NAME = "MSP Strateji Planı Gerekliliklerini Denetle"


class AuditCDPPlanRequirementsAlgorithm(_PlanStageAuditAlgorithm):
    LEVEL = "CDP"
    ALGORITHM_NAME = "audit_cdp_plan_requirements"
    DISPLAY_NAME = 'ÇDP Environmental plan Gerekliliklerini Denetle'


class AuditNIPPlanRequirementsAlgorithm(_PlanStageAuditAlgorithm):
    LEVEL = "NIP"
    ALGORITHM_NAME = "audit_nip_plan_requirements"
    DISPLAY_NAME = 'NİP Master plan Gerekliliklerini Denetle'


class AuditUIPPlanRequirementsAlgorithm(_PlanStageAuditAlgorithm):
    LEVEL = "UIP"
    ALGORITHM_NAME = "audit_uip_plan_requirements"
    DISPLAY_NAME = 'UİP Implementation plan Gerekliliklerini Denetle'


class AuditPlanHierarchyConsistencyAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_plan_hierarchy_consistency"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_plan_level_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditPlanHierarchyConsistencyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "PARENT", 'Üst kademe plan katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "PARENT_LEVEL", 'Üst plan kademesi', options=["MSP", "ÇDP", "NİP"], defaultValue=1
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "CHILD", 'Alt kademe plan katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "CHILD_LEVEL", 'Alt plan kademesi', options=["ÇDP", "NİP", "UİP"], defaultValue=2
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "MINIMUM_COVERAGE", 'Asgari kapsama oranı',
            QgsProcessingParameterNumber.Type.Double, defaultValue=0.99, minValue=0.01, maxValue=1.0,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.hierarchy_audit import PlanHierarchyAuditEngine

        parent = self.parameterAsSource(parameters, "PARENT", context)
        child = self.parameterAsSource(parameters, "CHILD", context)
        if not parent or not child:
            raise QgsProcessingException('Üst ve alt kademe plan katmanlarının ikisi de gereklidir.')
        parent_level = ("MSP", "CDP", "NIP")[self.parameterAsEnum(parameters, "PARENT_LEVEL", context)]
        child_level = ("CDP", "NIP", "UIP")[self.parameterAsEnum(parameters, "CHILD_LEVEL", context)]
        try:
            records = PlanHierarchyAuditEngine.audit(
                parent.getFeatures(), child.getFeatures(), parent_level, child_level,
                self.parameterAsDouble(parameters, "MINIMUM_COVERAGE", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(child.fields())
        fields.append(QgsField("parent_id", QMetaType.Type.QString, len=80))
        fields.append(QgsField("coverage", QMetaType.Type.Double, prec=5))
        fields.append(QgsField("link_status", QMetaType.Type.QString, len=20))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, child.wkbType(), child.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Plan hiyerarşisi denetimi çıktısı oluşturulamadı.')
        for record in records:
            output = QgsFeature(fields)
            output.setAttributes(record.child_feature.attributes() + [
                record.parent_id, record.coverage_ratio, record.linkage_status, record.message,
            ])
            output.setGeometry(record.child_feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(records),
            "MATCH_COUNT": sum(item.linkage_status == "MATCH" for item in records),
            "REVIEW_COUNT": sum(item.linkage_status != "MATCH" for item in records),
        }


class AuditPlanSubmissionDossierAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_plan_submission_dossier"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_plan_level_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditPlanSubmissionDossierAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plan_submission import PlanSubmissionAuditEngine

        try:
            result = PlanSubmissionAuditEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context)
            )
            output = PlanSubmissionAuditEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output,
            "STATUS": result.status,
            "ERROR_COUNT": result.error_count,
            "WARNING_COUNT": result.warning_count,
        }


class ScreenMPYYThresholdConstraintsAlgorithm(LocalizedProcessingAlgorithm):
    CONSTRAINTS = (
        ("GEOLOGY_HAZARD", "Jeoloji ve tehlike eşikleri"),
        ("FLOOD_HYDROLOGY", "Taşkın ve hidroloji eşikleri"),
        ("PROTECTED_AREA", "Korunan alan eşikleri"),
        ("AGRICULTURE_FOREST", "Tarım ve orman eşikleri"),
        ("WATER_BASIN", "İçme suyu havzası eşikleri"),
        ("COAST_INFRASTRUCTURE", "Kıyı ve altyapı eşikleri"),
    )

    def name(self) -> str:
        return "screen_mpyy_threshold_constraints"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ScreenMPYYThresholdConstraintsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        for key, label in self.CONSTRAINTS:
            self.addParameter(QgsProcessingParameterFeatureSource(
                key, label + " (isteğe bağlı)", [QgsProcessing.SourceType.TypeVectorPolygon], optional=True
            ))
        self.addParameter(QgsProcessingParameterNumber(
            "REVIEW_RATIO", 'İnceleme eşik oranı',
            QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0, maxValue=1.0,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.threshold_screening import ThresholdScreeningEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Plan önerisi katmanı okunamadı.')
        if source.sourceCrs().isGeographic():
            raise QgsProcessingException('Eşik alanı taraması için projeksiyonlu KRS gereklidir.')
        constraints = {}
        for key, _label in self.CONSTRAINTS:
            constraint_source = self.parameterAsSource(parameters, key, context)
            if constraint_source:
                if constraint_source.sourceCrs() != source.sourceCrs():
                    raise QgsProcessingException(
                        key + " katmanı öneri katmanıyla aynı KRS'yi kullanmalıdır."
                    )
                constraints[key] = list(constraint_source.getFeatures())
        try:
            records = ThresholdScreeningEngine.screen(
                source.getFeatures(), constraints,
                self.parameterAsDouble(parameters, "REVIEW_RATIO", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(source.fields())
        fields.append(QgsField("threshold_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("overlap_area", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("overlap_ratio", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("categories", QMetaType.Type.QString, len=254))
        fields.append(QgsField("article", QMetaType.Type.QString, len=20))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Eşik taraması çıktısı oluşturulamadı.')
        for record in records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.overlap_area, record.overlap_ratio,
                ";".join(record.categories), "MPYY 22", record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(records),
            "REVIEW_COUNT": sum(item.status == "REVIEW_REQUIRED" for item in records),
            "INVALID_COUNT": sum(item.status == "INVALID_GEOMETRY" for item in records),
        }


class AuditMPYYRoadPlanChangeAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_mpyy_road_plan_change"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYRoadPlanChangeAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.road_change_audit import RoadChangeAuditEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Yol değişikliği katmanı okunamadı.')
        fields = QgsFields(source.fields())
        fields.append(QgsField("audit_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("finding_codes", QMetaType.Type.QString, len=254))
        fields.append(QgsField("error_count", QMetaType.Type.Int))
        fields.append(QgsField("warning_count", QMetaType.Type.Int))
        fields.append(QgsField("article", QMetaType.Type.QString, len=20))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Yol denetimi çıktısı oluşturulamadı.')
        counts = {"NON_COMPLIANT": 0, "REVIEW_REQUIRED": 0, "COMPLIANT": 0}
        feature_count = 0
        for feature in source.getFeatures():
            data = {field.name().lower(): feature[field.name()] for field in feature.fields()}
            audit = RoadChangeAuditEngine.audit(data)
            counts[audit.status] += 1
            feature_count += 1
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                audit.status, ";".join(item.code for item in audit.findings),
                sum(item.severity == "ERROR" for item in audit.findings),
                sum(item.severity == "WARNING" for item in audit.findings), "MPYY 26",
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
        return {"OUTPUT": destination, "FEATURE_COUNT": feature_count, **counts}


class AuditMPYYDensityHeightChangeAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_mpyy_density_height_change"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYDensityHeightChangeAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.density_change_audit import DensityChangeAuditEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Yoğunluk ve yükseklik değişikliği katmanı okunamadı.')
        fields = QgsFields(source.fields())
        fields.append(QgsField("audit_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("required_k", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("population_delta", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("finding_codes", QMetaType.Type.QString, len=254))
        fields.append(QgsField("article", QMetaType.Type.QString, len=20))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Yoğunluk ve yükseklik denetimi çıktısı oluşturulamadı.')
        feature_count = 0
        non_compliant = 0
        for feature in source.getFeatures():
            data = {field.name().lower(): feature[field.name()] for field in feature.fields()}
            audit = DensityChangeAuditEngine.audit(data)
            feature_count += 1
            non_compliant += audit.status == "NON_COMPLIANT"
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                audit.status, audit.required_facade_distance_m, audit.population_change,
                ";".join(item.code for item in audit.findings), "MPYY 26",
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination, "FEATURE_COUNT": feature_count,
            "NON_COMPLIANT_COUNT": non_compliant,
        }


class EvaluateMSPActionMonitoringAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "evaluate_msp_action_monitoring"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return EvaluateMSPActionMonitoringAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterString(
            "EVALUATION_DATE", 'Değerlendirme tarihi (YYYY-AA-GG)', defaultValue="", optional=True
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.msp_monitoring import MSPMonitoringEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('MSP eylem katmanı okunamadı.')
        date_value = self.parameterAsString(parameters, "EVALUATION_DATE", context).strip() or None
        try:
            result = MSPMonitoringEngine.evaluate(source.getFeatures(), date_value)
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(source.fields())
        fields.append(QgsField("monitor_status", QMetaType.Type.QString, len=20))
        fields.append(QgsField("progress_ratio", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("article", QMetaType.Type.QString, len=20))
        fields.append(QgsField("monitor_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('MSP izleme çıktısı oluşturulamadı.')
        for record in result.records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.progress_ratio, "MPYY 16", record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(result.records),
            "WEIGHTED_PROGRESS": result.weighted_progress_ratio,
            "COMPLETE_COUNT": result.complete_count,
            "DELAYED_COUNT": result.delayed_count,
            "MISSING_DATA_COUNT": result.missing_data_count,
        }


class ClassifyCDPRevisionScopeAlgorithm(LocalizedProcessingAlgorithm):
    TRIGGER_PARAMETERS = (
        ("POPULATION_REQUIREMENT", "Nüfus gereksinimi karşılanamıyor"),
        ("REGIONAL_INVESTMENT", "Yeni bölgesel ölçekli yatırım"),
        ("REGIONAL_LAND_USE_DEMAND", "Yeni bölgesel arazi kullanım talebi"),
        ("CHANGED_SPATIAL_DYNAMICS", "Mekânsal dinamikler değişti"),
        ("MAIN_STRATEGY_CHANGED", "Ana plan stratejisi değişti"),
    )

    def name(self) -> str:
        return "classify_cdp_revision_scope"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ClassifyCDPRevisionScopeAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "CURRENT", 'Mevcut plan katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "PROPOSED", 'Önerilen plan katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        for key, label in self.TRIGGER_PARAMETERS:
            self.addParameter(QgsProcessingParameterBoolean(key, label, defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(
            "RATIONALE_DOCUMENTED", 'Revizyon gerekçesi belgelenmiş', defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "INFRASTRUCTURE_IMPACT_DOCUMENTED", 'Altyapı etkileri belgelenmiş', defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.cdp_revision import CDPRevisionEngine

        current = self.parameterAsSource(parameters, "CURRENT", context)
        proposed = self.parameterAsSource(parameters, "PROPOSED", context)
        if not current or not proposed:
            raise QgsProcessingException('Mevcut ve öneri ÇDP katmanları gereklidir.')
        if current.sourceCrs().isGeographic() or proposed.sourceCrs().isGeographic():
            raise QgsProcessingException('ÇDP alan karşılaştırması için projeksiyonlu KRS gereklidir.')
        if current.sourceCrs() != proposed.sourceCrs():
            raise QgsProcessingException("Mevcut ve öneri ÇDP katmanları aynı KRS'yi kullanmalıdır.")
        triggers = {
            key: self.parameterAsBool(parameters, key, context)
            for key, _label in self.TRIGGER_PARAMETERS
        }
        assessment = CDPRevisionEngine.assess(
            current.getFeatures(), proposed.getFeatures(), triggers,
            self.parameterAsBool(parameters, "INFRASTRUCTURE_IMPACT_DOCUMENTED", context),
            self.parameterAsBool(parameters, "RATIONALE_DOCUMENTED", context),
        )
        fields = QgsFields(proposed.fields())
        fields.append(QgsField("scope_class", QMetaType.Type.QString, len=30))
        fields.append(QgsField("changed_area", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("changed_ratio", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("revision_triggers", QMetaType.Type.QString, len=254))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, proposed.wkbType(), proposed.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('ÇDP kapsam çıktısı oluşturulamadı.')
        feature_count = 0
        for feature in proposed.getFeatures():
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                assessment.classification, assessment.changed_area,
                assessment.changed_area_ratio, ";".join(assessment.triggers),
                " ".join(assessment.findings)[:254],
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
            feature_count += 1
        return {
            "OUTPUT": destination, "FEATURE_COUNT": feature_count,
            "CLASSIFICATION": assessment.classification,
            "CHANGED_AREA": assessment.changed_area,
            "CHANGED_AREA_RATIO": assessment.changed_area_ratio,
        }


class AuditNIPUIPActiveMobilityNetworkAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_nip_uip_active_mobility_network"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditNIPUIPActiveMobilityNetworkAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "NETWORK", 'Çizgi ağ katmanı', [QgsProcessing.SourceType.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "CENTERS", 'Etkinlik merkezleri (isteğe bağlı)',
            [QgsProcessing.SourceType.TypeVectorAnyGeometry], optional=True,
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "SNAP_TOLERANCE", 'Yakalama toleransı (m)', defaultValue=1.0, minValue=0.001,
            parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "CENTER_ACCESS_DISTANCE", 'Merkez erişim mesafesi (m)', defaultValue=25.0,
            minValue=0.0, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.active_mobility_audit import ActiveMobilityAuditEngine

        network = self.parameterAsSource(parameters, "NETWORK", context)
        centers = self.parameterAsSource(parameters, "CENTERS", context)
        if not network:
            raise QgsProcessingException('Aktif ulaşım ağı okunamadı.')
        if network.sourceCrs().isGeographic():
            raise QgsProcessingException('Aktif ulaşım mesafeleri için projeksiyonlu KRS gereklidir.')
        if centers and centers.sourceCrs() != network.sourceCrs():
            raise QgsProcessingException("Merkezler ağ ile aynı KRS'yi kullanmalıdır.")
        try:
            result = ActiveMobilityAuditEngine.audit(
                network.getFeatures(), centers.getFeatures() if centers else (),
                self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context),
                self.parameterAsDouble(parameters, "CENTER_ACCESS_DISTANCE", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(network.fields())
        fields.append(QgsField("network_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("component_id", QMetaType.Type.Int))
        fields.append(QgsField("component_size", QMetaType.Type.Int))
        fields.append(QgsField("dead_end_count", QMetaType.Type.Int))
        fields.append(QgsField("articles", QMetaType.Type.QString, len=20))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, network.wkbType(), network.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Aktif ulaşım denetimi çıktısı oluşturulamadı.')
        for record in result.records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.component_id, record.component_feature_count,
                record.dead_end_count, "MPYY 23-24", record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(result.records),
            "COMPONENT_COUNT": result.component_count,
            "DISCONNECTED_FEATURE_COUNT": result.disconnected_feature_count,
            "CENTER_COUNT": result.center_count,
            "UNSERVED_CENTER_COUNT": result.unserved_center_count,
        }


class AuditMPYYEvidenceProvenanceAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_mpyy_evidence_provenance"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYEvidenceProvenanceAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "VERIFY_LOCAL_FILES", 'Yerel dayanak dosyalarını doğrula', defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.evidence_provenance import EvidenceProvenanceAuditEngine

        try:
            result = EvidenceProvenanceAuditEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context),
                self.parameterAsBool(parameters, "VERIFY_LOCAL_FILES", context),
            )
            output = EvidenceProvenanceAuditEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output,
            "STATUS": result.status,
            "ITEM_COUNT": result.item_count,
            "VERIFIED_FILE_COUNT": result.verified_file_count,
            "ERROR_COUNT": result.error_count,
            "WARNING_COUNT": result.warning_count,
        }


class AuditInstitutionOpinionRegisterAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_institution_opinion_register"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditInstitutionOpinionRegisterAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "REGISTER", 'JSON kayıt dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterString(
            "EVALUATION_DATE", 'Değerlendirme tarihi (YYYY-AA-GG)',
            defaultValue="", optional=True,
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.opinion_register import OpinionRegisterAuditEngine

        evaluation_date = self.parameterAsString(parameters, "EVALUATION_DATE", context).strip() or None
        try:
            result = OpinionRegisterAuditEngine.audit_file(
                self.parameterAsFile(parameters, "REGISTER", context), evaluation_date
            )
            output = OpinionRegisterAuditEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output,
            "STATUS": result.status,
            "RECORD_COUNT": len(result.records),
            "LATE_RESPONSE_COUNT": result.late_response_count,
            "DEEMED_NO_NEGATIVE_COUNT": result.deemed_no_negative_count,
            "PENDING_COUNT": result.pending_count,
            "INVALID_COUNT": result.invalid_count,
        }


class AnalyzeNIPUIPRoutedAccessibilityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "analyze_nip_uip_routed_accessibility"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeNIPUIPRoutedAccessibilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "NETWORK", 'Çizgi ağ katmanı', [QgsProcessing.SourceType.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "DEMAND", 'Talep nokta katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "FACILITIES", 'Tesis nokta katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "MAX_ROUTE_DISTANCE", 'Azami güzergâh mesafesi (m)', defaultValue=500.0,
            minValue=0.001, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "SNAP_TOLERANCE", 'Yakalama toleransı (m)', defaultValue=1.0,
            minValue=0.001, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "MAX_SNAP_DISTANCE", 'Azami yakalama mesafesi (m)', defaultValue=50.0,
            minValue=0.0, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.routed_accessibility import RoutedAccessibilityEngine

        network = self.parameterAsSource(parameters, "NETWORK", context)
        demand = self.parameterAsSource(parameters, "DEMAND", context)
        facilities = self.parameterAsSource(parameters, "FACILITIES", context)
        if not network or not demand or not facilities:
            raise QgsProcessingException('Ağ, talep ve donatı katmanları gereklidir.')
        if network.sourceCrs().isGeographic():
            raise QgsProcessingException('Ağ üzerinden erişilebilirlik için projeksiyonlu KRS gereklidir.')
        if demand.sourceCrs() != network.sourceCrs() or facilities.sourceCrs() != network.sourceCrs():
            raise QgsProcessingException("Tüm ağ erişilebilirliği katmanları aynı KRS'yi kullanmalıdır.")
        try:
            result = RoutedAccessibilityEngine.analyze(
                network.getFeatures(), demand.getFeatures(), facilities.getFeatures(),
                self.parameterAsDouble(parameters, "MAX_ROUTE_DISTANCE", context),
                self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context),
                self.parameterAsDouble(parameters, "MAX_SNAP_DISTANCE", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(demand.fields())
        fields.append(QgsField("access_status", QMetaType.Type.QString, len=20))
        fields.append(QgsField("route_distance_m", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("facility_id", QMetaType.Type.QString, len=80))
        fields.append(QgsField("snap_distance_m", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("articles", QMetaType.Type.QString, len=20))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, demand.wkbType(), demand.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Ağ üzerinden erişilebilirlik çıktısı oluşturulamadı.')
        for record in result.records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.route_distance_m, record.facility_id,
                record.snap_distance_m, "MPYY 23-24", record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(result.records),
            "ACCESSIBLE_COUNT": result.accessible_count,
            "INACCESSIBLE_COUNT": result.inaccessible_count,
            "UNREACHABLE_COUNT": result.unreachable_count,
            "UNSNAPPED_COUNT": result.unsnapped_count,
            "GRAPH_NODE_COUNT": result.graph_node_count,
            "GRAPH_EDGE_COUNT": result.graph_edge_count,
        }


class AuditAdjacentPlanBoundaryConsistencyAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_adjacent_plan_boundary_consistency"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditAdjacentPlanBoundaryConsistencyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "REFERENCE", 'Referans plan katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterField(
            "REFERENCE_CODE_FIELD", 'Referans karar kodu alanı', optional=True,
            parentLayerParameterName="REFERENCE",
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "ADJACENT", 'Komşu plan katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterField(
            "ADJACENT_CODE_FIELD", 'Komşu karar kodu alanı', optional=True,
            parentLayerParameterName="ADJACENT",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "TOLERANCE", 'Sınır toleransı (m)', defaultValue=1.0, minValue=0.001,
            parentParameterName="REFERENCE",
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "MINIMUM_COVERAGE", 'Asgari kapsama oranı',
            QgsProcessingParameterNumber.Type.Double, defaultValue=0.95,
            minValue=0.01, maxValue=1.0,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.adjacent_boundary_audit import AdjacentBoundaryAuditEngine

        reference = self.parameterAsSource(parameters, "REFERENCE", context)
        adjacent = self.parameterAsSource(parameters, "ADJACENT", context)
        if not reference or not adjacent:
            raise QgsProcessingException('Başvuru ve bitişik plan birleşim katmanları gereklidir.')
        if reference.sourceCrs().isGeographic() or adjacent.sourceCrs() != reference.sourceCrs():
            raise QgsProcessingException("Plan birleşimleri aynı projeksiyonlu KRS'yi kullanmalıdır.")
        try:
            records = AdjacentBoundaryAuditEngine.audit(
                reference.getFeatures(), adjacent.getFeatures(),
                self.parameterAsDouble(parameters, "TOLERANCE", context),
                self.parameterAsDouble(parameters, "MINIMUM_COVERAGE", context),
                self.parameterAsString(parameters, "REFERENCE_CODE_FIELD", context),
                self.parameterAsString(parameters, "ADJACENT_CODE_FIELD", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(reference.fields())
        fields.append(QgsField("seam_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("adjacent_id", QMetaType.Type.QString, len=80))
        fields.append(QgsField("min_distance", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("matched_length", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("coverage_ratio", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("adjacent_code", QMetaType.Type.QString, len=80))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, reference.wkbType(), reference.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Bitişik plan denetimi çıktısı oluşturulamadı.')
        for record in records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.adjacent_feature_id, record.minimum_distance,
                record.matched_length, record.coverage_ratio, record.adjacent_code, record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(records),
            "MATCH_COUNT": sum(item.status == "MATCH" for item in records),
            "GAP_COUNT": sum(item.status == "GEOMETRY_GAP" for item in records),
            "CONFLICT_COUNT": sum(item.status == "CODE_CONFLICT" for item in records),
        }


class AuditPlanFabricTopologyAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_plan_fabric_topology"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_evidence_change_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditPlanFabricTopologyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "DECISIONS", 'Plan karar poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "BOUNDARY", 'Plan sınırı (isteğe bağlı)', [QgsProcessing.SourceType.TypeVectorPolygon],
            optional=True,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "AREA_TOLERANCE", 'Alan toleransı (m²)',
            QgsProcessingParameterNumber.Type.Double, defaultValue=0.01, minValue=0.0,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))
        self.addParameter(QgsProcessingParameterFeatureSink("GAPS", 'Boşluk poligonları'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plan_fabric_audit import PlanFabricAuditEngine

        decisions = self.parameterAsSource(parameters, "DECISIONS", context)
        boundary = self.parameterAsSource(parameters, "BOUNDARY", context)
        if not decisions:
            raise QgsProcessingException('Plan kararı katmanı okunamadı.')
        if decisions.sourceCrs().isGeographic():
            raise QgsProcessingException('Plan dokusu alan denetimi için projeksiyonlu KRS gereklidir.')
        if boundary and boundary.sourceCrs() != decisions.sourceCrs():
            raise QgsProcessingException("Plan sınırı kararlarla aynı KRS'yi kullanmalıdır.")
        try:
            result = PlanFabricAuditEngine.audit(
                decisions.getFeatures(), boundary.getFeatures() if boundary else (),
                self.parameterAsDouble(parameters, "AREA_TOLERANCE", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(decisions.fields())
        fields.append(QgsField("fabric_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("overlap_area", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("overlap_ratio", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("conflicting_ids", QMetaType.Type.QString, len=254))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, decisions.wkbType(), decisions.sourceCrs()
        )
        gap_fields = QgsFields()
        gap_fields.append(QgsField("gap_area", QMetaType.Type.Double, prec=3))
        gap_fields.append(QgsField("articles", QMetaType.Type.QString, len=20))
        gap_sink, gap_destination = self.parameterAsSink(
            parameters, "GAPS", context, gap_fields,
            QgsWkbTypes.Type.MultiPolygon, decisions.sourceCrs(),
        )
        if sink is None or gap_sink is None:
            raise QgsProcessingException('Plan dokusu çıktıları oluşturulamadı.')
        for record in result.records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.overlap_area, record.overlap_ratio,
                ";".join(record.conflicting_feature_ids), record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        if result.gap_geometry:
            gap_geometry = QgsGeometry(result.gap_geometry)
            gap_geometry.convertToMultiType()
            gap_feature = QgsFeature(gap_fields)
            gap_feature.setAttributes([result.gap_area, "MPYY 7,21"])
            gap_feature.setGeometry(gap_geometry)
            gap_sink.addFeature(gap_feature)
        return {
            "OUTPUT": destination,
            "GAPS": gap_destination,
            "FEATURE_COUNT": len(result.records),
            "OVERLAP_FEATURE_COUNT": result.overlap_feature_count,
            "INVALID_FEATURE_COUNT": result.invalid_feature_count,
            "GAP_AREA": result.gap_area,
        }


class AuditMPYYPlanReportContentAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_mpyy_plan_report_content"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYPlanReportContentAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plan_report_audit import PlanReportAuditEngine

        try:
            result = PlanReportAuditEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context)
            )
            output = PlanReportAuditEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output,
            "STATUS": result.status,
            "ERROR_COUNT": result.error_count,
            "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYArticle12WalkingDistancesAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_mpyy_article12_walking_distances"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYArticle12WalkingDistancesAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "NETWORK", 'Çizgi ağ katmanı', [QgsProcessing.SourceType.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "DEMAND", 'Talep nokta katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterField(
            "DEMAND_SERVICE_FIELD", 'Talep hizmet türü alanı',
            parentLayerParameterName="DEMAND",
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "FACILITIES", 'Tesis nokta katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterField(
            "FACILITY_TYPE_FIELD", 'Tesis türü alanı',
            parentLayerParameterName="FACILITIES",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "SNAP_TOLERANCE", 'Yakalama toleransı (m)', defaultValue=1.0,
            minValue=0.001, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "MAX_SNAP_DISTANCE", 'Azami yakalama mesafesi (m)', defaultValue=50.0,
            minValue=0.0, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.article12_accessibility import Article12AccessibilityEngine

        network = self.parameterAsSource(parameters, "NETWORK", context)
        demand = self.parameterAsSource(parameters, "DEMAND", context)
        facilities = self.parameterAsSource(parameters, "FACILITIES", context)
        if not network or not demand or not facilities:
            raise QgsProcessingException('Ağ, talep ve donatı katmanları gereklidir.')
        if network.sourceCrs().isGeographic():
            raise QgsProcessingException('Madde 12 güzergâh mesafeleri için projeksiyonlu KRS gereklidir.')
        if demand.sourceCrs() != network.sourceCrs() or facilities.sourceCrs() != network.sourceCrs():
            raise QgsProcessingException("Tüm Madde 12 katmanları aynı KRS'yi kullanmalıdır.")
        try:
            result = Article12AccessibilityEngine.audit(
                network.getFeatures(), demand.getFeatures(), facilities.getFeatures(),
                self.parameterAsString(parameters, "DEMAND_SERVICE_FIELD", context),
                self.parameterAsString(parameters, "FACILITY_TYPE_FIELD", context),
                self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context),
                self.parameterAsDouble(parameters, "MAX_SNAP_DISTANCE", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(demand.fields())
        fields.append(QgsField("article12_status", QMetaType.Type.QString, len=30))
        fields.append(QgsField("service_type", QMetaType.Type.QString, len=80))
        fields.append(QgsField("threshold_m", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("route_distance_m", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("facility_id", QMetaType.Type.QString, len=80))
        fields.append(QgsField("exception_basis", QMetaType.Type.QString, len=160))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, demand.wkbType(), demand.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Madde 12 yürüme denetimi çıktısı oluşturulamadı.')
        for record in result.records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.service_type, record.threshold_m,
                record.route_distance_m, record.facility_id, record.exception_basis, record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination,
            "FEATURE_COUNT": len(result.records),
            "COMPLIANT_COUNT": result.compliant_count,
            "REVIEW_COUNT": result.review_count,
            "NON_COMPLIANT_COUNT": result.non_compliant_count,
            "INVALID_COUNT": result.invalid_count,
        }


class _SpecialPlanDossierAlgorithm(LocalizedProcessingAlgorithm):
    AUDIT_TYPE = ""
    ALGORITHM_NAME = ""
    DISPLAY_NAME = ""

    def name(self) -> str:
        return self.ALGORITHM_NAME

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", self.DISPLAY_NAME + " bildirimi", behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", self.DISPLAY_NAME + " raporu", 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.special_plan_audits import SpecialPlanAuditEngine

        try:
            result = SpecialPlanAuditEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context), self.AUDIT_TYPE
            )
            output = SpecialPlanAuditEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output,
            "STATUS": result.status,
            "ERROR_COUNT": result.error_count,
            "WARNING_COUNT": result.warning_count,
        }


class AuditConservationPlanDossierAlgorithm(_SpecialPlanDossierAlgorithm):
    AUDIT_TYPE = "CONSERVATION_PLAN"
    ALGORITHM_NAME = "audit_conservation_plan_dossier"
    DISPLAY_NAME = "MPYY Koruma Amaçlı İmar Planı Dosyasını Denetle"

    def createInstance(self):
        return AuditConservationPlanDossierAlgorithm()


class AuditIntegratedCoastalPlanDossierAlgorithm(_SpecialPlanDossierAlgorithm):
    AUDIT_TYPE = "INTEGRATED_COASTAL_PLAN"
    ALGORITHM_NAME = "audit_integrated_coastal_plan_dossier"
    DISPLAY_NAME = "MPYY Bütünleşik Kıyı Alanları Planı Dosyasını Denetle"

    def createInstance(self):
        return AuditIntegratedCoastalPlanDossierAlgorithm()


class AuditUrbanDesignProjectPrerequisitesAlgorithm(_SpecialPlanDossierAlgorithm):
    AUDIT_TYPE = "URBAN_DESIGN_PROJECT"
    ALGORITHM_NAME = "audit_urban_design_project_prerequisites"
    DISPLAY_NAME = "MPYY Kentsel Tasarım Projesi Ön Koşullarını Denetle"

    def createInstance(self):
        return AuditUrbanDesignProjectPrerequisitesAlgorithm()


class _MPYYGeneralDossierAlgorithm(LocalizedProcessingAlgorithm):
    AUDIT_TYPE = ""
    ALGORITHM_NAME = ""
    DISPLAY_NAME = ""

    def name(self):
        return self.ALGORITHM_NAME

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", self.DISPLAY_NAME + " bildirimi", behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", self.DISPLAY_NAME + " raporu", 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mpyy_general_dossiers import MPYYGeneralDossierEngine

        try:
            result = MPYYGeneralDossierEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context), self.AUDIT_TYPE
            )
            output = MPYYGeneralDossierEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count,
        }


class AuditMPYYArticle8ResearchDossierAlgorithm(_MPYYGeneralDossierAlgorithm):
    AUDIT_TYPE = "ARTICLE_8_RESEARCH"
    ALGORITHM_NAME = "audit_mpyy_article8_research_dossier"
    DISPLAY_NAME = "MPYY Madde 8 Araştırma Dosyasını Denetle"

    def createInstance(self):
        return AuditMPYYArticle8ResearchDossierAlgorithm()


class AuditMPYYArticle11StandardsContextAlgorithm(_MPYYGeneralDossierAlgorithm):
    AUDIT_TYPE = "ARTICLE_11_STANDARDS"
    ALGORITHM_NAME = "audit_mpyy_article11_standards_context"
    DISPLAY_NAME = "MPYY Madde 11 Standart Bağlamını Denetle"

    def createInstance(self):
        return AuditMPYYArticle11StandardsContextAlgorithm()


class AuditMPYYArticle10OfficialLegendAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_article10_official_legend"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYArticle10OfficialLegendAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterField(
            "CODE_FIELD", 'Gösterim kodu alanı', parentLayerParameterName="INPUT"
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "PLAN_LEVEL", 'Plan kademesi', options=["MSP", "ÇDP", "NİP", "UİP"], defaultValue=3
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.article10_legend_audit import Article10LegendAuditEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Plan kararı katmanı okunamadı.')
        level = ("MSP", "CDP", "NIP", "UIP")[self.parameterAsEnum(parameters, "PLAN_LEVEL", context)]
        try:
            records = Article10LegendAuditEngine.audit(
                source.getFeatures(), level, self.parameterAsString(parameters, "CODE_FIELD", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(source.fields())
        fields.append(QgsField("legend_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("normalized_code", QMetaType.Type.QString, len=120))
        fields.append(QgsField("catalog_source", QMetaType.Type.QString, len=80))
        fields.append(QgsField("article", QMetaType.Type.QString, len=20))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Resmî gösterim denetimi çıktısı oluşturulamadı.')
        for record in records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.normalized_code, record.catalog_source,
                "MPYY 10", record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination, "FEATURE_COUNT": len(records),
            "OFFICIAL_COUNT": sum(item.status == "OFFICIAL_MATCH" for item in records),
            "REVIEW_COUNT": sum(item.status == "UNMAPPED_REVIEW" for item in records),
            "MISSING_COUNT": sum(item.status == "MISSING_CODE" for item in records),
        }


class ClassifyMPYYArticle25PlanInterventionAlgorithm(LocalizedProcessingAlgorithm):
    DECLARATIONS = (
        ("NEED_NOT_MET", "Mevcut plan planlama gereksinimlerini karşılamıyor"),
        ("IMPLEMENTATION_IMPOSSIBLE", "Mevcut planın uygulanması olanaksız"),
        ("UPPER_PLAN_ALIGNMENT", "Üst plan uyumu yenileme gerektiriyor"),
        ("MAIN_DECISIONS_AFFECTED", "Ana plan kararları etkileniyor"),
        ("RATIONALE_DOCUMENTED", "Müdahale gerekçesi belgelendi"),
        ("LAND_USE_CONTINUITY_DOCUMENTED", "Arazi kullanım sürekliliği ve bütünlüğü belgelendi"),
    )

    def name(self):
        return "classify_mpyy_article25_plan_intervention"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return ClassifyMPYYArticle25PlanInterventionAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "CURRENT", 'Mevcut plan katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "PROPOSED", 'Önerilen plan katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        for key, label in self.DECLARATIONS:
            self.addParameter(QgsProcessingParameterBoolean(key, label, defaultValue=False))
        self.addParameter(QgsProcessingParameterDistance(
            "ADJACENCY_TOLERANCE", 'Komşuluk toleransı (m)', defaultValue=0.01,
            minValue=0.0, parentParameterName="CURRENT",
        ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.article25_intervention import Article25InterventionEngine

        current = self.parameterAsSource(parameters, "CURRENT", context)
        proposed = self.parameterAsSource(parameters, "PROPOSED", context)
        if not current or not proposed:
            raise QgsProcessingException('Mevcut ve öneri plan katmanları gereklidir.')
        if current.sourceCrs().isGeographic() or current.sourceCrs() != proposed.sourceCrs():
            raise QgsProcessingException("Madde 25 karşılaştırması aynı projeksiyonlu KRS'yi gerektirir.")
        declarations = {
            key: self.parameterAsBool(parameters, key, context) for key, _label in self.DECLARATIONS
        }
        assessment = Article25InterventionEngine.assess(
            current.getFeatures(), proposed.getFeatures(), declarations,
            self.parameterAsDouble(parameters, "ADJACENCY_TOLERANCE", context),
        )
        fields = QgsFields(proposed.fields())
        fields.append(QgsField("intervention", QMetaType.Type.QString, len=30))
        fields.append(QgsField("changed_area", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("added_area", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("removed_area", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("addition_contiguous", QMetaType.Type.Bool))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, proposed.wkbType(), proposed.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Madde 25 çıktısı oluşturulamadı.')
        count = 0
        for feature in proposed.getFeatures():
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                assessment.classification, assessment.changed_area, assessment.added_area,
                assessment.removed_area, assessment.addition_contiguous,
                " ".join(assessment.findings)[:254],
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
            count += 1
        return {
            "OUTPUT": destination, "FEATURE_COUNT": count,
            "CLASSIFICATION": assessment.classification,
            "CHANGED_AREA": assessment.changed_area,
            "ADDED_AREA": assessment.added_area,
            "REMOVED_AREA": assessment.removed_area,
        }


class ConsolidateMPYYAuditReportsAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "consolidate_mpyy_audit_reports"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return ConsolidateMPYYAuditReportsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "INPUT_DIRECTORY", 'Girdi klasörü',
            behavior=QgsProcessingParameterFile.Folder,
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.compliance_bundle import MPYYComplianceBundleEngine

        try:
            result = MPYYComplianceBundleEngine.consolidate(
                self.parameterAsFile(parameters, "INPUT_DIRECTORY", context),
                self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context),
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context),
            "STATUS": result["status"], "REPORT_COUNT": result["report_count"],
            "VERIFIED_REPORT_COUNT": result["verified_report_count"],
        }


class InitializeMPYYPlanDossierAlgorithm(LocalizedProcessingAlgorithm):
    LEVELS = ("MSP", "CDP", "NIP", "UIP")
    PURPOSES = ("NEW_PLAN", "REVISION", "ADDITION", "PLAN_CHANGE")
    LEVEL_LABELS = ("MSP", "ÇDP", "NİP", "UİP")
    PURPOSE_LABELS = ("Yeni plan", "Revizyon", "İlave plan", "Plan değişikliği")

    def name(self):
        return "initialize_mpyy_plan_dossier"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return InitializeMPYYPlanDossierAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            "PLAN_LEVEL", 'Plan kademesi', options=list(self.LEVEL_LABELS), defaultValue=3
        ))
        self.addParameter(QgsProcessingParameterEnum(
            "PURPOSE", 'Plan amacı', options=list(self.PURPOSE_LABELS), defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterFolderDestination(
            "OUTPUT_DIRECTORY", 'Çıktı klasörü'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.dossier_lifecycle import MPYYDossierScaffoldEngine

        try:
            result = MPYYDossierScaffoldEngine.create(
                self.parameterAsString(parameters, "OUTPUT_DIRECTORY", context),
                self.LEVELS[self.parameterAsEnum(parameters, "PLAN_LEVEL", context)],
                self.PURPOSES[self.parameterAsEnum(parameters, "PURPOSE", context)],
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_DIRECTORY": result["output_directory"],
            "MANIFEST": result["manifest"],
            "DIRECTORY_COUNT": result["directory_count"],
        }


class AuditMPYYDossierCompletenessAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_dossier_completeness"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYDossierCompletenessAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.dossier_lifecycle import (
            MPYYDossierCompletenessEngine, write_dossier_report,
        )

        try:
            result = MPYYDossierCompletenessEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context)
            )
            output = write_dossier_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYEvidenceFreshnessAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_evidence_freshness"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_evidence_change_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYEvidenceFreshnessAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterString(
            "AS_OF_DATE", 'Değerlendirme tarihi (YYYY-AA-GG)'
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.evidence_freshness import EvidenceFreshnessAuditEngine

        try:
            result = EvidenceFreshnessAuditEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context),
                self.parameterAsString(parameters, "AS_OF_DATE", context),
            )
            output = EvidenceFreshnessAuditEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "CURRENT_COUNT": result.current_count, "EXPIRED_COUNT": result.expired_count,
        }


class AuditMPYYMixedUseDetailsAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_mixed_use_details"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYMixedUseDetailsAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT", 'Çıktı katmanı'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mixed_use_audit import MPYYMixedUseAuditEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Plan kararı katmanı okunamadı.')
        fields = QgsFields(source.fields())
        fields.append(QgsField("mpyy_mix_status", QMetaType.Type.QString, len=24))
        fields.append(QgsField("effective_res_ratio", QMetaType.Type.Double, prec=6))
        fields.append(QgsField("mpyy_mix_findings", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Karma kullanım denetimi çıktısı oluşturulamadı.')
        counts = {"NON_COMPLIANT": 0, "REVIEW_REQUIRED": 0, "COMPLIANT": 0, "NOT_APPLICABLE": 0}
        count = 0
        for feature in source.getFeatures():
            record = {field.name(): feature[field.name()] for field in feature.fields()}
            result = MPYYMixedUseAuditEngine.audit(record)
            counts[result.status] += 1
            output = QgsFeature(fields)
            output.setAttributes(feature.attributes() + [
                result.status, result.effective_residential_ratio,
                ";".join(item.code for item in result.findings)[:254],
            ])
            output.setGeometry(feature.geometry())
            sink.addFeature(output)
            count += 1
        return {
            "OUTPUT": destination, "FEATURE_COUNT": count,
            "NON_COMPLIANT_COUNT": counts["NON_COMPLIANT"],
            "REVIEW_COUNT": counts["REVIEW_REQUIRED"],
        }


class AuditMPYYPublicationObjectionRegisterAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_publication_objection_register"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_plan_dossier_audits"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYPublicationObjectionRegisterAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası',
            behavior=QgsProcessingParameterFile.File, extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.dossier_lifecycle import MPYYPublicationRegisterEngine

        try:
            result = MPYYPublicationRegisterEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context)
            )
            output = MPYYPublicationRegisterEngine.write_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYParticipationRegisterAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_participation_register"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_administrative_integrity"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYParticipationRegisterAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.administrative_integrity import (
            MPYYParticipationRegisterEngine, audit_manifest_file,
            write_administrative_report,
        )

        try:
            result = audit_manifest_file(
                MPYYParticipationRegisterEngine,
                self.parameterAsFile(parameters, "MANIFEST", context),
            )
            output = write_administrative_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYCancelledPlanEvidenceAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_cancelled_plan_evidence"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_administrative_integrity"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYCancelledPlanEvidenceAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası',
            behavior=QgsProcessingParameterFile.File, extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.administrative_integrity import (
            MPYYCancelledPlanEvidenceEngine, audit_manifest_file,
            write_administrative_report,
        )

        try:
            result = audit_manifest_file(
                MPYYCancelledPlanEvidenceEngine,
                self.parameterAsFile(parameters, "MANIFEST", context),
            )
            output = write_administrative_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYPlanComponentConsistencyAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_plan_component_consistency"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_administrative_integrity"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYPlanComponentConsistencyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.administrative_integrity import (
            MPYYPlanComponentConsistencyEngine, audit_manifest_file,
            write_administrative_report,
        )

        try:
            result = audit_manifest_file(
                MPYYPlanComponentConsistencyEngine,
                self.parameterAsFile(parameters, "MANIFEST", context),
            )
            output = write_administrative_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYApprovalSheetRegisterAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_approval_sheet_register"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_administrative_integrity"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYApprovalSheetRegisterAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.administrative_integrity import (
            MPYYApprovalSheetRegisterEngine, audit_manifest_file,
            write_administrative_report,
        )

        try:
            result = audit_manifest_file(
                MPYYApprovalSheetRegisterEngine,
                self.parameterAsFile(parameters, "MANIFEST", context),
            )
            output = write_administrative_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYDigitalDeliveryPackageAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_digital_delivery_package"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_administrative_integrity"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYDigitalDeliveryPackageAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.administrative_integrity import (
            MPYYDigitalDeliveryEngine, write_administrative_report,
        )

        try:
            result = MPYYDigitalDeliveryEngine.audit_file(
                self.parameterAsFile(parameters, "MANIFEST", context)
            )
            output = write_administrative_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
        }


class AuditMPYYGeoPackageSchemaProfileAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_gpkg_schema_profile"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_digital_governance"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYGeoPackageSchemaProfileAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "GEOPACKAGE", 'GeoPackage dosyası', behavior=QgsProcessingParameterFile.File,
            extension="gpkg",
        ))
        self.addParameter(QgsProcessingParameterFile(
            "PROFILE", 'Kural / şema profili', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.digital_governance import (
            MPYYGeoPackageProfileEngine, write_governance_report,
        )

        try:
            result = MPYYGeoPackageProfileEngine.audit_files(
                self.parameterAsFile(parameters, "GEOPACKAGE", context),
                self.parameterAsFile(parameters, "PROFILE", context),
            )
            output = write_governance_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "WARNING_COUNT": result.warning_count,
            "CHECKED_TABLE_COUNT": result.details["checked_table_count"],
        }


class GenerateMPYYDossierInventoryAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "generate_mpyy_dossier_inventory"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_digital_governance"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return GenerateMPYYDossierInventoryAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "INPUT_DIRECTORY", 'Girdi klasörü', behavior=QgsProcessingParameterFile.Folder
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.digital_governance import MPYYDossierInventoryEngine

        try:
            result = MPYYDossierInventoryEngine.build(
                self.parameterAsFile(parameters, "INPUT_DIRECTORY", context),
                self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context),
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context),
            "STATUS": result.status, "FILE_COUNT": result.details["file_count"],
            "TOTAL_SIZE_BYTES": result.details["total_size_bytes"],
        }


class AuditMPYYPlanNoteDecisionLinksAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_plan_note_decision_links"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_digital_governance"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYPlanNoteDecisionLinksAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.digital_governance import (
            MPYYPlanNoteDecisionLinkEngine, audit_governance_manifest,
            write_governance_report,
        )

        try:
            result = audit_governance_manifest(
                MPYYPlanNoteDecisionLinkEngine,
                self.parameterAsFile(parameters, "MANIFEST", context),
            )
            output = write_governance_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count,
            "LINKED_DECISION_COUNT": result.details["linked_decision_count"],
        }


class AuditMPYYVersionChainAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "audit_mpyy_version_chain"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_digital_governance"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYVersionChainAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "MANIFEST", 'JSON içerik listesi dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.digital_governance import (
            MPYYVersionChainEngine, audit_governance_manifest, write_governance_report,
        )

        try:
            result = audit_governance_manifest(
                MPYYVersionChainEngine,
                self.parameterAsFile(parameters, "MANIFEST", context),
            )
            output = write_governance_report(
                result, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            )
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": output, "STATUS": result.status,
            "ERROR_COUNT": result.error_count, "VERSION_COUNT": result.details["version_count"],
            "HEAD_SHA256": result.details["head_sha256"],
        }


class AnalyzeMPYYMultimodalAccessibilityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "analyze_mpyy_multimodal_accessibility"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_accessibility"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeMPYYMultimodalAccessibilityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "NETWORK", 'Çizgi ağ katmanı', [QgsProcessing.SourceType.TypeVectorLine]
        ))
        for key, label, default in (
            ("MODE_FIELD", "Ulaşım türü alanı", "mode"),
            ("SPEED_FIELD", "Hız alanı", "speed_kmh"),
            ("TRAVEL_TIME_FIELD", "Açık yolculuk süresi alanı", "travel_time_min"),
            ("DIRECTION_FIELD", "Yön alanı", "direction"),
        ):
            self.addParameter(QgsProcessingParameterField(
                key, label, parentLayerParameterName="NETWORK", defaultValue=default
            ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "DEMAND", 'Talep nokta katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "FACILITIES", 'Tesis nokta katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        for key, label, default, minimum in (
            ("MAX_TIME_MIN", "En fazla yolculuk süresi (dakika)", 15.0, 0.001),
            ("WALK_SPEED_KMH", "Varsayılan yürüme hızı (km/sa)", 4.8, 0.001),
            ("BICYCLE_SPEED_KMH", "Varsayılan bisiklet hızı (km/sa)", 15.0, 0.001),
            ("TRANSIT_SPEED_KMH", "Varsayılan toplu taşıma hızı (km/sa)", 25.0, 0.001),
            ("TRANSFER_PENALTY_MIN", "Ulaşım türü aktarma cezası (dakika)", 3.0, 0.0),
        ):
            self.addParameter(QgsProcessingParameterNumber(
                key, label, QgsProcessingParameterNumber.Type.Double,
                defaultValue=default, minValue=minimum,
            ))
        self.addParameter(QgsProcessingParameterDistance(
            "SNAP_TOLERANCE", 'Yakalama toleransı (m)', defaultValue=1.0,
            minValue=0.001, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "MAX_SNAP_DISTANCE", 'Azami yakalama mesafesi (m)', defaultValue=50.0,
            minValue=0.0, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT", 'Çıktı katmanı'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.multimodal_accessibility import MPYYMultimodalAccessibilityEngine

        network = self.parameterAsSource(parameters, "NETWORK", context)
        demand = self.parameterAsSource(parameters, "DEMAND", context)
        facilities = self.parameterAsSource(parameters, "FACILITIES", context)
        if not network or not demand or not facilities:
            raise QgsProcessingException('Ağ, talep ve donatı katmanları gereklidir.')
        if network.sourceCrs().isGeographic():
            raise QgsProcessingException('Çok türlü erişilebilirlik için projeksiyonlu KRS gereklidir.')
        if demand.sourceCrs() != network.sourceCrs() or facilities.sourceCrs() != network.sourceCrs():
            raise QgsProcessingException("Tüm çok türlü erişilebilirlik katmanları aynı KRS'yi kullanmalıdır.")
        try:
            result = MPYYMultimodalAccessibilityEngine.analyze(
                network.getFeatures(), demand.getFeatures(), facilities.getFeatures(),
                self.parameterAsDouble(parameters, "MAX_TIME_MIN", context),
                self.parameterAsString(parameters, "MODE_FIELD", context),
                self.parameterAsString(parameters, "SPEED_FIELD", context),
                self.parameterAsString(parameters, "TRAVEL_TIME_FIELD", context),
                self.parameterAsString(parameters, "DIRECTION_FIELD", context),
                self.parameterAsDouble(parameters, "WALK_SPEED_KMH", context),
                self.parameterAsDouble(parameters, "BICYCLE_SPEED_KMH", context),
                self.parameterAsDouble(parameters, "TRANSIT_SPEED_KMH", context),
                self.parameterAsDouble(parameters, "TRANSFER_PENALTY_MIN", context),
                self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context),
                self.parameterAsDouble(parameters, "MAX_SNAP_DISTANCE", context),
                cancel_check=feedback.isCanceled,
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(demand.fields())
        fields.append(QgsField("access_status", QMetaType.Type.QString, len=20))
        fields.append(QgsField("route_time_min", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("facility_id", QMetaType.Type.QString, len=80))
        fields.append(QgsField("route_modes", QMetaType.Type.QString))
        fields.append(QgsField("snap_distance_m", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("articles", QMetaType.Type.QString, len=20))
        fields.append(QgsField("audit_notes", QMetaType.Type.QString, len=254))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, demand.wkbType(), demand.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Çok türlü erişilebilirlik çıktısı oluşturulamadı.')
        for record in result.records:
            output = QgsFeature(fields)
            output.setAttributes(record.feature.attributes() + [
                record.status, record.route_time_min, record.facility_id, record.modes,
                record.snap_distance_m, "MPYY 12, 21, 23-24", record.message,
            ])
            output.setGeometry(record.feature.geometry())
            sink.addFeature(output)
        return {
            "OUTPUT": destination, "FEATURE_COUNT": len(result.records),
            "ACCESSIBLE_COUNT": result.accessible_count,
            "INACCESSIBLE_COUNT": result.inaccessible_count,
            "UNREACHABLE_COUNT": result.unreachable_count,
            "UNSNAPPED_COUNT": result.unsnapped_count,
            "GRAPH_NODE_COUNT": result.graph_node_count,
            "GRAPH_EDGE_COUNT": result.graph_edge_count,
            "SKIPPED_EDGE_COUNT": result.skipped_edge_count,
        }


class CompareMPYYAccessibilityScenariosAlgorithm(AnalyzeMPYYMultimodalAccessibilityAlgorithm):
    def name(self) -> str:
        return "compare_mpyy_accessibility_scenarios"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return CompareMPYYAccessibilityScenariosAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        super().initAlgorithm(config)
        for key, label in (
            ("DEMAND", "Ortak talep nesneleri"),
            ("MAX_TIME_MIN", "Azami yolculuk süresi (dakika)"),
            ("WALK_SPEED_KMH", "Varsayılan yürüme hızı (km/sa)"),
            ("BICYCLE_SPEED_KMH", "Varsayılan bisiklet hızı (km/sa)"),
            ("TRANSIT_SPEED_KMH", "Varsayılan toplu taşıma hızı (km/sa)"),
            ("TRANSFER_PENALTY_MIN", "Ulaşım türü aktarma cezası (dakika)"),
        ):
            self.parameterDefinition(key).setDescription(label)
        for key in ("NETWORK", "FACILITIES", "MODE_FIELD", "SPEED_FIELD", "TRAVEL_TIME_FIELD",
                    "DIRECTION_FIELD", "SNAP_TOLERANCE", "MAX_SNAP_DISTANCE", "OUTPUT"):
            self.removeParameter(key)
        for key, label, geometry_type in (
            ("NETWORK_A", "Baseline network", QgsProcessing.SourceType.TypeVectorLine),
            ("NETWORK_B", 'Önerilen ağ', QgsProcessing.SourceType.TypeVectorLine),
            ("FACILITIES_A", "Baseline facilities", QgsProcessing.SourceType.TypeVectorAnyGeometry),
            ("FACILITIES_B", 'Önerilen tesisler', QgsProcessing.SourceType.TypeVectorAnyGeometry),
        ):
            self.addParameter(QgsProcessingParameterFeatureSource(key, label, [geometry_type]))
        for key, label, default in (
            ("MODE_FIELD", "Mode field in both networks", "mode"),
            ("SPEED_FIELD", "Optional speed field in both networks", "speed_kmh"),
            ("TRAVEL_TIME_FIELD", "Optional travel time field in both networks", "travel_time_min"),
            ("DIRECTION_FIELD", "Optional direction field in both networks", "direction"),
        ):
            self.addParameter(QgsProcessingParameterString(key, label, defaultValue=default))
        for key, label, default, minimum in (
            ("SNAP_TOLERANCE", "Network vertex snap tolerance (m)", 1.0, 0.001),
            ("MAX_SNAP_DISTANCE", "Maximum demand/facility snap distance (m)", 50.0, 0.0),
        ):
            self.addParameter(QgsProcessingParameterNumber(
                key, label, QgsProcessingParameterNumber.Type.Double, defaultValue=default, minValue=minimum
            ))
        self.addParameter(QgsProcessingParameterFeatureSink("OUTPUT", 'Çıktı katmanı'))

    def processAlgorithm(self, parameters, context, feedback):
        from qgis.core import Qgis
        from .core.accessibility_scenarios import MPYYAccessibilityScenarioEngine

        keys = ("NETWORK_A", "NETWORK_B", "DEMAND", "FACILITIES_A", "FACILITIES_B")
        sources = {key: self.parameterAsSource(parameters, key, context) for key in keys}
        if any(source is None for source in sources.values()):
            raise QgsProcessingException('Her iki ağ, her iki tesis grubu ve talep katmanı gereklidir.')
        crs = sources["NETWORK_A"].sourceCrs()
        if not crs.isValid() or crs.isGeographic() or crs.mapUnits() != Qgis.DistanceUnit.Meters:
            raise QgsProcessingException('Metre birimli geçerli bir projeksiyonlu koordinat sistemi gereklidir.')
        if any(source.sourceCrs() != crs for source in sources.values()):
            raise QgsProcessingException('Tüm senaryo katmanları aynı koordinat sistemini kullanmalıdır.')
        mode_field = self.parameterAsString(parameters, "MODE_FIELD", context)
        if any(source.fields().indexFromName(mode_field) < 0 for source in (
            sources["NETWORK_A"], sources["NETWORK_B"]
        )):
            raise QgsProcessingException('Belirtilen ulaşım türü alanı her iki ağda da bulunmalıdır.')
        options = {
            key.lower(): self.parameterAsString(parameters, key, context)
            for key in ("MODE_FIELD", "SPEED_FIELD", "TRAVEL_TIME_FIELD", "DIRECTION_FIELD")
        }
        options.update({
            key.lower(): self.parameterAsDouble(parameters, key, context)
            for key in ("WALK_SPEED_KMH", "BICYCLE_SPEED_KMH", "TRANSIT_SPEED_KMH", "TRANSFER_PENALTY_MIN")
        })
        options["snap_tolerance_m"] = self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context)
        options["maximum_snap_distance_m"] = self.parameterAsDouble(parameters, "MAX_SNAP_DISTANCE", context)
        if feedback.isCanceled():
            raise QgsProcessingException("Scenario comparison was canceled.")
        try:
            result = MPYYAccessibilityScenarioEngine.compare(
                sources["NETWORK_A"].getFeatures(), sources["NETWORK_B"].getFeatures(),
                sources["DEMAND"].getFeatures(), sources["FACILITIES_A"].getFeatures(),
                sources["FACILITIES_B"].getFeatures(),
                self.parameterAsDouble(parameters, "MAX_TIME_MIN", context),
                cancel_check=feedback.isCanceled, **options,
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields()
        fields.append(QgsField("demand_fid", QMetaType.Type.LongLong))
        for name in ("status_a", "status_b", "change", "facility_a", "facility_b", "modes_a", "modes_b"):
            fields.append(QgsField(name, QMetaType.Type.QString))
        for name in ("time_a_min", "time_b_min", "time_change_min", "snap_a_m", "snap_b_m"):
            fields.append(QgsField(name, QMetaType.Type.Double, prec=6))
        demand = sources["DEMAND"]
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, demand.wkbType(), crs
        )
        if sink is None:
            raise QgsProcessingException('Senaryo karşılaştırma çıktısı oluşturulamadı.')
        changes = {}
        for record in result.records:
            if feedback.isCanceled():
                raise QgsProcessingException("Scenario comparison was canceled.")
            first, second = record.baseline, record.proposed
            feature = QgsFeature(fields)
            feature.setGeometry(first.feature.geometry())
            feature.setAttributes([
                first.feature.id(), first.status, second.status, record.change,
                first.facility_id, second.facility_id, first.modes, second.modes,
                first.route_time_min, second.route_time_min, record.time_change_min,
                first.snap_distance_m, second.snap_distance_m,
            ])
            if not sink.addFeature(feature):
                raise QgsProcessingException("Could not write a scenario comparison feature.")
            changes[record.change] = changes.get(record.change, 0) + 1
        return {
            "OUTPUT": destination, "FEATURE_COUNT": len(result.records), "CHANGE_COUNTS": changes,
            "ACCESSIBLE_COUNT_A": result.baseline.accessible_count,
            "ACCESSIBLE_COUNT_B": result.proposed.accessible_count,
            "SKIPPED_EDGE_COUNT_A": result.baseline.skipped_edge_count,
            "SKIPPED_EDGE_COUNT_B": result.proposed.skipped_edge_count,
        }


class ImportMPYYGeoPackageSchemaProfileAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "import_mpyy_gpkg_schema_profile"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_digital_governance"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ImportMPYYGeoPackageSchemaProfileAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        for key, label, extension in (
            ("DICTIONARY", "Administration data dictionary", "csv"),
            ("MAPPING", "Column mapping and source metadata", "json"),
        ):
            self.addParameter(QgsProcessingParameterFile(
                key, label, behavior=QgsProcessingParameterFile.File, extension=extension
            ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_PROFILE", 'JSON şema profili çıktısı', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.schema_profile_import import MPYYSchemaProfileImportEngine

        try:
            source = self.parameterAsFile(parameters, "DICTIONARY", context)
            mapping = self.parameterAsFile(parameters, "MAPPING", context)
            output = self.parameterAsFileOutput(parameters, "OUTPUT_PROFILE", context)
            if Path(output).resolve() in {Path(source).resolve(), Path(mapping).resolve()}:
                raise ValueError('Çıktı profili sözlüğün veya eşleme dosyasının üzerine yazmamalıdır.')
            profile = MPYYSchemaProfileImportEngine.convert_files(source, mapping)
            destination = MPYYSchemaProfileImportEngine.write(profile, output)
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_PROFILE": destination, "TABLE_COUNT": len(profile["tables"]),
            "FIELD_COUNT": sum(len(table["fields"]) for table in profile["tables"]),
            "CONTENT_SHA256": profile["content_sha256"],
        }


class AuditMPYYSchemaProfileIdentityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_mpyy_schema_profile_identity"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "mpyy_digital_governance"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditMPYYSchemaProfileIdentityAlgorithm()

    def initAlgorithm(self, config=None) -> None:
        self.addParameter(QgsProcessingParameterFile(
            "PROFILE", 'Kural / şema profili', behavior=QgsProcessingParameterFile.File, extension="json"
        ))
        self.addParameter(QgsProcessingParameterFile(
            "DICTIONARY", 'Kaynak CSV sözlüğü (isteğe bağlı)', behavior=QgsProcessingParameterFile.File,
            extension="csv", optional=True,
        ))
        self.addParameter(QgsProcessingParameterString(
            "EXPECTED_SHA256", 'Bağımsız SHA-256 özeti (isteğe bağlı)', optional=True
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            "OUTPUT_REPORT", 'JSON rapor dosyası', 'JSON (*.json)'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.digital_governance import write_governance_report
        from .core.profile_identity import MPYYProfileIdentityEngine

        try:
            profile = self.parameterAsFile(parameters, "PROFILE", context)
            source = self.parameterAsFile(parameters, "DICTIONARY", context) or None
            output = self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
            inputs = {Path(profile).resolve()}
            if source is not None:
                inputs.add(Path(source).resolve())
            if Path(output).resolve() in inputs:
                raise ValueError('Kimlik raporu profilin veya sözlüğün üzerine yazmamalıdır.')
            result = MPYYProfileIdentityEngine.audit_files(
                profile, source, self.parameterAsString(parameters, "EXPECTED_SHA256", context)
            )
            destination = write_governance_report(result, output)
        except (OSError, ValueError) as error:
            raise QgsProcessingException(str(error)) from error
        return {
            "OUTPUT_REPORT": destination, "STATUS": result.status, "ERROR_COUNT": result.error_count,
            "COMPUTED_SHA256": result.details["computed_content_sha256"],
        }


class AnalyzeMPYYBuildingMorphologyAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "analyze_mpyy_building_morphology"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_urban_analytics"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeMPYYBuildingMorphologyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "BUILDINGS", 'Yapı poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT", 'Çıktı katmanı'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mpyy_urban_analytics import MPYYBuildingMorphologyEngine

        source = self.parameterAsSource(parameters, "BUILDINGS", context)
        if not source:
            raise QgsProcessingException('Yapı katmanı okunamadı.')
        if source.sourceCrs().isGeographic():
            raise QgsProcessingException('Yapı morfolojisi için projeksiyonlu KRS gereklidir.')
        records = MPYYBuildingMorphologyEngine.analyze(source.getFeatures())
        fields = QgsFields(source.fields())
        for name in (
            "alan_m2", "cevre_m", "kompaktlik", "disbukeylik",
            "dikdortgenlik", "uzama", "yonelim_derece", "ortak_duvar_orani",
        ):
            fields.append(QgsField(name, QMetaType.Type.Double, prec=6))
        fields.append(QgsField("analiz_durumu", QMetaType.Type.QString, len=24))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, source.wkbType(), source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Yapı morfolojisi çıktısı oluşturulamadı.')
        for record in records:
            output = QgsFeature(fields)
            output.setGeometry(record.feature.geometry())
            output.setAttributes(record.feature.attributes() + [
                record.area_m2, record.perimeter_m, record.compactness,
                record.convexity, record.rectangularity, record.elongation,
                record.orientation_deg, record.shared_wall_ratio, record.status,
            ])
            sink.addFeature(output)
        return {"OUTPUT": destination, "FEATURE_COUNT": len(records)}


class AnalyzeMPYYSpacematrixDensityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "analyze_mpyy_spacematrix_density"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_urban_analytics"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeMPYYSpacematrixDensityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "BUILDINGS", 'Yapı poligonları', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterField(
            "LEVELS_FIELD", 'Kat sayısı alanı (isteğe bağlı)',
            parentLayerParameterName="BUILDINGS", optional=True,
            type=QgsProcessingParameterField.DataType.Numeric,
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "DEFAULT_LEVELS", 'Default levels',
            QgsProcessingParameterNumber.Type.Double, defaultValue=2.0, minValue=0.0,
        ))
        self.addParameter(QgsProcessingParameterFeatureSource(
            "BLOCKS", 'Çalışma ada poligonları (isteğe bağlı)', [QgsProcessing.SourceType.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT", 'Çıktı katmanı'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mpyy_urban_analytics import MPYYSpacematrixEngine

        buildings = self.parameterAsSource(parameters, "BUILDINGS", context)
        blocks = self.parameterAsSource(parameters, "BLOCKS", context)
        if not buildings or not blocks:
            raise QgsProcessingException('Yapı ve analiz birimi katmanları gereklidir.')
        if blocks.sourceCrs().isGeographic() or buildings.sourceCrs() != blocks.sourceCrs():
            raise QgsProcessingException("Katmanlar aynı projeksiyonlu KRS'yi kullanmalıdır.")
        try:
            records = MPYYSpacematrixEngine.analyze(
                buildings.getFeatures(), blocks.getFeatures(),
                self.parameterAsString(parameters, "LEVELS_FIELD", context),
                self.parameterAsDouble(parameters, "DEFAULT_LEVELS", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields(blocks.fields())
        fields.append(QgsField("yapi_sayisi", QMetaType.Type.Int))
        for name in (
            "taban_alani_m2", "kat_alani_m2", "gsi", "fsi", "osr", "ortalama_kat",
        ):
            fields.append(QgsField(name, QMetaType.Type.Double, prec=6))
        fields.append(QgsField("analiz_durumu", QMetaType.Type.QString, len=24))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, blocks.wkbType(), blocks.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException('Mekân matrisi çıktısı oluşturulamadı.')
        for record in records:
            output = QgsFeature(fields)
            output.setGeometry(record.feature.geometry())
            output.setAttributes(record.feature.attributes() + [
                record.building_count, record.footprint_m2, record.floor_area_m2,
                record.gsi, record.fsi, record.osr, record.mean_levels, record.status,
            ])
            sink.addFeature(output)
        return {"OUTPUT": destination, "FEATURE_COUNT": len(records)}


class AnalyzeMPYYStreetMorphologyAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "analyze_mpyy_street_network_morphology"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_urban_analytics"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeMPYYStreetMorphologyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "NETWORK", 'Çizgi ağ katmanı', [QgsProcessing.SourceType.TypeVectorLine]
        ))
        self.addParameter(QgsProcessingParameterDistance(
            "SNAP_TOLERANCE", 'Yakalama toleransı (m)', defaultValue=1.0,
            minValue=0.001, parentParameterName="NETWORK",
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "ORIENTATION_BINS", 'Yönlenme histogramı sınıf sayısı',
            QgsProcessingParameterNumber.Type.Integer, defaultValue=36, minValue=8, maxValue=180,
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT", 'Çıktı katmanı'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mpyy_urban_analytics import MPYYStreetMorphologyEngine

        source = self.parameterAsSource(parameters, "NETWORK", context)
        if not source:
            raise QgsProcessingException('Yol ağı okunamadı.')
        if source.sourceCrs().isGeographic():
            raise QgsProcessingException('Yol ağı morfolojisi için projeksiyonlu KRS gereklidir.')
        try:
            result = MPYYStreetMorphologyEngine.analyze(
                source.getFeatures(),
                self.parameterAsDouble(parameters, "SNAP_TOLERANCE", context),
                self.parameterAsInt(parameters, "ORIENTATION_BINS", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        fields = QgsFields()
        for name in ("dugum", "baglanti", "bilesen", "cikmaz", "kavsak"):
            fields.append(QgsField(name, QMetaType.Type.Int))
        for name in (
            "toplam_uzunluk_m", "ort_segment_m", "yonelim_entropi",
            "yonelim_duzeni", "alfa", "beta", "gama",
        ):
            fields.append(QgsField(name, QMetaType.Type.Double, prec=6))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, QgsWkbTypes.Type.NoGeometry,
            QgsCoordinateReferenceSystem(),
        )
        if sink is None:
            raise QgsProcessingException('Yol ağı özeti oluşturulamadı.')
        output = QgsFeature(fields)
        output.setAttributes([
            result.node_count, result.edge_count, result.component_count,
            result.dead_end_count, result.intersection_count, result.total_length_m,
            result.mean_segment_length_m, result.orientation_entropy,
            result.orientation_order, result.alpha, result.beta, result.gamma,
        ])
        sink.addFeature(output)
        return {"OUTPUT": destination, "NODE_COUNT": result.node_count, "EDGE_COUNT": result.edge_count}


class CompareMPYYPlanScenariosAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "compare_mpyy_plan_scenarios"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_urban_analytics"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return CompareMPYYPlanScenariosAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            "SCENARIO_A", 'Başlangıç senaryosu JSON dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFile(
            "SCENARIO_B", 'Önerilen senaryo JSON dosyası', behavior=QgsProcessingParameterFile.File,
            extension="json",
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT", 'Çıktı katmanı'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mpyy_urban_analytics import MPYYScenarioComparisonEngine

        try:
            rows = MPYYScenarioComparisonEngine.read_and_compare(
                self.parameterAsFile(parameters, "SCENARIO_A", context),
                self.parameterAsFile(parameters, "SCENARIO_B", context),
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        if not rows:
            raise QgsProcessingException('Karşılaştırılabilir gösterge bulunamadı.')
        fields = QgsFields()
        fields.append(QgsField("gosterge", QMetaType.Type.QString, len=120))
        fields.append(QgsField("gosterge_kodu", QMetaType.Type.QString, len=80))
        for name in ("senaryo_a", "senaryo_b", "fark", "fark_orani"):
            fields.append(QgsField(name, QMetaType.Type.Double, prec=6))
        fields.append(QgsField("tercih_yonu", QMetaType.Type.QString, len=120))
        sink, destination = self.parameterAsSink(
            parameters, "OUTPUT", context, fields, QgsWkbTypes.Type.NoGeometry,
            QgsCoordinateReferenceSystem(),
        )
        if sink is None:
            raise QgsProcessingException('Senaryo karşılaştırma tablosu oluşturulamadı.')
        for row in rows:
            output = QgsFeature(fields)
            output.setAttributes([
                row["label"], row["key"], row["value_a"], row["value_b"],
                row["delta"], row["delta_ratio"], row["preferred"],
            ])
            sink.addFeature(output)
        return {"OUTPUT": destination, "METRIC_COUNT": len(rows)}


class AnalyzeMPYYAccessibilityEquityAlgorithm(LocalizedProcessingAlgorithm):
    def name(self):
        return "analyze_mpyy_accessibility_equity"

    def displayName(self):
        return tool_text(self, 'title')

    def group(self):
        return tool_text(self, 'category')

    def groupId(self):
        return "mpyy_urban_analytics"

    def shortHelpString(self):
        return tool_text(self, 'help')

    def createInstance(self):
        return AnalyzeMPYYAccessibilityEquityAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            "INPUT", 'Girdi katmanı', [QgsProcessing.SourceType.TypeVectorAnyGeometry]
        ))
        self.addParameter(QgsProcessingParameterField(
            "VALUE_FIELD", 'Erişilebilirlik değeri alanı', parentLayerParameterName="INPUT",
            type=QgsProcessingParameterField.DataType.Numeric,
        ))
        self.addParameter(QgsProcessingParameterField(
            "WEIGHT_FIELD", 'Nüfus / ağırlık alanı (isteğe bağlı)', parentLayerParameterName="INPUT",
            optional=True, type=QgsProcessingParameterField.DataType.Numeric,
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "USE_THRESHOLD", 'Belirtilen erişim eşiğini uygula', defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterNumber(
            "THRESHOLD", 'Erişim eşiği', QgsProcessingParameterNumber.Type.Double,
            defaultValue=0.0,
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            "HIGHER_IS_BETTER", 'Yüksek değerler daha iyi erişimi gösterir', defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT_UNITS", 'Çalışma birimi başına eşitlik sonuçları'
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            "OUTPUT_SUMMARY", 'Eşitlik özeti tablosu'
        ))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.mpyy_urban_analytics import MPYYAccessEquityEngine

        source = self.parameterAsSource(parameters, "INPUT", context)
        if not source:
            raise QgsProcessingException('Erişilebilirlik katmanı okunamadı.')
        value_field = self.parameterAsString(parameters, "VALUE_FIELD", context)
        weight_field = self.parameterAsString(parameters, "WEIGHT_FIELD", context)
        features = []
        values = []
        weights = []
        for feature in source.getFeatures():
            try:
                value = float(feature[value_field])
                weight = float(feature[weight_field]) if weight_field else 1.0
            except (KeyError, TypeError, ValueError):
                continue
            if math.isfinite(value) and math.isfinite(weight) and weight > 0:
                features.append(feature)
                values.append(value)
                weights.append(weight)
        threshold = (
            self.parameterAsDouble(parameters, "THRESHOLD", context)
            if self.parameterAsBool(parameters, "USE_THRESHOLD", context) else None
        )
        higher_is_better = self.parameterAsBool(parameters, "HIGHER_IS_BETTER", context)
        try:
            result = MPYYAccessEquityEngine.analyze(
                values, weights, threshold, higher_is_better
            )
        except ValueError as error:
            raise QgsProcessingException(str(error)) from error
        unit_fields = QgsFields(source.fields())
        unit_fields.append(QgsField("esitlik_degeri", QMetaType.Type.Double, prec=6))
        unit_fields.append(QgsField("nufus_agirligi", QMetaType.Type.Double, prec=3))
        unit_fields.append(QgsField("esik_yoksun", QMetaType.Type.Int))
        unit_sink, unit_destination = self.parameterAsSink(
            parameters, "OUTPUT_UNITS", context, unit_fields, source.wkbType(), source.sourceCrs()
        )
        if unit_sink is None:
            raise QgsProcessingException('Erişilebilirlik birimleri çıktısı oluşturulamadı.')
        for feature, value, weight in zip(features, values, weights):
            poor = 0
            if threshold is not None:
                poor = int(value < threshold if higher_is_better else value > threshold)
            output = QgsFeature(unit_fields)
            output.setGeometry(feature.geometry())
            output.setAttributes(feature.attributes() + [value, weight, poor])
            unit_sink.addFeature(output)
        summary_fields = QgsFields()
        summary_fields.append(QgsField("birim_sayisi", QMetaType.Type.Int))
        for name in (
            "nufus", "agirlikli_ortalama", "agirlikli_medyan", "gini",
            "degisim_katsayisi", "p90_p10", "esik_payi",
        ):
            summary_fields.append(QgsField(name, QMetaType.Type.Double, prec=6))
        summary_sink, summary_destination = self.parameterAsSink(
            parameters, "OUTPUT_SUMMARY", context, summary_fields,
            QgsWkbTypes.Type.NoGeometry, QgsCoordinateReferenceSystem(),
        )
        if summary_sink is None:
            raise QgsProcessingException('Eşitlik özeti oluşturulamadı.')
        summary = QgsFeature(summary_fields)
        summary.setAttributes([
            result.unit_count, result.population, result.weighted_mean,
            result.weighted_median, result.gini, result.coefficient_of_variation,
            result.p90_p10, result.threshold_share,
        ])
        summary_sink.addFeature(summary)
        return {
            "OUTPUT_UNITS": unit_destination, "OUTPUT_SUMMARY": summary_destination,
            "UNIT_COUNT": result.unit_count, "GINI": result.gini,
        }


class ImportCadToPlanGMLAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "import_cad_to_plangml"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "workspace"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ImportCadToPlanGMLAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource("INPUT", "Girdi katmanı", [QgsProcessing.SourceType.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterField("TABAKA_FIELD", "Tabaka alanı", "Layer", "INPUT"))
        self.addParameter(QgsProcessingParameterFile("WORKSPACE", "PlanGML çalışma alanı", extension="gpkg"))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT_REPORT", "Aktarım raporu", "CSV (*.csv)", optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plangml_import import import_cad_layer, write_csv

        source = self.parameterAsVectorLayer(parameters, "INPUT", context)
        if source is None:
            raise QgsProcessingException('Kaynak katman okunamadı.')
        field = self.parameterAsString(parameters, "TABAKA_FIELD", context)
        workspace = self.parameterAsFile(parameters, "WORKSPACE", context)
        try:
            report = import_cad_layer(source, field, workspace, feedback, context.project())
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        written = sum(r["aktarilan"] for r in report)
        for row in report:
            if row["durum"] != "aktarıldı":
                feedback.pushWarning(f'{row["tabaka"]} ({row["adet"]}): {row["durum"]}')
        feedback.pushInfo(f'{written} nesne PlanGML tablolarına yazıldı; {sum(1 for r in report if r["aktarilan"])} tabaka eşleşti.')
        result = {"WRITTEN": written}
        path = self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
        if path:
            result["OUTPUT_REPORT"] = write_csv(report, path, list(report[0].keys()) if report else ["tabaka"])
        return result


class AuditPlanGMLWorkspaceAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "audit_plangml_workspace"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "workspace"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return AuditPlanGMLWorkspaceAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile("WORKSPACE", "PlanGML çalışma alanı", extension="gpkg"))
        self.addParameter(QgsProcessingParameterEnum("PLAN_LEVEL", "Plan kademesi", options=["Dosyadan oku", "UIP", "NIP", "CDP"], defaultValue=0))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT_REPORT", "Denetim raporu", "CSV (*.csv)"))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plangml_import import audit_plangml_workspace, write_csv

        workspace = self.parameterAsFile(parameters, "WORKSPACE", context)
        level = [None, "UIP", "NIP", "CDP"][self.parameterAsEnum(parameters, "PLAN_LEVEL", context)]
        try:
            findings = audit_plangml_workspace(workspace, level)
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        counts = {}
        for row in findings:
            counts[row["sorun"]] = counts.get(row["sorun"], 0) + 1
        for problem, count in sorted(counts.items()):
            feedback.pushWarning(f"{problem}: {count}")
        if not findings:
            feedback.pushInfo('PlanGML şemasına aykırı bulgu yok.')
        path = write_csv(findings, self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context), ["katman", "fid", "sorun", "ayrinti"])
        return {"OUTPUT_REPORT": path, "FINDINGS": len(findings)}


class ConvertPlanGMLLevelAlgorithm(LocalizedProcessingAlgorithm):
    def name(self) -> str:
        return "convert_plangml_level"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "workspace"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ConvertPlanGMLLevelAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile("WORKSPACE", "PlanGML çalışma alanı", extension="gpkg"))
        self.addParameter(QgsProcessingParameterEnum("TARGET_LEVEL", "Hedef kademe", options=["NIP", "CDP"], defaultValue=0))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT", "Çıktı katmanı", "GeoPackage (*.gpkg)"))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT_REPORT", "Dönüşüm raporu", "CSV (*.csv)", optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plangml_import import write_csv
        from .core.plangml_level_conversion import convert_workspace

        source = self.parameterAsFile(parameters, "WORKSPACE", context)
        target_level = ["NIP", "CDP"][self.parameterAsEnum(parameters, "TARGET_LEVEL", context)]
        output = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        try:
            path, report = convert_workspace(source, output, target_level, feedback)
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        for row in report:
            if row["aktarilan"] < row["adet"] or row["doldurulacak"]:
                feedback.pushWarning(f'{row["kaynak"]} ({row["adet"]}): {row["durum"]}')
        feedback.pushInfo(f'{sum(r["aktarilan"] for r in report)} nesne {target_level} çalışma alanına aktarıldı.')
        result = {"OUTPUT": path}
        report_path = self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
        if report_path and report:
            result["OUTPUT_REPORT"] = write_csv(report, report_path, list(report[0].keys()))
        return result


class ImportPlanGMLFileAlgorithm(LocalizedProcessingAlgorithm):
    LEVELS = [None, "MUIP", "MNIP", "MCDP25", "MCDP100", "UIP", "NIP", "CDP"]

    def name(self) -> str:
        return "import_plangml_gml"

    def displayName(self) -> str:
        return tool_text(self, 'title')

    def group(self) -> str:
        return tool_text(self, 'category')

    def groupId(self) -> str:
        return "workspace"

    def shortHelpString(self) -> str:
        return tool_text(self, 'help')

    def createInstance(self):
        return ImportPlanGMLFileAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile("GML_FILE", "PlanGML GML dosyası", fileFilter="GML (*.gml *.xml)"))
        self.addParameter(QgsProcessingParameterEnum("GML_SCHEMA", "Şema", options=["Otomatik", "MUIP", "MNIP", "MCDP25", "MCDP100", "UIP", "NIP", "CDP"], defaultValue=0))
        self.addParameter(QgsProcessingParameterCrs("KRS", "Koordinat sistemi", optional=True))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT", "Çıktı katmanı", "GeoPackage (*.gpkg)"))
        self.addParameter(QgsProcessingParameterFileDestination("OUTPUT_REPORT", "İçe aktarma raporu", "CSV (*.csv)", optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        from .core.plangml_gml import import_plangml_gml
        from .core.plangml_import import write_csv

        path = self.parameterAsFile(parameters, "GML_FILE", context)
        level = self.LEVELS[self.parameterAsEnum(parameters, "GML_SCHEMA", context)]
        crs = self.parameterAsCrs(parameters, "KRS", context)
        output = self.parameterAsFileOutput(parameters, "OUTPUT", context)
        try:
            result, summary, report = import_plangml_gml(path, output, level, crs if crs.isValid() else None, feedback, context.project())
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
            raise QgsProcessingException(str(error)) from error
        feedback.pushInfo(f'Şema: {summary["sema"]} ({summary["belirleme"]}).')
        for row in report:
            if row["aktarilan"] < row["adet"] or row["kod_listesi_disi"] or row["bilinmeyen_oznitelik"]:
                feedback.pushWarning(f'{row["tip"]} ({row["adet"]}): aktarılan {row["aktarilan"]}; {row["ornek_sorun"] or row["bilinmeyen_oznitelik"]}')
        if summary["bilinmeyen_ogeler"]:
            feedback.pushWarning('Şemada olmayan öğeler: ' + ", ".join(f"{k} ({v})" for k, v in summary["bilinmeyen_ogeler"].items()))
        feedback.pushInfo(f'{sum(r["aktarilan"] for r in report)} nesne aktarıldı.')
        out = {"OUTPUT": result}
        report_path = self.parameterAsFileOutput(parameters, "OUTPUT_REPORT", context)
        if report_path and report:
            out["OUTPUT_REPORT"] = write_csv(report, report_path, list(report[0].keys()))
        return out


class MPYYProvider(QgsProcessingProvider):
    def id(self) -> str:
        return "planx_mpyy_studio"

    def name(self) -> str:
        return "PlanX MPYY Studio"

    def longName(self) -> str:
        return self.name()

    def icon(self):
        icon_path = Path(__file__).parent / "icons" / "icon.png"
        return QtGui.QIcon(str(icon_path)) if icon_path.exists() else QtGui.QIcon()

    def loadAlgorithms(self) -> None:
        self.addAlgorithm(CreateLandUseWorkspace())
        self.addAlgorithm(IngestVectorDatasetAlgorithm())
        self.addAlgorithm(ImportCadToPlanGMLAlgorithm())
        self.addAlgorithm(AuditPlanGMLWorkspaceAlgorithm())
        self.addAlgorithm(ConvertPlanGMLLevelAlgorithm())
        self.addAlgorithm(ImportPlanGMLFileAlgorithm())
        self.addAlgorithm(CalculateBuildingEnvelopeAlgorithm())
        self.addAlgorithm(ExecuteCrosswalkAlgorithm())
        self.addAlgorithm(SynthesizeParcelDensityAlgorithm())
        self.addAlgorithm(ValidateQualityControlAlgorithm())
        self.addAlgorithm(PackageForQFieldAlgorithm())
        self.addAlgorithm(CleanPlanningGeometriesAlgorithm())
        self.addAlgorithm(ExportPlanningReportAlgorithm())
        self.addAlgorithm(AnalyzeAmenityStandardsAlgorithm())
        self.addAlgorithm(EvaluatePlanRevisionAlgorithm())
        self.addAlgorithm(CalculateDOPAlgorithm())
        self.addAlgorithm(EstimatePlanCapacityAlgorithm())
        self.addAlgorithm(ValidatePAIYComplianceAlgorithm())
        self.addAlgorithm(GeneratePaftaGridAlgorithm())
        self.addAlgorithm(GeneratePlanNotesAlgorithm())
        self.addAlgorithm(GenerateComprehensiveReportAlgorithm())
        self.addAlgorithm(ApplyCornerChamferAlgorithm())
        self.addAlgorithm(GeneratePrintLayoutAlgorithm())
        self.addAlgorithm(CalculateParkingRequirementAlgorithm())
        self.addAlgorithm(PrioritizeUrbanTransformationAlgorithm())
        self.addAlgorithm(GenerateZoningCertificateAlgorithm())
        self.addAlgorithm(CalculateShelterRequirementAlgorithm())
        self.addAlgorithm(GenerateLandReadjustmentMatrixAlgorithm())
        self.addAlgorithm(EvaluateTransformationFeasibilityAlgorithm())
        self.addAlgorithm(OptimizeParcelSubdivisionAlgorithm())
        self.addAlgorithm(ExportOfficialZoningAtlasAlgorithm())
        self.addAlgorithm(ExportOfficialZoningAtlasBatchAlgorithm())
        self.addAlgorithm(GenerateProcedural3DMassingAlgorithm())
        self.addAlgorithm(AuditMunicipalBylawComplianceAlgorithm())
        self.addAlgorithm(PreviewWorkspaceReconciliationAlgorithm())
        self.addAlgorithm(ReconcileWorkspaceVersionsAlgorithm())
        self.addAlgorithm(AuditMSPPlanRequirementsAlgorithm())
        self.addAlgorithm(AuditCDPPlanRequirementsAlgorithm())
        self.addAlgorithm(AuditNIPPlanRequirementsAlgorithm())
        self.addAlgorithm(AuditUIPPlanRequirementsAlgorithm())
        self.addAlgorithm(AuditPlanHierarchyConsistencyAlgorithm())
        self.addAlgorithm(AuditPlanSubmissionDossierAlgorithm())
        self.addAlgorithm(ScreenMPYYThresholdConstraintsAlgorithm())
        self.addAlgorithm(AuditMPYYRoadPlanChangeAlgorithm())
        self.addAlgorithm(AuditMPYYDensityHeightChangeAlgorithm())
        self.addAlgorithm(EvaluateMSPActionMonitoringAlgorithm())
        self.addAlgorithm(ClassifyCDPRevisionScopeAlgorithm())
        self.addAlgorithm(AuditNIPUIPActiveMobilityNetworkAlgorithm())
        self.addAlgorithm(AuditMPYYEvidenceProvenanceAlgorithm())
        self.addAlgorithm(AuditInstitutionOpinionRegisterAlgorithm())
        self.addAlgorithm(AnalyzeNIPUIPRoutedAccessibilityAlgorithm())
        self.addAlgorithm(AuditAdjacentPlanBoundaryConsistencyAlgorithm())
        self.addAlgorithm(AuditPlanFabricTopologyAlgorithm())
        self.addAlgorithm(AuditMPYYPlanReportContentAlgorithm())
        self.addAlgorithm(AuditMPYYArticle12WalkingDistancesAlgorithm())
        self.addAlgorithm(AuditConservationPlanDossierAlgorithm())
        self.addAlgorithm(AuditIntegratedCoastalPlanDossierAlgorithm())
        self.addAlgorithm(AuditUrbanDesignProjectPrerequisitesAlgorithm())
        self.addAlgorithm(AuditMPYYArticle8ResearchDossierAlgorithm())
        self.addAlgorithm(AuditMPYYArticle10OfficialLegendAlgorithm())
        self.addAlgorithm(AuditMPYYArticle11StandardsContextAlgorithm())
        self.addAlgorithm(ClassifyMPYYArticle25PlanInterventionAlgorithm())
        self.addAlgorithm(ConsolidateMPYYAuditReportsAlgorithm())
        self.addAlgorithm(InitializeMPYYPlanDossierAlgorithm())
        self.addAlgorithm(AuditMPYYDossierCompletenessAlgorithm())
        self.addAlgorithm(AuditMPYYEvidenceFreshnessAlgorithm())
        self.addAlgorithm(AuditMPYYMixedUseDetailsAlgorithm())
        self.addAlgorithm(AuditMPYYPublicationObjectionRegisterAlgorithm())
        self.addAlgorithm(AuditMPYYParticipationRegisterAlgorithm())
        self.addAlgorithm(AuditMPYYCancelledPlanEvidenceAlgorithm())
        self.addAlgorithm(AuditMPYYPlanComponentConsistencyAlgorithm())
        self.addAlgorithm(AuditMPYYApprovalSheetRegisterAlgorithm())
        self.addAlgorithm(AuditMPYYDigitalDeliveryPackageAlgorithm())
        self.addAlgorithm(AuditMPYYGeoPackageSchemaProfileAlgorithm())
        self.addAlgorithm(GenerateMPYYDossierInventoryAlgorithm())
        self.addAlgorithm(AuditMPYYPlanNoteDecisionLinksAlgorithm())
        self.addAlgorithm(AuditMPYYVersionChainAlgorithm())
        self.addAlgorithm(AnalyzeMPYYMultimodalAccessibilityAlgorithm())
        self.addAlgorithm(AnalyzeMPYYBuildingMorphologyAlgorithm())
        self.addAlgorithm(AnalyzeMPYYSpacematrixDensityAlgorithm())
        self.addAlgorithm(AnalyzeMPYYStreetMorphologyAlgorithm())
        self.addAlgorithm(CompareMPYYPlanScenariosAlgorithm())
        self.addAlgorithm(AnalyzeMPYYAccessibilityEquityAlgorithm())
        self.addAlgorithm(CompareMPYYAccessibilityScenariosAlgorithm())
        self.addAlgorithm(ImportMPYYGeoPackageSchemaProfileAlgorithm())
        self.addAlgorithm(AuditMPYYSchemaProfileIdentityAlgorithm())
