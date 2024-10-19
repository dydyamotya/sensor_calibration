import logging
import pathlib
from typing import TYPE_CHECKING

import yaml
from PySide2 import QtCore, QtWidgets
from PySide2.QtCore import QTimer, Signal
from PySide2.QtWidgets import QFrame

from misc import Lamp
from operation_utils.program_generator import ProgramGenerator
from operation_utils.queue_runner import QueueRunner
from operation_utils.program_runner import ProgramRunner
from operation_utils.queues_holder import QueuesHolder
from operation_utils.operation_plot_widget import OperationalPlotWidget

if TYPE_CHECKING:
    from equipment_settings import EquipmentSettings
    from main_window import MyMainWindow
    from measurement import MeasurementWidget

logger = logging.getLogger(__name__)

def format_floats(floats_list):
    return (f"{x:5.5f}" for x in floats_list)


class OperationWidget(QtWidgets.QWidget):
    stop_signal = Signal()
    running_signal = Signal()

    def __init__(
        self,
        parent: "MyMainWindow",
        global_settings: QtCore.QSettings,
        measurement_widget: "MeasurementWidget",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.parent_py = parent
        self.global_settings = global_settings
        self.measurement_widget = measurement_widget
        self.gasstate_widget = parent.gasstate_widget
        self.runner = None
        self.generator = None
        self.queues_holder = QueuesHolder()
        save_folder = self.global_settings.value(
            "operation_widget_save_path", "./tests"
        )
        self.queue_runner = QueueRunner(
            self.queues_holder.add_new_queue(),
            self.measurement_widget.get_voltage_to_resistance_funcs,
            self.measurement_widget.get_multirange_status,
            save_folder,
        )
        self.settings: EquipmentSettings = self.parent_py.settings_widget
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
        self.plot_widget = OperationalPlotWidget(self)
        self.plot_widget.set_sensor_number(sensor_number)

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
            if self.runner is not None and not self.runner.isStopped():
                msg_box = QtWidgets.QMessageBox()
                msg_box.setWindowTitle("Вы уверены?")
                msg_box.setText("Проводится эксперимент, завершить его и начать новый?")
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
                ret = msg_box.exec_()
                if ret == QtWidgets.QMessageBox.No:
                    return
            self.refresh_state()
            self.load_program_button.setEnabled(False)
            comport, sensor_number, multirange, *_ = self.settings.get_variables()

            (
                critical_top,
                critical_bottom,
            ) = self.measurement_widget.get_critical_sensors_voltages()

            self.runner = ProgramRunner(
                self.generator,
                self.settings.get_new_ms,
                self.measurement_widget.get_sensor_types_list,
                self.measurement_widget.get_convert_funcs,
                self.get_range_mode_settings(),
                multirange,
                self.gasstate_widget.send_gasstate_signal,
                self.get_checkbox_state,
                self.queues_holder,
                self.stop_signal,
                self.running_signal,
                sensor_number,
                critical_top,
                critical_bottom,
            )
            self.plot_widget.clear_plot()
            self.runner.start()
            self.queue_runner.start()
            self.timer_plot.start()
            self.values_set_timer.setInterval(
                int(self.generator.program.settings.step * 500)
            )
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
            self,
            "Open program",
            self.global_settings.value("operation_widget_programs_path", "./tests"),
            "Program file (*.yaml)",
        )
        if not filename:
            self.load_label.setText("Not loaded")
            self.load_label.setStyleSheet("background-color:pink")
            return
        (
            self.global_settings.setValue(
                "operation_widget_programs_path",
                pathlib.Path(filename).parent.as_posix(),
            ),
        )
        try:
            loaded = yaml.load(pathlib.Path(filename).read_text(), yaml.Loader)
        except:
            self.load_label.setText("Not loaded")
            self.load_label.setStyleSheet("background-color:pink")
            raise
        else:
            self.generator = ProgramGenerator(loaded)
            self.load_label.setText("Loaded")
            self.load_label.setStyleSheet("background-color:palegreen")

    def set_values_on_meas_widget(self):
        results = self.queue_runner.get_meas_tuple()
        if results is not None:
            self.measurement_widget.set_results_values_to_widgets(*results)

    def turn_on_working_lines(self):
        if self.plot_widget:
            self.plot_widget.set_visible_lines_by_flags(self.measurement_widget.get_working_widgets())

    def turn_on_all_lines(self):
        if self.plot_widget:
            self.plot_widget.set_all_lines_visible()

    def turn_off_all_lines(self):
        if self.plot_widget:
            self.plot_widget.set_all_lines_invisible()

    def on_running_signal(self):
        self.lamp.set_running()



