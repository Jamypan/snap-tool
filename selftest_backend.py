# -*- coding: utf-8 -*-
"""
selftest_backend.py —— 后端能力验证脚本（不需要 GUI）。

覆盖：
  1. find_vertical_overlap 的定位精度
  2. 长截图拼接逻辑能否无损还原一张长图
  3. OCR 后端是否可用
"""
from __future__ import annotations

import io
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import snapback
from snapback import ScreenRect, find_vertical_overlap

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, PASS if ok else FAIL, detail))
    print(f"[{PASS if ok else FAIL}] {name}  {detail}")


# ---------------------------------------------------------------------------
def make_tall_image(width=600, height=3000) -> Image.Image:
    """造一张有丰富纹理的长图，模拟长网页。"""
    rng = np.random.default_rng(42)
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    # 基础渐变
    grad = np.linspace(0, 255, height, dtype=np.uint8)
    arr[:, :, 0] = grad[:, None]
    arr[:, :, 1] = (255 - grad)[:, None]
    arr[:, :, 2] = 128
    # 叠加随机色块，制造可匹配的纹理
    for _ in range(160):
        y = rng.integers(0, height - 30)
        x = rng.integers(0, width - 60)
        h = rng.integers(12, 40)
        w = rng.integers(20, 80)
        arr[y : y + h, x : x + w] = rng.integers(0, 256, size=3, dtype=np.uint8)
    img = Image.fromarray(arr)
    # 画一些文字行，更接近真实页面
    d = ImageDraw.Draw(img)
    for i in range(0, height, 60):
        d.text((10, i + 5), f"Line {i:04d}  —— 这是用于测试的长图内容", fill=(20, 20, 20))
    return img


def test_overlap_detection() -> None:
    tall = make_tall_image()
    arr = np.array(tall)

    # 场景 1：两帧在屏幕上相隔很远，不该匹配上
    canvas = arr[0:500].copy()
    far_frame = arr[1500:2000]
    top, score = find_vertical_overlap(canvas, far_frame)
    record(
        "overlap: 无关帧应低分",
        score < 0.5,
        f"top={top} score={score:.4f} (期望 score<0.5)",
    )

    # 场景 2：真正的重叠场景，应精确定位
    new_frame = arr[380:880]
    top, score = find_vertical_overlap(canvas, new_frame)
    ok = score > 0.95 and top == 380
    record(
        "overlap: 重叠帧应定位到第 380 行",
        ok,
        f"got top={top} score={score:.4f} (期望 top=380, score>0.95)",
    )


def test_stitch_logic() -> None:
    """复刻 stitch_scroll 的拼接数学，验证能否无损还原。"""
    tall = make_tall_image()
    full = np.array(tall)
    width = full.shape[1]

    frame_rows = 500
    step = 380          # 每帧滚动 380 行，保留 120 行重叠
    min_new_rows = 40
    threshold = 0.72

    # 生成模拟滚动帧序列
    frames = []
    pos = 0
    while pos + frame_rows <= full.shape[0]:
        frames.append(full[pos : pos + frame_rows])
        pos += step
    if pos < full.shape[0]:
        frames.append(full[max(0, full.shape[0] - frame_rows) :])

    canvas = None
    stop_reason = "max-frames"
    for i, frame in enumerate(frames):
        if canvas is None:
            canvas = frame.copy()
            continue
        top, score = find_vertical_overlap(canvas, frame)
        if top < 0 or score < threshold:
            stop_reason = f"match-failed(score={score:.3f})"
            break
        new_start = canvas.shape[0] - top
        if new_start < min_new_rows:
            stop_reason = "reached-bottom"
            break
        canvas = np.vstack([canvas, frame[new_start:]])

    # 与原图对比：canvas 应当无损还原原图（本用例模拟滚动到页面底部为止）
    h = canvas.shape[0]
    expect = full[:h]
    diff = np.abs(canvas.astype(int) - expect.astype(int)).mean()
    ok = diff < 1.0 and h == full.shape[0]
    record(
        "stitch: 长图拼接逐像素还原",
        ok,
        f"拼接高={h} 原图高={full.shape[0]} 平均像素差={diff:.4f} 停止原因={stop_reason}",
    )


def test_ocr() -> None:
    # 造一张白底黑字的图，字号放大以提高识别率
    img = Image.new("RGB", (900, 220), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = None
    for cand in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                 r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\arial.ttf"):
        try:
            font = ImageFont.truetype(cand, 56)
            break
        except Exception:
            continue
    text = "REA 截图工具 测试 2026"
    d.text((30, 60), text, fill=(0, 0, 0), font=font)

    try:
        got, backend = snapback.ocr_image(img)
    except Exception as exc:  # noqa: BLE001
        record("ocr: 识别中文+数字", False, f"失败: {exc}")
        return

    got_norm = got.replace(" ", "").replace("\n", "")
    hit = sum(1 for ch in "测试截图" if ch in got_norm)
    record(
        "ocr: 识别中文+数字",
        hit >= 2,
        f"backend={backend} 命中关键词数={hit}/4 输出={got!r}",
    )


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 66)
    print("后端自检")
    print("=" * 66)

    snapback.set_dpi_awareness()

    r = snapback.virtual_screen()
    record("capture: 取得虚拟屏幕尺寸", r.w > 0 and r.h > 0, f"{r.w}x{r.h} @({r.x},{r.y})")

    img = snapback.grab_all_screens()
    record("capture: 全屏抓取", img.size[0] > 0, f"{img.size} {img.mode}")

    test_overlap_detection()
    test_stitch_logic()
    test_ocr()

    print("=" * 66)
    failed = [n for n, s, _ in results if s == FAIL]
    print(f"合计 {len(results)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项：" + "、".join(failed))
    sys.exit(1 if failed else 0)
