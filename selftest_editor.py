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

  Stage F  整图旋转 / 镜像（底图 + 标注坐标一起变）
    F1  顺时针 90°：宽高互换、左上角红点到右上角
    F2  矩形/箭头/画笔/文字/马赛克坐标按公式变换
    F3  逆时针 / 左右镜像 / 上下镜像的像素方向
    F4  镜像后矩形坐标正确
    F5  Ctrl+Z 撤销变换恢复底图与标注
    F6  变换后再画标注，撤销顺序正确
    F7  马赛克缓存失效
    F8  旋转 4 次回到原图、导出始终全分辨率
    F9  菜单入口（含快捷键）能真正触发变换与画笔箭头设置
    F10 真实按键 Ctrl+R 能触发顺时针旋转

  Stage G  画笔首尾端点箭头
    G1  默认两端无箭头
    G2  设默认后新建画笔带上箭头
    G3  带箭头的画笔合成不报错且分辨率不变
    G4  终点箭头确实画出像素（与无箭头对比）
    G5  起点箭头确实画出像素
    G6  样式面板改选中画笔的箭头开关
    G7  整图变换后箭头字段保留、路径坐标跟着变

  Stage H  单实例守卫（singleinstance.py）
    H1  新建互斥体可启动
    H2  无实例记录却报「已存在」→ 陈旧锁自动接管
    H3  记录中的进程已退出 → 自动接管
    H4  活跃实例被识别为 running
    H5  互斥体不可用不阻止启动
    H6  不把自己误判为已有实例
    H7  进程创建时间签名可用
    H8  实例记录写读与 release 只删自己
    H9  残留 last-error 183 不误报「已在运行」（子进程真实复现）
    H10 唤醒事件可创建并可触发
    H11 真实活实例被判定 running（子进程持锁）
    H12 Qt 唤醒监听可安装
    H13 可枚举旧版幽灵进程且不误列自己

  Stage I  工具栏整图变换按钮 + 画笔起点/终点箭头勾选
    I1  编辑器工具栏含 4 个变换按钮（顺旋/逆旋/左右/上下）且可见
    I2  点「顺旋」触发顺时针 90°（宽高互换）
    I3  点「上下」触发垂直镜像，像素方向正确
    I4  截屏遮罩工具栏隐藏变换按钮
    I5  无选中标注时样式面板显示起点/终点箭头勾选框，勾选即设新建画笔默认

  Stage J  直线命令 + 工具栏图标化 + 箭头方向/尖锐度
    J1  工具列表含「直线」
    J2  所有工具 / 动作图标均可绘制成功
    J3  直线两端加箭头后确实多出像素
    J4  只加起点箭头：差异集中在起点端（方向正确）
    J5  只加终点箭头：差异集中在终点端（方向正确）
    J6  直线（两端）与箭头（单端）在起点端有差异
    J7  直线命令经 Canvas 完整走通 + 样式面板勾选
    J8  马赛克图标保留九宫格，且只在不规则的部分格子填实心方块

  Stage K  截屏前隐藏窗口 + 样式按钮 + 曲线端点箭头方向
    K1  工具栏已移除「样式」按钮
    K2  曲线末段抖动不影响终点箭头方向
    K3  起点箭头方向朝曲线外侧
    K4  末段采样点重合时不退化为水平箭头
    K5  末段抖动/平滑两条曲线渲染出的箭头一致
    K6  截屏前隐藏全部自有窗口（含编辑器/浮动面板）且可恢复

  Stage L  撤销 / 顺旋 / 逆旋 图标可区分性
    L1  撤销与逆旋图标像素差异足够大
    L2  顺旋与逆旋严格水平镜像（风格成对）
    L3  旋转图标含中心图片方块、撤销为中心留空
    L4  撤销折返路径为「左下 → 右 → 上 → 左」且中间留空
    L5  顺/逆旋箭头尖锐（半张角、三角形墨量、圆弧平头截断）

  Stage M  左右 / 上下 镜像图标重设计
    M1  上下是左右严格 90° 旋转（风格成对）
    M2  中间是虚线镜像轴，左右竖轴 / 上下横轴
    M3  两侧是实心三角，一纯白（原图）一淡白（镜像）
    M4  与圆环绕方块（旋转）、折线（撤销）形状类别分离
    M5  与旧版「对角两个小箭头」明显不同

  Stage N  关于对话框（头像 / 邮箱）与软件图标
    N1  头像与 ico 资源文件存在
    N2  运行时图标来自多尺寸 app.ico（不是代码画的相机）
    N3  关于文案含邮箱与 mailto 链接
    N4  关于对话框显示头像且未被裁切
    N5  关于对话框邮箱可见且可点击
    N6  打包配置收进头像 / ico，exe 图标指向 app.ico
    N7  关于窗口为非模态单例且可重复打开
    N8  截屏前关于窗口会被隐藏并恢复（不会被拍进图里）

  Stage P  独立「滚动长截图」命令（方案 2）
    P1  主窗口有信号 / 菜单动作 / 按钮，点击都能发出 long_capture_requested
    P2  8 语言切换后按钮 / 菜单文案即时刷新，英文无中文残留
    P3  Overlay.set_long_mode 强制 rect、切「确定」提示、清窗口探测
    P4  长截图模式 _confirm 发 long_shot（逻辑坐标）且不发 to_editor
    P5  普通模式 _confirm 仍发 to_editor（不回归）
    P6  语言切换后「确定」提示仍按长截图 key 翻译
    P7  逻辑选区 → 屏幕物理矩形的原点 / DPR 换算（含负原点）
    P8  start_long_capture 走 rect + long_mode，且 busy 时不再启动
    P9  _close_overlay(restore=False) 拼接期间不恢复自有窗口
    P10 托盘有独立动作，语言刷新覆盖它；App 已连接主窗口信号
    P11 关于 8 语言简介为用户指定文案，邮箱仍在，无旧「模仿微信」字样
    P12 帮助 8 语言均为 9 节且不再描述旧的工具条入口
    P13 _begin_capture(long_mode=True) 真的给 Overlay 开了长截图模式

  Stage Q  选窗口式滚动长截图（v17 新交互）
    Q1  左键按下沿切换暂停 / 继续，按住不放不重复触发
    Q2  右键按下沿结束，stop_reason = user-right-click
    Q3  点「确定」结束且 request_stop 幂等
    Q4  点在控制条上不触发暂停 / 结束，移出后正常生效
    Q5  选窗口时仍按住的左键作为基线忽略
    Q6  wait_while_paused 未暂停 / 已结束时立即返回
    Q7  stitch_scroll 暂停期间绝不抓帧，右键结束后不再滚轮
    Q8  stitch_scroll 滚到底自动结束，抓帧隐藏钩子成对调用
    Q9  place_bar_outside 避开窗口、全屏无解、负原点多显示器可用
    Q10 bar_screen_rect 按 DPR 换算成屏幕物理矩形
    Q11 Overlay 长截图 picking：单击窗口直接发 long_shot、不进编辑态
    Q12 Overlay 长截图 Enter 直接启动、右键取消
    Q13 _pick_window(client=True) 用客户区而非完整边框
    Q14 BusyBar 有「确定 ✓」、暂停状态、8 语言即时刷新
    Q15 8 语言帮助第 9 节描述新流程且无旧「框选 → 确定」
    Q16 StitchWorker 默认带 ScrollControl，控制条信号 / 钩子已接线
    Q17 主窗口按钮副标题改为「点击窗口后自动滚动」

用法：  python selftest_editor.py
退出码：0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import os
import sys

# 离屏渲染：必须在创建 QApplication 之前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# 自测固定用简体中文跑（部分断言按中文菜单名查找），且不会写真实配置
os.environ.setdefault("SNAPTOOL_LANG", "zh_CN")

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter

from snapeditor import Overlay, Shape, TOOLS, toolbar_icon
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
# Stage F — 整图旋转 / 镜像
# ---------------------------------------------------------------------------
def test_image_transform() -> None:
    print("\n--- Stage F: 整图旋转 / 镜像 ---")
    from PySide6.QtCore import QSize

    W, H = 160, 90

    def fresh() -> Canvas:
        b = make_image(W, H)
        b.setPixelColor(0, 0, QColor(255, 0, 0))   # 左上角红点，用来判方向
        c = Canvas(b, [], None)
        c.resize(1000, 680)
        c._fit()
        c.shapes = [
            Shape(kind="rect", rect=QRect(10, 20, 40, 30)),
            Shape(kind="arrow", start=QPoint(5, 5), end=QPoint(50, 5)),
            Shape(kind="pen", points=[QPoint(1, 1), QPoint(30, 10), QPoint(60, 20)]),
            Shape(kind="text", text="测试", pos=QPoint(20, 40)),
            Shape(kind="mosaic", rect=QRect(70, 30, 20, 20)),
        ]
        return c

    def red_at(c: Canvas) -> tuple[int, int]:
        q = c.base
        for y in range(q.height()):
            for x in range(q.width()):
                if q.pixelColor(x, y).red() > 200:
                    return (x, y)
        return (-1, -1)

    # F1 顺时针 90°：宽高互换，左上角红点到右上角
    cv = fresh()
    cv.transform_image("cw")
    ok_f1 = cv.base.size() == QSize(H, W) and red_at(cv) == (H - 1, 0)
    record(
        "F1 顺时针90°尺寸与像素方向",
        ok_f1,
        f"size=({cv.base.width()},{cv.base.height()}) red={red_at(cv)}",
    )

    # F2 各类标注坐标跟着变换（像素中心公式 / 矩形边界公式）
    r, ar, pn, tx, mo = cv.shapes
    ok_f2 = (
        r.rect == QRect(40, 10, 30, 40)
        and ar.start == QPoint(84, 5) and ar.end == QPoint(84, 50)
        and pn.points[0] == QPoint(88, 1)
        and tx.pos == QPoint(49, 20)
        and mo.rect == QRect(40, 70, 20, 20)
    )
    record(
        "F2 标注坐标随整图变换",
        ok_f2,
        f"rect={r.rect} arrow=({ar.start},{ar.end}) pen={pn.points[0]} text={tx.pos}",
    )

    # F3 逆时针 / 左右镜像 / 上下镜像的像素方向
    c2, c3, c4 = fresh(), fresh(), fresh()
    c2.transform_image("ccw")
    c3.transform_image("flip_h")
    c4.transform_image("flip_v")
    ok_f3 = (
        c2.base.size() == QSize(H, W) and red_at(c2) == (0, W - 1)
        and c3.base.size() == QSize(W, H) and red_at(c3) == (W - 1, 0)
        and c4.base.size() == QSize(W, H) and red_at(c4) == (0, H - 1)
    )
    record(
        "F3 逆时针/左右/上下镜像方向",
        ok_f3,
        f"ccw={red_at(c2)} flip_h={red_at(c3)} flip_v={red_at(c4)}",
    )

    # F4 镜像后的矩形 / 端点 / 文字坐标
    ok_f4 = (
        c3.shapes[0].rect == QRect(110, 20, 40, 30)
        and c3.shapes[1].start == QPoint(154, 5)
        and c4.shapes[0].rect == QRect(10, 40, 40, 30)
        and c4.shapes[3].pos == QPoint(20, 49)
    )
    record(
        "F4 镜像后标注坐标",
        ok_f4,
        f"flip_h rect={c3.shapes[0].rect} flip_v rect={c4.shapes[0].rect}",
    )

    # F5 撤销变换：底图与全部标注恢复
    cv.undo()
    ok_f5 = (
        cv.base.size() == QSize(W, H)
        and red_at(cv) == (0, 0)
        and len(cv.shapes) == 5
        and cv.shapes[0].rect == QRect(10, 20, 40, 30)
        and cv.shapes[1].start == QPoint(5, 5)
    )
    record(
        "F5 Ctrl+Z 撤销整图变换",
        ok_f5,
        f"size=({cv.base.width()},{cv.base.height()}) red={red_at(cv)}",
    )

    # F6 变换后又画标注：先撤销标注、再撤销变换
    c5 = fresh()
    c5.transform_image("cw")
    c5.shapes.append(Shape(kind="rect", rect=QRect(1, 1, 5, 5)))
    c5._op_stack.append("shape")
    c5.undo()
    first = len(c5.shapes) == 5 and c5.base.width() == H
    c5.undo()
    second = c5.base.width() == W
    record(
        "F6 撤销顺序(先标注后变换)",
        first and second,
        f"先撤标注={first} 再撤变换={second}",
    )

    # F7 马赛克缓存取自旧图，变换后必须失效
    c6 = fresh()
    c6.shapes[4]._mosaic_cache = ((1, 2, 3, 4), QImage())
    c6.transform_image("cw")
    ok_f7 = not hasattr(c6.shapes[4], "_mosaic_cache")
    record("F7 变换后马赛克缓存失效", ok_f7, f"has_cache={not ok_f7}")

    # F8 旋转 4 次回到原图，导出始终全分辨率
    c7 = fresh()
    for _ in range(4):
        c7.transform_image("cw")
    out = c7.compose()
    ok_f8 = (
        c7.base.size() == QSize(W, H)
        and red_at(c7) == (0, 0)
        and out.size() == QSize(W, H)
    )
    record(
        "F8 旋转4次复原且导出全分辨率",
        ok_f8,
        f"size=({c7.base.width()},{c7.base.height()}) red={red_at(c7)} out={out.size()}",
    )

    # F9 菜单是唯一入口，确认 QAction 的绑定与快捷键真的生效
    ed = EditorWindow(make_image(W, H), [], None)
    ed.resize(1000, 680)

    def find_submenu(title: str):
        for top in ed.menuBar().actions():
            m = top.menu()
            if m is None:
                continue
            for a in m.actions():
                if a.text() == title and a.menu() is not None:
                    return a.menu()
        return None

    m_t = find_submenu("图像变换")
    m_p = find_submenu("端点箭头")
    ok_menu = (
        m_t is not None and len(m_t.actions()) == 4
        and m_p is not None and len(m_p.actions()) == 4
    )
    if m_t:
        m_t.actions()[0].trigger()          # 顺时针 90°
    if m_p:
        m_p.actions()[3].trigger()          # 两端都加
    ok_f9 = (
        ok_menu
        and ed.canvas.base.size() == QSize(H, W)
        and ed.canvas._pen_arrow_start and ed.canvas._pen_arrow_end
        and "Ctrl+R" in m_t.actions()[0].shortcut().toString()
    )
    record(
        "F9 菜单入口与快捷键生效",
        ok_f9,
        f"menus={ok_menu} size=({ed.canvas.base.width()},{ed.canvas.base.height()}) "
        f"arrows=({ed.canvas._pen_arrow_start},{ed.canvas._pen_arrow_end})",
    )
    ed.close()

    # F10 真实按键：快捷键不只是菜单上的文字
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    ed2 = EditorWindow(make_image(W, H), [], None)
    ed2.resize(1000, 680)
    ed2.show()
    ed2.activateWindow()
    QApplication.instance().processEvents()
    QTest.keyClick(ed2, Qt.Key_R, Qt.ControlModifier)
    QApplication.instance().processEvents()
    ok_f10 = ed2.canvas.base.size() == QSize(H, W)
    record(
        "F10 真实按键 Ctrl+R 触发旋转",
        ok_f10,
        f"按键后 size=({ed2.canvas.base.width()},{ed2.canvas.base.height()})",
    )
    ed2.close()


# ---------------------------------------------------------------------------
# Stage G — 画笔首尾端点箭头
# ---------------------------------------------------------------------------
def test_pen_arrows() -> None:
    print("\n--- Stage G: 画笔首尾端点箭头 ---")
    from PySide6.QtCore import QSize

    base = make_image(400, 300)
    cv = Canvas(base, [], None)
    cv.resize(800, 600)
    cv._fit()

    ok_g1 = not cv._pen_arrow_start and not cv._pen_arrow_end
    record("G1 默认画笔两端无箭头", ok_g1, f"start={cv._pen_arrow_start} end={cv._pen_arrow_end}")

    # G2 设好默认后画一条画笔线
    cv.set_pen_arrows(True, True)
    cv._set_tool("pen")
    cv.mousePressEvent(mouse_event(QEvent.Type.MouseButtonPress, cv, QPoint(50, 50)))
    for p in (QPoint(80, 60), QPoint(120, 80)):
        cv.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, cv, p))
    cv.mouseReleaseEvent(mouse_event(QEvent.Type.MouseButtonRelease, cv, QPoint(120, 80)))
    s = cv.shapes[0] if cv.shapes else None
    ok_g2 = (
        s is not None and s.kind == "pen"
        and s.pen_arrow_start and s.pen_arrow_end
    )
    record(
        "G2 新建画笔带首尾箭头",
        ok_g2,
        f"shapes={len(cv.shapes)} start={getattr(s, 'pen_arrow_start', None)} end={getattr(s, 'pen_arrow_end', None)}",
    )

    # G3 带箭头合成不报错，分辨率不变
    out = cv.compose()
    ok_g3 = out.size() == base.size()
    record("G3 带箭头合成全分辨率", ok_g3, f"out={out.width()}x{out.height()}")

    # G4/G5 像素级验证：箭头确实画在了端点附近
    pts = [QPoint(50, 50), QPoint(80, 60), QPoint(120, 80)]

    def with_pen(**kw) -> QImage:
        c = Canvas(base, [Shape(kind="pen", points=list(pts),
                                color=QColor(255, 0, 0), width=3, **kw)], None)
        return c.compose()

    def diff_count(a: QImage, b: QImage, r: QRect) -> int:
        n = 0
        for y in range(r.top(), r.bottom()):
            for x in range(r.left(), r.right()):
                if a.pixelColor(x, y) != b.pixelColor(x, y):
                    n += 1
        return n

    plain = with_pen()
    d_end = diff_count(plain, with_pen(pen_arrow_end=True), QRect(95, 55, 50, 50))
    d_start = diff_count(plain, with_pen(pen_arrow_start=True), QRect(25, 25, 50, 50))
    record("G4 终点箭头画出像素", d_end > 30, f"差异像素={d_end}")
    record("G5 起点箭头画出像素", d_start > 30, f"差异像素={d_start}")

    # G6 样式面板可改选中画笔，勾选状态回填正确
    cv._selected = s
    cv._apply_style({"pen_arrow_start": False, "pen_arrow_end": True})
    cv._refresh_style_panel()
    ok_g6 = (
        not s.pen_arrow_start and s.pen_arrow_end
        and not cv.style_panel._pen_arrow_start.isChecked()
        and cv.style_panel._pen_arrow_end.isChecked()
    )
    record(
        "G6 样式面板改选中画笔箭头",
        ok_g6,
        f"shape=({s.pen_arrow_start},{s.pen_arrow_end}) panel=({cv.style_panel._pen_arrow_start.isChecked()},{cv.style_panel._pen_arrow_end.isChecked()})",
    )

    # G7 整图变换后箭头标记保留，路径坐标跟着变
    before = QPoint(s.points[0])
    cv.transform_image("cw")
    ok_g7 = (
        s.pen_arrow_end and not s.pen_arrow_start
        and s.points[0] != before
        and cv.base.size() == QSize(300, 400)
    )
    record(
        "G7 变换后箭头保留且坐标跟着变",
        ok_g7,
        f"arrow=({s.pen_arrow_start},{s.pen_arrow_end}) p0 {before}→{s.points[0]}",
    )


# ---------------------------------------------------------------------------
def test_single_instance() -> None:
    """Stage H：单实例守卫的判定逻辑、陈旧锁自愈与唤醒事件。"""
    import json
    import subprocess
    import tempfile
    import time
    import uuid
    from pathlib import Path

    import singleinstance as si

    here = str(Path(__file__).resolve().parent)
    me = os.getpid()
    own_sig = si.pid_signature(me)

    s1, r1 = si.classify(0, True, {}, me)
    record("H1 新建互斥体可启动", s1 == "ok" and r1 == "new-instance", f"{s1}/{r1}")

    # 旧版本不写实例记录；锁还在但没有记录时必须自动接管，不再弹「已在运行」
    s2, r2 = si.classify(183, True, {}, me)
    record(
        "H2 无记录却报已存在→陈旧锁接管",
        s2 == "stale" and r2 == "no-record", f"{s2}/{r2}",
    )
    s3, r3 = si.classify(183, True, {"pid": 99999999, "sig": "bogus"}, me)
    record("H3 记录进程已死→自动接管", s3 == "stale" and r3 == "dead-or-reused-pid", f"{s3}/{r3}")
    s4, r4 = si.classify(183, True, {"pid": me, "sig": own_sig}, 1)
    record("H4 活跃实例被识别为 running", s4 == "running" and r4 == "alive", f"{s4}/{r4}")
    s5, _ = si.classify(183, False, {}, me)
    record("H5 互斥体不可用不阻止启动", s5 == "ok", s5)
    s6, _ = si.classify(183, True, {"pid": me, "sig": own_sig}, me)
    record("H6 不把自己误判为已有实例", s6 == "stale", s6)
    record(
        "H7 进程创建时间签名可用",
        bool(own_sig) and si.pid_signature(99999999) is None, f"sig={own_sig}",
    )

    # H8 记录文件：写入内容正确；release 只删自己写的，不误删别的实例的
    with tempfile.TemporaryDirectory() as td:
        orig = si.INSTANCE_FILE
        si.INSTANCE_FILE = Path(td) / "instance.json"
        try:
            si.write_record()
            got = si.read_record()
            ok_w = got.get("pid") == me and got.get("sig") == own_sig
            si.INSTANCE_FILE.write_text(
                json.dumps({"pid": 123, "sig": "other"}), encoding="utf-8"
            )
            si.release()
            ok_keep = si.INSTANCE_FILE.exists()
            si.write_record()
            si.release()
            ok_del = not si.INSTANCE_FILE.exists()
            record(
                "H8 实例记录写读与只删自己", ok_w and ok_keep and ok_del,
                f"write={ok_w} keep={ok_keep} del={ok_del}",
            )
        finally:
            si.INSTANCE_FILE = orig

    tag = uuid.uuid4().hex[:8]
    unique_mutex = f"SnapTool_Selftest_{tag}"
    tmp_rec = Path(tempfile.gettempdir()) / f"snaptool-selftest-{tag}.json"

    # H9 关键回归：CreateMutexW 前残留的 last-error 183 曾让程序误报「已在运行」。
    # 用唯一互斥体名 + 子进程，确保与现场任何真实实例互不干扰。
    code = (
        "import ctypes, tempfile, singleinstance as si\n"
        "from pathlib import Path\n"
        f"si.MUTEX_NAME = {unique_mutex!r}\n"
        f"si.INSTANCE_FILE = Path({str(tmp_rec)!r})\n"
        "si._k32.SetLastError(183)\n"
        "st = si.probe()\n"
        "print(st.state + '/' + st.reason)\n"
    )
    try:
        cp = subprocess.run(
            [sys.executable, "-c", code], cwd=here,
            capture_output=True, text=True, timeout=25,
        )
        lines = [x for x in (cp.stdout or "").splitlines() if "/" in x]
        verdict = lines[-1] if lines else ""
        record(
            "H9 残留 last-error 不误报已运行", verdict == "ok/new-instance",
            f"子进程={verdict} stderr={(cp.stderr or '')[-100:]}",
        )
    except Exception as exc:  # noqa: BLE001
        record("H9 残留 last-error 不误报已运行", False, repr(exc))
    finally:
        try:
            tmp_rec.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass

    # H10 / H12 唤醒：重复启动时请已有实例显示主窗口
    orig_event = si.ACTIVATE_EVENT_NAME
    si.ACTIVATE_EVENT_NAME = f"SnapTool_Selftest_Event_{tag}"
    notifier = None
    try:
        before = si.signal_existing()
        h = si.create_activation_event()
        after = si.signal_existing()
        record(
            "H10 唤醒事件可创建并可触发",
            (not before) and bool(h) and after,
            f"before={before} handle={bool(h)} after={after}",
        )
        notifier = si.install_activation_notifier(lambda: None)
        record(
            "H12 Qt 唤醒监听可安装",
            notifier is not None and notifier.isActive(),
            f"timer_active={notifier is not None and notifier.isActive()}",
        )
    finally:
        si.ACTIVATE_EVENT_NAME = orig_event
        del notifier

    others = si.find_other_instances()
    record(
        "H13 可枚举旧版幽灵进程且不误列自己",
        isinstance(others, list) and me not in others,
        f"others={others}",
    )

    # H11 真实场景：另一个进程持有互斥体并写了活跃记录，本进程应判 running
    with tempfile.TemporaryDirectory() as td:
        rec_file = Path(td) / "instance.json"
        ready = Path(td) / "ready"
        alive_mutex = f"{unique_mutex}_alive"
        sub = (
            "import ctypes, json, time, singleinstance as si\n"
            "from pathlib import Path\n"
            f"si.MUTEX_NAME = {alive_mutex!r}\n"
            f"si.INSTANCE_FILE = Path({str(rec_file)!r})\n"
            "si._k32.SetLastError(0)\n"
            "h = si._k32.CreateMutexW(None, False, si.MUTEX_NAME)\n"
            "si.write_record()\n"
            f"Path({str(ready)!r}).write_text('ok', encoding='utf-8')\n"
            "time.sleep(8)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", sub], cwd=here,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(60):
                if ready.exists():
                    break
                time.sleep(0.05)
            orig_m, orig_f = si.MUTEX_NAME, si.INSTANCE_FILE
            si.MUTEX_NAME, si.INSTANCE_FILE = alive_mutex, rec_file
            try:
                st = si.probe()
                record(
                    "H11 真实活实例判定 running",
                    st.state == "running" and st.record.get("pid") not in (None, me),
                    f"{st.state}/{st.reason} rec={st.record}",
                )
            finally:
                si.MUTEX_NAME, si.INSTANCE_FILE = orig_m, orig_f
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Stage I — 工具栏整图变换按钮 + 画笔起点/终点箭头勾选
# ---------------------------------------------------------------------------
def test_toolbar_transform() -> None:
    print("\n--- Stage I: 工具栏整图变换按钮 + 画笔箭头勾选 ---")
    from snapeditor import Toolbar, TRANSFORM_ACTIONS, Overlay

    # I1 编辑器工具栏含 4 个变换按钮且未隐藏
    tb = Toolbar(None)
    have = all(a in tb._actions for a in TRANSFORM_ACTIONS)
    shown = all(not tb._actions[a].isHidden() for a in TRANSFORM_ACTIONS)
    record(
        "I1 编辑器工具栏含 4 个变换按钮且可见",
        have and shown,
        f"have={have} shown={shown}",
    )

    # I2 点「顺旋」触发顺时针 90°（宽高互换）
    ed = EditorWindow(make_image(160, 90), [], None)
    ed.resize(1000, 680)
    ed.show()
    app.processEvents()
    c0 = ed.canvas
    w0, h0 = c0.base.width(), c0.base.height()
    c0.toolbar._actions["顺旋"].click()
    app.processEvents()
    ok_i2 = (c0.base.width(), c0.base.height()) == (h0, w0)
    record("I2 点「顺旋」顺时针旋转 90°", ok_i2,
           f"before=({w0},{h0}) after=({c0.base.width()},{c0.base.height()})")

    # I3 点「上下」触发垂直镜像（像素方向：左上红点→左下）
    ed2 = EditorWindow(make_image(4, 2, (120, 160, 220)), [], None)
    ed2.resize(1000, 680)
    ed2.show()
    app.processEvents()
    c1 = ed2.canvas
    img = QImage(4, 2, QImage.Format_RGB32)
    img.fill(QColor(120, 160, 220))
    img.setPixelColor(0, 0, QColor(255, 0, 0))
    c1.base = img.copy()
    c1._fit()
    c1.toolbar._actions["上下"].click()
    app.processEvents()
    red = [(x, y) for y in range(c1.base.height())
           for x in range(c1.base.width())
           if c1.base.pixelColor(x, y).red() > 200]
    ok_i3 = red == [(0, 1)]
    record("I3 点「上下」垂直镜像方向正确", ok_i3, f"red_at={red}")

    # I4 截屏遮罩工具栏隐藏变换按钮
    ov = Overlay(make_image(200, 120))
    ov.hide()
    hidden = all(ov.toolbar._actions[a].isHidden() for a in TRANSFORM_ACTIONS)
    record("I4 截屏遮罩工具栏隐藏变换按钮", hidden, f"hidden={hidden}")
    ov.close()

    # I5 无选中标注时样式面板显示起点/终点箭头勾选框，勾选即设默认
    # 工具栏已移除「样式」按钮，改由菜单 / 选中标注自动弹出的同一入口打开
    c0._toggle_style_panel()  # 打开样式面板（无选中）
    app.processEvents()
    sp = c0.style_panel
    vis = sp._pen_arrow_start.isVisible() and sp._pen_arrow_end.isVisible()
    record("I5 无选中时样式面板显示箭头勾选框", vis, f"visible={vis}")
    sp._pen_arrow_start.setChecked(True)
    sp._pen_arrow_end.setChecked(True)
    app.processEvents()
    ok_arrows = c0._pen_arrow_start and c0._pen_arrow_end
    record("I5b 勾选起点/终点箭头设为新建画笔默认", ok_arrows,
           f"start={c0._pen_arrow_start} end={c0._pen_arrow_end}")
    ed.close()
    ed2.close()


# ---------------------------------------------------------------------------
# Stage J — 直线命令 + 箭头图标化 + 箭头方向/尖锐度
# ---------------------------------------------------------------------------
def test_line_and_icons() -> None:
    """新增直线命令（两端加箭头）、工具栏图标、箭头方向/尖锐度。"""
    from PySide6.QtCore import QSize

    base = make_image(400, 300)

    # J1 工具列表含「直线」
    tool_keys = [k for k, _ in TOOLS]
    ok_j1 = "line" in tool_keys
    record("J1 工具列表含直线", ok_j1, f"tools={tool_keys}")

    # J2 所有工具 / 动作图标都能绘制成功（不抛异常、非空白）
    icon_names = tool_keys + [
        "撤销", "样式", "顺旋", "逆旋", "左右", "上下",
        "长截图", "取字", "保存", "复制", "确定", "✕",
    ]
    bad = []
    for nm in icon_names:
        try:
            ic = toolbar_icon(nm)
            pm = ic.pixmap(QSize(22, 22))
            if ic.isNull() or pm.isNull():
                bad.append(nm)
        except Exception as e:  # noqa: BLE001
            bad.append(f"{nm}:{e}")
    record("J2 工具栏图标全部可绘制", not bad, f"异常={bad}")

    # J8 马赛克图标：九宫格保留，只在部分格子不规则填入实心方块
    from PySide6.QtGui import QPixmap, QPainter
    from snapeditor import _draw_icon, _ICON_SIZE

    pm_m = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pm_m.fill(QColor(0, 0, 0, 0))
    pi = QPainter(pm_m)
    pi.setRenderHint(QPainter.Antialiasing, True)
    _draw_icon("mosaic", pi)
    pi.end()
    im_m = pm_m.toImage()
    cell = (_ICON_SIZE - 8) / 3

    def mid(r, c):
        return int(4 + c * cell + cell / 2), int(4 + r * cell + cell / 2)

    filled_cells = ((0, 0), (0, 1), (1, 2), (2, 0), (2, 2))
    empty_cells = ((1, 0), (1, 1), (2, 1))
    ok_fill = all(100 < im_m.pixelColor(*mid(r, c)).alpha() < 230
                  for r, c in filled_cells)
    ok_blank = all(im_m.pixelColor(*mid(r, c)).alpha() < 20 for r, c in empty_cells)
    ok_grid = im_m.pixelColor(int(4 + cell), 7).alpha() > 230
    record("J8 马赛克图标保留九宫格并不规则填块",
           ok_fill and ok_blank and ok_grid,
           f"淡白块={ok_fill} 留白={ok_blank} 纯白网格={ok_grid}")

    def with_shape(s: Shape) -> QImage:
        c = Canvas(base, [s], None)
        return c.compose()

    def diff_count(a: QImage, b: QImage, r: QRect) -> int:
        n = 0
        for y in range(r.top(), r.bottom()):
            for x in range(r.left(), r.right()):
                if a.pixelColor(x, y) != b.pixelColor(x, y):
                    n += 1
        return n

    line_plain = Shape(kind="line", start=QPoint(20, 40), end=QPoint(180, 40),
                       color=QColor(255, 0, 0), width=3)
    line_both = Shape(kind="line", start=QPoint(20, 40), end=QPoint(180, 40),
                      color=QColor(255, 0, 0), width=3,
                      pen_arrow_start=True, pen_arrow_end=True)
    line_end = Shape(kind="line", start=QPoint(20, 40), end=QPoint(180, 40),
                     color=QColor(255, 0, 0), width=3, pen_arrow_end=True)
    arrow_one = Shape(kind="arrow", start=QPoint(20, 40), end=QPoint(180, 40),
                      color=QColor(255, 0, 0), width=3)

    p_plain = with_shape(line_plain)
    p_both = with_shape(line_both)
    p_end = with_shape(line_end)
    p_arrow = with_shape(arrow_one)

    # J3 直线两端加箭头后确实多出像素
    d_both = diff_count(p_plain, p_both, QRect(0, 0, 200, 80))
    record("J3 直线两端箭头画出像素", d_both > 60, f"差异={d_both}")

    # J4 只加起点箭头：差异集中在起点端（x<70），终点端（x>130）几乎无差异
    d_start_near = diff_count(p_plain, with_shape(
        Shape(kind="line", start=QPoint(20, 40), end=QPoint(180, 40),
              color=QColor(255, 0, 0), width=3, pen_arrow_start=True)),
        QRect(0, 0, 70, 80))
    d_start_far = diff_count(p_plain, with_shape(
        Shape(kind="line", start=QPoint(20, 40), end=QPoint(180, 40),
              color=QColor(255, 0, 0), width=3, pen_arrow_start=True)),
        QRect(130, 0, 70, 80))
    record("J4 起点箭头画在起点端", d_start_near > 20 and d_start_far < d_start_near,
           f"近={d_start_near} 远={d_start_far}")

    # J5 只加终点箭头：差异集中在终点端（x>130），验证方向指向终点
    d_end_near = diff_count(p_plain, p_end, QRect(130, 0, 70, 80))
    d_end_far = diff_count(p_plain, p_end, QRect(0, 0, 70, 80))
    record("J5 终点箭头画在终点端（方向正确）", d_end_near > 20 and d_end_far < d_end_near,
           f"近={d_end_near} 远={d_end_far}")

    # J6 直线（两端）与单端箭头（arrow 工具）在起点端有差异
    d_vs_arrow = diff_count(p_arrow, p_both, QRect(0, 0, 70, 80))
    record("J6 直线两端≠箭头单端（起点端不同）", d_vs_arrow > 20, f"差异={d_vs_arrow}")

    # J7 直线命令可经 Canvas 完整走通（含默认箭头 / 样式面板勾选）
    cv = Canvas(base, [], None)
    cv.resize(800, 600)
    cv._fit()
    cv.set_pen_arrows(False, True)  # 默认只加终点箭头
    cv._set_tool("line")
    cv.mousePressEvent(mouse_event(QEvent.Type.MouseButtonPress, cv, QPoint(50, 50)))
    cv.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, cv, QPoint(150, 50)))
    cv.mouseReleaseEvent(mouse_event(QEvent.Type.MouseButtonRelease, cv, QPoint(150, 50)))
    s = cv.shapes[0] if cv.shapes else None
    ok_line_create = (
        s is not None and s.kind == "line" and s.pen_arrow_end and not s.pen_arrow_start
    )
    record("J7a 直线命令画出、默认箭头生效",
           ok_line_create, f"kind={getattr(s, 'kind', None)} end={getattr(s, 'pen_arrow_end', None)}")

    if s is not None:
        cv._selected = s
        cv.show()
        cv._refresh_style_panel()
        cv.style_panel.show()
        vis = cv.style_panel._pen_arrow_start.isVisible() and cv.style_panel._pen_arrow_end.isVisible()
        chk = (cv.style_panel._pen_arrow_end.isChecked()
               and not cv.style_panel._pen_arrow_start.isChecked())
        record("J7b 选中直线显示端点箭头勾选框且回填正确", vis and chk,
               f"可见={vis} 勾选(end)={cv.style_panel._pen_arrow_end.isChecked()}")


# ---------------------------------------------------------------------------
# Stage K — 截屏前隐藏窗口 / 移除样式按钮 / 曲线端点箭头方向
# ---------------------------------------------------------------------------
def test_capture_hygiene_and_curve_arrows() -> None:
    print("\n--- Stage K: 截屏前隐藏窗口 + 样式按钮 + 曲线箭头方向 ---")
    from PySide6.QtWidgets import QApplication, QWidget
    from snapeditor import Toolbar, _path_arclengths, _pen_tangent

    app = QApplication.instance()

    # K1 工具栏不再有「样式」按钮，但样式面板仍可用（选中标注会自动弹出）
    tb = Toolbar()
    ok_k1 = "样式" not in tb._actions
    record("K1 工具栏已移除样式按钮", ok_k1, f"actions={list(tb._actions)}")
    tb.close()

    # K2/K3 曲线整体水平向右，但最后两个采样点斜向上（旧逻辑会取到 45°）
    pts = [QPoint(20, 100), QPoint(60, 100), QPoint(100, 100),
           QPoint(140, 100), QPoint(170, 100), QPoint(171, 100),
           QPoint(172, 99)]
    cum = _path_arclengths(pts)
    ue = _pen_tangent(pts, cum, False, 12.0)
    us = _pen_tangent(pts, cum, True, 12.0)
    ok_k2 = ue[0] > 0.9 and abs(ue[1]) < 0.25
    record("K2 末段抖动不影响终点箭头方向", ok_k2,
           f"终点切线=({ue[0]:.3f},{ue[1]:.3f}) 旧逻辑≈(0.707,-0.707)")
    ok_k3 = us[0] < -0.9 and abs(us[1]) < 0.25
    record("K3 起点箭头方向朝曲线外侧", ok_k3,
           f"起点切线=({us[0]:.3f},{us[1]:.3f})")

    # K4 末段两个采样点完全重合：旧逻辑会退回写死的水平 (1,0) 方向
    pts2 = [QPoint(100, 180), QPoint(100, 150), QPoint(100, 120),
            QPoint(100, 90), QPoint(100, 90)]
    ue2 = _pen_tangent(pts2, _path_arclengths(pts2), False, 12.0)
    ok_k4 = abs(ue2[0]) < 0.15 and ue2[1] < -0.9
    record("K4 末段重合点不退化为水平箭头", ok_k4,
           f"切线=({ue2[0]:.3f},{ue2[1]:.3f})")

    # K5 像素级：同一条走向的曲线，末端有没有抖动点，箭头渲染应几乎一致
    smooth = pts[:5] + [QPoint(172, 100)]   # 抹掉末段抖动，端点改为水平收尾
    base = make_image(260, 200)

    def render(pp) -> QImage:
        return Canvas(base, [Shape(kind="pen", points=list(pp),
                                  color=QColor(255, 0, 0), width=3,
                                  pen_arrow_end=True)], None).compose()

    pa, pb = render(pts), render(smooth)
    region = QRect(148, 82, 34, 38)   # 只比较终点箭头附近
    d_arrow = 0
    for y in range(region.top(), region.bottom()):
        for x in range(region.left(), region.right()):
            if pa.pixelColor(x, y) != pb.pixelColor(x, y):
                d_arrow += 1
    # 实测：新逻辑 70 像素，旧逻辑（只用最后两点定方向）237 像素，
    # 取 120 作为分界，两侧都留足抗锯齿/Qt 版本带来的波动余量
    ok_k5 = d_arrow < 120
    record("K5 箭头方向不受末段抖动带偏（渲染一致）", ok_k5,
           f"抖动/平滑两图箭头区差异像素={d_arrow}")

    # K6 截屏前隐藏本进程全部窗口（含编辑器、浮动面板），并能完整恢复
    import snap as snapmod

    holder = snapmod.App.__new__(snapmod.App)
    holder.app = app
    mw, edw, floatw = QWidget(), QWidget(), QWidget()
    for w in (mw, edw, floatw):
        w.show()
    holder.main_window = mw
    holder.preview = None
    holder.editor = edw
    holder._help_window = None
    holder._about_box = None
    holder.busy = None
    holder._hidden_windows = []
    app.processEvents()

    holder._hide_own_windows()
    hidden = (not mw.isVisible() and not edw.isVisible() and not floatw.isVisible())
    # 模拟等待窗口淡出期间又冒出来的自有窗口（start_capture 的多轮补隐藏）
    late = QWidget()
    late.show()
    holder._hide_visible_own_windows()
    late_hidden = not late.isVisible()
    holder._restore_own_windows()
    restored = all(w.isVisible() for w in (mw, edw, floatw, late))
    record("K6 截屏前隐藏全部自有窗口且可恢复",
           hidden and late_hidden and restored,
           f"隐藏={hidden} 补隐藏={late_hidden} 恢复={restored}")
    for w in (mw, edw, floatw, late):
        w.close()


# ---------------------------------------------------------------------------
# Stage L — 撤销 / 顺旋 / 逆旋 图标可区分性
# ---------------------------------------------------------------------------
def test_undo_rotate_icons() -> None:
    """撤销与逆时针旋转要一眼分开；顺/逆旋必须严格成对（水平镜像）。"""
    from PySide6.QtGui import QPixmap, QPainter
    from snapeditor import _draw_icon, _ICON_SIZE

    S = _ICON_SIZE

    def icon(name):
        pm = QPixmap(S, S)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        _draw_icon(name, p)
        p.end()
        return pm.toImage()

    undo, cw, ccw = icon("撤销"), icon("顺旋"), icon("逆旋")

    def ink(im, x, y):
        return im.pixelColor(x, y).alpha() > 100

    # L1 撤销与逆旋像素差异足够大（旧版同为圆弧箭头，实测仅 154）
    diff = sum(1 for y in range(S) for x in range(S)
               if undo.pixelColor(x, y).rgba() != ccw.pixelColor(x, y).rgba())
    # 形状类别分离：圆环顶部中线有墨、撤销的折线在那里是空的
    shape_ok = (not ink(undo, 13, 5)) and ink(cw, 13, 5) and ink(ccw, 13, 5)
    record("L1 撤销与逆旋图标明显不同", diff > 185 and shape_ok,
           f"差异像素={diff}(旧版154) 形状分离={shape_ok}")

    # L2 顺旋 / 逆旋严格水平镜像
    mismatch = sum(1 for y in range(S) for x in range(S)
                   if ink(cw, x, y) != ink(ccw, S - 1 - x, y))
    record("L2 顺旋与逆旋严格水平镜像", mismatch < 30, f"不匹配像素={mismatch}")

    # L3 旋转图标有中心「图片方块」，撤销是纯线稿、中心留空
    solid = (100 < cw.pixelColor(13, 10).alpha() < 230
             and 100 < ccw.pixelColor(13, 10).alpha() < 230)
    record("L3 旋转含中心方块、撤销为中心留空",
           solid and not ink(undo, 13, 10),
           f"旋转方块={solid} 撤销中心墨={ink(undo, 13, 10)}")

    # L4 撤销折返路径：左下起笔 → 右 → 上 → 左，中间与左侧留空
    corners = all(ink(undo, x, y) for x, y in ((5, 20), (20, 20), (20, 8), (14, 8)))
    hollow = (not ink(undo, 13, 13)) and (not ink(undo, 5, 13))
    record("L4 撤销折返路径方向正确", corners and hollow,
           f"四角有墨={corners} 中间留空={hollow}")

    # L5 旋转箭头尖锐度：三角形半张角必须更小、墨量更少，且实现确实换了
    # （旧版圆弧是圆头，末端半圆会盖住箭头尖；新版在根部平头截断）
    import math
    from PySide6.QtGui import QBrush
    from snapeditor import (_icon_pen, _arrow_at,
                            _ROT_ARROW_SIZE, _ROT_ARROW_WING)

    def arrow_area(size, wing, k=4):
        """4 倍放大单独渲染箭头，量化三角形墨量（几何面积 = size² × wing）。"""
        pm = QPixmap(S * k, S * k)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.scale(k, k)
        p.setPen(_icon_pen(2))
        p.setBrush(Qt.NoBrush)
        a = math.radians(330)
        _arrow_at(p, 13 + 8 * math.cos(a), 13 + 8 * math.sin(a),
                  -math.sin(a), math.cos(a), size=size, wing_ratio=wing)
        p.end()
        im = pm.toImage()
        return sum(1 for y in range(S * k) for x in range(S * k)
                   if im.pixelColor(x, y).alpha() > 100)

    old_area = arrow_area(6.0, 0.62)                     # 旧版半张角 31.8°
    new_area = arrow_area(_ROT_ARROW_SIZE, _ROT_ARROW_WING)
    geom_ok = (_ROT_ARROW_WING <= 0.38 and _ROT_ARROW_SIZE >= 7.0)

    def draw_old_cw(p):
        p.setBrush(Qt.NoBrush)
        p.setPen(_icon_pen(2))
        a = math.radians(330)
        p.drawArc(5, 5, 16, 16, int(40 * 16), int(290 * 16))
        _arrow_at(p, 13 + 8 * math.cos(a), 13 + 8 * math.sin(a),
                  -math.sin(a), math.cos(a), size=6.0, wing_ratio=0.62)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(245, 247, 250, 170)))
        p.drawRect(9, 9, 8, 8)

    pm_o = QPixmap(S, S)
    pm_o.fill(QColor(0, 0, 0, 0))
    po = QPainter(pm_o)
    po.setRenderHint(QPainter.Antialiasing, True)
    draw_old_cw(po)
    po.end()
    old_cw = pm_o.toImage()
    changed = sum(1 for y in range(S) for x in range(S)
                  if old_cw.pixelColor(x, y).rgba() != cw.pixelColor(x, y).rgba())

    record("L5 顺/逆旋箭头更尖（半张角/墨量/平头截断）",
           geom_ok and new_area < old_area * 0.88 and changed > 30,
           f"半张角={math.degrees(math.atan(_ROT_ARROW_WING)):.1f}° "
           f"墨量 {old_area}→{new_area} 与旧版差异={changed}")


# Stage M — 左右 / 上下 镜像图标重设计
# ---------------------------------------------------------------------------
def test_mirror_icons() -> None:
    """镜像图标＝虚线轴 + 两侧互为镜像的实心三角；上下是左右的 90° 旋转。"""
    from PySide6.QtGui import QPixmap, QPainter
    from snapeditor import _draw_icon, _icon_pen, _arrow_at, _ICON_SIZE

    S = _ICON_SIZE

    def render(fn):
        pm = QPixmap(S, S)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        fn(p)
        p.end()
        return pm.toImage()

    def icon(name):
        return render(lambda p: _draw_icon(name, p))

    def old(name):
        def draw(p):
            p.setBrush(Qt.NoBrush)
            p.setPen(_icon_pen(1.5))
            if name == "左右":
                p.drawLine(S / 2, 4, S / 2, S - 4)
                _arrow_at(p, 9, 9, -1, 0)
                _arrow_at(p, S - 9, S - 9, 1, 0)
            else:
                p.drawLine(4, S / 2, S - 4, S / 2)
                _arrow_at(p, 9, 9, 0, -1)
                _arrow_at(p, S - 9, S - 9, 0, 1)
        return render(draw)

    def ink(im, x, y):
        return im.pixelColor(x, y).alpha() > 100

    def diff(a, b):
        return sum(1 for y in range(S) for x in range(S)
                   if a.pixelColor(x, y).rgba() != b.pixelColor(x, y).rgba())

    h, v = icon("左右"), icon("上下")

    # M1 上下是左右绕画布中心旋转 90°，严格成对
    mismatch = sum(1 for y in range(S) for x in range(S)
                   if ink(h, x, y) != ink(v, S - 1 - y, x))
    record("M1 上下与左右严格 90° 旋转成对", mismatch == 0,
           f"不匹配像素={mismatch}")

    # M2 中间是虚线镜像轴：三段有墨、两处断开；左右竖轴、上下横轴
    dash_h = (ink(h, 13, 5) and not ink(h, 13, 9) and ink(h, 13, 13)
              and not ink(h, 13, 16) and ink(h, 13, 20))
    dash_v = (ink(v, 5, 13) and not ink(v, 9, 13) and ink(v, 13, 13)
              and not ink(v, 16, 13) and ink(v, 20, 13))
    record("M2 镜像轴为虚线且方向正确", dash_h and dash_v,
           f"左右竖轴={dash_h} 上下横轴={dash_v}")

    # M3 两侧是实心三角块，一纯白（原图）一淡白（镜像），不再是细线箭头
    solid_h = (h.pixelColor(7, 13).alpha() > 240
               and 140 < h.pixelColor(19, 13).alpha() < 220)
    solid_v = (v.pixelColor(13, 7).alpha() > 240
               and 140 < v.pixelColor(13, 19).alpha() < 220)
    record("M3 两侧为实心三角且原件/镜像分层", solid_h and solid_v,
           f"左右={solid_h} 上下={solid_v}")

    # M4 与圆环绕方块（旋转）、折线（撤销）形状类别分离
    sep = min(diff(h, icon(n)) for n in ("顺旋", "逆旋", "撤销"))
    record("M4 镜像图标与旋转/撤销明显不同", sep > 150,
           f"最小差异像素={sep}")

    # M5 与旧版（对角两个小箭头）相比确实换了设计
    dh, dv = diff(h, old("左右")), diff(v, old("上下"))
    record("M5 与旧版对角箭头图标明显不同", dh > 100 and dv > 100,
           f"左右差异={dh} 上下差异={dv}")


def test_about_and_app_icon():
    """Stage N  关于对话框（头像 / 联系邮箱）与软件图标资源。"""
    from pathlib import Path

    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QLabel, QWidget

    from snapui import (
        ABOUT_HTML,
        ABOUT_AVATAR_HEIGHT,
        APP_ICON_FILE,
        AVATAR_FILE,
        CONTACT_EMAIL,
        AboutDialog,
        make_icon,
        resource_path,
    )

    # N1 资源文件在源码目录就位；打包后由 SnapTool.spec 的 datas 保证
    p_ico, p_avatar = resource_path(APP_ICON_FILE), resource_path(AVATAR_FILE)
    record("N1 头像与 ico 资源文件存在",
           p_ico.is_file() and p_avatar.is_file(),
           f"ico={p_ico.is_file()} avatar={p_avatar.is_file()}")

    # N2 运行时图标来自新的多尺寸 ico，而不是旧版「代码画的相机」
    icon = make_icon()
    sizes = sorted({s.width() for s in icon.availableSizes()})
    ok_n2 = (not icon.isNull()) and 256 in sizes and not icon.pixmap(48, 48).isNull()
    record("N2 运行时图标来自 app.ico（多尺寸）", ok_n2, f"尺寸={sizes}")

    # N3 关于文案含邮箱与可点击的 mailto
    ok_n3 = CONTACT_EMAIL in ABOUT_HTML and f"mailto:{CONTACT_EMAIL}" in ABOUT_HTML
    record("N3 关于文案含邮箱与 mailto 链接", ok_n3, CONTACT_EMAIL)

    # N4 / N5 对话框真的把头像画出来、邮箱可点击
    dlg = AboutDialog(None, icon)
    avatar = dlg.findChild(QLabel, "aboutAvatar")
    text = dlg.findChild(QLabel, "aboutText")
    pm = avatar.pixmap() if avatar is not None else QPixmap()
    ok_n4 = (avatar is not None and not avatar.isHidden() and not pm.isNull()
             and pm.height() == ABOUT_AVATAR_HEIGHT and pm.width() > 100)
    record("N4 关于对话框显示头像且未被裁切", ok_n4,
           f"头像={pm.width()}x{pm.height()} 目标高={ABOUT_AVATAR_HEIGHT}")
    ok_n5 = (text is not None and CONTACT_EMAIL in text.text()
             and text.openExternalLinks())
    record("N5 关于对话框邮箱可见且可点击", ok_n5,
           f"可点击={text.openExternalLinks() if text else False}")

    # N6 打包配置把两个资源都收进发行版，exe 图标指向 app.ico
    spec = (Path(__file__).resolve().parent / "SnapTool.spec").read_text(
        encoding="utf-8"
    )
    ok_n6 = all(k in spec for k in (
        "('app.ico', '.')", "avatar-pan.webp", "icon=['app.ico']",
    ))
    record("N6 打包配置收进头像/ico 且 exe 图标指向 app.ico", ok_n6, "")

    # N7 show_about 用非模态单例，重复打开复用同一窗口
    import snap as snapmod

    holder = snapmod.App.__new__(snapmod.App)
    holder.main_window = QWidget()
    holder._about_box = None
    snapmod.App.show_about(holder)
    box = holder._about_box
    ok_show = isinstance(box, AboutDialog) and box.isVisible()
    snapmod.App.show_about(holder)
    ok_n7 = ok_show and holder._about_box is box
    record("N7 关于窗口为非模态单例且可重复打开", ok_n7,
           f"可见={ok_show} 复用={holder._about_box is box}")

    # N8 截屏前隐藏逻辑能捕获关于窗口，否则它会被拍进截图里
    holder.preview = holder.editor = None
    holder._help_window = None
    holder.busy = None
    holder._hidden_windows = []
    holder._hide_own_windows()
    hidden = not box.isVisible()
    holder._restore_own_windows()
    ok_n8 = hidden and box.isVisible()
    record("N8 截屏前关于窗口会被隐藏并恢复", ok_n8,
           f"隐藏={hidden} 恢复={box.isVisible()}")
    box.hide()


def test_i18n():
    """Stage O  8 种界面语言 + 启动时跟随系统语言 + 即时刷新 + 持久化。"""
    import ast
    import json
    import re
    import tempfile
    from pathlib import Path

    import i18n
    from i18n import LANGS, LANGUAGE_NAMES, ROWS, placeholders
    from i18n_docs import about_html, cli_help, help_html

    # O1 语言表：恰好 8 种，且每种都有本地名 / 英文名
    ok_o1 = (len(LANGS) == 8 and set(LANGS) == set(LANGUAGE_NAMES)
             and all(len(v) == 2 and all(v) for v in LANGUAGE_NAMES.values()))
    record("O1 提供 8 种语言且名称齐全", ok_o1, f"{len(LANGS)} 种: {'/'.join(LANGS)}")

    # O2 每条文案都有 8 个非空译文
    bad_rows = [(k, len(v)) for k, v in ROWS.items()
                if len(v) != len(LANGS) or any(not x for x in v)]
    record("O2 每条 UI 文案都有 8 种译文", not bad_rows,
           f"共 {len(ROWS)} 条，异常 {len(bad_rows)} 条")

    # O3 带占位符的句子，8 种语言占位符必须同名（否则 .format 会漏值）
    bad_ph = [k for k, v in ROWS.items()
              if len({frozenset(placeholders(x)) for x in v}) != 1]
    record("O3 占位符在 8 种语言间一致", not bad_ph, f"不一致 {len(bad_ph)} 条")

    # O4 源码里所有 t("中文") 字面量都能查到译文（静态扫描，防止漏翻）
    used: set[str] = set()
    for fn in Path(__file__).resolve().parent.glob("*.py"):
        if fn.name.startswith(("i18n", "selftest")):
            continue
        for n in ast.walk(ast.parse(fn.read_text(encoding="utf-8"))):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                    and n.func.id in ("t", "_t") and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and isinstance(n.args[0].value, str)):
                used.add(n.args[0].value)
    missing = sorted(used - set(ROWS))
    record("O4 源码中每个 tr 键都有译文", not missing,
           f"字面量键 {len(used)} 个，缺失 {len(missing)} 个")

    # O5 系统语言映射（含繁体地区 / 未支持语言回退英文）
    cases = {
        "zh_CN": "zh_CN", "zh-CN": "zh_CN", "zh_TW": "zh_TW",
        "zh-Hant-TW": "zh_TW", "zh_HK": "zh_TW", "en_US": "en",
        "ja_JP": "ja", "ko_KR": "ko", "fr_FR": "fr", "de_DE": "de",
        "es_ES": "es", "ru_RU": "en",
    }
    wrong = {k: i18n.normalize(k) for k, v in cases.items() if i18n.normalize(k) != v}
    record("O5 系统语言正确映射到 8 种语言", not wrong,
           f"用例 {len(cases)} 个，错误 {wrong}")

    # O6 Windows 显示语言优先于 Qt 区域格式（中文系统 + 英文区域格式）
    ui = i18n.windows_ui_language()
    ok_o6 = (not ui) or (i18n.system_language() == i18n.normalize(ui))
    ok_o6 = ok_o6 and i18n.system_language("ja_JP") == "ja"
    record("O6 跟随系统显示语言（非区域格式）", ok_o6,
           f"UI={ui!r} QLocale={__import__('PySide6.QtCore', fromlist=['QLocale']).QLocale.system().name()} -> {i18n.system_language()}")

    # ---- 下面用临时配置目录，避免污染真实 %APPDATA%\SnapTool ----
    old_home = os.environ.get("SNAPTOOL_HOME")
    old_force = os.environ.get("SNAPTOOL_LANG")
    old_locale = os.environ.get("SNAPTOOL_SYSTEM_LOCALE")
    tmp = tempfile.mkdtemp(prefix="snaptool-i18n-selftest-")
    os.environ["SNAPTOOL_HOME"] = tmp
    os.environ.pop("SNAPTOOL_LANG", None)
    os.environ["SNAPTOOL_SYSTEM_LOCALE"] = "zh_CN"
    cfg = Path(tmp) / "settings.json"
    cfg.write_text(json.dumps({
        "version": 2, "mode": "window", "capture": {"mods": 6, "vk": 65},
    }, ensure_ascii=False), encoding="utf-8")
    i18n.LANG.reload()
    ok_o7a = i18n.LANG.preference == "auto" and i18n.LANG.current == "zh_CN"

    i18n.LANG.set_preference("fr")
    raw = json.loads(cfg.read_text(encoding="utf-8"))
    i18n.LANG.reload()
    ok_o7 = (ok_o7a and raw.get("language") == "fr" and raw.get("mode") == "window"
             and raw.get("capture") == {"mods": 6, "vk": 65}
             and i18n.LANG.preference == "fr" and i18n.LANG.current == "fr")
    record("O7 语言设置写入 settings.json 且不丢其它配置", ok_o7,
           f"language={raw.get('language')} mode={raw.get('mode')}")

    # O8 auto 模式跟随系统（模拟不同系统语言，重启后仍生效）
    auto_ok = True
    for locale, expect in (("ja_JP", "ja"), ("de_DE", "de"),
                           ("zh-Hant-TW", "zh_TW"), ("ru_RU", "en")):
        os.environ["SNAPTOOL_SYSTEM_LOCALE"] = locale
        i18n.LANG.set_preference("auto")
        i18n.LANG.reload()
        auto_ok &= (i18n.LANG.preference == "auto" and i18n.LANG.current == expect)
    record("O8 auto 模式按系统语言启动", auto_ok,
           f"模拟 ja/de/zh-Hant/ru，当前={i18n.LANG.current}")

    # O9 切换语言发信号，已打开的窗口文本立即刷新
    from PySide6.QtWidgets import QApplication

    from hotkeys import Hotkey
    from snapui import AboutDialog, HelpWindow, LanguageDialog, MainWindow, make_icon

    app = QApplication.instance() or QApplication(sys.argv)
    mw = MainWindow(make_icon(), Hotkey(), "rect", Path(tmp))
    mw.show()
    about = AboutDialog(None, make_icon())
    helpw = HelpWindow("help")
    ed = EditorWindow(make_image(160, 100), [], None)
    dlg = LanguageDialog(mw)
    seen: list[str] = []
    i18n.LANG.changed.connect(lambda code: seen.append(code))
    i18n.LANG.set_preference("en")
    app.processEvents()
    ok_o9 = ("en" in seen and mw.windowTitle() == "SnapTool"
             and mw._menus["file"].title() == "File(&F)"
             and mw._actions["quit"].text() == "Exit"
             and ed._menus["edit"].title() == "Edit(&E)"
             and "About SnapTool" in about.windowTitle()
             and "User Guide" in helpw.windowTitle())
    record("O9 切换后主窗口/编辑器/关于/帮助即时刷新", ok_o9,
           f"信号={seen[-1:] if seen else []} 标题={mw.windowTitle()}")

    # O10 英文界面不残留中文 UI 文案（动态文本也一起检查）
    texts = [mw.windowTitle(), mw._sub.text(), mw._tip.text(),
             mw._lbl_now.text(), mw._lbl_hotkey.text(), mw._lbl_mode.text()]
    texts += [m.title() for m in mw._menus.values()]
    texts += [a.text() for a in mw._actions.values()]
    texts += [b.text() for b in mw._mode_buttons.values()]
    texts += [a.text() for a in ed._actions.values()]
    cjk_left = [x for x in texts if re.search(r"[\u4e00-\u9fff]", x)]
    record("O10 英文界面无中文残留", not cjk_left, f"残留 {cjk_left[:2]}")

    # O11 8 种语言的长文档（帮助 8 节 / 关于邮箱 / 命令行参数）齐全
    docs_bad = []
    for code in LANGS:
        h, a, c = help_html(code), about_html(code), cli_help(code)
        if (h.count("<h2>") < 8 or "mailto:283096251@qq.com" not in a
                or "--shot" not in c or "--selftest" not in c):
            docs_bad.append(code)
    record("O11 帮助/关于/命令行 8 语言内容完整", not docs_bad,
           f"异常语言={docs_bad}")

    # O12 设置对话框 9 项（跟随系统 + 8 种），选中即可生效
    codes = [dlg.combo.itemData(i) for i in range(dlg.combo.count())]
    ok_o12 = len(codes) == 9 and set(codes) == {"auto", *LANGS}
    dlg.combo.setCurrentIndex(dlg.combo.findData("ko"))
    dlg._apply()
    ok_o12 = ok_o12 and i18n.LANG.preference == "ko" and i18n.LANG.current == "ko"
    record("O12 语言对话框含跟随系统 + 8 语言且可切换", ok_o12,
           f"选项={len(codes)} 当前={i18n.LANG.current}")

    # O13 拉丁语系译文确实与简体中文不同（抽查高频文案）
    sample = ("打开保存目录", "确定", "端点箭头", "取字", "已复制到剪贴板  {w}×{h}")
    latin = ("en", "fr", "de", "es")
    ok_o13 = all(i18n.LANG.translate(k, c) != ROWS[k][0]
                 for k in sample for c in latin)
    record("O13 译文非中文占位（抽查 4 语种）", ok_o13, f"抽查 {len(sample) * len(latin)} 组")

    # 恢复环境变量与语言，避免影响后续 / 真实配置
    if old_force is None:
        os.environ.pop("SNAPTOOL_LANG", None)
    else:
        os.environ["SNAPTOOL_LANG"] = old_force
    if old_home is None:
        os.environ.pop("SNAPTOOL_HOME", None)
    else:
        os.environ["SNAPTOOL_HOME"] = old_home
    if old_locale is None:
        os.environ.pop("SNAPTOOL_SYSTEM_LOCALE", None)
    else:
        os.environ["SNAPTOOL_SYSTEM_LOCALE"] = old_locale
    i18n.LANG.reload()
    for w in (mw, about, helpw, ed, dlg):
        w.hide()


def test_long_capture() -> None:
    """Stage P  独立「滚动长截图」命令：入口 → 框选 → 确定 → 直接拼接。"""
    import inspect
    import re
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import i18n
    import snap as snapmod
    from PySide6.QtWidgets import QApplication, QPushButton

    from hotkeys import Hotkey
    from i18n_docs import about_html, help_html
    from snapui import ABOUT_HTML, HELP_HTML, MainWindow, make_icon

    app = QApplication.instance() or QApplication(sys.argv)

    # P1 主窗口信号 / 菜单动作 / 按钮都在，且点击真能发出信号
    with TemporaryDirectory(prefix="snaptool-p-") as tmp:
        mw = MainWindow(make_icon(), Hotkey(), "rect", Path(tmp))
        fired: list = []
        mw.long_capture_requested.connect(lambda: fired.append(1))
        has_signal = hasattr(mw, "long_capture_requested")
        a_long = mw._actions.get("long_capture")
        b_long = mw.findChild(QPushButton, "long")
        has_menu = a_long is not None and "滚动" in a_long.text()
        has_btn = b_long is not None and "滚动" in b_long.text()
        if a_long is not None:
            a_long.trigger()
        if b_long is not None:
            b_long.click()
        ok_p1 = has_signal and has_menu and has_btn and len(fired) == 2
        record("P1 主窗口信号/菜单/按钮三处入口齐备且可用", ok_p1,
               f"signal={has_signal} menu={has_menu} btn={has_btn} fired={len(fired)}")

        # P2 切换 8 种语言，按钮与菜单文案即时刷新且英文无中文残留
        bad_lang, cjk_bad = [], []
        for code in i18n.LANGS:
            i18n.LANG.set_preference(code, persist=False)
            app.processEvents()
            btn_text = b_long.text() if b_long is not None else ""
            menu_text = a_long.text() if a_long is not None else ""
            if not (btn_text and menu_text and menu_text in btn_text):
                bad_lang.append(code)
            if code == "en" and re.search(r"[\u4e00-\u9fff]", btn_text + menu_text):
                cjk_bad.append(btn_text)
        ok_p2 = not bad_lang and not cjk_bad
        record("P2 8 语言按钮/菜单即时刷新且英文无残留", ok_p2,
               f"异常语言={bad_lang} 英文残留={cjk_bad[:1]}")
        i18n.LANG.set_preference("zh_CN", persist=False)
        app.processEvents()
        mw.close()

    # P3 Overlay.set_long_mode：强制 rect、清窗口探测、切「确定」提示
    base = make_image(400, 200)
    ov = Overlay(base, dpr=2.0)
    ov.resize(200, 100)
    ov.set_capture_mode("window", lambda p: None)
    ov.set_long_mode(True)
    tip_key = ov.toolbar._tip_keys.get("action:确定")
    ok_p3 = (
        ov.long_mode and ov.capture_mode == "rect"
        and ov._window_picker is None and ov._mode == "idle"
        and tip_key == "开始滚动拼接 (Enter)"
        and ov.toolbar._actions["确定"].toolTip()
        == i18n.LANG.translate("开始滚动拼接 (Enter)")
    )
    record("P3 set_long_mode 强制 rect 并切换确定提示", ok_p3,
           f"mode={ov.capture_mode} tip_key={tip_key}")
    ov.close()

    # P4 长截图模式 _confirm：发 long_shot（逻辑坐标），不发 to_editor
    ov2 = Overlay(base, dpr=2.0)
    ov2.resize(200, 100)
    ov2.set_long_mode(True)
    ov2.sel = QRect(30, 20, 60, 40)
    ov2._mode = "editing"
    got_long, got_editor = [], []
    ov2.long_shot.connect(lambda r: got_long.append(QRect(r)))
    ov2.to_editor.connect(lambda b, sh: got_editor.append(1))
    ov2._confirm()
    ok_p4 = (
        len(got_long) == 1 and not got_editor
        and got_long[0] == QRect(30, 20, 60, 40)
    )
    record("P4 长截图确定发 long_shot 且逻辑坐标不变", ok_p4,
           f"long={len(got_long)} rect={got_long[0] if got_long else None} editor={len(got_editor)}")

    # 过小的选区不应触发拼接
    ov2b = Overlay(base, dpr=2.0)
    ov2b.resize(200, 100)
    ov2b.set_long_mode(True)
    ov2b.sel = QRect(10, 10, 3, 3)
    tiny: list = []
    ov2b.long_shot.connect(lambda r: tiny.append(1))
    ov2b._confirm()
    record("P4b 过小选区不启动拼接", not tiny, f"emitted={len(tiny)}")
    ov2.close(); ov2b.close()

    # P5 普通模式仍走 to_editor（回归）
    ov3 = Overlay(base, dpr=2.0)
    ov3.resize(200, 100)
    ov3.sel = QRect(30, 20, 60, 40)
    ov3._mode = "editing"
    norm_long, norm_editor = [], []
    ov3.long_shot.connect(lambda r: norm_long.append(1))
    ov3.to_editor.connect(lambda b, sh: norm_editor.append(b))
    ov3._confirm()
    ok_p5 = len(norm_editor) == 1 and not norm_long and norm_editor[0].size() == QRect(60, 40, 120, 80).size()
    record("P5 普通截图仍进编辑器（不回归）", ok_p5,
           f"editor={len(norm_editor)} long={len(norm_long)}")
    ov3.close()

    # P6 语言切换后「确定」提示仍用长截图 key
    ov4 = Overlay(base, dpr=2.0)
    ov4.set_long_mode(True)
    i18n.LANG.set_preference("en", persist=False)
    app.processEvents()
    en_tip = ov4.toolbar._actions["确定"].toolTip()
    ok_p6 = en_tip == "Start stitching (Enter)"
    record("P6 语言切换后确定提示仍按长截图文案", ok_p6, f"en={en_tip!r}")
    i18n.LANG.set_preference("zh_CN", persist=False)
    app.processEvents()
    ov4.close()

    # P7 局部逻辑选区 → 屏幕物理矩形（原点可为负、DPR 可为分数）
    r1 = snapmod.overlay_rect_to_screen(QRect(30, 20, 60, 40), QPoint(0, 0), 2.0)
    r2 = snapmod.overlay_rect_to_screen(QRect(30, 20, 60, 40), QPoint(-1920, 100), 1.5)
    ok_p7 = (
        (r1.x, r1.y, r1.w, r1.h) == (60, 40, 120, 80)
        and (r2.x, r2.y, r2.w, r2.h) == (-2835, 180, 90, 60)
    )
    record("P7 坐标换算含虚拟屏原点与 DPR", ok_p7,
           f"r1={(r1.x, r1.y, r1.w, r1.h)} r2={(r2.x, r2.y, r2.w, r2.h)}")

    # P8 start_long_capture 走 window + long_mode；busy / overlay 时不再启动
    holder = snapmod.App.__new__(snapmod.App)
    holder.overlay = None
    holder.busy = None
    calls: list = []
    holder._begin_capture = lambda mode, long_mode: calls.append((mode, long_mode))
    holder.start_long_capture()
    holder.overlay = object()
    holder.start_long_capture()
    holder.overlay = None
    holder.busy = object()
    holder.start_long_capture()
    ok_p8 = calls == [("window", True)]
    record("P8 start_long_capture 走 window+长截图且忙时不重入", ok_p8,
           f"calls={calls}")

    # P9 拼接期间不恢复自有窗口，结束后恢复
    holder2 = snapmod.App.__new__(snapmod.App)
    holder2._ocr_busy = True
    holder2.overlay = None
    restored: list = []
    holder2._restore_own_windows = lambda: restored.append(1)
    holder2._close_overlay(restore=False)
    no_restore = (not restored) and (holder2._ocr_busy is False)
    holder2._close_overlay()
    ok_p9 = no_restore and len(restored) == 1
    record("P9 拼接期间保持隐藏、结束统一恢复", ok_p9,
           f"no_restore={no_restore} restored={len(restored)}")

    # P10 App 已连接主窗口信号 / 托盘动作 / 语言刷新覆盖
    src_init = inspect.getsource(snapmod.App.__init__)
    src_retr = inspect.getsource(snapmod.App._retranslate_tray)
    src_long = inspect.getsource(snapmod.App._on_long_shot)
    ok_p10 = (
        "long_capture_requested.connect(self.start_long_capture)" in src_init
        and 'self._tray_actions["long_capture"]' in src_init
        and '("long_capture", "滚动长截图…")' in src_retr
        and "_close_overlay(restore=False)" in src_long
        and "_restore_own_windows()" in src_long
        and "overlay_rect_to_screen(logical_rect, origin, dpr)" in src_long
    )
    record("P10 信号/托盘/坐标/窗口恢复均已接线", ok_p10,
           f"init={src_init.count('long_capture')} retr={src_retr.count('long_capture')}")

    # P11 关于 8 语言简介 + 邮箱，且无旧简介
    old_words = ("模仿微信", "与微信无关", "不涉及任何逆向")
    bad_about = []
    for code in i18n.LANGS:
        html = about_html(code)
        if ("mailto:283096251@qq.com" not in html
                or any(w in html for w in old_words)
                or "滚动" not in html and "Scroll" not in html and "スクロール" not in html
                and "스크롤" not in html and "défilante" not in html
                and "Scroll-" not in html and "Captura larga" not in html
                and "捲動" not in html):
            bad_about.append(code)
    ok_p11 = (
        "一个自制功能强大的Windows桌面截图软件。" in ABOUT_HTML
        and not bad_about
        and not any(w in ABOUT_HTML for w in old_words)
    )
    record("P11 关于 8 语言简介已替换且邮箱保留", ok_p11,
           f"异常语言={bad_about}")

    # P12 帮助 8 语言均为 9 节，且不再描述旧的工具条入口
    bad_help = []
    for code in i18n.LANGS:
        html = help_html(code)
        if (html.count("<h2>") != 9
                or "9." not in html
                or "工具条「长截图」" in html):
            bad_help.append(code)
    ok_p12 = HELP_HTML.count("<h2>") == 9 and not bad_help
    record("P12 帮助 8 语言均含独立长截图章节且无旧入口", ok_p12,
           f"异常语言={bad_help} zh_h2={HELP_HTML.count('<h2>')}")

    # P13 集成：_begin_capture 真的给新建的 Overlay 打开长截图模式。
    # 用假抓屏 / 假虚拟屏 / 假托盘，避免依赖真实桌面与系统托盘。
    from unittest.mock import MagicMock

    from PIL import Image

    holder3 = snapmod.App.__new__(snapmod.App)
    holder3.app = app
    holder3.tray = MagicMock()
    holder3.overlay = None
    holder3.busy = None
    holder3.preview = None
    holder3.editor = None
    holder3._help_window = None
    holder3._about_box = None
    holder3._workers = []
    holder3._hidden_windows = []
    holder3._ocr_busy = False
    holder3.save_dir = Path(".")
    holder3._hide_own_windows = lambda: None
    holder3._hide_visible_own_windows = lambda: None
    holder3._restore_own_windows = lambda: None
    holder3.main_window = MagicMock()

    orig_grab = snapmod.snapback.grab_all_screens
    orig_vscreen = snapmod.snapback.virtual_screen
    snapmod.snapback.grab_all_screens = lambda: Image.new("RGB", (200, 100), (30, 60, 90))
    snapmod.snapback.virtual_screen = lambda: snapmod.snapback.ScreenRect(-100, -20, 200, 100)
    try:
        holder3._begin_capture("window", True)
        ov_p13 = holder3.overlay
        ok_p13 = (
            ov_p13 is not None and ov_p13.long_mode
            and ov_p13.capture_mode == "window"
            and ov_p13._window_picker is not None
            and ov_p13._mode == "picking"
            and ov_p13.toolbar._tip_keys.get("action:确定") == "开始滚动拼接 (Enter)"
            and holder3._capture_origin is not None
        )
        record("P13 _begin_capture 长截图模式端到端生效（窗口探测）", ok_p13,
               f"overlay={ov_p13 is not None} long_mode={getattr(ov_p13, 'long_mode', None)} "
               f"mode={getattr(ov_p13, 'capture_mode', None)} "
               f"origin={getattr(holder3, '_capture_origin', None)}")
    finally:
        snapmod.snapback.grab_all_screens = orig_grab
        snapmod.snapback.virtual_screen = orig_vscreen
        if holder3.overlay is not None:
            holder3.overlay.close()
            holder3.overlay = None

    # 恢复语言偏好，避免影响后续 / 真实配置
    i18n.LANG.set_preference("zh_CN", persist=False)
    app.processEvents()


def test_long_capture_v17() -> None:
    """Stage Q  选窗口式滚动长截图：左键暂停/继续、右键或打勾结束、到底自动结束。"""
    import time
    from pathlib import Path
    from tempfile import TemporaryDirectory

    import i18n
    import snap as snapmod
    import numpy as np
    from PIL import Image
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QKeyEvent, QMouseEvent
    from PySide6.QtWidgets import QApplication, QPushButton

    from hotkeys import Hotkey
    from i18n_docs import help_html
    from snapui import HELP_HTML, MainWindow, make_icon

    app = QApplication.instance() or QApplication(sys.argv)
    sb = snapmod.snapback

    def press(widget, button, x=50, y=50) -> None:
        ev = QMouseEvent(
            QEvent.MouseButtonPress, QPointF(x, y), QPointF(x, y),
            button, button, Qt.NoModifier,
        )
        widget.mousePressEvent(ev)

    # ---------------- Q1~Q6  ScrollControl 按键边沿与暂停语义 ----------------
    orig_key, orig_pos = sb.is_key_pressed, sb.get_cursor_pos
    state = {"l": False, "r": False, "pos": (9999, 9999)}
    sb.is_key_pressed = lambda vk: state["l"] if vk == sb.VK_LBUTTON else state["r"]
    sb.get_cursor_pos = lambda: state["pos"]
    try:
        c = sb.ScrollControl()
        c.poll()                      # 建立基线
        state["l"] = True; c.poll()  # 上升沿 → 暂停
        paused1 = c.paused
        c.poll()                      # 按住不放，不重复切换
        paused2 = c.paused
        state["l"] = False; c.poll()
        state["l"] = True; c.poll()  # 再按 → 继续
        paused3 = c.paused
        record("Q1 左键按下沿切换暂停/继续且按住不重复触发",
               paused1 and paused2 and not paused3,
               f"pause={paused1} hold={paused2} resume={not paused3}")

        c2 = sb.ScrollControl()
        c2.poll()
        state["r"] = True; c2.poll()
        record("Q2 右键按下沿结束且原因正确",
               c2.should_stop() and c2.stop_reason == "user-right-click",
               f"reason={c2.stop_reason}")
        state["r"] = False

        c3 = sb.ScrollControl()
        c3.request_stop("user-confirm")
        c3.request_stop("other")
        record("Q3 点确定结束且幂等",
               c3.should_stop() and c3.stop_reason == "user-confirm",
               f"reason={c3.stop_reason}")

        c4 = sb.ScrollControl(exclude_rect=sb.ScreenRect(0, 0, 100, 100))
        state["pos"], state["l"], state["r"] = (50, 50), False, False
        c4.poll()
        state["l"] = True; c4.poll(); state["l"] = False; c4.poll()
        state["r"] = True; c4.poll(); state["r"] = False
        filtered = (not c4.paused) and (not c4.should_stop())
        state["pos"] = (300, 300)
        state["l"] = True; c4.poll(); state["l"] = False
        record("Q4 点在控制条上不触发暂停/结束，移出后正常生效",
               filtered and c4.paused, f"filtered={filtered} after={c4.paused}")

        state["l"], state["r"], state["pos"] = True, False, (9999, 9999)
        c5 = sb.ScrollControl()
        c5.poll()                     # baseline = 左键仍按住
        ignored = not c5.paused
        state["l"] = False; c5.poll()
        state["l"] = True; c5.poll()
        record("Q5 选窗口时仍按住的左键被忽略，下一次点击才暂停",
               ignored and c5.paused, f"baseline_ignored={ignored} next={c5.paused}")
        state["l"] = False

        c6 = sb.ScrollControl()
        t0 = time.monotonic(); c6.wait_while_paused(); quick = time.monotonic() - t0 < 0.1
        c6._paused = True
        c6.request_stop("user-confirm")
        t0 = time.monotonic(); c6.wait_while_paused(); quick2 = time.monotonic() - t0 < 0.1
        record("Q6 wait_while_paused 未暂停 / 已结束时立即返回", quick and quick2,
               f"quick={quick} stopped={quick2}")
    finally:
        sb.is_key_pressed, sb.get_cursor_pos = orig_key, orig_pos

    # ---------------- Q7~Q8  stitch_scroll 集成（假抓屏 / 假滚轮） ----------------
    names = ("grab_region", "find_vertical_overlap", "_send_mouse_wheel",
             "get_cursor_pos", "set_cursor_pos")
    orig = {n: getattr(sb, n) for n in names}
    frame = np.full((40, 60, 3), 180, dtype=np.uint8)
    holder = {"grabs": 0, "wheels": 0, "before": 0, "after": 0, "paused_grabs": []}
    ctrl = sb.ScrollControl()
    changes: list = []
    ctrl.set_on_change(lambda: changes.append(ctrl.snapshot()))
    ticks = {"n": 0}
    # 每次 poll 读两次按键（左、右）；首轮还额外读两次建立基线
    seq = [
        (False, False),  # baseline
        (True, False),   # 左键按下 → 暂停
        (True, False),   # 按住
        (False, False),  # 松开
        (True, False),   # 再按 → 继续
        (False, False),
        (False, True),   # 右键 → 结束
    ]

    def scripted_key(vk: int) -> bool:
        ticks["n"] += 1
        idx = min((ticks["n"] - 1) // 2, len(seq) - 1)
        return seq[idx][0] if vk == sb.VK_LBUTTON else seq[idx][1]

    def fake_grab(_rect):
        holder["grabs"] += 1
        holder["paused_grabs"].append(ctrl.paused)
        return Image.fromarray(frame)

    def bump_before(): holder["before"] += 1
    def bump_after(): holder["after"] += 1

    try:
        sb.grab_region = fake_grab
        sb.find_vertical_overlap = lambda a, b: (0, 0.99)
        sb._send_mouse_wheel = lambda n: holder.__setitem__("wheels", holder["wheels"] + 1)
        sb.get_cursor_pos = lambda: (0, 0)
        sb.set_cursor_pos = lambda x, y: None
        sb.is_key_pressed = scripted_key
        img, stats = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 60, 40),
            settle_seconds=0,
            control=ctrl,
            on_before_grab=bump_before,
            on_after_grab=bump_after,
        )
        had_pause = any(s[0] and not s[1] for s in changes)   # 真正进入过暂停
        had_resume = any(not s[0] and not s[1] for s in changes)
        ok_q7 = (
            not any(holder["paused_grabs"])       # 抓帧时绝不处于暂停
            and had_pause and had_resume           # 左键暂停 / 再点继续
            and ctrl.should_stop()
            and stats["stop_reason"] == "user-right-click"
            and stats["frames"] == holder["grabs"] >= 1   # 结束后没有多抓一帧
            and holder["wheels"] <= holder["grabs"]
            and holder["before"] == holder["after"] == holder["grabs"]
            and img.height >= 40
        )
        record("Q7 暂停期间不抓帧、左键继续、右键结束且隐藏钩子成对调用", ok_q7,
               f"grabs={holder['grabs']} wheels={holder['wheels']} "
               f"before={holder['before']} after={holder['after']} "
               f"pause={had_pause} resume={had_resume} "
               f"reason={stats['stop_reason']} paused_grabs={holder['paused_grabs']}")

        # Q8 滚到底：overlap 只剩 10 行新增 → reached-bottom 自动结束
        holder.update(grabs=0, wheels=0, before=0, after=0)
        sb.find_vertical_overlap = lambda a, b: (max(0, a.shape[0] - 10), 0.99)
        img2, stats2 = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 60, 40),
            settle_seconds=0,
            on_before_grab=bump_before,
            on_after_grab=bump_after,
        )
        ok_q8 = (
            stats2["stop_reason"] == "reached-bottom"
            and holder["grabs"] == 2
            and holder["before"] == holder["after"] == 2
            and img2.height == 40
        )
        record("Q8 滚到底自动结束且抓帧钩子成对调用", ok_q8,
               f"reason={stats2['stop_reason']} grabs={holder['grabs']} "
               f"hooks={holder['before']}/{holder['after']}")
    finally:
        for n, fn in orig.items():
            setattr(sb, n, fn)
        sb.is_key_pressed = orig_key

    # ---------------- Q9~Q10  控制条几何 ----------------
    screen = QRect(0, 0, 1920, 1080)
    sel = QRect(300, 200, 800, 600)
    pos = snapmod.place_bar_outside(sel, screen, 510, 72)
    ok_place = (
        pos is not None and screen.contains(pos) and not pos.intersects(sel)
    )
    full = snapmod.place_bar_outside(QRect(0, 0, 1920, 1080), screen, 510, 72) is None
    neg_screen = QRect(-1920, 0, 3840, 1080)
    neg_sel = QRect(-1800, 100, 1600, 800)
    pos2 = snapmod.place_bar_outside(neg_sel, neg_screen, 510, 72)
    ok_neg = pos2 is not None and neg_screen.contains(pos2) and not pos2.intersects(neg_sel)
    record("Q9 控制条避开窗口、全屏返回 None、负原点多显示器可用",
           ok_place and full and ok_neg,
           f"normal={ok_place} fullscreen_no_place={full} negative_origin={ok_neg}")

    bar_q = snapmod.BusyBar()
    bar_q.move(100, 50)
    br = snapmod.bar_screen_rect(bar_q, 2.0)
    ok_q10 = (br.x, br.y, br.w, br.h) == (200, 100, 1020, 144)
    record("Q10 bar_screen_rect 按 DPR 换算物理矩形", ok_q10,
           f"{(br.x, br.y, br.w, br.h)}")

    # ---------------- Q11~Q12  Overlay 选窗口即启动 ----------------
    base = make_image(400, 200)
    picker = lambda p: (QRect(20, 20, 120, 80), "测试窗口")
    ov_q = Overlay(base, dpr=1.0)
    ov_q.resize(400, 200)
    ov_q.set_long_mode(True, picker)
    mode_ok = (
        ov_q.long_mode and ov_q.capture_mode == "window"
        and ov_q._mode == "picking" and ov_q._window_picker is not None
    )
    got_q, got_editor_q = [], []
    ov_q.long_shot.connect(lambda r: got_q.append(QRect(r)))
    ov_q.to_editor.connect(lambda b, sh: got_editor_q.append(1))
    press(ov_q, Qt.LeftButton, 50, 50)
    ok_q11 = (
        mode_ok and len(got_q) == 1 and got_q[0] == QRect(20, 20, 120, 80)
        and not got_editor_q and ov_q.sel is None and ov_q._mode == "picking"
    )
    record("Q11 单击窗口直接发 long_shot 且不进编辑态", ok_q11,
           f"mode={ov_q.capture_mode} long={len(got_q)} "
           f"rect={got_q[0] if got_q else None} editor={len(got_editor_q)}")

    ov_q2 = Overlay(base, dpr=1.0)
    ov_q2.resize(400, 200)
    ov_q2.set_long_mode(True, picker)
    ov_q2._hover_rect = QRect(30, 30, 100, 70)
    enter_got, cancelled = [], []
    ov_q2.long_shot.connect(lambda r: enter_got.append(QRect(r)))
    ov_q2.cancelled.connect(lambda: cancelled.append(1))
    ov_q2.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    ov_q3 = Overlay(base, dpr=1.0)
    ov_q3.resize(400, 200)
    ov_q3.set_long_mode(True, picker)
    cancelled3 = []
    ov_q3.cancelled.connect(lambda: cancelled3.append(1))
    press(ov_q3, Qt.RightButton)
    record("Q12 Enter 直接启动、右键取消",
           len(enter_got) == 1 and len(cancelled) == 0 and len(cancelled3) == 1,
           f"enter={len(enter_got)} right_cancel={len(cancelled3)}")

    # ---------------- Q13  客户区取窗口 ----------------
    holder_app = snapmod.App.__new__(snapmod.App)
    ov_pick = Overlay(base, dpr=1.0)
    ov_pick.resize(400, 200)
    ov_pick.move(-100, -20)
    holder_app.overlay = ov_pick
    orig_win = sb.window_rect_at
    sb.window_rect_at = lambda x, y: sb.WindowInfo(
        sb.ScreenRect(0, 0, 400, 300), "T", 1,
        sb.ScreenRect(10, 30, 380, 260),
    )
    try:
        full_q = holder_app._pick_window(QPoint(50, 50))
        client_q = holder_app._pick_window(QPoint(50, 50), client=True)
    finally:
        sb.window_rect_at = orig_win
    ok_q13 = (
        full_q is not None and client_q is not None
        and client_q[0] != full_q[0]
        and client_q[0].x() > full_q[0].x()
        and client_q[0].width() < full_q[0].width()
    )
    record("Q13 _pick_window(client=True) 用客户区而非完整边框", ok_q13,
           f"full={full_q[0] if full_q else None} client={client_q[0] if client_q else None}")

    # ---------------- Q14  BusyBar 控制条 ----------------
    fired = []
    bar_q.finish_clicked.connect(lambda: fired.append(1))
    bar_q.finish_btn.click()
    btn_ok = bool(fired) and ("确定" in bar_q.finish_btn.text() or "✓" in bar_q.finish_btn.text())
    bar_q.set_paused(True)
    paused_text = "暂停" in bar_q.title.text()
    bar_q.set_paused(False)
    running_text = "正在" in bar_q.title.text()
    bar_q.update_text(3, 2400)
    detail_ok = "3" in bar_q.detail.text() and "2400" in bar_q.detail.text()
    bad_lang_q = []
    for code in i18n.LANGS:
        i18n.LANG.set_preference(code, persist=False)
        app.processEvents()
        if not (bar_q.finish_btn.text() and bar_q.hint.text() and bar_q.title.text()):
            bad_lang_q.append(code)
    i18n.LANG.set_preference("zh_CN", persist=False)
    app.processEvents()
    record("Q14 控制条有确定✓、暂停状态、帧数、8 语言即时刷新",
           btn_ok and paused_text and running_text and detail_ok and not bad_lang_q,
           f"btn={btn_ok} paused={paused_text} running={running_text} "
           f"detail={detail_ok} bad_lang={bad_lang_q}")

    # ---------------- Q15  8 语言帮助 / 词条 ----------------
    keywords = ("左键", "左鍵", "left-click", "左クリック", "왼쪽 클릭",
                "clic gauche", "Linksklick", "clic izquierdo")
    stale = ("工具条「长截图」", "Drag to select", "按住鼠标左键框选",
             "按住滑鼠左鍵框選", "Faites glisser pour choisir",
             "Mit Ziehen den scrollenden", "Arrastre para elegir")
    bad_help_q = []
    for code in i18n.LANGS:
        h = help_html(code) if code != "zh_CN" else HELP_HTML
        if (h.count("<h2>") != 9
                or not any(k in h for k in keywords)
                or any(s in h for s in stale)):
            bad_help_q.append(code)
    new_keys = (
        "点击窗口后自动滚动拼接成长图",
        "单击选择要截长屏的窗口，自动向下滚屏    右键 / Esc 取消",
        "已暂停 · 左键继续", "已拼 {frames} 帧 · {height}px", "确定 ✓",
        "左键暂停 / 继续 · 右键结束 · 点「确定」结束    Esc 结束",
        "已滚动到底，长截图自动结束",
    )
    keys_ok = all(len(i18n.ROWS.get(k, ())) == 8 for k in new_keys)
    record("Q15 8 语言帮助描述新流程、无旧入口且新词条齐全",
           not bad_help_q and keys_ok,
           f"bad_help={bad_help_q} keys_ok={keys_ok}")

    # ---------------- Q16  Worker 接线 ----------------
    import inspect
    w = snapmod.StitchWorker(sb.ScreenRect(0, 0, 10, 10))
    src_long = inspect.getsource(snapmod.App._on_long_shot)
    ok_q16 = (
        isinstance(w.control, sb.ScrollControl)
        and hasattr(w, "state_changed") and w.before_grab is None
        and "finish_clicked.connect" in src_long
        and "set_exclude_rect" in src_long
        and "make_bar_hook" in src_long
        and "place_bar_outside" in src_long
    )
    record("Q16 Worker 带控制器且控制条信号/隐藏钩子已接线", ok_q16,
           f"control={type(w.control).__name__} hooks={w.before_grab is None}")

    # ---------------- Q17  主窗口副标题 ----------------
    with TemporaryDirectory(prefix="snaptool-q-") as tmp:
        mw_q = MainWindow(make_icon(), Hotkey(), "rect", Path(tmp))
        b_long_q = mw_q.findChild(QPushButton, "long")
        zh_ok = b_long_q is not None and "点击窗口后自动滚动" in b_long_q.text()
        i18n.LANG.set_preference("en", persist=False)
        app.processEvents()
        en_ok = b_long_q is not None and "Click a window" in b_long_q.text()
        i18n.LANG.set_preference("zh_CN", persist=False)
        app.processEvents()
        mw_q.close()
    record("Q17 主窗口按钮副标题改为点击窗口后自动滚动", zh_ok and en_ok,
           f"zh={zh_ok} en={en_ok}")

    for wgt in (ov_q, ov_q2, ov_q3, ov_pick, bar_q):
        wgt.close()
        wgt.deleteLater()
    app.processEvents()


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
    test_image_transform()
    test_pen_arrows()
    test_single_instance()
    test_toolbar_transform()
    test_line_and_icons()
    test_capture_hygiene_and_curve_arrows()
    test_undo_rotate_icons()
    test_mirror_icons()
    test_about_and_app_icon()
    test_i18n()
    test_long_capture()
    test_long_capture_v17()

    print("=" * 66)
    failed = [n for n, s, _ in results if s == FAIL]
    print(f"合计 {len(results)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项：" + "、".join(failed))
    sys.exit(1 if failed else 0)
