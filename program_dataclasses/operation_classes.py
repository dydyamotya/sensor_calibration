from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class MSOneTickClass:
    """Class containing information about one tick of MS sensors program"""
    us: np.ndarray
    rs: np.ndarray
    time_next_plus_t9: float
    time_next: float
    temperatures: tuple
    gas_state: int
    stage_num: int
    stage_type: int
    sensor_states: tuple
    converted: tuple

