# -*- coding: utf-8 -*-
"""
selftest_editor.py —— 截屏助手离屏自测（不需要真实屏幕 / 显示）。

覆盖「选定截图后统一进入程序窗口编辑」及退出静默这条链路的关键环节：

  Stage A  Canvas（snap_editor.py 新建的窗口编辑器画布）
    A1  视图自适应：大图在窗口内正确缩放并居中（scale<=1, offset>0）
    A2  图像↔屏幕坐标互转误差可控（取整容差 ±2px）
    A3  绘制矩形：合成鼠标事件画出矩形，形状以物理图像坐标存储
    A4  撤销：删掉刚画的矩形
    A5  样式面板：改色后选中标注颜色随之改变
    A6  合成导出：compose() 返回的图与原图同分辨率（全分辨率，不丢细节）

  Stage B  Overlay 选择确认裁剪 + 确定按钮定位（snapeditor.py）
    B1  确认裁剪：逻辑选区 ×dpr 得到物理裁剪图
    B2  确认模式：隐藏全部标注工具，只显示「确定 / 取消」
    B3  全屏(整屏)裁剪 = 整图
    B4  确定按钮浮在鼠标位置(near)；贴边收缩不镜像到对角；确认模式下点击其他位置按钮不变

  Stage C  窗口化编辑器接收
    C1  EditorWindow 持有的底图尺寸 == 原物理图尺寸
    C2  传入的物理坐标标注在编辑器中完整保留

  Stage D  退出静默（snap.py / snapui.py）
    D1  退出态主窗口安静关闭（不最小化、不弹"程序仍在运行"）
    D2  托盘通知统一出口在退出态被抑制
    D3  _on_minimized 退出态不弹提示
    D4  quit() 放行窗口关闭 / 撤托盘图标 / 退出事件循环
    D5  退出后无迟到通知、quit() 幂等

  Stage E  编辑器窗口内取字逐行盖回原文（方案 B）
    E1  识别中收起工具条、显示提示面板
    E2  结果按行生成文本框、文本一致、整块面板隐藏
    E3  行块位置 = 居中偏移 + bbox×缩放（不是堆在面板里）
    E4  窗口缩放后行块重新盖回新位置
    E5  取字态画布鼠标不误画标注
    E6  复制全部按阅读顺序拼接
    E7  Esc 收起取字层并恢复工具条
    E8  无 bbox 的后端降级为整块文本面板
    E9  收起后导出仍是全分辨率、工具条恢复
    E10 识别中按 Esc 取消本次取字，迟到的结果不弹出

用法：  python selftest_editor.py
退出码：0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import os
import sys

# 离屏渲染：必须在创建 QApplication 之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter

from snapeditor import Overlay, Shape
from snap_editor import Canvas, EditorWindow


PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, PASS if ok else FAIL, detail))
    print(f"[{PASS if ok else FAIL}] {name}  {detail}")
    return ok


# ---------------------------------------------------------------------------
# 工具：造一张纯色测试图 + 合成鼠标事件
# ---------------------------------------------------------------------------
def make_image(w: int, h: int, color=(120, 160, 220)) -> QImage:
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(*color))
    return img


def mouse_event(typ: QEvent.Type, widget, ip: QPoint) -> QMouseEvent:
    """在 widget 上造一个落点为图像坐标 ip 的鼠标事件（屏幕坐标经 _to_screen 反算）。"""
    sp = widget._to_screen(ip)
    pf = QPoint(sp.x(), sp.y())
    return QMouseEvent(typ, pf, pf, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


# ---------------------------------------------------------------------------
# Stage A — Canvas
# ---------------------------------------------------------------------------
def test_canvas() -> None:
    print("\n--- Stage A: Canvas 窗口化编辑器画布 ---")
    base = make_image(1600, 900)
    cv = Canvas(base, [], None)
    cv.resize(1000, 680)
    cv._fit()

    # A1 视图自适应
    ok_a1 = cv.view_scale <= 1.0 and cv.view_scale > 0.3 and cv.off_x > 0 and cv.off_y > 0
    record(
        "A1 视图自适应缩放居中",
        ok_a1,
        f"scale={cv.view_scale:.3f} off=({cv.off_x:.1f},{cv.off_y:.1f})",
    )

    # A2 坐标互转容差（取若干采样点）
    errs = []
    for sx in (0, 400, 800, 1599):
        for sy in (0, 450, 899):
            img_p = QPoint(sx, sy)
            back = cv._to_image(cv._to_screen(img_p))
            errs.append((back.x() - sx, back.y() - sy))
    max_dx = max(abs(e[0]) for e in errs)
    max_dy = max(abs(e[1]) for e in errs)
    ok_a2 = max_dx <= 2 and max_dy <= 2
    record("A2 坐标互转容差 ≤2px", ok_a2, f"max_dx={max_dx} max_dy={max_dy}")

    # A3 绘制矩形（图像坐标 200,150 → 400,300）
    cv._set_tool("rect")
    cv.toolbar._on_tool("rect")
    e1 = mouse_event(QEvent.Type.MouseButtonPress, cv, QPoint(200, 150))
    cv.mousePressEvent(e1)
    e2 = mouse_event(QEvent.Type.MouseMove, cv, QPoint(400, 300))
    cv.mouseMoveEvent(e2)
    e3 = mouse_event(QEvent.Type.MouseButtonRelease, cv, QPoint(400, 300))
    cv.mouseReleaseEvent(e3)

    ok_drawn = len(cv.shapes) == 1 and cv.shapes[0].kind == "rect"
    r = cv.shapes[0].rect if ok_drawn else QRect()
    ok_rect = (
        ok_drawn
        and abs(r.x() - 200) <= 2
        and abs(r.y() - 150) <= 2
        and abs(r.width() - 200) <= 2
        and abs(r.height() - 150) <= 2
    )
    record(
        "A3 绘制矩形(物理图像坐标)",
        ok_rect,
        f"rect=({r.x()},{r.y()},{r.width()},{r.height()}) 期望≈(200,150,200,150)",
    )

    # A4 撤销
    cv.undo()
    ok_a4 = len(cv.shapes) == 0
    record("A4 撤销删除矩形", ok_a4, f"剩余 shapes={len(cv.shapes)}")

    # A5 样式面板改色
    cv._set_tool("rect")
    e1 = mouse_event(QEvent.Type.MouseButtonPress, cv, QPoint(200, 150))
    cv.mousePressEvent(e1)
    e2 = mouse_event(QEvent.Type.MouseMove, cv, QPoint(400, 300))
    cv.mouseMoveEvent(e2)
    e3 = mouse_event(QEvent.Type.MouseButtonRelease, cv, QPoint(400, 300))
    cv.mouseReleaseEvent(e3)
    ok_has = len(cv.shapes) == 1
    # 选中并改色
    sel = cv.shapes[0]
    cv._selected = sel
    cv._apply_style({"color": QColor(255, 0, 0)})
    ok_a5 = ok_has and sel.color.red() == 255 and sel.color.green() == 0 and sel.color.blue() == 0
    record("A5 样式面板改色生效", ok_a5, f"color={sel.color.red()},{sel.color.green()},{sel.color.blue()}")

    # A6 合成导出同分辨率
    out = cv.compose()
    ok_a6 = out.width() == base.width() and out.height() == base.height()
    record("A6 compose 全分辨率导出", ok_a6, f"out={out.width()}x{out.height()} base={base.width()}x{base.height()}")


# ---------------------------------------------------------------------------
# Stage B — Overlay 选择→确认→裁剪
# ---------------------------------------------------------------------------
def test_overlay() -> None:
    print("\n--- Stage B: Overlay 选择确认裁剪 ---")
    base = make_image(400, 200)  # 物理原图，dpr=2 → 逻辑 200x100
    ov = Overlay(base, dpr=2.0)
    ov.resize(200, 100)

    # B1 确认裁剪：逻辑选区 (50,40,60,30) → 物理 (100,80,120,60)
    ov.shapes = []
    ov.sel = QRect(50, 40, 60, 30)
    ov._mode = "editing"
    captured: dict = {}
    ov.to_editor.connect(lambda b, sh: captured.setdefault("d", (b, sh)))
    ov._confirm()
    b_img, b_shapes = captured.get("d", (None, None))
    expect = base.copy(QRect(100, 80, 120, 60))
    ok_b1 = (
        b_img is not None
        and b_img.size() == expect.size()
        and b_shapes == []
        and b_img.pixel(0, 0) == base.pixel(100, 80)
        and b_img.pixel(119, 59) == base.pixel(219, 139)
    )
    record(
        "B1 确认裁剪到选区(物理)",
        ok_b1,
        f"size={b_img.size() if b_img else None} 期望={expect.size()}",
    )

    # B2 确认模式：隐藏全部标注工具，只显示「确定 / 取消」
    ov2 = Overlay(base, dpr=2.0)
    ov2.resize(200, 100)
    ov2.toolbar.set_confirm_mode(True)
    ov2.show()               # 让父链可见，isVisible() 才能反映按钮自身状态
    ov2.toolbar.show()
    tools_hidden = all(not b.isVisible() for b in ov2.toolbar._buttons.values())
    ok_b2 = (
        tools_hidden
        and ov2.toolbar._actions["确定"].isVisible()
        and ov2.toolbar._actions["✕"].isVisible()
        and not ov2.toolbar._actions["撤销"].isVisible()
        and not ov2.toolbar._actions["取字"].isVisible()
    )
    record(
        "B2 确认模式只留确定/取消",
        ok_b2,
        f"tools_hidden={tools_hidden} 确定={ov2.toolbar._actions['确定'].isVisible()} 取消={ov2.toolbar._actions['✕'].isVisible()}",
    )

    # B3 全屏直开等价：sel=整屏 → 裁剪=整图
    ov3 = Overlay(base, dpr=2.0)
    ov3.resize(200, 100)
    ov3.shapes = []
    ov3.sel = QRect(0, 0, 200, 100)
    ov3._mode = "editing"
    cap3: dict = {}
    ov3.to_editor.connect(lambda b, sh: cap3.setdefault("d", (b, sh)))
    ov3._confirm()
    b3, _ = cap3.get("d", (None, None))
    ok_b3 = b3 is not None and b3.size() == base.size() and b3.pixel(0, 0) == base.pixel(0, 0)
    record("B3 全屏(整屏)裁剪=整图", ok_b3, f"size={b3.size() if b3 else None} base={base.size()}")

    # B4 确定按钮浮在鼠标位置（near）；贴边收缩而非镜像到对角；确认后位置固定
    ov4 = Overlay(base, dpr=2.0)
    ov4.resize(200, 100)
    ov4.toolbar.set_confirm_mode(True)
    ov4.sel = QRect(50, 40, 60, 30)   # sel 仅用于早退出判断；near 决定位置

    # B4a near 在屏内且离边足够远 → 工具条落在光标右下方(near+14,+14)
    ov4._place_toolbar(near=QPoint(20, 20))
    g = ov4.toolbar.geometry()
    ok_b4a = (
        g.x() == 20 + 14
        and g.y() == 20 + 14
        and g.x() >= 0 and g.y() >= 0
        and (g.x() + g.width()) <= 200
        and (g.y() + g.height()) <= 100
    )
    record(
        "B4a 确定按钮浮在鼠标右下方",
        ok_b4a,
        f"geom=({g.x()},{g.y()},{g.width()},{g.height()}) 期望x=34 y=34",
    )

    # B4b near 贴近右下角 → 贴边收缩，绝不镜像到左上角（不会漂到屏幕角落）
    ov4._place_toolbar(near=QPoint(196, 96))
    g2 = ov4.toolbar.geometry()
    ok_b4b = (
        (g2.x() + g2.width()) == 200           # 右贴边
        and (g2.y() + g2.height()) == 100       # 底贴边
        and g2.x() >= 0 and g2.y() >= 0
        and not (g2.x() == 196 - g2.width() - 14)   # 没有镜像到光标左上方
    )
    record(
        "B4b 贴边收缩不镜像到对角",
        ok_b4b,
        f"geom=({g2.x()},{g2.y()},{g2.width()},{g2.height()}) 期望右/底贴边,非镜像",
    )

    # B4c 选择完成时 _apply_selection(near) 直接把按钮放到鼠标处并进入确认模式
    #     near=(70,40)：右下方都有足够空间，不会触发贴边收缩
    ov4.sel = QRect(50, 40, 60, 30)
    ov4._apply_selection(QRect(50, 40, 60, 30), near=QPoint(70, 40))
    g3 = ov4.toolbar.geometry()
    ok_b4c = (
        ov4._confirm_mode is True
        and g3.x() == 70 + 14
        and g3.y() == 40 + 14
        and (g3.x() + g3.width()) <= 200
        and (g3.y() + g3.height()) <= 100
    )
    record(
        "B4c _apply_selection 放置到鼠标处并确认",
        ok_b4c,
        f"geom=({g3.x()},{g3.y()},{g3.width()},{g3.height()}) confirm={ov4._confirm_mode}",
    )

    # B4d 确认模式下再次调用 _place_toolbar()（模拟点击其他位置/移动选区）按钮位置不变
    g_before = ov4.toolbar.geometry()
    ov4._place_toolbar()                       # 无 near，确认模式应跳过重定位
    g_after = ov4.toolbar.geometry()
    ok_b4d = (g_before == g_after)
    record(
        "B4d 确认后点击其他位置按钮不变",
        ok_b4d,
        f"before=({g_before.x()},{g_before.y()}) after=({g_after.x()},{g_after.y()})",
    )


# ---------------------------------------------------------------------------
# Stage C — EditorWindow 接收裁剪图并继续编辑
# ---------------------------------------------------------------------------
def test_editor_window() -> None:
    print("\n--- Stage C: EditorWindow 接收裁剪图并继续编辑 ---")
    base = make_image(1600, 900)
    # 模拟「框选确认」交出的裁剪图（这里以整图等价演示：接收 + 再编辑）
    ed = EditorWindow(base, [], None)  # save_dir=None 仅自测
    ed.resize(1000, 680)
    ed.canvas._fit()

    # C1 底图尺寸一致
    ok_c1 = ed.canvas.base.size() == base.size()
    record("C1 编辑器底图尺寸一致", ok_c1, f"canvas={ed.canvas.base.size()} base={base.size()}")

    # C2 在编辑器里继续标注（画一个矩形，物理图像坐标）
    ed.canvas._set_tool("rect")
    ed.canvas.toolbar._on_tool("rect")
    e1 = mouse_event(QEvent.Type.MouseButtonPress, ed.canvas, QPoint(200, 150))
    ed.canvas.mousePressEvent(e1)
    e2 = mouse_event(QEvent.Type.MouseMove, ed.canvas, QPoint(400, 300))
    ed.canvas.mouseMoveEvent(e2)
    e3 = mouse_event(QEvent.Type.MouseButtonRelease, ed.canvas, QPoint(400, 300))
    ed.canvas.mouseReleaseEvent(e3)
    ok_c2 = len(ed.canvas.shapes) == 1 and ed.canvas.shapes[0].kind == "rect"
    record("C2 编辑器内可继续标注", ok_c2, f"shapes={len(ed.canvas.shapes)}")

    # C3 编辑器内 compose 仍为全分辨率（=底图尺寸）
    out = ed.canvas.compose()
    ok_c3 = out.size() == base.size()
    record("C3 编辑器内 compose 全分辨率", ok_c3, f"out={out.width()}x{out.height()}")
    ed.close()


# ---------------------------------------------------------------------------
# Stage D — 退出静默：程序退出时不显示任何托盘提示
# ---------------------------------------------------------------------------
def test_quit_silent() -> None:
    print("\n--- Stage D: 退出静默（不显示任何提示） ---")
    from pathlib import Path
    from unittest.mock import MagicMock

    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QSystemTrayIcon

    from hotkeys import Hotkey
    from snap import App
    from snapui import MainWindow, make_icon

    # D1 退出态：主窗口安静关闭（accept），不最小化到托盘、不发提示信号
    mw = MainWindow(make_icon(), Hotkey(), "rect", Path("."))
    emitted: list = []
    mw.minimize_requested.connect(lambda: emitted.append(1))
    mw._allow_close = True
    ev = QCloseEvent()
    mw.closeEvent(ev)
    ok_d1 = ev.isAccepted() and not emitted
    record(
        "D1 退出时主窗口安静关闭(不最小化/不弹提示)",
        ok_d1,
        f"accepted={ev.isAccepted()} minimize_signal={len(emitted)}",
    )
    mw.close()

    # D1b 非退出态关闭窗口仍最小化到托盘（保证原有行为不回归）
    mw2 = MainWindow(make_icon(), Hotkey(), "rect", Path("."))
    emitted2: list = []
    mw2.minimize_requested.connect(lambda: emitted2.append(1))
    ev2 = QCloseEvent()
    mw2.closeEvent(ev2)
    ok_d1b = (not ev2.isAccepted()) and len(emitted2) == 1
    record(
        "D1b 常态关闭仍最小化到托盘(不回归)",
        ok_d1b,
        f"accepted={ev2.isAccepted()} minimize_signal={len(emitted2)}",
    )
    mw2.close()

    # D2 _tray_message：退出态一律不显示；正常态照常显示
    a = App.__new__(App)                 # 绕过 __init__（依赖真实托盘/热键）
    a.tray = MagicMock()
    a._quitting = True
    a._tray_message("标题", "程序仍在运行")
    ok_d2 = not a.tray.showMessage.called
    record("D2 退出态托盘通知被抑制", ok_d2, f"calls={a.tray.showMessage.call_count}")
    a._quitting = False
    a._tray_message("标题", "正常提示", QSystemTrayIcon.Information, 1000)
    ok_d2b = a.tray.showMessage.call_count == 1
    record("D2b 正常态托盘通知仍可用", ok_d2b, f"calls={a.tray.showMessage.call_count}")

    # D3 _on_minimized：退出态不弹"程序仍在运行"，也不置位 hint 标志
    a.tray.reset_mock()
    a._quitting = True
    a._minimize_hint_shown = False
    a._on_minimized()
    ok_d3 = not a.tray.showMessage.called and a._minimize_hint_shown is False
    record(
        "D3 退出态不弹「程序仍在运行」",
        ok_d3,
        f"calls={a.tray.showMessage.call_count} hint={a._minimize_hint_shown}",
    )

    # D4 quit()：置退出标志、放行窗口关闭、撤托盘图标、退出事件循环
    q = App.__new__(App)
    q._quitting = False
    q._minimize_hint_shown = False
    q._hotkey_registered = False
    q.tray = MagicMock()
    q.app = MagicMock()
    q.main_window = MagicMock()
    q.quit()
    ok_d4 = (
        q._quitting is True
        and q.main_window._allow_close is True
        and q.tray.setVisible.called
        and q.app.quit.called
    )
    record(
        "D4 quit() 静默收尾(放行关闭/撤托盘/退事件循环)",
        ok_d4,
        f"quitting={q._quitting} allow_close={q.main_window._allow_close} "
        f"tray_hidden={q.tray.setVisible.called} app_quit={q.app.quit.called}",
    )

    # D5 quit() 之后任何通知都不再显示；重复 quit() 不重复执行
    q.tray.showMessage.reset_mock()
    q._tray_message("标题", "迟到的通知")
    q._on_minimized()
    q.app.quit.reset_mock()
    q.quit()
    ok_d5 = not q.tray.showMessage.called and not q.app.quit.called
    record(
        "D5 退出后无迟到通知且 quit() 幂等",
        ok_d5,
        f"msg_calls={q.tray.showMessage.call_count} quit_calls={q.app.quit.call_count}",
    )


# ---------------------------------------------------------------------------
# Stage E — 窗口化编辑器里「取字逐行盖回原文位置」
# ---------------------------------------------------------------------------
def test_line_ocr() -> None:
    print("\n--- Stage E: 编辑器窗口内取字逐行盖回原文 ---")
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    base = make_image(1600, 900)
    ed = EditorWindow(base, [], None)
    ed.resize(1000, 680)
    ed.show()                 # 父链可见，isVisible() 才反映子控件真实状态
    cv = ed.canvas
    cv._fit()

    lines = [
        {"text": "第一行文字", "box": [100, 80, 420, 120], "score": 0.98},
        {"text": "第二行文字", "box": [100, 200, 420, 240], "score": 0.95},
        {"text": "末行", "box": [600, 700, 900, 745], "score": 0.90},
    ]

    # E1 识别中：工具条/样式面板收起，浮出提示
    cv.show_ocr_busy()
    ok_e1 = cv.ocr_panel.isVisible() and not cv.toolbar.isVisible() and cv._ocr_active()
    record(
        "E1 识别中收起工具条并显示提示",
        ok_e1,
        f"panel={cv.ocr_panel.isVisible()} toolbar={cv.toolbar.isVisible()}",
    )

    # E2 结果逐行盖回：每行一个只读文本框，整块面板不再显示
    cv.show_ocr_lines(lines, "rapidocr")
    blocks = list(cv.ocr_layer._blocks)
    texts = [b.toPlainText() for b in blocks]
    ok_e2 = (
        len(blocks) == 3
        and texts == ["第一行文字", "第二行文字", "末行"]
        and cv.ocr_layer.isVisible()
        and not cv.ocr_panel.isVisible()
        and not cv.toolbar.isVisible()
    )
    record(
        "E2 逐行生成文本框(非整块面板)",
        ok_e2,
        f"blocks={len(blocks)} texts={texts} layer={cv.ocr_layer.isVisible()}",
    )

    # E3 位置换算：off + bbox*scale，再减去 2px 内边距
    g0 = blocks[0].geometry() if blocks else QRect()
    exp_x = cv.off_x + 100 * cv.view_scale - 2
    exp_y = cv.off_y + 80 * cv.view_scale - 2
    ok_e3 = abs(g0.x() - exp_x) <= 3 and abs(g0.y() - exp_y) <= 3
    record(
        "E3 行块盖回原文位置",
        ok_e3,
        f"geom=({g0.x()},{g0.y()}) 期望≈({exp_x:.1f},{exp_y:.1f}) scale={cv.view_scale:.3f}",
    )

    # E4 窗口缩放后重新排布，仍贴在原文上
    cv.resize(820, 620)
    cv._fit()
    cv._place_ocr_layer()
    blocks2 = list(cv.ocr_layer._blocks)
    g1 = blocks2[0].geometry() if blocks2 else QRect()
    exp1_x = cv.off_x + 100 * cv.view_scale - 2
    exp1_y = cv.off_y + 80 * cv.view_scale - 2
    ok_e4 = (
        len(blocks2) == 3
        and abs(g1.x() - exp1_x) <= 3
        and abs(g1.y() - exp1_y) <= 3
    )
    record(
        "E4 缩放后行块重新盖回",
        ok_e4,
        f"geom=({g1.x()},{g1.y()}) 期望≈({exp1_x:.1f},{exp1_y:.1f}) scale={cv.view_scale:.3f}",
    )

    # E5 取字态：画布鼠标事件被取字层接管，不会误画标注
    before = len(cv.shapes)
    cv.mousePressEvent(mouse_event(QEvent.Type.MouseButtonPress, cv, QPoint(300, 300)))
    cv.mouseReleaseEvent(mouse_event(QEvent.Type.MouseButtonRelease, cv, QPoint(500, 400)))
    ok_e5 = len(cv.shapes) == before
    record("E5 取字态不误画标注", ok_e5, f"shapes {before} → {len(cv.shapes)}")

    # E6 复制全部：按从上到下、同排从左到右的阅读顺序
    cv.ocr_layer.copy_all()
    clip = QApplication.clipboard().text()
    ok_e6 = clip == "第一行文字\n第二行文字\n末行"
    record("E6 复制全部按阅读顺序", ok_e6, f"clip={clip!r}")

    # E7 Esc 收起取字层，恢复工具条与正常编辑态
    cv.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    ok_e7 = not cv._ocr_active() and cv.toolbar.isVisible() and cv._ocr_lines == []
    record(
        "E7 Esc 返回编辑态",
        ok_e7,
        f"active={cv._ocr_active()} toolbar={cv.toolbar.isVisible()} lines={len(cv._ocr_lines)}",
    )

    # E8 后端没有 bbox 时降级成整块文本面板，保证仍可选可复制
    cv.show_ocr_lines([{"text": "甲"}, {"text": "乙"}], "windows-ocr")
    ok_e8 = (
        cv.ocr_panel.isVisible()
        and not cv.ocr_layer.isVisible()
        and cv.ocr_panel.edit.toPlainText() == "甲\n乙"
    )
    record(
        "E8 无坐标后端降级整块面板",
        ok_e8,
        f"panel={cv.ocr_panel.isVisible()} text={cv.ocr_panel.edit.toPlainText()!r}",
    )

    # E9 收起后导出仍为全分辨率，工具条恢复
    cv._hide_ocr_panel()
    out = cv.compose()
    ok_e9 = out.size() == base.size() and cv.toolbar.isVisible()
    record(
        "E9 收起后导出全分辨率",
        ok_e9,
        f"out={out.width()}x{out.height()} toolbar={cv.toolbar.isVisible()}",
    )

    # E10 识别中按 Esc 放弃：迟到的识别结果不再弹出，下次取字可重新开始
    cv.show_ocr_busy()
    cv.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Escape, Qt.NoModifier))
    cv.show_ocr_lines(lines, "rapidocr")       # 模拟子线程迟到的回调
    ok_e10a = not cv._ocr_active() and not cv.ocr_layer.isVisible()
    cv.show_ocr_busy()
    cv.show_ocr_lines(lines[:1], "rapidocr")
    ok_e10b = cv.ocr_layer.isVisible() and len(cv.ocr_layer._blocks) == 1
    record(
        "E10 识别中 Esc 取消且可重新取字",
        ok_e10a and ok_e10b,
        f"迟到结果被忽略={ok_e10a} 重新取字={ok_e10b}",
    )
    cv._hide_ocr_panel()
    ed.close()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    print("=" * 66)
    print("窗口化编辑器离屏自测")
    print("=" * 66)

    app = QApplication.instance() or QApplication(sys.argv)

    test_canvas()
    test_overlay()
    test_editor_window()
    test_quit_silent()
    test_line_ocr()

    print("=" * 66)
    failed = [n for n, s, _ in results if s == FAIL]
    print(f"合计 {len(results)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项：" + "、".join(failed))
    sys.exit(1 if failed else 0)
