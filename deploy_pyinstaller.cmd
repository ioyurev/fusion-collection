if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
pyinstaller ../main.py -i ../assets/icon.ico --splash ../assets/splash.png -n fusion-collection -w --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy