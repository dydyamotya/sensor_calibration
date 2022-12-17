import configparser

from PySide2 import QtWidgets, QtCore
import argparse
import logging

from plotter import ExperimentPlotter
from u_calibration import UCalibrationWidget, ImportCalibrationWidget
from calibration import CalibrationWidget
from measurement import MeasurementWidget
from operation import OperationWidget
import sys
from pyside_constructor_widgets.widgets import comports_list
from database_widgets import DatabaseLeaderComboboxWidget, DatabaseNonleaderComboboxWidget
from sensor_system import MS_Uni, MS_ABC
import socket

from models import Machine, SensorPosition

logger = logging.getLogger(__name__)


class EquipmentSettings(QtWidgets.QWidget):
    redraw_signal = QtCore.Signal(int)

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

        self.machine_name_widget.currentTextChanged.connect(self.comport_widget.on_leader_value_change)
        self.machine_name_widget.currentTextChanged.connect(self.sensor_number_widget.on_leader_value_change)
        self.machine_name_widget.currentTextChanged.connect(self.multirange_widget.on_leader_value_change)

        self.machine_name_widget.activated.connect(self.redraw_signal.emit)
        self.multirange_widget.activated.connect(self.redraw_signal.emit)
        self.sensor_number_widget.activated.connect(self.redraw_signal.emit)
        self.comport_widget.activated.connect(self.redraw_signal.emit)

        self.redraw_signal.connect(self.save_settings)

        last_model_name = self.global_settings.value("lastmodel")
        try:
            self.machine_name_widget.set_new_value(last_model_name)
        except:
            self.machine_name_widget.setCurrentIndex(0)
        self.machine_name_widget.currentTextChanged.emit(self.machine_name_widget.currentText())

    def get_variables(self):
        return (self.comport_widget.get_value(),
                self.sensor_number_widget.get_value(),
                self.multirange_widget.get_value(),
                self.machine_name_widget.get_value(),
                self.machine_name_widget.get_id())

    def get_new_ms(self):
        return MS_Uni(self.sensor_number_widget.get_value(), self.comport_widget.get_value())

    def save_settings(self):
        self.global_settings.setValue("lastmodel", self.machine_name_widget.currentText())


    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.comport_widget.refresh_values(comports_list(), comports_list())

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

class GasStateWidget(QtWidgets.QWidget):
    redraw_signal = QtCore.Signal(int)

    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        self.setWindowTitle("Settings")
        self.global_settings = global_settings

        self.gas_state_server_address = QtWidgets.QLineEdit()
        layout.addRow("GasState Server IP:", self.gas_state_server_address)

        self.gas_state_test = QtWidgets.QLineEdit()
        layout.addRow("Test state:", self.gas_state_test)

        self.gas_state_test.returnPressed.connect(self.send_state_test)
        self.prev_gas_state = None

    def send_state(self, state_num: int):
        if state_num != self.prev_gas_state:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.001)
            ip, port = self.gas_state_server_address.text().split(":")
            s.connect((ip, int(port)))
            s.send(str(state_num).encode("utf-8"))
            s.close()
            self.prev_gas_state = state_num


    def send_state_test(self):
        self.send_state(self.gas_state_test.text())

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()




def main():
    app = QtWidgets.QApplication()
    settings = QtCore.QSettings("MotyaSoft", "SensorinGas Beta")

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s:%(module)s:%(levelname)s:%(message)s')

    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("SensorinGas Beta")

    menu_bar = main_window.menuBar()

    main_window.settings_widget = EquipmentSettings(settings, main_window)
    logger.debug("After equipment setting init")
    action = QtWidgets.QAction("Settings", main_window)
    action.triggered.connect(main_window.settings_widget.toggle_visibility)
    menu_bar.addAction(action)

    main_window.gasstate_widget = GasStateWidget(settings, main_window)
    logger.debug("After gasstate init")
    action = QtWidgets.QAction("GasState Server", main_window)
    action.triggered.connect(main_window.gasstate_widget.toggle_visibility)
    menu_bar.addAction(action)

    main_window.import_widget = ImportCalibrationWidget(settings, main_window)
    action = QtWidgets.QAction("Import", main_window)
    action.triggered.connect(main_window.import_widget.toggle_visibility)
    menu_bar.addAction(action)

    plotter_menu = menu_bar.addMenu("Plotter")
    main_window.plotter_experiment_widget = ExperimentPlotter(main_window)
    action = QtWidgets.QAction("Experiment plotter", main_window)
    action.triggered.connect(main_window.plotter_experiment_widget.toggle_visibility)
    plotter_menu.addAction(action)

    central_widget = QtWidgets.QTabWidget()
    main_window.setCentralWidget(central_widget)

    window = MeasurementWidget(main_window, level, settings)
    central_widget.addTab(window, "Measurement")

    window = OperationWidget(main_window, level, settings, window)
    central_widget.addTab(window, "Operation")

    window = CalibrationWidget(main_window, level, settings)
    central_widget.addTab(window, "Heater calibration")

    window = UCalibrationWidget(main_window, level, settings)
    central_widget.addTab(window, "Sensor calibration")

    main_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
