from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets

from .about_window import AboutWindow
from .caltool import MainWindow as CaltoolWindow
from .caltool import polyfit_coeff_to_str
from .config import config
from .data_collections import DataPoint, MeasurementInfo
from .helpers import error_message, time_to_str
from .measurement import Measurement
from .new_measurement_window import NewMeasurementWindow
from .plotter import Plotter
from .serial_reader import get_serial_ports
from .ui.MainWindow import Ui_MainWindow


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    measurement: Measurement

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        self.combobox_ports.addItems(get_serial_ports())

        self.action_calibration.triggered.connect(self.run_caltool)
        self.action_about.triggered.connect(self.show_about)

        self.btn_start_measurement.clicked.connect(self.new_measurement)
        self.btn_stop_measurement.clicked.connect(self.stop_measurement)
        if config.is_test_mode:
            label = QtWidgets.QLabel(self.statusbar, text="Тестовый режим")
            self.statusbar.addPermanentWidget(label)

    def closeEvent(self, event):
        if hasattr(self, "measurement") and self.measurement.is_running:
            self.stop_measurement()
        super().closeEvent(event)

    @QtCore.Slot(Exception)
    def show_read_exception_msg(self, e: Exception):
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
        plotter = Plotter(self.plot_layout)
        self.measurement = Measurement(plotter=plotter, parent=self)
        self.measurement.set_port(self.combobox_ports.currentText())
        if not self.measurement.check_hardware():
            return
        self.measurement.read_exception.connect(self.show_read_exception_msg)
        self.measurement.current_data_signal.connect(self.update_signals_display)
        nmw = NewMeasurementWindow(parent=self)
        nmw.signal_accepted.connect(self.start_measrument)
        nmw.show()

    def start_measrument(self, mi: MeasurementInfo):
        self.measurement.set_info(mi)
        log.info("Запуск измерения...")
        self.label_sample.setText(mi.sample)
        self.cal = mi.cal
        if mi.cal:
            self.set_calibration()
        self.measurement.start()
        log.info("Измерение запущено.")
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
        self.measurement.stop()
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

    @QtCore.Slot()
    def run_caltool(self):
        self.caltool_w = CaltoolWindow()
        self.caltool_w.show()
