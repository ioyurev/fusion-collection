from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

from loguru import logger as log
from PySide6 import QtCore

from fusion_collection.config import StandMode, config
from fusion_collection.hardware import HardwareManager, is_thermocouple_open

POLL_INTERVAL_SEC = 0.1


@dataclass(frozen=True)
class LiveSample:
    """Один живой отсчёт мониторинга (ВТА или ДТА)."""

    timestamp: float
    mode: StandMode
    emf_1_mv: float
    emf_2_mv: float = 0.0
    heater_output_v: float = 0.0
    cjc_temp_c: float = 25.0
    sampling_rate_hz: float = 10.0
    open_thermocouple_warning: bool = False


class HeaterRamp:
    """Чистая логика линейной развёртки напряжения нагревателя ВТА (мВ/с)."""

    def __init__(self, speed_mv_per_sec: int = 5) -> None:
        self.output_v: float = 0.0
        self.last_time: float | None = None
        self.enabled: bool = False
        self.speed_v_per_sec: float = speed_mv_per_sec / 1000.0

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.last_time = None

    def set_speed(self, speed_mv_per_sec: int) -> None:
        self.speed_v_per_sec = speed_mv_per_sec / 1000.0

    def step(self, now_monotonic: float) -> float:
        if not self.enabled:
            return self.output_v
        if self.last_time is None:
            self.last_time = now_monotonic
            return self.output_v
        dt = max(0.0, now_monotonic - self.last_time)
        self.output_v = max(0.0, min(10.0, self.output_v + self.speed_v_per_sec * dt))
        self.last_time = now_monotonic
        return self.output_v

    def reset(self) -> None:
        self.output_v = 0.0
        self.last_time = None


class AcquisitionLoop(QtCore.QThread):
    """Поток непрерывного опроса модулей в реальном времени (работает и вне записи измерения)."""

    sample_ready = QtCore.Signal(object)
    error_occurred = QtCore.Signal(str)

    def __init__(
        self,
        hardware: HardwareManager,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.hardware = hardware
        self.heater = HeaterRamp(speed_mv_per_sec=config.default_speed)
        self._running = False
        self._intervals: deque[float] = deque(maxlen=25)
        self._last_ts: float | None = None
        self._cjc_temp_c: float = 25.0
        self._tick_counter: int = 0

    def start_monitoring(self) -> None:
        if not self.isRunning():
            self._running = True
            self.start()

    def stop_monitoring(self) -> None:
        self._running = False
        self.heater.set_enabled(False)
        self.heater.reset()
        if self.isRunning():
            self.quit()
            self.wait(2000)
        if (
            not config.is_test_mode
            and self.hardware.connected
            and config.mode is StandMode.VTA
        ):
            try:
                self.hardware.adam4021.set_output(0.0)
            except Exception as exc:  # noqa: BLE001
                log.bind(error=str(exc)).warning("Failed to zero ADAM-4021 on stop")

    def _update_rate(self, now_ts: float) -> float:
        if self._last_ts is not None:
            dt = now_ts - self._last_ts
            if dt > 1e-6:
                self._intervals.append(dt)
        self._last_ts = now_ts
        if not self._intervals:
            return 10.0
        avg_dt = sum(self._intervals) / len(self._intervals)
        return 1.0 / avg_dt if avg_dt > 1e-6 else 10.0

    def _poll_once(self) -> LiveSample:
        now_ts = time.monotonic()
        rate_hz = self._update_rate(now_ts)
        mode = config.mode

        if config.is_test_mode:
            time.sleep(POLL_INTERVAL_SEC)
            sim_e1 = 5.0 + 2.0 * math.sin(now_ts * 0.5)
            sim_e2 = 5.0 + 1.8 * math.sin(now_ts * 0.5)
            out_v = self.heater.step(now_ts) if mode is StandMode.VTA else 0.0
            return LiveSample(
                timestamp=now_ts,
                mode=mode,
                emf_1_mv=round(sim_e1, 4),
                emf_2_mv=round(sim_e2, 4),
                heater_output_v=round(out_v, 3),
                cjc_temp_c=25.0,
                sampling_rate_hz=rate_hz,
                open_thermocouple_warning=False,
            )

        if self._tick_counter % 50 == 0:
            try:
                self._cjc_temp_c = self.hardware.adam4011_t1.read_cjc_temperature()
            except Exception as exc:  # noqa: BLE001
                log.bind(error=str(exc)).debug("CJC poll skipped")
        self._tick_counter += 1

        if mode is StandMode.VTA:
            emf_1 = self.hardware.adam4011_t1.read_data()
            out_v = self.heater.step(now_ts)
            self.hardware.adam4021.set_output(out_v)
            open_warn = is_thermocouple_open(emf_1)
            if open_warn:
                log.bind(emf_mv=emf_1).warning(
                    "Open thermocouple detected in VTA mode (heating NOT interrupted)"
                )
            return LiveSample(
                timestamp=now_ts,
                mode=StandMode.VTA,
                emf_1_mv=emf_1,
                heater_output_v=round(out_v, 3),
                cjc_temp_c=self._cjc_temp_c,
                sampling_rate_hz=rate_hz,
                open_thermocouple_warning=open_warn,
            )

        self.hardware.bus.trigger_synchronized_sampling()
        emf_1 = self.hardware.adam4011_t1.read_sync_data()
        emf_2 = self.hardware.adam4011_t2.read_sync_data()
        open_warn = is_thermocouple_open(emf_1) or is_thermocouple_open(emf_2)
        if open_warn:
            log.bind(emf_1=emf_1, emf_2=emf_2).warning(
                "Open thermocouple detected in DTA mode"
            )
        return LiveSample(
            timestamp=now_ts,
            mode=StandMode.DTA,
            emf_1_mv=emf_1,
            emf_2_mv=emf_2,
            cjc_temp_c=self._cjc_temp_c,
            sampling_rate_hz=rate_hz,
            open_thermocouple_warning=open_warn,
        )

    def run(self) -> None:
        while self._running:
            try:
                sample = self._poll_once()
                self.sample_ready.emit(sample)
            except Exception as exc:  # noqa: BLE001
                log.bind(error=str(exc)).error("Acquisition loop read error")
                self.error_occurred.emit(str(exc))
                time.sleep(0.5)
