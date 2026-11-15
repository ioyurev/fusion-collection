from __future__ import annotations

import json
from pathlib import Path

from fusion_common import (
    AdditivePolynomialCalibration,
    SensorSpec,
    make_gost_thermocouples,
)
from loguru import logger as log
from pydantic import TypeAdapter

from fusion_collection.config import APPDATA_PATH

REFERENCE_STANDARDS: dict[str, float] = {
    "Hg (Ртуть, плавление)": -38.86,
    "H2O (Вода, плавление)": 0.0,
    "Ga (Галлий, плавление)": 29.76,
    "Benzoic acid (Бензойная кислота)": 122.35,
    "KNO3 (Нитрат калия, переход)": 128.85,
    "In (Индий, плавление)": 156.61,
    "Sn (Олово, плавление)": 231.92,
    "Bi (Висмут, плавление)": 271.40,
    "KClO4 (Перхлорат калия, переход)": 299.95,
    "Pb (Свинец, плавление)": 327.47,
    "Ni (Никель, точка Кюри Tc)": 354.40,
    "Zn (Цинк, плавление)": 419.53,
    "Al-Cu (Эвтектика Cu/66.9%Al)": 548.16,
    "K2SO4 (Сульфат калия, переход)": 583.85,
    "Al (Алюминий, плавление)": 660.33,
    "K2CrO4 (Хромат калия, переход)": 669.15,
    "Fe (Железо, точка Кюри Tc)": 770.00,
    "Ag-Cu (Эвтектика Cu/71.9%Ag)": 779.91,
    "BaCO3 (Карбонат бария, переход)": 808.85,
    "SrCO3 (Карбонат стронция, переход)": 932.75,
    "Ag (Серебро, плавление)": 961.78,
    "Au (Золото, плавление)": 1064.18,
    "K2SO4 (Сульфат калия, плавление)": 1069.85,
    "Cu (Медь, плавление)": 1084.62,
    "Ni (Никель, плавление)": 1455.0,
    "Fe (Железо, плавление)": 1538.0,
    "Pd (Палладий, плавление)": 1554.9,
    "Pt (Платина, плавление)": 1768.2,
    "Al2O3 (Корунд, плавление)": 2054.0,
}


class CalibrationManager:
    """Файловый менеджер калибровок температуры по стандартным образцам."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.calibrations: dict[str, AdditivePolynomialCalibration] = {}
        self.load_all()

    def save_calibration(self, calibration: AdditivePolynomialCalibration) -> None:
        safe_name = "".join(
            ch if (ch.isalnum() or ch in (" ", "-", "_")) else "_"
            for ch in calibration.name
        ).strip()
        path = self.storage_dir / f"{safe_name or 'calibration'}.json"
        path.write_text(calibration.model_dump_json(indent=2), encoding="utf-8")
        self.calibrations[calibration.name] = calibration

    def load_calibration(self, name: str) -> AdditivePolynomialCalibration:
        if name in self.calibrations:
            return self.calibrations[name]
        path = self.storage_dir / f"{name}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        cal = AdditivePolynomialCalibration.model_validate(raw)
        self.calibrations[cal.name] = cal
        return cal

    def load_all(self) -> None:
        self.calibrations.clear()
        for path in sorted(self.storage_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                cal = AdditivePolynomialCalibration.model_validate(raw)
                name = cal.name or path.stem
                cal.name = name
                self.calibrations[name] = cal
            except (OSError, ValueError) as exc:
                log.bind(path=str(path), error=str(exc)).warning(
                    "Failed to load calibration profile"
                )

    def delete_calibration(self, name: str) -> None:
        self.calibrations.pop(name, None)
        for path in self.storage_dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if raw.get("name") == name or path.stem == name:
                    path.unlink()
            except (OSError, ValueError):
                continue

    def list_names(self) -> list[str]:
        return list(self.calibrations.keys())


class ThermocoupleManager:
    """Файловый менеджер пользовательских и стандартных профилей термопар ГОСТ Р 8.585-2001."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sensors: dict[str, SensorSpec] = {}
        self._ensure_defaults_and_load()

    def _ensure_defaults_and_load(self) -> None:
        self.load_all()
        for preset in make_gost_thermocouples():
            existing = self.sensors.get(preset.name)
            if existing is None or existing != preset:
                self.save_sensor(preset)

    def save_sensor(self, sensor: SensorSpec) -> None:
        safe_stem = "".join(
            ch if (ch.isalnum() or ch in (" ", "-", "_")) else "_" for ch in sensor.name
        ).strip()
        path = self.storage_dir / f"{safe_stem or 'sensor'}.json"
        path.write_text(sensor.model_dump_json(indent=2), encoding="utf-8")
        self.sensors[sensor.name] = sensor

    def load_sensor(self, name: str) -> SensorSpec:
        if name in self.sensors:
            return self.sensors[name]
        raise KeyError(f"Профиль термопары '{name}' не найден")

    def load_all(self) -> None:
        self.sensors.clear()
        adapter: TypeAdapter[SensorSpec] = TypeAdapter(SensorSpec)
        for path in sorted(self.storage_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                sensor = adapter.validate_python(raw)
                self.sensors[sensor.name] = sensor
            except (OSError, ValueError) as exc:
                log.bind(path=str(path), error=str(exc)).warning(
                    "Failed to load thermocouple profile"
                )

    def delete_sensor(self, name: str) -> None:
        self.sensors.pop(name, None)
        for path in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("name") == name:
                    path.unlink()
            except (OSError, ValueError):
                continue

    def list_names(self) -> list[str]:
        return list(self.sensors.keys())


_cal_manager: CalibrationManager | None = None
_tc_manager: ThermocoupleManager | None = None


def get_calibration_manager() -> CalibrationManager:
    global _cal_manager
    if _cal_manager is None:
        _cal_manager = CalibrationManager(APPDATA_PATH / "calibrations")
    return _cal_manager


def get_thermocouple_manager() -> ThermocoupleManager:
    global _tc_manager
    if _tc_manager is None:
        _tc_manager = ThermocoupleManager(APPDATA_PATH / "thermocouples")
    return _tc_manager
