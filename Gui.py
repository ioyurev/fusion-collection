import configparser
from PySide6 import QtWidgets, QtCore, QtUiTools
from Serial import SerialReader, DataConnector
from pglive.sources.live_plot_widget import LivePlotWidget
from pglive.sources.live_plot import LiveLinePlot

Ui_MainWindow, QMainWindow = QtUiTools.loadUiType('MainWindow.ui')

class MainWindow(QMainWindow, Ui_MainWindow):
    plotWidget: LivePlotWidget
    btnOpen: QtWidgets.QPushButton
    btnClose : QtWidgets.QPushButton

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # self.showMaximized()

        self.btnOpen.clicked.connect(self.openPort)
        self.btnClose.clicked.connect(self.closePort)

        self.plot_curve = LiveLinePlot()
        self.plotWidget.addItem(self.plot_curve)
        self.data_connector = DataConnector(self.plot_curve, max_points=600, update_rate=10, plot_rate=1)
        
        self.read_config()
        self.serialReader = SerialReader(port=self.port, baudrate=self.baudrate, data_connector=self.data_connector)
        self.serialReader.received_data.connect(self.precess_data,  QtCore.Qt.QueuedConnection)
        self.serialReader.start()

    def read_config(self):
        config = configparser.ConfigParser()
        if config.read("config.ini"):
            print("* конфиг файл прочитан")
            self.baudrate = int(config["Serial"]["baudrate"])
            self.port = config["Serial"]["port"]
            print(self.baudrate)
            print(self.port)
        else:
            print("* конфиг файл не прочитан")
            print("* применены параметры по умолчанию")
            self.baudrate = 9600
            self.port = 'COM5'

    def precess_data(self, data):
        txt = QtCore.QTextStream(data).readAll()
        print(txt)
        try:
            time, t1, t2 = txt.split(',')
        except Exception as e:
            print(e)
            self.serialReader.close()
            # self.data_connector.clear()
            # self.plot_curve
            return
        self.data_connector.cb_append_data_point(float(t2)-float(t1), float(time)/1000)

    def openPort(self):
        self.serialReader.open()

    def closePort(self):
        self.serialReader.close()