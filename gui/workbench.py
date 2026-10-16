"""Workbench shell: header, section navigation, pages and session state.

Five sections, in the order a plan is made: Çalışma (workspace, drawing by
plan function, field survey and its crosswalk), Stil, Denetim, Araçlar and
Kayıt. Forms are built by WorkflowFormsMixin and dropped into the slot of
their section; tool calculations live in DockActionsMixin.
"""

import contextlib
from datetime import datetime
from pathlib import Path

from qgis.core import QgsApplication, QgsProject, QgsSettings
from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, QObject, QSize, Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
    QListWidgetItem, QPlainTextEdit, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from .catalog import build_catalog, matches
from .widgets import StatusMessage, WrappedButton as QPushButton, prepare_form
from ..ui_theme import studio_stylesheet, apply_native_editor_theme

MANUAL_URL = "https://geophilo.com/planx_mpyy_studio/"

PAGE_WORK, PAGE_STYLE, PAGE_AUDIT, PAGE_TOOLS, PAGE_LOG = range(5)

# (icon, short label shown under the icon, what the section holds)
SECTIONS = [
    ("nav_work.svg", "Çalışma", "Çalışma alanı, fonksiyon seçerek çizim ve saha araştırması (UİP, NİP, ÇDP, MSP)"),
    ("nav_style.svg", "Stil", "Ek-1e / e-Plan resmî gösterim stilleri ve öznitelik formları"),
    ("nav_audit.svg", "Denetim", "Plan denetimleri: donatı, revizyon, yoğunluk, DOP, PAİY, kapasite"),
    ("nav_tools.svg", "Araçlar", "Bütün işlem algoritmaları ve arama · Ctrl+K"),
    ("nav_log.svg", "Kayıt", "Bu oturumun işlem kaydı ve sonuç ayrıntıları"),
]

# Forms that belong to a section page instead of the audit picker.
WORK_SLOTS = {"create_workspace": "workspace", "draw_plan_function": "draw",
              "create_land_use_workspace": "field", "crosswalk_saha_to_plan": "field"}
STEP_TITLES = {"create_workspace": "1 · Çalışma alanı", "draw_plan_function": "2 · Fonksiyon seçerek çiz",
               "create_land_use_workspace": "3 · Saha araştırması", "crosswalk_saha_to_plan": "Saha → plan kod eşleştirmesi"}
SECTION_FORMS = {"style_and_forms": PAGE_STYLE, **{tool: PAGE_WORK for tool in WORK_SLOTS}}


class _TabsAdapter:
    """Compatibility adapter for test suites or scripts calling dock.tabs."""

    def __init__(self, dock):
        self._dock = dock

    def count(self) -> int:
        return self._dock.nav_list.count()

    def currentIndex(self) -> int:
        return self._dock.main_stack.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        self._dock.set_page(index)

    def tabText(self, index: int) -> str:
        item = self._dock.nav_list.item(index)
        return item.text() if item else ""


class _ToolPagesAdapter:
    """Compatibility adapter for suites expecting dock.tool_pages: 0 = library, 1 = an open form."""

    def __init__(self, dock):
        self._dock = dock

    def currentIndex(self) -> int:
        return 0 if self._dock.main_stack.currentIndex() == PAGE_TOOLS else 1

    def setCurrentIndex(self, index: int) -> None:
        self._dock.set_page(PAGE_TOOLS if index == 0 else PAGE_AUDIT)


class _NavResizer(QObject):
    """Gives every section tile an equal share of the navigation width."""

    def __init__(self, nav):
        super().__init__(nav)
        self._nav = nav

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.fit()
        return False

    def fit(self) -> None:
        width = self._nav.viewport().width()
        count = max(1, self._nav.count())
        size = QSize(max(44, width // count), 54)
        self._nav.setGridSize(size)
        for row in range(self._nav.count()):
            self._nav.item(row).setSizeHint(size)


AUDIT_TITLES = {
    "analyze_amenity_standards": "Donatı Yeterliliği (Madde 11 / Ek-2 Standartları)",
    "evaluate_plan_revision": "Plan Revizyonu ve Eşdeğer Alan (Madde 26)",
    "synthesize_parcel_density": "Parsel ve Yapı Sentezi (Yoğunluk Analizi)",
    "validate_quality_control": "Topoloji ve Çekme Mesafesi Denetimi",
    "calculate_dop_reallocation": "Düzenleme Ortaklık Payı (DOP - Madde 18)",
    "estimate_plan_capacity": "Yapı ve Nüfus Kapasitesi Modellemesi",
    "validate_paiy_compliance": "Parsel Yapılaşabilirlik Ön Denetimi (PAİY)",
    "generate_pafta_grid": "Standart Pafta İndeksi Oluşturma (1/1.000 - 1/5.000)",
    "generate_plan_notes": "Plan Notları ve Yasal Lejant",
    "generate_comprehensive_report": "Plan Açıklama Raporu Dışa Aktarma",
    "apply_corner_chamfer": "Parsel Köşe Pahları (PAİY Madde 20)",
    "generate_print_layout": "Standart Baskı Düzeni Hazırlama (A0 - A3)",
    "calculate_parking_requirement": "Otopark İhtiyacı ve Yeterliliği",
    "prioritize_urban_transformation": "Dönüşüm Önceliği Ön Denetimi (6306)",
    "generate_zoning_certificate": "Resmi İmar Durumu Belgesi (İmar Çapı) & HUD",
    "calculate_shelter_requirement": "Sığınak Kapasitesi Denetimi",
    "generate_land_readjustment_matrix": "Parselasyon Dağıtım Cetveli & Tahsis (Madde 18)",
    "evaluate_transformation_feasibility": "Dönüşüm Hakediş ve Fizibilite (6306)",
}


class WorkbenchMixin:
    def _init_workbench(self) -> None:
        self._ui_connections = []
        self._inline_forms = {}
        self._recent_tools = []
        self._current_tool_id = None
        self._audit_tools = set()
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
        self._icons_dir = Path(__file__).resolve().parent.parent / "icons"

        root = QWidget(self)
        root.setObjectName("mpyyRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._header())
        root_layout.addWidget(self._navigation())

        self.main_stack = QStackedWidget()
        self.main_stack.setObjectName("mpyyMainStack")
        for build in (self._work_page, self._style_page, self._audit_page, self._tools_page, self._activity_page):
            self.main_stack.addWidget(build())
        root_layout.addWidget(self.main_stack, 1)

        self.status = StatusMessage()
        self.status.messageChanged.connect(self._record_activity)
        status_bar = QWidget()
        status_bar.setObjectName("mpyyStatusBar")
        status_layout = QVBoxLayout(status_bar)
        status_layout.setContentsMargins(10, 6, 10, 10)
        status_layout.addWidget(self.status)
        root_layout.addWidget(status_bar)
        self.setWidget(root)

        self.tabs = _TabsAdapter(self)
        self.tool_pages = _ToolPagesAdapter(self)
        self.nav_list.currentRowChanged.connect(self.set_page)
        self.nav_list.setCurrentRow(PAGE_WORK)

        self._build_workspace_forms()
        self._build_style_form()
        self._build_crosswalk_form()
        self._build_analysis_forms()
        self._filter_tools()
        self._refresh_context()
        self.status.setText('Hazır. Bir bölüm seçin ya da Ctrl+K ile araç arayın.')

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

    # ------------------------------------------------------------ shell
    def _header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("mpyyHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 10, 8, 8)
        layout.setSpacing(10)
        logo = QLabel()
        logo.setObjectName("mpyyLogo")
        icon = self._icons_dir / "icon.png"
        if icon.exists():
            logo.setPixmap(QtGui.QIcon(str(icon)).pixmap(QSize(44, 44)))
        logo.setFixedSize(46, 46)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(self._text("PlanX MPYY Studio", "heroTitle"))
        titles.addWidget(self._text("Mekânsal Planlar Yapım Yönetmeliği stüdyosu", "headerSubtitle"))
        layout.addLayout(titles, 1)
        badge = QLabel("v" + self._plugin_version())
        badge.setObjectName("versionBadge")
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        manual = QToolButton()
        manual.setObjectName("headerButton")
        manual.setIcon(QgsApplication.getThemeIcon("/mActionHelpContents.svg"))
        manual.setToolTip("Kullanım kılavuzu (geophilo.com)")
        manual.setAccessibleName("Kullanım kılavuzu")
        manual.setAutoRaise(True)
        manual.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl(MANUAL_URL)))
        layout.addWidget(manual, 0, Qt.AlignmentFlag.AlignTop)
        return header

    @staticmethod
    def _plugin_version() -> str:
        metadata = Path(__file__).resolve().parent.parent / "metadata.txt"
        with contextlib.suppress(OSError):
            for line in metadata.read_text(encoding="utf-8").splitlines():
                if line.startswith("version="):
                    return line.split("=", 1)[1].strip()
        return "1.0.0"

    def _navigation(self) -> QListWidget:
        """Section tiles: an icon over a short name, the full description as tooltip."""
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("mpyyNavList")
        self.nav_list.setViewMode(QListView.ViewMode.IconMode)
        self.nav_list.setFlow(QListView.Flow.LeftToRight)
        self.nav_list.setWrapping(False)
        self.nav_list.setMovement(QListView.Movement.Static)
        self.nav_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.nav_list.setUniformItemSizes(True)
        self.nav_list.setIconSize(QSize(22, 22))
        self.nav_list.setFixedHeight(62)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.nav_list.setAccessibleName("Bölümler")
        for icon_name, label, description in SECTIONS:
            item = QListWidgetItem(QtGui.QIcon(str(self._icons_dir / icon_name)), label)
            item.setToolTip(description)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.nav_list.addItem(item)
        self._nav_resizer = _NavResizer(self.nav_list)
        self.nav_list.viewport().installEventFilter(self._nav_resizer)
        self._nav_resizer.fit()
        return self.nav_list

    def set_page(self, index: int) -> None:
        if index < 0 or index >= self.main_stack.count():
            return
        if self.main_stack.currentIndex() != index:
            self.main_stack.setCurrentIndex(index)
        if self.nav_list.currentRow() != index:
            self.nav_list.blockSignals(True)
            self.nav_list.setCurrentRow(index)
            self.nav_list.blockSignals(False)

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
        page.setObjectName("mpyyPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        scroll.setWidget(page)
        return scroll, layout

    def _page_heading(self, layout, title: str, text: str) -> None:
        layout.addWidget(self._text(title, "sectionTitle"))
        layout.addWidget(self._text(text, "mutedText"))

    def _info_card(self, title: str, text: str, opened: bool = False) -> QFrame:
        """A quiet card whose body folds away: background knowledge, not a task."""
        card = QFrame()
        card.setObjectName("infoCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)
        toggle = QToolButton()
        toggle.setObjectName("foldButton")
        toggle.setText(title)
        toggle.setCheckable(True)
        toggle.setChecked(opened)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.DownArrow if opened else Qt.ArrowType.RightArrow)
        body = self._text(text, "mutedText")
        body.setVisible(opened)

        def fold(on):
            toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
            body.setVisible(on)

        toggle.toggled.connect(fold)
        layout.addWidget(toggle)
        layout.addWidget(body)
        return card

    # ------------------------------------------------------------ pages
    def _work_page(self):
        scroll, layout = self._page()
        self._workspace_scroll = scroll
        self.workspace_layout = layout
        self._page_heading(layout, "Çalışma alanı ve çizim",
                           "Plan kademesine göre bir çalışma alanı açın, plan fonksiyonunu seçerek çizin; "
                           "saha araştırmasını ayrı tutun ve plan kodlarına eşleyin.")
        self.project_context = self._text("", "statusCard")
        self.project_context.setAccessibleName("Mevcut proje bilgileri")
        layout.addWidget(self.project_context)
        self._slots = {}
        for name in ("workspace", "draw", "field"):
            slot = QVBoxLayout()
            slot.setSpacing(10)
            layout.addLayout(slot)
            self._slots[name] = slot
        dossier = QPushButton("Plan dosyası başlat veya dayanakları incele…")
        dossier.clicked.connect(lambda: self.browse_category("Plan dosyası ve dayanaklar"))
        layout.addWidget(dossier)
        layout.addWidget(self._info_card(
            "Plan kademeleri ve kısayollar",
            "MSP (Mekânsal Strateji, 1:250.000 ve üstü) → ÇDP (Çevre Düzeni, 1:50.000/100.000) → "
            "NİP (Nazım İmar, 1:5.000) → UİP (Uygulama İmar, 1:1.000).\n"
            "Saha çalışma alanlarında gözlenen arazi kullanımı ayrı bir GeoPackage içinde saklanır.\n"
            "Ctrl+K: araç ara · Alt+O: seçili aracı aç."))
        layout.addStretch()
        return scroll

    def _style_page(self):
        scroll, layout = self._page()
        self._styling_scroll = scroll
        self.styling_layout = layout
        self._page_heading(layout, "Stil ve öznitelik formları",
                           "Resmî MPYY / e-Plan ve Ek-1e gösterimine uygun kural tabanlı semboloji ile "
                           "değer listeli, sınırları denetlenen formlar.")
        self._style_slot = QVBoxLayout()
        layout.addLayout(self._style_slot)
        layout.addWidget(self._info_card(
            "Resmî gösterim ve standartlar",
            "Mekânsal Planlar Yapım Yönetmeliği Ek-1e ve Ek-1b gösterim kataloğuna uygun kural tabanlı "
            "semboloji ve formlar katmana uygulanır. MSP (1:250.000+), ÇDP (1:50.000/100.000), NİP (1:5.000) "
            "ve UİP (1:1.000) resmî renk ve tarama kurallarını içerir. Lejant yalnızca planda bulunan değerleri gösterir."))
        layout.addStretch()
        return scroll

    def _audit_page(self):
        page = QWidget()
        page.setObjectName("mpyyPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self._page_heading(layout, "Plan denetimleri ve analizler",
                           "İmar mevzuatı, donatı yeterliliği, plan değişikliği, DOP ve parselasyon hesapları.")
        picker_label = QLabel("Denetim")
        picker_label.setObjectName("fieldHeading")
        self.audit_tool_combo = QComboBox()
        self.audit_tool_combo.setAccessibleName("Denetim ve analiz aracı seçimi")
        picker_label.setBuddy(self.audit_tool_combo)
        layout.addWidget(picker_label)
        layout.addWidget(self.audit_tool_combo)
        self.inline_stack = QStackedWidget()
        self.inline_stack.setObjectName("mpyyInlineStack")
        layout.addWidget(self.inline_stack, 1)
        self.audit_tool_combo.currentIndexChanged.connect(self._on_audit_tool_changed)
        return page

    def _on_audit_tool_changed(self, index: int) -> None:
        tool_id = self.audit_tool_combo.itemData(index)
        if tool_id and tool_id in self._inline_forms:
            self.inline_stack.setCurrentWidget(self._inline_forms[tool_id])
            self._current_tool_id = tool_id

    def _tools_page(self):
        library = QWidget()
        library.setObjectName("mpyyPage")
        layout = QVBoxLayout(library)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        search_label = self._text("&Araç bul", "fieldHeading")
        self.tool_search = QLineEdit()
        self.tool_search.setPlaceholderText("Görev, girdi veya planlama terimi ara…  (Ctrl+K)")
        self.tool_search.setClearButtonEnabled(True)
        self.tool_search.addAction(QgsApplication.getThemeIcon("/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        self.tool_search.setAccessibleName("Araç bul")
        self.tool_search.setToolTip("Görev adlarında, gerekli girdilerde veya algoritma kimliklerinde arar. Kısayol: Ctrl+K.")
        search_label.setBuddy(self.tool_search)
        layout.addWidget(search_label)
        layout.addWidget(self.tool_search)
        filters = QHBoxLayout()
        self.tool_category = QComboBox()
        self.tool_category.setAccessibleName("Araç kategorisi")
        self.tool_category.addItem("Tüm kategoriler", "")
        for category in sorted({tool.category for tool in self.tools}):
            self.tool_category.addItem(category, category)
        self.tool_category.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tool_category.setMinimumContentsLength(8)
        self.tool_category.setMinimumWidth(0)
        self.tool_scope = QComboBox()
        self.tool_scope.setAccessibleName("Araç koleksiyonu")
        for label, value in (("Tüm araçlar", "all"), ("Kaydedilen kısayollar", "saved"), ("Son açılanlar", "recent")):
            self.tool_scope.addItem(label, value)
        self.tool_scope.setMinimumWidth(0)
        self.tool_scope.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tool_scope.setMinimumContentsLength(6)
        filters.addWidget(self.tool_category, 1)
        filters.addWidget(self.tool_scope, 1)
        layout.addLayout(filters)
        self.tool_count = self._text("", "mutedText")
        self.tool_count.setAccessibleName("Eşleşen araç sayısı")
        layout.addWidget(self.tool_count)
        self.empty_tools = self._text("Eşleşen araç yok. Aramayı temizleyin, kategoriyi değiştirin veya Tüm araçlar seçeneğini kullanın.")
        layout.addWidget(self.empty_tools)
        self.reset_tools = QPushButton("Arama ve filtreleri sıfırla")
        self.reset_tools.clicked.connect(self._reset_filters)
        layout.addWidget(self.reset_tools)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        self.tool_list = QListWidget()
        self.tool_list.setObjectName("toolList")
        self.tool_list.setAccessibleName("Eşleşen araçlar")
        self.tool_list.setWordWrap(True)
        self.tool_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tool_list.setMinimumHeight(110)
        self.tool_list.currentItemChanged.connect(self._preview_tool)
        self.tool_list.itemActivated.connect(self._activate_selected_tool)
        splitter.addWidget(self.tool_list)
        details, detail_layout = self._page()
        self.tool_title = self._text("Bir araç seçin", "sectionTitle")
        self.tool_purpose = self._text("")
        self.tool_inputs = self._text("")
        self.tool_output = self._text("")
        self.tool_inputs.setAccessibleName("Başlamadan önce")
        self.tool_output.setAccessibleName("Elde edeceğiniz sonuç")
        for widget in (self.tool_title, self.tool_purpose, self._text("Başlamadan önce", "fieldHeading"),
                       self.tool_inputs, self._text("Elde edeceğiniz sonuç", "fieldHeading"), self.tool_output):
            detail_layout.addWidget(widget)
        self.open_tool_button = QPushButton("Aracı aç…")
        self.open_tool_button.setObjectName("primaryButton")
        self.open_tool_button.setToolTip("Yapılandırmayı açar; henüz analizi çalıştırmaz. Kısayol: Alt+O.")
        self.open_tool_button.clicked.connect(self._activate_selected_tool)
        self.quick_form_button = QPushButton("Kısa formu kullan…")
        self.quick_form_button.setToolTip("Sonuçları doğrudan mevcut projeye uygular. Büyük analizler için İşlem Araç Kutusunu kullanın.")
        self.quick_form_button.clicked.connect(lambda: self.show_inline_form(self._current_tool_id))
        self.save_tool_button = QPushButton("Kısayolu kaydet")
        self.save_tool_button.clicked.connect(self._toggle_saved_tool)
        for widget in (self.open_tool_button, self.quick_form_button, self.save_tool_button):
            detail_layout.addWidget(widget)
        detail_layout.addStretch()
        splitter.addWidget(details)
        splitter.setSizes([230, 360])
        layout.addWidget(splitter, 1)

        self.tool_search.textChanged.connect(self._filter_tools)
        self.tool_search.returnPressed.connect(self.tool_list.setFocus)
        self.tool_category.currentIndexChanged.connect(self._filter_tools)
        self.tool_scope.currentIndexChanged.connect(self._filter_tools)
        return library

    def _activity_page(self):
        page = QWidget()
        page.setObjectName("mpyyPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        self._page_heading(layout, "Oturum kaydı",
                           "Yapılandırma açılışları hesaplama sonuçlarından ayrı kaydedilir. İşlem ilerlemesi ve "
                           "sonuçları QGIS İşlem Araç Kutusunda gösterilir.")
        self.activity_log = QPlainTextEdit()
        self.activity_log.setObjectName("activityLog")
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumBlockCount(400)
        self.activity_log.setAccessibleName("Oturum işlem ayrıntıları")
        layout.addWidget(self.activity_log, 1)
        copy = QPushButton("İşlem kaydını kopyala")
        copy.clicked.connect(lambda: QgsApplication.clipboard().setText(self.activity_log.toPlainText()))
        layout.addWidget(copy)
        return page

    # ------------------------------------------------------------ forms in their sections
    def _register_inline_form(self, tool_id, group) -> None:
        title = group.title()
        group.setAccessibleName(title)
        page, layout = self._page()
        layout.addWidget(group)
        layout.addStretch()
        prepare_form(group)
        self._inline_forms[tool_id] = page

        if tool_id in WORK_SLOTS:
            if tool_id in STEP_TITLES:
                group.setTitle(STEP_TITLES[tool_id])
            self._slots[WORK_SLOTS[tool_id]].addWidget(group)
        elif tool_id == "style_and_forms":
            self._style_slot.addWidget(group)
        else:
            self._audit_tools.add(tool_id)
            self.inline_stack.addWidget(page)
            display_title = AUDIT_TITLES.get(tool_id, title if title else (self._tools_by_id[tool_id].title if tool_id in self._tools_by_id else tool_id))
            self.audit_tool_combo.addItem(display_title, tool_id)

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
        self.tool_count.setText(f"{count} araç kullanılabilir" if count else "Eşleşen araç yok")
        self.empty_tools.setVisible(count == 0)
        self.reset_tools.setVisible(count == 0)
        if count and self.tool_list.currentItem() is None:
            self.tool_list.setCurrentRow(0)
        self._preview_tool(self.tool_list.currentItem())

    def _preview_tool(self, item, *args) -> None:
        tool = self._tools_by_id.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self._current_tool_id = tool.id if tool else None
        self.tool_title.setText(tool.title if tool else "Bir araç seçin")
        self.tool_purpose.setText(tool.purpose if tool else "")
        self.tool_inputs.setText(tool.inputs if tool else "")
        self.tool_output.setText(tool.output if tool else "")
        self.open_tool_button.setEnabled(tool is not None)
        self.save_tool_button.setEnabled(tool is not None)
        self.save_tool_button.setText("Kaydedilen kısayolu kaldır" if tool and tool.id in self._saved_tools else "Kısayolu kaydet")
        self.quick_form_button.setVisible(bool(tool and tool.id in self._inline_forms and tool.id not in
                                                {"create_workspace", "create_land_use_workspace", "style_and_forms"}))

    def _activate_selected_tool(self, *args) -> None:
        if self.main_stack.currentIndex() != PAGE_TOOLS:
            return
        tool = self._tools_by_id.get(self._current_tool_id)
        if tool is None:
            return
        if tool.id in SECTION_FORMS or tool.id in self._audit_tools:
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
        if tool_id in SECTION_FORMS:
            self.set_page(SECTION_FORMS[tool_id])
        elif tool_id in self._audit_tools:
            self.set_page(PAGE_AUDIT)
            idx = self.audit_tool_combo.findData(tool_id)
            if idx >= 0:
                self.audit_tool_combo.setCurrentIndex(idx)
            self.inline_stack.setCurrentWidget(self._inline_forms[tool_id])
        else:
            self.set_page(PAGE_TOOLS)
        self._remember_tool(tool_id)
        self.status.setText("Form açıldı. Girdileri inceleyin.\nUygulamadan önce girdileri doğrulayın.\nAraç: " + tool.title)

    def _back_to_tools(self) -> None:
        self.set_page(PAGE_TOOLS)
        self._filter_tools()
        self.tool_list.setFocus()

    def focus_tool_search(self) -> None:
        self.set_page(PAGE_TOOLS)
        self.tool_category.setCurrentIndex(0)
        self.tool_scope.setCurrentIndex(0)
        self.tool_search.setFocus()
        self.tool_search.selectAll()

    def browse_category(self, category) -> None:
        self.set_page(PAGE_TOOLS)
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
        title = tool.title if tool else "İstenen araç"
        try:
            self.iface.openProcessingAlgorithmDialog("planx_mpyy_studio:" + str(algorithm_name), {})
        except (AttributeError, RuntimeError, TypeError) as error:
            self.status.setText("Açılamadı: " + title + ": " + str(error))
        else:
            self._remember_tool(algorithm_name)
            self.status.setText("Yapılandırma açıldı. İşlem Araç Kutusunda çalıştırın.\nAraç: " + title)

    def _record_activity(self, text: str) -> None:
        self.activity_log.appendPlainText(datetime.now().strftime("%H:%M:%S") + "  " + text + "\n")

    def _refresh_context(self, *args) -> None:
        project = QgsProject.instance()
        count = len(project.mapLayers())
        crs = project.crs()
        crs_text = crs.authid() or ("Özel koordinat sistemi" if crs.isValid() else "Koordinat sistemi belirtilmemiş")
        active = self.iface.activeLayer() if self.iface and hasattr(self.iface, "activeLayer") else None
        text = f"Proje: {count} katman · {crs_text}"
        text += "\nEtkin katman: " + (active.name() if active else "Seçilmedi")
        if not count:
            text += "\nŞimdi bir çalışma alanı oluşturabilir ya da dosya tabanlı plan dosyası araçlarını kullanabilirsiniz."
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
