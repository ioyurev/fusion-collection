from pathlib import Path

from PySide6 import QtCore, QtWidgets

from .calibration_file import file_to_cal
from .caltool import pick_open_path
from .config import config
from .data_collections import MeasurementInfo
from .data_file import pick_save_path
from .helpers import error_message
from .ui.NewMeasurementWindow import Ui_Dialog


class NewMeasurementWindow(QtWidgets.QDialog, Ui_Dialog):
    signal_accepted = QtCore.Signal(MeasurementInfo)

    def __init__(self, parent):
        super().__init__(parent)
        self.setupUi(self)
        self.cal = None
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.btn_path.clicked.connect(self.pick_savepath)
        self.btn_choose_cal.clicked.connect(self.pick_calibration)
        self.btn_reset_cal.clicked.connect(self.reset_calibration)
        self.btn_reset_cal.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton
            )
        )
        self.btn_path.setIcon(
            QtWidgets.QApplication.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DialogOpenButton
            )
        )
        self.edit_operator.setText(config.recent_operator)

    def accept(self):
        savepath = Path(self.edit_path.text())
        if not savepath.is_absolute():
            error_message("Путь для сохранения не выбран.", parent=self)
            return
        operator = self.edit_operator.text()
        sample = self.edit_sample.text()
        comment = self.edit_comment.toPlainText()
        mi = MeasurementInfo(
            savepath=savepath,
            operator=operator,
            sample=sample,
            comment=comment,
            cal=self.cal,
        )
        config.recent_operator = operator
        config.write()
        self.close()
        self.signal_accepted.emit(mi)

    def pick_savepath(self):
        path = pick_save_path()
        self.edit_path.setText(path)

    def pick_calibration(self):
        path = pick_open_path()
        if path.is_file():
            self.cal = file_to_cal(path)
            self.btn_choose_cal.setText(path.name)

    def reset_calibration(self):
        self.cal = None
        self.btn_choose_cal.setText("Выбрать")
