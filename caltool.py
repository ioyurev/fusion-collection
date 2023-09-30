import sys
import numpy as np
from PySide6 import QtWidgets, QtUiTools, QtGui
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import zipfile
import tempfile
import pandas as pd

LABEL_SAMPLE = 'Образец'
LABEL_TEMP = 'Температура,\n°C'
LABEL_EMF = 'Сигнал температурной\nтермопары, мВ'
LABEL_PAREA = 'Площадь пика,\nмВ*с'
LABEL_TEFF = 'Тепловой эффект,\nДж/г'
LABELS = [LABEL_SAMPLE, LABEL_TEMP, LABEL_TEFF, LABEL_EMF, LABEL_PAREA]

def pick_save_path():
    return QtWidgets.QFileDialog.getSaveFileName(None, 'Save file')[0]

def pick_open_path():
    return QtWidgets.QFileDialog.getOpenFileName(None, 'Open file')[0]

def warning_message(text: str):
    print(f'* Предупреждение. {text}')
    QtWidgets.QMessageBox.warning(None, "Предупреждение", text)

Ui_MainWindow, QMainWindow = QtUiTools.loadUiType('caltool.ui')

class MainWindow(QMainWindow, Ui_MainWindow):
    tableWidget: QtWidgets.QTableWidget
    plotLayout: QtWidgets.QHBoxLayout
    btn_do_cal: QtWidgets.QPushButton
    btn_add_row: QtWidgets.QPushButton
    btn_del_row: QtWidgets.QPushButton
    action_save: QtGui.QAction
    action_open: QtGui.QAction
    label_cal_temp: QtWidgets.QLabel
    label_cal_sens: QtWidgets.QLabel

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        # self.showMaximized()

        self.action_save.triggered.connect(self.save)
        self.action_open.triggered.connect(self.open)

        self.tableWidget.setColumnCount(len(LABELS))
        self.tableWidget.setRowCount(3)
        self.tableWidget.setHorizontalHeaderLabels(LABELS)
        self.tableWidget.resizeColumnsToContents()

        self.btn_do_cal.clicked.connect(self.do_calibration)
        self.btn_add_row.clicked.connect(self.add_row)
        self.btn_del_row.clicked.connect(self.del_row)

        self.fig_temp = plt.figure()
        self.fig_sens = plt.figure()
        self.ax_temp = self.fig_temp.add_subplot(111)
        self.ax_sens = self.fig_sens.add_subplot(111)
        self.ax_temp.set_xlabel(LABEL_EMF)
        self.ax_temp.set_ylabel(LABEL_TEMP)
        self.ax_sens.set_xlabel(LABEL_PAREA)
        self.ax_sens.set_ylabel(LABEL_TEFF)
        self.canvas_temp = FigureCanvas(self.fig_temp)
        self.canvas_sens = FigureCanvas(self.fig_sens)
        self.plotLayout.addWidget(self.canvas_temp)
        self.plotLayout.addWidget(self.canvas_sens)
        self.redraw_figures()

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
        for el in data:
            if el is None:
                print('* Один из стоблцов не заполнен или заполнен неправильно')
                return None
        else:
            df = pd.DataFrame()
            for index, label in enumerate(LABELS):
                df[label] = data[index]
            return df

    def get_column_data(self, num: int, is_numerical=False):
        lst = []
        for row in range(self.tableWidget.rowCount()):
            lst.append(self.tableWidget.item(row, num).text())
        if is_numerical:
            dtype=float
        else:
            dtype=str
        try:
            return np.array(lst, dtype=dtype)
        except:
            warning_message(f'В столбце "{self.tableWidget.horizontalHeaderItem(num).text()}" могут быть только числовые значения!')
            return None

    def do_calibration(self):
        if self.table_is_complete():
            self.df = self.get_data()
            if self.df is not None:
                self.clear_figures()
                self.calibration_temp()
                self.calibration_sens()
                self.redraw_figures()

    def calibration_sens(self):
        df = pd.DataFrame()
        df[LABEL_PAREA] = self.df[LABEL_PAREA]
        df[LABEL_TEFF] = self.df[LABEL_TEFF]
        df.sort_values(LABEL_PAREA, inplace=True)
        xdata = df[LABEL_PAREA].to_numpy()
        ydata = df[LABEL_TEFF].to_numpy()
        coeff = np.polyfit(xdata, ydata, 2)
        yn = np.poly1d(coeff)
        Xdata = np.linspace(xdata[0], xdata[-1], 100)
        Ydata = yn(Xdata)
        self.ax_sens.scatter(xdata, ydata, s=3, color='red')
        for i in range(len(self.df[LABEL_SAMPLE])):
            self.ax_sens.text(xdata[i], ydata[i], ' '+self.df[LABEL_SAMPLE][i])
        self.ax_sens.plot(Xdata, Ydata, lw=1, color='blue')
        self.sens_coeff = coeff
        self.label_cal_sens.setText(f'f(x) = {"{:.3e}".format(coeff[0])} * x^2 + {"{:.3e}".format(coeff[1])} * x + {"{:.3e}".format(coeff[2])}')

    def calibration_temp(self):
        df = pd.DataFrame()
        df[LABEL_EMF] = self.df[LABEL_EMF]
        df[LABEL_TEMP] = self.df[LABEL_TEMP]
        df.sort_values(LABEL_EMF, inplace=True)
        xdata = df[LABEL_EMF].to_numpy()
        ydata = df[LABEL_TEMP].to_numpy()
        coeff = np.polyfit(xdata, ydata, 2)
        yn = np.poly1d(coeff)
        Xdata = np.linspace(xdata[0], xdata[-1], 100)
        Ydata = yn(Xdata)
        self.ax_temp.scatter(xdata, ydata, s=3, color='red')
        for i in range(len(self.df[LABEL_SAMPLE])):
            self.ax_temp.text(xdata[i], ydata[i], ' '+self.df[LABEL_SAMPLE][i])
        self.ax_temp.plot(Xdata, Ydata, lw=1, color='blue')
        self.temp_coeff = coeff
        self.label_cal_temp.setText(f'f(x) = {"{:.3e}".format(coeff[0])} * x^2 + {"{:.3e}".format(coeff[1])} * x + {"{:.3e}".format(coeff[2])}')

    def save(self):
        savepath = pick_save_path()
        print(f'* Выбран путь для сохранения: {savepath}')
        if savepath:
            with tempfile.TemporaryDirectory() as tempdir:
                print(f'* Создана временная папка для сохранения: {tempdir}')
                with open(f'{tempdir}/VERSION', 'w') as f:
                    f.write(str(1))
                self.df.to_csv(f'{tempdir}/{"data.csv"}', index=False)
                np.savetxt(f'{tempdir}/{"coeff_temp.csv"}', self.temp_coeff, delimiter=',')
                np.savetxt(f'{tempdir}/{"coeff_sens.csv"}', self.sens_coeff, delimiter=',')
                with zipfile.ZipFile(savepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(f'{tempdir}/VERSION', arcname='VERSION')
                    zipf.write(f'{tempdir}/{"data.csv"}', arcname='data.csv')
                    zipf.write(f'{tempdir}/{"coeff_temp.csv"}', arcname='coeff_temp.csv')
                    zipf.write(f'{tempdir}/{"coeff_sens.csv"}', arcname='coeff_sens.csv')

    def open(self):
        openpath = pick_open_path()
        if openpath:
            with zipfile.ZipFile(openpath, 'r') as zipf:
                self.df = pd.read_csv(zipf.open('data.csv'), sep=',', decimal='.')
        data_array = self.df.to_numpy()
        rows_num = data_array.shape[0]
        self.tableWidget.setRowCount(rows_num)
        for row in range(data_array.shape[0]):
            for col in range(data_array.shape[1]):
                value = data_array[row, col]
                item = QtWidgets.QTableWidgetItem(str(value))
                self.tableWidget.setItem(row, col, item)
        self.do_calibration()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
