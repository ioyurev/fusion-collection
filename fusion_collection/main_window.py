from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fusion_common import (
    COLLECTION_ICON_BG,
    FUS_EXT_FILTER,
    AdditivePolynomialCalibration,
    CalibrationSpec,
    IdentityCalibration,
    SensorSpec,
    make_vr_thermocouple,
    make_xa_thermocouple,
    resolve_ui_icon,
    show_fusion_about,
    show_fusion_docs,
    show_fusion_license,
    show_fusion_logs,
)
from loguru import logger as log
from PySide6 import QtCore, QtGui, QtWidgets

from fusion_collection.acquisition import AcquisitionLoop, LiveSample
from fusion_collection.calibration_manager import (
    get_calibration_manager,
    get_thermocouple_manager,
)
from fusion_collection.config import APPDATA_PATH, CONFIG_PATH, config
from fusion_collection.dialogs import (
    CalibrationManagerDialog,
    ConfigDialog,
    ModuleConfigWarningDialog,
    NewMeasurementDialog,
)
from fusion_collection.hardware import HardwareManager
from fusion_collection.plotter import LivePlotPanel
from fusion_collection.recovery import (
    find_pending_sessions,
    pack_staging_dir_to_fus,
    prune_invalid_sessions,
    remove_staging_dir,
)
from fusion_collection.session import MeasurementSession
from fusion_collection.thermocouple_dialogs import ThermocoupleManagerDialog
from fusion_collection.version import VERSION

if TYPE_CHECKING:
    from fusion_collection.recovery import PendingSession


def _format_mm_ss(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


_OPEN_TC_ERROR_HTML = '<span style="color: #d35400;"><b>Ошибка</b></span>'


def format_open_tc_warning(open_tc_1: bool, open_tc_2: bool) -> str:
    """Формирует канальный текст предупреждения об обрыве термопары без вывода ЭДС."""
    if open_tc_1 and open_tc_2:
        return "⚠ ВНИМАНИЕ: Обрыв цепи термопар (Канал 1 и Канал 2)!"
    if open_tc_1:
        return "⚠ ВНИМАНИЕ: Обрыв цепи термопары (Канал 1)!"
    if open_tc_2:
        return "⚠ ВНИМАНИЕ: Обрыв цепи термопары (Канал 2)!"
    return ""


class MainWindow(QtWidgets.QMainWindow):
    """Главное окно Fusion Collection с постоянным мониторингом в реальном времени."""

    def __init__(self) -> None:
        super().__init__()
        self.resize(1024, 680)
        log.bind(
            version=VERSION,
            config_path=str(CONFIG_PATH),
            **config.model_dump(mode="json"),
        ).info("Fusion Collection MainWindow initialized")
        self.hardware = HardwareManager()
        self.acq_loop = AcquisitionLoop(self.hardware, parent=self)
        self.session: MeasurementSession = self._create_monitoring_session()

        self._setup_menubar()
        self._build_ui()
        self.acq_loop.sample_ready.connect(self._on_live_sample)
        self.acq_loop.error_occurred.connect(self._on_loop_error)
        QtCore.QTimer.singleShot(50, self._startup_sequence)

    def _resolve_sensor(self, name: str, fallback: SensorSpec) -> SensorSpec:
        mgr = get_thermocouple_manager()
        try:
            return mgr.load_sensor(name)
        except KeyError:
            log.bind(requested_sensor=name, fallback_sensor=fallback.name).warning(
                "Configured thermocouple profile not found, using default ГОСТ profile"
            )
            return fallback

    def _resolve_active_calibration(self) -> CalibrationSpec:
        if not config.calibration_enabled or not config.last_selected_calibration:
            return IdentityCalibration()
        try:
            return get_calibration_manager().load_calibration(
                config.last_selected_calibration
            )
        except (KeyError, OSError, ValueError) as exc:
            log.bind(
                calibration=config.last_selected_calibration, error=str(exc)
            ).warning("Failed to load active calibration, disabling calibration")
            return IdentityCalibration()

    def _create_monitoring_session(
        self,
        sample: str = "—",
        operator: str = "",
        comment: str = "",
        sample_mass_mg: float | None = None,
        crucible: str = "",
        atmosphere: str = "",
    ) -> MeasurementSession:
        tc1 = self._resolve_sensor(config.thermocouple_t1, make_vr_thermocouple())
        tc2 = self._resolve_sensor(config.thermocouple_t2, make_xa_thermocouple())
        cal = self._resolve_active_calibration()
        return MeasurementSession(
            mode=config.mode,
            sample=sample,
            operator=operator or config.operator,
            comment=comment,
            sample_mass_mg=sample_mass_mg,
            crucible=crucible,
            atmosphere=atmosphere,
            sensor_t1=tc1,
            sensor_t2=tc2,
            calibration_t1=cal,
        )

    def _setup_menubar(self) -> None:
        menubar = self.menuBar()
        menubar.clear()
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon

        menu_file = menubar.addMenu("Файл")
        self.act_new = QtGui.QAction(
            resolve_ui_icon(ti.DocumentNew, st.SP_FileIcon),
            "Новое измерение",
            self,
        )
        self.act_new.triggered.connect(self._start_new_measurement_dialog)
        menu_file.addAction(self.act_new)

        menu_settings = menubar.addMenu("Настройки")
        act_cfg = QtGui.QAction(
            resolve_ui_icon(ti.Computer, st.SP_ComputerIcon),
            "Конфигурация стенда",
            self,
        )
        act_tc = QtGui.QAction(
            resolve_ui_icon(ti.DocumentProperties, st.SP_FileDialogDetailedView),
            "Управление термопарами",
            self,
        )
        act_cal = QtGui.QAction(
            resolve_ui_icon(ti.ToolsCheckSpelling, st.SP_DialogApplyButton),
            "Управление калибровками",
            self,
        )
        act_cfg.triggered.connect(self._open_config_dialog)
        act_tc.triggered.connect(self._open_tc_manager)
        act_cal.triggered.connect(self._open_cal_manager)
        menu_settings.addAction(act_cfg)
        menu_settings.addAction(act_tc)
        menu_settings.addAction(act_cal)

        menu_help = menubar.addMenu("Справка")
        act_docs = QtGui.QAction(
            resolve_ui_icon(ti.HelpFaq, st.SP_DialogHelpButton),
            "Руководство пользователя (F1)",
            self,
        )
        act_docs.setShortcut(QtGui.QKeySequence("F1"))
        act_docs.triggered.connect(
            lambda: show_fusion_docs(
                app_title="Fusion Collection",
                package_name="fusion_collection",
                icon_bg_color=COLLECTION_ICON_BG,
                parent=self,
            )
        )
        act_lic = QtGui.QAction(
            resolve_ui_icon(ti.DialogInformation, st.SP_MessageBoxInformation),
            "Лицензия GNU GPL v3.0",
            self,
        )
        act_lic.triggered.connect(
            lambda: show_fusion_license(
                app_title="Fusion Collection",
                icon_bg_color=COLLECTION_ICON_BG,
                parent=self,
            )
        )
        act_logs = QtGui.QAction(
            resolve_ui_icon(ti.EditFind, st.SP_FileDialogInfoView),
            "Журнал работы (логи) (F12)",
            self,
        )
        act_logs.setShortcut(QtGui.QKeySequence("F12"))
        act_logs.triggered.connect(
            lambda: show_fusion_logs(
                app_title="Fusion Collection",
                appdata_path=APPDATA_PATH,
                icon_bg_color=COLLECTION_ICON_BG,
                parent=self,
            )
        )
        menu_help.addAction(act_docs)
        menu_help.addAction(act_lic)
        menu_help.addAction(act_logs)
        menu_help.addSeparator()
        act_about = QtGui.QAction(
            resolve_ui_icon(ti.HelpAbout, st.SP_MessageBoxInformation),
            "О программе",
            self,
        )
        act_about.triggered.connect(
            lambda: show_fusion_about(
                app_title="Fusion Collection",
                version_str=VERSION,
                description=(
                    "Единое приложение сбора данных термического анализа "
                    "(ВТА и ДТА) и управления нагревом печи."
                ),
                repo_slug="fusion-collection",
                icon_bg_color=COLLECTION_ICON_BG,
                zenodo_doi="10.5281/zenodo.24275001",
                parent=self,
            )
        )
        menu_help.addAction(act_about)

    def _build_ui(self) -> None:
        mode_title = "ВТА" if config.mode == "vta" else "ДТА"
        self.setWindowTitle(f"Fusion Collection — Режим {mode_title}")

        old_central = self.centralWidget()
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        if old_central is not None:
            old_central.deleteLater()
        main_h = QtWidgets.QHBoxLayout(central)

        left_panel = QtWidgets.QVBoxLayout()
        self.lbl_warning = QtWidgets.QLabel("")
        self.lbl_warning.setStyleSheet("color: #d35400; font-weight: bold;")
        self.lbl_warning.hide()
        left_panel.addWidget(self.lbl_warning)

        live_group = QtWidgets.QGroupBox("Текущие показания")
        live_form = QtWidgets.QFormLayout(live_group)
        self.lbl_temp = QtWidgets.QLabel("<b>0.0 °C</b>")
        self.lbl_heat_rate = QtWidgets.QLabel("+0.0 °C/мин")
        self.lbl_t1 = QtWidgets.QLabel("0.000 мВ")
        self.lbl_t2 = QtWidgets.QLabel("0.000 мВ")
        self.lbl_dta = QtWidgets.QLabel("0.000 мВ")
        self.lbl_out = QtWidgets.QLabel("0.000 В")
        live_form.addRow("Температура:", self.lbl_temp)
        live_form.addRow("Скорость dT/dt:", self.lbl_heat_rate)
        live_form.addRow("Термопара 1:", self.lbl_t1)
        if config.mode == "dta":
            live_form.addRow("Термопара 2:", self.lbl_t2)
            live_form.addRow("Сигнал ДТА:", self.lbl_dta)
        else:
            live_form.addRow("Выход печи:", self.lbl_out)
        left_panel.addWidget(live_group)

        tract_group = QtWidgets.QGroupBox("Измерительный тракт")
        tract_form = QtWidgets.QFormLayout(tract_group)
        self.lbl_tc1 = QtWidgets.QLabel(
            self.session.sensor_t1.display_short_name
            if self.session.sensor_t1
            else config.thermocouple_t1
        )
        self.lbl_tc2 = QtWidgets.QLabel(
            self.session.sensor_t2.display_short_name
            if self.session.sensor_t2
            else config.thermocouple_t2
        )
        self.lbl_cjc = QtWidgets.QLabel("25.0 °C (0.000 мВ)")
        self.lbl_rate = QtWidgets.QLabel("0.0 Гц")
        tract_form.addRow("Тип термопары 1:", self.lbl_tc1)
        if config.mode == "dta":
            tract_form.addRow("Тип термопары 2:", self.lbl_tc2)
        tract_form.addRow("Холодный спай:", self.lbl_cjc)
        tract_form.addRow("Частота опроса:", self.lbl_rate)
        left_panel.addWidget(tract_group)

        cal_group = QtWidgets.QGroupBox("Калибровка температуры")
        cal_form = QtWidgets.QFormLayout(cal_group)
        self.lbl_cal_name = QtWidgets.QLabel("Выключена")
        self.lbl_cal_type = QtWidgets.QLabel("—")
        self.lbl_cal_range = QtWidgets.QLabel("—")
        self.lbl_cal_stats = QtWidgets.QLabel("—")
        self.lbl_cal_stats.setWordWrap(True)
        cal_form.addRow("Профиль:", self.lbl_cal_name)
        cal_form.addRow("Тип и реперы:", self.lbl_cal_type)
        cal_form.addRow("Диапазон:", self.lbl_cal_range)
        cal_form.addRow("Статистика:", self.lbl_cal_stats)
        self._update_calibration_labels()
        left_panel.addWidget(cal_group)

        if config.mode == "vta":
            heat_group = QtWidgets.QGroupBox("Управление нагревом (ВТА)")
            heat_layout = QtWidgets.QVBoxLayout(heat_group)
            spd_row = QtWidgets.QHBoxLayout()
            spd_row.addWidget(QtWidgets.QLabel("Скорость (мВ/с):"))
            self.sb_speed = QtWidgets.QSpinBox()
            self.sb_speed.setRange(-100, 100)
            self.sb_speed.setValue(config.default_speed)
            self.sb_speed.valueChanged.connect(self.acq_loop.heater.set_speed)
            spd_row.addWidget(self.sb_speed)
            heat_layout.addLayout(spd_row)

            st = QtWidgets.QStyle.StandardPixmap
            ti = QtGui.QIcon.ThemeIcon
            self.btn_heat_on = QtWidgets.QPushButton(
                resolve_ui_icon(ti.MediaPlaybackStart, st.SP_MediaPlay),
                "Включить развёртку нагрева",
            )
            self.btn_heat_pause = QtWidgets.QPushButton(
                resolve_ui_icon(ti.MediaPlaybackPause, st.SP_MediaPause),
                "Пауза развёртки (0 мВ/с)",
            )
            self.btn_heat_reset = QtWidgets.QPushButton(
                resolve_ui_icon(ti.MediaPlaybackStop, st.SP_MediaStop),
                "Сбросить выход нагрева в 0 В",
            )
            self.btn_heat_on.clicked.connect(
                lambda: self.acq_loop.heater.set_enabled(True)
            )
            self.btn_heat_pause.clicked.connect(lambda: self.sb_speed.setValue(0))
            self.btn_heat_reset.clicked.connect(self._reset_heater)
            heat_layout.addWidget(self.btn_heat_on)
            heat_layout.addWidget(self.btn_heat_pause)
            heat_layout.addWidget(self.btn_heat_reset)
            left_panel.addWidget(heat_group)

        rec_group = QtWidgets.QGroupBox("Запись измерения")
        rec_vbox = QtWidgets.QVBoxLayout(rec_group)
        rec_form = QtWidgets.QFormLayout()
        sample_txt = (
            f"<b>{self.session.sample}</b>"
            if self.session.reserved_path is not None
            else "—"
        )
        self.lbl_sample = QtWidgets.QLabel(sample_txt)
        self.lbl_file = QtWidgets.QLabel("—")
        self.lbl_file.setOpenExternalLinks(False)
        self.lbl_file.linkActivated.connect(self._open_reserved_file_folder)
        self._update_file_link_label()
        self.lbl_operator = QtWidgets.QLabel(self.session.operator or config.operator)
        self.lbl_time = QtWidgets.QLabel("00:00")
        rec_form.addRow("Образец:", self.lbl_sample)
        rec_form.addRow("Файл:", self.lbl_file)
        rec_form.addRow("Оператор:", self.lbl_operator)
        rec_form.addRow("Время записи:", self.lbl_time)
        rec_vbox.addLayout(rec_form)

        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        rec_btns = QtWidgets.QHBoxLayout()
        self.btn_rec_start = QtWidgets.QPushButton(
            resolve_ui_icon(ti.MediaRecord, st.SP_MediaPlay),
            "Старт записи",
        )
        self.btn_rec_start.setEnabled(
            self.session.reserved_path is not None
            and not self.session.recording_enabled
        )
        self.btn_rec_start.setToolTip(
            "Сначала создайте измерение в меню 'Файл -> Новое измерение'"
        )
        self.btn_rec_stop = QtWidgets.QPushButton(
            resolve_ui_icon(ti.MediaPlaybackStop, st.SP_MediaStop),
            "Стоп записи",
        )
        self.btn_rec_stop.setEnabled(self.session.recording_enabled)
        self.btn_rec_start.clicked.connect(self._on_start_recording_clicked)
        self.btn_rec_stop.clicked.connect(self._on_stop_recording_clicked)
        rec_btns.addWidget(self.btn_rec_start)
        rec_btns.addWidget(self.btn_rec_stop)
        rec_vbox.addLayout(rec_btns)
        left_panel.addWidget(rec_group)
        left_panel.addStretch()

        self.plot_panel = LivePlotPanel(mode=config.mode, parent=self)

        main_h.addLayout(left_panel, 0)
        main_h.addWidget(self.plot_panel, 1)

    def _update_calibration_labels(self) -> None:
        cal = self.session.calibration_t1
        if isinstance(cal, AdditivePolynomialCalibration):
            self.lbl_cal_name.setText(f"<b>{cal.name or 'Без имени'}</b>")
            self.lbl_cal_type.setText(
                f"{cal.calibration_type} ({len(cal.standards)} реп.)"
            )
            rng = cal.valid_temp_range
            self.lbl_cal_range.setText(
                f"{rng[0]:.1f} .. {rng[1]:.1f} °C" if rng else "—"  # noqa: MI001
            )
            try:
                st = cal.calculate_statistics()
                r2_s = f"{st.r_squared:.4f}" if st.r_squared is not None else "N/A"
                sec_s = f"{st.sec:.2f} °C" if st.sec is not None else "N/A"
                unc_s = (
                    f"±{st.expanded_uncertainty:.2f} °C"
                    if st.expanded_uncertainty is not None
                    else "N/A"
                )
                self.lbl_cal_stats.setText(f"R²={r2_s} | SEC={sec_s} | U={unc_s}")
            except ValueError:
                self.lbl_cal_stats.setText("—")
        else:
            self.lbl_cal_name.setText("Выключена")
            self.lbl_cal_type.setText("—")
            self.lbl_cal_range.setText("—")
            self.lbl_cal_stats.setText("—")

    def _update_file_link_label(self) -> None:
        p = self.session.reserved_path
        if p is not None:
            self.lbl_file.setText(f'<a href="#open">{p.name}</a>')
            self.lbl_file.setToolTip(f"Открыть папку с файлом:\n{p.resolve()}")
        else:
            self.lbl_file.setText("—")
            self.lbl_file.setToolTip("")

    def _open_reserved_file_folder(self, _link: str) -> None:
        p = self.session.reserved_path
        if p is not None:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl.fromLocalFile(str(p.resolve().parent))
            )

    def _reset_heater(self) -> None:
        self.acq_loop.heater.set_enabled(False)
        self.acq_loop.heater.reset()

    def _startup_sequence(self) -> None:
        self._check_pending_recovery()
        self._connect_and_start_monitoring()

    def _check_pending_recovery(self) -> None:
        active_dir = self.session.active_staging_dir
        prune_invalid_sessions(active_dir=active_dir)
        pending_items = find_pending_sessions(active_dir=active_dir)
        for item in pending_items:
            self._prompt_recover_session(item)

    def _prompt_recover_session(self, pending: PendingSession) -> None:
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle("Незавершённая запись измерения")
        target_str = str(pending.target_path) if pending.target_path else "не указан"
        box.setText(
            "Обнаружена незавершённая запись измерения после предыдущего сеанса:\n"
            f"• Образец: {pending.sample or '—'}\n"
            f"• Оператор: {pending.operator or '—'}\n"
            f"• Записано точек: {pending.row_count}\n"
            f"• Целевой файл: {target_str}\n\n"
            "Восстановить данные и сохранить их в файл .fus?"
        )
        btn_recover = box.addButton(
            "Восстановить в .fus",
            QtWidgets.QMessageBox.ButtonRole.AcceptRole,
        )
        btn_delete = box.addButton(
            "Удалить запись",
            QtWidgets.QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton(
            "Отложить",
            QtWidgets.QMessageBox.ButtonRole.RejectRole,
        )
        box.exec()
        clicked = box.clickedButton()

        if clicked == btn_delete:
            log.bind(
                staging_dir=str(pending.staging_dir),
                sample=pending.sample,
                rows=pending.row_count,
            ).info("User deleted pending recovery session")
            remove_staging_dir(
                pending.staging_dir,
                remove_empty_target_stub=True,
                target_path=pending.target_path,
            )
            return

        if clicked != btn_recover:
            return

        dest = pending.target_path
        need_prompt = (
            dest is None
            or not dest.parent.is_dir()
            or (dest.is_file() and dest.stat().st_size > 1)
        )
        if need_prompt:
            suggested = str(
                dest
                if dest is not None and dest.parent.is_dir()
                else (config.last_save_dir / f"{pending.sample or 'recovered'}.fus")
            )
            fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001 — Qt QFileDialog API returns (path, filter)
                self,
                "Сохранить восстановленное измерение (.fus)",
                suggested,
                FUS_EXT_FILTER,
            )
            if not fname:
                return
            dest = Path(fname)
            if dest.suffix.lower() != ".fus":
                dest = dest.with_suffix(".fus")

        assert dest is not None  # noqa: S101 — сужение типа Optional для mypy
        try:
            pack_staging_dir_to_fus(pending.staging_dir, dest)
        except (OSError, ValueError) as exc:
            log.opt(exception=True).bind(
                staging_dir=str(pending.staging_dir),
                target=str(dest),
                error=repr(exc),
            ).error("Failed to recover pending session to .fus")
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка восстановления",
                f"Не удалось восстановить измерение в файл '{dest}':\n{exc}",
            )
            return

        log.bind(
            staging_dir=str(pending.staging_dir),
            target=str(dest),
            sample=pending.sample,
            rows=pending.row_count,
        ).info("Recovered interrupted measurement to .fus")
        remove_staging_dir(pending.staging_dir)
        QtWidgets.QMessageBox.information(
            self,
            "Измерение восстановлено",
            f"Данные успешно восстановлены и сохранены в файл:\n{dest}",
        )

    def _connect_and_start_monitoring(self) -> None:
        self.acq_loop.stop_monitoring()
        if not self.hardware.connect_and_discover(mode=config.mode):
            QtWidgets.QMessageBox.warning(
                self,
                "Оборудование не найдено",
                "Не удалось обнаружить модули ADAM на доступных COM-портах. "
                "Проверьте питание модулей или включите тестовый режим в настройках.",
            )
            return

        try:
            mismatches = self.hardware.inspect_configurations(mode=config.mode)
        except Exception as exc:  # noqa: BLE001
            log.opt(exception=True).bind(
                mode=str(config.mode), error=repr(exc)
            ).warning("Configuration inspection failed")
            mismatches = []

        if mismatches:
            dlg = ModuleConfigWarningDialog(mismatches, parent=self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                QtWidgets.QApplication.setOverrideCursor(
                    QtCore.Qt.CursorShape.WaitCursor
                )
                try:
                    self.hardware.apply_reconfiguration(mismatches)
                finally:
                    QtWidgets.QApplication.restoreOverrideCursor()

        self.acq_loop.start_monitoring()

    @QtCore.Slot(object)
    def _on_live_sample(self, sample: LiveSample) -> None:
        pt = self.session.append_sample(sample)
        self.lbl_rate.setText(f"{sample.sampling_rate_hz:.1f} Гц")
        self.lbl_cjc.setText(
            f"{sample.cjc_temp_c:.1f} °C ({self.session.cjc_t1.e_cold:.3f} мВ)"
        )
        if sample.open_tc_1:
            self.lbl_t1.setText(_OPEN_TC_ERROR_HTML)
            self.lbl_temp.setText(_OPEN_TC_ERROR_HTML)
            self.lbl_heat_rate.setText(_OPEN_TC_ERROR_HTML)
        else:
            self.lbl_t1.setText(f"{sample.emf_1_mv:.3f} мВ")
            self.lbl_temp.setText(f"<b>{pt.temp_1_c:.1f} °C</b>")
            self.lbl_heat_rate.setText(f"{pt.heating_rate_c_min:+.1f} °C/мин")

        if config.mode == "vta":
            self.lbl_out.setText(f"{sample.heater_output_v:.3f} В")
        else:
            self.lbl_t2.setText(
                _OPEN_TC_ERROR_HTML if sample.open_tc_2 else f"{sample.emf_2_mv:.3f} мВ"
            )
            self.lbl_dta.setText(
                _OPEN_TC_ERROR_HTML
                if (sample.open_tc_1 or sample.open_tc_2)
                else f"{pt.dta_mv:.3f} мВ"
            )

        warn_text = format_open_tc_warning(sample.open_tc_1, sample.open_tc_2)
        if warn_text:
            self.lbl_warning.setText(warn_text)
            self.lbl_warning.show()
        else:
            self.lbl_warning.hide()

        if self.session.recording_enabled:
            self.lbl_time.setText(_format_mm_ss(pt.rel_time_s))

        self.plot_panel.append_point(
            timestamp=sample.timestamp,
            emf_1_mv=sample.emf_1_mv,
            temp_1_c=pt.temp_1_c,
            emf_2_mv=sample.emf_2_mv,
            heater_output_v=sample.heater_output_v,
        )

    @QtCore.Slot(str)
    def _on_loop_error(self, msg: str) -> None:
        self.lbl_warning.setText(f"⚠ Ошибка опроса: {msg}")
        self.lbl_warning.show()

    def _confirm_discard_or_save(self) -> bool:
        if not self.session.has_unsaved_data:
            return True
        ans = QtWidgets.QMessageBox.question(
            self,
            "Несохранённое измерение",
            "В текущей сессии есть несохранённые данные измерения.\n"
            "Сохранить их в файл .fus перед продолжением?",
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Save,
        )
        if ans == QtWidgets.QMessageBox.StandardButton.Cancel:
            return False
        if ans == QtWidgets.QMessageBox.StandardButton.Save:
            self.session.stop_recording()
            self._save_recorded_session()
            return not self.session.has_unsaved_data
        if ans == QtWidgets.QMessageBox.StandardButton.Discard:
            self.session.discard_recording()
        return True

    def _start_new_measurement_dialog(self) -> None:
        if not self._confirm_discard_or_save():
            return
        dlg = NewMeasurementDialog(parent=self)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.session.release_unused_reservation()
        mass_val = float(dlg.sb_mass.value())
        self.session = self._create_monitoring_session(
            sample=dlg.le_sample.text().strip(),
            operator=dlg.le_operator.text().strip(),
            comment=dlg.txt_comment.toPlainText().strip(),
            sample_mass_mg=mass_val if mass_val > 0.0 else None,
            crucible=dlg.le_crucible.text().strip(),
            atmosphere=dlg.le_atmosphere.text().strip(),
        )
        target_path = Path(dlg.le_filepath.text().strip())
        try:
            self.session.reserve_file(target_path)
        except OSError as exc:
            log.opt(exception=True).bind(path=str(target_path), error=repr(exc)).error(
                "Failed to reserve measurement file (.fus)"
            )
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка резервирования файла",
                f"Не удалось создать и заблокировать файл '{target_path}':\n{exc}",
            )
            return
        log.bind(
            mode=str(self.session.mode),
            sample=self.session.sample,
            operator=self.session.operator,
            sample_mass_mg=self.session.sample_mass_mg,
            crucible=self.session.crucible,
            atmosphere=self.session.atmosphere,
            sensor_t1=(self.session.sensor_t1.name if self.session.sensor_t1 else None),
            sensor_t2=(self.session.sensor_t2.name if self.session.sensor_t2 else None),
            calibration=(
                self.session.calibration_t1.name
                if self.session.calibration_t1
                else None
            ),
            reserved_path=str(target_path),
            comment=self.session.comment,
        ).info("Created and reserved new measurement session (.fus)")
        self.lbl_sample.setText(f"<b>{self.session.sample}</b>")
        self._update_file_link_label()
        self.lbl_operator.setText(self.session.operator)
        self._update_calibration_labels()
        self.lbl_time.setText("00:00")
        self.plot_panel.clear()
        self.plot_panel.set_recording_active(False)
        self.btn_rec_start.setEnabled(True)
        self.btn_rec_stop.setEnabled(False)

    def _on_start_recording_clicked(self) -> None:
        if self.session.reserved_path is None:
            return
        try:
            cjc_val = self.acq_loop.refresh_cjc_once()
            self.session.update_cjc(cjc_val)
        except Exception as exc:  # noqa: BLE001
            log.opt(exception=True).bind(error=repr(exc)).error(
                "Aborting measurement recording start due to CJC read failure"
            )
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка измерения холодного спая (CJC)",
                f"Не удалось считать температуру холодного спая ($AA3):\n{exc}\n\n"
                "Запись измерения отменена.",
            )
            return
        self.plot_panel.clear()
        self.plot_panel.set_recording_active(True)
        self.session.start_recording()
        log.bind(
            mode=str(self.session.mode),
            sample=self.session.sample,
            reserved_path=str(self.session.reserved_path),
            cjc_temp_c=self.session.cjc_t1.temperature,
            e_cold_mv=self.session.cjc_t1.e_cold,
        ).info("Started measurement recording")
        self.btn_rec_start.setEnabled(False)
        self.btn_rec_stop.setEnabled(True)

    def _on_stop_recording_clicked(self) -> None:
        if not self.session.recording_enabled:
            return
        self.session.stop_recording()
        dur_s = 0.0
        if self.session.time_list:
            *_, dur_s = self.session.time_list
        log.bind(
            mode=str(self.session.mode),
            sample=self.session.sample,
            points=len(self.session.time_list),
            duration_sec=dur_s,
        ).info("Stopped measurement recording")
        self.plot_panel.set_recording_active(False)
        self.btn_rec_start.setEnabled(False)
        self.btn_rec_stop.setEnabled(False)
        self._save_recorded_session(notify_user=True)

    def _save_recorded_session(self, notify_user: bool = False) -> None:
        if not self.session.time_list:
            if notify_user:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Запись остановлена",
                    "Запись остановлена, но ни одной точки не было накоплено.",
                )
            return
        if self.session.recording_enabled:
            self.session.stop_recording()
            self.plot_panel.set_recording_active(False)
            self.btn_rec_stop.setEnabled(False)
        try:
            locked_saved = self.session.finalize_locked_file()
            if locked_saved is not None:
                dur_s = 0.0
                if self.session.time_list:
                    *_, dur_s = self.session.time_list
                log.bind(
                    path=str(locked_saved),
                    sample=self.session.sample,
                    points=len(self.session.time_list),
                    duration_sec=dur_s,
                ).info("Saved measurement file (.fus)")
                config.last_save_measurement_index += 1
                config.last_save_dir = locked_saved.parent
                config.update()
                if notify_user:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Измерение сохранено",
                        f"Запись завершена.\nДанные успешно сохранены в файл:\n{locked_saved}",
                    )
        except (OSError, ValueError) as exc:
            log.opt(exception=True).bind(
                path=str(self.session.reserved_path), error=repr(exc)
            ).error("Failed to save measurement")
            if notify_user:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Ошибка сохранения измерения",
                    f"Не удалось сохранить данные измерения в файл:\n{exc}",
                )

    def _open_config_dialog(self) -> None:
        prev_mode = config.mode
        dlg = ConfigDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            log.bind(
                prev_mode=str(prev_mode),
                **config.model_dump(mode="json"),
            ).info("Updated stand configuration from Settings dialog")
            self.session = self._create_monitoring_session(
                sample=self.session.sample,
                operator=config.operator,
                comment=self.session.comment,
            )
            if config.mode != prev_mode:
                self._build_ui()
            else:
                self.lbl_tc1.setText(
                    self.session.sensor_t1.display_short_name
                    if self.session.sensor_t1
                    else config.thermocouple_t1
                )
                self.lbl_tc2.setText(
                    self.session.sensor_t2.display_short_name
                    if self.session.sensor_t2
                    else config.thermocouple_t2
                )
                self._update_calibration_labels()
                self.lbl_operator.setText(self.session.operator)
                self.plot_panel.apply_antialias(config.antialias)
            self._connect_and_start_monitoring()

    def _open_tc_manager(self) -> None:
        ThermocoupleManagerDialog(parent=self).exec()

    def _open_cal_manager(self) -> None:
        CalibrationManagerDialog(parent=self).exec()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._confirm_discard_or_save():
            event.ignore()
            return
        self.session.release_unused_reservation()
        self.acq_loop.stop_monitoring()
        self.hardware.bus.close()
        super().closeEvent(event)
