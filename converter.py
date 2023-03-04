from PySide2 import QtWidgets, QtCore
import struct
import pathlib
import csv
from collections import OrderedDict
import itertools

column_markers = tuple("U Rn Rs T gs sn st sts".split())
column_names = ("Voltages",
                "Heater resistance",
                "Sensor resistance",
                "Temperature",
                "Gas state",
                "Stage number",
                "Stage type",
                "Mode number")


def form_header(sensor_number, chosen):
    header_comment = (("Time,s",),
                      (f"U{idx},V" for idx in range(sensor_number)),
                      (f"Rn{idx},Ohm" for idx in range(sensor_number)),
                      (f"Rs{idx},Ohm" for idx in range(sensor_number)),
                      (f"T{idx},C" for idx in range(sensor_number)),
                      ("gas_state",),
                      ("stage_num",),
                      ("stage_type",),
                      (f"State{idx}" for idx in range(sensor_number))
                      )
    header = (("Time",),
              (f"U{idx}" for idx in range(sensor_number)),
              (f"Rn{idx}" for idx in range(sensor_number)),
              (f"Rs{idx}" for idx in range(sensor_number)),
              (f"T{idx}" for idx in range(sensor_number)),
              ("gas_state",),
              ("stage_num",),
              ("stage_type",),
              (f"State{idx}" for idx in range(sensor_number))
              )
    header = itertools.chain(*(val for ch, val in zip(chosen, header) if ch))
    header_comment = itertools.chain(*(val for ch, val in zip(chosen, header_comment) if ch))
    return header_comment, header

def format_float(value):
    if isinstance(value, float):
        return f"{value:10.4f}"
    elif isinstance(value, int):
        return f"{value:4d}"


class ConverterWidget(QtWidgets.QWidget):
    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)
        self.setWindowTitle("Converter")

        self.global_settings = global_settings

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        lineedit_layout = QtWidgets.QHBoxLayout()
        self.filepath_lineedit = QtWidgets.QLineEdit()
        openfile_button = QtWidgets.QPushButton("...")
        main_layout.addLayout(lineedit_layout)
        lineedit_layout.addWidget(self.filepath_lineedit)
        lineedit_layout.addWidget(openfile_button)
        openfile_button.clicked.connect(self.openfile_callback)

        self.checkboxes = OrderedDict()

        converter_chosen_lines = self.global_settings.value("converter_chosen_lines", "").split()

        for column, column_name in zip(column_markers, column_names):
            checkbox = QtWidgets.QCheckBox(column_name, self)
            if column in converter_chosen_lines:
                checkbox.setChecked(True)
            self.checkboxes[column] = checkbox
            main_layout.addWidget(checkbox)

        self.convert_button = QtWidgets.QPushButton("Convert")
        main_layout.addWidget(self.convert_button)
        self.convert_button.clicked.connect(self.convert_callback)

    def openfile_callback(self):
        filename, filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open result file", "./tests", "Result file (*.dat)")
        if filename:
            self.filepath_lineedit.setText(filename)

    def convert_callback(self):
        checked_boxes = " ".join((marker for marker, checkbox in self.checkboxes.items() if checkbox.isChecked()))
        self.global_settings.setValue("converter_chosen_lines", checked_boxes)

        chosen = (True, ) + tuple(checkbox.isChecked() for checkbox in self.checkboxes.values())

        orig_file = pathlib.Path(self.filepath_lineedit.text())
        out_file = orig_file.with_suffix(".txt")
        with orig_file.open("rb") as fd:
            with out_file.open("w") as fd_out:
                csvwriter = csv.writer(fd_out, delimiter="\t")
                sensors_number, *_ = struct.unpack("<B", fd.read(1))
                header_comment, header = form_header(sensors_number, chosen)
                csvwriter.writerow(header_comment)
                csvwriter.writerow(header)
                bin_write_struct = struct.Struct("<f" + sensors_number * 4 * "f" + "BIH" + sensors_number * "B")
                chunk = fd.read(bin_write_struct.size)
                while chunk:
                    values = bin_write_struct.unpack(chunk)
                    possible = (values[0:1],  # time
                                values[1:1 + sensors_number],  # us
                                values[1 + sensors_number: 1 + 2 * sensors_number],  # rs
                                values[1 + 2 * sensors_number: 1 + 3 * sensors_number],  # sr
                                values[1 + 3 * sensors_number: 1 + 4 * sensors_number],  # temperatures
                                values[1 + 4 * sensors_number: 1 + 4 * sensors_number + 1],  # gas_state
                                values[1 + 1 + 4 * sensors_number: 1 + 2 + 4 * sensors_number],  # stage_num
                                values[1 + 2 + 4 * sensors_number: 1 + 3 + 4 * sensors_number],  # stage_type
                                values[1 + 3 + 4 * sensors_number: 1 + 3 + 5 * sensors_number],  # sensor_states
                                )
                    row_to_write = map(format_float, tuple(itertools.chain(*(val for ch, val in zip(chosen, possible) if ch))))
                    csvwriter.writerow(row_to_write)
                    chunk = fd.read(bin_write_struct.size)

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
