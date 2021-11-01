import numpy as np
from scipy.optimize import curve_fit
from serial.tools.list_ports import comports
import sys

from sensor_system import MS12, MS4

from PySide2 import QtWidgets, QtCore, QtGui
from pyside_constructor_widgets.widgets import ComPortWidget
import logging
import matplotlib as mpl
from matplotlib import figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT

logger = logging.getLogger(__name__)

rs = np.array([5e8, 1e8, 1e7, 1e6, 1e5, 5.1e4, 1e4, 1e3])
r4_str_values = ["100 kOhm", "1.1 MOhm", "11.1 MOhm"]
r4_combobox_dict = dict(zip(r4_str_values, (1e5, 1.1e6, 1.11e7)))
r4_range_dict = dict(zip(r4_str_values, (1, 2, 3)))

r_labels_str = tuple(map("{:1.2e}".format, rs))

def get_float(x):
    try:
        return float(x)
    except:
        return 0

class MS_Uni():
    def __init__(self, sensor_number, port):
        self.sensors_number = sensor_number
        if sensor_number == 4:
            self.ms = MS4(port)
        elif sensor_number == 12:
            self.ms = MS12(port)
        else:
            raise Exception("Wrong port number")

    def send_measurement_range(self, values):
        self.ms.send_measurement_range(values[:self.sensors_number])
        self.ms.recieve_measurement_range_answer()

    def full_request(self, values):
        return self.ms.full_request(values[:self.sensors_number], self.ms.REQUEST_U)[0]

class MainWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.settings_widget = EquipmentSettings()
        layout.addWidget(self.settings_widget)
        hbox_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(hbox_layout)
        for _ in range(4):
            hbox_layout.addWidget(OneSensorFrame(self, self.settings_widget))



class PlusWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.label = QtWidgets.QPushButton(icon=QtGui.QIcon("icons/plus.png"))
        self.label.setMinimumSize(20, 20)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label)
        layout.setAlignment(self.label, QtCore.Qt.AlignCenter)
        self.setLayout(layout)


class OneSensorFrame(QtWidgets.QWidget):
    def __init__(self, master, settings, *args, **kwargs):
        super(OneSensorFrame, self).__init__(master, *args, **kwargs)
        self.settings = settings
        self.labels = []

        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)
        self.setLayout(layout)

        row = 0

        r4_widget = QtWidgets.QComboBox()
        r4_widget.addItems(tuple(r4_combobox_dict.keys()))
        r4_widget.setEditable(False)
        layout.addWidget(r4_widget, row, 1)
        layout.addWidget(QtWidgets.QLabel("R4: "), row, 0)
        row += 1

        sensor_widget = QtWidgets.QComboBox()
        sensor_widget.addItems(tuple(map(str, range(1, 13))))
        sensor_widget.setEditable(False)
        layout.addWidget(sensor_widget, row, 1)
        layout.addWidget(QtWidgets.QLabel("Sensor #: "), row, 0)
        row += 1
        

        entries = dict(
            zip(r_labels_str, (QtWidgets.QLineEdit(self) for i in range(len(r_labels_str)))))

        def get_func(index):
            def measure_u():
                com_port, sensor_number = self.settings.get_variables()
                print(f"{com_port}, {r4_widget.currentText()}, {sensor_widget.currentText()}")
                ms = MS_Uni(sensor_number=sensor_number, port=com_port)
                ms.send_measurement_range((r4_range_dict[r4_widget.currentText()],) * 12)

                answers = [ms.full_request((0,) * 12) for _ in range(5)]
                try:
                    entries[index].setText("{:2.5f}".format(sum([answer[int(sensor_widget.currentText()) - 1] for answer in answers])/5))
                except IndexError:
                    print("No sensor there")

            return measure_u

        buttons = dict(zip(r_labels_str,
                           (QtWidgets.QPushButton(icon=QtGui.QIcon("icons/load.png")) for i in
                            range(len(r_labels_str)))))

        for idx, (label, entry, button) in enumerate(zip(r_labels_str, entries.values(), buttons.values())):
            button.clicked.connect(get_func(idx))
            button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            label_widget = QtWidgets.QLabel(label)
            self.labels.append(label_widget)
            layout.addWidget(label_widget, row, 0)
            layout.addWidget(entry, row, 1)
            layout.addWidget(button, row, 2)
            row += 1


        result_widget_1 = QtWidgets.QLineEdit()
        result_widget_2 = QtWidgets.QLineEdit()
        result_widget_1.setReadOnly(True)
        result_widget_2.setReadOnly(True)

        slice_widget_1 = QtWidgets.QLineEdit(text="0")
        slice_widget_1.setValidator(QtGui.QIntValidator(0, 8))
        slice_widget_2 = QtWidgets.QLineEdit(text="8")
        slice_widget_2.setValidator(QtGui.QIntValidator(0, 8))

        rs1_widget = QtWidgets.QLineEdit(text="3.004")
        rs1_widget.setValidator(QtGui.QDoubleValidator())
        rs2_widget = QtWidgets.QLineEdit(text="1.991")
        rs2_widget.setValidator(QtGui.QDoubleValidator())

        def click_calc_button():
            k = 4.068

            def f(u, rs1, rs2):
                r4 = r4_combobox_dict[r4_widget.currentText()]
                return (rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4
            
            try:
                left_slice = int(slice_widget_1.text())
                right_slice = int(slice_widget_2.text())
                rs1 = float(rs1_widget.text())
                rs2 = float(rs2_widget.text())
            except ValueError:
                logger.error("You should enter some values in these fields")
                return None
            else:
                x = tuple(entries[i].text() for i in r_labels_str)
                x = tuple(map(get_float, x))
                y = rs
                x, y = x[left_slice:right_slice], y[left_slice:right_slice]
                popt, _ = curve_fit(f, x, y, p0=(rs1, rs2))
                result_widget_1.setText("{:2.6f}".format(popt[0]))
                result_widget_2.setText("{:2.6f}".format(popt[1]))

                PlotWidget(self, x, y, f, popt)

        calc_button = QtWidgets.QPushButton(text="Calc coeffs")
        calc_button.clicked.connect(click_calc_button)

        layout.addWidget(slice_widget_1, row, 0)
        layout.addWidget(slice_widget_2, row, 1)
        row+=1

        layout.addWidget(rs1_widget, row, 0)
        layout.addWidget(rs2_widget, row, 1)
        row += 1

        layout.addWidget(calc_button, row, 0)
        layout.addWidget(result_widget_1, row, 1)
        row += 1
        layout.addWidget(result_widget_2, row, 1)


class EquipmentSettings(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.comport_widget = ComPortWidget()
        layout.addWidget(self.comport_widget)
        self.sensor_number_widget = QtWidgets.QComboBox()
        layout.addWidget(self.sensor_number_widget)
        self.sensor_number_widget.addItems(("4", "12"))
        self.sensor_number_widget.setCurrentText("4")

    def get_variables(self):
        return self.comport_widget.text(), self.sensor_number_widget.currentText()

class PlotWidget(QtWidgets.QWidget):
    def __init__(self, parent, x, y, f, popt):
        super().__init__(parent, f=QtCore.Qt.Tool)
        fig = figure.Figure()
        ax = fig.add_subplot(1, 1, 1)
        canvas = FigureCanvasQTAgg(figure=fig)
        layout=QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(canvas)
        toolbox = NavigationToolbar2QT(canvas, self)
        layout.addWidget(toolbox)
        ax.set_yscale("log")
        ax.set_xlabel("Voltage, V")
        ax.set_ylabel("log(R)")
        self.setWindowTitle("Visualization of regression")
        ax.scatter(x, y)
        linspace = np.linspace(0, 5)
        ax.plot(linspace, f(linspace, *popt))
        canvas.draw()
        self.show()

def main():
    app = QtWidgets.QApplication()

    logging.basicConfig(level=logging.DEBUG)

    window = MainWidget()
    window.setWindowTitle("Sensor calibrator")
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
