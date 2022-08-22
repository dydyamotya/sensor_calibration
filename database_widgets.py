import typing

from PySide2 import QtWidgets, QtGui, QtCore
from peewee import Model
from typing import Type
import logging

logger = logging.getLogger(__name__)


class DatabaseLeaderComboboxWidget(QtWidgets.QComboBox):
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
        self.clear()
        self.mapping = dict(zip(keys, values))
        self.keys = keys
        self.values = values
        self.addItems(keys)

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
