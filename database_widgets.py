import typing
import json
from collections import OrderedDict, UserDict

from PySide2 import QtWidgets, QtGui, QtCore
from PySide2.QtCore import Signal
from PySide2.QtWidgets import QTableWidgetItem
from peewee import Model
from typing import Type
import logging

logger = logging.getLogger(__name__)

class ResistanseDict(UserDict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        else:
            try:
                return float(key)
            except ValueError:
                raise

class DatabaseLeaderComboboxWidget(QtWidgets.QComboBox):

    enter_hit_signal = Signal(str)
    def __init__(self, model: Type[Model], key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = model
        self.key = key
        self.setEditable(True)
        self.fill_with_values()

    def get_current_model_values(self):
        return tuple(map(lambda x: x.__getattribute__(self.key), self.model.select()))

    def fill_with_values(self):
        self.clear()
        self.addItems(self.get_current_model_values())

    def set_new_value(self, value: str):
        if value not in self.get_current_model_values():
            self.model.create(**{self.key: value})
        self.fill_with_values()
        self.setCurrentIndex(self.findText(value))

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Return:
            self.set_new_value(self.currentText())
            self.enter_hit_signal.emit(self.currentText())
        else:
            super(DatabaseLeaderComboboxWidget, self).keyPressEvent(event)

    def get_value(self):
        return self.currentText()

    def get_id(self):
        try:
            to_return = getattr(self.model.get(getattr(self.model, self.key) == self.currentText()), "id")
        except:
            self.set_new_value("Default")
            return getattr(self.model.get(getattr(self.model, self.key) == self.currentText()), "id")
        else:
            return to_return


class DatabaseNonleaderComboboxWidget(QtWidgets.QComboBox):
    def __init__(self, leader_widget: DatabaseLeaderComboboxWidget, key: str, keys: typing.Sequence,
                 values: typing.Sequence, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.leader_widget = leader_widget
        self.model = leader_widget.model
        self.leader_key = leader_widget.key
        self.key = key
        self.mapping = dict(zip(keys, values))
        self.keys = keys
        self.values = values
        self.addItems(keys)
        self.activated.connect(self.on_nonleader_value_changed)

    def refresh_values(self, keys: typing.Sequence, values: typing.Sequence):

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

    def on_leader_value_change(self, value: str):
        logger.debug("On leader value change")
        try:
            first_answer = self.model.get(getattr(self.model, self.leader_key) == value)
        except IndexError:
            return
        except self.model.DoesNotExist:
            return
        else:
            possible_answer = getattr(first_answer, self.key)
            reciprocal_dict = dict(zip(self.mapping.values(), self.mapping.keys()))
            logger.debug(possible_answer)
            try:
                rc_answer = reciprocal_dict[possible_answer]
            except KeyError:
                self.setCurrentIndex(0)
            else:
                answer_idx: int = self.findText(rc_answer)
                if answer_idx >= 0:
                    self.setCurrentIndex(answer_idx)
                else:
                    self.setCurrentIndex(0)
            finally:
                logger.debug(self.currentText())

    def on_nonleader_value_changed(self, index: int):
        first_answer = self.model.get(getattr(self.model, self.leader_key) == self.leader_widget.currentText())
        value = self.mapping[self.keys[index]]
        setattr(first_answer, self.key, value)
        first_answer.save()

    def get_value(self):
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return ''


class DatabaseNonleaderTableWidget(QtWidgets.QTableWidget):

    someValueChanged = Signal(int)
    def __init__(self, leader_widget: DatabaseLeaderComboboxWidget, key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.leader_widget = leader_widget
        self.model = leader_widget.model
        self.leader_key = leader_widget.key
        self.key = key
        self.setColumnCount(2)
        self.setRowCount(3)

        self.itemChanged.connect(self.on_nonleader_value_changed)

    def load_data(self, data):
        self.clear()
        for idx, (key, value) in enumerate(data.items()):
            self.setItem(idx, 0, QTableWidgetItem(key))
            self.setItem(idx, 1, QTableWidgetItem(value))

    def dump_data(self, process_func=None):
        data = OrderedDict()
        for idx in range(self.rowCount()):
            key_item = self.item(idx, 0)
            if key_item is not None:
                key_data = key_item.text()
            else:
                key_data = ""
            value_item = self.item(idx, 1)
            if value_item is not None:
                value_data = value_item.text()
            else:
                value_data = "0"
            if process_func is None:
                data[key_data] = value_data
            else:
                try:
                    data[key_data] = process_func(value_data)
                except:
                    data[key_data] = 0
        return data

    def on_leader_value_change(self, value: str):
        logger.debug("On leader value change")
        try:
            first_answer = self.model.get(getattr(self.model, self.leader_key) == value)
        except IndexError:
            return
        except self.model.DoesNotExist:
            return
        else:
            possible_answer = getattr(first_answer, self.key)
            logger.debug(possible_answer)
            data = json.loads(possible_answer, object_pairs_hook=OrderedDict)
            self.load_data(data)

    def on_nonleader_value_changed(self, item: QTableWidgetItem):
        first_answer = self.model.get(getattr(self.model, self.leader_key) == self.leader_widget.currentText())
        setattr(first_answer, self.key, json.dumps(self.dump_data()))
        self.someValueChanged.emit(0)
        first_answer.save()

    def get_data(self):
        data = self.dump_data(process_func=float)
        r4_str_values = tuple(data.keys())
        r4_combobox_dict = ResistanseDict(zip(r4_str_values, data.values()))
        r4_range_dict = dict(zip(r4_str_values, range(1, len(r4_str_values))))
        return r4_str_values, r4_combobox_dict, r4_range_dict

