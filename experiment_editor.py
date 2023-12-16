from PySide2 import QtWidgets, QtCore
from misc import clear_layout
from program_generator_types import Stage, SimpleStage, dict_of_stage_types
import sys


class StageItem(QtWidgets.QListWidgetItem):
    def __init__(self, stage: Stage, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage = stage

    def set_stage(self, stage: Stage):
        self.stage = stage
        self.setText(self.stage.name)


class ListOfStages(QtWidgets.QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragDropMode(self.InternalMove)

    def add_stage(self):
        num_of_rows = self.count()
        stage = SimpleStage.default()
        item = StageItem(stage, stage.name)
        self.insertItem(num_of_rows, item)

    def remove_stage(self):
        items = self.selectedItems()
        if len(items) > 0:
            item: StageItem = items[0]
            self.takeItem(self.indexFromItem(item).row())


class SuitableWidget(QtWidgets.QWidget):
    value_changed = QtCore.Signal()

    def __init__(self, payload, *args, first: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(payload, str):
            QtWidgets.QVBoxLayout(self)
            lineedit = QtWidgets.QLineEdit(payload)
            self.layout().addWidget(lineedit, QtCore.Qt.AlignTop)
            lineedit.textChanged.connect(self.value_changed)
        elif isinstance(payload, dict):
            QtWidgets.QGridLayout(self)
            for row_idx, (key, value) in enumerate(payload.items()):
                suitable_widget = SuitableWidget(value)
                suitable_widget.value_changed.connect(self.value_changed)
                key_lineedit = QtWidgets.QLabel(key)
                # if first:
                    # key_lineedit.setReadOnly(True)
                self.layout().addWidget(key_lineedit, row_idx, 0, QtCore.Qt.AlignTop)
                self.layout().addWidget(suitable_widget, row_idx, 1, QtCore.Qt.AlignTop)
        elif isinstance(payload, list):
            QtWidgets.QGridLayout(self)
            for row_idx, value in enumerate(payload):
                suitable_widget = SuitableWidget(value)
                suitable_widget.value_changed.connect(self.value_changed)
                self.layout().addWidget(suitable_widget, row_idx, 0, QtCore.Qt.AlignTop)
        elif isinstance(payload, int):
            QtWidgets.QVBoxLayout(self)
            spinbox = QtWidgets.QSpinBox()
            spinbox.setMaximum(1000)
            spinbox.setValue(payload)
            spinbox.valueChanged.connect(self.value_changed)
            self.layout().addWidget(spinbox, QtCore.Qt.AlignTop)
        elif isinstance(payload, float):
            QtWidgets.QVBoxLayout(self)
            spinbox = QtWidgets.QDoubleSpinBox()
            spinbox.setDecimals(1)
            spinbox.setSingleStep(1.0)
            spinbox.setMaximum(sys.maxsize)
            spinbox.setValue(payload)
            spinbox.valueChanged.connect(self.value_changed)
            self.layout().addWidget(spinbox, QtCore.Qt.AlignTop)
        else:
            QtWidgets.QVBoxLayout(self)
            lineedit = QtWidgets.QLineEdit(str(payload))
            self.layout().addWidget(lineedit, QtCore.Qt.AlignTop)
            lineedit.textChanged.connect(self.value_changed)

    def collect(self):
        main_layout = self.layout()
        if isinstance(main_layout, QtWidgets.QGridLayout):
            if main_layout.columnCount() == 1:
                result_list = []
                for row_idx in range(main_layout.rowCount()):
                    value = main_layout.itemAtPosition(row_idx, 0).widget().collect()
                    result_list.append(value)
                return result_list

            elif main_layout.columnCount() == 2:
                result_dict = {}
                for row_idx in range(main_layout.rowCount()):
                    key = main_layout.itemAtPosition(row_idx, 0).widget().text()
                    value = main_layout.itemAtPosition(row_idx, 1).widget().collect()
                    result_dict[key] = value
                return result_dict
            else:
                raise Exception("No such processor for layout: {} with {} columns".format(main_layout, main_layout.columnCount()))
        elif isinstance(main_layout, QtWidgets.QVBoxLayout):
            widget = main_layout.itemAt(0).widget()
            if isinstance(widget, QtWidgets.QLineEdit):
                return widget.text()
            elif isinstance(widget, QtWidgets.QSpinBox):
                return widget.value()
            elif isinstance(widget, QtWidgets.QDoubleSpinBox):
                return widget.value()
        else:
            raise Exception("No such processor for layout: {}".format(main_layout))


class StagePropertiesWidget(QtWidgets.QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QVBoxLayout(self)
        self.stage_item = None
        self.stages_history = {}

    @QtCore.Slot(StageItem) # pyright: ignore
    def draw_stage(self, stage_item: StageItem):
        self.stage_item = stage_item
        self.stages_history = {stage_item.stage.name: stage_item.stage}
        self._draw_top(stage_item.stage)

    def _draw_top(self, stage: Stage):
        clear_layout(self.layout())
        main_layout = self.layout()

        self.stage_type_button_group = QtWidgets.QButtonGroup()
        buttons_layout = QtWidgets.QHBoxLayout()
        self.characteristics_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(buttons_layout)
        main_layout.addLayout(self.characteristics_layout)

        for type_ in dict_of_stage_types.values():
            pushbutton = QtWidgets.QPushButton(type_.name.capitalize())
            pushbutton.setCheckable(True)
            if stage.name == type_.name:
                pushbutton.setChecked(True)
            self.stage_type_button_group.addButton(pushbutton)
            buttons_layout.addWidget(pushbutton)

        self.stage_type_button_group.buttonClicked.connect(self._redraw_bottom)
        self.stage_type_button_group.buttonClicked.emit(self.stage_type_button_group.checkedButton())

    @QtCore.Slot(QtWidgets.QAbstractButton) # pyright: ignore
    def _redraw_bottom(self, button: QtWidgets.QAbstractButton):
        clear_layout(self.characteristics_layout)
        type_name = button.text().lower()
        try:
            stage = self.stages_history[type_name]
        except KeyError:
            stage: Stage = dict_of_stage_types[type_name].default()
            self.stages_history[type_name] = stage

        # fill with values
        stage_dict = stage.to_dict()
        suitable_widget = SuitableWidget(stage_dict, first=True)
        suitable_widget.value_changed.connect(self._update_stage_item) # pyright: ignore
        self.characteristics_layout.addWidget(suitable_widget)
        self.characteristics_layout.addStretch()

        self._update_stage_item()

    def _update_stage_item(self):
        # every time value updates -> update stage item and stages history
        # here we go through chars layout and collect parts from suitable_widget's
        type_name = self.stage_type_button_group.checkedButton().text().lower()
        stage = self.stages_history[type_name]

        widget: SuitableWidget = self.characteristics_layout.itemAt(0).widget()
        dict_collected = widget.collect()
        stage = stage.from_dict(dict_collected)
        self.stages_history[type_name] = stage
        if self.stage_item is not None:
            self.stage_item.set_stage(stage)



class ExperimentEditorWidget(QtWidgets.QWidget):
    def __init__(self, settings, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = settings
        self.py_parent = parent

        self.list_of_stages_widget = ListOfStages()
        self.list_of_stages_plus_button = QtWidgets.QPushButton("+")
        self.list_of_stages_minus_button = QtWidgets.QPushButton("-")

        self.stage_properties_widget = StagePropertiesWidget()

        self.list_of_stages_widget.itemClicked.connect(self.stage_properties_widget.draw_stage)

        self.list_of_stages_plus_button.clicked.connect(self.list_of_stages_widget.add_stage)
        self.list_of_stages_minus_button.clicked.connect(self.list_of_stages_widget.remove_stage)

        main_layout = QtWidgets.QVBoxLayout(self)

        horizontal_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(horizontal_layout)

        list_layout = QtWidgets.QVBoxLayout()
        horizontal_layout.addLayout(list_layout)
        horizontal_layout.addWidget(self.stage_properties_widget)

        horizontal_layout.addStretch()

        list_layout.addWidget(self.list_of_stages_widget)

        buttons_list_layout = QtWidgets.QHBoxLayout()
        buttons_list_layout.addWidget(self.list_of_stages_plus_button)
        buttons_list_layout.addWidget(self.list_of_stages_minus_button)
        list_layout.addLayout(buttons_list_layout)

        main_layout.addStretch()


    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
