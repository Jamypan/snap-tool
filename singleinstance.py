# -*- coding: utf-8 -*-
"""单实例守卫（Windows）。

旧实现只用一个命名互斥体 + ``kernel32.GetLastError()`` 判断，有两个坑：

1. ``CreateMutexW`` 新建成功时**不会**把线程的 last-error 清零，前面
   ``set_dpi_awareness()`` 等 Win32 调用留下的 183 会让程序误报「已在运行」；
   而通过 ``ctypes.windll.kernel32.GetLastError()`` 取值又可能被调用链本身
   改写，反过来漏报。这里改用 ``WinDLL(use_last_error=True)``、调用前
   ``SetLastError(0)``、调用后 ``ctypes.get_last_error()``，并显式声明 64 位
   HANDLE 返回值。
2. 互斥体只说明「有进程持有句柄」，不说明那个进程还有可见界面。程序崩在
   半路、或截图时窗口被隐藏没恢复，就会留下「活着但看不见」的后台实例，
   之后每次启动都提示「已经在运行」。

因此额外维护 ``%APPDATA%/SnapTool/instance.json``：记录当前实例的 PID 与
**进程创建时间**（避免 PID 被系统复用造成误判）。互斥体报「已存在」时再
校验这个进程是否还是同一个：不在了就当作陈旧锁，直接接管启动；还在就
认为是真实例，交给调用方决定唤醒或结束重启。

对外主要 API：
    probe()                       -> InstanceState("ok" | "stale" | "running")
    classify(...)                 -> 纯判定逻辑，便于自测
    release()                     -> 退出时清掉自己的实例记录
    kill_recorded(record)         -> 结束后台实例（含子进程树）
    signal_existing()             -> 请已有实例把主窗口显示出来
    install_activation_notifier() -> 已有实例侧监听唤醒请求
"""
from __future__ import annotations

import atexit
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

MUTEX_NAME = "SnapTool_SingleInstance_Mutex"
ACTIVATE_EVENT_NAME = "SnapTool_ActivateExisting_Event"
ERROR_ALREADY_EXISTS = 183

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_EVENT_MODIFY_STATE = 0x0002
_SYNCHRONIZE = 0x00100000

_IS_WIN = sys.platform == "win32"
_k32 = ctypes.WinDLL("kernel32", use_last_error=True) if _IS_WIN else None
_APP_DIR = Path(os.environ.get("APPDATA") or os.path.expanduser("~")) / "SnapTool"
INSTANCE_FILE = _APP_DIR / "instance.json"
STARTUP_LOG = _APP_DIR / "startup.log"

_mutex_handle: int | None = None
_activate_handle: int | None = None


def _setup_prototypes() -> None:
    """显式声明签名，避免 64 位 HANDLE 被 ctypes 默认的 c_int 截断。"""
    if _k32 is None:
        return
    _k32.SetLastError.argtypes = (wintypes.DWORD,)
    _k32.SetLastError.restype = None
    _k32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    _k32.CreateMutexW.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    _k32.GetProcessTimes.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.CreateEventW.argtypes = (
        ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
    )
    _k32.CreateEventW.restype = wintypes.HANDLE
    _k32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    _k32.OpenEventW.restype = wintypes.HANDLE
    _k32.SetEvent.argtypes = (wintypes.HANDLE,)
    _k32.SetEvent.restype = wintypes.BOOL
    _k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _k32.WaitForSingleObject.restype = wintypes.DWORD


_setup_prototypes()


@dataclass
class InstanceState:
    state: str                       # "ok" | "stale" | "running"
    record: dict = field(default_factory=dict)
    reason: str = ""


# ---------------------------------------------------------------------------
# 进程身份
# ---------------------------------------------------------------------------
def pid_signature(pid: int) -> str | None:
    """进程创建时间（FILETIME 拼成的整数字符串）；进程不存在/不可查返回 None。

    PID 会被系统复用，只比对 PID 不够；创建时间一致基本可确认是同一个进程。
    """
    if _k32 is None or not isinstance(pid, int) or pid <= 0:
        return None
    h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not _k32.GetProcessTimes(
            h, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user),
        ):
            return None
        return str((created.dwHighDateTime << 32) | created.dwLowDateTime)
    finally:
        _k32.CloseHandle(h)


def own_record() -> dict:
    return {
        "pid": os.getpid(),
        "sig": pid_signature(os.getpid()) or "",
        "exe": Path(sys.executable).name,
        "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# 实例记录文件
# ---------------------------------------------------------------------------
def read_record() -> dict:
    try:
        data = json.loads(INSTANCE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001  文件不存在 / 损坏 / 权限问题都当没有记录
        return {}


def write_record() -> dict:
    rec = own_record()
    try:
        INSTANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        INSTANCE_FILE.write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # noqa: BLE001
        log(f"写实例记录失败：{exc}")
    return rec


def release() -> None:
    """只清掉「自己写的」记录，避免误删另一个实例刚写的。"""
    try:
        rec = read_record()
        mine = own_record()
        if rec.get("pid") == mine["pid"] and rec.get("sig") == mine["sig"]:
            INSTANCE_FILE.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


def log(msg: str) -> None:
    """启动诊断日志，便于排查「提示已运行」这类问题。"""
    try:
        STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with STARTUP_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} [{os.getpid()}] {msg}\n")
    except Exception:  # noqa: BLE001
        pass


atexit.register(release)


# ---------------------------------------------------------------------------
# 判定
# ---------------------------------------------------------------------------
def classify(error_code: int, handle_ok: bool, record: dict, self_pid: int) -> tuple[str, str]:
    """纯逻辑：由 CreateMutexW 结果与实例记录得出 (state, reason)。

    抽成无副作用函数，方便自测覆盖各种组合，不依赖真实进程状态。
    """
    if not handle_ok:
        # 互斥体创建失败时不阻止启动（宁可多开，也不能把用户挡在门外）
        return "ok", "mutex-unavailable"
    if error_code != ERROR_ALREADY_EXISTS:
        return "ok", "new-instance"

    pid = record.get("pid")
    sig = record.get("sig")
    if not isinstance(pid, int) or pid <= 0 or not sig:
        return "stale", "no-record"
    if pid == self_pid:
        return "stale", "self-record"
    if pid_signature(pid) != sig:
        return "stale", "dead-or-reused-pid"
    return "running", "alive"


def probe() -> InstanceState:
    """获取互斥体并判定当前是否有真正活着的实例。

    "ok"      可以启动（新建锁 / 拿不到锁但不阻止启动）
    "stale"   锁存在但记录中的进程已不在，自动接管启动
    "running" 确实有同程序的实例在跑，交调用方处理
    """
    global _mutex_handle
    if _k32 is None:
        return InstanceState("ok", {}, "not-win32")

    # 关键：先清零，否则上一次 Win32 调用残留的 183 会造成误报
    _k32.SetLastError(0)
    handle = _k32.CreateMutexW(None, False, MUTEX_NAME)
    err = ctypes.get_last_error()
    if handle:
        _mutex_handle = int(handle)  # 持有到进程结束，锁才不会提前消失

    record = read_record() if err == ERROR_ALREADY_EXISTS else {}
    state, reason = classify(err, bool(handle), record, os.getpid())
    log(f"probe err={err} handle={bool(handle)} record={record} -> {state}/{reason}")

    if state in ("ok", "stale"):
        new_rec = write_record()
        return InstanceState(state, new_rec, reason)
    return InstanceState("running", record, reason)


# ---------------------------------------------------------------------------
# 唤醒 / 结束后台实例
# ---------------------------------------------------------------------------
def create_activation_event() -> int | None:
    """创建自动复位事件，供本实例监听「请显示主窗口」请求。"""
    global _activate_handle
    if _k32 is None:
        return None
    h = _k32.CreateEventW(None, False, False, ACTIVATE_EVENT_NAME)
    if not h:
        return None
    _activate_handle = int(h)
    return _activate_handle


def install_activation_notifier(handler):
    """在 Qt 事件循环里监听唤醒请求；返回 QTimer，调用方必须持有引用。

    这里没有用 QWinEventNotifier：不同 PySide6 版本对原生 HANDLE 的参数类型
    要求不一致（6.12 会把 Python int 句柄判成参数不匹配）。改用 300ms 轮询
    WaitForSingleObject(h, 0)，一次系统调用、开销可忽略，且完全兼容。
    auto-reset 事件被取到后自动复位，不会重复触发。

    任何异常都只让「唤醒」功能失效，绝不影响主程序启动。
    """
    try:
        from PySide6.QtCore import QTimer

        h = create_activation_event()
        if not h:
            return None
        timer = QTimer()
        timer.setInterval(300)

        def _poll() -> None:
            if _k32 is not None and _k32.WaitForSingleObject(h, 0) == 0:
                handler()

        timer.timeout.connect(_poll)
        timer.start()
        return timer
    except Exception as exc:  # noqa: BLE001
        log(f"唤醒监听不可用：{exc}")
        return None


def signal_existing() -> bool:
    """请已在运行的实例把主窗口显示出来（旧版本没有监听时返回 False）。"""
    if _k32 is None:
        return False
    h = _k32.OpenEventW(_EVENT_MODIFY_STATE, False, ACTIVATE_EVENT_NAME)
    if not h:
        return False
    try:
        return bool(_k32.SetEvent(h))
    finally:
        _k32.CloseHandle(h)


def find_other_instances() -> list[int]:
    """列出「命令行指向本项目 snap.py」的其它进程 PID。

    用于 --restart 清掉旧版本留下的幽灵实例：它们不写 instance.json，
    仅靠记录文件是找不到它们的。
    """
    if not _IS_WIN:
        return []
    ps_cmd = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.CommandLine -like '*snap.py*' -and "
        "($_.Name -eq 'pythonw.exe' -or $_.Name -eq 'python.exe' "
        "-or $_.Name -eq 'SnapTool.exe') -and "
        f"$_.ProcessId -ne {os.getpid()} }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        cp = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=20, startupinfo=startup,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return [int(x) for x in (cp.stdout or "").split() if x.strip().isdigit()]
    except Exception as exc:  # noqa: BLE001
        log(f"枚举残留进程失败：{exc}")
        return []


def kill_other_instances() -> list[int]:
    """结束所有命令行指向 snap.py 的其它进程，返回被处理的 PID 列表。

    额外排除自己与自己的父进程：从 ``python -c`` 里调用时，父进程的命令行
    也可能带 ``snap.py`` 字样，而 taskkill /T 会连进程树一起结束。
    """
    protect = {os.getpid()}
    try:
        protect.add(os.getppid())
    except Exception:  # noqa: BLE001
        pass
    pids = [pid for pid in find_other_instances() if pid not in protect]
    for pid in pids:
        try:
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=8, startupinfo=startup,
            )
            log(f"--restart 结束残留实例 PID {pid}")
        except Exception as exc:  # noqa: BLE001
            log(f"结束 PID {pid} 失败：{exc}")
    return pids


def kill_recorded(record: dict) -> bool:
    """结束后台实例（含子进程树），返回该 PID 是否已消失。

    即便还有别的幽灵进程持有互斥体也没关系：它不在记录里，下次 probe 会因
    「记录中的 PID 已死」判定 stale，自动接管启动。
    """
    pid = record.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        startup = None
        if _IS_WIN:
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            startupinfo=startup,
        )
        log(f"taskkill /PID {pid} /T /F")
    except Exception as exc:  # noqa: BLE001
        log(f"结束后台实例失败：{exc}")

    for _ in range(12):
        if pid_signature(pid) is None:
            return True
        time.sleep(0.15)
    return False
