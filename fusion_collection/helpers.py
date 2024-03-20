from threading import Thread
from typing import Callable

from loguru import logger as log
from PySide6 import QtCore, QtWidgets


def time_to_str(time: float):
    min = int(time // 60)
    sec = int(time % 60)
    return f"{min:02d}:{sec:02d}"


def read_text_from_compiled_qrc_file(filepath: str):
    file = QtCore.QFile(filepath)
    if file.open(QtCore.QFile.OpenModeFlag.ReadOnly | QtCore.QFile.OpenModeFlag.Text):
        text = file.readAll().data().decode("utf-8")
        file.close()
        return text
    else:
        raise RuntimeError(f"Не удалось открыть файл {filepath}")


class FunctionExecutor(Thread):
    def __init__(self, f: Callable):
        self.f = f
        super().__init__()
        self.result = None

    def run(self):
        self.result = self.f()


def check_function_timeout(f: Callable, t: int) -> tuple:
    thread = FunctionExecutor(f)
    thread.start()
    thread.join(timeout=t)
    result = thread.result
    alive = thread.is_alive()
    if alive:
        log.warning(f"Функция {f.__name__} не выполнилась за {t} секунд.")
    return (alive, result)


def error_message(message: str, parent=None):
    QtWidgets.QMessageBox.critical(parent, "Ошибка", message)


def warning_message(message: str, parent=None):
    QtWidgets.QMessageBox.warning(parent, "Предупреждение", message)
