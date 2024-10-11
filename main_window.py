from PySide2 import QtWidgets, QtGui, QtCore

from equipment_settings import EquipmentSettings
from menus_widgets.paths_widget import PathsWidget
from gas_state_widget import GasStateWidget
from u_calibration.import_calibration_widget import ImportCalibrationWidget
from plotter import ExperimentPlotter
from converter import ConverterWidget
from experiment_editor import ExperimentEditorWidget

import logging 

logger = logging.getLogger(__name__)

class MyMainWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: QtCore.QSettings, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings_widget = EquipmentSettings(settings, self)
        logger.debug("After equipment setting init")
        self.gasstate_widget = GasStateWidget(settings, self)
        logger.debug("After gasstate init")
        self.import_widget = ImportCalibrationWidget(settings, self)
        self.paths_widget = PathsWidget(settings)
        self.plotter_experiment_widget = ExperimentPlotter()
        self.converter_widget = ConverterWidget(settings)
        self.experiment_editor_widget = ExperimentEditorWidget(settings, self)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.gasstate_widget.save_to_settings()
        return super().closeEvent(event)
