import logging
import pathlib
from typing import Optional, TYPE_CHECKING, List, Tuple

import numpy as np
from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import QFrame

from misc import (
    clear_layout,
    CssCheckBoxes,
)
from sensor_system import MS_ABC

if TYPE_CHECKING:
    from main_window import MyMainWindow

from measurement_utils.sensor_position_widget import SensorPositionWidget

logger = logging.getLogger(__name__)

values_for_css_boxes = [MS_ABC.SEND_CSS_1_4, MS_ABC.SEND_CSS_5_8, MS_ABC.SEND_CSS_9_12]

class MeasurementWidget(QtWidgets.QWidget):
    def __init__(
        self, parent: "MyMainWindow", global_settings: QtCore.QSettings, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        QtWidgets.QVBoxLayout(self)
        self.settings_widget = parent.settings_widget
        self.global_settings = global_settings
        self.widgets: List[SensorPositionWidget] = []
        self.css_boxes: Optional[CssCheckBoxes] = None
        self.multirange_state = 0
        self.settings_widget.redraw_signal.connect(self.init_ui)
        self.settings_widget.calibration_redraw_signal.connect(self.init_ui)
        self.settings_widget.start_program_signal.connect(self.process_program_signal)
        self.init_ui()

    def init_ui(self):
        self.widgets: List[SensorPositionWidget] = []
        self.css_boxes = None
        clear_layout(self.layout())
        (
            _,
            sensor_number,
            multirange,
            machine_name,
            _,
        ) = self.settings_widget.get_variables()
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

        all_working_button = QtWidgets.QPushButton("Invert working")
        all_working_button.clicked.connect(self.set_all_working)
        buttons_layout.addWidget(all_working_button)

        range_for_all = QtWidgets.QComboBox()
        range_for_all.addItems(["1", "2", "3"])
        buttons_layout.addWidget(range_for_all)
        range_for_all.currentTextChanged.connect(self.change_mode_for_all)

        self.info_label = QtWidgets.QLabel()
        buttons_layout.addWidget(self.info_label)

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
                self,
                i,
                machine_name,
                self.r4_str_values,
                r4_to_float,
                r4_to_int,
                self.multirange_state,
            )
            sensor_position_grid_layout.addWidget(sensor_position_widget, i // 4, i % 4)
            sensor_position_grid_layout.setColumnStretch(i % 4, 1)
            sensor_position_grid_layout.setRowStretch(i // 4, 1)
            sensor_position_widget.working_state_changed.connect(self.working_sensors_subset_changed_callback)
            self.widgets.append(sensor_position_widget)

    def load_calibration(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Calibration File",
            self.global_settings.value("calibration_widget_res_path", "./tests"),
            "Resistances File (*.npz)",
        )
        if filename:
            self.global_settings.setValue(
                "calibration_widget_res_path", pathlib.Path(filename).parent.as_posix()
            )
            npzfile = np.load(filename)
            try:
                voltages, resistances, temperatures = (
                    npzfile["voltages"],
                    npzfile["resistances"],
                    npzfile["temperatures"],
                )
            except KeyError:
                self.load_status_label.setText("Not loaded")
                self.load_status_label.setStyleSheet("background-color:pink")
            else:
                for voltage_row, resistance_row, temperatures_row, widget in zip(
                    voltages, resistances, temperatures, self.widgets
                ):
                    widget.load_calibration(
                        voltage_row, resistance_row, temperatures_row
                    )
                if len(voltages) == len(self.widgets):
                    self.load_status_label.setText("Loaded")
                    self.load_status_label.setStyleSheet("background-color:palegreen")
                else:
                    self.load_status_label.setText("Partially loaded")
                    self.load_status_label.setStyleSheet("background-color:palegoldenrod")



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

    def get_convert_funcs(self, type_):
        if type_ == "R":
            return [
                widget.get_resistance_for_temperature_func() for widget in self.widgets
            ]
        elif type_ == "V":
            return [
                widget.get_voltage_for_temperature_func() for widget in self.widgets
            ]

    def get_voltage_to_resistance_funcs(self):
        return tuple(
            widget.get_voltage_to_resistance_funcs() for widget in self.widgets
        )

    def get_heater_resistance_to_heater_temperature_funcs(self):
        return tuple(
            widget.get_temperature_for_resistance_func() for widget in self.widgets
        )

    def get_multirange_status(self) -> int:
        return self.multirange_state

    def set_results_values_to_widgets(self, us, rs, srs, modes, temperatures, uns=None):
        if uns is None:
            uns = (0,) * 12
        for u, r, sr, mode, temperature, un, widget in zip(
            us, rs, srs, modes, temperatures, uns, self.widgets
        ):
            widget.set_labels(u, r, sr, mode, temperature, un)

    def get_working_widgets(self):
        return [widget.isWorking() for widget in self.widgets]

    def send_us(self):
        if len(self.widgets) == 0:
            raise Exception("No widgets!")

        values = []
        for widget in self.widgets:
            try:
                value = float(widget.u_set_lineedit.text())
            except ValueError:
                values.append(0)
            else:
                values.append(value)

        if self.multirange_state:
            current_states = self.get_r4_resistance_modes()
            logger.debug(f"{values}, {current_states}")
            try:
                ms = self.settings_widget.get_new_ms()
            except:
                mess_box = QtWidgets.QMessageBox()
                mess_box.setText("Port doesn't exist")
                mess_box.exec_()
            else:
                if ms is None:
                    mess_box = QtWidgets.QMessageBox()
                    mess_box.setText("Can't create MS device")
                    mess_box.exec_()
                    return
                ms.send_measurement_range(current_states)
                sensor_types_list = self.get_sensor_types_list()
                us, rs = ms.full_request(
                    values,
                    request_type=MS_ABC.REQUEST_U,
                    sensor_types_list=sensor_types_list,
                )
                for widget, u, r, mode in zip(self.widgets, us, rs, current_states):
                    funcs = widget.get_voltage_to_resistance_funcs()
                    logger.debug(str(funcs))
                    sr = funcs[mode](u)
                    widget.set_labels(u, r, sr, mode, 0)
        else:
            try:
                ms = self.settings_widget.get_new_ms()
            except:
                mess_box = QtWidgets.QMessageBox()
                mess_box.setText("Port doesn't exist")
                mess_box.exec_()
            else:
                if ms is None:
                    mess_box = QtWidgets.QMessageBox()
                    mess_box.setText("Can't create MS device")
                    mess_box.exec_()
                    return
                sensor_types_list = self.get_sensor_types_list()
                us, rs = ms.full_request(
                    values,
                    request_type=MS_ABC.REQUEST_U,
                    sensor_types_list=sensor_types_list,
                )
                for widget, u, r in zip(self.widgets, us, rs):
                    func = widget.get_voltage_to_resistance_funcs()
                    logger.debug(str(func))
                    sr = func(u)
                    widget.set_labels(u, r, sr, 0, 0)

    def get_r4_resistance_modes(self) -> List[int]:
        if self.widgets:
            current_states = []
            if not self.multirange_state:
                return current_states
            for widget in self.widgets:
                try:
                    index = (
                        self.r4_str_values.index(widget.r4_positions.currentText()) + 1
                    )
                except:
                    current_states.append(3)
                else:
                    current_states.append(index)
            logger.debug(str(current_states))
            return current_states
        else:
            raise Exception("No widgets!")

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

    def get_critical_sensors_voltages(self) -> Tuple[dict, dict]:
        critical_top = {}
        critical_bottom = {}
        if self.widgets:
            for mode in range(1, 4):
                critical_top[mode] = list()
                critical_bottom[mode] = list()
                for widget in self.widgets:
                    top_voltage, bottom_voltage = widget.get_critical_voltages_for_mode(
                        mode
                    )
                    critical_top[mode].append(top_voltage)
                    critical_bottom[mode].append(bottom_voltage)
        else:
            for mode in range(1, 4):
                critical_top[mode] = (4,) * 12
                critical_bottom[mode] = (1,) * 12
        return critical_top, critical_bottom

    @QtCore.Slot()
    def working_sensors_subset_changed_callback(self):
        max_of_minimums, min_of_maximums = self.get_working_sensors_temperature_calibration_interval()
        if max_of_minimums is not None and min_of_maximums is not None:
            self.info_label.setText("Калибровка по температуре от {:3.2f} до {:3.2f}".format(max_of_minimums, min_of_maximums))
        else:
            self.info_label.setText("Не выбран ни один сенсор как рабочий или ни один не калиброван")

    def get_working_sensors_temperature_calibration_interval(self) -> Tuple[Optional[float], Optional[float]]:
        if self.widgets:
            min_temperatures = []
            max_temperatures = []
            for sensor_position_widget in self.widgets:
                if sensor_position_widget.isWorking() and sensor_position_widget.isCalibrated():
                    min_temperature, max_temperature = sensor_position_widget.get_temperature_calibration_extremums()
                    min_temperatures.append(min_temperature)
                    max_temperatures.append(max_temperature)
            if len(min_temperatures) > 0:
                return max(min_temperatures), min(max_temperatures)
            else:
                return None, None
        else:
            return None, None


