# -*- coding: utf-8 -*-
"""ui_theme.py —— 界面视觉主题（方案 E「奶油白 + 暖橙」）。

集中放三样东西，避免颜色 / 圆角 / 图标散落在各个窗口里：
  1. 配色与字号常量（与 ui-design/E-full/_style.css 一一对应）；
  2. 描边图标：按 24×24 设计稿坐标绘制，可在任意控件里按需着色；
  3. 通用控件：图标按钮、命令面板行、圆角卡片 + 投影。

只依赖 PySide6，不 import 本项目其它模块（snapeditor / snapui 都可引用）。
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# 配色（与设计稿 CSS 变量同名，方便对照）
# ---------------------------------------------------------------------------
CREAM = "#fbfaf7"        # --cream 卡片底色
INK = "#1c1c1e"          # --ink   主文字 / 深色按钮
INK2 = "#6b6660"         # --ink2  次级文字
INK3 = "#a39a90"         # --ink3  辅助文字 / 快捷键
LINE = "#e9e4dc"         # --line  分隔线 / 描边
ORANGE = "#f97316"       # --orange 强调色
SOFT = "#ffefe2"         # --osoft 选中行底色
DIM = "#2b3036"          # 遮罩外的深色底
CANVAS_BG = "#efece7"    # 编辑器画布底
HOVER = "#f5f0e8"        # 悬停底色
GREEN = "#1f8a5f"        # 「已启动」徽标文字
# v44：高级功能（PRO）金色系——与「当前选中」的暖橙刻意区分
PRO = "#e8a33d"          # 高级功能金（图标方块底 / 角标）
PRO_SOFT = "#fff4e2"     # 高级功能浅金底（整行背景）
PRO_LINE = "#f0d7a8"     # 高级功能描边

FONT_FAMILY = '"Microsoft YaHei UI","Microsoft YaHei","PingFang SC","Segoe UI",sans-serif'
FONT_QSS = f"font-family:{FONT_FAMILY};"

# 设计稿尺寸
BAR_HEIGHT = 60          # 悬浮条卡片高度
BAR_RADIUS = 20
BTN_SIZE = 40            # 悬浮条 / Dock 按钮
BTN_RADIUS = 13
PANEL_RADIUS = 20
ROW_HEIGHT = 44
ROW_RADIUS = 12


def qcolor(value: str, alpha: int | None = None) -> QColor:
    """'#rrggbb' → QColor，可附带 0~255 的透明度。"""
    c = QColor(value)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def ui_font(size: int = 9, weight: int = 400, bold: bool = False) -> QFont:
    f = QFont("Microsoft YaHei UI")
    f.setPixelSize(size)
    f.setWeight(QFont.DemiBold if bold else QFont.Normal)
    if weight:
        f.setWeight(QFont.Weight(weight) if weight > 0 else f.weight())
    return f


def apply_shadow(widget: QWidget, blur: int = 34, dy: int = 12, alpha: int = 46,
                 spread: int = 0) -> QGraphicsDropShadowEffect:
    """给控件挂一层柔和投影（设计稿的 0 18px 44px rgba(50,40,30,.18)）。"""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(50, 40, 30, alpha))
    eff.setEnabled(True)
    widget.setGraphicsEffect(eff)
    return eff


# ---------------------------------------------------------------------------
# 描边图标：24×24 设计坐标 → 任意像素尺寸
# ---------------------------------------------------------------------------
def _pen(color: QColor, width: float = 1.7) -> QPen:
    p = QPen(color)
    p.setWidthF(width)
    p.setCapStyle(Qt.RoundCap)
    p.setJoinStyle(Qt.RoundJoin)
    return p


def _camera(p: QPainter) -> None:
    path = QPainterPath(QPointF(4, 9))
    path.lineTo(4, 6)
    path.quadTo(4, 4, 6, 4)
    path.lineTo(9, 4)
    path.lineTo(11, 2)
    path.lineTo(13, 2)
    path.lineTo(15, 4)
    path.lineTo(18, 4)
    path.quadTo(20, 4, 20, 6)
    path.lineTo(20, 9)
    p.drawPath(path)
    p.drawEllipse(QPointF(12, 12.5), 3.6, 3.6)
    p.drawLine(QPointF(6, 19), QPointF(18, 19))


def _bracket_rect(p: QPainter) -> None:
    """框选：四角括号，比虚线框在小尺寸下更清楚。"""
    for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        x = 12 + sx * 8.0
        y = 12 + sy * 7.6
        p.drawLine(QPointF(x, y), QPointF(x - sx * 3.4, y))
        p.drawLine(QPointF(x, y), QPointF(x, y - sy * 3.4))


def _window(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(3, 4, 18, 16), 2.5, 2.5)
    p.drawLine(QPointF(3, 9), QPointF(21, 9))


def _fullscreen(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(2, 3, 20, 14), 2, 2)
    p.drawLine(QPointF(8, 21), QPointF(16, 21))
    p.drawLine(QPointF(12, 17), QPointF(12, 21))


def _longshot(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(6, 2, 12, 13), 2, 2)
    p.drawLine(QPointF(12, 18), QPointF(12, 21.4))
    p.drawLine(QPointF(9.2, 19), QPointF(12, 21.8))
    p.drawLine(QPointF(14.8, 19), QPointF(12, 21.8))


def _pin(p: QPainter) -> None:
    path = QPainterPath(QPointF(12, 17))
    path.lineTo(12, 22)
    p.drawPath(path)
    path = QPainterPath(QPointF(9, 3))
    path.lineTo(15, 3)
    path.lineTo(14, 9)
    path.lineTo(18, 12)
    path.lineTo(6, 12)
    path.lineTo(10, 9)
    path.closeSubpath()
    p.drawPath(path)


def _dots(p: QPainter) -> None:
    p.setBrush(p.pen().color())
    for cx in (5, 12, 19):
        p.drawEllipse(QPointF(cx, 12), 1.65, 1.65)


def _menu(p: QPainter) -> None:
    for y in (6.5, 12, 17.5):
        p.drawLine(QPointF(4, y), QPointF(20, y))


def _tray_down(p: QPainter) -> None:
    """保存：向下箭头落进托盘。"""
    p.drawLine(QPointF(12, 3), QPointF(12, 13))
    p.drawLine(QPointF(7.6, 9), QPointF(12, 13.4))
    p.drawLine(QPointF(16.4, 9), QPointF(12, 13.4))
    p.drawLine(QPointF(4, 16), QPointF(4, 19))
    p.drawLine(QPointF(4, 19), QPointF(20, 19))
    p.drawLine(QPointF(20, 19), QPointF(20, 16))


def _close(p: QPainter) -> None:
    p.drawLine(QPointF(6.5, 6.5), QPointF(17.5, 17.5))
    p.drawLine(QPointF(17.5, 6.5), QPointF(6.5, 17.5))


def _copy(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(8, 8, 12, 12), 2, 2)
    path = QPainterPath(QPointF(16, 8))
    path.lineTo(16, 5)
    path.quadTo(16, 4, 15, 4)
    path.lineTo(5, 4)
    path.quadTo(4, 4, 4, 5)
    path.lineTo(4, 15)
    path.quadTo(4, 16, 5, 16)
    path.lineTo(8, 16)
    p.drawPath(path)


def _text(p: QPainter) -> None:
    p.drawLine(QPointF(6, 5), QPointF(18, 5))
    p.drawLine(QPointF(12, 5), QPointF(12, 19))
    p.drawLine(QPointF(9.5, 19), QPointF(14.5, 19))


def _check(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 12.5))
    path.lineTo(9.6, 17)
    path.lineTo(19, 6.5)
    p.drawPath(path)


def _undo(p: QPainter) -> None:
    path = QPainterPath(QPointF(5, 18))
    path.lineTo(16, 18)
    path.quadTo(21, 18, 21, 13)
    path.quadTo(21, 8, 16, 8)
    path.lineTo(7, 8)
    p.drawPath(path)
    p.drawLine(QPointF(10.5, 4.6), QPointF(6.2, 8))
    p.drawLine(QPointF(10.5, 11.4), QPointF(6.2, 8))


def _keyboard(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(2, 6, 20, 12), 2.5, 2.5)
    for x in (6, 10, 14, 18):
        p.drawPoint(QPointF(x, 10))
    p.drawLine(QPointF(8, 14.5), QPointF(16, 14.5))


def _globe(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 9, 9)
    p.drawEllipse(QPointF(12, 12), 4.2, 9)
    p.drawLine(QPointF(3.4, 9), QPointF(20.6, 9))
    p.drawLine(QPointF(3.4, 15), QPointF(20.6, 15))


def _pen_wave(p: QPainter) -> None:
    path = QPainterPath(QPointF(3, 16))
    path.cubicTo(6, 6, 9, 20, 12, 12)
    path.cubicTo(15, 4, 18, 18, 21, 9)
    p.drawPath(path)


def _help(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 9, 9)
    path = QPainterPath(QPointF(9.4, 9.4))
    path.quadTo(9.4, 6.6, 12, 6.6)
    path.quadTo(14.6, 6.6, 14.6, 9.2)
    path.quadTo(14.6, 11, 12, 12)
    path.lineTo(12, 13.6)
    p.drawPath(path)
    p.drawPoint(QPointF(12, 17))


def _info(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 9, 9)
    p.drawLine(QPointF(12, 11), QPointF(12, 16.5))
    p.drawPoint(QPointF(12, 7.6))


def _folder(p: QPainter) -> None:
    path = QPainterPath(QPointF(3, 6))
    path.lineTo(3, 18)
    path.quadTo(3, 19.5, 4.5, 19.5)
    path.lineTo(19.5, 19.5)
    path.quadTo(21, 19.5, 21, 18)
    path.lineTo(21, 8.5)
    path.quadTo(21, 7, 19.5, 7)
    path.lineTo(11.5, 7)
    path.lineTo(9.5, 4.5)
    path.lineTo(4.5, 4.5)
    path.quadTo(3, 4.5, 3, 6)
    p.drawPath(path)


def _exit(p: QPainter) -> None:
    path = QPainterPath(QPointF(14, 4))
    path.lineTo(6, 4)
    path.quadTo(4.5, 4, 4.5, 5.5)
    path.lineTo(4.5, 18.5)
    path.quadTo(4.5, 20, 6, 20)
    path.lineTo(14, 20)
    p.drawPath(path)
    p.drawLine(QPointF(11, 12), QPointF(20, 12))
    p.drawLine(QPointF(16.6, 8.4), QPointF(20.4, 12))
    p.drawLine(QPointF(16.6, 15.6), QPointF(20.4, 12))


def _smile(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 9, 9)
    p.drawPoint(QPointF(9, 10))
    p.drawPoint(QPointF(15, 10))
    path = QPainterPath(QPointF(8.4, 14.2))
    path.quadTo(12, 17.4, 15.6, 14.2)
    p.drawPath(path)


_ICONS = {
    "logo": _camera,
    "region": _bracket_rect,
    "window": _window,
    "fullscreen": _fullscreen,
    "long": _longshot,
    "pin": _pin,
    "more": _dots,
    "menu": _menu,
    "save": _tray_down,
    "close": _close,
    "copy": _copy,
    "text": _text,
    "check": _check,
    "undo": _undo,
    "key": _keyboard,
    "globe": _globe,
    "pen": _pen_wave,
    "help": _help,
    "info": _info,
    "folder": _folder,
    "exit": _exit,
    "smile": _smile,
}


def paint_icon(p: QPainter, name: str, rect: QRectF, color: QColor,
               stroke: float = 1.7) -> None:
    """在 rect 内绘制 24 单位坐标系里的图标（居中、等比缩放）。"""
    fn = _ICONS.get(name)
    if fn is None:
        return
    side = min(rect.width(), rect.height())
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.translate(rect.center())
    p.scale(side / 24.0, side / 24.0)
    p.translate(-12, -12)
    p.setPen(_pen(color, stroke))
    p.setBrush(Qt.NoBrush)
    fn(p)
    p.restore()


_ICON_CACHE: dict[tuple[str, str, int, int], QIcon] = {}


def icon(name: str, color: str = INK2, size: int = 20, stroke: float = 1.7) -> QIcon:
    """返回缓存好的图标（按 名称+颜色+尺寸 缓存，避免每帧重绘）。"""
    key = (name, color, size, int(stroke * 10))
    hit = _ICON_CACHE.get(key)
    if hit is not None:
        return hit
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    paint_icon(p, name, QRectF(0, 0, size, size), qcolor(color), stroke)
    p.end()
    out = QIcon(pm)
    _ICON_CACHE[key] = out
    return out


def clear_icon_cache() -> None:
    _ICON_CACHE.clear()


# ---------------------------------------------------------------------------
# 通用控件
# ---------------------------------------------------------------------------
class IconButton(QPushButton):
    """自绘的图标按钮：悬停浅底、选中深底 + 橙色小圆点（设计稿 .mb / .dk）。"""

    def __init__(self, icon_name: str, toolTip: str = "", parent: QWidget | None = None,
                 size: int = BTN_SIZE, radius: int = BTN_RADIUS,
                 color: str = INK2, active_color: str = "#ffffff",
                 icon_size: int = 19, stroke: float = 1.7,
                 active_bg: str = INK) -> None:
        super().__init__(parent)
        self._name = icon_name
        self._radius = radius
        self._color = qcolor(color)
        self._active_color = qcolor(active_color)
        self._active_bg = qcolor(active_bg)
        self._icon_size = icon_size
        self._stroke = stroke
        self._dot = True
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCheckable(False)
        if toolTip:
            self.setToolTip(toolTip)
        self.setStyleSheet("background:transparent;border:none;")

    def set_icon_name(self, name: str) -> None:
        if name != self._name:
            self._name = name
            self.update()

    def set_dot(self, on: bool) -> None:
        """选中态是否画橙色小圆点（Dock 的工具按钮不需要）。"""
        self._dot = on
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        checked = self.isChecked()
        hovered = self.underMouse() and self.isEnabled()
        if checked:
            p.setPen(Qt.NoPen)
            p.setBrush(self._active_bg)
            p.drawRoundedRect(r, self._radius, self._radius)
        elif hovered:
            p.setPen(Qt.NoPen)
            p.setBrush(qcolor(HOVER))
            p.drawRoundedRect(r, self._radius, self._radius)
        color = self._active_color if checked else self._color
        if not self.isEnabled():
            color = qcolor(INK3)
        side = self._icon_size
        box = QRectF((r.width() - side) / 2, (r.height() - side) / 2 - (1 if checked else 0),
                     side, side)
        paint_icon(p, self._name, box, color, self._stroke)
        if checked and self._dot:
            p.setPen(Qt.NoPen)
            p.setBrush(qcolor(ORANGE))
            p.drawEllipse(QPointF(r.width() / 2, r.height() - 6.5), 2.0, 2.0)
        p.end()


class PillButton(QPushButton):
    """胶囊按钮：浅底（默认）/ 深底（dark）/ 橙色（orange），设计稿 .cap。"""

    STYLES = {
        "plain": (
            f"background:rgba(251,250,247,0.96);border:1px solid {LINE};color:{INK2};"
        ),
        "dark": f"background:{INK};border:1px solid {INK};color:#ffffff;font-weight:600;",
        "orange": f"background:{ORANGE};border:1px solid {ORANGE};color:#ffffff;font-weight:700;",
    }

    def __init__(self, text: str = "", icon_name: str | None = None,
                 kind: str = "plain", parent: QWidget | None = None,
                 height: int = 32) -> None:
        super().__init__(text, parent)
        self._kind = kind if kind in self.STYLES else "plain"
        self._icon_name = icon_name
        self._height = height
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(height)
        self._restyle()

    def _restyle(self) -> None:
        pad = "0 14px" if self.text() else "0 9px"
        radius = self._height // 2 + 1
        self.setStyleSheet(
            f"QPushButton{{border-radius:{radius}px;padding:{pad};font-size:12px;"
            f"{FONT_QSS}{self.STYLES[self._kind]}"
            "QPushButton:hover{filter:none;}"
            "}"
        )
        if self._icon_name:
            color = "#ffffff" if self._kind != "plain" else INK2
            self.setIcon(icon(self._icon_name, color, 15, 1.8))
            self.setIconSize(QSize(15, 15))

    def set_kind(self, kind: str) -> None:
        if kind in self.STYLES:
            self._kind = kind
            self._restyle()


class PanelRow(QPushButton):
    """命令面板里的一行：图标方块 + 标题/说明 + 右侧快捷键（设计稿 .prow）。"""

    def __init__(self, icon_name: str, title: str, desc: str = "", key: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._highlight = False
        self._pro = False            # v44：高级功能金色 PRO 标识
        self._key = key
        # 自绘不画文字，但保留按钮 text 供读屏 / 自测按文案查找
        self.setText(title)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(11)

        self._badge = QWidget(self)
        self._badge.setFixedSize(30, 30)
        self._badge.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addWidget(self._badge, 0, Qt.AlignVCenter)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self.title_label = QLabel(title, self)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.title_label.setStyleSheet(
            f"color:{INK};font-size:13px;font-weight:600;background:transparent;{FONT_QSS}"
        )
        self.desc_label = QLabel(desc, self)
        self.desc_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.desc_label.setStyleSheet(
            f"color:{INK3};font-size:10.5px;background:transparent;{FONT_QSS}"
        )
        self.desc_label.setVisible(bool(desc))
        col.addWidget(self.title_label)
        col.addWidget(self.desc_label)
        lay.addLayout(col, 1)

        self.key_label = QLabel(key, self)
        self.key_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.key_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.key_label.setStyleSheet(
            f"color:{INK3};font-size:10.5px;background:transparent;{FONT_QSS}"
        )
        self.key_label.setVisible(bool(key))
        lay.addWidget(self.key_label, 0, Qt.AlignVCenter)

    def set_texts(self, title: str, desc: str = "", key: str | None = None) -> None:
        self.setText(title)
        self.title_label.setText(title)
        self.desc_label.setText(desc)
        self.desc_label.setVisible(bool(desc))
        if key is not None:
            self._key = key
            self.key_label.setText(key)
            self.key_label.setVisible(bool(key))

    def set_icon_name(self, name: str) -> None:
        if name != self._icon_name:
            self._icon_name = name
            self.update()

    def set_highlight(self, on: bool) -> None:
        if on != self._highlight:
            self._highlight = on
            self.update()

    def set_pro(self, on: bool) -> None:
        """标为高级功能：金色浅底 + 金色图标方块 + 图标右下角金色小点。"""
        if on != self._pro:
            self._pro = on
            self.update()

    def is_pro(self) -> bool:
        return self._pro

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._highlight:
            p.setPen(Qt.NoPen)
            p.setBrush(qcolor(SOFT))
            p.drawRoundedRect(r, ROW_RADIUS, ROW_RADIUS)
        elif self._pro:
            # v44：高级功能整行浅金底（选中态仍以 SOFT 优先）
            p.setPen(QPen(qcolor(PRO_LINE), 1))
            p.setBrush(qcolor(PRO_SOFT))
            p.drawRoundedRect(r, ROW_RADIUS, ROW_RADIUS)
        elif self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(qcolor(HOVER))
            p.drawRoundedRect(r, ROW_RADIUS, ROW_RADIUS)
        # 图标方块
        g = QRectF(self._badge.geometry().adjusted(0, 0, 0, 0))
        if self._pro:
            p.setPen(QPen(qcolor(PRO), 1))
            p.setBrush(qcolor(PRO))
        else:
            p.setPen(QPen(qcolor("#ffd9bd" if self._highlight else LINE), 1))
            p.setBrush(qcolor("#ffffff"))
        p.drawRoundedRect(g.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        side = 16.0
        box = QRectF(g.center().x() - side / 2, g.center().y() - side / 2, side, side)
        paint_icon(p, self._icon_name, box,
                   qcolor(INK if self._pro else (ORANGE if self._highlight else INK2)), 1.7)
        # v44：高级功能在图标方块右下角加一枚金色小圆点（金色方块已足够醒目，
        # 不再叠 PRO 文字，避免和右侧快捷键提示重叠）
        if self._pro:
            dot = QRectF(g.right() - 4, g.bottom() - 4, 11, 11)
            p.setPen(QPen(qcolor("#ffffff"), 1.5))
            p.setBrush(qcolor(PRO))
            p.drawEllipse(dot)
        p.end()


class Card(QFrame):
    """奶油白圆角卡片（带投影）。"""

    def __init__(self, parent: QWidget | None = None, radius: int = PANEL_RADIUS,
                 bg: str = None, border: str = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._bg = qcolor(bg or CREAM, 250)
        self._border = qcolor(border or LINE)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet("background:transparent;")

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(self._border, 1))
        p.setBrush(self._bg)
        p.drawRoundedRect(r, self._radius, self._radius)
        p.end()


def hline(parent: QWidget | None = None, margin: int = 12) -> QWidget:
    """1px 分隔线（设计稿 .psep / .msep）。"""
    w = QWidget(parent)
    w.setFixedHeight(1)
    w.setStyleSheet(f"background:{LINE};")
    w.setContentsMargins(margin, 0, margin, 0)
    return w


def label(text: str, color: str = INK2, size: int = 12, bold: bool = False,
          parent: QWidget | None = None) -> QLabel:
    lb = QLabel(text, parent)
    lb.setStyleSheet(
        f"color:{color};font-size:{size}px;background:transparent;"
        f"font-weight:{600 if bold else 400};{FONT_QSS}"
    )
    return lb


def group_title(text: str, parent: QWidget | None = None) -> QLabel:
    """面板分组小标题（设计稿 .pgrp：10.5px、字距 .08em、INK3）。"""
    lb = QLabel(text, parent)
    lb.setStyleSheet(
        f"color:{INK3};font-size:10.5px;font-weight:700;letter-spacing:0.6px;"
        f"background:transparent;{FONT_QSS}"
    )
    return lb


__all__ = [
    "CREAM", "INK", "INK2", "INK3", "LINE", "ORANGE", "SOFT", "DIM", "CANVAS_BG",
    "HOVER", "GREEN", "FONT_QSS", "BAR_HEIGHT", "BAR_RADIUS", "BTN_SIZE",
    "BTN_RADIUS", "PANEL_RADIUS", "ROW_HEIGHT", "ROW_RADIUS",
    "qcolor", "ui_font", "apply_shadow", "paint_icon", "icon", "clear_icon_cache",
    "IconButton", "PillButton", "PanelRow", "Card", "hline", "label", "group_title",
]
