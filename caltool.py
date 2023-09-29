import sys
from PySide6 import QtWidgets, QtUiTools, QtGui
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

class NumberDelegate(QtWidgets.QItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent)
        validator = QtGui.QDoubleValidator()
        editor.setValidator(validator)
        return editor

    def setModelData(self, editor, model, index):
        text = editor.text()
        model.setData(index, float(text))


Ui_MainWindow, QMainWindow = QtUiTools.loadUiType('caltool.ui')

class MainWindow(QMainWindow, Ui_MainWindow):
    tableWidget: QtWidgets.QTableWidget
    plotLayout: QtWidgets.QHBoxLayout

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # self.showMaximized()
        self.tableWidget.setColumnCount(5)
        labels = ['Образец', 'Температура, °C', 'Масса, г', 'Сигнал термопары, мВ', 'Площадь пика']
        self.tableWidget.setRowCount(5)
        self.tableWidget.setHorizontalHeaderLabels(labels)
        
        self.fig_temp = plt.figure()
        self.fig_sens = plt.figure()
        self.ax_temp = self.fig_temp.add_subplot(111)
        self.ax_sens = self.fig_sens.add_subplot(111)
        self.canvas_temp = FigureCanvas(self.fig_temp)
        self.canvas_sens = FigureCanvas(self.fig_sens)
        self.plotLayout.addWidget(self.canvas_temp)
        self.plotLayout.addWidget(self.canvas_sens)
        self.ax_temp.set_title('Калибровка температуры')
        self.ax_sens.set_title('Калибровка чувствительности')
        self.fig_temp.tight_layout()
        self.fig_sens.tight_layout()

        # self.tableWidget.setItemDelegateForColumn(2, NumberDelegate())
        # self.tableWidget.setItemDelegateForColumn(3, NumberDelegate())

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())