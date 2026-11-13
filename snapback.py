# -*- coding: utf-8 -*-
"""
snapback.py —— 后端能力层：屏幕捕获 / 滚动长截图拼接 / OCR。

本模块不依赖 Qt，可单独导入和测试。
"""
from __future__ import annotations

import ctypes
import io
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageGrab

# ---------------------------------------------------------------------------
# Win32 常量
# ---------------------------------------------------------------------------
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

INPUT_MOUSE = 0
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
WHEEL_DELTA = 120

VK_ESCAPE = 0x1B

user32 = ctypes.windll.user32 if sys.platform == "win32" else None


def _t(key: str, **kwargs) -> str:
    """后端异常文案的多语言入口（延迟导入，保持本模块无顶层 Qt 依赖）。"""
    try:
        from i18n import t
        return t(key, **kwargs)
    except Exception:  # noqa: BLE001
        return key.format(**kwargs) if kwargs else key


# ---------------------------------------------------------------------------
# DPI 感知
# ---------------------------------------------------------------------------
def set_dpi_awareness() -> str:
    """必须在创建任何窗口之前调用，否则高分屏下截图会模糊、坐标会错位。"""
    if sys.platform != "win32":
        return "not-win32"
    # 2 = PROCESS_PER_MONITOR_DPI_AWARE
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "per-monitor"
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "system"
    except Exception:
        return "failed"


# ---------------------------------------------------------------------------
# 虚拟屏幕（支持多显示器，坐标可能为负）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScreenRect:
    x: int
    y: int
    w: int
    h: int

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


def virtual_screen() -> ScreenRect:
    """返回覆盖所有显示器的虚拟屏幕矩形。"""
    if user32 is None:
        return ScreenRect(0, 0, 1920, 1080)
    return ScreenRect(
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


# ---------------------------------------------------------------------------
# 窗口探测（「窗口截图」模式用，坐标均为物理像素）
# ---------------------------------------------------------------------------
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


@dataclass(frozen=True)
class WindowInfo:
    rect: ScreenRect
    title: str
    hwnd: int


def _visible_frame(hwnd: int) -> ScreenRect | None:
    """优先用 DWM 可见边框（不含 Win10/11 的透明阴影），失败退回 GetWindowRect。"""
    r = _RECT()
    try:
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(r), ctypes.sizeof(r),
        )
        if hr == 0 and r.right > r.left and r.bottom > r.top:
            return ScreenRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
    except Exception:  # noqa: BLE001
        pass
    if user32 is not None and user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
        if r.right > r.left and r.bottom > r.top:
            return ScreenRect(r.left, r.top, r.right - r.left, r.bottom - r.top)
    return None


def window_rect_at(x: int, y: int, exclude_pid: int | None = None) -> WindowInfo | None:
    """返回鼠标位置下最贴合的顶层窗口。

    EnumWindows 按 Z 序枚举，过滤掉不可见 / 最小化 / cloaked / 工具窗口 /
    本进程自己的窗口；在包含该点的候选里取面积最小的一个，这样不会误选
    覆盖整屏的透明浮层或桌面。返回物理像素矩形（已去掉窗口阴影）。
    """
    if user32 is None:
        return None
    import os

    if exclude_pid is None:
        exclude_pid = os.getpid()
    found: list[WindowInfo] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam) -> bool:
        try:
            h = int(hwnd or 0)
            if not h or not user32.IsWindowVisible(wintypes.HWND(h)):
                return True
            if user32.IsIconic(wintypes.HWND(h)):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(wintypes.HWND(h), ctypes.byref(pid))
            if pid.value == exclude_pid:
                return True
            cloaked = wintypes.DWORD()
            try:
                if (
                    ctypes.windll.dwmapi.DwmGetWindowAttribute(
                        wintypes.HWND(h), DWMWA_CLOAKED,
                        ctypes.byref(cloaked), ctypes.sizeof(cloaked),
                    ) == 0 and cloaked.value
                ):
                    return True
            except Exception:  # noqa: BLE001
                pass
            if user32.GetWindowLongW(wintypes.HWND(h), GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            r = _visible_frame(h)
            if r is None or r.w < 60 or r.h < 40:
                return True
            if not (r.x <= x < r.x + r.w and r.y <= y < r.y + r.h):
                return True
            n = user32.GetWindowTextLengthW(wintypes.HWND(h))
            buf = ctypes.create_unicode_buffer(max(1, n + 1))
            user32.GetWindowTextW(wintypes.HWND(h), buf, len(buf))
            found.append(WindowInfo(r, buf.value, h))
        except Exception:  # noqa: BLE001
            pass
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    if not found:
        return None
    return min(found, key=lambda w: w.rect.w * w.rect.h)


# ---------------------------------------------------------------------------
# 捕获
# ---------------------------------------------------------------------------
def grab_all_screens() -> Image.Image:
    """抓取整个虚拟桌面（所有显示器拼在一起）。返回 RGB 图像。"""
    r = virtual_screen()
    img = ImageGrab.grab(bbox=r.bbox, all_screens=True)
    return img.convert("RGB")


def grab_region(rect: ScreenRect) -> Image.Image:
    """抓取指定屏幕区域。"""
    return ImageGrab.grab(bbox=rect.bbox, all_screens=True).convert("RGB")


# ---------------------------------------------------------------------------
# 滚轮 / 光标控制
# ---------------------------------------------------------------------------
class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send_mouse_wheel(notches: int) -> None:
    """发送鼠标滚轮事件（正数向上、负数向下）。"""
    if user32 is None:
        return
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.mi.dx = 0
    inp.mi.dy = 0
    inp.mi.mouseData = ctypes.c_ulong(WHEEL_DELTA * notches & 0xFFFFFFFF).value
    inp.mi.dwFlags = MOUSEEVENTF_WHEEL
    inp.mi.time = 0
    inp.mi.dwExtraInfo = None
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def get_cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def is_escape_pressed() -> bool:
    """用于长截图过程中随时中断。"""
    if user32 is None:
        return False
    return bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)


# ---------------------------------------------------------------------------
# 长截图拼接
# ---------------------------------------------------------------------------
def find_vertical_overlap(
    acc: np.ndarray,
    frame: np.ndarray,
    search_rows: int = 400,
    template_rows: int = 120,
) -> tuple[int, float]:
    """
    在已拼接图像 acc 中定位新帧 frame 顶部的匹配位置。

    返回 (match_top_in_acc, score)。score 为归一化相关系数（0~1），越高越可信。
    只有 frame 顶部 template_rows 行能在 acc 尾部 search_rows 行里找到匹配时才有意义。
    """
    import cv2

    if acc.shape[1] != frame.shape[1]:
        raise ValueError(_t("拼接帧宽度必须一致"))

    if acc.shape[0] < template_rows or frame.shape[0] < template_rows:
        return -1, 0.0

    template = frame[0:template_rows]
    search_top = max(0, acc.shape[0] - search_rows)
    search = acc[search_top:]

    if search.shape[0] < template_rows:
        return -1, 0.0

    res = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return search_top + max_loc[1], float(max_val)


def stitch_scroll(
    rect: ScreenRect,
    *,
    max_height: int = 30000,
    min_new_rows: int = 40,
    match_threshold: float = 0.72,
    scroll_notches: int = -3,
    settle_seconds: float = 0.42,
    max_frames: int = 120,
    on_progress=None,
    should_stop=None,
) -> tuple[Image.Image, dict]:
    """
    自动滚动并拼接长截图。

    做法：把光标移到选区中心 → 抓帧 → 滚轮向下 → 再抓帧 →
    用模板匹配算出两帧的重叠量 → 只保留新增的部分拼到画布上。

    停止条件（任一命中）：
      - 连续两帧几乎没有新增内容（到底了）
      - 匹配得分低于阈值（无法对齐，通常是内容重复或页面在动）
      - 高度超过 max_height / 帧数超过 max_frames
      - 外部通过 should_stop() 要求中断（例如用户按了 ESC）

    返回 (拼接结果图, 统计信息 dict)。
    """
    cx = rect.x + rect.w // 2
    cy = rect.y + rect.h // 2
    saved_cursor = get_cursor_pos()
    set_cursor_pos(cx, cy)
    time.sleep(0.12)

    frames: list[np.ndarray] = []
    canvas: np.ndarray | None = None
    stats: dict = {
        "frames": 0,
        "stop_reason": "unknown",
        "score": 0.0,
        "height": 0,
        "cursor_restored": False,
    }

    try:
        for i in range(max_frames):
            if should_stop is not None and should_stop():
                stats["stop_reason"] = "user-interrupt"
                break

            img = grab_region(rect)
            frame = np.array(img)
            frames.append(frame)
            stats["frames"] = i + 1

            if canvas is None:
                canvas = frame.copy()
            else:
                top, score = find_vertical_overlap(canvas, frame)
                stats["score"] = round(score, 4)

                if top < 0 or score < match_threshold:
                    stats["stop_reason"] = (
                        "match-failed" if score < match_threshold else "no-overlap"
                    )
                    break

                # 新帧顶部对应 canvas 的 top 行；新内容 = 新帧从 (canvas 底 - top) 行开始
                new_start = canvas.shape[0] - top
                if new_start <= 0:
                    stats["stop_reason"] = "no-new-content"
                    break
                if new_start < min_new_rows:
                    # 只多出极少像素，认为已到底（再滚也几乎不动）
                    stats["stop_reason"] = "reached-bottom"
                    break

                new_part = frame[new_start:]
                if canvas.shape[0] + new_part.shape[0] > max_height:
                    allow = max(0, max_height - canvas.shape[0])
                    if allow <= 0:
                        stats["stop_reason"] = "max-height"
                        break
                    new_part = new_part[:allow]
                    canvas = np.vstack([canvas, new_part])
                    stats["stop_reason"] = "max-height"
                    break

                canvas = np.vstack([canvas, new_part])

            stats["height"] = int(canvas.shape[0])
            if on_progress is not None:
                on_progress(stats["frames"], stats["height"], canvas)

            if canvas.shape[0] >= max_height:
                stats["stop_reason"] = "max-height"
                break

            _send_mouse_wheel(scroll_notches)
            time.sleep(settle_seconds)
        else:
            stats["stop_reason"] = "max-frames"

        if canvas is None:
            canvas = np.array(grab_region(rect))

        stats["height"] = int(canvas.shape[0])
        return Image.fromarray(canvas), stats

    finally:
        set_cursor_pos(*saved_cursor)
        stats["cursor_restored"] = True


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
class OcrUnavailable(RuntimeError):
    pass


def _line(text: str, box=None, score: float = 0.0) -> dict:
    """OCR 行的统一结构。

    box 为 (x1, y1, x2, y2)，单位是**输入图像的像素坐标**；
    没有位置信息的后端填 None（前端会自动降级成整块文本面板）。
    """
    return {"text": str(text), "box": box, "score": float(score)}


def _box_from_points(points) -> tuple[float, float, float, float] | None:
    """把 N×2 顶点数组换成外接矩形 (x1,y1,x2,y2)。"""
    try:
        arr = np.asarray(points, dtype=float).reshape(-1, 2)
        if arr.size == 0:
            return None
        x1, y1 = arr.min(axis=0)
        x2, y2 = arr.max(axis=0)
        return (float(x1), float(y1), float(x2), float(y2))
    except Exception:  # noqa: BLE001
        return None


def _clean_windows_text(text: str) -> str:
    """Windows OCR 按「字」切词会在汉字间插空格，只合并 CJK 之间的空白。

    故意不动英文单词 / 数字之间的空格：截图里可能是表格的两个单元格，
    无脑粘连会把「480 160」错拼成「480160」。
    """
    import re

    cjk = r"\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef"
    return re.sub(rf"(?<=[{cjk}])[ \t]+(?=[{cjk}])", "", text)


def _ocr_windows_lines(img: Image.Image) -> list[dict]:
    """使用 Windows 内置 OCR 引擎（Windows.Media.Ocr），按行带包围框。"""
    import asyncio

    try:
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    except ImportError as exc:  # pragma: no cover
        raise OcrUnavailable(_t("未安装 winrt 包（Windows OCR 绑定）")) from exc

    async def _run() -> list[dict]:
        # 明确优先中文引擎：英文系统上 try_create_from_user_profile_languages()
        # 会拿到 en-US，中文识别会退化甚至返回空。
        engine = None
        try:
            engine = OcrEngine.try_create_from_language(Language("zh-Hans-CN"))
        except Exception:  # noqa: BLE001
            engine = None
        if engine is None:
            engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise OcrUnavailable(_t("系统未安装可用的 OCR 语言包（需 zh-CN OCR 语言包）"))

        # Windows OCR 对输入图有最大边长限制，4K / 多显示器全屏截图会直接失败；
        # 超限先缩放，识别完再把行框坐标乘回原图尺度（否则「盖回原位」会整体偏移）。
        max_dim = 0
        for attr in ("max_image_dimension", "MaxImageDimension"):
            try:
                val = getattr(engine, attr, 0)
                max_dim = int(val) if val else 0
            except Exception:  # noqa: BLE001
                max_dim = 0
            if max_dim:
                break
        w, h = img.size
        scale = 1.0
        work = img
        if max_dim and max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            work = img.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
            )

        buf = io.BytesIO()
        work.convert("RGB").save(buf, format="BMP")
        raw = buf.getvalue()

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream.get_output_stream_at(0))
        writer.write_bytes(raw)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        lines: list[dict] = []
        for ln in result.lines:
            box = None
            try:
                rects = [
                    (
                        float(w.bounding_rect.x),
                        float(w.bounding_rect.y),
                        float(w.bounding_rect.x + w.bounding_rect.width),
                        float(w.bounding_rect.y + w.bounding_rect.height),
                    )
                    for w in ln.words
                ]
                if rects:
                    box = (
                        min(r[0] for r in rects),
                        min(r[1] for r in rects),
                        max(r[2] for r in rects),
                        max(r[3] for r in rects),
                    )
            except Exception:  # noqa: BLE001
                box = None
            if box is not None and scale != 1.0:
                box = tuple(v / scale for v in box)
            lines.append(_line(_clean_windows_text(ln.text), box))
        return lines

    return asyncio.run(_run())


def _ocr_tesseract_lines(img: Image.Image) -> list[dict]:
    """Tesseract 兜底：image_to_data 按 (block, par, line) 聚合出带框的行。"""
    import pytesseract

    data = pytesseract.image_to_data(
        img, lang="chi_sim+eng", output_type=pytesseract.Output.DICT
    )
    groups: dict[tuple, dict] = {}
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not txt or conf < 0:
            continue
        key = (
            data["page_num"][i], data["block_num"][i],
            data["par_num"][i], data["line_num"][i],
        )
        x = int(data["left"][i])
        y = int(data["top"][i])
        x2 = x + int(data["width"][i])
        y2 = y + int(data["height"][i])
        g = groups.setdefault(key, {"parts": [], "box": [x, y, x2, y2]})
        g["parts"].append((x, txt))
        b = g["box"]
        b[0], b[1] = min(b[0], x), min(b[1], y)
        b[2], b[3] = max(b[2], x2), max(b[3], y2)

    out: list[dict] = []
    for key in sorted(groups):
        g = groups[key]
        txt = " ".join(t for _, t in sorted(g["parts"]))
        out.append(_line(txt, tuple(g["box"])))
    return out


# ---------------------------------------------------------------------------
# RapidOCR 后端（默认首选：PP-OCR 模型的 ONNX 版，轻量、中文效果好）
# ---------------------------------------------------------------------------
_rapid_engine = None  # 单例缓存：首次推理要加载 3 个 ONNX 模型


def _get_rapid_engine():
    """懒加载 RapidOCR 引擎（单例）。模型随 wheel 自带，不需要联网下载。"""
    global _rapid_engine
    if _rapid_engine is None:
        import io
        import logging
        import sys

        def _silence() -> None:
            # RapidOCR 模块级 logger("RapidOCR") 带一个 StreamHandler，且
            # RapidOCR() 构造时会把 level 重设回 config.yaml 的 INFO。
            # 换掉 handler 可避免无控制台时往 None 写入，也顺手止住 INFO 刷屏。
            for name in ("rapidocr", "RapidOCR", "onnxruntime"):
                lg = logging.getLogger(name)
                lg.setLevel(logging.ERROR)
                for h in list(lg.handlers):
                    lg.removeHandler(h)
                lg.addHandler(logging.NullHandler())
                lg.propagate = False

        # pythonw / --windowed exe 下 sys.stderr 为 None：导入 rapidocr 时
        # StreamHandler() 会绑到 None，临时给个内存流，构造完再还原。
        saved_stderr = getattr(sys, "stderr", None)
        if saved_stderr is None:
            sys.stderr = io.StringIO()
        try:
            _silence()
            from rapidocr import RapidOCR

            _silence()  # import 之后 logger 才被创建
            engine = RapidOCR()
            _silence()  # 构造之后 level 又被改回 INFO
        finally:
            sys.stderr = saved_stderr

        _rapid_engine = engine
    return _rapid_engine


def _ocr_rapid_lines(img: Image.Image) -> list[dict]:
    """RapidOCR 中文（+英文）识别，返回带行框与置信度的行列表。

    rapidocr 3.x 的 RapidOCROutput 提供 boxes(N×2 四点) / txts / scores，
    坐标已映射回输入图像像素尺度，可直接用于「逐行盖回原文位置」。
    """
    engine = _get_rapid_engine()
    arr = np.array(img.convert("RGB"))
    out = engine(arr)
    if out is None:
        return []
    boxes = getattr(out, "boxes", None)
    texts = getattr(out, "txts", None)
    scores = getattr(out, "scores", None)
    if boxes is None or texts is None:
        return []
    lines: list[dict] = []
    for i, text in enumerate(texts):
        if not text:
            continue
        box = None
        try:
            if i < len(boxes):
                box = _box_from_points(boxes[i])
        except Exception:  # noqa: BLE001
            box = None
        score = 0.0
        try:
            if scores is not None and i < len(scores):
                score = float(scores[i])
        except Exception:  # noqa: BLE001
            pass
        lines.append(_line(str(text), box, score))
    return lines


# ---------------------------------------------------------------------------
# PaddleOCR 后端（离线中文识别，方案 B）
# ---------------------------------------------------------------------------
_paddle_engine = None  # 单例缓存，避免每次取字都重新初始化（约 1~2 秒）


def _get_paddle_engine():
    """懒加载 PaddleOCR 引擎（单例）。首次调用会初始化并可能下载模型。"""
    global _paddle_engine
    if _paddle_engine is None:
        import logging

        from paddleocr import PaddleOCR

        # 静默 paddlex / paddle 的初始化日志，避免取字时刷屏
        for name in ("paddleocr", "paddlex", "ppocr"):
            logging.getLogger(name).setLevel(logging.ERROR)

        # enable_mkldnn=False 是关键：PaddlePaddle 3.x 的 oneDNN 后端在
        # 文本检测模型上有个未实现 bug，会抛 NotImplementedError。
        _paddle_engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
            cpu_threads=4,
        )
    return _paddle_engine


def _ocr_paddle_lines(img: Image.Image) -> list[dict]:
    """PaddleOCR 中文（+英文）识别，返回带 rec_boxes 坐标的行列表。

    PaddleOCR 3.x 的 predict 结果里 rec_texts / rec_scores / rec_polys /
    rec_boxes 是一一对应的；坐标已映射回输入图像像素尺度，可直接盖回原图。
    """
    engine = _get_paddle_engine()
    # predict 只接受 numpy.ndarray 或文件路径（str），不接受 bytes
    arr = np.array(img.convert("RGB"))
    result = engine.predict(arr)
    lines: list[dict] = []
    for r in result:
        texts = list(r.get("rec_texts") or [])
        scores = list(r.get("rec_scores") or [])
        polys = list(r.get("rec_polys") or [])
        boxes = r.get("rec_boxes")
        for i, text in enumerate(texts):
            if not text:
                continue
            box = None
            if boxes is not None and i < len(boxes):
                b = np.asarray(boxes[i], dtype=float).reshape(-1)
                if b.size >= 4:
                    box = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            if box is None and i < len(polys):
                box = _box_from_points(polys[i])
            score = float(scores[i]) if i < len(scores) else 0.0
            lines.append(_line(text, box, score))
    return lines


def _fix_box_scale(lines: list[dict], size: tuple[int, int]) -> list[dict]:
    """个别后端返回的是模型内部缩放后的坐标，明显越界时整体缩回原图尺度。"""
    w, h = size
    with_box = [d for d in lines if d.get("box")]
    if not with_box:
        return lines
    max_x = max(d["box"][2] for d in with_box)
    max_y = max(d["box"][3] for d in with_box)
    sx = w / max_x if max_x > w * 1.1 else 1.0
    sy = h / max_y if max_y > h * 1.1 else 1.0
    if sx == 1.0 and sy == 1.0:
        return lines
    for d in with_box:
        x1, y1, x2, y2 = d["box"]
        d["box"] = (x1 * sx, y1 * sy, x2 * sx, y2 * sy)
    return lines


def ocr_image_lines(img: Image.Image) -> tuple[list[dict], str]:
    """
    对图像做文字识别。返回 (行列表, 后端名)。

    行结构见 _line()：text + 原图像素坐标 box(x1,y1,x2,y2) + score。
    后端按可用性依次尝试：RapidOCR（首选，轻量且中文效果好）→ PaddleOCR
    → Windows 内置 OCR → Tesseract。打包成 exe 时 PaddleOCR 通常被排除，
    会自动落到后面的后端，因此 RapidOCR 是发行版的实际主力。
    """
    errors: list[str] = []
    for name, fn in (
        ("rapidocr", _ocr_rapid_lines),
        ("paddleocr", _ocr_paddle_lines),
        ("windows-ocr", _ocr_windows_lines),
        ("tesseract", _ocr_tesseract_lines),
    ):
        try:
            lines = _fix_box_scale(fn(img), img.size)
            return lines, name
        except OcrUnavailable as exc:
            errors.append(f"{name}: {exc}")
        except ImportError as exc:
            errors.append(f"{name}: {_t('缺少依赖 {error}', error=exc)}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    raise OcrUnavailable(" | ".join(errors) or _t("没有可用的 OCR 后端"))


def ocr_image(img: Image.Image) -> tuple[str, str]:
    """兼容入口：只要纯文本（自检脚本等使用），内部仍走带坐标的新链路。"""
    lines, backend = ocr_image_lines(img)
    return "\n".join(d["text"] for d in lines), backend


# ---------------------------------------------------------------------------
if __name__ == "__main__":  # 简易自检
    set_dpi_awareness()
    r = virtual_screen()
    print(f"虚拟屏幕: x={r.x} y={r.y} {r.w}x{r.h}")
    img = grab_all_screens()
    print(f"捕获成功: {img.size} 模式={img.mode}")
