"""V52.4：Windows 原生「选择文件夹」对话框（IFileOpenDialog + FOS_PICKFOLDERS）。

为什么不用 QFileDialog：
    Qt 的目录模式（ShowDirsOnly）在部分平台插件 / 打包环境下会退回 Qt 自绘
    对话框，也就是「Look in:」+「Directory:」+「Choose」那套 Win9x 样式；
    旧 API SHBrowseForFolder 同样是老样式。两者都不是 Windows 10/11 的资源
    管理器风格。

这里直接调 COM 的 IFileOpenDialog 并设置 FOS_PICKFOLDERS，拿到的是系统现代
「选择文件夹」窗口：面包屑地址栏、左侧导航窗格、新建文件夹、搜索框，跟随系统
深色模式。

实现只用 ctypes 手写 vtable 调用，不引入 comtypes / pywin32，打包无额外依赖。
主线程若被第三方库占成 MTA 公寓，会自动改到临时 STA 线程里弹窗，避免死锁。
"""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import POINTER, byref, c_void_p, c_wchar_p
from ctypes import wintypes

__all__ = ["pick_folder", "available", "FolderPickerUnavailable"]


class FolderPickerUnavailable(RuntimeError):
    """当前环境拿不到原生文件夹对话框。"""


_IS_WIN = os.name == "nt"

# CLSID_FileOpenDialog / IID_IFileOpenDialog / IID_IShellItem
_CLSID_FILE_OPEN_DIALOG = "{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}"
_IID_FILE_OPEN_DIALOG = "{D57C7288-D4AD-4768-BE02-9D969532D960}"
_IID_SHELL_ITEM = "{43826D1E-E718-42EE-BC55-A1E261C37BFE}"

FOS_PICKFOLDERS = 0x00000020
FOS_FORCEFILESYSTEM = 0x00000040
FOS_NOCHANGEDIR = 0x00000008
FOS_PATHMUSTEXIST = 0x00000800

SIGDN_FILESYSPATH = 0x80058000

RPC_E_CHANGED_MODE = 0x80010106
COINIT_APARTMENTTHREADED = 0x2
CLSCTX_INPROC_SERVER = 0x1


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


if _IS_WIN:  # pragma: no cover - 平台相关
    _ole32 = ctypes.windll.ole32
    _shell32 = ctypes.windll.shell32

    _ole32.CLSIDFromString.argtypes = [c_wchar_p, POINTER(GUID)]
    _ole32.CLSIDFromString.restype = ctypes.c_long
    _ole32.CoCreateInstance.argtypes = [
        POINTER(GUID), c_void_p, wintypes.DWORD, POINTER(GUID), POINTER(c_void_p)
    ]
    _ole32.CoCreateInstance.restype = ctypes.c_long
    _ole32.CoInitializeEx.argtypes = [c_void_p, wintypes.DWORD]
    _ole32.CoInitializeEx.restype = ctypes.c_long
    _ole32.CoTaskMemFree.argtypes = [c_void_p]
    _ole32.CoTaskMemFree.restype = None
    _shell32.SHCreateItemFromParsingName.argtypes = [
        c_wchar_p, c_void_p, POINTER(GUID), POINTER(c_void_p)
    ]
    _shell32.SHCreateItemFromParsingName.restype = ctypes.c_long


def _guid(text: str) -> GUID:
    value = GUID()
    if _ole32.CLSIDFromString(c_wchar_p(text), byref(value)) != 0:
        raise FolderPickerUnavailable(f"GUID 解析失败：{text}")
    return value


def _call(ptr: c_void_p, index: int, restype, *argtypes):
    """按 vtable 下标取方法并封装成可调用的 ctypes 函数。"""
    table = ctypes.cast(ptr, POINTER(POINTER(c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
    return proto(table[index])


def _release(ptr: c_void_p) -> None:
    if not ptr:
        return
    try:
        _call(ptr, 2, ctypes.c_ulong)(ptr)      # IUnknown::Release
    except Exception:                            # noqa: BLE001
        pass


def _shell_item(path: str) -> c_void_p | None:
    """把文件系统路径转成 IShellItem，失败返回 None。"""
    iid = _guid(_IID_SHELL_ITEM)
    item = c_void_p()
    hr = _shell32.SHCreateItemFromParsingName(
        c_wchar_p(path), None, byref(iid), byref(item))
    if hr != 0 or not item:
        return None
    return item


def _pick_blocking(title: str, initial: str | None, owner: int) -> str | None:
    """在当前（STA）线程弹出原生选择文件夹窗口，取消返回 None。"""
    clsid = _guid(_CLSID_FILE_OPEN_DIALOG)
    iid = _guid(_IID_FILE_OPEN_DIALOG)
    dialog = c_void_p()
    hr = _ole32.CoCreateInstance(
        byref(clsid), None, CLSCTX_INPROC_SERVER, byref(iid), byref(dialog))
    if hr != 0 or not dialog:
        raise FolderPickerUnavailable(
            f"CoCreateInstance 失败：0x{hr & 0xFFFFFFFF:08X}")

    try:
        # 只挑文件夹，且必须是真实存在的文件系统路径
        options = wintypes.DWORD(0)
        get_options = _call(dialog, 10, ctypes.c_long, POINTER(wintypes.DWORD))
        if get_options(dialog, byref(options)) == 0:
            set_options = _call(dialog, 9, ctypes.c_long, wintypes.DWORD)
            set_options(dialog, options.value | FOS_PICKFOLDERS
                        | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST
                        | FOS_NOCHANGEDIR)
        else:
            set_options = _call(dialog, 9, ctypes.c_long, wintypes.DWORD)
            set_options(dialog, FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
                        | FOS_PATHMUSTEXIST | FOS_NOCHANGEDIR)

        if title:
            _call(dialog, 17, ctypes.c_long, c_wchar_p)(dialog, title)

        if initial and os.path.isdir(initial):
            item = _shell_item(initial)
            if item:
                try:
                    _call(dialog, 12, ctypes.c_long, c_void_p)(dialog, item)
                finally:
                    _release(item)

        hwnd = wintypes.HWND(int(owner or 0))
        hr = _call(dialog, 3, ctypes.c_long, wintypes.HWND)(dialog, hwnd)
        if hr != 0:                      # 用户取消 / 关闭
            return None

        result = c_void_p()
        get_result = _call(dialog, 20, ctypes.c_long, POINTER(c_void_p))
        if get_result(dialog, byref(result)) != 0 or not result:
            return None
        try:
            name = c_wchar_p()
            get_name = _call(result, 5, ctypes.c_long, wintypes.DWORD,
                             POINTER(c_wchar_p))
            if get_name(result, SIGDN_FILESYSPATH, byref(name)) != 0:
                return None
            path = name.value or ""
            try:
                _ole32.CoTaskMemFree(ctypes.cast(name, c_void_p))
            except Exception:            # noqa: BLE001
                pass
            return path or None
        finally:
            _release(result)
    finally:
        _release(dialog)


def available() -> bool:
    """检测当前环境能否创建原生 IFileOpenDialog（只创建不弹窗）。"""
    if not _IS_WIN:
        return False
    try:
        hr = _ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED) & 0xFFFFFFFF
        if hr not in (0, 1, RPC_E_CHANGED_MODE):
            return False
        clsid = _guid(_CLSID_FILE_OPEN_DIALOG)
        iid = _guid(_IID_FILE_OPEN_DIALOG)
        dialog = c_void_p()
        rc = _ole32.CoCreateInstance(
            byref(clsid), None, CLSCTX_INPROC_SERVER, byref(iid), byref(dialog))
        if rc != 0 or not dialog:
            return False
        _release(dialog)
        return True
    except Exception:                    # noqa: BLE001
        return False


def pick_folder(title: str, initial: str | None = None, owner: int = 0) -> str | None:
    """弹出 Windows 原生「选择文件夹」窗口。

    :param title: 窗口标题。
    :param initial: 初始目录，不存在则忽略。
    :param owner: 归属窗口句柄，0 表示无归属（主窗口隐藏时用）。
    :returns: 选中的绝对路径；用户取消返回 None。
    :raises FolderPickerUnavailable: 当前线程 / 环境用不了原生对话框。
    """
    if not _IS_WIN:
        raise FolderPickerUnavailable("仅支持 Windows")

    hr = _ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED) & 0xFFFFFFFF
    if hr in (0, 1):                     # S_OK / S_FALSE：当前线程是 STA
        return _pick_blocking(title, initial, owner)
    if hr != RPC_E_CHANGED_MODE:
        raise FolderPickerUnavailable(f"CoInitializeEx 失败：0x{hr:08X}")

    # 主线程已经是 MTA，原生 Shell 对话框会死锁：换一个干净的 STA 线程
    box: dict[str, object] = {}
    done = threading.Event()

    def _worker() -> None:
        try:
            code = _ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED) & 0xFFFFFFFF
            if code not in (0, 1):
                raise FolderPickerUnavailable(
                    f"STA 线程初始化失败：0x{code:08X}")
            box["path"] = _pick_blocking(title, initial, 0)
        except Exception as exc:         # noqa: BLE001
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=_worker, daemon=True,
                     name="snaptool-folder-picker").start()
    while not done.wait(0.05):
        pass
    if "error" in box:
        raise box["error"]               # type: ignore[misc]
    return box.get("path")               # type: ignore[return-value]
