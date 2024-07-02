from pathlib import Path
from typing import NamedTuple

from .calibration_file import Calibration


class DataPointBytes(NamedTuple):
    time: float
    t1: bytes
    t2: bytes


class DataPoint(NamedTuple):
    time: float
    t1: float
    t2: float


class MeasurementInfo(NamedTuple):
    savepath: Path
    operator: str
    sample: str
    comment: str
    cal: Calibration
