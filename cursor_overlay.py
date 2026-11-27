# -*- coding: utf-8 -*-
"""cursor_overlay.py —— V52.5 把系统鼠标指针画进录屏帧。

mss.grab() 抓到的是屏幕像素，Windows 的光标是单独叠加的，不在抓屏结果里，
所以只把「录制鼠标指针」开关存进配置是没用的 —— 必须每帧把光标画上去。

这里用 Win32 GDI 取当前光标图标（CURSORINFO / GetIconInfo / GetDIBits），
拿到带 alpha 的像素和热点，再按屏幕坐标合成到帧上。纯 ctypes 实现，不依赖
pywin32 / Pillow，打包不需要额外 DLL。
"""
from __future__ import annotations

import ctypes
import os
from ctypes import POINTER, byref, c_void_p
from ctypes import wintypes

import numpy as np

__all__ = ["load_cursor", "overlay_cursor"]

CURSOR_SHOWING = 0x00000001
DIB_RGB_COLORS = 0
BI_RGB = 0


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HICON),
        ("ptScreenPos", wintypes.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.c_long),
        ("bmWidth", ctypes.c_long),
        ("bmHeight", ctypes.c_long),
        ("bmWidthBytes", ctypes.c_long),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


_IS_WIN = os.name == "nt"

if _IS_WIN:  # pragma: no cover - 平台相关
    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    _user32.GetCursorInfo.argtypes = [POINTER(CURSORINFO)]
    _user32.GetCursorInfo.restype = wintypes.BOOL
    _user32.GetIconInfo.argtypes = [wintypes.HICON, POINTER(ICONINFO)]
    _user32.GetIconInfo.restype = wintypes.BOOL
    _user32.GetDC.argtypes = [wintypes.HWND]
    _user32.GetDC.restype = wintypes.HDC
    _user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _user32.ReleaseDC.restype = ctypes.c_int
    _gdi32.GetObjectW.argtypes = [wintypes.HGDIOBJ, ctypes.c_int, c_void_p]
    _gdi32.GetObjectW.restype = ctypes.c_int
    _gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        c_void_p, POINTER(BITMAPINFOHEADER), wintypes.UINT,
    ]
    _gdi32.GetDIBits.restype = ctypes.c_int
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _gdi32.DeleteObject.restype = wintypes.BOOL


def _dib_bits(hdc, bitmap, start: int, count: int, width: int, height: int):
    """把位图读成 top-down 的 BGRA 数组，失败返回 None。"""
    info = BITMAPINFOHEADER()
    info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.biWidth = width
    info.biHeight = -height          # 负值 = top-down，行顺序与 numpy 一致
    info.biPlanes = 1
    info.biBitCount = 32
    info.biCompression = BI_RGB
    info.biSizeImage = width * height * 4

    buf = (ctypes.c_ubyte * (width * height * 4))()
    got = _gdi32.GetDIBits(
        hdc, bitmap, start, count, buf, byref(info), DIB_RGB_COLORS)
    if got <= 0:
        return None
    return np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 4).copy()


def load_cursor():
    """读取当前系统光标。

    :returns: (screen_x, screen_y, hotspot_x, hotspot_y, RGBA ndarray)
              光标隐藏 / 读取失败返回 None。
    """
    if not _IS_WIN:
        return None
    info = CURSORINFO()
    info.cbSize = ctypes.sizeof(CURSORINFO)
    if not _user32.GetCursorInfo(byref(info)):
        return None
    if not (info.flags & CURSOR_SHOWING) or not info.hCursor:
        return None

    icon = ICONINFO()
    if not _user32.GetIconInfo(info.hCursor, byref(icon)):
        return None

    try:
        bitmap = icon.hbmColor or icon.hbmMask
        bm = BITMAP()
        if _gdi32.GetObjectW(bitmap, ctypes.sizeof(BITMAP), byref(bm)) <= 0:
            return None
        width, total_h = int(bm.bmWidth), int(bm.bmHeight)
        if width <= 0 or total_h <= 0:
            return None

        # 单色光标：hbmMask 上半是 AND mask（1 = 透明），下半是 XOR 图形
        mono = not bool(icon.hbmColor)
        height = total_h // 2 if mono else total_h
        if height <= 0:
            return None

        hdc = _user32.GetDC(0)
        if not hdc:
            return None
        try:
            bgra = _dib_bits(hdc, bitmap, 0, height, width, height)
            if bgra is None:
                return None
            rgba = bgra[:, :, [2, 1, 0, 3]].copy()   # BGRA -> RGBA
            if mono:
                mask = _dib_bits(hdc, icon.hbmMask, 0, height, width, height)
                if mask is None:
                    return None
                rgba[:, :, 3] = np.where(mask[:, :, 0] == 0, 255, 0).astype(np.uint8)
            return (
                int(info.ptScreenPos.x), int(info.ptScreenPos.y),
                int(icon.xHotspot), int(icon.yHotspot), rgba,
            )
        finally:
            _user32.ReleaseDC(0, hdc)
    except Exception:                    # noqa: BLE001 - 取光标失败不能中断录制
        return None
    finally:
        # GetIconInfo 创建的位图必须由调用方释放，否则长时间录制会泄漏 GDI 对象
        if icon.hbmMask:
            _gdi32.DeleteObject(icon.hbmMask)
        if icon.hbmColor:
            _gdi32.DeleteObject(icon.hbmColor)


def overlay_cursor(frame: np.ndarray, left: int, top: int,
                   source_width: int, source_height: int) -> np.ndarray:
    """把当前光标合成到帧上，原地修改并返回 frame。

    left/top 是抓屏区域在虚拟桌面上的物理坐标；source_width/height 是抓屏原始
    尺寸，帧若因奇数宽高被 resize 过，会按比例换算光标位置和大小。
    """
    if frame is None or not hasattr(frame, "shape"):
        return frame
    data = load_cursor()
    if data is None:
        return frame

    screen_x, screen_y, hotspot_x, hotspot_y, rgba = data
    fh, fw = frame.shape[:2]
    if source_width <= 0 or source_height <= 0 or fw <= 0 or fh <= 0:
        return frame

    scale_x, scale_y = fw / float(source_width), fh / float(source_height)
    if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
        ch, cw = rgba.shape[:2]
        xs = np.clip((np.arange(max(1, int(round(cw * scale_x)))) / scale_x).astype(int), 0, cw - 1)
        ys = np.clip((np.arange(max(1, int(round(ch * scale_y)))) / scale_y).astype(int), 0, ch - 1)
        rgba = rgba[np.ix_(ys, xs)]

    dx = int(round((screen_x - int(left) - hotspot_x) * scale_x))
    dy = int(round((screen_y - int(top) - hotspot_y) * scale_y))
    ch, cw = rgba.shape[:2]

    # 裁剪到帧内
    x0, y0 = max(0, dx), max(0, dy)
    x1, y1 = min(fw, dx + cw), min(fh, dy + ch)
    if x0 >= x1 or y0 >= y1:
        return frame

    patch = rgba[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
    dst = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (
        dst * (1.0 - alpha) + patch[:, :, :3].astype(np.float32) * alpha
    ).astype(np.uint8)
    return frame
