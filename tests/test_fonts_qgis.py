"""The bundled fonts are registered when the plugin loads, not when a project is read.

The defect this guards.  A font marker symbol layer resolves its QFont at the
moment setFontFamily() is called, so a project restored while these fonts are
unregistered falls back to a substitute family — and registering them afterwards
does not repaint it.  Registering from the readProject handler is therefore
already too late; the call has to sit in initGui(), which a plugin loaded at
QGIS start-up reaches before any project is read.

The portability contract is that users do not install fonts themselves: the
plugin registers its bundled notation fonts at application scope and uses its
bundled DejaVu Sans for ordinary text when a source family is unavailable.
Headless tests verify that every shipped file can be registered; they do not
make pixel-identical rendering claims across operating systems.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QFontDatabase

from planx_mpyy_studio.main_plugin import PlanXMPYYStudioPlugin

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()

FONTS_DIR = Path(__file__).resolve().parents[1] / "resources" / "fonts"


class _StubIface:
    """Just enough of the QGIS interface for initGui() and unload() to run."""

    def mainWindow(self):
        return None

    def addPluginToMenu(self, menu, action):
        pass

    def addToolBarIcon(self, action):
        pass

    def removePluginMenu(self, menu, action):
        pass

    def removeToolBarIcon(self, action):
        pass


class FontRegistrationOnLoadTests(unittest.TestCase):
    def _plugin(self):
        plugin = PlanXMPYYStudioPlugin(_StubIface())
        # LIFO: drop the action first so unload() never calls QAction methods on
        # a stand-in, then release the readProject connection unload() made.
        self.addCleanup(plugin.unload)
        self.addCleanup(lambda: setattr(plugin, "action", None))
        return plugin

    def _initgui_recording(self, plugin):
        """Run initGui() with provider registration silenced and fonts recorded."""
        calls = []
        with patch.object(PlanXMPYYStudioPlugin, "initProcessing", lambda self: None), patch(
            "planx_mpyy_studio.core.fonts.register_mpyy_fonts", lambda: calls.append(1)
        ):
            plugin.initGui()
        return calls

    def test_initgui_registers_the_bundled_fonts(self):
        """Removing the call from initGui() must fail here."""
        calls = self._initgui_recording(self._plugin())
        self.assertEqual(len(calls), 1)

    def test_registration_survives_a_reload_that_returns_early(self):
        """A reload skips the menu work; the fonts must still be registered.

        The call also has to sit above initGui()'s early return, not merely
        somewhere inside it.
        """
        plugin = self._plugin()
        plugin.action = object()  # dock already built, so initGui() returns early
        self.assertEqual(len(self._initgui_recording(plugin)), 1)


class BundledFontPayloadTests(unittest.TestCase):
    def test_every_shipped_font_is_usable(self):
        """Registration is worthless if the package does not carry working fonts."""
        files = sorted(FONTS_DIR.glob("*.[tT][tT][fF]"))
        self.assertGreater(len(files), 100, "font payload missing from the package")

        unusable = []
        for path in files:
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id < 0 or not QFontDatabase.applicationFontFamilies(font_id):
                unusable.append(path.name)
        self.assertEqual(unusable, [])

    def test_portable_text_fallback_is_bundled(self):
        files = sorted(FONTS_DIR.glob("DejaVuSans*.[tT][tT][fF]"))
        self.assertTrue(files, "portable DejaVu Sans fallback missing")
        families = set()
        for path in files:
            font_id = QFontDatabase.addApplicationFont(str(path))
            self.assertGreaterEqual(font_id, 0, path.name)
            families.update(QFontDatabase.applicationFontFamilies(font_id))
        self.assertIn("DejaVu Sans", families)


if __name__ == "__main__":
    import sys

    result = unittest.main(exit=False).result
    sys.stdout.flush()
    os._exit(0 if result.wasSuccessful() else 1)
