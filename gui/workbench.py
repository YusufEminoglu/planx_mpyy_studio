"""Workbench navigation and state, independent of tool calculations."""

import contextlib
from datetime import datetime

from qgis.core import QgsApplication, QgsProject, QgsSettings
from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPlainTextEdit, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

from .catalog import build_catalog, matches
from .widgets import StatusMessage, WrappedButton as QPushButton, prepare_form
from ..ui_theme import studio_stylesheet, apply_native_editor_theme


class WorkbenchMixin:
    def _init_workbench(self) -> None:
        self._ui_connections = []
        self._inline_forms = {}
        self._recent_tools = []
        self._current_tool_id = None
        self._settings = QgsSettings()
        self._saved_tools = set(self._settings.value("planx_mpyy_studio/ui/saved_tools", [], type=list))
        provider = QgsApplication.processingRegistry().providerById("planx_mpyy_studio")
        self._catalog_provider = None
        if provider is None:
            from ..provider import MPYYProvider

            provider = MPYYProvider()
            provider.loadAlgorithms()
            # Own the provider while its unregistered algorithm wrappers are used.
            self._catalog_provider = provider
        aliases = {algorithm.name(): algorithm.displayName() for algorithm in provider.algorithms()}
        self.tools = build_catalog(aliases, aliases)
        self._tools_by_id = {tool.id: tool for tool in self.tools}
        self._saved_tools.intersection_update(self._tools_by_id)

        root = QWidget(self)
        root.setObjectName("mpyyRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        title = self._text("PlanX MPYY Studio", "heroTitle")
        layout.addWidget(title)
        layout.addWidget(self._text('Plan hazırlayın, dayanakları inceleyin ve çıktı üretin.', "mutedText"))
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setAccessibleName('Çalışma alanı bölümleri')
        self.tabs.addTab(self._start_page(), "&Başlangıç")
        self.tabs.addTab(self._tools_page(), "&Araçlar")
        self.tabs.addTab(self._activity_page(), "&Kayıt")
        self.tabs.setTabToolTip(2, "Bu oturumun işlem kaydı ve sonuç ayrıntıları")
        layout.addWidget(self.tabs, 1)
        self.status = StatusMessage()
        self.status.messageChanged.connect(self._record_activity)
        layout.addWidget(self.status)
        self.setWidget(root)
        self._build_workspace_forms()
        self._build_style_form()
        self._build_crosswalk_form()
        self._build_analysis_forms()
        self._filter_tools()
        self._refresh_context()
        self.status.setText('Hazır. Çalışma alanı veya araç seçin.')

        self._shortcuts = []
        shortcut_type = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut
        for sequence, callback in (("Ctrl+K", self.focus_tool_search), ("Alt+O", self._activate_selected_tool)):
            shortcut = shortcut_type(QtGui.QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        project = QgsProject.instance()
        for signal in (project.layersAdded, project.layersRemoved, project.crsChanged):
            signal.connect(self._refresh_context)
            self._ui_connections.append((signal, self._refresh_context))
        signal = getattr(self.iface, "currentLayerChanged", None)
        if signal is not None:
            signal.connect(self._refresh_context)
            self._ui_connections.append((signal, self._refresh_context))
        self._ui_ready = True
        self.setStyleSheet(studio_stylesheet(root.palette()))
        apply_native_editor_theme(self, root.palette())

    @staticmethod
    def _text(text: str, object_name: str = "") -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if object_name:
            label.setObjectName(object_name)
        return label

    def _page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        scroll.setWidget(page)
        return scroll, layout

    def _start_page(self):
        scroll, layout = self._page()
        layout.addWidget(self._text('Planlama görevinizle başlayın', "sectionTitle"))
        layout.addWidget(self._text('Yeni proje için bu adımları izleyin. Mevcut projede herhangi bir göreve ulaşmak için Araçlar sekmesini açın.', "mutedText"))
        self.project_context = self._text("")
        self.project_context.setAccessibleName('Mevcut proje bilgileri')
        layout.addWidget(self.project_context)
        for title, explanation, target in (
            ('1. Çalışma alanı oluştur veya aç', 'Plan kademelerini ve koordinat sistemini seçin; saha verisini ayrı veri setinde tutun.', "create_workspace"),
            ('2. Mevcut verileri içe aktar', 'Kadastro, saha veya diğer vektör verilerini içe aktarın.', "ingest_vector_dataset"),
            ('3. Katmanları ve formları biçimlendir', 'Plan profili seçin ve hedef katmanı denetleyin.', "style_and_forms"),
            ('4. Plan kararlarını incele', 'Geometri, plan kademeleri ve plan değişikliği denetimlerini bulun.', 'category:Plan denetimleri'),
            ('5. Raporları ve teslimi hazırla', 'Harita ve rapor oluşturun, ardından teslim paketini inceleyin.', 'category:Raporlar ve teslim'),
        ):
            card = QFrame()
            card.setObjectName("workflowCard")
            card_layout = QVBoxLayout(card)
            button = QPushButton(title)
            button.setAccessibleName(title)
            button.clicked.connect(lambda checked=False, value=target: self._open_start_target(value))
            card_layout.addWidget(button)
            card_layout.addWidget(self._text(explanation, "mutedText"))
            layout.addWidget(card)
        dossier = QPushButton('Plan dosyası başlat veya dayanakları incele…')
        dossier.clicked.connect(lambda: self.browse_category('Plan dosyası ve dayanaklar'))
        layout.addWidget(dossier)
        layout.addWidget(self._text('Plan kademeleri: MSP mekânsal strateji → ÇDP çevre düzeni → NİP nazım imar → UİP uygulama imar planı. Saha çalışma alanlarında gözlenen arazi kullanımı ayrı saklanır.', "mutedText"))
        layout.addWidget(self._text('Klavye: Ctrl+K araç arar. Tab kontroller arasında ilerler. Enter seçilen aracı açar. Alt+O görüntülenen aracı açar.', "mutedText"))
        layout.addStretch()
        return scroll

    def _tools_page(self):
        self.tool_pages = QStackedWidget()
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.setContentsMargins(8, 8, 8, 8)
        search_label = self._text('&Araç bul')
        self.tool_search = QLineEdit()
        self.tool_search.setPlaceholderText('Görev, girdi veya planlama terimi ara…')
        self.tool_search.setClearButtonEnabled(True)
        self.tool_search.setAccessibleName('Araç bul')
        self.tool_search.setToolTip('Görev adlarında, gerekli girdilerde veya algoritma kimliklerinde arar. Kısayol: Ctrl+K.')
        search_label.setBuddy(self.tool_search)
        layout.addWidget(search_label)
        layout.addWidget(self.tool_search)
        filter_layout = QHBoxLayout()
        self.tool_category = QComboBox()
        self.tool_category.setAccessibleName('Araç kategorisi')
        self.tool_category.addItem('Tüm kategoriler', "")
        for category in sorted({tool.category for tool in self.tools}):
            self.tool_category.addItem(category, category)
        self.tool_category.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tool_category.setMinimumContentsLength(8)
        self.tool_category.setMinimumWidth(0)
        self.tool_scope = QComboBox()
        self.tool_scope.setAccessibleName('Araç koleksiyonu')
        for label, value in (('Tüm araçlar', "all"), ('Kaydedilen kısayollar', "saved"), ('Son açılanlar', "recent")):
            self.tool_scope.addItem(label, value)
        self.tool_scope.setMinimumWidth(0)
        self.tool_scope.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tool_scope.setMinimumContentsLength(6)
        filter_layout.addWidget(self.tool_category, 1)
        filter_layout.addWidget(self.tool_scope, 1)
        layout.addLayout(filter_layout)
        self.tool_count = self._text("", "mutedText")
        self.tool_count.setAccessibleName('Eşleşen araç sayısı')
        layout.addWidget(self.tool_count)
        self.empty_tools = self._text('Eşleşen araç yok. Aramayı temizleyin, kategoriyi değiştirin veya Tüm araçlar seçeneğini kullanın.')
        layout.addWidget(self.empty_tools)
        self.reset_tools = QPushButton('Arama ve filtreleri sıfırla')
        self.reset_tools.clicked.connect(self._reset_filters)
        layout.addWidget(self.reset_tools)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.tool_list = QListWidget()
        self.tool_list.setAccessibleName('Eşleşen araçlar')
        self.tool_list.setWordWrap(True)
        self.tool_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tool_list.setMinimumHeight(110)
        self.tool_list.currentItemChanged.connect(self._preview_tool)
        self.tool_list.itemActivated.connect(self._activate_selected_tool)
        splitter.addWidget(self.tool_list)
        details, detail_layout = self._page()
        self.tool_title = self._text('Bir araç seçin', "sectionTitle")
        self.tool_purpose = self._text("")
        self.tool_inputs = self._text("")
        self.tool_output = self._text("")
        self.tool_inputs.setAccessibleName('Başlamadan önce')
        self.tool_output.setAccessibleName('Elde edeceğiniz sonuç')
        for widget in (self.tool_title, self.tool_purpose, self._text('Başlamadan önce', "fieldHeading"),
                       self.tool_inputs, self._text('Elde edeceğiniz sonuç', "fieldHeading"), self.tool_output):
            detail_layout.addWidget(widget)
        self.open_tool_button = QPushButton('Aracı aç…')
        self.open_tool_button.setObjectName("primaryButton")
        self.open_tool_button.setToolTip('Yapılandırmayı açar; henüz analizi çalıştırmaz. Kısayol: Alt+O.')
        self.open_tool_button.clicked.connect(self._activate_selected_tool)
        self.quick_form_button = QPushButton('Kısa formu kullan…')
        self.quick_form_button.setToolTip('Sonuçları doğrudan mevcut projeye uygular. Büyük analizler için İşlem Araç Kutusunu kullanın.')
        self.quick_form_button.clicked.connect(lambda: self.show_inline_form(self._current_tool_id))
        self.save_tool_button = QPushButton('Kısayolu kaydet')
        self.save_tool_button.clicked.connect(self._toggle_saved_tool)
        for widget in (self.open_tool_button, self.quick_form_button, self.save_tool_button):
            detail_layout.addWidget(widget)
        detail_layout.addStretch()
        splitter.addWidget(details)
        splitter.setSizes([220, 360])
        layout.addWidget(splitter, 1)
        self.tool_pages.addWidget(library)
        inline = QWidget()
        inline_layout = QVBoxLayout(inline)
        back = QPushButton('← Araçlara dön')
        back.clicked.connect(self._back_to_tools)
        inline_layout.addWidget(back)
        self.inline_title = self._text("", "sectionTitle")
        self.inline_description = self._text("", "mutedText")
        inline_layout.addWidget(self.inline_title)
        inline_layout.addWidget(self.inline_description)
        self.inline_stack = QStackedWidget()
        inline_layout.addWidget(self.inline_stack, 1)
        self.tool_pages.addWidget(inline)
        self.tool_search.textChanged.connect(self._filter_tools)
        self.tool_search.returnPressed.connect(self.tool_list.setFocus)
        self.tool_category.currentIndexChanged.connect(self._filter_tools)
        self.tool_scope.currentIndexChanged.connect(self._filter_tools)
        return self.tool_pages

    def _activity_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._text('Bu oturumun işlem kaydı', "sectionTitle"))
        layout.addWidget(self._text('Yapılandırma açılışları hesaplama sonuçlarından ayrı kaydedilir. İşlem ilerlemesi ve sonuçları QGIS İşlem Araç Kutusunda gösterilir.', "mutedText"))
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumBlockCount(400)
        self.activity_log.setAccessibleName('Oturum işlem ayrıntıları')
        layout.addWidget(self.activity_log, 1)
        copy = QPushButton('İşlem kaydını kopyala')
        copy.clicked.connect(lambda: QgsApplication.clipboard().setText(self.activity_log.toPlainText()))
        layout.addWidget(copy)
        return page

    def _register_inline_form(self, tool_id, group) -> None:
        group.setAccessibleName(group.title())
        group.setTitle("")
        page, layout = self._page()
        layout.addWidget(group)
        layout.addStretch()
        prepare_form(group)
        self._inline_forms[tool_id] = page
        self.inline_stack.addWidget(page)

    def _filter_tools(self, *args) -> None:
        current = self._current_tool_id
        self.tool_list.blockSignals(True)
        self.tool_list.clear()
        collection = self.tool_scope.currentData()
        for tool in self.tools:
            if collection == "saved" and tool.id not in self._saved_tools:
                continue
            if collection == "recent" and tool.id not in self._recent_tools:
                continue
            if not matches(tool, self.tool_search.text(), self.tool_category.currentData()):
                continue
            item = QListWidgetItem(tool.title + "\n" + tool.category)
            item.setData(Qt.ItemDataRole.UserRole, tool.id)
            item.setToolTip(tool.purpose)
            self.tool_list.addItem(item)
            if tool.id == current:
                self.tool_list.setCurrentItem(item)
        self.tool_list.blockSignals(False)
        count = self.tool_list.count()
        self.tool_count.setText(f"{count} araç kullanılabilir" if count else 'Eşleşen araç yok')
        self.empty_tools.setVisible(count == 0)
        self.reset_tools.setVisible(count == 0)
        if count and self.tool_list.currentItem() is None:
            self.tool_list.setCurrentRow(0)
        self._preview_tool(self.tool_list.currentItem())

    def _preview_tool(self, item, *args) -> None:
        tool = self._tools_by_id.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self._current_tool_id = tool.id if tool else None
        self.tool_title.setText(tool.title if tool else 'Bir araç seçin')
        self.tool_purpose.setText(tool.purpose if tool else "")
        self.tool_inputs.setText(tool.inputs if tool else "")
        self.tool_output.setText(tool.output if tool else "")
        self.open_tool_button.setEnabled(tool is not None)
        self.save_tool_button.setEnabled(tool is not None)
        self.save_tool_button.setText('Kaydedilen kısayolu kaldır' if tool and tool.id in self._saved_tools else 'Kısayolu kaydet')
        self.quick_form_button.setVisible(bool(tool and tool.id in self._inline_forms and tool.id not in
                                                {"create_workspace", "create_land_use_workspace", "style_and_forms"}))

    def _activate_selected_tool(self, *args) -> None:
        if self.tabs.currentIndex() != 1:
            return
        tool = self._tools_by_id.get(self._current_tool_id)
        if tool is None:
            return
        if tool.id in {"create_workspace", "create_land_use_workspace", "style_and_forms"}:
            self.show_inline_form(tool.id)
        elif tool.id == "database_report":
            layer = self.iface.activeLayer() if self.iface and hasattr(self.iface, "activeLayer") else None
            self.layer.setLayer(layer)
            self._remember_tool(tool.id)
            self.generate_db_report()
        else:
            self.open_processing_algorithm(tool.id)

    def show_inline_form(self, tool_id) -> None:
        if tool_id not in self._inline_forms:
            return
        tool = self._tools_by_id[tool_id]
        self._current_tool_id = tool_id
        self.inline_title.setText(tool.title)
        self.inline_description.setText(tool.purpose + '\nSonuç: ' + tool.output)
        self.inline_stack.setCurrentWidget(self._inline_forms[tool_id])
        self.tool_pages.setCurrentIndex(1)
        self.tabs.setCurrentIndex(1)
        self._remember_tool(tool_id)
        self.status.setText('Form açıldı. Girdileri inceleyin.\nUygulamadan önce girdileri doğrulayın.\nAraç: ' + tool.title)

    def _back_to_tools(self) -> None:
        self.tool_pages.setCurrentIndex(0)
        self._filter_tools()
        self.tool_list.setFocus()

    def focus_tool_search(self) -> None:
        self.tabs.setCurrentIndex(1)
        self.tool_pages.setCurrentIndex(0)
        self.tool_category.setCurrentIndex(0)
        self.tool_scope.setCurrentIndex(0)
        self.tool_search.setFocus()
        self.tool_search.selectAll()

    def browse_category(self, category) -> None:
        self.tabs.setCurrentIndex(1)
        self.tool_pages.setCurrentIndex(0)
        self.tool_search.clear()
        self.tool_scope.setCurrentIndex(0)
        self.tool_category.setCurrentIndex(max(0, self.tool_category.findData(category)))
        self.tool_list.setFocus()

    def _open_start_target(self, target) -> None:
        if target.startswith("category:"):
            self.browse_category(target.split(":", 1)[1])
        elif target in self._inline_forms:
            self.show_inline_form(target)
        else:
            self.open_processing_algorithm(target)

    def _reset_filters(self) -> None:
        self.tool_search.clear()
        self.tool_scope.setCurrentIndex(0)
        self.tool_category.setCurrentIndex(0)
        self.tool_search.setFocus()

    def _toggle_saved_tool(self) -> None:
        if not self._current_tool_id:
            return
        tool_id = self._current_tool_id
        if tool_id in self._saved_tools:
            self._saved_tools.remove(tool_id)
        else:
            self._saved_tools.add(tool_id)
        self._settings.setValue("planx_mpyy_studio/ui/saved_tools", sorted(self._saved_tools))
        self._filter_tools()

    def _remember_tool(self, tool_id) -> None:
        if tool_id in self._recent_tools:
            self._recent_tools.remove(tool_id)
        self._recent_tools.insert(0, tool_id)
        del self._recent_tools[12:]

    def open_processing_algorithm(self, algorithm_name) -> None:
        tool = self._tools_by_id.get(algorithm_name)
        title = tool.title if tool else 'İstenen araç'
        try:
            self.iface.openProcessingAlgorithmDialog("planx_mpyy_studio:" + str(algorithm_name), {})
        except (AttributeError, RuntimeError, TypeError) as error:
            self.status.setText('Açılamadı: ' + title + ": " + str(error))
        else:
            self._remember_tool(algorithm_name)
            self.status.setText('Yapılandırma açıldı. İşlem Araç Kutusunda çalıştırın.\nAraç: ' + title)

    def _record_activity(self, text: str) -> None:
        self.activity_log.appendPlainText(datetime.now().strftime("%H:%M:%S") + "  " + text + "\n")

    def _refresh_context(self, *args) -> None:
        project = QgsProject.instance()
        count = len(project.mapLayers())
        crs = project.crs()
        crs_text = crs.authid() or ('Özel koordinat sistemi' if crs.isValid() else 'Koordinat sistemi belirtilmemiş')
        active = self.iface.activeLayer() if self.iface and hasattr(self.iface, "activeLayer") else None
        text = f"Proje: {count} katman · {crs_text}"
        text += '\nEtkin katman: ' + (active.name() if active else 'Seçilmedi')
        if not count:
            text += '\nŞimdi çalışma alanı oluşturabilir veya dosya tabanlı plan dosyası araçlarını kullanabilirsiniz.'
        self.project_context.setText(text)

    def dispose_ui(self) -> None:
        for signal, callback in self._ui_connections:
            with contextlib.suppress(TypeError, RuntimeError):
                signal.disconnect(callback)
        self._ui_connections.clear()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if getattr(self, "_ui_ready", False) and not getattr(self, "_refreshing_theme", False) and event.type() in (
            QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange,
        ):
            self._refreshing_theme = True
            try:
                self.setStyleSheet(studio_stylesheet(QgsApplication.palette()))
                apply_native_editor_theme(self, QgsApplication.palette())
            finally:
                self._refreshing_theme = False
