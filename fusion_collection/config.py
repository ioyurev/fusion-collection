from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Final

from fusion_common import get_appdata_path
from loguru import logger as log
from pydantic import BaseModel, Field, field_serializer


class StandMode(StrEnum):
    VTA = "vta"
    DTA = "dta"


class Config(BaseModel):
    """Единая конфигурация стенда термического анализа (ВТА / ДТА)."""

    mode: StandMode = StandMode.VTA
    instrument: str = ""
    operator: str = "Operator"
    crucible: str = ""
    atmosphere: str = ""
    comport: str = "COM1"
    adam_baudrate: int = 9600
    adam4011_t1_address: int = 1
    adam4011_t2_address: int = 2
    adam4021_address: int = 3
    thermocouple_t1: str = "ТВР (тип А-1, Вольфрам-Рений)"
    thermocouple_t2: str = "ТХА (тип K, Хромель-Алюмель)"
    calibration_enabled: bool = False
    last_selected_calibration: str = ""
    custom_standards: dict[str, float] = Field(default_factory=dict)
    antialias: bool = True
    is_test_mode: bool = False
    default_speed: int = 5
    last_save_measurement_index: int = 1
    last_save_dir: Path = Field(default_factory=Path.cwd)

    @field_serializer("last_save_dir")
    def serialize_path(self, value: Path) -> str:
        return str(value)

    @classmethod
    def from_file(cls, path: Path) -> Config:
        if path.exists():
            try:
                raw = path.read_text(encoding="utf-8")
                return cls.model_validate_json(raw)
            except (OSError, ValueError) as exc:
                log.bind(path=str(path), error=str(exc)).warning(
                    "Failed to read config.json, using defaults"
                )
        cfg = cls()
        cfg.save(path)
        return cfg

    def save(self, path: Path | None = None) -> None:
        target = path if path is not None else CONFIG_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def update(self) -> None:
        self.save(CONFIG_PATH)


APPDATA_PATH: Final[Path] = get_appdata_path("fusion-collection")
CONFIG_PATH: Final[Path] = APPDATA_PATH / "config.json"
config = Config.from_file(CONFIG_PATH)
