import sys

from loguru import logger as log
from PySide6.QtWidgets import QApplication

from fusion_collection.main_window import MainWindow
from fusion_collection.ui import resources_rc  # noqa


def main():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        import pyi_splash

        pyi_splash.close()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    log.add("logs/{time}.log")
    main()
