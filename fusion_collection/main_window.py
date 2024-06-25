from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets

from .about_window import AboutWindow
from .caltool import MainWindow as CaltoolWindow
from .caltool import polyfit_coeff_to_str
from .config import config
from .data_collections import DataPoint
from .data_processor import DataProcessor
from .helpers import error_message, time_to_str
from .new_measurement_window import Measurement, NewMeasurementWindow
from .Plotter import Plotter
from .Serial import SerialReader, TestSerialReader, get_serial_ports
from .ui.MainWindow import Ui_MainWindow


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        self.combobo_ports.addItems(get_serial_ports())

        self.action_calibration.triggered.connect(self.run_caltool)
        self.action_about.triggered.connect(self.show_about)

        self.btn_start_measurement.clicked.connect(self.new_measurement)
        self.btn_stop_measurement.clicked.connect(self.stop_measurement)
        if config.is_test_mode():
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
        self.serialReader.read_exception.connect(self.read_exception)
        self.serialReader.received_data.connect(self.data_processor.process_data)
        self.data_processor.current_data_signal.connect(self.update_signals_display)

    @QtCore.Slot(Exception)
    def read_exception(self, e: Exception):
        self.stop_measurement()
        log.exception(e)
        error_message(
            "Остановка измерения.\nОшибка в ходе измерения.\n{e}", parent=self
        )

    @QtCore.Slot()
    def show_about(self):
        AboutWindow(parent=self).show()

    @QtCore.Slot()
    def new_measurement(self):
        self.serialReader.port = self.combobo_ports.currentText()
        if not self.serialReader.open():
            return
        if not self.serialReader.check():
            error_message("Ошибка при проверке оборудования.", parent=self)
            return
        nmw = NewMeasurementWindow(parent=self)
        nmw.signal_accepted.connect(self.start_measrument)
        nmw.show()

    def start_measrument(self, nm: Measurement):
        log.info("Запуск измерения.")
        self.cal = nm.cal
        if nm.cal:
            self.set_calibration()
        self.data_processor.clear()
        self.data_processor.set_measurement(nm)
        self.closePort()
        if config.is_test_mode():
            self.serialReader.reset_generator()
        if not self.serialReader.start_thread():
            self.closePort()
            error_message("Не удалось запустить измерение.", parent=self)
            return False
        log.info("Измерение запущено.")
        self.data_processor.timer_current_data.start(1000)
        self.btn_start_measurement.setEnabled(False)
        self.btn_stop_measurement.setEnabled(True)

    def set_calibration(self):
        self.label_cal_temp.setText(
            f"f(x) = {polyfit_coeff_to_str(self.cal.coeff_temp)}"
        )
        self.label_cal_sens.setText(
            f"f(x) = {polyfit_coeff_to_str(self.cal.coeff_sens)}"
        )
        self.temp_calc = self.cal.yn_temp
        self.sens_calc = self.cal.yn_sens

    @QtCore.Slot()
    def stop_measurement(self):
        self.closePort()
        self.data_processor.save_file()
        self.btn_start_measurement.setEnabled(True)
        self.btn_stop_measurement.setEnabled(False)

    @QtCore.Slot()
    def update_signals_display(self, data: DataPoint):
        self.label_time.setText(time_to_str(data.time))
        self.label_t1.setText(str(data.t1))
        self.label_t2.setText(str(data.t2))
        dta = data.t1 - data.t2
        self.label_dta_mcv.setText(str(round(dta, 3)))
        if self.cal:
            temp = self.temp_calc(data.t1)
            sens = self.sens_calc(data.t1)
            dta_mw = dta / sens
            self.label_temp.setText(f"{temp:.1f}")
            self.label_dta_mw.setText(f"{dta_mw:.3f}")

    def closePort(self):
        if self.serialReader.is_open:
            self.serialReader.close()
            self.data_processor.timer_current_data.stop()
            log.info("Порт закрыт.")

    @QtCore.Slot()
    def run_caltool(self):
        self.caltool_w = CaltoolWindow()
        self.caltool_w.show()
