from __future__ import annotations

from pathlib import Path

import pytest
from fusion_collection.acquisition import HeaterRamp, LiveSample
from fusion_collection.adam_config import Adam4011Config, Adam4021Config
from fusion_collection.config import StandMode
from fusion_collection.hardware import (
    SAFE_ZERO_OFFSET_V,
    Adam4011Module,
    Adam4021Module,
    is_thermocouple_open,
)
from fusion_collection.session import MeasurementSession
from fusion_common import (
    load_fus,
    make_vr_thermocouple,
    make_xa_thermocouple,
)


def test_adam4011_config_validation() -> None:
    valid_cfg = Adam4011Config.from_str("!01010680")
    assert valid_cfg.check_requirements() == []

    bad_cfg = Adam4011Config.from_str("!010F0601")
    issues = bad_cfg.check_requirements()
    assert len(issues) == 3
    assert "Модуль ADAM-4011" in bad_cfg.format_summary()


def test_adam4021_config_and_safe_zero_offset() -> None:
    valid_ao = Adam4021Config.from_str("!03320600")
    assert valid_ao.check_requirements() == []

    # CRITICAL HARDWARE INVARIANT TEST: 0.0 V must output +0.001 V (#0300.001)
    assert SAFE_ZERO_OFFSET_V == pytest.approx(0.001)
    cmd_zero = Adam4021Module.format_output_command(3, 0.0)
    assert cmd_zero == b"#0300.001"


def test_adam4011_sync_response_parser_preserves_sign() -> None:
    pos = Adam4011Module.parse_sync_response(b">011+12.345\r")
    assert pos.is_fresh is True
    assert pos.value_mv == pytest.approx(12.345)

    neg = Adam4011Module.parse_sync_response(b">020-00.456\r")
    assert neg.is_fresh is False
    assert neg.value_mv == pytest.approx(-0.456)


def test_open_thermocouple_detection_and_heater_ramp() -> None:
    assert is_thermocouple_open(65.521) is True
    assert is_thermocouple_open(15.0) is False

    ramp = HeaterRamp(speed_mv_per_sec=10)
    ramp.set_enabled(True)
    assert ramp.step(100.0) == pytest.approx(0.0)
    assert ramp.step(102.0) == pytest.approx(0.020)
    ramp.reset()
    assert ramp.output_v == 0.0


def test_vta_and_dta_sessions_save_to_fus(tmp_path: Path) -> None:
    vta_sess = MeasurementSession(
        mode=StandMode.VTA,
        sample="SmS",
        operator="Tester",
        sensor_t1=make_vr_thermocouple(),
    )
    vta_sess.start_recording()
    vta_sess.append_sample(
        LiveSample(
            timestamp=10.0, mode=StandMode.VTA, emf_1_mv=2.0, heater_output_v=0.5
        )
    )
    vta_sess.append_sample(
        LiveSample(
            timestamp=11.0, mode=StandMode.VTA, emf_1_mv=2.5, heater_output_v=0.6
        )
    )
    vta_sess.stop_recording()

    vta_file = tmp_path / "vta_run.fus"
    reserved = vta_sess.reserve_file(vta_file)
    assert reserved.exists()
    finalized = vta_sess.finalize_locked_file()
    assert finalized == vta_file
    loaded_vta = load_fus(vta_file)
    assert loaded_vta.manifest.sample == "SmS"
    assert loaded_vta.manifest.instrument == ""
    assert loaded_vta.get_channel("heater_output") is not None
    assert loaded_vta.get_channel("temperature") is not None

    dta_sess = MeasurementSession(
        mode=StandMode.DTA,
        sample="Gd2S3",
        operator="Tester",
        sensor_t1=make_xa_thermocouple(),
        sensor_t2=make_xa_thermocouple(),
    )
    dta_sess.start_recording()
    dta_sess.append_sample(
        LiveSample(timestamp=20.0, mode=StandMode.DTA, emf_1_mv=10.0, emf_2_mv=9.8)
    )
    dta_sess.append_sample(
        LiveSample(timestamp=21.0, mode=StandMode.DTA, emf_1_mv=10.5, emf_2_mv=10.1)
    )
    dta_sess.stop_recording()

    dta_file = tmp_path / "dta_run.fus"
    dta_sess.save(dta_file)
    loaded_dta = load_fus(dta_file)
    assert loaded_dta.manifest.sample == "Gd2S3"
    dta_desc = loaded_dta.get_descriptor("dta")
    assert dta_desc is not None
    assert dta_desc.metadata.get("exo_up") is True


def test_main_window_mode_switch_does_not_duplicate_menus() -> None:
    import sys

    from fusion_collection.config import config
    from fusion_collection.main_window import MainWindow
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication(sys.argv)
    prev_test_mode = config.is_test_mode
    prev_mode = config.mode
    config.is_test_mode = True
    try:
        config.mode = StandMode.VTA
        win = MainWindow()
        try:
            assert [a.text() for a in win.menuBar().actions()] == [
                "Файл",
                "Настройки",
                "Справка",
            ]
            assert win.session.sensor_t1 is not None
            assert win.session.sensor_t2 is not None
            assert win.lbl_tc1.text() == win.session.sensor_t1.display_short_name
            config.mode = StandMode.DTA
            win._build_ui()
            assert win.lbl_tc1.text() == win.session.sensor_t1.display_short_name
            assert win.lbl_tc2.text() == win.session.sensor_t2.display_short_name
            config.mode = StandMode.VTA
            win._build_ui()
            assert [a.text() for a in win.menuBar().actions()] == [
                "Файл",
                "Настройки",
                "Справка",
            ]
        finally:
            win.acq_loop.stop_monitoring()
            win.close()
    finally:
        config.is_test_mode = prev_test_mode
        config.mode = prev_mode
