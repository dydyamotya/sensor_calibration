from threading import Thread
from PySide2 import QtWidgets
from PySide2.QtGui import QPixmap, QColor
from PySide2.QtCore import Slot, Qt
from sensor_system import MS_Uni, MS_ABC
from misc import TypeCheckLineEdit, clear_layout, CssCheckBoxes
import time
import configparser
import pyqtgraph as pg

import numpy as np
import numpy.ma as ma

import logging

logger = logging.getLogger(__name__)

colors_for_lines = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22',
                    '#17becf', "#DDDDDD", "#00FF00"]

values_for_css_boxes = [MS_ABC.SEND_CSS_1_4,
                        MS_ABC.SEND_CSS_5_8, MS_ABC.SEND_CSS_9_12]




class CalibrationWidget(QtWidgets.QWidget):
    def __init__(self, parent, log_level, global_settings):
        super().__init__()
        self.setWindowTitle("Calibration")
        self.parent_py = parent
        self.log_level = log_level

        self.stopped = True
        self.ms = None
        self.thread = None
        self.last_idx = 0

        layout = QtWidgets.QHBoxLayout(self)

        left_layout = QtWidgets.QVBoxLayout()

        self.calibration_settings = CalibrationSettings(self)
        self.cal_plot_widget = CalibrationPlotWidget(self)
        self.cal_buttons = CalibrationButtons(self)

        scroll_per_sensor = QtWidgets.QScrollArea()
        scroll_per_sensor.setWidgetResizable(True)
        self.per_sensor = PerSensorSettings(self)
        self.per_sensor.connect_return_pressed(self.recalc_signal_handler)
        scroll_per_sensor.setWidget(self.per_sensor)
        self.r0_voltage = TypeCheckLineEdit(self, float, 0.3)
        self.save_buttons = SaveButtons(self)
        self.css_checkboxes = CssCheckBoxes(self)

        self.parent_py.settings_widget.redraw_signal.connect(self.per_sensor.ui_init)

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

        left_layout.addWidget(scroll_per_sensor)
        left_layout.addWidget(self.save_buttons)

        layout.addWidget(self.cal_plot_widget)

        self.voltages = None
        self.resistances = None

    @property
    def comport(self) -> str:
        return self.parent_py.settings_widget.get_variables()[0]

    @property
    def sensor_number(self) -> int:
        return self.parent_py.settings_widget.get_variables()[1]

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
            self.full_request_until_result((0,) * self.sensor_number)
        if self.ms:
            self.ms.close()
        self.ms = None

    def get_average_massive(
        self, voltage: float, steps_per_measurement: int, sleep_time: float
    ):
        voltages = (voltage,) * self.sensor_number
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
            self.ms = self.parent_py.settings_widget.get_new_ms()
            r0_voltage = self.r0_voltage.get_value()
            steps_per_measurement = 10
            averaging_massive = self.get_average_massive(
                r0_voltage, steps_per_measurement, 2.0
            )

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

        self.ms = self.parent_py.settings_widget.get_new_ms()

        (
            initial_voltage,
            steps_per_measurement,
            end_voltage,
            sleep_time,
            dots_to_draw,
            microstep,
        ) = self.calibration_settings.get_variables()

        all_steps = int((end_voltage - initial_voltage) / microstep) + 1

        self.resistances = np.zeros((self.sensor_number, all_steps))

        voltage_row = np.linspace(
            initial_voltage, end_voltage + microstep, num=all_steps
        )

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
                    voltage_dot, steps_per_measurement, sleep_time
                )

                self.resistances[:, idx] = self.calculate_masked_mean(
                    averaging_massive)

                if idx % dots_to_draw == 0:
                    self.cal_plot_widget.set_lines(
                        self.voltages[:, :idx],
                        self.per_sensor.process_resistances(
                            self.resistances[:, :idx]),
                    )
            except MS_ABC.MSException:
                self.last_idx = idx
                self.stopped = True
                self.ms.close()
                self.ms = None
                return
            except KeyboardInterrupt:
                break
        self.full_request_until_result((0,) * self.sensor_number)
        self.stopped = True
        self.last_idx = all_steps
        self.ms.close()
        self.ms = None

    def full_request_until_result(self, values):
        sensor_types_list = [
            send_code
            for checkbox_state, send_code in zip(
                self.css_checkboxes.collect_checkboxes(), values_for_css_boxes
            )
            if checkbox_state
        ]

        logger.debug(f"{sensor_types_list}")
        exceptions_save = None
        for i in range(20):
            try:
                us, rs = self.ms.full_request(values, sensor_types_list=sensor_types_list)
            except MS_ABC.MSException as e:
                exceptions_save = e
                logger.debug(f"Full request try: {i}")
            else:
                return us, rs
        else:
            raise exceptions_save

    def recalc_signal_handler(self):
        if self.stopped:
            logger.debug("Recalc signal handler")
            if any(self.resistances.flatten() > 0):
                voltages, _, temperatures = self.get_data()
                self.cal_plot_widget.set_lines(voltages, temperatures)

    def get_data(self):
        try:
            voltages = self.voltages[:, : self.last_idx]
            temperatures = self.per_sensor.process_resistances(
                self.resistances[:, : self.last_idx]
            )
            resistances = self.resistances[:, : self.last_idx]
        except TypeError:
            voltages, temperatures, resistances = (
                np.array([]),
                np.array([]),
                np.array([]),
            )
        return voltages, resistances, temperatures

    def load_data(self, voltages, resistances):
        self.last_idx = voltages.shape[1]
        self.voltages = voltages
        self.resistances = resistances

    def get_params(self):
        r0s, rns, alphas = [], [], []
        (
            initial_voltage,
            steps_per_measurement,
            end_voltage,
            sleep_time,
            dots_to_draw,
            microstep,
        ) = self.calibration_settings.get_variables()
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
        self.parent_py = parent
        self.signals = []
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.ui_init()


    def ui_init(self):
        logger.debug("Redraw signal catched")
        clear_layout(self.layout())
        layout = self.layout()
        self.disconnect_all_signals()

        sensor_number = self.parent_py.sensor_number

        logger.debug(sensor_number)

        self.sensor_widgets = tuple(
            OneSensorWidget(self, i) for i in range(sensor_number)
        )

        self.reconnect_all_signals()

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

        layout.update()
        self.update()


    def get_variables(self):
        for sensor_widget in self.sensor_widgets:
            yield sensor_widget.get_variables()

    def set_variables(self, config: configparser.ConfigParser):
        for idx, sensor_widget in enumerate(self.sensor_widgets):
            sensor_widget.r0.set_value(
                float(config["R0"][f"R0_{idx:d}"].replace(",", ".")) / 100
            )
            sensor_widget.rn.set_value(
                float(config["Rc"][f"Rc_{idx:d}"].replace(",", ".")) / 100
            )
            sensor_widget.alpha.set_value(
                float(config["a"][f"a0_{idx:d}"].replace(",", "."))
            )

    def process_resistances(self, resistances: np.ndarray) -> np.ndarray:
        T0 = self.T0_entry.get_value()
        temperatures = []
        for resistance_row, (r0, rn, alpha) in zip(resistances, self.get_variables()):
            temperatures.append(
                ((resistance_row - rn) / (r0 - rn) - 1) / alpha + T0)

        return np.vstack(temperatures)

    def set_r0s(self, resistances):
        for sensor_widget, resistance in zip(self.sensor_widgets, resistances):
            sensor_widget.set_r0(resistance)

    def connect_return_pressed(self, signal):
        self.signals.append(signal)
        for widget in self.sensor_widgets:
            widget.return_pressed_connect(signal)

    def disconnect_all_signals(self):
        for signal in self.signals:
            for widget in self.sensor_widgets:
                widget.return_pressed_disconnect(signal)

    def reconnect_all_signals(self):
        for signal in self.signals:
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
        color = QColor(colors_for_lines[number])
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

    def return_pressed_disconnect(self, signal):
        self.r0.returnPressed.disconnect(signal)
        self.rn.returnPressed.disconnect(signal)
        self.alpha.returnPressed.disconnect(signal)


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
            "Microstep",
        ]

        self.widget_types = [float, int, float, float, int, float]
        self.widget_defaults = [0.1, 10, 5.0, 2.0, 1, 0.01]
        self.entries = [
            TypeCheckLineEdit(self, type_, default_value)
            for widget_name, type_, default_value in zip(
                self.widgets_names, self.widget_types, self.widget_defaults
            )
        ]
        for widget_name, entry in zip(self.widgets_names, self.entries):
            layout.addRow(widget_name, entry)

    def get_variables(self):
        for entry in self.entries:
            yield entry.get_value()


class CalibrationPlotWidget(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.legend = pg.LegendItem(offset=(-10, 10), labelTextColor=pg.mkColor("#FFFFFF"),
                                    brush=pg.mkBrush(pg.mkColor("#111111")))
        plot_item = self.getPlotItem()
        plot_item.disableAutoRange()
        plot_item.setXRange(-0.2, 5.2)
        plot_item.setYRange(-20, 520)

        self.legend.setParentItem(plot_item)
        plot_item.showGrid(x=True, y=True)
        plot_item.setLabel("bottom", "Voltage", units="V")
        plot_item.setLabel("left", "Temperature", units="C")

        self.plot_data_items = [
            self.plot([0], [0], name=f"Sensor {i + 1}") for i in range(len(colors_for_lines))
        ]
        for idx, (plot_data_item, color) in enumerate(zip(self.plot_data_items, colors_for_lines)):
            plot_data_item.setPen(pg.mkPen(pg.mkColor(color), width=2))
            plot_data_item.setCurveClickable(True)
            self.legend.addItem(plot_data_item, f"Sensor {idx + 1}")

    def set_lines(self, voltages, temperatures):
        for plot_item, voltage_row, temperature_row in zip(
                self.plot_data_items, voltages, temperatures
        ):
            plot_item.setData(x=voltage_row, y=temperature_row)

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
            self, "Save Calibration", "./tests", "Calibration File (*.cal)"
        )
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
                np.savetxt(fd, new_array, fmt="%.6f",
                           delimiter="\t", newline="\t\n")

    def save_parameters(self):
        filename, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Parameters", "./tests", "Parameters File (*.par)"
        )
        if not filename:
            return

        config = configparser.ConfigParser()
        r0s, rns, alphas, t0, Vmax = self.parent_py.get_params()

        config["R0"] = {
            f"R0_{idx:d}": "{:f}".format(r0 * 100).replace(".", ",")
            for idx, r0 in enumerate(r0s)
        }
        config["Rc"] = {
            f"Rc_{idx:d}": "{:f}".format(rn * 100).replace(".", ",")
            for idx, rn in enumerate(rns)
        }
        config["a"] = {
            f"a0_{idx:d}": "{:f}".format(rn).replace(".", ",")
            for idx, rn in enumerate(alphas)
        }
        config["T0"] = dict(T0="{:f}".format(t0).replace(".", ","))
        config["Vmax"] = dict(Vmax="{:f}".format(Vmax).replace(".", ","))

        with open(filename, "w") as fd:
            config.write(fd)

    def load_parameters(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Parameters", "./tests", "Parameters File (*.par)"
        )
        if not filename:
            return
        config = configparser.ConfigParser()

        config.read(filename)

        self.parent_py.load_params(config)

    def save_resistances(self):
        filename, filters = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Resistances", "./tests", "Resistances File (*.npz)"
        )
        if not filename:
            return
        voltages, resistances, temperatures = self.parent_py.get_data()
        np.savez(filename, voltages=voltages, resistances=resistances, temperatures=temperatures)

    def load_resistances(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Resistances", "./tests", "Resistances File (*.npz)"
        )
        if not filename:
            return
        npzfile = np.load(filename)
        logger.debug("File loaded")
        voltages, resistances = npzfile["voltages"], npzfile["resistances"]
        self.parent_py.load_data(voltages, resistances)


