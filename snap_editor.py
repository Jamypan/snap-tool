# -*- coding: utf-8 -*-
"""
snap_editor.py —— 窗口化截图编辑器。

「全屏截图」双击后，把整张截图缩放进一个普通程序窗口，在这里继续做标注编辑：
矩形 / 椭圆 / 箭头 / 画笔 / 马赛克 / 文字，支持选中、拖动、改样式、撤销，
也可 OCR 取字、复制到剪贴板、另存为文件。

复用 snapeditor 里的数据模型（Shape）与绘制原语（draw_shape）、浮动工具条
（Toolbar）、样式面板（StylePanel）、OCR 结果面板（OcrPanel）、逐行盖回原文的
取字层（OcrLayer），避免重复造轮子。

坐标约定：所有标注都以「物理像素图像坐标」存储（与截图原图 1:1），显示时再按
view_scale 缩放并 letterbox 居中。这样导出的图像始终是全分辨率，不丢细节。
OCR 的 bbox 也是原图物理像素，取字层按同样的视图变换铺回原文位置。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from snapeditor import (
    ARROW_HANDLE_HIT,
    ARROW_HANDLE_R,
    ARROW_MIN_LEN,
    DEFAULT_PEN,
    FONT_SIZE,
    HANDLE_SIZE,
    MIN_SELECT,
    OcrLayer,
    OcrPanel,
    PEN_WIDTH,
    pen_smooth_min_step,
    ROTATABLE_KINDS,
    ROTATE_HANDLE_DIST,
    ROTATE_HANDLE_HIT,
    SHAPE_HANDLE_HIT,
    Shape,
    StylePanel,
    Toolbar,
    _ocr_copy_text,
    _reading_order,
    _text_edit_color,
    toolbar_icon,
    text_edit_baseline_offset,
    draw_shape,
    normalize_angle,
    paint_shape_corner_handles,
    paint_shape_rotate_handle,
    rotate_angle_from_drag,
    rotate_cursor,
    shape_angle,
    shape_corner_cursor,
    shape_corner_points,
    shape_hit_corner,
    shape_resize_rect,
    shape_rotate_center,
    shape_rotate_handle_point,
    shape_rotate_point,
    shape_rotate_rect,
    shape_text_box,
    shape_rotated_bbox,
    shape_rotated_corners,
    shape_hit_rotated_corner,
    shape_unrotate_point,
    unrotate_point_about,
)
from i18n import LANG, app_name, t
from ui_theme import (
    CANVAS_BG,
    CREAM,
    FONT_QSS,
    HOVER,
    INK,
    INK2,
    INK3,
    LINE,
    ORANGE,
    SOFT,
    PillButton,
    IconButton,
    apply_shadow,
)

# 连续拖动时的重绘节流（毫秒），与 Overlay 一致
REPAINT_INTERVAL_MS = 10.0


class Canvas(QWidget):
    """窗口化编辑器的画布：缩放显示截图 + 对象化标注交互。"""

    copy_requested = Signal(QImage)
    save_requested = Signal(QImage)
    ocr_requested = Signal(QImage)
    pin_requested = Signal(QImage)    # v34 钉在桌面：当前画布结果（含标注）
    close_requested = Signal()
    zoom_changed = Signal(float)      # 当前显示比例（1.0 = 原始像素 100%）

    def __init__(self, image: QImage, shapes: list[Shape], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.ArrowCursor)   # v36：默认选择态用普通箭头

        self.base = image if not image.isNull() else QImage(800, 600, QImage.Format_RGB32)
        self.shapes: list[Shape] = [self._clone(s) for s in (shapes or [])]
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
        # 新建画笔的默认端点箭头（也可在样式面板里对选中的画笔单独改）
        self._pen_arrow_start = False
        self._pen_arrow_end = False
        self._selected: Shape | None = None

        # 撤销栈：记录「新增标注 / 整图变换」的顺序，变换另存完整快照
        self._op_stack: list[str] = []
        self._transform_snapshots: list[tuple[QImage, list[Shape]]] = []

        self._mode = "idle"  # idle | drawing | dragging_shape | reshaping_arrow
        self._drag_origin: QPoint | None = None
        self._drag_shape: Shape | None = None
        self._drag_shape_origin: QPoint | None = None
        self._drag_shape_snapshot: dict | None = None
        self._reshape_arrow: Shape | None = None
        self._reshape_which = ""
        # 选中矩形 / 椭圆后拖四角缩放
        self._resize_shape: Shape | None = None
        self._resize_shape_corner = ""               # nw / ne / se / sw
        self._resize_shape_base: QRect | None = None
        self._resize_shape_center = QPointF()        # 拖动开始时的旋转中心
        self._resize_shape_angle = 0.0              # 拖动开始时的角度
        # 拖动旋转柄旋转矩形 / 椭圆 / 文字
        self._rotating_shape: Shape | None = None
        self._rotate_base_angle = 0.0
        self._rotate_start_pos = QPoint()
        self._rotate_center = QPointF()

        # 视图变换：把物理图像坐标映射到画布像素
        self.view_scale = 1.0
        self._fit_scale = 1.0         # 「适应窗口」的基准比例
        self._zoom = 1.0              # 用户放缩倍率（相对适应窗口）
        self.off_x = 0.0
        self.off_y = 0.0
        self._pan_origin: QPoint | None = None
        self._pan_off = (0.0, 0.0)

        # 重绘节流
        self._last_repaint = 0.0
        self._pending_repaint = False
        self._dirty: QRect | None = None

        self._text_edit: QLineEdit | None = None
        self._editing_shape: Shape | None = None

        # 浮动工具条（排除"长截图"，窗口编辑器里没有滚动拼接的概念）
        self.toolbar = Toolbar(self, exclude=("长截图", "确定"))
        self.toolbar.hide()
        self.toolbar.tool_changed.connect(self._set_tool)
        self.toolbar.undo_clicked.connect(self.undo)
        self.toolbar.close_clicked.connect(self.close_requested.emit)
        self.toolbar.copy_clicked.connect(lambda: self.copy_requested.emit(self.compose()))
        self.toolbar.pin_clicked.connect(lambda: self.pin_requested.emit(self.compose()))
        self.toolbar.save_clicked.connect(lambda: self.save_requested.emit(self.compose()))
        self.toolbar.ocr_clicked.connect(lambda: self.ocr_requested.emit(self.base.copy()))
        self.toolbar.style_clicked.connect(self._toggle_style_panel)
        self.toolbar.rot_cw_clicked.connect(lambda: self.transform_image("cw"))
        self.toolbar.rot_ccw_clicked.connect(lambda: self.transform_image("ccw"))
        self.toolbar.flip_h_clicked.connect(lambda: self.transform_image("flip_h"))
        self.toolbar.flip_v_clicked.connect(lambda: self.transform_image("flip_v"))

        self.style_panel = StylePanel(self, show_pen_arrows=True)
        self.style_panel.hide()
        self.style_panel.style_changed.connect(self._apply_style)

        # 取字：逐行盖回原文位置的覆盖层 + 识别中/降级用的整块文本面板
        self.ocr_panel = OcrPanel(self)
        self.ocr_panel.hide()
        self.ocr_panel.closed.connect(self._hide_ocr_panel)
        self.ocr_layer = OcrLayer(self)
        self.ocr_layer.hide()
        self.ocr_layer.closed.connect(self._hide_ocr_panel)
        self._ocr_lines: list[dict] = []
        self._ocr_backend = ""
        self._ocr_cancelled = False     # 识别中按 Esc：忽略迟到的识别结果

        self._fit()
        self._set_tool("select")
        self.toolbar._on_tool("select")

    # ------------------------------------------------------------ 视图变换
    def set_pen_arrows(self, start: bool, end: bool) -> None:
        """设新建画笔/直线的默认端点箭头；若正选中一条画笔或直线，也同时改它。"""
        self._pen_arrow_start = bool(start)
        self._pen_arrow_end = bool(end)
        if self._selected is not None and self._selected.kind in ("pen", "line"):
            self._selected.pen_arrow_start = self._pen_arrow_start
            self._selected.pen_arrow_end = self._pen_arrow_end
        self._refresh_style_panel()
        self.update()

    def _fit(self) -> None:
        """根据当前窗口大小计算缩放与居中偏移，使整张截图恰好装下。"""
        if self.base.isNull():
            return
        pad = 24
        avail_w = max(40, self.width() - 2 * pad - self._right_inset())
        avail_h = max(40, self.height() - 2 * pad)
        iw, ih = self.base.width(), self.base.height()
        scale = min(avail_w / iw, avail_h / ih, 1.0)
        if scale <= 0:
            scale = 0.1
        self._fit_scale = scale
        self.view_scale = scale * self._zoom
        # 放大到超过窗口时保持居中（偏移可为负），配合中键拖动浏览其它区域
        self.off_x = max(pad, (self.width() - self._right_inset() - iw * self.view_scale) / 2.0)
        self.off_y = (self.height() - ih * self.view_scale) / 2.0
        self.zoom_changed.emit(self.view_scale)

    # ------------------------------------------------------------ 视图放缩
    def _set_view_scale(self, scale: float, anchor: QPoint | None = None) -> None:
        """以 anchor（屏幕坐标）为不动点设置显示比例；不影响导出分辨率。"""
        scale = max(0.05, min(16.0, float(scale)))
        if anchor is None:
            anchor = QPoint(self.width() // 2, self.height() // 2)
        ip = self._to_image(anchor)                 # 用旧比例求锚点对应的图像坐标
        self.view_scale = scale
        self._zoom = scale / max(self._fit_scale, 1e-6)
        self.off_x = anchor.x() - ip.x() * scale
        self.off_y = anchor.y() - ip.y() * scale
        if self._text_edit is not None:
            self._commit_text()                     # 编辑中的文字框不跟着缩放，先提交
        self._place_ocr_layer()                     # 取字行块按新比例重新盖回
        self.zoom_changed.emit(self.view_scale)
        self.update()

    def zoom_in(self) -> None:
        self._set_view_scale(self.view_scale * 1.25)

    def zoom_out(self) -> None:
        self._set_view_scale(self.view_scale / 1.25)

    def zoom_actual(self) -> None:
        self._set_view_scale(1.0)

    def zoom_fit(self) -> None:
        self._zoom = 1.0
        self._fit()

    def wheelEvent(self, ev) -> None:  # noqa: N802
        """Ctrl + 滚轮：以光标所在点为锚点放缩。"""
        if ev.modifiers() & Qt.ControlModifier:
            delta = ev.angleDelta().y()
            if delta:
                self._set_view_scale(
                    self.view_scale * (1.15 ** (delta / 120.0)),
                    ev.position().toPoint(),
                )
            ev.accept()
            return
        super().wheelEvent(ev)

    def _to_screen(self, ip: QPoint) -> QPoint:
        return QPoint(
            int(round(self.off_x + ip.x() * self.view_scale)),
            int(round(self.off_y + ip.y() * self.view_scale)),
        )

    def _to_image(self, sp: QPoint) -> QPoint:
        return QPoint(
            int(round((sp.x() - self.off_x) / self.view_scale)),
            int(round((sp.y() - self.off_y) / self.view_scale)),
        )

    @staticmethod
    def _clone(s: Shape) -> Shape:
        ns = Shape(kind=s.kind)
        ns.color = QColor(s.color)
        ns.width = s.width
        ns.line_style = s.line_style
        ns.text = s.text
        ns.font_size = s.font_size
        ns.bold = s.bold
        ns.bg_color = QColor(s.bg_color) if s.bg_color else None
        ns.bg_border = bool(getattr(s, "bg_border", False))
        ns.bg_border_color = (QColor(s.bg_border_color) if s.bg_border_color else None)
        ns.bg_border_width = int(getattr(s, "bg_border_width", 2))
        ns.bg_border_style = getattr(s, "bg_border_style", "solid")
        ns.fill_color = QColor(s.fill_color) if s.fill_color else None
        if s.rect is not None:
            ns.rect = QRect(s.rect)
        if s.start is not None:
            ns.start = QPoint(s.start)
        if s.end is not None:
            ns.end = QPoint(s.end)
        if s.points:
            ns.points = [QPoint(p) for p in s.points]
        if s.pos is not None:
            ns.pos = QPoint(s.pos)
        ns.pen_arrow_start = bool(getattr(s, "pen_arrow_start", False))
        ns.pen_arrow_end = bool(getattr(s, "pen_arrow_end", False))
        ns.angle = float(getattr(s, "angle", 0.0) or 0.0)
        return ns

    # ------------------------------------------------------------ 工具 / 样式
    def _set_tool(self, key: str) -> None:
        self._tool = key
        # 马赛克没有可调样式：切到马赛克工具时立刻收起已打开的样式面板
        if key == "mosaic":
            self.style_panel.hide()

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
        else:
            self._refresh_style_panel()
            self._place_style_panel()
            self.style_panel.show()
            self.style_panel.raise_()

    def _refresh_style_panel(self) -> None:
        defaults = {
            "color": QColor(self._color),
            "width": self._width,
            "line_style": self._line_style,
            "font_size": self._font_size,
            "bg_color": QColor(self._bg_color) if self._bg_color else None,
            "bg_border": self._bg_border,
            "bg_border_color": (QColor(self._bg_border_color)
                                if self._bg_border_color else None),
            "bg_border_width": self._bg_border_width,
            "bg_border_style": self._bg_border_style,
            "fill_color": None,
            "pen_arrow_start": self._pen_arrow_start,
            "pen_arrow_end": self._pen_arrow_end,
        }
        self.style_panel.set_state(self._selected, defaults)

    def _right_inset(self) -> int:
        """右侧样式面板占用的宽度（面板可见时画布要让开）。"""
        if not self.style_panel.isVisible():
            return 0
        return max(200, self.style_panel.sizeHint().width()) + 28

    def _place_style_panel(self) -> None:
        self.style_panel.adjustSize()
        sp = self.style_panel.sizeHint()
        w = max(196, min(sp.width(), max(196, self.width() // 3)))
        x = max(8, self.width() - w - 16)
        y = 16
        h = min(sp.height(), max(160, self.height() - 32))
        self.style_panel.setGeometry(x, y, w, h)

    def _apply_style(self, changes: dict) -> None:
        target = self._selected
        for key, value in changes.items():
            if target is not None:
                if key == "color":
                    target.color = QColor(value)
                elif key == "width":
                    target.width = int(value)
                elif key == "line_style":
                    target.line_style = value
                elif key == "fill_color":
                    target.fill_color = QColor(value) if value else None
                elif key == "font_size":
                    target.font_size = int(value)
                elif key == "bold":
                    target.bold = bool(value)
                elif key == "bg_color":
                    target.bg_color = QColor(value) if value else None
                elif key == "bg_border":
                    target.bg_border = bool(value)
                elif key == "bg_border_color":
                    target.bg_border_color = QColor(value) if value else None
                elif key == "bg_border_width":
                    target.bg_border_width = int(value)
                elif key == "bg_border_style":
                    target.bg_border_style = value
                elif key == "pen_arrow_start":
                    target.pen_arrow_start = bool(value)
                elif key == "pen_arrow_end":
                    target.pen_arrow_end = bool(value)
                elif key == "angle" and target.kind in ROTATABLE_KINDS:
                    target.angle = normalize_angle(float(value))
            else:
                if key == "color":
                    self._color = QColor(value)
                elif key == "width":
                    self._width = int(value)
                elif key == "line_style":
                    self._line_style = value
                elif key == "font_size":
                    self._font_size = int(value)
                elif key == "bg_color":
                    self._bg_color = QColor(value) if value else None
                elif key == "bg_border":
                    self._bg_border = bool(value)
                elif key == "bg_border_color":
                    self._bg_border_color = QColor(value) if value else None
                elif key == "bg_border_width":
                    self._bg_border_width = int(value)
                elif key == "bg_border_style":
                    self._bg_border_style = value
                elif key == "pen_arrow_start":
                    self._pen_arrow_start = bool(value)
                elif key == "pen_arrow_end":
                    self._pen_arrow_end = bool(value)
        self.update()

    def _on_select_changed(self) -> None:
        if not self._style_panel_allowed():
            # 马赛克工具 / 选中马赛克：不弹面板，已经开着的也收起
            self.style_panel.hide()
        elif self._selected is not None:
            self._refresh_style_panel()
            self._place_style_panel()
            self.style_panel.show()
            self.style_panel.raise_()
        else:
            self.style_panel.hide()
        self.update()

    def undo(self) -> None:
        if self._draft is not None:
            self._draft = None
            self._mode = "idle"
            self.update()
            return
        # 按操作顺序撤销：整图变换恢复快照，新增标注则弹掉最后一条
        op = self._op_stack.pop() if self._op_stack else "shape"
        if op == "transform":
            if self._transform_snapshots:
                base, shapes = self._transform_snapshots.pop()
                self.base = base
                self.shapes = shapes
            self._selected = None
            self.style_panel.hide()
            self._fit()
            self._place_toolbar()
            self.update()
            return
        if self.shapes:
            self._selected = None
            self.shapes.pop()
            self._on_select_changed()
        else:
            self._selected = None
            self.update()

    # ------------------------------------------------------------ 命中检测
    @staticmethod
    def _bbox(s: Shape) -> QRect | None:
        if s.kind in ("rect", "ellipse", "mosaic") and s.rect:
            return QRect(s.rect)
        if s.kind in ("arrow", "line") and s.start and s.end:
            return QRect(s.start, s.end).normalized()
        if s.kind == "pen" and len(s.points) >= 2:
            r = QRect(s.points[0], s.points[0])
            for p in s.points:
                r = r.united(QRect(p, p))
            return r
        if s.kind == "text" and s.pos:
            # 与 shape_text_box 保持一致（含 bold），旋转中心才准确
            return shape_text_box(s)
        return None

    def _select_shape_at(self, pos: QPoint) -> bool:
        for s in reversed(self.shapes):
            bb = self._bbox(s)
            if bb is None:
                continue
            local = (
                shape_unrotate_point(s, pos).toPoint()
                if s.kind in ROTATABLE_KINDS else pos
            )
            if s.kind == "text":
                if bb.contains(local):
                    self._selected = s
                    self._on_select_changed()
                    return True
                continue
            # 线条类：点到图形边界的容差命中
            tol = max(6, int(self._width / self.view_scale) + 6) if s.kind != "pen" else 6
            if s.kind in ("rect", "ellipse", "mosaic"):
                grown = bb.adjusted(-tol, -tol, tol, tol)
                if grown.contains(local):
                    self._selected = s
                    self._on_select_changed()
                    return True
            elif s.kind in ("arrow", "line"):
                if self._near_seg(pos, s.start, s.end, tol):
                    self._selected = s
                    self._on_select_changed()
                    return True
            elif s.kind == "pen":
                if self._near_any_seg(pos, s.points, tol):
                    self._selected = s
                    self._on_select_changed()
                    return True
        self._selected = None
        self._on_select_changed()
        return False

    @staticmethod
    def _dist_to_seg(p: QPoint, a: QPoint, b: QPoint) -> float:
        dx, dy = b.x() - a.x(), b.y() - a.y()
        if dx == 0 and dy == 0:
            return ((p.x() - a.x()) ** 2 + (p.y() - a.y()) ** 2) ** 0.5
        t = ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = a.x() + t * dx, a.y() + t * dy
        return ((p.x() - cx) ** 2 + (p.y() - cy) ** 2) ** 0.5

    def _near_seg(self, p: QPoint, a: QPoint, b: QPoint, tol: int) -> bool:
        return self._dist_to_seg(p, a, b) <= tol

    def _near_any_seg(self, p: QPoint, pts: list[QPoint], tol: int) -> bool:
        return any(
            self._near_seg(p, pts[i], pts[i + 1], tol) for i in range(len(pts) - 1)
        )

    def _hit_arrow_endpoint(self, pos: QPoint, selected_only: bool = False):
        cands = (
            [self._selected]
            if (selected_only and self._selected and self._selected.kind in ("arrow", "line"))
            else (
                ([self._selected] if (self._selected and self._selected.kind in ("arrow", "line")) else [])
                + [s for s in reversed(self.shapes) if s.kind in ("arrow", "line") and s is not self._selected]
            )
        )
        r2 = (ARROW_HANDLE_HIT / max(self.view_scale, 1e-3)) ** 2
        for s in cands:
            if s is None:
                continue
            for which in ("start", "end"):
                pt = s.start if which == "start" else s.end
                if pt is None:
                    continue
                d = pos - pt
                if d.x() * d.x() + d.y() * d.y() <= r2:
                    return (s, which)
        return None

    # ------------------------------------------------------------ 形状四角
    def _selected_corner_rect(self) -> QRect | None:
        """仅当选中矩形 / 椭圆时返回它的外接矩形，其它标注返回 None。"""
        s = self._selected
        if s is None or s.kind not in ("rect", "ellipse") or not s.rect:
            return None
        return s.rect.normalized()

    def _hit_shape_corner(self, pos: QPoint) -> str:
        """pos 是图像坐标；四角按旋转后的位置命中，半径按显示比例反算。"""
        hit = max(1, int(SHAPE_HANDLE_HIT / max(self.view_scale, 1e-3)))
        return shape_hit_rotated_corner(self._selected, pos, hit)

    def _shape_corner_points(self) -> list[QPoint]:
        """四角控制柄的屏幕坐标（随形状旋转，半径固定为屏幕像素）。"""
        s = self._selected
        if s is None or s.kind not in ("rect", "ellipse"):
            return []
        return [self._to_screen(pt) for pt in shape_rotated_corners(s)]

    # ---------------------------------------------------------- 形状旋转
    def _rotate_handle_dist(self) -> int:
        """旋转柄与顶边的图像坐标距离：让屏幕上的距离大致恒定。"""
        return max(18, int(round(ROTATE_HANDLE_DIST / max(self.view_scale, 0.05))))

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
        hit = ROTATE_HANDLE_HIT / max(self.view_scale, 1e-3)
        d = QPointF(pos) - QPointF(h)
        return d.x() * d.x() + d.y() * d.y() <= hit * hit

    def _begin_shape_rotate(self, pos: QPoint) -> None:
        s = self._selected
        self._mode = "rotating_shape"
        self._rotating_shape = s
        self._rotate_base_angle = shape_angle(s)
        self._rotate_start_pos = QPoint(pos)
        self._rotate_center = shape_rotate_center(s)
        self.setCursor(rotate_cursor())

    def _apply_shape_rotate(self, pos: QPoint, snap: bool = False) -> None:
        s = self._rotating_shape
        if s is None:
            return
        s.angle = rotate_angle_from_drag(
            self._rotate_base_angle, self._rotate_center,
            self._rotate_start_pos, pos, snap,
        )
        self._repaint()

    def rotate_selected(self, degrees: float) -> bool:
        """菜单 / 快捷键：把选中形状按 90° 步进旋转。"""
        s = self._selected
        if s is None or s.kind not in ROTATABLE_KINDS:
            return False
        s.angle = normalize_angle(shape_angle(s) + float(degrees))
        self._refresh_style_panel()
        self.update()
        return True

    # ------------------------------------------------------------ 几何辅助
    @staticmethod
    def _shape_geometry(s: Shape) -> dict:
        return {
            "rect": QRect(s.rect) if s.rect else None,
            "start": QPoint(s.start) if s.start else None,
            "end": QPoint(s.end) if s.end else None,
            "points": list(s.points) if s.points else [],
            "pos": QPoint(s.pos) if s.pos else None,
        }

    @staticmethod
    def _translate_shape(s: Shape, delta: QPoint) -> None:
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

    # ------------------------------------------------------------ 文字工具
    def _begin_text(self, ipos: QPoint, existing: Shape | None = None) -> None:
        self._commit_text()
        e = QLineEdit(self)
        fs = (existing.font_size if existing else self._font_size)
        e.setStyleSheet(
            "QLineEdit { background: rgba(0,0,0,160); color: %s; "
            "border: 1px dashed #0aaeff; padding: 2px; }" % (
                _text_edit_color(existing.color if existing else QColor(self._color))
            )
        )
        if existing is not None:
            e.setText(existing.text)
            self._editing_shape = existing
        else:
            self._editing_shape = None
        f = e.font()
        f.setPixelSize(max(9, int(round(fs * self.view_scale))))
        e.setFont(f)
        e.resize(300, max(20, int(round(fs * self.view_scale)) + 16))
        e.show()
        # 输入框左上角 ≠ Shape.pos（基线）：编辑已有文字时把输入框反放到
        # 原字上；旋转过的文字先将其基线点映射到旋转后坐标。
        off = text_edit_baseline_offset(e)
        if existing is not None:
            base = shape_rotate_point(existing, existing.pos)
            e.move(self._to_screen(base) - off)
        else:
            e.move(self._to_screen(ipos))
        e.setFocus()
        e.selectAll()
        e.returnPressed.connect(self._commit_text)
        self._text_edit = e

    def _commit_text(self) -> None:
        e = self._text_edit
        if e is None:
            return
        self._text_edit = None
        txt = e.text().strip()
        # e.pos() 是输入框左上角；加上「左上角→文字基线」的偏移后才是
        # Shape.pos。偏移按屏幕字号计算，_to_image 会随 view_scale 还原。
        ipos = self._to_image(e.pos() + text_edit_baseline_offset(e))
        editing = self._editing_shape
        e.deleteLater()
        if editing is not None:
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
                pos=ipos,
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
            self._op_stack.append("shape")
            self._selected = s
        self._editing_shape = None
        # v31 粘滞工具：文字提交后保持文字工具，可连续输入下一个
        if self._selected is not None:
            self._on_select_changed()
        self.setFocus()
        self.update()

    # ------------------------------------------------------------ 键盘
    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        mods = ev.modifiers()
        if self._ocr_active():
            if k == Qt.Key_Escape:
                # 识别过程中按 Esc = 放弃本次取字；迟到的结果不再弹出
                if self.ocr_panel.isVisible() and self.ocr_panel.is_busy():
                    self._ocr_cancelled = True
                self._hide_ocr_panel()
                return
            super().keyPressEvent(ev)
            return
        if k == Qt.Key_Escape:
            self.close_requested.emit()
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            self.copy_requested.emit(self.compose())
            return
        if k == Qt.Key_Z and mods & Qt.ControlModifier:
            self.undo()
            return
        if k == Qt.Key_S and mods & Qt.ControlModifier:
            self.save_requested.emit(self.compose())
            return
        super().keyPressEvent(ev)

    # ------------------------------------------------------------ 鼠标
    def mouseDoubleClickEvent(self, ev) -> None:
        if self._ocr_active():
            return
        pos = self._to_image(ev.position().toPoint())
        if ev.button() != Qt.LeftButton:
            return
        if self._selected is not None and self._selected.kind == "text":
            if self._bbox(self._selected).contains(pos):
                self._selected = self._selected
                self._on_select_changed()
                self._begin_text(pos, existing=self._selected)
                return

    def mousePressEvent(self, ev) -> None:
        if self._ocr_active():
            return
        self._commit_text()
        if ev.button() == Qt.MiddleButton:
            self._mode = "panning"
            self._pan_origin = ev.position().toPoint()
            self._pan_off = (self.off_x, self.off_y)
            self.setCursor(Qt.ClosedHandCursor)
            ev.accept()
            return
        if ev.button() == Qt.RightButton:
            # v31：右键结束当前粘滞工具，回到「选择」态（不关闭编辑器）
            if self._tool != "select":
                self._set_tool("select")
                self.toolbar._on_tool("select")
            ev.accept()
            return
        pos = self._to_image(ev.position().toPoint())
        if ev.button() != Qt.LeftButton:
            return

        # 箭头端点控制柄优先
        hit = self._hit_arrow_endpoint(pos, selected_only=self._selected is not None)
        if hit:
            self._begin_arrow_reshape(hit)
            return

        # 旋转柄（矩形 / 椭圆 / 文字）优先于四角与点选
        if self._hit_rotate_handle(pos):
            self._begin_shape_rotate(pos)
            return

        # 选中矩形 / 椭圆后，四角控制柄优先于「点选 / 拖动 / 画新图形」
        corner = self._hit_shape_corner(pos)
        if corner:
            self._mode = "resizing_shape"
            self._resize_shape = self._selected
            self._resize_shape_corner = corner
            self._resize_shape_base = QRect(self._selected.rect)
            self._resize_shape_center = shape_rotate_center(self._selected)
            self._resize_shape_angle = shape_angle(self._selected)
            self.setCursor(shape_corner_cursor(corner))
            return

        if self._tool == "select":
            if self._select_shape_at(pos):
                # 选中标注 → 进入拖动
                self._mode = "dragging_shape"
                self._drag_shape = self._selected
                self._drag_shape_origin = pos
                self._drag_shape_snapshot = self._shape_geometry(self._selected)
                return
            self._selected = None
            self._on_select_changed()
            return

        if self._tool == "text":
            self._begin_text(pos)
            return

        # 绘图工具：新建标注
        self._draft = Shape(
            kind=self._tool,
            color=QColor(self._color),
            width=self._width,
            line_style=self._line_style,
            pen_arrow_start=self._pen_arrow_start,
            pen_arrow_end=self._pen_arrow_end,
        )
        if self._tool == "pen":
            self._draft.points = [pos]
        elif self._tool in ("arrow", "line"):
            self._draft.start = pos
            self._draft.end = pos
        else:
            self._draft.rect = QRect(pos, pos)
        self._mode = "drawing"
        # v36：真正开始绘制才显示“+”，松开鼠标后回到箭头
        self.setCursor(Qt.CrossCursor)
        self.update()

    def mouseMoveEvent(self, ev) -> None:
        if self._ocr_active():
            return
        if self._mode == "panning" and self._pan_origin is not None:
            d = ev.position().toPoint() - self._pan_origin
            self.off_x = self._pan_off[0] + d.x()
            self.off_y = self._pan_off[1] + d.y()
            self._place_ocr_layer()
            self.update()
            return
        pos = self._to_image(ev.position().toPoint())

        if self._mode == "rotating_shape" and self._rotating_shape is not None:
            self._apply_shape_rotate(
                pos, snap=bool(ev.modifiers() & Qt.ShiftModifier)
            )
            return

        if (
            self._mode == "resizing_shape"
            and self._resize_shape and self._resize_shape_base
        ):
            # 角点限制在图像内，对角保持固定；用起始快照重算避免累积误差
            r = QRect(0, 0, self.base.width(), self.base.height())
            pt = QPoint(
                max(r.left(), min(pos.x(), r.right())),
                max(r.top(), min(pos.y(), r.bottom())),
            )
            # 旋转过的形状：把屏幕点逆变换回局部坐标再缩放，中心/角度用
            # 拖动开始时的快照，避免 rect 变化导致旋转中心漂移。
            local = unrotate_point_about(
                pt, self._resize_shape_center, self._resize_shape_angle
            ).toPoint()
            self._resize_shape.rect = shape_resize_rect(
                self._resize_shape_base, self._resize_shape_corner, local
            )
            self._repaint()
            return

        if self._mode == "dragging_shape" and self._drag_shape and self._drag_shape_origin:
            self._restore_shape_geometry(self._drag_shape, self._drag_shape_snapshot)
            delta = pos - self._drag_shape_origin
            self._translate_shape(self._drag_shape, delta)
            self._repaint()
            return

        if self._mode == "reshaping_arrow" and self._reshape_arrow:
            s = self._reshape_arrow
            anchor = s.end if self._reshape_which == "start" else s.start
            if anchor is not None:
                r = QRect(0, 0, self.base.width(), self.base.height())
                pt = QPoint(
                    max(r.left(), min(pos.x(), r.right())),
                    max(r.top(), min(pos.y(), r.bottom())),
                )
                d = pt - anchor
                if d.x() * d.x() + d.y() * d.y() >= (ARROW_MIN_LEN * ARROW_MIN_LEN):
                    if self._reshape_which == "start":
                        s.start = pt
                    else:
                        s.end = pt
            self._repaint()
            return

        if self._mode == "drawing" and self._draft:
            d = self._draft
            if d.kind == "pen":
                # 丢弃几乎重合的采样点；关闭平滑档时阈值为 1（不丢点），
                # 其余档配合 _smooth_polyline 的中点平滑消除锯齿
                if (not d.points
                        or (pos - d.points[-1]).manhattanLength() >= pen_smooth_min_step()):
                    d.points.append(pos)
            elif d.kind in ("arrow", "line"):
                d.end = pos
            else:
                d.rect = QRect(d.rect.topLeft(), pos).normalized() if d.rect else QRect(pos, pos)
            self._repaint()
            return

        # 悬停光标提示（v36：不画图时一律普通箭头，绘制按下时才显示“+”）
        if self._tool == "select":
            corner = self._hit_shape_corner(pos)
            if self._hit_arrow_endpoint(pos):
                self.setCursor(Qt.SizeAllCursor)
            elif self._hit_rotate_handle(pos):
                self.setCursor(rotate_cursor())   # 环形箭头：提示可旋转
            elif corner:
                self.setCursor(shape_corner_cursor(corner))
            elif self._select_shape_at_hint(pos):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        elif self._tool == "text":
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _select_shape_at_hint(self, pos: QPoint) -> bool:
        for s in reversed(self.shapes):
            bb = self._bbox(s)
            if bb is None:
                continue
            local = (
                shape_unrotate_point(s, pos).toPoint()
                if s.kind in ROTATABLE_KINDS else pos
            )
            tol = max(6, int(self._width / self.view_scale) + 6)
            if s.kind in ("rect", "ellipse", "mosaic", "text"):
                if bb.adjusted(-tol, -tol, tol, tol).contains(local):
                    return True
            elif s.kind in ("arrow", "line"):
                if self._near_seg(pos, s.start, s.end, tol):
                    return True
            elif s.kind == "pen":
                if self._near_any_seg(pos, s.points, tol):
                    return True
        return False

    def mouseReleaseEvent(self, ev) -> None:
        if self._ocr_active():
            return
        if self._mode == "panning" and ev.button() == Qt.MiddleButton:
            self._mode = "idle"
            self._pan_origin = None
            self._set_tool(self._tool)
            ev.accept()
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
                self._op_stack.append("shape")
                self._selected = d
            self._draft = None
            self._mode = "idle"
            # v36：绘制结束回到箭头光标（工具保持粘滞，悬停也是箭头）
            self.setCursor(Qt.ArrowCursor)
            # v31 粘滞工具：画完保持当前工具，可连续画同类型标注；
            # 再次点该工具 / 点别的工具 / 右键才切回「选择」态。
            if self._selected is not None:
                self._on_select_changed()
            self.update()
            return

        if self._mode == "dragging_shape":
            self._mode = "idle"
            self._drag_shape = None
            self._drag_shape_origin = None
            self._drag_shape_snapshot = None
            self._place_style_panel()
            self.update()
            return

        if self._mode == "reshaping_arrow":
            self._mode = "idle"
            self._reshape_arrow = None
            self._reshape_which = ""
            self._place_style_panel()
            self.update()
            return

        if self._mode == "rotating_shape":
            self._mode = "idle"
            self._rotating_shape = None
            self._place_style_panel()
            self.update()
            return

        if self._mode == "resizing_shape":
            self._mode = "idle"
            self._resize_shape = None
            self._resize_shape_corner = ""
            self._resize_shape_base = None
            self._resize_shape_center = QPointF()
            self._resize_shape_angle = 0.0
            self._place_style_panel()
            self.update()
            return

    def _begin_arrow_reshape(self, hit) -> None:
        s, which = hit
        if s is not self._selected:
            self._selected = s
            self._on_select_changed()
        self._mode = "reshaping_arrow"
        self._reshape_arrow = s
        self._reshape_which = which

    # ------------------------------------------------------------ 重绘节流
    def _repaint(self) -> None:
        if self.base.isNull():
            self.update()
            return
        r = self.rect()
        self._dirty = r if self._dirty is None else self._dirty.united(r)
        now = time.monotonic()
        elapsed = (now - self._last_repaint) * 1000.0
        if elapsed >= REPAINT_INTERVAL_MS:
            self._last_repaint = now
            self.update(self._dirty)
            self._dirty = None
        elif not self._pending_repaint:
            self._pending_repaint = True
            wait = max(1, int(REPAINT_INTERVAL_MS - elapsed))
            QTimer.singleShot(wait, self._flush_repaint)

    def _flush_repaint(self) -> None:
        self._pending_repaint = False
        self._last_repaint = time.monotonic()
        if self._dirty is not None:
            self.update(self._dirty)
            self._dirty = None

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(CANVAS_BG))

        if self.base.isNull():
            return

        # 图片外框：先画投影，再画底图（顺序反了投影会盖住图）
        ir = QRect(
            int(round(self.off_x)),
            int(round(self.off_y)),
            int(round(self.base.width() * self.view_scale)),
            int(round(self.base.height() * self.view_scale)),
        )
        p.save()
        p.setPen(Qt.NoPen)
        for grow, alpha in ((20, 8), (12, 12), (6, 18)):
            p.setBrush(QColor(60, 45, 30, alpha))
            p.drawRoundedRect(ir.adjusted(-grow, -grow + 10, grow, grow + 12), 12, 12)
        p.restore()

        # 截图底图（缩放、letterbox）
        p.save()
        p.translate(self.off_x, self.off_y)
        p.scale(self.view_scale, self.view_scale)
        p.drawImage(QRectF(0, 0, self.base.width(), self.base.height()), self.base)
        for s in self.shapes:
            draw_shape(p, s, self.base, 1.0)
        if self._draft:
            draw_shape(p, self._draft, self.base, 1.0)
        p.restore()

        pen = QPen(QColor("#e6e0d6"))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(ir)

        # 选中标注高亮 + 箭头端点控制柄
        if self._selected:
            bb = (
                shape_rotated_bbox(self._selected)
                if self._selected.kind in ROTATABLE_KINDS
                else self._bbox(self._selected)
            )
            if bb is not None:
                hb = QRect(
                    int(round(self.off_x + bb.x() * self.view_scale)),
                    int(round(self.off_y + bb.y() * self.view_scale)),
                    int(round(bb.width() * self.view_scale)),
                    int(round(bb.height() * self.view_scale)),
                )
                hl = QPen(QColor(255, 255, 0, 220))
                hl.setStyle(Qt.DashLine)
                hl.setWidth(1)
                p.setPen(hl)
                p.setBrush(Qt.NoBrush)
                p.drawRect(hb.adjusted(-3, -3, 3, 3))
            if self._selected.kind in ("arrow", "line"):
                s = self._selected
                r = ARROW_HANDLE_R
                for pt in (s.start, s.end):
                    if pt is None:
                        continue
                    sp = self._to_screen(pt)
                    p.setPen(QPen(QColor(255, 255, 255), 2))
                    p.setBrush(QBrush(QColor(10, 132, 255)))
                    p.drawEllipse(QRectF(sp.x() - r, sp.y() - r, 2 * r, 2 * r))

            # 选中矩形 / 椭圆的四角控制柄（屏幕像素固定大小，不随放缩变粗）
            paint_shape_corner_handles(p, self._shape_corner_points())
            # 旋转柄：矩形 / 椭圆 / 文字通用，画布放缩后仍是固定屏幕大小
            paint_shape_rotate_handle(
                p, self._selected, self._rotate_handle_dist(),
                map_point=self._to_screen,
            )

    def resizeEvent(self, ev) -> None:  # noqa: N802
        self._fit()
        self._place_toolbar()
        self._place_style_panel()
        self._place_ocr_panel()
        self._place_ocr_layer()   # 窗口缩放后，取字行块要跟着重新盖回原文位置
        super().resizeEvent(ev)

    def _place_toolbar(self) -> None:
        """底部 Dock：水平居中、离底边 16px（设计稿 .dock）。"""
        self.toolbar.adjustSize()
        tb = self.toolbar.sizeHint()
        x = max(8, (self.width() - tb.width()) // 2)
        y = max(8, self.height() - tb.height() - 16)
        self.toolbar.setGeometry(x, y, tb.width(), tb.height())

    def _place_ocr_panel(self) -> None:
        """识别中 / 降级用的整块文本面板，居中靠下（显示前也会调用）。"""
        self.ocr_panel.adjustSize()
        ow = min(self.width() - 20, self.ocr_panel.sizeHint().width())
        oh = min(self.height() - 60, self.ocr_panel.sizeHint().height())
        ow, oh = max(240, ow), max(120, oh)
        x = max(10, (self.width() - ow) // 2)
        y = max(8, self.height() - oh - 16)
        self.ocr_panel.setGeometry(x, y, ow, oh)

    # ------------------------------------------------------------ 取字
    def _ocr_active(self) -> bool:
        """识别中 / 结果展示中：画布的鼠标键盘交互让给取字层或结果面板。"""
        return self.ocr_panel.isVisible() or self.ocr_layer.isVisible()

    def _hide_ocr_panel(self) -> None:
        """复制完成 / 点返回 / Esc：收起取字层，恢复工具条与正常编辑态。"""
        self.ocr_panel.hide()
        self.ocr_layer.hide()
        self._ocr_lines = []
        self._ocr_backend = ""
        self._place_toolbar()
        self.toolbar.show()
        self.toolbar.raise_()
        self._place_style_panel()
        if self._selected is not None and self._style_panel_allowed():
            self.style_panel.show()
            self.style_panel.raise_()
        else:
            self.style_panel.hide()
        self.setCursor(Qt.ArrowCursor)   # v36：退出取字回到箭头（按工具悬停态再更新）
        self.setFocus()
        self.update()

    def _place_ocr_layer(self) -> None:
        """按当前视图缩放，把每一行文字重新盖回它在图里的位置。"""
        if not self._ocr_lines:
            return
        self.ocr_layer.setGeometry(0, 0, self.width(), self.height())
        self.ocr_layer.set_lines_view(
            self._ocr_lines, self.view_scale, self.off_x, self.off_y, self._ocr_backend
        )
        self._place_ocr_bar()

    def _place_ocr_bar(self) -> None:
        """取字工具条优先放窗口顶部；若压住文字行就改放底部。"""
        bar = self.ocr_layer.bar
        bar.adjustSize()
        hint = bar.sizeHint()
        w = max(360, min(hint.width(), self.width() - 16))
        h = max(34, hint.height())
        x = max(8, (self.width() - w) // 2)

        def overlap(y: int) -> int:
            r = QRect(x, y, w, h)
            total = 0
            for block in self.ocr_layer._blocks:
                inter = r.intersected(block.geometry())
                total += max(0, inter.width()) * max(0, inter.height())
            return total

        y = min((8, max(8, self.height() - h - 8)), key=overlap)
        bar.setGeometry(x, y, w, h)
        bar.raise_()

    def show_ocr_busy(self) -> None:
        self._ocr_cancelled = False
        self._commit_text()
        self.toolbar.hide()
        self.style_panel.hide()
        self.ocr_layer.hide()
        self.ocr_panel.set_busy()
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()

    def show_ocr_lines(self, lines: list, backend: str = "") -> None:
        """方案 B：每行文字按识别框盖回原文位置，可就地拖选 / 复制。"""
        if self._ocr_cancelled:
            return
        usable = [d for d in lines if isinstance(d, dict) and d.get("box")]
        if not usable:
            # 后端没有位置信息（Windows OCR / Tesseract 兜底）时降级成整块面板
            self.show_ocr_text(_ocr_copy_text(lines), backend)
            return
        self._commit_text()
        self.toolbar.hide()
        self.style_panel.hide()
        self.ocr_panel.hide()
        self._ocr_lines = list(lines)
        self._ocr_backend = backend
        self._place_ocr_layer()
        self.ocr_layer.show()
        self.ocr_layer.raise_()
        self.ocr_layer.arm()
        self.setCursor(Qt.ArrowCursor)

    def show_ocr_text(self, text: str, backend: str = "") -> None:
        self.ocr_layer.hide()
        self.ocr_panel.set_result(text, backend)
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()
        self.ocr_panel.focus_edit()

    def show_ocr_message(self, msg: str) -> None:
        if self._ocr_cancelled:
            return
        self.ocr_layer.hide()
        self.ocr_panel.set_message(msg)
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()

    # ------------------------------------------------------------ 整图变换
    @staticmethod
    def _map_point(pt: QPoint, mode: str, w: int, h: int) -> QPoint:
        """物理像素坐标 → 变换后坐标（w/h 为变换前的图尺寸）。"""
        x, y = pt.x(), pt.y()
        # 点/端点按像素中心换算（减 1），与 QImage 的旋转结果严格对齐；
        # 矩形另用 _map_rect 的边界换算，两者差 1px 是正常的。
        if mode == "cw":
            return QPoint(h - 1 - y, x)
        if mode == "ccw":
            return QPoint(y, w - 1 - x)
        if mode == "flip_h":
            return QPoint(w - 1 - x, y)
        return QPoint(x, h - 1 - y)                        # flip_v

    @staticmethod
    def _map_point_f(pt: QPointF, mode: str, w: int, h: int) -> QPointF:
        """浮点版坐标映射：文字包围盒中心用它换算，避免基线起点取整偏差。"""
        x, y = pt.x(), pt.y()
        if mode == "cw":
            return QPointF(h - 1 - y, x)
        if mode == "ccw":
            return QPointF(y, w - 1 - x)
        if mode == "flip_h":
            return QPointF(w - 1 - x, y)
        return QPointF(x, h - 1 - y)                    # flip_v

    @classmethod
    def _map_rect(cls, r: QRect, mode: str, w: int, h: int) -> QRect:
        """矩形随整图变换；旋转 90° 时宽高互换。"""
        x, y, rw, rh = r.x(), r.y(), r.width(), r.height()
        if mode == "cw":
            return QRect(int(round(h - y - rh)), int(round(x)), int(round(rh)), int(round(rw)))
        if mode == "ccw":
            return QRect(int(round(y)), int(round(w - x - rw)), int(round(rh)), int(round(rw)))
        if mode == "flip_h":
            return QRect(int(round(w - x - rw)), int(round(y)), int(round(rw)), int(round(rh)))
        return QRect(int(round(x)), int(round(h - y - rh)), int(round(rw)), int(round(rh)))

    def transform_image(self, mode: str) -> None:
        """整图变换：底图 + 全部标注坐标一起变，导出仍是全分辨率。

        mode: cw 顺时针 90° / ccw 逆时针 90° / flip_h 左右镜像 / flip_v 上下镜像。
        变换进撤销栈，Ctrl+Z 可恢复。文字标注跟着底图一起旋转（不再保持水平），
        矩形 / 椭圆自身的角度保持不变——它们的几何已由外接矩形映射完成旋转。
        """
        if self.base.isNull() or mode not in ("cw", "ccw", "flip_h", "flip_v"):
            return
        if self._ocr_active():
            self._hide_ocr_panel()
        self._commit_text()
        self._draft = None
        self._mode = "idle"
        self._selected = None
        self.style_panel.hide()

        w, h = self.base.width(), self.base.height()
        self._transform_snapshots.append(
            (self.base.copy(), [self._clone(s) for s in self.shapes])
        )
        self._op_stack.append("transform")

        if mode == "cw":
            tf = QTransform().rotate(90)
        elif mode == "ccw":
            tf = QTransform().rotate(-90)
        elif mode == "flip_h":
            tf = QTransform(-1, 0, 0, 1, w, 0)
        else:
            tf = QTransform(1, 0, 0, -1, 0, h)
        self.base = self.base.transformed(tf)

        for s in self.shapes:
            if s.rect is not None and s.kind in ("rect", "ellipse", "mosaic"):
                s.rect = self._map_rect(s.rect, mode, w, h)
            if s.start is not None:
                s.start = self._map_point(s.start, mode, w, h)
            if s.end is not None:
                s.end = self._map_point(s.end, mode, w, h)
            if s.points:
                s.points = [self._map_point(p, mode, w, h) for p in s.points]
            if s.pos is not None:
                if s.kind == "text":
                    # 文字：按「包围盒中心」映射，字形再跟着底图转 90°。
                    # 只搬基线起点会让旋转后的文字偏离原位置；以中心为基准
                    # 旋转不改变中心，所以映射中心 + 保持相对偏移最稳。
                    box = shape_text_box(s)
                    c = QRectF(box).center()
                    offset = QPointF(s.pos) - c
                    s.pos = (self._map_point_f(c, mode, w, h) + offset).toPoint()
                    old = shape_angle(s)
                    if mode == "cw":
                        s.angle = normalize_angle(old + 90)
                    elif mode == "ccw":
                        s.angle = normalize_angle(old - 90)
                    else:
                        # 镜像：字形不做反字（仍可读），只把方向按镜像取负
                        s.angle = normalize_angle(-old)
                else:
                    s.pos = self._map_point(s.pos, mode, w, h)
            # 马赛克缓存取自旧图，变换后必须丢弃重算
            if hasattr(s, "_mosaic_cache"):
                delattr(s, "_mosaic_cache")

        self._fit()
        self._place_toolbar()
        self.update()

    # -------------------------------------------------------------- 合成
    def compose(self) -> QImage:
        """把底图 + 标注渲染成最终图像（物理像素，与原图同分辨率）。"""
        if self.base.isNull():
            return QImage()
        out = QImage(self.base.size(), QImage.Format_ARGB32_Premultiplied)
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawImage(0, 0, self.base)
        for s in self.shapes:
            draw_shape(p, s, self.base, 1.0)
        if self._draft:
            draw_shape(p, self._draft, self.base, 1.0)
        p.end()
        return out


# ---------------------------------------------------------------------------
# 窗口化编辑器主窗口
# ---------------------------------------------------------------------------
class _TopBar(QWidget):
    """编辑器顶部工具行：按住空白处可拖动整个无边框窗口。"""

    def __init__(self, parent: QWidget, window: QWidget) -> None:
        super().__init__(parent)
        self._window = window
        self._from: QPoint | None = None
        self.setMouseTracking(True)

    def paintEvent(self, ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(CANVAS_BG))
        p.end()

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._from = ev.globalPosition().toPoint()

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._from is not None and (ev.buttons() & Qt.LeftButton):
            pos = ev.globalPosition().toPoint()
            self._window.move(self._window.pos() + (pos - self._from))
            self._from = pos

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        self._from = None

    def mouseDoubleClickEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            if self._window.isMaximized():
                self._window.showNormal()
            else:
                self._window.showMaximized()


class EditorWindow(QMainWindow):
    """无标题栏的标注编辑器：顶部工具行 + 画布 + 底部 Dock + 右侧样式浮层。"""

    copy_requested = Signal(QImage)
    save_requested = Signal(QImage)
    ocr_requested = Signal(QImage)
    pin_requested = Signal(QImage)
    closed = Signal()

    def __init__(self, image: QImage, shapes: list[Shape], save_dir, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle(t("{app} - 截图编辑", app=app_name()))
        self._save_dir = save_dir
        self._actions: dict[str, QAction] = {}
        self._menus: dict[str, QMenu] = {}
        self.setMinimumSize(680, 460)

        central = QWidget(self)
        central.setObjectName("edRoot")
        central.setStyleSheet(
            f"QWidget#edRoot {{ background:{CANVAS_BG}; }}"
            f"QMenu {{ background:#fcfbf9; border:1px solid {LINE}; border-radius:12px;"
            f" padding:6px; {FONT_QSS} }}"
            f"QMenu::item {{ padding:7px 26px 7px 12px; border-radius:8px;"
            f" color:{INK}; font-size:12.5px; }}"
            f"QMenu::item:selected {{ background:{SOFT}; color:{INK}; }}"
            f"QMenu::item:disabled {{ color:{INK3}; }}"
            f"QMenu::separator {{ height:1px; background:{LINE}; margin:5px 8px; }}"
            f"QMenu::section {{ padding:8px 12px 3px 12px; color:{INK3};"
            f" font-size:10.5px; font-weight:700; }}"
        )
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.topbar = _TopBar(central, self)
        self.topbar.setFixedHeight(54)
        outer.addWidget(self.topbar)
        self._build_topbar()

        self.canvas = Canvas(image, shapes, self)
        outer.addWidget(self.canvas, 1)

        # 画布信号向外转发到窗口级信号（App 统一处理复制 / 保存 / 取字 / 关闭）
        self.canvas.copy_requested.connect(self.copy_requested.emit)
        self.canvas.save_requested.connect(self.save_requested.emit)
        self.canvas.ocr_requested.connect(self.ocr_requested.emit)
        self.canvas.pin_requested.connect(self.pin_requested.emit)
        self.canvas.close_requested.connect(self.closed.emit)

        self._build_menu()
        self._build_hamburger()   # 仅作兼容占位，界面上不再有 ☰

        self._grip = QSizeGrip(self.canvas)
        self._grip.setFixedSize(14, 14)
        self._grip.setStyleSheet("background:transparent;")

        self.resize(1140, 760)
        self.canvas.toolbar.set_phase("dock")
        self.canvas.toolbar.show()
        self.canvas.toolbar.raise_()
        LANG.changed.connect(self.retranslate_ui)
        self._round_corners()

    # ------------------------------------------------------------ 外观
    def _round_corners(self) -> None:
        """Win11：请 DWM 给无边框窗口加圆角（失败就算了，不影响功能）。"""
        try:
            import ctypes

            hwnd = int(self.winId())
            value = ctypes.c_int(2)          # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(value), ctypes.sizeof(value)
            )
        except Exception:  # noqa: BLE001
            pass

    def _build_topbar(self) -> None:
        """v40：顶部按钮与底部 Dock 同款（纯图标），居中放在正上方。

        「保存」与「另存为」行为完全相同（都弹同一个保存对话框），
        因此去掉重复的「另存为」，只保留「保存」并放到「复制」旁边。
        右上角是最小化 / 最大化 / 关闭三个标准窗口控制。
        """
        bar = self.topbar
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(3)

        # 左侧留一段与窗口控制等宽的空白，让图标组相对整个窗口真正居中
        lay.addSpacing(118)
        lay.addStretch(1)

        def icon_btn(icon_name: str, tip: str, slot, objname: str) -> QPushButton:
            """与 Dock 完全一致的 38×38 纯图标按钮。"""
            b = QPushButton(bar)
            b.setObjectName(objname)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(tip)
            b.setIcon(toolbar_icon(icon_name))
            b.setIconSize(QSize(19, 19))
            b.setFixedSize(38, 38)
            b.setStyleSheet(
                "QPushButton{background:transparent;border:none;border-radius:13px;}"
                "QPushButton:hover{background:#f5f0e8;}"
            )
            b.clicked.connect(slot)
            return b

        # 顺序：复制 / 保存 / 钉在桌面 / 取字 / 图像变换▾ / 缩放▾
        self._top_buttons: dict[str, QPushButton] = {}
        specs = (
            ("copy", "复制", "复制到剪贴板 (Ctrl+Enter)", "复制",
             lambda _=False: self.copy_requested.emit(self.canvas.compose())),
            ("save", "保存", "另存为文件 (Ctrl+S)", "保存",
             lambda _=False: self.save_requested.emit(self.canvas.compose())),
            ("pin", "钉在桌面", "钉在桌面：把当前截图贴成可移动的浮窗", "钉在桌面",
             lambda _=False: self.pin_requested.emit(self.canvas.compose())),
            ("ocr", "取字", "识别选区文字 (OCR)", "取字",
             lambda _=False: self.ocr_requested.emit(self.canvas.base.copy())),
        )
        for key, _label, tip, icon_name, slot in specs:
            b = icon_btn(icon_name, tip, slot, f"top_{key}")
            lay.addWidget(b)
            self._top_buttons[key] = b

        # 图像变换：图标自带下拉小三角，四个动作收进一个菜单
        self.btn_transform = icon_btn(
            "变换", t("图像变换"), lambda _=False: self._show_transform_menu(),
            "topTransform",
        )
        lay.addWidget(self.btn_transform)

        # 缩放：图标自带下拉小三角，放缩四项合并进一个菜单
        self.zoom_pill = icon_btn(
            "缩放", "", lambda _=False: self._show_view_menu(), "zoomPill",
        )
        lay.addWidget(self.zoom_pill)

        lay.addStretch(1)

        # v39：标准窗口控制——最小化 / 最大化(还原) / 关闭
        self.btn_min = PillButton("—", None, "plain", bar, height=30)
        self.btn_min.setObjectName("winMin")
        self.btn_min.setFixedWidth(34)
        self.btn_min.setToolTip(t("最小化"))
        self.btn_min.clicked.connect(lambda _=False: self.showMinimized())
        lay.addWidget(self.btn_min)

        self.btn_max = PillButton("□", None, "plain", bar, height=30)
        self.btn_max.setObjectName("winMax")
        self.btn_max.setFixedWidth(34)
        self.btn_max.setToolTip(t("最大化"))
        self.btn_max.clicked.connect(lambda _=False: self._toggle_maximized())
        lay.addWidget(self.btn_max)

        # 兼容旧代码：btn_menu 仍指向一个隐藏按钮，☰ 不再出现在界面上
        self.btn_menu = QPushButton(bar)
        self.btn_menu.setVisible(False)

        # v40：关闭按钮只留一个 X——此前文字 "✕" + close 图标（也是 X）叠出两个。
        self.btn_close = PillButton("✕", None, "plain", bar, height=30)
        self.btn_close.setObjectName("winClose")
        self.btn_close.setFixedWidth(38)
        self.btn_close.setToolTip(t("关闭"))
        self.btn_close.clicked.connect(lambda _=False: self.closed.emit())
        lay.addWidget(self.btn_close)

        # btn_save 兼容引用（现在就是顶部「保存」图标按钮）
        self.btn_save = self._top_buttons["save"]

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        grip = getattr(self, "_grip", None)
        if grip is not None:
            grip.move(self.canvas.width() - 16, self.canvas.height() - 16)
            grip.raise_()

    def _show_transform_menu(self) -> None:
        """整图旋转 / 镜像四项收进一个下拉按钮。"""
        m = QMenu(self)
        for i in range(4):
            a = self._actions.get(f"transform{i}")
            if a is not None:
                m.addAction(a)
        m.exec(self.btn_transform.mapToGlobal(
            QPoint(0, self.btn_transform.height() + 4)
        ))

    def _show_view_menu(self) -> None:
        m = QMenu(self)
        for i in range(4):
            a = self._actions.get(f"view{i}")
            if a is not None:
                m.addAction(a)
        m.exec(self.zoom_pill.mapToGlobal(QPoint(0, self.zoom_pill.height() + 4)))

    def _toggle_maximized(self) -> None:
        """最大化 / 还原切换，按钮图标与提示同步。"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        mx = self.isMaximized()
        self.btn_max.setText("❐" if mx else "□")
        self.btn_max.setToolTip(t("还原") if mx else t("最大化"))

    # 菜单文案的简体中文 key，retranslate_ui 与构造共用
    _FILE_TEXTS = ("复制到剪贴板\tCtrl+Enter", "另存为…\tCtrl+S",
                   "钉在桌面", "关闭编辑器\tEsc")
    _EDIT_TEXTS = ("撤销\tCtrl+Z", "OCR 取字", "样式面板")
    _TRANSFORM_TEXTS = ("顺时针旋转 90°", "逆时针旋转 90°", "左右镜像", "上下镜像")
    # 只旋转「选中的矩形 / 椭圆 / 文字」，与上面的整图旋转区分开
    _ROTATE_TEXTS = ("顺时针旋转选中 90°", "逆时针旋转选中 90°")
    _PEN_TEXTS = ("不加箭头", "只加起点", "只加终点", "两端都加")
    _VIEW_TEXTS = ("放大", "缩小", "实际大小 1:1", "适应窗口")

    def _build_menu(self) -> None:
        mb = self.menuBar()
        mb.hide()          # 方案 E 不再显示菜单栏，命令都从左上角 ☰ 弹出
        m_file = mb.addMenu(t("文件(&F)"))
        self._menus["file"] = m_file
        for i, (text_key, slot) in enumerate(zip(self._FILE_TEXTS, (
            lambda: self.copy_requested.emit(self.canvas.compose()),
            lambda: self.save_requested.emit(self.canvas.compose()),
            lambda: self.pin_requested.emit(self.canvas.compose()),
            self.closed.emit,
        ))):
            a = QAction(t(text_key), self)
            a.triggered.connect(slot)
            if i < 3:  # v39：关闭编辑器从菜单移除，顶部已有 ✕
                m_file.addAction(a)
            self._actions[f"file{i}"] = a

        m_edit = mb.addMenu(t("编辑(&E)"))
        self._menus["edit"] = m_edit
        for i, (text_key, slot) in enumerate(zip(self._EDIT_TEXTS, (
            self.canvas.undo,
            lambda: self.ocr_requested.emit(self.canvas.base.copy()),
            self.canvas._toggle_style_panel,
        ))):
            a = QAction(t(text_key), self)
            a.triggered.connect(slot)
            if i == 1:  # v39：撤销 / 样式面板属于重复命令，已从菜单移除
                m_edit.addAction(a)
            self._actions[f"edit{i}"] = a

        # 整图变换：底图和标注一起变，可用 Ctrl+Z 撤销
        m_transform = m_edit.addMenu(t("图像变换"))
        self._menus["transform"] = m_transform
        for i, (text_key, mode, shortcut) in enumerate(zip(
            self._TRANSFORM_TEXTS,
            ("cw", "ccw", "flip_h", "flip_v"),
            ("Ctrl+R", "Ctrl+Shift+R", "Ctrl+H", "Ctrl+Shift+H"),
        )):
            a = QAction(t(text_key), self)
            a.setShortcut(shortcut)
            a.triggered.connect(lambda _=False, m=mode: self.canvas.transform_image(m))
            m_transform.addAction(a)
            self._actions[f"transform{i}"] = a

        # 形状旋转：只作用于当前选中的矩形 / 椭圆 / 文字，90° 步进
        m_rotate = QMenu(t("旋转选中形状"), self)  # v39：不挂到菜单，仅留兼容对象
        self._menus["rotate"] = m_rotate
        for i, (text_key, deg, shortcut) in enumerate(zip(
            self._ROTATE_TEXTS, (90, -90), ("Ctrl+[", "Ctrl+]"),
        )):
            a = QAction(t(text_key), self)
            a.setShortcut(shortcut)
            a.triggered.connect(
                lambda _=False, d=deg: self.canvas.rotate_selected(d)
            )
            # v39：菜单里不再出现，但动作对象保留（快捷键 / 兼容旧接口）
            m_rotate.addAction(a)
            self._actions[f"rotate{i}"] = a

        # 端点箭头：既是新建画笔/直线的默认，也作用于当前选中的画笔或直线
        m_pen = QMenu(t("端点箭头"), self)  # v39：不挂到菜单，仅留兼容对象
        self._menus["pen"] = m_pen
        for i, (text_key, st, en) in enumerate(zip(
            self._PEN_TEXTS,
            (False, True, False, True),
            (False, False, True, True),
        )):
            a = QAction(t(text_key), self)
            a.triggered.connect(
                lambda _=False, s=st, e=en: self.canvas.set_pen_arrows(s, e)
            )
            # v39：菜单里不再出现，动作对象保留（样式面板仍可勾选）
            m_pen.addAction(a)
            self._actions[f"pen{i}"] = a

        # 视图放缩：只改显示比例，导出仍是全分辨率原图
        m_view = mb.addMenu(t("视图(&V)"))
        self._menus["view"] = m_view
        _ = None
        for i, (text_key, slot, shortcut) in enumerate(zip(
            self._VIEW_TEXTS,
            (self.canvas.zoom_in, self.canvas.zoom_out,
             self.canvas.zoom_actual, self.canvas.zoom_fit),
            ("Ctrl+=", "Ctrl+-", "Ctrl+1", "Ctrl+0"),
        )):
            a = QAction(t(text_key), self)
            a.setShortcut(shortcut)
            a.triggered.connect(lambda _=False, f=slot: f())
            # v39：放缩四项合并到顶部「缩放」下拉按钮，不进菜单栏
            self._actions[f"view{i}"] = a
        self.canvas.zoom_changed.connect(self._show_zoom)
        self._show_zoom(self.canvas.view_scale)

        # 菜单栏是隐藏的，QAction 的快捷键要靠挂到窗口上才生效
        for a in self._actions.values():
            if not a.shortcut().isEmpty():
                self.addAction(a)

        LANG.changed.connect(self.retranslate_ui)

    def _build_hamburger(self) -> None:
        """把「文件 / 编辑 / 视图」三组命令平铺进一个弹出菜单（设计稿第 5 屏）。"""
        m = QMenu(self)
        for key in ("file", "edit"):   # v39：视图已合并进顶部缩放下拉按钮
            src = self._menus.get(key)
            if src is None:
                continue
            m.addSection(src.title())
            for act in src.actions():
                if act.isSeparator():
                    continue
                sub = act.menu()
                if sub is not None:
                    wrap = m.addMenu(act.text())
                    for child in sub.actions():
                        if child.isSeparator():
                            wrap.addSeparator()
                        else:
                            wrap.addAction(child)
                else:
                    m.addAction(act)
        self._hamburger = m

    def retranslate_ui(self, _code: str = "") -> None:
        self.setWindowTitle(t("{app} - 截图编辑", app=app_name()))
        self._menus["file"].setTitle(t("文件(&F)"))
        self._menus["edit"].setTitle(t("编辑(&E)"))
        self._menus["transform"].setTitle(t("图像变换"))
        self._menus["rotate"].setTitle(t("旋转选中形状"))
        self._menus["pen"].setTitle(t("端点箭头"))
        self._menus["view"].setTitle(t("视图(&V)"))
        for prefix, keys in (
            ("file", self._FILE_TEXTS), ("edit", self._EDIT_TEXTS),
            ("transform", self._TRANSFORM_TEXTS), ("pen", self._PEN_TEXTS),
            ("view", self._VIEW_TEXTS), ("rotate", self._ROTATE_TEXTS),
        ):
            for i, text_key in enumerate(keys):
                self._actions[f"{prefix}{i}"].setText(t(text_key))
        # v40：顶部是纯图标按钮，语言切换只更新提示，不再改文字
        for key, label_key in zip(("copy", "save", "pin", "ocr"),
                                   ("复制", "保存", "钉在桌面", "取字")):
            b = getattr(self, "_top_buttons", {}).get(key)
            if b is not None:
                b.setToolTip(t(label_key))
        self.btn_transform.setToolTip(t("图像变换"))
        self.btn_min.setToolTip(t("最小化"))
        self.btn_max.setToolTip(
            t("还原") if self.isMaximized() else t("最大化")
        )
        self.btn_close.setToolTip(t("关闭"))
        self._show_zoom(self.canvas.view_scale)

    def _show_zoom(self, scale: float) -> None:
        text = t("缩放 {pct}%", pct=int(round(scale * 100)))
        # v40：图标按钮不占文字位置，当前比例放到悬浮提示里
        self.zoom_pill.setToolTip(text)
        self.statusBar().showMessage(text)
        self.statusBar().hide()

    def show_ocr_busy(self) -> None:
        self.canvas.show_ocr_busy()

    def show_ocr_lines(self, lines: list, backend: str = "") -> None:
        self.canvas.show_ocr_lines(lines, backend)

    def show_ocr_text(self, text: str, backend: str = "") -> None:
        self.canvas.show_ocr_text(text, backend)

    def show_ocr_message(self, msg: str) -> None:
        self.canvas.show_ocr_message(msg)

    def closeEvent(self, ev) -> None:  # noqa: N802
        self.hide()
        self.closed.emit()
        ev.ignore()
