# -*- coding: utf-8 -*-
"""
snapeditor.py —— 截图遮罩层、标注绘制、浮动工具条。

对外只暴露 Overlay：把它 show() 出来即可交互，用户完成/取消时发信号。
"""
from __future__ import annotations

import math
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, QSize, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import LANG, t

# ---------------------------------------------------------------------------
# 外观常量
# ---------------------------------------------------------------------------
DIM_ALPHA = 118              # 选区外遮罩不透明度
BORDER_COLOR = QColor(0, 174, 255)
HANDLE_SIZE = 8
HANDLE_HIT = 8
MIN_SELECT = 6               # 小于这个尺寸视为误触
ARROW_HANDLE_R = 6           # 箭头两端控制柄的绘制半径
ARROW_HANDLE_HIT = 11        # 端点命中半径（略大于绘制半径，方便点中）
ARROW_MIN_LEN = 6            # 拉伸端点时允许的最小箭头长度
DEFAULT_PEN = QColor(255, 59, 48)
PEN_WIDTH = 3
FONT_SIZE = 18
# 连续拖动时的重绘节流（毫秒）。高刷鼠标每秒可产生数百个 move 事件，
# 每次都排队重绘会让 paint 事件积压、画面追不上鼠标；节流后不积压，
# 末尾用单次定时器补画最终状态，保证松手时画面是准确的。
REPAINT_INTERVAL_MS = 10.0

# 选中矩形 / 椭圆后的四角控制柄（Overlay 与窗口编辑器共用）
SHAPE_HANDLE_R = 5           # 绘制半径（屏幕像素，不随画布放缩变化）
SHAPE_HANDLE_HIT = 11        # 命中半径（屏幕像素；Canvas 会按 view_scale 反算）
SHAPE_MIN_SIZE = 8           # 拖角缩放时允许的最小宽 / 高
SHAPE_CORNERS = ("nw", "ne", "se", "sw")

# 可旋转的标注（矩形 / 椭圆 / 文字）；线条类本身靠端点改变方向，马赛克是像素块
ROTATABLE_KINDS = ("rect", "ellipse", "text")
ROTATE_HANDLE_DIST = 26      # 旋转柄离顶边的距离（图像/逻辑坐标）
ROTATE_HANDLE_R = 6          # 旋转柄绘制半径（屏幕像素）
ROTATE_HANDLE_HIT = 12       # 旋转柄命中半径（屏幕像素）
ROTATE_SNAP_STEP = 15        # 按住 Shift 拖动时吸附的角度步长


def shape_corner_points(r: QRect) -> list[tuple[str, QPoint]]:
    """矩形四个角的 (角名, 坐标)：nw → ne → se → sw。"""
    return [
        ("nw", QPoint(r.left(), r.top())),
        ("ne", QPoint(r.right(), r.top())),
        ("se", QPoint(r.right(), r.bottom())),
        ("sw", QPoint(r.left(), r.bottom())),
    ]


def shape_hit_corner(r: QRect, pos: QPoint, hit: int = SHAPE_HANDLE_HIT) -> str:
    """命中四个角之一返回角名，否则返回空串。距离以传入坐标系为准。"""
    if not r or r.isNull():
        return ""
    best, best_d2 = "", hit * hit
    for name, pt in shape_corner_points(r):
        d = pos - pt
        d2 = d.x() * d.x() + d.y() * d.y()
        if d2 <= best_d2:
            best, best_d2 = name, d2
    return best


def shape_resize_rect(base: QRect, corner: str, pos: QPoint,
                      min_size: int = SHAPE_MIN_SIZE) -> QRect:
    """拖动 corner 角缩放矩形：对角固定、该角跟随 pos。

    允许拖过对角（自动 normalized，等于水平 / 垂直翻转）；宽高不小于
    min_size，避免图形被拖成一条线后无法再选中。base 始终是拖动开始时的
    快照，所以连续移动不会累积误差。
    """
    if corner not in SHAPE_CORNERS:
        return QRect(base)
    anchor = {
        "nw": QPoint(base.right(), base.bottom()),
        "ne": QPoint(base.left(), base.bottom()),
        "se": QPoint(base.left(), base.top()),
        "sw": QPoint(base.right(), base.top()),
    }[corner]
    x, y = pos.x(), pos.y()
    if abs(x - anchor.x()) < min_size:
        x = anchor.x() + (min_size if x >= anchor.x() else -min_size)
    if abs(y - anchor.y()) < min_size:
        y = anchor.y() + (min_size if y >= anchor.y() else -min_size)
    # 显式取 min/max，不用 QRect.normalized()：后者对负宽高会整体偏 1px，
    # 拖过对角翻转时固定角会悄悄移动。
    return QRect(
        QPoint(min(anchor.x(), x), min(anchor.y(), y)),
        QPoint(max(anchor.x(), x), max(anchor.y(), y)),
    )


def shape_corner_cursor(corner: str):
    """四角对应的斜向缩放光标；无效角返回 None。"""
    return {
        "nw": Qt.SizeFDiagCursor,
        "se": Qt.SizeFDiagCursor,
        "ne": Qt.SizeBDiagCursor,
        "sw": Qt.SizeBDiagCursor,
    }.get(corner)


def paint_shape_corner_handles(p: QPainter, pts: list[QPoint],
                               radius: int = SHAPE_HANDLE_R) -> None:
    """在画布（屏幕）坐标处画四角控制柄：白描边 + 蓝底圆点。"""
    if not pts:
        return
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QPen(QColor(255, 255, 255), 2))
    p.setBrush(QBrush(BORDER_COLOR))
    for pt in pts:
        p.drawEllipse(QRectF(pt.x() - radius, pt.y() - radius,
                             2 * radius, 2 * radius))
    p.restore()


# ---------------------------------------------------------------------------
# 形状旋转（矩形 / 椭圆 / 文字共用，Overlay 与窗口编辑器复用）
#
# 约定：形状自身的数据始终是「未旋转的局部几何」（rect / pos），angle 只影响
# 绘制与交互时的坐标变换。于是导出、拖动、四角缩放、整图变换都能在同一套
# 数据上工作，不需要把角度烘焙进坐标。
# ---------------------------------------------------------------------------
def normalize_angle(angle: float) -> float:
    """把角度收敛到 (-180, 180]，避免连续旋转后数值无限增长。"""
    a = (float(angle) + 180.0) % 360.0 - 180.0
    if a <= -180.0:            # 把 -180 显示成更自然的 180
        a += 360.0
    return 0.0 if abs(a) < 1e-6 else round(a, 3)


def shape_angle(s: Shape) -> float:
    """可旋转标注的角度；其它标注恒为 0。"""
    if s is None or s.kind not in ROTATABLE_KINDS:
        return 0.0
    return float(getattr(s, "angle", 0.0) or 0.0)


def shape_text_box(s: Shape) -> QRect:
    """文字标注的局部包围盒（与 draw_shape 的字体设置一致）。

    没有 QGuiApplication 时（例如纯数据自检 / 后台脚本）字体度量不可用，
    退回按字号估算，保证纯函数不依赖 GUI 实例也能安全调用。
    """
    if s is None or s.kind != "text" or s.pos is None:
        return QRect()
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        fs = max(1, int(s.font_size))
        tw = max(40, int(len(s.text or "") * fs * 0.62)) + 8
        th = int(fs * 1.4) + 4
        top = s.pos.y() - int(fs * 0.8) - 2
        return QRect(s.pos.x() - 4, int(top), int(tw), int(th))
    f = QFont()
    f.setPixelSize(s.font_size)
    f.setBold(s.bold)
    fm = QFontMetrics(f)
    tw = max(40, fm.horizontalAdvance(s.text or "")) + 8
    th = fm.height() + 4
    top = s.pos.y() - fm.ascent() - 2
    return QRect(s.pos.x() - 4, int(top), int(tw), int(th))


def shape_rotate_rect(s: Shape) -> QRect:
    """旋转变换所围绕的局部外接矩形；不可旋转时返回空矩形。"""
    if s is None or s.kind not in ROTATABLE_KINDS:
        return QRect()
    if s.kind == "text":
        return shape_text_box(s)
    return s.rect.normalized() if s.rect else QRect()


def shape_rotate_center(s: Shape) -> QPointF:
    """旋转中心（局部几何的中心，旋转不改变它）。"""
    r = shape_rotate_rect(s)
    return QRectF(r).center() if not r.isNull() else QPointF()


def rotation_transform_about(center: QPointF, angle: float) -> QTransform:
    """绕指定中心的旋转变换（角度为 0 时是单位变换）。"""
    tf = QTransform()
    if abs(float(angle)) < 1e-6:
        return tf
    tf.translate(center.x(), center.y())
    tf.rotate(angle)
    tf.translate(-center.x(), -center.y())
    return tf


def rotate_point_about(pt: QPointF | QPoint, center: QPointF,
                       angle: float) -> QPointF:
    return rotation_transform_about(center, angle).map(QPointF(pt))


def unrotate_point_about(pt: QPointF | QPoint, center: QPointF,
                         angle: float) -> QPointF:
    tf = rotation_transform_about(center, angle)
    if tf.isIdentity():
        return QPointF(pt)
    inv, ok = tf.inverted()
    return inv.map(QPointF(pt)) if ok else QPointF(pt)


def shape_rotation_transform(s: Shape) -> QTransform:
    """把「局部坐标」映射到「旋转后坐标」的变换。

    不可旋转 / 角度为 0 时返回单位变换；Qt 的正角度是顺时针（y 轴向下），
    与鼠标 atan2 的方向一致。
    """
    return rotation_transform_about(shape_rotate_center(s), shape_angle(s))


def shape_rotate_point(s: Shape, pt: QPointF | QPoint) -> QPoint:
    """局部点 → 旋转后的点。"""
    return rotate_point_about(pt, shape_rotate_center(s), shape_angle(s)).toPoint()


def shape_unrotate_point(s: Shape, pt: QPointF | QPoint) -> QPointF:
    """旋转后的点 → 局部点（命中检测、拖角缩放时用）。"""
    return unrotate_point_about(pt, shape_rotate_center(s), shape_angle(s))


def shape_rotated_bbox(s: Shape) -> QRect:
    """旋转后四角的外接矩形（选中高亮框用）。"""
    pts = shape_rotated_corners(s)
    if not pts:
        return QRect()
    r = QRect(pts[0], pts[0])
    for p in pts:
        r = r.united(QRect(p, p))
    return r


def shape_rotated_corners(s: Shape) -> list[QPoint]:
    """局部外接矩形四角旋转后的位置（绘制 / 命中四角柄）。"""
    r = shape_rotate_rect(s)
    if r.isNull():
        return []
    return [shape_rotate_point(s, pt) for _, pt in shape_corner_points(r)]


def shape_hit_rotated_corner(s: Shape, pos: QPoint, hit: int = SHAPE_HANDLE_HIT) -> str:
    """命中旋转后的四角之一；返回角名，未命中返回空串。"""
    if s is None or s.kind not in ("rect", "ellipse"):
        return ""
    best, best_d2 = "", float(hit) * float(hit)
    for name, pt in zip(SHAPE_CORNERS, shape_rotated_corners(s)):
        d = QPointF(pos) - QPointF(pt)
        d2 = d.x() * d.x() + d.y() * d.y()
        if d2 <= best_d2:
            best, best_d2 = name, d2
    return best


def shape_rotate_handle_point(s: Shape, dist: int = ROTATE_HANDLE_DIST) -> QPoint:
    """旋转柄位置：局部顶边中点上方 dist，再随形状一起旋转。"""
    r = shape_rotate_rect(s)
    if r.isNull():
        return QPoint()
    local = QPointF(QRectF(r).center().x(), r.top() - dist)
    return shape_rotation_transform(s).map(local).toPoint()


def shape_hit_rotate_handle(s: Shape, pos: QPoint,
                            hit: int = ROTATE_HANDLE_HIT) -> bool:
    if s is None or s.kind not in ROTATABLE_KINDS:
        return False
    h = shape_rotate_handle_point(s)
    d = QPointF(pos) - QPointF(h)
    return d.x() * d.x() + d.y() * d.y() <= float(hit) * float(hit)


def rotate_angle_from_drag(base_angle: float, center: QPointF,
                           start: QPoint, cur: QPoint,
                           snap: bool = False) -> float:
    """按鼠标绕中心的转角差计算新角度；snap=True 时吸附到 15° 整数倍。"""
    a0 = math.degrees(math.atan2(start.y() - center.y(), start.x() - center.x()))
    a1 = math.degrees(math.atan2(cur.y() - center.y(), cur.x() - center.x()))
    delta = a1 - a0
    if delta > 180.0:
        delta -= 360.0
    elif delta < -180.0:
        delta += 360.0
    angle = float(base_angle) + delta
    if snap:
        angle = round(angle / ROTATE_SNAP_STEP) * ROTATE_SNAP_STEP
    return normalize_angle(angle)


def paint_shape_rotate_handle(p: QPainter, s: Shape,
                              dist: int = ROTATE_HANDLE_DIST,
                              map_point=None) -> None:
    """画旋转柄：从顶边中点伸出一条虚线，末端是白边蓝底的圆点。

    map_point 可传入「图像坐标 → 屏幕坐标」的换算函数（窗口编辑器放缩时用），
    这样圆点半径始终是固定屏幕像素，不会被画布缩放放大。
    """
    if s is None or s.kind not in ROTATABLE_KINDS:
        return
    r = shape_rotate_rect(s)
    if r.isNull():
        return
    top = shape_rotate_point(s, QPointF(QRectF(r).center().x(), r.top()))
    h = shape_rotate_handle_point(s, dist)
    if map_point is not None:
        top, h = map_point(top), map_point(h)
    rad = ROTATE_HANDLE_R
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    ln = QPen(QColor(255, 255, 255, 210), 1)
    ln.setStyle(Qt.DashLine)
    p.setPen(ln)
    p.drawLine(QPointF(top), QPointF(h))
    p.setPen(QPen(QColor(255, 255, 255), 2))
    p.setBrush(QBrush(BORDER_COLOR))
    p.drawEllipse(QRectF(h.x() - rad, h.y() - rad, 2 * rad, 2 * rad))
    p.restore()


TOOLS = [
    ("rect", "矩形"),
    ("ellipse", "椭圆"),
    ("arrow", "箭头"),
    ("line", "直线"),
    ("pen", "画笔"),
    ("mosaic", "马赛克"),
    ("text", "文字"),
]

# 整图变换的 4 个命令按钮标签（窗口化编辑器工具栏用；截屏遮罩里隐藏，
# 因为旋转/镜像只作用于「已进入程序窗口」的整张截图）。
TRANSFORM_ACTIONS = ("顺旋", "逆旋", "左右", "上下")


# ---------------------------------------------------------------------------
# 工具栏图标（矢量绘制，避免依赖外部图片资源）
# ---------------------------------------------------------------------------
_ICON_SIZE = 26


def _icon_pen(lw: int = 2) -> QPen:
    pen = QPen(QColor(245, 247, 250))
    pen.setWidth(lw)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    return pen


def _arrow_at(p: QPainter, x: float, y: float, tx: float, ty: float,
              size: float = 6.0, wing_ratio: float = 0.62) -> None:
    """在 (x,y) 处画一个指向 (tx,ty) 方向（不必归一化）的实心小箭头。

    wing_ratio = 半宽/长度，即半张角的正切值：越小箭头越尖。
    默认 0.62（半张角约 32°）用于普通图标；旋转图标用更小的值。
    """
    import math

    n = math.hypot(tx, ty) or 1.0
    tx, ty = tx / n, ty / n
    nx, ny = -ty, tx
    bx, by = x - tx * size, y - ty * size
    w = size * wing_ratio
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(245, 247, 250)))
    p.drawPolygon(
        QPolygonF(
            [
                QPointF(x, y),
                QPointF(bx - nx * w, by - ny * w),
                QPointF(bx + nx * w, by + ny * w),
            ]
        )
    )


# 旋转图标的箭头：长而窄（半张角 atan(0.34)≈19°，旧版约 32°）
_ROT_ARROW_SIZE = 7.0
_ROT_ARROW_WING = 0.34


def _arc_arrow(p: QPainter, cx: float, cy: float, r: float,
               start_deg: float, sweep_deg: float) -> None:
    """画一段圆弧（带末端尖箭头），sweep_deg>0 顺时针、<0 逆时针（屏幕坐标）。

    圆弧末端沿弧长回退到箭头根部并改用「平头」收尾：旧版用圆头时，
    末端那个 1px 半圆会比箭头尖还突出，把尖盖成圆的。箭头本身是长窄
    三角形，底边半宽仍大于线宽，所以粗线下尖端也不会被糊掉。
    """
    import math

    sign = 1.0 if sweep_deg > 0 else -1.0
    a = math.radians(start_deg + sweep_deg)
    ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
    tx, ty = -math.sin(a) * sign, math.cos(a) * sign

    # 回退约半个箭头长的弧，让平头端面落在三角形内部（而非露在尖端外）
    back_deg = math.degrees((_ROT_ARROW_SIZE * 0.5) / r) if r > 0 else 0.0
    eff_sweep = sweep_deg - sign * back_deg
    pen = QPen(p.pen())
    pen.setCapStyle(Qt.FlatCap)
    p.setPen(pen)
    p.drawArc(int(cx - r), int(cy - r), int(2 * r), int(2 * r),
              int(start_deg * 16), int(eff_sweep * 16))

    # 尖端略前伸，保证它是整枚图标最靠前的像素，不被任何线头盖住
    tipx, tipy = ex + tx * 0.6, ey + ty * 0.6
    _arrow_at(p, tipx, tipy, tx, ty,
              size=_ROT_ARROW_SIZE, wing_ratio=_ROT_ARROW_WING)


def _draw_mirror_icon(p: QPainter) -> None:
    """画「左右镜像」基准图标：竖直虚线镜像轴 + 两侧互为镜像的实心三角。

    左三角纯白＝原图，右三角淡白＝翻过去的镜像；三角尖朝外侧、底边贴近
    轴但留 2px 缝，避免和轴线糊成一片。上下镜像直接把这张图旋转 90°，
    两者天然严格成对。
    """
    p.setPen(_icon_pen(1.5))
    p.setBrush(Qt.NoBrush)
    for a, b in ((3.0, 8.0), (11.0, 15.0), (18.0, 23.0)):
        p.drawLine(QPointF(13, a), QPointF(13, b))
    p.setPen(Qt.NoPen)
    for tip, base, alpha in ((4.0, 11.0, 255), (22.0, 15.0, 170)):
        p.setBrush(QBrush(QColor(245, 247, 250, alpha)))
        p.drawPolygon(
            QPolygonF(
                [
                    QPointF(tip, 13),
                    QPointF(base, 8),
                    QPointF(base, 18),
                ]
            )
        )


def _draw_icon(name: str, p: QPainter) -> None:
    p.setBrush(Qt.NoBrush)
    p.setPen(_icon_pen(2))
    S = _ICON_SIZE
    # ---- 绘图工具 ----
    if name == "rect":
        p.drawRect(4, 4, S - 8, S - 8)
    elif name == "ellipse":
        p.drawEllipse(QRectF(4, 4, S - 8, S - 8))
    elif name == "arrow":
        p.drawLine(5, S - 5, S - 6, 6)
        _arrow_at(p, S - 6, 6, 1.0, -1.0)
    elif name == "line":
        p.drawLine(5, S - 5, S - 6, 6)
    elif name == "pen":
        # 自由手绘笔触（波浪折线）
        pts = [(5, 18), (9, 11), (13, 16), (17, 9), (21, 13)]
        path = QPainterPath(QPointF(pts[0][0], pts[0][1]))
        for x, y in pts[1:]:
            path.lineTo(QPointF(x, y))
        p.drawPath(path)
    elif name == "mosaic":
        # 保留原来的 3×3 九宫格，只在部分格子里「不规则」填入实心方块，
        # 表达图像被打散成色块；块内缩留缝，网格线仍清晰可见。
        g = (S - 8) / 3
        p.drawRect(4, 4, S - 8, S - 8)
        p.drawLine(4 + g, 4, 4 + g, S - 4)
        p.drawLine(4 + 2 * g, 4, 4 + 2 * g, S - 4)
        p.drawLine(4, 4 + g, S - 4, 4 + g)
        p.drawLine(4, 4 + 2 * g, S - 4, 4 + 2 * g)
        p.setPen(Qt.NoPen)
        # 方块用略淡的白：与纯白网格线拉开层次，22px 下才不会糊成一整片
        p.setBrush(QBrush(QColor(245, 247, 250, 170)))
        pad = 1.0
        for r, c in ((0, 0), (0, 1), (1, 2), (2, 0), (2, 2)):
            p.drawRect(QRectF(4 + c * g + pad, 4 + r * g + pad,
                              g - 2 * pad, g - 2 * pad))
    elif name == "text":
        p.drawLine(S / 2, 4, S / 2, S - 4)
        p.drawLine(5, 4, S - 5, 4)
    # ---- 动作 ----
    elif name == "撤销":
        # 折返路径：左下起笔 → 往右 → 往上 → 往左 → 终点加箭头。
        # 用一整条 path 画，三个拐角才是圆角连接；形状与旋转的「圆环绕方块」不同。
        path = QPainterPath(QPointF(5, 20))
        path.lineTo(20, 20)      # 从左下往右
        path.lineTo(20, 8)       # 再往上
        path.lineTo(8, 8)        # 再往左
        p.drawPath(path)
        _arrow_at(p, 6, 8, -1, 0, size=6.5)
    elif name == "样式":
        p.drawEllipse(QRectF(5, 7, 15, 15))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(245, 247, 250)))
        for dx, dy in ((9, 11), (15, 11), (12, 16.5)):
            p.drawEllipse(QRectF(dx - 1.6, dy - 1.6, 3.2, 3.2))
    elif name in ("顺旋", "逆旋"):
        # 「圆环绕着图片方块」＝整图旋转 90°；中心淡白实心块是视觉主体，
        # 与「撤销」的纯线稿折线拉开差距。顺/逆起点互为 180°-θ，严格水平镜像。
        cw = name == "顺旋"
        _arc_arrow(p, S / 2, S / 2, 8,
                   40 if cw else 140, 290 if cw else -290)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(245, 247, 250, 170)))
        p.drawRect(QRectF(9, 9, 8, 8))
    elif name in ("左右", "上下"):
        # 镜像 = 沿轴翻过去：虚线轴 + 两侧一大一小同形三角（纯白原件 /
        # 淡白镜像）。上下直接把左右整张图绕画布中心转 90°，严格成对。
        p.save()
        if name == "上下":
            c = _ICON_SIZE / 2
            p.translate(c, c)
            p.rotate(90)
            p.translate(-c, -c)
        _draw_mirror_icon(p)
        p.restore()
    elif name == "长截图":
        p.drawRoundedRect(8, 3, 10, 17, 2, 2)
        p.drawLine(10, 9, 16, 9)
        p.drawLine(10, 13, 16, 13)
        p.drawLine(10, 17, 16, 17)
        _arrow_at(p, S / 2, 23, 0, 1, size=5.0)
    elif name == "取字":
        p.drawEllipse(QRectF(5, 5, 13, 13))
        p.drawLine(15, 15, 21, 21)
        p.setPen(_icon_pen(1.5))
        p.drawLine(S / 2, 7, 8, 15)
        p.drawLine(S / 2, 7, 15, 15)
        p.drawLine(8.5, 12, 14.5, 12)
    elif name == "保存":
        p.drawRect(5, 5, 16, 16)
        p.drawRect(9, 5, 8, 5)
        p.drawRect(9, 12, 8, 6)
    elif name == "复制":
        p.drawRect(6, 6, 12, 12)
        p.drawRect(11, 11, 12, 12)
    elif name == "确定":
        p.drawLine(7, 14, 11, 18)
        p.drawLine(11, 18, 19, 8)
    elif name == "✕":
        p.drawLine(7, 7, 19, 19)
        p.drawLine(19, 7, 7, 19)


_ICONS: dict[str, QIcon] = {}


def toolbar_icon(name: str) -> QIcon:
    """返回缓存的工具栏矢量图标（白色线条，适配深色按钮背景）。"""
    if name in _ICONS:
        return _ICONS[name]
    pm = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    _draw_icon(name, p)
    p.end()
    icon = QIcon(pm)
    _ICONS[name] = icon
    return icon



# ---------------------------------------------------------------------------
@dataclass
class Shape:
    """一条标注。用 kind 区分，未用到的字段留空。

    所有标注都支持：color（线条色/文字色）、width（粗细）、line_style（线型）。
    封闭图形（rect/ellipse/mosaic）的边框用 color，额外支持 fill_color（填充色）。
    文字额外支持 font_size、bg_color（背景色，带 alpha 可调透明度）；
    背景框还能描边：bg_border / bg_border_color / bg_border_width /
    bg_border_style，边框色可设为全透明（等于不描边）。
    画笔（pen）额外支持 pen_arrow_start / pen_arrow_end：在路径起点 / 终点画箭头。
    矩形 / 椭圆 / 文字额外支持 angle：绕自身中心的旋转角度（度，顺时针为正）。
    """

    kind: str
    color: QColor = field(default_factory=lambda: QColor(DEFAULT_PEN))
    width: int = PEN_WIDTH
    line_style: str = "solid"                 # solid | dash | dot
    rect: QRect | None = None                 # rect / ellipse / mosaic
    start: QPoint | None = None               # arrow
    end: QPoint | None = None                 # arrow
    points: list[QPoint] = field(default_factory=list)   # pen
    text: str = ""                            # text
    pos: QPoint | None = None                 # text
    font_size: int = FONT_SIZE
    bold: bool = False                        # text 加粗
    bg_color: QColor | None = None            # text 背景色（None=透明背景，alpha 可调）
    bg_border: bool = False                   # text 背景框是否描边
    bg_border_color: QColor | None = field(   # text 背景框边框色（alpha=0 = 透明）
        default_factory=lambda: QColor("#ff000000"))
    bg_border_width: int = 2                  # text 背景框边框线宽
    bg_border_style: str = "solid"            # text 背景框边框线型 solid/dash/dot
    fill_color: QColor | None = None          # 封闭图形填充色（None=不填充）
    pen_arrow_start: bool = False             # pen 路径起点箭头
    pen_arrow_end: bool = False               # pen 路径终点箭头
    angle: float = 0.0                        # rect / ellipse / text 绕中心旋转（度）


def _pixelated(src: QImage, block: int = 12) -> QImage:
    """把图片按 block 像素块做马赛克。"""
    w, h = src.width(), src.height()
    if w < 2 or h < 2:
        return src
    bw, bh = max(1, w // block), max(1, h // block)
    small = src.scaled(bw, bh, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)


LINE_STYLES = {
    "solid": Qt.SolidLine,
    "dash": Qt.DashLine,
    "dot": Qt.DotLine,
}


def _make_pen(s: Shape) -> QPen:
    """根据标注的线型/颜色/粗细生成画笔。"""
    pen = QPen(s.color)
    pen.setWidth(s.width)
    pen.setJoinStyle(Qt.RoundJoin)
    pen.setCapStyle(Qt.RoundCap)
    pen.setStyle(LINE_STYLES.get(s.line_style, Qt.SolidLine))
    return pen


def _unit_dir(a: QPoint, b: QPoint, fallback=(0.0, -1.0)) -> tuple[float, float]:
    """从 a 指向 b 的单位方向向量；两点重合时退回默认方向。"""
    import math

    dx, dy = b.x() - a.x(), b.y() - a.y()
    n = math.hypot(dx, dy)
    if n < 1:
        return fallback
    return dx / n, dy / n


def _path_arclengths(points) -> list[float]:
    """累计弧长表：cum[i] = points[0] 沿路径到 points[i] 的长度。"""
    import math

    cum = [0.0]
    for i in range(1, len(points)):
        cum.append(cum[-1] + math.hypot(
            points[i].x() - points[i - 1].x(),
            points[i].y() - points[i - 1].y(),
        ))
    return cum


def _point_at_arclen(points, cum, s: float) -> QPointF:
    """按累计弧长 s 在折线路径上取点（段内线性插值），s 会夹到 [0, 总长]。"""
    import bisect

    total = cum[-1]
    s = max(0.0, min(float(s), total))
    # bisect_right 能在有重复点（cum 值相同）时跳到最后一个可用段
    i = bisect.bisect_right(cum, s) - 1
    i = max(0, min(i, len(points) - 2))
    seg = cum[i + 1] - cum[i]
    if seg <= 1e-9:
        return QPointF(points[i + 1])
    t = (s - cum[i]) / seg
    a, b = points[i], points[i + 1]
    return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)


def _pen_tangent(points, cum, at_start: bool, span: float) -> tuple[float, float]:
    """曲线端点处「朝端点外侧」的稳定切线方向（单位向量）。

    不能只用最后两个采样点算方向：鼠标采样很密时相邻两点常常只差 1~2px
    甚至完全重合，算出来的方向会剧烈抖动，或者退化成写死的水平方向，
    看上去就是「箭头方向和曲线走向对不上」。这里沿路径回溯 span 弧长取
    一个参考点，用「参考点 → 端点」的方向，反映端点附近这一小段的走势。
    """
    total = cum[-1]
    if total <= 0:
        return (-1.0, 0.0) if at_start else (1.0, 0.0)
    L = min(span, total * 0.5)
    s = L if at_start else total - L
    ref = _point_at_arclen(points, cum, s)
    tip = points[0] if at_start else points[-1]
    return _unit_dir(ref, tip, (-1.0, 0.0) if at_start else (1.0, 0.0))


def _arrow_head(p: QPainter, tipx: float, tipy: float, ux: float, uy: float,
                color: QColor, width: int, head_override: float | None = None) -> None:
    """在 (tipx,tipy) 处画一个指向 (ux,uy) 方向的实心箭头。

    大小随线宽合理缩放（head≈线宽×3，并设下限），半张角固定约 22.8°，
    且底边不小于线宽，保证粗线时依然尖锐、不露圆头。head_override 用于
    极短线段时按已收缩后的长度绘制，避免箭头盖住整条线。
    """
    head = head_override if head_override is not None else max(12.0, width * 3.0)
    wing = max(head * 0.42, width * 0.62)
    t = QPointF(tipx, tipy)
    bx, by = tipx - ux * head, tipy - uy * head
    lx, ly = bx - uy * wing, by + ux * wing
    rx, ry = bx + uy * wing, by - ux * wing
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(color))
    p.drawPolygon(QPolygonF([t, QPointF(lx, ly), QPointF(rx, ry)]))


def _stroke_seg(p, ax, ay, bx, by, color, width, line_style, cap) -> None:
    lp = QPen(color)
    lp.setWidth(width)
    lp.setJoinStyle(Qt.RoundJoin)
    lp.setCapStyle(cap)
    lp.setStyle(LINE_STYLES.get(line_style, Qt.SolidLine))
    p.setPen(lp)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(ax, ay), QPointF(bx, by))


def _draw_line_arrows(p, a, b, color, width, line_style, with_start, with_end) -> None:
    """画一条带（可选）两端箭头的直线段。

    线在箭头根部截断并改用平头（FlatCap），让箭头始终尖锐；箭头方向沿线段
    指向两个端点（起点箭头朝外、终点箭头朝外）。两端箭头过长时按比例收缩，
    避免交叉。
    """
    import math

    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy)
    ux, uy = 0.0, 0.0
    if length >= 1:
        ux, uy = dx / length, dy / length
    head = max(12.0, width * 3.0)
    max_total = length * 0.8
    total = (head if with_start else 0) + (head if with_end else 0)
    scale = (max_total / total) if (total > max_total and total > 0) else 1.0
    hs = head * scale if with_start else 0.0
    he = head * scale if with_end else 0.0
    ax, ay = a.x() + ux * hs, a.y() + uy * hs
    bx, by = b.x() - ux * he, b.y() - uy * he
    _stroke_seg(p, ax, ay, bx, by, color, width, line_style, Qt.FlatCap)
    if with_end:
        _arrow_head(p, b.x(), b.y(), ux, uy, color, width, head * scale)
    if with_start:
        _arrow_head(p, a.x(), a.y(), -ux, -uy, color, width, head * scale)


def _draw_pen_arrows(p, points, color, width, line_style, with_start, with_end) -> None:
    """画画笔路径，并在两端（可选）加箭头。

    箭头方向取端点附近一小段弧长的「稳定切线」，不用最后两个采样点：鼠标
    采样很密时那一段可能只有 1~2px 甚至重合，方向会乱转，看起来与曲线
    走向不一致。线也沿同一方向截断到箭头根部并改用平头，保证粗线时箭头
    依然尖锐、且线不会在箭头根部突然拐一下。无箭头时保持圆头自由笔触。
    """
    n = len(points)
    if n == 1:
        p.setPen(QPen(color))
        p.setBrush(Qt.NoBrush)
        p.drawPoint(QPointF(points[0]))
        return
    if n < 2:
        return

    cum = _path_arclengths(points)
    total = cum[-1]
    if total < 1:
        # 采样点几乎重合，没形成线：只画点，别画出乱指的箭头
        p.setPen(QPen(color))
        p.setBrush(Qt.NoBrush)
        p.drawPoint(QPointF(points[0]))
        return

    need_trim = with_start or with_end
    head = max(12.0, width * 3.0)
    # 两端箭头加起来不超过路径的 80%，极短曲线时按比例收缩
    max_total = total * 0.8
    raw = (head if with_start else 0.0) + (head if with_end else 0.0)
    scale = (max_total / raw) if (raw > max_total and raw > 0) else 1.0
    hs = head * scale if with_start else 0.0
    he = head * scale if with_end else 0.0

    # 回溯约一个箭头长度（路径很短时最多取一半），得到端点处的稳定切线
    span = min(max(head, 12.0), total * 0.5)
    us = _pen_tangent(points, cum, True, span) if with_start else None
    ue = _pen_tangent(points, cum, False, span) if with_end else None

    # 截断端点 = 端点沿「朝外方向」回退箭头长度，正好落在箭头底边中心
    s0 = (QPointF(points[0].x() - us[0] * hs, points[0].y() - us[1] * hs)
          if with_start else QPointF(points[0]))
    e0 = (QPointF(points[-1].x() - ue[0] * he, points[-1].y() - ue[1] * he)
          if with_end else QPointF(points[-1]))

    lp = QPen(color)
    lp.setWidth(width)
    lp.setJoinStyle(Qt.RoundJoin)
    lp.setStyle(LINE_STYLES.get(line_style, Qt.SolidLine))
    lp.setCapStyle(Qt.FlatCap if need_trim else Qt.RoundCap)
    path = QPainterPath(s0)
    # 只保留落在两个截断点之间的原始采样点；被裁掉的尾部不再画，
    # 避免「最后一段很短、却要从它硬连到截断点」造成方向突然折一下
    lo = hs if with_start else 0.0
    hi = (total - he) if with_end else total
    for i in range(1, n - 1):
        if lo < cum[i] < hi:
            path.lineTo(QPointF(points[i]))
    path.lineTo(e0)
    p.setPen(lp)
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)

    if with_end:
        _arrow_head(p, points[-1].x(), points[-1].y(), ue[0], ue[1],
                    color, width, head * scale)
    if with_start:
        _arrow_head(p, points[0].x(), points[0].y(), us[0], us[1],
                    color, width, head * scale)


def draw_shape(p: QPainter, s: Shape, base_image: QImage, dpr: float) -> None:
    """
    在已设置好坐标变换的 painter 上绘制一条标注。

    矩形 / 椭圆 / 文字若带 angle，会先叠一层「绕自身中心旋转」的变换；
    数据本身仍是未旋转的局部几何，导出与交互因此可以共用同一份坐标。
    base_image 为物理像素的原图，供马赛克取样；dpr 用于逻辑↔物理换算。
    """
    tf = shape_rotation_transform(s)
    if tf.isIdentity():
        _draw_shape_raw(p, s, base_image, dpr)
        return
    p.save()
    p.setTransform(tf, True)
    # Qt6 的 drawText(QPoint, str) 在带旋转的 world transform 下会把基线
    # 额外平移（实测约 2×ascent），导致旋转文字偏离 shape_text_box() 的
    # 中心；转成字形路径后填充可严格按变换映射。矩形 / 椭圆不受影响。
    _draw_shape_raw(p, s, base_image, dpr, rotated_text=True)
    p.restore()


def _draw_shape_raw(p: QPainter, s: Shape, base_image: QImage, dpr: float,
                    rotated_text: bool = False) -> None:
    """在局部（未旋转）坐标系里绘制一条标注。

    rotated_text=True 时文字改用 QPainterPath 绘制，用于旋转变换下的
    精确对位；未旋转时仍走 drawText()，保持原有字形与基线一致。
    """
    pen = _make_pen(s)

    if s.kind in ("rect", "ellipse"):
        if not s.rect:
            return
        bpen = QPen(s.color)
        bpen.setWidth(s.width)
        bpen.setJoinStyle(Qt.RoundJoin)
        bpen.setStyle(LINE_STYLES.get(s.line_style, Qt.SolidLine))
        p.setPen(bpen)
        if s.fill_color is not None and s.fill_color.alpha() > 0:
            p.setBrush(QBrush(s.fill_color))
        else:
            p.setBrush(Qt.NoBrush)
        if s.kind == "rect":
            p.drawRect(s.rect)
        else:
            p.drawEllipse(s.rect)

    elif s.kind == "arrow":
        if not s.start or not s.end:
            return
        # 箭头工具：固定终点带箭头，方向从起点指向终点
        _draw_line_arrows(p, s.start, s.end, s.color, s.width, s.line_style, False, True)

    elif s.kind == "line":
        if not s.start or not s.end:
            return
        # 直线工具：两端箭头可在样式面板里分别开关
        _draw_line_arrows(
            p, s.start, s.end, s.color, s.width, s.line_style,
            bool(getattr(s, "pen_arrow_start", False)),
            bool(getattr(s, "pen_arrow_end", False)),
        )

    elif s.kind == "pen":
        if not s.points:
            return
        _draw_pen_arrows(
            p, s.points, s.color, s.width, s.line_style,
            bool(getattr(s, "pen_arrow_start", False)),
            bool(getattr(s, "pen_arrow_end", False)),
        )

    elif s.kind == "mosaic":
        if not s.rect or s.rect.width() < 2 or s.rect.height() < 2:
            return
        phys = QRect(
            int(round(s.rect.x() * dpr)),
            int(round(s.rect.y() * dpr)),
            max(1, int(round(s.rect.width() * dpr))),
            max(1, int(round(s.rect.height() * dpr))),
        )
        phys = phys.intersected(QRect(0, 0, base_image.width(), base_image.height()))
        if phys.isEmpty():
            return
        # 像素化结果按矩形缓存：原图在一次截图会话内不变，只有拖动改变矩形时
        # 才需要重算，避免每帧都对整块做两次缩放。
        key = (phys.x(), phys.y(), phys.width(), phys.height())
        cached = getattr(s, "_mosaic_cache", None)
        if cached is None or cached[0] != key:
            cached = (key, _pixelated(base_image.copy(phys)))
            s._mosaic_cache = cached
        p.drawImage(QRectF(s.rect), cached[1])

    elif s.kind == "text":
        if not s.pos or not s.text:
            return
        font = QFont()
        font.setPixelSize(s.font_size)
        font.setBold(s.bold)
        p.setFont(font)
        # 背景框用 shape_text_box() 计算，和旋转中心 / 命中框 / 旋转柄共用
        # 同一份几何；不能在这里用 p.fontMetrics()，带旋转变换时它会与
        # 局部坐标下的包围盒不一致。
        box = shape_text_box(s)
        want_bg = s.bg_color is not None and s.bg_color.alpha() > 0
        bc = getattr(s, "bg_border_color", None)
        want_border = (
            bool(getattr(s, "bg_border", False))
            and isinstance(bc, QColor) and bc.alpha() > 0
        )
        if not box.isNull() and (want_bg or want_border):
            if want_bg:
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(s.bg_color))
                p.drawRoundedRect(box, 3, 3)
            if want_border:
                bpen = QPen(bc)
                bpen.setWidth(max(1, int(getattr(s, "bg_border_width", 2))))
                bpen.setJoinStyle(Qt.RoundJoin)
                bpen.setStyle(LINE_STYLES.get(
                    getattr(s, "bg_border_style", "solid"), Qt.SolidLine))
                p.setPen(bpen)
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(box, 3, 3)
        if rotated_text:
            path = QPainterPath()
            path.addText(QPointF(s.pos), font, s.text)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(pen.color()))
            p.drawPath(path)
        else:
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawText(s.pos, s.text)


# ---------------------------------------------------------------------------
# 预设颜色
# ---------------------------------------------------------------------------
PRESET_COLORS = [
    "#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#00c7be",
    "#0a84ff", "#5856d6", "#af52de", "#ff2d55", "#ffffff",
    "#8e8e93", "#000000",
]


def _text_edit_color(c: QColor) -> str:
    """文字输入框的前景色：透明线条不能让正在输入的字也看不见。"""
    return c.name(QColor.HexRgb) if isinstance(c, QColor) and c.alpha() > 0 else "#ffffff"


class StylePanel(QWidget):
    """浮动样式面板。

    根据「当前选中标注的类型」动态显示相关控件：
      - 所有标注：颜色、线宽、线型
      - 封闭图形（rect/ellipse）：额外有填充色 + 填充透明度滑块
      - 文字（text）：额外有字号、背景色 + 背景透明度滑块、背景边框
        （启用开关、边框颜色含 ∅ 透明、独立线宽与线型）

    参数修改后实时通过 style_changed 信号通知宿主，宿主据此更新选中标注。
    """

    style_changed = Signal(dict)   # 携带 {key: value} 增量

    def __init__(self, parent: QWidget | None = None, show_pen_arrows: bool = False) -> None:
        # 作为 Overlay 的普通子控件（与 Toolbar 一致），确保稳定显示在遮罩上方。
        # 画笔端点箭头只有窗口化编辑器支持（遮罩现在不做标注），按需显示。
        super().__init__(parent)
        self._show_pen_arrows = show_pen_arrows
        self._fill_rgb = "#0a84ff"       # 填充色 RGB（alpha 由滑块单独控制）
        self._bg_rgb = "#000000"         # 文字背景色 RGB（alpha 由独立滑块控制）
        self._bg_border_rgb = "#000000"  # 文字背景边框色 RGB（默认不透明）
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        # 面板内默认用常规箭头光标（避免继承遮罩的十字光标），
        # 颜色块等按钮单独设为手型。
        self.setCursor(Qt.ArrowCursor)

        from PySide6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QPushButton,
            QSlider,
            QVBoxLayout,
            QCheckBox,
            QComboBox,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # --- 线条颜色（所有标注通用）---
        self._line_key = "颜色"
        self._line_label = QLabel(t("颜色"))
        root.addWidget(self._line_label)
        self._color_grid = QHBoxLayout()
        self._color_grid.setSpacing(4)
        self._color_btns: list[QPushButton] = []
        for c in PRESET_COLORS:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setProperty("color", c)
            b.setStyleSheet(
                f"background:{c}; border:1px solid #555; border-radius:4px;"
            )
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, col=c: self._emit("color", col))
            self._color_grid.addWidget(b)
            self._color_btns.append(b)
        # 透明线条：#AARRGGBB 中 alpha=0，画出来即无边框 / 无线条
        self._transparent_btn = QPushButton("\u2205")
        self._transparent_btn.setFixedSize(22, 22)
        self._transparent_btn.setProperty("color", "#00000000")
        self._transparent_btn.setToolTip(t("透明（无边框）"))
        self._transparent_btn.setCursor(Qt.PointingHandCursor)
        self._transparent_btn.setFocusPolicy(Qt.NoFocus)
        self._transparent_btn.clicked.connect(
            lambda _=False: self._emit("color", "#00000000")
        )
        self._color_grid.addWidget(self._transparent_btn)
        root.addLayout(self._color_grid)

        self._custom_btn = QPushButton(t("自定义颜色…"))
        self._custom_btn.setCursor(Qt.PointingHandCursor)
        self._custom_btn.setFocusPolicy(Qt.NoFocus)
        self._custom_btn.clicked.connect(self._pick_custom)
        root.addWidget(self._custom_btn)

        # --- 线宽（所有标注通用）---
        self._width_label = QLabel(t("线宽"))
        root.addWidget(self._width_label)
        self._width_slider = QSlider(Qt.Horizontal)
        self._width_slider.setRange(1, 20)
        self._width_slider.setValue(PEN_WIDTH)
        self._width_slider.setFocusPolicy(Qt.NoFocus)
        self._width_slider.valueChanged.connect(
            lambda v: self._emit("width", int(v))
        )
        root.addWidget(self._width_slider)

        # --- 线型（所有标注通用）---
        self._line_style_keys = (("solid", "实线"), ("dash", "虚线"), ("dot", "点线"))
        self._line_style_label = QLabel(t("线型"))
        root.addWidget(self._line_style_label)
        self._line_style_combo = QComboBox()
        self._line_style_combo.setFocusPolicy(Qt.NoFocus)
        for key, name in self._line_style_keys:
            self._line_style_combo.addItem(t(name), key)
        self._line_style_combo.currentIndexChanged.connect(
            lambda i: self._emit(
                "line_style", self._line_style_combo.itemData(i)
            )
        )
        root.addWidget(self._line_style_combo)

        # --- 填充色（封闭图形）---
        self._fill_label = QLabel(t("填充色"))
        root.addWidget(self._fill_label)
        self._fill_row = QHBoxLayout()
        self._fill_check = QCheckBox(t("启用"))
        self._fill_check.setFocusPolicy(Qt.NoFocus)
        self._fill_check.toggled.connect(self._on_fill_toggle)
        self._fill_row.addWidget(self._fill_check)
        root.addLayout(self._fill_row)
        self._fill_grid = QHBoxLayout()
        self._fill_grid.setSpacing(4)
        self._fill_btns = self._make_preset_color_buttons("fill_color")
        for b in self._fill_btns:
            self._fill_grid.addWidget(b)
        root.addLayout(self._fill_grid)
        self._fill_alpha_label = QLabel(t("填充透明度"))
        root.addWidget(self._fill_alpha_label)
        self._fill_alpha_slider = QSlider(Qt.Horizontal)
        self._fill_alpha_slider.setRange(0, 100)
        self._fill_alpha_slider.setValue(50)       # 先设值再连信号，避免构造期误 emit
        self._fill_alpha_slider.setFocusPolicy(Qt.NoFocus)
        self._fill_alpha_slider.setEnabled(False)  # 未启用填充时置灰
        self._fill_alpha_slider.valueChanged.connect(self._on_fill_alpha)
        root.addWidget(self._fill_alpha_slider)

        # --- 字号（文字）---
        self._size_label = QLabel(t("字号"))
        root.addWidget(self._size_label)
        self._size_slider = QSlider(Qt.Horizontal)
        self._size_slider.setRange(10, 72)
        self._size_slider.setValue(FONT_SIZE)
        self._size_slider.setFocusPolicy(Qt.NoFocus)
        self._size_slider.valueChanged.connect(
            lambda v: self._emit("font_size", int(v))
        )
        root.addWidget(self._size_slider)

        # --- 加粗（文字）---
        self._bold_check = QCheckBox(t("加粗"))
        self._bold_check.setFocusPolicy(Qt.NoFocus)
        self._bold_check.toggled.connect(lambda on: self._emit("bold", on))
        root.addWidget(self._bold_check)

        # --- 旋转角度（矩形 / 椭圆 / 文字）---
        self._angle_label = QLabel(t("旋转角度"))
        root.addWidget(self._angle_label)
        self._angle_box = QWidget()
        angle_row = QHBoxLayout(self._angle_box)
        angle_row.setContentsMargins(0, 0, 0, 0)
        angle_row.setSpacing(6)
        self._angle_slider = QSlider(Qt.Horizontal)
        self._angle_slider.setRange(-180, 180)
        self._angle_slider.setValue(0)
        self._angle_slider.setFocusPolicy(Qt.NoFocus)
        self._angle_slider.valueChanged.connect(self._on_angle_changed)
        angle_row.addWidget(self._angle_slider)
        self._angle_value = QLabel("0°")
        self._angle_value.setFixedWidth(38)
        angle_row.addWidget(self._angle_value)
        root.addWidget(self._angle_box)

        # --- 文字背景色（文字）---
        # 与封闭图形的「填充色」用同一套交互：预设色块 + 独立透明度滑块，
        # 两者的颜色 / 透明度各自记忆，互不影响。
        self._bg_label = QLabel(t("文字背景色"))
        root.addWidget(self._bg_label)
        self._bg_row = QHBoxLayout()
        self._bg_check = QCheckBox(t("启用"))
        self._bg_check.setFocusPolicy(Qt.NoFocus)
        self._bg_check.toggled.connect(self._on_bg_toggle)
        self._bg_row.addWidget(self._bg_check)
        root.addLayout(self._bg_row)
        self._bg_grid = QHBoxLayout()
        self._bg_grid.setSpacing(4)
        self._bg_btns = self._make_preset_color_buttons("bg_color")
        for b in self._bg_btns:
            self._bg_grid.addWidget(b)
        root.addLayout(self._bg_grid)
        self._bg_alpha_label = QLabel(t("背景透明度"))
        root.addWidget(self._bg_alpha_label)
        self._bg_alpha_slider = QSlider(Qt.Horizontal)
        self._bg_alpha_slider.setRange(0, 100)
        self._bg_alpha_slider.setValue(50)
        self._bg_alpha_slider.setFocusPolicy(Qt.NoFocus)
        self._bg_alpha_slider.setEnabled(False)
        self._bg_alpha_slider.valueChanged.connect(self._on_bg_alpha)
        root.addWidget(self._bg_alpha_slider)

        # --- 文字背景边框（文字）---
        self._bg_border_label = QLabel(t("文字背景边框"))
        root.addWidget(self._bg_border_label)
        self._bg_border_check = QCheckBox(t("启用边框"))
        self._bg_border_check.setFocusPolicy(Qt.NoFocus)
        self._bg_border_check.toggled.connect(self._on_bg_border_toggle)
        root.addWidget(self._bg_border_check)
        self._bg_border_color_label = QLabel(t("边框颜色"))
        root.addWidget(self._bg_border_color_label)
        self._bg_border_grid = QHBoxLayout()
        self._bg_border_grid.setSpacing(4)
        self._bg_border_btns = self._make_preset_color_buttons("bg_border_color")
        for b in self._bg_border_btns:
            self._bg_border_grid.addWidget(b)
        # 边框色专属「∅ 透明」：与顶部文字颜色的透明按钮互不干扰
        self._bg_border_transparent_btn = QPushButton("\u2205")
        self._bg_border_transparent_btn.setFixedSize(22, 22)
        self._bg_border_transparent_btn.setProperty("color", "#00000000")
        self._bg_border_transparent_btn.setToolTip(t("透明（无边框）"))
        self._bg_border_transparent_btn.setCursor(Qt.PointingHandCursor)
        self._bg_border_transparent_btn.setFocusPolicy(Qt.NoFocus)
        self._bg_border_transparent_btn.clicked.connect(
            lambda _=False: self._emit("bg_border_color", "#00000000")
        )
        self._bg_border_grid.addWidget(self._bg_border_transparent_btn)
        root.addLayout(self._bg_border_grid)
        self._bg_border_width_label = QLabel(t("边框线宽"))
        root.addWidget(self._bg_border_width_label)
        self._bg_border_width_slider = QSlider(Qt.Horizontal)
        self._bg_border_width_slider.setRange(1, 20)
        self._bg_border_width_slider.setValue(2)
        self._bg_border_width_slider.setFocusPolicy(Qt.NoFocus)
        self._bg_border_width_slider.valueChanged.connect(
            lambda v: self._emit("bg_border_width", int(v))
        )
        root.addWidget(self._bg_border_width_slider)
        self._bg_border_style_label = QLabel(t("边框线型"))
        root.addWidget(self._bg_border_style_label)
        self._bg_border_style_combo = QComboBox()
        self._bg_border_style_combo.setFocusPolicy(Qt.NoFocus)
        for key, name in self._line_style_keys:
            self._bg_border_style_combo.addItem(t(name), key)
        self._bg_border_style_combo.currentIndexChanged.connect(
            lambda i: self._emit(
                "bg_border_style", self._bg_border_style_combo.itemData(i)
            )
        )
        root.addWidget(self._bg_border_style_combo)

        # --- 端点箭头（画笔 / 直线：选中时改当前线条；无选中时设新建默认）---
        self._pen_arrow_label = QLabel(t("端点箭头"))
        root.addWidget(self._pen_arrow_label)
        self._pen_arrow_start = QCheckBox(t("起点加箭头"))
        self._pen_arrow_start.setFocusPolicy(Qt.NoFocus)
        self._pen_arrow_start.toggled.connect(
            lambda on: self._emit("pen_arrow_start", on)
        )
        root.addWidget(self._pen_arrow_start)
        self._pen_arrow_end = QCheckBox(t("终点加箭头"))
        self._pen_arrow_end.setFocusPolicy(Qt.NoFocus)
        self._pen_arrow_end.toggled.connect(
            lambda on: self._emit("pen_arrow_end", on)
        )
        root.addWidget(self._pen_arrow_end)

        # 按类型收集控件组，方便按需显隐
        self._shape_only = [
            self._fill_label, self._fill_check,
            self._fill_alpha_label, self._fill_alpha_slider,
        ] + self._fill_btns
        self._text_only = [
            self._size_label, self._size_slider,
            self._bold_check,
            self._bg_label, self._bg_check,
            self._bg_alpha_label, self._bg_alpha_slider,
            self._bg_border_label, self._bg_border_check,
            self._bg_border_color_label,
            self._bg_border_width_label, self._bg_border_width_slider,
            self._bg_border_style_label, self._bg_border_style_combo,
        ] + self._bg_btns + self._bg_border_btns + [self._bg_border_transparent_btn]
        # 边框未启用时收起细节控件（仍要服从 _text_only 的整体显隐）
        self._bg_border_detail = [
            self._bg_border_color_label,
            self._bg_border_width_label, self._bg_border_width_slider,
            self._bg_border_style_label, self._bg_border_style_combo,
        ] + self._bg_border_btns + [self._bg_border_transparent_btn]
        # 线宽/线型对文字无意义，仅在非文字时显示
        self._non_text = [
            self._width_label, self._width_slider,
            self._line_style_label, self._line_style_combo,
        ]
        self._pen_only = [
            self._pen_arrow_label,
            self._pen_arrow_start,
            self._pen_arrow_end,
        ]
        # 只有矩形 / 椭圆 / 文字能绕自身中心旋转
        self._rotatable_only = [
            self._angle_label, self._angle_box,
        ]

        # 初始隐藏填充/背景色块（勾选「启用」后才显示）
        for b in self._fill_btns + self._bg_btns:
            b.setVisible(False)

        self.setStyleSheet(
            """
            QWidget { background:#2b2b2b; border-radius:8px; }
            QLabel { color:#e8e8e8; font-size:12px; }
            QPushButton { color:#e8e8e8; background:#3c3c3c;
                border:1px solid #4a4a4a; border-radius:5px; padding:4px 8px; font-size:12px; }
            QPushButton:hover { background:#4a4a4a; }
            QCheckBox { color:#e8e8e8; font-size:12px; }
            QComboBox { color:#e8e8e8; background:#3c3c3c; border:1px solid #4a4a4a;
                border-radius:5px; padding:3px 6px; font-size:12px; }
            QComboBox QAbstractItemView { background:#3c3c3c; color:#e8e8e8;
                selection-background-color:#0a84ff; }
            QSlider::groove:horizontal { height:4px; background:#4a4a4a; border-radius:2px; }
            QSlider::handle:horizontal { width:14px; margin:-5px 0;
                background:#0a84ff; border-radius:7px; }
            QSlider::sub-page:horizontal { background:#0a84ff; border-radius:2px; }
            """
        )
        LANG.changed.connect(self.retranslate_ui)

    def retranslate_ui(self, _code: str = "") -> None:
        self._line_label.setText(t(self._line_key))
        self._custom_btn.setText(t("自定义颜色…"))
        self._width_label.setText(t("线宽"))
        self._line_style_label.setText(t("线型"))
        idx = self._line_style_combo.currentIndex()
        self._line_style_combo.blockSignals(True)
        for i, (_key, name) in enumerate(self._line_style_keys):
            self._line_style_combo.setItemText(i, t(name))
        self._line_style_combo.blockSignals(False)
        self._line_style_combo.setCurrentIndex(idx)
        self._fill_label.setText(t("填充色"))
        self._fill_check.setText(t("启用"))
        self._transparent_btn.setToolTip(t("透明（无边框）"))
        self._fill_alpha_label.setText(t("填充透明度"))
        self._size_label.setText(t("字号"))
        self._bold_check.setText(t("加粗"))
        self._angle_label.setText(t("旋转角度"))
        self._bg_label.setText(t("文字背景色"))
        self._bg_check.setText(t("启用"))
        self._bg_alpha_label.setText(t("背景透明度"))
        self._bg_border_label.setText(t("文字背景边框"))
        self._bg_border_check.setText(t("启用边框"))
        self._bg_border_color_label.setText(t("边框颜色"))
        self._bg_border_transparent_btn.setToolTip(t("透明（无边框）"))
        self._bg_border_width_label.setText(t("边框线宽"))
        self._bg_border_style_label.setText(t("边框线型"))
        idx_bg = self._bg_border_style_combo.currentIndex()
        self._bg_border_style_combo.blockSignals(True)
        for i, (_key, name) in enumerate(self._line_style_keys):
            self._bg_border_style_combo.setItemText(i, t(name))
        self._bg_border_style_combo.blockSignals(False)
        self._bg_border_style_combo.setCurrentIndex(idx_bg)
        self._pen_arrow_label.setText(t("端点箭头"))
        self._pen_arrow_start.setText(t("起点加箭头"))
        self._pen_arrow_end.setText(t("终点加箭头"))

    # ---------------------------------------------------------- 工具方法
    def _emit(self, key: str, value) -> None:
        self.style_changed.emit({key: value})

    def _on_angle_changed(self, value: int) -> None:
        self._angle_value.setText(f"{int(value)}°")
        self._emit("angle", float(value))

    def _make_preset_color_buttons(self, key: str) -> list:
        """生成一排预设颜色块，点击即 emit 对应的样式键。

        用于填充色/边框色/背景色，替代系统颜色对话框（避免被置顶遮罩盖住）。
        颜色用半透明版本（alpha=0x80），保证填充/背景可见。
        """
        btns = []
        from PySide6.QtWidgets import QPushButton

        for c in PRESET_COLORS:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setProperty("color", c)
            # 半透明展示（alpha 0x80），点击时用同样带透明度的颜色
            b.setStyleSheet(
                f"background:{c}; border:1px solid #555; border-radius:4px;"
            )
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(
                lambda _=False, col=c, k=key: self._emit(k, self._picked(k, col))
            )
            btns.append(b)
        return btns

    @staticmethod
    def _alpha_from(value: int) -> int:
        """滑块百分比 → QColor 的 0~255 alpha。"""
        return int(round(max(0, min(100, value)) * 255 / 100))

    def _alpha_byte(self) -> int:
        return self._alpha_from(self._fill_alpha_slider.value())

    def _bg_alpha_byte(self) -> int:
        return self._alpha_from(self._bg_alpha_slider.value())

    def _picked(self, key: str, col: str) -> str:
        """预设色块点击：填充色 / 文字背景色各用自己的透明度滑块，
        边框色默认不透明（透明由专属 ∅ 按钮设置），其它保持固定半透明。
        """
        if key == "fill_color":
            self._fill_rgb = col
            return self._with_alpha(col, self._alpha_byte())
        if key == "bg_color":
            self._bg_rgb = col
            return self._with_alpha(col, self._bg_alpha_byte())
        if key == "bg_border_color":
            self._bg_border_rgb = col
            return self._with_alpha(col, 255)
        return self._with_alpha(col)

    def _on_fill_alpha(self, value: int) -> None:
        if self._fill_alpha_slider.signalsBlocked():
            return
        c = QColor(self._fill_rgb)
        c.setAlpha(self._alpha_from(value))
        self._emit("fill_color", c.name(QColor.HexArgb))

    def _on_bg_alpha(self, value: int) -> None:
        if self._bg_alpha_slider.signalsBlocked():
            return
        c = QColor(self._bg_rgb)
        c.setAlpha(self._alpha_from(value))
        self._emit("bg_color", c.name(QColor.HexArgb))

    @staticmethod
    def _with_alpha(hex_color: str, alpha: int = 0x80) -> str:
        """给 #RRGGBB 颜色加 alpha 通道，返回 #AARRGGBB。"""
        c = QColor(hex_color)
        return f"#{alpha:02x}{c.red():02x}{c.green():02x}{c.blue():02x}"

    def _pick_custom(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        c = QColorDialog.getColor(parent=self, title=t("选择颜色"))
        if c.isValid():
            self._emit("color", c.name())

    def _on_fill_toggle(self, on: bool) -> None:
        for b in self._fill_btns:
            b.setVisible(on)
        self._fill_alpha_slider.setEnabled(on)
        if on:
            self._emit("fill_color", self._picked("fill_color", self._fill_rgb))
        else:
            self._emit("fill_color", None)

    def _on_bg_toggle(self, on: bool) -> None:
        for b in self._bg_btns:
            b.setVisible(on)
        self._bg_alpha_slider.setEnabled(on)
        if on:
            self._emit("bg_color", self._picked("bg_color", self._bg_rgb))
        else:
            self._emit("bg_color", None)

    def _on_bg_border_toggle(self, on: bool) -> None:
        for w in self._bg_border_detail:
            w.setVisible(on)
        self._emit("bg_border", bool(on))

    # ---------------------------------------------------------- 状态回填
    def set_state(self, shape: Shape | None, defaults: dict) -> None:
        """根据选中标注（或默认值）回填面板状态，并按类型显隐控件。

        shape 为 None 表示没有选中标注，此时用 defaults 里的当前样式值。
        """
        # 取实际要回填的值
        color = shape.color if shape else defaults.get("color", QColor(DEFAULT_PEN))
        width = shape.width if shape else defaults.get("width", PEN_WIDTH)
        line_style = shape.line_style if shape else defaults.get("line_style", "solid")
        font_size = shape.font_size if shape else defaults.get("font_size", FONT_SIZE)
        bg = shape.bg_color if shape else defaults.get("bg_color")
        fill = shape.fill_color if shape else None
        bborder = (bool(getattr(shape, "bg_border", False)) if shape
                   else bool(defaults.get("bg_border", False)))
        bborder_color = (getattr(shape, "bg_border_color", None) if shape
                         else defaults.get("bg_border_color"))
        bborder_width = (int(getattr(shape, "bg_border_width", 2)) if shape
                         else int(defaults.get("bg_border_width", 2)))
        bborder_style = (getattr(shape, "bg_border_style", "solid") if shape
                         else defaults.get("bg_border_style", "solid"))

        kind = shape.kind if shape else None
        is_shape = kind in ("rect", "ellipse", "mosaic")
        is_text = kind == "text"
        is_rotatable = kind in ROTATABLE_KINDS
        # 没有选中标注时也显示，方便先设好「新建画笔/直线」的默认箭头
        is_pen = self._show_pen_arrows and (
            kind in ("pen", "line") or shape is None
        )

        # 顶部「颜色」标签按类型命名：封闭图形/线条=线条颜色，文字=文字颜色
        if is_text:
            self._line_key = "文字颜色"
        elif is_shape or kind in ("arrow", "pen", "line"):
            self._line_key = "线条颜色"
        else:
            self._line_key = "颜色"
        self._line_label.setText(t(self._line_key))

        # 显隐控件
        for w in self._shape_only:
            w.setVisible(is_shape)
        for w in self._text_only:
            w.setVisible(is_text)
        # 线宽/线型：文字时隐藏（对文字无意义）
        for w in self._non_text:
            w.setVisible(not is_text)
        for w in self._pen_only:
            w.setVisible(is_pen)
        for w in self._rotatable_only:
            w.setVisible(is_rotatable)
        # 子组：先按类型整体显隐，再按「是否启用」显隐，避免选到非文字
        # 标注时把文字控件单独放出来
        for b in self._bg_btns:
            b.setVisible(is_text and bg is not None)
        self._bg_alpha_slider.setEnabled(bg is not None)
        for w in self._bg_border_detail:
            w.setVisible(is_text and bborder)

        # 线宽
        self._width_slider.blockSignals(True)
        self._width_slider.setValue(int(width))
        self._width_slider.blockSignals(False)

        # 线型
        self._line_style_combo.blockSignals(True)
        idx = self._line_style_combo.findData(line_style)
        self._line_style_combo.setCurrentIndex(max(0, idx))
        self._line_style_combo.blockSignals(False)

        # 字号
        self._size_slider.blockSignals(True)
        self._size_slider.setValue(int(font_size))
        self._size_slider.blockSignals(False)

        # 旋转角度（只对矩形 / 椭圆 / 文字可见）
        angle = int(round(normalize_angle(shape_angle(shape)))) if shape else 0
        angle = max(-180, min(180, angle))
        self._angle_slider.blockSignals(True)
        self._angle_slider.setValue(angle)
        self._angle_slider.blockSignals(False)
        self._angle_value.setText(f"{angle}°")

        # 加粗
        bold = shape.bold if shape else False
        self._bold_check.blockSignals(True)
        self._bold_check.setChecked(bool(bold))
        self._bold_check.blockSignals(False)

        # 画笔端点箭头
        p_start = getattr(shape, "pen_arrow_start", False) if shape else defaults.get("pen_arrow_start", False)
        p_end = getattr(shape, "pen_arrow_end", False) if shape else defaults.get("pen_arrow_end", False)
        self._pen_arrow_start.blockSignals(True)
        self._pen_arrow_start.setChecked(bool(p_start))
        self._pen_arrow_start.blockSignals(False)
        self._pen_arrow_end.blockSignals(True)
        self._pen_arrow_end.setChecked(bool(p_end))
        self._pen_arrow_end.blockSignals(False)

        # 填充色
        self._fill_check.blockSignals(True)
        self._fill_check.setChecked(fill is not None)
        self._fill_check.blockSignals(False)
        for b in self._fill_btns:
            b.setVisible(is_shape and fill is not None)
        self._fill_alpha_slider.setEnabled(fill is not None)
        if fill is not None and isinstance(fill, QColor):
            self._fill_rgb = fill.name(QColor.HexRgb)
            self._fill_alpha_slider.blockSignals(True)
            self._fill_alpha_slider.setValue(int(round(fill.alpha() * 100 / 255)))
            self._fill_alpha_slider.blockSignals(False)

        # 文字背景色（颜色 + 独立透明度）
        self._bg_check.blockSignals(True)
        self._bg_check.setChecked(bg is not None)
        self._bg_check.blockSignals(False)
        if bg is not None and isinstance(bg, QColor):
            self._bg_rgb = bg.name(QColor.HexRgb)
            self._bg_alpha_slider.blockSignals(True)
            self._bg_alpha_slider.setValue(int(round(bg.alpha() * 100 / 255)))
            self._bg_alpha_slider.blockSignals(False)

        # 文字背景边框
        self._bg_border_check.blockSignals(True)
        self._bg_border_check.setChecked(bborder)
        self._bg_border_check.blockSignals(False)
        self._bg_border_width_slider.blockSignals(True)
        self._bg_border_width_slider.setValue(max(1, min(20, bborder_width)))
        self._bg_border_width_slider.blockSignals(False)
        self._bg_border_style_combo.blockSignals(True)
        idx_b = self._bg_border_style_combo.findData(bborder_style)
        self._bg_border_style_combo.setCurrentIndex(max(0, idx_b))
        self._bg_border_style_combo.blockSignals(False)
        bcur = (bborder_color.name(QColor.HexRgb).lower()
                if isinstance(bborder_color, QColor) else "")
        btrans = isinstance(bborder_color, QColor) and bborder_color.alpha() == 0
        for b in self._bg_border_btns:
            c = b.property("color").lower()
            if c == bcur and not btrans:
                b.setStyleSheet(
                    f"background:{c}; border:2px solid #ffffff; border-radius:4px;"
                )
            else:
                b.setStyleSheet(
                    f"background:{c}; border:1px solid #555; border-radius:4px;"
                )
        self._bg_border_transparent_btn.setStyleSheet(
            "color:#e8e8e8; background:#3c3c3c; border:2px solid #ffffff;"
            "border-radius:4px; padding:0;" if btrans else
            "color:#e8e8e8; background:#3c3c3c; border:1px dashed #888;"
            "border-radius:4px; padding:0;"
        )

        # 颜色块高亮当前色：当前色加白色描边，其余用灰描边
        cur_hex = color.name(QColor.HexRgb).lower() if isinstance(color, QColor) else str(color).lower()
        is_transparent = isinstance(color, QColor) and color.alpha() == 0
        for b in self._color_btns:
            c = b.property("color").lower()
            if c == cur_hex and not is_transparent:
                b.setStyleSheet(
                    f"background:{c}; border:2px solid #ffffff; border-radius:4px;"
                )
            else:
                b.setStyleSheet(
                    f"background:{c}; border:1px solid #555; border-radius:4px;"
                )
        # 文字不该被设成透明（否则内容看不见），所以文字标注时隐藏该色块
        self._transparent_btn.setVisible(not is_text)
        self._transparent_btn.setStyleSheet(
            "color:#e8e8e8; background:#3c3c3c; border:2px solid #ffffff;"
            "border-radius:4px; padding:0;" if is_transparent else
            "color:#e8e8e8; background:#3c3c3c; border:1px dashed #888;"
            "border-radius:4px; padding:0;"
        )


# ---------------------------------------------------------------------------
class OcrPanel(QWidget):
    """OCR 结果面板：作为 Overlay 的普通子控件，浮在截图画面上方。

    文字用只读 QPlainTextEdit 呈现 —— 内容不可改，但仍可拖选、
    Ctrl+A 全选、Ctrl+C 复制、右键复制。点「复制」后面板自动收起，
    通过 closed 信号通知宿主恢复正常的截图编辑态。
    """

    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OcrPanelRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(
            "QWidget#OcrPanelRoot { background:#202124; border:1px solid #4a4a4a; "
            "border-radius:8px; }"
            "QLabel { color:#e8eaed; font-size:12px; }"
            "QPlainTextEdit { background:#2b2d31; color:#f1f3f4; border:1px solid #555; "
            "border-radius:4px; selection-background-color:#0a84ff; padding:6px; }"
            "QPushButton { background:#3a3d42; color:#f1f3f4; border:1px solid #5a5d62; "
            "border-radius:4px; padding:5px 12px; }"
            "QPushButton:hover { background:#4a4d52; }"
            "QPushButton:disabled { color:#888; background:#2b2d31; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        self._mode = "busy"
        self._result_tag = ""
        self._title = QLabel(t("正在识别文字…"))
        root.addWidget(self._title)

        self.edit = QPlainTextEdit()
        # 只读但保留标准文本选择/复制交互（拖选、Ctrl+A、Ctrl+C、右键菜单）
        self.edit.setReadOnly(True)
        self.edit.setFont(QFont("", 12))
        self.edit.setMinimumHeight(70)
        root.addWidget(self.edit, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._b_sel = QPushButton(t("复制选中"))
        self._b_all = QPushButton(t("复制全部"))
        self._b_close = QPushButton(t("关闭"))
        for b in (self._b_sel, self._b_all, self._b_close):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        self._b_sel.clicked.connect(self._copy_selection)
        self._b_all.clicked.connect(self._copy_all)
        self._b_close.clicked.connect(self.closed.emit)
        row.addStretch(1)
        row.addWidget(self._b_sel)
        row.addWidget(self._b_all)
        row.addWidget(self._b_close)
        root.addLayout(row)

        self._closing = False
        self.set_busy()
        LANG.changed.connect(self.retranslate_ui)

    def retranslate_ui(self, _code: str = "") -> None:
        self._b_sel.setText(t("复制选中"))
        self._b_all.setText(t("复制全部"))
        self._b_close.setText(t("关闭"))
        self._render_title()

    def _render_title(self) -> None:
        if self._mode == "busy":
            self._title.setText(t("正在识别文字…"))
        elif self._mode == "result":
            self._title.setText(
                t("识别结果{tag} · 可拖选文字，Ctrl+C 或点下方按钮复制",
                  tag=self._result_tag)
            )
        else:
            self._title.setText(t("取字"))

    # ------------------------------------------------------------ 状态切换
    def set_busy(self) -> None:
        self._closing = False
        self._busy = True
        self._mode = "busy"
        self._render_title()
        self.edit.clear()
        self.edit.hide()
        self._b_sel.setEnabled(False)
        self._b_all.setEnabled(False)

    def set_result(self, text: str, backend: str = "") -> None:
        self._closing = False
        self._busy = False
        self._mode = "result"
        self._result_tag = f"（{backend}）" if backend else ""
        self._render_title()
        self.edit.setPlainText(text)
        self.edit.show()
        self._b_sel.setEnabled(True)
        self._b_all.setEnabled(True)

    def set_message(self, msg: str) -> None:
        """识别失败 / 没识别到文字：仍显示面板，用户可关闭回到编辑态。"""
        self._closing = False
        self._busy = False
        self._mode = "message"
        self._render_title()
        self.edit.setPlainText(msg)
        self.edit.show()
        self._b_sel.setEnabled(False)
        self._b_all.setEnabled(False)

    def focus_edit(self) -> None:
        self.edit.setFocus()

    def is_busy(self) -> bool:
        return self._busy

    # ------------------------------------------------------------ 复制
    def _copy_selection(self) -> None:
        cur = self.edit.textCursor()
        txt = cur.selectedText() if cur.hasSelection() else self.edit.toPlainText()
        self._copy_and_close(txt)

    def _copy_all(self) -> None:
        self._copy_and_close(self.edit.toPlainText())

    def _copy_and_close(self, txt: str) -> None:
        if not txt or self._closing:
            return
        QApplication.clipboard().setText(txt)
        self._closing = True
        self._title.setText(t("已复制到剪贴板 ✓"))
        # 短暂显示反馈后自动收起面板，回到正常截图状态
        QTimer.singleShot(420, self.closed.emit)


def _is_cjk(ch: str) -> bool:
    """中文/全角标点：同一视觉行的两块之间不加空格，英文之间加空格。"""
    if not ch:
        return False
    o = ord(ch)
    return 0x3400 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF


def _reading_order(lines: list[dict]) -> list[str]:
    """把散落的识别框按「从上到下、同排从左到右」整理成可复制的整行文本。"""
    with_box = [d for d in lines if d.get("box")]
    no_box = [d.get("text", "") for d in lines if not d.get("box")]
    items = sorted(with_box, key=lambda d: (d["box"][1], d["box"][0]))
    rows: list[dict] = []
    for d in items:
        x1, y1, x2, y2 = d["box"]
        cy = (y1 + y2) / 2.0
        tol = max(6.0, (y2 - y1) * 0.6)
        for row in rows:
            if abs(row["cy"] - cy) <= tol:
                row["items"].append(d)
                n = len(row["items"])
                row["cy"] = (row["cy"] * (n - 1) + cy) / n
                break
        else:
            rows.append({"cy": cy, "items": [d]})

    out: list[str] = []
    for row in rows:
        parts = sorted(row["items"], key=lambda d: d["box"][0])
        txt = parts[0].get("text", "")
        for d in parts[1:]:
            nxt = d.get("text", "")
            if not nxt:
                continue
            sep = "" if (_is_cjk(txt[-1:]) and _is_cjk(nxt[:1])) else " "
            txt += sep + nxt
        if txt:
            out.append(txt)
    return out + [t for t in no_box if t]


# ---------------------------------------------------------------------------
class OcrBar(QWidget):
    """逐行取字模式的窄工具条：放在选区外侧，不遮挡原文。"""

    copied_selection = Signal()
    copied_all = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OcrBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(
            "QWidget#OcrBar { background:#202124; border:1px solid #4a4a4a; "
            "border-radius:8px; }"
            "QLabel { color:#e8eaed; font-size:12px; }"
            "QPushButton { background:#3a3d42; color:#f1f3f4; border:1px solid #5a5d62; "
            "border-radius:4px; padding:4px 10px; }"
            "QPushButton:hover { background:#4a4d52; }"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)
        self._status_key = "识别结果"
        self._status_kwargs: dict = {}
        self._label = QLabel(t("识别结果"))
        lay.addWidget(self._label, 1)
        self._btn_keys: list[tuple[QPushButton, str]] = []
        for text_key, sig in (
            ("复制选中", self.copied_selection),
            ("复制全部", self.copied_all),
            ("返回", self.closed),
        ):
            b = QPushButton(t(text_key))
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(sig.emit)
            lay.addWidget(b)
            self._btn_keys.append((b, text_key))
        LANG.changed.connect(self.retranslate_ui)

    def _render_status(self) -> None:
        self._label.setText(t(self._status_key, **self._status_kwargs))

    def set_status(self, n: int, backend: str = "") -> None:
        self._status_key = "识别到 {n} 行{tag} · 拖选文字后 Ctrl+C 复制，复制完自动返回"
        self._status_kwargs = {"n": n, "tag": f"（{backend}）" if backend else ""}
        self._render_status()

    def feedback(self, msg_key: str) -> None:
        """传入简体中文文案 key（而非已翻译文本），语言切换时可重新渲染。"""
        self._status_key = msg_key
        self._status_kwargs = {}
        self._render_status()

    def retranslate_ui(self, _code: str = "") -> None:
        for b, key in self._btn_keys:
            b.setText(t(key))
        self._render_status()


# ---------------------------------------------------------------------------
class OcrLayer(QWidget):
    """方案 B：把 OCR 每一行按 bbox 盖回原文在截图里的位置。

    每行一个只读 QPlainTextEdit —— 可拖选、Ctrl+A、Ctrl+C、右键复制；
    近不透明浅色底把原来的字盖住，避免「同一行字叠两遍」发糊。
    复制（按钮或 Ctrl+C）后自动收起，回到正常截图编辑态。
    """

    closed = Signal()
    MAX_BLOCKS = 160

    # 不透明浅底：完整盖住原来的字，避免「同一行字叠两遍」发糊，
    # 也避开子控件半透明背景在部分平台上的合成异常。
    BLOCK_STYLE = (
        "QWidget#OcrLayer { background:transparent; }"
        "QPlainTextEdit#OcrBlock { background:#f8fafc; color:#111318;"
        " border:1px solid #0a84ff; border-radius:2px; padding:0px;"
        " selection-background-color:#0a84ff; selection-color:#ffffff; }"
    )
    # 每个块再单独设一次，避免父样式表在某些平台下不向下传播导致透出原字
    BLOCK_QSS = (
        "QPlainTextEdit { background:#f8fafc; color:#111318;"
        " border:1px solid #0a84ff; border-radius:2px; padding:0px;"
        " selection-background-color:#0a84ff; selection-color:#ffffff; }"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OcrLayer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(self.BLOCK_STYLE)

        self.bar = OcrBar(self)
        self.bar.copied_selection.connect(self.copy_selection)
        self.bar.copied_all.connect(self.copy_all)
        self.bar.closed.connect(self.closed.emit)

        self._blocks: list[QPlainTextEdit] = []
        self._lines: list[dict] = []
        self._closing = False
        self._armed = False

    # ------------------------------------------------------------ 行文本块
    def clear_blocks(self) -> None:
        for e in self._blocks:
            e.removeEventFilter(self)
            e.hide()
            e.deleteLater()
        self._blocks = []

    def set_lines(
        self, lines: list[dict], sel: QRect, dpr: float, backend: str = ""
    ) -> None:
        """把选区裁剪图内的像素坐标换算成遮罩逻辑坐标，逐行铺回去。"""
        self.clear_blocks()
        self._lines = list(lines)
        self._closing = False
        d = dpr or 1.0
        pad = 2
        for item in [d0 for d0 in self._lines if d0.get("box")][: self.MAX_BLOCKS]:
            text = str(item.get("text", ""))
            if not text:
                continue
            x1, y1, x2, y2 = item["box"]
            lx = sel.left() + x1 / d - pad
            ly = sel.top() + y1 / d - pad
            lw = max(10.0, (x2 - x1) / d) + 2 * pad
            lh = max(10.0, (y2 - y1) / d) + 2 * pad

            # 字号跟随原文字高度；再留出富余宽度，保证识别出的字不被截断
            font_px = int(max(11, min(40, (y2 - y1) / d * 0.80)))
            f = QFont()
            f.setPixelSize(font_px)
            fm = QFontMetrics(f)
            w = int(max(lw, fm.horizontalAdvance(text) + 10))
            h = int(max(lh, fm.height() + 6))
            w = max(24, min(w, self.width() - 4))
            h = max(16, min(h, self.height() - 4))
            gx = max(0, min(int(round(lx)), self.width() - w))
            gy = max(0, min(int(round(ly)), self.height() - h))

            e = QPlainTextEdit(self)
            e.setObjectName("OcrBlock")
            e.setStyleSheet(self.BLOCK_QSS)
            e.setPlainText(text)
            e.setReadOnly(True)
            e.setLineWrapMode(QPlainTextEdit.NoWrap)
            e.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            e.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            e.setContentsMargins(0, 0, 0, 0)
            e.document().setDocumentMargin(0)
            e.setFont(f)
            e.setCursor(Qt.IBeamCursor)
            e.setGeometry(gx, gy, w, h)
            e.installEventFilter(self)
            e.show()
            self._blocks.append(e)

        self.bar.set_status(len(self._lines), backend)

    def set_lines_view(
        self,
        lines: list[dict],
        scale: float,
        ox: float,
        oy: float,
        backend: str = "",
    ) -> None:
        """窗口化编辑器用：把原图物理像素 bbox 换算到缩放后的画布坐标。

        Overlay 里 bbox 是「选区裁剪图的物理像素」，靠 sel + dpr 换算；编辑器
        里整张图被 view_scale 缩放并居中在 (off_x, off_y)，所以先在这里把
        坐标乘缩放再加偏移，然后复用 set_lines() 的同一套铺块逻辑。
        """
        s = scale or 1.0
        mapped: list[dict] = []
        for d in lines:
            box = d.get("box") if isinstance(d, dict) else None
            if not box:
                mapped.append(d)
                continue
            x1, y1, x2, y2 = box
            nd = dict(d)
            nd["box"] = [ox + x1 * s, oy + y1 * s, ox + x2 * s, oy + y2 * s]
            mapped.append(nd)
        # set_lines() 内部还会加 sel.left()/top() 并除以 d；这里传零偏移 + d=1
        self.set_lines(mapped, QRect(0, 0, 0, 0), 1.0, backend)

    def place_bar(self, sel: QRect) -> None:
        """优先选区上方；上方不够放下方；始终避开选区内容。"""
        self.bar.adjustSize()
        hint = self.bar.sizeHint()
        w = max(360, min(hint.width(), self.width() - 16))
        h = max(34, hint.height())
        x = max(0, min(sel.left(), self.width() - w))
        y = sel.top() - h - 8
        if y < 0:
            y = sel.bottom() + 8
        if y + h > self.height():
            y = max(0, self.height() - h - 8)
        self.bar.setGeometry(x, y, w, h)
        self.bar.raise_()   # 行块是后创建的子控件，工具条要保持最上层

    # ------------------------------------------------------------ 复制 / 关闭
    def arm(self) -> None:
        """结果态监听剪贴板：Ctrl+C / 右键复制 / 按钮复制都会自动收起。"""
        if not self._armed:
            QApplication.clipboard().dataChanged.connect(self._on_clipboard)
            self._armed = True

    def disarm(self) -> None:
        if self._armed:
            try:
                QApplication.clipboard().dataChanged.disconnect(self._on_clipboard)
            except (RuntimeError, TypeError):
                pass
            self._armed = False

    def _on_clipboard(self) -> None:
        self._copied()

    def _copy(self, txt: str) -> None:
        if not txt or self._closing:
            return
        QApplication.clipboard().setText(txt)
        self._copied()

    def _copied(self) -> None:
        if self._closing or not self.isVisible():
            return
        self._closing = True
        self.bar.feedback("已复制到剪贴板 ✓")
        QTimer.singleShot(420, self.closed.emit)

    def copy_selection(self) -> None:
        for e in self._blocks:
            cur = e.textCursor()
            if cur.hasSelection():
                self._copy(cur.selectedText())
                return
        fw = QApplication.focusWidget()
        if isinstance(fw, QPlainTextEdit) and fw in self._blocks:
            self._copy(fw.toPlainText())
            return
        self.bar.feedback("请先用鼠标拖选某一行文字，或点「复制全部」")

    def copy_all(self) -> None:
        self._copy("\n".join(_reading_order(self._lines)))

    # ------------------------------------------------------------ 事件
    def eventFilter(self, obj, ev):  # noqa: N802
        if isinstance(obj, QPlainTextEdit) and ev.type() == QEvent.KeyPress:
            if ev.key() == Qt.Key_Escape:
                self.closed.emit()
                return True
        return super().eventFilter(obj, ev)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        # 空白处的点击就地吞掉，不冒泡给 Overlay，避免误重新框选/加标注
        ev.accept()

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802
        ev.accept()

    def hideEvent(self, ev) -> None:  # noqa: N802
        self.disarm()
        super().hideEvent(ev)


# ---------------------------------------------------------------------------
class Toolbar(QWidget):
    """贴着选区显示的浮动工具条（作为 Overlay 的子控件，随遮罩一起消失）。"""

    tool_changed = Signal(str)
    undo_clicked = Signal()
    save_clicked = Signal()
    copy_clicked = Signal()
    long_clicked = Signal()
    ocr_clicked = Signal()
    style_clicked = Signal()
    close_clicked = Signal()
    confirm_clicked = Signal()  # 选择阶段「确定」：进入程序窗口继续编辑
    # 整图变换（仅窗口化编辑器使用，截屏遮罩里通过 exclude 隐藏）
    rot_cw_clicked = Signal()
    rot_ccw_clicked = Signal()
    flip_h_clicked = Signal()
    flip_v_clicked = Signal()

    def __init__(self, parent: QWidget | None = None, exclude: Iterable[str] = ()) -> None:
        super().__init__(parent)
        # 纯 QWidget 需要这个属性，样式表里的 background 才会被绘制
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.current = "select"

        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QLabel

        excluded = set(exclude or ())
        self._excluded = excluded
        self._buttons: dict[str, QPushButton] = {}
        self._actions: dict[str, QPushButton] = {}
        self._tip_keys: dict[str, str] = {}
        self._separators: list[QLabel] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        for key, label in TOOLS:
            b = QPushButton()
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(t(label))
            b.setFocusPolicy(Qt.NoFocus)
            b.setIcon(toolbar_icon(key))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(34, 30)
            b.clicked.connect(lambda _=False, k=key: self._on_tool(k))
            lay.addWidget(b)
            self._buttons[key] = b
            self._tip_keys["tool:" + key] = label

        def add_action(key: str, tip: str, sig: Signal) -> None:
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(t(tip))
            b.setFocusPolicy(Qt.NoFocus)
            b.setIcon(toolbar_icon(key))
            b.setIconSize(QSize(22, 22))
            b.setFixedSize(34, 30)
            b.clicked.connect(sig.emit)
            lay.addWidget(b)
            if key in excluded:
                b.hide()
            self._actions[key] = b
            self._tip_keys["action:" + key] = tip

        add_action("撤销", "撤销上一步标注 (Ctrl+Z)", self.undo_clicked)
        # 工具栏不再放「样式」按钮：选中标注时样式面板会自动弹出，
        # 窗口编辑器菜单里也有「样式面板」入口，不必多占一个图标位。

        # 整图变换分组（仅窗口化编辑器显示；截屏遮罩里隐藏）
        sep = QLabel("│")
        sep.setStyleSheet("QLabel { color:#666; font-size:14px; padding:0 2px; }")
        lay.addWidget(sep)
        self._separators.append(sep)
        add_action("顺旋", "顺时针旋转 90° (Ctrl+R)", self.rot_cw_clicked)
        add_action("逆旋", "逆时针旋转 90° (Ctrl+Shift+R)", self.rot_ccw_clicked)
        add_action("左右", "左右镜像 / 水平翻转 (Ctrl+H)", self.flip_h_clicked)
        add_action("上下", "上下镜像 / 垂直翻转 (Ctrl+Shift+H)", self.flip_v_clicked)

        add_action("长截图", "滚动长截图", self.long_clicked)
        add_action("取字", "识别选区文字 (OCR)", self.ocr_clicked)
        add_action("保存", "另存为文件 (Ctrl+S)", self.save_clicked)
        add_action("复制", "复制到剪贴板 (Enter)", self.copy_clicked)
        add_action("确定", "确认选区，进入程序窗口继续编辑 (Enter)", self.confirm_clicked)
        add_action("✕", "取消 (Esc)", self.close_clicked)

        self.setStyleSheet(
            """
            QWidget { background: #2b2b2b; border-radius: 8px; }
            QPushButton {
                color: #e8e8e8; background: #3c3c3c; border: 1px solid #4a4a4a;
                border-radius: 6px; padding: 2px; font-size: 13px;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton:checked { background: #0a84ff; border-color: #0a84ff; color: white; }
            """
        )
        LANG.changed.connect(self.retranslate_ui)

    def set_confirm_tip(self, text_key: str) -> None:
        """切换「确定」按钮的提示文案（长截图流程与常规编辑流程不同）。

        同时更新 _tip_keys，保证切换界面语言后 retranslate_ui 用对文案。
        """
        self._tip_keys["action:确定"] = text_key
        btn = self._actions.get("确定")
        if btn is not None:
            btn.setToolTip(t(text_key))

    def retranslate_ui(self, _code: str = "") -> None:
        """图标 key 保持中文不变，只刷新按钮提示文字。"""
        for key, text_key in self._tip_keys.items():
            kind, _, name = key.partition(":")
            btn = self._buttons.get(name) if kind == "tool" else self._actions.get(name)
            if btn is not None:
                btn.setToolTip(t(text_key))

    def _on_tool(self, key: str) -> None:
        for k, b in self._buttons.items():
            b.setChecked(k == key)
        self.current = key
        self.tool_changed.emit(key)

    def set_confirm_mode(self, on: bool) -> None:
        """选择阶段（确认前）：只保留「确定 / 取消」，隐藏全部标注工具与
        其它动作（撤销 / 长截图 / 取字 / 保存 / 复制）。on=False 时恢复
        （被排除的项保持隐藏）。"""
        for b in self._buttons.values():
            b.setVisible(not on)
        for s in self._separators:
            s.setVisible(not on)
        for key, b in self._actions.items():
            if key in ("确定", "✕"):
                b.setVisible(on)
            else:
                b.setVisible((not on) and key not in self._excluded)


# ---------------------------------------------------------------------------
class Overlay(QWidget):
    """
    全屏遮罩：框选 → 调整 → 标注 → 完成。

    信号：
        done(QImage)          用户完成，交付最终图像
        cancelled()           用户取消
        long_shot(QRect)      请求对选区做长截图（逻辑坐标）
        ocr(QImage)           请求对选区做 OCR
        saved(QImage)         用户点了保存（由宿主决定写到哪）
    """

    done = Signal(QImage)
    cancelled = Signal()
    long_shot = Signal(QRect)
    ocr = Signal(QImage)
    save_requested = Signal(QImage)
    # 全屏模式双击：把整张截图（物理图 + 已转物理坐标的标注）交给窗口化编辑器
    to_editor = Signal(QImage, list)

    def __init__(self, base_image: QImage, dpr: float = 1.0) -> None:
        super().__init__(
            None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)
        # 关键：paintEvent 会完整覆盖整个窗口，禁止 Qt 先擦背景。
        # 否则顶层窗口拖动框选时会被反复清空，导致选区"不动态显示"/闪烁。
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.base = base_image            # 物理像素原图
        self.dpr = dpr or 1.0
        # 预生成「选区高亮底图」与「压暗底图」的逻辑尺寸版本，
        # 避免 paintEvent 每帧都把物理尺寸图缩放到逻辑尺寸（高分屏卡顿主因）。
        # 先缩放再压暗：压暗只需在较小的逻辑尺寸图上做一次，
        # 比「物理图上压暗 + 再缩放」少一次全屏拷贝和一次全屏缩放。
        self.base_logical = self._scale_to_logical(base_image)
        self.dim_logical = self._make_dim(self.base_logical)

        self.sel: QRect | None = None     # 逻辑坐标选区
        self.shapes: list[Shape] = []
        self._draft: Shape | None = None
        self._tool = "select"

        # 当前样式：新建标注使用这些值；样式面板可实时修改
        self._color = QColor(DEFAULT_PEN)
        self._width = PEN_WIDTH
        self._font_size = FONT_SIZE
        self._bg_color: QColor | None = None
        self._bg_border = False
        self._bg_border_color: QColor | None = QColor("#ff000000")
        self._bg_border_width = 2
        self._bg_border_style = "solid"
        self._line_style = "solid"
        # 新建画笔 / 直线的默认端点箭头（也可在样式面板里对选中项单独改）
        self._pen_arrow_start = False
        self._pen_arrow_end = False

        # 当前选中的标注（用于"确定前修改已有标注"）
        self._selected: Shape | None = None

        self._mode = "idle"               # idle | picking | selecting | editing
        self.capture_mode = "rect"        # rect | window | fullscreen
        self.long_mode = False            # 独立「滚动长截图」命令：框选→确定→直接拼接
        # 遮罩上的提示文字在 paintEvent 里现取 t()，语言切换后需触发重绘
        LANG.changed.connect(self.update)
        self._window_picker = None        # callable(pos) -> (QRect, title) | QRect | None
        self._hover_rect: QRect | None = None
        self._confirm_mode = False        # 选择完成、仅显示「确定/取消」的阶段
        self._hover_title = ""
        self._last_pick_time = 0.0
        self._last_pick_pos = QPoint(-9999, -9999)
        self._drag_origin: QPoint | None = None
        self._move_origin: QPoint | None = None
        self._resize_edge = ""            # n/s/e/w/ne/nw/se/sw
        self._sel_at_drag_start: QRect | None = None
        self._drag_shape: Shape | None = None        # 正在拖动的标注
        self._drag_shape_origin: QPoint | None = None  # 拖动起点
        self._drag_shape_snapshot: dict | None = None  # 标注几何初始快照
        self._reshape_arrow: Shape | None = None     # 正在拉伸端点的箭头
        self._reshape_which = ""                     # "start" / "end"
        # 选中矩形 / 椭圆后拖四角缩放
        self._resize_shape: Shape | None = None
        self._resize_shape_corner = ""               # nw / ne / se / sw
        self._resize_shape_base: QRect | None = None  # 拖动开始时的 rect 快照
        self._resize_shape_center = QPointF()         # 拖动开始时的旋转中心
        self._resize_shape_angle = 0.0               # 拖动开始时的角度
        # 拖动旋转柄旋转矩形 / 椭圆 / 文字
        self._rotating_shape: Shape | None = None
        self._rotate_base_angle = 0.0
        self._rotate_start_pos = QPoint()
        self._rotate_center = QPointF()

        # --- 重绘节流 / 脏区跟踪 ---
        self._last_repaint = 0.0                  # time.monotonic() 秒
        self._pending_repaint = False             # 是否已排了补画定时器
        self._dirty: QRect | None = None          # 节流期间累积的待重绘区域
        self._last_painted_sel: QRect | None = None  # 上一次实际画出的选区（用于擦残影）
        self._cursor_cache = Qt.CrossCursor      # __init__ 里已设为十字
        self._label_font = QFont("", 10)
        self._label_cache: tuple[str, int, int] | None = None  # (文本, 宽, 高)

        self.toolbar = Toolbar(self, exclude=TRANSFORM_ACTIONS)
        self.toolbar.hide()
        self.toolbar.tool_changed.connect(self._set_tool)
        self.toolbar.undo_clicked.connect(self.undo)
        self.toolbar.close_clicked.connect(self.cancel)
        self.toolbar.copy_clicked.connect(self._confirm)
        self.toolbar.save_clicked.connect(lambda: self.save_requested.emit(self.compose()))
        # 旧工具条「长截图」按钮：确认模式下被 set_confirm_mode(True) 隐藏，
        # 现已由主窗口 / 托盘的独立命令取代。保留作兼容入口：它同样发
        # Overlay 局部逻辑选区，与 _confirm 的长截图分支语义一致。
        self.toolbar.long_clicked.connect(lambda: self.long_shot.emit(QRect(self.sel) if self.sel else QRect()))
        self.toolbar.ocr_clicked.connect(lambda: self.ocr.emit(self.raw_crop()))
        self.toolbar.style_clicked.connect(self._toggle_style_panel)
        self.toolbar.confirm_clicked.connect(self._confirm)

        self.style_panel = StylePanel(self, show_pen_arrows=True)
        self.style_panel.hide()
        self.style_panel.style_changed.connect(self._apply_style)

        # 取字：逐行盖回原文位置的覆盖层 + 识别中/降级用的浮层面板，
        # 两者都是普通子控件，稳定浮在遮罩上方且不会被置顶窗口遮挡。
        self.ocr_panel = OcrPanel(self)
        self.ocr_panel.hide()
        self.ocr_panel.closed.connect(self.hide_ocr_panel)
        self.ocr_layer = OcrLayer(self)
        self.ocr_layer.hide()
        self.ocr_layer.closed.connect(self.hide_ocr_panel)

        self._text_edit: QLineEdit | None = None
        self._editing_shape: Shape | None = None

    # ---------------------------------------------------------------- 工具
    @staticmethod
    def _make_dim(img: QImage) -> QImage:
        out = img.copy()
        p = QPainter(out)
        p.fillRect(out.rect(), QColor(0, 0, 0, DIM_ALPHA))
        p.end()
        return out

    def _scale_to_logical(self, img: QImage) -> QImage:
        """把物理像素图一次性缩到逻辑尺寸，供 paintEvent 直接 1:1 绘制。"""
        d = self.dpr
        if abs(d - 1.0) < 1e-6:
            return img
        w = max(1, int(round(img.width() / d)))
        h = max(1, int(round(img.height() / d)))
        return img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)

    def to_phys(self, r: QRect) -> QRect:
        d = self.dpr
        return QRect(
            int(round(r.x() * d)),
            int(round(r.y() * d)),
            max(1, int(round(r.width() * d))),
            max(1, int(round(r.height() * d))),
        )

    # ------------------------------------------------------------ 截图模式
    def set_long_mode(self, on: bool = True, window_picker=None) -> None:
        """切换为独立「滚动长截图」流程：悬停高亮窗口 → 单击即自动滚屏拼接。

        与旧版不同，这里**不框选、不点「确定」**：单击目标窗口后立刻把
        它的客户区矩形交给宿主启动拼接，滚动过程中的左键 / 右键 / 打勾
        才控制暂停与结束。

        window_picker 为 None 时（例如某些自测场景没有 Win32 窗口枚举）
        退回框选 + 确定的兼容路径，避免卡在 picking 状态无法操作。
        """
        self.long_mode = on
        self.sel = None
        self.shapes.clear()
        self._selected = None
        self._hover_rect = None
        self._hover_title = ""
        self._last_pick_time = 0.0
        self._last_pick_pos = QPoint(-9999, -9999)
        self.toolbar.set_confirm_tip(
            "开始滚动拼接 (Enter)" if on else "确认选区，进入程序窗口继续编辑 (Enter)"
        )
        if on and window_picker is not None:
            self.capture_mode = "window"
            self._window_picker = window_picker
            self._mode = "picking"
        else:
            self.capture_mode = "rect"
            self._window_picker = None
            self._mode = "idle"
        self.update()

    def set_capture_mode(self, mode: str, window_picker=None) -> None:
        """在 setGeometry 之后、show 之前调用。

        rect       —— 用户拖动框选（默认）
        window     —— 悬停高亮窗口、单击确认；window_picker 返回该窗口矩形
        fullscreen —— 直接选中整个虚拟屏幕（含多显示器）
        """
        self.capture_mode = mode if mode in ("rect", "window", "fullscreen") else "rect"
        self._window_picker = window_picker
        self.sel = None
        self.shapes.clear()
        self._selected = None
        self._hover_rect = None
        self._hover_title = ""
        self._last_pick_time = 0.0
        self._last_pick_pos = QPoint(-9999, -9999)
        if self.capture_mode == "fullscreen":
            self._apply_selection(QRect(0, 0, self.width(), self.height()))
        elif self.capture_mode == "window" and window_picker is not None:
            self._mode = "picking"
            self.update()
        else:
            if self.capture_mode == "window":
                # 没有窗口探测能力就退回框选，避免卡在 picking 无法操作
                self.capture_mode = "rect"
            self._mode = "idle"
            self.update()

    def _apply_selection(self, r: QRect, near: QPoint | None = None) -> None:
        """把矩形直接确定为选区并进入编辑态（框选 / 窗口 / 全屏共用）。

        near 为「选择结束时鼠标所在位置」（框选松开点 / 窗口点击点）。
        用于把「确定」按钮浮在鼠标附近，方便立即点选；之后不再随鼠标漂移。
        """
        r = self._clamp_to_widget(r.normalized())
        if r.width() < MIN_SELECT or r.height() < MIN_SELECT:
            self._mode = "idle"
            self.sel = None
            self.update()
            return
        self.sel = r
        self._mode = "editing"
        self._confirm_mode = True
        # 选择阶段只给「确定 / 取消」：标注等其它操作移到程序窗口里做
        self.toolbar.set_confirm_mode(True)
        self._place_toolbar(near=near)
        self.toolbar.show()
        self.toolbar.raise_()
        self.setFocus()
        self.toolbar.setFocusPolicy(Qt.NoFocus)
        self._set_tool("select")
        self.toolbar._on_tool("select")
        self.update()

    def _update_hover(self, pos: QPoint, force: bool = False) -> None:
        """窗口模式：查询鼠标下的窗口并刷新高亮。枚举窗口较贵，做 50ms 节流。"""
        if self._window_picker is None:
            return
        now = time.monotonic()
        if not force and (
            (now - self._last_pick_time) * 1000.0 < 50.0
            and (pos - self._last_pick_pos).manhattanLength() < 8
        ):
            return
        self._last_pick_time = now
        self._last_pick_pos = QPoint(pos)
        result = self._window_picker(pos)
        if isinstance(result, tuple):
            rect, title = result
        else:
            rect, title = result, ""
        if rect is not None:
            rect = self._clamp_to_widget(QRect(rect).normalized())
        if rect == self._hover_rect and (title or "") == self._hover_title:
            return
        self._hover_rect = rect
        self._hover_title = title or ""
        self.update()

    def _set_tool(self, key: str) -> None:
        self._tool = key
        # 马赛克没有可调样式：切到马赛克工具时立刻收起已打开的样式面板
        if key == "mosaic":
            self.style_panel.hide()
        if key == "text":
            cur = Qt.IBeamCursor
        elif key == "select":
            cur = Qt.SizeAllCursor if self.sel else Qt.CrossCursor
        else:
            cur = Qt.CrossCursor
        if cur != self._cursor_cache:
            self.setCursor(cur)
            self._cursor_cache = cur
        self.update()

    def undo(self) -> None:
        if self.shapes:
            self.shapes.pop()
            self._selected = None
            self.update()

    # ------------------------------------------------------------ 样式
    def _style_panel_allowed(self) -> bool:
        """马赛克不需要样式面板：马赛克工具激活或选中马赛克标注时都不显示。"""
        if getattr(self, "_tool", "") == "mosaic":
            return False
        sel = getattr(self, "_selected", None)
        return not (sel is not None and getattr(sel, "kind", "") == "mosaic")

    def _toggle_style_panel(self) -> None:
        if not self._style_panel_allowed():
            self.style_panel.hide()
            return
        if self.style_panel.isVisible():
            self.style_panel.hide()
            return
        self._refresh_style_panel()
        self._place_style_panel()
        self.style_panel.show()
        self.style_panel.raise_()

    def _refresh_style_panel(self) -> None:
        """把当前状态（选中标注优先，否则用默认值）回填到样式面板。"""
        defaults = {
            "color": self._color,
            "width": self._width,
            "font_size": self._font_size,
            "bg_color": self._bg_color,
            "bg_border": self._bg_border,
            "bg_border_color": self._bg_border_color,
            "bg_border_width": self._bg_border_width,
            "bg_border_style": self._bg_border_style,
            "line_style": self._line_style,
            "pen_arrow_start": self._pen_arrow_start,
            "pen_arrow_end": self._pen_arrow_end,
        }
        self.style_panel.set_state(self._selected, defaults)

    def _place_style_panel(self) -> None:
        if not self.sel:
            return
        self.style_panel.adjustSize()
        sp = self.style_panel.sizeHint()
        gap = 8
        # 优先放选区上方（避免与底部工具栏重叠）；上方不够就放右侧
        x = self.sel.left()
        y = self.sel.top() - sp.height() - gap
        if y < 0:
            x = self.sel.right() + gap
            y = self.sel.top()
        if x + sp.width() > self.width():
            x = self.sel.left()
            y = self.sel.bottom() + gap
        x = max(0, x)
        y = max(0, y)
        self.style_panel.setGeometry(x, y, sp.width(), sp.height())

    # ------------------------------------------------------------ 取字结果
    def _ocr_active(self) -> bool:
        """识别中 / 结果展示中：遮罩的鼠标键盘交互都让给取字层。"""
        return self.ocr_panel.isVisible() or self.ocr_layer.isVisible()

    def _place_ocr_panel(self) -> None:
        """优先放选区上方且不遮原图；空间不够依次退到右侧、下方，最后才覆盖在图上。"""
        if not self.sel:
            return
        gap = 8
        h_min = 180          # 标题 + 编辑框 + 按钮 + 内边距的最小可用高度
        sw, sh = self.width(), self.height()
        sel = self.sel.normalized()
        w = min(max(360, min(640, sel.width())), max(240, sw - 16))
        h_max = max(h_min, sh - 16)

        # 1) 选区上方：按可用空间压缩高度，保证面板完整落在原图之外
        avail = sel.top() - gap
        if avail >= h_min:
            h = min(300, avail, h_max)
            x = max(0, min(sel.left(), sw - w))
            self.ocr_panel.setGeometry(x, sel.top() - h - gap, w, h)
            return

        # 2) 右侧 → 3) 下方 → 4) 实在放不下才贴着选区浮在图上
        h = min(300, max(220, sel.height() // 2), h_max)
        if sel.right() + gap + w <= sw:
            x, y = sel.right() + gap, max(0, min(sel.top(), sh - h))
        elif sel.bottom() + gap + h <= sh:
            x, y = max(0, min(sel.left(), sw - w)), sel.bottom() + gap
        else:
            x = max(0, min(sel.left(), sw - w))
            y = max(0, min(sel.top(), sh - h))
        self.ocr_panel.setGeometry(x, y, w, h)

    def _show_ocr_panel(self) -> None:
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()

    def show_ocr_busy(self) -> None:
        """点「取字」后：收起工具条/样式面板，浮出识别中提示，遮罩保持显示。"""
        self._commit_text()
        self.toolbar.hide()
        self.style_panel.hide()
        self.ocr_layer.hide()
        self.ocr_panel.set_busy()
        self._show_ocr_panel()

    def show_ocr_lines(self, lines: list, backend: str = "") -> None:
        """方案 B：把每行文字按识别框盖回原文位置，可就地拖选 / 复制。"""
        if not self.sel:
            return
        usable = [d for d in lines if isinstance(d, dict) and d.get("box")]
        if not usable:
            # 后端没有位置信息（Windows OCR / Tesseract 兜底）时降级成整块
            # 文本面板，保证「可选取、可复制」不丢。
            self.show_ocr_result("\n".join(_reading_order(lines)), backend)
            return

        self._commit_text()
        self.toolbar.hide()
        self.style_panel.hide()
        self.ocr_panel.hide()
        sel = self.sel.normalized()
        # 覆盖层与遮罩等大；行块坐标已经是遮罩的逻辑坐标
        self.ocr_layer.setGeometry(0, 0, self.width(), self.height())
        self.ocr_layer.set_lines(lines, sel, self.dpr, backend)
        self.ocr_layer.place_bar(sel)
        self.ocr_layer.show()
        self.ocr_layer.raise_()
        self.ocr_layer.arm()
        if self._cursor_cache != Qt.ArrowCursor:
            self.setCursor(Qt.ArrowCursor)
            self._cursor_cache = Qt.ArrowCursor

    def show_ocr_result(self, text: str, backend: str = "") -> None:
        """降级路径：无坐标时用整块文本面板展示。"""
        self.ocr_layer.hide()
        self.ocr_panel.set_result(text, backend)
        self._show_ocr_panel()
        # 让 Ctrl+A / Ctrl+C 直接作用于结果文本，而不是落到遮罩上
        self.ocr_panel.focus_edit()

    def show_ocr_message(self, msg: str) -> None:
        """识别失败 / 空结果时的轻提示，不弹模态框打断截图。"""
        self.ocr_layer.hide()
        self.ocr_panel.set_message(msg)
        self._show_ocr_panel()

    def hide_ocr_panel(self) -> None:
        """复制完成 / 点关闭 / Esc：收起取字层，恢复工具条与正常编辑态。"""
        self.ocr_panel.hide()
        self.ocr_layer.hide()
        if self.sel:
            self._place_toolbar()
            self.toolbar.show()
            self.toolbar.raise_()
        if self._selected and self._style_panel_allowed():
            self._place_style_panel()
            self.style_panel.show()
            self.style_panel.raise_()
        else:
            self.style_panel.hide()
        self._set_tool(self._tool)      # 把光标从箭头改回绘制/选择态
        self.setFocus()
        self.update()

    def _apply_style(self, changes: dict) -> None:
        """样式面板的增量修改：更新当前样式，并应用到选中标注。"""
        # 先更新全局默认样式（新建标注会用这些值）
        if "color" in changes:
            self._color = QColor(changes["color"])
        if "width" in changes:
            self._width = int(changes["width"])
        if "font_size" in changes:
            self._font_size = int(changes["font_size"])
        if "line_style" in changes:
            self._line_style = changes["line_style"]
        if "bg_color" in changes:
            bg = changes["bg_color"]
            self._bg_color = QColor(bg) if bg else None
        if "bg_border" in changes:
            self._bg_border = bool(changes["bg_border"])
        if "bg_border_color" in changes:
            bc = changes["bg_border_color"]
            self._bg_border_color = QColor(bc) if bc else None
        if "bg_border_width" in changes:
            self._bg_border_width = int(changes["bg_border_width"])
        if "bg_border_style" in changes:
            self._bg_border_style = changes["bg_border_style"]
        if "pen_arrow_start" in changes:
            self._pen_arrow_start = bool(changes["pen_arrow_start"])
        if "pen_arrow_end" in changes:
            self._pen_arrow_end = bool(changes["pen_arrow_end"])

        # 应用到选中标注
        if self._selected:
            s = self._selected
            if "color" in changes:
                s.color = QColor(changes["color"])
            if "width" in changes:
                s.width = int(changes["width"])
            if "font_size" in changes:
                s.font_size = int(changes["font_size"])
            if "bold" in changes:
                s.bold = bool(changes["bold"])
            if "line_style" in changes:
                s.line_style = changes["line_style"]
            if "bg_color" in changes:
                s.bg_color = QColor(changes["bg_color"]) if changes["bg_color"] else None
            if "bg_border" in changes:
                s.bg_border = bool(changes["bg_border"])
            if "bg_border_color" in changes:
                bc = changes["bg_border_color"]
                s.bg_border_color = QColor(bc) if bc else None
            if "bg_border_width" in changes:
                s.bg_border_width = int(changes["bg_border_width"])
            if "bg_border_style" in changes:
                s.bg_border_style = changes["bg_border_style"]
            if "fill_color" in changes:
                fc = changes["fill_color"]
                s.fill_color = QColor(fc) if fc else None
            if "pen_arrow_start" in changes:
                s.pen_arrow_start = bool(changes["pen_arrow_start"])
            if "pen_arrow_end" in changes:
                s.pen_arrow_end = bool(changes["pen_arrow_end"])
            if "angle" in changes and s.kind in ROTATABLE_KINDS:
                s.angle = normalize_angle(float(changes["angle"]))
        self.update()

    def _select_shape_at(self, pos: QPoint) -> None:
        """点击选中一条标注（用于改样式）。返回是否命中。

        可旋转标注先把点击点逆变换回局部坐标，再用未旋转的包围盒判定。
        """
        for s in reversed(self.shapes):
            local = (
                shape_unrotate_point(s, pos).toPoint()
                if s.kind in ROTATABLE_KINDS else pos
            )
            if s.kind in ("rect", "ellipse") and s.rect and s.rect.adjusted(-6, -6, 6, 6).contains(local):
                self._selected = s
                self._on_select_changed()
                return True
            if s.kind == "mosaic" and s.rect and s.rect.adjusted(-6, -6, 6, 6).contains(pos):
                self._selected = s
                self._on_select_changed()
                return True
            if s.kind in ("arrow", "line") and s.start and s.end:
                # 用点到线段的距离判定命中（阈值随线宽自适应，最小 10 像素），不限制箭头长度
                hit = max(10, s.width + 6)
                if self._dist_to_segment(pos, s.start, s.end) <= hit:
                    self._selected = s
                    self._on_select_changed()
                    return True
            if s.kind == "pen" and len(s.points) >= 2:
                # 画笔：逐个线段判断，阈值随线宽自适应
                hit = max(10, s.width + 6)
                for i in range(len(s.points) - 1):
                    if self._dist_to_segment(pos, s.points[i], s.points[i + 1]) <= hit:
                        self._selected = s
                        self._on_select_changed()
                        return True
            if s.kind == "text" and s.pos:
                # 与 shape_text_box 共用同一套包围盒，旋转中心才不会和
                # 命中中心错开；外扩一圈方便点选 / 拖动。
                box = shape_text_box(s).adjusted(-8, -6, 16, 16)
                if box.contains(local):
                    self._selected = s
                    self._on_select_changed()
                    return True
        self._selected = None
        self._on_select_changed()
        return False

    @staticmethod
    def _dist_to_segment(p: QPoint, a: QPoint, b: QPoint) -> float:
        """计算点 p 到线段 ab 的距离。"""
        ax, ay = a.x(), a.y()
        bx, by = b.x(), b.y()
        px, py = p.x(), p.y()
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    @staticmethod
    def _shape_geometry(s: Shape) -> dict:
        """快照一条标注的几何属性，用于拖动时还原+平移。"""
        return {
            "rect": QRect(s.rect) if s.rect else None,
            "start": QPoint(s.start) if s.start else None,
            "end": QPoint(s.end) if s.end else None,
            "points": list(s.points) if s.points else [],
            "pos": QPoint(s.pos) if s.pos else None,
        }

    @staticmethod
    def _translate_shape(s: Shape, delta: QPoint) -> None:
        """把一条标注整体平移 delta 像素。"""
        if s.kind in ("rect", "ellipse", "mosaic") and s.rect:
            s.rect.translate(delta)
        elif s.kind in ("arrow", "line") and s.start and s.end:
            s.start += delta
            s.end += delta
        elif s.kind == "pen" and s.points:
            s.points = [p + delta for p in s.points]
        elif s.kind == "text" and s.pos:
            s.pos += delta

    @staticmethod
    def _restore_shape_geometry(s: Shape, snap: dict) -> None:
        """把标注几何还原到快照值。"""
        if snap.get("rect") is not None:
            s.rect = QRect(snap["rect"])
        if snap.get("start") is not None:
            s.start = QPoint(snap["start"])
        if snap.get("end") is not None:
            s.end = QPoint(snap["end"])
        if snap.get("points") is not None:
            s.points = list(snap["points"])
        if snap.get("pos") is not None:
            s.pos = QPoint(snap["pos"])

    def _on_select_changed(self) -> None:
        """选中标注变化后：自动弹出样式面板并回填，或隐藏。

        马赛克是纯像素化效果，没有颜色 / 线宽 / 线型可调，按需求不弹面板。
        """
        if not self._style_panel_allowed():
            self.style_panel.hide()
        elif self._selected is not None:
            # 选中了标注 → 自动打开样式面板，方便立即编辑
            self._refresh_style_panel()
            self._place_style_panel()
            self.style_panel.show()
            self.style_panel.raise_()
        self.update()

    # ------------------------------------------------------------ 选区几何
    def _normalized(self) -> QRect | None:
        if not self.sel:
            return None
        self.sel = self.sel.normalized()
        return self.sel

    def _hit_handle(self, pos: QPoint) -> str:
        r = self.sel
        if not r:
            return ""
        x, y = pos.x(), pos.y()
        hs = HANDLE_HIT
        edges = []
        if abs(x - r.left()) <= hs:
            edges.append("w")
        elif abs(x - r.right()) <= hs:
            edges.append("e")
        if abs(y - r.top()) <= hs:
            edges.append("n")
        elif abs(y - r.bottom()) <= hs:
            edges.append("s")
        if edges and r.adjusted(-hs, -hs, hs, hs).contains(pos):
            return "".join(edges)
        return ""

    def _handle_cursor(self, edge: str):
        return {
            "n": Qt.SizeVerCursor,
            "s": Qt.SizeVerCursor,
            "e": Qt.SizeHorCursor,
            "w": Qt.SizeHorCursor,
            "ne": Qt.SizeBDiagCursor,
            "sw": Qt.SizeBDiagCursor,
            "nw": Qt.SizeFDiagCursor,
            "se": Qt.SizeFDiagCursor,
        }.get(edge, None)

    # -------------------------------------------------------------- 鼠标
    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802
        """选择阶段不处理双击：标注已移到程序窗口，这里只负责选区域与「确定」。"""
        if self._ocr_active():
            return
        # 选择阶段双击无任何编辑动作（拖动选区 / 拖控制点 / 确定 才是该阶段功能）

    def _confirm(self) -> None:
        """选择阶段点「确定」/ 回车。

        普通截图：把选区（物理像素）裁剪出来，交给窗口化编辑器继续编辑。
        长截图模式：发出局部逻辑选区，由 App 换算成屏幕物理矩形后直接拼接。
        """
        self._commit_text()
        if not self.sel:
            self.cancel()
            return
        r = self.sel.normalized()
        if self.long_mode:
            if r.width() < 8 or r.height() < 8:
                return
            # 与工具条「长截图」按钮保持一致：发 Overlay 局部逻辑坐标，
            # 由 App 加上虚拟屏幕原点并乘 dpr 换算成物理像素矩形。
            self._teardown()
            self.long_shot.emit(QRect(r))
            return
        phys = self.to_phys(r).intersected(
            QRect(0, 0, self.base.width(), self.base.height())
        )
        if phys.width() < 1 or phys.height() < 1:
            self.cancel()
            return
        cropped = self.base.copy(phys)
        self._teardown()
        self.to_editor.emit(cropped, [])

    # ------------------------------------------------------------ 形状四角 / 旋转
    def _shape_corner_points(self) -> list[QPoint]:
        """当前选中的矩形 / 椭圆的四个角（旋转后的逻辑坐标）。"""
        s = self._selected
        if s is None or s.kind not in ("rect", "ellipse") or not s.rect:
            return []
        return shape_rotated_corners(s)

    def _hit_shape_corner(self, pos: QPoint) -> str:
        return shape_hit_rotated_corner(self._selected, pos)

    def _rotate_handle_dist(self) -> int:
        return ROTATE_HANDLE_DIST

    def _rotate_handle_pos(self) -> QPoint:
        s = self._selected
        if s is None or s.kind not in ROTATABLE_KINDS:
            return QPoint()
        return shape_rotate_handle_point(s, self._rotate_handle_dist())

    def _hit_rotate_handle(self, pos: QPoint) -> bool:
        s = self._selected
        if s is None or s.kind not in ROTATABLE_KINDS:
            return False
        h = self._rotate_handle_pos()
        d = QPointF(pos) - QPointF(h)
        return d.x() * d.x() + d.y() * d.y() <= ROTATE_HANDLE_HIT ** 2

    def _begin_shape_rotate(self, pos: QPoint) -> None:
        s = self._selected
        self._mode = "rotating_shape"
        self._rotating_shape = s
        self._rotate_base_angle = shape_angle(s)
        self._rotate_start_pos = QPoint(pos)
        self._rotate_center = shape_rotate_center(s)
        self.setCursor(Qt.CrossCursor)
        self._cursor_cache = Qt.CrossCursor

    def _apply_shape_rotate(self, pos: QPoint, snap: bool = False) -> None:
        s = self._rotating_shape
        if s is None:
            return
        s.angle = rotate_angle_from_drag(
            self._rotate_base_angle, self._rotate_center,
            self._rotate_start_pos, pos, snap,
        )
        self._repaint()

    # ------------------------------------------------------------ 箭头端点
    def _hit_arrow_endpoint(self, pos: QPoint, selected_only: bool = False):
        """命中箭头的起点/终点 → (shape, "start"/"end")，否则 None。"""
        if selected_only:
            candidates = [self._selected] if (
                self._selected and self._selected.kind in ("arrow", "line")
            ) else []
        else:
            # 当前选中的优先，其余按从上层到下层的顺序
            candidates = []
            if self._selected and self._selected.kind in ("arrow", "line"):
                candidates.append(self._selected)
            candidates += [
                s for s in reversed(self.shapes)
                if s.kind in ("arrow", "line") and s is not self._selected
            ]
        r2 = ARROW_HANDLE_HIT * ARROW_HANDLE_HIT
        for s in candidates:
            for which in ("start", "end"):
                pt = s.start if which == "start" else s.end
                if pt is None:
                    continue
                d = pos - pt
                if d.x() * d.x() + d.y() * d.y() <= r2:
                    return (s, which)
        return None

    def _begin_arrow_reshape(self, hit) -> None:
        """开始拉伸箭头的某一端（可改变方向与长度）。"""
        s, which = hit
        if s is not self._selected:
            self._selected = s
            self._on_select_changed()
        self._mode = "reshaping_arrow"
        self._reshape_arrow = s
        self._reshape_which = which
        cur = Qt.SizeAllCursor
        if cur != self._cursor_cache:
            self.setCursor(cur)
            self._cursor_cache = cur

    def mousePressEvent(self, ev) -> None:
        # 取字结果面板可见时，鼠标事件完全交给面板，不触发画标注/拖选区
        if self._ocr_active():
            return
        self._commit_text()
        pos = ev.position().toPoint()

        if self._mode == "picking":
            if ev.button() == Qt.RightButton:
                self.cancel()
                return
            if ev.button() == Qt.LeftButton:
                # 点击时强制重新探测，避免节流期间鼠标刚移进窗口却选中上一个
                self._update_hover(pos, force=True)
                if self._hover_rect:
                    if self.long_mode:
                        # 滚动长截图：单击窗口即开始自动滚屏，不再进入确认阶段。
                        # 发 Overlay 局部逻辑坐标，宿主会加虚拟屏原点并乘 dpr。
                        r = QRect(self._hover_rect)
                        self._teardown()
                        self.long_shot.emit(r)
                    else:
                        self._apply_selection(self._hover_rect, near=pos)
                else:
                    # 该位置没有可用窗口 → 退回手动框选
                    self.capture_mode = "rect"
                    self._mode = "idle"
                    self._hover_rect = None
                    self.update()
            return

        if ev.button() != Qt.LeftButton:
            return

        if self._mode == "editing" and self.sel:
            # 1) 当前选中箭头的两端控制柄：优先级最高，按住即可拉伸改方向。
            #    限定在选区内，避免在选区外点击（重新框选）时被误判成拉伸。
            hit = (
                self._hit_arrow_endpoint(pos, selected_only=True)
                if self.sel.contains(pos) else None
            )
            if hit:
                self._begin_arrow_reshape(hit)
                return

            # 1.4) 旋转柄（矩形 / 椭圆 / 文字）：优先于四角，通常浮在形状上方
            if self._hit_rotate_handle(pos):
                self._begin_shape_rotate(pos)
                return

            # 1.5) 选中矩形 / 椭圆的四角控制柄：优先于选区八点，
            #      形状角恰好压在选区角上时按「调形状」处理。
            corner = self._hit_shape_corner(pos) if self.sel.contains(pos) else ""
            if corner:
                self._mode = "resizing_shape"
                self._resize_shape = self._selected
                self._resize_shape_corner = corner
                self._resize_shape_base = QRect(self._selected.rect)
                self._resize_shape_center = shape_rotate_center(self._selected)
                self._resize_shape_angle = shape_angle(self._selected)
                cur = shape_corner_cursor(corner)
                if cur is not None and cur != self._cursor_cache:
                    self.setCursor(cur)
                    self._cursor_cache = cur
                return

            edge = self._hit_handle(pos)
            if edge:
                self._mode = "resizing"
                self._resize_edge = edge
                self._sel_at_drag_start = QRect(self.sel)
                return

            # 选区内点击：先尝试选中已有标注（任何工具态下都能点选标注进行编辑/拖动）
            if self.sel.contains(pos):
                # 2) 任意箭头的端点：直接选中并拉伸，不必先点一下选中
                hit = self._hit_arrow_endpoint(pos)
                if hit:
                    self._begin_arrow_reshape(hit)
                    return

                if self._select_shape_at(pos):
                    # 选中标注后进入「拖动标注」模式：用户按住拖动即可移动这条标注
                    self._mode = "dragging_shape"
                    self._drag_shape = self._selected
                    self._drag_shape_origin = pos
                    self._drag_shape_snapshot = self._shape_geometry(self._selected)
                    return

                # 没选中标注 → 在「选择」态下拖动选区；在绘图工具态下绘制新标注
                if self._tool == "select":
                    self._mode = "moving"
                    self._move_origin = pos
                    self._sel_at_drag_start = QRect(self.sel)
                    return

                start = pos
                if self._tool == "text":
                    self._begin_text(pos)
                    return
                self._draft = Shape(
                    kind=self._tool,
                    color=QColor(self._color),
                    width=self._width,
                    line_style=self._line_style,
                    pen_arrow_start=self._pen_arrow_start,
                    pen_arrow_end=self._pen_arrow_end,
                )
                if self._tool == "pen":
                    self._draft.points = [start]
                elif self._tool in ("arrow", "line"):
                    self._draft.start = start
                    self._draft.end = start
                else:
                    self._draft.rect = QRect(start, start)
                self._mode = "drawing"
                self.update()
                return

            # 点选区外：确认模式下按钮已固定在鼠标处，不要再开始新框选
            # （否则按钮会被重新定位、发生漂移）；仅恢复常态编辑才允许重选。
            if self._confirm_mode:
                return
            self._selected = None
            self.sel = QRect(pos, pos)
            self._mode = "selecting"
            self._drag_origin = pos
            self.toolbar.hide()
            self.update()
            return

        # idle 或 选区外 → 框选
        self.sel = QRect(pos, pos)
        self._mode = "selecting"
        self._drag_origin = pos
        self.toolbar.hide()
        self.update()

    def _repaint(self) -> None:
        """只重绘选区周边区域，并对连续拖动做节流，避免 paint 事件积压。"""
        if not self.sel:
            self.update()
            return
        # 脏区 = 当前选区 ∪ 拖动起始选区 ∪ 上一次画出的选区(擦残影)，
        # 外扩一圈容纳边框 / 控制点 / 尺寸标签。
        r = self.sel.normalized()
        if self._sel_at_drag_start:
            r = r.united(self._sel_at_drag_start.normalized())
        if self._last_painted_sel:
            r = r.united(self._last_painted_sel.normalized())
        pad = HANDLE_SIZE + 30
        r = r.adjusted(-pad, -pad, pad, pad).intersected(self.rect())
        if r.isEmpty():
            return
        self._dirty = r if self._dirty is None else self._dirty.united(r)

        now = time.monotonic()
        elapsed_ms = (now - self._last_repaint) * 1000.0
        if elapsed_ms >= REPAINT_INTERVAL_MS:
            self._last_repaint = now
            self.update(self._dirty)
            self._dirty = None
        elif not self._pending_repaint:
            # 被节流掉的状态不能丢：排一个单次定时器补画最终画面
            self._pending_repaint = True
            wait = max(1, int(REPAINT_INTERVAL_MS - elapsed_ms))
            QTimer.singleShot(wait, self._flush_repaint)

    def _flush_repaint(self) -> None:
        """节流后的补画：把累积脏区一次性提交，保证最终状态准确。"""
        self._pending_repaint = False
        self._last_repaint = time.monotonic()
        if self._dirty is not None:
            self.update(self._dirty)
            self._dirty = None

    def mouseMoveEvent(self, ev) -> None:
        if self._ocr_active():
            # 面板期间截图区不可交互，光标统一为常规箭头
            if self._cursor_cache != Qt.ArrowCursor:
                self.setCursor(Qt.ArrowCursor)
                self._cursor_cache = Qt.ArrowCursor
            return
        pos = ev.position().toPoint()

        if self._mode == "picking":
            self._update_hover(pos)
            return

        if self._mode == "selecting" and self._drag_origin:
            self.sel = QRect(self._drag_origin, pos).normalized()
            self._repaint()
            return

        if self._mode == "moving" and self._sel_at_drag_start and self._move_origin:
            delta = pos - self._move_origin
            r = self._sel_at_drag_start.translated(delta)
            self.sel = self._clamp_to_widget(r)
            self._place_toolbar()
            self._repaint()
            return

        if self._mode == "dragging_shape" and self._drag_shape and self._drag_shape_origin:
            # 拖动标注：还原初始几何再整体平移，避免累加误差
            self._restore_shape_geometry(self._drag_shape, self._drag_shape_snapshot)
            delta = pos - self._drag_shape_origin
            self._translate_shape(self._drag_shape, delta)
            # 标注始终在选区内，_repaint 的选区脏区足够覆盖其新旧位置
            self._repaint()
            return

        if self._mode == "reshaping_arrow" and self._reshape_arrow:
            s = self._reshape_arrow
            anchor = s.end if self._reshape_which == "start" else s.start
            if anchor is not None:
                # 端点限制在选区内（标注只在选区内渲染），并保持最小长度，
                # 允许拖过另一端以翻转箭头方向。
                r = self.sel.normalized().adjusted(1, 1, -1, -1)
                pt = QPoint(
                    max(r.left(), min(pos.x(), r.right())),
                    max(r.top(), min(pos.y(), r.bottom())),
                )
                d = pt - anchor
                if d.x() * d.x() + d.y() * d.y() >= ARROW_MIN_LEN ** 2:
                    if self._reshape_which == "start":
                        s.start = pt
                    else:
                        s.end = pt
            self._repaint()
            return

        if self._mode == "rotating_shape" and self._rotating_shape is not None:
            self._apply_shape_rotate(
                pos, snap=bool(ev.modifiers() & Qt.ShiftModifier)
            )
            return

        if (
            self._mode == "resizing_shape"
            and self._resize_shape and self._resize_shape_base
        ):
            # 角点限制在选区内（标注只在选区内渲染），其余角保持固定
            r = self.sel.normalized().adjusted(1, 1, -1, -1)
            pt = QPoint(
                max(r.left(), min(pos.x(), r.right())),
                max(r.top(), min(pos.y(), r.bottom())),
            )
            # 形状可能带旋转：把屏幕点逆变换回局部坐标再缩放，
            # 中心/角度用拖动开始时的快照，避免 rect 变化导致中心漂移。
            local = unrotate_point_about(
                pt, self._resize_shape_center, self._resize_shape_angle
            ).toPoint()
            self._resize_shape.rect = shape_resize_rect(
                self._resize_shape_base, self._resize_shape_corner, local
            )
            self._repaint()
            return

        if self._mode == "resizing" and self._sel_at_drag_start:
            self.sel = self._resize_rect(self._sel_at_drag_start, self._resize_edge, pos)
            self._place_toolbar()
            self._repaint()
            return

        if self._mode == "drawing" and self._draft:
            d = self._draft
            if d.kind == "pen":
                d.points.append(pos)
            elif d.kind in ("arrow", "line"):
                d.end = pos
            else:
                d.rect = QRect(d.rect.topLeft(), pos).normalized() if d.rect else QRect(pos, pos)
            self._repaint()
            return

        # 悬停反馈（仅当光标真的变化时才 setCursor，避免每次 move 都触发系统光标切换）
        if self._mode == "editing" and self.sel:
            corner = self._hit_shape_corner(pos) if self.sel.contains(pos) else ""
            if self.sel.contains(pos) and self._hit_arrow_endpoint(pos):
                cur = Qt.SizeAllCursor          # 箭头端点：提示可拉伸
            elif self._hit_rotate_handle(pos):
                cur = Qt.CrossCursor            # 旋转柄：提示可绕中心旋转
            elif corner:
                cur = shape_corner_cursor(corner)   # 形状四角：斜向缩放
            else:
                edge = self._hit_handle(pos)
                cur = self._handle_cursor(edge)
                if cur is None:
                    if self._tool == "select" and self.sel.contains(pos):
                        cur = Qt.SizeAllCursor
                    elif self._tool == "text":
                        cur = Qt.IBeamCursor
                    else:
                        cur = Qt.CrossCursor
            if cur != self._cursor_cache:
                self.setCursor(cur)
                self._cursor_cache = cur

    def mouseReleaseEvent(self, ev) -> None:
        pos = ev.position().toPoint()

        if self._mode == "selecting":
            r = self._normalized()
            if r and r.width() > MIN_SELECT and r.height() > MIN_SELECT:
                self._apply_selection(r, near=pos)
            else:
                self._mode = "idle"
                self.sel = None
                self.update()
            return

        if self._mode == "drawing" and self._draft:
            d = self._draft
            keep = False
            if d.kind == "pen" and len(d.points) >= 2:
                keep = True
            elif d.kind in ("arrow", "line") and d.start and d.end and (
                d.start - d.end
            ).manhattanLength() > 4:
                keep = True
            elif d.rect and d.rect.width() > 3 and d.rect.height() > 3:
                keep = True
            if keep:
                self.shapes.append(d)
                # 画完自动选中这条标注，并切回「选择」态，
                # 这样用户立刻就能点选/编辑它（而不是继续画同类型标注）。
                self._selected = d
            self._draft = None
            self._mode = "editing"
            # 切回 select（画完即回到选择/编辑状态）
            self._set_tool("select")
            self.toolbar._on_tool("select")
            if self._selected is not None:
                self._on_select_changed()
            self.update()
            return

        if self._mode in ("moving", "resizing"):
            self._mode = "editing"
            self._place_toolbar()
            self.update()

        if self._mode == "dragging_shape":
            # 结束拖动标注：保持选中，回到编辑态
            self._mode = "editing"
            self._drag_shape = None
            self._drag_shape_origin = None
            self._drag_shape_snapshot = None
            self._place_style_panel()
            self.update()

        if self._mode == "reshaping_arrow":
            # 结束拉伸端点：保持选中，回到编辑态
            self._mode = "editing"
            self._reshape_arrow = None
            self._reshape_which = ""
            self._place_style_panel()
            self.update()

        if self._mode == "rotating_shape":
            # 结束旋转：保持选中，样式面板回填新角度
            self._mode = "editing"
            self._rotating_shape = None
            self._place_style_panel()
            self.update()

        if self._mode == "resizing_shape":
            # 结束拖角缩放：保持选中，回到编辑态
            self._mode = "editing"
            self._resize_shape = None
            self._resize_shape_corner = ""
            self._resize_shape_base = None
            self._resize_shape_center = QPointF()
            self._resize_shape_angle = 0.0
            self._place_style_panel()
            self.update()

    # ------------------------------------------------------------ 选区辅助
    def _clamp_to_widget(self, r: QRect) -> QRect:
        w, h = self.width(), self.height()
        r = QRect(r)
        if r.left() < 0:
            r.moveLeft(0)
        if r.top() < 0:
            r.moveTop(0)
        if r.right() >= w:
            r.moveRight(w - 1)
        if r.bottom() >= h:
            r.moveBottom(h - 1)
        return r

    def _resize_rect(self, base: QRect, edge: str, pos: QPoint) -> QRect:
        r = QRect(base)
        if "n" in edge:
            r.setTop(pos.y())
        if "s" in edge:
            r.setBottom(pos.y())
        if "w" in edge:
            r.setLeft(pos.x())
        if "e" in edge:
            r.setRight(pos.x())
        r = r.normalized()
        if r.width() < MIN_SELECT:
            r.setWidth(MIN_SELECT)
        if r.height() < MIN_SELECT:
            r.setHeight(MIN_SELECT)
        return self._clamp_to_widget(r)

    def raw_crop(self) -> QImage:
        """选区未加标注的原始图像（物理像素），OCR 用这个更准。"""
        if not self.sel:
            return QImage()
        r = self.sel.normalized()
        phys = self.to_phys(r).intersected(
            QRect(0, 0, self.base.width(), self.base.height())
        )
        if phys.isEmpty():
            return QImage()
        return self.base.copy(phys)

    # -------------------------------------------------------------- 文字工具
    def _begin_text(self, pos: QPoint, existing: Shape | None = None) -> None:
        self._commit_text()
        e = QLineEdit(self)
        e.setStyleSheet(
            "QLineEdit { background: rgba(0,0,0,140); color: %s; "
            "border: 1px dashed #0aaeff; padding: 2px; }" % _text_edit_color(self._color)
        )
        if existing is not None:
            # 编辑已有文字：回填内容、字号、颜色，并记录被编辑对象
            e.setText(existing.text)
            e.setStyleSheet(
                "QLineEdit { background: rgba(0,0,0,140); color: %s; "
                "border: 1px dashed #0aaeff; padding: 2px; }" % _text_edit_color(existing.color)
            )
            self._editing_shape = existing
            e.move(existing.pos)
        else:
            self._editing_shape = None
            e.move(pos)
        f = e.font()
        f.setPixelSize(existing.font_size if existing else self._font_size)
        e.setFont(f)
        e.resize(300, (existing.font_size if existing else self._font_size) + 16)
        e.show()
        e.setFocus()
        e.selectAll()
        e.returnPressed.connect(self._commit_text)
        self._text_edit = e

    def _commit_text(self) -> None:
        e = self._text_edit
        if not e:
            return
        self._text_edit = None
        txt = e.text().strip()
        pos = e.pos()
        editing = getattr(self, "_editing_shape", None)
        e.deleteLater()
        if editing is not None:
            # 编辑已有文字：更新内容，若清空则删除该标注
            if txt:
                editing.text = txt
                self._selected = editing
            else:
                if editing in self.shapes:
                    self.shapes.remove(editing)
                self._selected = None
        elif txt:
            s = Shape(
                kind="text",
                text=txt,
                pos=pos,
                font_size=self._font_size,
                color=QColor(self._color),
                bg_color=QColor(self._bg_color) if self._bg_color else None,
                bg_border=bool(self._bg_border),
                bg_border_color=(QColor(self._bg_border_color)
                                 if self._bg_border_color else None),
                bg_border_width=int(self._bg_border_width),
                bg_border_style=self._bg_border_style,
                line_style=self._line_style,
            )
            self.shapes.append(s)
            self._selected = s
        self._editing_shape = None
        self.setFocus()
        # 文字提交后切回 select 态并选中刚输入的文字，便于立即编辑
        self._set_tool("select")
        self.toolbar._on_tool("select")
        if self._selected is not None:
            self._on_select_changed()
        self.update()

    # -------------------------------------------------------------- 键盘
    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        mods = ev.modifiers()
        if self._ocr_active():
            if k == Qt.Key_Escape:
                if self.ocr_panel.isVisible() and self.ocr_panel.is_busy():
                    # 识别中按 Esc = 放弃整次截图；否则结果出来后面板会自己又弹出
                    self.cancel()
                else:
                    # 结果态（逐行覆盖层或文本面板）按 Esc 只收起，回到正常截图编辑态
                    self.hide_ocr_panel()
                return
            # 面板显示期间回车不把截图直接复制走
            if k in (Qt.Key_Return, Qt.Key_Enter):
                return
            # Ctrl+A / Ctrl+C 等交给结果编辑框（焦点已在 edit 上）
            super().keyPressEvent(ev)
            return
        if self._mode == "picking":
            if k == Qt.Key_Escape:
                self.cancel()
            elif k in (Qt.Key_Return, Qt.Key_Enter) and self._hover_rect:
                if self.long_mode:
                    r = QRect(self._hover_rect)
                    self._teardown()
                    self.long_shot.emit(r)
                else:
                    self._apply_selection(self._hover_rect, near=self._last_pick_pos)
            return
        if k == Qt.Key_Escape:
            self.cancel()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        elif k == Qt.Key_Z and mods & Qt.ControlModifier:
            self.undo()
        else:
            super().keyPressEvent(ev)

    # -------------------------------------------------------------- 合成
    def compose(self) -> QImage:
        """把当前选区+标注渲染成最终图像（物理像素）。"""
        if not self.sel:
            return QImage()
        r = self.sel.normalized()
        phys = self.to_phys(r)
        phys = phys.intersected(QRect(0, 0, self.base.width(), self.base.height()))
        out = QImage(phys.size(), QImage.Format_ARGB32_Premultiplied)
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing, True)
        # 先铺底图（源矩形=物理坐标，目标=整张输出）
        p.drawImage(
            QRect(0, 0, out.width(), out.height()),
            self.base,
            phys,
        )
        # 再把标注按 dpr 缩放后画上去
        p.scale(self.dpr, self.dpr)
        p.translate(-r.x(), -r.y())
        for s in self.shapes:
            draw_shape(p, s, self.base, self.dpr)
        if self._draft:
            draw_shape(p, self._draft, self.base, self.dpr)
        p.end()
        return out

    def cancel(self) -> None:
        self._teardown()
        self.cancelled.emit()

    def _teardown(self) -> None:
        self.toolbar.hide()
        self.style_panel.hide()
        self.ocr_panel.hide()
        self.ocr_layer.hide()
        self._confirm_mode = False
        if self._text_edit:
            self._text_edit.deleteLater()
            self._text_edit = None
        self.hide()

    def hideEvent(self, ev) -> None:  # noqa: N802
        # 兜底：遮罩被隐藏时，工具条/样式面板/取字层也一定收起来
        self.toolbar.hide()
        self.style_panel.hide()
        self.ocr_panel.hide()
        self.ocr_layer.hide()
        super().hideEvent(ev)

    # -------------------------------------------------------------- 绘制
    def _place_toolbar(self, near: QPoint | None = None) -> None:
        """放置「确定/取消」工具条。

        - near 给定（选择完成瞬间）：把按钮浮在鼠标附近，方便立即点选；
          仅做「贴边收缩」保证整条按钮完整可见，不做镜像翻转，因此不会
          漂到屏幕对角角落。
        - near 为 None（选区移动 / 缩放 / 取字收起恢复）：跟随选区。
          确认模式下不允许这种重定位，保持按钮固定在鼠标处的位置不变。
        """
        if not self.sel:
            return
        self.toolbar.adjustSize()
        tb = self.toolbar.sizeHint()
        if near is not None:
            gap = 14
            x = near.x() + gap
            y = near.y() + gap
            # 贴边收缩：超出哪条边就贴哪条边，绝不镜像到对侧（避免漂到角落）
            x = min(x, self.width() - tb.width())
            y = min(y, self.height() - tb.height())
            x = max(0, x)
            y = max(0, y)
            self.toolbar.setGeometry(x, y, tb.width(), tb.height())
            return
        # 确认模式下按钮位置保持不动（鼠标点击其他位置也不会漂移）
        if self._confirm_mode:
            return
        gap = 8
        x = self.sel.left()
        y = self.sel.bottom() + gap
        if y + tb.height() > self.height():
            y = self.sel.top() - tb.height() - gap
        if y < 0:
            y = min(self.sel.bottom() - tb.height() - gap, self.height() - tb.height())
        if x + tb.width() > self.width():
            x = self.width() - tb.width()
        x = max(0, x)
        y = max(0, y)
        self.toolbar.setGeometry(x, y, tb.width(), tb.height())

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)

        # 只处理本次真正需要重绘的区域。paintEvent 里 QPainter 已自动裁剪到
        # ev.region()，把 blit 的目标/源矩形也缩到脏区，可避免整屏缩放路径。
        dirty = ev.rect().intersected(self.rect())

        # 1) 压暗底图：用「目标矩形 == 源矩形」的三参数形式做 1:1 拷贝。
        #    旧写法 drawImage(QRect(0,0,width,height), img) 在底图与窗口尺寸
        #    差 1px（高分屏取整）时会退化成整屏缩放，是拖框卡顿的主因。
        d = dirty.intersected(self.dim_logical.rect())
        if d != dirty:
            p.fillRect(dirty, QColor(0, 0, 0))
        if not d.isEmpty():
            p.drawImage(d, self.dim_logical, d)

        sel = self.sel.normalized() if self.sel else None

        if self._mode == "picking":
            # 窗口模式：只把悬停窗口恢复亮度，其余保持压暗，边框 + 标题标签
            hr = self._hover_rect
            if hr and not hr.isEmpty():
                lit = hr.intersected(self.base_logical.rect()).intersected(dirty)
                if not lit.isEmpty():
                    p.drawImage(lit, self.base_logical, lit)
                pen = QPen(BORDER_COLOR)
                pen.setWidth(2)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawRect(hr.adjusted(1, 1, -1, -1))

                label = f"{hr.width()} × {hr.height()}"
                if self._hover_title:
                    label = f"{self._hover_title}   {label}"
                p.setFont(self._label_font)
                fm = p.fontMetrics()
                tw, th = fm.horizontalAdvance(label) + 14, fm.height() + 6
                ly = hr.top() - th - 4
                if ly < 0:
                    ly = min(hr.bottom() + 4, self.height() - th - 4)
                p.setBrush(QColor(0, 0, 0, 190))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRect(hr.left(), max(0, ly), tw, th), 4, 4)
                p.setPen(QColor(255, 255, 255))
                p.drawText(QRect(hr.left(), max(0, ly), tw, th), Qt.AlignCenter, label)

            p.setFont(QFont("", 13))
            p.setPen(QColor(255, 255, 255, 220))
            hint = (
                t("单击选择要截长屏的窗口，自动向下滚屏    右键 / Esc 取消")
                if self.long_mode
                else t("窗口截图：移动鼠标到目标窗口，单击确认    右键 / Esc 取消")
            )
            p.drawText(
                self.rect().adjusted(0, 40, 0, 0),
                Qt.AlignHCenter | Qt.AlignTop,
                hint,
            )
            self._last_painted_sel = None
            p.end()
            return

        if sel and not sel.isEmpty():
            # 2) 选区恢复亮度：同样只 blit 脏区内的部分，严格 1:1
            lit = sel.intersected(self.base_logical.rect()).intersected(dirty)
            if not lit.isEmpty():
                p.drawImage(lit, self.base_logical, lit)

            # 3) 标注（只在选区内）。没有任何标注时跳过整块，省掉
            #    save/restore、抗锯齿切换与 clip 设置的每帧开销。
            if self.shapes or self._draft or self._selected:
                p.save()
                p.setRenderHint(QPainter.Antialiasing, True)
                p.setClipRect(sel)
                for s in self.shapes:
                    draw_shape(p, s, self.base, self.dpr)
                if self._draft:
                    draw_shape(p, self._draft, self.base, self.dpr)
                # 选中标注高亮虚线框
                if self._selected:
                    hl = QPen(QColor(255, 255, 0, 220))
                    hl.setStyle(Qt.DashLine)
                    hl.setWidth(1)
                    p.setPen(hl)
                    p.setBrush(Qt.NoBrush)
                    s = self._selected
                    if s.kind in ROTATABLE_KINDS:
                        # 可旋转标注：虚线框也跟着一起转
                        box = shape_rotate_rect(s)
                        if not box.isNull():
                            tf = shape_rotation_transform(s)
                            p.save()
                            if not tf.isIdentity():
                                p.setTransform(tf, True)
                            p.drawRect(box.adjusted(-4, -4, 4, 4))
                            p.restore()
                    elif s.kind == "mosaic" and s.rect:
                        p.drawRect(s.rect.adjusted(-4, -4, 4, 4))
                    elif s.kind in ("arrow", "line") and s.start and s.end:
                        # 箭头改用沿轴虚线 + 两端控制柄表示选中，不再画大矩形框
                        p.drawLine(s.start, s.end)
                p.restore()

            # 选中箭头的两端控制柄：画在选区裁剪之外，端点贴近选区边缘时
            # 也能完整看到并拖动。拖动任一端即可改变方向/长度。
            if self._selected and self._selected.kind in ("arrow", "line"):
                s = self._selected
                p.save()
                p.setRenderHint(QPainter.Antialiasing, True)
                r = ARROW_HANDLE_R
                for pt in (s.start, s.end):
                    if pt is None:
                        continue
                    p.setPen(QPen(QColor(255, 255, 255), 2))
                    p.setBrush(QBrush(BORDER_COLOR))
                    p.drawEllipse(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r))
                p.restore()

            # 选中矩形 / 椭圆的四角控制柄：同样画在裁剪之外，贴着选区
            # 边缘时也能完整看到并拖动。拖动任一角即可改宽高与形状。
            paint_shape_corner_handles(p, self._shape_corner_points())
            # 旋转柄：矩形 / 椭圆 / 文字都有，拖动即可绕中心任意旋转
            paint_shape_rotate_handle(p, self._selected, self._rotate_handle_dist())

            # 4) 边框
            pen = QPen(BORDER_COLOR)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(sel.adjusted(0, 0, -1, -1))

            if self._mode in (
                "selecting", "editing", "moving", "resizing", "drawing",
                "dragging_shape", "reshaping_arrow", "resizing_shape",
                "rotating_shape",
            ):
                # 5) 八个控制点
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(BORDER_COLOR))
                for pt in self._handle_points(sel):
                    p.drawRect(
                        QRect(
                            pt.x() - HANDLE_SIZE // 2,
                            pt.y() - HANDLE_SIZE // 2,
                            HANDLE_SIZE,
                            HANDLE_SIZE,
                        )
                    )
                # 6) 尺寸标签（字体度量按内容缓存，避免每帧重算）
                label = f"{sel.width()} × {sel.height()}"
                p.setFont(self._label_font)
                if self._label_cache is None or self._label_cache[0] != label:
                    fm = p.fontMetrics()
                    self._label_cache = (
                        label, fm.horizontalAdvance(label) + 12, fm.height() + 6,
                    )
                tw, th = self._label_cache[1], self._label_cache[2]
                ly = sel.top() - th - 4
                if ly < 0:
                    ly = sel.top() + 4
                p.setBrush(QColor(0, 0, 0, 170))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRect(sel.left(), ly, tw, th), 4, 4)
                p.setPen(QColor(255, 255, 255))
                p.drawText(QRect(sel.left(), ly, tw, th), Qt.AlignCenter, label)

        elif self._mode == "idle":
            # 没开始框选时给个提示；长截图模式说明「确定」即开始拼接
            p.setFont(QFont("", 13))
            p.setPen(QColor(255, 255, 255, 210))
            hint = (
                t("框选要滚动的区域，点「确定」开始自动拼接    Esc 取消")
                if self.long_mode
                else t("按住鼠标左键框选区域    Esc 取消")
            )
            p.drawText(
                self.rect().adjusted(0, 40, 0, 0),
                Qt.AlignHCenter | Qt.AlignTop,
                hint,
            )

        # 记录本次实际画出的选区，供下一次 _repaint 计算「擦残影」脏区
        self._last_painted_sel = QRect(sel) if sel and not sel.isEmpty() else None
        p.end()

    @staticmethod
    def _handle_points(r: QRect) -> list[QPoint]:
        cx = (r.left() + r.right()) // 2
        cy = (r.top() + r.bottom()) // 2
        return [
            QPoint(r.left(), r.top()),
            QPoint(cx, r.top()),
            QPoint(r.right(), r.top()),
            QPoint(r.right(), cy),
            QPoint(r.right(), r.bottom()),
            QPoint(cx, r.bottom()),
            QPoint(r.left(), r.bottom()),
            QPoint(r.left(), cy),
        ]
