from typing import NamedTuple


class DataPointBytes(NamedTuple):
    time: float
    t1: bytes
    t2: bytes


class DataPoint(NamedTuple):
    time: float
    t1: float
    t2: float
