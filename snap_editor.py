# -*- coding: utf-8 -*-
"""
snap_editor.py —— 窗口化截图编辑器。

「全屏截图」双击后，把整张截图缩放进一个普通程序窗口，在这里继续做标注编辑：
矩形 / 椭圆 / 箭头 / 画笔 / 马赛克 / 文字，支持选中、拖动、改样式、撤销，
也可 OCR 取字、复制到剪贴板、另存为文件。

复用 snapeditor 里的数据模型（Shape）与绘制原语（draw_shape）、浮动工具条
（Toolbar）、样式面板（StylePanel）、OCR 结果面板（OcrPanel），避免重复造轮子。

坐标约定：所有标注都以「物理像素图像坐标」存储（与截图原图 1:1），显示时再按
view_scale 缩放并 letterbox 居中。这样导出的图像始终是全分辨率，不丢细节。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
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
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
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
    OcrPanel,
    PEN_WIDTH,
    Shape,
    StylePanel,
    Toolbar,
    draw_shape,
)

# 连续拖动时的重绘节流（毫秒），与 Overlay 一致
REPAINT_INTERVAL_MS = 10.0


class Canvas(QWidget):
    """窗口化编辑器的画布：缩放显示截图 + 对象化标注交互。"""

    copy_requested = Signal(QImage)
    save_requested = Signal(QImage)
    ocr_requested = Signal(QImage)
    close_requested = Signal()

    def __init__(self, image: QImage, shapes: list[Shape], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.CrossCursor)

        self.base = image if not image.isNull() else QImage(800, 600, QImage.Format_RGB32)
        self.shapes: list[Shape] = [self._clone(s) for s in (shapes or [])]
        self._draft: Shape | None = None
        self._tool = "select"

        # 当前样式：新建标注使用这些值；样式面板可实时修改
        self._color = QColor(DEFAULT_PEN)
        self._width = PEN_WIDTH
        self._font_size = FONT_SIZE
        self._bg_color: QColor | None = None
        self._line_style = "solid"
        self._selected: Shape | None = None

        self._mode = "idle"  # idle | drawing | dragging_shape | reshaping_arrow
        self._drag_origin: QPoint | None = None
        self._drag_shape: Shape | None = None
        self._drag_shape_origin: QPoint | None = None
        self._drag_shape_snapshot: dict | None = None
        self._reshape_arrow: Shape | None = None
        self._reshape_which = ""

        # 视图变换：把物理图像坐标映射到画布像素
        self.view_scale = 1.0
        self.off_x = 0
        self.off_y = 0

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
        self.toolbar.save_clicked.connect(lambda: self.save_requested.emit(self.compose()))
        self.toolbar.ocr_clicked.connect(lambda: self.ocr_requested.emit(self.base.copy()))
        self.toolbar.style_clicked.connect(self._toggle_style_panel)

        self.style_panel = StylePanel(self)
        self.style_panel.hide()
        self.style_panel.style_changed.connect(self._apply_style)

        self.ocr_panel = OcrPanel(self)
        self.ocr_panel.hide()
        self.ocr_panel.closed.connect(self._hide_ocr_panel)

        self._fit()
        self._set_tool("select")
        self.toolbar._on_tool("select")

    # ------------------------------------------------------------ 视图变换
    def _fit(self) -> None:
        """根据当前窗口大小计算缩放与居中偏移，使整张截图恰好装下。"""
        if self.base.isNull():
            return
        pad = 24
        avail_w = max(40, self.width() - 2 * pad)
        avail_h = max(40, self.height() - 2 * pad)
        iw, ih = self.base.width(), self.base.height()
        scale = min(avail_w / iw, avail_h / ih, 1.0)
        if scale <= 0:
            scale = 0.1
        self.view_scale = scale
        self.off_x = max(pad, (self.width() - iw * scale) / 2.0)
        self.off_y = max(pad, (self.height() - ih * scale) / 2.0)

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
        return ns

    # ------------------------------------------------------------ 工具 / 样式
    def _set_tool(self, key: str) -> None:
        self._tool = key

    def _toggle_style_panel(self) -> None:
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
            "fill_color": None,
        }
        self.style_panel.set_state(self._selected, defaults)

    def _place_style_panel(self) -> None:
        self.style_panel.adjustSize()
        sp = self.style_panel.sizeHint()
        x = max(8, self.width() - sp.width() - 12)
        y = 56
        self.style_panel.setGeometry(x, y, sp.width(), sp.height())

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
        self.update()

    def _on_select_changed(self) -> None:
        if self._selected is not None:
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
        if s.kind == "arrow" and s.start and s.end:
            return QRect(s.start, s.end).normalized()
        if s.kind == "pen" and len(s.points) >= 2:
            r = QRect(s.points[0], s.points[0])
            for p in s.points:
                r = r.united(QRect(p, p))
            return r
        if s.kind == "text" and s.pos:
            f = QFont()
            f.setPixelSize(s.font_size)
            fm = QFontMetrics(f)
            tw = max(40, fm.horizontalAdvance(s.text)) + 8
            th = fm.height() + 4
            top = s.pos.y() - fm.ascent() - 2
            return QRect(s.pos.x() - 4, top, tw, th)
        return None

    def _select_shape_at(self, pos: QPoint) -> bool:
        for s in reversed(self.shapes):
            bb = self._bbox(s)
            if bb is None:
                continue
            if s.kind == "text":
                if bb.contains(pos):
                    self._selected = s
                    self._on_select_changed()
                    return True
                continue
            # 线条类：点到图形边界的容差命中
            tol = max(6, int(self._width / self.view_scale) + 6) if s.kind != "pen" else 6
            if s.kind in ("rect", "ellipse", "mosaic"):
                grown = bb.adjusted(-tol, -tol, tol, tol)
                if grown.contains(pos):
                    self._selected = s
                    self._on_select_changed()
                    return True
            elif s.kind == "arrow":
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
            if (selected_only and self._selected and self._selected.kind == "arrow")
            else (
                ([self._selected] if (self._selected and self._selected.kind == "arrow") else [])
                + [s for s in reversed(self.shapes) if s.kind == "arrow" and s is not self._selected]
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
        elif s.kind == "arrow" and s.start and s.end:
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
                (existing.color if existing else QColor(self._color)).name()
            )
        )
        if existing is not None:
            e.setText(existing.text)
            self._editing_shape = existing
            e.move(self._to_screen(existing.pos))
        else:
            self._editing_shape = None
            e.move(self._to_screen(ipos))
        f = e.font()
        f.setPixelSize(max(9, int(round(fs * self.view_scale))))
        e.setFont(f)
        e.resize(300, max(20, int(round(fs * self.view_scale)) + 16))
        e.show()
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
        ipos = self._to_image(e.pos())
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
                line_style=self._line_style,
            )
            self.shapes.append(s)
            self._selected = s
        self._editing_shape = None
        self._set_tool("select")
        self.toolbar._on_tool("select")
        if self._selected is not None:
            self._on_select_changed()
        self.setFocus()
        self.update()

    # ------------------------------------------------------------ 键盘
    def keyPressEvent(self, ev) -> None:
        k = ev.key()
        mods = ev.modifiers()
        if self.ocr_panel.isVisible():
            if k == Qt.Key_Escape:
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
        if self.ocr_panel.isVisible():
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
        if self.ocr_panel.isVisible():
            return
        self._commit_text()
        pos = self._to_image(ev.position().toPoint())
        if ev.button() != Qt.LeftButton:
            return

        # 箭头端点控制柄优先
        hit = self._hit_arrow_endpoint(pos, selected_only=self._selected is not None)
        if hit:
            self._begin_arrow_reshape(hit)
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
        )
        if self._tool == "pen":
            self._draft.points = [pos]
        elif self._tool == "arrow":
            self._draft.start = pos
            self._draft.end = pos
        else:
            self._draft.rect = QRect(pos, pos)
        self._mode = "drawing"
        self.update()

    def mouseMoveEvent(self, ev) -> None:
        if self.ocr_panel.isVisible():
            return
        pos = self._to_image(ev.position().toPoint())

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
                d.points.append(pos)
            elif d.kind == "arrow":
                d.end = pos
            else:
                d.rect = QRect(d.rect.topLeft(), pos).normalized() if d.rect else QRect(pos, pos)
            self._repaint()
            return

        # 悬停光标提示
        if self._tool == "select":
            if self._hit_arrow_endpoint(pos):
                self.setCursor(Qt.SizeAllCursor)
            elif self._select_shape_at_hint(pos):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.CrossCursor)
        elif self._tool == "text":
            self.setCursor(Qt.IBeamCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def _select_shape_at_hint(self, pos: QPoint) -> bool:
        for s in reversed(self.shapes):
            bb = self._bbox(s)
            if bb is None:
                continue
            tol = max(6, int(self._width / self.view_scale) + 6)
            if s.kind in ("rect", "ellipse", "mosaic", "text"):
                if bb.adjusted(-tol, -tol, tol, tol).contains(pos):
                    return True
            elif s.kind == "arrow":
                if self._near_seg(pos, s.start, s.end, tol):
                    return True
            elif s.kind == "pen":
                if self._near_any_seg(pos, s.points, tol):
                    return True
        return False

    def mouseReleaseEvent(self, ev) -> None:
        if self._mode == "drawing" and self._draft:
            d = self._draft
            keep = False
            if d.kind == "pen" and len(d.points) >= 2:
                keep = True
            elif d.kind == "arrow" and d.start and d.end and (
                d.start - d.end
            ).manhattanLength() > 4:
                keep = True
            elif d.rect and d.rect.width() > 3 and d.rect.height() > 3:
                keep = True
            if keep:
                self.shapes.append(d)
                self._selected = d
            self._draft = None
            self._mode = "idle"
            self._set_tool("select")
            self.toolbar._on_tool("select")
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
        p.fillRect(self.rect(), QColor(28, 30, 34))

        if self.base.isNull():
            return

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

        # 图片边框
        ir = QRect(
            int(round(self.off_x)),
            int(round(self.off_y)),
            int(round(self.base.width() * self.view_scale)),
            int(round(self.base.height() * self.view_scale)),
        )
        pen = QPen(QColor(80, 84, 90))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(ir)

        # 选中标注高亮 + 箭头端点控制柄
        if self._selected:
            bb = self._bbox(self._selected)
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
            if self._selected.kind == "arrow":
                s = self._selected
                r = ARROW_HANDLE_R
                for pt in (s.start, s.end):
                    if pt is None:
                        continue
                    sp = self._to_screen(pt)
                    p.setPen(QPen(QColor(255, 255, 255), 2))
                    p.setBrush(QBrush(QColor(10, 132, 255)))
                    p.drawEllipse(QRectF(sp.x() - r, sp.y() - r, 2 * r, 2 * r))

    def resizeEvent(self, ev) -> None:  # noqa: N802
        self._fit()
        self._place_toolbar()
        self._place_style_panel()
        self._place_ocr_panel()
        super().resizeEvent(ev)

    def _place_toolbar(self) -> None:
        self.toolbar.adjustSize()
        tb = self.toolbar.sizeHint()
        x = max(8, (self.width() - tb.width()) // 2)
        self.toolbar.setGeometry(x, 8, tb.width(), tb.height())

    def _place_ocr_panel(self) -> None:
        if not self.ocr_panel.isVisible():
            return
        self.ocr_panel.adjustSize()
        ow = min(self.width() - 20, self.ocr_panel.sizeHint().width())
        oh = min(self.height() - 60, self.ocr_panel.sizeHint().height())
        x = max(10, (self.width() - ow) // 2)
        y = self.height() - oh - 16
        self.ocr_panel.setGeometry(x, y, ow, oh)

    # ------------------------------------------------------------ OCR 面板
    def _ocr_active(self) -> bool:
        return self.ocr_panel.isVisible()

    def _hide_ocr_panel(self) -> None:
        self.ocr_panel.hide()
        self._place_style_panel()
        self.update()

    def show_ocr_busy(self) -> None:
        self.ocr_panel.set_busy()
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()

    def show_ocr_text(self, text: str, backend: str = "") -> None:
        self.ocr_panel.set_result(text, backend)
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()

    def show_ocr_message(self, msg: str) -> None:
        self.ocr_panel.set_message(msg)
        self._place_ocr_panel()
        self.ocr_panel.show()
        self.ocr_panel.raise_()

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
class EditorWindow(QMainWindow):
    """双击「全屏截图」后弹出的窗口化编辑器：标题栏 + 菜单 + 画布。"""

    copy_requested = Signal(QImage)
    save_requested = Signal(QImage)
    ocr_requested = Signal(QImage)
    closed = Signal()

    def __init__(self, image: QImage, shapes: list[Shape], save_dir, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("截屏助手 - 截图编辑")
        self._save_dir = save_dir

        self.canvas = Canvas(image, shapes, self)
        self.setCentralWidget(self.canvas)

        # 画布信号向外转发到窗口级信号（App 统一处理复制 / 保存 / 取字 / 关闭）
        self.canvas.copy_requested.connect(self.copy_requested.emit)
        self.canvas.save_requested.connect(self.save_requested.emit)
        self.canvas.ocr_requested.connect(self.ocr_requested.emit)
        self.canvas.close_requested.connect(self.closed.emit)

        self._build_menu()
        self.resize(1000, 680)
        self.canvas.toolbar.show()
        self.canvas.toolbar.raise_()

    def _build_menu(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu("文件(&F)")
        for text, slot in (
            ("复制到剪贴板\tCtrl+Enter", lambda: self.copy_requested.emit(self.canvas.compose())),
            ("另存为…\tCtrl+S", lambda: self.save_requested.emit(self.canvas.compose())),
            ("关闭编辑器\tEsc", self.closed.emit),
        ):
            a = QAction(text, self)
            a.triggered.connect(slot)
            m_file.addAction(a)

        m_edit = mb.addMenu("编辑(&E)")
        for text, slot in (
            ("撤销\tCtrl+Z", self.canvas.undo),
            ("OCR 取字", lambda: self.ocr_requested.emit(self.canvas.base.copy())),
            ("样式面板", self.canvas._toggle_style_panel),
        ):
            a = QAction(text, self)
            a.triggered.connect(slot)
            m_edit.addAction(a)

    def show_ocr_busy(self) -> None:
        self.canvas.show_ocr_busy()

    def show_ocr_text(self, text: str, backend: str = "") -> None:
        self.canvas.show_ocr_text(text, backend)

    def show_ocr_message(self, msg: str) -> None:
        self.canvas.show_ocr_message(msg)

    def closeEvent(self, ev) -> None:  # noqa: N802
        self.hide()
        self.closed.emit()
        ev.ignore()
