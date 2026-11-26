"""音频采集：把系统声音和麦克风分别录成独立的 WAV 文件。

每个音源一个线程，停止后各自生成文件，再由 video.py 中的合成函数
决定是混合成一条音轨，还是保留为多条独立音轨。
"""
from __future__ import annotations

import queue
import threading
import wave

import numpy as np

from .runlog import log

SAMPLE_RATE = 48000
BLOCK_FRAMES = 4800  # 100 毫秒


def boost_wav_file(path: str, gain_db: float) -> None:
    """把 WAV 文件的音量放大 gain_db 分贝（自动增益用，带削波保护）。"""
    if gain_db <= 0:
        return
    gain = 10 ** (gain_db / 20.0)
    with wave.open(path, "rb") as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) * gain
    data = np.clip(data, -32767, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setparams(params)
        w.writeframes(data.tobytes())


class AudioCapture(threading.Thread):
    """把单个 soundcard 设备的输入写成 16bit PCM WAV。"""

    def __init__(
        self,
        device,
        output_path: str,
        *,
        stereo: bool,
        stop_event: threading.Event,
        messages: queue.Queue,
        label: str,
        level_holder: dict | None = None,
        pause_event: threading.Event | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.device = device
        self.output_path = output_path
        self.stereo = stereo
        self.stop_event = stop_event
        self.messages = messages
        self.label = label
        self.level_holder = level_holder if level_holder is not None else {}
        self.pause_event = pause_event          # v52：置位时暂停写音频帧
        self.wrote_frames = 0
        self.peak = 0.0

    def _pick_channels(self, device) -> int:
        available = getattr(device, "channels", None)
        if isinstance(available, (list, tuple)) and available:
            return max(available) if self.stereo else min(available)
        if isinstance(available, int):
            return available
        return 2 if self.stereo else 1

    def run(self) -> None:
        # 注意：不要在采集线程显式 CoInitializeEx——pythonw 下与 soundcard
        # 内部的模块级 COM 初始化叠加会导致卡死，实测不初始化反而稳定
        device = getattr(self.device, "device", self.device)  # 兼容 AudioDeviceInfo 包装
        channels = self._pick_channels(device)
        log(f"[{self.label}] 采集线程启动：设备={getattr(device, 'name', '?')} 声道数={channels} 输出={self.output_path}")
        try:
            with wave.open(self.output_path, "wb") as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)

                with device.recorder(
                    samplerate=SAMPLE_RATE,
                    channels=channels,
                    blocksize=BLOCK_FRAMES,
                ) as recorder:
                    while not self.stop_event.is_set():
                        data = recorder.record(numframes=BLOCK_FRAMES)
                        if self.pause_event is not None and self.pause_event.is_set():
                            continue  # 暂停：照样读设备排空缓冲，但不写入文件
                        if data.size == 0:
                            continue
                        chunk_peak = float(np.max(np.abs(data))) if data.size else 0.0
                        if chunk_peak > self.peak:
                            self.peak = chunk_peak
                        # 实时电平，供界面在录制中显示
                        self.level_holder[self.label] = chunk_peak
                        pcm = (np.clip(data, -1.0, 1.0) * 32767.0).astype("<i2")
                        wav.writeframes(pcm.tobytes())
                        self.wrote_frames += len(data)

            duration = self.wrote_frames / SAMPLE_RATE
            log(f"[{self.label}] 采集结束：{duration:.1f} 秒，{self.wrote_frames} 帧，峰值 {self.peak:.4f}")
            if self.peak < 0.001:
                detail = (
                    f"{self.label}录了 {duration:.1f} 秒，但没有检测到任何声音信号。"
                    "请确认录制时电脑确实在播放声音（系统声音）或对着麦克风说话。"
                )
                self.messages.put(f"WARN:{detail}")
            else:
                self.messages.put(
                    f"{self.label}录制完成：{duration:.1f} 秒，音量峰值 {self.peak:.2f}"
                )
        except Exception as exc:  # noqa: BLE001 - 任何采集异常都要反馈到界面
            self.messages.put(f"ERROR:{self.label}录制失败：{type(exc).__name__}: {exc}")
            log(f"[{self.label}] 采集异常：{type(exc).__name__}: {exc}")
