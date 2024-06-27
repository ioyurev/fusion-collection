import sys

from loguru import logger as log
from PySide6.QtWidgets import QApplication

from fusion_collection.main_window import MainWindow
from fusion_collection.ui import resources_rc  # noqa


def close_splash():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        import pyi_splash

        pyi_splash.close()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    close_splash()
    sys.exit(app.exec())


if __name__ == "__main__":
    log.add("logs/{time}.log")
    main()
