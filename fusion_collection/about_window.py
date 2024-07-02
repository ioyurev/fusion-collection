from PySide6 import QtCore, QtWidgets

from .__version__ import VERSION
from .helpers import read_text_from_compiled_qrc_file as get_text
from .ui.__hash__ import HASH
from .ui.AboutWindow import Ui_Dialog


class AboutWindow(QtWidgets.QDialog, Ui_Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.label_about.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.label_about.setText(
            get_text(":/assets/about_text.html").format(hash=HASH, version=VERSION)
        )
        self.label_about.setOpenExternalLinks(True)
        self.text_license.setText(get_text(":/LICENSE_RU"))
        self.adjustSize()
        size = self.size()
        size.setWidth(600)
        self.setFixedSize(size)
