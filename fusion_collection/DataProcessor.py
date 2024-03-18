import numpy as np
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_plot import LiveLinePlot
from PySide6 import QtCore

from .data_collections import DataPoint, DataPointBytes

MAX_POINTS = 600
UPDATE_RATE = 10
PLOT_RATE = 1


class DataProcessor(QtCore.QObject):
    current_data_signal = QtCore.Signal(DataPointBytes)
    data_point = DataPoint(0.0, 0.0, 0.0)

    def __init__(
        self,
        curve_dta: LiveLinePlot,
        curve_temp: LiveLinePlot,
        curve_t1: LiveLinePlot,
        curve_t2: LiveLinePlot,
        coeff_temp: np.ndarray,
        calibration_is_set: bool,
    ) -> None:
        super().__init__()
        self.calibration_is_set = calibration_is_set
        self.time_array: list[float] = []
        self.t1_array: list[float] = []
        self.t2_array: list[float] = []
        self.connector_t1 = DataConnector(
            curve_t1,
            max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        self.connector_t2 = DataConnector(
            curve_t2,
            max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        self.connector_dta = DataConnector(
            curve_dta,
            max_points=MAX_POINTS,
            update_rate=UPDATE_RATE,
            plot_rate=PLOT_RATE,
        )
        if self.calibration_is_set:
            self.connector_temp = DataConnector(
                curve_temp,
                max_points=MAX_POINTS,
                update_rate=UPDATE_RATE,
                plot_rate=PLOT_RATE,
            )
        self.timer_current_data = QtCore.QTimer()
        self.timer_current_data.timeout.connect(self.emit_data)
        self.yn_temp = np.poly1d(coeff_temp)

    @QtCore.Slot(DataPointBytes)
    def process_data(self, data_point: DataPointBytes):
        t1 = float(data_point.t1.decode("utf-8").strip()[4:])
        t2 = float(data_point.t2.decode("utf-8").strip()[4:])
        self.time_array.append(data_point.time)
        self.t1_array.append(t1)
        self.t2_array.append(t2)
        self.data_point = DataPoint(data_point.time, t1, t2)
        dt = t2 - t1
        if self.calibration_is_set:
            temp = self.calc_temp(t1)
            self.connector_temp.cb_append_data_point(temp, data_point.time)
        self.connector_t1.cb_append_data_point(t1, data_point.time)
        self.connector_t2.cb_append_data_point(t2, data_point.time)
        self.connector_dta.cb_append_data_point(dt, data_point.time)

    @QtCore.Slot()
    def emit_data(self):
        self.current_data_signal.emit(self.data_point)

    def calc_temp(self, t: float) -> float:
        return self.yn_temp(t)
