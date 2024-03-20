from pathlib import Path

import numpy as np
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_plot import LiveLinePlot
from PySide6 import QtCore

from .calibration_file import Calibration
from .data_collections import DataPoint, DataPointBytes
from .data_file import Data

MAX_POINTS = 600
UPDATE_RATE = 10
PLOT_RATE = 1


class DataProcessor(QtCore.QObject):
    current_data_signal = QtCore.Signal(DataPointBytes)
    data_point = DataPoint(0.0, 0.0, 0.0)
    cal = None

    def __init__(
        self,
        curve_dta: LiveLinePlot,
        curve_temp: LiveLinePlot,
        curve_t1: LiveLinePlot,
        curve_t2: LiveLinePlot,
    ) -> None:
        super().__init__()
        self.time_array: list[float] = []
        self.t1_array: list[float] = []
        self.t2_array: list[float] = []
        self.connector_t1 = DataConnector(
            curve_t1,
            # max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        self.connector_t2 = DataConnector(
            curve_t2,
            # max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        self.connector_dta = DataConnector(
            curve_dta,
            # max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        self.connector_dta_temp = DataConnector(
            curve_temp,
            # max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        self.timer_current_data = QtCore.QTimer()
        self.timer_current_data.timeout.connect(self.emit_data)

    @QtCore.Slot(DataPointBytes)
    def process_data(self, data_point: DataPointBytes):
        t1 = float(data_point.t1.decode("utf-8").strip()[4:])
        t2 = float(data_point.t2.decode("utf-8").strip()[4:])
        self.time_array.append(data_point.time)
        self.t1_array.append(t1)
        self.t2_array.append(t2)
        self.data_point = DataPoint(data_point.time, t1, t2)
        dt = t2 - t1
        if self.cal:
            temp = self.calc_temp(t1)
            self.connector_dta_temp.cb_append_data_point(dt, temp)
        else:
            self.connector_dta_temp.cb_append_data_point(dt, t1)
        self.connector_t1.cb_append_data_point(t1, data_point.time)
        self.connector_t2.cb_append_data_point(t2, data_point.time)
        self.connector_dta.cb_append_data_point(dt, data_point.time)

    @QtCore.Slot()
    def emit_data(self):
        self.current_data_signal.emit(self.data_point)

    def calc_temp(self, t: float) -> float:
        return self.yn_temp(t)

    def clear(self):
        self.connector_t1.clear()
        self.connector_t2.clear()
        self.connector_dta.clear()
        self.connector_dta_temp.clear()

    def set_calibration(self, cal: Calibration | None):
        self.cal = cal
        if self.cal:
            self.yn_temp = np.poly1d(self.cal.coeff_temp)

    def save_to_file(self, path: Path):
        Data(self.time_array, self.t1_array, self.t2_array, self.cal).to_file(path=path)
