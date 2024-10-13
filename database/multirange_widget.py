from PySide2.QtCore import Signal
from database.base_widgets import DatabaseNonleaderComboboxWidget
from database.base_widgets import DatabaseLeaderComboboxWidget

class MultirangeDatabaseWidget(DatabaseNonleaderComboboxWidget):
    multirange_state_change = Signal(bool)
    def __init__(self,
                 leader_widget: DatabaseLeaderComboboxWidget,
                 *args, **kwargs):
        super().__init__(leader_widget,
                         "multirange",
                         ["yes", "no"],
                         [True, False],
                         *args,
                         **kwargs)
        self.activated.connect(self.on_multirange_activated)

    def get_value(self) -> bool:
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return True

    def on_multirange_activated(self):
        self.multirange_state_change.emit(self.get_value())

    def on_leader_value_change(self, value: str):
        super().on_leader_value_change(value)
        self.on_multirange_activated()
