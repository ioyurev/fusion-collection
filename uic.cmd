if not exist fusion_collection\ui mkdir fusion_collection\ui
python devtools/git_hash.py
pyside6-uic.exe assets\CalToolWindow.ui > fusion_collection\ui\CalToolWindow.py
pyside6-uic.exe assets\MainWindow.ui > fusion_collection\ui\MainWindow.py
pyside6-uic.exe assets\NewMeasurementWindow.ui > fusion_collection\ui\NewMeasurementWindow.py

pyside6-rcc.exe assets/resources.qrc > fusion_collection\ui\resources_rc.py

autoflake -i --remove-all-unused-imports fusion_collection\ui\CalToolWindow.py
autoflake -i --remove-all-unused-imports fusion_collection\ui\MainWindow.py
autoflake -i --remove-all-unused-imports fusion_collection\ui\NewMeasurementWindow.py
