# -*- coding: utf-8 -*-
"""升级窗口（V53）：待激活 / 激活成功两态。

基础功能一直免费；6 项高级功能未授权时点「立即升级」弹出本窗口。
流程：复制机器码 → 购买页面下单拿激活码（或用邀请码）→ 粘贴 → 本地验签解锁。
不联网、不扣款；机器码只在打开本窗口时才采集硬件信息。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from i18n import LANG, t
from license_core import (
    activate, import_license_file, is_pro, license_status,
    machine_code,
)

# 购买页面占位，页面上线后改这里即可
BUY_URL = "https://example.com/buy"

PRO_FEATURES = (
    "滚动长截图", "OCR 取字", "旋转 / 镜像",
    "端点箭头", "透明色与填充透明度", "画布视图放缩",
)


class UpgradeDialog(QDialog):
    """授权窗口：显示机器码，接受激活码 / 邀请码 / license.dat 导入。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("升级到专业版"))
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet(
            "QDialog { background:#ffffff; }"
            "QLabel { color:#1c1c1e; }"
            "QLineEdit { border:1px solid #d9d4cc; border-radius:8px;"
            " padding:7px 10px; background:#fcfbf9; }"
            "QPushButton { border-radius:8px; padding:6px 12px; }"
            "QPushButton#gold { background:#e8a33d; color:#1c1c1e; font-weight:700;"
            " border:none; }"
            "QPushButton#gold:hover { background:#d99426; }"
            "QPushButton#dark { background:#1c1c1e; color:#ffffff; border:none; }"
            "QPushButton#dark:hover { background:#333333; }"
            "QPushButton#ghost { background:#f1efe8; color:#6b6660; border:none; }"
        )
        self._build_ui()
        LANG.changed.connect(self.retranslate_ui)
        self._refresh_state()

    def showEvent(self, event) -> None:  # noqa: N802
        """真正显示时才采集机器码（构造/自测阶段碰硬件）。"""
        super().showEvent(event)
        self._code.setText(machine_code())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel(t("升级到专业版"))
        title.setStyleSheet("font-size:16px; font-weight:700;")
        root.addWidget(title)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            "background:#f1efe8; border-radius:8px; padding:8px 10px;"
            " color:#6b6660; font-size:11px;")
        root.addWidget(self._status)

        # 1. 机器码
        root.addWidget(QLabel(t("1. 复制机器码")))
        row = QHBoxLayout()
        self._code = QLabel("")
        self._code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._code.setStyleSheet(
            "background:#fbfaf7; border:1px solid #e9e4dc; border-radius:8px;"
            " padding:7px 10px; font-family:Consolas,monospace; font-size:13px;")
        row.addWidget(self._code, 1)
        copy_b = QPushButton(t("复制"))
        copy_b.setObjectName("dark")
        copy_b.clicked.connect(self._copy_machine)
        row.addWidget(copy_b)
        root.addLayout(row)
        hint = QLabel(t("机器码只在本机生成，不联网、不上传。"))
        hint.setStyleSheet("color:#a39a90; font-size:10px;")
        root.addWidget(hint)

        # 2. 购买页面
        root.addWidget(QLabel(t("2. 打开购买页面下单")))
        buy = QPushButton(t("前往购买页面") + "  →")
        buy.setObjectName("ghost")
        buy.clicked.connect(self._open_buy)
        root.addWidget(buy)

        # 3. 激活码 / 邀请码
        root.addWidget(QLabel(t("3. 输入激活码或邀请码")))
        self._input = QLineEdit()
        self._input.setPlaceholderText(t("在这里粘贴激活码或邀请码…"))
        root.addWidget(self._input)
        row2 = QHBoxLayout()
        imp = QPushButton(t("导入 license.dat"))
        imp.setObjectName("ghost")
        imp.clicked.connect(self._import_file)
        row2.addWidget(imp)
        unlock = QPushButton(t("立即解锁"))
        unlock.setObjectName("gold")
        unlock.clicked.connect(self._unlock)
        row2.addWidget(unlock, 1)
        root.addLayout(row2)

        self._result = QLabel("")
        self._result.setWordWrap(True)
        root.addWidget(self._result)

        note = QLabel(t("永久授权 · 一机一码 · 本机重装不限次数 · 基础功能一直免费"))
        note.setStyleSheet("color:#a39a90; font-size:10px;")
        root.addWidget(note)

    def _refresh_state(self) -> None:
        pro = is_pro()
        self._status.setText(
            t("已解锁专业版 · 永久授权 · 无需联网")
            if pro else
            t("专业版未激活 · 6 项高级功能已锁定，基础功能不受影响")
        )
        self._input.setEnabled(not pro)
        for w in self.findChildren(QPushButton):
            if w.objectName() in ("gold", "ghost") and w.text() in (
                t("立即解锁"), t("导入 license.dat")):
                w.setEnabled(not pro)

    def _copy_machine(self) -> None:
        QApplication.clipboard().setText(machine_code())
        self._result.setText(t("机器码已复制"))

    def _open_buy(self) -> None:
        QDesktopServices.openUrl(QUrl(BUY_URL))

    def _import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("导入 license.dat"), "", "license.dat (*.dat);;All Files (*)")
        if not path:
            return
        ok, reason = import_license_file(path)
        self._finish(ok, reason)

    def _unlock(self) -> None:
        code = self._input.text().strip()
        if not code:
            self._result.setText(t("请先输入激活码或邀请码"))
            return
        ok, reason = activate(code)
        self._finish(ok, reason)

    def _finish(self, ok: bool, reason: str) -> None:
        if ok:
            self._result.setText(t("激活成功，专业版已解锁"))
            self._refresh_state()
            return
        msgs = {
            "machine_mismatch": t("激活码与本机机器码不匹配"),
            "invite_expired": t("邀请码已过期"),
            "invalid_code": t("激活码无效，请检查后重试"),
            "save_failed": t("保存授权失败，请检查配置目录权限"),
        }
        self._result.setText(msgs.get(reason, t("激活失败，请重试")))

    def retranslate_ui(self, _code: str = "") -> None:
        self.setWindowTitle(t("升级到专业版"))
        self._refresh_state()
