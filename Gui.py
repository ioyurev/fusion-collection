from PySide6 import QtWidgets, QtUiTools
from Serial import SerialReader, get_serial_ports
from Plotter import Plotter, LivePlotWidget
from pglive.sources.data_connector import DataConnector

Ui_MainWindow, QMainWindow = QtUiTools.loadUiType('MainWindow.ui')

class MainWindow(QMainWindow, Ui_MainWindow):
    plotWidget: LivePlotWidget
    btnOpen: QtWidgets.QPushButton
    btnClose : QtWidgets.QPushButton
    combobo_ports : QtWidgets.QComboBox

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.combobo_ports.addItems(get_serial_ports())

        self.btnOpen.clicked.connect(self.openPort)
        self.btnClose.clicked.connect(self.closePort)

        self.serialReader = SerialReader()
        self.plotter = Plotter(self.plotWidget)
        # self.plotWidget.setBackground('w')
        self.data_connector = DataConnector(self.plotter.plot_curve, max_points=600, update_rate=10, plot_rate=1)
        self.serialReader.received_data.connect(self.process_data)

    def process_data(self, data: tuple[float, bytes, bytes]):
        tm = round(data[0], 3)
        t1 = float(data[1].decode('utf-8').strip()[1:])
        t2 = float(data[2].decode('utf-8').strip()[1:])
        print(tm, t1, t2)
        self.data_connector.cb_append_data_point(t2-t1, tm)

    def openPort(self):
        self.serialReader.port = self.combobo_ports.currentText()
        self.serialReader.start()

    def closePort(self):
        self.serialReader.close()
    