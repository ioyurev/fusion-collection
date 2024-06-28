from pglive.sources.live_plot import LiveLinePlot
from pglive.sources.live_plot_widget import LivePlotWidget

LABEL_T = "ЭДС, мВ"
LABEL_TIME = "Время, с"
LABEL_DTA = "ДТА, мВ"
LABEL_TEMP = "Температура, °C"


class Plotter:
    def __init__(
        self,
        widget_dta: LivePlotWidget,
        widget_dta_temp: LivePlotWidget,
        widget_t: LivePlotWidget,
    ) -> None:
        self.widget_dta = widget_dta
        self.widget_dta_temp = widget_dta_temp
        self.widget_t = widget_t

        self.plot_curve_t1 = LiveLinePlot(pen="r")
        self.plot_curve_t2 = LiveLinePlot(pen="k")
        self.plot_curve_dta = LiveLinePlot(pen="b")
        self.plot_curve_temp = LiveLinePlot(pen="b")

        self.p_t = self.widget_t.getPlotItem()
        self.p_dta = self.widget_dta.getPlotItem()
        self.p_dta_temp = self.widget_dta_temp.getPlotItem()

        self.p_t.setLabel("bottom", LABEL_TIME)
        self.p_t.setLabel("left", LABEL_T)
        self.p_dta.setLabel("bottom", LABEL_TIME)
        self.p_dta.setLabel("left", LABEL_DTA, color="#0000ff")
        self.p_dta_temp.setLabel("left", LABEL_DTA, color="#0000ff")
        self.p_dta_temp.setLabel("bottom", LABEL_T, color="#ff0000")

        self.widget_t.addItem(self.plot_curve_t1)
        self.widget_t.addItem(self.plot_curve_t2)
        self.widget_dta.addItem(self.plot_curve_dta)
        self.widget_dta_temp.addItem(self.plot_curve_temp)

    def set_dta_label_to_temp(self):
        self.p_dta_temp.setLabel("bottom", LABEL_TEMP, color="#ff0000")

    def set_dta_label_to_emf(self):
        self.p_dta_temp.setLabel("bottom", LABEL_T, color="#ff0000")
