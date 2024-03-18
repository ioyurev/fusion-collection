from PySide6 import QtCore, QtGui, QtWidgets

from __hash__ import HASH
from __version__ import VERSION

from .helpers import read_text_from_compiled_qrc_file as get_text


class AboutWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        layout = QtWidgets.QVBoxLayout()
        label_icon = QtWidgets.QLabel()
        label_icon.setPixmap(
            QtGui.QPixmap(":/icon.png").scaled(
                128, 128, mode=QtCore.Qt.TransformationMode.SmoothTransformation
            )
        )
        layout.addWidget(label_icon)
        label_text = QtWidgets.QLabel()
        label_text.setTextFormat(QtCore.Qt.TextFormat.RichText)
        label_text.setText(
            get_text(":/about_text.html").format(hash=HASH, version=VERSION)
        )
        label_text.setOpenExternalLinks(True)
        layout.addWidget(label_text)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())


@QtCore.Slot()
def show_about():
    AboutWindow().exec()
