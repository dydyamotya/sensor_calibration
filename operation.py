import datetime

from PySide2 import QtWidgets
from PySide2.QtCore import Signal, QTimer

from misc import clear_layout
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

logger = logging.getLogger(__name__)

colors_for_lines = ["#BBCCEE", "#CCEEFF", "#CCDDAA", "#EEEEBB", "#FFCCCC", "#DDDDDD", "#222255", "#225555", "#225522", "#666633", "#663333", "#555555"]

class QueueRunner():
    def __init__(self, queue: Queue, hold_method, converters_func_voltage_to_r):
        self.queue= queue
        self.thread = None
        self.hold_method = hold_method
        self.stopped = True
        self.filename = None
        self.converter_funcs_dicts = converters_func_voltage_to_r

    def start(self):
        self.stopped = False
        self.thread = threading.Thread(target=self.cycle)
        self.thread.daemon = True
        self.filename = (pathlib.Path("./tests") / datetime.datetime.now().strftime("%Y%m%d-%H:%M:%S")).with_suffix(".txt")
        self.thread.start()

    def cycle(self):
        fd = self.filename.open("w")
        converter_funcs = self.converter_funcs_dicts()
        while not self.stopped:
            sleep(0.01)
            if not self.queue.empty():
                data = self.queue.get()
                us, rs, time_next_plus_t0, time_next, temperatures, gas_state, stage_num, stage_type, sensor_states = data
                sensor_resistances = tuple(converter_func_dict[sensor_state](u) for converter_func_dict, u, sensor_state in zip(converter_funcs, us, sensor_states))

                self.hold_method((sensor_resistances, rs, time_next))
                fd.write(str((us, rs, sensor_resistances, time_next, temperatures, gas_state, stage_num, stage_type, sensor_states)) + "\n")
        fd.close()

    def stop(self):
        self.stopped = True


class OperationWidget(QtWidgets.QWidget):


    def __init__(self, parent, log_level, global_settings, measurement_widget,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_py = parent
        self.measurement_widget = measurement_widget
        self.gasstate_widget = parent.gasstate_widget
        self.runner = None
        self.queue = Queue()
        self.settings = self.parent_py.settings_widget
        self.settings.redraw_signal.connect(self.init_ui)
        QtWidgets.QVBoxLayout(self)
        self.timer_plot = QTimer()
        self.timer_plot.setInterval(1000)
        self.init_ui()


    def init_ui(self):
        clear_layout(self.layout())
        self.runner = None

        layout = self.layout()

        self.status_label = QtWidgets.QLabel("Not loaded")

        load_program_button = QtWidgets.QPushButton("Load program")
        load_program_button.clicked.connect(self.load_program)
        layout.addWidget(load_program_button)

        start_button = QtWidgets.QPushButton("Start")
        stop_button = QtWidgets.QPushButton("Stop")
        self.checkbox_if_send_u_or_r = QtWidgets.QCheckBox("Send U")
        layout.addWidget(start_button)
        layout.addWidget(stop_button)
        layout.addWidget(self.checkbox_if_send_u_or_r)
        start_button.clicked.connect(self.start)
        stop_button.clicked.connect(self.stop)

        self.plot_widget = AnswerPlotWidget(self)
        self.timer_plot.timeout.connect(self.plot_widget.plot_answer)
        layout.addWidget(self.plot_widget)
        self.queue_runner = QueueRunner(self.queue, self.plot_widget.hold_answer, self.measurement_widget.get_voltage_to_resistance_funcs)

    def get_checkbox_state(self):
        return self.checkbox_if_send_u_or_r.isChecked()

    def start(self):
        if self.runner:
            self.runner.start()
        if self.queue_runner:
            self.queue_runner.start()
        if not self.timer_plot.isActive():
            self.timer_plot.start()

    def stop(self):
        if self.runner:
            self.runner.stop()
        if self.queue_runner:
            self.queue_runner.stop()
        if self.timer_plot.isActive():
            self.timer_plot.stop()

    def load_program(self):
        filename, filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open program", "./tests", "Program file (*.yaml)")
        if not filename:
            self.status_label.setText("Not loaded")
            return
        try:
            loaded = yaml.load(pathlib.Path(filename).read_text(), yaml.Loader)
        except:
            raise
        else:
            generator = ProgramGenerator(loaded)
            with open("./tests/parsed.txt", "w") as fd:
                for time_, values in generator.parse_program_to_queue():
                    fd.write(f"{time_}, {values}\n")
            self.runner = ProgramRunner(
                generator, self.settings.get_new_ms,
                self.measurement_widget.get_sensor_types_list,
                self.measurement_widget.get_convert_funcs,
                self.settings.get_variables()[2],
                self.gasstate_widget.send_state,
                self.get_checkbox_state,
                self.queue)


class ProgramRunner:

    def __init__(self, program_generator: ProgramGenerator, get_ms_method,
                 get_sensor_types_list, get_convert_funcs, multirange,
                 send_gasstate_func,
                 checkbox_state,
                 queue):
        self.stopped = True
        self.program_generator = program_generator
        self.program = self.program_generator.parse_program_to_queue()
        self.get_ms_method = get_ms_method
        self.get_sensor_types_list = get_sensor_types_list
        self.convert_funcs = get_convert_funcs("R")
        self.convert_funcs_2 = get_convert_funcs("V")
        self.multirange: bool = multirange
        self.send_gasstate_func = send_gasstate_func
        self.checkbox_state = checkbox_state
        self.thread = None
        self.queue = queue

    def start(self):
        self.stopped = False
        self.thread = threading.Thread(target=self.cycle)
        self.thread.start()

    def stop(self):
        self.stopped = True

    def cycle(self):
        ms: MS_Uni = self.get_ms_method()
        time_0 = time()
        time_sleep = self.program_generator.program.settings.step / 100
        sensor_types_list = self.get_sensor_types_list()
        sensor_states = [
                            1,
                        ] * 12
        sensor_stab_up_states = [
                                    True,
                                ] * 12
        sensor_stab_down_states = [
                                      True,
                                  ] * 12
        while not self.stopped:
            time_next, (temperatures, gas_state, stage_num,
                        stage_type) = next(self.program)
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
                                      stage_type, sensor_states))
                    self.analyze_us(ms, us, sensor_states,
                                    sensor_stab_up_states,
                                    sensor_stab_down_states)
        self.clear_ms_state(ms)

    @staticmethod
    def clear_ms_state(ms: MS_Uni):
        ms.clear_state()
        ms.close()

    def convert_to_resistances(self, temperatures):
        return [func(t) for t, func in zip(temperatures, self.convert_funcs)]

    def convert_to_voltages(self, temperatures):
        return [func(t) for t, func in zip(temperatures, self.convert_funcs_2)]

    def analyze_us(self, ms: MS_Uni, us: np.ndarray, sensor_states: list,
                   sensor_stab_up_states: list, sensor_stab_down_states: list):
        if self.multirange:
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


class AnswerPlotWidget(pg.PlotWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensor_number = 12
        self.number_of_dots = 1200
        self.rs = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.us = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.times = np.empty(shape=(self.number_of_dots,))
        self.drawing_index = 0
        legend = pg.LegendItem(offset=(-10, 10), labelTextColor=pg.mkColor("#FFFFFF"), brush=pg.mkBrush(pg.mkColor("#111111")))
        legend.setParentItem(self.getPlotItem())
        self.plot_data_items = [
            self.plot([0], [0], name=f"Sensor {i + 1}") for i in range(self.sensor_number)
        ]
        for idx, (plot_data_item, color) in enumerate(zip(self.plot_data_items, colors_for_lines)):
            plot_data_item.setPen(pg.mkPen(pg.mkColor(color), width=2))
            legend.addItem(plot_data_item, f"Sensor {idx + 1}")
        self.lock = threading.Lock()

    def hold_answer(self, answer):
        with self.lock:
            us, rs, time_next= answer
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
