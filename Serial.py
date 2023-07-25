from PySide6 import QtCore, QtSerialPort
from pglive.sources.data_connector import DataConnector

class SerialReader(QtCore.QThread):
    received_data = QtCore.Signal(QtCore.QByteArray)

    def __init__(self, port: str, baudrate: int, data_connector: DataConnector) -> None:
        super().__init__(parent=None)
        self.data_connector: DataConnector = data_connector
        self.port = QtSerialPort.QSerialPort()
        self.port.setBaudRate(baudrate)
        self.port.setPortName(port)
        self.port.readyRead.connect(self.readFromPort)
        # self.open()

    def readFromPort(self):
        data = self.port.readAll()
        if len(data) > 0:
            self.received_data.emit(data)

    # def sendFromPort(self, text):
    #     self.port.write(text.encode())

    def open(self):
        if not self.port.open(QtCore.QIODevice.ReadWrite):
            print('Port open error')
        else:
            print('Port opened')

    def close(self):
        self.port.close()
        print('Port closed')