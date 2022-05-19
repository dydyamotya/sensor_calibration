from PySide2 import QtWidgets

try:
    from serial.tools.list_ports import comports
except ImportError:
    pass
else:
    class ComPortWidget(QtWidgets.QComboBox):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setPlaceholderText("COM Port")

        def showPopup(self):
            self.clear()
            comports_list = [x.device for x in comports()]
            self.insertItems(0, comports_list)
            super().showPopup()

        def text(self):
            return self.currentText()

    def comports_list():
        return [x.device for x in comports()]

class TestWidget():
    pass

