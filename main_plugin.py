"""QGIS lifecycle, based on the repository dock template."""

import sqlite3
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog,
    QgsProject,
    QgsProviderRegistry,
)
from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import Qt


class PlanXMPYYStudioPlugin:
    MENU = "&PlanX MPYY Studio"

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dock = None
        self.provider = None
        self._project_connected = False

    def initProcessing(self) -> None:
        if self.provider is None:
            from .provider import MPYYProvider
            registry = QgsApplication.processingRegistry()
            # QGIS can retain a provider after a failed plugin reload.  Remove
            # only the stale provider owned by this plugin ID before adding the
            # current implementation; otherwise addProvider() returns False.
            stale = registry.providerById("planx_mpyy_studio")
            if stale is not None:
                registry.removeProvider(stale)
            candidate = MPYYProvider()
            if registry.addProvider(candidate):
                self.provider = candidate
            else:
                # A provider registration failure must not make the dock
                # plugin unusable.  Processing remains unavailable, while the
                # workspace and styling UI can still load and report the issue.
                self.provider = None
                QgsMessageLog.logMessage(
                    'MPYY Processing sağlayıcısı kaydedilemedi; dock arayüzü yine de açılacak.',
                    "PlanX MPYY Studio",
                    Qgis.MessageLevel.Warning,
                )

    def initGui(self) -> None:
        # Register the bundled fonts before anything else.  A font marker symbol
        # layer resolves its QFont at the moment setFontFamily() is called, so a
        # project restored without these fonts registered falls back to a
        # substitute family and re-registering later does not repaint it.  A
        # plugin loaded at QGIS start-up reaches this point before any project
        # is read; registering from the readProject handler is already too late.
        from .core.fonts import register_mpyy_fonts

        register_mpyy_fonts()
        self.initProcessing()
        if self.action is not None:
            return
        # QAction moved to QtGui in Qt6; use the QGIS shim on either runtime.
        action_type = getattr(QtGui, "QAction", None) or QtWidgets.QAction
        icon = QtGui.QIcon(str(Path(__file__).parent / "icons" / "icon.png"))
        self.action = action_type(icon, "PlanX MPYY Studio", self.iface.mainWindow())
        self.action.triggered.connect(self.show_panel)
        self.iface.addPluginToMenu(self.MENU, self.action)
        self.iface.addToolBarIcon(self.action)
        QgsProject.instance().readProject.connect(self._rebind_project)
        self._project_connected = True
        self._rebind_project()

    def _rebind_project(self, *args) -> None:
        from .core.project_binding import load_project_layers

        project = QgsProject.instance()
        paths = set()
        for layer in project.mapLayers().values():
            if layer.providerType() == "ogr" and layer.customProperty(
                "mpyy/dataset_id", ""
            ):
                source = QgsProviderRegistry.instance().decodeUri("ogr", layer.source())
                if source.get("path"):
                    paths.add(source["path"])
        for path in paths:
            try:
                load_project_layers(path, project)
            except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
                QgsMessageLog.logMessage(
                    str(error), "PlanX MPYY Studio", Qgis.MessageLevel.Warning
                )

    def show_panel(self) -> None:
        if self.dock is None:
            from .dock import MPYYDock

            self.dock = MPYYDock(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.dock.raise_()

    def unload(self) -> None:
        if self._project_connected:
            QgsProject.instance().readProject.disconnect(self._rebind_project)
            self._project_connected = False
        if self.dock is not None:
            self.dock.dispose_ui()
            self.iface.removeDockWidget(self.dock)
            self.dock.setParent(None)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu(self.MENU, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
