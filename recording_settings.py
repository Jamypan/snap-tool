# -*- coding: utf-8 -*-
"""recording_settings.py —— v52 录屏设置（与截图设置共用 settings.json，键前缀 rec_）。

所有配置项读写都保留配置文件里的其它字段（截图热键 / 默认模式 / 语言等），
与 hotkeys.py 的 _load_raw/_save_raw 约定一致，避免互相覆盖。
"""
from __future__ import annotations

import os
from pathlib import Path

from hotkeys import _load_raw, _save_raw


def default_save_dir() -> Path:
    """与 snap.py 的默认截图目录一致（优先 图片/Screenshots）。"""
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

# 默认值
DEFAULT_FPS = 24                 # 画面帧率（15/20/24/30）
DEFAULT_REC_MODE = "rect"        # 默认录屏方式：rect / window / fullscreen
DEFAULT_SYSTEM_AUDIO = True      # 系统声音
DEFAULT_MIC = False              # 麦克风
DEFAULT_CURSOR = False           # 录制鼠标指针（预留，交给抓屏后端）
DEFAULT_CAMERA = False           # 摄像头画中画（用户要求并入）
DEFAULT_PIP_POS = "右下角"
DEFAULT_PIP_SIZE = 25            # 画中画占画面宽度百分比
# 音频保存：embed=整合进视频 / split=单独 WAV / both=两者都要
DEFAULT_AUDIO_SAVE = "embed"
# 视频里的音轨方式：mix=混合一条 / tracks=保留独立音轨
DEFAULT_AUDIO_MODE = "混合成一条音轨（推荐）"

FPS_CHOICES = (15, 20, 24, 30)
PIP_POSITIONS = ("左上角", "右上角", "左下角", "右下角")
PIP_SIZES = (15, 20, 25, 33)
AUDIO_SAVE_KEYS = ("embed", "split", "both")


def _raw() -> dict:
    return _load_raw()


def _write(**kwargs) -> bool:
    raw = _load_raw()
    raw.update(kwargs)
    return _save_raw(raw)


def load_fps() -> int:
    try:
        value = int(_raw().get("rec_fps", DEFAULT_FPS))
        return value if value in FPS_CHOICES else DEFAULT_FPS
    except (TypeError, ValueError):
        return DEFAULT_FPS


def save_fps(value: int) -> bool:
    return _write(rec_fps=value if value in FPS_CHOICES else DEFAULT_FPS)


def load_rec_mode() -> str:
    value = _raw().get("rec_mode", DEFAULT_REC_MODE)
    return value if value in ("rect", "window", "fullscreen") else DEFAULT_REC_MODE


def save_rec_mode(value: str) -> bool:
    return _write(rec_mode=value if value in ("rect", "window", "fullscreen") else DEFAULT_REC_MODE)


def _load_bool(key: str, default: bool) -> bool:
    value = _raw().get(key, default)
    return bool(value) if isinstance(value, bool) else default


def load_audio_flags() -> tuple[bool, bool, bool]:
    """返回 (系统声音, 麦克风, 录制鼠标指针)。"""
    return (
        _load_bool("rec_system_audio", DEFAULT_SYSTEM_AUDIO),
        _load_bool("rec_mic", DEFAULT_MIC),
        _load_bool("rec_cursor", DEFAULT_CURSOR),
    )


def save_audio_flags(system: bool, mic: bool, cursor: bool) -> bool:
    return _write(rec_system_audio=bool(system), rec_mic=bool(mic), rec_cursor=bool(cursor))


def load_camera_flags() -> tuple[bool, str, int]:
    """返回 (画中画开关, 位置, 大小百分比)。"""
    raw = _raw()
    pos = raw.get("rec_pip_pos", DEFAULT_PIP_POS)
    if pos not in PIP_POSITIONS:
        pos = DEFAULT_PIP_POS
    try:
        size = int(raw.get("rec_pip_size", DEFAULT_PIP_SIZE))
    except (TypeError, ValueError):
        size = DEFAULT_PIP_SIZE
    if size not in PIP_SIZES:
        size = DEFAULT_PIP_SIZE
    return _load_bool("rec_camera", DEFAULT_CAMERA), pos, size


def save_camera_flags(enabled: bool, pos: str, size: int) -> bool:
    return _write(
        rec_camera=bool(enabled),
        rec_pip_pos=pos if pos in PIP_POSITIONS else DEFAULT_PIP_POS,
        rec_pip_size=size if size in PIP_SIZES else DEFAULT_PIP_SIZE,
    )


def load_audio_save() -> str:
    value = _raw().get("rec_audio_save", DEFAULT_AUDIO_SAVE)
    return value if value in AUDIO_SAVE_KEYS else DEFAULT_AUDIO_SAVE


def save_audio_save(value: str) -> bool:
    return _write(rec_audio_save=value if value in AUDIO_SAVE_KEYS else DEFAULT_AUDIO_SAVE)


def load_audio_mode() -> str:
    value = _raw().get("rec_audio_mode", DEFAULT_AUDIO_MODE)
    modes = ("混合成一条音轨（推荐）", "保留独立音轨（播放器可切换）")
    return value if value in modes else DEFAULT_AUDIO_MODE


def save_audio_mode(value: str) -> bool:
    return _write(rec_audio_mode=value)


def load_save_dir() -> Path:
    value = _raw().get("rec_save_dir", "")
    if isinstance(value, str) and value:
        try:
            path = Path(os.path.expandvars(os.path.expanduser(value)))
            if path.is_dir():
                return path
        except Exception:  # noqa: BLE001
            pass
    return Path(default_save_dir())


def save_save_dir(path: str | Path) -> bool:
    return _write(rec_save_dir=str(path))


__all__ = [
    "DEFAULT_FPS", "DEFAULT_REC_MODE", "FPS_CHOICES", "PIP_POSITIONS", "PIP_SIZES",
    "AUDIO_SAVE_KEYS", "DEFAULT_AUDIO_SAVE", "DEFAULT_AUDIO_MODE",
    "load_fps", "save_fps", "load_rec_mode", "save_rec_mode",
    "load_audio_flags", "save_audio_flags", "load_camera_flags", "save_camera_flags",
    "load_audio_save", "save_audio_save", "load_audio_mode", "save_audio_mode",
    "load_save_dir", "save_save_dir",
]
