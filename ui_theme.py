"""Palette-aware visual system shared by every MPYY Studio module.

Colours come from the QGIS palette (light or dark) and are mixed, never
hard-coded, except the studio teal of the plugin icon (accent) and one warm
note for focus. Every text colour keeps a 4.5:1 contrast on its surface.
"""

from qgis.PyQt.QtGui import QColor, QPalette
from qgis.PyQt.QtWidgets import QApplication, QAbstractSpinBox


def apply_native_editor_theme(root, palette=None):
    """Windows spin panels ignore Base; colour their editor without replacing arrows."""
    colors = studio_colors(palette)
    editor_style = "background: %s; color: %s; border: 0; padding: 2px;" % (
        _hex(colors["base"]), _hex(colors["text"]),
    )
    for spin in root.findChildren(QAbstractSpinBox):
        spin.lineEdit().setStyleSheet(editor_style)


def _hex(color):
    return color.name(QColor.NameFormat.HexRgb)


def _mix(first, second, amount):
    return QColor(
        round(first.red() * (1 - amount) + second.red() * amount),
        round(first.green() * (1 - amount) + second.green() * amount),
        round(first.blue() * (1 - amount) + second.blue() * amount),
    )


def contrast_ratio(first, second):
    def luminance(color):
        channels = [value / 255.0 for value in (color.red(), color.green(), color.blue())]
        channels = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
        return sum(value * weight for value, weight in zip(channels, (0.2126, 0.7152, 0.0722)))
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def studio_colors(palette=None):
    palette = palette or QApplication.palette()
    window = palette.color(QPalette.ColorRole.Window)
    base = palette.color(QPalette.ColorRole.Base)
    text = palette.color(QPalette.ColorRole.WindowText)
    dark = window.lightness() < 128
    # The deep teal of the plugin icon's podium, lifted for dark panels.
    accent = QColor("#5FC4D0" if dark else "#136A78")
    surface = _mix(window, QColor("#FFFFFF"), 0.06) if dark else _mix(window, base, 0.65)
    card = _mix(window, QColor("#FFFFFF"), 0.11) if dark else base
    border = _mix(text, surface, 0.78 if dark else 0.86)
    subtle = _mix(text, surface, 0.40 if dark else 0.37)
    active = _mix(surface, accent, 0.20 if dark else 0.11)
    on_accent = max((QColor("#FFFFFF"), QColor("#0D1F24")), key=lambda color: contrast_ratio(color, accent))
    return {"surface": surface, "card": card, "text": text, "accent": accent,
            "border": border, "subtle": subtle, "active": active, "base": base,
            "on_accent": on_accent}


def studio_stylesheet(palette=None):
    values = {key: _hex(value) for key, value in studio_colors(palette).items()}
    return (
        """
QWidget#mpyyRoot { background: %(surface)s; color: %(text)s; }
QWidget#mpyyPage { background: transparent; }
QLabel { color: %(text)s; }

/* Header */
QFrame#mpyyHeader { background: %(card)s; border-bottom: 1px solid %(border)s; }
QLabel#heroTitle { color: %(text)s; font-weight: 700; font-size: 12pt; }
QLabel#headerSubtitle { color: %(subtle)s; font-size: 8.5pt; }
QLabel#versionBadge { background: %(active)s; color: %(accent)s; border: 1px solid %(border)s; border-radius: 9px; padding: 2px 8px; font-size: 7.5pt; font-weight: 700; }
QToolButton#headerButton { border: none; border-radius: 6px; padding: 3px; }
QToolButton#headerButton:hover { background: %(active)s; }

/* Section tiles */
QListWidget#mpyyNavList { background: %(card)s; border: none; border-bottom: 1px solid %(border)s; outline: none; padding: 4px 6px; }
QListWidget#mpyyNavList::item { color: %(subtle)s; border-radius: 8px; border: none; border-bottom: 3px solid transparent; padding: 4px 2px 3px 2px; margin: 2px 2px; font-size: 8pt; }
QListWidget#mpyyNavList::item:hover { background: %(surface)s; color: %(text)s; }
QListWidget#mpyyNavList::item:selected { background: %(active)s; color: %(accent)s; border-bottom: 3px solid %(accent)s; font-weight: 700; }

/* Page text */
QLabel#sectionTitle { font-weight: 700; font-size: 11.5pt; color: %(text)s; }
QLabel#fieldHeading { font-weight: 700; font-size: 9pt; color: %(text)s; }
QLabel#mutedText { color: %(subtle)s; font-size: 8.5pt; }
QLabel#statusCard, QFrame#statusCard { background: %(active)s; border: 1px solid %(border)s; border-left: 3px solid %(accent)s; border-radius: 8px; padding: 8px 10px; }

/* Cards: every form is a card with its title inside */
QGroupBox { background: %(card)s; border: 1px solid %(border)s; border-radius: 10px; margin-top: 4px; padding: 30px 6px 6px 6px; font-weight: 700; }
QGroupBox::title { subcontrol-origin: padding; subcontrol-position: top left; left: 12px; top: 9px; padding: 0; color: %(accent)s; font-size: 9.5pt; }
QFrame#infoCard { background: transparent; border: 1px dashed %(border)s; border-radius: 10px; }
QToolButton#foldButton { border: none; padding: 2px 0; font-weight: 700; color: %(text)s; }

/* Inputs */
QLineEdit, QComboBox { background: %(base)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 7px; padding: 6px 8px; }

/* Buttons */
QPushButton { background: %(card)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px; padding: 8px 12px; min-height: 18px; }
QPushButton:hover { border-color: %(accent)s; color: %(accent)s; }
QPushButton:pressed { background: %(active)s; }
QPushButton#primaryButton { background: %(accent)s; color: %(on_accent)s; border: 1px solid %(accent)s; font-weight: 700; }
QPushButton#primaryButton:hover { background: %(accent)s; color: %(on_accent)s; border-color: %(text)s; }
QPushButton:disabled { color: %(subtle)s; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus { border: 2px solid %(accent)s; }

/* Lists and the log */
QListWidget, QPlainTextEdit { background: %(base)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 8px; }
QListWidget#toolList::item { padding: 8px 10px; border-bottom: 1px solid %(border)s; }
QListWidget#toolList::item:selected { background: %(active)s; color: %(text)s; border-left: 3px solid %(accent)s; }
QListWidget::item:selected { background: %(accent)s; color: %(on_accent)s; }
QPlainTextEdit#activityLog { font-family: "Consolas", "DejaVu Sans Mono", monospace; font-size: 8.5pt; }

/* Frame pieces */
QStackedWidget#mpyyMainStack { background: %(surface)s; border: none; }
QWidget#mpyyStatusBar { background: %(surface)s; border-top: 1px solid %(border)s; }
QSplitter::handle:vertical { height: 6px; background: %(border)s; margin: 2px 40px; border-radius: 3px; }
QSplitter::handle:vertical:hover { background: %(accent)s; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 1px 4px 1px; border-radius: 4px; }
QScrollBar::handle:vertical { background: %(border)s; min-height: 24px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: %(accent)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 1px 4px 1px 4px; border-radius: 4px; }
QScrollBar::handle:horizontal { background: %(border)s; min-width: 24px; border-radius: 4px; }
QScrollBar::handle:horizontal:hover { background: %(accent)s; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: none; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
QCheckBox, QRadioButton { color: %(text)s; }
QScrollArea, QScrollArea > QWidget > QWidget { border: none; background: transparent; }
"""
        % values
    )
