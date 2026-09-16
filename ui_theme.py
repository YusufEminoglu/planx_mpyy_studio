"""Palette-aware visual system shared by every MPYY Studio module."""

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
    accent = QColor("#69B7D4" if dark else "#176B87")
    surface = (
        _mix(window, QColor("#FFFFFF"), 0.07) if dark else _mix(window, base, 0.72)
    )
    card = _mix(window, QColor("#FFFFFF"), 0.12) if dark else base
    border = _mix(text, surface, 0.76 if dark else 0.84)
    subtle = _mix(text, surface, 0.40 if dark else 0.37)
    active = _mix(surface, accent, 0.20 if dark else 0.12)
    on_accent = max((QColor("#FFFFFF"), QColor("#102028")), key=lambda color: contrast_ratio(color, accent))
    return {"surface": surface, "card": card, "text": text, "accent": accent,
            "border": border, "subtle": subtle, "active": active, "base": base,
            "on_accent": on_accent}


def studio_stylesheet(palette=None):
    values = {key: _hex(value) for key, value in studio_colors(palette).items()}
    return (
        """
QWidget#mpyyRoot { background: %(surface)s; color: %(text)s; }
QLabel { color: %(text)s; }
QLabel#sectionTitle, QLabel#fieldHeading { font-weight: 700; }
QFrame#workflowCard { border: 1px solid %(border)s; border-radius: 6px; background: %(card)s; }
QFrame#heroPanel { background: %(active)s; border: 1px solid %(border)s; border-radius: 9px; }
QLabel#heroMark { background: %(accent)s; color: %(on_accent)s; border-radius: 10px; font-weight: 800; }
QLabel#heroEyebrow { color: %(accent)s; font-size: 8pt; font-weight: 700; }
QLabel#heroTitle { color: %(text)s; font-weight: 700; }
QLabel#mutedText { color: %(subtle)s; }
QLabel#statusCard { background: %(active)s; border-left: 3px solid %(accent)s; border-radius: 5px; padding: 7px 9px; }
QTabWidget::pane { border: 1px solid %(border)s; border-radius: 8px; top: -1px; background: %(surface)s; }
QTabBar::tab { background: transparent; color: %(subtle)s; border: none; border-bottom: 2px solid transparent; padding: 7px 9px; margin: 2px; }
QTabBar::tab:selected { color: %(text)s; background: %(active)s; border-bottom-color: %(accent)s; font-weight: 600; }
QTabBar::tab:hover { color: %(accent)s; }
QGroupBox { background: %(card)s; border: 1px solid %(border)s; border-radius: 8px; margin-top: 10px; padding-top: 9px; }
QGroupBox::title { subcontrol-origin: margin; left: 9px; padding: 0 5px; font-weight: 600; }
QLineEdit, QComboBox { background: %(base)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 6px; padding: 6px 8px; }
QPushButton { background: %(card)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 6px; padding: 7px 11px; min-height: 17px; }
QPushButton:hover { border-color: %(accent)s; color: %(accent)s; }
QPushButton#primaryButton { background: %(accent)s; color: %(on_accent)s; border-color: %(accent)s; font-weight: 650; }
QPushButton:disabled { color: %(subtle)s; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus { border: 2px solid %(accent)s; }
QListWidget, QPlainTextEdit { background: %(base)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 5px; }
QListWidget::item { padding: 8px; border-bottom: 1px solid %(border)s; }
QListWidget::item:selected { background: %(accent)s; color: %(on_accent)s; }
QCheckBox, QRadioButton { color: %(text)s; }
QScrollArea, QScrollArea > QWidget > QWidget { border: none; background: transparent; }
"""
        % values
    )
