# -*- coding: utf-8 -*-
"""i18n.py —— 界面语言管理：8 种语言 + 启动时跟随系统语言。

设计要点：
  * 独立于其它业务模块（只依赖 PySide6.QtCore），任何模块都能 import；
  * key 用简体中文原文，源码里写 tr("打开保存目录")，改动最小；
  * 语言偏好写进 %APPDATA%\\SnapTool\\settings.json 的 ``language`` 字段，
    与热键 / 默认模式共用同一份配置，读写都保留其它字段；
  * 切换语言发 ``LANG.changed(code)`` 信号，已打开的窗口实时刷新文本。

可选环境变量（用于自测 / 便携场景）：
  SNAPTOOL_HOME            配置目录（与 hotkeys.py 一致）
  SNAPTOOL_SYSTEM_LOCALE   模拟系统语言，例如 "ja_JP"
  SNAPTOOL_LANG            强制语言偏好，优先级高于配置文件
"""
from __future__ import annotations

import ctypes
import json
import os
import string
import sys
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, Signal

from i18n_data import LANGUAGE_NAMES, LANGS, _ROWS as ROWS

AUTO = "auto"
DEFAULT_LANG = "zh_CN"
FALLBACK_LANG = "en"          # 系统语言不在 8 种里时的通用回退
CONFIG_KEY = "language"


def config_dir() -> Path:
    override = os.environ.get("SNAPTOOL_HOME")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "SnapTool"


def config_path() -> Path:
    return config_dir() / "settings.json"


def _load_raw() -> dict:
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_raw(raw: dict) -> bool:
    """原子写入，保留热键 / 默认模式等其它配置字段。"""
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)
        return True
    except Exception:  # noqa: BLE001
        return False


def valid_code(code: str) -> bool:
    return code == AUTO or code in LANGS


def normalize(code: str) -> str:
    """把系统 QLocale 名（zh_CN / zh-Hans-CN / en-US …）映射到 8 种语言之一。"""
    if not code:
        return FALLBACK_LANG
    name = code.replace("-", "_")
    parts = name.split("_")
    lang = parts[0].lower()
    region = parts[1].upper() if len(parts) > 1 else ""
    script = parts[2].lower() if len(parts) > 2 else ""
    if lang == "zh":
        # 繁体书写的地区（含中国香港 / 中国澳门 / 中国台湾）与 Hant 字样用繁体
        if region in ("TW", "HK", "MO") or "hant" in name.lower() or script == "hant":
            return "zh_TW"
        return "zh_CN"
    for supported in ("en", "ja", "ko", "fr", "de", "es"):
        if lang == supported:
            return supported
    return FALLBACK_LANG


def windows_ui_language() -> str:
    """Windows 显示语言（用户首选 UI 语言），例如 "zh-CN" / "en-US"。

    QLocale.system() 反映的是「区域格式」而不是显示语言：中文 Windows 上把
    区域格式改成美国英语时它会返回 en_US，界面却仍是中文。因此跟随系统语言
    优先取 Win32 的 GetUserPreferredUILanguages，失败才回退 QLocale。
    """
    if sys.platform != "win32":
        return ""
    try:
        k32 = ctypes.windll.kernel32
        k32.GetUserPreferredUILanguages.argtypes = [
            wintypes.DWORD, ctypes.POINTER(wintypes.ULONG),
            wintypes.LPWSTR, ctypes.POINTER(wintypes.ULONG),
        ]
        k32.GetUserPreferredUILanguages.restype = wintypes.BOOL
        count = wintypes.ULONG(0)
        size = wintypes.ULONG(0)
        MUI_LANGUAGE_NAME = 0x8
        if not k32.GetUserPreferredUILanguages(
            MUI_LANGUAGE_NAME, ctypes.byref(count), None, ctypes.byref(size)
        ) or not size.value:
            return ""
        buf = ctypes.create_unicode_buffer(size.value)
        if not k32.GetUserPreferredUILanguages(
            MUI_LANGUAGE_NAME, ctypes.byref(count), buf, ctypes.byref(size)
        ):
            return ""
        return buf.value or ""
    except Exception:  # noqa: BLE001
        return ""


def system_language(locale_name: str | None = None) -> str:
    """当前系统语言对应的界面语言代码；未支持的语言回退 English。

    优先级：显式参数 / 环境变量（自测用） > Windows 显示语言 > Qt 区域格式。
    """
    name = locale_name or os.environ.get("SNAPTOOL_SYSTEM_LOCALE")
    if not name:
        name = windows_ui_language()
    if not name:
        try:
            name = QLocale.system().name()
        except Exception:  # noqa: BLE001
            name = ""
    return normalize(name)


def placeholders(text: str) -> set[str]:
    """取出 ``{name}`` 形式的占位符，自测据此校验 8 语言一致性。"""
    out: set[str] = set()
    for _, field, _, _ in string.Formatter().parse(text):
        if field:
            out.add(field.split(".")[0].split("[")[0])
    return out


class LanguageManager(QObject):
    """全局单例：保存偏好、解析实际语言、广播切换信号。"""

    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._preference: str = AUTO
        self._current: str = DEFAULT_LANG
        self.reload()

    # ------------------------------------------------------------ 状态
    @property
    def preference(self) -> str:
        """"auto" 或 8 个语言代码之一（用户选择，写入配置文件）。"""
        return self._preference

    @property
    def current(self) -> str:
        """实际生效的语言代码（auto 已解析成系统语言）。"""
        return self._current

    def reload(self) -> None:
        """从环境变量 / 配置文件重新读取偏好并解析（不改变信号）。"""
        pref = os.environ.get("SNAPTOOL_LANG", "").strip()
        if not valid_code(pref):
            saved = _load_raw().get(CONFIG_KEY, AUTO)
            pref = saved if isinstance(saved, str) and valid_code(saved) else AUTO
        self._preference = pref
        self._current = system_language() if pref == AUTO else pref

    def resolve(self, pref: str | None = None) -> str:
        """给定偏好（默认用当前偏好）解析出实际语言代码。"""
        p = self._preference if pref is None else pref
        return system_language() if p == AUTO else p

    def set_preference(self, code: str, persist: bool = True) -> bool:
        """切换语言：写盘 + 发信号。返回实际生效语言是否发生变化。"""
        if not valid_code(code):
            return False
        new_current = self.resolve(code)
        changed = new_current != self._current
        self._preference = code
        self._current = new_current
        if persist and not os.environ.get("SNAPTOOL_LANG"):
            raw = _load_raw()
            raw[CONFIG_KEY] = code
            _save_raw(raw)
        self.changed.emit(new_current)
        return changed

    # ------------------------------------------------------------ 翻译
    def translate(self, key: str, lang: str | None = None, **kwargs) -> str:
        code = lang or self._current
        idx = LANGS.index(code) if code in LANGS else 0
        row = ROWS.get(key)
        text = row[idx] if row and idx < len(row) and row[idx] else (row[0] if row else key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text

    def t(self, key: str, **kwargs) -> str:
        return self.translate(key, **kwargs)


LANG = LanguageManager()


def t(key: str, **kwargs) -> str:
    """翻译一条界面文案。缺失 key 时回退到简体中文原文。"""
    return LANG.t(key, **kwargs)


def app_name() -> str:
    """随语言变化的程序名（配置目录名仍固定为 SnapTool）。"""
    return t("截屏助手")


def language_choices() -> list[tuple[str, str]]:
    """设置对话框的选项：(值, 显示名)。含「跟随系统」共 9 项。"""
    sys_name = LANGUAGE_NAMES.get(system_language(), LANGUAGE_NAMES[FALLBACK_LANG])[0]
    out = [(AUTO, t("跟随系统（{name}）", name=sys_name))]
    for code in LANGS:
        native, english = LANGUAGE_NAMES[code]
        label = native if native == english else f"{native} ({english})"
        out.append((code, label))
    return out


def language_label(code: str) -> str:
    if code == AUTO:
        return t("跟随系统")
    native, english = LANGUAGE_NAMES.get(code, LANGUAGE_NAMES[DEFAULT_LANG])
    return native if native == english else f"{native} ({english})"


__all__ = [
    "AUTO", "LANGS", "LANGUAGE_NAMES", "ROWS", "LANG", "t", "app_name",
    "config_dir", "config_path", "language_choices", "language_label",
    "normalize", "placeholders", "system_language", "valid_code",
    "windows_ui_language",
]
