# -*- coding: utf-8 -*-
"""recording_flow.py —— v52 录屏流程编排（不依赖 snap.py，便于离屏自测）。

把 screen-recorder 的采集线程（画面 / 系统声音 / 麦克风）与合成逻辑封装成
一个 QObject 控制器，供 snap.py 调用：
  * start(region, settings) 启动录制；region 为 mss 物理区域 dict 或 None（整屏）
  * stop() / toggle_pause() 停止 / 暂停
  * 用 QTimer 轮询后台线程消息，转成 Qt 信号给界面

摄像头画中画、系统声音、麦克风、帧率、音频保存方式都来自 settings 字典。
"""
from __future__ import annotations

import queue
import shutil
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from recorder.audio import AudioCapture, boost_wav_file
from recorder.devices import list_loopback_devices, list_microphones, list_cameras
from recorder.runlog import log
from recorder.video import (
    PIP_POSITIONS,
    ScreenRecorder,
    compute_boost_db,
    convert_mp4_to_gif,
    merge_audio_video,
)
from recording_ui import MIX_LABEL, TRACKS_LABEL

# 摄像头位置中文名 → video.py 的英文值（video.py 自带 PIP_POSITIONS 映射）


class RecordingController(QObject):
    """录制控制器：管理采集线程、暂停、停止合成与信号通知。"""

    started = Signal()
    stopped = Signal(str)         # 输出视频路径
    error = Signal(str)
    levels = Signal(dict)         # 实时音量 {标签: 峰值}
    tick = Signal(int)            # 已录秒数
    finalized = Signal()          # 合成完成，界面可恢复

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.recording = False
        self.paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._workers: list[tuple[str, threading.Thread]] = []
        self._messages: queue.Queue = queue.Queue()
        self._levels: dict[str, float] = {}
        self._temp_dir: str | None = None
        self._system_wav: str | None = None
        self._mic_wav: str | None = None
        self._out_dir: Path | None = None
        self._base_name = ""
        self._start_time = 0.0
        self._settings: dict = {}
        self._audio_in_video = True
        self._audio_mode = MIX_LABEL
        self._separate = False
        self._export_format = "MP4"
        self._finalizing = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(200)

    # ------------------------------------------------------------ 启动
    def start(self, region: dict | None, settings: dict) -> bool:
        """启动录制。region 为物理像素 dict 或 None（整屏）。settings 见 collect_settings。"""
        if self.recording:
            return False
        self._settings = dict(settings)
        # V52.1：不再弹窗询问，音频保存方式在录屏面板里预设好。
        # audio_save: embed=整合进视频 / split=分开 WAV / both=两者都要
        audio_save = settings.get("audio_save", "embed")
        self._audio_in_video = audio_save in ("embed", "both")
        self._separate = audio_save in ("split", "both")
        self._export_format = settings.get("export_format", "MP4")
        self._audio_mode = settings.get("audio_mode", MIX_LABEL)
        log(f"音频设置：保存={audio_save} 进视频={self._audio_in_video} "
            f"单独WAV={self._separate} 导出={self._export_format}")

        out_dir = Path(settings.get("save_dir") or Path.home() / "Screenshots")
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.error.emit(f"无法创建保存目录：{exc}")
            return False
        self._out_dir = out_dir
        self._base_name = "录屏_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".gif" if self._export_format == "GIF" else ".mp4"
        final = out_dir / (self._base_name + ext)
        if final.exists():
            self.error.emit("同名视频已存在，请稍后再试")
            return False

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._messages = queue.Queue()
        self._levels = {}
        self._workers = []
        self._temp_dir = tempfile.mkdtemp(prefix="snap_rec_")
        self._system_wav = None
        self._mic_wav = None

        fps = int(settings.get("fps", 24))
        # 摄像头画中画
        camera_index = None
        pip_pos = "bottom-right"
        pip_scale = 0.25
        if settings.get("camera") and list_cameras():
            camera_index = list_cameras()[0]
            cn_pos = settings.get("pip_pos", "右下角")
            pip_pos = PIP_POSITIONS.get(cn_pos, "bottom-right")
            pip_scale = int(settings.get("pip_size", 25)) / 100.0

        screen = ScreenRecorder(
            str(Path(self._temp_dir) / "video.mp4"),
            display_index=1,
            fps=fps,
            stop_event=self._stop_event,
            messages=self._messages,
            camera_index=camera_index,
            pip_position=pip_pos,
            pip_scale=pip_scale,
            region=region,
            pause_event=self._pause_event,
            show_cursor=bool(settings.get("cursor", False)),
        )
        screen.start()
        self._workers.append(("画面", screen))

        if settings.get("system_audio") and list_loopback_devices():
            self._system_wav = str(Path(self._temp_dir) / "system.wav")
            t = AudioCapture(
                list_loopback_devices()[0].device, self._system_wav,
                stereo=True, stop_event=self._stop_event, messages=self._messages,
                label="系统声音", level_holder=self._levels,
                pause_event=self._pause_event,
            )
            t.start()
            self._workers.append(("系统声音", t))

        if settings.get("mic") and list_microphones():
            self._mic_wav = str(Path(self._temp_dir) / "mic.wav")
            t = AudioCapture(
                list_microphones()[0].device, self._mic_wav,
                stereo=False, stop_event=self._stop_event, messages=self._messages,
                label="麦克风", level_holder=self._levels,
                pause_event=self._pause_event,
            )
            t.start()
            self._workers.append(("麦克风", t))

        self.recording = True
        self.paused = False
        self._start_time = time.monotonic()
        log(f"开始录制 | 区域={region} fps={fps} 摄像头={camera_index} "
            f"鼠标指针={bool(settings.get('cursor', False))} "
            f"系统声={bool(self._system_wav)} 麦克风={bool(self._mic_wav)}")
        self.started.emit()
        return True

    # ------------------------------------------------------------ 停止 / 暂停
    def stop(self) -> None:
        if not self.recording or self._finalizing:
            return
        self.recording = False
        self.paused = False
        self._pause_event.clear()
        self._stop_event.set()
        self._finalizing = True
        log("停止录制，开始合成")
        threading.Thread(target=self._finalize, daemon=True).start()

    def toggle_pause(self) -> bool:
        """切换暂停，返回当前是否处于暂停。"""
        if not self.recording:
            return False
        self.paused = not self.paused
        if self.paused:
            self._pause_event.set()
        else:
            self._pause_event.clear()
        return self.paused

    def elapsed(self) -> int:
        if not self.recording:
            return 0
        return int(time.monotonic() - self._start_time)

    # ------------------------------------------------------------ 合成
    def _finalize(self) -> None:
        # V52.1：等采集线程真正收尾（画面线程要 close stdin + ffmpeg.wait 写出 moov），
        # 否则拿到的 MP4 可能还没写完，转 GIF / 合成都会失败。
        for _label, worker in self._workers:
            try:
                worker.join(timeout=15)
            except Exception:  # noqa: BLE001
                pass
        audio_paths: list[str] = []
        labels: list[str] = []
        for path, label in ((self._system_wav, "系统声音"), (self._mic_wav, "麦克风")):
            if path and Path(path).exists() and Path(path).stat().st_size > 44:
                audio_paths.append(path)
                labels.append(label)

        out_dir = Path(self._out_dir)  # type: ignore[arg-type]
        is_gif = self._export_format == "GIF"
        final = out_dir / (self._base_name + (".gif" if is_gif else ".mp4"))
        try:
            video_source = str(Path(self._temp_dir) / "video.mp4")
            gain_db = 0.0
            if audio_paths:
                gain_db = compute_boost_db(audio_paths)
            # 先合成到带声音的 MP4；GIF 无音轨，用它作为转换源
            merged = str(Path(self._temp_dir) / "merged.mp4")
            if self._audio_in_video:
                mode = "tracks" if self._audio_mode == TRACKS_LABEL else "mix"
                merge_audio_video(video_source, audio_paths, merged,
                                  mode=mode, labels=labels, gain_db=gain_db)
            else:
                shutil.copy2(video_source, merged)
            if is_gif:
                convert_mp4_to_gif(merged, str(final))
            else:
                shutil.copy2(merged, str(final))
            if self._separate:
                for path, label in zip(audio_paths, labels):
                    target = out_dir / f"{self._base_name}_{label}.wav"
                    shutil.copy2(path, str(target))
                    if gain_db > 0:
                        boost_wav_file(str(target), gain_db)
            log(f"合成完成：{final} 音轨={audio_paths} 格式={self._export_format}")
            self.stopped.emit(str(final))
        except Exception as exc:  # noqa: BLE001
            log(f"合成失败：{type(exc).__name__}: {exc}")
            self.error.emit(f"保存视频失败：{type(exc).__name__}: {exc}")
        finally:
            if self._temp_dir:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._finalizing = False
            self.finalized.emit()

    # ------------------------------------------------------------ 消息轮询
    def _poll(self) -> None:
        # 计时与电平
        if self.recording:
            self.tick.emit(self.elapsed())
            if not self.paused:
                self.levels.emit(dict(self._levels))
        while not self._messages.empty():
            try:
                msg = self._messages.get_nowait()
            except queue.Empty:
                break
            if msg.startswith("ERROR:"):
                self.error.emit(msg[6:])
                if self.recording:
                    self.stop()
            elif msg.startswith("WARN:"):
                log("WARN " + msg[5:])
            else:
                log(msg)


__all__ = ["RecordingController"]
