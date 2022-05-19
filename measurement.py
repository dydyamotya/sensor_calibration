from yaml import load, dump
from collections import UserDict
import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
from scipy.stats import linregress
from sensor_system import MS_ABC

from PySide2 import QtWidgets, QtCore, QtGui
import logging
from matplotlib import figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from models import SensorPosition
from misc import clear_layout, CssCheckBoxes
logger = logging.getLogger(__name__)

values_for_css_boxes = [MS_ABC.SEND_CSS_1_4,
                        MS_ABC.SEND_CSS_5_8, MS_ABC.SEND_CSS_9_12]

r4_str_values = ["100 kOhm", "1.1 MOhm", "11.1 MOhm"]

class SensorPositionWidget(QtWidgets.QWidget):
    def __init__(self, parent, sensor_num, machine_name):
        super(SensorPositionWidget, self).__init__(parent)
        self.sensor_position = None
        self.sensor_num = sensor_num
        self.machine_name = machine_name
        self.loaded = False
        try:
            self.sensor_position = (SensorPosition.select()
                            .where((SensorPosition.machine_name == machine_name) & (SensorPosition.sensor_num == sensor_num + 1))
                            .order_by(SensorPosition.id.desc())
                            .get())
        except (IndexError, SensorPosition.DoesNotExist):
            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(QtWidgets.QLabel("No data"))
        else:
            layout = QtWidgets.QVBoxLayout(self)

            buttons_layout = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons_layout, stretch=0)

            sensor_position_layout = QtWidgets.QFormLayout()
            sensor_position = self.sensor_position
            layout.addLayout(sensor_position_layout, stretch=1)
            sensor_position_layout.addRow("Sensor num", QtWidgets.QLabel(f"{sensor_position.sensor_num}"))
            sensor_position_layout.addRow("Machine name", QtWidgets.QLabel(f"{machine_name}"))
            sensor_position_layout.addRow("R4", QtWidgets.QLabel(str(sensor_position.r4)))
            sensor_position_layout.addRow("Rs_U1", QtWidgets.QLabel(str(sensor_position.rs_u1)))
            sensor_position_layout.addRow("Rs_U2", QtWidgets.QLabel(str(sensor_position.rs_u2)))
            sensor_position_layout.addRow("Datetime", QtWidgets.QLabel(sensor_position.datetime.isoformat()))

    def load_calibration(self, voltages, resistances, temperatures):
        self.voltages = voltages
        self.resistances = resistances
        self.temperatures = temperatures
        try:
            self.func_T_to_U = interp1d(self.temperatures, self.voltages, kind="cubic")
        except ValueError:
            logger.debug(f"Calibration loading failed for {self.sensor_num} {self.machine_name} sensor")
            self.func_T_to_U = lambda x: 0

        res = linregress(self.temperatures, self.resistances)
        self.func_T_to_R = lambda x: res.intercept + res.slope * x

        self.loaded = True


    def get_resistance_for_temperature(self, temperature: float):
        if not self.loaded:
            return None
        self.func_T_to_R(temperature)

    def get_voltage_for_temperature(self, temperature: float):
        if not self.loaded:
            return None
        self.func_T_to_U(temperature)

    def get_resistance_for_temperature_func(self):
        if not self.loaded:
            return None
        return self.func_T_to_R

    def get_voltage_for_temperature_func(self):
        if not self.loaded:
            return None
        return self.func_T_to_U

    def get_r4(self):
        return r4_str_values.index(self.sensor_position.r4) + 1

class MeasurementWidget(QtWidgets.QWidget):
    def __init__(self, parent, level, global_settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QVBoxLayout(self)
        self.settings_widget = parent.settings_widget
        self.widgets = []
        self.css_boxes = None
        self.multirange_state = False
        self.settings_widget.redraw_signal.connect(self.init_ui)
        self.init_ui()

    def init_ui(self):
        self.widgets = []
        self.css_boxes = None
        clear_layout(self.layout())
        comport, sensor_number, multirange, machine_name = self.settings_widget.get_variables()
        self.multirange_state = multirange

        buttons_layout = QtWidgets.QHBoxLayout()
        self.layout().addLayout(buttons_layout)

        load_calibration_button = QtWidgets.QPushButton("Load calibration")
        load_calibration_button.clicked.connect(self.load_calibration)

        self.load_status_label = QtWidgets.QLabel("Not loaded")
        buttons_layout.addWidget(load_calibration_button)
        buttons_layout.addWidget(self.load_status_label)

        self.css_boxes = CssCheckBoxes()
        self.layout().addWidget(self.css_boxes)

        sensor_position_grid_layout = QtWidgets.QGridLayout()
        self.layout().addLayout(sensor_position_grid_layout)
        for i in range(sensor_number):
            sensor_position_widget = SensorPositionWidget(self, i, machine_name)
            sensor_position_grid_layout.addWidget(sensor_position_widget, i // 4, i % 4)
            sensor_position_grid_layout.setColumnStretch(i % 4, 1)
            sensor_position_grid_layout.setRowStretch(i // 4, 1)
            self.widgets.append(sensor_position_widget)

    def load_calibration(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(self, "Open Calibration File", "./tests", "Resistances File (*.npz)")
        if filename:
            npzfile = np.load(filename)
            try:
                voltages, resistances, temperatures = npzfile["voltages"], npzfile["resistances"], npzfile["temperatures"]
            except KeyError:
                self.load_status_label.setText("Not loaded")
            else:
                for voltage_row, resistance_row, temperatures_row, widget in zip(voltages, resistances, temperatures, self.widgets):
                    widget.load_calibration(voltage_row, resistance_row, temperatures_row)
                self.load_status_label.setText("Loaded")

    def get_sensor_types_list(self):
        if self.css_boxes:
            sensor_types_list = [
                send_code
                for checkbox_state, send_code in zip(
                    self.css_boxes.collect_checkboxes(), values_for_css_boxes
                )
                if checkbox_state
            ]
            return sensor_types_list
        else:
            raise Exception("No css boxes")

    def get_convert_funcs(self):
        return [widget.get_resistance_for_temperature_func() for widget in self.widgets]

    def get_r4_ranges_func(self):
        if self.multirange_state:
            def get():
                return [widget.get_r4() for widget in self.widgets]
        else:
            def get():
                return []
        return get
