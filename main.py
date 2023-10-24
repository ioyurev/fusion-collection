import sys
from PySide6.QtWidgets import QApplication
from Gui import MainWindow

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    try:
        import pyi_splash
        pyi_splash.update_text('UI Loaded ...')
        pyi_splash.close()
    except:
        pass

app = QApplication(sys.argv)
app.setStyle('Fusion')
window = MainWindow()
window.show()
sys.exit(app.exec())
