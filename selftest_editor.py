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

  Stage R  马赛克不弹样式面板
    R1  Canvas / Overlay 的 _style_panel_allowed 判定正确
    R2  Canvas 画完马赛克自动选中不弹面板，普通标注仍弹出
    R3  Overlay 选中马赛克不弹面板，普通标注仍弹出
    R4  切到马赛克工具立刻收起已开面板，手动打开也被拦住
    R5  OCR 结束恢复编辑态时，马赛克不会重新弹出面板

  Stage S  v19：长截图抗中断 / 透明色与填充 alpha / 画布视图放缩
    S1  单帧「几乎没动」不会立刻判到底，会重试后继续拼接
    S2  匹配失败先重试再继续，不一帧就放弃
    S3  连续失败超过上限才以 match-failed 结束
    S4  一次滚过头时自适应减小滚轮步长
    S5  模板偏移换算回 frame 第 0 行位置（避开固定顶栏）
    S6  每帧滚轮前重新锁定光标，滚轮次数不超过定位次数
    S7  控制条显示最近一次匹配分数
    S8  透明线条画出来确实没有边框像素
    S9  文字标注隐藏透明色块，封闭图形显示
    S10 填充透明度滑块回填与修改都正确
    S11 文字编辑框对透明色做前景色兜底
    S12 放缩以鼠标为锚点，导出仍是全分辨率
    S13 视图菜单 4 项含快捷键且 8 语言刷新、状态栏显示比例
    S14 放大 / 缩小 / 1:1 / 适应窗口倍率正确
    S15 中键拖动画布平移且不改变显示比例

  Stage T  v20：长截图画质（浮层 / 缝隙）
    T1  只隐藏与选区相交的小浮层，主窗口 / 窗口外 / 本进程排除
    T2  非 Windows 环境浮层处理静默降级
    T3  浮层每帧压住、结束恢复，统计字段齐全
    T4  抓帧异常时浮层仍被恢复
    T5  捕获区底部预留安全行、光标停在右侧滚动条
    T6  带固定浮层仍能精确对齐
    T7  假相关峰值被重叠区一致性验证纠正
    T8  重叠区行差分辨正确对齐与 3px 错位
    T9  到底时重叠不足 8 行不误伤匹配分数
    T10 README 已记录 v20 画质修复
    T11 滚到底后补抓完整画面，长图不缺尾

  Stage W  v23：文字背景透明度 + 文字背景边框
    W1  文字背景边框默认值齐全
    W2  文字背景透明度 25% 与 100% 渲染不同
    W3  填充透明度与背景透明度各自独立
    W4  启用边框后出现描边像素
    W5  边框颜色设为透明等于不描边
    W6  边框线宽 1 与 8 像素量不同
    W7  边框实线 / 虚线 / 点线各不相同
    W8  无背景色时也能单独显示边框
    W9  旋转文字时边框一起转且位置正确
    W10 面板启用边框 / 预设色 / ∅ 透明信号正确
    W11 面板状态回填颜色 / 透明度 / 线宽 / 线型
    W12 Canvas 选中标注与新建默认值都写入新键
    W13 Overlay 同样写入新键
    W14 克隆 / 撤销恢复边框全部字段
    W15 README / 中文帮助 / 7 语言帮助 / 8 语言词条同步

  Stage X  v24：文字输入位置（输入框左上角与文字基线对齐）
    X1  左上角→基线偏移随字号增长且非零
    X2  各字号输入框文字与提交后绘制像素重合
    X3  回归锁定：旧写法会让文字上跳 ≥15px
    X4  双击编辑时输入框盖在原字上、提交后坐标不变
    X5  窗口编辑器 1:1 视图：提交后文字像素不位移
    X6  放大 / 缩小视图下按屏幕字号换算仍对齐
    X7  双击编辑（含旋转文字）输入框落点正确、坐标不漂移
    X8  高 DPI 遮罩逻辑 / 物理坐标换算不丢偏移
    X9  连续输入互不干扰、撤销恢复正确位置
    X10 README / 中文帮助 / 7 语言帮助同步

  Stage Y  v25：绿色版体积优化（只改打包配置的回归）
    Y1  spec 保留冗余文件过滤规则
    Y2  过滤规则不误伤必需依赖
    Y3  optimize=0（numpy docstring 回归锁定）
    Y4  README 同步 v25 体积数字

  Stage Z  v26：确认阶段「复制」按钮（只复制原图，不进编辑器）
    Z1  确认模式显示复制按钮，且排在确定 / ✕ 最左
    Z2  点复制发出的是原图（不含标注），尺寸 / 像素正确
    Z3  点复制不发 to_editor、遮罩确认态已复位
    Z4  App 收到信号后写剪贴板并关闭遮罩
    Z5  全屏直截 / 长截图完成路径也自动复制原图
    Z6  README / 中文帮助 / 7 语言帮助同步

  Stage V  v22：矩形 / 椭圆 / 文字旋转
    V1  角度归一化与旋转变换往返
    V2  文字包围盒 / 旋转外接框 / 旋转中心
    V3  旋转后四角点、命中与外接框
    V4  旋转柄位置与命中（不可旋转标注排除）
    V5  拖动转角、跨 ±180 不跳变、Shift 吸附 15°
    V6  draw_shape 真的按角度绘制不同像素
    V6b 旋转文字像素中心贴合包围盒中心（字形路径绘制）
    V7  Canvas 拖旋转柄改角度、状态复位
    V8  Canvas Shift 吸附
    V9  菜单 90° 步进 + 样式面板角度回填
    V10 Canvas 文字可旋转、角度控件可见
    V11 Overlay 拖旋转柄，选区不变
    V12 旋转后四角缩放用局部坐标，不漂移
    V13 整图旋转时文字 ±90°、矩形角度不变、镜像取负、撤销恢复
    V14 画布放缩后旋转柄命中范围按显示比例反算
    V15 马赛克不出现旋转柄 / 不受角度影响
    V16 README / 中文帮助 / 7 语言帮助 / 8 语言词条同步

  Stage U  v21：矩形 / 椭圆四角拖柄缩放
    U1  四角点坐标与顺序（nw/ne/se/sw）
    U2  四角命中、中心 / 半径外 / 空矩形不误命中
    U3  拖任一角时对角精确固定，翻转不偏 1px
    U4  最小尺寸、拖过对角翻转、非法角原样返回
    U5  四角斜向缩放光标
    U6  Canvas 画完自动选中并显示 4 个角柄
    U7  Canvas 拖 se 角放大、状态复位、导出全分辨率
    U8  Canvas 椭圆拖 nw 角同样可缩放
    U9  Canvas 翻转后仍保持最小可编辑形状
    U10 画布放大 2 倍后命中仍准确
    U11 马赛克 / 箭头无四角柄，箭头端点拉伸未回归
    U12 Overlay 拖角只改图形，不改选区
    U13 Overlay 角点限制在选区内、马赛克无四角柄
    U14 两个编辑器绘制控制柄不抛异常
    U15 README / 中文帮助 / 7 语言帮助同步

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
    #     v26 起确认模式多一个「复制」、v34 再加「钉在桌面」，工具条更宽；
    #     小遮罩上 near+14 放不下时会被贴边收缩，因此 x 允许「光标右下」或「右贴边」两种。
    ov4.sel = QRect(50, 40, 60, 30)
    ov4._apply_selection(QRect(50, 40, 60, 30), near=QPoint(40, 40))
    g3 = ov4.toolbar.geometry()
    ok_b4c = (
        ov4._confirm_mode is True
        and g3.x() in (40 + 14, 200 - g3.width())
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
    from PySide6.QtCore import QRectF, QSize
    from snapeditor import shape_text_box

    W, H = 160, 90
    # 文字标注现在按「包围盒中心」映射（v22），旧断言里的基线起点不再适用
    text_center0 = QRectF(
        shape_text_box(Shape(kind="text", text="测试", pos=QPoint(20, 40)))
    ).center()

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
        and mo.rect == QRect(40, 70, 20, 20)
        # 文字：中心按 cw 公式映射，字形跟着转 90°（不再保持水平）
        and abs(tx.angle - 90.0) < 0.01
        and abs(QRectF(shape_text_box(tx)).center().x()
                - (H - 1 - text_center0.y())) <= 1.0
        and abs(QRectF(shape_text_box(tx)).center().y() - text_center0.x()) <= 1.0
    )
    record(
        "F2 标注坐标随整图变换（文字中心映射 + 字形旋转 90°）",
        ok_f2,
        f"rect={r.rect} arrow=({ar.start},{ar.end}) pen={pn.points[0]} "
        f"text=({tx.pos.x()},{tx.pos.y()}) angle={tx.angle}",
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
        # 文字中心按镜像公式映射；镜像不产生反字，角度只取负
        and abs(c3.shapes[3].angle) < 0.01
        and abs(c4.shapes[3].angle) < 0.01
        and abs(QRectF(shape_text_box(c3.shapes[3])).center().x()
                - (W - 1 - text_center0.x())) <= 1.0
        and abs(QRectF(shape_text_box(c4.shapes[3])).center().y()
                - (H - 1 - text_center0.y())) <= 1.0
    )
    record(
        "F4 镜像后标注坐标（文字中心映射，字形保持可读）",
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
        if (html.count("<h2>") != 10       # v34 新增第 10 节「贴图钉在桌面」
                or "9." not in html
                or "工具条「长截图」" in html):
            bad_help.append(code)
    ok_p12 = HELP_HTML.count("<h2>") == 10 and not bad_help
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
        sb.find_vertical_overlap = lambda a, b, **kw: (0, 0.99)
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
            hide_overlays=False, bottom_guard=0,
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

        # Q8 滚到底：新增行连续 3 帧都几乎为 0 才判到底（v19 抗误判）
        holder.update(grabs=0, wheels=0, before=0, after=0)
        sb.find_vertical_overlap = lambda a, b, **kw: (max(0, a.shape[0] - 10), 0.99)
        img2, stats2 = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 60, 40),
            settle_seconds=0,
            on_before_grab=bump_before,
            on_after_grab=bump_after,
            hide_overlays=False, bottom_guard=0,
        )
        ok_q8 = (
            stats2["stop_reason"] == "reached-bottom"
            and holder["grabs"] == 4          # 首帧 + 连续 3 帧确认，不再一帧就收工
            and holder["before"] == holder["after"] == 4
            and img2.height == 40
            and stats2["retries"] == 2
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
        if (h.count("<h2>") != 10          # v34 新增第 10 节贴图
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


def test_mosaic_style_panel() -> None:
    """Stage R：马赛克工具 / 马赛克标注都不弹样式面板，普通标注不回归。"""
    app = QApplication.instance()
    base = make_image(400, 300)

    def shown(panel) -> bool:
        # 离屏下父窗口未必可见，isVisible() 会连带返回 False；
        # isHidden() 只反映显式 show/hide，正好用来断言「弹出意图」。
        return not panel.isHidden()

    mos = Shape(kind="mosaic", rect=QRect(20, 20, 80, 60))
    rect = Shape(kind="rect", rect=QRect(120, 20, 80, 60))

    cv = Canvas(base, [], None)
    ov = Overlay(base, dpr=1.0)
    ov.sel = QRect(10, 10, 300, 200)

    # R1 允许判定：默认允许；马赛克工具 / 选中马赛克不允许；其它标注允许
    ok_r1 = cv._style_panel_allowed() and ov._style_panel_allowed()
    cv._set_tool("mosaic")
    ov._set_tool("mosaic")
    ok_r1 &= not cv._style_panel_allowed() and not ov._style_panel_allowed()
    cv._set_tool("select")
    ov._set_tool("select")
    cv._selected = ov._selected = mos
    ok_r1 &= not cv._style_panel_allowed() and not ov._style_panel_allowed()
    cv._selected = ov._selected = rect
    ok_r1 &= cv._style_panel_allowed() and ov._style_panel_allowed()
    record("R1 马赛克工具/标注被样式面板过滤，普通标注保留", ok_r1,
           f"canvas={cv._style_panel_allowed()} overlay={ov._style_panel_allowed()}")

    # R2 窗口编辑器：画完马赛克自动选中不弹，普通标注仍自动弹出
    cv._selected = None
    cv._on_select_changed()
    cv._selected = mos
    cv._on_select_changed()
    mos_hidden = cv.style_panel.isHidden()
    cv._selected = rect
    cv._on_select_changed()
    rect_shown = shown(cv.style_panel)
    record("R2 Canvas 马赛克自动选中不弹面板、矩形仍弹出", mos_hidden and rect_shown,
           f"mosaic_hidden={mos_hidden} rect_shown={rect_shown}")

    # R3 遮罩编辑器：同样的行为
    ov._selected = mos
    ov._on_select_changed()
    ov_mos_hidden = ov.style_panel.isHidden()
    ov._selected = rect
    ov._on_select_changed()
    ov_rect_shown = shown(ov.style_panel)
    record("R3 Overlay 马赛克自动选中不弹面板、矩形仍弹出",
           ov_mos_hidden and ov_rect_shown,
           f"mosaic_hidden={ov_mos_hidden} rect_shown={ov_rect_shown}")

    # R4 切到马赛克工具立刻收起已开面板；手动打开（菜单 / 工具条）也被拦住
    before = shown(cv.style_panel) and shown(ov.style_panel)
    cv._set_tool("mosaic")
    ov._set_tool("mosaic")
    after_tool = cv.style_panel.isHidden() and ov.style_panel.isHidden()
    cv._toggle_style_panel()
    ov._toggle_style_panel()
    after_toggle = cv.style_panel.isHidden() and ov.style_panel.isHidden()
    cv._selected = ov._selected = mos
    cv._set_tool("select")
    ov._set_tool("select")
    cv._toggle_style_panel()
    ov._toggle_style_panel()
    after_sel = cv.style_panel.isHidden() and ov.style_panel.isHidden()
    record("R4 切工具收起面板 + 手动入口也被拦截",
           before and after_tool and after_toggle and after_sel,
           f"before={before} tool={after_tool} toggle={after_toggle} selected={after_sel}")

    # R5 取字结束恢复编辑态时，不会把面板重新弹回马赛克上
    cv._selected = ov._selected = mos
    cv._hide_ocr_panel()
    ov.hide_ocr_panel()
    hidden_mos = cv.style_panel.isHidden() and ov.style_panel.isHidden()
    cv._selected = ov._selected = rect
    cv._hide_ocr_panel()
    ov.hide_ocr_panel()
    shown_rect = shown(cv.style_panel) and shown(ov.style_panel)
    record("R5 OCR 恢复时马赛克不弹、普通标注仍弹", hidden_mos and shown_rect,
           f"mosaic_hidden={hidden_mos} rect_shown={shown_rect}")

    cv.close()
    ov.close()
    cv.deleteLater()
    ov.deleteLater()
    app.processEvents()


def test_v19_features() -> None:
    """Stage S：长截图抗中断 / 透明色与填充 alpha / 画布视图放缩。"""
    import numpy as np
    from PIL import Image

    import i18n
    import snap as snapmod
    import snapback as sb
    from snapeditor import StylePanel, _text_edit_color, draw_shape

    app = QApplication.instance()

    # ---------------- S1~S4 / S6  拼接抗中断（假抓屏、假滚轮） ----------------
    names = ("grab_region", "find_vertical_overlap", "_send_mouse_wheel",
             "get_cursor_pos", "set_cursor_pos")
    orig = {n: getattr(sb, n) for n in names}

    def run(finder, *, frame_h: int = 200, max_frames: int = 5):
        frame = np.full((frame_h, 60, 3), 120, dtype=np.uint8)
        h = {"grabs": 0, "wheels": 0, "cursor": 0}

        def fake_grab(_rect):
            h["grabs"] += 1
            return Image.fromarray(frame)

        sb.grab_region = fake_grab
        sb.find_vertical_overlap = finder
        sb._send_mouse_wheel = lambda n: h.__setitem__("wheels", h["wheels"] + 1)
        sb.get_cursor_pos = lambda: (0, 0)
        sb.set_cursor_pos = lambda x, y: h.__setitem__("cursor", h["cursor"] + 1)
        img, stats = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 60, frame_h),
            settle_seconds=0, max_frames=max_frames,
            hide_overlays=False, bottom_guard=0,
        )
        return img, stats, h

    try:
        # S1 单帧低新增 → 重试确认，不会立刻 reached-bottom
        c1 = {"n": 0}

        def finder1(a, b, **kw):
            c1["n"] += 1
            return (a.shape[0] - (10 if c1["n"] == 1 else 100), 0.99)

        img1, st1, h1 = run(finder1, max_frames=5)
        ok_s1 = (st1["stop_reason"] != "reached-bottom" and st1["retries"] >= 1
                 and img1.height > 200 and st1["frames"] >= 4)
        record("S1 单帧几乎没动不会误判到底", ok_s1,
               f"reason={st1['stop_reason']} retries={st1['retries']} height={img1.height}")

        # S2 匹配失败先重试再继续
        c2 = {"n": 0}

        def finder2(a, b, **kw):
            c2["n"] += 1
            if c2["n"] <= 2:
                return (0, 0.1)
            return (a.shape[0] - 100, 0.99)

        img2, st2, h2 = run(finder2, max_frames=6)
        ok_s2 = (st2["retries"] == 2 and img2.height > 200
                 and st2["stop_reason"] not in ("match-failed", "no-overlap"))
        record("S2 匹配失败重试后继续拼接", ok_s2,
               f"reason={st2['stop_reason']} retries={st2['retries']} height={img2.height}")

        # S3 连续失败超过上限才结束
        img3, st3, h3 = run(lambda a, b, **kw: (0, 0.1), max_frames=8)
        ok_s3 = st3["stop_reason"] == "match-failed" and st3["retries"] == 2
        record("S3 连续失败超上限才结束", ok_s3,
               f"reason={st3['stop_reason']} retries={st3['retries']}")

        # S4 一次滚过头 → 自适应减小步长
        img4, st4, h4 = run(lambda a, b, **kw: (a.shape[0] - 150, 0.99),
                            frame_h=200, max_frames=4)
        ok_s4 = abs(st4["notches"]) < 3 and st4["stop_reason"] == "max-frames"
        record("S4 自适应减小滚轮步长", ok_s4,
               f"notches={st4['notches']} reason={st4['stop_reason']}")

        # S6 每帧滚轮前重新锁定光标
        ok_s6 = h4["cursor"] >= h4["wheels"] >= 1
        record("S6 每帧滚轮前重新锁定光标", ok_s6,
               f"cursor={h4['cursor']} wheels={h4['wheels']}")
    finally:
        for n, fn in orig.items():
            setattr(sb, n, fn)

    # S5 模板偏移：frame[20:60] 对应 acc[120:160]，应换算出 frame 第 0 行 = acc 第 100 行
    rng = np.random.default_rng(7)
    acc = rng.integers(0, 256, (300, 60, 3), dtype=np.uint8)
    # v20：重叠区（frame 前 200 行）必须与 canvas 尾部一致，真实拼接里
    # 这两段本来就是同一块页面内容；后半段才是本次滚动新进画面的内容。
    fr = np.vstack([acc[100:300], rng.integers(0, 256, (120, 60, 3), dtype=np.uint8)])
    top5, score5 = sb.find_vertical_overlap(
        acc, fr, search_rows=300, template_rows=40, template_offset=20
    )
    ok_s5 = abs(top5 - 100) <= 2 and score5 > 0.9
    record("S5 模板偏移换算回 frame 第 0 行", ok_s5,
           f"top={top5} score={score5:.3f}")

    # S7 控制条显示匹配分数
    bar_s = snapmod.BusyBar()
    bar_s.update_text(3, 2400, 0.93)
    ok_s7 = "0.93" in bar_s.detail.text() and "3" in bar_s.detail.text()
    record("S7 控制条显示最近匹配分数", ok_s7, bar_s.detail.text())
    bar_s.close()
    bar_s.deleteLater()

    # ---------------- S8~S11  透明色 / 填充透明度 ----------------
    def draw_rect(color: QColor) -> QColor:
        img = QImage(100, 60, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        s = Shape(kind="rect")
        s.rect, s.color, s.width = QRect(20, 10, 50, 30), color, 3
        draw_shape(p, s, img, 1.0)
        p.end()
        return img.pixelColor(20, 25)

    clear = draw_rect(QColor("#00000000"))
    red = draw_rect(QColor("#ff0000"))
    ok_s8 = (clear.red() == 255 and clear.green() == 255 and clear.blue() == 255
             and red.red() > 200 and red.green() < 80)
    record("S8 透明线条不产生边框像素", ok_s8,
           f"transparent=({clear.red()},{clear.green()},{clear.blue()}) "
           f"red=({red.red()},{red.green()},{red.blue()})")

    sp_s = StylePanel(show_pen_arrows=True)
    defaults_s = {
        "color": QColor("#ff0000"), "width": 3, "line_style": "solid",
        "font_size": 18, "bg_color": None,
        "pen_arrow_start": False, "pen_arrow_end": False,
    }
    sp_s.set_state(Shape(kind="text", text="x", pos=QPoint(0, 0)), defaults_s)
    hidden_text = sp_s._transparent_btn.isHidden()
    sp_s.set_state(Shape(kind="rect", rect=QRect(0, 0, 10, 10)), defaults_s)
    ok_s9 = hidden_text and not sp_s._transparent_btn.isHidden()
    record("S9 文字隐藏透明色块、封闭图形显示", ok_s9,
           f"text_hidden={hidden_text} rect_hidden={sp_s._transparent_btn.isHidden()}")

    got_s: list = []
    sp_s.style_changed.connect(lambda d: got_s.append(d))
    sp_s.set_state(Shape(kind="rect", rect=QRect(0, 0, 10, 10),
                         fill_color=QColor("#40ff0000")), defaults_s)
    back_alpha = sp_s._fill_alpha_slider.value()
    sp_s._fill_alpha_slider.setValue(80)
    emitted = got_s[-1] if got_s else {}
    ok_s10 = back_alpha == 25 and emitted.get("fill_color") == "#ccff0000"
    record("S10 填充透明度回填与修改", ok_s10,
           f"back={back_alpha} emitted={emitted}")
    sp_s.close()
    sp_s.deleteLater()

    ok_s11 = (_text_edit_color(QColor("#00000000")) == "#ffffff"
              and _text_edit_color(QColor("#ff0000")) == "#ff0000")
    record("S11 文字编辑框对透明色兜底", ok_s11,
           _text_edit_color(QColor("#00000000")))

    # ---------------- S12~S15  画布视图放缩 ----------------
    cv_s = Canvas(make_image(1600, 900), [], None)
    cv_s.resize(1000, 680)
    cv_s._fit()
    anchor = QPoint(300, 250)
    before = cv_s._to_image(anchor)
    cv_s._set_view_scale(cv_s.view_scale * 2, anchor)
    composed = cv_s.compose()
    ok_s12 = (cv_s._to_image(anchor) == before
              and composed.width() == 1600 and composed.height() == 900)
    record("S12 锚点放缩且导出保持全分辨率", ok_s12,
           f"anchor={before.x()},{before.y()} -> {cv_s._to_image(anchor).x()},"
           f"{cv_s._to_image(anchor).y()} export={composed.width()}x{composed.height()}")

    ed_s = EditorWindow(make_image(160, 90), [], None)
    acts = ed_s._menus["view"].actions()
    ok_menu = (len(acts) == 4 and all(a.text() for a in acts)
               and all(not a.shortcut().isEmpty() for a in acts))
    bad_lang_s = []
    for code in i18n.LANGS:
        i18n.LANG.set_preference(code, persist=False)
        app.processEvents()
        if not all(a.text() for a in acts):
            bad_lang_s.append(code)
    i18n.LANG.set_preference("zh_CN", persist=False)
    app.processEvents()
    ok_s13 = ok_menu and not bad_lang_s and "%" in ed_s.statusBar().currentMessage()
    record("S13 视图菜单 4 项 + 快捷键 + 8 语言 + 状态栏", ok_s13,
           f"menu={ok_menu} bad_lang={bad_lang_s} status={ed_s.statusBar().currentMessage()}")

    cv_e = ed_s.canvas
    s0 = cv_e.view_scale
    cv_e.zoom_in()
    s1 = cv_e.view_scale
    cv_e.zoom_out()
    s2 = cv_e.view_scale
    cv_e.zoom_actual()
    s3 = cv_e.view_scale
    cv_e.zoom_fit()
    s4 = cv_e.view_scale
    ok_s14 = (s1 > s0 and abs(s2 - s0) < 1e-6
              and abs(s3 - 1.0) < 1e-6 and abs(s4 - s0) < 1e-6)
    record("S14 放大/缩小/1:1/适应窗口倍率正确", ok_s14,
           f"{s0:.3f} -> {s1:.3f} -> {s2:.3f} -> {s3:.3f} -> {s4:.3f}")

    cv_e.zoom_in()
    cv_e.zoom_in()
    old_off = (cv_e.off_x, cv_e.off_y)
    p0 = QPoint(400, 300)
    cv_e.mousePressEvent(QMouseEvent(
        QEvent.MouseButtonPress, p0, p0, Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier))
    p1 = QPoint(460, 330)
    cv_e.mouseMoveEvent(QMouseEvent(
        QEvent.MouseMove, p1, p1, Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier))
    moved = (cv_e.off_x, cv_e.off_y) != old_off
    scale_kept = abs(cv_e.view_scale - s1 * 1.25) < 1e-6
    cv_e.mouseReleaseEvent(QMouseEvent(
        QEvent.MouseButtonRelease, p1, p1, Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier))
    ok_s15 = moved and scale_kept and cv_e._mode == "idle"
    record("S15 中键平移不改变显示比例", ok_s15,
           f"moved={moved} scale={cv_e.view_scale:.3f} mode={cv_e._mode}")

    for w in (cv_s, ed_s):
        w.close()
        w.deleteLater()
    app.processEvents()


def test_v20_long_capture_quality() -> None:
    """Stage T：长截图画质 —— 浮层清理 / 安全光标 / 抗干扰对齐。"""
    import numpy as np
    from PIL import Image

    import snapback as sb

    capture = sb.ScreenRect(100, 100, 1200, 800)

    # ---------------- T1~T2  浮层判定与非 Windows 降级 ----------------
    ime = sb.ScreenRect(1100, 700, 160, 40)
    main_win = sb.ScreenRect(100, 100, 1200, 800)
    away = sb.ScreenRect(3000, 3000, 120, 40)
    huge = sb.ScreenRect(100, 100, 1000, 700)
    core = "Windows.UI.Core.CoreWindow"
    ok_t1 = (
        sb._is_floating_overlay(capture, ime, core, "", "textinputhost.exe", 111, 999)
        and sb._is_floating_overlay(capture, ime, "tooltips_class32", "", "chrome.exe", 112, 999)
        and sb._is_floating_overlay(capture, ime, "X", "输入法候选", "sogouimebroker.exe", 113, 999)
        and sb._is_floating_overlay(capture, ime, "WeirdClass", "", "vendor.exe", 117, 999, sb.WS_EX_TOOLWINDOW)
        and not sb._is_floating_overlay(capture, ime, "OrdinaryWindow", "note", "app.exe", 118, 999, 0)
        and not sb._is_floating_overlay(capture, main_win, "Chrome_WidgetWin_1", "Bing", "chrome.exe", 114, 999)
        and not sb._is_floating_overlay(capture, away, core, "", "textinputhost.exe", 115, 999)
        and not sb._is_floating_overlay(capture, huge, core, "", "textinputhost.exe", 116, 999)
        and not sb._is_floating_overlay(capture, ime, core, "", "textinputhost.exe", 999, 999)
    )
    record("T1 只隐藏与选区相交的小浮层，主窗口/窗口外/本进程都排除", ok_t1,
           "ime/tooltip/toolwindow hit; main/away/huge/own excluded")

    orig_u32 = sb.user32
    try:
        sb.user32 = None
        no_win = sb.find_floating_overlays(capture) == []
        sb.hide_floating_overlays([1])
        sb.restore_floating_overlays([1])
    finally:
        sb.user32 = orig_u32
    record("T2 非 Windows 环境浮层处理静默降级", no_win, f"find={no_win}")

    # ---------------- T3~T4  隐藏/恢复、底部安全行、右侧光标 ----------------
    names = (
        "grab_region", "find_vertical_overlap", "_send_mouse_wheel",
        "get_cursor_pos", "set_cursor_pos", "find_floating_overlays",
        "hide_floating_overlays", "restore_floating_overlays",
    )
    orig = {n: getattr(sb, n) for n in names}
    seen: dict = {"hide": 0, "restore": 0, "rects": [], "cursor": []}
    blank = np.full((200, 60, 3), 120, dtype=np.uint8)

    try:
        sb.find_floating_overlays = lambda r: [101, 102]
        sb.hide_floating_overlays = lambda hs: seen.__setitem__("hide", seen["hide"] + 1)
        sb.restore_floating_overlays = lambda hs: seen.__setitem__(
            "restore", seen["restore"] + 1
        )
        sb.find_vertical_overlap = lambda a, b, **kw: (max(0, a.shape[0] - 60), 0.99)
        sb._send_mouse_wheel = lambda n: None
        sb.get_cursor_pos = lambda: (0, 0)
        sb.set_cursor_pos = lambda x, y: seen["cursor"].append((x, y))

        def fake_grab(r):
            seen["rects"].append(r)
            return Image.fromarray(blank)

        sb.grab_region = fake_grab
        img3, st3 = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 600, 240), settle_seconds=0, max_frames=2,
            hide_overlays=True, bottom_guard=24,
        )
        ok_t3 = (
            seen["hide"] >= 3 and seen["restore"] == 1
            and st3["overlays_hidden"] == 2
            and "align_diff" in st3 and "bottom_guard" in st3
        )
        record("T3 浮层每帧压住、结束恢复且统计字段齐全", ok_t3,
               f"hide={seen['hide']} restore={seen['restore']} stats={sorted(st3)}")

        # 抓帧抛异常时也必须恢复，否则输入法工具条会一直消失
        def boom(_r):
            raise RuntimeError("grab failed")

        sb.grab_region = boom
        try:
            sb.stitch_scroll(
                sb.ScreenRect(0, 0, 600, 240), settle_seconds=0, max_frames=1,
                hide_overlays=True, bottom_guard=0,
            )
        except RuntimeError:
            pass
        ok_t4 = seen["restore"] == 2
        record("T4 抓帧异常时浮层仍被恢复", ok_t4,
               f"restore={seen['restore']}")

        sb.grab_region = fake_grab
        seen["rects"].clear()
        seen["cursor"].clear()
        img5, st5 = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 600, 240), settle_seconds=0, max_frames=2,
            hide_overlays=False, bottom_guard=24,
        )
        guarded = [r for r in seen["rects"] if r.h == 216]
        # 最后一次 set_cursor_pos 是把光标还给用户（saved_cursor=(0,0)）
        active = seen["cursor"][:-1]
        right_side = [p for p in active if p[0] >= 600 - 12]
        ok_t5 = (
            len(guarded) == len(seen["rects"]) >= 1
            and st5["bottom_guard"] == 24
            and len(right_side) == len(active) >= 1
            and seen["cursor"][-1] == (0, 0)
        )
        record("T5 捕获区底部预留安全行、光标停在右侧滚动条而非画面中心",
               ok_t5, f"rects={[r.h for r in seen['rects']]} "
                      f"cursor_x={[p[0] for p in seen['cursor']]}")

        # T11 到底补尾：正常帧都用缩短的捕获区，最后一帧用完整 rect
        sb.find_vertical_overlap = lambda a, b, **kw: (max(0, a.shape[0] - 10), 0.99)
        seen["rects"].clear()
        img11, st11 = sb.stitch_scroll(
            sb.ScreenRect(0, 0, 600, 240), settle_seconds=0, max_frames=6,
            hide_overlays=False, bottom_guard=24,
        )
        ok_t11 = (
            st11["stop_reason"] == "reached-bottom"
            and seen["rects"][-1].h == 240
            and any(r.h == 216 for r in seen["rects"][:-1])
        )
        record("T11 滚到底后补抓完整画面，长图不缺尾", ok_t11,
               f"reason={st11['stop_reason']} rects={[r.h for r in seen['rects']]}")
    finally:
        for n, fn in orig.items():
            setattr(sb, n, fn)

    # ---------------- T6~T9  抗浮层对齐 ----------------
    rng = np.random.default_rng(3)
    page = rng.integers(0, 256, (500, 80, 3), dtype=np.uint8)

    def make_case(with_fake_peak: bool):
        acc = page[:300].copy()
        fr = np.vstack([
            page[200:300], rng.integers(0, 256, (100, 80, 3), dtype=np.uint8)
        ])
        if with_fake_peak:
            acc[60:100] = fr[30:70].copy()   # 相关系数更高但整体错位
        # 每帧固定在屏幕右下 / 左下的浮层（输入法工具条 / URL 提示条）
        white = np.full((18, 26, 3), 255, dtype=np.uint8)
        blue = np.full((14, 50, 3), 200, dtype=np.uint8)
        fr[-18:, -26:] = white
        fr[-14:, 0:50] = blue
        acc[-18:, -26:] = white
        acc[-14:, 0:50] = blue
        return acc, fr

    acc6, fr6 = make_case(False)
    top6, score6 = sb.find_vertical_overlap(
        acc6, fr6, search_rows=300, template_rows=40, template_offset=30
    )
    record("T6 带固定浮层仍能精确对齐（top≈200）",
           abs(top6 - 200) <= 2 and score6 > 0.9,
           f"top={top6} score={score6:.3f}")

    acc7, fr7 = make_case(True)
    top7, score7 = sb.find_vertical_overlap(
        acc7, fr7, search_rows=300, template_rows=40, template_offset=30
    )
    record("T7 假相关峰值被重叠区一致性验证纠正",
           abs(top7 - 200) <= 2 and score7 > 0.9,
           f"top={top7} score={score7:.3f}")

    d_ok = sb.overlap_row_diff(acc7, fr7, 200)
    d_bad = sb.overlap_row_diff(acc7, fr7, 197)
    record("T8 重叠区行差能分辨正确对齐与 3px 错位",
           d_ok < 5 and d_bad > d_ok + 5,
           f"correct={d_ok:.1f} shifted={d_bad:.1f}")

    same = np.zeros((100, 20, 3), dtype=np.uint8)
    record("T9 到底时重叠不足 8 行不误伤匹配分数",
           sb.overlap_row_diff(same, same, 95) == 0.0,
           f"diff={sb.overlap_row_diff(same, same, 95)}")

    # ---------------- T10  版本记录 ----------------
    from pathlib import Path
    readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
    record("T10 README 已记录 v20 画质修复", "v20" in readme and "输入法" in readme,
           f"v20={'v20' in readme} ime={'输入法' in readme}")


def test_v21_shape_corner_resize() -> None:
    """Stage U：矩形 / 椭圆四角拖柄（Overlay + 窗口编辑器 + 放缩）。"""
    from pathlib import Path

    from PySide6.QtGui import QPixmap

    from i18n_docs import help_html
    from snapui import HELP_HTML
    from snapeditor import (
        SHAPE_MIN_SIZE,
        shape_corner_cursor,
        shape_corner_points,
        shape_hit_corner,
        shape_resize_rect,
    )

    P, M, R = (
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseMove,
        QEvent.Type.MouseButtonRelease,
    )

    def overlay_event(typ, p: QPoint) -> QMouseEvent:
        return QMouseEvent(typ, QPoint(p), QPoint(p), Qt.LeftButton,
                           Qt.LeftButton, Qt.NoModifier)

    r = QRect(10, 20, 100, 60)
    pts = dict(shape_corner_points(r))

    # ---------------- U1~U5  纯几何函数 ----------------
    ok_u1 = (
        pts["nw"] == QPoint(10, 20) and pts["ne"] == QPoint(109, 20)
        and pts["se"] == QPoint(109, 79) and pts["sw"] == QPoint(10, 79)
        and len(shape_corner_points(r)) == 4
    )
    record("U1 四角点坐标与顺序正确（nw/ne/se/sw）", ok_u1,
           f"pts={[(k, v.x(), v.y()) for k, v in pts.items()]}")

    ok_u2 = (
        all(shape_hit_corner(r, p) == k for k, p in pts.items())
        and shape_hit_corner(r, QPoint(60, 50)) == ""
        and shape_hit_corner(r, QPoint(109 + 20, 79)) == ""
        and shape_hit_corner(QRect(), QPoint(10, 20)) == ""
    )
    record("U2 四角命中、中心与半径外不命中、空矩形不命中", ok_u2)

    a = shape_resize_rect(r, "se", QPoint(200, 150))
    b = shape_resize_rect(r, "nw", QPoint(0, 0))
    c = shape_resize_rect(r, "ne", QPoint(200, 0))
    d = shape_resize_rect(r, "sw", QPoint(0, 150))
    ok_u3 = (
        (a.left(), a.top(), a.right(), a.bottom()) == (10, 20, 200, 150)
        and (b.left(), b.top(), b.right(), b.bottom()) == (0, 0, 109, 79)
        and (c.left(), c.top(), c.right(), c.bottom()) == (10, 0, 200, 79)
        and (d.left(), d.top(), d.right(), d.bottom()) == (0, 20, 109, 150)
    )
    record("U3 拖任一角时对角精确固定，翻转不偏移 1px", ok_u3,
           f"se={a} nw={b} ne={c} sw={d}")

    tiny = shape_resize_rect(r, "se", QPoint(11, 21))
    flip = shape_resize_rect(r, "se", QPoint(0, 0))
    ok_u4 = (
        tiny.width() >= SHAPE_MIN_SIZE and tiny.height() >= SHAPE_MIN_SIZE
        and flip.left() == 0 and flip.top() == 0
        and flip.right() == 10 and flip.bottom() == 20   # se 的固定对角是 nw
        and shape_resize_rect(r, "xx", QPoint(500, 500)) == r
    )
    record("U4 最小尺寸 / 拖过对角翻转 / 非法角原样返回", ok_u4,
           f"tiny={tiny} flip={flip}")

    ok_u5 = (
        shape_corner_cursor("nw") == Qt.SizeFDiagCursor
        and shape_corner_cursor("se") == Qt.SizeFDiagCursor
        and shape_corner_cursor("ne") == Qt.SizeBDiagCursor
        and shape_corner_cursor("sw") == Qt.SizeBDiagCursor
        and shape_corner_cursor("") is None
    )
    record("U5 四角斜向缩放光标映射正确", ok_u5)

    # ---------------- U6~U11  窗口编辑器 Canvas ----------------
    cv = Canvas(make_image(1600, 900), [], None)
    cv.resize(1000, 680)
    cv._fit()

    def draw(kind: str, p1: QPoint, p2: QPoint):
        cv._set_tool(kind)
        cv.toolbar._on_tool(kind)
        cv.mousePressEvent(mouse_event(P, cv, p1))
        cv.mouseMoveEvent(mouse_event(M, cv, p2))
        cv.mouseReleaseEvent(mouse_event(R, cv, p2))
        return cv.shapes[-1]

    rect_s = draw("rect", QPoint(200, 150), QPoint(400, 300))
    r0 = QRect(rect_s.rect)
    rp = dict(shape_corner_points(rect_s.rect.normalized()))
    ok_u6 = (
        cv._selected is rect_s
        and len(cv._shape_corner_points()) == 4
        and cv._hit_shape_corner(rp["se"]) == "se"
        and cv._hit_shape_corner(rp["nw"]) == "nw"
    )
    record("U6 画完矩形自动选中并显示 4 个可命中的角柄", ok_u6,
           f"rect={rect_s.rect} handles={len(cv._shape_corner_points())}")

    cv.mousePressEvent(mouse_event(P, cv, rp["se"]))
    mode_press = cv._mode
    cv.mouseMoveEvent(mouse_event(M, cv, QPoint(520, 380)))
    cv.mouseReleaseEvent(mouse_event(R, cv, QPoint(520, 380)))
    rr = rect_s.rect.normalized()
    ok_u7 = (
        mode_press == "resizing_shape" and cv._mode == "idle"
        and cv._selected is rect_s
        and abs(rr.left() - r0.left()) <= 2 and abs(rr.top() - r0.top()) <= 2
        and abs(rr.right() - 520) <= 3 and abs(rr.bottom() - 380) <= 3
        and cv.compose().width() == 1600 and cv.compose().height() == 900
    )
    record("U7 拖 se 角放大矩形：左上固定、状态复位、导出仍全分辨率", ok_u7,
           f"mode={mode_press}->{cv._mode} rect={rr}")

    ell = draw("ellipse", QPoint(600, 200), QPoint(760, 320))
    e0 = QRect(ell.rect)
    ep = dict(shape_corner_points(ell.rect.normalized()))
    cv.mousePressEvent(mouse_event(P, cv, ep["nw"]))
    cv.mouseMoveEvent(mouse_event(M, cv, QPoint(560, 160)))
    cv.mouseReleaseEvent(mouse_event(R, cv, QPoint(560, 160)))
    er = ell.rect.normalized()
    ok_u8 = (
        cv._selected is ell
        and abs(er.right() - e0.right()) <= 2
        and abs(er.bottom() - e0.bottom()) <= 2
        and abs(er.left() - 560) <= 3 and abs(er.top() - 160) <= 3
    )
    record("U8 椭圆拖 nw 角同样可缩放，对角固定", ok_u8, f"ellipse={er}")

    ep2 = dict(shape_corner_points(ell.rect.normalized()))
    before_flip = QRect(ell.rect)
    cv.mousePressEvent(mouse_event(P, cv, ep2["se"]))
    cv.mouseMoveEvent(mouse_event(M, cv, QPoint(400, 100)))
    cv.mouseReleaseEvent(mouse_event(R, cv, QPoint(400, 100)))
    fr = ell.rect.normalized()
    ok_u9 = (
        abs(fr.left() - 400) <= 3 and abs(fr.top() - 100) <= 3
        and abs(fr.right() - before_flip.left()) <= 2
        and abs(fr.bottom() - before_flip.top()) <= 2
        and fr.width() >= SHAPE_MIN_SIZE and fr.height() >= SHAPE_MIN_SIZE
    )
    record("U9 拖过对角翻转后仍保持可编辑的最小形状", ok_u9, f"flipped={fr}")

    cv._set_view_scale(cv.view_scale * 2.0, QPoint(cv.width() // 2, cv.height() // 2))
    zc = dict(shape_corner_points(ell.rect.normalized()))["nw"]
    cv.mousePressEvent(mouse_event(P, cv, zc))
    ok_u10 = cv._mode == "resizing_shape" and len(cv._shape_corner_points()) == 4
    cv.mouseReleaseEvent(mouse_event(R, cv, zc))
    record("U10 画布放大 2 倍后四角命中范围仍准确", ok_u10,
           f"scale={cv.view_scale:.3f} mode={cv._mode}")

    mos = Shape(kind="mosaic")
    mos.rect = QRect(100, 100, 80, 60)
    cv.shapes.append(mos)
    cv._selected = mos
    no_handles = (
        cv._shape_corner_points() == []
        and cv._hit_shape_corner(dict(shape_corner_points(mos.rect))["se"]) == ""
    )
    arr = Shape(kind="arrow")
    arr.start, arr.end = QPoint(10, 10), QPoint(90, 90)
    arrow_hit = None
    cv._selected = arr
    no_handles_arrow = cv._shape_corner_points() == []
    arrow_hit = cv._hit_arrow_endpoint(QPoint(90, 90), selected_only=True)
    ok_u11 = (
        no_handles and no_handles_arrow
        and arrow_hit is not None and arrow_hit[0] is arr
    )
    record("U11 马赛克/箭头不出现四角柄，箭头端点拉伸未回归", ok_u11)

    # ---------------- U12~U14  截图遮罩 Overlay ----------------
    ov = Overlay(make_image(400, 200), dpr=1.0)
    ov.resize(400, 200)
    ov.sel = QRect(10, 10, 360, 170)
    sel0 = QRect(ov.sel)
    ov._mode = "editing"
    sh = Shape(kind="ellipse")
    sh.rect = QRect(50, 50, 100, 60)
    sh.color = QColor(255, 0, 0)
    ov.shapes = [sh]
    ov._selected = sh
    op = dict(shape_corner_points(sh.rect.normalized()))
    hit_ok = ov._hit_shape_corner(op["se"]) == "se" and len(ov._shape_corner_points()) == 4
    ov.mousePressEvent(overlay_event(P, op["se"]))
    ov_mode = ov._mode
    ov.mouseMoveEvent(overlay_event(M, QPoint(220, 150)))
    ov.mouseReleaseEvent(overlay_event(R, QPoint(220, 150)))
    nr = sh.rect.normalized()
    ok_u12 = (
        hit_ok and ov_mode == "resizing_shape" and ov._mode == "editing"
        and ov.sel == sel0
        and (nr.left(), nr.top()) == (50, 50)
        and (nr.right(), nr.bottom()) == (220, 150)
    )
    record("U12 Overlay 拖角只改图形，不改选区、不误触选区八点", ok_u12,
           f"shape={nr} sel={ov.sel} mode={ov_mode}->{ov._mode}")

    op2 = dict(shape_corner_points(sh.rect.normalized()))
    ov.mousePressEvent(overlay_event(P, op2["se"]))
    ov.mouseMoveEvent(overlay_event(M, QPoint(390, 195)))
    ov.mouseReleaseEvent(overlay_event(R, QPoint(390, 195)))
    nr2 = sh.rect.normalized()
    mos2 = Shape(kind="mosaic")
    mos2.rect = QRect(60, 60, 80, 50)
    ov._selected = mos2
    ok_u13 = (
        (nr2.right(), nr2.bottom()) == (368, 178)
        and ov.sel == sel0
        and ov._shape_corner_points() == []
        and ov._hit_shape_corner(QPoint(139, 109)) == ""
    )
    record("U13 角点被限制在选区内；Overlay 马赛克无四角柄", ok_u13,
           f"clamped=({nr2.right()},{nr2.bottom()}) sel_bound=(368,178)")

    ov._selected = sh
    cv._selected = rect_s
    render_ok, err = True, ""
    try:
        pm = QPixmap(cv.size())
        cv.render(pm)
        pm2 = QPixmap(ov.size())
        ov.render(pm2)
    except Exception as exc:  # noqa: BLE001
        render_ok, err = False, str(exc)
    record("U14 两个编辑器绘制四角控制柄不抛异常", render_ok, err)

    # ---------------- U15  文档与 8 语言帮助 ----------------
    readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
    markers = {
        "en": "corner handles",
        "ja": "四隅のハンドル",
        "ko": "모서리 핸들",
        "fr": "poignées d'angle",
        "de": "Eckgriffe",
        "es": "tiradores de esquina",
        "zh_TW": "四角控制點",
    }
    missing = [code for code, mark in markers.items() if mark not in help_html(code)]
    ok_u15 = (
        "v21" in readme and "四角" in readme
        and "四角" in HELP_HTML and not missing
    )
    record("U15 README / 中文帮助 / 7 语言帮助已同步四角缩放说明", ok_u15,
           f"missing={missing}")

    cv.close()
    ov.close()
    cv.deleteLater()
    ov.deleteLater()


def test_v22_shape_rotation() -> None:
    """Stage V：矩形 / 椭圆 / 文字旋转 + 整图旋转时文字联动。"""
    from pathlib import Path

    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPixmap

    from i18n_docs import help_html
    from snapui import HELP_HTML
    from snapeditor import (
        ROTATABLE_KINDS,
        Overlay,
        Shape,
        draw_shape,
        normalize_angle,
        paint_shape_rotate_handle,
        rotate_angle_from_drag,
        rotate_point_about,
        shape_angle,
        shape_hit_rotate_handle,
        shape_hit_rotated_corner,
        shape_rotate_center,
        shape_rotate_handle_point,
        shape_rotate_point,
        shape_rotate_rect,
        shape_rotated_bbox,
        shape_rotated_corners,
        shape_text_box,
        shape_unrotate_point,
        shape_corner_points,
        shape_resize_rect,
        unrotate_point_about,
    )
    from snap_editor import Canvas

    P, M, R = (
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseMove,
        QEvent.Type.MouseButtonRelease,
    )

    def ov_ev(typ, p: QPoint) -> QMouseEvent:
        return QMouseEvent(typ, QPoint(p), QPoint(p), Qt.LeftButton,
                           Qt.LeftButton, Qt.NoModifier)

    # ---------------- V1 角度归一化 / 变换往返 ----------------
    vals = [normalize_angle(x) for x in (0, 90, 180, 270, -190, 370)]
    sh = Shape(kind="rect")
    sh.rect = QRect(10, 20, 100, 60)
    sh.angle = 30.0
    back = shape_unrotate_point(sh, shape_rotate_point(sh, QPoint(10, 20)))
    ok_v1 = (
        vals == [0.0, 90.0, 180.0, -90.0, 170.0, 10.0]
        and abs(back.x() - 10) < 0.5 and abs(back.y() - 20) < 0.5
        and shape_angle(Shape(kind="mosaic")) == 0.0
    )
    record("V1 角度归一化与旋转变换往返", ok_v1, f"vals={vals} back={back}")

    # ---------------- V2 文字包围盒 / 外接框 / 中心 ----------------
    tx = Shape(kind="text", text="Hello", pos=QPoint(30, 80))
    tb = shape_text_box(tx)
    ok_v2 = (
        tb.width() >= 40 and tb.height() > 10
        and shape_rotate_rect(tx) == tb
        and abs(QRectF(tb).center().x() - shape_rotate_center(tx).x()) < 0.01
        and shape_rotate_rect(Shape(kind="pen")).isNull()
    )
    record("V2 文字包围盒 / 旋转外接框 / 旋转中心", ok_v2,
           f"textbox={tb} center={shape_rotate_center(tx)}")

    # ---------------- V3 旋转后四角 ----------------
    sh.angle = 90.0
    pts = shape_rotated_corners(sh)
    ok_v3 = (
        len(pts) == 4
        and pts[0] != dict(shape_corner_points(sh.rect))["nw"]
        and shape_hit_rotated_corner(sh, pts[2]) == "se"
        and shape_hit_rotated_corner(sh, QPoint(900, 900)) == ""
        and shape_rotated_bbox(sh).isValid()
        and shape_hit_rotated_corner(Shape(kind="text"), pts[0]) == ""
    )
    record("V3 旋转后四角点、命中与外接框", ok_v3,
           f"pts={[(p.x(), p.y()) for p in pts]}")

    # ---------------- V4 旋转柄 ----------------
    sh.angle = 30.0
    h = shape_rotate_handle_point(sh)
    ok_v4 = (
        shape_hit_rotate_handle(sh, h)
        and not shape_hit_rotate_handle(sh, h + QPoint(40, 40))
        and not shape_hit_rotate_handle(Shape(kind="mosaic"), h)
        and shape_hit_rotate_handle(tx, shape_rotate_handle_point(tx))
    )
    record("V4 旋转柄位置与命中，马赛克排除", ok_v4, f"handle={h}")

    # ---------------- V5 拖动转角 / 跨 ±180 / 吸附 ----------------
    c = QRect(10, 20, 100, 60).center()
    cf = QPointF(c)
    a90 = rotate_angle_from_drag(0, cf, QPoint(c.x(), c.y() - 50),
                                 QPoint(c.x() + 50, c.y()))
    across = rotate_angle_from_drag(170, cf, QPoint(c.x() - 50, c.y()),
                                    QPoint(c.x() + 50, c.y()))
    snap = rotate_angle_from_drag(0, cf, QPoint(c.x(), c.y() - 50),
                                  QPoint(c.x() + 36, c.y() - 35), True)
    ok_v5 = (
        abs(a90 - 90.0) < 0.01 and abs(across + 10.0) < 0.01
        and abs(snap - 45.0) < 0.01
        and abs(snap / 15 - round(snap / 15)) < 0.01
    )
    record("V5 拖动转角、跨 ±180 不跳变、Shift 吸附 15°", ok_v5,
           f"a90={a90} across={across} snap={snap}")

    # ---------------- V6 draw_shape 真的按角度绘制 ----------------
    base = make_image(300, 200, (255, 255, 255))

    def render_one(angle: float) -> QImage:
        im = QImage(300, 200, QImage.Format_ARGB32_Premultiplied)
        im.fill(QColor(255, 255, 255))
        p = QPainter(im)
        p.setRenderHint(QPainter.Antialiasing, True)
        s = Shape(kind="rect", color=QColor(255, 0, 0))
        s.rect = QRect(40, 40, 160, 60)
        s.width = 4
        s.angle = angle
        draw_shape(p, s, base, 1.0)
        p.end()
        return im

    a0, a90img = render_one(0.0), render_one(90.0)
    diff = sum(
        1 for y in range(0, 200, 2) for x in range(0, 300, 2)
        if a0.pixelColor(x, y).rgb() != a90img.pixelColor(x, y).rgb()
    )
    ok_v6 = diff > 200
    record("V6 draw_shape 按角度绘制不同像素", ok_v6, f"diff_pixels={diff}")

    # ---------------- V6b 旋转文字像素中心不偏移 ----------------
    # Qt6 的 drawText(QPoint, str) 在旋转 world transform 下会把文字基线
    # 额外平移（实测约 2×ascent ≈ 63px），导致旋转文字整体错位；v22 改用
    # QPainterPath 字形路径绘制，像素中心必须贴合 shape_text_box() 中心。
    from PySide6.QtCore import QRectF
    from snapeditor import shape_text_box

    def text_pixel_center(angle: float):
        im = QImage(400, 400, QImage.Format_ARGB32_Premultiplied)
        im.fill(QColor(255, 255, 255))
        pp = QPainter(im)
        pp.setRenderHint(QPainter.Antialiasing, True)
        ts = Shape(kind="text", text="ROTATE", pos=QPoint(100, 200),
                   color=QColor(220, 0, 0))
        ts.font_size = 34
        ts.angle = angle
        draw_shape(pp, ts, im, 1.0)
        pp.end()
        xs: list[int] = []
        ys: list[int] = []
        for yy in range(400):
            for xx in range(400):
                c = im.pixelColor(xx, yy)
                if c.red() > 150 and c.green() < 90 and c.blue() < 90:
                    xs.append(xx)
                    ys.append(yy)
        if not xs:
            return None
        return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)

    tbox = Shape(kind="text", text="ROTATE", pos=QPoint(100, 200))
    tbox.font_size = 34
    want = QRectF(shape_text_box(tbox)).center()
    centers = {a: text_pixel_center(a) for a in (0.0, 90.0, -90.0, 45.0)}
    ok_v6b = all(
        c is not None
        and abs(c[0] - want.x()) <= 6
        and abs(c[1] - want.y()) <= 6
        for c in centers.values()
    )
    record("V6b 旋转文字像素中心贴合包围盒中心（字形路径绘制）", ok_v6b,
           f"want=({want.x():.1f},{want.y():.1f}) " +
           " ".join(f"{a}°={c}" for a, c in centers.items()))

    # ---------------- V7~V10 Canvas 交互 ----------------
    cv = Canvas(make_image(1200, 800), [], None)
    cv.resize(1000, 680)
    cv._fit()
    cv._set_tool("rect")
    cv.mousePressEvent(mouse_event(P, cv, QPoint(200, 150)))
    cv.mouseMoveEvent(mouse_event(M, cv, QPoint(400, 300)))
    cv.mouseReleaseEvent(mouse_event(R, cv, QPoint(400, 300)))
    sh2 = cv.shapes[0]
    hp = cv._rotate_handle_pos()
    cv.mousePressEvent(mouse_event(P, cv, hp))
    mode_start = cv._mode
    cc = sh2.rect.center()
    cv.mouseMoveEvent(mouse_event(M, cv, QPoint(cc.x() + 70, cc.y() - 30)))
    cv.mouseReleaseEvent(mouse_event(R, cv, QPoint(cc.x() + 70, cc.y() - 30)))
    ok_v7 = (
        cv._hit_rotate_handle(cv._rotate_handle_pos())
        and mode_start == "rotating_shape"
        and abs(sh2.angle) > 5
        and cv._mode == "idle"
        and cv.compose().size() == cv.base.size()
    )
    record("V7 Canvas 拖旋转柄改角度、状态复位、导出全分辨率", ok_v7,
           f"mode={mode_start}->{cv._mode} angle={sh2.angle}")

    cv._begin_shape_rotate(cv._rotate_handle_pos())
    cv._apply_shape_rotate(QPoint(cc.x() + 40, cc.y() - 40), snap=True)
    ok_v8 = abs(sh2.angle / 15 - round(sh2.angle / 15)) < 0.01
    record("V8 Canvas Shift 吸附到 15° 整数倍", ok_v8, f"angle={sh2.angle}")
    cv._mode, cv._rotating_shape = "idle", None

    sh2.angle = 0.0
    step_ok = cv.rotate_selected(90)
    cv._refresh_style_panel()
    ok_v9 = (
        step_ok and abs(sh2.angle - 90.0) < 0.01
        and cv.style_panel._angle_slider.value() == 90
        and not cv.style_panel._angle_box.isHidden()
    )
    record("V9 菜单 90° 步进 + 样式面板角度回填", ok_v9,
           f"angle={sh2.angle} slider={cv.style_panel._angle_slider.value()}")

    tx2 = Shape(kind="text", text="ABC", pos=QPoint(500, 400))
    cv.shapes.append(tx2)
    cv._selected = tx2
    cv._on_select_changed()
    ok_v10 = (
        cv._hit_rotate_handle(cv._rotate_handle_pos())
        and cv.rotate_selected(90) and abs(tx2.angle - 90.0) < 0.01
        and not cv.style_panel._angle_box.isHidden()
        and tx2.kind in ROTATABLE_KINDS
    )
    record("V10 Canvas 文字可旋转、角度控件可见", ok_v10,
           f"angle={tx2.angle}")

    # ---------------- V11 Overlay ----------------
    ov = Overlay(make_image(500, 400), dpr=1.0)
    ov.resize(500, 400)
    ov.sel = QRect(10, 10, 470, 370)
    ov._mode = "editing"
    osh = Shape(kind="ellipse")
    osh.rect = QRect(100, 100, 160, 90)
    ov.shapes = [osh]
    ov._selected = osh
    oh = ov._rotate_handle_pos()
    ov.mousePressEvent(ov_ev(P, oh))
    ov.mouseMoveEvent(ov_ev(M, oh + QPoint(0, 80)))
    ov.mouseReleaseEvent(ov_ev(R, oh + QPoint(0, 80)))
    ok_v11 = (
        abs(osh.angle) > 5
        and ov.sel == QRect(10, 10, 470, 370)
        and ov._mode == "editing"
        and ov._hit_rotate_handle(ov._rotate_handle_pos())
    )
    record("V11 Overlay 拖旋转柄改角度，选区与状态不变", ok_v11,
           f"angle={osh.angle} sel={ov.sel}")

    # ---------------- V12 旋转后四角缩放用局部坐标 ----------------
    sh3 = Shape(kind="rect")
    sh3.rect = QRect(10, 20, 100, 60)
    sh3.angle = 45.0
    c3 = shape_rotate_center(sh3)
    p0 = QPointF(77, 33)
    p2 = unrotate_point_about(rotate_point_about(p0, c3, 45), c3, 45)
    local = shape_unrotate_point(sh3, QPoint(200, 150)).toPoint()
    nr = shape_resize_rect(sh3.rect, "se", local)
    ok_v12 = (
        abs(p2.x() - p0.x()) < 0.01 and abs(p2.y() - p0.y()) < 0.01
        and nr.isValid() and nr.width() >= 8 and nr.height() >= 8
        and local != QPoint(200, 150)
    )
    record("V12 旋转后四角缩放用局部坐标、逆变换不漂移", ok_v12,
           f"local={local} resized={nr}")

    # ---------------- V13 整图旋转联动 ----------------
    c4 = Canvas(make_image(300, 200), [], None)
    c4.resize(1000, 680)
    c4._fit()
    rr = Shape(kind="rect", rect=QRect(20, 30, 80, 40))
    rr.angle = 30.0
    tt = Shape(kind="text", text="Hi", pos=QPoint(60, 90))
    mm = Shape(kind="mosaic", rect=QRect(100, 50, 30, 30))
    c4.shapes = [rr, tt, mm]
    c4.transform_image("cw")
    ok_v13 = (
        abs(c4.shapes[1].angle - 90.0) < 0.01
        and abs(c4.shapes[0].angle - 30.0) < 0.01
        and abs(c4.shapes[2].angle) < 0.01
    )
    c4.transform_image("ccw")
    ok_v13 = (
        ok_v13 and abs(c4.shapes[1].angle) < 0.01
        and abs(c4.shapes[0].angle - 30.0) < 0.01
    )
    c4.shapes[1].angle = 45.0
    c4.transform_image("flip_h")
    ok_v13 = ok_v13 and abs(c4.shapes[1].angle + 45.0) < 0.01
    c4.undo()
    # 撤销会换成快照里的克隆对象，必须读 c4.shapes 而不是旧引用
    ok_v13 = ok_v13 and abs(c4.shapes[1].angle - 45.0) < 0.01
    record("V13 整图旋转文字 ±90°、矩形角度不变、镜像取负、撤销恢复", ok_v13,
           f"text={c4.shapes[1].angle} rect={c4.shapes[0].angle}")

    # ---------------- V14 放缩后命中 ----------------
    cv._selected = sh2
    cv._set_view_scale(2.0)
    hp2 = cv._rotate_handle_pos()
    ok_v14 = (
        cv._hit_rotate_handle(hp2)
        and not cv._hit_rotate_handle(hp2 + QPoint(40, 40))
        and cv._rotate_handle_dist() >= 18
    )
    record("V14 画布放缩后旋转柄命中按显示比例反算", ok_v14,
           f"scale={cv.view_scale} dist={cv._rotate_handle_dist()}")

    # ---------------- V15 不可旋转标注 ----------------
    mo = Shape(kind="mosaic", rect=QRect(10, 10, 30, 30))
    cv._selected = mo
    ok_v15 = (
        cv._rotate_handle_pos() == QPoint()
        and not cv._hit_rotate_handle(cv._rotate_handle_pos())
        and cv._shape_corner_points() == []
        and not cv.rotate_selected(90)
        and abs(mo.angle) < 0.01
    )
    pm = QPixmap(cv.size())
    try:
        pmp = QPainter(pm)
        paint_shape_rotate_handle(pmp, mo)
        pmp.end()
        ov._selected = osh
        pm2 = QPixmap(ov.size())
        ov.render(pm2)
    except Exception as exc:  # noqa: BLE001
        ok_v15 = False
        print("    绘制异常：", exc)
    record("V15 马赛克无旋转柄、不受角度影响、绘制不抛错", ok_v15)

    # ---------------- V16 文档与 i18n ----------------
    from i18n_data import _ROWS as ROWS

    keys = ("旋转角度", "旋转选中形状",
            "顺时针旋转选中 90°", "逆时针旋转选中 90°")
    ok_keys = all(k in ROWS and len(ROWS[k]) == 8 and all(ROWS[k]) for k in keys)
    readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
    markers = {
        "en": "rotation handle",
        "ja": "回転ハンドル",
        "ko": "회전 핸들",
        "fr": "poignée de rotation",
        "de": "Drehgriff",
        "es": "tirador de rotación",
        "zh_TW": "旋轉控制柄",
    }
    missing = [code for code, mark in markers.items() if mark not in help_html(code)]
    ok_v16 = (
        "v22" in readme and "旋转柄" in readme
        and "形状旋转" in HELP_HTML and "字形与底图一起旋转" in HELP_HTML
        and ok_keys and not missing
    )
    record("V16 README / 中文帮助 / 7 语言帮助 / 8 语言词条同步", ok_v16,
           f"keys={ok_keys} missing={missing}")

    for w in (cv, ov, c4):
        w.close()
        w.deleteLater()


def test_v23_text_background() -> None:
    """Stage W：文字背景透明度 + 文字背景边框（颜色可透明 / 线宽 / 线型）。"""
    from pathlib import Path

    from PySide6.QtCore import QPoint, QRectF
    from PySide6.QtGui import QPainter

    from i18n_data import _ROWS as ROWS
    from i18n_docs import help_html
    from snapui import HELP_HTML
    from snapeditor import Overlay, StylePanel, Shape, draw_shape, shape_text_box

    def make_text() -> Shape:
        s = Shape(kind="text", text="HELLO", pos=QPoint(40, 100))
        s.font_size = 28
        s.color = QColor(0, 0, 0)
        return s

    def render(s: Shape) -> QImage:
        im = QImage(320, 200, QImage.Format_ARGB32_Premultiplied)
        im.fill(QColor(255, 255, 255))
        p = QPainter(im)
        p.setRenderHint(QPainter.Antialiasing, True)
        draw_shape(p, s, im, 1.0)
        p.end()
        return im

    def red_stats(im: QImage):
        xs, ys = [], []
        for y in range(im.height()):
            for x in range(im.width()):
                c = im.pixelColor(x, y)
                if c.red() > 150 and c.green() < 90 and c.blue() < 90:
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return 0, None
        return len(xs), ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)

    # ---------------- W1 默认字段 ----------------
    d = Shape(kind="text")
    ok_w1 = (
        d.bg_border is False
        and isinstance(d.bg_border_color, QColor)
        and d.bg_border_color.alpha() == 255
        and d.bg_border_width == 2
        and d.bg_border_style == "solid"
    )
    record("W1 文字背景边框默认值齐全", ok_w1,
           f"border={d.bg_border} width={d.bg_border_width} style={d.bg_border_style}")

    # ---------------- W2 背景透明度可调 ----------------
    s = make_text()
    s.bg_color = QColor(0, 0, 255, 64)
    box = shape_text_box(s)
    probe = (box.x() + 2, box.y() + box.height() // 2)
    im25 = render(s)
    c25 = im25.pixelColor(*probe)
    s.bg_color = QColor(0, 0, 255, 255)
    im100 = render(s)
    c100 = im100.pixelColor(*probe)
    ok_w2 = (c25.blue() - c25.red()) < (c100.blue() - c100.red()) - 80
    record("W2 文字背景透明度 25% 与 100% 渲染不同", ok_w2,
           f"diff25={c25.blue()-c25.red()} diff100={c100.blue()-c100.red()}")

    # ---------------- W3 填充与背景透明度各自独立 ----------------
    sp = StylePanel()
    got: list[dict] = []
    sp.style_changed.connect(lambda dct: got.append(dct))
    sp._fill_alpha_slider.setValue(20)
    sp._bg_alpha_slider.setValue(80)
    fills = [d["fill_color"] for d in got if "fill_color" in d]
    bgs = [d["bg_color"] for d in got if "bg_color" in d]
    a_fill = QColor(fills[-1]).alpha() if fills else -1
    a_bg = QColor(bgs[-1]).alpha() if bgs else -1
    pick_fill = QColor(sp._picked("fill_color", "#ff0000")).alpha()
    pick_bg = QColor(sp._picked("bg_color", "#00ff00")).alpha()
    ok_w3 = (a_fill == 51 and a_bg == 204 and pick_fill == 51 and pick_bg == 204)
    record("W3 填充透明度与背景透明度各自独立", ok_w3,
           f"fill={a_fill}/{pick_fill} bg={a_bg}/{pick_bg}")

    # ---------------- W4 边框开关 ----------------
    s = make_text()
    s.bg_color = QColor(0, 0, 255, 64)
    s.bg_border_color = QColor(220, 0, 0)
    n_off, _ = red_stats(render(s))
    s.bg_border = True
    n_on, _ = red_stats(render(s))
    ok_w4 = n_off == 0 and n_on > 40
    record("W4 启用边框后出现描边像素", ok_w4, f"off={n_off} on={n_on}")

    # ---------------- W5 边框颜色透明 ----------------
    s.bg_border_color = QColor(0, 0, 0, 0)
    n_trans, _ = red_stats(render(s))
    s.bg_border_color = QColor(220, 0, 0)
    ok_w5 = n_trans == 0
    record("W5 边框颜色设为透明等于不描边", ok_w5, f"transparent_pixels={n_trans}")

    # ---------------- W6 边框线宽 ----------------
    s.bg_border_width = 1
    n1, _ = red_stats(render(s))
    s.bg_border_width = 8
    n8, _ = red_stats(render(s))
    ok_w6 = n8 > n1 * 2
    record("W6 边框线宽 1 与 8 像素量不同", ok_w6, f"w1={n1} w8={n8}")

    # ---------------- W7 边框线型 ----------------
    s.bg_border_width = 4
    s.bg_border_style = "solid"
    n_solid, _ = red_stats(render(s))
    s.bg_border_style = "dash"
    n_dash, _ = red_stats(render(s))
    s.bg_border_style = "dot"
    n_dot, _ = red_stats(render(s))
    ok_w7 = n_solid > n_dash > 0 and n_solid > n_dot > 0 and n_dash != n_dot
    record("W7 边框实线 / 虚线 / 点线各不相同", ok_w7,
           f"solid={n_solid} dash={n_dash} dot={n_dot}")

    # ---------------- W8 只描边不填背景 ----------------
    s.bg_color = None
    s.bg_border = True
    s.bg_border_style = "solid"
    n_only, _ = red_stats(render(s))
    ok_w8 = n_only > 40
    record("W8 无背景色时也能单独显示边框", ok_w8, f"pixels={n_only}")

    # ---------------- W9 旋转文字时边框跟着转 ----------------
    s.bg_color = QColor(0, 0, 255, 64)
    s.angle = 90.0
    n_rot, center_rot = red_stats(render(s))
    want = QRectF(shape_text_box(s)).center()
    ok_w9 = (
        n_rot > 40 and center_rot is not None
        and abs(center_rot[0] - want.x()) <= 8
        and abs(center_rot[1] - want.y()) <= 8
    )
    record("W9 旋转文字时边框一起转且位置正确", ok_w9,
           f"pixels={n_rot} center={center_rot} want=({want.x():.1f},{want.y():.1f})")

    # ---------------- W10 面板边框信号 ----------------
    got.clear()
    sp._bg_border_check.setChecked(True)
    sp._bg_border_btns[0].click()
    sp._bg_border_transparent_btn.click()
    keys = [list(d)[0] for d in got]
    colors = [d["bg_border_color"] for d in got if "bg_border_color" in d]
    ok_w10 = (
        any(d.get("bg_border") is True for d in got)
        and len(colors) >= 2
        and QColor(colors[0]).alpha() == 255
        and QColor(colors[-1]).alpha() == 0
    )
    record("W10 面板启用边框 / 预设色 / ∅ 透明信号正确", ok_w10,
           f"keys={keys} alphas={[QColor(c).alpha() for c in colors]}")

    # ---------------- W11 set_state 回填 ----------------
    t = make_text()
    t.bg_color = QColor(0, 0, 255, 64)
    t.bg_border = True
    t.bg_border_color = QColor(255, 0, 0)
    t.bg_border_width = 7
    t.bg_border_style = "dash"
    sp.set_state(t, {})
    ok_w11 = (
        sp._bg_check.isChecked() and sp._bg_border_check.isChecked()
        and sp._bg_alpha_slider.value() == 25
        and sp._bg_border_width_slider.value() == 7
        and sp._bg_border_style_combo.currentData() == "dash"
        # 离屏下面板本身没 show()，子控件 isVisible() 恒 False，用 isHidden()
        and not sp._bg_border_transparent_btn.isHidden()
        and not sp._bg_border_width_slider.isHidden()
    )
    record("W11 面板状态回填颜色 / 透明度 / 线宽 / 线型", ok_w11,
           f"alpha={sp._bg_alpha_slider.value()} width={sp._bg_border_width_slider.value()} "
           f"style={sp._bg_border_style_combo.currentData()}")

    # ---------------- W12 Canvas 应用新样式键 ----------------
    cv = Canvas(make_image(400, 300), [], None)
    cv.resize(900, 600)
    cv._fit()
    ct = make_text()
    cv.shapes.append(ct)
    cv._selected = ct
    cv._apply_style({
        "bg_color": "#40ff0000",
        "bg_border": True,
        "bg_border_color": "#ff00aa00",
        "bg_border_width": 5,
        "bg_border_style": "dot",
    })
    ok_cv = (
        ct.bg_border is True and ct.bg_border_width == 5
        and ct.bg_border_style == "dot"
        and ct.bg_color.alpha() == 64
        and ct.bg_border_color.green() == 170
    )
    cv._selected = None
    cv._apply_style({"bg_border_width": 9, "bg_border_style": "dash"})
    ok_cv = ok_cv and cv._bg_border_width == 9 and cv._bg_border_style == "dash"
    record("W12 Canvas 选中标注与新建默认值都写入新键", ok_cv,
           f"shape=({ct.bg_border},{ct.bg_border_width},{ct.bg_border_style}) "
           f"default=({cv._bg_border_width},{cv._bg_border_style})")

    # ---------------- W13 Overlay 应用新样式键 ----------------
    ov = Overlay(make_image(400, 300), dpr=1.0)
    ot = make_text()
    ov.shapes.append(ot)
    ov._selected = ot
    ov._apply_style({
        "bg_border": True,
        "bg_border_color": "#ffff0000",
        "bg_border_width": 6,
        "bg_border_style": "dash",
    })
    ok_ov = (
        ot.bg_border is True and ot.bg_border_width == 6
        and ot.bg_border_style == "dash"
        and ot.bg_border_color.red() == 255
        and ov._bg_border_width == 6
    )
    record("W13 Overlay 同样写入新键", ok_ov,
           f"shape=({ot.bg_border},{ot.bg_border_width},{ot.bg_border_style})")

    # ---------------- W14 克隆与撤销保留边框字段 ----------------
    cl = Canvas._clone(ct)
    ok_cl = (
        cl.bg_border == ct.bg_border
        and cl.bg_border_width == ct.bg_border_width
        and cl.bg_border_style == ct.bg_border_style
        and QColor(cl.bg_border_color) == QColor(ct.bg_border_color)
    )
    cv2 = Canvas(make_image(400, 300), [], None)
    cv2.resize(900, 600)
    cv2._fit()
    cv2.shapes = [make_text()]
    cv2.shapes[0].bg_border = True
    cv2.shapes[0].bg_border_width = 6
    cv2.shapes[0].bg_border_style = "dash"
    cv2.shapes[0].bg_border_color = QColor(255, 0, 0)
    cv2.transform_image("cw")
    cv2.undo()
    u = cv2.shapes[0]
    ok_w14 = (
        ok_cl and u.bg_border is True and u.bg_border_width == 6
        and u.bg_border_style == "dash" and u.bg_border_color.red() == 255
    )
    record("W14 克隆 / 撤销恢复边框全部字段", ok_w14,
           f"clone={ok_cl} undo=({u.bg_border},{u.bg_border_width},{u.bg_border_style})")

    # ---------------- W15 文档与 i18n 同步 ----------------
    keys = ("背景透明度", "文字背景边框", "启用边框",
            "边框颜色", "边框线宽", "边框线型")
    ok_keys = all(k in ROWS and len(ROWS[k]) == 8 and all(ROWS[k]) for k in keys)
    readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
    markers = {
        "en": "Background opacity", "ja": "背景の不透明度",
        "ko": "배경 불투명도", "fr": "Opacité du fond",
        "de": "Hintergrund-Deckkraft", "es": "Opacidad del fondo",
        "zh_TW": "背景透明度",
    }
    missing = [code for code, mark in markers.items() if mark not in help_html(code)]
    ok_w15 = (
        "v23" in readme and "文字背景边框" in readme
        and "文字背景透明度" in HELP_HTML and "文字背景边框" in HELP_HTML
        and ok_keys and not missing
    )
    record("W15 README / 中文帮助 / 7 语言帮助 / 8 语言词条同步", ok_w15,
           f"keys={ok_keys} missing={missing}")

    for w in (sp, cv, ov, cv2):
        w.close()
        w.deleteLater()


def test_v24_text_input_position() -> None:
    """Stage X：文字提交后不跳位（QLineEdit 左上角 ≠ Shape.pos 基线）。"""
    from pathlib import Path

    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QPainter

    from i18n_docs import help_html
    from snapui import HELP_HTML
    from snapeditor import (
        Overlay, Shape, draw_shape, shape_rotate_point,
        text_edit_baseline_offset,
    )
    from snap_editor import Canvas

    def red_bbox(im: QImage):
        xs, ys = [], []
        for y in range(im.height()):
            for x in range(im.width()):
                c = im.pixelColor(x, y)
                if c.red() > 150 and c.green() < 90 and c.blue() < 90:
                    xs.append(x)
                    ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys)) if xs else None

    def edit_pixels(e, w, h):
        im = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        im.fill(QColor(255, 255, 255))
        e.render(im, e.pos())
        return red_bbox(im)

    def shape_pixels(s, w, h, base):
        im = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        im.fill(QColor(255, 255, 255))
        p = QPainter(im)
        p.setRenderHint(QPainter.Antialiasing, True)
        draw_shape(p, s, base, 1.0)
        p.end()
        return red_bbox(im)

    def shape_pixels_screen(cv, s, base):
        """把图像坐标里的标注按视图变换画到屏幕坐标，便于和输入框比像素。"""
        im = QImage(cv.width(), cv.height(), QImage.Format_ARGB32_Premultiplied)
        im.fill(QColor(255, 255, 255))
        p = QPainter(im)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.translate(cv.off_x, cv.off_y)
        p.scale(cv.view_scale, cv.view_scale)
        draw_shape(p, s, base, 1.0)
        p.end()
        return red_bbox(im)

    def aligned(a, b, tol=2):
        return (a is not None and b is not None
                and all(abs(x - y) <= tol for x, y in zip(a, b)))

    # ---------------- X1~X3 新建文字：像素对齐 / 旧写法确实跳位 ----------------
    rows = []
    for fs in (18, 28, 34, 48):
        base = make_image(600, 400, (255, 255, 255))
        ov = Overlay(base, dpr=1.0)
        ov._font_size = fs
        ov._begin_text(QPoint(100, 150))
        e = ov._text_edit
        e.setText("TEST")
        off = text_edit_baseline_offset(e)
        b_edit = edit_pixels(e, 600, 400)
        ov._commit_text()
        s = ov.shapes[-1]
        b_new = shape_pixels(s, 600, 400, base)
        # 旧实现：直接把输入框左上角当基线
        old = Shape(kind="text", text="TEST", pos=QPoint(e.pos()),
                    font_size=fs, color=QColor(s.color))
        b_old = shape_pixels(old, 600, 400, base)
        rows.append((fs, off, b_edit, b_new,
                     b_edit[1] - b_old[1] if b_edit and b_old else 0))
        ov.close()
        ov.deleteLater()

    dys = [r[1].y() for r in rows]
    ok_x1 = (all(r[1].x() > 0 and r[1].y() >= r[0] * 0.6 for r in rows)
             and dys == sorted(dys) and dys[0] < dys[-1])
    record("X1 左上角→基线偏移随字号增长且非零", ok_x1,
           f"offsets={[(r[0], r[1].x(), r[1].y()) for r in rows]}")

    ok_x2 = all(aligned(r[2], r[3], 2) for r in rows)
    record("X2 各字号输入框文字与提交后绘制像素重合", ok_x2,
           f"pairs={[(r[0], r[2], r[3]) for r in rows]}")

    ok_x3 = all(r[4] >= 15 for r in rows)
    record("X3 回归锁定：旧写法会让文字上跳 ≥15px", ok_x3,
           f"jumps={[(r[0], r[4]) for r in rows]}")

    # ---------------- X4 Overlay 双击编辑：反放输入框、位置不漂移 ----------------
    base = make_image(600, 400, (255, 255, 255))
    ov = Overlay(base, dpr=1.0)
    ov._font_size = 34
    s = Shape(kind="text", text="HELLO", pos=QPoint(150, 220))
    s.font_size = 34
    s.color = QColor(255, 59, 48)
    ov.shapes.append(s)
    ov._selected = s
    b_before = shape_pixels(s, 600, 400, base)
    ov._begin_text(QPoint(0, 0), existing=s)
    e = ov._text_edit
    off = text_edit_baseline_offset(e)
    # 双击编辑默认全选文本（蓝底白字），先取消选区才能比对字形颜色
    e.deselect()
    b_edit4 = edit_pixels(e, 600, 400)
    placed = e.pos() == s.pos - off
    e.setText("WORLD")
    ov._commit_text()
    ok_x4 = (placed and s.pos == QPoint(150, 220) and s.text == "WORLD"
             and aligned(b_before, b_edit4, 2))
    record("X4 双击编辑时输入框盖在原字上、提交后坐标不变", ok_x4,
           f"placed={placed} pos={s.pos} bbox={b_before}/{b_edit4}")
    ov.close()
    ov.deleteLater()

    # ---------------- X5 Canvas 新建（1:1）像素对齐 ----------------
    base = make_image(900, 600, (255, 255, 255))
    cv = Canvas(base, [], None)
    cv.resize(1000, 700)
    cv._fit()
    cv._set_view_scale(1.0)
    cv._font_size = 30
    cv._set_tool("text")
    cv._begin_text(QPoint(200, 240))
    e = cv._text_edit
    e.setText("TEST")
    b_edit5 = edit_pixels(e, cv.width(), cv.height())
    want5 = cv._to_image(e.pos() + text_edit_baseline_offset(e))
    cv._commit_text()
    s5 = cv.shapes[-1]
    b_new5 = shape_pixels_screen(cv, s5, base)
    ok_x5 = s5.pos == want5 and aligned(b_edit5, b_new5, 4)
    record("X5 窗口编辑器 1:1 视图：提交后文字像素不位移", ok_x5,
           f"pos={s5.pos} want={want5} bbox={b_edit5}/{b_new5}")

    # ---------------- X6 Canvas 缩放视图 ----------------
    zoom = []
    for vs in (0.75, 1.5, 0.5):
        c = Canvas(base, [], None)
        c.resize(1000, 700)
        c._fit()
        c._set_view_scale(vs)
        c._font_size = 30
        c._set_tool("text")
        c._begin_text(QPoint(200, 240))
        ed = c._text_edit
        ed.setText("TEST")
        b_e = edit_pixels(ed, c.width(), c.height())
        want = c._to_image(ed.pos() + text_edit_baseline_offset(ed))
        c._commit_text()
        sh = c.shapes[-1]
        b_s = shape_pixels_screen(c, sh, base)
        zoom.append((vs, sh.pos == want, aligned(b_e, b_s, 6)))
        c.close()
        c.deleteLater()
    ok_x6 = all(a and b for _, a, b in zoom)
    record("X6 放大 / 缩小视图下按屏幕字号换算仍对齐", ok_x6, f"scales={zoom}")

    # ---------------- X7 Canvas 双击编辑（含旋转文字）往返 ----------------
    cv7 = Canvas(base, [], None)
    cv7.resize(1000, 700)
    cv7._fit()
    s7 = Shape(kind="text", text="HELLO", pos=QPoint(300, 260))
    s7.font_size = 28
    s7.color = QColor(255, 59, 48)
    cv7.shapes = [s7]
    cv7._selected = s7
    roundtrip = []
    for ang in (0.0, 90.0, -35.0):
        s7.angle = ang
        before = QPoint(s7.pos)
        cv7._begin_text(QPoint(0, 0), existing=s7)
        ed = cv7._text_edit
        off = text_edit_baseline_offset(ed)
        want = cv7._to_screen(shape_rotate_point(s7, before)) - off
        placed7 = ed.pos() == want
        ed.setText("EDIT")
        cv7._commit_text()
        roundtrip.append((ang, placed7, s7.pos == before))
    ok_x7 = all(a and b for _, a, b in roundtrip)
    record("X7 双击编辑（含旋转文字）输入框落点正确、坐标不漂移", ok_x7,
           f"roundtrip={roundtrip}")
    cv7.close()
    cv7.deleteLater()

    # ---------------- X8 高 DPI 遮罩 ----------------
    ov8 = Overlay(make_image(600, 400, (255, 255, 255)), dpr=2.0)
    ov8._font_size = 28
    ov8._begin_text(QPoint(100, 150))
    ed8 = ov8._text_edit
    ed8.setText("TEST")
    target8 = ed8.pos() + text_edit_baseline_offset(ed8)
    ov8._commit_text()
    s8 = ov8.shapes[-1]
    phys = ov8.to_phys(QRect(s8.pos.x(), s8.pos.y(), 1, 1)).topLeft()
    ok_x8 = (s8.pos == target8
             and abs(phys.x() - target8.x() * 2) <= 1
             and abs(phys.y() - target8.y() * 2) <= 1)
    record("X8 高 DPI 遮罩逻辑坐标 / 物理坐标换算不丢偏移", ok_x8,
           f"pos={s8.pos} phys={phys}")
    ov8.close()
    ov8.deleteLater()

    # ---------------- X9 连续输入与撤销 ----------------
    cv9 = Canvas(base, [], None)
    cv9.resize(1000, 700)
    cv9._fit()
    cv9._set_tool("text")
    want9 = []
    for pt in (QPoint(120, 120), QPoint(360, 280)):
        cv9._begin_text(pt)
        ed = cv9._text_edit
        ed.setText("AB")
        want9.append(cv9._to_image(ed.pos() + text_edit_baseline_offset(ed)))
        cv9._commit_text()
    ok_before = len(cv9.shapes) == 2 and cv9.shapes[0].pos == want9[0] \
        and cv9.shapes[1].pos == want9[1]
    cv9.undo()
    ok_x9 = (ok_before and len(cv9.shapes) == 1
             and cv9.shapes[0].pos == want9[0])
    record("X9 连续输入互不干扰、撤销恢复正确位置", ok_x9,
           f"positions={want9} undo_count={len(cv9.shapes)}")
    cv9.close()
    cv9.deleteLater()
    cv.close()
    cv.deleteLater()

    # ---------------- X10 文档同步 ----------------
    readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
    markers = {
        "en": "where you typed", "ja": "入力した位置",
        "ko": "입력한 위치", "fr": "position saisie",
        "de": "eingegebenen Position", "es": "posición escrita",
        "zh_TW": "輸入的位置",
    }
    missing = [code for code, mark in markers.items()
               if mark not in help_html(code)]
    ok_x10 = ("v24" in readme and "文字输入位置" in readme
              and "输入位置" in HELP_HTML and not missing)
    record("X10 README / 中文帮助 / 7 语言帮助同步输入位置修复", ok_x10,
           f"missing={missing}")


def test_v25_bundle_size() -> None:
    """Stage Y：v25 绿色版瘦身只改打包配置，锁住过滤规则与 optimize 设置。"""
    import re
    from pathlib import Path

    spec = Path(__file__).with_name("SnapTool.spec").read_text(encoding="utf-8")
    readme = Path(__file__).with_name("README.md").read_text(encoding="utf-8")

    # ---------------- Y1 冗余文件过滤规则仍在 ----------------
    must_drop = (
        "opencv_videoio_ffmpeg", "opengl32sw.dll", "qt6qml",
        "qt6virtualkeyboard", "qt6opengl", "qt6svg",
        "plugins/platforms/qdirect2d", "plugins/imageformats/qgif",
        "plugins/tls/", "pil/_avif", "cryptography/hazmat/bindings/_rust",
        "onnxruntime/datasets/", "onnxruntime/tools/", ".dist-info/",
        "chardet/models/", "certifi/cacert.pem",
    )
    missing = [k for k in must_drop if k not in spec]
    record("Y1 spec 保留冗余文件过滤规则", not missing, f"missing={missing}")

    # ---------------- Y2 过滤名单不能误伤必需文件 ----------------
    def tuple_items(var: str) -> list[str]:
        m = re.search(var + r"\s*=\s*\((.*?)\n\)", spec, re.S)
        return re.findall(r"'([^']+)'", m.group(1)) if m else []

    items = [x.lower() for x in tuple_items("_drop_binaries")
             + tuple_items("_drop_datas")]
    forbidden = (
        "cv2/cv2", "pp-ocrv6", "onnxruntime/capi", "qt6core", "qt6gui",
        "qt6widgets", "qt6network", "qwindows", "qico", "qjpeg", "qwebp",
        "libcrypto", "libssl", "ocr_test", "app.ico", "avatar",
    )
    bad = [(k, f) for k in items for f in forbidden if f in k]
    record("Y2 过滤规则不误伤必需依赖", bool(items) and not bad,
           f"rules={len(items)} bad={bad}")

    # ---------------- Y3 optimize 必须保持 0 ----------------
    ok_y3 = (re.search(r"optimize\s*=\s*0\s*,", spec) is not None
             and "numpy" in spec and "docstring" in spec)
    record("Y3 optimize=0（numpy docstring 回归锁定）", ok_y3,
           f"optimize0={bool(re.search(r'optimize\s*=\s*0\s*,', spec))}")

    # ---------------- Y4 README 体积数字同步 ----------------
    marks = ("v25", "265 MB", "117 MB", "238 项")
    absent = [m for m in marks if m not in readme]
    record("Y4 README 同步 v25 体积数字", not absent, f"absent={absent}")


def test_v26_copy_button() -> None:
    print("\n--- Stage Z: v26 确认阶段复制按钮 ---")
    import inspect
    from pathlib import Path
    from unittest.mock import MagicMock

    import snap as snapmod
    import i18n
    import i18n_docs
    from snapeditor import Shape

    # Z1 确认模式：复制按钮可见，且排在「确定 / ✕」最左侧
    base = QImage(400, 200, QImage.Format_RGB32)
    base.fill(QColor(30, 120, 220))
    ov = Overlay(base, dpr=2.0)
    ov.resize(200, 100)
    ov.toolbar.set_confirm_mode(True)
    shown = [k for k in ov.toolbar._actions if not ov.toolbar._actions[k].isHidden()]
    ok_z1 = (
        "复制" in shown
        and shown.index("复制") < shown.index("确定") < shown.index("✕")
        and all(k not in shown for k in ("撤销", "取字", "保存", "长截图"))
    )
    record("Z1 确认模式显示复制按钮且排最左", ok_z1, f"shown={shown}")
    ov.toolbar.set_confirm_mode(False)

    # Z2/Z3 点复制：发原图（不含标注），不进编辑器
    ov2 = Overlay(base, dpr=2.0)
    ov2.resize(200, 100)
    ov2.sel = QRect(50, 40, 60, 30)
    ov2._mode = "editing"
    ov2.shapes = [Shape(kind="rect", rect=QRect(50, 40, 30, 20), color=QColor(255, 0, 0))]
    got: dict = {}
    ov2.copy_only.connect(lambda im: got.setdefault("img", im.copy()))
    ov2.to_editor.connect(lambda *_: got.setdefault("editor", True))
    ov2._copy_only()
    expect = base.copy(QRect(100, 80, 120, 60))
    im = got.get("img")
    ok_z2 = (
        im is not None
        and im.size() == expect.size()
        and im.pixelColor(0, 0) == expect.pixelColor(0, 0)
    )
    record("Z2 复制按钮发出原图（不含标注）", ok_z2,
           f"size={im.size() if im else None} expect={expect.size()}")
    ok_z3 = not got.get("editor", False) and ov2._confirm_mode is False
    record("Z3 点复制不进编辑器、遮罩确认态复位", ok_z3,
           f"editor={got.get('editor', False)} confirm={ov2._confirm_mode}")

    # Z4 App 收到信号：写剪贴板 + 关闭遮罩
    fake = MagicMock()
    cimg = QImage(64, 32, QImage.Format_RGB32)
    cimg.fill(QColor(9, 8, 7))
    snapmod.App._on_copy_only(fake, cimg)
    snapmod.App._copy_to_clipboard(cimg)
    clip = QApplication.clipboard().image()
    ok_z4 = (
        fake._copy_to_clipboard.called
        and fake._copy_to_clipboard.call_args[0][0].size() == cimg.size()
        and fake._close_overlay.called
        and clip.size() == cimg.size()
        and clip.pixelColor(1, 1) == cimg.pixelColor(1, 1)
    )
    record("Z4 App 复制并关闭遮罩、剪贴板内容正确", ok_z4,
           f"clip={clip.size()} close={fake._close_overlay.called}")

    # Z5 全屏直截 / 长截图完成路径也自动复制
    src_init = inspect.getsource(snapmod.App._begin_capture)
    src_long = inspect.getsource(snapmod.App._on_long_shot)
    src_overlay_init = inspect.getsource(snapmod.Overlay.__init__)
    src_copy = inspect.getsource(snapmod.Overlay._copy_only)
    ok_z5 = (
        "self.overlay.copy_only.connect(self._on_copy_only)" in src_init
        and "self.toolbar.copy_clicked.connect(self._copy_only)" in src_overlay_init
        and "self.raw_crop()" in src_copy
        and "self._copy_to_clipboard(qimg)" in src_long
        and "copied=True" in src_long
    )
    record("Z5 全屏/长截图完成自动复制接线", ok_z5,
           f"init={src_init.count('copy_only')} long={src_long.count('_copy_to_clipboard')}")

    # Z6 文档同步
    readme = Path("README.md").read_text(encoding="utf-8")
    help_zh = Path("snapui.py").read_text(encoding="utf-8")
    marks = {
        "en": "far left of the toolbar", "ja": "ツールバー左端",
        "ko": "도구 모음 맨 왼쪽", "fr": "tout à gauche",
        "de": "ganz links", "es": "a la izquierda",
        "zh_TW": "工具條最左側",
    }
    bad = [c for c, m in marks.items() if m not in i18n_docs.help_html(c)]
    ok_z6 = (
        not bad
        and "v26" in readme and "不打开程序窗口" in readme
        and "不打开编辑器" in help_zh
    )
    record("Z6 README / 中文帮助 / 7 语言帮助同步", ok_z6,
           f"bad={bad} readme={'v26' in readme}")


def test_v27_copy_closes_windows() -> None:
    print("\n--- Stage AA: v27 复制关两窗 / 打勾开编辑器 ---")
    import inspect
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    import snap as snapmod
    from snap_editor import EditorWindow

    # AA1 复制路径：复制原图 + 不恢复旧窗口 + 关编辑器 + 隐藏主窗口
    fake = MagicMock()
    fake._hidden_windows = ["stale"]
    cimg = QImage(48, 24, QImage.Format_RGB32)
    cimg.fill(QColor(5, 6, 7))
    snapmod.App._on_copy_only(fake, cimg)
    fake._close_overlay.assert_called_once_with(restore=False)
    ok_aa1 = (
        fake._copy_to_clipboard.called
        and fake._close_editor_silently.called
        and fake.main_window.hide.called
        and fake._hidden_windows == []
    )
    record("AA1 复制关闭截图编辑与截屏助手、不恢复旧窗口", ok_aa1,
           f"restore={fake._close_overlay.call_args} "
           f"editor={fake._close_editor_silently.called} "
           f"main_hide={fake.main_window.hide.called} hidden={fake._hidden_windows}")

    # AA2 关闭旧编辑器先断开 closed 回调，避免主窗口被弹回来
    ed = MagicMock()
    fake2 = MagicMock()
    fake2.editor = ed
    snapmod.App._close_editor_silently(fake2)
    ok_aa2 = (
        fake2.editor is None
        and ed.closed.disconnect.called
        and ed.close.called
        and ed.deleteLater.called
        and not fake2._on_editor_closed.called
    )
    record("AA2 关闭编辑器先断开 closed 回调", ok_aa2,
           f"editor={fake2.editor} disconnect={ed.closed.disconnect.called} "
           f"close={ed.close.called}")

    # AA3 真实编辑器：silent close 不触发回调且窗口隐藏
    real_ed = EditorWindow(QImage(80, 60, QImage.Format_RGB32), [], Path("."))
    holder = SimpleNamespace(editor=real_ed, calls=0)
    def _on_closed() -> None:
        holder.calls += 1
    holder._on_editor_closed = _on_closed
    real_ed.closed.connect(_on_closed)
    real_ed.show()
    snapmod.App._close_editor_silently(holder)
    ok_aa3 = holder.editor is None and holder.calls == 0 and not real_ed.isVisible()
    record("AA3 真实编辑器关闭后回调未触发且窗口隐藏", ok_aa3,
           f"calls={holder.calls} visible={real_ed.isVisible()}")
    real_ed.deleteLater()

    # AA4 打勾路径：隐藏主窗口 + 打开编辑器
    fake3 = MagicMock()
    fake3.overlay = MagicMock()
    fake3.editor = MagicMock()
    fake3._hidden_windows = []
    snapmod.App._on_to_editor(fake3, cimg, [])
    ok_aa4 = fake3.main_window.hide.called and fake3._open_editor.called
    record("AA4 打勾打开截图编辑窗口并保持主窗口隐藏", ok_aa4,
           f"hide={fake3.main_window.hide.called} open={fake3._open_editor.called}")

    # AA5 源码接线锁定
    src_copy = inspect.getsource(snapmod.App._on_copy_only)
    src_silent = inspect.getsource(snapmod.App._close_editor_silently)
    src_open = inspect.getsource(snapmod.App._open_editor)
    src_to = inspect.getsource(snapmod.App._on_to_editor)
    ok_aa5 = (
        "_close_overlay(restore=False)" in src_copy
        and "self.main_window.hide()" in src_copy
        and "self.editor = None" in src_silent
        and "closed.disconnect" in src_silent
        and "self._close_editor_silently()" in src_open
        and "self.main_window.hide()" in src_to
        and "self._open_editor(base_img, shapes)" in src_to
    )
    record("AA5 复制 / 打勾两条路径源码接线正确", ok_aa5,
           f"copy_restore={src_copy.count('restore=False')} "
           f"to_hide={src_to.count('main_window.hide')}")

    # AA6 文档同步
    readme = Path("README.md").read_text(encoding="utf-8")
    help_zh = Path("snapui.py").read_text(encoding="utf-8")
    marks = ("v27", "关闭截图编辑与截屏助手两个窗口", "合计 250 项", "dist/v16")
    missing = [m for m in marks if m not in readme]
    ok_aa6 = (
        not missing
        and "并关闭截图编辑与截屏助手两个窗口" in help_zh
        and "点「确定」打开截图编辑窗口" in help_zh
    )
    record("AA6 README / 中文帮助同步 v27 窗口行为", ok_aa6,
           f"missing={missing}")


def test_v28_warmup_and_input_gate() -> None:
    print("\n--- Stage AB: v28 启动预热 + 首帧输入门闩 ---")
    import inspect
    from pathlib import Path
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QApplication

    import snap as snapmod

    def ov_ev(typ, p: QPoint):
        return QMouseEvent(typ, QPoint(p), QPoint(p), Qt.LeftButton,
                           Qt.LeftButton, Qt.NoModifier)

    # AB1 门闩默认开放：直接构造的 Overlay 可立即接收鼠标（兼容既有自测）
    ov = Overlay(QImage(200, 100, QImage.Format_RGB32), dpr=1.0)
    ov.resize(200, 100)
    ok_ab1 = ov._ready is True
    record("AB1 Overlay 默认输入开放（不破坏离线自测）", ok_ab1,
           f"ready={ov._ready}")

    # AB2 lock_input 上闩 + 等待光标；上闩后鼠标按下被吞、不进入 selecting
    ov.lock_input()
    ov._mode = "idle"
    ov.mousePressEvent(ov_ev(QEvent.Type.MouseButtonPress, QPoint(40, 30)))
    ok_ab2a = (
        ov._ready is False
        and ov.cursor().shape() == Qt.WaitCursor
        and ov._mode == "idle"
        and ov.sel is None
    )
    record("AB2 上闩后吞掉鼠标按下、无选区、显示等待光标", ok_ab2a,
           f"ready={ov._ready} cursor={ov.cursor().shape()} mode={ov._mode} sel={ov.sel}")

    # AB3 移动同样被吞（不产生 hover / 不改光标）
    ov.mouseMoveEvent(ov_ev(QEvent.Type.MouseMove, QPoint(90, 60)))
    ok_ab3 = ov._ready is False and ov._mode == "idle"
    record("AB3 上闩后吞掉鼠标移动", ok_ab3, f"mode={ov._mode}")

    # AB4 真正绘制一帧后 unlock_input 由 paintEvent 调度；直接验证解锁恢复十字
    ov.unlock_input()
    ok_ab4 = ov._ready is True and ov.cursor().shape() == Qt.CrossCursor
    record("AB4 解锁后恢复十字光标与输入", ok_ab4,
           f"ready={ov._ready} cursor={ov.cursor().shape()}")
    ov.close()

    # AB5 paintEvent 末尾确实挂了解锁调度（两种模式分支都要有）
    src_paint = inspect.getsource(Overlay.paintEvent)
    src_press = inspect.getsource(Overlay.mousePressEvent)
    src_move = inspect.getsource(Overlay.mouseMoveEvent)
    src_release = inspect.getsource(Overlay.mouseReleaseEvent)
    ok_ab5 = (
        src_paint.count("QTimer.singleShot(0, self.unlock_input)") == 2
        and "if not self._ready:" in src_press
        and "if not self._ready:" in src_move
        and "if not self._ready:" in src_release
    )
    record("AB5 两个绘制分支 + 三个鼠标入口都接了门闩/解锁", ok_ab5,
           f"unlock_sched={src_paint.count('unlock_input')} "
           f"guards={sum('if not self._ready:' in s for s in (src_press, src_move, src_release))}")

    # AB6 宿主流程：show 前上闩、show 后同步 repaint
    src_begin = inspect.getsource(snapmod.App._begin_capture)
    lock_pos = src_begin.find("lock_input()")
    repaint_pos = src_begin.find("repaint()")
    show_pos = src_begin.find("self.overlay.show()")
    ok_ab6 = (
        lock_pos > 0 and repaint_pos > lock_pos and show_pos > lock_pos
        and repaint_pos > show_pos
    )
    record("AB6 宿主 show 前上闩、show 后同步 repaint", ok_ab6,
           f"lock={lock_pos} show={show_pos} repaint={repaint_pos}")

    # AB7 启动预热方法存在，且用 singleShot(0) 调度、不阻塞启动
    src_init = inspect.getsource(snapmod.App.__init__)
    src_warm = inspect.getsource(snapmod.App._warmup)
    ok_ab7 = (
        "QTimer.singleShot(0, self._warmup)" in src_init
        and "probe.render(surface)" in src_warm
        and "Overlay(warm_img" in src_warm
        and "grab_region" in src_warm
        and "except Exception" in src_warm
    )
    record("AB7 启动预热构造+离屏绘制+抓屏后端且异常吞掉", ok_ab7,
           f"scheduled={'self._warmup' in src_init} render={'render' in src_warm}")

    # AB8 预热真的能跑通（离屏环境不应抛异常、不应留下可见窗口）
    fake = MagicMock()
    try:
        snapmod.App._warmup(fake)
        warm_ok = True
    except Exception as exc:  # noqa: BLE001
        warm_ok = False
        warm_err = repr(exc)
    ok_ab8 = warm_ok
    record("AB8 预热离屏空跑无异常", ok_ab8,
           f"ok={warm_ok} {'' if warm_ok else warm_err}")

    # AB9 lock_input 带兜底 timer，异常时也能解锁不卡死
    src_lock = inspect.getsource(Overlay.lock_input)
    ok_ab9 = "QTimer.singleShot(200, self.unlock_input)" in src_lock
    record("AB9 上闩带 200ms 兜底解锁，绝不卡死输入", ok_ab9,
           f"fallback={'singleShot(200' in src_lock}")

    # AB10 行为级：完整走一遍 上闩→show→绘制→事件循环→自动解锁
    ov2 = Overlay(QImage(120, 80, QImage.Format_RGB32), 1.0)
    ov2.setGeometry(0, 0, 120, 80)
    ov2.lock_input()
    ov2.show()
    ov2.update()
    app = QApplication.instance()
    app.processEvents()
    app.processEvents()
    ok_ab10 = ov2._ready is True and ov2.cursor().shape() == Qt.CrossCursor
    record("AB10 首帧绘制后经事件循环自动解锁（行为级）", ok_ab10,
           f"ready={ov2._ready} cursor={ov2.cursor().shape()}")
    ov2.close()

    # AB11 README 仍保留 v28 预热特性描述（历史版本记录，不写死当前总数）
    readme = Path("README.md").read_text(encoding="utf-8")
    ok_ab11 = "v28" in readme and "预热" in readme
    record("AB11 README 保留 v28 预热特性记录", ok_ab11,
           f"v28={'v28' in readme} warmup={'预热' in readme}")


def test_v31_sticky_tools_and_single_instance() -> None:
    print("\n--- Stage AC: v31 工具粘滞 + 单实例不弹框 ---")
    import inspect
    from pathlib import Path

    from PySide6.QtCore import QEvent, QPoint, QRect
    from PySide6.QtGui import QImage, QMouseEvent
    from PySide6.QtWidgets import QApplication

    import snap as snapmod
    from snapeditor import Overlay, Toolbar
    from snap_editor import Canvas

    def mk_ev(typ, p: QPoint, button=Qt.LeftButton):
        return QMouseEvent(typ, QPoint(p), QPoint(p), button,
                           button, Qt.NoModifier)

    # AC1 工具条：点不同工具=切换；再点当前工具=取消回 select
    tb = Toolbar(None)
    tb._on_tool("arrow")
    ok_ac1a = tb.current == "arrow" and tb._buttons["arrow"].isChecked()
    tb._on_tool("arrow")  # 再次点击同一工具 → 取消
    ok_ac1b = tb.current == "select" and not tb._buttons["arrow"].isChecked()
    tb._on_tool("rect")
    ok_ac1c = tb.current == "rect" and tb._buttons["rect"].isChecked()
    record("AC1 工具条切换/再次点击取消/切回选择", ok_ac1a and ok_ac1b and ok_ac1c,
           f"a={ok_ac1a} b={ok_ac1b} c={ok_ac1c}")
    tb.close()

    # AC2 行为级 Canvas：画完一个箭头仍保持 arrow 工具，可接着画第二个
    base = make_image(160, 100)
    cv = Canvas(base, [], None)
    cv._set_tool("arrow")
    # 第一个箭头
    cv.mousePressEvent(mk_ev(QEvent.Type.MouseButtonPress, QPoint(20, 20)))
    cv.mouseMoveEvent(mk_ev(QEvent.Type.MouseMove, QPoint(60, 60)))
    cv.mouseReleaseEvent(mk_ev(QEvent.Type.MouseButtonRelease, QPoint(60, 60)))
    after_first = (len(cv.shapes), cv._tool)
    # 第二个箭头（同一次工具会话内）
    cv.mousePressEvent(mk_ev(QEvent.Type.MouseButtonPress, QPoint(80, 30)))
    cv.mouseMoveEvent(mk_ev(QEvent.Type.MouseMove, QPoint(130, 70)))
    cv.mouseReleaseEvent(mk_ev(QEvent.Type.MouseButtonRelease, QPoint(130, 70)))
    after_second = (len(cv.shapes), cv._tool)
    ok_ac2 = (
        after_first == (1, "arrow")
        and after_second == (2, "arrow")
    )
    record("AC2 Canvas 连续画两个箭头且保持工具", ok_ac2,
           f"first={after_first} second={after_second}")
    cv.close()

    # AC3 行为级 Overlay：画完矩形仍保持 rect 工具（遮罩内粘滞同样生效）
    ov = Overlay(QImage(200, 120, QImage.Format_RGB32), dpr=1.0)
    ov.setGeometry(0, 0, 200, 120)
    ov._mode = "editing"             # 选区确认后的编辑态，允许选区内绘制
    ov._tool = "rect"
    ov.sel = QRect(0, 0, 200, 120)
    ov.mousePressEvent(mk_ev(QEvent.Type.MouseButtonPress, QPoint(20, 20)))
    ov.mouseMoveEvent(mk_ev(QEvent.Type.MouseMove, QPoint(60, 60)))
    ov.mouseReleaseEvent(mk_ev(QEvent.Type.MouseButtonRelease, QPoint(60, 60)))
    ok_ac3 = len(ov.shapes) == 1 and ov._tool == "rect"
    record("AC3 Overlay 画完矩形保持 rect 工具", ok_ac3,
           f"shapes={len(ov.shapes)} tool={ov._tool}")

    # AC4 右键结束粘滞：Overlay 右键回 select、不取消截图
    ov.mousePressEvent(mk_ev(QEvent.Type.MouseButtonPress, QPoint(100, 90),
                             Qt.RightButton))
    ok_ac4 = ov._tool == "select" and ov.sel is not None
    record("AC4 Overlay 右键结束工具回 select 且不取消截图", ok_ac4,
           f"tool={ov._tool} sel={ov.sel}")
    ov.close()

    # AC5 行为级 Canvas：右键结束工具回 select，编辑器不关
    cv2 = Canvas(make_image(160, 100), [], None)
    cv2._set_tool("ellipse")
    cv2.mousePressEvent(mk_ev(QEvent.Type.MouseButtonPress, QPoint(30, 30),
                              Qt.RightButton))
    ok_ac5 = cv2._tool == "select" and cv2.isVisible() is False  # 未建立窗口，仅验证工具态
    record("AC5 Canvas 右键结束工具回 select", ok_ac5,
           f"tool={cv2._tool}")
    cv2.close()

    # AC6 文字提交后保持文字工具（两处源码接线）
    src_ov_commit = inspect.getsource(Overlay._commit_text)
    src_cv_commit = inspect.getsource(Canvas._commit_text)
    ok_ac6 = (
        "_set_tool(\"select\")" not in src_ov_commit
        and "_set_tool(\"select\")" not in src_cv_commit
    )
    record("AC6 文字提交后不切回 select（覆盖两编辑器）", ok_ac6,
           f"ov={'select' in src_ov_commit} cv={'select' in src_cv_commit}")

    # AC7 绘制完成后不切回 select（两处 mouseReleaseEvent 源码）
    src_ov_rel = inspect.getsource(Overlay.mouseReleaseEvent)
    src_cv_rel = inspect.getsource(Canvas.mouseReleaseEvent)
    ok_ac7 = (
        "self.toolbar._on_tool(\"select\")" not in src_ov_rel
        and "self.toolbar._on_tool(\"select\")" not in src_cv_rel
    )
    record("AC7 绘制完成不切回 select（覆盖两编辑器）", ok_ac7,
           f"ov={'on_tool' in src_ov_rel} cv={'on_tool' in src_cv_rel}")

    # AC8 单实例：默认路径不弹对话框，signal_existing 后直接返回 False
    src_resolve = inspect.getsource(snapmod._resolve_existing_instance)
    default_block = src_resolve.split("if not restart:")[1].split("killed =")[0]
    ok_ac8 = (
        "MessageBoxW" not in default_block
        and "return False" in default_block
        and "signal_existing()" in src_resolve
    )
    record("AC8 单实例默认唤醒不弹框、直接退出新进程", ok_ac8,
           f"no_dialog={'MessageBoxW' not in default_block} "
           f"returns_false={'return False' in default_block}")

    # AC9 显式 --restart 仍保留重启链路
    restart_block = src_resolve.split("killed =")[1]
    ok_ac9 = "kill_recorded" in restart_block and "return True" in restart_block
    record("AC9 显式 --restart 保留强制重启链路", ok_ac9,
           f"kill={'kill_recorded' in restart_block}")

    # AC10 7 种绘制工具都在 TOOLS 中（粘滞覆盖全部标注命令）
    from snapeditor import TOOLS
    tool_keys = {k for k, _ in TOOLS}
    need = {"rect", "ellipse", "arrow", "line", "pen", "mosaic", "text"}
    ok_ac10 = need.issubset(tool_keys)
    record("AC10 七种标注工具全部纳入粘滞", ok_ac10,
           f"tools={sorted(tool_keys)}")

    # AC11 README 同步到 v31 / 工具粘滞与单实例行为
    readme = Path("README.md").read_text(encoding="utf-8")
    ok_ac11 = (
        "v31" in readme
        and "粘滞" in readme
        and "不再弹" in readme
    )
    record("AC11 README 同步 v31 工具粘滞与单实例行为", ok_ac11,
           f"v31={'v31' in readme} sticky={'粘滞' in readme} "
           f"nodlg={'不再弹' in readme}")


# ---------------------------------------------------------------------------
def test_v32_pen_smoothing() -> None:
    print("\n--- Stage AD: v32 画笔笔迹平滑 ---")
    from pathlib import Path
    import random

    from PySide6.QtCore import QEvent, QPoint, QPointF
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from snapeditor import _smooth_polyline

    def mk_ev(typ, p: QPoint, button=Qt.LeftButton):
        return QMouseEvent(typ, QPoint(p), QPoint(p), button,
                           button, Qt.NoModifier)

    # AD1 平滑函数存在，返回 QPainterPath 且首尾锚点精确
    path = _smooth_polyline(QPointF(0, 0), [QPointF(10, 5), QPointF(20, 0)],
                            QPointF(30, 5))
    ok_ad1 = (
        hasattr(path, "elementCount") and path.elementCount() > 0
        and path.pointAtPercent(0) == QPointF(0, 0)
        and path.pointAtPercent(1) == QPointF(30, 5)
    )
    record("AD1 平滑路径首尾锚点精确保留", ok_ad1,
           f"start={path.pointAtPercent(0)} end={path.pointAtPercent(1)}")

    # AD2 路径含有曲线段（不再是逐点直线折线）
    types = [path.elementAt(i).type for i in range(path.elementCount())]
    has_curve = any("CurveTo" in str(t) for t in types)
    record("AD2 画笔路径使用贝塞尔曲线段", has_curve,
           f"types={[str(t).split('.')[-1] for t in types]}")

    # AD3 行为级：模拟真实手抖（水平线 ±2px 高频抖动），平滑后相邻抖动明显下降
    random.seed(7)
    shaky = [QPointF(0, 100)]
    x = 0
    for _ in range(30):
        x += 3
        shaky.append(QPointF(x, 100 + random.choice([-2, -1, -1, 0, 0, 0, 1, 1, 2])))
    sm = _smooth_polyline(shaky[0], shaky[1:-1], shaky[-1])
    curve_pts = [sm.pointAtPercent(i / 60) for i in range(61)]

    def avg_dy(seq):
        return sum(abs(seq[i + 1].y() - seq[i].y()) for i in range(len(seq) - 1)) / (len(seq) - 1)

    raw_jitter, smooth_jitter = avg_dy(shaky), avg_dy(curve_pts)
    ok_ad3 = smooth_jitter < raw_jitter * 0.5
    record("AD3 手抖锯齿被平顺（相邻抖动降幅>50%）", ok_ad3,
           f"raw={raw_jitter:.2f}px smooth={smooth_jitter:.2f}px")

    # AD4 两个编辑器 mouseMove 都做了最小间距过滤（丢弃几乎重合的采样点）
    import inspect
    from snapeditor import Overlay as Ovl
    from snap_editor import Canvas as Cvs
    src_ov = inspect.getsource(Ovl.mouseMoveEvent)
    src_cv = inspect.getsource(Cvs.mouseMoveEvent)
    ok_ad4 = (
        "manhattanLength() >= pen_smooth_min_step()" in src_ov
        and "manhattanLength() >= pen_smooth_min_step()" in src_cv
    )
    record("AD4 两编辑器采集端都过滤重合抖动点", ok_ad4,
           f"overlay={'pen_smooth_min_step' in src_ov} canvas={'pen_smooth_min_step' in src_cv}")

    # AD5 行为级：密集微抖点被真实丢弃（1px 步进只保留间隔>=2的点）
    cv = Canvas(make_image(200, 120), [], None)
    cv._set_tool("pen")
    cv.mousePressEvent(mk_ev(QEvent.Type.MouseButtonPress, QPoint(20, 20)))
    for dx in range(1, 11):  # 每步只移动 1px
        cv.mouseMoveEvent(mk_ev(QEvent.Type.MouseMove, QPoint(20 + dx, 20)))
    cv.mouseReleaseEvent(mk_ev(QEvent.Type.MouseButtonRelease, QPoint(30, 20)))
    stored = cv.shapes[0].points if cv.shapes else []
    # 起点 + 每隔 2px 一个 ≈ 6 个点，而非 11 个
    ok_ad5 = 4 <= len(stored) <= 7
    record("AD5 1px 微抖采样点被丢弃", ok_ad5,
           f"stored={len(stored)} pts={[ (p.x(),p.y()) for p in stored ]}")
    cv.close()

    # AD6 画笔箭头仍可用（平滑没有破坏端点切线/箭头）
    base = make_image(200, 120)
    pts = [QPointF(30, 60), QPointF(80, 40), QPointF(160, 60)]
    plain = Canvas(base, [__import__("snapeditor").Shape(
        kind="pen", points=[QPoint(int(p.x()), int(p.y())) for p in pts],
        color=QColor(255, 0, 0), width=3)], None).compose()
    arrow = Canvas(base, [__import__("snapeditor").Shape(
        kind="pen", points=[QPoint(int(p.x()), int(p.y())) for p in pts],
        color=QColor(255, 0, 0), width=3, pen_arrow_end=True)], None).compose()
    diff = 0
    for yy in range(35, 85):
        for xx in range(140, 180):
            if plain.pixelColor(xx, yy) != arrow.pixelColor(xx, yy):
                diff += 1
    record("AD6 平滑后画笔端点箭头仍正常", diff > 20, f"箭头差异像素={diff}")

    # AD7 README 同步到 v32
    readme = Path("README.md").read_text(encoding="utf-8")
    ok_ad7 = "v32" in readme and "平滑" in readme and "锯齿" in readme
    record("AD7 README 同步 v32 画笔平滑", ok_ad7,
           f"v32={'v32' in readme} smooth={'平滑' in readme}")


# ---------------------------------------------------------------------------
def test_v33_pen_smooth_levels() -> None:
    print("\n--- Stage AE: v33 画笔平滑档位可调 ---")
    import inspect
    import os
    import random
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF

    import hotkeys
    import snapeditor
    from snapeditor import (
        PEN_SMOOTH_LEVELS, PEN_SMOOTH_DEFAULT,
        get_pen_smooth, set_pen_smooth, pen_smooth_min_step,
        _smooth_polyline,
    )

    # AE1 四档齐全，默认中等
    ok_ae1 = (
        tuple(PEN_SMOOTH_LEVELS) == ("off", "low", "medium", "high")
        and PEN_SMOOTH_DEFAULT == "medium"
        and hotkeys.PEN_SMOOTH_LEVELS == PEN_SMOOTH_LEVELS
    )
    record("AE1 四档齐全且两模块档位一致，默认中等", ok_ae1,
           f"levels={PEN_SMOOTH_LEVELS} default={PEN_SMOOTH_DEFAULT}")

    # AE2 非法档位回退默认，且不崩溃
    before = get_pen_smooth()
    ok_ae2 = set_pen_smooth("bogus") is False and get_pen_smooth() == PEN_SMOOTH_DEFAULT
    set_pen_smooth(before)   # 还原，避免影响后续测试
    record("AE2 非法档位回退默认", ok_ae2, f"now={get_pen_smooth()}")

    # AE3 采集端最小间距随档位：关闭=1（不丢点），其它=2
    set_pen_smooth("off")
    step_off = pen_smooth_min_step()
    set_pen_smooth("high")
    step_high = pen_smooth_min_step()
    set_pen_smooth(PEN_SMOOTH_DEFAULT)
    ok_ae3 = step_off == 1 and step_high == 2
    record("AE3 关闭档不丢采样点，其它档去抖", ok_ae3,
           f"off={step_off} high={step_high}")

    # AE4 行为级：四档平滑强度递增（曲率单调下降）
    random.seed(7)
    pts = [QPointF(0, 100)]
    x = 0
    for _ in range(30):
        x += 3
        pts.append(QPointF(x, 100 + random.choice([-2, -1, -1, 0, 0, 0, 1, 1, 2])))

    def curvature(seq):
        return sum(abs(seq[i + 1].y() - 2 * seq[i].y() + seq[i - 1].y())
                   for i in range(1, len(seq) - 1))

    curv = {}
    for lv, radius in (("off", 0), ("low", 0), ("medium", 1), ("high", 2)):
        if lv == "off":
            seq = [QPointF(p) for p in pts]           # 原始折线
        else:
            path = _smooth_polyline(pts[0], pts[1:-1], pts[-1], radius=radius)
            seq = [path.pointAtPercent(i / 90) for i in range(91)]
        curv[lv] = curvature(seq)
    ok_ae4 = (
        curv["off"] > curv["low"] > curv["medium"] > curv["high"]
        and curv["medium"] < curv["low"] * 0.6   # 默认明显比旧版(low)平滑
    )
    record("AE4 四档曲率递减，默认比旧版明显更平滑", ok_ae4,
           f"off={curv['off']:.1f} low={curv['low']:.1f} "
           f"med={curv['medium']:.1f} high={curv['high']:.1f}")

    # AE5 持久化往返（临时配置目录，不污染真实配置）
    with tempfile.TemporaryDirectory() as td:
        os.environ["SNAPTOOL_HOME"] = td
        try:
            defaults = hotkeys.load_pen_smooth()
            roundtrip = {}
            for lv in PEN_SMOOTH_LEVELS:
                hotkeys.save_pen_smooth(lv)
                roundtrip[lv] = hotkeys.load_pen_smooth()
            # 损坏值回退
            (Path(td) / "settings.json").write_text(
                '{"pen_smooth":"garbage"}', encoding="utf-8")
            fallback = hotkeys.load_pen_smooth()
        finally:
            os.environ.pop("SNAPTOOL_HOME", None)
    ok_ae5 = (
        defaults == PEN_SMOOTH_DEFAULT
        and all(roundtrip[lv] == lv for lv in PEN_SMOOTH_LEVELS)
        and fallback == PEN_SMOOTH_DEFAULT
    )
    record("AE5 平滑档位持久化往返与损坏回退", ok_ae5,
           f"defaults={defaults} roundtrip={roundtrip} fallback={fallback}")

    # AE6 菜单接线：主窗口有子菜单、四档 action、点击发信号
    from snapui import MainWindow, make_icon, PEN_SMOOTH_LABELS
    mw = MainWindow(make_icon(), __import__("hotkeys").Hotkey(),
                    "rect", Path("."), "medium")
    fired = []
    mw.pen_smooth_changed.connect(lambda lv: fired.append(lv))
    ok_ae6a = (
        "pen_smooth" in mw._menus
        and set(mw._pen_smooth_actions) == set(PEN_SMOOTH_LEVELS)
        and mw._pen_smooth_actions["medium"].isChecked()
    )
    mw._on_pen_smooth("high")
    ok_ae6b = fired == ["high"] and mw._pen_smooth == "high"
    record("AE6 设置菜单四档勾选与信号", ok_ae6a and ok_ae6b,
           f"menu={ok_ae6a} signal={fired}")
    mw.close()

    # AE7 App 启动时读取配置并应用；菜单改动即时生效
    import snap as snapmod
    ok_ae7 = (
        "set_pen_smooth(self.pen_smooth)" in inspect.getsource(snapmod.App.__init__)
        and "pen_smooth_changed.connect(self._on_pen_smooth_changed)"
        in inspect.getsource(snapmod.App.__init__)
        and "save_pen_smooth(level)" in inspect.getsource(snapmod.App._on_pen_smooth_changed)
    )
    record("AE7 App 启动应用+菜单改动持久化的接线", ok_ae7,
           f"apply={'set_pen_smooth(self.pen_smooth)' in inspect.getsource(snapmod.App.__init__)}")

    # AE8 i18n：新增文案 8 语言齐全，占位符一致
    from i18n_data import _ROWS, LANGS
    need_keys = ("画笔平滑度", "关闭（原始线条）", "轻度", "中等", "强",
                 "画笔平滑度已设为：{level}")
    bad = []
    for k in need_keys:
        row = _ROWS.get(k)
        if not row or len(row) != len(LANGS) or any(not s for s in row):
            bad.append(k)
    row = _ROWS.get("画笔平滑度已设为：{level}", ())
    if any("{level}" not in s for s in row):
        bad.append("占位符{level}")
    record("AE8 平滑度相关文案 8 语言齐全且占位符一致", not bad, f"bad={bad}")

    # AE9 README 同步到 v33
    readme = Path("README.md").read_text(encoding="utf-8")
    ok_ae9 = "v33" in readme and "平滑度" in readme and "档" in readme
    record("AE9 README 同步 v33 可调平滑度", ok_ae9,
           f"v33={'v33' in readme} level={'平滑度' in readme}")


# ---------------------------------------------------------------------------
def test_v34_pin_to_desktop() -> None:
    print("\n--- Stage AF: v34 贴图钉在桌面 ---")
    import os
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QImage, QColor

    from pinwindow import PinWindow, MIN_SCALE, MAX_SCALE, OPACITY_STEPS
    from snapeditor import Overlay, Toolbar
    import hotkeys

    img = make_image(400, 300)

    # AF1 PinWindow 基本属性：尺寸、缩放、透明度、置顶、关闭信号
    pin = PinWindow(img)
    ok_af1a = (pin.width() >= 400 and pin.height() >= 300 and pin.scale == 1.0
               and pin.opacity_pct == 100 and pin.always_on_top is True)
    closed = []
    pin.closed.connect(lambda: closed.append(1))
    pin.zoom(1)
    zin = pin.scale
    pin.zoom(-1)
    zout = pin.scale
    pin.set_opacity(50)
    op50 = pin.opacity_pct
    pin.set_always_on_top(False)
    top_off = pin.always_on_top
    pin.close()
    ok_af1b = (zin > 1.0 and abs(zout - 1.0) < 1e-6 and op50 == 50
               and top_off is False and closed == [1])
    record("AF1 浮窗属性/缩放/透明度/置顶/关闭信号", ok_af1a and ok_af1b,
           f"zin={zin:.2f} zout={zout:.2f} op={op50} top={top_off} closed={closed}")

    # AF2 缩放钳制在 [MIN_SCALE, MAX_SCALE]
    pin2 = PinWindow(img)
    pin2.set_scale(9999)
    hi = pin2.scale
    pin2.set_scale(0.0001)
    lo = pin2.scale
    pin2.close()
    record("AF2 缩放上下限钳制", abs(hi - MAX_SCALE) < 1e-6 and abs(lo - MIN_SCALE) < 1e-6,
           f"hi={hi} lo={lo} range=[{MIN_SCALE},{MAX_SCALE}]")

    # AF3 透明度档位齐全且 set_opacity 钳制
    pin3 = PinWindow(img)
    applied = [pin3.set_opacity(p) for p in OPACITY_STEPS]
    clamped_hi = pin3.set_opacity(500)
    clamped_lo = pin3.set_opacity(-5)
    pin3.close()
    ok_af3 = (applied == list(OPACITY_STEPS) and clamped_hi == 100 and clamped_lo == 5)
    record("AF3 透明度档位与钳制", ok_af3,
           f"applied={applied} clamp=({clamped_hi},{clamped_lo})")

    # AF4 拖动移动改窗口位置
    pin4 = PinWindow(img)
    pin4.move(100, 100)
    before = pin4.pos()
    from PySide6.QtGui import QMouseEvent
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPoint(20, 20), QPoint(20, 20),
                        QPoint(120, 120), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    pin4.mousePressEvent(press)
    move = QMouseEvent(QEvent.Type.MouseMove, QPoint(60, 50), QPoint(60, 50),
                       QPoint(160, 150), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    pin4.mouseMoveEvent(move)
    after = pin4.pos()
    pin4.close()
    ok_af4 = after.x() == before.x() + 40 and after.y() == before.y() + 30
    record("AF4 左键拖动移动浮窗", ok_af4,
           f"before=({before.x()},{before.y()}) after=({after.x()},{after.y()})")

    # AF5 右键菜单含全部动作
    pin5 = PinWindow(img)
    menu = pin5._build_menu()
    texts = [a.text() for a in menu.actions()]
    submenus = [a.menu() for a in menu.actions() if a.menu() is not None]
    op_texts = [a.text() for a in submenus[0].actions()] if submenus else []
    pin5.close()
    ok_af5 = (
        any("复制" in x for x in texts)
        and any("另存" in x for x in texts)
        and any("置顶" in x for x in texts)
        and any("重置" in x for x in texts)
        and any("关闭" in x for x in texts)
        and op_texts == [f"{p}%" for p in OPACITY_STEPS]
    )
    record("AF5 右键菜单动作齐全", ok_af5,
           f"actions={texts} op={op_texts}")

    # AF6 工具条/遮罩：确认阶段有「钉在桌面」按钮，且连接 pin_requested
    tb = Toolbar(None, exclude=("顺旋", "逆旋", "左右", "上下"))
    tb.set_confirm_mode(True)
    pin_btn = tb._actions.get("钉在桌面")
    # 父工具条未 show，isVisible() 恒 False；用 isHidden() 判断显式显隐
    ok_af6a = pin_btn is not None and not pin_btn.isHidden()
    # 编辑器工具条从不调用 set_confirm_mode，钉按钮默认显示
    from snap_editor import Canvas as _Canvas
    ed_tb = _Canvas(make_image(20, 20), [], None).toolbar
    ed_pin = ed_tb._actions.get("钉在桌面")
    ok_af6b = ed_pin is not None and not ed_pin.isHidden()
    ov = Overlay(img, 1.0)
    ok_af6c = hasattr(ov, "pin_requested") and "钉在桌面" in tb._tip_keys.get("action:钉在桌面", "钉在桌面")
    # 行为级：模拟选区后点钉按钮 → 发 pin_requested
    ov.resize(600, 500)
    ov.sel = __import__("PySide6").QtCore.QRect(50, 50, 200, 150)
    fired = []
    ov.pin_requested.connect(lambda q: fired.append((q.width(), q.height())))
    ov._pin_only()
    ok_af6d = len(fired) == 1 and fired[0] == (200, 150)
    record("AF6 工具条/遮罩钉在桌面按钮与信号",
           ok_af6a and ok_af6b and ok_af6c and ok_af6d,
           f"btn={ok_af6a}/{ok_af6b} sig={ok_af6c} fired={fired}")

    # AF7 编辑器：Canvas/EditorWindow 有 pin_requested 且菜单项存在
    from snap_editor import Canvas, EditorWindow
    cv = Canvas(img, [], None)
    ok_af7a = hasattr(cv, "pin_requested")
    ew = EditorWindow(img, [], Path("."))
    ok_af7b = hasattr(ew, "pin_requested") and "钉在桌面" in ew._FILE_TEXTS
    ew.close()
    record("AF7 编辑器钉在桌面接线", ok_af7a and ok_af7b,
           f"canvas={ok_af7a} editor={ok_af7b}")

    # AF8 贴图热键持久化往返 + 默认值
    with tempfile.TemporaryDirectory() as td:
        os.environ["SNAPTOOL_HOME"] = td
        try:
            default_pin = hotkeys.load_pin_hotkey()
            hk = hotkeys.Hotkey(hotkeys.MOD_CONTROL | hotkeys.MOD_ALT, 0x50)
            saved = hotkeys.save_pin_hotkey(hk)
            loaded = hotkeys.load_pin_hotkey()
            (Path(td) / "settings.json").write_text(
                '{"pin_hotkey":{"mods":999,"vk":0}}', encoding="utf-8")
            fallback = hotkeys.load_pin_hotkey()
        finally:
            os.environ.pop("SNAPTOOL_HOME", None)
    ok_af8 = (
        default_pin.vk == 0x50 and default_pin.mods == (hotkeys.MOD_CONTROL | hotkeys.MOD_SHIFT)
        and saved is True and loaded == hk and fallback.vk == 0x50
    )
    record("AF8 贴图热键默认/持久化/非法回退", ok_af8,
           f"default={default_pin.label()} roundtrip={loaded.label()} fallback={fallback.label()}")

    # AF9 App 四入口接线（源码级）+ PinWindow 列表管理
    import inspect
    import snap as snapmod
    src_init = inspect.getsource(snapmod.App.__init__)
    src_begin = inspect.getsource(snapmod.App._begin_capture)
    src_open_ed = inspect.getsource(snapmod.App._open_editor)
    ok_af9a = (
        "pin_hotkey" in src_init
        and "self.pins" in src_init
        and "self.overlay.pin_requested.connect(self._on_pin_requested)" in src_begin
        and "editor.pin_requested.connect(self._on_editor_pin)" in src_open_ed
        and "pin_clipboard" in src_init
    )
    # 行为级：_pin_image 建浮窗并加入列表，关闭后从列表移除
    #   用 __new__ 避免完整构造（注册全局热键 / 显示窗口 / 单实例锁干扰）
    q = snapmod.App.__new__(snapmod.App)
    q.app = QApplication.instance()
    q.pins = []
    before_n = len(q.pins)
    pinx = q._pin_image(make_image(50, 40))
    after_n = len(q.pins)
    pinx.close()
    q.app.processEvents()
    after_close = len(q.pins)
    ok_af9b = before_n == 0 and after_n == 1 and after_close == 0
    record("AF9 App 四入口接线与浮窗列表管理", ok_af9a and ok_af9b,
           f"wiring={ok_af9a} list={before_n}->{after_n}->{after_close}")

    # AF10 i18n：新文案 8 语言齐全且占位符一致
    from i18n_data import _ROWS, LANGS
    need_keys = (
        "钉在桌面", "贴图", "贴出剪贴板图片", "设置贴图热键…", "设置贴图热键 - {app}",
        "贴图热键已改为 {label}", "已把截图钉在桌面  {w}×{h}",
        "已把剪贴板图片钉在桌面  {w}×{h}", "剪贴板里没有图片，无法贴图。",
        "复制图片", "另存为…", "透明度", "保持置顶", "重置大小", "关闭贴图",
        "贴图用法", "贴图操作",
    )
    bad = []
    for k in need_keys:
        row = _ROWS.get(k)
        if not row or len(row) != len(LANGS) or any(not s for s in row):
            bad.append(k)
    for k, ph in (("设置贴图热键 - {app}", "{app}"),
                  ("贴图热键已改为 {label}", "{label}"),
                  ("已把截图钉在桌面  {w}×{h}", "{w}")):
        if any(ph not in s for s in _ROWS.get(k, ())):
            bad.append(k + ph)
    record("AF10 贴图相关文案 8 语言齐全且占位符一致", not bad, f"bad={bad}")

    # AF11 README 同步 v34
    readme = Path("README.md").read_text(encoding="utf-8")
    ok_af11 = "v34" in readme and "贴图钉在桌面" in readme
    record("AF11 README 同步 v34 贴图钉在桌面", ok_af11,
           f"v34={'v34' in readme} pin={'贴图钉在桌面' in readme}")


def test_v35_window_capture_accuracy() -> None:
    print("\n--- Stage AG: v35 窗口截图准确性修复 ---")
    import inspect
    from pathlib import Path

    from PySide6.QtCore import QEvent, QPoint, QPointF, QRect
    from PySide6.QtGui import QImage, QMouseEvent
    from PIL import Image

    import snapback as sb
    import snap as snapmod
    from snapeditor import Overlay

    base = make_image(320, 240)

    # AG1 类名黑名单：正常窗口放行，菜单/提示/任务栏/桌面/输入法一律拒绝
    deny_exact = [
        sb.is_pickable_window_class(c)
        for c in ("#32768", "tooltips_class32", "Shell_TrayWnd",
                  "Progman", "WorkerW")
    ]
    deny_sub = [
        sb.is_pickable_window_class(c)
        for c in ("IMEUI", "SogouIME", "CandidateList", "输入法窗口")
    ]
    ok_ag1 = (
        sb.is_pickable_window_class("Chrome_WidgetWin_1")
        and sb.is_pickable_window_class("")
        and not any(deny_exact) and not any(deny_sub)
    )
    record("AG1 窗口类名黑名单过滤", ok_ag1,
           f"allow={sb.is_pickable_window_class('Chrome_WidgetWin_1')} "
           f"deny_exact={deny_exact} deny_sub={deny_sub}")

    # AG2 Z 序优先：最前面的大窗口胜过被点中的小窗口（旧逻辑会选小的）
    big_top = sb.WindowInfo(sb.ScreenRect(0, 0, 1000, 800), "Top", 1, z=0)
    small_bottom = sb.WindowInfo(sb.ScreenRect(100, 100, 200, 200), "Bottom", 2, z=5)
    picked = sb.pick_top_window([big_top, small_bottom])
    ok_ag2 = picked is big_top and sb.pick_top_window([]) is None
    record("AG2 窗口选择改为 Z 序优先（不再取最小面积）", ok_ag2,
           f"picked={picked.title if picked else None}")

    # AG3 WindowInfo.dpr：DPI → 缩放比
    ok_ag3 = (
        abs(sb.WindowInfo(sb.ScreenRect(0, 0, 1, 1), "", 0, dpi=96).dpr - 1.0) < 1e-9
        and abs(sb.WindowInfo(sb.ScreenRect(0, 0, 1, 1), "", 0, dpi=144).dpr - 1.5) < 1e-9
        and abs(sb.WindowInfo(sb.ScreenRect(0, 0, 1, 1), "", 0, dpi=0).dpr - 1.0) < 1e-9
    )
    record("AG3 WindowInfo.dpr 换算（含损坏回退）", ok_ag3, "96->1.0 144->1.5 0->1.0")

    # AG4 Win32 辅助函数在无有效句柄 / 无显示器信息时安全降级
    ok_ag4 = (
        sb.foreground_window(0) is False
        and isinstance(sb.monitor_physical_rects(), list)
    )
    record("AG4 foreground_window / 显示器枚举安全降级", ok_ag4,
           f"fg0={sb.foreground_window(0)} monitors={sb.monitor_physical_rects()}")

    # AG5 混合 DPI 纯换算：主屏 150%、副屏物理原点偏移、无显示器信息回退
    mons = [sb.ScreenRect(0, 0, 1920, 1080), sb.ScreenRect(1920, 0, 1024, 768)]
    p_main = snapmod.physical_from_screen(QPoint(100, 50), QRect(0, 0, 1280, 720),
                                          1.5, mons, 1.0)
    p_second = snapmod.physical_from_screen(QPoint(1300, 100), QRect(1280, 0, 683, 384),
                                            1.5, mons, 1.0)
    p_fallback = snapmod.physical_from_screen(QPoint(100, 50), QRect(0, 0, 800, 800),
                                              2.0, [], 1.0)
    ok_ag5 = p_main == (150, 75) and p_second == (1950, 150) and p_fallback == (200, 100)
    record("AG5 混合 DPI 物理坐标换算", ok_ag5,
           f"main={p_main} second={p_second} fallback={p_fallback}")

    # AG6 _pick_window 附带 hwnd，并走新的坐标换算
    holder = snapmod.App.__new__(snapmod.App)
    ov_pick = Overlay(base, dpr=1.0)
    ov_pick.resize(400, 200)
    ov_pick.move(-100, -20)
    holder.overlay = ov_pick
    orig_win = sb.window_rect_at
    sb.window_rect_at = lambda x, y: sb.WindowInfo(
        sb.ScreenRect(0, 0, 400, 300), "T", 777, sb.ScreenRect(10, 30, 380, 260)
    )
    try:
        picked = holder._pick_window(QPoint(50, 50))
    finally:
        sb.window_rect_at = orig_win
    src_pick = inspect.getsource(snapmod.App._pick_window)
    ok_ag6 = (
        picked is not None and len(picked) == 3 and picked[2] == 777
        and "global_logical_to_physical" in src_pick
    )
    record("AG6 _pick_window 返回 hwnd 且用新坐标换算", ok_ag6,
           f"len={len(picked) if picked else 0} hwnd={picked[2] if picked else None}")

    # AG7 update_base 原子替换底图与预生成图；空图拒绝
    ov_base = Overlay(base, dpr=2.0)
    fresh = make_image(80, 60)
    changed = ov_base.update_base(fresh)
    ok_ag7 = (
        changed is True and ov_base.base is fresh
        and ov_base.base_logical.width() == 40 and ov_base.base_logical.height() == 30
        and ov_base.dim_logical.width() == 40
        and ov_base.update_base(QImage()) is False
    )
    record("AG7 Overlay.update_base 原子替换底图", ok_ag7,
           f"changed={changed} logical={ov_base.base_logical.width()}x{ov_base.base_logical.height()}")

    # AG8 重抓回调：正常调用 + 未设置回调 + 异常降级（保留旧底图）
    fired: list[int] = []
    ov_rg = Overlay(base, dpr=1.0)
    ov_rg.set_window_regrab(lambda h: fired.append(h) or make_image(60, 40))
    ok_rg1 = ov_rg._regrab_for_window(999) is True and fired == [999] and ov_rg.base.width() == 60
    ov_no = Overlay(base, dpr=1.0)
    ok_rg2 = ov_no._regrab_for_window(1) is False
    ov_err = Overlay(base, dpr=1.0)

    def _boom(_h):
        raise RuntimeError("grab failed")
    ov_err.set_window_regrab(_boom)
    ok_rg3 = ov_err._regrab_for_window(1) is False and ov_err.base is base
    record("AG8 重抓回调调用与异常降级", ok_rg1 and ok_rg2 and ok_rg3,
           f"fired={fired} no_cb={ok_rg2} fallback={ok_rg3}")

    # AG9 _update_hover 保存 hwnd（新 3 元组 + 旧 2 元组兼容）
    ov_hover = Overlay(base, dpr=1.0)
    ov_hover.resize(300, 200)
    ov_hover.set_capture_mode("window", lambda p: (QRect(10, 10, 100, 80), "Title", 321))
    ov_hover._update_hover(QPoint(50, 50), force=True)
    ok_h1 = ov_hover._hover_hwnd == 321 and ov_hover._hover_rect == QRect(10, 10, 100, 80)
    ov_hover._window_picker = lambda p: (QRect(20, 20, 50, 50), "Old")
    ov_hover._update_hover(QPoint(30, 30), force=True)
    ok_h2 = ov_hover._hover_hwnd == 0 and ov_hover._hover_rect == QRect(20, 20, 50, 50)
    record("AG9 _update_hover 记录 hwnd 且兼容旧签名", ok_h1 and ok_h2,
           f"new={ov_hover._hover_hwnd} legacy_ok={ok_h2}")

    # AG10 行为级：picking 点击 → 先重抓底图 → 再进入确认态
    ov_click = Overlay(base, dpr=1.0)
    ov_click.resize(400, 300)
    ov_click.set_capture_mode("window", lambda p: (QRect(20, 20, 200, 150), "W", 555))
    click_fired: list[int] = []
    ov_click.set_window_regrab(lambda h: click_fired.append(h) or make_image(120, 90))
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(50, 50),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    ov_click.mousePressEvent(ev)
    ok_ag10 = (
        click_fired == [555] and ov_click._mode == "editing"
        and ov_click.base.width() == 120
    )
    record("AG10 点击窗口先重抓再确认（所见即所得）", ok_ag10,
           f"fired={click_fired} mode={ov_click._mode} base_w={ov_click.base.width()}")

    # AG11 App._regrab_window_base 端到端（mock 抓屏 / 前置 / 遮罩）
    q = snapmod.App.__new__(snapmod.App)
    q.app = QApplication.instance()

    class _FakeOverlay:
        def __init__(self):
            self.visible = True
            self.calls: list[str] = []

        def isVisible(self):
            return self.visible

        def hide(self):
            self.visible = False
            self.calls.append("hide")

        def show(self):
            self.visible = True
            self.calls.append("show")

        def raise_(self):
            self.calls.append("raise")

        def activateWindow(self):
            self.calls.append("activate")

    fake_ov = _FakeOverlay()
    q.overlay = fake_ov
    orig_grab, orig_fg = sb.grab_all_screens, sb.foreground_window
    fg_calls: list[int] = []
    sb.grab_all_screens = lambda: Image.new("RGB", (33, 22), (10, 20, 30))
    sb.foreground_window = lambda h: fg_calls.append(h) or True
    try:
        grabbed = q._regrab_window_base(888)
    finally:
        sb.grab_all_screens, sb.foreground_window = orig_grab, orig_fg
    ok_ag11 = (
        grabbed is not None and grabbed.width() == 33
        and fg_calls == [888]
        and fake_ov.calls == ["hide", "show", "raise", "activate"]
        and fake_ov.visible is True
    )
    record("AG11 App 重抓流程：前置/隐藏/抓屏/恢复", ok_ag11,
           f"size={grabbed.width()}x{grabbed.height()} fg={fg_calls} calls={fake_ov.calls}")

    # AG12 各入口接线（静态源码检查，防回归）
    src_begin = inspect.getsource(snapmod.App._begin_capture)
    src_mouse = inspect.getsource(Overlay.mousePressEvent)
    src_key = inspect.getsource(Overlay.keyPressEvent)
    ok_ag12 = (
        "set_window_regrab(self._regrab_window_base)" in src_begin
        and "_regrab_for_window(self._hover_hwnd)" in src_mouse
        and "_regrab_for_window(self._hover_hwnd)" in src_key
    )
    record("AG12 重抓回调四处接线", ok_ag12,
           f"begin={'set_window_regrab' in src_begin} "
           f"mouse={'_regrab_for_window' in src_mouse} key={'_regrab_for_window' in src_key}")

    # AG13 长截图不走重抓（它自行逐帧抓图）
    ov_long = Overlay(base, dpr=1.0)
    ov_long.set_long_mode(True, lambda p: QRect(0, 0, 10, 10))
    record("AG13 长截图模式不启用重抓", ov_long._window_regrab is None,
           f"regrab={ov_long._window_regrab}")

    # AG14 README 同步 v35
    readme = Path("README.md").read_text(encoding="utf-8")
    ok_ag14 = "v35" in readme and "窗口截图" in readme
    record("AG14 README 同步 v35 窗口截图修复", ok_ag14,
           f"v35={'v35' in readme} window={'窗口截图' in readme}")


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
    test_mosaic_style_panel()
    test_v19_features()
    test_v20_long_capture_quality()
    test_v21_shape_corner_resize()
    test_v22_shape_rotation()
    test_v23_text_background()
    test_v24_text_input_position()
    test_v25_bundle_size()
    test_v26_copy_button()
    test_v27_copy_closes_windows()
    test_v28_warmup_and_input_gate()
    test_v31_sticky_tools_and_single_instance()
    test_v32_pen_smoothing()
    test_v33_pen_smooth_levels()
    test_v34_pin_to_desktop()
    test_v35_window_capture_accuracy()

    print("=" * 66)
    failed = [n for n, s, _ in results if s == FAIL]
    print(f"合计 {len(results)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项：" + "、".join(failed))
    sys.exit(1 if failed else 0)
