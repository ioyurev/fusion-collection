from loguru import logger as log
from PySide6 import QtCore

from .config import config
from .data_collections import DataPointBytes, MeasurementInfo
from .data_processor import DataProcessor
from .helpers import error_message
from .plotter import Plotter
from .serial_reader import SerialReader, TestSerialReader


class Measurement(QtCore.QObject):
    is_running = False
    mi: MeasurementInfo
    read_exception = QtCore.Signal(Exception)
    current_data_signal = QtCore.Signal(DataPointBytes)

    def __init__(self, plotter: Plotter, parent=None):
        super().__init__(parent=parent)
        self.plotter = plotter
        if config.is_test_mode:
            self.serialReader = TestSerialReader()
        else:
            self.serialReader = SerialReader()
        self.data_processor = DataProcessor(
            curve_dta=self.plotter.plot_curve_dta,
            curve_temp=self.plotter.plot_curve_temp,
            curve_t1=self.plotter.plot_curve_t1,
            curve_t2=self.plotter.plot_curve_t2,
        )

    def start(self):
        self.serialReader.read_exception.connect(self.read_exception.emit)
        self.serialReader.received_data.connect(self.data_processor.process_data)
        self.data_processor.current_data_signal.connect(self.current_data_signal.emit)
        self.close_port()
        self.data_processor.set_measurement(self.mi)
        if config.is_test_mode:
            self.serialReader.reset_generator()
        if not self.serialReader.start_thread():
            self.close_port()
            error_message("Не удалось запустить измерение.", parent=self)
        self.data_processor.timer_current_data.start(1000)
        self.is_running = True

    def stop(self):
        self.close_port()
        self.data_processor.save_file()
        self.is_running = False

    def set_info(self, mi: MeasurementInfo):
        self.mi = mi
        if mi.cal:
            self.plotter.set_dta_label_to_temp()
        else:
            self.plotter.set_dta_label_to_emf()

    def set_port(self, port: str):
        self.serialReader.port = port

    def close_port(self):
        if self.serialReader.is_open:
            self.serialReader.close()
            self.data_processor.timer_current_data.stop()
            log.info("Порт закрыт.")

    def check_hardware(self):
        if not self.serialReader.open():
            return False
        if not self.serialReader.check():
            error_message(
                message="Ошибка при проверке оборудования.", parent=self.parent()
            )
            return False
        return True
