from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Final

import serial
import serial.serialwin32
import serial.tools.list_ports
from loguru import logger as log

from fusion_collection.adam_config import Adam4011Config, Adam4021Config
from fusion_collection.config import config

# Обход ошибки Win32 SetCommState у драйверов WCH CH340 под Windows
_orig_reconfigure = getattr(serial.serialwin32.Serial, "_reconfigure_port", None)

if _orig_reconfigure is not None:

    def _safe_reconfigure_port(self: serial.Serial) -> None:
        try:
            _orig_reconfigure(self)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            log.bind(error=str(exc)).warning("CH340 SetCommState warning bypassed")

    serial.serialwin32.Serial._reconfigure_port = _safe_reconfigure_port  # type: ignore[attr-defined]

# CRITICAL HARDWARE SAFETY INVARIANT:
# При подаче строгого 0.000 В с ADAM-4021 на управляющий вход силового блока печи
# вход работает как короткое замыкание и выбивает вводные автоматы.
# Смещение +0.001 В является обязательным аппаратным ограничением безопасности!
SAFE_ZERO_OFFSET_V: Final[float] = 0.001

# Порог детектирования обрыва термопары в диапазоне ±50 mV (насыщение 16-бит АЦП = 65.521 мВ)
OPEN_THERMOCOUPLE_THRESHOLD_MV: Final[float] = 65.5
DISCOVERY_TIMEOUT_SEC: Final[float] = 0.15


def get_serial_ports() -> list[str]:
    return [port.device for port in serial.tools.list_ports.comports()]


def is_thermocouple_open(emf_mv: float) -> bool:
    return abs(emf_mv) >= OPEN_THERMOCOUPLE_THRESHOLD_MV


@dataclass(frozen=True)
class SyncSample:
    """Результат разбора синхронного чтения ADAM-4011 ($AA4)."""

    value_mv: float
    is_fresh: bool


@dataclass(frozen=True)
class ModuleConfigMismatch:
    module_label: str
    address: int
    current_summary: str
    expected_summary: str
    issues: list[str]
    reconfigure_cmd: bytes
    wait_seconds: float


class Adam4520Bus:
    """Транспортный уровень шины RS-485 через преобразователь ADAM-4520 (9600, 8, N, 1)."""

    endchar: bytes = b"\r"

    def __init__(
        self,
        baudrate: int = 9600,
        timeout: float = DISCOVERY_TIMEOUT_SEC,
    ) -> None:
        self._lock = threading.RLock()
        self.ser = serial.Serial(
            baudrate=baudrate,
            timeout=timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=False,
            dsrdtr=False,
        )

    @property
    def is_open(self) -> bool:
        with self._lock:
            return bool(self.ser.is_open)

    def open(self, port: str) -> None:
        with self._lock:
            if self.ser.is_open and self.ser.port != port:
                self.ser.close()
            if not self.ser.is_open:
                self.ser.port = port
                self.ser.open()
                log.bind(port=port).info("Opened RS-485 serial port")

    def close(self) -> None:
        with self._lock:
            if self.ser.is_open:
                port_name = self.ser.port
                self.ser.close()
                log.bind(port=port_name).info("Closed RS-485 serial port")

    def write_only(self, cmd: bytes) -> None:
        with self._lock:
            self.ser.reset_input_buffer()
            self.ser.write(cmd + self.endchar)

    def query_bytes(self, cmd: bytes) -> bytes:
        with self._lock:
            self.write_only(cmd)
            return bytes(self.ser.read_until(expected=self.endchar))

    def query_str(self, cmd: bytes) -> str:
        return self.query_bytes(cmd).decode("ascii", errors="replace").strip()

    def trigger_synchronized_sampling(self) -> None:
        """Отправляет широковещательную команду синхронной выборки #** всем модулям ADAM-4011."""
        self.write_only(b"#**")


class Adam4011Module:
    """Драйвер модуля ввода термопары ADAM-4011 / ADAM-4011D."""

    model_code = "4011"

    def __init__(self, bus: Adam4520Bus, address: int = 1) -> None:
        self.bus = bus
        self.address = address
        self.addr_bytes = f"{address:02X}".encode("ascii")
        self.name = ""
        self.firmware = ""
        self.module_config: Adam4011Config | None = None

    def check_identity(self) -> bool:
        resp = self.bus.query_str(b"$" + self.addr_bytes + b"M")
        expected_prefix = f"!{self.address:02X}"
        if resp.startswith(expected_prefix) and self.model_code in resp:
            self.name = resp
            fw_resp = self.bus.query_str(b"$" + self.addr_bytes + b"F")
            if fw_resp.startswith(expected_prefix):
                self.firmware = fw_resp[3:]
            return True
        return False

    def read_config(self) -> Adam4011Config:
        resp = self.bus.query_str(b"$" + self.addr_bytes + b"2")
        if not resp.startswith(f"!{self.address:02X}") or len(resp) < 9:
            raise ValueError(
                f"Некорректный ответ $AA2 от ADAM-4011 ({self.address:02X}h): {resp!r}"
            )
        self.module_config = Adam4011Config.from_str(resp)
        return self.module_config

    def read_cjc_temperature(self) -> float:
        resp = self.bus.query_str(b"$" + self.addr_bytes + b"3")
        if resp.startswith(">") and len(resp) >= 8:
            return float(resp[1:8].strip())
        raise ValueError(f"Некорректный ответ CJC ($AA3) от ADAM-4011: {resp!r}")

    def read_data(self) -> float:
        resp = self.bus.query_str(b"#" + self.addr_bytes)
        if not resp.startswith(">"):
            raise ValueError(f"Некорректный ответ #AA от ADAM-4011: {resp!r}")
        return float(resp[1:].strip())

    @staticmethod
    def parse_sync_response(raw: bytes | str) -> SyncSample:
        """Разбирает ответ $AA4 (>AA(status)(data) или !AA(status)(data))."""
        text = (
            raw.decode("ascii", errors="replace").strip()
            if isinstance(raw, bytes)
            else raw.strip()
        )
        if len(text) < 5 or text[:1] not in (">", "!"):
            raise ValueError(f"Некорректный ответ синхронного чтения ($AA4): {text!r}")
        status_char = text[3:4]
        is_fresh = status_char == "1"
        value = float(text[4:].strip())
        return SyncSample(value_mv=value, is_fresh=is_fresh)

    def read_sync_data(self) -> float:
        resp = self.bus.query_str(b"$" + self.addr_bytes + b"4")
        parsed = self.parse_sync_response(resp)
        if not parsed.is_fresh:
            log.bind(address=self.address).warning(
                "ADAM-4011 returned stale synchronized sample (status=0)"
            )
        return parsed.value_mv


class Adam4021Module:
    """Драйвер модуля ЦАП ADAM-4021 для управления нагревом печи ВТА."""

    model_code = "4021"

    def __init__(self, bus: Adam4520Bus, address: int = 3) -> None:
        self.bus = bus
        self.address = address
        self.addr_bytes = f"{address:02X}".encode("ascii")
        self.name = ""
        self.module_config: Adam4021Config | None = None

    def check_identity(self) -> bool:
        resp = self.bus.query_str(b"$" + self.addr_bytes + b"M")
        expected_prefix = f"!{self.address:02X}"
        if resp.startswith(expected_prefix) and self.model_code in resp:
            self.name = resp
            return True
        return False

    def read_config(self) -> Adam4021Config:
        resp = self.bus.query_str(b"$" + self.addr_bytes + b"2")
        if not resp.startswith(f"!{self.address:02X}") or len(resp) < 9:
            raise ValueError(
                f"Некорректный ответ $AA2 от ADAM-4021 ({self.address:02X}h): {resp!r}"
            )
        self.module_config = Adam4021Config.from_str(resp)
        return self.module_config

    @staticmethod
    def format_output_command(address: int, value_v: float) -> bytes:
        clamped = max(0.0, min(10.0, float(value_v)))
        # CRITICAL HARDWARE SAFETY INVARIANT: +0.001 V offset prevents 0.0 V short-circuit!
        safe_val = min(10.0, clamped + SAFE_ZERO_OFFSET_V)
        return f"#{address:02X}{safe_val:06.3f}".encode("ascii")

    def set_output(self, value_v: float) -> bytes:
        cmd = self.format_output_command(self.address, value_v)
        return self.bus.query_bytes(cmd)


class HardwareManager:
    """Координатор обнаружения модулей ADAM, автопоиска COM-порта и проверки конфигурации."""

    def __init__(self) -> None:
        self.bus = Adam4520Bus(baudrate=config.adam_baudrate)
        self.adam4011_t1 = Adam4011Module(self.bus, address=config.adam4011_t1_address)
        self.adam4011_t2 = Adam4011Module(self.bus, address=config.adam4011_t2_address)
        self.adam4021 = Adam4021Module(self.bus, address=config.adam4021_address)
        self.connected = False

    def sync_addresses_from_config(self) -> None:
        self.adam4011_t1 = Adam4011Module(self.bus, address=config.adam4011_t1_address)
        self.adam4011_t2 = Adam4011Module(self.bus, address=config.adam4011_t2_address)
        self.adam4021 = Adam4021Module(self.bus, address=config.adam4021_address)

    def _probe_port(self, port: str, mode: str) -> bool:
        try:
            self.bus.open(port)
            if mode == "vta":
                ok = (
                    self.adam4011_t1.check_identity() and self.adam4021.check_identity()
                )
            else:
                ok = (
                    self.adam4011_t1.check_identity()
                    and self.adam4011_t2.check_identity()
                )
            if not ok:
                self.bus.close()
            return ok
        except (serial.SerialException, OSError):
            self.bus.close()
            return False

    def connect_and_discover(self, mode: str | None = None) -> bool:
        active_mode = mode or config.mode
        self.sync_addresses_from_config()
        if config.is_test_mode:
            self.connected = True
            return True

        available_ports = get_serial_ports()
        candidates: list[str] = []
        if config.comport in available_ports:
            candidates.append(config.comport)
        for p in available_ports:
            if p not in candidates:
                candidates.append(p)

        for candidate_port in candidates:
            if self._probe_port(candidate_port, active_mode):
                if candidate_port != config.comport:
                    config.comport = candidate_port
                    config.update()
                self.connected = True
                return True

        self.connected = False
        return False

    def inspect_configurations(
        self, mode: str | None = None
    ) -> list[ModuleConfigMismatch]:
        """Считывает конфигурацию модулей ($AA2) и возвращает список несоответствий без их перезаписи."""
        active_mode = mode or config.mode
        if config.is_test_mode or not self.connected:
            return []

        mismatches: list[ModuleConfigMismatch] = []
        cfg_t1 = self.adam4011_t1.read_config()
        issues_t1 = cfg_t1.check_requirements()
        if issues_t1:
            exp_t1 = Adam4011Config.expected(self.adam4011_t1.address)
            mismatches.append(
                ModuleConfigMismatch(
                    module_label=f"ADAM-4011 (Канал 1, адрес {self.adam4011_t1.address:02X}h)",
                    address=self.adam4011_t1.address,
                    current_summary=cfg_t1.format_summary(),
                    expected_summary=exp_t1.format_summary(),
                    issues=issues_t1,
                    reconfigure_cmd=exp_t1.to_set_cmd(),
                    wait_seconds=7.0,
                )
            )

        if active_mode == "vta":
            cfg_ao = self.adam4021.read_config()
            issues_ao = cfg_ao.check_requirements()
            if issues_ao:
                exp_ao = Adam4021Config.expected(self.adam4021.address)
                mismatches.append(
                    ModuleConfigMismatch(
                        module_label=f"ADAM-4021 (ЦАП печи, адрес {self.adam4021.address:02X}h)",
                        address=self.adam4021.address,
                        current_summary=cfg_ao.format_summary(),
                        expected_summary=exp_ao.format_summary(),
                        issues=issues_ao,
                        reconfigure_cmd=exp_ao.to_set_cmd(),
                        wait_seconds=0.05,
                    )
                )
            self.adam4021.set_output(0.0)
        else:
            cfg_t2 = self.adam4011_t2.read_config()
            issues_t2 = cfg_t2.check_requirements()
            if issues_t2:
                exp_t2 = Adam4011Config.expected(self.adam4011_t2.address)
                mismatches.append(
                    ModuleConfigMismatch(
                        module_label=f"ADAM-4011 (Канал 2, адрес {self.adam4011_t2.address:02X}h)",
                        address=self.adam4011_t2.address,
                        current_summary=cfg_t2.format_summary(),
                        expected_summary=exp_t2.format_summary(),
                        issues=issues_t2,
                        reconfigure_cmd=exp_t2.to_set_cmd(),
                        wait_seconds=7.0,
                    )
                )

        return mismatches

    def apply_reconfiguration(self, mismatches: list[ModuleConfigMismatch]) -> None:
        """Применяет требуемую конфигурацию (%AANNTTCCFF) только после подтверждения пользователем."""
        for item in mismatches:
            resp = self.bus.query_str(item.reconfigure_cmd)
            log.bind(module=item.module_label, response=resp).info(
                "Applied ADAM module reconfiguration"
            )
            time.sleep(item.wait_seconds)
