import numpy as np
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets
from ui.MainWindow import Ui_MainWindow

from fusion_collection.AboutWindow import AboutWindow
from fusion_collection.CalibrationFile import file_to_cal
from fusion_collection.caltool import MainWindow as CaltoolWindow
from fusion_collection.caltool import pick_open_path, polyfit_coeff_to_str
from fusion_collection.DataFile import Data, pick_save_path
from fusion_collection.DataProcessor import DataProcessor
from fusion_collection.helpers import error_message, time_to_str, warning_message
from fusion_collection.Plotter import Plotter
from fusion_collection.Serial import SerialReader, get_serial_ports

from .data_collections import DataPoint


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
    coeff_temp = None
    cal = None

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        self.combobo_ports.addItems(get_serial_ports())

        self.action_calibration.triggered.connect(self.run_caltool)
        self.action_about.triggered.connect(self.show_about)

        self.btn_choose_calibration.clicked.connect(self.choose_calibration)
        self.btn_remove_calibration.clicked.connect(self.remove_calibration)
        self.btn_start_measurement.clicked.connect(self.start_measurement)
        self.btn_stop_measurement.clicked.connect(self.stop_measurement)

        self.serialReader = SerialReader()
        self.plotter = Plotter(
            widget_dta=self.plot_widget_dta,
            widget_temp=self.plot_widget_temp,
            widget_t1=self.plot_widget_t1,
            widget_t2=self.plot_widget_t2,
        )

        self.serial_is_started = False
        self.calibration_is_set = False

    @QtCore.Slot()
    def show_about(self):
        AboutWindow(parent=self).show()

    @QtCore.Slot()
    def start_measurement(self):
        log.info("Попытка запуска измерения.")
        self.closePort()
        if self.openPort():
            self.btn_start_measurement.setEnabled(False)
            self.btn_stop_measurement.setEnabled(True)

    @QtCore.Slot()
    def stop_measurement(self):
        self.closePort()
        tm_arr = self.data_processor.time_array
        t1_arr = self.data_processor.t1_array
        t2_arr = self.data_processor.t2_array
        Data(tm_arr, t1_arr, t2_arr, self.cal).to_file(safe_save())
        self.btn_start_measurement.setEnabled(True)
        self.btn_stop_measurement.setEnabled(False)

    @QtCore.Slot()
    def choose_calibration(self):
        path = pick_open_path()
        if path != "":
            self.cal = file_to_cal(path)
            self.coeff_temp = self.cal.coeff_temp
            self.coeff_sens = self.cal.coeff_sens
            self.label_cal_temp.setText(
                f"f(x) = {polyfit_coeff_to_str(self.coeff_temp)}"
            )
            self.label_cal_sens.setText(
                f"f(x) = {polyfit_coeff_to_str(self.coeff_sens)}"
            )
            self.sens_calc = np.poly1d(self.coeff_sens)
            self.calibration_is_set = True
            self.btn_remove_calibration.setEnabled(True)

    @QtCore.Slot()
    def remove_calibration(self):
        self.cal = None
        self.coeff_temp = None
        self.coeff_sens = None
        self.label_cal_temp.setText("")
        self.label_cal_sens.setText("")
        self.sens_calc = None
        self.calibration_is_set = False
        self.btn_remove_calibration.setEnabled(False)

    def openPort(self):
        self.serialReader.port = self.combobo_ports.currentText()
        if self.serialReader.port != "" and self.serial_is_started is False:
            self.data_processor = DataProcessor(
                curve_dta=self.plotter.plot_curve_dta,
                curve_temp=self.plotter.plot_curve_temp,
                curve_t1=self.plotter.plot_curve_t1,
                curve_t2=self.plotter.plot_curve_t2,
                coeff_temp=self.coeff_temp,
                calibration_is_set=self.calibration_is_set,
            )
            self.serialReader.received_data.connect(self.data_processor.process_data)
            self.temp_calc = lambda x: round(self.data_processor.calc_temp(x), 1)
            self.data_processor.current_data_signal.connect(self.update_signals_display)
            try:
                self.plotter.plot_curve_dta.clear()
                self.data_processor.connector_dta.clear()
            except Exception as e:
                log.warning(f"Не удалось очистить график: {e}")
            if self.serialReader.start_thread():
                self.data_processor.timer_current_data.start(1000)
                self.serial_is_started = True
                log.info("Порт открыт.")
                return True
            else:
                self.closePort()
                error_message(
                    f"Не удалось запустить измерение.\nПодробности в журнале сообщений:\n{self.log_path}"
                )
        else:
            log.warning("Устройство не обнаружно.")
            warning_message(
                "Устройство не обнаружно.\nПодключите устройство и перезапустите программу."
            )
            return False

    @QtCore.Slot()
    def update_signals_display(self, data: DataPoint):
        self.label_time.setText(time_to_str(data.time))
        self.label_t1.setText(str(data.t1))
        self.label_t2.setText(str(data.t2))
        dta = data.t2 - data.t1
        self.label_dta_mcv.setText(str(round(dta, 3)))
        if self.calibration_is_set:
            self.label_temp.setText(str(round(self.temp_calc(data.t1), 3)))
            sens = self.sens_calc(data.t1)
            self.label_dta_mw.setText(str(round(dta / sens, 3)))

    def closePort(self):
        if self.serial_is_started:
            self.serialReader.close()
            self.data_processor.timer_current_data.stop()
            self.serial_is_started = False
            log.info("Порт закрыт.")

    @QtCore.Slot()
    def run_caltool(self):
        self.caltool_w = CaltoolWindow()
        self.caltool_w.show()
