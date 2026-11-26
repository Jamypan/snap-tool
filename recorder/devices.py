"""设备检测：列出可用的显示器、系统声音回录设备、麦克风和摄像头。

经验证（python 与 pythonw 双环境实测）：
- soundcard 的枚举与采集不需要额外显式 COM 初始化（库自身模块级初始化即可），
  反而是"先显式 CoInitializeEx 再用 soundcard"在 pythonw 下会导致卡死；
- OpenCV 的 DSHOW 后端会在当前线程配对 CoInitialize/CoUninitialize，
  在主线程扫描摄像头可能破坏 soundcard 的 COM 状态，因此放到独立线程执行。
- 设备名称在枚举时立即取好（包装成 AudioDeviceInfo），避免之后再触碰 COM。
"""
from __future__ import annotations

import threading

import cv2
import mss
import soundcard as sc


class AudioDeviceInfo:
    """soundcard 设备的轻量包装：名称在枚举时取好，之后无需再触碰 COM。"""

    def __init__(self, device, name: str) -> None:
        self.device = device
        self.name = name

    def __repr__(self) -> str:  # 方便日志
        return f"<AudioDeviceInfo {self.name!r}>"


def list_displays() -> list[tuple[int, str, int, int]]:
    """返回 [(索引, 名称, 宽, 高), ...]，索引 0 表示全部显示器。"""
    result: list[tuple[int, str, int, int]] = []
    try:
        with mss.MSS() as sct:
            monitors = sct.monitors
            if len(monitors) > 1:
                virtual = monitors[0]
                result.append((0, "全部屏幕（拼接）", int(virtual["width"]), int(virtual["height"])))
            for i, mon in enumerate(monitors[1:], start=1):
                result.append((i, f"显示器 {i}", int(mon["width"]), int(mon["height"])))
    except Exception:  # noqa: BLE001 - 设备检测失败时返回空列表，由界面提示
        pass
    return result


def get_display_size(index: int) -> tuple[int, int]:
    """获取指定显示器的宽高，宽高强制为偶数以便 H.264 编码。"""
    with mss.MSS() as sct:
        monitor = sct.monitors[index]
        width = int(monitor["width"])
        height = int(monitor["height"])
    return width - width % 2, height - height % 2


def _enumerate_audio(include_loopback: bool) -> list[AudioDeviceInfo]:
    try:
        result: list[AudioDeviceInfo] = []
        for m in sc.all_microphones(include_loopback=True):
            is_loop = getattr(m, "isloopback", False)
            if is_loop != include_loopback:
                continue  # 按调用意图过滤：回录列表只要回录设备，麦克风列表只要真实麦克风
            try:
                name = m.name
            except Exception:  # noqa: BLE001 - 个别设备名取不到不影响整体
                name = "未知设备"
            result.append(AudioDeviceInfo(m, name))
        return result
    except Exception:  # noqa: BLE001 - 枚举失败返回空列表，由界面提示
        return []


def list_loopback_devices() -> list[AudioDeviceInfo]:
    """系统声音回录设备（即扬声器正在播放的声音）。"""
    return _enumerate_audio(include_loopback=True)


def list_microphones() -> list[AudioDeviceInfo]:
    """麦克风输入设备，不含回录设备。"""
    return _enumerate_audio(include_loopback=False)


def _scan_cameras(limit: int) -> list[int]:
    """在独立线程里扫描摄像头：DSHOW 后端会配对 COM 初始化/清理，
    放在主线程上可能破坏 soundcard 已建立的 COM 状态。"""
    found: list[int] = []
    for index in range(limit):
        cap = None
        try:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ok, _frame = cap.read()
                if ok:
                    found.append(index)
        except Exception:  # noqa: BLE001
            pass
        finally:
            if cap is not None:
                cap.release()
    return found


def list_cameras(limit: int = 4) -> list[int]:
    """检测可用的摄像头索引（独立线程执行，保护主线程 COM 状态）。"""
    result: list[int] = []
    worker = threading.Thread(target=lambda: result.extend(_scan_cameras(limit)), daemon=True)
    worker.start()
    worker.join(timeout=30)
    return result
