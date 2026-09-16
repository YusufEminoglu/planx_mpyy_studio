"""Keyboard-friendly, width-aware controls shared by workbench forms."""

from qgis.core import Qgis
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import QRect, QSize, Qt, pyqtSignal
from qgis.PyQt.QtGui import QPalette
from qgis.PyQt.QtWidgets import (
    QAbstractSpinBox, QComboBox, QFormLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QStyle, QStyleOptionButton, QStylePainter,
)


class WrappedButton(QPushButton):
    """Native focus/pressed painting with text that wraps at the available width."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setAccessibleName(text)

    def heightForWidth(self, width):
        rect = self.fontMetrics().boundingRect(QRect(0, 0, max(30, width - 28), 10000),
                                               Qt.TextFlag.TextWordWrap, self.text())
        return max(36, rect.height() + 20)

    def setText(self, text):
        super().setText(text)
        self.setAccessibleName(text)

    def sizeHint(self):
        return QSize(220, self.heightForWidth(220))

    def minimumSizeHint(self):
        return QSize(80, 36)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter.setPen(self.palette().color(group, QPalette.ColorRole.ButtonText))
        painter.drawText(self.rect().adjusted(12, 8, -12, -8),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextShowMnemonic, text)


class FieldSelector(QgsFieldComboBox):
    """Retains the existing action interface while selecting actual layer fields."""

    def __init__(self, preferred_field: str):
        super().__init__()
        self.preferred_field = preferred_field
        self.setAllowEmptyFieldName(True)

    def bind_layer(self, layer) -> None:
        self.setLayer(layer)
        self.setField(self.preferred_field)

    def text(self) -> str:
        return self.currentField()


class StatusMessage(QLabel):
    messageChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("statusCard")
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAccessibleName('Son işlem')
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard |
                                     Qt.TextInteractionFlag.TextSelectableByMouse)

    def setText(self, text: str) -> None:
        lines = str(text).splitlines()
        summary = lines[0] if lines else 'Hazır.'
        if len(summary) > 90:
            summary = summary[:87] + '... Ayrıntılar Kayıt sekmesinde.'
        super().setText(summary)
        self.setAccessibleDescription(str(text))
        self.messageChanged.emit(str(text))


def prepare_form(group) -> None:
    form = group.layout()
    if isinstance(form, QFormLayout):
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(7)
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label_item and isinstance(label_item.widget(), QLabel):
                label = label_item.widget()
                label.setWordWrap(True)
                if field_item and field_item.widget():
                    field = field_item.widget()
                    label.setBuddy(field)
                    field.setAccessibleName(label.text())
    for widget in group.findChildren(QComboBox):
        widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        widget.setMinimumContentsLength(8)
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    for widget in group.findChildren(QgsMapLayerComboBox):
        widget.setFilters(Qgis.LayerFilter.VectorLayer)
        widget.setAllowEmptyLayer(True)
        widget.setLayer(None)
    for widget in group.findChildren(QLabel):
        widget.setWordWrap(True)
        widget.setTextFormat(Qt.TextFormat.PlainText)
    for widget in group.findChildren(QPushButton):
        widget.setAccessibleName(widget.text())
        widget.setMinimumWidth(0)
        if not isinstance(widget, WrappedButton):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    for widget in group.findChildren(QAbstractSpinBox):
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    for widget in group.findChildren(QLineEdit):
        widget.setMinimumWidth(0)
