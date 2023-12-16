from PySide2 import QtWidgets, QtCore
import argparse
import logging

from choosebestcomb import ChooseBestCombinationOfSensorsWidget
from main_window import MyMainWindow
from u_calibration import UCalibrationWidget
from calibration import CalibrationWidget
from measurement import MeasurementWidget
from operation import OperationWidget
import sys

logger = logging.getLogger(__name__)



def main():
    app = QtWidgets.QApplication()
    settings = QtCore.QSettings("MotyaSoft", "SensorinGas Beta")

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s:%(module)s:%(levelname)s:%(message)s')

    main_window = MyMainWindow(settings)
    main_window.setWindowTitle("SensorinGas Beta")

    menu_bar = main_window.menuBar()

    settings_menu = menu_bar.addMenu("Settings")

    action = QtWidgets.QAction("Settings", main_window)
    action.triggered.connect(main_window.settings_widget.toggle_visibility)
    settings_menu.addAction(action)

    action = QtWidgets.QAction("GasState Server", main_window)
    action.triggered.connect(main_window.gasstate_widget.toggle_visibility)
    settings_menu.addAction(action)

    action = QtWidgets.QAction("Import", main_window)
    action.triggered.connect(main_window.import_widget.toggle_visibility)
    settings_menu.addAction(action)

    action = QtWidgets.QAction("Paths", main_window)
    action.triggered.connect(main_window.paths_widget.toggle_visibility)
    settings_menu.addAction(action)

    plotter_menu = menu_bar.addMenu("Plotter")

    action = QtWidgets.QAction("Experiment plotter", main_window)
    action.triggered.connect(main_window.plotter_experiment_widget.toggle_visibility)
    plotter_menu.addAction(action)

    converter_menu = menu_bar.addMenu("Converter")

    action = QtWidgets.QAction("Binary converter", main_window)
    action.triggered.connect(main_window.converter_widget.toggle_visibility)
    converter_menu.addAction(action)

    experiment_editor_menu = menu_bar.addMenu("Experiment")

    action = QtWidgets.QAction("Editor", main_window)
    action.triggered.connect(main_window.experiment_editor_widget.toggle_visibility)
    experiment_editor_menu.addAction(action)

    central_tab_widget = QtWidgets.QTabWidget()
    main_window.setCentralWidget(central_tab_widget)

    measurement_widget = MeasurementWidget(main_window, settings)
    central_tab_widget.addTab(measurement_widget, "Measurement")

    window = OperationWidget(main_window, settings, measurement_widget)
    central_tab_widget.addTab(window, "Operation")

    window = CalibrationWidget(main_window, level, settings)
    central_tab_widget.addTab(window, "Heater calibration")

    window = UCalibrationWidget(main_window, level, settings)
    central_tab_widget.addTab(window, "Sensor calibration")

    window = ChooseBestCombinationOfSensorsWidget(main_window, level, settings)
    central_tab_widget.addTab(window, "Choose best sensors")

    main_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
