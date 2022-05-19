from PySide2 import QtWidgets

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


def clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget() is not None:
            child.widget().deleteLater()
        elif child.layout() is not None:
            clear_layout(child.layout())

class CssCheckBoxes(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent_py = parent

        layout = QtWidgets.QHBoxLayout(self)

        self.checkboxes = []

        for i in range(1, 13, 4):
            checkbox = QtWidgets.QCheckBox(f"CSS {i:d}-{i+3:d}", parent=self)
            self.checkboxes.append(checkbox)
            layout.addWidget(checkbox)

    def collect_checkboxes(self):
        return [checkbox.isChecked() for checkbox in self.checkboxes]
