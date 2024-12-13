from PySide2.QtCore import Signal
from database.base_widgets import DatabaseNonleaderComboboxWidget
from database.base_widgets import DatabaseLeaderComboboxWidget

class HeaterResistanceConverterWidget(DatabaseNonleaderComboboxWidget):
    def __init__(self,
                 leader_widget: DatabaseLeaderComboboxWidget,
                 *args, **kwargs):
        super().__init__(leader_widget,
                         "heater_resistance_converter",
                         ["100", "1000"],
                         [100, 1000],
                         *args,
                         **kwargs)

    def get_value(self) -> bool:
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return True

