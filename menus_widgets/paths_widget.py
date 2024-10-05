from PySide2 import QtWidgets, QtCore
from misc import FileDialogLineEdit

class PathsWidget(QtWidgets.QWidget):
    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)
        main_layout = QtWidgets.QFormLayout(self)
        self.setWindowTitle("Paths settings")
        self.global_settings = global_settings

        main_layout.addWidget(QtWidgets.QLabel("To edit double-click or press Enter"))

        self.paths_settings = [
            "operation_widget_save_path",
            "operation_widget_programs_path",
            "calibration_widget_res_path",
            "calibration_widget_par_path",
            "calibration_widget_cal_path",
            "import_calibration_widget",
        ]

        self.lineedits = []
        for path in self.paths_settings:
            lineedit = FileDialogLineEdit(self.global_settings, path)
            main_layout.addRow(path, lineedit)
            self.lineedits.append(lineedit)

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
        if self.isVisible():
            self.refresh_values()

    def refresh_values(self):
        for path, lineedit in zip(self.paths_settings, self.lineedits):
            lineedit.setText(self.global_settings.value(path, "./tests"))
