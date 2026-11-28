# -*- coding: utf-8 -*-
"""高级功能闸门（V53）。

6 项高级功能在各入口统一调用 require_pro()：
未授权时弹升级窗口，返回 False 让调用方直接 return。
基础功能不调用本函数，始终可用。
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from i18n import t
from license_core import is_pro

_dialog: object | None = None


def require_pro(parent: QWidget | None = None) -> bool:
    """已授权返回 True；未授权弹升级窗口并返回 False。"""
    if is_pro():
        return True
    global _dialog
    try:
        from lic_ui import UpgradeDialog
        if _dialog is None or not hasattr(_dialog, "isVisible"):
            _dialog = UpgradeDialog(parent)
        dlg = _dialog  # type: ignore[assignment]
        if not dlg.isVisible():  # type: ignore[attr-defined]
            dlg.show()  # type: ignore[attr-defined]
            dlg.raise_()  # type: ignore[attr-defined]
            dlg.activateWindow()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    return False


def pro_label() -> str:
    return t("PRO 高级功能")
