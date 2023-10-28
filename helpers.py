from PySide6 import QtWidgets
from threading import Thread
from typing import Callable
import logging

class FunctionExecutor(Thread):
    def __init__(self, f: Callable):
        self.f = f
        super().__init__()
        self.result = None

    def run(self):
        self.result = self.f()

def check_function_timeout(f: Callable, t: int) -> bool:
    thread = FunctionExecutor(f)
    thread.start()
    thread.join(timeout=t)
    result = thread.result
    alive = thread.is_alive()
    if alive:
        log_warning(f'Функция {f.__name__} не выполнилась за {t} секунд.')
    return (alive, result)

def log_critical(message: str):
    print(f'CRTICALL: {message}')
    logging.critical(f'{message}')

def log_warning(message: str):
    print(f'WARNING: {message}')
    logging.warning(f'{message}')

def log_info(message: str):
    print(f'INFO: {message}')
    logging.info(f'{message}')

def error_message(message):
    print(f'* Вывод окна об ошибке.\n{message}')
    QtWidgets.QMessageBox.critical(None, "Ошибка", message)

def warning_message(message):
    print(f'* Вывод окна предупреждения.\n{message}')
    QtWidgets.QMessageBox.warning(None, "Предупреждение", message)