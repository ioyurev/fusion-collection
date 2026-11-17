from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from fusion_collection.config import config

IDLE_MAX_POINTS = 18_000


class LivePlotPanel(QtWidgets.QWidget):
    """Единая многоосевая панель графика для отображения всех кривых ВТА и ДТА."""

    def __init__(
        self,
        mode: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.recording_active: bool = False
        self._t0: float | None = None
        self.cb_xaxis: QtWidgets.QComboBox | None = None

        self._cap: int = 2048
        self._size: int = 0
        self._time_arr = np.empty(self._cap, dtype=float)
        self._temp_arr = np.empty(self._cap, dtype=float)
        self._emf1_arr = np.empty(self._cap, dtype=float)
        self._emf2_arr = np.empty(self._cap, dtype=float)
        self._dta_arr = np.empty(self._cap, dtype=float)
        self._out_arr = np.empty(self._cap, dtype=float)

        self.layout_box = QtWidgets.QVBoxLayout(self)
        self.layout_box.setContentsMargins(0, 0, 0, 0)
        self.layout_box.setSpacing(4)
        self._setup_single_panel()

    def _setup_single_panel(self) -> None:
        pg.setConfigOptions(antialias=bool(config.antialias))
        ctrl_row = QtWidgets.QHBoxLayout()
        self.cb_show_temp = QtWidgets.QCheckBox("Температура (°C)")
        self.cb_show_temp.setChecked(True)
        self.cb_show_emf = QtWidgets.QCheckBox(
            "ЭДС (мВ)" if self.mode == "vta" else "ЭДС T1 / T2 (мВ)"
        )
        self.cb_show_emf.setChecked(True)
        ctrl_row.addWidget(self.cb_show_temp)
        ctrl_row.addWidget(self.cb_show_emf)

        if self.mode == "vta":
            self.cb_show_extra = QtWidgets.QCheckBox("Выход печи (В)")
            self.cb_show_extra.setChecked(True)
            ctrl_row.addWidget(self.cb_show_extra)
        else:
            self.cb_show_extra = QtWidgets.QCheckBox("ДТА (мВ)")
            self.cb_show_extra.setChecked(True)
            ctrl_row.addWidget(self.cb_show_extra)
            ctrl_row.addWidget(QtWidgets.QLabel("Ось X:"))
            self.cb_xaxis = QtWidgets.QComboBox()
            self.cb_xaxis.addItems(["Время, мин", "Температура, °C"])
            self.cb_xaxis.currentIndexChanged.connect(self._on_xaxis_changed)
            ctrl_row.addWidget(self.cb_xaxis)

        self.cb_grid = QtWidgets.QCheckBox("Сетка")
        self.cb_grid.setChecked(False)
        ctrl_row.addWidget(self.cb_grid)
        ctrl_row.addStretch()
        self.lbl_coords = QtWidgets.QLabel("Курсор: —")
        self.lbl_coords.setStyleSheet("font-family: Consolas, monospace;")
        ctrl_row.addWidget(self.lbl_coords)
        self.layout_box.addLayout(ctrl_row)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=False, y=False, alpha=0.3)
        self.cb_grid.toggled.connect(
            lambda checked: self.plot_widget.showGrid(x=checked, y=checked, alpha=0.3)
        )
        self.layout_box.addWidget(self.plot_widget, 1)

        p_item = self.plot_widget.getPlotItem()
        assert p_item is not None  # noqa: S101 — сужение типа Optional для mypy
        self.main_plot = p_item
        self.main_plot.setLabel("bottom", "Время, мин")

        # Правая ось Y1 (ЭДС, мВ)
        self.axis_emf = pg.AxisItem("right")
        self.vb_emf = pg.ViewBox()
        self.main_plot.layout.addItem(self.axis_emf, 2, 3)
        self.main_plot.scene().addItem(self.vb_emf)
        self.axis_emf.linkToView(self.vb_emf)
        self.vb_emf.setXLink(self.main_plot)
        self.axis_emf.setLabel("ЭДС, мВ", color="#f1c40f")

        # Правая ось Y2 (Выход печи, В или Температура в ДТА)
        self.axis_aux = pg.AxisItem("right")
        self.vb_aux = pg.ViewBox()
        self.main_plot.layout.addItem(self.axis_aux, 2, 4)
        self.main_plot.scene().addItem(self.vb_aux)
        self.axis_aux.linkToView(self.vb_aux)
        self.vb_aux.setXLink(self.main_plot)

        if self.mode == "vta":
            self.main_plot.setLabel("left", "Температура, °C", color="#FD700D")
            self.axis_aux.setLabel("Выход печи, В", color="#0D9AFD")

            self.curve_temp = pg.PlotDataItem(
                pen=pg.mkPen("#FD700D", width=2), name="T (°C)"
            )
            self.curve_emf1 = pg.PlotDataItem(
                pen=pg.mkPen("#4BD0FD", width=1.5), name="ЭДС (мВ)"
            )
            self.curve_out = pg.PlotDataItem(
                pen=pg.mkPen("#0D9AFD", width=1.5), name="Выход (В)"
            )
            for c in (self.curve_temp, self.curve_emf1, self.curve_out):
                c.setDownsampling(auto=True, method="peak")
                c.setClipToView(True)

            self.main_plot.addItem(self.curve_temp)
            self.vb_emf.addItem(self.curve_emf1)
            self.vb_aux.addItem(self.curve_out)
        else:
            self.main_plot.setLabel("left", "ДТА, мВ", color="#0D9AFD")
            self.axis_aux.setLabel("Температура, °C", color="#FD700D")

            self.curve_dta = pg.PlotDataItem(
                pen=pg.mkPen("#0D9AFD", width=2), name="ДТА (мВ)"
            )
            self.curve_temp = pg.PlotDataItem(
                pen=pg.mkPen("#FD700D", width=1.8), name="T образца (°C)"
            )
            self.curve_emf1 = pg.PlotDataItem(
                pen=pg.mkPen("#4BD0FD", width=1.2), name="ЭДС T1 (мВ)"
            )
            self.curve_emf2 = pg.PlotDataItem(
                pen=pg.mkPen("#2ECC71", width=1.2), name="ЭДС T2 (мВ)"
            )
            for c in (
                self.curve_dta,
                self.curve_temp,
                self.curve_emf1,
                self.curve_emf2,
            ):
                c.setDownsampling(auto=True, method="peak")
                c.setClipToView(True)

            self.main_plot.addItem(self.curve_dta)
            self.vb_aux.addItem(self.curve_temp)
            self.vb_emf.addItem(self.curve_emf1)
            self.vb_emf.addItem(self.curve_emf2)

        self.main_plot.vb.sigResized.connect(self._sync_viewboxes)
        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.cb_show_temp.toggled.connect(self._update_visibility)
        self.cb_show_emf.toggled.connect(self._update_visibility)
        self.cb_show_extra.toggled.connect(self._update_visibility)

        style_hints = QtGui.QGuiApplication.styleHints()
        style_hints.colorSchemeChanged.connect(self._apply_color_scheme)
        self._apply_color_scheme(style_hints.colorScheme())
        self.apply_antialias(config.antialias)
        self._sync_viewboxes()

    def _on_mouse_moved(self, scene_pos: QtCore.QPointF) -> None:
        if not self.main_plot.vb.sceneBoundingRect().contains(scene_pos):
            return
        p_main = self.main_plot.vb.mapSceneToView(scene_pos)
        p_emf = self.vb_emf.mapSceneToView(scene_pos)
        p_aux = self.vb_aux.mapSceneToView(scene_pos)
        if self.mode == "vta":
            self.lbl_coords.setText(
                f"t={p_main.x():.2f} мин | T={p_main.y():.1f} °C | "
                f"E={p_emf.y():.3f} мВ | U={p_aux.y():.3f} В"
            )
        else:
            use_temp_x = self.cb_xaxis is not None and self.cb_xaxis.currentIndex() == 1
            x_lbl = (
                f"T={p_main.x():.1f} °C" if use_temp_x else f"t={p_main.x():.2f} мин"
            )
            self.lbl_coords.setText(
                f"{x_lbl} | ДТА={p_main.y():.3f} мВ | "
                f"T={p_aux.y():.1f} °C | E={p_emf.y():.3f} мВ"
            )

    def apply_antialias(self, enabled: bool) -> None:
        flag = bool(enabled)
        pg.setConfigOptions(antialias=flag)
        curves = (
            (self.curve_temp, self.curve_emf1, self.curve_out)
            if self.mode == "vta"
            else (
                self.curve_dta,
                self.curve_temp,
                self.curve_emf1,
                self.curve_emf2,
            )
        )
        for c in curves:
            c.opts["antialias"] = flag
            if c.xData is not None and c.yData is not None:
                c.setData(c.xData, c.yData, antialias=flag)

    def _apply_color_scheme(self, scheme: QtCore.Qt.ColorScheme) -> None:
        is_dark = scheme == QtCore.Qt.ColorScheme.Dark
        bg_hex = "#0F172A" if is_dark else "#FFFFFF"
        fg_hex = "#CBD5E1" if is_dark else "#1E293B"
        c_temp = "#FF7A18" if is_dark else "#D9460F"
        c_aux = "#38BDF8" if is_dark else "#0284C7"
        c_emf1 = "#4BD0FD" if is_dark else "#0D9488"
        c_emf2 = "#4ADE80" if is_dark else "#16A34A"

        self.plot_widget.setBackground(bg_hex)
        for ax_name in ("bottom", "left"):
            ax_item = self.main_plot.getAxis(ax_name)
            ax_item.setPen(fg_hex)
            ax_item.setTextPen(fg_hex)
        for extra_ax in (self.axis_emf, self.axis_aux):
            extra_ax.setPen(fg_hex)
            extra_ax.setTextPen(fg_hex)

        self.axis_emf.setLabel("ЭДС, мВ", color=c_emf1)
        self.curve_temp.setPen(pg.mkPen(c_temp, width=2))
        self.curve_emf1.setPen(pg.mkPen(c_emf1, width=1.5))
        if self.mode == "vta":
            self.main_plot.setLabel("left", "Температура, °C", color=c_temp)
            self.axis_aux.setLabel("Выход печи, В", color=c_aux)
            self.curve_out.setPen(pg.mkPen(c_aux, width=1.5))
        else:
            self.main_plot.setLabel("left", "ДТА, мВ", color=c_aux)
            self.axis_aux.setLabel("Температура, °C", color=c_temp)
            self.curve_dta.setPen(pg.mkPen(c_aux, width=2))
            self.curve_emf2.setPen(pg.mkPen(c_emf2, width=1.2))

    def _sync_viewboxes(self) -> None:
        rect = self.main_plot.vb.sceneBoundingRect()
        self.vb_emf.setGeometry(rect)
        self.vb_aux.setGeometry(rect)
        self.vb_emf.linkedViewChanged(self.main_plot.vb, self.vb_emf.XAxis)
        self.vb_aux.linkedViewChanged(self.main_plot.vb, self.vb_aux.XAxis)

    def _update_visibility(self) -> None:
        show_t = self.cb_show_temp.isChecked()
        show_e = self.cb_show_emf.isChecked()
        show_x = self.cb_show_extra.isChecked()

        self.curve_temp.setVisible(show_t)
        self.curve_emf1.setVisible(show_e)
        self.axis_emf.setVisible(show_e)

        if self.mode == "vta":
            self.curve_out.setVisible(show_x)
            self.axis_aux.setVisible(show_x)
            primary_vis = show_t
        else:
            self.curve_emf2.setVisible(show_e)
            self.curve_dta.setVisible(show_x)
            self.axis_aux.setVisible(show_t)
            primary_vis = show_x

        if primary_vis:
            self.main_plot.enableAutoRange(axis="x", enable=True)
        self._refresh_curves()

    def _sync_x_range_if_primary_hidden(self, x_arr: np.ndarray) -> None:
        if len(x_arr) == 0:
            return
        primary_vis = (
            self.cb_show_temp.isChecked()
            if self.mode == "vta"
            else self.cb_show_extra.isChecked()
        )
        any_vis = (
            self.cb_show_temp.isChecked()
            or self.cb_show_emf.isChecked()
            or self.cb_show_extra.isChecked()
        )
        if not primary_vis and any_vis:
            x_min = float(np.min(x_arr))
            x_max = float(np.max(x_arr))
            span = max(1e-6, x_max - x_min)
            self.main_plot.setXRange(
                x_min - span * 0.02,
                x_max + span * 0.02,
                padding=0.0,
            )

    def set_recording_active(self, active: bool) -> None:
        self.recording_active = active

    def clear(self) -> None:
        self._t0 = None
        self._size = 0
        self._refresh_curves()

    def _ensure_capacity(self) -> None:
        if self._size < self._cap:
            return
        new_cap = self._cap * 2
        for attr in (
            "_time_arr",
            "_temp_arr",
            "_emf1_arr",
            "_emf2_arr",
            "_dta_arr",
            "_out_arr",
        ):
            old_a = getattr(self, attr)
            new_a = np.empty(new_cap, dtype=float)
            new_a[: self._size] = old_a[: self._size]
            setattr(self, attr, new_a)
        self._cap = new_cap

    def append_point(
        self,
        timestamp: float,
        emf_1_mv: float,
        temp_1_c: float,
        emf_2_mv: float = 0.0,
        heater_output_v: float = 0.0,
    ) -> None:
        if not self.recording_active and self._size >= IDLE_MAX_POINTS:
            self.clear()

        if self._t0 is None:
            self._t0 = timestamp
        rel_t = max(0.0, (timestamp - self._t0) / 60.0)

        self._ensure_capacity()
        idx = self._size
        self._time_arr[idx] = rel_t
        self._temp_arr[idx] = temp_1_c
        self._emf1_arr[idx] = emf_1_mv
        if self.mode == "vta":
            self._out_arr[idx] = heater_output_v
        else:
            self._emf2_arr[idx] = emf_2_mv
            self._dta_arr[idx] = emf_1_mv - emf_2_mv
        self._size = idx + 1

        self._refresh_curves()

    def _on_xaxis_changed(self, _index: int = 0) -> None:
        use_temp_x = self.cb_xaxis is not None and self.cb_xaxis.currentIndex() == 1
        self.main_plot.setLabel(
            "bottom", "Температура образца, °C" if use_temp_x else "Время, мин"
        )
        self._refresh_curves()

    def _refresh_curves(self) -> None:
        show_t = self.cb_show_temp.isChecked()
        show_e = self.cb_show_emf.isChecked()
        show_x = self.cb_show_extra.isChecked()
        if not (show_t or show_e or show_x):
            return

        n = self._size
        t_arr = self._time_arr[:n]
        if self.mode == "vta":
            if show_t:
                self.curve_temp.setData(t_arr, self._temp_arr[:n], skipFiniteCheck=True)
            if show_e:
                self.curve_emf1.setData(t_arr, self._emf1_arr[:n], skipFiniteCheck=True)
            if show_x:
                self.curve_out.setData(t_arr, self._out_arr[:n], skipFiniteCheck=True)
            self._sync_x_range_if_primary_hidden(t_arr)
            return

        use_temp_x = self.cb_xaxis is not None and self.cb_xaxis.currentIndex() == 1
        temp_arr = self._temp_arr[:n]
        x_arr = temp_arr if use_temp_x else t_arr

        if show_x:
            self.curve_dta.setData(x_arr, self._dta_arr[:n], skipFiniteCheck=True)
        if show_t:
            self.curve_temp.setData(x_arr, temp_arr, skipFiniteCheck=True)
        if show_e:
            self.curve_emf1.setData(x_arr, self._emf1_arr[:n], skipFiniteCheck=True)
            self.curve_emf2.setData(x_arr, self._emf2_arr[:n], skipFiniteCheck=True)
        self._sync_x_range_if_primary_hidden(x_arr)
