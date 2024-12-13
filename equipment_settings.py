import logging

from PySide2 import QtCore, QtWidgets


from database.base_widgets import (
    DatabaseLeaderComboboxWidget,
    DatabaseNonleaderTableWidget,
)
from database.comport_widget import ComportDatabaseWidget
from database.multirange_widget import MultirangeDatabaseWidget
from database.sensor_number_widget import SensorNumberDatabaseWidget
from database.heater_resistance_converter_widget import HeaterResistanceConverterWidget
from database.models import Machine, SensorPosition
from sensor_system import MS_Uni

logger = logging.getLogger(__name__)

class EquipmentSettings(QtWidgets.QWidget):
    redraw_signal = QtCore.Signal()
    calibration_redraw_signal = QtCore.Signal()
    start_program_signal = QtCore.Signal(int)

    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)

        main_layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()
        buttons_layout = QtWidgets.QHBoxLayout()

        main_layout.addLayout(form_layout)
        main_layout.addLayout(buttons_layout)

        self.setWindowTitle("Settings")
        self.global_settings = global_settings
        self.running_program = False
        self.start_program_signal.connect(self.process_start_program_signal)

        self.machine_name_widget = DatabaseLeaderComboboxWidget(Machine, "name")
        form_layout.addRow("Machine name:", self.machine_name_widget)

        self.comport_widget = ComportDatabaseWidget(self.machine_name_widget)
        form_layout.addRow("Port:", self.comport_widget)

        self.sensor_number_widget = SensorNumberDatabaseWidget(self.machine_name_widget)
        form_layout.addRow("Sensor number:", self.sensor_number_widget)

        self.multirange_widget = MultirangeDatabaseWidget(self.machine_name_widget)
        form_layout.addRow("Multirange:", self.multirange_widget)

        self.modes_widget = DatabaseNonleaderTableWidget(
            self.machine_name_widget, "modes"
        )
        self.multirange_widget.multirange_state_change.connect(self.modes_widget.on_multirange_state_change)
        form_layout.addRow("Modes:", self.modes_widget)

        self.heater_resistance_converter_widget = HeaterResistanceConverterWidget(
            self.machine_name_widget
        )
        form_layout.addRow("Heater resistance converter value", self.heater_resistance_converter_widget)


        self.machine_name_widget.enter_hit_signal.connect(
            self.comport_widget.on_leader_value_change
        )
        self.machine_name_widget.enter_hit_signal.connect(
            self.sensor_number_widget.on_leader_value_change
        )
        self.machine_name_widget.enter_hit_signal.connect(
            self.multirange_widget.on_leader_value_change
        )
        self.machine_name_widget.enter_hit_signal.connect(
            self.modes_widget.on_leader_value_change
        )
        self.machine_name_widget.enter_hit_signal.connect(
            self.heater_resistance_converter_widget.on_leader_value_change
        )

        save_and_redraw_button = QtWidgets.QPushButton('Save and redraw')
        save_and_redraw_button.clicked.connect(self.save_settings)
        buttons_layout.addStretch()
        buttons_layout.addWidget(save_and_redraw_button)

        last_model_name = self.global_settings.value("lastmodel")
        try:
            self.machine_name_widget.set_new_value(last_model_name)
        except:
            self.machine_name_widget.setCurrentIndex(0)
        self.machine_name_widget.enter_hit_signal.emit(
            self.machine_name_widget.currentText()
        )

    def get_variables(self):
        return (
            self.comport_widget.get_value(),
            self.sensor_number_widget.get_value(),
            self.multirange_widget.get_value(),
            self.machine_name_widget.get_value(),
            self.machine_name_widget.get_id(),
        )

    def get_comport(self):
        return self.comport_widget.get_value()

    def get_sensor_number(self) -> int:
        return self.sensor_number_widget.get_value()

    def get_multirange(self) -> bool:
        return self.multirange_widget.get_value()

    def get_new_ms(self):
        if not self.running_program:
            number_of_sensors = self.sensor_number_widget.get_value()
            serial_port = self.comport_widget.get_value()
            heater_resistance_converter = self.heater_resistance_converter_widget.get_value()
            logger.debug(f"New MS device created on port {serial_port} with {number_of_sensors} sensors and converter value: {heater_resistance_converter}")
            return MS_Uni(number_of_sensors, serial_port, heater_resistance_converter)
        else:
            logger.debug("No device created because program is running")
            return None

    def get_r4_data(self):
        r4_data = self.modes_widget.get_data()
        return r4_data

    @QtCore.Slot()
    def save_settings(self):
        self.machine_name_widget.check_new_name()
        self.global_settings.setValue(
            "lastmodel", self.machine_name_widget.currentText()
        )
        self.comport_widget.save_to_database()
        self.sensor_number_widget.save_to_database()
        self.multirange_widget.save_to_database()
        self.modes_widget.save_to_database()

        self.redraw_signal.emit()
        self.calibration_redraw_signal.emit()

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.comport_widget.refresh_values()

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

    def process_start_program_signal(self, started_flag):
        self.running_program = started_flag

    def drop_empty_records_for_machine(self):
        *_, machine_id = self.get_variables()
        for sensor_position in SensorPosition.select().where(
            (SensorPosition.machine == machine_id) & (SensorPosition.r4 == "")
        ):
            sensor_position.delete_instance()


