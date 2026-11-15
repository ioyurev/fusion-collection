from __future__ import annotations

from fusion_common import (
    PiecewisePolynomialSensorModel,
    PolynomialSensorModel,
    resolve_ui_icon,
)
from PySide6 import QtGui, QtWidgets

from fusion_collection.calibration_manager import get_thermocouple_manager


class ThermocoupleEditorDialog(QtWidgets.QDialog):
    """Диалог создания и редактирования пользовательской термопары."""

    def __init__(
        self,
        sensor: PolynomialSensorModel | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Редактор профиля термопары")
        self.resize(520, 440)
        self.result_sensor: PolynomialSensorModel | None = None

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.le_name = QtWidgets.QLineEdit(sensor.name if sensor else "")
        self.le_desc = QtWidgets.QLineEdit(sensor.description if sensor else "")
        self.sb_emf_min = QtWidgets.QDoubleSpinBox()
        self.sb_emf_min.setRange(-100.0, 100.0)
        self.sb_emf_min.setDecimals(2)
        self.sb_emf_min.setValue(sensor.emf_min_mv if sensor else -10.0)

        self.sb_emf_max = QtWidgets.QDoubleSpinBox()
        self.sb_emf_max.setRange(-100.0, 200.0)
        self.sb_emf_max.setDecimals(2)
        self.sb_emf_max.setValue(sensor.emf_max_mv if sensor else 70.0)

        form.addRow("Название термопары:", self.le_name)
        form.addRow("Описание:", self.le_desc)
        form.addRow("Мин. ЭДС для CJC (мВ):", self.sb_emf_min)
        form.addRow("Макс. ЭДС для CJC (мВ):", self.sb_emf_max)
        layout.addLayout(form)

        layout.addWidget(
            QtWidgets.QLabel(
                "Коэффициенты полинома T(E) = c0 + c1·E + c2·E² + ... (от c0 к старшей степени):"
            )
        )
        self.table = QtWidgets.QTableWidget(0, 1)
        self.table.setHorizontalHeaderLabels(["Коэффициент c_i"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        coeffs = sensor.coefficients if sensor else [0.0, 25.0]
        for c_val in coeffs:
            self._append_coeff_row(c_val)

        row_btns = QtWidgets.QHBoxLayout()
        st = QtWidgets.QStyle.StandardPixmap
        ti = QtGui.QIcon.ThemeIcon
        btn_add = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ListAdd, st.SP_FileDialogNewFolder),
            "Добавить степень",
        )
        btn_del = QtWidgets.QPushButton(
            resolve_ui_icon(ti.ListRemove, st.SP_TrashIcon),
            "Удалить последнюю степень",
        )
        btn_add.clicked.connect(lambda: self._append_coeff_row(0.0))
        btn_del.clicked.connect(self._remove_last_row)
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_del)
        layout.addLayout(row_btns)

        box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._on_save)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _append_coeff_row(self, val: float) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setVerticalHeaderItem(row, QtWidgets.QTableWidgetItem(f"c{row}"))
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(repr(float(val))))

    def _remove_last_row(self) -> None:
        if self.table.rowCount() > 1:
            self.table.removeRow(self.table.rowCount() - 1)

    def _on_save(self) -> None:
        name = self.le_name.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Укажите название термопары.")
            return
        coeffs: list[float] = []
        try:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                text = item.text().strip() if item else "0.0"
                coeffs.append(float(text))
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(
                self, "Ошибка", f"Некорректное числовое значение коэффициента: {exc}"
            )
            return

        self.result_sensor = PolynomialSensorModel(
            name=name,
            description=self.le_desc.text().strip(),
            coefficients=coeffs,
            emf_min_mv=float(self.sb_emf_min.value()),
            emf_max_mv=float(self.sb_emf_max.value()),
        )
        self.accept()


class ThermocoupleManagerDialog(QtWidgets.QDialog):
    """Окно управления профилями термопар."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Управление термопарами")
        self.resize(460, 360)
        self.mgr = get_thermocouple_manager()

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
        btn_close = QtWidgets.QPushButton(
            resolve_ui_icon(ti.WindowClose, st.SP_DialogCloseButton), "Закрыть"
        )

        btn_new.clicked.connect(self._create_new)
        btn_edit.clicked.connect(self._edit_selected)
        btn_del.clicked.connect(self._delete_selected)
        btn_close.clicked.connect(self.accept)

        for b in (btn_new, btn_edit, btn_del):
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
        dlg = ThermocoupleEditorDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_sensor:
            self.mgr.save_sensor(dlg.result_sensor)
            self._refresh()

    def _edit_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        first_item, *_ = items
        sensor = self.mgr.load_sensor(first_item.text())
        if isinstance(sensor, PiecewisePolynomialSensorModel):
            segs_info = "\n".join(
                f"  • [{s.emf_min_mv} .. {s.emf_max_mv} мВ]: {len(s.coefficients)} коэфф."
                for s in sensor.segments
            )
            QtWidgets.QMessageBox.information(
                self,
                sensor.name,
                f"{sensor.description}\n\n"
                f"Кусочно-полиномиальная характеристика ГОСТ Р 8.585-2001:\n{segs_info}",
            )
            return
        if not isinstance(sensor, PolynomialSensorModel):
            return
        dlg = ThermocoupleEditorDialog(sensor=sensor, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_sensor:
            self.mgr.save_sensor(dlg.result_sensor)
            self._refresh()

    def _delete_selected(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        first_item, *_ = items
        self.mgr.delete_sensor(first_item.text())
        self._refresh()
