import socket
from PySide2 import QtWidgets, QtCore
import logging

logger = logging.getLogger(__name__)

class GasStateWidget(QtWidgets.QWidget):
    redraw_signal = QtCore.Signal(int)
    send_gasstate_signal = QtCore.Signal(int)

    def __init__(self, global_settings, *args, **kwargs):
        super().__init__(*args, f=QtCore.Qt.Tool, **kwargs)
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)
        self.setWindowTitle("Settings")
        self.global_settings: QtCore.QSettings = global_settings

        self.enable_checkbox = QtWidgets.QCheckBox()
        layout.addRow("Enabled:", self.enable_checkbox)

        self.gas_state_server_address = QtWidgets.QLineEdit()
        layout.addRow("GasState Server IP:", self.gas_state_server_address)

        self.gas_state_test = QtWidgets.QLineEdit()
        layout.addRow("Test state:", self.gas_state_test)

        self.gas_state_test.returnPressed.connect(self.send_state_test)
        self.send_gasstate_signal.connect(self.send_state)
        self.prev_gas_state = None

    def load_from_settings(self):
        gas_state_server_enabled_value = self.global_settings.value('gas_state_server_enabled', type=bool)
        if gas_state_server_enabled_value is not None:
            self.enable_checkbox.setEnabled(bool(gas_state_server_enabled_value))
        gas_state_server_address_value = self.global_settings.value('gas_state_server_address', type=str)
        if gas_state_server_address_value is not None:
            self.gas_state_server_address.setText(str(gas_state_server_address_value))

    def save_to_settings(self):
        self.global_settings.setValue('gas_state_server_enabled', self.enable_checkbox.isEnabled())
        self.global_settings.setValue('gas_state_server_address', self.gas_state_server_address.text())

    @QtCore.Slot(int)
    def send_state(self, state_num: int):
        if self.enable_checkbox.isChecked():
            if state_num != self.prev_gas_state:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.001)
                ip, port = self.gas_state_server_address.text().split(":")
                s.connect((ip, int(port)))
                s.send(str(state_num).encode("utf-8"))
                s.close()
                self.prev_gas_state = state_num


    def send_state_test(self):
        self.send_state(self.gas_state_test.text())

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()



