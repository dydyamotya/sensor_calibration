from program_dataclasses.operation_classes import MSOneTickClass
from queue import Queue
from PySide2 import QtCore
from time import sleep
import typing

class CycleCollector(QtCore.QObject):
    one_cycle_data_collected_signal = QtCore.Signal(list)

    def __init__(self, queue: Queue[MSOneTickClass]):
        super().__init__()
        self.queue = queue
        self.is_stopped = True
        self.previous_stage_num = -1
        self.one_cycle_data: typing.List[MSOneTickClass] = []

    def cycle(self):
        while not self.is_stopped:
            sleep(0.02)
            if not self.queue.empty():
                self.process_one_element_in_queue()

    def process_one_element_in_queue(self):
        one_tick_data = self.queue.get()
        if self.previous_stage_num != one_tick_data.stage_num:
            self.process_one_whole_cycle()
        else:
            self.add_one_tick_to_already_collected_data(one_tick_data)

    def process_one_whole_cycle(self):
        # todo: need to do this method
        self.one_cycle_data.clear()

    def add_one_tick_to_already_collected_data(self, one_tick: MSOneTickClass):
        self.one_cycle_data.append(one_tick)


