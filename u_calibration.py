import configparser
import datetime

from yaml import dump
import numpy as np
from scipy.optimize import curve_fit
import platform

from PySide2 import QtWidgets, QtCore, QtGui
import logging
import pyqtgraph as pg
from models import SensorPosition
from misc import clear_layout
import pathlib

logger = logging.getLogger(__name__)

rs = np.array([2e10, 1e10, 2.1e9, 5e8, 1e8, 1e7, 1e6, 1e5, 5.1e4, 1e4, 1e3])
r_labels_str = tuple(map("{:1.2e}".format, rs))



def get_float(x):
    try:
        return float(x)
    except:
        return 0


class UCalibrationWidget(QtWidgets.QWidget):

    def __init__(self, py_parent, debug_level, global_settings, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_level = debug_level
        self.py_parent = py_parent
        self.settings_widget = py_parent.settings_widget
        self.global_settings = global_settings
        self.import_widget = self.py_parent.import_widget
        self.settings_widget.calibration_redraw_signal.connect(self._init_ui)
        QtWidgets.QVBoxLayout(self)
        self._init_ui()

    def _init_ui(self):
        clear_layout(self.layout())
        self.setLayout(self.layout())
        self.widgets = []


        hbox_layout = QtWidgets.QHBoxLayout()
        self.layout().addLayout(hbox_layout)
        for _ in range(3):
            widget = OneSensorFrame(self, self.settings_widget, self.debug_level,
                           self.global_settings, self.import_widget)
            hbox_layout.addWidget(widget)
            self.widgets.append(widget)

        clear_all_button = QtWidgets.QPushButton("Очистить")
        clear_all_button.clicked.connect(self.clear_all)
        hbox_layout.addWidget(clear_all_button)
        hbox_layout.addStretch()

    def clear_all(self):
        msgbox = QtWidgets.QMessageBox()
        msgbox.setText("Уверены, что хотите очистить поля?")
        msgbox.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
        ret = msgbox.exec_()
        if ret == QtWidgets.QMessageBox.Yes:
            for widget in self.widgets:
                for entry in widget.entries.values():
                    entry.clear()


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

    def __init__(self, master, settings, debug_level, global_settings,
                 import_widget, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.settings_widget = settings

        r4_str_values, r4_combobox_dict, r4_range_dict = self.settings_widget.get_r4_data()
        self.import_widget = import_widget
        self.debug_level = debug_level
        self.global_settings = global_settings
        self.labels = []
        main_layout = QtWidgets.QVBoxLayout(self)
        layout = QtWidgets.QGridLayout()
        main_layout.addLayout(layout)
        main_layout.addStretch()
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)

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
            zip(r_labels_str,
                (QtWidgets.QLineEdit(self) for i in range(len(r_labels_str)))))

        def get_func(index):

            def measure_u():
                ms = self.settings_widget.get_new_ms()
                if ms is not None:
                    try:
                        if r4_widget.currentText() in r4_str_values:
                            ms.send_measurement_range(
                                (r4_range_dict[r4_widget.currentText()], ) * 12)
                        else:
                            pass

                        answers = [
                            ms.full_request((0, ) * 12)[0] for _ in range(15)
                        ]
                        try:
                            self.entries[r_labels_str[index]].setText(
                                "{:2.5f}".format(
                                    sum([
                                        answer[int(sensor_widget.currentText()) -
                                               1] for answer in answers[5:]
                                    ]) / 10))
                        except IndexError:
                            logger.error("No sensor there")
                    except:
                        ms.close()

            return measure_u

        buttons = dict(
            zip(r_labels_str,
                (QtWidgets.QPushButton(icon=QtGui.QIcon("icons/load.png"))
                 for i in range(len(r_labels_str)))))

        for idx, (label, entry, button) in enumerate(
                zip(r_labels_str, self.entries.values(), buttons.values())):
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
        slice_widget_1.setValidator(QtGui.QIntValidator(0, rs.shape[0]))
        slice_widget_2 = QtWidgets.QLineEdit(text=str(rs.shape[0]))
        slice_widget_2.setValidator(QtGui.QIntValidator(0, rs.shape[0]))

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
                return np.log10((rs1 - rs2) * r4 /
                                ((2.5 + 2.5 * k - u) / k - rs2) - r4)

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
                popt, _ = curve_fit(f_logd, x, np.log10(y), p0=(rs1, rs2))
                result_widget_1.setText("{:2.6f}".format(popt[0]))
                result_widget_2.setText("{:2.6f}".format(popt[1]))

                PlotWidget(self, x, y, f, popt, self.global_settings,
                           r4_widget.currentText(),
                           sensor_widget.currentText(), self.settings_widget,
                           self.import_widget)

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
        test_values = [
            "4.64",
            "4.63",
            "4.62",
            "4.61042", "4.57307", "4.20415", "2.41583", "0.75001", "0.58466",
            "0.43554", "0.40117"
        ]
        for widget, text in zip(self.entries.values(), test_values):
            widget.setText(text)


class PlotWidget(QtWidgets.QWidget):

    def __init__(self, parent, x, y, func, popt, global_settings, r4,
                 sensor_num, settings_widget, import_widget):
        super().__init__(parent, f=QtCore.Qt.Tool)

        self.global_settings = global_settings
        self.settings_widget = settings_widget
        self.r4_str_values, *_ = self.settings_widget.get_r4_data()
        self.import_widget = import_widget
        self.r4 = r4
        self.sensor_num = sensor_num
        self.x = x
        self.y = y
        self.popt = popt

        gl_widget = pg.GraphicsLayoutWidget()
        p1 = gl_widget.addPlot()
        gl_widget.nextRow()
        p2 = gl_widget.addPlot()

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(gl_widget)

        buttons_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(buttons_layout)

        accept_button = QtWidgets.QPushButton("Accept")
        buttons_layout.addWidget(accept_button)
        accept_button.clicked.connect(self.on_accept)

        cancel_button = QtWidgets.QPushButton("Cancel")
        buttons_layout.addWidget(cancel_button)
        cancel_button.clicked.connect(self.close)

        p1.setLogMode(y=True)
        p1.setLabel("bottom", "Voltage, V")
        p1.setLabel("left", "log(R)")
        self.setWindowTitle("Visualization of regression")
        p1.plot(x, y, symbol="o", pen=None)
        linspace = np.linspace(0, 5, num=10000)
        p1.plot(linspace, func(linspace, *popt))
        p2.setXLink(p1)
        p2.plot(x, np.abs((y - func(np.array(x), *popt)) / y), symbol="o")
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        self.move(screen.width() / 2, screen.height() / 2)
        self.show()

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()

    def on_accept(self):
        *_, machine_id = self.settings_widget.get_variables(
        )
        SensorPosition.create(machine=machine_id,
                              sensor_num=self.sensor_num,
                              r4=self.r4,
                              rs_u1=self.popt[0],
                              rs_u2=self.popt[1],
                              k=4.068,
                              x=list(self.x),
                              y=list(self.y))
        self.import_widget.configure_load_file(self.sensor_num, self.r4,
                                               self.popt[0], self.popt[1])
        self.settings_widget.redraw_signal.emit(machine_id)

    def save_to_file(self):
        self.global_settings.beginGroup("DeviceParameters")
        sensor_num = int(self.sensor_num)
        x = dump(list(self.x), default_flow_style=True)
        y = dump(self.y.tolist(), default_flow_style=True)
        if self.r4 in self.r4_str_values:

            r4_index = self.r4_str_values.index(self.r4) + 1
            self.global_settings.setValue(f"Rs_U1_{sensor_num}_{r4_index}",
                                          float(self.popt[0]))
            self.global_settings.setValue(f"Rs_U2_{sensor_num}_{r4_index}",
                                          float(self.popt[1]))
            self.global_settings.setValue(f"X_{sensor_num}_{r4_index}", x)
            self.global_settings.setValue(f"Y_{sensor_num}_{r4_index}", y)
        else:
            self.global_settings.setValue(f"Rs_U1_{sensor_num}", self.popt[0])
            self.global_settings.setValue(f"Rs_U2_{sensor_num}", self.popt[1])
            self.global_settings.setValue(f"X_{sensor_num}", x)
            self.global_settings.setValue(f"Y_{sensor_num}", y)
        self.global_settings.setValue(f"ku_{sensor_num}", 4.068)
        self.global_settings.endGroup()
        self.close()


class ImportCalibrationWidget(QtWidgets.QWidget):

    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)
        layout = QtWidgets.QVBoxLayout(self)
        self.setWindowTitle("Import")
        self.global_settings = global_settings
        self.settings_widget = self.parent().settings_widget
        self.import_button = QtWidgets.QPushButton(
            "Import parameters of positions")
        self.import_button.clicked.connect(self.import_parameters)
        self.r4_str_values, *_ = self.settings_widget.get_r4_data()
        layout.addWidget(self.import_button)

        hbox_layout = QtWidgets.QHBoxLayout()
        layout.addLayout(hbox_layout)
        self.load_file_lineedit = QtWidgets.QLineEdit()
        self.load_file_lineedit.setReadOnly(True)
        self.load_file_button = QtWidgets.QPushButton("...")
        self.load_file_button.clicked.connect(self.set_load_file)
        hbox_layout.addWidget(self.load_file_lineedit)
        hbox_layout.addWidget(self.load_file_button)

        layout.addStretch()

    def set_load_file(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load parameters", self.global_settings.value("import_calibration_widget", "./tests"), "Init files (*.ini)")
        if not filename:
            message_box = QtWidgets.QMessageBox()
            message_box.setText("No file selected")
            message_box.exec_()
            return

        self.global_settings.setValue("import_calibration_widget", pathlib.Path(filename).parent.as_posix())
        self.load_file_lineedit.setText(filename)

    def configure_load_file(self, sens_num, r4, rs_u1, rs_u2):

        ded = 0

        def deduplicate(x):
            nonlocal ded
            if x.lower() == "rn10_min":
                ded = ded + 1
                return x.lower() + str(ded)
            else:
                return x

        config = configparser.ConfigParser()
        config.optionxform = deduplicate
        if self.load_file_lineedit.text():
            message_box = QtWidgets.QMessageBox()
            idx_r4 = self.r4_str_values.index(r4)
            config.read(self.load_file_lineedit.text())
            if "Device parameters" not in config:
                config["Device parameters"] = {}
            config["Device parameters"][
                f"Rs_U1_{sens_num}_{idx_r4+1}"] = str(float(rs_u1)).replace(
                    ".", ",")
            config["Device parameters"][
                f"Rs_U2_{sens_num}_{idx_r4+1}"] = str(float(rs_u2)).replace(
                    ".", ",")
            config["Device parameters"][f"ku_{sens_num}"] = "4,068"
            with open(self.load_file_lineedit.text(), "w") as fd:
                config.write(fd)
            message_box.setText("Sensor position data writen to ms.ini")
            message_box.exec_()

    def import_parameters(self):
        filename, filters = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load parameters",
            self.global_settings.value("import_calibration_widget", "./tests"), "Init files (*.ini)")
        if not filename:
            return

        self.global_settings.setValue("import_calibration_widget", pathlib.Path(filename).parent.as_posix())

        config = configparser.ConfigParser()


        ded = 0

        def deduplicate(x):
            nonlocal ded
            if x.lower() == "rn10_min":
                ded = ded + 1
                return x.lower() + str(ded)
            else:
                return x

        config.optionxform = deduplicate
        config.read(filename)

        _, sensor_number, _, _, machine_id = self.settings_widget.get_variables(
        )
        not_added = []
        for sens_num in range(sensor_number):
            for idx_r4, r4 in enumerate(self.r4_str_values):
                try:
                    rs_u1 = config["Device parameters"][
                        f"Rs_U1_{sens_num+1}_{idx_r4+1}"].replace(",", ".")
                    rs_u2 = config["Device parameters"][
                        f"Rs_U2_{sens_num+1}_{idx_r4+1}"].replace(",", ".")
                except KeyError:
                    not_added.append((sens_num, r4))
                else:
                    SensorPosition.create(machine=machine_id,
                                          sensor_num=sens_num + 1,
                                          r4=r4,
                                          rs_u1=float(rs_u1),
                                          rs_u2=float(rs_u2),
                                          k=4.068,
                                          x=[],
                                          y=[])
        message_box = QtWidgets.QMessageBox()
        if len(not_added) > 0:
            text = "\n".join(f"{sens_num} {r4}" for sens_num, r4 in not_added)
        else:
            text = "Everything imported"
        message_box.setText(text)
        message_box.exec_()
        self.settings_widget.redraw_signal.emit(machine_id)

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
