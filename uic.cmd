pyside6-uic.exe ui\src\CalToolWindow.ui > ui\CalToolWindow.py
pyside6-uic.exe ui\src\MainWindow.ui > ui\MainWindow.py
pyside6-uic.exe ui\src\WindowNewMeasurement.ui > ui\WindowNewMeasurement.py

pyside6-rcc.exe assets/resources.qrc > resources_rc.py