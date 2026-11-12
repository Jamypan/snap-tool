# -*- coding: utf-8 -*-
"""
snap.py —— 截图工具主程序。

功能：
  · 启动即显示程序主窗口（帮助菜单 / 三种截图模式 / 默认模式设置）+ 托盘常驻
  · 全局热键唤起截图（默认 Ctrl+Shift+A，可在菜单里自定义）
  · 三种截图模式：框选、窗口（悬停高亮单击）、全屏
  · 矩形/椭圆/箭头/画笔/马赛克/文字标注（画笔首尾可加箭头）
  · 程序窗口里整图旋转 90° / 左右上下镜像（可撤销）
  · 复制到剪贴板 / 另存为
  · 滚动长截图（自动拼接）
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
    MODE_LABELS,
    Hotkey,
    HotkeyDialog,
    load_hotkey,
    load_mode,
    save_hotkey,
    save_mode,
)
from snapeditor import Overlay  # noqa: E402
from snap_editor import EditorWindow  # noqa: E402
from snapui import (  # noqa: E402
    ABOUT_HTML,
    APP_NAME,
    CLI_HELP,
    HelpWindow,
    MainWindow,
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


def save_qimage(img: QImage, path: Path) -> None:
    suffix = path.suffix.lower() or ".png"
    fmt = "JPG" if suffix in (".jpg", ".jpeg") else "PNG"
    if not img.save(str(path), fmt):
        raise OSError(f"保存失败：{path}")


# ---------------------------------------------------------------------------
# 后台工作线程
# ---------------------------------------------------------------------------
class StitchWorker(QThread):
    """滚动长截图（阻塞式，跑在子线程）。"""

    progress = Signal(int, int)
    ok = Signal(object, dict)
    failed = Signal(str)

    def __init__(self, rect: snapback.ScreenRect) -> None:
        super().__init__()
        self.rect = rect

    def run(self) -> None:  # noqa: D102
        try:
            img, stats = snapback.stitch_scroll(
                self.rect,
                on_progress=lambda f, h, c: self.progress.emit(f, h),
                should_stop=snapback.is_escape_pressed,
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
    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.title = QLabel("正在滚动截屏…")
        self.detail = QLabel("")
        self.title.setStyleSheet("color:#fff; font-size:14px; font-weight:bold;")
        self.detail.setStyleSheet("color:#cfcfcf; font-size:12px;")
        lay.addWidget(self.title)
        lay.addWidget(self.detail)
        self.setStyleSheet("background:#1f1f1f; border:1px solid #3a3a3a; border-radius:8px;")

    def update_text(self, frames: int, height: int) -> None:
        self.detail.setText(f"已拼 {frames} 帧 · 当前高度 {height}px\n按 Esc 可随时结束")
        self.adjustSize()


# ---------------------------------------------------------------------------
# 结果预览窗口
# ---------------------------------------------------------------------------
class PreviewWindow(QWidget):
    """长截图结果的预览与导出窗口。"""

    def __init__(self, img: QImage, save_dir: Path) -> None:
        super().__init__(None, Qt.Window)
        self.setWindowTitle(f"{APP_NAME} - 长截图预览")
        self.img = img
        self.save_dir = save_dir

        root = QVBoxLayout(self)
        area = QScrollArea()
        area.setWidgetResizable(True)
        label = QLabel()
        label.setPixmap(QPixmap.fromImage(img))
        area.setWidget(label)
        root.addWidget(area, 1)

        info = QLabel(f"尺寸：{img.width()} × {img.height()} px")
        info.setStyleSheet("color:#555;")
        root.addWidget(info)

        row = QHBoxLayout()
        b_copy = QPushButton("复制到剪贴板")
        b_save = QPushButton("保存为文件")
        b_close = QPushButton("关闭")
        b_copy.clicked.connect(self._copy)
        b_save.clicked.connect(self._save)
        b_close.clicked.connect(self.close)
        row.addStretch(1)
        row.addWidget(b_copy)
        row.addWidget(b_save)
        row.addWidget(b_close)
        root.addLayout(row)

        self.resize(760, 720)

    def _copy(self) -> None:
        QApplication.clipboard().setImage(self.img)
        self.setWindowTitle(f"{APP_NAME} - 已复制到剪贴板")

    def _save(self) -> None:
        default = self.save_dir / f"长截图_{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存长截图", str(default), "PNG 图片 (*.png);;JPEG 图片 (*.jpg)"
        )
        if not path:
            return
        try:
            save_qimage(self.img, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        self.setWindowTitle(f"{APP_NAME} - 已保存：{path}")


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
        self.busy: BusyBar | None = None
        self._ocr_busy = False          # 已有取字任务在跑时忽略重复点击
        self._workers: list[QThread] = []
        self._help_window: HelpWindow | None = None
        self._about_box: QMessageBox | None = None
        self._hidden_windows: list[QWidget] = []
        self._minimize_hint_shown = False
        self._quitting = False          # 正在退出：屏蔽一切托盘提示 / 窗口提示

        self.hotkey: Hotkey = load_hotkey()
        self.capture_mode = load_mode()
        self._hotkey_registered = False
        self._hk_error = ""

        icon = make_icon()
        self.main_window = MainWindow(icon, self.hotkey, self.capture_mode, self.save_dir)
        self.main_window.capture_requested.connect(self.start_capture)
        self.main_window.mode_changed.connect(self._on_mode_changed)
        self.main_window.hotkey_requested.connect(self.open_hotkey_settings)
        self.main_window.help_requested.connect(self.show_help)
        self.main_window.about_requested.connect(self.show_about)
        self.main_window.open_dir_requested.connect(self._open_save_dir)
        self.main_window.minimize_requested.connect(self._on_minimized)
        self.main_window.quit_requested.connect(self.quit)

        self.tray = QSystemTrayIcon(icon)
        self.menu = QMenu()
        act_show = QAction("显示主窗口", self.menu)
        act_show.triggered.connect(lambda _checked=False: self.show_main_window())
        self.menu.addAction(act_show)
        self.act_capture = QAction("截图", self.menu)
        self.act_capture.triggered.connect(lambda: self.start_capture())
        self.menu.addAction(self.act_capture)
        self.menu.addSeparator()
        for mode in CAPTURE_MODES:
            act = QAction(MODE_LABELS[mode], self.menu)
            act.triggered.connect(
                lambda _checked=False, m=mode: self.start_capture(m)
            )
            self.menu.addAction(act)
        self.menu.addSeparator()
        act_hotkey = QAction("设置热键…", self.menu)
        act_hotkey.triggered.connect(lambda _checked=False: self.open_hotkey_settings())
        self.menu.addAction(act_hotkey)
        act_dir = QAction("打开保存目录", self.menu)
        act_dir.triggered.connect(lambda _checked=False: self._open_save_dir())
        self.menu.addAction(act_dir)
        self.menu.addSeparator()
        act_help = QAction("使用说明…", self.menu)
        act_help.triggered.connect(lambda: self.show_help("help"))
        self.menu.addAction(act_help)
        act_about = QAction("关于…", self.menu)
        act_about.triggered.connect(lambda _checked=False: self.show_about())
        self.menu.addAction(act_about)
        act_quit = QAction("退出", self.menu)
        act_quit.triggered.connect(lambda _checked=False: self.quit())
        self.menu.addAction(act_quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.show()

        # 有人重复启动时请求「把主窗口显示出来」，避免用户以为程序没在运行
        # 返回的是 QTimer（轮询唤醒事件），必须挂在 self 上保持引用
        self._activate_notifier = singleinstance.install_activation_notifier(
            self._on_activate_request
        )

        self.filter = HotkeyFilter(self._on_hotkey)
        app.installNativeEventFilter(self.filter)
        self._hotkey_ok = self._try_register(self.hotkey)
        self._update_hotkey_texts()
        self.main_window.show()

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

    def _update_hotkey_texts(self) -> None:
        label = self.hotkey.label()
        self.act_capture.setText(f"截图  {label}")
        self.tray.setToolTip(f"{APP_NAME}（{label} 截图 · 右键可改热键）")
        self.main_window.set_hotkey(self.hotkey)

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
            APP_NAME, "程序本来就在运行，已为你显示主窗口。",
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
            APP_NAME,
            "已最小化到托盘，程序仍在运行。右键托盘可重新打开主窗口或退出。",
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
        # 用非模态实例而非静态 about()：截图时能被一起隐藏，也不会阻塞事件循环
        if self._about_box is None:
            box = QMessageBox(self.main_window)
            box.setWindowTitle(f"关于 {APP_NAME}")
            box.setIcon(QMessageBox.Information)
            box.setTextFormat(Qt.RichText)
            box.setText(ABOUT_HTML)
            box.setStandardButtons(QMessageBox.Ok)
            box.setWindowModality(Qt.NonModal)
            self._about_box = box
        self._about_box.show()
        self._about_box.raise_()
        self._about_box.activateWindow()

    def _on_mode_changed(self, mode: str) -> None:
        if mode not in CAPTURE_MODES:
            return
        self.capture_mode = mode
        self.main_window.set_mode(mode)
        msg = f"默认截图模式已设为「{MODE_LABELS[mode]}」，热键与托盘截图将使用此模式"
        if not save_mode(mode):
            msg += "（配置写入失败，重启后会恢复）"
        self._tray_message(APP_NAME, msg, QSystemTrayIcon.Information, 3000)

    # ------------------------------------------------------------ 自有窗口显隐
    def _hide_own_windows(self) -> None:
        """截图前隐藏自己的全部窗口，避免被拍进图里；结束后按原状态恢复。"""
        self._hidden_windows = []
        for w in (
            self.main_window,
            self.preview,
            self._help_window,
            self._about_box,
            self.busy,
        ):
            if w is not None and w.isVisible():
                w.hide()
                self._hidden_windows.append(w)

    def _restore_own_windows(self) -> None:
        for w in self._hidden_windows:
            w.show()
            w.raise_()
        self._hidden_windows = []

    def open_hotkey_settings(self) -> None:
        """托盘「设置热键…」：录制期间注销热键，退出时保证热键始终可用。"""
        if self.overlay is not None:
            return  # 截图进行中不弹设置窗口
        # 录制时用户按旧组合（如 Ctrl+Shift+A）不能把截图遮罩唤起来
        self._unregister_hotkey()
        try:
            for _ in range(10):
                dlg = HotkeyDialog(self.hotkey, None, APP_NAME, self._hk_error)
                if dlg.exec() != QDialog.Accepted:
                    break
                hk = dlg.hotkey
                if self._try_register(hk):
                    self.hotkey = hk
                    saved = save_hotkey(hk)
                    self._update_hotkey_texts()
                    msg = f"截图热键已改为 {hk.label()}"
                    if not saved:
                        msg += "（配置未能写入磁盘，重启后会恢复旧设置）"
                    self._tray_message(APP_NAME, msg, QSystemTrayIcon.Information, 3000)
                    break
                # 被其他程序占用 / 系统保留：让用户换一个，不改动旧设置
                self._hk_error = (
                    f"{hk.label()} 无法注册：可能已被其他程序占用，或属于系统保留组合。请换一个。"
                )
        finally:
            self._hk_error = ""
            if not self._hotkey_registered:
                self._hotkey_ok = self._try_register(self.hotkey)
                if not self._hotkey_ok:
                    self._tray_message(
                        APP_NAME,
                        f"热键 {self.hotkey.label()} 注册失败，请用托盘右键菜单截图，或在「设置热键…」里换一个组合。",
                        QSystemTrayIcon.Warning,
                        6000,
                    )

    def _on_hotkey(self, hk_id: int) -> None:
        if hk_id == HOTKEY_ID:
            self.start_capture()

    def _on_tray(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.start_capture()

    # ------------------------------------------------------------ 截图
    def start_capture(self, mode=None) -> None:
        """开始截图。mode 为 None 或非字符串时用默认模式（QAction.triggered 会传 bool）。"""
        if self.overlay is not None:
            return
        if not isinstance(mode, str) or mode not in CAPTURE_MODES:
            mode = self.capture_mode

        # 先把自己的窗口藏起来，避免拍进截图里
        self._hide_own_windows()
        self.tray.setVisible(False)
        self.app.processEvents()
        time.sleep(0.12)
        self.app.processEvents()

        try:
            pil = snapback.grab_all_screens()
        except Exception as exc:  # noqa: BLE001
            self.tray.setVisible(True)
            self._restore_own_windows()
            QMessageBox.warning(None, APP_NAME, f"截屏失败：{exc}")
            return

        self.tray.setVisible(True)

        qimg = pil_to_qimage(pil)

        # 全屏：截完直接进窗口化编辑器，不需选择 / 确定这一步
        if mode == "fullscreen":
            self._on_to_editor(qimg, [])
            return

        phys = snapback.virtual_screen()
        screen = self.app.primaryScreen()
        dpr = screen.devicePixelRatio() or 1.0

        self.overlay = Overlay(qimg, dpr)
        self.overlay.setGeometry(
            QRect(
                int(round(phys.x / dpr)),
                int(round(phys.y / dpr)),
                max(1, int(round(phys.w / dpr))),
                max(1, int(round(phys.h / dpr))),
            )
        )
        # 三种模式：框选 / 窗口（悬停高亮单击）/ 全屏（自动选中整个虚拟屏幕）
        self.overlay.set_capture_mode(mode, self._pick_window)
        self.overlay.done.connect(self._on_done)
        self.overlay.cancelled.connect(self._on_cancel)
        self.overlay.long_shot.connect(self._on_long_shot)
        self.overlay.ocr.connect(self._on_ocr)
        self.overlay.save_requested.connect(self._save_image)
        self.overlay.to_editor.connect(self._on_to_editor)

        # 用 setGeometry + show 而不是 showFullScreen：
        # 后者只覆盖主屏，多显示器下会漏掉其他屏幕。
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()
        self.overlay.setFocus()

    def _pick_window(self, pos: QPoint):
        """窗口模式：Overlay 局部逻辑坐标 → 物理坐标 → Win32 窗口枚举 → 逻辑矩形。"""
        ov = self.overlay
        if ov is None:
            return None
        dpr = ov.dpr or 1.0
        gp = ov.mapToGlobal(pos)
        origin = ov.mapToGlobal(QPoint(0, 0))
        info = snapback.window_rect_at(
            int(round(gp.x() * dpr)), int(round(gp.y() * dpr))
        )
        if info is None:
            return None
        r = info.rect
        q = QRect(
            int(round(r.x / dpr)) - origin.x(),
            int(round(r.y / dpr)) - origin.y(),
            max(1, int(round(r.w / dpr))),
            max(1, int(round(r.h / dpr))),
        ).intersected(ov.rect())
        if q.width() < 8 or q.height() < 8:
            return None
        return (q, info.title)

    def _close_overlay(self) -> None:
        # 遮罩关闭时取字任务的结果已无处展示，同时解除 busy 锁，
        # 否则用户按 Esc 取消后下次取字会被永久挡住。
        self._ocr_busy = False
        if self.overlay:
            self.overlay.deleteLater()
            self.overlay = None
        self._restore_own_windows()

    def _on_cancel(self) -> None:
        self._close_overlay()

    def _on_done(self, img: QImage) -> None:
        QApplication.clipboard().setImage(img)
        self._close_overlay()
        self._tray_message(
            APP_NAME,
            f"已复制到剪贴板  {img.width()}×{img.height()}",
            QSystemTrayIcon.Information,
            1800,
        )

    def _save_image(self, img: QImage) -> None:
        default = self.save_dir / f"截图_{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            None, "保存截图", str(default), "PNG 图片 (*.png);;JPEG 图片 (*.jpg)"
        )
        if not path:
            return
        try:
            save_qimage(img, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(None, APP_NAME, str(exc))
            return
        self._close_overlay()
        self._tray_message(APP_NAME, f"已保存：{path}", QSystemTrayIcon.Information, 2200)

    # ------------------------------------------------------------ 长截图
    def _on_long_shot(self, logical_rect: QRect) -> None:
        if logical_rect.isNull() or logical_rect.width() < 8:
            return
        dpr = self.overlay.dpr if self.overlay else 1.0
        rect = snapback.ScreenRect(
            int(round(logical_rect.x() * dpr)),
            int(round(logical_rect.y() * dpr)),
            int(round(logical_rect.width() * dpr)),
            int(round(logical_rect.height() * dpr)),
        )
        self._close_overlay()

        self.busy = BusyBar()
        self.busy.show()
        screen_geo = self.app.primaryScreen().availableGeometry()
        self.busy.move(screen_geo.center().x() - 130, screen_geo.top() + 60)

        worker = StitchWorker(rect)
        worker.progress.connect(self.busy.update_text)

        def on_ok(pil_img, stats) -> None:
            self._close_busy()
            qimg = pil_to_qimage(pil_img)
            self.preview = PreviewWindow(qimg, self.save_dir)
            self.preview.show()
            self.preview.raise_()
            self.preview.activateWindow()
            if stats.get("stop_reason") in ("match-failed", "no-overlap"):
                self._tray_message(
                    APP_NAME,
                    "内容未能自动对齐，结果可能不完整（页面可能有固定悬浮元素或动画）",
                    QSystemTrayIcon.Warning,
                    4000,
                )

        def on_fail(msg: str) -> None:
            self._close_busy()
            QMessageBox.warning(None, APP_NAME, f"长截图失败：{msg}")

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
                overlay.show_ocr_message("没有识别到文字。")

        def on_fail(msg: str) -> None:
            if self.overlay is not overlay:
                return
            self._ocr_busy = False
            overlay.show_ocr_message(
                "OCR 不可用：\n" + msg
                + "\n\n请确认已安装 OCR 依赖（rapidocr / onnxruntime）。"
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
        """
        self._ocr_busy = False
        if self.overlay is not None:
            self.overlay.deleteLater()
            self.overlay = None
        # 编辑器是一个普通程序窗口：隐藏主窗口，避免两个窗口叠在一起
        self.main_window.hide()
        self._open_editor(base_img, shapes)

    def _open_editor(self, base_img: QImage, shapes: list) -> None:
        if self.editor is not None:
            self.editor.close()
        editor = EditorWindow(base_img, shapes, self.save_dir)
        self.editor = editor
        editor.copy_requested.connect(self._on_editor_copy)
        editor.save_requested.connect(self._on_editor_save)
        editor.ocr_requested.connect(self._on_editor_ocr)
        editor.closed.connect(self._on_editor_closed)
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _on_editor_copy(self, img: QImage) -> None:
        QApplication.clipboard().setImage(img)
        self._tray_message(
            APP_NAME,
            f"已复制到剪贴板  {img.width()}×{img.height()}",
            QSystemTrayIcon.Information,
            1800,
        )

    def _on_editor_save(self, img: QImage) -> None:
        if self.editor is None:
            return
        default = self.save_dir / f"截图_{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(
            None, "保存截图", str(default), "PNG 图片 (*.png);;JPEG 图片 (*.jpg)"
        )
        if not path:
            return
        try:
            save_qimage(img, Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(None, APP_NAME, str(exc))
            return
        self._tray_message(APP_NAME, f"已保存：{path}", QSystemTrayIcon.Information, 2200)

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
                self.editor.show_ocr_message("没有识别到文字。")

        def on_fail(msg: str) -> None:
            self._ocr_busy = False
            if self.editor is not None:
                self.editor.show_ocr_message(
                    "OCR 不可用：\n" + msg
                    + "\n\n请确认已安装 OCR 依赖（rapidocr / onnxruntime）。"
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
        # 3) 注销全局热键后退出事件循环
        self._unregister_hotkey()
        self.app.quit()


# ---------------------------------------------------------------------------
def _run_selftest() -> int:
    """不进入 GUI 的自检：依赖 + OCR 后端可用性。

    结果同时打印到 stdout 和写入 %APPDATA%/SnapTool/selftest.log —— 打包成
    --windowed exe 后没有控制台，靠这份日志验证产物是否完整（模型/DLL 是否收齐）。
    """
    import importlib

    out: list[str] = [
        f"{APP_NAME} 自检 {datetime.now():%Y-%m-%d %H:%M:%S}",
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
            out.append(f"[ok]   optional {mod} 可用")
        except Exception:  # noqa: BLE001
            out.append(f"[--]   optional {mod} 未安装（对应功能不可用）")

    try:
        base = getattr(sys, "_MEIPASS", None) or str(Path(__file__).resolve().parent)
        png = Path(base) / "ocr_test.png"
        out.append(f"测试图   : {png} (exists={png.is_file()})")
        if not png.is_file():
            ok = False
            out.append("[FAIL] 找不到 ocr_test.png")
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
                out.append("[FAIL] OCR 返回 0 行")
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
        print(f"[selftest] 日志：{log}")
    return 0 if ok else 1


def _resolve_existing_instance(st, restart: bool) -> bool:
    """检测到已有实例：先唤醒它，再决定退出还是「结束后台实例并重启」。

    返回 True 表示继续启动新实例。这样「提示已运行却看不到界面」时，用户在
    弹窗里点「是」就能直接进新版，不必去任务管理器里找进程。
    """
    rec = st.record or {}
    pid = rec.get("pid", "?")
    started = rec.get("started", "未知")
    woken = singleinstance.signal_existing()
    singleinstance.log(f"已有实例 pid={pid} 唤醒={woken} restart={restart}")

    if not restart:
        hint = (
            "已请它把主窗口显示出来，请看任务栏。\n" if woken
            else "托盘图标可能被收进了通知区折叠栏（点 ^ 展开看看）。\n"
        )
        text = (
            f"截屏助手已在后台运行（PID {pid}，启动于 {started}）。\n\n"
            + hint
            + "如果确实看不到任何窗口，多半是残留的后台实例。\n\n"
            "是否结束它并重新启动？（若有未保存的编辑内容会丢失）"
        )
        # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST
        ans = ctypes.windll.user32.MessageBoxW(
            None, text, APP_NAME, 0x04 | 0x20 | 0x40000
        )
        if ans != 6:  # IDYES
            return False

    killed = singleinstance.kill_recorded(rec)
    singleinstance.log(f"结束后台实例结果={killed}")
    if not killed:
        ctypes.windll.user32.MessageBoxW(
            None,
            "结束后台实例未成功，但仍会尝试继续启动。\n"
            "若再次提示已在运行，请在任务管理器里结束残留的 pythonw.exe。",
            APP_NAME, 0x30 | 0x40000,
        )
    time.sleep(0.25)
    again = singleinstance.probe()
    singleinstance.log(f"重启后 probe -> {again.state}/{again.reason}")
    if again.state == "running":
        ctypes.windll.user32.MessageBoxW(
            None,
            "仍有实例占用，启动中止。请在任务管理器中结束所有 pythonw.exe 后重试，"
            "或双击 restart.bat。",
            APP_NAME, 0x10 | 0x40000,
        )
        return False
    return True


def main() -> int:
    # --help 不进入 Qt，也不检查单实例；pythonw 无控制台时改用系统弹窗
    if any(a in ("-h", "--help", "/?") for a in sys.argv[1:]):
        if getattr(sys, "stdout", None) is None:
            ctypes.windll.user32.MessageBoxW(
                None, CLI_HELP, f"{APP_NAME} - 命令行说明", 0x40
            )
        else:
            print(CLI_HELP)
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
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "系统托盘不可用，无法常驻运行。")
        return 2

    ctrl = App(app)
    app._ctrl = ctrl  # 防止被回收

    if "--shot" in sys.argv:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(120, ctrl.start_capture)
    elif not ctrl._hotkey_ok:
        ctrl.tray.showMessage(
            APP_NAME,
            f"全局热键 {ctrl.hotkey.label()} 注册失败（可能被其他程序占用）。"
            "请在主窗口或托盘菜单「设置热键…」换一个组合，也可直接点主窗口的截图按钮。",
            QSystemTrayIcon.Warning,
            8000,
        )

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
