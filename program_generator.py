import munch
import itertools
from scipy.interpolate import interp1d
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ProgramGeneratorException(Exception):
    pass

class ProgramGenerator:

    stages_counter = 0

    def __init__(self, program):
        self.program = munch.munchify(program)

    def parse_program_to_queue(self):
        self.reset_stage_number()
        settings = self.program.settings
        program = self.program.program
        settings.step = 1 / settings.frequency
        full = zip(itertools.count(0, settings.step), ProgramGenerator._parse_all_program(program, settings))
        return full

    @classmethod
    def get_stage_number(cls):
        stage_num = cls.stages_counter
        cls.stages_counter += 1
        return stage_num

    @classmethod
    def reset_stage_number(cls):
        cls.stages_counter = 0

    @staticmethod
    def convert_temperatures(temperatures):
        if isinstance(temperatures, list):
            if len(temperatures) == 12:
                return temperatures
            else:
                temp = (min(temperatures), ) * 12
                temp[:len(temperatures)] = temperatures
                return temp
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
                yield ProgramGenerator.convert_temperatures(float(func(inter_time))), gas_get_func(inter_time), stage_num, 2

