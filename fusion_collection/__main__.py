from __future__ import annotations

import sys

from fusion_common.splash import (
    COLLECTION_ICON_BG,
    finish_startup_splash,
    show_startup_splash,
)
from PySide6.QtWidgets import QApplication

from fusion_collection.version import VERSION


def main() -> None:
    app = QApplication(sys.argv)
    splash = show_startup_splash(
        app=app,
        subtitle="Thermal Data Collection",
        version_str=VERSION,
        icon_bg_color=COLLECTION_ICON_BG,
    )

    from fusion_common.splash import setup_fusion_logging  # noqa: PLC0415

    from fusion_collection.config import APPDATA_PATH  # noqa: PLC0415
    from fusion_collection.main_window import MainWindow  # noqa: PLC0415

    setup_fusion_logging(APPDATA_PATH)
    window = MainWindow()
    window.show()
    finish_startup_splash(splash, window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
