from typing import List
from abc import ABC, abstractmethod


class Stage(ABC):

    name = "undefined"

    @classmethod
    @abstractmethod
    def from_dict(cls, dict_: dict) -> "Stage":
        pass

    @classmethod
    @abstractmethod
    def to_dict(cls, for_ui=False) -> dict:
        pass

    @classmethod
    @abstractmethod
    def default(cls) -> "Stage":
        pass


class SimpleStage(Stage):

    name = "simple"

    def __init__(self, time: float, temperature: float, gas_state: int):
        super().__init__()
        self.time = time
        self.temperature = temperature
        self.gas_state = gas_state

    @classmethod
    def from_dict(cls, dict_: dict) -> "SimpleStage":
        try:
            return cls(dict_["time"], dict_["temperature"], dict_["gas_state"])
        except KeyError:
            raise Exception(
                "Not enough information for initialization of simple stage")

    def to_dict(self, for_ui=False) -> dict:
        if for_ui:
            result_dict = {"type": self.name}
        else:
            result_dict = {}

        result_dict.update({
            "time": self.time,
            "temperature": self.temperature,
            "gas_state": self.gas_state,
        })

        return result_dict

    @classmethod
    def default(cls) -> "SimpleStage":
        return cls(0.0, 0.0, 0)


class StepwiseStage(Stage):

    name = "stepwise"

    def __init__(self, time: float, temperature_start: float,
                 temperature_stop: float, temperature_step: float, cycles: int,
                 gas_states: List[int]):
        self.time = time
        self.temperature_start = temperature_start
        self.temperature_stop = temperature_stop
        self.temperature_step = temperature_step
        self.cycles = cycles
        self.gas_states = gas_states

    @classmethod
    def from_dict(cls, dict_: dict) -> "StepwiseStage":
        try:
            return cls(dict_["time"],
                       dict_["temperature_start"],
                       dict_["temperature_stop"],
                       dict_["temperature_step"],
                       dict_["cycles"],
                       dict_["gas_states"])
        except KeyError:
            raise Exception(
                "Not enough information for initialization of simple stage")

    def to_dict(self, for_ui=False) -> dict:
        if for_ui:
            result_dict = {"type": self.name}
        else:
            result_dict = {}

        result_dict.update({
            "time": self.time,
            "temperature_start": self.temperature_start,
            "temperature_stop": self.temperature_stop,
            "temperature_step": self.temperature_step,
            "cycles": self.cycles,
            "gas_states": self.gas_states,
        })

        return result_dict

    @classmethod
    def default(cls) -> "StepwiseStage":
        return cls(0.0, 0.0, 0.0, 0.0, 0, [0, 1])


list_of_types = [SimpleStage, StepwiseStage]
dict_of_stage_types = {type_.name.lower(): type_ for type_ in list_of_types}
