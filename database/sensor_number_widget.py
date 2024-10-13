from database.base_widgets import DatabaseNonleaderComboboxWidget
from database.base_widgets import DatabaseLeaderComboboxWidget

class SensorNumberDatabaseWidget(DatabaseNonleaderComboboxWidget):
    def __init__(self,
                 leader_widget: DatabaseLeaderComboboxWidget,
                 *args, **kwargs):
        super().__init__(leader_widget,
                         "sensors_number",
                         ["4", "12"],
                         [4, 12],
                         *args,
                         **kwargs)

    def get_value(self) -> int:
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return 4
