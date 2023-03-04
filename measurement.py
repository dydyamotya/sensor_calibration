from typing import Collection, Optional

from PySide2.QtWidgets import QFrame
from yaml import load, dump
from collections import UserDict
import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
from scipy.stats import linregress
from sensor_system import MS_ABC

from PySide2 import QtWidgets, QtCore, QtGui
import logging
from models import SensorPosition, fn, Machine
from misc import clear_layout, CssCheckBoxes, PlotCalibrationWidget
import pathlib

logger = logging.getLogger(__name__)

values_for_css_boxes = [
    MS_ABC.SEND_CSS_1_4, MS_ABC.SEND_CSS_5_8, MS_ABC.SEND_CSS_9_12
]


class SensorPositionWidget(QtWidgets.QGroupBox):

    def __init__(self, parent, sensor_num, machine_name, r4_str_values, r4_to_float, r4_to_int):
        super(SensorPositionWidget, self).__init__(parent)
        self.sensor_positions: Optional[Collection[Optional[SensorPosition]]] = None
        self.sensor_num = sensor_num
        self.machine_name = machine_name
        self.temperatures_loaded = False
        self.py_parent = parent
        self.resistances_convertors_loaded = False
        self.setTitle(f"Sensor {sensor_num + 1}")
        self.r4_str_values = r4_str_values
        self.r4_to_float = r4_to_float
        self.r4_to_int = r4_to_int
        self._init_ui()

    def _get_sensor_positions_from_db(self):
        machine_name = self.machine_name
        sensor_num = self.sensor_num
        try:
            machine_id = Machine.select(
                Machine.id).where(Machine.name == machine_name).get()
            self.sensor_positions = list(
                SensorPosition.select(SensorPosition, fn.MAX(
                    SensorPosition.id)).where(
                    (SensorPosition.machine == machine_id)
                    & (SensorPosition.sensor_num == sensor_num +
                       1)).group_by(SensorPosition.r4))
        except (IndexError, SensorPosition.DoesNotExist):
            self.sensor_positions = None
            self.resistances_convertors_loaded = False
        else:
            logger.debug(
                f"Loaded {machine_name} {sensor_num}, {self.sensor_positions}")
            self.resistances_convertors_loaded = True

    def _init_ui(self):
        machine_name = self.machine_name
        self._get_sensor_positions_from_db()
        main_layout = QtWidgets.QVBoxLayout(self)
        self.tab_wid = QtWidgets.QTabWidget()
        self.working_sensor = QtWidgets.QCheckBox("Working")
        self.working_sensor.stateChanged.connect(self.change_color)
        main_layout.addWidget(self.working_sensor)
        main_layout.addWidget(self.tab_wid)
        wid1 = QtWidgets.QWidget()
        wid2 = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(wid1)
        layout2 = QtWidgets.QFormLayout(wid2)
        self.tab_wid.addTab(wid2, "Operation")
        self.tab_wid.addTab(wid1, "DB")
        self.current_values_layout_labels = {label: QtWidgets.QLabel() for label in
                                             ("Us:", "Rn:", "Rs:", "Mode:", "T:", "Un:")}

        for label, widget in self.current_values_layout_labels.items():
            widget.setFrameStyle(QFrame.Panel)
            widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
            widget.setStyleSheet("background-color:pink")
            layout2.addRow(label, widget)
        self.u_set_lineedit = QtWidgets.QLineEdit()
        layout2.addRow("Set U", self.u_set_lineedit)

        if self.sensor_positions is None or len(self.sensor_positions) == 0:
            layout.addWidget(QtWidgets.QLabel("No data"))
        else:
            r4s = [
                sensor_position.r4 for sensor_position in self.sensor_positions
            ]
            self.r4_positions = QtWidgets.QComboBox()
            positions_r4s_combobox = self.r4_positions
            if self.resistances_convertors_loaded and len(self.sensor_positions) == 3:
                positions_r4s_combobox.setStyleSheet("background-color:palegreen")
            elif self.resistances_convertors_loaded and len(self.sensor_positions) < 3:
                positions_r4s_combobox.setStyleSheet("background-color:palegoldenrod")
            else:
                positions_r4s_combobox.setStyleSheet("background-color:pink")
            positions_r4s_combobox.addItems(r4s)
            positions_r4s_combobox.currentTextChanged.connect(
                self.choose_sensor_range)
            layout.addWidget(positions_r4s_combobox)

            buttons_layout = QtWidgets.QHBoxLayout()
            layout.addLayout(buttons_layout, stretch=0)

            sensor_position_layout = QtWidgets.QFormLayout()
            layout.addLayout(sensor_position_layout, stretch=1)
            sensor_position_layout.addRow("Machine name",
                                          QtWidgets.QLabel(f"{machine_name}"))
            self.labels = {
                label: QtWidgets.QLabel()
                for label in ("rs_u1", "rs_u2", "datetime")
            }
            for label, label_widget in self.labels.items():
                sensor_position_layout.addRow(label, label_widget)

            self.choose_sensor_range(positions_r4s_combobox.currentText())

            button_calibration_draw = QtWidgets.QPushButton("Draw calibration")
            button_calibration_draw.clicked.connect(self.draw_calibration)
            layout.addWidget(button_calibration_draw)
        layout.addStretch()

    def _init_sensor_position(self, sensor_position):
        for (label, label_widget), format_ in zip(self.labels.items(), (
                lambda x: f"{x:2.4f}", lambda x: f"{x:2.4f}", lambda x: x.strftime("%Y.%m.%d"))):
            label_widget.setText(format_(getattr(sensor_position, label)))

    def change_color(self):
        if self.working_sensor.isChecked() and self.temperatures_loaded:
            for label, widget in self.current_values_layout_labels.items():
                widget.setStyleSheet("background-color:palegreen")
        elif self.working_sensor.isChecked() and not self.temperatures_loaded:
            for label, widget in self.current_values_layout_labels.items():
                widget.setStyleSheet("background-color:palegoldenrod")
        else:
            for label, widget in self.current_values_layout_labels.items():
                widget.setStyleSheet("background-color:pink")

    def choose_sensor_range(self, range_):
        sensor_position, *_ = [
            sensor_position for sensor_position in self.sensor_positions
            if sensor_position.r4 == range_
        ]
        self._init_sensor_position(sensor_position)

    def load_calibration(self, voltages, resistances, temperatures):
        self.voltages = voltages
        self.resistances = resistances
        self.temperatures = temperatures

        logger.debug(f"{self.temperatures[:5]} .. {self.temperatures[-5:]}")
        logger.debug(f"{self.voltages[:5]} .. {self.voltages[-5:]}")
        logger.debug(f"{self.resistances[:5]} .. {self.resistances[-5:]}")
        try:
            self.func_T_to_U = interp1d(self.temperatures,
                                        self.voltages,
                                        kind="cubic")
        except ValueError:
            logger.debug(
                f"Calibration T_to_U loading failed for {self.sensor_num} {self.machine_name} sensor"
            )
            # logger.debug(f"Voltages: {self.voltages}")
            # logger.debug(f"Temperatures: {self.temperatures}")
            self.func_T_to_U = lambda x: 0
        else:
            logger.debug(
                f"Calibration T_to_U successful for {self.sensor_num} {self.machine_name} sensor"
            )
        try:
            res = linregress(self.temperatures, self.resistances)
        except ValueError:
            logger.debug(
                f"Calibration T_to_R loading failed for {self.sensor_num} {self.machine_name} sensor"
            )
            self.func_T_to_R = lambda x: 0
        else:
            self.func_T_to_R = lambda x: res.intercept + res.slope * x
            logger.debug(
                f"Calibration T_to_R successful for {self.sensor_num} {self.machine_name} sensor"
            )

        self.temperatures_loaded = True
        self.change_color()

    def get_resistance_for_temperature(self, temperature: float):
        if not self.temperatures_loaded:
            return None
        self.func_T_to_R(temperature)

    def get_voltage_for_temperature(self, temperature: float):
        if not self.temperatures_loaded:
            return None
        self.func_T_to_U(temperature)

    def get_resistance_for_temperature_func(self):
        if not (self.temperatures_loaded and self.working_sensor.isChecked()):
            return lambda x: 0
        return self.func_T_to_R

    def get_voltage_for_temperature_func(self):
        if not (self.temperatures_loaded and self.working_sensor.isChecked()):
            return lambda x: 0
        return self.func_T_to_U

    def get_voltage_to_resistance_funcs(self):
        funcs_dict = {}
        if (self.resistances_convertors_loaded and self.working_sensor.isChecked()):
            r4s = tuple(sensor_position.r4 for sensor_position in self.sensor_positions)
            for r4_str in self.r4_str_values:
                if r4_str in r4s:
                    sensor_position, *_ = [
                        sensor_position for sensor_position in self.sensor_positions
                        if sensor_position.r4 == r4_str
                    ]
                    rs_u1 = float(sensor_position.rs_u1)
                    rs_u2 = float(sensor_position.rs_u2)
                    r4 = self.r4_to_float[sensor_position.r4]

                    vertical_asimptote = 2.5 + 4.068 * (2.5 - rs_u2)

                    def function_wrapper(rs_u1, rs_u2, r4):
                        def f(u):
                            logger.debug(f"rs1: {rs_u1}, rs2: {rs_u2}, r4: {r4}, u: {u}")
                            if u < vertical_asimptote:
                                return (rs_u1 - rs_u2) * r4 / ((2.5 + 2.5 * 4.068 - u) / 4.068 - rs_u2) - r4
                            else:
                                return 1e14

                        return f

                    logger.debug(f"R4 is calibrated {r4_str} {r4s} {rs_u1} {rs_u2}")
                    funcs_dict[self.r4_to_int[sensor_position.r4]] = function_wrapper(rs_u1, rs_u2, r4)
                else:
                    logger.debug(f"R4 not in set of calibrated {r4_str} {r4s}")
                    funcs_dict[self.r4_to_int[r4_str]] = lambda u: u
        else:
            logger.debug("Not calibrated")
            for r4_str in self.r4_str_values:
                funcs_dict[self.r4_to_int[r4_str]] = lambda u: u
        return funcs_dict

    def set_labels(self, u, r, sr, mode, temperature, un=0):
        if u == sr:
            for value, widget in zip((u, r, sr, mode, temperature, un), self.current_values_layout_labels.values()):
                widget.setText(str(value))
        else:
            for value, widget_key in zip((u, r, sr, mode, temperature, un), self.current_values_layout_labels.keys()):
                if widget_key != "Rs:":
                    self.current_values_layout_labels[widget_key].setText(str(value))
                else:
                    self.current_values_layout_labels[widget_key].setText(f"{value:1.5e}")

    def get_current_sensor_position_from_database(self):

        r4_str = self.r4_positions.currentText()
        sensor_position, *_ = [
            sensor_position for sensor_position in self.sensor_positions
            if sensor_position.r4 == r4_str
        ]
        return sensor_position

    def draw_calibration(self):
        sensor_position: SensorPosition = self.get_current_sensor_position_from_database()
        x = tuple(map(float, sensor_position.x[1:-1].split(",")))
        y = tuple(map(float, sensor_position.y[1:-1].split(",")))
        try:
            PlotCalibrationWidget(self,
                                  x,
                                  y,
                                  sensor_position.rs_u1,
                                  sensor_position.rs_u2,
                                  self.r4_to_float[sensor_position.r4])
        except:
            msg_ = QtWidgets.QMessageBox()
            msg_.setText("No data")
            msg_.setWindowTitle("Warning")
            msg_.exec_()

    def get_critical_voltages(self):
        for sensor_position in self.sensor_positions:
            sensor_position.rs_u2



class MeasurementWidget(QtWidgets.QWidget):

    def __init__(self, parent, level, global_settings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QVBoxLayout(self)
        self.settings_widget = parent.settings_widget
        self.widgets = []
        self.css_boxes: Optional[CssCheckBoxes] = None
        self.multirange_state = False
        self.settings_widget.redraw_signal.connect(self.init_ui)
        self.settings_widget.calibration_redraw_signal.connect(self.init_ui)
        self.settings_widget.start_program_signal.connect(self.process_program_signal)
        self.init_ui()

    def init_ui(self):
        self.widgets = []
        self.css_boxes = None
        clear_layout(self.layout())
        comport, sensor_number, multirange, machine_name, machine_id = self.settings_widget.get_variables(
        )
        self.r4_str_values, r4_to_float, r4_to_int = self.settings_widget.get_r4_data()
        self.multirange_state = multirange

        buttons_layout = QtWidgets.QHBoxLayout()
        self.layout().addLayout(buttons_layout)

        load_calibration_button = QtWidgets.QPushButton("Load calibration")
        load_calibration_button.clicked.connect(self.load_calibration)

        self.load_status_label = QtWidgets.QLabel("Not loaded")
        self.load_status_label.setFrameStyle(QFrame.Panel)
        self.load_status_label.setStyleSheet("background-color:pink")
        buttons_layout.addWidget(load_calibration_button)
        buttons_layout.addWidget(self.load_status_label)

        self.send_u_button = QtWidgets.QPushButton("Send U to sensors")
        self.send_u_button.clicked.connect(self.send_us)
        buttons_layout.addWidget(self.send_u_button)

        all_working_button = QtWidgets.QPushButton("All working")
        all_working_button.clicked.connect(self.set_all_working)
        buttons_layout.addWidget(all_working_button)

        range_for_all = QtWidgets.QComboBox()
        range_for_all.addItems(["1", "2", "3"])
        buttons_layout.addWidget(range_for_all)
        range_for_all.currentTextChanged.connect(self.change_mode_for_all)

        buttons_layout.addStretch()

        self.css_boxes = CssCheckBoxes()
        self.layout().addWidget(self.css_boxes)

        scroll_sensor_positions_widget = QtWidgets.QScrollArea()
        scroll_sensor_positions_widget.setWidgetResizable(True)
        scroll_area_under_widget = QtWidgets.QWidget()
        sensor_position_grid_layout = QtWidgets.QGridLayout(scroll_area_under_widget)
        scroll_sensor_positions_widget.setWidget(scroll_area_under_widget)
        self.layout().addWidget(scroll_sensor_positions_widget)
        # self.layout().addStretch()
        for i in range(sensor_number):
            sensor_position_widget = SensorPositionWidget(
                self, i, machine_name, self.r4_str_values, r4_to_float, r4_to_int)
            sensor_position_grid_layout.addWidget(sensor_position_widget,
                                                  i // 4, i % 4)
            sensor_position_grid_layout.setColumnStretch(i % 4, 1)
            sensor_position_grid_layout.setRowStretch(i // 4, 1)
            self.widgets.append(sensor_position_widget)

    def load_calibration(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Calibration File",
            self.global_settings.value("calibration_widget_res_path", "./tests"),
            "Resistances File (*.npz)")
        if filename:
            self.global_settings.setValue("calibration_widget_res_path", pathlib.Path(filename).parent.as_posix())
            npzfile = np.load(filename)
            try:
                voltages, resistances, temperatures = npzfile[
                    "voltages"], npzfile["resistances"], npzfile[
                    "temperatures"]
            except KeyError:
                self.load_status_label.setText("Not loaded")
                self.load_status_label.setStyleSheet("background-color:pink")
            else:
                for voltage_row, resistance_row, temperatures_row, widget in zip(
                        voltages, resistances, temperatures, self.widgets):
                    widget.load_calibration(voltage_row, resistance_row,
                                            temperatures_row)
                self.load_status_label.setText("Loaded")
                self.load_status_label.setStyleSheet("background-color:palegreen")

    def get_sensor_types_list(self):
        if self.css_boxes:
            sensor_types_list = [
                send_code for checkbox_state, send_code in zip(
                    self.css_boxes.collect_checkboxes(), values_for_css_boxes)
                if checkbox_state
            ]
            return sensor_types_list
        else:
            raise Exception("No css boxes")

    def get_convert_funcs(self, type_):
        if type_ == "R":
            return [
                widget.get_resistance_for_temperature_func()
                for widget in self.widgets
            ]
        elif type_ == "V":
            return [
                widget.get_voltage_for_temperature_func()
                for widget in self.widgets
            ]

    def get_voltage_to_resistance_funcs(self):
        return tuple(widget.get_voltage_to_resistance_funcs() for widget in self.widgets)

    def set_results_values_to_widgets(self, us, rs, srs, modes, temperatures, uns=None):
        if uns is None:
            uns = (0,) * 12
        for u, r, sr, mode, temperature, un, widget in zip(us, rs, srs, modes, temperatures, uns, self.widgets):
            widget.set_labels(u, r, sr, mode, temperature, un)

    def get_working_widgets(self):
        return [widget.working_sensor.isChecked() for widget in self.widgets]

    def send_us(self):
        values = []
        for widget in self.widgets:
            try:
                value = float(widget.u_set_lineedit.text())
            except ValueError:
                values.append(0)
            else:
                values.append(value)

        current_states = self.get_r4_resistance_modes()
        logger.debug(f"{values}, {current_states}")
        try:
            ms = self.settings_widget.get_new_ms()
        except:
            mess_box = QtWidgets.QMessageBox()
            mess_box.setText("Port doesn't exist")
            mess_box.exec_()
        else:
            ms.send_measurement_range(current_states)
            sensor_types_list = self.get_sensor_types_list()
            us, rs = ms.full_request(values, request_type=MS_ABC.REQUEST_U,
                                     sensor_types_list=sensor_types_list)
            for widget, u, r, mode in zip(self.widgets, us, rs, current_states):
                funcs = widget.get_voltage_to_resistance_funcs()
                logger.debug(str(funcs))
                sr = funcs[mode](u)
                widget.set_labels(u, r, sr, mode, 0)

    def get_r4_resistance_modes(self):
        current_states = []
        for widget in self.widgets:
            try:
                index = self.r4_str_values.index(widget.r4_positions.currentText()) + 1
            except:
                current_states.append(3)
            else:
                current_states.append(index)
        logger.debug(str(current_states))
        return current_states

    def set_all_working(self):
        for widget in self.widgets:
            widget.working_sensor.nextCheckState()

    def change_mode_for_all(self, text):
        exception_catched = 0
        for widget in self.widgets:
            try:
                widget.r4_positions.setCurrentText(self.r4_str_values[int(text) - 1])
            except:
                exception_catched += 1

        if exception_catched > 0:
            msg_ = QtWidgets.QMessageBox()
            msg_.setText("Not all sensors have such a mode")
            msg_.exec_()

    def process_program_signal(self, started_flag):
        if started_flag:
            self.css_boxes.disable_all_checkboxes()
            self.send_u_button.setEnabled(False)
        else:
            self.css_boxes.enable_all_checkboxes()
            self.send_u_button.setEnabled(True)
