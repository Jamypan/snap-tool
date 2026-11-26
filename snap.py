# -*- coding: utf-8 -*-
"""
snap.py —— 截图工具主程序。

功能：
  · 启动即显示程序主窗口（帮助菜单 / 三种截图模式 / 默认模式设置）+ 托盘常驻
  · 全局热键唤起截图（默认 Alt+Z，可在菜单里自定义）
  · v52 录屏：F9 开始 / 停止，框选 / 窗口 / 全屏三种方式 + 系统声 / 麦克风 / 摄像头画中画
  · 三种截图模式：框选、窗口（悬停高亮单击）、全屏
  · 矩形/椭圆/箭头/画笔/马赛克/文字标注（画笔首尾可加箭头）
  · 程序窗口里整图旋转 90° / 左右上下镜像（可撤销）
  · 复制到剪贴板 / 另存为
  · 滚动长截图：单击目标窗口即自动下滚，左键暂停 / 继续、右键或「确定 ✓」结束
  · OCR 取字：逐行盖回原文位置，可就地拖选 / 复制

用法：python snap.py            正常启动（主窗口 + 托盘常驻）
     python snap.py --shot     启动后立刻截一次
     python snap.py --restart  结束后台残留实例并重新启动
     python snap.py --selftest 只做自检不进入界面
     python snap.py --help     打印命令行说明（不进入界面）
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

# 让脚本无论从哪个目录启动都能 import 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

import singleinstance  # noqa: E402
import snapback  # noqa: E402
from PySide6.QtCore import (  # noqa: E402
    QAbstractNativeEventFilter,
    QMetaObject,
    QPoint,
    QRect,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import QAction, QImage, QPixmap  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from hotkeys import (  # noqa: E402
    CAPTURE_MODES,
    HOTKEY_ID,
    PIN_HOTKEY_ID,
    REC_HOTKEY_ID,
    Hotkey,
    HotkeyDialog,
    load_hotkey,
    load_mode,
    load_pen_smooth,
    load_pin_hotkey,
    mode_label,
    save_hotkey,
    save_mode,
    save_pen_smooth,
    save_pin_hotkey,
)
from i18n import LANG, app_name, t  # noqa: E402
from i18n_docs import cli_help  # noqa: E402
from recording_flow import RecordingController  # noqa: E402
from recording_ui import (  # noqa: E402
    MIX_LABEL as REC_MIX_LABEL,
    AudioChoiceDialog,
    RecordBorder,
    RecordControlBar,
)
from snapeditor import Overlay, set_pen_smooth  # noqa: E402
from snap_editor import EditorWindow  # noqa: E402
from pinwindow import PinWindow  # noqa: E402
from snapui import (  # noqa: E402
    AboutDialog,
    HelpWindow,
    LanguageDialog,
    MainWindow,
    PEN_SMOOTH_LABELS,
    make_icon,
)

WM_HOTKEY = 0x0312

user32 = ctypes.windll.user32

# ---------------------------------------------------------------------------
# Win32 消息结构（用于全局热键）
# ---------------------------------------------------------------------------
class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
    ]


class HotkeyFilter(QAbstractNativeEventFilter):
    """把 WM_HOTKEY 转成 Python 回调。"""

    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, eventType, message):  # noqa: N802
        try:
            et = bytes(eventType) if not isinstance(eventType, bytes) else eventType
        except Exception:
            et = b""
        if et == b"windows_generic_MSG":
            msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
            if msg.message == WM_HOTKEY:
                self.callback(int(msg.wParam))
        return False, 0


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def pil_to_qimage(pil_img) -> QImage:
    pil = pil_img.convert("RGB")
    data = pil.tobytes("raw", "RGB")
    qimg = QImage(data, pil.width, pil.height, pil.width * 3, QImage.Format_RGB888)
    return qimg.copy()  # 必须 copy，否则跟随 Python 缓冲区一起失效


def default_save_dir() -> Path:
    home = Path(os.path.expanduser("~"))
    for name in ("Pictures", "图片"):
        p = home / name
        if p.exists():
            d = p / "Screenshots"
            d.mkdir(parents=True, exist_ok=True)
            return d
    d = home / "Screenshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def overlay_rect_to_screen(
    logical_rect: QRect, origin: QPoint, dpr: float
) -> "snapback.ScreenRect":
    """Overlay 局部逻辑选区 → 屏幕物理矩形。

    origin 是 Overlay(0,0) 的全局逻辑坐标（多显示器时可能为负），dpr 为
    设备像素比。长截图要在真实屏幕上滚动，所以必须先把选区还原成物理坐标；
    普通编辑器只裁剪内存里的底图，不需要这一步。
    """
    return snapback.ScreenRect(
        int(round((logical_rect.x() + origin.x()) * dpr)),
        int(round((logical_rect.y() + origin.y()) * dpr)),
        int(round(logical_rect.width() * dpr)),
        int(round(logical_rect.height() * dpr)),
    )


def physical_from_screen(
    gp: QPoint, geo: QRect, d: float, monitors: list, fallback_dpr: float
) -> tuple[int, int]:
    """纯换算：Qt 屏幕逻辑几何 + dpr + 显示器物理矩形 → 物理像素点。

    拆成纯函数便于混合 DPI 场景自测（无需真的接两块不同缩放的显示器）。
    """
    d = d or fallback_dpr
    if monitors:
        # Qt 屏幕逻辑尺寸 × dpr ≈ 物理尺寸，据此匹配对应的物理显示器
        want_w, want_h = geo.width() * d, geo.height() * d
        mon = min(monitors, key=lambda m: abs(m.w - want_w) + abs(m.h - want_h))
        top = geo.topLeft()
        return (
            int(round(mon.x + (gp.x() - top.x()) * d)),
            int(round(mon.y + (gp.y() - top.y()) * d)),
        )
    # 没有 Win32 显示器信息（非 Windows / 离屏测试）：按所在屏 dpr 换算
    return int(round(gp.x() * d)), int(round(gp.y() * d))


def global_logical_to_physical(gp: QPoint, fallback_dpr: float) -> tuple[int, int]:
    """Qt 全局逻辑坐标 → 屏幕物理像素（多显示器混合 DPI 下按光标所在屏换算）。

    旧代码统一乘主屏 dpr，副屏缩放不同时物理点会算偏，窗口探测于是命中
    错误的窗口。这里用光标所在 QScreen 的 dpr 与几何原点，配合 Win32 枚举
    出的显示器物理矩形做换算；拿不到就退回原来的统一 dpr 算法。
    """
    try:
        from PySide6.QtGui import QGuiApplication
        scr = QGuiApplication.screenAt(QPoint(gp))
        if scr is None:
            raise ValueError("no screen")
        return physical_from_screen(
            gp, scr.geometry(), float(scr.devicePixelRatio()),
            snapback.monitor_physical_rects(), fallback_dpr,
        )
    except Exception:  # noqa: BLE001
        return int(round(gp.x() * fallback_dpr)), int(round(gp.y() * fallback_dpr))


def place_bar_outside(
    sel: QRect, screen: QRect, bw: int, bh: int, margin: int = 8
) -> QRect | None:
    """为控制条找一个不与窗口选区相交、且完全在虚拟屏内的位置。

    优先窗口上方 → 下方 → 左 → 右，最后退回屏幕四角；全部无解（窗口
    占满整个虚拟屏）时返回 None，由调用方启用「抓帧瞬间隐藏」兜底。
    """
    cx = sel.left() + sel.width() // 2 - bw // 2
    cy = sel.top() + sel.height() // 2 - bh // 2
    candidates = [
        (cx, sel.top() - bh - margin),
        (cx, sel.bottom() + margin),
        (sel.left() - bw - margin, cy),
        (sel.right() + margin, cy),
        (screen.left() + margin, screen.top() + margin),
        (screen.right() - bw - margin, screen.top() + margin),
        (screen.left() + margin, screen.bottom() - bh - margin),
        (screen.right() - bw - margin, screen.bottom() - bh - margin),
    ]
    for x, y in candidates:
        x = max(screen.left(), min(x, screen.right() - bw))
        y = max(screen.top(), min(y, screen.bottom() - bh))
        r = QRect(x, y, bw, bh)
        if screen.contains(r) and not r.intersects(sel):
            return r
    return None


def bar_screen_rect(bar: QWidget, dpr: float) -> "snapback.ScreenRect":
    """控制条全局逻辑矩形 → 屏幕物理矩形（供 ScrollControl 过滤点击）。"""
    g = bar.geometry()
    return snapback.ScreenRect(
        int(round(g.x() * dpr)),
        int(round(g.y() * dpr)),
        int(round(g.width() * dpr)),
        int(round(g.height() * dpr)),
    )


def make_bar_hook(bar: QWidget, method: str):
    """生成在子线程里同步调用主线程 hide/show 的回调。

    BlockingQueuedConnection 会等主线程执行完再返回，保证抓帧那一刻
    控制条确实不可见；Qt 只在主线程事件循环运行时允许这种调用。
    """
    def hook() -> None:
        try:
            QMetaObject.invokeMethod(bar, method, Qt.BlockingQueuedConnection)
        except Exception:  # noqa: BLE001  控制条已销毁时不能打断拼接
            pass
    return hook


def save_qimage(img: QImage, path: Path) -> None:
    suffix = path.suffix.lower() or ".png"
    fmt = "JPG" if suffix in (".jpg", ".jpeg") else "PNG"
    if not img.save(str(path), fmt):
        raise OSError(t("保存失败：{path}", path=path))


# ---------------------------------------------------------------------------
# 后台工作线程
# ---------------------------------------------------------------------------
class StitchWorker(QThread):
    """滚动长截图（阻塞式，跑在子线程）。

    control 负责把左键 / 右键 / 「确定」翻译成暂停与结束状态；
    Qt 信号可以跨线程 emit，所以控制条的状态刷新走 state_changed。
    """

    progress = Signal(int, int, float)   # 帧数 / 当前高度 / 最近一次匹配得分
    state_changed = Signal(bool, str)
    ok = Signal(object, dict)
    failed = Signal(str)

    def __init__(
        self, rect: snapback.ScreenRect, control: "snapback.ScrollControl | None" = None
    ) -> None:
        super().__init__()
        self.rect = rect
        self.control = control or snapback.ScrollControl()
        # 控制条与选区重叠时，抓帧瞬间临时隐藏 / 恢复（由 App 注入）
        self.before_grab = None
        self.after_grab = None

    def run(self) -> None:  # noqa: D102
        ctrl = self.control
        ctrl.set_on_change(
            lambda: self.state_changed.emit(ctrl.paused, ctrl.stop_reason)
        )
        try:
            img, stats = snapback.stitch_scroll(
                self.rect,
                on_progress=lambda f, h, c, s: self.progress.emit(f, h, s),
                should_stop=snapback.is_escape_pressed,
                control=ctrl,
                on_before_grab=self.before_grab,
                on_after_grab=self.after_grab,
            )
            self.ok.emit(img, stats)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class OcrWorker(QThread):
    """OCR（阻塞式，跑在子线程）。

    ok 信号携带 (行列表, 后端名)：每行是 {"text", "box", "score"}，
    box 为选区裁剪图内的像素坐标，供前端把文字逐行盖回原位。
    """

    ok = Signal(object, str)
    failed = Signal(str)

    def __init__(self, img: QImage) -> None:
        super().__init__()
        self.img = img

    def run(self) -> None:  # noqa: D102
        try:
            from PIL import Image

            # 截图链路产生的 QImage 可能是 RGB888（3字节/像素），
            # 先统一转成 RGBA8888（4字节/像素），frombytes 才不会报
            # "not enough image data"。
            img = self.img.convertToFormat(QImage.Format_RGBA8888)
            pil = Image.frombytes(
                "RGBA",
                (img.width(), img.height()),
                img.constBits().tobytes(),
                "raw",
                "RGBA",
            ).convert("RGB")
            lines, backend = snapback.ocr_image_lines(pil)
            self.ok.emit(lines, backend)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# 长截图进行中的提示条
# ---------------------------------------------------------------------------
class BusyBar(QWidget):
    """滚动长截图进行中的悬浮控制条（无按钮，纯状态提示）。

    页面内**左键**：暂停 / 再点继续；**右键** 或 **Esc**：结束；
    滚到底也会自动结束。控制条尽量放在窗口之外，避免被拍进长图。
    """

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._frames, self._height = 0, 0
        self._score: float | None = None
        self._paused = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.title = QLabel()
        self.detail = QLabel()
        self.title.setStyleSheet("color:#fff; font-size:14px; font-weight:bold;")
        self.detail.setStyleSheet("color:#cfcfcf; font-size:12px;")
        row.addWidget(self.title)
        row.addWidget(self.detail)
        row.addStretch(1)
        root.addLayout(row)

        self.hint = QLabel()
        self.hint.setStyleSheet("color:#9ca3af; font-size:11px;")
        root.addWidget(self.hint)

        self.setStyleSheet(
            """
            QWidget { background:#1f1f1f; border:1px solid #3a3a3a; border-radius:8px; }
            """
        )
        # 去掉确定按钮后收窄：文字够放即可，不再需要容纳按钮。
        # 固定尺寸：拼接过程中数字/语言变化都不会让控制条改变几何，
        # 否则 exclude_rect 与实际位置会不一致。
        self.setFixedSize(400, 72)
        self.retranslate_ui()
        LANG.changed.connect(self.retranslate_ui)

    def update_text(self, frames: int, height: int, score: float | None = None) -> None:
        self._frames, self._height = frames, height
        self._score = score
        self._render_detail()

    def set_paused(self, paused: bool, _reason: str = "") -> None:
        self._paused = bool(paused)
        self._render_state()

    def _render_state(self) -> None:
        self.title.setText(
            t("已暂停 · 左键继续") if self._paused else t("正在滚动截屏…")
        )

    def _render_detail(self) -> None:
        text = t("已拼 {frames} 帧 · {height}px", frames=self._frames, height=self._height)
        if self._score is not None:
            # 数字无需翻译；匹配分掉下来时用户能立刻看出「页面在动」导致难对齐
            text += " · " + t("匹配 {score}", score=f"{self._score:.2f}")
        self.detail.setText(text)

    def retranslate_ui(self, _code: str = "") -> None:
        self._render_state()
        self._render_detail()
        # v51：去掉确定按钮，直接告诉用户三种结束方式
        self.hint.setText(t("左键暂停 / 继续 · 右键或 Esc 结束 · 滚到底自动结束"))


# ---------------------------------------------------------------------------
# 结果预览窗口
# ---------------------------------------------------------------------------
class PreviewWindow(QWidget):
    """长截图结果的预览与导出窗口。"""

    def __init__(self, img: QImage, save_dir: Path, copied: bool = False) -> None:
        super().__init__(None, Qt.Window)
        self._copied = copied
        self._saved_path: str | None = None
        self.setWindowTitle(t("{app} - 长截图预览", app=app_name()))
        self.img = img
        self.save_dir = save_dir

        root = QVBoxLayout(self)
        area = QScrollArea()
        area.setWidgetResizable(True)
        label = QLabel()
        label.setPixmap(QPixmap.fromImage(img))
        area.setWidget(label)
        root.addWidget(area, 1)

        self._info = QLabel(t("尺寸：{w} × {h} px", w=img.width(), h=img.height()))
        self._info.setStyleSheet("color:#555;")
        root.addWidget(self._info)

        row = QHBoxLayout()
        self._b_copy = QPushButton(t("复制到剪贴板"))
        self._b_save = QPushButton(t("保存为文件"))
        self._b_close = QPushButton(t("关闭"))
        self._b_copy.clicked.connect(self._copy)
        self._b_save.clicked.connect(self._save)
        self._b_close.clicked.connect(self.close)
        row.addStretch(1)
        row.addWidget(self._b_copy)
        row.addWidget(self._b_save)
        row.addWidget(self._b_close)
        root.addLayout(row)

        self.resize(760, 720)
        LANG.changed.connect(self.retranslate_ui)

    def retranslate_ui(self, _code: str = "") -> None:
        self._b_copy.setText(t("复制到剪贴板"))
        self._b_save.setText(t("保存为文件"))
        self._b_close.setText(t("关闭"))
        self._info.setText(t("尺寸：{w} × {h} px", w=self.img.width(), h=self.img.height()))
        self._render_title()

    def _render_title(self) -> None:
        app = app_name()
        if self._copied:
            self.setWindowTitle(t("{app} - 已复制到剪贴板", app=app))
        elif self._saved_path:
            self.setWindowTitle(t("{app} - 已保存：{path}", app=app, path=self._saved_path))
        else:
            self.setWindowTitle(t("{app} - 长截图预览", app=app))

    def _copy(self) -> None:
        QApplication.clipboard().setImage(self.img)
        self._copied, self._saved_path = True, None
        self._render_title()

    def _save(self) -> None:
        default = self.save_dir / f"{t('长截图_')}{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, t("保存长截图"), str(default), t("PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        )
        if not path:
            return
        try:
            save_qimage(self.img, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, app_name(), str(exc))
            return
        self._saved_path, self._copied = path, False
        self._render_title()


# 取字结果在截图遮罩内展示（见 snapeditor.py）：逐行盖回原文位置，
# 识别中/无坐标降级时才用浮层面板；不再使用独立的顶层结果窗口。


# ---------------------------------------------------------------------------
# 主控制器
# ---------------------------------------------------------------------------
class App:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.save_dir = default_save_dir()
        self.overlay: Overlay | None = None
        self.preview: PreviewWindow | None = None
        self.editor: EditorWindow | None = None
        self.pins: list[PinWindow] = []   # v34 钉在桌面的贴图浮窗（可多张）
        self.busy: BusyBar | None = None
        self._ocr_busy = False          # 已有取字任务在跑时忽略重复点击
        self._workers: list[QThread] = []
        self._help_window: HelpWindow | None = None
        self._about_box: AboutDialog | None = None
        self._hidden_windows: list[QWidget] = []
        self._minimize_hint_shown = False
        self._quitting = False          # 正在退出：屏蔽一切托盘提示 / 窗口提示
        # v52 录屏
        self.recorder = RecordingController()
        self._rec_bar: RecordControlBar | None = None
        self._rec_border: RecordBorder | None = None
        self._rec_paused = False
        self._rec_audio_choice = (True, REC_MIX_LABEL, False)

        self.hotkey: Hotkey = load_hotkey()
        self.pin_hotkey: Hotkey = load_pin_hotkey()   # v34 贴图热键
        self.capture_mode = load_mode()
        self.pen_smooth = load_pen_smooth()
        set_pen_smooth(self.pen_smooth)   # 应用画笔平滑档位到绘制模块
        self._hotkey_registered = False
        self._pin_hotkey_registered = False
        self._hk_error = ""

        icon = make_icon()
        self.main_window = MainWindow(icon, self.hotkey, self.capture_mode, self.save_dir,
                                      self.pen_smooth)
        self.main_window.capture_requested.connect(self.start_capture)
        self.main_window.long_capture_requested.connect(self.start_long_capture)
        self.main_window.ocr_capture_requested.connect(self.start_ocr_capture)
        self.main_window.pin_clipboard_requested.connect(
            lambda: self.pin_clipboard()
        )
        self.main_window.mode_changed.connect(self._on_mode_changed)
        self.main_window.hotkey_requested.connect(self.open_hotkey_settings)
        self.main_window.pin_hotkey_requested.connect(self.open_pin_hotkey_settings)
        self.main_window.help_requested.connect(self.show_help)
        self.main_window.about_requested.connect(self.show_about)
        self.main_window.open_dir_requested.connect(self._open_save_dir)
        self.main_window.minimize_requested.connect(self._on_minimized)
        self.main_window.quit_requested.connect(self.quit)
        self.main_window.language_requested.connect(self.open_language_settings)
        self.main_window.pen_smooth_changed.connect(self._on_pen_smooth_changed)
        # v52 录屏
        self.main_window.record_start_requested.connect(self.start_record)
        self.main_window.record_default_changed.connect(self._on_record_default_changed)
        self.main_window.record_dir_requested.connect(self._open_record_dir)
        self.recorder.started.connect(self._on_rec_started)
        self.recorder.stopped.connect(self._on_rec_stopped)
        self.recorder.error.connect(self._on_rec_error)
        self.recorder.levels.connect(self._on_rec_levels)
        self.recorder.tick.connect(lambda _s: None)
        self.recorder.finalized.connect(self._on_rec_finalized)

        self.tray = QSystemTrayIcon(icon)
        self.menu = QMenu()
        self._tray_actions: dict[str, QAction] = {}
        act_show = QAction(t("显示主窗口"), self.menu)
        act_show.triggered.connect(lambda _checked=False: self.show_main_window())
        self.menu.addAction(act_show)
        self._tray_actions["show"] = act_show
        self.act_capture = QAction(t("截图"), self.menu)
        self.act_capture.triggered.connect(lambda: self.start_capture())
        self.menu.addAction(self.act_capture)
        self._tray_actions["capture"] = self.act_capture
        self.act_pin_clipboard = QAction(t("贴出剪贴板图片"), self.menu)
        self.act_pin_clipboard.triggered.connect(lambda _checked=False: self.pin_clipboard())
        self.menu.addAction(self.act_pin_clipboard)
        self._tray_actions["pin_clipboard"] = self.act_pin_clipboard
        # v52：托盘录屏入口（F9 注册失败时的兜底）
        self.act_record = QAction(t("开始 / 停止录屏 (F9)"), self.menu)
        self.act_record.triggered.connect(lambda _checked=False: self.toggle_record())
        self.menu.addAction(self.act_record)
        self._tray_actions["record"] = self.act_record
        self.menu.addSeparator()
        for mode in CAPTURE_MODES:
            act = QAction(mode_label(mode), self.menu)
            act.triggered.connect(
                lambda _checked=False, m=mode: self.start_capture(m)
            )
            self.menu.addAction(act)
            self._tray_actions[f"mode_{mode}"] = act
        act_long = QAction(t("滚动长截图…"), self.menu)
        act_long.triggered.connect(lambda _checked=False: self.start_long_capture())
        self.menu.addAction(act_long)
        self._tray_actions["long_capture"] = act_long
        self.menu.addSeparator()
        act_hotkey = QAction(t("设置热键…"), self.menu)
        act_hotkey.triggered.connect(lambda _checked=False: self.open_hotkey_settings())
        self.menu.addAction(act_hotkey)
        self._tray_actions["hotkey"] = act_hotkey
        act_lang = QAction(t("语言…"), self.menu)
        act_lang.triggered.connect(lambda _checked=False: self.open_language_settings())
        self.menu.addAction(act_lang)
        self._tray_actions["language"] = act_lang
        act_dir = QAction(t("打开保存目录"), self.menu)
        act_dir.triggered.connect(lambda _checked=False: self._open_save_dir())
        self.menu.addAction(act_dir)
        self._tray_actions["dir"] = act_dir
        self.menu.addSeparator()
        act_help = QAction(t("使用说明…"), self.menu)
        act_help.triggered.connect(lambda: self.show_help("help"))
        self.menu.addAction(act_help)
        self._tray_actions["help"] = act_help
        act_about = QAction(t("关于…"), self.menu)
        act_about.triggered.connect(lambda _checked=False: self.show_about())
        self.menu.addAction(act_about)
        self._tray_actions["about"] = act_about
        act_quit = QAction(t("退出"), self.menu)
        act_quit.triggered.connect(lambda _checked=False: self.quit())
        self.menu.addAction(act_quit)
        self._tray_actions["quit"] = act_quit
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.show()
        LANG.changed.connect(self._retranslate_tray)

        # 有人重复启动时请求「把主窗口显示出来」，避免用户以为程序没在运行
        # 返回的是 QTimer（轮询唤醒事件），必须挂在 self 上保持引用
        self._activate_notifier = singleinstance.install_activation_notifier(
            self._on_activate_request
        )

        self.filter = HotkeyFilter(self._on_hotkey)
        app.installNativeEventFilter(self.filter)
        self._hotkey_ok = self._try_register(self.hotkey)
        self._pin_hotkey_ok = self._try_register_pin(self.pin_hotkey)
        self._rec_hotkey_ok = self._try_register_rec()
        self._update_hotkey_texts()
        self.main_window.show()

        # v28 启动预热：把首次截图才会触发的一次性开销（系统字体加载、工具条
        # 图标生成、全屏 QPainter 光栅化、PIL/GDI 抓屏后端初始化）挪到启动后
        # 的空闲时刻，避免第一次按热键时现做这些事、出现画面跟不上鼠标的卡顿。
        # singleShot(0) 让主窗口先绘制显示，预热在事件循环空闲时跑，不挡启动。
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._warmup)

    def _warmup(self) -> None:
        """v28：离屏空跑一次 Overlay 构造 + 绘制 + 抓屏，预热一次性资源。

        全程不 show 窗口、不影响用户；任何异常都吞掉，绝不让预热拖垮启动。
        """
        # 1) 构造隐藏 Overlay：触发 QFont/QFontMetrics、Toolbar/StylePanel/
        #    OcrPanel/OcrLayer 子控件与图标的一次性初始化。
        # 2) render 到离屏图：走一遍完整 paintEvent，预热 QPainter 光栅化管线、
        #    首帧 blit 与字体度量缓存。
        try:
            warm_img = QImage(64, 48, QImage.Format_RGB32)
            warm_img.fill(0xFF202020)
            probe = Overlay(warm_img, 1.0)
            probe.resize(64, 48)
            surface = QImage(64, 48, QImage.Format_RGB32)
            probe.render(surface)
            probe.deleteLater()
        except Exception:  # noqa: BLE001
            pass
        # 3) 抓 1×1 区域：初始化 PIL ImageGrab / GDI 后端，首次真截图不再现初始化
        try:
            snapback.grab_region(snapback.ScreenRect(0, 0, 1, 1))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ 热键
    def _try_register(self, hk: Hotkey) -> bool:
        """注销旧热键后注册 hk；失败时热键保持未注册状态，由调用方回滚。"""
        self._unregister_hotkey()
        if not hk.is_valid():
            return False
        ok = bool(user32.RegisterHotKey(None, HOTKEY_ID, hk.win_mods, hk.vk))
        self._hotkey_registered = ok
        return ok

    def _unregister_hotkey(self) -> None:
        if self._hotkey_registered:
            try:
                user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception:  # noqa: BLE001
                pass
        self._hotkey_registered = False

    def _try_register_pin(self, hk: Hotkey) -> bool:
        """v34：注册贴图热键（PIN_HOTKEY_ID）；失败时不影响截图热键。"""
        self._unregister_pin_hotkey()
        if not hk.is_valid():
            return False
        ok = bool(user32.RegisterHotKey(None, PIN_HOTKEY_ID, hk.win_mods, hk.vk))
        self._pin_hotkey_registered = ok
        return ok

    def _unregister_pin_hotkey(self) -> None:
        if getattr(self, "_pin_hotkey_registered", False):
            try:
                user32.UnregisterHotKey(None, PIN_HOTKEY_ID)
            except Exception:  # noqa: BLE001
                pass
        self._pin_hotkey_registered = False

    def _try_register_rec(self) -> bool:
        """v52：注册 F9 录屏热键（无需修饰键，与截图热键独立）。"""
        self._unregister_rec_hotkey()
        vk_f9 = 0x78
        mods = 0x4000  # MOD_NOREPEAT
        try:
            ok = bool(user32.RegisterHotKey(None, REC_HOTKEY_ID, mods, vk_f9))
        except Exception:  # noqa: BLE001
            ok = False
        self._rec_hotkey_registered = ok
        return ok

    def _unregister_rec_hotkey(self) -> None:
        if getattr(self, "_rec_hotkey_registered", False):
            try:
                user32.UnregisterHotKey(None, REC_HOTKEY_ID)
            except Exception:  # noqa: BLE001
                pass
        self._rec_hotkey_registered = False

    def _update_hotkey_texts(self) -> None:
        label = self.hotkey.label()
        self.act_capture.setText(t("截图  {label}", label=label))
        self.act_pin_clipboard.setText(
            t("贴出剪贴板图片  {label}", label=self.pin_hotkey.label())
        )
        self.tray.setToolTip(
            t("{app}（{label} 截图 · 右键可改热键）", app=app_name(), label=label)
        )
        self.main_window.set_hotkey(self.hotkey)
        self.main_window.set_pin_hotkey(self.pin_hotkey)

    def _retranslate_tray(self, _code: str = "") -> None:
        """语言切换后重建托盘菜单文案（截图项由 _update_hotkey_texts 带快捷键）。"""
        for key, text_key in (
            ("show", "显示主窗口"), ("hotkey", "设置热键…"),
            ("language", "语言…"), ("dir", "打开保存目录"),
            ("help", "使用说明…"), ("about", "关于…"), ("quit", "退出"),
            ("long_capture", "滚动长截图…"), ("record", "开始 / 停止录屏 (F9)"),
        ):
            self._tray_actions[key].setText(t(text_key))
        for mode in CAPTURE_MODES:
            self._tray_actions[f"mode_{mode}"].setText(mode_label(mode))
        self._update_hotkey_texts()

    def open_language_settings(self) -> None:
        """主窗口「设置 → 语言…」与托盘入口：选择 8 种语言或跟随系统。"""
        if self.overlay is not None:
            return  # 截图进行中不弹设置窗口
        dlg = LanguageDialog(self.main_window)
        dlg.exec()

    def _on_pen_smooth_changed(self, level: str) -> None:
        """主窗口「设置 → 画笔平滑度」：即时应用并持久化。"""
        if not set_pen_smooth(level):
            return
        self.pen_smooth = level
        save_pen_smooth(level)
        self._tray_message(
            app_name(),
            t("画笔平滑度已设为：{level}", level=t(PEN_SMOOTH_LABELS[level])),
            QSystemTrayIcon.Information,
            1500,
        )

    # ------------------------------------------------------------ 主窗口 / 帮助
    def show_main_window(self) -> None:
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _on_activate_request(self) -> None:
        """第二个实例启动时发来的唤醒请求：把主窗口与托盘图标都显出来。"""
        if self._quitting:
            return
        self.tray.setVisible(True)
        self.show_main_window()
        self._tray_message(
            app_name(), t("程序本来就在运行，已为你显示主窗口。"),
            QSystemTrayIcon.Information, 3000,
        )

    def _tray_message(self, title, msg, icon=QSystemTrayIcon.Information, msec=3000):
        """托盘气泡统一出口：程序正在退出时一律不显示任何通知。"""
        if self._quitting:
            return
        tray = self.tray
        tray.showMessage(title, msg, icon, msec)

    def _on_minimized(self) -> None:
        # 程序正在退出时不做任何显示（避免"已最小化到托盘，程序仍在运行"气泡）
        if self._quitting or self._minimize_hint_shown:
            return
        self._minimize_hint_shown = True
        self._tray_message(
            app_name(),
            t("已最小化到托盘，程序仍在运行。右键托盘可重新打开主窗口或退出。"),
            QSystemTrayIcon.Information,
            4000,
        )

    def show_help(self, topic: str = "help") -> None:
        if self._help_window is None:
            self._help_window = HelpWindow()
        self._help_window.show_topic(topic if isinstance(topic, str) else "help")
        self._help_window.show()
        self._help_window.raise_()
        self._help_window.activateWindow()

    def show_about(self) -> None:
        # 非模态单例：截图时能被一起隐藏，也不会阻塞事件循环。
        # AboutDialog 内含头像与联系邮箱，图标跟主窗口 / 托盘保持一致。
        if self._about_box is None:
            self._about_box = AboutDialog(
                self.main_window, self.main_window.windowIcon()
            )
        self._about_box.show()
        self._about_box.raise_()
        self._about_box.activateWindow()

    def _on_mode_changed(self, mode: str) -> None:
        if mode not in CAPTURE_MODES:
            return
        self.capture_mode = mode
        self.main_window.set_mode(mode)
        msg = t("默认截图模式已设为「{mode}」，热键与托盘截图将使用此模式",
                mode=mode_label(mode))
        if not save_mode(mode):
            msg += t("（配置写入失败，重启后会恢复）")
        self._tray_message(app_name(), msg, QSystemTrayIcon.Information, 3000)

    # ------------------------------------------------------------ 自有窗口显隐
    def _own_top_levels(self) -> list[QWidget]:
        """本进程所有顶层窗口，去重。

        除了主窗口 / 编辑器 / 预览窗，还包括浮动工具条、样式面板、取字面板、
        帮助与关于对话框等。截屏前它们都必须从屏幕上消失，否则会被拍进图里。
        """
        known = (
            self.main_window, self.preview, self.editor,
            self._help_window, self._about_box, self.busy,
        )
        out, seen = [], set()
        for w in list(known) + QApplication.topLevelWidgets():
            if w is None:
                continue
            key = id(w)
            if key in seen:
                continue
            seen.add(key)
            out.append(w)
        return out

    def _hide_visible_own_windows(self) -> None:
        """隐藏当前所有可见的自有窗口，并记下来供之后恢复。可重复调用。"""
        for w in self._own_top_levels():
            try:
                if not w.isVisible():
                    continue
                w.hide()
                if not any(x is w for x in self._hidden_windows):
                    self._hidden_windows.append(w)
            except RuntimeError:
                pass  # 窗口已被 C++ 层销毁

    def _hide_own_windows(self) -> None:
        """截图前隐藏自己的全部窗口，避免被拍进图里；结束后按原状态恢复。"""
        self._hidden_windows = []
        self._hide_visible_own_windows()

    def _restore_own_windows(self) -> None:
        for w in self._hidden_windows:
            try:
                w.show()
                w.raise_()
            except RuntimeError:
                pass  # 已被关闭 / 销毁的窗口不必再恢复
        self._hidden_windows = []

    def open_hotkey_settings(self) -> None:
        """托盘「设置热键…」：录制期间注销热键，退出时保证热键始终可用。"""
        if self.overlay is not None:
            return  # 截图进行中不弹设置窗口
        # 录制时用户按旧组合（如 Ctrl+Shift+A）不能把截图遮罩唤起来
        self._unregister_hotkey()
        try:
            for _ in range(10):
                dlg = HotkeyDialog(self.hotkey, None, app_name(), self._hk_error)
                if dlg.exec() != QDialog.Accepted:
                    break
                hk = dlg.hotkey
                if self._try_register(hk):
                    self.hotkey = hk
                    saved = save_hotkey(hk)
                    self._update_hotkey_texts()
                    msg = t("截图热键已改为 {label}", label=hk.label())
                    if not saved:
                        msg += t("（配置未能写入磁盘，重启后会恢复旧设置）")
                    self._tray_message(app_name(), msg, QSystemTrayIcon.Information, 3000)
                    break
                # 被其他程序占用 / 系统保留：让用户换一个，不改动旧设置
                self._hk_error = t(
                    "{label} 无法注册：可能已被其他程序占用，或属于系统保留组合。请换一个。",
                    label=hk.label(),
                )
        finally:
            self._hk_error = ""
            if not self._hotkey_registered:
                self._hotkey_ok = self._try_register(self.hotkey)
                if not self._hotkey_ok:
                    self._tray_message(
                        app_name(),
                        t("热键 {label} 注册失败，请用托盘右键菜单截图，或在「设置热键…」里换一个组合。",
                          label=self.hotkey.label()),
                        QSystemTrayIcon.Warning,
                        6000,
                    )

    def open_pin_hotkey_settings(self) -> None:
        """v34：设置贴图热键（把剪贴板图片贴到桌面）。录制期间注销该热键。"""
        from hotkeys import DEFAULT_PIN_MODS, DEFAULT_PIN_VK
        if self.overlay is not None:
            return
        self._unregister_pin_hotkey()
        default_pin = Hotkey(DEFAULT_PIN_MODS, DEFAULT_PIN_VK)
        try:
            for _ in range(10):
                dlg = HotkeyDialog(
                    self.pin_hotkey, None, app_name(), self._hk_error,
                    title_key="设置贴图热键 - {app}", default=default_pin,
                )
                if dlg.exec() != QDialog.Accepted:
                    break
                hk = dlg.hotkey
                if self._try_register_pin(hk):
                    self.pin_hotkey = hk
                    saved = save_pin_hotkey(hk)
                    self._update_hotkey_texts()
                    msg = t("贴图热键已改为 {label}", label=hk.label())
                    if not saved:
                        msg += t("（配置未能写入磁盘，重启后会恢复旧设置）")
                    self._tray_message(app_name(), msg, QSystemTrayIcon.Information, 3000)
                    break
                self._hk_error = t(
                    "{label} 无法注册：可能已被其他程序占用，或属于系统保留组合。请换一个。",
                    label=hk.label(),
                )
        finally:
            self._hk_error = ""
            if not self._pin_hotkey_registered:
                self._pin_hotkey_ok = self._try_register_pin(self.pin_hotkey)

    def _on_hotkey(self, hk_id: int) -> None:
        if hk_id == HOTKEY_ID:
            # 录制中屏蔽截图热键，避免遮罩覆盖录制画面
            if self.recorder.recording:
                return
            self.start_capture()
        elif hk_id == PIN_HOTKEY_ID:
            if self.recorder.recording:
                return
            self.pin_clipboard()
        elif hk_id == REC_HOTKEY_ID:
            self.toggle_record()

    def _on_tray(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            if self.recorder.recording:
                return
            self.start_capture()

    # ------------------------------------------------------------ v52 录屏
    def toggle_record(self) -> None:
        """F9：未在录→用默认方式开始；录制中→暂停/继续；已在暂停→继续。"""
        if self.recorder.recording:
            if self.recorder.paused:
                self._resume_record()
            else:
                self._pause_record()
            return
        self.start_record(None)

    def start_record(self, mode=None) -> None:
        """启动录屏。mode 为 None 时用录屏页的默认方式。"""
        if self.recorder.recording or self.overlay is not None or self.busy is not None:
            return
        if not isinstance(mode, str) or mode not in CAPTURE_MODES:
            panel = self.main_window.record_panel()
            mode = panel.rec_mode() if panel is not None else "rect"
        if mode == "fullscreen":
            # 整屏录制：无需选区，直接开始
            self._start_recording(None)
            return
        # 框选 / 窗口：用 Overlay 选区（复用截图那套遮罩交互）
        self._begin_capture(mode, long_mode=False, record=True)

    def _on_record_default_changed(self, mode: str) -> None:
        # 默认录屏方式由 recording_settings 自行持久化，这里只留信号兼容
        pass

    def _on_record_selected(self, logical_rect: QRect) -> None:
        """Overlay 选区回调：把局部逻辑矩形换成屏幕物理区域后开始录制。"""
        ov = self.overlay
        dpr = ov.dpr if ov else 1.0
        origin = getattr(self, "_capture_origin", QPoint(0, 0))
        if (logical_rect.isNull() or logical_rect.width() < 8
                or logical_rect.height() < 8):
            self._close_overlay()
            return
        rect = overlay_rect_to_screen(logical_rect, origin, dpr)
        self._close_overlay(restore=False)   # 录制期间自有窗口保持隐藏
        region = {"x": rect.x, "y": rect.y, "width": rect.w, "height": rect.h}
        self._start_recording(region, restore_windows=False)

    def _start_recording(self, region: dict | None, restore_windows: bool = True) -> None:
        """弹出音频确认 → 收集设置 → 启动录制线程 → 隐藏窗口并显示红框/控制条。"""
        # 每次录制前确认音频保存方式
        try:
            dlg = AudioChoiceDialog(None, self._rec_audio_choice)
            if dlg.exec() != QDialog.Accepted:
                if restore_windows:
                    self._restore_own_windows()
                return
            self._rec_audio_choice = dlg.choice()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(None, app_name(), f"音频设置失败：{exc}")
            if restore_windows:
                self._restore_own_windows()
            return

        panel = self.main_window.record_panel()
        settings = panel.collect_settings() if panel is not None else {}
        settings["audio_in_video"] = self._rec_audio_choice[0]
        settings["audio_mode"] = self._rec_audio_choice[1]
        settings["audio_separate"] = self._rec_audio_choice[2]

        # 隐藏自有窗口（整屏路径此时还没隐藏；框选路径已隐藏）
        if restore_windows:
            self._hide_own_windows()
            self.tray.setVisible(False)
            for _ in range(4):
                self.app.processEvents()
                time.sleep(0.05)
                self._hide_visible_own_windows()
            self.app.processEvents()

        if not self.recorder.start(region, settings):
            self.tray.setVisible(True)
            self._restore_own_windows()
            return

    def _on_rec_started(self) -> None:
        """录制真正开始：显示红框 + 悬浮控制条。"""
        self.tray.setVisible(True)
        # 红框：整屏用虚拟屏范围，区域用 region
        vs = snapback.virtual_screen()
        dpr = self.app.primaryScreen().devicePixelRatio() or 1.0
        screen = QRect(int(round(vs.x / dpr)), int(round(vs.y / dpr)),
                       max(1, int(round(vs.w / dpr))), max(1, int(round(vs.h / dpr))))
        self._rec_border = RecordBorder(screen)
        self._rec_border.show()
        labels = []
        settings = self._rec_audio_choice
        if settings[0] or settings[2]:
            labels.append(t("系统声"))
        if self.recorder._settings.get("mic"):
            labels.append(t("麦克风"))
        self._rec_bar = RecordControlBar()
        self._rec_bar.set_audio_labels(labels)
        self._rec_bar.pause_clicked.connect(self._pause_record)
        self._rec_bar.stop_clicked.connect(self.stop_record)
        self._rec_bar.show()
        self._place_rec_bar()

    def _place_rec_bar(self) -> None:
        if self._rec_bar is None:
            return
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        self._rec_bar.adjustSize()
        w, h = self._rec_bar.width(), self._rec_bar.height()
        self._rec_bar.move(avail.left() + (avail.width() - w) // 2,
                           avail.bottom() - h - 40)

    def _pause_record(self) -> None:
        if self.recorder.toggle_pause():
            if self._rec_bar:
                self._rec_bar.set_paused(True)

    def _resume_record(self) -> None:
        if self.recorder.toggle_pause():
            return
        if self._rec_bar:
            self._rec_bar.set_paused(False)

    def stop_record(self) -> None:
        self.recorder.stop()
        if self._rec_bar:
            self._rec_bar.setEnabled(False)

    def _on_rec_levels(self, levels: dict) -> None:
        if self._rec_bar:
            self._rec_bar.update_levels(levels)

    def _on_rec_stopped(self, path: str) -> None:
        self._tray_message(app_name(), t("录屏已保存：{path}", path=path),
                           QSystemTrayIcon.Information, 3000)

    def _on_rec_error(self, msg: str) -> None:
        self._tray_message(app_name(), msg, QSystemTrayIcon.Warning, 4000)

    def _on_rec_finalized(self) -> None:
        """合成结束：收起控制条和红框，恢复主窗口。"""
        if self._rec_bar:
            self._rec_bar.hide()
            self._rec_bar.deleteLater()
            self._rec_bar = None
        if self._rec_border:
            self._rec_border.hide()
            self._rec_border.deleteLater()
            self._rec_border = None
        self._restore_own_windows()
        self._rec_paused = False

    def _open_record_dir(self) -> None:
        from recording_settings import load_save_dir
        path = load_save_dir()
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except OSError as exc:
            QMessageBox.warning(None, app_name(), str(exc))

    # ------------------------------------------------------------ 截图
    def start_capture(self, mode=None) -> None:
        """开始截图。mode 为 None 或非字符串时用默认模式（QAction.triggered 会传 bool）。"""
        # 滚动长截图拼接期间 busy 是控制条（overlay 已关），此时热键 / 托盘
        # 再触发普通截图会把控制条一起隐藏并打断拼接，必须一并挡住。
        if self.overlay is not None or self.busy is not None:
            return
        if not isinstance(mode, str) or mode not in CAPTURE_MODES:
            mode = self.capture_mode
        self._begin_capture(mode, long_mode=False)

    def start_ocr_capture(self) -> None:
        """v38：框选一个区域后直接取字（不打开编辑器）。"""
        if self.overlay is not None or self.busy is not None:
            return
        self._begin_capture("rect", long_mode=False)
        if self.overlay is not None:
            self.overlay.set_auto_ocr(True)

    def start_long_capture(self) -> None:
        """独立命令「滚动长截图」：悬停选窗口 → 单击即自动向下滚屏拼接。

        与普通截图共用隐藏窗口 / 抓屏 / 遮罩，但走窗口探测模式；单击
        窗口后 Overlay.long_shot 直接把客户区交给 _on_long_shot 启动
        StitchWorker，不进编辑器、也不再点「确定」。
        """
        if self.overlay is not None or self.busy is not None:
            return
        self._begin_capture("window", long_mode=True)

    def _begin_capture(self, mode: str, long_mode: bool, record: bool = False) -> None:
        """隐藏自有窗口 → 抓一帧底图 → 显示遮罩（普通截图 / 长截图 / 录屏共用）。"""
        # 先把自己的窗口全部藏起来，避免拍进截图里
        self._hide_own_windows()
        self.tray.setVisible(False)
        # hide() 之后 Windows 合成器还有淡出动画，残留的半透明窗口影子会
        # 被拍进截图。分多轮刷新 + 等待，让屏幕合成完成；期间若又有自有
        # 窗口冒出来（迟到重绘 / 子面板），一并补隐藏后再抓屏。
        for _ in range(6):
            self.app.processEvents()
            time.sleep(0.06)
            self._hide_visible_own_windows()
        self.app.processEvents()

        try:
            pil = snapback.grab_all_screens()
        except Exception as exc:  # noqa: BLE001
            self.tray.setVisible(True)
            self._restore_own_windows()
            QMessageBox.warning(None, app_name(), t("截屏失败：{error}", error=exc))
            return

        self.tray.setVisible(True)

        qimg = pil_to_qimage(pil)

        # 全屏：截完直接进窗口化编辑器，不需选择 / 确定这一步
        # v52：录屏全屏不走这里（已在 start_record 直接启动录制）
        if mode == "fullscreen" and not long_mode and not record:
            self._on_to_editor(qimg, [])
            return

        phys = snapback.virtual_screen()
        screen = self.app.primaryScreen()
        dpr = screen.devicePixelRatio() or 1.0
        # 记下 Overlay 左上角对应的全局逻辑坐标：长截图要在真实屏幕上滚动，
        # 「确定」时遮罩已 hide，不能再依赖 mapToGlobal 的结果。
        self._capture_origin = QPoint(
            int(round(phys.x / dpr)), int(round(phys.y / dpr))
        )

        self.overlay = Overlay(qimg, dpr)
        self.overlay.setGeometry(
            QRect(
                int(round(phys.x / dpr)),
                int(round(phys.y / dpr)),
                max(1, int(round(phys.w / dpr))),
                max(1, int(round(phys.h / dpr))),
            )
        )
        # 普通截图：框选 / 窗口（悬停高亮单击）/ 全屏（自动选中整个虚拟屏幕）
        # 滚动长截图：固定走窗口探测，用客户区作为滚动区域（不含标题栏/边框）
        if record:
            self.overlay.set_record_mode(
                True, lambda p: self._pick_window(p, client=False)
            )
        elif long_mode:
            self.overlay.set_long_mode(
                True, lambda p: self._pick_window(p, client=True)
            )
        else:
            self.overlay.set_capture_mode(mode, self._pick_window)
            if mode == "window":
                # v35：普通窗口截图选中窗口时，前置目标并重抓一帧最新底图
                self.overlay.set_window_regrab(self._regrab_window_base)
        self.overlay.record_selected.connect(self._on_record_selected)
        self.overlay.done.connect(self._on_done)
        self.overlay.cancelled.connect(self._on_cancel)
        self.overlay.long_shot.connect(self._on_long_shot)
        self.overlay.ocr.connect(self._on_ocr)
        self.overlay.save_requested.connect(self._save_image)
        self.overlay.to_editor.connect(self._on_to_editor)
        self.overlay.copy_only.connect(self._on_copy_only)
        self.overlay.pin_requested.connect(self._on_pin_requested)

        # v28 输入门闩：show 之前先上闩，屏蔽鼠标并显示等待光标。
        self.overlay.lock_input()
        # 用 setGeometry + show 而不是 showFullScreen：
        # 后者只覆盖主屏，多显示器下会漏掉其他屏幕。
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.overlay.setFocus()
        # v28 首帧同步绘制：show() 只把窗口排队等事件循环绘制，直接返回时
        # 画面还没上屏，鼠标却能操作，导致「框选完了画面才跳出来」。
        # repaint() 同步触发 paintEvent 立即画完首帧，其末尾会解锁输入。
        self.overlay.repaint()

    def _pick_window(self, pos: QPoint, client: bool = False):
        """Overlay 局部逻辑坐标 → 物理坐标 → Win32 窗口枚举 → 逻辑矩形。

        client=True 时改用窗口客户区（去掉标题栏 / 边框），滚动拼接时
        固定的标题栏不会混进每一帧，模板匹配更准；取不到客户区就退回
        可见边框。普通窗口截图仍用完整边框。
        """
        ov = self.overlay
        if ov is None:
            return None
        dpr = ov.dpr or 1.0
        gp = ov.mapToGlobal(pos)
        origin = ov.mapToGlobal(QPoint(0, 0))
        # v35：按光标所在屏的 dpr 换算物理点，混合 DPI 多屏不再命中错窗口
        px, py = global_logical_to_physical(gp, dpr)
        info = snapback.window_rect_at(px, py)
        if info is None:
            return None
        frame = info.rect
        r = frame
        if client and info.client is not None:
            c = info.client
            x0, y0 = max(frame.x, c.x), max(frame.y, c.y)
            x1 = min(frame.x + frame.w, c.x + c.w)
            y1 = min(frame.y + frame.h, c.y + c.h)
            if x1 - x0 >= 60 and y1 - y0 >= 40:
                r = snapback.ScreenRect(x0, y0, x1 - x0, y1 - y0)
        q = QRect(
            int(round(r.x / dpr)) - origin.x(),
            int(round(r.y / dpr)) - origin.y(),
            max(1, int(round(r.w / dpr))),
            max(1, int(round(r.h / dpr))),
        ).intersected(ov.rect())
        if q.width() < 8 or q.height() < 8:
            return None
        # v35：附带 hwnd，供「点击窗口时前置目标并重抓底图」使用
        return (q, info.title, info.hwnd)

    def _regrab_window_base(self, hwnd: int = 0):
        """v35：选中窗口后重抓一帧底图（解决截到旧画面 / 遮挡物）。

        流程：尽力前置目标窗口 → 临时隐藏遮罩 → 等合成稳定 → 重新抓屏 →
        恢复遮罩。返回的 QImage 交给 Overlay.update_base 原子替换底图。
        任何异常都降级为「保留旧底图」，不影响截图主流程。
        """
        ov = getattr(self, "overlay", None)
        if ov is None:
            return None
        if hwnd:
            snapback.foreground_window(int(hwnd))
        was_visible = False
        try:
            was_visible = bool(ov.isVisible())
            if was_visible:
                ov.hide()
            self.app.processEvents()
            time.sleep(0.10)   # 给 Windows 合成器与目标窗口重绘一点时间
            self.app.processEvents()
            fresh = snapback.grab_all_screens()
        except Exception:  # noqa: BLE001
            return None
        finally:
            if was_visible:
                try:
                    ov.show()
                    ov.raise_()
                    ov.activateWindow()
                    self.app.processEvents()
                except Exception:  # noqa: BLE001
                    pass
        return pil_to_qimage(fresh)

    def _close_overlay(self, *, restore: bool = True) -> None:
        # 遮罩关闭时取字任务的结果已无处展示，同时解除 busy 锁，
        # 否则用户按 Esc 取消后下次取字会被永久挡住。
        # restore=False 用于长截图（拼接期间主窗口等自有窗口必须保持隐藏，
        # 否则每一帧都会把它们拍进长图）与 v27 复制路径（复制即收起全部窗口，
        # 由调用方自行管理显隐，不能再把截图前隐藏的窗口恢复出来）。
        self._ocr_busy = False
        if self.overlay:
            self.overlay.deleteLater()
            self.overlay = None
        if restore:
            self._restore_own_windows()

    def _on_cancel(self) -> None:
        self._close_overlay()

    @staticmethod
    def _copy_to_clipboard(img: QImage) -> None:
        """把图像放进系统剪贴板。剪贴板被别的程序锁住时静默跳过，
        不让一次复制失败拖垮截图主流程。"""
        try:
            QApplication.clipboard().setImage(img)
        except Exception:  # noqa: BLE001
            pass

    def _on_copy_only(self, img: QImage) -> None:
        """遮罩确认阶段点「复制」：复制原图，并关闭截图编辑 / 截屏助手两个窗口。

        v27：复制 = 彻底收起界面，只留托盘常驻；需要标注时再用热键截图并
        点「确定」打开编辑器。这里不能用默认的 _close_overlay(restore=True)，
        否则截图前隐藏的主窗口 / 旧编辑器会被重新显示出来。
        """
        self._copy_to_clipboard(img)
        self._close_overlay(restore=False)
        self._close_editor_silently()
        self.main_window.hide()
        self._hidden_windows = []
        self._tray_message(
            app_name(),
            t("已复制到剪贴板  {w}×{h}", w=img.width(), h=img.height()),
            QSystemTrayIcon.Information,
            1800,
        )

    # ------------------------------------------------------------ 贴图钉在桌面（v34）
    def _pin_image(self, img: QImage) -> PinWindow | None:
        """把当前图像贴成桌面浮窗。四入口（工具条/编辑器/托盘/热键）统一走这里。"""
        if img.isNull():
            return None
        dpr = self.app.primaryScreen().devicePixelRatio() or 1.0
        pin = PinWindow(img, dpr)
        pin.closed.connect(lambda: self._on_pin_closed(pin))
        self.pins.append(pin)
        pin.show()
        pin.raise_()
        return pin

    def _on_pin_closed(self, pin: PinWindow) -> None:
        if pin in self.pins:
            self.pins.remove(pin)

    def _on_pin_requested(self, img: QImage) -> None:
        """截图确认阶段点「钉在桌面」：贴图并收起截图界面 / 编辑器 / 主窗口。"""
        self._pin_image(img)
        self._close_overlay(restore=False)
        self._close_editor_silently()
        self.main_window.hide()
        self._hidden_windows = []
        self._tray_message(
            app_name(), t("已把截图钉在桌面  {w}×{h}", w=img.width(), h=img.height()),
            QSystemTrayIcon.Information, 1800,
        )

    def _on_editor_pin(self, img: QImage) -> None:
        """窗口化编辑器里点「钉在桌面」：贴图，编辑器保持打开可继续编辑。"""
        self._pin_image(img)
        self._tray_message(
            app_name(), t("已把截图钉在桌面  {w}×{h}", w=img.width(), h=img.height()),
            QSystemTrayIcon.Information, 1800,
        )

    def pin_clipboard(self) -> None:
        """托盘「贴出剪贴板图片」/ 贴图热键：把剪贴板里的图片贴到桌面。"""
        img = QApplication.clipboard().image()
        if img.isNull():
            self._tray_message(
                app_name(), t("剪贴板里没有图片，无法贴图。"),
                QSystemTrayIcon.Warning, 2200,
            )
            return
        self._pin_image(img)
        self._tray_message(
            app_name(), t("已把剪贴板图片钉在桌面  {w}×{h}", w=img.width(), h=img.height()),
            QSystemTrayIcon.Information, 1800,
        )

    def _on_done(self, img: QImage) -> None:
        self._copy_to_clipboard(img)
        self._close_overlay()
        self._tray_message(
            app_name(),
            t("已复制到剪贴板  {w}×{h}", w=img.width(), h=img.height()),
            QSystemTrayIcon.Information,
            1800,
        )

    def _save_image(self, img: QImage) -> None:
        default = self.save_dir / f"{t('截图_')}{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            None, t("保存截图"), str(default), t("PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        )
        if not path:
            return
        try:
            save_qimage(img, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(None, app_name(), str(exc))
            return
        self._close_overlay()
        self._tray_message(app_name(), t("已保存：{path}", path=path), QSystemTrayIcon.Information, 2200)

    # ------------------------------------------------------------ 长截图
    def _on_long_shot(self, logical_rect: QRect) -> None:
        """Overlay 交来的窗口客户区（局部逻辑）→ 屏幕物理矩形 → 自动滚屏拼接。

        控制条必须先摆好再启动线程：左键过滤区、抓帧隐藏钩子都依赖它的几何。
        """
        if (
            logical_rect.isNull()
            or logical_rect.width() < 8
            or logical_rect.height() < 8
        ):
            self._close_overlay()
            return
        ov = self.overlay
        dpr = ov.dpr if ov else 1.0
        origin = getattr(self, "_capture_origin", QPoint(0, 0))
        # 虚拟屏幕原点在多显示器下可能是负数，叠加 Overlay 全局原点再乘 dpr，
        # 否则副屏上的窗口会整体偏移，滚到错误的位置。
        rect = overlay_rect_to_screen(logical_rect, origin, dpr)
        # 拼接是逐帧抓屏：主窗口 / 帮助 / 关于等自有窗口若在拼接期间恢复，
        # 会被一帧一帧拍进长图。这里只关闭遮罩，等拼接结束再统一恢复。
        self._close_overlay(restore=False)

        self.busy = BusyBar()
        bw, bh = self.busy.width(), self.busy.height()
        sel = QRect(
            logical_rect.x() + origin.x(),
            logical_rect.y() + origin.y(),
            logical_rect.width(),
            logical_rect.height(),
        )
        vs = snapback.virtual_screen()
        screen = QRect(
            int(round(vs.x / dpr)),
            int(round(vs.y / dpr)),
            int(round(vs.w / dpr)),
            int(round(vs.h / dpr)),
        )
        # v51：恢复 v48 的摆位（控制条放窗口外，避免被拍进长图）。
        # v49/v50 改成跟鼠标走 + 按「光标是否在控制条内」决定是否发滚轮，
        # 实际导致页面完全不滚；确定按钮也一并去掉，改用右键 / Esc 结束。
        pos = place_bar_outside(sel, screen, bw, bh)
        outside = pos is not None
        if not outside:
            # 窗口占满整个虚拟屏：控制条只能放在角落，改由抓帧瞬间隐藏兜底
            pos = QRect(screen.left() + 8, screen.top() + 8, bw, bh)
        self.busy.move(pos.topLeft())
        self.busy.show()

        control = snapback.ScrollControl()
        r = bar_screen_rect(self.busy, dpr)
        m = int(round(10 * dpr))   # 放宽一圈，点边框附近也不算「页面内点击」
        control.set_exclude_rect(
            snapback.ScreenRect(r.x - m, r.y - m, r.w + 2 * m, r.h + 2 * m)
        )

        worker = StitchWorker(rect, control)
        if not outside:
            worker.before_grab = make_bar_hook(self.busy, "hide")
            worker.after_grab = make_bar_hook(self.busy, "show")
        worker.progress.connect(self.busy.update_text)
        worker.state_changed.connect(self.busy.set_paused)

        def on_ok(pil_img, stats) -> None:
            self._close_busy()
            self._restore_own_windows()
            qimg = pil_to_qimage(pil_img)
            # v26：长截图完成也自动进剪贴板
            self._copy_to_clipboard(qimg)
            # v49：不再只弹「预览」窗口（只能复制/保存/关闭，没法标注），
            # 直接开编辑器，和普通截图走同一套标注 / 复制 / 保存流程。
            self._open_editor(qimg, [])
            # v19：把「为什么结束」讲清楚，方便区分真到底与异常中断
            reason = stats.get("stop_reason")
            frames = stats.get("frames", 0)
            height = stats.get("height", 0)
            score = f"{float(stats.get('score', 0.0)):.2f}"
            early = {
                "match-failed": t("内容无法自动对齐"),
                "no-overlap": t("内容无法自动对齐"),
                "no-new-content": t("页面没有新增内容"),
                "max-frames": t("帧数已达上限"),
                "max-height": t("高度已达上限"),
            }
            if reason in early:
                self._tray_message(
                    app_name(),
                    t("长截图提前结束：{reason} · 共 {frames} 帧 · 匹配 {score}",
                      reason=early[reason], frames=frames, score=score),
                    QSystemTrayIcon.Warning, 6000,
                )
            else:
                self._tray_message(
                    app_name(),
                    t("长截图完成 · 共 {frames} 帧 · {height}px",
                      frames=frames, height=height),
                    QSystemTrayIcon.Information, 2600,
                )

        def on_fail(msg: str) -> None:
            self._close_busy()
            self._restore_own_windows()
            QMessageBox.warning(None, app_name(), t("长截图失败：{error}", error=msg))

        worker.ok.connect(on_ok)
        worker.failed.connect(on_fail)
        worker.finished.connect(lambda: self._reap(worker))
        self._workers.append(worker)
        worker.start()

    def _close_busy(self) -> None:
        if self.busy:
            self.busy.hide()
            self.busy.deleteLater()
            self.busy = None

    # ------------------------------------------------------------ OCR
    def _on_ocr(self, img: QImage) -> None:
        """取字：遮罩保持显示，结果逐行盖回原文位置；可拖选/复制，复制后自动收起。"""
        if img.isNull() or self.overlay is None or self._ocr_busy:
            return
        self._ocr_busy = True
        overlay = self.overlay      # 回调时确认遮罩没被用户在识别期间取消
        overlay.show_ocr_busy()
        worker = OcrWorker(img)

        def on_ok(lines: list, backend: str) -> None:
            if self.overlay is not overlay:
                return
            self._ocr_busy = False
            if lines:
                overlay.show_ocr_lines(lines, backend)
            else:
                overlay.show_ocr_message(t("没有识别到文字。"))

        def on_fail(msg: str) -> None:
            if self.overlay is not overlay:
                return
            self._ocr_busy = False
            overlay.show_ocr_message(
                t("OCR 不可用：{error}\n\n请确认已安装 OCR 依赖（rapidocr / onnxruntime）。",
                  error=msg)
            )

        worker.ok.connect(on_ok)
        worker.failed.connect(on_fail)
        worker.finished.connect(lambda: self._reap(worker))
        self._workers.append(worker)
        worker.start()

    # ------------------------------------------------------------ 窗口化编辑器
    def _on_to_editor(self, base_img: QImage, shapes: list) -> None:
        """选定截图（框选/窗口确认，或全屏直截）→ 打开窗口化编辑器继续编辑。

        不在这里恢复自身窗口：它们应保持隐藏，直到编辑器关闭。
        v26：完成瞬间先把原图放进剪贴板，用户可直接 Ctrl+V；若之后在编辑器
        里加了标注，再用 Ctrl+Enter / 「复制到剪贴板」按钮更新成最终图。
        """
        # v26 自动复制：此处拿到的是刚截下的原图，不含后续标注
        self._copy_to_clipboard(base_img)
        self._tray_message(
            app_name(),
            t("已复制到剪贴板  {w}×{h}", w=base_img.width(), h=base_img.height()),
            QSystemTrayIcon.Information,
            1800,
        )
        self._ocr_busy = False
        if self.overlay is not None:
            self.overlay.deleteLater()
            self.overlay = None
        # 编辑器是一个普通程序窗口：隐藏主窗口，避免两个窗口叠在一起
        self.main_window.hide()
        # 本次截图会打开新编辑器，旧编辑器不要留在「待恢复」列表里，
        # 否则新编辑器关闭后，恢复逻辑会把已经关掉的旧窗口重新弹出来。
        self._hidden_windows = [
            w for w in self._hidden_windows if w is not self.editor
        ]
        self._open_editor(base_img, shapes)

    def _close_editor_silently(self) -> None:
        """关闭当前编辑器，但不触发「编辑器关闭 → 恢复主窗口」流程。

        v27 两条路径都用到：点复制要收起全部窗口；点打勾要直接开新编辑器。
        若让旧编辑器的 closed 信号走 _on_editor_closed，主窗口会被弹回来。
        """
        editor = self.editor
        self.editor = None
        if editor is None:
            return
        try:
            editor.closed.disconnect(self._on_editor_closed)
        except (RuntimeError, TypeError):
            pass
        try:
            editor.close()
            editor.deleteLater()
        except RuntimeError:
            pass

    def _open_editor(self, base_img: QImage, shapes: list) -> None:
        self._close_editor_silently()
        editor = EditorWindow(base_img, shapes, self.save_dir)
        self.editor = editor
        editor.copy_requested.connect(self._on_editor_copy)
        editor.save_requested.connect(self._on_editor_save)
        editor.ocr_requested.connect(self._on_editor_ocr)
        editor.pin_requested.connect(self._on_editor_pin)
        editor.closed.connect(self._on_editor_closed)
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _on_editor_copy(self, img: QImage) -> None:
        QApplication.clipboard().setImage(img)
        self._tray_message(
            app_name(),
            t("已复制到剪贴板  {w}×{h}", w=img.width(), h=img.height()),
            QSystemTrayIcon.Information,
            1800,
        )

    def _on_editor_save(self, img: QImage) -> None:
        if self.editor is None:
            return
        default = self.save_dir / f"{t('截图_')}{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            None, t("保存截图"), str(default), t("PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        )
        if not path:
            return
        try:
            save_qimage(img, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(None, app_name(), str(exc))
            return
        self._tray_message(app_name(), t("已保存：{path}", path=path), QSystemTrayIcon.Information, 2200)

    def _on_editor_ocr(self, img: QImage) -> None:
        """窗口化编辑器里取字：结果逐行盖回原文位置（方案 B）。"""
        if self._ocr_busy or self.editor is None:
            return
        self._ocr_busy = True
        self.editor.show_ocr_busy()
        worker = OcrWorker(img)

        def on_ok(lines: list, backend: str) -> None:
            self._ocr_busy = False
            if self.editor is None:
                return
            if lines:
                # 保留每行的 bbox 交给编辑器，按原图位置逐行盖回
                self.editor.show_ocr_lines(lines, backend)
            else:
                self.editor.show_ocr_message(t("没有识别到文字。"))

        def on_fail(msg: str) -> None:
            self._ocr_busy = False
            if self.editor is not None:
                self.editor.show_ocr_message(
                    t("OCR 不可用：{error}\n\n请确认已安装 OCR 依赖（rapidocr / onnxruntime）。",
                      error=msg)
                )

        worker.ok.connect(on_ok)
        worker.failed.connect(on_fail)
        worker.finished.connect(lambda: self._reap(worker))
        self._workers.append(worker)
        worker.start()

    def _on_editor_closed(self) -> None:
        if self.editor is not None:
            self.editor.close()
            self.editor = None
        # 编辑器关闭后，恢复截图前被隐藏的自身窗口，并把主窗口重新显示出来
        self._restore_own_windows()
        self.show_main_window()

    def _reap(self, worker: QThread) -> None:
        if worker in self._workers:
            self._workers.remove(worker)

    # ------------------------------------------------------------ 杂项
    def _open_save_dir(self) -> None:
        try:
            subprocess.Popen(["explorer", str(self.save_dir)])
        except Exception:  # noqa: BLE001
            pass

    def quit(self) -> None:
        """彻底退出程序：安静收尾，不弹任何托盘气泡 / 提示窗口。"""
        if self._quitting:
            return
        self._quitting = True
        singleinstance.release()
        # 1) 让主窗口（及其它自有窗口）允许被真正关闭，closeEvent 不再
        #    「最小化到托盘」并弹"程序仍在运行"的气泡。
        self.main_window._allow_close = True
        # 2) 撤掉托盘图标与当前仍挂在通知区的气泡，退出过程不留任何显示。
        try:
            self.tray.setVisible(False)
        except Exception:  # noqa: BLE001
            pass
        # 3) 收起所有贴图浮窗、注销全局热键后退出事件循环
        #    （部分自测会不完全构造 App，用 getattr 兜底避免 AttributeError）
        for pin in list(getattr(self, "pins", [])):
            try:
                pin.close()
            except RuntimeError:  # noqa: BLE001
                pass
        self.pins = []
        self._unregister_hotkey()
        self._unregister_pin_hotkey()
        self._unregister_rec_hotkey()
        # v52：录制中退出则停止并等待合成线程收尾（最多 10 秒）
        if getattr(self, "recorder", None) and self.recorder.recording:
            self.recorder.stop()
            deadline = time.monotonic() + 10
            while self.recorder._finalizing and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.05)
        self.app.quit()


# ---------------------------------------------------------------------------
def _run_selftest() -> int:
    """不进入 GUI 的自检：依赖 + OCR 后端可用性。

    结果同时打印到 stdout 和写入 %APPDATA%/SnapTool/selftest.log —— 打包成
    --windowed exe 后没有控制台，靠这份日志验证产物是否完整（模型/DLL 是否收齐）。
    """
    import importlib

    out: list[str] = [
        f"{app_name()}{t(' 自检 ')}{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"python    : {sys.version.split()[0]}",
        f"frozen    : {bool(getattr(sys, 'frozen', False))}",
        f"executable: {sys.executable}",
    ]
    ok = True
    for mod in ("PySide6", "PIL", "numpy", "rapidocr", "onnxruntime"):
        try:
            m = importlib.import_module(mod)
            out.append(f"[OK]   import {mod:12s} {getattr(m, '__version__', '')}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            out.append(f"[FAIL] import {mod:12s} {type(exc).__name__}: {exc}")
    for mod in ("cv2", "paddleocr", "pytesseract"):
        try:
            importlib.import_module(mod)
            out.append(f"[ok]   optional {mod}{t(' 可用')}")
        except Exception:  # noqa: BLE001
            out.append(f"[--]   optional {mod}{t(' 未安装（对应功能不可用）')}")

    try:
        base = getattr(sys, "_MEIPASS", None) or str(Path(__file__).resolve().parent)
        png = Path(base) / "ocr_test.png"
        out.append(f"{t('测试图   : ')}{png} (exists={png.is_file()})")
        if not png.is_file():
            ok = False
            out.append(t("[FAIL] 找不到 ocr_test.png"))
        else:
            from PIL import Image

            lines, backend = snapback.ocr_image_lines(Image.open(png).convert("RGB"))
            out.append(f"[OK]   OCR backend={backend} lines={len(lines)}")
            for d in lines[:5]:
                out.append(
                    f"       {d['text']!r} box={d['box']} score={d['score']:.3f}"
                )
            if not lines:
                ok = False
                out.append(t("[FAIL] OCR 返回 0 行"))
    except Exception as exc:  # noqa: BLE001
        ok = False
        out.append(f"[FAIL] OCR: {type(exc).__name__}: {exc}")

    out.append(f"RESULT: {'PASS' if ok else 'FAIL'}")
    text = "\n".join(out)
    log = (
        Path(os.environ.get("APPDATA") or os.path.expanduser("~"))
        / "SnapTool"
        / "selftest.log"
    )
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(text, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    # frozen(--windowed) exe 没有控制台，stdout 编码与终端不一致会输出乱码，
    # 发行版一律以日志文件为准；源码模式才额外打印到控制台。
    if getattr(sys, "stdout", None) is not None and not getattr(sys, "frozen", False):
        print(text)
        print(t("[selftest] 日志：{log}", log=log))
    return 0 if ok else 1


def _resolve_existing_instance(st, restart: bool) -> bool:
    """检测到已有实例：默认直接唤醒其主窗口，不弹框、不重启。

    返回 True 表示继续启动新实例（仅显式 --restart 时才走这条路径）。
    默认路径只请老实例把主窗口显示出来，然后结束本次新进程 —— 用户重复
    双击程序时只是把窗口调出来，不再弹「是否结束它并重新启动」的对话框。
    """
    rec = st.record or {}
    pid = rec.get("pid", "?")
    woken = singleinstance.signal_existing()
    singleinstance.log(f"已有实例 pid={pid} 唤醒={woken} restart={restart}")

    if not restart:
        # signal_existing() 已通过激活通知请老实例显示主窗口；本进程直接退出。
        return False

    killed = singleinstance.kill_recorded(rec)
    singleinstance.log(f"结束后台实例结果={killed}")
    if not killed:
        ctypes.windll.user32.MessageBoxW(
            None,
            t("结束后台实例未成功，但仍会尝试继续启动。\n若再次提示已在运行，请在任务管理器里结束残留的 pythonw.exe。"),
            app_name(), 0x30 | 0x40000,
        )
    time.sleep(0.25)
    again = singleinstance.probe()
    singleinstance.log(f"重启后 probe -> {again.state}/{again.reason}")
    if again.state == "running":
        ctypes.windll.user32.MessageBoxW(
            None,
            t("仍有实例占用，启动中止。请在任务管理器中结束所有 pythonw.exe 后重试，或双击 restart.bat。"),
            app_name(), 0x10 | 0x40000,
        )
        return False
    return True


def main() -> int:
    # 启动时加载语言偏好：auto 会按 Windows 显示语言解析，未支持语言回退英文
    LANG.reload()
    # --help 不进入 Qt，也不检查单实例；pythonw 无控制台时改用系统弹窗
    if any(a in ("-h", "--help", "/?") for a in sys.argv[1:]):
        text = cli_help(name=app_name())
        if getattr(sys, "stdout", None) is None:
            ctypes.windll.user32.MessageBoxW(
                None, text, t("{app} - 命令行说明", app=app_name()), 0x40
            )
        else:
            print(text)
        return 0

    # --selftest 不建 QApplication、不检查单实例，供打包产物做冒烟验证
    if "--selftest" in sys.argv[1:]:
        return _run_selftest()

    snapback.set_dpi_awareness()
    restart = "--restart" in sys.argv[1:]
    if restart:
        # 旧版本不写实例记录，只靠锁找不到那些「活着但没界面」的幽灵进程；
        # 这里按命令行主动清一遍，避免它们继续占用全局热键。
        killed = singleinstance.kill_other_instances()
        if killed:
            singleinstance.log(f"--restart 共清理 {len(killed)} 个残留进程：{killed}")
            time.sleep(0.25)
    st = singleinstance.probe()
    if st.state == "running":
        if not _resolve_existing_instance(st, restart):
            return 0
    elif st.state == "stale":
        # 锁还在但记录里的进程已经不在（异常退出 / 残留后台进程）：静默接管
        singleinstance.log("检测到陈旧锁，已自动接管，不再提示「已在运行」")

    app = QApplication(sys.argv)
    app.setApplicationName(app_name())
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, app_name(), t("系统托盘不可用，无法常驻运行。"))
        return 2

    ctrl = App(app)
    app._ctrl = ctrl  # 防止被回收

    if "--shot" in sys.argv:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(120, ctrl.start_capture)
    elif not ctrl._hotkey_ok:
        ctrl.tray.showMessage(
            app_name(),
            t("全局热键 {label} 注册失败（可能被其他程序占用）。请在主窗口或托盘菜单「设置热键…」换一个组合，也可直接点主窗口的截图按钮。",
              label=ctrl.hotkey.label()),
            QSystemTrayIcon.Warning,
            8000,
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
