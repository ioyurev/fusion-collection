from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InputRangeCode(StrEnum):
    MV_15 = "00"
    MV_50 = "01"
    MV_100 = "02"
    MV_500 = "03"
    V_1 = "04"
    V_2_5 = "05"
    MA_20 = "06"
    MA_4_20 = "07"
    TC_J = "0E"
    TC_K = "0F"
    TC_T = "10"
    TC_E = "11"
    TC_R = "12"
    TC_S = "13"
    TC_B = "14"

    def description(self) -> str:
        return INPUT_RANGE_DESCRIPTIONS[self]


INPUT_RANGE_DESCRIPTIONS: dict[InputRangeCode, str] = {
    InputRangeCode.MV_15: "±15 mV",
    InputRangeCode.MV_50: "±50 mV",
    InputRangeCode.MV_100: "±100 mV",
    InputRangeCode.MV_500: "±500 mV",
    InputRangeCode.V_1: "±1 V",
    InputRangeCode.V_2_5: "±2.5 V",
    InputRangeCode.MA_20: "±20 mA",
    InputRangeCode.MA_4_20: "4~20 mA",
    InputRangeCode.TC_J: "Type J Thermocouple (0..760 °C)",
    InputRangeCode.TC_K: "Type K Thermocouple (0..1370 °C)",
    InputRangeCode.TC_T: "Type T Thermocouple (-100..400 °C)",
    InputRangeCode.TC_E: "Type E Thermocouple (0..1000 °C)",
    InputRangeCode.TC_R: "Type R Thermocouple (500..1750 °C)",
    InputRangeCode.TC_S: "Type S Thermocouple (500..1750 °C)",
    InputRangeCode.TC_B: "Type B Thermocouple (500..1800 °C)",
}


class OutputRangeCode(StrEnum):
    MA_0_20 = "30"
    MA_4_20 = "31"
    V_0_10 = "32"

    def description(self) -> str:
        return OUTPUT_RANGE_DESCRIPTIONS[self]


OUTPUT_RANGE_DESCRIPTIONS: dict[OutputRangeCode, str] = {
    OutputRangeCode.MA_0_20: "0 to 20 mA",
    OutputRangeCode.MA_4_20: "4 to 20 mA",
    OutputRangeCode.V_0_10: "0 to 10 V",
}


class BaudrateCode(StrEnum):
    B1200 = "03"
    B2400 = "04"
    B4800 = "05"
    B9600 = "06"
    B19200 = "07"
    B38400 = "08"

    def bps(self) -> int:
        return BAUDRATE_BPS[self]


BAUDRATE_BPS: dict[BaudrateCode, int] = {
    BaudrateCode.B1200: 1200,
    BaudrateCode.B2400: 2400,
    BaudrateCode.B4800: 4800,
    BaudrateCode.B9600: 9600,
    BaudrateCode.B19200: 19200,
    BaudrateCode.B38400: 38400,
}


class IntegrationTimeCode(StrEnum):
    MS_50_60HZ = "0"
    MS_60_50HZ = "1"

    def description(self) -> str:
        return (
            "50 ms (сеть 60 Hz)"
            if self is IntegrationTimeCode.MS_50_60HZ
            else "60 ms (сеть 50 Hz)"
        )


class ChecksumCode(StrEnum):
    DISABLED = "0"
    ENABLED = "1"

    def description(self) -> str:
        return "Disabled" if self is ChecksumCode.DISABLED else "Enabled"


class DataFormatCode(StrEnum):
    ENGINEERING_UNITS = "00"
    PERCENT_FSR = "01"
    TWOS_COMPLEMENT_HEX = "10"
    OHMS = "11"

    def description(self) -> str:
        return DATA_FORMAT_DESCRIPTIONS[self]


DATA_FORMAT_DESCRIPTIONS: dict[DataFormatCode, str] = {
    DataFormatCode.ENGINEERING_UNITS: "Engineering units (инженерные единицы)",
    DataFormatCode.PERCENT_FSR: "% of FSR (проценты шкалы)",
    DataFormatCode.TWOS_COMPLEMENT_HEX: "Two's complement hex",
    DataFormatCode.OHMS: "Ohms (Омы)",
}


class SlewRateCode(StrEnum):
    IMMEDIATE = "0000"
    SR_00625 = "0001"
    SR_0125 = "0010"
    SR_025 = "0011"
    SR_05 = "0100"
    SR_1 = "0101"
    SR_2 = "0110"
    SR_4 = "0111"
    SR_8 = "1000"
    SR_16 = "1001"
    SR_32 = "1010"
    SR_64 = "1011"


@dataclass(frozen=True)
class Adam4011Config:
    """Распарсенная конфигурация модуля ADAM-4011 ($AA2 / %AANNTTCCFF)."""

    address: str
    new_address: str
    input_range: InputRangeCode
    baudrate: BaudrateCode
    integration_time: IntegrationTimeCode
    checksum: ChecksumCode
    data_format: DataFormatCode

    @classmethod
    def expected(cls, address: int) -> Adam4011Config:
        addr_hex = f"{address:02X}"
        return cls(
            address=addr_hex,
            new_address=addr_hex,
            input_range=InputRangeCode.MV_50,
            baudrate=BaudrateCode.B9600,
            integration_time=IntegrationTimeCode.MS_60_50HZ,
            checksum=ChecksumCode.DISABLED,
            data_format=DataFormatCode.ENGINEERING_UNITS,
        )

    @classmethod
    def from_str(cls, response: str) -> Adam4011Config:
        clean = response.strip()
        is_set = clean.startswith("%")
        body = clean[1:]
        pairs = [body[i : i + 2] for i in range(0, len(body), 2)]
        if is_set:
            addr_s, new_addr_s, tt_s, cc_s, ff_s, *_ = pairs
        else:
            addr_s, tt_s, cc_s, ff_s, *_ = pairs
            new_addr_s = addr_s

        ff_val = int(ff_s, 16)
        int_bit = "1" if (ff_val & 0b1000_0000) else "0"
        chk_bit = "1" if (ff_val & 0b0100_0000) else "0"
        df_bits = f"{ff_val & 0b0000_0011:02b}"

        return cls(
            address=f"{int(addr_s, 16):02X}",
            new_address=f"{int(new_addr_s, 16):02X}",
            input_range=InputRangeCode(tt_s.upper()),
            baudrate=BaudrateCode(cc_s.upper()),
            integration_time=IntegrationTimeCode(int_bit),
            checksum=ChecksumCode(chk_bit),
            data_format=DataFormatCode(df_bits),
        )

    def to_set_cmd(self) -> bytes:
        ff_val = int(self.data_format.value, 2)
        if self.checksum is ChecksumCode.ENABLED:
            ff_val |= 0b0100_0000
        if self.integration_time is IntegrationTimeCode.MS_60_50HZ:
            ff_val |= 0b1000_0000
        cmd = (
            f"%{self.address}{self.new_address}"
            f"{self.input_range.value}{self.baudrate.value}{ff_val:02X}"
        )
        return cmd.encode("ascii")

    def check_requirements(self) -> list[str]:
        issues: list[str] = []
        if self.input_range not in (InputRangeCode.MV_50, InputRangeCode.MV_100):
            issues.append(
                f"Входной диапазон: {self.input_range.value} ({self.input_range.description()}), "
                f"ожидается 01 (±50 mV)"
            )
        if self.data_format is not DataFormatCode.ENGINEERING_UNITS:
            issues.append(
                f"Формат данных: {self.data_format.value} ({self.data_format.description()}), "
                f"ожидается 00 (Engineering units)"
            )
        if self.integration_time is not IntegrationTimeCode.MS_60_50HZ:
            issues.append(
                f"Время интегрирования: {self.integration_time.description()}, "
                f"ожидается 60 ms (сеть 50 Hz)"
            )
        if self.checksum is not ChecksumCode.DISABLED:
            issues.append("Контрольная сумма включена, ожидается Disabled (0)")
        return issues

    def format_summary(self) -> str:
        return (
            f"Модуль ADAM-4011 (адрес {self.address}h):\n"
            f"  • Диапазон входа (TT): {self.input_range.value} — {self.input_range.description()}\n"
            f"  • Скорость (CC): {self.baudrate.value} — {self.baudrate.bps()} бод\n"
            f"  • Время интегрирования: {self.integration_time.description()}\n"
            f"  • Формат данных: {self.data_format.value} — {self.data_format.description()}\n"
            f"  • Контрольная сумма: {self.checksum.description()}"
        )


@dataclass(frozen=True)
class Adam4021Config:
    """Распарсенная конфигурация модуля ЦАП ADAM-4021 ($AA2 / %AANNTTCCFF)."""

    address: str
    new_address: str
    output_range: OutputRangeCode
    baudrate: BaudrateCode
    slew_rate: SlewRateCode
    checksum: ChecksumCode
    data_format: DataFormatCode

    @classmethod
    def expected(cls, address: int) -> Adam4021Config:
        addr_hex = f"{address:02X}"
        return cls(
            address=addr_hex,
            new_address=addr_hex,
            output_range=OutputRangeCode.V_0_10,
            baudrate=BaudrateCode.B9600,
            slew_rate=SlewRateCode.IMMEDIATE,
            checksum=ChecksumCode.DISABLED,
            data_format=DataFormatCode.ENGINEERING_UNITS,
        )

    @classmethod
    def from_str(cls, response: str) -> Adam4021Config:
        clean = response.strip()
        is_set = clean.startswith("%")
        body = clean[1:]
        pairs = [body[i : i + 2] for i in range(0, len(body), 2)]
        if is_set:
            addr_s, new_addr_s, tt_s, cc_s, ff_s, *_ = pairs
        else:
            addr_s, tt_s, cc_s, ff_s, *_ = pairs
            new_addr_s = addr_s

        ff_val = int(ff_s, 16)
        chk_bit = "1" if (ff_val & 0b0100_0000) else "0"
        sr_bits = f"{(ff_val >> 2) & 0b0000_1111:04b}"
        df_bits = f"{ff_val & 0b0000_0011:02b}"

        return cls(
            address=f"{int(addr_s, 16):02X}",
            new_address=f"{int(new_addr_s, 16):02X}",
            output_range=OutputRangeCode(tt_s.upper()),
            baudrate=BaudrateCode(cc_s.upper()),
            slew_rate=SlewRateCode(sr_bits),
            checksum=ChecksumCode(chk_bit),
            data_format=DataFormatCode(df_bits),
        )

    def to_set_cmd(self) -> bytes:
        ff_val = int(self.data_format.value, 2) | (int(self.slew_rate.value, 2) << 2)
        if self.checksum is ChecksumCode.ENABLED:
            ff_val |= 0b0100_0000
        cmd = (
            f"%{self.address}{self.new_address}"
            f"{self.output_range.value}{self.baudrate.value}{ff_val:02X}"
        )
        return cmd.encode("ascii")

    def check_requirements(self) -> list[str]:
        issues: list[str] = []
        if self.output_range is not OutputRangeCode.V_0_10:
            issues.append(
                f"Выходной диапазон: {self.output_range.value} ({self.output_range.description()}), "
                f"ожидается 32 (0 to 10 V)"
            )
        if self.data_format is not DataFormatCode.ENGINEERING_UNITS:
            issues.append(
                f"Формат данных: {self.data_format.value} ({self.data_format.description()}), "
                f"ожидается 00 (Engineering units)"
            )
        if self.checksum is not ChecksumCode.DISABLED:
            issues.append("Контрольная сумма включена, ожидается Disabled (0)")
        return issues

    def format_summary(self) -> str:
        return (
            f"Модуль ADAM-4021 (адрес {self.address}h):\n"
            f"  • Диапазон выхода (TT): {self.output_range.value} — {self.output_range.description()}\n"
            f"  • Скорость (CC): {self.baudrate.value} — {self.baudrate.bps()} бод\n"
            f"  • Slew rate: {self.slew_rate.value}\n"
            f"  • Формат данных: {self.data_format.value} — {self.data_format.description()}\n"
            f"  • Контрольная сумма: {self.checksum.description()}"
        )
