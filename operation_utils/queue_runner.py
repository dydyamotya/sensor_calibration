from queue import Queue
from program_dataclasses.operation_classes import MSOneTickClass
import threading
import pathlib
import datetime
from time import sleep
import struct

import logging

logger = logging.getLogger(__name__)

class QueueRunner:
    def __init__(
        self,
        queue: Queue,
        converters_func_voltage_to_r,
        multirange_state_func,
        save_folder,
    ):
        self.queue = queue
        self.thread = None
        self.hold_method = None
        self.stopped = True
        self.filename = None
        self.save_folder = save_folder
        self.converter_funcs_dicts = converters_func_voltage_to_r
        self.multirange_state_func = multirange_state_func
        self._meas_values_tuple = None
        self.meas_tuple_lock = threading.Lock()
        self.bin_write_struct = None

    def set_hold(self, hold_method):
        self.hold_method = hold_method

    def drop_hold_method(self):
        self.hold_method = None

    def get_meas_tuple(self):
        with self.meas_tuple_lock:
            return self._meas_values_tuple

    def set_meas_tuple(self, values):
        with self.meas_tuple_lock:
            self._meas_values_tuple = values

    def start(self):
        if self.hold_method is not None and self.stopped:
            self.stopped = False
            self.thread = threading.Thread(target=self.cycle)
            self.filename = (
                pathlib.Path(self.save_folder)
                / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            ).with_suffix(".txt")
            self.binary_filename = (
                pathlib.Path(self.save_folder)
                / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            ).with_suffix(".dat")
            self.bin_write_struct = None
            self.thread.start()

    def join(self):
        if self.thread is not None:
            self.thread.join()

    def cycle(self):
        fd_bin = self.binary_filename.open("wb")
        converter_funcs = self.converter_funcs_dicts()
        multirange = self.multirange_state_func()
        while not self.stopped:
            sleep(0.02)
            if not self.queue.empty():
                self.one_cycle_step(multirange, converter_funcs, fd_bin)
        while not self.queue.empty():
            self.one_cycle_step(multirange, converter_funcs, fd_bin)

        fd_bin.close()

    def one_cycle_step(self, multirange: bool, converter_funcs, fd_bin):
        one_tick_data = self.queue.get()
        if multirange:
            sensor_resistances = tuple(
                converter_func_dict[sensor_state](u)
                for converter_func_dict, u, sensor_state in zip(
                    converter_funcs, one_tick_data.us, one_tick_data.sensor_states
                )
            )
        else:
            sensor_resistances = tuple(
                converter_func_dict(u)
                for converter_func_dict, u, sensor_state in zip(
                    converter_funcs, one_tick_data.us, one_tick_data.sensor_states
                )
            )
        logger.debug(f"Call in cycle")
        self.set_meas_tuple(
            (one_tick_data.us,
             one_tick_data.rs,
             sensor_resistances,
             one_tick_data.sensor_states,
             one_tick_data.temperatures,
             one_tick_data.converted)
        )
        self.hold_method((sensor_resistances, one_tick_data.rs, one_tick_data.time_next))
        if self.bin_write_struct is None:
            sensors_number = len(one_tick_data.rs)
            self.bin_write_struct = struct.Struct(
                "<f" + sensors_number * 4 * "f" + "BIH" + sensors_number * "B"
            )
            fd_bin.write(struct.pack("<B", sensors_number))
        fd_bin.write(
            self.bin_write_struct.pack(
                one_tick_data.time_next,
                *one_tick_data.us,
                *one_tick_data.rs,
                *sensor_resistances,
                *one_tick_data.temperatures,
                one_tick_data.gas_state,
                one_tick_data.stage_num,
                one_tick_data.stage_type,
                *one_tick_data.sensor_states,
            )
        )

    def stop(self):
        self.stopped = True
