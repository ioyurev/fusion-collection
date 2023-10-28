import os
import sys
from PySide6.QtWidgets import QApplication
from Gui import MainWindow
import logging
import datetime

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    try:
        import pyi_splash
        pyi_splash.update_text('UI Loaded ...')
        pyi_splash.close()
    except:
        pass

log_name = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S.log')
logs_folder = f'{os.path.dirname(sys.argv[0])}\\logs'
log_path = f"{logs_folder}\\{log_name}"
if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)
logging.basicConfig(level=logging.INFO, filename=log_path, filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

app = QApplication(sys.argv)
app.setStyle('Fusion')
window = MainWindow(log_path)
window.show()
sys.exit(app.exec())
