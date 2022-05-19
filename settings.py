from PySide2 import QtWidgets, QtCore, QtGui
from models import db

class SensorPositionWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QtWidgets.QFormLayout(self)

        self.sensor_num_lineedit = QtWidgets.QLineEdit()
        layout.addRow("Sensor num", self.sensor_num_lineedit)

        self.r4_lineedit = QtWidgets.QLineEdit()
        layout.addRow("R4", self.r4_lineedit)




