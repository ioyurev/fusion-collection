from PySide6 import QtWidgets
import pandas as pd
import numpy as np
from DataProcessor import DataProcessor
from helpers import warning_message
import zipfile
from CalibrationFile import Calibration
import io

VERSION = 1
FILE_EXT_FILTER = "Файл измерения Fusion(*.fus-mdt)"
HEADER_TIME = 'Time/s'
HEADER_T1 = 'T1/mcV'
HEADER_T2 = 'T2/mcV'

def pick_save_path():
    return QtWidgets.QFileDialog.getSaveFileName(None, 'Сохранить файл измерения', filter=FILE_EXT_FILTER)[0]

def safe_save():
    while True:
        path = pick_save_path()
        if path:
            break
        else:
            warning_message('Необходимо выбрать путь для сохранения измерения.')
    return path

class Data():
    def __init__(self, data_processor: DataProcessor, cal: Calibration, version=VERSION):
        self.version = version
        self.cal = cal
        self.df = pd.DataFrame()
        tm_arr = np.array(data_processor.time_array)
        t1_arr = np.array(data_processor.t1_array)
        t2_arr = np.array(data_processor.t2_array)
        self.df[HEADER_TIME] = tm_arr
        self.df[HEADER_T1] = t1_arr
        self.df[HEADER_T2] = t2_arr

    def to_zipbuffer(self):
        buffer_zip = io.BytesIO()
        buffer_data = io.StringIO()
        buffer_cal = self.cal.to_zipbuffer()

        self.df.to_csv(buffer_data, index=False)

        with zipfile.ZipFile(buffer_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr('VERSION', data=str(self.version))
            zipf.writestr('data.csv', data=buffer_data.getvalue())
            zipf.writestr('calibration.fus-cal', data=buffer_cal.getvalue())
        return buffer_zip
    
    def to_file(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_zipbuffer().getbuffer())
