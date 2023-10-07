from PySide6 import QtWidgets

def warning_message(text: str):
    print(f'* Предупреждение. {text}')
    QtWidgets.QMessageBox.warning(None, "Предупреждение", text)