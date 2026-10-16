"""Existing workspace, styling and analysis callbacks, separate from view construction."""

from ..core.localization import display_label, add_localized_layer
import sqlite3
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsProject,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType
from qgis.PyQt.QtWidgets import QFileDialog

from ..core.allocation_engine import AllocationEngine
from ..core.capacity_engine import PlanCapacityEngine
from ..core.chamfer_engine import ChamferEngine
from ..core.compliance_engine import ComplianceEngine
from ..core.crosswalk import execute_layer_crosswalk
from ..core.db_factory import create_land_use_workspace
from ..core.local_nip_workspace import create_local_nip_workspace
from ..core.local_uip_workspace import create_local_uip_workspace
from ..core.mpyy_workspace import create_mpyy_workspace
from ..core.msp_workspace import create_msp_workspace
from ..core.dop_engine import DOPEngine
from ..core.form_designer import MPYYFormDesigner
from ..core.layout_composer import MPYYLayoutComposer
from ..core.pafta_index import PaftaGridEngine
from ..core.parking_engine import ParkingEngine
from ..core.plan_diff import PlanRevisionDiffEngine
from ..core.plan_notes import PlanNotesEngine
from ..core.project_binding import apply_layer_style_and_form, load_project_layers
from ..core.qc_engine import QualityControlEngine
from ..core.report_exporter import PlanReportEngine
from ..core.risk_engine import UrbanTransformationRiskEngine
from ..core.shelter_engine import ShelterEngine
from ..core.synthesis import SynthesisEngine
from ..core.feasibility_engine import UrbanTransformationFeasibilityEngine
from ..core.zoning_certificate import ZoningCertificateEngine


#: Fields a target layer may carry a UİP/ÇDP/NİP classification in, most
#: specific first: the local MpyyUipDb form writes the function *name* into
#: ``uipfonksiyon``, coded layers carry ``fonksiyon_kodu``, and ``catalog_id``
#: is geometry + source FID, which keeps every catalogue row addressable.
STYLE_FIELDS = ("uipfonksiyon", "fonksiyon_kodu", "fonksiyon_adi", "catalog_id")

#: The same, for an MSP layer: the annex's own ``msp_kodu`` comes first, and the
#: e-Plan function fields are the fallbacks so a converted layer still styles.
MSP_FIELDS = ("msp_kodu",) + STYLE_FIELDS


class DockActionsMixin:
    def _styling_field(self, layer, candidates=STYLE_FIELDS):
        """The field the chosen profile classifies on.

        Raises ``ValueError`` naming the candidates when the layer carries none
        of them: the caller's ``except`` turns that into one status line, which
        is more use to a planner than an empty render.
        """

        for name in candidates:
            if layer.fields().indexFromName(name) >= 0:
                return name
        raise ValueError(
            'Katmanda ' + ", ".join(candidates[:-1]) + ' veya ' + candidates[-1]
            + ' alanı bulunamadı.'
        )


    def draw_plan_function(self):
        """Open the chosen function's MPYY layer with its values as defaults and start drawing."""
        from ..core.function_picker import activate, plan_functions

        record_id = self.fn_choice.currentData()
        chosen = next((f for f in plan_functions(self.fn_level.currentData()) if f.record_id == record_id), None)
        if chosen is None:
            self.status.setText('Listeden bir plan fonksiyonu seçin.')
            return None
        try:
            layer = activate(chosen, iface=self.iface)
        except LookupError as error:
            self.status.setText(f'{error} Önce bu kademede bir MPYY çalışma alanı açın.')
            return None
        self.status.setText(f'{chosen.name}: {chosen.describe()} çizmeye hazır; '
                            f'"{layer.name()}" katmanında yeni nesneler bu değerlerle gelir.')
        return layer

    def create_workspace(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Plan çalışma alanı oluştur', "", "GeoPackage (*.gpkg)")
        if not path:
            return
        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"
        try:
            scope = self.scope.currentData()
            if scope == "YEREL_UIP":
                create_local_uip_workspace(path, self.crs.crs())
            elif scope == "YEREL_NIP":
                create_local_nip_workspace(path, self.crs.crs())
            elif scope == "MSP_EK1E":
                create_msp_workspace(path, self.crs.crs())
            else:
                create_mpyy_workspace(path, self.crs.crs(), str(scope).split(":", 1)[1])
            self.load_workspace(path)
        except (ValueError, OSError, RuntimeError, TypeError, sqlite3.Error) as error:
            self.status.setText('Çalışma alanı oluşturulamadı: ' + str(error))


    def create_land_workspace(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Arazi kullanım çalışma alanı oluştur', "", "GeoPackage (*.gpkg)")
        if not path:
            return
        if not path.lower().endswith(".gpkg"):
            path += ".gpkg"
        try:
            create_land_use_workspace(path, self.crs.crs())
            self.load_workspace(path)
        except (ValueError, OSError, RuntimeError, TypeError, sqlite3.Error) as error:
            self.status.setText('Çalışma alanı oluşturulamadı: ' + str(error))


    def open_workspace(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Plan çalışma alanı aç', "", "GeoPackage (*.gpkg)")
        if path:
            try:
                self.load_workspace(path)
            except (ValueError, OSError, RuntimeError, TypeError, sqlite3.Error) as error:
                self.status.setText('Çalışma alanı açılamadı: ' + str(error))


    def load_workspace(self, path):
        layers = load_project_layers(path)
        if layers:
            target = next((lyr for lyr in layers if lyr.name() == "uip-alanlar"), layers[0])
            self.layer.setLayer(target)
            self.crs.setCrs(target.crs())
            self.status.setText(f'Çalışma alanı başarıyla yüklendi: {len(layers)} katman projeye eklendi.')


    def open_ingest_tool(self):
        try:
            from qgis import processing
            processing.execAlgorithmDialog("planx_mpyy_studio:ingest_vector_dataset", {})
        except Exception as err:
            self.status.setText('Aktarım aracı açılamadı: ' + str(err))


    def open_geom_cleaner(self):
        try:
            from qgis import processing
            processing.execAlgorithmDialog("planx_mpyy_studio:clean_planning_geometries", {})
        except Exception as err:
            self.status.setText('Geometri temizleme aracı açılamadı: ' + str(err))


    def open_qfield_packager(self):
        try:
            from qgis import processing
            processing.execAlgorithmDialog("planx_mpyy_studio:package_for_qfield", {})
        except Exception as err:
            self.status.setText('QField aracı açılamadı: ' + str(err))


    def open_report_exporter(self):
        try:
            from qgis import processing
            processing.execAlgorithmDialog("planx_mpyy_studio:export_planning_report", {})
        except Exception as err:
            self.status.setText('Rapor dışa aktarma aracı açılamadı: ' + str(err))


    def generate_db_report(self):
        layer = self.layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen önce bir katman seçin.')
            return

        source_path = layer.source().split("|")[0]
        if not source_path.lower().endswith(".gpkg"):
            self.status.setText('Seçili katman bir GeoPackage veritabanına ait değil.')
            return

        try:
            from pathlib import Path
            from ..core.db_factory import read_dataset_info
            info = read_dataset_info(source_path)
            lines = [
                f"=== PlanX MPYY GeoPackage Raporu ===",
                f"Dosya: {Path(source_path).name}",
                f"Tür: {info['workspace_kind']}",
                f"Şema Sürümü: {info['schema_version']}",
                f"Kademeler: {', '.join(info['plan_levels']) if info['plan_levels'] else 'Bağımsız Saha'}",
            ]
            with sqlite3.connect(source_path) as con:
                cur = con.cursor()
                cur.execute("SELECT table_name, data_type FROM gpkg_contents")
                rows = cur.fetchall()
                spatial_tables = [r[0] for r in rows if r[1] == "features"]
                views = [r[0] for r in rows if r[1] == "attributes" and r[0].startswith("v_")]
                lookups = [r[0] for r in rows if r[1] == "attributes" and not r[0].startswith("v_") and r[0] != "layer_styles"]

                lines.append(f'Mekânsal Katmanlar ({len(spatial_tables)}):')
                for st in spatial_tables:
                    try:
                        lyr = QgsVectorLayer(f"{source_path}|layername={st}", st, "ogr")
                        cnt = lyr.featureCount() if lyr.isValid() else "?"
                        lines.append(f"  • {st}: {cnt} nesne")
                    except Exception:
                        lines.append(f"  • {st}")

                if views:
                    lines.append(f'SQL Bilanço Görünümleri ({len(views)}):')
                    for v in views:
                        lines.append(f"  • {v}")

                if lookups:
                    lines.append(f'Sözlük Tabloları ({len(lookups)}):')
                    for lk in lookups:
                        lines.append(f"  • {lk}")

            self.status.setText("\n".join(lines))
        except Exception as err:
            self.status.setText(f'Rapor üretilemedi: {err}')


    def apply_style(self):
        layer = self.layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Geçerli bir vektör katmanı seçin.')
            return

        level = self.plan_type.currentData()
        try:
            if level in ("MPYY_MSP", "MSP"):
                res = self.msp_engine.apply(layer, field=self._styling_field(layer, MSP_FIELDS))
                self._last_engine = self.msp_engine
                self.status.setText(
                    f'MSP Ek-1e + EK-1b sembolojisi uygulandı: {res.styled_codes} kod, '
                    f'{res.pictogram_missing} piktogram çizilemedi, '
                    f'{len(res.approximated_codes)} yaklaşık gösterim. '
                    f'Katman, hangi kodların birebir çizilemediğini üstverisinde kaydeder.'
                )
            elif level in ("MPYY_CDP", "CDP", "YEREL_CDP"):
                res = self.mpyy_detail_engine.apply(
                    layer, field=self._styling_field(layer), plan_type="CDP"
                )
                self._last_engine = self.mpyy_detail_engine
                prefix = (
                    'Bilgi: ÇDP için henüz yerel taslak bulunmamaktadır. '
                    if level == "YEREL_CDP" else ''
                )
                self.status.setText(
                    prefix + f'ÇDP resmî bölge koruma/gelişme sembolojisi uygulandı: '
                    f'{res.official_styles} resmî, {res.fallback_styles} yedek gösterim.'
                )
            elif level in ("MPYY_NIP", "NIP", "YEREL_NIP"):
                res = self.mpyy_detail_engine.apply(
                    layer, field=self._styling_field(layer), plan_type="NIP"
                )
                self._last_engine = self.mpyy_detail_engine
                prefix = (
                    'Bilgi: 1/5.000 NİP özgün yerel taslağı kullanıcı tarafından '
                    'hazırlanmaktadır. Mevzuat standardı geçici olarak uygulandı. '
                    if level == "YEREL_NIP" else ''
                )
                self.status.setText(
                    prefix + f'NİP resmî brüt yoğunluk ve MNIP font notasyonları '
                    f'uygulandı: {res.official_styles} resmî, {res.fallback_styles} yedek gösterim.'
                )
            elif level == "MPYY_UIP":
                field_name = self._styling_field(layer)
                res = self.mpyy_detail_engine.apply(layer, field=field_name, plan_type="UIP")
                self._last_engine = self.mpyy_detail_engine
                self.status.setText(
                    f'MPYY / e-Plan sembolojisi "{field_name}" alanına uygulandı: '
                    f'{res.official_styles} resmî, {res.fallback_styles} yedek gösterim.'
                )
            elif level in ("YEREL_UIP", "UIP"):
                if layer.name() in ("uip-alanlar", "uip_cizgiler", "uip-notasyonlar"):
                    apply_layer_style_and_form(layer)
                    self._last_engine = None
                    self.status.setText('MpyyUipDb çizim şablonunun sembolojisi ve koşullu formu uygulandı.')
                else:
                    field_name = next(
                        (name for name in STYLE_FIELDS if layer.fields().indexFromName(name) >= 0),
                        None,
                    )
                    if field_name:
                        res = self.mpyy_engine.apply(layer, field_name=field_name, plan_level="UIP")
                        self._last_engine = self.mpyy_engine
                        self.status.setText(f'Yusuf Eminoğlu özgün yerel UİP XML sembolojisi uygulandı ({res.matched} eşleşme).')
                    else:
                        apply_layer_style_and_form(layer)
                        self._last_engine = None
                        self.status.setText('Yusuf Eminoğlu özgün yerel UİP sembolojisi uygulandı.')
            elif level == "YEREL_ARAZI":
                apply_layer_style_and_form(layer)
                self._last_engine = None
                self.status.setText('Arazi Kullanımı / Saha Sörveyi zenginleştirilmiş yerel sembolojisi uygulandı.')
            else:
                self.status.setText(f'Bilinmeyen profil seçimi: {level}')

        except Exception as err:
            self.status.setText(f'Stil uygulama hatası: {err}')


    def apply_smart_form(self):
        layer = self.layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Geçerli bir vektör katmanı seçin.')
            return

        if layer.customProperty("mpyy/form"):
            self.status.setText(
                f"'{layer.name()}' katmanının kendi koşullu formu var ({layer.customProperty('mpyy/form')}). "
                "Açılır listeleri ve sekmeleri bozmamak için genel form uygulanmadı."
            )
            return
        try:
            MPYYFormDesigner.apply_complete_form_experience(layer)
            self.status.setText(
                f"Akıllı Form ve Kısıtlar Başarıyla Uygulandı: '{layer.name()}'\n• 5 sekmeli sürükle-bırak formu (Fonksiyon, PAİY Yapılaşma, Mülkiyet, Afet, Sistem)\n• Otomatik alan ($area) ve inşaat hacmi (Alan*KAKS) ifadeleri\n• Değer haritaları (Nizam, Mülkiyet, Taşıyıcı Sistem, Hasar Durumu)\n• Mevzuat kısıtları (TAKS ≤ 1.0, KAKS ≤ 10.0, Kat ≥ 1, Çekme ≥ 0)"
            )
        except Exception as err:
            self.status.setText(f'Akıllı form uygulanamadı: {err}')


    def restore_style(self):
        layer = self.layer.currentLayer()
        if layer and self._last_engine:
            self._last_engine.restore(layer)
            self.status.setText('Önceki gösterim geri yüklendi.')
        else:
            self.status.setText('Geri yüklenecek önceki stil kaydı bulunamadı.')


    def run_crosswalk(self):
        src = self.cw_source.currentLayer()
        tgt = self.cw_target.currentLayer()
        fld = self.cw_field.text().strip()
        if not src or not tgt:
            self.status.setText('Lütfen kaynak ve hedef katmanları seçin.')
            return
        try:
            res = execute_layer_crosswalk(src, tgt, fld)
            self.status.setText(
            f"Fonksiyon eşleştirmesi tamamlandı: Toplam {res['toplam_nesne']} nesne, Otomatik: {res['otomatik_eslesen']}, Şehir Plancısı Onayı Bekleyen: {res['onay_bekleyen']} (ASLA otomatik atanmadı), Tanımsız: {res['tanimsiz']} satır bulundu."
            )
        except Exception as err:
            self.status.setText(f'Fonksiyon eşleştirmesi sırasında hata: {err}')


    def calculate_deficit(self):
        try:
            pop = int(self.spin_pop.value())
            green_m2 = float(self.edit_green.text().strip() or 0)
            res = SynthesisEngine.analyze_amenity_deficit(pop, green_m2)
            self.status.setText(
                f'Donatı Analizi: Nüfus {res.nufus}, Gereken: {res.gerekli_yesil_alan_m2} m², Existing: {res.mevcut_yesil_alan_m2} m² ({res.kisi_basi_mevcut_m2} m²/kişi). Açık: {res.yesil_alan_acigi_m2} m² - Status: {display_label(res.yeterlilik_durumu)} satır bulundu.'
            )
        except Exception as err:
            self.status.setText(f'Hesaplama hatası: {err}')


    def run_synthesis(self):
        parcels = self.synth_parcels.currentLayer()
        plans = self.synth_plans.currentLayer()
        buildings = self.synth_buildings.currentLayer()
        if not parcels:
            self.status.setText('Lütfen parsel katmanını seçin.')
            return

        plan_feats = list(plans.getFeatures()) if plans else []
        b_feats = list(buildings.getFeatures()) if buildings else []

        fields = QgsFields(parcels.fields())
        fields.append(QgsField("fiili_taks", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("fiili_kaks", QMetaType.Type.Double, prec=3))
        fields.append(QgsField("yapi_adedi", QMetaType.Type.Int))
        fields.append(QgsField("taban_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("insaat_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("hakim_kat", QMetaType.Type.Int))
        fields.append(QgsField("maks_kat", QMetaType.Type.Int))
        fields.append(QgsField("riskli_bina", QMetaType.Type.Int))
        fields.append(QgsField("hakim_plan_fonk", QMetaType.Type.QString, len=100))

        crs_str = parcels.crs().authid() or "EPSG:5254"
        synth_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", 'Kentsel_Sentez_Parseller', "memory")
        pr = synth_layer.dataProvider()
        pr.addAttributes(fields.toList())
        synth_layer.updateFields()

        out_features = []
        count = 0
        total_taban = 0.0

        for p in parcels.getFeatures():
            res = SynthesisEngine.synthesize_parcel(p, plan_feats, b_feats)
            total_taban += res.toplam_taban_alani_m2
            count += 1

            out_feat = QgsFeature(fields)
            out_feat.setGeometry(p.geometry())
            for fn in p.fields().names():
                out_feat[fn] = p[fn]

            out_feat["fiili_taks"] = res.hesaplanan_taks
            out_feat["fiili_kaks"] = res.hesaplanan_kaks
            out_feat["yapi_adedi"] = res.bina_sayisi
            out_feat["taban_m2"] = res.toplam_taban_alani_m2
            out_feat["insaat_m2"] = res.toplam_insaat_alani_m2
            out_feat["hakim_kat"] = res.hakim_kat
            out_feat["maks_kat"] = res.maks_kat
            out_feat["riskli_bina"] = res.riskli_bina_sayisi
            out_feat["hakim_plan_fonk"] = res.hakim_plan_fonksiyonu
            out_features.append(out_feat)

        pr.addFeatures(out_features)
        add_localized_layer(synth_layer)

        self.status.setText(
            f"Sentez tamamlandı: {count} parsel analiz edildi ve 'Kentsel_Sentez_Parseller' katmanı projeye eklendi. Toplam bina taban alanı: {total_taban:.1f} m²."
        )


    def run_qc(self):
        parcels = self.qc_parcels.currentLayer()
        buildings = self.qc_buildings.currentLayer()
        if not parcels:
            self.status.setText('Lütfen kalite kontrolü için parsel katmanını seçin.')
            return

        p_feats = list(parcels.getFeatures())
        b_feats = list(buildings.getFeatures()) if buildings else []
        setback_m = float(self.qc_setback.value())

        anomalies = QualityControlEngine.run_comprehensive_qc(p_feats, b_feats, setback_m=setback_m)

        if not anomalies:
            self.status.setText('Tebrikler: Hiçbir topolojik çakışma, tecavüz veya çekme ihlali tespit edilmedi (Temiz).')
            return

        crs_str = parcels.crs().authid() or "EPSG:5254"
        qc_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", 'MPYY_Kalite_Kontrol_Hatalari', "memory")
        fields = QgsFields()
        fields.append(QgsField("hata_turu", QMetaType.Type.QString, len=50))
        fields.append(QgsField("ciddiyet", QMetaType.Type.QString, len=20))
        fields.append(QgsField("nesne_id", QMetaType.Type.QString, len=100))
        fields.append(QgsField("aciklama", QMetaType.Type.QString, len=254))

        pr = qc_layer.dataProvider()
        pr.addAttributes(fields.toList())
        qc_layer.updateFields()

        out_feats = []
        for anom in anomalies:
            if not anom.geometri or anom.geometri.isEmpty():
                continue
            f = QgsFeature(fields)
            f.setGeometry(anom.geometri)
            f["hata_turu"] = anom.tur
            f["ciddiyet"] = anom.ciddiyet
            f["nesne_id"] = str(anom.nesne_id)
            f["aciklama"] = anom.aciklama
            out_feats.append(f)

        pr.addFeatures(out_feats)
        add_localized_layer(qc_layer)

        self.status.setText(
            f"Kalite kontrolü tamamlandı: {len(anomalies)} anomali tespit edildi ve 'MPYY_Kalite_Kontrol_Hatalari' katmanı haritaya eklendi."
        )


    def run_amenity_analysis(self):
        plan_layer = self.amenity_plan_layer.currentLayer()
        if not plan_layer or not plan_layer.isValid():
            self.status.setText('Lütfen analiz edilecek bir plan katmanı seçin.')
            return

        pop = self.spin_pop.value()
        field_name = self.amenity_field.text().strip() or "detay_katalogu"
        feats = list(plan_layer.getFeatures())
        totals = SynthesisEngine.extract_amenities_from_features(feats, function_field=field_name)
        results = SynthesisEngine.analyze_all_amenities(pop, totals, region_name=plan_layer.name())

        crs_str = plan_layer.crs().authid() or "EPSG:5254"
        table_layer = QgsVectorLayer(f"None?crs={crs_str}", 'MPYY_EK2_Donati_Dengesi', "memory")
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

        pr = table_layer.dataProvider()
        pr.addAttributes(fields.toList())
        table_layer.updateFields()

        out_feats = []
        deficits = 0
        total_amenity = 0.0
        for r in results:
            cat_name = r.bolge_adi.split(" - ")[-1]
            total_amenity += r.mevcut_yesil_alan_m2
            if r.yeterlilik_durumu != 'YETERLİ':
                deficits += 1
            karsilama = round(100.0 * r.mevcut_yesil_alan_m2 / r.gerekli_yesil_alan_m2, 1) if r.gerekli_yesil_alan_m2 > 0 else 100.0

            f = QgsFeature(fields)
            f["kategori"] = cat_name
            f["mevcut_m2"] = r.mevcut_yesil_alan_m2
            f["mevcut_ha"] = round(r.mevcut_yesil_alan_m2 / 10000.0, 4)
            f["standart_m2_kisi"] = r.standart_m2_kisi
            f["gerekli_m2"] = r.gerekli_yesil_alan_m2
            f["fiili_m2_kisi"] = r.kisi_basi_mevcut_m2
            f["acik_m2"] = r.yesil_alan_acigi_m2
            f["yeterlilik"] = r.yeterlilik_durumu
            f["karsilama_orani"] = karsilama
            out_feats.append(f)

        pr.addFeatures(out_feats)
        add_localized_layer(table_layer)
        self.status.setText(
            f'MPYY EK-2 Donatı analizi tamamlandı: {len(results)} donatı grubu incelendi. Toplam {total_amenity:.1f} m² donatı tespit edildi, {deficits} grupta açık var. Tablo projeye eklendi.'
        )


    def run_plan_diff(self):
        curr_layer = self.diff_old_layer.currentLayer()
        rev_layer = self.diff_new_layer.currentLayer()
        if not curr_layer or not rev_layer:
            self.status.setText('Lütfen hem yürürlükteki planı hem de öneri plan değişikliği katmanını seçin.')
            return

        radius = float(self.diff_radius.value())
        curr_feats = list(curr_layer.getFeatures())
        rev_feats = list(rev_layer.getFeatures())

        diff_features, summary = PlanRevisionDiffEngine.evaluate_revision(
            current_features=curr_feats,
            revised_features=rev_feats,
            service_radius_m=radius,
        )

        if not diff_features:
            self.status.setText('Plan karşılaştırması sonucunda geometrik fark bulunamadı veya kesişim boş.')
            return

        crs_str = curr_layer.crs().authid() or "EPSG:5254"
        diff_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", 'MPYY_Madde26_Plan_Degisikligi', "memory")
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

        pr = diff_layer.dataProvider()
        pr.addAttributes(fields.toList())
        diff_layer.updateFields()

        out_feats = []
        for df in diff_features:
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
            out_feats.append(feat)

        pr.addFeatures(out_feats)

        styles = {
            "KORUNAN": {"color": "#B0BEC5", "outline": "#546E7A"},
            "FONKSIYON_DEGISIMI": {"color": "#FFA726", "outline": "#E65100"},
            "DONATI_KALDIRILDI": {"color": "#EF5350", "outline": "#B71C1C"},
            "YENI_DONATI_EKLENDI": {"color": "#66BB6A", "outline": "#1B5E20"},
        }
        categories = []
        for cat_val, style_info in styles.items():
            sym = QgsFillSymbol.createSimple({
                "color": style_info["color"],
                "outline_color": style_info["outline"],
                "outline_width": "0.3",
            })
            categories.append(QgsRendererCategory(cat_val, sym, cat_val))

        renderer = QgsCategorizedSymbolRenderer("degisim_turu", categories)
        diff_layer.setRenderer(renderer)
        diff_layer.setOpacity(0.85)

        add_localized_layer(diff_layer)

        compliance_str = "UYGUN" if summary.madde_26_uygunlugu else 'UYGUN DEĞİL (Eşdeğer alan yetersiz/eksik)'
        self.status.setText(
            f'Madde 26 Analizi Tamamlandı: {len(diff_features)} parça incelendi. Kaldırılan Donatı: {summary.kaldirilan_donati_m2:.1f} m², Yeni Donatı: {summary.yeni_eklenen_donati_m2:.1f} m². Mevzuata Uygunluk: {compliance_str} satır bulundu.'
        )


    def run_dop(self):
        cad_layer = self.dop_cad_layer.currentLayer()
        if not cad_layer or not cad_layer.isValid():
            self.status.setText('Lütfen geçerli bir kadastro parsel katmanı seçin.')
            return

        pub_layer = self.dop_pub_layer.currentLayer()
        pub_feats = list(pub_layer.getFeatures()) if (pub_layer and pub_layer.isValid()) else None
        manual_pub = float(self.dop_manual_m2.value())
        forced_ratio = float(self.dop_forced_ratio.value()) if self.dop_forced_ratio.value() > 0 else None

        results, summary = DOPEngine.calculate_dop(
            cadastral_features=list(cad_layer.getFeatures()),
            public_features=pub_feats,
            manual_public_area_m2=manual_pub,
            forced_dop_ratio=forced_ratio,
        )

        if not results:
            self.status.setText('DOP hesabı gerçekleştirilemedi: Kadastro verisi boş veya alanlar geçersiz.')
            return

        crs_str = cad_layer.crs().authid() or "EPSG:5254"
        dop_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", 'MPYY_Madde18_Tahsis_Cetveli', "memory")
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

        pr = dop_layer.dataProvider()
        pr.addAttributes(fields.toList())
        dop_layer.updateFields()

        out_feats = []
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
            out_feats.append(feat)

        pr.addFeatures(out_feats)

        styles = {
            "UYGUN": {"color": "#81C784", "outline": "#2E7D32"},
            "YASAL_SINIR_ASILDI": {"color": "#E57373", "outline": "#C62828"},
        }
        categories = []
        for cat_val, s_info in styles.items():
            sym = QgsFillSymbol.createSimple({
                "color": s_info["color"],
                "outline_color": s_info["outline"],
                "outline_width": "0.3",
            })
            categories.append(QgsRendererCategory(cat_val, sym, cat_val))
        renderer = QgsCategorizedSymbolRenderer("yasal_durum", categories)
        dop_layer.setRenderer(renderer)
        dop_layer.setOpacity(0.85)

        add_localized_layer(dop_layer)

        durum_str = 'YASAL SINIR İÇİNDE (%45 Kuralı Karşılandı)' if summary.yasal_uygun else f'DİKKAT: YASAL TAVAN (%45) AŞILDI! (Aşan: {summary.kop_veya_kamulastirma_gerekli_m2:.1f} m²)'
        self.status.setText(
            f'Madde 18 DOP Hesabı Tamamlandı: {len(results)} parsel analiz edildi. Toplam kadastro alanı: {summary.toplam_kadastro_m2:.1f} m², Terk: {summary.toplam_terk_m2:.1f} m², DOP Oranı: %{summary.dop_orani * 100:.2f} — {durum_str}. Tahsis Cetveli projeye eklendi.'
        )


    def run_capacity(self):
        plan_layer = self.cap_plan_layer.currentLayer()
        if not plan_layer or not plan_layer.isValid():
            self.status.setText('Lütfen geçerli bir imar planı katmanı seçin.')
            return

        kaks = float(self.cap_kaks.value())
        taks = float(self.cap_taks.value())
        unit_m2 = float(self.cap_unit_m2.value())

        items, summary = PlanCapacityEngine.estimate_capacity(
            plan_features=list(plan_layer.getFeatures()),
            default_kaks=kaks,
            default_taks=taks,
            avg_unit_m2=unit_m2,
        )

        if not items:
            self.status.setText('Kapasite analizi yapılamadı: Planda konut veya karma kullanım fonksiyonu tespit edilemedi.')
            return

        crs_str = plan_layer.crs().authid() or "EPSG:5254"
        cap_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", 'MPYY_Imar_Kapasitesi_ve_Nufus', "memory")
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

        pr = cap_layer.dataProvider()
        pr.addAttributes(fields.toList())
        cap_layer.updateFields()

        out_feats = []
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
            out_feats.append(feat)

        pr.addFeatures(out_feats)
        add_localized_layer(cap_layer)

        self.status.setText(
            f'Kapasite Modellemesi Tamamlandı: {len(items)} konut/karma ada incelendi. Toplam İnşaat Alanı: {summary.toplam_insaat_m2:.1f} m², Konut Sayısı: {summary.toplam_konut_sayisi}, Öngörülen Nüfus: {summary.toplam_kapasite_nufusu} kişi, Brüt Yoğunluk: {summary.brut_yogunluk_kisi_ha} kişi/ha.'
        )


    def run_paiy_compliance(self):
        parcels_layer = self.paiy_parcels.currentLayer()
        if not parcels_layer or not parcels_layer.isValid():
            self.status.setText('Lütfen geçerli bir parsel katmanı seçin.')
            return

        def_nizam = str(self.paiy_nizam.currentData() or "AYRIK")
        def_floors = int(self.paiy_floors.value())
        front_sb = float(self.paiy_front.value())
        side_sb = float(self.paiy_side.value())

        results, summary = ComplianceEngine.evaluate_parcels(
            parcel_features=list(parcels_layer.getFeatures()),
            default_nizam=def_nizam,
            default_floors=def_floors,
            default_front_setback_m=front_sb,
            default_side_setback_m=side_sb,
        )

        if not results:
            self.status.setText('PAİY denetimi yapılamadı: Parsel katmanında geçerli geometri bulunamadı.')
            return

        crs_str = parcels_layer.crs().authid() or "EPSG:5254"
        comp_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", 'MPYY_PAIY_Yapilasabilirlik', "memory")
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

        pr = comp_layer.dataProvider()
        pr.addAttributes(fields.toList())
        comp_layer.updateFields()

        out_feats = []
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
            out_feats.append(feat)

        pr.addFeatures(out_feats)

        styles = {
            "YAPILASABILIR": {"color": "#66BB6A", "outline": "#2E7D32"},
            "IFRAZ_EDILEBILIR": {"color": "#42A5F5", "outline": "#1565C0"},
            "TEVHID_ZORUNLU": {"color": "#EF5350", "outline": "#C62828"},
            "CEKME_YETERSIZ": {"color": "#FFA726", "outline": "#E65100"},
        }
        categories = []
        for cat_val, s_info in styles.items():
            sym = QgsFillSymbol.createSimple({
                "color": s_info["color"],
                "outline_color": s_info["outline"],
                "outline_width": "0.3",
            })
            categories.append(QgsRendererCategory(cat_val, sym, cat_val))
        renderer = QgsCategorizedSymbolRenderer("durum", categories)
        comp_layer.setRenderer(renderer)
        comp_layer.setOpacity(0.85)

        add_localized_layer(comp_layer)

        self.status.setText(
            f'PAİY Denetimi Tamamlandı: {summary.toplam_parsel_sayisi} parsel incelendi. Yapılaşabilir: {summary.yapilasabilir_sayisi}, Tevhit gereken: {summary.tevhid_zorunlu_sayisi}, İfraz Edilebilir: {summary.ifraz_edilebilir_sayisi}, Çekme Yetersiz: {summary.cekme_yetersiz_sayisi}. Overall compliance: %{summary.uygunluk_orani_yuzde:.1f} satır bulundu.'
        )


    def run_pafta_grid(self):
        plan_layer = self.pafta_plan.currentLayer()
        if not plan_layer or not plan_layer.isValid():
            self.status.setText('Lütfen paftalanacak bir plan katmanı seçin.')
            return

        scale_val = str(self.pafta_scale.currentData() or "1/1.000")
        prefix = self.pafta_prefix.text().strip() or "P"

        sheets, summary = PaftaGridEngine.generate_sheet_grid(
            extent=plan_layer.extent(),
            scale_name=scale_val,
            plan_features=list(plan_layer.getFeatures()),
            prefix=prefix,
        )

        if not sheets:
            self.status.setText('Pafta bölümlemesi üretilemedi: Kapsanan plan alanı bulunamadı.')
            return

        crs_str = plan_layer.crs().authid() or "EPSG:5254"
        grid_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", f'MPYY_Pafta_Indeksi_{prefix}', "memory")
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

        pr = grid_layer.dataProvider()
        pr.addAttributes(fields.toList())
        grid_layer.updateFields()

        out_feats = []
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
            out_feats.append(feat)

        pr.addFeatures(out_feats)

        sym = QgsFillSymbol.createSimple({
            "color": "255,255,255,20",
            "outline_color": "#1976D2",
            "outline_width": "0.6",
        })
        grid_layer.setRenderer(QgsSingleSymbolRenderer(sym))

        add_localized_layer(grid_layer)

        self.status.setText(
            f'Pafta İndeksi Üretildi: Toplam {summary.toplam_pafta_sayisi} pafta ({summary.satir_sayisi} satır x {summary.sutun_sayisi} sütun). Ölçek: {summary.olcek}, Kapsanan Plan: {summary.kapsanan_plan_alani_m2:.1f} m². Katman haritaya eklendi.'
        )


    def run_plan_notes(self):
        plan_layer = self.notes_plan.currentLayer()
        if not plan_layer or not plan_layer.isValid():
            self.status.setText('Lütfen plan notları üretilecek geçerli bir plan katmanı seçin.')
            return

        title = self.notes_title.text().strip() or '1/1.000 Ölçekli Uygulama İmar Planı'
        scale = str(self.notes_scale.currentData() or "1/1.000")
        feats = list(plan_layer.getFeatures())

        notes = PlanNotesEngine.generate_plan_notes(
            plan_title=title,
            scale=scale,
            features=feats,
        )

        preview_lines = [
            f'=== {title.upper()} PLAN NOTLARI ===',
            f'Ölçek: {scale} | Mevzuat: MPYY & PAİY',
            f"Tespit Edilen Fonksiyonlar ({len(notes.tespit_edilen_kategoriler)}): {', '.join(map(display_label, notes.tespit_edilen_kategoriler))}",
            "",
            '1. GENEL HÜKÜMLER:',
        ]
        for idx, g in enumerate(notes.genel_hukumler[:4], 1):
            preview_lines.append(f"  1.{idx}. {g}")
        if len(notes.genel_hukumler) > 4:
            preview_lines.append(f'  ... (+{len(notes.genel_hukumler) - 4} genel hüküm)')

        preview_lines.append("")
        preview_lines.append(f'2. ÖZEL HÜKÜMLER: {len(notes.ozel_hukumler)} fonksiyon grubu için özel hüküm sentezlendi.')
        for grp, rls in list(notes.ozel_hukumler.items())[:3]:
            preview_lines.append(f"  • {grp}: {len(rls)} madde")

        if notes.uygulama_hukumleri:
            preview_lines.append("")
            preview_lines.append(
                f'3. UYGULAMA VE PARSELASYON: {len(notes.uygulama_hukumleri)} madde (Madde 18 DOP, Kamu Terkleri, PAİY İfraz-Tevhit).'
            )

        self.status.setText("\n".join(preview_lines))


    def run_comprehensive_report(self):
        plan_layer = self.rep_plan.currentLayer()
        if not plan_layer or not plan_layer.isValid():
            self.status.setText('Lütfen rapor üretilecek geçerli bir plan katmanı seçin.')
            return

        folder = QFileDialog.getExistingDirectory(self, 'Plan Açıklama Raporu Çıktı Klasörünü Seçin')
        if not folder:
            return

        title = self.rep_title.text().strip() or 'Uygulama İmar Planı Açıklama Raporu'
        scale = "1/1.000"
        feats = list(plan_layer.getFeatures())
        crs_auth = plan_layer.crs().authid() if plan_layer.crs() else "EPSG:5256"

        notes = PlanNotesEngine.generate_plan_notes(plan_title=title, scale=scale, features=feats)

        try:
            res = PlanReportEngine.generate_comprehensive_report(
                output_dir=folder,
                plan_features=feats,
                report_title=title,
                plan_scale=scale,
                crs_authid=crs_auth,
                plan_notes=notes,
            )
            self.status.setText(
                f"Kapsamlı plan açıklama raporu üretildi!\nToplam plan alanı: {res.get('total_area_m2', 0):,.1f} m²\nHTML raporu: {res.get('html_report')}\nMarkdown raporu: {res.get('markdown_report')}\nCSV Arazi Bilançosu: {res.get('csv_balance')}"
            )
        except Exception as err:
            self.status.setText(f'Rapor üretilemedi: {err}')


    def run_corner_chamfer(self):
        layer = self.chamfer_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen köşe pahı uygulanacak geçerli bir ada/parsel katmanı seçin.')
            return

        chamfer_dist = self.chamfer_dist.value()
        fields = layer.fields()
        fields.append(QgsField("pah_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("pah_adet", QMetaType.Type.Int))

        crs_str = layer.crs().authid() or "EPSG:5254"
        out_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", f'{layer.name()}_Pahli_{chamfer_dist}m', "memory")
        pr = out_layer.dataProvider()
        pr.addAttributes(fields.toList())
        out_layer.updateFields()

        out_feats = []
        total_cuts = 0
        total_cut_m2 = 0.0

        for feat in layer.getFeatures():
            res = ChamferEngine.apply_chamfer(feat.geometry(), chamfer_dist=chamfer_dist)
            out_f = QgsFeature(fields)
            out_f.setGeometry(res.geometri)
            for fld in layer.fields():
                out_f[fld.name()] = feat[fld.name()]
            out_f["pah_m2"] = res.kesilen_alan_m2
            out_f["pah_adet"] = res.pah_adedi
            out_feats.append(out_f)
            total_cuts += res.pah_adedi
            total_cut_m2 += res.kesilen_alan_m2

        pr.addFeatures(out_feats)
        add_localized_layer(out_layer)

        self.status.setText(
            f'PAİY Madde 20 Köşe Pahı Uygulandı!\nPah Mesafesi: {chamfer_dist:.1f} m\nToplam Kırılan Köşe: {total_cuts} adet\nToplam Terk/Pah Alanı: {total_cut_m2:.2f} m²\nProjeye eklenen yeni katman: {out_layer.name()}'
        )


    def run_print_layout(self):
        paper_size = str(self.layout_paper.currentData() or "A1")
        title = self.layout_title.text().strip() or '1/1.000 ÖLÇEKLİ UYGULAMA İMAR PLANI'
        muni = self.layout_muni.text().strip() or 'İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ'
        pafta = self.layout_pafta.text().strip() or 'İ22-c-04-a'

        layout_name = f"MPYY_Pafta_{paper_size}_{pafta.replace('-', '_')}"
        try:
            MPYYLayoutComposer.create_mpyy_layout(
                layout_name=layout_name,
                paper_size=paper_size,
                plan_title=title,
                municipality=muni,
                pafta_no=pafta,
                plan_scale="1/1.000",
            )
            self.status.setText(
                f'MPYY standart baskı paftası oluşturuldu!\nPafta adı: {layout_name}\nKağıt Boyutu: {paper_size}\nProjeler > Yerleşim Düzeni Yöneticisi menüsünden açıp düzenleyebilirsiniz.'
            )
        except Exception as err:
            self.status.setText(f'Pafta şablonu oluşturulamadı: {err}')


    def run_parking_analysis(self):
        layer = self.parking_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen otopark analizi yapılacak geçerli bir plan/parsel katmanı seçin.')
            return

        default_kaks = self.parking_kaks.value()
        area_per_car = self.parking_area_per_car.value()

        feats = list(layer.getFeatures())
        results, summary = ParkingEngine.evaluate_parking_balance(
            features=feats,
            default_kaks=default_kaks,
            area_per_car_m2=area_per_car,
        )

        res_by_id = {r.feature_id: r for r in results}

        fields = layer.fields()
        fields.append(QgsField("otopark_kategori", QMetaType.Type.QString, len=50))
        fields.append(QgsField("insaat_alani_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("otopark_ihtiyaci_arac", QMetaType.Type.Int))
        fields.append(QgsField("tahsis_edilen_m2", QMetaType.Type.Double, prec=2))

        crs_str = layer.crs().authid() or "EPSG:5254"
        out_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", f'{layer.name()}_Otopark_Analizi', "memory")
        pr = out_layer.dataProvider()
        pr.addAttributes(fields.toList())
        out_layer.updateFields()

        out_feats = []
        for f in feats:
            out_f = QgsFeature(fields)
            out_f.setGeometry(f.geometry())
            for fld in layer.fields():
                out_f[fld.name()] = f[fld.name()]

            r = res_by_id.get(f.id())
            if r:
                out_f["otopark_kategori"] = r.kategori
                out_f["insaat_alani_m2"] = r.insaat_alani_m2
                out_f["otopark_ihtiyaci_arac"] = r.otopark_ihtiyaci_arac
                out_f["tahsis_edilen_m2"] = r.tahsis_edilen_m2
            else:
                out_f["otopark_kategori"] = "GENEL_OTOPARK"
                out_f["insaat_alani_m2"] = 0.0
                out_f["otopark_ihtiyaci_arac"] = 0
                out_f["tahsis_edilen_m2"] = 0.0
            out_feats.append(out_f)

        pr.addFeatures(out_feats)
        add_localized_layer(out_layer)

        durum_str = 'YETERLİ (Fazlalık Mevcut)' if summary.yeterli_mi else 'YETERSİZ (Otopark Açığı Var!)'
        self.status.setText(
            f'Otopark Yönetmeliği Analizi Tamamlandı!\nToplam Otopark İhtiyacı: {summary.toplam_otopark_ihtiyaci_arac} araç ({summary.toplam_otopark_ihtiyaci_m2:.1f} m²)\nPlanda Ayrılan Umumi Otopark: {summary.planda_ayrilan_otopark_kapasite_arac} araç ({summary.planda_ayrilan_otopark_m2:.1f} m²)\nNet Denge (Açık/Fazlalık): {summary.otopark_acigi_fazlasi_arac:+d} araç\nKarşılama Oranı: %{summary.karsilama_orani_yuzde:.1f} - {durum_str}\nSonuç katmanı projeye eklendi: {out_layer.name()}'
        )


    def run_transformation_risk(self):
        layer = self.risk_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen afet risk analizi yapılacak geçerli bir bina/parsel katmanı seçin.')
            return

        ref_year = self.risk_ref_year.value()
        feats = list(layer.getFeatures())
        results, summary = UrbanTransformationRiskEngine.evaluate_risk(
            features=feats,
            reference_year=ref_year,
        )

        res_by_id = {r.feature_id: r for r in results}

        fields = layer.fields()
        fields.append(QgsField("skor_yas", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_yapi", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_hasar", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_kat", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("skor_jeoloji", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("toplam_risk", QMetaType.Type.Double, prec=1))
        fields.append(QgsField("oncelik_grubu", QMetaType.Type.QString, len=30))

        crs_str = layer.crs().authid() or "EPSG:5254"
        out_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", f'{layer.name()}_Afet_Risk_6306', "memory")
        pr = out_layer.dataProvider()
        pr.addAttributes(fields.toList())
        out_layer.updateFields()

        out_feats = []
        for f in feats:
            out_f = QgsFeature(fields)
            out_f.setGeometry(f.geometry())
            for fld in layer.fields():
                out_f[fld.name()] = f[fld.name()]

            r = res_by_id.get(f.id())
            if r:
                out_f["skor_yas"] = r.skor_yas
                out_f["skor_yapi"] = r.skor_yapi
                out_f["skor_hasar"] = r.skor_hasar
                out_f["skor_kat"] = r.skor_kat
                out_f["skor_jeoloji"] = r.skor_jeoloji
                out_f["toplam_risk"] = r.toplam_risk_skoru
                out_f["oncelik_grubu"] = r.oncelik_grubu
            out_feats.append(out_f)

        pr.addFeatures(out_feats)
        add_localized_layer(out_layer)

        self.status.setText(
            f'6306 s. Kentsel Dönüşüm ve Afet Risk Analizi Tamamlandı!\nİncelenen Bina Sayısı: {summary.toplam_bina_adedi} adet ({summary.toplam_insaat_alani_m2:.1f} m² inşaat)\nOrtalama Afet Risk Skoru: {summary.ortalama_risk_skoru} / 100\n🚨 Acil Dönüşüm: {summary.acil_donusum_adedi} bina ({summary.acil_donusum_alani_m2:.1f} m² taban)\n⚠️ Öncelikli Dönüşüm: {summary.oncelikli_donusum_adedi} bina ({summary.oncelikli_donusum_alani_m2:.1f} m² taban)\nAcil + Öncelikli Oranı: %{summary.acil_oncelikli_yuzde:.1f}\nSonuç katmanı projeye eklendi: {out_layer.name()}'
        )


    def run_zoning_certificate(self):
        layer = self.cert_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen geçerli bir parsel katmanı seçin.')
            return

        feats = list(layer.selectedFeatures()) or list(layer.getFeatures())
        if not feats:
            self.status.setText('Katmandan imar çapı üretilecek en az bir parsel seçin.')
            return

        feat = feats[0]
        muni = self.cert_muni.text().strip() or 'İMAR VE ŞEHİRCİLİK MÜDÜRLÜĞÜ'
        ilce = self.cert_ilce.text().strip() or 'İlçe'
        mah = self.cert_mah.text().strip() or 'Mahalle'
        pafta = self.cert_pafta.text().strip() or 'İ22-c-04-a'

        cert = ZoningCertificateEngine.generate_certificate(
            parcel_feature=feat,
            municipality=muni,
            ilce=ilce,
            mahalle=mah,
            pafta_no=pafta,
        )

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            'İmar Durum Belgesini Kaydet',
            f"Imar_Capi_{cert.ada_no}_{cert.parsel_no}.html",
            "HTML Belgeleri (*.html)",
        )
        if not out_path:
            return

        try:
            from pathlib import Path
            Path(out_path).write_text(cert.html_content, encoding="utf-8")
            self.status.setText(
                f'Resmî imar durumu belgesi (imar çapı) üretildi!\nBelge no: {cert.belge_no}\nBlock/parcel: {cert.ada_no}/{cert.parsel_no} ({cert.kadastro_alani_m2:,.2f} m²)\nFonksiyon: {display_label(cert.plan_fonksiyonu)}\nArrangement: {display_label(cert.yapi_nizami)}, TAKS: {cert.taks}, KAKS: {cert.kaks}, Floors: {cert.kat_adedi}\nAzami İnşaat Alanı: {cert.azami_insaat_alani_m2:,.2f} m²\nSaved file: {out_path}'
            )
        except Exception as err:
            self.status.setText(f'İmar çapı kaydedilemedi: {err}')


    def run_shelter_analysis(self):
        layer = self.shelter_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen sığınak analizi yapılacak geçerli bir plan/parsel katmanı seçin.')
            return

        default_kaks = self.shelter_kaks.value()
        area_pp = self.shelter_area_pp.value()

        feats = list(layer.getFeatures())
        results, summary = ShelterEngine.evaluate_shelter_requirements(
            features=feats,
            default_kaks=default_kaks,
            area_per_person_m2=area_pp,
        )

        res_by_id = {r.feature_id: r for r in results}

        fields = layer.fields()
        fields.append(QgsField("siginak_durumu", QMetaType.Type.QString, len=30))
        fields.append(QgsField("siginak_m2", QMetaType.Type.Double, prec=2))
        fields.append(QgsField("siginak_kisi", QMetaType.Type.Int))
        fields.append(QgsField("siginak_dayanak", QMetaType.Type.QString, len=100))

        crs_str = layer.crs().authid() or "EPSG:5254"
        out_layer = QgsVectorLayer(f"MultiPolygon?crs={crs_str}", f'{layer.name()}_Siginak_Analizi', "memory")
        pr = out_layer.dataProvider()
        pr.addAttributes(fields.toList())
        out_layer.updateFields()

        out_feats = []
        for f in feats:
            out_f = QgsFeature(fields)
            out_f.setGeometry(f.geometry())
            for fld in layer.fields():
                out_f[fld.name()] = f[fld.name()]

            r = res_by_id.get(f.id())
            if r:
                out_f["siginak_durumu"] = r.siginak_durumu
                out_f["siginak_m2"] = r.gerekli_siginak_alani_m2
                out_f["siginak_kisi"] = r.ongorulen_siginak_kapasite_kisi
                out_f["siginak_dayanak"] = r.yasal_dayanak
            out_feats.append(out_f)

        pr.addFeatures(out_feats)
        add_localized_layer(out_layer)

        genel_str = 'GEREKLİ (>=15.000 nüfus eşiği aşıldı)' if summary.genel_siginak_ayrilmali_mi else 'Münferit serpiştirme sığınakları yeterli'
        self.status.setText(
            f'Sığınak Yönetmeliği Analizi Tamamlandı!\nToplam Parsel: {summary.toplam_parsel_sayisi} adet\n🛡️ Sığınak Zorunlu Parseller: {summary.siginak_zorunlu_parsel_sayisi} adet (%{summary.zorunlu_parsel_orani_yuzde:.1f})\nToplam Gerekli Sığınak Alanı: {summary.toplam_gerekli_siginak_alani_m2:,.1f} m²\nToplam Sığınacak Kişi Kapasitesi: {summary.toplam_siginacak_kisi_kapasitesi} kişi\nGenel Sığınak Durumu: {genel_str}\nSonuç katmanı projeye eklendi: {out_layer.name()}'
        )


    def run_zoning_hud(self):
        layer = self.cert_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen canlı bilgi katmanı oluşturulacak bir parsel katmanı seçin.')
            return

        feats = list(layer.selectedFeatures()) or list(layer.getFeatures())
        if not feats:
            self.status.setText('Bilgi katmanı oluşturmak için en az bir parsel seçin.')
            return

        feat = feats[0]
        hud_layer = ZoningCertificateEngine.create_zoning_hud_layer(
            parcel_feature=feat,
            setback_m=3.0,
            crs_authid=layer.crs().authid() or "EPSG:5254",
        )
        add_localized_layer(hud_layer)
        self.status.setText(
            f'Canlı imar çapı ve çekme bilgi katmanı projeye eklendi: {hud_layer.name()} ({hud_layer.featureCount()} çizim/cephe elemanı).'
        )


    def run_allocation_matrix(self):
        cad_layer = self.alloc_cad_layer.currentLayer()
        zone_layer = self.alloc_zone_layer.currentLayer()
        if not cad_layer or not cad_layer.isValid() or not zone_layer or not zone_layer.isValid():
            self.status.setText('Lütfen hem kadastro hem de imar parselleri katmanlarını seçin.')
            return

        dop_ratio = self.alloc_dop_ratio.value()
        c_feats = list(cad_layer.getFeatures())
        z_feats = list(zone_layer.getFeatures())

        report = AllocationEngine.calculate_allocation_matrix(
            cadastral_features=c_feats,
            zoning_parcels=z_feats,
            dop_ratio=dop_ratio,
        )

        out_layer = AllocationEngine.create_allocation_memory_layer(
            report=report,
            crs_authid=zone_layer.crs().authid() or "EPSG:5254",
        )
        add_localized_layer(out_layer)

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            'İmar Dağıtım Cetvelini Kaydet (HTML)',
            "Imar_Dagitim_Tahsis_Cetveli.html",
            "HTML Belgeleri (*.html)",
        )
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report.html_report)

        self.status.setText(
            f'Madde 18 Parselasyon Dağıtım Cetveli Tamamlandı!\nKadastro Parsel Sayısı: {report.kadastro_parsel_sayisi} adet ({report.toplam_kadastro_m2:,.2f} m²)\nDOP Kesinti Oranı: %{report.dop_orani * 100:.2f} (Toplam DOP: {report.toplam_dop_kesinti_m2:,.2f} m²)\nTahsis Edilen Net İmar Alanı: {report.toplam_tahsis_imar_m2:,.2f} m²\nSonuç katmanı projeye eklendi: {out_layer.name()}'
        )


    def run_transformation_feasibility(self):
        layer = self.feas_parcel_layer.currentLayer()
        if not layer or not layer.isValid():
            self.status.setText('Lütfen kentsel dönüşüm fizibilitesi yapılacak geçerli bir parsel katmanı seçin.')
            return

        c_ratio = self.feas_contractor_ratio.value()
        p_feats = list(layer.getFeatures())

        items, summary = UrbanTransformationFeasibilityEngine.evaluate_feasibility(
            parcel_features=p_feats,
            contractor_ratio=c_ratio,
        )

        out_layer = UrbanTransformationFeasibilityEngine.create_feasibility_memory_layer(
            summary=summary,
            crs_authid=layer.crs().authid() or "EPSG:5254",
        )
        add_localized_layer(out_layer)

        self.status.setText(
            f'6306 s. Kentsel Dönüşüm Hakediş ve Fizibilite Analizi Tamamlandı!\nİncelenen Parsel Sayısı: {summary.toplam_parsel_sayisi} adet\nMevcut İnşaat: {summary.toplam_mevcut_insaat_m2:,.2f} m² → Yeni İmar: {summary.toplam_yeni_insaat_m2:,.2f} m²\nHak Sahipleri Alanı: {summary.toplam_hak_sahibi_m2:,.2f} m² | Müteahhit Payı: {summary.toplam_muteahhit_m2:,.2f} m²\nOrtalama Hakediş Katsayısı: {summary.ortalama_hakedis_katsayisi:.3f}\nNet proje mali dengesi: {summary.net_finansal_bakiye_tl:,.2f} TL\nSonuç katmanı projeye eklendi: {out_layer.name()}'
        )

