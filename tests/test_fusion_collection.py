from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fusion_common import (
    load_fus,
    make_vr_thermocouple,
    make_xa_thermocouple,
)
from loguru import logger as log

from fusion_collection.acquisition import AcquisitionLoop, HeaterRamp, LiveSample
from fusion_collection.adam_config import Adam4011Config, Adam4021Config
from fusion_collection.config import StandMode
from fusion_collection.hardware import (
    SAFE_ZERO_OFFSET_V,
    Adam4011Module,
    Adam4021Module,
    HardwareManager,
    is_thermocouple_open,
)
from fusion_collection.main_window import format_open_tc_warning
from fusion_collection.recovery import (
    DATA_FILENAME,
    MANIFEST_FILENAME,
    TARGET_FILENAME,
    find_pending_sessions,
    pack_staging_dir_to_fus,
    prune_invalid_sessions,
    remove_staging_dir,
)
from fusion_collection.session import MeasurementSession

if TYPE_CHECKING:
    from pathlib import Path


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
    assert pytest.approx(0.001) == SAFE_ZERO_OFFSET_V
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

    from PySide6.QtWidgets import QApplication

    from fusion_collection.config import config
    from fusion_collection.main_window import MainWindow

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


def test_staging_dir_recovery_handles_truncated_row_and_stub(tmp_path: Path) -> None:
    recovery_root = tmp_path / "recovery"
    target_fus = tmp_path / "002_Sn_reper.fus"

    sess = MeasurementSession(
        mode=StandMode.DTA,
        sample="Sn репер",
        operator="Tester",
        sensor_t1=make_xa_thermocouple(),
        sensor_t2=make_xa_thermocouple(),
        recovery_root=recovery_root,
    )
    sess.reserve_file(target_fus)
    assert target_fus.stat().st_size == 1

    sess.start_recording()
    staging_dir = sess.active_staging_dir
    assert staging_dir is not None
    assert (staging_dir / MANIFEST_FILENAME).is_file()
    assert (staging_dir / DATA_FILENAME).is_file()
    assert (staging_dir / TARGET_FILENAME).is_file()

    sess.append_sample(
        LiveSample(timestamp=10.0, mode=StandMode.DTA, emf_1_mv=65.521, emf_2_mv=5.0)
    )
    sess.append_sample(
        LiveSample(timestamp=11.0, mode=StandMode.DTA, emf_1_mv=65.521, emf_2_mv=5.5)
    )
    sess.append_sample(
        LiveSample(timestamp=12.0, mode=StandMode.DTA, emf_1_mv=65.521, emf_2_mv=6.0)
    )

    # Имитация внезапного падения процесса: закрываем data.csv и освобождаем Win32 lock,
    # как делает ОС при завершении процесса, и дописываем оборванную строку CSV
    sess.stop_recording()
    sess._unlock_and_close_handle()
    with (staging_dir / DATA_FILENAME).open("a", encoding="utf-8") as fh:
        fh.write("3.0,65.521,6.")

    # Пустая папка не удаляется чистым запросом find_pending_sessions (CQS), но удаляется prune_invalid_sessions
    empty_dir = recovery_root / "20250912_000000_000000_empty"
    empty_dir.mkdir(parents=True)
    pending = find_pending_sessions(recovery_root=recovery_root)
    assert empty_dir.exists()
    assert prune_invalid_sessions(recovery_root=recovery_root) == 1
    assert not empty_dir.exists()
    assert len(pending) == 1
    first_pending, *_ = pending
    assert first_pending.sample == "Sn репер"
    assert first_pending.target_path == target_fus
    assert first_pending.row_count == 3

    pack_staging_dir_to_fus(first_pending.staging_dir, target_fus)
    remove_staging_dir(first_pending.staging_dir)

    loaded = load_fus(target_fus)
    assert loaded.manifest.sample == "Sn репер"
    assert len(loaded.time_array) == 3
    dta_desc = loaded.get_descriptor("dta")
    assert dta_desc is not None
    assert dta_desc.metadata.get("exo_up") is True
    assert find_pending_sessions(recovery_root=recovery_root) == []


def test_staging_dir_cleanup_on_finalize_and_discard(tmp_path: Path) -> None:
    recovery_root = tmp_path / "recovery"

    ok_file = tmp_path / "ok.fus"
    ok_sess = MeasurementSession(
        mode=StandMode.VTA,
        sample="OkSample",
        operator="Tester",
        sensor_t1=make_vr_thermocouple(),
        recovery_root=recovery_root,
    )
    ok_sess.reserve_file(ok_file)
    ok_sess.start_recording()
    ok_staging = ok_sess.active_staging_dir
    assert ok_staging is not None
    ok_sess.append_sample(
        LiveSample(timestamp=1.0, mode=StandMode.VTA, emf_1_mv=3.0, heater_output_v=0.2)
    )
    ok_sess.stop_recording()
    assert ok_sess.finalize_locked_file() == ok_file
    assert not ok_staging.exists()
    assert len(load_fus(ok_file).time_array) == 1

    disc_file = tmp_path / "discarded.fus"
    disc_sess = MeasurementSession(
        mode=StandMode.DTA,
        sample="Discarded",
        operator="Tester",
        sensor_t1=make_xa_thermocouple(),
        sensor_t2=make_xa_thermocouple(),
        recovery_root=recovery_root,
    )
    disc_sess.reserve_file(disc_file)
    disc_sess.start_recording()
    disc_staging = disc_sess.active_staging_dir
    assert disc_staging is not None
    disc_sess.append_sample(
        LiveSample(timestamp=2.0, mode=StandMode.DTA, emf_1_mv=4.0, emf_2_mv=3.9)
    )
    disc_sess.discard_recording()
    assert not disc_staging.exists()
    assert not disc_file.exists()


def test_open_thermocouple_warning_text_and_log_debounce() -> None:
    assert format_open_tc_warning(False, False) == ""
    w1 = format_open_tc_warning(True, False)
    assert "Канал 1" in w1
    assert "мВ" not in w1
    assert "Канал 2" in format_open_tc_warning(False, True)
    w12 = format_open_tc_warning(True, True)
    assert "Канал 1" in w12
    assert "Канал 2" in w12

    records: list[tuple[str, str]] = []
    sink_id = log.add(
        lambda msg: records.append((msg.record["level"].name, msg.record["message"]))
    )
    try:
        loop = AcquisitionLoop(HardwareManager())
        for _ in range(5):
            loop.report_open_tc_transition(StandMode.DTA, True, False, 65.521, 5.0)
        loop.report_open_tc_transition(StandMode.DTA, False, False, 5.1, 5.0)
        loop.report_open_tc_transition(StandMode.DTA, False, False, 5.2, 5.0)
    finally:
        log.remove(sink_id)

    assert records == [
        ("WARNING", "Open thermocouple detected"),
        ("INFO", "Thermocouple circuit restored"),
    ]


def test_main_window_displays_error_for_open_thermocouple_fields() -> None:
    import sys

    from PySide6.QtWidgets import QApplication

    from fusion_collection.config import config
    from fusion_collection.main_window import MainWindow

    _app = QApplication.instance() or QApplication(sys.argv)
    prev_test_mode = config.is_test_mode
    prev_mode = config.mode
    config.is_test_mode = True
    try:
        config.mode = StandMode.DTA
        win = MainWindow()
        try:
            win._on_live_sample(
                LiveSample(
                    timestamp=1.0,
                    mode=StandMode.DTA,
                    emf_1_mv=65.521,
                    emf_2_mv=5.0,
                    open_tc_1=True,
                    open_tc_2=False,
                )
            )
            for lbl in (win.lbl_t1, win.lbl_temp, win.lbl_heat_rate, win.lbl_dta):
                assert "Ошибка" in lbl.text()
                assert "обрыв" not in lbl.text().lower()
            assert win.lbl_t2.text() == "5.000 мВ"

            win._on_live_sample(
                LiveSample(
                    timestamp=2.0,
                    mode=StandMode.DTA,
                    emf_1_mv=10.0,
                    emf_2_mv=65.521,
                    open_tc_1=False,
                    open_tc_2=True,
                )
            )
            assert win.lbl_t1.text() == "10.000 мВ"
            assert "Ошибка" not in win.lbl_temp.text()
            assert "Ошибка" not in win.lbl_heat_rate.text()
            assert "Ошибка" in win.lbl_t2.text()
            assert "Ошибка" in win.lbl_dta.text()

            win._on_live_sample(
                LiveSample(
                    timestamp=3.0,
                    mode=StandMode.DTA,
                    emf_1_mv=65.521,
                    emf_2_mv=65.521,
                    open_tc_1=True,
                    open_tc_2=True,
                )
            )
            for lbl in (
                win.lbl_t1,
                win.lbl_temp,
                win.lbl_heat_rate,
                win.lbl_t2,
                win.lbl_dta,
            ):
                assert "Ошибка" in lbl.text()

            config.mode = StandMode.VTA
            win._build_ui()
            win._on_live_sample(
                LiveSample(
                    timestamp=4.0,
                    mode=StandMode.VTA,
                    emf_1_mv=65.521,
                    heater_output_v=1.25,
                    open_tc_1=True,
                    open_tc_2=False,
                )
            )
            for lbl in (win.lbl_t1, win.lbl_temp, win.lbl_heat_rate):
                assert "Ошибка" in lbl.text()
            assert win.lbl_out.text() == "1.250 В"
        finally:
            win.acq_loop.stop_monitoring()
            win.close()
    finally:
        config.is_test_mode = prev_test_mode
        config.mode = prev_mode
