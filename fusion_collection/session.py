from __future__ import annotations

import contextlib
import os
import sys
from collections import deque
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

import numpy as np
from fusion_common import (
    CalibrationSpec,
    ChannelDescriptor,
    ChannelKey,
    CjcData,
    IdentityCalibration,
    MeasurementManifest,
    MeasurementRecord,
    SensorSpec,
    evaluate_channel_temperature,
    save_fus,
)
from fusion_common import (
    __version__ as common_version,
)
from loguru import logger as log

from fusion_collection.config import StandMode, config
from fusion_collection.recovery import (
    StagingDirWriter,
    get_recovery_root,
    pack_staging_dir_to_fus,
)
from fusion_collection.version import VERSION

if TYPE_CHECKING:
    from pathlib import Path

    from fusion_collection.acquisition import LiveSample


@dataclass(frozen=True)
class EvaluatedPoint:
    """Результат пересчёта живого отсчёта в физические величины сессии."""

    rel_time_s: float
    temp_1_c: float
    dta_mv: float
    heating_rate_c_min: float = 0.0


class MeasurementSession:
    """Сессия записи измерения (ВТА или ДТА) с сохранением в единый по-канальный формат .fus."""

    def __init__(
        self,
        mode: str,
        sample: str,
        operator: str,
        comment: str = "",
        sample_mass_mg: float | None = None,
        crucible: str = "",
        atmosphere: str = "",
        sensor_t1: SensorSpec | None = None,
        sensor_t2: SensorSpec | None = None,
        calibration_t1: CalibrationSpec | None = None,
        recovery_root: Path | None = None,
    ) -> None:
        self.mode = mode
        self.sample = sample
        self.operator = operator
        self.comment = comment
        self.sample_mass_mg = sample_mass_mg
        self.crucible = crucible
        self.atmosphere = atmosphere
        self.sensor_t1 = sensor_t1
        self.sensor_t2 = sensor_t2
        self.calibration_t1: CalibrationSpec = calibration_t1 or IdentityCalibration()
        self.cjc_t1: CjcData = CjcData()
        self._last_cjc_temp_c: float | None = None

        self.recording_enabled: bool = False
        self.has_unsaved_data: bool = False
        self._t0: float | None = None
        self._rate_window: deque[tuple[float, float]] = deque(maxlen=50)
        self.reserved_path: Path | None = None
        self._locked_fh: IO[bytes] | None = None
        self._recovery_root: Path = get_recovery_root(recovery_root)
        self._staging_writer: StagingDirWriter | None = None
        self._staging_write_failed: bool = False
        self.time_list: list[float] = []
        self.emf_1_list: list[float] = []
        self.emf_2_list: list[float] = []
        self.temp_1_list: list[float] = []
        self.dta_list: list[float] = []
        self.heater_out_list: list[float] = []

    @property
    def active_staging_dir(self) -> Path | None:
        return (
            self._staging_writer.staging_dir
            if self._staging_writer is not None
            else None
        )

    def update_cjc(self, cjc_temp_c: float) -> None:
        if self._last_cjc_temp_c == cjc_temp_c:
            return
        self._last_cjc_temp_c = cjc_temp_c
        if self.sensor_t1 is not None:
            self.cjc_t1 = CjcData.from_sensor(cjc_temp_c, self.sensor_t1)
        else:
            self.cjc_t1 = CjcData(temperature=cjc_temp_c, e_cold=0.0)
        if self._staging_writer is not None and not self._staging_write_failed:
            try:
                self._staging_writer.update_manifest(self.build_manifest())
            except OSError as exc:
                log.bind(error=str(exc)).warning(
                    "Failed to update manifest.json in staging directory"
                )

    def eval_temp_t1(self, emf_1_mv: float) -> float:
        return float(
            evaluate_channel_temperature(
                emf_1_mv,
                sensor=self.sensor_t1,
                cjc=self.cjc_t1,
                calibration=self.calibration_t1,
            )
        )

    def start_recording(self) -> None:
        if self._staging_writer is not None:
            self._staging_writer.cleanup()
            self._staging_writer = None
        self.clear()
        self.recording_enabled = True
        self._staging_write_failed = False
        try:
            self._staging_writer = StagingDirWriter.create(
                recovery_root=self._recovery_root,
                manifest=self.build_manifest(),
                columns=self.column_order(),
                target_path=self.reserved_path,
            )
        except OSError as exc:
            log.opt(exception=True).bind(error=repr(exc)).error(
                "Failed to initialize staging directory in AppData"
            )
            self._staging_writer = None

    def stop_recording(self) -> None:
        self.recording_enabled = False
        if self._staging_writer is not None:
            self._staging_writer.close()

    def clear(self) -> None:
        self._t0 = None
        self.has_unsaved_data = False
        self.time_list.clear()
        self.emf_1_list.clear()
        self.emf_2_list.clear()
        self.temp_1_list.clear()
        self.dta_list.clear()
        self.heater_out_list.clear()

    def _compute_heating_rate_c_min(self, timestamp: float, temp_c: float) -> float:
        self._rate_window.append((timestamp, temp_c))
        if len(self._rate_window) < 2:
            return 0.0
        t_first, temp_first = self._rate_window[0]  # noqa: MI001, PU001
        dt_s = timestamp - t_first
        if dt_s < 0.5:
            return 0.0
        return ((temp_c - temp_first) / dt_s) * 60.0

    def append_sample(self, sample: LiveSample) -> EvaluatedPoint:
        """Обрабатывает живой отсчёт и возвращает типизированный EvaluatedPoint."""
        self.update_cjc(sample.cjc_temp_c)
        temp_1_c = self.eval_temp_t1(sample.emf_1_mv)
        dta_mv = sample.emf_1_mv - sample.emf_2_mv
        rate_c_min = self._compute_heating_rate_c_min(sample.timestamp, temp_1_c)

        if not self.recording_enabled:
            return EvaluatedPoint(
                rel_time_s=0.0,
                temp_1_c=temp_1_c,
                dta_mv=dta_mv,
                heating_rate_c_min=rate_c_min,
            )

        if self._t0 is None:
            self._t0 = sample.timestamp
        rel_t = max(0.0, round(sample.timestamp - self._t0, 4))

        self.has_unsaved_data = True
        self.time_list.append(rel_t)
        self.emf_1_list.append(sample.emf_1_mv)
        self.temp_1_list.append(temp_1_c)
        if self.mode == StandMode.VTA:
            self.heater_out_list.append(sample.heater_output_v)
            row: tuple[float, ...] = (
                rel_t,
                sample.emf_1_mv,
                temp_1_c,
                sample.heater_output_v,
            )
        else:
            self.emf_2_list.append(sample.emf_2_mv)
            self.dta_list.append(dta_mv)
            row = (
                rel_t,
                sample.emf_1_mv,
                sample.emf_2_mv,
                dta_mv,
                temp_1_c,
            )

        if self._staging_writer is not None and not self._staging_write_failed:
            try:
                self._staging_writer.append_row(row)
            except OSError as exc:
                self._staging_write_failed = True
                log.opt(exception=True).bind(error=repr(exc)).error(
                    "Failed to append row to staging data.csv"
                )

        return EvaluatedPoint(
            rel_time_s=rel_t,
            temp_1_c=temp_1_c,
            dta_mv=dta_mv,
            heating_rate_c_min=rate_c_min,
        )

    def build_channels(self) -> list[ChannelDescriptor]:
        if self.mode == StandMode.VTA:
            return [
                ChannelDescriptor(column=ChannelKey.TIME, label="Время", unit="s"),
                ChannelDescriptor(column=ChannelKey.EMF_1, label="ЭДС", unit="mV"),
                ChannelDescriptor(
                    column=ChannelKey.TEMPERATURE,
                    label="Температура",
                    unit="°C",
                    source_columns=[ChannelKey.EMF_1],
                    sensor=self.sensor_t1,
                    cjc=self.cjc_t1,
                    calibration=self.calibration_t1,
                ),
                ChannelDescriptor(
                    column=ChannelKey.HEATER_OUTPUT,
                    label="Выход нагревателя",
                    unit="V",
                ),
            ]
        return [
            ChannelDescriptor(column=ChannelKey.TIME, label="Время", unit="s"),
            ChannelDescriptor(
                column=ChannelKey.EMF_1,
                label="Термопара 1 (образец)",
                unit="mV",
            ),
            ChannelDescriptor(
                column=ChannelKey.EMF_2,
                label="Термопара 2 (эталон)",
                unit="mV",
                sensor=self.sensor_t2,
            ),
            ChannelDescriptor(
                column=ChannelKey.DTA,
                label="ДТА",
                unit="mV",
                source_columns=[ChannelKey.EMF_1, ChannelKey.EMF_2],
                metadata={"exo_up": True},
            ),
            ChannelDescriptor(
                column=ChannelKey.TEMPERATURE,
                label="Температура образца",
                unit="°C",
                source_columns=[ChannelKey.EMF_1],
                sensor=self.sensor_t1,
                cjc=self.cjc_t1,
                calibration=self.calibration_t1,
            ),
        ]

    def column_order(self) -> list[str]:
        return [ch.column for ch in self.build_channels()]

    def build_manifest(self) -> MeasurementManifest:
        return MeasurementManifest(
            software_version=VERSION,
            common_version=common_version,
            sample=self.sample,
            operator=self.operator,
            instrument=config.instrument,
            sample_mass_mg=self.sample_mass_mg,
            crucible=self.crucible,
            atmosphere=self.atmosphere,
            comment=self.comment,
            channels=self.build_channels(),
        )

    def to_record(self) -> MeasurementRecord:
        if not self.time_list:
            raise ValueError("Нет записанных точек для сохранения измерения")

        if self.mode == StandMode.VTA:
            data_map: dict[str, np.ndarray] = {
                ChannelKey.TIME: np.array(self.time_list, dtype=float),
                ChannelKey.EMF_1: np.array(self.emf_1_list, dtype=float),
                ChannelKey.TEMPERATURE: np.array(self.temp_1_list, dtype=float),
                ChannelKey.HEATER_OUTPUT: np.array(self.heater_out_list, dtype=float),
            }
        else:
            data_map = {
                ChannelKey.TIME: np.array(self.time_list, dtype=float),
                ChannelKey.EMF_1: np.array(self.emf_1_list, dtype=float),
                ChannelKey.EMF_2: np.array(self.emf_2_list, dtype=float),
                ChannelKey.DTA: np.array(self.dta_list, dtype=float),
                ChannelKey.TEMPERATURE: np.array(self.temp_1_list, dtype=float),
            }

        return MeasurementRecord(manifest=self.build_manifest(), data=data_map)

    def save(self, path: Path) -> None:
        target = path if path.suffix.lower() == ".fus" else path.with_suffix(".fus")
        if self._staging_writer is not None and not self._staging_write_failed:
            self._staging_writer.close()
            pack_staging_dir_to_fus(self._staging_writer.staging_dir, target)
        else:
            save_fus(self.to_record(), target)
        if self._staging_writer is not None:
            self._staging_writer.cleanup()
            self._staging_writer = None
        self.has_unsaved_data = False

    def reserve_file(self, path: Path) -> Path:
        """Предварительно создаёт файл .fus на диске и эксклюзивно блокирует его дескриптор."""
        self.release_unused_reservation()
        out = path if path.suffix.lower() == ".fus" else path.with_suffix(".fus")
        out.parent.mkdir(parents=True, exist_ok=True)
        fh = out.open("w+b")
        fh.write(b"\x00")
        fh.flush()
        if sys.platform == "win32":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        self.reserved_path = out
        self._locked_fh = fh
        return out

    def _unlock_and_close_handle(self) -> None:
        fh = self._locked_fh
        self._locked_fh = None
        if fh is None:
            return
        with contextlib.suppress(OSError):
            if sys.platform == "win32":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        with contextlib.suppress(OSError):
            fh.close()

    def finalize_locked_file(self) -> Path | None:
        """Превращает рабочую папку в заблокированный файл .fus, снимает блокировку и очищает staging."""
        fh = self._locked_fh
        out_path = self.reserved_path
        if fh is None or out_path is None:
            return None
        if sys.platform == "win32":
            import msvcrt

            with contextlib.suppress(OSError):
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        if self._staging_writer is not None and not self._staging_write_failed:
            self._staging_writer.close()
            pack_staging_dir_to_fus(self._staging_writer.staging_dir, fh)
        else:
            save_fus(self.to_record(), fh)
        with contextlib.suppress(OSError):
            os.fsync(fh.fileno())
        with contextlib.suppress(OSError):
            fh.close()
        self._locked_fh = None
        if self._staging_writer is not None:
            self._staging_writer.cleanup()
            self._staging_writer = None
        self.has_unsaved_data = False
        return out_path

    def discard_recording(self) -> None:
        """Отменяет незавершённую запись, удаляя рабочую папку в AppData и 1-байтовую заглушку .fus."""
        self.recording_enabled = False
        if self._staging_writer is not None:
            self._staging_writer.cleanup()
            self._staging_writer = None
        res_p = self.reserved_path
        self._unlock_and_close_handle()
        self.reserved_path = None
        if res_p is not None:
            with contextlib.suppress(OSError):
                if res_p.is_file() and res_p.stat().st_size <= 1:
                    res_p.unlink()
        self.clear()

    def release_unused_reservation(self) -> None:
        """Снимает блокировку и удаляет пустой зарезервированный файл и пустую рабочую папку."""
        had_lock = self._locked_fh is not None
        res_p = self.reserved_path
        self._unlock_and_close_handle()
        self.reserved_path = None
        if len(self.time_list) == 0 and self._staging_writer is not None:
            self._staging_writer.cleanup()
            self._staging_writer = None
        if (
            had_lock
            and not self.has_unsaved_data
            and len(self.time_list) == 0
            and res_p is not None
            and res_p.exists()
        ):
            with contextlib.suppress(OSError):
                res_p.unlink()
