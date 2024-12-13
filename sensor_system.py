import struct
import typing
from typing import List
from abc import ABC, abstractmethod

import numpy as np
import serial

import logging 

logger = logging.getLogger(__name__)

import itertools, functools, operator


class MS_ABC(ABC):
    """Класс реализует базовый класс для сенсорных приборов"""
    BEGIN_KEY = bytes((0xAA, 0x55, 0xAA))
    END_KEY = bytes((0x0D, 0x0A))
    SEND_U = bytes((0x08,))
    SEND_R = bytes((0x88,))
    SEND_M = bytes((0x20,))
    SEND_CSS_1_4 = 0x01
    SEND_CSS_5_8 = 0x02
    SEND_CSS_9_12 = 0x04

    REQUEST_U = 0
    REQUEST_R = 1

    class MSException(Exception):
        pass

    @abstractmethod
    def __init__(self, port=None, heater_resistance_converter=100):
        self.ser = serial.Serial(port,
                                 baudrate=115200,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE,
                                 timeout=1)

        self.sensors_number = None  # Must be implemented by child
        self.struct = None  # Must be implemented by child
        self.heater_resistance_converter = heater_resistance_converter
        self.reciprocal_heater_resistance_converter = 1 / self.heater_resistance_converter

    def set_port(self, port: str):
        self.ser.port = port

    def close(self):
        self.ser.close()

    def open(self):
        try:
            self.ser.open()
        except serial.SerialException:
            logger.debug("Bad port. Not opened")
        except Exception as e:
            raise e

    @staticmethod
    def _convert_u(value: float) -> bytes:
        reciprocal_step = 65535 / 5  # step is 5/65535
        if value >= 5:
            value = 5
        elif value < 0:
            raise Exception("U must be larger than 0")
        return int(value * reciprocal_step).to_bytes(2, "little", signed=False)

    @staticmethod
    def _back_convert_u(value: int) -> float:
        return value / (2 ** 24) * 5

    def _convert_r(self, value: float) -> bytes:
        if value < 0:
            raise Exception("R must be larger than 0")
        return int(value * self.heater_resistance_converter).to_bytes(2, "little", signed=False)

    def _back_convert_r(self, value: int) -> float:
        return value * self.reciprocal_heater_resistance_converter

    def _request_test(self):
        recieved = b""
        while recieved[-2:] != self.END_KEY:
            recieved += self.ser.read(1)
        return recieved

    def full_request(self, values: typing.Collection, request_type, sensor_types_list: typing.Sequence) -> typing.Tuple[np.ndarray, np.ndarray]:
        """:returns us, rs
        us - voltage, measured on sensors,
        rs - resistance of heaters"""
        logger.debug("Full request in")
        logger.debug(f"Sending values, {values}")
        self._send(values, request_type, sensor_types_list)
        logger.debug(f"recieving values")
        return self.recieve_answer()

    def recieve_answer(self) -> typing.Tuple[np.ndarray, np.ndarray]:
        logger.debug("Start recieving")
        us = np.empty(self.sensors_number, dtype=np.float32)
        rs = np.empty(self.sensors_number, dtype=np.float32)
        # recieved = bytes()
        begin_key_index = 3
        end_key = 2
        data_one_sensor_length = 6
        r_index = 2
        u_index = 5
        recieved = self.ser.read(
            begin_key_index + self.sensors_number * data_one_sensor_length + end_key)
        logger.debug(recieved)
        if recieved[-end_key:] != self.END_KEY:
            logger.debug(recieved)
            while self.ser.read(1):
                pass
            raise MS_ABC.MSException("END_KEY is not matching")
        if recieved[:begin_key_index] != self.BEGIN_KEY:
            logger.debug(recieved)
            raise MS_ABC.MSException("BEGIN_KEY is not matching")
        for i in range(self.sensors_number):
            start_index = begin_key_index + i * data_one_sensor_length
            rs[i] = self._back_convert_r(
                int.from_bytes(recieved[start_index:start_index + r_index],
                               "little", signed=False))
            us[i] = self._back_convert_u(
                int.from_bytes(recieved[start_index + r_index:start_index + u_index],
                               "little", signed=False))
        logger.debug(f"{us}{rs}")
        return us, rs

    def send_measurement_range(self, values: typing.Union[typing.Iterable, typing.Sized]):
        if len(values) != self.sensors_number:
            raise MS_ABC.MSException("Too few values for setting measurement range")
        sensor_mask = {
            1: 0b11,
            2: 0b10,
            3: 0b00
        }
        self.ser.write(self.BEGIN_KEY)
        self.ser.write(self.SEND_M)
        result = 0
        for idx, value in enumerate(values):
            result |= (sensor_mask[value] << (idx * 2))
        self.ser.write(result.to_bytes(int(self.sensors_number / 4),
                                       "little", signed=False))
        self.ser.write(self.END_KEY)

    def recieve_measurement_range_answer(self) -> bytes:
        recieved = self.ser.read(6)
        if recieved[-2:] != self.END_KEY:
            raise MS_ABC.MSException("END_KEY in range is not matching")
        if recieved[:3] != self.BEGIN_KEY:
            raise MS_ABC.MSException("BEGIN_KEY in range is not matching")
        if recieved[3:4] != self.SEND_M:
            raise MS_ABC.MSException("SEND_M in range is not matching")
        return recieved

    def _form_send_key(self, key: bytes, sensor_types_list: typing.Collection):
        return bytes((functools.reduce(operator.or_, itertools.chain(key, sensor_types_list)), ))


    # Abstract methods
    # =========================
    @abstractmethod
    def _send(self, values: typing.Collection, request_type: int, sensor_types_list: typing.Collection):
        raise NotImplementedError

    @abstractmethod
    def _send_test(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def action(self, values):
        raise NotImplementedError

    @abstractmethod
    def clear_after_stop(self):
        raise NotImplementedError


class MS12(MS_ABC):
    """Класс реализует протокол общения с 12-сенсорным прибором."""

    def __init__(self, port=None, heater_resistance_converter=100):
        super().__init__(port=port, heater_resistance_converter=heater_resistance_converter)
        self.sensors_number = 12
        self.struct = struct.Struct(">" + (self.sensors_number + 1) * "f")

    def _send(self, values: typing.Collection, request_type: int, sensor_types_list: typing.Collection) -> int:
        if len(values) != self.sensors_number:
            raise MS_ABC.MSException("Must be iterable of 12 length")
        if request_type == self.REQUEST_U:
            send_key, convert_func = self.SEND_U, self._convert_u
        elif request_type == self.REQUEST_R:
            send_key, convert_func = self.SEND_R, self._convert_r
        else:
            raise MS_ABC.MSException(f"Wrong request_type arg, with value {request_type}")
        send_key = self._form_send_key(send_key, sensor_types_list)
        message = self.BEGIN_KEY + send_key + functools.reduce(operator.add, (convert_func(number) for number in values)) + bytes(8) + self.END_KEY
        logger.debug(str(message))
        return self.ser.write(message)

    def _send_test(self):
        send_message = self.BEGIN_KEY + self.SEND_U + bytes(16 * 2) + self.END_KEY
        return self.ser.write(send_message)

    def clear_after_stop(self):
        self._send_test()

    def action(self):
        pass


class MS4(MS_ABC):
    def __init__(self, port=None, heater_resistance_converter=100):
        super().__init__(port=port, heater_resistance_converter=heater_resistance_converter)
        self.sensors_number = 4
        self.struct = struct.Struct(">fffff")

    def action(self, values):
        pass

    def _send(self, values: typing.Collection, request_type: int, sensor_types_list: typing.Collection) -> int:
        if len(values) != self.sensors_number:
            raise MS_ABC.MSException("Must be iterable of 4 length")
        if request_type == self.REQUEST_U:
            send_key, convert_func = self.SEND_U, self._convert_u
        elif request_type == self.REQUEST_R:
            send_key, convert_func = self.SEND_R, self._convert_r
        else:
            raise MS_ABC.MSException(f"Wrong request_type arg, with value {request_type}")
        send_key = self._form_send_key(send_key, sensor_types_list)
        message = self.BEGIN_KEY + send_key + functools.reduce(operator.add, (convert_func(number) for number in values)) + self.END_KEY
        logger.debug(str(message))
        return self.ser.write(message)

    def _send_test(self, *args, **kwargs):
        send_message = self.BEGIN_KEY + self.SEND_U + bytes(4 * 2) + self.END_KEY
        return self.ser.write(send_message)

    def clear_after_stop(self):
        self._send_test()


class MSEmulator(MS_ABC):
    """In fact, I only need to realize the full_request method and send_measurement_range"""

    def __init__(self, port=None, sensor_number=4, heater_resistance_converter=100):
        super().__init__(port=port, heater_resistance_converter=heater_resistance_converter)
        self.sensors_number = sensor_number
        self.struct = struct.Struct(">f" + self.sensors_number * "f")

    def full_request(self, values: np.ndarray, request_type, sensor_types_list):
        us = np.ones(shape=(self.sensors_number,)) * np.random.normal(0, 2, self.sensors_number) - values * 2
        rs = np.ones(shape=(self.sensors_number,)) * 15 + np.random.normal(0, 0.2, self.sensors_number) + values * 5
        return us, rs

    def send_measurement_range(self, values):
        pass

    @staticmethod
    def revieve_measurement_range_answer():
        return bytes(7)

    def _send(self, *args, **kwargs):
        pass

    def _send_test(self, *args, **kwargs):
        pass

    def action(self, values):
        pass

class MS_Uni():
    def __init__(self, sensor_number, port, heater_resistance_converter):
        self.sensors_number = sensor_number
        if sensor_number == 4:
            self.ms = MS4(port, heater_resistance_converter=heater_resistance_converter)
        elif sensor_number == 12:
            self.ms = MS12(port, heater_resistance_converter=heater_resistance_converter)
        else:
            raise Exception("Wrong port number")

    def send_measurement_range(self, values: List[int]):
        self.ms.send_measurement_range(values[:self.sensors_number])
        self.ms.recieve_measurement_range_answer()

    def full_request(self, values, request_type = MS_ABC.REQUEST_U, sensor_types_list = None) -> typing.Tuple[np.ndarray, np.ndarray]:
        values = list(values)
        if sensor_types_list is None:
            sensor_types_list = []
        if request_type == MS_ABC.REQUEST_U:
            for sensor_type in sensor_types_list:
                if sensor_type == MS_ABC.SEND_CSS_1_4:
                    for i in range(0, 4):
                        values[i] = min(4, values[i])
                if sensor_type == MS_ABC.SEND_CSS_5_8:
                    for i in range(4, 8):
                        values[i] = min(4, values[i])
                if sensor_type == MS_ABC.SEND_CSS_9_12:
                    for i in range(8, 12):
                        values[i] = min(4, values[i])
        return self.ms.full_request(values[:self.sensors_number], request_type, sensor_types_list)

    def clear_state(self, sensor_types_list=None):
        self.full_request([0,] * self.ms.sensors_number, sensor_types_list=sensor_types_list)

    def close(self):
        self.ms.close()

