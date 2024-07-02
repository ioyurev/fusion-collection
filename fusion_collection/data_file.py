import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6 import QtWidgets

from .calibration_file import zipbuffer_to_cal
from .data_collections import MeasurementInfo

VERSION = 1
FILE_EXT_FILTER = "Файл измерения Fusion(*.fus-mdt)"
HEADER_TIME = "Time/s"
HEADER_T1 = "T1/mV"
HEADER_T2 = "T2/mV"


def pick_open_path():
    return QtWidgets.QFileDialog.getOpenFileName(
        None, "Открыть файл измерения", filter=FILE_EXT_FILTER
    )[0]


def pick_save_path():
    return QtWidgets.QFileDialog.getSaveFileName(
        None, "Сохранить файл измерения", filter=FILE_EXT_FILTER
    )[0]


def file_to_zipbuffer(path):
    with open(path, "rb") as f:
        return io.BytesIO(f.read())


def zipbuffer_to_data(buffer: io.BytesIO):
    with zipfile.ZipFile(buffer, "r") as zipf:
        version = float(zipf.open("VERSION").read())
        df = pd.read_csv(zipf.open("data.csv"), sep=",", decimal=".")
        tm_arr = df[HEADER_TIME].to_numpy()
        t1_arr = df[HEADER_T1].to_numpy()
        t2_arr = df[HEADER_T2].to_numpy()
        if "calibration.fus-cal" in zipf.namelist():
            cal = zipbuffer_to_cal(zipf.open("calibration.fus-cal"))
        else:
            cal = None
        mi = MeasurementInfo(
            savepath=Path(""),
            operator="",
            sample="",
            comment="",
            cal=cal,
        )
    return Data(
        time_array=tm_arr, t1_array=t1_arr, t2_array=t2_arr, mi=mi, version=version
    )


def file_to_data(path: str):
    return zipbuffer_to_data(file_to_zipbuffer(path))


class Data:
    def __init__(
        self,
        time_array: np.ndarray,
        t1_array: np.ndarray,
        t2_array: np.ndarray,
        mi: MeasurementInfo,
        version=VERSION,
    ):
        if version > VERSION:
            raise ValueError(
                "Файл измерения создан в более новой версии Fusion Collection."
            )
        self.version = version
        self.nm = mi
        self.df = pd.DataFrame()
        self.df[HEADER_TIME] = time_array
        self.df[HEADER_T1] = t1_array
        self.df[HEADER_T2] = t2_array
        self.info = dict()
        self.info["operator"] = mi.operator
        self.info["sample"] = mi.sample
        self.info["comment"] = mi.comment
        self.info["datetime"] = str(datetime.now())

    def to_zipbuffer(self):
        buffer_zip = io.BytesIO()
        buffer_data = io.StringIO()
        self.df.to_csv(buffer_data, index=False)
        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("VERSION", data=str(self.version))
            zipf.writestr("data.csv", data=buffer_data.getvalue())
            zipf.writestr("info.json", data=json.dumps(self.info, ensure_ascii=False))
            if self.nm.cal is not None:
                buffer_cal = self.nm.cal.to_zipbuffer()
                zipf.writestr("calibration.fus-cal", data=buffer_cal.getvalue())
        return buffer_zip

    def save_file(self):
        with open(self.nm.savepath, "wb") as f:
            f.write(self.to_zipbuffer().getbuffer())
