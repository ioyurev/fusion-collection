@echo off
chcp 65001 >nul
if not exist pyinstaller mkdir pyinstaller
cd pyinstaller
uv run fusion-splash --subtitle "Thermal Data Collection" --bg-color "#FD700D" --svg-out ../assets/icon.svg --icon-out icon.ico --version-from .. --out splash.png || exit /b 1
uv run pyinstaller ../fusion_collection/__main__.py --noconsole -i icon.ico --splash splash.png --collect-data fusion_common --collect-data fusion_collection -n fusion-collection --noconfirm --exclude-module PyQt6 --exclude-module PyQt5 --exclude-module scipy || exit /b 1
uv run fusion-packaging version-file --package fusion-collection --product "Fusion Collection" --description "Fusion Collection (VTA & DTA)" --version-from .. --out version_text_file || exit /b 1
uv run pyi-set_version version_text_file dist/fusion-collection/fusion-collection.exe || exit /b 1
uv run fusion-docs --package fusion_collection --out-dir dist/fusion-collection || exit /b 1
uv run fusion-packaging zip-dist --package fusion-collection --version-from .. --dist-root dist || exit /b 1
uv run fusion-packaging installer --package fusion-collection --product "Fusion Collection" --version-from .. --dist-root dist --icon icon.ico || exit /b 1
pause
