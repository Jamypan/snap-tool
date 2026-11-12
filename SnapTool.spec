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
"""
from PyInstaller.utils.hooks import collect_all

# ---- 数据 / 二进制 / 隐藏导入 ----------------------------------------------
datas = [('ocr_test.png', '.')]   # --selftest 用的冒烟测试图
binaries = []
hiddenimports = []

for _pkg in ('rapidocr', 'onnxruntime'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# snapback.py 里有若干函数内懒加载，显式兜底防止静态分析漏收
hiddenimports += [
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
    optimize=0,
)

# ---- 剔除用不到的大体积组件（约 80MB） -------------------------------------
# 本工具只用 QtWidgets 做 2D 绘制、只用 cv2 做图像拼接，不碰视频编码 / QML /
# PDF / 软件 OpenGL / Qt 语言包。静态分析会把它们一并收进来，这里显式过滤。
def _norm(entry_name):
    return str(entry_name).replace('\\', '/').lower()


_drop_binaries = (
    'opencv_videoio_ffmpeg',     # cv2 的两份 ffmpeg DLL，约 56MB
    'opengl32sw.dll',            # Qt 软件 OpenGL 后备，约 20MB
    'qt6quick.dll', 'qt6qml.dll', 'qt6pdf.dll',
)
a.binaries = [
    entry for entry in a.binaries
    if not any(key in _norm(entry[0]) for key in _drop_binaries)
]
a.datas = [
    entry for entry in a.datas
    if 'pyside6/translations/' not in _norm(entry[0])
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
