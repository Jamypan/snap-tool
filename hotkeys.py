# -*- coding: utf-8 -*-
"""
hotkeys.py —— 全局热键的表示、持久化与「可视化改键」对话框。

配置写在 %APPDATA%\\SnapTool\\settings.json（不写程序目录，方便绿色版 / 安装包分发）。
若设置了环境变量 SNAPTOOL_HOME，则改用该目录，便于便携版把配置带在 U 盘里。

只依赖 PySide6，不反向 import snap.py / snapeditor.py，可单独做离屏自检。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from i18n import LANG, app_name, t

# ---------------------------------------------------------------------------
# Win32 常量（RegisterHotKey）
# ---------------------------------------------------------------------------
HOTKEY_ID = 0xA001
PIN_HOTKEY_ID = 0xA002          # v34 贴图热键：把剪贴板图片贴到桌面
REC_HOTKEY_ID = 0xA003          # v52 录屏热键：F9 开始 / 停止
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # 长按不重复触发

# v52：截图默认热键由 Ctrl+Shift+A 改为 Alt+Z（K 稿要求）
DEFAULT_MODS = MOD_ALT
DEFAULT_VK = 0x5A  # Z
OLD_DEFAULT_MODS = MOD_CONTROL | MOD_SHIFT   # v51 及以前的旧默认值，用于一次性迁移
OLD_DEFAULT_VK = 0x41  # A

# v52：录屏热键固定 F9（0x78），不提供自定义界面
DEFAULT_REC_MODS = 0
DEFAULT_REC_VK = 0x78  # F9

# v34 贴图热键默认 Ctrl+Shift+P（P = Pin），与截图热键可各自独立修改
DEFAULT_PIN_MODS = MOD_CONTROL | MOD_SHIFT
DEFAULT_PIN_VK = 0x50  # P

# 截图模式（热键 / 托盘「截图」使用的默认模式）
CAPTURE_MODES = ("rect", "window", "fullscreen")
MODE_LABELS = {"rect": "框选截图", "window": "窗口截图", "fullscreen": "全屏截图"}
DEFAULT_MODE = "rect"


def mode_label(mode: str) -> str:
    """随界面语言变化的模式名；MODE_LABELS 保留为简体中文常量（自测/兼容）。"""
    return t(MODE_LABELS.get(mode, MODE_LABELS[DEFAULT_MODE]))

# 单独的修饰键虚拟码，不允许当作主键
_MODIFIER_VKS = {0x10, 0x11, 0x12, 0x5B, 0x5C}  # Shift / Ctrl / Alt / LWin / RWin

_VK_NAMES = {
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    0x13: "Pause",
    0x14: "CapsLock",
    0x1B: "Esc",
    0x20: "Space",
    0x2C: "PrintScreen",
    0x2D: "Insert",
    0x2E: "Delete",
    0x24: "Home",
    0x23: "End",
    0x21: "PageUp",
    0x22: "PageDown",
    0x25: "←",
    0x26: "↑",
    0x27: "→",
    0x28: "↓",
    0x90: "NumLock",
    0x91: "ScrollLock",
    0xBA: ";",
    0xBB: "=",
    0xBC: ",",
    0xBD: "-",
    0xBE: ".",
    0xBF: "/",
    0xC0: "`",
    0xDB: "[",
    0xDC: "\\",
    0xDD: "]",
    0xDE: "'",
}

_MOD_LABELS = (
    (MOD_CONTROL, "Ctrl"),
    (MOD_ALT, "Alt"),
    (MOD_SHIFT, "Shift"),
    (MOD_WIN, "Win"),
)


def vk_name(vk: int) -> str:
    """把虚拟键码转成给用户看的名字。"""
    if vk in _VK_NAMES:
        return _VK_NAMES[vk]
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    if 0x60 <= vk <= 0x69:
        return t("小键盘 {n}", n=vk - 0x60)
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    return f"VK 0x{vk:02X}"


@dataclass(frozen=True)
class Hotkey:
    """一个全局热键：修饰键位掩码 + 主键虚拟码。"""

    mods: int = DEFAULT_MODS
    vk: int = DEFAULT_VK

    @property
    def win_mods(self) -> int:
        """传给 RegisterHotKey 的修饰键（自动加 NOREPEAT）。"""
        return (self.mods & 0x0F) | MOD_NOREPEAT

    def is_valid(self) -> bool:
        return (
            bool(self.mods & 0x0F)
            and 0 < self.vk < 0x100
            and self.vk not in _MODIFIER_VKS
        )

    def label(self) -> str:
        parts = [name for bit, name in _MOD_LABELS if self.mods & bit]
        parts.append(vk_name(self.vk))
        return " + ".join(parts)

    def to_dict(self) -> dict:
        return {"mods": int(self.mods & 0x0F), "vk": int(self.vk)}

    @classmethod
    def from_dict(cls, data) -> "Hotkey":
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(int(data.get("mods", DEFAULT_MODS)), int(data.get("vk", DEFAULT_VK)))
        except (TypeError, ValueError):
            return cls()


# ---------------------------------------------------------------------------
# 配置持久化
# ---------------------------------------------------------------------------
def config_dir() -> Path:
    override = os.environ.get("SNAPTOOL_HOME")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "SnapTool"


def config_path() -> Path:
    return config_dir() / "settings.json"


def _load_raw() -> dict:
    """读取整份配置；缺失/损坏时返回空 dict。"""
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_raw(raw: dict) -> bool:
    """原子写入整份配置，保留其它字段。"""
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        data = dict(raw)
        data["version"] = 2
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception:  # noqa: BLE001
        return False


def load_hotkey() -> Hotkey:
    """读取已保存的热键；文件缺失/损坏/非法时回退到默认值。

    v52：若配置里仍是 v51 及以前的旧默认值 Ctrl+Shift+A，视为「没改过热键」，
    一次性迁移到新默认 Alt+Z 并写回；用户自定义的其它组合一律保留。
    """
    raw = _load_raw()
    hk = Hotkey.from_dict(raw.get("capture", {}))
    if not hk.is_valid():
        return Hotkey()
    if hk.mods == OLD_DEFAULT_MODS and hk.vk == OLD_DEFAULT_VK:
        new = Hotkey()
        raw["capture"] = new.to_dict()
        _save_raw(raw)
        return new
    return hk


def save_hotkey(hk: Hotkey) -> bool:
    """保存热键（同时保留默认截图模式等其它配置）。"""
    if not hk.is_valid():
        return False
    raw = _load_raw()
    raw["capture"] = hk.to_dict()
    return _save_raw(raw)


def _default_pin_hotkey() -> Hotkey:
    return Hotkey(DEFAULT_PIN_MODS, DEFAULT_PIN_VK)


def load_pin_hotkey() -> Hotkey:
    """v34：读取贴图热键；缺失/损坏/非法时回退到默认 Ctrl+Shift+P。"""
    raw = _load_raw().get("pin_hotkey")
    if not isinstance(raw, dict) or not raw:
        return _default_pin_hotkey()
    hk = Hotkey.from_dict(raw)
    return hk if hk.is_valid() else _default_pin_hotkey()


def save_pin_hotkey(hk: Hotkey) -> bool:
    """v34：保存贴图热键（保留其它配置）。"""
    if not hk.is_valid():
        return False
    raw = _load_raw()
    raw["pin_hotkey"] = hk.to_dict()
    return _save_raw(raw)


def load_mode() -> str:
    """读取热键使用的默认截图模式；非法值回退到框选。"""
    mode = _load_raw().get("mode", DEFAULT_MODE)
    return mode if mode in CAPTURE_MODES else DEFAULT_MODE


def save_mode(mode: str) -> bool:
    """保存默认截图模式（同时保留热键等其它配置）。"""
    if mode not in CAPTURE_MODES:
        return False
    raw = _load_raw()
    raw["mode"] = mode
    return _save_raw(raw)


# 画笔平滑度档位：与 snapeditor.PEN_SMOOTH_LEVELS 保持一致（此处只做字符串
# 存取，不 import snapeditor，避免打破分层；两处一致性由自测锁定）。
PEN_SMOOTH_LEVELS = ("off", "low", "medium", "high")
PEN_SMOOTH_DEFAULT = "medium"


def load_pen_smooth() -> str:
    """读取画笔平滑档位；缺失/非法时回退到默认（中等）。"""
    level = _load_raw().get("pen_smooth", PEN_SMOOTH_DEFAULT)
    return level if level in PEN_SMOOTH_LEVELS else PEN_SMOOTH_DEFAULT


def save_pen_smooth(level: str) -> bool:
    """保存画笔平滑档位（同时保留热键 / 模式等其它配置）。"""
    if level not in PEN_SMOOTH_LEVELS:
        return False
    raw = _load_raw()
    raw["pen_smooth"] = level
    return _save_raw(raw)


# ---------------------------------------------------------------------------
# Qt 按键 → Win32 虚拟键
# ---------------------------------------------------------------------------
def _qt(name: str):
    return getattr(Qt, name, None)


def _qi(value) -> int:
    """PySide6 6.12 的 Qt.Key 能直接 int()，但 KeyboardModifier 只能取 .value。"""
    if value is None:
        return 0
    return int(value.value) if hasattr(value, "value") else int(value)


def _build_qt_vk_map() -> dict[int, int]:
    m: dict[int, int] = {}

    def put(qt_name: str, vk: int) -> None:
        key = _qt(qt_name)
        if key is not None:
            m[_qi(key)] = vk

    for name, vk in (
        ("Key_Escape", 0x1B),
        ("Key_Tab", 0x09),
        ("Key_Backtab", 0x09),
        ("Key_Backspace", 0x08),
        ("Key_Return", 0x0D),
        ("Key_Enter", 0x0D),
        ("Key_Insert", 0x2D),
        ("Key_Delete", 0x2E),
        ("Key_Home", 0x24),
        ("Key_End", 0x23),
        ("Key_PageUp", 0x21),
        ("Key_PageDown", 0x22),
        ("Key_Left", 0x25),
        ("Key_Up", 0x26),
        ("Key_Right", 0x27),
        ("Key_Down", 0x28),
        ("Key_Space", 0x20),
        ("Key_Print", 0x2C),
        ("Key_SysReq", 0x2C),
        ("Key_Pause", 0x13),
        ("Key_ScrollLock", 0x91),
        ("Key_NumLock", 0x90),
        ("Key_CapsLock", 0x14),
        ("Key_Minus", 0xBD),
        ("Key_Equal", 0xBB),
        ("Key_BracketLeft", 0xDB),
        ("Key_BracketRight", 0xDD),
        ("Key_Backslash", 0xDC),
        ("Key_Semicolon", 0xBA),
        ("Key_Apostrophe", 0xDE),
        ("Key_Comma", 0xBC),
        ("Key_Period", 0xBE),
        ("Key_Slash", 0xBF),
        ("Key_QuoteLeft", 0xC0),
    ):
        put(name, vk)
    for i in range(1, 25):
        put(f"Key_F{i}", 0x6F + i)  # F1 = 0x70
    return m


_QT_VK_MAP = _build_qt_vk_map()
_MODIFIER_QT_KEYS = {
    _qi(k)
    for k in (
        _qt("Key_Control"),
        _qt("Key_Shift"),
        _qt("Key_Alt"),
        _qt("Key_Meta"),
        _qt("Key_AltGr"),
    )
    if k is not None
}
_KEYPAD_MOD = _qi(_qt("KeypadModifier"))


def mods_from_qt(qmods: int) -> int:
    m = 0
    if qmods & _qi(Qt.ControlModifier):
        m |= MOD_CONTROL
    if qmods & _qi(Qt.AltModifier):
        m |= MOD_ALT
    if qmods & _qi(Qt.ShiftModifier):
        m |= MOD_SHIFT
    if qmods & _qi(Qt.MetaModifier):
        m |= MOD_WIN
    return m


def qt_event_to_hotkey(ev) -> Hotkey | None:
    """把一个 QKeyEvent 转成 Hotkey；纯修饰键 / 无修饰键 / 不认识的键返回 None。"""
    k = _qi(ev.key())
    qmods = _qi(ev.modifiers())
    if k in _MODIFIER_QT_KEYS:
        return None
    mods = mods_from_qt(qmods)
    if not mods:
        return None

    vk = _QT_VK_MAP.get(k)
    if vk is None:
        if _qi(Qt.Key_A) <= k <= _qi(Qt.Key_Z) or _qi(Qt.Key_0) <= k <= _qi(Qt.Key_9):
            if _KEYPAD_MOD and (qmods & _KEYPAD_MOD) and _qi(Qt.Key_0) <= k <= _qi(Qt.Key_9):
                vk = 0x60 + (k - _qi(Qt.Key_0))
            else:
                vk = k & 0xFF
    if vk is None or vk in _MODIFIER_VKS:
        return None
    return Hotkey(mods, vk)


# 手动选择时的主键候选
KEY_CHOICES: list[tuple[str, int]] = []
KEY_CHOICES += [(c, ord(c)) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
KEY_CHOICES += [(c, ord(c)) for c in "0123456789"]
KEY_CHOICES += [(f"F{i}", 0x6F + i) for i in range(1, 13)]
KEY_CHOICES += [
    ("PrintScreen", 0x2C),
    ("Space", 0x20),
    ("Enter", 0x0D),
    ("Tab", 0x09),
    ("Backspace", 0x08),
    ("Esc", 0x1B),
    ("Insert", 0x2D),
    ("Delete", 0x2E),
    ("Home", 0x24),
    ("End", 0x23),
    ("PageUp", 0x21),
    ("PageDown", 0x22),
    ("←", 0x25),
    ("↑", 0x26),
    ("→", 0x27),
    ("↓", 0x28),
]


# ---------------------------------------------------------------------------
# 改键对话框
# ---------------------------------------------------------------------------
class HotkeyDialog(QDialog):
    """两种改键方式：直接按键录制，或勾选修饰键 + 下拉选主键。

    打开时先注销现有全局热键（由 App 负责），避免录制时旧热键把截图遮罩唤起来。
    """

    STYLE = (
        "QDialog { background:#f7f8fa; }"
        "QPushButton#capture { background:#ffffff; border:1px solid #0a84ff; border-radius:6px;"
        " color:#0a84ff; font-size:16px; font-weight:bold; padding:10px; }"
        "QPushButton#capture:hover { background:#eef6ff; }"
        "QPushButton { padding:6px 14px; }"
        "QPushButton#primary { background:#0a84ff; color:#ffffff; border:none; border-radius:5px;"
        " font-weight:bold; padding:7px 18px; }"
        "QPushButton#primary:hover { background:#0969cc; }"
        "QLabel#tip, QLabel#status { color:#6b7280; }"
        "QComboBox { padding:4px 8px; }"
    )

    def __init__(self, current: Hotkey, parent=None, app_title: str | None = None,
                 error: str = "", *, title_key: str = "设置截图热键 - {app}",
                 default: Hotkey | None = None) -> None:
        super().__init__(parent)
        self._default = default if default is not None else Hotkey()
        self.hotkey = current if current.is_valid() else self._default
        self._capturing = False
        self._grabbed = False
        self._app_title = app_title or app_name()
        self._title_key = title_key
        self.setWindowTitle(t(title_key, app=self._app_title))
        self.setMinimumWidth(430)
        self.setStyleSheet(self.STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        self.current_label = QLabel(t("当前热键：<b>{label}</b>", label=self.hotkey.label()))
        root.addWidget(self.current_label)

        self.capture_btn = QPushButton(self.hotkey.label())
        self.capture_btn.setObjectName("capture")
        self.capture_btn.setMinimumHeight(52)
        self.capture_btn.setToolTip(t("点这里后直接按下想要的组合键"))
        self.capture_btn.clicked.connect(self._start_capture)
        root.addWidget(self.capture_btn)

        self._tip = QLabel(
            t("点上方按钮后，按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键（如 Ctrl + Shift + S）。按 Esc 可放弃本次录制。")
        )
        self._tip.setObjectName("tip")
        self._tip.setWordWrap(True)
        root.addWidget(self._tip)

        mods_row = QHBoxLayout()
        mods_row.setSpacing(14)
        self.chk: dict[int, QCheckBox] = {}
        for bit, name in _MOD_LABELS:
            cb = QCheckBox(name)
            cb.setChecked(bool(self.hotkey.mods & bit))
            cb.stateChanged.connect(self._on_manual)
            self.chk[bit] = cb
            mods_row.addWidget(cb)
        mods_row.addStretch(1)

        key_row = QHBoxLayout()
        self._key_label = QLabel(t("主键"))
        key_row.addWidget(self._key_label)
        self.key_combo = QComboBox()
        for name, vk in KEY_CHOICES:
            self.key_combo.addItem(name, vk)
        self._select_combo_vk(self.hotkey.vk)
        self.key_combo.currentIndexChanged.connect(self._on_manual)
        key_row.addWidget(self.key_combo, 1)
        root.addLayout(mods_row)
        root.addLayout(key_row)

        self._manual_tip = QLabel(t("录制不到某些键（如 Win 组合）时，也可以在这里手动选择。"))
        self._manual_tip.setObjectName("tip")
        self._manual_tip.setWordWrap(True)
        root.addWidget(self._manual_tip)

        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        btns = QHBoxLayout()
        self._b_default = QPushButton(t("恢复默认"))
        self._b_default.clicked.connect(self._restore_default)
        self._b_cancel = QPushButton(t("取消"))
        self._b_cancel.clicked.connect(self.reject)
        self._b_save = QPushButton(t("保存"))
        self._b_save.setObjectName("primary")
        self._b_save.setDefault(True)
        self._b_save.clicked.connect(self.accept)
        btns.addWidget(self._b_default)
        btns.addStretch(1)
        btns.addWidget(self._b_cancel)
        btns.addWidget(self._b_save)
        root.addLayout(btns)

        if error:
            self._show_status(error, error=True)
        # show 之后自动进入录制态，用户可以直接按键
        QTimer.singleShot(0, self._start_capture)
        LANG.changed.connect(self.retranslate_ui)

    def retranslate_ui(self, _code: str = "") -> None:
        """语言切换后刷新改键对话框的静态文案（不打断正在录制的按键）。"""
        self.setWindowTitle(t(self._title_key, app=self._app_title))
        self.current_label.setText(t("当前热键：<b>{label}</b>", label=self.hotkey.label()))
        self.capture_btn.setToolTip(t("点这里后直接按下想要的组合键"))
        self._tip.setText(
            t("点上方按钮后，按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键（如 Ctrl + Shift + S）。按 Esc 可放弃本次录制。")
        )
        self._key_label.setText(t("主键"))
        self._manual_tip.setText(t("录制不到某些键（如 Win 组合）时，也可以在这里手动选择。"))
        self._b_default.setText(t("恢复默认"))
        self._b_cancel.setText(t("取消"))
        self._b_save.setText(t("保存"))

    # ------------------------------------------------------------ 状态同步
    def _show_status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet("color:#d93025; font-weight:bold;" if error else "color:#6b7280;")

    def _select_combo_vk(self, vk: int) -> None:
        idx = self.key_combo.findData(vk)
        if idx < 0:
            self.key_combo.addItem(vk_name(vk), vk)
            idx = self.key_combo.count() - 1
        self.key_combo.blockSignals(True)
        self.key_combo.setCurrentIndex(idx)
        self.key_combo.blockSignals(False)

    def _set_hotkey(self, hk: Hotkey) -> None:
        self.hotkey = hk
        for bit, cb in self.chk.items():
            cb.blockSignals(True)
            cb.setChecked(bool(hk.mods & bit))
            cb.blockSignals(False)
        self._select_combo_vk(hk.vk)
        self.capture_btn.setText(hk.label() if hk.is_valid() else t("未选择修饰键"))

    def _on_manual(self) -> None:
        self._stop_capture()
        mods = 0
        for bit, cb in self.chk.items():
            if cb.isChecked():
                mods |= bit
        vk = self.key_combo.currentData()
        self.hotkey = Hotkey(mods, int(vk) if vk is not None else DEFAULT_VK)
        self.capture_btn.setText(self.hotkey.label() if self.hotkey.is_valid() else t("未选择修饰键"))
        self._show_status("")

    def _restore_default(self) -> None:
        self._stop_capture()
        self._set_hotkey(self._default)
        self._show_status(t("已恢复为 {label}，点「保存」生效。", label=self._default.label()))

    # ------------------------------------------------------------ 按键录制
    def _start_capture(self) -> None:
        if not self.isVisible():
            return
        self._capturing = True
        self.capture_btn.setText(t("请按下组合键…"))
        self.capture_btn.setFocus()
        self.grabKeyboard()
        self._grabbed = True
        self._show_status(t("正在录制：按住修饰键再按主键（Esc 放弃录制）"))

    def _stop_capture(self) -> None:
        self._capturing = False
        if self._grabbed:
            self.releaseKeyboard()
            self._grabbed = False

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(ev)
            return
        k = _qi(ev.key())
        qmods = _qi(ev.modifiers())
        ev.accept()  # 不传给父控件，避免 Enter/Space 误触发默认按钮

        if k in _MODIFIER_QT_KEYS:
            return  # 修饰键单独按下，等主键
        if k == _qi(Qt.Key_Escape) and qmods == 0:
            self._stop_capture()
            self.capture_btn.setText(self.hotkey.label())
            self._show_status(t("已放弃录制，可点上方按钮重试，或直接手动选择。"))
            return

        hk = qt_event_to_hotkey(ev)
        if hk is None:
            self._show_status(t("请按住 Ctrl / Alt / Shift / Win 中至少一个，再按一个主键。"), error=True)
            return
        self._set_hotkey(hk)
        self._stop_capture()
        self._show_status(t("已录制：{label}。点「保存」生效。", label=hk.label()))

    def accept(self) -> None:  # noqa: D102
        if not self.hotkey.is_valid():
            self._stop_capture()
            self._show_status(t("请至少选择一个修饰键（Ctrl / Alt / Shift / Win），并指定主键。"), error=True)
            return
        self._stop_capture()
        super().accept()

    def done(self, r) -> None:  # noqa: D102
        self._stop_capture()
        super().done(r)
