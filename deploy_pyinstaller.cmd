py git_hash.py
if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
rd /f dist
pyinstaller ../main.py -i ../assets/icon.png --splash ../assets/splash.png -n fusion-collection --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy
if not exist version_text_file pyi-grab_version.exe C:\Windows\System32\cmd.exe version_text_file
py ../version_file_gen.py
pyi-set_version version_text_file dist/fusion-collection/fusion-collection.exe
