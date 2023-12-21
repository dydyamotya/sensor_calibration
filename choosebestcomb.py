from PySide2 import QtWidgets
import logging
import pyqtgraph as pg
import math

logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
from itertools import combinations, product
import pathlib
import threading



def find_cos_theta(S1, S2):
    return np.dot(S1 / np.linalg.norm(S1),
                  S2 / np.linalg.norm(S2))


def generate_temperature_combinations(num_of_sensors, num_of_temperatures):
    for temp_combination in product(*(range(num_of_temperatures) for _ in range(num_of_sensors))):
        yield temp_combination


def generate_all_combinations(num_of_sensors, num_of_temperatures, num_of_gases, progress_bar):
    low_num = min(num_of_sensors, num_of_gases + 1)
    num_of_combs = sum(math.comb(num_of_sensors, i) * (num_of_temperatures ** i) for i in range(2, low_num))
    logger.debug(f"Number of combination {num_of_combs}")

    progress_bar.setMaximum(num_of_combs)
    already_done = 0
    for i in range(1, low_num):
        for comb in combinations(range(num_of_sensors), i + 1):
            for temp_combination in generate_temperature_combinations(len(comb), num_of_temperatures):
                already_done += 1
                progress_bar.setValue(already_done)
                yield comb, temp_combination


def G(S, combination, alpha, beta):
    s_comb, t_comb = combination
    s_pair_combinations, t_pair_combinations = combinations(s_comb, 2), combinations(t_comb, 2)
    c_n_2 = math.comb(len(s_comb), 2)
    scalar_sum = 0
    if c_n_2 > 0:
        for s_pair, t_pair in zip(s_pair_combinations, t_pair_combinations):
            scalar_sum += find_cos_theta(S[t_pair[0], :, s_pair[0]], S[t_pair[1], :, s_pair[1]])

        orthogonal_source = alpha * (1 - scalar_sum / c_n_2)
    else:
        orthogonal_source = 0

    absolute_source = beta * np.sum(
            np.max(np.vstack(tuple(S[t_index, :, s_index] for s_index, t_index in zip(s_comb, t_comb))), axis=0))

    return orthogonal_source + absolute_source


def collect_files_from_xlsx(path_to_folder):
    data = []
    sensor_names = []
    for file in pathlib.Path(path_to_folder).iterdir():
        data.append(pd.read_excel(file, index_col=0))
        sensor_names.append(file.stem)
    gases = data[0].columns
    temperatures = data[0].index
    return np.concatenate([data_slice.values[:, :, np.newaxis] for data_slice in data], axis=2), gases, sensor_names, temperatures


class ChooseBestCombinationOfSensorsWidget(QtWidgets.QWidget):

    def __init__(self, parent, log_level, global_settings,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_py = parent
        self.data = None
        logger.setLevel(log_level)
        self.global_settings = global_settings

        main_layout = QtWidgets.QVBoxLayout(self)

        path_to_files_layout = QtWidgets.QHBoxLayout()

        main_layout.addLayout(path_to_files_layout)

        self.path_to_files = QtWidgets.QLineEdit()
        path_to_files_button = QtWidgets.QPushButton("Choose path")

        path_to_files_button.clicked.connect(self.choose_path_to_files)

        path_to_files_layout.addWidget(self.path_to_files)
        path_to_files_layout.addWidget(path_to_files_button)
        path_to_files_layout.addStretch()

        parameters_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(parameters_layout)


        self.alpha_widget = QtWidgets.QLineEdit("1")
        self.beta_widget = QtWidgets.QLineEdit("0.0001")
        parameters_layout.addWidget(QtWidgets.QLabel("Alpha:"))
        parameters_layout.addWidget(self.alpha_widget)
        parameters_layout.addWidget(QtWidgets.QLabel("Beta:"))
        parameters_layout.addWidget(self.beta_widget)
        parameters_layout.addStretch()

        buttons_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(buttons_layout)

        calculate_button = QtWidgets.QPushButton("Рассчитать комбинации")
        calculate_button.clicked.connect(self.calculate_button_click_handler)

        buttons_layout.addWidget(calculate_button)

        self.progress_bar = QtWidgets.QProgressBar()
        main_layout.addWidget(self.progress_bar)

        table_plot_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(table_plot_layout)

        splitter = QtWidgets.QSplitter()
        self.table_widget = QtWidgets.QTableWidget(self)
        self.table_widget.setColumnCount(4)
        self.table_widget.setRowCount(100)
        self.table_widget.cellClicked.connect(self.cellClickedEventHandler)
        self.table_widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.MinimumExpanding)

        self.plot_widget = pg.GraphicsLayoutWidget()

        splitter.addWidget(self.table_widget)
        splitter.addWidget(self.plot_widget)
        table_plot_layout.addWidget(splitter)

    def choose_path_to_files(self):
        try:
            filename = QtWidgets.QFileDialog.getExistingDirectory(self,
                                                                  "Выберите путь, где лежат файлы сенсорных откликов",
                                                                  self.global_settings.value("choosebestcomb_path", "./tests"))
        except ValueError:
            pass
        else:
            self.global_settings.setValue("choosebestcomb_path", filename)
            self.path_to_files.setText(filename)

    def calculate_button_click_handler(self):
        self.calculate()

    def calculate(self):
        path_to_file = pathlib.Path(self.path_to_files.text())
        S, gases, sensors, temperatures = collect_files_from_xlsx(path_to_file)

        try:
            alpha = float(self.alpha_widget.text())
        except ValueError:
            alpha = 1

        try:
            beta = float(self.beta_widget.text())
        except ValueError:
            beta = 0.0001


        calculated_data = pd.DataFrame(((G(S, (comb, temp_combination), alpha, beta),
                                         (comb, temp_combination),
                                         ",".join(sensors[i] + " " + str(temperatures[j]) + "C" for i, j  in zip(comb, temp_combination)),
                                         ) for comb, temp_combination in
                                        generate_all_combinations(S.shape[2], S.shape[0], S.shape[1], self.progress_bar)),
                                       columns=["G", "Comb", "Name comb"]).sort_values(by="G", ascending=False)
        logger.debug("Combinations have been calculated")
        for iloc_index in range(100):
            self.table_widget.setItem(iloc_index, 0, QtWidgets.QTableWidgetItem(str(calculated_data.index[iloc_index])))
            self.table_widget.setItem(iloc_index, 1, QtWidgets.QTableWidgetItem(str(calculated_data.iloc[iloc_index, 0])))
            self.table_widget.setItem(iloc_index, 2, QtWidgets.QTableWidgetItem(str(calculated_data.iloc[iloc_index, 1])))
            self.table_widget.setItem(iloc_index, 3, QtWidgets.QTableWidgetItem(str(calculated_data.iloc[iloc_index, 2])))


        calculated_data.to_excel((path_to_file.parent / path_to_file.stem).with_suffix(".xlsx"))

        self.data = SData(S, gases, sensors, calculated_data, temperatures)

    def cellClickedEventHandler(self, row, column):
        if self.data is not None:
            self.plot_widget.clear()
            for sensor_index, temperature_index in zip(*self.data.data.iloc[row, 1]):
                plot_widget = self.plot_widget.addPlot(title=self.data.sensors[sensor_index] + " " + str(self.data.temperatures[temperature_index]) + "C")
                plot_widget.addItem(pg.BarGraphItem(x = range(len(self.data.gases)),
                                                    height=self.data.S[temperature_index,:,sensor_index],
                                                    width=0.5))


class SData():
    def __init__(self, S, gases, sensors, calculated_data, temperatures):
        self.S = S
        self.sensors = sensors
        self.gases = gases
        self.data = calculated_data
        self.temperatures = temperatures
