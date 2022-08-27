import PySide2.QtGui
from PySide2 import QtWidgets
from PySide2.QtCore import Signal
from PySide2.QtGui import QPixmap, QColor

class Lamp(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super(Lamp, self).__init__(*args, **kwargs)
        self.running_pixmap = QPixmap(28, 28)
        self.stop_pixmap = QPixmap(28, 28)
        self.running_pixmap.fill(QColor("#00FF00"))
        self.stop_pixmap.fill(QColor("#FF0000"))
    def set_running(self):
        self.setPixmap(self.running_pixmap)

    def set_stop(self):
        self.setPixmap(self.stop_pixmap)

class ClickableLabel(QtWidgets.QLabel):
    clicked = Signal(int, bool)

    def __init__(self, num,  *args, **kwargs):
        super(ClickableLabel, self).__init__(*args, **kwargs)
        self.num = num
        self.state = True
        self.setStyleSheet("border-style:outset; border-width:4px; border-color:black;")

    def mousePressEvent(self, ev:PySide2.QtGui.QMouseEvent) -> None:
        if self.state:
            self.setStyleSheet("border-style:outset; border-width:4px; border-color:white;")
        else:
            self.setStyleSheet("border-style:outset; border-width:4px; border-color:black;")
        self.state = not self.state
        self.clicked.emit(self.num, self.state)

    def set_true(self):
        self.state = True
        self.setStyleSheet("border-style:outset; border-width:4px; border-color:black;")

    def click(self):
        self.mousePressEvent(None)

class TypeCheckLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent, type_, default_value):
        super().__init__(str(default_value), parent)
        self.type_ = type_
        self.default_value = default_value
        if not isinstance(default_value, type_):
            raise TypeError("default value type must be equal to type_ type")

    def get_value(self):
        try:
            return self.type_(self.text())
        except ValueError:
            return self.default_value

    def set_value(self, value):
        if not isinstance(value, self.type_):
            self.setText(str(self.default_value))
        else:
            self.setText(str(value))


def clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget() is not None:
            child.widget().deleteLater()
        elif child.layout() is not None:
            clear_layout(child.layout())

class CssCheckBoxes(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("CSS Sensors")
        layout = QtWidgets.QHBoxLayout(self)

        self.checkboxes = []

        for i in range(1, 13, 4):
            checkbox = QtWidgets.QCheckBox(f"CSS {i:d}-{i+3:d}", parent=self)
            self.checkboxes.append(checkbox)
            layout.addWidget(checkbox)
        layout.addStretch()
    def collect_checkboxes(self):
        return [checkbox.isChecked() for checkbox in self.checkboxes]
