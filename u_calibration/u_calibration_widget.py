import logging
import typing

from PySide2 import QtWidgets

from misc import clear_layout
from u_calibration.one_sensor_frame import OneSensorFrame

if typing.TYPE_CHECKING:
    from equipment_settings import EquipmentSettings

logger = logging.getLogger(__name__)

class UCalibrationWidget(QtWidgets.QWidget):

    def __init__(self, py_parent, debug_level, global_settings, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_level = debug_level
        self.py_parent = py_parent
        self.settings_widget: "EquipmentSettings" = py_parent.settings_widget
        self.global_settings = global_settings
        self.import_widget = self.py_parent.import_widget
        self.settings_widget.calibration_redraw_signal.connect(self._init_ui)
        QtWidgets.QVBoxLayout(self)
        self._init_ui()

    def _init_ui(self):
        clear_layout(self.layout())
        self.setLayout(self.layout())
        self.widgets = []


        hbox_layout = QtWidgets.QHBoxLayout()
        self.layout().addLayout(hbox_layout)
        for _ in range(3):
            widget = OneSensorFrame(self, self.settings_widget, self.debug_level,
                           self.global_settings, self.import_widget)
            hbox_layout.addWidget(widget)
            self.widgets.append(widget)

        clear_all_button = QtWidgets.QPushButton("Очистить")
        clear_all_button.clicked.connect(self.clear_all)
        hbox_layout.addWidget(clear_all_button)
        hbox_layout.addStretch()

    def clear_all(self):
        msgbox = QtWidgets.QMessageBox()
        msgbox.setText("Уверены, что хотите очистить поля?")
        msgbox.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
        ret = msgbox.exec_()
        if ret == QtWidgets.QMessageBox.Yes:
            for widget in self.widgets:
                for entry in widget.entries.values():
                    entry.clear()


