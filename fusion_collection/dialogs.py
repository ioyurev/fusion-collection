from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from fusion_common import (
    FUS_EXT_FILTER,
    AdditivePolynomialCalibration,
    CalibrationType,
    Standard,
    resolve_ui_icon,
)
from PySide6 import QtGui, QtWidgets

from fusion_collection.calibration_manager import (
    REFERENCE_STANDARDS,
    get_calibration_manager,
    get_thermocouple_manager,
)
from fusion_collection.config import StandMode, config
from fusion_collection.hardware import ModuleConfigMismatch, get_serial_ports


class ModuleConfigWarningDialog(QtWidgets.QDialog):
    """Окно предупреждения при несоответствии конфигурации модулей ADAM требованиям программы."""

    def __init__(
        self,
        mismatches: list[ModuleConfigMismatch],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mismatches = mismatches
        self.setWindowTitle("Несоответствие конфигурации модулей ADAM")
        self.resize(680, 480)

        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QLabel(
            "<b>Внимание!</b> Текущая конфигурация подключённых модулей ADAM "
            "не соответствует требованиям для корректной работы программы:"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        text_box = QtWidgets.QTextEdit()
        text_box.setReadOnly(True)
        blocks: list[str] = []
        for item in mismatches:
            issues_str = "\n".join(f"  ⚠ {iss}" for iss in item.issues)
            blocks.append(
                f"=== {item.module_label} ===\n"
                f"Обнаруженные расхождения:\n{issues_str}\n\n"
                f"[Текущая конфигурация в модуле]\n{item.current_summary}\n\n"
                f"[Требуемая конфигурация программы]\n{item.expected_summary}\n"
            )
        text_box.setPlainText("\n" + ("-" * 60 + "\n").join(blocks))
        layout.addWidget(text_box, 1)

        prompt = QtWidgets.QLabel(
            "Применить требуемую конфигурацию к указанным модулям сейчас? "
            "(Для модулей ADAM-4011 перенастройка занимает ~7 секунд)."
        )
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        btns = QtWidgets.QDialogButtonBox()
        self.btn_apply = btns.addButton(
            "Применить требуемую конфигурацию",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole,
        )
        btns.addButton(
            "Оставить без изменений",
            QtWidgets.QDialogButtonBox.ButtonRole.RejectRole,
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


class CalibrationEditorDialog(QtWidgets.QDialog):
    """Окно создания и редактирования калибровки температуры по стандартным образцам."""

    def __init__(
        self,
        calibration: AdditivePolynomialCalibration | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактор калибровки температуры")
        self.resize(980, 560)
        self.result_calibration: AdditivePolynomialCalibration | None = None

        main_layout = QtWidgets.QHBoxLayout(self)
        left_col = QtWidgets.QVBoxLayout()

        form = QtWidgets.QFormLayout()
        self.le_name = QtWidgets.QLineEdit(calibration.name if calibration else "")
        self.cb_type = QtWidgets.QComboBox()
        self.cb_type.addItems([t.value for t in CalibrationType])
        if calibration:
            self.cb_type.setCurrentText(calibration.calibration_type)
        self.le_desc = QtWidgets.QLineEdit(
            calibration.description if calibration else ""
        )
        form.addRow("Название:", self.le_name)
        form.addRow("Тип полинома:", self.cb_type)
        form.addRow("Описание:", self.le_desc)
        left_col.addLayout(form)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Стандарт", "T теор (°C)", "T эксп (°C)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        left_col.addWidget(self.table, 1)

        row_btns = QtWidgets.QHBoxLayout()
        self.cb_std_preset = QtWidgets.QComboBox()
        self._populate_standards_combobox()
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        btn_add = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ListAdd, st.SP_FileDialogNewFolder),
            "Добавить эталон",
        )
        btn_custom = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentNew, st.SP_FileIcon),
            "Свой стандарт",
        )
        btn_del = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ListRemove, st.SP_TrashIcon),
            "Удалить выбранный",
        )
        btn_add.clicked.connect(self._add_preset_standard)
        btn_custom.clicked.connect(self._add_custom_standard)
        btn_del.clicked.connect(self._remove_selected_rows)
        row_btns.addWidget(self.cb_std_preset, 1)
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_custom)
        row_btns.addWidget(btn_del)
        left_col.addLayout(row_btns)

        self.lbl_formula = QtWidgets.QLabel("Tскор = Tэксп")
        left_col.addWidget(self.lbl_formula)

        self.txt_stats = QtWidgets.QTextEdit()
        self.txt_stats.setReadOnly(True)
        self.txt_stats.setMaximumHeight(130)
        left_col.addWidget(self.txt_stats)

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._on_save)
        box.rejected.connect(self.reject)
        left_col.addWidget(box)

        plot_col = QtWidgets.QVBoxLayout()
        self.plot_curve = pg.PlotWidget(title="Поправка ΔT = Tтеор - Tэксп")
        self.plot_resid = pg.PlotWidget(title="Остатки калибровки (°C)")
        plot_col.addWidget(self.plot_curve, 1)
        plot_col.addWidget(self.plot_resid, 1)

        main_layout.addLayout(left_col, 1)
        main_layout.addLayout(plot_col, 1)

        if calibration:
            for std in calibration.standards:
                self._add_standard_row(std)

        self.table.itemChanged.connect(self._recalculate_preview)
        self.cb_type.currentTextChanged.connect(self._recalculate_preview)
        self._recalculate_preview()

    def _populate_standards_combobox(self) -> None:
        self.cb_std_preset.clear()
        merged = {**REFERENCE_STANDARDS, **config.custom_standards}
        for std_label, std_temp in merged.items():
            self.cb_std_preset.addItem(
                f"{std_label} ({std_temp} °C)", (std_label, std_temp)
            )

    def _add_preset_standard(self) -> None:
        data = self.cb_std_preset.currentData()
        if isinstance(data, tuple) and len(data) == 2:
            name_s, temp_f = data
            self._add_standard_row(
                Standard(name=str(name_s), t_theor=float(temp_f), t_exp=float(temp_f))
            )

    def _add_custom_standard(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Добавить свой стандарт")
        form = QtWidgets.QFormLayout(dlg)
        le_name = QtWidgets.QLineEdit()
        sb_theor = QtWidgets.QDoubleSpinBox()
        sb_theor.setRange(-273.15, 4000.0)
        sb_theor.setDecimals(2)
        sb_theor.setValue(500.0)
        sb_exp = QtWidgets.QDoubleSpinBox()
        sb_exp.setRange(-273.15, 4000.0)
        sb_exp.setDecimals(2)
        sb_exp.setValue(500.0)
        chk_save = QtWidgets.QCheckBox("Сохранить в справочник эталонов")
        chk_save.setChecked(True)
        form.addRow("Название стандарта:", le_name)
        form.addRow("T теор (°C):", sb_theor)
        form.addRow("T эксп (°C):", sb_exp)
        form.addRow("", chk_save)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        std_name = le_name.text().strip() or "Custom"
        t_th = float(sb_theor.value())
        t_ex = float(sb_exp.value())
        if chk_save.isChecked():
            config.custom_standards[std_name] = t_th
            config.update()
            self._populate_standards_combobox()
        self._add_standard_row(Standard(name=std_name, t_theor=t_th, t_exp=t_ex))

    def _add_standard_row(self, std: Standard) -> None:
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(std.name))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(std.t_theor)))
        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(std.t_exp)))
        self.table.blockSignals(False)
        self._recalculate_preview()

    def _remove_selected_rows(self) -> None:
        rows = sorted({item.row() for item in self.table.selectedItems()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._recalculate_preview()

    def _collect_calibration(self) -> AdditivePolynomialCalibration:
        standards: list[Standard] = []
        for row in range(self.table.rowCount()):
            i0 = self.table.item(row, 0)
            i1 = self.table.item(row, 1)
            i2 = self.table.item(row, 2)
            if not (i0 and i1 and i2):
                continue
            standards.append(
                Standard(
                    name=i0.text().strip(),
                    t_theor=float(i1.text().strip()),
                    t_exp=float(i2.text().strip()),
                )
            )
        cal_type = CalibrationType(self.cb_type.currentText())
        return AdditivePolynomialCalibration.from_standards(
            name=self.le_name.text().strip() or "Calibration",
            standards=standards,
            calibration_type=cal_type,
            description=self.le_desc.text().strip(),
        )

    def _recalculate_preview(self) -> None:
        self.plot_curve.clear()
        self.plot_resid.clear()
        try:
            cal = self._collect_calibration()
            stats = cal.calculate_statistics()
            self.lbl_formula.setText(cal.to_formula_str())
            r2_s = f"{stats.r_squared:.4f}" if stats.r_squared is not None else "N/A"
            sec_s = f"{stats.sec:.3f} °C" if stats.sec is not None else "N/A (n ≤ p)"
            unc_s = (
                f"±{stats.expanded_uncertainty:.3f} °C"
                if stats.expanded_uncertainty is not None
                else "N/A"
            )
            rng = cal.valid_temp_range
            rng_s = f"{rng[0]:.1f} .. {rng[1]:.1f} °C" if rng else "—"  # noqa: MI001
            self.txt_stats.setPlainText(
                f"Диапазон реперов: {rng_s}\n"
                f"R²: {r2_s} | SEC: {sec_s} | U (k=2): {unc_s}\n"
                f"Макс. ошибка: {stats.max_abs_error:.3f} °C"
            )
            t_exp = np.array([s.t_exp for s in cal.standards], dtype=float)
            delta_actual = np.array(stats.delta_t_actual, dtype=float)
            self.plot_curve.plot(
                t_exp, delta_actual, pen=None, symbol="o", symbolBrush="r"
            )
            x_grid = np.linspace(
                float(t_exp.min()) - 20.0, float(t_exp.max()) + 20.0, 200
            )
            y_grid = np.asarray(cal.apply(x_grid), dtype=float) - x_grid
            self.plot_curve.plot(x_grid, y_grid, pen="b")
            self.plot_resid.plot(
                t_exp,
                np.array(stats.residuals, dtype=float),
                pen=None,
                symbol="o",
                symbolBrush="g",
            )
        except ValueError as exc:
            self.lbl_formula.setText("Недостаточно точек для расчёта")
            self.txt_stats.setPlainText(str(exc))

    def _on_save(self) -> None:
        if not self.le_name.text().strip():
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Укажите имя калибровки.")
            return
        try:
            self.result_calibration = self._collect_calibration()
            self.accept()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Ошибка", str(exc))


class CalibrationManagerDialog(QtWidgets.QDialog):
    """Окно управления списком калибровок температуры."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Управление калибровками температуры")
        self.resize(480, 380)
        self.mgr = get_calibration_manager()

        layout = QtWidgets.QHBoxLayout(self)
        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget, 1)

        btn_col = QtWidgets.QVBoxLayout()
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        btn_new = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ListAdd, st.SP_FileIcon), "Создать"
        )
        btn_edit = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentProperties, st.SP_FileDialogDetailedView),
            "Редактировать",
        )
        btn_del = QtWidgets.QPushButton(
            resolve_ui_icon(ti.EditDelete, st.SP_TrashIcon), "Удалить"
        )
        btn_imp = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentOpen, st.SP_DialogOpenButton), "Импорт JSON"
        )
        btn_exp = QtWidgets.QPushButton(
            resolve_ui_icon(ti.DocumentSaveAs, st.SP_DialogSaveButton), "Экспорт JSON"
        )
        btn_close = QtWidgets.QPushButton(
            resolve_ui_icon(ti.WindowClose, st.SP_DialogCloseButton), "Закрыть"
        )

        btn_new.clicked.connect(self._create_new)
        btn_edit.clicked.connect(self._edit_selected)
        btn_del.clicked.connect(self._delete_selected)
        btn_imp.clicked.connect(self._import_json)
        btn_exp.clicked.connect(self._export_json)
        btn_close.clicked.connect(self.accept)

        for b in (btn_new, btn_edit, btn_del, btn_imp, btn_exp):
            btn_col.addWidget(b)
        btn_col.addStretch()
        btn_col.addWidget(btn_close)
        layout.addLayout(btn_col)
        self._refresh()

    def _refresh(self) -> None:
        self.mgr.load_all()
        self.list_widget.clear()
        self.list_widget.addItems(self.mgr.list_names())

    def _create_new(self) -> None:
        dlg = CalibrationEditorDialog(parent=self)
        if (
            dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted
            and dlg.result_calibration
        ):
            self.mgr.save_calibration(dlg.result_calibration)
            self._refresh()

    def _edit_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        first_item, *_ = items
        cal = self.mgr.load_calibration(first_item.text())
        dlg = CalibrationEditorDialog(calibration=cal, parent=self)
        if (
            dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted
            and dlg.result_calibration
        ):
            self.mgr.save_calibration(dlg.result_calibration)
            self._refresh()

    def _delete_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        first_item, *_ = items
        self.mgr.delete_calibration(first_item.text())
        self._refresh()

    def _import_json(self) -> None:
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(  # noqa: PU001 — Qt QFileDialog API returns (path, filter)
            self, "Импорт калибровки", "", "JSON (*.json)"
        )
        if not fname:
            return
        try:
            raw = json.loads(Path(fname).read_text(encoding="utf-8"))
            cal = AdditivePolynomialCalibration.model_validate(raw)
            self.mgr.save_calibration(cal)
            self._refresh()
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.critical(self, "Ошибка импорта", str(exc))

    def _export_json(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        first_item, *_ = items
        cal = self.mgr.load_calibration(first_item.text())
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001 — Qt QFileDialog API returns (path, filter)
            self, "Экспорт калибровки", f"{cal.name}.json", "JSON (*.json)"
        )
        if fname:
            Path(fname).write_text(cal.model_dump_json(indent=2), encoding="utf-8")


class ConfigDialog(QtWidgets.QDialog):
    """Окно настройки стенда (выбор режима ВТА/ДТА, COM-порта, адресов ADAM и термопар)."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Конфигурация установки")
        self.resize(480, 380)
        tc_names = get_thermocouple_manager().list_names()

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.cb_mode = QtWidgets.QComboBox()
        self.cb_mode.addItems([m.value for m in StandMode])
        self.cb_mode.setCurrentText(config.mode.value)

        self.le_instrument = QtWidgets.QLineEdit(config.instrument)
        self.le_instrument.setPlaceholderText("не указано")

        self.cb_port = QtWidgets.QComboBox()
        ports = get_serial_ports()
        if config.comport not in ports:
            ports.insert(0, config.comport)
        self.cb_port.addItems(ports)
        self.cb_port.setCurrentText(config.comport)

        self.sb_addr_t1 = QtWidgets.QSpinBox()
        self.sb_addr_t1.setRange(0, 255)
        self.sb_addr_t1.setValue(config.adam4011_t1_address)

        self.sb_addr_t2 = QtWidgets.QSpinBox()
        self.sb_addr_t2.setRange(0, 255)
        self.sb_addr_t2.setValue(config.adam4011_t2_address)

        self.sb_addr_ao = QtWidgets.QSpinBox()
        self.sb_addr_ao.setRange(0, 255)
        self.sb_addr_ao.setValue(config.adam4021_address)

        self.cb_tc1 = QtWidgets.QComboBox()
        self.cb_tc1.addItems(tc_names)
        self.cb_tc1.setCurrentText(config.thermocouple_t1)

        self.cb_tc2 = QtWidgets.QComboBox()
        self.cb_tc2.addItems(tc_names)
        self.cb_tc2.setCurrentText(config.thermocouple_t2)

        self.sb_speed = QtWidgets.QSpinBox()
        self.sb_speed.setRange(-100, 100)
        self.sb_speed.setValue(config.default_speed)

        self.chk_antialias = QtWidgets.QCheckBox(
            "Сглаживание линий графиков (антиалиазинг)"
        )
        self.chk_antialias.setChecked(config.antialias)

        self.chk_test = QtWidgets.QCheckBox("Тестовый режим (эмуляция без приборов)")
        self.chk_test.setChecked(config.is_test_mode)

        form.addRow("Режим стенда (vta / dta):", self.cb_mode)
        form.addRow("Название прибора / установки:", self.le_instrument)
        form.addRow("COM-порт:", self.cb_port)
        form.addRow("Адрес ADAM-4011 (Канал 1):", self.sb_addr_t1)
        form.addRow("Адрес ADAM-4011 (Канал 2, ДТА):", self.sb_addr_t2)
        form.addRow("Адрес ADAM-4021 (ЦАП печи, ВТА):", self.sb_addr_ao)
        form.addRow("Термопара канала 1:", self.cb_tc1)
        form.addRow("Термопара канала 2 (ДТА):", self.cb_tc2)
        form.addRow("Скорость нагрева по умолч. (мВ/с):", self.sb_speed)
        form.addRow("", self.chk_antialias)
        form.addRow("", self.chk_test)
        layout.addLayout(form)

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._apply)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._on_mode_changed(self.cb_mode.currentText())
        self.cb_mode.currentTextChanged.connect(self._on_mode_changed)

    def _on_mode_changed(self, mode: str) -> None:
        is_vta = mode == StandMode.VTA
        self.sb_addr_ao.setEnabled(is_vta)
        self.sb_speed.setEnabled(is_vta)
        self.sb_addr_t2.setEnabled(not is_vta)
        self.cb_tc2.setEnabled(not is_vta)

    def _apply(self) -> None:
        config.mode = StandMode(self.cb_mode.currentText())
        config.instrument = self.le_instrument.text().strip()
        config.comport = self.cb_port.currentText().strip() or "COM1"
        config.adam4011_t1_address = int(self.sb_addr_t1.value())
        config.adam4011_t2_address = int(self.sb_addr_t2.value())
        config.adam4021_address = int(self.sb_addr_ao.value())
        config.thermocouple_t1 = self.cb_tc1.currentText()
        config.thermocouple_t2 = self.cb_tc2.currentText()
        config.default_speed = int(self.sb_speed.value())
        config.antialias = self.chk_antialias.isChecked()
        config.is_test_mode = self.chk_test.isChecked()
        config.update()
        self.accept()


class NewMeasurementDialog(QtWidgets.QDialog):
    """Диалог параметров новой сессии записи измерения (с паспортом SCRAM/ICTAC)."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новое измерение")
        self.resize(460, 380)

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self._save_dir = (
            Path(config.last_save_dir)
            if Path(config.last_save_dir).is_dir()
            else Path.cwd()
        )
        self.le_operator = QtWidgets.QLineEdit(config.operator)
        self.le_sample = QtWidgets.QLineEdit()
        self.le_sample.setPlaceholderText("обязательное поле")

        file_row = QtWidgets.QHBoxLayout()
        self.le_filepath = QtWidgets.QLineEdit()
        self.le_filepath.setPlaceholderText(
            "обязательное поле — укажите путь или нажмите «Обзор»"
        )
        btn_browse = QtWidgets.QPushButton(
            resolve_ui_icon(
                QtGui.QIcon.ThemeIcon.FolderOpen,
                QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon,
            ),
            "Обзор",
        )
        btn_browse.clicked.connect(self._browse_file)
        file_row.addWidget(self.le_filepath, 1)
        file_row.addWidget(btn_browse)

        self.sb_mass = QtWidgets.QDoubleSpinBox()
        self.sb_mass.setRange(0.0, 100000.0)
        self.sb_mass.setDecimals(2)
        self.sb_mass.setSpecialValueText("не указана")
        self.sb_mass.setSuffix(" мг")

        self.le_crucible = QtWidgets.QLineEdit(config.crucible)
        self.le_crucible.setPlaceholderText("например: Pt, Al2O3, кварц")
        self.le_atmosphere = QtWidgets.QLineEdit(config.atmosphere)
        self.le_atmosphere.setPlaceholderText("например: Ar, вакуум, воздух")

        self.chk_cal = QtWidgets.QCheckBox("Применять калибровку температуры")
        self.chk_cal.setChecked(config.calibration_enabled)

        self.cb_cal = QtWidgets.QComboBox()
        self.cb_cal.addItems(get_calibration_manager().list_names())
        if config.last_selected_calibration:
            self.cb_cal.setCurrentText(config.last_selected_calibration)

        self.txt_comment = QtWidgets.QPlainTextEdit()
        self.txt_comment.setMaximumHeight(70)

        form.addRow("Оператор:", self.le_operator)
        form.addRow("Образец *:", self.le_sample)
        form.addRow("Файл .fus *:", file_row)
        form.addRow("Масса образца:", self.sb_mass)
        form.addRow("Тигель:", self.le_crucible)
        form.addRow("Атмосфера:", self.le_atmosphere)
        form.addRow("", self.chk_cal)
        form.addRow("Калибровка:", self.cb_cal)
        form.addRow("Примечание:", self.txt_comment)
        layout.addLayout(form)

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._on_accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _suggest_path(self, sample_text: str) -> Path:
        safe_smp = "".join(
            ch if (ch.isalnum() or ch in (" ", "-", "_")) else "_" for ch in sample_text
        ).strip()
        fname = f"{config.last_save_measurement_index:03d}_{safe_smp or 'sample'}.fus"
        return self._save_dir / fname

    def _browse_file(self) -> None:
        smp = self.le_sample.text().strip() or "sample"
        default_p = self.le_filepath.text().strip() or str(self._suggest_path(smp))
        fname, _ = QtWidgets.QFileDialog.getSaveFileName(  # noqa: PU001 — Qt QFileDialog API returns (path, filter)
            self, "Выбрать файл нового измерения (.fus)", default_p, FUS_EXT_FILTER
        )
        if fname:
            out = Path(fname)
            if out.suffix.lower() != ".fus":
                out = out.with_suffix(".fus")
            self._save_dir = out.parent
            self.le_filepath.setText(str(out))

    def _on_accept(self) -> None:
        if not self.le_sample.text().strip():
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Укажите название образца.")
            return
        if not self.le_filepath.text().strip():
            QtWidgets.QMessageBox.warning(
                self, "Ошибка", "Укажите путь к создаваемому файлу .fus."
            )
            return
        out_p = Path(self.le_filepath.text().strip())
        if out_p.suffix.lower() != ".fus":
            out_p = out_p.with_suffix(".fus")
            self.le_filepath.setText(str(out_p))
        config.last_save_dir = out_p.parent
        config.operator = self.le_operator.text().strip()
        config.crucible = self.le_crucible.text().strip()
        config.atmosphere = self.le_atmosphere.text().strip()
        config.calibration_enabled = self.chk_cal.isChecked()
        if self.chk_cal.isChecked():
            config.last_selected_calibration = self.cb_cal.currentText()
        config.update()
        self.accept()


# Файл измерения (.fus) выбирается обязательно в NewMeasurementDialog
