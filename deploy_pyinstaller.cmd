if not exist pyinstaller mkdir pyinstaller
cd pyinstaller

python ../devtools/splash_gen.py

..\.venv\Scripts\pyinstaller.exe ../fusion_collection/__main__.py -i ../assets/icon.png --splash splash.png -n fusion-collection --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy
python ../devtools/version_file_gen.py
pyi-set_version version_text_file dist/fusion-collection/fusion-collection.exe
xcopy ..\LICENSE .\fusion-collection\
xcopy ..\LICENSE_RU .\fusion-collection\
