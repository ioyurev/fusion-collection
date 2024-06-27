if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
pyinstaller ../fusion_collection/__main__.py -i ../assets/icon.png --splash ../fusion_collection/ui/splash.png -n fusion-collection --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy
py ../devtools/version_file_gen.py
pyi-set_version version_text_file dist/fusion-collection/fusion-collection.exe
