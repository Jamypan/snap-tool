# -*- coding: utf-8 -*-
"""
snapback.py —— 后端能力层：屏幕捕获 / 滚动长截图拼接 / OCR。

本模块不依赖 Qt，可单独导入和测试。
"""
from __future__ import annotations

import ctypes
import io
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageGrab

# ---------------------------------------------------------------------------
# Win32 常量
# ---------------------------------------------------------------------------
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

INPUT_MOUSE = 0
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
WHEEL_DELTA = 120

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_ESCAPE = 0x1B

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WS_EX_TOPMOST = 0x00000008
HWND_TOP = 0
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040

user32 = ctypes.windll.user32 if sys.platform == "win32" else None


def _t(key: str, **kwargs) -> str:
    """后端异常文案的多语言入口（延迟导入，保持本模块无顶层 Qt 依赖）。"""
    try:
        from i18n import t
        return t(key, **kwargs)
    except Exception:  # noqa: BLE001
        return key.format(**kwargs) if kwargs else key


# ---------------------------------------------------------------------------
# DPI 感知
# ---------------------------------------------------------------------------
def set_dpi_awareness() -> str:
    """必须在创建任何窗口之前调用，否则高分屏下截图会模糊、坐标会错位。"""
    if sys.platform != "win32":
        return "not-win32"
    # 2 = PROCESS_PER_MONITOR_DPI_AWARE
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "per-monitor"
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "system"
    except Exception:
        return "failed"


# ---------------------------------------------------------------------------
# 虚拟屏幕（支持多显示器，坐标可能为负）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScreenRect:
    x: int
    y: int
    w: int
    h: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


def virtual_screen() -> ScreenRect:
    """返回覆盖所有显示器的虚拟屏幕矩形。"""
    if user32 is None:
        return ScreenRect(0, 0, 1920, 1080)
    return ScreenRect(
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


# ---------------------------------------------------------------------------
# 窗口探测（「窗口截图」模式用，坐标均为物理像素）
# ---------------------------------------------------------------------------
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


@dataclass(frozen=True)
class WindowInfo:
    rect: ScreenRect
    title: str
    hwnd: int
    client: ScreenRect | None = None   # 客户区（去掉标题栏/边框），滚动拼接用它更准
    z: int = 0                         # Z 序序号（EnumWindows 枚举顺序，越小越靠前）
    dpi: int = 96                      # 窗口所属显示器的 DPI（96 = 100% 缩放）

    @property
    def dpr(self) -> float:
        """该窗口的逻辑→物理缩放比（96 DPI = 1.0）。"""
        return (self.dpi or 96) / 96.0


# ---------------------------------------------------------------------------
# 窗口选择：类名黑名单 + Z 序优先（v35）
# ---------------------------------------------------------------------------
# 这些窗口不该成为「窗口截图」的目标：菜单、工具提示、任务栏、桌面等。
# 它们的共同点是宽度/高度很小或铺满屏幕，却盖在真正的内容窗口之上，
# 旧逻辑「取包含鼠标点的最小窗口」极易误选它们。
_PICK_CLASS_DENY_EXACT = frozenset({
    "#32768",                  # 菜单（Windows 标准菜单类）
    "tooltips_class32",        # 工具提示
    "shell_traywnd",           # 任务栏
    "shell_secondarytraywnd",  # 副屏任务栏
    "progman",                 # 桌面
    "workerw",                 # 桌面工作区
    "windowsofrealtimedisplay",  # 壁纸渲染层
})
_PICK_CLASS_DENY_SUBSTR = (
    "tooltip", "candidate", "ime", "inputmethod",
    "输入法", "候选", "suggestion", "autocomplete",
)


def is_pickable_window_class(cls: str) -> bool:
    """纯判定函数：窗口类名是否允许作为「窗口截图」目标。

    取不到类名（空串）时放行，避免误伤；测试在非 Windows 平台也能覆盖。
    """
    c = (cls or "").strip()
    if not c:
        return True
    if c.lower() in _PICK_CLASS_DENY_EXACT:
        return False
    low = c.lower()
    return not any(s in low for s in _PICK_CLASS_DENY_SUBSTR)


def pick_top_window(candidates: list[WindowInfo]) -> WindowInfo | None:
    """候选按 EnumWindows 的 Z 序（顶 → 底）传入，返回最靠前的一个。

    旧逻辑取「面积最小」会在鼠标压到通知/悬浮球时误选小浮窗。Windows 的
    EnumWindows 本身就是自顶向下的 Z 序，黑名单过滤之后第一个就是用户
    在该点真正看到的窗口。
    """
    if not candidates:
        return None
    return min(candidates, key=lambda w: w.z)


def dpi_for_window(hwnd: int) -> int:
    """取窗口所属显示器的 DPI；失败回退 96（100% 缩放）。"""
    if sys.platform != "win32" or not hwnd or user32 is None:
        return 96
    try:
        v = int(user32.GetDpiForWindow(wintypes.HWND(hwnd)))
        return v if v > 0 else 96
    except Exception:  # noqa: BLE001
        return 96


def monitor_physical_rects() -> list[ScreenRect]:
    """枚举所有显示器的物理像素矩形（用于混合 DPI 坐标换算）。"""
    if user32 is None:
        return []
    out: list[ScreenRect] = []
    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
        ctypes.POINTER(_RECT), wintypes.LPARAM,
    )

    def _cb(_hmon, _hdc, lprc, _data) -> bool:
        try:
            r = lprc.contents
            out.append(ScreenRect(r.left, r.top, r.right - r.left, r.bottom - r.top))
        except Exception:  # noqa: BLE001
            pass
        return True

    try:
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
    except Exception:  # noqa: BLE001
        pass
    return out


def foreground_window(hwnd: int) -> bool:
    """尽力把目标窗口提到前台（选中窗口后重抓底图前调用）。

    Windows 的前台锁可能让 SetForegroundWindow 失败；SetWindowPos(HWND_TOP)
    不激活窗口、只提高 Z 序，通常更可靠。两者都试，任何异常都吞掉。
    """
    if sys.platform != "win32" or not hwnd or user32 is None:
        return False
    h = wintypes.HWND(hwnd)
    ok = False
    try:
        if user32.IsIconic(h):
            user32.ShowWindow(h, SW_RESTORE)
        ok = bool(user32.SetWindowPos(
            h, wintypes.HWND(HWND_TOP), 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        ))
    except Exception:  # noqa: BLE001
        pass
    try:
        ok = bool(user32.SetForegroundWindow(h)) or ok
    except Exception:  # noqa: BLE001
        pass
    return ok


def _client_rect(hwnd: int) -> ScreenRect | None:
    """取窗口客户区的屏幕物理矩形（不含标题栏、边框、阴影）。"""
    if user32 is None:
        return None
    try:
        r = _RECT()
        if not user32.GetClientRect(wintypes.HWND(hwnd), ctypes.byref(r)):
            return None
        pt = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(pt)):
            return None
        w, h = r.right - r.left, r.bottom - r.top
        if w < 60 or h < 40:
            return None
        return ScreenRect(int(pt.x), int(pt.y), int(w), int(h))
    except Exception:  # noqa: BLE001
        return None


def _visible_frame(hwnd: int) -> ScreenRect | None:
    """优先用 DWM 可见边框（不含 Win10/11 的透明阴影），失败退回 GetWindowRect。"""
    r = _RECT()
    try:
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(r), ctypes.sizeof(r),
        )
        if hr == 0 and r.right > r.left and r.bottom > r.top:
            return ScreenRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
    except Exception:  # noqa: BLE001
        pass
    if user32 is not None and user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
        if r.right > r.left and r.bottom > r.top:
            return ScreenRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
    return None


def window_rect_at(x: int, y: int, exclude_pid: int | None = None) -> WindowInfo | None:
    """返回鼠标位置下最贴合的顶层窗口。

    EnumWindows 按 Z 序枚举，过滤掉不可见 / 最小化 / cloaked / 工具窗口 /
    本进程自己的窗口；在包含该点的候选里取面积最小的一个，这样不会误选
    覆盖整屏的透明浮层或桌面。返回物理像素矩形（已去掉窗口阴影）。
    """
    if user32 is None:
        return None
    import os

    if exclude_pid is None:
        exclude_pid = os.getpid()
    found: list[WindowInfo] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam) -> bool:
        try:
            h = int(hwnd or 0)
            if not h or not user32.IsWindowVisible(wintypes.HWND(h)):
                return True
            if user32.IsIconic(wintypes.HWND(h)):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(wintypes.HWND(h), ctypes.byref(pid))
            if pid.value == exclude_pid:
                return True
            cloaked = wintypes.DWORD()
            try:
                if (
                    ctypes.windll.dwmapi.DwmGetWindowAttribute(
                        wintypes.HWND(h), DWMWA_CLOAKED,
                        ctypes.byref(cloaked), ctypes.sizeof(cloaked),
                    ) == 0 and cloaked.value
                ):
                    return True
            except Exception:  # noqa: BLE001
                pass
            # v35：菜单 / 工具提示 / 任务栏 / 桌面 / 输入法候选窗一律排除，
            # 否则「取最小窗口」会把它们当成目标（截出来只有一条小横条）。
            cls_buf = ctypes.create_unicode_buffer(256)
            try:
                user32.GetClassNameW(wintypes.HWND(h), cls_buf, len(cls_buf))
            except Exception:  # noqa: BLE001
                pass
            cls = cls_buf.value
            if not is_pickable_window_class(cls):
                return True
            proc = _process_name(pid.value) if pid.value else ""
            if any(k in cls.lower() or k in proc for k in _FLOATING_HINTS):
                return True
            if user32.GetWindowLongW(wintypes.HWND(h), GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            r = _visible_frame(h)
            if r is None or r.w < 60 or r.h < 40:
                return True
            if not (r.x <= x < r.x + r.w and r.y <= y < r.y + r.h):
                return True
            n = user32.GetWindowTextLengthW(wintypes.HWND(h))
            buf = ctypes.create_unicode_buffer(max(1, n + 1))
            user32.GetWindowTextW(wintypes.HWND(h), buf, len(buf))
            # EnumWindows 自顶向下枚举，len(found) 即 Z 序序号（越小越靠前）
            found.append(WindowInfo(
                r, buf.value, h, _client_rect(h),
                z=len(found), dpi=dpi_for_window(h),
            ))
        except Exception:  # noqa: BLE001
            pass
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    if not found:
        return None
    # v35：改用 Z 序优先（用户在该点真正看到的窗口），不再取面积最小。
    return pick_top_window(found)


# ---------------------------------------------------------------------------
# 捕获
# ---------------------------------------------------------------------------
def grab_all_screens() -> Image.Image:
    """抓取整个虚拟桌面（所有显示器拼在一起）。返回 RGB 图像。"""
    r = virtual_screen()
    img = ImageGrab.grab(bbox=r.bbox, all_screens=True)
    return img.convert("RGB")


def grab_region(rect: ScreenRect) -> Image.Image:
    """抓取指定屏幕区域。"""
    return ImageGrab.grab(bbox=rect.bbox, all_screens=True).convert("RGB")


# ---------------------------------------------------------------------------
# 滚轮 / 光标控制
# ---------------------------------------------------------------------------
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send_mouse_wheel(notches: int) -> None:
    """发送鼠标滚轮事件（正数向上、负数向下）。"""
    if user32 is None:
        return
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = 0
    inp.mi.dy = 0
    inp.mi.mouseData = ctypes.c_ulong(WHEEL_DELTA * notches & 0xFFFFFFFF).value
    inp.mi.dwFlags = MOUSEEVENTF_WHEEL
    inp.mi.time = 0
    inp.mi.dwExtraInfo = None
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def get_cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def is_key_pressed(vk: int) -> bool:
    """查询异步按键状态（最高位为 1 表示当前按下）。"""
    if user32 is None:
        return False
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def is_escape_pressed() -> bool:
    """用于长截图过程中随时中断。"""
    return is_key_pressed(VK_ESCAPE)


# ---------------------------------------------------------------------------
# 滚动长截图的交互控制（不依赖 Qt，可单独测试）
# ---------------------------------------------------------------------------
class ScrollControl:
    """把「左键暂停/继续、右键结束、点确定结束」翻译成拼接线程能读的状态。

    · 拼接线程：poll() / wait() / wait_while_paused() / should_stop() / paused
    · 主线程  ：request_stop() / set_exclude_rect()
    · 左键只认「按下沿」，按住不放不会反复切换；右键同上。
    · exclude_rect 是控制条的屏幕物理矩形：点在控制条上（尤其是「确定」）
      不算页面内的左/右键操作，否则点一下确定会同时触发暂停。
    """

    POLL_INTERVAL = 0.02

    def __init__(self, on_change=None, exclude_rect: ScreenRect | None = None) -> None:
        import threading

        self._lock = threading.Lock()
        self._paused = False
        self._stopped = False
        self._stop_reason = ""
        self._prev_left = False
        self._prev_right = False
        self._baseline_done = False
        self._on_change = on_change
        self.exclude_rect = exclude_rect

    # ------------------------------------------------------------ 只读状态
    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused

    @property
    def stop_reason(self) -> str:
        with self._lock:
            return self._stop_reason

    def should_stop(self) -> bool:
        with self._lock:
            return self._stopped

    def snapshot(self) -> tuple[bool, bool, str]:
        with self._lock:
            return self._paused, self._stopped, self._stop_reason

    # ------------------------------------------------------------ 主线程入口
    def request_stop(self, reason: str = "user-confirm") -> None:
        """控制条的「确定 ✓」/ 程序退出等调用：结束拼接。"""
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
            self._stop_reason = reason
        self._notify()

    def set_exclude_rect(self, rect: ScreenRect | None) -> None:
        with self._lock:
            self.exclude_rect = rect

    def set_on_change(self, fn) -> None:
        with self._lock:
            self._on_change = fn

    # ------------------------------------------------------------ 拼接线程
    def _notify(self) -> None:
        fn = self._on_change
        if fn is not None:
            try:
                fn()
            except Exception:  # noqa: BLE001  状态通知失败不能打断拼接
                pass

    def _cursor_in_exclude(self) -> bool:
        rect = self.exclude_rect
        if rect is None:
            return False
        try:
            x, y = get_cursor_pos()
        except Exception:  # noqa: BLE001
            return False
        return rect.x <= x < rect.x + rect.w and rect.y <= y < rect.y + rect.h

    def cursor_in_exclude(self) -> bool:
        """公共只读入口：拼接线程判断光标是否已移到控制条（去点「确定」）。"""
        return self._cursor_in_exclude()

    def _sync_baseline(self) -> None:
        """把当前已按住的键记成基线。

        选窗口时的那次左键点击可能还没松开，若不忽略会被算成「暂停」。
        """
        self._prev_left = is_key_pressed(VK_LBUTTON)
        self._prev_right = is_key_pressed(VK_RBUTTON)
        self._baseline_done = True

    def poll(self) -> None:
        """轮询一次鼠标按键边沿。由拼接线程在等待期间高频调用。"""
        if not self._baseline_done:
            self._sync_baseline()
        left = is_key_pressed(VK_LBUTTON)
        right = is_key_pressed(VK_RBUTTON)
        # 光标在控制条上：只刷新基线，不触发暂停/结束
        if self._cursor_in_exclude():
            self._prev_left, self._prev_right = left, right
            return
        if right and not self._prev_right:
            self.request_stop("user-right-click")
        elif left and not self._prev_left:
            with self._lock:
                self._paused = not self._paused
            self._notify()
        self._prev_left, self._prev_right = left, right

    def wait(self, seconds: float) -> None:
        """滚轮后的稳定等待期：细粒度轮询，短促点击也不会丢。"""
        end = time.monotonic() + max(0.0, seconds)
        while True:
            self.poll()
            if self.should_stop():
                return
            remain = end - time.monotonic()
            if remain <= 0:
                return
            time.sleep(min(self.POLL_INTERVAL, remain))

    def wait_while_paused(self) -> None:
        """暂停期间不抓帧、不滚轮，但持续监听「再点左键继续」。"""
        while self.paused and not self.should_stop():
            self.poll()
            time.sleep(self.POLL_INTERVAL)


# ---------------------------------------------------------------------------
# 长截图期间的屏幕浮层（输入法工具条 / 候选窗 / 提示条）
# ---------------------------------------------------------------------------
# 这类窗口固定在屏幕坐标、不随页面滚动，逐帧抓屏时会被一遍遍拍进长图，
# 形成周期性重复的小白条；它们还会干扰模板匹配，把重叠量带偏，导致帧间
# 出现大段重复内容（看起来像「拼接缝隙」）。拼接期间临时隐藏，结束一律恢复。
_FLOATING_HINTS = (
    "imeui", "imebroker", "msctfime", "chsime", "textinputhost",
    "textinput", "sogou", "qimei", "pinyin", "baiduime", "mspy",
    "candidate", "tooltips_class32", "tooltip", "corewindow",
    "inputmethod", "输入法", "候选",
)


def _process_name(pid: int) -> str:
    """取进程可执行文件名（小写）。取不到就返回空串，不影响主流程。"""
    if sys.platform != "win32" or not pid:
        return ""
    try:
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            k32.QueryFullProcessImageNameW(
                wintypes.HANDLE(handle), 0, buf, ctypes.byref(size)
            )
            import os
            return os.path.basename(buf.value).lower()
        finally:
            k32.CloseHandle(wintypes.HANDLE(handle))
    except Exception:  # noqa: BLE001
        return ""


def _rects_intersect(a: ScreenRect, b: ScreenRect) -> bool:
    return (
        a.x < b.x + b.w and b.x < a.x + a.w
        and a.y < b.y + b.h and b.y < a.y + a.h
    )


def _is_floating_overlay(
    capture: ScreenRect,
    win: ScreenRect,
    cls: str,
    title: str,
    proc: str,
    pid: int,
    own_pid: int,
    exstyle: int = 0,
) -> bool:
    """纯判定函数：只认「与选区相交的小浮层」，不碰正常主窗口。

    除了按类名 / 进程名识别输入法，凡是置顶或工具型的小窗口也一起清场：
    第三方输入法悬浮条类名千奇百怪，但它们同样会一帧一条地拍进长图。
    """
    if pid == own_pid or win.w < 8 or win.h < 8:
        return False
    if not _rects_intersect(capture, win):
        return False
    if win.w > max(160, capture.w * 0.7) or win.h > max(100, capture.h * 0.35):
        return False
    text = f"{cls} {title} {proc}".lower()
    keyword_hit = any(hint in text for hint in _FLOATING_HINTS)
    tool_like = bool(exstyle & (WS_EX_TOOLWINDOW | WS_EX_TOPMOST))
    return keyword_hit or tool_like


def find_floating_overlays(rect: ScreenRect, exclude_pid: int | None = None) -> list[int]:
    """枚举需要临时隐藏的浮层窗口句柄；任何 Win32 异常都退化为「不隐藏」。"""
    if user32 is None:
        return []
    import os

    if exclude_pid is None:
        exclude_pid = os.getpid()
    found: list[int] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam) -> bool:
        try:
            h = int(hwnd or 0)
            if not h or not user32.IsWindowVisible(wintypes.HWND(h)):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(wintypes.HWND(h), ctypes.byref(pid))
            if pid.value == exclude_pid:
                return True
            r = _RECT()
            if not user32.GetWindowRect(wintypes.HWND(h), ctypes.byref(r)):
                return True
            win = ScreenRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(wintypes.HWND(h), cls_buf, len(cls_buf))
            n = user32.GetWindowTextLengthW(wintypes.HWND(h))
            title_buf = ctypes.create_unicode_buffer(max(1, n + 1))
            user32.GetWindowTextW(wintypes.HWND(h), title_buf, len(title_buf))
            exstyle = user32.GetWindowLongW(wintypes.HWND(h), GWL_EXSTYLE)
            if _is_floating_overlay(
                rect, win, cls_buf.value, title_buf.value,
                _process_name(pid.value), pid.value, exclude_pid, exstyle,
            ):
                found.append(h)
        except Exception:  # noqa: BLE001
            pass
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(_cb), 0)
    except Exception:  # noqa: BLE001
        return []
    return found


def hide_floating_overlays(hwnds: list[int]) -> None:
    """每帧抓屏前调用一次：输入法可能自己把工具条重新弹出来。"""
    if user32 is None:
        return
    for h in hwnds:
        try:
            user32.ShowWindow(wintypes.HWND(h), SW_HIDE)
        except Exception:  # noqa: BLE001
            pass


def restore_floating_overlays(hwnds: list[int]) -> None:
    """拼接结束 / 异常都要恢复，SW_SHOWNOACTIVATE 不抢用户输入焦点。"""
    if user32 is None:
        return
    for h in hwnds:
        try:
            user32.ShowWindow(wintypes.HWND(h), SW_SHOWNOACTIVATE)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 长截图拼接
# ---------------------------------------------------------------------------
def overlap_row_diff(acc: np.ndarray, frame: np.ndarray, top: int) -> float:
    """重叠区逐行像素差的 75 分位数（0 = 完全对齐）。

    用「中间列带 + 行 p75」而不是整幅均值：
      · 中间列带：输入法工具条、链接提示条这类固定浮层只占边缘列；
      · **p75 而不是中位数**（v46）：网页大多是渐变 / 大面积纯色，错开 1~2
        行对「逐行差的中位数」完全没有影响（仍是 0.00，见下），可长截图正是
        靠这个把偏移纠回来——差 2 行时 378/379/380/381 的中位数全是 0，
        分不出谁对，每拼一帧累积 2px，越拼越歪；换成 75 分位后 380 是 0.00、
        379 是 0.49、378 是 2.51，能精确挑出正确位置。
      · 只有超过 1/4 的行都变了才会被抬高，普通浮层照样忽略。
    """
    if acc.shape[1] != frame.shape[1] or top < 0 or top >= acc.shape[0] - 4:
        return 255.0
    overlap = min(acc.shape[0] - top, frame.shape[0])
    if overlap < 8:
        # 滚到底时重叠本来就只剩几行，不该因此把匹配分数打下去，
        # 交给上层 min_new_rows / 到底连续确认去判断。
        return 0.0
    c0 = int(frame.shape[1] * 0.12)
    c1 = max(c0 + 8, int(frame.shape[1] * 0.88))
    a = acc[top: top + overlap: 2, c0:c1: 2].astype(np.int16)
    b = frame[0: overlap: 2, c0:c1: 2].astype(np.int16)
    if a.shape != b.shape or a.size == 0:
        return 255.0
    d = np.abs(a - b)
    rows = d.reshape(d.shape[0], -1).mean(axis=1)   # 兼容 2D 灰度 / 3D 彩色
    if rows.size == 0:
        return 255.0
    return float(np.percentile(rows, 75))


def find_vertical_overlap(
    acc: np.ndarray,
    frame: np.ndarray,
    search_rows: int = 400,
    template_rows: int = 120,
    template_offset: int = 0,
    *,
    max_candidates: int = 5,
    template_offsets: tuple[int, ...] | list[int] | None = None,
) -> tuple[int, float]:
    """
    在已拼接图像 acc 中定位新帧 frame 顶部的匹配位置。

    返回 (frame 第 0 行在 acc 中的行号, score)。尺寸不足返回 (-1, 0.0)。

    v20 抗浮层对齐：
      · 只在画面中间列带上做相关匹配，避开左侧链接提示条、右侧输入法工具条；
      · 取多个相关峰值候选，再用「重叠区逐行差」挑真正对齐的那个
        —— 固定浮层 / 重复卡片会让相关系数峰值落在错误位置，但错位会让
        绝大多数行都对不上；
      · 在 ±3 行内微调，消除 1~3px 的硬接缝（v46 由 ±2 放宽，配合 p75 评分）；
      · score 把对齐差折算进去，错得离谱时会低于阈值，交给上层重试。

    v46 多模板带（治「网页经常中断」的核心）：
      单条模板有个硬上限——模板取到 frame 的第 off 行、高 rows 行时，两帧
      重叠必须 >= off + rows 才可能对上。旧参数 off=86 / rows=120 意味着
      重叠要 >= 206 行，520px 高的窗口单帧最多只能滚约 314px；而浏览器一次
      滚轮常常就是 300~400px，于是一滚过线就必然失配、重试两次后中断。
      现在改成在帧内铺 2~3 条**短模板**（如 0%、12%、25% 处各 60~80 行），
      任一条命中即可：低位的模板保证大滚动也能对上（重叠只需 >= rows），
      高位的模板保证「网页顶部有 sticky 导航」时不被那块固定内容带偏。
    """
    import cv2

    if acc.shape[1] != frame.shape[1]:
        raise ValueError(_t("拼接帧宽度必须一致"))

    frame_h = int(frame.shape[0])
    rows = max(24, min(int(template_rows), frame_h))
    # 模板带规格：默认只一条（兼容旧调用与单元测试），stitch_scroll 会传多条
    specs: list[tuple[int, int]] = []
    if template_offsets:
        for off in sorted({int(o) for o in template_offsets}):
            if 0 <= off <= frame_h - rows:
                specs.append((off, rows))
    if not specs:
        specs = [(max(0, min(int(template_offset), frame_h - rows)), rows)]
    if acc.shape[0] < rows:
        return -1, 0.0

    # 两侧各留 12%：网页左右常贴着固定侧栏 / 悬浮条，中间主体最可信
    c0 = int(frame.shape[1] * 0.12)
    c1 = max(c0 + 8, int(frame.shape[1] * 0.88))
    search_top = max(0, acc.shape[0] - search_rows)
    search = acc[search_top:, c0:c1]
    if search.shape[0] < rows:
        return -1, 0.0

    # 粗匹配用 2× 降采样：1900px 宽的窗口按全分辨率做相关要 ~1 秒/帧，长图
    # 动辄几十帧，用户会明显觉得卡。降采样让计算量掉到 1/4 以下，位置误差
    # 不超过 2 个原像素，由后面的 ±3~±6 原像素精修兜住。
    down = 2 if (search.shape[1] >= 640 and rows >= 70) else 1
    small_search = None
    if down > 1:
        small_search = cv2.resize(
            search, None, fx=1.0 / down, fy=1.0 / down,
            interpolation=cv2.INTER_AREA,
        )

    best_key: tuple[float, float, float, int] | None = None
    best_top, best_score = -1, 0.0
    # 先跨所有模板带收集相关系数峰值，再统一排序取前几个做逐行差精修。
    # 逐行差（overlap_row_diff）是最贵的一步，每条模板各精修 5×7 次会把
    # 每帧耗时放大 4 倍；跨带排序后只精修少数候选，耗时与单模板相当。
    peaks: list[tuple[float, int, int]] = []          # (corr, off, top0)
    for off, trows in specs:
        template = frame[off: off + trows, c0:c1]
        if template.size == 0:
            continue
        if down > 1:
            tpl = cv2.resize(
                template, None, fx=1.0 / down, fy=1.0 / down,
                interpolation=cv2.INTER_AREA,
            )
            if tpl.shape[0] < 8 or tpl.shape[0] >= small_search.shape[0]:
                res = None
            else:
                res = cv2.matchTemplate(small_search, tpl, cv2.TM_CCOEFF_NORMED)
        else:
            res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
        if res is None:
            continue
        # 纯色模板会让 CCOEFF_NORMED 出现 NaN，先压成无效值
        res = np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)
        # 模板与搜索区等宽 → res 形状为 (N, 1)：逐个取峰值并抑制邻近行，
        # 得到互不相同的候选位置（网页里常有多块长得一样的卡片）。
        work = res.copy()
        for _ in range(max(1, max_candidates)):
            _, val, _, loc = cv2.minMaxLoc(work)
            if not np.isfinite(val) or val < 0.0:
                break
            row = int(loc[1])
            peaks.append((float(val), off, search_top + row * down - off))
            work[max(0, row - 3): min(work.shape[0], row + 4), 0] = -1.0
    if not peaks:
        return -1, 0.0
    peaks.sort(key=lambda t: t[0], reverse=True)

    # 精修范围与候选数按置信度自适应：逐行差（overlap_row_diff）是全程最贵
    # 的一步，13 个偏移 × 3 个候选要 200ms 以上。
    # 置信度不能只看相关系数——固定浮层 / 重复卡片会造出「相关很高但整体
    # 错位」的假峰，所以再加一道：峰顶处的逐行差也要够小，才敢只认这一个峰。
    first_top = peaks[0][2]
    first_diff = (
        overlap_row_diff(acc, frame, first_top)
        if 0 <= first_top <= acc.shape[0] - 8 else 255.0
    )
    trusted = peaks[0][0] >= 0.97 and first_diff <= 8.0
    span = 2 if trusted else 3 * down
    for corr, _off, t0 in peaks[:(1 if trusted else 3)]:
        for delta in range(-span, span + 1):
            top = t0 + delta
            if top < 0 or top > acc.shape[0] - 8:
                continue
            diff = overlap_row_diff(acc, frame, top)
            # 惩罚保持温和：轮播图 / GIF / 懒加载会让少量行变化，不能因此
            # 把本该通过的一帧判成匹配失败；主要靠候选间比较挑出正确位置。
            score = corr * (1.0 - min(0.4, diff / 400.0))
            # 末位用 -|delta| 作「离相关峰最近」的次级判据：渐变 / 大片留白的
            # 页面上相邻几行的逐行差可能全是 0，分不出差 1 行，此时应留在
            # 相关峰本身而不是被微调挪走（否则每拼一帧歪 1px，越拼越斜）。
            key = (score, -diff, corr, -abs(delta))
            if best_key is None or key > best_key:
                best_key, best_top, best_score = key, top, score
    if best_key is None:
        return -1, 0.0
    return best_top, float(best_score)


def detect_top_fixed(
    prev: np.ndarray,
    cur: np.ndarray,
    *,
    tol: float = 2.0,
    min_rows: int = 8,
    max_ratio: float = 0.45,
    gap: int = 6,
    blank_std: float = 3.0,
    min_changed_ratio: float = 0.25,
) -> int:
    """比较滚动前后的两帧，量出页面顶部「固定不动」的行数（sticky 顶栏高度）。

    网页顶部常有横跨整宽的固定导航 / 工具条 / Cookie 横幅：它们不随滚动
    移动，会挡住真正的新内容。模板一旦压在这块区域上就永远匹配不上，拼接
    时还会把同一段顶栏反复叠进长图，形成一条条重复的「假内容」。

    判据：滚动前后像素几乎不变（差异 < tol）**且** 该行本身有内容
    （标准差 > blank_std，排除纯白留白行）。变化行占比不足 min_changed_ratio
    时认为页面其实没滚动，直接放弃判定（否则静止页面会被误判成整屏固定）。

    返回需要从帧顶部裁掉的行数；0 表示没有检测到固定顶栏。
    """
    h = int(min(prev.shape[0], cur.shape[0]))
    if h < max(80, min_rows * 4) or prev.shape[1] != cur.shape[1]:
        return 0
    c0 = int(prev.shape[1] * 0.10)
    c1 = max(c0 + 8, int(prev.shape[1] * 0.90))
    p = prev[:h, c0:c1].astype(np.int16)
    c = cur[:h, c0:c1].astype(np.int16)
    d = np.abs(p - c)
    row_diff = d.reshape(d.shape[0], -1).mean(axis=1)
    band = prev[:h, c0:c1]
    row_std = band.reshape(band.shape[0], -1).std(axis=1)

    if float((row_diff >= tol).mean()) < min_changed_ratio:
        return 0                      # 页面没动，谈不上「固定」

    fixed = (row_diff < tol) & (row_std > blank_std)
    limit = int(h * max_ratio)
    n = 0
    gap_run = 0
    for i in range(limit):
        if bool(fixed[i]):
            n = i + 1
            gap_run = 0
        else:
            gap_run += 1
            if gap_run >= gap:        # 连续 gap 行都不是固定元素 → 顶栏到此为止
                break
    return n if n >= min_rows else 0


def stitch_scroll(
    rect: ScreenRect,
    *,
    max_height: int = 30000,
    min_new_rows: int = 40,
    match_threshold: float = 0.72,
    scroll_notches: int = -3,
    settle_seconds: float = 0.42,
    max_frames: int = 300,
    on_progress=None,
    should_stop=None,
    control: ScrollControl | None = None,
    on_before_grab=None,
    on_after_grab=None,
    bottom_confirm_frames: int = 3,
    retry_limit: int = 3,
    retry_settle: float = 0.5,
    adapt_scroll: bool = True,
    hide_overlays: bool = True,
    bottom_guard: int = 32,
    detect_fixed: bool = True,
    overshoot_ratio: float = 0.9,
    max_overshoot_fixes: int = 6,
) -> tuple[Image.Image, dict]:
    """
    自动滚动并拼接长截图（选中的窗口客户区即 rect）。

    做法：把光标移到选区右侧滚动条 → 抓帧 → 滚轮向下 → 再抓帧 →
    用模板匹配算出两帧的重叠量 → 只保留新增的部分拼到画布上。

    网页抗中断（v19）：
      · 到底必须连续 bottom_confirm_frames 帧都几乎没有新增才结束；
        单帧「没动」多半只是平滑滚动 / 惯性未稳定，或滚轮发给了别的窗口。
      · 匹配失败先减小步长、多等一拍重试 retry_limit 次，不再一帧就放弃。
      · 每帧滚轮前重新锁定光标，防止用户移动鼠标后滚错窗口。
      · 步长按上一帧新增行数自适应，避免一次滚过头导致找不到重叠。

    画质清理（v20）：
      · 临时隐藏输入法工具条 / 候选窗等与选区相交的小浮窗，结束必恢复；
        这些浮层固定在屏幕坐标，否则每帧都会被拍进去形成周期性小白条。
      · 光标改停在右侧滚动条附近而不是画面中心：停在链接上时浏览器会在
        左下角弹出 URL 提示条，滚动中链接一直换，提示条也就一帧一条。
      · 捕获区底部预留 bottom_guard 行，浏览器状态条 / 浮层底边不进画面；
        被让出的内容会在后续滚动中自然进入捕获区，滚到底后再补一帧完整
        画面把页脚那几十行接回来，长图不缺尾。
      · 匹配只取中间列带、多候选 + 重叠区一致性验证，避免浮层把重叠量
        带偏，产生大段重复内容（看起来像「拼接缝隙」）。

    v46 网页抗中断（治「截网页经常中断」）：
      1. 多模板带：不再只从帧中部取一条 120 行模板，而是在 0% / 12% / 25%
         处铺三条 60~80 行的短模板，任一条命中即可。旧参数下「重叠必须
         >= 206 行」意味着 520px 窗口单帧最多滚约 314px，而浏览器一滚
         常常 300~400px，一过线就必然失配。
      2. 步长上限联动：自适应步长不再允许滚到「重叠不足一条模板」的距离。
      3. 滚过头识别：滚动量接近整屏（scroll-snap 页面尤其常见）时**缩小
         步长重来**，不再当成「几乎没动」一路累加到判「到底」。
      4. 真到底确认：连续判定「没新增」后，先用更大步长再试一次，排除
         「滚轮没送达 / 步长太小」，仍无新增才收工。
      5. 固定顶栏剔除：detect_fixed 时用「滚动前后不变的行」量出 sticky
         导航的高度，从后续每帧顶部裁掉，避免重复叠进长图。

    control 提供交互语义：左键暂停 / 再按继续、右键结束、点「确定」结束；
    拼接线程在等待期间高频 poll()，暂停时不抓帧也不滚轮。
    on_before_grab / on_after_grab 用于「控制条与选区重叠」时，在抓帧瞬间
    临时隐藏 / 恢复控制条，避免它自己被拍进长图。

    返回 (拼接结果图, 统计信息 dict)；stats.stop_reason 记录结束原因，
    stats.retries / stats.score / stats.align_diff / stats.fixed_top /
    stats.overshoots / stats.overlays_hidden 等字段便于诊断。
    """
    # 底部预留：客户区最下面几十像素是浏览器状态条 / 浮层的高发区
    guard = min(max(0, int(bottom_guard)), max(0, rect.h // 6))
    grab_rect = ScreenRect(rect.x, rect.y, rect.w, max(1, rect.h - guard))
    # v49：旧版每次翻页前都把光标 SetCursorPos 到窗口最右侧（贴近滚动条），
    # 结果用户想移到「确定」按钮时会被一次次拉回去，几乎点不到。
    # 选窗口时用户已经把光标点在了目标窗口里，滚轮本来就会发给它，
    # 根本不需要抢光标。现在完全不动鼠标；用户一旦把光标移出窗口 / 移到
    # 控制条上，_scroll() 就停发滚轮，把控制权彻底交还给用户。
    try:
        hidden = find_floating_overlays(grab_rect) if hide_overlays else []
    except Exception:  # noqa: BLE001  探测失败不阻断拼接
        hidden = []
    hide_floating_overlays(hidden)

    canvas: np.ndarray | None = None
    notches = -abs(int(scroll_notches)) or -3
    low_new_streak = 0
    match_fail_streak = 0
    stats: dict = {
        "frames": 0,
        "stop_reason": "unknown",
        "score": 0.0,
        "align_diff": 0.0,
        "height": 0,
        "cursor_restored": False,   # v49 起不再移动光标，保留字段兼容旧诊断
        "cursor_parked": 0,         # 光标已移出抓取区 / 在控制条上，本帧停发滚轮
        "retries": 0,
        "notches": notches,
        "overlays_hidden": len(hidden),
        "bottom_guard": guard,
    }

    def _stop_requested() -> bool:
        return (control is not None and control.should_stop()) or (
            should_stop is not None and should_stop()
        )

    def _stop_reason() -> str:
        if control is not None and control.should_stop():
            return control.stop_reason or "user-confirm"
        return "user-interrupt"

    def _scroll(extra: float = 0.0) -> None:
        # 光标已离开抓取区，或正停在控制条上（用户去点「确定」）——
        # 此时绝不能继续发滚轮：一是滚轮会落到别的窗口，二是会把用户的
        # 鼠标抢回来。停发滚轮，页面静止，用户从容点击即可。
        x, y = get_cursor_pos()
        in_region = (
            rect.x <= x < rect.x + rect.w and rect.y <= y < rect.y + rect.h
        )
        in_bar = bool(control is not None and control.cursor_in_exclude())
        if not in_region or in_bar:
            stats["cursor_parked"] += 1
            _wait(0.05)
            return
        _send_mouse_wheel(notches)
        wait = settle_seconds + extra
        if control is not None:
            control.wait(wait)
        elif wait > 0:
            time.sleep(wait)

    def _progress() -> None:
        if on_progress is not None and canvas is not None:
            on_progress(stats["frames"], stats["height"], canvas, stats["score"])

    def _adapt(new_rows: int, content_h: int, t_rows: int) -> None:
        nonlocal notches
        if not adapt_scroll:
            return
        # 每帧新增行最好不超过窗口高度的 70%（再大就快滚过一整屏，相邻帧
        # 重叠太少容易失配）；太小则加大步长，避免长页面截不完。
        # v46：上限再受「至少要留一条模板高的重叠」约束——否则自适应出来的
        # 步长会比模板能容忍的还大，一滚就必失配。
        hi = max(min_new_rows * 2, min(int(content_h * 0.7), content_h - t_rows - 12))
        lo = max(1, min_new_rows * 2)
        if new_rows > hi and abs(notches) > 1:
            notches = -max(1, abs(notches) - 1)
        elif new_rows < lo and abs(notches) < 8:
            notches = -min(8, abs(notches) + 1)
        stats["notches"] = notches

    def _wait(seconds: float) -> None:
        if control is not None:
            control.wait(seconds)
        elif seconds > 0:
            time.sleep(seconds)

    def _retry(advance: bool = False) -> None:
        """单帧异常后的重试。

        advance=False（失配重试用）：**原地等待再重抓，不再往下滚**。
          旧行为是失配后继续滚一屏，于是漏掉的内容越滚越远、永远补不回来——
          页面滚过画布末尾之后就再无重叠，只能一路降级拼错。原地重抓正好
          对付「弹窗 / 视频 / 平滑滚动中间态」这类只污染一两帧的情况。

        advance=True（到底确认用）：继续滚一格，验证页面是不是真的不动了。
        """
        stats["retries"] += 1
        _progress()
        if advance:
            _scroll(retry_settle)
        else:
            _wait(retry_settle)

    fixed_top = 0
    fixed_tries = 0
    prev_frame: np.ndarray | None = None
    bottom_probed = False
    overshoots = 0
    last_new_rows: int | None = None
    good_notches = abs(notches)
    degraded = 0
    stats["fixed_top"] = 0
    stats["overshoots"] = 0
    stats["degraded"] = 0

    try:
        for i in range(max_frames):
            # 暂停：不抓帧、不滚轮，但继续监听鼠标（再点左键即继续）
            if control is not None:
                control.wait_while_paused()
            if _stop_requested():
                stats["stop_reason"] = _stop_reason()
                break

            if on_before_grab is not None:
                on_before_grab()
            try:
                # 输入法可能自己把工具条重新弹出来，每帧抓屏前再压一次
                if hidden:
                    hide_floating_overlays(hidden)
                img = grab_region(grab_rect)
            finally:
                if on_after_grab is not None:
                    on_after_grab()
            frame = np.array(img)
            stats["frames"] = i + 1

            # 固定顶栏：拿「滚动前 / 滚动后」两帧比出顶部不动的那几行。
            # 只在画布还基本是第一帧时接受结果，否则那块顶栏已经拼进长图中段，
            # 再裁帧只会让前后不一致。
            if (
                detect_fixed and fixed_top == 0 and fixed_tries < 4
                and prev_frame is not None and canvas is not None
                and canvas.shape[0] <= frame.shape[0] + 8
            ):
                fixed_tries += 1
                cand = detect_top_fixed(prev_frame, frame)
                if cand:
                    fixed_top = cand
                    stats["fixed_top"] = fixed_top
            if prev_frame is None or fixed_top == 0:
                prev_frame = frame

            content = frame[fixed_top:] if fixed_top else frame

            if canvas is None:
                canvas = frame.copy()
            else:
                content_h = int(content.shape[0])
                # 模板高度决定「能容忍多大的滚动」：重叠必须 >= 模板高才可能
                # 对上。取内容区高度的 1/10（44~72 行）——既够长到不易误匹配，
                # 又让自适应步长能放宽到 content_h - t_rows 附近。
                t_rows = min(72, max(40, content_h // 10))
                # 三条模板带：0%（大滚动也能对上）/ 12% / 25%（避开 sticky 顶栏）
                t_offs: list[int] = []
                for ratio in (0.0, 0.12, 0.25):
                    off = int(round(ratio * max(0, content_h - t_rows)))
                    if off + t_rows <= content_h and off not in t_offs:
                        t_offs.append(off)
                if not t_offs:
                    t_offs = [0]
                # 搜索窗只需覆盖「一次最大滚动 + 一条模板」的范围；旧值取
                # content_h*2 是两倍冗余，白白把每帧的匹配成本翻了一倍。
                search_rows = max(400, content_h + t_rows + 80)
                top, score = find_vertical_overlap(
                    canvas, content,
                    search_rows=search_rows,
                    template_rows=t_rows,
                    template_offset=t_offs[0],
                    template_offsets=t_offs,
                )
                stats["score"] = round(score, 4)
                stats["align_diff"] = (
                    round(overlap_row_diff(canvas, content, top), 2)
                    if top >= 0 else 255.0
                )

                if top == -1 or score < match_threshold:
                    # v46：先分清「页面压根没动」和「真的对不上」——把本帧与
                    # 画布末尾直接比一次，几乎完全相同说明是滚到到底 / 滚轮
                    # 没送达（焦点进了 iframe 之类），走到底确认流程；差异明显
                    # 说明页面确实在动、只是匹配不到（弹窗 / 视频 / scroll-snap
                    # 整屏吸附），这时绝不中断，按上次的步长降级继续拼。
                    still = 255.0
                    if canvas.shape[0] >= content_h:
                        still = overlap_row_diff(
                            canvas, content, max(0, canvas.shape[0] - content_h)
                        )
                    if still <= 4.0:
                        low_new_streak += 1
                        match_fail_streak = 0
                        if low_new_streak < bottom_confirm_frames:
                            _retry(advance=True)
                            continue
                        if not bottom_probed:
                            # 用**最小步长**再确认一次：页面真到底时它同样不会动，
                            # 而「滚轮没送达 / 步长被页面吃掉」时它能安全地只挪一点。
                            # （早先版本在这里把步长加倍，反而一探就滚过头、无重叠，
                            #  接着降级拼错，后面整段都歪。）
                            bottom_probed = True
                            notches = -1 if abs(notches) > 1 else notches
                            stats["notches"] = notches
                            _retry(advance=True)
                            continue
                        stats["stop_reason"] = "reached-bottom"
                        break
                    match_fail_streak += 1
                    if match_fail_streak <= retry_limit:
                        # 懒加载 / 动画 / 平滑滚动中间态只影响一帧：
                        # 减小步长、多等一会儿再抓，别整段长图就此收工。
                        if adapt_scroll and abs(notches) > 1:
                            notches = -max(1, abs(notches) - 1)
                            stats["notches"] = notches
                        _retry()
                        continue
                    # 降级估算：有历史就用上一次真实的滚动距离（步长不变时最准），
                    # 没有历史说明第一帧就无重叠——那多半是 scroll-snap 整屏吸附
                    # 或视口被整页替换，按「滚了整屏」处理（拼整帧）比按半屏猜
                    # 更接近真相，也不会把内容拦腰截断。
                    est_new = last_new_rows or content_h
                    new_start = max(0, min(content_h - 1, content_h - int(est_new)))
                    new_rows = content_h - new_start
                    degraded += 1
                    stats["degraded"] = degraded
                    match_fail_streak = 0
                    low_new_streak = 0
                else:
                    match_fail_streak = 0
                    # new_start 是「本帧与已拼画布的重叠行数」：越大＝滚得越少。
                    # v46 修正：旧代码把 new_start 当成「新增行数」，于是
                    # 「重叠很少＝滚过头」被误判成「几乎没动」，连续 3 帧就
                    # 假报「到底」，网页长图于是只截几屏就中断。
                    new_start = canvas.shape[0] - top

                    if new_start > content_h + 2:
                        # 重叠比整帧还多——物理上不可能，说明匹配落到了别处的
                        # 重复内容上（整屏弹窗、大片同色、图片占位符）。按失配
                        # 处理并原地重抓；若当成「没动」继续滚，就会一边滚一边
                        # 什么都没拼，白漏掉整整一屏。
                        match_fail_streak += 1
                        if match_fail_streak <= retry_limit:
                            _retry()
                            continue
                        est_new = last_new_rows or content_h
                        new_start = max(0, min(content_h - 1, content_h - int(est_new)))
                        new_rows = content_h - new_start
                        degraded += 1
                        stats["degraded"] = degraded
                        match_fail_streak = 0
                        low_new_streak = 0
                    else:
                        new_rows = content_h - new_start

                        if new_rows < min_new_rows:
                            # 页面几乎没动：到底必须连续确认，单帧不能直接判到底
                            low_new_streak += 1
                            if low_new_streak < bottom_confirm_frames:
                                _retry(advance=True)
                                continue
                            if not bottom_probed:
                                # 用**最小步长**再确认一次：页面真到底时它同样不会动，
                                # 而「滚轮没送达 / 步长被页面吃掉」时它能安全地只挪一点。
                                # （早先版本在这里把步长加倍，反而一探就滚过头、无重叠，
                                #  接着降级拼错，后面整段都歪。）
                                bottom_probed = True
                                notches = -1 if abs(notches) > 1 else notches
                                stats["notches"] = notches
                                _retry(advance=True)
                                continue
                            stats["stop_reason"] = "reached-bottom"
                            break
                        if new_start < max(12, t_rows // 2):
                            # 重叠比半条模板还少：滚过头 / scroll-snap 整屏跳动，
                            # 接缝风险高，缩小步长重来——绝不能判「到底」
                            overshoots += 1
                            stats["overshoots"] = overshoots
                            if abs(notches) > 1 and overshoots <= max_overshoot_fixes:
                                notches = -max(1, abs(notches) // 2)
                                stats["notches"] = notches
                                _retry(advance=True)
                                continue
                        low_new_streak = 0

                new_part = content[new_start:]
                if new_part.shape[0] == 0:
                    new_part = content[-1:]
                if canvas.shape[0] + new_part.shape[0] > max_height:
                    allow = max(0, max_height - canvas.shape[0])
                    if allow > 0:
                        canvas = np.vstack([canvas, new_part[:allow]])
                    stats["stop_reason"] = "max-height"
                    break

                canvas = np.vstack([canvas, new_part])
                last_new_rows = int(new_part.shape[0])
                # 失配时为了保命会把步长压到很小；一旦重新匹配成功就把它恢复到
                # 健康值，否则弹窗 / 动画过去之后会一直以 1 格慢爬，本来 20 帧
                # 的活拖成 50 帧（用户观感就是「长截图卡住了」）。
                if abs(notches) < good_notches:
                    notches = -good_notches
                _adapt(new_rows, content_h, t_rows)
                good_notches = abs(notches)

            stats["height"] = int(canvas.shape[0])
            _progress()

            if canvas.shape[0] >= max_height:
                stats["stop_reason"] = "max-height"
                break

            # 滚之前再看一眼控制状态：用户在等待期内点了右键 / 确定就别再滚了
            if control is not None:
                control.poll()
            if _stop_requested():
                stats["stop_reason"] = _stop_reason()
                break

            _scroll()
        else:
            stats["stop_reason"] = "max-frames"

        # 到底后补一帧完整高度：页面已不再滚动，完整帧比捕获区多出的
        # guard 行就是页脚，把底部预留让出的那几十像素补回长图末尾。
        if guard and stats["stop_reason"] == "reached-bottom" and canvas is not None:
            try:
                if hidden:
                    hide_floating_overlays(hidden)
                tail = np.array(grab_region(rect))
                t_rows = min(120, max(24, tail.shape[0] // 4))
                t_off = min(96, max(0, tail.shape[0] // 6))
                top_t, score_t = find_vertical_overlap(
                    canvas, tail,
                    search_rows=max(400, tail.shape[0] * 2),
                    template_rows=t_rows, template_offset=t_off,
                )
                add = canvas.shape[0] - top_t      # 重叠行数
                extra = tail.shape[0] - add          # 完整帧比捕获区多出的行数
                if (
                    top_t >= 0 and score_t >= match_threshold
                    and 0 <= add < tail.shape[0] and 0 < extra <= guard + 8
                ):
                    canvas = np.vstack([canvas, tail[add:]])
                    stats["score"] = round(score_t, 4)
            except Exception:  # noqa: BLE001  补尾失败不影响已拼好的长图
                pass

        if canvas is None:
            canvas = np.array(grab_region(grab_rect))

        stats["height"] = int(canvas.shape[0])
        return Image.fromarray(canvas), stats

    finally:
        # v49：不再恢复光标位置。用户在拼接期间可能已经把鼠标移到「确定」
        # 按钮上，强行写回起点只会让他觉得鼠标又被人抢走。
        restore_floating_overlays(hidden)


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
class OcrUnavailable(RuntimeError):
    pass


def _line(text: str, box=None, score: float = 0.0) -> dict:
    """OCR 行的统一结构。

    box 为 (x1, y1, x2, y2)，单位是**输入图像的像素坐标**；
    没有位置信息的后端填 None（前端会自动降级成整块文本面板）。
    """
    return {"text": str(text), "box": box, "score": float(score)}


def _box_from_points(points) -> tuple[float, float, float, float] | None:
    """把 N×2 顶点数组换成外接矩形 (x1,y1,x2,y2)。"""
    try:
        arr = np.asarray(points, dtype=float).reshape(-1, 2)
        if arr.size == 0:
            return None
        x1, y1 = arr.min(axis=0)
        x2, y2 = arr.max(axis=0)
        return (float(x1), float(y1), float(x2), float(y2))
    except Exception:  # noqa: BLE001
        return None


def _clean_windows_text(text: str) -> str:
    """Windows OCR 按「字」切词会在汉字间插空格，只合并 CJK 之间的空白。

    故意不动英文单词 / 数字之间的空格：截图里可能是表格的两个单元格，
    无脑粘连会把「480 160」错拼成「480160」。
    """
    import re

    cjk = r"\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef"
    return re.sub(rf"(?<=[{cjk}])[ \t]+(?=[{cjk}])", "", text)


def _ocr_windows_lines(img: Image.Image) -> list[dict]:
    """使用 Windows 内置 OCR 引擎（Windows.Media.Ocr），按行带包围框。"""
    import asyncio

    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    except ImportError as exc:  # pragma: no cover
        raise OcrUnavailable(_t("未安装 winrt 包（Windows OCR 绑定）")) from exc

    async def _run() -> list[dict]:
        # 明确优先中文引擎：英文系统上 try_create_from_user_profile_languages()
        # 会拿到 en-US，中文识别会退化甚至返回空。
        engine = None
        try:
            engine = OcrEngine.try_create_from_language(Language("zh-Hans-CN"))
        except Exception:  # noqa: BLE001
            engine = None
        if engine is None:
            engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise OcrUnavailable(_t("系统未安装可用的 OCR 语言包（需 zh-CN OCR 语言包）"))

        # Windows OCR 对输入图有最大边长限制，4K / 多显示器全屏截图会直接失败；
        # 超限先缩放，识别完再把行框坐标乘回原图尺度（否则「盖回原位」会整体偏移）。
        max_dim = 0
        for attr in ("max_image_dimension", "MaxImageDimension"):
            try:
                val = getattr(engine, attr, 0)
                max_dim = int(val) if val else 0
            except Exception:  # noqa: BLE001
                max_dim = 0
            if max_dim:
                break
        w, h = img.size
        scale = 1.0
        work = img
        if max_dim and max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            work = img.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
            )

        buf = io.BytesIO()
        work.convert("RGB").save(buf, format="BMP")
        raw = buf.getvalue()

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(raw)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        lines: list[dict] = []
        for ln in result.lines:
            box = None
            try:
                rects = [
                    (
                        float(w.bounding_rect.x),
                        float(w.bounding_rect.y),
                        float(w.bounding_rect.x + w.bounding_rect.width),
                        float(w.bounding_rect.y + w.bounding_rect.height),
                    )
                    for w in ln.words
                ]
                if rects:
                    box = (
                        min(r[0] for r in rects),
                        min(r[1] for r in rects),
                        max(r[2] for r in rects),
                        max(r[3] for r in rects),
                    )
            except Exception:  # noqa: BLE001
                box = None
            if box is not None and scale != 1.0:
                box = tuple(v / scale for v in box)
            lines.append(_line(_clean_windows_text(ln.text), box))
        return lines

    return asyncio.run(_run())


def _ocr_tesseract_lines(img: Image.Image) -> list[dict]:
    """Tesseract 兜底：image_to_data 按 (block, par, line) 聚合出带框的行。"""
    import pytesseract

    data = pytesseract.image_to_data(
        img, lang="chi_sim+eng", output_type=pytesseract.Output.DICT
    )
    groups: dict[tuple, dict] = {}
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not txt or conf < 0:
            continue
        key = (
            data["page_num"][i], data["block_num"][i],
            data["par_num"][i], data["line_num"][i],
        )
        x = int(data["left"][i])
        y = int(data["top"][i])
        x2 = x + int(data["width"][i])
        y2 = y + int(data["height"][i])
        g = groups.setdefault(key, {"parts": [], "box": [x, y, x2, y2]})
        g["parts"].append((x, txt))
        b = g["box"]
        b[0], b[1] = min(b[0], x), min(b[1], y)
        b[2], b[3] = max(b[2], x2), max(b[3], y2)

    out: list[dict] = []
    for key in sorted(groups):
        g = groups[key]
        txt = " ".join(t for _, t in sorted(g["parts"]))
        out.append(_line(txt, tuple(g["box"])))
    return out


# ---------------------------------------------------------------------------
# RapidOCR 后端（默认首选：PP-OCR 模型的 ONNX 版，轻量、中文效果好）
# ---------------------------------------------------------------------------
_rapid_engine = None  # 单例缓存：首次推理要加载 3 个 ONNX 模型


def _get_rapid_engine():
    """懒加载 RapidOCR 引擎（单例）。模型随 wheel 自带，不需要联网下载。"""
    global _rapid_engine
    if _rapid_engine is None:
        import io
        import logging
        import sys

        def _silence() -> None:
            # RapidOCR 模块级 logger("RapidOCR") 带一个 StreamHandler，且
            # RapidOCR() 构造时会把 level 重设回 config.yaml 的 INFO。
            # 换掉 handler 可避免无控制台时往 None 写入，也顺手止住 INFO 刷屏。
            for name in ("rapidocr", "RapidOCR", "onnxruntime"):
                lg = logging.getLogger(name)
                lg.setLevel(logging.ERROR)
                for h in list(lg.handlers):
                    lg.removeHandler(h)
                lg.addHandler(logging.NullHandler())
                lg.propagate = False

        # pythonw / --windowed exe 下 sys.stderr 为 None：导入 rapidocr 时
        # StreamHandler() 会绑到 None，临时给个内存流，构造完再还原。
        saved_stderr = getattr(sys, "stderr", None)
        if saved_stderr is None:
            sys.stderr = io.StringIO()
        try:
            _silence()
            from rapidocr import RapidOCR

            _silence()  # import 之后 logger 才被创建
            engine = RapidOCR()
            _silence()  # 构造之后 level 又被改回 INFO
        finally:
            sys.stderr = saved_stderr

        _rapid_engine = engine
    return _rapid_engine


def _ocr_rapid_lines(img: Image.Image) -> list[dict]:
    """RapidOCR 中文（+英文）识别，返回带行框与置信度的行列表。

    rapidocr 3.x 的 RapidOCROutput 提供 boxes(N×2 四点) / txts / scores，
    坐标已映射回输入图像像素尺度，可直接用于「逐行盖回原文位置」。
    """
    engine = _get_rapid_engine()
    arr = np.array(img.convert("RGB"))
    out = engine(arr)
    if out is None:
        return []
    boxes = getattr(out, "boxes", None)
    texts = getattr(out, "txts", None)
    scores = getattr(out, "scores", None)
    if boxes is None or texts is None:
        return []
    lines: list[dict] = []
    for i, text in enumerate(texts):
        if not text:
            continue
        box = None
        try:
            if i < len(boxes):
                box = _box_from_points(boxes[i])
        except Exception:  # noqa: BLE001
            box = None
        score = 0.0
        try:
            if scores is not None and i < len(scores):
                score = float(scores[i])
        except Exception:  # noqa: BLE001
            pass
        lines.append(_line(str(text), box, score))
    return lines


# ---------------------------------------------------------------------------
# PaddleOCR 后端（离线中文识别，方案 B）
# ---------------------------------------------------------------------------
_paddle_engine = None  # 单例缓存，避免每次取字都重新初始化（约 1~2 秒）


def _get_paddle_engine():
    """懒加载 PaddleOCR 引擎（单例）。首次调用会初始化并可能下载模型。"""
    global _paddle_engine
    if _paddle_engine is None:
        import logging

        from paddleocr import PaddleOCR

        # 静默 paddlex / paddle 的初始化日志，避免取字时刷屏
        for name in ("paddleocr", "paddlex", "ppocr"):
            logging.getLogger(name).setLevel(logging.ERROR)

        # enable_mkldnn=False 是关键：PaddlePaddle 3.x 的 oneDNN 后端在
        # 文本检测模型上有个未实现 bug，会抛 NotImplementedError。
        _paddle_engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
            cpu_threads=4,
        )
    return _paddle_engine


def _ocr_paddle_lines(img: Image.Image) -> list[dict]:
    """PaddleOCR 中文（+英文）识别，返回带 rec_boxes 坐标的行列表。

    PaddleOCR 3.x 的 predict 结果里 rec_texts / rec_scores / rec_polys /
    rec_boxes 是一一对应的；坐标已映射回输入图像像素尺度，可直接盖回原图。
    """
    engine = _get_paddle_engine()
    # predict 只接受 numpy.ndarray 或文件路径（str），不接受 bytes
    arr = np.array(img.convert("RGB"))
    result = engine.predict(arr)
    lines: list[dict] = []
    for r in result:
        texts = list(r.get("rec_texts") or [])
        scores = list(r.get("rec_scores") or [])
        polys = list(r.get("rec_polys") or [])
        boxes = r.get("rec_boxes")
        for i, text in enumerate(texts):
            if not text:
                continue
            box = None
            if boxes is not None and i < len(boxes):
                b = np.asarray(boxes[i], dtype=float).reshape(-1)
                if b.size >= 4:
                    box = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            if box is None and i < len(polys):
                box = _box_from_points(polys[i])
            score = float(scores[i]) if i < len(scores) else 0.0
            lines.append(_line(text, box, score))
    return lines


def _fix_box_scale(lines: list[dict], size: tuple[int, int]) -> list[dict]:
    """个别后端返回的是模型内部缩放后的坐标，明显越界时整体缩回原图尺度。"""
    w, h = size
    with_box = [d for d in lines if d.get("box")]
    if not with_box:
        return lines
    max_x = max(d["box"][2] for d in with_box)
    max_y = max(d["box"][3] for d in with_box)
    sx = w / max_x if max_x > w * 1.1 else 1.0
    sy = h / max_y if max_y > h * 1.1 else 1.0
    if sx == 1.0 and sy == 1.0:
        return lines
    for d in with_box:
        x1, y1, x2, y2 = d["box"]
        d["box"] = (x1 * sx, y1 * sy, x2 * sx, y2 * sy)
    return lines


def ocr_image_lines(img: Image.Image) -> tuple[list[dict], str]:
    """
    对图像做文字识别。返回 (行列表, 后端名)。

    行结构见 _line()：text + 原图像素坐标 box(x1,y1,x2,y2) + score。
    后端按可用性依次尝试：RapidOCR（首选，轻量且中文效果好）→ PaddleOCR
    → Windows 内置 OCR → Tesseract。打包成 exe 时 PaddleOCR 通常被排除，
    会自动落到后面的后端，因此 RapidOCR 是发行版的实际主力。
    """
    errors: list[str] = []
    for name, fn in (
        ("rapidocr", _ocr_rapid_lines),
        ("paddleocr", _ocr_paddle_lines),
        ("windows-ocr", _ocr_windows_lines),
        ("tesseract", _ocr_tesseract_lines),
    ):
        try:
            lines = _fix_box_scale(fn(img), img.size)
            return lines, name
        except OcrUnavailable as exc:
            errors.append(f"{name}: {exc}")
        except ImportError as exc:
            errors.append(f"{name}: {_t('缺少依赖 {error}', error=exc)}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    raise OcrUnavailable(" | ".join(errors) or _t("没有可用的 OCR 后端"))


def ocr_image(img: Image.Image) -> tuple[str, str]:
    """兼容入口：只要纯文本（自检脚本等使用），内部仍走带坐标的新链路。"""
    lines, backend = ocr_image_lines(img)
    return "\n".join(d["text"] for d in lines), backend


# ---------------------------------------------------------------------------
if __name__ == "__main__":  # 简易自检
    set_dpi_awareness()
    r = virtual_screen()
    print(f"虚拟屏幕: x={r.x} y={r.y} {r.w}x{r.h}")
    img = grab_all_screens()
    print(f"捕获成功: {img.size} 模式={img.mode}")
