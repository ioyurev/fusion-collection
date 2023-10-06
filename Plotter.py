from pglive.sources.live_plot_widget import LivePlotWidget
from pglive.sources.live_plot import LiveLinePlot
import pyqtgraph as pg

LABEL_TIME = 'Время, с'
LABEL_EMF = 'ДТА, мВ'
LABEL_TEMP = 'Температура, °C'

class Plotter():
    def __init__(self, widget_dta: LivePlotWidget, widget_temp: LivePlotWidget) -> None:
        self.widget_dta = widget_dta
        self.widget_temp = widget_temp

        self.plot_curve_dta = LiveLinePlot(pen="b")
        self.plot_curve_temp = LiveLinePlot(pen="r")
        
        self.p_dta = self.widget_dta.getPlotItem()
        self.p_temp = self.widget_temp.getPlotItem()

        self.p_dta.setLabel('left', LABEL_EMF, color='#0000ff')
        self.p_temp.setLabel('left', LABEL_TEMP, color='#ff0000')
        self.p_temp.setLabel('bottom', LABEL_TIME)

        self.widget_dta.addItem(self.plot_curve_dta)
        self.widget_temp.addItem(self.plot_curve_temp)

