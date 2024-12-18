import munch
import itertools
from scipy.interpolate import interp1d
import numpy as np
import logging
from typing import Tuple

from yaml import NodeEvent

logger = logging.getLogger(__name__)

class ProgramGeneratorException(Exception):
    pass

class ProgramGenerator:

    stages_counter = 0

    def __init__(self, program):
        self.program = munch.munchify(program)
        settings = self.program.settings
        settings.step = 1 / settings.frequency

    def parse_program_to_queue(self):
        self.reset_stage_number()
        settings = self.program.settings
        program = self.program.program
        full = zip(itertools.count(0, settings.step), ProgramGenerator._parse_all_program(program, settings))
        return full

    def calculate_full_time(self):
        self.reset_stage_number()
        return ProgramGenerator._calculate_full_time(self.program.program)

    def calculate_min_and_max_temperatures(self):
        self.reset_stage_number()
        return ProgramGenerator._calculate_min_and_max_temperatures(self.program.program)

    @classmethod
    def get_stage_number(cls):
        stage_num = cls.stages_counter
        cls.stages_counter += 1
        return stage_num

    @classmethod
    def reset_stage_number(cls):
        cls.stages_counter = 0

    @staticmethod
    def convert_temperatures(temperatures) -> tuple:
        if isinstance(temperatures, list):
            if len(temperatures) == 12:
                return tuple(temperatures)
            else:
                temp = [min(temperatures), ] * 12
                temp[:len(temperatures)] = temperatures
                return tuple(temp)
        else:
            return (temperatures, ) * 12
    @staticmethod
    def process_gas_state(gas_state, max_time, variable, variable_value):
        if isinstance(gas_state, munch.Munch):
            times = gas_state.time
            substates = gas_state.substates
            if variable is not None:
                substates = list(map(lambda x: eval(x.replace(variable, str(variable_value))), substates))
            times = [0] + times + [max_time]
            substates = substates + [substates[0], substates[0]]
            gas_get_func = interp1d(times, substates, kind="previous")
        else:
            gas_get_func = lambda x: gas_state
        return gas_get_func

    @staticmethod
    def process_gas_states_cycle(gas_states):
        for gas_stage in gas_states:
            if "template" in gas_stage:
                variable, start, end = gas_stage.template
                for j in range(start, end, 1):
                    for i in range(gas_stage.number):
                        if isinstance(gas_stage.state, list):
                            for sub_gas_state_ in itertools.chain(*[(sub_gas_stage.state,) * sub_gas_stage.number for sub_gas_stage in gas_stage.state]):
                                yield sub_gas_state_, variable, j
                        else:
                            yield gas_stage.state, variable, j
            else:
                for i in range(gas_stage.number):
                    if isinstance(gas_stage.state, list):
                        for sub_gas_state_ in itertools.chain(*[(sub_gas_stage.state,) * sub_gas_stage.number for sub_gas_stage in gas_stage.state]):
                            yield sub_gas_state_, None, None
                    else:
                        yield gas_stage.state, None, None

    @staticmethod
    def _parse_all_program(program, settings):
        for stage in program:
            if stage.type == "simple":
                yield from ProgramGenerator._process_simple(stage, settings)
            elif stage.type == "stepwise":
                yield from ProgramGenerator._process_stepwise(stage, settings)
            elif stage.type == "cyclic":
                yield from ProgramGenerator._process_cyclic(stage, settings)
            else:
                raise ProgramGeneratorException


    @staticmethod
    def _process_simple(stage, settings):
        stage_num = ProgramGenerator.get_stage_number()
        step = settings.step
        gas_state = stage.gas_state
        temperatures = ProgramGenerator.convert_temperatures(stage.temperature)
        for _ in np.arange(0, stage.time, step):
            yield temperatures, gas_state, stage_num, 0

    @staticmethod
    def _process_stepwise(stage, settings):
        step = settings.step
        temperature_step = -stage.temperature_step if stage.temperature_start > stage.temperature_stop else stage.temperature_step
        for temperature in np.arange(stage.temperature_start, stage.temperature_stop, temperature_step):
            converted_temperatures = ProgramGenerator.convert_temperatures(temperature)
            for cycle in range(stage.cycles):
                for gas_state in stage.gas_states:
                    stage_num = ProgramGenerator.get_stage_number()
                    for _ in np.arange(0, stage.time, step):
                        yield converted_temperatures, gas_state, stage_num, 1

    @staticmethod
    def _process_cyclic(stage, settings):
        step = settings.step
        temperatures = stage.temperatures
        func = interp1d(temperatures.time, temperatures.temperature)
        max_time = max(temperatures.time)
        for (gas_state, variable, variable_value), _ in zip(itertools.cycle(ProgramGenerator.process_gas_states_cycle(stage.gas_states)), range(stage.repeat)):
            gas_get_func = ProgramGenerator.process_gas_state(gas_state, max_time, variable, variable_value)
            stage_num = ProgramGenerator.get_stage_number()
            for inter_time in np.arange(0, max_time, step):
                yield ProgramGenerator.convert_temperatures(float(func(inter_time))), int(gas_get_func(inter_time)), stage_num, 2

    @staticmethod
    def _calculate_full_time(program):
        full_time = 0
        for stage in program:
            if stage.type == "simple":
                full_time += ProgramGenerator._calculate_simple_time(stage)
            elif stage.type == "stepwise":
                full_time += ProgramGenerator._calculate_stepwise_time(stage)
            elif stage.type == "cyclic":
                full_time += ProgramGenerator._calculate_cyclic_time(stage)
            else:
                raise ProgramGeneratorException
        return full_time

    @staticmethod
    def _calculate_simple_time(stage):
        return stage.time

    @staticmethod
    def _calculate_stepwise_time(stage):
        return np.arange(stage.temperature_start, stage.temperature_stop, stage.temperature_step).shape[0] * stage.cycles * len(stage.gas_states)

    @staticmethod
    def _calculate_cyclic_time(stage):
        return stage.repeat * max(stage.temperatures.time)

    @staticmethod
    def _calculate_min_and_max_temperatures(program) -> Tuple[float, float]:
        min_temperatures = []
        max_temperatures = []
        for stage in program:
            if stage.type == "simple":
                min_temperatures.append(ProgramGenerator._calculate_simple_temperature(stage))
                max_temperatures.append(ProgramGenerator._calculate_simple_temperature(stage))
            elif stage.type == "stepwise":
                min_temperatures.append(ProgramGenerator._calculate_stepwise_min_temperature(stage))
                max_temperatures.append(ProgramGenerator._calculate_stepwise_max_temperature(stage))
            elif stage.type == "cyclic":
                min_temperatures.append(ProgramGenerator._calculate_cyclic_min_temperature(stage))
                max_temperatures.append(ProgramGenerator._calculate_cyclic_max_temperature(stage))
            else:
                raise ProgramGeneratorException
        return min(min_temperatures), max(max_temperatures)

    @staticmethod
    def _calculate_simple_temperature(stage):
        return stage.temperature

    @staticmethod
    def _calculate_stepwise_min_temperature(stage):
        return min(stage.temperature_start, stage.temperature_stop)
        
    @staticmethod
    def _calculate_stepwise_max_temperature(stage):
        return max(stage.temperature_start, stage.temperature_stop)

    @staticmethod
    def _calculate_cyclic_min_temperature(stage):
        return np.min(stage.temperatures.temperature)
        
    @staticmethod
    def _calculate_cyclic_max_temperature(stage):
        return np.max(stage.temperatures.temperature)

