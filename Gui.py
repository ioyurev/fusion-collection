from PySide6 import QtWidgets, QtUiTools
from Serial import SerialReader, get_serial_ports
from Plotter import Plotter, LivePlotWidget
from DataProcessor import DataProcessor
from caltool import pick_open_path, open_calibration_file, polyfit_coeff_to_str
import numpy as np

Ui_MainWindow, QMainWindow = QtUiTools.loadUiType('MainWindow.ui')

class MainWindow(QMainWindow, Ui_MainWindow):
    plot_widget_dta: LivePlotWidget
    plot_widget_temp: LivePlotWidget
    plot_widget_t1: LivePlotWidget
    plot_widget_t2: LivePlotWidget
    btnOpen: QtWidgets.QPushButton
    btnClose : QtWidgets.QPushButton
    btn_choose_calibration: QtWidgets.QPushButton
    combobo_ports : QtWidgets.QComboBox
    label_t1: QtWidgets.QLabel
    label_t2: QtWidgets.QLabel
    label_dta_mv: QtWidgets.QLabel
    label_dta_mw: QtWidgets.QLabel
    label_temp: QtWidgets.QLabel
    label_cal_temp: QtWidgets.QLabel
    label_cal_sens: QtWidgets.QLabel

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.combobo_ports.addItems(get_serial_ports())

        self.btnOpen.clicked.connect(self.openPort)
        self.btnClose.clicked.connect(self.closePort)
        self.btn_choose_calibration.clicked.connect(self.choose_calibration)

        self.serialReader = SerialReader()
        self.plotter = Plotter(
            widget_dta=self.plot_widget_dta,
            widget_temp=self.plot_widget_temp,
            widget_t1=self.plot_widget_t1,
            widget_t2=self.plot_widget_t2)

        self.serial_is_started = False
        self.calibration_is_set = False

    def choose_calibration(self):
        path = pick_open_path()
        if path != '':
            df, self.coeff_temp, self.coeff_sens = open_calibration_file(path)
            self.label_cal_temp.setText(f'f(x) = {polyfit_coeff_to_str(self.coeff_temp)}')
            self.label_cal_sens.setText(f'f(x) = {polyfit_coeff_to_str(self.coeff_sens)}')
            self.dta_calc = np.poly1d(self.coeff_sens)
            self.calibration_is_set = True

    def openPort(self):
        self.serialReader.port = self.combobo_ports.currentText()
        if self.serialReader.port != '' and self.calibration_is_set and self.serial_is_started == False:
            self.data_processor = DataProcessor(
                curve_dta=self.plotter.plot_curve_dta,
                curve_temp=self.plotter.plot_curve_temp,
                curve_t1=self.plotter.plot_curve_t1,
                curve_t2=self.plotter.plot_curve_t2,
                coeff_temp=self.coeff_temp)
            self.serialReader.received_data.connect(self.data_processor.process_data)
            self.temp_calc = lambda x: round(self.data_processor.calc_temp(x), 1)
            self.data_processor.current_data_signal.connect(self.update_signals_display)
            self.plotter.plot_curve_dta.clear()
            self.data_processor.connector_dta.clear()
            self.serialReader.start()
            self.data_processor.timer_current_data.start(1000)
            self.serial_is_started = True
            print('Port opened')
    
    def update_signals_display(self, data: tuple[float, float]):
        t1, t2 = data
        self.label_t1.setText(str(t1))
        self.label_t2.setText(str(t2))
        self.label_dta_mv.setText(str(round(t2-t1, 3)))
        self.label_temp.setText(str(round(self.temp_calc(t1), 3)))
        self.label_dta_mw.setText(str(round(self.dta_calc(t1), 3)))

    def closePort(self):
        if self.serial_is_started:
            self.serialReader.close()
            self.data_processor.timer_current_data.stop()
            self.serial_is_started = False
            print('Port closed')
    