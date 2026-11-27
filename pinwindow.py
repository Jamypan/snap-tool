# -*- coding: utf-8 -*-
"""
pinwindow.py —— 「贴图钉在桌面」浮窗（v34）。

一张无边框、可置顶的图片浮窗，像便利贴一样贴在桌面上：
  · 左键拖动移动；滚轮缩放（0.1x ~ 8x）
  · 右键菜单：复制图片 / 另存为 / 透明度 / 保持置顶 / 重置大小 / 关闭
  · 双击关闭；Esc 关闭；Ctrl+C 复制原图
  · 顶栏右上角有悬停显示的关闭按钮

只依赖 PySide6 与 i18n，不 import snap.py，可单独离屏自测。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QWidget,
)

from clipboard_image import put_image as clipboard_put_image
from i18n import LANG, t

MIN_SCALE = 0.1
MAX_SCALE = 8.0
SCALE_STEP = 1.15          # 每格滚轮的缩放倍率
BORDER = 1                 # 图片外框宽度
PIN_RADIUS = 8             # 浮窗圆角（设计稿 .pin）
CLOSE_BOX = 20             # 右上角关闭按钮直径（逻辑像素）
OPACITY_STEPS = (100, 75, 50, 25)


class PinWindow(QWidget):
    """钉在桌面的图片浮窗。closed 信号在窗口关闭时发出一次。"""

    closed = Signal()

    def __init__(self, image: QImage, dpr: float = 1.0, parent=None) -> None:
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setWindowTitle(t("贴图"))

        self._base = QImage(image) if not image.isNull() else QImage(1, 1, QImage.Format_RGB32)
        self._dpr = dpr or 1.0
        self._scale = 1.0
        self._opacity_pct = 100
        self._topmost = True
        self._closed_emitted = False

        self._drag_origin: QPoint | None = None
        self._win_origin: QPoint | None = None
        self._hover = False
        self._hover_close = False
        self._menu: QMenu | None = None

        # 初始尺寸：优先 1:1 逻辑尺寸；大图收缩到屏幕的 70% 以内
        iw = max(1, int(round(self._base.width() / self._dpr)))
        ih = max(1, int(round(self._base.height() / self._dpr)))
        avail = self._available_geometry()
        max_w = max(120, int(avail.width() * 0.7))
        max_h = max(120, int(avail.height() * 0.7))
        if iw > max_w or ih > max_h:
            fit = min(max_w / iw, max_h / ih)
            self._scale = max(MIN_SCALE, fit)
        self.resize(self._total_size())

        self._place_near_cursor()
        LANG.changed.connect(self._on_language_changed)

    # ---------------------------------------------------------------- 几何
    @staticmethod
    def _available_geometry() -> QRect:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            if g.isValid() and g.width() > 0 and g.height() > 0:
                return g
        return QRect(0, 0, 1280, 720)

    def _scaled_size(self):
        from PySide6.QtCore import QSize
        return QSize(
            max(1, int(round(self._base.width() / self._dpr * self._scale))),
            max(1, int(round(self._base.height() / self._dpr * self._scale))),
        )

    def _total_size(self):
        from PySide6.QtCore import QSize
        s = self._scaled_size()
        return QSize(s.width() + BORDER * 2, s.height() + BORDER * 2)

    def _place_near_cursor(self) -> None:
        """放在鼠标附近，越界时收回屏幕内。"""
        avail = self._available_geometry()
        size = self._total_size()
        pos = QCursor.pos()
        x = pos.x() + 20
        y = pos.y() + 20
        x = min(max(x, avail.x()), max(avail.x(), avail.right() - size.width()))
        y = min(max(y, avail.y()), max(avail.y(), avail.bottom() - size.height()))
        self.move(x, y)

    def _apply_size(self, keep_center: bool = True) -> None:
        old = self.geometry()
        center = old.center() if keep_center else None
        size = self._total_size()
        if center is None:
            self.resize(size)
            return
        self.resize(size)
        self.move(center.x() - size.width() // 2, center.y() - size.height() // 2)

    # ---------------------------------------------------------------- 属性
    def image(self) -> QImage:
        return QImage(self._base)

    def set_image(self, image: QImage) -> None:
        if image.isNull():
            return
        self._base = QImage(image)
        self._scale = 1.0
        self._apply_size(keep_center=True)

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def opacity_pct(self) -> int:
        return self._opacity_pct

    @property
    def always_on_top(self) -> bool:
        return self._topmost

    def set_scale(self, scale: float, keep_center: bool = True) -> float:
        self._scale = max(MIN_SCALE, min(MAX_SCALE, float(scale)))
        self._apply_size(keep_center=keep_center)
        self.update()
        return self._scale

    def zoom(self, direction: int) -> float:
        """direction>0 放大，<0 缩小。"""
        factor = SCALE_STEP if direction > 0 else 1.0 / SCALE_STEP
        return self.set_scale(self._scale * factor)

    def reset_size(self) -> None:
        iw = max(1, int(round(self._base.width() / self._dpr)))
        ih = max(1, int(round(self._base.height() / self._dpr)))
        avail = self._available_geometry()
        fit = min(1.0, (avail.width() * 0.7) / iw, (avail.height() * 0.7) / ih)
        self.set_scale(max(MIN_SCALE, fit))

    def set_opacity(self, pct: int) -> int:
        self._opacity_pct = max(5, min(100, int(pct)))
        self.setWindowOpacity(self._opacity_pct / 100.0)
        return self._opacity_pct

    def set_always_on_top(self, on: bool) -> bool:
        self._topmost = bool(on)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._topmost)
        self.show()
        self.raise_()
        return self._topmost

    # ---------------------------------------------------------------- 动作
    def do_copy(self) -> None:
        clipboard_put_image(self._base)

    def do_save(self) -> None:
        default = Path.home() / "Pictures" / "Screenshots" / "贴图.png"
        path, _ = QFileDialog.getSaveFileName(
            self, t("保存贴图"), str(default),
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg)",
        )
        if not path:
            return
        suffix = Path(path).suffix.lower()
        fmt = "JPG" if suffix in (".jpg", ".jpeg") else "PNG"
        try:
            self._base.save(path, fmt)
        except Exception:  # noqa: BLE001
            pass

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        a_copy = menu.addAction(t("复制图片"))
        a_copy.triggered.connect(self.do_copy)
        a_save = menu.addAction(t("另存为…"))
        a_save.triggered.connect(self.do_save)
        menu.addSeparator()

        sub = menu.addMenu(t("透明度"))
        for pct in OPACITY_STEPS:
            a = sub.addAction(f"{pct}%")
            a.setCheckable(True)
            a.setChecked(pct == self._opacity_pct)
            a.triggered.connect(lambda _c=False, p=pct: self.set_opacity(p))

        a_top = menu.addAction(t("保持置顶"))
        a_top.setCheckable(True)
        a_top.setChecked(self._topmost)
        a_top.triggered.connect(lambda _c=False, v=not self._topmost: self.set_always_on_top(v))

        a_reset = menu.addAction(t("重置大小"))
        a_reset.triggered.connect(self.reset_size)
        menu.addSeparator()

        a_close = menu.addAction(t("关闭贴图"))
        a_close.triggered.connect(self.close)
        return menu

    # ---------------------------------------------------------------- 事件
    def contextMenuEvent(self, ev) -> None:  # noqa: N802
        self._menu = self._build_menu()   # 保持引用，防被回收
        self._menu.exec(ev.globalPos())

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() != Qt.LeftButton:
            return
        p = ev.position().toPoint()
        if self._close_hit(p):
            self.close()
            return
        self._drag_origin = ev.globalPosition().toPoint()
        self._win_origin = self.pos()

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        p = ev.position().toPoint()
        hit = self._close_hit(p)
        if hit != self._hover_close:
            self._hover_close = hit
            self.update()
        if self._drag_origin is not None and self._win_origin is not None:
            delta = ev.globalPosition().toPoint() - self._drag_origin
            self.move(self._win_origin + delta)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._drag_origin = None
            self._win_origin = None

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802
        self.close()

    def wheelEvent(self, ev) -> None:  # noqa: N802
        d = ev.angleDelta().y()
        if d == 0:
            return
        self.zoom(1 if d > 0 else -1)
        ev.accept()

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if ev.key() == Qt.Key_Escape:
            self.close()
        elif ev.key() == Qt.Key_C and ev.modifiers() & Qt.ControlModifier:
            self.do_copy()
        else:
            super().keyPressEvent(ev)

    def enterEvent(self, ev) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev) -> None:  # noqa: N802
        self._hover = False
        self._hover_close = False
        self.update()
        super().leaveEvent(ev)

    def _close_hit(self, p: QPoint) -> bool:
        s = self._total_size()
        return QRect(s.width() - CLOSE_BOX - BORDER, BORDER, CLOSE_BOX, CLOSE_BOX).contains(p)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, PIN_RADIUS, PIN_RADIUS)

        # 图片（圆角裁切）
        p.save()
        p.setClipPath(path)
        target = QRect(BORDER, BORDER, self.width() - BORDER * 2, self.height() - BORDER * 2)
        p.drawImage(target, self._base)
        p.restore()

        # 外框：悬停 / 取消置顶时用暖橙提示
        frame = QColor("#f97316") if (self._hover or not self._topmost) else QColor(28, 28, 30, 46)
        p.setPen(QPen(frame, BORDER))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # 缩放比例角标（设计稿 .ptag）
        if self._hover or abs(self._scale - 1.0) > 1e-3:
            text = f"{int(round(self._scale * 100))}%"
            p.setFont(QFont("Microsoft YaHei UI", 8))
            fm = p.fontMetrics()
            w = fm.horizontalAdvance(text) + 14
            h = fm.height() + 6
            box = QRectF(self.width() - w - 8, self.height() - h - 8, w, h)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(28, 28, 30, 170))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(QColor("#ffffff"))
            p.drawText(box, Qt.AlignCenter, text)

        # 关闭按钮：深色圆点 + 白叉（悬停才出现）
        if self._hover:
            r = CLOSE_BOX / 2.0
            center = QPointF(self.width() - r - 6, r + 6)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#d93025" if self._hover_close else QColor(28, 28, 30, 190)))
            p.drawEllipse(center, r, r)
            p.setPen(QPen(QColor("#ffffff"), 1.8))
            m = r * 0.42
            p.drawLine(QPointF(center.x() - m, center.y() - m),
                       QPointF(center.x() + m, center.y() + m))
            p.drawLine(QPointF(center.x() + m, center.y() - m),
                       QPointF(center.x() - m, center.y() + m))
        p.end()

    def closeEvent(self, ev) -> None:  # noqa: N802
        ev.accept()
        if not self._closed_emitted:
            self._closed_emitted = True
            self.closed.emit()

    def _on_language_changed(self, _code: str = "") -> None:
        self.setWindowTitle(t("贴图"))
        self.update()


__all__ = ["PinWindow", "MIN_SCALE", "MAX_SCALE", "OPACITY_STEPS"]
