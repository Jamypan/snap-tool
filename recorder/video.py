"""视频采集与合成。

采集：mss 抓屏（可选叠加摄像头画中画）→ 原始帧经管道交给 ffmpeg 编码成无声 MP4。
合成：录制结束后把系统声音、麦克风音轨混入视频，或保留为独立音轨。
"""
from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time

import cv2
import imageio_ffmpeg
import mss
import numpy as np
import wave

from .devices import get_display_size

PIP_POSITIONS = {
    "左上角": "top-left",
    "右上角": "top-right",
    "左下角": "bottom-left",
    "右下角": "bottom-right",
}


def _overlay_pip(frame: np.ndarray, pip: np.ndarray, position: str, scale: float) -> np.ndarray:
    """把摄像头画面缩小后贴到屏幕画面的角落。"""
    fh, fw = frame.shape[:2]
    ph, pw = pip.shape[:2]

    target_w = max(80, int(fw * scale))
    target_h = max(60, int(target_w * ph / pw))
    if target_h > fh * 0.5:
        target_h = int(fh * 0.5)
        target_w = max(80, int(target_h * pw / ph))
    pip = cv2.resize(pip, (target_w, target_h), interpolation=cv2.INTER_AREA)

    ph, pw = pip.shape[:2]
    margin = max(8, int(min(fw, fh) * 0.02))
    coords = {
        "top-left": (margin, margin),
        "top-right": (fw - pw - margin, margin),
        "bottom-left": (margin, fh - ph - margin),
        "bottom-right": (fw - pw - margin, fh - ph - margin),
    }
    x, y = coords.get(position, coords["bottom-right"])
    x = max(0, min(x, fw - pw))
    y = max(0, min(y, fh - ph))

    # 白色描边，方便看清画中画边界
    x0, y0 = max(0, x - 2), max(0, y - 2)
    x1, y1 = min(fw, x + pw + 2), min(fh, y + ph + 2)
    frame[y0:y1, x0:x1] = (255, 255, 255)
    frame[y : y + ph, x : x + pw] = pip
    return frame


class ScreenRecorder(threading.Thread):
    """录制全屏画面（含可选摄像头画中画）到无声 MP4。"""

    def __init__(
        self,
        output_path: str,
        *,
        display_index: int,
        fps: int,
        stop_event: threading.Event,
        messages: queue.Queue,
        camera_index: int | None = None,
        pip_position: str = "bottom-right",
        pip_scale: float = 0.25,
        region: dict | None = None,
        pause_event: threading.Event | None = None,
    ) -> None:
        """region: 可选的 mss 物理像素区域 {"x","y","width","height"}；
        None 表示整屏（沿用 display_index）。v52 框选/窗口录屏传具体区域。
        """
        super().__init__(daemon=True)
        self.output_path = output_path
        self.display_index = display_index
        self.fps = fps
        self.stop_event = stop_event
        self.messages = messages
        self.camera_index = camera_index
        self.pip_position = pip_position
        self.pip_scale = pip_scale
        self.region = region
        self.pause_event = pause_event          # v52：置位时暂停写帧（控制条暂停键）
        self.frames_written = 0

    def run(self) -> None:
        if self.region is not None:
            # 区域录制：宽高强制偶数（H.264 yuv420p 要求），不改左上角
            width = max(2, int(self.region["width"]) - int(self.region["width"]) % 2)
            height = max(2, int(self.region["height"]) - int(self.region["height"]) % 2)
        else:
            width, height = get_display_size(self.display_index)
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        command = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pixel_format",
            "bgr24",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(self.fps),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            self.output_path,
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            # 关键：用 pythonw 启动时，控制台子进程会弹黑窗口，必须显式禁止
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        camera = None
        pip_warned = False
        try:
            with mss.MSS() as sct:
                monitor = (
                    {
                        "left": int(self.region["x"]),
                        "top": int(self.region["y"]),
                        "width": width,
                        "height": height,
                    }
                    if self.region is not None
                    else sct.monitors[self.display_index]
                )
                if self.camera_index is not None:
                    camera = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                    if not camera.isOpened():
                        camera = None
                        self.messages.put("WARN:摄像头打开失败，本次只录制屏幕画面")

                interval = 1.0 / self.fps
                next_frame = time.perf_counter()

                while not self.stop_event.is_set():
                    # 暂停：仍照节拍空转，不抓帧不写帧，恢复后接着录
                    if self.pause_event is not None and self.pause_event.is_set():
                        time.sleep(1.0 / self.fps)
                        next_frame = time.perf_counter()
                        continue
                    shot = sct.grab(monitor)
                    frame = np.asarray(shot)[:, :, :3]  # BGRA -> BGR

                    if camera is not None:
                        ok, pip = camera.read()
                        if ok and pip is not None:
                            frame = _overlay_pip(frame, pip, self.pip_position, self.pip_scale)
                        elif not pip_warned:
                            pip_warned = True
                            self.messages.put("WARN:摄像头暂时读不到画面，画中画已跳过")

                    # 尺寸兜底：某些多显示器布局可能给出奇数尺寸
                    if frame.shape[1] != width or frame.shape[0] != height:
                        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

                    process.stdin.write(frame.tobytes())
                    self.frames_written += 1

                    next_frame += interval
                    delay = next_frame - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        next_frame = time.perf_counter()
        except BrokenPipeError:
            pass
        except Exception as exc:  # noqa: BLE001 - 采集异常要反馈到界面
            self.messages.put(f"ERROR:屏幕录制失败：{type(exc).__name__}: {exc}")
        finally:
            if camera is not None:
                camera.release()
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except Exception:  # noqa: BLE001
                    pass
            stderr = ""
            if process.stderr is not None:
                try:
                    stderr = process.stderr.read().decode("utf-8", errors="replace").strip()
                except Exception:  # noqa: BLE001
                    pass
            process.wait()

        if process.returncode not in (0, None):
            detail = stderr[-500:] if stderr else "无错误信息"
            self.messages.put(f"ERROR:视频编码失败：{detail}")
        else:
            self.messages.put(
                f"画面录制完成：{self.frames_written} 帧 / {self.frames_written / max(self.fps, 1):.1f} 秒"
            )


def compute_boost_db(wav_paths: list[str], target_peak: float = 0.90, max_gain_db: float = 18.0) -> float:
    """根据已录 WAV 的峰值计算自动增益（dB）。

    把最高峰值放大到接近满幅（0.90），防止削波；增益上限 max_gain_db，
    音量已经足够（峰值 > 目标）或无信号时返回 0（不放大）。
    """
    peak = 0.0
    for path in wav_paths:
        try:
            with wave.open(path, "rb") as w:
                frames = w.readframes(w.getnframes())
                data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32767.0
                if data.size:
                    peak = max(peak, float(np.max(np.abs(data))))
        except Exception:  # noqa: BLE001 - 读不到的文件跳过
            continue
    if peak <= 0.0:
        return 0.0
    gain_db = 20.0 * np.log10(min(target_peak / peak, 10 ** (max_gain_db / 20.0)))
    return round(float(gain_db), 1) if gain_db >= 1.0 else 0.0


def merge_audio_video(
    video_path: str,
    audio_paths: list[str],
    output_path: str,
    *,
    mode: str = "mix",
    labels: list[str] | None = None,
    gain_db: float = 0.0,
) -> None:
    """把录好的音轨合成进视频。

    mode='mix' 混合成一条音轨；mode='tracks' 保留多条独立音轨（播放器可切换）。
    gain_db>0 时对音轨做音量放大（自动增益，防止削波由峰值计算保证）。
    """
    if not audio_paths:
        shutil.copy2(video_path, output_path)
        return

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, "-y", "-loglevel", "error", "-i", video_path]
    for path in audio_paths:
        command += ["-i", path]

    count = len(audio_paths)
    # volume 放大后 AAC 编码可能过冲（实测约 20%），必须跟限幅器硬封顶
    limiter = ",alimiter=limit=0.89:level=false" if gain_db > 0 else ""
    if mode == "mix" and count > 1:
        streams = "".join(f"[{i}:a]" for i in range(1, count + 1))
        graph = f"{streams}amix=inputs={count}:duration=first:dropout_transition=0[a]"
        if gain_db > 0:
            graph += f";[a]volume={gain_db}dB{limiter}[aout]"
            command += ["-filter_complex", graph, "-map", "0:v:0", "-map", "[aout]"]
        else:
            command += ["-filter_complex", graph, "-map", "0:v:0", "-map", "[a]"]
    else:
        if gain_db > 0:
            parts = [f"[{i}:a]volume={gain_db}dB{limiter}[ag{i - 1}]" for i in range(1, count + 1)]
            command += ["-filter_complex", ";".join(parts), "-map", "0:v:0"]
            for i in range(count):
                command += ["-map", f"[ag{i}]"]
        else:
            command += ["-map", "0:v:0"]
            for i in range(1, count + 1):
                command += ["-map", f"{i}:a:0"]

    command += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"]

    if labels:
        for i, label in enumerate(labels[:count]):
            command += ["-metadata:s:a:" + str(i), "title=" + label]

    command.append(output_path)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 合成失败：{result.stderr.strip()[-500:]}")


def convert_mp4_to_gif(mp4_path: str, gif_path: str, fps: int = 12,
                       width: int = 640) -> None:
    """V52.1：把 MP4 转成 GIF（无音轨）。

    用 palettegen + paletteuse 两遍法生成调色板，避免直接转时颜色失真。
    默认 12fps、宽 640，兼顾体积与清晰度；GIF 不含声音。
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    scale_filter = f"fps={fps},scale={width}:-1:flags=lanczos"
    graph = f"[0:v]{scale_filter},split[a][b];[a]palettegen[p];[b][p]paletteuse"
    command = [
        ffmpeg, "-y", "-loglevel", "error", "-i", mp4_path,
        "-filter_complex", graph, "-loop", "0", gif_path,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 转 GIF 失败：{result.stderr.strip()[-500:]}")
