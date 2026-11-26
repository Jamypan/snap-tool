# -*- coding: utf-8 -*-
"""
snapui.py —— 程序主窗口、帮助说明、关于对话框、托盘图标。

只依赖 PySide6 与 hotkeys，不反向 import snap.py / snapeditor.py，
因此可单独离屏实例化做自检。主窗口只发信号，具体流程由 App 编排。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from hotkeys import CAPTURE_MODES, Hotkey, mode_label
from i18n import LANG, app_name, language_choices, language_label, t
from i18n_docs import about_html, cli_help, cli_help_html, help_html
from recording_ui import RecordPanel
from ui_theme import (
    BAR_HEIGHT,
    BAR_RADIUS,
    BTN_RADIUS,
    BTN_SIZE,
    CREAM,
    FONT_QSS,
    GREEN,
    HOVER,
    INK,
    INK2,
    INK3,
    LINE,
    ORANGE,
    PANEL_RADIUS,
    PICK_W,
    SOFT,
    Card,
    IconButton,
    PanelRow,
    PillButton,
    RowPicker,
    apply_shadow,
    group_title,
    paint_icon,
)

# 常量保留简体中文：配置目录名、exe 名、自检与旧版脚本都依赖它，
# 界面上显示的程序名统一用随语言变化的 app_name()。
APP_NAME = "截屏助手"
APP_VERSION = "V52"            # 「关于」窗口显示的版本号；改版本只改这一处
CONTACT_EMAIL = "283096251@qq.com"

# 画笔平滑度档位显示文案（key 用中文原文，走 i18n 翻译）
PEN_SMOOTH_LABELS = {
    "off": "关闭（原始线条）", "low": "轻度", "medium": "中等", "high": "强",
}
PEN_SMOOTH_LEVELS = ("off", "low", "medium", "high")
# 面板右侧只显示短档位名
PEN_SMOOTH_SHORT = {"off": "关闭", "low": "轻度", "medium": "中等", "high": "强"}

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
<p>双击 <code>run-silent.bat</code> 启动后，屏幕中央会显示<b>两列命令面板</b>，这就是程序主窗口：左列「截图 / 编辑与输出」，右列「设置 / 帮助」，共 12 行。每行左侧图标、中间标题与说明、右侧当前取值或快捷键——<b>平滑度、界面语言、热键都能就地切换</b>，点一下循环到下一个取值，改完立即生效并自动记住。
三种截图方式那三行<b>分成左右两个热区</b>：左边点一下就用这种方式马上截图，右边那条窄栏点一下只把它设为默认方式（不截图、面板也不关）；<b>当前默认的那一行整行浅橙底，右侧显示「默认」和实心橙点</b>。
<b>关掉窗口只会收回托盘，程序不会退出</b>；要彻底退出请点面板<b>右上角的「退出」按钮</b>或托盘右键「退出」。托盘右键「显示主窗口」可随时叫回来，左键单击托盘图标则直接截图。</p>
<p>「关于」保留在右列「帮助」组最后一行，点它查看版本信息与联系邮箱。程序不再有常驻桌面的悬浮条，也不会一直压在其它窗口上面。</p>

<h2>2. 三种截图模式</h2>
<table>
<tr><th>模式</th><th>怎么操作</th><th>适合场景</th></tr>
<tr><td>框选截图</td><td>按住鼠标左键拖出矩形，松手后可拖选区、拖八个控制点微调</td><td>截局部内容，默认模式</td></tr>
<tr><td>窗口截图</td><td>移动鼠标，目标窗口会高亮并显示标题与尺寸，单击确认；右键或 Esc 取消</td><td>完整截下某个窗口（自动去掉 Win10/11 的透明阴影边框）</td></tr>
<tr><td>全屏截图</td><td>进入时自动选中整个虚拟屏幕，无需拖选</td><td>截整个桌面或多显示器合屏</td></tr>
</table>
<p class="hint">窗口模式会跳过截屏助手自己的窗口；启动截图时本程序的主窗口、帮助窗口、编辑器窗口都会临时隐藏，避免被拍进图里，结束后自动恢复。
三种模式确定选区后，<b>选区外侧会浮出一条确认条</b>：最左「复制」可直接把原图放进剪贴板，<b>并关闭截图编辑与截屏助手两个窗口，只留托盘常驻</b>；「取字」直接识别选区里的文字；「钉在桌面」把选区贴成浮窗；「✕」取消；右侧深色的<b>「确定」</b>才打开截图编辑窗口，标注、取字、复制、保存的用法完全一致。选区下方空间不够时确认条会自动翻到上方。全屏直截与滚动长截图完成时也会自动把原图放进剪贴板；长截图随后进入编辑器，可直接标注。
遮罩顶部还有一条<b>模式切换条</b>，框选到一半想改成截窗口或全屏，直接点一下就地切换，不用退出重来。
另有独立「滚动长截图」命令，见第 9 节。</p>

<h2>3. 全局热键</h2>
<p>默认 <b>Alt + Z</b> 唤起截图（v52 起，旧版为 Ctrl + Shift + A），使用的模式由命令面板左列那三行<b>右侧「默认方式」栏点选</b>决定（会记住，重启后仍有效，被选中的那一行整行浅橙底并显示「默认」）。
点主窗口「截图热键」一行或托盘右键「设置热键…」可改成任意组合：打开后直接按键录制，也可以勾选修饰键 + 选主键。
<b>录屏热键固定为 F9</b>（开始 / 停止都用它），面板切到「录屏」页即可用。面板里的「贴图热键」同理，保存时立即生效，无需重启。</p>
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
<tr><td>文字输入位置</td><td>用文字工具点击后输入，按回车提交时文字会<b>留在输入时看到的位置</b>，不再往上跳一个字高；画布放大 / 缩小、高 DPI 屏幕下同样对齐。双击已有文字改内容时，输入框会盖在原字上，改完坐标不变（旋转过的文字也一样）</td></tr>
<tr><td>视图放缩</td><td><b>Ctrl + 滚轮</b>以光标为锚点放大 / 缩小，或点顶部居中<b>放大镜图标（带下拉小三角）</b>：放大（Ctrl+=）、缩小（Ctrl+-）、实际大小 1:1（Ctrl+1）、适应窗口（Ctrl+0），当前比例显示在悬浮提示里；放大后<b>按住鼠标中键拖动</b>可平移画布。导出始终是原图全分辨率</td></tr>
<tr><td>箭头</td><td>两端有圆形控制柄，拖动可改长度与方向（可拖过另一端反向）</td></tr>
<tr><td>矩形 / 椭圆四角</td><td>选中后外接矩形的<b>四个角</b>出现圆形控制柄，拖动任一角即可改变宽高与形状：对角保持固定、可拖过对角翻转、宽高有最小值保护；截图遮罩与程序窗口编辑器都可用，画布放缩后手柄大小与命中范围不变。马赛克、画笔等其它标注仍只可整体拖动或拉伸端点</td></tr>
<tr><td>形状旋转</td><td>选中<b>矩形 / 椭圆 / 文字</b>后，上方会出现一个圆形<b>旋转柄</b>：鼠标靠近时光标变成<b>环形箭头</b>提示可以旋转；拖动它即可绕形状中心任意旋转，按住 <b>Shift</b> 吸附到 15° 整数倍，Ctrl+[ / Ctrl+] 提供 90° 步进。旋转后四角控制柄、选中虚线框与点选命中都会跟着转；样式面板里不再显示旋转角度。马赛克、箭头 / 直线、画笔保持原样</td></tr>
<tr><td>整图旋转 / 镜像</td><td>程序窗口工具条右侧一组按钮：顺旋（顺时针 90° Ctrl+R）、逆旋（逆时针 90° Ctrl+Shift+R）、左右（镜像 Ctrl+H）、上下（镜像 Ctrl+Shift+H）；底图与已有标注一起变，<b>文字标注的字形也跟着旋转</b>（不再保持水平）；镜像时文字仍可读、不做反字。Ctrl+Z 可撤销，角度一并恢复</td></tr>
<tr><td>画笔端点箭头</td><td>选中画笔后弹出的样式面板里勾选「起点加箭头 / 终点加箭头」；无选中时设新建画笔默认，选中画笔时改当前线</td></tr>
<tr><td>撤销</td><td>Ctrl + Z，或编辑器底部 Dock 的「撤销」（整图变换也能撤销）</td></tr>
<tr><td>复制 / 保存 / 取消</td><td>选区外侧确认条最左的「复制」：复制原图并关闭截图编辑与截屏助手两个窗口，不打开编辑器、只留托盘；点「确定」才打开截图编辑窗口；已进入编辑器后用 Ctrl+Enter 更新成图，顶部「保存」存盘；Esc 或顶部「✕」取消</td></tr>
<tr><td>滚动长截图</td><td>独立命令，单击窗口滚屏、结束后进入编辑器：主窗口「滚动长截图…」一行 / 托盘右键均可启动，详见第 9 节</td></tr>
</table>
<p class="hint">编辑器窗口没有系统标题栏：顶部<b>正中央是 6 个纯图标按钮，风格与底部 Dock 完全一致</b>——复制 / 保存 / 钉在桌面 / 取字 / 图像变换（带下拉三角） / 缩放（带下拉三角）；「另存为」与「保存」功能相同，已合并为一个「保存」（紧跟复制）。右上角是最小化 / 最大化 / 关闭（关闭只有一个 ✕）。双击顶部空白处也能最大化/还原，右下角可拖拽调节大小。中间是奶油色画布，图片带柔和投影，<b>文字标注的背景框与边框都带圆角</b>；<b>底部居中是 Dock</b>——选择、矩形、椭圆、箭头、直线、画笔、马赛克、文字、撤销、钉在桌面、复制（深色主按钮）；右侧浮层是选中标注的样式面板，没选中标注时不出现。所有命令都在顶部图标按钮里，快捷键仍然可用。</p>
<p class="hint">如果识别内容是<b>表格</b>，「复制全部」与拖选复制都会按原表格的<b>行列结构</b>输出：列与列之间用 <code>Tab</code> 分隔、行与行之间换行，直接粘贴到 Excel / WPS 表格即可对回原来的单元格位置（拖选时未选中的单元格留空）。</p>
<p class="hint">视图放缩只改变屏幕上的显示比例，不会缩放、重采样导出图片；坐标换算、取字行块、文字输入都会跟着比例同步，因此放大后仍能精确标注。马赛克是纯像素化效果，没有颜色、线宽、线型等可调样式：使用马赛克工具或选中马赛克标注时，样式面板都不会弹出。</p>
<p class="hint">旋转 90° 后图片宽高互换，矩形/箭头/画笔/文字等标注位置跟着变换；文字按包围盒中心映射，字形与底图一起旋转（镜像时保持可读，不变成反字）。导出始终是全分辨率。</p>

<h2>5. 取字（OCR）</h2>
<p>从选区确认条的「取字」、编辑器底部 Dock 的「取字」，或菜单「编辑 → OCR 取字」进入，识别结果会<b>逐行盖回原文位置</b>：每行文字可选中、拖选、Ctrl+A / Ctrl+C 复制，
也可用窗口顶部取字工具条的「复制选中」「复制全部」。复制后约 0.4 秒自动收起，回到正常编辑态；
点「返回」或按 Esc 只收起取字层，不会关闭窗口。改变窗口大小后行块会重新盖回，不会错位。
识别中按 Esc 取消本次取字；识别中、失败或后端不返回坐标时显示整块结果面板。
取字默认走 RapidOCR（ONNX 模型随程序自带），首次取字需加载模型约 1~5 秒，之后常驻缓存。</p>
<p>若识别内容是<b>表格</b>，「复制全部」与拖选复制都会按原行列输出：列间用 Tab、行间用换行，可直接粘贴到 Excel / WPS 对应单元格。
单元格内的多行文字会<b>合并回同一格</b>（按从上到下顺序拼接），不会被拆成多个表格行。</p>

<h2>6. 文件与配置</h2>
<p>截图默认保存到 <code>%USERPROFILE%\\Pictures\\Screenshots</code>（托盘右键「打开保存目录」可直接在资源管理器里打开；托盘左键单击图标就是截图）。
配置在 <code>%APPDATA%\\SnapTool\\settings.json</code>，含热键与默认截图模式；设置环境变量
<code>SNAPTOOL_HOME</code> 可把配置目录改到别处，方便便携版。</p>

<h2>7. 命令行</h2>
<p><code>python snap.py --help</code> 查看全部参数；<code>--shot</code> 启动后立即截一次图；
<code>--restart</code> 结束后台残留实例并重启（等价于双击 <code>restart.bat</code>）。
命令行参数说明也可以在控制台里用 <code>--help</code> 直接看到。</p>

<h2>8. 常见问题</h2>
<ul>
<li><b>按热键没反应：</b>多半是热键被别的程序占用。托盘会弹注册失败提示，去命令面板「设置热键…」换一个组合；也可以直接点主窗口里的「框选截图」一行。</li>
<li><b>提示「已经在运行」却看不到程序：</b>托盘图标可能被折叠到通知区（点 ^ 展开），或窗口被拖到了屏幕边缘看不见的位置。重复启动时会先把它唤醒并显示，弹窗里选「是」即可结束它并重启，或直接双击 restart.bat。</li>
<li><b>改了代码没变化：</b>程序是单实例 + 托盘常驻，旧进程仍在跑旧代码，双击 restart.bat 即可用新代码重启。</li>
<li><b>高分屏坐标不准：</b>程序已开启 per-monitor DPI 感知；若仍偏移，重启程序后再试。</li>
<li><b>杀软误报：</b>全局热键 + 屏幕捕获容易被误报，未签名的 exe 需要加入信任。</li>
</ul>

<h2>9. 滚动长截图</h2>
<p>这是与三种截图模式并列的<b>独立命令</b>，从主窗口「滚动长截图…」一行或托盘右键「滚动长截图…」启动。它<b>不需要框选</b>：<b>单击目标窗口即自动向下滚屏，结束后进入编辑器可继续标注</b>。</p>
<ol>
<li>启动后先隐藏本程序所有窗口，再抓一帧底图并显示遮罩；</li>
<li>移动鼠标，目标窗口会高亮并显示标题；<b>单击左键选中窗口</b>，程序取它的客户区（自动排除标题栏与边框）作为滚动区域，<b>立即开始</b>逐帧抓屏、模板匹配拼成长图；</li>
<li>滚动中：<b>左键单击暂停，再单击继续</b>；<b>右键单击或按 <b>Esc</b> 结束</b>；滚到页面底部会<b>自动结束</b>；</li>
<li>结束后自动进入编辑器，可继续标注、复制，或另存为 PNG / JPG。</li>
</ol>
<p class="hint">拼接期间本程序窗口保持隐藏，控制条放在目标窗口之外（窗口占满屏幕时会在抓帧瞬间临时隐藏），避免被拍进长图；结束后自动恢复。若页面含固定悬浮元素或动画导致无法自动对齐，会提示结果可能不完整，可改用普通截图。</p>
<p class="hint"><b>网页不易中途截断</b>：单帧几乎没滚动不会立刻判「到底」，而是连续确认 3 帧；模板匹配失败会减小步长、多等一拍重试 2 次；模板从画面中部取以避开固定顶栏；滚轮步长按上一帧新增行数自适应；滚轮每次发给目标窗口右侧滚动条，保证页面持续滚动。控制条实时显示帧数、高度与匹配分数，结束时托盘提示会说明共拼了多少帧以及结束原因（到底 / 无法对齐 / 帧数或高度上限 / 手动结束）。</p>

<h2>10. 贴图钉在桌面</h2>
<p>把当前截图（含标注）贴成一张<b>无边框、可置顶的图片浮窗</b>，像便利贴一样钉在桌面上，方便对着它长时间参考 / 比对。共有四个入口：</p>
<ul>
<li>框选后确认阶段的「<b>钉在桌面</b>」按钮：贴当前截图，并收起截图界面与编辑器，只留浮窗；</li>
<li>编辑器「<b>文件 → 钉在桌面</b>」：贴当前带标注的成图，编辑器保持打开可继续编辑；</li>
<li>托盘右键「<b>贴出剪贴板图片</b>」：把剪贴板里的任意图片贴到桌面；</li>
<li>贴图热键（默认 <b>Ctrl + Shift + P</b>，可在命令面板「设置 → 设置贴图热键…」修改）：同样贴剪贴板图片。</li>
</ul>
<p>浮窗操作：<b>左键拖动</b>移动，<b>滚轮</b>缩放（0.1~8 倍），<b>右键菜单</b>可复制图片 / 另存为 / 调透明度（100/75/50/25%）/ 开关保持置顶 / 重置大小 / 关闭；<b>双击</b>或 <b>Esc</b> 关闭，<b>Ctrl+C</b> 复制原图。可同时钉多张，鼠标悬停时右上角出现关闭按钮。程序退出时会一并收起所有贴图。</p>

<h2>11. 录屏</h2>
<p>主窗口顶部切到「<b>录屏</b>」页（或按 <b>F9</b> 直接用默认方式开录）。录屏页和截图页用同一套左右分栏：<b>左列点某一行立刻用该方式录</b>（框选 / 窗口 / 全屏），<b>右列窄条点「默认」只设默认方式</b>，底部「开始录屏」用默认方式。</p>
<ul>
<li><b>框选录屏</b>：屏幕上拖出选区，松开即开始录，录制中选区固定不可改；</li>
<li><b>窗口录屏</b>：悬停高亮目标窗口，单击录制该窗口；</li>
<li><b>全屏录屏</b>：整块桌面，多屏合为一块。</li>
</ul>
<p>左列可开 <b>系统声音</b>（电脑播放的声音）、<b>麦克风</b>（你说话）、<b>录制鼠标指针</b>，以及 <b>摄像头画中画</b>（位置和大小可调）。右列设 <b>画面帧率</b>（15/20/24/30 fps）、<b>音频保存方式</b>、<b>保存位置</b>（默认在「图片\\Screenshots」，文件名 <code>录屏_日期_时间.mp4</code>）。每次开始录制前会再确认一次音频怎么存（整合到视频 / 分开存 WAV / 两者都要）。</p>
<p>开始录制后<b>本程序所有窗口自动隐藏</b>，屏幕边缘一圈红框表示正在录，底部悬浮控制条显示<b>计时、声音电平、暂停、停止</b>；按 <b>F9</b> 或点控制条的停止键结束，暂停后再按 F9 继续。停止后自动合成视频并保存到设定目录，托盘会提示结果。</p>
<p class="hint">系统声音录制依赖系统的回录设备（立体声混音 / Stereo Mix）；若未检测到，对应开关会不可用。只开一路声音时，视频里的两种音轨方式效果相同。</p>
</body></html>
"""

CLI_HELP = f"""{APP_NAME} —— 命令行参数

  python snap.py              正常启动：主窗口命令面板 + 托盘常驻
  python snap.py --shot       启动后立即截一次图（使用默认截图模式）
  python snap.py --restart    结束后台残留实例并重新启动（不弹确认框）
  python snap.py --selftest   只跑后端自检，不进入界面
                              结果写入 %APPDATA%\\SnapTool\\selftest.log
  python snap.py --help       显示本说明（也可写 -h 或 /?）

日常使用请双击 run-silent.bat（无黑窗口）。程序是单实例，重复启动会先唤醒
已有实例；若看不到界面，弹窗里选「是」即可结束后台实例并重启，
也可直接双击 restart.bat 一键重启。启动诊断见 %APPDATA%\\SnapTool\\startup.log。

三种截图模式：框选（拖鼠标选区域）、窗口（悬停高亮并单击）、全屏（自动选中整个虚拟屏幕）。
另有独立命令「滚动长截图…」（主窗口 / 托盘右键）：单击目标窗口即自动向下滚屏并拼接成长图，不框选，结束后进入编辑器可标注；滚动中左键暂停 / 继续、右键或 Esc 结束、到底自动结束。
默认方式与全局热键保存在 %APPDATA%\\SnapTool\\settings.json，
默认方式在命令面板左列「截图」三行右侧那一栏点选，热键在托盘菜单「设置热键…」里改。

更多说明见程序内帮助（托盘右键「使用说明」），或项目 README.md。
"""

ABOUT_HTML = f"""
<div style="font-family:'Microsoft YaHei',sans-serif; font-size:13px; color:#1f2937; line-height:1.6;">
<p style="font-size:19px; font-weight:bold; margin:0 0 4px 0;">{APP_NAME}</p>
<p style="font-size:12px; color:#6b7280; margin:0 0 10px 0;">版本：{APP_VERSION}</p>
<p>一个自制功能强大的Windows桌面截图软件。</p>
<p>功能：三种截图模式、对象化标注编辑、整图旋转 / 镜像、画笔端点箭头、独立「滚动长截图」命令、中文 OCR 逐行盖回取字、全局热键自定义、8 种界面语言。</p>
<p style="font-size:13px;">联系邮箱：<a href="mailto:{CONTACT_EMAIL}" style="color:#0a6ed1;">{CONTACT_EMAIL}</a></p>
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
# 主窗口：迷你悬浮条 + 命令面板（方案 E）
# ---------------------------------------------------------------------------
MODE_ICONS = {"rect": "region", "window": "window", "fullscreen": "fullscreen"}
MODE_DESCS = {
    "rect": "拖动选取任意区域",
    "window": "悬停高亮 · 单击确认",
    "fullscreen": "整块桌面 · 多屏合屏",
}


class LogoButton(QPushButton):
    """橙色渐变圆角 Logo（设计稿 .mb-logo）：点击用默认模式截图。"""

    def __init__(self, parent: QWidget | None = None, size: int = 36) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet("background:transparent;border:none;")

    def paintEvent(self, ev) -> None:  # noqa: N802
        from PySide6.QtGui import QLinearGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(0, 0, self._size, self._size)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        grad.setColorAt(0.0, QColor("#ffa257"))
        grad.setColorAt(1.0, QColor("#f97316"))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(r, min(13.0, self._size * 0.36), min(13.0, self._size * 0.36))
        side = self._size * 0.56
        box = QRectF((self._size - side) / 2, (self._size - side) / 2, side, side)
        paint_icon(p, "logo", box, QColor("#ffffff"), 1.9)
        p.end()


class _BarCard(Card):
    """悬浮条卡片：空白处按住可拖动整条（按钮区域正常点击）。"""

    def __init__(self, parent: QWidget, on_drag) -> None:
        super().__init__(parent, radius=BAR_RADIUS, bg=CREAM, border="#ffffff")
        self._on_drag = on_drag
        self._from: QPoint | None = None
        self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.LeftButton:
            self._from = ev.globalPosition().toPoint()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
        if self._from is not None and (ev.buttons() & Qt.LeftButton):
            pos = ev.globalPosition().toPoint()
            self._on_drag(pos - self._from)
            self._from = pos
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
        self._from = None
        super().mouseReleaseEvent(ev)


class CommandPanel(QWidget):
    """完整命令面板 —— 从 v39 起就是程序的主窗口本体（设计稿第 2 屏）。

    两列布局：左列截图命令 + 编辑输出，右列设置 + 帮助。
    所有行都是 PanelRow（QPushButton 子类）。「退出」单独放在标题栏右侧，
    「关于」保留在帮助组原位置。
    """

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(owner)
        self._owner = owner
        self.setFocusPolicy(Qt.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.card = Card(self, radius=PANEL_RADIUS, bg=CREAM, border=LINE)
        self.card.setMinimumWidth(0)
        outer.addWidget(self.card)

        root = QVBoxLayout(self.card)
        root.setContentsMargins(10, 10, 10, 12)
        root.setSpacing(4)

        # ---- 标题栏 ----
        head = QHBoxLayout()
        head.setContentsMargins(10, 6, 10, 8)
        head.setSpacing(10)
        self._logo = LogoButton(self.card, 30)
        head.addWidget(self._logo, 0, Qt.AlignVCenter)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)
        self._title = QLabel(app_name(), self.card)
        self._title.setStyleSheet(
            f"color:{INK};font-size:13.5px;font-weight:800;{FONT_QSS}"
        )
        self._sub = QLabel("", self.card)
        self._sub.setStyleSheet(f"color:{INK3};font-size:11px;{FONT_QSS}")
        title_col.addWidget(self._title)
        title_col.addWidget(self._sub)
        head.addLayout(title_col, 1)
        self._badge = QLabel("", self.card)
        self._badge.setStyleSheet(
            f"color:{GREEN};background:#e6f6ee;border-radius:99px;"
            f"padding:3px 9px;font-size:10.5px;{FONT_QSS}"
        )
        head.addWidget(self._badge, 0, Qt.AlignVCenter)
        # v39：退出从「关于与退出」里拆出来，单独做成面板顶部的按钮
        self._btn_quit = PillButton(t("退出"), "exit", "plain", self.card, height=28)
        self._btn_quit.setObjectName("quitTop")
        self._btn_quit.clicked.connect(
            lambda _=False: self._owner.quit_requested.emit()
        )
        head.addWidget(self._btn_quit, 0, Qt.AlignVCenter)
        root.addLayout(head)

        sep = QWidget(self.card)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{LINE};")
        root.addWidget(sep)

        # ---- 两列主体 ----
        body = QHBoxLayout()
        body.setContentsMargins(0, 4, 0, 0)
        body.setSpacing(0)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(2)
        body.addLayout(left, 1)
        vline = QWidget(self.card)
        vline.setFixedWidth(1)
        vline.setStyleSheet(f"background:{LINE};")
        body.addWidget(vline)
        body.addLayout(right, 1)
        root.addLayout(body)

        self._rows: dict[str, PanelRow] = {}

        def add(lay, key: str, icon_name: str, title: str, desc: str,
                slot, shortcut: str = "", obj: str = "") -> PanelRow:
            row = PanelRow(icon_name, title, desc, shortcut, self.card)
            if obj:
                row.setObjectName(obj)
            row.clicked.connect(lambda _=False: self._fire(slot))
            lay.addWidget(row)
            self._rows[key] = row
            return row

        def group(lay, key: str, label_widget: QLabel,
                  right_widget: QWidget | None = None) -> None:
            holder = QWidget(self.card)
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(12, 8, 12, 3)
            hl.addWidget(label_widget)
            if right_widget is not None:
                # 右列小标题对准下方那一列「默认方式」窄条
                hl.addStretch(1)
                hl.addWidget(right_widget)
            lay.addWidget(holder)

        self._lbl_now = group_title("", self.card)
        self._lbl_pick = group_title("", self.card)
        self._lbl_pick.setFixedWidth(PICK_W)
        self._lbl_pick.setAlignment(Qt.AlignCenter)
        group(left, "g_shot", self._lbl_now, self._lbl_pick)

        # 三种截图方式：一行两个热区——左边点一下就用这种方式截图，
        # 右边窄条只把它设成默认方式（热键与托盘以后都用它）。
        self._pickers: dict[str, RowPicker] = {}
        for mode in CAPTURE_MODES:
            row = add(left, f"mode_{mode}", MODE_ICONS[mode], mode_label(mode),
                      MODE_DESCS[mode], (lambda m=mode: owner._on_mode_click(m)))
            # 左半边是「立刻截图」，悬停给十字星光标；右半边窄条是「定默认」
            row.setCursor(Qt.CrossCursor)
            picker = row.enable_picker()
            picker.clicked.connect(
                lambda _=False, m=mode: owner._on_mode_pick(m))
            self._pickers[mode] = picker

        # 滚动长截图是「动作」不是「方式」，不参与选择：整行点击即执行，右边只留箭头
        self._b_long = add(left, "long_capture", "long", "滚动长截图…",
                           "点击窗口自动滚屏成长图",
                           lambda: owner.long_capture_requested.emit(), obj="long")
        self._b_long.set_pro(True)          # v44：高级功能金色标识
        self._b_long.set_key_icon("chevron")

        left.addSpacing(4)
        self._lbl_edit = group_title("", self.card)
        group(left, "g_edit", self._lbl_edit)
        ocr_row = add(left, "ocr", "text", "OCR 取字", "识别选区文字 · 离线 RapidOCR",
                      lambda: owner.ocr_capture_requested.emit(), "离线")
        ocr_row.set_pro(True)               # v44：高级功能金色标识
        pin_row = add(left, "pin_clipboard", "pin", "贴出剪贴板图片", "钉成桌面浮窗 · 可拖动缩放",
                      lambda: owner.pin_clipboard_requested.emit(), "Ctrl+Shift+P")
        pin_row.set_pro(True)               # v44：高级功能金色标识

        self._lbl_hotkey = group_title("", self.card)
        group(right, "g_set", self._lbl_hotkey)
        self._hk_row = add(right, "hotkey", "key", "截图热键", "点击修改，立即生效",
                           lambda: owner.hotkey_requested.emit())
        self._pinhk_row = add(right, "pin_hotkey", "pin", "贴图热键", "独立于截图热键",
                              lambda: owner.pin_hotkey_requested.emit())
        self._lang_row = add(right, "language", "globe", "界面语言", "8 种语言 · 可跟随系统",
                             lambda: owner.language_requested.emit())
        self._smooth_row = add(right, "pen_smooth", "pen", "画笔平滑度",
                               "关闭 / 轻度 / 中等 / 强", self._cycle_smooth)

        right.addSpacing(4)
        self._lbl_mode = group_title("", self.card)
        group(right, "g_help", self._lbl_mode)
        add(right, "help_help", "help", "使用说明", "10 个完整操作文档",
            lambda: owner.help_requested.emit("help"))
        add(right, "about", "smile", "关于", "版本信息 · 联系邮箱",
            lambda: self._owner.about_requested.emit(), obj="about")

        # 窗口被拉高时多余的高度留在列尾，避免标题 / 副标题被拉开
        left.addStretch(1)
        right.addStretch(1)

        # 兼容旧接口：面板里不再单独放「更改…」按钮
        self._b_change = QPushButton(self.card)
        self._b_change.setVisible(False)
        self._b_change.clicked.connect(lambda _=False: owner.hotkey_requested.emit())
        self.hotkey_label = QLabel("", self.card)
        self.hotkey_label.setVisible(False)
        self._mode_buttons = {}
        for mode in CAPTURE_MODES:
            self._mode_buttons[mode] = self._rows[f"mode_{mode}"]
        self._tip = QLabel("", self.card)
        self._tip.setVisible(False)
        self._last_hide = 0.0
        self.retranslate_ui()

    # ---------------------------------------------------------- 交互
    def hideEvent(self, ev) -> None:  # noqa: N802
        import time as _time
        self._last_hide = _time.monotonic()
        super().hideEvent(ev)

    def _fire(self, slot) -> None:
        # v39：面板就是主窗口本体，点行时不能再 hide()，否则整个窗口消失
        slot()

    def _cycle_smooth(self) -> None:
        levels = PEN_SMOOTH_LEVELS
        cur = self._owner._pen_smooth
        nxt = levels[(levels.index(cur) + 1) % len(levels)] if cur in levels else "medium"
        self._owner.set_pen_smooth(nxt)
        self._owner.pen_smooth_changed.emit(nxt)

    def _cycle_mode(self) -> None:
        """兼容旧调用：按「框选 → 窗口 → 全屏」循环设默认方式。"""
        modes = list(CAPTURE_MODES)
        cur = self._owner._mode
        nxt = modes[(modes.index(cur) + 1) % len(modes)] if cur in modes else "rect"
        self._owner._on_mode_pick(nxt)

    def _about_or_quit(self) -> None:
        """兼容旧调用：现在直接打开关于对话框。"""
        self._owner.about_requested.emit()

    # ---------------------------------------------------------- 刷新
    def set_values(self, hotkey: Hotkey, pin_hotkey: Hotkey | None, mode: str,
                   lang_label: str, smooth: str, save_dir=None) -> None:
        self._hk_row.set_texts(t("截图热键"), t("点击修改，立即生效"), hotkey.label())
        if pin_hotkey is not None:
            self._pinhk_row.set_texts(t("贴图热键"), t("独立于截图热键"),
                                      pin_hotkey.label())
        self._lang_row.set_texts(t("界面语言"), t("8 种语言 · 可跟随系统"), lang_label)
        self._smooth_row.set_texts(t("画笔平滑度"), t("关闭 / 轻度 / 中等 / 强"),
                                   t(PEN_SMOOTH_SHORT.get(smooth, "中等")))
        self.sync_default(mode)

    def sync_default(self, mode: str) -> None:
        """刷新「哪种方式是默认」：整行浅橙 + 右侧窄条实心橙点。"""
        for m, row in self._rows.items():
            if m.startswith("mode_"):
                row.set_highlight(m == f"mode_{mode}")
        for m, picker in self._pickers.items():
            picker.set_selected(m == mode)

    def retranslate_ui(self) -> None:
        self._title.setText(app_name())
        self._sub.setText(t("托盘常驻 · 关闭窗口不会退出程序"))
        self._badge.setText(t("已启动"))
        self._lbl_now.setText(t("截图"))
        self._lbl_pick.setText(t("默认方式"))
        self._lbl_edit.setText(t("编辑与输出"))
        self._lbl_hotkey.setText(t("设置"))
        self._lbl_mode.setText(t("帮助"))
        for mode in CAPTURE_MODES:
            self._rows[f"mode_{mode}"].set_texts(
                mode_label(mode), t(MODE_DESCS[mode]), "")
            self._pickers[mode].setText(t("默认"))
        self.sync_default(self._owner._mode)
        self._b_long.set_texts(t("滚动长截图…"), t("点击窗口自动滚屏成长图"), "")
        self._rows["ocr"].set_texts(t("OCR 取字"), t("识别选区文字 · 离线 RapidOCR"),
                                    t("离线"))
        self._rows["pin_clipboard"].set_texts(
            t("贴出剪贴板图片"), t("钉成桌面浮窗 · 可拖动缩放"), "Ctrl+Shift+P")
        self._rows["hotkey"].set_texts(t("截图热键"), t("点击修改，立即生效"), "")
        self._rows["pin_hotkey"].set_texts(t("贴图热键"), t("独立于截图热键"), "")
        self._rows["language"].set_texts(t("界面语言"), t("8 种语言 · 可跟随系统"), "")
        self._rows["pen_smooth"].set_texts(t("画笔平滑度"), t("关闭 / 轻度 / 中等 / 强"), "")
        self._rows["help_help"].set_texts(t("使用说明"), t("10 个完整操作文档"), "")
        self._rows["about"].set_texts(t("关于"), t("版本信息 · 联系邮箱"), "")
        self._btn_quit.setText(t("退出"))
        self._btn_quit._restyle()
        self._auto_min_width()
        self.adjustSize()

    def _auto_min_width(self) -> None:
        """按两列内容算卡片最小宽度：说明文字优先完整，长文案用省略号兜底。

        行是 QPushButton 子类，Qt 不会拿子布局算 sizeHint，只能手动量：
        widest = 连说明文字一起算的理想宽度；need = 只算标题 + 行尾控件
        （窄条 / 快捷键）的硬需求，说明文字那一栏可以省略。
        最终宽度夹在 [600, 700]：中文约 600，日德法最长文案到 700 为止，再长就省略。
        """
        widest = need = 0
        for row in self._rows.values():
            extra = 0
            picker = row.picker()
            if picker is not None:
                extra = picker.width()
            elif not row.key_label.isHidden():
                extra = row.key_label.sizeHint().width() + 6
            chrome = 24 + 30 + 11 + 11      # 左右内边距 + 图标方块 + 两处间距
            desc_w = row.desc_label.fontMetrics().horizontalAdvance(
                row.desc_label.full_text())
            widest = max(widest, chrome + max(desc_w, row.title_label.sizeHint().width())
                         + extra)
            need = max(need, chrome + row.title_label.sizeHint().width() + extra)
        width = max(600, need * 2 + 22, min(700, widest * 2 + 22))
        self.card.setMinimumWidth(min(700, width))

    def show_at(self, anchor: QWidget) -> None:
        """弹在悬浮条右上角，越界自动贴边。"""
        self.adjustSize()
        size = self.size()
        g = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        x = g.x() - size.width() + 40
        y = g.y() - size.height() - 6
        x = max(avail.left() + 8, min(x, avail.right() - size.width() - 8))
        y = max(avail.top() + 8, y)
        self.move(x, y)
        self.show()
        self.raise_()
        self.setFocus()


class MainWindow(QMainWindow):
    """启动即显示的「迷你悬浮条」：三种截图 + 长截图 + 贴图 + 热键 + 命令面板。

    设计稿方案 E：不再有标题栏和菜单栏，桌面底部只留一条 60px 高的胶囊条。
    所有低频命令收进「⋯」面板；主窗口的鼠标右键仍然给出菜单式入口。
    """

    capture_requested = Signal(str)      # rect / window / fullscreen
    long_capture_requested = Signal()    # 独立命令：滚动长截图
    ocr_capture_requested = Signal()     # v38 框选后直接取字
    pin_clipboard_requested = Signal()   # v38 贴出剪贴板图片
    mode_changed = Signal(str)           # 用户改了「默认模式」
    hotkey_requested = Signal()
    pin_hotkey_requested = Signal()      # v34 设置贴图热键
    help_requested = Signal(str)         # help / cli
    about_requested = Signal()
    open_dir_requested = Signal()
    minimize_requested = Signal()
    quit_requested = Signal()
    language_requested = Signal()
    pen_smooth_changed = Signal(str)     # 画笔平滑度档位 off/low/medium/high
    # v52 录屏
    record_start_requested = Signal(str)     # rect / window / fullscreen
    record_default_changed = Signal(str)
    record_dir_requested = Signal()

    def __init__(self, icon: QIcon, hotkey: Hotkey, mode: str, save_dir: Path,
                 pen_smooth: str = "medium") -> None:
        super().__init__()
        self._allow_close = False
        self._save_dir = Path(save_dir)
        self._actions: dict[str, QAction] = {}
        self._pen_smooth_actions: dict[str, QAction] = {}
        self._pen_smooth = pen_smooth
        self._mode = mode
        self._hotkey = hotkey
        self._pin_hotkey = None
        self._drag_from: QPoint | None = None
        self._placed = False

        self.setWindowTitle(app_name())
        self.setWindowIcon(icon)
        # v39：命令面板就是主窗口本体——普通窗口，能最小化 / 缩放，
        # 不再是无边框、常驻置顶、贴屏幕底部的迷你悬浮条。
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(f"QMainWindow{{background:{CREAM};}}")

        self._build_menu()
        self._panel = CommandPanel(self)

        # v52：顶部「截图 / 录屏」Tab + 两页切换（StackedWidget）
        self._tab_widget = QWidget(self)
        tab_lay = QVBoxLayout(self._tab_widget)
        tab_lay.setContentsMargins(0, 0, 0, 0)
        tab_lay.setSpacing(0)
        self._tabs = QWidget(self._tab_widget)
        tabs_lay = QHBoxLayout(self._tabs)
        tabs_lay.setContentsMargins(14, 6, 14, 4)
        tabs_lay.setSpacing(6)
        self._tab_shot = QPushButton("", self._tabs)
        self._tab_rec = QPushButton("", self._tabs)
        for b in (self._tab_shot, self._tab_rec):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setFixedHeight(30)
        self._tab_shot.setObjectName("tabShot")
        self._tab_rec.setObjectName("tabRec")
        self._tab_shot.clicked.connect(lambda _=False: self.switch_tab("shot"))
        self._tab_rec.clicked.connect(lambda _=False: self.switch_tab("record"))
        tabs_lay.addWidget(self._tab_shot, 1)
        tabs_lay.addWidget(self._tab_rec, 1)
        tab_lay.addWidget(self._tabs)

        self._stack = QStackedWidget(self._tab_widget)
        self._stack.addWidget(self._panel)              # index 0 = 截图
        self._record_panel = RecordPanel(self._tab_widget)  # index 1 = 录屏
        self._stack.addWidget(self._record_panel)
        tab_lay.addWidget(self._stack)
        self.setCentralWidget(self._tab_widget)
        self._current_tab = "shot"
        self._record_panel.start_requested.connect(
            lambda mode: self.record_start_requested.emit(mode))
        self._record_panel.default_mode_changed.connect(
            lambda mode: self.record_default_changed.emit(mode))
        self._record_panel.dir_requested.connect(
            lambda: self.record_dir_requested.emit())
        self._record_panel.help_requested.connect(
            lambda: self.help_requested.emit("help"))
        self._record_panel.about_requested.connect(
            lambda: self.about_requested.emit())
        self._record_panel.quit_requested.connect(
            lambda: self.quit_requested.emit())
        self._tab_shot.setText(t("截图") + "   " + hotkey.label())
        self._tab_rec.setText(t("录屏") + "   F9")
        self._apply_tab_style()

        # 兼容旧属性名：自测与内部逻辑仍按主窗口读这些控件
        self.card = self._panel.card
        self._sub = self._panel._sub
        self._tip = self._panel._tip
        self._lbl_now = self._panel._lbl_now
        self._lbl_edit = self._panel._lbl_edit
        self._lbl_hotkey = self._panel._lbl_hotkey
        self._lbl_mode = self._panel._lbl_mode
        self._mode_buttons = self._panel._mode_buttons
        self._b_change = self._panel._b_change
        self._quick = {m: self._panel._rows[f"mode_{m}"] for m in CAPTURE_MODES}
        self._b_long = self._panel._b_long
        self._b_pin = self._panel._rows["pin_clipboard"]
        # 「⋯」已随悬浮条取消：保留隐藏占位，老代码读属性不会炸
        self._b_more = QPushButton(self)
        self._b_more.setVisible(False)
        self.hotkey_label = QLabel("", self)
        self.hotkey_label.setVisible(False)
        self.set_hotkey(hotkey)
        self.set_mode(mode)
        self.set_pen_smooth(pen_smooth)
        self.set_save_dir(save_dir)
        self.adjustSize()
        self.setMinimumSize(600, 430)
        LANG.changed.connect(self.retranslate_ui)

    # ------------------------------------------------------------ 菜单动作
    def _build_menu(self) -> None:
        """建立 QAction（命令面板 / 右键菜单共用），QMenu 只作标题载体。"""
        self._menus: dict[str, QMenu] = {}

        m_file = QMenu(t("文件(&F)"), self)
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

        m_shot = QMenu(t("截图(&S)"), self)
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

        m_set = QMenu(t("设置(&E)"), self)
        self._menus["settings"] = m_set
        a_hk = QAction(t("设置热键…"), self)
        a_hk.triggered.connect(lambda _checked=False: self.hotkey_requested.emit())
        m_set.addAction(a_hk)
        a_pinhk = QAction(t("设置贴图热键…"), self)
        a_pinhk.triggered.connect(lambda _checked=False: self.pin_hotkey_requested.emit())
        m_set.addAction(a_pinhk)
        a_lang = QAction(
            f"{t('语言…')}  [{language_label(LANG.preference)}]", self
        )
        a_lang.triggered.connect(lambda _checked=False: self.language_requested.emit())
        m_set.addAction(a_lang)
        m_smooth = m_set.addMenu(t("画笔平滑度"))
        self._menus["pen_smooth"] = m_smooth
        smooth_group = QActionGroup(self)
        smooth_group.setExclusive(True)
        for level in PEN_SMOOTH_LEVELS:
            a = QAction(t(PEN_SMOOTH_LABELS[level]), self, checkable=True)
            a.setActionGroup(smooth_group)
            a.triggered.connect(
                lambda _checked=False, lv=level: self._on_pen_smooth(lv)
            )
            m_smooth.addAction(a)
            self._pen_smooth_actions[level] = a
        self._actions.update(hotkey=a_hk, pin_hotkey=a_pinhk, language=a_lang)

        m_help = QMenu(t("帮助(&H)"), self)
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

    # v39：悬浮条已移除，命令面板即主窗口本体。

    def _on_mode_click(self, mode: str) -> None:
        """左半边：立刻用这种方式截图，不改默认方式（老习惯按一下就走）。"""
        self.capture_requested.emit(mode)

    def _on_mode_pick(self, mode: str) -> None:
        """右半边窄条：只把它设为默认方式——不截图、面板不关。"""
        self.set_mode(mode)
        self.mode_changed.emit(mode)

    def _on_quick_mode(self, mode: str) -> None:
        """兼容旧调用：等同「设为默认 + 立刻截图」。"""
        self._on_mode_pick(mode)
        self._on_mode_click(mode)

    def toggle_panel(self) -> None:
        """兼容旧调用：命令面板就是主窗口，显示 / 激活它。"""
        if self.isHidden():
            self.show()
        self.raise_()
        self.activateWindow()

    def hide_panel(self) -> None:
        """兼容旧调用：面板不再单独收起，最小化到托盘。"""
        self._minimize_to_tray()

    # ------------------------------------------------------------ 定位
    def _drag_by(self, delta: QPoint) -> None:
        self.move(self.pos() + delta)

    def _place_default(self) -> None:
        """默认在屏幕中央显示（v39 起不再贴屏幕底部）。"""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        self.adjustSize()
        w, h = self.width(), self.height()
        self.move(avail.left() + max(0, (avail.width() - w) // 2),
                  avail.top() + max(0, (avail.height() - h) // 2))

    def showEvent(self, ev) -> None:  # noqa: N802
        if not self._placed:
            self._placed = True
            self._place_default()
        super().showEvent(ev)

    # ------------------------------------------------------------ 状态刷新
    def _on_mode_combo(self, idx: int) -> None:
        # 兼容旧接口（面板里已不再使用下拉框）
        if isinstance(idx, str):
            self.mode_changed.emit(idx)

    def _sync_quick(self) -> None:
        for mode, row in self._quick.items():
            row.set_highlight(mode == self._mode)
        if hasattr(self, "_panel"):
            self._panel.sync_default(self._mode)

    def set_pen_smooth(self, level: str) -> None:
        if level not in PEN_SMOOTH_LEVELS:
            level = "medium"
        self._pen_smooth = level
        a = self._pen_smooth_actions.get(level)
        if a is not None:
            a.setChecked(True)

    def _on_pen_smooth(self, level: str) -> None:
        self._pen_smooth = level
        self.pen_smooth_changed.emit(level)

    def set_hotkey(self, hk: Hotkey) -> None:
        self._hotkey = hk
        self.hotkey_label.setText(hk.label())
        if hasattr(self, "_panel"):
            self._panel._hk_row.set_texts(
                t("截图热键"), t("点击修改，立即生效"), hk.label()
            )

    def set_pin_hotkey(self, hk: Hotkey) -> None:
        self._pin_hotkey = hk

    def set_mode(self, mode: str) -> None:
        if mode not in CAPTURE_MODES:
            mode = "rect"
        self._mode = mode
        self._sync_quick()

    def set_save_dir(self, path: Path) -> None:
        self._save_dir = Path(path)

    def _minimize_to_tray(self) -> None:
        self.hide()
        self.minimize_requested.emit()

    # ------------------------------------------------------------ v52 Tab
    def switch_tab(self, which: str) -> None:
        """切换「截图 / 录屏」页。which: shot / record。"""
        self._current_tab = "record" if which == "record" else "shot"
        self._stack.setCurrentIndex(1 if self._current_tab == "record" else 0)
        self._apply_tab_style()
        self.adjustSize()

    def current_tab(self) -> str:
        return getattr(self, "_current_tab", "shot")

    def record_panel(self) -> RecordPanel:
        return self._record_panel

    def _apply_tab_style(self) -> None:
        """Tab 选中态：橙色实底白字，未选中浅灰底深字。"""
        rec_active = self._current_tab == "record"

        def style(on: bool) -> str:
            bg = ORANGE if on else SOFT
            fg = "#ffffff" if on else INK2
            weight = 700 if on else 400
            return (
                f"QPushButton{{border:none;border-radius:15px;background:{bg};"
                f"color:{fg};font-size:12px;font-weight:{weight};{FONT_QSS}}}"
            )

        self._tab_shot.setStyleSheet(style(not rec_active))
        self._tab_rec.setStyleSheet(style(rec_active))

    # ------------------------------------------------------------ 语言刷新
    def retranslate_ui(self, _code: str = "") -> None:
        self.setWindowTitle(app_name())
        for key, text_key in (
            ("file", "文件(&F)"), ("shot", "截图(&S)"),
            ("settings", "设置(&E)"), ("help", "帮助(&H)"),
        ):
            self._menus[key].setTitle(t(text_key))
        for key, text_key in (
            ("dir", "打开保存目录"), ("minimize", "最小化到托盘"),
            ("quit", "退出"), ("hotkey", "设置热键…"),
            ("pin_hotkey", "设置贴图热键…"),
            ("help_help", "使用说明…"), ("help_cli", "命令行参数…"),
            ("about", "关于…"), ("long_capture", "滚动长截图…"),
        ):
            self._actions[key].setText(t(text_key))
        for mode in CAPTURE_MODES:
            self._actions[f"shot_{mode}"].setText(mode_label(mode))
        self._actions["language"].setText(
            f"{t('语言…')}  [{language_label(LANG.preference)}]"
        )
        if "pen_smooth" in self._menus:
            self._menus["pen_smooth"].setTitle(t("画笔平滑度"))
            for level, a in self._pen_smooth_actions.items():
                a.setText(t(PEN_SMOOTH_LABELS[level]))
        self.set_hotkey(self._hotkey)
        self._panel.retranslate_ui()
        if hasattr(self, "_record_panel"):
            self._tab_shot.setText(t("截图") + "   " + self._hotkey.label())
            self._tab_rec.setText(t("录屏") + "   F9")
            self._record_panel.retranslate_ui()
        self.adjustSize()

    # ------------------------------------------------------------ 右键 / 关闭
    def contextMenuEvent(self, ev) -> None:  # noqa: N802
        m = QMenu(self)
        m.addAction(self._actions["help_help"])
        m.addAction(self._actions["dir"])
        m.addSeparator()
        m.addAction(self._actions["minimize"])
        m.addAction(self._actions["quit"])
        m.exec(ev.globalPos())

    def closeEvent(self, ev) -> None:  # noqa: N802
        if self._allow_close:
            ev.accept()
            return
        ev.ignore()
        self._minimize_to_tray()


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
