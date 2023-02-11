from PySide2 import QtWidgets, QtCore

from database_widgets import DatabaseLeaderComboboxWidget, DatabaseNonleaderComboboxWidget, DatabaseNonleaderTableWidget
from models import Machine
from pyside_constructor_widgets.widgets import comports_list
from sensor_system import MS_Uni


class EquipmentSettings(QtWidgets.QWidget):
    redraw_signal = QtCore.Signal(int)
    calibration_redraw_signal = QtCore.Signal(int)

    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        self.setWindowTitle("Settings")
        self.global_settings = global_settings

        self.machine_name_widget = DatabaseLeaderComboboxWidget(Machine, "name")
        layout.addRow("Machine name:", self.machine_name_widget)

        self.comport_widget = DatabaseNonleaderComboboxWidget(self.machine_name_widget, "last_port", comports_list(),
                                                              comports_list())
        layout.addRow("Port:", self.comport_widget)

        self.sensor_number_widget = DatabaseNonleaderComboboxWidget(self.machine_name_widget, "sensors_number",
                                                                    ["4", "12"], [4, 12])
        layout.addRow("Sensor number:", self.sensor_number_widget)

        self.multirange_widget = DatabaseNonleaderComboboxWidget(self.machine_name_widget, "multirange", ["yes", "no"],
                                                                 [1, 0])
        layout.addRow("Multirange:", self.multirange_widget)

        self.modes_widget = DatabaseNonleaderTableWidget(self.machine_name_widget, "modes")
        layout.addRow("Modes:", self.modes_widget)

        self.machine_name_widget.enter_hit_signal.connect(self.comport_widget.on_leader_value_change)
        self.machine_name_widget.enter_hit_signal.connect(self.sensor_number_widget.on_leader_value_change)
        self.machine_name_widget.enter_hit_signal.connect(self.multirange_widget.on_leader_value_change)
        self.machine_name_widget.enter_hit_signal.connect(self.modes_widget.on_leader_value_change)

        self.machine_name_widget.activated.connect(self.redraw_signal.emit)
        self.multirange_widget.activated.connect(self.redraw_signal.emit)
        self.sensor_number_widget.activated.connect(self.redraw_signal.emit)
        self.comport_widget.activated.connect(self.redraw_signal.emit)
        self.modes_widget.someValueChanged.connect(self.redraw_signal.emit)

        self.machine_name_widget.activated.connect(self.calibration_redraw_signal.emit)
        self.multirange_widget.activated.connect(self.calibration_redraw_signal.emit)
        self.sensor_number_widget.activated.connect(self.calibration_redraw_signal.emit)
        self.comport_widget.activated.connect(self.calibration_redraw_signal.emit)
        self.modes_widget.someValueChanged.connect(self.calibration_redraw_signal.emit)

        self.redraw_signal.connect(self.save_settings)
        self.calibration_redraw_signal.connect(self.save_settings)

        last_model_name = self.global_settings.value("lastmodel")
        try:
            self.machine_name_widget.set_new_value(last_model_name)
        except:
            self.machine_name_widget.setCurrentIndex(0)
        self.machine_name_widget.enter_hit_signal.emit(self.machine_name_widget.currentText())

    def get_variables(self):
        return (self.comport_widget.get_value(),
                self.sensor_number_widget.get_value(),
                self.multirange_widget.get_value(),
                self.machine_name_widget.get_value(),
                self.machine_name_widget.get_id())

    def get_new_ms(self):
        return MS_Uni(self.sensor_number_widget.get_value(), self.comport_widget.get_value())

    def get_r4_data(self):
        return self.modes_widget.get_data()

    def save_settings(self):
        self.global_settings.setValue("lastmodel", self.machine_name_widget.currentText())


    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.comport_widget.refresh_values(comports_list(), comports_list())

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()