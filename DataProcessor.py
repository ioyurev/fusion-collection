from pglive.sources.data_connector import DataConnector
from pglive.sources.live_plot import LiveLinePlot

class DataProcessor():
    def __init__(self, curve: LiveLinePlot) -> None:
        self.connector = DataConnector(curve, max_points=600, update_rate=10, plot_rate=1)
        self.data_point = (0, 0)

    def process_data(self, data: tuple[float, bytes, bytes]):
        tm = round(data[0], 3)
        t1 = float(data[1].decode('utf-8').strip()[1:])
        t2 = float(data[2].decode('utf-8').strip()[1:])
        self.data_point = (t1, t2)
        # print(tm, t1, t2)
        self.connector.cb_append_data_point(t2-t1, tm)
