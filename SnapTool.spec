# -*- mode: python ; coding: utf-8 -*-
"""
SnapTool.spec —— 截屏助手 Windows 绿色版构建配置

构建：  pyinstaller --noconfirm --clean SnapTool.spec
产物：  dist/SnapTool/SnapTool.exe（整个目录一起分发，不要只拷 exe）
验证：  SnapTool.exe --selftest  →  结果写到 %APPDATA%\\SnapTool\\selftest.log

要点：
  * RapidOCR 的 PP-OCRv6 ONNX 模型随 wheel 自带，用 collect_all 收进
    _internal，用户不需要联网下载，也不依赖系统中文 OCR 语言包。
  * 明确排除 PaddlePaddle 全家桶（380MB+）：snapback.py 里那条
    PaddleOCR 降级分支是函数内懒加载，静态分析仍会把它拖进产物。
    排除后发行版实际链路是 RapidOCR → Windows 内置 OCR → Tesseract。
  * upx=False：onnxruntime / OpenCV 的 DLL 被 UPX 压缩后容易加载失败。
  * v52 录屏：mss / soundcard / imageio_ffmpeg 整包收集，ffmpeg.exe 随包分发
    （用户要求依赖打进 exe，发行目录因此增加约 85MB）。
  * v25 体积优化：collect_all 之后按路径过滤 Qt 冗余插件 / 示例模型 /
    包元数据 / 未使用的扩展。3 个 OCR 模型、cv2.pyd、Qt6Core/Gui/Widgets、
    OpenSSL 运行库一律保留，功能不变。optimize 保持 0（numpy 需要 docstring）。
"""
from PyInstaller.utils.hooks import collect_all

# ---- 数据 / 二进制 / 隐藏导入 ----------------------------------------------
datas = [
    ('ocr_test.png', '.'),                  # --selftest 用的冒烟测试图
    ('app.ico', '.'),                       # 运行时窗口 / 托盘图标（make_icon 读取）
    ('assets/avatar-pan.webp', 'assets'),  # 「关于」对话框里的头像
    # v48：技术栈 / 第三方许可从「关于」界面移出，改为随包附带的文本文件
    ('THIRD-PARTY-LICENSES.txt', '.'),
]
binaries = []
hiddenimports = []

# v52 录屏：mss / soundcard / imageio_ffmpeg 带平台后端与 ffmpeg.exe，
# 必须整包收集，否则冻结版抓屏或编码会找不到二进制。
for _pkg in ('rapidocr', 'onnxruntime', 'mss', 'soundcard', 'imageio_ffmpeg'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# snapback.py 里有若干函数内懒加载，显式兜底防止静态分析漏收；
# singleinstance.py 是主程序顶层导入的本地模块，显式列出以防打包路径差异
hiddenimports += [
    'singleinstance',
    # 多语言模块（i18n_docs 里有函数内延迟导入，显式列出防漏收）
    'i18n', 'i18n_data', 'i18n_docs',
    # v52 录屏：本地模块 + 录制核心（部分模块在函数内导入，静态分析可能漏收）
    'ui_theme', 'hotkeys',
    # v52.4 原生选择文件夹 / v52.5 录屏光标叠加（延迟导入，显式列出防漏收）
    'folder_picker', 'cursor_overlay',
    # v52.6 剪贴板写图（snap.py / pinwindow.py 顶层导入，显式列出防漏收）
    'clipboard_image',
    'recording_settings', 'recording_ui', 'recording_flow',
    'recorder', 'recorder.video', 'recorder.audio',
    'recorder.devices', 'recorder.runlog',
    'mss', 'mss.windows',
    'soundcard', 'imageio_ffmpeg',
    'rapidocr',
    'onnxruntime',
    'cv2',
    'pyclipper',
    'shapely',
    'omegaconf',
    'yaml',
    'PIL.Image',
]

# ---- 明确排除（体积控制） ---------------------------------------------------
excludes = [
    # PaddleOCR 全家桶：源码保留降级分支，发行版用 RapidOCR 即可
    'paddle', 'paddleocr', 'paddlex', 'ppocr', 'paddlepaddle',
    # 其它重型 / 无关库
    'matplotlib', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2',
    'IPython', 'jupyter', 'notebook', 'torch', 'torchvision', 'tensorflow',
    'scipy', 'sklearn', 'sympy', 'pandas', 'numba', 'llvmlite',
    'pytest', 'sphinx', 'setuptools', 'pip', 'wx', 'plotly', 'bokeh', 'seaborn',
]

a = Analysis(
    ['snap.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    # 保持 optimize=0：试过 2（-OO 去掉 docstring），numpy 的
    # _core/overrides.py 用 add_docstring 装饰函数，docstring 变 None 后
    # 冻结版启动直接 TypeError: argument docstring should be a str。
    # 源码自身没有 assert，但第三方库依赖 docstring，不能开 -OO。
    optimize=0,
)

# ---- 剔除用不到的大体积组件 -------------------------------------------------
# 本工具只用 QtWidgets 做 2D 绘制、只用 cv2 做长截图模板匹配，不碰视频编码 /
# QML / PDF / OpenGL / 虚拟键盘 / 网络 / SVG / AVIF，也不联网。静态分析会把
# 整个 Qt 插件目录和几个间接依赖一起收进来，这里按路径显式过滤。
# 刻意保留：Qt6Network.dll / QtNetwork.pyd（PySide6 包内可能引用）、
# libcrypto / libssl（Python ssl 模块的 C 依赖）、LICENSE / ThirdPartyNotices
# （第三方许可证文本，分发时应当随附）。
def _norm(entry_name):
    return str(entry_name).replace('\\', '/').lower()


_drop_binaries = (
    # --- 既有：视频编码 / 软件 OpenGL ---
    'opencv_videoio_ffmpeg',     # cv2 的两份 ffmpeg DLL，约 56MB
    'opengl32sw.dll',            # Qt 软件 OpenGL 后备，约 20MB
    # --- Qt 模块本体：只用 Core / Gui / Widgets ---
    # 用短子串，避免 'qt6qml.dll' 漏掉 Qt6QmlMeta / Models / WorkerScript
    'qt6quick', 'qt6qml', 'qt6pdf',
    'qt6virtualkeyboard', 'qt6opengl', 'qt6svg',
    # --- Qt 插件：平台只留 qwindows；图片只留 ico / jpeg / webp（PNG 内置）---
    'plugins/platforms/qdirect2d', 'plugins/platforms/qminimal',
    'plugins/platforms/qoffscreen',
    'plugins/imageformats/qgif', 'plugins/imageformats/qicns',
    'plugins/imageformats/qtga', 'plugins/imageformats/qtiff',
    'plugins/imageformats/qwbmp', 'plugins/imageformats/qpdf',
    'plugins/imageformats/qsvg', 'plugins/iconengines/qsvgicon',
    'plugins/tls/', 'plugins/networkinformation/', 'plugins/generic/',
    'qtvirtualkeyboardplugin',
    # --- 间接依赖里用不到的大体积扩展 ---
    'pil/_avif',                              # Pillow AVIF 插件，程序只读写 PNG/JPG/WEBP/ICO
    'cryptography/hazmat/bindings/_rust',     # 离线程序不用 TLS / 证书
)
a.binaries = [
    entry for entry in a.binaries
    if not any(key in _norm(entry[0]) for key in _drop_binaries)
]

# 数据文件：示例模型 / 包元数据 / 类型标注 / 编码检测语料都不是运行时需要。
# rapidocr/models 下的 3 个 PP-OCR 模型、ocr_test.png、app.ico、头像一律保留。
_drop_datas = (
    'pyside6/translations/',
    'onnxruntime/datasets/',       # 3 个 onnxruntime 自带示例模型，不是 OCR 模型
    'onnxruntime/tools/',
    'onnxruntime/transformers/',
    'onnxruntime/quantization/',
    '.dist-info/',
    '/py.typed',
    '.pyi',
    'chardet/models/',             # requests 链的编码检测语料
    'certifi/cacert.pem',          # 程序不联网
)
a.datas = [
    entry for entry in a.datas
    if not any(key in _norm(entry[0]) for key in _drop_datas)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SnapTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SnapTool',
)

# ---- 许可声明额外在发行目录根部放一份 -------------------------------------
# PyInstaller 6 会把 datas 一律塞进 _internal/，普通用户解压后看不到。
# LGPL 要求分发时给出显著通知，所以最外层再复制一份，双击即可打开。
import os as _os
import shutil as _shutil

_dst = _os.path.join(DISTPATH, 'SnapTool')
if _os.path.isdir(_dst):
    _shutil.copy('THIRD-PARTY-LICENSES.txt', _dst)

