import numpy as np
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets
from ui.MainWindow import Ui_MainWindow

from .about_window import AboutWindow
from .caltool import MainWindow as CaltoolWindow
from .caltool import polyfit_coeff_to_str
from .data_collections import DataPoint
from .data_file import pick_save_path
from .data_processor import DataProcessor
from .helpers import error_message, time_to_str, warning_message
from .new_measurement_window import Measurement, NewMeasurementWindow
from .Plotter import Plotter
from .Serial import SerialReader, TestSerialReader, get_serial_ports


def safe_save():
    while True:
        path = pick_save_path()
        if path:
            break
        else:
            answer = QtWidgets.QMessageBox.question(
                None,
                "Сбор данных",
                "Вы не выбрали путь для созранения измерения.\n Продолжить?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                break
    return path


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, testing: bool):
        super().__init__()
        self.testing = testing
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        self.combobo_ports.addItems(get_serial_ports())

        self.action_calibration.triggered.connect(self.run_caltool)
        self.action_about.triggered.connect(self.show_about)

        self.btn_start_measurement.clicked.connect(self.new_measurement)
        self.btn_stop_measurement.clicked.connect(self.stop_measurement)
        if testing:
            self.serialReader = TestSerialReader()
            label = QtWidgets.QLabel(self.statusbar, text="Тестовый режим")
            self.statusbar.addPermanentWidget(label)
        else:
            self.serialReader = SerialReader()
        self.plotter = Plotter(
            widget_dta=self.plot_widget_dta,
            widget_dta_temp=self.plot_widget_dta_temp,
            widget_t1=self.plot_widget_t1,
            widget_t2=self.plot_widget_t2,
        )
        self.data_processor = DataProcessor(
            curve_dta=self.plotter.plot_curve_dta,
            curve_temp=self.plotter.plot_curve_temp,
            curve_t1=self.plotter.plot_curve_t1,
            curve_t2=self.plotter.plot_curve_t2,
        )

    @QtCore.Slot()
    def show_about(self):
        AboutWindow(parent=self).show()

    @QtCore.Slot()
    def new_measurement(self):
        nmw = NewMeasurementWindow(parent=self)
        nmw.signal_accepted.connect(self.start_measrument)
        nmw.show()

    def start_measrument(self, nm: Measurement):
        if nm.cal:
            self.cal = nm.cal
            self.label_cal_temp.setText(
                f"f(x) = {polyfit_coeff_to_str(nm.cal.coeff_temp)}"
            )
            self.label_cal_sens.setText(
                f"f(x) = {polyfit_coeff_to_str(nm.cal.coeff_sens)}"
            )
            self.sens_calc = np.poly1d(nm.cal.coeff_sens)

        self.data_processor.clear()
        self.data_processor.set_measurement(nm)
        log.info("Попытка запуска измерения.")
        self.closePort()
        if self.testing:
            self.serialReader.reset_generator()
        if self.openPort():
            self.btn_start_measurement.setEnabled(False)
            self.btn_stop_measurement.setEnabled(True)

    @QtCore.Slot()
    def stop_measurement(self):
        self.closePort()
        self.data_processor.save_file()
        self.btn_start_measurement.setEnabled(True)
        self.btn_stop_measurement.setEnabled(False)

    def openPort(self):
        self.serialReader.port = self.combobo_ports.currentText()
        if self.serialReader.is_open is False:
            self.serialReader.received_data.connect(self.data_processor.process_data)
            self.temp_calc = lambda x: round(self.data_processor.calc_temp(x), 1)
            self.data_processor.current_data_signal.connect(self.update_signals_display)
            if self.serialReader.start_thread():
                self.data_processor.timer_current_data.start(1000)
                log.info("Порт открыт.")
                return True
            else:
                self.closePort()
                error_message("Не удалось запустить измерение.", parent=self)
        else:
            log.warning("Устройство не обнаружно.")
            warning_message(
                "Устройство не обнаружно.\nПодключите устройство и перезапустите программу.",
                parent=self,
            )
            return False

    @QtCore.Slot()
    def update_signals_display(self, data: DataPoint):
        self.label_time.setText(time_to_str(data.time))
        self.label_t1.setText(str(data.t1))
        self.label_t2.setText(str(data.t2))
        dta = data.t2 - data.t1
        self.label_dta_mcv.setText(str(round(dta, 3)))
        if self.cal:
            self.label_temp.setText(str(round(self.temp_calc(data.t1), 3)))
            sens = self.sens_calc(data.t1)
            self.label_dta_mw.setText(str(round(dta / sens, 3)))

    def closePort(self):
        if self.serialReader.is_open:
            self.serialReader.close()
            self.data_processor.timer_current_data.stop()
            log.info("Порт закрыт.")

    @QtCore.Slot()
    def run_caltool(self):
        self.caltool_w = CaltoolWindow()
        self.caltool_w.show()
