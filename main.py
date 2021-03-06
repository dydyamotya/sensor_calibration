import numpy as np
from scipy.optimize import curve_fit
from serial.tools.list_ports import comports
import sys
import platform
from sensor_system import MS12, MS4, MS_Uni
from calibration import CalibrationProxyFrame

from PySide2 import QtWidgets, QtCore, QtGui
from pyside_constructor_widgets.widgets import ComPortWidget
import logging
import matplotlib as mpl
from matplotlib import figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
import argparse
logger = logging.getLogger(__name__)

from collections import UserDict

class ResistanseDict(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        else:
            try:
                return float(key)
            except ValueError:
                raise


rs = np.array([5e8, 1e8, 1e7, 1e6, 1e5, 5.1e4, 1e4, 1e3])
r4_str_values = ["100 kOhm", "1.1 MOhm", "11.1 MOhm"]
r4_combobox_dict = ResistanseDict(zip(r4_str_values, (1e5, 1.1e6, 1.11e7)))
r4_range_dict = dict(zip(r4_str_values, (1, 2, 3)))

r_labels_str = tuple(map("{:1.2e}".format, rs))



def get_float(x):
    try:
        return float(x)
    except:
        return 0



class MainWidget(QtWidgets.QWidget):
    def __init__(self, debug_level, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_level = debug_level
        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.settings_widget = EquipmentSettings()
        layout.addWidget(self.settings_widget)

        self.calibration_proxy_frame = CalibrationProxyFrame(self)
        layout.addWidget(self.calibration_proxy_frame)

        hbox_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(hbox_layout)
        for _ in range(3):
            hbox_layout.addWidget(OneSensorFrame(self, self.settings_widget, self.debug_level))


class PlusWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.label = QtWidgets.QPushButton(icon=QtGui.QIcon("icons/plus.png"))
        self.label.setMinimumSize(20, 20)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.label)
        layout.setAlignment(self.label, QtCore.Qt.AlignCenter)
        self.setLayout(layout)


class OneSensorFrame(QtWidgets.QWidget):
    def __init__(self, master, settings, debug_level, *args, **kwargs):
        super(OneSensorFrame, self).__init__(master, *args, **kwargs)
        self.settings = settings
        self.debug_level = debug_level
        self.labels = []

        layout = QtWidgets.QGridLayout()
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)
        self.setLayout(layout)

        row = 0

        r4_widget = QtWidgets.QComboBox()
        r4_widget.addItems(tuple(r4_combobox_dict.keys()))
        r4_widget.setEditable(True)
        layout.addWidget(r4_widget, row, 1)
        layout.addWidget(QtWidgets.QLabel("R4: "), row, 0)
        row += 1

        sensor_widget = QtWidgets.QComboBox()
        sensor_widget.addItems(tuple(map(str, range(1, 13))))
        sensor_widget.setEditable(False)
        layout.addWidget(sensor_widget, row, 1)
        layout.addWidget(QtWidgets.QLabel("Sensor #: "), row, 0)
        row += 1

        self.entries = dict(
            zip(r_labels_str, (QtWidgets.QLineEdit(self) for i in range(len(r_labels_str)))))

        def get_func(index):
            def measure_u():
                com_port, sensor_number, _ = self.settings.get_variables()
                logger.debug(
                    f"{com_port}, {r4_widget.currentText()}, {sensor_widget.currentText()}")
                ms = MS_Uni(sensor_number=sensor_number, port=com_port)
                try:
                    if r4_widget.currentText() in r4_str_values:
                        ms.send_measurement_range(
                            (r4_range_dict[r4_widget.currentText()],) * 12)
                    else:
                        pass

                    answers = [ms.full_request((0,) * 12)[0] for _ in range(15)]
                    try:
                        self.entries[r_labels_str[index]].setText("{:2.5f}".format(
                            sum([answer[int(sensor_widget.currentText()) - 1] for answer in answers[5:]])/10))
                    except IndexError:
                        print("No sensor there")
                except:
                    ms.close()


            return measure_u

        buttons = dict(zip(r_labels_str,
                           (QtWidgets.QPushButton(icon=QtGui.QIcon("icons/load.png")) for i in
                            range(len(r_labels_str)))))

        for idx, (label, entry, button) in enumerate(zip(r_labels_str, self.entries.values(), buttons.values())):
            button.clicked.connect(get_func(idx))
            button.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                 QtWidgets.QSizePolicy.Expanding)
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

        rs1_widget = QtWidgets.QLineEdit(text="3.2")
        rs2_widget = QtWidgets.QLineEdit(text="1.6")
        if platform.system() == "Linux":
            rs1_widget.setValidator(QtGui.QDoubleValidator())
            rs2_widget.setValidator(QtGui.QDoubleValidator())

        def click_calc_button():
            k = 4.068
            r4 = r4_combobox_dict[r4_widget.currentText()]

            def f(u, rs1, rs2):
                return (rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4

            def f_logd(u, rs1, rs2):
                return np.log10((rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4)

            try:
                left_slice = int(slice_widget_1.text())
                right_slice = int(slice_widget_2.text())
                rs1 = float(rs1_widget.text())
                rs2 = float(rs2_widget.text())
            except ValueError:
                logger.error("You should enter some values in these fields")
                return None
            else:
                x = tuple(self.entries[i].text() for i in r_labels_str)
                x = tuple(map(get_float, x))
                y = rs
                x, y = x[left_slice:right_slice], y[left_slice:right_slice]
                #popt, _ = curve_fit(f, x, y, p0=(rs1, rs2), bounds = ((2.9, 1.8), (3.2, 2.1)), method="dogbox")
                popt, _ = curve_fit(f_logd, x, np.log10(y), p0=(rs1, rs2))
                *_, separator = self.settings.get_variables()
                result_widget_1.setText("{:2.6f}".format(popt[0]).replace(".", "," if separator else "."))
                result_widget_2.setText("{:2.6f}".format(popt[1]).replace(".", "," if separator else "."))

                PlotWidget(self, x, y, f, popt)

        calc_button = QtWidgets.QPushButton(text="Calc coeffs")
        calc_button.clicked.connect(click_calc_button)


        layout.addWidget(slice_widget_1, row, 0)
        layout.addWidget(slice_widget_2, row, 1)
        row += 1

        layout.addWidget(rs1_widget, row, 0)
        layout.addWidget(rs2_widget, row, 1)
        row += 1

        layout.addWidget(calc_button, row, 0)
        layout.addWidget(result_widget_1, row, 1)
        row += 1

        if self.debug_level == logging.DEBUG:
            test_button = QtWidgets.QPushButton(text="Test values")
            test_button.clicked.connect(self.fill_with_test_data)
            layout.addWidget(test_button, row, 0)

        layout.addWidget(result_widget_2, row, 1)

    def fill_with_test_data(self):
        test_values = ["4.61042", "4.57307", "4.20415", "2.41583", "0.75001", "0.58466", "0.43554", "0.40117"]
        for widget, text in zip(self.entries.values(), test_values):
            widget.setText(text)



class EquipmentSettings(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.comport_widget = ComPortWidget()
        layout.addWidget(self.comport_widget)

        self.sensor_number_widget = QtWidgets.QComboBox()
        layout.addWidget(self.sensor_number_widget)

        self.separator_checkbox = QtWidgets.QCheckBox()
        layout.addWidget(self.separator_checkbox)

        self.sensor_number_widget.addItems(("4", "12"))
        self.sensor_number_widget.setCurrentText("12")

    def get_variables(self):
        return self.comport_widget.text(), int(self.sensor_number_widget.currentText()), self.separator_checkbox.isChecked()


class PlotWidget(QtWidgets.QWidget):
    def __init__(self, parent, x, y, f, popt):
        super().__init__(parent, f=QtCore.Qt.Tool)
        fig = figure.Figure()
        ax = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2, sharex=ax)
        canvas = FigureCanvasQTAgg(figure=fig)
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(canvas)
        toolbox = NavigationToolbar2QT(canvas, self)
        layout.addWidget(toolbox)
        ax.set_yscale("log")
        ax.set_xlabel("Voltage, V")
        ax.set_ylabel("log(R)")
        self.setWindowTitle("Visualization of regression")
        ax.scatter(x, y)
        linspace = np.linspace(0, 5, num=10000)
        ax.plot(linspace, f(linspace, *popt))
        ax2.plot(x, np.abs((y - f(np.array(x), *popt))/y), marker=".")
        fig.tight_layout()
        canvas.draw()
        self.show()

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()


def main():
    app = QtWidgets.QApplication()

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level)

    window = MainWidget(level)
    window.setWindowTitle("Sensor calibrator")
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
