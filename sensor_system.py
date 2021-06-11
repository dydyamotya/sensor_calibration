import struct
import typing
from abc import ABC, abstractmethod

import numpy as np
import serial


class MS_ABC(ABC):
    """Класс реализует базовый класс для сенсорных приборов"""
    BEGIN_KEY = bytes((0xAA, 0x55, 0xAA))
    END_KEY = bytes((0x0D, 0x0A))
    SEND_U = bytes((0x08,))
    SEND_R = bytes((0x88,))
    SEND_M = bytes((0x20,))

    REQUEST_U = 0
    REQUEST_R = 1

    class MSException(Exception):
        pass

    @abstractmethod
    def __init__(self, port=None):
        self.ser = serial.Serial(port,
                                 baudrate=115200,
                                 bytesize=serial.EIGHTBITS,
                                 parity=serial.PARITY_NONE,
                                 stopbits=serial.STOPBITS_ONE)

        self.sensors_number = None  # Must be implemented by child
        self.struct = None  # Must be implemented by child

    def set_port(self, port: str):
        self.ser.port = port

    def open(self):
        try:
            self.ser.open()
        except serial.SerialException:
            print("Bad port. Not opened")
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

    @staticmethod
    def _convert_r(value: float) -> bytes:
        reciprocal_step = 100  # step is 0.01 Ohm
        if value < 0:
            raise Exception("R must be larger than 0")
        return int(value * reciprocal_step).to_bytes(2, "little", signed=False)

    @staticmethod
    def _back_convert_r(value: int) -> float:
        return value * 0.01

    def _request_test(self):
        recieved = b""
        while recieved[-2:] != self.END_KEY:
            recieved += self.ser.read(1)
        return recieved

    def send_us(self, us: typing.Iterable) -> int:
        """:returns number of sent bytes"""
        return self._send(us, self._convert_u)

    def send_rs(self, rs: typing.Iterable):
        """:returns number of sent bytes"""
        return self._send(rs, self._convert_r)

    def full_request(self, values: typing.Iterable, request_type):
        """:returns us, rs
        us - voltage, measured on sensors,
        rs - resistance of heaters"""
        # todo: do you really need that method????
        if request_type == self.REQUEST_R:
            self.send_rs(values)
            return self.recieve_answer()
        elif request_type == self.REQUEST_U:
            self.send_us(values)
            return self.recieve_answer()
        else:
            raise MS_ABC.MSException("Wrong request type")

    def recieve_answer(self) -> typing.Tuple[np.ndarray, np.ndarray]:
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
        if recieved[-end_key:] != self.END_KEY:
            print(recieved)
            raise MS_ABC.MSException("END_KEY is not matching")
        if recieved[:begin_key_index] != self.BEGIN_KEY:
            print(recieved)
            raise MS_ABC.MSException("BEGIN_KEY is not matching")
        for i in range(self.sensors_number):
            start_index = begin_key_index + i * data_one_sensor_length
            rs[i] = self._back_convert_r(
                int.from_bytes(recieved[start_index:start_index + r_index],
                               "little", signed=False))
            us[i] = self._back_convert_u(
                int.from_bytes(recieved[start_index + r_index:start_index + u_index],
                               "little", signed=False))
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
        self.ser.write(result.to_bytes(self.sensors_number / 4,
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

    # Abstract methods
    # =========================
    @abstractmethod
    def _send(self, *args, **kwargs):
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

    def __init__(self, port=None):
        super().__init__(port=port)
        self.sensors_number = 12
        self.struct = struct.Struct(">" + (self.sensors_number + 1) * "f")

    def _send(self, values: typing.Union[typing.Iterable, typing.Sized], convert_func: typing.Callable) -> int:
        if len(values) != self.sensors_number:
            raise MS_ABC.MSException("Must be iterable of 12 length")
        sent_bytes = 0
        sent_bytes += self.ser.write(self.BEGIN_KEY)
        sent_bytes += self.ser.write(self.SEND_U)
        for number in values:
            sent_bytes += self.ser.write(convert_func(number))
        sent_bytes += self.ser.write(bytes(8))  # protocol issue
        sent_bytes += self.ser.write(self.END_KEY)
        return sent_bytes

    def _send_test(self):
        send_message = self.BEGIN_KEY + self.SEND_U + bytes(16 * 2) + self.END_KEY
        return self.ser.write(send_message)

    def clear_after_stop(self):
        self._send_test()

    def action(self):
        pass


class MS4(MS_ABC):
    def __init__(self, port=None):
        super().__init__(port=port)
        self.sensors_number = 4
        self.struct = struct.Struct(">fffff")

    def action(self, values):
        pass

    def _send(self, values: typing.Union[typing.Iterable, typing.Sized], convert_func: typing.Callable) -> int:
        if len(values) != self.sensors_number:
            raise MS_ABC.MSException("Must be iterable of 4 lenght")
        sent_bytes = 0
        sent_bytes += self.ser.write(self.BEGIN_KEY)
        sent_bytes += self.ser.write(self.SEND_U)
        for number in values:
            sent_bytes += self.ser.write(convert_func(number))
        sent_bytes += self.ser.write(self.END_KEY)
        return sent_bytes

    def _send_test(self, *args, **kwargs):
        send_message = self.BEGIN_KEY + self.SEND_U + bytes(4 * 2) + self.END_KEY
        return self.ser.write(send_message)

    def clear_after_stop(self):
        self._send_test()


class MSEmulator(MS_ABC):
    """In fact, I only need to realize the full_request method and send_measurement_range"""

    def __init__(self, port=None, sensor_number=4):
        super().__init__(port=port)
        self.sensors_number = sensor_number
        self.struct = struct.Struct(">f" + self.sensors_number * "f")

    def full_request(self, values: np.ndarray, request_type):
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
