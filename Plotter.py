from pglive.sources.live_plot_widget import LivePlotWidget
from pglive.sources.live_plot import LiveLinePlot

class Plotter():
    def __init__(self, widget: LivePlotWidget) -> None:
        self.widget = widget
        self.plot_curve = LiveLinePlot()
        self.widget.addItem(self.plot_curve)
