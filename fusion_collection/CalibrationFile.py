import io
import zipfile

import numpy as np
import pandas as pd
from PySide6 import QtWidgets

VERSION = 1
FILE_EXT_FILTER = "Файл калибровки Fusion(*.fus-cal)"


class Label:
    SAMPLE = "Образец"
    TEMP = "Температура, °C"
    EMF = "Сигнал температурной\nтермопары, мВ"
    PEAK_AREA = "Площадь пика, мВ*с/мг"
    EFFECT = "Тепловой эффект, Дж/г"
    SENS = "Чувствительность, мВ/мВт"


LABELS = [
    Label.SAMPLE,
    Label.TEMP,
    Label.EMF,
    Label.PEAK_AREA,
    Label.EFFECT,
    Label.SENS,
]


def pick_save_path():
    return QtWidgets.QFileDialog.getSaveFileName(
        None, "Сохранить файл калибровки", filter=FILE_EXT_FILTER
    )[0]


def pick_open_path():
    return QtWidgets.QFileDialog.getOpenFileName(
        None, "Открыть файл калибровки", filter=FILE_EXT_FILTER
    )[0]


def file_to_zipbuffer(path: str):
    with open(path, "rb") as f:
        return io.BytesIO(f.read())


def zipbuffer_to_cal(buffer):
    with zipfile.ZipFile(buffer, "r") as zipf:
        version = float(zipf.open("VERSION").read())
        df = pd.read_csv(
            zipf.open("data.csv"), sep=",", decimal=".", header=None, names=LABELS
        )
        coeff_temp = np.loadtxt(zipf.open("coeff_temp.csv"), dtype=float)
        coenf_sens = np.loadtxt(zipf.open("coeff_sens.csv"), dtype=float)
    return Calibration(df, coeff_temp, coenf_sens, version)


def file_to_cal(path: str):
    return zipbuffer_to_cal(file_to_zipbuffer(path))


class Calibration:
    def __init__(
        self,
        df: pd.DataFrame,
        coeff_temp: np.ndarray,
        coeff_sens: np.ndarray,
        version=VERSION,
    ):
        self.df = df
        self.version = version
        self.coeff_temp = coeff_temp
        self.coeff_sens = coeff_sens

    def to_zipbuffer(self):
        buffer_zip = io.BytesIO()
        buffer_data = io.StringIO()
        buffer_coeff_temp = io.StringIO()
        buffer_coeff_sens = io.StringIO()

        self.df.to_csv(buffer_data, index=False, header=False)
        np.savetxt(buffer_coeff_temp, self.coeff_temp, delimiter=",")
        np.savetxt(buffer_coeff_sens, self.coeff_temp, delimiter=",")

        with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("VERSION", data=str(self.version))
            zipf.writestr("data.csv", data=buffer_data.getvalue())
            zipf.writestr("coeff_temp.csv", data=buffer_coeff_temp.getvalue())
            zipf.writestr("coeff_sens.csv", data=buffer_coeff_sens.getvalue())

        return buffer_zip

    def to_file(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_zipbuffer().getbuffer())
