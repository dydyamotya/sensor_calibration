from threading import Thread
from PySide2 import QtWidgets
from PySide2.QtGui import QPixmap, QColor
from PySide2.QtCore import Slot, Qt
from sensor_system import MS_Uni, MS_ABC
from misc import TypeCheckLineEdit
import time
import configparser

from matplotlib import figure
from matplotlib.lines import Line2D
from matplotlib.colors import get_named_colors_mapping
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
import numpy as np
import numpy.ma as ma

import logging
logger = logging.getLogger(__name__)

colors_for_lines = (
    "tab:blue",
    'tab:orange',
    'tab:green',
    'tab:red',
    'tab:purple',
    "tab:brown",
    "tab:pink",
    "tab:gray",
    "tab:olive",
    "tab:cyan",
    "black",
    "lime"
)

values_for_css_boxes = [MS_ABC.SEND_CSS_1_4,
                        MS_ABC.SEND_CSS_5_8,
                        MS_ABC.SEND_CSS_9_12]


class CalibrationProxyFrame(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_py = parent
        self.widget_singleton = None
        layout = QtWidgets.QVBoxLayout(self)

        self.calibration_button = QtWidgets.QPushButton(
            "Show calibration widget")
        layout.addWidget(self.calibration_button)
        self.calibration_button.clicked.connect(self.form_widget)

    def form_widget(self):
        if self.widget_singleton is None:
            self.widget_singleton = CalibrationWidget(
                self.parent_py, self.parent_py.settings_widget.get_variables())
        self.widget_singleton.show()


class CalibrationWidget(QtWidgets.QWidget):
    def __init__(self, parent, settings):
        super().__init__()
        self.setWindowTitle("Calibration")
        self.parent_py = parent

        self.stopped = True
        self.ms = None
        self.thread = None
        self.last_idx = -1

        self.comport, self.sensor_number, _ = settings
        layout = QtWidgets.QHBoxLayout(self)

        left_layout = QtWidgets.QVBoxLayout()

        self.calibration_settings = CalibrationSettings(self)
        self.cal_plot_widget = CalibrationPlotWidget(self)
        self.cal_buttons = CalibrationButtons(self)
        self.per_sensor = PerSensorSettings(self)
        self.per_sensor.connect_return_pressed(self.recalc_signal_handler)
        self.r0_voltage = TypeCheckLineEdit(self, float, 0.3)
        self.save_buttons = SaveButtons(self)
        self.css_checkboxes = CssCheckBoxes(self)

        layout.addLayout(left_layout)

        settings_layout_hbox = QtWidgets.QHBoxLayout()
        settings_layout_hbox.addWidget(self.calibration_settings)

        buttons_layout_vbox = QtWidgets.QVBoxLayout()
        buttons_layout_vbox.addWidget(QtWidgets.QLabel("R0 Voltage"))
        buttons_layout_vbox.addWidget(self.r0_voltage)
        buttons_layout_vbox.addWidget(self.cal_buttons)
        buttons_layout_vbox.addWidget(self.css_checkboxes)

        settings_layout_hbox.addLayout(buttons_layout_vbox)

        left_layout.addLayout(settings_layout_hbox)

        left_layout.addWidget(self.per_sensor)
        left_layout.addWidget(self.save_buttons)

        layout.addWidget(self.cal_plot_widget)

        self.voltages = None
        self.resistances = None

    @Slot()
    def start_ms(self):
        self.stopped = False
        self.thread = Thread(target=self.loop_ms)
        self.thread.start()

    @Slot()
    def stop_ms(self):
        self.stopped = True
        if self.thread:
            self.thread.join()
            self.full_request_until_result((0, ) * self.sensor_number)
        if self.ms:
            self.ms.close()
        self.ms = None

    def get_average_massive(self, voltage: float, steps_per_measurement: int, sleep_time: float):
        voltages = (voltage, ) * self.sensor_number
        averaging_massive = np.zeros(
            (self.sensor_number, steps_per_measurement))
        try:
            us, rs = self.full_request_until_result(voltages)

            time.sleep(sleep_time)

            for i in range(steps_per_measurement):
                time.sleep(0.2)
                us, rs = self.full_request_until_result(voltages)
                averaging_massive[:, i] = rs

        except MS_ABC.MSException:
            raise
        else:
            return averaging_massive

    @staticmethod
    def calculate_masked_mean(array):
        masked_values = ma.masked_values(array, 655.35)
        return masked_values.mean(axis=1).filled(655.35)

    @Slot()
    def get_r0(self):
        try:
            self.ms = MS_Uni(self.sensor_number, self.comport)
            r0_voltage = self.r0_voltage.get_value()
            steps_per_measurement = 10
            averaging_massive = self.get_average_massive(r0_voltage,
                                                         steps_per_measurement,
                                                         2.0)

            self.per_sensor.set_r0s(
                self.calculate_masked_mean(averaging_massive))
        except MS_ABC.MSException:
            raise
        finally:
            self.ms.close()
            self.ms = None

    def loop_ms(self):
        if self.ms:
            return

        self.ms = MS_Uni(self.sensor_number, self.comport)

        initial_voltage, steps_per_measurement, end_voltage, sleep_time, dots_to_draw, microstep = self.calibration_settings.get_variables()

        all_steps = int((end_voltage - initial_voltage) / microstep) + 1

        self.resistances = np.zeros((self.sensor_number, all_steps))

        voltage_row = np.linspace(
            initial_voltage, end_voltage + microstep, num=all_steps)

        self.voltages = np.vstack(
            [voltage_row for i in range(self.sensor_number)])

        logger.debug(voltage_row)
        for idx, voltage_dot in enumerate(voltage_row):
            if self.stopped:
                self.last_idx = idx
                return
            logger.debug(f"{idx} {voltage_dot}")
            try:

                averaging_massive = self.get_average_massive(
                    voltage_dot, steps_per_measurement, sleep_time)

                self.resistances[:, idx] = self.calculate_masked_mean(
                    averaging_massive)

                if idx % dots_to_draw == 0:
                    self.cal_plot_widget.set_lines(
                        self.voltages[:, :idx], self.per_sensor.process_resistances(self.resistances[:, :idx]))
            except MS_ABC.MSException:
                self.last_idx = idx
                self.stopped = True
                self.ms.close()
                self.ms = None
                return
        self.full_request_until_result((0, ) * self.sensor_number)
        self.stopped = True
        self.last_idx = -1
        self.ms.close()
        self.ms = None

    def full_request_until_result(self, values):
        sensor_types_list = [send_code for checkbox_state, send_code in zip(
            self.css_checkboxes.collect_checkboxes(), values_for_css_boxes) if checkbox_state]

        logger.debug(f"{sensor_types_list}")
        for i in range(20):
            try:
                us, rs = self.ms.full_request(values, sensor_types_list)
            except MS_ABC.MSException:
                logger.debug(f"Full request try: {i}")
            else:
                return us, rs
        else:
            raise MS_ABC.MSException("Failed to obtain result somehow")

    def recalc_signal_handler(self):
        if self.stopped:
            logger.debug("Recalc signal handler")
            if any(self.resistances.flatten() > 0):
                voltages, _, temperatures = self.get_data()
                self.cal_plot_widget.set_lines(voltages, temperatures)

    def get_data(self):
        try:
            voltages = self.voltages[:, :self.last_idx]
            temperatures = self.per_sensor.process_resistances(
                self.resistances[:, :self.last_idx])
            resistances = self.resistances[:, :self.last_idx]
        except TypeError:
            voltages, temperatures, resistances = np.array(
                []), np.array([]), np.array([])
        finally:
            return voltages, resistances, temperatures

    def load_data(self, voltages, resistances):
        self.last_idx = -1
        self.voltages = voltages
        self.resistances = resistances

    def get_params(self):
        r0s, rns, alphas = [], [], []
        initial_voltage, steps_per_measurement, end_voltage, sleep_time, dots_to_draw, microstep = self.calibration_settings.get_variables()
        vmax = self.get_data()[0][0][-1]
        for r0, rn, alpha in self.per_sensor.get_variables():
            r0s.append(r0)
            rns.append(rn)
            alphas.append(alpha)
        return r0s, rns, alphas, self.per_sensor.T0_entry.get_value(), vmax

    def load_params(self, config: configparser.ConfigParser):
        self.per_sensor.T0_entry.set_value(config["T0"]["T0"])
        self.per_sensor.set_variables(config)


class PerSensorSettings(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        sensor_number = parent.sensor_number

        self.sensor_widgets = tuple(OneSensorWidget(self, i)
                                    for i in range(sensor_number))

        self.T0_entry = TypeCheckLineEdit(self, float, 40.0)
        layout.addWidget(QtWidgets.QLabel("T0"))
        layout.addWidget(self.T0_entry)

        column_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(column_layout)

        for name_col in ["R0", "Rn", "alpha"]:
            label = QtWidgets.QLabel(name_col, self)
            label.setAlignment(Qt.AlignCenter)
            column_layout.addWidget(label)

        for sensor_widget in self.sensor_widgets:
            layout.addWidget(sensor_widget)

    def get_variables(self):
        for sensor_widget in self.sensor_widgets:
            yield sensor_widget.get_variables()

    def set_variables(self, config: configparser.ConfigParser):
        for idx, sensor_widget in enumerate(self.sensor_widgets):
            sensor_widget.r0.set_value(
                float(config["R0"][f"R0_{idx:d}"].replace(",", ".")) / 100)
            sensor_widget.rn.set_value(
                float(config["Rc"][f"Rc_{idx:d}"].replace(",", ".")) / 100)
            sensor_widget.alpha.set_value(
                float(config["a"][f"a0_{idx:d}"].replace(",", ".")))

    def process_resistances(self, resistances: np.ndarray) -> np.ndarray:
        T0 = self.T0_entry.get_value()
        temperatures = []
        for resistance_row, (r0, rn, alpha) in zip(resistances, self.get_variables()):
            temperatures.append(
                ((resistance_row - rn)/(r0 - rn) - 1)/alpha + T0)

        return np.vstack(temperatures)

    def set_r0s(self, resistances):
        for sensor_widget, resistance in zip(self.sensor_widgets, resistances):
            sensor_widget.set_r0(resistance)

    def connect_return_pressed(self, signal):
        for widget in self.sensor_widgets:
            widget.return_pressed_connect(signal)


class OneSensorWidget(QtWidgets.QWidget):

    def __init__(self, parent, number):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)

        self.number = number

        self.r0 = TypeCheckLineEdit(self, float, 16.0)
        self.rn = TypeCheckLineEdit(self, float, 1.0)
        self.alpha = TypeCheckLineEdit(self, float, 0.003)

        layout.addWidget(QtWidgets.QLabel(str(number), self))
        layout.addWidget(self.r0)
        layout.addWidget(self.rn)
        layout.addWidget(self.alpha)

        pixmap = QPixmap(20, 20)
        color = QColor(get_named_colors_mapping()[colors_for_lines[number]])
        pixmap.fill(color)
        pixmap_label = QtWidgets.QLabel(self)
        pixmap_label.setPixmap(pixmap)

        layout.addWidget(pixmap_label)

    def get_variables(self):
        return (self.r0.get_value(), self.rn.get_value(), self.alpha.get_value())

    def set_r0(self, value):
        logger.debug(f"{value}")
        self.r0.set_value(value)

    def return_pressed_connect(self, signal):
        self.r0.returnPressed.connect(signal)
        self.rn.returnPressed.connect(signal)
        self.alpha.returnPressed.connect(signal)


class CalibrationButtons(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout(self)

        self.start_button = QtWidgets.QPushButton("Start", self)
        self.stop_button = QtWidgets.QPushButton("Stop", self)
        self.get_r0_button = QtWidgets.QPushButton("Get R0", self)

        self.buttons = [self.start_button,
                        self.stop_button, self.get_r0_button]

        self.start_button.clicked.connect(parent.start_ms)
        self.stop_button.clicked.connect(parent.stop_ms)
        self.get_r0_button.clicked.connect(parent.get_r0)

        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.get_r0_button)

    def turn_disable(self):
        for button in self.buttons:
            button.setDisabled(True)

    def turn_enable(self):
        for button in self.buttons:
            button.setEnabled(True)


class CalibrationSettings(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        layout = QtWidgets.QFormLayout(self)

        self.widgets_names = [
            "Initial voltage",
            "Steps",
            "End voltage",
            "Time sleep",
            "Dots to draw",
            "Microstep"
        ]

        self.widget_types = [float, int, float, float, int, float]
        self.widget_defaults = [0.1, 10, 5.1, 2.0, 1, 0.01]
        self.entries = [TypeCheckLineEdit(self, type_, default_value) for widget_name, type_, default_value in zip(
            self.widgets_names, self.widget_types, self.widget_defaults)]
        for widget_name, entry in zip(self.widgets_names, self.entries):
            layout.addRow(widget_name,  entry)

    def get_variables(self):
        for entry in self.entries:
            yield entry.get_value()


class CalibrationPlotWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        fig = figure.Figure()
        ax = fig.add_subplot(1, 1, 1)
        self.canvas = FigureCanvasQTAgg(figure=fig)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.canvas)
        toolbox = NavigationToolbar2QT(self.canvas, self)
        layout.addWidget(toolbox)

        ax.set_xlabel("Voltage, V")
        ax.set_ylabel("Temperature, C")

        self.lines_dict = {i: Line2D([], [], color=color)
                           for i, color in enumerate(colors_for_lines)}

        for line in self.lines_dict.values():
            ax.add_line(line)

        ax.set_ylim(-20, 520)
        ax.set_xlim(-0.2, 5.2)

    def set_lines(self, voltages, temperatures):
        for line, voltage_row, temperature_row in zip(self.lines_dict.values(), voltages, temperatures):
            line.set_xdata(voltage_row)
            line.set_ydata(temperature_row)
        self.canvas.draw()


class SaveButtons(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent_py: CalibrationWidget = parent

        layout = QtWidgets.QHBoxLayout(self)

        self.save_calibration_button = QtWidgets.QPushButton(
            "Save calibration", self)
        self.save_parameters_button = QtWidgets.QPushButton(
            "Save parameters", self)
        self.load_parameters_button = QtWidgets.QPushButton(
            "Load parameters", self)
        self.save_resistances_button = QtWidgets.QPushButton(
            "Save resistances", self)
        self.load_resistances_button = QtWidgets.QPushButton(
            "Load resistances", self)

        self.save_calibration_button.clicked.connect(self.save_calibration)
        self.save_parameters_button.clicked.connect(self.save_parameters)
        self.load_parameters_button.clicked.connect(self.load_parameters)
        self.save_resistances_button.clicked.connect(self.save_resistances)
        self.load_resistances_button.clicked.connect(self.load_resistances)

        layout.addWidget(self.save_calibration_button)
        layout.addWidget(self.save_parameters_button)
        layout.addWidget(self.load_parameters_button)
        layout.addWidget(self.save_resistances_button)
        layout.addWidget(self.load_resistances_button)

    def save_calibration(self):
        filename, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Calibration", "./tests", "Calibration File (*.cal)")
        if filename:
            voltages, _, temperatures = self.parent_py.get_data()
            items = voltages.shape[1]
            with open(filename, "w") as fd:
                fd.write(f"Items {items:d}\n")
                new_array = []
                for voltage, temperature in zip(voltages, temperatures):
                    new_array.append(voltage)
                    new_array.append(temperature)

                new_array = np.array(new_array).T
                np.savetxt(fd, new_array, fmt='%.6f',
                           delimiter="\t", newline="\t\n")

    def save_parameters(self):
        filename, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Parameters", "./tests", "Parameters File (*.par)")
        if not filename:
            return

        config = configparser.ConfigParser()
        r0s, rns, alphas, t0, Vmax = self.parent_py.get_params()

        config["R0"] = {f"R0_{idx:d}": "{:f}".format(
            r0*100).replace(".", ",") for idx, r0 in enumerate(r0s)}
        config["Rc"] = {f"Rc_{idx:d}": "{:f}".format(
            rn*100).replace(".", ",") for idx, rn in enumerate(rns)}
        config["a"] = {f"a0_{idx:d}": "{:f}".format(rn).replace(
            ".", ",") for idx, rn in enumerate(alphas)}
        config["T0"] = dict(T0="{:f}".format(t0).replace(".", ","))
        config["Vmax"] = dict(Vmax="{:f}".format(Vmax).replace(".", ","))

        with open(filename, "w") as fd:
            config.write(fd)

    def load_parameters(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Save Parameters", "./tests", "Parameters File (*.par)")
        if not filename:
            return
        config = configparser.ConfigParser()

        config.read(filename)

        self.parent_py.load_params(config)

    def save_resistances(self):
        filename, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Resistances", "./tests", "Resistances File (*.npz)")
        if not filename:
            return
        voltages, resistances, _ = self.parent_py.get_data()
        np.savez(filename, voltages=voltages, resistances=resistances)

    def load_resistances(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Resistances", "./tests", "Resistances File (*.npz)")
        if not filename:
            return
        npzfile = np.load(filename)
        voltages, resistances = npzfile["voltages"], npzfile["resistances"]
        self.parent_py.load_data(voltages, resistances)


class CssCheckBoxes(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent_py = parent

        layout = QtWidgets.QHBoxLayout(self)

        self.checkboxes = []

        for i in range(1, 13, 4):
            checkbox = QtWidgets.QCheckBox(f"CSS {i:d}-{i+3:d}", parent=self)
            self.checkboxes.append(checkbox)
            layout.addWidget(checkbox)

    def collect_checkboxes(self):
        return [checkbox.isChecked() for checkbox in self.checkboxes]
