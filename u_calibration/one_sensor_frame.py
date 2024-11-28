import logging
import platform
import typing
import functools

import numpy as np
from PySide2 import QtGui, QtWidgets, QtCore
from superqt import QRangeSlider
from scipy.optimize import curve_fit
from u_calibration.plot_widget import PlotWidget

if typing.TYPE_CHECKING:
    from equipment_settings import EquipmentSettings

logger = logging.getLogger(__name__)

rs = np.array([2e10, 1e10, 2.1e9, 5e8, 1e8, 1e7, 1e6, 1e5, 5.1e4, 1e4, 1e3])
r_labels_str = tuple(map("{:1.2e}".format, rs))

def get_float(x):
    try:
        return float(x)
    except:
        return 0


class OneSensorFrame(QtWidgets.QWidget):
    def __init__(
        self,
        master,
        settings: "EquipmentSettings",
        debug_level,
        global_settings,
        import_widget,
        *args,
        **kwargs,
    ):
        super().__init__(master, *args, **kwargs)
        self.settings_widget = settings

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

        self.r4_widget = QtWidgets.QComboBox()
        if self.settings_widget.get_multirange():
            _, r4_combobox_dict, _ = self.settings_widget.get_r4_data()
            self.r4_widget.addItems(tuple(r4_combobox_dict.keys()))

        self.r4_widget.setEditable(True)
        layout.addWidget(self.r4_widget, row, 1)
        layout.addWidget(QtWidgets.QLabel("R4: "), row, 0)
        row += 1

        sensor_number = self.settings_widget.get_sensor_number()

        self.sensor_widget = QtWidgets.QComboBox()
        self.sensor_widget.addItems(tuple(map(str, range(1, sensor_number + 1))))
        self.sensor_widget.setEditable(False)
        layout.addWidget(self.sensor_widget, row, 1)
        layout.addWidget(QtWidgets.QLabel("Sensor #: "), row, 0)
        row += 1

        self.entries = dict(
            zip(
                r_labels_str,
                (QtWidgets.QLineEdit(self) for _ in range(len(r_labels_str))),
            )
        )

        buttons = dict(
            zip(
                r_labels_str,
                (
                    QtWidgets.QPushButton(icon=QtGui.QIcon("icons/load.png"), text="")
                    for _ in range(len(r_labels_str))
                ),
            )
        )

        for idx, (label, entry, button) in enumerate(
            zip(r_labels_str, self.entries.values(), buttons.values())
        ):
            button.clicked.connect(self.create_func_for_u_measuring(idx))
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
            )
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

        slice_widget = QRangeSlider(QtCore.Qt.Orientation.Horizontal)
        slice_widget.setMinimum(0)
        slice_widget.setMaximum(rs.shape[0] - 1)
        slice_widget.setTickPosition(QRangeSlider.TicksBelow)
        slice_widget.setTickInterval(1)
        slice_widget.setValue((0, rs.shape[0] - 1))
        slice_widget.valueChanged.connect(self.on_slice_widget_value_change)

        rs1_widget = QtWidgets.QLineEdit(text="3.2")
        rs2_widget = QtWidgets.QLineEdit(text="1.6")
        if platform.system() == "Linux":
            rs1_widget.setValidator(QtGui.QDoubleValidator())
            rs2_widget.setValidator(QtGui.QDoubleValidator())

        def click_calc_button():
            k = 4.068
            if self.settings_widget.get_multirange():
                r4 = r4_combobox_dict[self.r4_widget.currentText()]
            else:
                r4 = float(self.r4_widget.currentText())

            def f(u, rs1, rs2):
                return (rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4

            def f_logd(u, rs1, rs2):
                return np.log10((rs1 - rs2) * r4 / ((2.5 + 2.5 * k - u) / k - rs2) - r4)

            try:
                left_slice, right_slice = slice_widget.value()
                right_slice += 1
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

                PlotWidget(
                    self,
                    x,
                    y,
                    f,
                    popt,
                    self.global_settings,
                    self.r4_widget.currentText(),
                    self.sensor_widget.currentText(),
                    self.settings_widget,
                    self.import_widget,
                )

        calc_button = QtWidgets.QPushButton(text="Calc coeffs")
        calc_button.clicked.connect(click_calc_button)

        layout.addWidget(slice_widget, row, 0, 1, 2)
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
            "4.61042",
            "4.57307",
            "4.20415",
            "2.41583",
            "0.75001",
            "0.58466",
            "0.43554",
            "0.40117",
        ]
        for widget, text in zip(self.entries.values(), test_values):
            widget.setText(text)

    def create_func_for_u_measuring(self, index: int):
        return functools.partial(self.measure_u, index)

    def measure_u(self, index: int):
        ms = self.settings_widget.get_new_ms()
        if ms is not None:
            if self.settings_widget.get_multirange():
                _, _, r4_range_dict = self.settings_widget.get_r4_data()
                try:
                    ms.send_measurement_range(
                        (r4_range_dict[self.r4_widget.currentText()],) * 12
                    )

                    us_answers = self.get_us_from_ms(ms)
                    average_u = self.calculate_average_u(us_answers)
                    self.record_u(index, average_u)
                except:
                    ms.close()
            else:
                us_answers = self.get_us_from_ms(ms)
                average_u = self.calculate_average_u(us_answers)
                self.record_u(index, average_u)

    def get_us_from_ms(self, ms):
        return [ms.full_request((0,) * 12)[0] for _ in range(15)]

    def calculate_average_u(self, us):
        return sum([u[int(self.sensor_widget.currentText()) - 1] for u in us[5:]]) / 10

    def record_u(self, index, average_u):
        self.entries[r_labels_str[index]].setText("{:2.5f}".format(average_u))

    @QtCore.Slot(tuple)
    def on_slice_widget_value_change(self, min_max_values_tuple: tuple):
        min_value, max_value = min_max_values_tuple
        for idx, r_label in enumerate(r_labels_str):
            line_edit = self.entries[r_label]
            is_in_range_of_slider =  (min_value <= idx <= max_value)
            line_edit.setEnabled(is_in_range_of_slider)
