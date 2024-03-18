import sys

import ui.resources_rc  # noqa
from loguru import logger as log
from PySide6.QtWidgets import QApplication

from fusion_collection.Gui import MainWindow


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
