from PySide2 import QtWidgets, QtCore
import argparse
import logging

from choosebestcomb import ChooseBestCombinationOfSensorsWidget
from equipment_settings import EquipmentSettings, PathsWidget
from plotter import ExperimentPlotter
from converter import ConverterWidget
from u_calibration import UCalibrationWidget, ImportCalibrationWidget
from calibration import CalibrationWidget
from measurement import MeasurementWidget
from operation import OperationWidget
import sys
import socket

logger = logging.getLogger(__name__)


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

    settings_menu = menu_bar.addMenu("Settings")
    main_window.settings_widget = EquipmentSettings(settings, main_window)
    logger.debug("After equipment setting init")
    action = QtWidgets.QAction("Settings", main_window)
    action.triggered.connect(main_window.settings_widget.toggle_visibility)
    settings_menu.addAction(action)

    main_window.gasstate_widget = GasStateWidget(settings, main_window)
    logger.debug("After gasstate init")
    action = QtWidgets.QAction("GasState Server", main_window)
    action.triggered.connect(main_window.gasstate_widget.toggle_visibility)
    settings_menu.addAction(action)

    main_window.import_widget = ImportCalibrationWidget(settings, main_window)
    action = QtWidgets.QAction("Import", main_window)
    action.triggered.connect(main_window.import_widget.toggle_visibility)
    settings_menu.addAction(action)

    main_window.paths_widget = PathsWidget(settings)
    action = QtWidgets.QAction("Paths", main_window)
    action.triggered.connect(main_window.paths_widget.toggle_visibility)
    settings_menu.addAction(action)

    plotter_menu = menu_bar.addMenu("Plotter")
    main_window.plotter_experiment_widget = ExperimentPlotter()
    action = QtWidgets.QAction("Experiment plotter", main_window)
    action.triggered.connect(main_window.plotter_experiment_widget.toggle_visibility)
    plotter_menu.addAction(action)

    converter_menu = menu_bar.addMenu("Converter")
    main_window.converter_widget = ConverterWidget(settings)
    action = QtWidgets.QAction("Binary converter", main_window)
    action.triggered.connect(main_window.converter_widget.toggle_visibility)
    converter_menu.addAction(action)

    central_widget = QtWidgets.QTabWidget()
    main_window.setCentralWidget(central_widget)

    window = MeasurementWidget(main_window, settings)
    central_widget.addTab(window, "Measurement")

    window = OperationWidget(main_window, settings, window)
    central_widget.addTab(window, "Operation")

    window = CalibrationWidget(main_window, level, settings)
    central_widget.addTab(window, "Heater calibration")

    window = UCalibrationWidget(main_window, level, settings)
    central_widget.addTab(window, "Sensor calibration")

    window = ChooseBestCombinationOfSensorsWidget(main_window, level, settings)
    central_widget.addTab(window, "Choose best sensors")

    main_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
