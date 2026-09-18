"""Comprehensive integration tests for PlanX MPYY Studio.

Tests cover:
- Workspace layer tree structure and Turkish group hierarchy.
- Authentic PlanGML form binding, tab layout, and default value expressions.
- QgsRelation registration between uip-alanlar and uipPolygonTable.
- Actions (Street View, TKGM, clipboard copy) and MapTip cards.
- Land use survey tables with external photo resources.
- Deterministic vs. ambiguous Crosswalk resolution (ONAY_BEKLIYOR guarantee).
- Urban synthesis engine (majority overlap, TAKS/KAKS, floor counts, amenity deficit).
- Setback building envelope negative buffer calculation.
"""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import (
    QgsAction,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)

from planx_mpyy_studio.core.actions import calculate_setback_envelope
from planx_mpyy_studio.core.crosswalk import (
    evaluate_crosswalk,
    execute_layer_crosswalk,
)
from planx_mpyy_studio.core.local_uip_workspace import create_local_uip_workspace
from planx_mpyy_studio.core.db_factory import (
    create_land_use_workspace,
    read_dataset_info,
)
from planx_mpyy_studio.core.form_designer import MPYYFormDesigner
from planx_mpyy_studio.core.project_binding import load_project_layers
from planx_mpyy_studio.core.qc_engine import QualityControlEngine
from planx_mpyy_studio.core.schema import LAND_TABLES
from planx_mpyy_studio.core.synthesis import SynthesisEngine
from planx_mpyy_studio.core.zoning_certificate import ZoningCertificateEngine
from planx_mpyy_studio.provider import MPYYProvider

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        QgsProject.instance().clear()

    def tearDown(self):
        QgsProject.instance().clear()
        self.tmp.cleanup()

    def test_land_use_workspace_and_external_resource_widgets(self):
        """Kriter 7: Arazi Kullanımı GeoPackage katmanları eksiksiz yüklenir."""
        p = Path(self.tmp.name) / "arazi_workspace.gpkg"
        create_land_use_workspace(p, "EPSG:5254")

        project = QgsProject.instance()
        loaded = load_project_layers(p, project)
        loaded_names = {lyr.name() for lyr in loaded}
        self.assertEqual(loaded_names, set(LAND_TABLES.keys()) | {"saha_kullanim_kodlari"})

        # Check group name
        root = project.layerTreeRoot()
        self.assertIsNotNone(root.findGroup('Arazi Kullanımı ve Saha Anketi'))

        # Verify photo and attribute fields on yapi_saha
        yapi = [lyr for lyr in loaded if lyr.name() == "yapi_saha"][0]
        yapi_fields = [f.name() for f in yapi.fields()]
        self.assertIn("fotograf", yapi_fields)
        self.assertIn("B_KAT", yapi_fields)
        self.assertIn("B_DURUM", yapi_fields)
        self.assertIn("B_FONK", yapi_fields)

    def test_crosswalk_deterministic_and_ambiguous_rules(self):
        """Kriter 8: Crosswalk deterministik fonksiyonları aktarır, belirsizleri ASLA otomatik atamaz."""
        # 1. Deterministic direct evaluation
        m_konut = evaluate_crosswalk("KONUT")
        self.assertEqual(m_konut.durum, "OTOMATIK_ESLESTI")
        self.assertEqual(m_konut.eslesen_fonksiyon, "YERLEŞİK KONUT ALANI")
        self.assertEqual(m_konut.ust_grup, "KONUT ALANLARI / YERLEŞİM ALANLARI")

        m_park = evaluate_crosswalk("PARK")
        self.assertEqual(m_park.durum, "OTOMATIK_ESLESTI")
        self.assertEqual(m_park.eslesen_fonksiyon, "PARK")

        # 2. Ambiguous multi-valued evaluation (MUST NOT auto-assign)
        m_karma = evaluate_crosswalk("KARMA_KULLANIM")
        self.assertEqual(m_karma.durum, "ONAY_BEKLIYOR")
        self.assertEqual(m_karma.eslesen_fonksiyon, "", "Ambiguous mapping must never auto-assign")
        self.assertGreater(len(m_karma.aday_fonksiyonlar), 1)

        m_arsa = evaluate_crosswalk("BOS_ARSA")
        self.assertEqual(m_arsa.durum, "ONAY_BEKLIYOR")
        self.assertEqual(m_arsa.eslesen_fonksiyon, "")

        # 3. Completely unrecognized
        m_unknown = evaluate_crosswalk("BILINMEYEN_OZEL_KOD_999")
        self.assertEqual(m_unknown.durum, "TANIMSIZ_KULLANICI_GIRDILMELI")
        self.assertEqual(m_unknown.eslesen_fonksiyon, "")

        # 4. Batch layer crosswalk execution test
        src_layer = QgsVectorLayer("Polygon?crs=epsg:5254&field=P_FONK:string", "saha_kaynak", "memory")
        src_pr = src_layer.dataProvider()

        f1 = QgsFeature(src_layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        f1.setAttribute("P_FONK", "KONUT")

        f2 = QgsFeature(src_layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(10, 0, 20, 10)))
        f2.setAttribute("P_FONK", "KARMA_KULLANIM")

        f3 = QgsFeature(src_layer.fields())
        f3.setGeometry(QgsGeometry.fromRect(QgsRectangle(20, 0, 30, 10)))
        f3.setAttribute("P_FONK", "BILINMEYEN")

        src_pr.addFeatures([f1, f2, f3])
        self.assertEqual(src_layer.featureCount(), 3)

        target_layer = QgsVectorLayer(
            "Polygon?crs=epsg:5254&field=fonksiyon_adi:string&field=ust_grup_adi:string&field=aciklama:string",
            "uip_hedef",
            "memory",
        )
        res = execute_layer_crosswalk(src_layer, target_layer, source_field_name="P_FONK")
        self.assertEqual(res["toplam_nesne"], 3)
        self.assertEqual(res["otomatik_eslesen"], 1)
        self.assertEqual(res["onay_bekleyen"], 1)
        self.assertEqual(res["tanimsiz"], 1)

        # Check target feature attributes
        feats = list(target_layer.getFeatures())
        # Konut was auto assigned
        self.assertEqual(feats[0]["fonksiyon_adi"], "YERLEŞİK KONUT ALANI")
        # Karma was left empty with pending notice
        self.assertEqual(feats[1]["fonksiyon_adi"], "")
        self.assertIn("ONAY_BEKLIYOR", feats[1]["aciklama"])
        # Unknown was left empty
        self.assertEqual(feats[2]["fonksiyon_adi"], "")

    def test_urban_synthesis_engine(self):
        """Kriter 9: Kentsel sentez (majority-overlap, TAKS/KAKS, risk, donatı açığı) doğrulanır."""
        # 1. Majority Overlap
        parcel_geom = QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100))  # 10,000 m2
        plan_fields = QgsFields()
        plan_fields.append(QgsField("fonksiyon_adi"))

        plan_f1 = QgsFeature(plan_fields)
        plan_f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 70, 100)))  # 70%
        plan_f1.setAttribute("fonksiyon_adi", "YERLEŞİK KONUT ALANI")

        plan_f2 = QgsFeature(plan_fields)
        plan_f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(70, 0, 100, 100)))  # 30%
        plan_f2.setAttribute("fonksiyon_adi", "PARK")

        func, ratio = SynthesisEngine.calculate_majority_overlap(parcel_geom, [plan_f1, plan_f2])
        self.assertEqual(func, "YERLEŞİK KONUT ALANI")
        self.assertAlmostEqual(ratio, 0.70, places=2)

        # 2. Building Density and Structural Risk
        b_fields = QgsFields()
        b_fields.append(QgsField("B_KAT"))
        b_fields.append(QgsField("B_DURUM"))

        b1 = QgsFeature(b_fields)
        b1.setGeometry(QgsGeometry.fromRect(QgsRectangle(10, 10, 30, 30)))  # 400 m2
        b1.setAttribute("B_KAT", 4)
        b1.setAttribute("B_DURUM", "İYİ")

        b2 = QgsFeature(b_fields)
        b2.setGeometry(QgsGeometry.fromRect(QgsRectangle(40, 10, 60, 30)))  # 400 m2
        b2.setAttribute("B_KAT", 2)
        b2.setAttribute("B_DURUM", "METRUK")

        metrics = SynthesisEngine.analyze_parcel_buildings(parcel_geom, [b1, b2])
        self.assertEqual(metrics["bina_sayisi"], 2)
        self.assertEqual(metrics["toplam_taban_alani"], 800.0)
        self.assertEqual(metrics["toplam_insaat_alani"], 400 * 4 + 400 * 2)  # 2400 m2
        self.assertEqual(metrics["riskli_bina_sayisi"], 1)

        # Full parcel synthesis result
        p_fields = QgsFields()
        p_fields.append(QgsField("ADA"))
        p_fields.append(QgsField("PARSEL"))
        p_feat = QgsFeature(p_fields)
        p_feat.setGeometry(parcel_geom)
        p_feat.setAttribute("ADA", "101")
        p_feat.setAttribute("PARSEL", "5")

        syn = SynthesisEngine.synthesize_parcel(p_feat, [plan_f1, plan_f2], [b1, b2])
        self.assertEqual(syn.parcel_id, "101/5")
        self.assertEqual(syn.hakim_plan_fonksiyonu, "YERLEŞİK KONUT ALANI")
        self.assertAlmostEqual(syn.hesaplanan_taks, 0.08, places=2)  # 800 / 10000
        self.assertAlmostEqual(syn.hesaplanan_kaks, 0.24, places=2)  # 2400 / 10000
        self.assertEqual(syn.riskli_bina_sayisi, 1)

        # 3. Amenity Deficit Analysis
        deficit_res = SynthesisEngine.analyze_amenity_deficit(
            population=1000,
            existing_green_area_m2=4000.0,
            region_name="Örnek Mahalle",
        )
        self.assertEqual(deficit_res.gerekli_yesil_alan_m2, 10000.0)
        self.assertEqual(deficit_res.yesil_alan_acigi_m2, 6000.0)
        self.assertEqual(deficit_res.yeterlilik_durumu, "YETERSIZ")

        sufficient_res = SynthesisEngine.analyze_amenity_deficit(
            population=1000,
            existing_green_area_m2=12000.0,
        )
        self.assertEqual(sufficient_res.yesil_alan_acigi_m2, 0.0)
        self.assertEqual(sufficient_res.yeterlilik_durumu, "YETERLI")

    def test_setback_envelope_geometry(self):
        """Kriter 10: Çekme mesafesi (setback) iç tampon geometrisi hesaplaması doğrulanır."""
        parcel_geom = QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100))  # 10,000 m2
        envelope_5m = calculate_setback_envelope(parcel_geom, 5.0)

        self.assertTrue(envelope_5m.isGeosValid())
        self.assertFalse(envelope_5m.isEmpty())
        # With 5m setback on all sides of 100x100 square, inner square is ~90x90 = 8100 m2
        self.assertLess(envelope_5m.area(), parcel_geom.area())
        self.assertAlmostEqual(envelope_5m.area(), 8100.0, delta=100.0)

        # Zero or negative setback returns original
        same_geom = calculate_setback_envelope(parcel_geom, 0.0)
        self.assertAlmostEqual(same_geom.area(), parcel_geom.area(), delta=0.1)

    def test_quality_control_engine(self):
        """Kriter QC: Parsel çakışmaları, bina tecavüzleri ve çekme ihlalleri tespit edilir."""
        # 1. Overlapping parcels
        p1 = QgsFeature()
        p1.setId(1)
        p1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))

        p2 = QgsFeature()
        p2.setId(2)
        p2.setGeometry(QgsGeometry.fromRect(QgsRectangle(50, 0, 150, 100)))  # 50m overlap

        overlaps = QualityControlEngine.check_parcel_overlaps([p1, p2])
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0].tur, "PARSEL_CAKISMA")
        self.assertEqual(overlaps[0].ciddiyet, "HATA")

        # 2. Building outside/spilling
        b_spill = QgsFeature()
        b_spill.setId(10)
        b_spill.setGeometry(QgsGeometry.fromRect(QgsRectangle(80, 20, 130, 60)))  # partially outside p1 (when p2 not present)

        spills = QualityControlEngine.check_building_spills([p1], [b_spill])
        self.assertEqual(len(spills), 1)
        self.assertEqual(spills[0].tur, "BINA_TECAVUZ")

        # 3. Setback violation (building within 5m margin)
        b_setback = QgsFeature()
        b_setback.setId(20)
        b_setback.setGeometry(QgsGeometry.fromRect(QgsRectangle(2, 2, 20, 20)))  # inside 5m setback

        violations = QualityControlEngine.check_setback_violations([p1], [b_setback], default_setback_m=5.0)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].tur, "CEKME_IHLALI")

    def test_processing_provider_and_all_algorithms(self):
        """The provider registers every supported Processing algorithm."""
        provider = MPYYProvider()
        provider.loadAlgorithms()
        alg_names = [a.name() for a in provider.algorithms()]
        self.assertEqual(len(alg_names), 86)
        self.assertIn("create_land_use_workspace", alg_names)
        self.assertIn("preview_workspace_reconciliation", alg_names)
        self.assertIn("audit_msp_plan_requirements", alg_names)
        self.assertIn("audit_cdp_plan_requirements", alg_names)
        self.assertIn("audit_nip_plan_requirements", alg_names)
        self.assertIn("audit_uip_plan_requirements", alg_names)
        self.assertIn("audit_plan_hierarchy_consistency", alg_names)
        self.assertIn("audit_plan_submission_dossier", alg_names)
        self.assertIn("screen_mpyy_threshold_constraints", alg_names)
        self.assertIn("audit_mpyy_road_plan_change", alg_names)
        self.assertIn("audit_mpyy_density_height_change", alg_names)
        self.assertIn("evaluate_msp_action_monitoring", alg_names)
        self.assertIn("classify_cdp_revision_scope", alg_names)
        self.assertIn("audit_nip_uip_active_mobility_network", alg_names)
        self.assertIn("audit_mpyy_evidence_provenance", alg_names)
        self.assertIn("audit_institution_opinion_register", alg_names)
        self.assertIn("analyze_nip_uip_routed_accessibility", alg_names)
        self.assertIn("audit_adjacent_plan_boundary_consistency", alg_names)
        self.assertIn("audit_plan_fabric_topology", alg_names)
        self.assertIn("audit_mpyy_plan_report_content", alg_names)
        self.assertIn("audit_mpyy_article12_walking_distances", alg_names)
        self.assertIn("audit_conservation_plan_dossier", alg_names)
        self.assertIn("audit_integrated_coastal_plan_dossier", alg_names)
        self.assertIn("audit_urban_design_project_prerequisites", alg_names)
        self.assertIn("audit_mpyy_article8_research_dossier", alg_names)
        self.assertIn("audit_mpyy_article10_official_legend", alg_names)
        self.assertIn("audit_mpyy_article11_standards_context", alg_names)
        self.assertIn("classify_mpyy_article25_plan_intervention", alg_names)
        self.assertIn("consolidate_mpyy_audit_reports", alg_names)
        self.assertIn("initialize_mpyy_plan_dossier", alg_names)
        self.assertIn("audit_mpyy_dossier_completeness", alg_names)
        self.assertIn("audit_mpyy_evidence_freshness", alg_names)
        self.assertIn("audit_mpyy_mixed_use_details", alg_names)
        self.assertIn("audit_mpyy_publication_objection_register", alg_names)
        self.assertIn("audit_mpyy_participation_register", alg_names)
        self.assertIn("audit_mpyy_cancelled_plan_evidence", alg_names)
        self.assertIn("audit_mpyy_plan_component_consistency", alg_names)
        self.assertIn("audit_mpyy_approval_sheet_register", alg_names)
        self.assertIn("audit_mpyy_digital_delivery_package", alg_names)
        self.assertIn("audit_mpyy_gpkg_schema_profile", alg_names)
        self.assertIn("generate_mpyy_dossier_inventory", alg_names)
        self.assertIn("audit_mpyy_plan_note_decision_links", alg_names)
        self.assertIn("audit_mpyy_version_chain", alg_names)
        self.assertIn("analyze_mpyy_multimodal_accessibility", alg_names)
        self.assertIn("analyze_mpyy_building_morphology", alg_names)
        self.assertIn("analyze_mpyy_spacematrix_density", alg_names)
        self.assertIn("analyze_mpyy_street_network_morphology", alg_names)
        self.assertIn("compare_mpyy_plan_scenarios", alg_names)
        self.assertIn("analyze_mpyy_accessibility_equity", alg_names)
        self.assertIn("compare_mpyy_accessibility_scenarios", alg_names)
        self.assertIn("import_mpyy_gpkg_schema_profile", alg_names)
        self.assertIn("audit_mpyy_schema_profile_identity", alg_names)
        self.assertIn("ingest_vector_dataset", alg_names)
        self.assertIn("calculate_building_envelope", alg_names)
        self.assertIn("crosswalk_saha_to_plan", alg_names)
        self.assertIn("synthesize_parcel_density", alg_names)
        self.assertIn("validate_quality_control", alg_names)
        self.assertIn("package_for_qfield", alg_names)
        self.assertIn("clean_planning_geometries", alg_names)
        self.assertIn("export_planning_report", alg_names)
        self.assertIn("analyze_amenity_standards", alg_names)
        self.assertIn("evaluate_plan_revision", alg_names)
        self.assertIn("calculate_dop_reallocation", alg_names)
        self.assertIn("estimate_plan_capacity", alg_names)
        self.assertIn("validate_paiy_compliance", alg_names)
        self.assertIn("generate_pafta_grid", alg_names)
        self.assertIn("generate_plan_notes", alg_names)
        self.assertIn("generate_comprehensive_report", alg_names)
        self.assertIn("apply_corner_chamfer", alg_names)
        self.assertIn("generate_print_layout", alg_names)
        self.assertIn("calculate_parking_requirement", alg_names)
        self.assertIn("prioritize_urban_transformation", alg_names)
        self.assertIn("generate_zoning_certificate", alg_names)
        self.assertIn("calculate_shelter_requirement", alg_names)
        self.assertIn("generate_land_readjustment_matrix", alg_names)
        self.assertIn("evaluate_transformation_feasibility", alg_names)



    def test_all_amenity_standards_matrix(self):
        """Kriter MPYY Ek-2: Tüm asgari donatı standartları kişi başı hesaplanır."""
        areas = {
            "Açık ve Yeşil Alan": 50000.0,
            "Eğitim Tesisleri": 15000.0,
            "Sağlık Tesisleri": 12000.0,
        }
        results = SynthesisEngine.analyze_all_amenities(5000, areas)
        self.assertEqual(len(results), 8)
        green_res = next(r for r in results if "Yeşil Alan" in r.bolge_adi)
        self.assertEqual(green_res.gerekli_yesil_alan_m2, 50000.0)
        self.assertEqual(green_res.yesil_alan_acigi_m2, 0.0)
        self.assertEqual(green_res.yeterlilik_durumu, "YETERLİ")

    def test_ingest_vector_dataset_algorithm(self):
        """Kriter Ingest: Harici CAD/GIS katmanı MPYY tablosuna otomatik alan eşleme ile aktarılır."""
        from planx_mpyy_studio.core.db_factory import create_land_use_workspace
        from planx_mpyy_studio.provider import IngestVectorDatasetAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        p_gpkg = Path(self.tmp.name) / "ingest_test.gpkg"
        create_land_use_workspace(p_gpkg, "EPSG:5254")

        # Create external source layer with colloquial field names
        uri = "MultiPolygon?crs=EPSG:5254&field=ada_no:string&field=parsel_no:string&field=kullanim:string&field=kat:integer&field=mahalle_adi:string"
        src_layer = QgsVectorLayer(uri, "external_cadastre", "memory")
        pr = src_layer.dataProvider()

        feat = QgsFeature(src_layer.fields())
        feat.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 40)))  # 2000 m2
        feat["ada_no"] = "202"
        feat["parsel_no"] = "5"
        feat["kullanim"] = "TICARET"
        feat["kat"] = 3
        feat["mahalle_adi"] = "ATATÜRK"
        pr.addFeature(feat)

        target_layer = QgsVectorLayer(f"{p_gpkg}|layername=parsel_saha", "parsel_saha", "ogr")
        self.assertTrue(target_layer.isValid())

        alg = IngestVectorDatasetAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "INPUT": src_layer,
            "TARGET_LAYER": target_layer,
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res["IMPORTED_COUNT"], 1)

        # Verify ingested feature in target layer
        target_layer.reload()
        features = list(target_layer.getFeatures())
        self.assertEqual(len(features), 1)
        imported_feat = features[0]
        self.assertEqual(imported_feat["ADA"], "202")
        self.assertEqual(imported_feat["PARSEL"], "5")
        self.assertEqual(imported_feat["P_FONK"], "TICARET")
        self.assertEqual(imported_feat["P_KAT"], 3)
        self.assertEqual(imported_feat["MAHALLE"], "ATATÜRK")
        self.assertAlmostEqual(imported_feat["alan_m2"], 2000.0, places=1)
        self.assertTrue(len(imported_feat["global_id"]) > 20)

    def test_mpyy_ek2_amenity_standards_algorithm(self):
        """Kriter MPYY Ek-2 Processing: Mekânsal plan katmanından donatılar taranır ve standart tablosu üretilir."""
        from planx_mpyy_studio.provider import AnalyzeAmenityStandardsAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=detay_katalogu:string&field=alan_m2:double"
        plan_layer = QgsVectorLayer(uri, "test_plan", "memory")
        pr = plan_layer.dataProvider()

        # Park: 30,000 m2
        f1 = QgsFeature(plan_layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 300, 100)))
        f1["detay_katalogu"] = "PARK"
        f1["alan_m2"] = 30000.0

        # Ilkokul: 10,000 m2
        f2 = QgsFeature(plan_layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 100, 100, 200)))
        f2["detay_katalogu"] = "ILKOKUL"
        f2["alan_m2"] = 10000.0

        pr.addFeatures([f1, f2])

        alg = AnalyzeAmenityStandardsAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "PLAN_LAYER": plan_layer,
            "POPULATION": 3000,
            "FIELD": "detay_katalogu",
            "OUTPUT": "memory:ek2_result",
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res["TOTAL_POPULATION"], 3000)
        self.assertAlmostEqual(res["TOTAL_AMENITY_M2"], 40000.0, places=1)
        self.assertIn("DEFICIT_COUNT", res)

    def test_mpyy_madde26_plan_revision_diff(self):
        """Kriter MPYY Madde 26: İmar planı değişikliğinde kaldırılan donatının eşdeğer alan denetimi."""
        from planx_mpyy_studio.core.plan_diff import PlanRevisionDiffEngine
        from planx_mpyy_studio.provider import EvaluatePlanRevisionAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string&field=ustkonugrup:string"
        curr_layer = QgsVectorLayer(uri, "current_plan", "memory")
        pr_curr = curr_layer.dataProvider()

        c1 = QgsFeature(curr_layer.fields())
        c1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        c1["uipfonksiyon"] = "PARK"
        c1["ustkonugrup"] = "AÇIK VE YEŞİL ALANLAR"

        c2 = QgsFeature(curr_layer.fields())
        c2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 200, 100)))
        c2["uipfonksiyon"] = "GELİŞME KONUT ALANI"
        c2["ustkonugrup"] = "KONUT ALANLARI"
        pr_curr.addFeatures([c1, c2])

        rev_layer = QgsVectorLayer(uri, "revised_plan", "memory")
        pr_rev = rev_layer.dataProvider()

        r1 = QgsFeature(rev_layer.fields())
        r1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        r1["uipfonksiyon"] = "TICARET KONUT ALANI"
        r1["ustkonugrup"] = "KARMA KULLANIM ALANLARI"

        r2 = QgsFeature(rev_layer.fields())
        r2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 200, 100)))
        r2["uipfonksiyon"] = "GELİŞME KONUT ALANI"
        r2["ustkonugrup"] = "KONUT ALANLARI"

        r3 = QgsFeature(rev_layer.fields())
        r3.setGeometry(QgsGeometry.fromRect(QgsRectangle(300, 0, 400, 100)))
        r3["uipfonksiyon"] = "PARK"
        r3["ustkonugrup"] = "AÇIK VE YEŞİL ALANLAR"
        pr_rev.addFeatures([r1, r2, r3])

        diff_feats, summary = PlanRevisionDiffEngine.evaluate_revision(
            list(curr_layer.getFeatures()),
            list(rev_layer.getFeatures()),
            service_radius_m=500.0,
        )

        self.assertGreater(len(diff_feats), 0)
        types = [df.degisim_turu for df in diff_feats]
        self.assertIn("DONATI_KALDIRILDI", types)
        self.assertIn("KORUNAN", types)
        self.assertIn("YENI_DONATI_EKLENDI", types)

        removed_item = next(df for df in diff_feats if df.degisim_turu == "DONATI_KALDIRILDI")
        self.assertTrue(removed_item.esdeger_alan_uygun)
        self.assertEqual(summary.kaldirilan_donati_m2, 10000.0)
        self.assertEqual(summary.yeni_eklenen_donati_m2, 10000.0)
        self.assertTrue(summary.madde_26_uygunlugu)

        alg = EvaluatePlanRevisionAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "CURRENT_PLAN": curr_layer,
            "REVISED_PLAN": rev_layer,
            "SERVICE_RADIUS": 500.0,
            "OUTPUT": "memory:diff_output",
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res["REMOVED_AMENITY_M2"], 10000.0)
        self.assertEqual(res["ADDED_AMENITY_M2"], 10000.0)
        self.assertTrue(res["MADDE_26_COMPLIANT"])

    def test_mpyy_madde18_dop_engine_and_algorithm(self):
        """Kriter MPYY Madde 18: Kadastro parselleri ve terk alanları üzerinden DOP ve tahsis hesabı."""
        from planx_mpyy_studio.core.dop_engine import DOPEngine
        from planx_mpyy_studio.provider import CalculateDOPAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=ada:string&field=parsel:string&field=malik:string"
        cad_layer = QgsVectorLayer(uri, "cadastre_test", "memory")
        pr = cad_layer.dataProvider()

        # Parcel 1: 6,000 m2 (60 x 100)
        p1 = QgsFeature(cad_layer.fields())
        p1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 60, 100)))
        p1["ada"] = "101"
        p1["parsel"] = "1"
        p1["malik"] = "Ahmet Yılmaz"

        # Parcel 2: 4,000 m2 (40 x 100)
        p2 = QgsFeature(cad_layer.fields())
        p2.setGeometry(QgsGeometry.fromRect(QgsRectangle(60, 0, 100, 100)))
        p2["ada"] = "101"
        p2["parsel"] = "2"
        p2["malik"] = "Ayşe Kaya"

        pr.addFeatures([p1, p2])

        # Public area layer: 4,000 m2 (DOPO = 4,000 / 10,000 = 0.40 <= 0.45)
        pub_layer = QgsVectorLayer(uri, "public_test", "memory")
        pr_pub = pub_layer.dataProvider()
        pub1 = QgsFeature(pub_layer.fields())
        pub1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 40, 100)))
        pub1["ada"] = "PARK"
        pub1["parsel"] = "1"
        pr_pub.addFeature(pub1)

        # 1. Direct Engine Test (Scenario A: DOPO <= 0.45)
        results, summary = DOPEngine.calculate_dop(
            cadastral_features=list(cad_layer.getFeatures()),
            public_features=list(pub_layer.getFeatures()),
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(summary.toplam_kadastro_m2, 10000.0)
        self.assertEqual(summary.toplam_terk_m2, 4000.0)
        self.assertAlmostEqual(summary.dop_orani, 0.40, places=4)
        self.assertTrue(summary.yasal_uygun)
        self.assertEqual(results[0].dop_kesintisi_m2, 2400.0)
        self.assertEqual(results[0].net_tahsis_m2, 3600.0)
        self.assertEqual(results[1].dop_kesintisi_m2, 1600.0)
        self.assertEqual(results[1].net_tahsis_m2, 2400.0)

        # Scenario B: DOPO > 0.45 (Excess ceiling warning)
        _, summary_excess = DOPEngine.calculate_dop(
            cadastral_features=list(cad_layer.getFeatures()),
            manual_public_area_m2=5000.0,  # 50%
        )
        self.assertFalse(summary_excess.yasal_uygun)
        self.assertAlmostEqual(summary_excess.dop_orani, 0.50, places=4)
        self.assertEqual(summary_excess.kop_veya_kamulastirma_gerekli_m2, 500.0)

        # 2. Algorithm Test
        alg = CalculateDOPAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "CADASTRE_LAYER": cad_layer,
            "PUBLIC_LAYER": pub_layer,
            "OUTPUT": "memory:dop_output",
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res["TOTAL_CADASTRE_M2"], 10000.0)
        self.assertEqual(res["TOTAL_PUBLIC_M2"], 4000.0)
        self.assertTrue(res["COMPLIANT_WITH_CEILING"])
        self.assertEqual(res["PARCEL_COUNT"], 2)

    def test_mpyy_plan_capacity_and_population_modeling(self):
        """Kriter İmar Kapasitesi: Zonlama poligonları üzerinden TAKS/KAKS, konut ve nüfus modellemesi."""
        from planx_mpyy_studio.core.capacity_engine import PlanCapacityEngine
        from planx_mpyy_studio.provider import EstimatePlanCapacityAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string&field=kaks:double&field=taks:double"
        plan_layer = QgsVectorLayer(uri, "plan_capacity_test", "memory")
        pr = plan_layer.dataProvider()

        # Residential zone: 10,000 m2 (100 x 100), KAKS = 1.5, TAKS = 0.35
        f1 = QgsFeature(plan_layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        f1["uipfonksiyon"] = "GELİŞME KONUT ALANI"
        f1["kaks"] = 1.5
        f1["taks"] = 0.35

        # Mixed-use zone: 10,000 m2, KAKS = 2.0, TAKS = 0.40
        f2 = QgsFeature(plan_layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 200, 100)))
        f2["uipfonksiyon"] = "TİCARET KONUT ALANI"
        f2["kaks"] = 2.0
        f2["taks"] = 0.40

        pr.addFeatures([f1, f2])

        # 1. Direct Engine Test
        items, summary = PlanCapacityEngine.estimate_capacity(
            plan_features=list(plan_layer.getFeatures()),
            avg_unit_m2=100.0,
            household_size=3.2,
        )
        self.assertEqual(len(items), 2)
        # Total residential construction: 15,000 + (20,000 * 0.6) = 27,000 m2
        self.assertEqual(summary.toplam_insaat_m2, 35000.0)  # Gross GFA
        self.assertEqual(summary.toplam_konut_sayisi, 270)   # 150 + 120
        self.assertEqual(summary.toplam_kapasite_nufusu, 864)  # 480 + 384
        self.assertGreater(summary.brut_yogunluk_kisi_ha, 0)
        self.assertGreater(len(summary.donati_yeterlilik), 0)

        # 2. Algorithm Test
        alg = EstimatePlanCapacityAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "PLAN_LAYER": plan_layer,
            "DEFAULT_KAKS": 1.5,
            "DEFAULT_TAKS": 0.35,
            "AVG_UNIT_M2": 100.0,
            "HOUSEHOLD_SIZE": 3.2,
            "OUTPUT": "memory:capacity_output",
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res["TOTAL_UNITS"], 270)
        self.assertEqual(res["TOTAL_POPULATION"], 864)

    def test_mpyy_paiy_compliance_engine_and_algorithm(self):
        """Kriter PAİY: Parsellerin nizam, cephe, derinlik, alan ve çekme zarfı denetimi."""
        from planx_mpyy_studio.core.compliance_engine import ComplianceEngine
        from planx_mpyy_studio.provider import ValidatePAIYComplianceAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=ada:string&field=parsel:string&field=nizam:string&field=kat:integer"
        layer = QgsVectorLayer(uri, "paiy_test_parcels", "memory")
        pr = layer.dataProvider()

        # Parcel 1: 15m x 30m = 450 m2 (AYRIK, 4 kat) -> YAPILASABILIR (area >= 300, frontage >= 12)
        p1 = QgsFeature(layer.fields())
        p1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 15, 30)))
        p1["ada"] = "201"
        p1["parsel"] = "1"
        p1["nizam"] = "AYRIK"
        p1["kat"] = 4

        # Parcel 2: 30m x 30m = 900 m2 (AYRIK, 4 kat) -> IFRAZ_EDILEBILIR (area >= 600, frontage >= 24)
        p2 = QgsFeature(layer.fields())
        p2.setGeometry(QgsGeometry.fromRect(QgsRectangle(20, 0, 50, 30)))
        p2["ada"] = "201"
        p2["parsel"] = "2"
        p2["nizam"] = "AYRIK"
        p2["kat"] = 4

        # Parcel 3: 8m x 20m = 160 m2 (AYRIK, 4 kat) -> TEVHID_ZORUNLU (frontage 8m < 12m, area 160 < 300)
        p3 = QgsFeature(layer.fields())
        p3.setGeometry(QgsGeometry.fromRect(QgsRectangle(60, 0, 68, 20)))
        p3["ada"] = "201"
        p3["parsel"] = "3"
        p3["nizam"] = "AYRIK"
        p3["kat"] = 4

        pr.addFeatures([p1, p2, p3])

        # 1. Direct Engine Test
        results, summary = ComplianceEngine.evaluate_parcels(list(layer.getFeatures()))
        self.assertEqual(len(results), 3)
        self.assertEqual(summary.toplam_parsel_sayisi, 3)

        res_map = {r.parsel: r for r in results}
        self.assertEqual(res_map["1"].durum, "YAPILASABILIR")
        self.assertEqual(res_map["2"].durum, "IFRAZ_EDILEBILIR")
        self.assertEqual(res_map["3"].durum, "TEVHID_ZORUNLU")

        # 2. Algorithm Test
        alg = ValidatePAIYComplianceAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "PARCEL_LAYER": layer,
            "DEFAULT_NIZAM": 0,
            "DEFAULT_FLOORS": 4,
            "FRONT_SETBACK": 5.0,
            "SIDE_SETBACK": 3.0,
            "OUTPUT": "memory:paiy_output",
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res["TOTAL_PARCELS"], 3)
        self.assertEqual(res["BUILDABLE_COUNT"], 2)
        self.assertEqual(res["TEVHID_REQUIRED_COUNT"], 1)

    def test_mpyy_pafta_grid_generator_and_algorithm(self):
        """Kriter Paftalama: İmar planı kapsamı üzerinden standart 1/1.000 pafta gridi ve indeksi üretimi."""
        from planx_mpyy_studio.core.pafta_index import PaftaGridEngine
        from planx_mpyy_studio.provider import GeneratePaftaGridAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=fonk:string"
        layer = QgsVectorLayer(uri, "plan_extent_test", "memory")
        pr = layer.dataProvider()

        # Plan polygon from (100, 100) to (1100, 900)
        # Snapped to 500m grid: X in [0, 1500] (3 cols), Y in [0, 1000] (2 rows) -> 6 paftas
        f = QgsFeature(layer.fields())
        f.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 100, 1100, 900)))
        f["fonk"] = "KONUT"
        pr.addFeature(f)

        # 1. Direct Engine Test
        sheets, summary = PaftaGridEngine.generate_sheet_grid(
            extent=layer.extent(),
            scale_name="1/1.000",
            plan_features=list(layer.getFeatures()),
            prefix="İ22-c",
        )
        self.assertGreater(len(sheets), 0)
        self.assertEqual(summary.olcek, "1/1.000")
        self.assertEqual(summary.hucre_genisligi_m, 500.0)
        self.assertTrue(sheets[0].pafta_no.startswith("İ22-c"))

        # 2. Algorithm Test
        alg = GeneratePaftaGridAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "PLAN_LAYER": layer,
            "SCALE": 0,  # 1/1.000
            "PREFIX": "K21-b",
            "OUTPUT": "memory:pafta_output",
        }
        res = alg.processAlgorithm(params, ctx, fb)
        self.assertGreater(res["TOTAL_SHEETS"], 0)

    def test_mpyy_plan_notes_engine_and_algorithm(self):
        """Kriter Plan Notları: MPYY standartlarına uygun genel, özel, jeolojik ve Madde 18 plan hükümleri sentezi."""
        from planx_mpyy_studio.core.plan_notes import PlanNotesEngine
        from planx_mpyy_studio.provider import GeneratePlanNotesAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback
        import tempfile

        uri = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string&field=ustkonugrup:string"
        layer = QgsVectorLayer(uri, "plan_notes_test", "memory")
        pr = layer.dataProvider()

        f1 = QgsFeature(layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 50)))
        f1["uipfonksiyon"] = "GELİŞME KONUT ALANI"
        f1["ustkonugrup"] = "KONUT ALANLARI"

        f2 = QgsFeature(layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(50, 0, 100, 50)))
        f2["uipfonksiyon"] = "PARK VE ÇOCUK BAHÇESİ"
        f2["ustkonugrup"] = "AÇIK VE YEŞİL ALANLAR"

        f3 = QgsFeature(layer.fields())
        f3.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 50, 50, 100)))
        f3["uipfonksiyon"] = "İLKOKUL ALANI"
        f3["ustkonugrup"] = "EĞİTİM ALANLARI"

        f4 = QgsFeature(layer.fields())
        f4.setGeometry(QgsGeometry.fromRect(QgsRectangle(50, 50, 100, 100)))
        f4["uipfonksiyon"] = "AİLE SAĞLIĞI MERKEZİ"
        f4["ustkonugrup"] = "SAĞLIK ALANLARI"

        pr.addFeatures([f1, f2, f3, f4])

        # 1. Direct Engine Test
        feats = list(layer.getFeatures())
        detected = PlanNotesEngine.detect_categories(feats)
        self.assertIn("KONUT", detected)
        self.assertIn("PARK_YESIL", detected)
        self.assertIn("EGITIM", detected)
        self.assertIn("SAGLIK", detected)

        notes = PlanNotesEngine.generate_plan_notes(
            plan_title="Örnek 1/1.000 UİP",
            scale="1/1.000",
            features=feats,
            include_geology=True,
            include_article18=True,
        )
        self.assertEqual(notes.plan_adi, "Örnek 1/1.000 UİP")
        self.assertGreaterEqual(len(notes.genel_hukumler), 5)
        self.assertIn('KONUT ALANLARI', notes.ozel_hukumler)
        self.assertIn('Park ve Yeşil Alanlar', notes.ozel_hukumler)
        self.assertIn('Eğitim Tesis Alanları', notes.ozel_hukumler)
        self.assertIn('Sağlık Tesis Alanları', notes.ozel_hukumler)
        self.assertGreater(len(notes.jeolojik_hukumler), 0)
        self.assertGreater(len(notes.uygulama_hukumleri), 0)
        self.assertIn("# ÖRNEK 1/1.000 UİP", notes.markdown_text)
        self.assertIn("<!DOCTYPE html>", notes.html_text)

        # 2. Algorithm Test
        with tempfile.TemporaryDirectory() as tmpdir:
            md_out = str(Path(tmpdir) / "notes.md")
            html_out = str(Path(tmpdir) / "notes.html")

            alg = GeneratePlanNotesAlgorithm()
            alg.initAlgorithm()
            ctx = QgsProcessingContext()
            fb = QgsProcessingFeedback()
            params = {
                "PLAN_LAYER": layer,
                "PLAN_TITLE": "Test Planı",
                "PLAN_SCALE": "1/1.000",
                "INCLUDE_GEOLOGY": True,
                "INCLUDE_ARTICLE18": True,
                "OUTPUT_MD": md_out,
                "OUTPUT_HTML": html_out,
            }
            res = alg.processAlgorithm(params, ctx, fb)
            self.assertGreaterEqual(res["CATEGORY_COUNT"], 4)
            self.assertTrue(Path(md_out).exists())
            self.assertTrue(Path(html_out).exists())

    def test_mpyy_comprehensive_report_engine_and_algorithm(self):
        """Kriter Açıklama Raporu: MPYY standartlarında arazi bilançosu ve kapsamlı plan açıklama raporu üretimi."""
        from planx_mpyy_studio.core.report_exporter import PlanReportEngine
        from planx_mpyy_studio.provider import GenerateComprehensiveReportAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback
        import tempfile

        uri = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string&field=ustkonugrup:string"
        layer = QgsVectorLayer(uri, "report_test", "memory")
        pr = layer.dataProvider()

        f1 = QgsFeature(layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))  # 10,000 m2
        f1["uipfonksiyon"] = "GELİŞME KONUT ALANI"
        f1["ustkonugrup"] = "KONUT ALANLARI"

        f2 = QgsFeature(layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 150, 100)))  # 5,000 m2
        f2["uipfonksiyon"] = "PARK VE YEŞİL ALAN"
        f2["ustkonugrup"] = "AÇIK VE YEŞİL ALANLAR"

        pr.addFeatures([f1, f2])

        feats = list(layer.getFeatures())

        # 1. Balance Engine Test
        rows, total_area = PlanReportEngine.compute_land_use_balance(feats)
        self.assertEqual(len(rows), 2)
        self.assertEqual(total_area, 15000.0)
        self.assertAlmostEqual(rows[0].yuzde + rows[1].yuzde, 100.0, places=1)

        # 2. Report Generation Test
        with tempfile.TemporaryDirectory() as tmpdir:
            res_rep = PlanReportEngine.generate_comprehensive_report(
                output_dir=tmpdir,
                plan_features=feats,
                report_title="Test Açıklama Raporu",
                plan_scale="1/1.000",
            )
            self.assertTrue(Path(res_rep["html_report"]).exists())
            self.assertTrue(Path(res_rep["markdown_report"]).exists())
            self.assertTrue(Path(res_rep["csv_balance"]).exists())
            self.assertEqual(res_rep["total_area_m2"], 15000.0)

            html_content = Path(res_rep["html_report"]).read_text(encoding="utf-8")
            self.assertIn("Test Açıklama Raporu", html_content)
            self.assertIn("Yusuf Eminoğlu", html_content)

            # 3. Algorithm Test
            alg = GenerateComprehensiveReportAlgorithm()
            alg.initAlgorithm()
            ctx = QgsProcessingContext()
            fb = QgsProcessingFeedback()
            params = {
                "PLAN_LAYER": layer,
                "REPORT_TITLE": "Algoritma Raporu",
                "PLAN_SCALE": "1/1.000",
                "OUTPUT_FOLDER": tmpdir,
            }
            res_alg = alg.processAlgorithm(params, ctx, fb)
            self.assertEqual(res_alg["TOTAL_AREA_M2"], 15000.0)
            self.assertTrue(Path(res_alg["HTML_REPORT"]).exists())

    def test_mpyy_corner_chamfer_engine_and_algorithm(self):
        """Kriter Köşe Pahı: PAİY Madde 20 uyarınca ada/parsel köşelerinde kavşak görüş pahı kırımı ve terk hesabı."""
        from planx_mpyy_studio.core.chamfer_engine import ChamferEngine
        from planx_mpyy_studio.provider import ApplyCornerChamferAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        # Create a 20m x 20m square polygon (area: 400 m2)
        poly = QgsGeometry.fromRect(QgsRectangle(0, 0, 20, 20))

        # 1. Direct Engine Test
        # 4 corners cut with chamfer_dist=3.0: each corner is a right triangle of (3x3)/2 = 4.5 m2
        # Total cut area: 4 x 4.5 = 18.0 m2, new area: 382.0 m2
        res = ChamferEngine.apply_chamfer(poly, chamfer_dist=3.0)
        self.assertEqual(res.pah_adedi, 4)
        self.assertAlmostEqual(res.kesilen_alan_m2, 18.0, places=1)
        self.assertAlmostEqual(res.yeni_alan_m2, 382.0, places=1)
        self.assertTrue(res.geometri.isGeosValid())

        # 2. Algorithm Test
        uri = "MultiPolygon?crs=EPSG:5254&field=ada:string&field=parsel:string"
        layer = QgsVectorLayer(uri, "parsel_chamfer_test", "memory")
        pr = layer.dataProvider()
        feat = QgsFeature(layer.fields())
        feat.setGeometry(poly)
        feat["ada"] = "101"
        feat["parsel"] = "1"
        pr.addFeature(feat)

        alg = ApplyCornerChamferAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "INPUT": layer,
            "CHAMFER_DISTANCE": 3.0,
            "MIN_ANGLE": 60.0,
            "MAX_ANGLE": 120.0,
            "OUTPUT": "memory:chamfer_output",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["TOTAL_CHAMFERS"], 4)
        self.assertAlmostEqual(res_alg["TOTAL_CUT_AREA_M2"], 18.0, places=1)

    def test_mpyy_print_layout_composer_and_algorithm(self):
        """Kriter Baskı Paftası: MPYY standart harita, koordinat gridi, lejant ve meclis anteti içeren pafta şablonu."""
        from planx_mpyy_studio.core.layout_composer import MPYYLayoutComposer
        from planx_mpyy_studio.provider import GeneratePrintLayoutAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        # 1. Direct Engine Test
        layout = MPYYLayoutComposer.create_mpyy_layout(
            layout_name="Test_UIP_A1_Paftasi",
            paper_size="A1",
            plan_title="TEST 1/1.000 UYGULAMA İMAR PLANI",
            municipality="İZMİR BÜYÜKŞEHİR BELEDİYESİ",
            pafta_no="İ22-c-04-a",
            plan_scale="1/1.000",
            extent=QgsRectangle(500000, 4200000, 501000, 4201000),
        )
        self.assertIsNotNone(layout)
        self.assertEqual(layout.name(), "Test_UIP_A1_Paftasi")
        page = layout.pageCollection().pages()[0]
        self.assertAlmostEqual(page.pageSize().width(), 841.0, places=0)
        self.assertAlmostEqual(page.pageSize().height(), 594.0, places=0)

        # 2. Algorithm Test
        alg = GeneratePrintLayoutAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "LAYOUT_NAME": "Test_Alg_Layout",
            "PAPER_SIZE": 1,  # A1
            "PLAN_TITLE": "Algoritma Plan Paftası",
            "MUNICIPALITY": "Kadıköy Belediyesi",
            "PAFTA_NO": "G22-a-01-c",
            "PLAN_SCALE": "1/1.000",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["LAYOUT_NAME"], "Test_Alg_Layout")
        self.assertEqual(res_alg["PAPER_SIZE"], "A1")

    def test_mpyy_form_designer_and_constraints(self):
        """Kriter Akıllı Form ve Kısıtlar: ValueMap, $area dinamik ifadeleri, mevzuat kısıtları ve sekmeli form."""
        from planx_mpyy_studio.core.form_designer import MPYYFormDesigner
        from qgis.core import QgsEditFormConfig

        uri = (
            "Polygon?crs=EPSG:5254"
            "&field=uipfonksiyon:string"
            "&field=alan_m2:double"
            "&field=nizam:string"
            "&field=taks:double"
            "&field=kaks:double"
            "&field=katadedi:int"
            "&field=yapiYaklasmaMesafesi:double"
            "&field=ADA:string"
            "&field=PARSEL:string"
            "&field=ada_parsel:string"
            "&field=MULKIYET_TURU:string"
            "&field=yerlesime_uygunluk:string"
        )
        layer = QgsVectorLayer(uri, "smart_form_test", "memory")

        MPYYFormDesigner.apply_complete_form_experience(layer)

        # 1. Tabbed Layout Verification
        cfg = layer.editFormConfig()
        self.assertEqual(cfg.layout(), QgsEditFormConfig.TabLayout)
        root = cfg.invisibleRootContainer()
        self.assertGreaterEqual(len(root.children()), 4)

        # 2. ValueMap Verification
        nizam_idx = layer.fields().indexFromName("nizam")
        self.assertEqual(layer.editorWidgetSetup(nizam_idx).type(), "ValueMap")
        self.assertIn("map", layer.editorWidgetSetup(nizam_idx).config())

        mulkiyet_idx = layer.fields().indexFromName("MULKIYET_TURU")
        self.assertEqual(layer.editorWidgetSetup(mulkiyet_idx).type(), "ValueMap")

        # 3. Default Value Expressions Verification
        area_idx = layer.fields().indexFromName("alan_m2")
        self.assertEqual(layer.defaultValueDefinition(area_idx).expression(), "round($area, 2)")
        self.assertTrue(layer.defaultValueDefinition(area_idx).applyOnUpdate())

        ap_idx = layer.fields().indexFromName("ada_parsel")
        self.assertIn("concat", layer.defaultValueDefinition(ap_idx).expression())

        # 4. Legislative Constraints Verification
        taks_idx = layer.fields().indexFromName("taks")
        self.assertIn("taks", layer.constraintExpression(taks_idx))
        self.assertIn('PAİY', layer.constraintDescription(taks_idx))

        kaks_idx = layer.fields().indexFromName("kaks")
        self.assertIn("kaks", layer.constraintExpression(kaks_idx))

        # 5. Field Aliases Verification
        self.assertIn('Plan Fonksiyonu', layer.attributeAlias(layer.fields().indexFromName("uipfonksiyon")))
        self.assertIn('Parsel', layer.attributeAlias(layer.fields().indexFromName("alan_m2")))
        self.assertIn('Yapı Nizamı', layer.attributeAlias(nizam_idx))

    def test_parking_requirement_engine_and_algorithm(self):
        """Kriter Otopark: Otopark Yönetmeliği uyarınca zorunlu araç ihtiyacı, açık/fazlalık ve karşılama oranı."""
        from planx_mpyy_studio.core.parking_engine import ParkingEngine
        from planx_mpyy_studio.provider import CalculateParkingRequirementAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string&field=kaks:double"
        layer = QgsVectorLayer(uri, "parking_test_layer", "memory")
        pr = layer.dataProvider()

        # 1. Residential parcel: 1000 m2, kaks=1.5 -> gross area = 1500 m2. Rate for KONUT = 150 m2/car -> 10 cars
        f1 = QgsFeature(layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 20)))
        f1["uipfonksiyon"] = "GELISME_KONUT_ALANI"
        f1["kaks"] = 1.5

        # 2. Commercial parcel: 500 m2, kaks=2.0 -> gross area = 1000 m2. Rate for TICARET = 40 m2/car -> 25 cars
        f2 = QgsFeature(layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 150, 10)))
        f2["uipfonksiyon"] = "TICARET_ALANI"
        f2["kaks"] = 2.0

        # 3. Dedicated public parking polygon: 1000 m2 -> 1000 / 25 = 40 cars capacity
        f3 = QgsFeature(layer.fields())
        f3.setGeometry(QgsGeometry.fromRect(QgsRectangle(200, 0, 250, 20)))
        f3["uipfonksiyon"] = "BOLGE_OTOPARKI"
        f3["kaks"] = 0.0

        pr.addFeatures([f1, f2, f3])

        # Engine test
        res_list, summary = ParkingEngine.evaluate_parking_balance(
            features=[f1, f2, f3],
            default_kaks=1.2,
            area_per_car_m2=25.0,
        )
        self.assertEqual(len(res_list), 2)
        self.assertEqual(summary.toplam_otopark_ihtiyaci_arac, 35)
        self.assertEqual(summary.planda_ayrilan_otopark_kapasite_arac, 40)
        self.assertEqual(summary.otopark_acigi_fazlasi_arac, 5)
        self.assertTrue(summary.yeterli_mi)
        self.assertAlmostEqual(summary.karsilama_orani_yuzde, (40 / 35) * 100.0, places=1)

        # Processing algorithm test
        alg = CalculateParkingRequirementAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "INPUT": layer,
            "DEFAULT_KAKS": 1.2,
            "AREA_PER_CAR": 25.0,
            "OUTPUT": "memory:parking_output",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["TOPLAM_IHTIYAC_ARAC"], 35)
        self.assertEqual(res_alg["PLANDA_AYRILAN_ARAC"], 40)
        self.assertEqual(res_alg["OTOPARK_DENGE_ARAC"], 5)
        self.assertTrue(res_alg["YETERLI_MI"])

    def test_urban_transformation_risk_engine_and_algorithm(self):
        """Kriter 6306 Kanun: Bina yaşı, taşıyıcı sistem, hasar ve jeolojik zemin sentezi ile afet risk skoru."""
        from planx_mpyy_studio.core.risk_engine import UrbanTransformationRiskEngine
        from planx_mpyy_studio.provider import PrioritizeUrbanTransformationAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = (
            "MultiPolygon?crs=EPSG:5254"
            "&field=bina_kodu:string"
            "&field=yapim_yili:int"
            "&field=B_YAPI_CINSI:string"
            "&field=B_HASAR_DURUMU:string"
            "&field=kat_adedi:int"
            "&field=yerlesime_uygunluk:string"
        )
        layer = QgsVectorLayer(uri, "risk_test_layer", "memory")
        pr = layer.dataProvider()

        # High risk building: 1985 built (pre-1999: 30 pts), Yığma (22 pts), Ağır hasarlı (25 pts), 4 kat (+4), UOA zemin (+10) = 91 pts -> ACIL_DONUSUM
        f_risk = QgsFeature(layer.fields())
        f_risk.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        f_risk["bina_kodu"] = "BINA-001"
        f_risk["yapim_yili"] = 1985
        f_risk["B_YAPI_CINSI"] = "YIGMA_TUGLA"
        f_risk["B_HASAR_DURUMU"] = "AGIR_HASARLI"
        f_risk["kat_adedi"] = 4
        f_risk["yerlesime_uygunluk"] = "UOA_HEYELAN"

        # Safe modern building: 2022 built (post-2018: 2 pts), Tünel kalıp (5 pts), Hasarsız (1 pt), 6 kat (+7), UA zemin (+1) = 16 pts -> DUSUK_RISK_KONTROLLU
        f_safe = QgsFeature(layer.fields())
        f_safe.setGeometry(QgsGeometry.fromRect(QgsRectangle(20, 0, 30, 10)))
        f_safe["bina_kodu"] = "BINA-002"
        f_safe["yapim_yili"] = 2022
        f_safe["B_YAPI_CINSI"] = "TUNEL_KALIP"
        f_safe["B_HASAR_DURUMU"] = "HASARSIZ"
        f_safe["kat_adedi"] = 6
        f_safe["yerlesime_uygunluk"] = "UA"

        pr.addFeatures([f_risk, f_safe])

        # Engine test
        res_list, summary = UrbanTransformationRiskEngine.evaluate_risk(
            features=[f_risk, f_safe],
            reference_year=2026,
        )
        self.assertEqual(len(res_list), 2)
        res_map = {r.bina_kodu: r for r in res_list}
        self.assertEqual(res_map["BINA-001"].oncelik_grubu, "ACIL_DONUSUM")
        self.assertGreaterEqual(res_map["BINA-001"].toplam_risk_skoru, 75.0)

        self.assertEqual(res_map["BINA-002"].oncelik_grubu, "DUSUK_RISK_KONTROLLU")
        self.assertLess(res_map["BINA-002"].toplam_risk_skoru, 25.0)

        self.assertEqual(summary.toplam_bina_adedi, 2)
        self.assertEqual(summary.acil_donusum_adedi, 1)
        self.assertEqual(summary.dusuk_risk_adedi, 1)
        self.assertAlmostEqual(summary.acil_oncelikli_yuzde, 50.0, places=1)

        # Processing algorithm test
        alg = PrioritizeUrbanTransformationAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "INPUT": layer,
            "REF_YEAR": 2026,
            "OUTPUT": "memory:risk_output",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["TOPLAM_BINA"], 2)
        self.assertEqual(res_alg["ACIL_DONUSUM_SAYISI"], 1)
        self.assertAlmostEqual(res_alg["ACIL_ONCELIKLI_YUZDE"], 50.0, places=1)

    def test_zoning_certificate_engine_and_algorithm(self):
        """Kriter İmar Çapı: Resmi İmar Durumu Belgesi üretimi, azami inşaat kapasitesi ve koordinat cetveli."""
        from planx_mpyy_studio.core.zoning_certificate import ZoningCertificateEngine
        from planx_mpyy_studio.provider import GenerateZoningCertificateAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = (
            "Polygon?crs=EPSG:5254"
            "&field=ada:string"
            "&field=parsel:string"
            "&field=mahalle:string"
            "&field=pafta:string"
            "&field=uipfonksiyon:string"
            "&field=nizam:string"
            "&field=taks:double"
            "&field=kaks:double"
            "&field=katadedi:string"
            "&field=onbahce:double"
            "&field=yanbahce:double"
        )
        layer = QgsVectorLayer(uri, "cert_test_layer", "memory")
        pr = layer.dataProvider()

        # 50m x 20m rectangular parcel (area: 1000 m2)
        poly = QgsGeometry.fromRect(QgsRectangle(500000, 4200000, 500050, 4200020))
        feat = QgsFeature(layer.fields())
        feat.setGeometry(poly)
        feat["ada"] = "205"
        feat["parsel"] = "12"
        feat["mahalle"] = "İSMETPAŞA"
        feat["pafta"] = "İ22-c-04-b"
        feat["uipfonksiyon"] = "GELISME_KONUT_ALANI"
        feat["nizam"] = "AYRIK"
        feat["taks"] = 0.35
        feat["kaks"] = 1.40
        feat["katadedi"] = "4"
        feat["onbahce"] = 5.0
        feat["yanbahce"] = 3.0
        pr.addFeature(feat)

        # 1. Engine Direct Test
        cert = ZoningCertificateEngine.generate_certificate(
            parcel_feature=feat,
            municipality="T.C. İZMİR BÜYÜKŞEHİR BELEDİYESİ",
            ilce="KONAK",
            mahalle="İSMETPAŞA",
            pafta_no="İ22-c-04-b",
        )
        self.assertEqual(cert.ada_no, "205")
        self.assertEqual(cert.parsel_no, "12")
        self.assertEqual(cert.kadastro_alani_m2, 1000.0)
        self.assertEqual(cert.azami_taban_alani_m2, 350.0)
        self.assertEqual(cert.azami_insaat_alani_m2, 1400.0)
        self.assertGreaterEqual(cert.otopark_arac_ihtiyaci, 1)
        self.assertGreaterEqual(len(cert.koordinatlar), 4)
        self.assertIn("<!DOCTYPE html>", cert.html_content)
        self.assertIn('RESMİ İMAR DURUMU BELGESİ', cert.html_content)
        self.assertIn("İSMETPAŞA", cert.html_content)

        # 2. Algorithm Test
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            out_html = str(Path(tmpdir) / "imar_capi.html")
            out_md = str(Path(tmpdir) / "imar_capi.md")

            alg = GenerateZoningCertificateAlgorithm()
            alg.initAlgorithm()
            ctx = QgsProcessingContext()
            fb = QgsProcessingFeedback()
            params = {
                "PARCEL_LAYER": layer,
                "MUNICIPALITY": "T.C. İZMİR BÜYÜKŞEHİR BELEDİYESİ",
                "ILCE": "KONAK",
                "MAHALLE": "İSMETPAŞA",
                "PAFTA_NO": "İ22-c-04-b",
                "OUTPUT_HTML": out_html,
                "OUTPUT_MD": out_md,
            }
            res_alg = alg.processAlgorithm(params, ctx, fb)
            self.assertEqual(res_alg["ADA_PARSEL"], "205/12")
            self.assertEqual(res_alg["INSAAT_ALANI_M2"], 1400.0)
            self.assertTrue(Path(out_html).exists())
            self.assertTrue(Path(out_md).exists())

    def test_shelter_requirement_engine_and_algorithm(self):
        """Kriter Sığınak: Sığınak Yönetmeliği uyarınca zorunlu sığınak eşikleri ve alan hesabı."""
        from planx_mpyy_studio.core.shelter_engine import ShelterEngine
        from planx_mpyy_studio.provider import CalculateShelterRequirementAlgorithm
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback

        uri = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string&field=kaks:double&field=bagimsiz_bolum_sayisi:int"
        layer = QgsVectorLayer(uri, "shelter_test_layer", "memory")
        pr = layer.dataProvider()

        # 1. Large apartment: 1000 m2, kaks=2.0 -> 2000 m2 gross, 16 units -> SIGINAK_ZORUNLU (req: >= 40 m2)
        f1 = QgsFeature(layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 20)))
        f1["uipfonksiyon"] = "KONUT_ALANI"
        f1["kaks"] = 2.0
        f1["bagimsiz_bolum_sayisi"] = 16

        # 2. Small detached house: 300 m2, kaks=0.6 -> 180 m2 gross, 1 unit -> SIGINAK_MUAFIYET (req: 0.0)
        f2 = QgsFeature(layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 115, 20)))
        f2["uipfonksiyon"] = "KONUT_ALANI"
        f2["kaks"] = 0.6
        f2["bagimsiz_bolum_sayisi"] = 1

        # 3. Commercial center: 800 m2, kaks=2.0 -> 1600 m2 gross -> SIGINAK_ZORUNLU (>=1000 m2 threshold, req: 1600 * 0.025 = 40 m2)
        f3 = QgsFeature(layer.fields())
        f3.setGeometry(QgsGeometry.fromRect(QgsRectangle(200, 0, 240, 20)))
        f3["uipfonksiyon"] = "TICARET_ALANI"
        f3["kaks"] = 2.0
        f3["bagimsiz_bolum_sayisi"] = 0

        pr.addFeatures([f1, f2, f3])

        # Engine test
        res_list, summary = ShelterEngine.evaluate_shelter_requirements(
            features=[f1, f2, f3],
            default_kaks=1.2,
            area_per_person_m2=1.2,
        )
        self.assertEqual(len(res_list), 3)
        self.assertEqual(summary.toplam_parsel_sayisi, 3)
        self.assertEqual(summary.siginak_zorunlu_parsel_sayisi, 2)
        self.assertEqual(summary.muaf_parsel_sayisi, 1)
        self.assertGreater(summary.toplam_gerekli_siginak_alani_m2, 50.0)
        self.assertGreater(summary.toplam_siginacak_kisi_kapasitesi, 30)

        # Processing algorithm test
        alg = CalculateShelterRequirementAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "INPUT": layer,
            "DEFAULT_KAKS": 1.2,
            "AREA_PER_PERSON": 1.2,
            "OUTPUT": "memory:shelter_output",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["TOPLAM_PARSEL"], 3)
        self.assertEqual(res_alg["SIGINAK_ZORUNLU_PARSEL"], 2)

    def test_spatial_index_optimization(self):
        """Kriter WP1: batch_synthesize_parcels mekânsal indeks ile O(N log M) hızında çalışır."""
        uri_p = "MultiPolygon?crs=EPSG:5254&field=PARSEL:string&field=ADA:string"
        layer_p = QgsVectorLayer(uri_p, "parcels", "memory")
        pr_p = layer_p.dataProvider()

        p1 = QgsFeature(layer_p.fields())
        p1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 50)))  # 2500 m2
        p1["ADA"] = "101"
        p1["PARSEL"] = "1"

        p2 = QgsFeature(layer_p.fields())
        p2.setGeometry(QgsGeometry.fromRect(QgsRectangle(100, 0, 150, 50)))  # 2500 m2
        p2["ADA"] = "101"
        p2["PARSEL"] = "2"
        pr_p.addFeatures([p1, p2])

        uri_b = "MultiPolygon?crs=EPSG:5254&field=B_KAT:integer&field=B_DURUM:string"
        layer_b = QgsVectorLayer(uri_b, "buildings", "memory")
        pr_b = layer_b.dataProvider()

        b1 = QgsFeature(layer_b.fields())
        b1.setGeometry(QgsGeometry.fromRect(QgsRectangle(10, 10, 30, 30)))  # 400 m2 inside p1
        b1["B_KAT"] = 4
        b1["B_DURUM"] = "IYI"

        b2 = QgsFeature(layer_b.fields())
        b2.setGeometry(QgsGeometry.fromRect(QgsRectangle(110, 10, 130, 30)))  # 400 m2 inside p2
        b2["B_KAT"] = 2
        b2["B_DURUM"] = "RISKLI"
        pr_b.addFeatures([b1, b2])

        uri_plan = "MultiPolygon?crs=EPSG:5254&field=uipfonksiyon:string"
        layer_plan = QgsVectorLayer(uri_plan, "plans", "memory")
        pr_plan = layer_plan.dataProvider()

        plan1 = QgsFeature(layer_plan.fields())
        plan1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 200, 100)))
        plan1["uipfonksiyon"] = "KONUT_ALANI"
        pr_plan.addFeature(plan1)

        results = SynthesisEngine.batch_synthesize_parcels(
            parcel_features=list(layer_p.getFeatures()),
            plan_features=list(layer_plan.getFeatures()),
            building_features=list(layer_b.getFeatures()),
            function_field="uipfonksiyon",
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].bina_sayisi, 1)
        self.assertEqual(results[0].toplam_taban_alani_m2, 400.0)
        self.assertEqual(results[0].toplam_insaat_alani_m2, 1600.0)
        self.assertEqual(results[1].riskli_bina_sayisi, 1)
        self.assertEqual(results[0].hakim_plan_fonksiyonu, "KONUT_ALANI")

    def test_allocation_matrix_engine_and_algorithm(self):
        """Kriter WP2: İmar Kanunu Madde 18 tahsis cetveli alan dengesini ve dağıtım matrisini sağlar."""
        from planx_mpyy_studio.core.allocation_engine import AllocationEngine
        from planx_mpyy_studio.provider import GenerateLandReadjustmentMatrixAlgorithm

        # 2 Cadastral parcels: 1000 m2 each = 2000 m2 total
        uri_c = "MultiPolygon?crs=EPSG:5254&field=ADA:string&field=PARSEL:string&field=malik:string"
        layer_c = QgsVectorLayer(uri_c, "cadastre", "memory")
        pr_c = layer_c.dataProvider()

        c1 = QgsFeature(layer_c.fields())
        c1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 20)))  # 1000 m2
        c1["ADA"] = "101"
        c1["PARSEL"] = "1"
        c1["malik"] = "Ahmet Yılmaz"

        c2 = QgsFeature(layer_c.fields())
        c2.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 20, 50, 40)))  # 1000 m2
        c2["ADA"] = "101"
        c2["PARSEL"] = "2"
        c2["malik"] = "Mehmet Demir"
        pr_c.addFeatures([c1, c2])

        # 1 Zoning parcel: 1200 m2 (net after 40% DOP on 2000 m2 = 1200 m2)
        uri_z = "MultiPolygon?crs=EPSG:5254&field=ADA:string&field=PARSEL:string"
        layer_z = QgsVectorLayer(uri_z, "zoning", "memory")
        pr_z = layer_z.dataProvider()

        z1 = QgsFeature(layer_z.fields())
        z1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 40, 30)))  # 1200 m2
        z1["ADA"] = "501"
        z1["PARSEL"] = "1"
        pr_z.addFeature(z1)

        report = AllocationEngine.calculate_allocation_matrix(
            cadastral_features=[c1, c2],
            zoning_parcels=[z1],
            dop_ratio=0.40,
        )

        self.assertEqual(report.toplam_kadastro_m2, 2000.0)
        self.assertEqual(report.toplam_dop_kesinti_m2, 800.0)
        self.assertEqual(report.toplam_tahsis_imar_m2, 1200.0)
        self.assertAlmostEqual(report.dop_orani, 0.40, places=2)
        self.assertTrue('Dağıtım ve Tahsis Cetveli' in report.html_report)
        self.assertEqual(len(report.items), 2)

        # Test memory layer generation
        mem_layer = AllocationEngine.create_allocation_memory_layer(report)
        self.assertTrue(mem_layer.isValid())
        self.assertEqual(mem_layer.featureCount(), 2)

        # Processing algorithm test
        alg = GenerateLandReadjustmentMatrixAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "CADASTRE": layer_c,
            "ZONING_PARCELS": layer_z,
            "DOP_RATIO": 0.40,
            "OUTPUT": "memory:alloc_output",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["TOPLAM_KADASTRO_M2"], 2000.0)
        self.assertEqual(res_alg["TOPLAM_TAHSIS_M2"], 1200.0)

    def test_conditional_form_visibility(self):
        """Kriter WP5: Bitişik nizamda yan bahçe çekmesi koşullu görünürlük ifadesi ile donatılır."""
        uri = (
            "MultiPolygon?crs=EPSG:5254"
            "&field=nizam:string"
            "&field=onBahce:double"
            "&field=yanBahce:double"
            "&field=arkaBahce:double"
        )
        layer = QgsVectorLayer(uri, "paiy_form_test", "memory")
        MPYYFormDesigner.configure_tabbed_drag_and_drop_form(layer)

        form_config = layer.editFormConfig()
        root = form_config.invisibleRootContainer()
        tabs = root.children()
        paiy_tab = next((t for t in tabs if 'PAİY' in t.name()), None)
        self.assertIsNotNone(paiy_tab)

        def find_container_recursive(container, target_name):
            for child in container.children():
                if hasattr(child, "name") and target_name in child.name():
                    return child
                if hasattr(child, "children"):
                    found = find_container_recursive(child, target_name)
                    if found:
                        return found
            return None

        yan_sub = find_container_recursive(paiy_tab, 'YAN BAHÇE MESAFESİ')
        self.assertIsNotNone(yan_sub)
        self.assertTrue(yan_sub.visibilityExpression().enabled())
        expr_str = yan_sub.visibilityExpression().data().expression()
        self.assertIn("BITISIK", expr_str)

    def test_free_height_violation_detector(self):
        """Kriter WP4: 7221 sayılı Kanun uyarınca Serbest yükseklik tespit edilir ve HUKUKA_AYKIRI_SERBEST_YUKSEKLIK raporlanır."""
        uri = "MultiPolygon?crs=EPSG:5254&field=yencok:string&field=katadedi:string"
        layer = QgsVectorLayer(uri, "height_qc_test", "memory")
        pr = layer.dataProvider()

        f1 = QgsFeature(layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        f1["yencok"] = "SERBEST"

        f2 = QgsFeature(layer.fields())
        f2.setGeometry(QgsGeometry.fromRect(QgsRectangle(20, 0, 30, 10)))
        f2["yencok"] = "15.50 m"
        f2["katadedi"] = "5"

        f3 = QgsFeature(layer.fields())
        f3.setGeometry(QgsGeometry.fromRect(QgsRectangle(40, 0, 50, 10)))
        f3["katadedi"] = "H:SERBEST"

        pr.addFeatures([f1, f2, f3])

        anomalies = QualityControlEngine.check_free_height_violations([f1, f2, f3])
        self.assertEqual(len(anomalies), 2)
        for a in anomalies:
            self.assertEqual(a.tur, "HUKUKA_AYKIRI_SERBEST_YUKSEKLIK")
            self.assertEqual(a.ciddiyet, "HATA")
            self.assertIn("7221", a.aciklama)

    def test_transformation_feasibility_engine_and_algorithm(self):
        """Kriter WP7: Kentsel dönüşüm hakediş, müteahhit paylaşımı ve alan fizibilitesi hesaplanır."""
        from planx_mpyy_studio.core.feasibility_engine import UrbanTransformationFeasibilityEngine
        from planx_mpyy_studio.provider import EvaluateTransformationFeasibilityAlgorithm

        uri = (
            "MultiPolygon?crs=EPSG:5254"
            "&field=ADA:string&field=PARSEL:string"
            "&field=mevcut_insaat_m2:double"
            "&field=kaks:double"
        )
        layer = QgsVectorLayer(uri, "feasibility_test", "memory")
        pr = layer.dataProvider()

        f1 = QgsFeature(layer.fields())
        f1.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 20)))  # 1000 m2
        f1["ADA"] = "105"
        f1["PARSEL"] = "3"
        f1["mevcut_insaat_m2"] = 1000.0  # Existing built area
        f1["kaks"] = 2.0  # Proposed KAKS -> 2000 m2 new area
        pr.addFeature(f1)

        items, summary = UrbanTransformationFeasibilityEngine.evaluate_feasibility(
            parcel_features=[f1],
            contractor_ratio=0.45,
            unit_construction_cost_tl=25000.0,
            unit_sale_price_tl=50000.0,
        )

        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it.yeni_insaat_alani_m2, 2000.0)
        self.assertEqual(it.muteahhit_insaat_m2, 900.0)
        self.assertEqual(it.hak_sahibi_insaat_m2, 1100.0)
        self.assertEqual(it.hakedis_katsayisi, 1.1)
        self.assertEqual(it.alan_farki_m2, 100.0)
        self.assertEqual(it.fizibilite_durumu, "ALAN_FAZLASI_POZITIF")
        self.assertEqual(it.tahmini_maliyet_tl, 50000000.0)  # 2000 * 25000
        self.assertEqual(it.tahmini_ciro_tl, 45000000.0)  # 900 * 50000
        self.assertTrue('Kentsel Dönüşüm Hakediş' in summary.html_report)

        # Processing algorithm test
        alg = EvaluateTransformationFeasibilityAlgorithm()
        alg.initAlgorithm()
        ctx = QgsProcessingContext()
        fb = QgsProcessingFeedback()
        params = {
            "PARCELS": layer,
            "CONTRACTOR_RATIO": 0.45,
            "UNIT_COST": 25000.0,
            "UNIT_PRICE": 50000.0,
            "DEFAULT_KAKS": 2.0,
            "OUTPUT": "memory:feas_output",
        }
        res_alg = alg.processAlgorithm(params, ctx, fb)
        self.assertEqual(res_alg["TOPLAM_PARSEL"], 1)
        self.assertEqual(res_alg["TOPLAM_YENI_INSAAT_M2"], 2000.0)

    def test_zoning_certificate_paiy5_and_hud(self):
        """Kriter WP3 & WP8: İmar çapında PAİY Md. 5 emsal harici alan hesaplanır ve CAD HUD üretilir."""
        uri = "MultiPolygon?crs=EPSG:5254&field=ADA:string&field=PARSEL:string&field=uipfonksiyon:string&field=kaks:double&field=taks:double"
        layer = QgsVectorLayer(uri, "cert_test", "memory")
        pr = layer.dataProvider()

        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 40)))  # 2000 m2
        feat["ADA"] = "101"
        feat["PARSEL"] = "7"
        feat["uipfonksiyon"] = "KONUT_ALANI"
        feat["taks"] = 0.35  # 700 m2
        feat["kaks"] = 1.50  # 3000 m2
        pr.addFeature(feat)

        cert = ZoningCertificateEngine.generate_certificate(feat)
        self.assertEqual(cert.azami_insaat_alani_m2, 3000.0)
        self.assertEqual(cert.emsal_harici_alan_m2, 900.0)  # 3000 * 0.30
        self.assertEqual(cert.toplam_ruhsat_insaat_m2, 3900.0)  # 3000 + 900
        self.assertIn('Emsal Harici Alan', cert.html_content)
        self.assertIn('Toplam Ruhsat İnşaat Alanı', cert.html_content)

        # Test CAD-grade HUD line layer
        hud_layer = ZoningCertificateEngine.create_zoning_hud_layer(feat, setback_m=3.0)
        self.assertTrue(hud_layer.isValid())
        self.assertGreater(hud_layer.featureCount(), 0)
        elem_types = [f["eleman_turu"] for f in hud_layer.getFeatures()]
        self.assertIn("PARSEL_CEPHESI", elem_types)
        self.assertIn("CEKME_SINIRI", elem_types)

    def test_geom_cleaner_heal_boundaries(self):
        """Kriter WP6: heal_topological_boundaries mikro-yırtıkları ve sınırları onarır."""
        from planx_mpyy_studio.core.geom_cleaner import heal_topological_boundaries
        g1 = QgsGeometry.fromRect(QgsRectangle(0.001, 0.002, 10.001, 10.002))
        healed = heal_topological_boundaries([g1], snap_tolerance=0.05)
        self.assertEqual(len(healed), 1)
        self.assertTrue(healed[0].isGeosValid())

    def test_parcel_subdivision_engine_and_algorithm(self):
        from planx_mpyy_studio.core.subdivision_engine import SubdivisionConstraint, SubdivisionEngine
        from planx_mpyy_studio.provider import OptimizeParcelSubdivisionAlgorithm

        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=PARSEL:string", "subdivision_test", "memory"
        )
        feature = QgsFeature(layer.fields())
        feature["PARSEL"] = "17"
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 48, 30)))
        layer.dataProvider().addFeature(feature)
        feature = next(layer.getFeatures())

        constraint = SubdivisionEngine.constraint_for("AYRIK", "KONUT_TICARET", floors=3)
        result = SubdivisionEngine.subdivide_feature(feature, constraint, target_frontage=12.0)
        self.assertEqual(result.generated_parcels_count, 2)
        self.assertAlmostEqual(sum(geom.area() for geom in result.subdivided_geometries), 1440.0, places=5)
        self.assertTrue(all(geom.area() >= 500.0 for geom in result.subdivided_geometries))
        self.assertTrue(all(metric.compliant for metric in result.parcel_metrics))
        self.assertTrue(all(metric.frontage_m >= 12.0 for metric in result.parcel_metrics))
        self.assertTrue(all(metric.depth_m >= 18.0 for metric in result.parcel_metrics))
        self.assertAlmostEqual(result.area_balance_error_m2, 0.0, places=6)
        self.assertTrue(all(0.0 < metric.compactness <= 1.0 for metric in result.parcel_metrics))
        self.assertTrue(all(metric.aspect_ratio >= 1.0 for metric in result.parcel_metrics))
        centroids = [geom.centroid().asPoint().x() for geom in result.subdivided_geometries]
        self.assertEqual(centroids, sorted(centroids))
        road = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(48, 0)])
        road_result = SubdivisionEngine.subdivide_feature(
            feature, constraint, target_frontage=12.0, road_geometries=[road]
        )
        self.assertTrue(all(metric.road_frontage_m >= 12.0 for metric in road_result.parcel_metrics))
        self.assertTrue(all(metric.compliant for metric in road_result.parcel_metrics))
        with self.assertRaises(ValueError):
            SubdivisionConstraint("", 12.0, 18.0, 500.0)

        algorithm = OptimizeParcelSubdivisionAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "PARCELS": layer,
                "ROADS": None,
                "NIZAM": 0,
                "LAND_USE": 0,
                "FLOORS": 3,
                "TARGET_FRONTAGE": 12.0,
                "MAX_PARCELS": 100,
                "OUTPUT": "memory:subdivision_output",
            },
            QgsProcessingContext(),
            QgsProcessingFeedback(),
        )
        self.assertEqual(response["SOURCE_COUNT"], 1)
        self.assertEqual(response["GENERATED_COUNT"], 2)

    def test_procedural_massing_engine_and_algorithm(self):
        from planx_mpyy_studio.core.massing_engine_3d import ProceduralMassingEngine
        from planx_mpyy_studio.provider import GenerateProcedural3DMassingAlgorithm

        parcel = QgsGeometry.fromRect(QgsRectangle(0, 0, 30, 30))
        massing = ProceduralMassingEngine.generate(
            parcel, setback_m=3.0, max_height_m=13.0,
            subbasement_height_m=0.5, ground_floor_height_m=4.0,
            typical_floor_height_m=3.0, roof_slope_percent=33.0,
        )
        self.assertAlmostEqual(massing.footprint_area_m2, 576.0, places=5)
        self.assertEqual(massing.floor_count, 4)
        self.assertAlmostEqual(massing.wall_top_z, 13.5, places=5)
        self.assertGreater(massing.roof_top_z, massing.wall_top_z)
        self.assertTrue(massing.geometry.constGet().is3D())
        self.assertEqual(massing.floor_elevations_m, (0.5, 4.5, 7.5, 10.5, 13.5))

        clamped = ProceduralMassingEngine.generate(
            parcel, setback_m=3.0, max_height_m=3.0,
            subbasement_height_m=0.5, ground_floor_height_m=4.0,
            include_roof=False,
        )
        self.assertEqual(clamped.floor_count, 1)
        self.assertAlmostEqual(clamped.wall_top_z, 3.5, places=5)
        self.assertIn("GROUND_FLOOR_HEIGHT_CLAMPED_TO_HMAX", clamped.warning_notes)

        layer = QgsVectorLayer("Polygon?crs=EPSG:5254&field=PARSEL:string", "massing_test", "memory")
        feature = QgsFeature(layer.fields())
        feature["PARSEL"] = "1"
        feature.setGeometry(parcel)
        layer.dataProvider().addFeature(feature)
        algorithm = GenerateProcedural3DMassingAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "PARCELS": layer,
                "SETBACK": 3.0,
                "MAX_HEIGHT": 13.0,
                "SUBBASEMENT_HEIGHT": 0.5,
                "GROUND_FLOOR_HEIGHT": 4.0,
                "TYPICAL_FLOOR_HEIGHT": 3.0,
                "ROOF_SLOPE": 33.0,
                "MAX_ROOF_RISE": 6.0,
                "INCLUDE_ROOF": True,
                "OUTPUT": "memory:massing_output",
            },
            QgsProcessingContext(),
            QgsProcessingFeedback(),
        )
        self.assertEqual(response["GENERATED_COUNT"], 1)

        capped = ProceduralMassingEngine.generate(
            QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)),
            setback_m=0.0, max_height_m=10.0, max_roof_rise_m=2.0,
        )
        self.assertAlmostEqual(capped.roof_rise_m, 2.0, places=6)
        self.assertIn("ROOF_RISE_CAPPED", capped.warning_notes)
        self.assertGreater(capped.gross_floor_area_m2, 0.0)
        self.assertGreater(capped.floor_area_ratio, 0.0)
        with self.assertRaises(ValueError):
            ProceduralMassingEngine.generate(parcel, max_height_m=float("nan"))

    def test_mpyy_plan_hierarchy_audit_and_algorithm(self):
        from planx_mpyy_studio.core.hierarchy_audit import PlanHierarchyAuditEngine
        from planx_mpyy_studio.provider import AuditPlanHierarchyConsistencyAlgorithm

        parent = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=global_id:string&field=fonksiyon_kodu:string",
            "cdp_parent", "memory",
        )
        parent_feature = QgsFeature(parent.fields())
        parent_feature["global_id"] = "CDP-1"
        parent_feature["fonksiyon_kodu"] = "KENTSEL_GELISME"
        parent_feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        parent.dataProvider().addFeature(parent_feature)

        child = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=global_id:string&field=ust_grup_kodu:string",
            "nip_child", "memory",
        )
        inside = QgsFeature(child.fields())
        inside["global_id"] = "NIP-1"
        inside["ust_grup_kodu"] = "KENTSEL_GELISME"
        inside.setGeometry(QgsGeometry.fromRect(QgsRectangle(10, 10, 30, 30)))
        outside = QgsFeature(child.fields())
        outside["global_id"] = "NIP-2"
        outside["ust_grup_kodu"] = "KENTSEL_GELISME"
        outside.setGeometry(QgsGeometry.fromRect(QgsRectangle(120, 120, 140, 140)))
        child.dataProvider().addFeatures([inside, outside])

        records = PlanHierarchyAuditEngine.audit(
            parent.getFeatures(), child.getFeatures(), "CDP", "NIP"
        )
        self.assertEqual([record.linkage_status for record in records], ["MATCH", "OUTSIDE"])
        self.assertAlmostEqual(records[0].coverage_ratio, 1.0, places=6)

        algorithm = AuditPlanHierarchyConsistencyAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "PARENT": parent, "PARENT_LEVEL": 1,
                "CHILD": child, "CHILD_LEVEL": 1,
                "MINIMUM_COVERAGE": 0.99,
                "OUTPUT": "memory:hierarchy_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["MATCH_COUNT"], 1)
        self.assertEqual(response["REVIEW_COUNT"], 1)

    def test_mpyy_plan_submission_dossier_and_algorithm(self):
        import json

        from planx_mpyy_studio.core.plan_submission import PlanSubmissionAuditEngine
        from planx_mpyy_studio.provider import AuditPlanSubmissionDossierAlgorithm

        manifest = {
            "plan_level": "UIP",
            "lifecycle_status": "FINALIZED",
            "plan_transaction_number": "PIN-2026-1",
            "approval_date": "2026-01-02",
            "approval_number": "10",
            "suspension_start_date": "2026-01-05",
            "suspension_end_date": "2026-02-04",
            "finalization_date": "2026-02-05",
            "provincial_delivery_date": "2026-02-10",
            "official_holidays": [],
            "documents": {
                "plan_sheet": True,
                "plan_notes": True,
                "plan_report": True,
                "author_signed": True,
                "upper_plan_analysis": True,
                "geological_survey": True,
                "accessibility_analysis": True,
                "current_base_map": True,
                "suspension_start_minutes": True,
                "suspension_end_minutes": True,
                "digital_dataset": True,
            },
        }
        audit = PlanSubmissionAuditEngine.audit(manifest)
        self.assertEqual(audit.status, "COMPLIANT")
        incomplete = dict(manifest)
        incomplete["documents"] = {}
        incomplete["suspension_start_date"] = "2026-02-20"
        incomplete_audit = PlanSubmissionAuditEngine.audit(incomplete)
        self.assertEqual(incomplete_audit.status, "NON_COMPLIANT")
        self.assertIn("LATE_SUSPENSION_START", {item.code for item in incomplete_audit.findings})

        manifest_path = Path(self.tmp.name) / "submission_manifest.json"
        report_path = Path(self.tmp.name) / "submission_audit.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditPlanSubmissionDossierAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLIANT")
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["content_sha256"]), 64)

    def test_municipal_bylaw_engine_and_algorithm(self):
        import json

        from planx_mpyy_studio.core.bylaw_engine import MunicipalBylawEngine, load_bylaw_profiles
        from planx_mpyy_studio.provider import AuditMunicipalBylawComplianceAlgorithm

        values = {
            "ceiling_height_m": 2.70,
            "unit_net_area_m2": 25.0,
            "roof_slope_percent": 20.0,
            "subbasement_height_m": 0.80,
            "parking_on_parcel": False,
        }
        audit = MunicipalBylawEngine.audit(values, "ISTANBUL_IBB")
        self.assertFalse(audit.compliant)
        self.assertEqual(
            {violation.rule_code for violation in audit.violations},
            {"MIN_CEILING_HEIGHT", "MIN_UNIT_NET_AREA", "ROOF_SLOPE", "PARKING_ON_PARCEL"},
        )
        incomplete = MunicipalBylawEngine.audit({"ceiling_height_m": 3.0}, "ISTANBUL_IBB")
        self.assertFalse(incomplete.compliant)
        self.assertEqual(incomplete.status, "INSUFFICIENT_DATA")
        self.assertIn("MIN_UNIT_NET_AREA", incomplete.missing_rules)
        invalid = MunicipalBylawEngine.audit(
            {
                "ceiling_height_m": "not-a-number",
                "unit_net_area_m2": 35.0,
                "roof_slope_percent": 33.0,
                "subbasement_height_m": 1.0,
                "parking_on_parcel": "unknown",
            },
            "ISTANBUL_IBB",
        )
        self.assertEqual(invalid.status, "INVALID_DATA")
        self.assertIn("MIN_CEILING_HEIGHT", invalid.invalid_rules)
        self.assertIn("PARKING_ON_PARCEL", invalid.invalid_rules)

        custom_path = Path(self.tmp.name) / "custom_bylaws.json"
        custom_path.write_text(json.dumps({
            "schema_version": 1,
            "profiles": [{
                "code": "TEST_CITY",
                "display_name": "Test City",
                "min_ceiling_height_m": 3.1,
                "permitted_roof_slopes_percent": [20.0],
                "parking_on_parcel_required": False,
                "profile_version": "2026.1",
            }],
        }), encoding="utf-8")
        custom_profiles = load_bylaw_profiles(custom_path)
        self.assertEqual(custom_profiles["TEST_CITY"].profile_version, "2026.1")
        custom_audit = MunicipalBylawEngine.audit(
            {
                "ceiling_height_m": 3.0,
                "roof_slope_percent": 20.0,
                "subbasement_height_m": 0.5,
            },
            "TEST_CITY",
            custom_profiles,
        )
        self.assertEqual(custom_audit.status, "NON_COMPLIANT")
        invalid_path = Path(self.tmp.name) / "invalid_bylaws.json"
        invalid_path.write_text(
            json.dumps({"schema_version": 1, "profiles": [{
                "code": "BAD", "display_name": "Bad", "min_ceiling_height_m": "NaN"
            }]}),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            load_bylaw_profiles(invalid_path)

        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=ceiling_height_m:double"
            "&field=unit_net_area_m2:double&field=roof_slope_percent:double"
            "&field=subbasement_height_m:double&field=parking_on_parcel:boolean",
            "bylaw_test", "memory",
        )
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        for key, value in values.items():
            feature[key] = value
        layer.dataProvider().addFeature(feature)
        algorithm = AuditMunicipalBylawComplianceAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"INPUT": layer, "PROFILE": 1, "OUTPUT": "memory:bylaw_output"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["NON_COMPLIANT_COUNT"], 1)

    def test_concurrency_engine_and_algorithm(self):
        import json
        import shutil
        import sqlite3

        from planx_mpyy_studio.core.concurrency_engine import GeoPackageConcurrencyEngine
        from planx_mpyy_studio.provider import (
            PreviewWorkspaceReconciliationAlgorithm,
            ReconcileWorkspaceVersionsAlgorithm,
        )

        base = Path(self.tmp.name) / "base.gpkg"
        incoming = Path(self.tmp.name) / "incoming.gpkg"
        output = Path(self.tmp.name) / "reconciled.gpkg"
        output_algorithm = Path(self.tmp.name) / "reconciled_algorithm.gpkg"
        output_preferred = Path(self.tmp.name) / "reconciled_preferred.gpkg"
        create_local_uip_workspace(base, "EPSG:5254")
        with sqlite3.connect(base) as connection:
            connection.execute("CREATE TABLE team_edits (edit_id TEXT PRIMARY KEY, note TEXT)")
            connection.execute(
                "INSERT INTO gpkg_contents(table_name,data_type,identifier) VALUES ('team_edits','attributes','Team edits')"
            )
            connection.execute("INSERT INTO team_edits VALUES ('A','base value')")
        shutil.copy2(base, incoming)
        with sqlite3.connect(incoming) as connection:
            connection.execute("UPDATE team_edits SET note='incoming value' WHERE edit_id='A'")
            connection.execute("INSERT INTO team_edits VALUES ('B','incoming only')")

        preview = GeoPackageConcurrencyEngine.preview_workspaces(base, incoming)
        self.assertEqual(preview.incoming_only_rows, 1)
        self.assertEqual(preview.divergent_rows, 1)
        self.assertGreater(preview.identical_rows, 0)
        preview_path = Path(self.tmp.name) / "reconciliation_preview.json"
        GeoPackageConcurrencyEngine.write_preview_report(preview, preview_path)
        preview_payload = json.loads(preview_path.read_text(encoding="utf-8"))
        self.assertEqual(len(preview_payload["content_sha256"]), 64)
        self.assertEqual(preview_payload["table_summaries"]["team_edits"]["divergent_rows"], 1)

        preview_algorithm_path = Path(self.tmp.name) / "reconciliation_preview_algorithm.json"
        preview_algorithm = PreviewWorkspaceReconciliationAlgorithm()
        preview_algorithm.initAlgorithm()
        preview_response = preview_algorithm.processAlgorithm(
            {
                "BASE_WORKSPACE": str(base),
                "INCOMING_WORKSPACE": str(incoming),
                "OUTPUT_REPORT": str(preview_algorithm_path),
            },
            QgsProcessingContext(),
            QgsProcessingFeedback(),
        )
        self.assertEqual(preview_response["INCOMING_ONLY_ROWS"], 1)
        self.assertEqual(preview_response["DIVERGENT_ROWS"], 1)
        self.assertTrue(preview_algorithm_path.is_file())

        result = GeoPackageConcurrencyEngine.reconcile_workspaces(base, incoming, output)
        self.assertEqual(result.inserted_rows, 1)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("team_edits", GeoPackageConcurrencyEngine.prepare_workspace(output))
        self.assertEqual(GeoPackageConcurrencyEngine.enable_wal(output), "WAL")
        with sqlite3.connect(output) as connection:
            self.assertEqual(connection.execute("SELECT note FROM team_edits WHERE edit_id='A'").fetchone()[0], "base value")
            self.assertEqual(connection.execute("SELECT note FROM team_edits WHERE edit_id='B'").fetchone()[0], "incoming only")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM _reconciliation_conflicts").fetchone()[0], 1)

        preferred = GeoPackageConcurrencyEngine.reconcile_workspaces(
            base, incoming, output_preferred, "PREFER_INCOMING"
        )
        self.assertEqual(preferred.updated_rows, 1)
        self.assertEqual(len(preferred.conflicts), 0)
        with sqlite3.connect(output_preferred) as connection:
            self.assertEqual(
                connection.execute("SELECT note FROM team_edits WHERE edit_id='A'").fetchone()[0],
                "incoming value",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT resolution FROM _reconciliation_conflicts WHERE feature_key='A'"
                ).fetchone()[0],
                "INCOMING_APPLIED",
            )
        self.assertEqual(
            GeoPackageConcurrencyEngine._row_hash({"note": "same", "uuid_version": "one"}),
            GeoPackageConcurrencyEngine._row_hash({"note": "same", "uuid_version": "two"}),
        )

        algorithm = ReconcileWorkspaceVersionsAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "BASE_WORKSPACE": str(base),
                "INCOMING_WORKSPACE": str(incoming),
                "OUTPUT": str(output_algorithm),
                "CONFLICT_STRATEGY": 0,
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["INSERTED_ROWS"], 1)
        self.assertEqual(response["CONFLICT_COUNT"], 1)

    def test_official_atlas_engine_and_algorithm(self):
        from planx_mpyy_studio.core.print_atlas_engine import OfficialPrintAtlasEngine
        from planx_mpyy_studio.provider import ExportOfficialZoningAtlasAlgorithm

        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=ada:string&field=parsel:string"
            "&field=kaks:double&field=taks:double&field=hmax:double",
            "atlas_test", "memory",
        )
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 40, 30)))
        feature["ada"] = "101"
        feature["parsel"] = "7"
        feature["kaks"] = 1.5
        feature["taks"] = 0.35
        feature["hmax"] = 15.5
        layer.dataProvider().addFeature(feature)
        feature = next(layer.getFeatures())

        layout, document_hash = OfficialPrintAtlasEngine.create_layout(
            layer, feature, "Test Municipality", "DOC-1", "A4_PORTRAIT", 25.0,
        )
        self.assertGreater(len(layout.items()), 4)
        self.assertTrue(any(item.__class__.__name__ == "QgsLayoutItemLegend" for item in layout.items()))
        self.assertEqual(len(document_hash), 64)
        pdf_path = Path(self.tmp.name) / "official_atlas.pdf"
        exported = OfficialPrintAtlasEngine.export(
            layout, pdf_path, document_hash, "A4_PORTRAIT", 300
        )
        self.assertTrue(Path(exported.output_path).is_file())
        self.assertGreater(Path(exported.output_path).stat().st_size, 0)
        self.assertEqual(len(exported.file_hash), 64)

        algorithm_path = Path(self.tmp.name) / "official_atlas_algorithm.pdf"
        algorithm = ExportOfficialZoningAtlasAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "PARCEL_LAYER": layer,
                "MUNICIPALITY": "Test Municipality",
                "DOCUMENT_NUMBER": "DOC-2",
                "PAGE_SIZE": 1,
                "BUFFER": 25.0,
                "DPI": 300,
                "OUTPUT": str(algorithm_path),
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(len(response["DOCUMENT_HASH"]), 64)
        self.assertTrue(algorithm_path.is_file())

    def test_official_atlas_batch_engine_and_algorithm(self):
        import json

        from planx_mpyy_studio.core.print_atlas_engine import OfficialPrintAtlasEngine
        from planx_mpyy_studio.provider import ExportOfficialZoningAtlasBatchAlgorithm

        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=ada:string&field=parsel:string",
            "atlas_batch_test", "memory",
        )
        features = []
        for index in range(2):
            feature = QgsFeature(layer.fields())
            feature["ada"] = "200"
            feature["parsel"] = str(index + 1)
            feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(index * 50, 0, index * 50 + 40, 30)))
            features.append(feature)
        layer.dataProvider().addFeatures(features)

        engine_dir = Path(self.tmp.name) / "batch_engine"
        result = OfficialPrintAtlasEngine.export_batch(
            layer, layer.getFeatures(), engine_dir, "Test Municipality", "DOC",
            "A4_PORTRAIT", 25.0, 300,
        )
        self.assertEqual(len(result.documents), 2)
        manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["documents"]), 2)
        self.assertEqual(manifest["document_count"], 2)
        self.assertEqual(len(manifest["documents_sha256"]), 64)
        self.assertTrue(all(len(row["file_sha256"]) == 64 for row in manifest["documents"]))
        self.assertTrue(all((engine_dir / row["file"]).is_file() for row in manifest["documents"]))

        cancel_dir = Path(self.tmp.name) / "batch_cancel"
        progress = {"current": 0}
        def record_progress(current, total):
            progress["current"] = current
        with self.assertRaises(RuntimeError):
            OfficialPrintAtlasEngine.export_batch(
                layer, layer.getFeatures(), cancel_dir, "Test Municipality", "CANCEL",
                "A4_PORTRAIT", 25.0, 300,
                progress_callback=record_progress,
                cancel_callback=lambda: progress["current"] >= 1,
            )
        self.assertEqual(list(cancel_dir.glob("*.pdf")), [])
        self.assertFalse((cancel_dir / "atlas_manifest.json").exists())

        algorithm_dir = Path(self.tmp.name) / "batch_algorithm"
        algorithm = ExportOfficialZoningAtlasBatchAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "PARCEL_LAYER": layer,
                "MUNICIPALITY": "Test Municipality",
                "DOCUMENT_PREFIX": "ALG",
                "PAGE_SIZE": 1,
                "BUFFER": 25.0,
                "DPI": 300,
                "SELECTED_ONLY": False,
                "OUTPUT_DIRECTORY": str(algorithm_dir),
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["DOCUMENT_COUNT"], 2)
        self.assertTrue(Path(response["MANIFEST"]).is_file())

    def test_article22_threshold_screening_engine_and_algorithm(self):
        from planx_mpyy_studio.core.threshold_screening import ThresholdScreeningEngine
        from planx_mpyy_studio.provider import ScreenMPYYThresholdConstraintsAlgorithm

        proposals = QgsVectorLayer("Polygon?crs=EPSG:5254&field=plan_id:string", "proposals", "memory")
        proposal = QgsFeature(proposals.fields())
        proposal["plan_id"] = "P1"
        proposal.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        proposals.dataProvider().addFeature(proposal)
        hazards = QgsVectorLayer("Polygon?crs=EPSG:5254", "hazards", "memory")
        hazard = QgsFeature(hazards.fields())
        hazard.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 50, 100)))
        hazards.dataProvider().addFeature(hazard)

        records = ThresholdScreeningEngine.screen(
            proposals.getFeatures(), {"GEOLOGY_HAZARD": hazards.getFeatures()}
        )
        self.assertEqual(records[0].status, "REVIEW_REQUIRED")
        self.assertAlmostEqual(records[0].overlap_ratio, 0.5)
        self.assertEqual(records[0].categories, ("GEOLOGY_HAZARD",))

        algorithm = ScreenMPYYThresholdConstraintsAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "INPUT": proposals,
                "GEOLOGY_HAZARD": hazards,
                "REVIEW_RATIO": 0.1,
                "OUTPUT": "memory:threshold_output",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["FEATURE_COUNT"], 1)
        self.assertEqual(response["REVIEW_COUNT"], 1)

    def test_article26_road_and_density_change_audits(self):
        from planx_mpyy_studio.core.density_change_audit import DensityChangeAuditEngine
        from planx_mpyy_studio.core.road_change_audit import RoadChangeAuditEngine
        from planx_mpyy_studio.provider import (
            AuditMPYYDensityHeightChangeAlgorithm,
            AuditMPYYRoadPlanChangeAlgorithm,
        )

        road_values = {
            "current_width_m": 12.0,
            "proposed_width_m": 6.0,
            "current_lanes": 2,
            "proposed_lanes": 1,
            "road_type": "TRAFFIC",
            "area_context": "DEVELOPMENT",
            "parcel_access": True,
            "dead_end": True,
            "turning_curve": False,
            "traffic_impact_assessment": False,
        }
        road_audit = RoadChangeAuditEngine.audit(road_values)
        road_codes = {item.code for item in road_audit.findings}
        self.assertEqual(road_audit.status, "NON_COMPLIANT")
        self.assertTrue({"ROAD_NARROWING", "LANE_REDUCTION", "PARCEL_ACCESS_WIDTH"} <= road_codes)

        road_layer = QgsVectorLayer(
            "LineString?crs=EPSG:5254&field=current_width_m:double&field=proposed_width_m:double"
            "&field=current_lanes:integer&field=proposed_lanes:integer&field=road_type:string"
            "&field=area_context:string&field=parcel_access:integer&field=dead_end:integer"
            "&field=turning_curve:integer&field=traffic_impact_assessment:integer",
            "road_changes", "memory",
        )
        road_feature = QgsFeature(road_layer.fields())
        road_feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(100, 0)]))
        for key, value in road_values.items():
            road_feature[key] = value
        road_layer.dataProvider().addFeature(road_feature)
        road_algorithm = AuditMPYYRoadPlanChangeAlgorithm()
        road_algorithm.initAlgorithm()
        road_response = road_algorithm.processAlgorithm(
            {"INPUT": road_layer, "OUTPUT": "memory:road_audit"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(road_response["NON_COMPLIANT"], 1)

        density_values = {
            "current_height_m": 12.0,
            "proposed_height_m": 20.0,
            "opposite_height_m": 16.0,
            "actual_facade_distance_m": 20.0,
            "current_population": 100.0,
            "proposed_population": 160.0,
            "current_intensity": 1.0,
            "proposed_intensity": 1.8,
            "silhouette_assessment": False,
            "infrastructure_impact_report": False,
            "social_infrastructure_balance": False,
        }
        density_audit = DensityChangeAuditEngine.audit(density_values)
        self.assertEqual(density_audit.required_facade_distance_m, 25.0)
        self.assertEqual(density_audit.population_change, 60.0)
        self.assertEqual(density_audit.status, "NON_COMPLIANT")
        density_layer = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=current_height_m:double&field=proposed_height_m:double"
            "&field=opposite_height_m:double&field=actual_facade_distance_m:double"
            "&field=current_population:double&field=proposed_population:double"
            "&field=current_intensity:double&field=proposed_intensity:double"
            "&field=silhouette_assessment:integer&field=infrastructure_impact_report:integer"
            "&field=social_infrastructure_balance:integer",
            "density_changes", "memory",
        )
        density_feature = QgsFeature(density_layer.fields())
        density_feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        for key, value in density_values.items():
            density_feature[key] = value
        density_layer.dataProvider().addFeature(density_feature)
        density_algorithm = AuditMPYYDensityHeightChangeAlgorithm()
        density_algorithm.initAlgorithm()
        density_response = density_algorithm.processAlgorithm(
            {"INPUT": density_layer, "OUTPUT": "memory:density_audit"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(density_response["NON_COMPLIANT_COUNT"], 1)

    def test_msp_monitoring_and_cdp_revision_scope(self):
        from planx_mpyy_studio.core.cdp_revision import CDPRevisionEngine
        from planx_mpyy_studio.core.msp_monitoring import MSPMonitoringEngine
        from planx_mpyy_studio.provider import (
            ClassifyCDPRevisionScopeAlgorithm,
            EvaluateMSPActionMonitoringAlgorithm,
        )

        actions = QgsVectorLayer(
            "Point?crs=EPSG:5254&field=action_id:string&field=baseline_value:double"
            "&field=target_value:double&field=actual_value:double&field=weight:double"
            "&field=due_date:string&field=responsible_institution:string",
            "msp_actions", "memory",
        )
        for action_id, actual, due in (("A1", 100.0, "2026-01-01"), ("A2", 30.0, "2026-01-01")):
            feature = QgsFeature(actions.fields())
            feature["action_id"] = action_id
            feature["baseline_value"] = 0.0
            feature["target_value"] = 100.0
            feature["actual_value"] = actual
            feature["weight"] = 1.0
            feature["due_date"] = due
            feature["responsible_institution"] = "Planning Authority"
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
            actions.dataProvider().addFeature(feature)
        monitoring = MSPMonitoringEngine.evaluate(actions.getFeatures(), "2026-09-14")
        self.assertEqual(monitoring.complete_count, 1)
        self.assertEqual(monitoring.delayed_count, 1)
        self.assertAlmostEqual(monitoring.weighted_progress_ratio, 0.65)
        monitoring_algorithm = EvaluateMSPActionMonitoringAlgorithm()
        monitoring_algorithm.initAlgorithm()
        monitoring_response = monitoring_algorithm.processAlgorithm(
            {
                "INPUT": actions, "EVALUATION_DATE": "2026-09-14",
                "OUTPUT": "memory:msp_monitoring",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(monitoring_response["DELAYED_COUNT"], 1)

        current = QgsVectorLayer("Polygon?crs=EPSG:5254&field=fonksiyon_kodu:string", "current", "memory")
        proposed = QgsVectorLayer("Polygon?crs=EPSG:5254&field=fonksiyon_kodu:string", "proposed", "memory")
        for layer, code in ((current, "KONUT"), (proposed, "SANAYI")):
            feature = QgsFeature(layer.fields())
            feature["fonksiyon_kodu"] = code
            feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
            layer.dataProvider().addFeature(feature)
        assessment = CDPRevisionEngine.assess(
            current.getFeatures(), proposed.getFeatures(), {"REGIONAL_INVESTMENT": True}
        )
        self.assertEqual(assessment.classification, "REVISION_REVIEW")
        self.assertAlmostEqual(assessment.changed_area, 10000.0)
        classifier = ClassifyCDPRevisionScopeAlgorithm()
        classifier.initAlgorithm()
        classifier_response = classifier.processAlgorithm(
            {
                "CURRENT": current, "PROPOSED": proposed, "REGIONAL_INVESTMENT": True,
                "RATIONALE_DOCUMENTED": True, "INFRASTRUCTURE_IMPACT_DOCUMENTED": True,
                "OUTPUT": "memory:cdp_scope",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(classifier_response["CLASSIFICATION"], "REVISION_REVIEW")

    def test_nip_uip_active_mobility_network_audit(self):
        from planx_mpyy_studio.core.active_mobility_audit import ActiveMobilityAuditEngine
        from planx_mpyy_studio.provider import AuditNIPUIPActiveMobilityNetworkAlgorithm

        network = QgsVectorLayer("LineString?crs=EPSG:5254&field=route_id:string", "network", "memory")
        lines = (
            ("L1", ((0, 0), (10, 0), (20, 0))),
            ("L2", ((10, 0), (10, 10))),
            ("L3", ((100, 100), (110, 100))),
        )
        for route_id, vertices in lines:
            feature = QgsFeature(network.fields())
            feature["route_id"] = route_id
            feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*point) for point in vertices]))
            network.dataProvider().addFeature(feature)
        centers = QgsVectorLayer("Point?crs=EPSG:5254", "centers", "memory")
        for point in ((5, 2), (250, 250)):
            feature = QgsFeature(centers.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point)))
            centers.dataProvider().addFeature(feature)
        audit = ActiveMobilityAuditEngine.audit(network.getFeatures(), centers.getFeatures(), 0.5, 10.0)
        self.assertEqual(audit.component_count, 2)
        self.assertEqual(audit.disconnected_feature_count, 1)
        self.assertEqual(audit.unserved_center_count, 1)

        algorithm = AuditNIPUIPActiveMobilityNetworkAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "NETWORK": network, "CENTERS": centers, "SNAP_TOLERANCE": 0.5,
                "CENTER_ACCESS_DISTANCE": 10.0, "OUTPUT": "memory:network_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["COMPONENT_COUNT"], 2)
        self.assertEqual(response["UNSERVED_CENTER_COUNT"], 1)

    def test_evidence_provenance_and_opinion_register_audits(self):
        import hashlib
        import json

        from planx_mpyy_studio.core.evidence_provenance import EvidenceProvenanceAuditEngine
        from planx_mpyy_studio.core.opinion_register import OpinionRegisterAuditEngine
        from planx_mpyy_studio.provider import (
            AuditInstitutionOpinionRegisterAlgorithm,
            AuditMPYYEvidenceProvenanceAlgorithm,
        )

        evidence_file = Path(self.tmp.name) / "evidence.dat"
        evidence_file.write_bytes(b"verified planning evidence")
        checksum = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
        categories = (
            "TOPOGRAPHY", "GEOLOGY", "HYDROGEOLOGY", "CURRENT_LAND_USE",
            "AGRICULTURE_FOREST", "INFRASTRUCTURE",
        )
        manifest = {
            "plan_level": "UIP",
            "context_flags": {},
            "evidence_items": [
                {
                    "evidence_id": f"EV-{index}",
                    "category": category,
                    "source_institution": "Planning Authority",
                    "acquisition_date": "2026-06-01",
                    "version": "2026.1",
                    "crs_authid": "EPSG:5254",
                    "scale_denominator": 1000,
                    "sha256": checksum,
                    "local_path": str(evidence_file),
                }
                for index, category in enumerate(categories, start=1)
            ],
        }
        result = EvidenceProvenanceAuditEngine.audit(manifest)
        self.assertEqual(result.status, "COMPLETE")
        self.assertEqual(result.verified_file_count, 6)
        broken = dict(manifest)
        broken["context_flags"] = {"coastal": True}
        broken_result = EvidenceProvenanceAuditEngine.audit(broken)
        self.assertEqual(broken_result.status, "INCOMPLETE")
        self.assertIn("MISSING_THRESHOLD_CATEGORY", {item.code for item in broken_result.findings})
        infinite_scale = json.loads(json.dumps(manifest))
        infinite_scale["evidence_items"][0]["scale_denominator"] = float("inf")
        infinite_result = EvidenceProvenanceAuditEngine.audit(infinite_scale, verify_local_files=False)
        self.assertIn("MISSING_SCALE_RESOLUTION", {item.code for item in infinite_result.findings})

        manifest_path = Path(self.tmp.name) / "evidence_manifest.json"
        evidence_report = Path(self.tmp.name) / "evidence_report.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditMPYYEvidenceProvenanceAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "MANIFEST": str(manifest_path), "VERIFY_LOCAL_FILES": True,
                "OUTPUT_REPORT": str(evidence_report),
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        self.assertEqual(len(json.loads(evidence_report.read_text(encoding="utf-8"))["content_sha256"]), 64)

        register = {
            "evaluation_date": "2026-09-14",
            "institutions": [
                {
                    "institution": "On Time", "request_date": "2026-08-01",
                    "response_date": "2026-08-20", "extension_granted": False,
                },
                {
                    "institution": "Late", "request_date": "2026-06-01",
                    "response_date": "2026-08-15", "extension_granted": True,
                },
                {
                    "institution": "Pending", "request_date": "2026-09-01",
                    "response_date": "", "extension_granted": False,
                },
            ],
        }
        opinion_result = OpinionRegisterAuditEngine.audit(register)
        self.assertEqual(opinion_result.status, "REVIEW_REQUIRED")
        self.assertEqual(opinion_result.late_response_count, 1)
        self.assertEqual(opinion_result.pending_count, 1)
        expired_register = {
            "evaluation_date": "2026-09-14",
            "institutions": [{
                "institution": "No Response", "request_date": "2026-06-01",
                "response_date": "", "extension_granted": False,
            }],
        }
        expired_result = OpinionRegisterAuditEngine.audit(expired_register)
        self.assertEqual(expired_result.status, "COMPLETE")
        self.assertEqual(expired_result.deemed_no_negative_count, 1)
        invalid_register = {
            "evaluation_date": "2026-09-14",
            "institutions": [{
                "institution": "Invalid Date", "request_date": "2026-08-01",
                "response_date": "not-a-date", "extension_granted": False,
            }],
        }
        self.assertEqual(OpinionRegisterAuditEngine.audit(invalid_register).invalid_count, 1)
        register_path = Path(self.tmp.name) / "opinion_register.json"
        opinion_report = Path(self.tmp.name) / "opinion_report.json"
        register_path.write_text(json.dumps(register), encoding="utf-8")
        opinion_algorithm = AuditInstitutionOpinionRegisterAlgorithm()
        opinion_algorithm.initAlgorithm()
        opinion_response = opinion_algorithm.processAlgorithm(
            {"REGISTER": str(register_path), "OUTPUT_REPORT": str(opinion_report)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(opinion_response["LATE_RESPONSE_COUNT"], 1)
        self.assertTrue(opinion_report.is_file())

    def test_nip_uip_routed_accessibility_engine_and_algorithm(self):
        from planx_mpyy_studio.core.routed_accessibility import RoutedAccessibilityEngine
        from planx_mpyy_studio.provider import AnalyzeNIPUIPRoutedAccessibilityAlgorithm

        network = QgsVectorLayer("LineString?crs=EPSG:5254", "route_network", "memory")
        for vertices in (
            ((0, 0), (100, 0), (200, 0)),
            ((1000, 0), (1100, 0)),
        ):
            feature = QgsFeature(network.fields())
            feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*point) for point in vertices]))
            network.dataProvider().addFeature(feature)
        demand = QgsVectorLayer("Point?crs=EPSG:5254&field=demand_id:string", "demand", "memory")
        for demand_id, point in (("near", (50, 0)), ("far", (150, 0)), ("isolated", (1050, 0))):
            feature = QgsFeature(demand.fields())
            feature["demand_id"] = demand_id
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point)))
            demand.dataProvider().addFeature(feature)
        facilities = QgsVectorLayer("Point?crs=EPSG:5254", "facilities", "memory")
        facility = QgsFeature(facilities.fields())
        facility.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        facilities.dataProvider().addFeature(facility)

        result = RoutedAccessibilityEngine.analyze(
            network.getFeatures(), demand.getFeatures(), facilities.getFeatures(), 80.0, 0.1, 60.0
        )
        self.assertEqual(result.accessible_count, 1)
        self.assertEqual(result.inaccessible_count, 1)
        self.assertEqual(result.unreachable_count, 1)
        self.assertEqual(result.graph_node_count, 5)

        algorithm = AnalyzeNIPUIPRoutedAccessibilityAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "NETWORK": network, "DEMAND": demand, "FACILITIES": facilities,
                "MAX_ROUTE_DISTANCE": 80.0, "SNAP_TOLERANCE": 0.1,
                "MAX_SNAP_DISTANCE": 60.0, "OUTPUT": "memory:routed_access",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["ACCESSIBLE_COUNT"], 1)
        self.assertEqual(response["UNREACHABLE_COUNT"], 1)

    def test_adjacent_plan_boundary_consistency_engine_and_algorithm(self):
        from planx_mpyy_studio.core.adjacent_boundary_audit import AdjacentBoundaryAuditEngine
        from planx_mpyy_studio.provider import AuditAdjacentPlanBoundaryConsistencyAlgorithm

        reference = QgsVectorLayer("LineString?crs=EPSG:5254&field=code:string", "reference", "memory")
        adjacent = QgsVectorLayer("LineString?crs=EPSG:5254&field=code:string", "adjacent", "memory")
        first = QgsFeature(reference.fields())
        first["code"] = "KONUT"
        first.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(100, 0)]))
        reference.dataProvider().addFeature(first)
        second = QgsFeature(adjacent.fields())
        second["code"] = "SANAYI"
        second.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0.2), QgsPointXY(100, 0.2)]))
        adjacent.dataProvider().addFeature(second)

        records = AdjacentBoundaryAuditEngine.audit(
            reference.getFeatures(), adjacent.getFeatures(), 0.5, 0.95, "code", "code"
        )
        self.assertEqual(records[0].status, "CODE_CONFLICT")
        self.assertGreater(records[0].coverage_ratio, 0.99)
        algorithm = AuditAdjacentPlanBoundaryConsistencyAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "REFERENCE": reference, "REFERENCE_CODE_FIELD": "code",
                "ADJACENT": adjacent, "ADJACENT_CODE_FIELD": "code",
                "TOLERANCE": 0.5, "MINIMUM_COVERAGE": 0.95,
                "OUTPUT": "memory:adjacent_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["CONFLICT_COUNT"], 1)

    def test_plan_fabric_topology_engine_and_algorithm(self):
        from planx_mpyy_studio.core.plan_fabric_audit import PlanFabricAuditEngine
        from planx_mpyy_studio.provider import AuditPlanFabricTopologyAlgorithm

        decisions = QgsVectorLayer("Polygon?crs=EPSG:5254&field=code:string", "decisions", "memory")
        for code, rectangle in (
            ("A", QgsRectangle(0, 0, 60, 100)),
            ("B", QgsRectangle(50, 0, 90, 100)),
        ):
            feature = QgsFeature(decisions.fields())
            feature["code"] = code
            feature.setGeometry(QgsGeometry.fromRect(rectangle))
            decisions.dataProvider().addFeature(feature)
        boundary = QgsVectorLayer("Polygon?crs=EPSG:5254", "boundary", "memory")
        boundary_feature = QgsFeature(boundary.fields())
        boundary_feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        boundary.dataProvider().addFeature(boundary_feature)

        result = PlanFabricAuditEngine.audit(decisions.getFeatures(), boundary.getFeatures())
        self.assertEqual(result.overlap_feature_count, 2)
        self.assertAlmostEqual(result.gap_area, 1000.0)
        self.assertTrue(all(record.overlap_area == 1000.0 for record in result.records))
        algorithm = AuditPlanFabricTopologyAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "DECISIONS": decisions, "BOUNDARY": boundary, "AREA_TOLERANCE": 0.01,
                "OUTPUT": "memory:fabric_audit", "GAPS": "memory:fabric_gaps",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["OVERLAP_FEATURE_COUNT"], 2)
        self.assertAlmostEqual(response["GAP_AREA"], 1000.0)

    def test_mpyy_article9_plan_report_engine_and_algorithm(self):
        import json

        from planx_mpyy_studio.core.plan_report_audit import PlanReportAuditEngine
        from planx_mpyy_studio.provider import AuditMPYYPlanReportContentAlgorithm

        sections = {name: True for name in PlanReportAuditEngine.COMMON_SECTIONS}
        sections.update({
            "detailed_change_rationale": True,
            "necessity_analyses": True,
            "mixed_use_ratios": True,
            "parking_details": True,
            "green_area_details": True,
            "social_technical_infrastructure_details": True,
            "independent_unit_count": 20,
        })
        manifest = {
            "plan_level": "UIP", "report_purpose": "PLAN_CHANGE",
            "contains_mixed_use": True, "sections": sections,
        }
        self.assertEqual(PlanReportAuditEngine.audit(manifest).status, "COMPLETE")
        scoped = json.loads(json.dumps(manifest))
        scoped["sections"]["efficient_use_of_space"] = False
        scoped["not_applicable_sections"] = {
            "efficient_use_of_space": "Addressed by the approved upper-plan report."
        }
        self.assertEqual(PlanReportAuditEngine.audit(scoped).status, "COMPLETE")
        incomplete = json.loads(json.dumps(manifest))
        incomplete["sections"]["detailed_change_rationale"] = False
        incomplete_result = PlanReportAuditEngine.audit(incomplete)
        self.assertEqual(incomplete_result.status, "INCOMPLETE")
        self.assertIn("MISSING_DETAILED_CHANGE_RATIONALE", {
            item.code for item in incomplete_result.findings
        })

        manifest_path = Path(self.tmp.name) / "plan_report_manifest.json"
        report_path = Path(self.tmp.name) / "plan_report_audit.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditMPYYPlanReportContentAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        self.assertEqual(len(json.loads(report_path.read_text(encoding="utf-8"))["content_sha256"]), 64)

    def test_mpyy_article12_walking_distance_engine_and_algorithm(self):
        from planx_mpyy_studio.core.article12_accessibility import Article12AccessibilityEngine
        from planx_mpyy_studio.provider import AuditMPYYArticle12WalkingDistancesAlgorithm

        network = QgsVectorLayer("LineString?crs=EPSG:5254", "walking_network", "memory")
        network_feature = QgsFeature(network.fields())
        network_feature.setGeometry(QgsGeometry.fromPolylineXY([
            QgsPointXY(0, 0), QgsPointXY(400, 0), QgsPointXY(1200, 0),
        ]))
        network.dataProvider().addFeature(network_feature)
        demand = QgsVectorLayer(
            "Point?crs=EPSG:5254&field=required_service:string"
            "&field=gross_density_ppha:double&field=rural_settlement:integer"
            "&field=barrier_justification:string",
            "article12_demand", "memory",
        )
        for point, density in (((400, 0), 150.0), ((1200, 0), 150.0), ((1200, 0), 80.0)):
            feature = QgsFeature(demand.fields())
            feature["required_service"] = "İlkokul"
            feature["gross_density_ppha"] = density
            feature["rural_settlement"] = 0
            feature["barrier_justification"] = ""
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point)))
            demand.dataProvider().addFeature(feature)
        facilities = QgsVectorLayer(
            "Point?crs=EPSG:5254&field=facility_type:string", "article12_facilities", "memory"
        )
        facility = QgsFeature(facilities.fields())
        facility["facility_type"] = "İlkokul"
        facility.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0, 0)))
        facilities.dataProvider().addFeature(facility)

        result = Article12AccessibilityEngine.audit(
            network.getFeatures(), demand.getFeatures(), facilities.getFeatures(),
            "required_service", "facility_type", 0.1, 5.0,
        )
        self.assertEqual(result.compliant_count, 1)
        self.assertEqual(result.non_compliant_count, 1)
        self.assertEqual(result.review_count, 1)
        self.assertTrue(all(item.threshold_m == 500.0 for item in result.records))
        self.assertEqual(
            Article12AccessibilityEngine.canonical_type("Orta (semt) cami"), "ORTA_CAMI"
        )
        self.assertEqual(
            Article12AccessibilityEngine.canonical_type("Aile Sağlığı Merkezi"),
            "AILE_SAGLIK_MERKEZI",
        )

        algorithm = AuditMPYYArticle12WalkingDistancesAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "NETWORK": network, "DEMAND": demand,
                "DEMAND_SERVICE_FIELD": "required_service", "FACILITIES": facilities,
                "FACILITY_TYPE_FIELD": "facility_type", "SNAP_TOLERANCE": 0.1,
                "MAX_SNAP_DISTANCE": 5.0, "OUTPUT": "memory:article12_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["COMPLIANT_COUNT"], 1)
        self.assertEqual(response["REVIEW_COUNT"], 1)

    def test_mpyy_article27_conservation_plan_dossier(self):
        import json

        from planx_mpyy_studio.core.special_plan_audits import SpecialPlanAuditEngine
        from planx_mpyy_studio.provider import AuditConservationPlanDossierAlgorithm

        manifest = {name: True for name in SpecialPlanAuditEngine.CONSERVATION_REQUIREMENTS}
        manifest["overlapping_protection_statuses"] = True
        incomplete = SpecialPlanAuditEngine.audit_conservation(manifest)
        self.assertEqual(incomplete.status, "INCOMPLETE")
        manifest["competent_authority_opinions"] = ["Culture", "Nature"]
        self.assertEqual(SpecialPlanAuditEngine.audit_conservation(manifest).status, "COMPLETE")
        manifest_path = Path(self.tmp.name) / "conservation_manifest.json"
        report_path = Path(self.tmp.name) / "conservation_report.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditConservationPlanDossierAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_articles28_29_integrated_coastal_plan_dossier(self):
        import json

        from planx_mpyy_studio.core.special_plan_audits import SpecialPlanAuditEngine
        from planx_mpyy_studio.provider import AuditIntegratedCoastalPlanDossierAlgorithm

        manifest = {name: True for name in SpecialPlanAuditEngine.COASTAL_REQUIREMENTS}
        manifest["planning_area_interaction_basis"] = True
        self.assertEqual(SpecialPlanAuditEngine.audit_coastal(manifest).status, "COMPLETE")
        missing = dict(manifest)
        missing["coastal_ecosystem"] = False
        self.assertEqual(SpecialPlanAuditEngine.audit_coastal(missing).status, "INCOMPLETE")
        manifest_path = Path(self.tmp.name) / "coastal_manifest.json"
        report_path = Path(self.tmp.name) / "coastal_report.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditIntegratedCoastalPlanDossierAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["ERROR_COUNT"], 0)

    def test_mpyy_article30_urban_design_project_prerequisites(self):
        import json

        from planx_mpyy_studio.core.special_plan_audits import SpecialPlanAuditEngine
        from planx_mpyy_studio.provider import AuditUrbanDesignProjectPrerequisitesAlgorithm

        manifest = {name: True for name in SpecialPlanAuditEngine.URBAN_DESIGN_REQUIREMENTS}
        manifest.update({
            "project_boundary_in_plan": True,
            "project_preceded_plan": False,
            "details_transferred_to_plan": False,
            "implementation_requested": True,
            "implementation_plan_approved": False,
        })
        blocked = SpecialPlanAuditEngine.audit_urban_design(manifest)
        self.assertEqual(blocked.status, "INCOMPLETE")
        self.assertIn("IMPLEMENTATION_PLAN_NOT_APPROVED", {item.code for item in blocked.findings})
        manifest["implementation_plan_approved"] = True
        self.assertEqual(SpecialPlanAuditEngine.audit_urban_design(manifest).status, "COMPLETE")
        manifest_path = Path(self.tmp.name) / "urban_design_manifest.json"
        report_path = Path(self.tmp.name) / "urban_design_report.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditUrbanDesignProjectPrerequisitesAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_article8_research_dossier(self):
        import json

        from planx_mpyy_studio.core.mpyy_general_dossiers import MPYYGeneralDossierEngine
        from planx_mpyy_studio.provider import AuditMPYYArticle8ResearchDossierAlgorithm

        manifest = {name: True for name in MPYYGeneralDossierEngine.ARTICLE8_BASE}
        manifest["high_urban_or_disaster_risk"] = True
        incomplete = MPYYGeneralDossierEngine.audit_article8(manifest)
        self.assertEqual(incomplete.status, "INCOMPLETE")
        self.assertIn("MISSING_RISK_OR_AVOIDANCE_STUDY", {item.code for item in incomplete.findings})
        manifest["risk_or_avoidance_study"] = True
        self.assertEqual(MPYYGeneralDossierEngine.audit_article8(manifest).status, "COMPLETE")
        manifest_path = Path(self.tmp.name) / "article8_manifest.json"
        report_path = Path(self.tmp.name) / "article8_report.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditMPYYArticle8ResearchDossierAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_article10_official_legend_audit(self):
        from planx_mpyy_studio.core.article10_legend_audit import Article10LegendAuditEngine
        from planx_mpyy_studio.provider import AuditMPYYArticle10OfficialLegendAlgorithm

        layer = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=display_code:string", "legend_decisions", "memory"
        )
        for index, code in enumerate(("CEMEVI_ALANI", "UNPUBLISHED_CUSTOM_SYMBOL")):
            feature = QgsFeature(layer.fields())
            feature["display_code"] = code
            feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(index * 20, 0, index * 20 + 10, 10)))
            layer.dataProvider().addFeature(feature)
        records = Article10LegendAuditEngine.audit(layer.getFeatures(), "UIP", "display_code")
        self.assertEqual(records[0].status, "OFFICIAL_MATCH")
        self.assertEqual(records[1].status, "UNMAPPED_REVIEW")
        algorithm = AuditMPYYArticle10OfficialLegendAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "INPUT": layer, "CODE_FIELD": "display_code", "PLAN_LEVEL": 3,
                "OUTPUT": "memory:legend_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["OFFICIAL_COUNT"], 1)
        self.assertEqual(response["REVIEW_COUNT"], 1)

    def test_mpyy_article11_standards_context_dossier(self):
        import json

        from planx_mpyy_studio.core.mpyy_general_dossiers import MPYYGeneralDossierEngine
        from planx_mpyy_studio.provider import AuditMPYYArticle11StandardsContextAlgorithm

        manifest = {name: True for name in MPYYGeneralDossierEngine.ARTICLE11_BASE}
        manifest["seasonal_tourism_housing"] = True
        incomplete = MPYYGeneralDossierEngine.audit_article11(manifest)
        self.assertEqual(incomplete.status, "INCOMPLETE")
        manifest.update({
            "permanent_population_assumption": True,
            "seasonal_area_infrastructure": True,
            "seasonal_area_parking": True,
        })
        self.assertEqual(MPYYGeneralDossierEngine.audit_article11(manifest).status, "COMPLETE")
        manifest_path = Path(self.tmp.name) / "article11_manifest.json"
        report_path = Path(self.tmp.name) / "article11_report.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        algorithm = AuditMPYYArticle11StandardsContextAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(report_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["ERROR_COUNT"], 0)

    def test_mpyy_article25_plan_intervention_classifier(self):
        from planx_mpyy_studio.core.article25_intervention import Article25InterventionEngine
        from planx_mpyy_studio.provider import ClassifyMPYYArticle25PlanInterventionAlgorithm

        current = QgsVectorLayer("Polygon?crs=EPSG:5254&field=fonksiyon_kodu:string", "current", "memory")
        current_feature = QgsFeature(current.fields())
        current_feature["fonksiyon_kodu"] = "KONUT"
        current_feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 100, 100)))
        current.dataProvider().addFeature(current_feature)
        proposed = QgsVectorLayer("Polygon?crs=EPSG:5254&field=fonksiyon_kodu:string", "proposed", "memory")
        for rectangle in (QgsRectangle(0, 0, 100, 100), QgsRectangle(100, 0, 150, 100)):
            feature = QgsFeature(proposed.fields())
            feature["fonksiyon_kodu"] = "KONUT"
            feature.setGeometry(QgsGeometry.fromRect(rectangle))
            proposed.dataProvider().addFeature(feature)
        declarations = {
            "NEED_NOT_MET": True, "LAND_USE_CONTINUITY_DOCUMENTED": True,
            "RATIONALE_DOCUMENTED": True,
        }
        assessment = Article25InterventionEngine.assess(
            current.getFeatures(), proposed.getFeatures(), declarations
        )
        self.assertEqual(assessment.classification, "ADDITION_REVIEW")
        self.assertTrue(assessment.addition_contiguous)
        self.assertAlmostEqual(assessment.added_area, 5000.0)
        algorithm = ClassifyMPYYArticle25PlanInterventionAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "CURRENT": current, "PROPOSED": proposed, "NEED_NOT_MET": True,
                "LAND_USE_CONTINUITY_DOCUMENTED": True, "RATIONALE_DOCUMENTED": True,
                "ADJACENCY_TOLERANCE": 0.01, "OUTPUT": "memory:article25_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["CLASSIFICATION"], "ADDITION_REVIEW")

    def test_mpyy_verified_audit_report_consolidation(self):
        import json

        from planx_mpyy_studio.core.compliance_bundle import MPYYComplianceBundleEngine
        from planx_mpyy_studio.core.mpyy_general_dossiers import MPYYGeneralDossierEngine
        from planx_mpyy_studio.provider import ConsolidateMPYYAuditReportsAlgorithm

        directory = Path(self.tmp.name) / "audit_reports"
        directory.mkdir()
        report_path = directory / "article8.json"
        manifest = {name: True for name in MPYYGeneralDossierEngine.ARTICLE8_BASE}
        result = MPYYGeneralDossierEngine.audit_article8(manifest)
        MPYYGeneralDossierEngine.write_report(result, report_path)
        bundle_path = Path(self.tmp.name) / "bundle.json"
        bundle = MPYYComplianceBundleEngine.consolidate(directory, bundle_path)
        self.assertEqual(bundle["status"], "COMPLETE")
        self.assertEqual(bundle["verified_report_count"], 1)
        self.assertEqual(len(bundle["content_sha256"]), 64)

        algorithm_path = Path(self.tmp.name) / "bundle_algorithm.json"
        algorithm = ConsolidateMPYYAuditReportsAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"INPUT_DIRECTORY": str(directory), "OUTPUT_REPORT": str(algorithm_path)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        tampered = json.loads(report_path.read_text(encoding="utf-8"))
        tampered["status"] = "INCOMPLETE"
        report_path.write_text(json.dumps(tampered), encoding="utf-8")
        self.assertEqual(
            MPYYComplianceBundleEngine.consolidate(directory, bundle_path)["status"], "INCOMPLETE"
        )

    def test_mpyy_plan_dossier_scaffold(self):
        import json

        from planx_mpyy_studio.core.dossier_lifecycle import MPYYDossierScaffoldEngine
        from planx_mpyy_studio.provider import InitializeMPYYPlanDossierAlgorithm

        root = Path(self.tmp.name) / "uip_dossier"
        result = MPYYDossierScaffoldEngine.create(root, "UIP", "NEW_PLAN")
        self.assertEqual(result["directory_count"], 7)
        manifest = json.loads((root / "dossier_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["plan_level"], "UIP")
        self.assertEqual(manifest["lifecycle_status"], "DRAFT")
        with self.assertRaises(ValueError):
            MPYYDossierScaffoldEngine.create(root, "UIP", "NEW_PLAN")

        algorithm_root = Path(self.tmp.name) / "msp_dossier"
        algorithm = InitializeMPYYPlanDossierAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"PLAN_LEVEL": 0, "PURPOSE": 1, "OUTPUT_DIRECTORY": str(algorithm_root)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["DIRECTORY_COUNT"], 7)
        self.assertTrue(Path(response["MANIFEST"]).is_file())

    def test_mpyy_dossier_completeness_and_file_identity(self):
        import hashlib
        import json

        from planx_mpyy_studio.core.dossier_lifecycle import MPYYDossierCompletenessEngine
        from planx_mpyy_studio.provider import AuditMPYYDossierCompletenessAlgorithm

        directory = Path(self.tmp.name) / "complete_dossier"
        directory.mkdir()
        roles = set(MPYYDossierCompletenessEngine.COMMON_ROLES)
        roles.update(MPYYDossierCompletenessEngine.LEVEL_ROLES["UIP"])
        files = []
        for role in sorted(roles):
            path = directory / (role + ".txt")
            content = ("evidence:" + role).encode("utf-8")
            path.write_bytes(content)
            files.append({
                "role": role, "path": path.name,
                "sha256": hashlib.sha256(content).hexdigest(),
            })
        manifest_path = directory / "dossier_manifest.json"
        manifest_path.write_text(json.dumps({
            "plan_level": "UIP", "purpose": "NEW_PLAN", "lifecycle_status": "DRAFT",
            "context_flags": {}, "files": files,
        }), encoding="utf-8")
        self.assertEqual(
            MPYYDossierCompletenessEngine.audit_file(manifest_path).status, "COMPLETE"
        )
        output = directory / "audit.json"
        algorithm = AuditMPYYDossierCompletenessAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(manifest_path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        (directory / "plan_sheet.txt").write_text("tampered", encoding="utf-8")
        tampered = MPYYDossierCompletenessEngine.audit_file(manifest_path)
        self.assertEqual(tampered.status, "INCOMPLETE")
        self.assertIn("FILE_CHECKSUM_MISMATCH", [item.code for item in tampered.findings])

    def test_mpyy_declared_evidence_freshness_policy(self):
        import json

        from planx_mpyy_studio.core.evidence_freshness import EvidenceFreshnessAuditEngine
        from planx_mpyy_studio.provider import AuditMPYYEvidenceFreshnessAlgorithm

        manifest = {
            "plan_level": "NIP",
            "evidence_items": [
                {"evidence_id": "geology", "valid_through": "2027-12-31"},
                {
                    "evidence_id": "land_use", "last_verified": "2026-01-01",
                    "review_interval_days": 120,
                },
            ],
        }
        result = EvidenceFreshnessAuditEngine.audit(manifest, "2026-09-15")
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.current_count, 1)
        self.assertEqual(result.expired_count, 1)

        manifest["evidence_items"] = [manifest["evidence_items"][0]]
        path = Path(self.tmp.name) / "freshness.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "freshness_report.json"
        algorithm = AuditMPYYEvidenceFreshnessAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "AS_OF_DATE": "2026-09-15", "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        self.assertEqual(response["CURRENT_COUNT"], 1)

    def test_mpyy_feature_level_mixed_use_details(self):
        from planx_mpyy_studio.core.mixed_use_audit import MPYYMixedUseAuditEngine
        from planx_mpyy_studio.provider import AuditMPYYMixedUseDetailsAlgorithm

        record = {
            "use_code": "TICARET+KONUT", "ratios_in_plan_report": True,
            "ratios_in_plan_notes": True, "parking_details": True,
            "green_area_details": True, "social_technical_infrastructure_details": True,
            "residential_infrastructure_allocated": True,
        }
        result = MPYYMixedUseAuditEngine.audit(record)
        self.assertEqual(result.status, "REVIEW_REQUIRED")
        self.assertAlmostEqual(result.effective_residential_ratio, 0.30)
        record["residential_ratio"] = 0.25
        self.assertEqual(MPYYMixedUseAuditEngine.audit(record).status, "COMPLIANT")

        uri = (
            "Polygon?crs=EPSG:5254&field=use_code:string&field=residential_ratio:double"
            "&field=ratios_in_plan_report:integer&field=ratios_in_plan_notes:integer"
            "&field=parking_details:integer&field=green_area_details:integer"
            "&field=social_technical_infrastructure_details:integer"
            "&field=residential_infrastructure_allocated:integer"
        )
        layer = QgsVectorLayer(uri, "mixed_use", "memory")
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        feature.setAttributes(["TICARET+KONUT", 0.25, 1, 1, 1, 1, 1, 1])
        layer.dataProvider().addFeature(feature)
        algorithm = AuditMPYYMixedUseDetailsAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"INPUT": layer, "OUTPUT": "memory:mixed_use_audit"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["FEATURE_COUNT"], 1)
        self.assertEqual(response["NON_COMPLIANT_COUNT"], 0)

    def test_mpyy_article33_publication_and_objection_register(self):
        import json

        from planx_mpyy_studio.core.dossier_lifecycle import MPYYPublicationRegisterEngine
        from planx_mpyy_studio.provider import AuditMPYYPublicationObjectionRegisterAlgorithm

        manifest = {
            "plan_level": "UIP",
            "publication": {
                "approval_date": "2026-09-01", "physical_start_date": "2026-09-02",
                "web_start_date": "2026-09-02", "end_date": "2026-10-02",
                "start_minutes_two_signatures": True, "end_minutes_two_signatures": True,
                "unit_head_signed": True, "local_announcement_evidenced": True,
                "official_holidays": [],
            },
            "objections": [{
                "received_date": "2026-09-10", "forwarded_date": "2026-10-10",
                "decision_date": "2026-11-01", "plan_changed": False,
            }],
        }
        self.assertEqual(MPYYPublicationRegisterEngine.audit(manifest).status, "COMPLETE")
        path = Path(self.tmp.name) / "publication.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "publication_report.json"
        algorithm = AuditMPYYPublicationObjectionRegisterAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        manifest["objections"][0]["plan_changed"] = True
        invalid = MPYYPublicationRegisterEngine.audit(manifest)
        self.assertEqual(invalid.status, "INCOMPLETE")
        self.assertIn("MISSING_REPUBLICATION", [item.code for item in invalid.findings])

    def test_mpyy_participation_register_and_msp_group_coverage(self):
        import json

        from planx_mpyy_studio.core.administrative_integrity import (
            MPYYParticipationRegisterEngine,
        )
        from planx_mpyy_studio.provider import AuditMPYYParticipationRegisterAlgorithm

        event = {
            "event_id": "meeting-01", "method": "MEETING", "date": "2026-08-20",
            "stakeholder_groups": ["PUBLIC_INSTITUTION", "CIVIL_SOCIETY"],
            "announcement_evidence": "notice-01", "attendance_evidence": "minutes-01",
            "outcome_summary": "Recorded planning concerns.",
            "input_disposition": "Responses are indexed in the plan report.",
        }
        manifest = {"plan_level": "NIP", "events": [event]}
        self.assertEqual(MPYYParticipationRegisterEngine.audit(manifest).status, "COMPLETE")
        msp_result = MPYYParticipationRegisterEngine.audit({"plan_level": "MSP", "events": [event]})
        self.assertEqual(msp_result.status, "INCOMPLETE")
        self.assertTrue(any(item.code.startswith("MISSING_MSP_GROUP") for item in msp_result.findings))

        path = Path(self.tmp.name) / "participation.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "participation_report.json"
        algorithm = AuditMPYYParticipationRegisterAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_cancelled_plan_evidence_reevaluation(self):
        import json

        from planx_mpyy_studio.core.administrative_integrity import (
            MPYYCancelledPlanEvidenceEngine,
        )
        from planx_mpyy_studio.provider import AuditMPYYCancelledPlanEvidenceAlgorithm

        manifest = {
            "plan_level": "CDP", "prior_plan_cancelled": True,
            "cancelled_plan_reference": "CDP-OLD-01",
            "cancellation_decision_reference": "court-2026-14",
            "reevaluations": [{
                "evidence_id": "old-" + kind.lower(), "kind": kind,
                "decision": "SUPERSEDED", "reevaluation_date": "2026-09-01",
                "rationale": "A current replacement is used.", "responsible_party": "planning_unit",
            } for kind in ("INSTITUTION_OPINIONS", "ANALYSIS", "SYNTHESIS")],
        }
        self.assertEqual(MPYYCancelledPlanEvidenceEngine.audit(manifest).status, "COMPLETE")
        self.assertEqual(
            MPYYCancelledPlanEvidenceEngine.audit({
                "plan_level": "CDP", "prior_plan_cancelled": False
            }).status,
            "NOT_APPLICABLE",
        )
        path = Path(self.tmp.name) / "cancelled_plan.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "cancelled_plan_report.json"
        algorithm = AuditMPYYCancelledPlanEvidenceAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_plan_component_identity_consistency(self):
        import json

        from planx_mpyy_studio.core.administrative_integrity import (
            MPYYPlanComponentConsistencyEngine,
        )
        from planx_mpyy_studio.provider import AuditMPYYPlanComponentConsistencyAlgorithm

        common = {
            "plan_id": "UIP-2026-01", "plan_version": "3", "plan_level": "UIP",
            "purpose": "REVISION", "sha256": "a" * 64,
        }
        manifest = {
            "plan_id": "UIP-2026-01", "plan_version": "3", "plan_level": "UIP",
            "purpose": "REVISION", "components": [
                dict(common, role=role) for role in (
                    "PLAN_SHEET", "OFFICIAL_DISPLAY", "PLAN_NOTES", "PLAN_REPORT"
                )
            ],
        }
        self.assertEqual(MPYYPlanComponentConsistencyEngine.audit(manifest).status, "COMPLETE")
        inconsistent = json.loads(json.dumps(manifest))
        inconsistent["components"][0]["plan_version"] = "2"
        result = MPYYPlanComponentConsistencyEngine.audit(inconsistent)
        self.assertIn("INCONSISTENT_PLAN_VERSION", [item.code for item in result.findings])

        path = Path(self.tmp.name) / "components.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "components_report.json"
        algorithm = AuditMPYYPlanComponentConsistencyAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_approval_sheet_front_face_register(self):
        import json

        from planx_mpyy_studio.core.administrative_integrity import (
            MPYYApprovalSheetRegisterEngine,
        )
        from planx_mpyy_studio.provider import AuditMPYYApprovalSheetRegisterAlgorithm

        common = {
            "front_face_pin": "UIP-31001234", "front_face_approval_date": "2026-09-01",
            "front_face_approval_number": "42", "stamped": True, "sha256": "b" * 64,
        }
        manifest = {
            "plan_level": "UIP", "plan_transaction_number": "UIP-31001234",
            "approval_date": "2026-09-01", "approval_number": "42",
            "sheets": [dict(common, sheet_id="H22-A"), dict(common, sheet_id="H22-B")],
        }
        self.assertEqual(MPYYApprovalSheetRegisterEngine.audit(manifest).status, "COMPLETE")
        invalid = json.loads(json.dumps(manifest))
        invalid["sheets"][1]["stamped"] = False
        self.assertIn(
            "SHEET_NOT_STAMPED",
            [item.code for item in MPYYApprovalSheetRegisterEngine.audit(invalid).findings],
        )
        path = Path(self.tmp.name) / "approval_sheets.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "approval_sheets_report.json"
        algorithm = AuditMPYYApprovalSheetRegisterAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")

    def test_mpyy_digital_delivery_package_integrity(self):
        import hashlib
        import json

        from planx_mpyy_studio.core.administrative_integrity import MPYYDigitalDeliveryEngine
        from planx_mpyy_studio.provider import AuditMPYYDigitalDeliveryPackageAlgorithm

        directory = Path(self.tmp.name) / "digital_delivery"
        directory.mkdir()
        roles = set(MPYYDigitalDeliveryEngine.COMMON_ROLES)
        roles.update(MPYYDigitalDeliveryEngine.IMAR_ROLES)
        files = []
        for role in sorted(roles):
            path = directory / (role.lower() + ".dat")
            content = ("delivery:" + role).encode("utf-8")
            path.write_bytes(content)
            files.append({
                "role": role, "path": path.name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "machine_readable": role == "GEOSPATIAL_PLAN_DATA",
            })
        manifest = {
            "plan_level": "UIP", "plan_transaction_number": "UIP-31001234",
            "format_profile_id": "ministry-profile-declared-by-administration",
            "crs_authid": "EPSG:5254", "delivery_receipt": "receipt-01",
            "destination_authority": "PROVINCIAL_DIRECTORATE",
            "finalization_date": "2026-09-01", "delivery_date": "2026-09-10",
            "files": files,
        }
        path = directory / "delivery_manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(MPYYDigitalDeliveryEngine.audit_file(path).status, "COMPLETE")
        output = directory / "delivery_report.json"
        algorithm = AuditMPYYDigitalDeliveryPackageAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        (directory / "plan_report.dat").write_text("tampered", encoding="utf-8")
        damaged = MPYYDigitalDeliveryEngine.audit_file(path)
        self.assertIn("DELIVERY_CHECKSUM_MISMATCH", [item.code for item in damaged.findings])

    def test_mpyy_profile_driven_geopackage_schema_audit(self):
        import json

        from planx_mpyy_studio.core.local_uip_workspace import create_local_uip_workspace
        from planx_mpyy_studio.core.digital_governance import MPYYGeoPackageProfileEngine
        from planx_mpyy_studio.provider import AuditMPYYGeoPackageSchemaProfileAlgorithm

        gpkg = Path(self.tmp.name) / "profile_workspace.gpkg"
        create_local_uip_workspace(gpkg, "EPSG:5254")
        profile = {
            "profile_id": "test-administration-profile", "profile_version": "1",
            "tables": [{
                "name": "mpyy_metadata", "fields": [
                    {"name": "dataset_id", "type": "TEXT", "not_null": True},
                    {"name": "schema_version", "type": "INTEGER", "not_null": True},
                ],
            }],
        }
        self.assertEqual(MPYYGeoPackageProfileEngine.audit(gpkg, profile).status, "COMPLETE")
        invalid = json.loads(json.dumps(profile))
        invalid["tables"].append({"name": "missing_table", "fields": []})
        self.assertIn(
            "MISSING_REQUIRED_TABLE",
            [item.code for item in MPYYGeoPackageProfileEngine.audit(gpkg, invalid).findings],
        )
        profile_path = Path(self.tmp.name) / "schema_profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        output = Path(self.tmp.name) / "schema_profile_report.json"
        algorithm = AuditMPYYGeoPackageSchemaProfileAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"GEOPACKAGE": str(gpkg), "PROFILE": str(profile_path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        self.assertEqual(response["CHECKED_TABLE_COUNT"], 1)

    def test_mpyy_deterministic_dossier_inventory(self):
        import json

        from planx_mpyy_studio.core.digital_governance import MPYYDossierInventoryEngine
        from planx_mpyy_studio.provider import GenerateMPYYDossierInventoryAlgorithm

        directory = Path(self.tmp.name) / "inventory_dossier"
        (directory / "nested").mkdir(parents=True)
        (directory / "plan.txt").write_text("plan", encoding="utf-8")
        (directory / "nested" / "report.txt").write_text("report", encoding="utf-8")
        output = directory / "inventory.json"
        first = MPYYDossierInventoryEngine.build(directory, output)
        self.assertEqual(first.status, "COMPLETE")
        self.assertEqual(first.details["file_count"], 2)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["content_sha256"]), 64)

        algorithm_output = directory / "algorithm_inventory.json"
        algorithm = GenerateMPYYDossierInventoryAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"INPUT_DIRECTORY": str(directory), "OUTPUT_REPORT": str(algorithm_output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        self.assertEqual(response["FILE_COUNT"], 3)

    def test_mpyy_plan_note_decision_code_links(self):
        import json

        from planx_mpyy_studio.core.digital_governance import MPYYPlanNoteDecisionLinkEngine
        from planx_mpyy_studio.provider import AuditMPYYPlanNoteDecisionLinksAlgorithm

        manifest = {
            "plan_level": "UIP", "decision_codes": ["KONUT", "PARK"],
            "require_every_decision_linked": True,
            "notes": [
                {"note_id": "N1", "text": "Housing conditions", "decision_codes": ["KONUT"]},
                {"note_id": "N2", "text": "Park conditions", "decision_codes": ["PARK"]},
            ],
        }
        self.assertEqual(MPYYPlanNoteDecisionLinkEngine.audit(manifest).status, "COMPLETE")
        invalid = json.loads(json.dumps(manifest))
        invalid["notes"][0]["decision_codes"] = ["UNKNOWN"]
        self.assertIn(
            "UNKNOWN_NOTE_DECISION_CODE",
            [item.code for item in MPYYPlanNoteDecisionLinkEngine.audit(invalid).findings],
        )
        path = Path(self.tmp.name) / "note_links.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "note_links_report.json"
        algorithm = AuditMPYYPlanNoteDecisionLinksAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["LINKED_DECISION_COUNT"], 2)

    def test_mpyy_plan_version_identity_chain(self):
        import json

        from planx_mpyy_studio.core.digital_governance import MPYYVersionChainEngine
        from planx_mpyy_studio.provider import AuditMPYYVersionChainAlgorithm

        manifest = {
            "plan_id": "NIP-2026-01", "versions": [
                {
                    "version": "1", "content_sha256": "a" * 64, "parent_sha256": "",
                    "created_at": "2026-09-01T10:00:00Z",
                },
                {
                    "version": "2", "content_sha256": "b" * 64,
                    "parent_sha256": "a" * 64, "created_at": "2026-09-02T10:00:00Z",
                },
            ],
        }
        self.assertEqual(MPYYVersionChainEngine.audit(manifest).status, "COMPLETE")
        broken = json.loads(json.dumps(manifest))
        broken["versions"][1]["parent_sha256"] = "c" * 64
        self.assertIn(
            "BROKEN_VERSION_CHAIN",
            [item.code for item in MPYYVersionChainEngine.audit(broken).findings],
        )
        path = Path(self.tmp.name) / "version_chain.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        output = Path(self.tmp.name) / "version_chain_report.json"
        algorithm = AuditMPYYVersionChainAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"MANIFEST": str(path), "OUTPUT_REPORT": str(output)},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["STATUS"], "COMPLETE")
        self.assertEqual(response["HEAD_SHA256"], "b" * 64)

    def test_mpyy_time_weighted_multimodal_accessibility(self):
        from planx_mpyy_studio.core.multimodal_accessibility import (
            MPYYMultimodalAccessibilityEngine,
        )
        from planx_mpyy_studio.provider import AnalyzeMPYYMultimodalAccessibilityAlgorithm

        network = QgsVectorLayer(
            "LineString?crs=EPSG:5254&field=mode:string&field=speed_kmh:double"
            "&field=travel_time_min:double&field=direction:string",
            "multimodal_network", "memory",
        )
        for wkt, attributes in (
            ("LINESTRING(0 0,100 0)", ["WALK", 6.0, None, "BOTH"]),
            ("LINESTRING(100 0,1100 0)", ["TRANSIT", 60.0, None, "BOTH"]),
        ):
            feature = QgsFeature(network.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            feature.setAttributes(attributes)
            network.dataProvider().addFeature(feature)
        demand = QgsVectorLayer("Point?crs=EPSG:5254", "demand", "memory")
        demand_feature = QgsFeature(demand.fields())
        demand_feature.setGeometry(QgsGeometry.fromWkt("POINT(0 0)"))
        demand.dataProvider().addFeature(demand_feature)
        facilities = QgsVectorLayer("Point?crs=EPSG:5254", "facilities", "memory")
        facility = QgsFeature(facilities.fields())
        facility.setGeometry(QgsGeometry.fromWkt("POINT(1100 0)"))
        facilities.dataProvider().addFeature(facility)
        result = MPYYMultimodalAccessibilityEngine.analyze(
            network.getFeatures(), demand.getFeatures(), facilities.getFeatures(),
            5.0, walk_speed_kmh=6.0, transit_speed_kmh=60.0,
            transfer_penalty_min=2.0,
        )
        self.assertEqual(result.accessible_count, 1)
        self.assertAlmostEqual(result.records[0].route_time_min, 4.0, places=6)
        self.assertEqual(result.records[0].modes, "WALK>TRANSIT")

        algorithm = AnalyzeMPYYMultimodalAccessibilityAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "NETWORK": network, "MODE_FIELD": "mode", "SPEED_FIELD": "speed_kmh",
                "TRAVEL_TIME_FIELD": "travel_time_min", "DIRECTION_FIELD": "direction",
                "DEMAND": demand, "FACILITIES": facilities, "MAX_TIME_MIN": 5.0,
                "WALK_SPEED_KMH": 6.0, "BICYCLE_SPEED_KMH": 15.0,
                "TRANSIT_SPEED_KMH": 60.0, "TRANSFER_PENALTY_MIN": 2.0,
                "SNAP_TOLERANCE": 1.0, "MAX_SNAP_DISTANCE": 50.0,
                "OUTPUT": "memory:multimodal_audit",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["ACCESSIBLE_COUNT"], 1)
        self.assertEqual(response["SKIPPED_EDGE_COUNT"], 0)

    def test_mpyy_planx_adapted_building_morphology(self):
        from planx_mpyy_studio.core.mpyy_urban_analytics import MPYYBuildingMorphologyEngine
        from planx_mpyy_studio.provider import AnalyzeMPYYBuildingMorphologyAlgorithm

        layer = QgsVectorLayer("Polygon?crs=EPSG:5254", "buildings", "memory")
        for rectangle in (QgsRectangle(0, 0, 10, 10), QgsRectangle(10, 0, 20, 10)):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromRect(rectangle))
            layer.dataProvider().addFeature(feature)
        records = MPYYBuildingMorphologyEngine.analyze(layer.getFeatures())
        self.assertEqual(len(records), 2)
        self.assertAlmostEqual(records[0].area_m2, 100.0)
        self.assertAlmostEqual(records[0].shared_wall_ratio, 0.25)
        algorithm = AnalyzeMPYYBuildingMorphologyAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"BUILDINGS": layer, "OUTPUT": "memory:building_morphology"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["FEATURE_COUNT"], 2)

    def test_mpyy_planx_adapted_spacematrix_density(self):
        from planx_mpyy_studio.core.mpyy_urban_analytics import MPYYSpacematrixEngine
        from planx_mpyy_studio.provider import AnalyzeMPYYSpacematrixDensityAlgorithm

        buildings = QgsVectorLayer(
            "Polygon?crs=EPSG:5254&field=kat:double", "buildings", "memory"
        )
        building = QgsFeature(buildings.fields())
        building.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 10, 10)))
        building["kat"] = 2.0
        buildings.dataProvider().addFeature(building)
        blocks = QgsVectorLayer("Polygon?crs=EPSG:5254", "blocks", "memory")
        block = QgsFeature(blocks.fields())
        block.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 20, 10)))
        blocks.dataProvider().addFeature(block)
        records = MPYYSpacematrixEngine.analyze(
            buildings.getFeatures(), blocks.getFeatures(), "kat", 1.0
        )
        self.assertAlmostEqual(records[0].gsi, 0.5)
        self.assertAlmostEqual(records[0].fsi, 1.0)
        self.assertAlmostEqual(records[0].osr, 0.5)
        self.assertAlmostEqual(records[0].mean_levels, 2.0)
        algorithm = AnalyzeMPYYSpacematrixDensityAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "BUILDINGS": buildings, "LEVELS_FIELD": "kat", "DEFAULT_LEVELS": 1.0,
                "BLOCKS": blocks, "OUTPUT": "memory:spacematrix",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["FEATURE_COUNT"], 1)

    def test_mpyy_planx_adapted_street_morphology(self):
        from planx_mpyy_studio.core.mpyy_urban_analytics import MPYYStreetMorphologyEngine
        from planx_mpyy_studio.provider import AnalyzeMPYYStreetMorphologyAlgorithm

        network = QgsVectorLayer("LineString?crs=EPSG:5254", "roads", "memory")
        for wkt in (
            "LINESTRING(0 0,100 0)", "LINESTRING(100 0,200 0)",
            "LINESTRING(100 0,100 100)",
        ):
            feature = QgsFeature(network.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            network.dataProvider().addFeature(feature)
        result = MPYYStreetMorphologyEngine.analyze(network.getFeatures(), 1.0, 36)
        self.assertEqual(result.node_count, 4)
        self.assertEqual(result.edge_count, 3)
        self.assertEqual(result.component_count, 1)
        self.assertEqual(result.dead_end_count, 3)
        self.assertEqual(result.intersection_count, 1)
        algorithm = AnalyzeMPYYStreetMorphologyAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"NETWORK": network, "SNAP_TOLERANCE": 1.0, "ORIENTATION_BINS": 36,
             "OUTPUT": "memory:street_morphology"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["NODE_COUNT"], 4)

    def test_mpyy_planx_adapted_scenario_comparison(self):
        import json

        from planx_mpyy_studio.core.mpyy_urban_analytics import MPYYScenarioComparisonEngine
        from planx_mpyy_studio.provider import CompareMPYYPlanScenariosAlgorithm

        first = {"name": "A", "metrics": [
            {"key": "park_area", "label": "Park alanı", "value": 100.0, "direction": "HIGHER"},
            {"key": "deficit", "label": "Donatı açığı", "value": 20.0, "direction": "LOWER"},
        ]}
        second = {"name": "B", "metrics": [
            {"key": "park_area", "label": "Park alanı", "value": 120.0, "direction": "HIGHER"},
            {"key": "deficit", "label": "Donatı açığı", "value": 10.0, "direction": "LOWER"},
        ]}
        rows = MPYYScenarioComparisonEngine.compare(first, second)
        self.assertEqual({row["preferred"] for row in rows}, {"B"})
        first_path = Path(self.tmp.name) / "scenario_a.json"
        second_path = Path(self.tmp.name) / "scenario_b.json"
        first_path.write_text(json.dumps(first), encoding="utf-8")
        second_path.write_text(json.dumps(second), encoding="utf-8")
        algorithm = CompareMPYYPlanScenariosAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {"SCENARIO_A": str(first_path), "SCENARIO_B": str(second_path),
             "OUTPUT": "memory:scenario_comparison"},
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["METRIC_COUNT"], 2)

    def test_mpyy_planx_adapted_accessibility_equity(self):
        from planx_mpyy_studio.core.mpyy_urban_analytics import MPYYAccessEquityEngine
        from planx_mpyy_studio.provider import AnalyzeMPYYAccessibilityEquityAlgorithm

        result = MPYYAccessEquityEngine.analyze([10.0, 20.0], [1.0, 1.0], 15.0, True)
        self.assertAlmostEqual(result.weighted_mean, 15.0)
        self.assertAlmostEqual(result.gini, 1.0 / 6.0)
        self.assertAlmostEqual(result.threshold_share, 0.5)
        layer = QgsVectorLayer(
            "Point?crs=EPSG:5254&field=access:double&field=population:double",
            "access_units", "memory",
        )
        for x, value, population in ((0, 10.0, 1.0), (10, 20.0, 1.0)):
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromWkt(f"POINT({x} 0)"))
            feature.setAttributes([value, population])
            layer.dataProvider().addFeature(feature)
        algorithm = AnalyzeMPYYAccessibilityEquityAlgorithm()
        algorithm.initAlgorithm()
        response = algorithm.processAlgorithm(
            {
                "INPUT": layer, "VALUE_FIELD": "access", "WEIGHT_FIELD": "population",
                "USE_THRESHOLD": True, "THRESHOLD": 15.0, "HIGHER_IS_BETTER": True,
                "OUTPUT_UNITS": "memory:access_equity_units",
                "OUTPUT_SUMMARY": "memory:access_equity_summary",
            },
            QgsProcessingContext(), QgsProcessingFeedback(),
        )
        self.assertEqual(response["UNIT_COUNT"], 2)
        self.assertAlmostEqual(response["GINI"], 1.0 / 6.0)


if __name__ == "__main__":
    unittest.main()
