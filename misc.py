import PySide2.QtGui
from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import Signal, QEvent
from PySide2.QtGui import QPixmap, QColor

import numpy as np
import pyqtgraph as pg

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

    def disable_all_checkboxes(self):
        for checkbox in self.checkboxes:
            checkbox.setEnabled(False)

    def enable_all_checkboxes(self):
        for checkbox in self.checkboxes:
            checkbox.setEnabled(True)

class PlotCalibrationWidget(QtWidgets.QWidget):
    def __init__(self, parent, x, y, rs_u1, rs_u2, r4):
        super().__init__(parent, f=QtCore.Qt.Tool)

        gl_widget = pg.GraphicsLayoutWidget()
        p1 = gl_widget.addPlot()
        gl_widget.nextRow()
        p2 = gl_widget.addPlot()

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(gl_widget)



        p1.setLogMode(y=True)
        p1.setLabel("bottom", "Voltage, V")
        p1.setLabel("left", "log(R)")
        self.setWindowTitle("Visualization of regression")
        p1.plot(x, y, symbol="o", pen=None)
        linspace = np.linspace(0, 5, num=10000)

        k = 4.068
        def f(u, rs1, rs2):
            return (rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4

        p1.plot(linspace, f(linspace, rs_u1, rs_u2))
        p2.setXLink(p1)
        p2.plot(x, np.abs((y - f(np.array(x), rs_u1, rs_u2)) / y), symbol="o")
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.move(screen.width() / 2, screen.height() / 2)
        self.show()

class FileDialogLineEdit(QtWidgets.QLineEdit):
    def __init__(self, global_settings, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.global_settings = global_settings
        self.name = name
        self.returnPressed.connect(self.return_pressed_callback)

    def event(self, event: PySide2.QtCore.QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonDblClick:
            self.return_pressed_callback()
        return super().event(event)

    def return_pressed_callback(self):
        dirname = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose path",
            self.global_settings.value(self.name, "./tests")
        )
        if dirname:
            self.global_settings.setValue(self.name, dirname)
            self.setText(dirname)



