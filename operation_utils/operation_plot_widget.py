import pyqtgraph as pg
import numpy as np
from misc import colors_for_lines
import threading
import logging

from operation_utils.one_view import OneView

logger = logging.getLogger(__name__)


class OperationalPlotWidget(pg.GraphicsLayoutWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensor_number = 12
        self.number_of_dots = 1200

        self.heater_resistances = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.sensor_resistances = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.times = np.empty(shape=(self.number_of_dots,))
        self.drawing_index = 0
        
        self.sensor_resistances_one_view = OneView(self.addPlot(row=0, col=0),
                                       logy=True,
                                       sensor_number=self.sensor_number)
        self.heater_resistances_one_view = OneView(self.addPlot(row=0, col=1),
                                       logy=False,
                                       sensor_number=self.sensor_number)

        self.lock = threading.Lock()


    def set_sensor_number(self, sensor_number: int):
        self.sensor_number = sensor_number
        self.sensor_resistances_one_view.set_sensor_number(sensor_number)
        self.heater_resistances_one_view.set_sensor_number(sensor_number)
        self.clear_plot()

    def clear_plot(self):
        self.drawing_index = 0
        self.heater_resistances = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.sensor_resistances = np.empty(shape=(self.sensor_number, self.number_of_dots))
        self.times = np.empty(shape=(self.number_of_dots,))
        self.sensor_resistances_one_view.clear()
        self.heater_resistances_one_view.clear()


    def hold_answer(self, answer):
        with self.lock:
            sensor_resistances, heater_resistances, time_next = answer
            logger.debug(f"Start add dots {time_next}")

            if self.drawing_index == self.number_of_dots:
                self.heater_resistances[:, :-1] = self.heater_resistances[:, 1:]
                self.sensor_resistances[:, :-1] = self.sensor_resistances[:, 1:]
                self.times[:-1] = self.times[1:]
                self.heater_resistances[:, self.number_of_dots - 1] = heater_resistances
                self.sensor_resistances[:, self.number_of_dots - 1] = sensor_resistances
                self.times[self.number_of_dots - 1] = time_next
            else:
                self.heater_resistances[:, self.drawing_index] = heater_resistances
                self.sensor_resistances[:, self.drawing_index] = sensor_resistances
                self.times[self.drawing_index] = time_next

            if self.drawing_index < self.number_of_dots:
                self.drawing_index += 1
            logger.debug(f"End adding dots {time_next}")

    def plot_answer(self):
        logger.debug(f"Try plotting data, drawing_index = {self.drawing_index}")
        with self.lock:
            logger.debug(f"Plotting data, drawing_index = {self.drawing_index}")
            self.sensor_resistances_one_view.plot_data(self.times[: self.drawing_index],
                                                       self.sensor_resistances[:, : self.drawing_index])
            self.heater_resistances_one_view.plot_data(self.times[: self.drawing_index],
                                                       self.heater_resistances[:, : self.drawing_index])
            logger.debug(f"End plotting data, drawing_index = {self.drawing_index}")

    def set_visible_lines_by_flags(self, flags):
        self.sensor_resistances_one_view.set_visible_lines_by_flags(flags)
        self.heater_resistances_one_view.set_visible_lines_by_flags(flags)

    def set_all_lines_visible(self):
        flags = (True, ) * 12
        self.set_visible_lines_by_flags(flags)

    def set_all_lines_invisible(self):
        flags = (False, ) * 12
        self.set_visible_lines_by_flags(flags)
