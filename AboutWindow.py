from PySide6 import QtWidgets, QtGui, QtCore

TEXT = """
Fussion Analysis<br>
<br>
Программа сбора данных термического анализа<br>
Автор: Юрьев И.О<br>
i.o.yurev@yandex.ru<br>
Тюмень, 2023 г.<br>
<br>
<a href=\"https://www.flaticon.com/free-icons/melt\">Melt icon created by Vitaly Gorbachev - Flaticon</a><br>
<br>
<a href=\"https://www.flaticon.com/free-icons/document\">Document icon created by Freepik - Flaticon</a><br>
<br>
<a href=\"https://www.flaticon.com/free-icons/settings\">Settings icons created by dmitri13 - Flaticon</a><br>
"""


class AboutWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setWindowIcon(QtGui.QIcon(":/icon.png"))
        layout = QtWidgets.QVBoxLayout()
        label_icon = QtWidgets.QLabel()
        label_icon.setPixmap(
            QtGui.QPixmap(":/icon.png").scaled(
                128, 128, mode=QtCore.Qt.SmoothTransformation
            )
        )
        layout.addWidget(label_icon)
        label_text = QtWidgets.QLabel()
        label_text.setTextFormat(QtCore.Qt.RichText)
        label_text.setText(TEXT)
        label_text.setOpenExternalLinks(True)
        layout.addWidget(label_text)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())


def show_about():
    AboutWindow().exec()


if __name__ == "__main__":
    app = QtWidgets.QApplication()
    show_about()
    app.exec()
