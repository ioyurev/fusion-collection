from PySide6 import QtCore, QtWidgets
from time import time
import serial
import serial.tools.list_ports

BAUDRATE = 9600
ENDCHAR = chr(13)
ENDCHAR_BYTES = bytes(ENDCHAR, 'ascii')
READCMD_1 = bytes('#01' + ENDCHAR, 'ascii')
READCMD_2 = bytes('#02' + ENDCHAR, 'ascii')

def get_serial_ports():
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    return port_list

class SerialReader(QtCore.QThread):
    received_data = QtCore.Signal(tuple)
    port: str = ''

    def start(self,) -> None:
        result = super().start()
        self.ser = serial.Serial(port=self.port,
                    baudrate=BAUDRATE,
                    parity=serial.PARITY_ODD,
                    stopbits=serial.STOPBITS_TWO,
                    bytesize=serial.EIGHTBITS)
        self.start_reading()
        return result

    def start_reading(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.read_data)
        self.start_time = time()
        self.timer.start(100)

    def read_data(self):
        self.ser.write(READCMD_1)
        t1 = self.ser.read_until(ENDCHAR_BYTES)
        self.ser.write(READCMD_2)
        t2 = self.ser.read_until(ENDCHAR_BYTES)
        tm = time() - self.start_time
        self.received_data.emit((tm, t1, t2))

    def close(self):
        self.timer.stop()
        self.ser.close()

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    ser = SerialReader()
    ser.port = 'COM3'
    ser.received_data.connect(print)
    ser.start()
    app.exec()
