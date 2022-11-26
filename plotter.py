from PySide2 import QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np
import pandas as pd

colors_for_lines = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22',
                    '#17becf', "#DDDDDD", "#00FF00"]

class ProgramPlotter(QtWidgets.QWidget):
    def __init__(self, program_generator, *args, **kwargs):
        super(ProgramPlotter, self).__init__(*args, f=QtCore.Qt.Window, **kwargs)
        self.program = program_generator
        time_next, (temperatures, gas_state, stage_num,
                    stage_type) = next(self.program)


class ExperimentPlotter(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(ExperimentPlotter, self).__init__(*args, f=QtCore.Qt.Window, **kwargs)
        self.setWindowTitle("Experiment plotter")
        self.setMinimumSize(700, 500)
        main_layout = QtWidgets.QVBoxLayout(self)
        controls_layout = QtWidgets.QVBoxLayout()
        import_groupbox = QtWidgets.QGroupBox()
        import_groupbox.setTitle("Import")
        import_groupbox_layout = QtWidgets.QHBoxLayout(import_groupbox)

        open_experiment_file_button = QtWidgets.QPushButton("Open experiment")
        open_experiment_file_button.clicked.connect(self.open_experiment_file)
        import_groupbox_layout.addWidget(open_experiment_file_button)

        import_groupbox_layout.addStretch()
        controls_layout.addWidget(import_groupbox)
        main_layout.addLayout(controls_layout)
        self.plot_widget = pg.PlotWidget(self)
        plot_item = self.plot_widget.getPlotItem()
        plot_item.showGrid(x=True, y=True)
        plot_item.setLogMode(y=True)
        self.legend_item = pg.LegendItem(offset=(-10, 10), labelTextColor=pg.mkColor("#FFFFFF"),
                               brush=pg.mkBrush(pg.mkColor("#111111")))
        self.legend_item.setParentItem(self.plot_widget.getPlotItem())
        main_layout.addWidget(self.plot_widget)

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())

    def open_experiment_file(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, " Open experiment file", ".", "Experiment File (*.txt)"
        )
        if not filename:
            return
        data = pd.read_csv(filename, delimiter="\t", index_col=0, skiprows=1)
        self.legend_item.clear()
        self.plot_widget.getPlotItem().clear()
        number_of_sensors = len(tuple(col for col in data.columns if col.startswith("State")))
        for i, (sensor_idx, color) in enumerate(zip(range(number_of_sensors), colors_for_lines)):
            plot_data_item = self.plot_widget.plot(x=data.index, y=data[f"Rs{sensor_idx}"], pen=pg.mkPen(pg.mkColor(color), width=2))
            self.legend_item.addItem(plot_data_item, f"Sensor {i + 1}")

