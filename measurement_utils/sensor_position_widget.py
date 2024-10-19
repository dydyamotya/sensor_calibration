import logging
from typing import Optional, List, Tuple

import numpy as np
from PySide2 import QtWidgets, QtCore, QtGui
from PySide2.QtWidgets import QFrame
from scipy.interpolate import interp1d
from scipy.stats import linregress

from misc import (
    PlotCalibrationWidget,
    find_index_of_last_non_repeatative_element,
)
from database.models import SensorPosition, fn, Machine

logger = logging.getLogger(__name__)

def find_first_negative(array):
    for idx, i in enumerate(reversed(array)):
        if i <= 0:
            return array.shape[0] - idx

class SensorPositionWidget(QtWidgets.QGroupBox):
    working_state_changed = QtCore.Signal(int)
    def __init__(
        self,
        parent,
        sensor_num,
        machine_name,
        r4_str_values,
        r4_to_float,
        r4_to_int,
        multirange: int,
    ):
        super(SensorPositionWidget, self).__init__(parent)
        self.sensor_positions: Optional[List[Optional[SensorPosition]]] = None
        self.sensor_num = sensor_num
        self.machine_name = machine_name
        self.temperatures_loaded = False
        self.py_parent = parent
        self.resistances_convertors_loaded = False
        self.setTitle(f"Sensor {sensor_num + 1}")
        self.r4_str_values = r4_str_values
        self.r4_to_float = r4_to_float
        self.r4_to_int = r4_to_int
        self.multirange = multirange
        self._init_ui()

    def _get_sensor_positions_from_db(self):
        machine_name = self.machine_name
        sensor_num = self.sensor_num
        try:
            machine_id = (
                Machine.select(Machine.id).where(Machine.name == machine_name).get()
            )
            self.sensor_positions = list(
                SensorPosition.select(SensorPosition, fn.MAX(SensorPosition.datetime))
                .where(
                    (SensorPosition.machine == machine_id)
                    & (SensorPosition.sensor_num == sensor_num + 1)
                )
                .group_by(SensorPosition.r4)
            )
            if len(self.sensor_positions) == 0:
                raise IndexError
        except (IndexError, SensorPosition.DoesNotExist):
            self.sensor_positions = None
            self.resistances_convertors_loaded = False
        else:
            logger.debug(f"Loaded {machine_name} {sensor_num}, {self.sensor_positions}")
            self.resistances_convertors_loaded = True

    def _init_ui(self):
        machine_name = self.machine_name
        self.temperatures_loaded = False
        self._get_sensor_positions_from_db()
        main_layout = QtWidgets.QVBoxLayout(self)
        self.tab_wid = QtWidgets.QTabWidget()

        self.working_sensor = QtWidgets.QCheckBox("Working")
        self.working_sensor.stateChanged.connect(self.change_color)
        self.working_sensor.stateChanged.connect(self.working_state_changed)

        draw_temperature_calibration_button = QtWidgets.QPushButton(QtGui.QIcon("./icons/temperature_calibration.png"), "")
        draw_temperature_calibration_button.clicked.connect(self.draw_temperature_calibration)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.working_sensor)
        buttons_layout.addStretch()
        buttons_layout.addWidget(draw_temperature_calibration_button)
        main_layout.addLayout(buttons_layout)

        main_layout.addWidget(self.tab_wid)
        wid1 = QtWidgets.QWidget()
        wid2 = QtWidgets.QWidget()
        wid3 = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(wid1)
        layout2 = QtWidgets.QFormLayout(wid2)
        layout3 = QtWidgets.QGridLayout(wid3)
        self.tab_wid.addTab(wid2, "Operation")
        self.tab_wid.addTab(wid1, "DB")
        self.tab_wid.addTab(wid3, "Crit. V")
        self.current_values_layout_labels = {
            label: QtWidgets.QLabel()
            for label in ("Us:", "Rn:", "Rs:", "Mode:", "T:", "Un:")
        }

        for label, widget in self.current_values_layout_labels.items():
            widget.setFrameStyle(QFrame.Panel)
            widget.setTextInteractionFlags(
                QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard
            )
            widget.setStyleSheet("background-color:pink")
            layout2.addRow(label, widget)
        self.u_set_lineedit = QtWidgets.QLineEdit()
        layout2.addRow("Set U", self.u_set_lineedit)

        if self.sensor_positions is None or len(self.sensor_positions) == 0:
            layout.addWidget(QtWidgets.QLabel("No data"))
        else:
            if self.multirange:
                r4s = [sensor_position.r4 for sensor_position in self.sensor_positions]
                self.r4_positions = QtWidgets.QComboBox()
                positions_r4s_combobox = self.r4_positions
                if (
                    self.resistances_convertors_loaded
                    and len(self.sensor_positions) == 3
                ):
                    positions_r4s_combobox.setStyleSheet("background-color:palegreen")
                elif (
                    self.resistances_convertors_loaded
                    and len(self.sensor_positions) < 3
                ):
                    positions_r4s_combobox.setStyleSheet(
                        "background-color:palegoldenrod"
                    )
                else:
                    positions_r4s_combobox.setStyleSheet("background-color:pink")
                positions_r4s_combobox.addItems(r4s)
                positions_r4s_combobox.currentTextChanged.connect(
                    self.choose_sensor_range
                )
                layout.addWidget(positions_r4s_combobox)

                buttons_layout = QtWidgets.QHBoxLayout()
                layout.addLayout(buttons_layout, stretch=0)

                sensor_position_layout = QtWidgets.QFormLayout()
                layout.addLayout(sensor_position_layout, stretch=1)
                sensor_position_layout.addRow(
                    "Machine name", QtWidgets.QLabel(f"{machine_name}")
                )
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
            else:
                if len(self.sensor_positions) > 1:
                    logger.warning("More than one sensor position for onerange machine")

                sensor_position = self.sensor_positions[0]
                self.r4_label = QtWidgets.QLabel(sensor_position.r4)
                layout.addWidget(self.r4_label)
                buttons_layout = QtWidgets.QHBoxLayout()
                layout.addLayout(buttons_layout, stretch=0)

                sensor_position_layout = QtWidgets.QFormLayout()
                layout.addLayout(sensor_position_layout, stretch=1)
                sensor_position_layout.addRow(
                    "Machine name", QtWidgets.QLabel(f"{machine_name}")
                )
                self.labels = {
                    label: QtWidgets.QLabel()
                    for label in ("rs_u1", "rs_u2", "datetime")
                }
                for label, label_widget in self.labels.items():
                    sensor_position_layout.addRow(label, label_widget)
                self.choose_sensor_range(self.r4_label.text())

        if self.sensor_positions is not None:
            if self.multirange:
                for idx, mode in enumerate(range(1, 4)):
                    (
                        critical_top_voltage,
                        critical_bottom_voltage,
                    ) = self.get_critical_voltages_for_mode(mode)
                    layout3.addWidget(QtWidgets.QLabel(self.r4_str_values[idx]), idx, 0)
                    layout3.addWidget(
                        QtWidgets.QLabel("{:1.4f}".format(critical_bottom_voltage)), idx, 1
                    )
                    layout3.addWidget(
                        QtWidgets.QLabel("{:1.4f}".format(critical_top_voltage)), idx, 2
                    )

        layout.addStretch()

    def _init_sensor_position(self, sensor_position):
        for (label, label_widget), format_ in zip(
            self.labels.items(),
            (
                lambda x: f"{x:2.4f}",
                lambda x: f"{x:2.4f}",
                lambda x: x.strftime("%Y.%m.%d"),
            ),
        ):
            label_widget.setText(format_(getattr(sensor_position, label)))

    def change_color(self):
        if self.working_sensor.isChecked() and self.temperatures_loaded:
            for widget in self.current_values_layout_labels.values():
                widget.setStyleSheet("background-color:palegreen")
        elif self.working_sensor.isChecked() and not self.temperatures_loaded:
            for widget in self.current_values_layout_labels.values():
                widget.setStyleSheet("background-color:palegoldenrod")
        else:
            for widget in self.current_values_layout_labels.values():
                widget.setStyleSheet("background-color:pink")

    def choose_sensor_range(self, range_):
        sensor_position, *_ = [
            sensor_position
            for sensor_position in self.sensor_positions
            if sensor_position.r4 == range_
        ]
        self._init_sensor_position(sensor_position)

    def load_calibration(self, voltages: np.ndarray, resistances: np.ndarray, temperatures: np.ndarray):
        non_rep_index = find_index_of_last_non_repeatative_element(voltages) + 1

        voltages = voltages[:non_rep_index]
        resistances = resistances[:non_rep_index]
        temperatures = temperatures[:non_rep_index]

        non_neg_diff_index = find_first_negative(np.diff(temperatures))
        if non_neg_diff_index is None:
            non_neg_diff_index = 0
        else:
            non_neg_diff_index += 1

        self.voltages = voltages[non_neg_diff_index:]
        self.resistances = resistances[non_neg_diff_index:]
        self.temperatures = temperatures[non_neg_diff_index:]

        logger.debug(f"{self.temperatures[:5]} .. {self.temperatures[-5:]}")
        logger.debug(f"{self.voltages[:5]} .. {self.voltages[-5:]}")
        logger.debug(f"{self.resistances[:5]} .. {self.resistances[-5:]}")
        
        if len(self.temperatures) > 0:
            try:
                self.func_T_to_U = interp1d(self.temperatures, self.voltages, kind="cubic")
            except ValueError as e:
                logger.debug(
                    f"Calibration T_to_U loading failed for {self.sensor_num} {self.machine_name} sensor"
                )
                logger.debug(str(e))
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
        if self.multirange:
            funcs_dict = {}
            if self.resistances_convertors_loaded and self.working_sensor.isChecked():
                r4s = tuple(
                    sensor_position.r4 for sensor_position in self.sensor_positions
                )
                for r4_str in self.r4_str_values:
                    if r4_str in r4s:
                        sensor_position, *_ = [
                            sensor_position
                            for sensor_position in self.sensor_positions
                            if sensor_position.r4 == r4_str
                        ]
                        rs_u1 = float(sensor_position.rs_u1)
                        rs_u2 = float(sensor_position.rs_u2)
                        r4 = self.r4_to_float[sensor_position.r4]

                        vertical_asimptote = 2.5 + 4.068 * (2.5 - rs_u2)

                        def function_wrapper(rs_u1, rs_u2, r4):
                            def f(u):
                                logger.debug(
                                    f"rs1: {rs_u1}, rs2: {rs_u2}, r4: {r4}, u: {u}"
                                )
                                if u < vertical_asimptote:
                                    return (rs_u1 - rs_u2) * r4 / (
                                        (2.5 + 2.5 * 4.068 - u) / 4.068 - rs_u2
                                    ) - r4
                                else:
                                    return 1e14

                            return f

                        logger.debug(f"R4 is calibrated {r4_str} {r4s} {rs_u1} {rs_u2}")
                        funcs_dict[
                            self.r4_to_int[sensor_position.r4]
                        ] = function_wrapper(rs_u1, rs_u2, r4)
                    else:
                        logger.debug(f"R4 not in set of calibrated {r4_str} {r4s}")
                        funcs_dict[self.r4_to_int[r4_str]] = lambda u: u
            else:
                logger.debug("Not calibrated")
                for r4_str in self.r4_str_values:
                    funcs_dict[self.r4_to_int[r4_str]] = lambda u: u
            return funcs_dict
        else:
            if self.resistances_convertors_loaded and self.working_sensor.isChecked():
                sensor_position = self.sensor_positions[0]
                try:
                    r4 = float(sensor_position.r4)
                except ValueError:
                    logger.warn("R4 is not calibrated")
                    return lambda u: u
                rs_u1 = float(sensor_position.rs_u1)
                rs_u2 = float(sensor_position.rs_u2)

                vertical_asimptote = 2.5 + 4.068 * (2.5 - rs_u2)

                def function_wrapper(rs_u1, rs_u2, r4):
                    def f(u):
                        logger.debug(f"rs1: {rs_u1}, rs2: {rs_u2}, r4: {r4}, u: {u}")
                        if u < vertical_asimptote:
                            return (rs_u1 - rs_u2) * r4 / (
                                (2.5 + 2.5 * 4.068 - u) / 4.068 - rs_u2
                            ) - r4
                        else:
                            return 1e14

                    return f

                return function_wrapper(rs_u1, rs_u2, r4)
            else:
                logger.debug("Not calibrated")
                return lambda u: u

    def set_labels(self, u, r, sr, mode, temperature, un=0):
        if u == sr:
            for value, widget in zip(
                (u, r, sr, mode, temperature, un),
                self.current_values_layout_labels.values(),
            ):
                widget.setText(str(value))
        else:
            for value, widget_key in zip(
                (u, r, sr, mode, temperature, un),
                self.current_values_layout_labels.keys(),
            ):
                if widget_key != "Rs:":
                    self.current_values_layout_labels[widget_key].setText(str(value))
                else:
                    self.current_values_layout_labels[widget_key].setText(
                        f"{value:1.5e}"
                    )

    def get_current_sensor_position_from_database(self):
        r4_str = self.r4_positions.currentText()
        sensor_position, *_ = [
            sensor_position
            for sensor_position in self.sensor_positions
            if sensor_position.r4 == r4_str
        ]
        return sensor_position

    def draw_calibration(self):
        sensor_position: SensorPosition = (
            self.get_current_sensor_position_from_database()
        )
        x = tuple(map(float, sensor_position.x[1:-1].split(",")))
        y = tuple(map(float, sensor_position.y[1:-1].split(",")))
        try:
            PlotCalibrationWidget(
                self).plot_calibration(
                x,
                y,
                sensor_position.rs_u1,
                sensor_position.rs_u2,
                self.r4_to_float[sensor_position.r4],
            )
        except:
            msg_ = QtWidgets.QMessageBox()
            msg_.setText("No data")
            msg_.setWindowTitle("Warning")
            msg_.exec_()

    @staticmethod
    def calculate_critical_value(
        rs11: float, rs12: float, rs21: float, rs22: float, r41: float, r42: float
    ):
        k = 4.068
        alpha1 = k * (rs11 - rs21) * r41
        alpha2 = k * (rs12 - rs22) * r42
        beta1 = 2.5 + k * (2.5 - rs21)
        beta2 = 2.5 + k * (2.5 - rs22)
        delta_r4 = r41 - r42

        b = alpha1 + alpha2 + delta_r4 * (beta2 - beta1 - 5)
        a = delta_r4
        c = (
            alpha1 * beta2
            - alpha2 * beta1
            + delta_r4 * 5 * beta1
            - delta_r4 * beta1 * beta2
            - 5 * alpha1
        )

        D = b * b - 4 * c * a

        return (-b + np.sqrt(D)) / 2 / a

    def get_critical_voltages_for_mode(self, mode: int) -> Tuple[float, float]:
        if self.sensor_positions is not None:
            r4_str = self.r4_str_values[mode - 1]
            try:
                sensor_position, *_ = [
                    sensor_position
                    for sensor_position in self.sensor_positions
                    if sensor_position is not None and (sensor_position.r4 == r4_str)
                ]
            except ValueError:
                return 5.0, 0.0

            rs_u1_1 = float(sensor_position.rs_u1)
            rs_u2_1 = float(sensor_position.rs_u2)
            r4_1 = self.r4_to_float[sensor_position.r4]

            next_mode = mode + 1
            prev_mode = mode - 1

            if next_mode > 3:
                critical_top_voltage = 5.0
            else:
                r4_str = self.r4_str_values[next_mode - 1]
                sensor_position, *_ = [
                    sensor_position
                    for sensor_position in self.sensor_positions
                    if sensor_position is not None and (sensor_position.r4 == r4_str)
                ]

                rs_u1_2 = float(sensor_position.rs_u1)
                rs_u2_2 = float(sensor_position.rs_u2)
                r4_2 = self.r4_to_float[sensor_position.r4]

                critical_top_voltage = (
                    self.calculate_critical_value(
                        rs_u1_1, rs_u1_2, rs_u2_1, rs_u2_2, r4_1, r4_2
                    )
                    + 0.1
                )

            if prev_mode < 1:
                critical_bottom_voltage = 0.0
            else:
                r4_str = self.r4_str_values[prev_mode - 1]
                sensor_position, *_ = [
                    sensor_position
                    for sensor_position in self.sensor_positions
                    if sensor_position is not None and (sensor_position.r4 == r4_str)
                ]

                rs_u1_2 = float(sensor_position.rs_u1)
                rs_u2_2 = float(sensor_position.rs_u2)
                r4_2 = self.r4_to_float[sensor_position.r4]

                critical_bottom_voltage = (
                    5.0
                    - self.calculate_critical_value(
                        rs_u1_2, rs_u1_1, rs_u2_2, rs_u2_1, r4_2, r4_1
                    )
                    - 0.1
                )

            return critical_top_voltage, critical_bottom_voltage
        return 5.0, 0.0
    
    def get_temperature_calibration_extremums(self) -> Tuple[float, float]:
        return min(self.temperatures), max(self.temperatures)

    def isWorking(self) -> bool:
        return self.working_sensor.isChecked()

    def isCalibrated(self) -> bool:
        return self.temperatures_loaded

    def draw_temperature_calibration(self):
        if self.temperatures_loaded:
            PlotCalibrationWidget(self).plot_temperature_calibration(self.voltages, self.temperatures)
        else:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setText("Надо сначала загрузить калибровку. Ну либо для этого сенсора калибровка отсутствует.")
            return msg_box.exec_()
