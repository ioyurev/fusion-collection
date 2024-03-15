from fusion_collection.CalibrationFile import Calibration, zipbuffer_to_cal
from PySide6 import QtWidgets
import pandas as pd
import numpy as np
import zipfile
import io

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
    return Data(
        time_array=tm_arr, t1_array=t1_arr, t2_array=t2_arr, cal=cal, version=version
    )


def file_to_data(path: str):
    return zipbuffer_to_data(file_to_zipbuffer(path))


class Data:
    def __init__(
        self,
        time_array: np.ndarray,
        t1_array: np.ndarray,
        t2_array: np.ndarray,
        cal: Calibration,
        version=VERSION,
    ):
        if version > VERSION:
            raise ValueError(
                "Файл измерения создан в более новой версии Fusion Collection."
            )
        self.version = version
        self.cal = cal
        self.df = pd.DataFrame()
        self.df[HEADER_TIME] = time_array
        self.df[HEADER_T1] = t1_array
        self.df[HEADER_T2] = t2_array
        self.info = dict()
        self.info["version"] = self.version
        # self.info['time'] = str(datetime.now())

    def to_zipbuffer(self):
        buffer_zip = io.BytesIO()
        buffer_data = io.StringIO()
        if self.cal is not None:
            buffer_cal = self.cal.to_zipbuffer()

        self.df.to_csv(buffer_data, index=False)

        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("VERSION", data=str(self.version))
            zipf.writestr("data.csv", data=buffer_data.getvalue())
            if self.cal is not None:
                zipf.writestr("calibration.fus-cal", data=buffer_cal.getvalue())
        return buffer_zip

    def to_file(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_zipbuffer().getbuffer())
