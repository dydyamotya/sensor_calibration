from database.base_widgets import DatabaseNonleaderComboboxWidget
from database.base_widgets import DatabaseLeaderComboboxWidget

class MultirangeDatabaseWidget(DatabaseNonleaderComboboxWidget):
    def __init__(self,
                 leader_widget: DatabaseLeaderComboboxWidget,
                 *args, **kwargs):
        super().__init__(leader_widget,
                         "multirange",
                         ["yes", "no"],
                         [True, False],
                         *args,
                         **kwargs)

    def get_value(self) -> bool:
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return True
