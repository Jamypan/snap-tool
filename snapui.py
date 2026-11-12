# -*- coding: utf-8 -*-
"""
snapui.py —— 程序主窗口、帮助说明、关于对话框、托盘图标。

只依赖 PySide6 与 hotkeys，不反向 import snap.py / snapeditor.py，
因此可单独离屏实例化做自检。主窗口只发信号，具体流程由 App 编排。
"""
from __future__ import annotations

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

from hotkeys import CAPTURE_MODES, MODE_LABELS, Hotkey

APP_NAME = "截屏助手"

MODE_DESC = {
    "rect": "拖动鼠标框选任意区域",
    "window": "移动鼠标点选一个窗口",
    "fullscreen": "整个屏幕（含多显示器）",
}


def make_icon() -> QIcon:
    """代码画一个相机图标，避免依赖外部 ico 文件（便于绿色版分发）。"""
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
三种模式确定选区后都进入同一个编辑器，标注、取字、复制、保存的用法完全一致。</p>

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
<tr><td>修改标注</td><td>点选标注后弹出样式面板，可改线条颜色/粗细/线型、文字颜色/字号/加粗/背景色、填充色、画笔端点箭头；按住标注可拖动；双击文字可改内容</td></tr>
<tr><td>箭头</td><td>两端有圆形控制柄，拖动可改长度与方向（可拖过另一端反向）</td></tr>
<tr><td>整图旋转 / 镜像</td><td>菜单「编辑 → 图像变换」：顺时针 90° Ctrl+R、逆时针 90° Ctrl+Shift+R、左右镜像 Ctrl+H、上下镜像 Ctrl+Shift+H；底图与已有标注一起变，Ctrl+Z 可撤销</td></tr>
<tr><td>画笔端点箭头</td><td>菜单「编辑 → 画笔端点箭头」选「不加 / 只加起点 / 只加终点 / 两端都加」；也可在样式面板勾选。既是新建画笔默认，也作用于选中的那条画笔</td></tr>
<tr><td>撤销</td><td>Ctrl + Z 或工具条「撤销」（整图变换也能撤销）</td></tr>
<tr><td>复制 / 保存 / 取消</td><td>Enter 或工具条「复制」；工具条「保存」；Esc 或工具条「✕」</td></tr>
<tr><td>长截图</td><td>先框选滚动区域，再点工具条「长截图」，滚动中按 Esc 结束</td></tr>
</table>
<p class="hint">旋转 90° 后图片宽高互换，矩形/箭头/画笔/文字等标注位置跟着变换；文字只移动位置、字形仍保持水平可读。导出始终是全分辨率。</p>

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
<p><code>python snap.py --help</code> 查看全部参数；<code>--shot</code> 启动后立即截一次图。
图形界面里也可以点「帮助 → 命令行参数」。</p>

<h2>8. 常见问题</h2>
<ul>
<li><b>按热键没反应：</b>多半是热键被别的程序占用。托盘会弹注册失败提示，去「设置热键…」换一个组合；也可以直接点主窗口的截图按钮。</li>
<li><b>改了代码没变化：</b>程序是单实例 + 托盘常驻，旧进程仍在跑旧代码，需要退出托盘再重新启动。</li>
<li><b>高分屏坐标不准：</b>程序已开启 per-monitor DPI 感知；若仍偏移，重启程序后再试。</li>
<li><b>杀软误报：</b>全局热键 + 屏幕捕获容易被误报，未签名的 exe 需要加入信任。</li>
</ul>
</body></html>
"""

CLI_HELP = f"""{APP_NAME} —— 命令行参数

  python snap.py              正常启动：显示主窗口 + 托盘常驻
  python snap.py --shot       启动后立即截一次图（使用默认截图模式）
  python snap.py --selftest   只跑后端自检，不进入界面
                              结果写入 %APPDATA%\\SnapTool\\selftest.log
  python snap.py --help       显示本说明（也可写 -h 或 /?）

日常使用请双击 run-silent.bat（无黑窗口）。程序是单实例，
重复启动只会提示「已经在运行」。

三种截图模式：框选（拖鼠标选区域）、窗口（悬停高亮并单击）、全屏（自动选中整个虚拟屏幕）。
默认模式与全局热键保存在 %APPDATA%\\SnapTool\\settings.json，
可在主窗口或托盘菜单「设置热键…」里修改。

更多说明见程序内「帮助 → 使用说明」，或项目 README.md。
"""

ABOUT_HTML = f"""
<p style="font-size:16px;"><b>{APP_NAME}</b></p>
<p>一个模仿微信截屏体验的 Windows 桌面截图工具。<b>纯原创实现，与微信无关</b>，不涉及任何逆向。</p>
<p>功能：三种截图模式、对象化标注编辑、整图旋转 / 镜像、画笔端点箭头、滚动长截图、中文 OCR 逐行盖回取字、全局热键自定义。</p>
<p class="hint">技术栈：Python 3.13 + PySide6 + Win32 API + RapidOCR (ONNX Runtime)。<br>
第三方组件许可：PySide6 (LGPL)、RapidOCR / PaddleOCR / OpenCV (Apache-2.0)、ONNX Runtime (MIT)。</p>
"""


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """启动即显示的程序窗口：菜单、模式按钮、热键与默认模式。"""

    capture_requested = Signal(str)      # rect / window / fullscreen
    mode_changed = Signal(str)           # 用户改了「默认模式」
    hotkey_requested = Signal()
    help_requested = Signal(str)         # help / cli
    about_requested = Signal()
    open_dir_requested = Signal()
    minimize_requested = Signal()
    quit_requested = Signal()

    STYLE = (
        "QMainWindow, QWidget#central { background:#f7f8fa; }"
        "QFrame#card { background:#ffffff; border:1px solid #e5e7eb; border-radius:8px; }"
        "QPushButton#mode { background:#ffffff; border:1px solid #d1d5db; border-radius:8px;"
        " padding:14px 6px; color:#111827; font-size:13px; }"
        "QPushButton#mode:hover { border-color:#0a84ff; background:#f0f7ff; }"
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
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumWidth(540)
        self.resize(620, 470)
        self.setStyleSheet(self.STYLE)
        self._build_menu()
        self._build_body(save_dir)
        self.set_hotkey(hotkey)
        self.set_mode(mode)

    def _build_menu(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("文件(&F)")
        a_dir = QAction("打开保存目录", self)
        a_dir.triggered.connect(lambda _checked=False: self.open_dir_requested.emit())
        m_file.addAction(a_dir)
        a_min = QAction("最小化到托盘", self)
        a_min.triggered.connect(lambda _checked=False: self._minimize_to_tray())
        m_file.addAction(a_min)
        m_file.addSeparator()
        a_quit = QAction("退出", self)
        a_quit.triggered.connect(lambda _checked=False: self.quit_requested.emit())
        m_file.addAction(a_quit)

        m_shot = mb.addMenu("截图(&S)")
        for mode in CAPTURE_MODES:
            a = QAction(MODE_LABELS[mode], self)
            a.triggered.connect(
                lambda _checked=False, m=mode: self.capture_requested.emit(m)
            )
            m_shot.addAction(a)

        m_set = mb.addMenu("设置(&E)")
        a_hk = QAction("设置热键…", self)
        a_hk.triggered.connect(lambda _checked=False: self.hotkey_requested.emit())
        m_set.addAction(a_hk)

        m_help = mb.addMenu("帮助(&H)")
        for text, topic in (("使用说明…", "help"), ("命令行参数…", "cli")):
            a = QAction(text, self)
            a.triggered.connect(
                lambda _checked=False, t=topic: self.help_requested.emit(t)
            )
            m_help.addAction(a)
        m_help.addSeparator()
        a_about = QAction("关于…", self)
        a_about.triggered.connect(lambda _checked=False: self.about_requested.emit())
        m_help.addAction(a_about)

    def _build_body(self, save_dir: Path) -> None:
        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 18, 24, 16)
        root.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size:22px; font-weight:bold; color:#111827;")
        root.addWidget(title)
        sub = QLabel("程序已启动 · 托盘常驻 · 关闭本窗口只会最小化到托盘，不会退出程序")
        sub.setObjectName("sub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self.hotkey_label = QLabel("")
        b_change = QPushButton("更改…")
        b_change.setObjectName("minor")
        b_change.clicked.connect(lambda _checked=False: self.hotkey_requested.emit())
        self.mode_combo = QComboBox()
        for m in CAPTURE_MODES:
            self.mode_combo.addItem(MODE_LABELS[m], m)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo)

        grid.addWidget(QLabel("截图热键"), 0, 0)
        grid.addWidget(self.hotkey_label, 0, 1)
        grid.addWidget(b_change, 0, 2)
        grid.addWidget(QLabel("默认模式"), 1, 0)
        grid.addWidget(self.mode_combo, 1, 1)
        hint = QLabel("热键与托盘「截图」使用此模式")
        hint.setObjectName("hint")
        grid.addWidget(hint, 1, 2)
        root.addWidget(card)

        root.addWidget(QLabel("立即截图"))
        row = QHBoxLayout()
        row.setSpacing(10)
        for mode in CAPTURE_MODES:
            b = QPushButton(f"{MODE_LABELS[mode]}\n{MODE_DESC[mode]}")
            b.setObjectName("mode")
            b.setMinimumHeight(76)
            b.clicked.connect(
                lambda _checked=False, m=mode: self.capture_requested.emit(m)
            )
            row.addWidget(b)
        root.addLayout(row)

        tip = QLabel(
            "提示：截图中按 Esc 取消；选区确定后可标注、取字、复制或保存。"
            " 详细说明见「帮助 → 使用说明」。"
        )
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        root.addWidget(tip)
        root.addStretch(1)

        self.setCentralWidget(central)
        self.set_save_dir(save_dir)

    def _on_mode_combo(self, idx: int) -> None:
        mode = self.mode_combo.itemData(idx)
        if isinstance(mode, str):
            self.mode_changed.emit(mode)

    # ------------------------------------------------------------ 对外更新
    def set_hotkey(self, hk: Hotkey) -> None:
        self.hotkey_label.setText(f"<b>{hk.label()}</b>")

    def set_mode(self, mode: str) -> None:
        idx = self.mode_combo.findData(mode)
        if idx < 0 or idx == self.mode_combo.currentIndex():
            return
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)

    def set_save_dir(self, path: Path) -> None:
        self.statusBar().showMessage(f"保存目录：{path}")

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
        self.setWindowTitle(f"{APP_NAME} - 使用说明")
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        lay.addWidget(self.browser, 1)
        row = QHBoxLayout()
        b_close = QPushButton("关闭")
        b_close.clicked.connect(lambda _checked=False: self.close())
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.show_topic(topic)

    def show_topic(self, topic: str) -> None:
        self.browser.setHtml(HELP_HTML if topic != "cli" else CLI_HELP_HTML)
        self.browser.moveCursor(QTextCursor.Start)
        self.setWindowTitle(
            f"{APP_NAME} - {'命令行参数' if topic == 'cli' else '使用说明'}"
        )


CLI_HELP_HTML = "<html><body style=\"font-family:'Microsoft YaHei';font-size:13px;\">" \
    "<h2>命令行参数</h2><pre style=\"font-family:Consolas,'Microsoft YaHei';font-size:13px;\">" \
    + CLI_HELP.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") \
    + "</pre></body></html>"
