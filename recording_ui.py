# -*- coding: utf-8 -*-
"""recording_ui.py —— v52 录屏界面（设计稿 K-recording），纯 PySide6。

包含四块：
  * RecordPanel       顶部「截图 / 录屏」Tab 里的录屏页：左列三种方式 + 声音
                      与画面开关，右列录制设置 + 帮助，底部「开始录屏」；
  * RecordControlBar  录制中悬浮控制条：计时 / 电平 / 暂停 / 停止 / 可改热键；
  * RecordBorder      录制中屏幕边缘红框（框选 / 全屏共用）；
  * AudioChoiceDialog 兼容保留（V52.1 起录制前不再弹窗，音频在面板预设）。

只依赖 PySide6 / i18n / ui_theme / recording_settings，不反向 import snap.py，
便于离屏自测。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from i18n import LANG, t
from recording_settings import (
    AUDIO_SAVE_KEYS,
    EXPORT_FORMATS,
    FPS_CHOICES,
    PIP_POSITIONS,
    PIP_SIZES,
    load_audio_flags,
    load_audio_mode,
    load_audio_save,
    load_camera_flags,
    load_export_format,
    load_fps,
    load_rec_hotkey,
    load_rec_mode,
    load_save_dir,
    save_audio_flags,
    save_audio_mode,
    save_audio_save,
    save_camera_flags,
    save_export_format,
    save_fps,
    save_rec_mode,
    save_save_dir,
)
from ui_theme import (
    CREAM,
    FONT_QSS,
    INK,
    INK2,
    INK3,
    LINE,
    ORANGE,
    SOFT,
    Card,
    PanelRow,
    RowPicker,
    group_title,
    icon,
    label,
)

REC_MODES = ("rect", "window", "fullscreen")
REC_MODE_ICONS = {"rect": "region", "window": "window", "fullscreen": "fullscreen"}
REC_MODE_SHORT = {"rect": "框选录屏", "window": "窗口录屏", "fullscreen": "全屏录屏"}
REC_MODE_DESC = {
    "rect": "拖动选取任意区域 · 松开开始",
    "window": "悬停高亮 · 单击录制该窗口",
    "fullscreen": "整块桌面 · 多屏合屏",
}

MIX_LABEL = "混合成一条音轨（推荐）"
TRACKS_LABEL = "保留独立音轨（播放器可切换）"


# ---------------------------------------------------------------------------
# 通用行：开关 / 下拉 / 值
# ---------------------------------------------------------------------------
class SwitchRow(QWidget):
    """一行：左侧标题+说明，右侧一个可点击的橙色开关。"""

    toggled = Signal(bool)

    def __init__(self, title: str, desc: str = "", on: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on = bool(on)
        self._title, self._desc = title, desc
        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 3, 12, 3)
        lay.setSpacing(8)
        col = QVBoxLayout()
        col.setSpacing(0)
        self._title_lb = QLabel(title, self)
        self._title_lb.setStyleSheet(
            f"color:{INK};font-size:12.5px;font-weight:600;background:transparent;{FONT_QSS}"
        )
        self._desc_lb = QLabel(desc, self)
        self._desc_lb.setStyleSheet(
            f"color:{INK3};font-size:10.5px;background:transparent;{FONT_QSS}"
        )
        self._desc_lb.setVisible(bool(desc))
        col.addWidget(self._title_lb)
        col.addWidget(self._desc_lb)
        lay.addLayout(col, 1)
        self._sw = _Switch(self._on, self)
        self._sw.setFixedSize(38, 21)
        lay.addWidget(self._sw, 0, Qt.AlignVCenter)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self.set_on(not self._on)
            self.toggled.emit(self._on)
        super().mousePressEvent(ev)

    def is_on(self) -> bool:
        return self._on

    def set_on(self, on: bool) -> None:
        self._on = bool(on)
        self._sw.set_on(self._on)

    def set_texts(self, title: str, desc: str = "") -> None:
        self._title, self._desc = title, desc
        self._title_lb.setText(title)
        self._desc_lb.setText(desc)
        self._desc_lb.setVisible(bool(desc))


class _Switch(QWidget):
    def __init__(self, on: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on = bool(on)

    def set_on(self, on: bool) -> None:
        self._on = bool(on)
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ORANGE if self._on else "#d9d0c5"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 4
        x = r.right() - d - 2 if self._on else r.left() + 2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, r.top() + 2, d, d))
        p.end()


class ValueRow(QWidget):
    """一行：左侧标题+说明，右侧一个下拉框。"""

    def __init__(self, title: str, desc: str, items: list[str], current: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 3, 12, 3)
        lay.setSpacing(8)
        col = QVBoxLayout()
        col.setSpacing(0)
        self._title_lb = QLabel(title, self)
        self._title_lb.setStyleSheet(
            f"color:{INK};font-size:12.5px;font-weight:600;background:transparent;{FONT_QSS}"
        )
        self._desc_lb = QLabel(desc, self)
        self._desc_lb.setStyleSheet(
            f"color:{INK3};font-size:10.5px;background:transparent;{FONT_QSS}"
        )
        col.addWidget(self._title_lb)
        col.addWidget(self._desc_lb)
        lay.addLayout(col, 1)
        self.combo = QComboBox(self)
        self.combo.addItems(items)
        if current in items:
            self.combo.setCurrentText(current)
        self.combo.setFixedWidth(128)
        self.combo.setStyleSheet(
            f"QComboBox{{border:1px solid {LINE};border-radius:8px;padding:4px 8px;"
            f"background:#ffffff;color:{INK};font-size:11.5px;{FONT_QSS}}}"
        )
        lay.addWidget(self.combo, 0, Qt.AlignVCenter)

    def set_texts(self, title: str, desc: str) -> None:
        self._title_lb.setText(title)
        self._desc_lb.setText(desc)

    def current_text(self) -> str:
        return self.combo.currentText()


# ---------------------------------------------------------------------------
# 录屏页
# ---------------------------------------------------------------------------
class RecordPanel(QWidget):
    """录屏 Tab 的内容页：布局仿 K 稿 k1.html，配色沿用方案 E。"""

    start_requested = Signal(str)     # 请求开始录屏，携带 rect/window/fullscreen
    default_mode_changed = Signal(str)
    help_requested = Signal()
    about_requested = Signal()
    quit_requested = Signal()
    dir_requested = Signal()
    hotkey_requested = Signal()      # V52.1：点击「录屏热键」行改键

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.card = Card(self, bg=CREAM, border=LINE)
        outer.addWidget(self.card)
        root = QVBoxLayout(self.card)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(3)

        self._rows: dict[str, PanelRow] = {}
        self._pickers: dict[str, RowPicker] = {}
        self._rec_mode = load_rec_mode()

        # 标题 + 副标题 + 退出（与截图页一致）
        head = QHBoxLayout()
        head.setContentsMargins(10, 4, 10, 6)
        self._title = QLabel("", self.card)
        self._title.setStyleSheet(
            f"color:{INK};font-size:13.5px;font-weight:800;{FONT_QSS}"
        )
        head.addWidget(self._title, 1)
        self._sub = QLabel("", self.card)
        self._sub.setStyleSheet(f"color:{INK3};font-size:11px;{FONT_QSS}")
        head.addWidget(self._sub, 1)
        self._btn_quit = QPushButton("", self.card)
        self._btn_quit.setObjectName("recQuit")
        self._btn_quit.setFixedHeight(26)
        self._btn_quit.setCursor(Qt.PointingHandCursor)
        self._btn_quit.setStyleSheet(
            f"QPushButton{{border:1px solid {LINE};border-radius:13px;padding:0 12px;"
            f"color:{INK2};font-size:11px;background:#ffffff;{FONT_QSS}}}"
        )
        self._btn_quit.clicked.connect(lambda _=False: self.quit_requested.emit())
        head.addWidget(self._btn_quit, 0, Qt.AlignVCenter)
        root.addLayout(head)
        # V52.1：按用户要求去掉录屏页头部区块（标题 / 副标题 / 退出）。
        # 控件保留以兼容自测与托盘逻辑，仅从界面上隐藏。
        for _w in (self._title, self._sub, self._btn_quit):
            _w.hide()

        sep = QWidget(self.card)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{LINE};")
        root.addWidget(sep)

        # 两列
        body = QHBoxLayout()
        body.setContentsMargins(0, 2, 0, 0)
        body.setSpacing(0)
        left = QVBoxLayout()
        left.setSpacing(1)
        right = QVBoxLayout()
        right.setSpacing(1)
        body.addLayout(left, 1)
        vline = QWidget(self.card)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"background:{LINE};")
        body.addWidget(vline)
        body.addLayout(right, 1)
        root.addLayout(body)

        self._lbl_mode = group_title("", self.card)
        self._lbl_pick = group_title("", self.card)
        self._lbl_pick.setFixedWidth(78)
        self._lbl_pick.setAlignment(Qt.AlignCenter)
        holder = QWidget(self.card)
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(12, 6, 12, 2)
        hl.addWidget(self._lbl_mode)
        hl.addStretch(1)
        hl.addWidget(self._lbl_pick)
        left.addWidget(holder)

        def add_mode(mode: str) -> None:
            row = PanelRow(REC_MODE_ICONS[mode], REC_MODE_SHORT[mode],
                           REC_MODE_DESC[mode], "", self.card)
            row.clicked.connect(lambda _=False, m=mode: self.start_requested.emit(m))
            row.setCursor(Qt.PointingHandCursor)
            picker = row.enable_picker()
            picker.clicked.connect(
                lambda _=False, m=mode: self._pick_mode(m))
            left.addWidget(row)
            self._rows[f"mode_{mode}"] = row
            self._pickers[mode] = picker

        for mode in REC_MODES:
            add_mode(mode)

        self._lbl_av = group_title("", self.card)
        left.addWidget(self._lbl_av)
        system, mic, cursor = load_audio_flags()
        self._sw_system = SwitchRow("系统声音", "录电脑播放的声音", system, self.card)
        self._sw_mic = SwitchRow("麦克风", "录你说话的声音", mic, self.card)
        self._sw_cursor = SwitchRow("录制鼠标指针", "视频里显示光标位置", cursor, self.card)
        left.addWidget(self._sw_system)
        left.addWidget(self._sw_mic)
        left.addWidget(self._sw_cursor)

        camera_on, pip_pos, pip_size = load_camera_flags()
        self._sw_camera = SwitchRow("摄像头画中画", "把摄像头画面贴到角落", camera_on, self.card)
        left.addWidget(self._sw_camera)
        self._pip_pos = ValueRow("画中画位置", "角落位置", list(PIP_POSITIONS), pip_pos, self.card)
        self._pip_size = ValueRow("画中画大小", "占画面宽度比例",
                                  [f"{s}%" for s in PIP_SIZES], f"{pip_size}%", self.card)
        left.addWidget(self._pip_pos)
        left.addWidget(self._pip_size)
        left.addStretch(1)

        # 右列：录制设置 + 帮助
        self._lbl_set = group_title("", self.card)
        right.addWidget(self._lbl_set)
        self._row_fps = ValueRow("画面帧率", "越高越流畅 · 文件也越大",
                                 [f"{f} fps" for f in FPS_CHOICES],
                                 f"{load_fps()} fps", self.card)
        right.addWidget(self._row_fps)
        audio_save_labels = {
            "embed": "整合到视频", "split": "分开保存 WAV", "both": "两者都要",
        }
        self._row_audio_save = ValueRow("音频保存", "录制完成的音频怎么存",
                                        list(audio_save_labels.values()),
                                        audio_save_labels.get(load_audio_save(), "整合到视频"),
                                        self.card)
        right.addWidget(self._row_audio_save)
        self._row_format = ValueRow("导出格式", "GIF 无声 · 体积更小",
                                    list(EXPORT_FORMATS), load_export_format(), self.card)
        right.addWidget(self._row_format)
        self._row_dir = PanelRow("folder", "保存位置", "录屏_日期_时间.mp4", "", self.card)
        self._row_dir.clicked.connect(lambda _=False: self.dir_requested.emit())
        self._rows["dir"] = self._row_dir
        right.addWidget(self._row_dir)
        self._row_hotkey = PanelRow("key", "录屏热键", "点击修改，立即生效", "", self.card)
        self._row_hotkey.setCursor(Qt.PointingHandCursor)
        self._row_hotkey.clicked.connect(lambda _=False: self.hotkey_requested.emit())
        self._rows["hotkey"] = self._row_hotkey
        right.addWidget(self._row_hotkey)

        self._lbl_help = group_title("", self.card)
        right.addWidget(self._lbl_help)
        help_row = PanelRow("help", "使用说明", "含录屏操作文档", "", self.card)
        help_row.clicked.connect(lambda _=False: self.help_requested.emit())
        about_row = PanelRow("smile", "关于", "版本信息 · 联系邮箱", "", self.card)
        about_row.clicked.connect(lambda _=False: self.about_requested.emit())
        right.addWidget(help_row)
        right.addWidget(about_row)
        self._rows["help"] = help_row
        self._rows["about"] = about_row
        right.addStretch(1)

        # 底部开始录屏按钮
        self._btn_start = QPushButton("", self.card)
        self._btn_start.setObjectName("recStart")
        self._btn_start.setFixedHeight(40)
        self._btn_start.setCursor(Qt.PointingHandCursor)
        self._btn_start.setStyleSheet(
            f"QPushButton{{background:{ORANGE};border:none;border-radius:20px;"
            f"color:#ffffff;font-size:14px;font-weight:700;{FONT_QSS}}}"
            "QPushButton:hover{background:#e9680c;}"
        )
        self._btn_start.clicked.connect(
            lambda _=False: self.start_requested.emit(self._rec_mode))
        root.addWidget(self._btn_start)

        self.set_rec_mode(self._rec_mode)
        self.retranslate_ui()

    # ---- 交互 ----
    def _pick_mode(self, mode: str) -> None:
        self.set_rec_mode(mode)
        save_rec_mode(mode)
        self.default_mode_changed.emit(mode)

    def set_rec_mode(self, mode: str) -> None:
        if mode not in REC_MODES:
            mode = "rect"
        self._rec_mode = mode
        for m, row in self._rows.items():
            if m.startswith("mode_"):
                row.set_highlight(m == f"mode_{mode}")
        for m, picker in self._pickers.items():
            picker.set_selected(m == mode)

    def rec_mode(self) -> str:
        return self._rec_mode

    def collect_settings(self) -> dict:
        """把当前界面设置收集成字典，供启动录制使用；同时写盘。"""
        fps = int(self._row_fps.current_text().split()[0])
        save_fps(fps)
        inv_labels = {v: k for k, v in {
            "embed": "整合到视频", "split": "分开保存 WAV", "both": "两者都要",
        }.items()}
        audio_save = inv_labels.get(self._row_audio_save.current_text(), "embed")
        save_audio_save(audio_save)
        export_format = self._row_format.current_text()
        save_export_format(export_format)
        system, mic, cursor = (self._sw_system.is_on(), self._sw_mic.is_on(),
                               self._sw_cursor.is_on())
        save_audio_flags(system, mic, cursor)
        camera_on = self._sw_camera.is_on()
        pip_pos = self._pip_pos.current_text()
        pip_size = int(self._pip_size.current_text().rstrip("%"))
        save_camera_flags(camera_on, pip_pos, pip_size)
        if camera_on:
            from recording_settings import PIP_POSITIONS as PPOS
            if pip_pos not in PPOS:
                pip_pos = PPOS[-1]
        return {
            "mode": self._rec_mode,
            "fps": fps,
            "system_audio": system,
            "mic": mic,
            "cursor": cursor,
            "camera": camera_on,
            "pip_pos": pip_pos,
            "pip_size": pip_size,
            "audio_save": audio_save,
            "audio_mode": load_audio_mode(),
            "export_format": export_format,
            "save_dir": load_save_dir(),
        }

    def set_dir_text(self, path: str) -> None:
        self._row_dir.set_texts(t("保存位置"), str(path), "")

    def set_hotkey_label(self, label: str) -> None:
        """V52.1：录屏热键改键后刷新行尾与开始按钮提示。"""
        self._hotkey_label = label
        self._rows["hotkey"].set_texts(t("录屏热键"), t("点击修改，立即生效"), label)
        self._btn_start.setText(t("开始录屏") + "   " + label)

    def hotkey_label(self) -> str:
        return getattr(self, "_hotkey_label", "F9")

    def retranslate_ui(self) -> None:
        self._title.setText(t("录屏"))
        self._sub.setText(t("顶部切换「截图 / 录屏」 · 三种方式沿用同一套分栏"))
        self._btn_quit.setText(t("⇥ 退出"))
        self._lbl_mode.setText(t("录屏方式"))
        self._lbl_pick.setText(t("默认方式"))
        for mode in REC_MODES:
            self._rows[f"mode_{mode}"].set_texts(
                t(REC_MODE_SHORT[mode]), t(REC_MODE_DESC[mode]), "")
            self._pickers[mode].setText(t("默认"))
        self._lbl_av.setText(t("声音与画面"))
        self._sw_system.set_texts(t("系统声音"), t("录电脑播放的声音"))
        self._sw_mic.set_texts(t("麦克风"), t("录你说话的声音"))
        self._sw_cursor.set_texts(t("录制鼠标指针"), t("视频里显示光标位置"))
        self._sw_camera.set_texts(t("摄像头画中画"), t("把摄像头画面贴到角落"))
        self._pip_pos.set_texts(t("画中画位置"), t("角落位置"))
        self._pip_size.set_texts(t("画中画大小"), t("占画面宽度比例"))
        self._lbl_set.setText(t("录制设置"))
        self._row_fps.set_texts(t("画面帧率"), t("越高越流畅 · 文件也越大"))
        self._row_audio_save.set_texts(t("音频保存"), t("录制完成的音频怎么存"))
        self._row_format.set_texts(t("导出格式"), t("GIF 无声 · 体积更小"))
        self._row_dir.set_texts(t("保存位置"), str(load_save_dir()), "")
        self.set_hotkey_label(getattr(self, "_hotkey_label", load_rec_hotkey().label()))
        self._lbl_help.setText(t("帮助"))
        self._rows["help"].set_texts(t("使用说明"), t("含录屏操作文档"), "")
        self._rows["about"].set_texts(t("关于"), t("版本信息 · 联系邮箱"), "")
        self.adjustSize()


# ---------------------------------------------------------------------------
# 录制中悬浮控制条
# ---------------------------------------------------------------------------
class RecordControlBar(QWidget):
    """录制中悬浮条：红点 + 计时 + 电平 + 暂停 + 停止 + 热键提示。"""

    pause_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._start = time.monotonic()
        self._paused = False
        self._paused_at = 0.0
        self._levels: dict[str, float] = {}
        self._build()
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(200)

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 8)
        root.setSpacing(10)
        self._dot = QLabel("●", self)
        self._dot.setStyleSheet("color:#e5484d;font-size:16px;")
        root.addWidget(self._dot)
        self._time = QLabel("00:00", self)
        self._time.setStyleSheet(
            f"color:#ffffff;font-size:15px;font-weight:700;font-family:Consolas;{FONT_QSS}"
        )
        root.addWidget(self._time)
        self._sep1 = _vline(self)
        root.addWidget(self._sep1)
        self._level = _LevelBar(self)
        self._level.setFixedSize(64, 14)
        root.addWidget(self._level)
        self._audio_lbl = QLabel("", self)
        self._audio_lbl.setStyleSheet(f"color:#cfd2d6;font-size:11px;{FONT_QSS}")
        root.addWidget(self._audio_lbl)
        self._sep2 = _vline(self)
        root.addWidget(self._sep2)
        self._btn_pause = _MiniBtn("pause", self)
        self._btn_pause.clicked.connect(lambda _=False: self.pause_clicked.emit())
        root.addWidget(self._btn_pause)
        self._btn_stop = _MiniBtn("stop", self)
        self._btn_stop.clicked.connect(lambda _=False: self.stop_clicked.emit())
        root.addWidget(self._btn_stop)
        self._hotkey_label = "F9"
        self._hint = QLabel(self._hotkey_label + " " + t("停止"), self)
        self._hint.setStyleSheet(f"color:#cfd2d6;font-size:11px;{FONT_QSS}")
        root.addWidget(self._hint)
        self.setStyleSheet(
            "QWidget#recBar{background:#23272e;border-radius:16px;}"
        )
        self.setObjectName("recBar")

    def set_hotkey_label(self, label: str) -> None:
        """V52.1：悬浮条停止提示跟随可改的录屏热键。"""
        self._hotkey_label = label
        if self._paused:
            self._hint.setText(t("已暂停 · {hk} 继续", hk=label))
        else:
            self._hint.setText(label + " " + t("停止"))

    def set_audio_labels(self, labels: list[str]) -> None:
        self._audio_lbl.setText(" · ".join(labels))

    def update_levels(self, levels: dict[str, float]) -> None:
        self._levels = dict(levels)
        peak = max(levels.values()) if levels else 0.0
        self._level.set_level(peak)

    def set_paused(self, paused: bool) -> None:
        if paused == self._paused:
            return
        self._paused = paused
        if paused:
            self._paused_at = time.monotonic()
            self._dot.setStyleSheet("color:#f5a524;font-size:16px;")
            self._hint.setText(t("已暂停 · {hk} 继续", hk=self._hotkey_label))
        else:
            self._start += time.monotonic() - self._paused_at
            self._dot.setStyleSheet("color:#e5484d;font-size:16px;")
            self._hint.setText(self._hotkey_label + " " + t("停止"))

    def _tick(self) -> None:
        now = self._paused_at if self._paused else time.monotonic()
        secs = int(max(0, now - self._start))
        mm, ss = divmod(secs, 60)
        self._time.setText(f"{mm:02d}:{ss:02d}")
        if self._paused:
            self._level.set_level(0.0)
        else:
            peak = max(self._levels.values()) if self._levels else 0.0
            self._level.set_level(peak)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#23272e"))
        p.drawRoundedRect(QRectF(self.rect()), 16, 16)
        p.end()


def _vline(parent: QWidget) -> QWidget:
    w = QWidget(parent)
    w.setFixedSize(1, 20)
    w.setStyleSheet("background:#3a4048;")
    return w


class _LevelBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._level = 0.0

    def set_level(self, value: float) -> None:
        v = max(0.0, min(1.0, float(value)))
        if abs(v - self._level) > 0.02:
            self._level = v
            self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        n = 7
        w = self.width() / n
        for i in range(n):
            on = self._level * n > i
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#34c759" if i < n - 2 else ("#f5a524" if i == n - 2 else "#e5484d")) if on else QColor("#4a5058"))
            p.drawRoundedRect(QRectF(i * w + 1, 4, w - 3, self.height() - 8), 2, 2)
        p.end()


class _MiniBtn(QPushButton):
    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a4048") if not self.underMouse() else QColor("#4a5058"))
        p.drawRoundedRect(QRectF(self.rect()), 7, 7)
        p.setBrush(QColor("#ffffff"))
        if self._kind == "pause":
            p.drawRoundedRect(QRectF(8, 6, 4, 14), 1, 1)
            p.drawRoundedRect(QRectF(15, 6, 4, 14), 1, 1)
        else:
            p.drawRoundedRect(QRectF(7, 7, 12, 12), 2, 2)
        p.end()


# ---------------------------------------------------------------------------
# 录制红框
# ---------------------------------------------------------------------------
class RecordBorder(QWidget):
    """录制中的屏幕红框：一条 4px 红边，鼠标穿透，不遮挡操作。"""

    def __init__(self, rect: QRect, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(rect)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(QPen(QColor("#e5484d"), 4))
        p.setBrush(Qt.NoBrush)
        r = self.rect().adjusted(2, 2, -2, -2)
        p.drawRect(r)
        p.end()


# ---------------------------------------------------------------------------
# 音频保存方式确认
# ---------------------------------------------------------------------------
class AudioChoiceDialog(QDialog):
    """录制前确认：整合到视频 / 分开 WAV / 两者都要 + 音轨方式。"""

    def __init__(self, parent: QWidget | None = None,
                 last: tuple[bool, str, bool] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("本次录制的音频怎么保存？"))
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("请选择这一次录制里，声音要怎么保存："), self))
        self._rb_embed = QRadioButton(t("整合到视频里（推荐）：声音嵌进 MP4，只有一个文件"), self)
        self._rb_split = QRadioButton(t("分开保存：视频不带声音，声音单独存成 WAV 文件"), self)
        self._rb_both = QRadioButton(t("两者都要：视频里有声音，同时单独导出 WAV 文件"), self)
        lay.addWidget(self._rb_embed)
        lay.addWidget(self._rb_split)
        lay.addWidget(self._rb_both)
        row = QHBoxLayout()
        row.addWidget(QLabel(t("视频里的音轨方式："), self))
        self._combo_mode = QComboBox(self)
        self._combo_mode.addItems([MIX_LABEL, TRACKS_LABEL])
        row.addWidget(self._combo_mode, 1)
        lay.addLayout(row)
        note = QLabel(t("提示：只勾选了系统声音或麦克风其中一路时，两种音轨方式效果相同。"), self)
        note.setStyleSheet(f"color:{INK3};font-size:11px;{FONT_QSS}")
        note.setWordWrap(True)
        lay.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        in_video = True
        mode = MIX_LABEL
        separate = False
        if last:
            in_video, mode, separate = last
        if in_video and not separate:
            self._rb_embed.setChecked(True)
        elif not in_video:
            self._rb_split.setChecked(True)
        else:
            self._rb_both.setChecked(True)
        if mode in (MIX_LABEL, TRACKS_LABEL):
            self._combo_mode.setCurrentText(mode)
        self._sync()
        for rb in (self._rb_embed, self._rb_split, self._rb_both):
            rb.toggled.connect(self._sync)

    def _sync(self) -> None:
        self._combo_mode.setEnabled(not self._rb_split.isChecked())

    def choice(self) -> tuple[bool, str, bool]:
        """返回 (音频进视频, 音轨方式, 单独导出 WAV)。"""
        if self._rb_split.isChecked():
            return False, self._combo_mode.currentText(), True
        if self._rb_both.isChecked():
            return True, self._combo_mode.currentText(), True
        return True, self._combo_mode.currentText(), False


__all__ = [
    "REC_MODES", "REC_MODE_ICONS", "REC_MODE_SHORT", "REC_MODE_DESC",
    "MIX_LABEL", "TRACKS_LABEL", "RecordPanel", "RecordControlBar",
    "RecordBorder", "AudioChoiceDialog", "SwitchRow", "ValueRow",
]
