import numpy as np
from PySide6 import QtCore
from pglive.sources.data_connector import DataConnector
from pglive.sources.live_plot import LiveLinePlot

class DataProcessor(QtCore.QObject):
    current_data_signal = QtCore.Signal(tuple)
    data_point = (0, 0)

    def __init__(self, curve_dta: LiveLinePlot, curve_temp: LiveLinePlot, curve_t1: LiveLinePlot, curve_t2: LiveLinePlot, coeff_temp: np.ndarray) -> None:
        super().__init__()
        self.connector_t1 = DataConnector(curve_t1, max_points=600, update_rate=10, plot_rate=1)
        self.connector_t2 = DataConnector(curve_t2, max_points=600, update_rate=10, plot_rate=1)
        self.connector_dta = DataConnector(curve_dta, max_points=600, update_rate=10, plot_rate=1)
        self.connector_temp = DataConnector(curve_temp, max_points=600, update_rate=10, plot_rate=1)
        self.timer_current_data = QtCore.QTimer()
        self.timer_current_data.timeout.connect(self.emit_data)
        self.yn_temp = np.poly1d(coeff_temp)

    def process_data(self, data: tuple[float, bytes, bytes]):
        tm = round(data[0], 3)
        t1 = float(data[1].decode('utf-8').strip()[1:])
        t2 = float(data[2].decode('utf-8').strip()[1:])
        self.data_point = (t1, t2)
        dt = t2 - t1
        temp = self.calc_temp(t1)
        self.connector_t1.cb_append_data_point(t1, tm)
        self.connector_t2.cb_append_data_point(t2, tm)
        self.connector_dta.cb_append_data_point(dt, tm)
        self.connector_temp.cb_append_data_point(temp, tm)

    def emit_data(self):
        self.current_data_signal.emit(self.data_point)

    def calc_temp(self, t: float) -> float:
        return self.yn_temp(t)
