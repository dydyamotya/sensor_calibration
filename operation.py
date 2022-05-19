from PySide2 import QtWidgets
from misc import clear_layout
from sensor_system import MS_Uni, MS_ABC
import pathlib
import yaml
import logging
from program_generator import ProgramGenerator, ProgramGeneratorException
from time import time, sleep
import numpy as np
import threading
import pyqtgraph as pg


logger = logging.getLogger(__name__)

class OperationWidget(QtWidgets.QWidget):
    def __init__(self, parent, log_level, global_settings, measurement_widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_py = parent
        self.measurement_widget = measurement_widget
        self.gasstate_widget = parent.gasstate_widget
        self.runner = None
        self.settings = self.parent_py.settings_widget
        self.settings.redraw_signal.connect(self.init_ui)
        QtWidgets.QVBoxLayout(self)
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
        layout.addWidget(start_button)
        layout.addWidget(stop_button)
        start_button.clicked.connect(self.start)
        stop_button.clicked.connect(self.stop)

        self.plot_widget = AnswerPlotWidget(self)
        layout.addWidget(self.plot_widget)

    def start(self):
        if self.runner:
            self.runner.start()

    def stop(self):
        if self.runner:
            self.runner.stop()

    def load_program(self):
        filename, filter = QtWidgets.QFileDialog.getOpenFileName(self, "Open program", "./tests", "Program file (*.yaml)")
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
            self.runner = ProgramRunner(generator,
                                        self.settings.get_new_ms,
                                        self.measurement_widget.get_sensor_types_list,
                                        self.measurement_widget.get_convert_funcs,
                                        self.settings.get_variables()[2],
                                        self.gasstate_widget.send_state)
            self.runner.log_all_data = self.plot_all_data

    def plot_all_data(self, *args, **kwargs):
        logger.debug(str(args))
        self.plot_widget.plot_answer(args)


class ProgramRunner:
    def __init__(self, program_generator: ProgramGenerator, get_ms_method, get_sensor_types_list, get_convert_funcs, multirange, send_gasstate_func):
        self.stopped = True
        self.program_generator = program_generator
        self.program = self.program_generator.parse_program_to_queue()
        self.get_ms_method = get_ms_method
        self.get_sensor_types_list = get_sensor_types_list
        self.convert_funcs = get_convert_funcs()
        self.multirange: bool = multirange
        self.send_gasstate = send_gasstate_func
        self.thread = None

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
        sensor_states = [1, ] * 12
        sensor_stab_up_states = [True, ] * 12
        sensor_stab_down_states = [True, ] * 12
        while not self.stopped:
            time_next, (temperatures, gas_state, stage_num, stage_type) = next(self.program)
            time_next_plus_t0 = time_0 + time_next
            while time() < time_next_plus_t0:
                sleep(time_sleep)
            try:
                us, rs = ms.full_request(self.convert_to_resistances(temperatures),
                                 request_type=MS_ABC.REQUEST_R,
                                 sensor_types_list=sensor_types_list)
            except MS_ABC.MSException:
                self.clear_ms_state(ms)
                raise
            else:
                try:
                    self.send_gasstate_func(gas_state)
                except:
                    pass
                else:
                    self.log_all_data(us, rs, time_next_plus_t0, time_next, temperatures, gas_state, stage_num, stage_type, sensor_states)
                    self.analyze_us(ms, us, sensor_states, sensor_stab_up_states, sensor_stab_down_states)
        self.clear_ms_state(ms)

    @staticmethod
    def clear_ms_state(ms: MS_Uni):
        ms.clear_state()
        ms.close()

    def convert_to_resistances(self, temperatures):
        return [func(t) for t, func in zip(temperatures, self.convert_funcs)]

    def log_all_data(self, *args):
        logger.debug(str(args))

    def analyze_us(self, ms: MS_Uni, us: np.ndarray, sensor_states: list, sensor_stab_up_states: list, sensor_stab_down_states: list):
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
        self.rs = np.empty(shape=(self.sensor_number, 400))
        self.us = np.empty(shape=(self.sensor_number, 400))
        self.times = np.empty(shape=(400,))
        self.drawing_index = 0
        self.plot_data_items = [self.plot([0], [0]) for i in range(self.sensor_number)]

    def plot_answer(self, answer):
        us, rs, time_next_plus_t0, time_next, temperatures, gas_state, stage_num, stage_type, sensor_states = answer
        
        if self.drawing_index == 400:
            self.rs[:, :-1] = self.rs[:, 1:]
            self.us[:, :-1] = self.us[:, 1:]
            self.times[:-1] = self.times[1:]

        self.rs[:, self.drawing_index] = rs
        self.us[:, self.drawing_index] = us
        self.times[self.drawing_index] = time_next_plus_t0

        if self.drawing_index < 400:
            self.drawing_index += 1

        for plot_item, us_line, rs_line in zip(self.plot_data_items,
                self.us[:, :self.drawing_index],
                self.rs[:, :self.drawing_index]):
            plot_item.setData(x=self.times[:self.drawing_index], y=us_line)

