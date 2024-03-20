from pathlib import Path
from typing import NamedTuple

from .CalibrationFile import Calibration


class DataPointBytes(NamedTuple):
    time: float
    t1: bytes
    t2: bytes


class DataPoint(NamedTuple):
    time: float
    t1: float
    t2: float


class Measurement(NamedTuple):
    savepath: Path
    operator: str
    sample: str
    comment: str
    cal: Calibration
