"""Focused forms extracted from the original dock, with existing action bindings."""

from qgis.core import QgsProject
from qgis.gui import QgsMapLayerComboBox, QgsProjectionSelectionWidget
from qgis.PyQt.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QSpinBox)
from .widgets import FieldSelector, WrappedButton as QPushButton


class WorkflowFormsMixin:
    def _build_workspace_forms(self):

        # Planning workspace group
        group_plan = QGroupBox('MPYY Çalışma Alanı')
        form_plan = QFormLayout(group_plan)
        form_plan.setContentsMargins(9, 8, 9, 9)

        self.crs = QgsProjectionSelectionWidget()
        self.crs.setCrs(QgsProject.instance().crs())
        form_plan.addRow('Çalışma alanı koordinat sistemi', self.crs)

        self.scope = QComboBox()
        self.scope.addItem('Yerel UİP — MpyyUipDb çizim şablonu', "YEREL_UIP")
        self.scope.addItem('Yerel NİP — MpyyNipDB çizim şablonu', "YEREL_NIP")
        for code, label in (("UIP", 'UİP'), ("NIP", 'NİP'), ("CDP", 'ÇDP')):
            self.scope.addItem(f'MPYY 1.1.7 şeması — {label} (e-Plan XSD)', "MPYY_XSD:" + code)
        form_plan.addRow('Plan kademesi', self.scope)

        btn_create = QPushButton('Çalışma alanı oluştur…')
        btn_create.setObjectName("primaryButton")
        btn_create.clicked.connect(self.create_workspace)
        form_plan.addRow(btn_create)

        btn_open = QPushButton('Mevcut çalışma alanını aç…')
        btn_open.clicked.connect(self.open_workspace)
        form_plan.addRow(btn_open)
        self._register_inline_form("create_workspace", group_plan)

        # Land use workspace group
        group_land = QGroupBox('Arazi Kullanımı ve Saha Anketi')
        form_land = QFormLayout(group_land)
        form_land.setContentsMargins(9, 8, 9, 9)
        lbl_info = QLabel('Arazi kullanımı ve saha araştırması kayıtları için ayrı bir GeoPackage oluşturur.')
        lbl_info.setWordWrap(True)
        lbl_info.setObjectName("mutedText")
        form_land.addRow(lbl_info)

        btn_land = QPushButton('Saha çalışma alanı oluştur…')
        btn_land.setObjectName("primaryButton")
        btn_land.clicked.connect(self.create_land_workspace)
        form_land.addRow(btn_land)

        btn_open_land = QPushButton('Mevcut saha çalışma alanını aç…')
        btn_open_land.clicked.connect(self.open_workspace)
        form_land.addRow(btn_open_land)
        self._register_inline_form("create_land_use_workspace", group_land)


    def _build_style_form(self):
        group = QGroupBox('Katman stili ve öznitelik formları')
        form = QFormLayout(group)
        form.setContentsMargins(9, 8, 9, 9)

        self.style_family = QComboBox()
        self.style_family.addItem('Yerel MPYY stilleri', "YEREL")
        self.style_family.addItem('MPYY / e-Plan stilleri', "MPYY")
        self.style_family.currentIndexChanged.connect(self._on_style_family_changed)

        self.plan_type = QComboBox()

        self.style_family_info = QLabel()
        self.style_family_info.setWordWrap(True)
        self.style_family_info.setObjectName("mutedText")

        self.layer = QgsMapLayerComboBox()
        form.addRow('Stil ailesi', self.style_family)
        form.addRow('Plan profili', self.plan_type)
        form.addRow(self.style_family_info)
        form.addRow('Hedef vektör katmanı', self.layer)

        self._on_style_family_changed()

        apply_btn = QPushButton('Stili ve formu uygula')
        apply_btn.setObjectName("primaryButton")
        apply_btn.clicked.connect(self.apply_style)
        form.addRow(apply_btn)

        restore_btn = QPushButton('Önceki stili geri yükle')
        restore_btn.clicked.connect(self.restore_style)
        form.addRow(restore_btn)

        btn_smart_form = QPushButton('Öznitelik formlarını düzenle')
        btn_smart_form.clicked.connect(self.apply_smart_form)
        form.addRow(btn_smart_form)

        self._register_inline_form("style_and_forms", group)


    def _on_style_family_changed(self):
        family = self.style_family.currentData()
        self.plan_type.clear()
        if family == "YEREL":
            self.plan_type.addItem('Uygulama imar planı (UİP, 1:1.000)', "YEREL_UIP")
            self.plan_type.addItem('Arazi kullanım araştırması (1:1.000)', "YEREL_ARAZI")
            self.plan_type.addItem('Nazım imar planı (NİP, taslak)', "YEREL_NIP")
            self.plan_type.addItem('Çevre düzeni planı (ÇDP, yedek stil)', "YEREL_CDP")
            self.style_family_info.setText(
                'Yerel UİP ve saha stilleri kullanılabilir. NİP taslaktır; ÇDP resmî yedek stili kullanır. Uygulamadan önce seçilen profili inceleyin.'
            )
        else:
            self.plan_type.addItem('Uygulama imar planı (UİP, 1:1.000)', "MPYY_UIP")
            self.plan_type.addItem('Nazım imar planı (NİP, 1:5.000)', "MPYY_NIP")
            self.plan_type.addItem('Çevre düzeni planı (ÇDP)', "MPYY_CDP")
            self.plan_type.addItem('Mekânsal Strateji Planı (MSP)', "MPYY_MSP")
            self.style_family_info.setText(
                'Eklentiyle gelen MPYY / e-Plan stillerini ve kod kataloglarını kullanır.'
            )


    def _build_crosswalk_form(self):
        group = QGroupBox('Saha-plan kod eşleştirmesi')
        form = QFormLayout(group)
        form.setContentsMargins(9, 8, 9, 9)

        desc = QLabel(
            'Saha kodlarını plan işlevleriyle eşleştirir. Belirsiz eşleşmeler inceleme için ONAY_BEKLIYOR koduyla işaretlenir.'
        )
        desc.setWordWrap(True)
        desc.setObjectName("mutedText")
        form.addRow(desc)

        self.cw_source = QgsMapLayerComboBox()
        self.cw_target = QgsMapLayerComboBox()
        self.cw_field = FieldSelector("P_FONK")

        form.addRow('Kaynak saha katmanı', self.cw_source)
        form.addRow('Kaynak kod alanı', self.cw_field)
        form.addRow('Hedef plan katmanı', self.cw_target)

        cw_btn = QPushButton('Saha kodlarını eşleştir')
        cw_btn.setObjectName("primaryButton")
        cw_btn.clicked.connect(self.run_crosswalk)
        form.addRow(cw_btn)

        self._register_inline_form("crosswalk_saha_to_plan", group)
        self.cw_source.layerChanged.connect(self.cw_field.bind_layer)


    def _build_analysis_forms(self):

        # Deficit analysis & MPYY EK-2 Automated Layer Extraction
        group_deficit = QGroupBox('Donatı yeterliliği')
        form_deficit = QFormLayout(group_deficit)
        form_deficit.setContentsMargins(9, 8, 9, 9)

        self.spin_pop = QSpinBox()
        self.spin_pop.setRange(1, 10000000)
        self.spin_pop.setValue(5000)
        form_deficit.addRow('Çalışma nüfusu', self.spin_pop)

        self.amenity_plan_layer = QgsMapLayerComboBox()
        form_deficit.addRow('Plan poligonları', self.amenity_plan_layer)

        self.amenity_field = FieldSelector("detay_katalogu")
        form_deficit.addRow('İşlev kodu alanı', self.amenity_field)

        btn_calc_all_def = QPushButton('Donatı yeterliliğini analiz et')
        btn_calc_all_def.setObjectName("primaryButton")
        btn_calc_all_def.clicked.connect(self.run_amenity_analysis)
        form_deficit.addRow(btn_calc_all_def)

        self.edit_green = QLineEdit("25000")
        form_deficit.addRow('Elle girilen yeşil alan (m²)', self.edit_green)

        btn_calc_def = QPushButton('Yeşil alan açığını hesapla')
        btn_calc_def.clicked.connect(self.calculate_deficit)
        form_deficit.addRow(btn_calc_def)
        self._register_inline_form("analyze_amenity_standards", group_deficit)
        self.amenity_plan_layer.layerChanged.connect(self.amenity_field.bind_layer)

        # MPYY Madde 26 Plan Revision and Equivalent Area
        group_diff = QGroupBox('Plan revizyonu ve eşdeğer alan')
        form_diff = QFormLayout(group_diff)
        form_diff.setContentsMargins(9, 8, 9, 9)

        self.diff_old_layer = QgsMapLayerComboBox()
        self.diff_new_layer = QgsMapLayerComboBox()
        form_diff.addRow('Mevcut plan', self.diff_old_layer)
        form_diff.addRow('Önerilen plan', self.diff_new_layer)

        self.diff_radius = QSpinBox()
        self.diff_radius.setRange(50, 5000)
        self.diff_radius.setSingleStep(50)
        self.diff_radius.setValue(500)
        self.diff_radius.setSuffix(" m")
        form_diff.addRow('İnceleme mesafesi', self.diff_radius)

        btn_diff = QPushButton('Plan revizyonunu incele')
        btn_diff.setObjectName("primaryButton")
        btn_diff.clicked.connect(self.run_plan_diff)
        form_diff.addRow(btn_diff)
        self._register_inline_form("evaluate_plan_revision", group_diff)

        # Majority Overlap & Building Density
        group_synth = QGroupBox('Parsel ve yapı sentezi')
        form_synth = QFormLayout(group_synth)
        form_synth.setContentsMargins(9, 8, 9, 9)

        self.synth_parcels = QgsMapLayerComboBox()
        self.synth_plans = QgsMapLayerComboBox()
        self.synth_buildings = QgsMapLayerComboBox()

        form_synth.addRow('Parsel poligonları', self.synth_parcels)
        form_synth.addRow('Plan işlevi katmanı', self.synth_plans)
        form_synth.addRow('Mevcut yapılar', self.synth_buildings)

        btn_synth = QPushButton('Parsel yoğunluğunu analiz et')
        btn_synth.setObjectName("primaryButton")
        btn_synth.clicked.connect(self.run_synthesis)
        form_synth.addRow(btn_synth)

        self._register_inline_form("synthesize_parcel_density", group_synth)

        # Quality Control and Topology
        group_qc = QGroupBox('Topoloji ve çekme mesafesi denetimleri')
        form_qc = QFormLayout(group_qc)
        form_qc.setContentsMargins(9, 8, 9, 9)

        self.qc_parcels = QgsMapLayerComboBox()
        self.qc_buildings = QgsMapLayerComboBox()
        self.qc_setback = QSpinBox()
        self.qc_setback.setRange(1, 50)
        self.qc_setback.setValue(3)

        form_qc.addRow('Parsel poligonları', self.qc_parcels)
        form_qc.addRow('Yapılar (isteğe bağlı)', self.qc_buildings)
        form_qc.addRow('Asgari çekme mesafesi (m)', self.qc_setback)

        btn_qc = QPushButton('Topoloji ve çekme mesafelerini denetle')
        btn_qc.setObjectName("primaryButton")
        btn_qc.clicked.connect(self.run_qc)
        form_qc.addRow(btn_qc)
        self._register_inline_form("validate_quality_control", group_qc)

        # Madde 18 DOP Reallocation Group
        group_dop = QGroupBox('Düzenleme ortaklık payı (DOP)')
        form_dop = QFormLayout(group_dop)
        form_dop.setContentsMargins(9, 8, 9, 9)

        self.dop_cad_layer = QgsMapLayerComboBox()
        self.dop_pub_layer = QgsMapLayerComboBox()
        form_dop.addRow('Kadastro parselleri', self.dop_cad_layer)
        form_dop.addRow('Kamu alanı katmanı', self.dop_pub_layer)

        self.dop_manual_m2 = QDoubleSpinBox()
        self.dop_manual_m2.setRange(0.0, 100000000.0)
        self.dop_manual_m2.setValue(0.0)
        self.dop_manual_m2.setSuffix(" m²")
        form_dop.addRow('Ek kesinti alanı', self.dop_manual_m2)

        self.dop_forced_ratio = QDoubleSpinBox()
        self.dop_forced_ratio.setRange(0.0, 1.0)
        self.dop_forced_ratio.setSingleStep(0.01)
        self.dop_forced_ratio.setValue(0.0)
        form_dop.addRow('Sabit DOP oranı (isteğe bağlı)', self.dop_forced_ratio)

        btn_dop = QPushButton('Kesinti ve tahsisi hesapla')
        btn_dop.setObjectName("primaryButton")
        btn_dop.clicked.connect(self.run_dop)
        form_dop.addRow(btn_dop)
        self._register_inline_form("calculate_dop_reallocation", group_dop)

        # Plan Capacity and Projected Population Modeling
        group_cap = QGroupBox('Yapı ve nüfus kapasitesi')
        form_cap = QFormLayout(group_cap)
        form_cap.setContentsMargins(9, 8, 9, 9)

        self.cap_plan_layer = QgsMapLayerComboBox()
        form_cap.addRow('İmar poligonları', self.cap_plan_layer)

        self.cap_kaks = QDoubleSpinBox()
        self.cap_kaks.setRange(0.1, 10.0)
        self.cap_kaks.setSingleStep(0.1)
        self.cap_kaks.setValue(1.2)
        form_cap.addRow('Varsayılan emsal (KAKS)', self.cap_kaks)

        self.cap_taks = QDoubleSpinBox()
        self.cap_taks.setRange(0.05, 1.0)
        self.cap_taks.setSingleStep(0.05)
        self.cap_taks.setValue(0.35)
        form_cap.addRow('Varsayılan taban alanı oranı (TAKS)', self.cap_taks)

        self.cap_unit_m2 = QDoubleSpinBox()
        self.cap_unit_m2.setRange(20.0, 500.0)
        self.cap_unit_m2.setValue(100.0)
        self.cap_unit_m2.setSuffix(" m²")
        form_cap.addRow('Ortalama konut alanı', self.cap_unit_m2)

        btn_cap = QPushButton('Plan kapasitesini hesapla')
        btn_cap.setObjectName("primaryButton")
        btn_cap.clicked.connect(self.run_capacity)
        form_cap.addRow(btn_cap)
        self._register_inline_form("estimate_plan_capacity", group_cap)

        # PAİY Zoning Compliance and Buildability
        group_paiy = QGroupBox('Parsel yapılaşabilirlik ön denetimi')
        form_paiy = QFormLayout(group_paiy)
        form_paiy.setContentsMargins(9, 8, 9, 9)

        self.paiy_parcels = QgsMapLayerComboBox()
        form_paiy.addRow('Parsel poligonları', self.paiy_parcels)

        self.paiy_nizam = QComboBox()
        for label, val in (
            ('Ayrık (AYRIK)', "AYRIK"),
            ('Bitişik (BITISIK)', "BITISIK"),
            ('İkiz (IKIZ)', "IKIZ"),
            ('Blok (BLOK)', "BLOK"),
            ('Serbest (SERBEST)', "SERBEST"),
        ):
            self.paiy_nizam.addItem(label, val)
        form_paiy.addRow('Yapılaşma Nizamı', self.paiy_nizam)

        self.paiy_floors = QSpinBox()
        self.paiy_floors.setRange(1, 50)
        self.paiy_floors.setValue(4)
        form_paiy.addRow('Varsayılan kat sayısı', self.paiy_floors)

        self.paiy_front = QDoubleSpinBox()
        self.paiy_front.setRange(0.0, 30.0)
        self.paiy_front.setValue(5.0)
        self.paiy_front.setSuffix(" m")
        form_paiy.addRow('ÖN BAHÇE MESAFESİ', self.paiy_front)

        self.paiy_side = QDoubleSpinBox()
        self.paiy_side.setRange(0.0, 30.0)
        self.paiy_side.setValue(3.0)
        self.paiy_side.setSuffix(" m")
        form_paiy.addRow('YAN BAHÇE MESAFESİ', self.paiy_side)

        btn_paiy = QPushButton('Parsel yapılaşabilirliğini denetle')
        btn_paiy.setObjectName("primaryButton")
        btn_paiy.clicked.connect(self.run_paiy_compliance)
        form_paiy.addRow(btn_paiy)
        self._register_inline_form("validate_paiy_compliance", group_paiy)

        # Standard Pafta Grid Indexing
        group_pafta = QGroupBox('Pafta indeksi')
        form_pafta = QFormLayout(group_pafta)
        form_pafta.setContentsMargins(9, 8, 9, 9)

        self.pafta_plan = QgsMapLayerComboBox()
        form_pafta.addRow('Plan katmanı', self.pafta_plan)

        self.pafta_scale = QComboBox()
        self.pafta_scale.addItem("1:1,000 (500 × 500 m)", "1/1.000")
        self.pafta_scale.addItem("1:2,000 (1,000 × 1,000 m)", "1/2.000")
        self.pafta_scale.addItem("1:5,000 (2,500 × 2,000 m)", "1/5.000")
        form_pafta.addRow('Pafta ölçeği', self.pafta_scale)

        self.pafta_prefix = QLineEdit("P")
        form_pafta.addRow('Pafta adı öneki', self.pafta_prefix)

        btn_pafta = QPushButton('Pafta indeksi oluştur')
        btn_pafta.setObjectName("primaryButton")
        btn_pafta.clicked.connect(self.run_pafta_grid)
        form_pafta.addRow(btn_pafta)
        self._register_inline_form("generate_pafta_grid", group_pafta)

        # Plan Notes & Statutory Legend Group
        group_notes = QGroupBox('Plan Notları')
        form_notes = QFormLayout(group_notes)
        form_notes.setContentsMargins(9, 8, 9, 9)

        self.notes_plan = QgsMapLayerComboBox()
        form_notes.addRow('Plan katmanı', self.notes_plan)

        self.notes_title = QLineEdit('Uygulama imar planı (1:1.000)')
        form_notes.addRow('Plan başlığı', self.notes_title)

        self.notes_scale = QComboBox()
        self.notes_scale.addItem('1:1.000 (UİP)', "1/1.000")
        self.notes_scale.addItem('1:5.000 (NİP)', "1/5.000")
        self.notes_scale.addItem('1:25.000 (NİP/ÇDP)', "1/25.000")
        self.notes_scale.addItem('1:50.000 (ÇDP)', "1/50.000")
        self.notes_scale.addItem('1:100.000 (ÇDP)', "1/100.000")
        form_notes.addRow('Plan ölçeği', self.notes_scale)

        btn_notes = QPushButton('İncelenmek üzere plan notları oluştur')
        btn_notes.setObjectName("primaryButton")
        btn_notes.clicked.connect(self.run_plan_notes)
        form_notes.addRow(btn_notes)
        self._register_inline_form("generate_plan_notes", group_notes)

        # Comprehensive Plan Report Group
        group_rep = QGroupBox('Plan açıklama raporu')
        form_rep = QFormLayout(group_rep)
        form_rep.setContentsMargins(9, 8, 9, 9)

        self.rep_plan = QgsMapLayerComboBox()
        form_rep.addRow('Plan katmanı', self.rep_plan)

        self.rep_title = QLineEdit('Uygulama imar planı raporu')
        form_rep.addRow('Rapor başlığı', self.rep_title)

        btn_rep = QPushButton('Plan raporunu dışa aktar…')
        btn_rep.setObjectName("primaryButton")
        btn_rep.clicked.connect(self.run_comprehensive_report)
        form_rep.addRow(btn_rep)
        self._register_inline_form("generate_comprehensive_report", group_rep)

        # PAİY Madde 20 Corner Chamfer Group
        group_chamfer = QGroupBox('Parsel köşe pahları')
        form_chamfer = QFormLayout(group_chamfer)
        form_chamfer.setContentsMargins(9, 8, 9, 9)

        self.chamfer_layer = QgsMapLayerComboBox()
        form_chamfer.addRow('Ada veya parsel poligonları', self.chamfer_layer)

        self.chamfer_dist = QDoubleSpinBox()
        self.chamfer_dist.setRange(0.5, 30.0)
        self.chamfer_dist.setSingleStep(0.5)
        self.chamfer_dist.setValue(3.0)
        self.chamfer_dist.setSuffix(" m")
        form_chamfer.addRow('Pah mesafesi (m)', self.chamfer_dist)

        btn_chamfer = QPushButton('Köşe pahlarını uygula')
        btn_chamfer.setObjectName("primaryButton")
        btn_chamfer.clicked.connect(self.run_corner_chamfer)
        form_chamfer.addRow(btn_chamfer)
        self._register_inline_form("apply_corner_chamfer", group_chamfer)

        # Standard Print Layout Generator Group
        group_layout = QGroupBox('Baskı düzeni')
        form_layout = QFormLayout(group_layout)
        form_layout.setContentsMargins(9, 8, 9, 9)

        self.layout_paper = QComboBox()
        self.layout_paper.addItem("A1 (841 × 594 mm)", "A1")
        self.layout_paper.addItem("A0 (1,189 × 841 mm)", "A0")
        self.layout_paper.addItem("A2 (594 x 420 mm)", "A2")
        self.layout_paper.addItem("A3 (420 × 297 mm)", "A3")
        form_layout.addRow('Kâğıt boyutu', self.layout_paper)

        self.layout_title = QLineEdit('UYGULAMA İMAR PLANI (1:1.000)')
        form_layout.addRow('Plan başlığı', self.layout_title)

        self.layout_muni = QLineEdit('Planlama birimi')
        form_layout.addRow('İdare', self.layout_muni)

        self.layout_pafta = QLineEdit('İ22-c-04-a')
        form_layout.addRow('Pafta No', self.layout_pafta)

        btn_layout = QPushButton('Baskı düzeni oluştur')
        btn_layout.setObjectName("primaryButton")
        btn_layout.clicked.connect(self.run_print_layout)
        form_layout.addRow(btn_layout)
        self._register_inline_form("generate_print_layout", group_layout)

        # Otopark Yönetmeliği İhtiyaç ve Yeterlilik Grubu
        group_parking = QGroupBox('Otopark İhtiyacı')
        form_parking = QFormLayout(group_parking)
        form_parking.setContentsMargins(9, 8, 9, 9)

        self.parking_layer = QgsMapLayerComboBox()
        form_parking.addRow('Plan veya parsel poligonları', self.parking_layer)

        self.parking_kaks = QDoubleSpinBox()
        self.parking_kaks.setRange(0.1, 10.0)
        self.parking_kaks.setSingleStep(0.1)
        self.parking_kaks.setValue(1.2)
        form_parking.addRow('Varsayılan emsal (KAKS)', self.parking_kaks)

        self.parking_area_per_car = QDoubleSpinBox()
        self.parking_area_per_car.setRange(15.0, 50.0)
        self.parking_area_per_car.setValue(25.0)
        self.parking_area_per_car.setSuffix(" m²")
        form_parking.addRow('Araç başına otopark alanı', self.parking_area_per_car)

        btn_parking = QPushButton('Otopark dengesini hesapla')
        btn_parking.setObjectName("primaryButton")
        btn_parking.clicked.connect(self.run_parking_analysis)
        form_parking.addRow(btn_parking)
        self._register_inline_form("calculate_parking_requirement", group_parking)

        # 6306 s. Kentsel Dönüşüm ve Afet Risk Önceliklendirmesi Grubu
        group_risk = QGroupBox('Dönüşüm önceliği ön denetimi')
        form_risk = QFormLayout(group_risk)
        form_risk.setContentsMargins(9, 8, 9, 9)

        self.risk_layer = QgsMapLayerComboBox()
        form_risk.addRow('Yapı veya parseller', self.risk_layer)

        self.risk_ref_year = QSpinBox()
        self.risk_ref_year.setRange(2000, 2100)
        self.risk_ref_year.setValue(2026)
        form_risk.addRow('Değerlendirme yılı', self.risk_ref_year)

        btn_risk = QPushButton('Dönüşüm önceliklerini belirle')
        btn_risk.setObjectName("primaryButton")
        btn_risk.clicked.connect(self.run_transformation_risk)
        form_risk.addRow(btn_risk)
        self._register_inline_form("prioritize_urban_transformation", group_risk)

        # Resmi İmar Durumu Belgesi (İmar Çapı) Grubu
        group_cert = QGroupBox('Parsel imar durumu belgesi')
        form_cert = QFormLayout(group_cert)
        form_cert.setContentsMargins(9, 8, 9, 9)

        self.cert_layer = QgsMapLayerComboBox()
        form_cert.addRow('Parsel poligonları', self.cert_layer)

        self.cert_muni = QLineEdit('Planlama birimi')
        form_cert.addRow('İdare', self.cert_muni)

        self.cert_ilce = QLineEdit("MERKEZ")
        form_cert.addRow('İlçe', self.cert_ilce)

        self.cert_mah = QLineEdit('Mahalle')
        form_cert.addRow('Mahalle', self.cert_mah)

        self.cert_pafta = QLineEdit('İ22-c-04-a')
        form_cert.addRow('Pafta No', self.cert_pafta)

        btn_cert = QPushButton('İmar durumu belgesini dışa aktar…')
        btn_cert.setObjectName("primaryButton")
        btn_cert.clicked.connect(self.run_zoning_certificate)
        form_cert.addRow(btn_cert)

        btn_hud = QPushButton('İmar bilgileri katmanı ekle')
        btn_hud.clicked.connect(self.run_zoning_hud)
        form_cert.addRow(btn_hud)
        self._register_inline_form("generate_zoning_certificate", group_cert)

        # Sığınak Yönetmeliği İhtiyaç ve Yeterlilik Grubu
        group_shelter = QGroupBox('Sığınak kapasitesi')
        form_shelter = QFormLayout(group_shelter)
        form_shelter.setContentsMargins(9, 8, 9, 9)

        self.shelter_layer = QgsMapLayerComboBox()
        form_shelter.addRow('Plan veya parsel poligonları', self.shelter_layer)

        self.shelter_kaks = QDoubleSpinBox()
        self.shelter_kaks.setRange(0.1, 10.0)
        self.shelter_kaks.setSingleStep(0.1)
        self.shelter_kaks.setValue(1.2)
        form_shelter.addRow('Varsayılan emsal (KAKS)', self.shelter_kaks)

        self.shelter_area_pp = QDoubleSpinBox()
        self.shelter_area_pp.setRange(0.8, 3.0)
        self.shelter_area_pp.setValue(1.2)
        self.shelter_area_pp.setSuffix(" m²")
        form_shelter.addRow('Kişi başına sığınak alanı', self.shelter_area_pp)

        btn_shelter = QPushButton('Sığınak kapasitesini hesapla')
        btn_shelter.setObjectName("primaryButton")
        btn_shelter.clicked.connect(self.run_shelter_analysis)
        form_shelter.addRow(btn_shelter)
        self._register_inline_form("calculate_shelter_requirement", group_shelter)

        # İmar Kanunu Madde 18 Parselasyon Dağıtım Cetveli Grubu
        group_alloc = QGroupBox('Tahsis matrisi')
        form_alloc = QFormLayout(group_alloc)
        form_alloc.setContentsMargins(9, 8, 9, 9)

        self.alloc_cad_layer = QgsMapLayerComboBox()
        form_alloc.addRow('Kaynak kadastro parselleri', self.alloc_cad_layer)

        self.alloc_zone_layer = QgsMapLayerComboBox()
        form_alloc.addRow('Hedef imar parselleri', self.alloc_zone_layer)

        self.alloc_dop_ratio = QDoubleSpinBox()
        self.alloc_dop_ratio.setRange(0.0, 0.45)
        self.alloc_dop_ratio.setSingleStep(0.01)
        self.alloc_dop_ratio.setValue(0.40)
        form_alloc.addRow('DOP oranı (en fazla 0,45)', self.alloc_dop_ratio)

        btn_alloc = QPushButton('Tahsis matrisi oluştur…')
        btn_alloc.setObjectName("primaryButton")
        btn_alloc.clicked.connect(self.run_allocation_matrix)
        form_alloc.addRow(btn_alloc)
        self._register_inline_form("generate_land_readjustment_matrix", group_alloc)

        # 6306 s. Kentsel Dönüşüm Hakediş ve Fizibilite Grubu
        group_feas = QGroupBox('Dönüşüm fizibilitesi')
        form_feas = QFormLayout(group_feas)
        form_feas.setContentsMargins(9, 8, 9, 9)

        self.feas_parcel_layer = QgsMapLayerComboBox()
        form_feas.addRow('Dönüşüm alanı parselleri', self.feas_parcel_layer)

        self.feas_contractor_ratio = QDoubleSpinBox()
        self.feas_contractor_ratio.setRange(0.10, 0.90)
        self.feas_contractor_ratio.setSingleStep(0.05)
        self.feas_contractor_ratio.setValue(0.45)
        form_feas.addRow('Müteahhit payı oranı', self.feas_contractor_ratio)

        btn_feas = QPushButton('Dönüşüm fizibilitesini hesapla')
        btn_feas.setObjectName("primaryButton")
        btn_feas.clicked.connect(self.run_transformation_feasibility)
        form_feas.addRow(btn_feas)
        self._register_inline_form("evaluate_transformation_feasibility", group_feas)
