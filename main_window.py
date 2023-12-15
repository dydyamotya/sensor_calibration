from PySide2 import QtWidgets, QtGui, QtCore

from equipment_settings import EquipmentSettings, PathsWidget
from gas_state_widget import GasStateWidget
from u_calibration import ImportCalibrationWidget
from plotter import ExperimentPlotter
from converter import ConverterWidget

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
