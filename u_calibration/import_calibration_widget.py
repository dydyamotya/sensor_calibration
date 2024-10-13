import configparser
import logging
import pathlib

from PySide2 import QtCore, QtWidgets

from database.models import SensorPosition

logger = logging.getLogger(__name__)

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
