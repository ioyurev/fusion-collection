if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
rd /f dist
pyinstaller ../main.py -i ../assets/icon.png --splash ../assets/splash.png -n fusion-collection -w --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy