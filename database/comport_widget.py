from database.base_widgets import DatabaseNonleaderComboboxWidget
from database.base_widgets import DatabaseLeaderComboboxWidget
from pyside_constructor_widgets.widgets import comports_list

class ComportDatabaseWidget(DatabaseNonleaderComboboxWidget):
    def __init__(self,
                 leader_widget: DatabaseLeaderComboboxWidget,
                 *args, **kwargs):
        super().__init__(leader_widget,
                         'last_port',
                         comports_list(),
                         comports_list(),
                         *args,
                         **kwargs)

    def get_value(self) -> str:
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return ''

    def refresh_values(self):
        keys = comports_list()
        values = comports_list()

        current_value = self.currentText()
        self.clear()
        self.mapping = dict(zip(keys, values))
        self.keys = keys
        self.values = values
        self.addItems(keys)
        try:
            self.setCurrentIndex(self.keys.index(current_value))
        except ValueError:
            self.setCurrentIndex(0)
