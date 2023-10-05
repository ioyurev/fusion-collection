from PySide6 import QtWidgets, QtUiTools, QtCore
from Serial import SerialReader, get_serial_ports
from Plotter import Plotter, LivePlotWidget
from DataProcessor import DataProcessor
from caltool import pick_open_path, open_calibration_file, polyfit_coeff_to_str
import numpy as np

Ui_MainWindow, QMainWindow = QtUiTools.loadUiType('MainWindow.ui')

class MainWindow(QMainWindow, Ui_MainWindow):
    plotWidget: LivePlotWidget
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
        self.plotter = Plotter(self.plotWidget)
        self.data_processor = DataProcessor(curve=self.plotter.plot_curve)
        self.serialReader.received_data.connect(self.data_processor.process_data)

        self.timer_display = QtCore.QTimer()
        self.timer_display.timeout.connect(self.update_signals_display)

    def choose_calibration(self):
        path = pick_open_path()
        if path != '':
            df, self.coeff_temp, self.coeff_sens = open_calibration_file(path)
            self.label_cal_temp.setText(f'f(x) = {polyfit_coeff_to_str(self.coeff_temp)}')
            self.label_cal_sens.setText(f'f(x) = {polyfit_coeff_to_str(self.coeff_sens)}')
            self.temp_calc = np.poly1d(self.coeff_temp)
            self.dta_calc = np.poly1d(self.coeff_sens)

    def openPort(self):
        self.plotter.plot_curve.clear()
        self.data_processor.connector.clear()
        self.serialReader.port = self.combobo_ports.currentText()
        self.serialReader.start()
        self.timer_display.start(1000)
    
    def update_signals_display(self):
        t1, t2 = self.data_processor.data_point
        self.label_t1.setText(str(t1))
        self.label_t2.setText(str(t2))
        self.label_dta_mv.setText(str(round(t2-t1, 3)))
        self.label_temp.setText(str(round(self.temp_calc(t1), 3)))
        self.label_dta_mw.setText(str(round(self.dta_calc(t1), 3)))

    def closePort(self):
        self.serialReader.close()
    