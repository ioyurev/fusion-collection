import sys

import numpy as np
import pandas as pd
import pyqtgraph as pg
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets
from ui.CalToolWindow import Ui_MainWindow

from .calibration_file import (
    LABELS,
    Calibration,
    Label,
    file_to_cal,
    pick_open_path,
    pick_save_path,
)
from .helpers import warning_message

MARKER_SIZE = 5
LW = 3

pg.setConfigOption("background", "w")
pg.setConfigOption("foreground", "k")


def polyfit_coeff_to_str(coeff: np.ndarray):
    length = len(coeff)
    last_index = length - 1
    equation = ""
    for i, value in enumerate(coeff):
        coeff_str = f'{"{:.3e}".format(value)}'
        if i == last_index:
            pass
        else:
            coeff_str += f" * x<sup>{length - i - 1}</sup>"
        equation += coeff_str + " + "
    return equation[:-3]


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QtGui.QIcon(":/calibration_icon.png"))

        self.tableWidget.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.tableWidget.horizontalHeader().setStretchLastSection(True)

        self.action_new.triggered.connect(self.new)
        self.action_save.triggered.connect(self.save)
        self.action_open.triggered.connect(self.open)
        self.action_close.triggered.connect(self.close)

        self.btn_do_cal.clicked.connect(self.do_calibration)
        self.btn_add_row.clicked.connect(self.add_row)
        self.btn_del_row.clicked.connect(self.del_row)

        self.plotWidget_temp = pg.plot()
        self.plotWidget_sens = pg.plot()
        self.plotWidget_temp.setTitle("Калибровка температуры")
        self.plotWidget_sens.setTitle("Калибровка чувственности")
        self.plotWidget_temp.getPlotItem().setLabel("bottom", Label.EMF)
        self.plotWidget_temp.getPlotItem().setLabel("left", Label.TEMP)
        self.plotWidget_sens.getPlotItem().setLabel("bottom", Label.TEMP)
        self.plotWidget_sens.getPlotItem().setLabel("left", Label.SENS)
        self.plotLayout.addWidget(self.plotWidget_temp)
        self.plotLayout.addWidget(self.plotWidget_sens)
        self.redraw_figures()

    def clear_figures(self):
        self.plotWidget_temp.clear()
        self.plotWidget_sens.clear()

    def redraw_figures(self):
        self.plotWidget_temp.getPlotItem().update()
        self.plotWidget_sens.getPlotItem().update()

    @QtCore.Slot()
    def add_row(self):
        self.tableWidget.insertRow(self.tableWidget.rowCount())

    @QtCore.Slot()
    def del_row(self):
        indexes = self.tableWidget.selectedIndexes()
        rows = list[int]
        for index in indexes:
            rows.append(index.row())
        uniqie_rows: list[int] = list(set(rows))
        uniqie_rows.sort(reverse=True)
        for row in uniqie_rows:
            self.tableWidget.removeRow(row)

    def table_is_complete(self):
        for row in range(self.tableWidget.rowCount()):
            for column in range(self.tableWidget.columnCount() - 1):
                if not self.tableWidget.item(row, column):
                    warning_message(
                        "Все ячейки должны быть заполнены!\nЕсли остались неиспользованные строки, то удалите их.",
                        parent=self,
                    )
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
                log.warning("Один из стоблцов не заполнен или заполнен неправильно")
                return None
        else:
            df = pd.DataFrame()
            for index, label in enumerate(LABELS[0:-1]):
                df[label] = data[index]
            return df

    def get_column_data(self, num: int, is_numerical=False):
        lst = []
        for row in range(self.tableWidget.rowCount()):
            lst.append(self.tableWidget.item(row, num).text())
        if is_numerical:
            dtype = "float"
        else:
            dtype = "str"
        try:
            return np.array(lst, dtype=np.dtype(dtype))
        except Exception as e:
            warning_message(
                f'В столбце "{self.tableWidget.horizontalHeaderItem(num).text()}" могут быть только числовые значения!\n{e}',
                parent=self,
            )
            return None

    @QtCore.Slot()
    def do_calibration(self):
        if self.table_is_complete() and self.tableWidget.rowCount() > 0:
            self.df = self.get_data()
            if self.df is not None:
                self.clear_figures()
                self.calibration_temp()
                self.calibration_sens()
                self.redraw_figures()

    def calibration_sens(self):
        df = pd.DataFrame()
        self.df[Label.SENS] = self.df[Label.EFFECT] / self.df[Label.PEAK_AREA]
        column_index = len(LABELS) - 1
        for row, value in enumerate(self.df[Label.SENS].to_list()):
            item = QtWidgets.QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.tableWidget.setItem(row, column_index, item)

        df[Label.TEMP] = self.df[Label.TEMP]
        df[Label.SENS] = self.df[Label.SENS]
        df.sort_values(Label.TEMP, inplace=True)
        xdata = df[Label.TEMP].to_numpy()
        ydata = df[Label.SENS].to_numpy()
        coeff = np.polyfit(xdata, ydata, 2)
        yn = np.poly1d(coeff)
        Xdata = np.linspace(xdata[0], xdata[-1], 100)
        Ydata = yn(Xdata)

        scatter = pg.ScatterPlotItem(
            x=xdata,
            y=ydata,
            pen=pg.mkPen(None),
            brush=pg.mkBrush("r"),
            size=MARKER_SIZE,
        )
        self.plotWidget_sens.addItem(scatter)

        for i, (x, y) in enumerate(zip(xdata, ydata)):
            label = pg.TextItem(text=self.df[Label.SAMPLE][i], color="k")
            label.setPos(x, y)
            self.plotWidget_sens.addItem(label)

        self.plotWidget_sens.setXRange(25, 1100, padding=0)
        self.plotWidget_sens.plot(Xdata, Ydata, pen=pg.mkPen(color="b", width=LW))

        self.sens_coeff = coeff
        self.label_cal_sens.setText(f"f(x) = {polyfit_coeff_to_str(coeff)}")

    def calibration_temp(self):
        df = pd.DataFrame()
        df[Label.EMF] = self.df[Label.EMF]
        df[Label.TEMP] = self.df[Label.TEMP]
        df.sort_values(Label.EMF, inplace=True)
        xdata = df[Label.EMF].to_numpy()
        ydata = df[Label.TEMP].to_numpy()
        coeff = np.polyfit(xdata, ydata, 2)
        yn = np.poly1d(coeff)
        Xdata = np.linspace(xdata[0], xdata[-1], 100)
        Ydata = yn(Xdata)

        scatter = pg.ScatterPlotItem(
            x=xdata,
            y=ydata,
            pen=pg.mkPen(None),
            brush=pg.mkBrush("r"),
            size=MARKER_SIZE,
        )
        self.plotWidget_temp.addItem(scatter)

        for i, (x, y) in enumerate(zip(xdata, ydata)):
            label = pg.TextItem(text=self.df[Label.SAMPLE][i], color="k")
            label.setPos(x, y)
            self.plotWidget_temp.addItem(label)

        self.plotWidget_temp.setYRange(25, 1100, padding=0)
        self.plotWidget_temp.plot(Xdata, Ydata, pen=pg.mkPen(color="b", width=LW))

        self.temp_coeff = coeff
        self.label_cal_temp.setText(f"f(x) = {polyfit_coeff_to_str(coeff)}")

    @QtCore.Slot()
    def new(self):
        self.action_close.setEnabled(True)
        self.action_save.setEnabled(True)
        self.set_editor_enabled(True)
        self.clear_figures()

    @QtCore.Slot()
    def close(self):
        self.action_close.setEnabled(False)
        self.action_save.setEnabled(False)
        self.set_editor_enabled(False)
        self.clear_figures()

    @QtCore.Slot()
    def save(self):
        savepath = pick_save_path()
        if savepath == "":
            return
        log.info(f"Выбран путь для сохранения: {savepath}")
        cal = Calibration(self.df, self.temp_coeff, self.sens_coeff)
        cal.to_file(savepath)

    @QtCore.Slot()
    def open(self):
        openpath = pick_open_path()
        log.info(f"Выбран файл для открытия: {openpath}")
        if openpath == "":
            return

        self.df = file_to_cal(openpath).df
        self.set_editor_enabled(True)
        self.action_close.setEnabled(True)
        self.action_save.setEnabled(True)

        data_array = self.df.to_numpy()
        rows_num = data_array.shape[0]
        self.tableWidget.setColumnCount(len(LABELS))
        self.tableWidget.setHorizontalHeaderLabels(LABELS)
        self.tableWidget.setRowCount(rows_num)
        for row in range(data_array.shape[0]):
            for col in range(data_array.shape[1]):
                value = data_array[row, col]
                item = QtWidgets.QTableWidgetItem(str(value))
                self.tableWidget.setItem(row, col, item)
        self.do_calibration()

    def create_table(self):
        self.tableWidget.clearContents()
        self.tableWidget.setColumnCount(len(LABELS))
        self.tableWidget.setRowCount(3)
        self.tableWidget.setHorizontalHeaderLabels(LABELS)
        column_index = len(LABELS) - 1
        for row in range(self.tableWidget.rowCount()):
            item = QtWidgets.QTableWidgetItem()
            item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.tableWidget.setItem(row, column_index, item)

    def clear_table(self):
        self.tableWidget.clearContents()
        self.tableWidget.setColumnCount(0)
        self.tableWidget.setRowCount(0)

    def set_editor_enabled(self, enabled: bool):
        self.tableWidget.setEnabled(enabled)
        self.btn_add_row.setEnabled(enabled)
        self.btn_del_row.setEnabled(enabled)
        self.btn_do_cal.setEnabled(enabled)
        if enabled:
            self.create_table()
        else:
            self.clear_table()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
