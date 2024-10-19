from .program_generator import ProgramGenerator
from program_dataclasses.operation_classes import MSOneTickClass
from sensor_system import MS_Uni, MS_ABC
from time import sleep, time
import threading
import traceback
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ProgramRunner:
    def __init__(
        self,
        program_generator: ProgramGenerator,
        get_ms_method,
        get_sensor_types_list,
        get_convert_funcs,
        solid_mode,
        multirange,
        send_gasstate_signal,
        checkbox_state,
        queues_holder,
        stop_signal,
        running_signal,
        sensor_number,
        sensors_critical_values_top,
        sensors_critical_values_bottom,
    ):
        self.stopped = True
        self.stop_signal = stop_signal
        self.running_signal = running_signal
        self.program_generator = program_generator
        self.program = self.program_generator.parse_program_to_queue()
        self.get_ms_method = get_ms_method
        self.get_sensor_types_list = get_sensor_types_list
        self.convert_funcs = get_convert_funcs("R")
        self.convert_funcs_2 = get_convert_funcs("V")
        self.solid_mode = solid_mode
        self.multirange: bool = multirange
        self.send_gasstate_signal = send_gasstate_signal
        self.checkbox_state = checkbox_state
        self.sensor_number = sensor_number
        self.thread = None
        self.queues_holder = queues_holder
        self.sensors_critical_values_bottom = sensors_critical_values_bottom
        self.sensors_critical_values_top = sensors_critical_values_top

        self.need_to_analyze = self.multirange and (self.solid_mode is None)

    def start(self):
        self.stopped = False
        self.thread = threading.Thread(target=self.cycle)
        self.thread.start()

    def stop(self):
        self.stopped = True

    def join(self):
        if self.thread is not None:
            self.thread.join()

    def cycle(self):
        ms: MS_Uni = self.get_ms_method()
        time_0 = time()
        time_sleep = self.program_generator.program.settings.step / 100
        sensor_types_list = self.get_sensor_types_list()
        sensor_states = [
            1,
        ] * self.sensor_number
        sensor_stab_up_states = [
            True,
        ] * self.sensor_number
        sensor_stab_down_states = [
            True,
        ] * self.sensor_number
        sensors_critical_values_top = self.sensors_critical_values_top
        sensors_critical_values_bottom = self.sensors_critical_values_bottom

        while not self.stopped:
            try:
                time_next, (temperatures, gas_state, stage_num, stage_type) = next(
                    self.program
                )
            except StopIteration:
                self.stop_signal.emit()
                self.stopped = True
            else:
                self.running_signal.emit()
                temperatures = temperatures[: self.sensor_number]
                time_next_plus_t0 = time_0 + time_next
                while time() < time_next_plus_t0:
                    sleep(time_sleep)
                try:
                    logger.debug(f"{time()} {time_next_plus_t0} {time_next}")
                    if self.checkbox_state():
                        converted = self.convert_to_voltages(temperatures)
                        us, rs = ms.full_request(
                            converted,
                            request_type=MS_ABC.REQUEST_U,
                            sensor_types_list=sensor_types_list,
                        )
                    else:
                        converted = self.convert_to_resistances(temperatures)
                        us, rs = ms.full_request(
                            converted,
                            request_type=MS_ABC.REQUEST_R,
                            sensor_types_list=sensor_types_list,
                        )
                except MS_ABC.MSException:
                    self.stop_signal.emit()
                    self.clear_ms_state(ms)
                    raise
                else:
                    try:
                        self.send_gasstate_signal.emit(gas_state)
                    except:
                        logger.error(traceback.format_exc())
                    finally:
                        self.queues_holder.put(
                            MSOneTickClass(
                                us,
                                rs,
                                time_next_plus_t0,
                                time_next,
                                temperatures,
                                gas_state,
                                stage_num,
                                stage_type,
                                sensor_states,
                                converted,
                            )
                        )
                        self.analyze_us(
                            ms,
                            us,
                            sensor_states,
                            sensor_stab_up_states,
                            sensor_stab_down_states,
                            sensors_critical_values_top,
                            sensors_critical_values_bottom,
                        )
        self.clear_ms_state(ms)

    def clear_ms_state(self, ms: MS_Uni):
        ms.clear_state(self.get_sensor_types_list())
        ms.close()

    def convert_to_resistances(self, temperatures) -> tuple:
        return tuple(func(t) for t, func in zip(temperatures, self.convert_funcs))

    def convert_to_voltages(self, temperatures) -> tuple:
        return tuple(func(t) for t, func in zip(temperatures, self.convert_funcs_2))

    def analyze_us(
        self,
        ms: MS_Uni,
        us: np.ndarray,
        sensor_states: list,
        sensor_stab_up_states: list,
        sensor_stab_down_states: list,
        sensors_critical_values_top: dict,
        sensors_critical_values_bottom: dict,
    ):
        if self.need_to_analyze:
            i = 0
            for idx, u in enumerate(us):
                sensor_state = sensor_states[idx]
                top_critical_value = sensors_critical_values_top[sensor_state][idx]
                bottom_critical_value = sensors_critical_values_bottom[sensor_state][
                    idx
                ]
                if u > top_critical_value and sensor_stab_up_states[idx]:
                    sensor_states[idx] = min(sensor_states[idx] + 1, 3)
                    if sensor_states[idx] == 3:
                        sensor_stab_up_states[idx] = False
                    sensor_stab_down_states[idx] = True
                    i += 1
                if u < bottom_critical_value and sensor_stab_down_states[idx]:
                    sensor_states[idx] = max(sensor_states[idx] - 1, 1)
                    sensor_stab_up_states[idx] = True
                    if sensor_states[idx] == 1:
                        sensor_stab_down_states[idx] = False
                    i += 1
            if i > 0:
                ms.send_measurement_range(sensor_states)
        else:
            if self.multirange:
                new_modes = self.solid_mode()
                if not all(
                    mode == prev_mode
                    for mode, prev_mode in zip(new_modes, sensor_states)
                ):
                    ms.send_measurement_range(new_modes)
                    for i in range(len(sensor_states)):
                        sensor_states[i] = new_modes[i]

    def isStopped(self) -> bool:
        return self.stopped
