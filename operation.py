import datetime
import struct

from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import Signal, QTimer, Qt
from PySide2.QtGui import QPixmap, QColor
from PySide2.QtWidgets import QFrame, QSizePolicy

from misc import clear_layout, ClickableLabel, Lamp
from sensor_system import MS_Uni, MS_ABC
import pathlib
import yaml
import logging
from program_generator import ProgramGenerator
from time import time, sleep
import numpy as np
import threading
import pyqtgraph as pg
from queue import Queue
import csv

logger = logging.getLogger(__name__)

colors_for_lines = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22',
                    '#17becf', "#DDDDDD", "#00FF00"]

def format_floats(floats_list):
    return (f"{x:5.5f}" for x in floats_list)


class LinesDrawButton(QtWidgets.QPushButton):
    def __init__(self, plot_widget, *args, **kwargs):
        super(LinesDrawButton, self).__init__("Lines toggle", *args, **kwargs)
        self.plot_widget = plot_widget
        self.clicked.connect(self.toggle_expand)
        self.tool_window = QtWidgets.QWidget(self, f=QtCore.Qt.Tool)
        self.tool_window.setWindowTitle("Lines Toggle")
        self.tool_window_layout = QtWidgets.QVBoxLayout(self.tool_window)

        self.pixmaps = []
        self.labels = []
        for idx, color in enumerate(colors_for_lines):
            layout3 = QtWidgets.QHBoxLayout()
            pixmap = QPixmap(20, 20)
            color = QColor(color)
            pixmap.fill(color)
            pixmap_label = ClickableLabel(idx, self)
            pixmap_label.setPixmap(pixmap)
            pixmap_label.setAlignment(Qt.AlignRight)
            pixmap_label.clicked.connect(self.plot_widget.set_visible_invisible)
            self.pixmaps.append(pixmap_label)
            label = QtWidgets.QLabel(f"Sensor {idx + 1}")
            self.labels.append(label)
            layout3.addWidget(pixmap_label)
            layout3.addWidget(label)
            layout3.addStretch()
            self.tool_window_layout.addLayout(layout3)
        self.tool_window_layout.addStretch()


    def toggle_expand(self):
        logger.debug("toggle clicked")
        logger.debug(f"tool window hidden: {self.tool_window.isHidden()}")
        if self.tool_window.isHidden():
            self.tool_window.show()
        else:
            self.tool_window.hide()
    def set_number_of_sensors(self, number):
        for idx, (label, pixmap) in enumerate(zip(self.labels, self.pixmaps)):
            label.setVisible(idx < number)
            pixmap.setVisible(idx < number)
            pixmap.set_true()


class QueueRunner():
    def __init__(self, queue: Queue, converters_func_voltage_to_r):
        self.queue = queue
        self.thread = None
        self.hold_method = None
        self.stopped = True
        self.filename = None
        self.converter_funcs_dicts = converters_func_voltage_to_r
        self._meas_values_tuple = None
        self.meas_tuple_lock = threading.Lock()

    def set_hold(self, hold_method):
        self.hold_method = hold_method

    def drop_hold_method(self):
        self.hold_method = None

    def get_meas_tuple(self):
        with self.meas_tuple_lock:
            return self._meas_values_tuple

    def set_meas_tuple(self, values):
        with self.meas_tuple_lock:
            self._meas_values_tuple = values

    def start(self):
        if self.hold_method is not None and self.stopped:
            self.stopped = False
            self.thread = threading.Thread(target=self.cycle)
            self.filename = (pathlib.Path("./tests") / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")).with_suffix(
                ".txt")
            self.binary_filename = (pathlib.Path("./tests") / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")).with_suffix(".dat")
            self.thread.start()

    def join(self):
        if self.thread is not None:
            self.thread.join()

    def cycle(self):
        fd_bin = self.binary_filename.open("wb")
        headed = False

        bin_write_struct = None
        converter_funcs = self.converter_funcs_dicts()
        while not self.stopped:
            sleep(0.02)
            if not self.queue.empty():
                data = self.queue.get()
                us, rs, time_next_plus_t0, time_next, temperatures, gas_state, stage_num, stage_type, sensor_states, converted = data
                sensor_resistances = tuple(
                    converter_func_dict[sensor_state](u) for converter_func_dict, u, sensor_state in
                    zip(converter_funcs, us, sensor_states))
                logger.debug(f"Call in cycle")
                self.set_meas_tuple((us, rs, sensor_resistances, sensor_states, temperatures, converted))
                self.hold_method((sensor_resistances, rs, time_next))
                if not headed:
                    sensors_number = len(rs)
                    headed = True
                    bin_write_struct = struct.Struct("<f" + sensors_number * 4 * "f" + "BIH" + sensors_number * "B")
                    fd_bin.write(struct.pack("<B", sensors_number))
                fd_bin.write(bin_write_struct.pack(time_next,
                                    *us,
                                    *rs,
                                    *sensor_resistances,
                                    *temperatures,
                                    gas_state,
                                    stage_num,
                                    stage_type,
                                    *sensor_states))
        while not self.queue.empty():
            data = self.queue.get()
            us, rs, time_next_plus_t0, time_next, temperatures, gas_state, stage_num, stage_type, sensor_states, converted = data
            sensor_resistances = tuple(
                converter_func_dict[sensor_state](u) for converter_func_dict, u, sensor_state in
                zip(converter_funcs, us, sensor_states))
            logger.debug(f"Call in cycle")
            self.set_meas_tuple((us, rs, sensor_resistances, sensor_states, temperatures, converted))
            self.hold_method((sensor_resistances, rs, time_next))
            if not headed:
                sensors_number = len(rs)
                headed = True
                bin_write_struct = struct.Struct("<f" + sensors_number * 4 * "f" + "BIH" + sensors_number * "B")
                fd_bin.write(struct.pack("<B", sensors_number))
            fd_bin.write(bin_write_struct.pack(time_next,
                                               *us,
                                               *rs,
                                               *sensor_resistances,
                                               *temperatures,
                                               gas_state,
                                               stage_num,
                                               stage_type,
                                               *sensor_states))

        fd_bin.close()

    def stop(self):
        self.stopped = True


class OperationWidget(QtWidgets.QWidget):
    stop_signal = Signal()
    running_signal = Signal()

    def __init__(self, parent, global_settings, measurement_widget,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_py = parent
        self.global_settings = global_settings
        self.measurement_widget = measurement_widget
        self.gasstate_widget = parent.gasstate_widget
        self.runner = None
        self.generator = None
        self.queue = Queue()
        self.queue_runner = QueueRunner(self.queue, self.measurement_widget.get_voltage_to_resistance_funcs)
        self.settings = self.parent_py.settings_widget
        self.settings.redraw_signal.connect(self.refresh_state)
        layout = QtWidgets.QVBoxLayout(self)
        self.timer_plot = QTimer()
        self.timer_plot.setInterval(1000)
        self.stop_signal.connect(self.stop)
        self.running_signal.connect(self.on_running_signal)
        self.values_set_timer = QTimer()
        layout1 = QtWidgets.QHBoxLayout()
        layout2 = QtWidgets.QHBoxLayout()
        layout.addLayout(layout1)
        layout.addLayout(layout2)

        load_program_groupbox = QtWidgets.QGroupBox()
        load_program_groupbox.setTitle("Program")
        load_program_groupbox_layout = QtWidgets.QHBoxLayout(load_program_groupbox)
        self.load_program_button = QtWidgets.QPushButton("Load program")
        self.load_program_button.clicked.connect(self.load_program)

        self.load_label = QtWidgets.QLabel("Not loaded")
        self.load_label.setFrameStyle(QFrame.Panel)
        self.load_label.setStyleSheet("background-color:pink")
        load_program_groupbox_layout.addWidget(self.load_program_button)
        load_program_groupbox_layout.addWidget(self.load_label)
        load_program_groupbox_layout.addStretch()

        layout1.addWidget(load_program_groupbox)

        controls_groupbox = QtWidgets.QGroupBox()
        controls_groupbox.setTitle("Controls")
        controls_groupbox_layout = QtWidgets.QHBoxLayout(controls_groupbox)
        start_button = QtWidgets.QPushButton("Start")
        stop_button = QtWidgets.QPushButton("Stop")
        start_button.clicked.connect(self.start)
        stop_button.clicked.connect(self.stop)
        self.checkbox_if_send_u_or_r = QtWidgets.QCheckBox("Send U")
        self.checkbox_if_send_u_or_r.setChecked(True)
        self.solid_mode_mode = QtWidgets.QCheckBox("Solid mode")
        controls_groupbox_layout.addWidget(start_button)
        controls_groupbox_layout.addWidget(stop_button)
        controls_groupbox_layout.addWidget(self.checkbox_if_send_u_or_r)
        controls_groupbox_layout.addWidget(self.solid_mode_mode)
        controls_groupbox_layout.addStretch()

        layout1.addWidget(controls_groupbox)

        _, sensor_number, *_ = self.settings.get_variables()
        self.plot_widget = AnswerPlotWidget(self)
        self.plot_widget.set_sensor_number(sensor_number)
        self.lines_widget = LinesDrawButton(self.plot_widget, self)
        self.lines_widget.set_number_of_sensors(sensor_number)

        layout1.addStretch(1)

        plot_options_groupbox = QtWidgets.QGroupBox()
        plot_options_groupbox.setTitle("Plot options")
        plot_options_groupbox_layout = QtWidgets.QHBoxLayout(plot_options_groupbox)

        temp_button = QtWidgets.QPushButton("Only working")
        temp_button.clicked.connect(self.turn_on_working_lines)
        plot_options_groupbox_layout.addWidget(temp_button)

        temp_button = QtWidgets.QPushButton("All on")
        temp_button.clicked.connect(self.turn_on_all_lines)
        plot_options_groupbox_layout.addWidget(temp_button)

        temp_button = QtWidgets.QPushButton("All off")
        temp_button.clicked.connect(self.turn_off_all_lines)
        plot_options_groupbox_layout.addWidget(temp_button)
        plot_options_groupbox_layout.addWidget(self.lines_widget)

        plot_options_groupbox_layout.addStretch()

        layout2.addWidget(plot_options_groupbox)

        status_groupbox = QtWidgets.QGroupBox()
        status_groupbox.setTitle("Status")
        status_groupbox_layout = QtWidgets.QHBoxLayout(status_groupbox)

        self.lamp = Lamp()
        self.lamp.set_stop()
        status_groupbox_layout.addWidget(self.lamp)

        layout2.addWidget(status_groupbox)

        layout2.addStretch(1)

        self.timer_plot.timeout.connect(self.plot_widget.plot_answer)
        self.queue_runner.set_hold(self.plot_widget.hold_answer)
        self.values_set_timer.timeout.connect(self.set_values_on_meas_widget)
        layout.addWidget(self.plot_widget)

    def refresh_state(self):
        comport, sensor_number, multirange, *_ = self.settings.get_variables()
        self.stop()
        self.plot_widget.set_sensor_number(sensor_number)
        self.lines_widget.set_number_of_sensors(sensor_number)
        self.runner = None
        if self.generator is None:
            self.load_label.setText("Not loaded")
            self.load_label.setStyleSheet("background-color:pink")
        else:
            self.load_label.setText("Loaded")
            self.load_label.setStyleSheet("background-color:palegreen")

    def get_checkbox_state(self):
        return self.checkbox_if_send_u_or_r.isChecked()

    def get_range_mode_settings(self):
        if self.solid_mode_mode.isChecked():
            return self.measurement_widget.get_r4_resistance_modes
        else:
            return None

    def start(self):
        if self.load_label.text() == "Loaded":
            self.refresh_state()
            self.load_program_button.setEnabled(False)
            comport, sensor_number, multirange, *_ = self.settings.get_variables()
            self.runner = ProgramRunner(
                self.generator, self.settings.get_new_ms,
                self.measurement_widget.get_sensor_types_list,
                self.measurement_widget.get_convert_funcs,
                self.get_range_mode_settings(),
                multirange,
                self.gasstate_widget.send_state,
                self.get_checkbox_state,
                self.queue,
                self.stop_signal, self.running_signal,
                sensor_number)
            self.plot_widget.clear_plot()
            self.runner.start()
            self.queue_runner.start()
            self.timer_plot.start()
            self.values_set_timer.setInterval(int(self.generator.program.settings.step * 500))
            self.values_set_timer.start()
            self.settings.start_program_signal.emit(1)


    def stop(self):
        if self.runner is not None:
            self.runner.stop()
            self.runner.join()
        self.queue_runner.stop()
        self.queue_runner.join()
        self.timer_plot.stop()
        self.values_set_timer.stop()
        self.lamp.set_stop()
        self.settings.start_program_signal.emit(0)
        self.load_program_button.setEnabled(True)

    def load_program(self):
        filename, filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open program",
            self.global_settings.value("operation_widget_programs_path", "./tests"),
            "Program file (*.yaml)")
        if not filename:
            self.load_label.setText("Not loaded")
            self.load_label.setStyleSheet("background-color:pink")
            return
        self.global_settings.setValue("operation_widget_programs_path", pathlib.Path(filename).parent.as_posix()),
        try:
            loaded = yaml.load(pathlib.Path(filename).read_text(), yaml.Loader)
        except:
            self.load_label.setText("Not loaded")
            self.load_label.setStyleSheet("background-color:pink")
            raise
        else:
            self.generator = ProgramGenerator(loaded)
            # logger.debug(f"Parsing started {datetime.datetime.now()}")
            # with open("./tests/parsed.txt", "w") as fd:
            #     for time_, values in self.generator.parse_program_to_queue():
            #         fd.write(f"{time_}, {values}\n")
            # logger.debug(f"Parsing stopped {datetime.datetime.now()}")
            self.load_label.setText("Loaded")
            self.load_label.setStyleSheet("background-color:palegreen")

    def set_values_on_meas_widget(self):
        results = self.queue_runner.get_meas_tuple()
        if results is not None:
            self.measurement_widget.set_results_values_to_widgets(*results)

    def turn_on_working_lines(self):
        if self.plot_widget:
            for state, pixmap in zip(self.measurement_widget.get_working_widgets(), self.lines_widget.pixmaps):
                if state != pixmap.state:
                    pixmap.click()

    def turn_on_all_lines(self):
        if self.plot_widget:
            for pixmap in self.lines_widget.pixmaps:
                if not pixmap.state:
                    pixmap.click()

    def turn_off_all_lines(self):
        if self.plot_widget:
            for pixmap in self.lines_widget.pixmaps:
                if pixmap.state:
                    pixmap.click()

    def on_running_signal(self):
        self.lamp.set_running()


class ProgramRunner:

    def __init__(self, program_generator: ProgramGenerator, get_ms_method,
                 get_sensor_types_list, get_convert_funcs, solid_mode, multirange,
                 send_gasstate_func,
                 checkbox_state,
                 queue,
                 stop_signal,
                 running_signal,
                 sensor_number):
        self.stopped = True
        self.stop_signal = stop_signal
        self.running_signal = running_signal
        self.program_generator = program_generator
        self.program = self.program_generator.parse_program_to_queue()
        self.get_ms_method = get_ms_method
        self.get_sensor_types_list = get_sensor_types_list
        self.convert_funcs = get_convert_funcs("R")
        self.convert_funcs_2 = get_convert_funcs("V")
        self.solid_mode = solid_mode
        self.multirange: bool = multirange
        self.send_gasstate_func = send_gasstate_func
        self.checkbox_state = checkbox_state
        self.sensor_number = sensor_number
        self.thread = None
        self.queue = queue

        self.need_to_analyze = self.multirange and (self.solid_mode is None)

    def start(self):
        self.stopped = False
        self.thread = threading.Thread(target=self.cycle)
        self.thread.start()

    def stop(self):
        self.stopped = True

    def join(self):
        if self.thread is not None:
            self.thread.join()

    def cycle(self):
        ms: MS_Uni = self.get_ms_method()
        time_0 = time()
        time_sleep = self.program_generator.program.settings.step / 100
        sensor_types_list = self.get_sensor_types_list()
        sensor_states = [
                            1,
                        ] * self.sensor_number
        sensor_stab_up_states = [
                                    True,
                                ] * self.sensor_number
        sensor_stab_down_states = [
                                      True,
                                  ] * self.sensor_number

        while not self.stopped:
            try:
                time_next, (temperatures, gas_state, stage_num,
                            stage_type) = next(self.program)
            except StopIteration:
                self.stop_signal.emit()
                self.stopped = True
            else:
                self.running_signal.emit()
                temperatures = temperatures[:self.sensor_number]
                time_next_plus_t0 = time_0 + time_next
                while time() < time_next_plus_t0:
                    sleep(time_sleep)
                try:
                    logger.debug(f"{time()} {time_next_plus_t0} {time_next}")
                    if self.checkbox_state():
                        converted = self.convert_to_voltages(temperatures)
                        us, rs = ms.full_request(converted, request_type=MS_ABC.REQUEST_U,
                                                 sensor_types_list=sensor_types_list)
                    else:
                        converted = self.convert_to_resistances(temperatures)
                        us, rs = ms.full_request(converted,
                                                 request_type=MS_ABC.REQUEST_R,
                                                 sensor_types_list=sensor_types_list)
                except MS_ABC.MSException:
                    self.stop_signal.emit()
                    self.clear_ms_state(ms)
                    raise
                else:
                    try:
                        self.send_gasstate_func(gas_state)
                    except:
                        logger.error("Cant send gas_state")
                    finally:
                        self.queue.put((us, rs, time_next_plus_t0, time_next,
                                        temperatures, gas_state, stage_num,
                                        stage_type, sensor_states, converted))
                        self.analyze_us(ms, us, sensor_states,
                                        sensor_stab_up_states,
                                        sensor_stab_down_states)
        self.clear_ms_state(ms)

    def clear_ms_state(self, ms: MS_Uni):
        ms.clear_state(self.get_sensor_types_list())
        ms.close()

    def convert_to_resistances(self, temperatures):
        return [func(t) for t, func in zip(temperatures, self.convert_funcs)]

    def convert_to_voltages(self, temperatures):
        return [func(t) for t, func in zip(temperatures, self.convert_funcs_2)]

    def analyze_us(self, ms: MS_Uni, us: np.ndarray, sensor_states: list,
                   sensor_stab_up_states: list, sensor_stab_down_states: list):
        if self.need_to_analyze:
            i = 0
            for idx, value_bool in enumerate(us > 4.6):
                if value_bool and sensor_stab_up_states[idx]:
                    sensor_states[idx] = min(sensor_states[idx] + 1, 3)
                    if sensor_states[idx] == 3:
                        sensor_stab_up_states[idx] = False
                    sensor_stab_down_states[idx] = True
                    i += 1
            for idx, value_bool in enumerate(us < 0.6):
                if value_bool and sensor_stab_down_states[idx]:
                    sensor_states[idx] = max(sensor_states[idx] - 1, 1)
                    sensor_stab_up_states[idx] = True
                    if sensor_states[idx] == 1:
                        sensor_stab_down_states[idx] = False
                    i += 1
            if i > 0:
                ms.send_measurement_range(sensor_states)
        else:
            if self.multirange:
                new_modes = self.solid_mode()
                if not all(mode == prev_mode for mode, prev_mode in zip(new_modes, sensor_states)):
                    ms.send_measurement_range(new_modes)
                    for i in range(len(sensor_states)):
                        sensor_states[i] = new_modes[i]



class AnswerPlotWidget(pg.PlotWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensor_number = 12
        self.number_of_dots = 1200

        self.rs = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.us = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.times = np.empty(shape=(self.number_of_dots,))
        self.drawing_index = 0
        self.emphasized_lines = []
        self.hidden_lines = []
        self.legend = pg.LegendItem(offset=(-10, 10), labelTextColor=pg.mkColor("#FFFFFF"),
                               brush=pg.mkBrush(pg.mkColor("#111111")))
        plot_item = self.getPlotItem()
        self.vboxitem = plot_item.getViewBox()
        self.legend.setParentItem(plot_item)
        plot_item.showGrid(x=True, y=True)
        plot_item.setLogMode(y=True)

        self.plot_data_items = [
            self.plot([0], [0], name=f"Sensor {i + 1}") for i in range(self.sensor_number)
        ]
        for idx, (plot_data_item, color) in enumerate(zip(self.plot_data_items, colors_for_lines)):
            plot_data_item.setPen(pg.mkPen(pg.mkColor(color), width=2))
            plot_data_item.setCurveClickable(True)
            plot_data_item.sigClicked.connect(self.line_clicked)
            self.legend.addItem(plot_data_item, f"Sensor {idx + 1}")
        self.lock = threading.Lock()

    def line_clicked(self, line):
        logger.debug("Line clicked")
        if line in self.emphasized_lines:
            line.setShadowPen(pg.mkPen(None))
            self.emphasized_lines.remove(line)
        else:
            line.setShadowPen(pg.mkPen(pg.mkColor("#666666"), width=8))
            self.emphasized_lines.append(line)

    def set_visible_invisible(self, index, state):
        line = self.plot_data_items[index]
        if line in self.vboxitem.addedItems:
            if not state:
                self.vboxitem.removeItem(line)
        else:
            if state:
                self.vboxitem.addItem(line)

    def set_visible(self, index):
        line = self.plot_data_items[index]
        if line not in self.vboxitem.addedItems:
            self.vboxitem.addItem(line)

    def set_invisible(self, index):
        line = self.plot_data_items[index]
        if line in self.vboxitem.addedItems:
            self.vboxitem.removeItem(line)

    def set_sensor_number(self, sensor_number):
        self.sensor_number = sensor_number
        self.clear_plot()

    def clear_plot(self):
        self.drawing_index = 0
        self.rs = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.us = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.times = np.empty(shape=(self.number_of_dots,))
        self.legend.clear()
        for idx, plot_item_data in enumerate(self.plot_data_items):
            plot_item_data.setData(x=[], y=[])
            if idx < self.sensor_number:
                self.set_visible(idx)
                self.legend.addItem(plot_item_data, f"Sensor {idx + 1}")
            else:
                self.set_invisible(idx)

    def hold_answer(self, answer):
        with self.lock:
            us, rs, time_next = answer
            logger.debug(f"Start add dots {time_next}")

            if self.drawing_index == self.number_of_dots:
                self.rs[:, :-1] = self.rs[:, 1:]
                self.us[:, :-1] = self.us[:, 1:]
                self.times[:-1] = self.times[1:]
                self.rs[:, self.number_of_dots - 1] = rs
                self.us[:, self.number_of_dots - 1] = us
                self.times[self.number_of_dots - 1] = time_next
            else:
                self.rs[:, self.drawing_index] = rs
                self.us[:, self.drawing_index] = us
                self.times[self.drawing_index] = time_next

            if self.drawing_index < self.number_of_dots:
                self.drawing_index += 1
            logger.debug(f"End adding dots {time_next}")

    def plot_answer(self):
        with self.lock:
            logger.debug(f'Plotting data, drawing_index = {self.drawing_index}')
            for plot_item, us_line, rs_line in zip(
                    self.plot_data_items, self.us[:, :self.drawing_index],
                    self.rs[:, :self.drawing_index]):
                plot_item.setData(x=self.times[:self.drawing_index], y=us_line)
            logger.debug(f'End plotting data, drawing_index = {self.drawing_index}')

