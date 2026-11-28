# -*- coding: utf-8 -*-
"""剪贴板写图（V52.6）。

旧实现直接调用 QClipboard.setImage()，并用 except: pass 把失败吞掉：
一旦剪贴板被别的程序短暂占用、或 Qt 的图片写入没成功，系统剪贴板里
留下的还是用户之前复制的文本，界面却提示「已复制到剪贴板」，粘贴出来
自然还是文字。

本模块的做法：
1. 优先用 Win32 原生 API：OpenClipboard → EmptyClipboard → SetClipboardData
   (CF_DIB)。EmptyClipboard 会明确清掉旧文本，CF_DIB 是 Windows 上通用
   的位图格式，Word / 微信 / 浏览器 / 画图都能识别。
2. 写完后用 GetClipboardData(CF_DIB) 校验，确认系统里真的有图。
3. 失败重试；仍失败才回退 Qt setImage，并如实返回成功与否。
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

CF_DIB = 8
CF_TEXT = 1
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
BI_RGB = 0


def _setup_win32():
    """为 Win32 API 声明正确的参数与返回类型。

    V52.6 首次发布时遗漏了这一步：ctypes 默认把函数返回值当作 32 位 int，
    在 64 位 Python 里 HGLOBAL/HANDLE 这类指针会被截断，GlobalLock 拿到错误
    地址、SetClipboardData 失败，原生写图形同虚设，剪贴板里仍是旧文本。
    这里显式把返回句柄的函数声明为 c_void_p，保证 64 位地址完整。
    """
    if sys.platform != "win32":
        return None, None
    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32
    u32.OpenClipboard.argtypes = [wintypes.HWND]
    u32.OpenClipboard.restype = wintypes.BOOL
    u32.CloseClipboard.argtypes = []
    u32.CloseClipboard.restype = wintypes.BOOL
    u32.EmptyClipboard.argtypes = []
    u32.EmptyClipboard.restype = wintypes.BOOL
    u32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    u32.SetClipboardData.restype = ctypes.c_void_p
    u32.GetClipboardData.argtypes = [wintypes.UINT]
    u32.GetClipboardData.restype = ctypes.c_void_p
    u32.EnumClipboardFormats.argtypes = [wintypes.UINT]
    u32.EnumClipboardFormats.restype = wintypes.UINT
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalAlloc.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    k32.GlobalUnlock.restype = wintypes.BOOL
    k32.GlobalFree.argtypes = [ctypes.c_void_p]
    k32.GlobalFree.restype = ctypes.c_void_p
    return u32, k32


_user32, _kernel32 = _setup_win32()


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _dib_from_qimage(img: QImage) -> bytes | None:
    """QImage → 32 位自下而上 DIB 字节串（含 BITMAPINFOHEADER）。"""
    try:
        src = (
            img
            if img.format() == QImage.Format_ARGB32
            else img.convertToFormat(QImage.Format_ARGB32)
        )
        w, h = src.width(), src.height()
        if w <= 0 or h <= 0:
            return None
        bpl = src.bytesPerLine()
        raw = bytes(src.constBits())
        if len(raw) < bpl * h:
            return None
        # DIB 的正高度表示自下而上，所以按行倒序写入
        pixels = b"".join(raw[y * bpl:(y + 1) * bpl] for y in range(h - 1, -1, -1))
        header = _BITMAPINFOHEADER(
            ctypes.sizeof(_BITMAPINFOHEADER), w, h, 1, 32, BI_RGB,
            len(pixels), 0, 0, 0, 0,
        )
        return bytes(header) + pixels
    except Exception:  # noqa: BLE001
        return None


def _open_clipboard(user32, tries: int = 8) -> bool:
    """剪贴板可能被别的程序短暂占用，短间隔重试。"""
    for _ in range(max(1, tries)):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def _native_put(dib: bytes) -> bool:
    """用 Win32 API 清空剪贴板并写入 DIB。"""
    user32, kernel32 = _user32, _kernel32
    if user32 is None or kernel32 is None:
        return False
    if not _open_clipboard(user32):
        return False
    hmem = None
    try:
        if not user32.EmptyClipboard():
            return False
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib))
        if not hmem:
            return False
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            kernel32.GlobalFree(hmem)
            hmem = None
            return False
        try:
            ctypes.memmove(ptr, dib, len(dib))
        finally:
            kernel32.GlobalUnlock(hmem)
        if not user32.SetClipboardData(CF_DIB, hmem):
            kernel32.GlobalFree(hmem)
            hmem = None
            return False
        # 成功后内存归系统所有，不能再 GlobalFree
        hmem = None
        return True
    finally:
        if hmem is not None:
            try:
                kernel32.GlobalFree(hmem)
            except Exception:  # noqa: BLE001
                pass
        user32.CloseClipboard()


def _native_has_image() -> bool:
    """校验系统剪贴板里确实有位图，而不是只剩旧文本。"""
    user32 = _user32
    if user32 is None:
        return False
    if not _open_clipboard(user32, tries=3):
        return False
    try:
        return bool(user32.GetClipboardData(CF_DIB))
    except Exception:  # noqa: BLE001
        return False
    finally:
        user32.CloseClipboard()


def _native_text_formats() -> list[int]:
    """列出剪贴板里的文本格式；正常写图后应为空。"""
    user32 = _user32
    if user32 is None or not _open_clipboard(user32, tries=3):
        return []
    found: list[int] = []
    try:
        fmt = 0
        while True:
            fmt = user32.EnumClipboardFormats(fmt)
            if not fmt:
                break
            if fmt in (CF_TEXT, CF_UNICODETEXT, 7):  # 7 = CF_OEMTEXT
                found.append(fmt)
    except Exception:  # noqa: BLE001
        pass
    finally:
        user32.CloseClipboard()
    return found


def put_image(img: QImage) -> bool:
    """把图片写入系统剪贴板并替换掉原有文本；成功返回 True。"""
    if img is None or img.isNull():
        return False

    # 离屏自测没有真实系统剪贴板，直接走 Qt 回退，避免碰到用户剪贴板
    use_native = sys.platform == "win32"
    try:
        app = QApplication.instance()
        if app is not None and app.platformName() == "offscreen":
            use_native = False
    except Exception:  # noqa: BLE001
        pass

    dib = _dib_from_qimage(img) if use_native else None
    if dib:
        for _ in range(3):
            try:
                if _native_put(dib) and _native_has_image():
                    # 图片在位且旧文本已清除才算真正成功
                    if not _native_text_formats():
                        return True
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.04)

    # 原生路径不可用时的兜底：Qt 自身写入，并回读确认
    try:
        clip = QApplication.clipboard()
        clip.clear()
        clip.setImage(img)
        return not clip.image().isNull()
    except Exception:  # noqa: BLE001
        return False
