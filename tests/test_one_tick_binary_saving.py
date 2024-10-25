import unittest
import struct
import numpy as np
from program_dataclasses.operation_classes import MSOneTickClass


class TestOneTickBinaryConverting(unittest.TestCase):
    def test_converting(self):
        sensors_number = 4

        one_tick_data = MSOneTickClass(
            us=np.array([4.569469, 4.54184, 4.562616, 4.5251384], dtype=np.float32),
            rs=np.array([655.35, 655.35, 655.35, 655.35], dtype=np.float32),
            time_next_plus_t9=1729875532.4046245,
            time_next=0,
            temperatures=(500.0, 500.0, 500.0, 500.0),
            gas_state=0,
            stage_num=0,
            stage_type=2,
            sensor_states=[1, 1, 1, 1],
            converted=(
                np.array(4.94354554),
                np.array(4.93821851),
                np.array(4.9371525),
                np.array(4.9396751),
            ),
        )

        sensor_resistances = [4,4,4,4]
        bin_write_struct = struct.Struct(
            "<f" + sensors_number * 4 * "f" + "BIH" + sensors_number * "B"
        )
        bin_write_struct.pack(
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
