"""Modular dock UI for planning workspaces, isolated symbology profiles, crosswalk, and synthesis."""

from qgis.PyQt.QtWidgets import QDockWidget

from .core.mpyy_styler import MPYYStylerEngine
from .core.styler import MPYYStylerEngine


from .gui.actions import DockActionsMixin
from .gui.forms import WorkflowFormsMixin
from .gui.workbench import WorkbenchMixin


class MPYYDock(WorkbenchMixin, WorkflowFormsMixin, DockActionsMixin, QDockWidget):
    def __init__(self, iface, parent=None):
        super().__init__("PlanX MPYY Studio", parent)
        self.setObjectName("PlanXMPYYStudioDock")
        self.setMinimumWidth(320)
        self.iface = iface

        self.mpyy_engine = MPYYStylerEngine()
        self.mpyy_engine = MPYYStylerEngine()
        self._last_engine = None

        self._init_workbench()
