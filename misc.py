from PySide2 import QtWidgets
from PySide2.QtCore import Signal, Slot, Qt

class TypeCheckLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent, type_, default_value):
        super().__init__(str(default_value), parent)
        self.type_ = type_
        self.default_value = default_value
        if not isinstance(default_value, type_):
            raise TypeError("default value type must be equal to type_ type")

    def get_value(self):
        try:
            return self.type_(self.text())
        except ValueError:
            return self.default_value

    def set_value(self, value):
        if not isinstance(value, self.type_):
            self.setText(str(self.default_value))
        else:
            self.setText(str(value))
            

