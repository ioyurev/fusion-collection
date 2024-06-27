from typing import NamedTuple

import numpy as np

from fusion_collection.config import config
from fusion_collection.data_file import HEADER_T1, HEADER_T2, HEADER_TIME, file_to_data


class Values(NamedTuple):
    time: np.ndarray
    t1: np.ndarray
    t2: np.ndarray


def float_to_bytes(arr: np.ndarray) -> list[bytes]:
    new_arr = list()
    for val in arr:
        result = f">01+{val}\r".encode()
        new_arr.append(result)
    return new_arr


if config.is_test_mode:
    data = file_to_data("test.fus-mdt")
    data_time = data.df[HEADER_TIME].to_numpy()
    data_t1_float = data.df[HEADER_T1].to_numpy()
    data_t2_float = data.df[HEADER_T2].to_numpy()
    data_t1 = float_to_bytes(data_t1_float)
    data_t2 = float_to_bytes(data_t2_float)
    values = Values(data_time, data_t1, data_t2)
