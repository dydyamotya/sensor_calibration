import logging

import numpy as np
import pyqtgraph as pg
from PySide2 import QtCore, QtWidgets
from yaml import dump

from database.models import SensorPosition

logger = logging.getLogger(__name__)

class PlotWidget(QtWidgets.QWidget):

    def __init__(self, parent, x, y, func, popt, global_settings, r4,
                 sensor_num, settings_widget, import_widget):
        super().__init__(parent, f=QtCore.Qt.Tool)

        self.global_settings = global_settings
        self.settings_widget = settings_widget
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
        if self.settings_widget.get_multirange():
            self.r4_str_values, *_ = self.settings_widget.get_r4_data()
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


