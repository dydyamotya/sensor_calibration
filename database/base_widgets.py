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
        self.database_model = model
        self.key = key
        self.setEditable(True)
        self.fill_with_values()

        self.activated.connect(self.on_activated_event)

    def get_current_model_values(self):
        return tuple(map(lambda x: x.__getattribute__(self.key), self.database_model.select()))

    def fill_with_values(self):
        self.clear()
        self.addItems(self.get_current_model_values())

    def on_activated_event(self, index: int):
        self.set_new_value(self.currentText())
        self.enter_hit_signal.emit(self.currentText())

    def set_new_value(self, value: str):
        if value not in self.get_current_model_values():
            self.database_model.create(**{self.key: value})
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
            to_return = getattr(self.database_model.get(getattr(self.database_model, self.key) == self.currentText()), "id")
        except:
            self.set_new_value("Default")
            return getattr(self.database_model.get(getattr(self.database_model, self.key) == self.currentText()), "id")
        else:
            return to_return

    def get_model_object(self, value: str):
        try:
            return self.database_model.get(getattr(self.database_model, self.key) == value)
        except IndexError:
            return None
        except self.database_model.DoesNotExist:
            return None

    def get_current_model_object(self):
        return self.get_model_object(self.currentText())


class DatabaseNonleaderComboboxWidget(QtWidgets.QComboBox):
    def __init__(self, leader_widget: DatabaseLeaderComboboxWidget, key: str, keys: typing.Sequence,
                 values: typing.Sequence, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.leader_widget = leader_widget
        self.key = key
        self.mapping = dict(zip(keys, values))
        self.keys = keys
        self.values = values
        self.addItems(keys)


    def on_leader_value_change(self, value: str):
        logger.debug("On leader value change")
        model_object = self.leader_widget.get_model_object(value)
        if model_object is not None:
            possible_answer = getattr(model_object, self.key)
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

    def save_to_database(self):
        index = self.currentIndex()
        database_model_object = self.leader_widget.get_current_model_object()
        if database_model_object is not None:
            value = self.mapping[self.keys[index]]
            setattr(database_model_object, self.key, value)
            database_model_object.save()

    def get_value(self):
        try:
            return self.mapping[self.currentText()]
        except KeyError:
            return ''


class DatabaseNonleaderTableWidget(QtWidgets.QTableWidget):

    def __init__(self, leader_widget: DatabaseLeaderComboboxWidget, key: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.leader_widget = leader_widget
        self.model_object = None
        self.key = key
        self.setColumnCount(2)
        self.setRowCount(3)

    def load_data(self, data):
        self.clear()
        for idx, (key, value) in enumerate(data.items()):
            self.setItem(idx, 0, QTableWidgetItem(key))
            self.setItem(idx, 1, QTableWidgetItem(value))

    def dump_data(self, process_func=None) -> OrderedDict:
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
        model_object = self.leader_widget.get_model_object(value)
        if model_object is not None:
            possible_answer = getattr(model_object, self.key)
            logger.debug(possible_answer)
            data = json.loads(possible_answer, object_pairs_hook=OrderedDict)
            self.load_data(data)
            self.check_if_data_is_okey()

    def save_to_database(self):
        database_model_object = self.leader_widget.get_current_model_object()
        if database_model_object is not None:
            setattr(database_model_object, self.key, json.dumps(self.dump_data()))
            database_model_object.save()

    def check_if_data_is_okey(self):
        data = self.dump_data(process_func=float)
        normal_default_data = {
            "100 KOhm": '100000',
            "1.1 MOhm": '1100000',
            "11.1 MOhm": '11100000',
        }
        if tuple(data.keys())[0] == "":
            self.load_data(normal_default_data)
            self.save_to_database()


    def get_data(self):
        data = self.dump_data(process_func=float)
        if data is not None:
            r4_str_values = tuple(data.keys())
            r4_combobox_dict = ResistanseDict(zip(r4_str_values, data.values()))
            r4_range_dict = dict(zip(r4_str_values, range(1, len(r4_str_values) + 1)))
            return r4_str_values, r4_combobox_dict, r4_range_dict


    def on_multirange_state_change(self, multirange_state: bool):
        self.setEnabled(multirange_state)
        if multirange_state:
            self.check_if_data_is_okey()

