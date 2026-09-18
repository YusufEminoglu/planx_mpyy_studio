"""Interaction and layout regression tests for the MPYY workbench."""

import tempfile
import unittest
import re
from pathlib import Path

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QPalette
from qgis.PyQt.QtWidgets import QLabel, QFormLayout, QPushButton, QScrollArea
from qgis.PyQt.QtTest import QTest

from ..dock import MPYYDock
from ..gui.catalog import _GROUPS, matches
from ..gui.widgets import WrappedButton
from ..ui_theme import contrast_ratio, studio_colors, apply_native_editor_theme
from ..core.localization import configure_localized_layer, display_label, display_expression

APP = QgsApplication.instance() or QgsApplication([], True)
APP.initQgis()


class Interface:
    def __init__(self):
        self.opened = []
        self.active = None

    def activeLayer(self):
        return self.active

    def openProcessingAlgorithmDialog(self, algorithm_id, parameters):
        self.opened.append((algorithm_id, parameters))


class GuiTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()
        self.iface = Interface()
        self.dock = MPYYDock(self.iface)
        self.dock.resize(360, 800)

    def tearDown(self):
        self.dock.dispose_ui()
        self.dock.close()
        self.dock.deleteLater()
        APP.processEvents()
        QgsProject.instance().clear()

    def select(self, tool_id):
        self.dock.browse_category("")
        for index in range(self.dock.tool_list.count()):
            item = self.dock.tool_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == tool_id:
                self.dock.tool_list.setCurrentItem(item)
                return
        self.fail("Tool not found: " + tool_id)

    def test_catalog_covers_every_processing_algorithm(self):
        described = {row[0] for rows in _GROUPS.values() for row in rows if len(row) < 6 or row[5]}
        actual = {tool.id for tool in self.dock.tools if tool.processing}
        self.assertEqual(actual, described)
        self.assertEqual(len(actual), 86)
        self.assertEqual(self.dock.tabs.count(), 3)
        self.assertEqual([self.dock.tabs.tabText(i).replace('&', '') for i in range(3)],
                         ['Başlangıç', 'Araçlar', 'Kayıt'])
        self.assertEqual(self.iface.opened, [])

    def test_search_category_and_empty_state_do_not_run_tools(self):
        self.dock.browse_category('Ulaşım ve erişim')
        self.assertEqual(self.dock.tool_list.count(), 6)
        self.dock.tool_search.setText("senaryo")
        self.assertEqual(self.dock.tool_list.count(), 1)
        self.assertEqual(self.dock._current_tool_id, "compare_mpyy_accessibility_scenarios")
        self.assertIn("ortak talep", self.dock.tool_inputs.text())
        self.dock.tool_search.setText("no such tool xyz")
        self.assertEqual(self.dock.tool_list.count(), 0)
        self.assertFalse(self.dock.open_tool_button.isEnabled())
        self.assertFalse(self.dock.empty_tools.isHidden())
        self.dock._reset_filters()
        self.assertEqual(self.dock.tool_list.count(), 88)
        self.assertEqual(self.iface.opened, [])

    def test_turkish_names_and_accent_insensitive_search(self):
        self.dock.focus_tool_search()
        self.dock.tool_search.setText("erişilebilirlik")
        self.assertGreaterEqual(self.dock.tool_list.count(), 1)
        first = {self.dock.tool_list.item(index).data(Qt.ItemDataRole.UserRole)
                 for index in range(self.dock.tool_list.count())}
        self.dock.tool_search.setText("erisilebilirlik")
        second = {self.dock.tool_list.item(index).data(Qt.ItemDataRole.UserRole)
                  for index in range(self.dock.tool_list.count())}
        self.assertEqual(first, second)
        self.dock.browse_category('Raporlar ve teslim')
        self.dock.focus_tool_search()
        self.assertEqual(self.dock.tool_category.currentData(), "")

    def test_processing_open_records_configuration_not_completion(self):
        self.select("compare_mpyy_accessibility_scenarios")
        self.dock.open_tool_button.click()
        self.assertEqual(self.iface.opened[0][0], "planx_mpyy_studio:compare_mpyy_accessibility_scenarios")
        self.assertIn("Yapılandırma açıldı", self.dock.status.text())
        self.assertNotIn("tamamlandı", self.dock.status.text().lower())
        self.assertEqual(self.dock._recent_tools[0], "compare_mpyy_accessibility_scenarios")

    def test_keyboard_search_and_activation(self):
        self.dock.focus_tool_search()
        QTest.keyClicks(self.dock.tool_search, "erisilebilirlik senaryolarini karsilastir")
        self.assertEqual(self.dock.tool_list.count(), 1)
        self.assertEqual(self.iface.opened, [])
        QTest.keyClick(self.dock.tool_list, Qt.Key.Key_Return)
        self.assertEqual(self.iface.opened[0][0], "planx_mpyy_studio:compare_mpyy_accessibility_scenarios")

    def test_compact_form_and_back_keep_input_state(self):
        self.select("estimate_plan_capacity")
        self.dock.quick_form_button.click()
        self.assertEqual(self.dock.tool_pages.currentIndex(), 1)
        self.dock.cap_kaks.setValue(2.4)
        self.dock._back_to_tools()
        self.assertEqual(self.dock.tool_pages.currentIndex(), 0)
        self.assertEqual(self.dock._current_tool_id, "estimate_plan_capacity")
        self.dock.show_inline_form("estimate_plan_capacity")
        self.assertEqual(self.dock.cap_kaks.value(), 2.4)
        self.assertEqual(self.iface.opened, [])

    def test_field_selectors_follow_real_layer_fields(self):
        first = QgsVectorLayer("Polygon?crs=EPSG:5254&field=P_FONK:string", "first", "memory")
        second = QgsVectorLayer("Polygon?crs=EPSG:5254&field=another:string", "second", "memory")
        QgsProject.instance().addMapLayers([first, second])
        self.dock.cw_source.setLayer(first)
        self.assertEqual(self.dock.cw_field.text(), "P_FONK")
        self.dock.cw_source.setLayer(second)
        self.assertNotEqual(self.dock.cw_field.text(), "P_FONK")
        self.assertEqual(self.dock.cw_field.layer(), second)

    def test_saved_shortcuts_and_recent_collection(self):
        self.select("audit_mpyy_schema_profile_identity")
        self.dock._saved_tools.clear()
        self.dock.save_tool_button.click()
        self.dock.tool_scope.setCurrentIndex(self.dock.tool_scope.findData("saved"))
        self.assertEqual(self.dock.tool_list.count(), 1)
        self.assertEqual(self.dock._current_tool_id, "audit_mpyy_schema_profile_identity")
        self.dock.open_tool_button.click()
        self.dock.tool_scope.setCurrentIndex(self.dock.tool_scope.findData("recent"))
        self.assertEqual(self.dock.tool_list.count(), 1)

    def test_status_details_are_bounded_and_copyable(self):
        self.dock.status.setText("Result ready\n" + "A long result line\n" * 100)
        self.assertEqual(self.dock.status.text(), "Result ready")
        self.assertLess(len(self.dock.status.text()), 210)
        self.assertIn("A long result line", self.dock.activity_log.toPlainText())
        self.assertIn("A long result line", self.dock.status.accessibleDescription())

    def test_accessible_form_labels_and_reflow_policy(self):
        page = self.dock._inline_forms["estimate_plan_capacity"]
        group = page.findChild(QFormLayout).parentWidget()
        form = group.layout()
        self.assertEqual(form.rowWrapPolicy(), QFormLayout.RowWrapPolicy.WrapAllRows)
        self.assertEqual(self.dock.cap_kaks.accessibleName(), 'Varsayılan emsal (KAKS)')
        for label in group.findChildren(QLabel):
            self.assertTrue(label.wordWrap())
        button = next(button for button in group.findChildren(QPushButton) if isinstance(button, WrappedButton))
        self.assertTrue(button.sizePolicy().hasHeightForWidth())
        self.assertGreaterEqual(button.heightForWidth(100), button.heightForWidth(300))

    def test_context_updates_and_dispose_disconnects(self):
        first = QgsVectorLayer("Polygon?crs=EPSG:5254", "Example parcels", "memory")
        QgsProject.instance().addMapLayer(first)
        self.assertIn("1 katman", self.dock.project_context.text())
        self.assertGreater(len(self.dock._ui_connections), 0)
        self.dock.dispose_ui()
        self.assertEqual(self.dock._ui_connections, [])
        previous = self.dock.project_context.text()
        QgsProject.instance().clear()
        self.assertEqual(self.dock.project_context.text(), previous)

    def test_light_and_dark_text_contrast(self):
        for dark in (False, True):
            palette = QPalette(APP.palette())
            palette.setColor(QPalette.ColorRole.Window, QColor("#242424" if dark else "#F4F4F4"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#171717" if dark else "#FFFFFF"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#F2F2F2" if dark else "#202020"))
            colors = studio_colors(palette)
            self.assertGreaterEqual(contrast_ratio(colors["text"], colors["surface"]), 4.5)
            self.assertGreaterEqual(contrast_ratio(colors["subtle"], colors["surface"]), 4.5)
            self.assertGreaterEqual(contrast_ratio(colors["on_accent"], colors["accent"]), 4.5)
            apply_native_editor_theme(self.dock, palette)
            self.assertIn(colors["base"].name(), self.dock.cap_kaks.lineEdit().styleSheet())
            self.assertIn(colors["text"].name(), self.dock.cap_kaks.lineEdit().styleSheet())
            self.assertEqual(self.dock.cap_kaks.styleSheet(), "")

    def assertTurkish(self, text):
        # HTML/CSS/expressions and user-supplied identifiers are not UI prose.
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>|\[%.*?%\]', ' ', text, flags=re.DOTALL)
        self.assertFalse(re.search(
            r'\b(workspace|layer|layers|output|input|report|ready|open|selected|created|failed|'
            r'error|review|configuration|before|tools|survey|building|private|undamaged|'
            r'yes|must|invalid|required|found|successfully|missing|total|balance|function|'
            r'area|approved|proposed|floor|coverage|population|ratio|detached|attached|'
            r'residential|commercial|minimum|maximum|optional|legend|evidence|dossier|'
            r'default|penalty|footprint|years|regional|investment|spatial|changed|'
            r'facilities|roof|slope|rise|geology|hazard|hydrology|agriculture|forest|basin|'
            r'coast|infrastructure|need|impossible|alignment|decisions|affected|continuity|'
            r'documented|walk|bicycle|transit|strategy|shared|features|speed|minutes)\b',
            text, re.IGNORECASE), text)

    def test_processing_presentation_is_turkish(self):
        from ..provider import MPYYProvider
        provider = MPYYProvider()
        provider.load()
        self.assertEqual(len(provider.algorithms()), 86)
        for algorithm in provider.algorithms():
            with self.subTest(algorithm=algorithm.name()):
                for text in (algorithm.displayName(), algorithm.group(), algorithm.shortHelpString()):
                    self.assertTurkish(text)
                for parameter in algorithm.parameterDefinitions():
                    self.assertTurkish(parameter.description())
                    if hasattr(parameter, 'fileFilter'):
                        self.assertTurkish(parameter.fileFilter())
                    if hasattr(parameter, 'options'):
                        for option in parameter.options():
                            self.assertTurkish(option)
                for output in algorithm.outputDefinitions():
                    self.assertTurkish(output.description())
        provider.unload()

    def test_workspaces_forms_dropdowns_and_legends_are_turkish(self):
        from ..core.db_factory import create_land_use_workspace
        from ..core.local_uip_workspace import create_local_uip_workspace
        from ..core.project_binding import load_project_layers
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            for filename, create in [('uip.gpkg', create_local_uip_workspace), ('survey.gpkg', create_land_use_workspace)]:
                path = Path(folder) / filename
                create(path, 'EPSG:5254')
                layers = load_project_layers(path)
                for layer in layers:
                    with self.subTest(layer=layer.name()):
                        for index, field in enumerate(layer.fields()):
                            self.assertTurkish(layer.attributeAlias(index))
                            self.assertTurkish(layer.constraintDescription(index))
                            setup = layer.editorWidgetSetup(index)
                            if setup.type() == 'ValueMap':
                                entries = setup.config().get('map', [])
                                if isinstance(entries, dict):
                                    entries = [entries]
                                for entry in entries:
                                    for label in entry:
                                        self.assertTurkish(label)
                        def visit(container):
                            self.assertTurkish(container.name())
                            for child in container.children():
                                if hasattr(child, 'children'):
                                    visit(child)
                        visit(layer.editFormConfig().invisibleRootContainer())
                        renderer = layer.renderer()
                        if hasattr(renderer, 'categories'):
                            for category in renderer.categories():
                                self.assertTurkish(category.label())
                        if hasattr(renderer, 'rootRule'):
                            def rules(rule):
                                self.assertTurkish(rule.label())
                                for child in rule.children():
                                    rules(child)
                            rules(renderer.rootRule())
            for group in QgsProject.instance().layerTreeRoot().findGroups():
                self.assertTurkish(group.name())
            QgsProject.instance().clear()

    def test_value_relation_translates_display_and_preserves_keys(self):
        from qgis.core import QgsFeature, QgsEditorWidgetSetup, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
        lookup = QgsVectorLayer('None?field=code:string&field=title:string', 'English lookup fixture', 'memory')
        feature = QgsFeature(lookup.fields())
        feature.setAttributes(['R1', 'Konut Alanı'])
        lookup.dataProvider().addFeatures([feature])
        QgsProject.instance().addMapLayer(lookup)
        layer = QgsVectorLayer('None?field=function:string', 'Lookup fixture', 'memory')
        config = {'Layer': lookup.id(), 'Key': 'code', 'Value': 'title', 'FilterExpression': '"code" = \'R1\''}
        layer.setEditorWidgetSetup(0, QgsEditorWidgetSetup('ValueRelation', config))
        configure_localized_layer(layer)
        current = layer.editorWidgetSetup(0).config()
        self.assertEqual(current['Key'], 'code')
        self.assertEqual(current['FilterExpression'], config['FilterExpression'])
        self.assertTrue(current['Value'].startswith('_mpyy_display_'))
        result = next(lookup.getFeatures())
        self.assertEqual(result['title'], 'Konut Alanı')
        self.assertEqual(result['code'], 'R1')
        self.assertEqual(result[current['Value']], 'Konut Alanı')
        fields_before = lookup.fields().count()
        configure_localized_layer(layer)
        self.assertEqual(lookup.fields().count(), fields_before)
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(lookup))
        context.setFeature(result)
        expression = QgsExpression(display_expression('title', ['Konut Alanı']))
        self.assertFalse(expression.hasParserError(), expression.parserErrorString())
        self.assertEqual(expression.evaluate(context), 'Konut Alanı')
        self.assertEqual(display_label('User-supplied place name'), 'User-supplied place name')

    def test_relation_reference_and_maptip_use_turkish_representations(self):
        from qgis.core import QgsFeature, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
        from ..core.local_uip_workspace import create_local_uip_workspace
        from ..core.project_binding import load_project_layers
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            path = Path(folder) / 'plan.gpkg'
            create_local_uip_workspace(path, 'EPSG:5254')
            layers = load_project_layers(path)
            layer = next(item for item in layers if item.name() == 'uip-alanlar')
            lookup = next(item for item in layers if item.name() == 'uipPolygonTable')
            raw = next(lookup.getFeatures())['uip_fonksiyon']
            feature = QgsFeature(layer.fields())
            feature['uipfonksiyon'] = raw
            feature['nizam'] = 'A'  # the template form stores A / B / BL
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
            context.setFeature(feature)
            expression = QgsExpression('represent_value("nizam")')
            self.assertFalse(expression.hasParserError())
            self.assertEqual(expression.evaluate(context), 'AYRIK')
            # The MpyyUipDb template keeps its own map tip; the plugin does not overwrite it.
            rendered = QgsExpression.replaceExpressionText(layer.mapTipTemplate(), context)
            if rendered:
                self.assertNotIn('[%', rendered)
                self.assertTurkish(re.sub(r'<[^>]+>', ' ', rendered))
            lookup_context = QgsExpressionContext()
            lookup_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(lookup))
            lookup_context.setFeature(next(lookup.getFeatures()))
            display = QgsExpression(lookup.displayExpression())
            self.assertEqual(display.evaluate(lookup_context), raw)
            self.assertEqual(feature['nizam'], 'A')
            self.assertEqual(feature['uipfonksiyon'], raw)
            QgsProject.instance().clear()

    def test_report_templates_are_turkish_and_keep_coded_data(self):
        from qgis.core import QgsFeature, QgsGeometry
        from types import SimpleNamespace
        from ..core.zoning_certificate import ZoningCertificateEngine
        from ..core.report_exporter import PlanReportEngine
        from ..core.plan_notes import PlanNotesEngine
        from ..core.actions import generate_uip_maptip_html, generate_nip_maptip_html, generate_parsel_saha_maptip_html, generate_yapi_saha_maptip_html, generate_yol_saha_maptip_html
        layer = QgsVectorLayer('Polygon?crs=EPSG:5254&field=uipfonksiyon:string&field=nizam:string', 'Certificate fixture', 'memory')
        feature = QgsFeature(layer.fields())
        feature['uipfonksiyon'] = 'KONUT_ALANI'
        feature['nizam'] = 'AYRIK'
        feature.setGeometry(QgsGeometry.fromWkt('POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))'))
        certificate = ZoningCertificateEngine.generate_certificate(feature)
        self.assertEqual(certificate.plan_fonksiyonu, 'KONUT_ALANI')
        self.assertEqual(certificate.yapi_nizami, 'AYRIK')
        self.assertIn('Konut Alanı', certificate.html_content)
        self.assertIn('Ayrık', certificate.html_content)
        self.assertTurkish(certificate.html_content)
        self.assertTurkish(certificate.markdown_content)
        for template in (generate_uip_maptip_html, generate_nip_maptip_html, generate_parsel_saha_maptip_html, generate_yapi_saha_maptip_html, generate_yol_saha_maptip_html):
            self.assertTurkish(re.sub(r'\[%.*?%\]', '', template(), flags=re.DOTALL))
        # Exercise every optional report section, including ASCII-only legacy copy.
        notes = PlanNotesEngine.generate_plan_notes('Türkçe deneme', '1:1,000', features=[feature])
        with tempfile.TemporaryDirectory() as folder:
            report = PlanReportEngine.generate_comprehensive_report(
                folder, [feature],
                capacity_summary=SimpleNamespace(ongorulen_nufus=100, toplam_konut_alani_m2=10000,
                    ortalama_emsal=1.4, toplam_insaat_alani_m2=14000, ongorulen_konut_adedi=140),
                amenity_results=[SimpleNamespace(donati_adi='Açık ve Yeşil Alan', yeterli_mi=True,
                    kisi_basi_standart_m2=10, mevzuat_ihtiyac_m2=1000, planda_ayrilan_m2=1200,
                    kisi_basi_fiili_m2=12)],
                dop_summary=SimpleNamespace(dop_orani_percent=40, toplam_kadastro_m2=10000,
                    toplam_terk_m2=4000, dop_orani_yuzde=40, yasal_sinir_asildi_mi=False),
                compliance_summary=SimpleNamespace(toplam_parsel=10, yapilasabilir_parseller=8,
                    tevhid_zorunlu_parseller=1, ifraz_edilebilir_parseller=1),
                pafta_summary=SimpleNamespace(toplam_pafta_sayisi=1, satir_sayisi=1,
                    sutun_sayisi=1, kapsanan_plan_alani_m2=10000),
                plan_notes=notes,
            )
            for key in ('html_report', 'markdown_report', 'csv_balance'):
                self.assertTurkish(Path(report[key]).read_text(encoding='utf-8-sig'))
        self.assertEqual(feature['uipfonksiyon'], 'KONUT_ALANI')

    def test_shipped_qml_labels_are_turkish_without_rewriting_codes(self):
        import xml.etree.ElementTree as ET
        root = Path(__file__).resolve().parents[1]
        checked = 0
        for path in root.rglob('*.qml'):
            document = ET.parse(path)
            with self.subTest(path=path.name):
                for element in document.getroot().iter():
                    role = {'alias': 'name', 'attributeEditorContainer': 'name',
                            'category': 'label', 'rule': 'label'}.get(element.tag)
                    if role:
                        self.assertTurkish(element.get(role, ''))
                        checked += 1
                for widget in document.getroot().iter('editWidget'):
                    if widget.get('type') == 'ValueMap':
                        for option in widget.iter('Option'):
                            if option.get('type') == 'QString' and 'name' in option.attrib:
                                self.assertTurkish(option.get('name'))
                                checked += 1
        self.assertGreater(checked, 500)
        # Captions still submit the code the template schema stores.
        document = ET.parse(root / 'forms/yerel_uip/uip-alanlar.qml')
        options = [element for element in document.getroot().iter('Option')
                   if element.get('name') == 'AYRIK' and element.get('type') == 'QString']
        self.assertTrue(options)
        self.assertEqual(options[0].get('value'), 'A')


if __name__ == "__main__":
    unittest.main()
