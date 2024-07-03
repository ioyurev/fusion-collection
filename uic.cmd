if not exist fusion_collection\ui mkdir fusion_collection\ui
if not exist fusion_collection\ui\__init__.py cd . > fusion_collection\ui\__init__.py
python devtools/git_hash.py
.venv\Scripts\pyside6-uic.exe assets\CalToolWindow.ui > fusion_collection\ui\CalToolWindow.py
.venv\Scripts\pyside6-uic.exe assets\MainWindow.ui > fusion_collection\ui\MainWindow.py
.venv\Scripts\pyside6-uic.exe assets\NewMeasurementWindow.ui > fusion_collection\ui\NewMeasurementWindow.py
.venv\Scripts\pyside6-uic.exe assets\AboutWindow.ui > fusion_collection\ui\AboutWindow.py

.venv\Scripts\pyside6-rcc.exe resources.qrc > fusion_collection\ui\resources_rc.py

.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_collection\ui\CalToolWindow.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_collection\ui\MainWindow.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_collection\ui\NewMeasurementWindow.py
.venv\Scripts\autoflake -i --remove-all-unused-imports fusion_collection\ui\AboutWindow.py
