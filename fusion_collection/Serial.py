from time import time

import serial
import serial.tools.list_ports
from loguru import logger as log
from PySide6 import QtCore, QtWidgets
from testing import values as DATA

from .data_collections import DataPointBytes
from .helpers import check_function_timeout

BAUDRATE = 9600
ENDCHAR = chr(13)
ENDCHAR_BYTES = bytes(ENDCHAR, "ascii")
SAMPLE_SYNC = bytes("#**" + ENDCHAR, "ascii")
READCMD_1 = bytes("$014" + ENDCHAR, "ascii")
READCMD_2 = bytes("$024" + ENDCHAR, "ascii")
READ_INTERVAL = 86
MODULE1_NAME = bytes("$01M" + ENDCHAR, "ascii")
MODULE2_NAME = bytes("$02M" + ENDCHAR, "ascii")


def gen_test_data():
    length = len(DATA.time)
    for i in range(length):
        yield DataPointBytes(time=DATA.time[i], t1=DATA.t1[i], t2=DATA.t2[i])


def get_serial_ports():
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    return port_list


class SerialReader(QtCore.QThread):
    received_data = QtCore.Signal(DataPointBytes)
    port: str = ""

    def __init__(self):
        super().__init__()
        self.ser = serial.Serial(
            baudrate=BAUDRATE,
            parity=serial.PARITY_ODD,
            stopbits=serial.STOPBITS_TWO,
            bytesize=serial.EIGHTBITS,
        )

    @property
    def is_open(self):
        return self.ser.is_open

    def start_thread(
        self,
    ) -> bool:
        if self.port == "":
            return False
        super().start()
        self.ser.port = self.port
        try:
            self.ser.open()
        except serial.SerialException as e:
            log.critical(f"Не удалось открыть порт: {e}")
            self.exit()
            self.wait()
            return False
        if self.check_responsability():
            self.start_reading()
            return True
        else:
            self.ser.close()
            self.exit()
            self.wait()
            return False

    def check_responsability(self) -> bool:
        if self.check_port():
            timeout, result = check_function_timeout(self.check_modules, 2)
            if not timeout:
                if result:
                    log.info("Модули обнаружены.")
                    if self.check_thermocouples():
                        log.info("Все проверки успешно пройдены.")
                        return True
            else:
                log.critical("Модули не обнаружены или не отвечают.")
        return False

    def check_port(self) -> bool:
        result = self.ser.is_open
        log.info(f"Проверка последовательного порта: {result}")
        return result

    def check_modules(self) -> bool:
        try:
            self.ser.write(MODULE1_NAME)
            answer1 = self.ser.read_until(ENDCHAR_BYTES)
            log.info(f"Ответ на вызов модуля 1: {answer1!r}")
            self.ser.write(MODULE2_NAME)
            answer2 = self.ser.read_until(ENDCHAR_BYTES)
            log.info(f"Ответ на вызов модуля 2: {answer2!r}")
            if answer1 == b"!014011\r" and answer2 == b"!024011\r":
                return True
            else:
                log.critical(
                    "Неожиданные ответы модулей. Вероятно, установленные неправильные модули "
                )
                return False
        except serial.SerialTimeoutException as e:
            log.critical(f"Таймаут при попытке вывода в порт: {e}")
            return False

    def check_thermocouples(self) -> bool:
        self.ser.write(SAMPLE_SYNC)
        self.ser.write(READCMD_1)
        x1 = self.ser.read_until(ENDCHAR_BYTES)
        self.ser.write(READCMD_2)
        x2 = self.ser.read_until(ENDCHAR_BYTES)
        log.info(f"Показания термопар: {x1 = }, {x2 = }")
        t1 = float(x1.decode("utf-8").strip()[4:])
        t2 = float(x2.decode("utf-8").strip()[4:])
        if t1 != 65.521 and t2 != 65.521:
            return True
        else:
            log.critical("Обрыв термопар.")
            return False

    def start_reading(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.read_data)
        self.start_time = time()
        self.timer.start(READ_INTERVAL)

    @QtCore.Slot()
    def read_data(self):
        self.ser.write(SAMPLE_SYNC)
        self.ser.write(READCMD_1)
        t1 = self.ser.read_until(ENDCHAR_BYTES)
        self.ser.write(READCMD_2)
        t2 = self.ser.read_until(ENDCHAR_BYTES)
        tm = time() - self.start_time
        self.received_data.emit(DataPointBytes(time=tm, t1=t1, t2=t2))

    def close(self):
        self.timer.stop()
        self.ser.close()
        self.quit()


class TestSerialReader(SerialReader):
    timer = QtCore.QTimer()
    is_open = False

    def reset_generator(self):
        self.generator = gen_test_data()

    def start_thread(self):
        self.is_open = True
        self.start_reading()
        return True

    def read_data(self):
        self.received_data.emit(next(self.generator))

    def close(self):
        self.is_open = False
        self.timer.stop()
        self.quit()


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    ser = SerialReader()
    ser.port = "COM3"
    ser.received_data.connect(print)
    ser.start_thread()
    app.exec()
