from pglive.sources.live_plot_widget import LivePlotWidget
from pglive.sources.live_plot import LiveLinePlot

LABEL_T1 = 'Термопара 1, мкВ'
LABEL_T2 = 'Термопара 2, мкВ'
LABEL_TIME = 'Время, с'
LABEL_EMF = 'ДТА, мкВ'
LABEL_TEMP = 'Температура, °C'

class Plotter():
    def __init__(self, widget_dta: LivePlotWidget, widget_temp: LivePlotWidget, widget_t1: LivePlotWidget, widget_t2: LivePlotWidget) -> None:
        self.widget_dta = widget_dta
        self.widget_temp = widget_temp
        self.widget_t1 = widget_t1
        self.widget_t2 = widget_t2

        self.plot_curve_t1 = LiveLinePlot(pen="k")
        self.plot_curve_t2 = LiveLinePlot(pen="k")
        self.plot_curve_dta = LiveLinePlot(pen="b")
        self.plot_curve_temp = LiveLinePlot(pen="r")
        
        self.p_t1 = self.widget_t1.getPlotItem()
        self.p_t2 = self.widget_t2.getPlotItem()
        self.p_dta = self.widget_dta.getPlotItem()
        self.p_temp = self.widget_temp.getPlotItem()


        self.p_t1.setLabel('left', LABEL_T1)
        self.p_t2.setLabel('left', LABEL_T2)
        self.p_dta.setLabel('left', LABEL_EMF, color='#0000ff')
        self.p_temp.setLabel('left', LABEL_TEMP, color='#ff0000')
        self.p_temp.setLabel('bottom', LABEL_TIME)

        self.widget_t1.addItem(self.plot_curve_t1)
        self.widget_t2.addItem(self.plot_curve_t2)
        self.widget_dta.addItem(self.plot_curve_dta)
        self.widget_temp.addItem(self.plot_curve_temp)
