"""Vulture whitelist for Qt virtual hooks and entrypoints in fusion-collection."""

from fusion_collection.acquisition import AcquisitionLoop
from fusion_collection.adam_config import SlewRateCode
from fusion_collection.config import Config
from fusion_collection.dialogs import ModuleConfigWarningDialog
from fusion_collection.hardware import Adam4011Module
from fusion_collection.main_window import MainWindow

_HOOKS = (
    Config.serialize_path,
    MainWindow.closeEvent,
    AcquisitionLoop.run,
    SlewRateCode.SR_00625,
    SlewRateCode.SR_0125,
    SlewRateCode.SR_025,
    SlewRateCode.SR_05,
    SlewRateCode.SR_1,
    SlewRateCode.SR_2,
    SlewRateCode.SR_4,
    SlewRateCode.SR_8,
    SlewRateCode.SR_16,
    SlewRateCode.SR_32,
    SlewRateCode.SR_64,
    ModuleConfigWarningDialog.btn_apply,
    Adam4011Module.firmware,
)
