import sys
import numpy as np
from PySide6 import QtWidgets, QtUiTools, QtGui
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

def str_to_float(lst: list):
    return [float(x) for x in lst]

def to_str(lst):
    return [str(x) for x in lst]

def warning_message(text: str):
    print(f'* Предупреждение. {text}')
    QtWidgets.QMessageBox.warning(None, "Предупреждение", text)

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
    btn_do_cal: QtWidgets.QPushButton
    btn_add_row: QtWidgets.QPushButton
    btn_del_row: QtWidgets.QPushButton
    action_save: QtGui.QAction

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # self.showMaximized()

        self.action_save.triggered.connect(self.save)

        self.tableWidget.setColumnCount(5)
        labels = ['Образец', 'Температура, °C', 'Тепловой эффект, Дж/г', 'Сигнал термопары, мВ', 'Площадь пика, мВ*с']
        self.tableWidget.setRowCount(3)
        self.tableWidget.setHorizontalHeaderLabels(labels)

        self.btn_do_cal.clicked.connect(self.do_calibration)
        self.btn_add_row.clicked.connect(self.add_row)
        self.btn_del_row.clicked.connect(self.del_row)

        self.fig_temp = plt.figure()
        self.fig_sens = plt.figure()
        self.ax_temp = self.fig_temp.add_subplot(111)
        self.ax_sens = self.fig_sens.add_subplot(111)
        self.ax_temp.set_xlabel('Сигнал термопары, мВ')
        self.ax_temp.set_ylabel('Температура, °C')
        self.ax_sens.set_xlabel('Площадь пика, мВ*с')
        self.ax_sens.set_ylabel('Тепловой эффект, Дж/г')
        self.canvas_temp = FigureCanvas(self.fig_temp)
        self.canvas_sens = FigureCanvas(self.fig_sens)
        self.plotLayout.addWidget(self.canvas_temp)
        self.plotLayout.addWidget(self.canvas_sens)
        self.redraw_figures()
        # self.tableWidget.setItemDelegateForColumn(2, NumberDelegate())
        # self.tableWidget.setItemDelegateForColumn(3, NumberDelegate())

    def clear_figures(self):
        self.ax_temp.clear()
        self.ax_sens.clear()

    def redraw_figures(self):
        self.fig_temp.tight_layout()
        self.fig_sens.tight_layout()
        self.canvas_temp.draw()
        self.canvas_sens.draw()

    def add_row(self):
        self.tableWidget.insertRow(self.tableWidget.rowCount())

    def del_row(self):
        indexes = self.tableWidget.selectedIndexes()
        rows: list[int] = []
        for index in indexes:
            rows.append(index.row())
        uniqie_rows: list[int] = list(set(rows))
        uniqie_rows.sort(reverse=True)
        # print(uniqie_rows)
        for row in uniqie_rows:
            self.tableWidget.removeRow(row)

    def table_is_complete(self):
        for row in range(self.tableWidget.rowCount()):
            for column in range(self.tableWidget.columnCount()):
                if not self.tableWidget.item(row, column):
                    warning_message('Все ячейки должны быть заполнены!\nЕсли остались неиспользованные строки, то удалите их.')
                    return False
        return True

    def get_data(self):
        name = self.get_column_data(0)
        temperature = self.get_column_data(1, is_numerical=True)
        thermal_effect = self.get_column_data(2, is_numerical=True)
        emf_signal = self.get_column_data(3, is_numerical=True)
        peak_area = self.get_column_data(4, is_numerical=True)
        data = (name, temperature, thermal_effect, emf_signal, peak_area) 
        if None in data:
            print('* Один из стоблцов не заполнен или заполнен неправильно')
            return None
        else:
            return data

    def get_column_data(self, num: int, is_numerical=False):
        lst = []
        result = None
        for row in range(self.tableWidget.rowCount()):
            lst.append(self.tableWidget.item(row, num).text())
        if is_numerical:
            try:
                result = str_to_float(lst)
            except:
                warning_message(f'В столбце "{self.tableWidget.horizontalHeaderItem(num).text()}" могут быть только числовые значения!')
        else:
            result = lst
        return result

    def do_calibration(self):
        if self.table_is_complete():
            self.data = self.get_data()
            if self.data is not None:
                self.clear_figures()
                self.calibration_temp(name=self.data[0], temp=self.data[1], emf=self.data[3])
                self.calibration_sens(name=self.data[0], thermal_effect=self.data[2], peak_area=self.data[4])
                self.redraw_figures()

    def calibration_sens(self, name: list[str], peak_area: list[float], thermal_effect: list[float]):
        xdata = peak_area
        ydata = thermal_effect
        coeff = np.polyfit(xdata, ydata, 2)
        yn = np.poly1d(coeff)
        Xdata = np.linspace(xdata[0], xdata[-1], 100)
        Ydata = yn(Xdata)
        self.ax_sens.scatter(xdata, ydata)
        self.ax_sens.plot(Xdata, Ydata)
        self.temp_coeff = coeff

    def calibration_temp(self, name: list[str], temp: list[float], emf: list[float]):
        xdata = emf
        ydata = temp
        coeff = np.polyfit(xdata, ydata, 2)
        yn = np.poly1d(coeff)
        Xdata = np.linspace(xdata[0], xdata[-1], 100)
        Ydata = yn(Xdata)
        self.ax_temp.scatter(xdata, ydata)
        self.ax_temp.plot(Xdata, Ydata)
        self.sens_coeff = coeff

    def save(self):
        with open('test_data/test.fus-cal-data', 'w') as f:
            for line in self.data:
                f.writelines(str(line))
        with open('test_data/test.fus-cal-coeff', 'w') as f:
            f.writelines(str(self.temp_coeff))
            f.writelines(str(self.sens_coeff))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())