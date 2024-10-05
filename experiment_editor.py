from PySide2 import QtWidgets, QtCore
from misc import clear_layout
from operation_utils.program_generator_types import Stage, SimpleStage, dict_of_stage_types
import typing
import yaml
import pathlib
import pyqtgraph as pg
from operation_utils.program_generator import ProgramGenerator
import numpy as np


class YAMLTreeItem:
    types_mapping = {int: "int", float: "float", dict: "dict", list: "list", str: "str"}

    def __init__(self, name, data, parent_item=None):
        self._children = []
        self._parent_item = parent_item
        self._name = name
        self._value = None
        self._end_node = False
        self._type_of_node = None
        self._init_data(data)

    def _init_data(self, data):
        if isinstance(data, dict):
            for key, value in data.items():
                item = YAMLTreeItem(key, value, parent_item=self)
                self._children.append(item)
            self._type_of_node = dict
        elif isinstance(data, list):
            for idx_row, value in enumerate(data):
                item = YAMLTreeItem(str(idx_row), value, parent_item=self)
                self._children.append(item)
            self._type_of_node = list
        else:
            self._value = data
            self._end_node = True
            self._type_of_node = type(data)

    def child(self, row: int) -> typing.Optional["YAMLTreeItem"]:
        try:
            return self._children[row]
        except KeyError:
            return None

    def parent(self):
        return self._parent_item

    def childCount(self):
        return len(self._children)

    def columnCount(self):
        return 3

    def row(self):
        parent = self.parent()
        if parent is None:
            return None
        else:
            return parent._children.index(self)

    def data(self, column: int = 0):
        if column == 0:
            return self._name
        elif column == 1:
            return self._value
        elif column == 2:
            return self.types_mapping[self._type_of_node]

    def set_value(self, value):
        if self._end_node:
            self._value = value

    def set_type(self, type_str):
        outer_types_mapping = dict(
            zip(self.types_mapping.values(), self.types_mapping.keys())
        )
        if type_str not in outer_types_mapping:
            return False
        else:
            new_type = outer_types_mapping[type_str]
            if new_type in [dict, list]:
                self._type_of_node = new_type
                self._end_node = False
                self._value = None
            else:
                self._type_of_node = new_type
                self._end_node = True
                self._value = 0

    def set_name(self, name):
        self._name = name

    def add_child(self, row: int):
        if len(self._children) > 0:
            last_item = self._children[-1]
            if last_item._type_of_node not in [dict, list]:
                item = YAMLTreeItem(str(row), last_item._value, parent_item=self)
            else:
                item = YAMLTreeItem(str(row), "", parent_item=self)
        else:
            item = YAMLTreeItem(str(row), "", parent_item=self)
        self._children.insert(row, item)

    def delete_child(self, row: int):
        if len(self._children) > 0:
            self._children.pop(row)

    def collect(self):
        if self._end_node:
            return self._type_of_node(self._value)
        else:
            if self._type_of_node == dict:
                return {child._name: child.collect() for child in self._children}
            elif self._type_of_node == list:
                return [child.collect() for child in self._children]


class YAMLTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._root_item = None

    def setModelData(self, stage: Stage):
        self._stage = stage
        self._root_item = YAMLTreeItem("root", self._stage.to_dict(for_ui=True))

    def index(
        self, row: int, column: int, parent: QtCore.QModelIndex
    ) -> QtCore.QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parent_item: YAMLTreeItem = self._root_item
        else:
            parent_item: YAMLTreeItem = parent.internalPointer()  # pyright: ignore

        child_item = parent_item.child(row)
        if child_item is not None:
            return self.createIndex(row, column, child_item)
        return QtCore.QModelIndex()

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        if not index.isValid():
            return QtCore.QModelIndex()
        child_item: YAMLTreeItem = index.internalPointer()  # pyright: ignore
        parent_item: YAMLTreeItem = child_item.parent()

        if parent_item is self._root_item:
            return QtCore.QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    def data(self, index: QtCore.QModelIndex, role: int) -> typing.Any:
        if not index.isValid():
            return None
        if role == QtCore.Qt.DisplayRole:
            item: YAMLTreeItem = index.internalPointer()  # pyright: ignore
            data_view = item.data(index.column())
            return data_view
        return None

    def rowCount(self, parent: QtCore.QModelIndex) -> int:
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self._root_item
        else:
            parent_item: YAMLTreeItem = parent.internalPointer()  # pyright: ignore
        return parent_item.childCount()

    def columnCount(self, parent: QtCore.QModelIndex) -> int:
        if parent.isValid():
            columnCount = parent.internalPointer().columnCount()
        if self._root_item is not None:
            columnCount = self._root_item.columnCount()
        else:
            columnCount = 0
        return columnCount

    def headerData(
        self, section: int, orientation: QtCore.Qt.Orientation, role: int
    ) -> typing.Any:
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.DisplayRole
        ):
            if section == 0:
                return "Key"
            elif section == 1:
                return "Value"
            elif section == 2:
                return "Type"
        return None

    def setData(self, index: QtCore.QModelIndex, value: typing.Any, role: int) -> bool:
        item: YAMLTreeItem = index.internalPointer()  # pyright: ignore
        if role == QtCore.Qt.EditRole:
            if index.column() == 1:
                prev_value = item._value
                item.set_value(value)
                try:
                    item.collect()
                except:
                    item.set_value(prev_value)
                    return False
                self.dataChanged.emit(index, index, QtCore.Qt.EditRole)
                return True
            elif index.column() == 0:
                prev_value = item._value
                item.set_name(value)
                try:
                    item.collect()
                except:
                    item.set_name(prev_value)
                    return False
                self.dataChanged.emit(index, index, QtCore.Qt.EditRole)
                return True
            elif index.column() == 2:
                prev_value = item._value
                item.set_type(value)
                try:
                    item.collect()
                except:
                    item.set_type(prev_value)
                    return False
                self.dataChanged.emit(index, index, QtCore.Qt.EditRole)
                return True

        return False

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        flags_ = super().flags(index)
        return QtCore.Qt.ItemIsEditable | flags_

    def removeRows(self, row: int, count: int, parent: QtCore.QModelIndex) -> bool:
        if parent.isValid():
            parent_item: YAMLTreeItem = parent.internalPointer()  # pyright: ignore
        else:
            return False

        child_item = parent_item.child(row)
        if child_item is None:
            return False

        self.beginRemoveRows(parent, row, row + count - 1)
        result = parent_item.delete_child(row)
        if result:
            self.endRemoveRows()
            return False
        self.dataChanged.emit(
            self.index(row + 1, 0, parent),
            self.index(row + count, 2, parent),
            QtCore.Qt.EditRole,
        )
        self.endRemoveRows()
        return True

    def insertRows(self, row: int, count: int, parent: QtCore.QModelIndex) -> bool:
        if parent.isValid():
            parent_item: YAMLTreeItem = parent.internalPointer()  # pyright: ignore
        else:
            if self._root_item is None:
                return False
            parent_item = self._root_item

        child_item = parent_item.child(row)
        if child_item is None:
            return False

        if child_item._type_of_node in [list, dict]:
            new_rows = child_item.childCount()
            child_modelindex = self.index(row, 0, parent)
            self.beginInsertRows(child_modelindex, new_rows, new_rows + count - 1)

            for i in range(new_rows, new_rows + count):
                child_item.add_child(i)
            self.endInsertRows()
            self.dataChanged.emit(
                self.index(new_rows, 0, parent),
                self.index(new_rows + count - 1, 2, parent),
                QtCore.Qt.EditRole,
            )
        else:
            if parent_item is self._root_item:
                return False
            self.beginInsertRows(parent, row + 1, row + count)

            for i in range(row + 1, row + 1 + count):
                parent_item.add_child(i)
            self.endInsertRows()
            self.dataChanged.emit(
                self.index(row + 1, 0, parent),
                self.index(row + count, 2, parent),
                QtCore.Qt.EditRole,
            )

    def collect(self):
        return self._root_item.collect()


class StageItem(QtWidgets.QListWidgetItem):
    def __init__(self, stage: Stage, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage = stage

    def set_stage(self, stage: Stage):
        self.stage = stage
        self.setText(self.stage.name)


class ListOfStages(QtWidgets.QListWidget):
    redraw_plot_signal = QtCore.Signal(np.ndarray, np.ndarray)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragDropMode(self.InternalMove)

    def redraw_plot(self):
        experiment_dict = self.create_dict()
        program_generator = ProgramGenerator(experiment_dict)
        full_time = program_generator.calculate_full_time()
        program_generator_gen = program_generator.parse_program_to_queue()
        times = []
        temperatures = []
        progress = QtWidgets.QProgressDialog(
            "Generating plot", "Stop", 0, full_time, self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        for time_next, (temperatures_, _, _, _) in program_generator_gen:
            times.append(time_next)
            temperatures.append(temperatures_[0])
            progress.setValue(time_next)
            if progress.wasCanceled():
                break
        times = np.array(times)
        temperatures = np.array(temperatures)
        self.redraw_plot_signal.emit(times, temperatures)

    def add_stage(self):
        num_of_rows = self.count()
        stage = SimpleStage.default()
        item = StageItem(stage, stage.name)
        self.insertItem(num_of_rows, item)

    def remove_stage(self):
        items = self.selectedItems()
        if len(items) > 0:
            item: StageItem = items[0]
            row = self.indexFromItem(item).row()
            self.takeItem(row)
            self.setCurrentItem(
                self.item(row if self.count() > row else self.count() - 1)
            )

    def clear_stages(self):
        for i in range(self.count()):
            item = self.takeItem(i)
            del item

    @QtCore.Slot(str)  # pyright: ignore
    def load_file(self, filename: str):
        loaded = yaml.load(pathlib.Path(filename).read_text(), yaml.Loader)
        self.clear_stages()
        self.clear_stages()
        program = loaded["program"]
        for idx, stage_ in enumerate(program):
            stage = dict_of_stage_types[stage_["type"]].from_dict(stage_)
            item = StageItem(stage, stage.name)
            self.insertItem(idx, item)

        if self.count() > 0:
            self.setCurrentItem(self.item(0))

    def create_dict(self) -> dict:
        base_dict = {"settings": {"frequency": 10}}
        stages_list = []
        for i in range(self.count()):
            stage_item: StageItem = self.item(i)
            stage: Stage = stage_item.stage
            stages_list.append(stage.to_dict())
        base_dict["program"] = stages_list

        return base_dict

    @QtCore.Slot(str)  # pyright: ignore
    def save_file(self, filename: str):
        base_dict = self.create_dict()
        with open(filename, "w") as fd:
            yaml.dump(base_dict, fd, sort_keys=False)


class StagePropertiesWidget(QtWidgets.QListWidget):
    plus_button_clicked_signal = QtCore.Signal()
    minus_button_clicked_signal = QtCore.Signal()
    signal_to_redraw_plot_signal = QtCore.Signal()
    import_temperature_profile_signal = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QVBoxLayout(self)
        self.stage_item = None
        self.stages_history = {}

        self.yaml_tree_model = YAMLTreeModel(self)
        self.yaml_tree_model.dataChanged.connect(self._update_stage_item)

        self.plus_button_clicked_signal.connect(self.addRowToModel)
        self.minus_button_clicked_signal.connect(self.deleteRowFromModel)
        self.import_temperature_profile_signal.connect(self.import_temperature_profile)

    @QtCore.Slot(StageItem)  # pyright: ignore
    def draw_stage(self, stage_item: StageItem):
        if stage_item is not None:
            self.stage_item = stage_item
            self.stages_history = {stage_item.stage.name: stage_item.stage}
            self._draw_top(stage_item.stage)

    def _draw_top(self, stage: Stage):
        clear_layout(self.layout())
        main_layout = self.layout()

        self.stage_type_button_group = QtWidgets.QButtonGroup()
        buttons_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(buttons_layout)

        self.treeview = QtWidgets.QTreeView()
        self.treeview.setModel(self.yaml_tree_model)

        main_layout.addWidget(self.treeview)

        rows_buttons_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(rows_buttons_layout)

        plus_button = QtWidgets.QPushButton("+")
        plus_button.clicked.connect(self.plus_button_clicked_signal)
        minus_button = QtWidgets.QPushButton("-")
        minus_button.clicked.connect(self.minus_button_clicked_signal)

        self.import_temperature_profile_button = QtWidgets.QPushButton(
            "Import temperature profile"
        )
        self.import_temperature_profile_button.clicked.connect(
            self.import_temperature_profile_signal
        )
        self.import_temperature_profile_button.setVisible(False)

        rows_buttons_layout.addStretch(1)
        rows_buttons_layout.addWidget(self.import_temperature_profile_button)
        rows_buttons_layout.addWidget(plus_button)
        rows_buttons_layout.addWidget(minus_button)

        for type_ in dict_of_stage_types.values():
            pushbutton = QtWidgets.QPushButton(type_.name.capitalize())
            pushbutton.setCheckable(True)
            if stage.name == type_.name:
                pushbutton.setChecked(True)
            self.stage_type_button_group.addButton(pushbutton)
            buttons_layout.addWidget(pushbutton)

        self.stage_type_button_group.buttonClicked.connect(self._redraw_bottom)
        self.stage_type_button_group.buttonClicked.emit(
            self.stage_type_button_group.checkedButton()
        )

    @QtCore.Slot(QtWidgets.QAbstractButton)  # pyright: ignore
    def _redraw_bottom(self, button: QtWidgets.QAbstractButton):
        type_name = button.text().lower()
        try:
            stage = self.stages_history[type_name]
        except KeyError:
            stage: Stage = dict_of_stage_types[type_name].default()
            self.stages_history[type_name] = stage

        # fill with values
        self.yaml_tree_model.beginResetModel()
        self.yaml_tree_model.setModelData(stage)
        self.yaml_tree_model.endResetModel()
        self.treeview.expandAll()
        for i in range(self.yaml_tree_model.columnCount(QtCore.QModelIndex())):
            self.treeview.resizeColumnToContents(i)
        # suitable_widget.value_changed.connect(self._update_stage_item) # pyright: ignore
        self.import_temperature_profile_button.setVisible(stage.name == "cyclic")

        self._update_stage_item()

    def _update_stage_item(self):
        # every time value updates -> update stage item and stages history
        # here we go through chars layout and collect parts from suitable_widget's
        type_name = self.stage_type_button_group.checkedButton().text().lower()
        try:
            stage = self.stages_history[type_name]
        except KeyError:
            pass
        else:
            dict_collected = self.treeview.model().collect()
            stage = stage.from_dict(dict_collected)
            self.stages_history[type_name] = stage
            if self.stage_item is not None:
                self.stage_item.set_stage(stage)
            self.signal_to_redraw_plot_signal.emit()

    def addRowToModel(self):
        first_qmodelindexes = self.treeview.selectedIndexes()
        if first_qmodelindexes is not None:
            modelindex = first_qmodelindexes[0]
            self.yaml_tree_model.insertRows(modelindex.row(), 1, modelindex.parent())

    def deleteRowFromModel(self):
        first_qmodelindexes = self.treeview.selectedIndexes()
        if first_qmodelindexes is not None:
            modelindex = first_qmodelindexes[0]
            self.yaml_tree_model.removeRows(modelindex.row(), 1, modelindex.parent())

    def import_temperature_profile(self):
        # import temperature profile from file
        filename, *_ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Выберите файл с температурным профилем",
            "./",
            "Profile files (*.dat)",
        )
        if filename:
            with open(filename) as fd:
                times_and_temperatures = np.loadtxt(fd)
            try:
                stage = self.stages_history["cyclic"]
            except KeyError:
                pass
            else:
                model_dict = stage.to_dict()
                model_dict["temperatures"]["time"] = (
                    times_and_temperatures[:, 0] / 1000
                ).tolist()
                model_dict["temperatures"]["temperature"] = times_and_temperatures[
                    :, 1
                ].tolist()
                new_stage = stage.from_dict(model_dict)
                self.stages_history["cyclic"] = new_stage
                self.yaml_tree_model.beginResetModel()
                self.yaml_tree_model.setModelData(new_stage)
                self.yaml_tree_model.endResetModel()
                self.treeview.expandAll()
                for i in range(self.yaml_tree_model.columnCount(QtCore.QModelIndex())):
                    self.treeview.resizeColumnToContents(i)
                self._update_stage_item()


class FilesWidget(QtWidgets.QWidget):
    file_open_signal = QtCore.Signal(str)
    file_save_signal = QtCore.Signal(str)

    def __init__(self, base_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QHBoxLayout(self)

        self.base_path = base_path

        self.path_lineedit = QtWidgets.QLineEdit()
        open_button = QtWidgets.QPushButton("Open")
        open_button.clicked.connect(self.open_callback)
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.save_callback)

        self.layout().addWidget(self.path_lineedit)
        self.layout().addWidget(open_button)
        self.layout().addWidget(save_button)

    def open_callback(self):
        filename, *_ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open experiment file",
            self.base_path,
            "Experiment files (*.yaml *.yml)",
        )
        if not filename:
            return
        self.path_lineedit.setText(filename)
        self.file_open_signal.emit(filename)

    def save_callback(self):
        filename, *_ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save experiment file",
            self.base_path,
            "Experiment files (*.yaml *.yml)",
        )
        if not filename:
            return
        self.path_lineedit.setText(filename)
        self.file_save_signal.emit(filename)


class PlotWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QtWidgets.QHBoxLayout(self)
        self.plot_widget = pg.PlotWidget(self)
        plot_item = self.plot_widget.getPlotItem()
        if plot_item is not None:
            plot_item.showGrid(x=True, y=True)
        self.layout().addWidget(self.plot_widget)

    @QtCore.Slot(np.ndarray, np.ndarray)  # pyright: ignore
    def plot_data(self, xdata: np.ndarray, ydata: np.ndarray):
        plot_item = self.plot_widget.getPlotItem()
        if plot_item is not None:
            plot_item.clear()
        self.plot_widget.plot(x=xdata, y=ydata, width=2)


class ExperimentEditorWidget(QtWidgets.QWidget):
    def __init__(self, settings, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Experiment Editor")

        self.settings = settings
        self.py_parent = parent

        experiment_path = self.settings.value(
            "operation_widget_programs_path", "./tests"
        )

        self.files_widget = FilesWidget(experiment_path)

        self.list_of_stages_widget = ListOfStages()
        self.list_of_stages_plus_button = QtWidgets.QPushButton("+")
        self.list_of_stages_minus_button = QtWidgets.QPushButton("-")
        redraw_button = QtWidgets.QPushButton("Redraw")

        self.plot_widget = PlotWidget()

        self.stage_properties_widget = StagePropertiesWidget()

        self.list_of_stages_widget.currentItemChanged.connect(
            self.stage_properties_widget.draw_stage
        )

        self.list_of_stages_plus_button.clicked.connect(
            self.list_of_stages_widget.add_stage
        )
        self.list_of_stages_minus_button.clicked.connect(
            self.list_of_stages_widget.remove_stage
        )

        self.files_widget.file_open_signal.connect(self.list_of_stages_widget.load_file)
        self.files_widget.file_save_signal.connect(self.list_of_stages_widget.save_file)

        redraw_button.clicked.connect(self.list_of_stages_widget.redraw_plot)

        self.list_of_stages_widget.redraw_plot_signal.connect(
            self.plot_widget.plot_data
        )

        # Layout
        main_layout = QtWidgets.QVBoxLayout(self)

        main_layout.addWidget(self.files_widget)

        horizontal_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(horizontal_layout, 2)

        list_layout = QtWidgets.QVBoxLayout()
        horizontal_layout.addLayout(list_layout)
        horizontal_layout.addWidget(self.stage_properties_widget, 0)

        list_layout.addWidget(self.list_of_stages_widget)

        buttons_list_layout = QtWidgets.QHBoxLayout()
        buttons_list_layout.addStretch(1)
        buttons_list_layout.addWidget(redraw_button)
        buttons_list_layout.addWidget(self.list_of_stages_plus_button)
        buttons_list_layout.addWidget(self.list_of_stages_minus_button)
        list_layout.addLayout(buttons_list_layout)

        main_layout.addWidget(self.plot_widget, 3)

    def toggle_visibility(self):
        self.setVisible(not self.isVisible())
