# -*- coding: utf-8 -*-
"""
snapui.py —— 程序主窗口、帮助说明、关于对话框、托盘图标。

只依赖 PySide6 与 hotkeys，不反向 import snap.py / snapeditor.py，
因此可单独离屏实例化做自检。主窗口只发信号，具体流程由 App 编排。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from hotkeys import CAPTURE_MODES, Hotkey, mode_label
from i18n import LANG, app_name, language_choices, language_label, t
from i18n_docs import about_html, cli_help, cli_help_html, help_html

# 常量保留简体中文：配置目录名、exe 名、自检与旧版脚本都依赖它，
# 界面上显示的程序名统一用随语言变化的 app_name()。
APP_NAME = "截屏助手"
CONTACT_EMAIL = "283096251@qq.com"

# 随程序分发的资源：源码运行时在 snapui.py 同目录，PyInstaller 打包后在 _MEIPASS。
# SnapTool.spec 的 datas 里必须同步列出这两个文件，否则绿色版会缺图标 / 头像。
APP_ICON_FILE = "app.ico"
AVATAR_FILE = "assets/avatar-pan.webp"
ABOUT_AVATAR_HEIGHT = 260

MODE_DESC = {
    "rect": "拖动鼠标框选任意区域",
    "window": "移动鼠标点选一个窗口",
    "fullscreen": "整个屏幕（含多显示器）",
}


def resource_path(name: str) -> Path:
    """返回随程序分发的资源路径（源码目录 / PyInstaller 的 _MEIPASS）。"""
    base = getattr(sys, "_MEIPASS", None) or str(Path(__file__).resolve().parent)
    return Path(base) / name


def make_icon() -> QIcon:
    """优先用随程序分发的 app.ico（多尺寸，窗口 / 托盘 / exe 一致）。

    资源缺失时退回代码画的相机图标，保证源码单独拷走某个 .py 也能跑起来。
    """
    ico = resource_path(APP_ICON_FILE)
    if ico.is_file():
        icon = QIcon(str(ico))
        if not icon.isNull():
            return icon
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(10, 132, 255))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(6, 12, 52, 40, 8, 8)
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(20, 22, 24, 20)
    p.setBrush(QColor(10, 132, 255))
    p.drawEllipse(28, 28, 8, 8)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------------------
# 帮助内容
# ---------------------------------------------------------------------------
HELP_HTML = """
<html><head><style>
body { font-family: 'Microsoft YaHei', sans-serif; font-size: 13px; color:#1f2937; }
h2 { color:#0a6ed1; font-size:16px; margin:16px 0 6px 0; }
p, li { line-height:1.6; }
table { border-collapse:collapse; width:100%; margin:6px 0; }
td, th { border:1px solid #d1d5db; padding:5px 8px; text-align:left; }
th { background:#f3f4f6; }
code { background:#f3f4f6; padding:1px 4px; }
.hint { color:#6b7280; }
</style></head><body>

<h2>1. 启动与常驻</h2>
<p>双击 <code>run-silent.bat</code> 启动后会显示本主窗口，同时右下角托盘出现图标。
<b>关闭主窗口只会最小化到托盘，程序不会退出</b>；要彻底退出请点「文件 → 退出」或托盘右键「退出」。
托盘右键「显示主窗口」可随时把窗口叫回来，左键单击托盘图标则直接截图。</p>

<h2>2. 三种截图模式</h2>
<table>
<tr><th>模式</th><th>怎么操作</th><th>适合场景</th></tr>
<tr><td>框选截图</td><td>按住鼠标左键拖出矩形，松手后可拖选区、拖八个控制点微调</td><td>截局部内容，默认模式</td></tr>
<tr><td>窗口截图</td><td>移动鼠标，目标窗口会高亮并显示标题与尺寸，单击确认；右键或 Esc 取消</td><td>完整截下某个窗口（自动去掉 Win10/11 的透明阴影边框）</td></tr>
<tr><td>全屏截图</td><td>进入时自动选中整个虚拟屏幕，无需拖选</td><td>截整个桌面或多显示器合屏</td></tr>
</table>
<p class="hint">窗口模式会跳过截屏助手自己的窗口；启动截图时本程序的主窗口、帮助窗口、预览窗口都会临时隐藏，避免被拍进图里，结束后自动恢复。
三种模式确定选区后都进入同一个编辑器，标注、取字、复制、保存的用法完全一致。
另有不进编辑器的独立「滚动长截图」命令，见第 9 节。</p>

<h2>3. 全局热键</h2>
<p>默认 <b>Ctrl + Shift + A</b> 唤起截图，使用的模式由主窗口的「默认模式」决定（会记住，重启后仍有效）。
右键托盘或主窗口「设置 → 设置热键…」可改成任意组合：打开后直接按键录制，也可以勾选修饰键 + 选主键。
保存时立即生效，无需重启。</p>
<p class="hint">若提示「无法注册」，说明该组合已被其它程序占用或属于系统保留组合，换一个即可，原设置不受影响。
至少需要 Ctrl / Alt / Shift / Win 中的一个修饰键。热键配置保存在 <code>%APPDATA%\\SnapTool\\settings.json</code>。</p>

<h2>4. 截图后的编辑</h2>
<table>
<tr><th>操作</th><th>说明</th></tr>
<tr><td>框选后调整</td><td>选区内空白处拖动可移动选区；拖八个控制点改变大小</td></tr>
<tr><td>标注工具</td><td>矩形、椭圆、箭头、画笔、马赛克、文字</td></tr>
<tr><td>修改标注</td><td>点选标注后弹出样式面板，可改线条颜色/粗细/线型、文字颜色/字号/加粗/背景色与背景透明度/背景边框、填充色、画笔端点箭头；按住标注可拖动；双击文字可改内容。<b>马赛克除外</b>：它没有可调样式，不弹样式面板</td></tr>
<tr><td>透明线条 / 填充透明度</td><td>线条颜色里的「<b>∅ 透明</b>」色块可画出无边框 / 无线条的图形（文字标注不提供该选项）；封闭图形（矩形 / 椭圆）启用填充后，可用「<b>填充透明度</b>」滑块调 0~100% 不透明度</td></tr>
<tr><td>文字背景透明度</td><td>选中文字后启用「<b>文字背景色</b>」，下面多出「<b>背景透明度</b>」滑块（0~100%），操作方式与封闭图形的「填充透明度」一样，但两者的颜色和透明度<b>各自独立记忆</b>，改一个不影响另一个</td></tr>
<tr><td>文字背景边框</td><td>选中文字后勾选「<b>启用边框</b>」，可给文字的圆角背景框描边：<b>边框颜色</b>可选预设色或「<b>∅ 透明</b>」（透明等于不描边），并有独立的<b>边框线宽</b>与<b>边框线型</b>（实线 / 虚线 / 点线）。背景与边框可分别开关，边框也能单独显示而不填背景；旋转文字时背景框与边框一起转，Ctrl+Z 可恢复</td></tr>
<tr><td>视图放缩</td><td><b>Ctrl + 滚轮</b>以光标为锚点放大 / 缩小，或菜单「视图(&V)」：放大（Ctrl+=）、缩小（Ctrl+-）、实际大小 1:1（Ctrl+1）、适应窗口（Ctrl+0）；放大后<b>按住鼠标中键拖动</b>可平移画布。状态栏显示当前比例，导出始终是原图全分辨率</td></tr>
<tr><td>箭头</td><td>两端有圆形控制柄，拖动可改长度与方向（可拖过另一端反向）</td></tr>
<tr><td>矩形 / 椭圆四角</td><td>选中后外接矩形的<b>四个角</b>出现圆形控制柄，拖动任一角即可改变宽高与形状：对角保持固定、可拖过对角翻转、宽高有最小值保护；截图遮罩与程序窗口编辑器都可用，画布放缩后手柄大小与命中范围不变。马赛克、画笔等其它标注仍只可整体拖动或拉伸端点</td></tr>
<tr><td>形状旋转</td><td>选中<b>矩形 / 椭圆 / 文字</b>后，上方会出现一个圆形<b>旋转柄</b>：拖动它即可绕形状中心任意旋转，按住 <b>Shift</b> 吸附到 15° 整数倍；样式面板里的「<b>旋转角度</b>」滑块可精确设定 -180°~180°。菜单「编辑 → 旋转选中形状」提供 90° 步进（Ctrl+[ / Ctrl+]）。旋转后四角控制柄、选中虚线框与点选命中都会跟着转；截图遮罩与程序窗口编辑器都支持。马赛克、箭头 / 直线、画笔保持原样</td></tr>
<tr><td>整图旋转 / 镜像</td><td>程序窗口工具条右侧一组按钮：顺旋（顺时针 90° Ctrl+R）、逆旋（逆时针 90° Ctrl+Shift+R）、左右（镜像 Ctrl+H）、上下（镜像 Ctrl+Shift+H）；底图与已有标注一起变，<b>文字标注的字形也跟着旋转</b>（不再保持水平）；镜像时文字仍可读、不做反字。Ctrl+Z 可撤销，角度一并恢复</td></tr>
<tr><td>画笔端点箭头</td><td>菜单「编辑 → 样式面板」打开面板，勾选「起点加箭头 / 终点加箭头」；无选中时设新建画笔默认，选中画笔时改当前线。也可用菜单「编辑 → 画笔端点箭头」</td></tr>
<tr><td>撤销</td><td>Ctrl + Z 或工具条「撤销」（整图变换也能撤销）</td></tr>
<tr><td>复制 / 保存 / 取消</td><td>Enter 或工具条「复制」；工具条「保存」；Esc 或工具条「✕」</td></tr>
<tr><td>滚动长截图</td><td>独立命令，不进入编辑器：主窗口按钮 /「截图(&S) → 滚动长截图…」/ 托盘右键均可启动，详见第 9 节</td></tr>
</table>
<p class="hint">视图放缩只改变屏幕上的显示比例，不会缩放、重采样导出图片；坐标换算、取字行块、文字输入都会跟着比例同步，因此放大后仍能精确标注。马赛克是纯像素化效果，没有颜色、线宽、线型等可调样式：使用马赛克工具或选中马赛克标注时，样式面板都不会弹出。</p>
<p class="hint">旋转 90° 后图片宽高互换，矩形/箭头/画笔/文字等标注位置跟着变换；文字按包围盒中心映射，字形与底图一起旋转（镜像时保持可读，不变成反字）。导出始终是全分辨率。</p>

<h2>5. 取字（OCR）</h2>
<p>在程序窗口里点工具条「取字」或菜单「编辑 → OCR 取字」，识别结果会<b>逐行盖回原文位置</b>：每行文字可选中、拖选、Ctrl+A / Ctrl+C 复制，
也可用窗口顶部取字工具条的「复制选中」「复制全部」。复制后约 0.4 秒自动收起，回到正常编辑态；
点「返回」或按 Esc 只收起取字层，不会关闭窗口。改变窗口大小后行块会重新盖回，不会错位。
识别中按 Esc 取消本次取字；识别中、失败或后端不返回坐标时显示整块结果面板。
取字默认走 RapidOCR（ONNX 模型随程序自带），首次取字需加载模型约 1~5 秒，之后常驻缓存。</p>

<h2>6. 文件与配置</h2>
<p>截图默认保存到 <code>%USERPROFILE%\\Pictures\\Screenshots</code>（主窗口状态栏显示实际路径，托盘「打开保存目录」可直接打开）。
配置在 <code>%APPDATA%\\SnapTool\\settings.json</code>，含热键与默认截图模式；设置环境变量
<code>SNAPTOOL_HOME</code> 可把配置目录改到别处，方便便携版。</p>

<h2>7. 命令行</h2>
<p><code>python snap.py --help</code> 查看全部参数；<code>--shot</code> 启动后立即截一次图；
<code>--restart</code> 结束后台残留实例并重启（等价于双击 <code>restart.bat</code>）。
图形界面里也可以点「帮助 → 命令行参数」。</p>

<h2>8. 常见问题</h2>
<ul>
<li><b>按热键没反应：</b>多半是热键被别的程序占用。托盘会弹注册失败提示，去「设置热键…」换一个组合；也可以直接点主窗口的截图按钮。</li>
<li><b>提示「已经在运行」却看不到程序：</b>托盘图标可能被折叠到通知区（点 ^ 展开）；也可能是旧实例只留下隐藏窗口。重复启动时会先把它唤醒并显示主窗口，弹窗里选「是」即可结束它并重启，或直接双击 restart.bat。</li>
<li><b>改了代码没变化：</b>程序是单实例 + 托盘常驻，旧进程仍在跑旧代码，双击 restart.bat 即可用新代码重启。</li>
<li><b>高分屏坐标不准：</b>程序已开启 per-monitor DPI 感知；若仍偏移，重启程序后再试。</li>
<li><b>杀软误报：</b>全局热键 + 屏幕捕获容易被误报，未签名的 exe 需要加入信任。</li>
</ul>

<h2>9. 滚动长截图</h2>
<p>这是与三种截图模式并列的<b>独立命令</b>，从主窗口按钮区「滚动长截图…」、「截图(&S) → 滚动长截图…」或托盘右键「滚动长截图…」启动。它<b>不进入编辑器、也不需要框选</b>：<b>单击目标窗口即自动向下滚屏</b>。</p>
<ol>
<li>启动后先隐藏本程序所有窗口，再抓一帧底图并显示遮罩；</li>
<li>移动鼠标，目标窗口会高亮并显示标题；<b>单击左键选中窗口</b>，程序取它的客户区（自动排除标题栏与边框）作为滚动区域，<b>立即开始</b>逐帧抓屏、模板匹配拼成长图；</li>
<li>滚动中：<b>左键单击暂停，再单击继续</b>；<b>右键单击结束</b>；点悬浮控制条的「<b>确定 ✓</b>」或按 <b>Esc</b> 也可结束；滚到页面底部会<b>自动结束</b>；</li>
<li>结束后弹出预览窗口，可直接另存为 PNG / JPG。</li>
</ol>
<p class="hint">拼接期间本程序窗口保持隐藏、控制条也会避开窗口区域（窗口占满屏幕时会在抓帧瞬间临时隐藏），避免被拍进长图；结束后自动恢复。若页面含固定悬浮元素或动画导致无法自动对齐，会提示结果可能不完整，可改用普通截图。</p>
<p class="hint"><b>网页不易中途截断</b>：单帧几乎没滚动不会立刻判「到底」，而是连续确认 3 帧；模板匹配失败会减小步长、多等一拍重试 2 次；模板从画面中部取以避开固定顶栏；滚轮步长按上一帧新增行数自适应；每次滚轮前把光标重新锁定到目标窗口，避免鼠标移动后滚错窗口。控制条实时显示帧数、高度与匹配分数，结束时托盘提示会说明共拼了多少帧以及结束原因（到底 / 无法对齐 / 帧数或高度上限 / 手动结束）。</p>
</body></html>
"""

CLI_HELP = f"""{APP_NAME} —— 命令行参数

  python snap.py              正常启动：显示主窗口 + 托盘常驻
  python snap.py --shot       启动后立即截一次图（使用默认截图模式）
  python snap.py --restart    结束后台残留实例并重新启动（不弹确认框）
  python snap.py --selftest   只跑后端自检，不进入界面
                              结果写入 %APPDATA%\\SnapTool\\selftest.log
  python snap.py --help       显示本说明（也可写 -h 或 /?）

日常使用请双击 run-silent.bat（无黑窗口）。程序是单实例，重复启动会先唤醒
已有实例并显示主窗口；若看不到界面，弹窗里选「是」即可结束后台实例并重启，
也可直接双击 restart.bat 一键重启。启动诊断见 %APPDATA%\\SnapTool\\startup.log。

三种截图模式：框选（拖鼠标选区域）、窗口（悬停高亮并单击）、全屏（自动选中整个虚拟屏幕）。
另有独立命令「滚动长截图…」（主窗口 /「截图」菜单 / 托盘右键）：单击目标窗口即自动向下滚屏并拼接成长图，不框选、不进编辑器；滚动中左键暂停 / 继续、右键或「确定 ✓」结束、到底自动结束。
默认模式与全局热键保存在 %APPDATA%\\SnapTool\\settings.json，
可在主窗口或托盘菜单「设置热键…」里修改。

更多说明见程序内「帮助 → 使用说明」，或项目 README.md。
"""

ABOUT_HTML = f"""
<div style="font-family:'Microsoft YaHei',sans-serif; font-size:13px; color:#1f2937; line-height:1.6;">
<p style="font-size:19px; font-weight:bold; margin:0 0 8px 0;">{APP_NAME}</p>
<p>一个自制功能强大的Windows桌面截图软件。</p>
<p>功能：三种截图模式、对象化标注编辑、整图旋转 / 镜像、画笔端点箭头、独立「滚动长截图」命令、中文 OCR 逐行盖回取字、全局热键自定义、8 种界面语言。</p>
<p style="font-size:13px;">联系邮箱：<a href="mailto:{CONTACT_EMAIL}" style="color:#0a6ed1;">{CONTACT_EMAIL}</a></p>
<p style="font-size:12px; color:#6b7280;">技术栈：Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime)。<br>
第三方组件许可：PySide6 (LGPL)、RapidOCR / PaddleOCR / OpenCV (Apache-2.0)、ONNX Runtime (MIT)。</p>
</div>
"""


class AboutDialog(QDialog):
    """「关于」：左侧头像，右侧软件说明与联系邮箱。

    非模态单例（由 App.show_about 复用）：关闭只是隐藏，不销毁；
    作为顶层窗口，截图时会被 _own_top_levels 一并隐藏，不会被拍进图里。
    """

    def __init__(self, parent: QWidget | None = None,
                 icon: QIcon | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("关于 {app}", app=app_name()))
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumWidth(580)
        self.setStyleSheet(
            "QDialog { background:#ffffff; }"
            "QLabel#aboutAvatar { background:#f7f8fa; border:1px solid #e5e7eb;"
            " border-radius:10px; }"
            "QPushButton#aboutOk { background:#0a84ff; color:#fff; border:none;"
            " border-radius:6px; padding:6px 18px; }"
            "QPushButton#aboutOk:hover { background:#0969cc; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(16)

        body = QHBoxLayout()
        body.setSpacing(20)
        avatar = QLabel()
        avatar.setObjectName("aboutAvatar")
        avatar.setAlignment(Qt.AlignCenter)
        pm = QPixmap(str(resource_path(AVATAR_FILE)))
        if not pm.isNull():
            pm = pm.scaledToHeight(ABOUT_AVATAR_HEIGHT, Qt.SmoothTransformation)
            avatar.setPixmap(pm)
            # 四周留白，让透明背景的头像落在浅灰圆角卡片里
            avatar.setFixedSize(pm.width() + 18, pm.height() + 18)
        else:
            avatar.setVisible(False)
        body.addWidget(avatar, 0, Qt.AlignTop)

        self._text = QLabel(about_html(name=app_name()))
        self._text.setObjectName("aboutText")
        self._text.setWordWrap(True)
        self._text.setTextFormat(Qt.RichText)
        self._text.setOpenExternalLinks(True)   # mailto 交给系统默认邮件客户端
        self._text.setAlignment(Qt.AlignTop)
        body.addWidget(self._text, 1)
        root.addLayout(body)

        row = QHBoxLayout()
        row.addStretch(1)
        self._ok = QPushButton(t("确定"))
        self._ok.setObjectName("aboutOk")
        self._ok.clicked.connect(self.hide)
        row.addWidget(self._ok)
        root.addLayout(row)

        LANG.changed.connect(self.retranslate_ui)

    def retranslate_ui(self, _code: str = "") -> None:
        """语言切换后即时刷新标题、正文（含邮箱链接）与按钮。"""
        self.setWindowTitle(t("关于 {app}", app=app_name()))
        self._text.setText(about_html(name=app_name()))
        self._ok.setText(t("确定"))


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """启动即显示的程序窗口：菜单、模式按钮、热键与默认模式。"""

    capture_requested = Signal(str)      # rect / window / fullscreen
    long_capture_requested = Signal()    # 独立命令：滚动长截图（框选→确定→自动拼接）
    mode_changed = Signal(str)           # 用户改了「默认模式」
    hotkey_requested = Signal()
    help_requested = Signal(str)         # help / cli
    about_requested = Signal()
    open_dir_requested = Signal()
    minimize_requested = Signal()
    quit_requested = Signal()
    language_requested = Signal()

    STYLE = (
        "QMainWindow, QWidget#central { background:#f7f8fa; }"
        "QFrame#card { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; }"
        "QPushButton#mode { background:#ffffff; border:1px solid #d1d5db; border-radius:8px;"
        " padding:14px 6px; color:#111827; font-size:13px; }"
        "QPushButton#mode:hover { border-color:#0a84ff; background:#f0f7ff; }"
        "QPushButton#long { background:#f0f7ff; border:1px solid #b6d7fb; border-radius:8px;"
        " padding:10px 8px; color:#0a6ed1; font-size:13px; font-weight:bold; }"
        "QPushButton#long:hover { border-color:#0a84ff; background:#e2f0ff; }"
        "QPushButton#minor { padding:4px 12px; }"
        "QPushButton#primary { background:#0a84ff; color:#fff; border:none; border-radius:6px;"
        " padding:8px 16px; font-weight:bold; }"
        "QComboBox { padding:4px 8px; }"
        "QLabel#sub, QLabel#hint { color:#6b7280; }"
    )

    def __init__(self, icon: QIcon, hotkey: Hotkey, mode: str, save_dir: Path) -> None:
        super().__init__()
        # 程序真正退出时由 App 置 True：closeEvent 直接放行关闭，
        # 不再走「最小化到托盘」并弹出「程序仍在运行」之类的提示。
        self._allow_close = False
        self._save_dir = Path(save_dir)
        self._actions: dict[str, QAction] = {}
        self.setWindowTitle(app_name())
        self.setWindowIcon(icon)
        self.setMinimumWidth(540)
        self.resize(620, 470)
        self.setStyleSheet(self.STYLE)
        self._build_menu()
        self._build_body(save_dir)
        self.set_hotkey(hotkey)
        self.set_mode(mode)
        LANG.changed.connect(self.retranslate_ui)

    def _build_menu(self) -> None:
        mb = self.menuBar()
        self._menus: dict[str, object] = {}

        m_file = mb.addMenu(t("文件(&F)"))
        self._menus["file"] = m_file
        a_dir = QAction(t("打开保存目录"), self)
        a_dir.triggered.connect(lambda _checked=False: self.open_dir_requested.emit())
        m_file.addAction(a_dir)
        a_min = QAction(t("最小化到托盘"), self)
        a_min.triggered.connect(lambda _checked=False: self._minimize_to_tray())
        m_file.addAction(a_min)
        m_file.addSeparator()
        a_quit = QAction(t("退出"), self)
        a_quit.triggered.connect(lambda _checked=False: self.quit_requested.emit())
        m_file.addAction(a_quit)
        self._actions.update(dir=a_dir, minimize=a_min, quit=a_quit)

        m_shot = mb.addMenu(t("截图(&S)"))
        self._menus["shot"] = m_shot
        for mode in CAPTURE_MODES:
            a = QAction(mode_label(mode), self)
            a.triggered.connect(
                lambda _checked=False, m=mode: self.capture_requested.emit(m)
            )
            m_shot.addAction(a)
            self._actions[f"shot_{mode}"] = a
        m_shot.addSeparator()
        a_long = QAction(t("滚动长截图…"), self)
        a_long.triggered.connect(lambda _checked=False: self.long_capture_requested.emit())
        m_shot.addAction(a_long)
        self._actions["long_capture"] = a_long

        m_set = mb.addMenu(t("设置(&E)"))
        self._menus["settings"] = m_set
        a_hk = QAction(t("设置热键…"), self)
        a_hk.triggered.connect(lambda _checked=False: self.hotkey_requested.emit())
        m_set.addAction(a_hk)
        a_lang = QAction(
            f"{t('语言…')}  [{language_label(LANG.preference)}]", self
        )
        a_lang.triggered.connect(lambda _checked=False: self.language_requested.emit())
        m_set.addAction(a_lang)
        self._actions.update(hotkey=a_hk, language=a_lang)

        m_help = mb.addMenu(t("帮助(&H)"))
        self._menus["help"] = m_help
        for text_key, topic in (("使用说明…", "help"), ("命令行参数…", "cli")):
            a = QAction(t(text_key), self)
            a.triggered.connect(
                lambda _checked=False, v=topic: self.help_requested.emit(v)
            )
            m_help.addAction(a)
            self._actions[f"help_{topic}"] = a
        m_help.addSeparator()
        a_about = QAction(t("关于…"), self)
        a_about.triggered.connect(lambda _checked=False: self.about_requested.emit())
        m_help.addAction(a_about)
        self._actions["about"] = a_about

    def _build_body(self, save_dir: Path) -> None:
        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(12)

        self._title = QLabel(app_name())
        self._title.setStyleSheet("font-size:22px; font-weight:bold; color:#111827;")
        root.addWidget(self._title)
        self._sub = QLabel(t("程序已启动 · 托盘常驻 · 关闭本窗口只会最小化到托盘，不会退出程序"))
        self._sub.setObjectName("sub")
        self._sub.setWordWrap(True)
        root.addWidget(self._sub)

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.hotkey_label = QLabel("")
        self._b_change = QPushButton(t("更改…"))
        self._b_change.setObjectName("minor")
        self._b_change.clicked.connect(lambda _checked=False: self.hotkey_requested.emit())
        self.mode_combo = QComboBox()
        for m in CAPTURE_MODES:
            self.mode_combo.addItem(mode_label(m), m)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo)

        self._lbl_hotkey = QLabel(t("截图热键"))
        grid.addWidget(self._lbl_hotkey, 0, 0)
        grid.addWidget(self.hotkey_label, 0, 1)
        grid.addWidget(self._b_change, 0, 2)
        self._lbl_mode = QLabel(t("默认模式"))
        grid.addWidget(self._lbl_mode, 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)
        self._hint = QLabel(t("热键与托盘「截图」使用此模式"))
        self._hint.setObjectName("hint")
        grid.addWidget(self._hint, 1, 2)
        root.addWidget(card)

        self._lbl_now = QLabel(t("立即截图"))
        root.addWidget(self._lbl_now)
        row = QHBoxLayout()
        row.setSpacing(10)
        self._mode_buttons: dict[str, QPushButton] = {}
        for mode in CAPTURE_MODES:
            b = QPushButton(f"{mode_label(mode)}\n{t(MODE_DESC[mode])}")
            b.setObjectName("mode")
            b.setMinimumHeight(76)
            b.clicked.connect(
                lambda _checked=False, m=mode: self.capture_requested.emit(m)
            )
            row.addWidget(b)
            self._mode_buttons[mode] = b
        root.addLayout(row)

        # 独立命令：滚动长截图（不属于三种截图模式，走专门的框选→拼接流程）
        self._b_long = QPushButton(
            f"{t('滚动长截图…')}    {t('点击窗口后自动滚动拼接成长图')}"
        )
        self._b_long.setObjectName("long")
        self._b_long.setMinimumHeight(42)
        self._b_long.setToolTip(t("点击窗口后自动滚动拼接成长图"))
        self._b_long.clicked.connect(
            lambda _checked=False: self.long_capture_requested.emit()
        )
        root.addWidget(self._b_long)

        self._tip = QLabel(
            t("提示：截图中按 Esc 取消；选区确定后可标注、取字、复制或保存。 详细说明见「帮助 → 使用说明」。")
        )
        self._tip.setObjectName("hint")
        self._tip.setWordWrap(True)
        root.addWidget(self._tip)
        root.addStretch(1)

        self.setCentralWidget(central)
        self.set_save_dir(save_dir)

    def _on_mode_combo(self, idx: int) -> None:
        mode = self.mode_combo.itemData(idx)
        if isinstance(mode, str):
            self.mode_changed.emit(mode)

    # ------------------------------------------------------------ 语言刷新
    def retranslate_ui(self, _code: str = "") -> None:
        """LANG.changed 触发：已在界面上的所有文案立即换语言。"""
        self.setWindowTitle(app_name())
        for key, text_key in (
            ("file", "文件(&F)"), ("shot", "截图(&S)"),
            ("settings", "设置(&E)"), ("help", "帮助(&H)"),
        ):
            self._menus[key].setTitle(t(text_key))
        for key, text_key in (
            ("dir", "打开保存目录"), ("minimize", "最小化到托盘"),
            ("quit", "退出"), ("hotkey", "设置热键…"),
            ("help_help", "使用说明…"), ("help_cli", "命令行参数…"),
            ("about", "关于…"), ("long_capture", "滚动长截图…"),
        ):
            self._actions[key].setText(t(text_key))
        for mode in CAPTURE_MODES:
            self._actions[f"shot_{mode}"].setText(mode_label(mode))
        self._actions["language"].setText(
            f"{t('语言…')}  [{language_label(LANG.preference)}]"
        )

        self._title.setText(app_name())
        self._sub.setText(t("程序已启动 · 托盘常驻 · 关闭本窗口只会最小化到托盘，不会退出程序"))
        self._b_change.setText(t("更改…"))
        self._lbl_hotkey.setText(t("截图热键"))
        self._lbl_mode.setText(t("默认模式"))
        self._hint.setText(t("热键与托盘「截图」使用此模式"))
        self._lbl_now.setText(t("立即截图"))
        for mode, btn in self._mode_buttons.items():
            btn.setText(f"{mode_label(mode)}\n{t(MODE_DESC[mode])}")
        self._b_long.setText(
            f"{t('滚动长截图…')}    {t('点击窗口后自动滚动拼接成长图')}"
        )
        self._b_long.setToolTip(t("点击窗口后自动滚动拼接成长图"))
        self._tip.setText(
            t("提示：截图中按 Esc 取消；选区确定后可标注、取字、复制或保存。 详细说明见「帮助 → 使用说明」。")
        )
        idx = self.mode_combo.currentIndex()
        self.mode_combo.blockSignals(True)
        for i, mode in enumerate(CAPTURE_MODES):
            self.mode_combo.setItemText(i, mode_label(mode))
        self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)
        self.set_save_dir(self._save_dir)
        self.set_hotkey(self._hotkey)

    # ------------------------------------------------------------ 对外更新
    def set_hotkey(self, hk: Hotkey) -> None:
        self._hotkey = hk
        self.hotkey_label.setText(f"<b>{hk.label()}</b>")

    def set_mode(self, mode: str) -> None:
        idx = self.mode_combo.findData(mode)
        if idx < 0 or idx == self.mode_combo.currentIndex():
            return
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)

    def set_save_dir(self, path: Path) -> None:
        self._save_dir = Path(path)
        self.statusBar().showMessage(t("保存目录：{path}", path=self._save_dir))

    def _minimize_to_tray(self) -> None:
        self.hide()
        self.minimize_requested.emit()

    def closeEvent(self, ev) -> None:  # noqa: N802
        # 程序正在退出：安静关闭窗口，不做任何提示 / 不最小化到托盘。
        if self._allow_close:
            ev.accept()
            return
        # 关窗口 = 最小化到托盘，程序继续常驻；退出走菜单
        ev.ignore()
        self._minimize_to_tray()


# ---------------------------------------------------------------------------
# 帮助窗口
# ---------------------------------------------------------------------------
class HelpWindow(QDialog):
    """非模态说明窗口，截图时由 App 临时隐藏、结束后恢复。"""

    def __init__(self, topic: str = "help", parent=None) -> None:
        super().__init__(parent)
        self._topic = "help"
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        lay.addWidget(self.browser, 1)
        row = QHBoxLayout()
        self._close_btn = QPushButton(t("关闭"))
        self._close_btn.clicked.connect(lambda _checked=False: self.close())
        row.addStretch(1)
        row.addWidget(self._close_btn)
        lay.addLayout(row)
        self.show_topic(topic)
        LANG.changed.connect(self.retranslate_ui)

    def show_topic(self, topic: str) -> None:
        self._topic = topic if topic in ("help", "cli") else "help"
        name = app_name()
        if self._topic == "cli":
            self.browser.setHtml(cli_help_html(name=name))
            self.setWindowTitle(t("{app} - 命令行参数", app=name))
        else:
            self.browser.setHtml(help_html())
            self.setWindowTitle(t("{app} - 使用说明", app=name))
        self.browser.moveCursor(QTextCursor.Start)

    def retranslate_ui(self, _code: str = "") -> None:
        self._close_btn.setText(t("关闭"))
        self.show_topic(self._topic)


CLI_HELP_HTML = "<html><body style=\"font-family:'Microsoft YaHei';font-size:13px;\">" \
    "<h2>命令行参数</h2><pre style=\"font-family:Consolas,'Microsoft YaHei';font-size:13px;\">" \
    + CLI_HELP.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") \
    + "</pre></body></html>"


# ---------------------------------------------------------------------------
# 语言设置
# ---------------------------------------------------------------------------
class LanguageDialog(QDialog):
    """「跟随系统 + 8 种语言」下拉框；切换后由 LANG.changed 立即刷新所有窗口。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("语言设置"))
        self.setMinimumWidth(400)
        self.setStyleSheet(
            "QDialog { background:#f7f8fa; }"
            "QLabel#langHint { color:#6b7280; }"
            "QPushButton { padding:6px 14px; }"
            "QPushButton#langOk { background:#0a84ff; color:#fff; border:none;"
            " border-radius:5px; font-weight:bold; padding:7px 18px; }"
            "QComboBox { padding:5px 8px; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        self._heading = QLabel(t("界面语言"))
        self._heading.setStyleSheet("font-size:15px; font-weight:bold;")
        root.addWidget(self._heading)

        self.combo = QComboBox()
        self._fill_choices()
        root.addWidget(self.combo)

        self._hint = QLabel(
            t("选择程序界面使用的语言。启动时默认跟随系统语言，设置会被记住。")
            + "\n" + t("切换后已打开的窗口会立即刷新。")
        )
        self._hint.setObjectName("langHint")
        self._hint.setWordWrap(True)
        root.addWidget(self._hint)

        self._current = QLabel(
            t("当前语言：{name}", name=language_label(LANG.preference))
        )
        root.addWidget(self._current)

        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel = QPushButton(t("取消"))
        self._cancel.clicked.connect(self.reject)
        self._ok = QPushButton(t("确定"))
        self._ok.setObjectName("langOk")
        self._ok.setDefault(True)
        self._ok.clicked.connect(self._apply)
        row.addWidget(self._cancel)
        row.addWidget(self._ok)
        root.addLayout(row)

        LANG.changed.connect(self.retranslate_ui)

    def _fill_choices(self) -> None:
        wanted = LANG.preference
        self.combo.blockSignals(True)
        self.combo.clear()
        for code, label in language_choices():
            self.combo.addItem(label, code)
        idx = self.combo.findData(wanted)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)

    def _apply(self) -> None:
        code = self.combo.currentData()
        if isinstance(code, str):
            LANG.set_preference(code)
        self.accept()

    def retranslate_ui(self, _code: str = "") -> None:
        self.setWindowTitle(t("语言设置"))
        self._heading.setText(t("界面语言"))
        self._hint.setText(
            t("选择程序界面使用的语言。启动时默认跟随系统语言，设置会被记住。")
            + "\n" + t("切换后已打开的窗口会立即刷新。")
        )
        self._current.setText(
            t("当前语言：{name}", name=language_label(LANG.preference))
        )
        self._cancel.setText(t("取消"))
        self._ok.setText(t("确定"))
        self._fill_choices()
