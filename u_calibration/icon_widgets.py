from PySide2 import QtCore, QtGui, QtWidgets

class PlusWidget(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.label = QtWidgets.QPushButton(icon=QtGui.QIcon("icons/plus.png"))
        self.label.setMinimumSize(20, 20)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label)
        layout.setAlignment(self.label, QtCore.Qt.AlignCenter)
        self.setLayout(layout)

